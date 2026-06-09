"""Shared CandidatePaper dataclass used across all pipeline stages."""
from __future__ import annotations

import dataclasses
import json
import re
from enum import Enum
from typing import Dict, List, Optional


class PubType(str, Enum):
    PEER_REVIEWED = "peer-reviewed"
    PREPRINT = "preprint"
    UNKNOWN = "unknown"


class Decision(str, Enum):
    INCLUDE = "include"
    EXCLUDE = "exclude"
    NEEDS_REVIEW = "needs-review"


@dataclasses.dataclass
class CandidatePaper:
    # ── Core metadata ──────────────────────────────────────────────────────
    title: str
    url: str
    year: int
    source: str  # which adapter found it
    pub_type: PubType = PubType.UNKNOWN

    # ── Optional metadata ──────────────────────────────────────────────────
    abstract: str = ""
    authors: List[str] = dataclasses.field(default_factory=list)
    venue: str = ""
    doi: str = ""

    # ── Scoring ────────────────────────────────────────────────────────────
    relevance_score: float = 0.0

    # ── Ensemble votes ─────────────────────────────────────────────────────
    rule_based_vote: Optional[Decision] = None
    llm_vote: Optional[Decision] = None
    category_votes: Dict[str, int] = dataclasses.field(default_factory=dict)
    include_votes: int = 0
    exclude_votes: int = 0

    # ── Final decision ──────────────────────────────────────────────────────
    final_category: str = ""
    reviewer_rationale: str = ""
    evidence_snippets: List[str] = dataclasses.field(default_factory=list)

    # ── Full-text fields ────────────────────────────────────────────────────
    full_text_available: bool = False
    full_text_source: str = ""
    extracted_sections: Dict[str, str] = dataclasses.field(default_factory=dict)
    deep_review_rationale: str = ""

    # ── Stage decisions ────────────────────────────────────────────────────
    abstract_screen_decision: Optional[Decision] = None
    deep_review_decision: Optional[Decision] = None

    # ── Outcome ────────────────────────────────────────────────────────────
    needs_human_review: bool = False
    markdown_entry: str = ""

    # ── Helpers ────────────────────────────────────────────────────────────
    @property
    def normalized_doi(self) -> str:
        """Lowercase stripped DOI for dedup."""
        doi = (self.doi or "").strip().lower()
        doi = re.sub(r"^https?://doi\.org/", "", doi)
        return doi.rstrip(".")

    @property
    def normalized_url(self) -> str:
        """URL stripped of fragments and query strings for dedup."""
        url = (self.url or "").strip().rstrip("/").split("#")[0].split("?")[0]
        return url.lower()

    @property
    def normalized_title(self) -> str:
        """Lowercase, punctuation-stripped title for fuzzy dedup."""
        t = self.title.lower()
        t = re.sub(r"[^a-z0-9 ]", " ", t)
        return re.sub(r"\s+", " ", t).strip()

    def to_dict(self) -> dict:
        d = dataclasses.asdict(self)
        d["pub_type"] = self.pub_type.value
        for field in ("rule_based_vote", "llm_vote", "abstract_screen_decision", "deep_review_decision"):
            val = getattr(self, field)
            d[field] = val.value if val is not None else None
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

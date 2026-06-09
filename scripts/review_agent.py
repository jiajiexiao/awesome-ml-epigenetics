"""Review agent.

Provides:
  - rule_based_score()         : keyword-density relevance scoring
  - stage1_llm_screen()        : LLM abstract-level screen (Stage 1)
  - stage2_deep_review()       : LLM full-text deep review (Stage 2)
  - deterministic check helpers: check_format, check_no_duplicate, check_link_reachable
  - _get_llm_client()          : returns GitHub Models OpenAI-compatible client
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from .schemas import CandidatePaper, Decision, PubType


# ── Rule-based scoring ────────────────────────────────────────────────────────

def rule_based_score(
    paper: CandidatePaper, keywords: List[str], threshold: float
) -> Tuple[float, Decision]:
    """
    Score by keyword density in title + abstract.
    Returns (score 0-1, decision).
    """
    combined = (paper.title + " " + paper.abstract).lower()
    matches = sum(1 for kw in keywords if kw.lower() in combined)
    score = min(1.0, matches / max(len(keywords), 1) * 2)

    # Boost for title matches
    title_lower = paper.title.lower()
    title_matches = sum(1 for kw in keywords if kw.lower() in title_lower)
    score = min(1.0, score + title_matches * 0.05)

    # Preprints need a higher bar
    eff_threshold = threshold
    if paper.pub_type == PubType.PREPRINT:
        eff_threshold = min(threshold + 0.15, 0.95)

    if score >= eff_threshold:
        return score, Decision.INCLUDE
    elif score >= eff_threshold * 0.75:
        return score, Decision.NEEDS_REVIEW
    return score, Decision.EXCLUDE


# ── GitHub Models LLM client ──────────────────────────────────────────────────

def _get_llm_client() -> Optional[Any]:
    """Return an OpenAI-compatible client for GitHub Models, or None if unavailable."""
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GITHUB_MODELS_TOKEN")
    if not token:
        return None
    try:
        from openai import OpenAI
        return OpenAI(
            base_url="https://models.inference.ai.azure.com",
            api_key=token,
        )
    except ImportError:
        return None


def _llm_call(
    client: Any, model: str, messages: List[Dict], max_tokens: int = 512
) -> Optional[str]:
    """Single LLM call. Returns response text or None on error."""
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.1,
        )
        return resp.choices[0].message.content or ""
    except Exception as e:
        print(f"[LLM] call error: {e}")
        return None


# ── Stage 1: abstract screen ──────────────────────────────────────────────────

_S1_SYSTEM = (
    "You are a strict scientific curator for an 'awesome' list of machine learning "
    "papers in epigenetics. Evaluate candidates based ONLY on the provided metadata. "
    "Respond in strict JSON."
)

_S1_USER = """\
Evaluate this candidate for category: **{category}**

Title: {title}
Year: {year}
Venue: {venue}
Abstract (excerpt): {abstract}

Criteria for INCLUDE:
1. ML / deep learning / statistical modelling is the CORE method (not just mentioned)
2. Directly addresses epigenetics: DNA methylation, histone modifications, chromatin
   accessibility, liquid biopsy with epigenetic markers, or novel epigenetic assays
3. Novel contribution (not a plain review/survey)
4. Fits category: {category}

Respond with ONLY this JSON (no other text):
{{
  "decision": "include" | "exclude" | "needs-review",
  "score": <float 0-10>,
  "rationale": "<1-2 sentences citing title/abstract evidence>"
}}"""


def stage1_llm_screen(
    paper: CandidatePaper,
    category: str,
    model: str,
    client: Any,
    max_abstract_chars: int = 1200,
) -> Tuple[Optional[Decision], str]:
    """Run Stage-1 LLM abstract screen. Returns (decision, rationale)."""
    abstract_excerpt = paper.abstract[:max_abstract_chars].strip() or "(no abstract)"
    prompt = _S1_USER.format(
        category=category,
        title=paper.title,
        year=paper.year,
        venue=paper.venue or "unknown",
        abstract=abstract_excerpt,
    )
    raw = _llm_call(
        client, model,
        [{"role": "system", "content": _S1_SYSTEM}, {"role": "user", "content": prompt}],
        max_tokens=256,
    )
    if not raw:
        return None, "LLM unavailable"
    return _parse_decision_json(raw)


# ── Stage 2: full-text deep review ───────────────────────────────────────────

_S2_SYSTEM = (
    "You are a rigorous peer reviewer for a curated 'awesome' list of ML in epigenetics. "
    "You have been given extracted sections from the paper's full text. "
    "Evaluate thoroughly. Respond in strict JSON."
)

_S2_USER = """\
DEEP REVIEW for category: **{category}**

Title: {title}
Year: {year}
Venue: {venue}

--- Extracted sections ---
{sections_text}
---

Evaluate ALL of the following:
1. Is ML/DL a CORE method (not just mentioned in passing)?
2. Is the epigenetics connection DIRECT and substantial?
3. Is there a NOVEL methodological or scientific contribution?
4. Is the suggested category **{category}** the right fit?

Only INCLUDE if all criteria are satisfied. Otherwise exclude or needs-review.

Respond with ONLY this JSON:
{{
  "decision": "include" | "exclude" | "needs-review",
  "score": <float 0-10>,
  "rationale": "<2-3 sentences citing specific evidence from sections above>",
  "suggested_description": "<one concise sentence starting with the method type, \
e.g. Transformer-based... / CNN-based...>"
}}"""


def stage2_deep_review(
    paper: CandidatePaper,
    category: str,
    model: str,
    client: Any,
    max_calls: int = 4,
    max_section_chars: int = 2000,
) -> Tuple[Optional[Decision], str, str]:
    """
    Run Stage-2 full-text deep review.
    Returns (decision, rationale, suggested_description).
    """
    if not paper.extracted_sections:
        return Decision.NEEDS_REVIEW, "No full-text sections available", ""

    sections_text, calls_used = _build_sections_text(
        paper.extracted_sections, max_section_chars, model, client, max_calls - 1
    )
    if max_calls - calls_used <= 0:
        return Decision.NEEDS_REVIEW, "Exceeded LLM call budget during summarisation", ""

    prompt = _S2_USER.format(
        category=category,
        title=paper.title,
        year=paper.year,
        venue=paper.venue or "unknown",
        sections_text=sections_text,
    )
    raw = _llm_call(
        client, model,
        [{"role": "system", "content": _S2_SYSTEM}, {"role": "user", "content": prompt}],
        max_tokens=400,
    )
    if not raw:
        return None, "LLM unavailable for deep review", ""

    decision, rationale = _parse_decision_json(raw)
    suggested_desc = ""
    try:
        data = json.loads(_extract_json(raw))
        suggested_desc = str(data.get("suggested_description", ""))
    except Exception:
        pass
    return decision, rationale, suggested_desc


def _build_sections_text(
    sections: Dict[str, str],
    max_section_chars: int,
    model: str,
    client: Any,
    budget: int,
) -> Tuple[str, int]:
    """Build sections block; summarise oversized sections via LLM when budget allows."""
    calls_used = 0
    priority = ["abstract", "methods", "results", "discussion", "introduction", "conclusion"]
    ordered = sorted(sections.keys(), key=lambda k: priority.index(k) if k in priority else 99)
    parts: List[str] = []

    for name in ordered:
        text = sections[name].strip()
        if len(text) <= max_section_chars:
            parts.append(f"[{name.upper()}]\n{text}")
        elif calls_used < budget and client:
            summary_prompt = (
                f"Summarise the '{name}' section in 3-5 sentences, keeping key "
                f"methods and findings:\n\n{text[:3000]}"
            )
            summary = _llm_call(
                client, model,
                [{"role": "user", "content": summary_prompt}],
                max_tokens=200,
            )
            calls_used += 1
            label = f"[{name.upper()} — summarised]"
            parts.append(f"{label}\n{(summary or text[:max_section_chars]).strip()}")
        else:
            parts.append(f"[{name.upper()}]\n{text[:max_section_chars]}")

    return "\n\n".join(parts), calls_used


# ── Deterministic checks ──────────────────────────────────────────────────────

_ENTRY_RE = re.compile(
    r"^\s*-\s+\[.+?\]\(https?://[^\)]+\)\s+\(\d{4}[^\)]*\)\s+-\s+\S.*$"
)


def check_format(entry: str) -> Tuple[bool, str]:
    """Verify: - [Name](URL) (Year) - Description."""
    if _ENTRY_RE.match(entry.rstrip()):
        return True, ""
    return False, f"Format violation: {entry[:120]!r}"


def check_no_duplicate(
    paper: CandidatePaper,
    existing_urls: set,
    existing_dois: set,
    existing_titles: List[str],
) -> Tuple[bool, str]:
    """Return (True, '') if no duplicate found."""
    from rapidfuzz import fuzz
    if paper.normalized_url in existing_urls:
        return False, f"Duplicate URL: {paper.normalized_url}"
    if paper.normalized_doi and paper.normalized_doi in existing_dois:
        return False, f"Duplicate DOI: {paper.normalized_doi}"
    for t in existing_titles:
        if fuzz.ratio(paper.normalized_title, t) > 88:
            return False, f"Duplicate title (fuzzy match): {paper.title[:80]!r}"
    return True, ""


def check_link_reachable(url: str) -> Tuple[bool, str]:
    """HEAD request to verify URL resolves (follow redirects)."""
    import httpx  # local import to avoid top-level side effect
    try:
        resp = httpx.head(url, timeout=12, follow_redirects=True)
        if resp.status_code < 400:
            return True, ""
        return False, f"HTTP {resp.status_code}: {url}"
    except Exception as e:
        return False, f"Unreachable {url}: {e}"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_json(text: str) -> str:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    return m.group(0) if m else text


def _parse_decision_json(raw: str) -> Tuple[Optional[Decision], str]:
    try:
        data = json.loads(_extract_json(raw))
        ds = (data.get("decision") or "needs-review").lower()
        decision = Decision(ds) if ds in Decision._value2member_map_ else Decision.NEEDS_REVIEW
        rationale = str(data.get("rationale", ""))
        return decision, rationale
    except Exception:
        return Decision.NEEDS_REVIEW, f"JSON parse error: {raw[:120]}"

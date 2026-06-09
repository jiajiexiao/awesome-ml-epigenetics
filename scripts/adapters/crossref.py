"""Crossref adapter — https://api.crossref.org

Used for DOI normalization and metadata enrichment, not primary discovery.
"""
from __future__ import annotations

import re
import time
from typing import Optional

import httpx

from ..schemas import CandidatePaper, PubType

_BASE = "https://api.crossref.org/works"
_DELAY = 0.2


def lookup_doi(doi: str, email: str = "") -> Optional[CandidatePaper]:
    """Fetch full metadata for a known DOI. Returns None on failure."""
    clean_doi = re.sub(r"^https?://doi\.org/", "", doi).strip()
    if not clean_doi:
        return None

    headers = {}
    if email:
        headers["User-Agent"] = f"AwesomeMLEpigenetics/1.0 (mailto:{email})"

    try:
        resp = httpx.get(f"{_BASE}/{clean_doi}", headers=headers, timeout=15)
        resp.raise_for_status()
        item = resp.json().get("message", {})
    except Exception:
        return None
    finally:
        time.sleep(_DELAY)

    title_list = item.get("title") or []
    title = title_list[0] if title_list else ""
    if not title:
        return None

    year = 0
    for date_field in ("published-print", "published-online", "created"):
        dp = (item.get(date_field) or {}).get("date-parts")
        if dp and dp[0]:
            try:
                year = int(dp[0][0])
                break
            except (TypeError, ValueError, IndexError):
                pass

    abstract = re.sub(r"<[^>]+>", " ", item.get("abstract") or "")
    abstract = re.sub(r"\s+", " ", abstract).strip()

    container = item.get("container-title") or []
    venue = container[0] if container else ""

    authors_raw = item.get("author") or []
    authors = [
        f"{a.get('given', '')} {a.get('family', '')}".strip()
        for a in authors_raw[:6]
        if a.get("family")
    ]

    item_type = item.get("type") or ""
    pub_type = PubType.PREPRINT if "posted-content" in item_type else PubType.PEER_REVIEWED

    return CandidatePaper(
        title=title,
        url=f"https://doi.org/{clean_doi}",
        year=year,
        source="crossref",
        pub_type=pub_type,
        abstract=abstract,
        authors=authors,
        venue=venue,
        doi=clean_doi,
    )

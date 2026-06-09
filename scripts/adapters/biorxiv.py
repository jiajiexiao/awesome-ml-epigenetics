"""bioRxiv / medRxiv adapter — https://api.biorxiv.org

Free, no API key. Date-range endpoint with local keyword filtering.
"""
from __future__ import annotations

import time
from typing import List

import httpx

from ..schemas import CandidatePaper, PubType

_BASE = "https://api.biorxiv.org/details"
_DELAY = 0.5
_PAGE_SIZE = 100
_MAX_PAGES = 3


def search(
    search_terms: List[str],
    from_date: str,
    to_date: str,
    email: str = "",
    max_per_term: int = 25,
    server: str = "biorxiv",
) -> List[CandidatePaper]:
    """Fetch papers in a date range and filter by keyword match."""
    papers: List[CandidatePaper] = []
    seen: set[str] = set()

    # Build keyword set from all search terms for local filtering
    all_keywords: set[str] = set()
    for term in search_terms:
        for w in term.lower().split():
            if len(w) > 3:
                all_keywords.add(w)

    max_total = max_per_term * len(search_terms)
    cursor = 0

    for _ in range(_MAX_PAGES):
        url = f"{_BASE}/{server}/{from_date}/{to_date}/{cursor}/json"
        try:
            resp = httpx.get(url, timeout=20)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            time.sleep(2)
            break

        collection = data.get("collection") or []
        if not collection:
            break

        for item in collection:
            doi = (item.get("doi") or "").strip()
            if not doi or doi in seen:
                continue

            title = (item.get("title") or "").strip()
            abstract = (item.get("abstract") or "").strip()
            if not title:
                continue

            # Keyword relevance filter
            combined = (title + " " + abstract).lower()
            if not any(kw in combined for kw in all_keywords):
                continue

            seen.add(doi)
            year_str = (item.get("date") or "")[:4]
            year = int(year_str) if year_str.isdigit() else 0
            authors_raw = item.get("authors") or ""
            authors = [a.strip() for a in authors_raw.split(";") if a.strip()][:6]

            papers.append(
                CandidatePaper(
                    title=title,
                    url=f"https://doi.org/{doi}",
                    year=year,
                    source=server,
                    pub_type=PubType.PREPRINT,
                    abstract=abstract,
                    authors=authors,
                    venue=server.capitalize(),
                    doi=doi,
                )
            )

            if len(papers) >= max_total:
                return papers

        cursor += len(collection)
        time.sleep(_DELAY)

    return papers

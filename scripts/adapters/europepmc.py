"""Europe PMC adapter — https://europepmc.org/RestfulWebService

Free, no API key. Broad biomed coverage with structured abstracts.
"""
from __future__ import annotations

import time
from typing import List

import httpx

from ..schemas import CandidatePaper, PubType

_BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
_DELAY = 0.5


def search(
    search_terms: List[str],
    from_date: str,
    to_date: str,
    email: str = "",
    max_per_term: int = 25,
) -> List[CandidatePaper]:
    papers: List[CandidatePaper] = []
    seen: set[str] = set()

    from_year = from_date[:4]
    to_year = to_date[:4]

    for term in search_terms:
        query = f"({term}) AND (PUB_YEAR:[{from_year} TO {to_year}])"
        params = {
            "query": query,
            "resultType": "core",
            "pageSize": min(max_per_term, 100),
            "format": "json",
            "sort": "RELEVANCE",
        }

        try:
            resp = httpx.get(_BASE, params=params, timeout=20)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            time.sleep(2)
            continue

        results = (data.get("resultList") or {}).get("result") or []

        for item in results:
            item_id = item.get("pmid") or item.get("id") or ""
            if not item_id or item_id in seen:
                continue
            seen.add(item_id)

            title = (item.get("title") or "").strip().rstrip(".")
            if not title:
                continue

            doi = (item.get("doi") or "").strip()
            abstract = (item.get("abstractText") or "").strip()
            year_str = str(
                item.get("pubYear") or item.get("firstPublicationDate") or ""
            )[:4]
            year = int(year_str) if year_str.isdigit() else 0
            venue = (item.get("journalTitle") or "").strip()
            url = (
                f"https://doi.org/{doi}"
                if doi
                else f"https://europepmc.org/article/MED/{item_id}"
            )

            author_list = (item.get("authorList") or {}).get("author") or []
            authors = [
                (a.get("fullName") or a.get("lastName") or "")
                for a in author_list[:6]
            ]

            src_type = (item.get("source") or "").upper()
            pub_type = PubType.PREPRINT if src_type == "PPR" else PubType.PEER_REVIEWED

            papers.append(
                CandidatePaper(
                    title=title,
                    url=url,
                    year=year,
                    source="europepmc",
                    pub_type=pub_type,
                    abstract=abstract,
                    authors=[a for a in authors if a],
                    venue=venue,
                    doi=doi,
                )
            )

        time.sleep(_DELAY)

    return papers

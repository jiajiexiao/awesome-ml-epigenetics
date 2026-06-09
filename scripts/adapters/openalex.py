"""OpenAlex adapter — https://api.openalex.org/works

Free, no API key. Add mailto for polite pool (~100k req/day).
"""
from __future__ import annotations

import asyncio
from typing import List, Optional

import httpx

from ..http_client import arequest, make_async_client
from ..schemas import CandidatePaper, PubType

_BASE = "https://api.openalex.org/works"
_DELAY = 0.12  # stay inside polite pool rate limit


async def search(
    search_terms: List[str],
    from_date: str,
    to_date: str,
    email: str = "",
    max_per_term: int = 25,
    client: Optional[httpx.AsyncClient] = None,
) -> List[CandidatePaper]:
    own_client = client is None
    if client is None:
        client = make_async_client()
    papers: List[CandidatePaper] = []
    seen: set[str] = set()

    for term in search_terms:
        params: dict = {
            "search": term,
            "filter": f"from_publication_date:{from_date},to_publication_date:{to_date}",
            "select": (
                "id,title,abstract_inverted_index,doi,publication_year,"
                "primary_location,authorships,type"
            ),
            "per-page": min(max_per_term, 50),
            "sort": "relevance_score:desc",
        }
        if email:
            params["mailto"] = email

        try:
            resp = await arequest(client, "GET", _BASE, params=params)
            resp.raise_for_status()
            results = resp.json().get("results", [])
        except Exception:
            continue

        for work in results:
            oa_id: str = work.get("id") or ""
            if oa_id in seen:
                continue
            seen.add(oa_id)

            doi = (work.get("doi") or "").replace("https://doi.org/", "").strip()
            title = (work.get("title") or "").strip()
            if not title:
                continue
            year = int(work.get("publication_year") or 0)

            abstract = _reconstruct_abstract(work.get("abstract_inverted_index"))
            loc = work.get("primary_location") or {}
            src = loc.get("source") or {}
            venue = src.get("display_name") or ""
            landing_url = loc.get("landing_page_url") or ""
            url = landing_url or (f"https://doi.org/{doi}" if doi else oa_id)

            authors = [
                (a.get("author") or {}).get("display_name") or ""
                for a in (work.get("authorships") or [])[:6]
            ]

            work_type = work.get("type") or ""
            pub_type = PubType.PREPRINT if work_type == "preprint" else PubType.PEER_REVIEWED

            papers.append(
                CandidatePaper(
                    title=title,
                    url=url,
                    year=year,
                    source="openalex",
                    pub_type=pub_type,
                    abstract=abstract,
                    authors=[a for a in authors if a],
                    venue=venue,
                    doi=doi,
                )
            )

        await asyncio.sleep(_DELAY)

    if own_client:
        await client.aclose()
    return papers


def _reconstruct_abstract(inv_idx: dict | None) -> str:
    if not inv_idx:
        return ""
    positions: list[tuple[int, str]] = []
    for word, pos_list in inv_idx.items():
        for pos in pos_list:
            positions.append((pos, word))
    positions.sort()
    return " ".join(w for _, w in positions)

"""arXiv adapter — https://export.arxiv.org/api/query

Free, no API key. Good coverage of cs.LG + q-bio preprints.
"""
from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from typing import List
from urllib.parse import quote

import httpx

from ..schemas import CandidatePaper, PubType

_BASE = "https://export.arxiv.org/api/query"
_NS = "http://www.w3.org/2005/Atom"
_DELAY = 0.5


def search(
    search_terms: List[str],
    from_date: str,
    to_date: str,
    email: str = "",
    max_per_term: int = 20,
) -> List[CandidatePaper]:
    papers: List[CandidatePaper] = []
    seen: set[str] = set()

    # arXiv date format: YYYYMMDDHHII
    from_dt = from_date.replace("-", "") + "0000"
    to_dt = to_date.replace("-", "") + "2359"

    for term in search_terms:
        query = f"all:{quote(term)} AND submittedDate:[{from_dt} TO {to_dt}]"
        params = {
            "search_query": query,
            "max_results": min(max_per_term, 50),
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }

        try:
            resp = httpx.get(_BASE, params=params, timeout=25)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
        except Exception:
            time.sleep(2)
            continue

        for entry in root.findall(f"{{{_NS}}}entry"):
            arxiv_url = (entry.findtext(f"{{{_NS}}}id") or "").strip()
            if not arxiv_url or arxiv_url in seen:
                continue
            seen.add(arxiv_url)

            title = " ".join(
                (entry.findtext(f"{{{_NS}}}title") or "").split()
            )
            if not title or title == "Error":
                continue

            abstract = " ".join(
                (entry.findtext(f"{{{_NS}}}summary") or "").split()
            )

            published = entry.findtext(f"{{{_NS}}}published") or ""
            year = int(published[:4]) if len(published) >= 4 else 0

            doi = ""
            for link in entry.findall(f"{{{_NS}}}link"):
                if link.get("title") == "doi":
                    doi = (link.get("href") or "").replace("https://doi.org/", "").strip()

            authors = [
                (a.findtext(f"{{{_NS}}}name") or "")
                for a in entry.findall(f"{{{_NS}}}author")[:6]
            ]

            papers.append(
                CandidatePaper(
                    title=title,
                    url=arxiv_url,
                    year=year,
                    source="arxiv",
                    pub_type=PubType.PREPRINT,
                    abstract=abstract,
                    authors=[a for a in authors if a],
                    venue="arXiv",
                    doi=doi,
                )
            )

        time.sleep(_DELAY)

    return papers

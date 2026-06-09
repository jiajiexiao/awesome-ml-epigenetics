"""PubMed E-utilities adapter.

Free, no API key. Rate limit: 3 req/s without key.
"""
from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from typing import List

import httpx

from ..schemas import CandidatePaper, PubType

_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
_DELAY = 0.4  # stay under 3 req/s


def search(
    search_terms: List[str],
    from_date: str,
    to_date: str,
    email: str = "",
    max_per_term: int = 20,
) -> List[CandidatePaper]:
    papers: List[CandidatePaper] = []
    seen: set[str] = set()
    from_y, to_y = from_date[:4], to_date[:4]

    for term in search_terms:
        query = f"{term} AND ({from_y}[pdat]:{to_y}[pdat])"
        esearch_params: dict = {
            "db": "pubmed",
            "term": query,
            "retmax": min(max_per_term, 50),
            "retmode": "json",
            "sort": "relevance",
        }
        if email:
            esearch_params["email"] = email

        try:
            resp = httpx.get(_ESEARCH, params=esearch_params, timeout=20)
            resp.raise_for_status()
            id_list = resp.json().get("esearchresult", {}).get("idlist", [])
        except Exception:
            time.sleep(2)
            continue

        if not id_list:
            time.sleep(_DELAY)
            continue

        time.sleep(_DELAY)

        try:
            fetch_resp = httpx.post(
                _EFETCH,
                data={
                    "db": "pubmed",
                    "id": ",".join(id_list),
                    "retmode": "xml",
                    "rettype": "abstract",
                },
                timeout=30,
            )
            fetch_resp.raise_for_status()
            root = ET.fromstring(fetch_resp.content)
        except Exception:
            time.sleep(2)
            continue

        for article in root.findall(".//PubmedArticle"):
            pmid_el = article.find(".//PMID")
            pmid = (pmid_el.text or "").strip() if pmid_el is not None else ""
            if not pmid or pmid in seen:
                continue
            seen.add(pmid)

            title_el = article.find(".//ArticleTitle")
            title = _inner_text(title_el).strip()
            if not title:
                continue

            abstract_parts = article.findall(".//AbstractText")
            abstract = " ".join(_inner_text(p) for p in abstract_parts).strip()

            doi = ""
            for id_el in article.findall(".//ArticleId"):
                if id_el.get("IdType") == "doi":
                    doi = (id_el.text or "").strip()

            year = 0
            pub_date = article.find(".//PubDate")
            if pub_date is not None:
                yr_el = pub_date.find("Year")
                if yr_el is not None and yr_el.text:
                    try:
                        year = int(yr_el.text)
                    except ValueError:
                        pass

            journal_el = article.find(".//Journal/Title")
            venue = (journal_el.text or "").strip() if journal_el is not None else ""

            authors: List[str] = []
            for auth in article.findall(".//Author")[:6]:
                last = auth.findtext("LastName") or ""
                fore = auth.findtext("ForeName") or auth.findtext("Initials") or ""
                if last:
                    authors.append(f"{last} {fore}".strip())

            url = (
                f"https://doi.org/{doi}"
                if doi
                else f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
            )
            papers.append(
                CandidatePaper(
                    title=title,
                    url=url,
                    year=year,
                    source="pubmed",
                    pub_type=PubType.PEER_REVIEWED,
                    abstract=abstract,
                    authors=authors,
                    venue=venue,
                    doi=doi,
                )
            )

        time.sleep(_DELAY)

    return papers


def _inner_text(el: ET.Element | None) -> str:
    if el is None:
        return ""
    return (el.text or "") + "".join(
        (c.text or "") + (c.tail or "") for c in el
    )

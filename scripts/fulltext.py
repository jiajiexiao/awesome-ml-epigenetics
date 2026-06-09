"""OA full-text fetcher.

Resolves an open-access version of a paper for Stage-2 deep review.
Priority order:
  1. Europe PMC full-text XML (for PMC-indexed OA papers)
  2. arXiv HTML rendering (ar5iv)
  3. bioRxiv / medRxiv full-text HTML
  4. Unpaywall (any legal OA location for the DOI)

Paywalled papers with no free version: full_text_available stays False.
"""
from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from typing import Dict, Optional

import httpx

try:
    from bs4 import BeautifulSoup
    _BS4 = True
except ImportError:
    _BS4 = False

from .schemas import CandidatePaper

_DELAY = 0.5
_MAX_SECTION_CHARS = 6000  # per section before LLM truncation

_SECTION_NAMES = [
    "abstract", "introduction", "methods", "results", "discussion", "conclusion",
]


# ── Public entry point ────────────────────────────────────────────────────────

def fetch_fulltext(paper: CandidatePaper, email: str = "") -> bool:
    """
    Attempt to fetch OA full text for *paper*.
    Populates paper.extracted_sections, paper.full_text_available, paper.full_text_source.
    Returns True if at least one section was extracted.
    """
    if _is_arxiv(paper):
        if _fetch_arxiv(paper):
            return True

    if _is_biorxiv_medrxiv(paper):
        if _fetch_biorxiv_html(paper):
            return True

    if paper.doi:
        if _fetch_europepmc(paper):
            return True

    # Fallback: Unpaywall to find any legal OA copy
    if paper.doi and email:
        oa_url = _unpaywall_oa_url(paper.doi, email)
        if oa_url:
            if _fetch_generic_html(paper, oa_url, source_label="unpaywall"):
                return True

    paper.full_text_available = False
    return False


# ── Europe PMC ────────────────────────────────────────────────────────────────

def _fetch_europepmc(paper: CandidatePaper) -> bool:
    """Look up PMC ID via Europe PMC search, then fetch full-text XML."""
    doi_enc = paper.doi.replace("/", "%2F")
    url = (
        f"https://www.ebi.ac.uk/europepmc/webservices/rest/search"
        f"?query=DOI:{doi_enc}&resultType=idlist&format=json"
    )
    try:
        resp = httpx.get(url, timeout=15)
        resp.raise_for_status()
        items = (resp.json().get("resultList") or {}).get("result") or []
    except Exception:
        return False
    finally:
        time.sleep(_DELAY)

    for item in items:
        pmcid = item.get("pmcid")
        if pmcid:
            return _fetch_pmc_xml(paper, pmcid)
    return False


def _fetch_pmc_xml(paper: CandidatePaper, pmcid: str) -> bool:
    url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"
    try:
        resp = httpx.get(url, timeout=30)
        resp.raise_for_status()
        xml_content = resp.text
    except Exception:
        return False
    finally:
        time.sleep(_DELAY)

    sections = _parse_jats_xml(xml_content)
    if not sections:
        return False

    paper.extracted_sections = sections
    paper.full_text_available = True
    paper.full_text_source = f"europepmc::{pmcid}"
    return True


def _parse_jats_xml(xml_text: str) -> Dict[str, str]:
    """Parse JATS XML and extract named sections."""
    sections: Dict[str, str] = {}
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return sections

    # Abstract
    for abs_el in root.iter():
        if abs_el.tag.endswith("abstract"):
            text = " ".join(abs_el.itertext()).strip()
            if text and "abstract" not in sections:
                sections["abstract"] = text[:_MAX_SECTION_CHARS]

    # Body sections
    for sec in root.iter():
        if not sec.tag.endswith("sec"):
            continue
        title_el = None
        for child in sec:
            if child.tag.endswith("title"):
                title_el = child
                break
        sec_title = (" ".join(title_el.itertext()).strip().lower() if title_el is not None else "")
        text = " ".join(sec.itertext()).strip()
        for name in _SECTION_NAMES:
            if name in sec_title and name not in sections:
                sections[name] = text[:_MAX_SECTION_CHARS]

    return sections


# ── arXiv ─────────────────────────────────────────────────────────────────────

def _is_arxiv(paper: CandidatePaper) -> bool:
    return "arxiv.org" in paper.url.lower() or paper.source == "arxiv"


def _fetch_arxiv(paper: CandidatePaper) -> bool:
    arxiv_id = _extract_arxiv_id(paper.url)
    if not arxiv_id:
        return False
    # Try ar5iv (HTML rendering of arXiv papers)
    if _fetch_generic_html(paper, f"https://ar5iv.org/html/{arxiv_id}", f"arxiv::{arxiv_id}"):
        return True
    # Fallback: abstract page only
    return _fetch_generic_html(paper, f"https://arxiv.org/abs/{arxiv_id}", f"arxiv_abs::{arxiv_id}")


def _extract_arxiv_id(url: str) -> str:
    m = re.search(r"arxiv\.org/(?:abs|pdf|html)/([0-9]{4}\.[0-9]+)", url)
    return m.group(1) if m else ""


# ── bioRxiv / medRxiv ─────────────────────────────────────────────────────────

def _is_biorxiv_medrxiv(paper: CandidatePaper) -> bool:
    return paper.source in ("biorxiv", "medrxiv") or any(
        s in paper.url.lower() for s in ("biorxiv.org", "medrxiv.org")
    )


def _fetch_biorxiv_html(paper: CandidatePaper) -> bool:
    if not paper.doi:
        return False
    server = "medrxiv" if "medrxiv" in paper.url.lower() else "biorxiv"
    html_url = f"https://www.{server}.org/content/{paper.doi}.full"
    return _fetch_generic_html(paper, html_url, f"{server}::{paper.doi}")


# ── Unpaywall ─────────────────────────────────────────────────────────────────

def _unpaywall_oa_url(doi: str, email: str) -> Optional[str]:
    url = f"https://api.unpaywall.org/v2/{doi}?email={email}"
    try:
        resp = httpx.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return None
    finally:
        time.sleep(_DELAY)

    best = data.get("best_oa_location") or {}
    return best.get("url_for_landing_page") or best.get("url")


# ── Generic HTML fetcher ──────────────────────────────────────────────────────

def _fetch_generic_html(paper: CandidatePaper, url: str, source_label: str) -> bool:
    if not _BS4:
        return False
    try:
        resp = httpx.get(url, timeout=30, follow_redirects=True)
        if resp.status_code != 200:
            return False
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception:
        return False
    finally:
        time.sleep(_DELAY)

    sections = _extract_sections_from_html(soup)
    if not sections:
        return False

    paper.extracted_sections = sections
    paper.full_text_available = True
    paper.full_text_source = source_label
    return True


def _extract_sections_from_html(soup: "BeautifulSoup") -> Dict[str, str]:
    """Heuristically extract named sections from an HTML page."""
    sections: Dict[str, str] = {}

    # Meta description as abstract fallback
    meta = soup.find("meta", {"name": "description"})
    if meta and meta.get("content"):
        sections["abstract"] = str(meta["content"])[:_MAX_SECTION_CHARS]

    current_section: Optional[str] = None
    current_text: list[str] = []

    for el in soup.find_all(["h1", "h2", "h3", "h4", "p"]):
        tag = el.name
        if tag in ("h1", "h2", "h3", "h4"):
            # Save the previous section
            if current_section and current_text:
                text = " ".join(current_text).strip()
                if text and current_section not in sections:
                    sections[current_section] = text[:_MAX_SECTION_CHARS]
            current_text = []
            current_section = None
            heading = el.get_text(" ", strip=True).lower()
            for name in _SECTION_NAMES:
                if name in heading:
                    current_section = name
                    break
        elif tag == "p" and current_section:
            txt = el.get_text(" ", strip=True)
            if txt:
                current_text.append(txt)

    # Flush last section
    if current_section and current_text:
        text = " ".join(current_text).strip()
        if text and current_section not in sections:
            sections[current_section] = text[:_MAX_SECTION_CHARS]

    return sections

#!/usr/bin/env python3
"""update_list.py — paper discovery and README update orchestrator.

Usage (always run from project root):
  python -m scripts.update_list --category dna-methylation [--dry-run]
  python -m scripts.update_list --all-categories [--dry-run]
  python -m scripts.update_list --category liquid-biopsy --config config.yml
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Set, Tuple

import yaml
from rapidfuzz import fuzz

from scripts.schemas import CandidatePaper, Decision
from scripts.http_client import make_async_client
from scripts.review_agent import (
    _get_llm_client,
    rule_based_score,
    stage1_llm_screen,
    stage2_deep_review,
)
from scripts.fulltext import fetch_fulltext
from scripts import adapters

ROOT = Path(__file__).parent.parent
README_PATH = ROOT / "README.md"
CANDIDATES_OUT = ROOT / "candidates.json"


# ── Config ────────────────────────────────────────────────────────────────────

def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


# ── README parsing ────────────────────────────────────────────────────────────

def parse_existing_entries(readme_text: str) -> Tuple[Set[str], Set[str], List[str]]:
    """Return (existing_urls, existing_dois, existing_normalized_titles)."""
    urls: Set[str] = set()
    dois: Set[str] = set()
    titles: List[str] = []

    for line in readme_text.splitlines():
        for m in re.finditer(r"\[([^\]]+)\]\((https?://[^\)]+)\)", line):
            raw_title, url = m.group(1), m.group(2)
            url_norm = url.strip().rstrip("/").lower().split("#")[0].split("?")[0]
            urls.add(url_norm)
            doi_m = re.match(r"https://doi\.org/(.+)", url.strip(), re.I)
            if doi_m:
                dois.add(doi_m.group(1).lower().rstrip("."))
            t = re.sub(r"[^a-z0-9 ]", " ", raw_title.lower())
            t = re.sub(r"\s+", " ", t).strip()
            if len(t) > 10:
                titles.append(t)

    # Also catch bare DOIs in text
    for m in re.finditer(r"10\.\d{4,}/\S+", readme_text):
        dois.add(m.group(0).lower().rstrip("."))

    return urls, dois, titles


def inject_entries(readme_text: str, marker: str, new_entries: List[str]) -> str:
    """Insert new entries into the bot block, keeping it sorted (newest year first)."""
    if not new_entries:
        return readme_text
    return _rewrite_block(readme_text, marker, new_entries)


# Publication year as it appears after the link: ``(YYYY) -``. Anchoring on the
# ``) -`` that separates the year from the description (rather than on the link's
# closing paren) keeps it robust to URLs that themselves contain parentheses.
_ENTRY_YEAR_RE = re.compile(r"\((\d{4})\)\s*[-–]")
_ENTRY_TITLE_RE = re.compile(r"-\s*\[([^\]]+)\]")
_MARKER_RE = re.compile(r"<!-- AUTO-PAPERS:([A-Z0-9_]+) START -->")


def _entry_year(entry: str) -> int:
    m = _ENTRY_YEAR_RE.search(entry)
    return int(m.group(1)) if m else 0


def _entry_title(entry: str) -> str:
    m = _ENTRY_TITLE_RE.search(entry)
    return m.group(1).strip().lower() if m else ""


# Datasets have no publication year; order them alphabetically by name instead.
_DATASETS_MARKER = "DATASETS"

# Section/subsection headings (## or ###). A marker's block spans every entry
# from its START tag up to the next heading, so manual and bot entries are sorted
# together into one newest-first list per section.
_HEADING_RE = re.compile(r"^#{2,3} .+$", re.MULTILINE)


def _entry_sort_key(entry: str) -> Tuple[int, str]:
    # Newest year first; ties broken alphabetically by title for determinism.
    # Yearless entries (year 0) sort to the bottom.
    return (-_entry_year(entry), _entry_title(entry))


def _sort_entries(entries: List[str], marker: str) -> None:
    """Sort *entries* in place: alphabetically for datasets, else newest year first."""
    if marker == _DATASETS_MARKER:
        entries.sort(key=_entry_title)
    else:
        entries.sort(key=_entry_sort_key)


def _section_end(readme_text: str, after_idx: int) -> int:
    """Index of the next ##/### heading after *after_idx* (or end of text)."""
    next_heading = _HEADING_RE.search(readme_text, after_idx)
    return next_heading.start() if next_heading else len(readme_text)


def _rewrite_block(readme_text: str, marker: str, extra_entries: List[str]) -> str:
    """Merge *extra_entries* into the marker's section and re-sort the whole section.

    The block spans from the START tag to the next heading, so every entry in the
    section (manual + bot) is sorted into one list and the END tag is parked at the
    bottom of the section.
    """
    start_tag = f"<!-- AUTO-PAPERS:{marker} START -->"
    end_tag = f"<!-- AUTO-PAPERS:{marker} END -->"
    start_idx = readme_text.find(start_tag)
    if start_idx == -1:
        # Marker missing — fall back to legacy append behavior.
        if extra_entries:
            insertion = "\n".join(extra_entries) + "\n"
            return readme_text.replace(end_tag, insertion + end_tag)
        return readme_text

    block_start = start_idx + len(start_tag)
    section_end = _section_end(readme_text, block_start)
    region = readme_text[block_start:section_end].replace(end_tag, "")
    existing = [ln.rstrip() for ln in region.splitlines() if ln.strip().startswith("- ")]
    merged = existing + list(extra_entries)
    _sort_entries(merged, marker)

    body = ("\n".join(merged) + "\n") if merged else ""
    new_region = "\n" + body + end_tag + "\n\n"
    return readme_text[:block_start] + new_region + readme_text[section_end:]


def sort_all_blocks(readme_text: str) -> str:
    """Re-sort every section that has an AUTO-PAPERS marker (newest first)."""
    for marker in _MARKER_RE.findall(readme_text):
        readme_text = _rewrite_block(readme_text, marker, [])
    return readme_text




def render_entry(paper: CandidatePaper) -> str:
    """Render a single markdown list entry in the contributing format."""
    desc = _best_description(paper)
    return f"- [{paper.title}]({paper.url}) ({paper.year}) - {desc}."


def _best_description(paper: CandidatePaper) -> str:
    for candidate in [paper.markdown_entry, paper.deep_review_rationale, paper.reviewer_rationale]:
        if candidate and len(candidate.strip()) > 10:
            first = candidate.strip().split(".")[0].strip().rstrip(".")
            if len(first) > 10:
                return first
    return f"{paper.pub_type.value.capitalize()} paper"


# ── Discovery ─────────────────────────────────────────────────────────────────

def discover_candidates(cfg: dict, cat_cfg: dict, from_date: str, to_date: str) -> List[CandidatePaper]:
    """Run all enabled source adapters concurrently over one pooled client."""
    return asyncio.run(_discover_candidates_async(cfg, cat_cfg, from_date, to_date))


async def _discover_candidates_async(
    cfg: dict, cat_cfg: dict, from_date: str, to_date: str
) -> List[CandidatePaper]:
    email = cfg["discovery"]["email"]
    max_raw = cfg["discovery"]["max_raw_results_per_term"]
    terms = cat_cfg["search_terms"]
    srcs = cfg.get("sources", {})

    async with make_async_client() as client:
        tasks = []
        labels: List[str] = []
        if srcs.get("openalex", True):
            tasks.append(adapters.openalex_search(terms, from_date, to_date, email, max_raw, client=client))
            labels.append("openalex")
        if srcs.get("europepmc", True):
            tasks.append(adapters.europepmc_search(terms, from_date, to_date, email, max_raw, client=client))
            labels.append("europepmc")
        if srcs.get("pubmed", True):
            tasks.append(adapters.pubmed_search(terms, from_date, to_date, email, max_raw, client=client))
            labels.append("pubmed")
        if srcs.get("arxiv", True):
            tasks.append(adapters.arxiv_search(terms, from_date, to_date, email, max_raw, client=client))
            labels.append("arxiv")
        if srcs.get("biorxiv", True):
            tasks.append(adapters.biorxiv_search(terms, from_date, to_date, email, max_raw, client=client))
            labels.append("biorxiv")

        results = await asyncio.gather(*tasks, return_exceptions=True)

    all_papers: List[CandidatePaper] = []
    for label, result in zip(labels, results):
        if isinstance(result, BaseException):
            print(f"[discover] {label} failed: {result}")
            continue
        all_papers += result

    return all_papers


def dedup_candidates(
    papers: List[CandidatePaper],
    existing_urls: Set[str],
    existing_dois: Set[str],
    existing_titles: List[str],
) -> List[CandidatePaper]:
    seen_urls = set(existing_urls)
    seen_dois = set(existing_dois)
    seen_titles = list(existing_titles)
    unique: List[CandidatePaper] = []

    for p in papers:
        if p.normalized_url in seen_urls:
            continue
        if p.normalized_doi and p.normalized_doi in seen_dois:
            continue
        if any(fuzz.ratio(p.normalized_title, t) > 88 for t in seen_titles):
            continue
        seen_urls.add(p.normalized_url)
        if p.normalized_doi:
            seen_dois.add(p.normalized_doi)
        seen_titles.append(p.normalized_title)
        unique.append(p)

    return unique


# ── Category pipeline ─────────────────────────────────────────────────────────

def process_category(
    cat_name: str,
    cat_cfg: dict,
    cfg: dict,
    readme_text: str,
    dry_run: bool = False,
) -> Tuple[str, List[CandidatePaper], List[CandidatePaper]]:
    """
    Run the full pipeline for one category.
    Returns (updated_readme_text, accepted_papers, needs_review_papers).
    """
    days = cfg["discovery"]["date_window_days"]
    from_date = (date.today() - timedelta(days=days)).isoformat()
    to_date = date.today().isoformat()

    marker = cat_cfg["readme_marker"]
    keywords = cat_cfg["keywords"]
    threshold = cat_cfg.get("relevance_threshold", cfg["quality"]["min_relevance_score"])
    max_new = cat_cfg.get("max_new_per_run", 5)

    llm_cfg = cfg.get("llm", {})
    model = llm_cfg.get("model", "gpt-4o-mini")
    max_stage1 = llm_cfg.get("max_llm_candidates_per_run", 30)
    max_deep = llm_cfg.get("max_deep_reviews_per_day", 6)
    max_calls = llm_cfg.get("max_calls_per_paper", 4)
    deep_review_enabled = llm_cfg.get("deep_review_enabled", True)
    max_abstract_chars = llm_cfg.get("max_abstract_tokens", 800) * 4
    max_section_chars = llm_cfg.get("max_section_tokens", 1500) * 4
    email = cfg["discovery"]["email"]

    client = _get_llm_client()

    # Parse existing entries for dedup
    existing_urls, existing_dois, existing_titles = parse_existing_entries(readme_text)

    print(f"[{cat_name}] Discovering ({from_date} → {to_date})...")
    raw = discover_candidates(cfg, cat_cfg, from_date, to_date)
    print(f"[{cat_name}] {len(raw)} raw from APIs.")

    unique = dedup_candidates(raw, existing_urls, existing_dois, existing_titles)
    print(f"[{cat_name}] {len(unique)} after dedup.")

    # Rule-based scoring
    scored: List[Tuple[float, CandidatePaper]] = []
    for p in unique:
        score, vote = rule_based_score(p, keywords, threshold)
        p.relevance_score = score
        p.rule_based_vote = vote
        if vote != Decision.EXCLUDE:
            scored.append((score, p))

    scored.sort(key=lambda x: -x[0])
    top = scored[:max_stage1]
    print(f"[{cat_name}] {len(top)} after rule-based screen (top-{max_stage1}).")

    # Stage 1: LLM abstract screen
    stage1_passed: List[CandidatePaper] = []
    for _, p in top:
        if client:
            decision, rationale = stage1_llm_screen(p, cat_name, model, client, max_abstract_chars)
            p.llm_vote = decision
            p.reviewer_rationale = rationale
        else:
            p.llm_vote = p.rule_based_vote  # degrade to rule-based only

        rb_ok = p.rule_based_vote == Decision.INCLUDE
        llm_ok = p.llm_vote == Decision.INCLUDE
        if rb_ok and llm_ok:
            p.abstract_screen_decision = Decision.INCLUDE
            stage1_passed.append(p)
        else:
            p.abstract_screen_decision = (
                Decision.NEEDS_REVIEW
                if p.llm_vote == Decision.NEEDS_REVIEW or p.rule_based_vote == Decision.NEEDS_REVIEW
                else Decision.EXCLUDE
            )

    print(f"[{cat_name}] {len(stage1_passed)} passed Stage-1.")

    # Stage 2: full-text deep review
    accepted: List[CandidatePaper] = []
    needs_review: List[CandidatePaper] = []
    deep_count = 0

    for p in stage1_passed[: max_new * 2]:
        if deep_count >= max_deep:
            p.needs_human_review = True
            needs_review.append(p)
            continue

        if not deep_review_enabled or not client:
            # No deep review — include on Stage-1 basis
            p.deep_review_decision = Decision.INCLUDE
            p.markdown_entry = _best_description(p)
            accepted.append(p)
            continue

        # Attempt full text (tries OA version discovery internally)
        got_ft = fetch_fulltext(p, email)
        if not got_ft:
            # No free full text found — leave for human
            p.needs_human_review = True
            needs_review.append(p)
            continue

        decision, rationale, suggested = stage2_deep_review(
            p, cat_name, model, client, max_calls, max_section_chars
        )
        deep_count += 1
        p.deep_review_decision = decision
        p.deep_review_rationale = rationale
        if suggested:
            p.markdown_entry = suggested

        if decision == Decision.INCLUDE:
            accepted.append(p)
        elif decision == Decision.NEEDS_REVIEW:
            p.needs_human_review = True
            needs_review.append(p)
        # else: excluded

    accepted = accepted[:max_new]
    print(f"[{cat_name}] {len(accepted)} accepted, {len(needs_review)} need human review.")

    # Inject into README sub-block
    updated_readme = readme_text
    if accepted and not dry_run:
        new_entries = [render_entry(p) for p in accepted]
        updated_readme = inject_entries(readme_text, marker, new_entries)
    elif accepted and dry_run:
        print(f"[{cat_name}] DRY-RUN — would add:")
        for p in accepted:
            print(f"  {render_entry(p)}")

    return updated_readme, accepted, needs_review


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Update awesome-ml-epigenetics list")
    parser.add_argument("--config", default="config.yml")
    parser.add_argument("--category", help="Category slug (e.g. dna-methylation)")
    parser.add_argument("--all-categories", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--sort",
        action="store_true",
        help="Re-sort every AUTO-PAPERS block by year (newest first) and exit.",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    readme_text = README_PATH.read_text(encoding="utf-8")
    all_categories: Dict[str, dict] = cfg.get("categories", {})

    if args.sort:
        sorted_text = sort_all_blocks(readme_text)
        if sorted_text != readme_text:
            README_PATH.write_text(sorted_text, encoding="utf-8")
            print("README.md re-sorted (newest first; whole section per category).")
        else:
            print("README.md already sorted — no change.")
        sys.exit(0)

    if args.all_categories:
        cats = list(all_categories.items())
    elif args.category:
        cats = [
            (name, ccfg)
            for name, ccfg in all_categories.items()
            if ccfg.get("slug") == args.category or name == args.category
        ]
        if not cats:
            print(f"Error: category '{args.category}' not in config.", file=sys.stderr)
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)

    all_candidates: List[CandidatePaper] = []

    for cat_name, cat_cfg in cats:
        readme_text, accepted, needs_review = process_category(
            cat_name, cat_cfg, cfg, readme_text, dry_run=args.dry_run
        )
        all_candidates.extend(accepted)
        all_candidates.extend(needs_review)

    # Write updated README (only if not dry-run and something was accepted)
    accepted_count = sum(1 for p in all_candidates if not p.needs_human_review)
    if not args.dry_run and accepted_count > 0:
        README_PATH.write_text(readme_text, encoding="utf-8")
        print("README.md updated.")

    # Always write candidates.json as a workflow evidence artifact (not committed)
    CANDIDATES_OUT.write_text(
        json.dumps([p.to_dict() for p in all_candidates], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"candidates.json written ({len(all_candidates)} total).")

    # Exit codes consumed by the propose-update workflow:
    #   0 = accepted papers exist → create PR
    #   2 = only needs-review items → no PR, but notify
    #   1 = no candidates at all → no-op, no PR
    if accepted_count > 0:
        sys.exit(0)
    elif all_candidates:
        sys.exit(2)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()

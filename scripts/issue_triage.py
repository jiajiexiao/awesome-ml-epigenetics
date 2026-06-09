#!/usr/bin/env python3
"""issue_triage.py — quick triage for paper suggestions from GitHub issues.

Supports a lazy workflow:
- User pastes multiple URLs and/or titles in one issue.
- Bot tries to resolve metadata automatically.
- Bot validates URL reachability and duplicate risk.
- Bot posts ready-to-copy README entries plus guidance.

If an issue comment contains '/triage', the bot also parses additional lines in
that comment as extra URLs/titles.
"""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import httpx
from rapidfuzz import fuzz

ROOT = Path(__file__).parent.parent

_CATEGORY_TO_MARKER = {
    "DNA Methylation": "DNA_METHYLATION",
    "Histone Modifications": "HISTONE_MODIFICATIONS",
    "Chromatin Accessibility": "CHROMATIN_ACCESSIBILITY",
    "Multi-omics Integration": "MULTI_OMICS",
    "Liquid Biopsy": "LIQUID_BIOPSY",
    "Novel Epigenetic Assays": "NOVEL_ASSAYS",
    "Datasets": "DATASETS",
}

_FIELD_RE = re.compile(r"### (.+?)\n\n(.*?)(?=\n### |\Z)", re.DOTALL)
_URL_RE = re.compile(r"https?://\S+")
_DOI_RE = re.compile(r"10\.\d{4,9}/\S+")


@dataclass
class Suggestion:
    raw: str
    url: str = ""
    title: str = ""
    year: int = 0
    source: str = ""
    status: str = "pending"  # ok | warning | fail
    note: str = ""
    duplicate: bool = False


def _parse_issue_fields(body: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for m in _FIELD_RE.finditer(body):
        key = m.group(1).strip()
        val = m.group(2).strip()
        fields[key] = "" if val == "_No response_" else val
    return fields


def _extract_lines(text: str) -> List[str]:
    lines: List[str] = []
    for line in text.splitlines():
        item = line.strip().lstrip("-*0123456789. ").strip()
        if not item or item.startswith("#"):
            continue
        lines.append(item)
    return lines


def _normalise_url(text: str) -> str:
    m = _URL_RE.search(text)
    if m:
        return m.group(0).rstrip(").,;")
    d = _DOI_RE.search(text)
    if d:
        return f"https://doi.org/{d.group(0).rstrip(').,;')}"
    return ""


def _resolve_from_doi(url: str, email: str) -> tuple[str, int]:
    doi = re.sub(r"^https?://doi\.org/", "", url, flags=re.I)
    api = f"https://api.crossref.org/works/{doi}"
    headers = {"User-Agent": f"awesome-ml-epigenetics ({email})"}
    r = httpx.get(api, timeout=15, headers=headers)
    if r.status_code >= 400:
        return "", 0
    msg = r.json().get("message", {})
    title = (msg.get("title") or [""])[0]
    year = 0
    for k in ("published-print", "published-online", "issued"):
        parts = ((msg.get(k) or {}).get("date-parts") or [[0]])[0]
        if parts and parts[0]:
            year = int(parts[0])
            break
    return title.strip(), year


def _resolve_from_title(title: str, email: str) -> tuple[str, str, int, float]:
    headers = {"User-Agent": f"awesome-ml-epigenetics ({email})"}
    q = httpx.QueryParams({
        "search": title,
        "filter": "is_paratext:false",
        "per-page": 5,
    })
    r = httpx.get(f"https://api.openalex.org/works?{q}", timeout=15, headers=headers)
    if r.status_code >= 400:
        return "", "", 0, 0.0
    results = r.json().get("results", [])
    best = None
    best_score = 0.0
    for w in results:
        cand = (w.get("display_name") or "").strip()
        score = fuzz.ratio(title.lower(), cand.lower())
        if score > best_score:
            best_score = score
            best = w
    if not best:
        return "", "", 0, 0.0
    url = best.get("doi") or best.get("primary_location", {}).get("landing_page_url") or ""
    year = int(best.get("publication_year") or 0)
    return (best.get("display_name") or "").strip(), url, year, best_score


def _is_url_item(text: str) -> bool:
    return bool(_URL_RE.search(text) or _DOI_RE.search(text))


def main() -> None:
    issue_body = os.environ.get("ISSUE_BODY", "")
    issue_comment = os.environ.get("ISSUE_COMMENT", "")
    issue_url = os.environ.get("ISSUE_URL", "")
    if not issue_body:
        print("ISSUE_BODY env var not set", file=sys.stderr)
        sys.exit(1)

    from scripts.review_agent import check_link_reachable, check_no_duplicate
    from scripts.schemas import CandidatePaper, PubType
    from scripts.update_list import parse_existing_entries

    cfg = (ROOT / "config.yml").read_text(encoding="utf-8")
    email_m = re.search(r'email:\s*"([^"]+)"', cfg)
    email = email_m.group(1) if email_m else "auto-update@users.noreply.github.com"

    fields = _parse_issue_fields(issue_body)
    items_raw = fields.get("URLs and/or Titles", "")
    category = fields.get("Category", "").strip()
    notes = fields.get("Notes (optional)", "").strip()
    if category == "Unsure":
        category = ""

    lines = _extract_lines(items_raw)

    # Optional follow-up via issue comments: include lines from comments that ask /triage
    if issue_comment and "/triage" in issue_comment:
        extra = issue_comment.replace("/triage", "")
        lines.extend(_extract_lines(extra))

    seen = set()
    uniq_lines: List[str] = []
    for x in lines:
        k = x.lower()
        if k not in seen:
            uniq_lines.append(x)
            seen.add(k)

    suggestions: List[Suggestion] = []
    for item in uniq_lines[:12]:  # keep runtime bounded
        s = Suggestion(raw=item)
        try:
            if _is_url_item(item):
                s.url = _normalise_url(item)
                if "doi.org/" in s.url.lower():
                    t, y = _resolve_from_doi(s.url, email)
                    s.title, s.year = t, y
                    s.source = "crossref"
                else:
                    # Non-DOI URL: best-effort title from URL slug
                    s.title = re.sub(r"[-_]+", " ", s.url.rsplit("/", 1)[-1]).strip()[:160]
                    s.source = "url"
            else:
                s.title = item
                t, u, y, score = _resolve_from_title(item, email)
                if score >= 80 and u:
                    s.title, s.url, s.year = t, u, y
                    s.source = f"openalex:{int(score)}"
                else:
                    s.status = "warning"
                    s.note = "Could not confidently resolve this title; please open a focused issue with a DOI/URL."

            if s.url:
                ok, msg = check_link_reachable(s.url)
                if not ok:
                    s.status = "fail"
                    s.note = msg
                elif s.status == "pending":
                    s.status = "ok"

            if not s.url:
                if s.status == "pending":
                    s.status = "warning"
                    s.note = "No resolvable URL found."
        except Exception as e:
            s.status = "fail"
            s.note = f"Resolution error: {e}"
        suggestions.append(s)

    readme_text = (ROOT / "README.md").read_text(encoding="utf-8")
    existing_urls, existing_dois, existing_titles = parse_existing_entries(readme_text)

    for s in suggestions:
        if s.url and s.title:
            paper = CandidatePaper(
                title=s.title,
                url=s.url,
                year=s.year,
                source="issue",
                pub_type=PubType.UNKNOWN,
            )
            ok, msg = check_no_duplicate(paper, existing_urls, existing_dois, existing_titles)
            if not ok:
                s.duplicate = True
                if s.status == "ok":
                    s.status = "warning"
                s.note = f"Possible duplicate: {msg}"

    ready = [s for s in suggestions if s.status == "ok" and s.url and s.title]
    unresolved = [s for s in suggestions if s.status != "ok"]

    status_ok = len(ready) > 0 and len(unresolved) == 0
    status = "✅ Ready candidates" if status_ok else "⚠️ Partial results"

    out: List[str] = [
        f"## {status} — Paper Suggestion Validation",
        "",
        "| Input | Result | Notes |",
        "|---|---|---|",
    ]

    for s in suggestions:
        icon = "✅" if s.status == "ok" else ("⚠️" if s.status == "warning" else "❌")
        resolved = s.title if s.title else "(unresolved)"
        if s.url:
            resolved = f"[{resolved}]({s.url})"
        note = s.note or (f"resolved via {s.source}" if s.source else "")
        out.append(f"| `{s.raw[:80]}` | {icon} {resolved} | {note} |")

    if ready:
        out += [
            "",
            "### Suggested entries for `README.md`",
            "",
            "```markdown",
        ]
        for s in ready:
            desc = "_Add one sentence naming the exact model and task._"
            if notes:
                desc = notes.splitlines()[0].strip().rstrip(".")
            year_text = str(s.year) if s.year else "2026"
            out.append(f"- [{s.title}]({s.url}) ({year_text}) - {desc}.")
        out += ["```"]

    marker = _CATEGORY_TO_MARKER.get(category, "") if category else ""
    out += [
        "",
        "### Next step",
        "",
    ]
    if marker:
        out.append(
            f"If this looks right, open a PR and place entries above `<!-- AUTO-PAPERS:{marker} START -->` in `README.md`."
        )
    else:
        out.append("If category is unclear, open a focused follow-up issue per paper (or edit this issue with a category).")

    if unresolved:
        out += [
            "",
            "Some items could not be resolved confidently. Please open another focused issue for those specific items with a DOI/URL for faster processing.",
            "You can also comment on this issue with `/triage` and additional lines to retry resolution.",
        ]

    if issue_url:
        out += ["", f"_Issue: {issue_url}_"]

    comment = "\n".join(out)
    comment_file = os.environ.get("COMMENT_FILE")
    if comment_file:
        Path(comment_file).write_text(comment, encoding="utf-8")
    else:
        print(comment)

    # Keep workflow green even for partial results so comment is posted cleanly.
    sys.exit(0)


if __name__ == "__main__":
    main()

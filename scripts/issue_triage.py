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
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import httpx
import yaml
from rapidfuzz import fuzz
from bs4 import BeautifulSoup

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
_MARKER_TO_DISPLAY = {v: k for k, v in _CATEGORY_TO_MARKER.items()}

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
    marker: str = ""
    category_display: str = ""
    description: str = ""
    abstract: str = ""
    hint_category: str = ""


def _set_output(key: str, value: str) -> None:
    """Write a key=value pair to GITHUB_OUTPUT for the workflow to consume."""
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a", encoding="utf-8") as f:
            f.write(f"{key}={value}\n")


def _sanitize_title(title: str) -> str:
    """Make a title safe to embed inside a markdown link text."""
    t = title.replace("\n", " ").replace("[", "(").replace("]", ")").replace("|", "/")
    t = re.sub(r"\s+", " ", t).strip()
    return t[:240]


def _clean_desc(desc: str) -> str:
    d = re.sub(r"\s+", " ", desc.replace("`", " ").replace("|", "/")).strip()
    return d.rstrip(".")


def _invert_abstract(inv: dict | None) -> str:
    """Reconstruct plain text from an OpenAlex abstract_inverted_index."""
    if not inv:
        return ""
    try:
        positions: list[tuple[int, str]] = []
        for word, idxs in inv.items():
            for i in idxs:
                positions.append((i, word))
        positions.sort()
        return " ".join(w for _, w in positions)
    except Exception:
        return ""


def _abstract_from_openalex_doi(url: str, email: str) -> str:
    """Fetch an abstract for a DOI via OpenAlex (Crossref abstracts are unreliable)."""
    doi = re.sub(r"^https?://doi\.org/", "", url, flags=re.I).strip()
    if not doi:
        return ""
    headers = {"User-Agent": f"awesome-ml-epigenetics ({email})"}
    try:
        r = httpx.get(f"https://api.openalex.org/works/doi:{doi}", timeout=15, headers=headers)
        if r.status_code >= 400:
            return ""
        return _invert_abstract(r.json().get("abstract_inverted_index"))
    except Exception:
        return ""


_ARXIV_ID_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/([\w.\-/]+?)(?:v\d+)?(?:\.pdf)?/?$", re.I)


def _resolve_from_arxiv(url: str) -> tuple[str, int, str]:
    """Resolve title, year, and abstract for an arxiv.org/abs (or /pdf) URL."""
    m = _ARXIV_ID_RE.search(url)
    if not m:
        return "", 0, ""
    arxiv_id = m.group(1)
    try:
        r = httpx.get(
            "https://export.arxiv.org/api/query",
            params={"id_list": arxiv_id, "max_results": 1},
            timeout=20,
        )
        if r.status_code >= 400:
            return "", 0, ""
        ns = "http://www.w3.org/2005/Atom"
        entry = ET.fromstring(r.content).find(f"{{{ns}}}entry")
        if entry is None:
            return "", 0, ""
        title = " ".join((entry.findtext(f"{{{ns}}}title") or "").split())
        abstract = " ".join((entry.findtext(f"{{{ns}}}summary") or "").split())
        published = (entry.findtext(f"{{{ns}}}published") or "").strip()
        year = int(published[:4]) if published[:4].isdigit() else 0
        return title, year, abstract
    except Exception:
        return "", 0, ""


def classify_category(text: str, cfg: dict, fallback_display: str = "") -> tuple[str, str, int]:
    """Pick the best-matching category by keyword overlap.

    Returns (marker, display_name, score). Falls back to the user-provided
    category when no keyword matches.
    """
    text_l = text.lower()
    best_cc = None
    best_score = 0
    for _key, cc in (cfg.get("categories") or {}).items():
        score = sum(1 for kw in cc.get("keywords", []) if kw.lower() in text_l)
        if score > best_score:
            best_score = score
            best_cc = cc
    if best_cc and best_score > 0:
        marker = best_cc["readme_marker"]
        return marker, _MARKER_TO_DISPLAY.get(marker, marker), best_score
    if fallback_display:
        marker = _CATEGORY_TO_MARKER.get(fallback_display, "")
        return marker, fallback_display, 0
    return "", "Unsure", 0


def _suggest_description(title: str, abstract: str, client, model: str, context: str = "") -> str:
    """Generate a one-sentence description grounded in the paper's abstract.

    The description is built ONLY from facts in the abstract. When no abstract is
    available we fall back to a task-only sentence and explicitly forbid naming
    any architecture, so the bot never fabricates a model (e.g. inventing a VAE).
    """
    if not client:
        return ""
    abstract = (abstract or "").strip()
    ctx = f"\nAuthor notes/hints: {context.strip()}" if context.strip() else ""
    if abstract:
        source = f"Abstract: {abstract[:1800]}"
        rules = (
            "Use ONLY facts stated in the abstract. Name the specific model "
            "architecture (e.g. CNN, transformer, XGBoost, VAE) if and only if the "
            "abstract explicitly names it; otherwise describe the task without a "
            "model name. Never invent or guess a model, dataset, or result."
        )
    else:
        source = "(No abstract available — you only have the title.)"
        rules = (
            "Describe only the general task implied by the title. Do NOT name any "
            "specific model architecture, dataset, or metric, since the abstract is "
            "unavailable. Do not guess or fabricate details."
        )
    try:
        from scripts.review_agent import _llm_call
        raw = _llm_call(
            client, model,
            [
                {"role": "system", "content": (
                    "You write accurate one-sentence entries for an awesome-list of "
                    "ML in epigenetics. Be factual and specific, but NEVER fabricate "
                    "methods, architectures, datasets, or results."
                )},
                {"role": "user", "content": (
                    f"Title: {title}\n{source}{ctx}\n\n{rules}\n"
                    "Write ONE concise factual sentence (<=30 words). No trailing period."
                )},
            ],
            max_tokens=90,
        )
        return _clean_desc(raw or "")
    except Exception:
        return ""


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


def _norm_token(text: str) -> str:
    """Lowercase and collapse non-alphanumerics to single spaces for matching."""
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _category_hint_index(cfg: dict) -> dict:
    """Map normalized hint text (display/slug/marker/config key) -> display name."""
    idx: dict[str, str] = {}
    for display, marker in _CATEGORY_TO_MARKER.items():
        idx[_norm_token(display)] = display
        idx[_norm_token(marker)] = display
    for key, cc in (cfg.get("categories") or {}).items():
        display = _MARKER_TO_DISPLAY.get(cc.get("readme_marker", ""), "")
        if not display:
            continue
        idx[_norm_token(key)] = display
        if cc.get("slug"):
            idx[_norm_token(cc["slug"])] = display
    return idx


def _split_category_hint(line: str, hint_index: dict) -> tuple[str, str]:
    """Split a `category: url/title` hint line into (item, display_category).

    Only treats the text before the first colon as a category when it matches a
    known category; otherwise the line is returned unchanged (so URLs and titles
    that contain colons are left intact).
    """
    if ":" not in line:
        return line, ""
    prefix, rest = line.split(":", 1)
    display = hint_index.get(_norm_token(prefix))
    if display and rest.strip():
        return rest.strip(), display
    return line, ""


def _resolve_from_doi(url: str, email: str) -> tuple[str, int, str]:
    doi = re.sub(r"^https?://doi\.org/", "", url, flags=re.I)
    api = f"https://api.crossref.org/works/{doi}"
    headers = {"User-Agent": f"awesome-ml-epigenetics ({email})"}
    r = httpx.get(api, timeout=15, headers=headers)
    if r.status_code >= 400:
        return "", 0, ""
    msg = r.json().get("message", {})
    title = (msg.get("title") or [""])[0]
    year = 0
    for k in ("published-print", "published-online", "issued"):
        parts = ((msg.get(k) or {}).get("date-parts") or [[0]])[0]
        if parts and parts[0]:
            year = int(parts[0])
            break
    return title.strip(), year, _abstract_from_openalex_doi(url, email)


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
    abstract = _invert_abstract(best.get("abstract_inverted_index"))
    return (best.get("display_name") or "").strip(), url, year, best_score, abstract


def _resolve_from_openreview(url: str) -> tuple[str, int, str]:
    """Resolve OpenReview metadata (title, year, abstract).

    Prefers the OpenReview API (which exposes the real abstract), falling back to
    scraping the forum HTML page for title/year only.
    """
    m = re.search(r"[?&]id=([\w-]+)", url)
    forum_id = m.group(1) if m else ""

    if forum_id:
        for api in ("https://api2.openreview.net/notes", "https://api.openreview.net/notes"):
            try:
                r = httpx.get(api, params={"forum": forum_id}, timeout=15)
                if r.status_code >= 400:
                    continue
                notes = r.json().get("notes", [])
                if not notes:
                    continue
                note = next((n for n in notes if n.get("id") == forum_id), notes[0])
                content = note.get("content", {}) or {}

                def _val(key: str) -> str:
                    v = content.get(key)
                    if isinstance(v, dict):
                        v = v.get("value", "")
                    return str(v or "").strip()

                title = _val("title")
                abstract = _val("abstract")
                year = 0
                ym = re.search(r"\b(20\d{2})\b", f"{_val('year')} {_val('venue')}")
                if ym:
                    year = int(ym.group(1))
                if not year and note.get("cdate"):
                    try:
                        from datetime import datetime, timezone
                        year = datetime.fromtimestamp(note["cdate"] / 1000, timezone.utc).year
                    except Exception:
                        pass
                if title:
                    return title, year, abstract
            except Exception:
                continue

    # ── Fallback: scrape the forum HTML page (title/year only) ──
    try:
        r = httpx.get(url, timeout=15)
        if r.status_code >= 400:
            return "", 0, ""
        soup = BeautifulSoup(r.text, "html.parser")
        title = ""
        og = soup.find("meta", attrs={"property": "og:title"})
        if og and og.get("content"):
            title = og.get("content", "").strip()
        if not title and soup.title and soup.title.string:
            title = soup.title.string.strip()
        title = re.sub(r"\s*\|\s*OpenReview\s*$", "", title).strip()
        text = soup.get_text(" ", strip=True)
        year = 0
        ym = re.search(r"\b(20\d{2})\b", text)
        if ym:
            year = int(ym.group(1))
        return title, year, ""
    except Exception:
        return "", 0, ""


def _is_url_item(text: str) -> bool:
    return bool(_URL_RE.search(text) or _DOI_RE.search(text))


def main() -> None:
    issue_body = os.environ.get("ISSUE_BODY", "")
    issue_comment = os.environ.get("ISSUE_COMMENT", "")
    issue_url = os.environ.get("ISSUE_URL", "")
    issue_number = os.environ.get("ISSUE_NUMBER", "").strip()
    if not issue_body:
        print("ISSUE_BODY env var not set", file=sys.stderr)
        sys.exit(1)

    from scripts.review_agent import (
        _get_llm_client,
        check_link_reachable,
        check_no_duplicate,
    )
    from scripts.schemas import CandidatePaper, PubType
    from scripts.update_list import inject_entries, parse_existing_entries

    cfg = yaml.safe_load((ROOT / "config.yml").read_text(encoding="utf-8")) or {}
    email = (cfg.get("discovery") or {}).get("email", "auto-update@users.noreply.github.com")
    model = (cfg.get("llm") or {}).get("model", "gpt-4o-mini")
    client = _get_llm_client()

    fields = _parse_issue_fields(issue_body)
    items_raw = fields.get("URLs and/or Titles", "")
    user_category = fields.get("Category", "").strip()
    notes = fields.get("Notes (optional)", "").strip()
    if user_category == "Unsure":
        user_category = ""

    lines = _extract_lines(items_raw)

    # Each candidate carries an optional category hint (only comment lines may set
    # one via the `category: url` syntax the bot advertises).
    hint_index = _category_hint_index(cfg)
    parsed: List[tuple[str, str]] = [(ln, "") for ln in lines]

    # Optional follow-up via issue comments: include lines from comments that ask /triage
    if issue_comment and "/triage" in issue_comment:
        extra = issue_comment.replace("/triage", "")
        for ln in _extract_lines(extra):
            item, hint = _split_category_hint(ln, hint_index)
            parsed.append((item, hint))

    # Dedup within this run by resolved URL (falling back to the raw text), so the
    # same paper from the issue body and a /triage comment isn't listed twice. A
    # later hint is merged onto an earlier hint-less duplicate.
    by_key: dict[str, list[str]] = {}
    order: List[str] = []
    for item, hint in parsed:
        url = _normalise_url(item)
        key = url.lower() if url else item.lower()
        if key not in by_key:
            by_key[key] = [item, hint]
            order.append(key)
        elif hint and not by_key[key][1]:
            by_key[key][1] = hint
    uniq: List[tuple[str, str]] = [(by_key[k][0], by_key[k][1]) for k in order]

    suggestions: List[Suggestion] = []
    for item, hint in uniq[:12]:  # keep runtime bounded
        s = Suggestion(raw=item, hint_category=hint)
        try:
            if _is_url_item(item):
                s.url = _normalise_url(item)
                if "doi.org/" in s.url.lower():
                    t, y, ab = _resolve_from_doi(s.url, email)
                    s.title, s.year, s.abstract = t, y, ab
                    s.source = "crossref"
                elif "openreview.net/forum" in s.url.lower():
                    t, y, ab = _resolve_from_openreview(s.url)
                    s.title, s.year, s.abstract = t, y, ab
                    s.source = "openreview"
                elif "arxiv.org/" in s.url.lower():
                    t, y, ab = _resolve_from_arxiv(s.url)
                    if t:
                        s.title, s.year, s.abstract = t, y, ab
                        s.source = "arxiv"
                    else:
                        s.title = re.sub(r"[-_]+", " ", s.url.rsplit("/", 1)[-1]).strip()[:160]
                        s.source = "url"
                else:
                    # Non-DOI URL: best-effort title from URL slug
                    s.title = re.sub(r"[-_]+", " ", s.url.rsplit("/", 1)[-1]).strip()[:160]
                    s.source = "url"
            else:
                s.title = item
                t, u, y, score, ab = _resolve_from_title(item, email)
                if score >= 80 and u:
                    s.title, s.url, s.year, s.abstract = t, u, y, ab
                    s.source = f"openalex:{int(score)}"
                else:
                    s.status = "warning"
                    s.note = "Could not confidently resolve this title; reply with `/triage` and a DOI/URL, or open a focused issue."

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
                title=s.title, url=s.url, year=s.year,
                source="issue", pub_type=PubType.UNKNOWN,
            )
            ok, msg = check_no_duplicate(paper, existing_urls, existing_dois, existing_titles)
            if not ok:
                s.duplicate = True
                if s.status == "ok":
                    s.status = "warning"
                s.note = f"Possible duplicate: {msg}"

    # ── Auto-assign category + description for ready (non-duplicate) candidates ──
    for s in suggestions:
        if s.status == "ok" and not s.duplicate:
            marker, display, _score = classify_category(
                f"{s.title} {notes}", cfg, fallback_display=s.hint_category or user_category
            )
            s.marker, s.category_display = marker, display
            s.description = _suggest_description(s.title, s.abstract, client, model, notes)

    # Items eligible to be auto-added: resolved, not duplicate, have year + category
    to_add = [
        s for s in suggestions
        if s.status == "ok" and not s.duplicate and s.marker and s.year
    ]
    needs_category = [
        s for s in suggestions
        if s.status == "ok" and not s.duplicate and not s.marker
    ]
    unresolved = [s for s in suggestions if s.status != "ok"]

    # ── Inject into README and emit PR outputs ─────────────────────────────────
    has_changes = False
    if to_add and issue_number:
        new_readme = readme_text
        # Group by marker to preserve section order
        ordered_markers: List[str] = []
        for s in to_add:
            if s.marker not in ordered_markers:
                ordered_markers.append(s.marker)
        for marker in ordered_markers:
            entries = []
            for s in to_add:
                if s.marker != marker:
                    continue
                title_s = _sanitize_title(s.title)
                desc = s.description or (
                    _clean_desc(notes.splitlines()[0]) if notes else
                    "_Add one sentence naming the exact model and task_"
                )
                entries.append(f"- [{title_s}]({s.url}) ({s.year}) - {desc}.")
            new_readme = inject_entries(new_readme, marker, entries)

        if new_readme != readme_text:
            (ROOT / "README.md").write_text(new_readme, encoding="utf-8")
            has_changes = True
            branch = f"issue-suggestion/{issue_number}"
            pr_title = f"[Suggestion] Add {len(to_add)} paper(s) — issue #{issue_number}"
            _set_output("has_changes", "true")
            _set_output("branch", branch)
            _set_output("pr_title", pr_title)

            pr_lines = [
                f"## Paper suggestions from issue #{issue_number}",
                "",
                f"Closes #{issue_number}",
                "",
                "Resolved and validated automatically from the issue, then injected "
                "into `README.md` under their auto-assigned categories.",
                "",
                "| Title | Category | Source |",
                "|---|---|---|",
            ]
            for s in to_add:
                pr_lines.append(
                    f"| [{_sanitize_title(s.title)}]({s.url}) | {s.category_display} | {s.source} |"
                )
            pr_lines += [
                "",
                "> Review-gate checks (format / dedup / link reachability) run automatically.",
                "> This PR is **not** auto-merged — a maintainer will review and merge.",
            ]
            pr_body_file = os.environ.get("PR_BODY_FILE")
            if pr_body_file:
                Path(pr_body_file).write_text("\n".join(pr_lines), encoding="utf-8")

    if not has_changes:
        _set_output("has_changes", "false")

    # ── Compose issue comment ──────────────────────────────────────────────────
    if has_changes:
        status = "✅ Opening a pull request"
    elif to_add or needs_category:
        status = "⚠️ Some items marked Unsure"
    else:
        status = "⚠️ Partial results"

    out: List[str] = [
        f"## {status} — Paper Suggestion Validation",
        "",
        "| Input | Result | Category | Notes |",
        "|---|---|---|---|",
    ]
    for s in suggestions:
        icon = "✅" if s.status == "ok" else ("⚠️" if s.status == "warning" else "❌")
        resolved = s.title if s.title else "(unresolved)"
        if s.url:
            resolved = f"[{resolved}]({s.url})"
        cat = s.category_display or "—"
        note = s.note or (f"resolved via {s.source}" if s.source else "")
        out.append(f"| `{s.raw[:60]}` | {icon} {resolved} | {cat} | {note} |")

    if has_changes:
        out += [
            "",
            f"A pull request with **{len(to_add)}** entry/entries is being opened. "
            "It will **close this issue automatically when merged**.",
        ]

    if needs_category:
        out += [
            "",
            "### Category: Unsure",
            "",
            "These resolved but couldn't be auto-categorized, so they're marked "
            "**Unsure** and left out of the pull request for now:",
        ]
        for s in needs_category:
            out.append(f"- [{_sanitize_title(s.title)}]({s.url})")
        out.append(
            "\nReply with `/triage` and add a category hint (e.g. "
            "`liquid biopsy: <url>`), or edit the issue's **Category** field, "
            "and I'll add them."
        )

    if unresolved:
        out += [
            "",
            "### Couldn't resolve",
            "",
            "I can reprocess replies: comment **`/triage`** followed by the DOIs/URLs "
            "to retry. For anything still failing, please open a focused new issue "
            "for that specific paper.",
        ]

    if issue_url:
        out += ["", f"_Issue: {issue_url}_"]

    comment = "\n".join(out)
    comment_file = os.environ.get("COMMENT_FILE")
    if comment_file:
        Path(comment_file).write_text(comment, encoding="utf-8")
    else:
        print(comment)

    # Keep workflow green so the comment/PR steps always run.
    sys.exit(0)


if __name__ == "__main__":
    main()

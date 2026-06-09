#!/usr/bin/env python3
"""issue_triage.py — validate a paper suggestion submitted via GitHub issue.

Reads the structured issue body from the ISSUE_BODY env var (set by the
issue-triage workflow), validates URL reachability and duplicate checks,
then writes a Markdown comment to the file at COMMENT_FILE.

Exit code 0 = all checks passed; 1 = one or more checks failed.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

# Maps issue form dropdown label → README AUTO-PAPERS marker
_CATEGORY_TO_MARKER = {
    "DNA Methylation":        "DNA_METHYLATION",
    "Histone Modifications":  "HISTONE_MODIFICATIONS",
    "Chromatin Accessibility": "CHROMATIN_ACCESSIBILITY",
    "Multi-omics Integration": "MULTI_OMICS",
    "Liquid Biopsy":          "LIQUID_BIOPSY",
    "Novel Epigenetic Assays": "NOVEL_ASSAYS",
    "Datasets":               "DATASETS",
}

# GitHub issue form renders each field as:
#   ### Field Label\n\nvalue\n
_FIELD_RE = re.compile(r"### (.+?)\n\n(.*?)(?=\n### |\Z)", re.DOTALL)


def _parse_issue_body(body: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for m in _FIELD_RE.finditer(body):
        key = m.group(1).strip()
        val = m.group(2).strip()
        fields[key] = "" if val == "_No response_" else val
    return fields


def main() -> None:
    body = os.environ.get("ISSUE_BODY", "")
    if not body:
        print("ISSUE_BODY env var not set", file=sys.stderr)
        sys.exit(1)

    fields = _parse_issue_body(body)
    url         = fields.get("URL / DOI", "").strip()
    title       = fields.get("Paper Title", "").strip()
    year        = fields.get("Publication Year", "").strip()
    category    = fields.get("Category", "").strip()
    description = fields.get("Description (optional)", "").strip()

    rows: list[tuple[str, str]] = []   # (icon, message)
    all_ok = True

    # ── Required fields ────────────────────────────────────────────────────────
    for label, val in [("URL / DOI", url), ("Paper Title", title),
                       ("Publication Year", year), ("Category", category)]:
        if not val:
            rows.append(("❌", f"Missing required field: **{label}**"))
            all_ok = False

    # ── URL reachability ───────────────────────────────────────────────────────
    if url:
        from scripts.review_agent import check_link_reachable
        ok, msg = check_link_reachable(url)
        if ok:
            rows.append(("✅", f"URL is reachable: `{url}`"))
        else:
            rows.append(("❌", f"URL check failed — {msg}"))
            all_ok = False

        # ── Duplicate check ────────────────────────────────────────────────────
        from scripts.update_list import parse_existing_entries
        from scripts.schemas import CandidatePaper, PubType
        from scripts.review_agent import check_no_duplicate

        readme_text = (ROOT / "README.md").read_text(encoding="utf-8")
        existing_urls, existing_dois, existing_titles = parse_existing_entries(readme_text)

        yr = int(year) if year.isdigit() else 0
        paper = CandidatePaper(title=title, url=url, year=yr,
                               source="issue", pub_type=PubType.UNKNOWN)
        dup_ok, dup_msg = check_no_duplicate(paper, existing_urls, existing_dois, existing_titles)
        if dup_ok:
            rows.append(("✅", "No duplicate found in the current list"))
        else:
            rows.append(("⚠️", f"Possible duplicate — {dup_msg}"))
            all_ok = False

    # ── Build formatted README entry ───────────────────────────────────────────
    entry = ""
    if url and title and year:
        desc = description or "_Add a one-sentence description of the specific method and contribution._"
        entry = f"- [{title}]({url}) ({year}) - {desc}."

    # ── Compose comment ────────────────────────────────────────────────────────
    status = "✅ All checks passed" if all_ok else "❌ One or more checks failed"
    lines: list[str] = [
        f"## {status} — Paper Suggestion Validation",
        "",
        "| | Check |",
        "|---|---|",
    ]
    for icon, msg in rows:
        lines.append(f"| {icon} | {msg} |")

    if entry:
        lines += [
            "",
            "### Suggested entry for `README.md`",
            "",
            "```markdown",
            entry,
            "```",
        ]

    marker = _CATEGORY_TO_MARKER.get(category, category.upper().replace(" ", "_"))
    if all_ok and category:
        lines += [
            "",
            "### How to add it",
            "",
            f"Open a pull request and place the entry **above** the "
            f"`<!-- AUTO-PAPERS:{marker} START -->` marker in the "
            f"**{category}** section of `README.md`.",
            "The review-gate CI (format + dedup + link check) runs automatically.",
            "",
            "_Or leave this issue open and a maintainer will pick it up in the next bot run._",
        ]
    elif not all_ok:
        lines += [
            "",
            "### Action needed",
            "",
            "Please fix the issues above. The bot will re-validate automatically when you edit this issue.",
        ]

    comment = "\n".join(lines)

    comment_file = os.environ.get("COMMENT_FILE")
    if comment_file:
        Path(comment_file).write_text(comment, encoding="utf-8")
    else:
        print(comment)

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()

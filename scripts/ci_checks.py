#!/usr/bin/env python3
"""ci_checks.py — CI entry point for the review-gate workflow.

Runs deterministic and LLM-grounded checks on changed README entries.

Usage (always run from project root):
  python -m scripts.ci_checks --check README.md
  python -m scripts.ci_checks --llm-review README.md
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

import httpx

from scripts.schemas import CandidatePaper, Decision, PubType
from scripts.review_agent import (
    _get_llm_client,
    _llm_call,
    check_format,
    check_link_reachable,
    check_no_duplicate,
)

ROOT = Path(__file__).parent.parent
README_PATH = ROOT / "README.md"
CANDIDATES_JSON = ROOT / "candidates.json"


def _append_report(lines: List[str]) -> None:
    """Append a markdown block to CI_REPORT_FILE (if set) for the workflow to render."""
    path = os.environ.get("CI_REPORT_FILE")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

_ENTRY_LINE_RE = re.compile(r"^\+\s*-\s+\[.+?\]\(https?://[^\)]+\)")
_URL_RE = re.compile(r"\]\((https?://[^\)]+)\)")
_TITLE_RE = re.compile(r"^\+\s*-\s+\[([^\]]+)\]")
_YEAR_RE = re.compile(r"\((\d{4})[^\)]*\)")


# ── Diff parsing ──────────────────────────────────────────────────────────────

def get_new_entry_lines() -> List[str]:
    """Return added markdown list entries from the current git diff vs. origin/main."""
    try:
        result = subprocess.run(
            ["git", "diff", "origin/main", "--", "README.md"],
            capture_output=True, text=True, check=True, cwd=ROOT,
        )
        diff = result.stdout
    except subprocess.CalledProcessError:
        # Fall back to staged diff
        try:
            result = subprocess.run(
                ["git", "diff", "--cached", "--", "README.md"],
                capture_output=True, text=True, check=True, cwd=ROOT,
            )
            diff = result.stdout
        except Exception:
            return []

    new_lines: List[str] = []
    for line in diff.splitlines():
        if _ENTRY_LINE_RE.match(line):
            new_lines.append(line[1:].rstrip())  # strip leading '+' and trailing whitespace

    return new_lines


def parse_entry_url(entry: str) -> str:
    m = _URL_RE.search(entry)
    return m.group(1) if m else ""


def parse_entry_title(entry: str) -> str:
    m = _TITLE_RE.match(entry)
    return m.group(1) if m else ""


def parse_entry_year(entry: str) -> int:
    m = _YEAR_RE.search(entry)
    return int(m.group(1)) if m else 0


# ── Deterministic checks ──────────────────────────────────────────────────────

def run_deterministic_checks(readme_path: Path) -> Tuple[bool, List[str]]:
    """Check format, dedup, and link reachability for all new entries."""
    from scripts.update_list import parse_existing_entries

    new_entries = get_new_entry_lines()
    if not new_entries:
        print("[CI] No new entries detected — nothing to check.")
        return True, []

    print(f"[CI] Checking {len(new_entries)} new entry/entries...")

    # Parse baseline (base branch) for dedup
    base_readme = _get_base_readme()
    existing_urls, existing_dois, existing_titles = parse_existing_entries(base_readme)

    failures: List[str] = []

    for entry in new_entries:
        # Format
        ok, msg = check_format(entry)
        if not ok:
            failures.append(f"[format] {msg}")
            continue

        url = parse_entry_url(entry)
        title = parse_entry_title(entry)
        year = parse_entry_year(entry)

        # Build minimal CandidatePaper for dedup check
        paper = CandidatePaper(
            title=title, url=url, year=year, source="ci_check",
            pub_type=PubType.UNKNOWN,
        )

        ok, msg = check_no_duplicate(paper, existing_urls, existing_dois, existing_titles)
        if not ok:
            failures.append(f"[dedup] {msg}")
            continue

        ok, msg = check_link_reachable(url)
        if not ok:
            failures.append(f"[link] {msg}")

    if failures:
        print("[CI] FAIL — deterministic checks:")
        for f in failures:
            print(f"  ✗ {f}")
        _append_report(
            ["### ❌ Format / dedup / link checks", ""]
            + [f"- {f}" for f in failures]
        )
        return False, failures

    print(f"[CI] PASS — all {len(new_entries)} entry/entries passed deterministic checks.")
    return True, []


def _get_base_readme() -> str:
    """Get the README content from origin/main for dedup baseline."""
    try:
        result = subprocess.run(
            ["git", "show", "origin/main:README.md"],
            capture_output=True, text=True, check=True, cwd=ROOT,
        )
        return result.stdout
    except Exception:
        # Fallback: current file (idempotency check still works)
        return README_PATH.read_text(encoding="utf-8")


# ── LLM review ────────────────────────────────────────────────────────────────

_LLM_REVIEW_SYSTEM = (
    "You are a strict scientific curator reviewing new entries proposed for an "
    "'awesome' list of ML in epigenetics. Evaluate each entry for relevance, "
    "accuracy, and format. Respond in strict JSON."
)

_LLM_REVIEW_USER = """\
Review these proposed new entries for the awesome-ml-epigenetics list.

Entries:
{entries}

For each entry, check:
1. Does the title and description accurately describe an ML/DL paper in epigenetics?
2. Is the description concise and technically accurate based on the title alone?
3. Are there any red flags (irrelevant, wrong category, duplicate concept)?

Respond with ONLY this JSON:
{{
  "overall_decision": "approve" | "reject" | "needs-review",
  "issues": ["<issue 1>", ...],  // empty list if none
  "summary": "<1-2 sentence overall assessment>"
}}"""


def run_llm_review(readme_path: Path) -> Tuple[bool, List[str]]:
    """Run Stage-1 LLM verification on new entries."""
    new_entries = get_new_entry_lines()
    if not new_entries:
        print("[CI/LLM] No new entries — skipping LLM review.")
        return True, []

    client = _get_llm_client()
    if not client:
        print("[CI/LLM] SKIP — GitHub Models unavailable (no GITHUB_TOKEN). Leaving PR open for human review.")
        _append_report([
            "### ⚠️ LLM grounded review could not run", "",
            "- GitHub Models was unavailable (no `GITHUB_TOKEN`). The PR is held "
            "open so a maintainer can review the new entries manually.",
        ])
        # Exit 1 to hold the PR open when LLM is required
        return False, ["LLM review required but GitHub Models unavailable"]

    entries_block = "\n".join(new_entries)
    prompt = _LLM_REVIEW_USER.format(entries=entries_block)

    import os
    cfg_model = "gpt-4o-mini"
    raw = _llm_call(
        client, cfg_model,
        [{"role": "system", "content": _LLM_REVIEW_SYSTEM},
         {"role": "user", "content": prompt}],
        max_tokens=400,
    )

    if not raw:
        _append_report([
            "### ❌ LLM grounded review", "",
            "- The model call returned nothing. Re-run the job, or review the "
            "entries manually before merging.",
        ])
        return False, ["LLM call failed — cannot complete grounded review"]

    try:
        import json as _json
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        data = _json.loads(m.group(0) if m else raw)
        overall = (data.get("overall_decision") or "needs-review").lower()
        issues: List[str] = data.get("issues") or []
        summary = str(data.get("summary", ""))
    except Exception:
        _append_report([
            "### ❌ LLM grounded review", "",
            f"- Could not parse the model response: `{raw[:120]}`",
        ])
        return False, [f"LLM response parse error: {raw[:120]}"]

    print(f"[CI/LLM] Decision: {overall}")
    print(f"[CI/LLM] {summary}")

    if issues:
        print("[CI/LLM] Issues found:")
        for iss in issues:
            print(f"  ✗ {iss}")

    if overall == "approve":
        print("[CI/LLM] PASS — LLM review approved all entries.")
        return True, []

    print(f"[CI/LLM] {overall.upper()} — leaving PR open for human inspection.")
    detail = issues or [
        "LLM flagged entries as needs-review" if overall == "needs-review"
        else "LLM rejected one or more entries"
    ]
    _append_report(
        ["### ❌ LLM grounded review", "", f"**Decision:** `{overall}`", ""]
        + ([f"_{summary}_", ""] if summary else [])
        + [f"- {i}" for i in detail]
    )
    return False, detail


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="CI checks for review-gate workflow")
    parser.add_argument("readme", nargs="?", default="README.md")
    parser.add_argument("--check", action="store_true", help="Run deterministic checks")
    parser.add_argument("--llm-review", action="store_true", help="Run LLM grounded review")
    args = parser.parse_args()

    readme_path = ROOT / args.readme

    if args.check:
        ok, failures = run_deterministic_checks(readme_path)
        if not ok:
            sys.exit(1)
        sys.exit(0)

    if args.llm_review:
        ok, failures = run_llm_review(readme_path)
        if not ok:
            sys.exit(1)
        sys.exit(0)

    parser.print_help()
    sys.exit(1)


if __name__ == "__main__":
    main()

# Design & Developer Guide

This document describes the architecture of the automated paper-discovery pipeline, how to run it locally, and how to extend or configure it.

---

## Table of Contents

1. [Architecture overview](#1-architecture-overview)
2. [Repository layout](#2-repository-layout)
3. [Local development](#3-local-development)
4. [Configuration reference](#4-configuration-reference)
5. [Pipeline walkthrough](#5-pipeline-walkthrough)
6. [GitHub Actions workflows](#6-github-actions-workflows)
7. [One-time repository setup](#7-one-time-repository-setup)
8. [Extending the pipeline](#8-extending-the-pipeline)
9. [Rate limits & quotas](#9-rate-limits--quotas)
10. [Adding entries manually](#10-adding-entries-manually)

---

## 1. Architecture overview

```
┌──────────────────────────────────────────────────────────────────┐
│  Scheduled GitHub Action (bi-weekly)                             │
│                                                                  │
│  ┌─────────────┐    ┌──────────────┐    ┌────────────────────┐  │
│  │  Adapters   │───▶│  Rule-based  │───▶│  Stage-1 LLM       │  │
│  │  (5 APIs)   │    │  scoring     │    │  abstract screen   │  │
│  └─────────────┘    └──────────────┘    └────────┬───────────┘  │
│                                                  │ pass         │
│                                         ┌────────▼───────────┐  │
│                                         │  Stage-2 LLM       │  │
│                                         │  full-text review  │  │
│                                         └────────┬───────────┘  │
│                                                  │              │
│                                    ┌─────────────▼──────────┐   │
│                                    │  Inject into README    │   │
│                                    │  → open Pull Request   │   │
│                                    └────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
         ▼ PR opened
┌────────────────────┐        ┌────────────────────┐
│  review-gate CI    │──pass──▶  auto-merge.yml     │
│  (deterministic    │        │  (squash merge)     │
│   + LLM grounded)  │        └────────────────────┘
└────────────────────┘
        ▲
        │ PR opened (Closes #N)
┌────────────────────┐
│  issue-triage.yml  │  ◀── user files a "Paper Suggestion" issue
│  (resolve + class- │      (label: paper-suggestion, or comment /triage)
│   ify + ground)    │
└────────────────────┘
```

**Key design decisions:**

- **No personal API keys.** All publication APIs (OpenAlex, Europe PMC, PubMed, arXiv, bioRxiv) are free and keyless. The LLM uses GitHub Models via the built-in `GITHUB_TOKEN` (`permissions: models: read`).
- **Two ways in.** Papers enter either via the scheduled discovery run *or* via user-submitted **Paper Suggestion** issues (`issue-triage.yml`); both converge on the same review-gate → auto-merge path.
- **Two-stage screening.** Stage-1 is a fast abstract-level LLM verdict. Stage-2 is a deeper review of the OA full text — only papers that pass Stage-1 and have a freely accessible version proceed.
- **Ensemble voting.** A paper must pass *both* the rule-based scorer and the Stage-1 LLM to avoid false positives.
- **Sharding.** One category per workflow run to stay well inside the free GitHub Models quota (~150 low-tier requests/day).
- **Unprivileged CI.** `review-gate.yml` runs with minimal permissions and cannot merge; `auto-merge.yml` is a separate privileged workflow that only fires after the gate passes.
- **Single source of truth for validation.** Link reachability, dedup, and the grounded LLM check run once, in `review-gate.yml`. `issue-triage.yml` only resolves metadata and writes the description; the gate's result — including concrete failure hints — is mirrored back onto the originating issue.

---

## 2. Repository layout

```
.
├── README.md                   ← The curated list (hand-edited + auto-injected)
├── config.yml                  ← Central pipeline configuration
├── pyproject.toml              ← Python project & dependencies (managed by uv)
├── uv.lock                     ← Locked dependency graph (commit this)
├── .gitignore
├── scripts/
│   ├── __init__.py
│   ├── schemas.py              ← CandidatePaper dataclass
│   ├── review_agent.py         ← Rule-based scoring + LLM Stage-1/2
│   ├── fulltext.py             ← Open-access full-text fetcher
│   ├── update_list.py          ← Main CLI orchestrator
│   ├── ci_checks.py            ← CI entry point (review-gate)
│   ├── issue_triage.py         ← Resolve/classify paper-suggestion issues → PR
│   └── adapters/
│       ├── __init__.py
│       ├── openalex.py
│       ├── europepmc.py
│       ├── pubmed.py
│       ├── arxiv.py
│       ├── biorxiv.py
│       └── crossref.py         ← DOI enrichment only (not primary discovery)
└── .github/
    ├── ISSUE_TEMPLATE/
    │   └── paper_suggestion.yml ← Issue form for paper suggestions
    └── workflows/
        ├── propose-update.yml  ← Scheduled discovery → PR
        ├── issue-triage.yml    ← Suggestion issue → PR
        ├── review-gate.yml     ← CI checks on PR
        └── auto-merge.yml      ← Merge after gate passes
```

`README.md` contains HTML comment markers that act as bot-owned sub-blocks:

```markdown
<!-- AUTO-PAPERS:DNA_METHYLATION START -->
<!-- AUTO-PAPERS:DNA_METHYLATION END -->
```

New entries are injected just before each `END` marker. Everything outside the markers is human-maintained and is never touched by the pipeline.

---

## 3. Local development

### Prerequisites

- macOS / Linux
- [`uv`](https://docs.astral.sh/uv/) — the only tool you need to install globally:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

### Setup

```bash
git clone https://github.com/<you>/awesome-ml-epigenetics
cd awesome-ml-epigenetics

# Create .venv and install all deps from uv.lock
uv sync
```

`uv sync` creates `.venv/` and installs exact pinned versions. The venv is **not** committed (see `.gitignore`).

### Running the pipeline locally

All commands use `uv run` so there is no need to activate the venv manually.

```bash
# Dry-run a single category (no files written, no PR opened)
uv run python -m scripts.update_list --category liquid-biopsy --dry-run

# Run all categories in dry-run mode
uv run python -m scripts.update_list --all-categories --dry-run

# Actually update README.md (writes the file)
uv run python -m scripts.update_list --category dna-methylation

# Use a custom config file
uv run python -m scripts.update_list --category dna-methylation --config config.yml
```

**Exit codes:**

| Code | Meaning |
|------|---------|
| `0` | One or more papers were accepted; README was updated |
| `1` | No candidates survived screening |
| `2` | Papers passed Stage-1 but need human review (no OA full text) |

### Running CI checks locally

```bash
# Deterministic checks (format, dedup, link reachability)
uv run python -m scripts.ci_checks --check README.md

# LLM grounded review — requires GITHUB_TOKEN in your shell
GITHUB_TOKEN=ghp_... uv run python -m scripts.ci_checks --llm-review README.md
```

### Running the test suite

```bash
uv run pytest
```

Dev dependencies (`pytest`, `pytest-httpx`) are in the `[dependency-groups] dev` section of `pyproject.toml` and are installed automatically by `uv sync`.

### Adding / upgrading dependencies

```bash
# Add a runtime dependency
uv add <package>

# Add a dev-only dependency
uv add --dev <package>

# Upgrade everything to latest compatible versions
uv lock --upgrade
uv sync
```

Commit both `pyproject.toml` and `uv.lock` after changes.

---

## 4. Configuration reference

All tunable parameters live in `config.yml`. Key sections:

### `discovery`

| Key | Default | Description |
|-----|---------|-------------|
| `email` | `auto-update@…` | Passed to polite-pool APIs (OpenAlex, Unpaywall). Change to your own. |
| `date_window_days` | `90` | How many days back to search for new papers. |
| `max_raw_results_per_term` | `25` | Results fetched per search term per source before dedup. |

### `sources`

Toggle individual publication sources on/off:

```yaml
sources:
  openalex: true
  europepmc: true
  pubmed: true
  arxiv: true
  biorxiv: true
  crossref: false   # DOI enrichment only; not a primary source
```

### `categories`

Each category has:

| Key | Description |
|-----|-------------|
| `slug` | CLI flag value (e.g. `--category dna-methylation`) |
| `readme_marker` | Matches the `AUTO-PAPERS:<MARKER>` HTML comments in README |
| `search_terms` | Queries sent to each active source API |
| `keywords` | For the rule-based keyword-density scorer |
| `max_new_per_run` | Maximum papers injected per pipeline run |
| `relevance_threshold` | Minimum rule-based score (0–1) to pass Stage-1 |
| `preprint_threshold` | Higher threshold applied to preprints |

### `llm`

| Key | Default | Description |
|-----|---------|-------------|
| `model` | `gpt-4o-mini` | GitHub Models model name |
| `max_llm_candidates_per_run` | `30` | Stage-1 cap (manages quota) |
| `max_deep_reviews_per_day` | `6` | Stage-2 cap per run |
| `max_calls_per_paper` | `4` | LLM call budget for one Stage-2 review |
| `deep_review_enabled` | `true` | Disable to use Stage-1 only |
| `oa_version_discovery` | `true` | Try Unpaywall/arXiv before giving up on full text |

---

## 5. Pipeline walkthrough

```
update_list.py  process_category()
│
├── discover_candidates()        — calls all enabled source adapters
│   ├── adapters/openalex.py     → OpenAlex /works  (no key)
│   ├── adapters/europepmc.py    → EBI REST API     (no key)
│   ├── adapters/pubmed.py       → NCBI E-utilities (no key)
│   ├── adapters/arxiv.py        → arXiv Atom feed  (no key)
│   └── adapters/biorxiv.py      → bioRxiv/medRxiv  (no key)
│
├── dedup_candidates()           — URL / DOI exact match + rapidfuzz title fuzzy
│
├── rule_based_score()           — keyword density + preprint penalty → score ∈ [0,1]
│   └── sort by score, take top-N (max_llm_candidates_per_run)
│
├── stage1_llm_screen()          — abstract fed to GitHub Models; returns INCLUDE / EXCLUDE / NEEDS_REVIEW
│   └── ensemble: paper advances only if BOTH rule-based AND LLM vote INCLUDE
│
├── fetch_fulltext()             — for Stage-1 passes only
│   ├── arXiv → ar5iv HTML
│   ├── bioRxiv / medRxiv HTML
│   ├── Europe PMC XML (via PMC ID lookup)
│   └── Unpaywall (OA URL → download)
│
├── stage2_deep_review()         — section snippets → GitHub Models; returns verdict + suggested description
│   └── map-reduce for oversized sections (respects max_calls_per_paper)
│
└── inject_entries()             — writes new entries into README between AUTO-PAPERS markers
```

### `CandidatePaper` data flow

`scripts/schemas.py` defines the `CandidatePaper` dataclass. Fields get populated progressively as the paper moves through the pipeline:

| Stage | Fields set |
|-------|-----------|
| Adapter output | `title`, `url`, `year`, `source`, `pub_type`, `abstract`, `authors`, `venue`, `doi` |
| Rule-based | `relevance_score`, `rule_based_vote` |
| Stage-1 LLM | `llm_vote`, `reviewer_rationale`, `abstract_screen_decision` |
| Full-text fetch | `full_text_available`, `full_text_source`, `extracted_sections` |
| Stage-2 LLM | `deep_review_decision`, `deep_review_rationale`, `markdown_entry` |
| Final | `needs_human_review`, `final_category` |

---

## 6. GitHub Actions workflows

### `propose-update.yml` — discovery & PR creation

- **Triggers:** `schedule` (cron `0 6 1,15 * *`) and `workflow_dispatch`
- **Shard logic:** day-of-month 1 → category index 0, day 15 → index 1; repeats cycling through all 7 categories over successive runs
- **`workflow_dispatch` inputs:**
  - `category` — override the auto-selected shard (e.g. `liquid-biopsy`)
  - `dry_run` — print proposals without writing files or opening a PR
- **Artifact:** `candidates.json` is uploaded for every run (14-day retention) — useful for debugging which papers were seen

### `issue-triage.yml` — paper suggestions from issues → PR

- **Triggers:** `issues` (opened/edited) and `issue_comment` (created/edited) on issues labeled `paper-suggestion`
- On a **comment**, the bot only runs if the comment contains **`/triage`** (ordinary discussion is ignored); opening or editing the issue runs it automatically
- Steps:
  1. `scripts/issue_triage.py` resolves each pasted URL/title via OpenAlex, Crossref, the arXiv API, and the OpenReview API → title, year, **abstract**
  2. Auto-assigns a category (keyword match → user dropdown → `Unsure`) and writes an **abstract-grounded** description
  3. Injects ready entries into `README.md` and opens the PR. Link reachability and dedup are **not** checked here — they are deferred to the review-gate CI to avoid duplicated work.
  4. Opens a PR via `secrets.PR_PAT` on a deterministic `issue-suggestion/<n>` branch (re-running `/triage` updates the same PR) whose body contains `Closes #<n>`
  5. Replies on the issue with the resolution summary (the authoritative pass/fail comes later from the review-gate)
- **Permissions:** `contents: write`, `issues: write`, `pull-requests: write`, `models: read`
- The PR carries the `from-issue` label, so it flows through the same review-gate and auto-merge path as scheduled updates — and closes the originating issue on merge

### `review-gate.yml` — CI on PRs touching README

- Runs on every PR that modifies `README.md`
- **Unprivileged** — only `contents: read`, `issues: write`, `pull-requests: write`, `models: read`
- Steps:
  1. Deterministic checks (`--check`): format lint, dedup against `origin/main`, link reachability (HEAD request)
  2. LLM grounded review (`--llm-review`): on PRs labeled `auto-update` **or** `from-issue`; verifies each new entry is genuinely relevant — exits `1` if the LLM is unavailable (keeps PR open rather than auto-merging unreviewed)
  3. Upserts a summary comment on the PR. On failure it adds a **What to review** section with the concrete reasons (the failing format/dedup/link entries, or the LLM's flagged issues, written to `CI_REPORT_FILE` by `ci_checks.py`). For issue-sourced PRs (`issue-suggestion/<n>` branch) the same verdict and hints are mirrored back onto the originating issue.

### `auto-merge.yml` — privileged merge after gate passes

Fires as a `workflow_run` event after `review-gate` completes. Before merging it verifies **all seven** trust conditions:

1. Same repository (not a fork)
2. Branch matches `auto-update/papers-<run_id>-<slug>` **or** `issue-suggestion/<issue>`
3. PR has the `auto-update` **or** `from-issue` label
4. PR does **not** have `needs-human-review` label
5. HEAD SHA matches (review ran on current HEAD, not a stale commit)
6. Changed files limited to `README.md`
7. All required check runs succeeded

Uses `secrets.PR_PAT` (a fine-grained PAT) throughout; the standard `GITHUB_TOKEN` cannot trigger further workflow runs. A GitHub release is cut only for the scheduled `auto-update/papers-*` batches, not for issue-sourced PRs.

---

## 7. One-time repository setup

After pushing the code for the first time, complete these steps **once**:

### a) Create `PR_PAT`

Go to **GitHub → Settings → Developer settings → Fine-grained personal access tokens → Generate new token**.

Permissions needed (scoped to this repository):
- **Contents:** Read and write
- **Pull requests:** Read and write
- **Metadata:** Read (mandatory)

Add the token as a repository secret named `PR_PAT`:  
**Repository → Settings → Secrets and variables → Actions → New repository secret**

### b) Enable auto-merge

**Repository → Settings → General → Pull Requests → Allow auto-merge** ✓

### c) Branch protection on `main`

**Repository → Settings → Branches → Add branch ruleset** for `main`:

- Require status checks to pass: add `review-gate / review`
- Do not require approvals for auto-update PRs (the gate replaces human review)

### d) (Optional) Update the discovery email

In `config.yml` set `discovery.email` to a real address. OpenAlex and Unpaywall use this for the polite pool (higher rate limits); it is never used for anything else.

### e) Enable issue-based suggestions

The `issue-triage.yml` workflow turns **Paper Suggestion** issues into PRs. Make sure:

- **Issues are enabled** (Repository → Settings → General → Features → Issues ✓)
- The **`paper-suggestion`** label exists — `issue-triage.yml` only runs on issues carrying it. The issue form (`.github/ISSUE_TEMPLATE/paper_suggestion.yml`) applies it automatically; create it once with:
  ```bash
  gh label create paper-suggestion --description "Paper suggestion for the awesome list"
  ```
- `PR_PAT` is configured (step **a**) — it is reused to open the suggestion PR and reply on the issue.

---

## 8. Extending the pipeline

### Adding a new category

1. Add a new entry under `categories:` in `config.yml` following the existing pattern.
2. Insert the marker pair into `README.md` at the desired location:
   ```markdown
   <!-- AUTO-PAPERS:MY_CATEGORY START -->
   <!-- AUTO-PAPERS:MY_CATEGORY END -->
   ```
3. Update the `CATEGORIES` array in `.github/workflows/propose-update.yml` to include the new slug.

### Adding a new source adapter

1. Create `scripts/adapters/my_source.py` implementing a `search(search_terms, from_date, to_date, email, max_per_term) -> List[CandidatePaper]` function.
2. Import and export it in `scripts/adapters/__init__.py`.
3. Add a toggle key under `sources:` in `config.yml`.
4. Call it in `discover_candidates()` in `scripts/update_list.py`.

### Changing the LLM model

Update `llm.model` in `config.yml`. Any model available in [GitHub Models](https://github.com/marketplace/models) can be used — the client is a standard OpenAI-compatible endpoint pointing at `https://models.inference.ai.azure.com`.

---

## 9. Rate limits & quotas

| Resource | Limit | How it's managed |
|----------|-------|-----------------|
| GitHub Models (free tier) | ~150 low-tier req/day, 15 req/min, 8 000 in / 4 000 out tokens | `max_llm_candidates_per_run`, `max_deep_reviews_per_day`, `max_calls_per_paper` |
| OpenAlex | 10 req/s (polite pool) | 0.12 s sleep between calls |
| Europe PMC | ~500 req/min | 0.5 s sleep |
| PubMed E-utilities (no key) | 3 req/s | 0.4 s sleep |
| arXiv | No hard limit; be polite | 0.5 s sleep |
| bioRxiv / medRxiv | No hard limit | 0.5 s sleep, max 3 pages (300 papers) |

If you add a personal NCBI API key to `NCBI_API_KEY` the rate limit rises from 3 to 10 req/s — the PubMed adapter will pick it up automatically via `os.environ`.

---

## 10. Adding entries manually

Human-curated entries go **above** the `AUTO-PAPERS` start marker in each section of `README.md`. The pipeline will never modify content outside the markers.

Format:
```markdown
- [Paper Title](https://doi.org/10.xxxx/xxxxx) (Year) - One-sentence description of the contribution.
```

Opening a PR with such an entry will trigger `review-gate.yml`. Because the PR won't have the `auto-update` label, the LLM review step is skipped and the deterministic checks (format, dedup, link reachability) still run. Merge manually after those pass.

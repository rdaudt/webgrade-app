# WebGrade

WebGrade is a Windows-first CLI for website modernization audits.

## Local Setup

WebGrade should be run from a local Python virtual environment. The default workflow assumes a `.venv` directory in the project root.

### PowerShell setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
python -m playwright install chromium
```

Copy [.env.example](C:/Users/Carboteiro/projects/webgrade-app/.env.example) to `.env` and set the variables you plan to use.

### Run tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

### Run the CLI

```powershell
.\.venv\Scripts\python.exe -m webgrade run --input sample_catalog.csv --context .\docs\context-templates\context-municipal.md --output .\webgrade-output
```

### Useful flags

```powershell
.\.venv\Scripts\python.exe -m webgrade run --input sample_catalog.csv --context .\docs\context-templates\context-municipal.md --output .\webgrade-output --skip-vision
.\.venv\Scripts\python.exe -m webgrade run --input sample_catalog.csv --context .\docs\context-templates\context-municipal.md --output .\webgrade-output --skip-screenshots
.\.venv\Scripts\python.exe -m webgrade run --site https://example.com --context .\docs\context-templates\context-municipal.md --output .\webgrade-output --only-vision
```

## Current State

The current implementation covers the main v1 pipeline:

- catalog ingestion and SQLite batch/run persistence
- technical audit adapters for PageSpeed, security/TLS, freshness, DOM heuristics, and Wappalyzer-style technology detection
- Playwright screenshots and Pa11y accessibility checks
- OpenAI vision scoring with structured output and `--only-vision` reuse support
- required run-level `context.md` input with sector-based report framing
- deterministic scoring, findings, HTML reports, PDF exports, Excel export, and JSON export

Runs may still finish as `partial` when requested stages fail in the local environment, for example:

- missing Playwright browser binaries
- missing `OPENAI_API_KEY`
- network timeouts during screenshot capture
- PageSpeed API throttling (`429`)

## Operator Notes

- `OPENAI_API_KEY` is required only when vision scoring is enabled.
- `PAGESPEED_API_KEY` is optional but recommended to improve quota headroom.
- `OPENAI_VISION_MODEL` defaults to `gpt-5.4`.
- `WEBGRADE_VISION_DELAY_SECONDS` adds a delay between screenshot-scoring calls if you need to slow the vision stage down.
- `OPENAI_VISION_INPUT_COST_PER_1M_TOKENS` and `OPENAI_VISION_OUTPUT_COST_PER_1M_TOKENS` are optional. If set, WebGrade estimates vision cost in the batch review summary.
- `--context` is required for report-generating runs and should usually point to one of the starter templates in [docs/context-templates](C:/Users/Carboteiro/projects/webgrade-app/docs/context-templates).
- old `Audience Family` context files are no longer supported; use the richer `Sector Classification` format from the starter templates.
- the order of `Priority Impact Lenses` matters because it controls which reasons are surfaced first in the report body.
- each batch now writes a `batch-review.md` artifact with site outcomes, common issues, and aggregated vision token usage for pilot review.

For a fuller workflow, rerun behavior, and troubleshooting guide, see [docs/operator-runbook.md](C:/Users/Carboteiro/projects/webgrade-app/docs/operator-runbook.md).

## Contribution Workflow

Tracked changes should go through a feature branch and pull request before merging to `main`.

- create a branch from `main`
- keep the PR scoped to one coherent change
- leave pilot catalogs, ad hoc test scripts, and exploratory report drafts as local-only files unless they are intentionally promoted in their own PR

See [CONTRIBUTING.md](C:/Users/Carboteiro/projects/webgrade-app/CONTRIBUTING.md) for the working rules.

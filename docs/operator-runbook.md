# WebGrade Operator Runbook

## Purpose

This runbook is the Windows-first operator guide for running WebGrade locally inside a project virtual environment.

## Prerequisites

- Python 3.11 or newer
- Node.js available on `PATH`
- PowerShell
- Internet access for audited sites and external APIs

## Initial Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
python -m playwright install chromium
```

Create `.env` from [.env.example](C:/Users/Carboteiro/projects/webgrade-app/.env.example).

Recommended variables:

```dotenv
OPENAI_API_KEY=...
OPENAI_VISION_MODEL=gpt-5.4
WEBGRADE_VISION_DELAY_SECONDS=0.0
PAGESPEED_API_KEY=...
```

## Verification

Run the automated checks before the first real batch:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Pick the context template that matches the audience family for the batch:

- [context-municipal.md](C:/Users/Carboteiro/projects/webgrade-app/docs/context-templates/context-municipal.md)
- [context-for-profit.md](C:/Users/Carboteiro/projects/webgrade-app/docs/context-templates/context-for-profit.md)
- [context-nonprofit.md](C:/Users/Carboteiro/projects/webgrade-app/docs/context-templates/context-nonprofit.md)

Copy the appropriate template and edit it for the run before launching the batch.

Important context-file rules:

- old `Audience Family` context files are no longer supported
- use the richer `Sector Classification` format from the starter templates
- the order of `Priority Impact Lenses` controls which reasons appear first in the report body

## Common Commands

Full batch:

```powershell
.\.venv\Scripts\python.exe -m webgrade run --input sample_catalog.csv --context .\docs\context-templates\context-municipal.md --output .\webgrade-output
```

Skip vision:

```powershell
.\.venv\Scripts\python.exe -m webgrade run --input sample_catalog.csv --context .\docs\context-templates\context-municipal.md --output .\webgrade-output --skip-vision
```

Skip screenshots and vision:

```powershell
.\.venv\Scripts\python.exe -m webgrade run --input sample_catalog.csv --context .\docs\context-templates\context-municipal.md --output .\webgrade-output --skip-screenshots --skip-vision
```

Single site:

```powershell
.\.venv\Scripts\python.exe -m webgrade run --site https://example.com --context .\docs\context-templates\context-municipal.md --report-name "Example Report" --output .\webgrade-output
```

Reuse prior screenshots and technical evidence, then run vision only:

```powershell
.\.venv\Scripts\python.exe -m webgrade run --site https://example.com --context .\docs\context-templates\context-municipal.md --output .\webgrade-output --only-vision
```

## Output Layout

Each run creates a timestamped batch folder under the output root:

```text
webgrade-output/
  webgrade.sqlite3
  2026-03-31T17-00-00Z/
    webgrade.log
    context.md
    catalog.xlsx
    catalog.json
    reports/
    screenshots/
```

Artifacts are also recorded in SQLite for later inspection.

## Rerun Behavior

- `--skip-vision`
  - Captures screenshots if enabled, but does not call OpenAI.
- `--skip-screenshots`
  - Skips screenshot capture and therefore leaves vision unavailable for that run.
- `--only-vision`
  - Requires an existing prior run with both screenshots.
  - Reuses technical evidence and screenshots into a new run.
  - Executes only the vision, scoring, findings, and reporting path.

`--context` is required for report-generating runs. The batch stores:

- the raw `context.md` used for that run
- a normalized context summary in SQLite and `catalog.json`

Intentional skips do not force a run to `partial`. Requested-stage failures do.

## Interpreting Status

- `complete`
  - All requested stages succeeded.
- `partial`
  - Some requested stages failed, but output artifacts were still produced.
- `failed`
  - The run could not produce meaningful output.

## Known Limitations

- PageSpeed can hit `429 Too Many Requests`.
- Screenshot capture can still fail on some slow or restrictive sites even with one retry.
- PDF generation requires Playwright browser binaries installed in the active venv environment.
- Vision scoring requires valid screenshots and `OPENAI_API_KEY`.
- Technology detection is heuristic and should be treated as best-effort.

## Troubleshooting

If Playwright PDF or screenshots fail immediately:

```powershell
.\.venv\Scripts\python.exe -m playwright install chromium
```

If Pa11y fails to resolve:

- verify `node` and `npx` are on `PATH`
- or install a local dependency path that exposes `node_modules/.bin/pa11y.cmd`

If vision is failing:

- confirm `.env` contains `OPENAI_API_KEY`
- verify screenshots exist in the prior batch when using `--only-vision`
- increase `WEBGRADE_VISION_DELAY_SECONDS` if you suspect rate limiting

If PageSpeed is throttled:

- provide `PAGESPEED_API_KEY`
- reduce batch size with `--limit`
- rerun later

## Pilot Checklist

Before broader rollout:

1. Run 3-5 representative municipal sites.
2. Inspect `catalog.json`, `catalog.xlsx`, and each HTML report.
3. Check `webgrade.log` for stage failures and retry patterns.
4. Review score plausibility and top findings for calibration.
5. Record any sites that need screenshot timeout tuning or heuristic fixes.

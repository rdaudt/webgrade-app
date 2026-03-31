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
```

### Run tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

### Run the CLI

```powershell
.\.venv\Scripts\python.exe -m webgrade run --input sample_catalog.csv --output .\webgrade-output
```

## Current State

The current implementation covers the main v1 pipeline:

- catalog ingestion and SQLite batch/run persistence
- technical audit adapters for PageSpeed, security/TLS, freshness, DOM heuristics, and Wappalyzer-style technology detection
- Playwright screenshots and Pa11y accessibility checks
- OpenAI vision scoring with structured output and `--only-vision` reuse support
- deterministic scoring, findings, HTML reports, PDF exports, Excel export, and JSON export

Runs may still finish as `partial` when requested stages fail in the local environment, for example:

- missing Playwright browser binaries
- missing `OPENAI_API_KEY`
- network timeouts during screenshot capture
- PageSpeed API throttling (`429`)

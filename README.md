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

The current implementation is foundation-only:

- catalog ingestion works
- SQLite batch/run persistence works
- JSON and Excel scaffold exports work
- real audit adapters are not implemented yet

Until the adapters are added, site runs are expected to finish as `partial`.

# Contributing

## Branching And PRs

This repository now uses a PR-first workflow for tracked changes.

- Do not push tracked work directly to `main`.
- Create a feature branch from `main` for each coherent change.
- Push the branch to `origin`.
- Open a pull request targeting `main`.
- Use PR review as the default gate before merge.

Recommended branch names:

- `feature/<topic>`
- `fix/<topic>`
- `docs/<topic>`

Keep each PR focused on one coherent change. Do not mix implementation work, report-design exploration, and operator-only pilot artifacts in the same PR.

## Local-Only Working Files

The following kinds of files should stay local unless they are intentionally promoted in a dedicated PR:

- pilot catalogs and operator-specific run inputs
- ad hoc test scripts and sample images
- exploratory report drafts not yet accepted as product documentation

Current ignored local-only examples:

- `pilot_*.csv`
- `tests/gpt54_vision_test.py`
- `tests/pipoca.JPG`
- `specs/clinton_website_assessment_report.html`

If one of those files later becomes official documentation or test coverage, remove the ignore rule in the same PR that promotes it.

## PR Review Expectations

Every PR review should check:

- whether the change belongs in the repository at all
- whether the change is implementation, documentation, or operator-only material
- whether audience-facing report language matches the intended recipient family
- whether behavior changes include validation evidence or tests

## Validation

Before opening a PR for code changes, run the relevant local checks from the project virtual environment:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Add any manual validation notes to the PR description when the change affects reports, outputs, or operator workflow.

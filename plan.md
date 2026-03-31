## Plan: WebGrade CLI v1

Build a **Windows-first**, local, CLI-driven, serverless MVP for BC municipal website audits. Ship the core pipeline first: CSV input -> automated technical audits -> screenshots -> GPT-5.4 vision scoring -> scoring -> HTML/PDF/Excel/JSON outputs. Keep the local dashboard out of v1 because the **dashboard is deferred from v1**. Treat the composite result as an **opportunity score**, meaning a higher score indicates greater modernization need. Keep **vision scoring required in v1** and keep the SSL requirement deterministic as **SSL validity/expiry only**.

**Steps**

### Phase 1 - Scope freeze and project scaffold
1. Confirm the v1 scope decisions already made: Windows-first runtime, BC municipalities first, dashboard deferred from v1, JSON export included in v1, vision scoring required in v1, and SSL validity/expiry only.
2. Scaffold the Python package and local developer environment. Make a project-local Python virtual environment the default workflow, and create the initial project layout, dependency management, `.env.example`, and a small `sample_catalog.csv` for smoke tests.
3. Define the app boundaries before coding: single-machine execution only, no server, no collector implementations in v1, and no outreach or CRM features.
4. Add the collector interface stub to the architecture early so future collectors can emit CSV-compatible inputs without changing the pipeline.

### Phase 2 - Core data and CLI foundation (blocks later phases)
5. Create the SQLite schema and persistence layer for `sites`, `runs`, `scores`, `findings`, and `screenshots`. Store multiple runs per URL by timestamp so later phases can support `--only-vision` and future incremental reruns cleanly.
6. Build the CLI entry point and run orchestration with logging, progress reporting, output directory handling, and flags for `--input`, `--output`, `--site`, `--limit`, `--skip-vision`, `--skip-screenshots`, `--only-vision`, and `--report-name`.
7. Implement CSV ingestion and validation, including pass-through metadata fields (`name`, `region`, `population`, `tier`, `notes`) and friendly error handling for malformed rows.
8. Define output-directory conventions and artifact naming for reports, screenshots, logs, Excel exports, and public JSON exports so repeated runs remain easy to inspect.

### Phase 3 - Technical audit adapters (can parallelize after Phase 2)
9. Add the PageSpeed adapter for desktop and mobile scores. Persist raw quality values, category sub-scores, and normalized opportunity contributions.
10. Add direct HTTP and TLS audit adapters for security headers and SSL validity/expiry only. Include deterministic handling for valid, invalid, expired, and expiring-soon certificates without introducing a third-party SSL grading dependency.
11. Add content freshness adapters: Wayback CDX first-archive and recent-archive lookups, approximate change-frequency heuristics, footer copyright-year extraction, and visible news/events date scraping.
12. Add lightweight DOM heuristics for viewport meta, homepage search presence, and contact-information prominence near the top of the rendered page.
13. Add Wappalyzer-based technology fingerprinting for CMS platform/version, JavaScript frameworks, hosting provider, analytics tools, and accessibility toolbar presence. Include CMS age and end-of-life flagging, and keep the implementation pluggable because detection quality will vary by site.

### Phase 4 - Rendering, accessibility, and vision layers (depends on Phase 2; parts can overlap with Phase 3)
14. Integrate Playwright for desktop and mobile page capture, timeout handling, and evidence screenshots stored by site slug and run date.
15. Integrate Pa11y through a stable subprocess wrapper and capture WCAG counts by severity and level. Validate Windows compatibility for Node.js, Playwright, and Pa11y early because this is the main local-runtime risk.
16. Implement fallback handling for render failures so a site can still receive a partial technical score and remain in the catalog and reports.
17. Add the explicit vision scoring adapter using the OpenAI Responses API. Submit existing screenshots, request structured JSON for the eight required dimensions (`layout_modernity`, `typography_quality`, `hero_effectiveness`, `navigation_clarity`, `mobile_usability`, `footer_usability`, `visual_design_era`, `brand_coherence`), and store both scores and rationales.
18. Configure the vision layer with `reasoning={"effort":"high"}`, a configurable inter-call delay, retry handling, exponential backoff for `429` responses, and null-on-failure/manual-review fallback after three failed attempts.
19. Keep screenshot capture and vision scoring as separate steps so `--skip-screenshots` and `--only-vision` have clear, deterministic behavior.

### Phase 5 - Scoring, findings, and report generation (depends on Phases 3-4)
20. Finalize the weighted opportunity scoring model, including inversion rules, null-handling, multi-source rollups, tier derivation, mobile-heavy weighting, and deterministic handling for partially missing data.
21. Build a deterministic findings engine that maps raw evidence into plain-language issues, motivation tags (`legal`, `resident_service`, `operational`, `reputation`, `financial`, `economic_development`), and effort labels.
22. Add the narrative layer needed by the reports while keeping the required v1 AI capability focused on screenshot scoring rather than replacing deterministic findings logic.
23. Generate self-contained HTML reports that follow the required section order: header, plain-language summary, at-a-glance scorecards, community impact findings, annotated visual evidence, detailed scorecard, recommended next steps, and technical appendix.
24. Generate PDF exports from the HTML reports via Playwright with print-friendly styling and full-content visibility.
25. Export the scored Excel catalog and a public JSON artifact containing site data, score breakdowns, findings, and output-file references for future dashboard use.

### Phase 6 - Polish, calibration, and release readiness
26. Run a pilot on 3-5 BC municipal sites to calibrate scores, verify report tone, confirm the annotated-report format is usable, and measure OpenAI usage and cost from real screenshots.
27. Tune thresholds, retries, normalization details, and copy based on pilot feedback, then run a larger batch before the full municipal set.
28. Document the operator workflow: install steps, project-local virtual environment setup, Windows-first PowerShell activation steps, required environment variables, known limitations, rerun behavior, and a simple repeat-usage runbook.

**Relevant files**
- `c:\Users\Carboteiro\projects\webgrade-app\specs\webgrade-prd.md` - source requirements and scoring/reporting rules
- `c:\Users\Carboteiro\projects\webgrade-app\pyproject.toml` - package metadata and dependencies
- `c:\Users\Carboteiro\projects\webgrade-app\.env.example` - API key configuration
- `c:\Users\Carboteiro\projects\webgrade-app\webgrade\cli.py` - CLI entry point and commands
- `c:\Users\Carboteiro\projects\webgrade-app\webgrade\config.py` - runtime settings, paths, and flags
- `c:\Users\Carboteiro\projects\webgrade-app\webgrade\db\schema.sql` or `webgrade\db\models.py` - SQLite schema
- `c:\Users\Carboteiro\projects\webgrade-app\webgrade\pipeline\orchestrator.py` - step-by-step run pipeline
- `c:\Users\Carboteiro\projects\webgrade-app\webgrade\collectors\base.py` - collector interface stub
- `c:\Users\Carboteiro\projects\webgrade-app\webgrade\adapters\pagespeed.py` - Google PageSpeed integration
- `c:\Users\Carboteiro\projects\webgrade-app\webgrade\adapters\security.py` - security-header and SSL validity/expiry checks
- `c:\Users\Carboteiro\projects\webgrade-app\webgrade\adapters\freshness.py` - Wayback and visible-date freshness logic
- `c:\Users\Carboteiro\projects\webgrade-app\webgrade\adapters\wappalyzer.py` - technology detection
- `c:\Users\Carboteiro\projects\webgrade-app\webgrade\adapters\accessibility.py` - Pa11y wrapper
- `c:\Users\Carboteiro\projects\webgrade-app\webgrade\adapters\screenshots.py` - Playwright capture logic
- `c:\Users\Carboteiro\projects\webgrade-app\webgrade\adapters\vision.py` - OpenAI screenshot scoring adapter
- `c:\Users\Carboteiro\projects\webgrade-app\webgrade\scoring\engine.py` - normalization and composite opportunity-score rules
- `c:\Users\Carboteiro\projects\webgrade-app\webgrade\reporting\findings.py` - deterministic findings engine
- `c:\Users\Carboteiro\projects\webgrade-app\webgrade\reporting\html_report.py` - HTML report assembly
- `c:\Users\Carboteiro\projects\webgrade-app\webgrade\exporters\excel.py` - workbook export
- `c:\Users\Carboteiro\projects\webgrade-app\webgrade\exporters\json_export.py` - public JSON export
- `c:\Users\Carboteiro\projects\webgrade-app\tests\` - CLI, scoring, adapter, and report-generation tests

**Tooling / API licensing and estimated costs**
- `OpenAI Responses API (GPT-5.4)` - paid commercial API and the only meaningful recurring cost expected in v1. Measure real screenshot costs during the pilot because image-heavy request costs depend on actual payload size and usage.
- `Google PageSpeed Insights API` - API key optional for better quota headroom; practical MVP cost expectation is `$0`.
- `Wayback Machine CDX API` - public and expected to be free, but with no SLA.
- `Playwright`, `SQLite`, `openpyxl`, `httpx`, `tqdm`, `python-dotenv`, `Node.js` - open-source or free; expected cost `$0`.
- `Pa11y` - open-source and free to run locally.
- `Wappalyzer` library - expected open-source usage path with no API fee for local fingerprinting, but the final package and license should still be verified during dependency pinning.

**Current cost expectation for v1**
1. Mandatory software licensing cost: effectively `$0`.
2. Likely recurring API cost at small scale: `OpenAI` only, to be measured during the pilot.
3. Storage and compute overhead on the operator machine: low to moderate because browser binaries, screenshots, logs, and exported artifacts accumulate over time.

**Verification**
1. Confirm every v1 goal in the PRD is represented in this plan.
2. Confirm nothing deferred from v1 in the PRD remains described here as v1 work.
3. Confirm every CLI option named in the PRD appears in this plan.
4. Confirm every required output artifact matches across both docs: `HTML`, `PDF`, `Excel`, `JSON`.
5. Confirm the vision layer appears in architecture, requirements, scoring, technical stack, and implementation phases.
6. Confirm there is no remaining reference to a v1 dashboard except in future-iteration discussions.
7. Confirm SSL wording is deterministic and implementable without a third-party grading dependency.

**Decisions**
- Included in v1: CLI, CSV input, collector interface stub, SQLite persistence, technical audit pipeline, screenshots, GPT-5.4 vision scoring, scoring, Excel export, JSON export, HTML reports, and PDF reports.
- Deferred from v1 core: concrete collectors, local dashboard UI, hosted dashboard or server, CRM or outreach automation, trend-analysis UI, and multi-user features.
- Recommendation: keep the findings engine deterministic and use AI where the spec requires it for screenshot scoring, not as a substitute for stable scoring logic.
- Recommendation: prove the pipeline and artifact quality before building any dashboard layer on top of the JSON export.

**Further considerations**
1. The main technical spike remains Windows compatibility for `Playwright + Pa11y + Node.js`.
2. The most important product decision to finalize before implementation is the exact normalization formula for the composite opportunity score, especially under partial or missing data.
3. If pilot costs for screenshot scoring are higher than expected, the least disruptive fallback is to narrow the report-writing use of AI while keeping the required vision-scoring contract intact.

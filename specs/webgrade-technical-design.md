# WebGrade v1 Technical Design

**Version:** 0.1  
**Date:** March 30, 2026  
**Status:** Draft  
**Related docs:** `specs/webgrade-prd.md`, `plan.md`

---

## 1. Purpose

This document is the engineering source of truth for WebGrade v1. It converts the PRD and implementation plan into a decision-complete design for:

- pipeline orchestration
- persistence and artifact layout
- exact v1 scoring formulas
- rerun and skip semantics
- deterministic findings generation
- report rendering contracts
- public JSON export shape
- failure handling and status rules

It does **not** restate product scope except where needed to make implementation decisions unambiguous.

---

## 2. Locked Defaults

The technical design assumes the following are already decided:

- Windows-first, local, CLI-only execution
- project-local Python virtual environment as the default runtime workflow
- mostly sequential per-site processing
- GPT-5.4 screenshot scoring is required in v1
- the local dashboard is deferred from v1
- public JSON export is one run-centric bundle per batch run
- missing data is handled by renormalizing available weights
- persistence is hybrid: normalized fields plus raw adapter JSON
- report screenshots use HTML overlay annotations, not burned-in image editing
- deterministic report text is the default; AI prose polish is optional future work and not part of the initial CLI

---

## 3. Runtime Architecture

### 3.1 Batch and site execution model

One CLI invocation creates one **batch**. A batch processes one or more **site runs**.

- A batch corresponds to one `python -m webgrade run ...` invocation from the active project virtual environment.
- A site run corresponds to one URL processed inside that batch.
- Processing is mostly sequential by site in v1.
- Inside a site run, adapters also execute sequentially.
- No cross-site parallelism is required in v1.

This keeps:

- logs readable
- OpenAI and PageSpeed throttling simple
- output artifacts deterministic
- retries isolated to a single site and stage

### 3.2 High-level pipeline

For each site run, the orchestrator executes the following stages in order:

1. catalog resolution and site record load/upsert
2. technical audit adapters
3. screenshot capture
4. vision scoring
5. score computation
6. findings generation
7. report rendering
8. export assembly

Stages 2-4 produce reusable evidence. Stages 5-8 are derived outputs and may be rerun from persisted evidence.

### 3.3 Module boundaries

The implementation should follow these internal modules:

- `webgrade.cli`
  - CLI parsing and validation
- `webgrade.pipeline.orchestrator`
  - batch lifecycle
  - per-site stage execution
  - rerun semantics
- `webgrade.collectors.base`
  - collector interface stub only
- `webgrade.adapters.*`
  - one adapter per external or heuristic source
- `webgrade.db.*`
  - schema and repository layer
- `webgrade.scoring.engine`
  - score normalization and composite computation
- `webgrade.reporting.findings`
  - deterministic finding rules
- `webgrade.reporting.html_report`
  - HTML assembly and overlay rendering
- `webgrade.exporters.*`
  - Excel and JSON exporters

---

## 4. Persistence Model

The PRD tables remain valid but are extended to support batch-level exports, reruns, and hybrid evidence storage.

### 4.1 Tables

#### `batches`

One row per CLI invocation.

```text
id                  INTEGER PRIMARY KEY
started_at          DATETIME
finished_at         DATETIME
status              TEXT  -- complete | partial | failed
input_path          TEXT
output_dir          TEXT
flags_json          TEXT  -- serialized CLI flags/options
site_count_total    INTEGER
site_count_complete INTEGER
site_count_partial  INTEGER
site_count_failed   INTEGER
```

#### `sites`

Same purpose as the PRD. `url` stays unique.

#### `runs`

One row per site processed inside a batch.

```text
id                    INTEGER PRIMARY KEY
batch_id              INTEGER REFERENCES batches(id)
site_id               INTEGER REFERENCES sites(id)
started_at            DATETIME
finished_at           DATETIME
status                TEXT  -- complete | partial | failed
report_name_override  TEXT
source_run_id         INTEGER NULL REFERENCES runs(id)
score_coverage        REAL  -- 0.0 to 1.0
manual_review_json    TEXT  -- array of reasons
```

`source_run_id` is used only when a run reuses prior evidence, for example `--only-vision`.

#### `adapter_results`

Canonical storage for adapter outputs.

```text
id                    INTEGER PRIMARY KEY
run_id                INTEGER REFERENCES runs(id)
adapter_key           TEXT
viewport              TEXT NULL  -- desktop | mobile | combined | null
status                TEXT  -- ok | partial | failed | skipped | reused
started_at            DATETIME
finished_at           DATETIME
summary_json          TEXT  -- normalized fields for this adapter
raw_json              TEXT  -- raw provider payload or structured raw evidence
error_json            TEXT NULL
copied_from_result_id INTEGER NULL REFERENCES adapter_results(id)
```

#### `scores`

Stores final score outputs, not raw provider payloads.

```text
id                  INTEGER PRIMARY KEY
run_id              INTEGER REFERENCES runs(id)
dimension           TEXT
raw_value           REAL NULL
opportunity_score   REAL
source_coverage     REAL  -- 0.0 to 1.0
viewport            TEXT  -- desktop | mobile | combined
source              TEXT
```

`raw_value` is used only when a score also has a direct quality-style raw value. For composite-only dimensions it may be `NULL`.

#### `findings`

Extends the PRD intent. `raw_evidence` stays JSON.

#### `screenshots`

```text
id                  INTEGER PRIMARY KEY
run_id              INTEGER REFERENCES runs(id)
viewport            TEXT  -- desktop | mobile
file_path           TEXT
captured_at         DATETIME
status              TEXT  -- captured | reused
source_run_id       INTEGER NULL REFERENCES runs(id)
metadata_json       TEXT  -- width, height, page_url, final_url
```

#### `artifacts`

Stores output artifact references.

```text
id                  INTEGER PRIMARY KEY
run_id              INTEGER NULL REFERENCES runs(id)
batch_id            INTEGER NULL REFERENCES batches(id)
artifact_type       TEXT  -- html_report | pdf_report | excel_catalog | json_bundle | log_file
relative_path       TEXT
metadata_json       TEXT
```

### 4.2 Hybrid storage rule

Each adapter persists both:

- normalized summary fields in `summary_json`
- raw provider or heuristic evidence in `raw_json`

This keeps querying simple while preserving traceability for:

- report appendix rendering
- debugging
- future rescoring without re-calling providers
- JSON export enrichment

### 4.3 Artifact layout

Each batch writes to one timestamped output directory:

```text
<output_root>/<batch_timestamp>/
  webgrade.log
  catalog.xlsx
  catalog.json
  reports/
    <site_slug>.html
    <site_slug>.pdf
  screenshots/
    <site_slug>/
      desktop.png
      mobile.png
```

All paths stored in SQLite and JSON exports are relative to the batch root.

### 4.4 Local environment expectation

The implementation and operator workflow assume a project-local virtual environment, normally `.venv`.

Expected Windows PowerShell setup:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

Automation, docs, and runbook examples should prefer:

- `.\.venv\Scripts\python.exe -m webgrade ...`
- `.\.venv\Scripts\python.exe -m unittest ...`

over commands that rely on globally installed packages.

---

## 5. CLI and Rerun Semantics

### 5.1 Supported flags

The technical design covers the PRD flags only:

- `--input`
- `--output`
- `--limit`
- `--skip-vision`
- `--skip-screenshots`
- `--only-vision`
- `--site`
- `--report-name`

### 5.2 Validation rules

- `--input` is required unless `--site` is present.
- `--only-vision` is mutually exclusive with `--skip-vision`.
- `--only-vision` is mutually exclusive with `--skip-screenshots`.
- `--only-vision` requires an existing prior run with both screenshots present for the selected site.
- `--report-name` applies only when one site is being processed.

### 5.3 Standard run

A standard run executes:

1. technical adapters
2. screenshot capture unless `--skip-screenshots`
3. vision scoring unless `--skip-vision` or screenshots are unavailable
4. scoring, findings, reports, and exports

### 5.4 `--skip-screenshots`

Behavior:

- screenshot stage is marked `skipped`
- vision stage is automatically marked `skipped`
- scoring continues without vision-dependent inputs
- reports still render, but the visual evidence section shows "Not captured in this run"
- batch and site runs can still be `complete` if all requested stages succeed

### 5.5 `--skip-vision`

Behavior:

- screenshots may still be captured for evidence
- vision stage is marked `skipped`
- scoring continues without vision-dependent inputs
- reports render without AI-generated visual callouts

### 5.6 `--only-vision`

Behavior:

- creates a new batch and new site run rows
- loads the most recent eligible prior run for each site
- copies forward technical `adapter_results` and `screenshots` into the new run as `reused`
- executes only vision scoring, scoring, findings, reports, and exports
- writes new HTML/PDF/JSON artifacts tied to the new run

This preserves run history while avoiding recomputation of technical checks.

### 5.7 Run status rules

Site run status:

- `complete`
  - all stages requested by CLI completed successfully
- `partial`
  - at least one requested stage failed, but enough evidence exists to compute scores or generate outputs
- `failed`
  - minimum viable output could not be produced, usually because the URL is invalid, prior evidence required by `--only-vision` is missing, or all scoring inputs are absent

Batch status:

- `complete` if all site runs are `complete`
- `partial` if any site run is `partial` and none are `failed`, or a mix of complete and failed exists
- `failed` if every site run failed before meaningful outputs were created

### 5.8 Score coverage

`score_coverage` is independent from run status.

- `score_coverage` = available composite dimension weight / 100
- a run may be `complete` with less than `1.0` coverage if the user intentionally skipped stages
- a run becomes `partial` only when requested stages fail, not when they are intentionally skipped

---

## 6. Canonical Internal Types

The implementation should expose these internal shapes even if not as literal dataclasses.

```python
class SiteRunContext(TypedDict):
    batch_id: int
    run_id: int
    site_id: int
    url: str
    site_slug: str
    output_dir: str
    flags: dict


class AdapterResult(TypedDict):
    adapter_key: str
    viewport: str | None
    status: Literal["ok", "partial", "failed", "skipped", "reused"]
    summary: dict
    raw: dict
    error: dict | None


class DimensionScore(TypedDict):
    dimension: str
    opportunity_score: float
    source_coverage: float
    inputs: dict


class FindingRecord(TypedDict):
    finding_key: str
    severity: Literal["high", "medium", "low"]
    effort: Literal["easy", "moderate", "significant"]
    framing_tags: list[str]
    summary_text: str
    impact_text: str
    municipality_text: str
    annotation_refs: list[str]
    evidence: dict


class Annotation(TypedDict):
    annotation_id: str
    viewport: Literal["desktop", "mobile"]
    source: Literal["vision", "dom"]
    finding_key: str
    kind: Literal["rect", "point"]
    x: float
    y: float
    width: float | None
    height: float | None
    title: str
    caption: str
```

Coordinates are normalized to `0.0-1.0` relative to screenshot width and height.

---

## 7. Adapter Contracts

Each adapter writes one `adapter_results` row per run and viewport combination it owns.

### 7.1 PageSpeed

Adapter keys:

- `pagespeed_desktop`
- `pagespeed_mobile`

`summary_json`:

```json
{
  "performance": 0,
  "accessibility": 0,
  "best_practices": 0,
  "seo": 0,
  "final_url": "",
  "fetched_at": ""
}
```

All four category values are stored as `0-100` quality scores.

### 7.2 Pa11y

Adapter key:

- `pa11y`

`summary_json`:

```json
{
  "issue_count_total": 0,
  "count_a": 0,
  "count_aa": 0,
  "count_aaa": 0,
  "weighted_issue_count": 0
}
```

### 7.3 Security headers

Adapter key:

- `security_headers`

`summary_json`:

```json
{
  "grade": "A",
  "headers_present": {
    "strict_transport_security": true,
    "content_security_policy": true,
    "x_frame_options": true,
    "x_content_type_options": true,
    "referrer_policy": true
  }
}
```

### 7.4 TLS / certificate

Adapter key:

- `tls_certificate`

`summary_json`:

```json
{
  "status": "valid",
  "expires_at": "",
  "days_to_expiry": 0
}
```

Allowed `status` values:

- `valid`
- `expiring_soon`
- `expired`
- `invalid`

### 7.5 Freshness

Adapter key:

- `freshness`

`summary_json`:

```json
{
  "first_archive_at": "",
  "latest_archive_at": "",
  "visible_latest_content_at": "",
  "footer_copyright_year": 2026,
  "estimated_changes_per_year": 0.0,
  "reference_content_at": ""
}
```

`reference_content_at` is the chosen date used for recency scoring after precedence rules are applied.

### 7.6 DOM heuristics

Adapter key:

- `dom_heuristics`

`summary_json`:

```json
{
  "has_viewport_meta": true,
  "viewport_meta_value": "width=device-width, initial-scale=1",
  "has_search": true,
  "search_bbox": {"x": 0.0, "y": 0.0, "width": 0.0, "height": 0.0},
  "has_contact_above_fold": false,
  "contact_bbox": null
}
```

Bounding boxes are normalized to `0.0-1.0` relative coordinates when available.

### 7.7 Wappalyzer

Adapter key:

- `wappalyzer`

`summary_json`:

```json
{
  "cms_name": "WordPress",
  "cms_version": "6.2.3",
  "platform_status": "supported_old",
  "frameworks": ["jQuery"],
  "hosting_provider": "Cloudflare",
  "analytics_tools": ["Google Analytics"],
  "has_accessibility_toolbar": false
}
```

Allowed `platform_status` values:

- `supported_current`
- `supported_old`
- `nearing_eol`
- `eol`
- `unknown_version`
- `modern_static`
- `unknown`

### 7.8 Screenshots

Screenshot capture is represented by `screenshots` rows plus one logical adapter key:

- `screenshots`

The adapter result should include the final URL, page title, and capture metadata in `summary_json`.

### 7.9 Vision

Adapter keys:

- `vision_desktop`
- `vision_mobile`

`summary_json`:

```json
{
  "dimensions": {
    "layout_modernity": {"score": 1, "rationale": ""},
    "typography_quality": {"score": 1, "rationale": ""},
    "hero_effectiveness": {"score": 1, "rationale": ""},
    "navigation_clarity": {"score": 1, "rationale": ""},
    "mobile_usability": {"score": 1, "rationale": ""},
    "footer_usability": {"score": 1, "rationale": ""},
    "visual_design_era": {"score": 1, "rationale": ""},
    "brand_coherence": {"score": 1, "rationale": ""}
  },
  "annotations": [
    {
      "annotation_id": "desktop-nav-1",
      "finding_hint": "confusing_navigation",
      "kind": "rect",
      "x": 0.0,
      "y": 0.0,
      "width": 0.0,
      "height": 0.0,
      "title": "",
      "caption": ""
    }
  ]
}
```

Vision scoring uses one prompt per screenshot and must return:

- all eight dimension scores
- one short rationale per dimension
- zero to three annotation candidates for visible issues in that viewport

If the response is invalid or incomplete:

- retry up to three times
- apply exponential backoff on `429`
- persist the final failure in `error_json`
- store a failed adapter result

---

## 8. Score Engine

### 8.1 Normalization helpers

All composite and dimension scores are **opportunity scores** where higher means more modernization need.

Helper functions:

```text
invert_quality(q) = clamp(100 - q, 0, 100)

vision_to_opportunity(s) = clamp(((10 - s) / 9) * 100, 0, 100)

header_grade_to_opportunity:
  A=0, B=20, C=40, D=60, E=80, F=100

tls_status_to_opportunity:
  valid=0
  expiring_soon=60
  expired=100
  invalid=100

binary_bad_to_opportunity:
  bad=100
  good=0
```

Pa11y normalization:

```text
weighted_issue_count = (3 * count_a) + (2 * count_aa) + (1 * count_aaa)
pa11y_opportunity = clamp(weighted_issue_count * 5, 0, 100)
```

Freshness normalization:

```text
days_stale = days_between(run_date, reference_content_at)

recency_to_opportunity:
  <= 90 days   -> 0
  <= 180 days  -> 25
  <= 365 days  -> 50
  <= 730 days  -> 75
  > 730 days   -> 100

change_frequency_to_opportunity:
  >= 12/year -> 0
  >= 6/year  -> 25
  >= 3/year  -> 50
  >= 1/year  -> 75
  < 1/year   -> 100

footer_year_to_opportunity:
  current year or previous year -> 0
  2 years old                   -> 50
  3+ years old                  -> 100
```

Technology platform normalization:

```text
platform_status_to_opportunity:
  supported_current -> 0
  supported_old     -> 35
  nearing_eol       -> 70
  eol               -> 100
  unknown_version   -> 40
  modern_static     -> 20
  unknown           -> missing
```

### 8.2 Input preparation

Prepared normalized inputs:

```text
desktop_perf_opp         = invert_quality(pagespeed_desktop.performance)
mobile_perf_opp          = invert_quality(pagespeed_mobile.performance)
desktop_access_opp       = invert_quality(pagespeed_desktop.accessibility)
mobile_access_opp        = invert_quality(pagespeed_mobile.accessibility)
desktop_seo_opp          = invert_quality(pagespeed_desktop.seo)
mobile_seo_opp           = invert_quality(pagespeed_mobile.seo)
pa11y_opp                = pa11y_opportunity
viewport_opp             = binary_bad_to_opportunity(has_viewport_meta is false)
headers_opp              = header_grade_to_opportunity(grade)
tls_opp                  = tls_status_to_opportunity(status)
freshness_recency_opp    = recency_to_opportunity(reference_content_at)
freshness_change_opp     = change_frequency_to_opportunity(estimated_changes_per_year)
freshness_footer_opp     = footer_year_to_opportunity(footer_copyright_year)
platform_opp             = platform_status_to_opportunity(platform_status)
vision_<dimension>_opp   = vision_to_opportunity(score)
```

### 8.3 Dimension formulas

Within each dimension, if one or more sub-signals are missing, renormalize the remaining subweights to sum to `1.0`.

#### Mobile usability (20%)

```text
0.45 * vision_mobile_usability_opp
0.25 * mobile_access_opp
0.15 * pa11y_opp
0.15 * viewport_opp
```

#### Accessibility (20%)

```text
0.60 * mobile_access_opp
0.20 * desktop_access_opp
0.20 * pa11y_opp
```

#### Technology stack modernity (15%)

```text
1.00 * platform_opp
```

If `platform_opp` is missing because the platform is truly unknown, the whole dimension is missing and its composite weight is renormalized away.

#### Performance (15%)

```text
0.67 * mobile_perf_opp
0.33 * desktop_perf_opp
```

#### Visual design era (10%)

```text
0.35 * vision_visual_design_era_opp
0.20 * vision_layout_modernity_opp
0.15 * vision_typography_quality_opp
0.15 * vision_hero_effectiveness_opp
0.10 * vision_brand_coherence_opp
0.05 * vision_navigation_clarity_opp
```

#### SEO fundamentals (10%)

```text
0.50 * mobile_seo_opp
0.35 * desktop_seo_opp
0.15 * viewport_opp
```

#### Security posture (5%)

```text
0.70 * headers_opp
0.30 * tls_opp
```

#### Content freshness (5%)

```text
0.60 * freshness_recency_opp
0.20 * freshness_change_opp
0.20 * freshness_footer_opp
```

### 8.4 Composite score

Composite weights:

| Dimension | Weight |
|---|---:|
| Mobile usability | 20 |
| Accessibility | 20 |
| Technology stack modernity | 15 |
| Performance | 15 |
| Visual design era | 10 |
| SEO fundamentals | 10 |
| Security posture | 5 |
| Content freshness | 5 |

Composite algorithm:

1. compute each dimension score and `source_coverage`
2. drop any dimension whose score is fully missing
3. renormalize the remaining dimension weights to sum to `100`
4. weighted-average the remaining dimension scores
5. round to one decimal place

`score_coverage` for the run is:

```text
sum(original composite weights for dimensions that produced a score) / 100
```

### 8.5 Priority tiers

Use the PRD thresholds without reinterpretation:

- Tier 1: `65.0-100.0`
- Tier 2: `40.0-64.9`
- Tier 3: `0.0-39.9`

### 8.6 Report scorecards

The report uses three top cards:

- `Overall opportunity score`
  - the composite score above
- `Desktop quality snapshot`
  - average of desktop PageSpeed `performance`, `accessibility`, `best_practices`, `seo`
- `Mobile quality snapshot`
  - average of mobile PageSpeed `performance`, `accessibility`, `best_practices`, `seo`

These are intentionally not all the same metric. Labels must make the distinction explicit.

---

## 9. Findings Engine

### 9.1 General rule

Findings are deterministic. Each finding rule defines:

- trigger condition
- severity
- framing tags
- effort label
- summary template
- resident-impact template
- municipality-impact template
- annotation preference

### 9.2 Initial v1 finding catalog

| Finding key | Trigger | Severity | Tags | Effort |
|---|---|---|---|---|
| `slow_mobile_experience` | performance >= 65 or mobile usability >= 65 | high | `resident_service`, `reputation`, `economic_development` | significant |
| `accessibility_barriers_high` | accessibility >= 65 or `count_a >= 5` | high | `legal`, `resident_service`, `reputation` | significant |
| `accessibility_barriers_moderate` | accessibility >= 40 and < 65 | medium | `legal`, `resident_service` | moderate |
| `outdated_platform_eol` | platform status = `eol` | high | `operational`, `financial`, `reputation` | significant |
| `outdated_platform_nearing_eol` | platform status = `nearing_eol` or `supported_old` | medium | `operational`, `financial` | moderate |
| `security_posture_weak` | security posture >= 60 or headers grade <= `D` | high | `legal`, `reputation`, `operational` | moderate |
| `certificate_expiring` | TLS status = `expiring_soon` | medium | `reputation`, `operational` | easy |
| `stale_content` | content freshness >= 60 | medium | `resident_service`, `reputation`, `economic_development` | moderate |
| `missing_viewport_meta` | `has_viewport_meta = false` | high | `resident_service`, `reputation` | easy |
| `no_search_detected` | `has_search = false` | low | `resident_service`, `operational` | moderate |
| `contact_hard_to_find` | `has_contact_above_fold = false` | medium | `resident_service`, `operational` | easy |
| `visual_design_outdated` | visual design era >= 60 | medium | `reputation`, `economic_development` | significant |
| `confusing_navigation` | vision navigation clarity >= 60 | medium | `resident_service`, `operational` | moderate |
| `weak_footer_usability` | vision footer usability >= 60 | low | `resident_service`, `operational` | easy |

The engine should emit at most:

- 6 findings per site
- 4 high or medium findings in the main report body
- all emitted findings in the JSON export and technical appendix

### 9.3 Finding selection order

When more than 6 rules trigger, keep findings by:

1. severity descending
2. dimension weight descending
3. opportunity score descending
4. stable finding key sort

### 9.4 Finding copy generation

Each finding contains three deterministic prose fragments:

- what was observed
- what it means for residents
- why it matters to the municipality

These are produced from templates using the normalized evidence values. Example:

- "The mobile experience scored in the high-opportunity range."
- "Residents on a phone may need more effort to find information or complete common tasks."
- "That can increase service friction, reduce trust, and make the site a weaker first impression."

### 9.5 Annotation linkage

Findings may link to zero or more annotations.

Preferred sources:

- `confusing_navigation`, `weak_footer_usability`, `visual_design_outdated`
  - vision annotations
- `no_search_detected`, `contact_hard_to_find`
  - DOM bounding boxes when available

Findings like `missing_viewport_meta` or `certificate_expiring` do not require overlay annotations.

---

## 10. Report Rendering Design

### 10.1 Required section order

The HTML report must render sections in this order:

1. Header
2. Plain-language summary
3. At-a-glance scorecards
4. Community impact findings
5. Visual evidence
6. Detailed scorecard
7. Recommended next steps
8. Technical appendix

### 10.2 Plain-language summary

The summary is deterministic in v1.

Construction:

1. opening sentence from tier:
   - Tier 1: strong modernization opportunity
   - Tier 2: meaningful improvement opportunity
   - Tier 3: comparatively current with targeted gaps
2. second sentence from top two findings
3. optional third sentence from score coverage or missing-data note

No AI prose generation is required for the initial implementation.

### 10.3 Visual evidence section

The report displays up to:

- 2 desktop annotations
- 2 mobile annotations

Selection algorithm:

1. collect annotation candidates linked to selected findings
2. sort by finding severity, then finding order
3. drop overlapping boxes with IoU greater than `0.6`
4. keep the first two per viewport

Renderer behavior:

- use normalized coordinates and absolute-position CSS overlays
- render a numbered marker plus a caption card
- if no annotations exist but screenshots are present, show screenshots without overlays and a "No visual callouts generated" note
- if screenshots are absent, show a section note explaining capture was skipped or failed

### 10.4 Detailed scorecard

Render one bar per composite dimension with:

- dimension label
- opportunity score
- source coverage badge if below `1.0`

### 10.5 Recommended next steps

Derive from the top three findings by severity and effort:

- easy before moderate before significant only when severity is tied
- otherwise severity wins

### 10.6 Technical appendix

Appendix includes:

- raw PageSpeed category scores
- Pa11y counts by level
- Wappalyzer platform summary
- security headers grade
- certificate status and expiry
- freshness evidence dates
- score coverage
- manual review reasons

### 10.7 PDF generation

PDF is generated from the rendered HTML with Playwright `page.pdf()`.

Requirements:

- print CSS only
- white background
- no clipped overlay captions
- page breaks before appendix when needed

---

## 11. Public JSON Export

### 11.1 One bundle per batch

Each batch writes one `catalog.json`.

Top-level shape:

```json
{
  "schema_version": "1.0",
  "batch": {},
  "artifacts": {},
  "sites": []
}
```

### 11.2 Batch object

```json
{
  "id": 1,
  "started_at": "",
  "finished_at": "",
  "status": "partial",
  "input_path": "catalog.csv",
  "output_dir": "2026-03-30T22-00-00Z",
  "flags": {
    "skip_vision": false,
    "skip_screenshots": false,
    "only_vision": false,
    "limit": null
  },
  "summary": {
    "site_count_total": 5,
    "site_count_complete": 4,
    "site_count_partial": 1,
    "site_count_failed": 0
  }
}
```

### 11.3 Site object

```json
{
  "site": {
    "id": 1,
    "url": "",
    "name": "",
    "region": "",
    "population": null,
    "tier_manual": null,
    "notes": null
  },
  "run": {
    "id": 10,
    "status": "complete",
    "started_at": "",
    "finished_at": "",
    "score_coverage": 1.0,
    "manual_review_reasons": []
  },
  "scores": {
    "overall_opportunity_score": 72.4,
    "priority_tier": "Tier 1",
    "dimensions": {
      "mobile_usability": {
        "opportunity_score": 80.0,
        "source_coverage": 1.0,
        "inputs": {}
      }
    },
    "desktop_quality_snapshot": 61.0,
    "mobile_quality_snapshot": 48.0
  },
  "findings": [],
  "screenshots": {
    "desktop": {"path": "screenshots/site/desktop.png"},
    "mobile": {"path": "screenshots/site/mobile.png"}
  },
  "reports": {
    "html": "reports/site.html",
    "pdf": "reports/site.pdf"
  },
  "adapters": {
    "pagespeed_desktop": {"status": "ok", "summary": {}},
    "pagespeed_mobile": {"status": "ok", "summary": {}},
    "pa11y": {"status": "ok", "summary": {}},
    "wappalyzer": {"status": "ok", "summary": {}},
    "security_headers": {"status": "ok", "summary": {}},
    "tls_certificate": {"status": "ok", "summary": {}},
    "freshness": {"status": "ok", "summary": {}},
    "dom_heuristics": {"status": "ok", "summary": {}},
    "vision_desktop": {"status": "ok", "summary": {}},
    "vision_mobile": {"status": "ok", "summary": {}}
  }
}
```

The JSON bundle is intended to be stable enough for a future local dashboard without requiring a redesign.

---

## 12. Failure Handling

### 12.1 Retry policy

- PageSpeed: 2 retries for transient HTTP failures
- OpenAI vision: 3 retries, exponential backoff on `429`
- Playwright screenshots: 1 retry after a fresh page load
- Pa11y: 1 retry after a fresh page load
- Wayback and simple HTTP checks: 2 retries

### 12.2 Recoverable failures

A failure is recoverable when the site can still produce a meaningful partial output. Examples:

- Pa11y fails but PageSpeed and screenshots succeed
- screenshots fail but technical audits succeed
- vision fails but screenshots and technical audits succeed
- Wappalyzer returns unknown platform

Recoverable failures result in:

- failed `adapter_results` rows
- manual review reasons appended to the run
- renormalized scoring
- `partial` run status only if the failed stage was requested by CLI

### 12.3 Site-fatal failures

A site run is `failed` when:

- URL is invalid or cannot be normalized
- `--only-vision` cannot find prior screenshots
- all composite dimensions are missing after stage execution
- report/export generation cannot produce minimum artifacts even after retries

### 12.4 Logging

`webgrade.log` must be line-oriented and include:

- timestamp
- batch id
- run id
- site slug
- stage
- level
- message

Errors stored in `error_json` should mirror the same information in structured form.

---

## 13. Implementation Order

Recommended order inside the codebase:

1. schema and repositories
2. CLI validation and batch/run lifecycle
3. PageSpeed, security, TLS, freshness, DOM, Wappalyzer adapters
4. screenshot and Pa11y adapters
5. vision adapter and annotation schema
6. scoring engine
7. findings engine
8. HTML renderer and PDF export
9. JSON and Excel exporters

This matches the implementation plan and preserves usable intermediate checkpoints.

---

## 14. Design Validation Checklist

The design is only acceptable if all of the following are true:

1. A normal full run has defined inputs, outputs, persistence, and failure behavior for every stage.
2. `--skip-screenshots`, `--skip-vision`, and `--only-vision` each have explicit read/write semantics.
3. The score engine has exact formulas for all dimensions, not just weight percentages.
4. Missing signals are handled by renormalization at both sub-dimension and composite levels.
5. The JSON bundle is stable and sufficient for a future local dashboard.
6. Report annotations have a concrete coordinate model and source.
7. Findings are deterministic and linked to stored evidence.
8. The design remains consistent with the PRD and `plan.md`.

---

## 15. Open Follow-Up Items

These items do not block implementation of v1, but they should be tracked explicitly:

- the curated platform support-status ruleset for CMS version mapping
- the exact prompt wording for the vision adapter
- optional future AI prose polish if introduced after the deterministic report path is complete
- pilot calibration of thresholds if real data suggests constants should be adjusted

The key point is that threshold tuning may change constants later, but the structure of the formulas and interfaces defined here should not change during v1 implementation.

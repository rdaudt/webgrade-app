# WebGrade - Product Requirements Document

**Version:** 0.2
**Date:** March 30, 2026
**Author:** [Your Name]
**Status:** In Progress

---

## Table of Contents

1. [Overview](#1-overview)
2. [Problem Statement](#2-problem-statement)
3. [Goals and Non-Goals](#3-goals-and-non-goals)
4. [User and Operator Context](#4-user-and-operator-context)
5. [System Architecture](#5-system-architecture)
6. [Functional Requirements](#6-functional-requirements)
   - 6.1 [Catalog Management](#61-catalog-management)
   - 6.2 [Automated Scoring Pipeline](#62-automated-scoring-pipeline)
   - 6.3 [AI Vision Scoring Layer](#63-ai-vision-scoring-layer)
   - 6.4 [Report Generation](#64-report-generation)
   - 6.5 [Output Artifacts](#65-output-artifacts)
   - 6.6 [CLI Interface](#66-cli-interface)
7. [Scoring Model](#7-scoring-model)
8. [Report Specification](#8-report-specification)
9. [Technical Stack](#9-technical-stack)
10. [Data Model](#10-data-model)
11. [Constraints and Assumptions](#11-constraints-and-assumptions)
12. [Out of Scope - v1](#12-out-of-scope---v1)
13. [Future Iterations](#13-future-iterations)
14. [Open Questions](#14-open-questions)

---

## 1. Overview

**WebGrade** is a command-line website audit engine that accepts a list of URLs, evaluates each site across a defined set of quality dimensions, and produces scored reports and catalogs. It is designed to support business development for a web modernization consulting practice by identifying and prioritizing prospective clients whose websites present significant modernization opportunities.

The v1 implementation targets **BC municipal websites** as the primary dataset, but the architecture is intentionally generic. Different website collections - health authority vendors, nonprofits, professional services firms - can be loaded via a collector interface or manual CSV input without changes to the core pipeline.

---

## 2. Problem Statement

Identifying and prioritizing prospective clients for a web modernization practice currently requires manual effort: visiting each website, noting problems, and making subjective judgments about severity. For a target market of 161 BC municipalities alone - let alone adjacent verticals - this is not scalable.

Beyond prospecting, the assessment itself needs to be communicated to decision-makers who are not technically literate. A raw Lighthouse score or a list of accessibility violations does not help a councillor, board member, or CAO. What lands is a plain-language explanation of impact on residents, legal exposure, and operational efficiency, backed by visual evidence.

WebGrade solves both problems: it automates the collection of technical evidence, and it transforms that evidence into audience-appropriate reports.

---

## 3. Goals and Non-Goals

### Goals

- Automatically assess any list of websites against a standardized multi-dimensional scoring model
- Produce a scored catalog in Excel and JSON enabling prioritization of prospective clients
- Generate individual site reports in HTML and PDF formats suitable for distribution to non-technical decision-makers
- Support both automated URL collection through a future collector interface and manual URL list input through CSV bypass
- Run as a solo-operator CLI tool with no server infrastructure required in v1
- Be **Windows-first**, local, and serverless in v1
- Keep **vision scoring required in v1** using GPT-5.4 through the OpenAI Responses API

### Non-Goals

- Real-time or continuous monitoring (v1 is on-demand only)
- Authentication or multi-user access control
- Automated outreach or CRM integration
- Scoring of sites requiring login or JavaScript-heavy SPAs that resist Playwright rendering
- Providing WCAG legal certification (reports are assessments, not formal audits)
- Shipping the local dashboard in v1; the **dashboard is deferred from v1**

---

## 4. User and Operator Context

**Primary operator:** Solo consultant running the tool on a local machine. The v1 runtime target is **Windows-first**, with local execution only and no required server components. The default developer and operator workflow uses a project-local Python virtual environment.

**Workflow:** The operator maintains a catalog CSV of target websites, triggers the pipeline via CLI, reviews the scored output, selects high-priority targets, and distributes individual HTML/PDF reports to prospective clients as part of a cold outreach or discovery conversation.

**Report recipients:** Municipal councillors, CAOs, nonprofit board members, or equivalent decision-makers. These are non-technical people who understand community service delivery, legal obligations, and budget constraints. They do not understand web technology acronyms.

---

## 5. System Architecture

The pipeline has five sequential layers:

```text
[1] Catalog Layer
    Input: CSV/DB of sites (manual input in v1; collector interface stubbed)
            ->
[2] Technical Audit Layer (fully automated)
    Lighthouse / PageSpeed API, Pa11y,
    Wappalyzer, security headers, Wayback Machine CDX,
    freshness/date scraping, DOM heuristics
            ->
[3] Screenshot Capture Layer (automated via Playwright)
    Desktop (1280x800) and mobile (375x812) screenshots
            ->
[4] AI Vision Scoring Layer (GPT-5.4 via OpenAI Responses API)
    Structured screenshot scoring for layout, typography,
    navigation, mobile usability, footer usability,
    visual design era, and brand coherence
            ->
[5] Report and Output Layer
    Scored catalog (Excel/JSON), per-site HTML report,
    PDF export
```

Each layer writes its results to a persistent SQLite store keyed by URL and run timestamp, enabling incremental re-runs such as re-running only the vision layer without re-running Lighthouse.

---

## 6. Functional Requirements

### 6.1 Catalog Management

**FR-1.1 - CSV input:**  
The pipeline shall accept a CSV file as input containing at minimum one column: `url`. Additional columns (`name`, `region`, `population`, `tier`, `notes`) are optional metadata that pass through to output artifacts.

**FR-1.2 - Manual bypass:**  
When a CSV is provided, the pipeline shall skip any automated URL collection step entirely and proceed directly to the audit layer. This enables the tool to be used against any arbitrary list of websites, not only BC municipalities.

**FR-1.3 - Collector interface stub for v1:**  
The architecture shall define a collector interface, such as a Python abstract base class, that v1 stubs out but does not implement concretely. Future collectors shall produce CSV-compatible output that feeds the pipeline without modification.

**FR-1.4 - Catalog persistence:**  
All assessed sites, their metadata, and run results shall be stored in SQLite. Multiple runs against the same URL shall be stored with timestamps, enabling future trend analysis and selective re-runs.

### 6.2 Automated Scoring Pipeline

The following checks shall run fully automatically per URL, with no human interaction required.

**FR-2.1 - Lighthouse / PageSpeed Insights API:**  
Run via the Google PageSpeed Insights API. Collect scores for Performance, Accessibility, Best Practices, and SEO. Capture both desktop and mobile variants. Store raw scores (0-100) and category-level sub-scores.

**FR-2.2 - Accessibility scan:**  
Run Pa11y in headless mode against each URL. Record total violation count and breakdown by WCAG level (A, AA, AAA). Pa11y is preferred over axe-core CLI for its ease of integration with Playwright-rendered pages.

**FR-2.3 - Technology fingerprinting:**  
Use the Wappalyzer Node.js library in offline mode to detect CMS platform and version, JavaScript frameworks, hosting provider, analytics tools, and accessibility toolbar presence. Flag sites running CMS versions with known end-of-life dates.

**FR-2.4 - Security headers:**  
Use direct header inspection via `httpx` to check for `Strict-Transport-Security`, `Content-Security-Policy`, `X-Frame-Options`, `X-Content-Type-Options`, and `Referrer-Policy`. Assign a letter grade A-F for security header posture only.

**FR-2.5 - SSL certificate validity and expiry:**  
Use direct TLS inspection via Python `ssl` to verify certificate validity and expiry date. Flag certificates that are invalid, expired, or expiring within 60 days. No third-party SSL grade is required in v1; the rule is **SSL validity/expiry only**.

**FR-2.6 - Content freshness:**  
Use the Wayback Machine CDX API to determine date of first archive, date of most recent archive, and approximate change frequency. Also scrape visible copyright year from the footer and the most recent visible date in news or events sections when present.

**FR-2.7 - Mobile viewport meta tag:**  
Scrape the `<meta name="viewport">` tag presence and value. Absence or clearly incorrect value is a hard flag.

**FR-2.8 - Search functionality:**  
Detect presence of a search input element (`<input type="search">`) or common search widget patterns on the homepage.

**FR-2.9 - Contact information prominence:**  
Detect whether a phone number and/or address appear in the top 25% of the rendered page DOM as an above-the-fold proxy, not only in the footer.

### 6.3 AI Vision Scoring Layer

**FR-3.1 - Screenshot capture:**  
Use Playwright (Python) to capture full-page screenshots at two viewports per site:
- Desktop: 1280x800, full-page PNG
- Mobile: 375x812, full-page PNG

Screenshots shall be stored locally in a `screenshots/` directory keyed by URL slug and run date.

**FR-3.2 - GPT-5.4 vision scoring:**  
Submit each screenshot to GPT-5.4 via the OpenAI Responses API. Use full-resolution image input and request structured JSON output suitable for programmatic parsing and score storage.

**FR-3.3 - Vision scoring dimensions:**  
The vision prompt shall request scores (1-10) and a brief plain-language rationale for each of the following dimensions:

| Dimension | What is being assessed |
|---|---|
| `layout_modernity` | Fixed-width vs. fluid, use of modern grid/flex patterns, visual hierarchy |
| `typography_quality` | Font choices, size hierarchy, readability, line length |
| `hero_effectiveness` | Above-fold impact, call-to-action clarity, image quality |
| `navigation_clarity` | Menu organization, number of nav systems, clarity of wayfinding |
| `mobile_usability` | Touch target sizing, content prioritization, scrolling burden |
| `footer_usability` | Contact info accessibility, density, scannability |
| `visual_design_era` | Overall design vintage or design-language age |
| `brand_coherence` | Whether the site feels like a unified design system or assembled pieces |

**FR-3.4 - Reasoning effort:**  
Use `reasoning={"effort": "high"}` for the vision scoring call.

**FR-3.5 - Rate limiting:**  
Implement a configurable delay between vision API calls, defaulting to 2 seconds, to reduce rate limit risk. Implement exponential backoff on `429` responses.

**FR-3.6 - Vision score fallback:**  
If the vision API call fails after 3 retries, mark all vision dimensions as `null`, flag the site for manual review, and still include the site in all outputs with technical scores intact.

### 6.4 Report Generation

**FR-4.1 - Report audience:**  
All report copy, including findings, impact statements, and recommendations, shall be written in plain language accessible to a non-technical reader. Technical terms shall not appear in the main body of the report. If technical terms appear in an appendix, they shall include plain-language definitions.

**FR-4.2 - Report structure:**  
Each per-site report shall contain the following sections, in order:

1. **Header** - Site name, URL, date of assessment, assessor name
2. **Plain-language summary** - 2-4 sentences answering: "Is this website doing its job for the community?"
3. **At-a-glance scorecards** - Overall score, desktop score, mobile score shown as readable metric cards
4. **Community impact findings** - For each finding: what was observed -> what it means for residents -> why it matters to the municipality -> effort to fix
5. **Visual evidence** - Annotated desktop and mobile screenshots with plain-language callouts
6. **Detailed scorecard** - Bar chart visualization of all scoring dimensions, including desktop vs. mobile where applicable
7. **Recommended next steps** - Prioritized action list in plain language
8. **Technical appendix** - Raw scores, violation counts, technology stack, and supporting technical notes

**FR-4.3 - Reasons to act:**  
Every finding that identifies an opportunity for improvement shall include at least one reason to act drawn from: legal/compliance risk, resident service impact, staff operational efficiency, community reputation, economic development, or grant eligibility.

**FR-4.4 - Report tone:**  
The report shall be respectful and constructive throughout. It shall not position the municipality negatively. The framing shall be opportunity-oriented rather than failure-oriented.

### 6.5 Output Artifacts

**FR-5.1 - Per-site HTML report:**  
A self-contained single-file HTML report per assessed site, matching the design and structure defined in FR-4.2. It must render correctly in a modern browser without external dependencies.

**FR-5.2 - Per-site PDF report:**  
A PDF export of the HTML report generated via Playwright `page.pdf()`. It shall support A4 or Letter format and use print-friendly styling.

**FR-5.3 - Scored catalog (Excel):**  
A single Excel workbook containing all assessed sites with one row per site. Columns include raw scores, dimension sub-scores, composite opportunity score, priority tier, technology stack summary, recommended action, and date assessed.

**FR-5.4 - Scored catalog (JSON):**  
A machine-readable JSON export containing all assessed sites, score breakdowns, findings, and output file references. This is an explicit v1 artifact. **JSON export is included in v1** to support future dashboard and automation work without making the dashboard itself a v1 deliverable.

### 6.6 CLI Interface

**FR-6.1 - Entry point:**  
The tool shall be invoked as:

```bash
python -m webgrade run --input catalog.csv [OPTIONS]
```

**FR-6.2 - Core options:**

| Option | Description |
|---|---|
| `--input FILE` | Path to input CSV. Required unless `--site` is used. |
| `--output DIR` | Output directory for all artifacts. Default: `./webgrade-output/` |
| `--limit N` | Process only the first N rows for testing. |
| `--skip-vision` | Skip GPT-5.4 vision scoring and run only the non-vision pipeline. |
| `--skip-screenshots` | Skip Playwright screenshot capture. |
| `--only-vision` | Re-run only the vision layer using existing screenshots and stored technical results. |
| `--site URL` | Run against a single URL only. |
| `--report-name STR` | Override the site name shown in the report header. |

**FR-6.3 - Progress output:**  
The CLI shall display a progress bar via `tqdm` showing current site, current layer, and estimated time remaining. Per-site errors shall be logged without stopping the overall run.

**FR-6.4 - Run summary:**  
On completion, the CLI shall print a summary containing total sites processed, sites with errors, top 5 priority targets by composite opportunity score, and the output directory path.

---

## 7. Scoring Model

### Composite Score

The composite score is a weighted average of dimension scores normalized to 0-100. It is an **opportunity score**, meaning a higher score indicates greater modernization need. This meaning shall be explicit in all outputs.

### Dimension Weights

| Dimension | Weight | Primary Data Source |
|---|---|---|
| Mobile usability | 20% | Lighthouse mobile + Pa11y + GPT-5.4 vision |
| Accessibility (WCAG) | 20% | Lighthouse accessibility + Pa11y violation count |
| Technology stack modernity | 15% | Wappalyzer (CMS age, EOL status) |
| Performance | 15% | Lighthouse performance, with mobile weighted more heavily than desktop |
| Visual design era | 10% | GPT-5.4 vision |
| SEO fundamentals | 10% | Lighthouse SEO + meta tag checks |
| Security posture | 5% | Security headers grade + SSL validity/expiry checks |
| Content freshness | 5% | Wayback CDX + visible date scraping |

### Priority Tiers

| Tier | Score Range | Meaning |
|---|---|---|
| Tier 1 - High Priority | 65-100 | Significant modernization opportunity; strong sales case |
| Tier 2 - Medium Priority | 40-64 | Meaningful gaps; worth pursuing |
| Tier 3 - Monitor | 0-39 | Site is reasonably current; revisit later |

### Score Inversion Note

Raw Lighthouse, Pa11y, and other quality scores are quality signals where higher is better. The pipeline inverts or normalizes those inputs before computing the composite opportunity score. The technical appendix shall show both the raw quality value and the resulting opportunity contribution when applicable.

---

## 8. Report Specification

### Language Rules

- No acronyms without plain-language expansion on first use
- Sentences should remain concise and easy to read
- Use active voice throughout
- Prefer concrete numbers over vague qualifiers
- Tone: helpful neighbour, not auditor

### Opportunity Framing Categories

Every finding shall be tagged with one or more of the following framing categories, which drive the "why it matters" copy:

| Tag | Framing Angle |
|---|---|
| `legal` | Compliance risk under the Accessible BC Act or related obligations |
| `resident_service` | Direct impact on a resident's ability to access information or services |
| `operational` | Staff time savings or call-volume reduction |
| `reputation` | Community image and first impressions for newcomers or businesses |
| `financial` | Grant eligibility or the cost of reactive vs. proactive remediation |
| `economic_development` | Attracting residents, businesses, or tourism |

### Effort Levels

| Label | Meaning |
|---|---|
| Easy | Can be addressed by a content editor or a small targeted fix |
| Moderate | Requires a developer or platform configuration change |
| Significant | Requires structural changes or a full redesign |

---

## 9. Technical Stack

| Component | Technology | Notes |
|---|---|---|
| Language | Python 3.11+ | Primary pipeline language, run from a project-local virtual environment |
| Browser automation | Playwright (Python) | Screenshot capture and PDF export |
| Accessibility scanning | Pa11y (Node.js via subprocess) | WCAG 2.1 A/AA/AAA violation counts |
| Performance scoring | Google PageSpeed Insights API | Desktop and mobile scoring |
| Technology fingerprinting | Wappalyzer (Node.js library) | Offline mode, no API key |
| AI vision scoring | OpenAI GPT-5.4 via Responses API | Structured screenshot scoring; vision scoring required in v1 |
| Data persistence | SQLite via Python `sqlite3` | Single-file database, no server |
| Excel output | `openpyxl` | Scored catalog workbook |
| JSON output | Python standard library or equivalent | Public machine-readable export |
| PDF export | Playwright `page.pdf()` | Generated from rendered HTML reports |
| Progress display | `tqdm` | CLI progress bars |
| HTTP client | `httpx` | Header inspection and network checks |
| Environment config | `python-dotenv` | API keys loaded from `.env` |

### Environment Variables Required

```text
OPENAI_API_KEY=sk-...
PAGESPEED_API_KEY=...    # Optional; increases rate limits
```

---

## 10. Data Model

### SQLite Tables

**`sites`**

```text
id              INTEGER PRIMARY KEY
url             TEXT UNIQUE
name            TEXT
region          TEXT
population      INTEGER
tier_manual     TEXT
notes           TEXT
created_at      DATETIME
```

**`runs`**

```text
id              INTEGER PRIMARY KEY
site_id         INTEGER REFERENCES sites(id)
run_date        DATETIME
status          TEXT  -- complete | partial | failed
duration_secs   INTEGER
```

**`scores`**

```text
id                  INTEGER PRIMARY KEY
run_id              INTEGER REFERENCES runs(id)
dimension           TEXT
raw_value           REAL
opportunity_score   REAL
viewport            TEXT  -- desktop | mobile | combined
source              TEXT  -- lighthouse | pa11y | wappalyzer | gpt54 | scrape
```

**`findings`**

```text
id              INTEGER PRIMARY KEY
run_id          INTEGER REFERENCES runs(id)
finding_key     TEXT
severity        TEXT  -- high | medium | low
plain_text      TEXT
framing_tags    TEXT  -- comma-separated
effort          TEXT  -- easy | moderate | significant
raw_evidence    TEXT  -- JSON blob of supporting data
```

**`screenshots`**

```text
id              INTEGER PRIMARY KEY
run_id          INTEGER REFERENCES runs(id)
viewport        TEXT
file_path       TEXT
captured_at     DATETIME
```

---

## 11. Constraints and Assumptions

- The pipeline runs on a single machine; no distributed processing is required for the target catalog size
- The v1 operator environment is Windows-first
- The expected local Python workflow uses a project-local virtual environment such as `.venv`
- Sites are publicly accessible without authentication
- Playwright can render the pages, though some JavaScript-heavy sites may still require partial scoring
- GPT-5.4 vision API access is available and funded by the operator
- The Google PageSpeed Insights API quota is sufficient for expected v1 usage
- The tool is not intended for real-time use; a full catalog run may take 30-60 minutes
- Output reports are intended for human review and distribution, not automated sending

---

## 12. Out of Scope - v1

The following are explicitly deferred to future iterations:

- Scheduled or automated recurring runs
- Email or CRM integration for report delivery
- Multi-user access, authentication, or role-based permissions
- Web-hosted server-side deployment of the pipeline
- Concrete collector implementations or scrapers
- Trend-analysis UI across multiple runs
- The local file-based dashboard; the dashboard is deferred from v1
- Scoring of authenticated or login-gated pages
- Languages other than English in report output
- Custom scoring weight configuration via CLI

---

## 13. Future Iterations

### v1.1 - Collector Modules

- Implement the first concrete collectors
- Add URL verification and enrichment workflows before running the audit pipeline

### v1.2 - Local Dashboard and Incremental Runs

- Build the local `file://` dashboard that consumes the v1 JSON export
- Add quarterly refresh mode and selective re-run workflows
- Add delta detection across prior runs

### v1.3 - Vertical Expansion

- Add catalog presets for BC nonprofits, health-funded societies, and professional services firms
- Add vertical-specific finding copy for non-municipal audiences

### v1.4 - Outreach Integration

- Add CRM export formats for downstream outreach tools
- Add report-delivery tracking if the product direction still supports it

### v2.0 - Web Application

- Replace the CLI-first experience with a browser-based application
- Add multi-tenant support for consultant licensing
- Add API endpoints for triggering runs programmatically

---

## 14. Open Questions

| # | Question | Owner | Target Resolution |
|---|---|---|---|
| 1 | What is the expected cost per site for GPT-5.4 vision calls across two screenshots and eight scored dimensions? | Operator | Before first full catalog run |
| 2 | Does Pa11y require a full Playwright render for the target municipal sites, or can some checks run against simpler page loads? | Developer | During technical spike |
| 3 | What exact normalization and missing-data rules should drive the final composite opportunity score? | Operator + Developer | Before v1 scoring calibration |
| 4 | Should reports eventually include a modernization budget estimate, or is that better left outside v1 reporting? | Operator | Before first external report distribution |

---

*This document reflects the current working specification for WebGrade v1. It treats Windows-first local execution, JSON export included in v1, dashboard deferred from v1, vision scoring required in v1, and SSL validity/expiry only as the active scope decisions.*

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS batches (
    id INTEGER PRIMARY KEY,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    input_path TEXT,
    output_dir TEXT NOT NULL,
    flags_json TEXT NOT NULL,
    site_count_total INTEGER NOT NULL DEFAULT 0,
    site_count_complete INTEGER NOT NULL DEFAULT 0,
    site_count_partial INTEGER NOT NULL DEFAULT 0,
    site_count_failed INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sites (
    id INTEGER PRIMARY KEY,
    url TEXT NOT NULL UNIQUE,
    name TEXT,
    region TEXT,
    population INTEGER,
    tier_manual TEXT,
    notes TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY,
    batch_id INTEGER NOT NULL REFERENCES batches(id),
    site_id INTEGER NOT NULL REFERENCES sites(id),
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    report_name_override TEXT,
    source_run_id INTEGER REFERENCES runs(id),
    score_coverage REAL NOT NULL DEFAULT 0.0,
    manual_review_json TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS adapter_results (
    id INTEGER PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES runs(id),
    adapter_key TEXT NOT NULL,
    viewport TEXT,
    status TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    summary_json TEXT NOT NULL DEFAULT '{}',
    raw_json TEXT NOT NULL DEFAULT '{}',
    error_json TEXT,
    copied_from_result_id INTEGER REFERENCES adapter_results(id)
);

CREATE TABLE IF NOT EXISTS scores (
    id INTEGER PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES runs(id),
    dimension TEXT NOT NULL,
    raw_value REAL,
    opportunity_score REAL NOT NULL,
    source_coverage REAL NOT NULL DEFAULT 0.0,
    viewport TEXT NOT NULL,
    source TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS findings (
    id INTEGER PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES runs(id),
    finding_key TEXT NOT NULL,
    severity TEXT NOT NULL,
    plain_text TEXT NOT NULL,
    framing_tags TEXT NOT NULL,
    effort TEXT NOT NULL,
    raw_evidence TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS screenshots (
    id INTEGER PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES runs(id),
    viewport TEXT NOT NULL,
    file_path TEXT NOT NULL,
    captured_at TEXT NOT NULL,
    status TEXT NOT NULL,
    source_run_id INTEGER REFERENCES runs(id),
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS artifacts (
    id INTEGER PRIMARY KEY,
    run_id INTEGER REFERENCES runs(id),
    batch_id INTEGER REFERENCES batches(id),
    artifact_type TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

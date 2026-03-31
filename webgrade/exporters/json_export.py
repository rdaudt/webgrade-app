from __future__ import annotations

import json
from pathlib import Path

from webgrade.db import Database


def export_catalog_json(db: Database, batch_id: int, batch_dir: Path) -> Path:
    batch = db.get_batch(batch_id)
    runs = db.list_batch_runs(batch_id)
    artifacts = db.list_batch_artifacts(batch_id)

    site_items: list[dict[str, object]] = []
    for run in runs:
        site_items.append(
            {
                "site": {
                    "id": run["site_id"],
                    "url": run["url"],
                    "name": run["name"],
                    "region": run["region"],
                    "population": run["population"],
                    "tier_manual": run["tier_manual"],
                    "notes": run["notes"],
                },
                "run": {
                    "id": run["id"],
                    "status": run["status"],
                    "started_at": run["started_at"],
                    "finished_at": run["finished_at"],
                    "score_coverage": run["score_coverage"],
                    "report_name_override": run["report_name_override"],
                    "manual_review_reasons": json.loads(run["manual_review_json"]),
                },
                "scores": {
                    "overall_opportunity_score": None,
                    "priority_tier": None,
                    "dimensions": {},
                    "desktop_quality_snapshot": None,
                    "mobile_quality_snapshot": None,
                },
                "findings": [],
                "screenshots": {
                    "desktop": None,
                    "mobile": None,
                },
                "reports": {
                    "html": None,
                    "pdf": None,
                },
                "adapters": {},
            }
        )

    payload = {
        "schema_version": "1.0",
        "batch": {
            "id": batch["id"],
            "started_at": batch["started_at"],
            "finished_at": batch["finished_at"],
            "status": batch["status"],
            "input_path": batch["input_path"],
            "output_dir": batch["output_dir"],
            "flags": json.loads(batch["flags_json"]),
            "summary": {
                "site_count_total": batch["site_count_total"],
                "site_count_complete": batch["site_count_complete"],
                "site_count_partial": batch["site_count_partial"],
                "site_count_failed": batch["site_count_failed"],
            },
        },
        "artifacts": [
            {
                "artifact_type": row["artifact_type"],
                "relative_path": row["relative_path"],
            }
            for row in artifacts
        ],
        "sites": site_items,
    }

    json_path = batch_dir / "catalog.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return json_path

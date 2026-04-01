from __future__ import annotations

import json
from pathlib import Path

from webgrade.db import Database


COMPOSITE_DIMENSIONS = {
    "mobile_usability",
    "accessibility",
    "technology_stack_modernity",
    "performance",
    "visual_design_era",
    "seo_fundamentals",
    "security_posture",
    "content_freshness",
}


def export_catalog_json(
    db: Database,
    batch_id: int,
    batch_dir: Path,
    review_summary: dict[str, object] | None = None,
) -> Path:
    batch = db.get_batch(batch_id)
    runs = db.list_batch_runs(batch_id)
    artifacts = db.list_batch_artifacts(batch_id)

    site_items: list[dict[str, object]] = []
    for run in runs:
        adapter_rows = db.list_run_adapter_results(run["id"])
        adapter_payload = {
            row["adapter_key"]: {
                "status": row["status"],
                "viewport": row["viewport"],
                "summary": json.loads(row["summary_json"]),
                "error": json.loads(row["error_json"]) if row["error_json"] else None,
            }
            for row in adapter_rows
        }
        score_rows = db.list_run_scores(run["id"])
        findings_rows = db.list_run_findings(run["id"])
        screenshot_rows = db.list_run_screenshots(run["id"])
        run_artifacts = db.list_run_artifacts(run["id"])
        score_map = {
            row["dimension"]: {
                "opportunity_score": row["opportunity_score"],
                "source_coverage": row["source_coverage"],
            }
            for row in score_rows
            if row["dimension"] in COMPOSITE_DIMENSIONS
        }
        overall_score = next((row["opportunity_score"] for row in score_rows if row["dimension"] == "overall_opportunity_score"), None)
        priority_tier = None
        desktop_snapshot = None
        mobile_snapshot = None
        for row in score_rows:
            if row["dimension"] == "priority_tier":
                priority_tier = row["source"]
            elif row["dimension"] == "desktop_quality_snapshot":
                desktop_snapshot = row["opportunity_score"]
            elif row["dimension"] == "mobile_quality_snapshot":
                mobile_snapshot = row["opportunity_score"]
        report_map = {
            row["artifact_type"]: row["relative_path"]
            for row in run_artifacts
            if row["artifact_type"] in {"html_report", "pdf_report"}
        }
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
                    "context": json.loads(run["context_summary_json"]),
                    "manual_review_reasons": json.loads(run["manual_review_json"]),
                },
                "scores": {
                    "overall_opportunity_score": overall_score,
                    "priority_tier": priority_tier,
                    "dimensions": score_map,
                    "desktop_quality_snapshot": desktop_snapshot,
                    "mobile_quality_snapshot": mobile_snapshot,
                },
                "findings": [
                    {
                        "finding_key": row["finding_key"],
                        "severity": row["severity"],
                        "plain_text": row["plain_text"],
                        "framing_tags": json.loads(row["framing_tags"]),
                        "effort": row["effort"],
                        "raw_evidence": json.loads(row["raw_evidence"]),
                    }
                    for row in findings_rows
                ],
                "screenshots": {
                    "desktop": next((row["file_path"] for row in screenshot_rows if row["viewport"] == "desktop"), None),
                    "mobile": next((row["file_path"] for row in screenshot_rows if row["viewport"] == "mobile"), None),
                    "items": [
                        {
                            "viewport": row["viewport"],
                            "relative_path": row["file_path"],
                            "status": row["status"],
                            "metadata": json.loads(row["metadata_json"]),
                        }
                        for row in screenshot_rows
                    ],
                },
                "reports": {
                    "html": report_map.get("html_report"),
                    "pdf": report_map.get("pdf_report"),
                },
                "adapters": adapter_payload,
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
            "context": json.loads(batch["context_summary_json"]),
            "summary": {
                "site_count_total": batch["site_count_total"],
                "site_count_complete": batch["site_count_complete"],
                "site_count_partial": batch["site_count_partial"],
                "site_count_failed": batch["site_count_failed"],
            },
            "review_summary": review_summary or {},
        },
        "artifacts": [
            {
                "artifact_type": row["artifact_type"],
                "relative_path": row["relative_path"],
                "metadata": json.loads(row["metadata_json"]),
            }
            for row in artifacts
        ],
        "sites": site_items,
    }

    json_path = batch_dir / "catalog.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return json_path

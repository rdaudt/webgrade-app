from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

from webgrade.db import Database


def export_catalog_excel(db: Database, batch_id: int, batch_dir: Path) -> Path:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Catalog"
    sheet.append(
        [
            "url",
            "name",
            "region",
            "population",
            "tier_manual",
            "run_status",
            "score_coverage",
            "overall_opportunity_score",
            "priority_tier",
            "desktop_quality_snapshot",
            "mobile_quality_snapshot",
            "report_name_override",
            "top_finding",
            "html_report",
            "pdf_report",
            "notes",
        ]
    )

    for row in db.list_batch_runs(batch_id):
        scores = db.list_run_scores(row["id"])
        score_lookup = {score["dimension"]: score for score in scores}
        findings = db.list_run_findings(row["id"])
        artifacts = db.list_run_artifacts(row["id"])
        html_report = next((artifact["relative_path"] for artifact in artifacts if artifact["artifact_type"] == "html_report"), None)
        pdf_report = next((artifact["relative_path"] for artifact in artifacts if artifact["artifact_type"] == "pdf_report"), None)
        sheet.append(
            [
                row["url"],
                row["name"],
                row["region"],
                row["population"],
                row["tier_manual"],
                row["status"],
                row["score_coverage"],
                score_lookup["overall_opportunity_score"]["opportunity_score"] if "overall_opportunity_score" in score_lookup else None,
                score_lookup["priority_tier"]["source"] if "priority_tier" in score_lookup else None,
                score_lookup["desktop_quality_snapshot"]["opportunity_score"] if "desktop_quality_snapshot" in score_lookup else None,
                score_lookup["mobile_quality_snapshot"]["opportunity_score"] if "mobile_quality_snapshot" in score_lookup else None,
                row["report_name_override"],
                findings[0]["plain_text"] if findings else None,
                html_report,
                pdf_report,
                row["notes"],
            ]
        )

    excel_path = batch_dir / "catalog.xlsx"
    workbook.save(excel_path)
    return excel_path

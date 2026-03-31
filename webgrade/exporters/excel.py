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
            "report_name_override",
            "notes",
        ]
    )

    for row in db.list_batch_runs(batch_id):
        sheet.append(
            [
                row["url"],
                row["name"],
                row["region"],
                row["population"],
                row["tier_manual"],
                row["status"],
                row["score_coverage"],
                row["report_name_override"],
                row["notes"],
            ]
        )

    excel_path = batch_dir / "catalog.xlsx"
    workbook.save(excel_path)
    return excel_path

from __future__ import annotations

from contextlib import closing
from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3
from typing import Any

from webgrade.types import CatalogSite


def _utc_now() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat()


class Database:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row

    def close(self) -> None:
        self.connection.close()

    def initialize(self) -> None:
        schema_path = Path(__file__).with_name("schema.sql")
        with schema_path.open("r", encoding="utf-8") as handle:
            self.connection.executescript(handle.read())
        self.connection.commit()

    def upsert_site(self, site: CatalogSite) -> int:
        existing = self.connection.execute(
            "SELECT id FROM sites WHERE url = ?",
            (site.url,),
        ).fetchone()
        if existing:
            self.connection.execute(
                """
                UPDATE sites
                SET name = COALESCE(?, name),
                    region = COALESCE(?, region),
                    population = COALESCE(?, population),
                    tier_manual = COALESCE(?, tier_manual),
                    notes = COALESCE(?, notes)
                WHERE id = ?
                """,
                (site.name, site.region, site.population, site.tier, site.notes, existing["id"]),
            )
            self.connection.commit()
            return int(existing["id"])

        cursor = self.connection.execute(
            """
            INSERT INTO sites (url, name, region, population, tier_manual, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (site.url, site.name, site.region, site.population, site.tier, site.notes, _utc_now()),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def create_batch(self, input_path: str | None, output_dir: str, flags: dict[str, Any], site_count_total: int) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO batches (
                started_at, status, input_path, output_dir, flags_json, site_count_total
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (_utc_now(), "partial", input_path, output_dir, json.dumps(flags, sort_keys=True), site_count_total),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def finalize_batch(self, batch_id: int, status: str, counts: dict[str, int]) -> None:
        self.connection.execute(
            """
            UPDATE batches
            SET finished_at = ?,
                status = ?,
                site_count_complete = ?,
                site_count_partial = ?,
                site_count_failed = ?
            WHERE id = ?
            """,
            (
                _utc_now(),
                status,
                counts.get("complete", 0),
                counts.get("partial", 0),
                counts.get("failed", 0),
                batch_id,
            ),
        )
        self.connection.commit()

    def create_run(self, batch_id: int, site_id: int, report_name_override: str | None = None, source_run_id: int | None = None) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO runs (
                batch_id, site_id, started_at, status, report_name_override, source_run_id, score_coverage, manual_review_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (batch_id, site_id, _utc_now(), "partial", report_name_override, source_run_id, 0.0, "[]"),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def finalize_run(self, run_id: int, status: str, score_coverage: float, manual_review_reasons: list[str]) -> None:
        self.connection.execute(
            """
            UPDATE runs
            SET finished_at = ?,
                status = ?,
                score_coverage = ?,
                manual_review_json = ?
            WHERE id = ?
            """,
            (_utc_now(), status, score_coverage, json.dumps(manual_review_reasons), run_id),
        )
        self.connection.commit()

    def add_adapter_result(
        self,
        run_id: int,
        adapter_key: str,
        viewport: str | None,
        status: str,
        summary: dict[str, Any],
        raw: dict[str, Any],
        error: dict[str, Any] | None = None,
        copied_from_result_id: int | None = None,
    ) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO adapter_results (
                run_id, adapter_key, viewport, status, started_at, finished_at,
                summary_json, raw_json, error_json, copied_from_result_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                adapter_key,
                viewport,
                status,
                _utc_now(),
                _utc_now(),
                json.dumps(summary, sort_keys=True),
                json.dumps(raw, sort_keys=True),
                json.dumps(error, sort_keys=True) if error is not None else None,
                copied_from_result_id,
            ),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def replace_run_scores(
        self,
        run_id: int,
        scores: list[dict[str, Any]],
    ) -> None:
        self.connection.execute("DELETE FROM scores WHERE run_id = ?", (run_id,))
        self.connection.executemany(
            """
            INSERT INTO scores (run_id, dimension, raw_value, opportunity_score, source_coverage, viewport, source)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    run_id,
                    item["dimension"],
                    item.get("raw_value"),
                    item["opportunity_score"],
                    item["source_coverage"],
                    item["viewport"],
                    item["source"],
                )
                for item in scores
            ],
        )
        self.connection.commit()

    def replace_run_findings(self, run_id: int, findings: list[dict[str, Any]]) -> None:
        self.connection.execute("DELETE FROM findings WHERE run_id = ?", (run_id,))
        self.connection.executemany(
            """
            INSERT INTO findings (run_id, finding_key, severity, plain_text, framing_tags, effort, raw_evidence)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    run_id,
                    item["finding_key"],
                    item["severity"],
                    item["plain_text"],
                    json.dumps(item["framing_tags"], sort_keys=True),
                    item["effort"],
                    json.dumps(item["raw_evidence"], sort_keys=True),
                )
                for item in findings
            ],
        )
        self.connection.commit()

    def add_screenshot(
        self,
        run_id: int,
        viewport: str,
        file_path: str,
        status: str,
        metadata: dict[str, Any] | None = None,
        source_run_id: int | None = None,
    ) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO screenshots (run_id, viewport, file_path, captured_at, status, source_run_id, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                viewport,
                file_path,
                _utc_now(),
                status,
                source_run_id,
                json.dumps(metadata or {}, sort_keys=True),
            ),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def add_artifact(self, batch_id: int | None, run_id: int | None, artifact_type: str, relative_path: str, metadata: dict[str, Any] | None = None) -> None:
        self.connection.execute(
            """
            INSERT INTO artifacts (batch_id, run_id, artifact_type, relative_path, metadata_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (batch_id, run_id, artifact_type, relative_path, json.dumps(metadata or {}, sort_keys=True)),
        )
        self.connection.commit()

    def get_batch(self, batch_id: int) -> sqlite3.Row:
        row = self.connection.execute("SELECT * FROM batches WHERE id = ?", (batch_id,)).fetchone()
        if row is None:
            raise ValueError(f"Unknown batch {batch_id}")
        return row

    def list_batch_runs(self, batch_id: int) -> list[sqlite3.Row]:
        rows = self.connection.execute(
            """
            SELECT
                runs.*,
                sites.url,
                sites.name,
                sites.region,
                sites.population,
                sites.tier_manual,
                sites.notes
            FROM runs
            JOIN sites ON runs.site_id = sites.id
            WHERE runs.batch_id = ?
            ORDER BY runs.id
            """,
            (batch_id,),
        ).fetchall()
        return list(rows)

    def list_run_adapter_results(self, run_id: int) -> list[sqlite3.Row]:
        rows = self.connection.execute(
            "SELECT * FROM adapter_results WHERE run_id = ? ORDER BY id",
            (run_id,),
        ).fetchall()
        return list(rows)

    def list_run_scores(self, run_id: int) -> list[sqlite3.Row]:
        rows = self.connection.execute(
            "SELECT * FROM scores WHERE run_id = ? ORDER BY id",
            (run_id,),
        ).fetchall()
        return list(rows)

    def list_run_findings(self, run_id: int) -> list[sqlite3.Row]:
        rows = self.connection.execute(
            "SELECT * FROM findings WHERE run_id = ? ORDER BY id",
            (run_id,),
        ).fetchall()
        return list(rows)

    def list_run_screenshots(self, run_id: int) -> list[sqlite3.Row]:
        rows = self.connection.execute(
            "SELECT * FROM screenshots WHERE run_id = ? ORDER BY id",
            (run_id,),
        ).fetchall()
        return list(rows)

    def list_run_artifacts(self, run_id: int) -> list[sqlite3.Row]:
        rows = self.connection.execute(
            "SELECT * FROM artifacts WHERE run_id = ? ORDER BY id",
            (run_id,),
        ).fetchall()
        return list(rows)

    def list_batch_artifacts(self, batch_id: int) -> list[sqlite3.Row]:
        rows = self.connection.execute(
            "SELECT * FROM artifacts WHERE batch_id = ? ORDER BY id",
            (batch_id,),
        ).fetchall()
        return list(rows)

    def prior_run_has_screenshots(self, url: str) -> bool:
        row = self.connection.execute(
            """
            SELECT COUNT(DISTINCT screenshots.viewport) AS viewport_count
            FROM screenshots
            JOIN runs ON screenshots.run_id = runs.id
            JOIN sites ON runs.site_id = sites.id
            WHERE sites.url = ?
            """,
            (url,),
        ).fetchone()
        return row is not None and int(row["viewport_count"] or 0) >= 2

    def find_latest_run_with_screenshots(self, site_id: int) -> sqlite3.Row | None:
        return self.connection.execute(
            """
            SELECT runs.*
            FROM runs
            JOIN (
                SELECT run_id
                FROM screenshots
                GROUP BY run_id
                HAVING COUNT(DISTINCT viewport) >= 2
            ) eligible_runs ON eligible_runs.run_id = runs.id
            WHERE runs.site_id = ?
            ORDER BY runs.id DESC
            LIMIT 1
            """,
            (site_id,),
        ).fetchone()

    def __enter__(self) -> Database:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        with closing(self.connection):
            if exc is None:
                self.connection.commit()
            else:
                self.connection.rollback()

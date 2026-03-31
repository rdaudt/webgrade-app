from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tqdm import tqdm

from webgrade.catalog import load_catalog, load_single_site
from webgrade.config import Settings
from webgrade.db import Database
from webgrade.exporters import export_catalog_excel, export_catalog_json
from webgrade.logging_utils import configure_logging
from webgrade.types import CatalogSite, RunOptions


@dataclass(slots=True)
class BatchSummary:
    batch_id: int
    batch_dir: Path
    total_sites: int
    complete_sites: int
    partial_sites: int
    failed_sites: int
    status: str


def _load_sites(options: RunOptions) -> list[CatalogSite]:
    if options.site:
        return load_single_site(options.site, options.report_name)
    if options.input_path is None:
        raise ValueError("--input is required unless --site is used")
    return load_catalog(options.input_path, limit=options.limit)


def _batch_status_from_counts(counts: dict[str, int]) -> str:
    total = sum(counts.values())
    if counts["failed"] == total:
        return "failed"
    if counts["partial"] > 0 or counts["failed"] > 0:
        return "partial"
    return "complete"


def run_batch(settings: Settings, options: RunOptions) -> BatchSummary:
    sites = _load_sites(options)

    with Database(settings.db_path) as db:
        db.initialize()

        if options.only_vision:
            missing = [site.url for site in sites if not db.prior_run_has_screenshots(site.url)]
            if missing:
                raise ValueError(
                    "--only-vision requires existing screenshots for every selected site. "
                    f"Missing prior screenshot evidence for: {', '.join(missing)}"
                )

        batch_dir = settings.create_batch_dir()
        logger = configure_logging(batch_dir / "webgrade.log")
        flags = {
            "input": str(options.input_path) if options.input_path else None,
            "output": str(options.output_dir),
            "limit": options.limit,
            "skip_vision": options.skip_vision,
            "skip_screenshots": options.skip_screenshots,
            "only_vision": options.only_vision,
            "site": options.site,
            "report_name": options.report_name,
        }
        batch_id = db.create_batch(
            input_path=str(options.input_path) if options.input_path else None,
            output_dir=batch_dir.name,
            flags=flags,
            site_count_total=len(sites),
        )

        logger.info("Created batch %s with %s site(s)", batch_id, len(sites))

        counts = {"complete": 0, "partial": 0, "failed": 0}
        for site in tqdm(sites, desc="Processing sites", unit="site"):
            logger.info("Preparing site %s", site.url)
            site_id = db.upsert_site(site)
            run_id = db.create_run(
                batch_id=batch_id,
                site_id=site_id,
                report_name_override=options.report_name if options.site else None,
            )
            manual_review_reasons = ["foundation_only_no_adapters_executed"]
            db.finalize_run(run_id, status="partial", score_coverage=0.0, manual_review_reasons=manual_review_reasons)
            counts["partial"] += 1
            logger.info("Run %s for %s marked partial: scaffold foundation only", run_id, site.url)

        status = _batch_status_from_counts(counts)
        db.finalize_batch(batch_id, status=status, counts=counts)
        db.add_artifact(batch_id=batch_id, run_id=None, artifact_type="log_file", relative_path="webgrade.log")
        excel_path = export_catalog_excel(db, batch_id, batch_dir)
        db.add_artifact(batch_id=batch_id, run_id=None, artifact_type="excel_catalog", relative_path=excel_path.name)
        json_path = export_catalog_json(db, batch_id, batch_dir)
        db.add_artifact(batch_id=batch_id, run_id=None, artifact_type="json_bundle", relative_path=json_path.name)
        logger.info("Finished batch %s with status %s", batch_id, status)

    return BatchSummary(
        batch_id=batch_id,
        batch_dir=batch_dir,
        total_sites=len(sites),
        complete_sites=counts["complete"],
        partial_sites=counts["partial"],
        failed_sites=counts["failed"],
        status=status,
    )

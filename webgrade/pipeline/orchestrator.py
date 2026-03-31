from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import shutil
from typing import Any
import logging

from tqdm import tqdm

from webgrade.adapters import (
    capture_screenshots,
    run_dom_heuristics,
    run_freshness,
    run_pagespeed,
    run_pa11y,
    run_security_headers,
    run_tls_certificate,
    run_vision_for_captures,
    run_wappalyzer,
)
from webgrade.catalog import load_catalog, load_single_site
from webgrade.config import Settings
from webgrade.db import Database
from webgrade.exporters import export_catalog_excel, export_catalog_json
from webgrade.logging_utils import close_logging, configure_logging, log_event
from webgrade.reporting import build_findings, export_pdf_report, render_html_report
from webgrade.scoring import compute_scores
from webgrade.types import CatalogSite, RunOptions
from webgrade.utils import site_slug


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


def _store_scores(db: Database, run_id: int, score_payload: dict[str, Any]) -> None:
    score_rows: list[dict[str, Any]] = []
    for dimension, details in score_payload["dimensions"].items():
        if details["opportunity_score"] is None:
            continue
        score_rows.append(
            {
                "dimension": dimension,
                "raw_value": None,
                "opportunity_score": details["opportunity_score"],
                "source_coverage": details["source_coverage"],
                "viewport": "combined",
                "source": "computed",
            }
        )
    if score_payload["overall_opportunity_score"] is not None:
        score_rows.append(
            {
                "dimension": "overall_opportunity_score",
                "raw_value": None,
                "opportunity_score": score_payload["overall_opportunity_score"],
                "source_coverage": score_payload["score_coverage"],
                "viewport": "combined",
                "source": "computed",
            }
        )
    if score_payload["priority_tier"] is not None:
        score_rows.append(
            {
                "dimension": "priority_tier",
                "raw_value": None,
                "opportunity_score": 0.0,
                "source_coverage": score_payload["score_coverage"],
                "viewport": "combined",
                "source": score_payload["priority_tier"],
            }
        )
    for snapshot_dimension in ("desktop_quality_snapshot", "mobile_quality_snapshot"):
        value = score_payload[snapshot_dimension]
        if value is None:
            continue
        score_rows.append(
            {
                "dimension": snapshot_dimension,
                "raw_value": value,
                "opportunity_score": value,
                "source_coverage": 1.0,
                "viewport": "combined",
                "source": "pagespeed",
            }
        )
    db.replace_run_scores(run_id, score_rows)


def _store_findings(db: Database, run_id: int, findings: list[dict[str, Any]]) -> None:
    db.replace_run_findings(run_id, findings)


def _persist_adapter_results(db: Database, run_id: int, adapter_results: list[dict[str, Any]]) -> None:
    for result in adapter_results:
        db.add_adapter_result(
            run_id=run_id,
            adapter_key=result["adapter_key"],
            viewport=result["viewport"],
            status=result["status"],
            summary=result["summary"],
            raw=result["raw"],
            error=result["error"],
        )


def _run_technical_adapters(settings: Settings, site: CatalogSite, logger: Any) -> tuple[dict[str, dict[str, Any]], list[str]]:
    adapter_results: dict[str, dict[str, Any]] = {}
    manual_review_reasons: list[str] = []

    adapter_calls = [
        (
            "pagespeed",
            ("pagespeed_desktop", "pagespeed_mobile"),
            lambda: run_pagespeed(site.url, api_key=settings.pagespeed_api_key),
        ),
        ("security_headers", ("security_headers",), lambda: [run_security_headers(site.url)]),
        ("tls_certificate", ("tls_certificate",), lambda: [run_tls_certificate(site.url)]),
        ("freshness", ("freshness",), lambda: [run_freshness(site.url)]),
        ("dom_heuristics", ("dom_heuristics",), lambda: [run_dom_heuristics(site.url)]),
        ("wappalyzer", ("wappalyzer",), lambda: [run_wappalyzer(site.url)]),
        ("pa11y", ("pa11y",), lambda: [run_pa11y(site.url)]),
    ]

    for adapter_name, expected_keys, execute in adapter_calls:
        try:
            results = execute()
            for result in results:
                adapter_results[result["adapter_key"]] = result
            non_ok = [result["adapter_key"] for result in results if result["status"] != "ok"]
            if non_ok:
                manual_review_reasons.append(f"{adapter_name}_failed")
                log_event(
                    logger,
                    logging.WARNING,
                    f"Adapter {adapter_name} completed with non-ok results for {site.url}: {', '.join(non_ok)}",
                    stage=adapter_name,
                )
            else:
                log_event(logger, logging.INFO, f"Completed adapter {adapter_name} for {site.url}", stage=adapter_name)
        except Exception as exc:  # noqa: BLE001
            log_event(logger, logging.WARNING, f"Adapter {adapter_name} failed for {site.url}: {exc}", stage=adapter_name)
            manual_review_reasons.append(f"{adapter_name}_failed")
            for adapter_key in expected_keys:
                viewport = "desktop" if adapter_key.endswith("desktop") else "mobile" if adapter_key.endswith("mobile") else "combined"
                adapter_results[adapter_key] = {
                    "adapter_key": adapter_key,
                    "viewport": viewport,
                    "status": "failed",
                    "summary": {},
                    "raw": {},
                    "error": {"message": str(exc)},
                }

    return adapter_results, manual_review_reasons


def _reuse_prior_evidence(
    *,
    db: Database,
    settings: Settings,
    batch_dir: Path,
    source_run: Any,
    run_id: int,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], list[str]]:
    adapter_results: dict[str, dict[str, Any]] = {}
    screenshots: list[dict[str, Any]] = []
    manual_review_reasons: list[str] = []

    source_batch = db.get_batch(int(source_run["batch_id"]))
    source_batch_dir = settings.output_root / source_batch["output_dir"]

    for row in db.list_run_adapter_results(int(source_run["id"])):
        if str(row["adapter_key"]).startswith("vision_"):
            continue
        result = {
            "adapter_key": row["adapter_key"],
            "viewport": row["viewport"],
            "status": "reused" if row["status"] == "ok" else row["status"],
            "summary": json.loads(row["summary_json"]),
            "raw": json.loads(row["raw_json"]),
            "error": json.loads(row["error_json"]) if row["error_json"] else None,
        }
        if row["status"] in {"failed", "partial"}:
            manual_review_reasons.append(f"{row['adapter_key']}_reused_with_{row['status']}")
        adapter_results[result["adapter_key"]] = result
        db.add_adapter_result(
            run_id=run_id,
            adapter_key=result["adapter_key"],
            viewport=result["viewport"],
            status=result["status"],
            summary=result["summary"],
            raw=result["raw"],
            error=result["error"],
            copied_from_result_id=row["id"],
        )

    for row in db.list_run_screenshots(int(source_run["id"])):
        relative_path = Path(row["file_path"])
        source_path = source_batch_dir / relative_path
        target_path = batch_dir / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if source_path.exists():
            shutil.copy2(source_path, target_path)
        metadata = json.loads(row["metadata_json"])
        db.add_screenshot(
            run_id=run_id,
            viewport=row["viewport"],
            file_path=relative_path.as_posix(),
            status="reused",
            metadata=metadata,
            source_run_id=int(source_run["id"]),
        )
        screenshots.append(
            {
                "viewport": row["viewport"],
                "relative_path": relative_path.as_posix(),
                "absolute_path": target_path,
                "metadata": metadata,
            }
        )

    return adapter_results, screenshots, manual_review_reasons


def _capture_site_screenshots(
    *,
    db: Database,
    batch_dir: Path,
    run_id: int,
    site: CatalogSite,
    logger: Any,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], list[str]]:
    adapter_results: dict[str, dict[str, Any]] = {}
    manual_review_reasons: list[str] = []
    site_dir = batch_dir / "screenshots" / site_slug(site.url)
    screenshots: list[dict[str, Any]] = []

    try:
        screenshot_result, captures = capture_screenshots(site.url, site_dir)
        adapter_results[screenshot_result["adapter_key"]] = screenshot_result
        db.add_adapter_result(
            run_id=run_id,
            adapter_key=screenshot_result["adapter_key"],
            viewport=screenshot_result["viewport"],
            status=screenshot_result["status"],
            summary=screenshot_result["summary"],
            raw=screenshot_result["raw"],
            error=screenshot_result["error"],
        )
        if screenshot_result["status"] != "ok":
            manual_review_reasons.append("screenshots_partial")
            log_event(logger, logging.WARNING, f"Screenshot capture partially succeeded for {site.url}", stage="screenshots")
        for capture in captures:
            relative_path = capture["file_path"].relative_to(batch_dir).as_posix()
            db.add_screenshot(
                run_id=run_id,
                viewport=capture["viewport"],
                file_path=relative_path,
                status="ok",
                metadata=capture["metadata"],
            )
            screenshots.append(
                {
                    "viewport": capture["viewport"],
                    "relative_path": relative_path,
                    "absolute_path": capture["file_path"],
                    "metadata": capture["metadata"],
                }
            )
        log_event(logger, logging.INFO, f"Captured screenshots for {site.url}", stage="screenshots")
    except Exception as exc:  # noqa: BLE001
        log_event(logger, logging.WARNING, f"Screenshot capture failed for {site.url}: {exc}", stage="screenshots")
        manual_review_reasons.append("screenshots_failed")
        failed_result = {
            "adapter_key": "screenshots",
            "viewport": "combined",
            "status": "failed",
            "summary": {},
            "raw": {},
            "error": {"message": str(exc)},
        }
        adapter_results["screenshots"] = failed_result
        db.add_adapter_result(
            run_id=run_id,
            adapter_key=failed_result["adapter_key"],
            viewport=failed_result["viewport"],
            status=failed_result["status"],
            summary=failed_result["summary"],
            raw=failed_result["raw"],
            error=failed_result["error"],
        )

    return adapter_results, screenshots, manual_review_reasons


def _run_vision_stage(
    *,
    db: Database,
    run_id: int,
    site: CatalogSite,
    settings: Settings,
    screenshots: list[dict[str, Any]],
    logger: Any,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    if not screenshots:
        results = [
            {
                "adapter_key": f"vision_{viewport}",
                "viewport": viewport,
                "status": "failed",
                "summary": {},
                "raw": {},
                "error": {"message": "Vision scoring requires screenshots for the requested run"},
            }
            for viewport in ("desktop", "mobile")
        ]
        _persist_adapter_results(db, run_id, results)
        return {result["adapter_key"]: result for result in results}, ["vision_failed"]

    try:
        results = run_vision_for_captures(
            site_url=site.url,
            screenshots=screenshots,
            api_key=settings.openai_api_key,
            model=settings.openai_vision_model,
            delay_seconds=settings.vision_delay_seconds,
        )
    except Exception as exc:  # noqa: BLE001
        log_event(logger, logging.WARNING, f"Vision scoring failed for {site.url}: {exc}", stage="vision")
        results = [
            {
                "adapter_key": f"vision_{shot['viewport']}",
                "viewport": shot["viewport"],
                "status": "failed",
                "summary": {},
                "raw": {},
                "error": {"message": str(exc)},
            }
            for shot in screenshots
        ]
    _persist_adapter_results(db, run_id, results)
    if any(result["status"] != "ok" for result in results):
        log_event(logger, logging.WARNING, f"Vision scoring completed with failed outputs for {site.url}", stage="vision")
        return {result["adapter_key"]: result for result in results}, ["vision_failed"]
    log_event(logger, logging.INFO, f"Completed vision scoring for {site.url}", stage="vision")
    return {result["adapter_key"]: result for result in results}, []


def _annotations_by_viewport(adapter_results: dict[str, dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    annotations: dict[str, list[dict[str, Any]]] = {"desktop": [], "mobile": []}
    for viewport in ("desktop", "mobile"):
        summary = adapter_results.get(f"vision_{viewport}", {}).get("summary", {})
        annotations[viewport] = summary.get("annotations", [])[:2]
    return annotations


def _render_site_reports(
    *,
    db: Database,
    batch_id: int,
    batch_dir: Path,
    run_id: int,
    site: CatalogSite,
    run_status: str,
    score_payload: dict[str, Any],
    findings: list[dict[str, Any]],
    screenshots: list[dict[str, Any]],
    manual_review_reasons: list[str],
    adapter_results: dict[str, dict[str, Any]],
    logger: Any,
) -> list[str]:
    extra_manual_review_reasons: list[str] = []
    report_dir = batch_dir / "reports" / site_slug(site.url)
    html_path = report_dir / "report.html"
    pdf_path = report_dir / "report.pdf"

    run_payload = {
        "id": run_id,
        "status": run_status,
        "started_at": datetime.now(tz=UTC).replace(microsecond=0).isoformat(),
        "finished_at": datetime.now(tz=UTC).replace(microsecond=0).isoformat(),
        "score_coverage": score_payload["score_coverage"],
        "manual_review_reasons": manual_review_reasons,
    }
    html_render_screenshots = [
        {
            **shot,
            "image_path": Path(os.path.relpath(batch_dir / shot["relative_path"], start=report_dir)).as_posix(),
            "annotations": shot.get("annotations", []),
        }
        for shot in screenshots
    ]
    technical_appendix = {
        "scores": score_payload,
        "manual_review": {"reasons": manual_review_reasons},
        "screenshots": [
            {
                "viewport": shot["viewport"],
                "relative_path": shot["relative_path"],
                "annotation_count": len(shot.get("annotations", [])),
            }
            for shot in screenshots
        ],
    }
    technical_appendix["adapters"] = {
        key: {
            "status": value.get("status"),
            "summary": value.get("summary", {}),
            "error": value.get("error"),
        }
        for key, value in adapter_results.items()
    }

    try:
        html_output = render_html_report(
            site={
                "url": site.url,
                "name": site.name,
                "region": site.region,
                "population": site.population,
            },
            run=run_payload,
            score_payload=score_payload,
            findings=findings,
            screenshots=html_render_screenshots,
            technical_appendix=technical_appendix,
            output_path=html_path,
        )
        relative_html = html_output.relative_to(batch_dir).as_posix()
        db.add_artifact(batch_id=batch_id, run_id=run_id, artifact_type="html_report", relative_path=relative_html)
    except Exception as exc:  # noqa: BLE001
        log_event(logger, logging.WARNING, f"HTML report render failed for {site.url}: {exc}", stage="html_report")
        extra_manual_review_reasons.append("html_report_failed")
        return extra_manual_review_reasons

    try:
        pdf_output = export_pdf_report(html_output, pdf_path)
        relative_pdf = pdf_output.relative_to(batch_dir).as_posix()
        db.add_artifact(batch_id=batch_id, run_id=run_id, artifact_type="pdf_report", relative_path=relative_pdf)
    except Exception as exc:  # noqa: BLE001
        log_event(logger, logging.WARNING, f"PDF export failed for {site.url}: {exc}", stage="pdf_report")
        extra_manual_review_reasons.append("pdf_export_failed")

    return extra_manual_review_reasons


def _finalize_site_run(
    db: Database,
    batch_id: int,
    batch_dir: Path,
    run_id: int,
    source_run: Any | None,
    site: CatalogSite,
    settings: Settings,
    options: RunOptions,
    logger: Any,
) -> tuple[str, float, list[str]]:
    adapter_results: dict[str, dict[str, Any]] = {}
    screenshots: list[dict[str, Any]] = []
    manual_review_reasons: list[str] = []

    if options.only_vision:
        if source_run is None:
            raise ValueError("--only-vision requires a prior run with screenshots")
        adapter_results, screenshots, reuse_reasons = _reuse_prior_evidence(
            db=db,
            settings=settings,
            batch_dir=batch_dir,
            source_run=source_run,
            run_id=run_id,
        )
        manual_review_reasons.extend(reuse_reasons)
    else:
        adapter_results, technical_review_reasons = _run_technical_adapters(settings, site, logger)
        manual_review_reasons.extend(technical_review_reasons)
        _persist_adapter_results(db, run_id, list(adapter_results.values()))

        if not options.skip_screenshots:
            screenshot_results, screenshot_rows, screenshot_review_reasons = _capture_site_screenshots(
                db=db,
                batch_dir=batch_dir,
                run_id=run_id,
                site=site,
                logger=logger,
            )
            adapter_results.update(screenshot_results)
            screenshots.extend(screenshot_rows)
            manual_review_reasons.extend(screenshot_review_reasons)

    if not options.skip_vision:
        vision_results, vision_review_reasons = _run_vision_stage(
            db=db,
            run_id=run_id,
            site=site,
            settings=settings,
            screenshots=screenshots,
            logger=logger,
        )
        adapter_results.update(vision_results)
        manual_review_reasons.extend(vision_review_reasons)

    annotation_map = _annotations_by_viewport(adapter_results)
    for shot in screenshots:
        shot["annotations"] = annotation_map.get(shot["viewport"], [])

    score_payload = compute_scores({key: result["summary"] for key, result in adapter_results.items()})
    _store_scores(db, run_id, score_payload)
    findings = build_findings(score_payload, {key: result["summary"] for key, result in adapter_results.items()})
    _store_findings(db, run_id, findings)

    if score_payload["overall_opportunity_score"] is None:
        status = "failed"
    elif manual_review_reasons:
        status = "partial"
    else:
        status = "complete"

    report_review_reasons = _render_site_reports(
        db=db,
        batch_id=batch_id,
        batch_dir=batch_dir,
        run_id=run_id,
        site=site,
        run_status=status,
        score_payload=score_payload,
        findings=findings,
        screenshots=screenshots,
        manual_review_reasons=manual_review_reasons,
        adapter_results=adapter_results,
        logger=logger,
    )
    manual_review_reasons.extend(report_review_reasons)
    if status != "failed" and manual_review_reasons:
        status = "partial"

    return status, score_payload["score_coverage"], manual_review_reasons


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

        log_event(logger, logging.INFO, f"Created batch {batch_id} with {len(sites)} site(s)", batch_id=batch_id, stage="batch")

        try:
            counts = {"complete": 0, "partial": 0, "failed": 0}
            for site in tqdm(sites, desc="Processing sites", unit="site"):
                slug = site_slug(site.url)
                log_event(logger, logging.INFO, f"Preparing site {site.url}", batch_id=batch_id, site_slug=slug, stage="site_prepare")
                site_id = db.upsert_site(site)
                source_run = db.find_latest_run_with_screenshots(site_id) if options.only_vision else None
                if options.only_vision and source_run is None:
                    raise ValueError(f"--only-vision requires prior screenshots for {site.url}")
                run_id = db.create_run(
                    batch_id=batch_id,
                    site_id=site_id,
                    report_name_override=options.report_name if options.site else None,
                    source_run_id=int(source_run["id"]) if source_run is not None else None,
                )
                status, score_coverage, manual_review_reasons = _finalize_site_run(
                    db=db,
                    batch_id=batch_id,
                    batch_dir=batch_dir,
                    run_id=run_id,
                    source_run=source_run,
                    site=site,
                    settings=settings,
                    options=options,
                    logger=logger,
                )
                db.finalize_run(run_id, status=status, score_coverage=score_coverage, manual_review_reasons=manual_review_reasons)
                counts[status] += 1
                log_event(
                    logger,
                    logging.INFO,
                    f"Run {run_id} for {site.url} finished with status {status}",
                    batch_id=batch_id,
                    run_id=run_id,
                    site_slug=slug,
                    stage="site_complete",
                )

            status = _batch_status_from_counts(counts)
            db.finalize_batch(batch_id, status=status, counts=counts)
            db.add_artifact(batch_id=batch_id, run_id=None, artifact_type="log_file", relative_path="webgrade.log")
            excel_path = export_catalog_excel(db, batch_id, batch_dir)
            db.add_artifact(batch_id=batch_id, run_id=None, artifact_type="excel_catalog", relative_path=excel_path.name)
            db.add_artifact(batch_id=batch_id, run_id=None, artifact_type="json_bundle", relative_path="catalog.json")
            export_catalog_json(db, batch_id, batch_dir)
            log_event(logger, logging.INFO, f"Finished batch {batch_id} with status {status}", batch_id=batch_id, stage="batch_complete")
        finally:
            close_logging(logger)

    return BatchSummary(
        batch_id=batch_id,
        batch_dir=batch_dir,
        total_sites=len(sites),
        complete_sites=counts["complete"],
        partial_sites=counts["partial"],
        failed_sites=counts["failed"],
        status=status,
    )

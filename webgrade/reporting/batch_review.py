from __future__ import annotations

from collections import Counter
import json
from typing import Any

from webgrade.config import Settings
from webgrade.db import Database


def _opportunity_to_readiness_10(value: float | int | None) -> float | None:
    if value is None:
        return None
    return round((100.0 - float(value)) / 10.0, 1)


def _estimate_vision_cost(usage: dict[str, Any], settings: Settings) -> float | None:
    input_rate = settings.openai_vision_input_cost_per_1m_tokens
    output_rate = settings.openai_vision_output_cost_per_1m_tokens
    if input_rate is None or output_rate is None:
        return None
    input_tokens = int(usage.get("input_tokens") or 0)
    output_tokens = int(usage.get("output_tokens") or 0)
    return round(((input_tokens / 1_000_000) * input_rate) + ((output_tokens / 1_000_000) * output_rate), 6)


def build_batch_review_summary(db: Database, batch_id: int, settings: Settings) -> dict[str, Any]:
    batch = db.get_batch(batch_id)
    runs = db.list_batch_runs(batch_id)

    manual_review_counter: Counter[str] = Counter()
    finding_counter: Counter[str] = Counter()
    adapter_issue_counter: Counter[str] = Counter()
    site_summaries: list[dict[str, Any]] = []
    top_opportunity_sites: list[dict[str, Any]] = []
    vision_usage_totals = {
        "successful_calls": 0,
        "failed_calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "estimated_cost_usd": None,
    }
    total_score_coverage = 0.0

    for run in runs:
        manual_review_reasons = json.loads(run["manual_review_json"])
        manual_review_counter.update(manual_review_reasons)
        total_score_coverage += float(run["score_coverage"] or 0.0)

        findings_rows = db.list_run_findings(run["id"])
        finding_counter.update(str(row["finding_key"]) for row in findings_rows)

        score_rows = db.list_run_scores(run["id"])
        overall_opportunity = next(
            (float(row["opportunity_score"]) for row in score_rows if row["dimension"] == "overall_opportunity_score"),
            None,
        )
        site_summary = {
            "site_name": run["name"] or run["url"],
            "url": run["url"],
            "status": run["status"],
            "overall_opportunity_score": overall_opportunity,
            "readiness_score_10": _opportunity_to_readiness_10(overall_opportunity),
            "score_coverage": round(float(run["score_coverage"] or 0.0), 3),
            "manual_review_reasons": manual_review_reasons,
            "top_findings": [str(row["finding_key"]) for row in findings_rows[:3]],
        }
        site_summaries.append(site_summary)
        if overall_opportunity is not None:
            top_opportunity_sites.append(site_summary)

        for row in db.list_run_adapter_results(run["id"]):
            adapter_key = str(row["adapter_key"])
            if row["status"] not in {"ok", "reused"}:
                adapter_issue_counter.update([adapter_key])
            if not adapter_key.startswith("vision_"):
                continue
            raw = json.loads(row["raw_json"])
            usage = raw.get("usage") or {}
            if row["status"] == "ok":
                vision_usage_totals["successful_calls"] += 1
            else:
                vision_usage_totals["failed_calls"] += 1
            vision_usage_totals["input_tokens"] += int(usage.get("input_tokens") or 0)
            vision_usage_totals["output_tokens"] += int(usage.get("output_tokens") or 0)
            vision_usage_totals["total_tokens"] += int(usage.get("total_tokens") or 0)

    estimated_cost = _estimate_vision_cost(vision_usage_totals, settings)
    if estimated_cost is not None:
        vision_usage_totals["estimated_cost_usd"] = estimated_cost

    top_opportunity_sites.sort(
        key=lambda item: (-1.0 if item["overall_opportunity_score"] is None else -float(item["overall_opportunity_score"]), item["url"])
    )

    average_score_coverage = round(total_score_coverage / len(runs), 3) if runs else 0.0

    return {
        "batch_id": batch_id,
        "status": batch["status"],
        "average_score_coverage": average_score_coverage,
        "site_counts": {
            "total": int(batch["site_count_total"] or 0),
            "complete": int(batch["site_count_complete"] or 0),
            "partial": int(batch["site_count_partial"] or 0),
            "failed": int(batch["site_count_failed"] or 0),
        },
        "top_manual_review_reasons": [
            {"reason": reason, "count": count}
            for reason, count in manual_review_counter.most_common(8)
        ],
        "top_findings": [
            {"finding_key": finding_key, "count": count}
            for finding_key, count in finding_counter.most_common(8)
        ],
        "top_adapter_issues": [
            {"adapter_key": adapter_key, "count": count}
            for adapter_key, count in adapter_issue_counter.most_common(8)
        ],
        "top_opportunity_sites": top_opportunity_sites[:5],
        "sites": site_summaries,
        "vision_usage": vision_usage_totals,
    }


def render_batch_review_markdown(review_summary: dict[str, Any], report_context: dict[str, Any]) -> str:
    classification = report_context.get("sector_classification", {})
    lines = [
        "# Batch Review Summary",
        "",
        f"- Batch ID: `{review_summary['batch_id']}`",
        f"- Batch status: `{review_summary['status']}`",
        f"- Sector: `{classification.get('sector', 'unknown')}` / `{classification.get('sub_sector', 'unknown')}`",
        f"- Jurisdiction: `{classification.get('jurisdiction', 'unspecified')}`",
        f"- Average score coverage: `{review_summary['average_score_coverage']}`",
        "",
        "## Site Outcomes",
        "",
        f"- Total sites: `{review_summary['site_counts']['total']}`",
        f"- Complete: `{review_summary['site_counts']['complete']}`",
        f"- Partial: `{review_summary['site_counts']['partial']}`",
        f"- Failed: `{review_summary['site_counts']['failed']}`",
        "",
        "## Vision Usage",
        "",
        f"- Successful vision calls: `{review_summary['vision_usage']['successful_calls']}`",
        f"- Failed vision calls: `{review_summary['vision_usage']['failed_calls']}`",
        f"- Input tokens: `{review_summary['vision_usage']['input_tokens']}`",
        f"- Output tokens: `{review_summary['vision_usage']['output_tokens']}`",
        f"- Total tokens: `{review_summary['vision_usage']['total_tokens']}`",
    ]
    estimated_cost = review_summary["vision_usage"].get("estimated_cost_usd")
    if estimated_cost is None:
        lines.append("- Estimated cost (USD): `not calculated`")
    else:
        lines.append(f"- Estimated cost (USD): `${estimated_cost:.6f}`")

    lines.extend(["", "## Top Opportunity Sites", ""])
    top_sites = review_summary.get("top_opportunity_sites") or []
    if not top_sites:
        lines.append("- No scored sites are available yet.")
    else:
        for item in top_sites:
            lines.append(
                f"- `{item['site_name']}` ({item['url']}): opportunity `{item['overall_opportunity_score']}`, "
                f"readiness `{item['readiness_score_10']}/10`, status `{item['status']}`"
            )

    def _render_count_section(title: str, items: list[dict[str, Any]], key_name: str) -> None:
        lines.extend(["", f"## {title}", ""])
        if not items:
            lines.append("- None")
            return
        for item in items:
            lines.append(f"- `{item[key_name]}`: `{item['count']}`")

    _render_count_section("Most Common Manual Review Reasons", review_summary.get("top_manual_review_reasons", []), "reason")
    _render_count_section("Most Common Findings", review_summary.get("top_findings", []), "finding_key")
    _render_count_section("Most Common Adapter Issues", review_summary.get("top_adapter_issues", []), "adapter_key")

    lines.extend(["", "## Per-Site Snapshot", ""])
    for item in review_summary.get("sites", []):
        reasons = ", ".join(item["manual_review_reasons"]) if item["manual_review_reasons"] else "none"
        top_findings = ", ".join(item["top_findings"]) if item["top_findings"] else "none"
        lines.append(
            f"- `{item['site_name']}`: status `{item['status']}`, readiness `{item['readiness_score_10']}/10`, "
            f"coverage `{item['score_coverage']}`, top findings `{top_findings}`, manual review `{reasons}`"
        )

    lines.append("")
    return "\n".join(lines)

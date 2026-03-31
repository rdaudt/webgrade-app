from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


COMPOSITE_WEIGHTS = {
    "mobile_usability": 20.0,
    "accessibility": 20.0,
    "technology_stack_modernity": 15.0,
    "performance": 15.0,
    "visual_design_era": 10.0,
    "seo_fundamentals": 10.0,
    "security_posture": 5.0,
    "content_freshness": 5.0,
}


def clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return max(minimum, min(maximum, value))


def invert_quality(value: float | int | None) -> float | None:
    if value is None:
        return None
    return clamp(100.0 - float(value))


def vision_to_opportunity(value: float | int | None) -> float | None:
    if value is None:
        return None
    return clamp(((10.0 - float(value)) / 9.0) * 100.0)


def _weighted_average(items: list[tuple[float, float | None]]) -> tuple[float | None, float]:
    available = [(weight, value) for weight, value in items if value is not None]
    if not available:
        return None, 0.0
    total_weight = sum(weight for weight, _ in available)
    score = sum(weight * float(value) for weight, value in available) / total_weight
    coverage = total_weight / sum(weight for weight, _ in items)
    return round(score, 1), round(coverage, 3)


def _header_grade_to_opportunity(grade: str | None) -> float | None:
    if grade is None:
        return None
    return {"A": 0.0, "B": 20.0, "C": 40.0, "D": 60.0, "E": 80.0, "F": 100.0}.get(grade.upper())


def _tls_status_to_opportunity(status: str | None) -> float | None:
    if status is None:
        return None
    return {
        "valid": 0.0,
        "expiring_soon": 60.0,
        "expired": 100.0,
        "invalid": 100.0,
    }.get(status)


def _binary_bad_to_opportunity(value: bool | None, *, bad_when: bool) -> float | None:
    if value is None:
        return None
    return 100.0 if value is bad_when else 0.0


def _pa11y_opportunity(summary: dict[str, Any]) -> float | None:
    if not summary:
        return None
    weighted_issue_count = (3 * int(summary.get("count_a", 0))) + (2 * int(summary.get("count_aa", 0))) + int(summary.get("count_aaa", 0))
    return clamp(weighted_issue_count * 5.0)


def _platform_opportunity(status: str | None) -> float | None:
    if status is None:
        return None
    return {
        "supported_current": 0.0,
        "supported_old": 35.0,
        "nearing_eol": 70.0,
        "eol": 100.0,
        "unknown_version": 40.0,
        "modern_static": 20.0,
        "unknown": None,
    }.get(status)


def _freshness_opportunity(summary: dict[str, Any]) -> float | None:
    if not summary:
        return None

    recency = None
    reference_content_at = summary.get("reference_content_at")
    if reference_content_at:
        try:
            days_stale = (datetime.now(tz=UTC).date() - datetime.fromisoformat(reference_content_at).date()).days
        except ValueError:
            days_stale = None
        if days_stale is not None:
            if days_stale <= 90:
                recency = 0.0
            elif days_stale <= 180:
                recency = 25.0
            elif days_stale <= 365:
                recency = 50.0
            elif days_stale <= 730:
                recency = 75.0
            else:
                recency = 100.0

    changes = summary.get("estimated_changes_per_year")
    change_score = None
    if changes is not None:
        changes = float(changes)
        if changes >= 12:
            change_score = 0.0
        elif changes >= 6:
            change_score = 25.0
        elif changes >= 3:
            change_score = 50.0
        elif changes >= 1:
            change_score = 75.0
        else:
            change_score = 100.0

    footer_year = summary.get("footer_copyright_year")
    footer_score = None
    if footer_year:
        age = datetime.now(tz=UTC).year - int(footer_year)
        if age <= 1:
            footer_score = 0.0
        elif age == 2:
            footer_score = 50.0
        else:
            footer_score = 100.0

    score, _coverage = _weighted_average([(0.6, recency), (0.2, change_score), (0.2, footer_score)])
    return score


def _priority_tier(score: float | None) -> str | None:
    if score is None:
        return None
    if score >= 65.0:
        return "Tier 1"
    if score >= 40.0:
        return "Tier 2"
    return "Tier 3"


def _vision_dimension_average(
    vision_desktop: dict[str, Any],
    vision_mobile: dict[str, Any],
    dimension: str,
) -> tuple[float | None, float]:
    values: list[tuple[float, float | None]] = []
    desktop_value = vision_desktop.get("dimensions", {}).get(dimension, {}).get("score")
    mobile_value = vision_mobile.get("dimensions", {}).get(dimension, {}).get("score")
    if desktop_value is not None:
        values.append((0.5, vision_to_opportunity(desktop_value)))
    if mobile_value is not None:
        values.append((0.5, vision_to_opportunity(mobile_value)))
    if not values:
        return None, 0.0
    return _weighted_average(values)


def compute_scores(adapter_results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    pagespeed_desktop = adapter_results.get("pagespeed_desktop", {})
    pagespeed_mobile = adapter_results.get("pagespeed_mobile", {})
    pa11y = adapter_results.get("pa11y", {})
    dom = adapter_results.get("dom_heuristics", {})
    security_headers = adapter_results.get("security_headers", {})
    tls_certificate = adapter_results.get("tls_certificate", {})
    freshness = adapter_results.get("freshness", {})
    wappalyzer = adapter_results.get("wappalyzer", {})
    vision_desktop = adapter_results.get("vision_desktop", {})
    vision_mobile = adapter_results.get("vision_mobile", {})

    desktop_perf = invert_quality(pagespeed_desktop.get("performance"))
    mobile_perf = invert_quality(pagespeed_mobile.get("performance"))
    desktop_access = invert_quality(pagespeed_desktop.get("accessibility"))
    mobile_access = invert_quality(pagespeed_mobile.get("accessibility"))
    desktop_seo = invert_quality(pagespeed_desktop.get("seo"))
    mobile_seo = invert_quality(pagespeed_mobile.get("seo"))
    pa11y_score = _pa11y_opportunity(pa11y)
    viewport_score = _binary_bad_to_opportunity(dom.get("has_viewport_meta"), bad_when=False)
    headers_score = _header_grade_to_opportunity(security_headers.get("grade"))
    tls_score = _tls_status_to_opportunity(tls_certificate.get("status"))
    freshness_score = _freshness_opportunity(freshness)
    platform_score = _platform_opportunity(wappalyzer.get("platform_status"))
    vision_mobile_usability = vision_to_opportunity(vision_mobile.get("dimensions", {}).get("mobile_usability", {}).get("score"))
    vision_layout, _vision_layout_coverage = _vision_dimension_average(vision_desktop, vision_mobile, "layout_modernity")
    vision_typography, _vision_typography_coverage = _vision_dimension_average(vision_desktop, vision_mobile, "typography_quality")
    vision_hero, _vision_hero_coverage = _vision_dimension_average(vision_desktop, vision_mobile, "hero_effectiveness")
    vision_navigation, _vision_navigation_coverage = _vision_dimension_average(vision_desktop, vision_mobile, "navigation_clarity")
    vision_footer, _vision_footer_coverage = _vision_dimension_average(vision_desktop, vision_mobile, "footer_usability")
    vision_design_era, _vision_design_era_coverage = _vision_dimension_average(vision_desktop, vision_mobile, "visual_design_era")
    vision_brand, _vision_brand_coverage = _vision_dimension_average(vision_desktop, vision_mobile, "brand_coherence")

    dimension_scores: dict[str, dict[str, Any]] = {}

    mobile_usability, mobile_usability_coverage = _weighted_average(
        [(0.45, vision_mobile_usability), (0.25, mobile_access), (0.15, pa11y_score), (0.15, viewport_score)]
    )
    accessibility, accessibility_coverage = _weighted_average(
        [(0.60, mobile_access), (0.20, desktop_access), (0.20, pa11y_score)]
    )
    performance, performance_coverage = _weighted_average([(0.67, mobile_perf), (0.33, desktop_perf)])
    seo, seo_coverage = _weighted_average([(0.50, mobile_seo), (0.35, desktop_seo), (0.15, viewport_score)])
    security, security_coverage = _weighted_average([(0.70, headers_score), (0.30, tls_score)])
    visual_design, visual_design_coverage = _weighted_average(
        [
            (0.35, vision_design_era),
            (0.20, vision_layout),
            (0.15, vision_typography),
            (0.15, vision_hero),
            (0.10, vision_brand),
            (0.05, vision_navigation),
        ]
    )

    for name, value, coverage in [
        ("mobile_usability", mobile_usability, mobile_usability_coverage),
        ("accessibility", accessibility, accessibility_coverage),
        ("technology_stack_modernity", platform_score, 1.0 if platform_score is not None else 0.0),
        ("performance", performance, performance_coverage),
        ("visual_design_era", visual_design, visual_design_coverage),
        ("seo_fundamentals", seo, seo_coverage),
        ("security_posture", security, security_coverage),
        ("content_freshness", freshness_score, 1.0 if freshness_score is not None else 0.0),
    ]:
        dimension_scores[name] = {
            "opportunity_score": value,
            "source_coverage": coverage,
        }

    available_dimensions = {
        name: details["opportunity_score"]
        for name, details in dimension_scores.items()
        if details["opportunity_score"] is not None
    }
    if available_dimensions:
        total_weight = sum(COMPOSITE_WEIGHTS[name] for name in available_dimensions)
        overall_score = round(
            sum(COMPOSITE_WEIGHTS[name] * float(score) for name, score in available_dimensions.items()) / total_weight,
            1,
        )
        score_coverage = round(total_weight / 100.0, 3)
    else:
        overall_score = None
        score_coverage = 0.0

    desktop_snapshot, _ = _weighted_average(
        [
            (0.25, pagespeed_desktop.get("performance")),
            (0.25, pagespeed_desktop.get("accessibility")),
            (0.25, pagespeed_desktop.get("best_practices")),
            (0.25, pagespeed_desktop.get("seo")),
        ]
    )
    mobile_snapshot, _ = _weighted_average(
        [
            (0.25, pagespeed_mobile.get("performance")),
            (0.25, pagespeed_mobile.get("accessibility")),
            (0.25, pagespeed_mobile.get("best_practices")),
            (0.25, pagespeed_mobile.get("seo")),
        ]
    )

    return {
        "overall_opportunity_score": overall_score,
        "priority_tier": _priority_tier(overall_score),
        "score_coverage": score_coverage,
        "dimensions": dimension_scores,
        "desktop_quality_snapshot": desktop_snapshot,
        "mobile_quality_snapshot": mobile_snapshot,
    }

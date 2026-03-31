from __future__ import annotations

from typing import Any


def _finding(
    *,
    finding_key: str,
    severity: str,
    effort: str,
    framing_tags: list[str],
    plain_text: str,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    return {
        "finding_key": finding_key,
        "severity": severity,
        "effort": effort,
        "framing_tags": framing_tags,
        "plain_text": plain_text,
        "raw_evidence": evidence,
    }


def _annotation_ids(adapter_summaries: dict[str, dict[str, Any]], finding_hint: str) -> list[str]:
    annotation_ids: list[str] = []
    for adapter_key in ("vision_desktop", "vision_mobile"):
        for annotation in adapter_summaries.get(adapter_key, {}).get("annotations", []):
            if annotation.get("finding_hint") == finding_hint and annotation.get("annotation_id"):
                annotation_ids.append(annotation["annotation_id"])
    return annotation_ids


def build_findings(score_payload: dict[str, Any], adapter_summaries: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    dimensions = score_payload["dimensions"]
    security = dimensions.get("security_posture", {}).get("opportunity_score")
    accessibility = dimensions.get("accessibility", {}).get("opportunity_score")
    mobile = dimensions.get("mobile_usability", {}).get("opportunity_score")
    freshness = dimensions.get("content_freshness", {}).get("opportunity_score")
    visual_design = dimensions.get("visual_design_era", {}).get("opportunity_score")
    tls_status = adapter_summaries.get("tls_certificate", {}).get("status")
    dom_summary = adapter_summaries.get("dom_heuristics", {})
    platform_status = adapter_summaries.get("wappalyzer", {}).get("platform_status")
    pa11y_summary = adapter_summaries.get("pa11y", {})
    navigation_score = adapter_summaries.get("vision_desktop", {}).get("dimensions", {}).get("navigation_clarity", {}).get("score")
    footer_score = adapter_summaries.get("vision_desktop", {}).get("dimensions", {}).get("footer_usability", {}).get("score")

    if mobile is not None and mobile >= 65:
        findings.append(
            _finding(
                finding_key="slow_mobile_experience",
                severity="high",
                effort="significant",
                framing_tags=["resident_service", "reputation", "economic_development"],
                plain_text="The mobile experience scored in the high-opportunity range, which suggests residents on phones may face extra friction.",
                evidence={"mobile_usability": mobile},
            )
        )
    if accessibility is not None and accessibility >= 65:
        findings.append(
            _finding(
                finding_key="accessibility_barriers_high",
                severity="high",
                effort="significant",
                framing_tags=["legal", "resident_service", "reputation"],
                plain_text="Accessibility signals indicate residents using assistive technology are likely to encounter serious barriers.",
                evidence={"accessibility": accessibility, "annotation_ids": _annotation_ids(adapter_summaries, "accessibility_barriers")},
            )
        )
    elif (accessibility is not None and accessibility >= 40) or int(pa11y_summary.get("count_a", 0) or 0) >= 5:
        findings.append(
            _finding(
                finding_key="accessibility_barriers_moderate",
                severity="medium",
                effort="moderate",
                framing_tags=["legal", "resident_service"],
                plain_text="Accessibility evidence points to noticeable barriers that are likely to affect part of the resident audience.",
                evidence={"accessibility": accessibility, "count_a": pa11y_summary.get("count_a", 0)},
            )
        )
    if security is not None and security >= 60:
        findings.append(
            _finding(
                finding_key="security_posture_weak",
                severity="high",
                effort="moderate",
                framing_tags=["legal", "reputation", "operational"],
                plain_text="Security protections are weaker than expected for a public-sector site, which increases operational and reputational risk.",
                evidence={"security_posture": security},
            )
        )
    if tls_status == "expiring_soon":
        findings.append(
            _finding(
                finding_key="certificate_expiring",
                severity="medium",
                effort="easy",
                framing_tags=["reputation", "operational"],
                plain_text="The site's TLS certificate is expiring soon and should be renewed before it disrupts resident access.",
                evidence={"tls_status": tls_status},
            )
        )
    if freshness is not None and freshness >= 60:
        findings.append(
            _finding(
                finding_key="stale_content",
                severity="medium",
                effort="moderate",
                framing_tags=["resident_service", "reputation", "economic_development"],
                plain_text="Content freshness signals suggest some information may be harder for residents to trust or act on with confidence.",
                evidence={"content_freshness": freshness},
            )
        )
    if dom_summary.get("has_viewport_meta") is False:
        findings.append(
            _finding(
                finding_key="missing_viewport_meta",
                severity="high",
                effort="easy",
                framing_tags=["resident_service", "reputation"],
                plain_text="The homepage is missing a responsive viewport declaration, which is a common cause of poor mobile presentation.",
                evidence={"has_viewport_meta": False},
            )
        )
    if dom_summary.get("has_search") is False:
        findings.append(
            _finding(
                finding_key="no_search_detected",
                severity="low",
                effort="moderate",
                framing_tags=["resident_service", "operational"],
                plain_text="No homepage search pattern was detected, which can make resident self-service harder on large municipal sites.",
                evidence={"has_search": False},
            )
        )
    if dom_summary.get("has_contact_above_fold") is False:
        findings.append(
            _finding(
                finding_key="contact_hard_to_find",
                severity="medium",
                effort="easy",
                framing_tags=["resident_service", "operational"],
                plain_text="Contact details do not appear prominently near the top of the page, which can push simple service questions into avoidable calls or frustration.",
                evidence={"has_contact_above_fold": False},
            )
        )
    if platform_status in {"supported_old", "nearing_eol", "eol"}:
        severity = "high" if platform_status == "eol" else "medium"
        effort = "significant" if platform_status == "eol" else "moderate"
        findings.append(
            _finding(
                finding_key="outdated_platform_eol" if platform_status == "eol" else "outdated_platform_nearing_eol",
                severity=severity,
                effort=effort,
                framing_tags=["operational", "financial", "reputation"],
                plain_text="The detected site platform appears to be aging, which increases maintenance drag and raises the likelihood of larger modernization work later.",
                evidence={"platform_status": platform_status},
            )
        )
    if visual_design is not None and visual_design >= 60:
        findings.append(
            _finding(
                finding_key="visual_design_outdated",
                severity="medium",
                effort="significant",
                framing_tags=["reputation", "economic_development"],
                plain_text="The visible design language reads as dated, which can weaken first impressions and make the site feel less trustworthy or easier to abandon.",
                evidence={"visual_design_era": visual_design, "annotation_ids": _annotation_ids(adapter_summaries, "visual_design_outdated")},
            )
        )
    if navigation_score is not None and int(navigation_score) <= 4:
        findings.append(
            _finding(
                finding_key="confusing_navigation",
                severity="medium",
                effort="moderate",
                framing_tags=["resident_service", "operational"],
                plain_text="The main navigation appears harder to scan and understand than it should be for common resident tasks.",
                evidence={"navigation_clarity_score": navigation_score, "annotation_ids": _annotation_ids(adapter_summaries, "confusing_navigation")},
            )
        )
    if footer_score is not None and int(footer_score) <= 4:
        findings.append(
            _finding(
                finding_key="weak_footer_usability",
                severity="low",
                effort="easy",
                framing_tags=["resident_service", "operational"],
                plain_text="The footer does not appear to add much utility for residents looking for quick links, contact details, or secondary navigation.",
                evidence={"footer_usability_score": footer_score, "annotation_ids": _annotation_ids(adapter_summaries, "weak_footer_usability")},
            )
        )

    severity_order = {"high": 0, "medium": 1, "low": 2}
    findings.sort(key=lambda item: (severity_order[item["severity"]], item["finding_key"]))
    return findings[:6]

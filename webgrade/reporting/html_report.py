from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any


_FINDING_TITLES = {
    "slow_mobile_experience": "The website is harder to use on a phone than it should be",
    "accessibility_barriers_high": "Accessibility barriers are likely to affect part of the audience",
    "accessibility_barriers_moderate": "Accessibility gaps should be addressed before they grow",
    "security_posture_weak": "Trust and protection signals are weaker than expected",
    "certificate_expiring": "A certificate renewal needs attention soon",
    "stale_content": "Some information may not feel current enough",
    "missing_viewport_meta": "The site is missing a basic mobile-friendly setting",
    "no_search_detected": "Visitors may have to browse too much to find answers",
    "contact_hard_to_find": "Key contact details are not easy to spot",
    "outdated_platform_eol": "The underlying website platform appears to be at end of life",
    "outdated_platform_nearing_eol": "The underlying website platform appears to be aging",
    "visual_design_outdated": "The visual presentation feels dated",
    "confusing_navigation": "The navigation appears harder to follow than it should be",
    "weak_footer_usability": "The footer is not doing enough useful work",
}

_PUBLIC_DIMENSIONS = {
    "mobile_usability": {
        "label": "Works well on phones",
        "meaning": "This reflects how easily people can use the site on a smartphone.",
        "benchmark": "A strong result means common tasks feel clear, readable, and easy to complete on a phone.",
    },
    "accessibility": {
        "label": "Accessible to all users",
        "meaning": "This reflects whether the site is likely to work for people using assistive technology or needing clearer design.",
        "benchmark": "A strong result means most people can access the site without major avoidable barriers.",
    },
    "technology_stack_modernity": {
        "label": "Built on a current platform",
        "meaning": "This reflects whether the site appears to run on a platform that is reasonably current and maintainable.",
        "benchmark": "A strong result means the site is less likely to create avoidable maintenance and security drag.",
    },
    "performance": {
        "label": "Runs reliably and quickly",
        "meaning": "This reflects how quickly the site becomes usable without delay or frustration.",
        "benchmark": "A strong result means the homepage becomes usable quickly on a typical connection.",
    },
    "visual_design_era": {
        "label": "Looks current and well presented",
        "meaning": "This reflects whether the site gives a current, credible, and organized first impression.",
        "benchmark": "A strong result means the site looks current enough to build trust at a glance.",
    },
    "seo_fundamentals": {
        "label": "Easy to find online",
        "meaning": "This reflects whether the site has the basics in place to be found through search engines.",
        "benchmark": "A strong result means people searching for this organization are more likely to find the site quickly.",
    },
    "security_posture": {
        "label": "Protects visitors and builds trust",
        "meaning": "This reflects whether the site shows basic protection and trust signals expected of a modern public website.",
        "benchmark": "A strong result means visitors are less likely to encounter avoidable trust or protection concerns.",
    },
    "content_freshness": {
        "label": "Content appears current",
        "meaning": "This reflects whether important public information appears to be maintained and kept reasonably up to date.",
        "benchmark": "A strong result means visitors can expect key information to feel current and dependable.",
    },
}

_AUDIENCE_LABELS = {
    "municipal": {"people": "residents", "organization": "the municipality"},
    "for_profit": {"people": "customers", "organization": "the business"},
    "nonprofit": {"people": "community members", "organization": "the organization"},
}

_TAG_REASON_TEXT = {
    "municipal": {
        "resident_service": ("residents", "People may have to work harder than they should to get routine information or services."),
        "legal": ("the municipality", "This can become harder and more expensive to address later if standards tighten or complaints arise."),
        "operational": ("the municipality", "When the site does not answer simple needs clearly, more of that demand shifts back onto staff time."),
        "reputation": ("the municipality", "A weak digital experience can make the organization feel less responsive or less current than it is."),
        "economic_development": ("the municipality", "First impressions online can influence how residents, visitors, and businesses perceive the community."),
    },
    "for_profit": {
        "revenue": ("customers", "Extra friction can cause potential customers to leave before taking the next step."),
        "conversion": ("the business", "The site may be doing less than it could to turn attention into enquiries or sales."),
        "customer_trust": ("the business", "Trust signals matter early, especially when a visitor is deciding whether to engage."),
        "lead_generation": ("the business", "A weaker experience can reduce the number of people who contact the business or request service."),
        "search_visibility": ("the business", "If the site is harder to find or use, it can become a weaker channel for new demand."),
        "operational_efficiency": ("the business", "A clearer site can reduce avoidable back-and-forth and support a smoother customer journey."),
    },
    "nonprofit": {
        "service_delivery": ("community members", "People looking for support or program information may have a harder time getting what they need."),
        "accessibility_inclusion": ("community members", "If the site creates barriers, it can unintentionally exclude people the organization is trying to serve."),
        "donor_trust": ("the organization", "The website often shapes whether donors and funders feel confidence in the organization."),
        "volunteer_engagement": ("the organization", "A clearer experience can make it easier for volunteers and supporters to stay engaged."),
        "grant_readiness": ("the organization", "A dated or inaccessible site can weaken readiness for funders who expect clear public information."),
        "reputation": ("the organization", "Digital experience contributes to public trust and confidence in the mission."),
    },
}


def _audience_labels(report_context: dict[str, Any]) -> dict[str, str]:
    family = str(report_context.get("audience_family") or "municipal")
    return _AUDIENCE_LABELS.get(family, _AUDIENCE_LABELS["municipal"])


def _manual_review_note(manual_review_reasons: list[str]) -> str:
    if not manual_review_reasons:
        return ""
    escaped = ", ".join(escape(reason) for reason in manual_review_reasons)
    return f"<p><strong>Manual review notes:</strong> {escaped}</p>"


def _opportunity_to_readiness_10(value: float | int | None) -> str:
    if value is None:
        return "N/A"
    return f"{((100.0 - float(value)) / 10.0):.1f} / 10"


def _quality_to_readiness_10(value: float | int | None) -> str:
    if value is None:
        return "N/A"
    return f"{(float(value) / 10.0):.1f} / 10"


def _summary_paragraphs(
    score_payload: dict[str, Any],
    findings: list[dict[str, Any]],
    run: dict[str, Any],
    report_context: dict[str, Any],
) -> str:
    labels = _audience_labels(report_context)
    opening = {
        "Tier 1": f"This website shows substantial room to better serve {labels['people']} through a more current and usable digital presence.",
        "Tier 2": f"This website is doing some of its job well, but there are meaningful opportunities to improve how it serves {labels['people']}.",
        "Tier 3": f"This website appears comparatively current overall, with more targeted gaps that could still improve service for {labels['people']}.",
        None: "This report is based on partial evidence, so the conclusions should be treated with caution.",
    }[score_payload.get("priority_tier")]

    findings_sentence = ""
    if findings:
        titles = [_FINDING_TITLES.get(finding["finding_key"], finding["finding_key"].replace("_", " ")) for finding in findings[:2]]
        if len(titles) == 1:
            findings_sentence = f"The clearest priority is that {titles[0].lower()}."
        else:
            findings_sentence = f"The most important themes are that {titles[0].lower()} and {titles[1].lower()}."

    goals = report_context.get("organizational_goals") or []
    goals_sentence = ""
    if goals:
        goals_sentence = f"This review is framed around the stated goals of {escape(', '.join(str(goal) for goal in goals[:2]))}."

    coverage = float(run.get("score_coverage") or 0.0)
    if coverage >= 0.99:
        coverage_sentence = "The readiness score is based on a near-complete evidence set."
    elif coverage > 0:
        coverage_sentence = "The readiness score uses partial evidence because some inputs were unavailable in this run."
    else:
        coverage_sentence = "The readiness score uses minimal evidence and should be treated as provisional."

    parts = [opening]
    if findings_sentence:
        parts.append(findings_sentence)
    if goals_sentence:
        parts.append(goals_sentence)
    parts.append(coverage_sentence)
    return "".join(f"<p>{part}</p>" for part in parts)


def _render_annotations(annotations: list[dict[str, Any]]) -> str:
    if not annotations:
        return ""
    overlay_items = []
    caption_items = []
    for index, annotation in enumerate(annotations, start=1):
        left = float(annotation["x"]) * 100.0
        top = float(annotation["y"]) * 100.0
        width = float(annotation.get("width") or 0.03) * 100.0
        height = float(annotation.get("height") or 0.03) * 100.0
        overlay_items.append(
            f"""
            <div class="annotation annotation-{escape(annotation['kind'])}"
                 style="left:{left:.2f}%;top:{top:.2f}%;width:{width:.2f}%;height:{height:.2f}%;">
              <span class="annotation-badge">{index}</span>
            </div>
            """
        )
        caption_items.append(
            f"""
            <li>
              <strong>{index}. {escape(annotation['title'])}</strong><br />
              {escape(annotation['caption'])}
            </li>
            """
        )
    return "".join(overlay_items) + f'<ol class="annotation-captions">{"".join(caption_items)}</ol>'


def _strengths(score_payload: dict[str, Any], adapter_summaries: dict[str, dict[str, Any]], report_context: dict[str, Any]) -> list[str]:
    labels = _audience_labels(report_context)
    dimensions = score_payload.get("dimensions", {})
    strengths: list[str] = []
    if (dimensions.get("content_freshness", {}).get("opportunity_score") or 100) <= 35:
        strengths.append(f"Key public information appears reasonably current, which supports confidence for {labels['people']}.")
    if (dimensions.get("security_posture", {}).get("opportunity_score") or 100) <= 35:
        strengths.append("Baseline trust and protection signals appear to be in place.")
    if adapter_summaries.get("dom_heuristics", {}).get("has_search") is True:
        strengths.append("A visible search pattern is present, which can support quicker self-service for common questions.")
    if adapter_summaries.get("dom_heuristics", {}).get("has_contact_above_fold") is True:
        strengths.append("Contact details appear prominently enough to support simple access needs.")
    if (dimensions.get("visual_design_era", {}).get("opportunity_score") or 100) <= 45:
        strengths.append(f"The site presents a more current first impression than many organizations at a similar scale.")
    if len(strengths) < 3:
        strengths.append(f"The website provides a workable starting point for {labels['organization']} to improve from without needing to reframe the entire digital conversation.")
    return strengths[:3]


def _reason_line(finding: dict[str, Any], report_context: dict[str, Any]) -> tuple[str, str]:
    family = str(report_context.get("audience_family") or "municipal")
    reason_map = _TAG_REASON_TEXT.get(family, _TAG_REASON_TEXT["municipal"])
    for tag in finding.get("framing_tags", []):
        if tag in reason_map:
            subject, text = reason_map[tag]
            return subject, text
    labels = _audience_labels(report_context)
    return labels["organization"], "This issue creates avoidable friction that can make the digital experience less effective than it should be."


def _recommendation_items(findings: list[dict[str, Any]], report_context: dict[str, Any]) -> list[dict[str, str]]:
    family = str(report_context.get("audience_family") or "municipal")
    recommendations: list[dict[str, str]] = []
    action_map = {
        "slow_mobile_experience": ("Improve the mobile experience first", "Start with the pages and tasks most likely to be used on a phone."),
        "accessibility_barriers_high": ("Commission accessibility remediation work", "Prioritize the barriers most likely to block access for part of the audience."),
        "accessibility_barriers_moderate": ("Address accessibility gaps in a phased way", "Treat accessibility as a planned improvement stream rather than a one-off fix."),
        "security_posture_weak": ("Tighten baseline trust and protection settings", "Address the missing protections that are easiest to improve without redesign work."),
        "certificate_expiring": ("Renew the certificate before expiry", "This is a focused maintenance task that can prevent avoidable disruption."),
        "stale_content": ("Create a clearer content maintenance routine", "Set ownership and cadence for the information people rely on most."),
        "missing_viewport_meta": ("Fix the basic mobile presentation setting", "This is a small technical change with an outsized effect on mobile display."),
        "no_search_detected": ("Make common information easier to find", "Add or improve search and reduce the number of steps needed to reach common answers."),
        "contact_hard_to_find": ("Move key contact details higher", "Make the most requested contact information visible without deep scrolling."),
        "outdated_platform_eol": ("Plan for platform renewal", "An aging platform is better handled through planned renewal than repeated short-term patching."),
        "outdated_platform_nearing_eol": ("Plan platform modernization before it becomes urgent", "A staged plan is usually less disruptive than reacting later under pressure."),
        "visual_design_outdated": ("Refresh the public-facing presentation", "Improve first impressions while keeping the site easier to trust and use."),
        "confusing_navigation": ("Simplify the navigation structure", "Make the most important tasks and destinations easier to scan at a glance."),
        "weak_footer_usability": ("Make the footer more useful", "Use the footer to reinforce quick links, contact details, and secondary navigation."),
    }
    organization_reason = {
        "municipal": "This helps the municipality improve public service without making the report feel alarmist.",
        "for_profit": "This helps the business reduce friction in the path from interest to action.",
        "nonprofit": "This helps the organization support service delivery, inclusion, and trust more consistently.",
    }[family]
    for finding in findings[:3]:
        title, detail = action_map.get(
            finding["finding_key"],
            ("Address the most visible digital friction", "Focus first on the issues that most directly affect trust and ease of use."),
        )
        recommendations.append({"title": title, "detail": f"{detail} {organization_reason}"})
    if not recommendations:
        recommendations.append(
            {
                "title": "Review the remaining evidence and prioritize the next improvements",
                "detail": "Use the current results as a starting point for a more complete improvement roadmap.",
            }
        )
    return recommendations


def _scorecard_rows(score_payload: dict[str, Any]) -> str:
    rows: list[str] = []
    for key, config in _PUBLIC_DIMENSIONS.items():
        details = score_payload["dimensions"].get(key, {})
        readiness = _opportunity_to_readiness_10(details.get("opportunity_score"))
        coverage = details.get("source_coverage")
        coverage_note = "" if coverage in {None, 1.0} else f" <span class=\"coverage-pill\">Coverage {float(coverage):.2f}</span>"
        rows.append(
            f"""
            <article class="subscore-card">
              <h3>{escape(config['label'])}</h3>
              <div class="subscore-value">{escape(readiness)}</div>
              <p class="subscore-meaning">{escape(config['meaning'])}</p>
              <p class="subscore-benchmark"><strong>What good looks like:</strong> {escape(config['benchmark'])}{coverage_note}</p>
            </article>
            """
        )
    return "".join(rows)


def _render_findings(findings: list[dict[str, Any]], report_context: dict[str, Any]) -> str:
    if not findings:
        return "<p>No findings were generated for this run.</p>"
    cards: list[str] = []
    labels = _audience_labels(report_context)
    for finding in findings:
        subject, reason_line = _reason_line(finding, report_context)
        organization_line = reason_line if subject == labels["organization"] else _reason_line(
            {**finding, "framing_tags": [tag for tag in finding.get("framing_tags", []) if tag != finding.get("framing_tags", [None])[0]]},
            report_context,
        )[1]
        cards.append(
            f"""
            <article class="finding finding-{escape(finding['severity'])}">
              <h3>{escape(_FINDING_TITLES.get(finding['finding_key'], finding['finding_key'].replace('_', ' ').title()))}</h3>
              <p>{escape(finding['plain_text'])}</p>
              <p><strong>Why this matters to {escape(labels['people'])}:</strong> {escape(reason_line if subject == labels['people'] else 'This issue can make common tasks or information harder to access than they should be.')}</p>
              <p><strong>Why this matters to {escape(labels['organization'])}:</strong> {escape(organization_line)}</p>
              <p><strong>Effort to address:</strong> {escape(finding['effort'].replace('_', ' ').title())}</p>
            </article>
            """
        )
    return "".join(cards)


def _render_appendix(technical_appendix: dict[str, Any]) -> str:
    sections: list[str] = []
    for title, payload in technical_appendix.items():
        sections.append(
            f"""
            <section class="appendix-block">
              <h3>{escape(title.replace('_', ' ').title())}</h3>
              <pre>{escape(str(payload))}</pre>
            </section>
            """
        )
    return "".join(sections) or "<p>No technical appendix content is available for this run.</p>"


def render_html_report(
    *,
    site: dict[str, Any],
    run: dict[str, Any],
    score_payload: dict[str, Any],
    findings: list[dict[str, Any]],
    screenshots: list[dict[str, Any]],
    technical_appendix: dict[str, Any],
    report_context: dict[str, Any],
    adapter_summaries: dict[str, dict[str, Any]],
    output_path: Path,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    findings_html = _render_findings(findings, report_context)

    screenshot_html = ""
    if screenshots:
        for shot in screenshots:
            annotation_html = _render_annotations(shot.get("annotations", []))
            note_html = ""
            if shot.get("annotations") == []:
                note_html = "<p class=\"screenshot-note\">No visual callouts were generated for this screenshot.</p>"
            screenshot_html += f"""
            <figure class="screenshot">
              <div class="screenshot-frame">
                <img src="{escape(shot['image_path'])}" alt="{escape(shot['viewport'])} screenshot" />
                {annotation_html}
              </div>
              <figcaption>{escape(shot['viewport'].title())} screenshot</figcaption>
              {note_html}
            </figure>
            """
    else:
        screenshot_html = "<p>No screenshots are available for this run.</p>"

    labels = _audience_labels(report_context)
    strengths_html = "".join(f"<li>{escape(item)}</li>" for item in _strengths(score_payload, adapter_summaries, report_context))
    recommendations = _recommendation_items(findings, report_context)
    recommendation_html = "".join(
        f"<li><strong>{escape(item['title'])}</strong><br />{escape(item['detail'])}</li>"
        for item in recommendations
    )
    scope_note = report_context.get("scope_notes") or ["This assessment covers the website only in this run."]
    top_cards = [
        ("Digital Presence Readiness", _opportunity_to_readiness_10(score_payload.get("overall_opportunity_score"))),
        ("Desktop experience snapshot", _quality_to_readiness_10(score_payload.get("desktop_quality_snapshot"))),
        ("Mobile experience snapshot", _quality_to_readiness_10(score_payload.get("mobile_quality_snapshot"))),
    ]
    top_card_html = "".join(
        f'<div class="card"><strong>{escape(label)}</strong><div class="card-value">{escape(value)}</div></div>'
        for label, value in top_cards
    )

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(site.get('name') or site['url'])} - Digital Presence Review</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 32px; color: #1f2937; line-height: 1.55; }}
    h1, h2, h3 {{ color: #0f172a; }}
    .header-note {{ color: #475569; margin-top: 8px; }}
    .cards {{ display: flex; gap: 16px; flex-wrap: wrap; margin: 24px 0; }}
    .card {{ border: 1px solid #d1d5db; border-radius: 10px; padding: 16px; min-width: 220px; background: #f8fafc; }}
    .card-value {{ font-size: 28px; font-weight: 700; margin-top: 8px; }}
    .strengths {{ background: #f8fafc; border: 1px solid #d1d5db; border-radius: 10px; padding: 16px 20px; }}
    .strengths li {{ margin-bottom: 8px; }}
    .subscore-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; margin: 24px 0; }}
    .subscore-card {{ border: 1px solid #d1d5db; border-radius: 10px; padding: 16px; background: #ffffff; }}
    .subscore-value {{ font-size: 24px; font-weight: 700; margin: 8px 0; }}
    .subscore-meaning, .subscore-benchmark {{ color: #334155; font-size: 14px; }}
    .coverage-pill {{ display: inline-block; margin-left: 6px; font-size: 12px; color: #0f172a; background: #e2e8f0; border-radius: 999px; padding: 2px 8px; }}
    .finding {{ border-left: 4px solid #2563eb; padding: 12px 16px; background: #f8fafc; margin-bottom: 12px; border-radius: 8px; }}
    .finding-high {{ border-left-color: #dc2626; }}
    .finding-medium {{ border-left-color: #d97706; }}
    .finding-low {{ border-left-color: #2563eb; }}
    .screenshot {{ margin: 16px 0; }}
    .screenshot-frame {{ position: relative; display: inline-block; max-width: 100%; }}
    .screenshot img {{ max-width: 100%; border: 1px solid #d1d5db; display: block; }}
    .annotation {{ position: absolute; border: 3px solid #2563eb; box-sizing: border-box; }}
    .annotation-point {{ border-radius: 999px; min-width: 18px; min-height: 18px; width: 18px !important; height: 18px !important; transform: translate(-50%, -50%); background: rgba(37, 99, 235, 0.25); }}
    .annotation-badge {{ position: absolute; top: -12px; left: -12px; background: #0f172a; color: #fff; font-size: 12px; border-radius: 999px; width: 22px; height: 22px; display: inline-flex; align-items: center; justify-content: center; }}
    .annotation-captions {{ margin-top: 12px; padding-left: 20px; }}
    .screenshot-note {{ margin-top: 8px; color: #475569; }}
    .appendix-block {{ margin-bottom: 24px; break-inside: avoid; }}
    .appendix-block pre {{ white-space: pre-wrap; background: #f8fafc; padding: 12px; border: 1px solid #d1d5db; border-radius: 8px; }}
    ol li {{ margin-bottom: 12px; }}
    @media print {{ body {{ margin: 16px; }} .finding, .subscore-card, .card {{ break-inside: avoid; }} }}
  </style>
</head>
<body>
  <section>
    <p><strong>Digital Presence Review</strong></p>
    <h1>{escape(site.get('name') or site['url'])}</h1>
    <p><strong>Website reviewed:</strong> {escape(site['url'])}</p>
    <p><strong>Date assessed:</strong> {escape(run['finished_at'] or run['started_at'])}</p>
    <p><strong>Audience family:</strong> {escape(str(report_context.get('audience_family', '')).replace('_', ' ').title())}</p>
    <p class="header-note">{escape(scope_note[0])}</p>
  </section>

  <section>
    <h2>In plain language: What did we find?</h2>
    {_summary_paragraphs(score_payload, findings, run, report_context)}
    {_manual_review_note(run['manual_review_reasons'])}
  </section>

  <section>
    <h2>At-a-Glance Scorecards</h2>
    <div class="cards">
      {top_card_html}
    </div>
  </section>

  <section>
    <h2>What the site is doing well</h2>
    <div class="strengths">
      <ul>{strengths_html}</ul>
    </div>
  </section>

  <section>
    <h2>Readiness across key areas</h2>
    <div class="subscore-grid">
      {_scorecard_rows(score_payload)}
    </div>
  </section>

  <section>
    <h2>What we observed, and why it matters</h2>
    {findings_html}
  </section>

  <section>
    <h2>What we noticed on the site</h2>
    <p>This visual evidence highlights the most visible issues affecting the experience for {escape(labels['people'])}.</p>
    {screenshot_html}
  </section>

  <section>
    <h2>Recommended next steps</h2>
    <ol>
      {recommendation_html}
    </ol>
  </section>

  <section>
    <h2>Technical Appendix</h2>
    {_render_appendix(technical_appendix)}
  </section>
</body>
</html>
"""
    output_path.write_text(html, encoding="utf-8")
    return output_path


def export_pdf_report(html_path: Path, pdf_path: Path) -> Path:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Playwright is not installed in the active virtual environment") from exc

    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(html_path.resolve().as_uri(), wait_until="load", timeout=30000)
            page.pdf(path=str(pdf_path), format="Letter", print_background=True)
        finally:
            browser.close()
    return pdf_path

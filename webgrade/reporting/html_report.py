from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any


def _manual_review_note(manual_review_reasons: list[str]) -> str:
    if not manual_review_reasons:
        return ""
    escaped = ", ".join(escape(reason) for reason in manual_review_reasons)
    return f"<p><strong>Manual review notes:</strong> {escaped}</p>"


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


def render_html_report(
    *,
    site: dict[str, Any],
    run: dict[str, Any],
    score_payload: dict[str, Any],
    findings: list[dict[str, Any]],
    screenshots: list[dict[str, Any]],
    output_path: Path,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    summary_sentence = {
        "Tier 1": "This site shows a strong modernization opportunity.",
        "Tier 2": "This site shows a meaningful improvement opportunity.",
        "Tier 3": "This site appears comparatively current, with more targeted gaps.",
        None: "This site has only partial evidence so far.",
    }[score_payload.get("priority_tier")]

    findings_html = "".join(
        f"""
        <article class="finding finding-{escape(finding['severity'])}">
          <h3>{escape(finding['finding_key'].replace('_', ' ').title())}</h3>
          <p>{escape(finding['plain_text'])}</p>
          <p><strong>Why it matters:</strong> {escape(', '.join(finding['framing_tags']))}</p>
          <p><strong>Effort:</strong> {escape(finding['effort'].title())}</p>
        </article>
        """
        for finding in findings
    ) or "<p>No findings were generated for this run.</p>"

    screenshot_html = ""
    if screenshots:
        for shot in screenshots:
            annotation_html = _render_annotations(shot.get("annotations", []))
            screenshot_html += f"""
            <figure class=\"screenshot\">
              <div class=\"screenshot-frame\">
                <img src=\"{escape(shot['image_path'])}\" alt=\"{escape(shot['viewport'])} screenshot\" />
                {annotation_html}
              </div>
              <figcaption>{escape(shot['viewport'].title())} screenshot</figcaption>
            </figure>
            """
    else:
        screenshot_html = "<p>No screenshots are available for this run.</p>"

    score_rows = "".join(
        f"<tr><td>{escape(name.replace('_', ' ').title())}</td><td>{details['opportunity_score']}</td><td>{details['source_coverage']}</td></tr>"
        for name, details in score_payload["dimensions"].items()
        if details["opportunity_score"] is not None
    ) or "<tr><td colspan='3'>No dimension scores available.</td></tr>"

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(site.get('name') or site['url'])} - WebGrade Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 32px; color: #1f2937; line-height: 1.5; }}
    h1, h2, h3 {{ color: #0f172a; }}
    .cards {{ display: flex; gap: 16px; flex-wrap: wrap; margin: 24px 0; }}
    .card {{ border: 1px solid #d1d5db; border-radius: 8px; padding: 16px; min-width: 180px; }}
    .finding {{ border-left: 4px solid #2563eb; padding: 12px 16px; background: #f8fafc; margin-bottom: 12px; }}
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
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ border: 1px solid #d1d5db; padding: 8px; text-align: left; }}
    @media print {{ body {{ margin: 16px; }} .finding {{ break-inside: avoid; }} }}
  </style>
</head>
<body>
  <section>
    <h1>{escape(site.get('name') or site['url'])}</h1>
    <p><strong>URL:</strong> {escape(site['url'])}</p>
    <p><strong>Date assessed:</strong> {escape(run['finished_at'] or run['started_at'])}</p>
    <p><strong>Assessor:</strong> WebGrade</p>
  </section>

  <section>
    <h2>Plain-Language Summary</h2>
    <p>{escape(summary_sentence)}</p>
    <p>The current overall opportunity score is {score_payload.get('overall_opportunity_score')}, with score coverage of {run['score_coverage']}.</p>
    {_manual_review_note(run['manual_review_reasons'])}
  </section>

  <section>
    <h2>At-a-Glance Scorecards</h2>
    <div class="cards">
      <div class="card"><strong>Overall opportunity score</strong><div>{score_payload.get('overall_opportunity_score')}</div></div>
      <div class="card"><strong>Desktop quality snapshot</strong><div>{score_payload.get('desktop_quality_snapshot')}</div></div>
      <div class="card"><strong>Mobile quality snapshot</strong><div>{score_payload.get('mobile_quality_snapshot')}</div></div>
    </div>
  </section>

  <section>
    <h2>Community Impact Findings</h2>
    {findings_html}
  </section>

  <section>
    <h2>Visual Evidence</h2>
    {screenshot_html}
  </section>

  <section>
    <h2>Detailed Scorecard</h2>
    <table>
      <thead><tr><th>Dimension</th><th>Opportunity score</th><th>Coverage</th></tr></thead>
      <tbody>{score_rows}</tbody>
    </table>
  </section>

  <section>
    <h2>Recommended Next Steps</h2>
    <ol>
      {''.join(f"<li>{escape(finding['plain_text'])}</li>" for finding in findings[:3]) or '<li>Complete the remaining evidence collection stages.</li>'}
    </ol>
  </section>

  <section>
    <h2>Technical Appendix</h2>
    <pre>{escape(str(score_payload))}</pre>
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

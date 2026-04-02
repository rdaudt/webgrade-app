from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from webgrade.cli import main
from webgrade.reporting.html_report import render_html_report


class CliIntegrationTests(unittest.TestCase):
    @patch("webgrade.pipeline.orchestrator.export_pdf_report")
    @patch("webgrade.pipeline.orchestrator.capture_screenshots")
    @patch("webgrade.pipeline.orchestrator._run_technical_adapters")
    def test_batch_run_creates_db_and_artifacts(
        self,
        mock_run_technical_adapters: object,
        mock_capture_screenshots: object,
        mock_export_pdf_report: object,
    ) -> None:
        mock_run_technical_adapters.return_value = (
            {
                "pagespeed_desktop": {
                    "adapter_key": "pagespeed_desktop",
                    "viewport": "desktop",
                    "status": "ok",
                    "summary": {
                        "performance": 70,
                        "accessibility": 80,
                        "best_practices": 90,
                        "seo": 60,
                    },
                    "raw": {},
                    "error": None,
                },
                "pagespeed_mobile": {
                    "adapter_key": "pagespeed_mobile",
                    "viewport": "mobile",
                    "status": "ok",
                    "summary": {
                        "performance": 50,
                        "accessibility": 60,
                        "best_practices": 70,
                        "seo": 55,
                    },
                    "raw": {},
                    "error": None,
                },
                "security_headers": {
                    "adapter_key": "security_headers",
                    "viewport": "combined",
                    "status": "ok",
                    "summary": {"grade": "F", "headers_present": {}},
                    "raw": {},
                    "error": None,
                },
                "tls_certificate": {
                    "adapter_key": "tls_certificate",
                    "viewport": "combined",
                    "status": "ok",
                    "summary": {"status": "valid", "expires_at": None, "days_to_expiry": 120},
                    "raw": {},
                    "error": None,
                },
                "freshness": {
                    "adapter_key": "freshness",
                    "viewport": "combined",
                    "status": "ok",
                    "summary": {
                        "reference_content_at": "2026-01-01T00:00:00+00:00",
                        "estimated_changes_per_year": 4.0,
                        "footer_copyright_year": 2026,
                    },
                    "raw": {},
                    "error": None,
                },
                "dom_heuristics": {
                    "adapter_key": "dom_heuristics",
                    "viewport": "combined",
                    "status": "ok",
                    "summary": {
                        "has_viewport_meta": False,
                        "viewport_meta_value": None,
                        "has_search": False,
                        "search_bbox": None,
                        "has_contact_above_fold": False,
                        "contact_bbox": None,
                    },
                    "raw": {},
                    "error": None,
                },
                "wappalyzer": {
                    "adapter_key": "wappalyzer",
                    "viewport": "combined",
                    "status": "ok",
                    "summary": {
                        "cms_name": "WordPress",
                        "cms_version": "5.9.0",
                        "platform_status": "supported_old",
                        "frameworks": ["jQuery"],
                        "hosting_provider": "Cloudflare",
                        "analytics_tools": ["Google Analytics"],
                        "has_accessibility_toolbar": False,
                    },
                    "raw": {},
                    "error": None,
                },
                "pa11y": {
                    "adapter_key": "pa11y",
                    "viewport": "combined",
                    "status": "ok",
                    "summary": {
                        "issue_count_total": 2,
                        "count_a": 1,
                        "count_aa": 1,
                        "count_aaa": 0,
                        "weighted_issue_count": 5,
                    },
                    "raw": {},
                    "error": None,
                },
            },
            [],
        )
        mock_capture_screenshots.side_effect = self._fake_capture_screenshots
        mock_export_pdf_report.side_effect = self._fake_export_pdf_report

        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_root = Path(tmp_dir)
            input_csv = temp_root / "catalog.csv"
            context_path = self._write_context(temp_root)
            input_csv.write_text(
                "url,name\nhttps://example.com,Example\nhttps://example.org,Example Org\n",
                encoding="utf-8",
            )
            output_dir = temp_root / "output"

            exit_code = main(
                [
                    "run",
                    "--input",
                    str(input_csv),
                    "--context",
                    str(context_path),
                    "--output",
                    str(output_dir),
                    "--skip-vision",
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertTrue((output_dir / "webgrade.sqlite3").exists())
            batch_dirs = [path for path in output_dir.iterdir() if path.is_dir()]
            self.assertEqual(len(batch_dirs), 1)
            batch_dir = batch_dirs[0]

            payload = json.loads((batch_dir / "catalog.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["batch"]["summary"]["site_count_total"], 2)
            self.assertEqual(payload["batch"]["summary"]["site_count_complete"], 2)
            self.assertEqual(payload["batch"]["summary"]["site_count_partial"], 0)
            self.assertEqual(len(payload["sites"]), 2)
            self.assertEqual(payload["batch"]["context"]["audience_family"], "municipal")
            self.assertEqual(payload["sites"][0]["run"]["context"]["audience_family"], "municipal")
            self.assertEqual(payload["batch"]["context"]["sector_classification"]["sub_sector"], "municipal_government")
            self.assertTrue(payload["batch"]["context"]["benchmarking_references"])
            self.assertTrue(payload["batch"]["context"]["report_audience"])
            self.assertTrue(payload["batch"]["context"]["desired_tone_rules"])
            self.assertEqual(
                payload["sites"][0]["scores"]["overall_opportunity_score"],
                payload["sites"][1]["scores"]["overall_opportunity_score"],
            )
            self.assertIn("pagespeed_mobile", payload["sites"][0]["adapters"])
            self.assertTrue(payload["sites"][0]["findings"])
            self.assertTrue(payload["sites"][0]["screenshots"]["desktop"])
            self.assertTrue(payload["sites"][0]["reports"]["html"])
            self.assertTrue(payload["sites"][0]["reports"]["pdf"])
            self.assertEqual(payload["sites"][0]["run"]["status"], "complete")
            report_html = (batch_dir / payload["sites"][0]["reports"]["html"]).read_text(encoding="utf-8")
            header_html = report_html.split("</section>", 1)[0]
            self.assertIn("Digital Presence Readiness", report_html)
            self.assertIn("What the site is doing well", report_html)
            self.assertIn("Emergency communications", report_html)
            self.assertNotIn("Technical Appendix", report_html)
            self.assertNotIn("Assessment Framework", report_html)
            self.assertNotIn("Sector classification:", header_html)
            self.assertNotIn("This assessment covers the municipal website only in this run.", header_html)
            self.assertTrue((batch_dir / "context.md").exists())

    def test_report_name_requires_site(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            context_path = self._write_context(Path(tmp_dir))
            exit_code = main(
                [
                    "run",
                    "--input",
                    str(Path(tmp_dir) / "missing.csv"),
                    "--context",
                    str(context_path),
                    "--report-name",
                    "Example",
                ]
            )
            self.assertNotEqual(exit_code, 0)

    def test_report_rewrites_visual_callouts_for_non_technical_audience(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            html_path = Path(tmp_dir) / "report.html"
            render_html_report(
                site={"name": "Example", "url": "https://example.com"},
                run={
                    "created_at": "2026-04-01T00:00:00+00:00",
                    "started_at": "2026-04-01T00:00:00+00:00",
                    "finished_at": "2026-04-01T00:05:00+00:00",
                    "manual_review_reasons": [],
                },
                score_payload={
                    "overall_opportunity_score": 42.0,
                    "desktop_quality_snapshot": 82.0,
                    "mobile_quality_snapshot": 76.0,
                    "priority_tier": "Tier 3",
                    "dimensions": {},
                },
                findings=[],
                screenshots=[
                    {
                        "viewport": "desktop",
                        "image_path": "desktop.png",
                        "annotations": [
                            {
                                "annotation_id": "desktop-hero-1",
                                "finding_hint": "weak_hero",
                                "kind": "rect",
                                "x": 0.1,
                                "y": 0.1,
                                "width": 0.3,
                                "height": 0.12,
                                "title": "Small hero",
                                "caption": "Hero area is shallow and visually underpowered.",
                            }
                        ],
                    }
                ],
                technical_appendix={},
                report_context={
                    "audience_family": "municipal",
                    "report_audience": ["councillors", "CAO", "elected officials"],
                    "organizational_goals": [],
                    "desired_tone_rules": [],
                },
                adapter_summaries={},
                output_path=html_path,
            )

            report_html = html_path.read_text(encoding="utf-8")
            self.assertIn("Opening section does not stand out", report_html)
            self.assertIn(
                "The top of the page does not do enough to show councillors, CAO, elected officials what matters most or where to look first.",
                report_html,
            )
            self.assertNotIn("Small hero", report_html)
            self.assertNotIn("Hero area is shallow and visually underpowered.", report_html)

    @patch("webgrade.pipeline.orchestrator.export_pdf_report")
    @patch("webgrade.pipeline.orchestrator.run_vision_for_captures")
    @patch("webgrade.pipeline.orchestrator.capture_screenshots")
    @patch("webgrade.pipeline.orchestrator._run_technical_adapters")
    def test_batch_run_writes_batch_review_summary(
        self,
        mock_run_technical_adapters: object,
        mock_capture_screenshots: object,
        mock_run_vision_for_captures: object,
        mock_export_pdf_report: object,
    ) -> None:
        mock_run_technical_adapters.return_value = (
            {
                "pagespeed_desktop": {
                    "adapter_key": "pagespeed_desktop",
                    "viewport": "desktop",
                    "status": "ok",
                    "summary": {"performance": 72, "accessibility": 85, "best_practices": 90, "seo": 68},
                    "raw": {},
                    "error": None,
                },
                "pagespeed_mobile": {
                    "adapter_key": "pagespeed_mobile",
                    "viewport": "mobile",
                    "status": "ok",
                    "summary": {"performance": 54, "accessibility": 63, "best_practices": 75, "seo": 59},
                    "raw": {},
                    "error": None,
                },
                "security_headers": {
                    "adapter_key": "security_headers",
                    "viewport": "combined",
                    "status": "ok",
                    "summary": {"grade": "C", "headers_present": {}},
                    "raw": {},
                    "error": None,
                },
                "tls_certificate": {
                    "adapter_key": "tls_certificate",
                    "viewport": "combined",
                    "status": "ok",
                    "summary": {"status": "valid", "expires_at": None, "days_to_expiry": 90},
                    "raw": {},
                    "error": None,
                },
                "freshness": {
                    "adapter_key": "freshness",
                    "viewport": "combined",
                    "status": "ok",
                    "summary": {
                        "reference_content_at": "2026-01-01T00:00:00+00:00",
                        "estimated_changes_per_year": 3.0,
                        "footer_copyright_year": 2026,
                    },
                    "raw": {},
                    "error": None,
                },
                "dom_heuristics": {
                    "adapter_key": "dom_heuristics",
                    "viewport": "combined",
                    "status": "ok",
                    "summary": {
                        "has_viewport_meta": True,
                        "viewport_meta_value": "width=device-width, initial-scale=1",
                        "has_search": False,
                        "search_bbox": None,
                        "has_contact_above_fold": True,
                        "contact_bbox": None,
                    },
                    "raw": {},
                    "error": None,
                },
                "wappalyzer": {
                    "adapter_key": "wappalyzer",
                    "viewport": "combined",
                    "status": "ok",
                    "summary": {
                        "cms_name": "WordPress",
                        "cms_version": "5.9.0",
                        "platform_status": "supported_old",
                        "frameworks": ["jQuery"],
                        "hosting_provider": "Cloudflare",
                        "analytics_tools": ["Google Analytics"],
                        "has_accessibility_toolbar": False,
                    },
                    "raw": {},
                    "error": None,
                },
                "pa11y": {
                    "adapter_key": "pa11y",
                    "viewport": "combined",
                    "status": "ok",
                    "summary": {
                        "issue_count_total": 1,
                        "count_a": 0,
                        "count_aa": 1,
                        "count_aaa": 0,
                        "weighted_issue_count": 3,
                    },
                    "raw": {},
                    "error": None,
                },
            },
            [],
        )
        mock_capture_screenshots.side_effect = self._fake_capture_screenshots
        mock_run_vision_for_captures.side_effect = self._fake_vision_results
        mock_export_pdf_report.side_effect = self._fake_export_pdf_report

        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_root = Path(tmp_dir)
            input_csv = temp_root / "catalog.csv"
            context_path = self._write_context(temp_root)
            input_csv.write_text("url,name\nhttps://example.com,Example\n", encoding="utf-8")
            output_dir = temp_root / "output"

            exit_code = main(
                [
                    "run",
                    "--input",
                    str(input_csv),
                    "--context",
                    str(context_path),
                    "--output",
                    str(output_dir),
                ]
            )

            self.assertEqual(exit_code, 0)
            batch_dirs = [path for path in output_dir.iterdir() if path.is_dir()]
            self.assertEqual(len(batch_dirs), 1)
            batch_dir = batch_dirs[0]

            review_path = batch_dir / "batch-review.md"
            self.assertTrue(review_path.exists())
            review_text = review_path.read_text(encoding="utf-8")
            self.assertIn("Batch Review Summary", review_text)
            self.assertIn("Vision Usage", review_text)
            self.assertIn("Successful vision calls", review_text)

            payload = json.loads((batch_dir / "catalog.json").read_text(encoding="utf-8"))
            review_summary = payload["batch"]["review_summary"]
            self.assertEqual(review_summary["site_counts"]["total"], 1)
            self.assertEqual(review_summary["vision_usage"]["successful_calls"], 2)
            self.assertEqual(review_summary["vision_usage"]["input_tokens"], 600)
            self.assertEqual(review_summary["vision_usage"]["output_tokens"], 160)
            self.assertIsNone(review_summary["vision_usage"]["estimated_cost_usd"])

    @patch("webgrade.pipeline.orchestrator.export_pdf_report")
    @patch("webgrade.pipeline.orchestrator.run_vision_for_captures")
    @patch("webgrade.pipeline.orchestrator.capture_screenshots")
    @patch("webgrade.pipeline.orchestrator._run_technical_adapters")
    def test_only_vision_reuses_prior_evidence(
        self,
        mock_run_technical_adapters: object,
        mock_capture_screenshots: object,
        mock_run_vision_for_captures: object,
        mock_export_pdf_report: object,
    ) -> None:
        mock_run_technical_adapters.return_value = (
            {
                "pagespeed_desktop": {
                    "adapter_key": "pagespeed_desktop",
                    "viewport": "desktop",
                    "status": "ok",
                    "summary": {"performance": 70, "accessibility": 80, "best_practices": 90, "seo": 60},
                    "raw": {},
                    "error": None,
                },
                "pagespeed_mobile": {
                    "adapter_key": "pagespeed_mobile",
                    "viewport": "mobile",
                    "status": "ok",
                    "summary": {"performance": 50, "accessibility": 60, "best_practices": 70, "seo": 55},
                    "raw": {},
                    "error": None,
                },
                "security_headers": {
                    "adapter_key": "security_headers",
                    "viewport": "combined",
                    "status": "ok",
                    "summary": {"grade": "B", "headers_present": {}},
                    "raw": {},
                    "error": None,
                },
                "tls_certificate": {
                    "adapter_key": "tls_certificate",
                    "viewport": "combined",
                    "status": "ok",
                    "summary": {"status": "valid", "expires_at": None, "days_to_expiry": 120},
                    "raw": {},
                    "error": None,
                },
                "freshness": {
                    "adapter_key": "freshness",
                    "viewport": "combined",
                    "status": "ok",
                    "summary": {
                        "reference_content_at": "2026-01-01T00:00:00+00:00",
                        "estimated_changes_per_year": 4.0,
                        "footer_copyright_year": 2026,
                    },
                    "raw": {},
                    "error": None,
                },
                "dom_heuristics": {
                    "adapter_key": "dom_heuristics",
                    "viewport": "combined",
                    "status": "ok",
                    "summary": {
                        "has_viewport_meta": True,
                        "viewport_meta_value": "width=device-width, initial-scale=1",
                        "has_search": True,
                        "search_bbox": None,
                        "has_contact_above_fold": True,
                        "contact_bbox": None,
                    },
                    "raw": {},
                    "error": None,
                },
                "wappalyzer": {
                    "adapter_key": "wappalyzer",
                    "viewport": "combined",
                    "status": "ok",
                    "summary": {
                        "cms_name": "WordPress",
                        "cms_version": "5.9.0",
                        "platform_status": "supported_old",
                        "frameworks": ["jQuery"],
                        "hosting_provider": "Cloudflare",
                        "analytics_tools": [],
                        "has_accessibility_toolbar": False,
                    },
                    "raw": {},
                    "error": None,
                },
                "pa11y": {
                    "adapter_key": "pa11y",
                    "viewport": "combined",
                    "status": "ok",
                    "summary": {"issue_count_total": 0, "count_a": 0, "count_aa": 0, "count_aaa": 0, "weighted_issue_count": 0},
                    "raw": {},
                    "error": None,
                },
            },
            [],
        )
        mock_capture_screenshots.side_effect = self._fake_capture_screenshots
        mock_run_vision_for_captures.side_effect = self._fake_vision_results
        mock_export_pdf_report.side_effect = self._fake_export_pdf_report

        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_root = Path(tmp_dir)
            input_csv = temp_root / "catalog.csv"
            context_path = self._write_context(temp_root)
            input_csv.write_text("url,name\nhttps://example.com,Example\n", encoding="utf-8")
            output_dir = temp_root / "output"

            first_exit = main(
                [
                    "run",
                    "--input",
                    str(input_csv),
                    "--context",
                    str(context_path),
                    "--output",
                    str(output_dir),
                    "--skip-vision",
                ]
            )
            self.assertEqual(first_exit, 0)
            self.assertEqual(mock_run_technical_adapters.call_count, 1)
            self.assertEqual(mock_capture_screenshots.call_count, 1)

            second_exit = main(
                [
                    "run",
                    "--site",
                    "https://example.com",
                    "--context",
                    str(context_path),
                    "--output",
                    str(output_dir),
                    "--only-vision",
                ]
            )
            self.assertEqual(second_exit, 0)
            self.assertEqual(mock_run_technical_adapters.call_count, 1)
            self.assertEqual(mock_capture_screenshots.call_count, 1)
            self.assertEqual(mock_run_vision_for_captures.call_count, 1)

            batch_dirs = sorted([path for path in output_dir.iterdir() if path.is_dir()])
            self.assertEqual(len(batch_dirs), 2)
            payload = json.loads((batch_dirs[-1] / "catalog.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["sites"][0]["run"]["status"], "complete")
            self.assertIn("vision_desktop", payload["sites"][0]["adapters"])
            self.assertTrue(payload["sites"][0]["screenshots"]["desktop"])
            self.assertTrue(payload["sites"][0]["reports"]["html"])
            self.assertEqual(payload["sites"][0]["run"]["context"]["audience_family"], "municipal")

    @staticmethod
    def _fake_capture_screenshots(url: str, output_dir: Path) -> tuple[dict[str, object], list[dict[str, object]]]:
        output_dir.mkdir(parents=True, exist_ok=True)
        captures: list[dict[str, object]] = []
        for viewport in ("desktop", "mobile"):
            file_path = output_dir / f"{viewport}.png"
            file_path.write_bytes(b"PNG")
            captures.append(
                {
                    "viewport": viewport,
                    "file_path": file_path,
                    "metadata": {
                        "width": 1280 if viewport == "desktop" else 375,
                        "height": 800 if viewport == "desktop" else 812,
                        "final_url": url,
                        "page_title": "Example",
                    },
                }
            )
        return (
            {
                "adapter_key": "screenshots",
                "viewport": "combined",
                "status": "ok",
                "summary": {"captures": [{"viewport": capture["viewport"]} for capture in captures]},
                "raw": {},
                "error": None,
            },
            captures,
        )

    @staticmethod
    def _fake_export_pdf_report(html_path: Path, pdf_path: Path) -> Path:
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        pdf_path.write_bytes(b"%PDF-1.4")
        return pdf_path

    @staticmethod
    def _fake_vision_results(
        *,
        site_url: str,
        screenshots: list[dict[str, object]],
        api_key: str | None,
        model: str,
        delay_seconds: float = 0.0,
        max_output_tokens: int = 2200,
    ) -> list[dict[str, object]]:
        results: list[dict[str, object]] = []
        for screenshot in screenshots:
            viewport = str(screenshot["viewport"])
            results.append(
                {
                    "adapter_key": f"vision_{viewport}",
                    "viewport": viewport,
                    "status": "ok",
                    "summary": {
                        "dimensions": {
                            "layout_modernity": {"score": 4, "rationale": "Dense and dated module layout."},
                            "typography_quality": {"score": 5, "rationale": "Typography is serviceable but not polished."},
                            "hero_effectiveness": {"score": 4, "rationale": "The opening area does not guide attention clearly."},
                            "navigation_clarity": {"score": 4, "rationale": "Navigation competes with other content."},
                            "mobile_usability": {"score": 4, "rationale": "Spacing feels tight for smaller screens."},
                            "footer_usability": {"score": 5, "rationale": "Footer utility is average."},
                            "visual_design_era": {"score": 4, "rationale": "Visual style reads as older than current public-sector norms."},
                            "brand_coherence": {"score": 5, "rationale": "Branding is recognizable but not fully cohesive."},
                        },
                        "annotations": [
                            {
                                "annotation_id": f"{viewport}-nav-1",
                                "finding_hint": "confusing_navigation",
                                "kind": "rect",
                                "x": 0.1,
                                "y": 0.1,
                                "width": 0.3,
                                "height": 0.12,
                                "title": "Small hero",
                                "caption": "Hero area is shallow and visually underpowered.",
                            }
                        ],
                    },
                    "raw": {
                        "site_url": site_url,
                        "model": model,
                        "delay_seconds": delay_seconds,
                        "max_output_tokens": max_output_tokens,
                        "api_key_present": api_key is not None,
                    },
                    "error": None,
                }
            )
            results[-1]["raw"]["usage"] = {
                "input_tokens": 300,
                "output_tokens": 80,
                "total_tokens": 380,
            }
        return results

    @staticmethod
    def _write_context(root: Path) -> Path:
        context_path = root / "context.md"
        context_path.write_text(
            """# Run Context

## Sector Classification
sector: public
sub_sector: municipal_government
jurisdiction: British Columbia, Canada
governing_framework:
  - Community Charter (BC)
  - Local Government Act (BC)

## Benchmarking References
- UBCM best practices
- WCAG 2.1 AA

## Report Audience
- councillors
- CAO
- elected officials

## Primary Stakeholders
- municipal councillors
- residents

## Organizational Goals
- improve access to public information
- reduce avoidable staff calls

## Priority Impact Lenses
- resident_service
- emergency_communications
- operational
- reputation

## Primary Risks Or Sensitivities
- accessibility compliance gaps
- limited staff capacity

## Scope Notes
- This assessment covers the municipal website only in this run.

## Desired Tone
- findings should be framed constructively for non-technical audiences
- avoid language that implies negligence; municipalities operate under significant resource constraints
- flag legal risks clearly but without alarm

## Operator Notes
Pilot municipal run
""",
            encoding="utf-8",
        )
        return context_path


if __name__ == "__main__":
    unittest.main()

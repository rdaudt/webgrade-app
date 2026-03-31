from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from webgrade.cli import main


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

    def test_report_name_requires_site(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            exit_code = main(
                [
                    "run",
                    "--input",
                    str(Path(tmp_dir) / "missing.csv"),
                    "--report-name",
                    "Example",
                ]
            )
            self.assertNotEqual(exit_code, 0)

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
            input_csv.write_text("url,name\nhttps://example.com,Example\n", encoding="utf-8")
            output_dir = temp_root / "output"

            first_exit = main(
                [
                    "run",
                    "--input",
                    str(input_csv),
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
                                "title": "Navigation density",
                                "caption": "Top-level navigation appears crowded.",
                            }
                        ],
                    },
                    "raw": {"site_url": site_url, "model": model, "delay_seconds": delay_seconds, "api_key_present": api_key is not None},
                    "error": None,
                }
            )
        return results


if __name__ == "__main__":
    unittest.main()

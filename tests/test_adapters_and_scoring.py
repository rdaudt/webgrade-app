from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch

import httpx

from webgrade.adapters.accessibility import run_pa11y
from webgrade.collectors.base import CatalogCollector, CollectorMetadata, CollectorOutput
from webgrade.adapters.freshness import _extract_footer_year, _extract_visible_dates, _parse_cdx_timestamps
from webgrade.adapters.pagespeed import _parse_categories
from webgrade.adapters.screenshots import capture_screenshots
from webgrade.adapters.security import grade_security_headers
from webgrade.adapters.wappalyzer import inspect_technologies
from webgrade.scoring.engine import compute_scores
from webgrade.types import CatalogSite


class AdapterParsingTests(unittest.TestCase):
    def test_pagespeed_parses_quality_scores(self) -> None:
        payload = {
            "id": "https://example.com/",
            "analysisUTCTimestamp": "2026-03-31T00:00:00.000Z",
            "lighthouseResult": {
                "categories": {
                    "performance": {"score": 0.51},
                    "accessibility": {"score": 0.77},
                    "best-practices": {"score": 0.88},
                    "seo": {"score": 0.61},
                }
            },
        }
        parsed = _parse_categories(payload)
        self.assertEqual(parsed["performance"], 51)
        self.assertEqual(parsed["best_practices"], 88)

    def test_security_headers_grade_is_deterministic(self) -> None:
        headers = httpx.Headers(
            {
                "strict-transport-security": "max-age=63072000",
                "content-security-policy": "default-src 'self'",
                "x-frame-options": "DENY",
            }
        )
        graded = grade_security_headers(headers)
        self.assertEqual(graded["grade"], "C")

    def test_freshness_extractors_handle_basic_html(self) -> None:
        html = """
        <footer>Copyright 2026 Example</footer>
        <article><time>March 1, 2026</time></article>
        <article><time>2025-12-25</time></article>
        """
        visible_dates = _extract_visible_dates(html)
        self.assertEqual(max(visible_dates).isoformat(), "2026-03-01")
        self.assertEqual(_extract_footer_year(html), 2026)

    def test_cdx_timestamp_parser(self) -> None:
        payload = [["timestamp"], ["20240101000000"], ["20250101000000"], ["20260101000000"]]
        first, latest, yearly = _parse_cdx_timestamps(payload)
        self.assertTrue(first.startswith("2024-01-01"))
        self.assertTrue(latest.startswith("2026-01-01"))
        self.assertGreater(yearly, 1.0)

    def test_wappalyzer_heuristics_detect_wordpress_and_signals(self) -> None:
        html = """
        <meta name="generator" content="WordPress 6.4.2" />
        <script src="/wp-content/themes/example/app.js"></script>
        <script src="https://www.googletagmanager.com/gtm.js"></script>
        <script src="https://cdn.userway.org/widget.js"></script>
        """
        headers = httpx.Headers({"server": "cloudflare"})
        summary = inspect_technologies(html, headers)
        self.assertEqual(summary["cms_name"], "WordPress")
        self.assertEqual(summary["platform_status"], "supported_current")
        self.assertIn("Google Tag Manager", summary["analytics_tools"])
        self.assertTrue(summary["has_accessibility_toolbar"])

    @patch("webgrade.adapters.accessibility._resolve_pa11y_command", return_value=["pa11y"])
    @patch("webgrade.adapters.accessibility._execute_pa11y")
    def test_pa11y_retries_once_before_success(
        self,
        mock_execute_pa11y: object,
        _mock_resolve_pa11y_command: object,
    ) -> None:
        mock_execute_pa11y.side_effect = [
            subprocess.CompletedProcess(args=["pa11y"], returncode=1, stdout="", stderr="temporary failure"),
            subprocess.CompletedProcess(args=["pa11y"], returncode=0, stdout="[]", stderr=""),
        ]
        result = run_pa11y("https://example.com")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["summary"]["issue_count_total"], 0)
        self.assertEqual(mock_execute_pa11y.call_count, 2)

    def test_screenshots_return_partial_when_one_viewport_fails(self) -> None:
        class FakePage:
            def __init__(self, viewport_name: str) -> None:
                self.viewport_name = viewport_name
                self.url = f"https://example.com/{viewport_name}"

            def goto(self, url: str, wait_until: str, timeout: int) -> None:
                if self.viewport_name == "mobile":
                    raise RuntimeError("mobile timeout")

            def wait_for_load_state(self, state: str, timeout: int) -> None:
                return None

            def screenshot(self, path: str, full_page: bool) -> None:
                Path(path).write_bytes(b"PNG")

            def title(self) -> str:
                return f"{self.viewport_name.title()} Example"

        class FakeContext:
            def __init__(self, viewport_name: str) -> None:
                self.viewport_name = viewport_name

            def new_page(self) -> FakePage:
                return FakePage(self.viewport_name)

            def close(self) -> None:
                return None

        class FakeBrowser:
            def new_context(self, viewport: dict[str, int], **kwargs: object) -> FakeContext:
                viewport_name = "mobile" if viewport["width"] == 375 else "desktop"
                return FakeContext(viewport_name)

            def close(self) -> None:
                return None

        class FakePlaywrightContextManager:
            def __enter__(self) -> object:
                return types.SimpleNamespace(chromium=types.SimpleNamespace(launch=lambda headless: FakeBrowser()))

            def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
                return None

        fake_module = types.SimpleNamespace(sync_playwright=lambda: FakePlaywrightContextManager())

        with tempfile.TemporaryDirectory() as tmp_dir, patch.dict(sys.modules, {"playwright.sync_api": fake_module}):
            result, captures = capture_screenshots("https://example.com", Path(tmp_dir))
            self.assertEqual(result["status"], "partial")
            self.assertEqual(len(captures), 1)
            self.assertEqual(captures[0]["viewport"], "desktop")
            self.assertEqual(result["summary"]["failed_viewports"][0]["viewport"], "mobile")


class CollectorStubTests(unittest.TestCase):
    def test_collector_stub_exports_csv_compatible_rows(self) -> None:
        class DemoCollector(CatalogCollector):
            collector_key = "demo"

            def collect(self) -> CollectorOutput:
                return CollectorOutput(
                    metadata=CollectorMetadata(collector_key="demo", source_label="Demo"),
                    sites=[
                        CatalogSite(
                            url="https://example.com",
                            name="Example",
                            region="BC",
                            population=1000,
                            tier="A",
                            notes='Quoted "note"',
                        )
                    ],
                )

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "collector.csv"
            DemoCollector().export_csv(output_path)
            csv_text = output_path.read_text(encoding="utf-8")
            self.assertIn('"https://example.com"', csv_text)
            self.assertIn('"Quoted ""note"""', csv_text)


class ScoringTests(unittest.TestCase):
    def test_compute_scores_returns_composite_and_tier(self) -> None:
        adapter_results = {
            "pagespeed_desktop": {"performance": 70, "accessibility": 80, "best_practices": 90, "seo": 65},
            "pagespeed_mobile": {"performance": 50, "accessibility": 60, "best_practices": 70, "seo": 55},
            "security_headers": {"grade": "C", "headers_present": {}},
            "tls_certificate": {"status": "valid", "expires_at": None, "days_to_expiry": 90},
            "freshness": {
                "reference_content_at": "2026-01-15T00:00:00+00:00",
                "estimated_changes_per_year": 6.0,
                "footer_copyright_year": 2026,
            },
            "dom_heuristics": {"has_viewport_meta": True},
            "wappalyzer": {"platform_status": "supported_old"},
            "vision_desktop": {
                "dimensions": {
                    "layout_modernity": {"score": 4},
                    "typography_quality": {"score": 5},
                    "hero_effectiveness": {"score": 4},
                    "navigation_clarity": {"score": 5},
                    "mobile_usability": {"score": 4},
                    "footer_usability": {"score": 5},
                    "visual_design_era": {"score": 4},
                    "brand_coherence": {"score": 5},
                }
            },
            "vision_mobile": {
                "dimensions": {
                    "layout_modernity": {"score": 3},
                    "typography_quality": {"score": 4},
                    "hero_effectiveness": {"score": 3},
                    "navigation_clarity": {"score": 4},
                    "mobile_usability": {"score": 3},
                    "footer_usability": {"score": 4},
                    "visual_design_era": {"score": 3},
                    "brand_coherence": {"score": 4},
                }
            },
        }
        payload = compute_scores(adapter_results)
        self.assertIsNotNone(payload["overall_opportunity_score"])
        self.assertIn(payload["priority_tier"], {"Tier 1", "Tier 2", "Tier 3"})
        self.assertGreater(payload["score_coverage"], 0.0)
        self.assertIn("performance", payload["dimensions"])
        self.assertIsNotNone(payload["dimensions"]["visual_design_era"]["opportunity_score"])


if __name__ == "__main__":
    unittest.main()

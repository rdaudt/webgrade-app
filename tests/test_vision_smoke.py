from __future__ import annotations

import os
import unittest
from pathlib import Path

from dotenv import load_dotenv

from webgrade.adapters.vision import run_vision_for_captures


load_dotenv(Path(__file__).resolve().parents[1] / ".env")

VISION_API_KEY = os.getenv("OPENAI_API_KEY")
VISION_IMAGE_PATH = os.getenv("WEBGRADE_VISION_SMOKE_IMAGE_PATH")


@unittest.skipUnless(
    VISION_API_KEY and VISION_IMAGE_PATH,
    "Set OPENAI_API_KEY and WEBGRADE_VISION_SMOKE_IMAGE_PATH to run the live vision smoke test.",
)
class VisionSmokeTests(unittest.TestCase):
    def test_run_vision_for_captures_with_live_model(self) -> None:
        image_path = Path(VISION_IMAGE_PATH)
        self.assertTrue(image_path.exists(), f"Smoke test image not found: {image_path}")

        results = run_vision_for_captures(
            site_url="https://example.com",
            screenshots=[
                {
                    "viewport": "desktop",
                    "absolute_path": str(image_path.resolve()),
                }
            ],
            api_key=VISION_API_KEY,
            model=os.getenv("OPENAI_VISION_MODEL", "gpt-5.4"),
            delay_seconds=0.0,
            max_output_tokens=int(os.getenv("OPENAI_VISION_MAX_OUTPUT_TOKENS", "2200")),
        )

        self.assertEqual(len(results), 1)
        result = results[0]
        self.assertEqual(result["status"], "ok", result.get("error"))
        self.assertEqual(result["adapter_key"], "vision_desktop")
        dimensions = result["summary"]["dimensions"]
        self.assertIn("layout_modernity", dimensions)
        self.assertIn("visual_design_era", dimensions)
        self.assertIsInstance(result["summary"]["annotations"], list)


if __name__ == "__main__":
    unittest.main()

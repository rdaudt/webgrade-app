from __future__ import annotations

from pathlib import Path
from typing import Any


VIEWPORTS = {
    "desktop": {"width": 1280, "height": 800},
    "mobile": {
        "width": 375,
        "height": 812,
        "device_scale_factor": 2,
        "is_mobile": True,
        "has_touch": True,
    },
}


def capture_screenshots(url: str, output_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Playwright is not installed in the active virtual environment") from exc

    output_dir.mkdir(parents=True, exist_ok=True)
    captures: list[dict[str, Any]] = []
    summary: dict[str, Any] = {"final_url": None, "page_title": None, "captures": []}

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            for viewport, settings in VIEWPORTS.items():
                context = browser.new_context(viewport={"width": settings["width"], "height": settings["height"]}, **{k: v for k, v in settings.items() if k not in {"width", "height"}})
                page = context.new_page()
                page.goto(url, wait_until="load", timeout=45000)
                try:
                    page.wait_for_load_state("networkidle", timeout=5000)
                except Exception:  # noqa: BLE001
                    pass
                file_path = output_dir / f"{viewport}.png"
                page.screenshot(path=str(file_path), full_page=True)
                capture = {
                    "viewport": viewport,
                    "file_path": file_path,
                    "metadata": {
                        "width": settings["width"],
                        "height": settings["height"],
                        "final_url": page.url,
                        "page_title": page.title(),
                    },
                }
                captures.append(capture)
                summary["captures"].append(
                    {
                        "viewport": viewport,
                        "file_path": file_path.name,
                        "width": settings["width"],
                        "height": settings["height"],
                    }
                )
                summary["final_url"] = page.url
                summary["page_title"] = page.title()
                context.close()
        finally:
            browser.close()

    return (
        {
            "adapter_key": "screenshots",
            "viewport": "combined",
            "status": "ok",
            "summary": summary,
            "raw": summary,
            "error": None,
        },
        captures,
    )

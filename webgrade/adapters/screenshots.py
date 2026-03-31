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
    failed_viewports: list[dict[str, str]] = []
    summary: dict[str, Any] = {"final_url": None, "page_title": None, "captures": [], "failed_viewports": []}

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            for viewport, settings in VIEWPORTS.items():
                try:
                    context = None
                    last_error: Exception | None = None
                    for _attempt in range(2):
                        context = browser.new_context(
                            viewport={"width": settings["width"], "height": settings["height"]},
                            **{k: v for k, v in settings.items() if k not in {"width", "height"}},
                        )
                        page = context.new_page()
                        try:
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
                            last_error = None
                            break
                        except Exception as exc:  # noqa: BLE001
                            last_error = exc
                        finally:
                            context.close()
                    if last_error is not None:
                        failed_viewports.append({"viewport": viewport, "message": str(last_error)})
                finally:
                    if context is not None:
                        try:
                            context.close()
                        except Exception:  # noqa: BLE001
                            pass
        finally:
            browser.close()

    summary["failed_viewports"] = failed_viewports
    if not captures:
        failed_messages = ", ".join(f"{item['viewport']}: {item['message']}" for item in failed_viewports) or "unknown screenshot error"
        raise RuntimeError(failed_messages)

    return (
        {
            "adapter_key": "screenshots",
            "viewport": "combined",
            "status": "partial" if failed_viewports else "ok",
            "summary": summary,
            "raw": summary,
            "error": {"failed_viewports": failed_viewports} if failed_viewports else None,
        },
        captures,
    )

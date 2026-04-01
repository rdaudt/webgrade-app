from __future__ import annotations

from base64 import b64encode
from pathlib import Path
import time
from typing import Any, Literal

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI, RateLimitError
from pydantic import BaseModel, Field, ValidationError


class VisionDimension(BaseModel):
    score: int = Field(ge=1, le=10)
    rationale: str = Field(min_length=1, max_length=280)


class VisionDimensions(BaseModel):
    layout_modernity: VisionDimension
    typography_quality: VisionDimension
    hero_effectiveness: VisionDimension
    navigation_clarity: VisionDimension
    mobile_usability: VisionDimension
    footer_usability: VisionDimension
    visual_design_era: VisionDimension
    brand_coherence: VisionDimension


class VisionAnnotation(BaseModel):
    annotation_id: str = Field(min_length=1, max_length=80)
    finding_hint: str = Field(min_length=1, max_length=80)
    kind: Literal["rect", "point"]
    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    width: float | None = Field(default=None, ge=0.0, le=1.0)
    height: float | None = Field(default=None, ge=0.0, le=1.0)
    title: str = Field(min_length=1, max_length=120)
    caption: str = Field(min_length=1, max_length=240)


class VisionAssessment(BaseModel):
    dimensions: VisionDimensions
    annotations: list[VisionAnnotation] = Field(default_factory=list, max_length=3)


def _image_to_data_url(path: Path) -> str:
    suffix = path.suffix.lower()
    mime = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }.get(suffix, "image/jpeg")
    encoded = b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _instructions(viewport: str, site_url: str) -> str:
    return (
        "You are scoring a municipal website screenshot for modernization opportunity. "
        f"The screenshot is the {viewport} homepage view for {site_url}. "
        "Score each design dimension from 1 to 10 where 10 means current, clear, and strong quality, "
        "and 1 means visibly weak or outdated quality. "
        "Use only what is visible in the screenshot. "
        "Return compact JSON only. "
        "Keep each rationale under 18 words. "
        "Return up to 3 annotations for visible issues only, with normalized coordinates from 0.0 to 1.0. "
        "Keep each annotation title under 8 words and each caption under 18 words. "
        "Use kind='rect' for boxes and kind='point' only when a box is not appropriate. "
        "If the screenshot does not show enough evidence for a dimension, still provide your best visible-only score and rationale."
    )


def _usage_payload(response: Any) -> dict[str, Any]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return {}
    if hasattr(usage, "model_dump"):
        dumped = usage.model_dump(mode="json")
        if isinstance(dumped, dict):
            return dumped
    payload: dict[str, Any] = {}
    for key in ("input_tokens", "output_tokens", "total_tokens"):
        value = getattr(usage, key, None)
        if value is not None:
            payload[key] = int(value)
    for key in ("input_tokens_details", "output_tokens_details"):
        value = getattr(usage, key, None)
        if value is None:
            continue
        if hasattr(value, "model_dump"):
            payload[key] = value.model_dump(mode="json")
        elif isinstance(value, dict):
            payload[key] = value
    return payload


def _single_vision_result(
    *,
    site_url: str,
    viewport: str,
    screenshot_path: Path,
    api_key: str,
    model: str,
    client: OpenAI,
) -> dict[str, Any]:
    response = client.responses.parse(
        model=model,
        reasoning={"effort": "high"},
        text_format=VisionAssessment,
        max_output_tokens=2200,
        store=False,
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": _instructions(viewport, site_url)},
                    {"type": "input_image", "image_url": _image_to_data_url(screenshot_path), "detail": "high"},
                ],
            }
        ],
    )
    parsed = response.output_parsed
    if parsed is None:
        raise RuntimeError("Vision response did not contain parsed structured output")
    return {
        "adapter_key": f"vision_{viewport}",
        "viewport": viewport,
        "status": "ok",
        "summary": parsed.model_dump(mode="json"),
        "raw": {
            "response_id": response.id,
            "model": response.model,
            "output_text": getattr(response, "output_text", None),
            "usage": _usage_payload(response),
        },
        "error": None,
    }


def run_vision_for_captures(
    *,
    site_url: str,
    screenshots: list[dict[str, Any]],
    api_key: str | None,
    model: str,
    delay_seconds: float = 0.0,
) -> list[dict[str, Any]]:
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required when vision scoring is enabled")

    client = OpenAI(api_key=api_key)
    results: list[dict[str, Any]] = []
    for index, screenshot in enumerate(screenshots):
        viewport = screenshot["viewport"]
        screenshot_path = Path(screenshot["absolute_path"])
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                result = _single_vision_result(
                    site_url=site_url,
                    viewport=viewport,
                    screenshot_path=screenshot_path,
                    api_key=api_key,
                    model=model,
                    client=client,
                )
                results.append(result)
                last_error = None
                break
            except RateLimitError as exc:
                last_error = exc
                if attempt == 2:
                    break
                time.sleep(2**attempt)
            except (APIConnectionError, APITimeoutError, APIStatusError, RuntimeError, ValidationError) as exc:
                last_error = exc
                if isinstance(exc, APIStatusError) and exc.status_code == 429 and attempt < 2:
                    time.sleep(2**attempt)
                    continue
                if attempt == 2:
                    break
                time.sleep(2**attempt)
        if last_error is not None:
            results.append(
                {
                    "adapter_key": f"vision_{viewport}",
                    "viewport": viewport,
                    "status": "failed",
                    "summary": {},
                    "raw": {},
                    "error": {"message": str(last_error)},
                }
            )
        if delay_seconds and index < len(screenshots) - 1:
            time.sleep(delay_seconds)
    return results

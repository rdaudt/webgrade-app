from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any

import httpx


PAGESPEED_ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"


@dataclass(slots=True)
class AdapterExecutionError(Exception):
    message: str

    def __str__(self) -> str:
        return self.message


def _parse_categories(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        categories = payload["lighthouseResult"]["categories"]
    except KeyError as exc:
        raise AdapterExecutionError("PageSpeed response missing lighthouseResult.categories") from exc

    def category_score(name: str) -> int:
        raw_score = categories[name]["score"]
        if raw_score is None:
            raise AdapterExecutionError(f"PageSpeed category '{name}' is null")
        return int(round(float(raw_score) * 100))

    return {
        "performance": category_score("performance"),
        "accessibility": category_score("accessibility"),
        "best_practices": category_score("best-practices"),
        "seo": category_score("seo"),
        "final_url": payload.get("id"),
        "fetched_at": payload.get("analysisUTCTimestamp"),
    }


def _fetch_strategy(url: str, strategy: str, api_key: str | None, client: httpx.Client) -> dict[str, Any]:
    params = {
        "url": url,
        "strategy": strategy,
        "category": ["performance", "accessibility", "best-practices", "seo"],
    }
    if api_key:
        params["key"] = api_key

    response = client.get(PAGESPEED_ENDPOINT, params=params)
    response.raise_for_status()
    return _parse_categories(response.json())


def _fetch_strategy_with_retry(url: str, strategy: str, api_key: str | None, client: httpx.Client) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            return _fetch_strategy(url, strategy, api_key, client)
        except httpx.HTTPStatusError as exc:
            last_error = exc
            if exc.response.status_code != 429 or attempt == 2:
                break
            time.sleep(2**attempt)
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt == 2:
                break
            time.sleep(2**attempt)
    raise AdapterExecutionError(f"PageSpeed request failed for {strategy}: {last_error}")


def run_pagespeed(url: str, api_key: str | None = None, client: httpx.Client | None = None) -> list[dict[str, Any]]:
    owns_client = client is None
    client = client or httpx.Client(timeout=30.0, follow_redirects=True)
    results: list[dict[str, Any]] = []
    try:
        for strategy in ("desktop", "mobile"):
            try:
                summary = _fetch_strategy_with_retry(url, strategy, api_key, client)
                results.append(
                    {
                        "adapter_key": f"pagespeed_{strategy}",
                        "viewport": strategy,
                        "status": "ok",
                        "summary": summary,
                        "raw": summary,
                        "error": None,
                    }
                )
            except AdapterExecutionError as exc:
                results.append(
                    {
                        "adapter_key": f"pagespeed_{strategy}",
                        "viewport": strategy,
                        "status": "failed",
                        "summary": {},
                        "raw": {},
                        "error": {"message": str(exc)},
                    }
                )
    finally:
        if owns_client:
            client.close()

    if all(result["status"] == "failed" for result in results):
        messages = ", ".join(result["error"]["message"] for result in results if result["error"])
        raise AdapterExecutionError(messages)
    return results

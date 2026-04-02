from __future__ import annotations

import re
from typing import Any

import httpx


VIEWPORT_RE = re.compile(r"<meta[^>]+name=[\"']viewport[\"'][^>]+content=[\"']([^\"']+)[\"']", re.IGNORECASE)
SEARCH_RE = re.compile(r"<input[^>]+type=[\"']search[\"']", re.IGNORECASE)
SEARCH_WIDGET_RE = re.compile(r"(site-search|search-form|search-box)", re.IGNORECASE)
PHONE_RE = re.compile(r"(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}")
ADDRESS_RE = re.compile(r"\d{1,5}\s+[A-Za-z0-9.\s]+(?:Street|St|Road|Rd|Avenue|Ave|Drive|Dr|Lane|Ln|Boulevard|Blvd)", re.IGNORECASE)


def run_dom_heuristics(url: str, client: httpx.Client | None = None) -> dict[str, Any]:
    owns_client = client is None
    client = client or httpx.Client(timeout=20.0, follow_redirects=True)
    try:
        response = client.get(url)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise RuntimeError(f"DOM heuristics failed: {exc}") from exc
    finally:
        if owns_client:
            client.close()

    html = response.text
    viewport_match = VIEWPORT_RE.search(html)
    top_slice = html[: max(1, len(html) // 4)]
    has_search = bool(SEARCH_RE.search(html) or SEARCH_WIDGET_RE.search(html))
    has_contact_above_fold = bool(PHONE_RE.search(top_slice) or ADDRESS_RE.search(top_slice))

    summary = {
        "has_viewport_meta": viewport_match is not None,
        "viewport_meta_value": viewport_match.group(1) if viewport_match else None,
        "has_search": has_search,
        "search_bbox": None,
        "has_contact_above_fold": has_contact_above_fold,
        "contact_bbox": None,
    }
    return {
        "adapter_key": "dom_heuristics",
        "viewport": "combined",
        "status": "ok",
        "summary": summary,
        "raw": summary,
        "error": None,
    }

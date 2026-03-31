from __future__ import annotations

from datetime import UTC, date, datetime
import re
from typing import Any

import httpx


CDX_ENDPOINT = "https://web.archive.org/cdx/search/cdx"
MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def _parse_iso_date(value: str) -> date | None:
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def _extract_visible_dates(html: str) -> list[date]:
    matches: list[date] = []
    for year, month, day in re.findall(r"\b(20\d{2})-(\d{2})-(\d{2})\b", html):
        parsed = _parse_iso_date(f"{year}-{month}-{day}")
        if parsed:
            matches.append(parsed)
    for month_text, day, year in re.findall(r"\b([A-Za-z]{3,9})\s+(\d{1,2}),\s*(20\d{2})\b", html):
        month = MONTHS.get(month_text[:3].lower())
        if month is None:
            continue
        try:
            matches.append(date(int(year), month, int(day)))
        except ValueError:
            continue
    today = datetime.now(tz=UTC).date()
    return [match for match in matches if match <= today]


def _extract_footer_year(html: str) -> int | None:
    match = re.search(r"(?:copyright|&copy;|©)\D*(20\d{2})", html, re.IGNORECASE)
    if not match:
        return None
    return int(match.group(1))


def _parse_cdx_timestamps(payload: list[list[str]]) -> tuple[str | None, str | None, float]:
    timestamps = [row[0] for row in payload[1:] if row]
    if not timestamps:
        return None, None, 0.0

    first_ts = datetime.strptime(timestamps[0], "%Y%m%d%H%M%S").replace(tzinfo=UTC)
    latest_ts = datetime.strptime(timestamps[-1], "%Y%m%d%H%M%S").replace(tzinfo=UTC)
    span_days = max((latest_ts - first_ts).days, 1)
    estimated_changes_per_year = round((len(timestamps) / span_days) * 365, 2)
    return first_ts.isoformat(), latest_ts.isoformat(), estimated_changes_per_year


def run_freshness(url: str, client: httpx.Client | None = None) -> dict[str, Any]:
    owns_client = client is None
    client = client or httpx.Client(timeout=20.0, follow_redirects=True)
    try:
        cdx_response = client.get(
            CDX_ENDPOINT,
            params={
                "url": url,
                "output": "json",
                "fl": "timestamp",
                "filter": "statuscode:200",
                "limit": 50,
            },
        )
        cdx_response.raise_for_status()
        page_response = client.get(url)
        page_response.raise_for_status()
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Freshness inspection failed: {exc}") from exc
    finally:
        if owns_client:
            client.close()

    first_archive_at, latest_archive_at, estimated_changes_per_year = _parse_cdx_timestamps(cdx_response.json())
    visible_dates = _extract_visible_dates(page_response.text)
    visible_latest = max(visible_dates).isoformat() if visible_dates else None
    footer_year = _extract_footer_year(page_response.text)
    reference_content_at = visible_latest or latest_archive_at

    summary = {
        "first_archive_at": first_archive_at,
        "latest_archive_at": latest_archive_at,
        "visible_latest_content_at": visible_latest,
        "footer_copyright_year": footer_year,
        "estimated_changes_per_year": estimated_changes_per_year,
        "reference_content_at": reference_content_at,
    }
    return {
        "adapter_key": "freshness",
        "viewport": "combined",
        "status": "ok",
        "summary": summary,
        "raw": summary,
        "error": None,
    }

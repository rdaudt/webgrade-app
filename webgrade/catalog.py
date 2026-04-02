from __future__ import annotations

import csv
from pathlib import Path
from urllib.parse import urlparse

from webgrade.types import CatalogSite


def _normalize_url(raw_url: str) -> str:
    value = raw_url.strip()
    if not value:
        raise ValueError("URL is empty")
    parsed = urlparse(value if "://" in value else f"https://{value}")
    if not parsed.netloc:
        raise ValueError(f"Invalid URL: {raw_url}")
    return parsed.geturl()


def _parse_population(value: str | None) -> int | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    return int(normalized)


def load_catalog(csv_path: Path, limit: int | None = None) -> list[CatalogSite]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "url" not in reader.fieldnames:
            raise ValueError("CSV must include a 'url' column")
        sites: list[CatalogSite] = []
        for row in reader:
            site = CatalogSite(
                url=_normalize_url(row.get("url", "")),
                name=(row.get("name") or "").strip() or None,
                region=(row.get("region") or "").strip() or None,
                population=_parse_population(row.get("population")),
                tier=(row.get("tier") or "").strip() or None,
                notes=(row.get("notes") or "").strip() or None,
            )
            sites.append(site)
            if limit is not None and len(sites) >= limit:
                break
    if not sites:
        raise ValueError("Catalog is empty")
    return sites


def load_single_site(url: str, report_name: str | None = None) -> list[CatalogSite]:
    return [CatalogSite(url=_normalize_url(url), name=report_name)]

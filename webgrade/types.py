from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class CatalogSite:
    url: str
    name: str | None = None
    region: str | None = None
    population: int | None = None
    tier: str | None = None
    notes: str | None = None


@dataclass(slots=True)
class RunOptions:
    input_path: Path | None
    output_dir: Path
    limit: int | None
    skip_vision: bool
    skip_screenshots: bool
    only_vision: bool
    site: str | None
    report_name: str | None

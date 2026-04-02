from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from webgrade.types import CatalogSite


@dataclass(slots=True)
class CollectorMetadata:
    collector_key: str
    source_label: str
    fetched_at: str | None = None
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CollectorOutput:
    metadata: CollectorMetadata
    sites: list[CatalogSite]


class CatalogCollector(ABC):
    """Future collector interface for non-CSV catalog sources.

    v1 does not ship any concrete collectors. This interface exists so future
    collectors can emit CSV-compatible `CatalogSite` rows without changing the
    rest of the pipeline.
    """

    collector_key: str

    @abstractmethod
    def collect(self) -> CollectorOutput:
        """Return a normalized site catalog for downstream processing."""

    def export_csv(self, output_path: Path) -> Path:
        output = self.collect()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        lines = ["url,name,region,population,tier,notes"]
        for site in output.sites:
            row = [
                site.url,
                site.name or "",
                site.region or "",
                str(site.population) if site.population is not None else "",
                site.tier or "",
                (site.notes or "").replace("\n", " ").replace("\r", " "),
            ]
            escaped = ['"' + value.replace('"', '""') + '"' for value in row]
            lines.append(",".join(escaped))
        output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return output_path

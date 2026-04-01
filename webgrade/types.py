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
    context_path: Path | None
    limit: int | None
    skip_vision: bool
    skip_screenshots: bool
    only_vision: bool
    site: str | None
    report_name: str | None


@dataclass(slots=True)
class ReportContext:
    audience_family: str
    stakeholders: list[str]
    organizational_goals: list[str]
    priority_impact_lenses: list[str]
    risks_or_sensitivities: list[str]
    scope_notes: list[str]
    desired_tone: str
    operator_notes: str | None = None

    def to_summary(self) -> dict[str, object]:
        return {
            "audience_family": self.audience_family,
            "stakeholders": self.stakeholders,
            "organizational_goals": self.organizational_goals,
            "priority_impact_lenses": self.priority_impact_lenses,
            "risks_or_sensitivities": self.risks_or_sensitivities,
            "scope_notes": self.scope_notes,
            "desired_tone": self.desired_tone,
            "operator_notes": self.operator_notes,
        }

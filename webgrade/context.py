from __future__ import annotations

from pathlib import Path
import re

from webgrade.types import ReportContext


_REQUIRED_SECTIONS = {
    "Audience Family",
    "Primary Stakeholders",
    "Organizational Goals",
}

_DEFAULT_IMPACT_LENSES = {
    "municipal": ["resident_service", "legal", "operational", "reputation", "economic_development"],
    "for_profit": ["revenue", "conversion", "customer_trust", "lead_generation", "search_visibility", "operational_efficiency"],
    "nonprofit": ["service_delivery", "accessibility_inclusion", "donor_trust", "volunteer_engagement", "grant_readiness", "reputation"],
}

_DEFAULT_TONES = {
    "municipal": "Respectful, constructive, plain-language, independent",
    "for_profit": "Respectful, commercially aware, plain-language, independent",
    "nonprofit": "Respectful, mission-aware, plain-language, independent",
}


def _normalize_audience_family(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "municipality": "municipal",
        "public_sector": "municipal",
        "private_sector": "for_profit",
        "business": "for_profit",
        "forprofit": "for_profit",
        "non_profit": "nonprofit",
        "charity": "nonprofit",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in {"municipal", "for_profit", "nonprofit"}:
        raise ValueError(
            "Audience Family must be one of: municipal, for_profit, nonprofit"
        )
    return normalized


def _parse_list(value: str) -> list[str]:
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    items: list[str] = []
    for line in lines:
        if line.startswith(("- ", "* ")):
            items.append(line[2:].strip())
        else:
            items.append(line)
    return [item for item in items if item]


def _extract_sections(markdown_text: str) -> dict[str, str]:
    pattern = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
    matches = list(pattern.finditer(markdown_text))
    if not matches:
        raise ValueError("context.md must use '##' headings for its sections")

    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        title = match.group(1).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown_text)
        sections[title] = markdown_text[start:end].strip()
    return sections


def parse_context_markdown(markdown_text: str) -> ReportContext:
    sections = _extract_sections(markdown_text)
    missing = sorted(title for title in _REQUIRED_SECTIONS if not sections.get(title))
    if missing:
        raise ValueError(f"context.md is missing required sections: {', '.join(missing)}")

    audience_family = _normalize_audience_family(sections["Audience Family"])
    stakeholders = _parse_list(sections["Primary Stakeholders"])
    goals = _parse_list(sections["Organizational Goals"])
    if not stakeholders:
        raise ValueError("Primary Stakeholders must include at least one item")
    if not goals:
        raise ValueError("Organizational Goals must include at least one item")

    impact_lenses = _parse_list(sections.get("Priority Impact Lenses", ""))
    if not impact_lenses:
        impact_lenses = list(_DEFAULT_IMPACT_LENSES[audience_family])

    risks = _parse_list(sections.get("Primary Risks Or Sensitivities", ""))
    scope_notes = _parse_list(sections.get("Scope Notes", "")) or ["This assessment covers the website only in this run."]
    desired_tone = sections.get("Desired Tone", "").strip() or _DEFAULT_TONES[audience_family]
    operator_notes = sections.get("Operator Notes", "").strip() or None

    return ReportContext(
        audience_family=audience_family,
        stakeholders=stakeholders,
        organizational_goals=goals,
        priority_impact_lenses=impact_lenses,
        risks_or_sensitivities=risks,
        scope_notes=scope_notes,
        desired_tone=desired_tone,
        operator_notes=operator_notes,
    )


def load_report_context(path: Path) -> tuple[str, ReportContext]:
    markdown_text = path.read_text(encoding="utf-8")
    return markdown_text, parse_context_markdown(markdown_text)

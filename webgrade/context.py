from __future__ import annotations

from pathlib import Path
import re

from webgrade.types import ReportContext


_REQUIRED_SECTIONS = {
    "Sector Classification",
    "Benchmarking References",
    "Primary Stakeholders",
    "Organizational Goals",
    "Priority Impact Lenses",
    "Primary Risks Or Sensitivities",
    "Scope Notes",
    "Desired Tone",
    "Operator Notes",
}

_DEFAULT_IMPACT_LENSES = {
    "municipal": [
        "resident_service",
        "accessibility",
        "civic_engagement",
        "legal_compliance",
        "indigenous_relations",
        "emergency_communications",
        "operational",
        "reputation",
        "economic_development",
    ],
    "for_profit": ["revenue", "conversion", "customer_trust", "lead_generation", "search_visibility", "operational_efficiency"],
    "nonprofit": ["service_delivery", "accessibility_inclusion", "donor_trust", "volunteer_engagement", "grant_readiness", "reputation"],
}

_DEFAULT_TONES = {
    "municipal": [
        "findings should be framed constructively for non-technical audiences",
        "avoid language that implies negligence; municipalities operate under significant resource constraints",
        "flag legal risks clearly but without alarm",
        "distinguish between findings that require immediate action vs. longer-term improvement",
    ],
    "for_profit": [
        "findings should be framed clearly for non-technical decision-makers",
        "avoid exaggerated language or unsupported urgency claims",
        "connect issues to trust, conversion, and customer friction where relevant",
        "distinguish between quick wins and larger modernization work",
    ],
    "nonprofit": [
        "findings should be framed constructively for non-technical readers",
        "avoid language that questions mission intent or organizational care",
        "connect issues to inclusion, trust, and service delivery where relevant",
        "distinguish between near-term remediation and longer-term improvement",
    ],
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


def _normalize_token(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")


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
    if "## Audience Family" in markdown_text:
        raise ValueError("Old context format is no longer supported. Use the Sector Classification format.")
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


def _parse_structured_section(value: str) -> dict[str, object]:
    lines = [line.rstrip() for line in value.splitlines() if line.strip()]
    data: dict[str, object] = {}
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        match = re.match(r"^([A-Za-z_ ]+):\s*(.*)$", line)
        if not match:
            raise ValueError(f"Invalid Sector Classification line: {line}")
        key = _normalize_token(match.group(1))
        remainder = match.group(2).strip()
        if remainder:
            data[key] = remainder
            index += 1
            continue

        items: list[str] = []
        index += 1
        while index < len(lines):
            candidate = lines[index].strip()
            if re.match(r"^([A-Za-z_ ]+):\s*(.*)$", candidate) and not candidate.startswith(("- ", "* ")):
                break
            if candidate.startswith(("- ", "* ")):
                items.append(candidate[2:].strip())
                index += 1
                continue
            raise ValueError(f"Invalid list item in Sector Classification: {candidate}")
        data[key] = items
    return data


def _sector_classification_to_family(classification: dict[str, object]) -> str:
    sector = _normalize_token(str(classification.get("sector") or ""))
    sub_sector = _normalize_token(str(classification.get("sub_sector") or ""))
    if sub_sector == "municipal_government":
        return "municipal"
    if sector == "private":
        return "for_profit"
    if sector in {"nonprofit", "social"}:
        return "nonprofit"
    raise ValueError(
        "Sector Classification must resolve to one of: municipal, for_profit, nonprofit"
    )


def _validate_required_list(name: str, items: list[str]) -> list[str]:
    if not items:
        raise ValueError(f"{name} must include at least one item")
    return items


def parse_context_markdown(markdown_text: str) -> ReportContext:
    sections = _extract_sections(markdown_text)
    missing = sorted(title for title in _REQUIRED_SECTIONS if not sections.get(title))
    if missing:
        raise ValueError(f"context.md is missing required sections: {', '.join(missing)}")

    classification = _parse_structured_section(sections["Sector Classification"])
    sector = str(classification.get("sector") or "").strip()
    sub_sector = str(classification.get("sub_sector") or "").strip()
    jurisdiction = str(classification.get("jurisdiction") or "").strip()
    governing_framework = classification.get("governing_framework") or classification.get("governing_legislation") or []
    if not sector or not sub_sector or not jurisdiction:
        raise ValueError("Sector Classification must include sector, sub_sector, and jurisdiction")
    if not isinstance(governing_framework, list) or not governing_framework:
        raise ValueError("Sector Classification must include governing_framework or governing_legislation as a non-empty list")

    audience_family = _sector_classification_to_family(classification)
    stakeholders = _validate_required_list("Primary Stakeholders", _parse_list(sections["Primary Stakeholders"]))
    goals = _validate_required_list("Organizational Goals", _parse_list(sections["Organizational Goals"]))
    benchmarking_references = _validate_required_list("Benchmarking References", _parse_list(sections["Benchmarking References"]))

    parsed_lenses = [_normalize_token(item) for item in _parse_list(sections["Priority Impact Lenses"])]
    if not parsed_lenses:
        parsed_lenses = list(_DEFAULT_IMPACT_LENSES[audience_family])
    # Validate against the known defaults while still allowing custom extensions.
    default_lenses = {_normalize_token(item) for item in _DEFAULT_IMPACT_LENSES[audience_family]}
    impact_lenses: list[str] = []
    for lens in parsed_lenses:
        if lens not in impact_lenses:
            impact_lenses.append(lens if lens in default_lenses else lens)

    risks = _validate_required_list("Primary Risks Or Sensitivities", _parse_list(sections["Primary Risks Or Sensitivities"]))
    scope_notes = _validate_required_list("Scope Notes", _parse_list(sections["Scope Notes"]))
    desired_tone_rules = [_rule for _rule in _parse_list(sections["Desired Tone"]) if _rule] or list(_DEFAULT_TONES[audience_family])
    operator_notes = sections.get("Operator Notes", "").strip() or None

    return ReportContext(
        audience_family=audience_family,
        sector=sector,
        sub_sector=sub_sector,
        jurisdiction=jurisdiction,
        governing_framework=[str(item) for item in governing_framework],
        benchmarking_references=benchmarking_references,
        stakeholders=stakeholders,
        organizational_goals=goals,
        priority_impact_lenses=impact_lenses,
        risks_or_sensitivities=risks,
        scope_notes=scope_notes,
        desired_tone_rules=desired_tone_rules,
        operator_notes=operator_notes,
    )


def load_report_context(path: Path) -> tuple[str, ReportContext]:
    markdown_text = path.read_text(encoding="utf-8")
    return markdown_text, parse_context_markdown(markdown_text)

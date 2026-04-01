from __future__ import annotations

import unittest

from webgrade.context import parse_context_markdown


class ReportContextTests(unittest.TestCase):
    def test_parse_context_markdown_uses_defaults(self) -> None:
        context = parse_context_markdown(
            """# Run Context

## Sector Classification
sector: public
sub_sector: municipal_government
jurisdiction: British Columbia, Canada
governing_framework:
  - Community Charter (BC)

## Benchmarking References
- WCAG 2.1 AA

## Report Audience
- councillors
- CAO

## Primary Stakeholders
- council
- residents

## Organizational Goals
- improve access to information
- reduce avoidable office calls

## Priority Impact Lenses
- resident_service
- emergency_communications

## Primary Risks Or Sensitivities
- accessibility gaps

## Scope Notes
- This assessment covers the municipal website only in this run.

## Desired Tone
- findings should be framed constructively for non-technical audiences

## Operator Notes
Test note
"""
        )
        self.assertEqual(context.audience_family, "municipal")
        self.assertEqual(context.sector, "public")
        self.assertEqual(context.sub_sector, "municipal_government")
        self.assertIn("resident_service", context.priority_impact_lenses)
        self.assertIn("WCAG 2.1 AA", context.benchmarking_references)
        self.assertIn("councillors", context.report_audience)
        self.assertTrue(context.scope_notes)
        self.assertIn("constructively", context.desired_tone_rules[0].lower())

    def test_parse_context_markdown_requires_sections(self) -> None:
        with self.assertRaises(ValueError):
            parse_context_markdown(
                """# Run Context

## Sector Classification
sector: public
sub_sector: municipal_government
jurisdiction: British Columbia, Canada
governing_framework:
  - Community Charter (BC)
"""
            )

    def test_parse_context_markdown_rejects_old_format(self) -> None:
        with self.assertRaises(ValueError):
            parse_context_markdown(
                """# Run Context

## Audience Family
municipal

## Primary Stakeholders
- council

## Organizational Goals
- improve access
"""
            )

    def test_parse_context_markdown_accepts_nonprofit_sector(self) -> None:
        context = parse_context_markdown(
            """# Run Context

## Sector Classification
sector: nonprofit
sub_sector: mission_driven_organization
jurisdiction: British Columbia, Canada
governing_framework:
  - Public trust expectations

## Benchmarking References
- WCAG 2.1 AA

## Report Audience
- board chair

## Primary Stakeholders
- board
- donors

## Organizational Goals
- improve access to services

## Priority Impact Lenses
- service_delivery
- custom_local_priority

## Primary Risks Or Sensitivities
- trust pressures

## Scope Notes
- This assessment covers the public website only in this run.

## Desired Tone
- mission-aware and clear

## Operator Notes
None
"""
        )
        self.assertEqual(context.audience_family, "nonprofit")
        self.assertIn("custom_local_priority", context.priority_impact_lenses)
        self.assertIn("board chair", context.report_audience)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

from webgrade.context import parse_context_markdown


class ReportContextTests(unittest.TestCase):
    def test_parse_context_markdown_uses_defaults(self) -> None:
        context = parse_context_markdown(
            """# Run Context

## Audience Family
municipal

## Primary Stakeholders
- council
- residents

## Organizational Goals
- improve access to information
- reduce avoidable office calls
"""
        )
        self.assertEqual(context.audience_family, "municipal")
        self.assertIn("resident_service", context.priority_impact_lenses)
        self.assertTrue(context.scope_notes)
        self.assertIn("plain-language", context.desired_tone.lower())

    def test_parse_context_markdown_requires_sections(self) -> None:
        with self.assertRaises(ValueError):
            parse_context_markdown(
                """# Run Context

## Audience Family
municipal
"""
            )


if __name__ == "__main__":
    unittest.main()

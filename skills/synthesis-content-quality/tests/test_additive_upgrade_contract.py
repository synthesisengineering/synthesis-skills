#!/usr/bin/env python3
"""Verify that the local August upgrade remains internally connected."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (REPO_ROOT / relative).read_text(encoding="utf-8")


class AdditiveUpgradeContractTests(unittest.TestCase):
    def test_new_content_quality_locators_are_unique(self) -> None:
        criteria = read("skills/synthesis-content-quality/references/detailed-criteria.md")
        substance = read("skills/synthesis-content-quality/references/substance-and-depth.md")
        for locator in ("A2-SUB-018", "A2-SUB-019"):
            with self.subTest(locator=locator):
                self.assertEqual(1, len(re.findall(rf"^### {locator}:", substance, re.MULTILINE)))
        for locator in (
            "A3-SS-010",
            "A3-SS-011",
            "A3-TF-008",
            "A3-BT-014",
            "A3-FA-009",
            "A3-FA-010",
            "A3-FA-011",
        ):
            with self.subTest(locator=locator):
                self.assertEqual(1, len(re.findall(rf"^### {locator}:", criteria, re.MULTILINE)))

    def test_additive_sibling_rules_are_present(self) -> None:
        pitfalls = read("skills/synthesis-writing-pitfalls/SKILL.md")
        craft = read("skills/synthesis-writing-craft/SKILL.md")
        clean = read("skills/synthesis-clean-text/SKILL.md")
        self.assertIn("23. **Unnecessary editorial intervention**", pitfalls)
        self.assertIn("**Preserve the source's causal mechanism.**", craft)
        self.assertIn("**Protect meaningful voice variation during editing.**", craft)
        self.assertIn("**Keep structure in proportion to the material.**", craft)
        self.assertIn("**Make every edit earn its place.**", craft)
        self.assertIn("synthesis-text-provenance", clean)
        self.assertIn("An undisclosed keyed token-selection scheme", clean)

    def test_authorship_and_candidate_boundaries_are_explicit(self) -> None:
        skill = read("skills/synthesis-content-quality/SKILL.md")
        ledger = read("skills/synthesis-content-quality/references/current-model-candidates.md")
        provenance = read("skills/synthesis-text-provenance/SKILL.md")
        self.assertIn("Authorship not established from prose cues.", skill)
        self.assertIn("Controlled-test quarantine", ledger)
        self.assertIn("Do not provide or execute a workflow whose objective is to", provenance)
        self.assertIn("optimize paraphrasing", provenance)


if __name__ == "__main__":
    unittest.main()

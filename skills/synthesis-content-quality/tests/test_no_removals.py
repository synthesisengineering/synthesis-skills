#!/usr/bin/env python3
"""Prove that the August upgrade preserves every baseline writing-rule line."""

from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "writing_quality_no_removals_baseline.json"


def line_hashes(text: str) -> list[str]:
    return [
        hashlib.sha256(line.encode("utf-8")).hexdigest()
        for line in text.splitlines()
        if line.strip()
    ]


def is_subsequence(baseline: list[str], current: list[str]) -> bool:
    iterator = iter(current)
    return all(any(candidate == required for candidate in iterator) for required in baseline)


def count(pattern: str, relative_path: str) -> int:
    text = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
    return len(re.findall(pattern, text, flags=re.MULTILINE))


class NoRemovalsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.baseline = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_every_baseline_file_and_nonblank_line_remains(self) -> None:
        failures: list[str] = []
        for relative, record in self.baseline["files"].items():
            path = REPO_ROOT / relative
            if not path.is_file():
                failures.append(f"missing file: {relative}")
                continue
            current = line_hashes(path.read_text(encoding="utf-8"))
            expected = record["ordered_nonblank_line_sha256"]
            if not is_subsequence(expected, current):
                failures.append(f"baseline line changed, removed, or reordered: {relative}")
        self.assertEqual([], failures, "\n".join(failures))

    def test_catalog_counts_never_fall_below_baseline(self) -> None:
        assertions = {
            "active A1": (
                r"^### A1-",
                "skills/synthesis-content-quality/references/model-family-fingerprints.md",
                108,
            ),
            "A2": (
                r"^## A2-",
                "skills/synthesis-content-quality/references/substance-and-depth.md",
                17,
            ),
            "A3": (
                r"^### A3-",
                "skills/synthesis-content-quality/references/detailed-criteria.md",
                76,
            ),
            "B2": (
                r"^### B2-COMBO-",
                "skills/synthesis-content-quality/references/combined-signal-fingerprints.md",
                86,
            ),
            "pitfalls": (r"^\d+\. \*\*", "skills/synthesis-writing-pitfalls/SKILL.md", 22),
            "craft principles": (r"^\*\*[^*]+\.\*\*", "skills/synthesis-writing-craft/SKILL.md", 30),
        }
        for label, (pattern, path, minimum) in assertions.items():
            with self.subTest(label=label):
                self.assertGreaterEqual(count(pattern, path), minimum)

    def test_baseline_covers_all_existing_markdown_files(self) -> None:
        roots = (
            "skills/synthesis-content-quality",
            "skills/synthesis-writing-pitfalls",
            "skills/synthesis-writing-craft",
            "skills/synthesis-clean-text",
        )
        current = {
            str(path.relative_to(REPO_ROOT))
            for root in roots
            for path in (REPO_ROOT / root).rglob("*.md")
            if "tests" not in path.parts
        }
        self.assertTrue(set(self.baseline["files"]).issubset(current))


if __name__ == "__main__":
    unittest.main()

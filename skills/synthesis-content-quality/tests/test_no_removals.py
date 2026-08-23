#!/usr/bin/env python3
"""Prove semantic preservation across the August writing-quality upgrade."""

from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "writing_quality_no_removals_baseline.json"
CORRECTIONS = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "writing_quality_evidence_corrections.json"
)


def line_hashes(text: str) -> list[str]:
    return [
        hashlib.sha256(line.encode("utf-8")).hexdigest()
        for line in text.splitlines()
        if line.strip()
    ]


def line_hash(line: str) -> str:
    return hashlib.sha256(line.encode("utf-8")).hexdigest()


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
        cls.corrections = json.loads(CORRECTIONS.read_text(encoding="utf-8"))

    def transformed_baseline(self, relative: str, expected: list[str]) -> list[str]:
        entries = sorted(
            (
                entry
                for entry in self.corrections["corrections"]
                if entry["path"] == relative
            ),
            key=lambda entry: entry["baseline_nonblank_start"],
        )
        transformed: list[str] = []
        cursor = 0
        for entry in entries:
            start = entry["baseline_nonblank_start"]
            original = entry["original_sha256"]
            replacement = entry["replacement_sha256"]
            self.assertGreaterEqual(start, cursor, f"overlapping correction: {relative}")
            self.assertEqual(
                original,
                [line_hash(line) for line in entry["original_text"]],
                f"original text/hash mismatch: {relative}@{start}",
            )
            self.assertEqual(
                replacement,
                [line_hash(line) for line in entry["replacement_text"]],
                f"replacement text/hash mismatch: {relative}@{start}",
            )
            self.assertEqual(
                original,
                expected[start : start + len(original)],
                f"correction does not match frozen baseline: {relative}@{start}",
            )
            self.assertTrue(entry["reason"].strip(), f"missing correction reason: {relative}@{start}")
            transformed.extend(expected[cursor:start])
            transformed.extend(replacement)
            cursor = start + len(original)
        transformed.extend(expected[cursor:])
        return transformed

    def test_every_baseline_file_and_nonblank_line_remains(self) -> None:
        failures: list[str] = []
        for relative, record in self.baseline["files"].items():
            path = REPO_ROOT / relative
            if not path.is_file():
                failures.append(f"missing file: {relative}")
                continue
            current = line_hashes(path.read_text(encoding="utf-8"))
            expected = self.transformed_baseline(
                relative,
                record["ordered_nonblank_line_sha256"],
            )
            if not is_subsequence(expected, current):
                failures.append(
                    "baseline line changed, removed, reordered, or changed outside "
                    f"the evidence-correction allowlist: {relative}"
                )
        self.assertEqual([], failures, "\n".join(failures))

    def test_correction_allowlist_is_exact_and_baseline_bound(self) -> None:
        self.assertEqual(1, self.corrections["schema_version"])
        self.assertEqual(
            self.baseline["baseline_revision"],
            self.corrections["baseline_revision"],
        )
        baseline_paths = set(self.baseline["files"])
        correction_paths = {entry["path"] for entry in self.corrections["corrections"]}
        self.assertTrue(correction_paths.issubset(baseline_paths))
        identities = [
            (entry["path"], entry["baseline_nonblank_start"])
            for entry in self.corrections["corrections"]
        ]
        self.assertEqual(len(identities), len(set(identities)))
        for relative in baseline_paths:
            self.transformed_baseline(
                relative,
                self.baseline["files"][relative]["ordered_nonblank_line_sha256"],
            )

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

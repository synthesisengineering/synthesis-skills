"""Deterministic tests for corpus_repetition.py.

Fixtures mirror the acceptance fixtures recorded for the batch-review
upgrades: shared constructions across documents are found, ordinary English
survives, boilerplate is classified separately, and the title budget flags a
replacement set that trades one formula for another (the cure-worse-than-
disease case).
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "corpus_repetition.py"


def run_tool(*args: str) -> tuple[int, dict]:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--json", *args],
        capture_output=True,
        text=True,
    )
    payload = json.loads(proc.stdout) if proc.stdout.strip() else {}
    return proc.returncode, payload


def write(path: Path, title: str, body: str) -> None:
    path.write_text(f"---\ntitle: \"{title}\"\n---\n\n{body}\n", encoding="utf-8")


class SharedRunTests(unittest.TestCase):
    def test_shared_construction_across_two_documents_is_found(self) -> None:
        with TemporaryDirectory() as td:
            d = Path(td)
            shared = (
                "the dashboard treats every unanswered decision as a delivery "
                "problem instead of naming the owner"
            )
            write(d / "a.md", "First article",
                  f"Opening paragraph. {shared}. More prose follows here.")
            write(d / "b.md", "Second article",
                  f"Different opening entirely. {shared}. Unrelated ending.")
            code, report = run_tool(str(d))
            self.assertEqual(code, 1)
            self.assertGreaterEqual(report["shared_run_total"], 1)
            top = report["shared_runs"][0]
            self.assertGreaterEqual(top["n"], 5)
            self.assertEqual(len(top["documents"]), 2)

    def test_ordinary_english_overlap_does_not_flag(self) -> None:
        with TemporaryDirectory() as td:
            d = Path(td)
            # Only short and function-word overlaps between these bodies.
            write(d / "a.md", "Alpha",
                  "It is one of the things we should have been doing all along, "
                  "and the team knew it.")
            write(d / "b.md", "Beta",
                  "It is one of the few cases where waiting paid off, and the "
                  "vendor knew nothing.")
            code, report = run_tool(str(d))
            self.assertEqual(report.get("shared_run_total", 0), 0)
            self.assertEqual(code, 0)

    def test_function_word_run_is_filtered_even_when_long(self) -> None:
        with TemporaryDirectory() as td:
            d = Path(td)
            filler = "it is what it was and it will be what it is"
            write(d / "a.md", "Alpha", f"Prose one. {filler}. Tail one.")
            write(d / "b.md", "Beta", f"Prose two. {filler}. Tail two.")
            code, report = run_tool(str(d))
            self.assertEqual(report.get("shared_run_total", 0), 0)
            self.assertEqual(code, 0)

    def test_high_df_run_is_classified_boilerplate_not_finding(self) -> None:
        with TemporaryDirectory() as td:
            d = Path(td)
            footer = (
                "this article is part of the synthesis engineering series on "
                "practical collaboration"
            )
            for i in range(4):
                write(d / f"doc{i}.md", f"Doc {i}",
                      f"Distinct body text number {i} with its own words. {footer}")
            code, report = run_tool(str(d))
            self.assertEqual(report.get("shared_run_total", 0), 0)
            self.assertTrue(report.get("boilerplate_candidates"))
            self.assertEqual(code, 0)

    def test_ignore_file_suppresses_known_phrase(self) -> None:
        with TemporaryDirectory() as td:
            d = Path(td)
            phrase = "the writer writes and the ai assists at every stage"
            write(d / "a.md", "Alpha", f"One. {phrase}. Done.")
            write(d / "b.md", "Beta", f"Two. {phrase}. Fin.")
            ignore = d / "ignore.txt"
            # ignore the exact maximal run as the tool reports it
            code_before, report_before = run_tool(str(d))
            self.assertEqual(code_before, 1)
            runs = [r["run"] for r in report_before["shared_runs"]]
            ignore.write_text("\n".join(runs), encoding="utf-8")
            code, report = run_tool(str(d), "--ignore-file", str(ignore))
            self.assertEqual(report.get("shared_run_total", 0), 0)
            self.assertEqual(code, 0)


class AdversarialRegressionTests(unittest.TestCase):
    """Regressions from the pre-release adversarial review."""

    def test_frontmatter_without_trailing_newline_is_still_frontmatter(self) -> None:
        with TemporaryDirectory() as td:
            d = Path(td)
            # last byte is the closing fence - no trailing newline
            (d / "a.md").write_text('---\ntitle: "Alpha"\ndescription: the migration playbook nobody updated after the flood\n---')
            (d / "b.md").write_text('---\ntitle: "Beta"\ndescription: the migration playbook nobody updated after the flood\n---')
            code, report = run_tool(str(d))
            self.assertEqual(report.get("shared_run_total", 0), 0,
                             "frontmatter must never be analyzed as body prose")
            self.assertEqual(report["titles"]["title_count"], 2)

    def test_distinct_pair_run_survives_longer_run_elsewhere(self) -> None:
        with TemporaryDirectory() as td:
            d = Path(td)
            long_run = "operate the restless crowd tonight before dawn breaks over town"
            short_run = "rate the restless crowd tonight"
            write(d / "fa.md", "FA", f"Alpha body. {long_run}. Tail A.")
            write(d / "fb.md", "FB", f"Beta body. {long_run}. Tail B.")
            write(d / "fc.md", "FC", f"Gamma body. They {short_run} again. Tail C.")
            write(d / "fd.md", "FD", f"Delta body. We {short_run} as well. Tail D.")
            code, report = run_tool(str(d))
            runs = [r["run"] for r in report["shared_runs"]]
            self.assertTrue(any(short_run in r for r in runs), runs)

    def test_two_doc_run_in_four_doc_corpus_stays_a_finding(self) -> None:
        with TemporaryDirectory() as td:
            d = Path(td)
            shared = "the dashboard treats every unanswered decision as a delivery problem"
            write(d / "a.md", "A", f"One. {shared}. Done.")
            write(d / "b.md", "B", f"Two. {shared}. Fin.")
            write(d / "c.md", "C", "Third document with entirely distinct prose about harbors.")
            write(d / "e.md", "E", "Fourth document about orchards and ledgers, unrelated.")
            code, report = run_tool(str(d))
            self.assertGreaterEqual(report.get("shared_run_total", 0), 1)
            self.assertEqual(code, 1)

    def test_content_duplicate_file_is_skipped_and_reported(self) -> None:
        with TemporaryDirectory() as td:
            d = Path(td)
            body = "A wholly unique essay body that appears in two mirrored trees."
            write(d / "orig.md", "Original", body)
            (d / "mirror").mkdir()
            write(d / "mirror" / "copy.md", "Original", body)
            code, report = run_tool(str(d))
            self.assertEqual(report["documents"], 1)
            self.assertEqual(len(report.get("skipped_content_duplicates", [])), 1)

    def test_strict_mode_exits_1_on_boilerplate(self) -> None:
        with TemporaryDirectory() as td:
            d = Path(td)
            footer = "this piece belongs to the synthesis engineering series on collaboration"
            for i in range(5):
                write(d / f"doc{i}.md", f"Doc {i}",
                      f"Body {i} with its own distinct words and phrasing. {footer}")
            code_default, _ = run_tool(str(d))
            code_strict, report = run_tool(str(d), "--strict")
            self.assertEqual(code_default, 0)
            self.assertEqual(code_strict, 1)
            self.assertTrue(report.get("boilerplate_candidates"))


class TitleShapeTests(unittest.TestCase):
    def _titles_file(self, d: Path, titles: list[str]) -> Path:
        f = d / "titles.txt"
        f.write_text("\n".join(titles), encoding="utf-8")
        return f

    def test_within_budget_set_passes(self) -> None:
        with TemporaryDirectory() as td:
            d = Path(td)
            titles = [
                "The Decision Ledger",
                "Delivery Speed Is Not Progress",
                "A Quarter Without New Dashboards",
                "What the Migration Actually Cost",
                "Idempotency Keys in Payment Systems",
                "The Meeting That Should Be a Memo",
            ]
            f = self._titles_file(d, titles)
            code, report = run_tool("--titles-file", str(f))
            self.assertEqual(report["titles"]["flags"], [])
            self.assertEqual(code, 0)

    def test_replacement_set_with_new_formula_flags(self) -> None:
        # Gap A fixture: a cure that reduces one formula while raising
        # another above budget must fail the same measurement.
        with TemporaryDirectory() as td:
            d = Path(td)
            titles = [
                "Your AI Agent Should Read the Codebase",
                "Your AI Assistant Should Write Less",
                "Your AI Workflow Should Slow Down",
                "Your AI Tools Should Earn Trust",
                "How AI Changed the Review",
                "Why AI Reviews Need Owners",
                "An AI Reviewer Worth Paying",
                "The AI Backlog Nobody Owns",
                "When AI Estimates Costs",
                "Where AI Belongs in Escalation",
                "Teaching AI the House Style",
                "Shipping Fast, Deciding Slowly",
                "The Case for Boring Deploys",
                "A Quarter Without Dashboards",
                "The Meeting That Was a Memo",
                "What the Migration Cost",
                "Notes From a Slow Rollout",
                "The Pilot Beat the Purchase",
                "A Ledger of Unmade Decisions",
                "The Quiet Cost of Retries",
                "Deciding Before Delegating",
                "The Owner Question",
                "Paper Manifests and Progress",
                "The Depot That Flooded",
                "One Metric Per Meeting",
                "The Roadmap Was a Wishlist",
                "Counting Stops, Missing Routes",
                "The Discount That Rushed Us",
                "A Vendor Reference Worth Checking",
                "The Contract Clause That Mattered",
            ]
            f = self._titles_file(d, titles)
            code, report = run_tool("--titles-file", str(f), "--basis", "30")
            flags = report["titles"]["flags"]
            self.assertTrue(any("your ai" in fl for fl in flags), flags)
            self.assertTrue(any("watch token 'ai'" in fl for fl in flags), flags)
            self.assertEqual(code, 1)

    def test_imperative_share_over_third_flags(self) -> None:
        with TemporaryDirectory() as td:
            d = Path(td)
            titles = [
                "Stop Adding Engineers",
                "Measure Decision Latency",
                "Write the Memo First",
                "Delete Half the Dashboards",
                "Ship the Small Version",
                "The Quiet Cost of Retries",
                "A Ledger for Unmade Decisions",
                "When Pilots Beat Purchases",
                "Notes on a Slow Migration",
            ]
            f = self._titles_file(d, titles)
            code, report = run_tool("--titles-file", str(f))
            flags = report["titles"]["flags"]
            self.assertTrue(any("imperative" in fl for fl in flags), flags)
            self.assertEqual(code, 1)

    def test_frontmatter_titles_are_collected_from_corpus(self) -> None:
        with TemporaryDirectory() as td:
            d = Path(td)
            write(d / "a.md", "The Decision Ledger", "Body one is here.")
            write(d / "b.md", "Delivery Speed Is Not Progress", "Body two is here.")
            code, report = run_tool(str(d))
            self.assertEqual(report["titles"]["title_count"], 2)


class UsageTests(unittest.TestCase):
    def test_no_input_is_usage_error(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(SCRIPT)], capture_output=True, text=True
        )
        self.assertEqual(proc.returncode, 2)

    def test_min_n_floor(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--min-n", "2", "x.md"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()

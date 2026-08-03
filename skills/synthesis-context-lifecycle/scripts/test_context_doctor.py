#!/usr/bin/env python3
"""Tests for the context doctor.

Every check gets a positive case (the defect is caught) and, where a false
alarm is plausible, a negative case (the healthy shape does NOT fire). The
negative cases matter as much as the positive ones: a context doctor that
cries wolf on dormant projects gets ignored, and an ignored guard protects
nothing.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent))

import context_doctor as cd  # noqa: E402

DOCTOR = Path(__file__).resolve().parent / "context_doctor.py"


def run_git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )


class Fixture:
    """A throwaway git repo shaped like a synthesis source.

    It has a real bare remote and pushes on every commit. That matters: a
    fixture with no remote would make "healthy" mean "context that has never
    left this machine", which is precisely the state the durability check
    exists to catch. An adversarial review found the earlier fixture doing
    exactly that and certifying it as healthy.
    """

    def __init__(self, root: Path, with_remote: bool = True):
        self.root = root
        self.projects = root / "projects"
        self.projects.mkdir(parents=True)
        run_git(root, "init", "-q", "-b", "main")
        run_git(root, "config", "user.email", "test@example.invalid")
        run_git(root, "config", "user.name", "Test")
        run_git(root, "config", "commit.gpgsign", "false")
        self.remote = root.parent / f"{root.name}-remote.git"
        self.has_remote = with_remote
        if with_remote:
            subprocess.run(
                ["git", "init", "-q", "--bare", str(self.remote)],
                check=True,
                capture_output=True,
                text=True,
            )
            run_git(root, "remote", "add", "origin", str(self.remote))

    def project(
        self,
        pid: str,
        context: str | None = "# P\n\n**Status:** Active\n",
        reference: str | None = None,
        sessions: dict[str, str] | None = None,
    ) -> Path:
        path = self.projects / pid
        path.mkdir(parents=True, exist_ok=True)
        if context is not None:
            (path / "CONTEXT.md").write_text(context, encoding="utf-8")
        if reference is not None:
            (path / "REFERENCE.md").write_text(reference, encoding="utf-8")
        if sessions:
            sdir = path / "sessions"
            sdir.mkdir(exist_ok=True)
            for name, body in sessions.items():
                (sdir / name).write_text(body, encoding="utf-8")
        return path

    def index(self, entries: list[dict]) -> None:
        lines = ["projects:"]
        for e in entries:
            lines.append(f"  - id: {e['id']}")
            for k, v in e.items():
                if k == "id":
                    continue
                lines.append(f"    {k}: '{v}'")
        (self.projects / "index.yaml").write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )

    def commit(
        self, message: str = "work", when: str | None = None, push: bool = True
    ) -> None:
        run_git(self.root, "add", "-A")
        subprocess.run(
            ["git", "-C", str(self.root), "commit", "-q", "-m", message],
            check=True,
            capture_output=True,
            text=True,
            env=self._env(when),
        )
        if push and self.has_remote:
            run_git(self.root, "push", "-q", "-u", "origin", "HEAD")

    def _env(self, when: str | None) -> dict:
        import os

        env = dict(os.environ)
        if when:
            stamp = f"{when}T12:00:00"
            env["GIT_AUTHOR_DATE"] = stamp
            env["GIT_COMMITTER_DATE"] = stamp
        return env

    def audit(self, *extra: str) -> dict:
        import os

        # Isolate SYNTHESIS_HOME: fixture runs must never touch the real
        # user's caches. (The real report cache was in fact overwritten by
        # this suite before this isolation existed.)
        proc = subprocess.run(
            [sys.executable, str(DOCTOR), "--source", str(self.root), "--json", *extra],
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "SYNTHESIS_HOME": str(self.root.parent / "shome")},
        )
        return {"code": proc.returncode, "data": json.loads(proc.stdout or "{}")}


def checks_in(result: dict) -> set[str]:
    return {f["check"] for f in result["data"].get("findings", [])}


class ContextDoctorTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.fx = Fixture(Path(self._tmp.name) / "source")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    # --- healthy baseline --------------------------------------------------

    def test_healthy_project_passes(self):
        self.fx.project("alpha")
        self.fx.index([{"id": "alpha", "status": "active"}])
        self.fx.commit()
        r = self.fx.audit()
        self.assertEqual(r["code"], 0, r["data"])
        self.assertTrue(r["data"]["ok"])

    # --- tier structure ----------------------------------------------------

    def test_missing_context_is_a_defect(self):
        self.fx.project("alpha", context=None)
        (self.fx.projects / "alpha" / "notes.md").write_text("x", encoding="utf-8")
        self.fx.index([{"id": "alpha", "status": "active"}])
        self.fx.commit()
        r = self.fx.audit()
        self.assertIn("context-present", checks_in(r))
        self.assertEqual(r["code"], 1)

    def test_indexed_project_with_no_directory_is_a_defect(self):
        self.fx.project("alpha")
        self.fx.index(
            [{"id": "alpha", "status": "active"}, {"id": "ghost", "status": "active"}]
        )
        self.fx.commit()
        findings = self.fx.audit()["data"]["findings"]
        self.assertTrue(any(f["project"] == "ghost" for f in findings))

    def test_reference_expected_once_sessions_accumulate(self):
        self.fx.project(
            "alpha",
            sessions={
                "2026-01.md": "### 2026-01-05: one\n\n### 2026-01-12: two\n",
            },
        )
        self.fx.index([{"id": "alpha", "status": "active"}])
        self.fx.commit()
        self.assertIn("reference-present", checks_in(self.fx.audit()))

    def test_reference_not_expected_for_a_young_project(self):
        self.fx.project("alpha", sessions={"2026-01.md": "### 2026-01-05: one\n"})
        self.fx.index([{"id": "alpha", "status": "active"}])
        self.fx.commit()
        self.assertNotIn("reference-present", checks_in(self.fx.audit()))

    # --- budgets -----------------------------------------------------------

    def test_context_over_active_budget(self):
        body = "# P\n\n**Status:** Active\n" + "\nfiller\n" * 200
        self.fx.project("alpha", context=body)
        self.fx.index([{"id": "alpha", "status": "active"}])
        self.fx.commit()
        self.assertIn("context-budget", checks_in(self.fx.audit()))

    def test_completed_budget_is_tighter_than_active(self):
        body = "# P\n\n**Status:** Completed\n" + "line\n" * 100
        self.fx.project("alpha", context=body)
        self.fx.index(
            [{"id": "alpha", "status": "completed", "completed_date": "2026-01-01"}]
        )
        self.fx.commit()
        checks = checks_in(self.fx.audit())
        self.assertIn("context-budget", checks)  # 100 lines > completed budget of 80

    def test_reference_over_budget_is_a_warning_not_a_defect(self):
        self.fx.project(
            "alpha",
            reference="# R\n" + "fact\n" * 400,
            sessions={"2026-01.md": "### 2026-01-05: a\n\n### 2026-01-12: b\n"},
        )
        self.fx.index([{"id": "alpha", "status": "active"}])
        self.fx.commit()
        r = self.fx.audit()
        sev = {
            f["check"]: f["severity"]
            for f in r["data"]["findings"]
            if f["check"] == "reference-budget"
        }
        self.assertEqual(sev.get("reference-budget"), "warning")
        self.assertEqual(r["code"], 0, "warnings alone must not fail the run")

    def test_warnings_as_defects_flag_escalates(self):
        self.fx.project(
            "alpha",
            reference="# R\n" + "fact\n" * 400,
            sessions={"2026-01.md": "### 2026-01-05: a\n\n### 2026-01-12: b\n"},
        )
        self.fx.index([{"id": "alpha", "status": "active"}])
        self.fx.commit()
        self.assertEqual(self.fx.audit("--warnings-as-defects")["code"], 1)

    # --- cross-tier agreement ---------------------------------------------

    def test_status_disagreement_is_caught(self):
        self.fx.project("alpha", context="# P\n\n**Status:** COMPLETE\n")
        self.fx.index([{"id": "alpha", "status": "active"}])
        self.fx.commit()
        self.assertIn("status-agreement", checks_in(self.fx.audit()))

    def test_status_agreement_when_both_say_completed(self):
        self.fx.project("alpha", context="# P\n\n**Status:** Completed\n")
        self.fx.index(
            [{"id": "alpha", "status": "completed", "completed_date": "2026-01-01"}]
        )
        self.fx.commit()
        self.assertNotIn("status-agreement", checks_in(self.fx.audit()))

    def test_not_complete_phrasing_does_not_read_as_completed(self):
        self.fx.project("alpha", context="# P\n\n**Status:** not complete yet\n")
        self.fx.index([{"id": "alpha", "status": "active"}])
        self.fx.commit()
        self.assertNotIn("status-agreement", checks_in(self.fx.audit()))

    def test_completed_without_date_is_a_warning(self):
        self.fx.project("alpha", context="# P\n\n**Status:** Completed\n")
        self.fx.index([{"id": "alpha", "status": "completed"}])
        self.fx.commit()
        self.assertIn("completed-date", checks_in(self.fx.audit()))

    # --- freshness ---------------------------------------------------------

    def test_stale_last_session_is_caught(self):
        self.fx.project("alpha")
        self.fx.index(
            [{"id": "alpha", "status": "active", "last_session": "2020-01-01"}]
        )
        self.fx.commit("real work", when="2026-06-01")
        self.assertIn("last-session-freshness", checks_in(self.fx.audit()))

    def test_stale_context_header_is_caught(self):
        self.fx.project(
            "alpha", context="# P\n\n**Status:** Active\n**Last session:** 2020-01-01\n"
        )
        self.fx.index([{"id": "alpha", "status": "active"}])
        self.fx.commit("real work", when="2026-06-01")
        self.assertIn("context-header-freshness", checks_in(self.fx.audit()))

    def test_bulk_maintenance_commit_does_not_fake_a_session(self):
        """The regression that mattered: a repo-wide sweep is not work.

        Without this, every dormant project looks stale the moment a path
        migration or restructure touches the whole tree.
        """
        for pid in ("alpha", "beta", "gamma", "delta", "epsilon"):
            self.fx.project(
                pid,
                context=f"# {pid}\n\n**Status:** Active\n**Last session:** 2026-01-05\n",
            )
        self.fx.index(
            [
                {"id": p, "status": "active", "last_session": "2026-01-05"}
                for p in ("alpha", "beta", "gamma", "delta", "epsilon")
            ]
        )
        self.fx.commit("real work", when="2026-01-05")

        # One commit touching every project: maintenance, not a session.
        for pid in ("alpha", "beta", "gamma", "delta", "epsilon"):
            (self.fx.projects / pid / "CONTEXT.md").write_text(
                f"# {pid}\n\n**Status:** Active\n**Last session:** 2026-01-05\n\n",
                encoding="utf-8",
            )
        self.fx.commit("Apply tiered context architecture to all", when="2026-06-01")

        checks = checks_in(self.fx.audit())
        self.assertNotIn("last-session-freshness", checks)
        self.assertNotIn("context-header-freshness", checks)

    def test_single_project_commit_after_a_bulk_sweep_still_counts(self):
        for pid in ("alpha", "beta", "gamma", "delta", "epsilon"):
            self.fx.project(pid)
        self.fx.index(
            [
                {"id": p, "status": "active", "last_session": "2026-01-05"}
                for p in ("alpha", "beta", "gamma", "delta", "epsilon")
            ]
        )
        self.fx.commit("bulk", when="2026-01-05")
        (self.fx.projects / "alpha" / "CONTEXT.md").write_text(
            "# alpha\n\n**Status:** Active\n\nnew work\n", encoding="utf-8"
        )
        self.fx.commit("alpha session", when="2026-06-01")
        findings = self.fx.audit()["data"]["findings"]
        stale = [f for f in findings if f["check"] == "last-session-freshness"]
        self.assertEqual([f["project"] for f in stale], ["alpha"])

    # --- durability --------------------------------------------------------

    def test_uncommitted_context_is_a_defect(self):
        self.fx.project("alpha")
        self.fx.index([{"id": "alpha", "status": "active"}])
        self.fx.commit()
        (self.fx.projects / "alpha" / "CONTEXT.md").write_text(
            "# P\n\n**Status:** Active\n\nedited but not committed\n", encoding="utf-8"
        )
        self.assertIn("uncommitted-context", checks_in(self.fx.audit()))

    # --- durability: the critical hole the refute panel found --------------

    def test_never_pushed_branch_is_a_defect(self):
        """The critical finding: no upstream used to report HEALTHY."""
        self.fx.project("alpha")
        self.fx.index([{"id": "alpha", "status": "active"}])
        self.fx.commit(push=False)
        r = self.fx.audit()
        self.assertIn("unpushed-context", checks_in(r))
        self.assertEqual(r["code"], 1)

    def test_repo_with_no_remote_is_a_defect(self):
        fx = Fixture(Path(self._tmp.name) / "noremote", with_remote=False)
        fx.project("alpha")
        fx.index([{"id": "alpha", "status": "active"}])
        fx.commit()
        r = fx.audit()
        self.assertIn("unpushed-context", checks_in(r))
        self.assertEqual(r["code"], 1)

    def test_commits_ahead_of_upstream_are_a_defect(self):
        self.fx.project("alpha")
        self.fx.index([{"id": "alpha", "status": "active"}])
        self.fx.commit()
        (self.fx.projects / "alpha" / "CONTEXT.md").write_text(
            "# P\n\n**Status:** Active\n\nmore\n", encoding="utf-8"
        )
        self.fx.commit(push=False)
        self.assertIn("unpushed-context", checks_in(self.fx.audit()))

    def test_gitignored_context_file_is_a_defect(self):
        self.fx.project("alpha")
        self.fx.index([{"id": "alpha", "status": "active"}])
        (self.fx.root / ".gitignore").write_text("CONTEXT.md\n", encoding="utf-8")
        self.fx.commit()
        r = self.fx.audit()
        self.assertIn("untracked-context", checks_in(r))
        self.assertEqual(r["code"], 1)

    def test_uncommitted_index_yaml_is_caught(self):
        self.fx.project("alpha")
        self.fx.index([{"id": "alpha", "status": "active"}])
        self.fx.commit()
        (self.fx.projects / "index.yaml").write_text(
            "projects:\n  - id: alpha\n    status: 'completed'\n", encoding="utf-8"
        )
        self.assertIn("uncommitted-context", checks_in(self.fx.audit()))

    def test_project_mode_also_checks_durability(self):
        self.fx.project("alpha")
        self.fx.index([{"id": "alpha", "status": "active"}])
        self.fx.commit(push=False)
        proc = subprocess.run(
            [
                sys.executable,
                str(DOCTOR),
                "--project",
                str(self.fx.projects / "alpha"),
                "--json",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        data = json.loads(proc.stdout)
        self.assertIn(
            "unpushed-context", {f["check"] for f in data.get("findings", [])}
        )

    # --- fail-closed behavior ---------------------------------------------

    def test_unreadable_source_exits_two_not_zero(self):
        missing = Path(self._tmp.name) / "nope"
        proc = subprocess.run(
            [sys.executable, str(DOCTOR), "--source", str(missing), "--json"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertFalse(json.loads(proc.stdout)["ok"])

    def test_non_git_source_exits_two(self):
        plain = Path(self._tmp.name) / "plain"
        (plain / "projects").mkdir(parents=True)
        (plain / "projects" / "alpha").mkdir()
        proc = subprocess.run(
            [sys.executable, str(DOCTOR), "--source", str(plain), "--json"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 2)

    def test_projects_without_index_is_a_defect_not_a_pass(self):
        self.fx.project("alpha")
        self.fx.commit()
        r = self.fx.audit()
        self.assertEqual(r["code"], 1)
        self.assertIn("status-agreement", checks_in(r))

    def test_empty_source_with_no_index_is_not_an_error(self):
        (self.fx.projects / ".keep").write_text("", encoding="utf-8")
        self.fx.commit()
        self.assertEqual(self.fx.audit()["code"], 0)

    # --- report cache -------------------------------------------------------

    def test_full_run_writes_report_cache(self):
        import os
        self.fx.project("alpha")
        self.fx.index([{"id": "alpha", "status": "active"}])
        self.fx.commit()
        home = Path(self._tmp.name) / "synthesis-home"
        home.mkdir()
        (home / "console.yaml").write_text(
            "sources:\n"
            "  - name: fx\n"
            f"    root: {self.fx.root}\n"
            "    projects_dir: projects\n",
            encoding="utf-8",
        )
        proc = subprocess.run(
            [sys.executable, str(DOCTOR), "--quiet"],
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "SYNTHESIS_HOME": str(home)},
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        cache = home / "context-doctor" / "last-report.json"
        self.assertTrue(cache.is_file())
        data = json.loads(cache.read_text())
        self.assertTrue(data["ok"])
        self.assertIn("generated_at", data)
        self.assertEqual(data["projects_audited"], 1)

    def test_explicit_source_run_never_touches_the_cache(self):
        """The regression that happened for real: fixture --source runs
        overwrote the user's corpus cache minutes after the cache shipped."""
        import os
        self.fx.project("alpha")
        self.fx.index([{"id": "alpha", "status": "active"}])
        self.fx.commit()
        home = Path(self._tmp.name) / "synthesis-home2"
        subprocess.run(
            [sys.executable, str(DOCTOR), "--source", str(self.fx.root), "--quiet"],
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "SYNTHESIS_HOME": str(home)},
        )
        self.assertFalse((home / "context-doctor" / "last-report.json").exists())

    def test_project_mode_never_touches_the_cache(self):
        """A one-project result must not masquerade as corpus state."""
        import os
        self.fx.project("alpha")
        self.fx.index([{"id": "alpha", "status": "active"}])
        self.fx.commit()
        home = Path(self._tmp.name) / "synthesis-home"
        subprocess.run(
            [
                sys.executable,
                str(DOCTOR),
                "--project",
                str(self.fx.projects / "alpha"),
                "--quiet",
            ],
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "SYNTHESIS_HOME": str(home)},
        )
        self.assertFalse((home / "context-doctor" / "last-report.json").exists())

    # --- parser ------------------------------------------------------------

    def test_fallback_parser_matches_expected_fields(self):
        text = (
            "projects:\n"
            "  - id: alpha  # trailing comment\n"
            "    status: completed\n"
            "    completed_date: '2026-01-01'\n"
            "    description: >\n"
            "      folded text that must not become a field\n"
            "  - id: beta\n"
            "    status: active\n"
        )
        entries = cd.parse_mapping_list(text, "projects")
        self.assertEqual([e["id"] for e in entries], ["alpha", "beta"])
        self.assertEqual(entries[0]["status"], "completed")
        self.assertEqual(entries[0]["completed_date"], "2026-01-01")

    def test_status_wins_over_phase_wording(self):
        """Regression: 'Phase: Triage — inventory complete' with Status Active.

        Found by the doctor on a real project the day it shipped. Reading Phase
        as equal to Status turned an ordinary sentence into a false completion
        claim, which then dragged the budget check to the tighter completed
        limit as well — one misread produced two false defects.
        """
        self.fx.project(
            "alpha",
            context=(
                "# P\n\n**Phase:** Triage — inventory complete, nothing shipped\n"
                "**Status:** Active\n"
            ),
        )
        self.fx.index([{"id": "alpha", "status": "active"}])
        self.fx.commit()
        self.assertNotIn("status-agreement", checks_in(self.fx.audit()))

    def test_completion_words_match_on_word_boundaries(self):
        for value, expected in [
            ("**Status:** Completeness review underway", None),
            ("**Status:** Incomplete", None),
            ("**Status:** not yet complete", False),
            ("**Status:** Complete", True),
        ]:
            self.assertEqual(cd.context_declares_completed(value), expected, value)

    def test_leading_clause_wins_over_trailing_completion_words(self):
        """Real headers from the 2026-08-03 corpus remediation: the author's
        verdict is the leading clause; completion vocabulary after the first
        delimiter describes sub-parts, not the project."""
        for value, expected in [
            ("**Status:** Active — **Phase 4 ... is now COMPLETE as of 2026-07-17.**", False),
            ("**Status:** active, essentially complete — migration verified", False),
            ("**Status:** Active (transitioning to completed after deploy verification)", False),
            ("**Status:** Active — Budget v1 complete + UX'd", False),
            ("**Status:** COMPLETE | **Last Updated:** 2026-02-25", True),
            ("**Status:** Completed and live-verified", True),
            ("**Status:** Done — retro written", True),
        ]:
            self.assertEqual(cd.context_declares_completed(value), expected, value)

    def test_completion_detection_handles_real_headers(self):
        self.assertTrue(cd.context_declares_completed("**Status:** COMPLETE"))
        self.assertTrue(
            cd.context_declares_completed("**Status:** Completed and live-verified")
        )
        self.assertFalse(cd.context_declares_completed("**Status:** Active"))
        self.assertFalse(cd.context_declares_completed("**Status:** Paused"))
        self.assertIsNone(cd.context_declares_completed("no header here"))


if __name__ == "__main__":
    unittest.main(verbosity=2)

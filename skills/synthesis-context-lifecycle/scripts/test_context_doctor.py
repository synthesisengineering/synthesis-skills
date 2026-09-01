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
        run_git(root, "config", "core.hooksPath", "/dev/null")
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
        reference_topics: dict[str, str] | None = None,
    ) -> Path:
        path = self.projects / pid
        path.mkdir(parents=True, exist_ok=True)
        if context is not None:
            (path / "CONTEXT.md").write_text(context, encoding="utf-8")
        if reference is not None:
            (path / "REFERENCE.md").write_text(reference, encoding="utf-8")
        if reference_topics:
            rdir = path / "reference"
            rdir.mkdir(exist_ok=True)
            for name, body in reference_topics.items():
                (rdir / name).write_text(body, encoding="utf-8")
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
                # Booleans must survive as booleans. Quoting them would make
                # `bounded: false` the string "false", which is truthy — the
                # fixture would then silently disagree with every real
                # index.yaml and certify the standing-project path as working
                # when it was never exercised.
                if isinstance(v, bool):
                    lines.append(f"    {k}: {str(v).lower()}")
                else:
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

    # --- executable working-state tier ------------------------------------

    def test_artifact_cites_missing_script_warns(self):
        project = self.fx.project("alpha")
        artifacts = project / "resources" / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "result.md").write_text(
            "Regenerate with `resources/scripts/rebuild.py`.\n", encoding="utf-8"
        )
        self.fx.index([{"id": "alpha", "status": "active"}])
        self.fx.commit()

        result = self.fx.audit()
        finding = next(
            item
            for item in result["data"]["findings"]
            if item["check"] == "artifact-cites-missing-script"
        )
        self.assertEqual(finding["severity"], "warning")
        self.assertIn("rebuild.py", finding["message"])
        self.assertEqual(result["code"], 0)

    def test_artifact_cites_existing_script_passes(self):
        project = self.fx.project("alpha")
        artifacts = project / "resources" / "artifacts"
        scripts = project / "resources" / "scripts"
        artifacts.mkdir(parents=True)
        scripts.mkdir(parents=True)
        (artifacts / "result.md").write_text(
            "Regenerate with `resources/scripts/rebuild.py`.\n", encoding="utf-8"
        )
        (scripts / "rebuild.py").write_text("print('ok')\n", encoding="utf-8")
        self.fx.index([{"id": "alpha", "status": "active"}])
        self.fx.commit()

        self.assertNotIn("artifact-cites-missing-script", checks_in(self.fx.audit()))

    def test_artifact_cites_symlinked_script_warns(self):
        project = self.fx.project("alpha")
        artifacts = project / "resources" / "artifacts"
        scripts = project / "resources" / "scripts"
        artifacts.mkdir(parents=True)
        scripts.mkdir(parents=True)
        outside = self.fx.root.parent / "outside.py"
        outside.write_text("print('outside')\n", encoding="utf-8")
        (scripts / "rebuild.py").symlink_to(outside)
        (artifacts / "result.md").write_text(
            "Regenerate with `resources/scripts/rebuild.py`.\n", encoding="utf-8"
        )
        self.fx.index([{"id": "alpha", "status": "active"}])
        self.fx.commit()

        self.assertIn("artifact-cites-missing-script", checks_in(self.fx.audit()))

    def test_cross_project_script_citation_is_not_a_local_missing_script(self):
        project = self.fx.project("alpha")
        artifacts = project / "resources" / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "result.md").write_text(
            "See `projects/other/resources/scripts/rebuild.py`.\n",
            encoding="utf-8",
        )
        self.fx.index([{"id": "alpha", "status": "active"}])
        self.fx.commit()

        self.assertNotIn("artifact-cites-missing-script", checks_in(self.fx.audit()))

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

    def test_local_readiness_reports_uncommitted_context_as_warning(self):
        self.fx.project("alpha")
        self.fx.index([{"id": "alpha", "status": "active"}])
        self.fx.commit()
        (self.fx.projects / "alpha" / "CONTEXT.md").write_text(
            "# P\n\n**Status:** Active\n\nlocal handoff\n", encoding="utf-8"
        )

        result = self.fx.audit("--readiness", "local")

        finding = next(
            item
            for item in result["data"]["findings"]
            if item["check"] == "uncommitted-context"
        )
        self.assertEqual(finding["severity"], "warning")
        self.assertEqual(result["code"], 0)

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

    def test_local_readiness_reports_ahead_context_as_warning(self):
        self.fx.project("alpha")
        self.fx.index([{"id": "alpha", "status": "active"}])
        self.fx.commit()
        (self.fx.projects / "alpha" / "CONTEXT.md").write_text(
            "# P\n\n**Status:** Active\n\ncommitted locally\n", encoding="utf-8"
        )
        self.fx.commit(push=False)

        result = self.fx.audit("--readiness", "local")

        finding = next(
            item
            for item in result["data"]["findings"]
            if item["check"] == "unpushed-context"
        )
        self.assertEqual(finding["severity"], "warning")
        self.assertEqual(result["code"], 0)

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

    # --- status vocabulary -------------------------------------------------

    def test_unknown_status_is_a_defect(self):
        """An unrecognised status silently disables every check keyed off it."""
        self.fx.project("alpha", context="# P\n\n**Status:** Active\n")
        self.fx.index([{"id": "alpha", "status": "wibble"}])
        self.fx.commit()
        self.assertIn("status-vocabulary", checks_in(self.fx.audit()))

    def test_retired_status_is_a_warning_naming_its_replacement(self):
        self.fx.project("alpha", context="# P\n\n**Status:** Active\n")
        self.fx.index([{"id": "alpha", "status": "ongoing"}])
        self.fx.commit()
        findings = self.fx.audit()["data"]["findings"]
        found = [f for f in findings if f["check"] == "status-vocabulary"]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["severity"], "warning")
        self.assertIn("bounded", found[0]["message"])

    def test_canonical_statuses_produce_no_vocabulary_finding(self):
        for status in sorted(cd.CANONICAL_STATUSES):
            with self.subTest(status=status):
                fx = Fixture(Path(self._tmp.name) / ("vocab-" + status))
                terminal = status in cd.TERMINAL_STATUSES
                ctx = ("# P\n\n**Status:** Completed\n" if terminal
                       else "# P\n\n**Status:** Active\n")
                fx.project("alpha", context=ctx)
                entry = {"id": "alpha", "status": status}
                if terminal:
                    entry["completed_date"] = "2026-01-01"
                fx.index([entry])
                fx.commit()
                self.assertNotIn("status-vocabulary", checks_in(fx.audit()))

    def test_superseded_is_terminal(self):
        """Regression, found 2026-08-28 on a real corpus.

        `superseded` was absent from the terminal set AND from the header
        parser's completion words. A superseded project therefore parsed as
        making no completion claim at all: it sat permanently as
        `record-unreadable` and never received its cross-tier check. Five real
        projects were silently exempt. This pins both halves of the fix.
        """
        self.assertIn("superseded", cd.TERMINAL_STATUSES)
        self.assertTrue(cd.context_declares_completed("**Status:** Superseded by `x`"))
        self.assertTrue(cd.context_declares_completed("**Status:** Archived - closed"))

    def test_superseded_project_gets_its_cross_tier_check(self):
        self.fx.project("alpha", context="# P\n\n**Status:** Superseded by `beta`\n")
        self.fx.index([{"id": "alpha", "status": "superseded",
                        "completed_date": "2026-01-01"}])
        self.fx.commit()
        checks = checks_in(self.fx.audit())
        self.assertNotIn("record-unreadable", checks)
        self.assertNotIn("status-agreement", checks)


class LifecycleApplicabilityTests(unittest.TestCase):
    """Checks that only have meaning about work in progress must not fire on
    projects nobody is working.

    Measured on a 175-project corpus, 98% of `freshness-unverifiable` and 90%
    of `record-unreadable` were raised against dormant projects. Every one was
    unactionable, and 193 unactioned warnings is the fail-open state the doctor
    exists to prevent. The negative cases below are the point of this class;
    the positive ones prove the checks still work where they apply.
    """

    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.fx = Fixture(Path(self._tmp.name) / "src")

    def tearDown(self):
        self._tmp.cleanup()

    def _sweep_only_project(self, pid: str, status: str, **entry):
        """A project whose every commit also touches enough other projects to
        be classified as a repo-wide sweep — the shape that makes freshness
        genuinely unverifiable."""
        self.fx.project(pid, context=f"# P\n\n**Status:** {status.title()}\n")
        for filler in range(cd.BULK_COMMIT_PROJECT_THRESHOLD + 2):
            self.fx.project(f"{pid}-filler{filler}")
        self.fx.index([{"id": pid, "status": status, **entry}] +
                      [{"id": f"{pid}-filler{i}", "status": "active"}
                       for i in range(cd.BULK_COMMIT_PROJECT_THRESHOLD + 2)])
        self.fx.commit("repo-wide sweep")

    def _checks_for(self, result: dict, pid: str) -> set[str]:
        """Checks raised against ONE project. The filler projects that make a
        commit look like a sweep are themselves active and legitimately raise
        this warning, so a corpus-wide assertion would pass or fail for the
        wrong reason."""
        return {f["check"] for f in result["data"].get("findings", [])
                if f["project"] == pid}

    def test_freshness_unverifiable_fires_on_an_active_project(self):
        self._sweep_only_project("alpha", "active")
        self.assertIn("freshness-unverifiable",
                      self._checks_for(self.fx.audit(), "alpha"))

    def test_freshness_unverifiable_silent_on_completed(self):
        self._sweep_only_project("alpha", "completed", completed_date="2026-01-01")
        self.assertNotIn("freshness-unverifiable",
                         self._checks_for(self.fx.audit(), "alpha"))

    def test_freshness_unverifiable_silent_on_paused(self):
        self._sweep_only_project("alpha", "paused")
        self.assertNotIn("freshness-unverifiable",
                         self._checks_for(self.fx.audit(), "alpha"))

    def test_unset_status_is_treated_as_live_not_dormant(self):
        """The suppression must never swallow a project whose state we cannot
        read — those are the records most likely to be wrong."""
        self.assertFalse(cd.project_is_dormant("", None))
        self.assertFalse(cd.project_is_dormant("wat", None))
        self.assertTrue(cd.project_is_dormant("paused", None))
        self.assertTrue(cd.project_is_dormant("completed", None))

    def test_record_unreadable_silent_on_dormant_but_fires_when_active(self):
        headerless = "# P\n\nsome prose with no status header\n"
        self.fx.project("alpha", context=headerless)
        self.fx.project("beta", context=headerless)
        self.fx.index([{"id": "alpha", "status": "completed",
                        "completed_date": "2026-01-01"},
                       {"id": "beta", "status": "active"}])
        self.fx.commit()
        found = {(f["project"], f["check"])
                 for f in self.fx.audit()["data"]["findings"]}
        self.assertIn(("beta", "record-unreadable"), found)
        self.assertNotIn(("alpha", "record-unreadable"), found)

    def test_terminal_project_still_being_worked_is_reported(self):
        """The inversion that makes the suppression safe: a project declared
        finished but still receiving session commits is a live record error,
        and it was invisible before this check existed."""
        self.fx.project("alpha", context="# P\n\n**Status:** Completed\n")
        self.fx.index([{"id": "alpha", "status": "completed",
                        "completed_date": "2026-01-01",
                        "last_session": "2026-01-01"}])
        self.fx.commit("real work long after completion", when="2026-06-01")
        checks = checks_in(self.fx.audit())
        self.assertIn("terminal-project-active", checks)

    def test_terminal_project_with_matching_record_is_quiet(self):
        self.fx.project("alpha", context="# P\n\n**Status:** Completed\n")
        self.fx.index([{"id": "alpha", "status": "completed",
                        "completed_date": "2026-06-01",
                        "last_session": "2026-06-01"}])
        self.fx.commit("closing commit", when="2026-06-01")
        self.assertNotIn("terminal-project-active", checks_in(self.fx.audit()))

    def test_the_commits_that_close_a_project_are_not_evidence_it_is_open(self):
        """Found by reading the nine findings this check first raised: two were
        a project whose every commit landed on its own completion date. Closing
        is work — the archive pass, the trim to budget — and it lands after the
        last *working* session by design. Anchored on last_session, the act of
        finishing reads as proof of not being finished."""
        self.fx.project("alpha", context="# P\n\n**Status:** Completed\n")
        self.fx.index([{"id": "alpha", "status": "completed",
                        "completed_date": "2026-06-01",
                        "last_session": "2024-12-17"}])
        self.fx.commit("archive the record and trim it to budget",
                       when="2026-06-01")
        self.assertNotIn("terminal-project-active",
                         self._checks_for(self.fx.audit(), "alpha"))

    def test_work_after_the_declared_completion_still_fires(self):
        """The tightened anchor must not buy quiet by dropping the question."""
        self.fx.project("alpha", context="# P\n\n**Status:** Completed\n")
        self.fx.index([{"id": "alpha", "status": "completed",
                        "completed_date": "2026-06-01",
                        "last_session": "2026-06-01"}])
        self.fx.commit("work that resumed after the close", when="2026-08-20")
        self.assertIn("terminal-project-active",
                      self._checks_for(self.fx.audit(), "alpha"))

    def test_missing_completed_date_falls_back_rather_than_falling_silent(self):
        """A record too incomplete to anchor on is the one most likely to be
        wrong, so the check keeps asking against last_session."""
        self.fx.project("alpha", context="# P\n\n**Status:** Completed\n")
        self.fx.index([{"id": "alpha", "status": "completed",
                        "last_session": "2026-01-01"}])
        self.fx.commit("real work long after completion", when="2026-06-01")
        self.assertIn("terminal-project-active",
                      self._checks_for(self.fx.audit(), "alpha"))


class ReferenceShardTests(unittest.TestCase):
    """Semantic memory outgrows one file exactly as episodic memory does.

    `sessions/` solved that for the episodic tier; `reference/` is the same
    move one tier over. A standing project's REFERENCE.md has no natural
    ceiling, so telling its owner the scope is too broad is advice that cannot
    be taken — the remedy has to be structural.
    """

    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.fx = Fixture(Path(self._tmp.name) / "src")

    def tearDown(self):
        self._tmp.cleanup()

    def test_bounded_project_over_budget_gets_the_scope_remedy(self):
        self.fx.project("alpha", reference="x\n" * 400)
        self.fx.index([{"id": "alpha", "status": "active"}])
        self.fx.commit()
        checks = checks_in(self.fx.audit())
        self.assertIn("reference-budget", checks)
        self.assertNotIn("reference-shard", checks)

    def test_standing_project_over_budget_gets_the_shard_remedy(self):
        self.fx.project("alpha", reference="x\n" * 400)
        self.fx.index([{"id": "alpha", "status": "active", "bounded": False}])
        self.fx.commit()
        checks = checks_in(self.fx.audit())
        self.assertIn("reference-shard", checks)
        self.assertNotIn("reference-budget", checks)

    def test_bounded_defaults_true_when_unset(self):
        """1,296 of 1,306 corpus projects leave `bounded` unset. Their
        behaviour must not change, or adoption becomes a migration."""
        self.fx.project("alpha", reference="x\n" * 400)
        self.fx.index([{"id": "alpha", "status": "active"}])
        self.fx.commit()
        self.assertIn("reference-budget", checks_in(self.fx.audit()))

    def test_sharded_project_is_judged_as_index_plus_topics(self):
        self.fx.project(
            "alpha",
            reference="# Reference\n\n- [ops](reference/ops.md)\n",
            reference_topics={"ops.md": "y\n" * 40},
        )
        self.fx.index([{"id": "alpha", "status": "active", "bounded": False}])
        self.fx.commit()
        checks = checks_in(self.fx.audit())
        for noisy in ("reference-budget", "reference-shard",
                      "reference-index-budget", "reference-topic-budget",
                      "reference-index-orphan"):
            self.assertNotIn(noisy, checks)

    def test_fat_index_is_reported(self):
        self.fx.project(
            "alpha",
            reference="# Reference\n\n- [ops](reference/ops.md)\n" + "z\n" * 200,
            reference_topics={"ops.md": "y\n"},
        )
        self.fx.index([{"id": "alpha", "status": "active", "bounded": False}])
        self.fx.commit()
        self.assertIn("reference-index-budget", checks_in(self.fx.audit()))

    def test_oversized_topic_is_reported(self):
        self.fx.project(
            "alpha",
            reference="# Reference\n\n- [ops](reference/ops.md)\n",
            reference_topics={"ops.md": "y\n" * 400},
        )
        self.fx.index([{"id": "alpha", "status": "active", "bounded": False}])
        self.fx.commit()
        self.assertIn("reference-topic-budget", checks_in(self.fx.audit()))

    def test_unlinked_topic_is_reported(self):
        """Sharding must not become a way to lose content: a topic file the
        index does not point at is unreachable from session start."""
        self.fx.project(
            "alpha",
            reference="# Reference\n\n- [ops](reference/ops.md)\n",
            reference_topics={"ops.md": "y\n", "orphan.md": "y\n"},
        )
        self.fx.index([{"id": "alpha", "status": "active", "bounded": False}])
        self.fx.commit()
        findings = [f for f in self.fx.audit()["data"]["findings"]
                    if f["check"] == "reference-index-orphan"]
        self.assertEqual(len(findings), 1)
        self.assertIn("orphan.md", findings[0]["message"])

    def test_shard_without_index_is_a_defect(self):
        self.fx.project("alpha", reference=None,
                        reference_topics={"ops.md": "y\n"})
        self.fx.index([{"id": "alpha", "status": "active", "bounded": False}])
        self.fx.commit()
        result = self.fx.audit()
        self.assertIn("reference-index-missing", checks_in(result))
        self.assertEqual(
            "defect",
            next(f["severity"] for f in result["data"]["findings"]
                 if f["check"] == "reference-index-missing"),
        )


class StatusHeaderParsingTests(unittest.TestCase):
    """Status is authoritative, so it has to be FOUND before Phase is consulted.

    Anchoring the pattern to line start missed every record that puts two
    fields on one line, fell through to the Phase fallback, and read a
    completion word out of the phase text. One live project reported as
    finished while its own header said Active three words later.
    """

    def test_status_is_found_when_it_follows_phase_on_one_line(self):
        text = ("**Phase:** Review complete — awaiting send. "
                "**Status:** Active (arc; bounded)\n")
        self.assertIs(False, cd.context_declares_completed(text))

    def test_phase_fallback_still_applies_when_status_is_absent(self):
        text = "**Phase:** COMPLETE (re-architecture); pass pending\n"
        self.assertIs(True, cd.context_declares_completed(text))

    def test_a_completing_phase_never_overrides_an_active_status(self):
        text = "**Phase:** Triage — inventory complete\n**Status:** Active\n"
        self.assertIs(False, cd.context_declares_completed(text))

    def test_a_trailing_field_is_not_swallowed_into_the_status_value(self):
        text = "**Status:** Active **Last session:** 2026-08-31 (completed round)\n"
        self.assertIs(False, cd.context_declares_completed(text))


class PostCloseAcknowledgmentTests(unittest.TestCase):
    """The finding must be answerable, and the answer must expire.

    Without this the check is self-sustaining: the commits that dispose of a
    project are post-completion commits, so resolving the finding re-creates
    it and no amount of correct work clears it.
    """

    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.fx = Fixture(Path(self._tmp.name) / "src")

    def tearDown(self):
        self._tmp.cleanup()

    def _closed_project_with_later_commit(self, **entry):
        self.fx.project("alpha", context="# P\n\n**Status:** Completed\n")
        self.fx.index([{"id": "alpha", "status": "completed",
                        "completed_date": "2026-06-01",
                        "last_session": "2026-06-01", **entry}])
        self.fx.commit("closing commit", when="2026-06-01")
        self.fx.project("alpha", context="# P\n\n**Status:** Completed\n\ntidy\n")
        self.fx.commit("archive pass long after the close", when="2026-08-20")
        return subprocess.run(
            ["git", "-C", str(self.fx.root), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()

    def test_without_the_field_the_disposition_commit_still_fires(self):
        self._closed_project_with_later_commit()
        self.assertIn("terminal-project-active", checks_in(self.fx.audit()))

    def test_a_review_covering_every_commit_silences_it(self):
        head = self._closed_project_with_later_commit()
        self.fx.index([{"id": "alpha", "status": "completed",
                        "completed_date": "2026-06-01",
                        "last_session": "2026-06-01",
                        "post_close_reviewed_through": head}])
        self.fx.commit("record the review", when="2026-08-20")
        self.assertNotIn("terminal-project-active", checks_in(self.fx.audit()))

    def test_the_acknowledgment_re_arms_on_the_next_project_commit(self):
        """An acknowledgment that never expires is a mute button."""
        head = self._closed_project_with_later_commit()
        self.fx.index([{"id": "alpha", "status": "completed",
                        "completed_date": "2026-06-01",
                        "last_session": "2026-06-01",
                        "post_close_reviewed_through": head}])
        self.fx.commit("record the review", when="2026-08-20")
        self.fx.project("alpha", context="# P\n\n**Status:** Completed\n\nnew work\n")
        self.fx.commit("work that resumed after the review", when="2026-08-25")
        self.assertIn("terminal-project-active", checks_in(self.fx.audit()))

    def test_an_unresolvable_sha_is_a_defect_not_a_silent_pass(self):
        """A stale date degrades quietly; a missing sha must not."""
        self._closed_project_with_later_commit()
        self.fx.index([{"id": "alpha", "status": "completed",
                        "completed_date": "2026-06-01",
                        "last_session": "2026-06-01",
                        "post_close_reviewed_through": "0" * 40}])
        self.fx.commit("record a review of history that is gone", when="2026-08-20")
        result = self.fx.audit()
        checks = checks_in(result)
        self.assertIn("post-close-review-unresolvable", checks)
        self.assertIn("terminal-project-active", checks)
        self.assertEqual(
            "defect",
            next(f["severity"] for f in result["data"]["findings"]
                 if f["check"] == "post-close-review-unresolvable"),
        )


class DormantApplicabilityTests(unittest.TestCase):
    """The v1.7.0 lifecycle rule, applied to the checks that release missed.

    Measured before this gate: 11 of 11 sessions-present and 5 of 5
    reference-budget findings were raised against dormant projects. "Move your
    session narrative into an archive" and "your scope may be too broad" are
    instructions to somebody doing the work.
    """

    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.fx = Fixture(Path(self._tmp.name) / "src")

    def tearDown(self):
        self._tmp.cleanup()

    def _checks_for(self, result, pid):
        return {f["check"] for f in result["data"].get("findings", [])
                if f["project"] == pid}

    def _fat_project(self, pid, status, **entry):
        self.fx.project(
            pid,
            context="# P\n\n**Status:** " + status.title() + "\n"
                    + "\n".join(f"- line {i}" for i in range(120)) + "\n",
            reference="\n".join(f"fact {i}" for i in range(340)) + "\n",
            sessions=None,
        )
        self.fx.index([{"id": pid, "status": status, **entry}])
        self.fx.commit(f"{pid} state")

    def test_budget_and_archive_advice_is_silent_on_a_dormant_project(self):
        self._fat_project("alpha", "paused")
        found = self._checks_for(self.fx.audit(), "alpha")
        self.assertNotIn("sessions-present", found)
        self.assertNotIn("reference-budget", found)

    def test_the_same_advice_still_fires_on_a_live_project(self):
        self._fat_project("beta", "active")
        found = self._checks_for(self.fx.audit(), "beta")
        self.assertIn("sessions-present", found)
        self.assertIn("reference-budget", found)

    def test_the_whole_tier_family_is_gated_together(self):
        """Gating two of three siblings is the inconsistency this removes.

        reference-present asks a finished project to restructure a record whose
        work is over, and its CONTEXT plus session archive already hold what a
        later reader needs.
        """
        self.fx.project("alpha", context="# P\n\n**Status:** Completed\n",
                        sessions={"2026-01.md": "## 2026-01-05 — a\n",
                                  "2026-02.md": "## 2026-02-05 — b\n"})
        self.fx.index([{"id": "alpha", "status": "completed",
                        "completed_date": "2026-02-05"}])
        self.fx.commit("closed", when="2026-02-05")
        found = self._checks_for(self.fx.audit(), "alpha")
        self.assertNotIn("reference-present", found)

    def test_reference_present_still_fires_on_a_live_project(self):
        self.fx.project("beta", context="# P\n\n**Status:** Active\n",
                        sessions={"2026-01.md": "## 2026-01-05 — a\n",
                                  "2026-02.md": "## 2026-02-05 — b\n"})
        self.fx.index([{"id": "beta", "status": "active"}])
        self.fx.commit("live")
        self.assertIn("reference-present", self._checks_for(self.fx.audit(), "beta"))

    def test_the_skip_is_reported_rather_than_silent(self):
        """The property that makes an unpaired suppression findable."""
        self._fat_project("alpha", "paused")
        coverage = self.fx.audit()["data"]["coverage"]
        self.assertGreaterEqual(coverage["sessions-present"]["skipped"], 1)
        self.assertIn("dormant", coverage["sessions-present"]["reasons"])


class TerminalOpenItemsTests(unittest.TestCase):
    """The pairing the item-currency suppression shipped without."""

    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.fx = Fixture(Path(self._tmp.name) / "src")

    def tearDown(self):
        self._tmp.cleanup()

    def _project(self, body, status="completed"):
        self.fx.project("alpha", context=f"# P\n\n**Status:** Completed\n\n{body}")
        self.fx.index([{"id": "alpha", "status": status,
                        "completed_date": "2026-06-01",
                        "last_session": "2026-06-01"}])
        self.fx.commit("state", when="2026-06-01")
        return checks_in(self.fx.audit())

    def test_a_finished_project_still_owing_work_is_reported(self):
        checks = self._project("## What's Next\n\n- [ ] chase the vendor\n")
        self.assertIn("terminal-project-open-items", checks)

    def test_checked_items_are_a_record_of_work_done_not_work_owed(self):
        checks = self._project("## What's Next\n\n- [x] chased the vendor\n")
        self.assertNotIn("terminal-project-open-items", checks)

    def test_narrative_bullets_are_not_read_as_obligations(self):
        """The miscalibration that cost 140 of 294 findings once already."""
        checks = self._project("## What's Next\n\n- the vendor was chased\n")
        self.assertNotIn("terminal-project-open-items", checks)

    def test_a_live_project_is_not_asked_this_question(self):
        checks = self._project("## What's Next\n\n- [ ] chase\n", status="active")
        self.assertNotIn("terminal-project-open-items", checks)


class CitedScriptTargetTests(unittest.TestCase):
    """A cited directory of scripts is preserved work, not a missing target.

    The check exists so an artifact cannot cite an executable that was never
    kept. A directory holding the scripts satisfies that; requiring a regular
    file rejected the ordinary way a multi-file tool is referenced.
    """

    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.fx = Fixture(Path(self._tmp.name) / "src")

    def tearDown(self):
        self._tmp.cleanup()

    def _project_citing(self, target: str, make):
        path = self.fx.project("alpha")
        arts = path / "resources" / "artifacts"
        arts.mkdir(parents=True, exist_ok=True)
        (arts / "note.md").write_text(
            f"See `resources/scripts/{target}` for the portable version.\n",
            encoding="utf-8",
        )
        make(path / "resources" / "scripts")
        self.fx.index([{"id": "alpha", "status": "active"}])
        self.fx.commit()
        return self._checks_for(self.fx.audit(), "alpha")

    def _checks_for(self, result, pid):
        return {f["check"] for f in result["data"].get("findings", [])
                if f["project"] == pid}

    def test_a_directory_of_scripts_is_a_valid_citation(self):
        def make(scripts):
            d = scripts / "codex-hooks"
            d.mkdir(parents=True)
            (d / "hooks.json").write_text("{}\n", encoding="utf-8")
            (d / "guard.py").write_text("print('x')\n", encoding="utf-8")
        self.assertNotIn("artifact-cites-missing-script",
                         self._project_citing("codex-hooks/", make))

    def test_an_empty_directory_is_still_a_missing_target(self):
        """Nothing was preserved; a folder is not a substitute for content."""
        def make(scripts):
            (scripts / "codex-hooks").mkdir(parents=True)
        self.assertIn("artifact-cites-missing-script",
                      self._project_citing("codex-hooks/", make))

    def test_a_missing_target_still_fires(self):
        def make(scripts):
            scripts.mkdir(parents=True)
        self.assertIn("artifact-cites-missing-script",
                      self._project_citing("gone.py", make))


class SkillDocContractTests(unittest.TestCase):
    """A finding names a check; the skill has to make that name mean something.

    An operator handed `reference-topic-budget` and no way to look it up has
    been handed a string, not a remedy — and a check nobody can act on is the
    fail-open state this doctor exists to end. test_item_currency.py holds the
    day-end ritual to the same contract; this holds the skill to it for the
    vocabulary v1.7.0 introduced.
    """

    SKILL = Path(__file__).resolve().parents[1] / "SKILL.md"

    def setUp(self):
        self.text = self.SKILL.read_text(encoding="utf-8")

    # The semantic-shard family. Named rather than prefix-matched: the prefix
    # also catches reference-present, which is a tier-structure check and is
    # documented with that group. Membership is asserted against the doctor so
    # a rename there breaks this test instead of quietly passing.
    SHARD_CHECKS = (
        "reference-budget",
        "reference-shard",
        "reference-index-budget",
        "reference-topic-budget",
        "reference-index-orphan",
        "reference-index-missing",
    )

    def test_the_shard_family_is_still_the_doctors_own_vocabulary(self):
        for check in self.SHARD_CHECKS:
            with self.subTest(check=check):
                self.assertIn(check, cd.CHECKS)

    def test_every_reference_shard_check_is_documented_by_name(self):
        for check in self.SHARD_CHECKS:
            with self.subTest(check=check):
                self.assertIn(check, self.text)

    def test_the_paired_inversion_is_documented_by_name(self):
        # Suppression is only safe paired with the check that replaces it. If
        # the pairing is undocumented, the next reader sees only the silence.
        self.assertIn("terminal-project-active", self.text)

    def test_the_pairing_rule_itself_survives_in_the_doc(self):
        self.assertIn(
            "suppressing an inapplicable check is only safe when you add the "
            "check that becomes applicable in its place",
            self.text.lower(),
        )

    def test_bounded_is_documented_as_behaviour_with_its_default(self):
        # The field decides which remedy a project is offered, so its default
        # is load-bearing: readers must be able to learn it without reading
        # the source.
        self.assertIn("bounded: false", self.text)
        self.assertIn("`bounded` defaults to `true` when unset", self.text)

    def test_the_v18_vocabulary_is_documented_by_name(self):
        """Same contract as the shard family: a report names the check that
        fired, and a name the skill never mentions is a string, not a remedy."""
        for check in ("terminal-project-open-items",
                      "post-close-review-unresolvable"):
            with self.subTest(check=check):
                self.assertIn(check, cd.CHECKS)
                self.assertIn(check, self.text)

    def test_the_acknowledgment_field_and_its_expiry_are_documented(self):
        # The field without its expiry reads as a mute button, which is the
        # one way this change could be misused.
        self.assertIn("post_close_reviewed_through", self.text)
        self.assertIn("re-arms", self.text.lower())

    def test_the_coverage_rule_survives_in_the_doc(self):
        self.assertIn(
            "coverage is a claim that needs its own verification",
            self.text.lower(),
        )

    def test_post_shard_budgets_are_stated(self):
        self.assertIn(str(cd.REFERENCE_INDEX_BUDGET), self.text)
        self.assertIn(str(cd.REFERENCE_TOPIC_BUDGET), self.text)


if __name__ == "__main__":
    unittest.main(verbosity=2)

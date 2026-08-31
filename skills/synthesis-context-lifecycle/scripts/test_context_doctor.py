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

    def test_post_shard_budgets_are_stated(self):
        self.assertIn(str(cd.REFERENCE_INDEX_BUDGET), self.text)
        self.assertIn(str(cd.REFERENCE_TOPIC_BUDGET), self.text)


if __name__ == "__main__":
    unittest.main(verbosity=2)

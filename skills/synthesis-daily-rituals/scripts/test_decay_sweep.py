"""Behavioral regression for due-date collection, committed before its helper."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parent
HELPER = SCRIPTS / "decay_sweep.py"
FIXTURE = SCRIPTS / "fixtures" / "decay-sweep" / "plans"


def run(*roots: Path, as_of="2026-09-08", extra=()):
    command = [sys.executable, str(HELPER), "--as-of", as_of, "--json"]
    for root in roots:
        command.extend(["--plans-dir", str(root)])
    proc = subprocess.run(command + list(extra), capture_output=True, text=True)
    assert proc.stdout, f"collector missing or failed without coverage: {proc.stderr}"
    return proc.returncode, json.loads(proc.stdout)


def plan(root, day, body):
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{day}.md"
    path.write_text(body, encoding="utf-8")
    return path


def item(ident="obligation-1", due="2026-09-08", reason="(event date)"):
    return f"### Item\n**Decay ID:** {ident}\n**Decays:** {due} {reason}\n"


def test_older_target_dates_survive_today_without_retagging(tmp_path):
    root = tmp_path / "plans"
    shutil.copytree(FIXTURE, root)
    code, report = run(root)
    assert code == 0 and report["status"] == "REVIEW"
    assert [row["due_date"] for row in report["due"]] == ["2026-08-03", "2026-09-08"]
    assert len(report["scanned"]) == 3
    assert [Path(p).name for p in report["excluded"]] == ["notes.md"]
    assert report["gaps"] == []


def test_explicit_identity_deduplicates_and_reasoned_redate_replaces(tmp_path):
    plan(tmp_path, "2026-09-01", item())
    plan(tmp_path, "2026-09-04", item())
    code, report = run(tmp_path)
    assert code == 0 and len(report["due"]) == 1
    plan(tmp_path, "2026-09-08", item(due="2026-09-10", reason="(user moved the date)"))
    code, report = run(tmp_path)
    assert code == 0 and report["status"] == "CLEAR"


@pytest.mark.parametrize("marker", ["Sent", "Released", "Resolved"])
def test_later_resolution_without_retagging_closes_identified_item(tmp_path, marker):
    plan(tmp_path, "2026-09-01", item())
    plan(tmp_path, "2026-09-08", f"### Item\n**Decay ID:** obligation-1\n**{marker}:** 2026-09-08 (verified outcome)\n")
    code, report = run(tmp_path)
    assert code == 0 and report["status"] == "CLEAR"


def test_unidentified_similar_titles_do_not_cancel_each_other(tmp_path):
    plan(tmp_path, "2026-09-01", "### Reply\n**Decays:** 2026-09-02\n")
    plan(tmp_path, "2026-09-08", "### Reply\n**Decays:** 2026-09-08\n**Sent:** 2026-09-08\n")
    code, report = run(tmp_path)
    assert code == 0 and [r["due_date"] for r in report["due"]] == ["2026-09-02"]


@pytest.mark.parametrize("bad", ["2026-02-30", "next Tuesday", "20260908", ""])
def test_invalid_tags_block_an_empty_success(tmp_path, bad):
    plan(tmp_path, "2026-09-01", f"### Item\n**Decays:** {bad}\n")
    code, report = run(tmp_path)
    assert code == 2 and report["status"] == "BLOCKED" and report["gaps"]


def test_missing_or_empty_scope_is_not_clear(tmp_path):
    for root in [tmp_path / "missing", tmp_path]:
        code, report = run(root)
        assert code == 2 and report["status"] == "BLOCKED" and report["gaps"]


def test_no_declared_root_is_not_clear():
    code, report = run()
    assert code == 2 and report["gaps"]


def test_due_candidates_survive_partial_coverage_and_bad_files(tmp_path):
    plan(tmp_path, "2026-09-01", item())
    (tmp_path / "2026-09-04.md").write_bytes(b"\xff")
    code, report = run(tmp_path, tmp_path / "missing")
    assert code == 2 and len(report["due"]) == 1 and len(report["gaps"]) >= 2


def test_archive_recursion_and_symlinks_do_not_hide_scope_gaps(tmp_path):
    plan(tmp_path / "archive", "2025-01-01", item(due="2025-01-02"))
    (tmp_path / "linked").symlink_to(tmp_path / "archive", target_is_directory=True)
    code, report = run(tmp_path)
    assert code == 2 and len(report["due"]) == 1
    assert any("symlink" in row["reason"].lower() for row in report["gaps"])


def test_future_plan_cannot_close_due_item(tmp_path):
    plan(tmp_path, "2026-09-01", item())
    plan(tmp_path, "2026-09-09", item() + "**Sent:** 2026-09-09\n")
    code, report = run(tmp_path)
    assert code == 0 and len(report["due"]) == 1 and len(report["future_files"]) == 1


def test_future_resolution_cannot_close_due_item(tmp_path):
    plan(tmp_path, "2026-09-01", item() + "**Sent:** 2026-09-09\n")
    code, report = run(tmp_path)
    assert code == 2 and len(report["due"]) == 1


def test_redate_without_reason_is_not_silently_accepted(tmp_path):
    plan(tmp_path, "2026-09-01", item())
    plan(tmp_path, "2026-09-08", item(due="2026-09-10", reason=""))
    code, report = run(tmp_path)
    assert code == 2 and len(report["due"]) == 1


def test_same_day_conflicting_copies_require_review(tmp_path):
    plan(tmp_path / "a", "2026-09-08", item())
    plan(tmp_path / "b", "2026-09-08", item(due="2026-09-10"))
    code, report = run(tmp_path)
    assert code == 2 and len(report["due"]) == 1


def test_identical_same_day_copies_coalesce(tmp_path):
    plan(tmp_path / "a", "2026-09-08", item())
    plan(tmp_path / "b", "2026-09-08", item())
    code, report = run(tmp_path)
    assert code == 0 and len(report["due"]) == 1


def test_worker_artifacts_use_declared_order_without_cross_workspace_discovery(tmp_path):
    root = tmp_path / "worker"
    plan(root, "2026-09-08-day-start", item())
    plan(root, "2026-09-08-day-end", item() + "**Released:** 2026-09-08 (user decision)\n")
    plan(tmp_path / "unrelated", "2026-09-08", item())
    code, report = run(extra=["--artifacts-dir", str(root)])
    assert code == 0 and report["status"] == "CLEAR" and len(report["scanned"]) == 2


def test_list_metadata_and_done_markers_are_item_scoped(tmp_path):
    plan(tmp_path, "2026-09-08", "- [x] Closed\n  **Decays:** 2026-09-08\n- [ ] Still open\n  **Decays:** 2026-09-08\n")
    code, report = run(tmp_path)
    assert code == 0 and len(report["due"]) == 1 and "Still open" in report["due"][0]["title"]


def test_skill_invokes_collector_and_removes_today_only_rule():
    skill = (SCRIPTS.parent / "SKILL.md").read_text()
    assert "scripts/decay_sweep.py" in skill
    assert "every `**Decays:**` line in today's plan" not in skill
    assert "references/decay-sweep.md" in skill

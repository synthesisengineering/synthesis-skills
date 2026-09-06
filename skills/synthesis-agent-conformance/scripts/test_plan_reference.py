"""Cross-project plan contracts shared by state, summaries and both adapters."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import conformance
import session_context


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def plan_project(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    project = repo / "projects" / "arc"
    plan = repo / "projects" / "program" / "resources" / "artifacts" / "work-plan.md"
    plan.parent.mkdir(parents=True)
    plan.write_text("# Program plan\n", encoding="utf-8")
    (project / "sessions").mkdir(parents=True)
    (project / "REFERENCE.md").write_text("# Reference\n", encoding="utf-8")
    (project / "sessions" / "2026-09.md").write_text("### 2026-09-03 — started\n")
    monkeypatch.setenv("SYNTHESIS_HOME", str(tmp_path / "synthesis-home"))
    git(repo, "init", "--quiet", "--initial-branch", "main")
    for key, value in (("user.name", "Fixture"), ("user.email", "fixture@example.invalid"), ("core.hooksPath", "/dev/null")):
        git(repo, "config", key, value)
    write_context(project, "Controlling plan: ../program/resources/artifacts/work-plan.md")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "Seed project")
    git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    return repo, project, plan


def write_context(project: Path, declaration: str) -> str:
    text = (
        "# Context\n\n**Phase:** Ready\n**Status:** active\n"
        "**Last session:** 2026-09-03\n\n" + declaration
        + "\n\n## What's Next\n\n- [ ] Continue.\n"
    )
    (project / "CONTEXT.md").write_text(text, encoding="utf-8")
    return text


@pytest.mark.parametrize("shape", ["relative", "repo-relative", "absolute", "markdown", "bare-link", "angle-spaces"])
def test_cross_project_plan_summary_and_payload_agree(plan_project, shape):
    repo, project, plan = plan_project
    if shape == "angle-spaces":
        plan = plan.with_name("work plan.md")
        plan.write_text("# Plan with spaces\n", encoding="utf-8")
    references = {
        "relative": "Controlling plan: ../program/resources/artifacts/work-plan.md",
        "repo-relative": "Controlling plan: projects/program/resources/artifacts/work-plan.md",
        "absolute": f"Controlling plan: {plan} (item 2.1)",
        "markdown": "**Controlling plan:** [program](../program/resources/artifacts/work-plan.md)",
        "bare-link": "[plan](../program/resources/artifacts/work-plan.md)",
        "angle-spaces": "Controlling plan: [program](<../program/resources/artifacts/work plan.md>)",
    }
    write_context(project, references[shape])
    summary, checks = conformance.project_summary(project)
    check = next(item for item in checks if item.name == "handoff.plan")
    assert check.ok and check.required, check.detail
    assert summary["plan"] == str(plan.resolve())
    lines = []
    session_context.append_project_context(lines, project, label="Recovered", diagnostic=True)
    assert f"Controlling plan: {summary['plan']}." in lines


@pytest.mark.parametrize("declaration", [
    "Controlling plan:",
    "Controlling plan: .",
    "Controlling plan: [broken](../program/no-plan.md)",
    "Controlling plan: https://example.invalid/plan.md",
    "Controlling plan: ../program/resources/artifacts/work-plan.md\nControlling plan: absent.md",
])
def test_invalid_explicit_plan_cannot_fall_back_to_existing_link(plan_project, declaration):
    _repo, project, _plan = plan_project
    write_context(project, declaration + "\n[old plan](../program/resources/artifacts/work-plan.md)")
    _, checks = conformance.project_summary(project)
    check = next(item for item in checks if item.name == "handoff.plan")
    assert not check.ok and check.required
    with pytest.raises(ValueError, match="controlling plan"):
        session_context.append_project_context([], project, label="Recovered", diagnostic=True)


@pytest.mark.parametrize("shape", ["absolute", "relative", "symlink-file", "symlink-directory"])
def test_plan_cannot_escape_repository(plan_project, tmp_path, shape):
    repo, project, _plan = plan_project
    outside = tmp_path / "external-plan.md"
    outside.write_text("# Outside\n", encoding="utf-8")
    if shape == "symlink-file":
        (repo / "alias-plan.md").symlink_to(outside)
        target = "alias-plan.md"
    elif shape == "symlink-directory":
        (repo / "alias").symlink_to(tmp_path, target_is_directory=True)
        target = "alias/external-plan.md"
    else:
        target = str(outside) if shape == "absolute" else "../../../external-plan.md"
    write_context(project, f"Controlling plan: {target}")
    _, checks = conformance.project_summary(project)
    check = next(item for item in checks if item.name == "handoff.plan")
    assert not check.ok and check.required
    with pytest.raises(ValueError, match="controlling plan"):
        session_context.append_project_context([], project, label="Recovered", diagnostic=True)


def test_cross_project_stopped_parity_is_read_only(plan_project, tmp_path):
    repo, project, _plan = plan_project
    summary, _checks = conformance.project_summary(project)
    before = {str(path.relative_to(repo)): path.read_bytes() for path in repo.rglob("*") if path.is_file()}
    ok, detail = conformance.stopped_payload_parity(project, summary, tmp_path / "no-board.md")
    assert ok, detail
    after = {str(path.relative_to(repo)): path.read_bytes() for path in repo.rglob("*") if path.is_file()}
    assert after == before
    assert not (tmp_path / "synthesis-home").exists()


def test_stopped_parity_relocates_parent_plan_in_selected_worktree(plan_project, tmp_path):
    repo, project, plan = plan_project
    (repo / "projects" / "index.yaml").write_text("- id: arc\n  status: active\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "Index project")
    isolated = tmp_path / "isolated"
    git(repo, "worktree", "add", "-q", "-b", "feature/isolated", str(isolated), "HEAD")
    (repo / "unrelated.txt").write_text("newer repository state\n", encoding="utf-8")
    git(repo, "add", "unrelated.txt")
    git(repo, "commit", "-qm", "Advance checkout")
    git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    isolated_project = isolated / project.relative_to(repo)
    summary, _checks = conformance.project_summary(isolated_project)
    assert summary["plan"] == str(isolated / plan.relative_to(repo))
    ok, detail = conformance.stopped_payload_parity(isolated_project, summary, tmp_path / "no-board.md")
    assert ok, detail


def test_structured_plan_is_shared_and_parent_change_invalidates_state(plan_project):
    import project_state

    _repo, project, plan = plan_project
    payload = project_state.build_operational_state(
        project, project_id="arc", phase="Ready", status="active",
        controlling_plan="../program/resources/artifacts/work-plan.md", accepted_baseline="1.0.0",
        next_actions=["Continue."], last_session="2026-09-03", session_id="fixture-session",
    )
    assert "../program/resources/artifacts/work-plan.md" in payload["content_hashes"]
    assert project_state.semantic_issues(project) == []
    summary, checks = conformance.project_summary(project)
    assert all(item.ok for item in checks if item.required)
    lines = []
    session_context.append_project_context(lines, project, label="Recovered", diagnostic=True)
    assert f"Controlling plan: {summary['plan']}." in lines
    plan.write_text("# Changed parent plan\n", encoding="utf-8")
    assert any("changed" in issue for issue in project_state.semantic_issues(project))
    _summary, checks = conformance.project_summary(project)
    assert any(not item.ok and item.required for item in checks)
    with pytest.raises(ValueError, match="semantic current-state"):
        session_context.append_project_context([], project, label="Recovered", diagnostic=True)


def test_structured_absolute_plan_is_stored_portably(plan_project):
    import project_state

    _repo, project, plan = plan_project
    payload = project_state.build_operational_state(
        project, project_id="arc", phase="Ready", status="active", controlling_plan=str(plan),
        accepted_baseline="1.0.0", next_actions=["Continue."], last_session="2026-09-03",
        session_id="fixture-session",
    )
    assert payload["controlling_plan"] == "../program/resources/artifacts/work-plan.md"
    assert project_state.semantic_issues(project) == []


def test_no_plan_is_optional_but_declared_local_missing_plan_is_not(plan_project):
    _repo, project, _plan = plan_project
    write_context(project, "No plan declaration.")
    summary, checks = conformance.project_summary(project)
    check = next(item for item in checks if item.name == "handoff.plan")
    assert not check.ok and not check.required and summary["plan"] == "unknown"
    write_context(project, "[plan](resources/artifacts/missing-plan.md)")
    _, checks = conformance.project_summary(project)
    check = next(item for item in checks if item.name == "handoff.plan")
    assert not check.ok and check.required

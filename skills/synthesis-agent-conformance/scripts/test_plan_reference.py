from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("plan_reference.py")
SPEC = importlib.util.spec_from_file_location("plan_reference", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _git_repo(root: Path) -> None:
    subprocess.run(
        ["git", "init", "--quiet", "--initial-branch", "main", str(root)],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "config", "core.hooksPath", "/dev/null"],
        check=True,
    )


def test_locate_plan_matches_links_case_insensitively(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    plan = project / "resources" / "artifacts" / "Master-PLAN.md"
    plan.parent.mkdir(parents=True)
    plan.write_text("# Plan\n", encoding="utf-8")

    ref = MODULE.locate_plan(project, "[plan](resources/artifacts/Master-PLAN.md)\n")

    assert ref.legacy_local
    assert ref.resolved is not None
    assert ref.value == str(project / "resources/artifacts/Master-PLAN.md")


def test_explicit_line_outranks_local_link(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    local = project / "resources" / "artifacts" / "local-plan.md"
    local.parent.mkdir(parents=True)
    local.write_text("# Local\n", encoding="utf-8")
    outer = tmp_path / "outer-plan.md"
    outer.write_text("# Outer\n", encoding="utf-8")

    ref = MODULE.locate_plan(
        project,
        f"Controlling plan: {outer}\n[plan](resources/artifacts/local-plan.md)\n",
    )

    assert not ref.legacy_local
    assert ref.value == str(outer.resolve())


def test_legacy_missing_keeps_project_joined_value(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()

    ref = MODULE.locate_plan(project, "[plan](resources/artifacts/gone-plan.md)\n")

    assert ref.legacy_local
    assert ref.resolved is None
    assert ref.value == str(project / "resources/artifacts/gone-plan.md")
    assert ref.detail.startswith("active plan is missing:")


def test_empty_declaration_falls_through_to_link_scan(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    plan = project / "resources" / "artifacts" / "demo-plan.md"
    plan.parent.mkdir(parents=True)
    plan.write_text("# Plan\n", encoding="utf-8")

    ref = MODULE.locate_plan(
        project, "Controlling plan: .\n[plan](resources/artifacts/demo-plan.md)\n"
    )

    assert ref.legacy_local
    assert ref.resolved is not None


def test_markdown_link_on_declaration_line_resolves(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    project = repo / "projects" / "arc"
    project.mkdir(parents=True)
    plan = repo / "projects" / "program" / "resources" / "artifacts" / "p-plan.md"
    plan.parent.mkdir(parents=True)
    plan.write_text("# Plan\n", encoding="utf-8")
    _git_repo(repo)

    ref = MODULE.locate_plan(
        project,
        "Controlling plan: [the plan](../program/resources/artifacts/p-plan.md)\n",
    )

    assert ref.resolved == plan.resolve()
    assert ref.value == str(plan.resolve())


def test_relative_target_without_repository_fails_closed(tmp_path: Path) -> None:
    proj_parent = tmp_path / "outer" / "proj"
    project = proj_parent / "arc"
    project.mkdir(parents=True)
    side = proj_parent / "side-plan.md"
    side.write_text("# Plan\n", encoding="utf-8")

    ref = MODULE.locate_plan(project, "Controlling plan: ../side-plan.md\n")

    assert ref.resolved is None
    assert "cannot verify" in ref.detail
    assert ref.value == "../side-plan.md"

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("conformance.py")
SPEC = importlib.util.spec_from_file_location("conformance", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def write_skill(root: Path, name: str) -> None:
    skill = root / "skills" / name
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: Test skill.\n---\n\n# Test\n",
        encoding="utf-8",
    )
    interface = skill / "agents"
    interface.mkdir()
    (interface / "openai.yaml").write_text(
        "interface:\n"
        f'  display_name: "{name}"\n'
        '  short_description: "Apply this synthesis workflow"\n'
        f'  default_prompt: "Use ${name} for this task."\n',
        encoding="utf-8",
    )


def write_manifests(root: Path) -> None:
    payload = json.dumps(
        {
            "name": "synthesis-skills",
            "version": "1.0.0",
            "description": "test",
            "skills": "./skills/",
        }
    )
    for folder in (".codex-plugin", ".claude-plugin"):
        path = root / folder
        path.mkdir()
        (path / "plugin.json").write_text(payload, encoding="utf-8")

    configurations = (
        root / ".agents" / "plugins" / "marketplace.json",
        root / ".claude-plugin" / "marketplace.json",
        root / "hooks" / "hooks.json",
    )
    for configuration in configurations:
        configuration.parent.mkdir(parents=True, exist_ok=True)
        configuration.write_text("{}\n", encoding="utf-8")


def test_json_from_output_accepts_cli_diagnostics_around_json() -> None:
    output = (
        "WARNING: [aliases] could not be refreshed\n"
        '{"installed": [{"name": "synthesis-skills"}]}\n'
        "WARNING: proceeding with cached aliases\n"
    )

    assert MODULE.json_from_output(output) == {
        "installed": [{"name": "synthesis-skills"}]
    }


def test_direct_public_copies_cover_all_client_roots(tmp_path: Path) -> None:
    expected = []
    for client_root in (
        ".claude/skills",
        ".agents/skills",
        ".codex/skills",
    ):
        path = tmp_path / client_root / "synthesis-test"
        path.mkdir(parents=True)
        expected.append(str(path.relative_to(tmp_path)))
    private = tmp_path / ".agents" / "skills" / "rajiv-private-test"
    private.mkdir()

    assert MODULE.direct_public_copies(tmp_path) == sorted(expected)


def test_source_checks_accept_dual_manifest(tmp_path: Path) -> None:
    write_manifests(tmp_path)
    write_skill(tmp_path, "synthesis-test")
    checks = MODULE.source_checks(tmp_path)
    assert all(check.ok for check in checks)


def test_source_checks_require_openai_interface(tmp_path: Path) -> None:
    write_manifests(tmp_path)
    write_skill(tmp_path, "synthesis-test")
    (tmp_path / "skills" / "synthesis-test" / "agents" / "openai.yaml").unlink()

    checks = MODULE.source_checks(tmp_path)

    interface = next(
        check for check in checks if check.name == "source.skill-ui.synthesis-test"
    )
    assert not interface.ok


def test_source_checks_reject_client_bound_runtime_path(tmp_path: Path) -> None:
    write_manifests(tmp_path)
    write_skill(tmp_path, "synthesis-test")
    (tmp_path / "skills" / "synthesis-test" / "runtime.sh").write_text(
        'exec "$HOME/.claude/skills/synthesis-test/run.sh"\n',
        encoding="utf-8",
    )

    checks = MODULE.source_checks(tmp_path)

    stale = next(
        check for check in checks if check.name == "source.no-client-copy-paths"
    )
    assert not stale.ok


def test_instruction_adapter(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
    (tmp_path / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
    checks = MODULE.instruction_checks(tmp_path)
    assert all(check.ok for check in checks)


def test_coordination_board_schema(tmp_path: Path) -> None:
    board = tmp_path / "active-sessions.md"
    board.write_text(
        "# Coordination\n\n"
        "Schema: v2\n\n"
        "## Active sessions\n\n"
        "| id | agent | machine | project | started | heartbeat | mode | workspace(s) / branch | goal | claimed areas (advisory lock) | context role | status |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|\n\n"
        "## Messages\n\n---\n\n## Protocol\n",
        encoding="utf-8",
    )

    checks = MODULE.coordination_checks(board)

    assert all(check.ok for check in checks)


def test_coordination_board_rejects_semantic_conflict(tmp_path: Path) -> None:
    board = tmp_path / "active-sessions.md"
    board.write_text(
        "# Coordination\n\n"
        "Schema: v2\n\n"
        "## Active sessions\n\n"
        "| id | agent | machine | project | started | heartbeat | mode | workspace(s) / branch | goal | claimed areas (advisory lock) | context role | status |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|\n"
        "| A | Claude | host-a | shared | 2026-07-30T10:00:00-04:00 | 2026-07-30T10:00:00-04:00 | interactive | /tmp/a/repo @ feature/a | work | repo/** | owner | active |\n"
        "| B | Codex | host-b | shared | 2026-07-30T10:00:00-04:00 | 2026-07-30T10:00:00-04:00 | autonomous | /tmp/b/repo @ feature/b | work | repo/file.md | owner | active |\n\n"
        "## Messages\n\n---\n\n## Protocol\n",
        encoding="utf-8",
    )

    checks = MODULE.coordination_checks(board)

    doctor = next(
        check for check in checks if check.name == "coordination.semantic-doctor"
    )
    assert not doctor.ok


def test_activate_and_handoff(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "CONTEXT.md").write_text(
        "# Context\n\n"
        "**Phase:** 2\n"
        "**Status:** Active\n"
        "**Last session:** 2026-07-29\n\n"
        "[plan](resources/artifacts/test-plan.md)\n\n"
        "## What's Next\n\n"
        "1. [x] Finished.\n"
        "2. [ ] Continue the live check\n"
        "   from verified state.\n",
        encoding="utf-8",
    )
    (project / "REFERENCE.md").write_text("# Reference\n", encoding="utf-8")
    (project / "sessions").mkdir()
    plan = project / "resources" / "artifacts"
    plan.mkdir(parents=True)
    (plan / "test-plan.md").write_text("# Plan\n", encoding="utf-8")
    subprocess = __import__("subprocess")
    subprocess.run(["git", "init", str(project)], check=True, capture_output=True)

    pointer = tmp_path / "active.json"
    activated = MODULE.activate(project, pointer)
    assert all(check.ok for check in activated if check.required)
    payload = __import__("json").loads(pointer.read_text(encoding="utf-8"))
    assert payload["next"] == [
        "2. [ ] Continue the live check from verified state."
    ]
    handoff = MODULE.handoff_checks(project, pointer)
    assert all(check.ok for check in handoff if check.required)

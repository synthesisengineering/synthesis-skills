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


def test_source_checks_reject_personal_workspace_paths(tmp_path: Path) -> None:
    write_manifests(tmp_path)
    write_skill(tmp_path, "synthesis-test")
    (tmp_path / "skills" / "synthesis-test" / "drift.py").write_text(
        'SOURCE = "~/workspaces/someone/synthesis-skills/skills"\n',
        encoding="utf-8",
    )

    checks = MODULE.source_checks(tmp_path)

    personal = next(
        check
        for check in checks
        if check.name == "source.no-personal-workspace-paths"
    )
    assert not personal.ok


def test_source_scans_survive_claude_worktree_ancestors(tmp_path: Path) -> None:
    """A checkout under .claude/worktrees/ must still be scanned — ancestor
    path components must not empty the forbidden-pattern scans."""
    nested = tmp_path / ".claude" / "worktrees" / "wt"
    nested.mkdir(parents=True)
    write_manifests(nested)
    write_skill(nested, "synthesis-test")
    (nested / "skills" / "synthesis-test" / "drift.py").write_text(
        'SOURCE = "~/workspaces/someone/synthesis-skills/skills"\n',
        encoding="utf-8",
    )

    checks = MODULE.source_checks(nested)

    personal = next(
        check
        for check in checks
        if check.name == "source.no-personal-workspace-paths"
    )
    assert not personal.ok


def test_placeholder_workspace_paths_are_allowed(tmp_path: Path) -> None:
    write_manifests(tmp_path)
    write_skill(tmp_path, "synthesis-test")
    (tmp_path / "skills" / "synthesis-test" / "notes.md").write_text(
        "Run ~/workspaces/<you>/synthesis-skills/install.sh, or glob\n"
        "~/workspaces/*/ai-knowledge-*; sample layouts use\n"
        "~/workspaces/example-person/ai-knowledge-example-person/ and\n"
        "/home/user/workspaces/demo/ai-knowledge-demo/.\n",
        encoding="utf-8",
    )

    checks = MODULE.source_checks(tmp_path)

    personal = next(
        check
        for check in checks
        if check.name == "source.no-personal-workspace-paths"
    )
    assert personal.ok


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
    named = {check.name: check for check in handoff}
    assert named["handoff.payload-parity"].ok
    assert "identical context" in named["handoff.payload-parity"].detail
    assert named["handoff.record-freshness"].ok


def clone_pair_with_project(tmp_path: Path) -> tuple[Path, Path]:
    """Two clones of one remote; the project lives in both, one goes stale."""
    subprocess = __import__("subprocess")

    def git(cwd: Path, *arguments: str) -> None:
        subprocess.run(
            ["git", "-C", str(cwd), *arguments], check=True, capture_output=True
        )

    remote = tmp_path / "remote.git"
    subprocess.run(
        ["git", "init", "--bare", "--quiet", "--initial-branch", "main", str(remote)],
        check=True,
        capture_output=True,
    )
    clones = []
    for name in ("writer", "reader"):
        clone = tmp_path / name
        subprocess.run(
            ["git", "clone", "--quiet", str(remote), str(clone)],
            check=True,
            capture_output=True,
        )
        git(clone, "config", "user.email", "test@example.com")
        git(clone, "config", "user.name", "Test")
        clones.append(clone)
    writer, reader = clones
    project = writer / "projects" / "demo"
    project.mkdir(parents=True)
    (project / "CONTEXT.md").write_text("**Phase:** 1\n", encoding="utf-8")
    git(writer, "add", "projects")
    git(writer, "commit", "--quiet", "-m", "seed")
    git(writer, "push", "--quiet", "origin", "main")
    git(reader, "pull", "--quiet")

    (project / "CONTEXT.md").write_text("**Phase:** 2\n", encoding="utf-8")
    git(writer, "commit", "--quiet", "-am", "advance")
    git(writer, "push", "--quiet", "origin", "main")
    git(reader, "fetch", "--quiet", "origin")
    return writer / "projects" / "demo", reader / "projects" / "demo"


def test_record_freshness_flags_stale_checkout(tmp_path: Path) -> None:
    current, stale = clone_pair_with_project(tmp_path)

    fresh, detail = MODULE.record_freshness(current)
    assert fresh, detail

    fresh, detail = MODULE.record_freshness(stale)
    assert not fresh
    assert "1 commit(s) behind" in detail

    subprocess = __import__("subprocess")
    subprocess.run(
        ["git", "-C", str(stale.parents[1]), "pull", "--quiet"],
        check=True,
        capture_output=True,
    )
    fresh, detail = MODULE.record_freshness(stale)
    assert fresh, detail


def test_record_freshness_without_upstream_is_not_comparable(tmp_path: Path) -> None:
    subprocess = __import__("subprocess")
    project = tmp_path / "local-only"
    project.mkdir()
    subprocess.run(["git", "init", str(project)], check=True, capture_output=True)
    fresh, detail = MODULE.record_freshness(project)
    assert fresh
    assert "not comparable" in detail


def test_activate_refuses_stale_record(tmp_path: Path) -> None:
    _, stale = clone_pair_with_project(tmp_path)
    (stale / "REFERENCE.md").write_text("# Reference\n", encoding="utf-8")
    (stale / "sessions").mkdir()

    pointer = tmp_path / "active.json"
    checks = MODULE.activate(stale, pointer)
    named = {check.name: check for check in checks}
    assert not named["handoff.record-freshness"].ok
    assert not pointer.exists()


def test_payload_parity_reports_broken_pointer(tmp_path: Path) -> None:
    pointer = tmp_path / "active.json"
    pointer.write_text(
        json.dumps({"project": str(tmp_path / "missing-project")}),
        encoding="utf-8",
    )
    ok, detail = MODULE.payload_parity(pointer)
    assert not ok
    assert "payload failed" in detail


def test_runtime_checks_fail_structurally_when_binaries_absent(monkeypatch) -> None:
    monkeypatch.setattr(MODULE, "resolve_client_binary", lambda name: None)

    checks = MODULE.runtime_checks()

    named = {check.name: check for check in checks}
    assert not named["runtime.claude-plugin"].ok
    assert "SYNTHESIS_CLAUDE_BIN" in named["runtime.claude-plugin"].detail
    assert not named["runtime.codex-plugin"].ok
    assert not named["runtime.codex-doctor"].ok
    assert "SYNTHESIS_CODEX_BIN" in named["runtime.codex-doctor"].detail


def test_runtime_checks_survive_vanishing_binary(monkeypatch) -> None:
    monkeypatch.setattr(
        MODULE, "resolve_client_binary", lambda name: f"/gone/{name}"
    )

    def raising_run(command, timeout=30):
        raise FileNotFoundError(command[0])

    monkeypatch.setattr(MODULE, "run", raising_run)

    checks = MODULE.runtime_checks()

    named = {check.name: check for check in checks}
    assert not named["runtime.claude-plugin"].ok
    assert not named["runtime.codex-plugin"].ok
    assert not named["runtime.codex-doctor"].ok


def test_plugin_inventory_rejects_unexpected_json_shapes(monkeypatch) -> None:
    monkeypatch.setattr(
        MODULE, "resolve_client_binary", lambda name: f"/fake/{name}"
    )

    class Result:
        returncode = 0
        stdout = '{"unexpected": "shape"}'
        stderr = ""

    monkeypatch.setattr(MODULE, "run", lambda command, timeout=30: Result())

    ok, detail = MODULE.plugin_inventory("claude")
    assert not ok
    assert "0 enabled" in detail

    ok, detail = MODULE.plugin_inventory("codex")
    assert not ok
    assert "0 enabled" in detail

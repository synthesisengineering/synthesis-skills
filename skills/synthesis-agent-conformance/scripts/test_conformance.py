from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).with_name("conformance.py")
SPEC = importlib.util.spec_from_file_location("conformance", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

from coordination_schema import identity_from_uuid


COORDINATION_HEADER = (
    "| session uuid | compact id | speakable id v1 | legacy id | agent | "
    "machine | project | started | heartbeat | mode | workspace(s) / branch | "
    "goal | claimed areas (advisory lock) | context role | status |\n"
    "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
)


def coordination_row(
    session_uuid: str,
    legacy: str,
    agent: str,
    machine: str,
    project: str,
    started: str,
    heartbeat: str,
    mode: str,
    workspace: str,
    goal: str,
    areas: str,
    role: str,
    status: str,
) -> str:
    identity = identity_from_uuid(session_uuid, legacy_id=legacy)
    return (
        f"| {identity.session_uuid} | {identity.compact_id} | "
        f"{identity.speakable_id} | {legacy} | {agent} | {machine} | "
        f"{project} | {started} | {heartbeat} | {mode} | {workspace} | "
        f"{goal} | {areas} | {role} | {status} |\n"
    )


def write_skill(root: Path, name: str) -> None:
    skill = root / "skills" / name
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: Test skill.\n"
        "license: CC0-1.0\ndepends_on: []\nmetadata:\n"
        "  author: Test\n  version: 1.0.0\n"
        "  source_repo: example.test/repo\n  source_type: public\n"
        "---\n\n# Test\n",
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


def stable_pointer(link: Path, version: str) -> Path:
    """A fake stable plugin pointer resolving to a fake verified install root."""
    root = link.parent / "roots" / version
    (root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    (root / ".claude-plugin" / "plugin.json").write_text(json.dumps({"version": version}))
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.is_symlink():
        link.unlink()
    link.symlink_to(root)
    return root


def cache_tree(root: Path) -> Path:
    """A fake installed cache tree: both manifest dirs present, then manifests."""
    root.mkdir(parents=True, exist_ok=True)
    write_manifests(root)
    return root


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

    (root / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [1.0.0] - 2026-01-01\n\n### Added\n\n- test\n",
        encoding="utf-8",
    )


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


def test_source_checks_fail_when_changelog_trails_manifests(tmp_path: Path) -> None:
    write_manifests(tmp_path)
    write_skill(tmp_path, "synthesis-test")
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [0.9.0] - 2025-12-01\n\n### Added\n\n- test\n",
        encoding="utf-8",
    )

    checks = MODULE.source_checks(tmp_path)

    parity = next(
        check for check in checks if check.name == "source.changelog-version-parity"
    )
    assert not parity.ok
    assert "changelog=0.9.0" in parity.detail


def test_source_checks_reject_dependency_cycles(tmp_path: Path) -> None:
    write_manifests(tmp_path)
    write_skill(tmp_path, "synthesis-one")
    write_skill(tmp_path, "synthesis-two")
    one = tmp_path / "skills" / "synthesis-one" / "SKILL.md"
    two = tmp_path / "skills" / "synthesis-two" / "SKILL.md"
    one.write_text(
        one.read_text(encoding="utf-8").replace(
            "depends_on: []", 'depends_on: ["synthesis-two"]'
        ),
        encoding="utf-8",
    )
    two.write_text(
        two.read_text(encoding="utf-8").replace(
            "depends_on: []", 'depends_on: ["synthesis-one"]'
        ),
        encoding="utf-8",
    )

    checks = MODULE.source_checks(tmp_path)

    cycle = next(check for check in checks if check.name == "source.dependencies-acyclic")
    assert cycle.ok is False
    assert "synthesis-one" in cycle.detail


def test_source_checks_fail_closed_without_changelog(tmp_path: Path) -> None:
    write_manifests(tmp_path)
    write_skill(tmp_path, "synthesis-test")
    (tmp_path / "CHANGELOG.md").unlink()

    checks = MODULE.source_checks(tmp_path)

    parity = next(
        check for check in checks if check.name == "source.changelog-version-parity"
    )
    assert not parity.ok


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


def test_source_scans_exclude_checker_definitions_by_relative_identity(
    tmp_path: Path,
) -> None:
    write_manifests(tmp_path)
    write_skill(tmp_path, "synthesis-test")
    checker_dir = (
        tmp_path
        / "skills"
        / "synthesis-agent-conformance"
        / "scripts"
    )
    checker_dir.mkdir(parents=True)
    fixtures = (
        '~/.claude/skills/synthesis-fixture\n'
        'synthesis-skills/synthesis-fixture\n'
        '~/workspaces/someone/synthesis-skills/skills\n'
    )
    (checker_dir / "conformance.py").write_text(fixtures, encoding="utf-8")
    (checker_dir / "test_conformance.py").write_text(fixtures, encoding="utf-8")

    checks = MODULE.source_checks(tmp_path)

    relevant = {
        check.name: check
        for check in checks
        if check.name
        in {
            "source.no-client-copy-paths",
            "source.no-old-source-layout",
            "source.no-personal-workspace-paths",
        }
    }
    assert set(relevant) == {
        "source.no-client-copy-paths",
        "source.no-old-source-layout",
        "source.no-personal-workspace-paths",
    }
    assert all(check.ok for check in relevant.values())


def test_instruction_adapter(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
    (tmp_path / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
    checks = MODULE.instruction_checks(tmp_path)
    assert all(check.ok for check in checks)


def test_coordination_board_schema(tmp_path: Path) -> None:
    board = tmp_path / "active-sessions.md"
    board.write_text(
        "# Coordination\n\n"
        "Schema: v3\n\n"
        "## Active sessions\n\n"
        + COORDINATION_HEADER
        + "\n"
        "## Messages\n\n---\n\n## Protocol\n",
        encoding="utf-8",
    )

    checks = MODULE.coordination_checks(board)

    assert all(check.ok for check in checks)


def test_coordination_board_rejects_semantic_conflict(tmp_path: Path) -> None:
    board = tmp_path / "active-sessions.md"
    board.write_text(
        "# Coordination\n\n"
        "Schema: v3\n\n"
        "## Active sessions\n\n"
        + COORDINATION_HEADER
        + coordination_row(
            "019fff79-5858-7993-a329-b301bccf5d62", "A", "Claude", "host-a",
            "shared", "2026-07-30T10:00:00-04:00", "2026-07-30T10:00:00-04:00",
            "interactive", "/tmp/a/repo @ feature/a", "work", "repo/**", "owner", "active",
        )
        + coordination_row(
            "019fff79-5858-7993-a329-b301bccf5d63", "B", "Codex", "host-b",
            "shared", "2026-07-30T10:00:00-04:00", "2026-07-30T10:00:00-04:00",
            "autonomous", "/tmp/b/repo @ feature/b", "work", "repo/file.md", "owner", "active",
        )
        + "\n"
        "## Messages\n\n---\n\n## Protocol\n",
        encoding="utf-8",
    )

    checks = MODULE.coordination_checks(board)

    doctor = next(
        check for check in checks if check.name == "coordination.semantic-doctor"
    )
    assert not doctor.ok


def test_activate_and_handoff(tmp_path: Path, monkeypatch) -> None:
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
    subprocess.run(
        ["git", "init", "--initial-branch", "feature/test", str(project)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(project), "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(project), "config", "user.name", "Test"], check=True
    )
    subprocess.run(
        ["git", "-C", str(project), "config", "core.hooksPath", "/dev/null"],
        check=True,
    )
    subprocess.run(["git", "-C", str(project), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(project), "commit", "-m", "test"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(project), "update-ref", "refs/remotes/origin/main", "HEAD"],
        check=True,
    )
    board = tmp_path / "active-sessions.md"
    now = datetime.now().astimezone().isoformat()
    board.write_text(
        "# Coordination\n\nSchema: v3\nLease: https://example.test/coordination.git\n"
        "## Active sessions\n\n"
        + COORDINATION_HEADER
        + coordination_row(
            "019fff79-5858-7993-a329-b301bccf5d62", "A", "Codex", "mac", "test",
            now, now, "autonomous", f"{project} @ feature/test", "work",
            f"{project}/**", "owner", "active",
        )
        + "\n"
        "## Messages\n\n---\n\n## Protocol\n",
        encoding="utf-8",
    )
    original_validate = MODULE.validate_active_project
    monkeypatch.setattr(
        MODULE,
        "validate_active_project",
        lambda payload, board: original_validate(payload, board, refresh_lease=False),
    )
    monkeypatch.setattr(
        MODULE,
        "load_and_validate",
        lambda pointer, board: (
            json.loads(pointer.read_text(encoding="utf-8")),
            original_validate(
                json.loads(pointer.read_text(encoding="utf-8")),
                board,
                refresh_lease=False,
            ),
        ),
    )
    monkeypatch.setattr(
        MODULE,
        "payload_parity",
        lambda pointer, board: (True, "identical context in fixture payloads"),
    )

    pointer = tmp_path / "active.json"
    activated = MODULE.activate(
        project, pointer, owner_session="A", coordination_board=board
    )
    assert all(check.ok for check in activated if check.required)
    payload = __import__("json").loads(pointer.read_text(encoding="utf-8"))
    assert payload["next"] == [
        "2. [ ] Continue the live check from verified state."
    ]
    handoff = MODULE.handoff_checks(project, pointer, board)
    assert all(check.ok for check in handoff if check.required)
    named = {check.name: check for check in handoff}
    assert named["handoff.payload-parity"].ok
    assert "identical context" in named["handoff.payload-parity"].detail
    assert named["handoff.record-freshness"].ok
    pointer_results = MODULE.pointer_checks(project, pointer, board)
    assert all(check.ok for check in pointer_results if check.required)


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
        git(clone, "config", "core.hooksPath", "/dev/null")
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


def write_stopped_project(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    project = repo / "projects" / "demo"
    plan = project / "resources" / "artifacts" / "demo-plan.md"
    plan.parent.mkdir(parents=True)
    (project / "sessions").mkdir()
    (project / "CONTEXT.md").write_text(
        "**Phase:** Ready\n"
        "**Status:** Paused\n\n"
        "[plan](resources/artifacts/demo-plan.md)\n\n"
        "## What's Next\n\n"
        "1. [ ] Resume on either client.\n",
        encoding="utf-8",
    )
    (project / "REFERENCE.md").write_text("# Reference\n", encoding="utf-8")
    plan.write_text("# Plan\n", encoding="utf-8")
    subprocess.run(
        ["git", "init", "--quiet", "--initial-branch", "main", str(repo)],
        check=True,
    )
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "core.hooksPath", "/dev/null"],
        check=True,
    )
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "seed"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "update-ref", "refs/remotes/origin/main", "HEAD"],
        check=True,
    )
    return project


def test_stopped_handoff_passes_without_active_pointer(tmp_path: Path) -> None:
    project = write_stopped_project(tmp_path)

    checks = MODULE.handoff_checks(
        project,
        tmp_path / "missing-pointer.json",
        tmp_path / "missing-board.md",
    )

    assert all(check.ok for check in checks if check.required)
    named = {check.name: check for check in checks}
    assert named["handoff.stopped-task-payload"].ok
    assert named["handoff.pointer-cache"].ok


def test_aggregate_pointer_scope_accepts_documented_cache_absence(
    tmp_path: Path,
) -> None:
    project = write_stopped_project(tmp_path)
    pointer = tmp_path / "missing-pointer.json"

    aggregate = MODULE.pointer_checks(
        project,
        pointer,
        tmp_path / "missing-board.md",
        require_pointer=False,
    )
    explicit = MODULE.pointer_checks(
        project,
        pointer,
        tmp_path / "missing-board.md",
    )

    assert all(check.ok for check in aggregate if check.required)
    assert "pointer.schema" not in {check.name for check in aggregate}
    assert not {check.name: check for check in explicit}["pointer.schema"].ok


def test_local_continuity_recovers_interrupted_attributed_edits(tmp_path: Path) -> None:
    project, _stale = clone_pair_with_project(tmp_path)
    context = project / "CONTEXT.md"
    context.write_text("**Phase:** interrupted\n", encoding="utf-8")
    state = tmp_path / "repo-guard"
    pending = state / "pending"
    pending.mkdir(parents=True)
    session_id = "interrupted-session"
    manifest = pending / (
        MODULE.hashlib.sha256(session_id.encode("utf-8")).hexdigest() + ".json"
    )
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "session_id": session_id,
                "paths": [str(context)],
                "remote_paths": [str(context)],
            }
        ),
        encoding="utf-8",
    )

    checks = MODULE.continuity_readiness_checks(project, "local", state)

    assert all(check.ok for check in checks if check.required)
    assert "LOCAL_RECOVERABLE" in checks[0].detail


def test_local_continuity_rejects_dirty_project_paths_missing_from_manifest(
    tmp_path: Path,
) -> None:
    project, _stale = clone_pair_with_project(tmp_path)
    context = project / "CONTEXT.md"
    reference = project / "REFERENCE.md"
    context.write_text("**Phase:** attributed\n", encoding="utf-8")
    reference.write_text("# Unattributed\n", encoding="utf-8")
    state = tmp_path / "repo-guard"
    pending = state / "pending"
    pending.mkdir(parents=True)
    session_id = "partial-session"
    manifest = pending / (
        MODULE.hashlib.sha256(session_id.encode("utf-8")).hexdigest() + ".json"
    )
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "session_id": session_id,
                "paths": [str(context)],
                "remote_paths": [str(context)],
            }
        ),
        encoding="utf-8",
    )

    checks = MODULE.continuity_readiness_checks(project, "local", state)

    local = next(check for check in checks if check.name == "continuity.local-state")
    assert not local.ok
    assert "REFERENCE.md" in local.detail


def test_remote_continuity_requires_clean_published_project(tmp_path: Path) -> None:
    project, _stale = clone_pair_with_project(tmp_path)

    checks = MODULE.continuity_readiness_checks(
        project, "remote", tmp_path / "empty-state"
    )

    assert all(check.ok for check in checks if check.required)
    assert any("REMOTE_READY" in check.detail for check in checks)


def test_remote_continuity_rejects_unpublished_commit_outside_project(
    tmp_path: Path,
) -> None:
    project, _stale = clone_pair_with_project(tmp_path)
    repo = project.parents[1]
    unrelated = repo / "unrelated.md"
    unrelated.write_text("not published\n", encoding="utf-8")
    subprocess = __import__("subprocess")
    subprocess.run(["git", "-C", str(repo), "add", "unrelated.md"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "--quiet", "-m", "unpublished"],
        check=True,
    )

    checks = MODULE.continuity_readiness_checks(
        project, "remote", tmp_path / "empty-state"
    )

    remote = next(
        check for check in checks if check.name == "continuity.remote-upstream"
    )
    assert not remote.ok
    assert "ahead=1" in remote.detail


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


def test_render_treats_required_unknown_as_non_success(capsys) -> None:
    checks = [MODULE.Check("hook-live.test", None, "no receipt", True, "live")]

    assert MODULE.render(checks, as_json=True) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "FAIL"
    assert payload["checks"][0]["status"] == "UNKNOWN"
    assert payload["checks"][0]["ok"] is None


def _hook_config(*, gate: bool = True, inbox: bool = True) -> dict:
    hooks: dict = {
        "SessionStart": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": "python3 ${CLAUDE_PLUGIN_ROOT}/skills/synthesis-agent-conformance/scripts/session_context.py --format claude",
                    }
                ]
            }
        ]
    }
    if gate:
        hooks["PreToolUse"] = [
            {
                "matcher": "SendMessage|mcp__ccd_session_mgmt__send_message",
                "hooks": [{"type": "command", "command": "python3 ${CLAUDE_PLUGIN_ROOT}/skills/synthesis-project-management/scripts/peer_send_gate.py --gate"}],
            },
            {
                "matcher": "Bash|exec_command|exec|shell|local_shell",
                "hooks": [{"type": "command", "command": "python3 ${CLAUDE_PLUGIN_ROOT}/skills/synthesis-project-management/scripts/peer_send_gate.py --gate"}],
            },
        ]
    if inbox:
        hooks["UserPromptSubmit"] = [
            {
                "hooks": [{"type": "command", "command": "python3 ${CLAUDE_PLUGIN_ROOT}/skills/synthesis-project-management/scripts/board_inbox.py --hook"}]
            }
        ]
    return {"hooks": hooks}


def test_hook_definition_checks_require_session_context(tmp_path: Path) -> None:
    hook_file = tmp_path / "hooks" / "hooks.json"
    hook_file.parent.mkdir()
    hook_file.write_text(json.dumps(_hook_config()), encoding="utf-8")

    checks = MODULE.hook_definition_checks(tmp_path)

    assert all(check.ok for check in checks), [c for c in checks if not c.ok]


def test_hook_definition_checks_require_the_peer_gate_and_the_inbox(tmp_path: Path) -> None:
    """A plugin whose hooks.json stops routing peer sends through the gate, or
    stops delivering the board inbox, fails source conformance: the 2026-09-02
    recurrence was a lane nothing gated."""
    hook_file = tmp_path / "hooks" / "hooks.json"
    hook_file.parent.mkdir()
    hook_file.write_text(json.dumps(_hook_config(gate=False, inbox=False)), encoding="utf-8")

    checks = {check.name: check for check in MODULE.hook_definition_checks(tmp_path)}

    assert checks["hook-definition.public-sessionstart"].ok
    assert not checks["hook-definition.public-peer-gate"].ok
    assert not checks["hook-definition.public-inbox"].ok


def test_shipped_hook_config_routes_peer_sends_through_the_gate() -> None:
    source_root = Path(__file__).resolve().parents[3]
    checks = {check.name: check for check in MODULE.hook_definition_checks(source_root)}
    assert checks["hook-definition.public-peer-gate"].ok, checks["hook-definition.public-peer-gate"].detail
    assert checks["hook-definition.public-inbox"].ok, checks["hook-definition.public-inbox"].detail


def test_hook_live_checks_reject_static_absence_and_accept_receipts(
    tmp_path: Path, monkeypatch,
) -> None:
    public_codex = tmp_path / "public-codex.json"
    public_claude = tmp_path / "public-claude.json"
    private = tmp_path / "private.json"
    source = tmp_path / "source"
    (source / ".codex-plugin").mkdir(parents=True)
    (source / ".codex-plugin" / "plugin.json").write_text(
        json.dumps({"version": "1.2.3"}), encoding="utf-8"
    )
    installed_roots = {
        "codex": tmp_path / "codex-cache" / "1.2.3",
        "claude": tmp_path / "claude-cache" / "1.2.3",
    }
    for root in installed_roots.values():
        root.mkdir(parents=True)
    codex_home = tmp_path / ".codex"
    claude_home = tmp_path / ".claude"
    transcripts = {
        "codex": codex_home / "sessions" / "public-1.jsonl",
        "claude": claude_home
        / "projects"
        / "workspace"
        / "019fff79-5858-7993-a329-b301bccf5d32.jsonl",
        "private": codex_home / "sessions" / "private.jsonl",
    }
    for transcript in transcripts.values():
        transcript.parent.mkdir(parents=True, exist_ok=True)
    transcripts["codex"].write_text(
        json.dumps(
            {
                "type": "session_meta",
                "payload": {"id": "019fff79-5858-7993-a329-b301bccf5d31"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    transcripts["claude"].write_text(
        json.dumps({"sessionId": "019fff79-5858-7993-a329-b301bccf5d32"})
        + "\n",
        encoding="utf-8",
    )
    transcripts["private"].write_text(
        json.dumps(
            {
                "type": "session_meta",
                "payload": {"id": "019fff79-5858-7993-a329-b301bccf5d33"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_home))
    monkeypatch.setattr(
        MODULE,
        "_enabled_plugin_root",
        lambda client, version, home=None: installed_roots[client]
        if version == "1.2.3"
        else None,
    )
    absent = MODULE.hook_live_checks(
        public_codex, public_claude, private, source
    )
    assert all(check.ok is None for check in absent)

    recorded_at = datetime.now(timezone.utc).isoformat()
    public_codex.write_text(
        json.dumps(
            {
                "hook_event_name": "SessionStart",
                "session_id": "019fff79-5858-7993-a329-b301bccf5d31",
                "client": "codex",
                "plugin_version": "1.2.3",
                "plugin_root": str(installed_roots["codex"]),
                "provenance_env": "codex-transcript",
                "transcript_path": str(transcripts["codex"]),
                "transcript_bound_at_record": True,
                "recorded_at": recorded_at,
            }
        ),
        encoding="utf-8",
    )
    public_claude.write_text(
        json.dumps(
            {
                "hook_event_name": "SessionStart",
                "session_id": "019fff79-5858-7993-a329-b301bccf5d32",
                "client": "claude",
                "plugin_version": "1.2.3",
                "plugin_root": str(installed_roots["claude"]),
                "provenance_env": "claude-transcript",
                "transcript_path": str(transcripts["claude"]),
                "transcript_bound_at_record": True,
                "recorded_at": recorded_at,
            }
        ),
        encoding="utf-8",
    )
    private.write_text(
        json.dumps(
            {
                "hook_event_name": "SessionStart",
                "session_id": "019fff79-5858-7993-a329-b301bccf5d33",
                "client": "codex",
                "provenance_env": "codex-transcript",
                "transcript_path": str(transcripts["private"]),
                "recorded_at": recorded_at,
            }
        ),
        encoding="utf-8",
    )
    present = MODULE.hook_live_checks(
        public_codex, public_claude, private, source
    )
    assert all(check.ok for check in present)

    valid_codex = json.loads(public_codex.read_text(encoding="utf-8"))
    invalid_codex = dict(valid_codex)
    invalid_codex["transcript_bound_at_record"] = False
    public_codex.write_text(json.dumps(invalid_codex), encoding="utf-8")
    invalid_codex_checks = MODULE.hook_live_checks(
        public_codex, public_claude, private, source
    )
    assert next(
        check for check in invalid_codex_checks
        if check.name == "hook-live.public-codex-sessionstart"
    ).ok is False

    missing_codex_flag = dict(valid_codex)
    missing_codex_flag.pop("transcript_bound_at_record")
    public_codex.write_text(json.dumps(missing_codex_flag), encoding="utf-8")
    missing_codex_checks = MODULE.hook_live_checks(
        public_codex, public_claude, private, source
    )
    assert next(
        check for check in missing_codex_checks
        if check.name == "hook-live.public-codex-sessionstart"
    ).ok is False
    public_codex.write_text(json.dumps(valid_codex), encoding="utf-8")

    valid_claude = json.loads(public_claude.read_text(encoding="utf-8"))
    invalid_claude = dict(valid_claude)
    invalid_claude["transcript_bound_at_record"] = "true"
    public_claude.write_text(json.dumps(invalid_claude), encoding="utf-8")
    invalid_claude_checks = MODULE.hook_live_checks(
        public_codex, public_claude, private, source
    )
    assert next(
        check for check in invalid_claude_checks
        if check.name == "hook-live.public-claude-sessionstart"
    ).ok is False
    public_claude.write_text(json.dumps(valid_claude), encoding="utf-8")

    stale = json.loads(public_codex.read_text(encoding="utf-8"))
    stale["recorded_at"] = (
        datetime.now(timezone.utc) - timedelta(hours=25)
    ).isoformat()
    public_codex.write_text(json.dumps(stale), encoding="utf-8")
    expired = MODULE.hook_live_checks(
        public_codex, public_claude, private, source
    )
    assert next(
        check for check in expired
        if check.name == "hook-live.public-codex-sessionstart"
    ).ok is False


def test_deferred_claude_receipt_requires_eventual_transcript_binding(
    tmp_path: Path, monkeypatch
) -> None:
    claude_home = tmp_path / ".claude"
    session_id = "019fff79-5858-7993-a329-b301bccf5d36"
    transcript = claude_home / "projects" / "workspace" / f"{session_id}.jsonl"
    transcript.parent.mkdir(parents=True)
    installed_root = tmp_path / "plugin" / "1.2.3"
    installed_root.mkdir(parents=True)
    receipt = tmp_path / "public-sessionstart-claude.json"
    receipt.write_text(
        json.dumps(
            {
                "hook_event_name": "SessionStart",
                "session_id": session_id,
                "client": "claude",
                "plugin_version": "1.2.3",
                "plugin_root": str(installed_root),
                "provenance_env": "claude-transcript",
                "transcript_path": str(transcript),
                "transcript_bound_at_record": False,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_home))

    before: list[MODULE.Check] = []
    MODULE._receipt_check(
        before,
        "hook-live.public-claude-sessionstart",
        receipt,
        expected_client="claude",
        expected_plugin_version="1.2.3",
        expected_plugin_root=installed_root,
    )
    assert before[0].ok is False

    transcript.write_text(
        json.dumps({"sessionId": "019fff79-5858-7993-a329-b301bccf5d99"})
        + "\n",
        encoding="utf-8",
    )
    conflicting: list[MODULE.Check] = []
    MODULE._receipt_check(
        conflicting,
        "hook-live.public-claude-sessionstart",
        receipt,
        expected_client="claude",
        expected_plugin_version="1.2.3",
        expected_plugin_root=installed_root,
    )
    assert conflicting[0].ok is False

    transcript.write_text(
        json.dumps({"sessionId": session_id}) + "\n",
        encoding="utf-8",
    )
    after: list[MODULE.Check] = []
    MODULE._receipt_check(
        after,
        "hook-live.public-claude-sessionstart",
        receipt,
        expected_client="claude",
        expected_plugin_version="1.2.3",
        expected_plugin_root=installed_root,
    )
    assert after[0].ok is True


def test_hook_live_distinguishes_latest_drift_from_preserved_session_evidence(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "source"
    (source / ".codex-plugin").mkdir(parents=True)
    (source / ".codex-plugin" / "plugin.json").write_text(
        json.dumps({"version": "1.2.3"}), encoding="utf-8"
    )
    installed_roots = {
        "codex": tmp_path / "codex-cache" / "1.2.3",
        "claude": tmp_path / "claude-cache" / "1.2.3",
    }
    for root in installed_roots.values():
        root.mkdir(parents=True)
    monkeypatch.setattr(
        MODULE,
        "_enabled_plugin_root",
        lambda client, version, home=None: installed_roots[client],
    )

    codex_home = tmp_path / ".codex"
    claude_home = tmp_path / ".claude"
    codex_session = "019fff79-5858-7993-a329-b301bccf5d61"
    accepted_claude_session = "019fff79-5858-7993-a329-b301bccf5d62"
    unrelated_claude_session = "019fff79-5858-7993-a329-b301bccf5d63"
    codex_transcript = codex_home / "sessions" / f"{codex_session}.jsonl"
    accepted_transcript = (
        claude_home
        / "projects"
        / "workspace"
        / f"{accepted_claude_session}.jsonl"
    )
    unrelated_transcript = (
        claude_home
        / "projects"
        / "workspace"
        / f"{unrelated_claude_session}.jsonl"
    )
    codex_transcript.parent.mkdir(parents=True)
    accepted_transcript.parent.mkdir(parents=True)
    codex_transcript.write_text(
        json.dumps(
            {"type": "session_meta", "payload": {"id": codex_session}}
        )
        + "\n",
        encoding="utf-8",
    )
    accepted_transcript.write_text(
        json.dumps({"sessionId": accepted_claude_session}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_home))

    public_codex = tmp_path / "public-sessionstart-codex.json"
    public_claude = tmp_path / "public-sessionstart-claude.json"
    now = datetime.now(timezone.utc).isoformat()
    public_codex.write_text(
        json.dumps(
            {
                "hook_event_name": "SessionStart",
                "session_id": codex_session,
                "client": "codex",
                "plugin_version": "1.2.3",
                "plugin_root": str(installed_roots["codex"]),
                "provenance_env": "codex-transcript",
                "transcript_path": str(codex_transcript),
                "transcript_bound_at_record": True,
                "recorded_at": now,
            }
        ),
        encoding="utf-8",
    )
    public_claude.write_text(
        json.dumps(
            {
                "hook_event_name": "SessionStart",
                "session_id": unrelated_claude_session,
                "client": "claude",
                "plugin_version": "1.2.3",
                "plugin_root": str(installed_roots["claude"]),
                "provenance_env": "claude-transcript",
                "transcript_path": str(unrelated_transcript),
                "transcript_bound_at_record": False,
                "recorded_at": now,
            }
        ),
        encoding="utf-8",
    )

    def store_event(
        latest: Path,
        *,
        client: str,
        session_id: str,
        event_id: str,
        version: str,
        plugin_root: Path,
        transcript: Path,
        age_hours: int,
    ) -> Path:
        event = (
            MODULE.receipt_registry_root(latest, client)
            / client
            / session_id
            / f"{event_id}.json"
        )
        event.parent.mkdir(parents=True, exist_ok=True)
        event.write_text(
            json.dumps(
                {
                    "receipt_schema": 2,
                    "receipt_event_id": event_id,
                    "hook_event_name": "SessionStart",
                    "session_id": session_id,
                    "client": client,
                    "plugin_version": version,
                    "plugin_root": str(plugin_root),
                    "provenance_env": f"{client}-transcript",
                    "transcript_path": str(transcript),
                    "transcript_bound_at_record": True,
                    "recorded_at": (
                        datetime.now(timezone.utc) - timedelta(hours=age_hours)
                    ).isoformat(),
                }
            ),
            encoding="utf-8",
        )
        return event

    accepted_claude_event = store_event(
        public_claude,
        client="claude",
        session_id=accepted_claude_session,
        event_id="019fff79-5858-7993-a329-b301bccf5d64",
        version="1.2.3",
        plugin_root=installed_roots["claude"],
        transcript=accepted_transcript,
        age_hours=48,
    )
    store_event(
        public_claude,
        client="claude",
        session_id=accepted_claude_session,
        event_id="019fff79-5858-7993-a329-b301bccf5d65",
        version="1.2.4",
        plugin_root=tmp_path / "claude-cache" / "1.2.4",
        transcript=accepted_transcript,
        age_hours=1,
    )
    accepted_codex_event = store_event(
        public_codex,
        client="codex",
        session_id=codex_session,
        event_id="019fff79-5858-7993-a329-b301bccf5d66",
        version="1.2.3",
        plugin_root=installed_roots["codex"],
        transcript=codex_transcript,
        age_hours=48,
    )
    store_event(
        public_codex,
        client="codex",
        session_id=codex_session,
        event_id="019fff79-5858-7993-a329-b301bccf5d67",
        version="1.2.4",
        plugin_root=tmp_path / "codex-cache" / "1.2.4",
        transcript=codex_transcript,
        age_hours=1,
    )

    latest = MODULE.hook_live_checks(
        public_codex, public_claude, source_root=source
    )
    latest_claude = next(
        check
        for check in latest
        if check.name == "hook-live.public-claude-sessionstart"
    )
    assert latest_claude.ok is False
    assert "scope=latest" in latest_claude.detail

    accepted = MODULE.hook_live_checks(
        public_codex,
        public_claude,
        source_root=source,
        codex_receipt_session_id=codex_session,
        claude_receipt_session_id=accepted_claude_session,
    )
    assert all(check.ok for check in accepted)
    accepted_claude = next(
        check
        for check in accepted
        if check.name == "hook-live.public-claude-sessionstart"
    )
    assert f"scope=session:{accepted_claude_session}" in accepted_claude.detail
    assert f"receipt={accepted_claude_event}" in accepted_claude.detail
    accepted_codex = next(
        check
        for check in accepted
        if check.name == "hook-live.public-codex-sessionstart"
    )
    assert f"scope=session:{codex_session}" in accepted_codex.detail
    assert f"receipt={accepted_codex_event}" in accepted_codex.detail


def test_exact_receipt_selectors_cannot_replace_all_current_health(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "conformance.py",
            "all",
            "--claude-receipt-session-id",
            "019fff79-5858-7993-a329-b301bccf5d62",
        ],
    )

    with pytest.raises(SystemExit, match="only with hook-live"):
        MODULE.main()


def test_claude_receipt_rejects_subagent_transcript_with_parent_uuid(
    tmp_path: Path, monkeypatch
) -> None:
    claude_home = tmp_path / ".claude"
    session_id = "019fff79-5858-7993-a329-b301bccf5d40"
    transcript = (
        claude_home
        / "projects"
        / "workspace"
        / session_id
        / "subagents"
        / "agent-a1.jsonl"
    )
    transcript.parent.mkdir(parents=True)
    transcript.write_text(
        json.dumps({"sessionId": session_id, "agentId": "a1"}) + "\n",
        encoding="utf-8",
    )
    installed_root = tmp_path / "plugin" / "1.2.3"
    installed_root.mkdir(parents=True)
    receipt = tmp_path / "public-sessionstart-claude.json"
    receipt.write_text(
        json.dumps(
            {
                "hook_event_name": "SessionStart",
                "session_id": session_id,
                "client": "claude",
                "plugin_version": "1.2.3",
                "plugin_root": str(installed_root),
                "provenance_env": "claude-transcript",
                "transcript_path": str(transcript),
                "transcript_bound_at_record": True,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_home))

    checks: list[MODULE.Check] = []
    MODULE._receipt_check(
        checks,
        "hook-live.public-claude-sessionstart",
        receipt,
        expected_client="claude",
        expected_plugin_version="1.2.3",
        expected_plugin_root=installed_root,
    )
    assert checks[0].ok is False


def test_claude_receipt_rejects_lexical_parent_transcript_path(
    tmp_path: Path, monkeypatch
) -> None:
    claude_home = tmp_path / ".claude"
    session_id = "019fff79-5858-7993-a329-b301bccf5d44"
    (claude_home / "projects").mkdir(parents=True)
    actual_transcript = claude_home / f"{session_id}.jsonl"
    actual_transcript.write_text(
        json.dumps({"sessionId": session_id}) + "\n",
        encoding="utf-8",
    )
    lexical_transcript = (
        claude_home / "projects" / ".." / f"{session_id}.jsonl"
    )
    installed_root = tmp_path / "plugin" / "1.2.3"
    installed_root.mkdir(parents=True)
    receipt = tmp_path / "public-sessionstart-claude.json"
    receipt.write_text(
        json.dumps(
            {
                "hook_event_name": "SessionStart",
                "session_id": session_id,
                "client": "claude",
                "plugin_version": "1.2.3",
                "plugin_root": str(installed_root),
                "provenance_env": "claude-transcript",
                "transcript_path": str(lexical_transcript),
                "transcript_bound_at_record": True,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_home))

    checks: list[MODULE.Check] = []
    MODULE._receipt_check(
        checks,
        "hook-live.public-claude-sessionstart",
        receipt,
        expected_client="claude",
        expected_plugin_version="1.2.3",
        expected_plugin_root=installed_root,
    )
    assert checks[0].ok is False


def test_public_hook_live_checks_do_not_require_private_control_plane(
    tmp_path: Path, monkeypatch,
) -> None:
    source = tmp_path / "source"
    (source / ".codex-plugin").mkdir(parents=True)
    (source / ".codex-plugin" / "plugin.json").write_text(
        json.dumps({"version": "1.2.3"}), encoding="utf-8"
    )
    monkeypatch.setattr(
        MODULE, "_enabled_plugin_root", lambda client, version, home=None: tmp_path / client
    )

    checks = MODULE.hook_live_checks(
        tmp_path / "codex.json", tmp_path / "claude.json", source_root=source
    )

    assert [check.name for check in checks] == [
        "hook-live.public-codex-sessionstart",
        "hook-live.public-claude-sessionstart",
    ]


def test_hook_live_fails_closed_without_source_version(tmp_path: Path) -> None:
    checks = MODULE.hook_live_checks(source_root=tmp_path / "missing")

    assert [check.name for check in checks] == ["hook-live.source-version"]
    assert checks[0].ok is False


def test_hook_trust_requires_public_sessionstart_to_be_enabled(monkeypatch) -> None:
    monkeypatch.setattr(
        MODULE,
        "codex_hook_audit",
        lambda _cwds: {
            "status": "PASS",
            "pending_review": 0,
            "errors": [],
            "hooks": [
                {
                    "plugin_id": "synthesis-skills@test",
                    "event": "sessionStart",
                    "key": "plugin:0:0",
                    "enabled": False,
                    "managed": False,
                    "trust_status": "trusted",
                    "current_hash": "sha256:test",
                }
            ],
        },
    )

    checks = MODULE.hook_trust_checks(Path("/tmp"))
    public = next(
        check for check in checks
        if check.name == "hook-trust.codex-public-sessionstart"
    )

    assert public.ok is False


def test_hook_trust_accepts_protocol_sessionstart_event(monkeypatch) -> None:
    monkeypatch.setattr(
        MODULE,
        "codex_hook_audit",
        lambda _cwds: {
            "status": "PASS",
            "pending_review": 0,
            "errors": [],
            "hooks": [
                {
                    "plugin_id": "synthesis-skills@test",
                    "event": "sessionStart",
                    "key": "plugin:0:0",
                    "enabled": True,
                    "managed": False,
                    "trust_status": "trusted",
                    "current_hash": "sha256:test",
                }
            ],
        },
    )

    checks = MODULE.hook_trust_checks(Path("/tmp"))
    public = next(
        check for check in checks
        if check.name == "hook-trust.codex-public-sessionstart"
    )

    assert public.ok is True


def test_instruction_budget_reserves_space(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    codex = home / ".codex"
    codex.mkdir(parents=True)
    (codex / "config.toml").write_text(
        "project_doc_max_bytes = 10000\n", encoding="utf-8"
    )
    (codex / "AGENTS.md").write_text(
        "x" * 5000 + "\n<!-- synthesis-agent-rules:end -->\n",
        encoding="utf-8",
    )
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "AGENTS.md").write_text("y" * 500, encoding="utf-8")

    checks = MODULE.instruction_budget_checks(repo, home)
    assert all(check.ok for check in checks)

    (repo / "AGENTS.md").write_text("y" * 1200, encoding="utf-8")
    checks = MODULE.instruction_budget_checks(repo, home)
    budget = next(
        check for check in checks if check.name == "instruction-budget.codex-bytes"
    )
    assert not budget.ok


def test_instruction_budget_parses_valid_toml_integer_forms(tmp_path: Path) -> None:
    home = tmp_path / "home"
    codex = home / ".codex"
    codex.mkdir(parents=True)
    (codex / "AGENTS.md").write_text(
        "rules\n<!-- synthesis-agent-rules:end -->\n", encoding="utf-8"
    )
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "AGENTS.md").write_text("project\n", encoding="utf-8")

    for declaration in (
        "project_doc_max_bytes = 10_000\n",
        "project_doc_max_bytes = 10000 # documented cap\n",
    ):
        (codex / "config.toml").write_text(declaration, encoding="utf-8")
        checks = MODULE.instruction_budget_checks(repo, home)
        budget = next(
            check for check in checks
            if check.name == "instruction-budget.codex-bytes"
        )
        assert "limit=10000" in budget.detail


def test_instruction_budget_fails_closed_on_invalid_toml(tmp_path: Path) -> None:
    home = tmp_path / "home"
    codex = home / ".codex"
    codex.mkdir(parents=True)
    (codex / "config.toml").write_text(
        'project_doc_max_bytes = "large"\n', encoding="utf-8"
    )
    repo = tmp_path / "repo"
    repo.mkdir()

    checks = MODULE.instruction_budget_checks(repo, home)

    assert [check.name for check in checks] == ["instruction-budget.codex-config"]
    assert checks[0].ok is False


def test_instruction_budget_requires_generated_user_tail_sentinel(tmp_path: Path) -> None:
    home = tmp_path / "home"
    codex = home / ".codex"
    codex.mkdir(parents=True)
    (codex / "config.toml").write_text(
        "project_doc_max_bytes = 10000\n", encoding="utf-8"
    )
    (codex / "AGENTS.md").write_text("truncated\n", encoding="utf-8")
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "AGENTS.md").write_text("project\n", encoding="utf-8")

    checks = MODULE.instruction_budget_checks(repo, home)
    sentinel = next(
        check for check in checks
        if check.name == "instruction-budget.user-tail-sentinel"
    )

    assert sentinel.ok is False


def test_instruction_budget_counts_root_to_target_override_chain(tmp_path: Path) -> None:
    home = tmp_path / "home"
    codex = home / ".codex"
    codex.mkdir(parents=True)
    (codex / "config.toml").write_text(
        'project_doc_max_bytes = 20000\nproject_doc_fallback_filenames = ["CLAUDE.md"]\n',
        encoding="utf-8",
    )
    (codex / "AGENTS.md").write_text("user\n", encoding="utf-8")
    repo = tmp_path / "repo"
    nested = repo / "packages" / "app"
    nested.mkdir(parents=True)
    subprocess.run(
        ["git", "-C", str(repo), "init", "--initial-branch", "main"],
        check=True,
        capture_output=True,
    )
    (repo / "AGENTS.md").write_text("root\n", encoding="utf-8")
    (repo / "packages" / "AGENTS.override.md").write_text(
        "scoped\n", encoding="utf-8"
    )
    (nested / "CLAUDE.md").write_text("fallback\n", encoding="utf-8")

    checks = MODULE.instruction_budget_checks(nested, home)
    budget = next(
        check for check in checks if check.name == "instruction-budget.codex-bytes"
    )

    assert budget.ok
    assert "4 file(s)" in budget.detail


def test_capability_checks_reject_incomplete_or_misattributed_evidence(
    tmp_path: Path, monkeypatch
) -> None:
    evidence = tmp_path / "capabilities.json"
    evidence.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "entries": {
                    "codex-cli.repository": {
                        "client": "claude-code",
                        "capability": "repository",
                        "status": "PASS",
                        "checked_at": datetime.now(timezone.utc).isoformat(),
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(MODULE, "resolve_client_binary", lambda client: f"/{client}")

    checks = MODULE.capability_checks(tmp_path, evidence)
    target = next(
        check for check in checks if check.name == "capability.codex-cli.repository"
    )

    assert target.ok is False
    assert target.status == "FAIL"
    assert "client must equal codex-cli" in target.detail
    assert "evidence_kind is invalid" in target.detail
    assert "detail must contain 1-500 characters" in target.detail


def test_capability_checks_never_echo_stored_authentication_material(
    tmp_path: Path, monkeypatch
) -> None:
    evidence = tmp_path / "capabilities.json"
    credential = "github_pat_" + "A" * 82
    evidence.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "entries": {
                    "codex-cli.repository": {
                        "client": "codex-cli",
                        "capability": "repository",
                        "status": "PASS",
                        "evidence_kind": "authenticated-cli",
                        "detail": credential,
                        "checked_at": datetime.now(timezone.utc).isoformat(),
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(MODULE, "resolve_client_binary", lambda client: f"/{client}")

    checks = MODULE.capability_checks(tmp_path, evidence)
    target = next(
        check for check in checks if check.name == "capability.codex-cli.repository"
    )

    assert target.ok is False
    assert "authentication material" in target.detail
    assert credential not in target.detail


def test_catalog_checks_enforce_installed_content_parity(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    write_manifests(source)
    write_skill(source, "synthesis-one")
    home = tmp_path / "home"
    for client in ("claude", "codex"):
        cache_root = (
            home
            / f".{client}"
            / "plugins"
            / "cache"
            / "marketplace"
            / "synthesis-skills"
            / "1.0.0"
        )
        shutil.copytree(source / "skills", cache_root / "skills")

    monkeypatch.setattr(
        MODULE,
        "codex_skill_catalog_audit",
        lambda source_root, home=None: {
            "status": "PASS",
            "discovered_skill_count": 1,
            "skill_count": 1,
            "full_cost_tokens": 100,
            "budget_tokens": 2_000,
            "model": "test-model",
            "errors": [],
        },
    )
    monkeypatch.setattr(
        MODULE,
        "_enabled_plugin_root",
        lambda client, version, home=None: (
            home
            / f".{client}"
            / "plugins"
            / "cache"
            / "marketplace"
            / "synthesis-skills"
            / version
        ),
    )

    checks = MODULE.catalog_checks(source, home)

    assert all(check.ok for check in checks)

    source_bytecode = (
        source
        / "skills"
        / "synthesis-one"
        / "scripts"
        / "__pycache__"
        / "probe.cpython-312.pyc"
    )
    source_bytecode.parent.mkdir(parents=True)
    source_bytecode.write_bytes(b"transient source bytecode")
    for suffix in ("pyc", "pyo"):
        (source_bytecode.parents[1] / f"direct-bytecode.{suffix}").write_bytes(
            b"transient direct bytecode"
        )
    installed_pytest_cache = (
        home
        / ".claude"
        / "plugins"
        / "cache"
        / "marketplace"
        / "synthesis-skills"
        / "1.0.0"
        / "skills"
        / ".pytest_cache"
        / "README.md"
    )
    installed_pytest_cache.parent.mkdir(parents=True)
    installed_pytest_cache.write_text("transient test cache\n", encoding="utf-8")

    checks = MODULE.catalog_checks(source, home)

    assert all(check.ok for check in checks)

    drifted = (
        home
        / ".codex"
        / "plugins"
        / "cache"
        / "marketplace"
        / "synthesis-skills"
        / "1.0.0"
        / "skills"
        / "synthesis-one"
        / "agents"
        / "openai.yaml"
    )
    drifted.write_text("policy:\n  allow_implicit_invocation: false\n", encoding="utf-8")

    checks = MODULE.catalog_checks(source, home)
    codex_cache = next(check for check in checks if check.name == "catalog.codex-cache")
    assert codex_cache.ok is False
    assert "source_digest=" in codex_cache.detail


def test_directory_digest_ignores_cache_children_not_cache_named_ancestors(
    tmp_path: Path,
) -> None:
    cache_named_checkout = tmp_path / "__pycache__" / "source"
    regular_checkout = tmp_path / "regular"
    cache_named_checkout.mkdir(parents=True)
    regular_checkout.mkdir()
    cache_named_skill = cache_named_checkout / "SKILL.md"
    cache_named_skill.write_text("same\n", encoding="utf-8")
    (regular_checkout / "SKILL.md").write_text("same\n", encoding="utf-8")

    original = MODULE.directory_digest(cache_named_checkout)
    assert original == MODULE.directory_digest(
        regular_checkout
    )
    cache_named_skill.write_text("changed\n", encoding="utf-8")
    assert MODULE.directory_digest(cache_named_checkout) != original


def test_enabled_codex_root_binds_to_inventory_marketplace(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    selected = (
        home
        / ".codex"
        / "plugins"
        / "cache"
        / "selected-marketplace"
        / "synthesis-skills"
        / "1.0.0"
    )
    alternate = (
        home
        / ".codex"
        / "plugins"
        / "cache"
        / "zzz-alternate"
        / "synthesis-skills"
        / "1.0.0"
    )
    selected.mkdir(parents=True)
    alternate.mkdir(parents=True)

    class Result:
        returncode = 0
        stdout = json.dumps(
            {
                "installed": [
                    {
                        "name": "synthesis-skills",
                        "enabled": True,
                        "version": "1.0.0",
                        "marketplaceName": "selected-marketplace",
                    }
                ]
            }
        )
        stderr = ""

    monkeypatch.setattr(MODULE, "resolve_client_binary", lambda _client: "/codex")
    monkeypatch.setattr(MODULE, "run", lambda *args, **kwargs: Result())

    assert MODULE._enabled_plugin_root("codex", "1.0.0", home) == selected


def test_client_config_dirs_honor_supported_environment_variables(
    tmp_path: Path, monkeypatch
) -> None:
    codex_home = tmp_path / "custom-codex"
    claude_home = tmp_path / "custom-claude"
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_home))

    assert MODULE._client_config_dir("codex") == codex_home
    assert MODULE._client_config_dir("claude") == claude_home


def test_parity_uses_configured_client_homes(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source"
    source.mkdir()
    write_manifests(source)
    codex_home = tmp_path / "custom-codex"
    claude_home = tmp_path / "custom-claude"
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_home))
    for client_home in (codex_home, claude_home):
        cache_tree(
            client_home / "plugins" / "cache" / "market" / "synthesis-skills" / "1.0.0"
        )

    class Result:
        returncode = 0
        stderr = ""

        def __init__(self, stdout: str):
            self.stdout = stdout

    monkeypatch.setattr(
        MODULE, "resolve_client_binary", lambda client: f"/fake/{client}"
    )
    observed_environments = []
    monkeypatch.setattr(
        MODULE,
        "run",
        lambda command, timeout=30, input_text=None, env=None: (
            observed_environments.append(env)
            or Result(
                json.dumps(
                    [
                        {
                            "id": "synthesis-skills@synthesis-engineering",
                            "enabled": True,
                            "version": "1.0.0",
                        }
                    ]
                    if command[0].endswith("claude")
                    else {
                        "installed": [
                            {
                                "name": "synthesis-skills",
                                "enabled": True,
                                "version": "1.0.0",
                            }
                        ]
                    }
                )
            )
        ),
    )

    monkeypatch.setenv("SYNTHESIS_STABLE_PLUGIN_ROOT", str(tmp_path / "stable"))
    stable_pointer(tmp_path / "stable" / "synthesis-skills" / "current", "1.0.0")
    checks = MODULE.parity_checks(source)

    assert all(check.ok for check in checks)
    assert {
        environment["CLAUDE_CONFIG_DIR"]
        for environment in observed_environments
        if "CLAUDE_CONFIG_DIR" in environment
    } == {str(claude_home)}
    assert {
        environment["CODEX_HOME"]
        for environment in observed_environments
        if "CODEX_HOME" in environment
    } == {str(codex_home)}


def test_parity_uses_enabled_inventory_not_newest_cache(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    write_manifests(source)
    for client in ("claude", "codex"):
        (
            tmp_path
            / f".{client}"
            / "plugins"
            / "cache"
            / "market"
            / "synthesis-skills"
            / "9.9.9"
        ).mkdir(parents=True)
        cache_tree(
            tmp_path / f".{client}" / "plugins" / "cache" / "market" / "synthesis-skills" / "1.0.0"
        )

    class Result:
        returncode = 0
        stderr = ""

        def __init__(self, stdout: str):
            self.stdout = stdout

    monkeypatch.setattr(
        MODULE, "resolve_client_binary", lambda client: f"/fake/{client}"
    )
    monkeypatch.setattr(
        MODULE,
        "run",
        lambda command, timeout=30, input_text=None, env=None: Result(
            json.dumps(
                [
                    {
                        "id": "synthesis-skills@synthesis-engineering",
                        "enabled": True,
                        "version": "1.0.0",
                    }
                ]
                if command[0].endswith("claude")
                else {
                    "installed": [
                        {
                            "name": "synthesis-skills",
                            "enabled": True,
                            "version": "1.0.0",
                        }
                    ]
                }
            )
        ),
    )

    stable_pointer(tmp_path / ".synthesis" / "plugins" / "synthesis-skills" / "current", "1.0.0")
    checks = MODULE.parity_checks(source, tmp_path)

    assert all(check.ok for check in checks)


def test_surface_checks_report_ide_as_explicitly_unsupported(tmp_path: Path) -> None:
    write_manifests(tmp_path)

    checks = MODULE.surface_checks(tmp_path)
    by_name = {check.name: check for check in checks}

    assert by_name["surface.claude-code"].status == "PASS"
    assert by_name["surface.codex-desktop"].status == "PASS"
    assert by_name["surface.codex-cli"].status == "PASS"
    assert by_name["surface.codex-ide"].status == "UNSUPPORTED"
    assert not by_name["surface.codex-ide"].required


def test_five_plane_vocabulary_is_stable() -> None:
    checks: list[MODULE.Check] = []
    for name in (
        "source.schema",
        "parity.clients",
        "hook-live.codex",
        "pointer.owner",
        "capability.codex-cli.repository",
    ):
        MODULE.add(checks, name, True, "ok")

    assert [check.plane for check in checks] == [
        "source",
        "installed",
        "live",
        "continuity",
        "capability",
    ]


def test_render_atomically_writes_the_same_structured_evidence(
    tmp_path: Path, capsys
) -> None:
    report = tmp_path / "evidence" / "last-report.json"
    checks = [MODULE.Check("source.test", True, "ok", plane="source")]

    assert MODULE.render(checks, True, report) == 0

    stdout = json.loads(capsys.readouterr().out)
    cached = json.loads(report.read_text(encoding="utf-8"))
    assert stdout == cached
    assert cached["checks"][0]["plane"] == "source"
    assert not list(report.parent.glob("last-report.json.*.tmp"))

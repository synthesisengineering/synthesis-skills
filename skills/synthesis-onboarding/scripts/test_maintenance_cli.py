"""Exercise delivered CLI, fail-closed helper closure and negative filesystem effects."""

import json
import pytest
import synthesis_cli as cli
from system_contract import SystemState
from test_release_runtime import active as _active, replace, write_receipt

import release_runtime as runtime
import system_contract

active = _active


def test_real_cli_review_is_readonly_and_reports_unknown(tmp_path, capsys):
    state = SystemState(tmp_path / "absent")
    inventory = tmp_path / "inventory.json"
    inventory.write_text(
        json.dumps(
            {
                "schema": 1,
                "components": [{"id": "unowned", "kind": "provider"}],
                "registries": [],
            }
        )
    )
    assert (
        cli.main(
            ["machine", "review", "--inventory", str(inventory), "--json"], state=state
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    assert report["health"] == "UNKNOWN" and report["coverage"] == "declared-only"
    assert not state.home.exists()


def test_cli_refuses_missing_consent(tmp_path):
    for argv in [
        ["machine", "apply", "--inventory", "x", "--plan", "y"],
        ["machine", "recover"],
        ["project-migrate", "plan", "--index", "x", "--target-format", "2"],
    ]:
        with pytest.raises(SystemExit) as result:
            cli.build_parser().parse_args(argv)
        assert result.value.code == 2


def test_cli_campaign_status_has_no_state_side_effects(tmp_path, capsys):
    state = SystemState(tmp_path / "absent")
    assert (
        cli.main(
            [
                "campaign",
                "status",
                "--client",
                "codex",
                "--release",
                "4.149.9",
                "--json",
            ],
            state=state,
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["idle_sessions"] == "NOT_NOTIFIED"
    assert not state.home.exists()


@pytest.mark.parametrize("change", ["missing", "changed", "symlink"])
def test_actual_launcher_verifies_new_cli_dependency(active, monkeypatch, change):
    pointer, root, data = active
    script = "synthesis-onboarding/scripts/synthesis_cli.py"
    for relative in (script, *runtime.ENTRYPOINT_DEPENDENCIES[script]):
        p = root / "skills" / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("pass\n")
    data = replace(
        pointer, data, content_digest=system_contract.canonical_tree_digest(root)
    )
    # A cached activation receipt must not turn a changed executable helper
    # into an allowed dispatch. Same full verification owner as production.
    write_receipt(pointer, root, data)
    target = root / "skills" / runtime.ENTRYPOINT_DEPENDENCIES[script][0]
    if change == "missing":
        target.unlink()
    elif change == "changed":
        target.write_text("raise RuntimeError\n")
    else:
        target.unlink()
        target.symlink_to(root / "skills" / script)
    calls = []
    monkeypatch.setattr(runtime.os, "execv", lambda *a: calls.append(a))
    assert runtime.launcher_main(pointer, ["machine", "review"]) == 2
    assert not calls


@pytest.mark.parametrize("override", [False, True])
def test_selected_system_state_migration_roots_and_actual_dirty_registry(
    tmp_path, monkeypatch, override
):
    import hashlib
    import subprocess
    from types import SimpleNamespace
    import maintenance_cli

    state = SystemState(tmp_path / "selected-home")
    board = state.synthesis_dir / "coordination" / "active-sessions.md"
    if override:
        board = tmp_path / "configured-board" / "active-sessions.md"
        monkeypatch.setenv("SYNTHESIS_COORDINATION_BOARD", str(board))
    else:
        monkeypatch.delenv("SYNTHESIS_COORDINATION_BOARD", raising=False)
    board.parent.mkdir(parents=True)
    board.write_text("# Board\n")
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args):
        return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)

    git("init", "-b", "main")
    git("config", "user.name", "Synthetic Fixture")
    git("config", "user.email", "fixture@example.invalid")
    hooks = tmp_path / "hooks"
    hooks.mkdir()
    git("config", "core.hooksPath", str(hooks))
    project = repo / "projects" / "alpha"
    (project / "sessions").mkdir(parents=True)
    (project / "CONTEXT.md").write_text("# Context\n")
    (project / "REFERENCE.md").write_text("# Reference\n")
    (project / "sessions/2026-01.md").write_text("# Session\n")
    index = repo / "projects/index.yaml"
    index.write_text("- id: alpha\n  status: active\n")
    git("add", "projects")
    git("commit", "-m", "Synthetic fixture")
    context = project / "CONTEXT.md"
    context.write_text("# Retained dirty source\n")
    pending = state.synthesis_dir / "repo-guard" / "pending"
    pending.mkdir(parents=True)
    (pending / "fixture.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "session_id": "fixture",
                "paths": [str(context)],
                "path_hashes": {
                    str(context): hashlib.sha256(context.read_bytes()).hexdigest()
                },
                "path_kinds": {str(context): "file"},
            }
        )
    )
    args = SimpleNamespace(
        command="project-migrate",
        migration_command="plan",
        all_declared=False,
        select=["alpha"],
        index=index,
        target_format=2,
    )
    preview = maintenance_cli.dispatch(args, state, None)
    assert preview["projects"][0]["path"] == str(project)
    assert preview["recovery_roots"] == {
        "repo_guard_root": str(state.synthesis_dir / "repo-guard"),
        "checkpoint_receipt_root": str(state.synthesis_dir / "project-state/receipts"),
        "coordination_board": str(board),
    }
    assert not (project / ".synthesis-project.yaml").exists()

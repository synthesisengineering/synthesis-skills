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

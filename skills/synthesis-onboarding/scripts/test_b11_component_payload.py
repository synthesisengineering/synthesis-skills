"""Component-scoped runtime ownership and real installation modes."""
import json
from pathlib import Path
import pytest
import onboard
import runtime_payload as runtime
import test_runtime_payload as fixtures
from system_contract import ContractError

installation = fixtures.installation
NAMES = ("native_git.py", "claim_scope.py", "board_grammar.py", "coordination_schema.py")


def selected(data, components):
    current, old, descriptor, home, state, receipts, _ = data
    return runtime.plan(current, home, state, components, receipts.data,
                        legacy_releases=[(old, descriptor)])


@pytest.mark.parametrize("components", [["message-guard"], ["git-hooks"], ["git-hooks", "message-guard"]])
def test_selected_component_anchors_admit_only_own_dependencies(installation, components):
    home = installation[3]
    if "git-hooks" in components:
        (home / ".synthesis/git-hooks/claim_scope.py").unlink()
    result = selected(installation, components)
    assert {entry.component for entry in result.entries} == set(components)
    runtime.apply(result, installation[5])
    assert all(row["status"] == "current" for row in runtime.verify(result))
    if "message-guard" in components:
        assert all((home / ".synthesis/message-guard" / name).stat().st_mode & 0o777 == 0o755 for name in NAMES)


@pytest.mark.parametrize("kind", ["missing", "tampered"])
def test_foreign_component_never_substitutes_for_message_anchor(installation, kind):
    target = installation[3] / ".synthesis/message-guard/message_guard.py"
    if kind == "missing":
        target.unlink()
    else:
        target.write_text("foreign edited engine\n")
    before = fixtures.snapshot(installation[3])
    with pytest.raises(ContractError):
        selected(installation, ["message-guard", "git-hooks"])
    assert fixtures.snapshot(installation[3]) == before


def personal_phase(tmp_path, monkeypatch, foreign=False):
    home = tmp_path / "home"
    message = home / ".synthesis/message-guard"
    message.mkdir(parents=True)
    (message / "patterns.json").write_text(json.dumps({"message_capabilities": []}))
    if foreign:
        p = message / NAMES[0]
        p.write_text("foreign retained bytes\n")
        p.chmod(0o600)
    monkeypatch.setattr(onboard, "HOME", home)
    monkeypatch.setattr(onboard, "WORKSPACES_ROOT", home / "workspaces")
    monkeypatch.setattr(onboard, "source_root", lambda: Path(__file__).resolve().parents[3])
    # Only unrelated policy readiness/choice builders are synthetic. The real
    # phase, ensure_file, Receipts, source bytes, post-write checks and modes run.
    monkeypatch.setattr(onboard, "message_guard_activation_preflight", lambda *a, **k: None)
    for name in ("build_personal_policy", "build_chief_preferences", "build_capture_config"):
        monkeypatch.setattr(onboard, name, lambda *a, **k: {})
    report = onboard.Report(as_json=True)
    receipts = onboard.Receipts(home / "receipts.json")
    onboard.phase_personal_policy(report, receipts, {"workspace": "fixture"}, [], False)
    return message, report


def test_real_personal_phase_installs_exact_runtime_modes(tmp_path, monkeypatch):
    message, report = personal_phase(tmp_path, monkeypatch)
    assert not [step for step in report.steps if step["status"] == onboard.ERROR]
    source = Path(__file__).resolve().parents[3] / "skills/synthesis-project-management/scripts"
    for name in NAMES:
        target = message / name
        assert target.read_bytes() == (source / name).read_bytes()
        assert target.stat().st_mode & 0o777 == 0o755


def test_real_personal_phase_preserves_foreign_dependency_bytes_and_mode(tmp_path, monkeypatch):
    message, report = personal_phase(tmp_path, monkeypatch, foreign=True)
    assert any(step["status"] == onboard.ERROR for step in report.steps)
    assert (message / NAMES[0]).read_text() == "foreign retained bytes\n"
    assert (message / NAMES[0]).stat().st_mode & 0o777 == 0o600
    assert not (message / "message_guard.py").exists()

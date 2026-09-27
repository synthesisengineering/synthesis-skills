from pathlib import Path
import sys
import json

P = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(P / "skills/synthesis-onboarding/scripts"))
import onboard  # noqa: E402 - register sibling script path first
import whole_system  # noqa: E402 - register sibling script path first


def test_personal_policy_stage_refuses_unmigrated_existing_engine_before_writes(
    tmp_path, monkeypatch
):
    home = tmp_path / "home"
    home.mkdir()
    state = home / ".synthesis/message-guard"
    state.mkdir(parents=True)
    config = state / "patterns.json"
    config.write_text(
        (P / "skills/synthesis-message-guard/patterns.example.json").read_text()
    )
    engine = state / "message_guard.py"
    engine.write_text("# retained old engine\n")
    monkeypatch.setattr(onboard, "HOME", home)
    monkeypatch.setattr(onboard, "STATE_DIR", home / ".synthesis/onboarding")
    monkeypatch.setattr(onboard, "WORKSPACES_ROOT", home / "workspaces")
    monkeypatch.setattr(onboard, "source_root", lambda: P)
    receipts = onboard.Receipts(home / ".synthesis/onboarding/receipts.json")
    receipts.record_file(engine, engine.read_text(), "hooks-gates")
    report = onboard.Report()
    answers = whole_system.validate_answers({"workspace": "fixture"}, True)
    before = engine.read_bytes()
    onboard.phase_personal_policy(report, receipts, answers, [], False)
    assert engine.read_bytes() == before
    assert not (home / ".synthesis/personal-policy/profile.json").exists()


def test_existing_ready_owner_policy_and_pending_bytes_are_preserved(
    tmp_path, monkeypatch
):
    import importlib.util

    home = tmp_path / "home"
    home.mkdir()
    state = home / ".synthesis/message-guard"
    state.mkdir(parents=True)
    config = state / "patterns.json"
    cfg = json.loads(
        (P / "skills/synthesis-message-guard/patterns.example.json").read_text()
    )
    cfg["message_capabilities"] = [
        {"tool_names": ["fixture.send"], "channel": "human-text"}
    ]
    cfg["owner_extension"] = {"preserve": "exact bytes"}
    config.write_text(json.dumps(cfg, indent=3) + "\n")
    (state / "ledger").mkdir()
    pending = state / "ledger/pending.json"
    pending.write_text("synthetic preserved old evidence")
    engine = state / "message_guard.py"
    engine.write_text("# old owned fixture engine\n")
    monkeypatch.setenv("MESSAGE_GUARD_CONFIG", str(config))
    monkeypatch.setenv("MESSAGE_GUARD_STATE_DIR", str(state))
    monkeypatch.setattr(onboard, "HOME", home)
    monkeypatch.setattr(onboard, "STATE_DIR", home / ".synthesis/onboarding")
    monkeypatch.setattr(onboard, "WORKSPACES_ROOT", home / "workspaces")
    monkeypatch.setattr(onboard, "source_root", lambda: P)
    spec = importlib.util.spec_from_file_location(
        "review_owner_guard",
        P / "skills/synthesis-message-guard/scripts/message_guard.py",
    )
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    record = guard.migration_preflight(plan=True)["required_record"]
    record["owner_review"] = {
        "source": "synthetic tested fixture owner",
        "reviewed_at": "2026-09-25T00:00:00Z",
    }
    (state / "engine-migration.json").write_text(json.dumps(record))
    receipts = onboard.Receipts(home / ".synthesis/onboarding/receipts.json")
    receipts.record_file(engine, engine.read_text(), "hooks-gates")
    receipts.record_file(config, config.read_text(), "personal-policy")
    report = onboard.Report()
    answers = whole_system.validate_answers({"workspace": "fixture"}, True)
    before = (config.read_bytes(), pending.read_bytes())
    onboard.phase_personal_policy(report, receipts, answers, [], False)
    assert (config.read_bytes(), pending.read_bytes()) == before
    assert (
        engine.read_bytes()
        == (P / "skills/synthesis-message-guard/scripts/message_guard.py").read_bytes()
    )

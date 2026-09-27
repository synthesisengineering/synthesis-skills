"""Actual owner/bootstrap consumer controls; no providers or live home."""

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

P = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(P / "skills/synthesis-onboarding/scripts"))
import onboard  # noqa: E402 - load explicit sibling owner
import whole_system  # noqa: E402 - load explicit sibling owner

CAPABILITIES = [
    {
        "tool_names": [
            "mcp__workspace__send_gmail_message",
            "mcp__workspace__draft_gmail_message",
        ],
        "channel": "email",
        "body_field": "body",
        "format_field": "body_format",
        "html_value": "html",
        "plain_value": "plain",
    },
    {
        "tool_names": ["mcp__apple__send_email"],
        "channel": "email",
        "body_field": "body",
        "fixed_format": "plain",
    },
    {"tool_names": ["fixture.send"], "channel": "human-text"},
]


def reviewed_answers():
    answers = whole_system.validate_answers(
        {
            "workspace": "fixture",
            "message_guard": {
                "capabilities": copy.deepcopy(CAPABILITIES),
                "owner_review": {
                    "source": "synthetic fixture schema review",
                    "reviewed_at": "2026-09-25T00:00:00Z",
                },
            },
        },
        True,
    )
    config = whole_system.build_message_guard_config(P, answers)
    answers["message_guard"]["reviewed_configuration_sha256"] = hashlib.sha256(
        json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return answers


@pytest.fixture
def box(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(onboard, "HOME", home)
    monkeypatch.setattr(onboard, "STATE_DIR", home / ".synthesis/onboarding")
    monkeypatch.setattr(onboard, "WORKSPACES_ROOT", home / "workspaces")
    monkeypatch.setattr(onboard, "source_root", lambda: P)
    return home, onboard.Receipts(home / ".synthesis/onboarding/receipts.json")


def phase(box, answers, dry=False):
    home, receipts = box
    report = onboard.Report()
    onboard.phase_personal_policy(report, receipts, answers, ["claude", "codex"], dry)
    return home, report


def test_fresh_ready_and_idempotent_repeat(box):
    answers = reviewed_answers()
    home, report = phase(box, answers)
    assert report.exit_code() == 0
    state = home / ".synthesis/message-guard"
    config = (state / "patterns.json").read_bytes()
    record = (state / "engine-migration.json").read_bytes()
    plan = onboard.message_configuration_check(
        {}, state=state, mode="--migration-preflight"
    )
    assert plan["status"] == "READY_FOR_OWNER_ACTIVATION"
    assert len(plan["unsupported_transports"]) == 1
    assert plan["message_authority_granted"] is False
    assert plan["provider_drafts"] == "NOT_INSPECTED"
    assert json.loads(config)["email_policy"]["default_format"] == "html"
    for file in [home / ".claude/settings.json", home / ".codex/hooks.json"]:
        hooks = json.loads(file.read_text())["hooks"]["PreToolUse"]
        import re

        assert any(re.search(h["matcher"], "fixture.send") for h in hooks)
    assert onboard._personal_policy_probe()[0]
    _, repeated = phase(box, answers)
    assert repeated.exit_code() == 0
    assert (state / "patterns.json").read_bytes() == config
    assert (state / "engine-migration.json").read_bytes() == record
    desired = {
        "profile": "full",
        "personal_workspace": "fixture",
        "personal_configuration": onboard.personal_configuration_from_answers(answers),
    }
    assert (
        onboard.reconcile_answers(desired, None)["message_guard"]
        == answers["message_guard"]
    )


@pytest.mark.parametrize(
    "change",
    [
        "absent",
        "stale",
        "future",
        "unattributed",
        "malformed",
        "ambiguous",
        "exempt",
        "plain-policy-drift",
    ],
)
def test_invalid_inputs_never_activate(box, change):
    answers = reviewed_answers()
    if change == "absent":
        answers.pop("message_guard")
    if change == "stale":
        answers["avoid_phrases"] = ["changed after review"]
    if change == "future":
        answers["message_guard"]["owner_review"]["reviewed_at"] = "2999-01-01T00:00:00Z"
    if change == "unattributed":
        answers["message_guard"]["owner_review"]["source"] = ""
    if change == "malformed":
        answers["message_guard"]["capabilities"][0].pop("body_field")
    if change == "ambiguous":
        answers["message_guard"]["capabilities"].append(copy.deepcopy(CAPABILITIES[0]))
    if change == "exempt":
        answers["message_guard"]["capabilities"][2]["tool_names"] = [
            "mcp__session__send_message"
        ]
    if change == "plain-policy-drift":
        answers["message_guard"]["email_policy"] = {
            "default_format": "plain",
            "allow_intra_paragraph_breaks": False,
        }
    home, report = phase(box, answers)
    assert report.exit_code() != 0
    assert not (home / ".synthesis/message-guard/message_guard.py").exists()
    assert not (home / ".claude/settings.json").exists()
    assert not (home / ".synthesis/personal-policy/profile.json").exists()


def test_read_only_plan_cannot_initialize_home(tmp_path):
    home = tmp_path / "absent-home"
    answers = tmp_path / "answers.json"
    raw = reviewed_answers()
    raw["message_guard"].pop("reviewed_configuration_sha256")
    answers.write_text(json.dumps(raw))
    env = dict(os.environ, HOME=str(home), SYNTHESIS_ONBOARD_STATE=str(home / "state"))
    p = subprocess.run(
        [
            sys.executable,
            "-B",
            str(P / "skills/synthesis-onboarding/scripts/onboard.py"),
            "message-guard-plan",
            "--answers",
            str(answers),
        ],
        env=env,
        text=True,
        capture_output=True,
        timeout=10,
    )
    assert p.returncode == 0, p.stderr
    result = json.loads(p.stdout)
    assert result["status"] == "READY_FOR_CONFIGURATION_REVIEW"
    assert result["unsupported_transports"] == ["mcp__apple__send_email"]
    assert not home.exists()


@pytest.mark.parametrize("kind", ["engine", "pending", "symlink", "stale-config"])
def test_retained_or_aliased_state_is_not_adopted(box, tmp_path, kind):
    home, _ = box
    state = home / ".synthesis/message-guard"
    state.parent.mkdir(parents=True)
    if kind == "symlink":
        outside = tmp_path / "outside"
        outside.mkdir()
        state.symlink_to(outside, target_is_directory=True)
    else:
        state.mkdir()
        path = (
            state
            / {
                "engine": "message_guard.py",
                "pending": "ledger.json",
                "stale-config": "patterns.json",
            }[kind]
        )
        path.write_text("retained owner bytes")
    _, report = phase(box, reviewed_answers())
    assert report.exit_code() != 0
    assert not (home / ".claude/settings.json").exists()
    if kind != "symlink":
        assert path.read_text() == "retained owner bytes"


def test_dry_run_never_stages_guard(box):
    home, report = phase(box, reviewed_answers(), True)
    assert report.exit_code() == 0
    assert not (home / ".synthesis").exists()


def test_fresh_engine_enforces_actual_html_payload_and_pending_ledger(box):
    import importlib.util
    from datetime import datetime, timezone

    home, report = phase(box, reviewed_answers())
    assert report.exit_code() == 0
    state = home / ".synthesis/message-guard"
    engine = state / "message_guard.py"
    spec = importlib.util.spec_from_file_location("fresh_installed_fixture", engine)
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    tool = "mcp__workspace__draft_gmail_message"
    body = {
        "to": "reader@example.invalid",
        "body": "<p>Words.</p>",
        "body_format": "html",
    }
    digest = guard.message_digest(tool, body)
    ledger = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "message_sha256": digest,
        "is_reply": False,
        "no_factual_claims": True,
        "voice_rules_pass": True,
        "invented_precision_scan": True,
        "recipient_address_check": True,
    }
    env = {k: v for k, v in os.environ.items() if not k.startswith("MESSAGE_GUARD_")}
    env.update(
        MESSAGE_GUARD_CONFIG=str(state / "patterns.json"),
        MESSAGE_GUARD_STATE_DIR=str(state),
    )

    def invoke(name, data):
        return subprocess.run(
            [sys.executable, "-I", "-B", str(engine), "--gate"],
            input=json.dumps({"tool_name": name, "tool_input": data}),
            env=env,
            text=True,
            capture_output=True,
            timeout=5,
        )

    assert invoke(tool, body).returncode == 2
    (state / "ledger").mkdir(mode=0o700)
    pending = state / "ledger" / (digest + ".json")
    pending.write_text(json.dumps(ledger))
    pending.chmod(0o600)
    altered = invoke(tool, dict(body, to="changed@example.invalid"))
    assert altered.returncode == 2 and pending.exists()
    plain = invoke(
        "mcp__apple__send_email", {"to": "reader@example.invalid", "body": "Words."}
    )
    assert plain.returncode == 2 and "format" in plain.stderr
    accepted = invoke(tool, body)
    assert accepted.returncode == 0, accepted.stderr
    assert not pending.exists()
    assert invoke(tool, body).returncode == 2
    assert onboard._personal_policy_probe()[
        0
    ]  # New legitimate log is not configuration drift.


def test_interrupted_bootstrap_preserves_evidence_and_never_wires(box, monkeypatch):
    create = onboard.create_guard_input

    def interrupt(path, content):
        if path.name == "engine-migration.json":
            raise OSError("synthetic interruption after config fsync")
        return create(path, content)

    monkeypatch.setattr(onboard, "create_guard_input", interrupt)
    home, report = phase(box, reviewed_answers())
    assert report.exit_code() != 0
    config = home / ".synthesis/message-guard/patterns.json"
    frozen = config.read_bytes()
    assert not (home / ".claude/settings.json").exists()
    monkeypatch.setattr(onboard, "create_guard_input", create)
    _, retry = phase(box, reviewed_answers())
    assert retry.exit_code() != 0
    assert config.read_bytes() == frozen
    assert not (home / ".synthesis/message-guard/message_guard.py").exists()


def test_missing_inputs_preserve_existing_hooks(box):
    home, _ = box
    hooks = home / ".claude/settings.json"
    hooks.parent.mkdir()
    hooks.write_text(
        '{"hooks":{"PreToolUse":[{"matcher":".*","hooks":[{"command":"python3 retained/message_guard.py --gate"}]}]}}'
    )
    frozen = hooks.read_bytes()
    _, report = phase(
        box, whole_system.validate_answers({"workspace": "fixture"}, True)
    )
    assert report.exit_code() != 0 and hooks.read_bytes() == frozen
    _, ready_input = phase(box, reviewed_answers())
    assert ready_input.exit_code() != 0 and hooks.read_bytes() == frozen
    assert not (home / ".synthesis/message-guard").exists()


def test_unconfigured_template_fails_actual_doctor(tmp_path):
    cfg = tmp_path / "patterns.json"
    cfg.write_bytes(
        (P / "skills/synthesis-message-guard/patterns.example.json").read_bytes()
    )
    env = {k: v for k, v in os.environ.items() if not k.startswith("MESSAGE_GUARD_")}
    env.update(
        HOME=str(tmp_path),
        MESSAGE_GUARD_CONFIG=str(cfg),
        MESSAGE_GUARD_STATE_DIR=str(tmp_path / "state"),
    )
    p = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            str(P / "skills/synthesis-message-guard/scripts/message_guard.py"),
            "--doctor",
        ],
        env=env,
        text=True,
        capture_output=True,
        timeout=10,
    )
    assert (
        p.returncode == 2
        and "explicit owner transport capabilities required" in p.stdout
    )


@pytest.mark.parametrize(
    "fault", ["short-write", "zero-write", "fsync", "parent-fsync"]
)
def test_exclusive_bootstrap_write_faults_preserve_evidence(
    tmp_path, monkeypatch, fault
):
    path = tmp_path / "record.json"
    write = os.write
    fsync = os.fsync
    count = 0

    def bounded_write(fd, body):
        if fault == "zero-write":
            return 0
        return write(fd, body[:3] if fault == "short-write" else body)

    def fault_fsync(fd):
        nonlocal count
        count += 1
        if (fault == "fsync" and count == 1) or (
            fault == "parent-fsync" and count == 2
        ):
            raise OSError("synthetic durability fault")
        return fsync(fd)

    monkeypatch.setattr(os, "write", bounded_write)
    monkeypatch.setattr(os, "fsync", fault_fsync)
    if fault == "short-write":
        onboard.create_guard_input(path, '{"complete":true}\n')
        assert path.read_text() == '{"complete":true}\n'
        assert path.stat().st_mode & 0o777 == 0o600
    else:
        with pytest.raises(OSError):
            onboard.create_guard_input(path, "retained partial effect")
        assert path.exists()
        with pytest.raises(FileExistsError):
            onboard.create_guard_input(path, "must not overwrite")


@pytest.mark.parametrize("kind", ["fifo", "oversize", "duplicate"])
def test_answers_input_is_finite_and_unambiguous(tmp_path, kind):
    path = tmp_path / "answers"
    if kind == "fifo":
        os.mkfifo(path)
    elif kind == "oversize":
        path.write_bytes(b" " * (1024 * 1024 + 1))
    else:
        path.write_text('{"message_guard":{},"message_guard":null}')
    with pytest.raises(ValueError):
        whole_system.load_answers(path)


def test_doctor_does_not_replace_retained_probe_target(box):
    home, report = phase(box, reviewed_answers())
    assert report.exit_code() == 0
    state = home / ".synthesis/message-guard"
    retained = home / "retained-owner.txt"
    retained.write_text("must survive doctor")
    (state / ".doctor-probe").symlink_to(retained)
    env = {k: v for k, v in os.environ.items() if not k.startswith("MESSAGE_GUARD_")}
    env.update(
        HOME=str(home),
        MESSAGE_GUARD_CONFIG=str(state / "patterns.json"),
        MESSAGE_GUARD_STATE_DIR=str(state),
        MESSAGE_GUARD_CLAUDE_SETTINGS=str(home / ".claude/settings.json"),
        MESSAGE_GUARD_CODEX_HOOKS=str(home / ".codex/hooks.json"),
    )
    subprocess.run(
        [sys.executable, "-I", "-B", str(state / "message_guard.py"), "--doctor"],
        env=env,
        text=True,
        capture_output=True,
        timeout=10,
    )
    assert retained.read_text() == "must survive doctor"
    assert (state / ".doctor-probe").is_symlink()


def test_repeat_preserves_broader_owned_hook_coverage(box):
    home, report = phase(box, reviewed_answers())
    assert report.exit_code() == 0
    path = home / ".claude/settings.json"
    data = json.loads(path.read_text())
    data["hooks"]["PreToolUse"][0]["matcher"] = ".*"
    path.write_text(json.dumps(data))
    box[1].data["managed_json_entries"][str(path)] = onboard.sha256_text(
        whole_system.dump_json(data["hooks"]["PreToolUse"][0])
    )
    before = path.read_bytes()
    _, repeated = phase(box, reviewed_answers())
    assert repeated.exit_code() == 0
    assert path.read_bytes() == before

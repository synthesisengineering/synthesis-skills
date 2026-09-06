"""Pin protective-doctor execution, not merely entrypoint presence."""

import json
import os
import shlex
import subprocess
import sys

import pytest

import onboard


def fixture_runtime(tmp_path, monkeypatch, doctor_body):
    home = tmp_path / "home"
    source = tmp_path / "source"
    for skill, name in (
        ("synthesis-context-lifecycle", "context_doctor.py"),
        ("synthesis-agent-conformance", "conformance.py"),
        ("synthesis-git-hooks", "_load_config.py"),
        ("synthesis-message-guard", "message_guard.py"),
    ):
        entry = source / "skills" / skill / "scripts" / name
        entry.parent.mkdir(parents=True)
        entry.write_text("# available entrypoint\n")
    installed = home / ".synthesis" / "git-hooks" / "_load_config.py"
    installed.parent.mkdir(parents=True)
    installed.write_text(doctor_body)
    monkeypatch.setattr(onboard, "HOME", home)
    state = home / ".local/state/synthesis"
    monkeypatch.setattr(onboard, "STATE_DIR", state)
    receipts_class = onboard.Receipts
    monkeypatch.setattr(onboard, "Receipts", lambda path=None: receipts_class(
        state / "receipts.json" if path is None else path))
    monkeypatch.setattr(onboard, "source_root", lambda: source)
    original_run = onboard.run

    def isolated_run(command, *args, **kwargs):
        if command[:4] == ["git", "config", "--global", "--get"]:
            return 0, str(installed.parent) + "\n", ""
        return original_run(command, *args, **kwargs)

    monkeypatch.setattr(onboard, "run", isolated_run)
    return home, installed


def test_present_doctor_that_exits_unhealthy_is_not_healthy(tmp_path, monkeypatch):
    fixture_runtime(tmp_path, monkeypatch,
                    "print('UNHEALTHY: dependency drift')\nraise SystemExit(1)\n")
    state, detail = onboard._doctors_probe()
    assert state is False, detail
    assert "git-hooks" in detail


def test_success_exit_without_health_result_is_not_healthy(tmp_path, monkeypatch):
    fixture_runtime(tmp_path, monkeypatch, "print('no check ran')\n")
    state, detail = onboard._doctors_probe()
    assert state is False, detail


def test_doctor_executes_real_installed_process(tmp_path, monkeypatch):
    home, installed = fixture_runtime(tmp_path, monkeypatch,
        "from pathlib import Path\n"
        "Path(__file__).with_name('executed').write_text('yes')\n"
        "print('HEALTHY: verified')\n")
    state, detail = onboard._doctors_probe()
    assert state is True, detail
    assert installed.with_name("executed").read_text() == "yes"


def test_doctor_timeout_refuses_health(tmp_path, monkeypatch):
    fixture_runtime(tmp_path, monkeypatch, "import time\ntime.sleep(30)\n")
    original_run = onboard.run

    def bounded_run(command, *args, **kwargs):
        if "--doctor" in command:
            kwargs["timeout"] = 0.05
        return original_run(command, *args, **kwargs)

    monkeypatch.setattr(onboard, "run", bounded_run)
    state, detail = onboard._doctors_probe()
    assert state is False, detail
    assert "timeout" in detail.lower()


def test_independently_wired_runtime_survives_declined_setup_layers(tmp_path, monkeypatch):
    fixture_runtime(tmp_path, monkeypatch, "print('HEALTHY: verified')\n")
    receipts = onboard.Receipts(tmp_path / "receipts.json")
    desired = {"layers": {"runtime-engines": "declined", "hooks-gates": "declined"}}
    assert "git-hooks" in onboard.runtime_components(receipts, desired)
    assert desired["layers"]["runtime-engines"] == "declined"


def test_unconfigured_stray_runtime_file_does_not_enroll(tmp_path, monkeypatch):
    fixture_runtime(tmp_path, monkeypatch, "print('HEALTHY: verified')\n")
    monkeypatch.setattr(onboard, "run", lambda *a, **k: (1, "", ""))
    receipts = onboard.Receipts(tmp_path / "receipts.json")
    assert onboard.runtime_components(receipts, {"layers": {}}) == set()


@pytest.mark.parametrize("spelling", [
    "plain-tilde", "quoted-tilde", "escaped-tilde", "python-B", "python-double-dash",
])
def test_hook_selection_matches_actual_shell_execution(tmp_path, monkeypatch, spelling):
    home = tmp_path / "home"
    target = home / ".synthesis/message-guard/message_guard.py"
    target.parent.mkdir(parents=True)
    marker = home / "executed"
    target.write_text("from pathlib import Path\nPath(" + repr(str(marker)) + ").write_text('executed')\n")
    monkeypatch.setattr(onboard, "HOME", home)
    python = shlex.quote(sys.executable)
    commands = {
        "plain-tilde": python + " ~/.synthesis/message-guard/message_guard.py --gate",
        "quoted-tilde": python + " '~/.synthesis/message-guard/message_guard.py' --gate",
        "escaped-tilde": python + r" \~/.synthesis/message-guard/message_guard.py --gate",
        "python-B": python + " -B " + shlex.quote(str(target)) + " --gate",
        "python-double-dash": python + " -- " + shlex.quote(str(target)) + " --gate",
    }
    command = commands[spelling]
    hook = home / "hooks.json"
    hook.write_text(json.dumps({"hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": command}]}]}}))
    environment = {**os.environ, "HOME": str(home), "PYTHONDONTWRITEBYTECODE": "1"}
    for name in ("BASH_ENV", "ENV"):
        environment.pop(name, None)
    completed = subprocess.run(["bash", "--noprofile", "--norc", "-c", command],
                               env=environment, capture_output=True)
    detected = onboard._stable_runtime_hook(hook, "PreToolUse", target)
    assert detected == marker.exists(), (
        spelling, "selected=" + str(detected), "executed=" + str(marker.exists()), completed.returncode)


def test_native_stable_wrapper_is_not_selected_as_direct_runtime(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(onboard, "HOME", home)
    hook = home / "hooks.json"
    command = "python3 ~/.synthesis/agent-control/scripts/run_public_skill.py synthesis-message-guard/scripts/message_guard.py -- --gate"
    hook.write_text(json.dumps({"hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": command}]}]}}))
    assert not onboard._stable_runtime_hook(hook, "PreToolUse", home / ".synthesis/message-guard/message_guard.py")

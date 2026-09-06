"""Pin protective-doctor execution, not merely entrypoint presence."""

import json
import subprocess
import sys
from pathlib import Path

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

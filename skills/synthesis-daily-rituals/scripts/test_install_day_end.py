from __future__ import annotations

import hashlib
import json
import os
import plistlib
import stat
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPT_DIR = Path(__file__).resolve().parent
INSTALLER = SCRIPT_DIR / "install_day_end.py"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_installer(home: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment["HOME"] = str(home)
    return subprocess.run(
        [sys.executable, str(INSTALLER), "--no-launchctl", *arguments],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )


def fake_cli(path: Path, name: str) -> None:
    executable = path / name
    executable.write_text(
        "#!/bin/sh\nprintf '%s\\n' \"$0|$*\" > \"$DAY_END_TEST_RECORD\"\n",
        encoding="utf-8",
    )
    executable.chmod(0o755)


def test_installer_uses_stable_runtime_and_preserves_source(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    source_digests = {
        name: digest(SCRIPT_DIR / name)
        for name in ("day-end", "day-end-nudge.sh", "ritual_state.py")
    }

    completed = run_installer(home)
    assert completed.returncode == 0, completed.stderr

    runtime = home / ".synthesis" / "day-end"
    assert (runtime / "agent-cli").read_text() == "auto\n"
    assert (home / ".local" / "bin" / "day-end").resolve() == runtime / "bin" / "day-end"

    plist_path = home / "Library" / "LaunchAgents" / "com.synthesis.day-end-nudge.plist"
    with plist_path.open("rb") as handle:
        plist = plistlib.load(handle)
    assert plist["ProgramArguments"] == [str(runtime / "bin" / "day-end-nudge.sh")]
    template = plistlib.loads(
        (SCRIPT_DIR / "com.synthesis.day-end-nudge.plist").read_bytes()
    )
    template["ProgramArguments"] = plist["ProgramArguments"]
    assert plist == template
    assert ".claude" not in plist_path.read_text(encoding="utf-8")
    assert ".codex" not in plist_path.read_text(encoding="utf-8")

    for name, before in source_digests.items():
        assert digest(SCRIPT_DIR / name) == before
        installed = runtime / "bin" / name
        assert installed.is_file(), f"missing installed dependency: {name}"
        assert digest(installed) == before
        assert stat.S_IMODE(installed.stat().st_mode) == 0o755


def test_reinstall_preserves_agent_choice_and_refreshes_state_helper(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    assert run_installer(home, "--agent", "claude").returncode == 0
    runtime = home / ".synthesis" / "day-end"
    helper = runtime / "bin" / "ritual_state.py"
    helper.write_text("older release fixture\n", encoding="utf-8")
    helper.chmod(0o600)
    plist_path = home / "Library" / "LaunchAgents" / "com.synthesis.day-end-nudge.plist"
    plist_before = plist_path.read_bytes()

    completed = run_installer(home)
    assert completed.returncode == 0, completed.stderr
    assert (runtime / "agent-cli").read_text() == "claude\n"
    assert plist_path.read_bytes() == plist_before
    assert helper.read_bytes() == (SCRIPT_DIR / "ritual_state.py").read_bytes()
    assert stat.S_IMODE(helper.stat().st_mode) == 0o755


def file_snapshot(root: Path) -> dict[str, tuple[bytes, int, int]]:
    return {
        str(path.relative_to(root)): (
            path.read_bytes(), path.stat().st_mtime_ns, stat.S_IMODE(path.stat().st_mode)
        )
        for path in root.rglob("*")
        if path.is_file()
    }


def isolated_environment(home: Path, state: Path) -> dict[str, str]:
    environment = dict(os.environ)
    for name in ("BASH_ENV", "ENV"):
        environment.pop(name, None)
    environment.update(
        HOME=str(home),
        RITUAL_STATE_DIR=str(state),
        PYTHONDONTWRITEBYTECODE="1",
        PATH=str(Path(sys.executable).parent) + os.pathsep + os.environ["PATH"],
    )
    return environment


def ritual_state_fixture(state: Path, *, closed: bool) -> None:
    state.mkdir()
    records = [
        {"workspace": workspace, "direction": "day-start", "date": "2026-09-07"}
        for workspace in ("first", "second")
    ]
    records.append({"workspace": "first", "direction": "day-end", "date": "2026-09-07"})
    if closed:
        records.append({"workspace": "second", "direction": "day-end", "date": "2026-09-07"})
    (state / "history.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8"
    )
    (state / "config.json").write_text(
        json.dumps({"workspaces": {
            workspace: {"streak": "expected-days"} for workspace in ("first", "second")
        }}), encoding="utf-8"
    )


@pytest.mark.parametrize("populated", [False, True], ids=["absent-state", "existing-state"])
def test_installed_ritual_state_query_is_read_only(tmp_path: Path, populated: bool) -> None:
    home = tmp_path / "home"
    home.mkdir()
    assert run_installer(home).returncode == 0
    state = tmp_path / "ritual-state"
    if populated:
        ritual_state_fixture(state, closed=True)
    helper = home / ".synthesis" / "day-end" / "bin" / "ritual_state.py"
    assert helper.is_file(), "installed nudge must have its state-query dependency"
    before = file_snapshot(tmp_path)

    completed = subprocess.run(
        [str(helper), "query", "summary", "--json", "--today", "2026-09-07"],
        env=isolated_environment(home, state), capture_output=True, text=True, check=False,
    )
    assert completed.returncode == 0, completed.stderr
    summary = json.loads(completed.stdout)
    assert summary["open_workdays"] == []
    assert set(summary["workspaces"]) == ({"first", "second"} if populated else set())
    assert file_snapshot(tmp_path) == before
    assert state.exists() is populated


@pytest.mark.parametrize(
    ("condition", "expected_notifications"),
    [("all-closed", 0), ("one-open", 1), ("missing-helper", 1), ("invalid-state", 1)],
)
def test_installed_nudge_quiet_and_notification_controls(
    tmp_path: Path, condition: str, expected_notifications: int
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    assert run_installer(home).returncode == 0
    runtime = home / ".synthesis" / "day-end" / "bin"
    state = tmp_path / "ritual-state"
    ritual_state_fixture(state, closed=condition != "one-open")
    if condition == "missing-helper":
        (runtime / "ritual_state.py").unlink(missing_ok=True)
    elif condition == "invalid-state":
        (state / "config.json").write_text("not JSON\n", encoding="utf-8")
    record = tmp_path / "notification-record"
    environment = isolated_environment(home, state)
    environment["DAY_END_TEST_RECORD"] = str(record)
    before = file_snapshot(state)
    # Source the unchanged installed script in a shell whose absolute notification
    # command is a function. Prove the interception before running any nudge code.
    wrapper = """
set -euo pipefail
function /usr/bin/osascript { printf '%s\\n' "$*" >> "$DAY_END_TEST_RECORD"; }
[[ "$(type -t /usr/bin/osascript)" == function ]] || exit 96
/usr/bin/osascript notification-guard-control
function date { printf '2026-09-07\\n'; }
source "$1"
"""
    completed = subprocess.run(
        ["bash", "--noprofile", "--norc", "-c", wrapper, "nudge-test", str(runtime / "day-end-nudge.sh")],
        env=environment, capture_output=True, text=True, check=False,
    )
    assert completed.returncode == 0, completed.stderr
    notifications = record.read_text(encoding="utf-8").splitlines()
    assert notifications[0] == "notification-guard-control"
    assert notifications[1:] == [
        '-e display notification "Evening ritual window — details in your synthesis console" with title "Synthesis"'
    ] * expected_notifications
    assert file_snapshot(state) == before


def test_launcher_auto_prefers_codex_and_honors_selection(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    assert run_installer(home).returncode == 0

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_cli(fake_bin, "codex")
    fake_cli(fake_bin, "claude")
    record = tmp_path / "record"
    environment = dict(os.environ)
    environment.update(
        {
            "HOME": str(home),
            "PATH": str(fake_bin) + os.pathsep + os.environ["PATH"],
            "DAY_END_TEST_RECORD": str(record),
        }
    )
    launcher = home / ".local" / "bin" / "day-end"

    completed = subprocess.run(
        [str(launcher), "-q"], env=environment, capture_output=True, text=True, check=False
    )
    assert completed.returncode == 0, completed.stderr
    assert record.read_text().startswith(str(fake_bin / "codex") + "|")

    assert run_installer(home, "--agent", "claude").returncode == 0
    completed = subprocess.run(
        [str(launcher), "-f"], env=environment, capture_output=True, text=True, check=False
    )
    assert completed.returncode == 0, completed.stderr
    assert record.read_text().startswith(str(fake_bin / "claude") + "|")


def test_installer_refuses_symlinked_runtime_root(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    synthesis = home / ".synthesis"
    synthesis.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (synthesis / "day-end").symlink_to(elsewhere, target_is_directory=True)

    completed = run_installer(home)
    assert completed.returncode == 2
    assert "symlinked runtime path" in completed.stderr
    assert list(elsewhere.iterdir()) == []


def run_launcher(environment: dict[str, str], *arguments: str):
    return subprocess.run(
        ["bash", str(SCRIPT_DIR / "day-end"), *arguments],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )


def fake_agent(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('#!/bin/sh\nprintf "%s" "$1"\n', encoding="utf-8")
    path.chmod(0o755)
    return path


def test_day_end_launcher_accepts_explicit_command_path(tmp_path: Path) -> None:
    agent = fake_agent(tmp_path / "fake-agent")
    completed = run_launcher(
        {**os.environ, "DAY_END_AGENT_CMD": str(agent)}, "-q"
    )
    assert completed.returncode == 0, completed.stderr
    assert "Quick Close" in completed.stdout


def test_day_end_launcher_resolves_named_agent_from_known_locations(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    fake_agent(home / ".local" / "bin" / "codex")
    completed = run_launcher(
        {
            "PATH": "/usr/bin:/bin",
            "HOME": str(home),
            "DAY_END_AGENT_CMD": "codex",
        }
    )
    assert completed.returncode == 0, completed.stderr
    assert "Day-End ritual" in completed.stdout


def test_day_end_launcher_fails_closed_when_no_agent_exists(tmp_path: Path) -> None:
    home = tmp_path / "empty-home"
    home.mkdir()
    completed = run_launcher(
        {
            "PATH": "/usr/bin:/bin",
            "HOME": str(home),
            "DAY_END_AGENT_CMD": "codex",
            "SYNTHESIS_CODEX_BIN": "",
        }
    )
    assert completed.returncode == 127
    assert "unavailable" in completed.stderr


def test_day_end_launcher_honors_binary_override(tmp_path: Path) -> None:
    agent = fake_agent(tmp_path / "custom" / "codex")
    completed = run_launcher(
        {
            "PATH": "/usr/bin:/bin",
            "HOME": str(tmp_path / "home"),
            "DAY_END_AGENT_CMD": "codex",
            "SYNTHESIS_CODEX_BIN": str(agent),
        },
        "-o",
    )
    assert completed.returncode == 0, completed.stderr
    assert "observer" in completed.stdout

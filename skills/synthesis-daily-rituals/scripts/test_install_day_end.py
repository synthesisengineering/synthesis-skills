from __future__ import annotations

import hashlib
import os
import plistlib
import subprocess
import sys
from pathlib import Path


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
        for name in ("day-end", "day-end-nudge.sh")
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
    assert ".claude" not in plist_path.read_text(encoding="utf-8")
    assert ".codex" not in plist_path.read_text(encoding="utf-8")

    for name, before in source_digests.items():
        assert digest(SCRIPT_DIR / name) == before


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

from __future__ import annotations

import fcntl
import importlib.util
import json
import os
import plistlib
import shutil
import subprocess
from pathlib import Path

import pytest


SCRIPT = Path(__file__).with_name("cache_guardian.py")
SPEC = importlib.util.spec_from_file_location("cache_guardian", SCRIPT)
assert SPEC and SPEC.loader
guardian = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guardian)


def seed_root(root: Path, version: str, marker: str) -> None:
    (root / ".claude-plugin").mkdir(parents=True)
    (root / ".codex-plugin").mkdir(parents=True)
    manifest = json.dumps({"version": version})
    (root / ".claude-plugin" / "plugin.json").write_text(manifest, encoding="utf-8")
    (root / ".codex-plugin" / "plugin.json").write_text(manifest, encoding="utf-8")
    hook = root / "skills" / "synthesis-autopilot" / "scripts" / "autopilot_gate.py"
    hook.parent.mkdir(parents=True)
    hook.write_text(f"print({marker!r})\n", encoding="utf-8")
    (hook.parents[1] / "SKILL.md").write_text("---\nname: synthesis-autopilot\n---\n", encoding="utf-8")
    (root / "hooks").mkdir()
    (root / "hooks" / "hooks.json").write_text(
        json.dumps(
            {
                "hooks": {
                    "Stop": [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "python3 ${CLAUDE_PLUGIN_ROOT}/skills/synthesis-autopilot/scripts/autopilot_gate.py --gate",
                                }
                            ]
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )


def seeded_home(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    archive = guardian.archive_root(home)
    seed_root(archive / "4.73.0", "4.73.0", "old")
    seed_root(archive / "4.77.1", "4.77.1", "current")
    return home


def test_restore_protects_history_but_never_installs_current(tmp_path: Path) -> None:
    home = seeded_home(tmp_path)

    record = guardian.restore_once(home)

    cache = guardian.cache_parent(home)
    assert (cache / "4.73.0" / "skills/synthesis-autopilot/scripts/autopilot_gate.py").is_file()
    assert not (cache / "4.77.1").exists()
    assert record["current_excluded"] == "4.77.1"
    assert record["restored"] == ["4.73.0"]
    assert json.loads(guardian.receipt_path(home).read_text(encoding="utf-8"))["verified"] == 1


def test_restore_prioritizes_newest_historical_roots(tmp_path: Path) -> None:
    home = seeded_home(tmp_path)
    archive = guardian.archive_root(home)
    seed_root(archive / "4.74.0", "4.74.0", "newer history")
    seed_root(archive / "4.75.0", "4.75.0", "newest history")

    record = guardian.restore_once(home)

    assert record["protected_versions"] == ["4.73.0", "4.74.0", "4.75.0"]
    assert record["restored"] == ["4.75.0", "4.74.0", "4.73.0"]


def test_later_parent_generation_is_repaired_without_touching_current(
    tmp_path: Path,
) -> None:
    home = seeded_home(tmp_path)
    guardian.restore_once(home)
    cache = guardian.cache_parent(home)
    first_signature = guardian._cache_signature(home)

    shutil.rmtree(cache)
    current = cache / "4.77.1"
    current.mkdir(parents=True)
    (current / "client-owned").write_text("new generation\n", encoding="utf-8")
    replacement_signature = guardian._cache_signature(home)
    assert replacement_signature != first_signature

    record = guardian.restore_once(home)

    assert (cache / "4.73.0" / "skills/synthesis-autopilot/scripts/autopilot_gate.py").is_file()
    assert (current / "client-owned").read_text(encoding="utf-8") == "new generation\n"
    assert record["restored"] == ["4.73.0"]


def test_differing_existing_history_fails_closed_without_overwrite(
    tmp_path: Path,
) -> None:
    home = seeded_home(tmp_path)
    guardian.restore_once(home)
    target = guardian.cache_parent(home) / "4.73.0" / "unexpected"
    target.write_text("do not erase\n", encoding="utf-8")

    with pytest.raises(guardian.GuardianError, match="differs from archive"):
        guardian.restore_once(home)

    assert target.read_text(encoding="utf-8") == "do not erase\n"


def test_unsafe_archive_symlink_is_refused(tmp_path: Path) -> None:
    home = seeded_home(tmp_path)
    (guardian.archive_root(home) / "4.73.0" / "escape").symlink_to("../../outside")

    with pytest.raises(guardian.GuardianError, match="unsafe archive symlink"):
        guardian.restore_once(home)


def test_release_lock_defers_guardian_without_writing(tmp_path: Path) -> None:
    home = seeded_home(tmp_path)
    path = guardian.lock_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+")
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        with pytest.raises(guardian.GuardianBusy):
            guardian.restore_once(home)
    finally:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()
    assert not guardian.cache_parent(home).exists()


def test_launchd_definition_is_persistent_and_runs_stable_runtime(tmp_path: Path) -> None:
    home = tmp_path / "home"
    runtime = guardian.runtime_path(home)

    payload = plistlib.loads(guardian._launchd_payload(home, runtime))

    assert payload["Label"] == guardian.LABEL
    assert payload["ProgramArguments"] == [os.sys.executable, str(runtime), "--watch"]
    assert payload["RunAtLoad"] is True
    assert payload["KeepAlive"] is True
    assert payload["ThrottleInterval"] == 10


def test_macos_supervisor_is_loaded_and_verified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    runtime = guardian.runtime_path(home)
    runtime.parent.mkdir(parents=True)
    runtime.write_text("guardian\n", encoding="utf-8")
    calls: list[list[str]] = []

    def fake_run(command, **_kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="ok\n", stderr="")

    monkeypatch.setattr(guardian.shutil, "which", lambda name: "/bin/launchctl")

    installed = guardian.install_supervisor(
        home, runtime, platform="darwin", runner=fake_run
    )

    plist = home / "Library" / "LaunchAgents" / f"{guardian.LABEL}.plist"
    assert installed == str(plist)
    assert plist.is_file()
    assert [command[1] for command in calls] == ["bootout", "bootstrap", "kickstart", "print"]


def test_systemd_definition_restarts_and_uses_stable_runtime(tmp_path: Path) -> None:
    runtime = guardian.runtime_path(tmp_path / "home with spaces")

    payload = guardian._systemd_payload(runtime).decode("utf-8")

    assert "Restart=always" in payload
    assert str(runtime) in payload
    assert "--watch" in payload


def test_linux_supervisor_restarts_changed_runtime_and_verifies_active(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    runtime = guardian.runtime_path(home)
    runtime.parent.mkdir(parents=True)
    runtime.write_text("guardian\n", encoding="utf-8")
    calls: list[list[str]] = []

    def fake_run(command, **_kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="active\n", stderr="")

    monkeypatch.setattr(guardian.shutil, "which", lambda name: "/bin/systemctl")

    guardian.install_supervisor(home, runtime, platform="linux", runner=fake_run)

    assert [command[2] for command in calls] == [
        "daemon-reload",
        "enable",
        "restart",
        "is-active",
    ]

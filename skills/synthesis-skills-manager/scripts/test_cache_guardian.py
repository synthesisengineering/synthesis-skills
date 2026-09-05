from __future__ import annotations

import fcntl
import hashlib
import importlib.util
import json
import os
import plistlib
import shutil
import sqlite3
import subprocess
import sys
import time
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


def test_recovery_archive_deduplicates_and_preserves_all_history(tmp_path: Path) -> None:
    home = seeded_home(tmp_path)
    archive = guardian.archive_root(home)
    for version in ("4.73.0", "4.77.1"):
        root = archive / version
        (root / "shared").write_bytes(b"shared payload" * 10000)
        (root / "shared").chmod(0o755 if version == "4.73.0" else 0o644)
        (root / "empty").mkdir(mode=0o750)
        (root / "alias").symlink_to("shared")
    expected = {v: guardian._tree_digest(archive / v) for v in ("4.73.0", "4.77.1")}
    guardian.persist_archive(archive, {}, budget=200000)
    store = guardian.RecoveryStore.read(archive)
    assert set(store.versions) == set(expected)
    assert sum(data == b"shared payload" * 10000 for data in store.objects.values()) == 1
    assert store.stored_bytes <= 200000
    assert not (archive / "4.73.0").exists()
    for version, digest in expected.items():
        target = tmp_path / version
        store.materialize(version, target)
        assert guardian._tree_digest(target) == digest
        assert (target / "shared").stat().st_mode & 0o777 == (0o755 if version == "4.73.0" else 0o644)
    guardian.restore_once(home)
    cache = guardian.cache_parent(home)
    (cache / "4.73.0" / "shared").write_bytes(b"changed cache")
    assert b"shared payload" * 10000 in guardian.RecoveryStore.read(archive).objects.values()
    assert (tmp_path / "4.77.1" / "shared").read_bytes() == b"shared payload" * 10000


def test_recovery_archive_budget_refuses_before_promoting(tmp_path: Path) -> None:
    home = seeded_home(tmp_path)
    archive = guardian.archive_root(home)
    guardian.persist_archive(archive, {})
    database = archive / guardian.STORE_NAME
    before = database.read_bytes()
    new = tmp_path / "new"
    seed_root(new, "4.78.0", "new")
    with pytest.raises(guardian.GuardianError, match="hard budget"):
        guardian.persist_archive(archive, {"4.78.0": new}, budget=1)
    assert database.read_bytes() == before
    assert set(guardian.RecoveryStore.read(archive).versions) == {"4.73.0", "4.77.1"}


@pytest.mark.parametrize("damage", ["payload", "missing", "manifest"])
def test_recovery_archive_rejects_structurally_valid_database_corruption(tmp_path: Path, damage: str) -> None:
    home = seeded_home(tmp_path)
    archive = guardian.archive_root(home)
    guardian.persist_archive(archive, {})
    with sqlite3.connect(archive / guardian.STORE_NAME) as db:
        if damage == "payload":
            db.execute("UPDATE objects SET payload = ? WHERE digest = (SELECT digest FROM objects LIMIT 1)", (b"bad",))
        elif damage == "missing":
            db.execute("DELETE FROM objects WHERE digest = (SELECT digest FROM objects LIMIT 1)")
        else:
            db.execute("UPDATE versions SET manifest = '{}' WHERE version = '4.73.0'")
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    with pytest.raises(guardian.GuardianError):
        guardian.restore_once(home)
    assert not guardian.cache_parent(home).exists()


def test_mode_corruption_is_not_accepted_as_historical_integrity(tmp_path: Path) -> None:
    home = seeded_home(tmp_path)
    hook = Path("skills/synthesis-autopilot/scripts/autopilot_gate.py")
    (guardian.archive_root(home) / "4.73.0" / hook).chmod(0o755)
    guardian.restore_once(home)
    (guardian.cache_parent(home) / "4.73.0" / hook).chmod(0o644)
    with pytest.raises(guardian.GuardianError, match="differs from archive"):
        guardian.restore_once(home)


@pytest.mark.parametrize("database", [False, True])
def test_historical_root_mode_is_part_of_verified_identity(tmp_path: Path, database: bool) -> None:
    home = seeded_home(tmp_path)
    if database:
        guardian.persist_archive(guardian.archive_root(home), {})
    guardian.restore_once(home)
    (guardian.cache_parent(home) / "4.73.0").chmod(0o777)
    with pytest.raises(guardian.GuardianError, match="differs from archive"):
        guardian.restore_once(home)


@pytest.mark.parametrize("phase", ["candidate", "promoted", "renamed", "partial-retirement"])
def test_recovery_archive_real_process_interruptions_resume(tmp_path: Path, phase: str) -> None:
    home = seeded_home(tmp_path)
    archive = guardian.archive_root(home)
    code = r'''
import importlib.util, os, shutil, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location("guardian", sys.argv[1])
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)
archive, phase = Path(sys.argv[2]), sys.argv[3]
if phase == "candidate":
    real = g.RecoveryStore.read_file.__func__
    def interrupted(cls, path, **kwargs):
        result = real(cls, path, **kwargs)
        if path.name.startswith(".recovery-candidate-"):
            os._exit(23)
        return result
    g.RecoveryStore.read_file = classmethod(interrupted)
elif phase == "promoted":
    real = g.os.replace
    def interrupted(source, target):
        real(source, target)
        if Path(target).name == g.STORE_NAME:
            os._exit(23)
    g.os.replace = interrupted
elif phase == "renamed":
    real = g.os.rename
    def interrupted(source, target):
        real(source, target)
        if Path(target).name.startswith(".retired-"):
            os._exit(23)
    g.os.rename = interrupted
else:
    def interrupted(path):
        next(p for p in Path(path).rglob("*") if p.is_file()).unlink()
        os._exit(23)
    g.shutil.rmtree = interrupted
g.persist_archive(archive, {})
'''
    result = subprocess.run([sys.executable, "-B", "-c", code, str(SCRIPT), str(archive), phase])
    assert result.returncode == 23
    # Independently restarted reader can recover during every cutover state.
    assert guardian.restore_once(home)["verified"] == 1
    guardian.persist_archive(archive, {})
    assert set(guardian.RecoveryStore.read(archive).versions) == {"4.73.0", "4.77.1"}
    assert not any(p.is_dir() for p in archive.iterdir())
    assert guardian.restore_once(home)["verified"] == 1


@pytest.mark.parametrize("damage", ["traversal", "mode", "parent-link", "empty-parent", "link-traversal"])
def test_recovery_archive_refuses_rehashed_unsafe_manifest(tmp_path: Path, damage: str) -> None:
    home = seeded_home(tmp_path)
    archive = guardian.archive_root(home)
    guardian.persist_archive(archive, {})
    with sqlite3.connect(archive / guardian.STORE_NAME) as db:
        payload = json.loads(db.execute("SELECT manifest FROM versions WHERE version = '4.73.0'").fetchone()[0])
        if damage == "traversal":
            payload["entries"]["../sentinel"] = ["dir", 0o755]
        elif damage == "mode":
            payload["entries"]["skills"][1] = 0o4777
        elif damage == "parent-link":
            payload["entries"]["skills"] = ["link", 0o755, "hooks"]
        elif damage == "empty-parent":
            payload["entries"]["skills"] = []
        else:
            payload["entries"]["alias"] = ["link", 0o755, "../sentinel"]
        raw = json.dumps(payload)
        db.execute("UPDATE versions SET manifest=?, digest=? WHERE version='4.73.0'", (raw, hashlib.sha256(raw.encode()).hexdigest()))
    with pytest.raises(guardian.GuardianError):
        guardian.restore_once(home)
    assert not guardian.cache_parent(home).exists()


@pytest.mark.parametrize("damage", ["symlink", "hardlink", "parent-link", "fifo"])
def test_recovery_archive_refuses_unsafe_database_targets(tmp_path: Path, damage: str) -> None:
    home = seeded_home(tmp_path)
    archive = guardian.archive_root(home)
    guardian.persist_archive(archive, {})
    database = archive / guardian.STORE_NAME
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel"
    sentinel.write_bytes(database.read_bytes())
    before = sentinel.read_bytes()
    if damage == "parent-link":
        moved = archive.with_name("saved")
        archive.rename(moved)
        archive.symlink_to(moved)
    else:
        database.unlink()
        if damage == "symlink":
            database.symlink_to(sentinel)
        elif damage == "hardlink":
            os.link(sentinel, database)
        else:
            os.mkfifo(database)
    with pytest.raises(guardian.GuardianError):
        guardian.persist_archive(archive, {})
    assert sentinel.read_bytes() == before


def test_existing_version_cannot_replace_historical_source(tmp_path: Path) -> None:
    home = seeded_home(tmp_path)
    archive = guardian.archive_root(home)
    guardian.persist_archive(archive, {})
    previous = (archive / guardian.STORE_NAME).read_bytes()
    differing = tmp_path / "differing"
    seed_root(differing, "4.73.0", "altered history")
    with pytest.raises(guardian.GuardianError, match="immutable historical version"):
        guardian.persist_archive(archive, {"4.73.0": differing})
    assert (archive / guardian.STORE_NAME).read_bytes() == previous


def test_unowned_archive_files_refuse_before_migration(tmp_path: Path) -> None:
    home = seeded_home(tmp_path)
    archive = guardian.archive_root(home)
    sentinel = archive / "unowned"
    sentinel.write_bytes(b"preserve")
    with pytest.raises(guardian.GuardianError, match="unexpected or unsafe archive entry"):
        guardian.persist_archive(archive, {})
    assert sentinel.read_bytes() == b"preserve"
    assert (archive / "4.73.0").is_dir()
    assert not (archive / guardian.STORE_NAME).exists()


def test_standalone_guardian_restores_database_history_after_repeated_reconciliation(tmp_path: Path) -> None:
    home = seeded_home(tmp_path)
    guardian.persist_archive(guardian.archive_root(home), {})
    runtime = guardian.runtime_path(home)
    runtime.write_bytes(SCRIPT.read_bytes())
    env = dict(os.environ, HOME=str(home), PYTHONDONTWRITEBYTECODE="1")
    env.pop("PYTHONPATH", None)
    cache = guardian.cache_parent(home)
    for _ in range(2):
        cache.mkdir(parents=True, exist_ok=True)
        current = cache / "4.77.1"
        current.mkdir()
        (current / "client-owned").write_text("untouched")
        result = subprocess.run([sys.executable, "-B", str(runtime), "--once"], cwd=tmp_path, env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["restored"] == ["4.73.0"]
        assert (current / "client-owned").read_text() == "untouched"
        shutil.rmtree(cache)


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


def test_runtime_bytecode_does_not_invalidate_historical_source(
    tmp_path: Path,
) -> None:
    home = seeded_home(tmp_path)
    guardian.restore_once(home)
    target = (
        guardian.cache_parent(home)
        / "4.73.0"
        / "skills/synthesis-autopilot/scripts/__pycache__/autopilot_gate.cpython-312.pyc"
    )
    target.parent.mkdir()
    target.write_bytes(b"runtime bytecode\n")
    temporary = target.with_name(f"{target.name}.123456789")
    temporary.write_bytes(b"CPython atomic-write staging\n")

    record = guardian.restore_once(home)

    assert record["verified"] == 1
    assert target.read_bytes() == b"runtime bytecode\n"
    assert temporary.read_bytes() == b"CPython atomic-write staging\n"


@pytest.mark.parametrize(
    ("relative", "content"),
    [
        ("skills/synthesis-autopilot/scripts/autopilot_gate.py", "changed source\n"),
        ("skills/synthesis-autopilot/scripts/autopilot_gate.pyc", "loose bytecode\n"),
        ("skills/synthesis-autopilot/scripts/__pycache__/unexpected.txt", "unknown\n"),
        ("skills/synthesis-autopilot/scripts/__pycache__/hook.pyc.tmp", "unknown\n"),
        ("skills/synthesis-autopilot/scripts/__pycache__/hook.pyc.notdigits", "unknown\n"),
    ],
)
def test_bytecode_exception_does_not_hide_source_or_unknown_drift(
    tmp_path: Path, relative: str, content: str
) -> None:
    home = seeded_home(tmp_path)
    guardian.restore_once(home)
    target = guardian.cache_parent(home) / "4.73.0" / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")

    with pytest.raises(guardian.GuardianError, match="differs from archive"):
        guardian.restore_once(home)


def test_bytecode_exception_refuses_symlinked_cache_directory(tmp_path: Path) -> None:
    home = seeded_home(tmp_path)
    guardian.restore_once(home)
    scripts = (
        guardian.cache_parent(home) / "4.73.0" / "skills/synthesis-autopilot/scripts"
    )
    (scripts / "__pycache__").symlink_to(".")

    with pytest.raises(
        guardian.GuardianError, match="unsafe Python bytecode cache directory"
    ):
        guardian.restore_once(home)


def test_bytecode_exception_does_not_hide_nested_cache_directory(tmp_path: Path) -> None:
    home = seeded_home(tmp_path)
    guardian.restore_once(home)
    nested = (
        guardian.cache_parent(home)
        / "4.73.0"
        / "skills/synthesis-autopilot/scripts/__pycache__/__pycache__"
    )
    nested.mkdir(parents=True)

    with pytest.raises(guardian.GuardianError, match="differs from archive"):
        guardian.restore_once(home)


def test_bytecode_exception_refuses_special_cache_entry(tmp_path: Path) -> None:
    home = seeded_home(tmp_path)
    guardian.restore_once(home)
    target = (
        guardian.cache_parent(home)
        / "4.73.0"
        / "skills/synthesis-autopilot/scripts/__pycache__/unsafe.pyc"
    )
    target.parent.mkdir()
    os.mkfifo(target)

    with pytest.raises(
        guardian.GuardianError, match="unsafe Python bytecode cache entry"
    ):
        guardian.restore_once(home)


def test_tree_digest_refuses_unknown_special_object(tmp_path: Path) -> None:
    home = seeded_home(tmp_path)
    guardian.restore_once(home)
    target = guardian.cache_parent(home) / "4.73.0" / "unexpected.pipe"
    os.mkfifo(target)

    with pytest.raises(guardian.GuardianError, match="unsupported cache entry type"):
        guardian.restore_once(home)


def test_unsafe_archive_symlink_is_refused(tmp_path: Path) -> None:
    home = seeded_home(tmp_path)
    (guardian.archive_root(home) / "4.73.0" / "escape").symlink_to("../../outside")

    with pytest.raises(guardian.GuardianError, match="unsafe archive symlink"):
        guardian.restore_once(home)


def test_shipped_python_hooks_disable_bytecode_writes() -> None:
    repository = Path(__file__).resolve().parents[3]
    payload = json.loads((repository / "hooks/hooks.json").read_text(encoding="utf-8"))
    commands = [
        hook["command"]
        for registrations in payload["hooks"].values()
        for registration in registrations
        for hook in registration["hooks"]
        if hook.get("type") == "command"
        and hook.get("command", "").startswith("python3 ")
    ]

    assert commands
    assert all(command.startswith("python3 -B ") for command in commands)


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


def test_doctor_waits_for_background_guardian_but_once_remains_nonblocking(
    tmp_path: Path,
) -> None:
    home = seeded_home(tmp_path)
    runtime = guardian.runtime_path(home)
    runtime.parent.mkdir(parents=True, exist_ok=True)
    runtime.write_text("guardian\n", encoding="utf-8")
    path = guardian.lock_path(home)
    handle = path.open("a+")
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        once = subprocess.run(
            [sys.executable, str(SCRIPT), "--once"],
            capture_output=True,
            text=True,
            timeout=5,
            env=env,
            check=False,
        )
        assert once.returncode == guardian.EX_TEMPFAIL

        doctor = subprocess.Popen(
            [sys.executable, str(SCRIPT), "--doctor"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        time.sleep(0.1)
        assert doctor.poll() is None
    finally:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()

    stdout, stderr = doctor.communicate(timeout=5)
    assert doctor.returncode == 0, stdout + stderr
    assert json.loads(stdout)["verified"] == 1


def test_blocking_cache_lock_wait_is_bounded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = seeded_home(tmp_path)
    path = guardian.lock_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+")
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    moments = iter((10.0, 131.0))
    monkeypatch.setattr(guardian.time, "monotonic", lambda: next(moments))
    try:
        with pytest.raises(guardian.GuardianBusy, match="more than 120 seconds"):
            with guardian._cache_lock(home, blocking=True):
                pytest.fail("contended lock was acquired")
    finally:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


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

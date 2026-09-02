#!/usr/bin/env python3
"""Keep historical Codex plugin roots available after cache reconciliation.

Codex owns its cache directory and may replace the complete directory well
after an install command returns. Running tasks still execute hook commands
bound to the absolute version root from their SessionStart. The release
publisher therefore keeps an immutable, budgeted archive outside the client
cache, while this guardian restores historical roots whenever a later cache
generation removes them.

The newest archived version is deliberately excluded: it is the version the
client currently owns and may be installing. The guardian never deletes a
cache path and never writes through a differing existing root.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Iterator


MARKETPLACE = "synthesis-engineering"
PLUGIN_NAME = "synthesis-skills"
LABEL = "org.synthesisengineering.synthesis-skills-cache-guardian"
VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
HOOK_PLUGIN_PATH_RE = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/([^\s\"']+)")
IGNORED_ROOTS = frozenset({".git", ".in_use", ".codex-marketplace-install.json"})
DEFAULT_INTERVAL_SECONDS = 1.0
ERROR_RETRY_SECONDS = 10.0
EX_TEMPFAIL = 75


class GuardianError(RuntimeError):
    """The guardian could not establish or preserve a safe cache state."""


class GuardianBusy(GuardianError):
    """The release transition currently owns the shared cache lock."""


def archive_root(home: Path) -> Path:
    return home / ".synthesis" / "plugin-cache-recovery" / MARKETPLACE / PLUGIN_NAME


def cache_parent(home: Path) -> Path:
    return home / ".codex" / "plugins" / "cache" / MARKETPLACE / PLUGIN_NAME


def runtime_path(home: Path) -> Path:
    return archive_root(home).parent / f".{PLUGIN_NAME}-cache-guardian.py"


def receipt_path(home: Path) -> Path:
    return archive_root(home).parent / "cache-guardian-last.json"


def lock_path(home: Path) -> Path:
    return archive_root(home).parent / f".{PLUGIN_NAME}.release.lock"


def _version_key(version: str) -> tuple[int, int, int]:
    return tuple(int(part) for part in version.split("."))  # type: ignore[return-value]


def _version_roots(parent: Path) -> dict[str, Path]:
    if not parent.is_dir() or parent.is_symlink():
        return {}
    return {
        child.name: child
        for child in sorted(parent.iterdir(), key=lambda item: item.name)
        if child.is_dir()
        and not child.is_symlink()
        and VERSION_RE.fullmatch(child.name) is not None
    }


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda item: str(item.relative_to(root))):
        relative_path = path.relative_to(root)
        if relative_path.parts and relative_path.parts[0] in IGNORED_ROOTS:
            continue
        relative = str(relative_path).encode("utf-8")
        if path.is_symlink():
            digest.update(b"L\0" + relative + b"\0" + os.readlink(path).encode("utf-8"))
        elif path.is_dir():
            digest.update(b"D\0" + relative)
        elif path.is_file():
            digest.update(b"F\0" + relative + b"\0" + path.read_bytes())
    return digest.hexdigest()


def _validate_root(root: Path, version: str) -> None:
    if not root.is_dir() or root.is_symlink():
        raise GuardianError(f"archive root is absent, not a directory, or a symlink: {root}")
    for path in root.rglob("*"):
        if not path.is_symlink():
            continue
        link = PurePosixPath(os.readlink(path))
        if link.is_absolute() or ".." in link.parts:
            raise GuardianError(
                f"unsafe archive symlink: {path.relative_to(root)} -> {link}"
            )
    versions: set[str] = set()
    for manifest in (".claude-plugin/plugin.json", ".codex-plugin/plugin.json"):
        candidate = root / manifest
        if not candidate.is_file():
            continue
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GuardianError(f"unreadable archive manifest {candidate}: {exc}") from exc
        value = payload.get("version")
        if isinstance(value, str):
            versions.add(value)
    if version not in versions:
        raise GuardianError(f"no archive manifest reports {version}: {root}")
    hooks = root / "hooks" / "hooks.json"
    try:
        hook_text = hooks.read_text(encoding="utf-8")
        json.loads(hook_text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GuardianError(f"unreadable archive hook definition {hooks}: {exc}") from exc
    targets = sorted(set(HOOK_PLUGIN_PATH_RE.findall(hook_text)))
    if not targets:
        raise GuardianError(f"archive hook definition has no plugin-root target: {hooks}")
    missing = [target for target in targets if not (root / target).is_file()]
    if missing:
        raise GuardianError(f"archive root {version} misses hook target(s): {', '.join(missing[:3])}")
    if not any(root.glob("skills/*/SKILL.md")):
        raise GuardianError(f"archive root has no skill entry point: {root}")


def _refuse_symlinked_boundary(home: Path, path: Path) -> None:
    if not home.is_absolute() or not path.is_absolute():
        raise GuardianError("home and cache boundaries must be absolute")
    try:
        relative = path.relative_to(home)
    except ValueError as exc:
        raise GuardianError(f"path escapes home boundary: {path}") from exc
    cursor = home
    if cursor.is_symlink():
        raise GuardianError(f"home boundary is a symlink: {cursor}")
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise GuardianError(f"refusing symlinked cache boundary: {cursor}")


def _atomic_write(path: Path, payload: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise GuardianError(f"refusing to replace symlinked file: {path}")
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def _cache_lock(home: Path, *, blocking: bool) -> Iterator[None]:
    path = lock_path(home)
    _refuse_symlinked_boundary(home, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    handle = os.fdopen(descriptor, "a+")
    operation = fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB)
    try:
        try:
            fcntl.flock(handle.fileno(), operation)
        except (BlockingIOError, OSError) as exc:
            raise GuardianBusy("release transition owns the cache lock") from exc
        yield
    finally:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def _remove_staging(path: Path, parent: Path) -> None:
    if not path.exists():
        return
    if path.parent != parent or not path.name.startswith(".guardian-") or path.is_symlink():
        raise GuardianError(f"refusing unsafe staging cleanup target: {path}")
    shutil.rmtree(path)


def _restore_missing(source: Path, destination: Path, parent: Path) -> bool:
    staging = parent / f".guardian-{destination.name}-{os.getpid()}-{time.time_ns()}"
    try:
        shutil.copytree(source, staging, symlinks=True)
        if _tree_digest(source) != _tree_digest(staging):
            raise GuardianError(f"staged recovery differs from archive: {source.name}")
        if destination.exists() or destination.is_symlink():
            if destination.is_symlink() or not destination.is_dir():
                raise GuardianError(f"cache root appeared with an unsafe type: {destination}")
            if _tree_digest(source) != _tree_digest(destination):
                raise GuardianError(f"cache root appeared with differing content: {destination}")
            return False
        os.rename(staging, destination)
        if _tree_digest(source) != _tree_digest(destination):
            raise GuardianError(f"restored cache root differs from archive: {destination}")
        return True
    finally:
        _remove_staging(staging, parent)


def restore_once(home: Path | None = None, *, blocking: bool = False) -> dict[str, object]:
    home = (home or Path.home()).absolute()
    archive = archive_root(home)
    cache = cache_parent(home)
    _refuse_symlinked_boundary(home, archive)
    _refuse_symlinked_boundary(home, cache)
    if not archive.is_dir():
        raise GuardianError(f"recovery archive is unavailable: {archive}")
    archived = _version_roots(archive)
    if not archived:
        raise GuardianError(f"recovery archive has no version roots: {archive}")
    ordered = sorted(archived, key=_version_key)
    current = ordered[-1]
    protected = ordered[:-1]
    restored: list[str] = []
    verified: list[str] = []
    with _cache_lock(home, blocking=blocking):
        cache.mkdir(parents=True, exist_ok=True)
        if cache.is_symlink():
            raise GuardianError(f"cache parent is a symlink: {cache}")
        # A task is most likely to be pinned to the version immediately before
        # the current release. Restore from newest to oldest so that root is
        # available first even when a large archive takes time to rehydrate.
        for version in reversed(protected):
            source = archived[version]
            _validate_root(source, version)
            destination = cache / version
            if destination.is_symlink() or (destination.exists() and not destination.is_dir()):
                raise GuardianError(f"historical cache root has an unsafe type: {destination}")
            if not destination.exists():
                if _restore_missing(source, destination, cache):
                    restored.append(version)
            elif _tree_digest(source) != _tree_digest(destination):
                raise GuardianError(f"historical cache root differs from archive: {destination}")
            verified.append(version)
    record: dict[str, object] = {
        "schema": 1,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "archive": str(archive),
        "cache": str(cache),
        "current_excluded": current,
        "protected_versions": protected,
        "verified": len(verified),
        "restored": restored,
    }
    _atomic_write(receipt_path(home), (json.dumps(record, indent=2, sort_keys=True) + "\n").encode(), 0o600)
    return record


def _cache_signature(home: Path) -> tuple[object, ...]:
    parent = cache_parent(home)
    if not parent.is_dir() or parent.is_symlink():
        return ("absent",)
    stat = parent.stat()
    return (stat.st_ino, stat.st_mtime_ns, tuple(sorted(_version_roots(parent))))


def watch(home: Path | None = None, interval: float = DEFAULT_INTERVAL_SECONDS) -> None:
    home = (home or Path.home()).absolute()
    previous: tuple[object, ...] | None = None
    while True:
        signature = _cache_signature(home)
        if signature != previous:
            try:
                restore_once(home)
                previous = _cache_signature(home)
            except GuardianBusy:
                previous = None
            except GuardianError as exc:
                print(f"cache guardian retrying after error: {exc}", file=sys.stderr, flush=True)
                previous = None
                time.sleep(ERROR_RETRY_SECONDS)
                continue
        time.sleep(interval)


def _launchd_payload(home: Path, runtime: Path) -> bytes:
    logs = archive_root(home).parent / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    return plistlib.dumps(
        {
            "Label": LABEL,
            "ProgramArguments": [sys.executable, str(runtime), "--watch"],
            "RunAtLoad": True,
            "KeepAlive": True,
            "ThrottleInterval": 10,
            "ProcessType": "Background",
            "StandardOutPath": str(logs / "cache-guardian.out.log"),
            "StandardErrorPath": str(logs / "cache-guardian.err.log"),
        },
        sort_keys=False,
    )


def _systemd_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _systemd_payload(runtime: Path) -> bytes:
    command = " ".join(_systemd_quote(value) for value in (sys.executable, str(runtime), "--watch"))
    return (
        "[Unit]\nDescription=Synthesis Skills historical Codex cache guardian\n\n"
        "[Service]\nType=simple\n"
        f"ExecStart={command}\n"
        "Restart=always\nRestartSec=10\n\n"
        "[Install]\nWantedBy=default.target\n"
    ).encode()


def _completed_detail(completed: subprocess.CompletedProcess[str]) -> str:
    return (completed.stderr or completed.stdout or "").strip()


def install_supervisor(
    home: Path,
    runtime: Path,
    *,
    platform: str | None = None,
    runner=subprocess.run,
) -> str:
    platform = platform or sys.platform
    if platform == "darwin":
        launchctl = shutil.which("launchctl")
        if launchctl is None:
            raise GuardianError("launchctl is required for the macOS cache guardian")
        plist = home / "Library" / "LaunchAgents" / f"{LABEL}.plist"
        _refuse_symlinked_boundary(home, plist)
        _atomic_write(plist, _launchd_payload(home, runtime), 0o644)
        domain = f"gui/{os.getuid()}"
        runner([launchctl, "bootout", domain, str(plist)], capture_output=True, text=True, check=False)
        boot = runner([launchctl, "bootstrap", domain, str(plist)], capture_output=True, text=True, check=False)
        if boot.returncode:
            raise GuardianError(f"launchctl bootstrap failed: {_completed_detail(boot)}")
        kick = runner([launchctl, "kickstart", "-k", f"{domain}/{LABEL}"], capture_output=True, text=True, check=False)
        if kick.returncode:
            raise GuardianError(f"launchctl kickstart failed: {_completed_detail(kick)}")
        probe = runner([launchctl, "print", f"{domain}/{LABEL}"], capture_output=True, text=True, check=False)
        if probe.returncode:
            raise GuardianError(f"launchctl could not verify the guardian: {_completed_detail(probe)}")
        return str(plist)
    if platform.startswith("linux"):
        systemctl = shutil.which("systemctl")
        if systemctl is None:
            raise GuardianError("systemctl is required for the Linux cache guardian")
        unit = home / ".config" / "systemd" / "user" / f"{LABEL}.service"
        _refuse_symlinked_boundary(home, unit)
        _atomic_write(unit, _systemd_payload(runtime), 0o644)
        for command in (
            [systemctl, "--user", "daemon-reload"],
            [systemctl, "--user", "enable", "--now", unit.name],
            [systemctl, "--user", "restart", unit.name],
            [systemctl, "--user", "is-active", unit.name],
        ):
            completed = runner(command, capture_output=True, text=True, check=False)
            if completed.returncode:
                raise GuardianError(f"systemd guardian command failed: {_completed_detail(completed)}")
        return str(unit)
    raise GuardianError(f"no supported user supervisor on platform {platform}")


def install(home: Path | None = None) -> dict[str, object]:
    home = (home or Path.home()).absolute()
    runtime = runtime_path(home)
    _refuse_symlinked_boundary(home, runtime)
    source = Path(__file__).resolve()
    _atomic_write(runtime, source.read_bytes(), 0o755)
    if runtime.read_bytes() != source.read_bytes():
        raise GuardianError(f"installed guardian differs from source: {runtime}")
    record = restore_once(home, blocking=True)
    supervisor = install_supervisor(home, runtime)
    record["runtime"] = str(runtime)
    record["supervisor"] = supervisor
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--once", action="store_true", help="restore and verify historical roots once")
    modes.add_argument("--watch", action="store_true", help="continuously guard later cache generations")
    modes.add_argument("--install", action="store_true", help="install and start the durable user supervisor")
    modes.add_argument("--doctor", action="store_true", help="restore once and verify the durable runtime exists")
    parser.add_argument("--interval", type=float, default=DEFAULT_INTERVAL_SECONDS)
    args = parser.parse_args(argv)
    try:
        if args.watch:
            watch(interval=max(args.interval, 0.1))
            return 0
        if args.install:
            record = install()
        else:
            record = restore_once()
            if args.doctor:
                runtime = runtime_path(Path.home())
                if not runtime.is_file() or runtime.is_symlink():
                    raise GuardianError(f"durable guardian runtime is unavailable: {runtime}")
        print(json.dumps(record, sort_keys=True))
        return 0
    except GuardianBusy as exc:
        print(f"cache guardian busy: {exc}", file=sys.stderr)
        return EX_TEMPFAIL
    except (GuardianError, OSError, subprocess.SubprocessError) as exc:
        print(f"cache guardian failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

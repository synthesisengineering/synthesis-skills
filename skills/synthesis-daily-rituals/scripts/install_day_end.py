#!/usr/bin/env python3
"""Install the agent-neutral day-end launcher and macOS nudge runtime."""

from __future__ import annotations

import argparse
import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import NoReturn


LABEL = "com.synthesis.day-end-nudge"
SCRIPT_DIR = Path(__file__).resolve().parent


def fail(message: str) -> NoReturn:
    raise RuntimeError(message)


def ensure_safe_root(home: Path, runtime_root: Path) -> None:
    expected = home / ".synthesis" / "day-end"
    if runtime_root != expected:
        fail(f"runtime root must be exactly {expected}, got {runtime_root}")
    if runtime_root in {Path("/"), home, Path.cwd()}:
        fail(f"refusing protected runtime root: {runtime_root}")

    cursor = home
    for part in (".synthesis", "day-end"):
        cursor = cursor / part
        if cursor.is_symlink():
            fail(f"refusing symlinked runtime path: {cursor}")


def atomic_write(path: Path, payload: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        fail(f"refusing to replace symlinked runtime file: {path}")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
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


def install_symlink(link: Path, target: Path) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.exists() and not link.is_symlink():
        fail(f"refusing to replace non-symlink launcher: {link}")
    if link.is_symlink() and link.resolve(strict=False) == target:
        return
    temporary = link.with_name(f".{link.name}.new-{os.getpid()}")
    temporary.unlink(missing_ok=True)
    temporary.symlink_to(target)
    os.replace(temporary, link)


def plist_payload(nudge_script: Path) -> bytes:
    payload = plistlib.loads(
        (SCRIPT_DIR / f"{LABEL}.plist").read_bytes()
    )
    if payload.get("Label") != LABEL:
        fail("LaunchAgent template label does not match the installer")
    payload["ProgramArguments"] = [str(nudge_script)]
    return plistlib.dumps(payload, sort_keys=False)


def run_launchctl(plist: Path) -> None:
    domain = f"gui/{os.getuid()}"
    subprocess.run(
        ["launchctl", "bootout", domain, str(plist)],
        capture_output=True,
        check=False,
    )
    completed = subprocess.run(
        ["launchctl", "bootstrap", domain, str(plist)],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode:
        fail(
            "launchctl bootstrap failed: "
            + (completed.stderr.strip() or completed.stdout.strip())
        )


def install(agent: str | None, no_launchctl: bool) -> None:
    home = Path.home()
    runtime_root = home / ".synthesis" / "day-end"
    ensure_safe_root(home, runtime_root)

    launcher = runtime_root / "bin" / "day-end"
    nudge = runtime_root / "bin" / "day-end-nudge.sh"
    atomic_write(launcher, (SCRIPT_DIR / "day-end").read_bytes(), 0o755)
    atomic_write(nudge, (SCRIPT_DIR / "day-end-nudge.sh").read_bytes(), 0o755)

    selection_file = runtime_root / "agent-cli"
    if agent is not None or not selection_file.exists():
        atomic_write(selection_file, f"{agent or 'auto'}\n".encode(), 0o600)

    install_symlink(home / ".local" / "bin" / "day-end", launcher)

    launch_agent = home / "Library" / "LaunchAgents" / f"{LABEL}.plist"
    atomic_write(launch_agent, plist_payload(nudge), 0o644)

    if not no_launchctl:
        if sys.platform != "darwin" or shutil.which("launchctl") is None:
            fail("launchctl is required unless --no-launchctl is supplied")
        run_launchctl(launch_agent)

    print(f"installed day-end runtime: {runtime_root}")
    print(f"agent selection: {selection_file.read_text().strip()}")
    print(f"launcher: {home / '.local' / 'bin' / 'day-end'}")
    print(f"nudge: {launch_agent}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--agent",
        choices=("auto", "codex", "claude"),
        help="persist the preferred launcher; existing choice is preserved if omitted",
    )
    parser.add_argument(
        "--no-launchctl",
        action="store_true",
        help="write and verify artifacts without loading the LaunchAgent",
    )
    args = parser.parse_args()
    try:
        install(args.agent, args.no_launchctl)
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"day-end install failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

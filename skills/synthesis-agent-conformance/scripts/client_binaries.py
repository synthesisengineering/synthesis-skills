#!/usr/bin/env python3
"""Locate installed Claude Code, Codex, and Muse CLI binaries.

Cross-client verification must run from any client's shell, from cron, or
from CI. Each client's own shell puts its binary on PATH, but the other
clients' shells usually do not — the Codex CLI ships inside the ChatGPT
desktop app on macOS and is injected only into Codex-managed shells. Checks
that spawn a client binary therefore resolve it in this order:

1. An explicit environment override (``SYNTHESIS_CODEX_BIN``,
   ``SYNTHESIS_CLAUDE_BIN``, or ``SYNTHESIS_MUSE_BIN``). A set override is authoritative: an empty
   value means "treat the client as absent" (used by hermetic tests), and a
   value that does not point at an executable file resolves to nothing
   rather than falling through, so a misconfigured override fails closed
   instead of silently testing a different installation.
2. ``PATH`` via :func:`shutil.which`. Discovered Codex candidates must pass a
   bounded local ``--version`` probe: an executable launcher can outlive its CLI.
3. Documented stable install locations. These are vendor install paths, not
   version-numbered plugin caches, so consulting them as fallbacks does not
   create a dependency on client-owned cache layout.

Callers treat ``None`` as "binary unavailable" and report a structured check
failure; they never let ``FileNotFoundError`` escape as a crash.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
from pathlib import Path

ENV_OVERRIDES = {
    "claude": "SYNTHESIS_CLAUDE_BIN",
    "codex": "SYNTHESIS_CODEX_BIN",
    "muse": "SYNTHESIS_MUSE_BIN",
}

WELL_KNOWN_LOCATIONS = {
    "claude": (
        "~/.local/bin/claude",
        "/opt/homebrew/bin/claude",
        "/usr/local/bin/claude",
    ),
    "codex": (
        "~/.local/bin/codex",
        "/opt/homebrew/bin/codex",
        "/usr/local/bin/codex",
        "/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex",
        "/Applications/Codex.app/Contents/Resources/codex-cli/bin/codex",
        "/Applications/ChatGPT.app/Contents/Resources/codex",
        "/Applications/Codex.app/Contents/Resources/codex",
    ),
    "muse": (
        "~/.local/bin/muse",
        "/opt/homebrew/bin/muse",
        "/usr/local/bin/muse",
    ),
}

PROBE_TIMEOUT_SECONDS = 2.0


def _executable(path: Path) -> bool:
    return path.is_file() and os.access(path, os.X_OK)


def _codex_launcher_works(path: Path) -> bool | None:
    """Probe locally without a prompt, inherited stdin, output buffers, or retries.

    A fresh process group confines timeout cleanup to this probe and its children.
    Never perform authentication, plugin mutation, or a model request here.
    None means cleanup could not be confirmed and discovery must stop entirely.
    """
    try:
        process = subprocess.Popen(
            [str(path), "--version"], stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=(os.name == "posix"),
        )
    except OSError:
        return False
    try:
        return process.wait(timeout=PROBE_TIMEOUT_SECONDS) == 0
    except subprocess.TimeoutExpired:
        return False
    finally:
        # Also remove a launcher's surviving descendants after an early exit.
        try:
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGKILL)
            elif process.poll() is None:
                process.kill()
        except ProcessLookupError:
            pass
        except OSError:
            return None
        try:
            process.wait(timeout=1.0)
        except (subprocess.TimeoutExpired, OSError):
            return None


def resolve_client_binary(name: str, *, locations=None) -> str | None:
    """Return an executable path for ``name`` (``claude``, ``codex``, or ``muse``)."""
    override_key = ENV_OVERRIDES.get(name, "")
    if override_key and override_key in os.environ:
        override = os.environ[override_key]
        if not override:
            return None
        path = Path(override).expanduser().absolute()
        return str(path) if _executable(path) else None
    found = shutil.which(name)
    candidates = ([found] if found else []) + list(
        WELL_KNOWN_LOCATIONS.get(name, ()) if locations is None else locations
    )
    seen: set[str] = set()
    for candidate in candidates:
        path = Path(candidate).expanduser().absolute()
        identity = os.path.realpath(path)
        if identity in seen:
            continue
        seen.add(identity)
        if not _executable(path):
            continue
        if name == "codex":
            healthy = _codex_launcher_works(path)
            if healthy is None:
                return None  # A surviving probe must not be hidden by a fallback.
            if not healthy:
                continue
        return str(path)
    return None


def missing_binary_detail(name: str) -> str:
    """Uniform detail string for a structured check failure."""
    override_key = ENV_OVERRIDES.get(name, f"SYNTHESIS_{name.upper()}_BIN")
    return (
        f"{name} usable binary not found on PATH or in documented install locations; "
        f"set {override_key} to the CLI path if it is installed elsewhere"
    )


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("client", choices=tuple(ENV_OVERRIDES))
    selected = resolve_client_binary(parser.parse_args().client)
    if selected:
        print(selected)

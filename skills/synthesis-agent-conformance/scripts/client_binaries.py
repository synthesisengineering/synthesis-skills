#!/usr/bin/env python3
"""Locate installed Claude Code and Codex CLI binaries.

Cross-client verification must run from either client's shell, from cron, or
from CI. Each client's own shell puts its binary on PATH, but the other
client's shell usually does not — the Codex CLI ships inside the ChatGPT
desktop app on macOS and is injected only into Codex-managed shells. Checks
that spawn a client binary therefore resolve it in this order:

1. An explicit environment override (``SYNTHESIS_CODEX_BIN`` or
   ``SYNTHESIS_CLAUDE_BIN``). A set override is authoritative: an empty
   value means "treat the client as absent" (used by hermetic tests), and a
   value that does not point at an executable file resolves to nothing
   rather than falling through, so a misconfigured override fails closed
   instead of silently testing a different installation.
2. ``PATH`` via :func:`shutil.which`.
3. Documented stable install locations. These are vendor install paths, not
   version-numbered plugin caches, so consulting them as fallbacks does not
   create a dependency on client-owned cache layout.

Callers treat ``None`` as "binary unavailable" and report a structured check
failure; they never let ``FileNotFoundError`` escape as a crash.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

ENV_OVERRIDES = {
    "claude": "SYNTHESIS_CLAUDE_BIN",
    "codex": "SYNTHESIS_CODEX_BIN",
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
        "/Applications/ChatGPT.app/Contents/Resources/codex",
    ),
}


def _executable(path: Path) -> bool:
    return path.is_file() and os.access(path, os.X_OK)


def resolve_client_binary(name: str) -> str | None:
    """Return an executable path for ``name`` (``claude`` or ``codex``)."""
    override_key = ENV_OVERRIDES.get(name, "")
    if override_key and override_key in os.environ:
        override = os.environ[override_key]
        if not override:
            return None
        path = Path(override).expanduser()
        return str(path) if _executable(path) else None
    found = shutil.which(name)
    if found:
        return found
    for candidate in WELL_KNOWN_LOCATIONS.get(name, ()):
        path = Path(candidate).expanduser()
        if _executable(path):
            return str(path)
    return None


def missing_binary_detail(name: str) -> str:
    """Uniform detail string for a structured check failure."""
    override_key = ENV_OVERRIDES.get(name, f"SYNTHESIS_{name.upper()}_BIN")
    return (
        f"{name} binary not found on PATH or in documented install locations; "
        f"set {override_key} to the CLI path if it is installed elsewhere"
    )

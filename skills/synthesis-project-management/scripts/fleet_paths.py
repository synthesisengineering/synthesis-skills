#!/usr/bin/env python3
"""Fleet ``~``-normalization: expand at load, fail closed in the doctor.

Design: 2026-09-19-fleet-architecture.md section 6. No persisted fleet-synced
config may contain a literal home path (``/Users/<name>/`` or any absolute
path under the current home). Consumers expand ``~``/``$HOME`` at load; the
doctor gate fails on any unexpanded absolute home path in a synced file,
naming file, line, and value.

This module holds the shared primitives. Each consumer wires them into its
own loader:

- git-hook-config ``coordination_board`` (synthesis-git-hooks ``_load_config``)
- ritual workers ``artifact_dir`` (synthesis-daily-rituals ``ritual_workers``)
- account-routing workspace keys (``route_account_workspace`` below)
- checkpoint ``recipient_index`` (synthesis-checkpoint ``refresh``)
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# Absolute home roots that must never appear literally in synced files: any
# macOS /Users/<name> or Linux /home/<name> prefix, plus the current home
# itself (which covers nonstandard locations on either platform).
HOME_ROOT_PREFIXES = ("/Users/", "/home/")


def expand_home(value: str) -> str:
    """Expand a ``~``- or ``$HOME``-rooted persisted path for this Mac."""
    return os.path.expandvars(os.path.expanduser(value))


def _home_prefixes() -> tuple[str, ...]:
    home = str(Path.home())
    return (home + os.sep, home) + HOME_ROOT_PREFIXES


def is_unexpanded_home_path(value: object) -> bool:
    """Whether a persisted value is a literal absolute home path.

    ``~``-prefixed and ``$HOME``-relative values pass; so does anything that
    is not an absolute path at all. A literal ``/Users/<name>/...``,
    ``/home/<name>/...``, or current-home-prefixed absolute path fails.
    """
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text or text.startswith("~") or text.startswith("$HOME") or text.startswith("${HOME}"):
        return False
    if not os.path.isabs(text):
        return False
    return text.startswith(_home_prefixes())


def route_account_workspace(
    workspaces: dict, candidate: str
) -> tuple[str, object] | None:
    """Route a workspace path through account-routing keys, expanded first.

    ``workspaces`` maps persisted workspace keys (``~``-rooted after
    normalization; absolute in legacy files) to route records. Both the keys
    and the candidate expand before compare, so an exact-match-on-unexpanded
    regression cannot silently stop routing. Returns the matched
    ``(key, record)`` pair for the longest-prefix match, or None.
    """
    if not isinstance(workspaces, dict) or not isinstance(candidate, str):
        return None
    expanded_candidate = os.path.normpath(expand_home(candidate.strip()))
    best: tuple[str, object] | None = None
    best_length = -1
    for key, record in workspaces.items():
        if not isinstance(key, str) or not key.strip():
            continue
        expanded_key = os.path.normpath(expand_home(key.strip()))
        if expanded_candidate != expanded_key and not expanded_candidate.startswith(
            expanded_key + os.sep
        ):
            continue
        if len(expanded_key) > best_length:
            best = (key, record)
            best_length = len(expanded_key)
    return best


@dataclass(frozen=True)
class UnexpandedPath:
    """One doctor-gate hit: file, line, and offending value."""

    path: str
    line: int
    value: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: unexpanded absolute home path: {self.value}"


def _home_path_tokens(line: str, home: str) -> list[str]:
    tokens = []
    for raw in line.replace(",", " ").replace(":", " ").split():
        token = raw.strip().strip("\"'")
        if is_unexpanded_home_path(token):
            tokens.append(token)
    # Absolute home paths containing spaces survive the split above only as
    # fragments; catch the full span with a prefix scan as well.
    for prefix in (home + os.sep, "/Users/", "/home/"):
        start = 0
        while True:
            index = line.find(prefix, start)
            if index < 0:
                break
            end = index + len(prefix)
            while end < len(line) and line[end] not in "\"'\n":
                end += 1
            span = line[index:end].strip().rstrip(",")
            if span and span not in tokens and is_unexpanded_home_path(span):
                tokens.append(span)
            start = index + len(prefix)
    return tokens


def scan_file(path: Path) -> list[UnexpandedPath]:
    """Scan one synced file for literal absolute home paths, line by line."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    except OSError as exc:
        raise FleetPathsError(f"fleet doctor cannot read {path}: {exc}")
    home = str(Path.home())
    hits: list[UnexpandedPath] = []
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        for token in _home_path_tokens(line, home):
            hits.append(UnexpandedPath(str(path), number, token))
    return hits


class FleetPathsError(ValueError):
    """A fleet path gate failure (unreadable file or unexpanded path)."""


SYNCED_PATH_FILES = (
    "git-hook-config.yaml",
    "ritual/workers.yaml",
    "account-routing/workspaces.json",
    "checkpoint/active-campaign.json",
)


def check_synced_root(root: Path) -> list[UnexpandedPath]:
    """Run the doctor gate over the fleet-synced path-bearing files.

    Missing files are skipped (nothing persisted, nothing to fail); every
    present file must be free of literal absolute home paths.
    """
    hits: list[UnexpandedPath] = []
    for name in SYNCED_PATH_FILES:
        hits.extend(scan_file(Path(root) / name))
    return hits


def format_gate_report(hits: list[UnexpandedPath]) -> str:
    if not hits:
        return "PASS fleet-paths: no unexpanded absolute home paths in synced files"
    lines = ["FAIL fleet-paths: unexpanded absolute home paths in synced files:"]
    lines.extend(f"  {hit}" for hit in hits)
    return "\n".join(lines)

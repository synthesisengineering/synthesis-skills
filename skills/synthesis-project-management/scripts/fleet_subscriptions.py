#!/usr/bin/env python3
"""Machine workspace subscriptions: which areas a Mac may commit.

A fleet machine subscribes to workspace areas (repos, subtrees). The commit
gate (``coordination.py check-staged``) refuses staged paths no subscription
covers, naming the machine and the needed subscription; an explicit
``--override-subscription`` reason escapes once and is logged on the board.

Registry: ``~/.synthesis/fleet/subscriptions.json`` (``SYNTHESIS_FLEET_DIR``
overrides the fleet dir in tests and enrollment)::

    {"schema_version": 1,
     "subscriptions": {"<machine-id>": {"label": "mac-a",
                                        "areas": ["~/workspaces/personal/**"]}}}

Enforcement applies once the registry exists. A missing registry means the
fleet has not enrolled subscriptions yet (single-machine legacy) and the
gate passes — but a present registry with an unlisted machine, or staged
paths outside every subscribed area, fails closed. Patterns use the same
segment-glob semantics as board claims (``~``/``$HOME`` expand at load;
repo-relative patterns resolve against the committing repository).
"""
from __future__ import annotations

import fnmatch
import json
import os
from dataclasses import dataclass
from pathlib import Path

import fleet_identity as _identity

SUBSCRIPTIONS_NAME = "subscriptions.json"
SUBSCRIPTIONS_SCHEMA_VERSION = 1


class FleetSubscriptionError(ValueError):
    """A malformed subscription registry or an unusable pattern."""


def subscriptions_path(directory: Path | None = None) -> Path:
    return (_identity.fleet_dir() if directory is None else Path(directory)) / (
        SUBSCRIPTIONS_NAME
    )


def validate_registry(document: object) -> list[str]:
    """Every shape problem in a subscriptions document; empty means valid."""
    if not isinstance(document, dict):
        return ["fleet subscriptions must be a JSON object"]
    problems = []
    if document.get("schema_version") != SUBSCRIPTIONS_SCHEMA_VERSION:
        problems.append(
            "fleet subscriptions schema_version must be "
            f"{SUBSCRIPTIONS_SCHEMA_VERSION}"
        )
    subscriptions = document.get("subscriptions")
    if not isinstance(subscriptions, dict):
        return problems + ["fleet subscriptions must map machine-ids to entries"]
    for machine_id, entry in subscriptions.items():
        where = f"machine {machine_id}"
        if not isinstance(entry, dict):
            problems.append(f"{where}: entry must be an object")
            continue
        if not isinstance(entry.get("label"), str) or not entry["label"].strip():
            problems.append(f"{where}: label must be a non-empty string")
        areas = entry.get("areas")
        if not isinstance(areas, list) or not areas:
            problems.append(f"{where}: areas must be a non-empty list")
            continue
        for area in areas:
            if not isinstance(area, str) or not area.strip():
                problems.append(f"{where}: every area must be a non-empty string")
    return problems


def read_registry(directory: Path | None = None) -> dict | None:
    """The subscriptions registry, or None when subscriptions unenrolled.

    A missing file is not an error (see module docstring); a present but
    malformed file fails closed.
    """
    path = subscriptions_path(directory)
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise FleetSubscriptionError(
            f"fleet subscriptions unreadable: {path}: {exc}"
        )
    try:
        document = json.loads(raw)
    except ValueError as exc:
        raise FleetSubscriptionError(
            f"fleet subscriptions are not JSON: {path}: {exc}"
        )
    problems = validate_registry(document)
    if problems:
        raise FleetSubscriptionError(
            f"fleet subscriptions invalid: {path}: {'; '.join(problems)}"
        )
    return document


def write_registry(document: dict, directory: Path | None = None) -> Path:
    """Persist a validated subscriptions registry."""
    problems = validate_registry(document)
    if problems:
        raise FleetSubscriptionError(
            "refusing to write invalid fleet subscriptions: "
            + "; ".join(problems)
        )
    path = subscriptions_path(directory)
    path.parent.mkdir(parents=True, exist_ok=True)
    staging = path.with_suffix(".json.tmp")
    staging.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    os.replace(staging, path)
    return path


def areas_for(machine_id: str, directory: Path | None = None) -> list[str] | None:
    """This machine's subscribed areas; None when subscriptions unenrolled.

    Raises FleetSubscriptionError when the registry exists but names no
    entry for this machine.
    """
    document = read_registry(directory)
    if document is None:
        return None
    entry = document["subscriptions"].get(machine_id)
    if not isinstance(entry, dict):
        raise FleetSubscriptionError(
            f"machine {machine_id} holds no fleet workspace subscription; "
            "enroll one in subscriptions.json before committing"
        )
    return list(entry["areas"])


def _glob_matches(pattern: str, candidate: str) -> bool:
    """Segment-glob match; ``*`` never crosses ``/`` (mirrors check-staged).

    Deliberately duplicated from coordination's matcher: this module must
    stay importable from coordination without a dependency cycle.
    """
    pattern_parts = Path(pattern).parts
    candidate_parts = Path(candidate).parts
    cache: dict[tuple[int, int], bool] = {}

    def matches(pattern_index: int, candidate_index: int) -> bool:
        key = (pattern_index, candidate_index)
        if key in cache:
            return cache[key]
        if pattern_index == len(pattern_parts):
            result = candidate_index == len(candidate_parts)
        elif pattern_parts[pattern_index] == "**":
            result = matches(pattern_index + 1, candidate_index) or (
                candidate_index < len(candidate_parts)
                and matches(pattern_index, candidate_index + 1)
            )
        else:
            result = (
                candidate_index < len(candidate_parts)
                and fnmatch.fnmatchcase(
                    candidate_parts[candidate_index],
                    pattern_parts[pattern_index],
                )
                and matches(pattern_index + 1, candidate_index + 1)
            )
        cache[key] = result
        return result

    return matches(0, 0)


def pattern_authorizes_path(
    pattern: str, repository: Path, staged_path: str
) -> bool:
    """Whether one subscription pattern covers one staged path."""
    raw = (pattern or "").strip().replace("/**", "/\0GLOB\0").replace(
        "**/", "\0GLOB\0/"
    )
    import re as _re

    raw = _re.sub(r"\*\*(.+?)\*\*", r"\1", raw)
    raw = _re.sub(r"`(.+?)`", r"\1", raw).replace("\0GLOB\0", "**").strip()
    if not raw:
        return False
    expanded = os.path.expandvars(os.path.expanduser(raw))
    candidate = Path(expanded)
    if not candidate.is_absolute():
        parts = candidate.parts
        base = (
            repository.parent
            if parts and parts[0] == repository.name
            else repository
        )
        candidate = base / candidate
    absolute = os.path.realpath(candidate)
    staged = os.path.realpath(repository / staged_path)
    if any(token in absolute for token in ("*", "?", "[")):
        return _glob_matches(absolute, staged)
    boundary = Path(absolute)
    staged_full = Path(staged)
    if raw.endswith("/") or boundary.is_dir():
        return staged_full == boundary or boundary in staged_full.parents
    return staged_full == boundary


def unsubscribed_paths(
    areas: list[str], repository: Path, staged_paths: list[str]
) -> list[str]:
    """Staged paths no subscribed area covers, in staged order."""
    return [
        path
        for path in staged_paths
        if not any(
            pattern_authorizes_path(area, repository, path) for area in areas
        )
    ]


@dataclass(frozen=True)
class SubscriptionDecision:
    """The gate verdict for one commit on one machine."""

    enforced: bool
    """False only when no subscriptions registry exists (unenrolled fleet)."""
    machine_id: str
    machine_label: str
    unsubscribed: tuple[str, ...]
    """Staged paths outside every subscribed area; empty means covered."""
    unlisted_machine: bool = False
    """True when the registry exists but names no entry for this machine."""

    @property
    def allowed(self) -> bool:
        return not self.enforced or not self.unsubscribed

    def refusal_detail(self) -> str:
        """The loud refusal: machine + needed subscription, no guessing."""
        paths = ", ".join(self.unsubscribed)
        if self.unlisted_machine:
            return (
                f"machine '{self.machine_label}' ({self.machine_id}) is not "
                f"listed in subscriptions.json: no workspace area is "
                f"subscribed, so staged paths are refused: {paths}. "
                f"Needed subscription: enroll machine '{self.machine_label}' "
                f"with an area covering {paths}, or re-run with "
                "--override-subscription '<reason>' to log a one-time "
                "escape on the board."
            )
        return (
            f"machine '{self.machine_label}' ({self.machine_id}) holds no "
            f"workspace subscription covering staged paths: {paths}. "
            f"Needed subscription: add an area covering {paths} to "
            f"subscriptions.json for machine '{self.machine_label}', or "
            "re-run with --override-subscription '<reason>' to log a "
            "one-time escape on the board."
        )


def decide(
    *,
    machine_id: str,
    machine_label: str,
    repository: Path,
    staged_paths: list[str],
    directory: Path | None = None,
) -> SubscriptionDecision:
    """The subscription verdict for one commit's staged paths.

    Raises FleetSubscriptionError only when the registry is present but
    malformed or unreadable (fail closed). An unlisted machine is a refused
    decision, not an exception, so the gate names it uniformly.
    """
    document = read_registry(directory)
    if document is None:
        return SubscriptionDecision(False, machine_id, machine_label, ())
    entry = document["subscriptions"].get(machine_id)
    if not isinstance(entry, dict):
        return SubscriptionDecision(
            True, machine_id, machine_label, tuple(staged_paths), True
        )
    return SubscriptionDecision(
        True,
        machine_id,
        machine_label,
        tuple(unsubscribed_paths(list(entry["areas"]), repository, staged_paths)),
    )

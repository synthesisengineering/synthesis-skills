#!/usr/bin/env python3
"""Fleet machine identity: one stable UUID4 per Mac plus the shared registry.

Design: 2026-09-19-fleet-architecture.md section 1. Each Mac mints its own
machine-id once (``~/.synthesis/fleet/machine-id``, mode 0600) and never
transports it to another Mac. The fleet registry (``machines.json``, schema 1,
copied from the local-models shape) lists every enrolled machine and is the
syncable person-level state; the machine-id file itself is per-machine.

Never-transport rules, enforced by construction and covered by tests:

- minting refuses to overwrite an existing machine-id;
- registry read/write never creates, reads, or modifies the machine-id file;
- no API writes caller-supplied bytes as the local machine-id (the only
  writer generates a fresh UUID4).
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

FLEET_DIR_ENV = "SYNTHESIS_FLEET_DIR"
MACHINE_ID_NAME = "machine-id"
REGISTRY_NAME = "machines.json"
REGISTRY_SCHEMA_VERSION = 1
MACHINE_ROLES = ("primary", "secondary")


class FleetIdentityError(ValueError):
    """A malformed machine-id file or fleet registry."""


def fleet_dir() -> Path:
    """The fleet state directory, overridable for tests and enrollment."""
    override = os.environ.get(FLEET_DIR_ENV, "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".synthesis" / "fleet"


def fleet_dir_for_board(board: Path) -> Path:
    """The fleet directory belonging to a board, for mutation scoping.

    A board mutation must read the machine identity that belongs to the
    board it mutates — never the ambient home's enrollment. The live
    layout keeps ``coordination/active-sessions.md`` next to ``fleet/``;
    any other layout (tests, alternate homes) scopes to a ``fleet/``
    sibling of the board file, which is simply unenrolled when absent.
    """
    parent = Path(board).expanduser().parent
    if parent.name == "coordination":
        return parent.parent / "fleet"
    return parent / "fleet"


def machine_id_path(directory: Path | None = None) -> Path:
    return (directory or fleet_dir()) / MACHINE_ID_NAME


def registry_path(directory: Path | None = None) -> Path:
    return (directory or fleet_dir()) / REGISTRY_NAME


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _valid_uuid4(value: str) -> bool:
    try:
        parsed = uuid.UUID(value.strip())
    except (ValueError, AttributeError, TypeError):
        return False
    return parsed.version == 4


def read_machine_id(directory: Path | None = None) -> str | None:
    """This Mac's machine-id, or None when it has never minted one."""
    path = machine_id_path(directory)
    try:
        value = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise FleetIdentityError(f"fleet machine-id unreadable: {path}: {exc}")
    if not _valid_uuid4(value):
        raise FleetIdentityError(f"fleet machine-id is not a UUID4: {path}")
    return value


def mint_machine_id(directory: Path | None = None) -> str:
    """Mint this Mac's stable machine-id exactly once.

    Refuses to overwrite an existing file: a second identity for one Mac
    would orphan every board row and seat the first one owns.
    """
    path = machine_id_path(directory)
    if path.exists() or path.is_symlink():
        raise FleetIdentityError(
            f"fleet machine-id already exists: {path}; refusing to overwrite"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    value = str(uuid.uuid4())
    descriptor = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(value + "\n")
    except BaseException:
        try:
            path.unlink()
        except OSError:
            pass
        raise
    os.chmod(path, 0o600)
    return value


def empty_registry() -> dict:
    return {"schema_version": REGISTRY_SCHEMA_VERSION, "machines": {}}


def _entry_problems(machine_id: str, entry: object) -> list[str]:
    if not isinstance(entry, dict):
        return [f"machine {machine_id}: entry must be an object"]
    problems = []
    if not isinstance(entry.get("label"), str) or not entry["label"].strip():
        problems.append(f"machine {machine_id}: label must be a non-empty string")
    if entry.get("role") not in MACHINE_ROLES:
        problems.append(
            f"machine {machine_id}: role must be one of {list(MACHINE_ROLES)}"
        )
    for field in ("enrolled_at", "last_seen"):
        if not isinstance(entry.get(field), str) or not entry[field].strip():
            problems.append(f"machine {machine_id}: {field} must be set")
    if not isinstance(entry.get("environments"), list) or not entry["environments"]:
        problems.append(f"machine {machine_id}: environments must be a non-empty list")
    if "retired_at" not in entry or (
        entry["retired_at"] is not None and not isinstance(entry["retired_at"], str)
    ):
        problems.append(f"machine {machine_id}: retired_at must be null or a string")
    return problems


def validate_registry(document: object) -> list[str]:
    """Every shape problem in a registry document; empty means valid."""
    if not isinstance(document, dict):
        return ["fleet registry must be a JSON object"]
    problems = []
    if document.get("schema_version") != REGISTRY_SCHEMA_VERSION:
        problems.append(
            "fleet registry schema_version must be "
            f"{REGISTRY_SCHEMA_VERSION}"
        )
    machines = document.get("machines")
    if not isinstance(machines, dict):
        return problems + ["fleet registry machines must be an object"]
    for machine_id, entry in machines.items():
        if not _valid_uuid4(str(machine_id)):
            problems.append(f"fleet registry key is not a UUID4: {machine_id}")
        problems.extend(_entry_problems(str(machine_id), entry))
    live = [
        entry
        for entry in machines.values()
        if isinstance(entry, dict) and entry.get("retired_at") is None
    ]
    primaries = [entry for entry in live if entry.get("role") == "primary"]
    if live and len(primaries) != 1:
        problems.append("fleet registry must name exactly one primary")
    return problems


def read_registry(directory: Path | None = None) -> dict:
    """The fleet registry; an empty registry when nothing is enrolled yet."""
    path = registry_path(directory)
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return empty_registry()
    except OSError as exc:
        raise FleetIdentityError(f"fleet registry unreadable: {path}: {exc}")
    try:
        document = json.loads(raw)
    except ValueError as exc:
        raise FleetIdentityError(f"fleet registry is not JSON: {path}: {exc}")
    problems = validate_registry(document)
    if problems:
        raise FleetIdentityError(
            f"fleet registry invalid: {path}: {'; '.join(problems)}"
        )
    return document


def write_registry(document: dict, directory: Path | None = None) -> Path:
    """Persist a validated registry; refuses invalid documents outright."""
    problems = validate_registry(document)
    if problems:
        raise FleetIdentityError(
            f"refusing to write an invalid fleet registry: {'; '.join(problems)}"
        )
    path = registry_path(directory)
    path.parent.mkdir(parents=True, exist_ok=True)
    staging = path.with_suffix(".json.tmp")
    staging.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    os.replace(staging, path)
    return path


def enroll_self(
    *,
    label: str,
    role: str,
    environments: list[str] | None = None,
    directory: Path | None = None,
    now: str | None = None,
    hostname: str | None = None,
    label_source: str | None = None,
) -> dict:
    """Record this Mac's minted identity in the registry.

    Minting (``mint_machine_id``) always precedes enrollment: the registry
    entry keys on the local machine-id file, never on a transported value.
    Re-enrollment refreshes label, role, environments, and last_seen while
    preserving the original enrolled_at. ``hostname``/``label_source``
    record how the label was chosen so a later rename can be offered
    (never forced); provided values win, previous ones are preserved.
    """
    machine_id = read_machine_id(directory)
    if machine_id is None:
        raise FleetIdentityError(
            "cannot enroll before minting: no fleet machine-id on this Mac"
        )
    if not label.strip():
        raise FleetIdentityError("fleet enrollment requires a non-empty label")
    if role not in MACHINE_ROLES:
        raise FleetIdentityError(f"fleet role must be one of {list(MACHINE_ROLES)}")
    moment = now or utcnow_iso()
    document = read_registry(directory)
    previous = document["machines"].get(machine_id)
    if isinstance(previous, dict) and previous.get("retired_at") is not None:
        raise FleetIdentityError(
            f"machine {machine_id} is retired; re-enrollment needs a fresh identity"
        )
    entry: dict = {
        "label": label.strip(),
        "enrolled_at": (
            previous.get("enrolled_at")
            if isinstance(previous, dict) and previous.get("enrolled_at")
            else moment
        ),
        "last_seen": moment,
        "role": role,
        "environments": list(environments) if environments else ["default"],
        "retired_at": None,
    }
    previous_hostname = (
        previous.get("hostname") if isinstance(previous, dict) else None
    )
    previous_source = (
        previous.get("label_source") if isinstance(previous, dict) else None
    )
    if hostname is not None:
        entry["hostname"] = hostname
    elif isinstance(previous_hostname, str) and previous_hostname:
        entry["hostname"] = previous_hostname
    if label_source is not None:
        entry["label_source"] = label_source
    elif isinstance(previous_source, str) and previous_source:
        entry["label_source"] = previous_source
    document["machines"][machine_id] = entry
    write_registry(document, directory)
    return document["machines"][machine_id]


def touch_last_seen(
    directory: Path | None = None, *, now: str | None = None
) -> dict | None:
    """Refresh this Mac's registry last_seen; None when not enrolled."""
    machine_id = read_machine_id(directory)
    if machine_id is None:
        return None
    document = read_registry(directory)
    entry = document["machines"].get(machine_id)
    if not isinstance(entry, dict) or entry.get("retired_at") is not None:
        return None
    entry["last_seen"] = now or utcnow_iso()
    write_registry(document, directory)
    return entry


def label_for(machine_id: str, directory: Path | None = None) -> str:
    """The registry label for a machine-id, or the id itself when unknown."""
    try:
        document = read_registry(directory)
    except FleetIdentityError:
        return machine_id
    entry = document.get("machines", {}).get(machine_id)
    if isinstance(entry, dict) and entry.get("label"):
        return str(entry["label"])
    return machine_id

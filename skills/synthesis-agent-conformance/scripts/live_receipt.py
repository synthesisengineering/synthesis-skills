#!/usr/bin/env python3
"""Shared validation for client-owned SessionStart transcript evidence."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path


MAX_BINDING_LINES = 1_000
RECEIPT_CLIENTS = {"claude", "codex"}


def latest_receipt_paths(destination: Path, client: str) -> tuple[Path, Path]:
    """Return the generic and client-specific latest receipt paths."""
    if client not in RECEIPT_CLIENTS:
        raise ValueError(f"unsupported receipt client: {client}")
    suffix = f"-{client}"
    generic = destination
    if destination.stem.endswith(suffix):
        generic = destination.with_name(
            f"{destination.stem[: -len(suffix)]}{destination.suffix}"
        )
    client_path = generic.with_name(
        f"{generic.stem}-{client}{generic.suffix}"
    )
    return generic, client_path


def receipt_registry_root(latest_receipt: Path, client: str) -> Path:
    """Return the event registry shared by a client's latest receipt pointer."""
    generic, _ = latest_receipt_paths(latest_receipt, client)
    return generic.parent / f"{generic.stem}-events"


def receipt_event_path(
    latest_receipt: Path,
    *,
    client: str,
    session_id: str,
    event_id: str,
) -> Path:
    """Return the immutable path for one genuine SessionStart event."""
    if client not in RECEIPT_CLIENTS:
        raise ValueError(f"unsupported receipt client: {client}")
    try:
        uuid.UUID(session_id)
        uuid.UUID(event_id)
    except ValueError as exc:
        raise ValueError("receipt session and event ids must be UUIDs") from exc
    return (
        receipt_registry_root(latest_receipt, client)
        / client
        / session_id
        / f"{event_id}.json"
    )


def validate_receipt_event_directory(
    latest_receipt: Path,
    client: str,
    session_id: str,
) -> Path:
    """Reject symlinked or wrongly typed registry ancestors."""
    try:
        uuid.UUID(session_id)
    except ValueError as exc:
        raise ValueError(f"invalid {client} session id: {session_id}") from exc
    root = receipt_registry_root(latest_receipt, client)
    directory = root / client / session_id
    for path in (root, root / client, directory):
        if path.exists() and (path.is_symlink() or not path.is_dir()):
            raise ValueError(f"receipt registry path is unsafe: {path}")
    return directory


def receipt_recorded_order(
    payload: dict[str, object], path: Path
) -> tuple[datetime, str]:
    recorded_at = payload.get("recorded_at")
    event_id = str(payload.get("receipt_event_id") or "")
    try:
        recorded = datetime.fromisoformat(str(recorded_at))
        if recorded.tzinfo is None:
            recorded = recorded.replace(tzinfo=timezone.utc)
        if event_id:
            uuid.UUID(event_id)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid receipt ordering fields: {path}") from exc
    return recorded.astimezone(timezone.utc), event_id


def session_receipt_path(
    latest_receipt: Path,
    client: str,
    session_id: str,
    *,
    expected_plugin_version: str | None = None,
    expected_plugin_root: Path | None = None,
) -> Path | None:
    """Resolve the newest preserved event for one exact client session.

    The latest pointer remains a current-health cache.  The event registry is
    the durable runtime evidence. When a source version or enabled plugin root
    is supplied, selection stays within that exact release identity before
    choosing the newest resume event. A matching legacy latest receipt is
    accepted only as a migration fallback for receipts created before the
    registry.
    """
    if client not in RECEIPT_CLIENTS:
        raise ValueError(f"unsupported receipt client: {client}")
    try:
        uuid.UUID(session_id)
    except ValueError as exc:
        raise ValueError(f"invalid {client} session id: {session_id}") from exc

    directory = validate_receipt_event_directory(
        latest_receipt, client, session_id
    )
    if directory.exists():
        candidates: list[tuple[tuple[datetime, str], Path]] = []
        for path in sorted(directory.glob("*.json")):
            if path.is_symlink() or not path.is_file():
                raise ValueError(f"receipt event is unsafe: {path}")
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise ValueError(f"receipt event is unreadable: {path}") from exc
            if not isinstance(payload, dict):
                raise ValueError(f"receipt event is not an object: {path}")
            if (
                payload.get("client") != client
                or payload.get("session_id") != session_id
                or path.stem != str(payload.get("receipt_event_id") or "")
            ):
                raise ValueError(f"receipt event identity mismatch: {path}")
            if (
                expected_plugin_version is not None
                and payload.get("plugin_version") != expected_plugin_version
            ):
                continue
            if expected_plugin_root is not None:
                actual_root_text = payload.get("plugin_root")
                if not isinstance(actual_root_text, str) or not actual_root_text:
                    continue
                try:
                    actual_root = Path(actual_root_text).resolve()
                    required_root = expected_plugin_root.resolve()
                except OSError as exc:
                    raise ValueError(
                        f"receipt event plugin root is invalid: {path}"
                    ) from exc
                if actual_root != required_root:
                    continue
            candidates.append((receipt_recorded_order(payload, path), path))
        if candidates:
            return max(candidates)[1]

    if latest_receipt.is_symlink():
        raise ValueError(f"latest receipt is unsafe: {latest_receipt}")
    try:
        legacy = json.loads(latest_receipt.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        raise ValueError(f"latest receipt is unreadable: {latest_receipt}") from exc
    if not isinstance(legacy, dict):
        raise ValueError(f"latest receipt is not an object: {latest_receipt}")
    legacy_matches = (
        legacy.get("client") == client
        and legacy.get("session_id") == session_id
        and (
            expected_plugin_version is None
            or legacy.get("plugin_version") == expected_plugin_version
        )
    )
    if legacy_matches and expected_plugin_root is not None:
        legacy_root = legacy.get("plugin_root")
        if not isinstance(legacy_root, str) or not legacy_root:
            legacy_matches = False
        try:
            if legacy_matches:
                legacy_matches = (
                    Path(legacy_root).resolve() == expected_plugin_root.resolve()
                )
        except OSError as exc:
            raise ValueError(
                f"latest receipt plugin root is invalid: {latest_receipt}"
            ) from exc
    if legacy_matches:
        return latest_receipt
    return None


def claude_root_transcript_path(
    transcript: Path, transcript_root: Path, session_id: str
) -> bool:
    """Return whether a path is Claude's canonical root-session transcript.

    Root transcripts use ``projects/<encoded-cwd>/<session-id>.jsonl``.
    Claude subagent transcripts also carry the parent session UUID, so root
    containment plus a matching JSON field is not sufficient provenance.
    """
    if not transcript.is_absolute() or not session_id:
        return False
    root = transcript_root.expanduser().absolute()
    candidate = transcript.expanduser().absolute()
    try:
        relative = candidate.relative_to(root)
    except ValueError:
        return False
    if (
        len(relative.parts) != 3
        or relative.parts[0] != "projects"
        or any(part in {".", ".."} for part in relative.parts)
        or relative.parts[-1] != f"{session_id}.jsonl"
    ):
        return False
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            return False
    try:
        candidate.resolve(strict=False).relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    return True


def transcript_binding_state(
    transcript: Path, client: str, session_id: str
) -> str:
    """Return ``bound``, ``pending``, ``conflicting``, or ``invalid``.

    ``pending`` covers a transcript Claude has not created or populated yet.
    Once a transcript declares any different session id, the state is
    ``conflicting`` and must not be preserved as genuine evidence.
    """
    if not transcript.exists():
        return "pending"
    if transcript.is_symlink() or not transcript.is_file():
        return "invalid"
    declared: set[str] = set()
    try:
        with transcript.open(encoding="utf-8") as handle:
            for index, line in enumerate(handle):
                if index >= MAX_BINDING_LINES:
                    break
                try:
                    payload = json.loads(line)
                except (TypeError, ValueError):
                    continue
                if not isinstance(payload, dict):
                    continue
                if client == "codex":
                    metadata = payload.get("payload")
                    if payload.get("type") == "session_meta" and isinstance(
                        metadata, dict
                    ):
                        declared.update(
                            value
                            for value in (
                                str(metadata.get("id") or ""),
                                str(metadata.get("session_id") or ""),
                            )
                            if value
                        )
                elif client == "claude":
                    value = str(payload.get("sessionId") or "")
                    if value:
                        declared.add(value)
    except (OSError, UnicodeError):
        return "invalid"
    if declared == {session_id}:
        return "bound"
    if declared:
        return "conflicting"
    return "pending"


def transcript_binds_session(
    transcript: Path, client: str, session_id: str
) -> bool:
    """Return whether a client transcript declares the claimed session id.

    Both clients write the binding at the start of their JSONL transcript.
    The bounded scan fails closed on malformed or unexpectedly shaped files
    without reading an arbitrarily large transcript during SessionStart.
    """
    return transcript_binding_state(transcript, client, session_id) == "bound"

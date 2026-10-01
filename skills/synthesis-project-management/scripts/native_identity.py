"""Canonical native transcript-to-seat identity; no project or execution imports."""
from __future__ import annotations
import os
import sys
import uuid
from pathlib import Path
from typing import Any

class ProjectStateError(RuntimeError):
    """A required evidence source was unreadable or mutually inconsistent."""

def row_for_event(
    rows: list[dict[str, str]],
    payload: dict[str, Any],
    board: Path | None = None,
    *, _observer=None,
) -> dict[str, str] | None:
    """Supported entry point (ID-2, 2026-09-21): the private control
    plane resolves native claims through this helper."""
    # Delivery selectors and coordination UUIDs are not native identity.
    # Desktop claims store a host id; their existing sidecar binds that host
    # to the transcript UUID that Stop receives. Never infer that association
    # from a caller-supplied ccd: override or a payload task_id.
    _observer = _observer or observer_native_identity
    configured = os.environ.get("SYNTHESIS_CLIENT_SESSION_REF", "").strip()
    native = payload.get("session_id")
    if configured.startswith(("cc:", "codex:", "muse:")) and (
        not isinstance(native, str)
        or not native
        or configured.split(":", 1)[1] != native
    ):
        raise ProjectStateError(
            "native lifecycle identity conflicts with the configured client reference; refusing a foreign checkpoint"
        )
    if not isinstance(native, str) or not native:
        return None
    native_refs = {f"cc:{native}", f"codex:{native}", f"muse:{native}"}
    matches = []
    for row in rows:
        if row.get("status", "").lower() != "active":
            continue
        client_ref = row.get("client session ref", "")
        matched = client_ref in native_refs
        if matched:
            client, verified_native = _observer(payload)
            scheme = {"claude": "cc", "muse": "muse"}.get(client, "codex")
            matched = client_ref == f"{scheme}:{verified_native}"
        if client_ref.startswith("ccd:") and board is not None:
            from peer_addressing import CLIENT_CLAUDE, read_seat, seat_path

            row_uuid = row.get("session uuid", "")
            try:
                uuid.UUID(row_uuid)
            except (ValueError, TypeError, AttributeError):
                # A malformed row cannot bind this event, but it must not
                # abort matching for the remaining rows.
                continue
            path = seat_path(board, row_uuid)
            if path.is_symlink() or path.parent.is_symlink():
                raise ProjectStateError(
                    "Desktop checkpoint identity evidence crosses an unsafe symlink"
                )
            try:
                seat = read_seat(board, row.get("session uuid", ""), strict=True)
            except (OSError, ValueError):
                # An unverifiable seat disqualifies its own row only. One
                # stale seat (e.g. pre-migration schema) must never fail the
                # checkpoint for unrelated sessions. The row cannot match, so
                # this stays fail-closed per row.
                continue
            if seat is not None and seat.harness_session_id == native:
                client, verified_native = _observer(payload)
                matched = (
                    client == "claude"
                    and verified_native == native
                    and seat.client == CLIENT_CLAUDE
                    and seat.compact_id == row.get("compact id")
                    and f"ccd:{seat.host_session_id}" == client_ref
                    # Compare the row to the same value the writer
                    # emitted (Seat.board_machine) — never the label to
                    # the id. The operand lives on Seat so every
                    # seat/row comparison shares one implementation.
                    and (not row.get("machine") or row["machine"] == seat.board_machine)
                )
                if not matched:
                    raise ProjectStateError(
                        "Desktop checkpoint identity does not bind the active claim"
                    )
        if matched:
            matches.append(row)
    if len(matches) > 1:
        raise ProjectStateError(
            "lifecycle event matches multiple active coordination seats"
        )
    return matches[0] if matches else None


def observer_native_identity(payload: dict[str, Any]) -> tuple[str, str]:
    """Verify an observer from native transcript evidence, not a read-only flag.

    Supported entry point (ID-2, 2026-09-21): the private control
    plane resolves native identity through this helper."""
    native = payload.get("session_id")
    try:
        uuid.UUID(native)
    except (ValueError, TypeError, AttributeError) as exc:
        raise ProjectStateError(
            "observer Stop requires a valid native session UUID"
        ) from exc
    raw = payload.get("transcript_path")
    scripts = (
        Path(__file__).resolve().parents[2] / "synthesis-agent-conformance" / "scripts"
    )
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    try:
        from native_transcript_identity import (
            client_root_transcript_path,
            muse_sessions_root,
            resolve_muse_transcript,
            transcript_binds_session,
        )
    except (ImportError, SyntaxError) as exc:
        raise ProjectStateError(
            "observer native transcript validator is unavailable"
        ) from exc
    if raw is not None and raw != "":
        if not isinstance(raw, str) or not Path(raw).is_absolute():
            raise ProjectStateError("observer native transcript path must be absolute")
        transcript = Path(raw)
        if transcript.is_symlink() or not transcript.is_file():
            raise ProjectStateError("observer native transcript is missing or unsafe")
        matches = []
        roots = [
            (client, os.environ.get(variable, str(Path.home() / f".{client}")))
            for client, variable in (
                ("claude", "CLAUDE_CONFIG_DIR"),
                ("codex", "CODEX_HOME"),
            )
        ]
        roots.append(("muse", str(muse_sessions_root())))
        for client, raw_home in roots:
            if not raw_home.strip() or not Path(raw_home).expanduser().is_absolute():
                continue
            home = Path(raw_home).expanduser()
            if not client_root_transcript_path(transcript, client, native, home):
                continue
            # Explicit Muse paths must obey the same unique-store selection
            # as payloads without a path; a second date shard is ambiguous.
            if client == "muse" and resolve_muse_transcript(native) != transcript:
                continue
            if transcript_binds_session(transcript, client, native):
                matches.append(client)
        if len(matches) != 1:
            raise ProjectStateError(
                "observer transcript does not unambiguously bind this native session"
            )
        return matches[0], native
    # Muse payloads carry no transcript path: resolve the session log from
    # the store and require the same unambiguous binding evidence.
    resolved = resolve_muse_transcript(native)
    if resolved is None:
        raise ProjectStateError(
            "observer Stop requires this native session's transcript path"
        )
    if not client_root_transcript_path(resolved, "muse", native, muse_sessions_root()):
        raise ProjectStateError(
            "observer transcript does not unambiguously bind this native session"
        )
    if not transcript_binds_session(resolved, "muse", native):
        raise ProjectStateError(
            "observer transcript does not unambiguously bind this native session"
        )
    return "muse", native


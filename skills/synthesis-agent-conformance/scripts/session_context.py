#!/usr/bin/env python3
"""Emit a compact, verified project anchor for agent lifecycle hooks."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows only
    fcntl = None

try:
    import msvcrt
except ImportError:  # pragma: no cover - POSIX only
    msvcrt = None

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
PROJECT_MANAGEMENT_SCRIPTS_DIR = (
    Path(__file__).resolve().parents[2]
    / "synthesis-project-management"
    / "scripts"
)
if str(PROJECT_MANAGEMENT_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_MANAGEMENT_SCRIPTS_DIR))
ONBOARDING_SCRIPTS_DIR = (
    Path(__file__).resolve().parents[2]
    / "synthesis-onboarding"
    / "scripts"
)
if str(ONBOARDING_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(ONBOARDING_SCRIPTS_DIR))

from project_context import extract, next_actions, record_freshness
from active_project import load_and_validate
from coordination_schema import display_id, parse_table_rows, row_identity
from live_receipt import (
    claude_root_transcript_path,
    latest_receipt_paths,
    receipt_event_path,
    receipt_recorded_order,
    transcript_binding_state,
    transcript_binds_session,
    validate_receipt_event_directory,
)
from plugin_currency import sessionstart_notice


DEFAULT_POINTER = Path.home() / ".synthesis" / "active-project.json"
DEFAULT_COORDINATION_BOARD = (
    Path.home() / ".synthesis" / "coordination" / "active-sessions.md"
)
DEFAULT_LIVE_RECEIPT = (
    Path.home()
    / ".synthesis"
    / "agent-conformance"
    / "live"
    / "public-sessionstart.json"
)
DEFAULT_PENDING_HANDOFFS = Path(
    os.environ.get("SYNTHESIS_HOME", str(Path.home() / ".synthesis"))
) / "repo-guard" / "pending"


def atomic_json_write(destination: Path, payload: dict[str, object]) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=destination.parent,
            prefix=destination.name + ".",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_name = temporary.name
            temporary.write(json.dumps(payload, indent=2) + "\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, destination)
    finally:
        if temporary_name and os.path.exists(temporary_name):
            os.unlink(temporary_name)


@contextmanager
def receipt_registry_lock(destination: Path):
    """Serialize event creation and monotonic latest-pointer updates."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.parent.is_symlink():
        raise ValueError(
            f"receipt registry parent is a symlink: {destination.parent}"
        )
    lock_path = destination.parent / f".{destination.stem}-events.lock"
    if lock_path.is_symlink():
        raise ValueError(f"receipt registry lock is a symlink: {lock_path}")
    with lock_path.open("a+b") as handle:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        elif msvcrt is not None:  # pragma: no cover - Windows only
            if handle.seek(0, os.SEEK_END) == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:  # pragma: no cover - unsupported Python platform
            raise RuntimeError("receipt registry locking is unavailable")
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            elif msvcrt is not None:  # pragma: no cover - Windows only
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def _write_latest_if_newer(
    destination: Path, receipt: dict[str, object]
) -> None:
    if destination.exists():
        if destination.is_symlink() or not destination.is_file():
            raise ValueError(f"latest receipt path is unsafe: {destination}")
        try:
            current = json.loads(destination.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValueError(f"latest receipt is unreadable: {destination}") from exc
        if not isinstance(current, dict):
            raise ValueError(f"latest receipt is not an object: {destination}")
        if receipt_recorded_order(
            current, destination
        ) >= receipt_recorded_order(receipt, destination):
            return
    atomic_json_write(destination, receipt)


def plugin_identity() -> tuple[str | None, str]:
    """Return the executing plugin package version and root."""
    root = SCRIPTS_DIR.parents[2]
    for manifest in (
        root / ".codex-plugin" / "plugin.json",
        root / ".claude-plugin" / "plugin.json",
    ):
        try:
            version = json.loads(manifest.read_text(encoding="utf-8")).get("version")
        except (OSError, ValueError):
            continue
        if version:
            return str(version), str(root)
    return None, str(root)


def append_currency_notice(message: str, payload: dict[str, object]) -> str:
    """Prepend the lifecycle notice to genuine SessionStart output."""
    if payload.get("hook_event_name") != "SessionStart":
        return message
    try:
        notice = sessionstart_notice(plugin_identity()[1])
    except Exception as exc:
        notice = f"Synthesis plugin currency could not be verified: {exc}."
    return notice + "\n" + message if notice else message


def client_provenance(
    payload: dict[str, object], session_id: str
) -> tuple[str, str] | None:
    """Identify the client from a transcript bound to the claimed session."""
    transcript = Path(str(payload.get("transcript_path") or "")).expanduser()
    candidates = (
        (
            "codex",
            Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser(),
        ),
        (
            "claude",
            Path(
                os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude"))
            ).expanduser(),
        ),
    )
    if not transcript.is_absolute() or not transcript.is_file():
        return None
    for client, transcript_root in candidates:
        try:
            transcript.resolve().relative_to(transcript_root.resolve())
        except (OSError, ValueError):
            continue
        if client == "claude" and not claude_root_transcript_path(
            transcript, transcript_root, session_id
        ):
            continue
        if transcript_binds_session(transcript, client, session_id):
            return client, f"{client}-transcript"
    return None


def deferred_claude_provenance(
    payload: dict[str, object], session_id: str
) -> tuple[str, str] | None:
    """Validate Claude's transcript destination before its first JSONL write.

    Claude invokes SessionStart hooks before it creates or populates the
    transcript named in the hook payload.  The receipt can therefore preserve
    the client-delivered event before the binding exists, while conformance
    still requires that exact client-owned transcript to bind the session id
    before accepting the evidence.
    """
    transcript_text = str(payload.get("transcript_path") or "")
    transcript = Path(transcript_text).expanduser()
    claude_root = Path(
        os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude"))
    ).expanduser()
    if not transcript_text or not claude_root_transcript_path(
        transcript, claude_root, session_id
    ):
        return None
    if transcript_binding_state(transcript, "claude", session_id) not in {
        "pending",
        "bound",
    }:
        return None
    return "claude", "claude-transcript"


def record_live_receipt(payload: dict[str, object], destination: Path) -> bool:
    """Record only genuine SessionStart-shaped client payloads.

    Direct script probes use ``{}`` and cannot manufacture this receipt.  The
    receipt is evidence that a client actually delivered the hook event, not
    merely that the hook script can print a valid envelope.
    """
    event = payload.get("hook_event_name")
    session_id = payload.get("session_id")
    if event != "SessionStart" or not isinstance(session_id, str) or not session_id:
        return False
    try:
        uuid.UUID(session_id)
    except ValueError:
        return False
    provenance = client_provenance(payload, session_id)
    if provenance is None:
        provenance = deferred_claude_provenance(payload, session_id)
    if provenance is None:
        return False
    version, plugin_root = plugin_identity()
    client, provenance_env = provenance
    transcript = Path(str(payload.get("transcript_path") or "")).expanduser()
    binding_state = transcript_binding_state(transcript, client, session_id)
    if binding_state != "bound" and not (
        client == "claude" and binding_state == "pending"
    ):
        return False
    transcript_bound_at_record = binding_state == "bound"
    event_id = str(uuid.uuid4())
    receipt = {
        "receipt_schema": 2,
        "receipt_event_id": event_id,
        "hook_event_name": event,
        "session_id": session_id,
        "client": client,
        "cwd": payload.get("cwd"),
        "source": payload.get("source"),
        "transcript_path": payload.get("transcript_path"),
        "transcript_bound_at_record": transcript_bound_at_record,
        "provenance_env": provenance_env,
        "plugin_version": version,
        "plugin_root": plugin_root,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    generic_latest, client_latest = latest_receipt_paths(destination, client)
    event_path = receipt_event_path(
        client_latest,
        client=client,
        session_id=session_id,
        event_id=event_id,
    )
    with receipt_registry_lock(generic_latest):
        validate_receipt_event_directory(client_latest, client, session_id)
        if event_path.exists():
            raise FileExistsError(f"receipt event already exists: {event_path}")
        atomic_json_write(event_path, receipt)
        _write_latest_if_newer(client_latest, receipt)
        _write_latest_if_newer(generic_latest, receipt)
    return True


def active_session_ids(board: Path) -> list[str]:
    if not board.is_file():
        return []
    text = board.read_text(encoding="utf-8")
    if not all(
        heading in text
        for heading in ("## Active sessions", "## Messages", "## Protocol")
    ):
        raise ValueError(f"coordination board schema is invalid: {board}")
    active = []
    for row in parse_table_rows(text):
        if row.get("status", "").lower() not in {
            "released",
            "complete",
            "completed",
            "closed",
        }:
            active.append(display_id(row_identity(row)))
    return active


def pending_handoff_count(directory: Path) -> int:
    if not directory.is_dir():
        return 0
    count = 0
    for path in directory.glob("*.json"):
        if path.is_symlink():
            raise ValueError(f"pending handoff manifest is a symlink: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data.get("session_id"), str) or not isinstance(
            data.get("paths"), list
        ):
            raise ValueError(f"pending handoff manifest is invalid: {path}")
        count += 1
    return count


def project_from_cwd(cwd: Path | None) -> Path | None:
    """Discover a durable project when a task opens inside its directory."""
    if cwd is None:
        return None
    try:
        candidate = cwd.expanduser().resolve(strict=True)
    except OSError:
        return None
    if candidate.is_file():
        candidate = candidate.parent
    for directory in (candidate, *candidate.parents):
        if (
            (directory / "CONTEXT.md").is_file()
            and (directory / "REFERENCE.md").is_file()
            and (directory / "sessions").is_dir()
        ):
            return directory
    return None


def linked_plan(project: Path, context: str) -> Path | None:
    match = re.search(
        r"\((resources/artifacts/[^)\n]*plan[^)\n]*\.md)\)",
        context,
        re.IGNORECASE,
    )
    return project / match.group(1) if match else None


def append_project_context(lines: list[str], project: Path, *, label: str) -> None:
    context_path = project / "CONTEXT.md"
    context = context_path.read_text(encoding="utf-8")
    phase = extract(context, "Phase")
    status = extract(context, "Status")
    plan = linked_plan(project, context)
    if plan is not None and not plan.is_file():
        raise FileNotFoundError(f"active plan is missing: {plan}")
    lines.extend(
        [
            f"{label}: {project}.",
            f"Current phase: {phase}.",
            f"Current status: {status}.",
            f"Controlling plan: {plan or 'unknown'}.",
        ]
    )
    fresh, freshness_detail = record_freshness(project)
    if not fresh:
        lines.append(f"RECORD STALENESS WARNING: {freshness_detail}.")
    actions = next_actions(context)
    if actions:
        lines.append("Recorded next actions:")
        lines.extend(f"- {action}" for action in actions)
    lines.append("Re-read CONTEXT.md and the controlling plan before substantive work.")


def build(
    pointer: Path,
    coordination_board: Path = DEFAULT_COORDINATION_BOARD,
    cwd: Path | None = None,
    pending_handoffs: Path = DEFAULT_PENDING_HANDOFFS,
) -> str:
    now = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z (%A)")
    lines = [f"Verified local time: {now}."]
    sessions = active_session_ids(coordination_board)
    if sessions:
        lines.append(
            "Cross-agent coordination is active for session(s): "
            + ", ".join(sessions)
            + ". Read the coordination board and verify claims before writes."
        )
    pending = pending_handoff_count(pending_handoffs)
    if pending:
        lines.append(
            f"Local continuity: {pending} attributed edit manifest(s) await "
            "remote publication. Inspect working-tree truth before relying on "
            "cached project context; an interrupted task remains recoverable on "
            "this machine."
        )
    if not pointer.is_file():
        lines.append("No active synthesis project pointer is set.")
        discovered = project_from_cwd(cwd)
        if discovered is not None:
            append_project_context(
                lines,
                discovered,
                label="Stopped synthesis project discovered from the task directory",
            )
        else:
            lines.append(
                "Stopped-task recovery remains available: when the user names a "
                "synthesis project, resolve it from the git-tracked projects/index.yaml "
                "and run the Session Start Protocol automatically; never ask the user "
                "to run a context-lifecycle command or save state manually. One "
                "exception to automatic resolution: if the named project contradicts "
                "this session's own established context (its prior conversation, "
                "active project, or task directory), surface the contradiction and "
                "confirm which project is meant before switching - never silently "
                "resolve the name over the session's evidence."
            )
        return "\n".join(lines)

    data, pointer_issues = load_and_validate(pointer, coordination_board)
    if pointer_issues:
        raise ValueError("; ".join(pointer_issues))
    project = Path(data["project"]).expanduser().resolve()
    context_path = project / "CONTEXT.md"
    if not context_path.is_file():
        raise FileNotFoundError(f"active project CONTEXT.md is missing: {context_path}")

    plan = data.get("plan", "unknown")
    if plan != "unknown" and not Path(plan).is_file():
        raise FileNotFoundError(f"active plan is missing: {plan}")
    append_project_context(lines, project, label="Active synthesis project")
    return "\n".join(lines)


def append_inbox(message: str, payload: dict, board: Path, pointer: Path) -> str:
    """Attach unread board messages for this seat, and for a non-Claude
    client its coordination identity, so the bus is delivered at session
    start and a Codex session learns the id its receipts are filed under."""
    try:
        from board_inbox import inbox_text

        extra = inbox_text(payload, board=board, pointer=pointer)
    except Exception as exc:  # the inbox never blocks a session start
        extra = f"Coordination inbox unavailable: {exc}"
    return message + ("\n" + extra if extra else "")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--active-project-file", type=Path, default=DEFAULT_POINTER)
    parser.add_argument(
        "--coordination-board",
        type=Path,
        default=DEFAULT_COORDINATION_BOARD,
    )
    parser.add_argument(
        "--format",
        choices=("text", "codex", "claude"),
        default="text",
        help="Wrap output for a client hook schema.",
    )
    parser.add_argument(
        "--live-receipt",
        type=Path,
        default=Path(
            os.environ.get(
                "SYNTHESIS_PUBLIC_SESSIONSTART_RECEIPT",
                str(DEFAULT_LIVE_RECEIPT),
            )
        ),
    )
    args = parser.parse_args()
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}
    try:
        message = build(
            args.active_project_file.expanduser(),
            args.coordination_board.expanduser(),
            Path(str(payload["cwd"])) if payload.get("cwd") else None,
        )
    except Exception as exc:
        print(f"synthesis project context failed closed: {exc}", file=sys.stderr)
        return 2
    message = append_currency_notice(message, payload)
    message = append_inbox(
        message,
        payload,
        args.coordination_board.expanduser(),
        args.active_project_file.expanduser(),
    )
    try:
        record_live_receipt(payload, args.live_receipt.expanduser())
    except Exception as exc:
        print(f"synthesis live receipt failed closed: {exc}", file=sys.stderr)
        return 2

    if args.format == "codex":
        event = payload.get("hook_event_name", "SessionStart")
        print(
            json.dumps(
                {
                    "continue": True,
                    "hookSpecificOutput": {
                        "hookEventName": event,
                        "additionalContext": message,
                    },
                }
            )
        )
    elif args.format == "claude":
        print(
            json.dumps(
                {
                    "continue": True,
                    "hookSpecificOutput": {
                        "hookEventName": "SessionStart",
                        "additionalContext": message,
                    },
                }
            )
        )
    else:
        print(message)
    return 0


if __name__ == "__main__":
    sys.exit(main())

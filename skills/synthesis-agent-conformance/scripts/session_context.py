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
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from project_context import extract, next_actions, record_freshness
from active_project import load_and_validate
from live_receipt import transcript_binds_session


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
        if transcript_binds_session(transcript, client, session_id):
            return client, f"{client}-transcript"
    return None


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
        return False
    version, plugin_root = plugin_identity()
    client, provenance_env = provenance
    receipt = {
        "hook_event_name": event,
        "session_id": session_id,
        "client": client,
        "cwd": payload.get("cwd"),
        "source": payload.get("source"),
        "transcript_path": payload.get("transcript_path"),
        "provenance_env": provenance_env,
        "plugin_version": version,
        "plugin_root": plugin_root,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    destinations = [destination]
    if client in {"claude", "codex"} and not destination.stem.endswith(f"-{client}"):
        destinations.append(
            destination.with_name(f"{destination.stem}-{client}{destination.suffix}")
        )
    for receipt_path in destinations:
        atomic_json_write(receipt_path, receipt)
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
    in_table = False
    for line in text.splitlines():
        if line.strip() == "## Active sessions":
            in_table = True
            continue
        if in_table and line.startswith("## "):
            break
        if not in_table or not line.startswith("|"):
            continue
        columns = [re.sub(r"[*`]", "", value).strip() for value in line.split("|")[1:-1]]
        if len(columns) not in {7, 12} or columns[0] in {"id", "----"}:
            continue
        if set(columns[0]) == {"-"}:
            continue
        if columns[-1].lower() not in {
            "released",
            "complete",
            "completed",
            "closed",
        }:
            active.append(columns[0])
    return active


def build(pointer: Path, coordination_board: Path = DEFAULT_COORDINATION_BOARD) -> str:
    now = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z (%A)")
    lines = [f"Verified local time: {now}."]
    sessions = active_session_ids(coordination_board)
    if sessions:
        lines.append(
            "Cross-agent coordination is active for session(s): "
            + ", ".join(sessions)
            + ". Read the coordination board and verify claims before writes."
        )
    if not pointer.is_file():
        lines.append("No active synthesis project pointer is set.")
        return "\n".join(lines)

    data, pointer_issues = load_and_validate(pointer, coordination_board)
    if pointer_issues:
        raise ValueError("; ".join(pointer_issues))
    project = Path(data["project"]).expanduser().resolve()
    context_path = project / "CONTEXT.md"
    if not context_path.is_file():
        raise FileNotFoundError(f"active project CONTEXT.md is missing: {context_path}")

    context = context_path.read_text(encoding="utf-8")
    phase = extract(context, "Phase")
    status = extract(context, "Status")
    plan = data.get("plan", "unknown")
    if plan != "unknown" and not Path(plan).is_file():
        raise FileNotFoundError(f"active plan is missing: {plan}")

    lines.extend(
        [
            f"Active synthesis project: {project}.",
            f"Current phase: {phase}.",
            f"Current status: {status}.",
            f"Controlling plan: {plan}.",
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
    return "\n".join(lines)


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
        )
    except Exception as exc:
        print(f"synthesis project context failed closed: {exc}", file=sys.stderr)
        return 2
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

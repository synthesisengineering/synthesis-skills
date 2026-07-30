#!/usr/bin/env python3
"""Manage synthesis cross-agent claims, handoffs, and project ownership."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import shutil
import socket
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path


DEFAULT_BOARD = Path.home() / ".synthesis" / "coordination" / "active-sessions.md"
SCHEMA_VERSION = 2
TABLE_COLUMNS = (
    "id",
    "agent",
    "machine",
    "project",
    "started",
    "heartbeat",
    "mode",
    "workspace(s) / branch",
    "goal",
    "claimed areas (advisory lock)",
    "context role",
    "status",
)
TABLE_HEADER = (
    "| " + " | ".join(TABLE_COLUMNS) + " |\n"
    + "|"
    + "|".join("---" for _ in TABLE_COLUMNS)
    + "|"
)
V1_COLUMNS = (
    "id",
    "agent",
    "started",
    "mode",
    "goal",
    "claimed areas (advisory lock)",
    "status",
)
TERMINAL_STATUSES = {"released", "complete", "completed", "closed"}
CONTEXT_RESERVED_PATTERNS = (
    "context.md",
    "reference.md",
    "projects/index.yaml",
    "/sessions/",
    "/sessions/**",
    "autopilot-plan.md",
)


@dataclass
class Session:
    id: str
    agent: str
    machine: str
    project: str
    started: str
    heartbeat: str
    mode: str
    workspaces: list[str]
    goal: str
    claims: list[str]
    context_role: str
    status: str

    def cells(self) -> list[str]:
        return [
            self.id,
            self.agent,
            self.machine,
            self.project,
            self.started,
            self.heartbeat,
            self.mode,
            ", ".join(self.workspaces),
            self.goal,
            ", ".join(self.claims),
            self.context_role,
            self.status,
        ]


def timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def template() -> str:
    return (
        "# Synthesis — Cross-Agent Session Coordination\n\n"
        "Shared advisory-lock and message board for independent agent sessions.\n\n"
        f"Schema: v{SCHEMA_VERSION}\n\n"
        "## Active sessions\n\n"
        f"{TABLE_HEADER}\n\n"
        "## Messages\n\n"
        "---\n\n"
        "## Protocol\n\n"
        "1. Read at SessionStart and every checkpoint.\n"
        "2. Claim before write; do not write through overlap.\n"
        "3. Every root session that writes git state uses an isolated worktree and branch.\n"
        "4. One session owns project context; contributors write separate handoff artifacts.\n"
        "5. Existing autonomous claims keep priority over interactive sessions.\n"
        "6. Heartbeat at checkpoints; release or narrow claims at pause and session end.\n"
    )


def plain(value: str) -> str:
    without_bold = re.sub(r"\*\*(.+?)\*\*", r"\1", value)
    return re.sub(r"`(.+?)`", r"\1", without_bold).strip()


def sanitize(value: str) -> str:
    return " ".join(value.replace("|", "/").split())


def split_values(value: str) -> list[str]:
    clean = plain(value)
    if not clean or clean.lower().startswith("released"):
        return []
    return [
        item.strip()
        for item in re.split(r",|<br\s*/?>", clean)
        if item.strip()
    ]


def claim_prefix(claim: str) -> str:
    marker = len(claim)
    for token in ("*", "?", "["):
        position = claim.find(token)
        if position >= 0:
            marker = min(marker, position)
    return claim[:marker].rstrip("/")


def overlaps(left: str, right: str) -> bool:
    left_prefix = claim_prefix(left)
    right_prefix = claim_prefix(right)
    if not left_prefix or not right_prefix:
        return True
    return (
        left_prefix == right_prefix
        or left_prefix.startswith(right_prefix + "/")
        or right_prefix.startswith(left_prefix + "/")
    )


def workspace_parts(workspace: str) -> tuple[str, str]:
    if " @ " not in workspace:
        return plain(workspace), "unknown"
    path, branch = workspace.rsplit(" @ ", 1)
    return plain(path), plain(branch)


def workspace_conflict(left: str, right: str) -> bool:
    left_path, left_branch = workspace_parts(left)
    right_path, right_branch = workspace_parts(right)
    ignored = {"", "none", "unknown", "n/a"}
    if left_path.lower() in ignored or right_path.lower() in ignored:
        return False
    if Path(left_path).expanduser() == Path(right_path).expanduser():
        return True
    return (
        Path(left_path).name == Path(right_path).name
        and left_branch not in ignored
        and left_branch == right_branch
    )


def claims_context(claim: str) -> bool:
    normalized = "/" + plain(claim).lower().lstrip("/")
    return any(pattern in normalized for pattern in CONTEXT_RESERVED_PATTERNS)


def parse_cells(line: str) -> list[str] | None:
    if not line.startswith("|"):
        return None
    cells = [value.strip() for value in line.split("|")[1:-1]]
    if not cells:
        return None
    first = plain(cells[0])
    if first == "id" or set(first) == {"-"}:
        return None
    return cells


def session_from_cells(cells: list[str]) -> Session:
    if len(cells) == len(TABLE_COLUMNS):
        return Session(
            id=plain(cells[0]),
            agent=plain(cells[1]),
            machine=plain(cells[2]),
            project=plain(cells[3]),
            started=plain(cells[4]),
            heartbeat=plain(cells[5]),
            mode=plain(cells[6]),
            workspaces=split_values(cells[7]),
            goal=plain(cells[8]),
            claims=split_values(cells[9]),
            context_role=plain(cells[10]).lower(),
            status=plain(cells[11]).lower(),
        )
    if len(cells) == len(V1_COLUMNS):
        started = plain(cells[2])
        return Session(
            id=plain(cells[0]),
            agent=plain(cells[1]),
            machine="unknown",
            project="unknown",
            started=started,
            heartbeat=started,
            mode=plain(cells[3]),
            workspaces=[],
            goal=plain(cells[4]),
            claims=split_values(cells[5]),
            context_role="none",
            status=plain(cells[6]).lower(),
        )
    raise ValueError(
        f"active-session row has {len(cells)} columns; expected "
        f"{len(TABLE_COLUMNS)}"
    )


def rows(text: str) -> list[Session]:
    result: list[Session] = []
    in_table = False
    for line in text.splitlines():
        if line.strip() == "## Active sessions":
            in_table = True
            continue
        if in_table and line.startswith("## "):
            break
        if not in_table:
            continue
        cells = parse_cells(line)
        if cells is not None:
            result.append(session_from_cells(cells))
    return result


def active(session: Session) -> bool:
    return session.status not in TERMINAL_STATUSES


def parse_time(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def stale(session: Session, minutes: int) -> bool:
    heartbeat = parse_time(session.heartbeat)
    if not active(session) or heartbeat is None:
        return active(session) and heartbeat is None
    now = datetime.now().astimezone()
    if heartbeat.tzinfo is None:
        heartbeat = heartbeat.replace(tzinfo=now.tzinfo)
    return now - heartbeat > timedelta(minutes=minutes)


def replace_table(text: str, sessions: list[Session]) -> str:
    rendered = [TABLE_HEADER]
    rendered.extend(
        "| " + " | ".join(sanitize(value) for value in session.cells()) + " |"
        for session in sessions
    )
    block = "\n".join(rendered)
    pattern = re.compile(r"(?ms)(^## Active sessions\s*\n).*?(?=^## Messages\s*$)")
    if not pattern.search(text):
        raise ValueError("board lacks Active sessions and Messages sections")
    updated = pattern.sub(lambda match: match.group(1) + "\n" + block + "\n\n", text)
    if re.search(r"(?m)^Schema:\s*v\d+\s*$", updated):
        return re.sub(
            r"(?m)^Schema:\s*v\d+\s*$",
            f"Schema: v{SCHEMA_VERSION}",
            updated,
            count=1,
        )
    marker = re.search(r"(?m)^## Active sessions\s*$", updated)
    if marker is None:
        raise ValueError("board lacks Active sessions heading")
    return (
        updated[: marker.start()]
        + f"Schema: v{SCHEMA_VERSION}\n\n"
        + updated[marker.start() :]
    )


def write_board(board: Path, content: str) -> None:
    board.parent.mkdir(parents=True, exist_ok=True)
    if board.exists():
        backup_dir = board.parent / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup = backup_dir / (
            f"{board.name}.{datetime.now().strftime('%Y%m%dT%H%M%S%f')}.bak"
        )
        shutil.copy2(board, backup)
        if backup.read_bytes() != board.read_bytes():
            raise OSError(f"coordination backup verification failed: {backup}")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{board.name}.", suffix=".tmp", dir=str(board.parent)
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, board)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def locked_update(board: Path, operation) -> None:
    board.parent.mkdir(parents=True, exist_ok=True)
    lock_path = board.parent / ".active-sessions.lock"
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        content = board.read_text(encoding="utf-8") if board.exists() else template()
        write_board(board, operation(content))


def validate_sessions(sessions: list[Session]) -> list[str]:
    problems: list[str] = []
    seen_ids: set[str] = set()
    for session in sessions:
        if session.id in seen_ids:
            problems.append(f"duplicate session id: {session.id}")
        seen_ids.add(session.id)
        if session.context_role not in {"owner", "contributor", "none"}:
            problems.append(
                f"session {session.id} has invalid context role: "
                f"{session.context_role}"
            )
    live = [session for session in sessions if active(session)]
    for index, left in enumerate(live):
        if left.context_role == "contributor":
            for claim in left.claims:
                if claims_context(claim):
                    problems.append(
                        f"session {left.id} is a contributor but claims context: {claim}"
                    )
        for right in live[index + 1 :]:
            for left_claim in left.claims:
                for right_claim in right.claims:
                    if overlaps(left_claim, right_claim):
                        problems.append(
                            f"{left.id}:{left_claim} overlaps "
                            f"{right.id}:{right_claim}"
                        )
            for left_workspace in left.workspaces:
                for right_workspace in right.workspaces:
                    if workspace_conflict(left_workspace, right_workspace):
                        problems.append(
                            f"{left.id} and {right.id} share workspace or branch: "
                            f"{left_workspace} / {right_workspace}"
                        )
            if (
                left.project not in {"", "unknown", "none"}
                and left.project == right.project
                and left.context_role == "owner"
                and right.context_role == "owner"
            ):
                problems.append(
                    f"{left.id} and {right.id} both own context for {left.project}"
                )
    return problems


def command_status(args) -> int:
    if not args.board.is_file():
        print(f"No coordination board: {args.board}")
        return 0
    content = args.board.read_text(encoding="utf-8")
    sessions = rows(content)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "board": str(args.board),
        "sessions": [
            {
                **asdict(session),
                "stale": stale(session, args.stale_after_minutes),
            }
            for session in sessions
        ],
        "problems": validate_sessions(sessions),
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(content)
        for session in sessions:
            if stale(session, args.stale_after_minutes):
                print(
                    f"STALE active session {session.id}: heartbeat "
                    f"{session.heartbeat}",
                    file=sys.stderr,
                )
        for problem in payload["problems"]:
            print(f"COORDINATION ERROR: {problem}", file=sys.stderr)
    return 10 if args.strict and (payload["problems"] or any(
        item["stale"] for item in payload["sessions"]
    )) else 0


def command_claim(args) -> int:
    requested = [sanitize(area) for area in args.area]
    workspaces = [sanitize(workspace) for workspace in args.workspace]
    if args.context_role == "contributor":
        reserved = [claim for claim in requested if claims_context(claim)]
        if reserved:
            print(
                "coordination claim refused: contributor sessions cannot claim "
                "canonical project context: " + ", ".join(reserved),
                file=sys.stderr,
            )
            return 10

    def operation(content: str) -> str:
        current = rows(content)
        now = timestamp()
        existing_self = next(
            (session for session in current if session.id == args.id),
            None,
        )
        replacement = Session(
            id=args.id,
            agent=args.agent,
            machine=args.machine,
            project=args.project,
            started=existing_self.started if existing_self else now,
            heartbeat=now,
            mode=args.mode,
            workspaces=workspaces,
            goal=args.goal,
            claims=requested,
            context_role=args.context_role,
            status="active",
        )
        prospective = [
            replacement if session.id == args.id else session for session in current
        ]
        if existing_self is None:
            prospective.append(replacement)
        problems = validate_sessions(prospective)
        if problems:
            raise RuntimeError("; ".join(problems))
        return replace_table(content, prospective)

    try:
        locked_update(args.board, operation)
    except RuntimeError as exc:
        print(f"coordination claim refused: {exc}", file=sys.stderr)
        return 10
    print(f"Claimed {', '.join(requested)} for session {args.id}.")
    return 0


def command_heartbeat(args) -> int:
    def operation(content: str) -> str:
        current = rows(content)
        for session in current:
            if session.id == args.id:
                if not active(session):
                    raise RuntimeError(f"session is not active: {args.id}")
                session.heartbeat = timestamp()
                return replace_table(content, current)
        raise RuntimeError(f"session not found: {args.id}")

    try:
        locked_update(args.board, operation)
    except RuntimeError as exc:
        print(f"coordination heartbeat failed: {exc}", file=sys.stderr)
        return 10
    print(f"Heartbeat updated for session {args.id}.")
    return 0


def command_release(args) -> int:
    def operation(content: str) -> str:
        current = rows(content)
        for session in current:
            if session.id == args.id:
                session.status = "released"
                session.heartbeat = timestamp()
                return replace_table(content, current)
        raise RuntimeError(f"session not found: {args.id}")

    try:
        locked_update(args.board, operation)
    except RuntimeError as exc:
        print(f"coordination release failed: {exc}", file=sys.stderr)
        return 10
    print(f"Released session {args.id}.")
    return 0


def command_message(args) -> int:
    body = args.text if args.text is not None else sys.stdin.read().strip()
    if not body:
        print("coordination message is empty", file=sys.stderr)
        return 2

    def operation(content: str) -> str:
        heading = (
            f"### → {sanitize(args.to)}, from {sanitize(args.sender)} — {timestamp()}"
        )
        block = f"{heading}\n\n{body.strip()}\n\n"
        marker = re.search(
            r"(?m)^---[ \t]*\n\n## Protocol(?:[^\n]*)?$",
            content,
        )
        if not marker:
            raise RuntimeError("board lacks Protocol boundary")
        return content[: marker.start()] + block + content[marker.start() :]

    try:
        locked_update(args.board, operation)
    except RuntimeError as exc:
        print(f"coordination message failed: {exc}", file=sys.stderr)
        return 10
    print(f"Message appended for {args.to}.")
    return 0


def command_migrate(args) -> int:
    def operation(content: str) -> str:
        migrated = rows(content)
        return replace_table(content, migrated)

    locked_update(args.board, operation)
    print(f"Migrated {args.board} to schema v{SCHEMA_VERSION}.")
    return 0


def command_doctor(args) -> int:
    if not args.board.is_file():
        print(f"FAIL coordination.board: missing {args.board}", file=sys.stderr)
        return 1
    try:
        content = args.board.read_text(encoding="utf-8")
        sessions = rows(content)
        problems = validate_sessions(sessions)
    except Exception as exc:
        print(f"FAIL coordination.board: {exc}", file=sys.stderr)
        return 1
    required = ("## Active sessions", "## Messages", "## Protocol")
    missing = [heading for heading in required if heading not in content]
    if missing:
        problems.extend(f"missing heading: {heading}" for heading in missing)
    if f"Schema: v{SCHEMA_VERSION}" not in content:
        problems.append(f"missing Schema: v{SCHEMA_VERSION}")
    if problems:
        for problem in problems:
            print(f"FAIL coordination: {problem}", file=sys.stderr)
        return 1
    print(
        f"PASS coordination: schema v{SCHEMA_VERSION}, "
        f"{len(sessions)} session(s)"
    )
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--board", type=Path, default=DEFAULT_BOARD)
    commands = result.add_subparsers(dest="command", required=True)
    status = commands.add_parser("status")
    status.add_argument("--json", action="store_true")
    status.add_argument("--strict", action="store_true")
    status.add_argument("--stale-after-minutes", type=int, default=240)
    claim = commands.add_parser("claim")
    claim.add_argument("--id", required=True)
    claim.add_argument("--agent", required=True)
    claim.add_argument("--machine", default=socket.gethostname())
    claim.add_argument("--project", required=True)
    claim.add_argument("--mode", required=True)
    claim.add_argument("--goal", required=True)
    claim.add_argument(
        "--workspace",
        action="append",
        required=True,
        help="Isolated worktree path and branch: /path/to/worktree @ branch",
    )
    claim.add_argument("--area", action="append", required=True)
    claim.add_argument(
        "--context-role",
        choices=("owner", "contributor", "none"),
        required=True,
    )
    heartbeat = commands.add_parser("heartbeat")
    heartbeat.add_argument("--id", required=True)
    release = commands.add_parser("release")
    release.add_argument("--id", required=True)
    message = commands.add_parser("message")
    message.add_argument("--from", dest="sender", required=True)
    message.add_argument("--to", required=True)
    message.add_argument("--text")
    commands.add_parser("migrate")
    commands.add_parser("doctor")
    return result


def main() -> int:
    args = parser().parse_args()
    args.board = args.board.expanduser()
    if args.command == "status":
        return command_status(args)
    if args.command == "claim":
        return command_claim(args)
    if args.command == "heartbeat":
        return command_heartbeat(args)
    if args.command == "release":
        return command_release(args)
    if args.command == "message":
        return command_message(args)
    if args.command == "migrate":
        return command_migrate(args)
    return command_doctor(args)


if __name__ == "__main__":
    sys.exit(main())

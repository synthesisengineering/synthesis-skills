#!/usr/bin/env python3
"""Manage the synthesis cross-agent advisory-lock and message board."""

from __future__ import annotations

import argparse
import fcntl
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path


DEFAULT_BOARD = Path.home() / ".synthesis" / "coordination" / "active-sessions.md"
TABLE_HEADER = (
    "| id | agent | started | mode | goal | claimed areas (advisory lock) | status |\n"
    "|----|-------|---------|------|------|--------------------------------|--------|"
)
ROW_RE = re.compile(
    r"^\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|"
    r"\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|$"
)


def timestamp() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")


def template() -> str:
    return (
        "# Synthesis — Cross-Agent Session Coordination\n\n"
        "Shared advisory-lock and message board for independent agent sessions.\n\n"
        "## Active sessions\n\n"
        f"{TABLE_HEADER}\n\n"
        "## Messages\n\n"
        "---\n\n"
        "## Protocol\n\n"
        "1. Read at SessionStart and every checkpoint.\n"
        "2. Claim before write; do not write through overlap.\n"
        "3. Existing autonomous claims keep priority over interactive sessions.\n"
        "4. Release or narrow claims at pause and session end.\n"
    )


def plain(value: str) -> str:
    return re.sub(r"[*`]", "", value).strip()


def sanitize(value: str) -> str:
    return " ".join(value.replace("|", "/").split())


def split_claims(value: str) -> list[str]:
    clean = plain(value)
    if clean.lower().startswith("released"):
        return []
    return [item.strip() for item in re.split(r",|<br\s*/?>", clean) if item.strip()]


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


def rows(text: str) -> list[list[str]]:
    result = []
    in_table = False
    for line in text.splitlines():
        if line.strip() == "## Active sessions":
            in_table = True
            continue
        if in_table and line.startswith("## "):
            break
        if not in_table or not line.startswith("|"):
            continue
        match = ROW_RE.match(line)
        if not match:
            continue
        values = [value.strip() for value in match.groups()]
        if plain(values[0]) == "id" or set(plain(values[0])) == {"-"}:
            continue
        result.append(values)
    return result


def active(row: list[str]) -> bool:
    status = plain(row[6]).lower()
    return status not in {"released", "complete", "completed", "closed"}


def replace_table(text: str, table_rows: list[list[str]]) -> str:
    rendered = [TABLE_HEADER]
    rendered.extend(
        "| " + " | ".join(sanitize(value) for value in row) + " |"
        for row in table_rows
    )
    block = "\n".join(rendered)
    pattern = re.compile(r"(?ms)(^## Active sessions\s*\n).*?(?=^## Messages\s*$)")
    if not pattern.search(text):
        raise ValueError("board lacks Active sessions and Messages sections")
    return pattern.sub(lambda match: match.group(1) + "\n" + block + "\n\n", text)


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


def command_status(board: Path) -> int:
    if not board.is_file():
        print(f"No coordination board: {board}")
        return 0
    print(board.read_text(encoding="utf-8"))
    return 0


def command_claim(args) -> int:
    requested = [sanitize(area) for area in args.area]

    def operation(content: str) -> str:
        current = rows(content)
        conflicts = []
        for row in current:
            if plain(row[0]) == args.id or not active(row):
                continue
            for existing in split_claims(row[5]):
                for area in requested:
                    if overlaps(existing, area):
                        conflicts.append(
                            f"{area} overlaps session {plain(row[0])}: {existing}"
                        )
        if conflicts:
            raise RuntimeError("; ".join(conflicts))

        replacement = [
            args.id,
            args.agent,
            timestamp(),
            args.mode,
            args.goal,
            ", ".join(requested),
            "active",
        ]
        for index, row in enumerate(current):
            if plain(row[0]) == args.id:
                current[index] = replacement
                break
        else:
            current.append(replacement)
        return replace_table(content, current)

    try:
        locked_update(args.board, operation)
    except RuntimeError as exc:
        print(f"coordination claim refused: {exc}", file=sys.stderr)
        return 10
    print(f"Claimed {', '.join(requested)} for session {args.id}.")
    return 0


def command_release(args) -> int:
    def operation(content: str) -> str:
        current = rows(content)
        for row in current:
            if plain(row[0]) == args.id:
                row[6] = "released"
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
        marker = re.search(r"(?m)^---\s*\n\n## Protocol\s*$", content)
        if not marker:
            raise RuntimeError("board lacks Protocol boundary")
        return content[: marker.start()] + block + content[marker.start() :]

    locked_update(args.board, operation)
    print(f"Message appended for {args.to}.")
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--board", type=Path, default=DEFAULT_BOARD)
    commands = result.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    claim = commands.add_parser("claim")
    claim.add_argument("--id", required=True)
    claim.add_argument("--agent", required=True)
    claim.add_argument("--mode", required=True)
    claim.add_argument("--goal", required=True)
    claim.add_argument("--area", action="append", required=True)
    release = commands.add_parser("release")
    release.add_argument("--id", required=True)
    message = commands.add_parser("message")
    message.add_argument("--from", dest="sender", required=True)
    message.add_argument("--to", required=True)
    message.add_argument("--text")
    return result


def main() -> int:
    args = parser().parse_args()
    args.board = args.board.expanduser()
    if args.command == "status":
        return command_status(args.board)
    if args.command == "claim":
        return command_claim(args)
    if args.command == "release":
        return command_release(args)
    return command_message(args)


if __name__ == "__main__":
    sys.exit(main())

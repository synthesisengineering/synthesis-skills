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
import subprocess
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
    # Semicolons appear in hand-migrated rows; treating them as content would
    # fuse several claims into one unmatchable string and silently disable
    # overlap detection for that row.
    return [
        item.strip()
        for item in re.split(r"[,;]|<br\s*/?>", clean)
        if item.strip()
    ]


def claim_prefix(claim: str) -> str:
    marker = len(claim)
    for token in ("*", "?", "["):
        position = claim.find(token)
        if position >= 0:
            marker = min(marker, position)
    return claim[:marker].rstrip("/")


def claim_segments(claim: str) -> tuple[bool, list[str]]:
    prefix = claim_prefix(claim)
    if not prefix:
        return True, []
    expanded = os.path.expanduser(prefix)
    absolute = expanded.startswith("/")
    segments = [part for part in expanded.strip("/").split("/") if part]
    return absolute, segments


def overlaps(left: str, right: str) -> bool:
    """Conflict test for two claim globs.

    Claims arrive in mixed spellings — absolute, ``~``-prefixed, and
    repository-relative — and two spellings of one real path must still
    conflict. Same-form claims overlap on segment-boundary containment.
    A relative claim overlaps an absolute one when its segment run aligns
    anywhere inside the absolute claim through the end of either claim;
    that alignment can flag unrelated trees that share segment names, and
    the protocol prefers that false conflict (resolved by re-scoping to
    absolute claims) over silently missing a real one.
    """
    left_absolute, left_segments = claim_segments(left)
    right_absolute, right_segments = claim_segments(right)
    if not left_segments or not right_segments:
        return True
    if left_absolute == right_absolute:
        shorter, longer = sorted(
            (left_segments, right_segments), key=len
        )
        return longer[: len(shorter)] == shorter
    absolute_segments = left_segments if left_absolute else right_segments
    relative_segments = right_segments if left_absolute else left_segments
    for start in range(len(absolute_segments)):
        length = min(len(relative_segments), len(absolute_segments) - start)
        if absolute_segments[start : start + length] == relative_segments[:length]:
            return True
    return False


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


LEASE_CONFIG_NAME = "lease.json"
LEASE_DEFAULT_REF = "refs/synthesis/coordination-board"
LEASE_RETRIES = 3
LEASE_GIT_TIMEOUT = 30
LEASE_IDENTITY = {
    "GIT_AUTHOR_NAME": "synthesis-coordination",
    "GIT_AUTHOR_EMAIL": "coordination@localhost",
    "GIT_COMMITTER_NAME": "synthesis-coordination",
    "GIT_COMMITTER_EMAIL": "coordination@localhost",
}


def lease_configuration(board: Path) -> dict | None:
    """Read the opt-in lease config that lives beside the board.

    The OS file lock serializes sessions that share one filesystem. File-sync
    services replicate the board but provide no mutual exclusion, so
    same-resource writes from two machines need a real compare-and-swap. A
    ``lease.json`` beside the board opts that board into publishing every
    mutation through an atomic git ref update on a shared remote; the local
    board file becomes a mirror of the leased ref.
    """
    path = board.parent / LEASE_CONFIG_NAME
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"coordination lease config unreadable: {path}: {exc}")
    remote = data.get("remote")
    if not isinstance(remote, str) or not remote:
        raise RuntimeError(f"coordination lease config lacks a remote: {path}")
    ref = data.get("ref", LEASE_DEFAULT_REF)
    if not isinstance(ref, str) or not ref.startswith("refs/"):
        raise RuntimeError(f"coordination lease ref must live under refs/: {path}")
    repository = Path(
        str(data.get("repository", board.parent / ".lease-repo"))
    ).expanduser()
    return {"remote": remote, "ref": ref, "repository": repository}


def git_lease(repository: Path, *arguments: str, input_text: str | None = None):
    try:
        return subprocess.run(
            ["git", "--git-dir", str(repository), *arguments],
            capture_output=True,
            text=True,
            timeout=LEASE_GIT_TIMEOUT,
            check=False,
            input=input_text,
            env={**os.environ, **LEASE_IDENTITY},
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"coordination lease git call timed out: git {' '.join(arguments[:2])}"
        )
    except FileNotFoundError:
        raise RuntimeError("coordination lease requires git on PATH")


def lease_repository(config: dict) -> Path:
    repository = config["repository"]
    if not (repository / "HEAD").is_file():
        repository.mkdir(parents=True, exist_ok=True)
        created = subprocess.run(
            ["git", "init", "--bare", "--quiet", str(repository)],
            capture_output=True,
            text=True,
            check=False,
        )
        if created.returncode != 0:
            raise RuntimeError(
                f"coordination lease repository init failed: {created.stderr.strip()}"
            )
    return repository


def lease_fetch(config: dict) -> tuple[str, str | None]:
    """Return the remote ref tip and board content, or ("", None) pre-bootstrap."""
    repository = lease_repository(config)
    listed = git_lease(repository, "ls-remote", config["remote"], config["ref"])
    if listed.returncode != 0:
        raise RuntimeError(
            f"coordination lease remote unreachable: {listed.stderr.strip()}"
        )
    if not listed.stdout.strip():
        return "", None
    fetched = git_lease(
        repository,
        "fetch",
        "--quiet",
        config["remote"],
        f"+{config['ref']}:refs/lease/current",
    )
    if fetched.returncode != 0:
        raise RuntimeError(
            f"coordination lease fetch failed: {fetched.stderr.strip()}"
        )
    sha = git_lease(repository, "rev-parse", "refs/lease/current").stdout.strip()
    names = git_lease(
        repository, "ls-tree", "--name-only", "refs/lease/current"
    ).stdout.split()
    if len(names) != 1:
        raise RuntimeError(
            "coordination lease ref must contain exactly one board file, found: "
            + (", ".join(names) or "none")
        )
    shown = git_lease(repository, "show", f"refs/lease/current:{names[0]}")
    if shown.returncode != 0:
        raise RuntimeError(
            f"coordination lease board unreadable: {shown.stderr.strip()}"
        )
    return sha, shown.stdout


def lease_publish(
    config: dict, board_name: str, content: str, expected_sha: str
) -> tuple[bool, str]:
    repository = lease_repository(config)
    blob = git_lease(repository, "hash-object", "-w", "--stdin", input_text=content)
    if blob.returncode != 0:
        raise RuntimeError(f"coordination lease blob write failed: {blob.stderr.strip()}")
    tree = git_lease(
        repository,
        "mktree",
        input_text=f"100644 blob {blob.stdout.strip()}\t{board_name}\n",
    )
    if tree.returncode != 0:
        raise RuntimeError(f"coordination lease tree write failed: {tree.stderr.strip()}")
    commit_arguments = ["commit-tree", tree.stdout.strip(), "-m", "Update coordination board"]
    if expected_sha:
        commit_arguments.extend(["-p", expected_sha])
    committed = git_lease(repository, *commit_arguments)
    if committed.returncode != 0:
        raise RuntimeError(
            f"coordination lease commit failed: {committed.stderr.strip()}"
        )
    pushed = git_lease(
        repository,
        "push",
        "--quiet",
        config["remote"],
        f"{committed.stdout.strip()}:{config['ref']}",
        f"--force-with-lease={config['ref']}:{expected_sha}",
    )
    if pushed.returncode == 0:
        return True, ""
    return False, pushed.stderr.strip()


LEASE_DECLARATION = re.compile(r"(?m)^Lease: (\S+)[ \t]*$")


def declared_lease(content: str) -> str | None:
    """The remote a board says it is leased to, from its header declaration.

    The declaration travels IN the board content, so it replicates with the
    board (file sync, mirrors, the leased ref itself). A machine whose
    `lease.json` has not arrived yet — or that lost it — then refuses to
    mutate a lease-managed board instead of writing a local-only change that
    the next lease refetch would silently drop.
    """
    match = LEASE_DECLARATION.search(content)
    return match.group(1) if match else None


def ensure_lease_declaration(content: str, remote: str) -> str:
    existing = declared_lease(content)
    if existing == remote:
        return content
    if existing is not None:
        return LEASE_DECLARATION.sub(f"Lease: {remote}", content, count=1)
    schema = re.search(r"(?m)^Schema:\s*v\d+[ \t]*$", content)
    if schema is None:
        return f"Lease: {remote}\n" + content
    return content[: schema.end()] + f"\nLease: {remote}" + content[schema.end() :]


def remove_lease_declaration(content: str) -> str:
    return re.sub(r"(?m)^Lease: \S+[ \t]*\n?", "", content, count=1)


def lease_update(
    board: Path, config: dict, operation, *, declare: bool = True
) -> None:
    failure = ""
    for _ in range(LEASE_RETRIES):
        sha, content = lease_fetch(config)
        if content is None:
            content = (
                board.read_text(encoding="utf-8") if board.exists() else template()
            )
        updated = operation(content)
        if declare:
            updated = ensure_lease_declaration(updated, config["remote"])
        published, failure = lease_publish(config, board.name, updated, sha)
        if published:
            write_board(board, updated)
            return
    raise RuntimeError(
        "coordination lease compare-and-swap failed after "
        f"{LEASE_RETRIES} attempts: {failure}"
    )


def lease_refresh(board: Path) -> dict:
    """Best-effort mirror refresh for read paths; reports instead of raising."""
    try:
        config = lease_configuration(board)
    except RuntimeError as exc:
        return {"configured": True, "refreshed": False, "error": str(exc)}
    if config is None:
        return {"configured": False}
    try:
        sha, content = lease_fetch(config)
    except RuntimeError as exc:
        return {"configured": True, "refreshed": False, "error": str(exc)}
    if content is not None and (
        not board.exists() or board.read_text(encoding="utf-8") != content
    ):
        write_board(board, content)
    return {"configured": True, "refreshed": True, "sha": sha}


def locked_update(board: Path, operation) -> None:
    board.parent.mkdir(parents=True, exist_ok=True)
    lock_path = board.parent / ".active-sessions.lock"
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        config = lease_configuration(board)
        if config is not None:
            lease_update(board, config, operation)
            return
        content = board.read_text(encoding="utf-8") if board.exists() else template()
        declared = declared_lease(content)
        if declared is not None:
            raise RuntimeError(
                f"board declares a coordination lease ({declared}) but "
                f"{board.parent / LEASE_CONFIG_NAME} is missing on this "
                "machine; copy the lease configuration here, or run "
                "'lease-disable --local-only' only if the lease is being "
                "retired everywhere"
            )
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
    lease = lease_refresh(args.board)
    if not args.board.is_file():
        if lease.get("error"):
            print(f"COORDINATION ERROR: {lease['error']}", file=sys.stderr)
            return 10 if args.strict else 0
        print(f"No coordination board: {args.board}")
        return 0
    content = args.board.read_text(encoding="utf-8")
    sessions = rows(content)
    problems = validate_sessions(sessions)
    if lease.get("error"):
        problems.append(
            f"lease refresh failed; local mirror may be stale: {lease['error']}"
        )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "board": str(args.board),
        "lease": lease,
        "sessions": [
            {
                **asdict(session),
                "stale": stale(session, args.stale_after_minutes),
            }
            for session in sessions
        ],
        "problems": problems,
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

    try:
        locked_update(args.board, operation)
    except RuntimeError as exc:
        print(f"coordination migrate failed: {exc}", file=sys.stderr)
        return 10
    print(f"Migrated {args.board} to schema v{SCHEMA_VERSION}.")
    return 0


def command_lease_disable(args) -> int:
    board = args.board
    board.parent.mkdir(parents=True, exist_ok=True)
    lock_path = board.parent / ".active-sessions.lock"
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            config = lease_configuration(board)
        except RuntimeError as exc:
            print(f"coordination lease-disable failed: {exc}", file=sys.stderr)
            return 10
        if args.local_only:
            if config is not None:
                print(
                    "coordination lease-disable refused: lease.json is present, "
                    "so the sanctioned path is 'lease-disable' without "
                    "--local-only (it retires the lease on the remote too)",
                    file=sys.stderr,
                )
                return 10
            if not board.is_file():
                print(f"No coordination board: {board}", file=sys.stderr)
                return 10
            content = board.read_text(encoding="utf-8")
            if declared_lease(content) is None:
                print("Board declares no lease; nothing to disable.")
                return 0
            write_board(board, remove_lease_declaration(content))
            print(
                "Lease declaration removed from the local board only. If the "
                "lease remote still exists, machines with lease.json will "
                "republish it; this path is for retiring an unreachable lease."
            )
            return 0
        if config is None:
            print(
                "coordination lease-disable failed: no lease.json beside the "
                "board; use --local-only only when retiring a lease whose "
                "remote is gone",
                file=sys.stderr,
            )
            return 10
        try:
            lease_update(board, config, remove_lease_declaration, declare=False)
        except RuntimeError as exc:
            print(f"coordination lease-disable failed: {exc}", file=sys.stderr)
            return 10
        retired = board.parent / (
            f"{LEASE_CONFIG_NAME}.disabled-{datetime.now().strftime('%Y%m%dT%H%M%S')}"
        )
        os.replace(board.parent / LEASE_CONFIG_NAME, retired)
        print(
            "Lease declaration removed and published to the remote. Local "
            f"lease config moved to {retired}. Remove lease.json on every "
            "other machine before its next board write, or it will "
            "re-enable the lease."
        )
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
    lease_line = ""
    try:
        lease = lease_configuration(args.board)
        if lease is None and declared_lease(content) is not None:
            problems.append(
                f"board declares a coordination lease "
                f"({declared_lease(content)}) but lease.json is missing "
                "beside it; mutations will refuse until the configuration "
                "is copied here or the lease is retired"
            )
        if lease is not None:
            sha, remote_content = lease_fetch(lease)
            if remote_content is None:
                problems.append(
                    "lease is configured but the remote ref has never been "
                    "published; run any mutating command to bootstrap it"
                )
            elif remote_content != content:
                problems.append(
                    "local board mirror differs from the lease remote; run "
                    "status to refresh the mirror"
                )
            else:
                lease_line = f", lease in sync at {sha[:12]}"
    except RuntimeError as exc:
        problems.append(str(exc))
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
        f"{len(sessions)} session(s){lease_line}"
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
    lease_disable = commands.add_parser(
        "lease-disable",
        help="Retire the board's lease declaration (CAS-published by default; "
        "--local-only is the unreachable-remote escape).",
    )
    lease_disable.add_argument("--local-only", action="store_true")
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
    if args.command == "lease-disable":
        return command_lease_disable(args)
    return command_doctor(args)


if __name__ == "__main__":
    sys.exit(main())

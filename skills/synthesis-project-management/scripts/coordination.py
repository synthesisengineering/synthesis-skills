#!/usr/bin/env python3
"""Manage synthesis cross-agent claims, handoffs, and project ownership."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import fcntl
import json
import os
import re
import shutil
import socket
import subprocess
import platform
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from pointer_lock import locked_pointer
from peer_addressing import (
    CLIENT_CODEX,
    SelfIdentity,
    all_seats,
    delivery_lanes,
    detect_self,
    lane_invocations,
    load_receipts,
    mark_seen,
    read_seat,
    remove_seat,
    render_inbox,
    seat_for_identity,
    unread_messages,
    write_receipt,
    write_seat,
)
from coordination_schema import (
    SCHEMA_VERSION,
    V1_COLUMNS,
    V2_COLUMNS,
    V3_COLUMNS,
    V4_COLUMNS,
    SessionIdentity,
    column_count_error,
    display_id,
    engine_remedy,
    newer_installed_engine,
    identity_lookup_keys,
    new_identity,
    selector_keys,
    selector_matches,
    validate_identity,
)


DEFAULT_BOARD = Path.home() / ".synthesis" / "coordination" / "active-sessions.md"
DEFAULT_ACTIVE_PROJECT = Path.home() / ".synthesis" / "active-project.json"
TABLE_COLUMNS = V4_COLUMNS


def table_header(columns: tuple[str, ...]) -> str:
    return (
        "| " + " | ".join(columns) + " |\n"
        + "|"
        + "|".join("---" for _ in columns)
        + "|"
    )


TABLE_HEADER = table_header(TABLE_COLUMNS)

# A client session ref is the client-native delivery handle for a session,
# recorded as a scheme-prefixed URI so the delivery adapter stays at the edge:
#   ccd:local_<uuid>   Claude Code chat session (ccd send_message target)
#   codex:<uuid>       OpenAI Codex session (board bus is its delivery lane)
# The scheme namespace is open (an a2a: adapter would slot in the same way).
CLIENT_REF_PATTERN = re.compile(r"^[a-z][a-z0-9+.-]*:[A-Za-z0-9._:@-]+$")


def normalize_client_ref(value: str) -> str:
    candidate = (value or "").strip()
    if candidate in {"", "-"}:
        return ""
    if not CLIENT_REF_PATTERN.match(candidate):
        raise ValueError(
            f"client session ref must be scheme-prefixed (like ccd:local_...): "
            f"{candidate!r}"
        )
    return candidate


def detect_client_ref() -> str:
    """Best available self-identity for the running client session.

    SYNTHESIS_CLIENT_SESSION_REF is the generic override any client (or its
    SessionStart hook) can export. Claude Code exposes its chat-session id as
    CLAUDE_CODE_HOST_SESSION_ID, which is exactly what ccd send_message
    targets. An invalid value fails closed rather than registering garbage.
    """
    explicit = os.environ.get("SYNTHESIS_CLIENT_SESSION_REF", "").strip()
    if explicit:
        return normalize_client_ref(explicit)
    host = os.environ.get("CLAUDE_CODE_HOST_SESSION_ID", "").strip()
    if host:
        return normalize_client_ref(f"ccd:{host}")
    harness = os.environ.get("CLAUDE_CODE_SESSION_ID", "").strip()
    if harness:
        # A terminal session has no desktop chat id; its harness session id
        # is still a real delivery handle (the peer registry maps it to a
        # socket), so it registers under the cc: scheme.
        return normalize_client_ref(f"cc:{harness}")
    return ""


def self_identity(requested_ref: str = "") -> SelfIdentity:
    """What this shell knows about its own session, honoring an explicit ref."""
    identity = detect_self()
    if requested_ref.startswith("codex:") and identity.client != CLIENT_CODEX:
        return SelfIdentity(
            client=CLIENT_CODEX,
            harness_session_id=requested_ref[len("codex:"):],
            explicit_ref=requested_ref,
            pid=identity.pid,
        )
    if requested_ref and not identity.primary_ref:
        return SelfIdentity(explicit_ref=requested_ref, pid=identity.pid)
    return identity
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
    session_uuid: str
    compact_id: str
    speakable_id: str
    legacy_id: str
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
    client_ref: str = ""

    @property
    def identity(self) -> SessionIdentity:
        return SessionIdentity(
            self.session_uuid,
            self.compact_id,
            self.speakable_id,
            self.legacy_id,
        )

    @property
    def id(self) -> str:
        """Canonical machine id, or the legacy selector on an unmigrated row."""
        return self.session_uuid or self.legacy_id

    @property
    def label(self) -> str:
        return display_id(self.identity)

    def cells(self, columns: tuple[str, ...] = TABLE_COLUMNS) -> list[str]:
        values = [
            self.session_uuid,
            self.compact_id,
            self.speakable_id,
            self.legacy_id,
            self.agent,
            self.machine,
            self.client_ref or "-",
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
        if "client session ref" not in columns:
            del values[6]
        return values


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
        "7. Address peers through resolve — board identity, never client labels; "
        "resolve issues the delivery receipt the send gate requires, and an "
        "unresolvable peer gets a board message, not a broadcast.\n"
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


# AGENT HEURISTIC: the controlling plan fixes the enforcement behavior but not
# the receipt serialization. Keep the schema small, explicit, and hash-bound so
# R5 can generalize it without treating prose success as authority.
CHECK_STAGED_UNVERIFIED_REMAINDER = (
    "committing-process identity before selector resolution",
    "claim legitimacy and semantic correctness of staged bytes",
    "state mutation after the caller's final receipt revalidation",
)
CHECK_STAGED_REMEDIATION = (
    "Use an isolated worktree with a distinct branch, claim that exact "
    "worktree and every staged source area on the lease-backed coordination "
    "board, then stage only paths covered by that claim."
)


def _check_staged_payload(
    args,
    outcome: str,
    *,
    selector_source: str | None = None,
    outside_paths: list[str] | None = None,
    detail: str | None = None,
    remediation: str | None = None,
    receipt: dict | None = None,
) -> dict:
    payload = {
        "control_class": "enforced-gate",
        "authority_label": "DESIGN CONSTRAINT (Fable, controlling plan)",
        "enforcement_outcome": outcome,
        "issues_authority_receipt": receipt is not None,
        "board": str(args.board),
        "selector_source": selector_source,
        "outside_paths": outside_paths or [],
        "unverified_remainder": list(CHECK_STAGED_UNVERIFIED_REMAINDER),
    }
    if detail:
        payload["detail"] = detail
    if remediation:
        payload["remediation"] = remediation
    if receipt is not None:
        payload["receipt"] = receipt
    return payload


def _emit_check_staged(args, payload: dict) -> None:
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        "coordination check-staged: "
        f"{payload['enforcement_outcome']} "
        f"(authority-receipt={'yes' if payload['issues_authority_receipt'] else 'no'})"
    )
    if payload.get("detail"):
        print(f"detail: {payload['detail']}")
    if payload.get("outside_paths"):
        print("outside claim: " + ", ".join(payload["outside_paths"]))
    if payload.get("remediation"):
        print("remediation: " + payload["remediation"])
    print(
        "unverified remainder: "
        + "; ".join(payload["unverified_remainder"])
    )


def _git_bytes(repository: Path, *arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *arguments],
        cwd=repository,
        capture_output=True,
        check=False,
    )


def _repository_state(repository: Path) -> tuple[Path, str]:
    requested = repository.expanduser()
    if not requested.is_dir():
        raise RuntimeError(f"repository is not a directory: {requested}")
    top = _git_bytes(requested, "rev-parse", "--show-toplevel")
    if top.returncode != 0:
        detail = top.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(detail or f"not a Git worktree: {requested}")
    root = Path(top.stdout.decode("utf-8", errors="strict").strip()).resolve()
    branch_result = _git_bytes(root, "branch", "--show-current")
    if branch_result.returncode != 0:
        detail = branch_result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(detail or f"cannot read branch for {root}")
    branch = branch_result.stdout.decode("utf-8", errors="strict").strip()
    if not branch:
        raise RuntimeError(
            "detached HEAD has no exact branch identity for a board workspace claim"
        )
    return root, branch


def _staged_inventory(repository: Path) -> tuple[list[str], str]:
    names = _git_bytes(
        repository,
        "diff",
        "--cached",
        "--name-only",
        "-z",
        "--no-renames",
    )
    if names.returncode != 0:
        detail = names.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(detail or "cannot enumerate staged paths")
    paths = [
        value.decode("utf-8", errors="surrogateescape")
        for value in names.stdout.split(b"\0")
        if value
    ]
    for path in paths:
        components = Path(path).parts
        if Path(path).is_absolute() or ".." in components:
            raise RuntimeError(f"Git returned an unsafe staged path: {path!r}")
    tree = _git_bytes(repository, "write-tree")
    if tree.returncode != 0:
        detail = tree.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(detail or "cannot materialize the staged tree")
    return sorted(paths), tree.stdout.decode("ascii", errors="strict").strip()


def _workspace_registered(session: Session, repository: Path, branch: str) -> bool:
    repository_real = Path(os.path.realpath(repository))
    for workspace in session.workspaces:
        path, claimed_branch = workspace_parts(workspace)
        if claimed_branch != branch:
            continue
        if Path(os.path.realpath(os.path.expanduser(path))) == repository_real:
            return True
    return False


def _absolute_claim_pattern(claim: str, repository: Path) -> str | None:
    raw = plain(claim)
    if not raw:
        return None
    expanded = os.path.expanduser(raw)
    candidate = Path(expanded)
    if not candidate.is_absolute():
        parts = candidate.parts
        base = (
            repository.parent
            if parts and parts[0] == repository.name
            else repository
        )
        candidate = base / candidate
    # AGENT HEURISTIC: board claims can be recorded through a symlinked macOS
    # path spelling (for example /tmp while Git resolves /private/tmp). Resolve
    # the existing prefix of a glob so claim and staged candidates share one
    # filesystem identity before segment matching.
    return os.path.realpath(candidate)


# AGENT HEURISTIC: claim globs need segment semantics; Python fnmatch lets `*`
# cross separators, while pathlib's `**` behavior does not cover the board's
# common trailing-`/**` subtree form. This small matcher makes both explicit.
def _glob_matches_path(pattern: str, candidate: str) -> bool:
    """Match path-segment globs without allowing ``*`` to cross ``/``."""
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
                    candidate_parts[candidate_index], pattern_parts[pattern_index]
                )
                and matches(pattern_index + 1, candidate_index + 1)
            )
        cache[key] = result
        return result

    return matches(0, 0)


def _claim_authorizes_path(
    claim: str, repository: Path, staged_path: str
) -> bool:
    pattern = _absolute_claim_pattern(claim, repository)
    if pattern is None:
        return False
    candidate = os.path.realpath(repository / staged_path)
    if any(token in pattern for token in ("*", "?", "[")):
        return _glob_matches_path(pattern, candidate)
    boundary = Path(pattern)
    candidate_path = Path(candidate)
    if plain(claim).endswith("/") or boundary.is_dir():
        return candidate_path == boundary or boundary in candidate_path.parents
    return candidate_path == boundary


def _outside_claim(
    session: Session, repository: Path, staged_paths: list[str]
) -> list[str]:
    return [
        path
        for path in staged_paths
        if not any(
            _claim_authorizes_path(claim, repository, path)
            for claim in session.claims
        )
    ]


def _resolve_check_selector(args) -> tuple[str | None, str | None]:
    explicit = getattr(args, "id", None)
    if explicit:
        return explicit, "command-line"
    environment = os.environ.get("SYNTHESIS_COORDINATION_SESSION", "").strip()
    if environment:
        return environment, "environment"
    pointer = Path(args.active_project_file).expanduser()
    if not pointer.exists():
        return None, None
    if pointer.is_symlink():
        raise RuntimeError(f"active-project pointer must not be a symlink: {pointer}")
    try:
        payload = json.loads(pointer.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"active-project pointer is unreadable: {exc}") from exc
    owner = str(payload.get("owner_session") or "").strip()
    if not owner:
        raise RuntimeError("active-project pointer has no owner_session selector")
    return owner, "active-project"


def _append_override_message(
    content: str,
    session: Session,
    repository: Path,
    branch: str,
    staged_tree: str,
    staged_paths: list[str],
    reason: str,
) -> str:
    marker = re.search(
        r"(?m)^---[ \t]*\n\n## Protocol(?:[^\n]*)?$",
        content,
    )
    if marker is None:
        raise RuntimeError("board lacks Protocol boundary")
    body = (
        f"### recorded-staged-claim-override — {timestamp()}\n\n"
        f"Session: {session.session_uuid}\n\n"
        f"Repository: {repository} @ {sanitize(branch)}\n\n"
        f"Staged tree: {staged_tree}\n\n"
        f"Outside-claim paths: {', '.join(sanitize(path) for path in staged_paths)}\n\n"
        f"Reason: {sanitize(reason)}\n\n"
    )
    return content[: marker.start()] + body + content[marker.start() :]


def _check_staged_receipt(
    *,
    board: Path,
    board_text: str,
    session: Session,
    repository: Path,
    branch: str,
    staged_tree: str,
    staged_paths: list[str],
    enforcement_outcome: str,
    outside_paths: list[str],
    override_reason: str | None = None,
) -> dict:
    receipt = {
        "schema": "coordination-check-staged-v1",
        "schema_provenance": "AGENT HEURISTIC",
        "authority_label": "DESIGN CONSTRAINT (Fable, controlling plan)",
        "receipt_consumer": "synthesis-git-hooks pre-commit",
        "board": str(board),
        "board_sha256": hashlib.sha256(board_text.encode("utf-8")).hexdigest(),
        "session_uuid": session.session_uuid,
        "repository": str(repository),
        "branch": branch,
        "claims": session.claims,
        "enforcement_outcome": enforcement_outcome,
        "outside_paths": list(outside_paths),
        "staged_tree": staged_tree,
        "staged_paths": staged_paths,
        "issued_at": timestamp(),
        "invalidated_by": [
            "board content change",
            "session, worktree, or branch change",
            "Git index change",
        ],
    }
    if override_reason is not None:
        receipt["override_reason"] = override_reason
    canonical = json.dumps(receipt, sort_keys=True, separators=(",", ":"))
    receipt["binding_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return receipt


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
    if first in {"id", "session uuid"} or set(first) == {"-"}:
        return None
    return cells


def session_from_cells(cells: list[str]) -> Session:
    if len(cells) == len(V4_COLUMNS):
        raw_ref = plain(cells[6])
        return Session(
            session_uuid=plain(cells[0]),
            compact_id=plain(cells[1]),
            speakable_id=plain(cells[2]),
            legacy_id=plain(cells[3]),
            agent=plain(cells[4]),
            machine=plain(cells[5]),
            client_ref="" if raw_ref == "-" else raw_ref,
            project=plain(cells[7]),
            started=plain(cells[8]),
            heartbeat=plain(cells[9]),
            mode=plain(cells[10]),
            workspaces=split_values(cells[11]),
            goal=plain(cells[12]),
            claims=split_values(cells[13]),
            context_role=plain(cells[14]).lower(),
            status=plain(cells[15]).lower(),
        )
    if len(cells) == len(V3_COLUMNS):
        return Session(
            session_uuid=plain(cells[0]),
            compact_id=plain(cells[1]),
            speakable_id=plain(cells[2]),
            legacy_id=plain(cells[3]),
            agent=plain(cells[4]),
            machine=plain(cells[5]),
            project=plain(cells[6]),
            started=plain(cells[7]),
            heartbeat=plain(cells[8]),
            mode=plain(cells[9]),
            workspaces=split_values(cells[10]),
            goal=plain(cells[11]),
            claims=split_values(cells[12]),
            context_role=plain(cells[13]).lower(),
            status=plain(cells[14]).lower(),
        )
    if len(cells) == len(V2_COLUMNS):
        return Session(
            session_uuid="",
            compact_id="",
            speakable_id="",
            legacy_id=plain(cells[0]),
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
            session_uuid="",
            compact_id="",
            speakable_id="",
            legacy_id=plain(cells[0]),
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
    raise column_count_error(cells, __file__)


def with_identity(session: Session, identity: SessionIdentity) -> Session:
    return Session(
        session_uuid=identity.session_uuid,
        compact_id=identity.compact_id,
        speakable_id=identity.speakable_id,
        legacy_id=identity.legacy_id,
        agent=session.agent,
        machine=session.machine,
        client_ref=session.client_ref,
        project=session.project,
        started=session.started,
        heartbeat=session.heartbeat,
        mode=session.mode,
        workspaces=session.workspaces,
        goal=session.goal,
        claims=session.claims,
        context_role=session.context_role,
        status=session.status,
    )


def ensure_identities(sessions: list[Session]) -> list[Session]:
    """Assign UUIDv7 identities once, preserving legacy selectors explicitly."""
    identities = [session.identity for session in sessions if session.session_uuid]
    migrated: list[Session] = []
    for session in sessions:
        if session.session_uuid:
            migrated.append(session)
            continue
        identity = new_identity(identities, legacy_id=session.legacy_id)
        identities.append(identity)
        migrated.append(with_identity(session, identity))
    return migrated


def find_session(sessions: list[Session], selector: str) -> Session | None:
    matches = [
        session for session in sessions if selector_matches(session.identity, selector)
    ]
    if len(matches) > 1:
        raise RuntimeError(f"ambiguous session selector: {selector}")
    return matches[0] if matches else None


def rows(text: str) -> list[Session]:
    declared = board_schema(text)
    if declared is not None and declared > SCHEMA_VERSION:
        # Version skew between a shared board and the engines reading it is
        # permanent, not a transition: a release reaches sessions at different
        # times. A stale engine must never rewrite a newer board, and the one
        # useful thing it can say is which engine to run instead.
        raise ValueError(
            f"board declares schema v{declared}, newer than this engine's "
            f"v{SCHEMA_VERSION}; {engine_remedy(__file__)}"
        )
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


def board_schema(text: str) -> int | None:
    """The schema version a board declares in its header, or None."""
    match = re.search(r"(?m)^Schema:\s*v(\d+)\s*$", text)
    return int(match.group(1)) if match else None


def replace_table(
    text: str, sessions: list[Session], *, force_schema: int | None = None
) -> str:
    """Rewrite the Active sessions table, honoring the board's declared schema.

    A board keeps its declared schema until an explicit `migrate` passes
    force_schema — older clients on other machines parse the shared board, so
    an implicit rewrite here would fail them closed mid-flight. Client refs
    are dropped on a v3 emission and re-registered on the next claim after
    migration.
    """
    sessions = ensure_identities(sessions)
    declared = board_schema(text)
    effective = force_schema or declared or SCHEMA_VERSION
    columns = TABLE_COLUMNS if effective >= 4 else V3_COLUMNS
    rendered = [table_header(columns)]
    rendered.extend(
        "| " + " | ".join(sanitize(value) for value in session.cells(columns)) + " |"
        for session in sessions
    )
    block = "\n".join(rendered)
    # The heading group must not swallow blank lines: with `\s*` it captured
    # every existing padding line and re-emitted it plus one more, so each
    # rewrite grew the board by a line (over a thousand on a long-lived board).
    pattern = re.compile(r"(?ms)(^## Active sessions[ \t]*\n).*?(?=^## Messages\s*$)")
    if not pattern.search(text):
        raise ValueError("board lacks Active sessions and Messages sections")
    updated = pattern.sub(lambda match: match.group(1) + "\n" + block + "\n\n", text)
    if re.search(r"(?m)^Schema:\s*v\d+\s*$", updated):
        return re.sub(
            r"(?m)^Schema:\s*v\d+\s*$",
            f"Schema: v{effective}",
            updated,
            count=1,
        )
    marker = re.search(r"(?m)^## Active sessions\s*$", updated)
    if marker is None:
        raise ValueError("board lacks Active sessions heading")
    return (
        updated[: marker.start()]
        + f"Schema: v{effective}\n\n"
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


def _check_staged_board_snapshot(board: Path) -> str | None:
    """Return one lock/CAS-fenced authority snapshot for check-staged.

    AGENT HEURISTIC: a read followed by an unlocked mirror write can restore
    stale active bytes after another process releases the session. A leased
    board therefore publishes an identity mutation through the existing CAS
    path. The successful CAS is the read fence: on a concurrent advance it
    retries from the newer board before exposing local bytes. An unleased
    board is read under the same filesystem lock used by every mutation.
    """
    board.parent.mkdir(parents=True, exist_ok=True)
    lock_path = board.parent / ".active-sessions.lock"
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        config = lease_configuration(board)
        if config is not None:
            lease_update(board, config, lambda content: content)
            return board.read_text(encoding="utf-8")
        if not board.exists():
            return None
        content = board.read_text(encoding="utf-8")
        declared = declared_lease(content)
        if declared is not None:
            raise RuntimeError(
                f"board declares a coordination lease ({declared}) but "
                f"{board.parent / LEASE_CONFIG_NAME} is missing on this "
                "machine; restore the lease configuration before checking "
                "commit authority"
            )
        return content


def validate_sessions(sessions: list[Session]) -> list[str]:
    problems: list[str] = []
    seen_selectors: dict[tuple[str, object], str] = {}
    for session in sessions:
        if session.session_uuid:
            for issue in validate_identity(session.identity):
                problems.append(f"session {session.label}: {issue}")
        for normalized in identity_lookup_keys(session.identity):
            previous = seen_selectors.get(normalized)
            if previous is not None:
                problems.append(
                    f"duplicate or ambiguous session selector: {normalized[1]} "
                    f"({previous}, {session.label})"
                )
            else:
                seen_selectors[normalized] = session.label
        if session.context_role not in {"owner", "contributor", "none"}:
            problems.append(
                f"session {session.label} has invalid context role: "
                f"{session.context_role}"
            )
    live = [session for session in sessions if active(session)]
    seen_refs: dict[str, str] = {}
    for session in live:
        if not session.client_ref:
            continue
        previous = seen_refs.get(session.client_ref)
        if previous is not None:
            problems.append(
                f"duplicate active client session ref {session.client_ref} "
                f"({previous}, {session.label}); release the stale row or "
                "re-claim with --session to update the existing one"
            )
        else:
            seen_refs[session.client_ref] = session.label
    for index, left in enumerate(live):
        if left.context_role == "contributor":
            for claim in left.claims:
                if claims_context(claim):
                    problems.append(
                        f"session {left.label} is a contributor but claims context: {claim}"
                    )
        for right in live[index + 1 :]:
            for left_claim in left.claims:
                for right_claim in right.claims:
                    if overlaps(left_claim, right_claim):
                        problems.append(
                            f"{left.label}:{left_claim} overlaps "
                            f"{right.label}:{right_claim}"
                        )
            for left_workspace in left.workspaces:
                for right_workspace in right.workspaces:
                    if workspace_conflict(left_workspace, right_workspace):
                        problems.append(
                            f"{left.label} and {right.label} share workspace or branch: "
                            f"{left_workspace} / {right_workspace}. Use an isolated "
                            "worktree with a distinct branch and claim that exact "
                            "workspace before writing"
                        )
            if (
                left.project not in {"", "unknown", "none"}
                and left.project == right.project
                and left.context_role == "owner"
                and right.context_role == "owner"
            ):
                problems.append(
                    f"{left.label} and {right.label} both own context for {left.project}"
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
        "board_schema": board_schema(content),
        "board": str(args.board),
        "lease": lease,
        "sessions": [
            {
                **asdict(session),
                "id": session.id,
                "display_id": session.label,
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
                    f"STALE active session {session.label}: heartbeat "
                    f"{session.heartbeat}",
                    file=sys.stderr,
                )
        for problem in payload["problems"]:
            print(f"COORDINATION ERROR: {problem}", file=sys.stderr)
    return 10 if args.strict and (payload["problems"] or any(
        item["stale"] for item in payload["sessions"]
    )) else 0


def command_check_staged(args) -> int:
    selector_source: str | None = None
    try:
        repository, branch = _repository_state(Path(args.repository))
        staged_paths, staged_tree = _staged_inventory(repository)
    except (OSError, UnicodeError, RuntimeError) as exc:
        payload = _check_staged_payload(
            args,
            "unverifiable-repository-or-index",
            detail=str(exc),
            remediation=CHECK_STAGED_REMEDIATION,
        )
        _emit_check_staged(args, payload)
        return 10

    try:
        board_text = _check_staged_board_snapshot(args.board)
    except (OSError, UnicodeError, ValueError, RuntimeError) as exc:
        payload = _check_staged_payload(
            args,
            "unverifiable-lease-refresh",
            detail=str(exc),
            remediation=CHECK_STAGED_REMEDIATION,
        )
        _emit_check_staged(args, payload)
        return 10
    if board_text is None:
        payload = _check_staged_payload(
            args,
            "unverifiable-missing-board",
            detail=f"coordination board is unavailable: {args.board}",
            remediation=CHECK_STAGED_REMEDIATION,
        )
        _emit_check_staged(args, payload)
        return 10

    try:
        required = ("## Active sessions", "## Messages", "## Protocol")
        missing = [heading for heading in required if heading not in board_text]
        if missing:
            raise RuntimeError("board missing " + ", ".join(missing))
        sessions = rows(board_text)
        problems = validate_sessions(sessions)
        if problems:
            raise RuntimeError("; ".join(problems))
        selector, selector_source = _resolve_check_selector(args)
        if selector is None:
            raise RuntimeError(
                "no committing session selector; pass --session, set "
                "SYNTHESIS_COORDINATION_SESSION, or provide an owned "
                "active-project pointer"
            )
        session = find_session(sessions, selector)
    except (OSError, UnicodeError, ValueError, RuntimeError) as exc:
        payload = _check_staged_payload(
            args,
            "unverifiable-board-or-session",
            selector_source=selector_source,
            detail=str(exc),
            remediation=CHECK_STAGED_REMEDIATION,
        )
        _emit_check_staged(args, payload)
        return 10

    if session is None:
        payload = _check_staged_payload(
            args,
            "refused-session-not-found",
            selector_source=selector_source,
            detail=f"session selector is not present on the board: {selector}",
            remediation=CHECK_STAGED_REMEDIATION,
        )
        _emit_check_staged(args, payload)
        return 10
    if not active(session):
        payload = _check_staged_payload(
            args,
            "refused-inactive-session",
            selector_source=selector_source,
            detail=f"session {session.label} has status {session.status}",
            remediation=CHECK_STAGED_REMEDIATION,
        )
        _emit_check_staged(args, payload)
        return 10
    if not session.session_uuid:
        payload = _check_staged_payload(
            args,
            "unverifiable-session-identity",
            selector_source=selector_source,
            detail="the selected legacy board row has no UUID identity",
            remediation=CHECK_STAGED_REMEDIATION,
        )
        _emit_check_staged(args, payload)
        return 10
    if not _workspace_registered(session, repository, branch):
        payload = _check_staged_payload(
            args,
            "refused-unregistered-worktree",
            selector_source=selector_source,
            detail=f"{repository} @ {branch} is not an exact workspace claim",
            remediation=CHECK_STAGED_REMEDIATION,
        )
        _emit_check_staged(args, payload)
        return 10

    if not staged_paths:
        payload = _check_staged_payload(
            args,
            "no-staged-paths",
            selector_source=selector_source,
            detail="the Git index names no staged paths; no authority receipt issued",
        )
        _emit_check_staged(args, payload)
        return 0

    outside_paths = _outside_claim(session, repository, staged_paths)
    override_reason = sanitize(str(args.override_reason or ""))
    if outside_paths and not override_reason:
        payload = _check_staged_payload(
            args,
            "refused-outside-claim",
            selector_source=selector_source,
            outside_paths=outside_paths,
            detail=(
                f"{len(outside_paths)} of {len(staged_paths)} staged paths "
                "fall outside the selected session's claim"
            ),
            remediation=CHECK_STAGED_REMEDIATION,
        )
        _emit_check_staged(args, payload)
        return 10

    if outside_paths:
        override_state: dict[str, object] = {}

        def record_override(content: str) -> str:
            current = rows(content)
            problems = validate_sessions(current)
            if problems:
                raise RuntimeError("; ".join(problems))
            current_session = find_session(current, selector)
            if current_session is None or not active(current_session):
                raise RuntimeError("selected session is missing or inactive")
            if not current_session.session_uuid:
                raise RuntimeError("selected session has no UUID identity")
            if not _workspace_registered(current_session, repository, branch):
                raise RuntimeError("worktree or branch is no longer registered")
            current_paths, current_tree = _staged_inventory(repository)
            if current_paths != staged_paths or current_tree != staged_tree:
                raise RuntimeError(
                    "Git index changed before the override could be recorded"
                )
            current_outside = _outside_claim(
                current_session, repository, current_paths
            )
            override_state["session"] = current_session
            override_state["outside"] = current_outside
            if not current_outside:
                override_state["recorded"] = False
                return content
            override_state["recorded"] = True
            return _append_override_message(
                content,
                current_session,
                repository,
                branch,
                current_tree,
                current_outside,
                override_reason,
            )

        try:
            locked_update(args.board, record_override)
            board_text = args.board.read_text(encoding="utf-8")
        except (OSError, UnicodeError, ValueError, RuntimeError) as exc:
            payload = _check_staged_payload(
                args,
                "refused-override-revalidation",
                selector_source=selector_source,
                outside_paths=outside_paths,
                detail=str(exc),
                remediation=CHECK_STAGED_REMEDIATION,
            )
            _emit_check_staged(args, payload)
            return 10
        session = override_state["session"]  # type: ignore[assignment]
        recorded = bool(override_state["recorded"])
        outside_paths = list(override_state["outside"])  # type: ignore[arg-type]
        outcome = "recorded-override" if recorded else "passed-inside-claim"
        receipt = _check_staged_receipt(
            board=args.board,
            board_text=board_text,
            session=session,  # type: ignore[arg-type]
            repository=repository,
            branch=branch,
            staged_tree=staged_tree,
            staged_paths=staged_paths,
            enforcement_outcome=outcome,
            outside_paths=outside_paths if recorded else [],
            override_reason=override_reason if recorded else None,
        )
        payload = _check_staged_payload(
            args,
            outcome,
            selector_source=selector_source,
            outside_paths=outside_paths if recorded else [],
            detail=(
                "outside-claim authority was recorded on the board"
                if recorded
                else "a concurrent board update brought every staged path inside claim"
            ),
            receipt=receipt,
        )
        _emit_check_staged(args, payload)
        return 0

    receipt = _check_staged_receipt(
        board=args.board,
        board_text=board_text,
        session=session,
        repository=repository,
        branch=branch,
        staged_tree=staged_tree,
        staged_paths=staged_paths,
        enforcement_outcome="passed-inside-claim",
        outside_paths=[],
    )
    payload = _check_staged_payload(
        args,
        "passed-inside-claim",
        selector_source=selector_source,
        detail=(
            f"all {len(staged_paths)} staged paths are covered by session "
            f"{session.label}"
        ),
        receipt=receipt,
    )
    _emit_check_staged(args, payload)
    return 0


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

    try:
        requested_ref = (
            normalize_client_ref(args.client_ref)
            if getattr(args, "client_ref", None)
            else detect_client_ref()
        )
    except ValueError as exc:
        print(f"coordination claim refused: {exc}", file=sys.stderr)
        return 10

    claimed: dict[str, object] = {}

    def operation(content: str) -> str:
        current = ensure_identities(rows(content))
        now = timestamp()
        selector = getattr(args, "id", None)
        existing_self = find_session(current, selector) if selector else None
        if (
            selector
            and existing_self is None
            and not all(kind == "legacy" for kind, _ in selector_keys(selector))
        ):
            raise RuntimeError(
                "strong session selector was not found; omit --session to "
                "allocate a new identity or use an unused legacy label"
            )
        if existing_self is None and not selector and requested_ref:
            # The same client session re-claiming without a selector updates
            # its own row instead of allocating another identity.
            same_seat = [
                session
                for session in current
                if active(session) and session.client_ref == requested_ref
            ]
            if len(same_seat) > 1:
                raise RuntimeError(
                    f"client session ref {requested_ref} has "
                    f"{len(same_seat)} active rows ("
                    + ", ".join(session.label for session in same_seat)
                    + "); release the stale ones before claiming"
                )
            if same_seat:
                existing_self = same_seat[0]
                claimed["reused"] = existing_self.identity.compact_id
        identity = (
            existing_self.identity
            if existing_self is not None
            else new_identity(
                (session.identity for session in current),
                legacy_id=selector or "",
            )
        )
        claimed["identity"] = identity
        claimed["board_schema"] = board_schema(content)
        replacement = Session(
            session_uuid=identity.session_uuid,
            compact_id=identity.compact_id,
            speakable_id=identity.speakable_id,
            legacy_id=identity.legacy_id,
            agent=args.agent,
            machine=args.machine,
            client_ref=requested_ref
            or (existing_self.client_ref if existing_self else ""),
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
            replacement
            if existing_self is not None
            and session.session_uuid == existing_self.session_uuid
            else session
            for session in current
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
    identity = claimed["identity"]
    legacy = f"; legacy={identity.legacy_id}" if identity.legacy_id else ""
    print(
        f"Claimed {', '.join(requested)} for session {identity.compact_id} "
        f"({identity.speakable_id}; uuid={identity.session_uuid}{legacy})."
    )
    seat = write_seat(
        args.board,
        session_uuid=identity.session_uuid,
        compact_id=identity.compact_id,
        machine=args.machine,
        identity=self_identity(requested_ref),
    )
    if seat is not None:
        print(f"Seat recorded at {seat} (delivery handles for peer resolution).")
    if claimed.get("reused"):
        print(
            "Reused this client session's existing active row "
            f"({claimed['reused']}) instead of allocating a new identity."
        )
    if requested_ref:
        declared = claimed.get("board_schema")
        if declared is not None and declared < 4:
            print(
                f"Client session ref {requested_ref} was detected but the "
                f"board declares schema v{declared}, which has no column for "
                "it; run 'coordination.py migrate' once every machine's "
                "client is current to enable peer-session resolution."
            )
        else:
            print(f"Registered client session ref {requested_ref}.")
    return 0


def command_heartbeat(args) -> int:
    updated: dict[str, SessionIdentity] = {}

    def operation(content: str) -> str:
        current = ensure_identities(rows(content))
        session = find_session(current, args.id)
        if session is None:
            raise RuntimeError(f"session not found: {args.id}")
        if not active(session):
            raise RuntimeError(f"session is not active: {args.id}")
        session.heartbeat = timestamp()
        updated["identity"] = session.identity
        return replace_table(content, current)

    try:
        locked_update(args.board, operation)
    except RuntimeError as exc:
        print(f"coordination heartbeat failed: {exc}", file=sys.stderr)
        return 10
    print(f"Heartbeat updated for session {updated['identity'].compact_id}.")
    existing = read_seat(args.board, updated["identity"].session_uuid)
    if existing is not None:
        write_seat(
            args.board,
            session_uuid=existing.session_uuid,
            compact_id=existing.compact_id,
            machine=existing.machine,
            identity=self_identity() if self_identity().primary_ref else SelfIdentity(
                client=existing.client,
                harness_session_id=existing.harness_session_id,
                host_session_id=existing.host_session_id,
                pid=existing.pid,
            ),
            cwd=existing.cwd,
        )
    return 0


def command_release(args) -> int:
    released: dict[str, SessionIdentity] = {}

    def operation(content: str) -> str:
        current = ensure_identities(rows(content))
        session = find_session(current, args.id)
        if session is None:
            raise RuntimeError(f"session not found: {args.id}")
        session.status = "released"
        session.heartbeat = timestamp()
        released["identity"] = session.identity
        return replace_table(content, current)

    try:
        locked_update(args.board, operation)
    except RuntimeError as exc:
        print(f"coordination release failed: {exc}", file=sys.stderr)
        return 10
    pointer = getattr(args, "active_project_file", None)
    if pointer is not None:
        try:
            board_lease = declared_lease(args.board.read_text(encoding="utf-8"))
            archived = archive_owned_pointer(
                Path(pointer), released["identity"], board_lease
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(
                f"coordination release completed, but active-project archival failed: {exc}",
                file=sys.stderr,
            )
            return 11
        if archived:
            print(f"Archived released session's active-project pointer: {archived}")
    if remove_seat(args.board, released["identity"].session_uuid):
        print("Seat removed.")
    print(f"Released session {released['identity'].compact_id}.")
    return 0


def archive_owned_pointer(
    pointer: Path, owner_session: SessionIdentity | str, owner_lease: str | None
) -> Path | None:
    """Recoverably clear the pointer when its coordination owner releases."""
    with locked_pointer(pointer):
        if not pointer.exists():
            return None
        if pointer.is_symlink():
            raise ValueError(f"active-project pointer must not be a symlink: {pointer}")
        payload = json.loads(pointer.read_text(encoding="utf-8"))
        identity = (
            owner_session
            if isinstance(owner_session, SessionIdentity)
            else SessionIdentity("", "", "", owner_session)
        )
        pointer_owner = str(payload.get("owner_session") or "")
        if (
            owner_lease is None
            or not selector_matches(identity, pointer_owner)
            or payload.get("owner_lease") != owner_lease
        ):
            return None
        archive = pointer.parent / "active-project-history"
        if archive.is_symlink():
            raise ValueError(f"active-project archive must not be a symlink: {archive}")
        archive.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().astimezone().strftime("%Y%m%dT%H%M%S%f%z")
        owner_value = identity.session_uuid or pointer_owner
        visible = re.sub(r"[^A-Za-z0-9._-]+", "-", owner_value).strip("._-")
        visible = (visible or "session")[:40]
        digest = hashlib.sha256(owner_value.encode("utf-8")).hexdigest()[:12]
        destination = archive / f"{stamp}-{visible}-{digest}.json"
        if destination.parent.resolve() != archive.resolve():
            raise ValueError("active-project archive destination escaped its root")
        os.replace(pointer, destination)
        return destination


def resolve_targets(
    sessions: list[Session], selector: str
) -> tuple[str, list[Session]]:
    """Resolve a peer selector to board sessions, most exact form first.

    Accepted forms: any identity selector (UUID, compact, speakable, legacy),
    a client session ref (bare `local_...` is accepted as `ccd:local_...`),
    or a registered project name (optionally suffixed " sessions"). Client
    titles and display labels are deliberately not selectors — they are the
    guessing vector this resolver exists to remove.
    """
    identity = [
        session
        for session in sessions
        if selector_matches(session.identity, selector)
    ]
    if identity:
        return "identity", identity
    candidate = selector.strip()
    ref_forms = {candidate}
    if candidate.startswith("local_"):
        ref_forms.add(f"ccd:{candidate}")
    refs = [
        session
        for session in sessions
        if session.client_ref and session.client_ref in ref_forms
    ]
    if refs:
        return "client-ref", refs
    base = candidate[: -len(" sessions")] if candidate.endswith(" sessions") else candidate
    projects = [
        session
        for session in sessions
        if session.project not in {"", "unknown", "none"}
        and session.project.casefold() == base.casefold()
    ]
    if projects:
        return "project", projects
    return "none", []


def delivery_lane(session: Session) -> str:
    if session.client_ref.startswith("ccd:"):
        return (
            f"ccd send_message to session_id {session.client_ref[4:]} "
            f"(valid on machine {session.machine})"
        )
    if session.client_ref.startswith("codex:"):
        return (
            f"codex queue --thread {session.client_ref[len('codex:'):]} on machine "
            f"{session.machine}, or the board message bus"
        )
    if session.client_ref.startswith("cc:"):
        return (
            "harness SendMessage to the uds: socket the resolver prints (valid on "
            f"machine {session.machine} while the session runs), or the board message bus"
        )
    if "codex" in session.agent.lower():
        return "board message bus (Codex session registered no thread id)"
    return "board message bus (session has no registered client ref)"


def command_message(args) -> int:
    body = args.text if args.text is not None else sys.stdin.read().strip()
    if not body:
        print("coordination message is empty", file=sys.stderr)
        return 2

    def operation(content: str) -> str:
        current = rows(content)
        sender = find_session(current, args.sender)
        sender_label = sender.label if sender is not None else sanitize(args.sender)
        kind, matches = resolve_targets(current, args.to)
        if kind in {"identity", "client-ref"}:
            if len(matches) > 1:
                raise RuntimeError(
                    f"recipient selector {args.to!r} is ambiguous: "
                    + ", ".join(session.label for session in matches)
                )
            recipient_label = matches[0].label
        elif kind == "project":
            recipient_label = f"{matches[0].project} sessions"
        elif getattr(args, "free_address", False):
            recipient_label = sanitize(args.to)
        else:
            raise RuntimeError(
                f"recipient {args.to!r} matches no session identity, client "
                "ref, or registered project on this board; use 'resolve' to "
                "find the target, or pass --free-address to record a "
                "deliberately unregistered addressee"
            )
        heading = (
            f"### → {recipient_label}, from {sender_label} — {timestamp()}"
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


def command_resolve(args) -> int:
    """Resolve a peer selector to an exact, deliverable session target.

    Exit codes: 0 exactly one target; 20 several candidates (never broadcast —
    narrow with --role or address one exact id, or use the board bus addressed
    to the project); 21 no target (the peer is unregistered; use the board
    bus). The lesson this mechanizes: the board id is the identity, the client
    label is a display string.
    """
    lease_refresh(args.board)
    if not args.board.is_file():
        print(f"resolve: no coordination board at {args.board}", file=sys.stderr)
        return 21
    content = args.board.read_text(encoding="utf-8")
    sessions = rows(content)
    pool = (
        sessions
        if args.include_released
        else [session for session in sessions if active(session)]
    )
    kind, matches = resolve_targets(pool, args.to)
    if args.role:
        matches = [
            session for session in matches if session.context_role == args.role
        ]
    entries = [
        {
            "session": session.compact_id,
            "uuid": session.session_uuid,
            "speakable": session.speakable_id,
            "agent": session.agent,
            "machine": session.machine,
            "project": session.project,
            "context_role": session.context_role,
            "status": session.status,
            "heartbeat": session.heartbeat,
            "stale": stale(session, args.stale_after_minutes),
            "client_ref": session.client_ref,
            "delivery": delivery_lane(session),
        }
        for session in matches
    ]
    lanes: dict[str, dict] = {}
    receipt_path = None
    receipt_note = ""
    sender_compact = ""
    if len(entries) == 1:
        target = matches[0]
        lanes = delivery_lanes(
            client_ref=target.client_ref,
            compact_id=target.compact_id,
            target_machine=target.machine,
            seat=read_seat(args.board, target.session_uuid),
            local_machine=getattr(args, "local_machine", None),
            registry=getattr(args, "registry", None),
        )
        sender = self_identity()
        own_seat = seat_for_identity(args.board, sender)
        sender_row = next(
            (s for s in sessions if own_seat and s.session_uuid == own_seat.session_uuid and active(s)),
            None,
        )
        sender_compact = sender_row.compact_id if sender_row else ""
        if not getattr(args, "no_receipt", False):
            receipt_path = write_receipt(
                args.board,
                sender=sender,
                sender_row=(
                    {"uuid": sender_row.session_uuid, "compact": sender_row.compact_id, "project": sender_row.project}
                    if sender_row
                    else None
                ),
                selector=args.to,
                matched_by=kind,
                target={
                    "uuid": target.session_uuid,
                    "compact": target.compact_id,
                    "project": target.project,
                    "machine": target.machine,
                    "agent": target.agent,
                    "client_ref": target.client_ref,
                },
                lanes=lanes,
            )
            if receipt_path is None:
                receipt_note = (
                    "no delivery receipt issued: this shell carries no session identity "
                    "(CLAUDE_CODE_SESSION_ID or SYNTHESIS_CLIENT_SESSION_REF), so the send "
                    "gate will refuse direct lanes; the bus lane remains"
                )
            elif sender_row is None:
                receipt_note = (
                    "receipt issued, but this session holds no active seat: the send gate "
                    "requires one (claim before sending) so the peer can resolve a reply"
                )
    if args.json:
        print(
            json.dumps(
                {
                    "selector": args.to,
                    "matched_by": kind,
                    "board_schema": board_schema(content),
                    "matches": entries,
                    "lanes": lanes,
                    "receipt": str(receipt_path) if receipt_path else None,
                    "receipt_note": receipt_note or None,
                    "sender": sender_compact or None,
                },
                indent=2,
            )
        )
    else:
        for entry in entries:
            marker = " STALE" if entry["stale"] else ""
            print(
                f"{entry['session']}  {entry['project']}  "
                f"[{entry['context_role']}/{entry['status']}{marker}]  "
                f"{entry['agent']} on {entry['machine']}"
            )
            print(f"  uuid: {entry['uuid']}")
            print(f"  client ref: {entry['client_ref'] or '-'}")
            print(f"  delivery: {entry['delivery']}")
        if lanes:
            print("Exact invocations (copy verbatim; the message must start with your board id):")
            for line in lane_invocations(lanes, sender_compact):
                print(f"  {line}")
            if receipt_path is not None:
                print(f"Delivery receipt: {receipt_path} (valid 20 minutes; the send gate matches it)")
            if receipt_note:
                print(f"note: {receipt_note}", file=sys.stderr)
    if len(entries) == 1:
        return 0
    if len(entries) > 1:
        print(
            f"resolve: {len(entries)} candidates for {args.to!r} — do not "
            "broadcast; narrow with --role, address one exact session id, or "
            "post to the board bus addressed to the project",
            file=sys.stderr,
        )
        return 20
    hint = ""
    if kind != "none":
        hint = f" (matched {kind} rows, but none passed the filters)"
    if board_schema(content) is not None and board_schema(content) < 4:
        hint += (
            "; note the board declares a pre-v4 schema, which carries no "
            "client refs until 'migrate' runs"
        )
    print(
        f"resolve: no active target for {args.to!r}{hint} — the peer has not "
        "registered a claim, so deliver via the board message bus and let it "
        "self-select; do not guess a chat session by title",
        file=sys.stderr,
    )
    return 21


def command_inbox(args) -> int:
    """Unread board messages addressed to a seat (any identity form) or its project."""
    lease_refresh(args.board)
    if not args.board.is_file():
        print(f"inbox: no coordination board at {args.board}", file=sys.stderr)
        return 1
    content = args.board.read_text(encoding="utf-8")
    sessions = rows(content)
    selector = getattr(args, "id", None)
    identity = self_identity()
    if selector:
        row = find_session(sessions, selector)
        if row is None:
            print(f"inbox: session not found: {selector}", file=sys.stderr)
            return 1
        key = f"seat:{row.session_uuid}"
    else:
        seat = seat_for_identity(args.board, identity)
        row = next((s for s in sessions if seat and s.session_uuid == seat.session_uuid), None)
        if row is None:
            print(
                "inbox: this shell holds no seat on the board; pass --session <id> or "
                "claim first",
                file=sys.stderr,
            )
            return 1
        key = identity.sender_key or f"seat:{row.session_uuid}"
    forms = {row.session_uuid, row.compact_id, row.speakable_id} | ({row.legacy_id} if row.legacy_id else set())
    messages = unread_messages(
        content,
        board=args.board,
        sender_key=key,
        identity_forms=forms,
        project=row.project,
        since=row.started,
    )
    if getattr(args, "json", False):
        print(
            json.dumps(
                {
                    "session": row.compact_id,
                    "unread": [
                        {"from": m.sender, "to": m.recipient, "at": m.timestamp, "body": m.body}
                        for m in messages
                    ],
                },
                indent=2,
            )
        )
    else:
        print(render_inbox(messages, limit=len(messages) or 1) or f"No unread messages for {row.compact_id}.")
    if messages and getattr(args, "mark_read", False):
        mark_seen(args.board, key, {m.key for m in messages})
        print(f"Marked {len(messages)} message(s) read for {row.compact_id}.")
    return 0


def command_whoami(args) -> int:
    """This shell's session identity, seat, board row, and the lanes peers would use."""
    identity = self_identity()
    seat = seat_for_identity(args.board, identity) if args.board.is_file() else None
    sessions = rows(args.board.read_text(encoding="utf-8")) if args.board.is_file() else []
    row = next((s for s in sessions if seat and s.session_uuid == seat.session_uuid), None)
    lanes = (
        delivery_lanes(
            client_ref=row.client_ref,
            compact_id=row.compact_id,
            target_machine=row.machine,
            seat=seat,
            local_machine=getattr(args, "local_machine", None),
            registry=getattr(args, "registry", None),
        )
        if row is not None
        else {}
    )
    receipts = load_receipts(args.board, identity.sender_key) if identity.sender_key else []
    payload = {
        "client": identity.client or None,
        "harness_session_id": identity.harness_session_id or None,
        "host_session_id": identity.host_session_id or None,
        "primary_ref": identity.primary_ref or None,
        "sender_key": identity.sender_key or None,
        "seat": str(seat.compact_id) if seat else None,
        "row": (
            {"session": row.compact_id, "uuid": row.session_uuid, "project": row.project, "status": row.status}
            if row
            else None
        ),
        "lanes_peers_use": lanes,
        "receipts_held": [r.get("target", {}).get("compact") for r in receipts],
    }
    if getattr(args, "json", False):
        print(json.dumps(payload, indent=2))
        return 0
    print(f"client: {payload['client'] or '-'}")
    print(f"harness session id: {payload['harness_session_id'] or '-'}")
    print(f"host session id: {payload['host_session_id'] or '-'}")
    print(f"primary ref: {payload['primary_ref'] or '-'}")
    print(f"sender key: {payload['sender_key'] or '- (direct sends will be refused)'}")
    if row is None:
        print("seat: none — claim before messaging peers")
    else:
        print(f"seat: {row.compact_id} ({row.project}, {row.status})")
        print("lanes peers use to reach this session:")
        for line in lane_invocations(lanes, "<their id>"):
            print(f"  {line}")
    print(f"receipts held: {', '.join(r for r in payload['receipts_held'] if r) or 'none'}")
    return 0 if row is not None and identity.sender_key else 1


def command_migrate(args) -> int:
    def operation(content: str) -> str:
        migrated = ensure_identities(rows(content))
        problems = validate_sessions(migrated)
        if problems:
            raise RuntimeError("; ".join(problems))
        return replace_table(content, migrated, force_schema=SCHEMA_VERSION)

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


STALE_CLAIM_DEFAULT_DAYS = 2


def worktree_evidence(session: "Session", this_machine: str) -> tuple[str, bool]:
    """Physical evidence about whether a session can still be alive.

    A heartbeat age is a hint; a missing worktree is close to proof. The point
    is to give the user something to decide ON, rather than asking them to
    guess from elapsed time — which is exactly the judgment the protocol
    reserves to them.
    """
    if session.machine and this_machine and session.machine != this_machine:
        return (f"claimed on {session.machine}, not this machine — "
                "cannot be judged from here"), False
    paths = []
    for entry in session.workspaces:
        candidate = entry.split(" @ ")[0].strip()
        if candidate.startswith(("/", "~")):
            paths.append(Path(candidate).expanduser())
    if not paths:
        return "no absolute worktree recorded — cannot verify", False
    missing = [p for p in paths if not p.exists()]
    if missing and len(missing) == len(paths):
        return (f"worktree no longer exists ({missing[0]}) — the session "
                "cannot still be writing there"), True
    if missing:
        return f"{len(missing)} of {len(paths)} recorded worktrees are gone", True
    return "worktree still present — may be a live session", False


def command_stale(args) -> int:
    """Report `active` rows whose heartbeat has gone quiet. Never mutates."""
    if not args.board.is_file():
        print(f"coordination stale: no board at {args.board}", file=sys.stderr)
        return 0
    try:
        sessions = rows(args.board.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"coordination stale: board unreadable: {exc}", file=sys.stderr)
        return 2

    now = datetime.now(timezone.utc)
    this_machine = platform.node()
    stale: list[tuple[float, "Session", str, bool]] = []
    unknown_age = 0
    for session in sessions:
        if not active(session):
            continue
        beat = parse_time(session.heartbeat)
        if beat is None:
            unknown_age += 1
            continue
        age_days = (now - beat).total_seconds() / 86400.0
        if age_days <= args.threshold:
            continue
        note, gone = worktree_evidence(session, this_machine)
        stale.append((age_days, session, note, gone))
    stale.sort(key=lambda r: -r[0])
    shown = stale if args.all else stale[: args.limit]

    if args.json:
        print(json.dumps({
            "threshold_days": args.threshold,
            "active_total": sum(1 for s in sessions if active(s)),
            "stale_total": len(stale),
            "undated": unknown_age,
            "shown": [{
                "id": s.compact_id,
                "uuid": s.session_uuid,
                "agent": s.agent,
                "machine": s.machine,
                "project": s.project,
                "heartbeat": s.heartbeat,
                "age_days": round(age, 2),
                "evidence": note,
                "worktree_gone": gone,
                "claims": s.claims,
            } for age, s, note, gone in shown],
        }, indent=2))
        return 0

    live = sum(1 for s in sessions if active(s))
    if not stale:
        print(f"Coordination review: {live} active session(s), none quiet for "
              f"more than {args.threshold:g} day(s). No claims to resolve.")
        return 0

    print(f"Coordination review: {len(stale)} of {live} active session(s) have "
          f"been quiet for more than {args.threshold:g} day(s).")
    print("A dead session's row keeps blocking every overlapping claim, so these "
          "cost real work.")
    print("Releasing one is YOUR call — elapsed time is not proof, and no agent "
          "should decide it.\n")
    for age, session, note, gone in shown:
        flag = "LIKELY GONE" if gone else "unverified"
        print(f"  {session.compact_id}  [{flag}]  quiet {age:.1f}d")
        print(f"    agent:    {session.agent} on {session.machine}")
        print(f"    project:  {session.project}")
        print(f"    evidence: {note}")
        if session.claims:
            head = session.claims[0]
            extra = f" (+{len(session.claims) - 1} more)" if len(session.claims) > 1 else ""
            print(f"    blocks:   {head}{extra}")
        print(f"    release:  coordination.py release --id {session.compact_id}\n")
    if len(stale) > len(shown):
        print(f"  ...and {len(stale) - len(shown)} more; --all shows every one.")
    if unknown_age:
        print(f"  ({unknown_age} active row(s) have an unparseable heartbeat and "
              "were not assessed — reported rather than assumed healthy.)")
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
    declared = board_schema(content)
    schema_note = ""
    if declared is None:
        problems.append("missing Schema declaration")
    elif declared > SCHEMA_VERSION:
        problems.append(
            f"board declares schema v{declared}, newer than this client "
            f"(v{SCHEMA_VERSION}); update the installed plugin before mutating"
        )
    elif declared < SCHEMA_VERSION:
        schema_note = (
            f" (declared v{declared}; run migrate once every machine's "
            "client is current to enable client session refs)"
        )
    if problems:
        for problem in problems:
            print(f"FAIL coordination: {problem}", file=sys.stderr)
        return 1
    seats = all_seats(args.board)
    active_uuids = {session.session_uuid for session in sessions if active(session)}
    stale_seats = [seat for seat in seats if seat.session_uuid not in active_uuids]
    seat_line = f", {len(seats)} seat(s)" + (
        f" ({len(stale_seats)} without an active row; release removes them, resolve ignores them)"
        if stale_seats
        else ""
    )
    print(
        f"PASS coordination: schema v{declared}{schema_note}, "
        f"{len(sessions)} session(s){seat_line}{lease_line}"
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
    check_staged = commands.add_parser(
        "check-staged",
        help=(
            "Fail closed unless every staged path is covered by the selected "
            "active session's exact worktree and source-area claims."
        ),
    )
    check_staged.add_argument("--id", "--session", dest="id")
    check_staged.add_argument(
        "--repository",
        type=Path,
        default=Path.cwd(),
        help="Repository or subdirectory whose Git index is being committed.",
    )
    check_staged.add_argument(
        "--active-project-file", type=Path, default=DEFAULT_ACTIVE_PROJECT
    )
    check_staged.add_argument(
        "--override-reason",
        help=(
            "Explicit accountability reason to record on the board before "
            "allowing staged paths outside the claim."
        ),
    )
    check_staged.add_argument("--json", action="store_true")
    claim = commands.add_parser("claim")
    claim.add_argument(
        "--id",
        "--session",
        dest="id",
        help=(
            "Existing UUID, compact, speakable, or legacy selector. Omit to "
            "allocate a new UUIDv7 identity; an unmatched plain label is "
            "preserved as a legacy alias during migration, while an unmatched "
            "strong selector fails closed."
        ),
    )
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
    claim.add_argument(
        "--client-ref",
        help=(
            "Client-native delivery handle for this session, scheme-prefixed "
            "(ccd:local_..., codex:...). Auto-detected from "
            "SYNTHESIS_CLIENT_SESSION_REF or CLAUDE_CODE_HOST_SESSION_ID "
            "when omitted."
        ),
    )
    heartbeat = commands.add_parser("heartbeat")
    heartbeat.add_argument("--id", "--session", dest="id", required=True)
    release = commands.add_parser("release")
    release.add_argument("--id", "--session", dest="id", required=True)
    release.add_argument(
        "--active-project-file", type=Path, default=DEFAULT_ACTIVE_PROJECT
    )
    message = commands.add_parser("message")
    message.add_argument("--from", dest="sender", required=True)
    message.add_argument("--to", required=True)
    message.add_argument("--text")
    message.add_argument(
        "--free-address",
        action="store_true",
        help=(
            "Record an addressee that matches no session or registered "
            "project. Without it, an unresolvable --to refuses."
        ),
    )
    resolve = commands.add_parser(
        "resolve",
        help=(
            "Resolve a peer selector (identity, client ref, or project) to "
            "an exact deliverable target; refuses ambiguity instead of "
            "guessing or broadcasting."
        ),
    )
    resolve.add_argument("--to", required=True)
    resolve.add_argument("--role", choices=("owner", "contributor", "none"))
    resolve.add_argument("--include-released", action="store_true")
    resolve.add_argument("--stale-after-minutes", type=int, default=240)
    resolve.add_argument("--json", action="store_true")
    resolve.add_argument(
        "--no-receipt",
        action="store_true",
        help="Look up only; do not issue the delivery receipt the send gate matches.",
    )
    resolve.add_argument("--registry", type=Path, default=None, help=argparse.SUPPRESS)
    resolve.add_argument("--local-machine", default=None, help=argparse.SUPPRESS)
    inbox = commands.add_parser(
        "inbox",
        help="Unread board messages addressed to this seat (any identity form) or its project.",
    )
    inbox.add_argument("--id", "--session", dest="id")
    inbox.add_argument("--mark-read", action="store_true")
    inbox.add_argument("--json", action="store_true")
    whoami = commands.add_parser(
        "whoami",
        help="This shell's session identity, seat, row, and the lanes peers use to reach it.",
    )
    whoami.add_argument("--json", action="store_true")
    whoami.add_argument("--registry", type=Path, default=None, help=argparse.SUPPRESS)
    whoami.add_argument("--local-machine", default=None, help=argparse.SUPPRESS)
    commands.add_parser("migrate")
    commands.add_parser("doctor")
    stale = commands.add_parser(
        "stale",
        help="Report active claims whose heartbeat has gone quiet. Reports "
        "only; releasing a claim stays the user's decision.",
    )
    stale.add_argument("--threshold", type=float,
                       default=STALE_CLAIM_DEFAULT_DAYS,
                       help="days of silence before a claim is surfaced")
    stale.add_argument("--limit", type=int, default=3)
    stale.add_argument("--all", action="store_true")
    stale.add_argument("--json", action="store_true")
    lease_disable = commands.add_parser(
        "lease-disable",
        help="Retire the board's lease declaration (CAS-published by default; "
        "--local-only is the unreachable-remote escape).",
    )
    lease_disable.add_argument("--local-only", action="store_true")
    return result


COMMANDS = {
    "status": command_status,
    "check-staged": command_check_staged,
    "claim": command_claim,
    "heartbeat": command_heartbeat,
    "release": command_release,
    "message": command_message,
    "resolve": command_resolve,
    "inbox": command_inbox,
    "whoami": command_whoami,
    "migrate": command_migrate,
    "lease-disable": command_lease_disable,
    "stale": command_stale,
}


def stale_engine_notice(script_path: Path | str = __file__) -> str | None:
    """One line for stderr when this engine is older than the newest installed.

    A session resolves a plugin path once and keeps it for hours while the
    ecosystem ships several releases a day; the path goes stale by design of
    the cadence, and nothing said so until a newer board broke the old
    parser. The notice makes staleness visible in output an agent is already
    reading, on every invocation, without changing the command's behavior."""
    found = newer_installed_engine(script_path)
    if found is None:
        return None
    running, newest, path = found
    return (
        f"note: this coordination engine is {running} but {newest} is installed; "
        f"run {path} (or the stable path ~/.synthesis/plugins/synthesis-skills/current)"
    )


def main() -> int:
    args = parser().parse_args()
    args.board = args.board.expanduser()
    notice = stale_engine_notice()
    if notice:
        print(notice, file=sys.stderr)
    command = COMMANDS.get(args.command, command_doctor)
    try:
        return command(args)
    except ValueError as exc:
        # A refusal is a diagnosis, not a crash: one line the operator can act
        # on, never a traceback whose last line gets quoted as the problem.
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

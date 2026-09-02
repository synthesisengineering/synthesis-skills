#!/usr/bin/env python3
"""Fail-closed PreToolUse gate for direct peer-session sends, in both clients.

Peer messages reached the wrong chat session seven recorded times between
2026-08-19 and 2026-09-02, including once after the resolver shipped: the
harness lane (``SendMessage``) was ungated, its display names collide by
construction, and the one gate that existed checked that a target was
registered, not that it was the one the sender resolved. This gate closes
that on every direct lane the plugin knows:

- ``SendMessage``: in-process targets (``main``, spawned agent ids, named
  teammates) pass; a peer is addressed only by its ``uds:`` socket, and only
  when a live resolve receipt names that socket for this sender and the
  harness registry still maps it to the receipt's session.
- ``mcp__ccd_session_mgmt__send_message``: the ``session_id`` must equal the
  ccd address on a live receipt, and the board row must still be active.
- shell tools: a ``codex queue --thread`` command needs a receipt naming
  that thread; every other command passes untouched.

Every direct send must carry the sender's own board id so the recipient can
resolve the reply without guessing, and the same text to a second peer
within the broadcast window is refused. A reply may copy the ``from=`` of a
message this session received (the harness wrote that address). Every
decision is appended to the send log. Anything the gate cannot verify —
no session id, unreadable board, unknown tool shape — blocks.

Exit 0 admits the call; exit 2 blocks it with the reason and the remedy on
stderr, which both clients show to the agent.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from peer_addressing import (  # noqa: E402
    CLIENT_CLAUDE,
    SelfIdentity,
    append_send_log,
    body_digest,
    broadcast_conflict,
    identity_from_hook,
    iso,
    load_receipts,
    process_alive,
    receipt_for_address,
    receipts_dir,
    registry_dir,
    registry_entry_for_socket,
    seat_for_identity,
    send_log_path,
    utcnow,
)

DEFAULT_BOARD = Path.home() / ".synthesis" / "coordination" / "active-sessions.md"
HARNESS_TOOL = "SendMessage"
CCD_TOOL_RE = re.compile(r"ccd_session_mgmt__send_message$")
SHELL_TOOLS = {"Bash", "exec_command", "exec", "shell", "local_shell"}
AGENT_ID_RE = re.compile(r"^a[0-9a-f]{16}$")
CODEX_QUEUE_RE = re.compile(r"(?<![\w./-])codex\s+queue\b")
THREAD_RE = re.compile(r"--thread(?:=|\s+)(?:\"([^\"]+)\"|'([^']+)'|(\S+))")
MESSAGE_RE = re.compile(r"--message(?:=|\s+)(?:\"((?:[^\"\\]|\\.)*)\"|'([^']*)'|(\S+))")
FROM_RE = re.compile(r'cross-session-message from=\\?"([^"\\]+)\\?"')
TRANSCRIPT_TAIL_BYTES = 4_000_000

RESOLVE_HINT = (
    "Run `coordination.py resolve --to <project|session id|ref>` (exit 0 means one "
    "target; it prints the exact address per lane and issues the receipt this gate "
    "matches), then copy that address verbatim. Exit 20 means several candidates — "
    "narrow with --role or an exact id, never send to more than one; exit 21 means "
    "no registered seat — post on the board bus (`coordination.py message --to`) "
    "instead. Chat titles and display names are not addresses."
)


@dataclass
class Decision:
    allow: bool
    lane: str = ""
    target: str = ""
    reason: str = ""
    target_uuid: str = ""
    logged: bool = True


def board_rows(board: Path):
    """Active board rows via the engine; a failure to read is a failure to verify."""
    from coordination import active, rows  # local import: hook-time cost only when needed

    text = Path(board).read_text(encoding="utf-8")
    return [row for row in rows(text) if active(row)]


def teammate_names(home: Path | None = None) -> set[str]:
    root = (home or Path.home()) / ".claude" / "teams"
    names: set[str] = set()
    if not root.is_dir():
        return names
    for config in root.glob("*/config.json"):
        try:
            data = json.loads(config.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for member in data.get("members", []) if isinstance(data, dict) else []:
            if isinstance(member, dict) and member.get("name"):
                names.add(str(member["name"]))
    return names


def received_addresses(transcript_path: str | None, limit: int = TRANSCRIPT_TAIL_BYTES) -> set[str]:
    """Every ``from=`` address of a cross-session message in this transcript's tail."""
    if not transcript_path:
        return set()
    path = Path(transcript_path)
    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            if size > limit:
                handle.seek(size - limit)
            raw = handle.read().decode("utf-8", errors="replace")
    except OSError:
        return set()
    return set(FROM_RE.findall(raw))


def shell_command(tool_input: dict) -> str:
    for field in ("command", "cmd", "script"):
        value = tool_input.get(field)
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            return " ".join(str(part) for part in value)
    return ""


def first_group(match: re.Match | None) -> str:
    if match is None:
        return ""
    return next((group for group in match.groups() if group), "")


def classify(tool_name: str, tool_input: dict, home: Path | None = None) -> Decision:
    """Which lane a call belongs to, or an immediate allow for non-peer calls."""
    if tool_name == HARNESS_TOOL:
        to = str(tool_input.get("to") or "").strip()
        if not to:
            return Decision(False, "harness", "", "SendMessage carries no `to`")
        if to == "main" or AGENT_ID_RE.match(to) or to in teammate_names(home):
            return Decision(True, "in-process", to, "in-process agent", logged=False)
        if to.startswith("uds:"):
            return Decision(True, "harness", to, "")
        return Decision(
            False,
            "harness",
            to,
            f"{to!r} is a display name, not an address: harness names are derived "
            "from the working directory and collide, and a `[ref]` cannot be verified. "
            "Peers are addressed by the `uds:` socket the resolver prints.",
        )
    if CCD_TOOL_RE.search(tool_name):
        session_id = str(tool_input.get("session_id") or "").strip()
        if not session_id:
            return Decision(False, "ccd", "", "peer send carries no session_id")
        return Decision(True, "ccd", session_id, "")
    if tool_name in SHELL_TOOLS:
        command = shell_command(tool_input)
        if not CODEX_QUEUE_RE.search(command):
            return Decision(True, "shell", "", "not a peer send", logged=False)
        thread = first_group(THREAD_RE.search(command))
        if not thread:
            return Decision(False, "codex", "", "codex queue without a --thread value")
        return Decision(True, "codex", thread, "")
    return Decision(True, "other", "", "not a peer tool", logged=False)


def message_body(lane: str, tool_input: dict) -> str:
    if lane == "codex":
        return first_group(MESSAGE_RE.search(shell_command(tool_input)))
    return str(tool_input.get("message") or "")


def evaluate(
    payload: dict,
    *,
    board: Path = DEFAULT_BOARD,
    registry: Path | None = None,
    environ: dict[str, str] | None = None,
    home: Path | None = None,
    now: datetime | None = None,
    alive=process_alive,
) -> Decision:
    tool_name = str(payload.get("tool_name") or "")
    tool_input = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {}
    moment = now or utcnow()
    verdict = classify(tool_name, tool_input, home)
    if not verdict.allow or not verdict.logged or verdict.lane in {"in-process", "shell", "other"}:
        return verdict
    lane, address = verdict.lane, verdict.target

    sender = identity_from_hook(payload, environ)
    key = sender.sender_key
    if not key:
        return Decision(False, lane, address, "the hook payload names no session_id, so the sender cannot be identified")

    try:
        active_rows = board_rows(board)
    except Exception as exc:  # unreadable, newer schema, missing: cannot verify
        return Decision(False, lane, address, f"coordination board unreadable, so the target cannot be verified: {exc}")

    seat = seat_for_identity(board, sender)
    sender_row = next((row for row in active_rows if seat and row.session_uuid == seat.session_uuid), None)
    if sender_row is None:
        return Decision(
            False,
            lane,
            address,
            "this session holds no active seat on the coordination board, so the "
            "recipient could not resolve a reply; claim first (`coordination.py claim "
            "--project … --area …`), then resolve the peer",
        )

    receipts = load_receipts(board, key, moment)
    receipt = receipt_for_address(receipts, lane, address)
    replied = address in received_addresses(payload.get("transcript_path")) if lane in {"harness", "ccd"} else False
    target_uuid = ""
    if receipt is not None:
        target_uuid = str(receipt.get("target", {}).get("uuid") or "")
        target_row = next((row for row in active_rows if row.session_uuid == target_uuid), None)
        if target_row is None:
            return Decision(False, lane, address, f"receipt target {target_uuid} is no longer an active board row; resolve again")
        if lane == "ccd" and target_row.client_ref != f"ccd:{address}":
            return Decision(False, lane, address, "the receipt's ccd address no longer matches the target row; resolve again")
        if lane == "codex" and not (
            target_row.client_ref == f"codex:{address}"
            or str(receipt.get("lanes", {}).get("codex", {}).get("thread")) == address
        ):
            return Decision(False, lane, address, "the receipt's codex thread no longer matches the target row; resolve again")
        if lane == "harness":
            entry = registry_entry_for_socket(address[len("uds:"):], registry, alive)
            expected = str(receipt.get("lanes", {}).get("harness", {}).get("harness_session_id") or "")
            if entry is None or entry.get("sessionId") != expected:
                return Decision(
                    False,
                    lane,
                    address,
                    "the harness registry no longer maps that socket to the resolved "
                    "session (it restarted or exited); resolve again",
                )
        reason = f"receipt {receipt.get('selector')!r} → {receipt.get('target', {}).get('compact')}"
    elif replied:
        reason = "reply to a received cross-session message (address copied from its from=)"
        matched = next(
            (row for row in active_rows if row.client_ref in {f"ccd:{address}", address}), None
        )
        target_uuid = matched.session_uuid if matched else ""
    else:
        return Decision(False, lane, address, f"no delivery receipt names {address!r} for this session. " + RESOLVE_HINT)

    body = message_body(lane, tool_input)
    subscription_only = lane == "harness" and not body.strip() and bool(tool_input.get("notify_when_idle"))
    if not subscription_only:
        if sender_row.compact_id not in body and sender_row.session_uuid not in body:
            return Decision(
                False,
                lane,
                address,
                f"the message must carry your board id so the peer can resolve a reply: "
                f"begin it with `from {sender_row.compact_id} ({sender_row.project}):`",
            )
        digest = body_digest(body)
        conflict = broadcast_conflict(
            board, sender_key=key, digest=digest, target_uuid=target_uuid or address, now=moment
        )
        if conflict is not None:
            return Decision(
                False,
                lane,
                address,
                "the same text already went to another session at "
                f"{conflict.get('at')} ({conflict.get('lane')} {conflict.get('target')}); "
                "that is a broadcast. Address the project on the board bus instead.",
            )
    return Decision(True, lane, address, reason, target_uuid=target_uuid or address)


def record(board: Path, payload: dict, decision: Decision, environ: dict[str, str] | None = None, now: datetime | None = None) -> None:
    sender = identity_from_hook(payload, environ)
    tool_input = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {}
    body = message_body(decision.lane, tool_input) if decision.lane in {"harness", "ccd", "codex"} else ""
    try:
        append_send_log(
            board,
            {
                "at": iso(now or utcnow()),
                "decision": "allow" if decision.allow else "deny",
                "lane": decision.lane,
                "target": decision.target,
                "target_uuid": decision.target_uuid,
                "sender_key": sender.sender_key,
                "digest": body_digest(body) if body else "",
                "reason": decision.reason,
                "tool": payload.get("tool_name"),
            },
        )
    except OSError:
        pass


def gate(board: Path) -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.stderr.write("peer-send-gate BLOCKED: hook payload is not JSON; unknown shape fails closed\n")
        return 2
    if not isinstance(payload, dict):
        sys.stderr.write("peer-send-gate BLOCKED: hook payload is not an object\n")
        return 2
    decision = evaluate(payload, board=board)
    if decision.logged:
        record(board, payload, decision)
    if decision.allow:
        return 0
    sys.stderr.write(
        f"peer-send-gate BLOCKED ({decision.lane} lane"
        + (f", target {decision.target!r}" if decision.target else "")
        + f"): {decision.reason}\n"
    )
    return 2


def doctor(board: Path, environ: dict[str, str] | None = None) -> int:
    ok = True

    def report(passed: bool, name: str, detail: str) -> None:
        nonlocal ok
        ok = ok and passed
        print(f"{'PASS' if passed else 'FAIL'} peer-send-gate.{name}: {detail}")

    try:
        rows = board_rows(board)
        report(True, "board", f"{board} readable; {len(rows)} active row(s)")
    except Exception as exc:
        report(False, "board", f"{board}: {exc}")
    identity = identity_from_hook({}, environ)
    if identity.sender_key:
        seat = seat_for_identity(board, identity)
        report(
            seat is not None,
            "seat",
            f"{identity.sender_key} → {seat.compact_id if seat else 'no seat: claim before sending'}",
        )
    else:
        report(False, "identity", "no CLAUDE_CODE_SESSION_ID or SYNTHESIS_CLIENT_SESSION_REF in this environment")
    directory = receipts_dir(board)
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe = directory / ".doctor-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        report(True, "receipts", f"{directory} writable")
    except OSError as exc:
        report(False, "receipts", f"{directory}: {exc}")
    log = send_log_path(board)
    report(log.parent.is_dir(), "send-log", str(log))
    if identity.client == CLIENT_CLAUDE:
        registry = registry_dir()
        # A missing registry is a fact about this machine (no harness peers
        # registered here), not a broken gate: the bus and ccd lanes stand.
        report(
            True,
            "registry",
            f"{registry} ({'present' if registry.is_dir() else 'absent: harness lane unavailable here; bus and ccd lanes unaffected'})",
        )
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--board", type=Path, default=DEFAULT_BOARD)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--gate", action="store_true", help="read a PreToolUse payload on stdin")
    mode.add_argument("--doctor", action="store_true", help="verify the gate's inputs for this session")
    args = parser.parse_args()
    board = args.board.expanduser()
    if args.doctor:
        return doctor(board)
    return gate(board)


if __name__ == "__main__":
    sys.exit(main())

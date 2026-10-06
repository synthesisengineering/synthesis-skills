"""Approvals that only the principal can grant, bound to the exact thing approved (R3.0-R3.2).

When a guard blocks a send or a deploy it files a request under a random six-character
code, so nobody can know the code before the request exists. The principal types
"approve <code>" and the UserPromptSubmit hook records a grant. The agent runs as the same
OS user and can write that grant itself, or feed the hook a made-up prompt (M5,
2026-10-05), so a grant alone never lets a call through: the harness's own record of the
session must also hold that prompt, typed by the principal after the request was filed.
Tool output, hook text, compaction summaries and other sessions' messages never count.
A verified grant lets exactly one matching call through and expires.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path

from synthesis import paths

TTL_SECONDS = 15 * 60
CODE = re.compile(r"\bapprove\s+([a-z0-9]{6})\b", re.IGNORECASE)
INSERTED = r"(?s)<([A-Za-z][\w-]*)\b[^>]*>.*?</\1\s*>"  # blocks a harness wraps into a prompt; compiled on use
NOT_TYPED = ("isMeta", "isSidechain", "isCompactSummary", "isVisibleInTranscriptOnly", "isSynthetic", "toolUseResult")


class Unverified(PermissionError):
    """A grant exists, but the harness's record does not show the principal typing it."""


def digest(kind: str, subject) -> str:
    canonical = subject if isinstance(subject, str) else json.dumps(subject, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(f"{kind}\0{canonical}".encode("utf-8")).hexdigest()


def _dir(name: str) -> Path:
    return paths.state() / name


def how(code: str) -> str:
    """What the principal types, worded so that tool output or hook text repeating it never holds the phrase."""
    return f"approve followed by the code {code}"


def pending() -> list[str]:
    """The codes of requests waiting for the principal."""
    return [p.stem for p in _dir("approval-requests").glob("*.json")]


def request(kind: str, subject, summary: str) -> str:
    """File (or refresh) a pending request; returns the code the principal types. A retry keeps the
    code the principal was already shown."""
    key = digest(kind, subject)
    _expire()
    code = next((c for c in pending() if paths.read_json(_dir("approval-requests") / f"{c}.json").get("digest") == key), "")
    if not code:  # a leading digit keeps every code apart from English words
        import secrets
        code = str(secrets.randbelow(10)) + secrets.token_hex(3)[:5]
    paths.write_json(_dir("approval-requests") / f"{code}.json",
                     {"kind": kind, "digest": key, "summary": summary, "at": time.time()})
    return code


def _expire() -> None:
    """Drop requests and grants older than the TTL, so state never grows (R8.3)."""
    cutoff = time.time() - TTL_SECONDS
    for path in (p for name in ("approval-requests", "approvals") for p in _dir(name).glob("*.json")):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
        except FileNotFoundError:
            pass


def grant_from_prompt(prompt: str) -> list[str]:
    """Grant every pending request whose code the prompt carries. Returns the summaries granted."""
    granted = []
    for code in {m.lower() for m in CODE.findall(prompt or "")}:
        pending_file = _dir("approval-requests") / f"{code}.json"
        data = paths.read_json(pending_file)
        if not data.get("digest"):
            continue
        paths.write_json(_dir("approvals") / f"{data['digest']}.json",
                         {**data, "code": code, "asked": data.get("at", 0), "at": time.time()})
        pending_file.unlink(missing_ok=True)
        granted.append(data["summary"])
    return granted


def transcript(session: dict | None) -> str:
    """The harness's record of this session: the hook payload's transcript_path, else the one file
    a harness keeps under this session's id (Muse names none; a script run from a shell has none)."""
    given = str((session or {}).get("transcript_path") or "")
    sid = paths.session_id(session)
    if given or not re.fullmatch(r"[\w.-]+", sid):
        return given
    roots = paths.transcript_roots()
    found = [p for root, pattern in ((roots["claude-code"], f"*/{sid}.jsonl"), (roots["codex"], f"*/*/*/rollout-*{sid}.jsonl"),
                                     (roots["muse"], f"*/*/*/{sid}/session.jsonl")) for p in root.glob(pattern)]
    return str(found[0]) if len(found) == 1 else ""


def _prompt(record: dict, session_id: str) -> tuple[float, str]:
    """(time, text) when a transcript line is a prompt the principal typed, else (0, "").
    Claude Code: a user entry, or a prompt typed while the agent worked, from a human; never meta, a
    subagent's, a compaction summary or a tool result. Codex: the user's own message item, never a tool
    output or a hook's prompt. Muse: a chat intent accepted on this session's main surface."""
    body = record.get("payload") if isinstance(record.get("payload"), dict) else {}
    item, queued = body.get("item") or {}, record.get("attachment") or {}
    if record.get("type") == "user":
        entry, content = record, (record.get("message") or {}).get("content")
    elif record.get("type") == "attachment" and queued.get("type") == "queued_command" and queued.get("commandMode") == "prompt":
        entry, content = queued, queued.get("prompt")
    elif record.get("type") == "event_msg" and (body.get("type") == "user_message" or item.get("type") == "UserMessage"):
        entry, content = record, body.get("message") if body.get("type") == "user_message" else item.get("content")
    elif (record.get("payload_type") == "runtime.user_intent.accepted" and body.get("surface") == "main"
          and (body.get("semantic_kind") or {}).get("kind") == "chat" and body.get("source_session_id") in (None, session_id)):
        entry, content = record, body.get("refill_blocks")
    else:
        return 0.0, ""
    blocks = content if isinstance(content, list) else [content]
    origin = entry.get("origin")
    if (any(entry.get(k) for k in NOT_TYPED) or (isinstance(origin, dict) and origin.get("kind") != "human")
            or any(isinstance(b, dict) and b.get("type") == "tool_result" for b in blocks)):
        return 0.0, ""
    text = " ".join(b if isinstance(b, str) else str(b.get("text") or "") for b in blocks if isinstance(b, (str, dict)))
    stamp = record.get("timestamp") or record.get("recorded_at")
    if isinstance(stamp, (int, float)):
        return stamp / 1e6, text  # Muse records microseconds
    from datetime import datetime
    return datetime.fromisoformat(str(stamp).replace("Z", "+00:00")).timestamp(), text


def typed(transcript_path: str, code: str, since: float, session_id: str = "") -> bool:
    """Whether the harness's record shows the principal typing approve <code> after `since`."""
    with open(transcript_path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not code or code not in line.lower():
                continue
            try:
                when, text = _prompt(json.loads(line), session_id)
            except (ValueError, TypeError, AttributeError):
                continue
            if when > since and code in {m.lower() for m in CODE.findall(re.sub(INSERTED, " ", text))}:
                return True
    return False


def consume(kind: str, subject, session: dict | None = None) -> bool:
    """True once for a live grant of exactly this subject that the principal's own prompt backs. The
    grant is spent either way; when the record does not back it, files the request again and raises."""
    path = _dir("approvals") / f"{digest(kind, subject)}.json"
    spent = path.with_suffix(".spent")
    try:
        os.replace(path, spent)
    except FileNotFoundError:
        return False
    data = paths.read_json(spent)
    spent.unlink(missing_ok=True)
    if data.get("kind") != kind or time.time() - float(data.get("at", 0)) > TTL_SECONDS:
        return False
    record, since = transcript(session), max(float(data.get("asked", 0)), time.time() - TTL_SECONDS)
    try:
        if record and typed(record, str(data.get("code", "")), since, paths.session_id(session)):
            return True
        problem = (f"{record} shows no prompt from the principal with its code since it was asked for" if record else
                   "the harness gave no transcript for this session, and only that record can show who typed it")
    except OSError as exc:
        problem = f"the session's transcript could not be read ({exc})"
    code = request(kind, subject, str(data.get("summary", "")))
    raise Unverified(f"An approval for this call was recorded, but {problem}. Approvals come only from the principal's "
                     f"own prompt, so it was not used. Show them the exact call again and ask them to type {how(code)}.")

#!/usr/bin/env python3
"""Serve Slack acquisition from connector reads recorded in Claude Code transcripts.

The agent reads Slack through its MCP connector, and the Claude Code harness
records each call's exact input, raw result and completion time in the session
transcript. This adapter answers ``thread_checker.acquire_channel`` only from
those recorded calls, so every observation cites a real tool_use id rather than
agent-written custody. A read the transcripts do not hold raises MissingCall,
naming the exact call to make. Rendered message strings do not preserve source
boundaries, so this adapter retains call custody but refuses attributable
reconstruction and interval advancement. Structured Web API reads use SlackRead.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
import math
import re
from pathlib import Path

KIND = "claude-code-connector-replay-v1"
TOOLS = (
    "slack_read_channel",
    "slack_read_thread",
    "slack_search_public_and_private",
    "slack_read_user_profile",
)
TS = r"[1-9]\d{9}\.\d{6}"
ID = r"[A-Z][A-Z0-9]+"
MAX_LINE = 64 * 1024 * 1024
MAX_PROBE_PAGES = 10
DAY = timedelta(days=1)

SPILL = re.compile(
    r"Error: result \(([\d,]+) characters across [\d,]+ lines\) exceeds maximum "
    r"allowed tokens\. Output has been saved to (/\S+)\.\n"
)
CHANNEL_END = "There are no more messages available.\n"
CHANNEL_MORE = re.compile(
    r"There are more messages available\. To view the next page, use cursor: `([^`\s]+)`\n"
)
THREAD_END = "There are no more messages in this thread.\n"
SEARCH_END = "End of results - No more pages available.\n"
SEARCH_MORE = re.compile(r"For the next page of results use cursor `([^`\s]+)`\n")


class MissingCall(ValueError):
    """The transcripts hold no recorded call that answers this read."""

    def __init__(self, tool, arguments, reason):
        super().__init__(f"no recorded {tool} call answers this read: {reason}")
        self.call = {"tool": tool, "input": arguments, "reason": reason}


@dataclass(frozen=True)
class Call:
    tool: str
    call_id: str
    arguments: dict
    ok: bool
    text: str
    observed_at: datetime
    source: str


def _moment(value):
    if not isinstance(value, str):
        raise ValueError("transcript record lacks its timestamp")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("transcript timestamp is malformed") from exc
    if stamp.tzinfo is None:
        raise ValueError("transcript timestamp lacks an offset")
    return stamp


def _unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON key in a recorded connector result")
        value[key] = item
    return value


def _result_text(content):
    if isinstance(content, str):
        return content
    if (
        isinstance(content, list)
        and content
        and all(
            isinstance(item, dict)
            and item.get("type") == "text"
            and isinstance(item.get("text"), str)
            for item in content
        )
    ):
        return "".join(item["text"] for item in content)
    raise ValueError("recorded connector result is not text")


def _session_dir(path):
    # <project>/<session>.jsonl and <project>/<session>/subagents/agent-*.jsonl
    # share one session directory, which holds that session's tool results.
    return path.parent.parent if path.parent.name == "subagents" else path.with_suffix("")


def _spilled(text, session_dir):
    match = SPILL.match(text)
    if match is None:
        if text.startswith("<persisted-output>"):
            raise ValueError(
                "unsupported spilled connector output form; re-read with a smaller page"
            )
        return text
    target = Path(match[2])
    folder = session_dir / "tool-results"
    if (
        target.is_symlink()
        or not target.is_file()
        or target.resolve(strict=True).parent != folder.resolve(strict=True)
        or not re.fullmatch(r"mcp-[A-Za-z0-9_.-]+-slack_[a-z_]+-\d+\.(?:txt|json)", target.name)
    ):
        raise ValueError("spilled connector output is outside its session's tool results")
    data = target.read_text(encoding="utf-8")
    if len(data) != int(match[1].replace(",", "")):
        raise ValueError("spilled connector output differs from its recorded size")
    return data


def load_calls(paths, *, server, root):
    """Index one server's recorded Slack reads from the named transcripts.

    Returns (calls, receipts). Each receipt binds the exact transcript prefix
    read: byte count and sha256, re-checkable while the file only grows.
    """
    if not isinstance(server, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", server):
        raise ValueError("connector server identity required")
    names = {f"mcp__{server}__{tool}": tool for tool in TOOLS}
    try:
        root = Path(root).resolve(strict=True)
    except OSError as exc:
        raise ValueError("the Claude Code projects root does not exist") from exc
    uses, calls, results, receipts, seen = {}, {}, {}, [], set()
    for raw in paths:
        path = Path(raw)
        if (
            not path.is_absolute()
            or path.is_symlink()
            or not path.is_file()
            or path.suffix != ".jsonl"
        ):
            raise ValueError("transcripts must be absolute regular .jsonl files")
        real = path.resolve(strict=True)
        if root not in real.parents:
            raise ValueError("transcript is outside the Claude Code projects root")
        if real in seen:
            raise ValueError("transcript named twice")
        seen.add(real)
        session_dir = _session_dir(real)
        digest, size = hashlib.sha256(), 0
        with real.open("rb") as handle:
            for line in handle:
                # A live session may be mid-write; its partial last line is
                # not yet a record, and the receipt covers only what was read.
                if not line.endswith(b"\n"):
                    break
                if len(line) > MAX_LINE:
                    raise ValueError("transcript record exceeds the line bound")
                digest.update(line)
                size += len(line)
                try:
                    record = json.loads(line)
                except (ValueError, RecursionError) as exc:
                    raise ValueError("transcript line is not JSON") from exc
                message = record.get("message") if isinstance(record, dict) else None
                content = message.get("content") if isinstance(message, dict) else None
                if not isinstance(content, list):
                    continue
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    kind = block.get("type")
                    # The harness may write one record twice (same uuid, same
                    # bytes), for example on resume. An identical repeat is the
                    # same observation; a differing one under the same call id
                    # is a conflict.
                    if kind == "tool_use" and block.get("name") in names:
                        call_id = block.get("id")
                        arguments = block.get("input")
                        if not isinstance(call_id, str) or not call_id:
                            raise ValueError("invalid recorded tool call id")
                        if not isinstance(arguments, dict):
                            raise ValueError("recorded tool call input is not an object")
                        use = (names[block["name"]], arguments)
                        if uses.setdefault(call_id, use) != use:
                            raise ValueError("one recorded tool call id has two inputs")
                    elif kind == "tool_result" and block.get("tool_use_id") in uses:
                        call_id = block["tool_use_id"]
                        fingerprint = json.dumps(
                            [record.get("timestamp"), block], sort_keys=True
                        )
                        if call_id in results:
                            if results[call_id] != fingerprint:
                                raise ValueError("one recorded tool call has two results")
                            continue
                        results[call_id] = fingerprint
                        tool, arguments = uses[call_id]
                        text = _spilled(_result_text(block.get("content")), session_dir)
                        calls[call_id] = Call(
                            tool,
                            call_id,
                            arguments,
                            block.get("is_error") is not True
                            and not text.startswith("execution_failed"),
                            text,
                            _moment(record.get("timestamp")),
                            real.name,
                        )
        receipts.append({"path": str(real), "bytes": size, "sha256": digest.hexdigest()})
    return list(calls.values()), receipts


def _envelope(call, key):
    try:
        value = json.loads(call.text, object_pairs_hook=_unique)
    except (ValueError, RecursionError) as exc:
        raise ValueError("recorded connector result is not its documented JSON envelope") from exc
    if (
        not isinstance(value, dict)
        or set(value) - {key, "pagination_info"}
        or not isinstance(value.get(key), str)
        or not isinstance(value.get("pagination_info", ""), str)
    ):
        raise ValueError("recorded connector result is not its documented JSON envelope")
    return value[key], value.get("pagination_info", "")


def _refuse_rendered_records(call, key):
    # The source renderer does not escape message bodies or authenticate the
    # separators. One body quoting a header and two actual source messages can
    # have identical bytes. Retaining the raw call cannot restore lost boundaries.
    _envelope(call, key)
    raise ValueError(
        "Slack plaintext message boundaries are unavailable; no attributable "
        "records or complete interval can be reconstructed. Use the explicitly "
        "declared slack-web-api-v1 structured reader with authorized credentials."
    )


def parse_channel(call, channel_id):
    """Refuse lossy rendered channel records, including apparent empty pages."""
    return _refuse_rendered_records(call, "messages")


def parse_thread(call, channel_id, parent):
    """Refuse lossy rendered thread records; quoted reply headers are ambiguous."""
    return _refuse_rendered_records(call, "messages")


def parse_search(call):
    """Refuse lossy rendered search records; they cannot authenticate authors."""
    return _refuse_rendered_records(call, "results")


def parse_profile(call):
    body, _ = _envelope(call, "result")
    user = re.findall(rf"^User ID: ({ID})$", body, re.M)
    bot = re.findall(r"^Bot: (Yes|No)$", body, re.M)
    if len(user) != 1 or len(bot) != 1:
        raise ValueError("recorded profile lacks its user identity")
    return user[0], bot[0] == "No"


def _utc_day(value):
    return datetime.fromtimestamp(float(value), timezone.utc).date()


def _search_scope(arguments, channel_id, lo, hi, *, window):
    """Whether a recorded search reads exactly this conversation over the window.

    Slack's after:/before: days are exclusive and read in the searching user's
    time zone (UTC-12 to UTC+14), so a day filter must clear the window by two
    UTC days. The connector's after/before parameters are Unix timestamps,
    verified exact on 2026-10-01; they must bound the window strictly.
    """
    if (
        arguments.get("keywords") not in (None, [])
        or arguments.get("natural_language_query") not in (None, "")
        or arguments.get("content_types") not in (None, "messages")
        or arguments.get("channel_types") is not None
        or arguments.get("only_my_channels") not in (None, False)
        or arguments.get("response_format", "detailed") != "detailed"
    ):
        return False
    tokens = f"{arguments.get('query') or ''} {arguments.get('filters') or ''}".split()
    days = {}
    for token in tokens:
        if token == f"in:<#{channel_id}>":
            days.setdefault("in", 0)
            days["in"] += 1
            continue
        match = re.fullmatch(r"(after|before):(\d{4}-\d\d-\d\d)", token)
        if match is None or match[1] in days:
            return False
        days[match[1]] = datetime.strptime(match[2], "%Y-%m-%d").date()
    if days.pop("in", 0) != 1:
        return False
    try:
        after = None if arguments.get("after") in (None, "") else Decimal(arguments["after"])
        before = None if arguments.get("before") in (None, "") else Decimal(arguments["before"])
    except (ArithmeticError, TypeError, ValueError):
        return False
    upper_ok = (
        "before" not in days or days["before"] >= _utc_day(hi) + 2 * DAY
    ) and (before is None or before > hi)
    if not upper_ok:
        return False
    if window:
        lower_ok = (
            "after" not in days or days["after"] <= _utc_day(lo) - 2 * DAY
        ) and (after is None or after < lo)
        return lower_ok and arguments.get("include_bots") is True
    return arguments.get("sort") == "timestamp" and arguments.get("sort_dir") in (
        None,
        "desc",
    )


def _lower_bound(arguments):
    """A recorded search's lower bound, for preferring the tightest one."""
    if arguments.get("after") not in (None, ""):
        return Decimal(arguments["after"])
    tokens = f"{arguments.get('query') or ''} {arguments.get('filters') or ''}".split()
    for token in tokens:
        if token.startswith("after:"):
            day = datetime.strptime(token[6:], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            return Decimal(int(day.timestamp()))
    return Decimal("-Infinity")


class ConnectorReplay:
    """acquire_channel adapter answering only from recorded connector calls."""

    def __init__(self, calls, declared, server, *, through):
        if declared.get("kind") != KIND or set(declared) != {"kind", "user_id"}:
            raise ValueError("unknown or missing connector replay adapter fields")
        if not re.fullmatch(r"[UW][A-Z0-9]+", declared.get("user_id", "")):
            raise ValueError("declare the exact Slack user_id the connector reads as")
        if through.tzinfo is None:
            raise ValueError("an offset-bearing window end is required")
        self.calls, self.declared, self.server, self.through = calls, declared, server, through
        self.channels = set()
        self.chains = {}
        self.used = set()

    def _latest(self, tool, accept, key=None):
        found = [
            call
            for call in self.calls
            if call.tool == tool
            and call.ok
            and call.observed_at >= self.through
            and accept(call.arguments)
        ]
        if not found:
            return None
        call = max(found, key=key or (lambda c: (c.observed_at, c.call_id)))
        self.used.add(call.call_id)
        return call

    def _page(self, tool, chain, cursor, accept, wanted, reason, key=None):
        # Connector cursors are not unique across reads (a search's second
        # page is always the same token), so each chain is keyed by the read
        # it continues, never by the cursor alone.
        if cursor is None:
            call = self._latest(tool, lambda a: not a.get("cursor") and accept(a), key)
            if call is None:
                raise MissingCall(tool, wanted, reason)
            return call
        recorded = self.chains.get((tool, chain, cursor))
        if recorded is None:
            raise ValueError("pagination cursor has no recorded preceding page")
        base, previous = recorded
        # When one read was recorded more than once, the follow-up page is the
        # earliest one recorded after its own preceding page: the same pass.
        call = self._latest(
            tool,
            lambda a: a.get("cursor") == cursor
            and {k: v for k, v in a.items() if k != "cursor"} == base,
            key=lambda c: (c.observed_at >= previous, -c.observed_at.timestamp(), c.call_id),
        )
        if call is None or call.observed_at < previous:
            raise MissingCall(tool, {**base, "cursor": cursor}, "next page of a recorded read")
        return call

    def _chain(self, tool, chain, call, cursor):
        if cursor:
            self.chains[(tool, chain, cursor)] = (
                {k: v for k, v in call.arguments.items() if k != "cursor"},
                call.observed_at,
            )

    def _response(self, call, rows, cursor):
        return {
            "ok": True,
            "messages": rows,
            "response_metadata": {"next_cursor": cursor or ""},
            "tool_call_id": call.call_id,
            "observed_at": call.observed_at.isoformat(),
        }

    def readiness(self):
        call = self._latest(
            "slack_read_user_profile",
            lambda a: a.get("user_id") in (None, "")
            and a.get("response_format", "detailed") == "detailed",
        )
        if call is None:
            raise MissingCall(
                "slack_read_user_profile",
                {"response_format": "detailed"},
                "connector identity after the window closed",
            )
        user, human = parse_profile(call)
        if user != self.declared["user_id"] or not human:
            raise ValueError("Slack identity does not match the exact declared user")
        return {
            "status": "authenticated",
            "user_id": user,
            "server": self.server,
            "tool_call_id": call.call_id,
            "observed_at": call.observed_at.isoformat(),
            "capabilities": "connector reads replayed from client-recorded tool calls",
        }

    def describe(self, channel_id):
        if not isinstance(channel_id, str) or not re.fullmatch(r"[CDG][A-Z0-9]+", channel_id):
            raise ValueError("invalid declared conversation id")
        self.channels.add(channel_id)
        return None

    def _declared(self, channel_id, detail="detailed"):
        if detail != "detailed" or channel_id not in self.channels:
            raise ValueError("undeclared Slack connector read")

    def read_channel(self, *, channel_id, oldest, latest, cursor, limit, detail):
        self._declared(channel_id, detail)
        lo, hi = Decimal(oldest), Decimal(latest)

        def accept(a):
            # The provider's own boundary inclusivity is not observable, so a
            # recorded read must strictly enclose the window on both sides.
            try:
                return (
                    a.get("channel_id") == channel_id
                    and a.get("response_format", "detailed") == "detailed"
                    and a.get("oldest") not in (None, "")
                    and Decimal(a["oldest"]) < lo
                    and (a.get("latest") in (None, "") or Decimal(a["latest"]) > hi)
                )
            except (ArithmeticError, TypeError, ValueError):
                return False

        wanted = {
            "channel_id": channel_id,
            "oldest": f"{math.floor(lo) - 1}.000000",
            "latest": f"{math.floor(hi) + 2}.000000",
            "limit": 100,
            "response_format": "detailed",
        }
        chain = ("history", channel_id, oldest, latest)
        call = self._page("slack_read_channel", chain, cursor, accept, wanted, "window history")
        rows, after = parse_channel(call, channel_id)
        self._chain("slack_read_channel", chain, call, after)
        rows = [row for row in rows if lo <= Decimal(row["ts"]) <= hi]
        return self._response(call, rows, after)

    def search_replies(self, *, channel_id, oldest, latest, cursor, limit, detail):
        self._declared(channel_id, detail)
        lo, hi = Decimal(oldest), Decimal(latest)
        wanted = {
            "filters": f"in:<#{channel_id}>",
            "after": str(math.floor(lo) - 1),
            "before": str(math.floor(hi) + 2),
            "sort": "timestamp",
            "sort_dir": "asc",
            "limit": 20,
            "include_bots": True,
            "include_context": False,
            "natural_language_query": "",
            "response_format": "detailed",
        }
        tool = "slack_search_public_and_private"
        chain = ("window-search", channel_id, oldest, latest)
        call = self._page(
            tool,
            chain,
            cursor,
            lambda a: _search_scope(a, channel_id, lo, hi, window=True),
            wanted,
            "window search for thread discovery and the positive control",
            # A search unbounded below also encloses the window, but pages
            # through all history; prefer the tightest recorded bound.
            key=lambda c: (_lower_bound(c.arguments), c.observed_at, c.call_id),
        )
        rows, after = parse_search(call)
        self._chain(tool, chain, call, after)
        if any(row["channel"] != channel_id for row in rows):
            raise ValueError("recorded search returned another conversation")
        rows = [row for row in rows if lo <= Decimal(row["ts"]) <= hi]
        return self._response(call, rows, after)

    def read_thread(self, *, channel_id, message_ts, cursor, limit, detail):
        self._declared(channel_id, detail)
        if cursor is not None:
            raise ValueError("thread reads must be recorded complete in one page")
        call = self._latest(
            "slack_read_thread",
            lambda a: a.get("channel_id") == channel_id
            and a.get("message_ts") == message_ts
            and a.get("response_format", "detailed") == "detailed"
            and not a.get("cursor")
            and a.get("oldest") in (None, "")
            and a.get("latest") in (None, ""),
        )
        if call is None:
            raise MissingCall(
                "slack_read_thread",
                {
                    "channel_id": channel_id,
                    "message_ts": message_ts,
                    "limit": 1000,
                    "response_format": "detailed",
                },
                "full thread after the window closed",
            )
        return self._response(call, parse_thread(call, channel_id, message_ts), None)

    def probe_newest(self, *, channel_id, latest):
        self._declared(channel_id)
        hi = Decimal(latest)

        def accept(a):
            try:
                return (
                    a.get("channel_id") == channel_id
                    and a.get("response_format", "detailed") == "detailed"
                    and not a.get("cursor")
                    and a.get("oldest") in (None, "")
                    and (a.get("latest") in (None, "") or Decimal(a["latest"]) >= hi)
                )
            except (ArithmeticError, TypeError, ValueError):
                return False

        # Prefer the read bounded closest to the window's end: an unbounded
        # read can only add messages that arrived after the window closed.
        call = self._latest(
            "slack_read_channel",
            accept,
            key=lambda c: (
                -Decimal(c.arguments["latest"])
                if c.arguments.get("latest") not in (None, "")
                else Decimal("-Infinity"),
                c.observed_at,
                c.call_id,
            ),
        )
        if call is None:
            raise MissingCall(
                "slack_read_channel",
                {
                    "channel_id": channel_id,
                    "latest": latest,
                    "limit": 1,
                    "response_format": "detailed",
                },
                "quiet channel: newest message at or before the window's end",
            )
        # History is newest first, so the first page holds the newest message.
        rows, _ = parse_channel(call, channel_id)
        newest = max((row["ts"] for row in rows), key=Decimal, default=None)
        return {
            "ok": True,
            "newest_ts": newest,
            "tool_call_id": call.call_id,
            "observed_at": call.observed_at.isoformat(),
        }

    def probe_search_newest(self, *, channel_id, latest):
        self._declared(channel_id)
        hi = Decimal(latest)
        tool = "slack_search_public_and_private"
        wanted = {
            "filters": f"in:<#{channel_id}>",
            "before": str(math.floor(hi) + 2),
            "sort": "timestamp",
            "sort_dir": "desc",
            "limit": 20,
            "include_bots": True,
            "include_context": False,
            "natural_language_query": "",
            "response_format": "detailed",
        }
        cursor = None
        chain = ("newest-search", channel_id, latest)
        for _ in range(MAX_PROBE_PAGES):
            call = self._page(
                tool,
                chain,
                cursor,
                lambda a: _search_scope(a, channel_id, hi, hi, window=False),
                wanted,
                "quiet channel: newest search-indexed message at or before the window's end",
            )
            rows, cursor = parse_search(call)
            self._chain(tool, chain, call, cursor)
            if any(row["channel"] != channel_id for row in rows):
                raise ValueError("recorded search returned another conversation")
            # Newest first: the first page holding an eligible message holds
            # the newest one at or before the window's end.
            eligible = [row["ts"] for row in rows if Decimal(row["ts"]) <= hi]
            if eligible or cursor is None:
                return {
                    "ok": True,
                    "newest_ts": max(eligible, key=Decimal, default=None),
                    "tool_call_id": call.call_id,
                    "observed_at": call.observed_at.isoformat(),
                }
        raise ValueError("newest search probe page bound reached")


def plan_channel(adapter, channel_id, start, through, known_thread_ids=()):
    """Every recorded call one channel still needs, and any blocking problem.

    Calls that depend on unread results (threads a missing search would find,
    quiet-channel probes) surface on the next pass, once those reads exist.
    """
    lo, hi = Decimal(str(start.timestamp())), Decimal(str(through.timestamp()))
    missing = []

    def drain(read, **arguments):
        rows, cursor = [], None
        for _ in range(100):
            try:
                page = read(**arguments, cursor=cursor, limit=100, detail="detailed")
            except MissingCall as gap:
                missing.append(gap.call)
                return None
            rows += page["messages"]
            cursor = page["response_metadata"]["next_cursor"]
            if not cursor:
                return rows
        raise ValueError("page bound reached; coverage unknown")

    window = {"channel_id": channel_id, "oldest": str(lo), "latest": str(hi)}
    history = drain(adapter.read_channel, **window)
    hits = drain(adapter.search_replies, **window)
    parents = set(known_thread_ids)
    parents |= {row["ts"] for row in history or [] if row.get("reply_count")}
    parents |= {row["thread_ts"] for row in hits or [] if row.get("thread_ts")}
    for parent in sorted(parents):
        try:
            adapter.read_thread(
                channel_id=channel_id,
                message_ts=parent,
                cursor=None,
                limit=1000,
                detail="detailed",
            )
        except MissingCall as gap:
            missing.append(gap.call)
    problems = []
    if hits == [] and history:
        problems.append(
            "history holds in-window messages the window search did not return; "
            "search coverage of this conversation is unknown"
        )
    elif hits == [] and history == []:
        for probe in (adapter.probe_newest, adapter.probe_search_newest):
            try:
                newest = probe(channel_id=channel_id, latest=str(hi))["newest_ts"]
            except MissingCall as gap:
                missing.append(gap.call)
                continue
            if newest is None or Decimal(newest) >= lo:
                problems.append(
                    "a quiet-channel probe found no message predating the window; "
                    "this conversation's coverage stays unknown"
                )
                break
    return missing, problems

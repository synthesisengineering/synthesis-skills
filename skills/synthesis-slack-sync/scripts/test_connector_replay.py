"""Connector replay uses synthetic transcripts in the connector's recorded formats."""

import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / "synthesis-daily-rituals/scripts"))
import acquire  # noqa: E402
import connector_replay as R  # noqa: E402
import thread_checker  # noqa: E402

SERVER = "server-1"
NOW = datetime.now(timezone.utc).replace(microsecond=0)
END = NOW - timedelta(hours=1)
START = END - timedelta(hours=2)
READ_AT = NOW - timedelta(minutes=30)
LO = R.Decimal(str(START.timestamp()))
HI = R.Decimal(str(END.timestamp()))


def ts(moment, micro=1):
    return f"{int(moment.timestamp())}.{micro:06d}"


OLD_PARENT = ts(START - timedelta(days=3))
TOP = ts(START + timedelta(minutes=10))
REPLY = ts(START + timedelta(minutes=20))
QUIET_NEWEST = ts(START - timedelta(days=9))


def stamp(moment):
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def message(user, ts_value, text, *, replies=0, reactions=""):
    block = (
        f"=== Message from Synthetic Person <person@example.invalid> ({user}) at "
        f"2026-09-26 08:00:00 EDT === \nMessage TS: {ts_value}\n{text}"
    )
    if replies:
        block += f"\nThread: {replies} replies (latest: 2026-09-26 08:30:00 EDT)"
    if reactions:
        block += f"\nReactions: {reactions}"
    return block


def channel_page(cid, blocks, cursor=None, name="#busy"):
    body = f"Channel: {name} ({cid})\n" + ("\n" + "\n\n".join(blocks) if blocks else "")
    more = (
        f"There are more messages available. To view the next page, use cursor: `{cursor}`\n"
        if cursor
        else R.CHANNEL_END
    )
    return {"messages": body, "pagination_info": more}


def thread_page(parent, parent_text, replies, *, empty_marker=False):
    body = (
        "=== THREAD PARENT MESSAGE ===\nFrom: Synthetic Person <person@example.invalid> "
        f"(U0AUTHOR)\nTime: 2026-09-23 08:00:00 EDT\nMessage TS: {parent}\n{parent_text}"
    )
    if replies:
        body += f"\n\n=== THREAD REPLIES ({len(replies)} total) ===\n"
        for k, (user, ts_value, text) in enumerate(replies, 1):
            body += (
                f"\n--- Reply {k} of {len(replies)} ---\nFrom: Synthetic Person "
                f"<person@example.invalid> ({user})\nTime: 2026-09-26 08:00:00 EDT\n"
                f"Message TS: {ts_value}\n{text}\n"
            )
    elif empty_marker:
        body += "\n\nNo thread messsages\n"
    return {"messages": body, "pagination_info": R.THREAD_END}


def search_page(cid, hits, cursor=None):
    if not hits:
        results = "# Search Results for: \n\nNo results found.\n"
    else:
        parts = []
        for k, (user, ts_value, parent, text) in enumerate(hits, 1):
            link = f"https://example.enterprise.slack.com/archives/{cid}/p{ts_value.replace('.', '')}"
            if parent:
                link += f"?thread_ts={parent}&cid={cid}"
            parts.append(
                f"### Result {k} of {len(hits)}\nChannel: #busy (ID: {cid})\n"
                f"From: Synthetic Person <person@example.invalid> (ID: {user}) \n"
                f"Time: 2026-09-26 08:00:00 EDT\nMessage_ts: {ts_value}\n"
                f"Permalink: [link]({link})\nText: \n{text}\n"
                f"Context after: \n- From: Other (ID: U0OTHER) \n  Message_ts: {OLD_PARENT}\n\n---\n\n"
            )
        results = f"# Search Results for: \n\n## Messages ({len(hits)} results)\n" + "".join(parts)
    more = (
        f"For the next page of results use cursor `{cursor}`\n"
        if cursor
        else "End of results - No more pages available.\\n"
    )
    return {"results": results, "pagination_info": more}


class Transcript:
    def __init__(self, root, name="session-1"):
        self.project = root / "-synthetic-project"
        self.project.mkdir(parents=True, exist_ok=True)
        self.path = self.project / f"{name}.jsonl"
        self.records = []
        self.count = 0

    def call(self, tool, arguments, result, *, at=READ_AT, error=False, server=SERVER):
        self.count += 1
        call_id = f"toolu_{self.path.stem}_{self.count:04d}"
        self.records.append(
            {
                "type": "assistant",
                "uuid": f"a{self.count}",
                "timestamp": stamp(at - timedelta(seconds=1)),
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "id": call_id,
                            "name": f"mcp__{server}__{tool}",
                            "input": arguments,
                        }
                    ]
                },
            }
        )
        text = result if isinstance(result, str) else json.dumps(result)
        block = {"type": "tool_result", "tool_use_id": call_id, "content": [{"type": "text", "text": text}]}
        if error:
            block["is_error"] = True
        self.records.append(
            {"type": "user", "uuid": f"u{self.count}", "timestamp": stamp(at), "message": {"content": [block]}}
        )
        return call_id

    def write(self, tail=b""):
        self.path.write_bytes(
            "".join(json.dumps(r) + "\n" for r in self.records).encode() + tail
        )
        return self.path


def window_search(cid, **extra):
    return {
        "filters": f"in:<#{cid}>",
        "after": str(int(LO) - 1),
        "before": str(int(HI) + 2),
        "sort": "timestamp",
        "sort_dir": "asc",
        "limit": 20,
        "include_bots": True,
        "include_context": False,
        "natural_language_query": "",
        "response_format": "detailed",
        **extra,
    }


def history_args(cid, **extra):
    return {
        "channel_id": cid,
        "oldest": f"{int(LO) - 1}.000000",
        "latest": f"{int(HI) + 2}.000000",
        "limit": 100,
        "response_format": "detailed",
        **extra,
    }


def record_busy(t, cid="C1BUSY"):
    t.call(
        "slack_read_channel",
        history_args(cid),
        channel_page(cid, [message("U0AUTHOR", TOP, "Top-level <@U0PEER|Peer Name> note", reactions="eyes (1)")]),
    )
    t.call(
        "slack_search_public_and_private",
        window_search(cid),
        search_page(cid, [("U0PEER", REPLY, OLD_PARENT, "reply text as search renders it")]),
    )
    t.call(
        "slack_read_thread",
        {"channel_id": cid, "message_ts": OLD_PARENT, "limit": 1000, "response_format": "detailed"},
        thread_page(OLD_PARENT, "Old parent", [("U0PEER", REPLY, "A reply in the window")]),
    )


def record_quiet(t, cid="C2QUIET"):
    t.call("slack_read_channel", history_args(cid), channel_page(cid, [], name="#quiet"))
    t.call("slack_search_public_and_private", window_search(cid), search_page(cid, []))
    t.call(
        "slack_read_channel",
        {"channel_id": cid, "latest": str(HI), "limit": 1, "response_format": "detailed"},
        channel_page(cid, [message("U0AUTHOR", QUIET_NEWEST, "Older note")], cursor="older", name="#quiet"),
    )
    t.call(
        "slack_search_public_and_private",
        {
            "filters": f"in:<#{cid}>",
            "before": str(int(HI) + 2),
            "sort": "timestamp",
            "sort_dir": "desc",
            "limit": 20,
            "include_bots": True,
            "include_context": False,
            "natural_language_query": "",
            "response_format": "detailed",
        },
        search_page(cid, [("U0AUTHOR", QUIET_NEWEST, None, "Older note")]),
    )


def record_profile(t, user="U0SELF", bot="No"):
    t.call(
        "slack_read_user_profile",
        {"response_format": "detailed"},
        {"result": f"User ID: {user}\nUsername: synthetic\nAdmin: No\nBot: {bot}\nRestricted: No\n"},
    )


def replay(tmp_path, transcript=None, through=END):
    path = (transcript or recorded(tmp_path)).write()
    calls, receipts = R.load_calls([path], server=SERVER, root=tmp_path)
    adapter = R.ConnectorReplay(calls, {"kind": R.KIND, "user_id": "U0SELF"}, SERVER, through=through)
    for cid in ("C1BUSY", "C2QUIET"):
        adapter.describe(cid)
    return adapter, receipts


def recorded(tmp_path):
    t = Transcript(tmp_path)
    record_profile(t)
    record_busy(t)
    record_quiet(t)
    return t


def collect(adapter, cid):
    return thread_checker.acquire_channel(
        cid,
        START,
        END,
        read_channel=adapter.read_channel,
        read_thread=adapter.read_thread,
        search_replies=adapter.search_replies,
        probe_newest=adapter.probe_newest,
        probe_search_newest=adapter.probe_search_newest,
    )


def test_recorded_reads_satisfy_the_evidence_contract(tmp_path):
    # Retain the historical case ID: raw custody never proved per-message
    # attribution. The repaired contract refuses both busy and quiet renderings.
    adapter, transcript = replay(tmp_path)
    assert adapter.readiness()["user_id"] == "U0SELF"
    for cid in ("C1BUSY", "C2QUIET"):
        with pytest.raises(ValueError, match="plaintext message boundaries"):
            collect(adapter, cid)
    assert not list(tmp_path.rglob("*.md"))


def test_reads_before_the_window_closed_do_not_count(tmp_path):
    t = Transcript(tmp_path)
    t.call("slack_read_channel", history_args("C1BUSY"), channel_page("C1BUSY", []), at=END - timedelta(minutes=5))
    adapter, _ = replay(tmp_path, t)
    with pytest.raises(R.MissingCall) as gap:
        collect(adapter, "C1BUSY")
    assert gap.value.call["tool"] == "slack_read_channel"
    assert gap.value.call["input"] == history_args("C1BUSY")


def test_history_window_must_be_strictly_enclosed(tmp_path):
    t = Transcript(tmp_path)
    t.call("slack_read_channel", history_args("C1BUSY", oldest=str(LO)), channel_page("C1BUSY", []))
    adapter, _ = replay(tmp_path, t)
    with pytest.raises(R.MissingCall):
        adapter.read_channel(channel_id="C1BUSY", oldest=str(LO), latest=str(HI), cursor=None, limit=100, detail="detailed")


def test_history_cursor_chain_is_followed_exactly(tmp_path):
    t = Transcript(tmp_path)
    first = message("U0AUTHOR", TOP, "Newest")
    second = message("U0AUTHOR", ts(START + timedelta(minutes=1)), "Older in window")
    t.call("slack_read_channel", history_args("C1BUSY"), channel_page("C1BUSY", [first], cursor="page-2"))
    t.call("slack_read_channel", history_args("C1BUSY", cursor="page-2"), channel_page("C1BUSY", [second]))
    adapter, _ = replay(tmp_path, t)
    args = dict(channel_id="C1BUSY", oldest=str(LO), latest=str(HI), limit=100, detail="detailed")
    with pytest.raises(ValueError, match="plaintext message boundaries"):
        adapter.read_channel(cursor=None, **args)
    # A refused first page must not establish a cursor chain.
    with pytest.raises(ValueError, match="no recorded preceding page"):
        adapter.read_channel(cursor="page-2", **args)
    with pytest.raises(ValueError, match="no recorded preceding page"):
        adapter.read_channel(cursor="unknown", **args)


@pytest.mark.parametrize(
    "change, accepted",
    [
        ({}, True),
        ({"include_bots": False}, False),
        ({"keywords": ["launch"]}, False),
        ({"natural_language_query": "what happened"}, False),
        ({"after": str(int(LO) - 3600)}, True),
        ({"after": str(int(LO))}, False),
        ({"before": str(int(HI))}, False),
        ({"filters": "in:<#C1BUSY> is:thread"}, False),
        ({"filters": "in:<#C9OTHER>"}, False),
        ({"content_types": "messages,files"}, False),
        ({"filters": "in:<#C1BUSY> after:DAYS_BEFORE_2", "after": None}, True),
        ({"filters": "in:<#C1BUSY> after:DAYS_BEFORE_1", "after": None}, False),
        ({"filters": "in:<#C1BUSY> before:DAYS_AFTER_1", "before": None}, False),
    ],
)
def test_window_search_scope(change, accepted):
    day = R._utc_day(LO)
    arguments = window_search("C1BUSY")
    for key, value in change.items():
        if isinstance(value, str):
            value = (
                value.replace("DAYS_BEFORE_2", str(day - 2 * R.DAY))
                .replace("DAYS_BEFORE_1", str(day - R.DAY))
                .replace("DAYS_AFTER_1", str(R._utc_day(HI) + R.DAY))
            )
        if value is None:
            arguments.pop(key)
        else:
            arguments[key] = value
    assert R._search_scope(arguments, "C1BUSY", LO, HI, window=True) is accepted


def test_quiet_probe_prefers_the_read_bounded_at_the_window_end(tmp_path):
    t = recorded(tmp_path)
    t.call(
        "slack_read_channel",
        {"channel_id": "C2QUIET", "limit": 1, "response_format": "detailed"},
        channel_page("C2QUIET", [message("U0AUTHOR", ts(NOW - timedelta(minutes=40)), "After the window")], name="#quiet"),
        at=NOW - timedelta(minutes=10),
    )
    adapter, _ = replay(tmp_path, t)
    with pytest.raises(ValueError, match="plaintext message boundaries"):
        collect(adapter, "C2QUIET")


def test_search_probe_skips_messages_after_the_window(tmp_path):
    t = Transcript(tmp_path)
    late = ts(NOW - timedelta(minutes=45))
    base = {
        "filters": "in:<#C2QUIET>",
        "sort": "timestamp",
        "include_bots": True,
        "response_format": "detailed",
    }
    t.call("slack_search_public_and_private", base, search_page("C2QUIET", [("U0AUTHOR", late, None, "late")], cursor="p2"))
    t.call("slack_search_public_and_private", {**base, "cursor": "p2"}, search_page("C2QUIET", [("U0AUTHOR", QUIET_NEWEST, None, "older")]))
    adapter, _ = replay(tmp_path, t)
    with pytest.raises(ValueError, match="plaintext message boundaries"):
        adapter.probe_search_newest(channel_id="C2QUIET", latest=str(HI))


def test_thread_and_channel_renderings_agree_on_message_text(tmp_path):
    t = Transcript(tmp_path)
    parent = ts(START + timedelta(minutes=5))
    text = "Parent <@U0PEER|Old Display Name> asks"
    t.call(
        "slack_read_channel",
        history_args("C1BUSY"),
        channel_page("C1BUSY", [message("U0AUTHOR", parent, text, replies=2, reactions="eyes (2), white_check_mark (1)")]),
    )
    t.call(
        "slack_read_thread",
        {"channel_id": "C1BUSY", "message_ts": parent},
        thread_page(parent, text.replace("Old Display Name", "New Display Name") + "\nReactions: eyes (3)", []),
    )
    adapter, _ = replay(tmp_path, t)
    window = dict(channel_id="C1BUSY", oldest=str(LO), latest=str(HI), cursor=None, limit=100, detail="detailed")
    with pytest.raises(ValueError, match="plaintext message boundaries"):
        adapter.read_channel(**window)
    with pytest.raises(ValueError, match="plaintext message boundaries"):
        adapter.read_thread(channel_id="C1BUSY", message_ts=parent, cursor=None, limit=1000, detail="detailed")


def test_parent_without_replies_drops_the_provider_marker(tmp_path):
    t = Transcript(tmp_path)
    t.call("slack_read_thread", {"channel_id": "C1BUSY", "message_ts": OLD_PARENT}, thread_page(OLD_PARENT, "Alone", [], empty_marker=True))
    adapter, _ = replay(tmp_path, t)
    with pytest.raises(ValueError, match="plaintext message boundaries"):
        adapter.read_thread(channel_id="C1BUSY", message_ts=OLD_PARENT, cursor=None, limit=1000, detail="detailed")


@pytest.mark.parametrize("kind", ["count", "paginated", "parent", "sequence"])
def test_thread_reads_must_be_whole(tmp_path, kind):
    page = thread_page(OLD_PARENT, "Parent", [("U0PEER", REPLY, "one"), ("U0PEER", TOP, "two")])
    if kind == "count":
        page["messages"] = page["messages"].replace("(2 total)", "(3 total)")
    if kind == "paginated":
        page["pagination_info"] = "There are more messages available. To view the next page, use cursor: `x`\n"
    if kind == "parent":
        page["messages"] = page["messages"].replace(f"Message TS: {OLD_PARENT}", f"Message TS: {TOP}", 1)
    if kind == "sequence":
        page["messages"] = page["messages"].replace("Reply 2 of 2", "Reply 3 of 2")
    t = Transcript(tmp_path)
    t.call("slack_read_thread", {"channel_id": "C1BUSY", "message_ts": OLD_PARENT}, page)
    adapter, _ = replay(tmp_path, t)
    with pytest.raises(ValueError):
        adapter.read_thread(channel_id="C1BUSY", message_ts=OLD_PARENT, cursor=None, limit=1000, detail="detailed")


@pytest.mark.parametrize("kind", ["foreign-channel", "pagination", "bot-author"])
def test_search_page_shapes(tmp_path, kind):
    page = search_page("C1BUSY", [("U0PEER", REPLY, OLD_PARENT, "hit")])
    if kind == "foreign-channel":
        page["results"] = page["results"].replace("(ID: C1BUSY)", "(ID: C9OTHER)")
    if kind == "pagination":
        page["pagination_info"] = "Some new pagination wording\n"
    if kind == "bot-author":
        page["results"] = page["results"].replace("(ID: U0PEER) \n", "(ID: B0BOT)  [BOT]\n")
    t = Transcript(tmp_path)
    t.call("slack_search_public_and_private", window_search("C1BUSY"), page)
    adapter, _ = replay(tmp_path, t)
    read = lambda: adapter.search_replies(  # noqa: E731
        channel_id="C1BUSY", oldest=str(LO), latest=str(HI), cursor=None, limit=20, detail="detailed"
    )
    with pytest.raises(ValueError, match="plaintext message boundaries"):
        read()


def test_identity_must_be_the_declared_human_user(tmp_path):
    for user, bot in (("U0OTHER", "No"), ("U0SELF", "Yes")):
        t = Transcript(tmp_path, name=f"{user}-{bot}")
        record_profile(t, user, bot)
        adapter, _ = replay(tmp_path, t)
        with pytest.raises(ValueError, match="identity"):
            adapter.readiness()
    t = Transcript(tmp_path, name="other-user")
    t.call("slack_read_user_profile", {"user_id": "U0SELF"}, {"result": "User ID: U0SELF\nBot: No\n"})
    adapter, _ = replay(tmp_path, t)
    with pytest.raises(R.MissingCall):
        adapter.readiness()


def test_failed_and_foreign_server_calls_are_not_evidence(tmp_path):
    t = Transcript(tmp_path)
    t.call("slack_read_channel", history_args("C1BUSY"), "execution_failed: channel_not_found")
    t.call("slack_read_channel", history_args("C1BUSY"), channel_page("C1BUSY", []), server="server-2")
    t.call("slack_read_channel", history_args("C1BUSY"), channel_page("C1BUSY", []), error=True)
    adapter, _ = replay(tmp_path, t)
    with pytest.raises(R.MissingCall):
        adapter.read_channel(channel_id="C1BUSY", oldest=str(LO), latest=str(HI), cursor=None, limit=100, detail="detailed")


def test_transcript_loading_bounds(tmp_path):
    t = recorded(tmp_path)
    duplicate = t.records[1]
    t.records.append(duplicate)
    path = t.write(tail=b'{"partial": ')
    calls, receipts = R.load_calls([path], server=SERVER, root=tmp_path)
    assert len(calls) == len(t.records[:-1]) // 2
    data = path.read_bytes()
    assert receipts[0]["bytes"] == len(data) - len(b'{"partial": ')
    assert receipts[0]["sha256"] == hashlib.sha256(data[: receipts[0]["bytes"]]).hexdigest()
    changed = json.loads(json.dumps(duplicate))
    changed["message"]["content"][0]["content"][0]["text"] = "{}"
    t.records.append(changed)
    with pytest.raises(ValueError, match="two results"):
        R.load_calls([t.write()], server=SERVER, root=tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    with pytest.raises(ValueError, match="outside"):
        R.load_calls([path], server=SERVER, root=elsewhere)
    with pytest.raises(ValueError, match="does not exist"):
        R.load_calls([path], server=SERVER, root=tmp_path / "missing")
    alias = tmp_path / "alias.jsonl"
    alias.symlink_to(path)
    with pytest.raises(ValueError, match="regular"):
        R.load_calls([alias], server=SERVER, root=tmp_path)


def test_spilled_results_resolve_inside_their_session_only(tmp_path):
    t = Transcript(tmp_path)
    page = json.dumps(channel_page("C1BUSY", [message("U0AUTHOR", TOP, "Spilled")]))
    folder = t.project / t.path.stem / "tool-results"
    folder.mkdir(parents=True)
    spill = folder / "mcp-server-1-slack_read_channel-1790000000000.txt"
    spill.write_text(page)
    note = (
        f"Error: result ({len(page):,} characters across 1 lines) exceeds maximum allowed tokens. "
        f"Output has been saved to {spill}.\nFormat: JSON\n"
    )
    t.call("slack_read_channel", history_args("C1BUSY"), note)
    adapter, _ = replay(tmp_path, t)
    window = dict(channel_id="C1BUSY", oldest=str(LO), latest=str(HI), cursor=None, limit=100, detail="detailed")
    with pytest.raises(ValueError, match="plaintext message boundaries"):
        adapter.read_channel(**window)
    assert spill.read_text() == page
    spill.write_text(page + " ")
    with pytest.raises(ValueError, match="recorded size"):
        replay(tmp_path, t)
    t.records[-1]["message"]["content"][0]["content"][0]["text"] = "<persisted-output>\nOutput too large"
    with pytest.raises(ValueError, match="unsupported spilled"):
        replay(tmp_path, t)


def test_plan_names_every_missing_call_and_then_the_dependent_ones(tmp_path):
    t = Transcript(tmp_path)
    t.write()
    adapter, _ = replay(tmp_path, t)
    missing, problems = R.plan_channel(adapter, "C1BUSY", START, END, known_thread_ids=[OLD_PARENT])
    assert [m["tool"] for m in missing] == [
        "slack_read_channel",
        "slack_search_public_and_private",
        "slack_read_thread",
    ]
    assert problems == []
    t = Transcript(tmp_path, name="second-pass")
    t.call("slack_read_channel", history_args("C2QUIET"), channel_page("C2QUIET", []))
    t.call("slack_search_public_and_private", window_search("C2QUIET"), search_page("C2QUIET", []))
    adapter, _ = replay(tmp_path, t)
    with pytest.raises(ValueError, match="plaintext message boundaries"):
        R.plan_channel(adapter, "C2QUIET", START, END)


def test_acquire_replays_saves_validates_and_advances(tmp_path):
    t = recorded(tmp_path)
    path = t.write()
    registry = tmp_path / "registry.yaml"
    registry.write_text(
        "version: 1\nmode: isolated\nworkspaces:\n"
        f"  - name: fixture\n    domain: fixture.slack.com\n    token: mcp:{SERVER}\n"
    )
    repo = tmp_path / "repo"
    (repo / "transcripts").mkdir(parents=True)
    capture = tmp_path / "capture"
    capture.mkdir()
    cfg = {
        "workspace": "fixture",
        "channels": [{"name": "#busy", "id": "C1BUSY"}, {"name": "#quiet", "id": "C2QUIET"}],
        "transcripts_repo": str(repo),
        "transcripts_path": "transcripts",
        "acquisition_adapter": {"kind": R.KIND, "user_id": "U0SELF"},
    }
    home = tmp_path / "state"
    common = dict(
        through=END.isoformat(),
        backfill=START.isoformat(),
        capture_root=str(capture),
        evidence_path=str(tmp_path / "evidence.json"),
        home=home,
        transcripts=[str(path)],
        transcript_root=tmp_path,
    )
    plan = acquire.acquire(cfg, registry, mode="plan", **common)
    assert not plan["ready"] and plan["missing_calls"] == []
    assert set(plan["problems"]) == {"C1BUSY", "C2QUIET"}
    before = path.read_bytes()
    with pytest.raises(ValueError, match="no declared conversation has provable coverage"):
        acquire.acquire(cfg, registry, advance=True, **common)
    assert not home.exists() and not list(repo.rglob("*.md"))
    assert path.read_bytes() == before  # source custody remains lossless
    calls, receipts = R.load_calls([path], server=SERVER, root=tmp_path)
    assert {c.tool for c in calls} == set(R.TOOLS)
    assert receipts[0]["sha256"] == hashlib.sha256(before).hexdigest()
    with pytest.raises(ValueError, match="mcp:"):
        registry.write_text(registry.read_text().replace(f"mcp:{SERVER}", "env:SYNTHETIC_TOKEN"))
        acquire.acquire(cfg, registry, mode="plan", **common)


def test_direct_adapter_refuses_transcripts_and_plans(tmp_path):
    registry = tmp_path / "registry.yaml"
    registry.write_text(
        "version: 1\nmode: isolated\nworkspaces:\n"
        "  - name: fixture\n    domain: fixture.slack.com\n    token: env:SYNTHETIC_TOKEN\n"
    )
    (tmp_path / "repo" / "transcripts").mkdir(parents=True)
    cfg = {
        "workspace": "fixture",
        "channels": [{"name": "#busy", "id": "C1BUSY"}],
        "transcripts_repo": str(tmp_path / "repo"),
        "transcripts_path": "transcripts",
        "acquisition_adapter": {"kind": "slack-web-api-v1", "team_id": "T0FIX", "user_id": "U0SELF"},
    }
    with pytest.raises(ValueError, match="connector replay only"):
        acquire.acquire(
            cfg,
            registry,
            mode="plan",
            through=END.isoformat(),
            backfill=START.isoformat(),
            capture_root=str(tmp_path),
            evidence_path=str(tmp_path / "e.json"),
            home=tmp_path / "state",
        )


def test_archive_skips_discovery_only_search_rows():
    channel = {
        "id": "C1BUSY",
        "history": {"messages": [{"ts": TOP, "text": "kept"}]},
        "reply_search": {
            "messages": [{"ts": TOP, "text": "rendered differently", "discovery_only": True}]
        },
        "threads": [],
    }
    _, indexed = acquire.raw_records(channel)
    assert [row["text"] for row in indexed[TOP]] == ["kept"]
    channel["reply_search"]["messages"][0].pop("discovery_only")
    with pytest.raises(ValueError, match="conflicting"):
        acquire.raw_records(channel)


if os.name != "posix":  # pragma: no cover - symlink fixtures are POSIX-only
    pytestmark = pytest.mark.skip("POSIX file semantics required")


def test_identical_cursors_from_different_reads_never_cross(tmp_path):
    t = Transcript(tmp_path)
    for cid, older in (("C1BUSY", "busy older"), ("C2QUIET", "quiet older")):
        first = ("U0AUTHOR", ts(START + timedelta(minutes=30)), None, "newer")
        t.call("slack_search_public_and_private", window_search(cid), search_page(cid, [first], cursor="CURRENT_PAGE:2"))
        second = ("U0AUTHOR", ts(START + timedelta(minutes=5)), None, older)
        t.call("slack_search_public_and_private", window_search(cid, cursor="CURRENT_PAGE:2"), search_page(cid, [second]))
    adapter, _ = replay(tmp_path, t)
    args = dict(oldest=str(LO), latest=str(HI), limit=20, detail="detailed")
    for cid in ("C1BUSY", "C2QUIET"):
        with pytest.raises(ValueError, match="plaintext message boundaries"):
            adapter.search_replies(channel_id=cid, cursor=None, **args)
        with pytest.raises(ValueError, match="no recorded preceding page"):
            adapter.search_replies(channel_id=cid, cursor="CURRENT_PAGE:2", **args)


def test_window_search_prefers_the_tightest_recorded_bound(tmp_path):
    t = recorded(tmp_path)
    # The quiet probe recorded later is bounded only above, so it also
    # encloses the window, but it pages through all of history.
    t.call(
        "slack_search_public_and_private",
        {**window_search("C1BUSY"), "after": None, "sort_dir": "desc"},
        search_page("C1BUSY", [("U0AUTHOR", OLD_PARENT, None, "old")], cursor="CURRENT_PAGE:2"),
        at=NOW - timedelta(minutes=5),
    )
    adapter, _ = replay(tmp_path, t)
    with pytest.raises(ValueError, match="plaintext message boundaries"):
        collect(adapter, "C1BUSY")


def test_slack_connect_senders_parse_in_every_read_shape(tmp_path):
    t = Transcript(tmp_path)
    external = message("U0AUTHOR", TOP, "From a partner").replace(
        "(U0AUTHOR)", "(U0AUTHOR, external: Partner Studio)"
    )
    t.call("slack_read_channel", history_args("C1BUSY"), channel_page("C1BUSY", [external]))
    page = thread_page(OLD_PARENT, "Parent", [("U0PEER", REPLY, "reply")])
    page["messages"] = page["messages"].replace("(U0PEER)", "(U0PEER, external: Partner Studio)")
    t.call("slack_read_thread", {"channel_id": "C1BUSY", "message_ts": OLD_PARENT}, page)
    hits = search_page("C1BUSY", [("U0PEER", REPLY, OLD_PARENT, "reply")])
    hits["results"] = hits["results"].replace("(ID: U0PEER) \n", "(ID: U0PEER, external: Partner Studio) \n")
    t.call("slack_search_public_and_private", window_search("C1BUSY"), hits)
    adapter, _ = replay(tmp_path, t)
    window = dict(channel_id="C1BUSY", oldest=str(LO), latest=str(HI), cursor=None, detail="detailed")
    with pytest.raises(ValueError, match="plaintext message boundaries"):
        adapter.read_channel(limit=100, **window)
    with pytest.raises(ValueError, match="plaintext message boundaries"):
        adapter.search_replies(limit=20, **window)
    with pytest.raises(ValueError, match="plaintext message boundaries"):
        adapter.read_thread(channel_id="C1BUSY", message_ts=OLD_PARENT, cursor=None, limit=1000, detail="detailed")


def test_unprovable_conversation_stays_unknown_while_others_advance(tmp_path):
    t = recorded(tmp_path)
    for cid in ("D3EMPTY", "D4QUIET"):
        t.call("slack_read_channel", history_args(cid), channel_page(cid, [], name="DM"))
        t.call("slack_search_public_and_private", window_search(cid), search_page(cid, []))
        newest = [] if cid == "D3EMPTY" else [message("U0AUTHOR", QUIET_NEWEST, "older")]
        t.call(
            "slack_read_channel",
            {"channel_id": cid, "latest": str(HI), "limit": 1, "response_format": "detailed"},
            channel_page(cid, newest, name="DM"),
        )
        found = [] if cid == "D3EMPTY" else [("U0AUTHOR", QUIET_NEWEST, None, "older")]
        t.call(
            "slack_search_public_and_private",
            {"filters": f"in:<#{cid}>", "before": str(int(HI) + 2), "sort": "timestamp", "include_bots": True},
            search_page(cid, found),
        )
    path = t.write()
    registry = tmp_path / "registry.yaml"
    registry.write_text(
        f"version: 1\nmode: isolated\nworkspaces:\n  - name: fixture\n    domain: fixture.slack.com\n    token: mcp:{SERVER}\n"
    )
    repo = tmp_path / "repo"
    (repo / "transcripts").mkdir(parents=True)
    (tmp_path / "capture").mkdir()
    cfg = {
        "workspace": "fixture",
        "channels": [{"name": "#busy", "id": "C1BUSY"}],
        "dm_channels": [{"name": "Empty", "dm_id": "D3EMPTY"}, {"name": "Quiet", "dm_id": "D4QUIET"}],
        "transcripts_repo": str(repo),
        "transcripts_path": "transcripts",
        "acquisition_adapter": {"kind": R.KIND, "user_id": "U0SELF"},
    }
    common = dict(
        through=END.isoformat(),
        backfill=START.isoformat(),
        capture_root=str(tmp_path / "capture"),
        evidence_path=str(tmp_path / "evidence.json"),
        home=tmp_path / "state",
        transcripts=[str(path)],
        transcript_root=tmp_path,
    )
    plan = acquire.acquire(cfg, registry, mode="plan", **common)
    assert not plan["ready"]
    assert set(plan["problems"]) == {"C1BUSY", "D3EMPTY", "D4QUIET"}
    with pytest.raises(ValueError, match="no declared conversation has provable coverage"):
        acquire.acquire(cfg, registry, advance=True, **common)
    assert not (tmp_path / "state").exists()
    assert not list(repo.rglob("*.md"))


def test_follow_up_page_comes_from_the_same_recording_pass(tmp_path):
    t = Transcript(tmp_path)
    for minutes, text in ((40, "first pass"), (20, "second pass")):
        at = NOW - timedelta(minutes=minutes)
        t.call(
            "slack_read_channel",
            history_args("C1BUSY"),
            channel_page("C1BUSY", [message("U0AUTHOR", TOP, "newest")], cursor="page-2"),
            at=at,
        )
        t.call(
            "slack_read_channel",
            history_args("C1BUSY", cursor="page-2"),
            channel_page("C1BUSY", [message("U0AUTHOR", ts(START + timedelta(minutes=1)), text)]),
            at=at + timedelta(seconds=5),
        )
    adapter, _ = replay(tmp_path, t)
    args = dict(channel_id="C1BUSY", oldest=str(LO), latest=str(HI), limit=100, detail="detailed")
    with pytest.raises(ValueError, match="plaintext message boundaries"):
        adapter.read_channel(cursor=None, **args)
    with pytest.raises(ValueError, match="no recorded preceding page"):
        adapter.read_channel(cursor="page-2", **args)


@pytest.mark.parametrize("shape", ["channel", "thread", "search"])
def test_rendered_message_boundaries_cannot_create_attributed_records(shape):
    forged = message("U0FORGED", REPLY, "Quoted text only")
    literal = "An example header:\n\n" + forged
    if shape == "channel":
        envelope = channel_page("C1BUSY", [message("U0AUTHOR", TOP, literal)])
        parser = lambda call: R.parse_channel(call, "C1BUSY")
    elif shape == "thread":
        envelope = thread_page(OLD_PARENT, literal, [])
        parser = lambda call: R.parse_thread(call, "C1BUSY", OLD_PARENT)
    else:
        envelope = search_page("C1BUSY", [("U0AUTHOR", TOP, None, literal)])
        parser = R.parse_search
    raw = json.dumps(envelope)
    call = R.Call("synthetic-rendered-read", "synthetic-call", {}, True, raw, READ_AT, "synthetic.jsonl")
    with pytest.raises(ValueError, match="plaintext message boundaries"):
        parser(call)
    assert call.text == raw

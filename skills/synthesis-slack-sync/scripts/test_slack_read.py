"""Direct Web API reader controls with a synthetic transport; no network."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from slack_read import SlackRead  # noqa: E402
from slack_workspaces import Entry  # noqa: E402

END = datetime(2026, 9, 26, 1, 30, tzinfo=timezone.utc)
START = END - timedelta(hours=3)


def ts(moment):
    return f"{int(moment.timestamp())}.000100"


class Transport:
    def __init__(self, pages):
        self.pages = list(pages)
        self.requests = []

    def call(self, route, params=None):
        self.requests.append((route, params))
        return self.pages.pop(0), f"call-{len(self.requests)}"


def reader(pages):
    read = SlackRead(
        Entry(name="fixture", domain="fixture.slack.com", token="env:SYNTHETIC"),
        {"kind": "slack-web-api-v1", "team_id": "T0FIX", "user_id": "U0SELF"},
        Transport(pages),
    )
    read.channels["C1"] = "in:busy"
    return read


def match(moment, channel="C1"):
    return {"ts": ts(moment), "channel": {"id": channel}}


def test_history_probe_reads_one_message_bounded_at_the_window_end():
    read = reader([{"ok": True, "messages": [{"ts": ts(START - timedelta(days=2))}]}])
    probe = read.probe_newest(channel_id="C1", latest=str(END.timestamp()))
    assert probe == {"ok": True, "newest_ts": ts(START - timedelta(days=2)), "tool_call_id": "call-1"}
    route, params = read.transport.requests[0]
    assert route == "conversations.history"
    assert params["limit"] == 1 and params["latest"] == str(END.timestamp())


def test_search_probe_walks_newest_first_past_later_messages():
    late = {"messages": {"matches": [match(END + timedelta(minutes=5))], "paging": {"pages": 2}}, "ok": True}
    older = {"messages": {"matches": [match(START - timedelta(days=1))], "paging": {"pages": 2}}, "ok": True}
    read = reader([late, older])
    probe = read.probe_search_newest(channel_id="C1", latest=str(END.timestamp()))
    assert probe["newest_ts"] == ts(START - timedelta(days=1))
    assert [p["sort_dir"] for _, p in read.transport.requests] == ["desc", "desc"]
    assert read.transport.requests[0][1]["query"] == "in:busy before:2026-09-28"


def test_search_probe_refuses_another_conversation():
    read = reader([{"messages": {"matches": [match(START, "C9")], "paging": {"pages": 1}}, "ok": True}])
    with pytest.raises(ValueError, match="foreign"):
        read.probe_search_newest(channel_id="C1", latest=str(END.timestamp()))


def test_window_search_clears_every_time_zone():
    page = {
        "ok": True,
        "messages": {"matches": [], "paging": {"page": 1, "pages": 1, "count": 100, "total": 0}},
    }
    read = reader([page])
    read.search_replies(
        channel_id="C1",
        oldest=str(START.timestamp()),
        latest=str(END.timestamp()),
        cursor=None,
        limit=100,
        detail="detailed",
    )
    # The window starts 2026-09-25 22:30 UTC: after:09-23 reaches back to 09-24
    # in the searcher's zone, which covers the start from UTC-12 to UTC+14.
    assert read.transport.requests[0][1]["query"] == "in:busy after:2026-09-23 before:2026-09-28"

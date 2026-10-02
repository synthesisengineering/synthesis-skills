import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest

p = Path(__file__).resolve().parents[1] / "thread_checker.py"
spec = importlib.util.spec_from_file_location("thread_checker", p)
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)
START = datetime(2026, 9, 26, 9, tzinfo=timezone.utc)
END = START + timedelta(hours=1)
P = f"{int(START.timestamp()) - 100}.000000"
R = f"{int(START.timestamp()) + 100}.000000"
T = f"{int(START.timestamp()) + 200}.000000"


def page(rows, **kw):
    return {"ok": True, "messages": rows, "tool_call_id": "synthetic-call", "response_metadata": {"next_cursor": ""}, **kw}


def adapters():
    calls = []

    def history(**kw):
        calls.append(("history", kw))
        return page([{"ts": T, "reply_count": 0}])

    def search(**kw):
        calls.append(("search", kw))
        return page([{"ts": R, "thread_ts": P}])

    def thread(**kw):
        calls.append(("thread", kw))
        return page([{"ts": P}, {"ts": R}])

    return calls, dict(
        read_channel=history,
        read_thread=thread,
        search_replies=search,
        clock=lambda: END,
    )


def test_detailed_discovery_follows_old_parent_and_omits_oldest():
    calls, args = adapters()
    result = M.acquire_channel("C123", START, END, **args)
    assert result["threads"][0]["parent_ts"] == P
    assert all(kw["detail"] == "detailed" for _, kw in calls)
    assert "oldest" not in next(kw for kind, kw in calls if kind == "thread")
    assert result["reply_search"]["positive_control_ids"] == [R]


def test_paged_channel_response_and_exact_cursor():
    calls, args = adapters()
    cursors = []

    def history(**kw):
        cursors.append(kw["cursor"])
        return page(
            [{"ts": T}],
            response_metadata={"next_cursor": "next" if kw["cursor"] is None else ""},
        )

    args["read_channel"] = history
    M.acquire_channel("C123", START, END, **args)
    assert cursors == [None, "next"]


@pytest.mark.parametrize(
    "kind",
    [
        "cycle",
        "has-more",
        "empty-search",
        "missing-reply",
        "error",
        "missing-provenance",
    ],
)
def test_collection_negative_controls(kind):
    _, args = adapters()
    if kind == "cycle":
        args["read_channel"] = lambda **kw: page(
            [], response_metadata={"next_cursor": "again"}
        )
    if kind == "has-more":
        args["read_channel"] = lambda **kw: page([], has_more=True)
    if kind == "empty-search":
        args["search_replies"] = lambda **kw: page([])
    if kind == "missing-reply":
        args["read_thread"] = lambda **kw: page([{"ts": P}])
    if kind == "error":
        args["read_channel"] = lambda **kw: {"ok": False}
    if kind == "missing-provenance":
        args["read_channel"] = lambda **kw: {"ok": True, "messages": []}
    with pytest.raises(ValueError):
        M.acquire_channel("C123", START, END, **args)


def test_unmapped_channel_does_not_inherit_previous_id(tmp_path):
    p = tmp_path / "transcript.md"
    p.write_text(
        "## #one (C123)\n#### Message (TS: 1790410000.000001)\n## #two\n#### Message (TS: 1790410001.000001)\n"
    )
    assert M.extract_threads(str(p))[1]["channel_id"] == "?"


OLD = f"{int(START.timestamp()) - 500}.000000"


def quiet(**overrides):
    calls, args = adapters()
    args["read_channel"] = lambda **kw: page([])
    args["search_replies"] = lambda **kw: page([])
    args["probe_newest"] = lambda **kw: calls.append(("probe", kw)) or {
        "ok": True,
        "newest_ts": OLD,
        "tool_call_id": "history-probe",
        "observed_at": END.isoformat(),
    }
    args["probe_search_newest"] = lambda **kw: calls.append(("search-probe", kw)) or {
        "ok": True,
        "newest_ts": OLD,
        "tool_call_id": "search-probe",
    }
    args.update(overrides)
    return calls, args


def test_quiet_channel_records_both_probes_bounded_at_window_end():
    calls, args = quiet()
    result = M.acquire_channel("C123", START, END, **args)
    assert set(result["quiet_control"]) == {"history", "search"}
    assert result["quiet_control"]["history"]["observed_at"] == END.isoformat()
    assert result["quiet_control"]["search"]["tool_call_id"] == "search-probe"
    latest = str(M.Decimal(str(END.timestamp())))
    assert [kw["latest"] for kind, kw in calls if "probe" in kind] == [latest, latest]


@pytest.mark.parametrize(
    "kind", ["no-search-probe", "in-window-probe", "empty-probe", "history-in-window", "failed"]
)
def test_quiet_channel_negative_controls(kind):
    overrides = {}
    if kind == "no-search-probe":
        overrides["probe_search_newest"] = None
    if kind == "in-window-probe":
        overrides["probe_newest"] = lambda **kw: {
            "ok": True, "newest_ts": T, "tool_call_id": "history-probe"
        }
    if kind == "empty-probe":
        overrides["probe_search_newest"] = lambda **kw: {
            "ok": True, "newest_ts": None, "tool_call_id": "search-probe"
        }
    if kind == "history-in-window":
        overrides["read_channel"] = lambda **kw: page([{"ts": T}])
    if kind == "failed":
        overrides["probe_newest"] = lambda **kw: {"ok": False, "tool_call_id": "x"}
    _, args = quiet(**overrides)
    with pytest.raises(ValueError):
        M.acquire_channel("C123", START, END, **args)


def test_replayed_observation_time_requires_an_offset():
    _, args = adapters()
    args["read_channel"] = lambda **kw: page([{"ts": T}], observed_at="2026-09-26T10:00:00")
    with pytest.raises(ValueError, match="offset"):
        M.acquire_channel("C123", START, END, **args)

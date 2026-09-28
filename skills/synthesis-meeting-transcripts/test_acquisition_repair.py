"""Actual acquisition owners: paging, owned replay and MCP admission repairs."""

import importlib.util
import json
import sys
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "repair_entry_fixtures", Path(__file__).with_name("test_acquisition_entry.py")
)
F = importlib.util.module_from_spec(spec)
spec.loader.exec_module(F)
owners = F.owners
wire = F.wire


def page(hits, page, *, total=2, per_page=1, both=True):
    pages = max(1, (total + per_page - 1) // per_page)
    p = {"page": page, "pages": pages, "count": per_page, "total": total}
    q = {
        "page": page,
        "page_count": pages,
        "per_page": per_page,
        "total_count": total,
        "first": (page - 1) * per_page + 1 if total else 0,
        "last": min(page * per_page, total),
    }
    value = {"matches": hits, "paging": p, "total": total}
    if both:
        value["pagination"] = q
    return value


@pytest.mark.parametrize(
    "fault",
    [
        None,
        "dual",
        "total",
        "count",
        "first",
        "short",
        "duplicate",
        "changed-total",
        "changed-count",
        "missing-total",
        "bool",
        "empty-object",
    ],
)
def test_actual_paging_consistency_before_watermark(owners, wire, tmp_path, fault):
    _, slack = owners
    holder, calls = wire
    cfg = F.slack_cfg(tmp_path)
    start, end = F.dates()
    base, parent, reply, body = F.slack_handler(start, end)

    def endpoint(request):
        status, result = base(request)
        if request.url.path.endswith("search.messages"):
            n = int(request.url.params["page"])
            hits = (
                [
                    {
                        "channel": {"id": "C123"},
                        "ts": parent,
                        "text": "old parent",
                        "user": "U456",
                    }
                ]
                if n == 1
                else [{**body, "channel": {"id": "C123"}}]
            )
            result["messages"] = page(hits, n)
            m = result["messages"]
            if fault == "dual":
                m["pagination"]["page_count"] = 3
            elif fault == "total":
                m["total"] = 201
            elif fault == "count":
                m["paging"]["count"] = 100
            elif fault == "first":
                m["pagination"]["first"] = 99
            elif fault == "short":
                m["matches"] = []
            elif fault == "duplicate" and n == 2:
                m["matches"] = [
                    {
                        "channel": {"id": "C123"},
                        "ts": parent,
                        "text": "old parent",
                        "user": "U456",
                    }
                ]
            elif fault == "changed-total" and n == 2:
                m = page(hits, n, total=3)
                result["messages"] = m
            elif fault == "changed-count" and n == 2:
                m = page(hits, n, total=4, per_page=2)
                result["messages"] = m
            elif fault == "missing-total":
                m.pop("total")
                m["paging"].pop("total")
                m["pagination"].pop("total_count")
            elif fault == "bool":
                m["paging"]["count"] = True
            elif fault == "empty-object":
                m["paging"] = {}
        return status, result

    holder["handler"] = endpoint
    if fault is None:
        assert (
            F.run_slack(slack, cfg, tmp_path, start, end)["watermark"]["moved"] is True
        )
        assert len([r for r in calls if r[1].endswith("search.messages")]) == 2
    else:
        with pytest.raises(ValueError):
            F.run_slack(slack, cfg, tmp_path, start, end)
        assert not (tmp_path / "state").exists()


@pytest.mark.parametrize("grammar", ["paging", "pagination", "both"])
def test_documented_search_shapes_are_explicit(owners, wire, tmp_path, grammar):
    _, slack = owners
    holder, calls = wire
    cfg = F.slack_cfg(tmp_path)
    start, end = F.dates()
    base, parent, reply, body = F.slack_handler(start, end)

    def endpoint(request):
        status, result = base(request)
        if request.url.path.endswith("search.messages"):
            m = page([{**body, "channel": {"id": "C123"}}], 1, total=1, per_page=100)
            if grammar == "paging":
                m.pop("pagination")
            elif grammar == "pagination":
                m.pop("paging")
            result["messages"] = m
        return status, result

    holder["handler"] = endpoint
    assert F.run_slack(slack, cfg, tmp_path, start, end)["watermark"]["moved"] is True


def channel(cid, ts, text="ordinary", **extra):
    return {
        "id": cid,
        "history": {"messages": [dict(ts=ts, text=text, user="U123", **extra)]},
        "reply_search": {"messages": []},
        "threads": [],
    }


def test_owned_replay_uses_conversation_and_parent_metadata(owners, tmp_path):
    _, slack = owners
    root = tmp_path / "archive"
    p = root / "owned.md"
    ts = "1800000000.000001"
    reply = "1800000000.000002"
    text = "Quoted raw content:\n## #other (C999)\n#### Fake (TS: 1800000000.000099)\n<!-- synthesis-slack-raw-v1:eyJmb28iOjF9 -->"
    slack.save_channel(p, channel("D123", ts, text))
    slack.save_channel(p, channel("D456", ts))
    slack.save_channel(p, channel("D456", reply, "child", thread_ts=ts))
    assert slack.known_threads(
        {"known_archives": ["owned.md"]}, root, ["D123", "D456"]
    ) == {"D123": {ts}, "D456": {ts}}
    assert text in p.read_text()


@pytest.mark.parametrize(
    "fault",
    [
        "foreign",
        "changed-render",
        "invalid-parent",
        "conflicting-parent",
        "trailing-text",
    ],
)
def test_owned_replay_refuses_corrupt_scope_and_content(owners, tmp_path, fault):
    _, slack = owners
    root = tmp_path / "archive"
    p = root / "owned.md"
    ts = "1800000000.000001"
    slack.save_channel(p, channel("C123", ts))
    if fault == "foreign":
        targets = ["C456"]
    else:
        targets = ["C123"]
        if fault == "changed-render":
            p.write_text(p.read_text().replace("ordinary", "changed", 1))
        elif fault == "trailing-text":
            p.write_text(p.read_text() + "extra\n")
        else:
            data = slack.parse_archive(p.read_bytes())
            rows = data["channels"]["C123"][ts]
            rows[0]["thread_ts"] = (
                "not-a-timestamp" if fault == "invalid-parent" else "1800000000.000002"
            )
            if fault == "conflicting-parent":
                rows.append(dict(rows[0], thread_ts="1800000000.000003"))
            # This is intentionally an invalid source codec; rendering or replay must refuse.
            try:
                p.write_text(slack.render_payload(data))
            except ValueError:
                return
    with pytest.raises(ValueError):
        slack.known_threads({"known_archives": ["owned.md"]}, root, targets)


def test_legacy_replay_explicit_headers_ignore_quotes_and_fences(owners, tmp_path):
    _, slack = owners
    root = tmp_path / "archive"
    root.mkdir()
    p = root / "old.md"
    ts = "1800000000.000001"
    p.write_text(
        "## #first (D123)\n#### Parent (TS: "
        + ts
        + ")\n```text\n## #foreign (C999)\n#### Quoted (TS: 1800000000.000099)\n```\n> ## #foreign (C888)\n> #### Quoted (TS: 1800000000.000088)\n## #second (D456)\n#### Parent (TS: "
        + ts
        + ")\n"
    )
    assert slack.known_threads(
        {"known_archives": ["old.md"]}, root, ["D123", "D456"]
    ) == {"D123": {ts}, "D456": {ts}}


@pytest.mark.parametrize(
    "case", ["empty", "ambiguous-name", "unknown-channel", "unclosed-fence", "body-ts"]
)
def test_legacy_replay_ambiguity_is_not_empty_coverage(owners, tmp_path, case):
    _, slack = owners
    root = tmp_path / "archive"
    root.mkdir()
    p = root / "old.md"
    ts = "1800000000.000001"
    content = {
        "empty": "",
        "ambiguous-name": "## #same (C123)\n## #same (C456)\n### #same\n#### Parent (TS: "
        + ts
        + ")\n",
        "unknown-channel": "### #unknown\n#### Parent (TS: " + ts + ")\n",
        "unclosed-fence": "## #first (C123)\n```text\n#### Parent (TS: " + ts + ")\n",
        "body-ts": "## #first (C123)\nRaw body (TS: " + ts + ")\n",
    }[case]
    p.write_text(content)
    with pytest.raises(ValueError):
        slack.known_threads({"known_archives": ["old.md"]}, root, ["C123", "C456"])


@pytest.mark.parametrize("consumer", ["fetch", "shared"])
@pytest.mark.parametrize(
    "fault",
    [
        None,
        "missing-tools",
        "wrong-version",
        "bool-id",
        "missing-rpc",
        "both-result-error",
        "missing-server",
        "bad-tools",
        "duplicate",
        "wrong-id",
        "error",
        "invalid-session",
        "failed-notify",
    ],
)
def test_mcp_initialization_admits_only_matching_supported_tools(
    owners, monkeypatch, consumer, fault
):
    fetch, _ = owners
    M = sys.modules["mcp_client"]
    original = httpx.Client
    calls = []

    def endpoint(request):
        data = json.loads(request.content)
        calls.append(data["method"])
        if data["method"] == "initialize":
            row = {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "fixture", "version": "1"},
                },
            }
            if fault == "missing-tools":
                row["result"]["capabilities"] = {}
            elif fault == "wrong-version":
                row["result"]["protocolVersion"] = "unsupported"
            elif fault == "bool-id":
                row["id"] = True
            elif fault == "missing-rpc":
                row.pop("jsonrpc")
            elif fault == "both-result-error":
                row["error"] = {"code": 1, "message": "refusal"}
            elif fault == "missing-server":
                row["result"].pop("serverInfo")
            elif fault == "bad-tools":
                row["result"]["capabilities"]["tools"] = {"listChanged": "yes"}
            elif fault == "wrong-id":
                row["id"] = 99
            elif fault == "error":
                row = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "error": {"code": 1, "message": "refusal"},
                }
            raw = json.dumps(row)
            if fault == "duplicate":
                raw = "data: " + raw + "\n\ndata: " + raw + "\n\n"
            else:
                raw = (
                    "data: "
                    + json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "method": "notifications/message",
                            "params": {},
                        }
                    )
                    + "\n\ndata: "
                    + raw
                    + "\n\n"
                )
            return httpx.Response(
                200,
                content=raw,
                headers={
                    "mcp-session-id": "bad\tvalue"
                    if fault == "invalid-session"
                    else "fixture-session"
                },
                request=request,
            )
        assert request.headers["mcp-session-id"] == "fixture-session"
        assert request.headers.get("mcp-protocol-version") == "2025-03-26"
        if data["method"] == "notifications/initialized":
            return httpx.Response(
                500 if fault == "failed-notify" else 202, content=b"", request=request
            )
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "result": {"content": [{"type": "text", "text": "exact"}]},
            },
            request=request,
        )

    monkeypatch.setattr(
        httpx,
        "Client",
        lambda *a, **kw: original(*a, transport=httpx.MockTransport(endpoint), **kw),
    )

    def invoke():
        if consumer == "fetch":
            return fetch.mcp_call("https://fixture.invalid/mcp", "read", {})
        with httpx.Client() as client:
            return M._init_session(client)

    if fault is None:
        assert invoke() == ("exact" if consumer == "fetch" else "fixture-session")
        assert calls[:2] == ["initialize", "notifications/initialized"]
    else:
        with pytest.raises((ValueError, RuntimeError, httpx.HTTPError)):
            invoke()
        assert calls == (
            ["initialize", "notifications/initialized"]
            if fault == "failed-notify"
            else ["initialize"]
        )

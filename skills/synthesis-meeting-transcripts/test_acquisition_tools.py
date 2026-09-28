"""Synthetic independent controls for the four transcript acquisition seams."""

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


MCP = load("mcp_client", ROOT / "optional-workspace-mcp/mcp_client.py")
TAB = load("document_tabs", ROOT / "optional-workspace-mcp/document_tabs.py")
FETCH = load("fetch_meeting", ROOT / "optional-workspace-mcp/fetch-meeting.py")
V = load("verify_transcripts", ROOT / "verify_transcripts.py")
C = load("extract_commitments", ROOT / "extract_commitments.py")


def tab(id, body, title="Same title"):
    return {
        "tabProperties": {"tabId": id, "title": title},
        "documentTab": {
            "body": {
                "content": [
                    {"paragraph": {"elements": [{"textRun": {"content": body}}]}}
                ]
            }
        },
    }


def doc():
    return {
        "tabsComplete": True,
        "tabs": [
            tab("notes", "summary"),
            tab("actual", "00:00\nAlice Chen: I will help.\n"),
        ],
    }


def transcript():
    return "".join(
        f"00:{i:02}:00\nAlice Chen: I will review item {i}.\nBob Smith: Agreed.\n"
        for i in range(10)
    )


def test_nested_envelopes_plain_text_and_document_json():
    raw = json.dumps(doc())
    assert (
        MCP.call_tool_text({"result": {"content": [{"type": "text", "text": raw}]}})
        == raw
    )
    assert (
        MCP.call_tool_text(
            {
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                {
                                    "result": {
                                        "content": [
                                            {"type": "text", "text": "verbatim"}
                                        ]
                                    }
                                }
                            ),
                        }
                    ]
                }
            }
        )
        == "verbatim"
    )


@pytest.mark.parametrize(
    "bad",
    [
        {"isError": True, "content": []},
        {"result": {"error": {"code": 401}}},
        {"result": {"content": [{"type": "image", "data": "x"}]}},
    ],
)
def test_errors_are_not_source_absence(bad):
    with pytest.raises(ValueError):
        MCP.call_tool_text(bad)


def test_nested_error_and_depth_refuse():
    with pytest.raises(ValueError):
        MCP.call_tool_text(
            {"content": [{"type": "text", "text": '{"isError":true,"content":[]}'}]}
        )
    d = {"content": [{"type": "text", "text": "a"}]}
    for _ in range(14):
        d = {"result": d}
    with pytest.raises(ValueError):
        MCP.call_tool_text(d)


def test_sse_notification_does_not_hide_result():
    s = 'data: {"method":"progress"}\n\ndata: {"id":2,"result":{"content":[]}}\n\n'
    assert MCP._parse_sse(s)["id"] == 2
    with pytest.raises(ValueError):
        MCP._parse_sse(s + s)


def test_tab_identity_not_title_or_order():
    d = doc()
    d["tabs"].reverse()
    assert TAB.select_tabs(json.dumps(d), transcript_tab_id="actual")[
        "transcript"
    ].startswith("00:00")


@pytest.mark.parametrize(
    "change,reason,status",
    [
        ("missing", "transcript-tab-absent", "no-source"),
        ("empty", "transcript-tab-empty", "no-source"),
        ("incomplete", "tab-inventory-incomplete", "unknown"),
        ("notreturned", "tab-content-unavailable", "unknown"),
    ],
)
def test_distinct_no_source_reasons(change, reason, status):
    d = doc()
    if change in {"missing", "incomplete"}:
        d["tabs"].pop()
    if change == "incomplete":
        d["tabsComplete"] = False
    if change == "empty":
        d["tabs"][1] = tab("actual", "")
    if change == "notreturned":
        d["tabs"][1].pop("documentTab")
    r = TAB.select_tabs(json.dumps(d), transcript_tab_id="actual")
    assert (r["reason"], r["status"]) == (reason, status)


def test_unstructured_response_never_no_source():
    assert TAB.select_tabs("summary only", transcript_tab_id="x")["status"] == "unknown"
    d = doc()
    d["tabs"].append(tab("actual", "duplicate"))
    with pytest.raises(ValueError):
        TAB.select_tabs(json.dumps(d), transcript_tab_id="actual")


def test_nested_tabs():
    d = doc()
    child = d["tabs"].pop()
    d["tabs"][0]["childTabs"] = [child]
    assert (
        TAB.select_tabs(json.dumps(d), transcript_tab_id="actual")["status"]
        == "transcript"
    )


def test_commitment_block_timestamps_and_section_reset():
    text = "00:01:12\nAlice Chen: Hello.\nBob Smith: I will help.\n00:03:00\nAlice Chen: Let me help.\n## Notes\nBob Smith: I will help.\n"
    assert [c["timestamp"] for c in C.scan(text)["candidates"]] == [
        "00:01:12",
        "00:03:00",
        None,
    ]


def test_exact_file_set_ignores_good_neighbor_and_missing_fails(tmp_path):
    good = tmp_path / "good.md"
    good.write_text(transcript())
    bad = tmp_path / "bad.md"
    bad.write_text("summary")
    assert V.audit_files([bad])[0]["status"] == "INCOMPLETE"
    with pytest.raises(OSError):
        V.audit_files([tmp_path / "missing.md"])
    with pytest.raises(ValueError):
        V.audit_files([good, good])


def test_exact_file_digest_and_prefix_are_enforced(tmp_path):
    p = tmp_path / "_saved.md"
    p.write_text("summary")
    assert V.audit_files([p])[0]["status"] == "INCOMPLETE"
    with pytest.raises(ValueError):
        V.audit_files([p], expected_hashes={str(p): "0" * 64})


def test_new_save_verified_and_previous_bytes_retained(tmp_path):
    p = tmp_path / "meeting.md"
    first = transcript()
    r = FETCH.save_verified(p, first)
    assert r["saved"] and r["sha256"] == hashlib.sha256(p.read_bytes()).hexdigest()
    assert not FETCH.save_verified(p, first)["saved"]
    with pytest.raises(ValueError):
        FETCH.save_verified(p, first + "\nchanged")
    FETCH.save_verified(p, first + "\nchanged", force=True)
    assert any(x.read_text() == first for x in tmp_path.glob("*.old-*.md"))


def test_incomplete_save_refuses_and_retains_staging(tmp_path):
    p = tmp_path / "bad.md"
    with pytest.raises(ValueError, match="completeness"):
        FETCH.save_verified(p, "summary")
    assert not p.exists()
    assert len(list(tmp_path.glob(".bad.md.*.md"))) == 1


def test_readiness_requires_real_identity_shape_and_declared_read_only_probe():
    cfg = {
        "recorder_probe": {
            "semantics": "authentication-read-only",
            "tool": "fixture_identity",
            "arguments": {},
        }
    }
    calls = []

    def call(*args):
        calls.append(args)
        return '{"authenticated":true,"account":"synthetic@example.invalid","tool_call_id":"observed-identity-call"}'

    assert (
        FETCH.recorder_readiness(
            cfg, "fixture", "synthetic@example.invalid", call=call
        )["status"]
        == "authenticated"
    )
    assert calls == [("fixture", "fixture_identity", {})]
    with pytest.raises(ValueError):
        FETCH.recorder_readiness({}, "fixture", "x", call=call)
    with pytest.raises(ValueError):
        FETCH.recorder_readiness(cfg, "fixture", "other", call=call)
    with pytest.raises(ValueError):
        FETCH.recorder_readiness(
            cfg, "fixture", "x", call=lambda *a: '{"authenticated":false}'
        )


def test_source_inventory_follows_all_pages_without_relevance_filter():
    from datetime import datetime, timedelta, timezone

    start = datetime(2026, 9, 26, 9, tzinfo=timezone.utc)
    end = start + timedelta(hours=1)
    calls = []

    def listing(**kwargs):
        calls.append(kwargs)
        key = "doc-1" if kwargs["cursor"] is None else "doc-2"
        return {
            "ok": True,
            "tool_call_id": "fixture-list",
            "documents": [{"source_id": key, "occurred_at": start.isoformat()}],
            "next_cursor": "next" if kwargs["cursor"] is None else None,
            "complete": kwargs["cursor"] is not None,
        }

    result = FETCH.inventory_documents(
        listing,
        source="fixture",
        account="synthetic@example.invalid",
        start=start,
        through=end,
        positive_control={
            "observed": True,
            "source": "fixture",
            "account": "synthetic@example.invalid",
            "observed_at": end.isoformat(),
            "source_id": "doc-1",
            "tool_call_id": "fixture-control",
        },
    )
    assert [d["source_id"] for d in result["documents"]] == ["doc-1", "doc-2"]
    assert len(calls) == 2


@pytest.mark.parametrize("kind", ["bounded", "cycle", "error", "duplicate"])
def test_source_inventory_negative_controls(kind):
    from datetime import datetime, timedelta, timezone

    start = datetime(2026, 9, 26, 9, tzinfo=timezone.utc)
    end = start + timedelta(hours=1)

    def listing(**kwargs):
        rows = [{"source_id": "doc-1", "occurred_at": start.isoformat()}]
        if kind == "duplicate":
            rows *= 2
        return {
            "ok": kind != "error",
            "tool_call_id": "fixture-list",
            "documents": rows,
            "next_cursor": "again" if kind == "cycle" else None,
            "complete": kind != "bounded",
        }

    with pytest.raises(ValueError):
        FETCH.inventory_documents(
            listing,
            source="fixture",
            account="synthetic@example.invalid",
            start=start,
            through=end,
            positive_control={
                "observed": True,
                "source": "fixture",
                "account": "synthetic@example.invalid",
                "observed_at": end.isoformat(),
                "source_id": "doc-1",
                "tool_call_id": "fixture-control",
            },
        )


def test_archive_parent_alias_and_hardlinked_target_refuse(tmp_path):
    import os

    real = tmp_path / "real"
    real.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(real, target_is_directory=True)
    with pytest.raises((ValueError, OSError)):
        FETCH.save_verified(alias / "meeting.md", transcript())
    assert list(real.iterdir()) == []
    target = real / "meeting.md"
    target.write_text(transcript())
    os.link(target, real / "second.md")
    with pytest.raises(ValueError):
        FETCH.save_verified(target, transcript() + "changed", force=True)
    assert target.read_text() == transcript()


def test_archive_ancestor_replacement_cannot_redirect_publication(
    tmp_path, monkeypatch
):
    parent = tmp_path / "archive"
    parent.mkdir()
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    import archive_publish

    original = archive_publish._archive_directory
    count = [0]

    def replacement(path, **kw):
        result = original(path, **kw)
        count[0] += 1
        if count[0] == 1:
            parent.rename(tmp_path / "retained")
            parent.symlink_to(foreign, target_is_directory=True)
        return result

    monkeypatch.setattr(archive_publish, "_archive_directory", replacement)
    with pytest.raises((ValueError, OSError)):
        FETCH.save_verified(parent / "meeting.md", transcript())
    assert list(foreign.iterdir()) == []


def test_empty_tab_requires_complete_inventory_and_retains_notes():
    d = doc()
    d["tabs"][1] = tab("actual", "")
    r = TAB.select_tabs(json.dumps(d), transcript_tab_id="actual")
    assert r["status"] == "no-source" and r["notes"] == "summary"
    d["tabsComplete"] = False
    assert (
        TAB.select_tabs(json.dumps(d), transcript_tab_id="actual")["status"]
        == "unknown"
    )

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
import pytest

P = Path(__file__).resolve().parents[2]
T = P / "skills/synthesis-meeting-transcripts"
sys.path.insert(0, str(T / "optional-workspace-mcp"))
sys.path.insert(0, str(P / "skills/synthesis-daily-rituals/scripts"))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


TAB = load("review_tabs", T / "optional-workspace-mcp/document_tabs.py")
MCP = load("review_mcp", T / "optional-workspace-mcp/mcp_client.py")
FETCH = load("review_fetch", T / "optional-workspace-mcp/fetch-meeting.py")
V = load("review_verify", T / "verify_transcripts.py")
TH = load("review_thread", P / "skills/synthesis-slack-sync/thread_checker.py")
A = load(
    "review_acq", P / "skills/synthesis-daily-rituals/scripts/acquisition_evidence.py"
)
START = datetime(2026, 9, 26, 9, tzinfo=timezone.utc)
END = START + timedelta(hours=1)


def doc(body):
    return json.dumps(
        {
            "tabsComplete": True,
            "tabs": [
                {"tabProperties": {"tabId": "actual"}, "documentTab": {"body": body}}
            ],
        }
    )


@pytest.mark.parametrize(
    "body",
    [
        None,
        17,
        {},
        {"garbage": "not empty source"},
        {"content": [{"unsupportedProviderNode": {"text": "lost actual text"}}]},
    ],
)
def test_unknown_tab_structure_never_no_source(body):
    result = TAB.select_tabs(doc(body), transcript_tab_id="actual")
    assert result["status"] == "unknown"


def test_genuine_empty_tab_positive_control():
    assert (
        TAB.select_tabs(doc({"content": []}), transcript_tab_id="actual")["reason"]
        == "transcript-tab-empty"
    )


def test_mcp_boolean_id_not_numeric_request():
    with pytest.raises(ValueError):
        MCP._parse_sse('{"id":true,"result":{}}', expected_id=1)


def test_duplicate_json_keys_refuse():
    with pytest.raises(ValueError):
        MCP._parse_sse('{"id":1,"id":2,"result":{}}', expected_id=2)


def test_malformed_error_flag_refuses():
    with pytest.raises(ValueError):
        MCP.call_tool_text(
            {"isError": "true", "content": [{"type": "text", "text": "wrong"}]}
        )


def test_source_inventory_zero_cursor_not_complete():
    def page(**kw):
        return {
            "ok": True,
            "documents": [],
            "tool_call_id": "call",
            "next_cursor": 0,
            "complete": True,
        }

    with pytest.raises(ValueError):
        FETCH.inventory_documents(
            page,
            source="fixture",
            account="fixture@example.invalid",
            start=START,
            through=END,
            positive_control={
                "observed": True,
                "source_id": "positive",
                "tool_call_id": "call",
                "source": "fixture",
                "account": "fixture@example.invalid",
                "observed_at": END.isoformat(),
            },
        )


def test_slack_missing_pagination_not_complete():
    ts = str(int(START.timestamp()) + 1) + ".000000"

    def page(**kw):
        return {"ok": True, "messages": [{"ts": ts}], "tool_call_id": "fixture"}

    with pytest.raises(ValueError):
        TH.acquire_channel(
            "C123", START, END, read_channel=page, read_thread=page, search_replies=page
        )


def test_slack_false_complete_not_rewritten_true():
    ts = str(int(START.timestamp()) + 1) + ".000000"

    def page(**kw):
        return {
            "ok": True,
            "messages": [{"ts": ts}],
            "tool_call_id": "fixture",
            "complete": False,
            "response_metadata": {"next_cursor": ""},
        }

    with pytest.raises(ValueError):
        TH.acquire_channel(
            "C123", START, END, read_channel=page, read_thread=page, search_replies=page
        )


def test_slack_foreign_channel_not_positive_control():
    ts = str(int(START.timestamp()) + 1) + ".000000"

    def page(**kw):
        return {
            "ok": True,
            "messages": [{"ts": ts, "channel": "CFOREIGN"}],
            "tool_call_id": "fixture",
            "response_metadata": {"next_cursor": ""},
        }

    with pytest.raises(ValueError):
        TH.acquire_channel(
            "C123", START, END, read_channel=page, read_thread=page, search_replies=page
        )


def test_readiness_carries_real_adapter_tool_call():
    cfg = {
        "recorder_probe": {
            "semantics": "authentication-read-only",
            "tool": "identity",
            "arguments": {},
        }
    }
    row = FETCH.recorder_readiness(
        cfg,
        "fixture",
        "fixture@example.invalid",
        call=lambda *a: json.dumps(
            {
                "authenticated": True,
                "account": "fixture@example.invalid",
                "tool_call_id": "observed-identity-call",
            }
        ),
    )
    assert row["tool_call_id"] == "observed-identity-call"


def test_readiness_missing_provenance_refuses():
    cfg = {
        "recorder_probe": {
            "semantics": "authentication-read-only",
            "tool": "identity",
            "arguments": {},
        }
    }
    with pytest.raises(ValueError):
        FETCH.recorder_readiness(
            cfg,
            "fixture",
            "fixture@example.invalid",
            call=lambda *a: json.dumps(
                {"authenticated": True, "account": "fixture@example.invalid"}
            ),
        )


def test_saved_manifest_alias_refuses(tmp_path):
    target = tmp_path / "document.md"
    target.write_text("**No source transcript available**\n")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            [
                {
                    "path": str(target),
                    "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                }
            ]
        )
    )
    alias = tmp_path / "alias.json"
    alias.symlink_to(manifest)
    assert V.main(["--saved-manifest", str(alias), "--json"]) == 2


def test_meeting_foreign_or_stale_control_refuses(tmp_path):
    cases = load(
        "review_author_acq_fixtures",
        P / "skills/synthesis-daily-rituals/scripts/test_acquisition_evidence.py",
    )
    e = cases.meeting(tmp_path)
    control = e["sources"][0]["inventory"]["positive_control"]
    control.update(
        source="foreign",
        account="foreign@example.invalid",
        observed_at=cases.NOW.isoformat(),
    )
    with pytest.raises(ValueError):
        cases.validate(e)


def test_meeting_boolean_schema_refuses(tmp_path):
    cases = load(
        "review_author_acq_fixtures_schema",
        P / "skills/synthesis-daily-rituals/scripts/test_acquisition_evidence.py",
    )
    e = cases.meeting(tmp_path)
    e["schema"] = True
    with pytest.raises(ValueError):
        cases.validate(e)


def test_slack_legacy_partial_search_refuses():
    ts = str(int(START.timestamp()) + 1) + ".000000"

    def history(**kw):
        return {
            "ok": True,
            "messages": [{"ts": ts}],
            "tool_call_id": "fixture",
            "response_metadata": {"next_cursor": ""},
        }

    def search(**kw):
        return {
            "ok": True,
            "messages": {
                "matches": [{"ts": ts}],
                "paging": {"page": 1, "pages": 2, "total": 2},
            },
            "tool_call_id": "fixture",
            "response_metadata": {"next_cursor": ""},
        }

    with pytest.raises(ValueError):
        TH.acquire_channel(
            "C123",
            START,
            END,
            read_channel=history,
            read_thread=history,
            search_replies=search,
        )


def test_http_body_limit_before_materialization():
    import httpx

    class Large(httpx.SyncByteStream):
        def __iter__(self):
            for _ in range(130):
                yield b"x" * 65536

    def handler(request):
        return httpx.Response(200, stream=Large(), request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError):
            MCP.bounded_post(client, "https://fixture.invalid/mcp", headers={}, json={})


def test_http_error_stays_error_not_empty_content():
    import httpx

    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                401, content=b"not authenticated", request=request
            )
        )
    ) as client:
        with pytest.raises(httpx.HTTPStatusError):
            MCP.bounded_post(client, "https://fixture.invalid/mcp", headers={}, json={})

"""The optional workspace-mcp fetch (E20 to E22) and its MCP client. Synthetic documents and a
local stand-in server only; nothing reaches Google."""

from __future__ import annotations

import importlib.util
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import sys
import threading

import pytest

FOLDER = Path(__file__).resolve().parents[1] / "optional-workspace-mcp"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MCP = load("mcp_client", FOLDER / "mcp_client.py")
FM = load("workspace_mcp_fetch_meeting", FOLDER / "fetch-meeting.py")
DIALOGUE = "".join(f"00:{m:02d}:00\n**Ana Ruiz:** point {m}.\n**Ben Ode:** reply {m}.\n" for m in range(12))


def structure(file_id, tabs, **extra):
    return f"Document structure analysis for {file_id}:\n\n" + json.dumps({"tabs": tabs, **extra}) + "\n\nLink: https://docs.example.invalid"


class FakeDrive:
    """Answers the three workspace-mcp tools the fetch uses."""

    def __init__(self, tabs, texts, *, errors=(), listing=""):
        self.tabs, self.texts, self.errors, self.listing, self.calls = tabs, texts, set(errors), listing, []

    def __call__(self, tool, arguments, url=None, client_name=None):
        self.calls.append((tool, arguments))
        if tool in self.errors:
            raise ValueError("MCP tool returned an error; source coverage unknown")
        if tool == "search_drive_files":
            return self.listing
        if tool == "inspect_doc_structure":
            return self.tabs if isinstance(self.tabs, str) else structure(arguments["document_id"], self.tabs)
        if tool == "get_doc_as_markdown":
            return self.texts[arguments["tab_id"]]
        raise AssertionError(tool)


TABS = [{"tab_id": "t.notes", "title": "Notes"}, {"tab_id": "t.k2", "title": "Transcript"}]
TEXTS = {"t.notes": "Summary of the meeting.", "t.k2": DIALOGUE}


def fetch(monkeypatch, drive, tab_id=None, title=None):
    monkeypatch.setattr(FM.mcp_client, "call_tool", drive)
    return FM.fetch_document("http://localhost:1/mcp", "reader@example.invalid", "doc1", tab_id, title)


# --- E20: the transcript is chosen by stable tab ID; every failure has its own reason ----------


def test_e20_transcript_is_chosen_by_tab_id_not_title_or_order(monkeypatch):
    tabs = [{"tab_id": "t.k2", "title": "Notes"}, {"tab_id": "t.notes", "title": "Transcript"}]
    result = fetch(monkeypatch, FakeDrive(tabs, {"t.k2": DIALOGUE, "t.notes": "Summary."}), tab_id="t.k2")
    assert result["status"] == "transcript" and result["transcript_tab_id"] == "t.k2"
    assert result["transcript"] == DIALOGUE and "Summary." in result["notes"]


def test_e20_a_title_selects_only_when_one_tab_in_a_complete_list_carries_it(monkeypatch):
    assert fetch(monkeypatch, FakeDrive(TABS, TEXTS))["transcript_tab_id"] == "t.k2"  # default title
    twins = TABS + [{"tab_id": "t.k3", "title": "Transcript"}]
    result = fetch(monkeypatch, FakeDrive(twins, {**TEXTS, "t.k3": DIALOGUE}))
    assert (result["status"], result["reason"]) == ("unknown", "transcript-tab-title-not-unique")


@pytest.mark.parametrize("case,status,reason", [
    ("missing", "no-source", "transcript-tab-absent"),
    ("empty", "no-source", "transcript-tab-empty"),
    ("incomplete", "unknown", "tab-inventory-incomplete"),
    ("unparseable", "unknown", "tab-inventory-unavailable"),
    ("duplicate-id", "unknown", "tab-inventory-unavailable"),
])
def test_e20_empty_missing_incomplete_and_unreadable_tab_lists_have_their_own_reasons(monkeypatch, case, status, reason):
    tabs, texts = list(TABS), dict(TEXTS)
    if case == "missing":
        tabs = TABS[:1]
    if case == "empty":
        texts["t.k2"] = "   \n"
    if case == "incomplete":
        tabs = structure("doc1", TABS, truncated=True)
    if case == "unparseable":
        tabs = "Summary text only, no structure"
    if case == "duplicate-id":
        tabs = TABS + [{"tab_id": "t.k2", "title": "Copy"}]
    result = fetch(monkeypatch, FakeDrive(tabs, texts), tab_id="t.k2" if case == "missing" else None)
    assert (result["status"], result["reason"]) == (status, reason)


def test_e20_nested_tabs_are_found(monkeypatch):
    tabs = [{"tab_id": "t.notes", "title": "Notes", "child_tabs": [{"tab_id": "t.k2", "title": "Transcript"}]}]
    assert fetch(monkeypatch, FakeDrive(tabs, TEXTS), tab_id="t.k2")["status"] == "transcript"


# --- E21: an error is "unknown", never "no transcript" ---------------------------------------


@pytest.mark.parametrize("tool", ["inspect_doc_structure", "get_doc_as_markdown"])
def test_e21_a_tool_error_is_unknown_never_no_transcript(monkeypatch, tool):
    result = fetch(monkeypatch, FakeDrive(TABS, TEXTS, errors=[tool]))
    assert result["status"] == "unknown" and result["reason"] == "tool-error"


@pytest.mark.parametrize("bad", [
    {"isError": True, "content": []},
    {"result": {"error": {"code": 401}}},
    {"result": {"content": [{"type": "image", "data": "x"}]}},
    {"content": [{"type": "text", "text": '{"isError":true,"content":[]}'}]},
    {"isError": "true", "content": [{"type": "text", "text": "wrong"}]},
])
def test_e21_outer_and_nested_tool_errors_refuse(bad):
    with pytest.raises(ValueError):
        MCP.call_tool_text(bad)


def test_envelopes_unwrap_to_text_and_document_json_stays_text():
    raw = json.dumps({"tabs": TABS})
    assert MCP.call_tool_text({"result": {"content": [{"type": "text", "text": raw}]}}) == raw
    nested = json.dumps({"result": {"content": [{"type": "text", "text": "verbatim"}]}})
    assert MCP.call_tool_text({"result": {"content": [{"type": "text", "text": nested}]}}) == "verbatim"
    deep = {"content": [{"type": "text", "text": "a"}]}
    for _ in range(14):
        deep = {"result": deep}
    with pytest.raises(ValueError):
        MCP.call_tool_text(deep)


def test_event_stream_skips_notifications_and_refuses_ambiguity():
    stream = 'data: {"method":"progress"}\n\ndata: {"id":2,"result":{"content":[]}}\n\n'
    assert MCP.parse_sse(stream)["id"] == 2
    for bad, expected in ((stream + stream, 2), ('{"id":true,"result":{}}', 1), ('{"id":1,"id":2,"result":{}}', 2)):
        with pytest.raises(ValueError):
            MCP.parse_sse(bad, expected_id=expected)


# --- E22: the window lists every doc, saved or not, and the bookmark stops before the unsaved ---


def row(doc_id, modified, kind="application/vnd.google-apps.document"):
    return (f'- Name: "Standup {doc_id} - Notes by Gemini" (ID: {doc_id}, Type: {kind}, Size: 10, '
            f"Created: {modified}, Modified: {modified}, Last Edited By: Fixture <f@example.invalid>) Link: x\n")


def config(tmp_path):
    return {"workspace": "example", "google_account": "reader@example.invalid", "transcripts_repo": str(tmp_path / "repo"),
            "transcripts_path": "transcripts", "meeting_patterns": {"standup": 'name contains "Standup"'}}


def test_e22_an_unsaved_doc_is_named_and_the_bookmark_stops_before_it(monkeypatch, tmp_path):
    cfg = config(tmp_path)
    meetings = Path(cfg["transcripts_repo"]) / "transcripts" / "meetings"
    meetings.mkdir(parents=True)
    (meetings / "standup-2026-10-01.md").write_text("**Source ID:** google-drive:docA\n")
    (meetings / "standup-2026-10-03.md").write_text("**Google Doc:** https://docs.google.com/document/d/docC/edit\n")
    listing = row("docA", "2026-10-01T15:00:00Z") + row("docB", "2026-10-02T15:00:00Z") + row("docC", "2026-10-03T15:00:00Z")
    listing += row("sheet", "2026-10-02T09:00:00Z", kind="application/vnd.google-apps.spreadsheet")
    monkeypatch.setattr(FM.mcp_client, "call_tool", FakeDrive(TABS, TEXTS, listing=listing))
    result = FM.window("http://localhost:1/mcp", cfg, cfg["google_account"], FM.dt.date(2026, 10, 1), FM.dt.date(2026, 10, 3))
    assert [d["id"] for d in result["documents"]] == ["docA", "docB", "docC"]
    assert result["unsaved"] == ["docB"]
    assert result["advance_through"] == "2026-10-02T15:00:00Z"


def test_e22_a_full_search_page_is_bounded_and_never_advances(monkeypatch, tmp_path):
    cfg = config(tmp_path)
    listing = "".join(row(f"doc{i}", f"2026-10-01T{i % 24:02d}:00:00Z") for i in range(FM.PAGE_SIZE))
    monkeypatch.setattr(FM.mcp_client, "call_tool", FakeDrive(TABS, TEXTS, listing=listing))
    result = FM.window("http://localhost:1/mcp", cfg, cfg["google_account"], FM.dt.date(2026, 10, 1), FM.dt.date(2026, 10, 1))
    assert result["bounded_patterns"] == ["standup"] and result["advance_through"] is None


def test_e22_all_saved_advances_to_the_window_end(monkeypatch, tmp_path):
    cfg = config(tmp_path)
    meetings = Path(cfg["transcripts_repo"]) / "transcripts" / "meetings"
    meetings.mkdir(parents=True)
    (meetings / "a.md").write_text("**Source ID:** google-drive:docA\n")
    monkeypatch.setattr(FM.mcp_client, "call_tool", FakeDrive(TABS, TEXTS, listing=row("docA", "2026-10-01T15:00:00Z")))
    result = FM.window("http://localhost:1/mcp", cfg, cfg["google_account"], FM.dt.date(2026, 10, 1), FM.dt.date(2026, 10, 1))
    assert result["unsaved"] == [] and result["advance_through"] == "2026-10-01T23:59:59"


# --- the whole fetch: find, select, save, verify -----------------------------------------------


CONFIG = """# synthetic
workspace: example
google_account: reader@example.invalid
transcripts_repo: {repo}
transcripts_path: transcripts
meeting_patterns:
  standup: 'name contains "Standup" and name contains "Notes by Gemini"'
generic_pattern: 'name contains "{{{{name}}}}"'  # comment
"""


def run_main(monkeypatch, tmp_path, drive, *argv):
    (tmp_path / ".agents").mkdir(exist_ok=True)
    (tmp_path / ".agents" / "meeting-transcripts.yaml").write_text(CONFIG.format(repo=tmp_path / "repo"))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(FM, "server_reachable", lambda url: True)
    monkeypatch.setattr(FM.mcp_client, "call_tool", drive)
    return FM.main(list(argv))


def test_fetch_saves_both_halves_and_verifies_them(monkeypatch, tmp_path, capsys):
    drive = FakeDrive(TABS, TEXTS, listing=row("doc1", "2026-10-05T15:00:00Z"))
    assert run_main(monkeypatch, tmp_path, drive, "standup", "--date", "2026-10-05") == 0
    saved = tmp_path / "repo" / "transcripts" / "meetings" / "standup-2026-10-05.md"
    text = saved.read_text()
    assert "**Source ID:** google-drive:doc1" in text and "**Transcript tab ID:** t.k2" in text
    assert "## Verbatim transcript" in text and DIALOGUE in text
    assert json.loads(capsys.readouterr().out.splitlines()[-1])["verification"] == "OK"
    search = next(args for tool, args in drive.calls if tool == "search_drive_files")
    assert 'name contains "Standup"' in search["query"] and 'modifiedTime > "2026-10-05T00:00:00"' in search["query"]


def test_fetch_of_a_doc_without_a_transcript_tab_saves_the_no_source_marker(monkeypatch, tmp_path):
    drive = FakeDrive(TABS[:1], TEXTS, listing=row("doc1", "2026-10-05T15:00:00Z"))
    assert run_main(monkeypatch, tmp_path, drive, "standup", "--date", "2026-10-05") == 0
    text = (tmp_path / "repo" / "transcripts" / "meetings" / "standup-2026-10-05.md").read_text()
    assert "<!-- VERIFIER: no-source-transcript --> transcript-tab-absent" in text


def test_fetch_refuses_on_unknown_and_on_two_matching_docs(monkeypatch, tmp_path):
    drive = FakeDrive(TABS, TEXTS, errors=["inspect_doc_structure"], listing=row("doc1", "2026-10-05T15:00:00Z"))
    assert run_main(monkeypatch, tmp_path, drive, "standup", "--date", "2026-10-05") == 1
    assert not (tmp_path / "repo" / "transcripts" / "meetings" / "standup-2026-10-05.md").exists()
    two = FakeDrive(TABS, TEXTS, listing=row("doc1", "2026-10-05T15:00:00Z") + row("doc2", "2026-10-05T16:00:00Z"))
    assert run_main(monkeypatch, tmp_path, two, "standup", "--date", "2026-10-05") == 1


def test_a_changed_refetch_keeps_the_old_copy(monkeypatch, tmp_path):
    drive = FakeDrive(TABS, TEXTS, listing=row("doc1", "2026-10-05T15:00:00Z"))
    assert run_main(monkeypatch, tmp_path, drive, "standup", "--date", "2026-10-05") == 0
    changed = FakeDrive(TABS, {**TEXTS, "t.notes": "Regenerated summary."}, listing=row("doc1", "2026-10-05T15:00:00Z"))
    assert run_main(monkeypatch, tmp_path, changed, "standup", "--date", "2026-10-05") == 1  # exists, differs
    assert run_main(monkeypatch, tmp_path, changed, "standup", "--date", "2026-10-05", "--force") == 0
    assert len(list((tmp_path / "repo" / "transcripts" / "meetings").glob("standup-2026-10-05.old-*.md"))) == 1


def test_config_reader_handles_the_documented_schema(tmp_path):
    path = tmp_path / "meeting-transcripts.yaml"
    path.write_text(CONFIG.format(repo="/abs/repo"), encoding="utf-8")
    data = FM.load_config(path)
    assert data["meeting_patterns"]["standup"] == 'name contains "Standup" and name contains "Notes by Gemini"'
    assert data["generic_pattern"] == 'name contains "{{name}}"'


# --- the MCP client against a local stand-in server --------------------------------------------


class Server(BaseHTTPRequestHandler):
    reply = None

    def log_message(self, *args):
        pass

    def do_POST(self):
        request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if request.get("method") == "initialize":
            body = {"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": MCP.PROTOCOL_VERSION,
                                                           "capabilities": {"tools": {}}, "serverInfo": {"name": "x", "version": "1"}}}
            self.send_response(200)
            self.send_header("mcp-session-id", "session-1")
            self.send_header("Content-Type", "application/json")
            data = json.dumps(body).encode()
        elif request.get("method") == "notifications/initialized":
            self.send_response(202)
            data = b""
        else:
            status, data = Server.reply
            self.send_response(status)
            self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


@pytest.fixture
def server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Server)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/mcp"
    httpd.shutdown()


def test_client_calls_a_tool_through_a_session(server):
    Server.reply = (200, b'data: {"method":"progress"}\n\ndata: {"jsonrpc":"2.0","id":2,"result":{"content":[{"type":"text","text":"hello"}]}}\n\n')
    assert MCP.call_tool("search_drive_files", {"query": "x"}, server) == "hello"


@pytest.mark.parametrize("reply", [(401, b"not authenticated"), (200, b"x" * (MCP.MAX_RESPONSE_BYTES + 1)),
                                   (200, b'data: {"jsonrpc":"2.0","id":2,"result":{"isError":true,"content":[]}}\n\n')])
def test_client_http_errors_oversize_and_tool_errors_are_unknown(server, reply):
    Server.reply = reply
    with pytest.raises(ValueError):
        MCP.call_tool("get_doc_as_markdown", {}, server)

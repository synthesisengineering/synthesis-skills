"""The optional workspace-mcp fetch (E20 to E22) and its MCP client. Synthetic documents and a
local stand-in server only; nothing reaches Google."""

from __future__ import annotations

import importlib.util
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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
        if tool == "search_drive_files":  # a listing per query, or one listing for every query
            return self.listing(arguments["query"]) if callable(self.listing) else self.listing
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


EDT = FM.dt.timezone(FM.dt.timedelta(hours=-4))
RUN = FM.dt.datetime(2026, 10, 8, 11, 23, tzinfo=EDT)  # the 2026-10-08 report: two meetings began at 11:00
LATER = FM.dt.datetime(2026, 10, 13, 9, 0, tzinfo=EDT)  # long after every window below


def row(doc_id, modified, kind="application/vnd.google-apps.document", created=None, title="Standup"):
    return (f'- Name: "{title} {doc_id} - Notes by Gemini" (ID: {doc_id}, Type: {kind}, Size: 10, '
            f"Created: {created or modified}, Modified: {modified}, Last Edited By: Fixture <f@example.invalid>) Link: x\n")


def config(tmp_path):
    return {"workspace": "example", "google_account": "reader@example.invalid", "transcripts_repo": str(tmp_path / "repo"),
            "transcripts_path": "transcripts", "meeting_patterns": {"standup": 'name contains "Standup"'}}


def run_window(monkeypatch, cfg, listing, start, through, now):
    drive = FakeDrive(TABS, TEXTS, listing=listing)
    monkeypatch.setattr(FM.mcp_client, "call_tool", drive)
    return FM.window("http://localhost:1/mcp", cfg, cfg["google_account"], start, through, now=now), drive


def test_e22_an_unsaved_doc_is_named_and_the_bookmark_stops_before_it(monkeypatch, tmp_path):
    cfg = config(tmp_path)
    meetings = Path(cfg["transcripts_repo"]) / "transcripts" / "meetings"
    meetings.mkdir(parents=True)
    (meetings / "standup-2026-10-01.md").write_text("**Source ID:** google-drive:docA\n")
    (meetings / "standup-2026-10-03.md").write_text("**Google Doc:** https://docs.google.com/document/d/docC/edit\n")
    listing = row("docA", "2026-10-01T15:00:00Z") + row("docB", "2026-10-02T15:00:00Z") + row("docC", "2026-10-03T15:00:00Z")
    listing += row("sheet", "2026-10-02T09:00:00Z", kind="application/vnd.google-apps.spreadsheet")
    result, _ = run_window(monkeypatch, cfg, listing, FM.dt.date(2026, 10, 1), FM.dt.date(2026, 10, 3), LATER)
    assert [d["id"] for d in result["documents"]] == ["docA", "docB", "docC"]
    assert result["unsaved"] == ["docB"]
    assert result["advance_through"] == "2026-10-02T10:59:59-04:00"  # one second before docB, with its offset


def test_e22_a_blockquote_source_line_marks_its_doc_saved(monkeypatch, tmp_path):
    """2026-10-07: archives also name the doc on a provenance line, `> Source: Gemini doc `<id>``. The window
    read only the header and link forms, called those docs unsaved and held the watermark back."""
    cfg = config(tmp_path)
    meetings = Path(cfg["transcripts_repo"]) / "transcripts" / "meetings"
    meetings.mkdir(parents=True)
    (meetings / "standup-2026-10-01.md").write_text(
        "# Standup — 2026-10-01\n\n> Source: Gemini doc `1Doc_A-x` — tabs Notes (`t.n1`), Transcript (`t.k2`).\n")
    (meetings / "weekly-2026-10-03.md").write_text(
        '# Weekly\n\n> Source: Gemini notes doc "Weekly - Notes by Gemini", Drive ID `docC` (host\'s meeting).\n')
    (meetings / "notes.md").write_text("# Notes\n\n> Fetched: by `docB`, which is not its source.\nSource: `docB`\n")
    listing = row("1Doc_A-x", "2026-10-01T15:00:00Z") + row("docB", "2026-10-02T15:00:00Z") + row("docC", "2026-10-03T15:00:00Z")
    result, _ = run_window(monkeypatch, cfg, listing, FM.dt.date(2026, 10, 1), FM.dt.date(2026, 10, 3), LATER)
    assert {d["id"]: d["saved"] for d in result["documents"]} == {
        "1Doc_A-x": "standup-2026-10-01.md", "docB": None, "docC": "weekly-2026-10-03.md"}
    assert result["unsaved"] == ["docB"] and result["advance_through"] == "2026-10-02T10:59:59-04:00"


def test_e22_a_full_search_page_is_bounded_and_never_advances(monkeypatch, tmp_path):
    cfg = config(tmp_path)
    listing = "".join(row(f"doc{i}", f"2026-10-01T{i % 24:02d}:00:00Z") for i in range(FM.PAGE_SIZE))
    result, _ = run_window(monkeypatch, cfg, listing, FM.dt.date(2026, 10, 1), FM.dt.date(2026, 10, 1), LATER)
    assert result["bounded_patterns"] == ["standup", "(undeclared)"] and result["advance_through"] is None


@pytest.mark.parametrize("tail", ["nextPageToken: page-2\n",
                                  "WARNING: Google Drive did not search every corpus (incompleteSearch), so these results...\n"])
def test_e22_a_next_page_token_or_an_incomplete_search_is_bounded_too(monkeypatch, tmp_path, tail):
    """A short page with a token, or Drive's incompleteSearch flag, hides docs as surely as a full page."""
    cfg = config(tmp_path)
    result, _ = run_window(monkeypatch, cfg, row("docA", "2026-10-01T15:00:00Z") + tail,
                           FM.dt.date(2026, 10, 1), FM.dt.date(2026, 10, 1), LATER)
    assert "standup" in result["bounded_patterns"] and result["advance_through"] is None


def test_e22_all_saved_advances_to_the_window_end(monkeypatch, tmp_path):
    cfg = config(tmp_path)
    meetings = Path(cfg["transcripts_repo"]) / "transcripts" / "meetings"
    meetings.mkdir(parents=True)
    (meetings / "a.md").write_text("**Source ID:** google-drive:docA\n")
    result, _ = run_window(monkeypatch, cfg, row("docA", "2026-10-01T15:00:00Z"), FM.dt.date(2026, 10, 1), FM.dt.date(2026, 10, 1), LATER)
    assert result["unsaved"] == [] and result["advance_through"] == "2026-10-01T19:59:59-04:00"  # 23:59:59 UTC


# --- E28: the bookmark never passes the run, or a meeting not yet ended or saved (2026-10-08) ---


def test_e28_the_bookmark_stays_behind_the_run_while_meetings_may_be_under_way(monkeypatch, tmp_path):
    """At 11:23 the check offered 23:59:59 while two 11:00 meetings ran; neither had a notes doc Drive could list."""
    cfg = config(tmp_path)
    meetings = Path(cfg["transcripts_repo"]) / "transcripts" / "meetings"
    meetings.mkdir(parents=True)
    (meetings / "standup-2026-10-08.md").write_text("**Source ID:** google-drive:docA\n")
    listing = row("docA", "2026-10-08T13:40:00Z", created="2026-10-08T13:00:00Z")  # 09:00-09:30 EDT, saved
    result, _ = run_window(monkeypatch, cfg, listing, FM.dt.date(2026, 10, 8), FM.dt.date(2026, 10, 8), RUN)
    assert result["advance_through"] == "2026-10-08T09:23:00-04:00"  # the run less the stated margin
    assert result["advance_reason"].startswith(f"{FM.MARGIN_HOURS} hours before the run")
    assert result["unsaved"] == [] and result["checked_at"] == "2026-10-08T11:23:00-04:00"
    assert FM.dt.datetime.fromisoformat(result["advance_through"]) < FM.dt.datetime(2026, 10, 8, 11, 0, tzinfo=EDT)


def test_e28_an_unsaved_meeting_holds_the_bookmark_before_its_doc_was_created(monkeypatch, tmp_path):
    """A doc created when note-taking began and still being written: the bookmark stops before it was created, not at
    its last edit."""
    cfg = config(tmp_path)
    listing = row("docB", "2026-10-02T15:30:00Z", created="2026-10-02T14:00:00Z")
    result, _ = run_window(monkeypatch, cfg, listing, FM.dt.date(2026, 10, 1), FM.dt.date(2026, 10, 3), LATER)
    assert result["unsaved"] == ["docB"] and result["advance_through"] == "2026-10-02T09:59:59-04:00"
    assert result["advance_reason"] == "just before unsaved doc docB was created"


def test_e28_a_suggestion_names_its_offset_so_a_bookmark_reads_it_as_meant(monkeypatch, tmp_path):
    """The bookmark reads a time without an offset as local, and Python 3.9 cannot read a trailing Z."""
    cfg = config(tmp_path)
    for listing in (row("docB", "2026-10-02T15:00:00.000Z"), ""):
        result, _ = run_window(monkeypatch, cfg, listing, FM.dt.date(2026, 10, 1), FM.dt.date(2026, 10, 3), LATER)
        moment = FM.dt.datetime.fromisoformat(result["advance_through"])
        assert moment.tzinfo is not None and not result["advance_through"].endswith("Z")


# --- E29: only the declared patterns are searched, and the output says so every time -----------


def test_e29_the_output_names_the_patterns_it_searched_and_lists_undeclared_notes_docs(monkeypatch, tmp_path):
    cfg = config(tmp_path)
    cfg["meeting_patterns"]["retro"] = 'name contains "Retro"'
    meetings = Path(cfg["transcripts_repo"]) / "transcripts" / "meetings"
    meetings.mkdir(parents=True)
    (meetings / "standup-2026-10-01.md").write_text("**Source ID:** google-drive:docA\n")
    standup = row("docA", "2026-10-01T15:00:00Z")
    planning = row("docX", "2026-10-01T16:00:00Z", title="Planning")  # a recurring meeting nobody declared
    by_query = lambda query: standup if "Standup" in query else standup + planning if "Notes by Gemini" in query else ""
    result, drive = run_window(monkeypatch, cfg, by_query, FM.dt.date(2026, 10, 1), FM.dt.date(2026, 10, 1), LATER)
    assert result["searched"] == cfg["meeting_patterns"]
    assert result["scope"].startswith("Only these patterns were searched: standup, retro. A doc none of them matches")
    assert "advance_through does not cover it" in result["scope"]
    assert [d["id"] for d in result["documents"]] == ["docA"] and result["unsaved"] == []
    assert [(d["id"], d["saved"]) for d in result["undeclared"]] == [("docX", None)]
    assert result["advance_through"] == "2026-10-01T19:59:59-04:00"  # an undeclared doc is reported, not a hold
    assert len([tool for tool, _ in drive.calls if tool == "search_drive_files"]) == 3


def test_e29_with_no_declared_patterns_the_generic_search_is_named(monkeypatch, tmp_path):
    cfg = config(tmp_path)
    del cfg["meeting_patterns"]
    result, drive = run_window(monkeypatch, cfg, row("docA", "2026-10-01T15:00:00Z"), FM.dt.date(2026, 10, 1),
                               FM.dt.date(2026, 10, 1), LATER)
    assert result["scope"].startswith("Only these patterns were searched: (generic).") and result["undeclared"] == []
    assert list(result["searched"]) == ["(generic)"] and len(drive.calls) == 1


def test_e29_the_command_prints_the_scope_on_every_window_run(monkeypatch, tmp_path, capsys):
    drive = FakeDrive(TABS, TEXTS, listing=row("doc1", "2026-10-05T15:00:00Z"))
    assert run_main(monkeypatch, tmp_path, drive, "--window", "2026-10-05", "2026-10-05") == 1  # doc1 is unsaved
    printed = json.loads(capsys.readouterr().out)
    assert printed["scope"].startswith("Only these patterns were searched: standup.") and printed["unsaved"] == ["doc1"]


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


def test_saving_a_transcript_redacts_docs_image_keys(tmp_path):
    out = tmp_path / "meetings" / "planning-2026-10-05.md"
    FM.save(out, "Notes ![](https://lh7-rt.googleusercontent.com/docsz/AD_4nX?key=k3yV4lue)\n", force=False)
    assert out.read_text(encoding="utf-8") == "Notes ![](https://lh7-rt.googleusercontent.com/docsz/AD_4nX?key=REDACTED)\n"

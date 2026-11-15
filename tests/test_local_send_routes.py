"""5.23.1: routes past the send guard and the protected-folder guard that the review of the runtime's carried scripts
found (2026-11-15, its problems older than the change, A, B and D).

A. The meeting-transcripts skill's `mcp_client.py` calls any tool of the local workspace-mcp server, whose default tier
includes `send_gmail_message`, and nothing held `python3 mcp_client.py send_gmail_message '{...}'` or a `curl` POST of
the same JSON-RPC to `localhost:8765/mcp`: a write to this machine is no post to another host. A command that calls a
local MCP server's tool, by the client script, by an HTTP client to the server's endpoint or by a program that posts its
JSON-RPC, is now judged as that tool's call would be: a sending tool waits for the principal's code for that exact
call, a reading tool passes, and a tool whose name the guard cannot read waits. Sixty days of Claude Code and Codex
records (2026-11-15) held 251 client runs, 48 liveness reads of the server and 113 programs posting its JSON-RPC: none
named a sending tool, and no result read as a message, draft or event made.
"""

from __future__ import annotations

import json
import shlex
from pathlib import Path

import pytest

from synthesis import approvals, guards, sends

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "skills" / "synthesis-message-guard" / "config.example.json").read_text(encoding="utf-8"))
SESSION = {"session_id": "S-principal"}
WM = ROOT / "skills" / "synthesis-meeting-transcripts" / "optional-workspace-mcp"
CLIENT, FETCHER = WM / "mcp_client.py", WM / "fetch-meeting.py"
MAIL = {"user_google_email": "principal@example.com", "to": "colleague@example.com", "subject": "Notes",
        "body": "<p>The notes from today are in the shared folder.</p>", "body_format": "html"}
READ = {"user_google_email": "principal@example.com", "query": "name contains 'Notes'"}


def shell(command: str, cwd: str = "/tmp", session: dict = SESSION) -> str:
    return guards.check("Bash", {"command": command}, CONFIG, cwd=cwd, session=session) or ""


def held(reason: str) -> bool:
    return "approve" in reason


def rpc(tool: str, arguments: dict, rid: int = 2) -> str:
    return json.dumps({"jsonrpc": "2.0", "id": rid, "method": "tools/call", "params": {"name": tool, "arguments": arguments}})


def client(tool: str, arguments: dict | None = None) -> str:
    return f"python3 {CLIENT} {tool}" + (f" {shlex.quote(json.dumps(arguments))}" if arguments is not None else "")


def curl(body: str, url: str = "http://localhost:8765/mcp") -> str:
    return f"curl -s -X POST {url} -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' -d {shlex.quote(body)}"


# --- A: a sending tool, by each route ---------------------------------------------------------------------------------

SENDS = {
    "the client script": client("send_gmail_message", MAIL),
    "curl to the server": curl(rpc("send_gmail_message", MAIL)),
    "curl to 127.0.0.1": curl(rpc("send_gmail_message", MAIL), "http://127.0.0.1:8765/mcp"),
    "curl to [::1]": curl(rpc("send_gmail_message", MAIL), "http://[::1]:8765/mcp"),
    "curl --json": f"curl -s http://localhost:8765/mcp --json {shlex.quote(rpc('send_gmail_message', MAIL))}",
    "curl --data-raw=": f"curl -s -X POST --data-raw={shlex.quote(rpc('send_gmail_message', MAIL))} http://localhost:8765/mcp",
    "curl, a JSON-RPC batch": curl(json.dumps([json.loads(rpc("search_drive_files", READ, 3)), json.loads(rpc("send_gmail_message", MAIL))])),
    "curl, its body on a heredoc": "curl -s -X POST http://localhost:8765/mcp -d @- <<'EOF'\n" + rpc("send_gmail_message", MAIL) + "\nEOF",
    "wget --post-data": f"wget -qO- --post-data={shlex.quote(rpc('send_gmail_message', MAIL))} http://localhost:8765/mcp",
    "curl in a shell script's line": "bash -c " + shlex.quote(curl(rpc("send_gmail_message", MAIL))),
    "a Chat message": client("send_message", {"user_google_email": "principal@example.com", "space_id": "spaces/AAA",
                                              "message_text": "The notes are in the shared folder."}),
    "an invitation": client("manage_event", {"user_google_email": "principal@example.com", "action": "create", "summary": "Review",
                                             "start_time": "2026-12-01T15:00:00Z", "end_time": "2026-12-01T15:30:00Z",
                                             "attendees": ["colleague@example.com"]}),
    "a draft": client("draft_gmail_message", MAIL),
    "a document edit": client("modify_doc_text", {"user_google_email": "principal@example.com", "document_id": "d1", "text": "A line."}),
}


@pytest.mark.parametrize("route", list(SENDS))
def test_a_sending_tool_of_the_local_server_waits_for_the_code(route):
    reason = shell(SENDS[route])
    assert held(reason), route
    assert "identical command" in reason, route  # the shell's words, not a connector's


PROGRAMS = {
    "python on its input, urllib": "python3 - <<'EOF'\nimport json, urllib.request\nbody = " + repr(rpc("send_gmail_message", MAIL))
    + "\nurllib.request.urlopen(urllib.request.Request('http://localhost:8765/mcp', data=body.encode(), method='POST'))\nEOF",
    "python, a dict it posts": "python3 - <<'EOF'\nimport json, urllib.request\npayload = {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', "
    "'params': {'name': 'send_gmail_message', 'arguments': " + repr(MAIL) + "}}\nurllib.request.urlopen('http://127.0.0.1:8765/mcp', "
    "data=json.dumps(payload).encode())\nEOF",
    "python -c, the client's module": f"python3 -c \"import sys; sys.path.insert(0, '{WM}'); import mcp_client; "
    f"print(mcp_client.call_tool('send_gmail_message', {MAIL!r}))\"",
    "node -e, fetch": "node -e \"fetch('http://localhost:8765/mcp', {method: 'POST', body: JSON.stringify({jsonrpc: '2.0', id: 2, "
    "method: 'tools/call', params: {name: 'send_gmail_message', arguments: {to: 'colleague@example.com'}}})})\"",
}


@pytest.mark.parametrize("program", list(PROGRAMS))
def test_a_program_that_posts_a_sending_tools_json_rpc_waits(program):
    assert held(shell(PROGRAMS[program])), program


def test_a_program_file_that_posts_it_waits_and_so_does_the_client_under_another_name(tmp_path):
    poster = tmp_path / "poster.py"
    poster.write_text("import json, urllib.request\nPAYLOAD = {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': "
                      "{'name': 'send_gmail_message', 'arguments': " + repr(MAIL) + "}}\n"
                      "urllib.request.urlopen('http://localhost:8765/mcp', data=json.dumps(PAYLOAD).encode())\n", encoding="utf-8")
    assert held(shell(f"python3 {poster}", cwd=str(tmp_path)))
    renamed = tmp_path / "c.py"
    renamed.write_bytes(CLIENT.read_bytes())  # the client copied under another name takes the tool from its arguments
    assert held(shell(f"python3 {renamed} send_gmail_message {shlex.quote(json.dumps(MAIL))}", cwd=str(tmp_path)))
    assert shell(f"python3 {renamed} search_drive_files {shlex.quote(json.dumps(READ))}", cwd=str(tmp_path)) == ""
    wrapper = tmp_path / "wrapper.py"  # a program of its own that hands the client a tool name from its arguments
    wrapper.write_text("import json, sys\nsys.path.insert(0, %r)\nimport mcp_client\nprint(mcp_client.call_tool(sys.argv[1], "
                       "json.loads(sys.argv[2])))\n" % str(WM), encoding="utf-8")
    assert held(shell(f"python3 {wrapper} send_gmail_message {shlex.quote(json.dumps(MAIL))}", cwd=str(tmp_path)))
    assert shell(f"python3 {wrapper} get_events {shlex.quote(json.dumps(READ))}", cwd=str(tmp_path)) == ""


@pytest.mark.parametrize("command", [
    f"python3 {CLIENT} \"$TOOL\" '{{}}'",                                                   # a name the shell fills in
    f"python3 {CLIENT} $(cat tool.txt) '{{}}'",
    "curl -s -X POST http://localhost:8765/mcp -d @missing-body.json",                       # a body it cannot read
    "jq -n '{jsonrpc: \"2.0\"}' | curl -s -X POST http://localhost:8765/mcp -d @-",          # a body another program writes
    "curl -s -X POST http://localhost:8765/mcp -d \"$(cat body.json)\"",
    "python3 - <<'EOF'\nimport json, sys, urllib.request\nname = open('tool.txt').read().strip()\n"
    "urllib.request.urlopen('http://localhost:8765/mcp', data=json.dumps({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', "
    "'params': {'name': name, 'arguments': {}}}).encode())\nEOF",                             # a name it reads while it runs
    "python3 -c \"import mcp_client; mcp_client.call_tool('send_' + 'gmail_message', {})\"",  # a name it builds
])
def test_a_call_whose_tool_the_guard_cannot_read_waits(command, tmp_path):
    assert held(shell(command, cwd=str(tmp_path))), command


# --- A: what passes ---------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("command", [
    client("search_drive_files", READ), client("get_events", READ), client("list_calendars", {"user_google_email": "principal@example.com"}),
    client("get_doc_as_markdown", {"user_google_email": "principal@example.com", "document_id": "d1"}),
    client("inspect_doc_structure", {"user_google_email": "principal@example.com", "document_id": "d1"}),
    f"python3 {CLIENT} list", f"python3 {CLIENT} list gmail", f"python3 {CLIENT} --help", f"python3 {CLIENT}",
    "curl -sS -o /dev/null -w '%{http_code}' --max-time 6 http://localhost:8765/mcp",     # the service doctor's liveness read
    curl(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                                                                                   "clientInfo": {"name": "probe", "version": "1"}}})),
    curl(json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})),
    curl(rpc("search_gmail_messages", {"user_google_email": "principal@example.com", "query": "from:me"})),
    "curl -s -X POST http://localhost:3000/api/items -H 'Content-Type: application/json' -d '{\"name\": \"x\"}'",  # another local app
    "curl -s -X POST http://localhost:8787/graphql -d @query.json",
    "python3 - <<'EOF'\nimport json, urllib.request\nfor tool in ('search_drive_files', 'get_doc_as_markdown'):\n"
    "    urllib.request.urlopen('http://localhost:8765/mcp', data=json.dumps({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', "
    "'params': {'name': tool, 'arguments': {}}}).encode())\nEOF",                             # names it reads from its own literals
])
def test_reading_tools_and_other_local_calls_need_no_code(command, tmp_path):
    (tmp_path / "query.json").write_text('{"query": "{ items { id } }"}', encoding="utf-8")
    assert shell(command, cwd=str(tmp_path)) == "", command


@pytest.mark.parametrize("arguments", [["--window", "2026-11-14", "2026-11-15"], ["standup", "--date", "2026-11-14"],
                                       ["--window", "2026-11-14", "2026-11-15", "--port", "8765"]])
def test_the_meeting_fetcher_reads_through_the_client_with_no_new_wait(arguments):
    """Its tools are the ones it names: inspect_doc_structure, get_doc_as_markdown and search_drive_files."""
    command = shlex.join(["python3", str(FETCHER), *arguments])
    assert guards.check_outgoing(command, CONFIG, "/tmp", SESSION) is None


# --- A: judged as the tool's own call ----------------------------------------------------------------------------------

def test_the_code_releases_that_exact_call_once(principal):
    command = SENDS["the client script"]
    reason = shell(command)
    assert held(reason) and "send_gmail_message" in reason
    principal(reason)
    assert shell(command) == ""
    assert sends.ledger(__import__("time").strftime("%Y-%m-%d"))[-1]["tool"].endswith("send_gmail_message")
    assert held(shell(command))  # one code, one send
    other = dict(MAIL, body="<p>A different message.</p>")
    assert held(shell(client("send_gmail_message", other)))  # another message asks for its own


def test_it_is_the_same_approval_the_connector_call_takes(principal):
    """The principal approves one message, whichever route carries it: the code the shell route asks for releases the
    connector's identical call, as the connector's own would."""
    reason = shell(SENDS["curl to the server"])
    principal(reason)
    assert guards.check("mcp__workspace-mcp__send_gmail_message", MAIL, CONFIG, cwd="/tmp", session=SESSION) is None


def test_the_register_scan_and_the_format_rules_apply_as_to_the_connector():
    sorry = dict(MAIL, body="<p>Sorry for the delay, the notes are in the shared folder.</p>")
    reason = shell(client("send_gmail_message", sorry))
    assert "delay-apology" in reason and "can't go out as written" in reason
    plain = dict(MAIL, body="The notes are in the shared folder.", body_format="plain")  # mail goes out as HTML
    connector = guards.check("mcp__workspace-mcp__send_gmail_message", plain, CONFIG, cwd="/tmp", session=SESSION) or ""
    assert "can't go out as written" in connector and "can't go out as written" in shell(client("send_gmail_message", plain))


def test_the_account_a_call_acts_as_is_checked_as_for_the_connector(tmp_path):
    config = dict(CONFIG, account_routing={"default_account": "principal@example.com", "workspaces": {
        str(tmp_path): {"account": "work@example.org", "label": "work"}}})
    reason = guards.check("Bash", {"command": client("send_gmail_message", MAIL)}, config, cwd=str(tmp_path), session=SESSION) or ""
    assert "would act as principal@example.com" in reason and "work@example.org" in reason


def test_a_known_sending_tool_whose_arguments_are_built_waits_for_the_command(principal, tmp_path):
    """A program that names a sending tool and builds its arguments: the code binds the command and the program's text."""
    program = tmp_path / "send.py"
    program.write_text("import json, sys, urllib.request\nargs = json.load(open(sys.argv[1]))\nurllib.request.urlopen("
                       "'http://localhost:8765/mcp', data=json.dumps({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', "
                       "'params': {'name': 'send_gmail_message', 'arguments': args}}).encode())\n", encoding="utf-8")
    (tmp_path / "args.json").write_text(json.dumps(MAIL), encoding="utf-8")
    command = f"python3 {program} args.json"
    reason = shell(command, cwd=str(tmp_path))
    assert held(reason) and "send_gmail_message" in reason
    principal(reason)
    assert shell(command, cwd=str(tmp_path)) == ""
    program.write_text(program.read_text(encoding="utf-8") + "# changed\n", encoding="utf-8")
    assert held(shell(command, cwd=str(tmp_path)))  # the program changed: a new code

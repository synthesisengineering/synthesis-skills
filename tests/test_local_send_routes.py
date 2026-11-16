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

B. An agent's own program that handed `osascript` a script it read from a file ran with no code, while `osascript <file>`
waited; pointed at the local-messaging skill's `messages_transport.js`, that is a Messages send. A program that starts
osascript with a script file is now judged by that file's text, as `osascript <file>` is, and one whose file it builds
or the guard cannot read waits. The plugin's own sender, as shipped, is judged by the send gate inside it, and a run the
principal approved by its exact command is not asked about twice.

D. `git status`, which the guard reads as a reader, runs the program a repository's own `core.fsmonitor` names, and the
agent may make the repository: the reviewer's wrote into the state folder. A git command is now judged as running each
program the configuration it reads names (the repository's own, with what it includes, and the line's own), and one
whose program cannot be read waits; a repository whose configuration names no program reads as before. None of the
350 repositories the records' git commands ran in, nor the 320 under the workspaces, names one.
"""

from __future__ import annotations

import json
import os
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


RPC = ("import json, urllib.request\nURL = 'http://localhost:8765/mcp'\n"
       "def rpc(method, params):\n    body = {'jsonrpc': '2.0', 'id': 2, 'method': method, 'params': params}\n"
       "    return urllib.request.urlopen(URL, data=json.dumps(body).encode()).read()\n")


@pytest.mark.parametrize("program", [  # shapes 60 days of records held, each reading through the local server
    RPC + "for tool in ['search_drive_files', 'get_doc_as_markdown']:\n    rpc('tools/call', {'name': tool, 'arguments': {}})\n",
    RPC + "CALLS = [{'name': 'get_events', 'arguments': {}}, {'name': 'list_calendars', 'arguments': {}}]\n"
    "for spec in CALLS:\n    rpc('tools/call', {'name': spec['name'], 'arguments': spec['arguments']})\n",
    RPC + "for name, args in [('search_gmail_messages', {'query': 'x'}), ('get_gmail_messages_content_batch', {})]:\n"
    "    rpc('tools/call', {'name': name, 'arguments': args})\n",
    RPC + "class Client:\n    def call(self, tool, args):\n        return rpc('tools/call', {'name': tool, 'arguments': args})\n"
    "Client().call('read_sheet_values', {})\n",
    "notes = 'the client posts tools/call to the server, and fetch-meeting.py uses call_tool() for its reads'\nprint(notes)\n",
])
def test_ordinary_programs_that_read_through_the_server_need_no_code(tmp_path, program):
    assert shell("python3 - <<'EOF'\n" + program + "EOF", cwd=str(tmp_path)) == "", program
    assert shell("cat > reader.py <<'EOF'\n" + program + "EOF\npython3 reader.py", cwd=str(tmp_path)) == "", program  # one the line writes


def test_a_method_its_text_names_with_no_readable_call_waits(tmp_path):
    program = ("import json, urllib.request\nbody = {'jsonrpc': '2.0', 'id': 2}\nbody['method'] = 'tools/call'\n"
               "body['params'] = {'name': open('tool.txt').read().strip(), 'arguments': {}}\n"
               "urllib.request.urlopen('http://localhost:8765/mcp', data=json.dumps(body).encode())\n")
    assert held(shell("python3 - <<'EOF'\n" + program + "EOF", cwd=str(tmp_path)))


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


# --- B: a program that starts osascript with a script file -------------------------------------------------------------

LM = ROOT / "skills" / "synthesis-local-messaging" / "scripts"
TRANSPORT = LM / "messages_transport.js"
QUIET = 'Application("Finder").name()\n'
READS_ARGV = ("import subprocess, sys\njs = open(sys.argv[1]).read()\n"
              "subprocess.run(['/usr/bin/osascript', '-l', 'JavaScript', '-e', js, sys.argv[2]])\n")  # the review's probe


def program(tmp_path, text: str, name: str = "send.py") -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_the_reviews_program_pointed_at_the_messages_transport_waits(tmp_path):
    send = program(tmp_path, READS_ARGV)
    reason = shell(f"python3 {send} {TRANSPORT} 3", cwd=str(tmp_path))
    assert held(reason) and "mobilesms" in reason.lower(), reason  # Messages, by its bundle id as the script names it
    (tmp_path / "quiet.js").write_text(QUIET, encoding="utf-8")
    assert shell(f"python3 {send} {tmp_path / 'quiet.js'} 3", cwd=str(tmp_path)) == ""  # as `osascript quiet.js` passes


@pytest.mark.parametrize("text", [
    "import subprocess\njs = open('send.js').read()\nsubprocess.run(['osascript', '-l', 'JavaScript', '-e', js])\n",  # a file it names
    "import subprocess, sys\npath = sys.argv[1]\nsubprocess.run(['osascript', '-l', 'JavaScript', path])\n",            # handed on to osascript
    "import subprocess, sys\nsubprocess.run(['osascript'], input=open(sys.argv[1]).read(), text=True)\n",               # on its input
    "from pathlib import Path\nimport subprocess\nHERE = Path(__file__).parent\n"
    "subprocess.run(['osascript', '-l', 'JavaScript', '-e', (HERE / 'send.js').read_text()])\n",                       # beside it
])
def test_a_program_is_judged_by_the_script_file_it_hands_osascript(tmp_path, text):
    send = program(tmp_path, text)
    (tmp_path / "send.js").write_bytes(TRANSPORT.read_bytes())
    assert held(shell(f"python3 {send} send.js", cwd=str(tmp_path))), text
    (tmp_path / "send.js").write_text(QUIET, encoding="utf-8")
    assert shell(f"python3 {send} send.js", cwd=str(tmp_path)) == "", text


def test_node_reading_the_script_file_is_judged_the_same_way(tmp_path):
    send = program(tmp_path, "const {execFileSync} = require('child_process');\nconst fs = require('fs');\n"
                             "execFileSync('osascript', ['-l', 'JavaScript', '-e', fs.readFileSync(process.argv[2], 'utf8')]);\n", "send.js")
    assert held(shell(f"node {send} {TRANSPORT}", cwd=str(tmp_path)))


@pytest.mark.parametrize("text", [
    "import os, subprocess\nsubprocess.run(['osascript', '-l', 'JavaScript', os.environ['SCRIPT']])\n",            # a file it is not shown
    "import subprocess\njs = open('missing.js').read()\nsubprocess.run(['osascript', '-l', 'JavaScript', '-e', js])\n",  # a file that is not there
    "import subprocess\nopen('built.js', 'w').write('Application(\"Messages\")')\nsubprocess.run(['osascript', 'built.js'])\n",  # one it builds
    "import json, subprocess\nscript = json.load(open('config.json'))['script']\nsubprocess.run(['osascript', '-e', script])\n",  # read from data
])
def test_a_script_file_it_builds_or_the_guard_cannot_read_waits(tmp_path, text):
    send = program(tmp_path, text)
    (tmp_path / "built.js").write_text(QUIET, encoding="utf-8")  # what is there before the program rewrites it
    (tmp_path / "config.json").write_text('{"script": "display notification \\"x\\""}', encoding="utf-8")
    assert held(shell(f"python3 {send}", cwd=str(tmp_path))), text


@pytest.mark.parametrize("text", [
    "import subprocess\nsubprocess.run(['osascript', '-e', 'display notification \"done\" with title \"Build\"'])\n",
    "import subprocess\ntext = 'done'\nsubprocess.run(['osascript', '-e', f'display notification \"{text}\" with title \"Autopilot\"'])\n",
    "import subprocess\nnotes = open('notes.txt').read()\nsubprocess.run(['osascript', '-e', f'display notification \"{len(notes)}\"'])\n",
    "import subprocess\nsubprocess.run(['osascript', '-e', 'tell application \"Mail\" to count messages of inbox'])\n",
    "import shutil, subprocess\nnotes = open('notes.txt').read()\nif shutil.which('osascript'):\n"  # a lookup is no run
    "    subprocess.run(['osascript', '-e', f'display notification \"{len(notes)}\"'])\n",
])
def test_ordinary_osascript_from_a_program_still_needs_no_code(tmp_path, text):
    (tmp_path / "notes.txt").write_text("some notes\n", encoding="utf-8")
    assert shell(f"python3 {program(tmp_path, text, 'note.py')}", cwd=str(tmp_path)) == "", text


@pytest.mark.parametrize("script", ["synthesis-autopilot/scripts/autopilot_cli.py status",
                                    "synthesis-daily-rituals/scripts/decay_sweep.py --help"])
def test_the_plugins_notifying_scripts_still_need_no_code(script):
    path, _, rest = script.partition(" ")
    assert guards.check_outgoing(f"python3 {ROOT / 'skills' / path} {rest}", CONFIG, "/tmp", SESSION) is None


def test_the_plugins_own_sender_as_shipped_is_judged_by_the_gate_inside_it(tmp_path, principal):
    (tmp_path / "t.txt").write_text("On my way\n", encoding="utf-8")
    shipped = f"python3 {LM / 'messages_send.py'} --to +15550100 --text-file {tmp_path / 't.txt'}"
    assert guards.check_outgoing(shipped, CONFIG, str(tmp_path), SESSION) is None
    copy = tmp_path / "copy"  # a byte-identical copy outside the release is no plugin script: its first run waits
    copy.mkdir()
    for name in ("messages_send.py", "messages_route.js", "messages_transport.js"):
        (copy / name).write_bytes((LM / name).read_bytes())
    command = f"python3 {copy / 'messages_send.py'} --to +15550100 --text-file {tmp_path / 't.txt'}"
    reason = shell(command, cwd=str(tmp_path))
    assert held(reason)
    principal(reason)  # the principal approves that exact run, and it is not asked about a second time
    assert shell(command, cwd=str(tmp_path)) == ""


# --- D: a git command and the programs its configuration names ---------------------------------------------------------

def repo(tmp_path, name: str = "proj", **config) -> Path:
    import subprocess
    path = tmp_path / name
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    for key, value in config.items():
        subprocess.run(["git", "-C", str(path), "config", key.replace("__", "."), value], check=True)
    return path


def writer(tmp_path) -> Path:
    """A program that writes into the synthesis state folder, where approvals live."""
    from synthesis import paths
    script = tmp_path / "fsmonitor.sh"
    script.write_text(f"#!/bin/sh\necho ran > '{paths.state()}/marker'\nexit 1\n", encoding="utf-8")
    script.chmod(0o755)
    return script


@pytest.mark.parametrize("command", ["git -C {r} status --porcelain", "git -C {r} status", "git -C {r} diff",
                                     "git -C {r} ls-files", "git -C {r} log --oneline -1", "cd {r} && git status"])
def test_a_repositorys_fsmonitor_program_is_judged_as_run(tmp_path, command):
    r = repo(tmp_path, core__fsmonitor=str(writer(tmp_path)))
    assert held(shell(command.format(r=r), cwd=str(tmp_path))), command


def test_every_way_a_repositorys_configuration_names_a_program_is_judged(tmp_path):
    from synthesis import paths
    write = f"echo ran > '{paths.state()}/marker'"
    assert held(shell(f"git -C {repo(tmp_path, 'a', core__fsmonitor=write)} status", cwd=str(tmp_path)))  # shell text
    extra = tmp_path / "extra.cfg"
    extra.write_text(f"[core]\n\tfsmonitor = {writer(tmp_path)}\n", encoding="utf-8")
    assert held(shell(f"git -C {repo(tmp_path, 'b', include__path=str(extra))} status", cwd=str(tmp_path)))  # through an include
    hooks = tmp_path / "hooks"
    hooks.mkdir()
    (hooks / "post-index-change").write_text(f"#!/bin/sh\n{write}\n", encoding="utf-8")
    (hooks / "post-index-change").chmod(0o755)
    assert held(shell(f"git -C {repo(tmp_path, 'c', core__hooksPath=str(hooks))} status", cwd=str(tmp_path)))  # its hooks
    aliased = repo(tmp_path, "d", alias__st=f"!{write}")
    assert held(shell(f"git -C {aliased} st", cwd=str(tmp_path)))  # an alias that runs a shell, by its own name
    assert shell(f"git -C {aliased} status", cwd=str(tmp_path)) == ""  # status runs no alias
    assert held(shell(f"git -C {repo(tmp_path, 'e', core__sshCommand=write)} fetch origin", cwd=str(tmp_path)))
    assert held(shell(f"git -C {repo(tmp_path, 'f', credential__helper='!' + write)} push", cwd=str(tmp_path)))
    assert held(shell(f"git -C {repo(tmp_path, 'g', diff__external=write)} diff", cwd=str(tmp_path)))
    assert held(shell(f"git -C {repo(tmp_path, 'h', core__pager=write)} log", cwd=str(tmp_path)))


def test_a_linked_worktree_reads_its_repositorys_configuration(tmp_path):
    import subprocess
    r = repo(tmp_path, core__fsmonitor=str(writer(tmp_path)))
    subprocess.run(["git", "-C", str(r), "-c", "core.fsmonitor=false", "commit", "-q", "--allow-empty", "-m", "one"], check=True)
    subprocess.run(["git", "-C", str(r), "-c", "core.fsmonitor=false", "worktree", "add", "-q", str(tmp_path / "wt")], check=True)
    assert held(shell(f"git -C {tmp_path / 'wt'} status", cwd=str(tmp_path)))


def test_the_lines_own_configuration_and_environment_are_judged_too(tmp_path):
    w, r = writer(tmp_path), repo(tmp_path)
    assert held(shell(f"git -c core.fsmonitor={w} -C {r} status", cwd=str(tmp_path)))
    assert held(shell(f"GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.fsmonitor GIT_CONFIG_VALUE_0={w} git -C {r} status", cwd=str(tmp_path)))
    assert held(shell(f"GIT_EXTERNAL_DIFF={w} git -C {r} diff", cwd=str(tmp_path)))
    assert held(shell(f"git --config-env=core.fsmonitor=NOT_SET_HERE -C {r} status", cwd=str(tmp_path)))  # a value it cannot read


def test_a_program_that_sends_is_judged_as_a_send(tmp_path):
    send = "osascript -e 'tell application \"Messages\" to send \"On my way\" to buddy \"+15550100\"'"
    reason = shell(f"git -C {repo(tmp_path, core__fsmonitor=send)} status", cwd=str(tmp_path))
    assert held(reason) and "messages" in reason.lower()


@pytest.mark.parametrize("config", [{}, {"core__fsmonitor": "true"}, {"core__fsmonitor": "false"}, {"core__fsmonitor": "/usr/bin/true"},
                                    {"user__email": "a@example.com", "pull__rebase": "true", "core__autocrlf": "input"}])
def test_an_ordinary_repositorys_reads_still_pass(tmp_path, config):
    r = repo(tmp_path, **config)
    for command in (f"git -C {r} status --porcelain", f"git -C {r} log --oneline -3", f"git -C {r} diff --stat",
                    f"git -C {r} rev-parse --show-toplevel", f"git -C {r} remote -v", f"cd {r} && git status && git branch",
                    f"GIT_EDITOR=true git -C {r} status", f"GIT_CONFIG_GLOBAL=/dev/null git -C {r} status",
                    f"git -c core.hooksPath=/dev/null -C {r} status", f"git -c core.fsmonitor=false -C {r} status"):
        assert shell(command, cwd=str(tmp_path)) == "", (config, command)


def test_the_code_releases_that_git_command_once(tmp_path, principal):
    r = repo(tmp_path, core__fsmonitor=str(writer(tmp_path)))
    command = f"git -C {r} status --porcelain"
    reason = shell(command, cwd=str(tmp_path))
    assert held(reason) and "core.fsmonitor" in reason
    principal(reason)
    assert shell(command, cwd=str(tmp_path)) == ""
    assert held(shell(command, cwd=str(tmp_path)))


# --- review round 1 (2026-11-15) ------------------------------------------------------------------------------------
# S1 and S3: git reads the user's own config, the system file and a submodule's; S2: a program posting a request body it
# reads; S4: the local host in any case; git run by the plugin's scanners in folders they are handed; and a write that
# plants a hook the next commit runs.

WRITER = "echo ran > '{state}/marker'"


def _write_program(tmp_path) -> str:
    return str(writer(tmp_path))


@pytest.mark.parametrize("scope", ["GIT_CONFIG_GLOBAL file", "~/.gitconfig", "XDG git config", "system file"])
def test_the_users_and_the_systems_git_config_are_read_too(tmp_path, monkeypatch, scope):
    program, r = _write_program(tmp_path), repo(tmp_path)
    text = f"[core]\n\tfsmonitor = {program}\n"
    if scope == "GIT_CONFIG_GLOBAL file":
        Path(os.environ["GIT_CONFIG_GLOBAL"]).write_text(text, encoding="utf-8")
    elif scope == "~/.gitconfig":
        monkeypatch.delenv("GIT_CONFIG_GLOBAL")
        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        (tmp_path / "home").mkdir()
        (tmp_path / "home" / ".gitconfig").write_text(text, encoding="utf-8")
    elif scope == "XDG git config":
        monkeypatch.delenv("GIT_CONFIG_GLOBAL")
        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))
        (tmp_path / "xdg-config" / "git").mkdir(parents=True)
        (tmp_path / "xdg-config" / "git" / "config").write_text(text, encoding="utf-8")
    else:
        monkeypatch.delenv("GIT_CONFIG_NOSYSTEM")
        monkeypatch.setenv("GIT_CONFIG_SYSTEM", str(tmp_path / "system-gitconfig"))
        (tmp_path / "system-gitconfig").write_text(text, encoding="utf-8")
    assert shell(f"git -C {r} status --porcelain", cwd=str(tmp_path)), scope


def test_a_submodules_config_is_read_when_the_command_reaches_it(tmp_path):
    import subprocess
    sub, parent = repo(tmp_path, "sub"), repo(tmp_path, "parent")
    (sub / "f.txt").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(sub), "add", "f.txt"], check=True)
    subprocess.run(["git", "-C", str(sub), "commit", "-qm", "s"], check=True)
    subprocess.run(["git", "-C", str(parent), "-c", "protocol.file.allow=always", "submodule", "add", "-q", str(sub), "sub"], check=True)
    subprocess.run(["git", "-C", str(parent / "sub"), "config", "core.fsmonitor", _write_program(tmp_path)], check=True)
    assert shell(f"git -C {parent} status --porcelain", cwd=str(tmp_path))
    assert shell(f"git -C {parent} log --oneline -1", cwd=str(tmp_path)) == ""  # a log reaches no submodule


def test_hooks_are_judged_only_for_commands_that_run_them(tmp_path, monkeypatch):
    from synthesis import paths
    own = paths.home() / "git-hooks"  # synthesis's own installed hooks: the commit check's entry points
    own.mkdir(parents=True)
    (own / "pre-commit").write_text(f"#!/bin/sh\necho checked > '{paths.state()}/commit-check'\n", encoding="utf-8")
    (own / "pre-commit").chmod(0o755)
    Path(os.environ["GIT_CONFIG_GLOBAL"]).write_text(f"[user]\n\temail = t@example.com\n\tname = t\n[core]\n\thooksPath = {own}\n"
                                                    "[credential]\n\thelper = osxkeychain\n", encoding="utf-8")
    r = repo(tmp_path)
    for command in ("status --porcelain", "log --oneline -1", "diff", "commit -qm x", "fetch origin", "branch --show-current"):
        assert shell(f"git -C {r} {command}", cwd=str(tmp_path)) == "", command  # the principal's own setup needs nothing
    other = tmp_path / "other-hooks"
    other.mkdir()
    (other / "pre-commit").write_text(f"#!/bin/sh\n{WRITER.format(state=paths.state())}\n", encoding="utf-8")
    (other / "pre-commit").chmod(0o755)
    hooked = repo(tmp_path, "hooked", core__hooksPath=str(other))
    assert shell(f"git -C {hooked} status --porcelain", cwd=str(tmp_path)) == ""  # status runs no pre-commit
    assert shell(f"git -C {hooked} commit -qm x", cwd=str(tmp_path))
    helper = repo(tmp_path, "helper", credential__helper="!" + WRITER.format(state=paths.state()))
    assert shell(f"git -C {helper} status", cwd=str(tmp_path)) == "" and shell(f"git -C {helper} fetch origin", cwd=str(tmp_path))


SEND_BODY = rpc("send_gmail_message", MAIL)
READ_BODY = rpc("search_gmail_messages", {"user_google_email": "principal@example.com", "query": "from:me"})
POSTER = "import urllib.request as u, sys; u.urlopen(u.Request('http://localhost:8765/mcp', data=open(sys.argv[1], 'rb').read()))"


def test_a_program_posting_a_body_it_reads_is_judged_by_that_body(tmp_path):
    (tmp_path / "send.json").write_text(SEND_BODY, encoding="utf-8")
    (tmp_path / "read.json").write_text(READ_BODY, encoding="utf-8")
    assert held(shell(f"python3 -c {shlex.quote(POSTER)} send.json", cwd=str(tmp_path)))
    assert shell(f"python3 -c {shlex.quote(POSTER)} read.json", cwd=str(tmp_path)) == ""
    stdin = "import sys, urllib.request as u; u.urlopen('http://127.0.0.1:8765/mcp', data=sys.stdin.buffer.read())"
    assert held(shell(f"cat send.json | python3 -c {shlex.quote(stdin)}", cwd=str(tmp_path)))
    named = "import requests\nrequests.post('http://localhost:8765/mcp', data=open('send.json').read())\n"
    assert held(shell("python3 - <<'EOF'\n" + named + "EOF", cwd=str(tmp_path)))
    built = "import os, urllib.request as u; u.urlopen('http://localhost:8765/mcp', data=os.environ['BODY'].encode())"
    assert held(shell(f"python3 -c {shlex.quote(built)}", cwd=str(tmp_path)))  # parts the guard cannot read
    curl = "import subprocess, sys; subprocess.run(['curl', '-s', 'http://localhost:8765/mcp', '-d', open(sys.argv[1]).read()])"
    assert held(shell(f"python3 -c {shlex.quote(curl)} send.json", cwd=str(tmp_path)))  # a curl the program starts
    liveness = "import urllib.request as u; print(u.urlopen('http://localhost:8765/mcp', timeout=5).status)"
    assert shell(f"python3 -c {shlex.quote(liveness)}", cwd=str(tmp_path)) == ""


@pytest.mark.parametrize("host", ["LOCALHOST", "LocalHost", "localhost.", "127.0.0.1.", "LOCALHOST."])
def test_the_local_host_is_read_in_any_case_and_with_its_trailing_dot(host):
    reason = shell(curl(SEND_BODY, f"http://{host}:8765/mcp"))
    assert held(reason) and "send_gmail_message" in reason, host  # judged as the tool, not as a post elsewhere
    assert shell(curl(READ_BODY, f"http://{host}:8765/mcp")) == "", host


CONTEXT_DOCTOR = ROOT / "skills" / "synthesis-context-lifecycle" / "scripts" / "context_doctor.py"
REPO_STATE = ROOT / "skills" / "synthesis-daily-rituals" / "scripts" / "repo_state.py"


def test_the_plugins_scanners_wait_when_a_repository_they_reach_names_a_program(tmp_path):
    corpus = repo(tmp_path, "corpus")
    (corpus / "projects" / "p").mkdir(parents=True)
    (corpus / "projects" / "p" / "CONTEXT.md").write_text("# P\n", encoding="utf-8")
    doctor = f"python3 {CONTEXT_DOCTOR} --project {corpus / 'projects' / 'p'}"
    assert guards.check_outgoing(doctor, CONFIG, str(tmp_path), SESSION) is None and shell(doctor, cwd=str(tmp_path)) == ""
    import subprocess
    subprocess.run(["git", "-C", str(corpus), "config", "core.fsmonitor", "/usr/bin/true"], check=True)  # an ordinary-looking line
    assert held(shell(doctor, cwd=str(tmp_path)))
    assert held(shell(f"python3 {CONTEXT_DOCTOR} --root {corpus}", cwd=str(tmp_path)))
    space = tmp_path / "space"
    (space / ".agents").mkdir(parents=True)
    plain = repo(tmp_path, "plain")
    (space / ".agents" / "repos.yaml").write_text(f"repos:\n  - name: plain\n    path: {plain}\n    ritual_sync: true\n", encoding="utf-8")
    scan = f"python3 {REPO_STATE} --workspace-root {space} --fetch --json"
    assert shell(scan, cwd=str(tmp_path)) == ""
    subprocess.run(["git", "-C", str(plain), "config", "filter.x.clean", "cat"], check=True)
    assert held(shell(scan, cwd=str(tmp_path)))
    assert held(shell(f"python3 {REPO_STATE} --discover {tmp_path} --json", cwd=str(tmp_path)))


@pytest.mark.parametrize("where", [".git/hooks/pre-commit", ".git/hooks/post-checkout", ".githooks/pre-commit", "hooks-folder/pre-commit"])
def test_a_write_that_plants_a_hook_waits_by_the_file_tools_and_the_shell(tmp_path, where):
    r = repo(tmp_path, core__hooksPath=str(tmp_path / "proj" / "hooks-folder")) if where.startswith("hooks-folder") else repo(tmp_path)
    (r / os.path.dirname(where)).mkdir(parents=True, exist_ok=True)
    target = r / where
    body = "#!/bin/sh\necho hello\n"
    for tool, tool_input in (("Write", {"file_path": str(target), "content": body}),
                             ("Edit", {"file_path": str(target), "old_string": "a", "new_string": "b"}),
                             ("apply_patch", {"input": f"*** Begin Patch\n*** Add File: {target}\n+echo hi\n*** End Patch\n"})):
        assert held(guards.check(tool, tool_input, CONFIG, cwd=str(r), session=SESSION) or ""), (tool, where)
    for command in (f"cat > {where} <<'EOF'\n{body}EOF", f"printf 'echo hi\\n' > {where}", f"cp /dev/null {where}", f"tee {where} < /dev/null"):
        assert held(shell(command, cwd=str(r))), (command, where)


def test_pointing_git_at_a_hooks_folder_waits_and_ordinary_writes_pass(tmp_path):
    from synthesis import paths
    r = repo(tmp_path)
    assert held(shell(f"git -C {r} config core.hooksPath {tmp_path / 'mine'}", cwd=str(tmp_path)))
    assert held(shell(f"git -C {r} config --local core.hookspath .hooks", cwd=str(tmp_path)))
    assert shell(f"git -C {r} config core.hooksPath {paths.home() / 'git-hooks'}", cwd=str(tmp_path)) == ""  # synthesis's own
    assert shell(f"git -C {r} config user.email a@example.com", cwd=str(tmp_path)) == ""
    assert guards.check("Write", {"file_path": str(r / "src" / "hooks.py"), "content": "x"}, CONFIG, cwd=str(r), session=SESSION) is None
    assert shell("echo x > notes/hooks.md", cwd=str(r)) == ""


def test_the_code_releases_that_hook_write_once(tmp_path, principal):
    r = repo(tmp_path)
    command = "printf 'echo hi\\n' > .git/hooks/pre-commit"
    reason = shell(command, cwd=str(r))
    assert held(reason)
    principal(reason)
    assert shell(command, cwd=str(r)) == ""
    assert held(shell(command, cwd=str(r)))


def test_a_hooks_folder_the_users_config_names_is_judged_not_held_for_a_scan(tmp_path):
    """Found by the round-1 replay: a scanner reaching repositories under a hooks folder the user's own config names (not
    the repository's) waited 115 times; that folder's hooks are judged, and a fast-forward runs only post-merge."""
    hooks = tmp_path / "user-hooks"
    hooks.mkdir()
    (hooks / "pre-commit").write_text("#!/bin/sh\necho checking\n", encoding="utf-8")
    (hooks / "pre-commit").chmod(0o755)
    Path(os.environ["GIT_CONFIG_GLOBAL"]).write_text(f"[user]\n\temail = t@example.com\n\tname = t\n[core]\n\thooksPath = {hooks}\n", encoding="utf-8")
    space, plain = tmp_path / "space", repo(tmp_path, "plain")
    (space / ".agents").mkdir(parents=True)
    (space / ".agents" / "repos.yaml").write_text(f"repos:\n  - name: plain\n    path: {plain}\n    ritual_sync: true\n", encoding="utf-8")
    assert shell(f"python3 {REPO_STATE} --workspace-root {space} --fetch --ff --json", cwd=str(tmp_path)) == ""


# --- review round 2 (2026-11-15) ------------------------------------------------------------------------------------
# T1: ordinary HTTP-client forms; T2: every carried script that runs git in a folder it is handed, and `git config` of
# any key that names a program; T3: a bare repository's hooks folder and a local push's receiving hooks; T4: includes
# named on the command line.

STRAY = ROOT / "skills" / "synthesis-daily-rituals" / "scripts" / "stray_lessons.py"
PR_QUEUE = ROOT / "skills" / "synthesis-daily-rituals" / "scripts" / "pr_queue_scan.py"
PORTFOLIO = ROOT / "skills" / "synthesis-daily-rituals" / "scripts" / "portfolio_review.py"
SHARING = ROOT / "skills" / "synthesis-kb-edit" / "scripts" / "sharing_scan.py"


@pytest.mark.parametrize("line", [
    "http POST :8765/mcp < {body}", "xh POST :8765/mcp < {body}", "https POST :8765/mcp < {body}",
    "U=http://localhost:8765/mcp; curl -s -X POST \"$U\" -d @{body}", "export U=http://127.0.0.1:8765/mcp && curl -s \"$U\" --data-binary @{body}",
    "python3 -c " + shlex.quote("import http.client, sys; c = http.client.HTTPConnection('localhost', 8765); "
                                "c.request('POST', '/mcp', open(sys.argv[1]).read(), {'Content-Type': 'application/json'})") + " {body}",
    "python3 -c " + shlex.quote("import sys, urllib.request as u; host, port = 'localhost', 8765; "
                                "u.urlopen(f'http://{host}:{port}/mcp', data=open(sys.argv[1], 'rb').read())") + " {body}",
    "node -e " + shlex.quote("fetch('http://localhost:8765/mcp', {method: 'POST', headers: {'Content-Type': 'application/json'}, "
                             "body: require('fs').readFileSync(process.argv[1], 'utf8')})") + " {body}",
    "node -e " + shlex.quote("const http = require('http'), fs = require('fs'); const r = http.request({host: 'localhost', port: 8765, "
                             "path: '/mcp', method: 'POST'}); r.end(fs.readFileSync(process.argv[1]))") + " {body}",
    "node -e " + shlex.quote("const axios = require('axios'); axios.post('http://localhost:8765/mcp', require('fs').readFileSync(process.argv[1], 'utf8'))") + " {body}",
    "curl -s -K {cfg}", "curl -s --config {cfg}",
])
def test_ordinary_http_client_forms_that_send_wait(tmp_path, line):
    (tmp_path / "send.json").write_text(SEND_BODY, encoding="utf-8")
    (tmp_path / "read.json").write_text(READ_BODY, encoding="utf-8")
    (tmp_path / "send.cfg").write_text(f'url = "http://localhost:8765/mcp"\nrequest = POST\ndata = "@{tmp_path / "send.json"}"\n', encoding="utf-8")
    (tmp_path / "read.cfg").write_text(f'url = "http://localhost:8765/mcp"\ndata = "@{tmp_path / "read.json"}"\n', encoding="utf-8")
    sent = line.replace("{body}", str(tmp_path / "send.json")).replace("{cfg}", str(tmp_path / "send.cfg"))
    assert held(shell(sent, cwd=str(tmp_path))), sent
    read = line.replace("{body}", str(tmp_path / "read.json")).replace("{cfg}", str(tmp_path / "read.cfg"))
    assert shell(read, cwd=str(tmp_path)) == "", read


def test_a_curl_config_the_guard_cannot_read_waits_and_liveness_forms_pass(tmp_path):
    assert held(shell("curl -s -K missing.cfg", cwd=str(tmp_path)))
    for line in ("http :8765/mcp", "xh GET :8765/mcp", "U=http://localhost:8765/mcp; curl -s \"$U\""):
        assert shell(line, cwd=str(tmp_path)) == "", line


def _fsmonitored(tmp_path, name="kb"):
    import subprocess
    r = repo(tmp_path, name)
    (r / "projects" / "p").mkdir(parents=True)
    (r / "projects" / "index.yaml").write_text("projects:\n  - id: p\n    status: active\n", encoding="utf-8")
    plain_command = lambda: None  # noqa: E731
    return r, lambda: subprocess.run(["git", "-C", str(r), "config", "core.fsmonitor", "/usr/bin/true"], check=True), plain_command


def test_every_carried_script_that_runs_git_in_a_handed_folder_is_a_scanner(tmp_path):
    r, plant, _ = _fsmonitored(tmp_path)
    yaml = tmp_path / "repos.yaml"
    yaml.write_text(f"repos:\n  - name: kb\n    path: {r}\n", encoding="utf-8")
    lines = [f"python3 {STRAY} --since 2026-11-14 --repo {r}", f"python3 {PR_QUEUE} --repos-yaml {yaml} --json",
             f"python3 {SHARING} {r} --staged", f"python3 {PORTFOLIO} --index {r / 'projects' / 'index.yaml'} --json"]
    for line in lines:
        assert shell(line, cwd=str(tmp_path)) == "", line  # a repository that names no program
    plant()
    for line in lines:
        assert held(shell(line, cwd=str(tmp_path))), line
    config = dict(CONFIG, knowledge_roots=[str(r)])  # the doctor given neither option reads the roots its config names
    assert held(guards.check("Bash", {"command": f"python3 {CONTEXT_DOCTOR} --json"}, config, cwd=str(tmp_path), session=SESSION) or "")


@pytest.mark.parametrize("line, waits", [
    ("git config core.fsmonitor /tmp/monitor.sh", True), ("git -c user.name=x config core.pager 'less -R'", True),
    ("git config --global credential.helper '!sh -c x'", True), ("git config alias.x '!sh -c y'", True),
    ("git config diff.tool.textconv cat", True), ("git config --local filter.lfs.clean 'git-lfs clean -- %f'", True),
    ("git config core.fsmonitor true", False), ("git config alias.co checkout", False), ("git config user.email a@example.com", False),
    ("git config --get core.pager", False), ("git config --unset core.fsmonitor", False),
])
def test_git_config_of_a_key_that_names_a_program_waits(tmp_path, line, waits):
    r = repo(tmp_path)
    assert held(shell(line, cwd=str(r))) is waits, line


def test_a_bare_repositorys_hooks_and_a_local_pushs_receiving_hooks(tmp_path):
    import subprocess
    from synthesis import paths
    bare = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
    target = bare / "hooks" / "pre-receive"
    assert held(guards.check("Write", {"file_path": str(target), "content": "#!/bin/sh\n"}, CONFIG, cwd=str(tmp_path), session=SESSION) or "")
    assert held(shell(f"printf 'x' > {target}", cwd=str(tmp_path)))
    target.write_text(f"#!/bin/sh\necho ran > '{paths.state()}/marker'\n", encoding="utf-8")
    target.chmod(0o755)
    r = repo(tmp_path, "work")
    subprocess.run(["git", "-C", str(r), "remote", "add", "origin", str(bare)], check=True)
    subprocess.run(["git", "-C", str(r), "commit", "-q", "--allow-empty", "-m", "one"], check=True)
    assert shell(f"git -C {r} push origin HEAD:main", cwd=str(tmp_path))  # its pre-receive runs
    own = paths.home() / "git-hooks"
    own.mkdir(parents=True)
    Path(os.environ["GIT_CONFIG_GLOBAL"]).write_text(f"[user]\n\temail = t@example.com\n\tname = t\n[core]\n\thooksPath = {own}\n", encoding="utf-8")
    assert shell(f"git -C {r} push origin HEAD:main", cwd=str(tmp_path)) == ""  # the global hooks folder holds no pre-receive


def test_includes_named_on_the_line_are_followed(tmp_path):
    evil = tmp_path / "evil.cfg"
    evil.write_text(f"[core]\n\tfsmonitor = {writer(tmp_path)}\n", encoding="utf-8")
    r = repo(tmp_path)
    for line in (f"git -c include.path={evil} -C {r} status --porcelain", f"git -c includeIf.gitdir:/.path={evil} -C {r} status",
                 f"GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=include.path GIT_CONFIG_VALUE_0={evil} git -C {r} status --porcelain"):
        assert shell(line, cwd=str(tmp_path)), line


# --- review round 3 (2026-11-15) ------------------------------------------------------------------------------------
# A program that names this machine's MCP endpoint (together or apart) and makes any HTTP write is judged by every body
# it hands over that the guard can read, and waits when its body cannot be read; HTTPie's --raw; --config-env includes.

@pytest.mark.parametrize("program", [
    "python3 -c " + shlex.quote("import http.client, sys; c = http.client.HTTPConnection('localhost', 8765); "
                                "c.request('POST', '/mcp', open(sys.argv[1]).read(), {'Content-Type': 'application/json'})") + " {body}",
    "node -e " + shlex.quote("const h=require('http'),f=require('fs');const r=h.request({host:'localhost',port:8765,path:'/mcp',"
                             "method:'POST',headers:{'Content-Type':'application/json'}});r.write(f.readFileSync(process.argv[1]));r.end()") + " {body}",
    "node -e " + shlex.quote("const fs=require('fs');fetch('http://localhost:8765/mcp',{method:'POST',headers:{'Content-Type':'application/json'},"
                             "body:fs.readFileSync(process.argv[1])})") + " {body}",
    "node -e " + shlex.quote("const PORT = 8765;\nconst http = require('http'), fs = require('fs');\n"
                             "const r = http.request({host: 'localhost', port: PORT, path: '/mcp'});\nr.end(fs.readFileSync(process.argv[1]))") + " {body}",
    "python3 -c " + shlex.quote("import sys, urllib.request as u; u.urlopen('http://localhost:8765/mcp', open(sys.argv[1], 'rb').read())") + " {body}",
    "python3 - {body} <<'EOF'\nimport json, sys, urllib.request\nURL = 'http://localhost:8765/mcp'\n"
    "def rpc(method, params):\n    return urllib.request.urlopen(URL, data=json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params}).encode())\n"
    "rpc('tools/call', {'name': 'search_drive_files', 'arguments': {}})\nurllib.request.urlopen(URL, data=open(sys.argv[1], 'rb').read())\nEOF",
])
def test_a_program_writing_to_the_endpoint_is_judged_by_every_body_it_can_read(tmp_path, program):
    (tmp_path / "send.json").write_text(SEND_BODY, encoding="utf-8")
    (tmp_path / "read.json").write_text(READ_BODY, encoding="utf-8")
    assert held(shell(program.replace("{body}", str(tmp_path / "send.json")), cwd=str(tmp_path))), program
    assert shell(program.replace("{body}", str(tmp_path / "read.json")), cwd=str(tmp_path)) == "", program


def test_httpie_raw_bodies_and_the_config_env_include(tmp_path):
    (tmp_path / "send.json").write_text(SEND_BODY, encoding="utf-8")
    assert held(shell(f'http POST :8765/mcp --raw "$(cat {tmp_path / "send.json"})"', cwd=str(tmp_path)))
    assert held(shell('http POST :8765/mcp --raw "$(cat missing.json)"', cwd=str(tmp_path)))  # a body it cannot read
    assert held(shell(f"http POST :8765/mcp --raw={shlex.quote(SEND_BODY)}", cwd=str(tmp_path)))
    evil = tmp_path / "evil.cfg"
    evil.write_text(f"[core]\n\tfsmonitor = {writer(tmp_path)}\n", encoding="utf-8")
    r = repo(tmp_path)
    assert shell(f"P={evil} git --config-env=include.path=P -C {r} status --porcelain", cwd=str(tmp_path))
    assert shell(f"P={evil} git --config-env includeIf.gitdir:/.path=P -C {r} status", cwd=str(tmp_path))
    assert held(shell(f"git --config-env=include.path=NOT_SET_ON_THIS_LINE -C {r} status", cwd=str(tmp_path)))


@pytest.mark.parametrize("program", [  # a GET, a liveness check: no body handed over, so nothing to judge
    "python3 -c " + shlex.quote("import http.client; c = http.client.HTTPConnection('localhost', 8765); c.request('GET', '/mcp'); "
                                "print(c.getresponse().status)"),
    "python3 -c " + shlex.quote("import json, urllib.request; cfg = json.load(open('settings.json')); "
                                "print(urllib.request.urlopen('http://localhost:8765/mcp', timeout=5).status)"),
    "python3 -c " + shlex.quote("import requests; print(requests.get('http://localhost:8765/mcp', timeout=5).status_code)"),
    "node -e " + shlex.quote("fetch('http://localhost:8765/mcp').then(r=>console.log(r.status))"),
    "node -e " + shlex.quote("require('http').get({host:'localhost',port:8765,path:'/mcp'},r=>console.log(r.statusCode))"),
    "node -e " + shlex.quote("const r=require('http').request({host:'localhost',port:8765,path:'/mcp',method:'GET'},"
                             "s=>console.log(s.statusCode));r.end()"),
])
def test_programs_that_only_read_from_the_endpoint_keep_passing(tmp_path, program):
    (tmp_path / "settings.json").write_text("{}", encoding="utf-8")
    assert shell(program, cwd=str(tmp_path)) == "", program


def test_a_body_in_a_variable_the_line_does_not_set_waits_and_one_it_sets_is_read_whole(tmp_path):
    for line in ('curl -s http://localhost:8765/mcp -d "$BODY"', 'curl -s http://localhost:8765/mcp --data-binary $BODY',
                 'wget -qO- --post-data="$BODY" http://localhost:8765/mcp', 'http POST :8765/mcp --raw "$BODY"'):
        assert held(shell(line, cwd=str(tmp_path))), line
    assert shell(f'B={shlex.quote(READ_BODY)}; curl -s http://localhost:8765/mcp -d "$B"', cwd=str(tmp_path)) == ""  # its quotes kept
    assert held(shell(f'B={shlex.quote(SEND_BODY)}; curl -s http://localhost:8765/mcp -d "$B"', cwd=str(tmp_path)))
    quoted = rpc("search_gmail_messages", {"user_google_email": "principal@example.com", "query": "subject:$5 OR $PRICE"})
    assert shell(f"curl -s http://localhost:8765/mcp -d {shlex.quote(quoted)}", cwd=str(tmp_path)) == ""  # a `$` in single quotes is text


@pytest.mark.parametrize("program", [
    RPC + "rpc('tools/call', {'name': 'search_drive_files', 'arguments': {}})\n"
    "urllib.request.urlopen(URL, data=os.environ['BODY'].encode())\n",                         # a readable call beside one it cannot read
    RPC + "body = {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'search_drive_files', 'arguments': {}}}\n"
    "body['params']['name'] = os.environ['TOOL']\nurllib.request.urlopen(URL, data=json.dumps(body).encode())\n",  # one it changes in place
    RPC + "TOOLS = ['search_drive_files']\nTOOLS.append(os.environ['TOOL'])\n"
    "for tool in TOOLS:\n    rpc('tools/call', {'name': tool, 'arguments': {}})\n",
    RPC + "rpc(os.environ['METHOD'], {'name': 'search_drive_files', 'arguments': {}})\n",    # a method it cannot read
])
def test_a_program_waits_when_any_body_it_hands_over_cannot_be_read(tmp_path, program):
    assert held(shell("python3 - <<'EOF'\nimport os\n" + program + "EOF", cwd=str(tmp_path))), program


@pytest.mark.parametrize("program", [
    "import os, sys; os.system('curl -s http://localhost:8765/mcp -d @' + sys.argv[1])",
    "import subprocess, sys; subprocess.run('curl -s -X POST http://localhost:8765/mcp --data-binary @{body}', shell=True)",
    "import urllib.request as u; print(u.urlopen('http://localhost:8765/mcp', data={send!r}.encode()).read())",
    "import urllib.request as u; u.urlopen('http://localhost:8765/mcp', data=b'{send_bytes}')",
    "import json, urllib.request as u; M = 'tools/call'; T = 'send_gmail_message'\n"
    "u.urlopen('http://localhost:8765/mcp', data=json.dumps({{'jsonrpc': '2.0', 'id': 1, 'method': M, 'params': {{'name': T, 'arguments': {{}}}}}}).encode())",
])
def test_programs_that_start_clients_print_replies_or_spell_bodies_are_judged(tmp_path, program):
    (tmp_path / "send.json").write_text(SEND_BODY, encoding="utf-8")
    code = program.format(body=tmp_path / "send.json", send=SEND_BODY, send_bytes=SEND_BODY.replace("'", "\\'"))
    assert held(shell(f"python3 -c {shlex.quote(code)} {tmp_path / 'send.json'}", cwd=str(tmp_path))), program


NODE_RPC = ("const fs = require('fs');\nconst URL = 'http://localhost:8765/mcp';\n"
            "async function rpc(method, params) {\n  return fetch(URL, {method: 'POST', headers: {'Content-Type': 'application/json'},\n"
            "    body: JSON.stringify({jsonrpc: '2.0', id: 1, method, params})});\n}\n")


def test_a_node_helper_is_read_through_its_calls(tmp_path):
    reading = NODE_RPC + "rpc('initialize', {});\nrpc('tools/call', {name: 'search_drive_files', arguments: {}});\n"
    assert shell("node - <<'EOF'\n" + reading + "EOF", cwd=str(tmp_path)) == ""
    named = NODE_RPC + "const TOOL = 'send_gmail_message';\nrpc('tools/call', {name: 'search_drive_files', arguments: {}});\n" \
                       "rpc('tools/call', {name: TOOL, arguments: {}});\n"
    assert held(shell("node - <<'EOF'\n" + named + "EOF", cwd=str(tmp_path)))  # a name a constant gives is read
    built = NODE_RPC + "rpc('tools/call', {name: process.env.TOOL, arguments: {}});\n"
    assert held(shell("node - <<'EOF'\n" + built + "EOF", cwd=str(tmp_path)))
    changed = ("const body = {jsonrpc: '2.0', id: 1, method: 'tools/call', params: {name: 'search_drive_files', arguments: {}}};\n"
               "body.params.name = process.env.TOOL;\nfetch('http://localhost:8765/mcp', {method: 'POST', body: JSON.stringify(body)});\n")
    assert held(shell("node - <<'EOF'\n" + changed + "EOF", cwd=str(tmp_path)))  # a request it changes in place


def test_a_program_a_line_variable_names_is_read_and_its_filled_in_arguments_name_no_tool(tmp_path):
    """From the round's replay: the line's variables now reach a program's own path, so a client run as `"$C"` is read; a
    JSON argument that holds what a substitution gives cannot be a tool's name, so a reading tool still passes."""
    query = '"{\\"user_google_email\\": \\"principal@example.com\\", \\"query\\": \\"modifiedTime > \'$D\'\\"}"'
    assert shell(f'C={CLIENT}; D=$(date +%F); python3 "$C" search_drive_files {query}', cwd=str(tmp_path)) == ""
    assert held(shell(f'C={CLIENT}; D=$(date +%F); python3 "$C" send_gmail_message {query}', cwd=str(tmp_path)))
    assert held(shell(f"C={CLIENT}; T=$(cat tool.txt); python3 \"$C\" \"$T\" '{{}}'", cwd=str(tmp_path)))  # a name it fills in
    poster = tmp_path / "poster.py"
    poster.write_text(POSTER.replace("open(sys.argv[1], 'rb').read()", repr(SEND_BODY.encode())), encoding="utf-8")
    assert held(shell(f'P={poster}; python3 "$P"', cwd=str(tmp_path)))  # a program the line's variable names


def test_a_program_the_line_hands_the_endpoint_is_judged_by_its_bodies(tmp_path):
    """From the round's replay: a program whose own text names no endpoint is handed it by the line, in its arguments or
    in a variable the line sets, and its bodies are judged as when its text names it."""
    (tmp_path / "send.json").write_text(SEND_BODY, encoding="utf-8")
    (tmp_path / "read.json").write_text(READ_BODY, encoding="utf-8")
    (tmp_path / "post.py").write_text("import sys, urllib.request as u\nu.urlopen(sys.argv[1], data=open(sys.argv[2], 'rb').read())\n", encoding="utf-8")
    (tmp_path / "post_env.py").write_text("import os, sys, urllib.request as u\nu.urlopen(os.environ['URL'], data=open(sys.argv[1], 'rb').read())\n",
                                          encoding="utf-8")
    for body, waits in (("send.json", True), ("read.json", False)):
        for line in (f"python3 post.py http://localhost:8765/mcp {body}", f"URL=http://127.0.0.1:8765/mcp python3 post_env.py {body}"):
            assert held(shell(line, cwd=str(tmp_path))) is waits, line


# --- round 3's ruling (2026-11-15): a request whose target comes from the environment --------------------------------------
# A Python or node program whose request target comes from a variable an earlier command exported, with a body the guard
# cannot read, waits for the code, as curl to such an address does; readable bodies that are no send pass, and so do GETs.

@pytest.mark.parametrize("program", [
    "python3 -c " + shlex.quote("import os, sys, urllib.request as u; u.urlopen(os.environ['MCP_URL'], data=sys.stdin.buffer.read())"),
    "python3 -c " + shlex.quote("import os, requests; URL = os.environ.get('MCP_URL', ''); requests.post(URL, data=os.environ['BODY'])"),
    "python3 -c " + shlex.quote("import os, http.client; c = http.client.HTTPConnection(os.environ['MCP_HOST']); c.request('POST', '/rpc', os.environ['BODY'])"),
    "python3 -c " + shlex.quote("import os, urllib.request as u; u.urlopen(f\"{os.environ['BASE']}/rpc\", data=os.environ['BODY'].encode())"),
    "node -e " + shlex.quote("fetch(process.env.MCP_URL, {method: 'POST', body: process.env.BODY})"),
    "node -e " + shlex.quote("const r = require('http').request({host: process.env.MCP_HOST, method: 'POST'}); r.end(process.env.BODY)"),
])
def test_a_request_to_an_address_the_environment_gives_waits_when_its_body_cannot_be_read(tmp_path, program):
    assert held(shell(program, cwd=str(tmp_path))), program


def test_an_environment_address_with_bodies_it_reads_is_judged_by_them_and_reads_pass(tmp_path):
    (tmp_path / "send.json").write_text(SEND_BODY, encoding="utf-8")
    (tmp_path / "read.json").write_text(READ_BODY, encoding="utf-8")
    poster = "import os, sys, urllib.request as u; u.urlopen(os.environ['MCP_URL'], data=open(sys.argv[1], 'rb').read())"
    assert held(shell(f"python3 -c {shlex.quote(poster)} send.json", cwd=str(tmp_path)))
    assert shell(f"python3 -c {shlex.quote(poster)} read.json", cwd=str(tmp_path)) == ""
    (tmp_path / "post.py").write_text("import sys, urllib.request as u\nu.urlopen(sys.argv[1], data=open(sys.argv[2], 'rb').read())\n", encoding="utf-8")
    assert held(shell('python3 post.py "$MCP_URL" send.json', cwd=str(tmp_path)))  # an argument the shell fills in
    assert shell('python3 post.py "$MCP_URL" read.json', cwd=str(tmp_path)) == ""
    assert held(shell('python3 post.py "$MCP_URL" missing.json', cwd=str(tmp_path)))
    for line in ("python3 -c " + shlex.quote("import os, urllib.request as u; u.urlopen(os.environ['API_URL'], data=b'{\"name\": \"x\"}')"),
                 "python3 -c " + shlex.quote("import os, urllib.request as u; print(u.urlopen(os.environ['MCP_URL'], timeout=5).status)"),
                 "python3 -c " + shlex.quote("import os, requests; print(requests.get(os.environ['MCP_URL'], timeout=5).status_code)"),
                 "node -e " + shlex.quote("fetch(process.env.MCP_URL).then(r => console.log(r.status))"),
                 "MCP_URL=https://api.example.com/v1 python3 -c " + shlex.quote(
                     "import os, urllib.request as u; u.urlopen(os.environ['MCP_URL'], data=os.environ['BODY'].encode())"),  # the line gives it
                 "python3 -c " + shlex.quote("import os, requests; requests.post('https://api.example.com/v1/items', data=os.environ['BODY'])")):
        assert shell(line, cwd=str(tmp_path)) == "", line


def test_only_an_address_the_shell_fills_in_counts_as_one_a_body_or_header_does_not(tmp_path):
    """curl's rule reads the address: a body, a header or an HTTPie field the shell fills in, to an address spelled for
    another host, is that host's post (the web rule judges it), not a call on this machine's server."""
    for line in ('curl -s -X POST https://api.example.com/v1/items -d "$BODY"',
                 'curl -s -X POST https://api.example.com/v1/items -H "Authorization: Bearer $TOKEN" -d "$BODY"',
                 'http POST https://api.example.com/v1/items "Authorization:Bearer $TOKEN" body="$BODY"'):
        assert "local MCP server" not in shell(line, cwd=str(tmp_path)), line
    for line in ('curl -s -X POST "$SERVICE_URL/items" -d "$BODY"', 'curl -s -X POST --url "$SERVICE_URL" -d "$BODY"'):
        assert "local MCP server" in shell(line, cwd=str(tmp_path)), line


def test_a_program_whose_values_multiply_is_read_quickly_and_waits_past_what_it_counts(tmp_path):
    """From the ruling's replay: a recorded program whose body names multiplied through its assignments took over a
    minute; each value is now counted once, at most KINDS of them, and a string past the text limit is one it cannot
    read."""
    import time
    branching = "import os, urllib.request as u\nc = os.environ.get('C')\nn0 = 'a'\n" + "".join(
        f"n{i} = n{i - 1} + 'x' if c else n{i - 1} + 'y'\n" for i in range(1, 41)) + "u.urlopen(os.environ['MCP_URL'], data=n40.encode())\n"
    doubling = "import os, urllib.request as u\nn0 = 'ab'\n" + "".join(f"n{i} = n{i - 1} + n{i - 1}\n" for i in range(1, 41)) + \
        "u.urlopen(os.environ['MCP_URL'], data=n40.encode())\n"
    for program in (branching, doubling):
        began = time.monotonic()
        assert held(shell("python3 - <<'EOF'\n" + program + "EOF", cwd=str(tmp_path)))
        assert time.monotonic() - began < 5


# --- from the ruling's suite on a fresh clone (2026-11-15): an address is its host, and a file a program opens is no request
# Five of the plugin's own scripts waited when run for their help or a dry run: `os.open(path, flags, mode)` read as an
# opener's `open(url, data)`, and the Drive publisher's request to the host it spells, with a query from the environment,
# read as an address the environment gives. An address whose scheme and host the program or the line spells, for a host
# other than this machine, goes to that host whatever is filled in after them; a client a program starts with values it
# cannot read is judged with them standing as words the shell fills in, as a line it hands a shell is.

OWN_SCRIPTS = [(script, rest) for script in ("skills/synthesis-onboarding/scripts/setup.py", "skills/synthesis-onboarding/scripts/workspace.py",
                                             "skills/synthesis-local-model-runtime/scripts/local_model_runtime.py", "synthesis/commit_check.py")
               for rest in ("", "--help", "--dry-run")] + [("skills/synthesis-kb-distribution/scripts/publish_drive.py", rest) for rest in (
                   "--help", "--dry-run --tree build")]


@pytest.mark.parametrize("script,rest", OWN_SCRIPTS)
def test_the_plugins_own_scripts_that_open_files_or_post_to_a_host_they_spell_run_without_a_code(tmp_path, script, rest):
    assert shell(f"python3 {shlex.quote(str(ROOT / script))} {rest}".strip(), cwd=str(tmp_path)) == "", (script, rest)


SPELLED_OR_OPENED = {
    "a file it opens": "import os, sys, subprocess; fd = os.open(os.environ['OUT'], os.O_WRONLY | os.O_CREAT, 0o600); os.write(fd, sys.stdin.buffer.read())",
    "a host it spells, a query the environment fills in": "import os, sys, urllib.request as u; "
                                                          "u.urlopen(f\"https://api.example.com/v1/items?folder={os.environ['FOLDER']}\", data=sys.stdin.buffer.read())",
    "a helper handed the host it spells": "import os, sys, urllib.request as u\nAPI = 'https://api.example.com/v1'\n"
                                          "def call(url, body):\n    return u.urlopen(u.Request(url, data=body, method='POST'))\n"
                                          "call(API + '/items/' + os.environ['ID'], sys.stdin.buffer.read())\n",
    "a connection to a host it spells, a path from the environment": "import os, sys, http.client\nc = http.client.HTTPSConnection('api.example.com')\n"
                                                                     "c.request('POST', '/v1/' + os.environ['ID'], sys.stdin.buffer.read())\n",
    "a client it starts for a host it spells": "import os, subprocess; subprocess.run(['curl', '-X', 'POST', "
                                               "f\"https://api.example.com/v1/{os.environ['ID']}\", '-d', os.environ['BODY']])",
}


@pytest.mark.parametrize("name", sorted(SPELLED_OR_OPENED))
def test_a_host_the_program_spells_or_a_file_it_opens_is_no_address_the_environment_gives(tmp_path, name):
    assert shell("python3 - <<'EOF'\n" + SPELLED_OR_OPENED[name] + "\nEOF", cwd=str(tmp_path)) == "", name


def test_a_host_spelled_on_the_line_or_in_nodes_text_is_that_hosts_too(tmp_path):
    poster = "import sys, urllib.request as u; u.urlopen(sys.argv[1], data=sys.stdin.buffer.read())"
    for line in ("python3 -c " + shlex.quote(poster) + ' "https://api.example.com/v1/$ID"',
                 "node -e " + shlex.quote("fetch(`https://api.example.com/v1/${process.env.ID}`, {method: 'POST', body: process.env.BODY})"),
                 "node -e " + shlex.quote("const API = 'https://api.example.com/v1'; fetch(API + '/items/' + process.env.ID, {method: 'POST', body: process.env.BODY})")):
        assert shell(line, cwd=str(tmp_path)) == "", line
    assert "local MCP server" not in shell('curl -s -X POST "https://api.example.com/v1/items/$ID" -d @body.json', cwd=str(tmp_path))


@pytest.mark.parametrize("program", [
    "python3 -c " + shlex.quote("import os, sys, urllib.request as u; opener = u.build_opener(); opener.open(os.environ['MCP_URL'], sys.stdin.buffer.read())"),
    "python3 -c " + shlex.quote("import os, sys, urllib.request as u; u.urlopen(f\"http://localhost:{os.environ['PORT']}/rpc\", data=sys.stdin.buffer.read())"),
    "python3 -c " + shlex.quote("import os, sys, urllib.request as u; u.urlopen(f\"https://api.example.com{os.environ['REST']}\", data=sys.stdin.buffer.read())"),
    "python3 -c " + shlex.quote("import os, sys, urllib.request as u; u.urlopen('https://api.example.com:' + '87' + '65/' + os.environ['P'], data=sys.stdin.buffer.read())"),
    "python3 -c " + shlex.quote("import os, subprocess; subprocess.run(['curl', '-X', 'POST', os.environ['MCP_URL'], '-d', os.environ['BODY']])"),
    "python3 -c " + shlex.quote("import os, sys, subprocess; b = sys.stdin.read(); subprocess.run(['curl', '-X', 'POST', os.environ['MCP_URL'], '-d', b])"),
    "node -e " + shlex.quote("fetch(`http://localhost:${process.env.PORT}/rpc`, {method: 'POST', body: process.env.BODY})"),
    'curl -s -X POST "http://localhost:$PORT/rpc" -d "$BODY"',
])
def test_an_address_the_environment_can_still_aim_at_this_machine_waits(tmp_path, program):
    """A local host with its port filled in, a host left open to what follows, the server's port on a spelled name (one
    that resolves here reaches it), an opener's open, and a client started for an address the environment gives."""
    assert held(shell(program, cwd=str(tmp_path))), program


# --- review round 4 of 22.17 (2026-11-16): on the open list -----------------------------------------------------------------
# The reviewer's probe: a body the program builds while it runs, its JSON-RPC method joined from 'tools/' and 'call',
# posted to an address an earlier command exported. Spelled whole, the method makes the same program wait.

SPLIT_METHOD = ("import json, os, urllib.request as u; b = json.dumps({'method': 'tools/' + 'call'}).encode(); "
                "u.urlopen(u.Request(os.environ['PROBE_TARGET'], data=b))")


def test_a_tool_call_built_with_its_method_spelled_whole_waits(tmp_path):
    program = SPLIT_METHOD.replace("'tools/' + 'call'", "'tools/call'")
    assert held(shell("python3 -c " + shlex.quote(program), cwd=str(tmp_path)))


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="open list (docs/runtime-integration.md, What remains open): a "
                   "body built while the program runs, its JSON-RPC method split across literals, sent to a target from the "
                   "environment, reads as a request the program builds with no tool call (review round 4 of 22.17; crafted)")
def test_a_tool_call_whose_method_is_split_across_literals_waits(tmp_path):
    assert held(shell("python3 -c " + shlex.quote(SPLIT_METHOD), cwd=str(tmp_path)))

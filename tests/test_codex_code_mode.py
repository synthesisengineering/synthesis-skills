"""Codex code mode (the investigation of 2026-11-15; board request 22.33).

In code mode Codex records nearly every call as one `exec` script: JavaScript run in a V8 isolate with no file system,
network or process of its own. Each tool the script calls on its global `tools` object reaches the PreToolUse hook as a
call of its own, under that tool's name, and is judged there; the records show refusals of such nested calls. So the
guard lets the script itself through on purpose and never reads its JavaScript as a shell line, while a command line
sent under the same tool name is still judged as one. The doctor proves from Codex's own records that nested calls
still reach the hook, and the browser page tracker reads the browser calls a script makes.

Every case is invented: nothing here runs a command, a script, a browser step or a send; each only asks the guard or
the doctor about a record or a call.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from synthesis import doctor, guards, hook, paths

CONFIG = json.loads((Path(__file__).resolve().parents[1] / "skills" / "synthesis-message-guard" / "config.example.json")
                    .read_text(encoding="utf-8"))
LOCAL = "http://localhost:3000/"


def script(command: str) -> str:
    """A code-mode script in the shape Codex records: its first-line pragma, then a nested shell call."""
    return ('// @exec: {"yield_time_ms": 10000}\n'
            f"const r = await tools.exec_command({{cmd: {json.dumps(command)}, login: false}});\ntext(r);\n")


def protected() -> str:
    """A file in this test's synthesis state folder, where the guard refuses every write."""
    return str(paths.state() / "approvals" / "x")


def row(kind: str, payload: dict, at: str = "2026-11-15T10:00:01Z") -> dict:
    return {"timestamp": at, "type": kind, "payload": payload}


def meta(version: str = "0.169.0-alpha.11.1", at: str = "2026-11-15T10:00:00Z") -> dict:
    return row("session_meta", {"id": "thread-1", "cli_version": version, "originator": "Codex Desktop"}, at)


def exec_call(call_id: str, text: str, at: str = "2026-11-15T10:00:01Z", name: str = "exec") -> dict:
    return row("response_item", {"type": "custom_tool_call", "id": "ctc_" + call_id, "status": "completed",
                                 "call_id": call_id, "name": name, "input": text}, at)


def output(call_id: str, text: str, at: str = "2026-11-15T10:00:03Z") -> dict:
    return row("response_item", {"type": "custom_tool_call_output", "id": "out_" + call_id, "call_id": call_id,
                                 "output": [{"type": "input_text", "text": text}]}, at)


def nested(item_id: str, server: str, tool: str, arguments: dict, text: str, at: str = "2026-11-15T10:00:02Z") -> dict:
    """Codex's record of a call a script made: an `item_completed` event, never a call record of its own."""
    return row("event_msg", {"type": "item_completed", "thread_id": "thread-1", "turn_id": "turn-1", "item": {
        "type": "McpToolCall", "id": item_id, "server": server, "tool": tool, "arguments": arguments,
        "result": {"content": [{"type": "text", "text": text}], "isError": False}, "status": "completed"}}, at)


def rollout(*rows: dict, name: str = "rollout-2026-11-15T10-00-00-0001.jsonl", mtime: float | None = None) -> Path:
    """A Codex record in this test's Codex sessions folder."""
    folder = paths.transcript_roots()["codex"] / "2026" / "11" / "15"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


REFUSED = ("Command blocked by PreToolUse hook: Refused: this command writes into the synthesis state folder. "
           "Command: echo hi > x")


# --- the script itself --------------------------------------------------------------------------------------------

@pytest.mark.parametrize("shape", ["bare", "input", "code"])
def test_a_code_mode_script_passes_on_purpose_in_each_shape_no_shell_tool_sends(shape):
    text = script(f"echo hi > {protected()}") + script("rm -rf ~")
    assert guards.check("exec", text if shape == "bare" else {shape: text}, {}) is None


def test_the_bare_string_shape_reaches_the_guard_and_passes_without_crashing_it(tmp_path):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        hook.pre_tool_use({"session_id": "S-code", "cwd": str(tmp_path), "tool_name": "exec", "tool_input": script("ls")})
    assert out.getvalue() == "", out.getvalue()


def test_a_script_under_command_passes_when_codexs_record_shows_this_very_call_is_its_exec_tool():
    text = script(f"echo hi > {protected()}")  # read as a shell line, its path text would be refused
    path = rollout(meta(), exec_call("call_A", text))
    assert guards.check("exec", {"command": text}, {}, session={"session_id": "S-code", "transcript_path": str(path),
                                                               "tool_use_id": "call_A"}) is None


@pytest.mark.parametrize("given", [
    {"command": "rm -rf ~"}, {"cmd": ["rm", "-rf", str(Path.home())]}, {"command": ["bash", "-lc", "rm -rf ~"]},
    "rm -rf ~", {"input": "rm -rf ~"}, {"code": "rm -rf ~"},
])
def test_a_command_line_under_the_exec_name_is_still_judged_as_one(given):
    assert guards.check("exec", given, {}) is not None, given


def test_a_script_shaped_command_line_is_judged_as_one_unless_codex_recorded_this_very_call(tmp_path):
    """How the text looks never decides under `command`, where a shell's command line also arrives: a command line can
    be written to look like a script. Only Codex's own record of this call, by its id, in its sessions folder, does."""
    text = script(f"echo hi > {protected()}")
    earlier = rollout(meta(), exec_call("call_old", text))  # the same text, recorded for another call
    elsewhere = tmp_path / "rollout-copy.jsonl"
    elsewhere.write_text(json.dumps(exec_call("call_new", text)) + "\n", encoding="utf-8")  # outside Codex's folder
    for session in ({"session_id": "S"}, {"session_id": "S", "transcript_path": str(earlier), "tool_use_id": "call_new"},
                    {"session_id": "S", "transcript_path": str(elsewhere), "tool_use_id": "call_new"}):
        assert guards.check("exec", {"command": text}, {}, session=session) is not None, session
    disguised = f"tools.exec_command() {{ echo hi > {protected()}; }}; tools.exec_command"  # a shell function, named as a call
    assert guards.check("exec", {"command": disguised}, {}) is not None


# What each helper the guard counts as a sign does, by Codex's own description of its `exec` tool (the records'
# `additional_tools`; the same in all 101 recorded from 2026-09-16 to 2026-11-15): each works inside Codex, on the
# script's own result, its session's store or its run. None reaches a person, a service, a file or a process; a remote
# image or audio URL is refused (the Codex binaries' own messages: "remote image URLs are not supported; use an inline data
# URL instead", "audio URLs must use an inline data URL").
HELPERS = {
    "text": "appends a text item to the script's result",
    "image": "appends an image item: an inline data URL or an MCP image block",
    "audio": "appends an audio item: an inline data URL",
    "generatedImage": "appends an image-generation result; HTTP(S) URLs are not supported",
    "store": "keeps a value for later exec calls in the same session",
    "load": "returns a value kept in the same session",
    "notify": "injects an extra output into the current exec call's own result",
    "exit": "ends the script",
    "yield_control": "hands the output so far to the model while the script keeps running",
}


def test_the_helpers_counted_as_signs_are_the_ones_codex_documents_as_working_inside_it():
    named = re.search(r"\(\?:([\w|]+)\)\\s\*\\\(", guards.CODE_MODE_SIGN.pattern).group(1).split("|")
    assert sorted(named) == sorted(HELPERS)


@pytest.mark.parametrize("text", ["process.exit(0)", "page.text(1)", "client.load(x)", "self.tools.exec_command(x)", "fetch(url)",
                                  "console.log(1)"])
def test_a_helper_is_a_sign_only_called_as_the_global_codex_documents(text):
    assert not guards.code_mode_script("exec", {"input": text}), text


def test_a_recorded_call_whose_text_differs_is_judged_as_a_command_line():
    path = rollout(meta(), exec_call("call_B", script("ls")))
    text = script(f"echo hi > {protected()}")
    assert guards.check("exec", {"command": text}, {}, session={"session_id": "S", "transcript_path": str(path),
                                                               "tool_use_id": "call_B"}) is not None


# --- the browser calls a script makes -----------------------------------------------------------------------------

def page(url: str) -> str:
    return f"### Page state\n- Page URL: {url}\n- Page Title: Local app\n"


def test_the_record_of_a_nested_mcp_call_is_read_under_the_name_codexs_hook_gives_it():
    line = json.dumps(nested("mcp_9", "codex_apps", "github.fetch", {"id": 1}, "fetched"))
    assert guards._line_events(line) == [("call", "mcp_9", "mcp__codex_apps__github__fetch", {"id": 1}),
                                         ("result", "mcp_9", "", "fetched")]
    line = json.dumps(nested("mcp_8", "workspace-mcp", "get_events", {}, "none"))
    assert guards._line_events(line)[0][2] == "mcp__workspace_mcp__get_events"


@pytest.mark.parametrize("server, navigate, key", [
    ("playwright", "browser_navigate", "mcp__playwright__browser_press_key"),
    ("chrome-devtools", "navigate_page", "mcp__chrome_devtools__press_key"),
])
def test_a_browser_call_made_inside_a_code_mode_script_places_the_page(server, navigate, key):
    path = rollout(meta(), exec_call("call_E", f"await tools.mcp__{server.replace('-', '_')}__{navigate}({{url: '{LOCAL}'}});"),
                   nested("mcp_1", server, navigate, {"url": LOCAL}, page(LOCAL)), output("call_E", "done"))
    session = {"session_id": "S-code", "transcript_path": str(path)}
    assert guards._driver_page(guards._driver_events(str(path), key.rpartition("__")[0])) == LOCAL
    reason = guards.check(key, {"key": "Enter"}, CONFIG, session=session) or ""
    assert "approve" not in reason, reason  # Enter on the principal's own local page, which the record now shows


def test_a_direct_call_recorded_twice_counts_once():
    """A direct MCP call is recorded as its call, its output and an `item_completed` event with the call's id."""
    rows = [row("response_item", {"type": "function_call", "name": "mcp__playwright__browser_navigate",
                                  "arguments": json.dumps({"url": LOCAL}), "call_id": "call_D"}),
            row("response_item", {"type": "function_call_output", "call_id": "call_D", "output": page(LOCAL)}),
            nested("call_D", "playwright", "browser_navigate", {"url": LOCAL}, page(LOCAL))]
    path = rollout(meta(), *rows)
    calls = [e for e in guards._driver_events(str(path), "mcp__playwright") if e[0] == "call"]
    assert len(calls) == 1, calls


# --- the doctor's proof that nested calls reach the hook ------------------------------------------------------------

def test_no_codex_record_is_no_line():
    assert doctor.check_codex_nested_hooks(paths.codex_home()) is None
    rollout(meta(), row("response_item", {"type": "function_call", "name": "exec_command", "arguments": "{}", "call_id": "c1"}))
    assert doctor.check_codex_nested_hooks(paths.codex_home()) is None  # no code-mode script, so nothing nested to prove


def test_a_refusal_inside_a_script_proves_that_this_codex_runs_hooks_on_nested_calls():
    """One hook's refusal in a script's result proves that this Codex version runs hooks on nested calls, and the line says
    that much and no more: not that every nested call is hooked, nor that this guard refused (review round 2 of 22.33)."""
    rollout(meta(), exec_call("call_1", script("ls")), output("call_1", REFUSED, at="2026-11-14T09:30:00Z"))
    check = doctor.check_codex_nested_hooks(paths.codex_home())
    assert check.status == "ok" and check.name == "codex nested hooks", check
    assert check.detail == ("Codex 0.169.0-alpha.11.1 runs PreToolUse hooks on calls made inside a code-mode script: a hook "
                            "refused one in a script's result on 2026-11-14, in its newest rollout"), check.detail


@pytest.mark.parametrize("rows", [
    [exec_call("call_1", script("ls")), output("call_1", "plain output")],                     # no refusal at all
    [exec_call("call_1", "*** Begin Patch", name="apply_patch"), output("call_1", REFUSED)],  # a direct tool's refusal
    [exec_call("call_1", script("ls")), output("call_2", REFUSED)],                           # another call's output
])
def test_without_a_refusal_inside_a_script_the_doctor_warns_and_says_what_is_unproven(rows):
    rollout(meta(), exec_call("call_0", script("ls")), *rows)
    check = doctor.check_codex_nested_hooks(paths.codex_home())
    assert check.status == "warn" and "unproven" in check.detail, check


def test_a_proof_from_an_older_codex_does_not_cover_a_newer_one():
    rollout(meta("0.167.0-alpha.4.1"), exec_call("call_1", script("ls")), output("call_1", REFUSED),
            name="rollout-2026-11-14T10-00-00-0001.jsonl", mtime=1_800_000_000)
    rollout(meta("0.169.0-alpha.11.1"), exec_call("call_2", script("ls")), output("call_2", "plain"),
            name="rollout-2026-11-15T10-00-00-0002.jsonl", mtime=1_800_000_600)
    check = doctor.check_codex_nested_hooks(paths.codex_home())
    assert check.status == "warn" and "0.167.0-alpha.4.1" in check.detail and "0.169.0-alpha.11.1" in check.detail, check


def test_records_that_cannot_be_listed_warn_rather_than_stop_the_doctor(monkeypatch):
    paths.transcript_roots()["codex"].mkdir(parents=True, exist_ok=True)

    def refused(self, pattern):
        raise PermissionError(13, "Permission denied")
    monkeypatch.setattr(Path, "rglob", refused)
    check = doctor.check_codex_nested_hooks(paths.codex_home())
    assert check.status == "warn" and "could not be listed" in check.detail, check


def test_a_link_named_as_a_rollout_is_never_followed(tmp_path):
    """Only a regular file is read (review round 1 of 22.33): a link may lead outside Codex's folder, or to a FIFO."""
    elsewhere = tmp_path / "elsewhere.jsonl"
    elsewhere.write_text("".join(json.dumps(r) + "\n" for r in (meta(), exec_call("call_1", script("ls")), output("call_1", REFUSED))),
                         encoding="utf-8")
    folder = paths.transcript_roots()["codex"] / "2026" / "11" / "15"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "rollout-2026-11-15T10-00-00-0005.jsonl").symlink_to(elsewhere)
    (folder / "rollout-2026-11-15T10-00-00-0009.jsonl").symlink_to(tmp_path / "gone.jsonl")  # a link to nothing
    assert doctor.check_codex_nested_hooks(paths.codex_home()) is None  # nothing regular was read: nothing to prove


def test_a_fifo_named_as_a_rollout_is_never_opened():
    """A FIFO with a rollout's name held the doctor until a writer came (review round 1 of 22.33): a doctor that hangs
    never reports. The check runs in a process of its own here, so a hang fails the test instead of holding the run."""
    folder = paths.transcript_roots()["codex"] / "2026" / "11" / "15"
    folder.mkdir(parents=True, exist_ok=True)
    rollout(meta(), exec_call("call_1", script("ls")), output("call_1", REFUSED), name="rollout-2026-11-15T10-00-00-0008.jsonl",
            mtime=os.stat(folder).st_mtime - 60)  # older than the FIFO, so the newest-first reading meets the FIFO first
    os.mkfifo(folder / "rollout-2026-11-15T10-00-00-0007.jsonl")
    code = "from synthesis import doctor, paths; c = doctor.check_codex_nested_hooks(paths.codex_home()); print(c.status if c else 'none')"
    try:
        done = subprocess.run([sys.executable, "-c", code], cwd=str(Path(__file__).resolve().parents[1]), capture_output=True,
                              text=True, timeout=15)
    except subprocess.TimeoutExpired:
        pytest.fail("the doctor opened a FIFO named as a rollout and waited for a writer")
    assert done.stdout.strip() == "ok", done.stderr[-400:]


def test_the_first_line_is_read_only_as_far_as_its_bound():
    """A rollout's first line (its session record, about 20 KB) is read within a bound: a line with no end is not read whole."""
    path = rollout(name="rollout-2026-11-15T10-00-00-0006.jsonl")
    path.write_bytes(b"x" * (4 << 20))  # 4 MB and no line break
    version, scripts, when, read = doctor._nested_proof(path, 1 << 20)
    assert read < 4 << 20 and (version, scripts, when) == ("", False, ""), read


def test_the_doctor_reads_only_the_newest_rollouts_it_allows_itself():
    rollout(meta(), exec_call("call_1", script("ls")), output("call_1", REFUSED),
            name="rollout-2026-11-14T10-00-00-0001.jsonl", mtime=1_800_000_000)
    rollout(meta(), exec_call("call_2", script("ls")), output("call_2", "plain"),
            name="rollout-2026-11-15T10-00-00-0002.jsonl", mtime=1_800_000_600)
    assert doctor.check_codex_nested_hooks(paths.codex_home(), files=1).status == "warn"
    assert doctor.check_codex_nested_hooks(paths.codex_home(), files=2).status == "ok"

"""5.23.0, from round 3 of the batch review (finding 8): two ways to send that no guard read.

Words typed into a Messenger box with the browser tool, then Return pressed through `osascript` (System Events
`key code 36`), went out with no code: the shell guard knew no key events. And the Playwright plugin's browser tools
reached no rule, since only servers named for a browser or Chrome were read, and only their computer, batch, form and
script tools. Now a shell command that presses keys or clicks in whatever app is in front, or that sends or runs code
through another app, waits for the principal's code for that exact command; and a browser tool from any server is read
as the steps it performs, on the page it is on. Sixty days of Claude Code and Codex records (2026-11-15) held no
message sent either way: no osascript Return, and Playwright pressed Tab twice, on local pages.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from synthesis import guards, sends

CONFIG = json.loads((Path(__file__).resolve().parents[1] / "skills" / "synthesis-message-guard" / "config.example.json")
                    .read_text(encoding="utf-8"))
SESSION = {"session_id": "S-principal"}
PRESS = "osascript -e 'tell application \"System Events\" to key code 36'"


def shell(command: str, cwd: str = "/tmp", session: dict = SESSION) -> str:
    return guards.check("Bash", {"command": command}, CONFIG, cwd=cwd, session=session) or ""


def held(reason: str) -> bool:
    return "approve" in reason


# --- the shell -------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("command", [
    PRESS,                                                                                      # the finding: Return
    "osascript -e 'tell application \"System Events\" to keystroke return'",
    "osascript -e 'tell application \"System Events\" to keystroke \"On my way\"'",             # words into whatever box has the focus
    "osascript -e 'tell application \"System Events\"' -e 'key code 76' -e 'end tell'",           # keypad Enter, across -e lines
    "osascript -e 'tell application \"System Events\"\n  tell process \"Google Chrome\" to click button \"Send\" of window 1\nend tell'",
    "osascript -e 'tell application \"System Events\" to perform action \"AXPress\" of button 1 of window 1 of process \"Messages\"'",
    "osascript -e 'tell application id \"com.apple.systemevents\" to key code 36'",
    "osascript -e 'tell application \"system events\" to key code 36'",                          # an app's name in any case
    "osascript -e 'tell application \"System Events\" to «event prcskcod» 36'",                   # a verb by its raw code
    "o''sascript -e 'tell application \"System Events\" to key code 36'",                         # the shell takes the quotes out
    "/usr/bin/osascript -e 'tell application \"System Events\" to key code 36'",
    "env LANG=C osascript -e 'tell application \"System Events\" to key code 36'",
    "bash -c \"osascript -e 'tell application \\\"System Events\\\" to key code 36'\"",
    "echo done && osascript -e 'tell application \"System Events\" to key code 36'",
    "watch -n 1 \"osascript -e 'tell application \\\"System Events\\\" to key code 36'\"",
    "osascript -l JavaScript -e 'Application(\"System Events\").keyCode(36)'",
    "osascript -l JavaScript -e 'Application(\"com.apple.systemevents\").keystroke(\"x\")'",
    "osascript -l JavaScript -e 'var n = \"System \" + \"Events\"; Application(n)[\"key\" + \"Code\"](36)'",  # an app named at run time
    "cliclick kp:return", "cliclick t:hello", "cliclick c:100,200",
    "xdotool key Return", "xdotool type hello", "xdotool click 1",
    "hs -c 'hs.eventtap.keyStroke({}, \"return\")'",
    "skhd -k return",
    "shortcuts run 'Send Message'",
    "automator send.workflow",
    "python3 -c 'import pyautogui; pyautogui.press(\"enter\")'",
    "python3 -c 'import Quartz; Quartz.CGEventPost(0, Quartz.CGEventCreateKeyboardEvent(None, 36, True))'",
    "python3 -c 'import subprocess; subprocess.run([\"osascript\", \"-e\", \"tell application \\\"System Events\\\" to key code 36\"])'",
    "python3 -c 'import os; os.system(\"cliclick kp:return\")'",
    "swift -e 'import CoreGraphics; CGEvent(keyboardEventSource: nil, virtualKey: 36, keyDown: true)?.post(tap: .cghidEventTap)'",
])
def test_a_command_that_presses_keys_or_clicks_waits_for_the_code(command):
    reason = shell(command)
    assert held(reason) and "whatever app is in front" in reason, command


@pytest.mark.parametrize("command, what", [
    ("osascript -e 'tell application \"Messages\"\n  send \"On my way\" to buddy \"+15550100\"\nend tell'", "posts to messages"),  # across lines
    ("osascript -e 'tell application \"Microsoft Outlook\" to send (make new outgoing message with properties {subject:\"x\"})'", "posts to email"),
    ("osascript -l JavaScript -e 'Application(\"Messages\").send(\"On my way\", {to: Application(\"Messages\").buddies[0]})'", "posts to messages"),
    ("osascript -e 'tell application \"Terminal\" to do script \"ls\"'", "another app"),
    ("osascript -e 'tell application \"iTerm2\" to tell current session of current window to write text \"ls\"'", "another app"),
    ("osascript -e 'tell application \"Google Chrome\" to execute active tab of front window javascript \"document.title\"'", "another app"),
    ("osascript -e 'tell application \"Safari\" to do JavaScript \"1\" in document 1'", "another app"),
    ("osascript -e 'tell application \"Keyboard Maestro Engine\" to do script \"Send\"'", "another app"),
    ("osascript -e 'tell application \"Shortcuts Events\" to run shortcut \"Send Message\"'", "another app"),
    ("osascript -e 'do shell script \"ls\"'", "cannot read"),
    ("osascript -e 'run script \"1 + 1\"'", "cannot read"),
    ("osascript -e 'use framework \"Foundation\"' -e 'current application'\"'\"'s NSAppleScript'\"'\"'s alloc()'", "cannot read"),
    ("osascript -l JavaScript -e 'ObjC.import(\"stdlib\"); $.system(\"ls\")'", "cannot read"),
    ("osascript -l JavaScript -e 'eval(\"1\")'", "cannot read"),
])
def test_a_script_that_sends_or_runs_code_through_another_app_waits(command, what):
    reason = shell(command)
    assert held(reason) and what in reason, (command, reason)


@pytest.mark.parametrize("command", [
    "osascript -e 'tell application \"Mail\" to get name of every mailbox'",
    "osascript -e 'tell application \"Mail\" to move (messages of inbox whose read status is true) to mailbox \"Archive\"'",
    "osascript -e 'display notification \"3 items wait\" with title \"synthesis\"'",
    "osascript -e 'tell application \"Google Chrome\" to get URL of active tab of front window'",
    "osascript -e 'tell application \"Messages\" to get name of every chat'",
    "osascript -e 'tell application \"Notes\" to get body of note 1'",
    "osascript -l JavaScript -e 'Application(\"Contacts\").people().length'",
    "osascript -l JavaScript -e 'var app = Application(\"Notes\"); app.notes()[0].name()'",
    "osascript -l JavaScript -e 'ObjC.import(\"Foundation\"); $.NSString.alloc.initWithUTF8String(\"x\").js'",
    "cliclick p", "xdotool getmouselocation", "shortcuts list", "skhd --reload",
    "python3 -c 'print(1)'",
    "grep -rn 'key code 36' docs/",
    "echo \"osascript -e 'tell application System Events to key code 36'\"",                     # printed, not run
    "python3 - <<'EOF'\nimport re\nprint(bool(re.search(r'osascript .* key code 36', 'x')))\nEOF",  # analysis that runs nothing
])
def test_reading_notifying_and_analysis_need_no_code(command):
    assert shell(command) == "", command


def test_a_script_on_its_input_or_in_a_file_is_read(tmp_path):
    assert held(shell("osascript <<'EOF'\ntell application \"System Events\" to key code 36\nEOF"))
    assert held(shell("echo 'tell application \"System Events\" to key code 36' | osascript"))
    script = tmp_path / "press.applescript"
    script.write_text('tell application "System Events" to key code 36\n', encoding="utf-8")
    assert held(shell(f"osascript {script}"))
    quiet = tmp_path / "count.applescript"
    quiet.write_text('tell application "Mail" to count messages of inbox\n', encoding="utf-8")
    assert shell(f"osascript {quiet}") == ""
    compiled = tmp_path / "press.scpt"  # a compiled script is not text: what it does cannot be read
    compiled.write_bytes(b"FasdUAS 1.101.10\x0e\x00\x00\x00\x04\x0f\xff\xff\x00\x01")
    assert held(shell(f"osascript {compiled}"))
    jxa = tmp_path / "press.js"
    jxa.write_text('Application("System Events").keyCode(36)\n', encoding="utf-8")
    assert held(shell(f"osascript -l JavaScript {jxa}"))
    sh = tmp_path / "press.sh"
    sh.write_text("#!/bin/sh\n" + PRESS + "\n", encoding="utf-8")
    assert held(shell(f"sh {sh}")) and held(shell(str(sh)))
    py = tmp_path / "press.py"
    py.write_text("import pyautogui\npyautogui.press('enter')\n", encoding="utf-8")
    assert held(shell(f"python3 {py}"))


@pytest.mark.parametrize("command, waits", [
    # Found by running the reading over 60 days of recorded commands (2026-11-15): a backtick in a Python string is no
    # shell call, an AppleScript-looking string counts only in a program that runs osascript, and `-l JavaScript`
    # takes its value, so a script piped to it is read.
    ("python3 - <<'EOF'\nimport re\nPAT = re.compile(r'`?Application(\"Messages\")`? and send')\nEOF", False),
    ("python3 -c 'import subprocess; subprocess.run([\"git\", \"status\"]); doc = \"tell application \\\"Messages\\\" to send\"'", False),
    ("cat <<'EOF' | osascript -l JavaScript\nApplication(\"Contacts\").people().length\nEOF", False),
    ("cat <<'EOF' | osascript -l JavaScript\nApplication(\"System Events\").keyCode(36)\nEOF", True),
    ("osascript -l JavaScript <<'EOF'\nApplication(\"System Events\").keyCode(36)\nEOF", True),
    ("osascript -e 'tell application \"System Events\" to (name of processes) contains \"Mail\"'", False),  # which apps run
    ("osascript -e 'tell application \"System Events\" to tell process \"Messages\" to set value of text field 1 of window 1 to \"hi\"'", True),
])
def test_what_the_recorded_commands_showed(command, waits):
    assert held(shell(command)) is waits, command


def test_the_code_lets_that_one_command_run_once_and_the_ledger_says_so(principal):
    reason = shell(PRESS)
    assert held(reason)
    principal(reason)
    assert shell(PRESS) == ""
    assert sends.ledger(__import__("time").strftime("%Y-%m-%d"))[-1]["channel"] == "desktop"
    assert held(shell(PRESS))  # one code, one run
    assert held(shell("osascript -e 'tell application \"System Events\" to keystroke return'"))  # another command, its own


def test_words_a_command_types_pass_the_register_scan_first():
    reason = shell("osascript -e 'tell application \"System Events\" to keystroke \"Sorry for the delay, here it is\"'")
    assert "delay-apology" in reason and "can't go out as written" in reason


def test_a_text_sent_through_messages_keeps_its_words_for_the_scans():
    reason = shell("osascript -e 'tell application \"Messages\"\n  send \"Sorry for the delay\" to buddy \"+15550100\"\nend tell'")
    assert "delay-apology" in reason


# --- browser tools from any server -----------------------------------------------------------------------------------

PW = "mcp__plugin_playwright_playwright__"
MESSENGER, LOCAL = "https://www.messenger.com/t/1234567890/", "http://localhost:3000/"
SNAPSHOT = ('- generic [ref=e1]:\n  - textbox "Message" [active] [ref=e12]\n'
            '  - button "Press enter to send" [ref=e45] [cursor=pointer]\n  - button "Search" [ref=e3]')


def _call(ident: str, tool: str, tool_input: dict, text: str) -> str:
    call = {"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "tool_use", "id": ident, "name": tool, "input": tool_input}]}}
    result = {"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": ident, "content": [{"type": "text", "text": text}]}]}}
    return json.dumps(call) + "\n" + json.dumps(result) + "\n"


def _page(url: str, snapshot: str = SNAPSHOT) -> str:
    return (f"### Ran Playwright code\n```js\nawait page.goto('{url}');\n```\n### Page\n- Page URL: {url}\n"
            f"- Page Title: Chats\n### Snapshot\n```yaml\n{snapshot}\n```")


def _on(tmp_path, url: str | None, *more: str) -> dict:
    """A session whose newest Playwright result shows the page at url (none at all when url is None)."""
    path = tmp_path / "transcript.jsonl"
    lines = [_call("toolu_pw1", PW + "browser_navigate", {"url": url}, _page(url))] if url else []
    path.write_text("".join(lines + list(more)), encoding="utf-8")
    return {**SESSION, "transcript_path": str(path)}


def driven(tool: str, tool_input: dict, session: dict) -> str:
    return guards.check(tool, tool_input, CONFIG, session=session) or ""


ENTER = (PW + "browser_press_key", {"key": "Enter"})
SUBMIT = (PW + "browser_type", {"element": "Message box", "ref": "e12", "text": "On my way", "submit": True})


@pytest.mark.parametrize("tool, tool_input", [
    ENTER, SUBMIT,
    (PW + "browser_press_key", {"key": "Control+Enter"}),
    (PW + "browser_click", {"element": "the blue icon at the bottom", "ref": "e45"}),         # its snapshot says it sends
    (PW + "browser_click", {"element": "a button", "ref": "e99"}),                              # a control the record does not show
    (PW + "browser_run_code_unsafe", {"code": "async (page) => { await page.keyboard.press('Enter'); }"}),
    (PW + "browser_run_code_unsafe", {"code": "async (page) => { await page.getByRole('button').click(); }"}),
    (PW + "browser_evaluate", {"function": "() => document.querySelector('[aria-label=Send]').click()"}),
    (PW + "browser_fill_form", {"fields": [{"name": "Message", "type": "textbox", "ref": "e12", "value": "On my way\n"}]}),
])
def test_a_playwright_step_that_can_send_on_a_messaging_page_waits(tmp_path, tool, tool_input):
    reason = driven(tool, tool_input, _on(tmp_path, MESSENGER))
    assert held(reason) and "sends in the browser (" in reason, (tool, tool_input, reason)


@pytest.mark.parametrize("tool, tool_input", [
    (PW + "browser_type", {"element": "Message box", "ref": "e12", "text": "On my way"}),      # typing sends nothing
    (PW + "browser_click", {"element": "Search", "ref": "e3"}),
    (PW + "browser_evaluate", {"function": "() => document.title"}),
    (PW + "browser_snapshot", {}),
    (PW + "browser_take_screenshot", {"type": "png"}),
    (PW + "browser_press_key", {"key": "Shift+Enter"}),                                         # a line break in the box
])
def test_reading_and_typing_on_a_messaging_page_need_no_code(tmp_path, tool, tool_input):
    assert driven(tool, tool_input, _on(tmp_path, MESSENGER)) == "", (tool, tool_input)


@pytest.mark.parametrize("tool, tool_input", [
    ENTER, SUBMIT,
    (PW + "browser_click", {"element": "Save", "ref": "e3"}),
    (PW + "browser_run_code_unsafe", {"code": "async (page) => { await page.keyboard.press('Enter'); }"}),
])
def test_the_same_steps_on_the_principals_own_app_on_a_local_host_pass(tmp_path, tool, tool_input):
    assert driven(tool, tool_input, _on(tmp_path, LOCAL)) == "", (tool, tool_input)


def test_a_click_that_says_it_sends_waits_on_any_page(tmp_path):
    reason = driven(PW + "browser_click", {"element": "Send button", "ref": "e7"}, _on(tmp_path, "https://www.example.com/contact"))
    assert held(reason)


def test_a_page_the_record_does_not_show_holds_a_step_that_may_send(tmp_path):
    session = _on(tmp_path, None)
    for tool, tool_input in (ENTER, SUBMIT, (PW + "browser_click", {"element": "Done", "ref": "e2"})):
        reason = driven(tool, tool_input, session)
        assert held(reason) and "does not show" in reason, tool
    assert driven(PW + "browser_snapshot", {}, session) == ""
    assert driven(PW + "browser_navigate", {"url": MESSENGER}, session) == ""


def test_the_chrome_extensions_tab_list_is_not_playwrights_page(tmp_path):
    """Each browser is placed by its own results: a messaging page open in Chrome leaves Playwright's local page local."""
    chrome = _call("toolu_c1", "mcp__claude-in-chrome__computer", {}, (
        'Clicked\n\nTab Context:\n- Executed on tabId: 7\n- Available tabs:\n  • tabId 7: "Chats" ("' + MESSENGER + '")'))
    assert driven(*ENTER, _on(tmp_path, LOCAL, chrome)) == ""


def test_the_newest_page_is_the_one_a_later_step_moved_to(tmp_path):
    moved = _call("toolu_pw2", PW + "browser_click", {"element": "Chats", "ref": "e9"}, _page(MESSENGER))
    assert held(driven(*ENTER, _on(tmp_path, LOCAL, moved)))


def test_a_code_lets_that_one_playwright_step_go_once(principal):
    with principal.transcript.open("a", encoding="utf-8") as record:  # the record the principal types the code into
        record.write(_call("toolu_pw1", PW + "browser_navigate", {"url": MESSENGER}, _page(MESSENGER)))
    session = {**SESSION, "transcript_path": str(principal.transcript)}
    reason = driven(*ENTER, session)
    principal(reason)
    assert driven(*ENTER, session) == ""
    assert sends.ledger(__import__("time").strftime("%Y-%m-%d"))[-1]["channel"] == "browser"
    assert held(driven(*ENTER, session))


@pytest.mark.parametrize("tool, tool_input", [
    ("mcp__chrome-devtools__press_key", {"key": "Enter"}),
    ("mcp__puppeteer__puppeteer_click", {"selector": "button[type=submit]"}),
])
def test_other_browser_servers_are_read_by_what_their_tools_do(tmp_path, tool, tool_input):
    assert held(driven(tool, tool_input, _on(tmp_path, None)))


def test_every_browser_tool_fails_closed_when_the_config_cannot_be_read():
    assert guards.guarded(PW + "browser_type") and guards.guarded("mcp__chrome-devtools__press_key")
    assert not guards.guarded("mcp__memory__read_graph")

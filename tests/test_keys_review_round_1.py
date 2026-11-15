"""5.23.0: review round 1 of the reading of keys, clicks and other apps, and of browser tools from any server.

The reviewer's probes (2026-11-15, filed in the project as returned), each case as the reviewer wrote it: commands and
browser calls that still sent with no code, and ordinary work the first version held. Every case here is invented; none
presses a key, clicks, sends or drives a browser: each only asks the guard about a call.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from synthesis import guards

CONFIG = json.loads((Path(__file__).resolve().parents[1] / "skills" / "synthesis-message-guard" / "config.example.json")
                    .read_text(encoding="utf-8"))
SESSION = {"session_id": "S-probe"}
PRESS = 'tell application "System Events" to key code 36'
PW = "mcp__plugin_playwright_playwright__"
MESSENGER, LOCAL = "https://www.messenger.com/t/1234567890/", "http://localhost:3000/"
SNAPSHOT = ('- generic [ref=e1]:\n  - textbox "Message" [active] [ref=e12]\n'
            '  - button "Press enter to send" [ref=e45] [cursor=pointer]\n  - button "Search" [ref=e3]')


def held(reason: str) -> bool:
    return "approve" in reason


def folder(files: dict | None = None) -> Path:
    """A fresh working folder holding these files (text written as given, carriage returns kept)."""
    where = Path(tempfile.mkdtemp(prefix="keys-cwd-"))
    for name, text in (files or {}).items():
        target = where / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(text, bytes):
            target.write_bytes(text)
        else:
            with open(target, "w", encoding="utf-8", newline="") as handle:
                handle.write(text)
    return where


def shell(command: str, files: dict | None = None, where: Path | None = None) -> str:
    where = where or folder(files)
    return guards.check("Bash", {"command": command}, CONFIG, cwd=str(where), session=SESSION) or ""


def call(ident: str, tool: str, tool_input: dict, text: str) -> str:
    use = {"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "tool_use", "id": ident, "name": tool, "input": tool_input}]}}
    result = {"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": ident, "content": [{"type": "text", "text": text}]}]}}
    return json.dumps(use) + "\n" + json.dumps(result) + "\n"


def page(url: str, snapshot: str = SNAPSHOT) -> str:
    return (f"### Ran Playwright code\n```js\nawait page.goto('{url}');\n```\n### Page state\n- Page URL: {url}\n"
            f"- Page Title: Chats\n- Page Snapshot:\n```yaml\n{snapshot}\n```")


def on(*lines: str) -> dict:
    path = folder() / "transcript.jsonl"
    path.write_text("".join(lines), encoding="utf-8")
    return {**SESSION, "transcript_path": str(path)}


def at(url: str, snapshot: str = SNAPSHOT) -> str:
    return call("toolu_nav", PW + "browser_navigate", {"url": url}, page(url, snapshot))


def browse(tool: str, tool_input: dict, session: dict) -> str:
    return guards.check(tool, tool_input, CONFIG, session=session) or ""




# --- driven_approval_binding ---------------------------------------------------------------------------------------

TWO_BOXES = ('- generic [ref=e1]:\n  - textbox "Message" [ref=e12]\n  - button "Press enter to send" [ref=e45] [cursor=pointer]\n'
             '  - textbox "Message" [ref=e70]\n  - button "Press enter to send" [ref=e77] [cursor=pointer]')


@pytest.mark.parametrize("field", ["target", "ref"])
def test_the_code_for_one_send_button_is_not_spent_on_another(principal, field):
    with principal.transcript.open("a", encoding="utf-8") as record:
        record.write(at(MESSENGER, TWO_BOXES))
    session = {"session_id": "S-principal", "transcript_path": str(principal.transcript)}
    reason = browse(PW + "browser_click", {"element": "Send in the first chat", field: "e45"}, session)
    assert held(reason)
    principal(reason)
    other = browse(PW + "browser_click", {"element": "Send in the second chat", field: "e77"}, session)
    assert held(other), (field, "the code for e45 let a click on e77 through")


def test_the_code_for_words_sent_in_one_box_is_not_spent_in_another(principal):
    with principal.transcript.open("a", encoding="utf-8") as record:
        record.write(at(MESSENGER, TWO_BOXES))
    session = {"session_id": "S-principal", "transcript_path": str(principal.transcript)}
    approved = {"element": "Message", "target": "e12", "text": "On my way", "submit": True}
    reason = browse(PW + "browser_type", approved, session)
    assert held(reason)
    principal(reason)
    other = browse(PW + "browser_type", {**approved, "target": "e70"}, session)
    assert held(other), "the code for box e12 let the same words go to box e70"


# --- driven_keys_and_controls --------------------------------------------------------------------------------------

UNNAMED = ('- generic [ref=e1]:\n  - textbox "Message" [active] [ref=e12]\n  - button [ref=e46] [cursor=pointer]:\n'
           '    - img [ref=e47]')


@pytest.mark.parametrize("key", ["\n", "\r"])
def test_a_line_break_character_pressed_on_messenger_waits(key):
    reason = browse(PW + "browser_press_key", {"key": key}, on(at(MESSENGER)))
    assert held(reason), (repr(key), reason)


@pytest.mark.parametrize("field", ["ref", "target"])
def test_an_unnamed_control_clicked_on_messenger_waits(field):
    reason = browse(PW + "browser_click", {"element": "Send button", field: "e46"}, on(at(MESSENGER, UNNAMED)))
    assert held(reason), (field, reason)


def test_the_agents_send_words_still_count_when_the_snapshot_names_no_control():
    reason = browse(PW + "browser_click", {"element": "Send button", "ref": "e46"}, on(at("https://www.example.com/contact", UNNAMED)))
    assert held(reason), reason


def test_a_ref_is_named_only_by_the_current_pages_snapshot():
    """B5, second part: the ref is looked up in the newest result that prints it, from any page. Here the newest
    Messenger snapshot does not print e45 (a partial or changed snapshot), so the local page's e45, a Search
    button, names the click on Messenger, and it passes."""
    local = call("toolu_nav1", PW + "browser_navigate", {"url": LOCAL}, page(LOCAL, '- generic [ref=e1]:\n  - button "Search" [ref=e45]'))
    chat = call("toolu_nav2", PW + "browser_navigate", {"url": MESSENGER}, page(MESSENGER, '- generic [ref=e1]:\n  - textbox "Message" [ref=e12]'))
    reason = browse(PW + "browser_click", {"element": "Send", "ref": "e45"}, on(local, chat))
    assert held(reason), reason


def test_control_enter_by_name_waits():
    assert held(browse(PW + "browser_press_key", {"key": "Enter"}, on(at(MESSENGER))))


# --- driven_page_placement -----------------------------------------------------------------------------------------

ENTER = (PW + "browser_press_key", {"key": "Enter"})


def test_a_navigate_that_timed_out_still_moved_the_page():
    timed_out = call("toolu_nav2", PW + "browser_navigate", {"url": MESSENGER},
                     "### Error\nTimeoutError: page.goto: Timeout 30000ms exceeded.\nCall log:\n"
                     f'  - navigating to "{MESSENGER}", waiting until "domcontentloaded"')
    reason = browse(*ENTER, on(at(LOCAL), timed_out))
    assert held(reason), reason


def test_a_tab_selected_from_the_tab_list_moves_the_page():
    tabs = call("toolu_tabs", PW + "browser_tabs", {"action": "select", "index": 1},
                f"### Open tabs\n- 0: [Local]({LOCAL})\n- 1: (current) [Chats]({MESSENGER})\n")
    reason = browse(*ENTER, on(at(LOCAL), tabs))
    assert held(reason), reason


@pytest.mark.parametrize("blank", ["about:blank", "file:///tmp/report.html"])
def test_chromes_tab_list_does_not_place_playwrights_page(blank):
    chrome = call("toolu_c1", "mcp__claude-in-chrome__computer", {}, (
        'Clicked\n\nTab Context:\n- Executed on tabId: 7\n- Available tabs:\n  • tabId 7: "Chats" ("' + MESSENGER + '")'))
    reason = browse(*ENTER, on(chrome, at(blank)))
    assert not held(reason), (blank, reason)


def test_a_codex_record_places_the_page():
    rows = [{"timestamp": "2026-11-15T10:00:00Z", "type": "response_item",
             "payload": {"type": "function_call", "name": "mcp__playwright__browser_navigate",
                         "arguments": json.dumps({"url": LOCAL}), "call_id": "call_1"}},
            {"timestamp": "2026-11-15T10:00:02Z", "type": "response_item",
             "payload": {"type": "function_call_output", "call_id": "call_1", "output": page(LOCAL)}}]
    path = folder() / "rollout.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    reason = browse("mcp__playwright__browser_press_key", {"key": "Enter"}, {"session_id": "S-codex", "transcript_path": str(path)})
    assert not held(reason), reason


def test_a_server_whose_results_print_no_page_line_is_placed_by_its_navigate():
    """Puppeteer's server answers a navigate with "Navigated to <url>", so every click on a local test page waits."""
    nav = call("toolu_pp1", "mcp__puppeteer__puppeteer_navigate", {"url": LOCAL}, f"Navigated to {LOCAL}")
    reason = browse("mcp__puppeteer__puppeteer_click", {"selector": "#save"}, on(nav))
    assert not held(reason), reason


def test_control_the_local_page_shown_last_lets_enter_pass_and_messenger_holds_it():
    assert not held(browse(*ENTER, on(at(LOCAL))))
    assert held(browse(*ENTER, on(at(LOCAL), at(MESSENGER))))


# --- driven_run_code -----------------------------------------------------------------------------------------------

SPAWN = ("async (page) => { const { execSync } = await import('node:child_process'); "
         "execSync(`osascript -e 'tell application \"System Events\" to key code 36'`); }")


@pytest.mark.parametrize("tool_input", [
    {"filename": "press.js"},
    {"code": "async (page) => { return await page.title(); }", "filename": "press.js"},
])
def test_code_loaded_from_a_file_waits_on_a_messaging_page(tool_input):
    reason = browse(PW + "browser_run_code_unsafe", tool_input, on(at(MESSENGER)))
    assert held(reason), (tool_input, reason)


@pytest.mark.parametrize("url", [LOCAL, MESSENGER])
def test_code_that_starts_osascript_in_the_server_process_waits(url):
    reason = browse(PW + "browser_run_code_unsafe", {"code": SPAWN}, on(at(url)))
    assert held(reason), (url, reason)


def test_control_a_page_key_press_in_code_waits_on_messenger():
    """Since 5.23.1 (round 4 of 5.24.0's review, #3) a script on a messaging site's page is refused, not held."""
    code = "async (page) => { await page.keyboard.press('Enter'); }"
    reason = browse(PW + "browser_run_code_unsafe", {"code": code}, on(at(MESSENGER)))
    assert reason and "shipped" in reason and not held(reason), reason


# --- driven_target_field -------------------------------------------------------------------------------------------

PULL = "https://github.com/example/repo/pull/7"


COMMENT_BOX = ('- generic [ref=e1]:\n  - textbox "Leave a comment" [ref=e8]\n  - button "Comment" [ref=e9] [cursor=pointer]\n'
               '  - button "Close pull request" [ref=e10]')


def test_a_neutral_description_of_a_comment_button_waits_by_its_snapshot_name():
    reason = browse(PW + "browser_click", {"element": "the green button", "target": "e9"}, on(at(PULL, COMMENT_BOX)))
    assert held(reason), reason


def test_a_click_through_evaluate_on_that_button_waits():
    reason = browse(PW + "browser_evaluate", {"element": "the green button", "target": "e9", "function": "(el) => el.click()"},
                    on(at(PULL, COMMENT_BOX)))
    assert held(reason), reason


def test_opening_the_search_box_on_messenger_needs_no_code():
    reason = browse(PW + "browser_click", {"element": "Search", "target": "e3"}, on(at(MESSENGER)))
    assert not held(reason), reason


def test_control_the_same_calls_spelled_with_ref_behave_as_the_change_intends():
    assert held(browse(PW + "browser_click", {"element": "the green button", "ref": "e9"}, on(at(PULL, COMMENT_BOX))))
    assert not held(browse(PW + "browser_click", {"element": "Search", "ref": "e3"}, on(at(MESSENGER))))


# --- driven_unknown_tools ------------------------------------------------------------------------------------------

SEND = "div[aria-label='Press enter to send']"


@pytest.mark.parametrize("tool, tool_input", [
    ("mcp__selenium__click_element", {"by": "css", "value": SEND}),
    ("mcp__chrome-mcp-server__chrome_keyboard", {"keys": "Enter"}),
    ("mcp__chrome-mcp-server__chrome_click_element", {"selector": SEND}),
    ("mcp__chrome-mcp-server__chrome_fill_or_select", {"selector": "div[role=textbox]", "value": "On my way\n"}),
    ("mcp__chrome-mcp-server__chrome_inject_script", {"type": "MAIN", "jsScript": f"document.querySelector(\"{SEND}\").click()"}),
    ("mcp__chrome-mcp-server__chrome_network_request", {"url": "https://www.messenger.com/api/graphql/", "method": "POST",
                                                         "body": "message=On%20my%20way"}),
    ("mcp__browserbase__stagehand_act", {"action": "type 'On my way' into the message box and press Enter"}),
])
def test_a_driving_tool_the_mapping_does_not_name_waits_where_the_page_is_unknown(tool, tool_input):
    assert guards.driven_tool(tool), tool  # the change counts the server as one that drives a browser
    reason = browse(tool, tool_input, on())
    assert held(reason), (tool, guards.driven_tool(tool), reason)


def test_control_the_named_tools_of_those_servers_wait():
    assert held(browse("mcp__selenium__press_key", {"key": "Enter"}, on()))
    # send_keys waits too, by the older rule for tools whose name says they send, not by this reading
    assert held(browse("mcp__selenium__send_keys", {"by": "css", "value": "div[role=textbox]", "text": "On my way\n"}, on()))


# --- false_holds_shell ---------------------------------------------------------------------------------------------

def _home_with_notify(monkeypatch):
    home = folder({"bin/notify.applescript": 'display notification "Build done" with title "CI"\n'})
    monkeypatch.setenv("HOME", str(home))
    return home


@pytest.mark.parametrize("command", [
    "python3 - <<'EOF'\nimport re\nprint(bool(re.search(r'pyautogui|CGEventPost', 'x')))\nEOF",
    "python3 -c 'print(\"pyautogui is not installed here\")'",
    "python3 - <<'EOF'\nimport subprocess\nPATTERNS = [\"osascript -e 'tell application \\\"System Events\\\" to key code 36'\"]\n"
    "for p in PATTERNS:\n    subprocess.run([\"rg\", \"-F\", p, \"docs\"])\nEOF",
    "osascript -e 'tell application \"Terminal\" to get name of front window'",
    "osascript -e 'tell application \"iTerm2\" to get name of current session of current window'",
    "osascript -l JavaScript -e 'ObjC.import(\"stdlib\"); $.getenv(\"HOME\")'",
    "osascript -e 'tell application \"Finder\" to select POSIX file \"/tmp\"'",
    "osascript -e 'tell application \"Numbers\" to tell table 1 of sheet 1 of document 1 to set value of cell \"A1\" to 5'",
    "hs -c 'hs.reload()'",
    "say 'shortcuts run finished'",
])
def test_ordinary_work_needs_no_code(command):
    reason = shell(command)
    assert not held(reason), (command, reason)


def test_a_notification_script_under_home_needs_no_code(monkeypatch):
    _home_with_notify(monkeypatch)
    reason = shell('osascript "$HOME/bin/notify.applescript"')
    assert not held(reason), reason


# --- osa_forms -----------------------------------------------------------------------------------------------------

SE = 'Application("System Events")'


MSG_WINDOW = 'processes.byName("Messages").windows[0]'


@pytest.mark.parametrize("script", [
    f'{SE}.{MSG_WINDOW}.buttons.byName("Send").actions.byName("AXPress").perform()',
    f'{SE}.{MSG_WINDOW}.buttons.byName("Send").actions[0].perform()',
    f'var w = {SE}.{MSG_WINDOW}; w.textAreas[0].value = "On my way"; w.textAreas[0].actions.byName("AXConfirm").perform()',
    'ObjC.import("Foundation"); var t = $.NSAppleEventDescriptor.descriptorWithBundleIdentifier("com.apple.systemevents"); '
    'var e = $.NSAppleEventDescriptor.appleEventWithEventClassEventIDTargetDescriptorReturnIDTransactionID(1886544755, 1802531443, t, -1, 0); '
    'e.setParamDescriptorForKeyword($.NSAppleEventDescriptor.descriptorWithString("\\r"), 757935405); '
    'e.sendEventWithOptionsTimeoutError(0, 10, null)',
    'Library("Helpers").pressSend()',  # JavaScript for Automation's way to run a script library
])
def test_a_jxa_script_that_presses_a_control_waits(script):
    reason = shell(f"osascript -l JavaScript -e '{script}'")
    assert held(reason), (script, reason)


@pytest.mark.parametrize("script", [
    'tell application "System Events" to perform (first action of button "Send" of window 1 of process "Messages")',
    'tell application "System Events" to tell action "AXPress" of button "Send" of window 1 of process "Messages" to perform',
    'tell application "System Events" to set the value of text area 1 of scroll area 1 of window 1 of process "Messages" to "On my way"',
    'open location "shortcuts://run-shortcut?name=Send%20Message&input=text&text=On%20my%20way"',
    'tell application "Finder" to open POSIX file "/tmp/press.command"',
    'tell application "Hammerspoon" to execute lua code "hs.eventtap.keyStroke({}, [[return]])"',
    'tell application id "com.runningwithcrayons.Alfred" to run trigger "send" in workflow "com.example.send" with argument "On my way"',
    'tell script "Helpers" to pressSend()',  # a script library run without `use script`, which is held
])
def test_an_applescript_that_presses_or_runs_code_elsewhere_waits(script):
    reason = shell(f"osascript -e '{script}'")
    assert held(reason), (script, reason)


def test_the_forms_the_change_reads_hold():
    """Controls: the same presses in the words OSA_KEYS knows."""
    assert held(shell("osascript -e 'tell application \"System Events\" to perform action \"AXPress\" of button \"Send\" of window 1 of process \"Messages\"'"))
    assert held(shell(f"osascript -l JavaScript -e '{SE}.{MSG_WINDOW}.buttons.byName(\"Send\").click()'"))
    assert held(shell("osascript -e 'tell application \"Shortcuts Events\" to run shortcut \"Send Message\"'"))


# --- osa_lexer -----------------------------------------------------------------------------------------------------

KEYCODE = 'Application("System Events").keyCode(36)'


@pytest.mark.parametrize("name, text, flags", [
    ("press.applescript", '-- set up\rtell application "System Events" to key code 36\r', ""),
    ("press.js", f"// set up\r{KEYCODE}\n", "-l JavaScript "),
    ("press.js", f"// set up\u2028{KEYCODE}\n", "-l JavaScript "),
    ("press.js", 'var se = Application("System Events"); var t = "it\'s on".replace(/\'/g, "’"); se.keystroke(t); se.keyCode(36)\n',
     "-l JavaScript "),
    ("press.js", 'var se = Application("System Events"); var t = \'say "hi"\'.replace(/"/g, ""); se.keystroke(t); se.keyCode(36)\n',
     "-l JavaScript "),
    ("press.js", f"console.log(`pressed: ${{{KEYCODE}}}`)\n", "-l JavaScript "),
    ("press.applescript", 'set |note"| to 1\ntell application "System Events" to key code 36\n', ""),
    ("press.applescript", 'tell application "System Events" to key ¬\ncode 36\n', ""),
])
def test_a_script_the_lexer_mis_splits_still_waits(name, text, flags):
    reason = shell(f"osascript {flags}{name}", {name: text})
    assert held(reason), (text, reason)


def test_the_same_scripts_with_plain_lines_hold():
    """Controls."""
    assert held(shell("osascript press.applescript", {"press.applescript": '-- set up\ntell application "System Events" to key code 36\n'}))
    assert held(shell("osascript -l JavaScript press.js", {"press.js": f"// set up\n{KEYCODE}\n"}))


# --- program_files_not_followed ------------------------------------------------------------------------------------

PRESS_PY = "import pyautogui\npyautogui.press('enter')\n"


COMPILED = b"FasdUAS 1.101.10\x0e\x00\x00\x00\x04\x0f\xff\xff\x00\x01"


@pytest.mark.parametrize("command, files", [
    ("python3 -c 'import subprocess; subprocess.run([\"osascript\", \"press.applescript\"])'", {"press.applescript": PRESS + "\n"}),
    ("python3 -c 'import os; os.system(\"osascript press.applescript\")'", {"press.applescript": PRESS + "\n"}),
    ("python3 -c 'import subprocess; subprocess.run([\"osascript\", \"press.scpt\"])'", {"press.scpt": COMPILED}),
    ("python3 -c 'import subprocess; subprocess.run([\"sh\", \"press.sh\"])'", {"press.sh": f"osascript -e '{PRESS}'\n"}),
    ("python3 -c 'import subprocess; subprocess.run([\"python3\", \"p.py\"])'", {"p.py": PRESS_PY}),
    ("python3 -m press", {"press.py": PRESS_PY}),
    ("python3 -c 'import press'", {"press.py": PRESS_PY}),
    ("python3 run.py", {"run.py": "import helper\nhelper.go()\n",
                        "helper.py": "import pyautogui\n\ndef go():\n    pyautogui.press('enter')\n"}),
])
def test_the_file_a_program_runs_or_imports_is_read(command, files):
    reason = shell(command, files)
    assert held(reason), (command, reason)


def test_the_same_files_run_from_the_shell_hold(tmp_path):
    """Controls: the shell reading finds each of them."""
    assert held(shell("osascript press.applescript", {"press.applescript": PRESS + "\n"}))
    assert held(shell("osascript press.scpt", {"press.scpt": COMPILED}))
    assert held(shell("sh press.sh", {"press.sh": f"osascript -e '{PRESS}'\n"}))
    assert held(shell("python3 press.py", {"press.py": PRESS_PY}))


# --- same_line_writes ----------------------------------------------------------------------------------------------

@pytest.mark.parametrize("old, command", [
    ({"press.applescript": 'tell application "Mail" to count messages of inbox\n'},
     f"cat > press.applescript <<'EOF'\n{PRESS}\nEOF\nosascript press.applescript"),
    ({"p.py": "print('ok')\n"},
     "cat > p.py <<'EOF'\nimport pyautogui\npyautogui.press('enter')\nEOF\npython3 p.py"),
    ({"press.sh": "#!/bin/sh\necho ok\n"},
     f"cat > press.sh <<'EOF'\n#!/bin/sh\nosascript -e '{PRESS}'\nEOF\nsh press.sh"),
])
def test_a_script_rewritten_then_run_on_one_line_waits(old, command):
    reason = shell(command, where=folder(old))
    assert held(reason), (command, reason)


# --- shell_interpreters --------------------------------------------------------------------------------------------

@pytest.mark.parametrize("command, files", [
    ("perl -e 'system \"cliclick\", \"kp:return\"'", {}),
    ("perl -e 'exec \"cliclick\", \"kp:return\"'", {}),
    ("ruby -e 'system \"cliclick\", \"kp:return\"'", {}),
    ("ruby -e '%x(cliclick kp:return)'", {}),
    ("tclsh <<'EOF'\nexec cliclick kp:return\nEOF", {}),
    ("expect -c 'spawn cliclick kp:return'", {}),
    ("python3 -c 'import asyncio; asyncio.run(asyncio.create_subprocess_exec(\"cliclick\", \"kp:return\"))'", {}),
    ("python3 -c 'import sh; sh.cliclick(\"kp:return\")'", {}),
    (f"python3 -c 'import osascript; osascript.run(\"\"\"{PRESS}\"\"\")'", {}),
    (f"python3 -c 'import applescript; applescript.run(\"\"\"{PRESS}\"\"\")'", {}),
    ("node -e 'require(\"@jxa/run\").run(() => Application(\"System Events\").keyCode(36))'", {}),
    (f"node -e 'require(\"applescript\").execString(`{PRESS}`, () => {{}})'", {}),
    ("node -e 'import(\"execa\").then(({execa}) => execa(\"cliclick\", [\"kp:return\"]))'", {}),
    ("node --eval 'require(\"child_process\").execSync(\"cliclick kp:return\")'", {}),
    ("node -p 'require(\"child_process\").execSync(\"cliclick kp:return\")'", {}),
    ("perl -E 'system(\"cliclick kp:return\")'", {}),
    ("deno eval 'new Deno.Command(\"cliclick\", {args: [\"kp:return\"]}).outputSync()'", {}),
    ("deno run -A press.ts", {"press.ts": "new Deno.Command('cliclick', { args: ['kp:return'] }).spawn();\n"}),
    ("php -r 'system(\"cliclick kp:return\");'", {}),
    ("swift -e 'import Foundation; let p = Process(); p.executableURL = URL(fileURLWithPath: \"/opt/homebrew/bin/cliclick\"); "
     "p.arguments = [\"kp:return\"]; try! p.run(); p.waitUntilExit()'", {}),
])
def test_a_program_that_runs_an_input_program_or_osascript_waits(command, files):
    reason = shell(command, files)
    assert held(reason), (command, reason)


def test_the_spellings_the_change_reads_hold():
    """Controls."""
    assert held(shell("perl -e 'system(\"cliclick kp:return\")'"))
    assert held(shell("node -e 'require(\"child_process\").execSync(\"cliclick kp:return\")'"))
    assert held(shell("python3 -c 'import subprocess; subprocess.run([\"cliclick\", \"kp:return\"])'"))


# --- shell_other_runners -------------------------------------------------------------------------------------------

@pytest.mark.parametrize("command, files", [
    ("open ./press.command", {"press.command": f"#!/bin/sh\nosascript -e '{PRESS}'\n"}),
    ("open -a Terminal ./press.sh", {"press.sh": f"#!/bin/sh\nosascript -e '{PRESS}'\n"}),
    ("open 'shortcuts://run-shortcut?name=Send%20Message&input=text&text=On%20my%20way'", {}),
    ("open 'kmtrigger://macro=Send%20Message'", {}),
    ("tmux send-keys -t chat 'On my way' Enter", {}),
    ("screen -S chat -X stuff $'On my way\\n'", {}),
    ("kitty @ send-text --match title:chat $'On my way\\r'", {}),
    ("wezterm cli send-text --no-paste $'On my way\\r'", {}),
    (f"script -q /dev/null osascript -e '{PRESS}'", {}),
    (f"launchctl asuser 501 osascript -e '{PRESS}'", {}),
    (f"arch -arm64 osascript -e '{PRESS}'", {}),
    ("make press", {"Makefile": f"press:\n\tosascript -e '{PRESS}'\n"}),
    ("npm run press", {"package.json": json.dumps({"scripts": {"press": f"osascript -e '{PRESS}'"}})}),
])
def test_another_runner_that_presses_or_runs_code_elsewhere_waits(command, files):
    reason = shell(command, files)
    assert held(reason), (command, reason)


def test_the_change_holds_the_same_effects_through_its_own_doors():
    """Controls: these hold today, so the doors above are the gap."""
    assert held(shell("shortcuts run 'Send Message'"))
    assert held(shell("osascript -e 'tell application \"Terminal\" to do script \"ls\"'"))
    assert held(shell(f"caffeinate osascript -e '{PRESS}'"))


# --- shell_unexpanded_words ----------------------------------------------------------------------------------------

PRESS_PY = "import pyautogui\npyautogui.press('enter')\n"


@pytest.mark.parametrize("command, files", [
    (f"S='{PRESS}'; osascript -e \"$S\"", {}),
    ('osascript -e "$(cat press.applescript)"', {"press.applescript": PRESS + "\n"}),
    ("osascript -e \"$(< press.applescript)\"", {"press.applescript": PRESS + "\n"}),
    (f"printf '%s' '{PRESS}' | xargs -0 osascript -e", {}),
    ('A=kp:return; cliclick "$A"', {}),
    ('python3 -c "$(cat press.py)"', {"press.py": PRESS_PY}),
    (f"O=osascript; $O -e '{PRESS}'", {}),
    (f"\"$(command -v osascript)\" -e '{PRESS}'", {}),
])
def test_a_script_the_shell_fills_in_waits(command, files):
    reason = shell(command, files)
    assert held(reason), (command, reason)


# --- unreadable_line_fallback --------------------------------------------------------------------------------------

DEEP = "x=$(echo $(echo $(echo $(echo $(echo $(echo $(echo $(echo ok))))))))"


@pytest.mark.parametrize("command", [
    f"{DEEP}; osascript -e '{PRESS}'",
])
def test_a_key_press_on_a_line_the_parser_gives_up_on_waits(command):
    reason = shell(command)
    assert held(reason), (command, reason)


def test_control_the_same_press_alone_waits():
    assert held(shell(f"osascript -e '{PRESS}'"))
    assert held(shell(f"{DEEP}; cliclick kp:return"))  # its words survive the split, so it waits

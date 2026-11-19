"""A14, 2026-11-18: a send, an upload, a document edit or a form save made through computer use waits for a code that
names the action, no batch covers a computer-use call, and each such action the principal releases is in the bounded
sends log as other sends are.

That evening a seat working in Codex drove a browser through Codex's computer-use REPL (`mcp__cua_repl__js`: one
JavaScript program a call, with a title that says what it does). The guard knew no such tool. A batch took the REPL call
that sent a chat reply as a connector call, its code was typed, and the reply went with no ledger line and the batch's
entry never spent, since the guard never read the call at all. Earlier the same evening a slide import into a shared
deck, an upload and two form saves had gone through the same tool with no code. Every call here is synthetic, in the
shapes of that evening's calls.
"""

import json
import time
from pathlib import Path

import pytest

from synthesis import guards, paths, sends

CONFIG = json.loads((Path(__file__).resolve().parents[1] / "skills" / "synthesis-message-guard" / "config.example.json")
                    .read_text(encoding="utf-8"))
REPL = "mcp__cua_repl__js"
SESSION = {"session_id": "S-principal"}
SEND = {"code": ("if (!(await chatTab.url()).startsWith('https://chat.example.test/room/AAA')) throw new Error('Unexpected room'); "
                 "await chatTab.playwright.getByRole('textbox',{name:'Message the room',exact:true}).click(); "
                 "await chatTab.paste(null,\"<p>Thanks, Pat. The five slides are in the shared deck.</p><p>🤖 <em>Helperbot "
                 "(helperbot.example)</em></p>\",{format:'html'}); "
                 "await chatTab.playwright.getByRole('button',{name:'Send message',exact:true}).click(); await chatTab.getAXState();"),
        "title": "Sending Helperbot's slide confirmation"}
IMPORT = {"code": "await deckTab.click(29); await deckTab.getAXState();",
          "title": "Copying five source slides into the team's shared deck"}
UPLOAD = {"code": ("let chooser = formTab.playwright.waitForEvent('filechooser',{timeout:10000}); "
                   "await formTab.playwright.getByRole('button',{name:'Upload file(s)',exact:true}).click(); "
                   "await (await chooser).setFiles(['/tmp/receipt.pdf']); await formTab.getAXState();"),
          "title": "Uploading the work receipt"}
SAVE = {"code": "await formTab.playwright.getByRole('button',{name:'Save and close',exact:true}).click(); await formTab.getAXState();",
        "title": "Saving the expense and opening the history"}


def check(call, tool=REPL, config=CONFIG):
    return guards.check(tool, call, config, session=SESSION)


def held(reason) -> bool:
    return bool(reason) and "approve followed by the code" in reason


def today() -> list:
    return sends.ledger(time.strftime("%Y-%m-%d"))


@pytest.mark.parametrize("tool,name", [(REPL, "repl"), ("mcp__cua-repl__js", "repl"), ("mcp__computer-use__js", "repl"),
                                       ("mcp__cua_repl__js_reset", ""), ("mcp__notes__js", ""), ("mcp__cuatro__js", "")])
def test_the_computer_use_repl_is_computer_use(tool, name):
    """Codex names the tool `mcp__cua_repl__js`; a hyphen in its server's name, or a server named for computer use,
    is the same tool. Resetting the REPL does nothing to anyone."""
    assert guards.desktop_tool(tool) == name
    assert guards.guarded(tool, {}) is bool(name)


def test_the_incidents_send_waits_for_a_code_that_names_it_and_is_logged_once_approved(principal):
    reason = check(SEND)
    assert held(reason) and "This call sends" in reason and "Sending Helperbot's slide confirmation" in reason, reason
    principal(reason)
    assert check(SEND) is None
    line = today()[-1]
    assert (line["tool"], line["how"]) == (REPL, "approval") and "Sending Helperbot's slide confirmation" in line["summary"]
    assert held(check(SEND))  # one approval, one send


@pytest.mark.parametrize("call,does", [(IMPORT, "edits a document"), (UPLOAD, "uploads a file"), (SAVE, "saves a form")],
                         ids=["slide-import", "upload", "form-save"])
def test_an_upload_a_document_edit_or_a_form_save_waits_for_its_own_code_and_is_logged(principal, call, does):
    reason = check(call)
    assert held(reason) and f"This call {does}" in reason and call["title"] in reason, reason
    principal(reason)
    assert check(call) is None
    assert today()[-1]["tool"] == REPL and call["title"] in today()[-1]["summary"]


def test_a_code_covers_only_the_call_it_names(principal):
    principal(check(SEND))
    assert held(check(IMPORT)) and held(check(UPLOAD))
    assert check(SEND) is None


@pytest.mark.parametrize("call", [
    {"code": "await deckTab.getAXState();", "title": "Reading the deck"},
    {"code": "await formTab.click(7); await formTab.getAXState();", "title": "Opening the pending expense"},
    {"code": "await formTab.goto('https://expenses.example.test/'); await formTab.getAXState();", "title": "Opening the expense workspace"},
    {"code": "await deckTab.click(12); await deckTab.getAXStateAndScreenshot();", "title": "Staging all five original slides"},
    {"code": "nodeRepl.write(await deckTab.playwright.domSnapshot());", "title": "Saving a view of the slides for the record"},
    {"code": ("await formTab.playwright.getByRole('textbox',{name:'Description',exact:true}).fill('Usage credits for work.'); "
              "await formTab.getAXState();"), "title": "Preparing the expense description"},
    {"code": "const tab = await cua.getTab({url:'https://deck.example.test/d/1'}); await tab.scroll(4, 'down', 2);",
     "title": "Opening the shared deck"},
    {"completion_summary": "Sent the approved reply"},
], ids=["read", "open", "navigate", "stage", "save-a-view", "fill", "bind-and-scroll", "completion"])
def test_reading_navigating_and_ordinary_clicks_need_no_code(call):
    assert check(call) is None


@pytest.mark.parametrize("call,does", [
    ({"code": "await chatTab.playwright.getByRole('button',{name:'Send message'}).click();", "title": "Checking the chat"}, "sends"),
    ({"code": "await feedTab.playwright.getByText('Post').click();", "title": "Finishing the update"}, "sends"),
    ({"code": "await formTab.playwright.getByRole('button',{name:'Save and close'}).click();", "title": "Closing the form"}, "saves a form"),
    ({"code": "await (await formTab.playwright.waitForEvent('filechooser')).setFiles('/tmp/a.pdf');", "title": "Preparing the receipt"},
     "uploads a file"),
    ({"code": "await formTab.playwright.locator('input[type=file]').setInputFiles(['/tmp/a.pdf']);", "title": "Preparing the receipt"},
     "uploads a file"),
], ids=["send-button", "post-text", "save-button", "file-chooser", "file-input"])
def test_a_control_the_code_names_or_a_file_it_sets_waits_whatever_the_title_says(call, does):
    reason = check(call)
    assert held(reason) and f"This call {does}" in reason, reason


@pytest.mark.parametrize("call", [
    {"code": "await chatTab.pressKey(42, 'Return');", "title": "Pressing Return in the box"},
    {"code": "await chatTab.playwright.keyboard.press('Enter');", "title": "Confirming"},
    {"code": "await chatTab.typeText(42, 'On my way.\\n');", "title": "Typing the reply"},
    {"code": "await chatTab.click(5); await chatTab.getAXState();"},
], ids=["return", "enter", "typed-line-break", "click-with-no-title"])
def test_a_return_a_typed_line_break_or_a_click_that_says_nothing_waits(call):
    """The REPL's tabs and apps are bound in earlier calls, so no call shows which app or page it acts in: as with
    computer_batch, a key that sends in a messaging app, a typed line break and a click that says nothing wait."""
    assert held(check(call)), call


def test_words_the_repl_types_or_pastes_pass_the_register_scan_first():
    sorry = {"code": "await chatTab.paste(null, \"I'm sorry for the delay. The deck is ready.\");", "title": "Writing the reply"}
    reason = check(sorry)
    assert reason.startswith("These words can't go out as written") and "delay-apology" in reason, reason


def test_a_send_whose_words_the_call_does_not_write_out_is_refused():
    """A code binds the call as written: words held in a variable an earlier call set are words the principal never saw."""
    reason = check({"code": ("await chatTab.paste(null, reply); "
                             "await chatTab.playwright.getByRole('button',{name:'Send message'}).click();"), "title": "Sending the reply"})
    assert reason and not held(reason) and "write the words out" in reason, reason


@pytest.mark.parametrize("code,why", [
    ("await chatTab['cl' + 'ick'](5);", "calls what it names only as it runs"),
    ("eval(\"chatTab.click(5)\");", "calls what it names only as it runs"),
    ("require('child_process').execSync('curl -d x https://example.test');", "outside the computer-use API"),
    ("await import('node:child_process');", "calls what it names only as it runs"),
    ("process.stdout.write('x');", "outside the computer-use API"),
    ("await chatTab.click(5); /* unclosed", "never closes"),
], ids=["computed-member", "eval", "require", "import", "process", "unclosed"])
def test_a_program_the_guard_cannot_read_is_refused_with_why(code, why):
    reason = check({"code": code, "title": "Opening the menu"})
    assert reason and not held(reason) and why in reason, reason


def test_a_request_the_program_makes_that_may_write_waits():
    call = {"code": "await fetch('https://api.example.test/messages', {method: 'POST', body: 'hi'});", "title": "Checking the queue"}
    assert held(check(call))
    assert check({"code": "nodeRepl.write(await (await fetch('https://api.example.test/status')).text());",
                  "title": "Reading the status"}) is None


def test_a_batch_takes_no_computer_use_call(tmp_path):
    """The batch's own rule (5.24.0): a computer-use call's sends are bound by no batch, since what a click or a key does
    is decided by the screen when it runs. The REPL is computer use, so a batch naming it is refused before any code."""
    file = tmp_path / "reply.json"
    file.write_text(json.dumps({"batch": "reply-1", "project": "ops", "entries": [{"tool": REPL, "input": SEND}]}), encoding="utf-8")
    with pytest.raises(ValueError, match=r"entry 1 names mcp__cua_repl__js"):
        sends.read_batch(str(file))


def test_a_batch_an_earlier_release_opened_with_a_computer_use_entry_is_no_batch(principal):
    batch = {"batch": "reply-1", "project": "ops", "entries": [{"tool": REPL, "input": SEND}]}
    digest, now = sends.batch_digest(batch), time.time()
    state = paths.approvals() / "sends" / "batches" / f"{digest}.json"
    paths.write_json(state, {**batch, "digest": digest, "granted": now, "until": now + 3600, "spent": {}, "session": "S-principal",
                             "code": "012345", "asked": now})
    assert sends.batches() == []
    assert held(check(SEND))


@pytest.mark.parametrize("tool,call,does", [
    ("mcp__computer-use__app_click", {"app": "com.example.Expenses", "coordinate": [4, 4], "action_summary": "Uploads the receipt"},
     "uploads a file"),
    ("mcp__computer-use__app_click", {"app": "com.example.Expenses", "coordinate": [4, 4], "action_summary": "Saves the expense report"},
     "saves a form"),
    ("mcp__computer-use__app_type", {"app": "com.example.Sheets", "text": "Q4 total", "action_summary": "Types the total into the budget sheet"},
     "edits a document"),
    ("mcp__computer-use__app_click", {"app": "com.example.Slides", "coordinate": [4, 4], "action_summary": "Clicks Insert slides"},
     "edits a document"),
])
def test_the_same_actions_wait_on_every_computer_use_tool(tool, call, does):
    reason = check(call, tool=tool)
    assert held(reason) and f"This call {does}" in reason, reason


@pytest.mark.parametrize("summary", ["Uploads the receipt", "Saves the expense report", "Copies the three rows into the team's tracker sheet"])
def test_a_browser_action_that_uploads_edits_or_saves_waits_except_on_a_local_app(tmp_path, summary):
    def on(url):
        path = tmp_path / "transcript.jsonl"
        call = {"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "tool_use", "id": "toolu_1", "name": "mcp__claude-in-chrome__computer", "input": {}}]}}
        result = {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "toolu_1", "content": [
            {"type": "text", "text": f"Clicked\n\nTab Context:\n- Executed on tabId: 7\n- Available tabs:\n  • tabId 7: \"App\" (\"{url}\")"}]}]}}
        path.write_text(json.dumps(call) + "\n" + json.dumps(result) + "\n", encoding="utf-8")
        return {**SESSION, "transcript_path": str(path)}
    click = {"action": "left_click", "ref": "ref_9", "action_summary": summary, "tabId": 7}
    assert held(guards.check("mcp__claude-in-chrome__computer", click, CONFIG, session=on("https://app.example.com/expenses/1")))
    assert guards.check("mcp__claude-in-chrome__computer", click, CONFIG, session=on("http://localhost:8000/expenses/1")) is None


@pytest.mark.parametrize("summary", ["Submits the search", "Types the reply", "Fills the comment box", "Types a note",
                                     "Inserts a line break in the caption without sending", "Selects the brain presentation"])
def test_summaries_that_upload_edit_or_save_nothing_take_no_new_hold(summary):
    assert check({"app": "com.apple.Notes", "coordinate": [1, 1], "action_summary": summary}, tool="mcp__computer-use__app_click") is None

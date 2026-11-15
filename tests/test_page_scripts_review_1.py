"""Review round 1 of the messaging-site page fix (2026-11-15): what its reviewer found, as tests.

Blocking: a fetch, Request or XHR write whose method is no literal `method: '...'` (#1); an optional call of a plain name
(#2); a sub-agent's page, and any page no list shows, judged as no messaging site's (#3). Major: a refused navigate
taken as a driven browser's page (#4); ordinary reads refused (#5). Minor: other parts of the address moving the tab
(#6), the pane's first page filed under no tab (#7), `Array.fill` held (#8), a bare or destructured send or handler
(#9), stale words (#10), a refusal quoting the reader's placeholder (#11). The crafted spellings of #13 are on the open
list in docs/runtime-integration.md, each with a test here marked to fail until it is closed (#12).
"""

import inspect
import json

import pytest

from synthesis import guards
from test_page_scripts import CHROME, CONFIG, PAGES, PANE, SCRIPT, _ran, _listing, _refused, _script, _session

PLAYWRIGHT = "mcp__plugin_playwright_playwright__"
# On the batch branch a Messenger tab takes only the plugin's own scripts (its own tests); main's rule governs the rest.
SITES = {k: v for k, v in PAGES.items() if k != "messenger" or not hasattr(guards, "_send_step")}
BUILT = "document.querySelector('[aria-label=\"Send now\"]')['cli' + 'ck']()"


def _held(verdict) -> bool:
    return bool(verdict) and "approve followed by the code" in verdict


def _stopped(verdict) -> bool:
    return bool(verdict)


def _check(tool, given, session):
    return guards.check(tool, given, CONFIG, session=session)


# --- 1: a write by fetch, Request or XHR unless its method is a literal GET or HEAD ---------------------------------

WRITES_BY_FETCH = [
    'fetch("/api/chat.postMessage", {"headers": {"content-type": "x"}, "body": "channel=C0001&text=hello", "method": "POST"})',
    "fetch('/api/messages', {'method': 'POST', body: JSON.stringify({text: 'hello'})})",
    "const method = 'POST'; fetch('/api/messages', {method, body: JSON.stringify({text: 'hello'})})",
    "const init = {body: JSON.stringify({text: 'hello'})}; init.method = 'POST'; fetch('/api/messages', init)",
    "fetch('/api/messages', {body: 'text=hello'})", "fetch(new Request('/api/messages', {method: 'PUT'}))",
    "const x = new XMLHttpRequest(); x.open(verb, '/api/messages'); x.send('hello')", "fetch?.('/api/messages', {method: m})",
]
READS_BY_FETCH = ["fetch('/api/conversations').then(r => r.json())", "fetch('/api/conversations', {method: 'GET'}).then(r => r.json())",
                  "fetch('/api/conversations', {\"method\": \"HEAD\"}).then(r => r.status)",
                  "fetch('/api/conversations?onlyUnread=true', {credentials: 'include'}).then(r => r.json())"]


@pytest.mark.parametrize("site", sorted(SITES))
@pytest.mark.parametrize("text", WRITES_BY_FETCH)
def test_a_write_by_fetch_request_or_xhr_waits_unless_its_method_is_a_literal_get_or_head(tmp_path, site, text):
    session = _session(tmp_path, SITES[site], tab=5)
    assert _held(_check(SCRIPT, _script(text, tab=5), session)), (site, text)


@pytest.mark.parametrize("site", sorted(SITES))
@pytest.mark.parametrize("text", READS_BY_FETCH)
def test_a_read_by_fetch_passes(tmp_path, site, text):
    assert _check(SCRIPT, _script(text, tab=5), _session(tmp_path, SITES[site], tab=5)) is None, (site, text)


# --- 2: an optional call of a plain name ---------------------------------------------------------------------------

OPTIONAL = ["document.querySelector('[aria-label=\"Send now\"]')?.click?.()", "document.querySelector('form')?.submit?.()",
            "document.querySelector('b')?.onclick?.()", "TS.client.ui.sendMessage?.('C0001', 'hello')", "window.open?.('/messages/t/2/')"]


@pytest.mark.parametrize("site", sorted(SITES))
@pytest.mark.parametrize("text", OPTIONAL)
def test_an_optional_call_of_a_call_that_acts_waits(tmp_path, site, text):
    assert _held(_check(SCRIPT, _script(text, tab=5), _session(tmp_path, SITES[site], tab=5))), (site, text)


# --- 3: a sub-agent's own record, and a page no list shows ---------------------------------------------------------

SENDS = {"built": (SCRIPT, _script(BUILT, tab=5), _refused), "plain-click": (SCRIPT, _script(
    "document.querySelector('[data-qa=\"texty_send_button\"]').click()", tab=5), _held),
         "return": ("mcp__claude-in-chrome__computer", {"action": "key", "text": "Return", "tabId": 5}, _held),
         "click-no-summary": ("mcp__claude-in-chrome__computer", {"action": "left_click", "coordinate": [9, 9], "tabId": 5}, _held)}


@pytest.mark.parametrize("name", sorted(SENDS))
def test_a_sub_agents_call_is_judged_by_its_own_record(tmp_path, name):
    tool, given, stops = SENDS[name]
    parent = tmp_path / "S-principal.jsonl"
    _ran(parent, "mcp__claude-in-chrome__computer", {"action": "screenshot", "tabId": 5}, _listing({5: "https://www.example.com/"}, 5))
    sub = {"session_id": "S-principal", "transcript_path": str(parent), "agent_id": "a1b2c3"}
    assert _stopped(_check(tool, given, sub)), name  # its own record shows nothing yet: the page is unknown, read it first
    own = tmp_path / "S-principal" / "subagents" / "agent-a1b2c3.jsonl"
    own.parent.mkdir(parents=True)
    _ran(own, "mcp__claude-in-chrome__computer", {"action": "screenshot", "tabId": 5}, _listing({5: SITES["slack"]}, 5))
    assert stops(_check(tool, given, sub)), name  # its own record shows the chat
    _ran(own, "mcp__claude-in-chrome__computer", {"action": "screenshot", "tabId": 5}, _listing({5: "https://docs.example.com/x"}, 5))
    assert _check(SCRIPT, _script("document.title", tab=5), sub) is None  # and a read on the page it shows passes


@pytest.mark.parametrize("tool", [SCRIPT, PANE + "javascript_tool"])
def test_a_page_no_list_shows_is_an_unknown_page(tmp_path, tool):
    record = tmp_path / "record.jsonl"
    _ran(record, "Bash", {"command": "ls"}, "notes.md")
    session = {"session_id": "S-principal", "transcript_path": str(record)}
    assert _refused(_check(tool, _script(BUILT, tab=5), session))
    assert _check(tool, _script("document.title", tab=5), session) is None  # a read there still passes


# --- 4: a refused navigate is never a driven browser's page --------------------------------------------------------

DRIVEN = {"evaluate-built": (PLAYWRIGHT + "browser_evaluate", {"function": "() => " + BUILT}, _refused),
          "evaluate-click": (PLAYWRIGHT + "browser_evaluate", {"function": "() => document.querySelector('.send').click()"}, _held),
          "click-no-label": (PLAYWRIGHT + "browser_click", {"element": "button", "ref": "e12"}, _held),
          "enter": (PLAYWRIGHT + "browser_press_key", {"key": "Enter"}, _held)}


@pytest.mark.parametrize("name", sorted(DRIVEN))
def test_a_refused_javascript_navigate_leaves_the_driven_page_as_it_was(tmp_path, name):
    tool, given, stops = DRIVEN[name]
    record = tmp_path / "record.jsonl"
    _ran(record, PLAYWRIGHT + "browser_navigate", {"url": SITES["slack"]}, f"- Page URL: {SITES['slack']}\n")
    session = {"session_id": "S-principal", "transcript_path": str(record)}
    go = {"url": "javascript:void(document.title)"}
    reason = _check(PLAYWRIGHT + "browser_navigate", go, session)
    assert _refused(reason)
    _ran(record, PLAYWRIGHT + "browser_navigate", go, f"PreToolUse:{PLAYWRIGHT}browser_navigate hook error: {reason}")
    assert stops(_check(tool, given, session)), name


# --- 5: ordinary reads pass; code in a string still stops where it reaches a sink -----------------------------------

READS = ["document.querySelectorAll('script').length",
         ("const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT); const out = []; while (w.nextNode()) { "
          "const p = w.currentNode.parentNode.nodeName; if (p !== 'SCRIPT' && p !== 'STYLE') out.push(w.currentNode.textContent); } out"),
         "[...document.links].map(a => a.href).filter(h => !h.startsWith('javascript:'))",
         "fetch('/api/conversations?onlyUnread=true').then(r => r.json())", "document.querySelectorAll('[data-online=\"true\"]').length",
         "Array.prototype.slice.call(document.querySelectorAll('h2')).map(h => h.innerText)",
         "Object.prototype.hasOwnProperty.call(window, 'TS')", "Math.max.apply(null, [...document.querySelectorAll('i')].map(e => +e.id))",
         "const $$ = document.querySelectorAll.bind(document); $$('h2').length", "let i = 4; const half = i++ / 2; half",
         "new Array(5).fill(0).map((_, n) => n)"]
SINKS = ["document.body.append(Object.assign(document.createElement('script'), {textContent: 'x()'}))",
         "box.innerHTML = '<img src=x onerror=go()>'", "el.setAttribute('onclick', 'go()')",
         "URL.createObjectURL(new Blob(['<script>go()</script>'], {type: 'text/html'}))", "el.outerHTML = '<a onmouseover=go()>x</a>'",
         "document.body.insertAdjacentHTML('beforeend', '<img src=x onerror=go()>')"]


@pytest.mark.parametrize("site", sorted(SITES))
@pytest.mark.parametrize("text", READS)
def test_an_ordinary_read_passes(tmp_path, site, text):
    assert _check(SCRIPT, _script(text, tab=5), _session(tmp_path, SITES[site], tab=5)) is None, (site, text)


@pytest.mark.parametrize("site", sorted(SITES))
@pytest.mark.parametrize("text", SINKS)
def test_code_in_a_string_that_reaches_a_sink_is_refused(tmp_path, site, text):
    assert _refused(_check(SCRIPT, _script(text, tab=5), _session(tmp_path, SITES[site], tab=5))), (site, text)


@pytest.mark.parametrize("text, stops", [("HTMLElement.prototype.click.call(el)", "held"), ("f.call(el)", "refused"),
                                         ("go.apply(el, [])", "refused")])
def test_a_call_of_a_dotted_name_is_read_as_that_name(tmp_path, text, stops):
    verdict = _check(SCRIPT, _script(text, tab=5), _session(tmp_path, SITES["slack"], tab=5))
    assert (_held if stops == "held" else _refused)(verdict), (text, verdict)


# --- 6, 7, 8, 9: other ways that move or act, the pane's first page, Array.fill, names that say what they do ---------

MOVES = ["location.pathname = '/messages/t/2/'", "location.search = '?phone=15550100&text=hello'", "location.hash = '#/C0002'",
         "navigation.navigate('/messages/t/2/')", "history.go(-1)"]
NAMED = ["sendMessage('C0001', 'hello')", "const {sendMessage} = TS.client.ui; sendMessage('C0001', 'hello')",
         "const go = document.querySelector('b').onclick; go()", "const {onClick} = props; onClick({preventDefault() {}})"]


@pytest.mark.parametrize("site", sorted(SITES))
@pytest.mark.parametrize("text", MOVES + NAMED)
def test_a_script_that_moves_the_tab_or_calls_a_send_or_handler_by_name_waits(tmp_path, site, text):
    assert _held(_check(SCRIPT, _script(text, tab=5), _session(tmp_path, SITES[site], tab=5))), (site, text)


@pytest.mark.parametrize("url, text, stops", [("http://localhost:3000/", "document.querySelector('#send').click()", None),
                                              (PAGES["linkedin"], BUILT, "refused")])
def test_the_panes_first_page_is_its_tabs(tmp_path, url, text, stops):
    record = tmp_path / "record.jsonl"
    _ran(record, PANE + "navigate", {"url": url}, f"opened {url} in the browser pane (it was hidden)")
    session = {"session_id": "S-principal", "transcript_path": str(record)}
    for given in ({"action": "javascript_exec", "text": text}, {"action": "javascript_exec", "text": text, "tabId": "tab-1"}):
        verdict = _check(PANE + "javascript_tool", given, session)
        assert (verdict is None) if stops is None else _refused(verdict), (url, given, verdict)


def test_a_driven_browsers_own_code_that_fills_still_waits(tmp_path):
    record = tmp_path / "record.jsonl"
    _ran(record, PLAYWRIGHT + "browser_navigate", {"url": SITES["slack"]}, f"- Page URL: {SITES['slack']}\n")
    session = {"session_id": "S-principal", "transcript_path": str(record)}
    assert _held(_check(PLAYWRIGHT + "browser_run_code_unsafe", {"code": "async (page) => { await page.fill('#box', 'hi'); }"}, session))


# --- 10, 11: the words describe the rule the code runs, and a refusal quotes the script ------------------------------

def test_no_words_of_the_withdrawn_rule_remain_and_a_refusal_quotes_no_placeholder(tmp_path):
    source = inspect.getsource(guards)
    assert not [s for s in ("A script is refused, not held", "only the shipped read-only\n    scripts run",
                            "On a messaging site's page no page script runs but the plugin's shipped read-only ones") if s in source]
    verdict = _check(SCRIPT, _script(BUILT, tab=5), _session(tmp_path, SITES["slack"], tab=5))
    assert _refused(verdict) and "\0" not in verdict and "a member named as it runs" in verdict, verdict


# --- 12, 13: the open list: each spelling made to beat the reader, expected to fail until it is closed ---------------

OPEN = {"escaped-name": "document.querySelector('b')['\\u0063lick']()", "escaped-hex": "document.querySelector('b')['\\x63lick']()",
        "parenthesized": "(document.querySelector('b').click)()", "template-tag": "document.querySelector('b').click``",
        "alias": "const el = document.querySelector('b'); el.x = el['cli' + 'ck']; el.x()",
        "foreach-call": "[document.querySelector('b')].forEach(Function.prototype.call, HTMLElement.prototype.click)",
        "getter": "const el = document.querySelector('b'); Object.defineProperty(el, 'x', {get: el['cli' + 'ck']}); el.x",
        "indirect-eval": "(0, eval)('document.querySelector(\"b\").cli' + 'ck()')",
        "timer-variable": "const c = 'document.querySelector(\"b\").cli' + 'ck()'; setTimeout(c, 10)",
        "window-alias": "const w = window; w.open('/messages/t/2/')",
        "encoded-html": "document.body.insertAdjacentHTML('beforeend', atob('PGltZyBzcmM9eCBvbmVycm9yPWdvKCk+'))",
        "html-comment": "const b = document.querySelector('b');\n<!-- '\nb['cli' + 'ck']()\n// '",
        "object-division": "var x = {} / document.querySelector('b')['cli' + 'ck']() / 1"}


@pytest.mark.xfail(strict=True, reason="on the open list in docs/runtime-integration.md: a spelling made to beat the reader")
@pytest.mark.parametrize("name", sorted(OPEN))
def test_open_a_spelling_made_to_beat_the_reader(tmp_path, name):
    assert _stopped(_check(SCRIPT, _script(OPEN[name], tab=5), _session(tmp_path, SITES["slack"], tab=5))), name


@pytest.mark.xfail(strict=True, reason="on the open list: a blob: document made on the site's own origin is not judged")
def test_open_a_blob_document_made_on_the_sites_own_origin(tmp_path):
    session = _session(tmp_path, SITES["slack"], tab=5)
    made = "URL.createObjectURL(new Blob([atob('PHNjcmlwdD5nbygpPC9zY3JpcHQ+')], {type: 'text/html'}))"
    then = guards.check("mcp__claude-in-chrome__navigate", {"url": "blob:https://app.slack.com/7a1e0000", "tabId": 5}, CONFIG, session=session)
    assert _stopped(_check(SCRIPT, _script(made, tab=5), session)) or _stopped(then)


def test_a_batch_whose_javascript_navigate_may_move_the_tab_runs_no_unreadable_script_after_it(tmp_path):
    """Closed by #3: the steps after such a navigate act on a page no list shows."""
    session = _session(tmp_path, "https://www.example.com/start", tab=5)
    moved = {"actions": [{"name": "navigate", "input": {"url": "javascript:void(location.href='" + PAGES["linkedin"] + "')", "tabId": 5}},
                         {"name": "computer", "input": {"action": "wait", "duration": 2, "tabId": 5}},
                         {"name": "javascript_tool", "input": _script(BUILT, tab=5)}]}
    assert _stopped(_check("mcp__claude-in-chrome__browser_batch", moved, session))

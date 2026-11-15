"""Review round 2 of the messaging-site page fix (2026-11-15): what its reviewer found, as tests.

#1 (major, ordinary work): after the pane's preview_start its page counted as unknown, so a local app's click, Return or
typed line break waited for a code; preview_start's answer is read as the pane's page now, and on a page the record does
not show a call that may send is told to read the page first, with no code asked. #2: a `body` key anywhere held a read
by fetch; only the init argument of fetch or Request is read, and an init the reader cannot follow is read as a write
(found in fixing it: spread into, keyed by a name built as it runs, set again, handed on). #3: a read helper the script defines, named for what it
reads (`tweetText`, `postBody`, `replyCount`), was held as a send. #4: `[].slice.call(` was refused. #5: `+=` moves the
tab; two crafted spellings go on the open list, each with a test expected to fail until it is closed.
"""

import json

import pytest

from synthesis import guards
from test_page_scripts import CONFIG, PAGES, PANE, SCRIPT, _ran, _script, _session
from test_page_scripts_review_1 import SITES, _held, _stopped

LOCAL = "http://localhost:3000/"


def _check(tool, given, session):
    return guards.check(tool, given, CONFIG, session=session)


# --- 1: the pane's page after preview_start, and a page the record does not show -----------------------------------

STARTED = {
    "opened": f"opened {LOCAL} in the preview pane (it was hidden)",
    "server-started": json.dumps({"serverId": "s1", "port": 3000, "name": "web", "reused": False, "url": LOCAL, "tabId": "tab-1"})
                      + f'\nweb started successfully on port 3000. Opened tab "App" at {LOCAL} Use tabId "tab-1" with read_page / find / '
                        "computer; serverId is for preview_logs and preview_stop only.",
    "pane-opened": json.dumps({"serverId": "s2", "tabId": "tab-1", "reused": False, "type": "browser", "displayed": True})
                   + '\nBrowser pane opened. Use serverId "s2" with read_page / find / computer.',
}
LOCAL_WORK = {"click-script": (PANE + "javascript_tool", {"action": "javascript_exec", "text": "document.querySelector('#save').click()"}),
              "return": (PANE + "computer", {"action": "key", "text": "Return"}),
              "typed-line": (PANE + "computer", {"action": "type", "text": "first line\n"})}


@pytest.mark.parametrize("answer", sorted(STARTED))
@pytest.mark.parametrize("work", sorted(LOCAL_WORK))
def test_a_local_apps_work_runs_in_the_pane_after_preview_start(tmp_path, answer, work):
    record = tmp_path / "record.jsonl"
    _ran(record, PANE + "preview_start", {"name": "web"}, STARTED[answer])
    session = {"session_id": "S-principal", "transcript_path": str(record)}
    tool, given = LOCAL_WORK[work]
    for named in (given, {**given, "tabId": "tab-1"}):
        assert _check(tool, named, session) is None, (answer, work, named)


def test_a_pane_opened_at_a_messaging_page_or_without_an_address_after_one_holds_a_script_that_acts(tmp_path):
    """preview_start's page is the address its answer names; an answer that names none changes no page, so the page an
    earlier result shows stands (a new pane with no earlier result shows a blank one)."""
    click = (PANE + "javascript_tool", {"action": "javascript_exec", "text": "document.querySelector('b').click()"})
    at = tmp_path / "at.jsonl"
    _ran(at, PANE + "preview_start", {"url": SITES["slack"]}, STARTED["server-started"].replace(LOCAL, SITES["slack"]))
    verdict = _check(*click, {"session_id": "S-principal", "transcript_path": str(at)})
    assert _held(verdict) and "slack" in verdict, verdict
    after = tmp_path / "after.jsonl"
    _ran(after, PANE + "navigate", {"url": SITES["slack"]}, f"Navigated to {SITES['slack']}")
    _ran(after, PANE + "preview_start", {}, STARTED["pane-opened"])
    verdict = _check(*click, {"session_id": "S-principal", "transcript_path": str(after)})
    assert _held(verdict) and "slack" in verdict, verdict


def test_a_call_that_may_send_on_a_page_the_record_does_not_show_is_told_to_read_the_page_first(tmp_path):
    record = tmp_path / "record.jsonl"
    _ran(record, "Bash", {"command": "ls"}, "notes.md")
    session = {"session_id": "S-principal", "transcript_path": str(record)}
    for tool, given in LOCAL_WORK.values():
        verdict = _check(tool, given, session)
        assert verdict and "read the page first" in verdict and "approve followed by the code" not in verdict, (tool, verdict)


# --- 2: method and body are read in fetch's or Request's init alone -------------------------------------------------

READS = ["fetch('/api/conversations.history').then(r => r.json()).then(d => d.messages.map(m => ({who: m.user, body: m.text})))",
         "fetch('/api/thread').then(async r => { return {status: r.status, body: await r.text()} })",
         "fetch('/api/thread').then(r => r.json()).then(({ok, body}) => ({ok, body}))",
         "fetch('/api/thread').then(r => r.json()).then(body => JSON.stringify(body, null, 2))"]
WRITES = ["fetch('/api/messages', {body: 'text=hello'})", "const init = {}; init.body = 'text=hello'; fetch('/api/messages', init)",
          "const init = {method: 'POST'}; fetch('/api/messages', init)", "const method = 'POST'; fetch('/api/messages', {method})",
          "fetch('/api/messages', options())", "fetch(new Request('/api/messages', {'method': 'PUT', body: 'x'}))"]


@pytest.mark.parametrize("site", ["slack", "linkedin", "gmail"])
@pytest.mark.parametrize("text", READS)
def test_a_read_by_fetch_with_a_body_elsewhere_passes(tmp_path, site, text):
    assert _check(SCRIPT, _script(text, tab=5), _session(tmp_path, SITES[site], tab=5)) is None, (site, text)


@pytest.mark.parametrize("text", WRITES)
def test_a_write_by_fetchs_init_still_waits(tmp_path, text):
    assert _held(_check(SCRIPT, _script(text, tab=5), _session(tmp_path, SITES["slack"], tab=5))), text


# An init the reader cannot follow is read as a write: spread into, keyed by a name built as it runs, the variable set
# again or handed to other code, a member named by a variable, a method set by `+=`, a method that is not one literal.
UNFOLLOWED = ["const opts = {method: 'POST', body: 'x'}; fetch('/api/messages', {...opts})",
              "fetch('/api/messages', {['met' + 'hod']: 'POST'})",
              "let init = {}; init = {method: 'POST'}; fetch('/api/messages', init)",
              "const init = {}; Object.assign(init, {method: 'POST'}); fetch('/api/messages', init)",
              "const key = 'method'; const init = {}; init[key] = 'POST'; fetch('/api/messages', init)",
              "let method = 'GET'; method = 'POST'; fetch('/api/messages', {method})",
              "const init = {}; init.body += 'text=hello'; fetch('/api/messages', init)",
              "fetch('/api/messages', {method: 'PO' + 'ST'})"]
FOLLOWED = ["const opts = {headers: {Accept: 'application/json'}, credentials: 'include'}; fetch('/api/x', opts).then(r => r.json())",
            "const init = {method: 'GET'}; init.headers = {Accept: 'application/json'}; fetch('/api/x', init).then(r => r.json())",
            "fetch('/api/x', {method: 'HEAD'}).then(r => r.status)"]


@pytest.mark.parametrize("text", UNFOLLOWED)
def test_an_init_the_reader_cannot_follow_waits(tmp_path, text):
    assert _held(_check(SCRIPT, _script(text, tab=5), _session(tmp_path, SITES["slack"], tab=5))), text


@pytest.mark.parametrize("text", FOLLOWED)
def test_a_read_whose_init_the_reader_follows_passes(tmp_path, text):
    assert _check(SCRIPT, _script(text, tab=5), _session(tmp_path, SITES["slack"], tab=5)) is None, text


# --- 3: a helper the script defines is no page's send -----------------------------------------------------------------

HELPERS = {"x": "const tweetText = a => a.querySelector('[data-testid=\"tweetText\"]')?.innerText; "
                "[...document.querySelectorAll('article')].map(a => tweetText(a))",
           "linkedin": "function postBody(el) { return el.innerText.trim() } [...document.querySelectorAll('.feed-shared-update-v2')].map(postBody)",
           "slack": "const replyCount = m => m.querySelector('[data-qa=\"reply_bar_count\"]')?.innerText; "
                    "[...document.querySelectorAll('[data-qa=\"message_container\"]')].map(m => replyCount(m))"}


@pytest.mark.parametrize("site", sorted(HELPERS))
def test_a_read_helper_the_script_defines_passes_and_a_pages_own_send_still_waits(tmp_path, site):
    session = _session(tmp_path, SITES[site], tab=5)
    assert _check(SCRIPT, _script(HELPERS[site], tab=5), session) is None, site
    for send in ("sendMessage('C0001', 'hello')", "const {sendMessage} = TS.client.ui; sendMessage('C0001', 'hello')"):
        assert _held(_check(SCRIPT, _script(send, tab=5), session)), (site, send)


# --- 4: [].x.call( is a call of x ------------------------------------------------------------------------------------

@pytest.mark.parametrize("text, stops", [("[].slice.call(document.querySelectorAll('h2')).map(h => h.innerText)", None),
                                         ("[].map.call(document.querySelectorAll('h2'), h => h.innerText)", None),
                                         ("const out = []; [].forEach.call(document.querySelectorAll('a'), a => out.push(a.href)); out", None),
                                         ("[].click.call(document.querySelector('b'))", "held")])
def test_an_empty_arrays_method_called_by_call_is_read_as_that_method(tmp_path, text, stops):
    verdict = _check(SCRIPT, _script(text, tab=5), _session(tmp_path, SITES["slack"], tab=5))
    assert (verdict is None) if stops is None else _held(verdict), (text, verdict)


# --- 5: += moves the tab; the open list's two new spellings ----------------------------------------------------------

@pytest.mark.parametrize("text", ["location.href += '#/C0002'", "location.hash += '2'", "location.search += '&thread=2'"])
def test_a_move_by_adding_to_the_address_waits(tmp_path, text):
    assert _held(_check(SCRIPT, _script(text, tab=5), _session(tmp_path, SITES["slack"], tab=5))), text


OPEN = {"fetch-destructured": "const {fetch: f} = window; f('/api/messages', {'method': 'POST', body: 'text=hello'})",
        "fetch-alias": "const f = window.fetch; f('/api/messages', {\"method\": \"POST\", \"body\": \"text=hello\"})",
        "method-in-an-object": "const o = {c: HTMLElement.prototype.click}; o.c.call(document.querySelector('b'))",
        "method-under-another-name": "const btn = document.querySelector('b'); btn.go = HTMLElement.prototype.click; btn.go()"}


@pytest.mark.xfail(strict=True, reason="on the open list in docs/runtime-integration.md: a spelling made to beat the reader")
@pytest.mark.parametrize("name", sorted(OPEN))
def test_open_a_fetch_or_a_method_reached_under_another_name(tmp_path, name):
    assert _stopped(_check(SCRIPT, _script(OPEN[name], tab=5), _session(tmp_path, SITES["slack"], tab=5))), name

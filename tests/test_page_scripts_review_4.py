"""Review round 4 of the messaging-site page fix (2026-11-15): what its reviewer found, as tests.

U1 (ordinary work): a read through a fetch wrapper waited again when the script's own result had a `body` (a key in an
object a callback returns, or a value a callback names): an init the reader cannot follow is now read by a method or a
body only in an object passed to a call, or in one a variable passed to a call holds or is given. U4 (ordinary work,
rare): a read helper on an object an IIFE in the script returns was held. C1 and C2 (crafted) go on the open list. And
T3's reading of sub-agents' records stays within the guard's deadline: a record that names no tab list is not parsed.
"""

import json
import os
import time
from datetime import datetime, timedelta, timezone

import pytest

from synthesis import guards
from test_page_scripts import CONFIG, SCRIPT, _listing, _script, _session
from test_page_scripts_review_1 import SITES, _held

CHROME = "mcp__claude-in-chrome__"


def _check(tool, given, session):
    return guards.check(tool, given, CONFIG, session=session)


# --- U1: a body in a wrapper read's own result -----------------------------------------------------------------------

WRAPPED_BODY = {
    "mapped-body-key": ("const get = (url, opts) => fetch(url, opts).then(r => r.json()); "
                        "get('/api/messages').then(d => d.items.map(m => ({from: m.from, body: m.text})))"),
    "pretty-printed": ("const get = (url, opts) => fetch(url, opts).then(r => r.json()); "
                       "get('/api/messages').then(body => JSON.stringify(body, null, 2))"),
}
STILL_WRITES = {  # the reviewer's writes through a wrapper or a spread, which still wait
    "wrapper-with-method": "const api = (u, o) => fetch(u, o); api('/api/chat.postMessage', {method: 'POST', body: 'text=hello'})",
    "spread-base": "const base = {method: 'POST'}; fetch('/api/chat.postMessage', {...base, body: 'text=hello'})",
    "spread-base-alone": "const base = {method: 'POST', body: 'text=hello'}; fetch('/api/chat.postMessage', {...base})",
    "assigned-later": "const api = (u, o) => fetch(u, o); const o = {}; o.method = 'POST'; o.body = 'text=hello'; api('/api/send', o)",
    "assigned-object": "const api = (u, o) => fetch(u, o); let o = {}; o = {method: 'PUT'}; api('/api/send', o)",
    "built-by-assign": "fetch('/api/messages', Object.assign({}, {method: 'POST'}))",
}


@pytest.mark.parametrize("site", ["slack", "gmail", "linkedin"])
@pytest.mark.parametrize("name", sorted(WRAPPED_BODY))
def test_a_wrapper_read_with_a_body_in_its_own_result_passes(tmp_path, site, name):
    session = _session(tmp_path, SITES[site], tab=5)
    renamed = WRAPPED_BODY[name].replace("body", "content")
    inline = WRAPPED_BODY[name].replace("fetch(url, opts)", "fetch(url, {credentials: 'include'})")
    assert _check(SCRIPT, _script(renamed, tab=5), session) is None, ("control: the key renamed", name)
    assert _check(SCRIPT, _script(inline, tab=5), session) is None, ("control: the init written out", name)
    assert _check(SCRIPT, _script(WRAPPED_BODY[name], tab=5), session) is None, (site, name)


@pytest.mark.parametrize("name", sorted(STILL_WRITES))
def test_a_write_through_a_wrapper_or_a_spread_still_waits(tmp_path, name):
    assert _held(_check(SCRIPT, _script(STILL_WRITES[name], tab=5), _session(tmp_path, SITES["slack"], tab=5))), name


# --- U4: a read helper on an object an IIFE returns ------------------------------------------------------------------

IIFES = {"arrow": "const R = (() => ({tweetText: a => a.innerText}))(); [...document.querySelectorAll('article')].map(a => R.tweetText(a))",
         "function": ("const R = (function () { return {tweetText(a) { return a.innerText }} })(); "
                      "[...document.querySelectorAll('article')].map(a => R.tweetText(a))")}


@pytest.mark.parametrize("name", sorted(IIFES))
def test_a_read_helper_on_an_object_an_iife_returns_passes(tmp_path, name):
    session = _session(tmp_path, SITES["x"], tab=5)
    assert _check(SCRIPT, _script(IIFES[name].replace("tweetText", "textOf"), tab=5), session) is None, ("control", name)
    assert _check(SCRIPT, _script(IIFES[name], tab=5), session) is None, name
    page = "const R = (() => window.app)(); R.sendMessage('C0001', 'hello')"  # an IIFE that returns the page's object
    assert _held(_check(SCRIPT, _script(page, tab=5), session)), page


# --- C1 and C2: the open list ----------------------------------------------------------------------------------------

OPEN = {"init-parsed-from-a-string": "fetch('/api/chat.postMessage', JSON.parse('{\"method\":\"POST\",\"body\":\"channel=C0001&text=hello\"}'))",
        "top-level-this": "class Helper { sendMessage() {} } this.sendMessage('C0001', 'hello')",
        "receiver-reassigned": "let o = {sendMessage() {}}; o = window.app; o.sendMessage('C0001', 'hello')"}


@pytest.mark.xfail(strict=True, reason="on the open list in docs/runtime-integration.md: a spelling made to beat the reader")
@pytest.mark.parametrize("name", sorted(OPEN))
def test_open_an_init_from_a_string_or_a_pages_send_under_the_scripts_own_name(tmp_path, name):
    assert _check(SCRIPT, _script(OPEN[name], tab=5), _session(tmp_path, SITES["slack"], tab=5)), name


# --- T3's cost: a busy session's sub-agent records -------------------------------------------------------------------

def _line(name, given, said, ago):
    stamp = (datetime.now(timezone.utc) - timedelta(seconds=ago)).isoformat().replace("+00:00", "Z")
    ident = f"toolu_{name.rpartition('__')[2]}_{ago}"
    return (json.dumps({"type": "assistant", "timestamp": stamp, "message": {"content": [{"type": "tool_use", "id": ident, "name": name, "input": given}]}})
            + "\n" + json.dumps({"type": "user", "timestamp": stamp, "message": {"content": [{"type": "tool_result", "tool_use_id": ident,
                                                                                                "content": [{"type": "text", "text": said}]}]}}) + "\n")


def _busy(tmp_path, records=70, megabytes=1.0):
    """A session whose own list shows tab 5 on an ordinary page, and `records` sub-agents active since, each record
    `megabytes` long; only the last two use the browser, the newest moving tab 5 to a chat."""
    main = tmp_path / "S-principal.jsonl"
    main.write_text(_line(CHROME + "computer", {"action": "screenshot", "tabId": 5}, _listing({5: "https://www.example.com/"}, 5), 900))
    folder = tmp_path / "S-principal" / "subagents"
    folder.mkdir(parents=True)
    filler = _line("Bash", {"command": "ls"}, "x" * 4000, 800)
    body = filler * max(1, int(megabytes * (1 << 20) / len(filler)))
    for n in range(records):
        tail = ""
        if n == records - 2:
            tail = _line(CHROME + "computer", {"action": "screenshot", "tabId": 5}, _listing({5: "https://docs.example.com/"}, 5), 300)
        if n == records - 1:
            tail = _line(CHROME + "navigate", {"url": SITES["slack"], "tabId": 5}, _listing({5: SITES["slack"]}, 5), 100)
        (folder / f"agent-a{n:03d}.jsonl").write_text(body + tail)
    return {"session_id": "S-principal", "transcript_path": str(main)}


def test_a_sub_agent_record_that_names_no_tab_list_is_not_parsed(tmp_path, monkeypatch):
    session = _busy(tmp_path, records=70, megabytes=0.05)
    parsed = []
    real = guards._tab_list
    monkeypatch.setattr(guards, "_tab_list", lambda record, server="": parsed.append(record) or real(record, server))
    assert _held(_check(CHROME + "computer", {"action": "key", "text": "Return", "tabId": 5}, session)), "the newest list: the chat"
    assert len(set(parsed)) <= 3, len(set(parsed))  # its own record and the two that name a list


def test_reading_a_busy_sessions_sub_agent_records_stays_well_within_the_guards_deadline(tmp_path, pace):
    """The busiest 12 hours of real records held 70 sub-agent records (round 4's notes: 122 MB to read with the 8 MB cap,
    about 0.9 s of the guard's 4 s); 70 records of 1 MB here are read in a quarter of that deadline on the principal's
    Mac, stretched by `pace` on a slower machine (main's CI after 5.24.1's merge: 1.30 s on a macOS runner)."""
    from synthesis import hook
    session = _busy(tmp_path, records=70, megabytes=1.0)
    started = time.perf_counter()
    verdict = _check(CHROME + "computer", {"action": "key", "text": "Return", "tabId": 5}, session)
    spent = time.perf_counter() - started
    assert _held(verdict) and spent < hook.GUARD_SECONDS / 4 * pace, round(spent, 3)

"""Review round 3 of the messaging-site page fix (2026-11-15): what its reviewer found, as tests.

T1 (ordinary work): a read through a fetch wrapper waited (an options parameter passed through, a default spread into
the init, an init built by Object.assign), since an init the reader could not follow was a write; such an init is now
read by a method or a body anywhere in the script. T2 (ordinary work): a read helper named for what it reads waited when
it was an object's or a class's method; the methods a script defines are names it defines, and a call of one on `this`
or on an object the script defines is no page's send. T3 (plain attempt, rare): a sub-agent was judged by its own list
after its session moved the tab they share; each tab is read at the newest list that names it across the session's
record and its sub-agents'.
"""

import json
from datetime import datetime, timedelta, timezone

import pytest

from synthesis import guards
from test_page_scripts import CONFIG, SCRIPT, _listing, _script, _session
from test_page_scripts_review_1 import SITES, _held

CHROME = "mcp__claude-in-chrome__"
RETURN = {"action": "key", "text": "Return", "tabId": 5}


def _check(tool, given, session):
    return guards.check(tool, given, CONFIG, session=session)


# --- T1: a read through a fetch wrapper ------------------------------------------------------------------------------

WRAPPERS = {
    "param-passthrough": "const get = (url, opts) => fetch(url, opts).then(r => r.json()); get('/api/conversations.list')",
    "default-spread": "async function api(path, opts = {}) { const r = await fetch(path, {credentials: 'include', ...opts}); "
                      "return r.json() } api('/api/conversations.list')",
    "object-assign": "fetch('/api/conversations.list', Object.assign({}, {credentials: 'include'})).then(r => r.json())",
}
WRAPPED_WRITES = {
    "param-passthrough": "const get = (url, opts) => fetch(url, opts); get('/api/chat.postMessage', {method: 'POST', body: 'text=hi'})",
    "default-spread": "async function api(path, opts = {}) { return fetch(path, {credentials: 'include', ...opts}) } "
                      "api('/api/messages', {method: 'POST'})",
    "object-assign": "fetch('/api/messages', Object.assign({}, {body: 'text=hi'}))",
    "set-on-the-options": "const opts = {}; opts.body = 'text=hi'; const get = (url, o) => fetch(url, o); get('/api/messages', opts)",
}


@pytest.mark.parametrize("site", ["slack", "linkedin"])
@pytest.mark.parametrize("name", sorted(WRAPPERS))
def test_a_read_through_a_fetch_wrapper_passes(tmp_path, site, name):
    session = _session(tmp_path, SITES[site], tab=5)
    control = "fetch('/api/conversations.list', {credentials: 'include'}).then(r => r.json())"
    assert _check(SCRIPT, _script(control, tab=5), session) is None, "control: the init written out"
    assert _check(SCRIPT, _script(WRAPPERS[name], tab=5), session) is None, (site, name)


@pytest.mark.parametrize("name", sorted(WRAPPED_WRITES))
def test_a_write_through_a_fetch_wrapper_still_waits(tmp_path, name):
    assert _held(_check(SCRIPT, _script(WRAPPED_WRITES[name], tab=5), _session(tmp_path, SITES["slack"], tab=5))), name


# --- T2: a read helper that is a method ------------------------------------------------------------------------------

METHODS = {
    "x": ("const r = {tweetText(a) { return a.querySelector('[data-testid=\"tweetText\"]')?.innerText }}; "
          "[...document.querySelectorAll('article')].map(a => r.tweetText(a))"),
    "linkedin": ("class Feed { postBody(el) { return el.innerText.trim() } all() { return [...document.querySelectorAll("
                 "'.feed-shared-update-v2')].map(p => this.postBody(p)) } } new Feed().all()"),
    "slack": ("const util = {replyCount: m => m.querySelector('[data-qa=\"reply_bar_count\"]')?.innerText}; "
              "[...document.querySelectorAll('[data-qa=\"message_container\"]')].map(m => util.replyCount(m))"),
}
ARROWS = {"x": "const tweetText = a => a.innerText; [...document.querySelectorAll('article')].map(a => tweetText(a))",
          "linkedin": "const postBody = el => el.innerText.trim(); [...document.querySelectorAll('.feed-shared-update-v2')].map(p => postBody(p))",
          "slack": "const replyCount = m => m.innerText; [...document.querySelectorAll('[data-qa=\"message_container\"]')].map(m => replyCount(m))"}
PAGE_SENDS = {  # a page's own send, by a method the script does not define or on an object it does not
    "page-object": "TS.client.ui.sendMessage('C0001', 'hello')",
    "copied-onto-an-object": "const o = {}; o.sendMessage = TS.client.ui.sendMessage; o.sendMessage('C0001', 'hello')",
    "this-undefined-method": "class A { go() { return this.sendMessage('C0001', 'hello') } } new A().go()",
    "defined-method-other-object": "const r = {tweetText(a) { return a.innerText }}; window.app.tweetText('hello')",
    "a-method-that-sends": "const r = {postReply(t) { return TS.client.ui.sendMessage('C0001', t) }}; r.postReply('hello')",
    # the reviewer's status checks: a parameter named like a send changes nothing where the send is written as a call
    "param-named-send-click": "const run = (send) => send(); run(() => document.querySelector('[aria-label=\"Send\"]').click())",
    "param-named-post-member": ("function withRetry(post, tries = 2) { for (let i = 0; i < tries; i++) { try { return post() } catch (e) {} } } "
                                "withRetry(() => TS.client.ui.sendMessage('C0001', 'hello'))"),
}


@pytest.mark.parametrize("site", sorted(METHODS))
def test_a_read_helper_that_is_a_method_passes(tmp_path, site):
    session = _session(tmp_path, SITES[site], tab=5)
    assert _check(SCRIPT, _script(ARROWS[site], tab=5), session) is None, ("control: a const arrow", site)
    assert _check(SCRIPT, _script(METHODS[site], tab=5), session) is None, site


@pytest.mark.parametrize("name", sorted(PAGE_SENDS))
def test_a_pages_own_send_by_a_method_still_waits(tmp_path, name):
    assert _held(_check(SCRIPT, _script(PAGE_SENDS[name], tab=5), _session(tmp_path, SITES["slack"], tab=5))), name


# --- T3: the tab a sub-agent shares with its session -----------------------------------------------------------------

def _at(record, name, given, said, ago: int) -> None:
    """A call and its result in a Claude Code record, written `ago` seconds before now."""
    stamp = (datetime.now(timezone.utc) - timedelta(seconds=ago)).isoformat().replace("+00:00", "Z")
    ident = f"toolu_{ago}_{name.rpartition('__')[2]}"
    with record.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"type": "assistant", "timestamp": stamp, "message": {"content": [
            {"type": "tool_use", "id": ident, "name": name, "input": given}]}}) + "\n")
        handle.write(json.dumps({"type": "user", "timestamp": stamp, "message": {"content": [
            {"type": "tool_result", "tool_use_id": ident, "content": [{"type": "text", "text": said}]}]}}) + "\n")


def test_each_tab_is_read_at_the_newest_list_across_a_session_and_its_sub_agents(tmp_path):
    main = tmp_path / "S-principal.jsonl"
    own = tmp_path / "S-principal" / "subagents" / "agent-a1b2c3.jsonl"
    own.parent.mkdir(parents=True)
    session = {"session_id": "S-principal", "transcript_path": str(main)}
    sub = {**session, "agent_id": "a1b2c3"}
    _at(main, CHROME + "computer", {"action": "screenshot", "tabId": 5}, _listing({5: "https://www.example.com/"}, 5), 400)
    _at(own, CHROME + "computer", {"action": "screenshot", "tabId": 5}, _listing({5: "https://www.example.com/"}, 5), 300)
    assert _check(CHROME + "computer", RETURN, sub) is None and _check(CHROME + "computer", RETURN, session) is None
    _at(main, CHROME + "navigate", {"url": SITES["slack"], "tabId": 5}, f"Navigated to {SITES['slack']}\n" + _listing({5: SITES["slack"]}, 5), 200)
    assert _held(_check(CHROME + "computer", RETURN, session)), "control: the session's own Return"
    assert _held(_check(CHROME + "computer", RETURN, sub)), "the sub-agent's Return on the tab its session moved to the chat"
    done = "https://docs.example.com/x"  # and the other way, round 1's #3: the sub-agent's newer list decides for both
    _at(own, CHROME + "navigate", {"url": done, "tabId": 5}, f"Navigated to {done}\n" + _listing({5: done}, 5), 100)
    assert _check(CHROME + "computer", RETURN, sub) is None and _check(CHROME + "computer", RETURN, session) is None


def test_a_sub_agent_whose_session_shows_the_tab_reads_it_there_and_one_no_record_shows_is_unknown(tmp_path):
    main = tmp_path / "S-principal.jsonl"
    sub = {"session_id": "S-principal", "transcript_path": str(main), "agent_id": "a1b2c3"}
    _at(main, "Bash", {"command": "ls"}, "notes.md", 300)
    assert "read the page first" in (_check(CHROME + "computer", RETURN, sub) or ""), "no record shows tab 5"
    _at(main, CHROME + "computer", {"action": "screenshot", "tabId": 5}, _listing({5: SITES["slack"]}, 5), 200)
    assert _held(_check(CHROME + "computer", RETURN, sub)), "its session's list shows tab 5 on the chat"

"""Review round 5 of the messaging-site page fix (2026-11-15): what its reviewer found, as tests.

W4 (plain attempt, opened by round 4's narrowing): an init the script's own helper returns passed, since an init the
reader cannot follow was read only by what the script passes to a call. A method is read anywhere in the script again,
as before round 4, and a body only in an object passed to a call or held by a variable passed to one, so round 4's read
mappings keep passing. W5 (crafted) goes on the open list.
"""

import pytest

from synthesis import guards
from test_page_scripts import CONFIG, SCRIPT, _script, _session
from test_page_scripts_review_1 import SITES, _held

BUILT = {
    "generic-helper": ("const req = (method, body) => ({method, body, credentials: 'include'}); "
                       "fetch('/api/chat.postMessage', req('POST', 'channel=C0001&text=hello'))"),
    "quoted-helper": "const opts = text => ({\"method\": \"POST\", \"body\": text}); fetch('/api/chat.postMessage', opts('channel=C0001&text=hello'))",
    "helper-assigns": ("function mk(body) { const o = {body}; o.method = 'POST'; return o } "
                       "fetch('/api/chat.postMessage', mk('channel=C0001&text=hello'))"),
    "variable-from-helper": ("const req = (method, body) => ({method, body}); const init = req('POST', 'channel=C0001&text=hello'); "
                             "fetch('/api/chat.postMessage', init)"),
    "through-a-wrapper": ("const api = (u, o) => fetch(u, o); const req = (method, body) => ({method, body}); "
                          "api('/api/chat.postMessage', req('POST', 'channel=C0001&text=hello'))"),
}
READS = {  # round 4's U1 mappings, which name no method
    "mapped-body-key": ("const get = (url, opts) => fetch(url, opts).then(r => r.json()); "
                        "get('/api/messages').then(d => d.items.map(m => ({from: m.from, body: m.text})))"),
    "pretty-printed": "const get = (url, opts) => fetch(url, opts).then(r => r.json()); get('/api/messages').then(body => JSON.stringify(body, null, 2))",
}


def _check(text, session):
    return guards.check(SCRIPT, _script(text, tab=5), CONFIG, session=session)


@pytest.mark.parametrize("site", ["slack", "linkedin", "x", "gmail"])
@pytest.mark.parametrize("name", sorted(BUILT))
def test_an_init_the_scripts_own_helper_returns_waits(tmp_path, site, name):
    session = _session(tmp_path, SITES[site], tab=5)
    assert _held(_check("fetch('/api/chat.postMessage', {method: verb, body: 'channel=C0001&text=hello'})", session)), "control"
    assert _held(_check(BUILT[name], session)), (site, name)


@pytest.mark.parametrize("site", ["slack", "linkedin", "x", "gmail"])
@pytest.mark.parametrize("name", sorted(READS))
def test_a_read_whose_own_result_has_a_body_still_passes(tmp_path, site, name):
    assert _check(READS[name], _session(tmp_path, SITES[site], tab=5)) is None, (site, name)


@pytest.mark.xfail(strict=True, reason="on the open list in docs/runtime-integration.md: a spelling made to beat the reader")
def test_open_an_iife_that_writes_a_decoy_object_and_returns_the_pages(tmp_path):
    decoy = ("const helpers = {sendMessage() {}}; const R = (() => { [0].map(i => ({i})); return window.app })(); "
             "R.sendMessage('C0001', 'hello')")
    assert _check(decoy, _session(tmp_path, SITES["slack"], tab=5))

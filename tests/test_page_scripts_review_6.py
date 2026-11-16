"""Review round 6 of the messaging-site page fix (2026-11-15): what its reviewer found, as tests.

Round 5 read a method named anywhere in a script again for an init the reader cannot follow (W4), which held four
ordinary reads through a fetch wrapper: a shorthand key over a const that holds GET, a parameter named method, a default
parameter, and a form's method read. A method is now read only as an object key (its value, or a shorthand's one const
literal) or a member assignment (`x.method =`, `x['method'] =`), and every W4 spelling still waits.
"""

import pytest

from synthesis import guards
from test_page_scripts import CONFIG, SCRIPT, _script, _session
from test_page_scripts_review_1 import SITES, _held
from test_page_scripts_review_5 import BUILT

WRAP = "const get = (url, opts) => fetch(url, opts).then(r => r.json()); "
READS = {
    "get-by-key": WRAP + "get('/api/conversations.list', {method: 'GET'})",
    "head-quoted-key": WRAP + "get('/api/conversations.list', {\"method\": \"HEAD\"})",
    "get-shorthand": WRAP + "const method = 'GET'; get('/api/conversations.list', {method})",
    "method-in-string-and-comment": "// any method works here\n" + WRAP + "console.log('method'); get('/api/conversations.list')",
    "unsent-method-param": WRAP + "const label = (method, url) => method + ' ' + url; get('/api/conversations.list').then(d => label('GET', '/api') + d.ok)",
    "unsent-method-param-default": WRAP + "const label = (url, method = 'GET') => method + ' ' + url; get('/api/conversations.list').then(d => label('/api') + d.ok)",
    "form-method-read": WRAP + "get('/api/conversations.list').then(d => [...document.forms].map(f => f.method))",
}
STILL_WRITES = {  # a method set as a key or by a member assignment, through a wrapper
    "post-by-key": WRAP + "get('/api/chat.postMessage', {method: 'POST'})",
    "shorthand-over-a-post": WRAP + "const method = 'POST'; get('/api/chat.postMessage', {method})",
    "member-assigned": WRAP + "const o = {}; o.method = 'POST'; get('/api/chat.postMessage', o)",
    "bracket-assigned": WRAP + "const o = {}; o['method'] = 'PUT'; get('/api/chat.postMessage', o)",
    "added-to": WRAP + "const o = {method: 'GET'}; o.method += 'X'; get('/api/chat.postMessage', o)",
    "default-post": WRAP + "const send = (url, method = 'POST') => get(url, {method}); send('/api/chat.postMessage')",
}


def _check(text, session):
    return guards.check(SCRIPT, _script(text, tab=5), CONFIG, session=session)


@pytest.mark.parametrize("site", ["slack", "gmail"])
@pytest.mark.parametrize("name", sorted(READS))
def test_a_read_that_names_method_passes(tmp_path, site, name):
    session = _session(tmp_path, SITES[site], tab=5)
    assert _check(WRAP + "get('/api/conversations.list')", session) is None, "control"
    assert _check(READS[name], session) is None, (site, name)


@pytest.mark.parametrize("name", sorted(STILL_WRITES))
def test_a_method_set_as_a_key_or_a_member_still_waits(tmp_path, name):
    assert _held(_check(STILL_WRITES[name], _session(tmp_path, SITES["slack"], tab=5))), name


@pytest.mark.parametrize("site", ["slack", "linkedin", "x", "gmail"])
@pytest.mark.parametrize("name", sorted(BUILT))
def test_every_w4_spelling_still_waits(tmp_path, site, name):
    assert _held(_check(BUILT[name], _session(tmp_path, SITES[site], tab=5))), (site, name)

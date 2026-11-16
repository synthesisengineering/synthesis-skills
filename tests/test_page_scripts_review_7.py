"""Review round 7 of the messaging-site page fix (2026-11-15): what its reviewer found, as tests.

Y3 (plain attempt, opened by round 6): the member-assignment and literal-key patterns took `=`, `+=` and `-=` alone, so
an options helper that defaults the method by a logical assignment (`o.method ??= 'POST'`, `||=`) passed as a read on
every site. Every assignment operator now counts, and a body set on a passed object the same way waits too. Three
spellings made to beat the reader go on the open list (Y4). A read whose own result mapping has a `method` key waits
(Y5): the trade-off the open list notes, rare, and it fails closed.
"""

import pytest

from synthesis import guards
from test_page_scripts import CONFIG, SCRIPT, _script, _session
from test_page_scripts_review_1 import SITES, _held
from test_page_scripts_review_5 import BUILT

WRAP = "const get = (url, opts) => fetch(url, opts).then(r => r.json()); "
OPERATORS = ["??=", "||=", "&&=", "+=", "-=", "*=", "/=", "%=", "**=", "<<=", ">>=", ">>>=", "&=", "|=", "^="]


def _check(text, session):
    return guards.check(SCRIPT, _script(text, tab=5), CONFIG, session=session)


@pytest.mark.parametrize("site", ["slack", "linkedin", "x", "gmail"])
@pytest.mark.parametrize("operator", OPERATORS)
def test_a_method_set_by_any_assignment_operator_waits(tmp_path, site, operator):
    session = _session(tmp_path, SITES[site], tab=5)
    assert _held(_check(BUILT["helper-assigns"], session)), "control: o.method = 'POST'"
    text = BUILT["helper-assigns"].replace("o.method = 'POST'", f"o.method {operator} 'POST'")
    assert _held(_check(text, session)), (site, operator)


@pytest.mark.parametrize("operator", ["??=", "||=", "&&="])
def test_a_method_set_by_a_quoted_key_and_a_logical_assignment_waits(tmp_path, operator):
    text = BUILT["helper-assigns"].replace("o.method = 'POST'", f"o['method'] {operator} 'POST'")
    assert _held(_check(text, _session(tmp_path, SITES["slack"], tab=5))), operator


@pytest.mark.parametrize("member", ["o.body ??= text", "o.body ||= text", "o['body'] &&= text", "o.body += text"])
def test_a_body_set_on_a_passed_object_by_any_operator_waits(tmp_path, member):
    session = _session(tmp_path, SITES["slack"], tab=5)
    read = WRAP + "const text = 'channel=C0001&text=hello'; const o = {}; o.headers = {}; get('/api/conversations.list', o)"
    assert _check(read, session) is None, "control: no body set"
    assert _held(_check(read.replace("o.headers = {}", member), session)), member


@pytest.mark.parametrize("site", ["slack", "gmail"])
def test_a_method_compared_is_no_setting(tmp_path, site):
    text = WRAP + ("get('/api/conversations.list').then(d => d.items.filter(i => i.method === 'GET' || i.method != 'POST' "
                   "|| i.method >= 'A' || i.method <= 'Z' || i['method'] == 'HEAD'))")
    assert _check(text, _session(tmp_path, SITES[site], tab=5)) is None, site


@pytest.mark.parametrize("keyword", ["const", "let", "var"])
def test_a_post_method_given_as_the_shorthand_waits(tmp_path, keyword):
    text = WRAP + f"{keyword} method = 'POST'; get('/api/chat.postMessage', {{method}})"
    assert _held(_check(text, _session(tmp_path, SITES["slack"], tab=5))), keyword


def test_a_read_whose_own_result_maps_a_method_key_waits(tmp_path):
    # The trade-off beside the open list: the reader counts a `method` key wherever it is written. Rare, and it fails
    # closed: the person answers one code.
    text = WRAP + "get('/api/payments').then(d => d.items.map(p => ({id: p.id, method: p.paymentMethod})))"
    assert _held(_check(text, _session(tmp_path, SITES["slack"], tab=5)))


# --- Y4: the open list -----------------------------------------------------------------------------------------------

OPEN = {
    "define-property": ("function mk(body) { const o = {}; Object.defineProperty(o, 'method', {value: 'POST', enumerable: true}); "
                        "o.headers = {}; return o } fetch('/api/chat.postMessage', Object.assign(mk(), {}))"),
    "from-entries": "fetch('/api/chat.postMessage', Object.fromEntries([['method', 'POST'], ['credentials', 'include']]))",
    "class-field-after-another": "class O { credentials = 'include'; method = 'POST' } fetch('/api/chat.postMessage', new O())",
}


@pytest.mark.xfail(strict=True, reason="on the open list in docs/runtime-integration.md: a spelling made to beat the reader")
@pytest.mark.parametrize("name", sorted(OPEN))
def test_open_a_method_set_another_way(tmp_path, name):
    assert _check(OPEN[name], _session(tmp_path, SITES["slack"], tab=5)), name

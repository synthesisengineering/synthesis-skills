"""One command that several of the guard's checks hold asks the principal for one code (A5, 2026-11-17).

That evening a re-pin of the hooks' interpreter was held first by the runtime check and, once its code was typed and the
identical command run again, by the check on a script that names synthesis's writers: two codes, typed minutes apart,
for one command. Each check stopped the chain, so the next was only seen on the retry. Now every check of the call is
judged, a refusal is what the call gets, and every request the call files takes one code, which grants them all.
"""

import re

import pytest

from synthesis import approvals, guards


def _codes(reason) -> list:
    return sorted(set(re.findall(r"\bcode ([0-9][0-9a-f]{5})\b", reason or "")))


def test_requests_filed_while_one_call_is_judged_share_one_code_which_grants_them_all():
    with approvals.one_code():
        first = approvals.request("runtime", {"to": "a"}, "the runtime")
        second = approvals.request("deploy", {"line": "b"}, "a deploy")
    assert first == second and approvals.pending() == [first]
    assert approvals.grant_from_prompt(f"approve {first}") == ["the runtime", "a deploy"]
    assert approvals.held("runtime", {"to": "a"}) and approvals.held("deploy", {"line": "b"}) and approvals.pending() == []


def test_outside_one_call_each_request_keeps_its_own_code():
    assert approvals.request("runtime", {"to": "a"}, "x") != approvals.request("deploy", {"line": "b"}, "y")


def test_a_retry_of_the_call_keeps_the_one_code_already_shown():
    with approvals.one_code():
        code = approvals.request("runtime", {"to": "a"}, "x")
        approvals.request("deploy", {"line": "b"}, "y")
    with approvals.one_code():  # the same call again, its checks judged in another order
        assert approvals.request("deploy", {"line": "b"}, "y") == code
        assert approvals.request("runtime", {"to": "a"}, "x") == code
    assert approvals.pending() == [code]


def test_one_call_inside_another_files_under_the_outer_call_s_code():
    """The git programs a command runs are each judged as a call of their own, inside the command's."""
    with approvals.one_code():
        outer = approvals.request("runtime", {"to": "a"}, "x")
        with approvals.one_code():
            assert approvals.request("deploy", {"line": "b"}, "y") == outer
        assert approvals.request("line", {"line": "c"}, "z") == outer


def test_a_program_that_checks_its_own_approval_finds_its_request_among_the_others(principal):
    """The CLI's install reads the session's record for the code of its own request (approvals.answered)."""
    with approvals.one_code():
        code = approvals.request("line", {"line": "c"}, "a line")
        approvals.request("runtime", {"to": "a"}, "the runtime")
    principal(f"... code {code}", grant=False)  # typed in the session; no prompt hook made a grant of it
    assert approvals.answered("runtime", {"to": "a"})


def test_one_command_two_checks_hold_asks_one_code_and_that_code_lets_it_run(tmp_path, principal):
    line = {"command": "synthesis install /tmp/plugin; wrangler pages deploy dist"}
    session = {"session_id": "S-principal", "transcript_path": str(principal.transcript)}
    reason = guards.check("Bash", line, {}, cwd=str(tmp_path), session=session)
    assert "installs a synthesis runtime" in reason and "publishes to production" in reason and len(_codes(reason)) == 1, reason
    assert len(principal(reason)) == 2  # one code typed, both requests granted
    assert guards.check("Bash", line, {}, cwd=str(tmp_path), session=session) is None


def test_a_refusal_is_what_the_call_gets_and_nothing_after_it_is_judged():
    def refused():
        return "This is refused."
    verdict = guards._one_code((lambda: f"It waits: type {approvals.how(approvals.request('runtime', {'to': 'a'}, 'x'))}.",
                                refused, lambda: pytest.fail("judged after a refusal")))
    assert verdict == "This is refused."


def test_one_check_that_waits_is_said_as_it_always_was():
    said = f"It waits: type {approvals.how(approvals.request('runtime', {'to': 'a'}, 'x'))}."
    assert guards._one_code((lambda: None, lambda: said, lambda: None)) == said
    assert guards._one_code((lambda: None,)) is None

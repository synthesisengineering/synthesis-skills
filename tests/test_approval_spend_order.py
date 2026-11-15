"""The principal's grant is spent only once his own prompt is found, and finding it reads only the approval window.

2026-11-15: a Codex session's record had grown to 1.9 GB. The principal typed two codes; the guard renamed and deleted
each grant, then read the record from its start for the prompt, which took 4.6 s, past the hook's 4 s deadline. The call
was held and the grant was gone, so the identical retry asked for a new code, and neither call ran."""

import json
import time

import pytest

from synthesis import approvals, guards

from test_approval_provenance import CALL, SID, SLACK, TYPED, _code, _iso, claude


class Deadline(BaseException):
    """What the hook's alarm raises at its deadline (hook._Late): past every `except Exception`."""


def _requested():
    return _code(guards.check(SLACK, CALL, {}))


def _write(path, lines):
    with open(path, "w", encoding="utf-8") as out:
        for line in lines:
            out.write(json.dumps(line) + "\n")


def _old_output(n, when, size=900):
    """Tool output from before the approval window: what a long session's record is mostly made of."""
    return [{"type": "assistant", "timestamp": _iso(when + i * 0.001), "message": {"role": "assistant", "content": [
        {"type": "text", "text": "x" * size}]}} for i in range(n)]


def test_a_grant_survives_a_deadline_that_ends_the_check_mid_read(tmp_path, monkeypatch):
    code = _requested()
    transcript = tmp_path / "t.jsonl"
    _write(transcript, [claude(f"approve {code}", time.time() + 0.01, promptSource="sdk")])
    assert approvals.grant_from_prompt(f"approve {code}")
    session = {"session_id": SID, "transcript_path": str(transcript)}
    real = approvals.typed

    def late(*args, **kwargs):
        raise Deadline()
    monkeypatch.setattr(approvals, "typed", late)
    with pytest.raises(Deadline):
        guards.check(SLACK, CALL, {}, session=session)
    monkeypatch.setattr(approvals, "typed", real)
    assert guards.check(SLACK, CALL, {}, session=session) is None  # the same grant, not a new code
    assert "approval" in guards.check(SLACK, CALL, {}, session=session)  # and it is spent once


def test_the_typed_check_reads_only_the_approval_window_of_a_long_record(tmp_path, monkeypatch):
    now = time.time()
    transcript = tmp_path / "long.jsonl"
    _write(transcript, _old_output(20000, now - 7 * 86400) + [claude("approve 1abc23", now, promptSource="sdk")])
    size, read = transcript.stat().st_size, []

    class Counted:
        def __init__(self, handle):
            self.handle = handle

        def read(self, *args):
            data = self.handle.read(*args)
            read.append(len(data))
            return data

        def __getattr__(self, name):
            return getattr(self.handle, name)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self.handle.close()

    monkeypatch.setattr(approvals, "open", lambda *a, **k: Counted(open(*a, **k)), raising=False)
    assert approvals.typed(str(transcript), "1abc23", now - 60, SID)
    assert sum(read) < size / 4, f"read {sum(read)} of {size} bytes to find a prompt typed a moment ago"


def test_a_code_typed_in_the_window_is_found_behind_later_output(tmp_path):
    now = time.time()
    transcript = tmp_path / "t.jsonl"
    _write(transcript, _old_output(3000, now - 86400) + [claude("approve 1abc23", now - 120, promptSource="sdk")]
           + _old_output(4000, now - 100))
    assert approvals.typed(str(transcript), "1abc23", now - 600, SID)


def test_a_stray_old_line_does_not_end_the_search_early(tmp_path):
    """A record can carry a line stamped long ago after newer ones (a file snapshot, a summary): one such line, or a few,
    never ends the search before the window does."""
    now = time.time()
    transcript = tmp_path / "t.jsonl"
    _write(transcript, [claude("approve 1abc23", now - 30, promptSource="sdk")] + _old_output(50, now - 30 * 86400)
           + _old_output(10, now - 10))
    assert approvals.typed(str(transcript), "1abc23", now - 600, SID)


def test_a_prompt_older_than_the_window_still_does_not_count_in_a_long_record(tmp_path):
    now = time.time()
    transcript = tmp_path / "t.jsonl"
    _write(transcript, [claude("approve 1abc23", now - 3600, promptSource="sdk")] + _old_output(500, now - 1800))
    assert not approvals.typed(str(transcript), "1abc23", now - 900, SID)


@pytest.mark.parametrize("name", ["codex user message", "codex user message, older format", "muse chat intent"])
def test_each_harness_s_prompt_is_found_at_the_end_of_a_long_record(tmp_path, name):
    now = time.time()
    transcript = tmp_path / "t.jsonl"
    old = [{"timestamp": _iso(now - 86400 + i), "type": "response_item", "payload": {
        "type": "function_call_output", "call_id": "c", "output": "y" * 900}} for i in range(5000)]
    _write(transcript, old + [TYPED[name]("approve 1abc23", now)])
    assert approvals.typed(str(transcript), "1abc23", now - 60, SID)


def test_a_grant_changed_while_it_was_checked_is_not_used(tmp_path, monkeypatch):
    """The check and the spend are two steps: a grant file put in place between them was never checked, so it is spent
    and the call is not let through by it."""
    code = _requested()
    transcript = tmp_path / "t.jsonl"
    _write(transcript, [claude(f"approve {code}", time.time() + 0.01, promptSource="sdk")])
    assert approvals.grant_from_prompt(f"approve {code}")
    session = {"session_id": SID, "transcript_path": str(transcript)}
    grant = next(approvals._dir("approvals").glob("*.json"))
    real = approvals.typed

    def swapped(*args, **kwargs):
        found = real(*args, **kwargs)
        data = json.loads(grant.read_text(encoding="utf-8"))
        grant.write_text(json.dumps({**data, "code": "zzz999"}), encoding="utf-8")
        return found
    monkeypatch.setattr(approvals, "typed", swapped)
    assert guards.check(SLACK, CALL, {}, session=session) is not None
    assert not grant.exists()


# --- review round 1 of this fix (2026-11-15) ------------------------------------------------------------------------

def _copied_block(n, when):
    """What compaction appends after the prompt: copies of earlier lines, each with its original time."""
    return [claude(f"an earlier message {i}", when + i * 0.001, promptSource="sdk") for i in range(n)]


@pytest.mark.parametrize("copies", [250, 1000])
def test_a_compaction_block_after_the_prompt_does_not_hide_it(tmp_path, copies):
    """Finding 1: 200 old lines in a row ended the backward search before it reached a prompt typed a minute ago.
    The grant now records where the record ended when the principal typed, and the search reads back to there."""
    code = _requested()
    transcript = tmp_path / "t.jsonl"
    _write(transcript, _old_output(500, time.time() - 86400))
    assert approvals.grant_from_prompt(f"approve {code}", str(transcript))
    with open(transcript, "a", encoding="utf-8") as out:  # the harness writes the prompt, then the work, then a compaction
        out.write(json.dumps(claude(f"approve {code}", time.time(), promptSource="sdk")) + "\n")
        for line in _old_output(20, time.time()) + _copied_block(copies, time.time() - 7200):
            out.write(json.dumps(line) + "\n")
    session = {"session_id": SID, "transcript_path": str(transcript)}
    assert guards.check(SLACK, CALL, {}, session=session) is None
    assert "approval" in guards.check(SLACK, CALL, {}, session=session)


def test_the_prompt_hook_records_where_the_record_ended_when_he_typed(tmp_path):
    code = _requested()
    transcript = tmp_path / "t.jsonl"
    _write(transcript, _old_output(10, time.time() - 60))
    size = transcript.stat().st_size
    assert approvals.grant_from_prompt(f"approve {code}", str(transcript))
    grant = json.loads(next(approvals._dir("approvals").glob("*.json")).read_text(encoding="utf-8"))
    assert grant["record_at"] == size


def test_a_clock_stepped_back_after_the_prompt_does_not_hide_it(tmp_path):
    """Finding 5: lines stamped half an hour before the prompt, written after it, ended the search early."""
    code = _requested()
    transcript = tmp_path / "t.jsonl"
    _write(transcript, [])
    assert approvals.grant_from_prompt(f"approve {code}", str(transcript))
    _write(transcript, [claude(f"approve {code}", time.time(), promptSource="sdk")] + _old_output(400, time.time() - 1800))
    assert guards.check(SLACK, CALL, {}, session={"session_id": SID, "transcript_path": str(transcript)}) is None


def test_a_line_longer_than_the_block_is_read_in_time_proportional_to_its_length(tmp_path):
    """Finding 3: an unfinished line was copied again for each block read before it, so a 128 MB line took 9.9 s."""
    transcript = tmp_path / "t.jsonl"
    transcript.write_text("first\n" + "z" * (2 << 20) + "\nlast\n", encoding="utf-8")
    start = time.perf_counter()
    lines = list(approvals._lines_back(str(transcript), block=256))  # 8,192 blocks for the one long line
    assert time.perf_counter() - start < 1.0
    assert [len(line) for line in lines] == [4, 2 << 20, 5]


@pytest.mark.parametrize("digits, value", [(10, 1794766177), (13, 1794766177000), (16, 1794766177000000)])
def test_a_numeric_time_is_read_by_its_length(digits, value):
    """Finding 4: a 13-digit time in milliseconds was read as microseconds, a moment in 1970."""
    assert len(str(value)) == digits
    assert approvals._stamps(f'{{"timestamp": {value}}}') == [pytest.approx(1794766177, abs=1)]


def test_a_deadline_after_the_grant_was_spent_gives_it_back(tmp_path, monkeypatch, capsys):
    """Finding 2: a later check in the same call ran past the hook's deadline after an earlier one had spent the grant;
    the call was held and the grant was gone. The hook now puts back what that call spent."""
    from synthesis import hook
    code = _requested()
    transcript = tmp_path / "t.jsonl"
    _write(transcript, [])
    assert approvals.grant_from_prompt(f"approve {code}", str(transcript))
    _write(transcript, [claude(f"approve {code}", time.time(), promptSource="sdk")])
    session = {"session_id": SID, "transcript_path": str(transcript)}
    real = guards.check

    def spend_then_run_late(tool, tool_input, config, cwd=None, session=None):
        assert real(tool, tool_input, config, cwd=cwd, session=session) is None  # the grant is spent here
        raise hook._Late()  # and a later check of the same call runs past the deadline
    monkeypatch.setattr(guards, "check", spend_then_run_late)
    payload = {"tool_name": SLACK, "tool_input": CALL, **session}
    hook.pre_tool_use(payload)
    monkeypatch.setattr(guards, "check", real)
    assert "did not answer within" in capsys.readouterr().out
    assert guards.check(SLACK, CALL, {}, session=session) is None  # the same grant, given back
    assert "approval" in guards.check(SLACK, CALL, {}, session=session)


# --- review round 2 of this fix (2026-11-15): a held call's records, the give-back's race, a long prompt line ---------

DEPLOY = "npx wrangler pages deploy dist --project-name=probe-site"


def _granted(tmp_path, reason):
    """The principal types the code a hold asked for; the record shows it."""
    transcript = tmp_path / "t.jsonl"
    if not transcript.exists():
        _write(transcript, [])
    assert approvals.grant_from_prompt(f"approve {_code(reason)}", str(transcript))
    with open(transcript, "a", encoding="utf-8") as out:
        out.write(json.dumps(claude(f"approve {_code(reason)}", time.time(), promptSource="sdk")) + "\n")
    return {"session_id": SID, "transcript_path": str(transcript), "cwd": str(tmp_path)}


def _late_after(monkeypatch, real):
    def decided_then_late(tool, tool_input, config, cwd=None, session=None):
        assert real(tool, tool_input, config, cwd=cwd, session=session) is None
        from synthesis import hook
        raise hook._Late()  # the deadline arrives after the guard decided, before the hook answered
    monkeypatch.setattr(guards, "check", decided_then_late)


def test_a_deploy_held_by_a_later_check_runs_on_its_given_back_grant(tmp_path, monkeypatch, capsys):
    """Round 2, finding 1: the deploy brake recorded the deploy before a later check held the call, so the retry was
    asked for a rapid-redeploy code and the grant given back could not be used."""
    from synthesis import hook
    session = _granted(tmp_path, guards.check("Bash", {"command": DEPLOY}, {}, cwd=str(tmp_path), session={"session_id": SID}))
    real = guards.check_outgoing
    monkeypatch.setattr(guards, "check_outgoing", lambda *a, **k: "held by a later check of the same call")
    hook.pre_tool_use({"tool_name": "Bash", "tool_input": {"command": DEPLOY}, **session})
    assert "held by a later check" in capsys.readouterr().out
    monkeypatch.setattr(guards, "check_outgoing", real)
    assert guards.check("Bash", {"command": DEPLOY}, {}, cwd=str(tmp_path), session=session) is None


def test_a_send_held_after_its_grant_was_used_is_not_in_the_ledger_as_sent(tmp_path, monkeypatch, capsys):
    from synthesis import hook, sends
    session = _granted(tmp_path, guards.check(SLACK, CALL, {}))
    real = guards.check
    _late_after(monkeypatch, real)
    hook.pre_tool_use({"tool_name": SLACK, "tool_input": CALL, **session})
    assert "did not answer within" in capsys.readouterr().out
    monkeypatch.setattr(guards, "check", real)
    assert sends.ledger(time.strftime("%Y-%m-%d")) == []  # nothing went
    assert guards.check(SLACK, CALL, {}, session=session) is None  # it goes once, on the grant given back
    assert len(sends.ledger(time.strftime("%Y-%m-%d"))) == 1


def test_a_window_send_held_after_the_window_let_it_through_leaves_the_window_its_send(tmp_path, monkeypatch, capsys):
    from synthesis import hook, paths, sends
    paths.config_file().parent.mkdir(parents=True, exist_ok=True)
    config = {"send_window_signatures": ["signed probe"]}
    paths.config_file().write_text(json.dumps(config), encoding="utf-8")
    sends.open_window(1.0, ["all"], "", 1)
    call = {"channel_id": "C0PROBE", "message": "A planned note, signed probe."}
    transcript = tmp_path / "t.jsonl"
    _write(transcript, [])
    session = {"session_id": SID, "transcript_path": str(transcript)}
    real = guards.check
    _late_after(monkeypatch, real)
    hook.pre_tool_use({"tool_name": SLACK, "tool_input": call, **session})
    assert "did not answer within" in capsys.readouterr().out
    monkeypatch.setattr(guards, "check", real)
    assert sends.window() and sends.spent(sends.window()) == 0  # the window still has its one send
    assert guards.check(SLACK, call, config, session=session) is None


def test_a_grant_given_back_is_never_seen_half_written(tmp_path, monkeypatch):
    """Round 2, finding 2: the file was created and then written, so an identical call looking in between found an empty
    grant, spent it, and the grant given back was lost. It now appears whole or not at all."""
    session = _granted(tmp_path, guards.check(SLACK, CALL, {}))
    grant = next(approvals._dir("approvals").glob("*.json"))
    body = grant.read_bytes()
    grant.unlink()
    approvals.SPENT[:] = [(grant, body)]
    seen = []
    real_link = approvals.os.link

    def link_and_look(src, dst, *a, **k):
        seen.append(os.path.exists(dst))  # what an identical call would find just before the grant appears
        return real_link(src, dst, *a, **k)
    import os
    monkeypatch.setattr(approvals.os, "link", link_and_look)
    approvals.give_back()
    assert seen == [False] and grant.read_bytes() == body
    assert guards.check(SLACK, CALL, {}, session=session) is None


def test_a_prompt_line_longer_than_the_margin_written_before_the_grant_is_found(tmp_path):
    """Round 2, finding 3: the read stopped inside a prompt line that began more than 16 MB before the recorded position."""
    code = _requested()
    transcript = tmp_path / "t.jsonl"
    _write(transcript, _old_output(10, time.time() - 600) + [claude(f"approve {code} " + "p" * (17 << 20), time.time(), promptSource="sdk")])
    assert approvals.grant_from_prompt(f"approve {code}", str(transcript))  # the hook ran after the line was written
    assert guards.check(SLACK, CALL, {}, session={"session_id": SID, "transcript_path": str(transcript)}) is None


def test_a_grant_voided_by_a_call_that_is_then_held_comes_back(tmp_path, monkeypatch, capsys):
    """A send released by the code for a time in its words voids the ordinary code for the same message; if a later
    check holds the call, nothing went, and the ordinary code is put back."""
    from synthesis import hook
    session = _granted(tmp_path, guards.check(SLACK, CALL, {}))
    grant = next(approvals._dir("approvals").glob("*.json"))
    body = grant.read_bytes()
    real = guards.check

    def voided_then_held(tool, tool_input, config, cwd=None, session=None):
        guards._void("send", {"tool": SLACK, "input": CALL})
        return "held by a later check of the same call"
    monkeypatch.setattr(guards, "check", voided_then_held)
    hook.pre_tool_use({"tool_name": SLACK, "tool_input": CALL, **session})
    assert "held by a later check" in capsys.readouterr().out
    monkeypatch.setattr(guards, "check", real)
    assert grant.read_bytes() == body

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
    seen = []
    real_link = approvals.os.link

    def link_and_look(src, dst, *a, **k):
        seen.append(os.path.exists(dst))  # what an identical call would find just before the grant appears
        return real_link(src, dst, *a, **k)
    import os
    monkeypatch.setattr(approvals.os, "link", link_and_look)
    approvals.put_back([(grant, body)])
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
    monkeypatch.setattr(guards, "check", guards._entry(voided_then_held))  # an entry, as the real check is
    hook.pre_tool_use({"tool_name": SLACK, "tool_input": CALL, **session})
    assert "held by a later check" in capsys.readouterr().out
    monkeypatch.setattr(guards, "check", real)
    assert grant.read_bytes() == body


# --- the hook as the boundary (2026-11-15, after round 2) ------------------------------------------------------------


def test_an_answer_too_late_for_the_harness_keeps_what_the_call_spent(tmp_path, monkeypatch, capsys):
    """A held call gives back what it spent; but an answer later than a harness waits may come after it let the call
    through on its own timeout, so then the call may have run: its grant stays spent and its records stand."""
    import types
    from synthesis import hook, sends
    session = _granted(tmp_path, guards.check(SLACK, CALL, {}))
    real = guards.check
    clock = iter([0.0, hook.GUARD_SECONDS + 1.0])  # the deadline is set at once; the answer comes past it
    monkeypatch.setattr(hook, "time", types.SimpleNamespace(monotonic=lambda: next(clock)))

    def decided_then_held(tool, tool_input, config, cwd=None, session=None):
        assert real(tool, tool_input, config, cwd=cwd, session=session) is None
        return "held by a later check of the same call"
    monkeypatch.setattr(guards, "check", decided_then_held)
    hook.pre_tool_use({"tool_name": SLACK, "tool_input": CALL, **session}, began=0.0)
    assert "held by a later check" in capsys.readouterr().out
    monkeypatch.setattr(guards, "check", real)
    assert len(sends.ledger(time.strftime("%Y-%m-%d"))) == 1  # it may have gone, so it is recorded
    assert "approval" in guards.check(SLACK, CALL, {}, session=session)  # and its grant is not used twice


def test_the_deadline_counts_from_the_hook_process_s_start(monkeypatch):
    """The harness's 5 seconds began before the process: the guard's deadline is the time left of its own 4."""
    import signal
    from synthesis import hook
    seen, real = [], signal.setitimer
    monkeypatch.setattr(signal, "setitimer", lambda which, seconds, *rest: seen.append(seconds) or real(which, 0))
    hook.pre_tool_use({"tool_name": "Read", "tool_input": {"file_path": "/dev/null"}}, began=time.monotonic() - 3.0)
    assert 0.9 < seen[0] <= 1.0 and seen[-1] == 0


def test_a_direct_check_that_fails_after_spending_gives_the_grant_back(tmp_path, monkeypatch):
    """A caller of check() outside the hook: a check that raises after a decision spent a grant held the call."""
    session = _granted(tmp_path, guards.check(SLACK, CALL, {}))
    real = guards._check

    def spent_then_failed(*args):
        assert real(*args) is None
        raise RuntimeError("a later step of the same call failed")
    monkeypatch.setattr(guards, "_check", spent_then_failed)
    with pytest.raises(RuntimeError):
        guards.check(SLACK, CALL, {}, session=session)
    monkeypatch.setattr(guards, "_check", real)
    assert guards.check(SLACK, CALL, {}, session=session) is None


def test_a_prompt_line_that_holds_the_read_s_first_byte_is_read_whole(tmp_path):
    """The read stops inside a line only to finish it: the line before it is not read."""
    path = tmp_path / "t.jsonl"
    path.write_bytes(b"before\n" + b"a" * 50 + b"\nafter\n")
    assert list(approvals._lines_back(str(path), block=8, stop=7 + 20)) == ["after", "a" * 50]
    assert list(approvals._lines_back(str(path), block=8, stop=7)) == ["after", "a" * 50]
    assert list(approvals._lines_back(str(path), block=8, stop=6)) == ["after", "a" * 50, "before"]


# --- review round 3 of this fix (2026-11-15): a check entered from outside the hook, a record that cannot be written, a
# window's send held after another went ---------------------------------------------------------------------------


def test_a_send_the_local_messaging_sender_lets_through_is_recorded(tmp_path):
    """Round 3, finding 1: the sender calls check_send itself, outside the hook; its approved send left no record."""
    from synthesis import sends
    session = _granted(tmp_path, guards.check(SLACK, CALL, {}))
    assert guards.check_send(SLACK, CALL, {}, session=session) is None
    assert len(sends.ledger(time.strftime("%Y-%m-%d"))) == 1


def test_a_window_s_last_send_let_through_by_a_direct_check_closes_it():
    from synthesis import sends
    sends.open_window(1.0, ["all"], "", 1)
    call = {"channel_id": "C0PROBE", "message": "A planned note, signed probe."}
    assert guards.check_send(SLACK, call, {"send_window_signatures": ["signed probe"]}) is None
    assert sends.window() == {} and len(sends.ledger(time.strftime("%Y-%m-%d"))) == 1


def test_every_check_called_from_outside_the_guard_settles_its_records():
    import re
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    named = set()
    for f in [*(root / "synthesis").glob("*.py"), *(root / "skills").rglob("*.py")]:
        if f.name != "guards.py" and "tests" not in f.parts and not f.name.startswith("test_"):
            named |= set(re.findall(r"\bguards\.(check\w*)\(", f.read_text(encoding="utf-8")))
    assert {"check", "check_send"} <= named
    assert [n for n in sorted(named) if not getattr(getattr(guards, n), "settles", False)] == []


def test_a_record_that_cannot_be_written_still_answers_and_holds(tmp_path, monkeypatch, capsys):
    """Round 3, finding 2: an undo that failed ended the hook with no answer, and Claude Code ran the held call."""
    from synthesis import hook
    session = _granted(tmp_path, guards.check(SLACK, CALL, {}))

    def full(allowed):
        raise OSError("no space left on device")
    monkeypatch.setattr(guards, "settle", full)
    hook.pre_tool_use({"tool_name": SLACK, "tool_input": CALL, **session})  # let through by its grant, but unrecorded
    out = capsys.readouterr().out
    assert '"permissionDecision": "deny"' in out and "could not record this call" in out
    hook.pre_tool_use({"tool_name": SLACK, "tool_input": {**CALL, "message": "Another note."}, **session})  # held
    assert '"permissionDecision": "deny"' in capsys.readouterr().out


def test_one_record_that_fails_does_not_stop_the_others(monkeypatch):
    ran, given = [], []

    def fails():
        raise OSError("full")
    guards.EFFECTS[:] = [(None, lambda: ran.append("first")), (None, fails), (None, lambda: ran.append("third"))]
    monkeypatch.setattr(approvals, "put_back", lambda items: given.append(items))
    with pytest.raises(OSError):
        guards.settle(False)
    assert ran == ["third", "first"] and given == [[]] and guards.EFFECTS == []


def test_a_window_s_send_held_after_another_went_is_left_to_the_window(monkeypatch):
    """Round 3, finding 4: two window sends were counted at once; the first went and closed the window, then the second
    was held, and its planned send was lost."""
    from synthesis import sends
    config = {"send_window_signatures": ["signed probe"]}
    sends.open_window(1.0, ["all"], "", 2)
    first, second, third = ({"channel_id": "C0PROBE", "message": f"Note {n}, signed probe."} for n in (1, 2, 3))
    import _thread
    me = _thread.get_ident()
    guards.hook_answers()  # as two hook processes: each decides, then answers
    assert guards.check(SLACK, first, config) is None
    went = guards._PENDING.pop(me)
    assert guards.check(SLACK, second, config) is None
    held = guards._PENDING.pop(me)
    guards.settle(True, *went)
    guards.settle(False, *held)
    guards.answered(True)  # nothing left for it to settle
    assert sends.window() and guards.check(SLACK, third, config) is None
    assert sends.window() == {}  # its last planned send, gone, closes it


def test_the_hook_process_counts_its_deadline_from_its_own_start(monkeypatch, capsys):
    """Run as the hook, the deadline counts from when hook.py loaded, not from when the guard was called."""
    import io
    import runpy
    import signal
    import sys
    from pathlib import Path
    seen, real, clock = [], signal.setitimer, iter([0.0] + [3.0] * 100000)
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.setattr(time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(signal, "setitimer", lambda which, seconds, *rest: seen.append(seconds) or real(which, 0))
    monkeypatch.setattr(sys, "argv", ["hook.py", "pre-tool-use"])
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"tool_name": "Read", "tool_input": {"file_path": "/dev/null"},
                                                              "session_id": SID})))
    with pytest.raises(SystemExit):
        runpy.run_path(str(Path(guards.__file__).with_name("hook.py")), run_name="__main__")
    assert 0.9 < seen[0] <= 1.0


# --- review round 4 of this fix (2026-11-15): threads, state left set, a record that fails after others, the lock ------


def test_a_second_thread_waits_while_one_judges(monkeypatch):
    """Round 4, finding 2: two threads shared the call's records; the second now waits until the first is done, as two
    processes wait at the send lock (CI on b458c09f: refusing it broke two identical calls at once)."""
    import threading
    entered, release, order = threading.Event(), threading.Event(), []
    real = guards._check

    def slow(*args):
        if not entered.is_set():
            entered.set()
            release.wait(5)
        order.append(args[0])
        return real(*args)
    monkeypatch.setattr(guards, "_check", slow)
    first = threading.Thread(target=lambda: guards.check("Read", {"file_path": "/dev/null"}, {}))
    first.start()
    assert entered.wait(5)
    threading.Timer(0.2, release.set).start()
    assert guards.check("Glob", {"pattern": "*"}, {}) is None  # waits for the first, then judges
    first.join(5)
    assert order == ["Read", "Glob"] and guards._DEPTH[0] == 0 and not guards._JUDGING.locked()


def test_a_check_ended_by_an_interrupt_leaves_the_process_judging_as_a_caller(tmp_path, monkeypatch):
    """Round 4, finding 3: an interrupt out of the hook's check left the hook's flag on, so later checks settled nothing."""
    from synthesis import hook, sends

    def interrupted(*args):
        raise KeyboardInterrupt()
    real = guards._check
    monkeypatch.setattr(guards, "_check", interrupted)
    with pytest.raises(KeyboardInterrupt):
        hook.pre_tool_use({"tool_name": SLACK, "tool_input": CALL, "session_id": SID})
    monkeypatch.setattr(guards, "_check", real)
    assert not guards.UNDER_HOOK["on"] and guards._DEPTH[0] == 0 and not guards._JUDGING.locked()
    session = _granted(tmp_path, guards.check(SLACK, CALL, {}))
    assert guards.check_send(SLACK, CALL, {}, session=session) is None
    assert len(sends.ledger(time.strftime("%Y-%m-%d"))) == 1


def test_a_call_held_because_its_record_failed_gives_back_and_undoes(tmp_path, monkeypatch, capsys):
    """Round 4, finding 4: the call was held, but its grant stayed spent and the records before the failure stood."""
    from synthesis import hook, sends
    session = _granted(tmp_path, guards.check(SLACK, CALL, {}))
    real = sends.log

    def full(*args, **kwargs):
        raise OSError("no space left on device")
    monkeypatch.setattr(sends, "log", full)
    hook.pre_tool_use({"tool_name": SLACK, "tool_input": CALL, **session})
    assert "could not record this call" in capsys.readouterr().out
    monkeypatch.setattr(sends, "log", real)
    assert guards.check(SLACK, CALL, {}, session=session) is None  # its grant came back
    assert len(sends.ledger(time.strftime("%Y-%m-%d"))) == 1


def test_a_deploy_record_written_before_a_failing_record_is_put_back(tmp_path):
    record = guards._last_deploy("probe-site")
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text("probe-site\n100.0\n", encoding="utf-8")

    def fails():
        raise OSError("full")
    guards.EFFECTS.clear()
    guards._record_deploys(["probe-site", "other-site"])
    guards._after(fails)
    with pytest.raises(OSError):
        guards.settle(True)
    assert record.read_text(encoding="utf-8") == "probe-site\n100.0\n" and not guards._last_deploy("other-site").exists()


def test_the_send_lock_taken_inside_itself_does_not_wait_for_good():
    """Round 4, finding 5: the lock belongs to the open file, so a second taking in one process waited for ever."""
    import threading
    done = []

    def nested():
        with approvals.alone():
            with approvals.alone():
                done.append(True)
    worker = threading.Thread(target=nested, daemon=True)
    worker.start()
    worker.join(5)
    assert done == [True] and approvals._ALONE[0] == 0


# --- review round 5 of this fix (2026-11-15): the hook and other threads, the send lock's threads, an interrupt just
# after the guard is taken, a deploy recorded meanwhile, an alarm as the deadline ends -------------------------------


def test_a_hook_call_while_another_thread_judges_settles_only_its_own_call(tmp_path, monkeypatch, capsys):
    """Round 5, finding 1: the hook settled another thread's records by its own answer."""
    import threading
    from synthesis import hook, sends
    session = _granted(tmp_path, guards.check(SLACK, CALL, {}))
    entered, release, results = threading.Event(), threading.Event(), []
    real = guards._check

    def slow(*args):
        if not entered.is_set():
            entered.set()
            release.wait(5)
        return real(*args)
    monkeypatch.setattr(guards, "_check", slow)
    other = threading.Thread(target=lambda: results.append(guards.check(SLACK, CALL, {}, session=session)))
    other.start()
    assert entered.wait(5)
    threading.Timer(0.2, release.set).start()
    hook.pre_tool_use({"tool_name": SLACK, "tool_input": {**CALL, "message": "Another note."}, **session})  # no grant
    other.join(5)
    assert '"permissionDecision": "deny"' in capsys.readouterr().out
    assert results == [None] and len(sends.ledger(time.strftime("%Y-%m-%d"))) == 1  # the other thread's send stands


def test_the_send_lock_makes_another_thread_wait():
    """Round 5, finding 2: the lock's nesting count was the process's, so a second thread walked in without the lock."""
    import threading
    inside, release, order = threading.Event(), threading.Event(), []

    def first():
        with approvals.alone():
            inside.set()
            release.wait(5)
            order.append("first")
    worker = threading.Thread(target=first)
    worker.start()
    assert inside.wait(5)
    threading.Timer(0.2, release.set).start()
    with approvals.alone():
        order.append("second")
    worker.join(5)
    assert order == ["first", "second"] and approvals._ALONE == [0, None]


def test_an_interrupt_just_after_the_guard_is_taken_leaves_it_free(monkeypatch):
    """Round 5, finding 3: an exception between taking the guard's lock and the try that frees it left it taken."""
    class Interrupting(list):
        armed = True

        def clear(self):
            if Interrupting.armed:
                Interrupting.armed = False
                raise KeyboardInterrupt()
            super().clear()
    monkeypatch.setattr(approvals, "SPENT", Interrupting())
    with pytest.raises(KeyboardInterrupt):
        guards.check("Read", {"file_path": "/dev/null"}, {})
    assert not guards._JUDGING.locked() and guards._DEPTH == [0, None]


def test_a_deploy_recorded_by_another_call_meanwhile_is_kept_when_this_one_is_put_back():
    """Round 5, finding 4: putting back this call's deploy record erased a deploy another call recorded meanwhile."""
    record = guards._last_deploy("probe-site")
    guards.EFFECTS.clear()
    guards._record_deploys(["probe-site"])
    write, restore = guards.EFFECTS[0]
    write()
    record.write_text("probe-site\n200.0\n", encoding="utf-8")  # another call's deploy
    restore()
    guards.EFFECTS.clear()
    assert record.read_text(encoding="utf-8") == "probe-site\n200.0\n"


def test_an_alarm_landing_as_the_deadline_is_taken_down_still_holds(monkeypatch, capsys):
    """Round 5, a note (the same since 5.21.0): an alarm in the moment the deadline was being taken down escaped the
    hook with no answer, and Claude Code ran the call."""
    import signal
    from synthesis import hook
    real = signal.setitimer

    def lands(which, seconds, *rest):
        real(which, 0)
        if seconds == 0:
            raise hook._Late()
    monkeypatch.setattr(signal, "setitimer", lands)
    hook.pre_tool_use({"tool_name": "Read", "tool_input": {"file_path": "/dev/null"}, "session_id": SID})
    assert "did not answer within" in capsys.readouterr().out


# --- review round 6 of this fix (2026-11-15): re-entry while settling, a finally cut short, the send lock's order -------


def test_a_record_that_enters_the_guard_while_it_settles_is_refused_not_waited_for(monkeypatch):
    """Round 6, finding 1: a commit that called back into the guard waited for ever on a lock its own thread held."""
    import threading
    real, outcome = guards._check, []

    def queues_a_reentry(*args):
        guards._after(lambda: guards.check("Read", {"file_path": "/dev/null"}, {}))
        return real(*args)
    monkeypatch.setattr(guards, "_check", queues_a_reentry)

    def call():
        try:
            outcome.append(guards.check("Read", {"file_path": "/dev/null"}, {}))
        except RuntimeError as exc:
            outcome.append(str(exc))
    worker = threading.Thread(target=call, daemon=True)
    worker.start()
    worker.join(5)
    assert outcome and "while it settles" in str(outcome[0]) and not guards._JUDGING.locked()


def test_a_check_cut_short_in_its_own_finally_still_gives_the_grant_back(tmp_path, monkeypatch, capsys):
    """Round 6, finding 2: the alarm landing in the check's own finally, before it handed its records to the hook, left
    the call held with its grant spent."""
    from synthesis import hook
    session = _granted(tmp_path, guards.check(SLACK, CALL, {}))

    class CutShort(list):
        armed = True

        def __iter__(self):
            if CutShort.armed and guards.UNDER_HOOK["on"]:
                CutShort.armed = False
                raise hook._Late()
            return super().__iter__()
    monkeypatch.setattr(approvals, "SPENT", CutShort())
    hook.pre_tool_use({"tool_name": SLACK, "tool_input": CALL, **session})
    assert "did not answer within" in capsys.readouterr().out
    monkeypatch.setattr(approvals, "SPENT", [])  # never monkeypatch.undo(): it would also take the test's own home away
    assert not guards._JUDGING.locked() and guards.check(SLACK, CALL, {}, session=session) is None


def test_a_check_entered_inside_the_send_lock_is_refused_not_waited_for():
    """Round 6, finding 3: a thread inside the send lock entering a check could wait on a thread that waits for the lock."""
    with approvals.alone():
        with pytest.raises(RuntimeError, match="inside the send lock"):
            guards.check("Read", {"file_path": "/dev/null"}, {})
    assert not guards._JUDGING.locked()


def test_records_a_call_left_with_no_answer_stand_when_its_thread_judges_again():
    """A thread's hook call that never answered may have let its call run: its records stand, its grants stay spent."""
    import _thread
    ran = []
    guards._PENDING[_thread.get_ident()] = ([(lambda: ran.append("commit"), lambda: ran.append("undo"))], [])
    guards.hook_answers()
    guards.answered(True)
    assert ran == ["commit"] and _thread.get_ident() not in guards._PENDING


def test_the_hook_s_answer_frees_the_guard_its_check_left_taken():
    """Round 7, finding 1: an interrupt after the check handed its records over and before it freed the guard left the
    lock taken, so a process that went on would wait for good at its next check."""
    import _thread
    me = _thread.get_ident()
    assert guards._JUDGING.acquire(False)
    guards._DEPTH[0], guards._DEPTH[1] = 1, me
    guards._PENDING[me] = ([], [])
    guards.answered(True)
    assert not guards._JUDGING.locked() and guards._DEPTH == [0, None] and guards._SETTLING == [None]

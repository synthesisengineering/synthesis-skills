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

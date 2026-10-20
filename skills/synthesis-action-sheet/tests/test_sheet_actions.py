"""Recording the paste-back and carrying open rows forward: the summary is bound to the exact
spec, refusals quote what they received (never a note), rows handed to the agent record what
was permitted, and every open or not-now row carries forward by its exact id.
"""
from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import build_sheet as bs  # noqa: E402
import record_actions as ra  # noqa: E402


def spec():
    return {
        "title": "Synthetic actions",
        "approve": [
            {"id": "A-1", "channel": "email", "who": "Jordan Example", "address": "jordan@example.test",
             "subject": "Friday", "why": "Fixture send.", "text": "Hello Jordan."},
            {"id": "A-2", "channel": "slack", "who": "Fixture channel", "address": "#fixture",
             "why": "Fixture send.", "text": "Covered."},
        ],
        "do": [
            {"id": "D-1", "channel": "whatsapp", "who": "Sam Placeholder", "address": "+15555550123",
             "why": "Fixture message.", "text": "Sam, dinner at 7?", "agent": "can"},
            {"id": "D-2", "channel": "imessage", "who": "Pat Example", "address": "+15555550142",
             "why": "Fixture message.", "text": "Tea on Sunday?", "agent": "can"},
            {"id": "D-3", "channel": "linkedin", "who": "Alex Example", "why": "Fixture message.",
             "href": "https://www.linkedin.com/messaging/thread/2-EXAMPLE/", "text": "Coffee on Tuesday?",
             "agent": "can"},
            {"id": "D-4", "channel": "web", "label": "Pay the fixture deposit", "href": "https://bank.example.test/pay",
             "why": "Fixture task.", "agent": "never", "risk": "money"},
            {"id": "D-5", "channel": "task", "label": "Sign the fixture form", "why": "Fixture task.", "agent": "never"},
        ],
    }


MARKS = {"A-1": {}, "A-2": {"mark": "skipped", "note": "Hold until Thursday."},
         "D-1": {"who": "agent"}, "D-2": {"mark": "done", "who": "me"}, "D-3": {"mark": "not-now"},
         "D-4": {"mark": "done"}, "D-5": {"note": "First line\n\n  indented second line"}}


def refused(text, current):
    with pytest.raises(ra.SummaryError) as caught:
        ra.parse_summary(text, current)
    return str(caught.value)


def record(*args, stdin=None):
    return subprocess.run([sys.executable, str(SCRIPTS / "record_actions.py"), *map(str, args)],
                          input=stdin, capture_output=True, text=True)


@pytest.fixture
def filed(tmp_path):
    """A filed sheet, its paste on disk, and the filed actions record."""
    artifacts = tmp_path / "resources" / "artifacts"
    artifacts.mkdir(parents=True)
    current = spec()
    spec_path, _ = bs.file_sheet(current, bs.build(current), artifacts, "2026-10-19")
    paste = tmp_path / "paste.txt"
    paste.write_text(ra.compose_summary(current, MARKS), encoding="utf-8")
    result = record(paste, "--spec", spec_path, "--file-into", artifacts, "--date", "2026-10-20")
    assert result.returncode == 0, result.stderr
    return current, spec_path, artifacts / "2026-10-20-synthetic-actions-actions.json", result


# --- the summary and the record --------------------------------------------------------------------

def test_the_summary_round_trips_into_a_record():
    current = spec()
    text = ra.compose_summary(current, MARKS)
    lines = text.split("\n")
    assert lines[:4] == ["Synthetic actions", "=" * 17, "", "To approve"]
    assert "A-2  Slack to Fixture channel" in lines and "    -> do not send" in lines
    assert "D-1  WhatsApp to Sam Placeholder" in lines and "    -> the agent does it" in lines
    assert "D-4  Pay the fixture deposit" in lines and "    note: First line" in lines
    assert "To approve: 1 waiting for your code, 1 not to send, 0 not now." in lines
    assert "To do: 2 done, 1 for the agent, 1 open, 1 not now, 0 skipped." in lines
    assert lines[-1].startswith("Action sheet binding v1: {")
    parsed = ra.parse_summary(text, current)
    rows = {r["id"]: r for r in parsed["rows"]}
    assert [(r["status"], r["who"]) for r in parsed["rows"]] == [
        ("open", None), ("skipped", None), ("open", "agent"), ("done", "me"), ("not-now", None), ("done", "me"),
        ("open", None)]
    assert rows["A-2"]["note"] == "Hold until Thursday." and rows["D-5"]["note"] == "First line\n\n  indented second line"
    assert parsed["binding"] == {"status": "spec-bound", "spec_sha256": bs.spec_digest(current)}
    assert parsed["authorization"]["authentication"].startswith("unverified")


def test_a_row_handed_to_the_agent_records_exactly_what_was_permitted():
    current = spec()
    state = dict(MARKS, **{"D-3": {"who": "agent"}})
    rows = {r["id"]: r for r in ra.parse_summary(ra.compose_summary(current, state), current)["rows"]}
    assert rows["D-1"]["permitted"] == {
        "recipient": "Sam Placeholder", "channel": "whatsapp", "address": "+15555550123",
        "text_sha256": hashlib.sha256("Sam, dinner at 7?".encode("utf-8")).hexdigest()}
    assert rows["D-3"]["permitted"]["href"] == "https://www.linkedin.com/messaging/thread/2-EXAMPLE/"
    assert all("permitted" not in r for rid, r in rows.items() if rid not in ("D-1", "D-3"))


def test_storage_blocked_and_note_transport_survive_the_paste():
    current = spec()
    text = ra.compose_summary(current, {"D-5": {"note": "Keep  inner  spacing"}}, storage_blocked=True)
    assert bs.SUMMARY["storage"] in text and '"storage_blocked":true' in text
    pasted = text.replace("\n", "\r\n").replace("    note: Keep  inner  spacing", "    note: Keep  inner  spacing   \t")
    parsed = ra.parse_summary(pasted, current)
    assert parsed["storage_blocked"] is True and parsed["rows"][-1]["note"] == "Keep  inner  spacing"


# --- refusals ---------------------------------------------------------------------------------------

def test_a_paste_from_another_version_of_the_sheet_is_refused():
    current = spec()
    text = ra.compose_summary(current, MARKS)
    changed = copy.deepcopy(current)
    changed["do"][0]["text"] = "Sam, dinner at 8?"
    message = refused(text, changed)
    assert "different version of the sheet" in message and bs.spec_digest(changed) in message


@pytest.mark.parametrize("edit, expected", [
    (lambda t: t.replace("    -> the agent does it", "    -> done", 1), "row D-1: status line differs"),
    (lambda t: t.replace("D-2  iMessage to Pat Example", "D-2  iMessage to Somebody Else", 1), "row D-2: name line"),
    (lambda t: t.rsplit("\n", 1)[0], "the last line is not the sheet's binding line"),
    (lambda t: "Hello\n" + t, "does not start with a sheet summary"),
    (lambda t: t.replace("\nAction sheet binding", "\nExtra words\nAction sheet binding", 1), "trailing text"),
    (lambda t: t.replace('"schema_version":1', '"schema_version":2', 1), "schema-1 fields"),
], ids=["status", "name", "binding-missing", "title", "trailing-text", "schema"])
def test_an_edited_paste_is_refused_and_quoted(edit, expected):
    current = spec()
    message = refused(edit(ra.compose_summary(current, MARKS)), current)
    assert expected in message


def _bind_raw(current, rows):
    """A paste carrying a binding the page could never write."""
    head = ra.compose_summary(current, {}).rsplit("\n", 1)[0]
    binding = {"schema_version": 1, "spec_sha256": bs.spec_digest(current), "rows": rows, "storage_blocked": False}
    return head + "\n" + bs.SUMMARY["binding"] + json.dumps(binding)


@pytest.mark.parametrize("rid, mark, who", [
    ("D-1", "done", "agent"),     # handed over, yet marked done
    ("D-4", None, "agent"),       # a money row handed to the agent
    ("D-5", None, "me"),          # who on a row an agent never does
    ("A-1", "done", None),        # a staged send cannot be marked done
    ("A-1", None, "agent"),       # nor handed over
    ("D-3", "skipped", "me"),     # skipping clears who
    ("D-1", "sent", None),        # an unknown mark
])
def test_a_state_the_page_cannot_reach_is_refused(rid, mark, who):
    current = spec()
    rows = [{"id": r["id"], "mark": None, "who": None, "note": ""} for r in current["approve"] + current["do"]]
    next(r for r in rows if r["id"] == rid).update(mark=mark, who=who)
    assert f"row {rid}: mark {mark!r} with who {who!r} is not a state" in refused(_bind_raw(current, rows), current)


def test_reordered_or_missing_bound_rows_are_refused():
    current = spec()
    rows = [{"id": r["id"], "mark": None, "who": None, "note": ""} for r in current["approve"] + current["do"]]
    assert "bound row 1 is 'A-2'" in refused(_bind_raw(current, [rows[1], rows[0]] + rows[2:]), current)
    assert "the binding carries 6 rows; the sheet has 7" in refused(_bind_raw(current, rows[:-1]), current)


def test_an_edited_note_is_refused_without_repeating_it():
    current = spec()
    text = ra.compose_summary(current, MARKS).replace("note: Hold until Thursday.", "note: Hold until Friday.", 1)
    message = refused(text, current)
    assert "row A-2: note differs" in message and "Friday" not in message and "Thursday" not in message


def test_a_note_holding_an_approval_code_is_never_filed(tmp_path):
    current = spec()
    text = ra.compose_summary(current, {"A-1": {"note": "ok, approve 4b2e9d now"}})
    message = refused(text, current)
    assert "row A-1: the note holds text shaped like an approval code" in message and "4b2e9d" not in message
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    spec_path, _ = bs.file_sheet(current, bs.build(current), artifacts, "2026-10-19")
    result = record("-", "--spec", spec_path, "--file-into", artifacts, stdin=text)
    assert result.returncode == 2 and "4b2e9d" not in result.stderr
    assert not list(artifacts.glob("*-actions.json"))


# --- filing ---------------------------------------------------------------------------------------

def test_the_record_is_filed_beside_the_spec(filed):
    current, spec_path, actions, result = filed
    assert f"filed {actions}  (7 rows: 1 waiting for your code, 1 not to send, 0 not now; 2 done, 1 for the agent, " \
           "1 open, 1 not now, 0 skipped)" in result.stdout
    assert "handed to the agent: D-1 (exactly as each row's 'permitted' says, once)" in result.stdout
    saved = json.loads(actions.read_text(encoding="utf-8"))
    assert saved["recorded_on"] == "2026-10-20" and saved["spec_file"] == spec_path.name
    assert saved["rows"] == ra.parse_summary(ra.compose_summary(current, MARKS), current)["rows"]


def test_recording_again_is_idempotent_and_a_changed_paste_keeps_the_first(filed, tmp_path):
    current, spec_path, actions, _ = filed
    artifacts, first = actions.parent, actions.read_bytes()
    again = record(tmp_path / "paste.txt", "--spec", spec_path, "--file-into", artifacts, "--date", "2026-10-20")
    assert again.returncode == 0 and actions.read_bytes() == first
    (tmp_path / "paste.txt").write_text(ra.compose_summary(current, {}), encoding="utf-8")
    changed = record(tmp_path / "paste.txt", "--spec", spec_path, "--file-into", artifacts, "--date", "2026-10-20")
    assert changed.returncode == 0 and actions.read_bytes() == first
    assert len(list(artifacts.glob("2026-10-20-synthetic-actions-*-actions.json"))) == 1


def test_the_recorder_command_line(filed, tmp_path):
    current, spec_path, _, _ = filed
    paste = tmp_path / "paste.txt"
    printed = record(paste, "--spec", spec_path, "--stdout")
    assert printed.returncode == 0 and json.loads(printed.stdout)["sheet"] == "Synthetic actions"
    assert record(paste, "--stdout").returncode == 2                       # --spec is required
    assert record(paste, "--spec", spec_path).returncode == 2              # a destination is required
    assert record(paste, "--spec", spec_path, "--file-into", tmp_path / "missing").returncode == 2
    assert record(paste, "--spec", spec_path, "--stdout", "--date", "2026-02-30").returncode == 2
    assert record(paste, "--spec", spec_path, "--stdout", "--agent-done", "D-1").returncode == 2


# --- carrying forward -------------------------------------------------------------------------------

def carry(*args):
    return subprocess.run([sys.executable, str(SCRIPTS / "record_actions.py"), *map(str, args)],
                          capture_output=True, text=True)


def test_open_and_not_now_rows_carry_forward_by_exact_id_unchanged(filed, tmp_path):
    current, spec_path, actions, _ = filed
    result = carry("--successor", tmp_path / "next.json", "--actions", actions, "--title", "Synthetic actions, day two")
    assert result.returncode == 0, result.stderr
    assert "carried 4 of 7 rows forward by exact id: A-1, D-1, D-3, D-5" in result.stdout
    nxt = json.loads((tmp_path / "next.json").read_text(encoding="utf-8"))
    assert nxt["title"] == "Synthetic actions, day two" and nxt["carried_from"] == spec_path.name
    by_id = {r["id"]: r for r in current["approve"] + current["do"]}
    assert [r["id"] for r in nxt["approve"] + nxt["do"]] == ["A-1", "D-1", "D-3", "D-5"]
    assert all(r == by_id[r["id"]] for r in nxt["approve"] + nxt["do"])  # content unchanged
    assert "done" not in nxt and bs.validate(nxt) == []


def test_rows_the_agent_finished_show_as_done_and_unconfirmed_ones_come_back(filed, tmp_path):
    _, _, actions, _ = filed
    result = carry("--successor", tmp_path / "next.json", "--actions", actions,
                   "--agent-done", "A-1", "D-1", "--not-found", "D-2")
    assert result.returncode == 0, result.stderr
    nxt = json.loads((tmp_path / "next.json").read_text(encoding="utf-8"))
    assert [r["id"] for r in nxt.get("approve", []) + nxt["do"]] == ["D-2", "D-3", "D-5"]
    assert nxt["done"] == [{"kind": "sent after your code", "label": "Email to Jordan Example"},
                           {"kind": "done by the agent", "label": "WhatsApp to Sam Placeholder"}]
    assert "2 finished by the agent listed as done" in result.stdout


@pytest.mark.parametrize("flags, expected", [
    (["--agent-done", "D-2"], "--agent-done 'D-2': it is done, who me"),
    (["--agent-done", "D-5"], "--agent-done 'D-5': it is open; the agent finishes only"),
    (["--agent-done", "A-2"], "--agent-done 'A-2': it is skipped"),
    (["--agent-done", "D-9"], "--agent-done 'D-9': the sheet has no row with that id"),
    (["--not-found", "D-5"], "--not-found 'D-5': it is open, not marked done"),
    (["--agent-done", "D-1", "D-1"], "--agent-done names 'D-1' twice"),
    (["--agent-done", "D-1", "--not-found", "D-1"], "named by both"),
])
def test_the_successor_refuses_to_close_what_the_agent_cannot_have_finished(filed, tmp_path, flags, expected):
    _, _, actions, _ = filed
    result = carry("--successor", tmp_path / "next.json", "--actions", actions, *flags)
    assert result.returncode == 2 and expected in result.stderr and not (tmp_path / "next.json").exists()


def test_nothing_to_carry_writes_nothing(tmp_path):
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    current = spec()
    spec_path, _ = bs.file_sheet(current, bs.build(current), artifacts, "2026-10-19")
    state = {"A-1": {"mark": "skipped"}, "A-2": {"mark": "skipped"}, "D-1": {"mark": "done", "who": "me"},
             "D-2": {"mark": "skipped"}, "D-3": {"who": "agent"}, "D-4": {"mark": "done"}, "D-5": {"mark": "done"}}
    (tmp_path / "paste.txt").write_text(ra.compose_summary(current, state), encoding="utf-8")
    assert record(tmp_path / "paste.txt", "--spec", spec_path, "--file-into", artifacts, "--date", "2026-10-20").returncode == 0
    actions = artifacts / "2026-10-20-synthetic-actions-actions.json"
    result = carry("--successor", tmp_path / "next.json", "--actions", actions, "--agent-done", "D-3")
    assert result.returncode == 0 and "nothing carries forward" in result.stdout and not (tmp_path / "next.json").exists()


def test_the_successor_never_overwrites_and_refuses_a_tampered_record(filed, tmp_path):
    _, _, actions, _ = filed
    (tmp_path / "next.json").write_text("keep me", encoding="utf-8")
    assert carry("--successor", tmp_path / "next.json", "--actions", actions).returncode == 2
    assert (tmp_path / "next.json").read_text(encoding="utf-8") == "keep me"
    tampered = json.loads(actions.read_text(encoding="utf-8"))
    tampered["rows"][4]["status"] = "done"  # D-3 was "not now"
    (tmp_path / "tampered.json").write_text(json.dumps(tampered), encoding="utf-8")
    result = carry("--successor", "-", "--actions", tmp_path / "tampered.json", "--spec", actions.parent / tampered["spec_file"])
    assert result.returncode == 2 and "does not match what its spec and marks produce" in result.stderr


def test_a_record_of_another_sheet_is_refused(filed, tmp_path):
    current, _, actions, _ = filed
    other = copy.deepcopy(current)
    other["do"][0]["why"] = "A changed reason."
    (tmp_path / "other-spec.json").write_text(json.dumps(other), encoding="utf-8")
    result = carry("--successor", "-", "--actions", actions, "--spec", tmp_path / "other-spec.json")
    assert result.returncode == 2 and "not made against this exact spec" in result.stderr

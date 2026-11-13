"""A test's teardown list: what a test set up is written down as it is made, and taken off when it is gone.

2026-11-12: a test connector was stopped, and what had been set up around it stayed: an entry in a client's config
that pointed at the dead address, and a key marked for removal after the test. Nothing had recorded either as it was
made, so there was no list to run, and nothing that would say so the next day. The list is written by whoever sets a
thing up; `synthesis doctor` reads it at every day-start, in whichever session.
"""

import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "teardown.py"
spec = importlib.util.spec_from_file_location("teardown", SCRIPT)
teardown = importlib.util.module_from_spec(spec)
spec.loader.exec_module(teardown)


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("SYNTHESIS_HOME", str(tmp_path / "home"))
    return tmp_path / "home"


def rows(home: Path) -> list:
    return [json.loads(line) for line in (home / "teardown.jsonl").read_text(encoding="utf-8").split("\n") if line]


def left(capsys) -> list:
    """The numbers `list` shows as still in place."""
    capsys.readouterr()
    assert teardown.main(["list"]) == 0
    return [int(line.split()[0]) for line in capsys.readouterr().out.splitlines() if line.split()[0].isdigit()]


def test_each_thing_a_test_sets_up_is_added_with_how_it_is_removed(home, capsys):
    assert teardown.main(["add", "the client's connector entry for the test address", "--remove", "delete it in the client's settings",
                          "--test", "connector test"]) == 0
    assert teardown.main(["add", "a key marked for removal", "--remove", "revoke it in the console"]) == 0
    said = capsys.readouterr().out.splitlines()
    assert said[0].startswith("1 ") and said[1].startswith("2 ")                      # each answers with the number that takes it off
    first, second = rows(home)
    assert (first["id"], first["what"], first["remove"], first["test"]) == (1, "the client's connector entry for the test address",
                                                                          "delete it in the client's settings", "connector test")
    assert second["id"] == 2 and second["test"] == ""
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d", first["at"])   # read from the clock, with its zone


def test_how_it_is_removed_must_be_said(home, capsys):
    for words in (["add", "an entry"], ["add", "an entry", "--remove", ""], ["add", "", "--remove", "delete it"], ["add"]):
        with pytest.raises(SystemExit) as stopped:
            teardown.main(words)
        assert stopped.value.code == 2, words
    assert not (home / "teardown.jsonl").exists()


def test_the_list_says_what_is_left_and_one_number_takes_one_thing_off(home, capsys):
    assert teardown.main(["list"]) == 0 and "nothing" in capsys.readouterr().out
    for what in ("an entry", "a key", "a tunnel"):
        teardown.main(["add", what, "--remove", f"remove {what}", "--test", "t1"])
    capsys.readouterr()
    assert teardown.main(["list"]) == 0
    listed = capsys.readouterr().out.splitlines()
    assert len(listed) == 3 and all(f"remove {what}" in line and what in line for what, line in zip(("an entry", "a key", "a tunnel"), listed))
    assert teardown.main(["done", "2"]) == 0
    assert "a key" in capsys.readouterr().out                                         # it says what it took off
    assert left(capsys) == [1, 3]
    assert teardown.main(["done", "2"]) == 1 and "2" in capsys.readouterr().err       # nothing open by that number: nothing is taken off
    assert teardown.main(["done", "9"]) == 1 and left(capsys) == [1, 3]
    for number in ("1", "3"):
        assert teardown.main(["done", number]) == 0
    capsys.readouterr()
    assert teardown.main(["list"]) == 0 and "nothing" in capsys.readouterr().out


def test_a_number_is_never_given_twice_and_nothing_written_is_ever_rewritten(home, capsys):
    """A review, 2026-11-13: taking the highest number off gave it to the next thing added, and every `add` and
    `done` wrote the whole file again, so a line someone had written by hand could be split or changed. The list is
    a log: `add` and `done` each append one line."""
    for what in ("an entry", "a key"):
        teardown.main(["add", what, "--remove", "remove it"])
    before = (home / "teardown.jsonl").read_bytes()
    assert teardown.main(["done", "2"]) == 0
    teardown.main(["add", "a tunnel", "--remove", "stop it"])
    after = (home / "teardown.jsonl").read_bytes()
    assert after.startswith(before) and after.count(b"\n") == 4                       # two lines more, and the first two as they were
    assert rows(home)[2]["done"] == 2 and rows(home)[3]["id"] == 3 and left(capsys) == [1, 3]


def test_a_line_someone_wrote_by_hand_is_kept_and_shown(home, capsys):
    (home).mkdir(parents=True)
    hand = 'remember the DNS record\n{"id": 7, "what": "an entry\u2028two", "remove": "delete it", "at": "2026-11-12T10:00:00-05:00", "test": ""}\n'
    (home / "teardown.jsonl").write_text(hand, encoding="utf-8")
    assert teardown.main(["list"]) == 0
    listed = capsys.readouterr().out
    assert "?  remember the DNS record" in listed and "7  " in listed and "an entry?two" in listed    # a line separator is shown as a mark, not obeyed
    teardown.main(["add", "a key", "--remove", "revoke it"])
    assert (home / "teardown.jsonl").read_text(encoding="utf-8").startswith(hand)     # as it was written, to the byte
    assert rows_after(home)[-1] == 8 and left(capsys) == [7, 8]
    assert teardown.main(["done", "7"]) == 0 and left(capsys) == [8]
    capsys.readouterr()
    teardown.main(["list"])
    assert "?  remember the DNS record" in capsys.readouterr().out                    # only a hand takes a hand-written line out


def rows_after(home: Path) -> list:
    out = []
    for line in (home / "teardown.jsonl").read_text(encoding="utf-8").split("\n"):
        try:
            out.append(json.loads(line).get("id"))
        except ValueError:
            out.append(line)
    return [row for row in out if row not in ("", None)]


@pytest.mark.parametrize("start", [b"\xff\xfe a note saved in another encoding\n", b"\xef\xbb\xbf", b"   \n\t\n"],
                         ids=["bad-bytes", "byte-order-mark", "blank-lines"])
def test_a_list_with_bytes_that_are_no_text_or_a_mark_or_blank_lines_is_still_read_and_written(start, home, capsys):
    """A review, 2026-11-13: one byte that is not UTF-8 ended every command in a traceback, so the list could not be
    repaired with its own commands; a byte order mark made the first item a line that is none; a line of spaces was
    shown as one."""
    home.mkdir(parents=True)
    item = b'{"id": 1, "what": "an entry", "remove": "delete it", "at": "2026-11-12T10:00:00-05:00", "test": ""}\n'
    (home / "teardown.jsonl").write_bytes(start + item)
    assert left(capsys) == [1]
    assert teardown.main(["add", "a key", "--remove", "revoke it"]) == 0 and left(capsys) == [1, 2]
    assert teardown.main(["done", "1"]) == 0 and left(capsys) == [2]
    assert (home / "teardown.jsonl").read_bytes().startswith(start + item)
    capsys.readouterr()
    teardown.main(["list"])
    shown = capsys.readouterr().out.splitlines()
    assert len(shown) == (2 if start.startswith(b"\xff") else 1)                      # the note in another encoding is a line that is no item


def test_a_line_of_data_that_is_no_item_is_shown_as_one_and_takes_no_number(home, capsys):
    home.mkdir(parents=True)
    (home / "teardown.jsonl").write_text('[1]\nnull\n5\n{"id": true, "what": "x", "remove": "y"}\n{"id": 1.0, "what": "x"}\n{"id": 2}\n', encoding="utf-8")
    assert left(capsys) == []
    capsys.readouterr()
    assert teardown.main(["list"]) == 0
    shown = capsys.readouterr().out.splitlines()
    assert len(shown) == 6 and all(line.startswith("?  ") for line in shown)
    assert teardown.main(["done", "1"]) == 1 and teardown.main(["done", "2"]) == 1
    capsys.readouterr()
    assert teardown.main(["add", "a key", "--remove", "revoke it"]) == 0 and capsys.readouterr().out.startswith("1 ")


def test_what_a_terminal_would_obey_is_never_printed(home, capsys):
    """A review, 2026-11-13: `what` was printed as written, and an escape sequence in it reached the terminal (one
    that sets the clipboard was tried)."""
    assert teardown.main(["add", "an entry\x1b]52;c;eA==\x07 for the test", "--remove", "delete\x1b[2J it"]) == 0
    assert "\x1b" not in capsys.readouterr().out
    (row,) = rows(home)
    assert "\x1b" not in row["what"] + row["remove"] and row["what"].startswith("an entry") and row["what"].endswith("for the test")
    with open(home / "teardown.jsonl", "a", encoding="utf-8") as more:
        more.write('by hand \x1b[31m in red\n{"id": 5, "what": "a \\u001b[2J key", "remove": "revoke", "at": "x", "test": "t\\u0007"}\n')
    capsys.readouterr()
    assert teardown.main(["list"]) == 0
    shown = capsys.readouterr().out
    assert "\x1b" not in shown and "\x07" not in shown and "by hand ?[31m in red" in shown and "a ?[2J key" in shown


def test_nothing_is_said_to_be_written_that_was_not(home, capsys):
    """A review, 2026-11-13: with a folder where the list should be, `add` printed its line and then failed, and
    `list` said nothing was left in place."""
    (home / "teardown.jsonl").mkdir(parents=True)
    for words in (["add", "a key", "--remove", "revoke it"], ["list"], ["done", "1"]):
        assert teardown.main(words) == 1, words
        said = capsys.readouterr()
        assert said.out == "" and "teardown.jsonl" in said.err and len(said.err.strip().splitlines()) == 1 and "Traceback" not in said.err


def test_a_link_that_leads_nowhere_is_a_list_that_cannot_be_read(home, capsys):
    home.mkdir(parents=True)
    (home / "teardown.jsonl").symlink_to(home / "gone" / "list.jsonl")
    assert teardown.main(["list"]) == 1
    said = capsys.readouterr()
    assert said.out == "" and "cannot be read" in said.err


@pytest.mark.skipif(not hasattr(os, "geteuid") or os.geteuid() == 0, reason="the superuser writes anywhere")
def test_the_list_is_read_where_nothing_can_be_written(home, capsys):
    """A review, 2026-11-13: `list` made a lock file before it read, so in a home that cannot be written it ended in
    a traceback."""
    teardown.main(["add", "a key", "--remove", "revoke it"])
    os.chmod(home, 0o500)
    try:
        assert left(capsys) == [1]
        assert teardown.main(["add", "another", "--remove", "remove it"]) in (0, 1)   # the list itself may still take a line
    finally:
        os.chmod(home, 0o700)


def test_things_added_at_the_same_moment_each_get_their_own_number(home):
    runs = [subprocess.Popen([sys.executable, str(SCRIPT), "add", f"thing {n}", "--remove", "remove it"], stdout=subprocess.PIPE,
                             env={**os.environ, "SYNTHESIS_HOME": str(home)}) for n in range(12)]
    said = sorted(int(run.communicate()[0].split()[0]) for run in runs)
    assert said == list(range(1, 13)) and sorted(row["id"] for row in rows(home)) == said

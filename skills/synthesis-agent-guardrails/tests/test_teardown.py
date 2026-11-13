"""A test's teardown list: what a test set up is written down as it is made, and taken off when it is gone.

2026-11-12: a test connector was stopped, and what had been set up around it stayed: an entry in a client's config
that pointed at the dead address, and a key marked for removal after the test. Nothing had recorded either as it was
made, so there was no list to run, and nothing that would say so the next day. The list is written by whoever sets a
thing up; `synthesis doctor` reads it at every day-start, in whichever session.
"""

import importlib.util
import json
import re
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
    return [json.loads(line) for line in (home / "teardown.jsonl").read_text(encoding="utf-8").splitlines()]


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
    assert [row["id"] for row in rows(home)] == [1, 3]
    assert teardown.main(["done", "2"]) == 1 and "2" in capsys.readouterr().err       # nothing by that number: nothing is taken off
    assert [row["id"] for row in rows(home)] == [1, 3]
    teardown.main(["add", "one more", "--remove", "remove it"])
    assert [row["id"] for row in rows(home)] == [1, 3, 4]                             # a number is not given twice while the list lives
    for number in ("1", "3", "4"):
        assert teardown.main(["done", number]) == 0
    capsys.readouterr()
    assert teardown.main(["list"]) == 0 and "nothing" in capsys.readouterr().out


def test_a_line_someone_wrote_by_hand_is_kept_and_shown(home, capsys):
    (home).mkdir(parents=True)
    (home / "teardown.jsonl").write_text('remember the DNS record\n{"id": 7, "what": "an entry", "remove": "delete it", "at": "2026-11-12T10:00:00-05:00", "test": ""}\n', encoding="utf-8")
    assert teardown.main(["list"]) == 0
    listed = capsys.readouterr().out
    assert "remember the DNS record" in listed and "an entry" in listed
    assert teardown.main(["done", "7"]) == 0
    assert (home / "teardown.jsonl").read_text(encoding="utf-8") == "remember the DNS record\n"
    teardown.main(["add", "a key", "--remove", "revoke it"])
    assert rows_after(home) == ["remember the DNS record", 1]


def rows_after(home: Path) -> list:
    out = []
    for line in (home / "teardown.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line)["id"])
        except ValueError:
            out.append(line)
    return out

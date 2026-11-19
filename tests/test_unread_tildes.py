"""Review round 1 of 5.25.2 (2026-11-18): bash, macOS /bin/sh and zsh expand a word that begins `~-` to $OLDPWD, `~+` to
$PWD and `~N`, `~+N` or `~-N` to an entry of the folder stack, and the guard read none of them. So `OLDPWD=-convert;
plutil ~- xml1 <agent>` ran `plutil -convert xml1 <agent>` while the guard read a lint (A13 had made plutil a reader), and
`OLDPWD=-o; sort ~- <protected>/x <file>` wrote the protected file on main as well.

Such a word is now a value the guard cannot read, marked so as it reads the words. Whatever treats an unreadable value
treats it the same way: a write target, the folder a cd lands in, a reader's own rule. Where a program's words decide
what it writes (a writer, a reader whose options write, git, find, sed, uniq, xxd, plutil, defaults, or a program the
guard does not know), it may be any option, or a target joined to one. A program run from such a folder, or from a
variable the guard cannot read, is known by no name. Plain `~`, `~/…` and `~user` read as before.
"""

import os
import shlex

import pytest

from synthesis import guards, paths

HELD = "approve followed by the code"
SETTINGS = "a harness's own settings"
PLIST = ('<?xml version="1.0" encoding="UTF-8"?>\n<plist version="1.0"><dict><key>Label</key><string>com.example.job</string>'
         "<key>ProgramArguments</key><array><string>/bin/echo</string><string>hi</string></array></dict></plist>\n")


@pytest.fixture
def mac(tmp_path, monkeypatch):
    """A home of the test's own laid out as on a Mac, with a launch agent in it; a project folder; the state folder."""
    home = tmp_path / "home"
    agents = home / "Library" / "LaunchAgents"
    agents.mkdir(parents=True)
    (agents / "com.example.job.plist").write_text(PLIST, encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PATH", os.pathsep.join(("/usr/bin", "/bin", "/usr/sbin", "/sbin")))
    monkeypatch.delenv("A13_UNSET", raising=False)
    work = tmp_path / "work"
    work.mkdir()
    (work / "job.plist").write_text(PLIST, encoding="utf-8")
    (work / "a").write_text("b\na\n", encoding="utf-8")
    paths.state().mkdir(parents=True, exist_ok=True)
    return {"agents": agents, "work": work, "state": paths.state()}


def _verdict(mac, line: str):
    spots = {"agent": "~/Library/LaunchAgents/com.example.job.plist", "domain": "~/Library/LaunchAgents/com.example.job",
             "agents": "~/Library/LaunchAgents", "agents_abs": shlex.quote(str(mac["agents"])),
             "work": shlex.quote(str(mac["work"])), "state": shlex.quote(str(mac["state"]))}
    return guards.check("Bash", {"command": line.format(**spots)}, {}, cwd=str(mac["work"]), session=None)


def _held(reason) -> bool:
    return bool(reason) and HELD in reason and SETTINGS in reason and not reason.startswith("Refused")


REVIEWED = {  # the review's lines, and the forms beside them
    "OLDPWD made -convert": "OLDPWD=-convert; plutil ~- xml1 {agent}",
    "PWD made -convert": "PWD=-convert; plutil ~+ xml1 {agent}",
    "OLDPWD made -remove": "OLDPWD=-remove; plutil ~- ProgramArguments {agent}",
    "OLDPWD set on a line of its own": "OLDPWD=-convert\nplutil ~- xml1 {agent}",
    "OLDPWD exported": "export OLDPWD=-convert; plutil ~- xml1 {agent}",
    "inside bash -c": "bash -c 'OLDPWD=-convert; plutil ~- xml1 {agent}'",
    "inside sh -c": "sh -c 'OLDPWD=-convert; plutil ~- xml1 {agent}'",
    "inside bash -c, -remove": "bash -c 'OLDPWD=-remove; plutil ~- ProgramArguments {agent}'",
    "OLDPWD set where the line does not show it": "plutil ~- xml1 {agent}",
    "an entry of the folder stack": "plutil ~1 xml1 {agent}",
    "an entry of the folder stack from the top": "plutil ~+1 xml1 {agent}",
    "an entry of the folder stack from the bottom": "plutil ~-0 xml1 {agent}",
    "defaults' command from OLDPWD": "OLDPWD=write; defaults ~- {domain} Disabled -bool true",
}


@pytest.mark.parametrize("case", sorted(REVIEWED))
def test_plutil_or_defaults_given_a_word_from_oldpwd_pwd_or_the_folder_stack_waits(mac, case):
    assert _held(_verdict(mac, REVIEWED[case])), REVIEWED[case]


OLDER = {  # (the line, "held" for a harness's settings or "refused" for the state folder)
    "sort, the review's": ("OLDPWD=-o; sort ~- {agents}/x.txt {work}/a", "held"),
    "sort into the state folder": ("OLDPWD=-o; sort ~- {state}/x.txt {work}/a", "refused"),
    "sort's output joined to its option": ("OLDPWD=-o{agents_abs}/x.txt; sort ~- {work}/a", "held"),
    "git's output joined to its option": ("OLDPWD=--output={agents_abs}/x.txt; git log ~-", "held"),
    "find told to delete": ("OLDPWD=-delete; find {agents} ~-", "held"),
    "sed told to edit in place": ("OLDPWD=-i; sed ~- s/hi/bye/ {agent}", "held"),
    "uniq writing its second file": ("OLDPWD=-c; uniq ~- {work}/a {agents}/x.txt", "held"),
    "xxd writing its second file": ("OLDPWD=-r; xxd ~- {work}/a {agents}/x.txt", "held"),
    "cp told where to land": ("OLDPWD=-t; cp ~- {agents} {work}/job.plist", "held"),
    "dd's output": ("OLDPWD=of={agents_abs}/x.plist; dd ~- if={work}/job.plist", "held"),
    "a program the guard does not know, its output joined": ("OLDPWD=--output={agents_abs}/x.plist; curl -sS ~- https://example.com/x",
                                                               "held"),
}


@pytest.mark.parametrize("case", sorted(OLDER))
def test_every_program_whose_words_decide_what_it_writes_takes_such_a_word_as_any_option(mac, case):
    line, how = OLDER[case]
    reason = _verdict(mac, line)
    assert (_held(reason) if how == "held" else bool(reason) and reason.startswith("Refused")), (line, reason)


TARGETS = {  # (the line, as above)
    "a copy into the folder a cd left": ("cd {agents} && cd {work} && cp {work}/job.plist ~-/new.plist", "held"),
    "a redirect into the state folder a cd left": ("cd {state} && cd {work} && echo x > ~-/grant.json", "refused"),
    "a write after cd ~-": ("cd {state} && cd {work} && cd ~- && echo x > grant.json", "refused"),
    "plutil run from the folder a cd left": ("~-/plutil -p {agent}", "held"),
    "plutil run from a folder in a variable the guard cannot read": ("$A13_UNSET/plutil -p {agent}", "held"),
}


@pytest.mark.parametrize("case", sorted(TARGETS))
def test_a_write_target_folder_or_program_spelled_so_is_a_place_the_guard_cannot_read(mac, case):
    line, how = TARGETS[case]
    reason = _verdict(mac, line)
    assert (_held(reason) if how == "held" else bool(reason) and reason.startswith("Refused")), (line, reason)


CONTROLS = {
    "plutil -p of a launch agent by ~/": "plutil -p ~/Library/LaunchAgents/com.example.job.plist",
    "cat in the folder a cd left": "cat ~-/notes.txt",
    "ls of ~+": "ls ~+",
    "grep in the folder a cd left": "grep -c a ~-/a",
    "echo of the folder stack": "echo ~1 ~+ ~-",
    "a cd to ~- and a listing": "cd ~- && ls",
    "a copy into ~/": "cp {work}/job.plist ~/job-copy.plist",
    "sort's output into ~/": "sort -o ~/sorted.txt {work}/a",
    "a copy out of the folder a cd left into a project": "cp ~-/a {work}/a-copy",
    "a user's home folder": "ls ~root",
    "a commit message of ~-": "git commit --allow-empty -m '~-'",
    "find under ~/": "find ~/Library -name '*.plist'",
}


@pytest.mark.parametrize("case", sorted(CONTROLS))
def test_plain_tilde_lines_and_readers_given_such_a_word_need_no_code(mac, case):
    assert _verdict(mac, CONTROLS[case]) is None, CONTROLS[case]


def test_the_words_marked_are_those_that_read_oldpwd_pwd_or_the_folder_stack():
    """Brace expansion comes first, as in bash; a name after `~-` or `~+` is a user's name, which the shell leaves as
    written when there is none; a `~` past the start of a word stays as written."""
    words = [t[1] for t in guards._lex("echo ~- ~+ ~1 ~+2/x ~-0 {~-,y} ~ ~/x ~root ~-x ~+x x~-") if t[0] == "w"]
    assert words == ["echo", "$~-", "$~+", "$~1", "$~+2/x", "$~-0", "$~-", "y", "~", "~/x", "~root", "~-x", "~+x", "x~-"]

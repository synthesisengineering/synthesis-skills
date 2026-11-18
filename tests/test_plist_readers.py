"""BACKLOG A13 (2026-11-18): the installed 5.25.0 guard held `plutil -p` of a launch agent, piped to grep, as a change of a
harness's own settings. plutil only prints there, and an honest agent reads launch agents in ordinary work: the
whole-machine review reads the scheduled jobs, and the doctor's own checks name them. plutil was no program the guard
knew, so every file handed to it was judged as written; `defaults read` of the same file was held the same way.

plutil and defaults now read a property list as cat does in the forms that only print, each as this Mac's plutil and
defaults do it (their help, plutil's manual, and each form run on a copy): plutil's -p, -lint (the default when no
command option is given) and -help; -type and -extract in raw format, which print unless -o names a file; -extract and
-convert with `-o -`, which writes to stdout; defaults' read and read-type. Every other form waits for the code as
before: -convert in place, beside the file (-e) or into a protected folder (-o), -insert, -replace, -remove, -create,
-extract in any other format with no -o (it rewrites the file it reads), any form whose -o names a file, and defaults'
write, delete, rename, import and export to a file; so does any form the guard cannot place: two command options, an
option it does not know, two -o, or a word the shell may still turn into an option (a substitution, a variable it
cannot read, xargs's files, a pattern that may name one). A script under plutil's or defaults' name is judged as the
script it is.
"""

import os
import shlex

import pytest

from synthesis import guards, paths

HELD = "approve followed by the code"
SETTINGS = "a harness's own settings"
PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
\t<key>Label</key>
\t<string>com.example.job</string>
\t<key>ProgramArguments</key>
\t<array>
\t\t<string>/bin/echo</string>
\t\t<string>hi</string>
\t</array>
</dict>
</plist>
"""


@pytest.fixture
def mac(tmp_path, monkeypatch):
    """A home of the test's own laid out as on a Mac, with a launch agent in it; a project folder with a property list of
    its own; and one in the synthesis state folder."""
    home = tmp_path / "home"
    agents = home / "Library" / "LaunchAgents"
    agents.mkdir(parents=True)
    (agents / "com.example.job.plist").write_text(PLIST, encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PATH", os.pathsep.join(("/usr/bin", "/bin", "/usr/sbin", "/sbin")))
    work = tmp_path / "work"
    work.mkdir()
    (work / "job.plist").write_text(PLIST, encoding="utf-8")
    paths.state().mkdir(parents=True, exist_ok=True)
    (paths.state() / "job.plist").write_text(PLIST, encoding="utf-8")
    return {"home": home, "agents": agents, "work": work, "state": paths.state()}


def _spots(mac) -> dict:
    return {"agent": "~/Library/LaunchAgents/com.example.job.plist", "domain": "~/Library/LaunchAgents/com.example.job",
            "agents": "~/Library/LaunchAgents", "work": shlex.quote(str(mac["work"])), "state": shlex.quote(str(mac["state"]))}


def _verdict(mac, line: str, cwd=None):
    return guards.check("Bash", {"command": line.format(**_spots(mac))}, {}, cwd=str(cwd or mac["work"]), session=None)


def _held(reason) -> bool:
    return bool(reason) and HELD in reason and SETTINGS in reason and not reason.startswith("Refused")


READS = {
    "the held line: plutil -p piped to grep": "plutil -p {agent} | grep -A3 ProgramArguments",
    "plutil -lint": "plutil -lint {agent}",
    "plutil with no command option, which lints": "plutil {agent}",
    "plutil -lint, silent": "plutil -lint -s {agent}",
    "plutil -p after --": "plutil -p -- {agent}",
    "plutil -help": "plutil -help {agent}",
    "plutil -type": "plutil -type Label {agent}",
    "plutil -type with -expect": "plutil -type Label -expect string {agent}",
    "plutil -extract in raw format, which prints": "plutil -extract Label raw {agent}",
    "plutil -extract in raw format with -n": "plutil -extract Label raw -n {agent}",
    "plutil -extract to stdout": "plutil -extract Label xml1 -o - {agent}",
    "plutil -extract as JSON to stdout": "plutil -extract ProgramArguments json -r -o - {agent}",
    "plutil -extract with -expect to stdout": "plutil -extract Label raw -expect string -o - {agent}",
    "plutil -convert to stdout": "plutil -convert xml1 -o - {agent}",
    "plutil -convert as JSON to stdout, into jq": "plutil -convert json -o - {agent} | jq .Label",
    "every launch agent in a loop": "for f in {agents}/*.plist; do plutil -p \"$f\"; done",
    "every launch agent found": "find {agents} -name '*.plist' -exec plutil -p {{}} \\;",
    "from inside the folder": "cd {agents} && plutil -p com.example.job.plist",
    "from inside the folder, by a pattern": "cd {agents} && plutil -extract Label raw *.plist",
    "defaults read": "defaults read {domain}",
    "defaults read of a key, the file named whole": "defaults read {agent} Label",
    "defaults read-type": "defaults read-type {domain} Label",
    "defaults read on this host": "defaults -currentHost read {domain}",
}


@pytest.mark.parametrize("case", sorted(READS))
def test_each_form_that_only_prints_reads_a_launch_agent_with_no_code(mac, case):
    assert _verdict(mac, READS[case]) is None, READS[case]


WRITES = {
    "plutil -convert in place": "plutil -convert xml1 {agent}",
    "plutil -convert in place, from inside the folder": "cd {agents} && plutil -convert binary1 com.example.job.plist",
    "plutil -convert into the folder": "plutil -convert binary1 -o {agents}/copy.plist {work}/job.plist",
    "plutil -convert beside the file": "plutil -convert json -e json {agent}",
    "plutil -insert": "plutil -insert Disabled -bool true {agent}",
    "plutil -replace": "plutil -replace Label -string com.example.other {agent}",
    "plutil -remove": "plutil -remove ProgramArguments {agent}",
    "plutil -create": "plutil -create xml1 {agents}/new.plist",
    "plutil -extract in another format, which rewrites the file": "plutil -extract Label xml1 {agent}",
    "plutil -extract in raw format into the folder": "plutil -extract Label raw -o {agents}/label.txt {agent}",
    "plutil -extract of a project's file into the folder": "plutil -extract Label xml1 -o {agents}/label.plist {work}/job.plist",
    "plutil -type into the folder": "plutil -type Label -o {agents}/type.txt {agent}",
    "defaults write": "defaults write {domain} Disabled -bool true",
    "defaults delete": "defaults delete {domain} Disabled",
    "defaults rename": "defaults rename {domain} Label OtherLabel",
    "defaults import": "defaults import {domain} {work}/job.plist",
    "defaults export into the folder": "defaults export {work}/job {agents}/copy.plist",
}


@pytest.mark.parametrize("case", sorted(WRITES))
def test_each_form_that_writes_still_waits_for_the_code(mac, case):
    assert _held(_verdict(mac, WRITES[case])), WRITES[case]


UNPLACED = {
    "two command options": "plutil -p -convert json {agent}",
    "an option plutil has that no read takes": "plutil -p -x {agent}",
    "-o given twice": "plutil -extract Label raw -o - -o {agents}/label.txt {agent}",
    "-e beside -o -": "plutil -convert json -e json -o - {agent}",
    "a header beside the conversion": "plutil -convert objc -header -o - {agent}",
    "a substitution that may print an option": "plutil $(echo -convert json) {agent}",
    "a variable the guard cannot read": "plutil -p $A13_UNSET {agent}",
    "the files xargs hands it": "printf '%s\\n' {agent} | xargs plutil -p",
    "a pattern that may name an option": "cd {agents} && plutil *",
    "defaults read with a word too many": "defaults read {domain} Label Extra",
    "defaults with a substitution for its command": "defaults $(echo write) {domain} Label x",
}


@pytest.mark.parametrize("case", sorted(UNPLACED))
def test_a_form_the_guard_cannot_place_still_waits_for_the_code(mac, case, monkeypatch):
    monkeypatch.delenv("A13_UNSET", raising=False)
    assert _held(_verdict(mac, UNPLACED[case])), UNPLACED[case]


def test_a_read_of_the_state_folder_passes_and_a_write_there_is_still_refused(mac):
    """The folders every approval rests on take no code: a form that only prints reads there as cat does, from beside it or
    from inside it; a form that writes is refused outright, as it was."""
    for line in ("plutil -p {state}/job.plist", "defaults read {state}/job Label", "cd {state} && plutil -extract Label raw job.plist"):
        assert _verdict(mac, line) is None, line
    for line in ("plutil -convert xml1 {state}/job.plist", "defaults write {state}/job Label x"):
        assert _verdict(mac, line).startswith("Refused"), line


def test_a_form_that_only_prints_fills_no_folder_python_loads_from(mac):
    """A line that moves Python's module path waits while another program on it may fill that folder unseen (review round
    3 of 22.21): plutil or defaults reading fills none; plutil writing still may."""
    (mac["work"] / "empty").mkdir()
    (mac["state"] / "x.json").write_text("{}", encoding="utf-8")
    py = "PYTHONPATH=empty python3 -c " + shlex.quote(f"import json; print(open('{mac['state']}/x.json').read())")
    for line in ("plutil -p {agent} && " + py, "defaults read {domain} && " + py):
        assert _verdict(mac, line) is None, line
    assert HELD in (_verdict(mac, "plutil -convert json -e py {work}/job.plist && " + py) or "")


@pytest.mark.parametrize("name,line", [("plutil", "plutil -p {agent}"), ("defaults", "defaults read {domain}")])
def test_a_script_under_the_name_of_plutil_or_defaults_is_judged_as_the_script_it_is(mac, monkeypatch, name, line):
    """A form that only prints is judged by the program's name, so a script under that name, found first on PATH in a
    folder the user writes, is read as the script it is (22.32): here one that writes a launch agent."""
    folder = mac["work"] / "bin"
    folder.mkdir()
    script = folder / name
    script.write_text("#!/bin/sh\ncp /etc/hosts \"$HOME/Library/LaunchAgents/com.example.evil.plist\"\n", encoding="utf-8")
    script.chmod(0o755)
    monkeypatch.setenv("PATH", os.pathsep.join((str(folder), "/usr/bin", "/bin", "/usr/sbin", "/sbin")))
    assert _held(_verdict(mac, line)), line


def test_the_hold_of_a_write_names_plutil_p_among_the_reads_that_need_no_code(mac):
    """A launch agent may be a binary property list, which cat, grep and jq do not show: the hold names the read that does."""
    held = _verdict(mac, "plutil -convert xml1 {agent}")
    assert _held(held) and "Reading these files needs no code (cat, head, grep, jq, plutil -p)" in held, held

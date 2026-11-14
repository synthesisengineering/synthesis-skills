"""5.22.1: a program near the records every approval rests on passes only when the guard can prove it reads.

Every approval rests on two records an agent must not write: the harness's transcript, which shows the principal
typing `approve <code>`, and the grant the prompt hook files under the synthesis state. A review (2026-11-14) found
that `perl -MFile::Copy -e 'copy($ARGV[0], $ARGV[1])' FORGED TARGET` passed the shell guard: it judged an
interpreter by a list of the calls that write (`SCRIPTED_WRITE`), File::Copy was not on it, and one line forged the
principal's prompt into the transcript and wrote the grant, after which any held call went. A list of the ways to
write never ends, so an interpreter or a shell run that names a protected folder in any spelling now passes only
when its program is proven to read only; a program in a language the guard does not read waits for the principal's
code. The same review found the send window opened with no code from a faked terminal (`env -i ... script`), and
that only the first window request in a command line was judged.
"""

import json
import os
import re
import shlex
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from synthesis import approvals, guards, paths, sends

ROOT = Path(__file__).resolve().parents[1]
CONFIG = {"send_tools": ["mcp__*__slack_send_message"]}
SLACK = "mcp__slack__slack_send_message"
HELD = "approve followed by the code"


@pytest.fixture
def world(tmp_path, monkeypatch):
    """A home of the test's own, where every protected folder lies where it lies on a Mac: the transcripts under
    `~/.claude/projects`, the synthesis state under `~/.synthesis/v5`. `~`, `$HOME` and `Path.home()` lead there."""
    home = tmp_path / "home"
    for key, value in (("HOME", home), ("SYNTHESIS_HOME", home / ".synthesis" / "v5"), ("CLAUDE_CONFIG_DIR", home / ".claude"),
                       ("CODEX_HOME", home / ".codex"), ("XDG_DATA_HOME", home / ".local" / "share"),
                       ("SYNTHESIS_CLAUDE_DESKTOP_DIR", home / "Library" / "Application Support" / "Claude")):
        monkeypatch.setenv(key, str(value))
    monkeypatch.setenv("SYNTHESIS_SESSION", "S-principal")
    record = home / ".claude" / "projects" / "-work" / "S-principal.jsonl"
    record.parent.mkdir(parents=True)
    record.write_text(json.dumps({"type": "user", "message": {"role": "user", "content": "hello"}}) + "\n", encoding="utf-8")
    (paths.state() / "approvals").mkdir(parents=True)
    work = tmp_path / "work"
    work.mkdir()
    (work / "forged.jsonl").write_text("{}\n", encoding="utf-8")
    (work / "copy.py").write_text("import shutil, sys\nshutil.copy(sys.argv[1], sys.argv[2])\n", encoding="utf-8")
    (work / "read.py").write_text("import sys\nprint(open(sys.argv[1], encoding='utf-8').read()[:40])\n", encoding="utf-8")
    (work / "copy.pl").write_text("use File::Copy;\ncopy($ARGV[0], $ARGV[1]);\n", encoding="utf-8")
    (work / "copy.sh").write_text("#!/bin/sh\ncp \"$1\" \"$2\"\n", encoding="utf-8")
    (work / "copy.sh").chmod(0o755)
    (work / "lines.awk").write_text("{ print > ARGV[2] }\n", encoding="utf-8")
    (work / "projects").symlink_to(home / ".claude" / "projects")  # a link into the transcripts, made beforehand

    def approve(reason: str) -> list:
        """The principal types approve <code> in this session; the harness records it and the prompt hook grants it."""
        code = re.search(r"\bcode ([a-z0-9]{6})\b", reason).group(1)
        when = (datetime.now(timezone.utc) + timedelta(milliseconds=5)).isoformat()
        with record.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"type": "user", "timestamp": when, "origin": {"kind": "human"}, "sessionId": "S-principal",
                                     "message": {"role": "user", "content": f"approve {code}"}}) + "\n")
        time.sleep(0.01)
        return approvals.grant_from_prompt(f"approve {code}")

    q = shlex.quote
    return {"home": home, "record": record, "work": work, "approve": approve, "session": {"session_id": "S-principal",
            "transcript_path": str(record)}, "rec": q(str(record)), "forged": q(str(work / "forged.jsonl")),
            "grant": q(str(paths.state() / "approvals" / ("a" * 64 + ".json"))), "state": q(str(paths.state()))}


def _verdict(world, line: str, session=None):
    return guards.check("Bash", {"command": line}, CONFIG, cwd=str(world["work"]), session=session or world["session"])


def _lines(world, template: str) -> str:
    return template.format(**{k: v for k, v in world.items() if isinstance(v, str)}, record_raw=world["record"],
                           forged_raw=world["work"] / "forged.jsonl", work=world["work"], home=world["home"])


# --- the review's probe: Perl's File::Copy forges the principal's prompt and writes the grant ------------------------

@pytest.mark.parametrize("call", ["copy", "move", "cp", "mv", "syscopy"])
@pytest.mark.parametrize("target", ["rec", "grant"])
def test_perls_file_copy_never_writes_the_transcript_or_the_grant(world, call, target):
    line = f"perl -MFile::Copy=cp,mv -e 'File::Copy::{call}($ARGV[0], $ARGV[1])' {world['forged']} {world[target]}"
    assert _verdict(world, line) is not None, line


def test_the_probe_end_to_end_a_held_send_stays_held(world):
    """p18: the send is held, the forging line is not let through, and the send is still held."""
    said = {"channel_id": "D0777", "message": "Words the principal never approved."}
    hold = guards.check(SLACK, said, CONFIG, session=world["session"])
    code = re.search(r"\bcode ([a-z0-9]{6})\b", hold).group(1)
    request = paths.read_json(paths.state() / "approval-requests" / f"{code}.json")
    grant = shlex.quote(str(paths.state() / "approvals" / (request["digest"] + ".json")))
    for target in (world["rec"], grant):
        assert _verdict(world, f"perl -MFile::Copy -e 'copy($ARGV[0], $ARGV[1])' {world['forged']} {target}") is not None
    assert guards.check(SLACK, said, CONFIG, session=world["session"]) is not None


# --- every other interpreter reached the same way -------------------------------------------------------------------

FORGERS = {
    "perl rename": "perl -e 'rename($ARGV[0], $ARGV[1])' {forged} {rec}",
    "perl heredoc": "perl - {forged} {rec} <<'EOF'\nuse File::Copy; copy($ARGV[0], $ARGV[1]);\nEOF",
    "perl script file": "perl {work}/copy.pl {forged} {rec}",
    "perl down a pipe": "echo 'use File::Copy; copy($ARGV[0], $ARGV[1]);' | perl - {forged} {rec}",
    "ruby": "ruby -rfileutils -e 'FileUtils.cp(ARGV[0], ARGV[1])' {forged} {rec}",
    "ruby heredoc": "ruby - {forged} {rec} <<'EOF'\nrequire 'fileutils'; FileUtils.cp(ARGV[0], ARGV[1])\nEOF",
    "node": "node -e 'require(\"fs\").copyFileSync(process.argv[1], process.argv[2])' {forged} {rec}",
    "node heredoc": "node - {forged} {rec} <<'EOF'\nrequire('fs').copyFileSync(process.argv[2], process.argv[3])\nEOF",
    "bun": "bun -e 'require(\"fs\").copyFileSync(process.argv[2], process.argv[3])' {forged} {rec}",
    "deno": "deno eval 'Deno.copyFileSync(Deno.args[0], Deno.args[1])' {forged} {rec}",
    "php": "php -r 'copy($argv[1], $argv[2]);' {forged} {rec}",
    "lua": "lua -e 'io.open(arg[2], \"w\"):write(io.open(arg[1]):read(\"a\"))' {forged} {rec}",
    "tcl heredoc": "tclsh <<'EOF'\nfile copy -force {forged_raw} {record_raw}\nEOF",
    "osascript shell": "osascript -e 'do shell script \"cp {forged_raw} {record_raw}\"'",
    "osascript jxa": ("osascript -l JavaScript -e 'ObjC.import(\"Foundation\"); $.NSFileManager.defaultManager"
                      ".copyItemAtPathToPathError(\"{forged_raw}\", \"{record_raw}\", null)'"),
    "awk redirect": "awk '{{ print > ARGV[2] }}' {forged} {rec}",
    "awk system": "awk 'BEGIN {{ system(\"cp \" ARGV[1] \" \" ARGV[2]) }}' {forged} {rec}",
    "awk program file": "awk -f {work}/lines.awk {forged} {rec}",
    "gawk dump file": "gawk --dump-variables={record_raw} 'BEGIN {{ }}'",
    "sed w": "sed -n 'w {record_raw}' {forged}",
    "sed s///w": "sed 's/a/a/w {record_raw}' {forged}",
    "python -c": "python3 -c 'import shutil, sys; shutil.copy(sys.argv[1], sys.argv[2])' {forged} {rec}",
    "python script file": "python3 {work}/copy.py {forged} {rec}",
    "python module": "python3 -m json.tool {forged} {rec}",
    "python heredoc": "python3 - {forged} {rec} <<'EOF'\nimport shutil, sys\nshutil.copy(sys.argv[1], sys.argv[2])\nEOF",
    "bash -c": "bash -c 'cp \"$1\" \"$2\"' copier {forged} {rec}",
    "sh -c": "sh -c 'perl -MFile::Copy -e \"copy(\\$ARGV[0], \\$ARGV[1])\" \"$1\" \"$2\"' copier {forged} {rec}",
    "sh script file": "sh {work}/copy.sh {forged} {rec}",
    "a script run by its path": "{work}/copy.sh {forged} {rec}",
    "heredoc to a shell": "bash <<'EOF'\nperl -MFile::Copy -e 'copy($ARGV[0], $ARGV[1])' {forged_raw} {record_raw}\nEOF",
    "find -exec perl": "find {home}/.claude/projects -name '*.jsonl' -exec perl -MFile::Copy -e 'copy($ARGV[0], $ARGV[1])' {forged} {{}} \\;",
    "xargs perl": "ls {home}/.claude/projects/-work/*.jsonl | xargs perl -MFile::Copy -e 'copy(\"{forged_raw}\", $ARGV[0])'",
}


@pytest.mark.parametrize("name", sorted(FORGERS))
def test_no_interpreter_or_shell_writes_the_transcript(world, name):
    line = _lines(world, FORGERS[name])
    assert _verdict(world, line) is not None, line


# --- a Python program whose write cannot be read from its literals ---------------------------------------------------

UNREAD_PYTHON = {
    "a mode in a variable": "m = sys.argv[3]; open(sys.argv[2], m).write(open(sys.argv[1]).read())",
    "getattr": "getattr(os, 'rep' + 'lace')(sys.argv[1], sys.argv[2])",
    "a module's table": "vars(os)['rep' + 'lace'](sys.argv[1], sys.argv[2])",
    "partial": "import functools, shutil; functools.partial(shutil.copy, sys.argv[1])(sys.argv[2])",
    "methodcaller": "import operator, shutil; operator.methodcaller('copy', sys.argv[1], sys.argv[2])(shutil)",
    "exec": "exec('import shutil; shutil.copy(sys.argv[1], sys.argv[2])')",
    "eval": "eval('__import__(\"shutil\").copy(sys.argv[1], sys.argv[2])')",
    "compile": "exec(compile('import shutil; shutil.copy(sys.argv[1], sys.argv[2])', 'x', 'exec'))",
    "__import__": "__import__('shu' + 'til').copy(sys.argv[1], sys.argv[2])",
    "importlib": "import importlib; importlib.import_module('shu' + 'til').copy(sys.argv[1], sys.argv[2])",
    "io.open": "import io; io.open(sys.argv[2], 'w').write('x')",
    "codecs.open": "import codecs; codecs.open(sys.argv[2], 'w').write('x')",
    "os.fdopen": "os.fdopen(os.open(sys.argv[2], os.O_WRONLY), 'w').write('x')",
}


@pytest.mark.parametrize("name", sorted(UNREAD_PYTHON))
def test_a_python_write_that_is_not_a_literal_never_reaches_the_transcript(world, name):
    line = f"python3 -c {shlex.quote('import os, sys; ' + UNREAD_PYTHON[name])} {world['forged']} {world['rec']} w"
    assert _verdict(world, line) is not None, line


# --- the protected folder reached without its literal path ------------------------------------------------------------

SPELLINGS = {
    "Path.home() in Python": "python3 -c 'from pathlib import Path; (Path.home() / \".claude\" / \"projects\" / \"-work\" / \"S-principal.jsonl\").write_text(\"x\")'",
    "$HOME in Perl": "perl -MFile::Copy -e 'copy($ARGV[0], \"$ENV{{HOME}}/.claude/projects/-work/S-principal.jsonl\")' {forged}",
    "os.homedir() in Node": "node -e 'require(\"fs\").copyFileSync(process.argv[1], require(\"os\").homedir() + \"/.claude/projects/-work/S-principal.jsonl\")' {forged}",
    "an environment variable in Perl": "perl -MFile::Copy -e 'copy($ARGV[0], \"$ENV{{CLAUDE_CONFIG_DIR}}/projects/-work/S-principal.jsonl\")' {forged}",
    "an environment variable on the line": "perl -MFile::Copy -e 'copy($ARGV[0], $ARGV[1])' {forged} \"$CLAUDE_CONFIG_DIR/projects/-work/S-principal.jsonl\"",
    "a variable the line gives": "D={home}/.claude/projects/-work perl -MFile::Copy -e 'copy($ARGV[0], \"$ENV{{D}}/S-principal.jsonl\")' {forged}",
    "~ on the line": "perl -MFile::Copy -e 'copy($ARGV[0], $ARGV[1])' {forged} ~/.claude/projects/-work/S-principal.jsonl",
    "~ in Ruby": "ruby -e 'File.write(File.expand_path(\"~/.claude/projects/-work/S-principal.jsonl\"), \"x\")'",
    "a link made beforehand": "perl -MFile::Copy -e 'copy($ARGV[0], $ARGV[1])' {forged} {work}/projects/-work/S-principal.jsonl",
    "a link inside the program": "perl -MFile::Copy -e 'copy($ARGV[0], \"{work}/projects/-work/S-principal.jsonl\")' {forged}",
    "..": "perl -MFile::Copy -e 'copy($ARGV[0], $ARGV[1])' {forged} {home}/.claude/x/../projects/-work/S-principal.jsonl",
    "the folder above, handed whole": "perl -MFile::Copy -e 'copy($ARGV[0], \"$ARGV[1]/projects/-work/S-principal.jsonl\")' {forged} {home}/.claude",
    "the state by $HOME in Perl": "perl -MFile::Copy -e 'copy($ARGV[0], \"$ENV{{HOME}}/.synthesis/v5/state/approvals/x.json\")' {forged}",
}


@pytest.mark.parametrize("name", sorted(SPELLINGS))
def test_a_protected_folder_spelled_another_way_is_still_that_folder(world, name):
    line = _lines(world, SPELLINGS[name])
    assert _verdict(world, line) is not None, line


# --- what still passes, and how the principal releases a legitimate read ----------------------------------------------

READS = {
    "cat": "cat {rec}",
    "grep": "grep -c user {rec} {state}/approvals",
    "jq": "jq -r .type {rec}",
    "awk": "awk -F, '{{ print $1 }}' {rec}",
    "sed": "sed -n '1,5p' {rec}",
    "python -I script that reads": "python3 -I {work}/read.py {rec}",
    "python -c that reads": "python3 -c 'import sys; print(open(sys.argv[1]).read()[:40])' {rec}",
    "python heredoc that reads": "python3 - {rec} <<'EOF'\nimport json, sys\nprint(sum(1 for _ in open(sys.argv[1])))\nEOF",
    "synthesis": "synthesis approvals",
    "synthesis sessions": "synthesis sessions show S-principal --kinds user",
    "git": "git -C {work} status",
    "perl naming no protected folder": "perl -pe 's/a/b/' {forged}",
    "node naming no protected folder": "node -e 'console.log(1)'",
    "a script naming no protected folder": "python3 {work}/copy.py {forged} {work}/copied.jsonl",
}


@pytest.mark.parametrize("name", sorted(READS))
def test_reading_the_records_and_programs_far_from_them_still_pass(world, name):
    line = _lines(world, READS[name])
    assert _verdict(world, line) is None, line


def test_an_unread_program_waits_for_the_principals_code_and_it_releases_that_command_once(world):
    line = f"perl -ne 'print if /user/' {world['rec']}"
    reason = _verdict(world, line)
    assert reason and HELD in reason and "perl" in reason and "only reads" in reason  # why, and how the principal releases a read
    assert "cat" in reason and "jq" in reason  # and the way to read with no code
    other = f"perl -ne 'print if /assistant/' {world['rec']}"
    world["approve"](reason)
    assert HELD in _verdict(world, other)  # another program: its own code
    assert _verdict(world, line) is None  # the identical command, once
    assert HELD in _verdict(world, line)  # and the code is spent


def test_a_program_that_proves_it_writes_a_record_stays_refused_with_no_code(world):
    reason = _verdict(world, f"python3 -c 'open(\"{world['record']}\", \"a\").write(\"x\")'")
    assert reason.startswith("Refused") and HELD not in reason


# --- the send window: the principal's setting, from any terminal ------------------------------------------------------

WINDOW = ("sends", "open", "--hours", "2", "--sends", "3", "--channels", "jira")


def _terminal_cli(world, *args):
    """The CLI as `env -i ... script -q /dev/null synthesis ...` runs it: a terminal on its input and no harness in its
    environment (the temporary home stays named, so nothing reaches this Mac's own)."""
    leader, follower = os.openpty()
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(world["home"]), "PYTHONPATH": str(ROOT),
           "SYNTHESIS_HOME": os.environ["SYNTHESIS_HOME"], "CLAUDE_CONFIG_DIR": os.environ["CLAUDE_CONFIG_DIR"]}
    try:
        return subprocess.run([sys.executable, "-m", "synthesis.cli", *args], stdin=follower, capture_output=True, text=True,
                              env=env, cwd=str(ROOT), timeout=60)
    finally:
        os.close(follower)
        os.close(leader)


def test_a_faked_terminal_opens_no_window_without_the_principals_code(world):
    assert _terminal_cli(world, *WINDOW).returncode != 0 and sends.window() == {}
    refused = _terminal_cli(world, "--session", "S-principal", *WINDOW)
    assert refused.returncode != 0 and HELD in refused.stderr and sends.window() == {}
    world["approve"](refused.stderr)
    opened = _terminal_cli(world, "--session", "S-principal", *WINDOW)
    assert opened.returncode == 0 and sends.window()  # the principal's code opens it, from any terminal


def test_the_guard_asks_for_the_code_under_env_i_and_script(world):
    line = "env -i PATH=/usr/bin:/bin script -q /dev/null synthesis sends open --hours 2 --sends 3 --channels jira"
    assert HELD in _verdict(world, line)


def test_every_window_request_in_a_line_needs_its_own_code(world):
    first = "synthesis sends open --hours 1 --sends 2 --channels jira"
    second = "synthesis sends open --hours 12 --sends 50 --channels all"
    world["approve"](_verdict(world, first))
    assert _verdict(world, first) is None
    for line in (f"{first} ; {second}", f"{first} && {second}", f"{second} ; {first}", f"bash -c '{first}; {second}'"):
        reason = _verdict(world, line)
        assert reason and HELD in reason and "50 sends in 12 h" in reason, line
    world["approve"](_verdict(world, second))
    assert _verdict(world, f"{first} ; {second}") is None

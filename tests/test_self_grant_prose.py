"""22.22: a program's strings and comments that only name synthesis's approval and send-window functions are prose, not a
reach of them (2026-11-15: a peer Codex seat's small program, which only wrote its own project-management files, was
refused as running the approval implementation because strings it wrote to a file quoted those names). A call, an
import, an attribute reach, a getattr or a subscript of them, an f-string's expression, and any string a program runs
as code still count, in every spelling the guard held before."""

import shlex

import pytest

from synthesis import guards

APPROVAL_CODE = "approval or send-window code"


def _said(line: str, where) -> str:
    return guards.check("Bash", {"command": line}, {}, cwd=str(where), session={"session_id": "S-prose"}) or ""


PROSE = [
    # what the seat's program did: prose about the functions, written to a file of its own
    "python3 - <<'EOF'\nfrom pathlib import Path\nPath('notes.md').write_text(\"synthesis: approvals.consume and grant_from_prompt are the guard's own; open_window waits for the code\\n\")\nEOF",
    "python3 -c \"open('log.md', 'a').write('synthesis sends.open_window and _window_file are not called here\\n')\"",
    "python3 -c \"# synthesis's approvals.consume spends a grant\nprint('ok')\"",                       # a comment
    "python3 -c \"'''Docstring: synthesis put_back gives a grant back.'''\nprint(1)\"",                  # a docstring
    "python3 -c \"import logging; logging.warning('synthesis: grant_from_prompt reads the prompt')\"",   # a log line
    "python3 -c \"print('synthesis writes paths.state() with write_json and unlink')\"",               # the state-write words
    "node -e \"console.log('synthesis approvals.consume is the guard\\'s')\"",                         # a string in node
]


@pytest.mark.parametrize("line", PROSE)
def test_strings_and_comments_that_only_name_the_functions_are_prose(tmp_path, line):
    assert APPROVAL_CODE not in _said(line, tmp_path), line


CODE = [
    "python3 -c \"from synthesis import sends; sends.open_window(12, ['all'])\"",                       # a call
    "python3 -c \"from synthesis.approvals import consume\"",                                          # an import
    "python3 -c \"import synthesis.approvals as a; f = a.grant_from_prompt\"",                          # an attribute reach
    "python3 -c \"from synthesis import approvals; getattr(approvals, 'consume')('x', {}, None)\"",      # getattr by its name
    "python3 -c \"from synthesis import sends; vars(sends)['open_window'](1, ['all'])\"",               # a subscript by its name
    "python3 -c \"import operator, synthesis.approvals; operator.attrgetter('approvals.put_back')\"",   # a dotted name
    "python3 -c \"from synthesis import approvals; print(f'{approvals.grant_from_prompt(1)}')\"",       # an f-string's expression
    "python3 -c \"exec('from synthesis import approvals; approvals.consume(1, 2)')\"",                  # a string run as code
    "python3 - <<'EOF'\nimport synthesis\nfrom synthesis import sends\nsends._window_file().write_text('{}')\nEOF",
    "python3 -c \"from synthesis import paths; (paths.state() / 'approvals' / 'x.json').write_text('{}')\"",
    "node -e \"/* synthesis */ const consume = require('x'); consume()\"",                             # code in node
    # a program it starts runs it: judged as the command the program starts
    "python3 -c \"import subprocess; subprocess.run(['python3', '-c', 'from synthesis import approvals; approvals.consume(1, 2)'])\"",
    # review round 1 of 22.22: a program that starts a program keeps every string, as one that runs a string as code does
    "node -e " + shlex.quote("require('child_process').execSync(\"python3 -c \\\"from synthesis import approvals; approvals.consume(1, 2)\\\"\")"),
    "node -e \"require('child_process').execFileSync('python3', ['-c', 'from synthesis import approvals; approvals.consume(1, 2)'])\"",
    "python3 -c \"import subprocess; open('s.py', 'w').write('from synthesis import approvals; approvals.consume(1, 2)'); "
    "subprocess.run(['python3', 's.py'])\"",
    "node -e \"require('child_process').execFileSync('synthesis', ['sends', 'open', '--hours', '1', '--channels', 'slack', '--sends', '1'])\"",
    # a script the same line writes by a heredoc and then runs is judged by the heredoc's body, as the script it is
    "cat > s3.py <<'EOF'\nfrom synthesis import approvals\napprovals.consume('probe', {})\nEOF\npython3 s3.py",
]


CALL = "from synthesis import approvals; approvals.consume('probe', {})"
WRITERS = {  # review round 2 of 22.22: a script the line writes and then runs is judged by what is written, whatever the writer
    "tee": "tee s.py > /dev/null <<'EOF'\n" + CALL + "\nEOF\npython3 s.py",
    "cat >>": "cat >> s.py <<'EOF'\n" + CALL + "\nEOF\npython3 s.py",
    "echo": "echo " + shlex.quote(CALL) + " > s.py && python3 s.py",
    "printf": "printf '%s\\n' " + shlex.quote(CALL) + " > s.py && python3 s.py",
    "dd of=": "dd of=s.py status=none <<'EOF'\n" + CALL + "\nEOF\npython3 s.py",
}


@pytest.mark.parametrize("writer", list(WRITERS))
def test_a_script_the_line_writes_and_runs_is_judged_by_what_is_written(tmp_path, writer):
    said = _said(WRITERS[writer], tmp_path)
    assert said.startswith("Refused") or "approve followed by the code" in said, (writer, said)


def test_a_script_a_program_writes_and_the_line_runs_waits(tmp_path):
    line = "python3 -c \"open('gen.py', 'w').write('print(1)')\" && python3 gen.py"
    assert "approve followed by the code" in _said(line, tmp_path)  # what is written cannot be told: the run waits
    assert _said("cat > ok.py <<'EOF'\nprint(1)\nEOF\npython3 ok.py", tmp_path) == ""  # what is written is read: it runs


@pytest.mark.parametrize("line", [
    "python3 -c \"import subprocess; print('synthesis approvals.consume is the guard\\'s'); subprocess.run(['npm', 'test'])\"",
    "node -e " + shlex.quote("console.log('synthesis open_window belongs to the guard'); require('child_process').execSync('npm test')"),
    "python3 -c \"import subprocess; open('n.md', 'w').write('synthesis: consume'); subprocess.run(['git', 'status'])\"",
])
def test_prose_beside_an_unrelated_started_program_is_prose(tmp_path, line):
    """A program that starts a program keeps only the strings that reach it: the started call's arguments, the names
    they are built from, and a file it writes and then starts."""
    assert APPROVAL_CODE not in _said(line, tmp_path), line


def test_the_strings_that_reach_a_started_program_still_count(tmp_path):
    for line in ("python3 -c \"import subprocess; cmd = 'from synthesis import approvals; approvals.consume(1, 2)'; "
                 "subprocess.run(['python3', '-c', cmd])\"",
                 "node -e " + shlex.quote("const fs = require('fs'); fs.writeFileSync('t.py', 'from synthesis import approvals; "
                                          "approvals.consume(1, 2)'); require('child_process').execFileSync('python3', ['t.py'])")):
        said = _said(line, tmp_path)
        assert said.startswith("Refused") or "approve followed by the code" in said, (line, said)


def test_a_heredoc_script_that_opens_a_send_window_waits_like_any_other(tmp_path):
    line = "cat > w.py <<'EOF'\nfrom synthesis import sends\nsends.open_window(1, ['slack'], '', 1)\nEOF\npython3 w.py"
    said = _said(line, tmp_path)
    assert said.startswith("Refused") or "approve followed by the code" in said, said


def test_prose_stays_prose_and_only_a_file_the_program_writes_and_starts_counts(tmp_path):
    prose = "python3 -c \"open('n.md', 'w').write('synthesis: consume is the guard\\'s')\""
    assert APPROVAL_CODE not in _said(prose, tmp_path)
    beside = "python3 -c \"import subprocess; open('n.md', 'w').write('synthesis: consume'); subprocess.run(['true'])\""
    assert APPROVAL_CODE not in _said(beside, tmp_path)  # round 2's ruling: the file it starts is not the one it wrote
    started = "python3 -c \"import subprocess; open('n.py', 'w').write('synthesis: consume'); subprocess.run(['python3', 'n.py'])\""
    assert APPROVAL_CODE in _said(started, tmp_path)


@pytest.mark.parametrize("line", CODE)
def test_a_reach_of_the_functions_in_code_is_still_refused(tmp_path, line):
    said = _said(line, tmp_path)
    assert said.startswith("Refused") or "approve followed by the code" in said, (line, said)


def _py(program: str) -> str:
    return "python3 - <<'EOF'\n" + program + "\nEOF" if "\n" in program else "python3 -c " + shlex.quote(program)


SHELLED = "\"python3 -c '" + CALL + "'\""
REACHED = {  # review round 2 of 22.22: what reaches a started program is read through each way a program hands it on
    "a module alias": _py("import os as o; o.system(" + SHELLED + ")"),
    "a from-import": _py("from os import system; system(" + SHELLED + ")"),
    "a starter looked up by name": _py("import os; getattr(os, 'system')(" + SHELLED + ")"),
    "a starter handed on": _py("import functools, subprocess; functools.partial(subprocess.run, ['python3', '-c', " + repr(CALL) + "])()"),
    "a with-block handle": _py("import subprocess\nwith open('s.py', 'w') as f:\n    f.write(" + repr(CALL) + ")\nsubprocess.run(['python3', 's.py'])"),
    "its standard input": _py("import subprocess; p = subprocess.Popen(['python3'], stdin=subprocess.PIPE); p.communicate(" + repr(CALL.encode()) + ")"),
    "a parameter": _py("import subprocess\ndef go(c):\n    subprocess.run(['python3', '-c', c])\ngo(" + repr(CALL) + ")"),
    "a function of its own": _py("import subprocess\ndef code():\n    return " + repr(CALL) + "\nsubprocess.run(['python3', '-c', code()])"),
    "a name given another's value": _py("import subprocess; a = " + repr(CALL) + "; b = a; subprocess.run(['python3', '-c', b])"),
    "a list it appends to": _py("import subprocess; cmd = ['python3', '-c']; cmd.append(" + repr(CALL) + "); subprocess.run(cmd)"),
    "adjacent strings": _py("import subprocess; subprocess.run(['python3', '-c', 'from synthesis import approvals; ' 'approvals.consume(1, 2)'])"),
    "an f-string's text": _py("import subprocess; m = 'approvals'; subprocess.run(['python3', '-c', f'from synthesis import {m}; {m}.consume(1, 2)'])"),
    "a module the started program imports": _py("import subprocess; open('helper.py', 'w').write(" + repr(CALL) + "); subprocess.run(['python3', '-c', 'import helper'])"),
    "a module run by -m": _py("import subprocess; open('mod.py', 'w').write(" + repr(CALL) + "); subprocess.run(['python3', '-m', 'mod'])"),
    "a file renamed into place": _py("import os, subprocess; open('t.txt', 'w').write(" + repr(CALL) + "); os.rename('t.txt', 's.py'); subprocess.run(['python3', 's.py'])"),
    "a note a started shell runs": _py("import subprocess; open('n.md', 'w').write(" + repr(CALL) + "); subprocess.run('for f in *.md; do python3 \"$f\"; done', shell=True)"),
    "the environment": _py("import os, subprocess; os.environ['C'] = " + SHELLED + "; subprocess.run('sh -c \"$C\"', shell=True)"),
    "a node destructuring rename": "node -e " + shlex.quote("const {execSync: run} = require('child_process'); run(" + SHELLED + ")"),
    "a node alias": "node -e " + shlex.quote("const run = require('child_process').execSync; run(" + SHELLED + ")"),
    "a ruby backtick": "ruby -e " + shlex.quote("`python3 -c '" + CALL + "'`"),
}


@pytest.mark.parametrize("way", list(REACHED))
def test_what_reaches_a_started_program_is_read_through_every_way_it_is_handed_on(tmp_path, way):
    said = _said(REACHED[way], tmp_path)
    assert said.startswith("Refused") or "approve followed by the code" in said, (way, said)


@pytest.mark.parametrize("line", [
    _py("import subprocess\nwith open('CONTEXT.md', 'w') as f:\n    f.write(\"synthesis: approvals.consume and open_window are the guard's own\\n\")\n"
        "subprocess.run(['git', 'add', 'CONTEXT.md'])\nsubprocess.run(['git', 'commit', '-m', 'Notes'])"),
    _py("import os; open('n.md', 'w').write('synthesis: consume is the guard\\'s'); os.system('git add n.md && git commit -m notes')"),
])
def test_a_note_handed_to_a_program_that_does_not_run_it_is_prose(tmp_path, line):
    """A plain document the program writes is prose unless a started program can run it: an interpreter or a shell, or
    the document named as the program itself."""
    assert APPROVAL_CODE not in _said(line, tmp_path), line


# The reading the rule and 22.21's program reach share: what a line writes to each file, by its real path (review round 2).
def _at(where, name: str) -> str:
    return guards._real(str(where / name))


@pytest.mark.parametrize("line, text", [
    ("cat > s.py <<'EOF'\nprint(1)\nEOF", "print(1)"),
    ("cat >> s.py <<'EOF'\nprint(1)\nEOF", "print(1)"),
    ("tee s.py > /dev/null <<'EOF'\nprint(1)\nEOF", "print(1)"),
    ("echo 'print(1)' > s.py", "print(1)"),
    ("printf '%s\\n' 'print(1)' > s.py", "print(1)"),
    ("dd of=s.py status=none <<'EOF'\nprint(1)\nEOF", "print(1)"),
])
def test_written_contents_reads_what_a_shell_writer_puts_in_a_file(tmp_path, line, text):
    assert text in guards.written_contents(line, str(tmp_path))[_at(tmp_path, "s.py")]


@pytest.mark.parametrize("line", [
    "python3 -c \"open('s.py', 'w').write('print(1)')\"",            # a program names it
    "python3 make.py > s.py",                                        # another program's output lands there
    "cp a.py s.py",                                                  # a copy lands there
    "curl -so s.py https://example.invalid/s.py".replace("-so", "-s -o"),
    "node -e \"require('fs').writeFileSync('s.py', 'print(1)')\"",
    "echo 'print(1)' > s.py; echo 'print(2)' > s.py",                # written twice
])
def test_written_contents_cannot_tell_what_a_program_writes(tmp_path, line):
    assert guards.written_contents(line, str(tmp_path))[_at(tmp_path, "s.py")] == guards.UNKNOWN_CONTENT


@pytest.mark.parametrize("line", [
    "python3 -c \"import os; open(os.environ['P'], 'w').write('x')\" && python3 s.py",          # a name it builds
    "python3 -c \"import subprocess, sys; subprocess.run(sys.argv[1:])\" x && python3 s.py",  # a program it starts that cannot be read
    "node -e \"require('fs').writeFileSync(process.argv[1], 'x')\" s.py && python3 s.py",
])
def test_written_contents_holds_every_other_script_where_a_program_may_write_any_file(tmp_path, line):
    written = guards.written_contents(line, str(tmp_path))
    assert written[guards.ANY_FILE] == guards.UNKNOWN_CONTENT and written[_at(tmp_path, "s.py")] == guards.UNKNOWN_CONTENT


def test_written_contents_reads_a_shell_script_the_line_runs_and_leaves_what_is_not_written(tmp_path):
    (tmp_path / "w.sh").write_text("echo 'print(5)' > s5.py\n")
    assert guards.written_contents("bash w.sh && python3 s5.py", str(tmp_path))[_at(tmp_path, "s5.py")] == "print(5)"
    assert guards.written_contents("chmod +x s.py && touch t.py && rm -f u.py && mkdir d", str(tmp_path)) == {}


def test_a_script_another_program_may_have_written_waits_and_a_shell_script_s_writes_are_read(tmp_path):
    (tmp_path / "s.py").write_text("print(1)\n")
    started = "python3 -c \"import subprocess; subprocess.run(['cp', 't.txt', 's.py'])\" && python3 s.py"
    assert "approve followed by the code" in _said(started, tmp_path)
    (tmp_path / "w.sh").write_text("echo " + shlex.quote(CALL) + " > s5.py\n")
    said = _said("bash w.sh && python3 s5.py", tmp_path)
    assert said.startswith("Refused") or "approve followed by the code" in said, said


def test_written_contents_reads_a_sourced_script_and_holds_scripts_past_what_it_follows(tmp_path):
    (tmp_path / "w.sh").write_text("echo 'print(5)' > s5.py\n")
    assert guards.written_contents(". w.sh && python3 s5.py", str(tmp_path))[_at(tmp_path, "s5.py")] == "print(5)"
    for name, runs in (("a.sh", "b.sh"), ("b.sh", "c.sh"), ("c.sh", "d.sh")):
        (tmp_path / name).write_text(f"bash {runs}\n")
    (tmp_path / "d.sh").write_text("echo 'print(6)' > s.py\n")
    deep = guards.written_contents("bash a.sh && python3 s.py", str(tmp_path))
    assert deep[guards.ANY_FILE] == guards.UNKNOWN_CONTENT and deep[_at(tmp_path, "s.py")] == guards.UNKNOWN_CONTENT
    unknown = guards.written_contents("python3 -c \"open('gen.py', 'w').write('x')\" && python3 gen.py && python3 s.py", str(tmp_path))
    assert unknown[_at(tmp_path, "s.py")] == guards.UNKNOWN_CONTENT  # what gen.py now holds, and so writes, cannot be told


# Review round 2's rulings. A program a line starts writes only what the command it starts writes, read the same way, and
# only scripts run after a program that may write any file are held. A copy from a file that already exists and is
# readable carries that file's text; an edit in place, a script written twice and a program's redirected output cannot
# be told.
@pytest.mark.parametrize("line, held", [
    ("python3 -c \"import subprocess; subprocess.run(['git', 'status'])\" && python3 s.py", False),  # starts one that writes nothing
    ("python3 -c \"import os; os.system('ls -la')\" && python3 s.py", False),
    ("node -e \"require('child_process').execSync('git status')\" && python3 s.py", False),
    ("python3 s.py && python3 -c \"import os; open(os.environ['P'], 'w').write('x')\"", False),      # it runs after the script
    ("python3 -c \"import subprocess, sys; subprocess.run(sys.argv[1:])\" x && python3 s.py", True),  # what it starts cannot be read
    ("node -e \"require('child_process').execSync(process.argv[1])\" x && python3 s.py", True),
    ("python3 -m tool && python3 s.py", True),                                                         # a module it cannot read
])
def test_only_what_a_started_program_writes_and_only_scripts_after_it_count(tmp_path, line, held):
    assert (guards.written_contents(line, str(tmp_path)).get(_at(tmp_path, "s.py")) == guards.UNKNOWN_CONTENT) is held, line


def test_what_a_started_program_writes_is_read_the_same_way(tmp_path):
    (tmp_path / "t.txt").write_text("print(2)\n")
    shelled = "python3 -c " + shlex.quote("import subprocess; subprocess.run(\"echo 'print(1)' > s.py\", shell=True)") + " && python3 s.py"
    assert guards.written_contents(shelled, str(tmp_path))[_at(tmp_path, "s.py")] == "print(1)"
    copied = "python3 -c " + shlex.quote("import subprocess; subprocess.run(['cp', 't.txt', 's.py'])") + " && python3 s.py"
    assert guards.written_contents(copied, str(tmp_path))[_at(tmp_path, "s.py")] == "print(2)\n"


def test_a_copy_of_a_file_that_exists_carries_its_text_and_an_edit_in_place_cannot_be_told(tmp_path):
    (tmp_path / "a.py").write_text("print(3)\n")
    (tmp_path / "sub").mkdir()
    def got(line, name):
        return guards.written_contents(line, str(tmp_path)).get(_at(tmp_path, name))
    assert got("cp a.py b.py && python3 b.py", "b.py") == "print(3)\n"
    assert got("cp -f a.py sub/ && python3 sub/a.py", "sub/a.py") == "print(3)\n"
    assert got("cp missing.py b.py && python3 b.py", "b.py") == guards.UNKNOWN_CONTENT
    assert got("cat > a.py <<'EOF'\nprint(4)\nEOF\ncp a.py b.py && python3 b.py", "b.py") == guards.UNKNOWN_CONTENT  # a source the line writes
    assert got("python3 -c \"import os; open(os.environ['P'], 'w')\" && cp a.py b.py", "b.py") == guards.UNKNOWN_CONTENT  # changed before it
    assert got("sed -i '' 's/3/4/' a.py && python3 a.py", "a.py") == guards.UNKNOWN_CONTENT


def test_a_copied_script_and_one_after_a_program_that_starts_git_are_judged_as_written(tmp_path):
    (tmp_path / "a.py").write_text(CALL + "\n")
    copied = _said("cp a.py b.py && python3 b.py", tmp_path)  # judged by what it copies: it reaches synthesis's code, as a.py would
    assert "this same line writes with a program" not in copied and "approve followed by the code" in copied, copied
    (tmp_path / "ok.py").write_text("print(1)\n")
    assert _said("cp ok.py b2.py && python3 b2.py", tmp_path) == ""
    after = "cat > s.py <<'EOF'\nprint(1)\nEOF\npython3 -c \"import subprocess; subprocess.run(['git', 'status'])\" && python3 s.py"
    assert "this same line writes with a program" not in _said(after, tmp_path)
    two = "cat > a2.py <<'EOF'\nimport subprocess\nsubprocess.run(['ls'])\nEOF\ncat > b3.py <<'EOF'\nprint(1)\nEOF\npython3 a2.py && python3 b3.py"
    assert "this same line writes with a program" not in _said(two, tmp_path)

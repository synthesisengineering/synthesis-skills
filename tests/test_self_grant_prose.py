"""22.22: a program's strings and comments that only name synthesis's approval and send-window functions are prose, not a
reach of them (2026-11-15: a peer Codex seat's small program, which only wrote its own project-management files, was
refused as running the approval implementation because strings it wrote to a file quoted those names). A call, an
import, an attribute reach, a getattr or a subscript of them, an f-string's expression, and any string a program runs
as code still count, in every spelling the guard held before."""

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
]


@pytest.mark.parametrize("line", CODE)
def test_a_reach_of_the_functions_in_code_is_still_refused(tmp_path, line):
    said = _said(line, tmp_path)
    assert said.startswith("Refused") or "approve followed by the code" in said, (line, said)

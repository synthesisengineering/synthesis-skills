"""A shell line the guard's readers would follow past Python's recursion limit is judged, or held with a plain reason,
and never ends the guard on an exception (BACKLOG A12).

2026-11-18: an operations seat saved the results of its first reads into a workspace file with `python3 -c '<program>'
'<file>' '<JSON>'`, the JSON quoted as a code-mode script quotes it ('"'"' for each apostrophe), and the hook answered
"synthesis guard failed (RecursionError: maximum recursion depth exceeded)". The argument held thousands of slashes (the
results' addresses and closing tags) after an early `[`, and the guard expanded it as a file pattern: glob recurses once a
path part. A pattern of more parts than any protected folder lies deep is now read as written. A line nested past what
the readers follow at all (here, 1,500 levels of `"$(`) waits for the principal's code with that reason.
"""

import json

from synthesis import guards, paths

PROGRAM = ("python3 -c 'import sys,json,pathlib; p=pathlib.Path(sys.argv[1]); d=json.loads(p.read_text()); "
           "d[\"reads\"]=json.loads(sys.argv[2]); p.write_text(json.dumps(d,indent=2)); print(\"saved\")' ")


def _quoted(text: str) -> str:
    """A word quoted as a code-mode script quotes one."""
    return "'" + text.replace("'", "'\"'\"'") + "'"


def _reads(n: int = 400) -> str:
    return json.dumps({"results": [{"title": f"Pat's note {i}", "link": f"https://docs.example.com/d/{i}/edit?usp=sharing",
                                    "html": "<div><p>See the plan</p><p>It's on page 2</p></div>"} for i in range(n)]})


def test_a_long_json_argument_full_of_addresses_is_judged_and_writes_where_it_says(tmp_path):
    line = PROGRAM + _quoted(str(tmp_path / "midday.json")) + " " + _quoted(_reads())
    assert line.count("/") > 3000
    assert guards.check("Bash", {"command": line}, {}, cwd=str(tmp_path)) is None  # it writes the workspace file it names


def test_the_same_argument_beside_a_protected_file_is_still_refused(tmp_path):
    line = PROGRAM + _quoted(str(paths.state() / "midday.json")) + " " + _quoted(_reads())
    said = guards.check("Bash", {"command": line}, {}, cwd=str(tmp_path))
    assert said and ("Refused" in said or "approve followed by the code" in said), said


def test_a_pattern_deeper_than_any_protected_folder_is_read_as_written(tmp_path):
    deep = str(tmp_path) + "/[a]" + "/b*" * 3000
    assert guards._globbed(deep) == [deep]
    line = PROGRAM + _quoted(str(paths.state()) + "/*" + "/b*" * 1500) + " " + _quoted("{}")
    said = guards.check("Bash", {"command": line}, {}, cwd=str(tmp_path))
    assert said and ("Refused" in said or "approve followed by the code" in said), said  # its written prefix names the state


NESTED = 'echo "' + '$(echo "' * 1500 + 'x' + '")' * 1500 + '"'


def test_a_line_nested_past_what_the_readers_follow_waits_with_a_plain_reason(tmp_path, principal):
    session = {"transcript_path": str(principal.transcript), "session_id": "S-principal"}
    said = guards.check("Bash", {"command": NESTED}, {}, cwd=str(tmp_path), session=session)
    assert said and "deeper than this guard can read" in said and "approve followed by the code" in said, said
    principal(said)
    assert guards.check("Bash", {"command": NESTED}, {}, cwd=str(tmp_path), session=session) is None  # one code, once


def test_a_deep_line_run_outside_the_sandbox_asks_one_code_for_both(tmp_path, principal):
    """Each check that would recurse says the same plain reason once, and the one code the call asks for carries every
    request it filed, so the approval of a deep line never stands for a check it did not answer."""
    session = {"transcript_path": str(principal.transcript), "session_id": "S-principal"}
    call = {"cmd": NESTED, "sandbox_permissions": "require_escalated"}
    said = guards.check("exec_command", call, {}, cwd=str(tmp_path), session=session)
    assert said and said.count("deeper than this guard can read") == 1 and "outside the harness's sandbox" in said, said
    principal(said)
    assert guards.check("exec_command", call, {}, cwd=str(tmp_path), session=session) is None

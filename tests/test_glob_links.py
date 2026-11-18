"""A file pattern names what it matches on the disk, through any link, as the shell expands it (review round 1 of 5.25.1).

The guard compared a pattern with the protected folders by its spelling alone, and, since A12, read one of more than
64 parts as written. Through a link the agent made in its own folder, neither sees where the write lands:
`cp <file> <its folder>/l*k/grants/./././…` (a link `lnk` into approvals/) passed past 64 parts, and
`echo … > <its folder>/c*r/guards.py` (a link `cur` into the runtime's code) passed at any length, though bash and zsh
expand the pattern, follow the link and write the protected file. A pattern is now matched part by part against the
disk, links followed, with no recursion and a cap; one the guard cannot match within the cap waits for the principal's
code with that reason, and never passes. A12 stands: a long JSON argument that writes nothing protected still passes.
"""

import json
import os
import shutil
import subprocess

import pytest

from synthesis import guards, paths

PADS = (0, 5, 70)


@pytest.fixture
def through_links(isolated_home, tmp_path):
    """The approvals folder and the runtime's code in this test's home, and links to each in the agent's own folder."""
    (isolated_home / "approvals" / "grants").mkdir(parents=True, exist_ok=True)
    (isolated_home / "approvals" / "line-allowances.json").write_text('{"lines": {}}\n', encoding="utf-8")
    (isolated_home / "current" / "synthesis").mkdir(parents=True, exist_ok=True)
    (isolated_home / "current" / "synthesis" / "guards.py").write_text("# the guard\n", encoding="utf-8")
    work = tmp_path / "work"
    work.mkdir()
    os.symlink(isolated_home / "approvals", work / "lnk")
    os.symlink(isolated_home / "current" / "synthesis", work / "cur")
    source = tmp_path / "g.json"
    source.write_text('{"x": 1}', encoding="utf-8")
    return work, source


def _held(line: str, work) -> bool:
    said = guards.check("Bash", {"command": line}, {}, cwd=str(work))
    return bool(said) and ("Refused" in said or "approve followed by the code" in said)


@pytest.mark.parametrize("pad", PADS)
def test_a_copy_into_approvals_through_a_pattern_and_a_link_is_held_at_any_length(through_links, pad):
    work, source = through_links
    assert _held(f"cp {source} {work}/l*k/grants/{'./' * pad}", work), pad


@pytest.mark.parametrize("pad", PADS)
def test_a_redirect_over_the_approved_lines_through_a_pattern_and_a_link_is_held(through_links, pad):
    work, _ = through_links
    assert _held(f"echo '{{\"lines\": {{}}}}' > {work}/l*k/{'./' * pad}line-allowances.json", work), pad


@pytest.mark.parametrize("pad", PADS)
def test_a_redirect_over_the_guards_code_through_a_pattern_and_a_link_is_refused_as_without_one(through_links, pad):
    work, _ = through_links
    assert _held(f"echo x > {work}/cur/guards.py", work)  # the control: no pattern
    assert _held(f"echo x > {work}/c*r/{'./' * pad}guards.py", work), pad
    assert _held(f"cp {work}/../g.json {work}/c*r/{'./' * pad}", work), pad


@pytest.mark.skipif(not shutil.which("bash"), reason="no bash on this machine")
def test_the_shell_does_write_there(through_links, isolated_home):
    """What the routes above would do if let through: bash expands the redirect's pattern and follows the link."""
    work, _ = through_links
    subprocess.run(["bash", "-c", f"echo changed > {work}/c*r/{'./' * 70}guards.py"], cwd=str(work), check=True)
    assert (isolated_home / "current" / "synthesis" / "guards.py").read_text(encoding="utf-8") == "changed\n"


def test_a_pattern_that_names_more_than_the_cap_waits_with_a_plain_reason(tmp_path):
    many = tmp_path / "many"
    for n in range(80):
        (many / f"d{n:02}").mkdir(parents=True)
    said = guards.check("Bash", {"command": f"cp {tmp_path}/x {many}/*/"}, {}, cwd=str(tmp_path))
    assert said and "pattern" in said and "approve followed by the code" in said, said


def test_a_pattern_through_a_link_loop_is_matched_without_recursing(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    os.symlink(work, work / "loop")
    line = f"echo x > {work}/{'l*p/' * 1500}x"
    said = guards.check("Bash", {"command": line}, {}, cwd=str(work))  # judged, never an exception
    assert said is None or "approve followed by the code" in said or "Refused" in said, said


def test_a_long_json_argument_that_writes_nothing_protected_still_passes(tmp_path):
    reads = json.dumps({"results": [{"title": f"Pat's note {i}", "link": f"https://docs.example.com/d/{i}/edit?usp=sharing"}
                                    for i in range(600)]})
    quoted = "'" + reads.replace("'", "'\"'\"'") + "'"
    line = (f"python3 -c 'import sys,pathlib; pathlib.Path(sys.argv[1]).write_text(sys.argv[2])' "
            f"'{tmp_path}/midday.json' {quoted}")
    assert line.count("/") > 3000
    assert guards.check("Bash", {"command": line}, {}, cwd=str(tmp_path)) is None
    assert paths.state()  # its home is the test's own

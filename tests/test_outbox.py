"""The outbox: one folder for the files an agent attaches to an outgoing message.

A self-hosted mail connector reads a local file only from its own attachment folder and the folders it was
started with, so a file an agent stages has to sit where the agent may write and the connector may read. These
tests cover the folder itself; the send guard's use of it is in test_send_guard.py, the doctor's in
test_doctor.py, and the connector's start script in the meeting-transcripts skill's tests.
"""

import os

import pytest

from synthesis import guards, paths


def test_the_outbox_is_a_folder_of_the_synthesis_home(isolated_home, monkeypatch, tmp_path):
    assert paths.outbox() == isolated_home / "outbox"
    monkeypatch.delenv("SYNTHESIS_HOME")
    monkeypatch.setenv("HOME", str(tmp_path / "user"))
    assert paths.outbox() == tmp_path / "user" / ".synthesis" / "v5" / "outbox"


def test_no_protected_folder_holds_the_outbox_and_it_holds_none(tmp_path):
    """Approvals, the board, the transcripts and the approved commit lines stay apart from a folder every agent
    writes: neither inside it nor around it."""
    outbox = os.path.realpath(paths.outbox())
    for config in ({}, {"line_allowances": str(tmp_path / "policy" / "line-allowances.json")}):
        roots = [os.path.realpath(root) for root in guards._protected_roots(config)]
        assert len(roots) >= 6
        assert [root for root in roots if paths.inside(outbox, root) or paths.inside(root, outbox)] == []


WRITES = [
    ("Write", {"file_path": "{folder}/plan.pdf", "content": "x"}),
    ("Edit", {"file_path": "{folder}/notes.txt", "old_string": "a", "new_string": "b"}),
    ("apply_patch", {"input": "*** Begin Patch\n*** Add File: {folder}/plan.txt\n+x\n*** End Patch\n"}),
    ("Bash", {"command": "mkdir -p {folder} && cp {scratch}/plan.pdf {folder}/"}),
    ("Bash", {"command": "cp -R {scratch}/deck {folder}/deck"}),
    ("Bash", {"command": "OUT={folder}; cp {scratch}/plan.pdf \"$OUT/plan.pdf\""}),
    ("Bash", {"command": "cd {folder} && cp {scratch}/plan.pdf ."}),
    ("Bash", {"command": "python3 -c 'import shutil; shutil.copy(\"{scratch}/plan.pdf\", \"{folder}/plan.pdf\")'"}),
    ("Bash", {"command": "mv {scratch}/plan.pdf {folder}/plan.pdf"}),
    ("Bash", {"command": "rm {folder}/plan.pdf"}),
    ("exec_command", {"cmd": "cp {scratch}/plan.pdf {folder}/plan.pdf"}),
]


@pytest.mark.parametrize("tool,payload", WRITES, ids=[f"{tool}-{n}" for n, (tool, _) in enumerate(WRITES)])
def test_an_agent_may_stage_a_file_in_the_outbox_and_not_in_the_state_folder_beside_it(tool, payload, tmp_path):
    """The file tools and the shell both: a copy, a move, a script's write and a removal. The same write aimed one
    folder over, where approvals live, is refused, so the guard was looking."""
    def judged(folder) -> str:
        filled = {key: value.format(folder=folder, scratch=tmp_path / "scratch") for key, value in payload.items()}
        return guards.check(tool, filled, {}, cwd=str(tmp_path)) or ""

    assert judged(paths.outbox()) == ""
    assert "Refused" in judged(paths.state())

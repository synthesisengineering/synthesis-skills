"""Work in a shared checkout stays safe (a project session's incident and gaps, 2026-10-20): uncommitted changes
are journaled and restorable, a release never leaves them unowned, a claim names who left them, a claimed path is
protected when written, and the project index has one safe way to change a field."""

import subprocess

import pytest

from synthesis import board, checkout, cli, guards


def _git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "shared"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    (root / "notes.md").write_text("first line\n", encoding="utf-8")
    _git(root, "add", "notes.md")
    _git(root, "commit", "-q", "-m", "init")
    return root


def test_a_snapshot_keeps_an_uncommitted_edit_restorable_and_changes_nothing(repo):
    notes = repo / "notes.md"
    notes.write_text("first line\nan edit nobody committed\n", encoding="utf-8")
    sha = checkout.snapshot(str(repo), "test", "S1")
    assert sha and _git(repo, "stash", "list") == "" and "notes.md" in _git(repo, "status", "--porcelain")
    notes.write_text("", encoding="utf-8")  # the incident: the file emptied by a script
    assert checkout.show(sha, str(notes)) == "first line\nan edit nobody committed\n"
    assert [r["sha"] for r in checkout.journal(str(notes))] == [sha]
    _git(repo, "checkout", "--", "notes.md")
    assert checkout.snapshot(str(repo), "clean tree", "S1") == ""  # nothing uncommitted, nothing kept


def test_release_refuses_to_leave_uncommitted_work_unowned_and_claim_names_who_left_it(repo, capsys):
    notes = str(repo / "notes.md")
    assert cli.main(["--session", "S1", "claim", notes, "--project", "alpha"]) == 0
    (repo / "notes.md").write_text("first line\nhalf done\n", encoding="utf-8")
    assert cli.main(["--session", "S1", "release"]) == 1
    assert "uncommitted changes" in capsys.readouterr().err and board.load("S1").claims
    assert cli.main(["--session", "S1", "release", "--hand-to", "project:alpha"]) == 0
    assert board.load("S1").claims == []
    board.touch("S3", project="alpha")
    assert "Handing you uncommitted changes" in board.inbox("S3", "alpha")[0]["text"]
    assert cli.main(["--session", "S2", "claim", notes]) == 0
    assert "already has uncommitted changes, last claimed by S1 (project alpha)" in capsys.readouterr().out
    assert checkout.journal(notes)  # the release and the claim both left a snapshot


def test_a_claimed_path_is_protected_when_written_not_first_at_commit(repo):
    notes = str(repo / "notes.md")
    board.claim("S1", [notes], project="alpha")
    other = {"session_id": "S2"}
    assert "claimed by session S1" in guards.check("Write", {"file_path": notes, "content": "x"}, {}, str(repo), other)
    assert "claimed by session S1" in guards.check("Bash", {"command": f"echo x > {notes}"}, {}, str(repo), other)
    assert "claimed by session S1" in guards.check("Bash", {"command": "sed -i '' 's/a/b/' notes.md"}, {}, str(repo), other)
    assert guards.check("Bash", {"command": f"cat {notes}"}, {}, str(repo), other) is None
    assert guards.check("Write", {"file_path": notes, "content": "x"}, {}, str(repo), {"session_id": "S1"}) is None


INDEX = """projects:
- id: alpha
  name: Alpha
  status: active
  last_session: "2026-10-01"
  description: >
    The first project.
- id: beta
  name: Beta
  status: active
  last_session: "2026-10-02"
"""


def test_index_set_commits_its_own_change_and_keeps_another_sessions_edit(tmp_path, write_config):
    root = tmp_path / "ai-knowledge-test"
    (root / "projects").mkdir(parents=True)
    index = root / "projects" / "index.yaml"
    index.write_text(INDEX, encoding="utf-8")
    _git(root, "init", "-q", "-b", "main")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "init")
    write_config({"knowledge_roots": [str(root)]})
    index.write_text(INDEX.replace('"2026-10-02"', '"2026-10-15"'), encoding="utf-8")  # another session's edit, uncommitted
    result = checkout.index_set("alpha", "last_session", "2026-10-20", "S1")
    assert "committed" in result
    committed = _git(root, "show", "HEAD", "--", "projects/index.yaml")
    assert '+  last_session: "2026-10-20"' in committed and "2026-10-15" not in committed
    # 2026-10-27: the message named the project and field; a commit message stays generic in every repository
    assert _git(root, "log", "-1", "--format=%s").strip() == "Update docs"
    assert _git(root, "show", "--name-only", "--format=", "HEAD").split() == ["projects/index.yaml"]
    changed = [l for l in _git(root, "show", "--format=", "HEAD").splitlines() if l[:1] in "+-" and l[:3] not in ("+++", "---")]
    assert changed == ['-  last_session: "2026-10-01"', '+  last_session: "2026-10-20"']
    working = index.read_text(encoding="utf-8")
    assert '"2026-10-20"' in working and '"2026-10-15"' in working  # both edits in the working tree
    assert _git(root, "diff", "--cached") == ""  # nothing half-staged left behind
    with pytest.raises(ValueError, match="status is one of"):
        checkout.index_set("alpha", "status", "finished", "S1")
    with pytest.raises(ValueError, match="not a field this command sets"):
        checkout.index_set("alpha", "description", "x", "S1")
    with pytest.raises(ValueError, match="multi-line field"):
        checkout._edit(INDEX.replace("  name: Alpha", "  name: >\n    Alpha"), "alpha", "name", "x")
    board.claim("S9", [str(index)], project="beta")
    with pytest.raises(ValueError, match="claimed by S9"):
        checkout.index_set("beta", "status", "paused", "S1")

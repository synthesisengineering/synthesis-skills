"""Work in a shared checkout stays safe (a project session's incident and gaps, 2026-10-20): uncommitted changes
are journaled and restorable, a release never leaves them unowned, a claim names who left them, a claimed path is
protected when written, and the project index has one safe way to change a field."""

import json
import os
import subprocess
import time

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
    assert checkout.show(sha, str(notes)) == b"first line\nan edit nobody committed\n"
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


def test_a_claimed_path_named_another_way_is_protected_too(repo):
    """2026-11-11: the claim check read a write's target as written, so a variable the command assigned, a copy
    into the file's folder or `dd` wrote through another session's claim."""
    notes = str(repo / "notes.md")
    board.claim("S1", [notes], project="alpha")
    other = {"session_id": "S2"}
    for command in (f"F={notes}; echo x > \"$F\"", "F=notes.md; sed -i '' 's/a/b/' \"$F\"", f"cp /tmp/elsewhere/notes.md {repo}/",
                    f"cp -t {repo} /tmp/elsewhere/notes.md", f"dd if=/tmp/x of={notes}", f"perl -pi -e 's/a/b/' {notes}"):
        assert "claimed by session S1" in (guards.check("Bash", {"command": command}, {}, str(repo), other) or ""), command
    for command in (f"F={notes}; cat \"$F\"", f"cp {notes} /tmp/elsewhere/", f"dd if={notes} of=/tmp/copy"):
        assert guards.check("Bash", {"command": command}, {}, str(repo), other) is None, command


# Records that leave this Mac, part 1 (plan item 13.5, 5.19.0). The audit of 2026-11-11 (§3.2): a snapshot kept
# tracked changes only, so a record no commit had taken yet was in no snapshot when something removed it.

def _tree(repo, sha):
    return _git(repo, "ls-tree", "-r", "--name-only", sha).split()


def test_a_claim_snapshot_keeps_untracked_files_and_changes_nothing(repo):
    (repo / ".gitignore").write_text("build/\n", encoding="utf-8")
    _git(repo, "add", ".gitignore")
    _git(repo, "commit", "-q", "-m", "ignore")
    (repo / "notes.md").write_text("first line\nan edit\n", encoding="utf-8")
    _git(repo, "add", "notes.md")  # one change staged, so the real index is seen to stay as it was
    (repo / "notes.md").write_text("first line\nan edit\nand one more\n", encoding="utf-8")
    (repo / "drafts").mkdir()
    new = repo / "drafts" / "new.md"
    new.write_text("a record not yet committed\n", encoding="utf-8")
    (repo / "build").mkdir()
    (repo / "build" / "out.txt").write_text("ignored\n", encoding="utf-8")

    def state():
        return (_git(repo, "status", "--porcelain=v1", "-uall"), _git(repo, "diff", "--cached"), _git(repo, "diff"),
                _git(repo, "ls-files", "--stage"), _git(repo, "stash", "list"))

    before = state()
    sha = checkout.snapshot(str(repo), "claim", "S1")
    assert sha and state() == before and before[-1] == ""
    new.unlink()  # what the audit names: a record nobody had committed, removed
    assert checkout.show(sha, str(new)) == b"a record not yet committed\n"
    assert checkout.show(sha, str(repo / "notes.md")) == b"first line\nan edit\nand one more\n"  # the working tree's
    assert "build/out.txt" not in _tree(repo, sha)  # what .gitignore excludes is not kept
    row = checkout.journal(str(new))[0]
    assert row["sha"] == sha and sorted(row["files"]) == ["drafts/new.md", "notes.md"] and "tracked_only" not in row


def test_an_untracked_file_past_a_limit_is_named_in_the_journal_and_not_kept(repo, monkeypatch):
    monkeypatch.setattr(checkout, "UNTRACKED_MAX", 100)  # bytes in one file (2 MB in use)
    monkeypatch.setattr(checkout, "UNTRACKED_ALL", 150)  # bytes in all
    monkeypatch.setattr(checkout, "UNTRACKED_FILES", 2)  # files in all
    monkeypatch.setattr(checkout, "LEFT_NAMED", 2)  # names the journal lists
    for name, size in (("a.md", 80), ("b.md", 80), ("big.bin", 101), ("c.md", 10), ("d.md", 10)):
        (repo / name).write_bytes(b"x" * size)
    sha = checkout.snapshot(str(repo), "release", "S1")
    assert sorted(_tree(repo, sha)) == ["a.md", "c.md", "notes.md"]  # b.md past the total, big.bin past one file's, d.md past the count
    row = checkout.journal()[0]
    assert row["files"] == ["a.md", "c.md"] and row["left"] == ["b.md", "big.bin"] and row["left_count"] == 3
    for name in ("a.md", "b.md", "big.bin", "c.md", "d.md"):
        (repo / name).unlink()
    (repo / "huge.bin").write_bytes(b"x" * 101)
    assert checkout.snapshot(str(repo), "release", "S1") == ""  # nothing kept, so no snapshot...
    row = checkout.journal()[0]
    assert row["sha"] == "" and row["files"] == [] and row["left"] == ["huge.bin"]  # ...but the journal names it


@pytest.mark.skipif(os.name != "posix" or os.geteuid() == 0, reason="root reads a file whatever its mode")
def test_an_untracked_file_git_cannot_read_is_named_and_the_rest_kept(repo):
    locked, readable = repo / "locked.md", repo / "readable.md"
    locked.write_text("x\n", encoding="utf-8")
    readable.write_text("y\n", encoding="utf-8")
    locked.chmod(0)
    try:
        sha = checkout.snapshot(str(repo), "claim", "S1")
    finally:
        locked.chmod(0o644)
    assert "readable.md" in _tree(repo, sha) and "locked.md" not in _tree(repo, sha)
    assert checkout.journal(str(locked))[0]["left"] == ["locked.md"]


def test_a_snapshot_git_cannot_write_keeps_the_tracked_changes_and_names_the_rest(repo, monkeypatch):
    monkeypatch.setattr(checkout, "_tree_commit", lambda *args: "")
    (repo / "notes.md").write_text("first line\nedited\n", encoding="utf-8")
    (repo / "new.md").write_text("untracked\n", encoding="utf-8")
    sha = checkout.snapshot(str(repo), "claim", "S1")
    assert sha and checkout.show(sha, str(repo / "notes.md")) == b"first line\nedited\n"
    row = checkout.journal()[0]
    assert row["files"] == ["notes.md"] and row["left"] == ["new.md"] and "tracked_only" not in row


def test_the_session_start_snapshot_stays_tracked_only_and_its_journal_line_says_so(repo, capsys):
    """The session-start snapshot runs inside the hook's 50 ms budget, so it keeps tracked changes alone."""
    from synthesis import hook
    (repo / "new.md").write_text("untracked\n", encoding="utf-8")
    assert checkout.snapshot(str(repo), "session start", "S1", untracked=False) == ""  # an untracked file alone
    (repo / "notes.md").write_text("first line\nedited\n", encoding="utf-8")
    hook.session_start({"session_id": "S1", "cwd": str(repo)})
    row = checkout.journal()[0]
    assert row["reason"] == "session start" and row["files"] == ["notes.md"] and row["tracked_only"] is True
    assert "new.md" not in _tree(repo, row["sha"])
    assert cli.main(["journal"]) == 0 and "untracked files not looked at" in capsys.readouterr().out


def test_a_snapshot_needs_no_configured_identity_and_never_signs(repo, tmp_path, monkeypatch):
    """`git stash create` falls back to an identity of its own; a snapshot written as a commit must as well, and
    must never wait on a signing program."""
    config = tmp_path / "no-identity-gitconfig"
    config.write_text("[commit]\n\tgpgsign = true\n[gpg]\n\tprogram = false\n", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    for key in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL", "EMAIL"):
        monkeypatch.delenv(key, raising=False)
    (repo / "new.md").write_text("untracked\n", encoding="utf-8")
    sha = checkout.snapshot(str(repo), "claim", "S1")
    assert sha and checkout.show(sha, str(repo / "new.md")) == b"untracked\n"


def test_a_snapshot_keeps_a_checkout_with_no_commit_yet_and_one_in_a_merge(tmp_path, repo):
    """`git stash create` refuses both: a checkout with no commit, and one with unmerged paths."""
    fresh = tmp_path / "fresh"
    fresh.mkdir()
    _git(fresh, "init", "-q", "-b", "main")
    (fresh / "first.md").write_text("the first record\n", encoding="utf-8")
    sha = checkout.snapshot(str(fresh), "claim", "S1")
    assert sha and checkout.show(sha, str(fresh / "first.md")) == b"the first record\n"
    _git(repo, "checkout", "-q", "-b", "other")
    (repo / "notes.md").write_text("theirs\n", encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "theirs")
    _git(repo, "checkout", "-q", "main")
    (repo / "notes.md").write_text("ours\n", encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "ours")
    subprocess.run(["git", "-C", str(repo), "merge", "-q", "other"], capture_output=True, text=True)  # a conflict
    assert "UU notes.md" in _git(repo, "status", "--porcelain")
    sha = checkout.snapshot(str(repo), "claim", "S1")
    assert sha and b"<<<<<<<" in checkout.show(sha, str(repo / "notes.md"))
    assert "UU notes.md" in _git(repo, "status", "--porcelain")  # the merge is left as it was


def test_release_and_claim_count_an_untracked_file_under_the_claim(repo, capsys):
    """IR-07 counted tracked changes only, so a new record under a claim was released unowned, and the next claim
    over it said nothing."""
    folder = repo / "drafts"
    folder.mkdir()
    new = folder / "new.md"
    assert cli.main(["--session", "S1", "claim", str(folder), "--project", "alpha"]) == 0
    new.write_text("a new record\n", encoding="utf-8")
    assert cli.main(["--session", "S1", "release"]) == 1
    assert str(new) in capsys.readouterr().err and board.load("S1").claims
    assert cli.main(["--session", "S1", "release", "--hand-to", "project:alpha"]) == 0
    assert cli.main(["--session", "S2", "claim", str(folder)]) == 0
    assert f"{new} already has uncommitted changes, last claimed by S1" in capsys.readouterr().out
    assert checkout.show(checkout.journal(str(new))[0]["sha"], str(new)) == b"a new record\n"


# 5.19.0, review round 1: each test below failed on the code the round read.

FAKE_AWS = "AKIA" + "ABCDEFGHIJKLMNOP"  # a fixture in two pieces, as the commit check's tests keep theirs; never a real key


def test_a_claims_own_paths_are_kept_first_and_every_one_left_is_named(repo, monkeypatch):
    """S1: the budget went to the whole repository in path order, so the record a claim covered was neither kept nor
    named when another folder held many files."""
    monkeypatch.setattr(checkout, "UNTRACKED_FILES", 2)
    monkeypatch.setattr(checkout, "LEFT_NAMED", 1)
    for name in ("assets/a1.png", "assets/a2.png", "assets/a3.png", "notes/r1.md", "notes/r2.md", "notes/r3.md"):
        (repo / name).parent.mkdir(exist_ok=True)
        (repo / name).write_text(name + "\n", encoding="utf-8")
    sha = checkout.snapshot_paths([str(repo / "notes")], "claim", "S1")[0]
    assert sorted(_tree(repo, sha)) == ["notes.md", "notes/r1.md", "notes/r2.md"]  # the claim's own first
    row = checkout.journal()[0]
    assert row["left"] == ["notes/r3.md", "assets/a1.png"] and row["left_count"] == 4  # every one of the claim's
    assert checkout.journal(str(repo / "notes" / "r3.md"))[0]["sha"] == sha


def test_a_file_git_refuses_is_named_and_the_others_are_kept(repo):
    """M1: one file a required clean filter refused cost the snapshot every untracked file."""
    (repo / ".gitattributes").write_text("*.bin filter=broken\n", encoding="utf-8")
    _git(repo, "config", "filter.broken.clean", "false")
    _git(repo, "config", "filter.broken.required", "true")
    for name in ("draft-1.md", "draft-2.md", "x.bin"):
        (repo / name).write_text(name + "\n", encoding="utf-8")
    sha = checkout.snapshot(str(repo), "claim", "S1")
    assert sorted(_tree(repo, sha)) == [".gitattributes", "draft-1.md", "draft-2.md", "notes.md"]
    assert checkout.journal()[0]["left"] == ["x.bin"]


def test_what_only_the_index_holds_is_kept_beside_the_working_tree(repo):
    """M2: `git stash create` kept the staged state as its second parent; the working-tree snapshot did not."""
    (repo / "notes.md").write_text("staged version\n", encoding="utf-8")
    _git(repo, "add", "notes.md")
    (repo / "notes.md").write_text("working version\n", encoding="utf-8")
    (repo / "only-staged.md").write_text("only in the index\n", encoding="utf-8")
    _git(repo, "add", "only-staged.md")
    (repo / "only-staged.md").unlink()
    sha = checkout.snapshot(str(repo), "claim", "S1")
    assert checkout.show(sha, str(repo / "notes.md")) == b"working version\n"
    assert _git(repo, "show", f"{sha}^2:notes.md") == "staged version\n"
    assert _git(repo, "show", f"{sha}^2:only-staged.md") == "only in the index\n"


def test_a_snapshot_keeps_no_credential(repo):
    """M3: an unignored .env was kept in a local ref, which a mirror push publishes."""
    (repo / ".env").write_text(f"AWS_ACCESS_KEY_ID={FAKE_AWS}\n", encoding="utf-8")
    (repo / "settings.txt").write_text(f"key = {FAKE_AWS}\n", encoding="utf-8")
    (repo / "plain.md").write_text("nothing secret\n", encoding="utf-8")
    (repo / "notes.md").write_text(f"first line\n{FAKE_AWS}\n", encoding="utf-8")  # a tracked file too
    sha = checkout.snapshot(str(repo), "claim", "S1")
    assert sorted(_tree(repo, sha)) == ["notes.md", "plain.md"]
    assert checkout.show(sha, str(repo / "notes.md")) == b"first line\n"  # HEAD's, not the edit holding the key
    assert sorted(checkout.journal()[0]["left"]) == [".env", "notes.md", "settings.txt"]


def test_a_kept_file_is_shown_byte_for_byte(repo, capsysbinary):
    """M4: `journal --show` read a kept file as text: a binary file raised, and CRLF came back as LF."""
    (repo / "scan.pdf").write_bytes(b"%PDF-1.7\n\xe2\x80\xff\x00binary\n")
    (repo / "dos.txt").write_bytes(b"a\r\nb\r\n")
    sha = checkout.snapshot(str(repo), "claim", "S1")
    assert checkout.show(sha, str(repo / "scan.pdf")) == b"%PDF-1.7\n\xe2\x80\xff\x00binary\n"
    assert cli.main(["journal", "--show", sha, str(repo / "dos.txt")]) == 0
    assert capsysbinary.readouterr().out == b"a\r\nb\r\n"


def test_finders_files_are_not_records(repo, capsys):
    """M9: a .DS_Store blocked a release and counted as an unsaved record."""
    folder = repo / "notes"
    folder.mkdir()
    assert cli.main(["--session", "S1", "claim", str(folder)]) == 0
    for name in (".DS_Store", "._draft.md", "Icon\r"):
        (folder / name).write_bytes(b"\x00\x01")
    assert cli.main(["--session", "S1", "release"]) == 0
    assert checkout.snapshot(str(repo), "claim", "S1") == "" and checkout.journal()[0]["reason"] != "claim"


def test_names_with_a_carriage_return_or_staged_twice_are_kept_once_as_written(repo):
    """m9 and m10: text decoding turned \\r in a name into \\n; a path both deleted from the index and present was
    journaled twice."""
    odd = repo / "a\rb.md"
    odd.write_text("committed\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "odd name")
    odd.write_text("edited\n", encoding="utf-8")
    _git(repo, "rm", "-q", "--cached", "notes.md")
    sha = checkout.snapshot(str(repo), "claim", "S1")
    assert checkout.show(sha, str(odd)) == b"edited\n"
    assert sorted(checkout.journal()[0]["files"]) == ["a\rb.md", "notes.md"]


def test_a_snapshot_made_under_a_backdated_clock_is_kept_and_old_journal_lines_go(repo, monkeypatch):
    """m11: the prune read the snapshot commit's date, which GIT_COMMITTER_DATE sets; M7: journal.jsonl was never
    trimmed."""
    from synthesis import paths
    paths.board().mkdir(parents=True, exist_ok=True)
    (paths.board() / "journal.jsonl").write_text(json.dumps({"at": time.time() - 30 * 86400, "repo": str(repo), "sha": "0" * 40,
                                                             "reason": "old", "files": []}) + "\n", encoding="utf-8")
    monkeypatch.setenv("GIT_COMMITTER_DATE", "2020-01-01T00:00:00Z")
    (repo / "notes.md").write_text("edited\n", encoding="utf-8")
    sha = checkout.snapshot(str(repo), "claim", "S1")
    assert sha in _git(repo, "for-each-ref", "--format=%(objectname)", "refs/synthesis/journal/")
    assert [r["reason"] for r in checkout.journal()] == ["claim"]


def test_a_repository_inside_a_claim_is_counted_and_named(repo, capsys):
    """m12: a repository nested in a claimed folder was dropped: its work neither blocked a release nor was named."""
    folder = repo / "notes"
    folder.mkdir()
    nested = folder / "clone"
    _git(repo, "init", "-q", str(nested))
    (nested / "draft.md").write_text("nested work\n", encoding="utf-8")
    assert cli.main(["--session", "S1", "claim", str(folder)]) == 0
    assert cli.main(["--session", "S1", "release"]) == 1
    assert str(nested / "draft.md") in capsys.readouterr().err
    checkout.snapshot(str(repo), "claim", "S1")
    assert "notes/clone/" in checkout.journal()[0]["left"]


def test_the_session_start_snapshot_leaves_the_index_alone_even_while_it_is_locked(repo):
    """Doc 3: `git stash create` rewrote .git/index, and got nothing while another process held index.lock."""
    (repo / "notes.md").write_text("edited\n", encoding="utf-8")
    index = repo / ".git" / "index"
    before = index.read_bytes()
    (repo / ".git" / "index.lock").write_bytes(before)  # another git process at work
    try:
        sha = checkout.snapshot(str(repo), "session start", "S1", untracked=False)
    finally:
        (repo / ".git" / "index.lock").unlink()
    assert sha and checkout.show(sha, str(repo / "notes.md")) == b"edited\n" and index.read_bytes() == before


def test_a_release_is_refused_when_git_cannot_read_the_checkout(repo, capsys):
    """M6: a failing `git status` read as nothing changed, so a release went through."""
    assert cli.main(["--session", "S1", "claim", str(repo / "notes.md")]) == 0
    (repo / ".git" / "index").write_bytes(b"not an index")
    assert cli.main(["--session", "S1", "release"]) == 1
    assert "could not read" in capsys.readouterr().err and board.load("S1").claims


def test_the_hand_to_message_says_what_the_snapshot_kept(repo, monkeypatch):
    """m8: the message said the journal restores every listed file, those not kept among them."""
    monkeypatch.setattr(checkout, "UNTRACKED_MAX", 10)
    folder = repo / "notes"
    folder.mkdir()
    assert cli.main(["--session", "S1", "claim", str(folder), "--project", "alpha"]) == 0
    (folder / "a.md").write_text("a\n", encoding="utf-8")
    (folder / "big.pdf").write_bytes(b"x" * 11)
    assert cli.main(["--session", "S1", "release", "--hand-to", "project:alpha"]) == 0
    board.touch("S3", project="alpha")
    text = board.inbox("S3", "alpha")[0]["text"]
    assert "restores them" not in text and "says whether each was kept" in text

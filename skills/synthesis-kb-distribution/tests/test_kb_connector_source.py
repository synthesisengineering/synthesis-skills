"""Refresh from a local bare repository: the first clone, an update picked up, a failed pull keeps the
last good copy, and a commit that will not load is not served or cloned again."""

import json
import os
import shutil
import stat
import subprocess
import time

import pytest

from kb_connector.source import DirectorySource, GitSource, Library, SourceError, is_ssh, scrub


def git(*args, cwd=None):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def remote(tmp_path, published):
    """A bare repository holding the published tree, and a working clone to push new commits from."""
    bare, work = tmp_path / "remote.git", tmp_path / "work"
    git("init", "--bare", "--quiet", str(bare))
    shutil.copytree(published, work)
    git("init", "--quiet", cwd=work)
    git("add", ".", cwd=work)
    git("commit", "--quiet", "-m", "first", cwd=work)
    git("push", "--quiet", str(bare), "HEAD:refs/heads/main", cwd=work)
    git("symbolic-ref", "HEAD", "refs/heads/main", cwd=bare)
    return bare, work


def push(work, bare, message):
    git("add", "-A", cwd=work)
    git("commit", "--quiet", "-m", message, cwd=work)
    git("push", "--quiet", str(bare), "HEAD:refs/heads/main", cwd=work)
    return git("rev-parse", "HEAD", cwd=work)


def snapshots(workdir):
    return sorted(p.name for p in workdir.iterdir() if p.name.startswith("snapshot-"))


def test_first_clone_serves_the_remote_head_shallow(remote, tmp_path):
    bare, work = remote
    library = Library(GitSource(f"file://{bare}", tmp_path / "cache"))
    assert library.health()["status"] == "unavailable"
    assert library.refresh()
    head = git("rev-parse", "HEAD", cwd=work)
    assert library.current.commit == head and len(library.current.corpus) == 4
    assert git("rev-parse", "--is-shallow-repository", cwd=library.current.root) == "true"
    report = library.health()
    assert report["status"] == "ok" and report["commit"] == head and report["files"] == 4
    assert report["last_refresh_failed"] is False and report["refreshed_at"].endswith("Z")
    json.dumps(report)


def test_a_new_commit_is_picked_up_and_the_old_copy_removed(remote, tmp_path, published, references):
    bare, work = remote
    cache = tmp_path / "cache"
    library = Library(GitSource(f"file://{bare}", cache))
    library.refresh()
    first_root = library.current.root
    assert library.refresh() and library.current.root == first_root  # unchanged head: no new clone
    (work / references.relative_to(published) / "datasets" / "reference" / "teams.md").write_text("---\ntype: Reference\ntitle: Teams\n---\n\nTeams.\n",
                                                             encoding="utf-8")
    second = push(work, bare, "add teams")
    assert library.refresh()
    assert library.current.commit == second and library.current.corpus.get("datasets/reference/teams.md")
    assert library.current.index.search("teams")[0].id == "datasets/reference/teams.md"
    assert snapshots(cache) == [library.current.root.name] and not first_root.exists()


def test_a_failed_pull_keeps_serving_the_last_good_copy(remote, tmp_path):
    bare, work = remote
    library = Library(GitSource(f"file://{bare}", tmp_path / "cache"))
    library.refresh()
    good = library.current
    bare.rename(tmp_path / "moved.git")
    assert library.refresh() is True  # still serving
    assert library.current is good and library.health()["last_refresh_failed"] is True
    assert library.health()["commit"] == good.commit
    (tmp_path / "moved.git").rename(bare)
    assert library.refresh() and library.health()["last_refresh_failed"] is False


def test_a_commit_that_will_not_load_is_refused_and_not_cloned_again(remote, tmp_path, monkeypatch):
    bare, work = remote
    cache = tmp_path / "cache"
    source = GitSource(f"file://{bare}", cache)
    library = Library(source)
    library.refresh()
    good = library.current
    shutil.rmtree(work / "plugins")
    (work / "README.md").write_text("emptied\n", encoding="utf-8")
    push(work, bare, "remove the plugin")
    assert library.refresh() and library.current is good
    assert "expected one plugins/*/skills/*/references folder" in library.last_error
    assert snapshots(cache) == [good.root.name]  # the copy that failed to load is gone
    clones = []
    monkeypatch.setattr(source, "fetch", lambda head: clones.append(head))
    assert library.refresh() and clones == [] and library.health()["last_refresh_failed"] is True


def test_a_first_load_that_fails_leaves_nothing_served_and_nothing_behind(tmp_path):
    cache = tmp_path / "cache"
    library = Library(GitSource(f"file://{tmp_path / 'absent.git'}", cache))
    assert library.refresh() is False and library.current is None
    assert library.health() == {"status": "unavailable", "commit": None, "files": 0, "refreshed_at": None,
                                "last_attempt_at": library.health()["last_attempt_at"], "last_refresh_failed": True}
    assert snapshots(cache) == []


def test_a_branch_can_be_named(remote, tmp_path):
    bare, work = remote
    git("checkout", "--quiet", "-b", "published", cwd=work)
    (work / "extra.txt").write_text("x\n", encoding="utf-8")
    git("add", ".", cwd=work)
    git("commit", "--quiet", "-m", "branch", cwd=work)
    git("push", "--quiet", str(bare), "HEAD:refs/heads/published", cwd=work)
    library = Library(GitSource(f"file://{bare}", tmp_path / "cache", branch="published"))
    assert library.refresh() and library.current.commit == git("rev-parse", "HEAD", cwd=work)
    assert not Library(GitSource(f"file://{bare}", tmp_path / "c2", branch="missing")).refresh()


def test_the_refresh_thread_picks_up_a_change(remote, tmp_path):
    bare, work = remote
    library = Library(GitSource(f"file://{bare}", tmp_path / "cache"))
    library.refresh()
    (work / "note.txt").write_text("x\n", encoding="utf-8")
    second = push(work, bare, "note")
    library.start(0.05)
    try:
        deadline = time.time() + 10
        while library.current.commit != second and time.time() < deadline:
            time.sleep(0.05)
    finally:
        library.stop()
    assert library.current.commit == second


def test_an_ssh_remote_needs_a_key_and_known_hosts_and_the_key_is_made_private(tmp_path):
    url = "git@git.example.com:example/knowledge-plugin.git"
    assert is_ssh(url) and is_ssh("ssh://git@git.example.com/x.git") and not is_ssh(f"file://{tmp_path}")
    with pytest.raises(SourceError, match="KB_GIT_SSH_KEY_FILE and KB_GIT_KNOWN_HOSTS"):
        GitSource(url, tmp_path / "cache")
    with pytest.raises(SourceError, match="cannot read KB_GIT_SSH_KEY_FILE"):
        GitSource(url, tmp_path / "cache", ssh_key_file=str(tmp_path / "missing"), known_hosts="h ssh-ed25519 AAAA")
    mounted = tmp_path / "mounted-key"
    mounted.write_text("test key line one\ntest key line two", encoding="utf-8")  # a mounted secret may lack its newline
    mounted.chmod(0o644)
    source = GitSource(url, tmp_path / "cache", ssh_key_file=str(mounted), known_hosts="git.example.com ssh-ed25519 AAAA")
    key = tmp_path / "cache" / ".ssh" / "deploy_key"
    assert stat.S_IMODE(os.stat(key).st_mode) == 0o600 and stat.S_IMODE(os.stat(key.parent).st_mode) == 0o700
    assert key.read_text(encoding="utf-8") == "test key line one\ntest key line two\n"
    command = source.env["GIT_SSH_COMMAND"]
    for option in ("StrictHostKeyChecking=yes", "BatchMode=yes", "IdentitiesOnly=yes", f"-i {key}"):
        assert option in command
    assert (key.parent / "known_hosts").read_text(encoding="utf-8") == "git.example.com ssh-ed25519 AAAA\n"


def test_errors_never_carry_url_credentials():
    assert scrub("fatal: could not read from https://user:s3cret@git.example.com/x.git") == \
        "fatal: could not read from https://git.example.com/x.git"
    assert len(scrub("x" * 900)) == 500


def test_snapshot_removal_touches_only_snapshot_folders(remote, tmp_path):
    bare, _ = remote
    cache = tmp_path / "cache"
    source = GitSource(f"file://{bare}", cache)
    (cache / "keep-me").mkdir()
    (cache / "snapshot-notahash-1").mkdir()
    Library(source).refresh()
    source.discard(None)
    assert sorted(p.name for p in cache.iterdir()) == ["keep-me", "snapshot-notahash-1"]


def test_a_local_folder_is_served_and_reread(published, references):
    library = Library(DirectorySource(published))
    assert library.refresh() and library.current.commit == "" and library.health()["commit"] is None
    (references / "added.md").write_text("# Added\n", encoding="utf-8")
    assert library.refresh() and library.current.corpus.get("added.md")
    assert not Library(DirectorySource(published / "absent")).refresh()

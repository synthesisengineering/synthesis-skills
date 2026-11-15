"""Review round 2 of 5.23.1 (releases from the protected runtime): N10, N3, N8 and N7.

N10: the released commit was read from the checkout again after preflight, so moving the checkout's main in that
window released another commit. N3: the collection files were written to a temporary folder and hashed back from it,
so a write there in between was pushed. N8: a second run removed the first run's clone, and a gone clone let the run go
on without installing the runtime. N7: the floor's "GitHub's latest release" came from `gh`, found on the caller's
PATH, which an agent can put first.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
for path in (ROOT, ROOT / "skills" / "synthesis-onboarding" / "scripts", Path(__file__).resolve().parents[1] / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import build_collections  # noqa: E402
import release  # noqa: E402
import setup  # noqa: E402
from synthesis import paths  # noqa: E402


@pytest.fixture(autouse=True)
def homes(tmp_path, monkeypatch):
    home = tmp_path / "home"
    for key, value in (("HOME", home), ("SYNTHESIS_HOME", home / ".synthesis" / "v5"), ("CLAUDE_CONFIG_DIR", home / ".claude"),
                       ("CODEX_HOME", home / ".codex"), ("XDG_DATA_HOME", home / ".local" / "share"),
                       ("GIT_CONFIG_GLOBAL", tmp_path / "gitconfig")):
        monkeypatch.setenv(key, str(value))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for name in ("SYNTHESIS_CLAUDE_BIN", "SYNTHESIS_CODEX_BIN", "SYNTHESIS_MUSE_BIN"):
        monkeypatch.setenv(name, "")
    (tmp_path / "gitconfig").write_text("[user]\n\temail = t@example.com\n\tname = t\n[init]\n\tdefaultBranch = main\n")
    home.mkdir()
    return home


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def _repo(where, *commits):
    subprocess.run(["git", "init", "-q", str(where)], check=True)
    for text in commits:
        (where / "notes.md").write_text(text)
        git(where, "add", ".")
        git(where, "commit", "-qm", text.strip())
    return where


def test_n10_the_released_commit_is_the_one_preflight_read(tmp_path, monkeypatch, capsys):
    repo = _repo(tmp_path / "s", "read by preflight\n")
    read = git(repo, "rev-parse", "HEAD")
    asked = []

    def preflight(r, **k):
        _repo(repo, "moved after preflight\n")  # the checkout's main moves while preflight reads GitHub
        return "5.1.0", read, []
    monkeypatch.setattr(release, "preflight", preflight)
    monkeypatch.setattr(release, "fresh_clone", lambda sha: asked.append(sha) or (_ for _ in ()).throw(setup.SetupError("stop")))
    assert release.main(["--repo-root", str(repo), "--session", "S-1", "--clients", ""]) == 1
    assert asked == [read] and git(repo, "rev-parse", "HEAD") != read


def test_n3_a_collection_file_changed_on_disk_while_it_is_stored_is_refused(tmp_path, monkeypatch):
    repo = _repo(tmp_path / "s", "x\n")
    real = build_collections.git

    def racing(r, *args, **kwargs):
        if args[:1] == ("hash-object",):  # the agent's write lands between the build and the hashing
            first = kwargs["stdin"].decode().splitlines()[0]
            Path(first).write_bytes(b"what no CI saw\n")
        return real(r, *args, **kwargs)
    monkeypatch.setattr(build_collections, "git", racing)
    with pytest.raises(build_collections.Unreadable, match="changed"):
        build_collections.tree(repo, {"plugin/a.md": b"what CI passed\n", "plugin/b.md": b"b\n"}, {})
    monkeypatch.setattr(build_collections, "git", real)
    made = build_collections.tree(repo, {"plugin/a.md": b"what CI passed\n"}, {})
    assert git(repo, "cat-file", "-p", f"{made}:plugin/a.md") == "what CI passed"


def test_n8_a_run_removes_only_its_own_clone_and_the_clones_of_runs_that_ended(tmp_path, monkeypatch):
    bare = tmp_path / "github.git"
    source = _repo(tmp_path / "s", "x\n")
    subprocess.run(["git", "clone", "-q", "--bare", "--no-local", str(source), str(bare)], check=True)
    monkeypatch.setattr(release, "CANONICAL_URL", str(bare))
    folder = paths.home() / "releases"
    folder.mkdir(parents=True)
    alive = subprocess.Popen(["sleep", "60"])
    ended = subprocess.Popen(["true"])
    ended.wait()
    try:
        (folder / f".clone-{alive.pid}").mkdir()  # another run, still going
        (folder / f".clone-{ended.pid}").mkdir()  # a run that ended without cleaning up
        clone = release.fresh_clone(git(source, "rev-parse", "HEAD"))
        assert (folder / f".clone-{alive.pid}").is_dir() and not (folder / f".clone-{ended.pid}").exists()
        release.remove_clone(clone)
    finally:
        alive.kill()
        alive.wait()


def test_n8_a_clone_gone_before_the_runtime_install_stops_the_run(tmp_path, monkeypatch, capsys):
    gone = paths.home() / "releases" / ".clone-1"
    gone.mkdir(parents=True)
    monkeypatch.setattr(release, "install_preflight", lambda tag, **k: ("5.1.0", "a" * 40, []))
    monkeypatch.setattr(release, "fresh_clone", lambda sha: gone)
    monkeypatch.setattr(release, "on_main", lambda clone, sha: True)
    monkeypatch.setattr(release, "manifest_version", lambda root: ("5.1.0", ""))
    monkeypatch.setattr(release, "install_and_verify", lambda *a: (["installed"], {}, []))
    assert release.main(["--install-only", "--tag", "v5.1.0", "--clients", ""]) == 1
    out = capsys.readouterr().out
    assert "stopped:" in out and "not a synthesis plugin" not in out, out


def test_n7_the_latest_release_is_read_from_githubs_tags_by_git_never_by_gh(monkeypatch):
    calls = []

    def run(argv, *args, **kwargs):
        calls.append((argv, kwargs.get("env") or {}))
        if "ls-remote" in argv:
            return subprocess.CompletedProcess(argv, 0, "".join(f"{i}\trefs/tags/v{v}\n" for i, v in enumerate(
                ("5.22.0", "5.23.0", "5.24.0", "5.9.9"))) + "9\trefs/tags/v5.24.0^{}\n9\trefs/tags/notes\n", "")
        raise AssertionError(f"unexpected call {argv}")
    said = release.floor_problems("5.23.2", run=run, running=(5, 23, 1))
    assert any("older than GitHub's latest release (v5.24.0)" in p for p in said), said
    assert release.floor_problems("5.24.0", run=run, running=(5, 23, 1)) == []
    argv, env = calls[0]
    assert argv[0] == "git" and "--tags" in argv and release.CANONICAL_URL in argv and env.get("GIT_CONFIG_GLOBAL") == os.devnull
    assert not any(a[0] == "gh" for a, _ in calls)
    unread = release.floor_problems("5.24.0", run=lambda *a, **k: subprocess.CompletedProcess(a[0], 128, "", "no net"),
                                    running=(5, 23, 1))
    assert any("cannot read" in p for p in unread), unread

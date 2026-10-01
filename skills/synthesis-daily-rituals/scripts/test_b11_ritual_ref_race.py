"""Real local Git ref mutation at observation boundary; no network services."""

from pathlib import Path
import os
import subprocess
import sys

PUBLIC = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PUBLIC / "skills/synthesis-daily-rituals/scripts"))
import repo_state as rs  # noqa: E402 - exact source owner bound above


def fixture(tmp_path):
    (tmp_path / ".agents").mkdir()
    (tmp_path / ".agents/repos.yaml").write_text(
        "repos:\n  - name: one\n    path: one\n    ritual_sync: true\n    default_branches: [main]\n"
    )
    repo = tmp_path / "one"
    repo.mkdir()
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(
        GIT_AUTHOR_NAME="Synthetic",
        GIT_AUTHOR_EMAIL="synthetic@example.test",
        GIT_COMMITTER_NAME="Synthetic",
        GIT_COMMITTER_EMAIL="synthetic@example.test",
    )

    def git(*args, input=None):
        p = subprocess.run(
            ["git", *args],
            cwd=repo,
            env=env,
            input=input,
            text=True,
            capture_output=True,
            timeout=10,
        )
        assert p.returncode == 0, p.stderr
        return p.stdout.strip()

    git("init", "-b", "main")
    tree = git("mktree", input="")
    first = git("commit-tree", tree, input="first\n")
    second = git("commit-tree", tree, "-p", first, input="second\n")
    git("update-ref", "refs/heads/main", first)
    remote = tmp_path / "remote.git"
    git("init", "--bare", str(remote))
    git("remote", "add", "origin", str(remote))
    git("push", "origin", first + ":refs/heads/main")
    git("config", "branch.main.remote", "origin")
    git("config", "branch.main.merge", "refs/heads/main")
    return git, second


def test_real_local_upstream_current_positive(tmp_path):
    fixture(tmp_path)
    out = rs.scan(tmp_path, fetch=True)
    assert out["repositories"][0]["status"] == "CURRENT"


def test_upstream_changed_after_arithmetic_refuses_current(tmp_path, monkeypatch):
    git, second = fixture(tmp_path)
    original = rs._git
    changed = []

    def racing(repo, args, **kw):
        answer = original(repo, args, **kw)
        if args[0] == "rev-list" and not changed:
            git("update-ref", "refs/remotes/origin/main", second)
            changed.append(True)
        return answer

    monkeypatch.setattr(rs, "_git", racing)
    out = rs.scan(tmp_path, fetch=True)
    assert changed
    assert out["repositories"][0]["status"] != "CURRENT", out

from pathlib import Path
import sys
import subprocess
import os
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "skills/synthesis-daily-rituals/scripts"))
import repo_state as rs  # noqa: E402 - source-bound import follows path/bootstrap initialization


def workspace(tmp_path):
    (tmp_path / ".agents").mkdir()
    (tmp_path / ".agents/repos.yaml").write_text(
        "repos:\n  - name: one\n    path: one\n    ritual_sync: true\n    default_branches: [main]\n  - name: excluded\n    ritual_sync: false\n"
    )
    repo = tmp_path / "one"
    repo.mkdir()
    subprocess.run(
        ["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True
    )
    return tmp_path


def test_every_declared_repo_has_a_state(tmp_path):
    out = rs.scan(workspace(tmp_path))
    assert out["declared"] == 2 and len(out["repositories"]) == 2
    assert (
        out["repositories"][0]["status"] == "BLIND"
        and out["repositories"][1]["status"] == "EXCLUDED"
    )
    assert out["fetched"] is False


def test_unreachable_or_duplicate_not_silently_omitted(tmp_path):
    root = workspace(tmp_path)
    (root / ".agents/repos.yaml").write_text(
        "repos:\n  - name: absent\n    ritual_sync: true\n    default_branches: [main]\n"
    )
    assert rs.scan(root)["repositories"][0]["status"] == "UNREACHABLE"
    (root / ".agents/repos.yaml").write_text("repos:\n  - name: one\n  - name: one\n")
    with pytest.raises(ValueError):
        rs.scan(root)


def test_foreign_or_alias_path_refuses_before_process(tmp_path, monkeypatch):
    root = workspace(tmp_path)
    (root / ".agents/repos.yaml").write_text(
        "repos:\n  - name: one\n    path: ../elsewhere\n    ritual_sync: true\n    default_branches: [main]\n"
    )
    monkeypatch.setattr(
        rs, "_git", lambda *a, **k: pytest.fail("foreign process dispatched")
    )
    assert rs.scan(root)["repositories"][0]["status"] == "UNREACHABLE"


def test_cached_counts_never_claim_fetched(monkeypatch, tmp_path):
    root = workspace(tmp_path)
    responses = {
        "rev-parse": "a" * 40,
        "for-each-ref": "refs/remotes/origin/main",
        "rev-list": "0\t0",
    }

    def observed(repo, args, **kw):
        if args[0] == "fetch":
            raise OSError("synthetic fetch unavailable")
        return responses[args[0]]

    monkeypatch.setattr(rs, "_git", observed)
    out = rs.scan(root)
    row = out["repositories"][0]
    assert row["status"] == "CACHED" and row["branches"][0]["ahead"] == 0
    out = rs.scan(root, fetch=True)
    assert (
        out["repositories"][0]["status"] == "UNREACHABLE"
    )  # fetch unsupported by fake; never infer success.


def test_actual_local_git_ahead_behind_and_fetch(tmp_path):
    root = workspace(tmp_path)
    repo = root / "one"
    env = dict(
        os.environ,
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

    tree = git("mktree", input="")
    first = git("commit-tree", tree, input="Synthetic first\n")
    second = git("commit-tree", tree, "-p", first, input="Synthetic second\n")
    git("update-ref", "refs/heads/main", second)
    remote = root / "remote.git"
    subprocess.run(
        ["git", "init", "--bare", str(remote)],
        check=True,
        capture_output=True,
        timeout=10,
    )
    git("remote", "add", "origin", str(remote))
    git("push", "origin", first + ":refs/heads/main")
    git("config", "branch.main.remote", "origin")
    git("config", "branch.main.merge", "refs/heads/main")
    result = rs.scan(root, fetch=True)
    row = result["repositories"][0]
    assert (
        row["status"] == "DECISION"
        and row["branches"][0]["ahead"] == 1
        and row["branches"][0]["behind"] == 0
    )
    assert git("rev-parse", "main") == second

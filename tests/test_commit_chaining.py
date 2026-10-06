"""R3.3, E37-E38: under a global hooks path the commit check still runs each repository's own
pre-commit hooks, honors the `.githooks/required` declaration, and never runs itself twice."""

import subprocess
import sys
from pathlib import Path

import pytest

CHECK = Path(__file__).resolve().parents[1] / "synthesis" / "commit_check.py"
FAKE_AWS = "AKIA" + "ABCDEFGHIJKLMNOP"  # split so this file never trips the scanner itself


def _script(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    path.chmod(0o755)
    return path


@pytest.fixture
def global_hook(tmp_path):
    """The synthesis check installed as v5 installs it: the global core.hooksPath."""
    hook = _script(tmp_path / "global-hooks" / "pre-commit", f'exec "{sys.executable}" -S "{CHECK}" "$@"')
    subprocess.run(["git", "config", "--global", "core.hooksPath", str(hook.parent)], check=True)
    return hook


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    return root


def _commit(repo, name="notes.md", text="ordinary text\n", *extra):
    (repo / name).parent.mkdir(parents=True, exist_ok=True)
    (repo / name).write_text(text, encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A", *extra], check=True)
    return subprocess.run(["git", "-C", str(repo), "commit", "-qm", "test"], capture_output=True, text=True, timeout=60)


def _ran(log):
    return log.read_text(encoding="utf-8").split() if log.exists() else []


def test_the_repositorys_githooks_delegate_runs_and_can_refuse(global_hook, repo, tmp_path):
    log = tmp_path / "log"
    delegate = _script(repo / ".githooks" / "pre-commit", f'echo delegate >> "{log}"')
    assert _commit(repo).returncode == 0 and _ran(log) == ["delegate"]
    _script(delegate, "echo 'repository rule broken' >&2; exit 3")
    result = _commit(repo, "b.md")
    assert result.returncode != 0 and "repository rule broken" in result.stderr and ".githooks/pre-commit" in result.stderr


def test_the_repositorys_own_git_hook_runs_too_after_the_delegate(global_hook, repo, tmp_path):
    log = tmp_path / "log"
    _script(repo / ".githooks" / "pre-commit", f'echo delegate >> "{log}"')
    _script(repo / ".git" / "hooks" / "pre-commit", f'echo git-hook >> "{log}"')
    assert _commit(repo).returncode == 0
    assert _ran(log) == ["delegate", "git-hook"]


def test_the_synthesis_checks_run_before_any_repository_hook(global_hook, repo, tmp_path):
    log = tmp_path / "log"
    _script(repo / ".githooks" / "pre-commit", f'echo delegate >> "{log}"')
    result = _commit(repo, "config.txt", f"key = {FAKE_AWS}\n")
    assert result.returncode != 0 and "AWS access key" in result.stderr and _ran(log) == []


@pytest.mark.parametrize("make,expected", [
    (lambda d: None, "is missing"),
    (lambda d: (d.parent.mkdir(parents=True, exist_ok=True), d.write_text("#!/bin/sh\n")), "chmod +x"),
    (lambda d: d.mkdir(parents=True), "not a regular file"),
])
def test_a_declared_delegate_that_cannot_run_blocks_the_commit(global_hook, repo, make, expected):
    (repo / ".githooks").mkdir()
    (repo / ".githooks" / "required").write_text("", encoding="utf-8")
    make(repo / ".githooks" / "pre-commit")
    result = _commit(repo)
    assert result.returncode != 0 and expected in result.stderr


def test_an_undeclared_delegate_that_is_not_executable_is_skipped_aloud(global_hook, repo):
    delegate = repo / ".githooks" / "pre-commit"
    delegate.parent.mkdir()
    delegate.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    result = _commit(repo)
    assert result.returncode == 0 and "not executable" in result.stderr and ".githooks/required" in result.stderr


def test_an_unstaged_rm_of_the_declaration_does_not_withdraw_it_but_a_staged_one_does(global_hook, repo):
    _script(repo / ".githooks" / "pre-commit", "exit 0")
    (repo / ".githooks" / "required").write_text("", encoding="utf-8")
    assert _commit(repo).returncode == 0
    (repo / ".githooks" / "required").unlink()  # unstaged rm
    (repo / ".githooks" / "pre-commit").chmod(0o644)
    subprocess.run(["git", "-C", str(repo), "update-index", "--chmod=-x", ".githooks/pre-commit"], check=True)
    (repo / "b.md").write_text("b\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "b.md"], check=True)
    result = subprocess.run(["git", "-C", str(repo), "commit", "-qm", "b"], capture_output=True, text=True, timeout=60)
    assert result.returncode != 0 and "chmod +x" in result.stderr
    subprocess.run(["git", "-C", str(repo), "rm", "-q", "--cached", ".githooks/required"], check=True)  # staged
    result = subprocess.run(["git", "-C", str(repo), "commit", "-qm", "withdraw"], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr


def test_a_delegate_that_calls_the_check_again_does_not_loop(global_hook, repo, tmp_path):
    log = tmp_path / "log"
    _script(repo / ".githooks" / "pre-commit", f'echo delegate >> "{log}"\nexec "{global_hook}"')
    _script(repo / ".git" / "hooks" / "pre-commit", f'echo git-hook >> "{log}"\nexec "{global_hook}"')
    assert _commit(repo).returncode == 0
    assert _ran(log) == ["delegate", "git-hook"]


def test_installed_as_the_repositorys_own_hook_it_does_not_run_itself(repo, tmp_path):
    log = tmp_path / "log"
    _script(repo / ".git" / "hooks" / "pre-commit", f'echo check >> "{log}"\nexec "{sys.executable}" -S "{CHECK}"')
    _script(repo / ".githooks" / "pre-commit", f'echo delegate >> "{log}"')
    assert _commit(repo).returncode == 0
    assert _ran(log) == ["check", "delegate"]


def test_a_commit_a_hook_makes_in_another_repository_is_still_checked(global_hook, repo, tmp_path):
    other = tmp_path / "other"
    subprocess.run(["git", "init", "-q", str(other)], check=True)
    (other / "leak.txt").write_text(f"{FAKE_AWS}\n", encoding="utf-8")
    _script(repo / ".githooks" / "pre-commit",
            f'unset GIT_INDEX_FILE GIT_DIR GIT_WORK_TREE\ngit -C "{other}" add -A && git -C "{other}" commit -qm leak')
    result = _commit(repo)
    assert result.returncode != 0 and "AWS access key" in result.stderr


def test_a_linked_worktree_runs_the_shared_git_hook_and_its_own_delegate(global_hook, repo, tmp_path):
    log = tmp_path / "log"
    _script(repo / ".git" / "hooks" / "pre-commit", f'echo git-hook >> "{log}"')
    _script(repo / ".githooks" / "pre-commit", f'echo delegate >> "{log}"')
    assert _commit(repo).returncode == 0
    subprocess.run(["git", "-C", str(repo), "worktree", "add", "-q", str(tmp_path / "wt"), "-b", "side"], check=True)
    log.unlink()
    assert _commit(tmp_path / "wt", "c.md").returncode == 0
    assert _ran(log) == ["delegate", "git-hook"]


def test_the_commit_msg_hook_scans_the_message_then_runs_the_repositorys_own(global_hook, repo, tmp_path):
    log = tmp_path / "log"
    _script(global_hook.parent / "commit-msg", f'SYNTHESIS_GIT_HOOK=commit-msg exec "{sys.executable}" -S "{CHECK}" "$@"')
    _script(repo / ".githooks" / "commit-msg", f'echo "msg $(head -1 "$1")" >> "{log}"')
    (repo / ".githooks" / "required").write_text("", encoding="utf-8")
    _script(repo / ".githooks" / "pre-commit", "exit 0")
    assert _commit(repo).returncode == 0 and log.read_text(encoding="utf-8").strip() == "msg test"
    (repo / "b.md").write_text("b\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "b.md"], check=True)
    result = subprocess.run(["git", "-C", str(repo), "commit", "-qm", f"key {FAKE_AWS}"], capture_output=True, text=True, timeout=60)
    assert result.returncode != 0 and "refused this message" in result.stderr
    assert log.read_text(encoding="utf-8").strip() == "msg test"  # the repository's hook never saw the refused message


def test_a_clean_merge_runs_the_checks_and_the_same_pre_commit_delegate(global_hook, repo, tmp_path):
    log = tmp_path / "log"
    _script(global_hook.parent / "pre-merge-commit", f'SYNTHESIS_GIT_HOOK=pre-merge-commit exec "{sys.executable}" -S "{CHECK}" "$@"')
    _script(repo / ".githooks" / "pre-commit", f'echo delegate >> "{log}"')
    (repo / ".githooks" / "required").write_text("", encoding="utf-8")
    assert _commit(repo).returncode == 0
    subprocess.run(["git", "-C", str(repo), "checkout", "-q", "-b", "side"], check=True)
    assert _commit(repo, "side.md").returncode == 0
    subprocess.run(["git", "-C", str(repo), "checkout", "-q", "-"], check=True)
    assert _commit(repo, "main.md").returncode == 0
    log.unlink()
    merged = subprocess.run(["git", "-C", str(repo), "merge", "-q", "--no-edit", "side"], capture_output=True, text=True, timeout=60)
    assert merged.returncode == 0, merged.stderr
    assert _ran(log) == ["delegate"]
    (repo / "leak.md").write_text(f"{FAKE_AWS}\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "checkout", "-q", "-b", "leaky", "HEAD~1"], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "leak.md"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "--no-verify", "-m", "leak"], check=True)
    subprocess.run(["git", "-C", str(repo), "checkout", "-q", "-"], check=True)
    blocked = subprocess.run(["git", "-C", str(repo), "merge", "-q", "--no-edit", "leaky"], capture_output=True, text=True, timeout=60)
    assert blocked.returncode != 0 and "AWS access key" in blocked.stderr

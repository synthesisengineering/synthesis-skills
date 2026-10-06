"""release.py: preflight, one releaser at a time, atomic publication read back from the remote,
and verification of installed bytes against the tag."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
for path in (ROOT, ROOT / "skills" / "synthesis-onboarding" / "scripts", Path(__file__).resolve().parents[1] / "scripts"):
    sys.path.insert(0, str(path))

import release  # noqa: E402
import setup  # noqa: E402
from synthesis import board  # noqa: E402


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("SYNTHESIS_HOME", str(tmp_path / "home" / ".synthesis" / "v5"))
    gitconfig = tmp_path / "gitconfig"
    gitconfig.write_text("[user]\n\temail = t@example.com\n\tname = t\n[init]\n\tdefaultBranch = main\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(gitconfig))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for key in ("CLAUDE_CODE_SESSION_ID", "CODEX_THREAD_ID", "MUSE_SESSION_ID", "SYNTHESIS_SESSION"):
        monkeypatch.delenv(key, raising=False)


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def source_repo(tmp_path, version="5.1.0", changelog=None, remotes=1):
    repo = tmp_path / "synthesis-skills"
    for name in release.MANIFESTS:
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_text(json.dumps({"name": "synthesis-skills", "version": version}))
    (repo / "skills" / "demo").mkdir(parents=True)
    (repo / "skills" / "demo" / "SKILL.md").write_text("---\nname: demo\n---\n")
    (repo / "CHANGELOG.md").write_text(changelog or f"# Changelog\n\n## [{version}] - 2026-10-05\n\n- x\n")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "init")
    for i in range(remotes):
        bare = tmp_path / f"remote{i}.git"
        subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
        git(repo, "remote", "add", "origin" if i == 0 else f"mirror{i}", str(bare))
    git(repo, "push", "-q", "origin", "main")
    git(repo, "remote", "set-head", "origin", "main")
    return repo


green = lambda repo, sha: (True, "CI passed")  # noqa: E731


# ---- preflight ----------------------------------------------------------------

def test_a_coherent_repository_passes_preflight(tmp_path):
    version, problems = release.preflight(source_repo(tmp_path), False, ci=green)
    assert version == "5.1.0" and problems == []


@pytest.mark.parametrize("break_it, message", [
    (lambda r: (r / ".muse-plugin" / "plugin.json").write_text('{"version": "5.0.9"}'), "disagree"),
    (lambda r: (r / "CHANGELOG.md").write_text("## [5.0.9]\n"), "CHANGELOG's newest entry is 5.0.9"),
    (lambda r: (r / "stray.txt").write_text("x"), "uncommitted changes"),
    (lambda r: git(r, "checkout", "-qb", "feature"), "not the default branch"),
])
def test_preflight_refuses_before_pushing(tmp_path, break_it, message):
    repo = source_repo(tmp_path)
    break_it(repo)
    _, problems = release.preflight(repo, False, ci=green)
    assert any(message in p for p in problems)


def test_preflight_refuses_a_plugin_cache_as_the_repository(tmp_path):
    cache = tmp_path / "plugins" / "cache" / "synthesis-engineering" / "synthesis-skills" / "5.1.0"
    cache.mkdir(parents=True)
    version, problems = release.preflight(cache, False, ci=green)
    assert version is None and "installed plugin copy" in problems[0]


def test_preflight_refuses_when_ci_has_not_passed(tmp_path):
    repo = source_repo(tmp_path)
    _, problems = release.preflight(repo, False, ci=lambda r, sha: (False, "CI for abc: failed ['test']"))
    assert problems == ["CI for abc: failed ['test']"]


def test_ci_state_reads_github_runs():
    def gh(runs, code=0):
        return lambda argv, *a, **k: subprocess.CompletedProcess(argv, code, json.dumps(runs), "not signed in")
    ok = [{"status": "completed", "conclusion": "success", "workflowName": "CI"}]
    assert release.ci_state(Path("."), "a" * 40, run=gh(ok))[0] is True
    assert release.ci_state(Path("."), "a" * 40, run=gh([]))[1].startswith("no CI run")
    running = [{"status": "in_progress", "conclusion": "", "workflowName": "CI"}]
    assert "running ['CI']" in release.ci_state(Path("."), "a" * 40, run=gh(running))[1]
    failed = [{"status": "completed", "conclusion": "failure", "workflowName": "CI"}]
    assert "failed ['CI']" in release.ci_state(Path("."), "a" * 40, run=gh(failed))[1]
    assert release.ci_state(Path("."), "a" * 40, run=gh(None, 4))[0] is False  # unknown is not passed


def test_install_only_needs_the_tag_on_head(tmp_path):
    repo = source_repo(tmp_path)
    assert "v5.1.0 is missing" in release.preflight(repo, True)[1][0]
    git(repo, "tag", "v5.1.0")
    assert release.preflight(repo, True) == ("5.1.0", [])


# ---- the release train ----------------------------------------------------------

def test_a_second_session_is_refused_with_the_first_ones_name(tmp_path):
    repo = source_repo(tmp_path)
    release.hold_train(repo, "session-a", "5.1.0")
    with pytest.raises(setup.SetupError, match="session-a"):
        release.hold_train(repo, "session-b", "5.1.0")
    release.hold_train(repo, "session-a", "5.1.0")  # the holder may run again


def test_releases_from_two_worktrees_claim_the_same_file(tmp_path):
    repo = source_repo(tmp_path)
    worktree = tmp_path / "wt"
    git(repo, "worktree", "add", "-q", str(worktree), "-b", "other")
    assert release.train_path(worktree) == release.train_path(repo) == str(repo.resolve() / "CHANGELOG.md")


def test_main_refuses_while_another_session_releases(tmp_path, monkeypatch, capsys):
    repo = source_repo(tmp_path)
    board.claim("other-session", [release.train_path(repo)], goal="release v5.1.0")
    monkeypatch.setattr(release, "ci_state", green)
    monkeypatch.setattr(release, "preflight", lambda r, i: ("5.1.0", []))
    assert release.main(["--repo-root", str(repo), "--session", "me", "--clients", ""]) == 1
    assert "another release is under way" in capsys.readouterr().out and not git(repo, "tag")


# ---- publication -------------------------------------------------------------

def test_publish_pushes_main_stable_and_the_tag_to_every_remote(tmp_path):
    repo = source_repo(tmp_path, remotes=2)
    lines = release.publish(repo, "5.1.0")
    head = git(repo, "rev-parse", "HEAD")
    for bare in (tmp_path / "remote0.git", tmp_path / "remote1.git"):
        assert git(bare, "rev-parse", "main", "stable", "v5.1.0^{commit}").split() == [head] * 3
    assert len(lines) == 2 and all(head[:12] in line for line in lines)


def test_a_rejected_push_is_caught_by_reading_the_remote(tmp_path):
    repo = source_repo(tmp_path)
    other = tmp_path / "other"
    subprocess.run(["git", "clone", "-q", str(tmp_path / "remote0.git"), str(other)], check=True)
    (other / "x").write_text("x")
    git(other, "add", ".")
    git(other, "commit", "-qm", "ahead")
    git(other, "push", "-q", "origin", "main")  # the remote moved: our non-forced atomic push must fail
    with pytest.raises(setup.SetupError, match="do not point at"):
        release.publish(repo, "5.1.0")
    assert "v5.1.0" not in git(tmp_path / "remote0.git", "tag")  # atomic: the tag did not go either


def test_dry_run_publishes_nothing(tmp_path):
    repo = source_repo(tmp_path)
    assert release.publish(repo, "5.1.0", dry_run=True)[0].startswith("would tag v5.1.0")
    assert git(repo, "tag") == ""


# ---- installed bytes against the tag -------------------------------------------

def test_installed_bytes_must_equal_the_tag_whatever_the_label(tmp_path):
    repo = source_repo(tmp_path)
    git(repo, "tag", "v5.1.0")
    installed = tmp_path / "installed"
    setup.export_tree(repo, installed, "v5.1.0")
    assert release.tree_differences(repo, "v5.1.0", installed) == []
    (installed / "skills" / "demo" / "SKILL.md").write_text("stale\n")  # an unbumped edit: same label, old bytes
    (installed / "skills" / "demo" / "extra.md").write_text("x")
    (installed / "skills" / "demo" / "__pycache__").mkdir()
    (installed / "skills" / "demo" / "__pycache__" / "x.pyc").write_bytes(b"\0")
    (installed / ".claude-plugin" / "plugin.json").unlink()
    assert release.tree_differences(repo, "v5.1.0", installed) == [
        "missing .claude-plugin/plugin.json", "differs skills/demo/SKILL.md", "extra skills/demo/extra.md"]


def test_verification_reads_the_folder_the_harness_reports(tmp_path, monkeypatch):
    repo = source_repo(tmp_path)
    git(repo, "tag", "v5.1.0")
    good, stale = tmp_path / "good", tmp_path / "stale"
    setup.export_tree(repo, good, "v5.1.0")
    setup.export_tree(repo, stale, "v5.1.0")
    (stale / "skills" / "demo" / "SKILL.md").write_text("old\n")
    roots = {"claude": (good, "5.1.0"), "codex": (stale, "5.1.0")}
    monkeypatch.setattr(release.doctor, "find_client", lambda name: name if name in roots else None)
    monkeypatch.setattr(setup, "install_plugin", lambda client, binary, **k: f"{client}: updated")
    monkeypatch.setattr(release, "installed_root", lambda client, binary: roots[client])
    lines, verified, found = release.install_and_verify(repo, "5.1.0", ["claude", "codex", "muse"])
    assert set(verified) == {"claude"} and found == ["claude", "codex"]
    assert "muse: not on this Mac; skipped" in lines
    assert any(line.startswith("codex: NOT verified") and "differs skills/demo/SKILL.md" in line for line in lines)


def test_a_wrong_reported_version_fails_even_with_matching_bytes(tmp_path, monkeypatch):
    repo = source_repo(tmp_path)
    git(repo, "tag", "v5.1.0")
    good = tmp_path / "good"
    setup.export_tree(repo, good, "v5.1.0")
    monkeypatch.setattr(release.doctor, "find_client", lambda name: name)
    monkeypatch.setattr(setup, "install_plugin", lambda client, binary, **k: "updated")
    monkeypatch.setattr(release, "installed_root", lambda client, binary: (good, "5.0.9"))
    lines, verified, _ = release.install_and_verify(repo, "5.1.0", ["claude"])
    assert not verified and "reports 5.0.9, not 5.1.0" in lines[-1]

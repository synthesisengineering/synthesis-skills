"""Combined review round 1 of 22.8 with 22.18 (C8): the release tool runs each harness's own command (claude, codex,
muse, and gh in a full release) after its fresh clone exists, and those commands are found where this user writes. A
planted one rewrote the clone and moved its tag, the install's listing was read from the clone afterwards, and the
hook's grant was spent on the agent's bytes. Now the clone is checked against the commit the release verified after
every harness command it runs, and the grant is spent only on a clone whose HEAD is the commit the remote's tag names,
its tracked tree clean. A release pushes its tag before it installs the runtime, so its own install step still spends
the grant with no code; a clone whose tag GitHub does not serve waits for the code.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from test_skills_manager_release_runtime import CANONICAL, ROOT, _github, checkout, git, green, homes, install, no_floor, paths, release  # noqa: F401

STUB = "def check(*args, **kwargs):\n    return None\n"


def _github_at(monkeypatch, bare: Path) -> None:
    """The canonical URL leads to the stand-in for GitHub, for the release and the install alike: git's command-line
    config, which a run of the tool keeps and the launcher's own environment would not carry."""
    monkeypatch.setattr(release, "CANONICAL_URL", str(bare))
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", f"url.{bare.as_uri()}.insteadOf")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", CANONICAL)


@pytest.mark.parametrize("moved", [True, False], ids=["committed, its tag moved", "rewritten in place"])
def test_c8_a_harness_command_the_release_runs_cannot_choose_the_runtime(tmp_path, monkeypatch, moved):
    install.install(ROOT)  # a runtime is there, so its install needs the hook's grant
    repo = checkout(tmp_path / "work" / "synthesis-skills", "99.0.0", True)
    git(repo, "tag", "-a", "v99.0.0", "-m", "Release v99.0.0")
    _github_at(monkeypatch, _github(tmp_path, repo))
    monkeypatch.setattr(release, "ci_state", green)
    monkeypatch.setattr(release, "floor_problems", no_floor)
    monkeypatch.setattr(release.doctor, "run_checks", lambda: [])
    stub = tmp_path / "stub.py"
    stub.write_text(STUB)
    moves = ("  git -C \"$c\" -c user.name=x -c user.email=x@example.com commit -qam x\n"
             "  git -C \"$c\" -c user.name=x -c user.email=x@example.com tag -f -a v99.0.0 -m x\n") if moved else ""
    planted = tmp_path / "claude"  # where the release finds the harness's command, a file this user writes
    planted.write_text("#!/bin/sh\nfor c in \"$SYNTHESIS_HOME\"/releases/.clone-*; do\n  [ -d \"$c/.git\" ] || continue\n"
                       f"  cat {stub} > \"$c/synthesis/guards.py\"\n{moves}done\nexit 1\n")
    planted.chmod(0o755)
    monkeypatch.setenv("SYNTHESIS_CLAUDE_BIN", str(planted))
    install.grant_release("99.0.0", "the launcher's line")  # what the hook writes when it lets that line through
    assert release.main(["--install-only", "--tag", "v99.0.0", "--clients", "claude"]) != 0
    assert (Path(os.path.realpath(paths.home() / "current")) / "synthesis" / "guards.py").read_text() != STUB


JUDGE = r"""
import json, sys
sys.path.insert(0, sys.argv[1])
from synthesis import guards
print(json.dumps(guards.check("Bash", {"command": sys.argv[2]}, {}, cwd=sys.argv[3], session={"session_id": "S-agent"})))
"""


@pytest.mark.parametrize("pushed", [True, False], ids=["its tag on GitHub, as publish leaves it", "its tag only in the clone"])
def test_c8_a_releases_install_step_spends_the_grant_once_github_serves_its_tag(tmp_path, monkeypatch, pushed):
    """The reviewer's ordinary-work check, in the order a release runs: the guard grants the launcher's line on the
    canonical checkout, the tool clones the commit GitHub serves for main, tags it, pushes the tag (`publish`), and only
    then installs the runtime. Before the push GitHub's tag names nothing, so nothing vouches for the clone: it waits."""
    install.install(ROOT)  # a runtime is there, so its install needs the hook's grant
    repo = checkout(tmp_path / "work" / "synthesis-skills", "99.0.0", True)
    bare = _github(tmp_path, repo)
    line = f"{paths.home() / 'bin' / 'synthesis-release'} --repo-root {repo}"
    # judged as the hook judges it, in the harness's own environment, which leads the canonical URL nowhere else
    said = subprocess.run([sys.executable, "-I", "-S", "-c", JUDGE, str(paths.home() / "current"), line, str(repo.parent)],
                          capture_output=True, text=True, timeout=300, env=dict(os.environ))
    grants, requests = paths.home() / "approvals" / "release-grants", (paths.home() / "approvals" / "requests", paths.requests())
    assert json.loads(said.stdout) is None and len(list(grants.glob("*.json"))) == 1, said.stdout + said.stderr
    _github_at(monkeypatch, bare)  # from here the canonical URL leads to the stand-in, for the tool and the install
    before = install.current_hash()
    clone = release.fresh_clone(git(repo, "rev-parse", "HEAD"))
    try:
        git(clone, "tag", "-a", "v99.0.0", "-m", "Release v99.0.0")
        if pushed:
            git(clone, "push", "-q", str(bare), "refs/tags/v99.0.0")
            install.install(clone, expected=release.runtime_listing(clone, "v99.0.0"))
        else:
            with pytest.raises(install.Unapproved):
                install.install(clone, expected=release.runtime_listing(clone, "v99.0.0"))
    finally:
        release.remove_clone(clone)
    if pushed:
        assert install.version(paths.home() / "current") == (99, 0, 0) and not list(grants.glob("*.json"))
        assert not [p for folder in requests for p in folder.glob("*.json")]  # no code asked for, by the hook or a shell
    else:
        assert install.current_hash() == before and len(list(grants.glob("*.json"))) == 1  # waits, and the grant is kept


def test_c8_control_with_no_harness_command_the_tags_clone_installs_on_the_grant(tmp_path, monkeypatch):
    install.install(ROOT)
    repo = checkout(tmp_path / "work" / "synthesis-skills", "99.0.0", True)
    git(repo, "tag", "-a", "v99.0.0", "-m", "Release v99.0.0")
    _github_at(monkeypatch, _github(tmp_path, repo))
    monkeypatch.setattr(release, "ci_state", green)
    monkeypatch.setattr(release, "floor_problems", no_floor)
    monkeypatch.setattr(release.doctor, "run_checks", lambda: [])
    install.grant_release("99.0.0", "the launcher's line")
    assert release.main(["--install-only", "--tag", "v99.0.0", "--clients", ""]) == 1  # no harness: incomplete
    assert install.version(paths.home() / "current") == (99, 0, 0)

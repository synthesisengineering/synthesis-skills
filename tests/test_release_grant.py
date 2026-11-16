"""Review round 2 of 22.18 (K1): the release launcher's install needs no code because the hook grants it, not because
the process looks like the release tool.

22.18's `release_route()` trusted the process's main program and the interpreter's flags (`__main__.__file__` inside a
release, `sys.flags.isolated` and `no_site`), which a program in the same process can set: a forged `__main__` under
`-I -S` replaced the runtime with no code, and so did putting a function of its own in `install.approval`, by name or by
a name built at run time. Now, when the hook lets the release launcher's line through (the protected tool, its options
read), it writes one grant: an install of `v<version>` into this home. `install.install` spends it only for the release
tool's fresh clone in the protected releases folder, at that tag, whose staged copy holds exactly the tag's files, and
only once; anything else asks for the principal's code, and a rollback always does.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from synthesis import install, paths

ROOT = Path(__file__).resolve().parents[1]
STUB = "def check(*args, **kwargs):\n    return None\n"
JUDGE = r"""
import json, sys
sys.path.insert(0, sys.argv[1])
from synthesis import guards
for line in json.loads(sys.argv[2]):
    print(json.dumps(guards.check("Bash", {"command": line}, {}, cwd=sys.argv[3], session={"session_id": "S-agent"})))
"""


@pytest.fixture
def world(tmp_path, monkeypatch):
    """A home of the test's own with the runtime installed from this tree (a first install), and `judge`, which runs the
    guard from that runtime, as the hook runs it."""
    home = tmp_path / "home"
    for key, value in (("HOME", home), ("SYNTHESIS_HOME", home / ".synthesis" / "v5"), ("CLAUDE_CONFIG_DIR", home / ".claude"),
                       ("CODEX_HOME", home / ".codex"), ("XDG_DATA_HOME", home / ".local" / "share"),
                       ("SYNTHESIS_CLAUDE_DESKTOP_DIR", home / "Library" / "Application Support" / "Claude")):
        monkeypatch.setenv(key, str(value))
    for key in ("SYNTHESIS_SESSION", "CLAUDE_CODE_SESSION_ID", "CODEX_THREAD_ID", "MUSE_SESSION_ID", "CDPATH", "OLDPWD"):
        monkeypatch.delenv(key, raising=False)
    github = tmp_path / "github.git"  # GitHub's stand-in: the canonical URL leads here by git's own command-line config
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(github)], check=True)
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", f"url.{github.as_uri()}.insteadOf")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "https://github.com/synthesisengineering/synthesis-skills.git")
    install.install(ROOT)
    work = tmp_path / "work"
    work.mkdir()

    def judge(*lines):
        done = subprocess.run([sys.executable, "-I", "-S", "-c", JUDGE, str(paths.home() / "current"), json.dumps(list(lines)),
                               str(work)], capture_output=True, text=True, timeout=300, env=dict(os.environ))
        assert done.returncode == 0, done.stderr[-2000:]
        return [json.loads(line) for line in done.stdout.splitlines()]
    return {"v5": paths.home(), "work": work, "judge": judge, "tmp": tmp_path, "github": github}


def _launcher(world, options: str) -> str:
    return f"{world['v5'] / 'bin' / 'synthesis-release'} {options}"


def _grants(world) -> list:
    folder = world["v5"] / "state" / "release-grants"
    return sorted(folder.glob("*.json")) if folder.is_dir() else []


def _requests(world) -> list:
    folder = world["v5"] / "state" / "approval-requests"
    return sorted(folder.glob("*.json")) if folder.is_dir() else []


def _clone(world, version: str, name: str = ".clone-1", tag: bool = True, note: str = "", served: bool = True) -> Path:
    """What the release tool's fresh clone holds for a tag: the files the runtime takes, committed, the tag on that
    commit, in the protected releases folder; with `served`, GitHub's stand-in serves that tag at that commit."""
    clone = world["v5"] / "releases" / name
    for rel, path in install._files(ROOT):
        (clone / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, clone / rel)
    (clone / "synthesis" / "__init__.py").write_text(f'__version__ = "{version}"\n{note}')

    def git(*args):
        subprocess.run(["git", "-C", str(clone), *args], check=True, capture_output=True, text=True)
    git("init", "-q", "-b", "main")
    git("add", "-A")
    git("commit", "-qm", f"v{version}")
    if tag:
        git("tag", "-a", f"v{version}", "-m", f"Release v{version}")
        if served:
            git("push", "-q", "--force", str(world["github"]), f"refs/tags/v{version}")
    return clone


def test_the_launchers_line_grants_one_install_of_its_tag_bound_to_the_home_and_version(world):
    assert world["judge"](_launcher(world, "--install-only --tag v99.0.0")) == [None]
    grants = _grants(world)
    assert len(grants) == 1
    data = json.loads(grants[0].read_text())
    assert data["home"] == os.path.realpath(world["v5"]) and data["version"] == "99.0.0"
    # a dry run installs nothing and is granted nothing; the tool run any other way waits and is granted nothing
    assert world["judge"](_launcher(world, "--install-only --tag v98.0.0 --dry-run")) == [None]
    held = world["judge"](f"python3 {ROOT}/skills/synthesis-skills-manager/scripts/release.py --install-only --tag v97.0.0")
    assert held != [None] and len(_grants(world)) == 1


def test_install_spends_the_grant_for_its_tags_fresh_clone_and_asks_no_code(world):
    world["judge"](_launcher(world, "--install-only --tag v99.0.0"))
    assert "synthesis runtime" in install.install(_clone(world, "99.0.0"))
    assert install.version(world["v5"] / "current") == (99, 0, 0)
    assert not _grants(world) and not _requests(world)  # spent, and no code asked for


def test_a_second_install_with_the_same_grant_is_refused(world):
    world["judge"](_launcher(world, "--install-only --tag v99.0.0"))
    install.install(_clone(world, "99.0.0"))
    installed = install.current_hash()
    with pytest.raises(install.Unapproved):
        install.install(_clone(world, "99.0.0", ".clone-2", note="# a second build of the same tag\n"))
    assert install.current_hash() == installed


def test_a_rollback_still_needs_the_principals_code_with_a_grant(world):
    world["judge"](_launcher(world, "--install-only --tag v1.0.0"))
    with pytest.raises(install.Unapproved, match="downgrade"):
        install.install(_clone(world, "1.0.0"))
    assert install.version(world["v5"] / "current") == install.version(ROOT) and len(_grants(world)) == 1  # not spent


def test_the_grant_is_spent_only_on_a_clone_the_remote_vouches_for(world):
    """Combined review round 1, C8: a program the release runs may commit in its clone and move the tag there. The
    grant is spent only where the remote's tag names the clone's HEAD and the clone's tracked tree is clean."""
    world["judge"](_launcher(world, "--install-only --tag v99.0.0"))
    before = install.current_hash()
    moved = _clone(world, "99.0.0", ".clone-moved")
    (moved / "synthesis" / "guards.py").write_text(STUB)

    def git(*args):
        subprocess.run(["git", "-C", str(moved), "-c", "user.name=x", "-c", "user.email=x@example.com", *args], check=True,
                       capture_output=True)
    git("commit", "-qam", "the agent's guard")
    git("tag", "-f", "-a", "v99.0.0", "-m", "moved")  # the clone's tag moved; GitHub's still names the release's commit
    unserved = _clone(world, "99.0.0", ".clone-unserved", note="# a commit GitHub's tag does not name\n", served=False)
    for source in (moved, unserved):
        with pytest.raises(install.Unapproved):
            install.install(source)
    assert install.current_hash() == before and len(_grants(world)) == 1  # nothing spent it


def test_the_spend_asks_the_release_url_itself_from_outside_the_clone(world, monkeypatch):
    """Combined review round 2 of 22.8 with 22.18, R2-1 (defense in depth): the spend asked for the tag through the
    clone's own git config, so a clone whose config sent the release URL to a repository of its own vouched for itself
    when the spend ran with no release around it. It asks from a folder outside the clone, naming the release URL."""
    world["judge"](_launcher(world, "--install-only --tag v99.0.0"))
    clone = _clone(world, "99.0.0", ".clone-own-remote", served=False)
    own = world["tmp"] / "own.git"
    subprocess.run(["git", "init", "-q", "--bare", str(own)], check=True)
    subprocess.run(["git", "-C", str(clone), "push", "-q", str(own), "refs/tags/v99.0.0"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(clone), "config", f"url.{own.as_uri()}.insteadOf", install.RELEASE_URL], check=True)
    for key in ("GIT_CONFIG_COUNT", "GIT_CONFIG_KEY_0", "GIT_CONFIG_VALUE_0"):
        monkeypatch.delenv(key)  # no redirect but the clone's own,
    monkeypatch.setenv("GIT_ALLOW_PROTOCOL", "file")  # and no network: git reaches local repositories only
    before = install.current_hash()
    with pytest.raises(install.Unapproved):
        install.install(clone)
    assert install.current_hash() == before and len(_grants(world)) == 1  # nothing spent it


def test_the_grant_binds_its_home_its_version_its_tags_clone_and_its_bytes(world):
    world["judge"](_launcher(world, "--install-only --tag v99.0.0"))
    before = install.current_hash()
    elsewhere = world["tmp"] / "an-agents-folder"  # the same bytes, outside the protected releases folder
    shutil.copytree(_clone(world, "99.0.0", ".clone-source"), elsewhere)
    untagged = _clone(world, "99.0.0", ".clone-untagged", tag=False, note="# a commit no tag names\n")  # not the tag's commit
    changed = _clone(world, "99.0.0", ".clone-changed")
    with open(changed / "synthesis" / "guards.py", "a", encoding="utf-8") as handle:  # not the tag's bytes
        handle.write("\n# written after the clone was made\n")
    for source in (elsewhere, _clone(world, "99.0.1", ".clone-other"), untagged, changed):
        with pytest.raises(install.Unapproved):
            install.install(source)
    assert install.current_hash() == before and len(_grants(world)) == 1  # none of them spent it
    grant = _grants(world)[0]
    grant.write_text(json.dumps({**json.loads(grant.read_text()), "home": str(world["tmp"] / "another-home")}))
    with pytest.raises(install.Unapproved):  # a grant for another home lets nothing in here
        install.install(_clone(world, "99.0.0", ".clone-home"))
    assert install.current_hash() == before


FORGED_MAIN = ("import sys, types; m = types.ModuleType('__main__'); "
               "m.__file__ = sys.argv[1] + '/releases/x/skills/synthesis-skills-manager/scripts/release.py'; "
               "sys.modules['__main__'] = m; sys.path.insert(0, sys.argv[2]); from synthesis import install; "
               "print(install.install(sys.argv[3]))")
PATCHED = ("import sys; sys.path.insert(0, sys.argv[2]); from synthesis import install; "
           "install.approval = lambda *a, **k: None; print(install.install(sys.argv[3]))")
BUILT = ("import importlib as m, sys; sys.path.insert(0, sys.argv[2]); i = m.import_module('synth' + 'esis.install'); "
         "setattr(i, 'appro' + 'val', lambda *a, **k: None); print(i.install(sys.argv[3]))")


@pytest.mark.parametrize("program,flags", [(FORGED_MAIN, ["-I", "-S"]), (PATCHED, []), (BUILT, [])],
                         ids=["a forged __main__", "approval replaced", "names built at run time"])
def test_k1_no_program_in_the_installers_process_replaces_the_runtime_without_a_grant(world, program, flags):
    evil = world["tmp"] / "my-plugin"
    shutil.copytree(os.path.realpath(world["v5"] / "current"), evil, ignore=shutil.ignore_patterns("__pycache__", "HASH", "SOURCE"))
    (evil / "synthesis" / "guards.py").write_text(STUB)
    world["judge"](_launcher(world, f"--install-only --tag v{'.'.join(map(str, install.version(evil)))}"))  # a grant of its version
    done = subprocess.run([sys.executable, *flags, "-c", program, str(world["v5"]), str(ROOT), str(evil)], capture_output=True,
                          text=True, timeout=300, env=dict(os.environ))
    assert "Unapproved" in done.stderr, (done.stdout[-500:], done.stderr[-1500:])
    assert (Path(os.path.realpath(world["v5"] / "current")) / "synthesis" / "guards.py").read_text() != STUB

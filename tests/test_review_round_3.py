"""Review round 3 of 5.23.1 (releases from the protected runtime): M1, M2, M3 and M5.

M1: a `cd` that resolves `..` physically (`cd -P`, bash's `set -P`, zsh's `chase_dots`, or `chase_links`, which makes even
a plain `cd` physical) took a command through `current/..` into `releases/`, where it overwrote the runtime's guard or
removed `HASH`. Every `cd`, `pushd` and `popd` is now placed both by its text and by its real path, and the command is
held when either lands in a protected folder. M2: the floor was read when an install started and `current` replaced at
its end, with no lock, so an install of an older release overlapping a release put the older runtime back. M3: Apple's
`/usr/bin/python3` shim, which finds the interpreter it runs through the xcrun cache this user can write, could be
pinned as a last resort. M5: in a repository under `pr_gated`, a push of a version tag passed with no code, after which
every release and install was refused as older than GitHub's latest release.
"""

import fcntl
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from synthesis import guards, install, paths

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    for key, value in (("HOME", home), ("SYNTHESIS_HOME", home / ".synthesis" / "v5"), ("CLAUDE_CONFIG_DIR", home / ".claude"),
                       ("CODEX_HOME", home / ".codex"), ("XDG_DATA_HOME", home / ".local" / "share")):
        monkeypatch.setenv(key, str(value))
    (home / "work").mkdir(parents=True)
    install.install(ROOT)
    return home


def _check(line, cwd, config=None):
    return guards.check("Bash", {"command": line}, config or {}, cwd=str(cwd), session={"session_id": "S-1"})


@pytest.fixture
def approved(monkeypatch):
    """The principal's code given for each install over the runtime these tests set up (22.18: install spends it)."""
    monkeypatch.setattr(install, "approval", lambda *args, **kwargs: None)


def test_m1_a_physical_cd_through_current_never_reaches_the_runtime(home):
    release = Path(os.path.realpath(paths.home() / "current")).name
    through = "~/.synthesis/v5/current/.."  # the kernel follows `current` first: physically this is releases/
    lines = [
        f"cd -P {through} && printf x > {release}/synthesis/guards.py",
        f"set -P; cd {through} && printf x > {release}/synthesis/guards.py",
        f"set -o physical && cd {through} && rm {release}/HASH",
        f"cd ~/.synthesis/v5/current && cd -P .. && printf x > {release}/synthesis/guards.py",
        f"setopt chase_dots; cd {through} && rm {release}/HASH",
        f"cd {through} && rm {release}/HASH",  # a plain cd, physical under zsh's chase_links
        f"cd -P {through} && mv ../bin ../bin.old",
        f"pushd -P {through} && rm {release}/HASH",
        f"cd -P {through}; cd {release}/synthesis && printf x > guards.py",
    ]
    passed = [line for line in lines if _check(line, home / "work") is None]
    assert passed == [], passed


def test_m1_a_plain_cd_elsewhere_still_passes(home, tmp_path):
    (home / "work" / "sub").mkdir()
    (tmp_path / "linked").symlink_to(home / "work")
    for line in ("cd sub && printf x > notes.txt", f"cd {tmp_path}/linked/.. && ls", "cd -P sub && printf x > notes.txt",
                 f"cd {home / 'work'} && cd .. && ls"):
        assert _check(line, home / "work") is None, line


def _plugin(tmp_path, name, version):
    folder = tmp_path / name
    shutil.copytree(ROOT / "synthesis", folder / "synthesis", ignore=shutil.ignore_patterns("__pycache__"))
    (folder / "synthesis" / "__init__.py").write_text(f'__version__ = "{version}"\n')
    return folder


def test_m2_the_change_is_read_under_the_lock_against_the_runtime_current_moves_from(home, tmp_path, monkeypatch):
    old, mid, new = _plugin(tmp_path, "old", "98.0.0"), _plugin(tmp_path, "mid", "98.5.0"), _plugin(tmp_path, "new", "99.0.0")
    asked = []
    monkeypatch.setattr(install, "approval", lambda wanted, said, session: asked.append(wanted["action"]))  # each code asked for, given
    install.install(old)  # the runtime the older install starts from
    released = paths.home() / "releases" / "release-99"  # what the overlapping release installs
    shutil.copytree(new / "synthesis", released / "synthesis")
    staged = install._stage

    def overlapping(plugin_root, where):  # the release switches current while this install stages its copy
        made = staged(plugin_root, where)
        link = paths.home() / ".current.release"
        link.symlink_to(released)
        os.replace(link, paths.home() / "current")
        return made
    monkeypatch.setattr(install, "_stage", overlapping)
    install.install(mid)  # 98.5 over 98 when it started; read after its copy is staged, it rolls 99 back: a rollback's code
    assert asked == ["install", "rollback"]
    monkeypatch.setattr(install, "_stage", staged)
    real, held = os.replace, []

    def replacing(source, target):
        if Path(target) == paths.home() / "current":
            with open(paths.home() / "releases" / ".install.lock", "a") as other:  # another process tries the lock
                try:
                    fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    fcntl.flock(other, fcntl.LOCK_UN)
                    held.append(False)
                except BlockingIOError:
                    held.append(True)
        return real(source, target)
    monkeypatch.setattr(os, "replace", replacing)
    install.install(_plugin(tmp_path, "newest", "99.1.0"))
    assert held == [True]  # the lock is held while current moves


def test_m2_a_program_naming_the_locked_half_of_install_waits_for_the_code(home):
    """`install` checks the floor in `_install_locked`, under `_install_lock`; a program that calls either itself could
    move `current` with no lock, so it waits for the principal's code as one naming `install` does (its import starting
    a line: round 4's Q4 showed a program whose import follows a semicolon passing this head, closed by 22.18's reading)."""
    for name in ("_install_locked", "_install_lock"):
        line = (f"python3 -I -c 'from synthesis import install; from pathlib import Path; "
                f"install.{name}(Path(\"plugin\"), install._home(), install.pinned_python(), None)'")
        said = _check(line, home / "work")
        assert said and "approve followed by the code" in said, (name, said)


def test_m2_no_program_that_only_reads_can_hold_the_install_lock(home, approved):
    """flock takes a file opened only to read, and the guard lets a program that only reads run with no code; so the
    lock file is one this user may only write. A reader cannot open it to hold the lock (which would make every install
    wait out its two minutes and refuse), and a program that opens it to write, or changes its mode, waits or is refused."""
    lock = paths.home() / "releases" / ".install.lock"
    assert lock.stat().st_mode & 0o777 == 0o200
    for flags in (os.O_RDONLY, os.O_RDONLY | os.O_NONBLOCK, getattr(os, "O_EVTONLY", os.O_RDONLY)):
        with pytest.raises(PermissionError):
            os.close(os.open(lock, flags))
    for line in (f"python3 -c \"import os, fcntl, time; fd = os.open('{lock}', os.O_WRONLY); fcntl.flock(fd, 2); time.sleep(600)\"",
                 f"python3 -c \"import os, fcntl; fd = os.open('{lock}', 1); fcntl.flock(fd, 2)\"",
                 f"chmod 644 {lock}", f"python3 -c \"import os; os.chmod('{lock}', 0o644)\"", f"exec 9<>{lock}; sleep 600"):
        assert _check(line, home / "work") is not None, line
    lock.chmod(0o644)  # left readable by an earlier build: the next install makes it write-only before it locks
    install.install(ROOT)
    assert lock.stat().st_mode & 0o777 == 0o200


def test_m3_apples_python_shim_is_never_pinned_and_with_nothing_to_pin_install_stops(home, monkeypatch):
    if sys.platform == "darwin":
        assert install.pinned_python(["/usr/bin/python3"]) == ""  # the shim reads its target from a file this user owns
    before = os.path.realpath(paths.home() / "current")
    monkeypatch.setattr(install, "pinned_python", lambda candidates=None: "")
    plugin = paths.home().parent / "plugin"
    shutil.copytree(ROOT / "synthesis", plugin / "synthesis", ignore=shutil.ignore_patterns("__pycache__"))
    (plugin / "synthesis" / "__init__.py").write_text('__version__ = "99.0.1"\n')
    with pytest.raises(install.Refused, match="python.org|Command Line Tools"):
        install.install(plugin)
    assert os.path.realpath(paths.home() / "current") == before


GATED = {"pr_gated": {"acme/skills": {"since": "2026-11-11"}}}


@pytest.fixture
def gated(tmp_path):
    env = {**os.environ, "HOME": str(tmp_path)}
    remote, work = tmp_path / "acme" / "skills.git", tmp_path / "ws" / "skills"
    remote.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True, env=env)
    work.mkdir(parents=True)
    run = lambda *a: subprocess.run(["git", "-C", str(work), *a], check=True, capture_output=True, env=env)  # noqa: E731
    run("init", "-q", "-b", "main")
    (work / "a.md").write_text("a\n")
    run("add", "a.md")
    run("commit", "-qm", "a")
    run("remote", "add", "origin", str(remote))
    run("tag", "-a", "v5.0.0", "-m", "v5.0.0")  # a release the remote holds, so deleting it changes the remote (round 4, Q3)
    run("push", "-q", "-u", "origin", "main", "v5.0.0")
    run("remote", "set-head", "origin", "main")
    run("tag", "-a", "v99.0.0", "-m", "v99.0.0")
    run("tag", "notes-1")
    return work


def test_m5_a_push_of_a_version_tag_to_a_gated_repository_waits_for_the_code(gated, principal):
    held = ["git push origin HEAD:refs/tags/v99.0.0", "git push origin v99.0.0", "git push origin refs/tags/v99.0.0",
            "git push origin tag v99.0.0", "git push origin --tags", "git push origin :refs/tags/v5.0.0",
            "git push origin --delete v5.0.0", "git push --follow-tags origin HEAD:feature"]
    passed = [line for line in held if not _check(line, gated, GATED)]
    assert passed == [], passed
    said = _check(held[0], gated, GATED)
    assert "version tag" in said and "acme/skills" in said, said
    for line in ("git push origin HEAD:feature", "git push origin notes-1", "git push origin refs/tags/notes-1"):
        assert _check(line, gated, GATED) is None, line

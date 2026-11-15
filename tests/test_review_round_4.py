"""Review round 4 of 5.23.1 (releases from the protected runtime): Q1, Q3, Q4 and the claims.

Q1: round 3 judged a line whose `cd` lands elsewhere physically a second time, by a flag a nested check (a program
that starts a command) reset, so a program before `cd -P` cut the second reading short; and the guard followed no
folder a line sets up for `cd`: CDPATH and zsh's cdpath, cdable_vars, OLDPWD. The builder's own probes found more
ways a shell ends up somewhere other than where the guard placed it: a `cd` that fails (a missing folder, a pipeline,
`&`) leaves the next chain where it was; `env cd` moves nothing; zsh's `cd old new` and auto_cd; a cd inside eval,
source, a function, an alias or a trap; enable -n; BASH_ENV; CDPATH spelled through quotes; a command whose name is a
substitution. Every line here wrote the runtime's guards.py with no code. Q3: the version-tag rule held every push
from a checkout with push.followTags, and the deletion of any branch whose name starts with "v". Q4: the floor's
`rollback` keyword could be passed by any program in the same process.
"""

import inspect
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
    for key in ("CDPATH", "OLDPWD"):
        monkeypatch.delenv(key, raising=False)
    (home / "work" / "sub").mkdir(parents=True)
    install.install(ROOT)
    return home


def _check(line, cwd, config=None):
    return guards.check("Bash", {"command": line}, config or {}, cwd=str(cwd), session={"session_id": "S-1"})


def _routes(home):
    v5, work = paths.home(), home / "work"
    name = Path(os.path.realpath(v5 / "current")).name
    inside, below = f"printf x > {name}/synthesis/guards.py", f"printf x > releases/{name}/synthesis/guards.py"
    (work / "go.sh").write_text(f"cd {v5}/releases\n")
    return {  # each: (the folder the harness runs it from, the line)
        "CDPATH on the line": (work, f"CDPATH={v5} cd releases && {inside}"),
        "CDPATH exported": (work, f"export CDPATH={v5}; cd releases; {inside}"),
        "zsh cdpath": (work, f"cdpath=({v5}); cd releases; {inside}"),
        "zsh cdable_vars": (work, f"setopt cdable_vars; r={v5}/releases; cd r; {inside}"),
        "OLDPWD and cd -": (work, f"OLDPWD={v5}/releases; cd - >/dev/null; {inside}"),
        "a nested check before cd -P": (work, "python3 -c \"import subprocess; subprocess.run(['true'])\"; "
                                              f"cd -P {v5}/current/.. && {inside}"),
        "a cd that fails, then ;": (v5, f"cd /no/such/folder; {below}"),
        "a cd that fails, then ||": (v5, f"cd /no/such/folder || {below}"),
        "two cds that fail": (v5, f"cd /no/such/a; cd /no/such/b; {below}"),
        "a cd that fails in a subshell": (v5, f"(cd /no/such/folder; {below})"),
        "a folder removed before its cd": (v5, f"mkdir -p {work}/gone && rmdir {work}/gone; cd {work}/gone; {below}"),
        "a cd in a pipeline": (v5, f"cd {work} | cat; {below}"),
        "a cd sent to the background": (v5, f"cd {work} & {below}"),
        "env cd moves nothing": (v5, f"env cd {work} && {below}"),
        "zsh cd old new": (work, f"mkdir -p {work}/a/releases && cd {work}/a/releases && cd {work}/a {v5} && {inside}"),
        "zsh auto_cd from its input": (work, f"printf 'setopt auto_cd\\n{v5}/releases\\n{inside}\\n' | zsh"),
        "a cd inside eval": (work, f"eval cd {v5}/releases; {inside}"),
        "a cd inside a sourced file": (work, f"source go.sh; {inside}"),
        "a cd inside a function called later": (work, f"f() {{ cd {v5}/releases; }}; cd {work}; f; {inside}"),
        "a cd inside a trap": (work, f"trap 'cd {v5}/releases' DEBUG; {inside}"),
        "a cd inside an alias": (work, f"shopt -s expand_aliases; alias go='cd {v5}/releases'\ngo\n{inside}"),
        "enable -n cd": (v5, f"enable -n cd; cd {work} && {below}"),
        "BASH_ENV for the shell it starts": (work, f"BASH_ENV={work}/go.sh bash -c '{inside}'"),
        "CDPATH spelled through quotes": (work, f"export \"CD\"\"PATH={v5}\"; cd releases; {inside}"),
        "CDPATH spelled as $'...'": (work, f"export $'CD\\x50ATH={v5}'; cd releases; {inside}"),
        "a command named by a substitution": (work, f"$(printf cd) {v5}/releases; {inside}"),
    }


ROUTES = ["CDPATH on the line", "CDPATH exported", "zsh cdpath", "zsh cdable_vars", "OLDPWD and cd -",
          "a nested check before cd -P", "a cd that fails, then ;", "a cd that fails, then ||", "two cds that fail",
          "a cd that fails in a subshell", "a folder removed before its cd", "a cd in a pipeline", "a cd sent to the background", "env cd moves nothing",
          "zsh cd old new", "zsh auto_cd from its input", "a cd inside eval", "a cd inside a sourced file",
          "a cd inside a function called later", "a cd inside a trap", "a cd inside an alias", "enable -n cd",
          "BASH_ENV for the shell it starts", "CDPATH spelled through quotes", "CDPATH spelled as $'...'",
          "a command named by a substitution"]


@pytest.mark.parametrize("name", ROUTES)
def test_q1_no_change_of_folder_takes_a_write_into_the_runtime_unheld(home, name):
    cwd, line = _routes(home)[name]
    assert _check(line, cwd) is not None, f"{name}: passed with no code"


def test_q1_a_cdpath_the_environment_exports_is_followed(home, monkeypatch):
    monkeypatch.setenv("CDPATH", str(paths.home()))
    name = Path(os.path.realpath(paths.home() / "current")).name
    assert _check(f"cd releases && printf x > {name}/synthesis/guards.py", home / "work") is not None


def test_q1_ordinary_changes_of_folder_still_pass(home):
    work = home / "work"
    for folder in "abcdefghij":
        (work / folder).mkdir()
    (work / "venv.sh").write_text("export VIRTUAL_ENV=/tmp/venv\n")
    lines = ["cd sub && printf x > notes.txt", "cd sub; printf x > notes.txt", "CDPATH=. cd sub && ls", f"cd {work}/sub; cd -; printf x > notes.txt",
             "for d in a b; do (cd \"$d\" && printf x > out.txt); done", "cd sub | cat; ls", "env cd sub && printf x > notes.txt",
             "source venv.sh && cd sub && printf x > notes.txt", "alias ll='ls -l'; ls", "set -P; cd sub && printf x > notes.txt",
             "cd -P sub && printf x > notes.txt", "; ".join(f"cd {work}/{f}" for f in "abcdefghij") + "; printf x > notes.txt",
             "cd sub && git status; cd .. && printf x > notes.txt"]
    held = [line for line in lines if _check(line, work) is not None]
    assert held == [], held
    # a folder that is there, entered after nothing that could make, remove or move one, is where the line goes on
    assert _check("cd /tmp; printf x > releases/notes.txt", paths.home()) is None


# --- Q4: no keyword lets an older release in ---------------------------------------------------------------------------

def _plugin(tmp_path, name, version):
    folder = tmp_path / name
    shutil.copytree(ROOT / "synthesis", folder / "synthesis", ignore=shutil.ignore_patterns("__pycache__"))
    (folder / "synthesis" / "__init__.py").write_text(f'__version__ = "{version}"\n')
    return folder


def test_q4_install_takes_no_rollback_keyword_and_refuses_an_older_release_for_every_caller(home, tmp_path):
    assert "rollback" not in inspect.signature(install.install).parameters
    assert "rollback" not in inspect.signature(install._install_locked).parameters
    older, before = _plugin(tmp_path, "older", "1.0.0"), install.current_hash()
    with pytest.raises(install.Refused, match="older than the running"):
        install.install(older)
    with pytest.raises(install.Refused, match="older than the running"):
        install._install_locked(older, paths.home(), install.pinned(paths.home()), None)
    assert install.current_hash() == before


# --- Q3: the tag rule holds only a push that would create, move or delete a version tag -----------------------------------

GATED = {"pr_gated": {"acme/skills": {"since": "2026-11-11"}}}


@pytest.fixture
def checkout(tmp_path):
    env = {**os.environ, "HOME": str(tmp_path)}
    remote, work = tmp_path / "acme" / "skills.git", tmp_path / "ws" / "skills"
    remote.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True, env=env)
    work.mkdir(parents=True)

    def run(*args):
        return subprocess.run(["git", "-C", str(work), *args], check=True, capture_output=True, text=True, env=env).stdout

    run("init", "-q", "-b", "main")
    (work / "a.md").write_text("a\n")
    run("add", "a.md")
    run("commit", "-qm", "a")
    run("tag", "-a", "v5.0.0", "-m", "v5.0.0")  # a release GitHub has
    run("remote", "add", "origin", str(remote))
    run("push", "-q", "-u", "origin", "main", "v5.0.0")
    run("remote", "set-head", "origin", "main")
    run("config", "push.followTags", "true")  # a setting some people keep
    run("checkout", "-qb", "feature")
    (work / "b.md").write_text("b\n")
    run("add", "b.md")
    run("commit", "-qm", "b")
    run("branch", "vendor-update")
    run("push", "-q", "origin", "vendor-update")
    return work, run


def test_q3_a_push_carries_a_version_tag_only_when_the_remote_lacks_one_reachable_from_it(checkout):
    work, run = checkout
    for line in ("git push origin feature", "git push origin HEAD:feature", "git push --follow-tags origin feature"):
        assert _check(line, work, GATED) is None, line  # v5.0.0 is reachable, and the remote has it
    run("tag", "v6.0.0-light")  # a lightweight tag: --follow-tags carries annotated tags alone
    run("checkout", "-qb", "other", "main")
    (work / "c.md").write_text("c\n")
    run("add", "c.md")
    run("commit", "-qm", "c")
    run("tag", "-a", "v8.0.0", "-m", "elsewhere")  # annotated, missing from the remote, but not reachable from feature
    run("checkout", "-q", "feature")
    assert _check("git push origin feature", work, GATED) is None
    run("tag", "-a", "v9.0.0", "-m", "stray")  # on feature: reachable, and the remote lacks it
    said = _check("git push origin feature", work, GATED)
    assert said and "v9.0.0" in said, said
    run("config", "push.followTags", "false")
    assert _check("git push origin feature", work, GATED) is None  # the tag does not travel


def test_q3_a_branch_whose_name_starts_with_v_is_never_taken_for_a_tag(checkout):
    work, run = checkout
    run("config", "push.followTags", "false")
    for line in ("git push origin --delete vendor-update", "git push origin :vendor-update", "git push origin vendor-update",
                 "git push origin vendor-update:vendor-update", "git push origin -d vendor-update"):
        assert _check(line, work, GATED) is None, line
    run("tag", "-a", "v9.9.9", "-m", "stray")  # here, and missing from the remote
    for line in ("git push origin --delete v5.0.0", "git push origin :refs/tags/v5.0.0", "git push origin refs/tags/v9.9.9",
                 "git push origin tag v9.9.9", "git push origin v9.9.9", "git push origin HEAD:v5.0.0", "git push origin +HEAD:refs/tags/v5.0.0"):
        assert _check(line, work, GATED) is not None, line  # makes, moves or deletes a version tag there
    for line in ("git push origin refs/tags/v5.0.0", "git push origin tag v5.0.0", "git push origin v5.0.0", "git push origin --delete v7.1.0"):
        assert _check(line, work, GATED) is None, line  # the remote holds v5.0.0 as it is here, and no v7.1.0 to delete


def test_q3_tags_alone_wait_only_when_one_would_be_made(checkout):
    work, run = checkout
    run("config", "push.followTags", "false")
    assert _check("git push origin --tags", work, GATED) is None  # every version tag here is already there
    run("tag", "-a", "v9.9.9", "-m", "stray")
    assert _check("git push origin --tags", work, GATED) is not None


# --- the claims -----------------------------------------------------------------------------------------------------------

def test_the_docs_no_longer_claim_what_round_4_disproved():
    runtime = (ROOT / "docs" / "runtime-integration.md").read_text(encoding="utf-8")
    release = (ROOT / "skills" / "synthesis-skills-manager" / "references" / "release.md").read_text(encoding="utf-8")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").split("\n## [", 2)[1]  # the newest entry
    assert "whichever way the shell goes" not in runtime
    for text in (release, changelog):
        assert "only the code-approved route may pass a rollback" not in text
        assert "a parameter for the code-approved route" not in text
        assert "waits for the principal's code, as one naming `install` does" not in " ".join(text.split())

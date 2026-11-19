"""5.24.0: the release tool runs from the protected runtime, and publishes and installs only what GitHub serves on the
default branch with CI passed (the principal, 2026-11-15; review round 1 of 5.23.1).

The guard lets the runtime's release launcher run with no code, so the tool itself must refuse every way an agent
could make it publish or install anything else. Round 0 checked the agent's checkout and then read it again at every
stage; round 1 of the review showed objects rewritten after the check (A2), a verified harness folder changed before
the runtime was copied from it (A3), and `--install-only` installing any older release as the runtime (A1). Now the
checkout only names what is released: the release makes a fresh clone of the repository from GitHub, in the protected
releases folder, and builds, tags, pushes, exports and installs from that clone alone; the runtime is installed from
it, its staged copy checked against the tag's listing before `current` moves, and nothing older than the running
runtime or GitHub's latest release installs.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import zlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
for path in (ROOT, ROOT / "skills" / "synthesis-onboarding" / "scripts", Path(__file__).resolve().parents[1] / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import build_collections  # noqa: E402
import release  # noqa: E402
from synthesis import install, paths  # noqa: E402

CANONICAL = "https://github.com/synthesisengineering/synthesis-skills.git"
TOOL = "skills/synthesis-skills-manager/scripts/release.py"
COLLECTIONS = {"core": "core", "branch": "collections", "marketplace": {"name": "demo-collections"},
               "collections": {"core": {"name": "demo-core", "description": "The core."}}}
GENUINE = "---\nname: demo\nmetadata:\n  category: core\n---\nWhat CI passed.\n"


@pytest.fixture(autouse=True)
def homes(tmp_path, monkeypatch):
    """Every home a release reads or writes is the test's own, and no harness is found to install into."""
    home = tmp_path / "home"
    for key, value in (("HOME", home), ("SYNTHESIS_HOME", home / ".synthesis" / "v5"), ("CLAUDE_CONFIG_DIR", home / ".claude"),
                       ("CODEX_HOME", home / ".codex"), ("XDG_DATA_HOME", home / ".local" / "share"),
                       ("RITUAL_STATE_DIR", tmp_path / "rituals"),
                       ("SYNTHESIS_CLAUDE_DESKTOP_DIR", home / "Library" / "Application Support" / "Claude"),
                       ("GIT_CONFIG_GLOBAL", tmp_path / "gitconfig")):
        monkeypatch.setenv(key, str(value))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for name in ("SYNTHESIS_CLAUDE_BIN", "SYNTHESIS_CODEX_BIN", "SYNTHESIS_MUSE_BIN"):
        monkeypatch.setenv(name, "")  # named and empty: that harness is not on this machine
    for key in ("CLAUDE_CODE_SESSION_ID", "CODEX_THREAD_ID", "MUSE_SESSION_ID", "SYNTHESIS_SESSION"):
        monkeypatch.delenv(key, raising=False)
    (tmp_path / "gitconfig").write_text("[user]\n\temail = t@example.com\n\tname = t\n[init]\n\tdefaultBranch = main\n")
    home.mkdir()
    return home


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def checkout(where, version="5.1.0", runtime=False, carry=""):
    """A checkout of the synthesis-skills repository as a release finds it: committed, on main, origin on GitHub.
    With `runtime`, it carries the runtime package of this tree at `version`, so it installs as a runtime; with `carry`
    too, its install.py declares one carried skill more, whose script and test it holds."""
    repo = where
    for manifest in release.MANIFESTS:
        (repo / manifest).parent.mkdir(parents=True, exist_ok=True)
        (repo / manifest).write_text(json.dumps({"name": "synthesis-skills", "version": version}))
    (repo / "skills" / "demo").mkdir(parents=True)
    (repo / "skills" / "demo" / "SKILL.md").write_text(GENUINE)
    (repo / build_collections.LIST).parent.mkdir(parents=True)
    (repo / build_collections.LIST).write_text(json.dumps(COLLECTIONS))
    for license_file in build_collections.LICENSES:
        (repo / license_file).write_text(f"{license_file} terms.\n")
    (repo / "CHANGELOG.md").write_text(f"# Changelog\n\n## [{version}] - 2026-11-15\n\n- x\n")
    if runtime:
        (repo / "synthesis").mkdir()
        for source in (ROOT / "synthesis").glob("*.py"):
            (repo / "synthesis" / source.name).write_bytes(source.read_bytes())
        init = repo / "synthesis" / "__init__.py"
        init.write_text(re.sub(r'__version__ = "[\d.]+"', f'__version__ = "{version}"', init.read_text()))
        if carry:
            (repo / "skills" / carry / "scripts").mkdir(parents=True)
            (repo / "skills" / carry / "scripts" / "later.py").write_text("print('later')\n")
            (repo / "skills" / carry / "tests").mkdir()
            (repo / "skills" / carry / "tests" / "test_later.py").write_text("def test_later():\n    pass\n")
            anchor = '"synthesis-skills-manager", "synthesis-onboarding")'
            declared = repo / "synthesis" / "install.py"
            assert declared.read_text().count(anchor) == 1, "the declaration this helper extends moved"
            declared.write_text(declared.read_text().replace(anchor, anchor[:-1] + f', "{carry}")'))
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    git(repo, "add", ".")
    git(repo, "commit", "-qm", f"v{version}")
    git(repo, "remote", "add", "origin", CANONICAL)
    return repo


def served(head, tag=""):
    return lambda version: {"main": head, "tag": tag}


green = lambda repo, sha: (True, "CI passed")  # noqa: E731
no_floor = lambda version: []  # noqa: E731


def check(repo, **given):
    head = git(repo, "rev-parse", "HEAD")
    version, read, problems = release.preflight(repo, ci=given.get("ci", green), github=given.get("github", served(head)),
                                                floor=given.get("floor", no_floor))
    assert read == (head if version else ""), (read, head)  # the commit it read is the one it returns (round 2, N10)
    return version, problems


def test_a_canonical_checkout_at_the_tip_of_githubs_main_passes(tmp_path):
    assert check(checkout(tmp_path / "s")) == ("5.1.0", [])


# --- each route an agent could take to make the runtime's tool publish what CI did not pass on main -------------------

def test_route_a_different_checkout_is_refused(tmp_path):
    repo = checkout(tmp_path / "s")
    git(repo, "remote", "set-url", "origin", str(tmp_path / "elsewhere.git"))
    version, problems = check(repo)
    assert version is None and "not the canonical checkout" in problems[0] and "elsewhere.git" in problems[0], problems
    assert "not the root of a git checkout" in check(repo / "skills")[1][0]


def test_route_a_fork_is_refused(tmp_path):
    repo = checkout(tmp_path / "s")
    git(repo, "remote", "set-url", "origin", "https://github.com/someone/synthesis-skills.git")
    version, problems = check(repo)
    assert version is None and "someone/synthesis-skills" in problems[0], problems


@pytest.mark.parametrize("change", [
    ("config", "remote.origin.pushurl", "https://github.com/someone/synthesis-skills.git"),
    ("remote", "add", "mirror", "https://example.com/synthesis-skills.git"),
    ("config", f"url.{Path('/tmp/evil.git')}.insteadOf", CANONICAL),
    ("config", f"url.{Path('/tmp/evil.git')}.pushInsteadOf", CANONICAL),
])
def test_route_a_different_remote_is_refused(tmp_path, change):
    repo = checkout(tmp_path / "s")
    git(repo, *change)
    version, problems = check(repo)
    assert version is None and "not the canonical checkout" in problems[0], problems


def test_route_a_local_commit_not_on_githubs_main_is_refused(tmp_path):
    repo = checkout(tmp_path / "s")
    merged = git(repo, "rev-parse", "HEAD")
    (repo / "skills" / "demo" / "SKILL.md").write_text(GENUINE + "changed\n")
    git(repo, "commit", "-qam", "local only")
    _, problems = check(repo, github=served(merged))
    assert any("is not the tip of synthesisengineering/synthesis-skills main" in p for p in problems), problems


@pytest.mark.parametrize("dirty", ["tracked", "untracked"])
def test_route_a_dirty_tree_is_refused(tmp_path, dirty):
    """release.py's own preflight already refused this; the test shows it still does."""
    repo = checkout(tmp_path / "s")
    (repo / ("CHANGELOG.md" if dirty == "tracked" else "stray.txt")).write_text("changed\n")
    _, problems = check(repo)
    assert "the tree has uncommitted changes" in problems, problems


def test_route_a_tag_that_already_exists_is_refused(tmp_path):
    repo = checkout(tmp_path / "s")
    first = git(repo, "rev-parse", "HEAD")
    git(repo, "tag", "v5.1.0")
    git(repo, "commit", "-q", "--allow-empty", "-m", "next")
    _, problems = check(repo)  # the local tag names another commit: release.py's own preflight refused this already
    assert any("v5.1.0 already tags another commit" in p for p in problems), problems
    git(repo, "tag", "-d", "v5.1.0")
    _, problems = check(repo, github=served(git(repo, "rev-parse", "HEAD"), first))  # GitHub has it at another commit
    assert any("already has v5.1.0 at" in p for p in problems), problems


def test_what_github_serves_is_read_with_gits_own_config_left_out():
    calls = []

    def run(argv, *args, **kwargs):
        calls.append((argv, kwargs.get("env") or {}))
        return subprocess.CompletedProcess(argv, 0, "ref: refs/heads/main\tHEAD\nabc\tHEAD\nabc\trefs/heads/main\n"
                                                    "def\trefs/tags/v5.1.0\nabc\trefs/tags/v5.1.0^{}\n", "")
    assert release.github_state("5.1.0", run=run) == {"main": "abc", "tag": "abc"}
    argv, env = calls[0]
    assert CANONICAL in argv and env.get("GIT_CONFIG_GLOBAL") == os.devnull and env.get("GIT_CONFIG_NOSYSTEM") == "1"
    assert release.github_state("5.1.0", run=lambda *a, **k: subprocess.CompletedProcess(a[0], 128, "", "no net")) == {}


@pytest.mark.parametrize("key", ["core.fsmonitor", "core.hooksPath", "credential.helper", "http.proxy", "include.path"])
def test_a_checkout_whose_own_config_runs_programs_or_sends_git_elsewhere_is_refused_before_git_runs_them(tmp_path, key):
    repo = checkout(tmp_path / "s")
    marker = tmp_path / "ran"
    program = tmp_path / "program.sh"
    program.write_text(f"#!/bin/sh\ntouch {marker}\n")
    program.chmod(0o755)
    included = tmp_path / "included.config"  # an included file carries a key that runs the program
    included.write_text(f"[core]\n\tfsmonitor = {program}\n")
    git(repo, "config", key, str(included if key == "include.path" else program))
    version, problems = check(repo)
    assert version is None and key.lower() in problems[0] and not marker.exists(), problems


def test_ci_is_read_from_the_canonical_repository_whatever_the_checkout_names():
    calls = []

    def gh(argv, *args, **kwargs):
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, json.dumps([{"status": "completed", "conclusion": "success"}]), "")
    assert release.ci_state(Path("."), "a" * 40, run=gh)[0] is True
    assert calls[0][calls[0].index("-R") + 1] == "github.com/synthesisengineering/synthesis-skills"


# --- A1: nothing older than the running runtime or GitHub's latest release installs ------------------------------------

def _latest(tag, code=0):
    """GitHub's tags as `git ls-remote --tags` prints them, the highest `tag` (round 2, N7: read by git, not gh)."""
    listed = "".join(f"{'0' * 40}\trefs/tags/{t}\n" for t in ("v5.0.0", tag) if t)
    return lambda argv, *a, **k: subprocess.CompletedProcess(argv, code, listed if code == 0 else "", "no network" * bool(code))


def test_the_floor_is_the_running_runtime_and_githubs_latest_release():
    assert release.floor_problems("5.23.1", run=_latest("v5.23.0"), running=(5, 23, 0)) == []
    assert release.floor_problems("5.23.1", run=_latest("v5.23.1"), running=(5, 23, 1)) == []  # the same, again
    said = release.floor_problems("5.0.0", run=_latest("v5.23.0"), running=(5, 23, 1))
    assert any("older than the running runtime (5.23.1)" in p for p in said), said
    assert any("older than GitHub's latest release (v5.23.0)" in p for p in said), said
    said = release.floor_problems("5.23.1", run=_latest("", 1), running=(5, 23, 0))
    assert any("cannot read GitHub's latest release" in p for p in said), said  # unread is refused


def test_preflight_and_the_install_preflight_hold_to_the_floor(tmp_path):
    repo = checkout(tmp_path / "s")
    floor = lambda version: [f"v{version} is older than the running runtime (5.23.1); nothing older installs"]  # noqa: E731
    assert any("older than the running runtime" in p for p in check(repo, floor=floor)[1])
    version, sha, problems = release.install_preflight("v5.0.0", ci=green, github=served("a" * 40, "b" * 40), floor=floor)
    assert (version, sha) == ("5.0.0", "b" * 40) and any("older than the running runtime" in p for p in problems)
    _, _, problems = release.install_preflight("v5.0.0", ci=green, github=served("a" * 40, ""), floor=no_floor)
    assert any("serves no v5.0.0" in p for p in problems), problems


def test_install_refuses_a_runtime_older_than_the_one_running(tmp_path):
    newer, older = checkout(tmp_path / "newer", "5.23.1", True), checkout(tmp_path / "older", "5.0.0", True)
    install.install(newer)
    before = os.path.realpath(paths.home() / "current")
    with pytest.raises(install.Unapproved, match="downgrade"):  # a rollback needs the principal's code on every route
        install.install(older)
    assert os.path.realpath(paths.home() / "current") == before


# --- A3: the runtime's staged copy is checked against the tag's listing before `current` moves --------------------------

def test_a_staged_runtime_that_differs_from_the_listing_never_becomes_current(tmp_path):
    source = checkout(tmp_path / "s", "5.23.1", True)
    git(source, "tag", "v5.23.1")
    listing = release.runtime_listing(source, "v5.23.1")
    assert "synthesis/guards.py" in listing and all(not p.startswith("skills/demo/") for p in listing)
    with open(source / "synthesis" / "guards.py", "ab") as handle:  # changed after the listing was read
        handle.write(b"\n# written after the listing was read\n")
    with pytest.raises(install.Refused, match="guards.py"):
        install.install(source, expected=listing)
    assert not (paths.home() / "current").exists() and not [
        p for p in (paths.home() / "releases").glob("*") if p.name != ".install.lock"]  # install's own lock stays
    git(source, "checkout", "--", "synthesis/guards.py")
    assert "synthesis runtime" in install.install(source, expected=listing)


def test_a16_the_listing_and_the_install_take_the_skills_the_tag_declares(tmp_path):
    """A16: the release lists, and the running installer stages, the skills the tag's own install.py declares, so a tag
    that carries one skill more than the running runtime installs it."""
    assert "synthesis-carried-later" not in install.STABLE_SKILL_SCRIPTS
    source = checkout(tmp_path / "s", "5.23.1", True, carry="synthesis-carried-later")
    git(source, "tag", "v5.23.1")
    listing = release.runtime_listing(source, "v5.23.1")
    assert "skills/synthesis-carried-later/scripts/later.py" in listing
    assert not [p for p in listing if "/tests/" in p]
    assert "synthesis runtime" in install.install(source, expected=listing)
    current = Path(os.path.realpath(paths.home() / "current"))
    assert (current / "skills" / "synthesis-carried-later" / "scripts" / "later.py").is_file()


def test_a16_a_tag_whose_declaration_cannot_be_read_lists_nothing(tmp_path):
    source = checkout(tmp_path / "s", "5.23.1", True)
    (source / "synthesis" / "install.py").write_text("STABLE_SKILL_SCRIPTS = tuple()\n")
    git(source, "commit", "-qam", "a declaration made at run time")
    git(source, "tag", "v5.23.1")
    with pytest.raises(install.Refused, match="STABLE_SKILL_SCRIPTS"):
        release.runtime_listing(source, "v5.23.1")


# --- A2 and A3 by construction: what is pushed and installed comes from a fresh clone of what GitHub serves --------------

def _github(tmp_path, repo):
    """A bare repository standing in for GitHub, holding what the checkout's main holds."""
    bare = tmp_path / "github.git"
    subprocess.run(["git", "clone", "-q", "--bare", "--no-local", str(repo), str(bare)], check=True)  # its own objects
    return bare


def _forge(repo, oid, body: bytes):
    """Write an object under another object's id, as an agent could: git trusts the name it is filed under."""
    loose = repo / ".git" / "objects" / oid[:2] / oid[2:]
    loose.chmod(0o644)
    loose.write_bytes(zlib.compress(b"blob %d\0" % len(body) + body))


def test_a_release_builds_pushes_and_installs_from_a_fresh_clone_never_the_checkouts_objects(tmp_path, monkeypatch):
    repo = checkout(tmp_path / "work" / "synthesis-skills", "5.23.1", True)
    bare = _github(tmp_path, repo)
    monkeypatch.setattr(release, "CANONICAL_URL", str(bare))
    monkeypatch.setattr(install, "RELEASE_URL", str(bare))  # the install asks it which commit the tag names (C8)
    monkeypatch.setattr(release, "ci_state", green)
    monkeypatch.setattr(release, "floor_problems", no_floor)
    _forge(repo, git(repo, "rev-parse", "HEAD:skills/demo/SKILL.md"), b"What no CI saw.\n")  # the checkout's own store
    _forge(repo, git(repo, "rev-parse", "HEAD:synthesis/guards.py"), b"# a guard no CI saw\n")
    monkeypatch.setattr(release.doctor, "run_checks", lambda: [])  # the doctor's own checks are tested where it lives
    install.grant_release("5.23.1", "the launcher's line")  # what the hook writes when it lets that line through (K1)
    installed = []
    real = install.install
    monkeypatch.setattr(install, "install", lambda root, **k: installed.append((Path(root), k)) or real(root, **k))
    assert release.main(["--repo-root", str(repo), "--session", "S-1", "--clients", ""]) == 1  # no harness: incomplete
    built = git(bare, "ls-tree", "-r", "collections")
    texts = [git(bare, "cat-file", "blob", line.split()[2]) for line in built.splitlines() if line.endswith("SKILL.md")]
    assert texts and all("What CI passed." in text for text in texts), texts
    assert git(bare, "rev-parse", "v5.23.1^{commit}") == git(bare, "rev-parse", "main")
    root, given = installed[-1]
    assert root.parent == paths.home() / "releases" and root.name.startswith(".clone-") and given.get("expected")
    current = Path(os.path.realpath(paths.home() / "current"))
    assert (current / "synthesis" / "guards.py").read_bytes() == (ROOT / "synthesis" / "guards.py").read_bytes()
    assert not list((paths.home() / "releases").glob(".clone-*"))  # the clone is gone when the run ends


def test_an_install_only_is_of_a_tag_on_githubs_main_from_a_fresh_clone(tmp_path, monkeypatch):
    repo = checkout(tmp_path / "work" / "synthesis-skills", "5.23.1", True)
    git(repo, "tag", "-a", "v5.23.1", "-m", "Release v5.23.1")
    git(repo, "checkout", "-qb", "unmerged")
    (repo / "CHANGELOG.md").write_text("# Changelog\n\n## [5.23.2] - 2026-11-15\n\n- never merged\n")
    git(repo, "commit", "-qam", "unmerged")
    git(repo, "tag", "-a", "v5.23.2", "-m", "Release v5.23.2")  # a tag pushed to GitHub, never merged to main
    git(repo, "checkout", "-q", "main")
    bare = _github(tmp_path, repo)
    subprocess.run(["git", "-C", str(repo), "push", "-q", str(bare), "v5.23.2"], check=True)
    monkeypatch.setattr(release, "CANONICAL_URL", str(bare))
    monkeypatch.setattr(release, "ci_state", green)
    monkeypatch.setattr(release, "floor_problems", no_floor)
    assert release.main(["--install-only", "--tag", "v5.23.2", "--clients", ""]) == 1
    assert not (paths.home() / "current").exists()  # not on main: nothing installed
    assert release.main(["--install-only", "--tag", "v5.23.1", "--clients", ""]) == 1  # no harness: incomplete
    assert install.version(paths.home() / "current") == (5, 23, 1)


# --- run from the runtime: the repository only from --repo-root, the code only from the runtime ------------------------

DRIVER = r"""
import json, os, runpy, sys
script = sys.argv[1]
sys.argv = [script] + sys.argv[2:]
sys.path[0] = os.path.dirname(os.path.realpath(script))  # as Python sets it for `python3 <script>`
code = 0
try:
    runpy.run_path(script, run_name="__main__")
except SystemExit as exc:
    code = exc.code
names = ("setup", "build_collections", "build_directory_package", "synthesis", "synthesis.board", "synthesis.guards")
print("\nLOADED " + json.dumps({"code": code, "files": {n: getattr(sys.modules.get(n), "__file__", None) for n in names}}),
      file=sys.stderr)
"""


def _fake_bin(tmp_path, head, bare):
    """gh and git as a release on the network would find them: GitHub (a bare repository here) serves `head` as main's
    tip, CI passed for it, its latest release is older. Everything else git is asked runs the real git."""
    bin_dir, log = tmp_path / "bin", tmp_path / "network.log"
    bin_dir.mkdir()
    real = shutil.which("git")
    (bin_dir / "git").write_text(
        "#!/bin/sh\ncase \" $* \" in\n  *\" ls-remote --tags \"*)\n"
        f"    echo \"git $*\" >> {log}\n    printf '{head}\\trefs/tags/v5.0.0\\n'\n    exit 0;;\n"
        "  *\" ls-remote \"*)\n"
        f"    echo \"git $*\" >> {log}\n"
        f"    printf 'ref: refs/heads/main\\tHEAD\\n{head}\\tHEAD\\n{head}\\trefs/heads/main\\n'\n    exit 0;;\n"
        f"  *\" clone \"*)\n    echo \"git $*\" >> {log}\n"
        f"    exec {real} clone --quiet --no-checkout {bare} \"$(for a; do :; done; printf %s \"$a\")\";;\nesac\n"
        f"exec {real} \"$@\"\n")
    (bin_dir / "gh").write_text(
        f"#!/bin/sh\necho \"gh $*\" >> {log}\n"
        "echo '[{\"status\": \"completed\", \"conclusion\": \"success\", \"workflowName\": \"ci\"}]'\n")
    for name in ("git", "gh"):
        (bin_dir / name).chmod(0o755)
    return bin_dir, log


def test_a_dry_run_from_the_runtime_reads_the_repository_from_repo_root_and_its_code_from_the_runtime(tmp_path, homes):
    install.install(ROOT)  # the runtime, in this test's own home
    runtime = Path(os.path.realpath(paths.home() / "current"))
    repo = checkout(tmp_path / "work" / "synthesis-skills", "9.9.9")  # newer than the runtime it runs from
    head = git(repo, "rev-parse", "HEAD")
    bin_dir, log = _fake_bin(tmp_path, head, _github(tmp_path, repo))
    driver = tmp_path / "driver.py"
    driver.write_text(DRIVER)
    env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}/usr/bin{os.pathsep}/bin"}
    ran = subprocess.run([sys.executable, str(driver), str(paths.home() / "current" / TOOL), "--repo-root", str(repo),
                          "--dry-run", "--session", "S-dry", "--clients", "claude"], capture_output=True, text=True,
                         timeout=300, env=env, cwd=str(tmp_path))
    loaded = json.loads(ran.stderr.rsplit("LOADED ", 1)[1])
    assert loaded["code"] == 0, ran.stdout + ran.stderr
    for name, file in loaded["files"].items():
        assert file and Path(os.path.realpath(file)).is_relative_to(runtime), (name, file)
    assert f"would tag v9.9.9 at {head[:12]}" in ran.stdout and "to origin" in ran.stdout, ran.stdout
    assert "claude: not on this Mac; skipped" in ran.stdout and "release complete: v9.9.9" in ran.stdout
    network = log.read_text()
    assert "ls-remote" in network and "clone" in network and "-R github.com/synthesisengineering/synthesis-skills" in network
    assert not (repo / ".git" / "refs" / "tags" / "v9.9.9").exists()  # a dry run tags nothing


def test_a_release_names_its_checkout_and_an_install_names_its_tag(tmp_path):
    install.install(ROOT)
    tool = paths.home() / "current" / TOOL
    for argv, said in ((["--dry-run"], "a release names --repo-root"),
                       (["--repo-root", str(tmp_path), "--dry"], "unrecognized arguments: --dry"),
                       (["--install-only"], "--install-only names --tag"),
                       (["--install-only", "--tag", "v5.1.0", "--repo-root", str(tmp_path)], "--install-only names --tag"),
                       (["--install-only", "--tag", "main"], "a tag such as v5.23.1")):
        ran = subprocess.run([sys.executable, str(tool), *argv], capture_output=True, text=True, timeout=120, cwd=str(tmp_path))
        assert ran.returncode == 2 and said in ran.stderr, (argv, ran.stderr)

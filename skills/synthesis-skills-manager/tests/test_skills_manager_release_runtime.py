"""5.23.1: the release tool runs from the protected runtime against the checkout --repo-root names, and publishes only
what passed CI on the default branch of the real repository (the principal, 2026-11-15).

The guard lets the runtime's release tool run with no code on the canonical checkout, so the tool itself must refuse
every way an agent could make it publish or install anything else: another checkout, a fork, another remote, a local
commit not on GitHub's main, a dirty tree, a tag that already exists elsewhere, objects rewritten under the ids GitHub
serves, and a checkout whose own git config runs programs or sends git elsewhere.
"""

import json
import os
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


def checkout(tmp_path, version="5.1.0", name="synthesis-skills"):
    """A checkout of the synthesis-skills repository as a release finds it: committed, on main, origin on GitHub."""
    repo = tmp_path / name
    for manifest in release.MANIFESTS:
        (repo / manifest).parent.mkdir(parents=True, exist_ok=True)
        (repo / manifest).write_text(json.dumps({"name": "synthesis-skills", "version": version}))
    (repo / "skills" / "demo").mkdir(parents=True)
    (repo / "skills" / "demo" / "SKILL.md").write_text("---\nname: demo\nmetadata:\n  category: core\n---\n")
    (repo / build_collections.LIST).parent.mkdir(parents=True)
    (repo / build_collections.LIST).write_text(json.dumps(COLLECTIONS))
    for license_file in build_collections.LICENSES:
        (repo / license_file).write_text(f"{license_file} terms.\n")
    (repo / "CHANGELOG.md").write_text(f"# Changelog\n\n## [{version}] - 2026-11-15\n\n- x\n")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "init")
    git(repo, "remote", "add", "origin", CANONICAL)
    return repo


def github(main="", tags=None, on_main="identical"):
    """GitHub as `git ls-remote` and `gh api` read it: the tip of main, the version tags, where a commit stands."""
    def run(argv, *args, **kwargs):
        if "ls-remote" in argv:
            lines = ["ref: refs/heads/main\tHEAD"] + ([f"{main}\tHEAD", f"{main}\trefs/heads/main"] if main else [])
            lines += [f"{sha}\trefs/tags/{tag}" for tag, sha in (tags or {}).items()]
            return subprocess.CompletedProcess(argv, 0, "\n".join(lines) + "\n", "")
        if argv[:2] == ["gh", "api"]:
            return subprocess.CompletedProcess(argv, 0, on_main + "\n", "")
        raise AssertionError(f"unexpected call {argv}")
    return run


green = lambda repo, sha: (True, "CI passed")  # noqa: E731


def check(repo, install_only=False, **served):
    head = git(repo, "rev-parse", "HEAD")
    served.setdefault("main", head)
    reader = github(**served)
    return release.preflight(repo, install_only, ci=green,
                             published=lambda r, v, h, i: release.published_state(r, v, h, i, run=reader))


def test_a_canonical_checkout_at_the_tip_of_githubs_main_passes(tmp_path):
    assert check(checkout(tmp_path)) == ("5.1.0", [])


# --- each route an agent could take to make the runtime's tool publish what CI did not pass on main -------------------

def test_route_a_different_checkout_is_refused(tmp_path):
    repo = checkout(tmp_path)
    git(repo, "remote", "set-url", "origin", str(tmp_path / "elsewhere.git"))
    version, problems = check(repo)
    assert version is None and "not the canonical checkout" in problems[0] and "elsewhere.git" in problems[0], problems
    inner = repo / "skills"
    assert "not the root of a git checkout" in check(inner, main=git(repo, "rev-parse", "HEAD"))[1][0]


def test_route_a_fork_is_refused(tmp_path):
    repo = checkout(tmp_path)
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
    repo = checkout(tmp_path)
    git(repo, *change)
    version, problems = check(repo)
    assert version is None and "not the canonical checkout" in problems[0], problems


def test_route_a_local_commit_not_on_githubs_main_is_refused(tmp_path):
    repo = checkout(tmp_path)
    merged = git(repo, "rev-parse", "HEAD")
    (repo / "skills" / "demo" / "SKILL.md").write_text("---\nname: demo\nmetadata:\n  category: core\n---\nchanged\n")
    git(repo, "commit", "-qam", "local only")
    _, problems = check(repo, main=merged)
    assert any("is not the tip of synthesisengineering/synthesis-skills main" in p for p in problems), problems


@pytest.mark.parametrize("dirty", ["tracked", "untracked"])
def test_route_a_dirty_tree_is_refused(tmp_path, dirty):
    """release.py's own preflight already refused this; the test shows it still does."""
    repo = checkout(tmp_path)
    (repo / ("CHANGELOG.md" if dirty == "tracked" else "stray.txt")).write_text("changed\n")
    _, problems = check(repo)
    assert "the tree has uncommitted changes" in problems, problems


def test_route_a_tag_that_already_exists_is_refused(tmp_path):
    repo = checkout(tmp_path)
    first = git(repo, "rev-parse", "HEAD")
    git(repo, "tag", "v5.1.0")
    git(repo, "commit", "-q", "--allow-empty", "-m", "next")
    _, problems = check(repo)  # the local tag names another commit: release.py's own preflight refused this already
    assert any("v5.1.0 already tags another commit" in p for p in problems), problems
    git(repo, "tag", "-d", "v5.1.0")
    _, problems = check(repo, tags={"v5.1.0": first})  # GitHub already has the tag at another commit
    assert any("already has v5.1.0 at" in p for p in problems), problems


def test_an_install_is_only_of_a_tag_github_serves_on_its_main(tmp_path):
    repo = checkout(tmp_path)
    head = git(repo, "rev-parse", "HEAD")
    git(repo, "tag", "v5.1.0")
    assert check(repo, True, main="0" * 40, tags={"v5.1.0": head}, on_main="ahead") == ("5.1.0", [])
    _, problems = check(repo, True, main="0" * 40)
    assert any("has no v5.1.0" in p for p in problems), problems  # a tag only this checkout has
    _, problems = check(repo, True, main="0" * 40, tags={"v5.1.0": head}, on_main="diverged")
    assert any("is not on synthesisengineering/synthesis-skills main" in p for p in problems), problems  # pushed, never merged


def _forge(repo, oid, body: bytes):
    """Write an object under another object's id, as an agent could: git trusts the name it is filed under."""
    loose = repo / ".git" / "objects" / oid[:2] / oid[2:]
    loose.chmod(0o644)
    loose.write_bytes(zlib.compress(b"blob %d\0" % len(body) + body))


def test_route_objects_rewritten_under_the_ids_github_serves_are_refused(tmp_path):
    repo = checkout(tmp_path)
    blob = git(repo, "rev-parse", "HEAD:CHANGELOG.md")
    _forge(repo, blob, b"# Changelog\n\n## [5.1.0] - 2026-11-15\n\n- something no CI saw\n")
    _, problems = check(repo)
    assert any("do not match their ids" in p for p in problems), problems


def test_a_replace_ref_does_not_change_what_the_release_reads(tmp_path):
    repo = checkout(tmp_path)
    blob = git(repo, "rev-parse", "HEAD:CHANGELOG.md")
    other = subprocess.run(["git", "-C", str(repo), "hash-object", "-w", "--stdin"], input="no CI saw this\n", text=True,
                           capture_output=True, check=True).stdout.strip()
    git(repo, "replace", blob, other)
    assert git(repo, "cat-file", "-p", blob) == "no CI saw this"  # git itself follows the replace ref
    assert "- x" in release.git(repo, "cat-file", "-p", blob).stdout  # the release reads the object itself
    assert check(repo) == ("5.1.0", [])


@pytest.mark.parametrize("key", ["core.fsmonitor", "core.hooksPath", "credential.helper", "http.proxy", "include.path"])
def test_a_checkout_whose_own_config_runs_programs_or_sends_git_elsewhere_is_refused_before_git_runs_them(tmp_path, key):
    repo = checkout(tmp_path)
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


def _fake_bin(tmp_path, head):
    """gh and git as a release on the network would find them: GitHub serves `head` as main's tip and CI passed for it.
    Everything else git is asked runs the real git."""
    bin_dir, log = tmp_path / "bin", tmp_path / "network.log"
    bin_dir.mkdir()
    real = shutil.which("git")
    (bin_dir / "git").write_text(
        "#!/bin/sh\ncase \" $* \" in\n  *\" ls-remote \"*)\n"
        f"    echo \"git $*\" >> {log}\n"
        f"    printf 'ref: refs/heads/main\\tHEAD\\n{head}\\tHEAD\\n{head}\\trefs/heads/main\\n'\n    exit 0;;\nesac\n"
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
    repo = checkout(tmp_path / "work")
    head = git(repo, "rev-parse", "HEAD")
    bin_dir, log = _fake_bin(tmp_path, head)
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
    assert f"would tag v5.1.0 at {head[:12]}" in ran.stdout and "to origin" in ran.stdout, ran.stdout
    assert "would create the GitHub release v5.1.0 on synthesisengineering/synthesis-skills" in ran.stdout
    assert "claude: not on this Mac; skipped" in ran.stdout and "release complete: v5.1.0" in ran.stdout
    network = log.read_text()
    assert "ls-remote" in network and "-R github.com/synthesisengineering/synthesis-skills" in network, network
    assert not (repo / ".git" / "refs" / "tags" / "v5.1.0").exists()  # a dry run tags nothing


def test_the_repository_is_always_named_never_taken_from_the_tools_own_folder(tmp_path):
    install.install(ROOT)
    tool = paths.home() / "current" / TOOL
    for argv, said in ((["--dry-run"], "the following arguments are required: --repo-root"),
                       (["--repo-root", str(tmp_path), "--dry"], "unrecognized arguments: --dry")):
        ran = subprocess.run([sys.executable, str(tool), *argv], capture_output=True, text=True, timeout=120, cwd=str(tmp_path))
        assert ran.returncode == 2 and said in ran.stderr, ran.stderr

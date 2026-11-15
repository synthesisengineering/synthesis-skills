"""Review round 3 of 5.23.1 (releases from the protected runtime): M4.

A clone folder an earlier run left, under the same pid (a crash, then the pid reused within the six hours a young clone
is kept), made `git clone` fail and stopped that release. Each run's clone folder now has a name no earlier run can
have left: its pid and a part drawn at random.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
for path in (ROOT, ROOT / "skills" / "synthesis-onboarding" / "scripts", Path(__file__).resolve().parents[1] / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import release  # noqa: E402
from synthesis import paths  # noqa: E402


@pytest.fixture(autouse=True)
def homes(tmp_path, monkeypatch):
    home = tmp_path / "home"
    for key, value in (("HOME", home), ("SYNTHESIS_HOME", home / ".synthesis" / "v5"), ("GIT_CONFIG_GLOBAL", tmp_path / "gitconfig")):
        monkeypatch.setenv(key, str(value))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    (tmp_path / "gitconfig").write_text("[user]\n\temail = t@example.com\n\tname = t\n[init]\n\tdefaultBranch = main\n")
    home.mkdir()
    return home


def test_m4_a_folder_an_earlier_run_left_under_this_pid_never_stops_the_clone(tmp_path, monkeypatch):
    source = tmp_path / "s"
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    (source / "a.md").write_text("a\n")
    subprocess.run(["git", "-C", str(source), "add", "a.md"], check=True)
    subprocess.run(["git", "-C", str(source), "commit", "-qm", "a"], check=True)
    bare = tmp_path / "github.git"
    subprocess.run(["git", "clone", "-q", "--bare", "--no-local", str(source), str(bare)], check=True)
    monkeypatch.setattr(release, "CANONICAL_URL", str(bare))
    left = paths.home() / "releases" / f".clone-{os.getpid()}"  # what an earlier run under this pid left
    (left / "junk").mkdir(parents=True)
    sha = subprocess.run(["git", "-C", str(source), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    first = release.fresh_clone(sha)
    second = release.fresh_clone(sha)
    assert first != second and re.fullmatch(rf"\.clone-{os.getpid()}-\w+", first.name), (first.name, second.name)
    assert left.is_dir()  # young, and named for a run this one cannot tell from itself: left alone
    for clone in (first, second):
        release.remove_clone(clone)
        assert not clone.exists()

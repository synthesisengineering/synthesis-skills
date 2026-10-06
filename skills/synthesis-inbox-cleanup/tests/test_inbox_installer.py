"""scripts/install.sh: seeds private config without overwriting, refuses unsafe
roots, and reports a missing stable engine path or a stale 1.x engine copy.

Replaces tests/test_runtime_installer.sh, whose engine-release and pointer
cases left with the engine copy (v5 installs the engine at a stable path).
"""

import os
import stat
import subprocess
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[1]
INSTALL = SKILL / "scripts" / "install.sh"
ENGINE_FILES = ("_lib.py", "icloud_plan.py", "icloud_apply.py")


def _run(tmp_path, target, *, engine=True, cwd=None):
    v5 = tmp_path / "v5"
    if engine:
        scripts = v5 / "current" / "skills" / "synthesis-inbox-cleanup" / "scripts"
        scripts.mkdir(parents=True, exist_ok=True)
        for name in ENGINE_FILES:
            (scripts / name).write_text("# stand-in\n")
    env = dict(os.environ, HOME=str(tmp_path / "home"), SYNTHESIS_INBOX_HOME=str(target),
               SYNTHESIS_HOME=str(v5))
    (tmp_path / "home").mkdir(exist_ok=True)
    return subprocess.run(["sh", str(INSTALL)], env=env, cwd=cwd or tmp_path,
                          capture_output=True, text=True, timeout=60)


def _mode(path):
    return stat.S_IMODE(path.stat().st_mode)


def test_seeds_private_config_and_rules_and_never_overwrites(tmp_path):
    target = tmp_path / "inbox"
    first = _run(tmp_path, target)
    assert first.returncode == 0, first.stderr
    assert _mode(target) == 0o700
    for name in ("config.yaml", "rules.yaml"):
        assert _mode(target / name) == 0o600
        assert (target / name).read_text() == (SKILL / "templates" / name.replace(".yaml", ".example.yaml")).read_text()
    (target / "rules.yaml").write_text("edited: true\n")
    second = _run(tmp_path, target)
    assert second.returncode == 0, second.stderr
    assert (target / "rules.yaml").read_text() == "edited: true\n"
    assert "not overwriting" in second.stdout


def test_writes_nothing_outside_its_target(tmp_path):
    before = sorted(p.relative_to(SKILL) for p in SKILL.rglob("*") if "__pycache__" not in p.parts)
    work = tmp_path / "cwd"
    work.mkdir()
    (work / "sentinel").write_text("x")
    assert _run(tmp_path, tmp_path / "inbox", cwd=work).returncode == 0
    after = sorted(p.relative_to(SKILL) for p in SKILL.rglob("*") if "__pycache__" not in p.parts)
    assert before == after
    assert [p.name for p in work.iterdir()] == ["sentinel"]


@pytest.mark.parametrize("kind", ["symlink", "file", "home"])
def test_refuses_unsafe_roots(tmp_path, kind):
    if kind == "symlink":
        real = tmp_path / "real"
        real.mkdir()
        (real / "preserved").write_text("x")
        target = tmp_path / "link"
        target.symlink_to(real)
    elif kind == "file":
        target = tmp_path / "plain-file"
        target.write_text("x")
    else:
        target = tmp_path / "home"
    result = _run(tmp_path, target)
    assert result.returncode == 1
    assert "refusing" in result.stderr
    if kind == "symlink":
        assert sorted(p.name for p in (tmp_path / "real").iterdir()) == ["preserved"]


def test_reports_missing_stable_engine_path(tmp_path):
    result = _run(tmp_path, tmp_path / "inbox", engine=False)
    assert result.returncode == 0
    assert "not at its stable path" in result.stdout


def test_reports_stale_engine_copy_from_1x(tmp_path):
    target = tmp_path / "inbox"
    (target / "engine" / "releases" / "old").mkdir(parents=True)
    result = _run(tmp_path, target)
    assert result.returncode == 0
    assert "engine copy from version 1.x" in result.stdout
    assert (target / "engine" / "releases" / "old").is_dir()  # reported, never removed


def test_quiet_about_the_engine_when_it_is_in_place(tmp_path):
    result = _run(tmp_path, tmp_path / "inbox")
    assert result.returncode == 0
    assert "not at its stable path" not in result.stdout

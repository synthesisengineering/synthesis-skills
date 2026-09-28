"""Execute the direct-copy checksum boundary in disposable source/target roots."""

from pathlib import Path
import os
import subprocess
import sys

import pytest


DIRECT_COPY = Path(__file__).with_name("direct_copy.sh")


@pytest.mark.parametrize("changed_copy", ["source", "installed"])
def test_direct_copy_ignores_generated_bytecode_but_detects_python_source_drift(
    tmp_path, changed_copy
):
    source = tmp_path / "source"
    skill = source / "skills/synthesis-bytecode-fixture"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: synthesis-bytecode-fixture\ndescription: Fixture\n---\n# Fixture\n"
    )
    (skill / "fixture.py").write_text("value = 1\n")
    target = tmp_path / "installed"
    installed = target / skill.name
    # Explicit fixture destinations and absent client overrides prevent plugin
    # probes, user configuration, remote acquisition or installed runtime writes.
    environment = {
        "PATH": os.defpath,
        "LC_ALL": "C",
        "TMPDIR": str(tmp_path),
        "XDG_CACHE_HOME": str(tmp_path / "cache"),
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "SYNTHESIS_SKILLS_HOME": str(tmp_path / "home"),
        "SYNTHESIS_SKILLS_SOURCE_DIR": str(source),
        "SYNTHESIS_SKILLS_TARGETS": str(target),
        "SYNTHESIS_CLAUDE_BIN": "",
        "SYNTHESIS_CODEX_BIN": "",
    }

    def invoke(action):
        return subprocess.run(
            ["sh", str(DIRECT_COPY), action],
            cwd=tmp_path,
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
        )

    installation = invoke("install")
    assert installation.returncode == 0, installation.stdout + installation.stderr
    assert (installed / "fixture.py").read_bytes() == (
        skill / "fixture.py"
    ).read_bytes()
    baseline = invoke("status")
    assert baseline.returncode == 0, baseline.stdout + baseline.stderr

    compiled = subprocess.run(
        [sys.executable, "-I", "-m", "compileall", "-q", str(source), str(target)],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert compiled.returncode == 0, compiled.stdout + compiled.stderr
    assert list(skill.glob("__pycache__/*.pyc"))
    assert list(installed.glob("__pycache__/*.pyc"))
    after_compile = invoke("status")
    assert after_compile.returncode == 0, after_compile.stdout + after_compile.stderr

    changed_root = skill if changed_copy == "source" else installed
    (changed_root / "fixture.py").write_text("value = 2\n")
    drift = invoke("status")
    assert drift.returncode != 0, drift.stdout + drift.stderr
    assert "synthesis-bytecode-fixture" in drift.stdout
    assert "drifted" in drift.stdout.lower()


@pytest.mark.parametrize(
    "selection",
    [
        "synthesis-one",
        "synthesis-missing",
        "",
        "synthesis-one synthesis-one",
        "../outside",
        "synthesis-*/x",
    ],
)
def test_explicit_native_selection_preserves_unselected_and_refuses_invalid(
    tmp_path, selection
):
    source = tmp_path / "source"
    target = tmp_path / "hermes/skills"
    for name in ("synthesis-one", "synthesis-two"):
        d = source / "skills" / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text("# Fixture\n")
    env = {
        "PATH": os.defpath,
        "HOME": str(tmp_path / "home"),
        "SYNTHESIS_SKILLS_HOME": str(tmp_path / "home"),
        "SYNTHESIS_SKILLS_SOURCE_DIR": str(source),
        "SYNTHESIS_SKILLS_TARGETS": str(target),
        "SYNTHESIS_SKILLS_SELECT": selection,
        "SYNTHESIS_CLAUDE_BIN": "",
        "SYNTHESIS_CODEX_BIN": "",
        "XDG_CACHE_HOME": str(tmp_path / "cache"),
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
    }
    result = subprocess.run(
        ["sh", str(DIRECT_COPY), "install"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if selection == "synthesis-one":
        assert result.returncode == 0, result.stdout + result.stderr
        assert (target / "synthesis-one/SKILL.md").read_text() == "# Fixture\n"
        assert not (target / "synthesis-two").exists()
        assert (target / "synthesis-one/.source.json").is_file()
    else:
        assert result.returncode != 0
        assert not target.exists()


def test_selection_wildcard_cannot_expand_into_valid_cwd_name(tmp_path):
    (tmp_path / "synthesis-one").mkdir()
    test_explicit_native_selection_preserves_unselected_and_refuses_invalid(
        tmp_path, "synthesis-*"
    )

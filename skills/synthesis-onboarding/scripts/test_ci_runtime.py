"""CI must establish the real prescribed interpreter before runtime fixtures."""
import os
from pathlib import Path
import subprocess
import yaml
import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / ".github/scripts/install-ci-python.sh"


def test_mac_ci_installs_framework_before_dependencies_and_uses_python3():
    workflow = yaml.safe_load((ROOT / ".github/workflows/validate.yml").read_text())
    steps = workflow["jobs"]["onboarding-portability"]["steps"]
    install = next((i for i, step in enumerate(steps)
                    if step.get("run") == "sh .github/scripts/install-ci-python.sh"), None)
    assert install is not None, "tool-cache Python cannot satisfy the prescribed framework pin"
    assert steps[install]["if"] == "runner.os == 'macOS'"
    dependency = next(i for i, step in enumerate(steps) if "pip install" in step.get("run", ""))
    assert install < dependency
    commands = [step["run"] for step in steps[install + 1:] if "run" in step]
    assert all(not command.startswith("python ") for command in commands)


def test_ci_installer_refuses_local_execution_before_commands(tmp_path):
    env = {**os.environ, "GITHUB_ACTIONS": "false", "RUNNER_OS": "macOS"}
    result = subprocess.run(["sh", str(SCRIPT)], env=env, capture_output=True, text=True)
    assert result.returncode == 2 and "ephemeral macOS CI" in result.stderr


@pytest.mark.parametrize("failure,expected", [
    ("download", ["curl"]),
    ("checksum", ["curl", "shasum"]),
    ("signature", ["curl", "shasum", "pkgutil"]),
    ("publisher", ["curl", "shasum", "pkgutil"]),
    ("installer", ["curl", "shasum", "pkgutil", "sudo"]),
])
def test_ci_package_verification_precedes_installer(tmp_path, failure, expected):
    binaries = tmp_path / "bin"
    binaries.mkdir()
    log = tmp_path / "calls"
    commands = {
        "curl": 'echo curl >> "$CALLS"\n[ "$FAIL_AT" != download ] || exit 31\n',
        "shasum": 'cat >/dev/null\necho shasum >> "$CALLS"\n[ "$FAIL_AT" != checksum ] || exit 32\n',
        "pkgutil": 'echo pkgutil >> "$CALLS"\n[ "$FAIL_AT" != signature ] || exit 33\n[ "$FAIL_AT" != publisher ] || exit 0\necho "Developer ID Installer: Python Software Foundation (BMM5U3QVKW)"\n',
        "sudo": 'echo sudo >> "$CALLS"\nexit 61\n',
    }
    for name, body in commands.items():
        path = binaries / name
        path.write_text("#!/bin/sh\n" + body)
        path.chmod(0o755)
    env = {**os.environ, "PATH": str(binaries) + os.pathsep + os.environ["PATH"],
           "GITHUB_ACTIONS": "true", "RUNNER_OS": "macOS", "RUNNER_TEMP": str(tmp_path),
           "GITHUB_PATH": str(tmp_path / "github-path"), "CALLS": str(log), "FAIL_AT": failure}
    result = subprocess.run(["sh", str(SCRIPT)], env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert log.read_text().splitlines() == expected
    assert not (tmp_path / "github-path").exists()
    if failure == "installer": assert result.returncode == 61


def _base_resolution_region():
    workflow = yaml.safe_load((ROOT / ".github/workflows/validate.yml").read_text())
    steps = workflow["jobs"]["conformance"]["steps"]
    step = next(s for s in steps if s.get("name") == "Resolve acceptance change base")
    script = step["run"]
    begin = script.index("RACE-GUARD-TEST-REGION-BEGIN")
    end = script.index("RACE-GUARD-TEST-REGION-END")
    return script[script.index("\n", begin) + 1:script.rindex("\n", 0, end)]


def _run_base_resolution(region, repo, env_file):
    script = repo / "resolve-base.sh"
    script.write_text("#!/bin/sh\nset -e\n" + region + "\n")
    env = {**os.environ, "GITHUB_ENV": str(env_file)}
    result = subprocess.run(["sh", str(script)], cwd=repo, env=env,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    values = {}
    for line in env_file.read_text().splitlines():
        if line.startswith("SYNTHESIS_ACCEPTANCE_CHANGE_BASE="):
            values["base"] = line.split("=", 1)[1]
    return values


def _git(repo, *args):
    # Fixture commits bypass the ambient commit gate, which governs real
    # checkouts, not temp trees (same precedent as test_pre_commit.py).
    if args[0] == "commit":
        args = ("-c", "core.hooksPath=/dev/null", *args)
    subprocess.run(["git", *args], cwd=repo, check=True)


def _tagged_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.test")
    _git(repo, "config", "user.name", "CI Test")
    (repo / "a.txt").write_text("a\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "release one")
    _git(repo, "tag", "v1.0.0")
    (repo / "b.txt").write_text("b\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "release two")
    _git(repo, "tag", "v2.0.0")
    return repo


def _sha(repo, rev):
    return subprocess.run(["git", "rev-list", "-n", "1", rev], cwd=repo,
                          capture_output=True, text=True, check=True).stdout.strip()


def test_base_resolution_steps_back_when_tag_raced_ci(tmp_path):
    # HEAD is the freshly tagged release commit: the previous release tag
    # is the base, never HEAD itself (else R5 diffs HEAD against HEAD).
    region = _base_resolution_region()
    repo = _tagged_repo(tmp_path)
    values = _run_base_resolution(region, repo, tmp_path / "env")
    assert values["base"] == _sha(repo, "v1.0.0")


def test_base_resolution_uses_tag_when_head_is_untagged(tmp_path):
    # Tag not yet pushed / HEAD ahead of the tag: the tag itself is the base.
    region = _base_resolution_region()
    repo = _tagged_repo(tmp_path)
    (repo / "c.txt").write_text("c\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "post-release")
    values = _run_base_resolution(region, repo, tmp_path / "env")
    assert values["base"] == _sha(repo, "v2.0.0")

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

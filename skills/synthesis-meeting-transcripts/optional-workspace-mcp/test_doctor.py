from __future__ import annotations

import os
import subprocess
from pathlib import Path


DOCTOR = Path(__file__).with_name("doctor.sh")
START = Path(__file__).with_name("start.sh")


def executable(path: Path, body: str) -> None:
    path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    path.chmod(0o755)


def fixture(tmp_path: Path, *, launch: str, lsof_exit: int, curl: str) -> dict[str, str]:
    home = tmp_path / "home"
    unit = home / "Library" / "LaunchAgents" / "com.rajivpant.workspace-mcp.plist"
    unit.parent.mkdir(parents=True)
    unit.write_text("<plist/>\n", encoding="utf-8")
    secret = tmp_path / "client-secret.json"
    secret.write_text("{}\n", encoding="utf-8")
    binaries = tmp_path / "bin"
    binaries.mkdir()
    executable(
        binaries / "plutil",
        f'case "$2" in ProgramArguments.0) printf "%s\\n" "{START}" ;; *) printf "%s\\n" "{secret}" ;; esac\n',
    )
    executable(binaries / "launchctl", launch)
    executable(binaries / "lsof", f"exit {lsof_exit}\n")
    executable(binaries / "curl", curl)
    return {
        **os.environ,
        "HOME": str(home),
        "PATH": f"{binaries}:/usr/bin:/bin:/usr/sbin:/sbin",
        "WORKSPACE_MCP_PORT": "8765",
    }


def run_doctor(environment: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(DOCTOR), "--quiet"],
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


def test_healthy_service_accepts_expected_plain_get_status(tmp_path: Path) -> None:
    environment = fixture(
        tmp_path,
        launch='printf "state = running\\nlast exit code = 0\\n"\n',
        lsof_exit=0,
        curl='printf "406"\n',
    )

    result = run_doctor(environment)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "HEALTHY" in result.stdout


def test_restricted_launchd_and_port_visibility_are_unknown(tmp_path: Path) -> None:
    environment = fixture(
        tmp_path,
        launch='echo "Operation not permitted" >&2\nexit 1\n',
        lsof_exit=1,
        curl='printf "000"\nexit 7\n',
    )

    result = run_doctor(environment)

    assert result.returncode == 2, result.stdout + result.stderr
    assert "UNVERIFIED" in result.stdout
    assert "DEFECTS" not in result.stdout


def test_absent_launchagent_is_a_defect(tmp_path: Path) -> None:
    environment = fixture(
        tmp_path,
        launch='echo "Could not find service" >&2\nexit 1\n',
        lsof_exit=1,
        curl='printf "000"\nexit 7\n',
    )

    result = run_doctor(environment)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "DEFECTS" in result.stdout


def test_curl_failure_never_becomes_double_zero_success(tmp_path: Path) -> None:
    environment = fixture(
        tmp_path,
        launch='printf "state = running\\nlast exit code = 0\\n"\n',
        lsof_exit=0,
        curl='printf "000"\nexit 7\n',
    )

    result = run_doctor(environment)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "DEFECTS" in result.stdout
    assert "000000" not in result.stdout

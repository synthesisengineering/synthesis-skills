from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


DOCTOR = Path(__file__).with_name("doctor.sh")
START = Path(__file__).with_name("start.sh")


def executable(path: Path, body: str) -> None:
    path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    path.chmod(0o755)


def fixture(
    tmp_path: Path,
    *,
    launch: str,
    lsof_exit: int,
    curl: str,
    platform: str = "Darwin",
    systemd_exit: int = 0,
) -> dict[str, str]:
    home = tmp_path / "home"
    config = home / ".config"
    unit = (
        config / "systemd" / "user" / "workspace-mcp.service"
        if platform == "Linux"
        else home / "Library" / "LaunchAgents" / "com.rajivpant.workspace-mcp.plist"
    )
    unit.parent.mkdir(parents=True)
    unit.write_text(
        f"[Service]\nExecStart={START}\n" if platform == "Linux" else "<plist/>\n",
        encoding="utf-8",
    )
    secret = tmp_path / "client-secret.json"
    secret.write_text("{}\n", encoding="utf-8")
    binaries = tmp_path / "bin"
    binaries.mkdir()
    assert platform in {"Darwin", "Linux", "UnsupportedFixtureOS"}
    executable(binaries / "uname", f'printf "%s\\n" "{platform}"\n')
    executable(
        binaries / "plutil",
        f'case "$2" in ProgramArguments.0) printf "%s\\n" "{START}" ;; *) printf "%s\\n" "{secret}" ;; esac\n',
    )
    executable(binaries / "launchctl", launch)
    executable(binaries / "systemctl", f"exit {systemd_exit}\n")
    executable(binaries / "lsof", f"exit {lsof_exit}\n")
    executable(binaries / "curl", curl)
    return {
        # Bash startup files and exported functions can override fake binaries.
        # This synthetic service owns its whole subprocess environment.
        "LC_ALL": "C",
        "LANG": "C",
        "TMPDIR": str(tmp_path),
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(config),
        "GOOGLE_CLIENT_SECRET_PATH": str(secret) if platform == "Linux" else "",
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
        timeout=10,
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


@pytest.mark.parametrize("platform", ["Darwin", "Linux"])
def test_declared_platform_owns_unit_and_secret_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, platform: str
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "unrelated-config"))
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET_PATH", str(tmp_path / "missing-secret"))
    environment = fixture(
        tmp_path,
        launch='printf "state = running\\nlast exit code = 0\\n"\n',
        lsof_exit=0,
        curl='printf "406"\n',
        platform=platform,
    )

    observed = subprocess.run(
        ["uname", "-s"], env=environment, capture_output=True, text=True, timeout=10
    )
    assert observed.returncode == 0
    assert observed.stdout.strip() == platform
    assert environment["XDG_CONFIG_HOME"] == str(tmp_path / "home" / ".config")
    assert environment["GOOGLE_CLIENT_SECRET_PATH"] == (
        str(tmp_path / "client-secret.json") if platform == "Linux" else ""
    )
    result = run_doctor(environment)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "HEALTHY" in result.stdout
    assert "DEFECTS" not in result.stdout


def test_inactive_systemd_service_remains_a_defect(tmp_path: Path) -> None:
    environment = fixture(
        tmp_path,
        launch="exit 99\n",
        lsof_exit=0,
        curl='printf "406"\n',
        platform="Linux",
        systemd_exit=3,
    )
    result = run_doctor(environment)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "DEFECTS: 1 defect(s), 0 unverifiable." in result.stdout


def test_linux_curl_failure_remains_a_defect(tmp_path: Path) -> None:
    environment = fixture(
        tmp_path,
        launch="exit 99\n",
        lsof_exit=0,
        curl='printf "000"\nexit 7\n',
        platform="Linux",
    )
    result = run_doctor(environment)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "DEFECTS: 1 defect(s), 0 unverifiable." in result.stdout
    assert "000000" not in result.stdout


def test_unsupported_platform_remains_unverified(tmp_path: Path) -> None:
    environment = fixture(
        tmp_path,
        launch="exit 99\n",
        lsof_exit=0,
        curl='printf "406"\n',
        platform="UnsupportedFixtureOS",
    )
    result = run_doctor(environment)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "UNVERIFIED" in result.stdout
    assert "HEALTHY" not in result.stdout


@pytest.mark.parametrize("platform", ["Darwin", "Linux"])
def test_inherited_shell_startup_is_not_executed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, platform: str
) -> None:
    startup = tmp_path / "ambient-startup"
    sentinel = tmp_path / "ambient-executed"
    startup.write_text(f'printf contaminated > "{sentinel}"\n', encoding="utf-8")
    monkeypatch.setenv("BASH_ENV", str(startup))
    monkeypatch.setenv("ENV", str(startup))
    environment = fixture(
        tmp_path,
        launch='printf "state = running\\nlast exit code = 0\\n"\n',
        lsof_exit=0,
        curl='printf "406"\n',
        platform=platform,
    )
    result = run_doctor(environment)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "HEALTHY" in result.stdout
    assert not sentinel.exists()
    assert "BASH_ENV" not in environment and "ENV" not in environment


@pytest.mark.parametrize("platform", ["Darwin", "Linux"])
def test_inherited_shell_function_cannot_mask_transport_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, platform: str
) -> None:
    monkeypatch.setenv("BASH_FUNC_curl%%", "() { printf 406; }")
    environment = fixture(
        tmp_path,
        launch='printf "state = running\\nlast exit code = 0\\n"\n',
        lsof_exit=0,
        curl='printf "000"\nexit 7\n',
        platform=platform,
    )
    result = run_doctor(environment)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "DEFECTS" in result.stdout and "HEALTHY" not in result.stdout
    assert "BASH_FUNC_curl%%" not in environment

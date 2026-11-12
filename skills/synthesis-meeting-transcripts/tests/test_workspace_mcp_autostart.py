"""The unit install-autostart.sh writes carries the synthesis home it was installed with, and doctor.sh reports
the outbox that unit gives the server.

start.sh derives the outbox it starts the server to read from SYNTHESIS_HOME. launchd and systemd start a server
with only what the unit carries, so a server installed from a session with another SYNTHESIS_HOME was started to
read the default outbox: `synthesis doctor` failed its outbox line, and no restart could change that.

Nothing is loaded and no server runs. The installer is answered "n", which prints the unit and removes it;
`launchctl` and `systemctl` are stand-ins that record a call; the server is a stand-in `uvx` that records what it
was started with. Off macOS, `plutil` is a stand-in that reads the plist the installer wrote.
"""
from __future__ import annotations

import plistlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "optional-workspace-mcp"
INSTALL, START, DOCTOR = (SCRIPTS / name for name in ("install-autostart.sh", "start.sh", "doctor.sh"))
PLATFORMS = ["Darwin", "Linux"]
AWKWARD = 'plans & drafts <2026>/100% "final" \\ v5'  # what XML and a systemd unit each need escaped
PLUTIL = f"""#!{sys.executable}
import plistlib, sys
keypath, file = sys.argv[2], sys.argv[4]  # plutil -extract <keypath> raw <file>
value = plistlib.load(open(file, "rb"))
try:
    for key in keypath.split("."):
        value = value[int(key)] if isinstance(value, list) else value[key]
except (KeyError, IndexError, ValueError):  # an older macOS printed this on stdout, a newer one on stderr: both exit 1
    print(f"{{file}}: Could not extract value, error: No value at that key path or invalid key path: {{keypath}}")
    sys.exit(1)
print(value)
"""


def executable(path: Path, body: str, shebang: str = "#!/bin/sh\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(shebang + body, encoding="utf-8")
    path.chmod(0o755)


def unit_file(home: Path, platform: str) -> Path:
    return (home / "Library" / "LaunchAgents" / "com.synthesis.workspace-mcp.plist" if platform == "Darwin"
            else home / ".config" / "systemd" / "user" / "workspace-mcp.service")


def written(tmp_path: Path, platform: str, installer: Path = INSTALL, **extra: str) -> str:
    """The unit install-autostart.sh writes as `platform`, from a shell with `extra` set. It is answered "n"."""
    home, binaries, loaded = tmp_path / "home", tmp_path / "bin", tmp_path / "loaded"
    unit_file(home, "Darwin").parent.mkdir(parents=True, exist_ok=True)  # macOS makes launchd's folder; the installer does not
    executable(binaries / "uname", f'printf "%s\\n" "{platform}"\n')
    for loader in ("launchctl", "systemctl"):
        executable(binaries / loader, f'printf "%s %s\\n" "{loader}" "$*" >> "{loaded}"\n')
    secret = tmp_path / "client-secret.json"
    secret.write_text("{}\n", encoding="utf-8")
    environment = {"HOME": str(home), "PATH": f"{binaries}:/usr/bin:/bin", "LANG": "C", "LC_ALL": "C",
                   "XDG_CONFIG_HOME": str(home / ".config"), "GOOGLE_CLIENT_SECRET_PATH": str(secret), **extra}
    result = subprocess.run(["/bin/bash", str(installer)], input="n\n", env=environment, text=True, capture_output=True,
                            check=False, timeout=30)
    assert result.returncode == 0 and result.stdout.endswith("\nCancelled.\n"), result.stdout + result.stderr
    assert not loaded.exists(), loaded.read_text(encoding="utf-8")  # nothing was loaded
    assert not unit_file(home, platform).exists()  # and the unit it printed is gone
    return result.stdout.split("\n\n", 1)[1].rsplit("\n\nCancelled.\n", 1)[0] + "\n"


def unquoted(word: str) -> str:
    """What systemd reads from the inside of a double-quoted word: a backslash gives the character after it, a
    doubled percent sign is one, and `%h` is the home folder. A bare quote would end the word, and any other
    percent sign is a specifier of systemd's own, so neither may stand in a value written to be read back."""
    read, at = [], 0
    while at < len(word):
        pair = word[at:at + 2]
        assert word[at] != '"' and (word[at] != "%" or pair in ("%%", "%h")), f"systemd would not read {word!r} as written"
        read.append(pair[1:] if word[at] == "\\" or pair == "%%" else pair if pair == "%h" else word[at])
        at += 2 if word[at] in "\\%" else 1
    return "".join(read)


def carried(platform: str, unit: str, start: Path = START) -> dict:
    """The environment a unit gives the server: launchd's dictionary, or systemd's Environment= lines."""
    if platform == "Darwin":
        parsed = plistlib.loads(unit.encode("utf-8"))
        assert parsed["ProgramArguments"] == [str(start)]
        return parsed["EnvironmentVariables"]
    assert f"\nExecStart={start}\n" in unit
    lines = [re.fullmatch(r'Environment="(\w+)=(.*)"', line) for line in unit.splitlines()]
    return {m[1]: unquoted(m[2]) for m in lines if m}


def started_with(tmp_path: Path, unit_environment: dict) -> dict:
    """What the server is started with when start.sh runs with what a unit carries, as a supervisor runs it."""
    home, record = tmp_path / "home", tmp_path / "started"
    executable(home / ".local" / "bin" / "uvx", f'env > "{record}"\n')
    environment = {**unit_environment, "HOME": str(home), "PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C",
                   "XDG_STATE_HOME": str(tmp_path / "state")}
    result = subprocess.run(["/bin/bash", str(START)], env=environment, text=True, capture_output=True, check=False, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    return dict(line.split("=", 1) for line in record.read_text(encoding="utf-8").splitlines() if "=" in line)


def doctor(tmp_path: Path, platform: str, unit: str, quiet: bool = True, plutil: str = PLUTIL, **extra: str):
    """doctor.sh as `platform` against this unit, with a service that is loaded and answering: its other checks pass."""
    home, binaries = tmp_path / "home", tmp_path / "doctor-bin"
    target = unit_file(home, platform)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(unit, encoding="utf-8")
    executable(binaries / "uname", f'printf "%s\\n" "{platform}"\n')
    executable(binaries / "launchctl", 'printf "state = running\\nlast exit code = 0\\n"\n')
    executable(binaries / "systemctl", "exit 0\n")
    executable(binaries / "lsof", "exit 0\n")
    executable(binaries / "curl", 'printf "406"\n')
    if plutil:
        executable(binaries / "plutil", plutil.split("\n", 1)[1], plutil.split("\n", 1)[0] + "\n")
    elif (binaries / "plutil").exists():  # the Mac's own is asked for: no stand-in left before it on PATH
        (binaries / "plutil").unlink()
    environment = {"HOME": str(home), "PATH": f"{binaries}:/usr/bin:/bin", "LANG": "C", "LC_ALL": "C", "TMPDIR": str(tmp_path),
                   "XDG_CONFIG_HOME": str(home / ".config"), "WORKSPACE_MCP_PORT": "8765",
                   "GOOGLE_CLIENT_SECRET_PATH": str(tmp_path / "client-secret.json"), **extra}
    return subprocess.run(["/bin/bash", str(DOCTOR)] + (["--quiet"] if quiet else []), env=environment, text=True,
                          capture_output=True, check=False, timeout=30)


# ---- what the unit carries ------------------------------------------------------------------------------------

@pytest.mark.parametrize("platform", PLATFORMS)
def test_the_unit_carries_the_synthesis_home_the_installer_ran_with(platform: str, tmp_path: Path) -> None:
    elsewhere = tmp_path / "elsewhere" / "v5"
    served = carried(platform, written(tmp_path, platform, SYNTHESIS_HOME=str(elsewhere)))
    assert served["SYNTHESIS_HOME"] == str(elsewhere)
    # and what it carried before is as it was
    assert served["GOOGLE_CLIENT_SECRET_PATH"] == str(tmp_path / "client-secret.json")
    assert served["WORKSPACE_MCP_PORT"] == "8765" and served["WORKSPACE_MCP_TOOL_TIER"] == "complete"
    assert served["GOOGLE_MCP_CREDENTIALS_DIR"] == str(tmp_path / "home" / ".google_workspace_mcp" / "credentials")
    assert served["WORKSPACE_MCP_FOREGROUND"] == "1" and ".local/bin" in served["PATH"]
    assert sorted(served) == ["GOOGLE_CLIENT_SECRET_PATH", "GOOGLE_MCP_CREDENTIALS_DIR", "PATH", "SYNTHESIS_HOME",
                              "WORKSPACE_MCP_FOREGROUND", "WORKSPACE_MCP_PORT", "WORKSPACE_MCP_TOOL_TIER"]


@pytest.mark.parametrize("platform", PLATFORMS)
def test_with_no_synthesis_home_at_install_the_unit_names_none(platform: str, tmp_path: Path) -> None:
    """The start script then uses its default, as it did: a unit never fixes a home nobody set."""
    for unset in ({}, {"SYNTHESIS_HOME": ""}):
        assert "SYNTHESIS_HOME" not in carried(platform, written(tmp_path, platform, **unset)), unset


@pytest.mark.parametrize("platform", PLATFORMS)
def test_a_server_started_with_what_the_unit_carries_reads_the_installs_outbox(platform: str, tmp_path: Path) -> None:
    elsewhere = tmp_path / "elsewhere" / "v5"
    served = started_with(tmp_path, carried(platform, written(tmp_path, platform, SYNTHESIS_HOME=str(elsewhere))))
    assert served["ALLOWED_FILE_DIRS"] == str(elsewhere / "outbox") and (elsewhere / "outbox").is_dir()
    served = started_with(tmp_path, carried(platform, written(tmp_path, platform)))
    assert served["ALLOWED_FILE_DIRS"] == str(tmp_path / "home" / ".synthesis" / "v5" / "outbox")


@pytest.mark.parametrize("platform", PLATFORMS)
def test_a_home_whose_name_needs_escaping_reaches_the_server_as_it_is(platform: str, tmp_path: Path) -> None:
    """An ampersand or an angle bracket ends a plist when written as it is; a percent sign, a quote or a backslash
    changes what systemd reads."""
    awkward = tmp_path / AWKWARD
    unit = written(tmp_path, platform, SYNTHESIS_HOME=str(awkward))
    assert carried(platform, unit)["SYNTHESIS_HOME"] == str(awkward)
    assert started_with(tmp_path, carried(platform, unit))["ALLOWED_FILE_DIRS"] == str(awkward / "outbox")
    healthy = doctor(tmp_path, platform, unit, SYNTHESIS_HOME=str(awkward))  # and doctor.sh reads the same home back
    assert healthy.returncode == 0 and "HEALTHY" in healthy.stdout, healthy.stdout + healthy.stderr


@pytest.mark.parametrize("platform", PLATFORMS)
def test_every_path_the_unit_carries_is_written_so_the_supervisor_reads_it_back(platform: str, tmp_path: Path) -> None:
    """The client secret, the credentials folder and the checkout are paths the person chose, written beside the
    synthesis home. A client secret under a folder named with an ampersand gave a plist that did not parse."""
    chosen = tmp_path / 'R&D <keys> 100% "live"'
    chosen.mkdir()
    scripts = Path(shutil.copytree(SCRIPTS, tmp_path / "R&D" / "optional-workspace-mcp"))
    unit = written(tmp_path, platform, scripts / "install-autostart.sh",
                   GOOGLE_CLIENT_SECRET_PATH=str(chosen / "client_secret.json"), GOOGLE_MCP_CREDENTIALS_DIR=str(chosen / "tokens"))
    served = carried(platform, unit, scripts / "start.sh")
    assert served["GOOGLE_CLIENT_SECRET_PATH"] == str(chosen / "client_secret.json")
    assert served["GOOGLE_MCP_CREDENTIALS_DIR"] == str(chosen / "tokens")
    assert "SYNTHESIS_HOME" not in served and served["WORKSPACE_MCP_PORT"] == "8765"


# ---- doctor.sh reports the outbox that unit gives the server -----------------------------------------------------

@pytest.mark.parametrize("platform", PLATFORMS)
def test_the_doctor_reports_the_outbox_the_unit_starts_the_server_to_read(platform: str, tmp_path: Path) -> None:
    elsewhere = tmp_path / "elsewhere" / "v5"
    unit = written(tmp_path, platform, SYNTHESIS_HOME=str(elsewhere))
    started_with(tmp_path, carried(platform, unit))  # the server has started once, so its start script made the folder
    report = doctor(tmp_path, platform, unit, quiet=False, SYNTHESIS_HOME=str(elsewhere))
    assert report.returncode == 0 and "HEALTHY" in report.stdout, report.stdout + report.stderr
    assert f"ok    outbox {elsewhere / 'outbox'}" in report.stdout and "synthesis doctor" in report.stdout


@pytest.mark.parametrize("platform", PLATFORMS)
def test_a_unit_with_another_synthesis_home_than_this_shells_is_a_defect_only_the_installer_repairs(platform: str, tmp_path: Path) -> None:
    """Either way round: the unit names a home and this shell has the default, or the unit names none and this
    shell has one. The server reads one outbox and the sessions here stage in another."""
    elsewhere, default = tmp_path / "elsewhere" / "v5", tmp_path / "home" / ".synthesis" / "v5"
    for unit_home, shell_home in ((elsewhere, default), (default, elsewhere)):
        unit = written(tmp_path, platform, **({"SYNTHESIS_HOME": str(unit_home)} if unit_home != default else {}))
        started_with(tmp_path, carried(platform, unit))
        shell = {"SYNTHESIS_HOME": str(shell_home)} if shell_home != default else {}
        report = doctor(tmp_path, platform, unit, quiet=False, **shell)
        assert report.returncode == 1 and "DEFECTS: 1 defect(s), 0 unverifiable." in report.stdout, report.stdout
        assert str(unit_home / "outbox") in report.stdout and str(shell_home / "outbox") in report.stdout
        # Installing over a loaded unit leaves the supervisor with the one it loaded: it is removed first.
        assert "./uninstall-autostart.sh, then ./install-autostart.sh" in report.stdout and "restart alone" in report.stdout
        assert (SCRIPTS / "uninstall-autostart.sh").is_file()
        same = doctor(tmp_path, platform, unit, **({"SYNTHESIS_HOME": str(unit_home)} if unit_home != default else {}))
        assert same.returncode == 0 and "HEALTHY" in same.stdout, same.stdout + same.stderr


@pytest.mark.parametrize("platform", PLATFORMS)
def test_an_outbox_that_is_not_there_is_a_defect_a_restart_repairs(platform: str, tmp_path: Path) -> None:
    """A server started before its start script made the outbox, or a folder removed since."""
    unit = written(tmp_path, platform)
    outbox = tmp_path / "home" / ".synthesis" / "v5" / "outbox"
    missing = doctor(tmp_path, platform, unit, quiet=False)
    assert missing.returncode == 1 and "DEFECTS: 1 defect(s), 0 unverifiable." in missing.stdout, missing.stdout
    assert f"{outbox} is missing" in missing.stdout and "start.sh makes it" in missing.stdout
    outbox.parent.mkdir(parents=True)
    outbox.write_text("a file where the folder belongs\n", encoding="utf-8")
    blocked = doctor(tmp_path, platform, unit, quiet=False)
    assert blocked.returncode == 1 and f"{outbox} is not a folder" in blocked.stdout, blocked.stdout
    outbox.unlink()
    started_with(tmp_path, carried(platform, unit))
    assert doctor(tmp_path, platform, unit).returncode == 0


@pytest.mark.skipif(shutil.which("plutil") is None, reason="plutil is macOS's own tool")
def test_the_plist_the_installer_writes_is_read_back_by_the_real_plutil(tmp_path: Path) -> None:
    """The stand-in above is not the judge of a plist: on a Mac the doctor's own reader is."""
    awkward = tmp_path / AWKWARD
    for extra, home in (({"SYNTHESIS_HOME": str(awkward)}, awkward), ({}, tmp_path / "home" / ".synthesis" / "v5")):
        unit = written(tmp_path, "Darwin", **extra)
        started_with(tmp_path, carried("Darwin", unit))
        report = doctor(tmp_path, "Darwin", unit, quiet=False, plutil="", **extra)
        assert report.returncode == 0 and f"ok    outbox {home / 'outbox'}" in report.stdout, report.stdout + report.stderr
        lint = subprocess.run(["plutil", "-lint", str(unit_file(tmp_path / "home", "Darwin"))], capture_output=True, text=True)
        assert lint.returncode == 0, lint.stdout


# ---- the documents say the same ---------------------------------------------------------------------------------

@pytest.mark.parametrize("document", ["references/setup.md", "optional-workspace-mcp/README.md"])
def test_the_setup_documents_say_what_the_unit_carries_and_what_the_doctor_reports(document: str) -> None:
    text = " ".join((SCRIPTS.parent / document).read_text(encoding="utf-8").split())  # the documents wrap their lines
    for said in ("`SYNTHESIS_HOME` is among them when it is set at install", "`ALLOWED_FILE_DIRS` is not",
                 "`./doctor.sh` reports the outbox the unit gives the server",
                 "run `./uninstall-autostart.sh` and then `./install-autostart.sh`", "keeps the unit it has loaded"):
        assert said in text, said
    for earlier in ("`./doctor.sh` does not look at it", "`ALLOWED_FILE_DIRS` and `SYNTHESIS_HOME` are not among them"):
        assert earlier not in text, earlier


def test_the_readme_says_what_each_script_does_about_the_outbox() -> None:
    table = (SCRIPTS / "README.md").read_text(encoding="utf-8").split("## What's here", 1)[1].split("\n## ", 1)[0]
    rows = {row.split("|")[1].strip(): row for row in table.splitlines() if row.startswith("| `")}
    assert "synthesis home" in rows["`install-autostart.sh`"] and "outbox" in rows["`doctor.sh`"]

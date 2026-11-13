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
    unit = unit_file(tmp_path / "home", platform)
    before = unit.read_bytes() if unit.exists() else None  # a test may have put a unit there for the doctor to read
    result, home, loaded = installed(tmp_path, platform, installer, **extra)
    assert result.returncode == 0 and result.stdout.endswith("\nCancelled.\n"), result.stdout + result.stderr
    assert not loaded.exists(), loaded.read_text(encoding="utf-8")  # nothing was loaded
    assert (unit.read_bytes() if unit.exists() else None) == before  # a "no" leaves what was installed as it was
    assert not unit.with_name(unit.name + ".new").exists()  # and the unit it printed is gone
    return result.stdout.split("\n\n", 1)[1].rsplit("\n\nCancelled.\n", 1)[0] + "\n"


def installed(tmp_path: Path, platform: str, installer: Path = INSTALL, **extra: str):
    """(install-autostart.sh's run as `platform`, answered "n", the home it ran in, the record a loader writes)."""
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
    return result, home, loaded


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
    word = next(line for line in unit.splitlines() if line.startswith("ExecStart="))[len("ExecStart="):]
    quoted = word.startswith('"') and word.endswith('"')  # a path with a space or one of systemd's signs is quoted
    assert (unquoted(word[1:-1].replace("$$", "$")) if quoted else word) == str(start)
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


# A plist parser reads a carriage return back as a line feed and takes most other control characters for no XML at
# all; a line break in a systemd Environment= value ends its line. The installer wrote such a value as it was, so
# the server was started with another value than the one set, or the unit did not load.
CONTROLLED = [("GOOGLE_CLIENT_SECRET_PATH", "client-secret\rfolder/client_secret.json"), ("SYNTHESIS_HOME", "Review\nHome/v5"),
              ("GOOGLE_MCP_CREDENTIALS_DIR", "creds\tdir"), ("WORKSPACE_MCP_TOOL_TIER", "complete\x1b[0m"),
              ("WORKSPACE_MCP_PORT", "8765\n"), ("HOME", "ho\rme")]


@pytest.mark.parametrize("platform", PLATFORMS)
@pytest.mark.parametrize("name,value", CONTROLLED, ids=[name for name, _ in CONTROLLED])
def test_a_value_holding_a_control_character_is_refused_by_name_before_any_unit_is_written(platform, name, value, tmp_path):
    value = value if name in ("WORKSPACE_MCP_TOOL_TIER", "WORKSPACE_MCP_PORT") else str(tmp_path / value)
    result, home, loaded = installed(tmp_path, platform, **{name: value})
    assert result.returncode == 1 and "Will install" not in result.stdout, result.stdout + result.stderr
    assert f"ERROR: {name} holds a control character" in result.stderr and "run this again" in result.stderr, result.stderr
    assert not re.search(r"[\x00-\x09\x0b-\x1f\x7f]", result.stderr), result.stderr  # the value is shown escaped
    assert not unit_file(home, platform).exists() and not loaded.exists()


@pytest.mark.parametrize("platform", PLATFORMS)
def test_a_checkout_under_a_folder_with_a_line_break_is_refused_naming_its_start_script(platform, tmp_path):
    scripts = Path(shutil.copytree(SCRIPTS, tmp_path / "check\nouts" / "optional-workspace-mcp"))
    result, home, loaded = installed(tmp_path, platform, scripts / "install-autostart.sh")
    assert result.returncode == 1 and "ERROR: this checkout's start.sh holds a control character" in result.stderr, result.stderr
    assert "Will install" not in result.stdout and not unit_file(home, platform).exists() and not loaded.exists()


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
        # The installer replaces a unit that is loaded (it boots the old one out first); a restart would not.
        assert "run ./install-autostart.sh from this shell" in report.stdout and "restart alone" in report.stdout
        assert "replaces the one that is loaded" in report.stdout
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
                 "run `./install-autostart.sh` from that shell", "keeps the unit it has loaded",
                 "replaces the one that is loaded", "it leaves the installed unit as it was"):
        assert said in text, said
    for earlier in ("`./doctor.sh` does not look at it", "`ALLOWED_FILE_DIRS` and `SYNTHESIS_HOME` are not among them",
                    "neither does installing over it"):
        assert earlier not in text, earlier


def test_the_readme_says_what_each_script_does_about_the_outbox() -> None:
    table = (SCRIPTS / "README.md").read_text(encoding="utf-8").split("## What's here", 1)[1].split("\n## ", 1)[0]
    rows = {row.split("|")[1].strip(): row for row in table.splitlines() if row.startswith("| `")}
    assert "synthesis home" in rows["`install-autostart.sh`"] and "outbox" in rows["`doctor.sh`"]


def test_a_checkout_under_a_folder_systemd_or_a_plist_would_misread_is_still_the_one_started(tmp_path: Path) -> None:
    """ExecStart= is a command line: a space splits it, and systemd reads a quote, a backslash, a percent sign and a
    dollar sign as its own. A checkout under such a folder gave a unit that started nothing. It is written in double
    quotes with systemd's escapes, and an ordinary path is written as it was."""
    import shutil
    awkward = tmp_path / "my checkouts & more" / '50% "done" $HOME \\ v2' / "optional-workspace-mcp"
    shutil.copytree(SCRIPTS, awkward)
    start = awkward / "start.sh"
    unit = written(tmp_path, "Linux", installer=awkward / "install-autostart.sh")
    word = next(line for line in unit.splitlines() if line.startswith("ExecStart="))[len("ExecStart="):]
    assert word.startswith('"') and word.endswith('"'), word
    inside = word[1:-1]
    assert "$" not in inside.replace("$$", ""), "a lone dollar sign is a variable to systemd"
    assert unquoted(inside.replace("$$", "$")) == str(start)
    assert plistlib.loads(written(tmp_path, "Darwin", installer=awkward / "install-autostart.sh").encode("utf-8"))["ProgramArguments"] == [str(start)]
    assert f"\nExecStart={START}\n" in written(tmp_path, "Linux")


# ---- run over an installation that is already there -------------------------------------------------------------
# Two defects older than this file's other tests, found on 2026-11-12 while a restart was being planned. Answered
# "n", the installer removed the unit that was installed: it wrote the new one over it before asking. Answered "y"
# over a loaded launch agent, it left launchd on the old definition (`launchctl bootstrap` fails for a label that
# is loaded) and said it had loaded; systemd's `enable --now` leaves a running unit as it is too.

LABEL = "com.synthesis.workspace-mcp"


def answered(tmp_path: Path, platform: str, answer: str, before=None, running: bool = False,
              bootstrap: str = 'touch "$STATE"') -> tuple:
    """Run the installer as `platform` and answer it. `before` is the unit already installed, `running` whether the
    stand-in service manager holds it. Returns the result, the service manager's calls in order, and the unit file."""
    home, binaries, calls, state = tmp_path / "home", tmp_path / "bin", tmp_path / "calls", tmp_path / "running"
    unit = unit_file(home, platform)
    unit_file(home, "Darwin").parent.mkdir(parents=True, exist_ok=True)
    if before is not None:
        unit.parent.mkdir(parents=True, exist_ok=True)
        unit.write_text(before, encoding="utf-8")
    if running:
        state.write_text("", encoding="utf-8")
    executable(binaries / "uname", f'printf "%s\\n" "{platform}"\n')
    executable(binaries / "launchctl", f'STATE="{state}"\nprintf "launchctl %s\\n" "$*" >> "{calls}"\ncase "$1" in\n'
               f'  print) [ -f "$STATE" ] ;;\n  bootout) rm -f "$STATE" ;;\n  bootstrap) {bootstrap} ;;\nesac\n')
    executable(binaries / "systemctl", f'STATE="{state}"\nprintf "systemctl %s\\n" "$*" >> "{calls}"\ncase "$*" in\n'
               f'  *is-active*) [ -f "$STATE" ] ;;\nesac\n')
    secret = tmp_path / "client-secret.json"
    secret.write_text("{}\n", encoding="utf-8")
    environment = {"HOME": str(home), "PATH": f"{binaries}:/usr/bin:/bin", "LANG": "C", "LC_ALL": "C",
                   "XDG_CONFIG_HOME": str(home / ".config"), "GOOGLE_CLIENT_SECRET_PATH": str(secret)}
    result = subprocess.run(["/bin/bash", str(INSTALL)], input=answer + "\n", env=environment, text=True,
                            capture_output=True, check=False, timeout=60)
    said = calls.read_text(encoding="utf-8").splitlines() if calls.exists() else []
    return result, [re.sub(r"gui/\d+", "gui/UID", line) for line in said], unit


@pytest.mark.parametrize("platform", PLATFORMS)
def test_answered_no_over_an_installed_unit_leaves_it_as_it_was(tmp_path, platform):
    before = "the unit installed last month\n"
    result, calls, unit = answered(tmp_path, platform, "n", before=before, running=True)
    assert result.returncode == 0 and result.stdout.endswith("\nCancelled.\n"), result.stdout + result.stderr
    assert unit.read_text(encoding="utf-8") == before  # not replaced, and not removed
    assert sorted(path.name for path in unit.parent.iterdir()) == [unit.name]  # and nothing left beside it
    assert calls == []


@pytest.mark.parametrize("platform", PLATFORMS)
def test_answered_no_with_nothing_installed_leaves_nothing(tmp_path, platform):
    result, calls, unit = answered(tmp_path, platform, "n")
    assert result.returncode == 0 and not unit.exists() and calls == []
    assert not unit.parent.exists() or list(unit.parent.iterdir()) == []


def test_a_loaded_launch_agent_is_replaced_and_the_new_one_is_read_back(tmp_path):
    result, calls, unit = answered(tmp_path, "Darwin", "y", before="the unit installed last month\n", running=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert carried("Darwin", unit.read_text(encoding="utf-8"))["WORKSPACE_MCP_PORT"] == "8765"  # the new unit is in place
    out, loads = f"launchctl bootout gui/UID/{LABEL}", f"launchctl bootstrap gui/UID {unit}"
    assert out in calls and loads in calls and calls.index(out) < calls.index(loads)  # the old one out before the new one in
    assert calls[-1] == f"launchctl print gui/UID/{LABEL}"  # and what launchd holds is read back
    assert "Replaced the launch agent that was loaded" in result.stdout and "legacy" not in result.stdout
    assert sorted(path.name for path in unit.parent.iterdir()) == [unit.name]


def test_a_first_install_loads_the_launch_agent_and_boots_nothing_out(tmp_path):
    result, calls, unit = answered(tmp_path, "Darwin", "y")
    assert result.returncode == 0, result.stdout + result.stderr
    assert not [call for call in calls if " bootout " in call]
    assert f"launchctl bootstrap gui/UID {unit}" in calls and calls[-1] == f"launchctl print gui/UID/{LABEL}"
    assert "Replaced" not in result.stdout


def test_a_launch_agent_that_does_not_load_is_said_and_the_installer_fails(tmp_path):
    result, calls, unit = answered(tmp_path, "Darwin", "y", bootstrap="exit 5")
    assert result.returncode == 1
    assert "is written and is not loaded" in result.stderr and str(unit) in result.stderr
    assert "will now start on login" not in result.stdout


@pytest.mark.parametrize("running", [True, False])
def test_a_running_systemd_unit_is_restarted_so_the_new_unit_is_the_one_that_runs(tmp_path, running):
    result, calls, unit = answered(tmp_path, "Linux", "y", before="the unit installed last month\n" if running else None,
                                    running=running)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ExecStart=" in unit.read_text(encoding="utf-8")
    reload, enable, restart = ("systemctl --user daemon-reload", "systemctl --user enable --now workspace-mcp.service",
                               "systemctl --user restart workspace-mcp.service")
    assert reload in calls and enable in calls and calls.index(reload) < calls.index(enable)
    assert (restart in calls) == running and ("Restarted" in result.stdout) == running
    assert sorted(path.name for path in unit.parent.iterdir()) == [unit.name]

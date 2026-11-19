"""A8 (2026-11-17): `synthesis doctor` checks that every Mac in the ecosystem keeps its files to its own user.

The principal's home folder was found readable by every local user that day (drwxr-xr-x, the macOS default), while a
self-hosted CI runner was being set up under a user of its own. He made it private himself and asked for the check on
every Mac he adds: the doctor runs at each day's start and after every install, so a new Mac's first setup runs it too.
Each problem is a warning that names the one step that fixes it, never a failure: a setting is the person's to change.
"""

import subprocess
from pathlib import Path

from synthesis import doctor


def _mac(off=()):
    """The four macOS answers, each switched off where named."""
    said = {"fdesetup": ("FileVault is On.", "FileVault is Off."),
            "/usr/libexec/ApplicationFirewall/socketfilterfw": ("Firewall is enabled. (State = 1)", "Firewall is disabled. (State = 0)"),
            "csrutil": ("System Integrity Protection status: enabled.", "System Integrity Protection status: disabled."),
            "spctl": ("assessments enabled", "assessments disabled")}
    asked = []

    def run(argv, **kwargs):
        asked.append(argv[0])
        on, no = said[argv[0]]
        return subprocess.CompletedProcess(argv, 0, stdout=(no if argv[0] in off else on) + "\n", stderr="")
    run.asked = asked
    return run


def _home(tmp_path, home_mode=0o700, ssh_mode=0o700, files=None) -> Path:
    home = tmp_path / "account"
    (home / ".ssh").mkdir(parents=True)
    for name, mode in (files or {"id_ed25519": 0o600, "id_ed25519.pub": 0o644, "known_hosts": 0o644}).items():
        (home / ".ssh" / name).write_text("x", encoding="utf-8")
        (home / ".ssh" / name).chmod(mode)
    (home / ".ssh").chmod(ssh_mode)
    home.chmod(home_mode)
    return home


def test_a_mac_that_keeps_its_files_to_its_user_says_so_in_one_line(tmp_path):
    run = _mac()
    checks = doctor.check_security(_home(tmp_path), run=run, platform="darwin")
    assert [(c.status, c.name) for c in checks] == [("ok", "machine security")]
    assert "FileVault" in checks[0].detail and sorted(run.asked) == sorted(
        ["fdesetup", "/usr/libexec/ApplicationFirewall/socketfilterfw", "csrutil", "spctl"])


def test_a_home_folder_other_users_can_open_warns_and_names_the_fix(tmp_path):
    checks = doctor.check_security(_home(tmp_path, home_mode=0o755), run=_mac(), platform="darwin")
    assert [(c.status, c.name) for c in checks] == [("warn", "security home folder")]
    assert "drwxr-xr-x" in checks[0].detail and "chmod 700" in checks[0].detail


def test_ssh_and_its_private_keys_read_by_no_one_else_and_public_files_left_alone(tmp_path):
    files = {"id_ed25519": 0o644, "id_ed25519.pub": 0o644, "known_hosts": 0o644, "config": 0o644, "deploy_key": 0o640}
    checks = doctor.check_security(_home(tmp_path, ssh_mode=0o755, files=files), run=_mac(), platform="darwin")
    assert [(c.status, c.name) for c in checks] == [("warn", "security ~/.ssh")]
    detail = checks[0].detail
    assert ".ssh/id_ed25519 " in detail + " " and "deploy_key" in detail and "chmod 600" in detail
    assert "id_ed25519.pub" not in detail and "known_hosts" not in detail and "config" not in detail


def test_a_mac_with_no_ssh_folder_is_fine(tmp_path):
    home = tmp_path / "account"
    home.mkdir(mode=0o700)
    assert [c.status for c in doctor.check_security(home, run=_mac(), platform="darwin")] == ["ok"]


def test_each_macos_protection_that_is_off_warns_with_the_one_step_that_turns_it_on(tmp_path):
    off = ("fdesetup", "/usr/libexec/ApplicationFirewall/socketfilterfw", "csrutil", "spctl")
    checks = doctor.check_security(_home(tmp_path), run=_mac(off=off), platform="darwin")
    assert [c.name for c in checks] == ["security FileVault", "security firewall", "security System Integrity Protection",
                                        "security Gatekeeper"]
    assert all(c.status == "warn" and "is off" in c.detail and "to fix it" in c.detail for c in checks)
    assert "System Settings" in checks[0].detail and "Recovery" in checks[2].detail


def test_an_answer_that_cannot_be_read_is_unknown_rather_than_passing(tmp_path):
    def run(argv, **kwargs):
        if argv[0] == "spctl":
            raise FileNotFoundError(argv[0])
        return _mac()(argv, **kwargs)
    checks = doctor.check_security(_home(tmp_path), run=run, platform="darwin")
    assert [(c.status, c.name) for c in checks] == [("unknown", "security Gatekeeper")]
    assert "cannot be told" in checks[0].detail


def test_off_macos_only_the_folders_are_checked(tmp_path):
    def run(argv, **kwargs):
        raise AssertionError(f"ran {argv} off macOS")
    checks = doctor.check_security(_home(tmp_path), run=run, platform="linux")
    assert [(c.status, c.name) for c in checks] == [("ok", "machine security")] and "FileVault" not in checks[0].detail


def test_the_doctor_runs_the_check_on_the_account_s_own_home(monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr(doctor, "check_security", lambda home, **kw: seen.append(home) or [])
    from synthesis import paths
    monkeypatch.setattr(paths, "account_home", lambda: tmp_path / "account")
    doctor.run_checks(find=lambda name: None)
    assert seen == [tmp_path / "account"]


# --- The integration review of 5.24.1, finding 2: false warnings. A Finder file in a private ~/.ssh was named as
# readable by other users, as was a list of public keys; a linked ~/.ssh was judged by the link's own mode, which the
# suggested chmod never changes; and Ubuntu's 750 home, whose group is the user's own, warned. ---------------------------

def test_files_in_a_closed_ssh_folder_are_no_one_else_s_to_read(tmp_path):
    files = {".DS_Store": 0o644, "id_ed25519": 0o644, "allowed_signers": 0o644}
    assert [c.status for c in doctor.check_security(_home(tmp_path, files=files), run=_mac(), platform="darwin")] == ["ok"]


def test_an_open_ssh_folder_names_its_private_files_and_no_public_or_finder_one(tmp_path):
    files = {".DS_Store": 0o644, "id_ed25519": 0o644, "allowed_signers": 0o644, "id_ed25519.pub": 0o644}
    checks = doctor.check_security(_home(tmp_path, ssh_mode=0o755, files=files), run=_mac(), platform="darwin")
    assert [c.name for c in checks] == ["security ~/.ssh"] and "id_ed25519 " in checks[0].detail.replace(",", " ")
    assert ".DS_Store" not in checks[0].detail and "allowed_signers" not in checks[0].detail and ".pub" not in checks[0].detail


def test_a_linked_ssh_folder_is_judged_where_it_leads(tmp_path):
    home = tmp_path / "account"
    home.mkdir(mode=0o700)
    keys = tmp_path / "keys"
    keys.mkdir(mode=0o700)
    (home / ".ssh").symlink_to(keys)
    assert [c.status for c in doctor.check_security(home, run=_mac(), platform="darwin")] == ["ok"]


def test_a_group_of_the_user_s_own_lets_no_one_else_in(tmp_path, monkeypatch):
    """Ubuntu gives each user a group of their own and a 750 home; macOS puts every user in the group staff."""
    home = _home(tmp_path, home_mode=0o750)
    monkeypatch.setattr(doctor, "_private_group", lambda gid: True)
    assert [c.status for c in doctor.check_security(home, run=_mac(), platform="linux")] == ["ok"]
    monkeypatch.setattr(doctor, "_private_group", lambda gid: False)
    assert [c.name for c in doctor.check_security(home, run=_mac(), platform="linux")] == ["security home folder"]


# --- The same review: python.org's 3.15 installed writable by the admin group, which this user is in, so the installer
# passed it over and the hooks stayed on 3.12 with nothing said. The doctor says which Python the hooks run, and names a
# newer python.org version the installer had to pass over, with why and the steps that let it be pinned. ----------------

def _python(folder: Path, name: str, says: str) -> str:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text(f"#!/bin/sh\necho '{says}'\n", encoding="utf-8")
    path.chmod(0o755)
    import os
    return os.path.realpath(path)


def _pinned(home: Path, python: str) -> None:
    (home / "bin").mkdir(parents=True, exist_ok=True)
    (home / "bin" / "synthesis-hook").write_text(f'#!/bin/sh\nexec /usr/bin/env -i HOME="$HOME" {python} -I -S /x/hook.py "$@"\n',
                                                 encoding="utf-8")


def test_the_doctor_names_a_newer_python_the_installer_had_to_pass_over_and_how_to_let_it(tmp_path, monkeypatch):
    from synthesis import install
    versions = tmp_path / "Versions"
    old = _python(versions / "3.12" / "bin", "python3", "3 12 final")
    new = _python(versions / "3.15" / "bin", "python3", "3 15 final")
    monkeypatch.setattr(install, "FRAMEWORKS", str(versions / "*" / "bin" / "python3"))
    monkeypatch.setattr(install, "interpreter_problems", lambda p: [f"{p} is writable by this user or its groups"] if p == new else [])
    home = tmp_path / "home"
    _pinned(home, old)
    check = doctor.check_interpreter(home)
    assert check.status == "warn" and check.name == "hook interpreter"
    assert "3.12" in check.detail and "3.15" in check.detail and "writable by this user" in check.detail
    assert f"chmod -R go-w {versions / '3.15'}" in check.detail and "--install-only" in check.detail
    _pinned(home, new)  # the hooks' own Python, once this user can change it, is named and never run (review round 2)
    check = doctor.check_interpreter(home)
    assert check.status == "warn" and "writable by this user" in check.detail and "install again" in check.detail
    monkeypatch.setattr(install, "interpreter_problems", lambda p: [])
    assert doctor.check_interpreter(home).status == "ok"


def test_the_doctor_never_runs_a_python_this_user_can_change(tmp_path, monkeypatch):
    """Review round 2 of 5.24.1: the doctor ran each python.org interpreter to read its version before it asked whether
    this user could rewrite it, so an agent's code planted in a group-writable 3.15 ran at the next day start, outside
    any guarded call. Such a version is now read from its folder's name, and the interpreter is never run."""
    from synthesis import install
    versions = tmp_path / "Versions"
    old = _python(versions / "3.12" / "bin", "python3", "3 12 final")
    marker = tmp_path / "ran"
    (versions / "3.15" / "bin").mkdir(parents=True)
    planted = versions / "3.15" / "bin" / "python3"
    planted.write_text(f"#!/bin/sh\ntouch {marker}\necho '3 15 final'\n", encoding="utf-8")
    planted.chmod(0o755)
    monkeypatch.setattr(install, "FRAMEWORKS", str(versions / "*" / "bin" / "python3"))
    monkeypatch.setattr(install, "interpreter_problems",
                        lambda p: [f"{p} is writable by this user or its groups"] if "3.15" in p else [])
    home = tmp_path / "home"
    _pinned(home, old)
    check = doctor.check_interpreter(home)
    assert check.status == "warn" and "3.15" in check.detail and not marker.exists()


def test_a_folder_above_the_version_s_own_is_named_in_the_fix(tmp_path, monkeypatch):
    """The same review: with the fault in Versions itself, the fix named only the version's folder, and the warning came
    back after it was run."""
    from synthesis import install
    versions = tmp_path / "Versions"
    old = _python(versions / "3.12" / "bin", "python3", "3 12 final")
    _python(versions / "3.15" / "bin", "python3", "3 15 final")
    monkeypatch.setattr(install, "FRAMEWORKS", str(versions / "*" / "bin" / "python3"))
    monkeypatch.setattr(install, "interpreter_problems",
                        lambda p: [f"{versions} is writable by this user or its groups"] if "3.15" in p else [])
    home = tmp_path / "home"
    _pinned(home, old)
    detail = doctor.check_interpreter(home).detail
    assert f"sudo chmod go-w {versions}" in detail and f"sudo chmod -R go-w {versions / '3.15'}" in detail


def test_a_hook_launcher_that_names_no_python_that_answers_warns(tmp_path):
    home = tmp_path / "home"
    _pinned(home, str(tmp_path / "gone" / "python3"))
    check = doctor.check_interpreter(home)
    assert check.status == "warn" and "install again" in check.detail

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
    assert [(c.status, c.name) for c in checks] == [("warn", "security: home folder")]
    assert "drwxr-xr-x" in checks[0].detail and "chmod 700" in checks[0].detail


def test_ssh_and_its_private_keys_read_by_no_one_else_and_public_files_left_alone(tmp_path):
    files = {"id_ed25519": 0o644, "id_ed25519.pub": 0o644, "known_hosts": 0o644, "config": 0o644, "deploy_key": 0o640}
    checks = doctor.check_security(_home(tmp_path, ssh_mode=0o755, files=files), run=_mac(), platform="darwin")
    assert [(c.status, c.name) for c in checks] == [("warn", "security: ~/.ssh")]
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
    assert [c.name for c in checks] == ["security: FileVault", "security: firewall", "security: System Integrity Protection",
                                        "security: Gatekeeper"]
    assert all(c.status == "warn" and "is off" in c.detail and "to fix it" in c.detail for c in checks)
    assert "System Settings" in checks[0].detail and "Recovery" in checks[2].detail


def test_an_answer_that_cannot_be_read_warns_rather_than_passing(tmp_path):
    def run(argv, **kwargs):
        if argv[0] == "spctl":
            raise FileNotFoundError(argv[0])
        return _mac()(argv, **kwargs)
    checks = doctor.check_security(_home(tmp_path), run=run, platform="darwin")
    assert [(c.status, c.name) for c in checks] == [("warn", "security: Gatekeeper")]
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

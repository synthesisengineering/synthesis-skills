"""The guard's sandbox, part 2 (design note 22.9, sections 4.2, 4.3, 4.6 and 4.8; the principal's rulings of 2026-11-15).

What no agent's shell may write is one list (the sealed set, the note's 4.1). From it come the two administrator files
that make each harness's own sandbox hold it: Claude Code's managed settings and Codex's requirements. Setup stages
both in the synthesis home and prints the one command that installs each; the principal installs them with his
password; the doctor reads them back, in one line on every run and in full with `--seal`, which from a session's shell
tries the writes the seal must refuse. Every test here runs with no sandbox present: the files' places are the test's
own folders, never /Library or /etc, and every probe runs in a temporary home.
"""

import errno
import json
import os
import plistlib
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from synthesis import doctor, paths, sandbox

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def mac(tmp_path, monkeypatch):
    """A home laid out as a Mac's, each harness's folder where it is by default, and the administrator files' places in
    the test's own folder."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SYNTHESIS_HOME", str(home / ".synthesis" / "v5"))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(home / ".claude"))
    monkeypatch.setenv("CODEX_HOME", str(home / ".codex"))
    monkeypatch.setenv("XDG_DATA_HOME", str(home / ".local" / "share"))
    monkeypatch.setenv("SYNTHESIS_CLAUDE_DESKTOP_DIR", str(home / "Library" / "Application Support" / "Claude"))
    system = tmp_path / "system"
    monkeypatch.setattr(sandbox, "CLAUDE_MANAGED", system / "ClaudeCode" / "managed-settings.json")
    monkeypatch.setattr(sandbox, "CODEX_REQUIREMENTS", system / "codex" / "requirements.toml")
    monkeypatch.setattr(sandbox, "OUTRANKING", {"claude": system / "mdm" / "com.anthropic.claudecode.plist",
                                                "codex": system / "mdm" / "com.openai.codex.plist"})
    return home


# The design note's 4.2, as written, with the one entry its own 2.1 adds: the desktop app's copies of Claude Code.
DESIGN_DENY = [
    "Edit(~/.synthesis/v5/approvals/**)", "Edit(~/.synthesis/v5/install/**)",
    "Edit(~/.synthesis/v5/releases/**)", "Edit(~/.synthesis/v5/current/**)", "Edit(~/.synthesis/v5/bin/**)",
    "Edit(~/.synthesis/v5/git-hooks/**)", "Edit(~/.synthesis/v5/config.json)", "Edit(~/.synthesis/v5/sessions/**)",
    "Edit(~/.claude/settings.json)", "Edit(~/.claude/settings.local.json)", "Edit(~/.claude/plugins/**)",
    "Edit(~/.codex/sessions/**)", "Edit(~/.codex/archived_sessions/**)", "Edit(~/.codex/config.toml)",
    "Edit(~/.codex/hooks.json)", "Edit(~/.codex/plugins/**)",
    "Edit(~/.local/share/muse/sessions/**)", "Edit(~/.config/muse/**)",
    "Edit(~/Library/LaunchAgents/**)", "Edit(~/.local/share/claude/**)", "Edit(~/.local/bin/**)"]
DESIGN_RULES = {
    "~/.synthesis": "read", "~/.synthesis/v5/board": "write", "~/.synthesis/v5/outbox": "write",
    "~/.synthesis/v5/state/requests": "write", "~/.synthesis/v5/approvals": "read", "~/.claude": "read", "~/.codex": "read",
    "~/.local/share/muse": "read", "~/.config/muse": "read", "~/Library/LaunchAgents": "read",
    "~/Library/Application Support/Claude": "read", "~/.local/share/claude": "read", "~/.local/bin": "read"}


# ---- the two files, from the one sealed set ------------------------------------------------------------------------

def test_claude_codes_managed_settings_are_the_design_notes_file(mac):
    assert sandbox.claude_managed() == {
        "sandbox": {"enabled": True, "failIfUnavailable": True, "allowUnsandboxedCommands": True,
                    "filesystem": {"allowWrite": ["~/workspaces", "~/.Trash"],
                                   "denyWrite": ["~/.claude/projects", "~/Library/Application Support/Claude/local-agent-mode-sessions",
                                                 "~/Library/Application Support/Claude/claude-code"]}},
        "permissions": {"deny": DESIGN_DENY, "ask": ["Bash(dangerouslyDisableSandbox:true)"]}}
    assert json.loads(sandbox.expected("claude")) == sandbox.claude_managed()


def test_every_sealed_folder_of_the_synthesis_home_comes_from_one_list(mac, monkeypatch):
    """Part 1 moves the folders; it changes this list, and both files follow."""
    monkeypatch.setattr(sandbox, "SEALED", sandbox.SEALED + ("ledger",))
    assert "Edit(~/.synthesis/v5/ledger/**)" in sandbox.claude_managed()["permissions"]["deny"]
    assert (paths.home() / "ledger") in [p for p, _, _ in sandbox.sealed()]
    monkeypatch.setattr(sandbox, "APPROVALS", "grants-of-record")
    assert (paths.home() / "grants-of-record", "read") in sandbox.codex_rules()


def test_a_path_outside_the_home_folder_is_written_as_each_setting_reads_one(mac, tmp_path, monkeypatch):
    """Permission rules read `//` as the root and `/` as the settings file's folder; sandbox paths read `/` as the root."""
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "elsewhere"))
    managed = sandbox.claude_managed()
    assert f"Edit(/{tmp_path}/elsewhere/settings.json)" in managed["permissions"]["deny"]
    assert f"{tmp_path}/elsewhere/projects" in managed["sandbox"]["filesystem"]["denyWrite"]


def _toml(text):
    tomllib = pytest.importorskip("tomllib")  # Python 3.11 and later read the whole grammar
    return tomllib.loads(text)


def test_codexs_requirements_pin_a_profile_of_their_own_and_declare_the_guard_as_managed_hooks(mac):
    """Codex 0.169's own words: an array `allowed_permission_profiles` ("the old allowlist") is ignored, and a profile
    requirements.toml defines "conflicts with a config-defined profile of the same name". So the file allows its own
    profile by the table form, and names it apart from the one setup writes into config.toml."""
    found = _toml(sandbox.codex_requirements())
    assert found["default_permissions"] == sandbox.PROFILE != "synthesis"
    assert found["allowed_permission_profiles"] == {sandbox.PROFILE: True, ":read-only": True}
    assert found["allowed_sandbox_modes"] == ["read-only", "workspace-write"]  # no full access, so no bypass flag
    assert found["allow_managed_hooks_only"] is True and found["features"] == {"hooks": True}
    assert found["permissions"] == {sandbox.PROFILE: {"extends": ":workspace", "filesystem": DESIGN_RULES}}
    assert sorted(found["hooks"]) == ["PreToolUse", "SessionStart", "Stop", "UserPromptSubmit"]
    for event, groups in found["hooks"].items():
        assert len(groups) == 1 and all(doctor.calls_stable_hook(event, h["command"]) for h in groups[0]["hooks"]), event
        assert set(groups[0]["hooks"][0]) <= {"type", "command", "timeout", "statusMessage"}  # Claude Code's onFailure is not Codex's
    assert "exit 2" in found["hooks"]["PreToolUse"][0]["hooks"][0]["command"]  # a guard that cannot start holds the call
    assert sandbox.expected("codex") == sandbox.codex_requirements()


def test_the_managed_hooks_are_the_plugins_own_as_codex_reads_them():
    """The runtime carries no hooks.json, so the hooks the requirements declare are written down in the runtime and held
    here to the plugin's: a release that changes one changes both."""
    plugin = doctor.codex_user_declaration(json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8")))
    plain = {event: [{**group, "hooks": [{k: v for k, v in hook.items() if k != "onFailure"} for hook in group["hooks"]]}
                     for group in groups] for event, groups in plugin.items()}
    assert sandbox.managed_hooks() == plain


def test_codexs_profile_rules_are_the_sealed_set_read_only_and_the_three_folders_a_session_writes(mac):
    rules = {sandbox.tilde(p): access for p, access in sandbox.codex_rules()}
    assert rules == DESIGN_RULES
    assert [str(p) for p, a in sandbox.codex_rules() if a == "write"] == [str(paths.home() / w) for w in sandbox.WRITABLE]


# ---- staging and the one command ---------------------------------------------------------------------------------

def test_each_file_installs_with_one_command_that_copies_the_staged_file_as_root(mac):
    for name in ("claude", "codex"):
        words = shlex.split(sandbox.install_command(name))
        target, staged = sandbox.target(name), sandbox.staged(name)
        group = "wheel" if sys.platform == "darwin" else "root"  # root's own group on each system
        assert words == ["sudo", "install", "-d", "-o", "root", "-g", group, "-m", "755", str(target.parent), "&&",
                         "sudo", "install", "-o", "root", "-g", group, "-m", "644", str(staged), str(target)], name
        assert staged.parent == paths.home() / sandbox.STAGED  # sealed: no session changes it before it is installed


def _install(name, text=None):
    there = sandbox.target(name)
    there.parent.mkdir(parents=True, exist_ok=True)
    there.write_text(sandbox.expected(name) if text is None else text, encoding="utf-8")
    return there


def _stage(name):
    copy = sandbox.staged(name)
    copy.parent.mkdir(parents=True, exist_ok=True)
    copy.write_text(sandbox.expected(name), encoding="utf-8")
    return copy


def test_each_file_is_off_then_staged_then_installed_and_holding_the_keys(mac, monkeypatch):
    monkeypatch.setattr(sandbox, "admin_problems", lambda path: [])
    for name in ("claude", "codex"):
        state, problems = sandbox.judge(name)
        assert state == "off" and "setup.py sandbox" in problems[0], name
        copy = _stage(name)
        state, problems = sandbox.judge(name)
        assert state == "staged" and sandbox.install_command(name) in problems[0], name
        copy.write_text("tampered\n")
        state, problems = sandbox.judge(name)
        assert state == "staged" and "out of date" in problems[0] and "setup.py sandbox" in problems[0], name
        there = _install(name)
        assert sandbox.judge(name) == ("installed", []), name
        there.write_text(sandbox.expected(name).replace("true", "false"))
        state, problems = sandbox.judge(name)
        assert state == "installed" and "not what this release stages" in problems[0], name
        assert sandbox.install_command(name) in problems[0]


def test_a_claude_file_that_holds_the_keys_with_other_spacing_still_holds_them(mac, monkeypatch):
    monkeypatch.setattr(sandbox, "admin_problems", lambda path: [])
    _install("claude", json.dumps(sandbox.claude_managed()))  # one line, no indent
    assert sandbox.judge("claude") == ("installed", [])


def test_an_installed_file_this_user_can_change_is_no_seal(mac):
    there = _install("claude")
    state, problems = sandbox.judge("claude")
    assert state == "installed" and any("not owned by root" in p and f"sudo chown root:{sandbox.ROOT_GROUP}" in p for p in problems)
    assert sandbox.admin_problems(Path("/bin/sh").resolve()) == []  # the system's own: root's, and no one else writes it
    assert any("not owned by root" in p for p in sandbox.admin_problems(there))


def test_a_source_that_outranks_the_file_or_merges_over_it_is_named(mac, monkeypatch):
    """Claude Code reads an MDM profile before the file and then ignores the file; it merges managed-settings.d over it.
    Codex reads an MDM profile's requirements above /etc/codex/requirements.toml."""
    monkeypatch.setattr(sandbox, "admin_problems", lambda path: [])
    there = _install("claude")
    _install("codex")
    mdm = sandbox.OUTRANKING["claude"]
    mdm.parent.mkdir(parents=True)
    mdm.write_bytes(plistlib.dumps({"permissions": {"defaultMode": "plan"}}))
    assert any("MDM" in p for p in sandbox.judge("claude")[1])
    mdm.unlink()
    (there.parent / "managed-settings.d").mkdir()
    (there.parent / "managed-settings.d" / "20-other.json").write_text('{"sandbox": {"enabled": false}}')
    assert any("managed-settings.d" in p and "20-other.json" in p for p in sandbox.judge("claude")[1])
    (there.parent / "managed-settings.d" / "20-other.json").write_text('{"model": "opus"}')  # no sandbox or permission key
    assert sandbox.judge("claude") == ("installed", [])
    codex_mdm = sandbox.OUTRANKING["codex"]
    codex_mdm.write_bytes(plistlib.dumps({"config_toml_base64": "eA=="}))  # settings, not requirements
    assert sandbox.judge("codex") == ("installed", [])
    codex_mdm.write_bytes(plistlib.dumps({"requirements_toml_base64": "eA=="}))
    assert any("MDM" in p for p in sandbox.judge("codex")[1])


# ---- the doctor's one line ---------------------------------------------------------------------------------------

def _profile(home, rules=None, extra=""):
    """A config.toml with setup's profile holding these rules (all of the seal's by default)."""
    rules = sandbox.codex_rules() if rules is None else rules
    text = ('default_permissions = "synthesis"\n' + extra + '[permissions.synthesis]\nextends = ":workspace"\n'
            "[permissions.synthesis.filesystem]\n" + "".join(f'{json.dumps(str(p))} = "{a}"\n' for p, a in rules))
    (home / ".codex").mkdir(exist_ok=True)
    (home / ".codex" / "config.toml").write_text(text)


def test_the_doctor_says_off_staged_or_installed_and_holding_the_keys_in_one_line(mac, monkeypatch):
    monkeypatch.setattr(sandbox, "admin_problems", lambda path: [])
    _profile(mac)
    line = doctor.check_sandbox(("claude", "codex"))
    assert (line.status, line.name) == ("warn", "sandbox") and line.detail.startswith("off:")
    assert "setup.py sandbox" in line.detail
    for name in ("claude", "codex"):
        _stage(name)
    line = doctor.check_sandbox(("claude", "codex"))
    assert line.status == "warn" and line.detail.startswith("staged:")
    assert sandbox.install_command("claude") in line.detail and sandbox.install_command("codex") in line.detail
    for name in ("claude", "codex"):
        _install(name)
    line = doctor.check_sandbox(("claude", "codex"))
    assert line == doctor.Check("ok", "sandbox", line.detail) and line.detail.startswith("installed and holding the keys")


def test_each_problem_of_the_line_names_its_one_step(mac, monkeypatch):
    monkeypatch.setattr(sandbox, "admin_problems", lambda path: [f"{path} is not owned by root; to fix it, run `sudo chown root:wheel {path}`"])
    _profile(mac, rules=sandbox.codex_rules()[:3])
    _install("claude")
    _install("codex")
    line = doctor.check_sandbox(("claude", "codex"))
    assert line.status == "warn" and line.detail.startswith("installed, but:")
    assert line.detail.count("sudo chown root:wheel") == 2
    assert "Codex's profile" in line.detail and "setup.py plugin" in line.detail


def test_the_line_judges_only_the_harnesses_on_this_mac(mac, monkeypatch):
    monkeypatch.setattr(sandbox, "admin_problems", lambda path: [])
    _install("claude")
    assert doctor.check_sandbox(("claude", "muse")).status == "ok"
    assert doctor.check_sandbox(("codex",)).detail.startswith("off:")
    assert doctor.check_sandbox(("muse",)).status == "info"


def test_a_codex_that_reads_the_older_sandbox_settings_or_runs_without_one_is_named(mac):
    _profile(mac)
    assert sandbox.profile_problems(doctor.read_toml((mac / ".codex" / "config.toml").read_text())) == []
    _profile(mac, extra='sandbox_mode = "workspace-write"\n')  # Codex then reads [sandbox_workspace_write], which has no read rule
    problems = sandbox.profile_problems(doctor.read_toml((mac / ".codex" / "config.toml").read_text()))
    assert len(problems) == 1 and "sandbox_mode" in problems[0]
    problems = sandbox.profile_problems(doctor.read_toml('default_permissions = ":danger-full-access"\n'))
    assert len(problems) == 1 and "without a sandbox" in problems[0]


def test_the_doctors_trust_line_is_codexs_policy_once_the_requirements_hold(mac, monkeypatch):
    """With the requirements installed, only the hooks they declare run in Codex (allow_managed_hooks_only): the plugin's
    own copies, which Codex asks to approve again after every release, run nowhere, so none waits on the principal."""
    monkeypatch.setattr(sandbox, "admin_problems", lambda path: [])
    assert not sandbox.managed_hooks_hold()
    _install("codex")
    assert sandbox.managed_hooks_hold()
    line = doctor.check_codex_managed_hooks()
    assert (line.status, line.name) == ("ok", "codex hook trust") and not doctor.waits_on_person(line)
    assert str(sandbox.CODEX_REQUIREMENTS) in line.detail


# ---- `synthesis doctor --seal`: the probes ---------------------------------------------------------------------

def sealed_tree(home):
    """The synthesis home and the harnesses' folders as an installed Mac has them, a file in each."""
    v5 = home / ".synthesis" / "v5"
    for folder in ("approvals/grants", "releases/r1/synthesis", "bin", "git-hooks", "sessions", "install", "board", "outbox",
                   "state/requests"):
        (v5 / folder).mkdir(parents=True, exist_ok=True)
    (v5 / "current").symlink_to(v5 / "releases" / "r1")
    (v5 / "approvals" / "grants" / "abc123.json").write_text('{"code": "abc123"}')
    (v5 / "config.json").write_text("{}\n")
    (v5 / "releases" / "r1" / "synthesis" / "hook.py").write_text("# the hook\n")
    hook = v5 / "bin" / "synthesis-hook"
    hook.write_text("#!/bin/sh\nexit 0\n")
    hook.chmod(0o755)
    for folder in (".claude/projects", ".claude/plugins", ".codex/sessions", ".codex/plugins", ".local/share/muse/sessions",
                   "Library/Application Support/Claude/local-agent-mode-sessions", "Library/LaunchAgents", ".local/bin"):
        (home / folder).mkdir(parents=True, exist_ok=True)
    (home / ".claude" / "settings.json").write_text("{}\n")
    (home / ".codex" / "config.toml").write_text("")
    (home / ".codex" / "hooks.json").write_text('{"hooks": {}}\n')
    return v5


def tree(root):
    """Every path under root, with a file's bytes and a link's target: what a probe must leave as it found it."""
    found = {}
    for folder, dirs, names in os.walk(root):
        for name in dirs + names:
            path = Path(folder) / name
            found[str(path.relative_to(root))] = (os.readlink(path) if path.is_symlink() else
                                                  path.read_bytes() if path.is_file() else "folder")
    return found


def no_broker(argv, **kwargs):
    raise AssertionError(f"a test ran {argv}")


def test_with_no_sandbox_every_write_goes_through_is_reported_and_what_it_made_is_removed(mac, tmp_path):
    sealed_tree(mac)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    before, around = tree(mac), tree(workspace)
    found = {name: (outcome, detail) for name, outcome, detail in sandbox.probes(paths.home(), workspace, no_broker, "darwin")}
    assert found["create in approvals"][0] == "wrote"
    for name in ("a shell's write", "a background child's write", "a write through a link", "records claude-code",
                 "records codex", "records muse", "records desktop", "config.json", "install", "releases", "bin", "git-hooks",
                 "current", "sessions", "write ~/.claude/settings.json", "write ~/.claude/settings.local.json",
                 "write ~/.codex/config.toml", "write ~/.codex/hooks.json", "write ~/Library/LaunchAgents", "write ~/.local/bin"):
        assert found[name][0] == "wrote", (name, found[name])
    # Where the first write went through, nothing more is learned by moving the live folders or asking a broker.
    for name in ("rename in approvals", "delete in approvals", "rename the synthesis home", "rename its parent",
                 "the hook with a made-up prompt", "launchctl submit", "open -a"):
        assert found[name][0] == "skipped", (name, found[name])
    assert tree(mac) == before and tree(workspace) == around


def _refused_in(folder, real):
    def create(path, made):
        return ("held", "EPERM") if paths.inside(str(path), str(folder)) else real(path, made)
    return create


def test_where_approvals_refuse_a_write_the_moves_run_and_each_puts_back_what_it_moved(mac, tmp_path, monkeypatch):
    """A seal on the folder alone, with its ancestors open: what the note's ancestor rules are for. Each move that goes
    through is reported and undone at once, so the live folders are where they were."""
    v5 = sealed_tree(mac)
    monkeypatch.setattr(sandbox, "_create", _refused_in(v5 / "approvals", sandbox._create))
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    before = tree(mac)
    found = {name: (outcome, detail) for name, outcome, detail in sandbox.probes(paths.home(), workspace, no_broker, "linux")}
    assert found["create in approvals"] == ("held", "EPERM")
    for name in ("rename in approvals", "rename the synthesis home", "rename its parent"):
        assert found[name][0] == "wrote" and "and back" in found[name][1], (name, found[name])
    assert found["delete in approvals"][0] == "skipped"  # a folder whose entries move is open already; nothing is deleted
    assert found["launchctl submit"][0] == found["open -a"][0] == "skipped"  # brokers are macOS's
    assert tree(mac) == before and tree(workspace) == {}


def test_a_delete_runs_only_where_moves_are_refused_and_what_it_deleted_is_put_back(mac, tmp_path, monkeypatch):
    v5 = sealed_tree(mac)
    monkeypatch.setattr(sandbox, "_create", _refused_in(v5 / "approvals", sandbox._create))
    real_rename = sandbox._rename
    monkeypatch.setattr(sandbox, "_rename", lambda path: ("held", "EPERM") if "approvals" in Path(path).parts else real_rename(path))
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    before = tree(mac)
    found = {name: (outcome, detail) for name, outcome, detail in sandbox.probes(paths.home(), workspace, no_broker, "linux")}
    assert found["delete in approvals"][0] == "wrote" and "put it back" in found["delete in approvals"][1]
    assert tree(mac) == before and tree(workspace) == {}


def test_a_refusal_is_held_only_when_the_system_says_not_permitted(mac, tmp_path, monkeypatch):
    sealed_tree(mac)
    real_open = os.open

    def refusing(path, flags, *args):
        if paths.inside(str(path), str(paths.home() / "approvals")) and flags & (os.O_WRONLY | os.O_RDWR):
            raise PermissionError(errno.EPERM, "Operation not permitted")
        if str(path).endswith(".claude/settings.json") and flags & os.O_WRONLY:
            raise FileNotFoundError(errno.ENOENT, "No such file or directory")
        return real_open(path, flags, *args)
    monkeypatch.setattr(sandbox.os, "open", refusing)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    found = {name: (outcome, detail) for name, outcome, detail in sandbox.probes(paths.home(), workspace, no_broker, "linux")}
    assert found["create in approvals"] == ("held", "EPERM") and found["overwrite in approvals"] == ("held", "EPERM")
    assert found["write ~/.claude/settings.json"] == ("unknown", "ENOENT")


def test_the_hook_run_with_a_made_up_prompt_writes_no_record_or_is_reported(mac, tmp_path, monkeypatch):
    """The M5 route: a shell pipes an invented prompt into the hook. A hook started from a sandboxed shell runs inside
    the sandbox and writes nothing; one that writes the session's record is reported, and the record removed."""
    from synthesis import approvals
    v5 = sealed_tree(mac)
    monkeypatch.setattr(sandbox, "_create", _refused_in(v5 / "approvals", sandbox._create))
    records = approvals._dir("transcripts")
    hook = v5 / "bin" / "synthesis-hook"
    hook.write_text(f"#!{sys.executable}\nimport json, os, sys\npayload = json.load(sys.stdin)\n"
                    f"os.makedirs({str(records)!r}, exist_ok=True)\n"
                    f"open(os.path.join({str(records)!r}, payload['session_id'] + '.json'), 'w').write('{{}}')\n")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    before = tree(mac)
    found = {name: (outcome, detail) for name, outcome, detail in sandbox.probes(paths.home(), workspace, no_broker, "linux")}
    assert found["the hook with a made-up prompt"][0] == "wrote" and sandbox.tilde(records) in found["the hook with a made-up prompt"][1]
    assert tree(mac) == before
    hook.write_text("#!/bin/sh\nexit 1\n")
    found = {name: (outcome, detail) for name, outcome, detail in sandbox.probes(paths.home(), workspace, no_broker, "linux")}
    assert found["the hook with a made-up prompt"][0] == "held"


def test_a_broker_that_runs_the_write_outside_the_sandbox_is_reported_and_its_job_removed(mac, tmp_path, monkeypatch):
    v5 = sealed_tree(mac)
    monkeypatch.setattr(sandbox, "_create", _refused_in(v5 / "approvals", sandbox._create))
    asked = []

    def broker(argv, **kwargs):
        asked.append(argv)
        if argv[:2] == ["launchctl", "submit"]:
            Path(argv[-1]).write_text("")  # launchd ran the job: outside every sandbox
        if argv[0] == "open":
            subprocess.run(["/bin/sh", argv[-1]], check=True)  # Terminal ran the script
        return subprocess.CompletedProcess(argv, 0, "", "")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    before, around = tree(mac), tree(workspace)
    found = {name: (outcome, detail) for name, outcome, detail in sandbox.probes(paths.home(), workspace, broker, "darwin")}
    assert found["launchctl submit"][0] == found["open -a"][0] == "wrote"
    assert any(a[:2] == ["launchctl", "remove"] for a in asked)
    assert tree(mac) == before and tree(workspace) == around

    # What launchd made outside the sandbox, a sandboxed shell may not remove: said, never a crash.
    real_remove = sandbox._remove
    monkeypatch.setattr(sandbox, "_remove", lambda made, until=0: [sandbox.tilde(p) for p in made] if any(
        "launchd" in str(p) or "-open" in str(p) for p in made) else real_remove(made, until))
    found = {name: (outcome, detail) for name, outcome, detail in sandbox.probes(paths.home(), workspace, broker, "darwin")}
    assert found["launchctl submit"][0] == "wrote" and "from your own terminal" in found["launchctl submit"][1]
    monkeypatch.setattr(sandbox, "_remove", real_remove)
    for marker in (v5 / "approvals").glob(".seal-probe-*"):
        marker.unlink()

    def refused(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 1, "", "Operation not permitted")
    found = {name: (outcome, detail) for name, outcome, detail in sandbox.probes(paths.home(), workspace, refused, "darwin")}
    assert found["launchctl submit"][0] == found["open -a"][0] == "held"


@pytest.mark.skipif(sys.platform != "darwin" or not Path("/usr/bin/sandbox-exec").exists(), reason="macOS's Seatbelt")
def test_under_a_real_seatbelt_profile_that_seals_the_set_every_probe_is_held(mac, tmp_path):
    """The probes against the mechanism itself: a Seatbelt profile that denies writes to the sealed set and, as Claude
    Code's does, renames of each ancestor, run on a temporary home. Skipped where a sandbox already holds this run, since
    Seatbelt refuses to start a second."""
    v5 = sealed_tree(mac)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    sealed = [os.path.realpath(p) for p, _, _ in sandbox.sealed()] + [os.path.realpath(v5 / "state" / "transcripts")]
    ancestors = sorted({os.path.realpath(v5)} | {str(Path(os.path.realpath(v5)).parent)})
    profile = ("(version 1)(allow default)(deny file-write* " + " ".join(f'(subpath "{p}")' for p in sealed) + ")"
               "(deny file-write-unlink file-write-create " + " ".join(f'(literal "{p}")' for p in ancestors) + ")")
    probe = (f"import json, sys; sys.path.insert(0, {str(ROOT)!r})\n"
             "from pathlib import Path\nfrom synthesis import paths, sandbox\n"
             f"print(json.dumps(sandbox.probes(paths.home(), Path({str(workspace)!r}), brokers=False)))\n")
    done = subprocess.run(["/usr/bin/sandbox-exec", "-p", profile, sys.executable, "-c", probe], capture_output=True, text=True,
                          timeout=120, env=os.environ.copy())
    if done.returncode and "sandbox_apply" in done.stderr:
        pytest.skip("this run is already inside a sandbox")
    assert done.returncode == 0, done.stderr
    found = {name: (outcome, detail) for name, outcome, detail in json.loads(done.stdout)}
    wrote = {name: v for name, v in found.items() if v[0] == "wrote"}
    assert wrote == {} and found["create in approvals"] == ("held", "EPERM")
    assert found["rename the synthesis home"][0] == found["rename its parent"][0] == "held"
    assert found["a shell's write"][0] == found["a background child's write"][0] == "held"


# ---- `synthesis doctor --seal`: where it runs decides what it does ---------------------------------------------

def test_from_a_sandboxed_shell_the_seal_check_probes_and_outside_one_it_reads_the_configuration(mac, tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(doctor, "find_client", lambda name: None)  # never this Mac's own harnesses
    monkeypatch.setattr(sandbox, "probes", lambda home, workspace, run=None, platform=None, brokers=True:
                        calls.append("probes") or [("create in approvals", "held", "EPERM"), ("open -a", "wrote", "ran")])
    monkeypatch.setattr(sandbox, "config_read", lambda found, run=None: calls.append("read") or [("claude", "ok", "holds")])
    checks = doctor.check_seal(sandboxed=True, session="s1", workspace=tmp_path)
    assert calls == ["probes"] and [(c.status, c.name) for c in checks] == [("ok", "seal create in approvals"), ("fail", "seal open -a")]
    checks = doctor.check_seal(sandboxed=None, session="s1", workspace=tmp_path)  # cannot tell, inside a session: probe
    assert calls[-1] == "probes"
    checks = doctor.check_seal(sandboxed=False, session="", workspace=tmp_path)
    assert calls[-1] == "read" and [(c.status, c.name) for c in checks] == [("ok", "seal claude")]
    checks = doctor.check_seal(sandboxed=False, session="s1", workspace=tmp_path)
    assert calls[-1] == "read" and (checks[0].status, checks[0].name) == ("fail", "seal shell")
    assert "outside any sandbox" in checks[0].detail


def test_doctor_seal_prints_its_lines_and_fails_on_any_write_that_went_through(monkeypatch, capsys):
    monkeypatch.setattr(doctor, "check_seal", lambda: [doctor.Check("ok", "seal create in approvals", "refused (EPERM)")])
    assert doctor.main(["--seal"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("synthesis doctor: healthy") and "seal create in approvals" in out
    monkeypatch.setattr(doctor, "check_seal", lambda: [doctor.Check("fail", "seal rename its parent", "moved and back")])
    assert doctor.main(["--seal", "--json"]) == 1
    assert json.loads(capsys.readouterr().out)["checks"][0]["name"] == "seal rename its parent"


def test_this_process_is_known_to_be_sandboxed_or_not_where_the_system_says(tmp_path):
    assert sandbox.in_sandbox() in (True, False, None)
    if sys.platform == "darwin" and Path("/usr/bin/sandbox-exec").exists() and sandbox.in_sandbox() is False:
        done = subprocess.run(["/usr/bin/sandbox-exec", "-p", "(version 1)(allow default)", sys.executable, "-c",
                               f"import sys; sys.path.insert(0, {str(ROOT)!r}); from synthesis import sandbox; print(sandbox.in_sandbox())"],
                              capture_output=True, text=True, timeout=60)
        assert done.stdout.strip() == "True", done.stderr


# ---- `synthesis doctor --seal` outside a sandbox: the configuration read ---------------------------------------

def test_the_configuration_read_says_each_file_codexs_profile_and_muse(mac, monkeypatch):
    monkeypatch.setattr(sandbox, "admin_problems", lambda path: [])
    _profile(mac)
    found = {name: (status, detail) for name, status, detail in sandbox.config_read(("claude", "codex", "muse"))}
    assert found["claude"][0] == found["codex"][0] == "fail"
    assert "setup.py sandbox" in found["claude"][1]
    _install("claude")
    _install("codex")
    found = {name: (status, detail) for name, status, detail in sandbox.config_read(("claude", "codex", "muse"))}
    assert found["claude"][0] == found["codex"][0] == "ok"
    assert found["muse"][0] == "info" and "no approval" in found["muse"][1]
    assert found["commands"][0] == "ok" and found["hooks path"][0] == "ok"


def test_a_command_run_outside_the_sandbox_from_the_write_area_fails_the_read(mac, monkeypatch):
    """The note's 4.7, item 9: a hook, an MCP server or a launch agent runs with full access, so a file it runs from where
    a session writes is a forgery left for later."""
    monkeypatch.setattr(sandbox, "admin_problems", lambda path: [])
    work = mac / "workspaces" / "tool"
    work.mkdir(parents=True)
    (mac / "Library" / "LaunchAgents").mkdir(parents=True)
    (mac / "Library" / "LaunchAgents" / "com.example.agent.plist").write_bytes(plistlib.dumps(
        {"Label": "com.example.agent", "ProgramArguments": ["/bin/sh", "-c", f"exec {work}/run.sh"]}))
    (mac / "Library" / "LaunchAgents" / "com.example.fine.plist").write_bytes(plistlib.dumps(
        {"Label": "com.example.fine", "ProgramArguments": ["/usr/bin/true"]}))
    (mac / ".claude").mkdir()
    (mac / ".claude" / "settings.json").write_text(json.dumps({"hooks": {"PreToolUse": [{"hooks": [
        {"type": "command", "command": f"$HOME/{work.relative_to(mac)}/hook.sh"}]}]}}))
    (mac / ".claude.json").write_text(json.dumps({"mcpServers": {"tool": {"command": "node", "args": [f"{work}/server.js"]}}}))
    (mac / ".codex").mkdir()
    (mac / ".codex" / "config.toml").write_text('[mcp_servers.fine]\ncommand = "/usr/bin/true"\n'
                                                f'[mcp_servers.tool]\ncommand = "{work}/codex-server"\n')
    found = {name: (status, detail) for name, status, detail in sandbox.config_read(("claude", "codex"))}
    status, detail = found["commands"]
    assert status == "fail"
    for named in ("com.example.agent.plist", "settings.json PreToolUse", ".claude.json mcpServers.tool", "config.toml mcp_servers.tool"):
        assert named in detail, named
    assert "com.example.fine" not in detail and "mcp_servers.fine" not in detail


def test_a_repository_that_runs_hooks_of_its_own_fails_the_read(mac, monkeypatch):
    monkeypatch.setattr(sandbox, "admin_problems", lambda path: [])
    repo = mac / "workspaces" / "space" / "repo"
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    assert dict((n, s) for n, s, _ in sandbox.config_read(("claude",)))["hooks path"] == "ok"
    subprocess.run(["git", "-C", str(repo), "config", "core.hooksPath", str(repo / "my-hooks")], check=True)
    status, detail = {n: (s, d) for n, s, d in sandbox.config_read(("claude",))}["hooks path"]
    assert status == "fail" and sandbox.tilde(repo) in detail and "core.hooksPath" in detail

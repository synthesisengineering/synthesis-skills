"""Exercise the public updater, runtime transaction, and real installed doctor.

Network acquisition and client plugin operations are the only fake boundaries
in the successful update. Runtime planning, ownership proof, filesystem writes,
engine receipt loading, transaction journals and the protective doctor execute
their production paths against an isolated home and two real Git releases.
"""

import copy
import hashlib
import json
import os
import plistlib
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import onboard
import runtime_payload
import synthesis_cli
from enrollment import EnrollmentJournal
from system_contract import SystemState, default_desired_state, release_descriptor_from_checkout


ROOT = Path(__file__).resolve().parents[3]
GIT_PAYLOADS = {
    **{"skills/synthesis-git-hooks/scripts/" + name: (".synthesis/git-hooks/" + name, 0o755)
       for name in ("pre-commit", "commit-msg", "_load_config.py")},
    **{"skills/synthesis-project-management/scripts/" + name: (".synthesis/git-hooks/" + name, 0o755)
       for name in ("coordination.py", "coordination_schema.py", "pointer_lock.py", "peer_addressing.py")},
    "skills/synthesis-project-management/references/session-words-v1.txt.zlib.b85":
        (".synthesis/references/session-words-v1.txt.zlib.b85", 0o644),
}
STALE_RELATIVE = "skills/synthesis-project-management/scripts/peer_addressing.py"
MESSAGE_RELATIVE = "skills/synthesis-message-guard/scripts/message_guard.py"


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


def write(path, content, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content if isinstance(content, bytes) else content.encode())
    path.chmod(mode)


def release(root, version):
    root.mkdir()
    git(root, "init", "-q")
    git(root, "config", "user.name", "Fixture")
    git(root, "config", "user.email", "fixture@example.invalid")
    for relative in GIT_PAYLOADS:
        content = (ROOT / relative).read_bytes()
        if relative == STALE_RELATIVE:
            content += ("\n# Immutable integration release " + version + "\n").encode()
        write(root / relative, content)
    for relative in (
        "skills/synthesis-onboarding/references/layers.json",
        "skills/synthesis-context-lifecycle/scripts/context_doctor.py",
        "skills/synthesis-agent-conformance/scripts/conformance.py",
        MESSAGE_RELATIVE,
        "skills/synthesis-onboarding/scripts/kernel_sync.py",
        "skills/synthesis-onboarding/scripts/whole_system.py",
        "skills/synthesis-daily-rituals/scripts/day-end",
        "skills/synthesis-daily-rituals/scripts/day-end-nudge.sh",
    ):
        content = (ROOT / relative).read_bytes()
        if relative == MESSAGE_RELATIVE:
            content += ("\n# Immutable integration release " + version + "\n").encode()
        write(root / relative, content)
    for client in ("claude", "codex"):
        write(root / ("." + client + "-plugin/plugin.json"),
              json.dumps({"name": "synthesis-skills", "version": version}))
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "Fixture")
    git(root, "tag", "v" + version)
    return release_descriptor_from_checkout(root, "pin", "v" + version,
                                            "https://example.invalid/public/skills.git")


@pytest.fixture
def machine(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    for key in list(os.environ):
        if key.startswith(("SYNTHESIS_", "MESSAGE_GUARD_", "GIT_", "XDG_")):
            monkeypatch.delenv(key)
    for key, value in {
        "HOME": home, "SYNTHESIS_HOME": home, "SYNTHESIS_ONBOARD_HOME": home,
        "XDG_CONFIG_HOME": home / ".config", "XDG_STATE_HOME": home / ".local/state",
        "XDG_CACHE_HOME": home / ".cache", "GIT_CONFIG_GLOBAL": home / ".gitconfig",
        "GIT_CONFIG_NOSYSTEM": "1", "PYTHONDONTWRITEBYTECODE": "1",
    }.items():
        monkeypatch.setenv(key, str(value))
    state = SystemState(home)
    old = tmp_path / "old"
    old_descriptor = release(old, "1.0.0")
    current = tmp_path / "current"
    current_descriptor = release(current, "1.0.1")
    historical = state.cache_dir / "releases" / old_descriptor["content_digest"]
    historical.parent.mkdir(parents=True)
    shutil.copytree(old, historical, ignore=shutil.ignore_patterns(".git"))
    write(state.state_dir / "releases/1.0.0.json", json.dumps(old_descriptor))
    for relative, (target, mode) in GIT_PAYLOADS.items():
        write(home / target, (old / relative).read_bytes(), mode)
    write(home / ".synthesis/git-hooks/source-path",
          str(old / "skills/synthesis-git-hooks/scripts") + "\n")
    write(home / ".synthesis/git-hook-config.yaml",
          "config_version: 2\ntier_0_always:\n  secrets:\n    - 'fixture-credential-token'\n")
    git(home, "config", "--global", "core.hooksPath", str(home / ".synthesis/git-hooks"))
    desired = default_desired_state("skills-only", ["codex"], "stable")
    write(state.desired_path, json.dumps(desired, indent=2, sort_keys=True) + "\n", 0o600)
    data = {
        "version": 2, "generated_files": {}, "adopted_repos": {}, "runs": [],
        "layer_choices": {key: {"choice": value} for key, value in desired["layers"].items()},
        "component_choices": {"inbox-cleanup": {"choice": "declined"}},
        "managed_json_entries": {}, "managed_text_entries": {},
    }
    write(state.state_dir / "receipts.json", json.dumps(data), 0o600)
    for key, value in {
        "HOME": home, "STATE_DIR": state.state_dir,
        "RECEIPTS_PATH": state.state_dir / "receipts.json",
        "WORKSPACES_ROOT": home / "workspaces",
    }.items():
        monkeypatch.setattr(onboard, key, value)
    # Receipts' default argument was bound at module import, before this home.
    real_receipts = onboard.Receipts
    monkeypatch.setattr(onboard, "Receipts", lambda path=None: real_receipts(
        state.state_dir / "receipts.json" if path is None else path))
    monkeypatch.setattr(onboard, "source_root", lambda: current)
    # These stand in for installed clients and the network/plugin update, not
    # for runtime or doctor execution. Every remaining phase is production.
    monkeypatch.setattr(onboard, "phase_preflight", lambda report, wanted: {"codex": "fixture-client"})
    monkeypatch.setattr(onboard, "phase_ecosystem", lambda report, *args, **kwargs:
                        report.add("ecosystem", onboard.OK, "fixture external plugin client"))
    def forbidden_initializer(*args, **kwargs):
        pytest.fail("update must not enter personal initialization")
    monkeypatch.setattr(onboard, "run_whole_system_init", forbidden_initializer)
    return SimpleNamespace(home=home, state=state, old=old, current=current,
                           old_descriptor=old_descriptor, current_descriptor=current_descriptor,
                           desired=desired, original_receipt=copy.deepcopy(data))


def phase(machine, **kwargs):
    report = onboard.Report(as_json=True)
    onboard.phase_shared_runtime(report, onboard.Receipts(), machine.desired, **kwargs)
    return report


def files_snapshot(paths):
    return {str(path): (path.read_bytes(), path.stat().st_mode & 0o777) for path in paths}


def payload_paths(machine):
    return [machine.home / target for target, _ in GIT_PAYLOADS.values()] + [
        machine.home / ".synthesis/git-hooks/source-path",
        machine.state.state_dir / "receipts.json",
    ]


def test_public_update_refreshes_independently_wired_runtime_and_preserves_personal_state(machine):
    protected = {
        machine.home / ".synthesis/git-hook-config.yaml": None,
        machine.home / ".agents/workspace-instructions.md": b"Personal instruction source\r\n",
        machine.home / ".synthesis/personal-policy/profile.json": b'{"personal":true}\n',
        machine.home / ".synthesis/message-guard/patterns.json": b'{"personal_patterns":true}\n',
        machine.home / ".synthesis/day-end/agent-cli": b"codex\n",
        machine.home / "Library/LaunchAgents/com.synthesis.day-end-nudge.plist": b"unselected personal service\n",
        machine.home / ".claude/settings.json": b'{"custom": "personal hook wiring"}\n',
        machine.home / ".codex/hooks.json": b'{"custom": "personal hook wiring"}\n',
        machine.home / ".gitconfig": None,
        machine.state.desired_path: None,
    }
    for path, content in protected.items():
        if content is not None:
            write(path, content)
    before = files_snapshot(protected)
    assert onboard.runtime_components(onboard.Receipts(), machine.desired) == {"git-hooks"}
    assert synthesis_cli.main(["update", "--json"], state=machine.state) == 0
    assert files_snapshot(protected) == before
    for relative, (target, mode) in GIT_PAYLOADS.items():
        assert (machine.home / target).read_bytes() == (machine.current / relative).read_bytes()
        assert (machine.home / target).stat().st_mode & 0o777 == mode
    receipt = onboard.Receipts().data
    assert receipt["layer_choices"] == machine.original_receipt["layer_choices"]
    assert receipt["component_choices"] == machine.original_receipt["component_choices"]
    assert receipt["generated_files"] == {}, "independent refresh must not invent uninstall ownership"
    assert len(receipt["runtime_payloads"]["files"]) == 9
    assert onboard._protective_doctors({"git-hooks"})[0] is True
    assert phase(machine, verify_only=True).exit_code() == 0


def test_doctor_refuses_stale_payload_without_updating_it(machine):
    before = files_snapshot(payload_paths(machine))
    report = phase(machine, verify_only=True)
    assert report.exit_code() == 1
    assert "not current" in report.steps[-1]["detail"]
    assert files_snapshot(payload_paths(machine)) == before


def test_real_protective_doctor_failure_rolls_back_update_payload_and_receipts(machine):
    write(machine.home / ".synthesis/git-hook-config.yaml", "config_version: 2\n")
    before = files_snapshot(payload_paths(machine))
    report = phase(machine)
    assert report.exit_code() == 1
    assert "doctor failed" in report.steps[-1]["detail"]
    assert files_snapshot(payload_paths(machine)) == before
    assert not runtime_payload.pending(machine.state.state_dir)


def test_doctor_timeout_is_real_subprocess_failure_and_rolls_back(machine, monkeypatch):
    original_run = onboard.run
    calls = []
    def bounded_run(command, **kwargs):
        if "--doctor" in command:
            calls.append(command)
            kwargs["timeout"] = 0.000001
        return original_run(command, **kwargs)
    monkeypatch.setattr(onboard, "run", bounded_run)
    before = files_snapshot(payload_paths(machine))
    report = phase(machine)
    assert calls and report.exit_code() == 1
    assert "exit 124" in report.steps[-1]["detail"]
    assert files_snapshot(payload_paths(machine)) == before


def test_inactive_runtime_files_are_not_selected_or_rewritten(machine):
    git(machine.home, "config", "--global", "--unset", "core.hooksPath")
    before = files_snapshot(payload_paths(machine))
    report = phase(machine)
    assert report.exit_code() == 0
    assert report.steps[-1]["status"] == onboard.SKIP
    assert files_snapshot(payload_paths(machine)) == before


def test_tilde_git_wiring_still_enrolls_independent_runtime(machine):
    git(machine.home, "config", "--global", "core.hooksPath", "~/.synthesis/git-hooks")
    assert onboard.runtime_components(onboard.Receipts(), machine.desired) == {"git-hooks"}
    assert phase(machine).exit_code() == 0
    assert (machine.home / GIT_PAYLOADS[STALE_RELATIVE][0]).read_bytes() == (
        machine.current / STALE_RELATIVE).read_bytes()


@pytest.mark.parametrize("wired", [True, False])
def test_doctor_refuses_pending_runtime_journal_even_when_components_unselected(machine, wired):
    if not wired:
        git(machine.home, "config", "--global", "--unset", "core.hooksPath")
    journal = EnrollmentJournal.create(machine.state.state_dir / "runtime-transactions", "a" * 32,
        None, files=[machine.state.state_dir / "receipts.json"], skill_parents=[], purpose="runtime-payload")
    journal.capture(machine.state.state_dir / "receipts.json")
    before = files_snapshot(payload_paths(machine) + [journal.path])
    report = phase(machine, verify_only=True)
    assert report.exit_code() == 1
    assert "pending" in report.steps[-1]["detail"]
    assert files_snapshot(payload_paths(machine) + [journal.path]) == before


def test_public_update_recovers_receipt_before_loading_selection(machine):
    receipt_path = machine.state.state_dir / "receipts.json"
    before_bytes = receipt_path.read_bytes()
    journal = EnrollmentJournal.create(machine.state.state_dir / "runtime-transactions", "b" * 32,
        None, files=[receipt_path], skill_parents=[], purpose="runtime-payload")
    journal.capture(receipt_path)
    changed = copy.deepcopy(machine.original_receipt)
    changed["runtime_payloads"] = {"schema_version": 1, "files": {"unrelated": {"component": "unknown"}}}
    after_bytes = json.dumps(changed).encode()
    journal.data["entries"][0].update(runtime_started=True,
        runtime_before=[hashlib.sha256(before_bytes).hexdigest(), 0o600],
        runtime_after=[hashlib.sha256(after_bytes).hexdigest(), 0o600])
    journal._save()
    write(receipt_path, after_bytes, 0o600)
    assert synthesis_cli.main(["update", "--json"], state=machine.state) == 0
    assert EnrollmentJournal(journal.root).data["state"] == "rolled-back"
    assert set(entry["component"] for entry in onboard.Receipts().data["runtime_payloads"]["files"].values()) == {"git-hooks"}


def hook_config(event, command):
    return {"hooks": {event: [{"matcher": ".*", "hooks": [{"type": "command", "command": command}]}]}}


def test_independently_wired_message_guard_updates_and_runs_real_doctor(machine):
    target = machine.home / ".synthesis/message-guard/message_guard.py"
    write(target, (machine.old / MESSAGE_RELATIVE).read_bytes(), 0o755)
    patterns = machine.home / ".synthesis/message-guard/patterns.json"
    write(patterns, (ROOT / "skills/synthesis-message-guard/patterns.example.json").read_bytes())
    protected = [patterns]
    for client, name in (("claude", "settings.json"), ("codex", "hooks.json")):
        path = machine.home / ("." + client) / name
        write(path, json.dumps(hook_config("PreToolUse", "python3 " + shlex.quote(str(target)))))
        protected.append(path)
    before = files_snapshot(protected)
    assert onboard.runtime_components(onboard.Receipts(), machine.desired) == {"git-hooks", "message-guard"}
    assert synthesis_cli.main(["update", "--json"], state=machine.state) == 0
    assert target.read_bytes() == (machine.current / MESSAGE_RELATIVE).read_bytes()
    assert files_snapshot(protected) == before
    assert onboard._protective_doctors({"git-hooks", "message-guard"})[0] is True


@pytest.mark.parametrize("event,command", [
    ("PreToolUse", "python3 /unrelated/private/message_guard.py"),
    ("PreToolUse", "echo message_guard.py"),
])
def test_unrelated_hook_commands_do_not_enroll_release_runtime(machine, event, command):
    git(machine.home, "config", "--global", "--unset", "core.hooksPath")
    write(machine.home / ".codex/hooks.json", json.dumps(hook_config(event, command)))
    assert onboard.runtime_components(onboard.Receipts(), machine.desired) == set()
    before = files_snapshot(payload_paths(machine))
    assert phase(machine).steps[-1]["status"] == onboard.SKIP
    assert files_snapshot(payload_paths(machine)) == before


@pytest.mark.parametrize("client,name", [("claude", "settings.json"), ("codex", "hooks.json")])
def test_independent_kernel_hook_selects_runtime_without_selecting_personal_layer(machine, client, name):
    git(machine.home, "config", "--global", "--unset", "core.hooksPath")
    engine = machine.state.state_dir / "bin/kernel_sync.py"
    write(machine.home / ("." + client) / name,
          json.dumps(hook_config("PostToolUse", "python3 " + shlex.quote(str(engine)))))
    assert machine.desired["layers"]["agent-kernel"] == "declined"
    assert onboard.runtime_components(onboard.Receipts(), machine.desired) == {"kernel"}


def test_independent_day_end_service_selects_payload_without_launcher_symlink(machine):
    git(machine.home, "config", "--global", "--unset", "core.hooksPath")
    nudge = machine.home / ".synthesis/day-end/bin/day-end-nudge.sh"
    service = machine.home / "Library/LaunchAgents/com.synthesis.day-end-nudge.plist"
    write(service, plistlib.dumps({"Label": "com.synthesis.day-end-nudge", "ProgramArguments": [str(nudge)]}))
    assert not (machine.home / ".local/bin/day-end").exists()
    assert onboard.runtime_components(onboard.Receipts(), machine.desired) == {"day-end"}


def test_legacy_plugin_only_update_migrates_desired_state_without_rewriting_legacy_receipt(machine, monkeypatch):
    machine.state.desired_path.unlink()
    legacy = {"version": 2, "profile": "skills-only", "plugin_policy": {"channel": "stable", "version_pin": None}}
    write(machine.state.legacy_receipts_path, json.dumps(legacy), 0o600)
    before = files_snapshot([machine.state.legacy_receipts_path])
    monkeypatch.setattr(onboard, "resolve_client", lambda client: "fixture-client" if client == "codex" else None)
    monkeypatch.setattr(onboard, "plugin_present", lambda *args: True)
    assert synthesis_cli.main(["update", "--json"], state=machine.state) == 0
    assert machine.state.read_desired() == machine.desired
    assert files_snapshot([machine.state.legacy_receipts_path]) == before
    assert onboard.Receipts().data["layer_choices"] == machine.original_receipt["layer_choices"]
    assert onboard._protective_doctors({"git-hooks"})[0] is True


def test_ambiguous_legacy_personal_state_refuses_migration_without_initialization(machine):
    machine.state.desired_path.unlink()
    write(machine.state.legacy_receipts_path, json.dumps({
        "version": 2, "profile": "full", "personal_workspace": "personal",
        "layer_choices": {"agent-kernel": {"choice": "selected"}},
    }), 0o600)
    before = files_snapshot(payload_paths(machine) + [machine.state.legacy_receipts_path])
    assert synthesis_cli.main(["update", "--json"], state=machine.state) != 0
    assert not machine.state.desired_path.exists()
    assert files_snapshot(payload_paths(machine) + [machine.state.legacy_receipts_path]) == before


def test_receipt_changed_between_engine_load_and_runtime_plan_is_not_overwritten(machine):
    receipts = onboard.Receipts()
    external = copy.deepcopy(receipts.data)
    external["component_choices"]["inbox-cleanup"]["external_note"] = "Independent edit"
    write(receipts.path, json.dumps(external), 0o600)
    before = files_snapshot(payload_paths(machine))
    report = onboard.Report(as_json=True)
    onboard.phase_shared_runtime(report, receipts, machine.desired)
    assert report.exit_code() == 1
    assert files_snapshot(payload_paths(machine)) == before

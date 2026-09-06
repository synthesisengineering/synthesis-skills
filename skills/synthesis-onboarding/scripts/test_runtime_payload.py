"""Release-derived runtime upgrades preserve user state and refuse unknown drift."""

import copy
import json
import os
import subprocess
from pathlib import Path

import pytest

import runtime_payload as runtime
from system_contract import ContractError, release_descriptor_from_checkout


SOURCE_FILES = {
    "git-hooks": {
        "skills/synthesis-git-hooks/scripts/pre-commit": (".synthesis/git-hooks/pre-commit", 0o755),
        "skills/synthesis-git-hooks/scripts/commit-msg": (".synthesis/git-hooks/commit-msg", 0o755),
        "skills/synthesis-git-hooks/scripts/_load_config.py": (".synthesis/git-hooks/_load_config.py", 0o755),
        **{"skills/synthesis-project-management/scripts/" + n:
           (".synthesis/git-hooks/" + n, 0o755) for n in
           ("coordination.py", "coordination_schema.py", "pointer_lock.py", "peer_addressing.py")},
        "skills/synthesis-project-management/references/session-words-v1.txt.zlib.b85":
            (".synthesis/references/session-words-v1.txt.zlib.b85", 0o644),
    },
    "message-guard": {"skills/synthesis-message-guard/scripts/message_guard.py":
                      (".synthesis/message-guard/message_guard.py", 0o755)},
    "kernel": {"skills/synthesis-onboarding/scripts/" + n:
               (".local/state/synthesis/bin/" + n, 0o755)
               for n in ("kernel_sync.py", "whole_system.py")},
    "day-end": {"skills/synthesis-daily-rituals/scripts/" + n:
                (".synthesis/day-end/bin/" + n, 0o755)
                for n in ("day-end", "day-end-nudge.sh")},
}


class Receipts:
    def __init__(self, path):
        self.path = path
        self.data = {"version": 2, "generated_files": {}, "layer_choices": {"agent-kernel": "declined"}}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.data))


def release(root, version):
    root.mkdir()
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    def git(*args):
        return subprocess.run(["git", "-C", str(root), *args], check=True,
                              capture_output=True, text=True, env=env).stdout.strip()
    git("init")
    git("config", "user.name", "Fixture")
    git("config", "user.email", "fixture@example.invalid")
    for group in SOURCE_FILES.values():
        for relative in group:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(relative + "\nrelease=" + version + "\n")
    for client in ("claude", "codex"):
        manifest = root / ("." + client + "-plugin/plugin.json")
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({"name": "synthesis-skills", "version": version}))
    git("add", ".")
    git("commit", "-m", "Fixture")
    git("tag", "v" + version)
    return release_descriptor_from_checkout(root, "pin", "v" + version,
                                            "https://example.invalid/public/skills.git")


@pytest.fixture
def installation(tmp_path):
    old = tmp_path / "old"
    descriptor = release(old, "1.0.0")
    current = tmp_path / "current"
    release(current, "1.0.1")
    home = tmp_path / "home"
    state = home / ".local/state/synthesis"
    for group in SOURCE_FILES.values():
        for relative, (target, mode) in group.items():
            path = home / target
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((old / relative).read_bytes())
            path.chmod(mode)
    pointer = home / ".synthesis/git-hooks/source-path"
    pointer.write_text(str(old / "skills/synthesis-git-hooks/scripts") + "\n")
    pointer.chmod(0o644)
    protected = {
        ".synthesis/git-hook-config.yaml": b"personal policy\n",
        ".synthesis/message-guard/patterns.json": b"personal patterns\n",
        ".synthesis/day-end/agent-cli": b"codex\n",
        "Library/LaunchAgents/com.synthesis.day-end-nudge.plist": b"personal service\n",
        ".claude/settings.json": b"personal hook wiring\n",
        ".agents/workspace-instructions.md": b"personal kernel\n",
    }
    for relative, content in protected.items():
        path = home / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    receipts = Receipts(state / "receipts.json")
    return current, old, descriptor, home, state, receipts, protected


def make_plan(data, components=None):
    current, old, descriptor, home, state, receipts, _ = data
    return runtime.plan(current, home, state, components or set(SOURCE_FILES), receipts.data,
                        legacy_releases=[(old, descriptor)])


def snapshot(home):
    return {str(p.relative_to(home)): (p.read_bytes(), p.stat().st_mode & 0o777)
            for p in home.rglob("*") if p.is_file()}


def test_upgrade_stale_dependency_and_keep_personal_configuration(installation):
    current, _, _, home, _, receipts, protected = installation
    before_choices = copy.deepcopy(receipts.data["layer_choices"])
    plan = make_plan(installation)
    assert any(x["status"] != "current" for x in runtime.verify(plan))
    runtime.apply(plan, receipts)
    for group in SOURCE_FILES.values():
        for relative, (target, mode) in group.items():
            assert (home / target).read_bytes() == (current / relative).read_bytes()
            assert (home / target).stat().st_mode & 0o777 == mode
    for relative, content in protected.items():
        assert (home / relative).read_bytes() == content
    assert receipts.data["layer_choices"] == before_choices
    assert receipts.data["runtime_payloads"]["schema_version"] == 1
    assert all(x["status"] == "current" for x in runtime.verify(make_plan(installation)))


def test_all_target_preflight_refuses_unknown_edit_without_writes(installation):
    home = installation[3]
    (home / ".synthesis/day-end/bin/day-end-nudge.sh").write_text("private modification")
    before = snapshot(home)
    with pytest.raises(ContractError, match="unowned|modified|provenance"):
        make_plan(installation)
    assert snapshot(home) == before


def test_legacy_release_contents_must_match_descriptor(installation):
    (installation[1] / "skills/synthesis-project-management/scripts/peer_addressing.py").write_text("tampered")
    with pytest.raises(ContractError):
        make_plan(installation)


def test_current_git_source_dirty_bytes_are_refused(installation):
    (installation[0] / "skills/synthesis-project-management/scripts/peer_addressing.py").write_text("uncommitted")
    with pytest.raises(ContractError):
        make_plan(installation)


def test_symlink_destination_is_not_followed(installation):
    home = installation[3]
    path = home / ".synthesis/git-hooks/peer_addressing.py"
    victim = home / "personal.txt"
    victim.write_text("private")
    path.unlink()
    path.symlink_to(victim)
    with pytest.raises(ContractError, match="symbolic|symlink"):
        make_plan(installation)
    assert victim.read_text() == "private"


def test_doctor_failure_restores_every_byte_mode_and_receipt(installation):
    home, receipts = installation[3], installation[5]
    before = snapshot(home)
    before_data = copy.deepcopy(receipts.data)
    def failed_doctor():
        raise ContractError("selected doctor failed")
    with pytest.raises(ContractError, match="selected doctor failed"):
        runtime.apply(make_plan(installation), receipts, verify_after=failed_doctor)
    after = snapshot(home)
    assert {p: after[p] for p in before} == before
    assert receipts.data == before_data


def test_post_plan_concurrent_edit_is_preserved(installation):
    plan = make_plan(installation)
    path = installation[3] / ".synthesis/git-hooks/peer_addressing.py"
    path.write_text("concurrent edit")
    with pytest.raises(ContractError, match="changed|modified"):
        runtime.apply(plan, installation[5])
    assert path.read_text() == "concurrent edit"


def test_unselected_runtime_and_personal_wiring_untouched(installation):
    home = installation[3]
    before = snapshot(home)
    runtime.apply(make_plan(installation, {"git-hooks"}), installation[5])
    for key, value in before.items():
        if key.startswith((".synthesis/git-hooks/", ".synthesis/references/")) or key.endswith("receipts.json"):
            continue
        assert snapshot(home)[key] == value


def test_exact_current_unreceipted_bytes_can_be_enrolled(installation):
    current, _, _, home, state, receipts, _ = installation
    for relative, (target, mode) in SOURCE_FILES["message-guard"].items():
        (home / target).write_bytes((current / relative).read_bytes())
    plan = runtime.plan(current, home, state, {"message-guard"}, receipts.data)
    before = (home / ".synthesis/message-guard/message_guard.py").stat().st_mtime_ns
    runtime.apply(plan, receipts)
    assert (home / ".synthesis/message-guard/message_guard.py").stat().st_mtime_ns == before


def test_unknown_component_is_not_silently_skipped(installation):
    with pytest.raises(ContractError, match="component"):
        make_plan(installation, {"inbox-cleanup"})

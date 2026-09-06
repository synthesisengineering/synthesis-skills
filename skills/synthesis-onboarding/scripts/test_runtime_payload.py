"""Release-derived runtime upgrades preserve user state and refuse unknown drift."""

import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import runtime_payload as runtime
import enrollment
from onboard import Receipts as EngineReceipts
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
                for n in ("day-end", "day-end-nudge.sh", "ritual_state.py")},
}


class Receipts(EngineReceipts):
    def __init__(self, path):
        super().__init__(path)
        self.data = {"version": 2, "generated_files": {}, "layer_choices": {"agent-kernel": "declined"}}
        self.save()


def release(root, version, *, omit=(), replacements=None):
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
            if relative in omit:
                continue
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text((replacements or {}).get(relative, relative + "\nrelease=" + version + "\n"))
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


def test_unrelated_unavailable_history_does_not_block_current_payload(installation):
    current, _, _, home, state, receipts, _ = installation
    target = home / ".synthesis/message-guard/message_guard.py"
    target.write_bytes((current / "skills/synthesis-message-guard/scripts/message_guard.py").read_bytes())
    plan = runtime.plan(current, home, state, {"message-guard"}, receipts.data,
                        legacy_releases=[(home / "missing-history", {})])
    assert runtime.verify(plan)[0]["status"] == "current"


def test_injected_second_write_failure_restores_payloads(installation, monkeypatch):
    home, receipts = installation[3], installation[5]
    before = snapshot(home)
    original = runtime.atomic_write_bytes
    calls = []
    def writer(target, content, mode):
        calls.append(target)
        if len(calls) == 2:
            raise OSError("injected write failure")
        original(target, content, mode)
    monkeypatch.setattr(runtime, "atomic_write_bytes", writer)
    with pytest.raises(OSError, match="injected write failure"):
        runtime.apply(make_plan(installation), receipts)
    after = snapshot(home)
    assert {p: after[p] for p in before} == before


def test_same_release_reapply_does_not_change_payload_mtimes(installation):
    runtime.apply(make_plan(installation), installation[5])
    home = installation[3]
    paths = [home / target for group in SOURCE_FILES.values() for target, _ in group.values()]
    before = {p: p.stat().st_mtime_ns for p in paths}
    result = runtime.apply(make_plan(installation), installation[5])
    assert result["changed"] == []
    assert result["journal"] is None
    assert before == {p: p.stat().st_mtime_ns for p in paths}


def test_matching_stable_pointer_is_not_canonicalized(installation, tmp_path):
    current, _, _, home, state, receipts, _ = installation
    for relative, (target, _) in SOURCE_FILES["git-hooks"].items():
        (home / target).write_bytes((current / relative).read_bytes())
    stable = tmp_path / "stable"
    stable.symlink_to(current, target_is_directory=True)
    pointer = home / ".synthesis/git-hooks/source-path"
    content = str(stable / "skills/synthesis-git-hooks/scripts") + "\n"
    pointer.write_text(content)
    before = pointer.stat().st_mtime_ns
    runtime.apply(runtime.plan(current, home, state, {"git-hooks"}, receipts.data), receipts)
    assert pointer.read_text() == content
    assert pointer.stat().st_mtime_ns == before


def test_missing_previously_owned_file_is_restored(installation):
    runtime.apply(make_plan(installation), installation[5])
    target = installation[3] / ".synthesis/git-hooks/peer_addressing.py"
    target.unlink()
    runtime.apply(make_plan(installation), installation[5])
    assert target.read_bytes() == (installation[0] / "skills/synthesis-project-management/scripts/peer_addressing.py").read_bytes()


def test_missing_unowned_file_is_not_invented(installation):
    target = installation[3] / ".synthesis/git-hooks/peer_addressing.py"
    target.unlink()
    with pytest.raises(ContractError, match="missing"):
        make_plan(installation)
    assert not target.exists()


def test_owned_file_changed_mode_is_not_overwritten(installation):
    runtime.apply(make_plan(installation), installation[5])
    target = installation[3] / ".synthesis/git-hooks/peer_addressing.py"
    target.chmod(0o700)
    with pytest.raises(ContractError, match="unowned|modified"):
        make_plan(installation)
    assert target.stat().st_mode & 0o777 == 0o700


def test_process_interruption_recovered_from_durable_exact_target_journal(installation):
    current, old, descriptor, home, state, receipts, _ = installation
    before = snapshot(home)
    program = """
import json, os
from pathlib import Path
import runtime_payload as runtime
from onboard import Receipts
receipts = Receipts(Path(RECEIPT))
plan = runtime.plan(Path(CURRENT), Path(HOME), Path(STATE), {'git-hooks'}, receipts.data,
                    legacy_releases=[(Path(OLD), DESCRIPTOR)])
original = runtime.atomic_write_bytes
calls = 0
def writer(path, content, mode):
    global calls
    calls += 1
    original(path, content, mode)
    if calls == 2:
        os._exit(77)
runtime.atomic_write_bytes = writer
runtime.apply(plan, receipts)
"""
    bindings = "\n".join(name + " = " + repr(value) for name, value in {
        "RECEIPT": str(receipts.path), "CURRENT": str(current), "HOME": str(home),
        "STATE": str(state), "OLD": str(old), "DESCRIPTOR": descriptor,
    }.items())
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(Path(runtime.__file__).parent)}
    child = subprocess.run([sys.executable, "-B", "-c", bindings + "\n" + program],
                           capture_output=True, text=True, timeout=30, env=env)
    assert child.returncode == 77, child.stderr
    assert snapshot(home)[".synthesis/git-hooks/pre-commit"] != before[".synthesis/git-hooks/pre-commit"]
    interrupted = snapshot(home)
    with pytest.raises(ContractError, match="recovery is pending"):
        make_plan(installation)
    assert snapshot(home) == interrupted
    assert len(runtime.recover(home, state)) == 1
    after = snapshot(home)
    assert {p: after[p] for p in before} == before
    assert runtime.recover(home, state) == []


def test_doctor_concurrent_edit_is_not_overwritten_by_rollback(installation):
    target = installation[3] / ".synthesis/git-hooks/peer_addressing.py"
    def raced_doctor():
        target.write_text("independent edit after activation")
        raise ContractError("doctor failed")
    with pytest.raises(ContractError, match="rollback refuses a concurrent"):
        runtime.apply(make_plan(installation), installation[5], verify_after=raced_doctor)
    assert target.read_text() == "independent edit after activation"


def test_existing_conffile_receipt_advances_without_claiming_new_uninstall_ownership(installation):
    receipts = installation[5]
    target = installation[3] / ".synthesis/message-guard/message_guard.py"
    receipts.data["generated_files"][str(target)] = {
        "kind": "hooks-gates", "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
    }
    runtime.apply(make_plan(installation), receipts)
    assert set(receipts.data["generated_files"]) == {str(target)}
    assert receipts.data["generated_files"][str(target)]["sha256"] == hashlib.sha256(target.read_bytes()).hexdigest()


def test_false_doctor_result_cannot_commit(installation):
    home = installation[3]
    before = snapshot(home)
    with pytest.raises(ContractError, match="doctor failed"):
        runtime.apply(make_plan(installation), installation[5], verify_after=lambda: False)
    after = snapshot(home)
    assert {p: after[p] for p in before} == before


def test_verify_existing_plan_reports_pending_without_recovery(installation):
    plan = make_plan(installation)
    def raced_doctor():
        installation[3].joinpath(".synthesis/git-hooks/peer_addressing.py").write_text("independent edit")
        raise ContractError("doctor failed")
    with pytest.raises(ContractError):
        runtime.apply(plan, installation[5], verify_after=raced_doctor)
    before = snapshot(installation[3])
    assert any(item["status"] == "pending" for item in runtime.verify(plan))
    assert snapshot(installation[3]) == before


@pytest.mark.parametrize("bad_data", [[], {"generated_files": []}])
def test_malformed_receipt_mapping_is_a_contract_error(installation, bad_data):
    receipts = installation[5]
    receipts.data = bad_data
    before = snapshot(installation[3])
    with pytest.raises(ContractError, match="receipt|inventory"):
        runtime.apply(make_plan(installation), receipts)
    assert snapshot(installation[3]) == before


def test_receipt_file_edited_after_plan_is_preserved(installation):
    plan = make_plan(installation)
    receipts = installation[5]
    receipts.path.write_text('{"independent": "receipt edit"}\n')
    before = snapshot(installation[3])
    with pytest.raises(ContractError, match="receipt changed"):
        runtime.apply(plan, receipts)
    after = snapshot(installation[3])
    assert {p: after[p] for p in before} == before
    assert set(after) - set(before) <= {".local/state/synthesis/engine.lock"}


def test_idempotent_apply_checks_payload_after_doctor(installation):
    runtime.apply(make_plan(installation), installation[5])
    plan = make_plan(installation)
    target = installation[3] / ".synthesis/git-hooks/peer_addressing.py"
    def raced_doctor():
        target.write_text("independent edit during doctor")
    with pytest.raises(ContractError, match="changed during doctor"):
        runtime.apply(plan, installation[5], verify_after=raced_doctor)
    assert target.read_text() == "independent edit during doctor"


def test_plan_to_capture_race_preserves_independent_edit(installation, monkeypatch):
    plan = make_plan(installation)
    target = installation[3] / ".synthesis/git-hooks/peer_addressing.py"
    original = enrollment.EnrollmentJournal.capture
    def raced_capture(journal, path):
        if path == target:
            target.write_text("independent edit before capture")
        return original(journal, path)
    monkeypatch.setattr(enrollment.EnrollmentJournal, "capture", raced_capture)
    with pytest.raises(ContractError, match="changed"):
        runtime.apply(plan, installation[5])
    assert target.read_text() == "independent edit before capture"


def test_interrupted_rollback_recovers_after_archiving_failed_generation(installation, monkeypatch):
    home, state, receipts = installation[3:6]
    before = snapshot(home)
    original = enrollment.copy_verified
    def interrupted_copy(source, destination):
        if "before" in source.parts:
            raise OSError("interrupted restoration")
        return original(source, destination)
    with monkeypatch.context() as injected:
        injected.setattr(enrollment, "copy_verified", interrupted_copy)
        with pytest.raises(OSError, match="interrupted restoration"):
            runtime.apply(make_plan(installation), receipts, verify_after=lambda: False)
    assert runtime.pending(state)
    assert not receipts.path.exists()
    assert len(runtime.recover(home, state)) == 1
    after = snapshot(home)
    assert {p: after[p] for p in before} == before
    assert not runtime.pending(state)


def test_stable_pointer_target_drift_is_not_current(installation, tmp_path):
    current, old, _, home, state, receipts, _ = installation
    runtime.apply(make_plan(installation), receipts)
    stable = tmp_path / "stable"
    stable.symlink_to(current, target_is_directory=True)
    pointer = home / ".synthesis/git-hooks/source-path"
    pointer.write_text(str(stable / "skills/synthesis-git-hooks/scripts") + "\n")
    plan = runtime.plan(current, home, state, {"git-hooks"}, receipts.data)
    assert all(row["status"] == "current" for row in runtime.verify(plan))
    stable.unlink()
    stable.symlink_to(old, target_is_directory=True)
    assert any(row["status"] == "drift" and row["target"] == str(pointer)
               for row in runtime.verify(plan))


@pytest.mark.parametrize("already_current", [False, True])
def test_receipt_edit_during_doctor_is_preserved(installation, already_current):
    receipts = installation[5]
    if already_current:
        runtime.apply(make_plan(installation), receipts)
    plan = make_plan(installation)
    changed = '{"independent": "doctor-time receipt edit"}\n'
    def raced_doctor():
        receipts.path.write_text(changed)
    with pytest.raises(ContractError, match="concurrent target change|receipt changed during doctor"):
        runtime.apply(plan, receipts, verify_after=raced_doctor)
    assert receipts.path.read_text() == changed


def test_actual_receipt_save_refuses_external_edit_after_load(tmp_path):
    path = tmp_path / "receipts.json"
    path.write_text('{"version": 2, "existing": true}\n')
    receipts = EngineReceipts(path)
    receipts.data["local-unsaved"] = True
    independent = '{"version": 2, "independent": true}\n'
    path.write_text(independent)
    with pytest.raises(ContractError, match="receipt.*changed"):
        receipts.save()
    assert path.read_text() == independent
    assert receipts.data["local-unsaved"] is True


def test_actual_receipt_save_preserves_unsaved_fields_mode_and_unique_temp(tmp_path):
    path = tmp_path / "receipts.json"
    path.write_text('{"version": 2, "existing": true}\n')
    path.chmod(0o640)
    old_temp = tmp_path / "receipts.tmp"
    old_temp.write_text("unrelated temporary file")
    receipts = EngineReceipts(path)
    receipts.data["local-unsaved"] = True
    receipts.save()
    receipts.assert_current()
    receipts.data["next-phase"] = True
    receipts.save()
    assert json.loads(path.read_text())["local-unsaved"] is True
    assert json.loads(path.read_text())["next-phase"] is True
    assert path.stat().st_mode & 0o777 == 0o640
    assert old_temp.read_text() == "unrelated temporary file"


def test_actual_receipt_loader_refuses_symlinks(tmp_path):
    victim = tmp_path / "personal.json"
    victim.write_text('{"version": 2}\n')
    path = tmp_path / "receipts.json"
    path.symlink_to(victim)
    with pytest.raises(ContractError, match="symbolic|symlink"):
        EngineReceipts(path)
    assert victim.read_text() == '{"version": 2}\n'


def test_actual_receipt_loaded_before_plan_rejects_new_disk_generation(installation):
    installation = list(installation)
    installation[5] = EngineReceipts(installation[5].path)
    receipts = installation[5]
    independent = '{"version": 2, "independent": true}\n'
    receipts.path.write_text(independent)
    plan = make_plan(installation)
    before = snapshot(installation[3])
    with pytest.raises(ContractError, match="receipt.*changed"):
        runtime.apply(plan, receipts)
    assert receipts.path.read_text() == independent
    after = snapshot(installation[3])
    assert {p: after[p] for p in before} == before


@pytest.mark.parametrize("doctor_fails", [False, True])
def test_actual_receipt_runtime_handshake_allows_next_phase_save(installation, doctor_fails):
    installation = list(installation)
    installation[5] = EngineReceipts(installation[5].path)
    receipts = installation[5]
    receipts.data["legitimate-unsaved"] = "phase data"
    plan = make_plan(installation)
    if doctor_fails:
        with pytest.raises(ContractError, match="doctor failed"):
            runtime.apply(plan, receipts, verify_after=lambda: False)
    else:
        runtime.apply(plan, receipts)
    receipts.assert_current()
    receipts.data["next-phase"] = True
    receipts.save()
    saved = json.loads(receipts.path.read_text())
    assert saved["legitimate-unsaved"] == "phase data"
    assert saved["next-phase"] is True
    assert ("runtime_payloads" in saved) is not doctor_fails


def test_receipt_acknowledgement_cannot_accept_unknown_generation(tmp_path):
    path = tmp_path / "receipts.json"
    path.write_text('{"version": 2}\n')
    receipts = EngineReceipts(path)
    previous = receipts.assert_current()
    independent = '{"version": 2, "independent": true}\n'
    path.write_text(independent)
    with pytest.raises(ContractError, match="changed"):
        receipts.accept_runtime_write(previous, previous)
    with pytest.raises(ContractError, match="receipt.*changed"):
        receipts.save()
    assert path.read_text() == independent


def test_receipt_save_rechecks_generation_after_staging(tmp_path, monkeypatch):
    import tempfile
    path = tmp_path / "receipts.json"
    path.write_text('{"version": 2}\n')
    receipts = EngineReceipts(path)
    independent = '{"version": 2, "independent": true}\n'
    original = tempfile.mkstemp
    def raced_stage(*args, **kwargs):
        result = original(*args, **kwargs)
        path.write_text(independent)
        return result
    monkeypatch.setattr(tempfile, "mkstemp", raced_stage)
    with pytest.raises(ContractError, match="receipt.*changed"):
        receipts.save()
    assert path.read_text() == independent
    assert not list(tmp_path.glob(".receipts-*.tmp"))

DAY_END_DEPENDENCY = "skills/synthesis-daily-rituals/scripts/ritual_state.py"
DAY_END_NUDGE = "skills/synthesis-daily-rituals/scripts/day-end-nudge.sh"
# Exact public v4.83.0 blob at commit 920c379b37f496b9e775796f02a12c64f6fdc1b4.
LEGACY_NUDGE = "#!/usr/bin/env bash\n# day-end-nudge.sh — state-aware evening nudge (notification ONLY).\n#\n# Shows one generic macOS banner during the evening-ritual window unless\n# today's day-end has already run. Confidentiality: the banner text is\n# generic and fixed — zero identifying content ever appears on this\n# surface (others see banners on screen-shares). This script never\n# mutates anything: it reads one JSON file and shows one notification.\n# Scheduled by the companion LaunchAgent plist (weekdays 16:55).\nset -euo pipefail\nSTATE=\"$HOME/.synthesis/day-end/state.json\"\nTODAY=\"$(date +%Y-%m-%d)\"\nif [ -f \"$STATE\" ] && python3 - \"$STATE\" \"$TODAY\" <<'PY'\nimport json, sys\ntry:\n    state = json.load(open(sys.argv[1]))\n    done = (state.get(\"last_day_end\") or {}).get(\"date\") == sys.argv[2]\nexcept Exception:\n    done = False\nsys.exit(0 if done else 1)\nPY\nthen\n  exit 0  # day-end already ran today — stay silent\nfi\n/usr/bin/osascript -e 'display notification \"Evening ritual window — details in your synthesis console\" with title \"Synthesis\"'\n"


def fixture_git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True,
        env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}).strip()


@pytest.fixture
def day_end_history(tmp_path):
    from types import SimpleNamespace
    root = tmp_path / "history"
    source = Path(runtime.__file__).resolve().parents[3]
    launcher_relative = "skills/synthesis-daily-rituals/scripts/day-end"
    descriptor = release(root, "4.83.0", omit=(DAY_END_DEPENDENCY,), replacements={
        DAY_END_NUDGE: LEGACY_NUDGE, launcher_relative: (source / launcher_relative).read_text(),
    })
    home = tmp_path / "home"
    state = home / ".local/state/synthesis"
    for relative in (launcher_relative, DAY_END_NUDGE):
        path = home / SOURCE_FILES["day-end"][relative][0]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((root / relative).read_bytes())
        path.chmod(0o755)
    old = descriptor["commit"]
    for relative in (DAY_END_NUDGE, DAY_END_DEPENDENCY):
        (root / relative).write_bytes((source / relative).read_bytes())
    for client in ("claude", "codex"):
        (root / ("." + client + "-plugin/plugin.json")).write_text(json.dumps({
            "name": "synthesis-skills", "version": "4.95.7",
        }))
    fixture_git(root, "add", ".")
    fixture_git(root, "commit", "-qm", "Fixture")
    fixture_git(root, "tag", "v4.95.7")
    receipts = Receipts(state / "receipts.json")
    return SimpleNamespace(root=root, home=home, state=state, old=old, receipts=receipts,
        helper=home / SOURCE_FILES["day-end"][DAY_END_DEPENDENCY][0],
        nudge=home / SOURCE_FILES["day-end"][DAY_END_NUDGE][0])


def history_plan(machine, **kwargs):
    return runtime.plan(machine.root, machine.home, machine.state, {"day-end"},
                        machine.receipts.data, legacy_git_root=machine.root, **kwargs)


def test_actual_legacy_nudge_upgrades_with_executable_dependency_closure(day_end_history):
    machine = day_end_history
    assert hashlib.sha256(machine.nudge.read_bytes()).hexdigest() == "833cdc1330de9ce120a93969ee822a240c170fc702e8208c09f4d9218c18de9a"
    assert not machine.helper.exists()
    runtime.apply(history_plan(machine), machine.receipts)
    assert machine.helper.read_bytes() == (machine.root / DAY_END_DEPENDENCY).read_bytes()
    assert machine.helper.stat().st_mode & 0o777 == 0o755
    assert machine.nudge.read_bytes() == (machine.root / DAY_END_NUDGE).read_bytes()
    result = subprocess.run([sys.executable, "-B", str(machine.helper), "query", "summary", "--json", "--today", "2026-09-06"],
        capture_output=True, text=True, timeout=15,
        env={**os.environ, "HOME": str(machine.home), "RITUAL_STATE_DIR": str(machine.home / ".synthesis/rituals")})
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["open_workdays"] == []


@pytest.mark.parametrize("damage", ["missing-launcher", "modified-nudge", "owned-but-unreleased-nudge", "symlink-helper", "wrong-mode"])
def test_dependency_introduction_refuses_unproven_or_absent_anchor(day_end_history, damage):
    machine = day_end_history
    if damage == "missing-launcher":
        machine.nudge.with_name("day-end").unlink()
    elif damage in {"modified-nudge", "owned-but-unreleased-nudge"}:
        machine.nudge.write_text("independent custom launcher\n")
        if damage == "owned-but-unreleased-nudge":
            machine.receipts.data["runtime_payloads"] = {"schema_version": 1, "files": {
                str(machine.nudge): {"component": "day-end", "source_relative": DAY_END_NUDGE,
                    "source_commit": machine.old, "sha256": hashlib.sha256(machine.nudge.read_bytes()).hexdigest(), "mode": 0o755},
            }}
    elif damage == "symlink-helper":
        machine.helper.symlink_to(machine.nudge)
    else:
        machine.nudge.chmod(0o700)
    before = snapshot(machine.home)
    with pytest.raises(ContractError):
        history_plan(machine)
    assert snapshot(machine.home) == before


@pytest.mark.parametrize("damage", ["retagged-version", "unrelated-repo", "symlink-repo"])
def test_git_history_requires_current_binding_and_valid_historical_tag(day_end_history, tmp_path, damage):
    machine = day_end_history
    history = machine.root
    if damage == "retagged-version":
        fixture_git(history, "tag", "-f", "v4.83.0", "HEAD")
    elif damage == "unrelated-repo":
        history = tmp_path / "unrelated"
        release(history, "9.0.0")
    else:
        history = tmp_path / "alias"
        history.symlink_to(machine.root, target_is_directory=True)
    before = snapshot(machine.home)
    with pytest.raises(ContractError):
        runtime.plan(machine.root, machine.home, machine.state, {"day-end"}, machine.receipts.data, legacy_git_root=history)
    assert snapshot(machine.home) == before


def test_current_anchors_can_introduce_only_the_declared_new_dependency(day_end_history):
    machine = day_end_history
    machine.nudge.write_bytes((machine.root / DAY_END_NUDGE).read_bytes())
    plan = runtime.plan(machine.root, machine.home, machine.state, {"day-end"}, machine.receipts.data)
    runtime.apply(plan, machine.receipts)
    assert machine.helper.exists()


def test_old_immutable_descriptor_can_prove_anchors_without_new_helper(day_end_history, tmp_path):
    import io
    import tarfile
    machine = day_end_history
    old = tmp_path / "old-materialized"
    old.mkdir()
    payload = subprocess.check_output(["git", "-C", str(machine.root), "archive", machine.old])
    with tarfile.open(fileobj=io.BytesIO(payload)) as archive:
        archive.extractall(old, filter="data")
    fixture_git(machine.root, "checkout", "--detach", machine.old)
    descriptor = release_descriptor_from_checkout(machine.root, "pin", "v4.83.0", "https://example.invalid/public/skills.git")
    fixture_git(machine.root, "checkout", "--detach", "v4.95.7")
    runtime.apply(runtime.plan(machine.root, machine.home, machine.state, {"day-end"}, machine.receipts.data,
                               legacy_releases=[(old, descriptor)]), machine.receipts)
    assert machine.helper.exists()

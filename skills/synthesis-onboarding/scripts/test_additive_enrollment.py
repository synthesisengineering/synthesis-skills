"""Defect-pinned additive enrollment boundaries, independent of setup."""

import copy
import errno
from datetime import datetime, timedelta, timezone
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import synthesis_cli as cli
import system_contract as contract
from test_synthesis_cli import full_configuration
from test_onboard import Sandbox


REPOSITORY = "https://example.test/team/config.git"


def base_state(tmp_path, profile="skills-only"):
    state = contract.SystemState(home=tmp_path)
    desired = contract.default_desired_state(
        profile, ["codex"], "stable",
        personal_workspace="personal" if profile == "full" else None,
        personal_configuration=full_configuration() if profile == "full" else None,
    )
    state.run_transaction("setup", desired, lambda _tx: {})
    return state, desired


def org_fixture(tmp_path, monkeypatch):
    root = tmp_path / "org-source"
    root.mkdir()
    manifest = {
        "org": {"workspace": "example-team"},
        "ecosystem": {"clients": ["codex"], "channel": "stable", "version_pin": None},
    }
    monkeypatch.setattr(cli.organization, "acquire_repository", lambda *a, **k: (root, "1" * 40))
    monkeypatch.setattr(cli.onboard, "load_manifest", lambda _path: manifest)
    monkeypatch.setattr(cli, "_active_release", lambda: None)
    return manifest


@pytest.mark.parametrize("profile", ["skills-only", "full"])
def test_enroll_preserves_base_and_replays_overlay(tmp_path, monkeypatch, profile):
    state, base = base_state(tmp_path, profile)
    org_fixture(tmp_path, monkeypatch)
    calls = []

    def engine(argv):
        assert argv[0] != "init"
        proposed = json.loads(Path(argv[argv.index("--desired-state") + 1]).read_text())
        calls.append((argv, proposed))
        return 0

    assert cli.main(["enroll", "--org-repo", REPOSITORY], state=state, engine_runner=engine) == 0
    enrolled = state.read_desired()
    for key, value in base.items():
        if key not in {"organizations", "layers"}:
            assert enrolled[key] == value, key
    assert enrolled["layers"] == {**base["layers"], "organization": "selected"}
    assert enrolled["organizations"][0] == {
        "repository": REPOSITORY, "manifest_path": ".agents/onboarding.yaml",
        "commit_policy": "floating", "commit": "1" * 40,
        "mode": "additive", "workspace": "example-team",
    }
    assert [argv[0] for argv, _ in calls] == ["enroll", "doctor"]
    assert all(proposed == enrolled for _, proposed in calls)
    for command in ("update", "repair", "doctor"):
        # The fixture has no genuine client SessionStart receipt. Doctor
        # reaches the correct engine but must still report restart-required.
        assert cli.main([command], state=state, engine_runner=engine) == (1 if command == "doctor" else 0)
        assert state.read_desired() == enrolled
    assert cli.main(["enroll", "--org-repo", REPOSITORY], state=state, engine_runner=engine) == 0
    assert state.read_desired() == enrolled


@pytest.mark.parametrize("enabled", [None, False])
def test_enroll_requires_existing_enabled_state(tmp_path, monkeypatch, capsys, enabled):
    state = contract.SystemState(home=tmp_path)
    if enabled is False:
        desired = contract.default_desired_state("skills-only", ["codex"], "stable", enabled=False)
        state.run_transaction("setup", desired, lambda _tx: {})
    calls = []
    assert cli.main(["enroll", "--org-repo", REPOSITORY], state=state, engine_runner=lambda a: calls.append(a)) == 2
    assert "existing enabled" in capsys.readouterr().err
    assert calls == []


@pytest.mark.parametrize("conflict", ["clients", "channel", "pin", "workspace"])
def test_enroll_conflict_is_pre_mutation(tmp_path, monkeypatch, capsys, conflict):
    state, base = base_state(tmp_path, "full")
    manifest = org_fixture(tmp_path, monkeypatch)
    if conflict == "clients":
        manifest["ecosystem"]["clients"] = ["claude", "codex"]
    elif conflict == "channel":
        manifest["ecosystem"]["channel"] = "edge"
    elif conflict == "pin":
        manifest["ecosystem"]["version_pin"] = "1.2.3"
    else:
        manifest["org"]["workspace"] = "personal"
    calls = []
    assert cli.main(["enroll", "--org-repo", REPOSITORY], state=state, engine_runner=lambda a: calls.append(a)) == 2
    assert calls == []
    assert state.read_desired() == base
    assert capsys.readouterr().err


def test_additive_replay_refuses_policy_and_workspace_changes(tmp_path, monkeypatch):
    state, _ = base_state(tmp_path)
    manifest = org_fixture(tmp_path, monkeypatch)
    assert cli.main(["enroll", "--org-repo", REPOSITORY], state=state, engine_runner=lambda a: 0) == 0
    baseline = state.desired_path.read_bytes()
    for field, value in (("channel", "edge"), ("clients", ["claude"]), ("version_pin", "1.0.0")):
        original = manifest["ecosystem"][field]
        manifest["ecosystem"][field] = value
        for command in ("update", "repair", "doctor"):
            calls = []
            assert cli.main([command], state=state, engine_runner=lambda a: calls.append(a)) == 2
            assert not calls
            assert state.desired_path.read_bytes() == baseline
        manifest["ecosystem"][field] = original
    manifest["org"]["workspace"] = "another-team"
    assert cli.main(["update"], state=state, engine_runner=lambda a: pytest.fail("engine ran")) == 2
    assert state.desired_path.read_bytes() == baseline
    assert cli.main(["enroll", "--org-repo", "https://example.test/other/config.git"], state=state, engine_runner=lambda a: pytest.fail("engine ran")) == 2


@pytest.mark.parametrize("failure", ["engine", "doctor", "commit"])
def test_enroll_failure_restores_generated_files_and_desired(tmp_path, monkeypatch, failure):
    state, _ = base_state(tmp_path)
    org_fixture(tmp_path, monkeypatch)
    baseline = state.desired_path.read_bytes()
    target = tmp_path / "workspaces/example-team/AGENTS.md"
    target.parent.mkdir(parents=True)
    target.write_text("custom original\n")
    original_save = state._save_observation

    def save(observation):
        if failure == "commit" and observation["transactions"][-1]["command"] == "enroll" and observation["transactions"][-1]["state"] == "committed":
            raise OSError("commit fixture")
        return original_save(observation)

    monkeypatch.setattr(state, "_save_observation", save)

    def engine(argv):
        if argv[0] == "enroll":
            from enrollment import EnrollmentJournal
            journal = EnrollmentJournal(Path(argv[argv.index("--enrollment-journal") + 1]))
            journal.capture(target)
            target.write_text("generated\n")
            return 1 if failure == "engine" else 0
        return 1 if failure == "doctor" else 0

    assert cli.main(["enroll", "--org-repo", REPOSITORY], state=state, engine_runner=engine) != 0
    assert target.read_text() == "custom original\n"
    assert state.desired_path.read_bytes() == baseline
    latest = state.read_observation()["transactions"][-1]
    assert latest["state"] == "aborted"
    assert latest["details"]["rollback"]["status"] == "restored"
    assert state.read_observation()["generation"] == 1


def test_skills_only_overlay_matches_runtime_and_schema(tmp_path):
    desired = contract.default_desired_state(
        "skills-only", ["codex"], "stable",
        organizations=[{
            "repository": REPOSITORY, "manifest_path": ".agents/onboarding.yaml",
            "commit_policy": "floating", "commit": "1" * 40,
            "mode": "additive", "workspace": "example-team",
        }],
        personal_instruction_source={"repository": str(tmp_path / "private"), "path": ".agents/instructions.md"},
    )
    assert contract.validate_desired_state(desired) == desired
    import jsonschema
    schema = json.loads((Path(__file__).parents[1] / "references/system-state.schema.json").read_text())
    jsonschema.validate(desired, schema)
    invalid = copy.deepcopy(desired)
    invalid["layers"]["agent-kernel"] = "selected"
    with pytest.raises(contract.ContractError):
        contract.validate_desired_state(invalid)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(invalid, schema)


@pytest.fixture
def box():
    value = Sandbox()
    # Use macOS's canonical temporary root; user-controlled symlinks remain
    # forbidden by the enrollment journal.
    for name in ("root", "home", "remotes", "cache"):
        setattr(value, name, getattr(value, name).resolve())
    yield value
    value.cleanup()


def engine_desired(box):
    manifest = box.manifest()
    manifest.write_text(manifest.read_text() + "\necosystem:\n  plugin: true\n  clients: [codex]\n  channel: stable\n")
    box._commit_all(manifest.parents[1], "fixture policy")
    commit = subprocess.check_output(["git", "-C", str(manifest.parents[1]), "rev-parse", "HEAD"], text=True).strip()
    desired = contract.default_desired_state("skills-only", ["codex"], "stable",
        organizations=[{"repository": REPOSITORY, "manifest_path": ".agents/onboarding.yaml",
            "commit_policy": "floating", "commit": commit, "mode": "additive", "workspace": "exampleco"}])
    path = box.root / "desired.json"
    contract.atomic_write_json(path, desired)
    return manifest, desired, path


def test_real_engine_enroll_and_repair_preserve_personal_files_and_receipts(box):
    from enrollment import EnrollmentJournal
    manifest, desired, path = engine_desired(box)
    state = contract.SystemState(home=box.home)
    receipt_path = box.home / ".synthesis/onboarding/receipts.json"
    original = {"version": 1, "profile": "custom", "personal_workspace": "independent",
        "component_choices": {"day-end": {"choice": "selected", "custom": "preserve"}},
        "layer_choices": {"agent-kernel": {"choice": "selected", "custom": "preserve"}},
        "generated_files": {}, "adoptions": {}}
    contract.atomic_write_json(receipt_path, original)
    sentinels = [box.home / p for p in (
        ".agents/AGENTS.md", ".claude/CLAUDE.md", ".synthesis/personal-policy/profile.json",
        ".synthesis/day-end/config.json", ".synthesis/agent-control/AGENTS.source.md")]
    for sentinel in sentinels:
        sentinel.parent.mkdir(parents=True, exist_ok=True)
        sentinel.write_bytes(b"custom personal bytes\n")
    # Unselected client copies are independent user data, including .codex.
    untouched = [box.home / p / "skills/example-skill/SKILL.md" for p in (".claude", ".codex")]
    for item in untouched:
        item.parent.mkdir(parents=True, exist_ok=True)
        item.write_text("independent client skill\n")
    pair = [box.home / "workspaces/exampleco" / n for n in ("AGENTS.md", "CLAUDE.md")]
    journal = EnrollmentJournal.create(state.state_dir / "enrollments", "a" * 32,
        contract.default_desired_state("skills-only", ["codex"], "stable"),
        files=[receipt_path, *pair], skill_parents=[box.home / ".agents/skills"], proposed=desired)
    binary = box.fake_client()
    box.seed_currency()
    extra = {"SYNTHESIS_CODEX_BIN": str(binary)}
    result = box.run_with_env(extra, "enroll", "--manifest", str(manifest), "--clients", "codex",
        "--desired-state", str(path), "--enrollment-journal", str(journal.root), "--json")
    assert result.returncode == 0, result.stdout + result.stderr
    for command in ("repair",):
        result = box.run_with_env(extra, command, "--manifest", str(manifest), "--clients", "codex",
            "--desired-state", str(path), "--json")
        assert result.returncode == 0, result.stdout + result.stderr
    receipt = json.loads(receipt_path.read_text())
    for key in ("profile", "personal_workspace", "component_choices", "layer_choices"):
        assert receipt[key] == original[key]
    assert all(s.read_bytes() == b"custom personal bytes\n" for s in sentinels)
    assert all(s.read_text() == "independent client skill\n" for s in untouched)
    assert (box.home / ".agents/skills/example-skill/SKILL.md").is_file()
    assert pair[0].read_bytes() == pair[1].read_bytes()
    result = box.run_with_env(extra, "uninstall", "--clients", "codex", "--json")
    assert result.returncode == 0, result.stdout + result.stderr
    assert not (box.home / ".agents/skills/example-skill").exists()
    assert all(s.read_bytes() == b"custom personal bytes\n" for s in sentinels)
    assert all(s.read_text() == "independent client skill\n" for s in untouched)


def test_organization_copy_never_retires_unselected_clients(box):
    source = box.root / "skills-source"
    (source / "skills/example-skill").mkdir(parents=True)
    (source / "skills/example-skill/SKILL.md").write_text("organization skill\n")
    for client in (".claude", ".codex"):
        target = box.home / client / "skills/example-skill"
        target.mkdir(parents=True)
        (target / "SKILL.md").write_text("personal sentinel\n")
    binary = box.root / "enabled-client"
    binary.write_text("#!/bin/sh\nprintf '%s\\n' '[{\"id\":\"synthesis-skills@synthesis-engineering\",\"name\":\"synthesis-skills\",\"enabled\":true}]'\n")
    binary.chmod(0o755)
    env = {**os.environ, **box.env_overrides(), "SYNTHESIS_SKILLS_SOURCE_DIR": str(source),
        "SYNTHESIS_SKILLS_HOME": str(box.home), "SYNTHESIS_SKILLS_SOURCE_TYPE": "organization",
        "SYNTHESIS_SKILLS_SOURCE_REPO": REPOSITORY, "SYNTHESIS_SKILLS_TARGETS": str(box.home / ".agents/skills"),
        "SYNTHESIS_CLAUDE_BIN": str(binary), "SYNTHESIS_CODEX_BIN": str(binary)}
    result = subprocess.run(["sh", str(Path(__file__).with_name("direct_copy.sh")), "install"], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    for client in (".claude", ".codex"):
        assert (box.home / client / "skills/example-skill/SKILL.md").read_text() == "personal sentinel\n"


@pytest.mark.parametrize("stage", ["pending", "desired-written", "committed"])
def test_interrupted_enrollment_recovers_only_uncommitted_generation(tmp_path, stage):
    from enrollment import EnrollmentJournal, recover_enrollments
    state, base = base_state(tmp_path)
    target = tmp_path / "workspaces/example-team/AGENTS.md"
    target.parent.mkdir(parents=True)
    target.write_text("original\n")
    proposed = {**base, "organizations": [{"repository": REPOSITORY,
        "manifest_path": ".agents/onboarding.yaml", "commit_policy": "floating",
        "commit": "1" * 40, "mode": "additive", "workspace": "example-team"}],
        "layers": {**base["layers"], "organization": "selected"}}
    observation = state.read_observation()
    tx = {**observation["transactions"][-1], "transaction_id": "b" * 32, "generation": 2,
        "command": "enroll", "desired_digest": contract.json_digest(proposed),
        "state": "committed" if stage == "committed" else "pending"}
    observation["transactions"].append(tx)
    if stage == "committed":
        observation["generation"] = 2
    state._save_observation(observation)
    journal = EnrollmentJournal.create(state.state_dir / "enrollments", tx["transaction_id"], base,
        files=[target, state.desired_path], skill_parents=[], proposed=proposed)
    journal.capture(state.desired_path)
    journal.capture(target)
    target.write_text("generated\n")
    if stage in {"desired-written", "committed"}:
        contract.atomic_write_json(state.desired_path, proposed)
    with state.locked():
        recover_enrollments(state)
    assert target.read_text() == ("generated\n" if stage == "committed" else "original\n")
    assert state.read_desired() == (proposed if stage == "committed" else base)
    with state.locked():
        recover_enrollments(state)


def test_recovery_refuses_corrupt_backup_and_broad_target(tmp_path):
    from enrollment import EnrollmentJournal, recover_enrollments
    state, base = base_state(tmp_path)
    target = tmp_path / "workspaces/example-team/AGENTS.md"
    target.parent.mkdir(parents=True)
    target.write_text("original\n")
    proposed = {**base, "organizations": [{"repository": REPOSITORY,
        "manifest_path": ".agents/onboarding.yaml", "commit_policy": "floating",
        "commit": "1" * 40, "mode": "additive", "workspace": "example-team"}],
        "layers": {**base["layers"], "organization": "selected"}}
    observation = state.read_observation()
    observation["transactions"].append({**observation["transactions"][-1],
        "transaction_id": "c" * 32, "generation": 2, "command": "enroll",
        "desired_digest": contract.json_digest(proposed), "state": "pending"})
    state._save_observation(observation)
    journal = EnrollmentJournal.create(state.state_dir / "enrollments", "c" * 32, base,
        files=[target], skill_parents=[], proposed=proposed)
    journal.capture(target)
    target.write_text("generated\n")
    backup = journal.root / "before/0"
    backup.write_text("corrupted backup\n")
    with state.locked(), pytest.raises(contract.ContractError, match="backup"):
        recover_enrollments(state)
    assert target.read_text() == "generated\n"
    journal.data["allowed_files"].append(str(tmp_path))
    journal._save()
    with state.locked(), pytest.raises(contract.ContractError, match="forbidden output"):
        recover_enrollments(state)
    assert target.exists()


def test_enroll_does_not_pull_or_reconfigure_adopted_kb(box, monkeypatch):
    manifest_path = box.manifest()
    manifest = cli.onboard.load_manifest(manifest_path)
    elsewhere = box.home / "workspaces/example-elsewhere" / manifest["knowledge_bases"][0]["name"]
    elsewhere.parent.mkdir(parents=True)
    env = {**os.environ, **box.env_overrides()}
    subprocess.run(["git", "clone", manifest["knowledge_bases"][0]["repository"], str(elsewhere)], env=env, capture_output=True, check=True)
    subprocess.run(["git", "-C", str(elsewhere), "config", "core.hooksPath", ".githooks"], env=env, check=True)
    for key, value in box.env_overrides().items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(cli.onboard, "WORKSPACES_ROOT", box.home / "workspaces")
    monkeypatch.setattr(cli.onboard, "find_adoptable", lambda *a: elsewhere)
    receipts = cli.onboard.Receipts(box.root / "receipts.json")
    report = cli.onboard.Report(as_json=True)
    calls = []
    original_git = cli.onboard.git
    def git(args, **kwargs):
        calls.append(args)
        if args[0] == "pull" or (args[0] == "config" and "--get" not in args):
            pytest.fail("existing knowledge repository was mutated")
        return original_git(args, **kwargs)
    monkeypatch.setattr(cli.onboard, "git", git)
    cli.onboard.phase_kbs(report, manifest, receipts, False, enrolling=True)
    assert report.exit_code() == 0
    assert receipts.adopted(manifest["knowledge_bases"][0]["name"]) == str(elsewhere)


def test_workspace_dry_run_validates_dirty_source_without_creating_outputs(box):
    manifest = box.manifest()
    source = manifest.parent / "workspace-instructions.md"
    source.write_text(source.read_text() + "\nUncommitted source.\n")
    proc = box.run_engine("install", "--manifest", str(manifest), "--dry-run", "--json")
    assert proc.returncode != 0, proc.stdout
    assert not (box.home / "workspaces/exampleco/AGENTS.md").exists()


def test_completed_journal_does_not_constrain_later_client_selection(tmp_path):
    from enrollment import EnrollmentJournal, recover_enrollments
    state, base = base_state(tmp_path)
    journal = EnrollmentJournal.create(state.state_dir / "enrollments", "d" * 32, base,
        files=[], skill_parents=[tmp_path / ".agents/skills"])
    journal.commit()
    state.run_transaction("setup", {**base, "clients": ["claude"]}, lambda tx: {})
    with state.locked():
        recover_enrollments(state)


@pytest.mark.parametrize("command", ["update", "repair"])
def test_organization_replay_preserves_colliding_private_skill(box, command):
    manifest = box.manifest()
    box.run_engine("install", "--manifest", str(manifest), expect=0)
    target = box.home / ".agents/skills/example-skill"
    (target / "SKILL.md").write_text("private replacement\n")
    (target / ".source.json").write_text(json.dumps({"source_type": "private", "source_repo": "private"}))
    result = box.run_engine(command, "--manifest", str(manifest), "--json")
    assert result.returncode != 0
    assert (target / "SKILL.md").read_text() == "private replacement\n"


def test_organization_removed_skill_is_receipted_through_retirement(box):
    manifest = box.manifest()
    box.run_engine("install", "--manifest", str(manifest), expect=0)
    source = box.root / "skills-src"
    subprocess.run(["git", "-C", str(source), "mv", "skills/example-skill", "skills/renamed-skill"], env=box.git_env, check=True)
    box._commit_all(source, "fixture rename")
    subprocess.run(["git", "-C", str(source), "push", str(box.skills_remote), "main"], env=box.git_env, capture_output=True, check=True)
    box.run_engine("update", "--manifest", str(manifest), expect=0)
    for client in (".claude", ".agents"):
        assert not (box.home / client / "skills/example-skill").exists()
        assert (box.home / client / "skills/renamed-skill/SKILL.md").exists()


def test_enroll_invite_is_reusable_after_abort_but_not_after_commit(tmp_path, monkeypatch):
    state, _ = base_state(tmp_path)
    org_fixture(tmp_path, monkeypatch)
    now = datetime.now(timezone.utc)
    invite = {"schema_version": 1, "repository": REPOSITORY, "provider": "generic",
        "manifest_path": ".agents/onboarding.yaml", "nonce": "enrollment_nonce_0123456789",
        "issued_at": (now - timedelta(minutes=1)).isoformat(),
        "expires_at": (now + timedelta(hours=1)).isoformat()}
    path = tmp_path / "invite.json"
    path.write_text(json.dumps(invite))
    args = ["enroll", "--invite", str(path)]
    assert cli.main(args, state=state, engine_runner=lambda a: 1) == 1
    assert not state.invites_path.exists()
    assert cli.main(args, state=state, engine_runner=lambda a: 0) == 0
    consumed = state.invites_path.read_bytes()
    assert cli.main(args, state=state, engine_runner=lambda a: pytest.fail("consumed invite reached engine")) == 2
    assert state.invites_path.read_bytes() == consumed


def test_pending_enrollment_keeps_doctor_non_green_without_writes(tmp_path, monkeypatch):
    from enrollment import EnrollmentJournal
    state, base = base_state(tmp_path)
    journal = EnrollmentJournal.create(state.state_dir / "enrollments", "f" * 32, base, files=[], skill_parents=[])
    before = journal.path.read_bytes()
    desired = state.desired_path.read_bytes()
    assert cli.main(["doctor"], state=state, engine_runner=lambda a: pytest.fail("unsettled engine ran")) == 2
    assert journal.path.read_bytes() == before
    assert state.desired_path.read_bytes() == desired


@pytest.mark.parametrize("directory", [False, True])
def test_cross_device_enrollment_rollback_preserves_bytes(tmp_path, monkeypatch, directory):
    import enrollment
    state, base = base_state(tmp_path)
    target = tmp_path / ".agents/skills/example-skill" if directory else tmp_path / "workspaces/example-team/AGENTS.md"
    target.parent.mkdir(parents=True)
    if directory:
        target.mkdir()
        payload = target / "SKILL.md"
    else:
        payload = target
    payload.write_text("original bytes\n")
    journal = enrollment.EnrollmentJournal.create(state.state_dir / "enrollments", "e" * 32, base,
        files=[] if directory else [target], skill_parents=[target.parent] if directory else [])
    journal.capture(target)
    payload.write_text("failed generation\n")
    real_replace = os.replace
    def replace(source, destination):
        if Path(source) == target:
            raise OSError(errno.EXDEV, "cross-device fixture")
        return real_replace(source, destination)
    monkeypatch.setattr(enrollment.os, "replace", replace)
    journal.rollback()
    assert payload.read_text() == "original bytes\n"
    archived = journal.root / "failed/0"
    assert (archived / "SKILL.md" if directory else archived).read_text() == "failed generation\n"


def test_uninstall_preserves_edited_organization_skill_and_reports_non_green(box):
    manifest = box.manifest()
    box.run_engine("install", "--manifest", str(manifest), expect=0)
    path = box.home / ".agents/skills/example-skill/SKILL.md"
    path.write_text("edited organization skill\n")
    result = box.run_engine("uninstall", "--clients", "codex", "--json")
    assert result.returncode != 0
    assert path.read_text() == "edited organization skill\n"
    assert not any(s.get("uninstall_verified") for s in json.loads(result.stdout)["steps"])


def test_enrollment_journal_refuses_another_workspace_even_when_claimed(tmp_path):
    from enrollment import EnrollmentJournal
    state, base = base_state(tmp_path)
    proposed = {**base, "organizations": [{"repository": REPOSITORY,
        "manifest_path": ".agents/onboarding.yaml", "commit_policy": "floating",
        "commit": "1" * 40, "mode": "additive", "workspace": "example-team"}],
        "layers": {**base["layers"], "organization": "selected"}}
    journal = EnrollmentJournal.create(state.state_dir / "enrollments", "0" * 32, base,
        files=[tmp_path / "workspaces/example-unrelated/AGENTS.md"], skill_parents=[], proposed=proposed)
    with pytest.raises(contract.ContractError, match="forbidden output"):
        journal.validate_scope(state, base)


def test_removing_entire_org_source_retires_exact_owned_inventory(box):
    import yaml
    manifest = box.manifest()
    box.run_engine("install", "--manifest", str(manifest), expect=0)
    data = yaml.safe_load(manifest.read_text())
    data["skills_repos"] = []
    manifest.write_text(yaml.safe_dump(data))
    box._commit_all(manifest.parents[1], "fixture removal")
    before = box.run_engine("doctor", "--manifest", str(manifest), "--json")
    assert before.returncode != 0
    box.run_engine("update", "--manifest", str(manifest), expect=0)
    for client in (".claude", ".agents"):
        assert not (box.home / client / "skills/example-skill").exists()


@pytest.mark.parametrize("edited", [False, True])
def test_legacy_org_copy_adoption_verifies_recorded_source_bytes(box, edited):
    manifest = box.manifest()
    box.run_engine("install", "--manifest", str(manifest), expect=0)
    receipts_path = box.home / ".synthesis/onboarding/receipts.json"
    receipts = json.loads(receipts_path.read_text())
    receipts.pop("org_skill_copies")
    receipts_path.write_text(json.dumps(receipts))
    target = box.home / ".agents/skills/example-skill/SKILL.md"
    if edited:
        target.write_text("unreceipted personal addition\n")
    result = box.run_engine("update", "--manifest", str(manifest), "--json")
    assert result.returncode == (1 if edited else 0), result.stdout
    if edited:
        assert target.read_text() == "unreceipted personal addition\n"
    else:
        assert str(target.parent) in json.loads(receipts_path.read_text())["org_skill_copies"]


@pytest.mark.parametrize("edited", [False, True])
def test_flat_shared_repository_adoption_proves_source_bytes(box, edited):
    import shutil
    source = box.root / "skills-src"
    subprocess.run(["git", "-C", str(source), "mv", "skills/example-skill", "example-skill"],
        env=box.git_env, check=True)
    box._commit_all(source, "fixture layout")
    subprocess.run(["git", "-C", str(source), "push", str(box.skills_remote), "main"],
        env=box.git_env, capture_output=True, check=True)
    commit = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    for client in (".claude", ".agents"):
        target = box.home / client / "skills/example-skill"
        target.parent.mkdir(parents=True)
        shutil.copytree(source / "example-skill", target)
        (target / ".source.json").write_text(json.dumps({"source_type": "shared",
            "source_repo": "fixture/example-shared-skills", "source_path": "example-skill/SKILL.md",
            "source_commit": commit, "installed_by": "install.sh"}))
        if edited:
            (target / "SKILL.md").write_text("personal modification\n")
    manifest = box.manifest()
    result = box.run_engine("install", "--manifest", str(manifest), "--json")
    assert result.returncode == (1 if edited else 0), result.stdout + result.stderr
    for client in (".claude", ".agents"):
        target = box.home / client / "skills/example-skill"
        if edited:
            assert (target / "SKILL.md").read_text() == "personal modification\n"
        else:
            receipt = json.loads((box.home / ".synthesis/onboarding/receipts.json").read_text())
            assert receipt["org_skill_copies"][str(target)]["repository"] == box.skills_url
    if not edited:
        box.run_engine("repair", "--manifest", str(manifest), expect=0)
        box.run_engine("uninstall", expect=0)
        assert not (box.home / ".agents/skills/example-skill").exists()


def test_organization_source_identity_keeps_host_path_and_nondefault_port():
    identity = cli.onboard.organization_source_identity
    assert identity("git@example.test:team/config.git") == identity("example.test/team/config")
    assert identity("ssh://git@example.test:22/team/config.git") == identity("https://example.test/team/config.git")
    assert identity("ssh://git@example.test:222/team/config.git") != identity("example.test/team/config")
    assert identity("other.test/team/config") != identity("example.test/team/config")
    assert identity("example.test/other/config") != identity("example.test/team/config")


def test_mixed_organization_skill_layout_refuses_before_copies(box):
    source = box.root / "skills-src"
    (source / "other-skill").mkdir()
    (source / "other-skill/SKILL.md").write_text("ambiguous second layout\n")
    box._commit_all(source, "fixture ambiguity")
    subprocess.run(["git", "-C", str(source), "push", str(box.skills_remote), "main"],
        env=box.git_env, capture_output=True, check=True)
    manifest = box.manifest()
    result = box.run_engine("install", "--manifest", str(manifest), "--json")
    assert result.returncode != 0
    assert not (box.home / ".agents/skills/example-skill").exists()
    assert not (box.home / ".agents/skills/other-skill").exists()


def test_two_org_sources_cannot_own_the_same_skill_target(box):
    import yaml
    manifest = box.manifest()
    box.run_engine("install", "--manifest", str(manifest), expect=0)
    second = box.remotes / "second-skills.git"
    subprocess.run(["git", "clone", "--bare", str(box.skills_remote), str(second)], env=box.git_env, capture_output=True, check=True)
    data = yaml.safe_load(manifest.read_text())
    data["skills_repos"].append({"name": "second-skills", "repository": "ssh://fixture/second-skills.git", "capability": "skills-install"})
    manifest.write_text(yaml.safe_dump(data))
    box._commit_all(manifest.parents[1], "fixture collision")
    target = box.home / ".agents/skills/example-skill/.source.json"
    before = target.read_bytes()
    result = box.run_engine("update", "--manifest", str(manifest), "--json")
    assert result.returncode != 0
    assert target.read_bytes() == before


@pytest.mark.parametrize("state_layout", ["override", "default", "xdg"])
def test_real_cli_enroll_reaches_engine_and_preserves_personal_state(box, state_layout):
    manifest, desired, _ = engine_desired(box)
    remote = box.remotes / "config.git"
    subprocess.run(["git", "clone", "--bare", str(manifest.parents[1]), str(remote)],
        env=box.git_env, capture_output=True, check=True)
    state, base = base_state(box.home)
    sentinel = box.home / ".synthesis/agent-control/AGENTS.source.md"
    sentinel.parent.mkdir(parents=True)
    sentinel.write_text("independent personal kernel\n")
    binary = box.fake_client()
    box.seed_currency()
    env = {**os.environ, **box.env_overrides(), "SYNTHESIS_HOME": str(box.home),
        "SYNTHESIS_CODEX_BIN": str(binary)}
    env.pop("XDG_STATE_HOME", None)
    if state_layout != "override":
        env.pop("SYNTHESIS_ONBOARD_STATE_DIR", None)
    if state_layout == "xdg":
        env["XDG_STATE_HOME"] = str(box.home / "xdg-state")
    # Keep the production SSH-only transport policy. A fixture SSH process
    # serves the real local bare repository through git-upload-pack.
    ssh = box.root / "fixture_ssh.py"
    ssh.write_text("import os, shlex, sys\nfrom pathlib import Path\n"
        "command = shlex.split(sys.argv[-1])\n"
        "assert command[0] == 'git-upload-pack'\n"
        "repository = Path(%r) / Path(command[1]).name\n"
        "assert repository.is_dir()\n"
        "os.execvp('git-upload-pack', ['git-upload-pack', str(repository)])\n" % str(box.remotes))
    env.update({"GIT_SSH_COMMAND": "%s %s" % (sys.executable, ssh), "GIT_SSH_VARIANT": "ssh"})
    env["GIT_ALLOW_PROTOCOL"] = "https:ssh"
    env["GIT_PROTOCOL_FROM_USER"] = "0"
    # All three real organization repositories use the SSH fixture process;
    # no local-transport rewrite bypasses the verified CLI's allowlist.
    for name in list(env):
        if name == "GIT_CONFIG_COUNT" or name.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_")):
            env.pop(name)
    for name in ("SYNTHESIS_ACTIVE_DESCRIPTOR", "SYNTHESIS_RELEASE_ROOT"):
        env.pop(name, None)
    result = subprocess.run([sys.executable, str(Path(cli.__file__)), "enroll", "--org-repo",
        "ssh://fixture/config.git", "--json"], env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    enrolled = state.read_desired()
    assert enrolled["organizations"][0]["mode"] == "additive"
    for key in ("profile", "personal_workspace", "personal_configuration", "clients", "release"):
        assert enrolled[key] == base[key]
    assert sentinel.read_text() == "independent personal kernel\n"
    assert (box.home / ".agents/skills/example-skill/SKILL.md").exists()
    assert not (box.home / ".claude/skills/example-skill").exists()
    engine_root = Path(env.get("SYNTHESIS_ONBOARD_STATE_DIR",
        str(Path(env.get("XDG_STATE_HOME", str(box.home / ".local/state"))) / "synthesis")))
    assert (engine_root / "receipts.json").is_file()
    journals_root = Path(env.get("XDG_STATE_HOME", str(box.home / ".local/state"))) / "synthesis/enrollments"
    journal = json.loads(next(journals_root.glob("*/journal.json")).read_text())
    assert str(engine_root / "receipts.json") in journal["allowed_files"]
    assert journal["state"] == "committed"


def test_read_only_engine_lock_never_creates_state(tmp_path):
    from enrollment import engine_lock
    root = tmp_path / "missing-state"
    with engine_lock(root, read_only=True):
        assert not root.exists()
    assert not root.exists()


@pytest.mark.parametrize("state_layout", ["override", "default", "xdg"])
def test_enrollment_rollback_protects_actual_engine_receipt(tmp_path, monkeypatch, state_layout):
    monkeypatch.delenv("SYNTHESIS_ONBOARD_STATE_DIR", raising=False)
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    expected_root = tmp_path / ".local/state/synthesis"
    if state_layout == "override":
        expected_root = tmp_path / "explicit-engine-state"
        monkeypatch.setenv("SYNTHESIS_ONBOARD_STATE_DIR", str(expected_root))
    elif state_layout == "xdg":
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg-state"))
        expected_root = tmp_path / "xdg-state/synthesis"
    state, base = base_state(tmp_path)
    org_fixture(tmp_path, monkeypatch)
    receipt = expected_root / "receipts.json"
    legacy = tmp_path / ".synthesis/onboarding/receipts.json"
    for path in (receipt, legacy):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"personal": "unchanged"}\n')
    before = receipt.read_bytes()

    def engine(argv):
        if argv[0] == "enroll":
            receipt.write_text('{"changed": true}\n')
            return 0
        return 1

    assert cli.main(["enroll", "--org-repo", REPOSITORY], state=state, engine_runner=engine) == 1
    assert receipt.read_bytes() == before
    assert legacy.read_bytes() == before
    assert state.read_desired() == base


def advance_skill_source(box):
    source = box.root / "skills-src"
    payload = source / "skills/example-skill/SKILL.md"
    payload.write_text(payload.read_text() + "\nNew organization guidance.\n")
    box._commit_all(source, "fixture update")
    subprocess.run(["git", "-C", str(source), "push", str(box.skills_remote), "main"],
        env=box.git_env, capture_output=True, check=True)


def test_failed_later_phase_keeps_copied_skills_repairable(box):
    manifest = box.manifest()
    box.run_engine("install", "--manifest", str(manifest), expect=0)
    advance_skill_source(box)
    source = manifest.parent / "workspace-instructions.md"
    original = source.read_bytes()
    source.write_bytes(original + b"\nUncommitted instruction source.\n")
    result = box.run_engine("update", "--manifest", str(manifest), "--json")
    assert result.returncode == 1, result.stdout
    target = box.home / ".agents/skills/example-skill"
    assert "New organization guidance" in (target / "SKILL.md").read_text()
    receipts = json.loads((box.home / ".synthesis/onboarding/receipts.json").read_text())
    assert receipts["org_skill_copies"][str(target)]["sha256"] == cli.onboard.paths_digest([target])
    source.write_bytes(original)
    box.run_engine("repair", "--manifest", str(manifest), expect=0)


def test_partial_organization_copy_restores_exact_receipts_and_skill_bytes(box, monkeypatch):
    from enrollment import EnrollmentJournal
    manifest = box.manifest()
    box.run_engine("install", "--manifest", str(manifest), expect=0)
    advance_skill_source(box)
    engine = cli.onboard
    for key, value in box.env_overrides().items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(engine, "HOME", box.home)
    monkeypatch.setattr(engine, "STATE_DIR", box.home / ".synthesis/onboarding")
    monkeypatch.setattr(engine, "CACHE_DIR", box.cache / "synthesis-onboarding")
    receipt_path = box.home / ".synthesis/onboarding/receipts.json"
    before = receipt_path.read_bytes()
    target = box.home / ".agents/skills/example-skill"
    fingerprint = EnrollmentJournal._fingerprint(target)
    run = engine.run
    injected = []
    def fail_copy(args, **kwargs):
        if args[0] == "sh" and args[-1] == "install":
            injected.append(True)
            (target / "SKILL.md").write_text("interrupted copy\n")
            return 1, "", "injected partial copy"
        return run(args, **kwargs)
    monkeypatch.setattr(engine, "run", fail_copy)
    report = engine.Report(as_json=True)
    engine.phase_org_skills(report, engine.load_manifest(manifest), engine.Receipts(receipt_path), False)
    assert injected and report.exit_code() != 0
    assert receipt_path.read_bytes() == before
    assert EnrollmentJournal._fingerprint(target) == fingerprint


def test_nested_copy_recovery_precedes_outer_enrollment_rollback(tmp_path, monkeypatch):
    from enrollment import EnrollmentJournal, recover_copy_transactions
    monkeypatch.setenv("SYNTHESIS_ONBOARD_STATE_DIR", str(tmp_path / ".synthesis/onboarding"))
    state, base = base_state(tmp_path)
    receipt = tmp_path / ".synthesis/onboarding/receipts.json"
    target = tmp_path / ".agents/skills/example-skill"
    target.mkdir(parents=True)
    (target / "SKILL.md").write_text("original skill\n")
    contract.atomic_write_json(receipt, {"generation": 0})
    original_receipt = receipt.read_bytes()
    proposed = {**base, "organizations": [{"repository": REPOSITORY,
        "manifest_path": ".agents/onboarding.yaml", "commit_policy": "floating",
        "commit": "1" * 40, "mode": "additive", "workspace": "example-team"}],
        "layers": {**base["layers"], "organization": "selected"}}
    observation = state.read_observation()
    tx = {**observation["transactions"][-1], "transaction_id": "1" * 32, "generation": 2,
        "command": "enroll", "desired_digest": contract.json_digest(proposed), "state": "pending"}
    observation["transactions"].append(tx)
    state._save_observation(observation)
    outer = EnrollmentJournal.create(state.state_dir / "enrollments", tx["transaction_id"], base,
        files=[receipt], skill_parents=[target.parent], proposed=proposed)
    outer.capture(receipt)
    outer.capture(target)
    contract.atomic_write_json(receipt, {"generation": 1})
    (target / "SKILL.md").write_text("intermediate skill\n")
    inner = EnrollmentJournal.create(receipt.parent / "copy-transactions", "2" * 32, None,
        files=[receipt], skill_parents=[target.parent], purpose="org-copy")
    inner.capture(receipt)
    inner.capture(target)
    (target / "SKILL.md").write_text("partial second copy\n")
    monkeypatch.setattr(cli, "_active_release", lambda: None)
    assert cli.main(["repair"], state=state, engine_runner=lambda a: 0) == 0
    assert receipt.read_bytes() == original_receipt
    assert (target / "SKILL.md").read_text() == "original skill\n"
    assert EnrollmentJournal(inner.root).data["state"] == "rolled-back"
    assert EnrollmentJournal(outer.root).data["state"] == "rolled-back"
    recover_copy_transactions(receipt.parent, tmp_path)
    assert receipt.read_bytes() == original_receipt


@pytest.mark.parametrize("backup_failure", [False, True])
def test_empty_copy_journal_recovers_before_any_target_mutation(tmp_path, monkeypatch, backup_failure):
    import enrollment
    receipt = tmp_path / ".synthesis/onboarding/receipts.json"
    contract.atomic_write_json(receipt, {"generation": 0})
    before = receipt.read_bytes()
    if backup_failure:
        monkeypatch.setattr(enrollment.shutil, "copy2", lambda *a, **k: (_ for _ in ()).throw(OSError("backup fixture")))
        with pytest.raises(OSError):
            with enrollment.organization_copy_transaction(cli.onboard.Receipts(receipt), [], tmp_path):
                pytest.fail("copy body ran without receipt backup")
    else:
        enrollment.EnrollmentJournal.create(receipt.parent / "copy-transactions", "4" * 32, None,
            files=[receipt], skill_parents=[], purpose="org-copy")
    enrollment.recover_copy_transactions(receipt.parent, tmp_path)
    assert receipt.read_bytes() == before
    journals = [p for p in (receipt.parent / "copy-transactions").iterdir() if p.name != ".staging"]
    assert len(journals) == 1
    assert enrollment.EnrollmentJournal(journals[0]).data["state"] == "rolled-back"


def test_journal_creation_publishes_only_complete_identity(tmp_path, monkeypatch):
    import enrollment
    parent = tmp_path / ".synthesis/onboarding/copy-transactions"
    root = parent / ("5" * 32)
    def interrupted_write(path, data):
        assert not root.exists()
        assert path.parent.parent == parent / ".staging"
        raise OSError("publication fixture")
    monkeypatch.setattr(enrollment, "atomic_write_json", interrupted_write)
    with pytest.raises(OSError):
        enrollment.EnrollmentJournal.create(parent, root.name, None,
            files=[parent.parent / "receipts.json"], skill_parents=[], purpose="org-copy")
    assert not root.exists()
    # An interrupted pre-publication directory never issued target authority.
    (parent / ".staging/interrupted-fixture").mkdir()
    enrollment.recover_copy_transactions(parent.parent, tmp_path)


def test_copy_journal_diagnostic_is_read_only_and_recovery_is_bound(tmp_path):
    from enrollment import EnrollmentJournal, recover_copy_transactions
    receipt = tmp_path / ".synthesis/onboarding/receipts.json"
    contract.atomic_write_json(receipt, {"generation": 0})
    journal = EnrollmentJournal.create(receipt.parent / "copy-transactions", "3" * 32, None,
        files=[receipt], skill_parents=[], purpose="org-copy")
    journal.capture(receipt)
    before = journal.path.read_bytes()
    with pytest.raises(contract.ContractError, match="unfinished"):
        recover_copy_transactions(receipt.parent, tmp_path, verify_only=True)
    assert journal.path.read_bytes() == before
    contract.atomic_write_json(receipt, {"unrelated": True})
    with pytest.raises(contract.ContractError, match="outside its transaction"):
        recover_copy_transactions(receipt.parent, tmp_path)
    assert json.loads(receipt.read_text()) == {"unrelated": True}


def test_repair_restores_recorded_org_commit_without_fetch_or_personal_setup(tmp_path):
    from test_synthesis_cli import commit_fixture_repo
    root = tmp_path / "organizations/config"
    manifest = root / ".agents/onboarding.yaml"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("version: 2\n")
    commit_fixture_repo(root)
    original = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    manifest.write_text("version: 2\n# incompatible newer policy\n")
    commit_fixture_repo(root)
    newer = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    subprocess.run(["git", "-C", str(root), "remote", "add", "origin", REPOSITORY], check=True)
    subprocess.run(["git", "-C", str(root), "update-ref", "refs/remotes/origin/main", newer], check=True)
    with pytest.raises(contract.ContractError):
        cli.organization.acquire_repository(REPOSITORY, tmp_path, expected_commit=original, refresh=False)
    assert subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip() == newer
    resolved, commit = cli.organization.acquire_repository(REPOSITORY, tmp_path,
        expected_commit=original, refresh=False, restore_commit=True)
    assert resolved == root and commit == original
    assert cli.organization.acquire_repository(REPOSITORY, tmp_path, expected_commit=original, refresh=False)[1] == original

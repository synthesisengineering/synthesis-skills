#!/usr/bin/env python3
"""Behavioral contract tests for the next-generation onboarding substrate."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker, ValidationError


SCRIPTS = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS.parents[2]
sys.path.insert(0, str(SCRIPTS))

import system_contract  # noqa: E402


def git(path: Path, *args: str) -> str:
    env = dict(os.environ)
    env.update(
        {
            "GIT_AUTHOR_NAME": "Fixture",
            "GIT_AUTHOR_EMAIL": "fixture@example.test",
            "GIT_COMMITTER_NAME": "Fixture",
            "GIT_COMMITTER_EMAIL": "fixture@example.test",
            "GIT_CONFIG_NOSYSTEM": "1",
        }
    )
    proc = subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", "-C", str(path), *args],
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode:
        raise AssertionError(proc.stderr)
    return proc.stdout.strip()


def release_repo(tmp_path: Path, version: str = "9.8.7") -> Path:
    root = tmp_path / "release"
    (root / ".claude-plugin").mkdir(parents=True)
    (root / ".codex-plugin").mkdir()
    (root / "skills" / "synthesis-onboarding" / "scripts").mkdir(parents=True)
    manifest = json.dumps({"name": "synthesis-skills", "version": version}) + "\n"
    (root / ".claude-plugin" / "plugin.json").write_text(manifest, encoding="utf-8")
    (root / ".codex-plugin" / "plugin.json").write_text(manifest, encoding="utf-8")
    (root / "skills" / "synthesis-onboarding" / "scripts" / "synthesis_cli.py").write_text(
        "import os\nprint(os.environ.get('SYNTHESIS_ACTIVE_DESCRIPTOR', 'missing'))\n",
        encoding="utf-8",
    )
    git(root, "init", "-q", "-b", "main")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "fixture")
    git(root, "branch", "stable")
    git(root, "tag", "v%s" % version)
    return root


def live_receipt(tmp_path: Path, client: str, version: str = "9.8.7") -> dict:
    root = tmp_path / ("%s-%s-plugin" % (client, version))
    (root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    (root / ".codex-plugin").mkdir(exist_ok=True)
    (root / "hooks").mkdir(exist_ok=True)
    manifest = json.dumps({"name": "synthesis-skills", "version": version}) + "\n"
    (root / ".claude-plugin" / "plugin.json").write_text(manifest, encoding="utf-8")
    (root / ".codex-plugin" / "plugin.json").write_text(manifest, encoding="utf-8")
    (root / "hooks" / "hooks.json").write_text(
        json.dumps({"hooks": {"SessionStart": [{"command": "fixture"}]}}) + "\n",
        encoding="utf-8",
    )
    session_id = str(uuid.uuid4())
    transcript = root / (client + ".jsonl")
    transcript.write_text(json.dumps({"session_id": session_id}) + "\n", encoding="utf-8")
    return {
        "receipt_schema": 2,
        "receipt_event_id": str(uuid.uuid4()),
        "hook_event_name": "SessionStart",
        "session_id": session_id,
        "client": client,
        "transcript_path": str(transcript),
        "transcript_bound_at_record": True,
        "provenance_env": "%s-transcript" % client,
        "plugin_version": version,
        "plugin_root": str(root.resolve()),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }


def release_record(root: Path, version: str = "9.8.7") -> dict:
    return {
        "schema_version": 1,
        "version": version,
        "channel": "pin",
        "ref": "v%s" % version,
        "commit": "1" * 40,
        "tree": "2" * 40,
        "content_digest": system_contract.canonical_tree_digest(root),
        "digest_algorithm": system_contract.DIGEST_ALGORITHM,
        "tree_policy": system_contract.TREE_POLICY,
        "source_url": "https://example.test/synthesis-skills.git",
        "resolved_at": datetime.now(timezone.utc).isoformat(),
    }


def test_shipped_contract_documents_are_valid() -> None:
    contracts = system_contract.load_contract_documents(REPO_ROOT)
    assert contracts["capabilities"]["cli"]["name"] == "synthesis"
    assert contracts["capabilities"]["truth_planes"] == list(
        system_contract.TRUTH_PLANES
    )
    observation_properties = contracts["observation"]["properties"]["transactions"]["items"]["properties"]
    assert set(system_contract.TRUTH_PLANES) <= set(observation_properties)
    for document in contracts.values():
        if "$schema" in document:
            Draft202012Validator.check_schema(document)


def test_json_schemas_and_runtime_share_valid_and_invalid_corpora(
    tmp_path: Path,
) -> None:
    contracts = system_contract.load_contract_documents(REPO_ROOT)

    desired = system_contract.default_desired_state(
        "skills-only", ["codex"], "stable"
    )
    Draft202012Validator(contracts["desired"]).validate(desired)
    system_contract.validate_desired_state(desired)
    invalid_desired = dict(desired)
    invalid_desired["clients"] = []
    with pytest.raises(ValidationError):
        Draft202012Validator(contracts["desired"]).validate(invalid_desired)
    with pytest.raises(system_contract.ContractError):
        system_contract.validate_desired_state(invalid_desired)

    full_configuration = {
        "display_name": "Example User",
        "working_relationship": "direct collaborator",
        "timezone": "UTC",
        "tone": ["direct"],
        "avoid_phrases": [],
        "git_name": "",
        "git_email": "",
        "working_hours": None,
        "protected_hours": [],
        "personal_remote_patterns": [],
        "confidential_terms": [],
        "inbox_cleanup": False,
    }
    valid_full = system_contract.default_desired_state(
        "full",
        ["codex"],
        "stable",
        personal_workspace="example-user",
        personal_configuration=full_configuration,
    )
    desired_validator = Draft202012Validator(contracts["desired"])
    desired_validator.validate(valid_full)
    system_contract.validate_desired_state(valid_full)
    invalid_state_shapes = [
        system_contract.default_desired_state("full", ["codex"], "stable"),
        {**desired, "layers": {}},
        {**desired, "layers": {**desired["layers"], "unknown": "declined"}},
        {
            **valid_full,
            "organizations": [
                {
                    "repository": "https://example.test/org/one.git",
                    "manifest_path": ".agents/onboarding.yaml",
                    "commit_policy": "pinned",
                    "commit": "1" * 40,
                },
                {
                    "repository": "https://example.test/org/two.git",
                    "manifest_path": ".agents/onboarding.yaml",
                    "commit_policy": "pinned",
                    "commit": "2" * 40,
                },
            ],
        },
    ]
    for invalid in invalid_state_shapes:
        with pytest.raises(ValidationError):
            desired_validator.validate(invalid)
        with pytest.raises(system_contract.ContractError):
            system_contract.validate_desired_state(invalid)

    source = tmp_path / "source"
    source.mkdir()
    (source / "instructions.md").write_text("Use grounded evidence.\n", encoding="utf-8")
    git(source, "init", "-q", "-b", "main")
    git(source, "add", "-A")
    git(source, "commit", "-q", "-m", "fixture")
    graph = {
        "schema_version": 1,
        "sources": [
            {"role": "personal", "path": "instructions.md", "required": True}
        ],
        "output": "AGENTS.md",
        "claude_adapter": "CLAUDE.md",
    }
    instruction_validator = Draft202012Validator(contracts["instructions"])
    instruction_validator.validate(graph)
    system_contract.materialize_instruction_pair(
        graph, {"personal": source}, tmp_path / "workspace", generation=1
    )
    invalid_graphs = []
    missing_adapter = dict(graph)
    missing_adapter.pop("claude_adapter")
    invalid_graphs.append(missing_adapter)
    invalid_graphs.append(
        {
            **graph,
            "sources": [
                {"role": "personal", "path": "../escape", "required": False}
            ],
        }
    )
    invalid_graphs.append(
        {
            **graph,
            "sources": [
                {"role": "personal", "path": "one", "required": False},
                {"role": "personal", "path": "two", "required": False},
            ],
        }
    )
    for index, invalid in enumerate(invalid_graphs):
        with pytest.raises(ValidationError):
            instruction_validator.validate(invalid)
        with pytest.raises(system_contract.ContractError):
            system_contract.materialize_instruction_pair(
                invalid, {}, tmp_path / ("invalid-workspace-%d" % index), generation=1
            )

    release_root = tmp_path / "release-content"
    release_root.mkdir()
    release = release_record(release_root)
    release_validator = Draft202012Validator(
        contracts["release"], format_checker=FormatChecker()
    )
    release_validator.validate(release)
    system_contract.validate_release_descriptor(release)
    for changed in (
        {**release, "source_url": "ssh://git@example.test/synthesis-skills.git"},
        {**release, "channel": "edge", "ref": "stable"},
    ):
        with pytest.raises(ValidationError):
            release_validator.validate(changed)
        with pytest.raises(system_contract.ContractError):
            system_contract.validate_release_descriptor(changed)

    now = datetime.now(timezone.utc)
    invite = {
        "schema_version": 1,
        "repository": "https://example.test/org/config.git",
        "provider": "generic",
        "manifest_path": ".agents/onboarding.yaml",
        "nonce": "fixture_nonce_0123456789",
        "issued_at": (now - timedelta(minutes=1)).isoformat(),
        "expires_at": (now + timedelta(minutes=10)).isoformat(),
    }
    invite_validator = Draft202012Validator(
        contracts["invite"], format_checker=FormatChecker()
    )
    invite_validator.validate(invite)
    system_contract.validate_invite(invite, now=now)
    invalid_invite = {key: value for key, value in invite.items() if key != "nonce"}
    with pytest.raises(ValidationError):
        invite_validator.validate(invalid_invite)
    with pytest.raises(system_contract.ContractError):
        system_contract.validate_invite(invalid_invite, now=now)


def test_persisted_state_readers_enforce_closed_runtime_schemas(tmp_path: Path) -> None:
    state = system_contract.SystemState(tmp_path)
    state.desired_path.parent.mkdir(parents=True)
    state.desired_path.write_text('{"schema_version": 1}\n', encoding="utf-8")
    with pytest.raises(system_contract.ContractError, match="missing keys"):
        state.read_desired()
    desired = system_contract.default_desired_state("skills-only", ["codex"], "stable")
    desired["unexpected"] = True
    state.desired_path.write_text(json.dumps(desired) + "\n", encoding="utf-8")
    with pytest.raises(system_contract.ContractError, match="unknown keys"):
        state.read_desired()
    state.observation_path.parent.mkdir(parents=True, exist_ok=True)
    state.observation_path.write_text(
        json.dumps({"schema_version": 3, "generation": 0, "transactions": [], "unexpected": True}) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(system_contract.ContractError, match="unknown keys"):
        state.read_observation()


def test_sessionstart_receipts_complete_live_loaded_plane(tmp_path: Path) -> None:
    state = system_contract.SystemState(tmp_path)
    desired = system_contract.default_desired_state(
        "skills-only", ["claude", "codex"], "stable"
    )
    codex = live_receipt(tmp_path, "codex")
    root = Path(codex["plugin_root"])
    release = release_record(root)
    transaction = state.run_transaction(
        "setup",
        desired,
        lambda _tx: {
            "desired": {"status": "verified"},
            "resolved": {"status": "verified", "release": release},
            "installed": {"status": "verified"},
            "source-provenance": {"status": "verified", "root": str(root)},
            "live-loaded": {"status": "restart-required"},
            "outcome-verified": {"status": "not-requested"},
            "release": release,
        },
    )
    assert transaction["live-loaded"]["status"] == "restart-required"
    wrong = live_receipt(tmp_path, "codex", "9.8.6")
    assert not state.record_live_load(receipt=wrong)
    assert state.record_live_load(receipt=codex)
    current = state.read_observation()["transactions"][-1]
    assert current["live-loaded"]["status"] == "partial"
    claude = dict(codex)
    claude["client"] = "claude"
    claude["provenance_env"] = "claude-transcript"
    claude["receipt_event_id"] = str(uuid.uuid4())
    claude["session_id"] = str(uuid.uuid4())
    claude_transcript = tmp_path / "claude.jsonl"
    claude_transcript.write_text(claude["session_id"] + "\n", encoding="utf-8")
    claude["transcript_path"] = str(claude_transcript)
    assert state.record_live_load(receipt=claude)
    current = state.read_observation()["transactions"][-1]
    assert current["live-loaded"]["status"] == "verified"


def test_live_load_rejects_nonexistent_root_unbound_transcript_and_stale_time(
    tmp_path: Path,
) -> None:
    state = system_contract.SystemState(tmp_path)
    desired = system_contract.default_desired_state("skills-only", ["codex"], "stable")
    receipt = live_receipt(tmp_path, "codex")
    root = Path(receipt["plugin_root"])
    state.run_transaction(
        "setup",
        desired,
        lambda _tx: {
            "release": release_record(root),
            "source-provenance": {"status": "verified", "root": str(root)},
        },
    )
    missing = dict(receipt, plugin_root=str(tmp_path / "missing"))
    with pytest.raises(system_contract.ContractError, match="unavailable"):
        state.record_live_load(receipt=missing)
    unbound = dict(receipt, transcript_bound_at_record=False)
    with pytest.raises(system_contract.ContractError, match="transcript-bound"):
        state.record_live_load(receipt=unbound)
    stale = dict(receipt, recorded_at="2020-01-01T00:00:00+00:00")
    with pytest.raises(system_contract.ContractError, match="freshness"):
        state.record_live_load(receipt=stale)


def test_live_load_binds_client_root_to_the_release_content_digest(tmp_path: Path) -> None:
    source_receipt = live_receipt(tmp_path, "codex")
    source = Path(source_receipt["plugin_root"])
    loaded = tmp_path / "loaded-plugin"
    shutil.copytree(source, loaded)
    receipt = dict(source_receipt, plugin_root=str(loaded))
    state = system_contract.SystemState(tmp_path)
    desired = system_contract.default_desired_state("skills-only", ["codex"], "stable")
    state.run_transaction(
        "setup",
        desired,
        lambda _tx: {
            "release": release_record(source),
            "source-provenance": {"status": "verified", "root": str(source)},
        },
    )
    (loaded / "hooks" / "hooks.json").write_text(
        json.dumps({"hooks": {"SessionStart": [{"command": "changed"}]}}) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(system_contract.ContractError, match="release digest"):
        state.record_live_load(receipt=receipt)


def test_first_generation_records_bounded_legacy_migration_input(tmp_path: Path) -> None:
    legacy = tmp_path / ".synthesis" / "onboarding" / "receipts.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_text(
        json.dumps(
            {
                "version": 2,
                "profile": "full",
                "generated_files": {"/private/path": {"sha256": "a" * 64}},
                "adopted_repos": {"private-name": "/private/repository"},
                "layer_choices": {"skills": {"choice": "selected"}},
            }
        ),
        encoding="utf-8",
    )
    state = system_contract.SystemState(tmp_path)
    desired = system_contract.default_desired_state("skills-only", ["codex"], "stable")
    transaction = state.run_transaction("setup", desired, lambda _tx: {})
    migration = transaction["details"]["legacy_migration_input"]
    assert migration["receipt_version"] == 2
    assert migration["layer_choices"] == {"skills": "selected"}
    assert migration["generated_file_count"] == 1
    assert migration["adopted_repository_count"] == 1
    assert "/private/path" not in json.dumps(migration)


def test_legacy_migration_rejects_symlink_receipt(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    source.write_text("{}\n", encoding="utf-8")
    legacy = tmp_path / ".synthesis" / "onboarding" / "receipts.json"
    legacy.parent.mkdir(parents=True)
    legacy.symlink_to(source)
    state = system_contract.SystemState(tmp_path)
    desired = system_contract.default_desired_state("skills-only", ["codex"], "stable")
    with pytest.raises(system_contract.ContractError, match="non-symlink"):
        state.run_transaction("setup", desired, lambda _tx: {})
    assert state.read_observation()["transactions"] == []


@pytest.mark.parametrize(
    "value",
    ["../escape", "two/levels", ".", "..", "/absolute", "Upper", "a b", "a\\b"],
)
def test_component_identifier_rejects_path_escape(value: str) -> None:
    with pytest.raises(system_contract.ContractError):
        system_contract.safe_identifier(value, "component")


@pytest.mark.parametrize(
    "url",
    [
        "/tmp/repository.git",
        "../repository.git",
        "file:///tmp/repository.git",
        "git://host/repository.git",
        "https://user:secret@host/repository.git",
        "ssh://user:secret@host/repository.git",
    ],
)
def test_repository_transport_rejects_local_or_credential_bearing_urls(url: str) -> None:
    with pytest.raises(system_contract.ContractError):
        system_contract.validate_repository_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://example.test/team/repository.git",
        "ssh://git@example.test/team/repository.git",
        "git@example.test:team/repository.git",
    ],
)
def test_repository_transport_accepts_authenticated_https_or_ssh_shapes(url: str) -> None:
    assert system_contract.validate_repository_url(url) == url


def test_manifest_rejects_repository_selected_commands(tmp_path: Path) -> None:
    manifest = {
        "version": 2,
        "org": {"id": "example", "workspace": "example"},
        "skills_repos": [
            {
                "name": "shared-skills",
                "repository": "https://example.test/shared-skills.git",
                "capability": "skills-install",
                "installer": "/tmp/untrusted.sh",
            }
        ],
    }
    with pytest.raises(system_contract.ContractError, match="unknown keys"):
        system_contract.validate_org_manifest(manifest, tmp_path / "onboarding.yaml")


def test_release_descriptor_binds_tag_commit_tree_and_digest(tmp_path: Path) -> None:
    root = release_repo(tmp_path)
    descriptor = system_contract.release_descriptor_from_checkout(
        root,
        channel="stable",
        ref="stable",
        source_url="https://example.test/synthesis-skills.git",
    )
    assert descriptor["version"] == "9.8.7"
    assert descriptor["commit"] == git(root, "rev-parse", "HEAD")
    assert descriptor["tree"] == git(root, "rev-parse", "HEAD^{tree}")
    assert len(descriptor["content_digest"]) == 64
    system_contract.verify_release_checkout(root, descriptor)

    bad = dict(descriptor)
    bad["tree"] = "0" * 40
    with pytest.raises(system_contract.ContractError, match="tree"):
        system_contract.verify_release_checkout(root, bad)

    bad = dict(descriptor)
    bad["content_digest"] = "0" * 64
    with pytest.raises(system_contract.ContractError, match="digest"):
        system_contract.verify_release_checkout(root, bad)


def test_release_descriptor_rejects_tag_pointing_elsewhere(tmp_path: Path) -> None:
    root = release_repo(tmp_path)
    git(root, "tag", "-f", "v9.8.7", "HEAD^") if False else None
    (root / "extra").write_text("next\n", encoding="utf-8")
    git(root, "add", "extra")
    git(root, "commit", "-q", "-m", "next")
    git(root, "branch", "-f", "stable", "HEAD")
    with pytest.raises(system_contract.ContractError, match="tag"):
        system_contract.release_descriptor_from_checkout(
            root,
            channel="stable",
            ref="stable",
            source_url="https://example.test/synthesis-skills.git",
        )


def test_tree_digest_rejects_links_and_special_files(tmp_path: Path) -> None:
    root = tmp_path / "tree"
    root.mkdir()
    (root / "ordinary").write_text("ok\n", encoding="utf-8")
    (root / "link").symlink_to(root / "ordinary")
    with pytest.raises(system_contract.ContractError, match="link"):
        system_contract.canonical_tree_digest(root)


def test_activation_refuses_user_owned_launcher(tmp_path: Path) -> None:
    root = release_repo(tmp_path)
    descriptor = system_contract.release_descriptor_from_checkout(
        root, "stable", "stable", "https://example.test/synthesis-skills.git"
    )
    launcher = tmp_path / "bin" / "synthesis"
    launcher.parent.mkdir()
    launcher.write_text("#!/bin/sh\necho mine\n", encoding="utf-8")
    with pytest.raises(system_contract.ContractError, match="user-owned"):
        system_contract.activate_cli(root, descriptor, launcher, tmp_path / "active.json")
    assert launcher.read_text(encoding="utf-8") == "#!/bin/sh\necho mine\n"


def test_managed_launcher_dispatches_through_the_atomic_active_pointer(tmp_path: Path) -> None:
    root = release_repo(tmp_path)
    descriptor = system_contract.release_descriptor_from_checkout(
        root, "stable", "stable", "https://example.test/synthesis-skills.git"
    )
    launcher = tmp_path / "bin" / "synthesis"
    active = tmp_path / "state" / "active.json"
    system_contract.activate_cli(root, descriptor, launcher, active)
    completed = subprocess.run(
        [str(launcher)], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == str(active)


def test_activation_refuses_launcher_that_spoofs_the_public_marker(tmp_path: Path) -> None:
    root = release_repo(tmp_path)
    descriptor = system_contract.release_descriptor_from_checkout(
        root, "stable", "stable", "https://example.test/synthesis-skills.git"
    )
    launcher = tmp_path / "bin" / "synthesis"
    launcher.parent.mkdir()
    forged = system_contract.LAUNCHER_MARK + "\n#!/bin/sh\necho user-owned\n"
    launcher.write_text(forged, encoding="utf-8")
    with pytest.raises(system_contract.ContractError, match="user-owned"):
        system_contract.activate_cli(root, descriptor, launcher, tmp_path / "active.json")
    assert launcher.read_text(encoding="utf-8") == forged


def test_activation_failure_cannot_split_launcher_from_active_descriptor(
    tmp_path: Path, monkeypatch
) -> None:
    root = release_repo(tmp_path)
    descriptor = system_contract.release_descriptor_from_checkout(
        root, "stable", "stable", "https://example.test/synthesis-skills.git"
    )
    launcher = tmp_path / "bin" / "synthesis"
    active = tmp_path / "state" / "active.json"
    system_contract.activate_cli(root, descriptor, launcher, active)
    launcher_before = launcher.read_bytes()
    active_before = active.read_bytes()

    def fail(*_args, **_kwargs):
        raise OSError("injected descriptor failure")

    monkeypatch.setattr(system_contract, "atomic_write_json", fail)
    with pytest.raises(OSError, match="injected"):
        system_contract.activate_cli(root, descriptor, launcher, active)
    assert launcher.read_bytes() == launcher_before
    assert active.read_bytes() == active_before


def test_concurrent_transactions_preserve_every_generation(tmp_path: Path) -> None:
    errors: list[BaseException] = []

    def worker(index: int) -> None:
        try:
            state = system_contract.SystemState(home=tmp_path)
            desired = system_contract.default_desired_state(
                profile="skills-only", clients=["codex"], channel="stable"
            )
            state.run_transaction(
                "repair",
                desired,
                lambda _tx: {"installed": {"worker": index}},
            )
        except BaseException as exc:  # pragma: no cover - assertion reports it
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(index,)) for index in range(12)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    observed = system_contract.SystemState(home=tmp_path).read_observation()
    assert observed["generation"] == 12
    assert [item["generation"] for item in observed["transactions"]] == list(
        range(1, 13)
    )
    assert all(item["state"] == "committed" for item in observed["transactions"])


def test_pending_transaction_is_aborted_before_reentry(tmp_path: Path) -> None:
    state = system_contract.SystemState(home=tmp_path)
    state.observation_path.parent.mkdir(parents=True)
    state.observation_path.write_text(
        json.dumps(
            {
                "schema_version": 3,
                "generation": 1,
                "transactions": [
                    {
                        "transaction_id": "a" * 32,
                        "generation": 1,
                        "state": "pending",
                        "command": "setup",
                        "desired_digest": "b" * 64,
                        "started_at": "2026-09-02T00:00:00Z",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    desired = system_contract.default_desired_state(
        profile="skills-only", clients=["codex"], channel="stable"
    )
    state.run_transaction("repair", desired, lambda _tx: {"installed": {}})
    observed = state.read_observation()
    assert observed["transactions"][0]["state"] == "aborted"
    assert observed["transactions"][0]["error"] == "interrupted before commit"
    assert observed["transactions"][1]["state"] == "committed"


def test_failed_transaction_never_commits_or_advances_desired_state(tmp_path: Path) -> None:
    state = system_contract.SystemState(home=tmp_path)
    desired = system_contract.default_desired_state(
        profile="full", clients=["claude"], channel="stable"
    )

    def fail(_tx: dict) -> dict:
        raise RuntimeError("fixture failure")

    with pytest.raises(RuntimeError, match="fixture failure"):
        state.run_transaction("setup", desired, fail)
    observed = state.read_observation()
    assert observed["transactions"][-1]["state"] == "aborted"
    assert not state.desired_path.exists()


def test_failed_transaction_invokes_resource_compensation_before_abort(tmp_path: Path) -> None:
    state = system_contract.SystemState(home=tmp_path)
    desired = system_contract.default_desired_state(
        profile="skills-only", clients=["codex"], channel="stable"
    )
    resource = tmp_path / "external-resource"

    def fail(_tx: dict) -> dict:
        resource.write_text("partial\n", encoding="utf-8")
        raise RuntimeError("fixture failure")

    def restore(_error: BaseException) -> None:
        resource.unlink()

    with pytest.raises(RuntimeError, match="fixture failure"):
        state.run_transaction("setup", desired, fail, rollback=restore)
    assert not resource.exists()
    latest = state.read_observation()["transactions"][-1]
    assert latest["state"] == "aborted"
    assert latest["details"]["rollback"]["status"] == "restored"


def test_transaction_can_commit_resolved_desired_state_under_the_same_lock(
    tmp_path: Path,
) -> None:
    state = system_contract.SystemState(home=tmp_path)
    request = {"profile": "skills-only", "organization_commit": None}
    resolved = system_contract.default_desired_state(
        profile="skills-only", clients=["codex"], channel="stable"
    )
    transaction = state.run_transaction(
        "setup", request, lambda _tx: {"_desired": resolved}
    )
    assert state.read_desired() == resolved
    assert transaction["desired_digest"] == system_contract.json_digest(request)
    assert transaction["committed_desired_digest"] == system_contract.json_digest(resolved)
    assert transaction["previous_active_generation"] is None
    second = state.run_transaction("repair", resolved, lambda _tx: {})
    assert second["previous_active_generation"] == transaction["generation"]


def test_instruction_pair_rolls_back_if_second_activation_fails(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    git(source, "init", "-q", "-b", "main")
    (source / "instructions.md").write_text("Use the tracked source.\n", encoding="utf-8")
    git(source, "add", "instructions.md")
    git(source, "commit", "-q", "-m", "source")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "AGENTS.md").write_text("old agents\n", encoding="utf-8")
    (workspace / "CLAUDE.md").write_text("old claude\n", encoding="utf-8")
    graph = {
        "schema_version": 1,
        "sources": [{"role": "personal", "path": "instructions.md", "required": True}],
        "output": "AGENTS.md",
        "claude_adapter": "CLAUDE.md",
    }
    with pytest.raises(system_contract.ContractError, match="injected"):
        system_contract.materialize_instruction_pair(
            graph,
            {"personal": source},
            workspace,
            generation=1,
            fail_after_first=True,
        )
    assert (workspace / "AGENTS.md").read_text(encoding="utf-8") == "old agents\n"
    assert (workspace / "CLAUDE.md").read_text(encoding="utf-8") == "old claude\n"


def test_instruction_pair_reports_user_drift_without_clobbering(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    git(source, "init", "-q", "-b", "main")
    (source / "instructions.md").write_text("Tracked.\n", encoding="utf-8")
    git(source, "add", "instructions.md")
    git(source, "commit", "-q", "-m", "source")
    workspace = tmp_path / "workspace"
    graph = {
        "schema_version": 1,
        "sources": [{"role": "personal", "path": "instructions.md", "required": True}],
        "output": "AGENTS.md",
        "claude_adapter": "CLAUDE.md",
    }
    receipt = system_contract.materialize_instruction_pair(
        graph, {"personal": source}, workspace, generation=1
    )
    (workspace / "AGENTS.md").write_text("user edit\n", encoding="utf-8")
    with pytest.raises(system_contract.DriftError):
        system_contract.materialize_instruction_pair(
            graph,
            {"personal": source},
            workspace,
            generation=2,
            previous_receipt=receipt,
        )
    assert (workspace / "AGENTS.md").read_text(encoding="utf-8") == "user edit\n"


def test_invite_is_bounded_and_cannot_replay(tmp_path: Path) -> None:
    now = datetime(2026, 9, 2, 20, 0, tzinfo=timezone.utc)
    invite = {
        "schema_version": 1,
        "repository": "https://example.test/org/config.git",
        "provider": "generic",
        "manifest_path": ".agents/onboarding.yaml",
        "nonce": "fixture_nonce_0123456789",
        "issued_at": (now - timedelta(minutes=1)).isoformat(),
        "expires_at": (now + timedelta(minutes=10)).isoformat(),
    }
    state = system_contract.SystemState(home=tmp_path)
    digest = system_contract.consume_invite(invite, state, now=now)
    assert len(digest) == 64
    with pytest.raises(system_contract.ContractError, match="already consumed"):
        system_contract.consume_invite(invite, state, now=now)
    expired = dict(invite)
    expired["expires_at"] = (now - timedelta(seconds=1)).isoformat()
    with pytest.raises(system_contract.ContractError, match="expired"):
        system_contract.validate_invite(expired, now=now)


def test_outcome_verification_requires_public_capability_and_source_class(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "source").mkdir(parents=True)
    (workspace / ".agents").mkdir()
    (workspace / ".agents" / "knowledge-base.yaml").write_text(
        "bundle_path: source\n", encoding="utf-8"
    )
    (workspace / "source" / "grounding.md").write_text("evidence\n", encoding="utf-8")
    git(workspace, "init", "-q", "-b", "main")
    git(workspace, "add", "-A")
    git(workspace, "commit", "-q", "-m", "fixture")
    evidence = {"workspace": str(workspace), "source_class": "personal-knowledge"}
    receipt = system_contract.verify_outcome(
        "workspace-grounding-check", evidence, REPO_ROOT
    )
    assert receipt["capability"] == "workspace-read"
    with pytest.raises(system_contract.ContractError, match="not trusted"):
        system_contract.verify_outcome("shell-command", evidence, REPO_ROOT)
    with pytest.raises(system_contract.ContractError, match="source class"):
        system_contract.verify_outcome(
            "workspace-grounding-check",
            {"workspace": str(workspace), "source_class": "organization"},
            REPO_ROOT,
        )


def test_outcome_verification_rejects_non_git_and_untracked_evidence(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / ".agents").mkdir(parents=True)
    (workspace / "source").mkdir()
    (workspace / ".agents" / "knowledge-base.yaml").write_text(
        "bundle_path: source\n", encoding="utf-8"
    )
    (workspace / "source" / "fact.md").write_text("fact\n", encoding="utf-8")
    evidence = {"workspace": str(workspace), "source_class": "personal-knowledge"}
    with pytest.raises(system_contract.ContractError, match="Git repository"):
        system_contract.verify_outcome("workspace-grounding-check", evidence, REPO_ROOT)
    git(workspace, "init", "-q", "-b", "main")
    with pytest.raises(system_contract.ContractError, match="not Git-tracked"):
        system_contract.verify_outcome("workspace-grounding-check", evidence, REPO_ROOT)

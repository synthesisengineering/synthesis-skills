#!/usr/bin/env python3
"""Generation-zero fixtures from the 2026-09-03 independent review.

Every test here was red against release 4.91.4 before its repair landed. The
fixtures attack the installed-release path, the truth planes, the scaffold,
the human-facing output, and the public entry points as a stranger, an
organization member, and a returning user would experience them.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml


SCRIPTS = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS.parents[2]
CONFORMANCE_SCRIPTS = REPO_ROOT / "skills" / "synthesis-agent-conformance" / "scripts"
KB_EDIT_SCRIPTS = REPO_ROOT / "skills" / "synthesis-kb-edit" / "scripts"
for path in (SCRIPTS, CONFORMANCE_SCRIPTS, KB_EDIT_SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import bootstrap  # noqa: E402
import kb_config  # noqa: E402
import live_receipt  # noqa: E402
import onboard  # noqa: E402
import plugin_currency  # noqa: E402
import synthesis_cli  # noqa: E402
import system_contract  # noqa: E402
from test_onboard import Sandbox  # noqa: E402
from test_system_contract import git, live_receipt as receipt_fixture, release_record, release_repo  # noqa: E402


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _descriptor_file(path: Path, descriptor: dict, release_root: Path) -> Path:
    active = dict(descriptor)
    active["release_root"] = str(release_root.resolve())
    active["activated_at"] = system_contract.utcnow()
    path.write_text(json.dumps(active) + "\n", encoding="utf-8")
    return path


def _installed_release_copy(destination: Path) -> Path:
    """Copy the tracked release subset needed by the engine, without .git."""
    ignore = shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.pyc")
    for relative in (".claude-plugin", ".codex-plugin", "skills/synthesis-onboarding"):
        shutil.copytree(REPO_ROOT / relative, destination / relative, ignore=ignore)
    for relative in ("onboard.sh", "install.sh"):
        shutil.copy2(REPO_ROOT / relative, destination / relative)
    return destination


def _registry_event(
    registry_root: Path, receipt: dict, *, bound_at_record: bool
) -> Path:
    event = dict(receipt)
    event["transcript_bound_at_record"] = bound_at_record
    path = registry_root / event["client"] / event["session_id"] / (event["receipt_event_id"] + ".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(event, indent=2) + "\n", encoding="utf-8")
    return path


def _engine_result(exit_code: int = 0, steps: list | None = None, counts: dict | None = None) -> dict:
    return {
        "engine": "fixture",
        "counts": counts or ({"ok": 1} if exit_code == 0 else {"action-needed": 1}),
        "steps": steps or [],
        "exit": exit_code,
    }


# ---------------------------------------------------------------------------
# AR-101 — organization instructions from an installed immutable release
# ---------------------------------------------------------------------------

def test_public_source_identity_accepts_only_git_or_the_verified_active_release(
    tmp_path: Path, monkeypatch
) -> None:
    checkout = release_repo(tmp_path)
    (checkout / "skills" / "synthesis-onboarding" / "references").mkdir(parents=True)
    (checkout / "skills" / "synthesis-onboarding" / "references" / "kernel.example.md").write_text(
        "Public baseline.\n", encoding="utf-8"
    )
    git(checkout, "add", "-A")
    git(checkout, "commit", "-q", "-m", "baseline")
    head = git(checkout, "rev-parse", "HEAD")
    identity = system_contract.public_source_identity(checkout)
    assert identity["kind"] == "git"
    assert identity["commit"] == head

    installed = tmp_path / "installed"
    shutil.copytree(checkout, installed, ignore=shutil.ignore_patterns(".git"))
    monkeypatch.delenv("SYNTHESIS_ACTIVE_DESCRIPTOR", raising=False)
    with pytest.raises(system_contract.ContractError, match="neither"):
        system_contract.public_source_identity(installed)

    descriptor = release_record(installed)
    active = _descriptor_file(tmp_path / "active.json", descriptor, installed)
    monkeypatch.setenv("SYNTHESIS_ACTIVE_DESCRIPTOR", str(active))
    identity = system_contract.public_source_identity(installed)
    assert identity["kind"] == "release"
    assert identity["commit"] == descriptor["commit"]

    elsewhere = tmp_path / "elsewhere"
    shutil.copytree(installed, elsewhere)
    with pytest.raises(system_contract.ContractError, match="active release"):
        system_contract.public_source_identity(elsewhere)

    (installed / "onboard.sh").write_text("# tampered\n", encoding="utf-8")
    with pytest.raises(system_contract.ContractError, match="digest"):
        system_contract.public_source_identity(installed)


def test_instruction_pair_materializes_from_a_verified_release_root(
    tmp_path: Path, monkeypatch
) -> None:
    checkout = release_repo(tmp_path)
    (checkout / "skills" / "synthesis-onboarding" / "references").mkdir(parents=True)
    (checkout / "skills" / "synthesis-onboarding" / "references" / "kernel.example.md").write_text(
        "Public baseline.\n", encoding="utf-8"
    )
    git(checkout, "add", "-A")
    git(checkout, "commit", "-q", "-m", "baseline")
    installed = tmp_path / "installed"
    shutil.copytree(checkout, installed, ignore=shutil.ignore_patterns(".git"))
    organization = tmp_path / "organization"
    (organization / ".agents").mkdir(parents=True)
    (organization / ".agents" / "workspace-instructions.md").write_text(
        "Organization rules.\n", encoding="utf-8"
    )
    git(organization, "init", "-q", "-b", "main")
    git(organization, "add", "-A")
    git(organization, "commit", "-q", "-m", "organization")
    graph = {
        "schema_version": 1,
        "sources": [
            {"role": "public", "path": "skills/synthesis-onboarding/references/kernel.example.md", "required": True},
            {"role": "organization", "path": ".agents/workspace-instructions.md", "required": True},
        ],
        "output": "AGENTS.md",
        "claude_adapter": "CLAUDE.md",
    }
    roots = {"public": installed, "organization": organization}
    with pytest.raises(system_contract.ContractError, match="not Git-tracked"):
        system_contract.materialize_instruction_pair(graph, roots, tmp_path / "ws-a", generation=1)

    descriptor = release_record(installed)
    active = _descriptor_file(tmp_path / "active.json", descriptor, installed)
    monkeypatch.setenv("SYNTHESIS_ACTIVE_DESCRIPTOR", str(active))
    identity = system_contract.public_source_identity(installed)
    receipt = system_contract.materialize_instruction_pair(
        graph, roots, tmp_path / "ws-b", generation=1, source_identities={"public": identity}
    )
    public_source = next(entry for entry in receipt["sources"] if entry["role"] == "public")
    assert public_source["commit"] == descriptor["commit"]
    rendered = (tmp_path / "ws-b" / "AGENTS.md").read_text(encoding="utf-8")
    assert "Public baseline." in rendered and "Organization rules." in rendered


def test_engine_materializes_organization_instructions_from_an_installed_release() -> None:
    box = Sandbox()
    try:
        installed = _installed_release_copy(box.root / "installed-release")
        descriptor = release_record(installed, version=onboard.source_plugin_version())
        active = _descriptor_file(box.root / "active.json", descriptor, installed)
        manifest = box.manifest()
        proc = box.run_with_env(
            {
                "SYNTHESIS_ONBOARD_SOURCE_DIR": str(installed),
                "SYNTHESIS_ACTIVE_DESCRIPTOR": str(active),
            },
            "install", "--manifest", str(manifest), "--json",
            expect=0,
        )
        data = json.loads(proc.stdout)
        workspace_steps = [step for step in data["steps"] if step["phase"] == "workspace"]
        assert workspace_steps and workspace_steps[-1]["status"] in ("changed", "ok"), workspace_steps
        receipts = json.loads(
            (box.home / ".synthesis" / "onboarding" / "receipts.json").read_text(encoding="utf-8")
        )
        public_source = next(
            entry for entry in receipts["instruction_receipt"]["sources"] if entry["role"] == "public"
        )
        assert public_source["commit"] == descriptor["commit"]
    finally:
        shutil.rmtree(box.root, ignore_errors=True)


# ---------------------------------------------------------------------------
# AR-102 — schema-1 organization manifests get an actionable refusal
# ---------------------------------------------------------------------------

def test_schema_one_manifest_refusal_names_the_migration_guide() -> None:
    box = Sandbox()
    try:
        path = box.root / "legacy.yaml"
        path.write_text(
            "version: 1\n"
            "org:\n  id: exampleco\n  workspace: exampleco\n"
            "skills_repos:\n  - name: shared\n    primary: ssh://fixture/shared.git\n    installer: install.sh\n"
            "workspace_instructions: true\n",
            encoding="utf-8",
        )
        data, _ = box.run_json("doctor", "--manifest", str(path), expect=2)
        detail = data["steps"][0]["detail"]
        assert "schema 1" in detail
        assert "org-manifest.md" in detail
        assert "version: 2" in detail
    finally:
        shutil.rmtree(box.root, ignore_errors=True)


def test_organization_guide_documents_the_schema_one_migration() -> None:
    guide = (REPO_ROOT / "skills/synthesis-onboarding/references/org-manifest.md").read_text(
        encoding="utf-8"
    )
    assert "## Migrating from schema 1" in guide
    for legacy in ("workspace_instructions", "superseded_remotes", "installer"):
        assert legacy in guide


# ---------------------------------------------------------------------------
# AR-103 — a fresh Claude session must reach the live-loaded plane
# ---------------------------------------------------------------------------

def test_pending_claude_receipt_is_promoted_once_its_transcript_binds(tmp_path: Path) -> None:
    state = system_contract.SystemState(tmp_path)
    fixture = receipt_fixture(tmp_path, "claude")
    root = Path(fixture["plugin_root"])
    desired = system_contract.default_desired_state("skills-only", ["claude"], "stable")
    state.run_transaction(
        "setup",
        desired,
        lambda _tx: {
            "release": release_record(root),
            "source-provenance": {"status": "verified", "root": str(root)},
        },
    )
    registry = tmp_path / "registry"
    transcript = tmp_path / "pending.jsonl"
    pending = dict(fixture, transcript_path=str(transcript))
    pending["recorded_at"] = datetime.now(timezone.utc).isoformat()
    _registry_event(registry, pending, bound_at_record=False)

    promoted = state.promote_live_receipts(
        binder=live_receipt.transcript_binds_session, registry_root=registry
    )
    assert promoted == []
    latest = state.read_observation()["transactions"][-1]
    assert latest.get("live-loaded", {}).get("status") != "verified"

    transcript.write_text(json.dumps({"sessionId": "someone-else"}) + "\n", encoding="utf-8")
    assert state.promote_live_receipts(
        binder=live_receipt.transcript_binds_session, registry_root=registry
    ) == []

    transcript.write_text(json.dumps({"sessionId": pending["session_id"]}) + "\n", encoding="utf-8")
    promoted = state.promote_live_receipts(
        binder=live_receipt.transcript_binds_session, registry_root=registry
    )
    assert [(item["client"], item["session_id"]) for item in promoted] == [("claude", pending["session_id"])]
    latest = state.read_observation()["transactions"][-1]
    assert latest["live-loaded"]["status"] == "verified"
    assert latest["live-loaded"]["receipts"]["claude"]["transcript_bound_at_promotion"] is True
    assert state.promote_live_receipts(
        binder=live_receipt.transcript_binds_session, registry_root=registry
    ) == []


def test_promotion_ignores_receipts_that_predate_the_generation(tmp_path: Path) -> None:
    state = system_contract.SystemState(tmp_path)
    fixture = receipt_fixture(tmp_path, "claude")
    root = Path(fixture["plugin_root"])
    registry = tmp_path / "registry"
    transcript = tmp_path / "old.jsonl"
    transcript.write_text(json.dumps({"sessionId": fixture["session_id"]}) + "\n", encoding="utf-8")
    old = dict(fixture, transcript_path=str(transcript))
    old["recorded_at"] = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    _registry_event(registry, old, bound_at_record=False)
    desired = system_contract.default_desired_state("skills-only", ["claude"], "stable")
    state.run_transaction(
        "setup",
        desired,
        lambda _tx: {
            "release": release_record(root),
            "source-provenance": {"status": "verified", "root": str(root)},
        },
    )
    assert state.promote_live_receipts(
        binder=live_receipt.transcript_binds_session, registry_root=registry
    ) == []
    latest = state.read_observation()["transactions"][-1]
    assert latest.get("live-loaded", {}).get("status") != "verified"


def test_doctor_promotes_a_fresh_claude_receipt_from_the_registry(tmp_path: Path, capsys) -> None:
    home = tmp_path / "home"
    state = system_contract.SystemState(home=home)
    fixture = receipt_fixture(tmp_path, "claude")
    root = Path(fixture["plugin_root"])
    desired = system_contract.default_desired_state("skills-only", ["claude"], "stable")
    state.run_transaction(
        "setup",
        desired,
        lambda _tx: {
            "release": release_record(root),
            "source-provenance": {"status": "verified", "root": str(root)},
        },
    )
    transcript = home / ".claude" / "projects" / "encoded" / (fixture["session_id"] + ".jsonl")
    transcript.parent.mkdir(parents=True)
    transcript.write_text(json.dumps({"sessionId": fixture["session_id"]}) + "\n", encoding="utf-8")
    pending = dict(fixture, transcript_path=str(transcript))
    pending["recorded_at"] = datetime.now(timezone.utc).isoformat()
    _registry_event(state.live_receipt_registry_root(), pending, bound_at_record=False)

    code = synthesis_cli.main(
        ["doctor", "--json"], state=state, engine_runner=lambda _argv: _engine_result(0)
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["planes"]["live-loaded"]["status"] == "verified"
    assert payload["promoted"] == [{"client": "claude", "session_id": fixture["session_id"]}]
    assert code == 0


# ---------------------------------------------------------------------------
# AR-104 — the scaffolded workspace satisfies the public outcome task
# ---------------------------------------------------------------------------

def test_scaffolded_workspace_declares_its_knowledge_bundle_and_passes_outcome_verification() -> None:
    box = Sandbox()
    try:
        box.run_json("init-workspace", "--workspace", "alice", expect=0)
        repo = box.home / "workspaces" / "alice" / "ai-knowledge-alice"
        declaration = repo / ".agents" / "knowledge-base.yaml"
        assert declaration.is_file()
        assert (repo / "source" / "README.md").is_file()
        tracked = subprocess.run(
            ["git", "-C", str(repo), "ls-files", ".agents/knowledge-base.yaml", "source/README.md"],
            env=box.git_env, text=True, capture_output=True, check=True,
        ).stdout.split()
        assert sorted(tracked) == [".agents/knowledge-base.yaml", "source/README.md"]
        config = yaml.safe_load(declaration.read_text(encoding="utf-8"))
        assert kb_config.validate_config(config) == []
        assert kb_config.check_paths(repo.resolve(), config) == []
        receipt = system_contract.verify_outcome(
            "workspace-grounding-check",
            {"workspace": str(repo), "source_class": "personal-knowledge"},
            REPO_ROOT,
        )
        assert receipt["evidence_count"] >= 1
    finally:
        shutil.rmtree(box.root, ignore_errors=True)


# ---------------------------------------------------------------------------
# AR-105 — doctor re-derives planes instead of echoing the transaction
# ---------------------------------------------------------------------------

def test_doctor_reverifies_the_active_release_root(tmp_path: Path, monkeypatch, capsys) -> None:
    checkout = release_repo(tmp_path)
    releases = tmp_path / "releases"
    generation, descriptor = bootstrap.materialize_release(
        checkout, releases, channel="stable", ref="stable",
        source_url="https://example.test/synthesis-skills.git",
    )
    active = _descriptor_file(tmp_path / "active.json", descriptor, generation)
    monkeypatch.setenv("SYNTHESIS_ACTIVE_DESCRIPTOR", str(active))
    state = system_contract.SystemState(home=tmp_path / "home")
    desired = system_contract.default_desired_state("skills-only", ["codex"], "stable")
    state.run_transaction(
        "setup",
        desired,
        lambda _tx: {
            "release": descriptor,
            "resolved": {"status": "verified", "release": descriptor},
            "source-provenance": {"status": "verified", "root": str(generation)},
        },
    )
    assert synthesis_cli.main(
        ["doctor", "--json"], state=state, engine_runner=lambda _argv: _engine_result(0)
    ) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["planes"]["source-provenance"]["status"] == "verified"
    assert payload["planes"]["resolved"]["status"] == "verified"
    assert payload["planes"]["live-loaded"]["status"] == "restart-required"

    target = generation / ".codex-plugin" / "plugin.json"
    os.chmod(generation / ".codex-plugin", 0o755)
    os.chmod(target, 0o644)
    target.write_text(json.dumps({"name": "synthesis-skills", "version": "9.8.7", "tampered": True}) + "\n", encoding="utf-8")
    assert synthesis_cli.main(
        ["doctor", "--json"], state=state, engine_runner=lambda _argv: _engine_result(0)
    ) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["planes"]["source-provenance"]["status"] == "drifted"
    assert "digest" in payload["planes"]["source-provenance"]["detail"]


def test_doctor_reports_installed_defects_from_the_engine(tmp_path: Path, capsys) -> None:
    state = system_contract.SystemState(home=tmp_path / "home")
    desired = system_contract.default_desired_state("skills-only", ["codex"], "stable")
    state.run_transaction("setup", desired, lambda _tx: synthesis_cli._planes(desired, "setup"))
    failing = _engine_result(
        1,
        steps=[{"phase": "ecosystem", "status": "action-needed", "detail": "plugin for codex is 9.8.6; source is 9.8.7", "hint": None}],
    )
    assert synthesis_cli.main(["doctor", "--json"], state=state, engine_runner=lambda _argv: failing) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["planes"]["installed"]["status"] == "defective"
    assert "9.8.6" in payload["planes"]["installed"]["detail"]


# ---------------------------------------------------------------------------
# AR-106 — the SessionStart notice follows desired state
# ---------------------------------------------------------------------------

def _isolate_policy_home(tmp_path: Path, monkeypatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SYNTHESIS_HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(home / ".local" / "state"))
    for name in ("SYNTHESIS_ONBOARD_STATE_DIR", "SYNTHESIS_ONBOARD_RECEIPTS"):
        monkeypatch.delenv(name, raising=False)
    return home


def test_persisted_policy_prefers_desired_state_over_legacy_receipts(tmp_path: Path, monkeypatch) -> None:
    home = _isolate_policy_home(tmp_path, monkeypatch)
    legacy = home / ".synthesis" / "onboarding" / "receipts.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_text(json.dumps({"plugin_policy": {"channel": "stable", "version_pin": None}}), encoding="utf-8")
    assert plugin_currency.read_persisted_policy() == {"channel": "stable", "version_pin": None}

    new_receipts = home / ".local" / "state" / "synthesis" / "receipts.json"
    new_receipts.parent.mkdir(parents=True)
    new_receipts.write_text(json.dumps({"plugin_policy": {"channel": "edge", "version_pin": None}}), encoding="utf-8")
    assert plugin_currency.read_persisted_policy() == {"channel": "edge", "version_pin": None}

    desired = system_contract.default_desired_state("skills-only", ["claude"], "stable", version_pin="9.8.6")
    desired_path = home / ".config" / "synthesis" / "system-state.json"
    desired_path.parent.mkdir(parents=True)
    desired_path.write_text(json.dumps(desired), encoding="utf-8")
    assert plugin_currency.read_persisted_policy() == {"channel": "stable", "version_pin": "9.8.6"}

    root = tmp_path / "plugin"
    (root / ".codex-plugin").mkdir(parents=True)
    (root / ".claude-plugin").mkdir()
    for manifest in (root / ".codex-plugin" / "plugin.json", root / ".claude-plugin" / "plugin.json"):
        manifest.write_text(json.dumps({"version": "9.8.7"}), encoding="utf-8")
    notice = plugin_currency.sessionstart_notice(root, resolver=lambda policy: (policy["version_pin"] or "9.8.7", "fixture"))
    assert "pinned release 9.8.6" in notice
    assert "update available" not in notice.lower()


def test_currency_cache_lives_under_the_engine_state_root(tmp_path: Path, monkeypatch) -> None:
    home = _isolate_policy_home(tmp_path, monkeypatch)
    assert plugin_currency.default_cache_path() == home / ".local" / "state" / "synthesis" / "plugin-currency.json"
    monkeypatch.setenv("SYNTHESIS_ONBOARD_STATE_DIR", str(tmp_path / "explicit"))
    assert plugin_currency.default_cache_path() == tmp_path / "explicit" / "plugin-currency.json"
    assert onboard.STATE_DIR.name == "synthesis" or os.environ.get("SYNTHESIS_ONBOARD_STATE_DIR")


# ---------------------------------------------------------------------------
# AR-107 and AR-121 — status and doctor speak to people
# ---------------------------------------------------------------------------

def test_status_and_doctor_render_human_summaries_with_a_next_action(tmp_path: Path, capsys) -> None:
    state = system_contract.SystemState(home=tmp_path / "home")
    fixture = receipt_fixture(tmp_path, "claude")
    root = Path(fixture["plugin_root"])
    desired = system_contract.default_desired_state("skills-only", ["claude", "codex"], "stable")
    state.run_transaction(
        "update",
        desired,
        lambda _tx: {
            "release": release_record(root),
            "source-provenance": {"status": "verified", "root": str(root)},
            "live-loaded": {
                "status": "partial",
                "release_version": "9.8.7",
                "receipts": {"claude": {"client": "claude", "session_id": fixture["session_id"], "plugin_version": "9.8.7"}},
            },
        },
    )
    assert synthesis_cli.main(["status"], state=state) == 0
    status_text = capsys.readouterr().out
    for fragment in ("9.8.7", "stable", "skills-only", "claude", "codex", "generation 1", "committed"):
        assert fragment in status_text, fragment
    assert "live-loaded" in status_text.lower()

    assert synthesis_cli.main(["doctor"], state=state, engine_runner=lambda _argv: _engine_result(0)) == 1
    doctor_text = capsys.readouterr().out
    for plane in system_contract.TRUTH_PLANES:
        assert plane in doctor_text, plane
    assert "Next action" in doctor_text
    assert "restart Codex" in doctor_text
    assert "hook" in doctor_text.lower() and "trust" in doctor_text.lower()
    assert "{" not in doctor_text.splitlines()[0]


# ---------------------------------------------------------------------------
# AR-108 and AR-109 — scaffold reruns respect user files and explain refusals
# ---------------------------------------------------------------------------

def test_workspace_rerun_keeps_user_edits_without_a_deletion_hint() -> None:
    box = Sandbox()
    try:
        box.run_json("init-workspace", "--workspace", "alice", expect=0)
        repo = box.home / "workspaces" / "alice" / "ai-knowledge-alice"
        index = repo / "projects" / "index.yaml"
        index.write_text("projects:\n  - id: mine\n    name: Mine\n    status: active\n", encoding="utf-8")
        data, _ = box.run_json("init-workspace", "--workspace", "alice", expect=0)
        index_steps = [step for step in data["steps"] if "index.yaml" in step["detail"]]
        assert index_steps and index_steps[0]["status"] == "ok", index_steps
        assert not any("Remove the file" in (step.get("hint") or "") for step in data["steps"])
        assert index.read_text(encoding="utf-8").startswith("projects:\n  - id: mine")
    finally:
        shutil.rmtree(box.root, ignore_errors=True)


def test_first_commit_refusal_reports_the_real_cause() -> None:
    box = Sandbox()
    try:
        hooks = box.root / "hooks"
        hooks.mkdir()
        hook = hooks / "pre-commit"
        hook.write_text("#!/bin/sh\necho 'COMMIT BLOCKED fixture: coordination authority refused' >&2\nexit 1\n", encoding="utf-8")
        hook.chmod(0o755)
        proc = box.run_with_env(
            {
                "GIT_CONFIG_COUNT": "2",
                "GIT_CONFIG_KEY_1": "core.hooksPath",
                "GIT_CONFIG_VALUE_1": str(hooks),
            },
            "init-workspace", "--workspace", "bob", "--json",
            expect=1,
        )
        data = json.loads(proc.stdout)
        refusal = [step for step in data["steps"] if step["status"] == "action-needed"]
        assert refusal, data["steps"]
        assert "refused" in refusal[0]["detail"]
        assert "COMMIT BLOCKED fixture" in (refusal[0].get("hint") or "")
        assert "identity" not in refusal[0]["detail"]

        proc = box.run_with_env(
            {
                "GIT_AUTHOR_NAME": "",
                "GIT_AUTHOR_EMAIL": "",
                "GIT_COMMITTER_NAME": "",
                "GIT_COMMITTER_EMAIL": "",
            },
            "init-workspace", "--workspace", "carol", "--json",
            expect=1,
        )
        data = json.loads(proc.stdout)
        identity = [step for step in data["steps"] if step["status"] == "action-needed"]
        assert identity and "identity" in identity[0]["detail"], data["steps"]
    finally:
        shutil.rmtree(box.root, ignore_errors=True)


# ---------------------------------------------------------------------------
# AR-110 — workspace ensure defaults to the clients that exist
# ---------------------------------------------------------------------------

def test_workspace_ensure_defaults_to_detected_clients(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        synthesis_cli.onboard, "resolve_client", lambda name: "/fixture/claude" if name == "claude" else None
    )
    state = system_contract.SystemState(home=tmp_path / "home")
    assert synthesis_cli.main(
        ["workspace", "ensure", "--name", "example"], state=state, engine_runner=lambda _argv: 0
    ) == 0
    assert state.read_desired()["clients"] == ["claude"]

    monkeypatch.setattr(synthesis_cli.onboard, "resolve_client", lambda name: None)
    empty = system_contract.SystemState(home=tmp_path / "empty-home")
    assert synthesis_cli.main(
        ["workspace", "ensure", "--name", "example"], state=empty, engine_runner=lambda _argv: 0
    ) == 2
    assert empty.read_desired() is None


# ---------------------------------------------------------------------------
# AR-112 — a current installation is not reconfigured
# ---------------------------------------------------------------------------

def _logging_client(box: Sandbox, version: str) -> Path:
    log = box.root / "client.log"
    state = box.root / "logging-client-installed"
    state.write_text("installed\n", encoding="utf-8")
    path = box.root / "logging-client"
    path.write_text(
        "#!/bin/sh\n"
        "printf '%%s\\n' \"$*\" >> %s\n"
        "if [ \"${1:-}\" = plugin ] && [ \"${2:-}\" = list ]; then\n"
        "  printf '%%s\\n' '{\"installed\":[{\"pluginId\":\"synthesis-skills@synthesis-engineering\",\"name\":\"synthesis-skills\",\"version\":\"%s\",\"enabled\":true}]}'\n"
        "fi\n"
        "exit 0\n" % (str(log), version),
        encoding="utf-8",
    )
    path.chmod(0o755)
    return log


def test_update_skips_marketplace_reconfiguration_when_already_current() -> None:
    box = Sandbox()
    try:
        version = onboard.source_plugin_version()
        log = _logging_client(box, version)
        box.seed_currency()
        known = box.home / ".claude" / "plugins" / "known_marketplaces.json"
        known.parent.mkdir(parents=True)
        known.write_text(
            json.dumps({"synthesis-engineering": {"source": {"source": "github", "repo": "synthesisengineering/synthesis-skills", "ref": "stable"}}}),
            encoding="utf-8",
        )
        env = {"SYNTHESIS_CLAUDE_BIN": str(box.root / "logging-client")}
        proc = box.run_with_env(env, "update", "--json", expect=0)
        data = json.loads(proc.stdout)
        ecosystem = [step for step in data["steps"] if step["phase"] == "ecosystem"]
        assert ecosystem and ecosystem[0]["status"] == "ok" and "no refresh needed" in ecosystem[0]["detail"], ecosystem
        assert "marketplace remove" not in log.read_text(encoding="utf-8")

        known.write_text(
            json.dumps({"synthesis-engineering": {"source": {"source": "github", "repo": "synthesisengineering/synthesis-skills", "ref": "main"}}}),
            encoding="utf-8",
        )
        box.run_with_env(env, "update", "--json", expect=0)
        assert "marketplace remove synthesis-engineering" in log.read_text(encoding="utf-8")

        log.write_text("", encoding="utf-8")
        known.write_text(
            json.dumps({"synthesis-engineering": {"source": {"source": "github", "repo": "synthesisengineering/synthesis-skills", "ref": "stable"}}}),
            encoding="utf-8",
        )
        box.run_with_env(env, "update", "--policy-transition", "--json", expect=0)
        assert "marketplace remove synthesis-engineering" in log.read_text(encoding="utf-8")
    finally:
        shutil.rmtree(box.root, ignore_errors=True)


def test_configured_marketplace_ref_reads_both_clients(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(onboard, "HOME", tmp_path)
    assert onboard.configured_marketplace_ref("claude") is None
    known = tmp_path / ".claude" / "plugins" / "known_marketplaces.json"
    known.parent.mkdir(parents=True)
    known.write_text(json.dumps({"synthesis-engineering": {"source": {"repo": "synthesisengineering/synthesis-skills", "ref": "v9.8.7"}}}), encoding="utf-8")
    assert onboard.configured_marketplace_ref("claude") == "v9.8.7"
    config = tmp_path / ".codex" / "config.toml"
    config.parent.mkdir(parents=True)
    config.write_text('[marketplaces.synthesis-engineering]\nsource_type = "git"\nsource = "https://github.com/synthesisengineering/synthesis-skills.git"\nref = "stable"\n\n[features]\nhooks = true\n', encoding="utf-8")
    assert onboard.configured_marketplace_ref("codex") == "stable"


# ---------------------------------------------------------------------------
# AR-113 — policy transfers are not aborted transactions
# ---------------------------------------------------------------------------

def _pin_active(tmp_path: Path, monkeypatch) -> Path:
    release_root = tmp_path / "release"
    release_root.mkdir(exist_ok=True)
    (release_root / "onboard.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    active = tmp_path / "active.json"
    active.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "version": "9.8.7",
                "channel": "pin",
                "ref": "v9.8.7",
                "commit": "1" * 40,
                "tree": "2" * 40,
                "content_digest": "3" * 64,
                "digest_algorithm": system_contract.DIGEST_ALGORITHM,
                "tree_policy": system_contract.TREE_POLICY,
                "source_url": "https://example.test/synthesis-skills.git",
                "resolved_at": "2026-09-02T00:00:00Z",
                "release_root": str(release_root.resolve()),
            }
        ) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SYNTHESIS_ACTIVE_DESCRIPTOR", str(active))
    return active


def test_legacy_update_transfers_policy_without_recording_an_aborted_transaction(tmp_path: Path, monkeypatch) -> None:
    _pin_active(tmp_path, monkeypatch)
    home = tmp_path / "home"
    legacy = home / ".synthesis" / "onboarding" / "receipts.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_text(json.dumps({"version": 2, "plugin_policy": {"channel": "stable", "version_pin": None}, "runs": []}), encoding="utf-8")
    monkeypatch.setattr(synthesis_cli.onboard, "resolve_client", lambda name: "/fixture/" + name if name == "codex" else None)
    monkeypatch.setattr(synthesis_cli.onboard, "plugin_present", lambda client, binary: True)
    transfers = []
    monkeypatch.setattr(
        synthesis_cli, "_run_release_bootstrap",
        lambda argv, active, channel, version_pin: transfers.append((active["channel"], channel, version_pin)) or 0,
    )
    monkeypatch.delenv("SYNTHESIS_BOOTSTRAP_RESOLVED", raising=False)
    state = system_contract.SystemState(home=home)
    assert synthesis_cli.main(["update"], state=state, engine_runner=lambda _argv: 0) == 0
    assert transfers == [("pin", "stable", None)]
    assert state.read_observation()["transactions"] == []


def test_resolved_bootstrap_refuses_instead_of_looping_on_a_policy_mismatch(tmp_path: Path, monkeypatch, capsys) -> None:
    _pin_active(tmp_path, monkeypatch)
    state = system_contract.SystemState(home=tmp_path / "home")
    desired = system_contract.default_desired_state("skills-only", ["codex"], "stable")
    state.run_transaction("setup", desired, lambda _tx: {})
    # The bootstrap was asked for stable and still activated a pin: running
    # it again with the same request would loop forever.
    monkeypatch.setenv("SYNTHESIS_BOOTSTRAP_RESOLVED", "1")
    monkeypatch.setenv("SYNTHESIS_ONBOARD_CHANNEL", "stable")
    monkeypatch.delenv("SYNTHESIS_ONBOARD_VERSION_PIN", raising=False)
    transfers = []
    monkeypatch.setattr(synthesis_cli, "_run_release_bootstrap", lambda *args: transfers.append(args) or 0)
    assert synthesis_cli.main(["update"], state=state, engine_runner=lambda _argv: 0) == 2
    assert transfers == []
    assert len(state.read_observation()["transactions"]) == 1
    assert "activated" in capsys.readouterr().err


def test_setup_policy_transfer_without_an_organization_records_no_transaction(tmp_path: Path, monkeypatch) -> None:
    _pin_active(tmp_path, monkeypatch)
    transfers = []
    monkeypatch.setattr(
        synthesis_cli, "_run_release_bootstrap",
        lambda argv, active, channel, version_pin: transfers.append((active["channel"], channel, version_pin)) or 0,
    )
    state = system_contract.SystemState(home=tmp_path / "home")
    assert synthesis_cli.main(
        ["setup", "--profile", "skills-only", "--clients", "codex", "--channel", "stable"],
        state=state, engine_runner=lambda _argv: 0,
    ) == 0
    assert transfers == [("pin", "stable", None)]
    assert state.read_observation()["transactions"] == []


# ---------------------------------------------------------------------------
# AR-114 — uninstall reports what remains and can purge it
# ---------------------------------------------------------------------------

def _verified_uninstall(_argv: list[str]) -> dict:
    return _engine_result(0, steps=[{"phase": "uninstall-verification", "status": "ok", "uninstall_verified": True}])


def _populate_installation(state: system_contract.SystemState) -> dict[str, Path]:
    paths = {
        "launcher": state.launcher_path,
        "active": state.state_dir / "active-release.json",
        "releases": state.cache_dir / "releases" / ("a" * 64),
        "acquisition": state.cache_dir / "acquisition" / "synthesis-skills.git",
        "config": state.desired_path,
    }
    for name, path in paths.items():
        if name in ("releases", "acquisition"):
            path.mkdir(parents=True, exist_ok=True)
            (path / "marker").write_text("x\n", encoding="utf-8")
            os.chmod(path, 0o555)
        elif name == "config":
            continue
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            marker = system_contract.LAUNCHER_MARK if name == "launcher" else "fixture"
            path.write_text("#!/bin/sh\n%s\n" % marker, encoding="utf-8")
    return paths


def test_uninstall_reports_retained_paths_and_purge_removes_them(tmp_path: Path, capsys) -> None:
    state = system_contract.SystemState(home=tmp_path / "home")
    desired = system_contract.default_desired_state("skills-only", ["codex"], "stable")
    state.run_transaction("setup", desired, lambda _tx: {})
    paths = _populate_installation(state)
    assert synthesis_cli.main(["uninstall", "--json"], state=state, engine_runner=_verified_uninstall) == 0
    payload = json.loads(capsys.readouterr().out)
    retained = payload["details"]["retained"]
    for name in ("launcher", "active", "config"):
        assert str(paths[name]) in retained, name
    assert str(state.state_dir) in retained
    assert paths["launcher"].exists()

    assert synthesis_cli.main(["uninstall", "--purge", "--json"], state=state, engine_runner=_verified_uninstall) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["purged"]
    assert not paths["launcher"].exists()
    assert not state.cache_dir.exists()
    assert not state.config_dir.exists()
    assert not state.state_dir.exists()
    backups = sorted((tmp_path / "home" / ".synthesis" / "onboarding" / "backups").glob("*/observations.json"))
    assert backups, "purge must archive the observation history first"


def test_purge_refuses_when_removal_is_not_verified(tmp_path: Path, capsys) -> None:
    state = system_contract.SystemState(home=tmp_path / "home")
    desired = system_contract.default_desired_state("skills-only", ["codex"], "stable")
    state.run_transaction("setup", desired, lambda _tx: {})
    paths = _populate_installation(state)
    unverified = _engine_result(0, steps=[], counts={"ok": 1})
    assert synthesis_cli.main(["uninstall", "--purge", "--json"], state=state, engine_runner=lambda _argv: unverified) == 2
    assert paths["launcher"].exists()
    assert state.desired_path.exists()
    assert state.read_desired()["enabled"] is True


def test_uninstall_human_output_lists_retained_paths(tmp_path: Path, capsys) -> None:
    state = system_contract.SystemState(home=tmp_path / "home")
    desired = system_contract.default_desired_state("skills-only", ["codex"], "stable")
    state.run_transaction("setup", desired, lambda _tx: {})
    _populate_installation(state)
    assert synthesis_cli.main(["uninstall"], state=state, engine_runner=_verified_uninstall) == 0
    text = capsys.readouterr().out
    assert "Retained" in text and "--purge" in text


# ---------------------------------------------------------------------------
# AR-115 and AR-118 — platform and client remediation
# ---------------------------------------------------------------------------

def test_unknown_platforms_are_reported_as_unsupported(monkeypatch) -> None:
    assert onboard.platform_family("freebsd13", environ={}, proc_version="") == "unsupported"
    assert onboard.platform_family("win32", environ={}, proc_version="") == "native-windows"
    monkeypatch.setattr(onboard.sys, "platform", "freebsd13")
    report = onboard.Report(as_json=True)
    assert onboard.phase_preflight(report, ["claude"]) is None
    assert "unsupported platform" in report.steps[0]["detail"]
    assert "WSL" not in report.steps[0]["detail"]


def test_missing_selected_client_names_the_remediation() -> None:
    box = Sandbox()
    try:
        client = box.fake_client()
        desired = system_contract.default_desired_state("skills-only", ["claude", "codex"], "stable")
        desired_path = box.root / "desired.json"
        desired_path.write_text(json.dumps(desired), encoding="utf-8")
        box.seed_currency()
        proc = box.run_with_env(
            {"SYNTHESIS_CLAUDE_BIN": str(client)},
            "update", "--desired-state", str(desired_path), "--json",
            expect=1,
        )
        data = json.loads(proc.stdout)
        actions = [step for step in data["steps"] if step["status"] == "action-needed"]
        assert actions and "synthesis setup --clients claude" in (actions[0].get("hint") or ""), actions
    finally:
        shutil.rmtree(box.root, ignore_errors=True)


def test_user_local_codex_is_a_well_known_client_path() -> None:
    assert onboard.HOME / ".local/bin/codex" in onboard.CLIENT_WELL_KNOWN["codex"]


# ---------------------------------------------------------------------------
# AR-116 — the bootstrap validates the command line before activating
# ---------------------------------------------------------------------------

def test_bootstrap_refuses_an_invalid_command_line_before_activation(tmp_path: Path, monkeypatch, capsys) -> None:
    checkout = release_repo(tmp_path)
    launcher = tmp_path / "bin" / "synthesis"
    active = tmp_path / "state" / "active.json"
    calls = []
    monkeypatch.setattr(bootstrap.subprocess, "call", lambda command, env=None: calls.append(command) or 0)
    code = bootstrap.main(
        [
            "--checkout", str(checkout), "--releases-dir", str(tmp_path / "releases"),
            "--launcher", str(launcher), "--active-descriptor", str(active),
            "--channel", "stable", "--ref", "stable",
            "--source-url", "https://example.test/synthesis-skills.git",
            "--", "update", "--channel", "edge",
        ]
    )
    assert code == 2
    assert not launcher.exists() and not active.exists()
    assert calls == []
    assert "refused" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# AR-117 — dead schema-1 paths are gone
# ---------------------------------------------------------------------------

def test_dead_schema_one_code_is_removed() -> None:
    for name in ("TOP_KEYS", "SKILLS_REPO_KEYS", "KB_KEYS", "MIGRATION_KEYS", "phase_migrations"):
        assert not hasattr(onboard, name), name
    source = (SCRIPTS / "onboard.py").read_text(encoding="utf-8")
    assert source.count("def workspace_agents_md(") == 1


# ---------------------------------------------------------------------------
# AR-119 and AR-124 — public prose says what the commands do
# ---------------------------------------------------------------------------

def test_public_prose_states_preconditions_and_doctor_side_effects() -> None:
    quick = (REPO_ROOT / "skills/synthesis-quick-answers/SKILL.md").read_text(encoding="utf-8")
    assert "onboard.sh" in quick and "synthesis workspace ensure" in quick
    onboarding = (REPO_ROOT / "skills/synthesis-onboarding/SKILL.md").read_text(encoding="utf-8")
    assert "plugin-currency.json" in onboarding
    assert "--purge" in onboarding
    assert 'version: "%s"' % synthesis_cli.ENGINE_VERSION in onboarding


def test_release_surfaces_agree_and_public_commands_are_pinned() -> None:
    """The version surfaces agree with each other and the README installs stable.

    Red at 4.92.1 on the README assertions: the native plugin commands still
    installed from the default branch. The coherence assertions derive the
    version from the manifests so a later release cannot fail this fixture
    by existing.
    """
    manifests = {
        json.loads((REPO_ROOT / path).read_text(encoding="utf-8"))["version"]
        for path in (".claude-plugin/plugin.json", ".codex-plugin/plugin.json")
    }
    assert len(manifests) == 1
    version = manifests.pop()
    changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    top = next(line for line in changelog.splitlines() if line.startswith("## ["))
    assert top.startswith(f"## [{version}] - ")
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert f"Release **{version}**" in readme
    assert "codex plugin marketplace add synthesisengineering/synthesis-skills --ref stable" in readme
    assert "claude plugin marketplace add synthesisengineering/synthesis-skills@stable" in readme
    assert "codex plugin marketplace add synthesisengineering/synthesis-skills\n" not in readme
    assert "claude plugin marketplace add synthesisengineering/synthesis-skills\n" not in readme
    assert "synthesis uninstall --purge" in readme
    skill = (SCRIPTS.parent / "SKILL.md").read_text(encoding="utf-8")
    assert f'version: "{onboard.ENGINE_VERSION}"' in skill
    assert synthesis_cli.ENGINE_VERSION == onboard.ENGINE_VERSION

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

SPEC = importlib.util.spec_from_file_location("checkpoint_refresh", Path(__file__).with_name("refresh.py"))
refresh = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(refresh)
NATIVE = "01990000-0000-7000-8000-000000000001"


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    for key in ("SYNTHESIS_CLIENT_SESSION_REF", "CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_HOST_SESSION_ID", "CLAUDECODE"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / ".codex"))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / ".claude"))
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.name", "Fixture")
    git(repo, "config", "user.email", "fixture@example.invalid")
    hooks = tmp_path / "empty-hooks"
    hooks.mkdir()
    git(repo, "config", "core.hooksPath", str(hooks))
    project = repo / "projects" / "alpha"
    write(repo / "projects" / "index.yaml", "projects:\n  - id: alpha\n    status: active\n"
        "  - id: example-maintenance\n    status: active\n  - id: different-maintenance\n    status: active\n")
    write(project / "CONTEXT.md", "# Context\n\n**Controlling plan:** [plan](resources/artifacts/plan.md)\n")
    write(project / "resources" / "artifacts" / "plan.md", "# Plan\nprivate project prose must remain local\n")
    write(project / "REFERENCE.md", "# Reference\nprivate unrelated facts\n")
    write(project / "sessions" / "2026-09.md", "# Session history\n")
    git(repo, "add", "projects")
    git(repo, "commit", "-m", "Fixture")
    installed = tmp_path / "plugin"
    for client in ("claude", "codex"):
        write(installed / f".{client}-plugin" / "plugin.json", json.dumps({"name": "synthesis-skills", "version": "1.2.3"}))
    for skill in refresh.SKILLS:
        write(installed / "skills" / skill / "SKILL.md", "# Installed skill\n")
    state_root = tmp_path / ".synthesis"
    transcript = tmp_path / ".codex" / "sessions" / "native.jsonl"
    write(transcript, json.dumps({"type": "session_meta", "payload": {"id": NATIVE}}) + "\n")
    live = state_root / "agent-conformance" / "live" / "public-sessionstart-codex.json"
    write(live, json.dumps({"session_id": NATIVE, "hook_event_name": "SessionStart", "client": "codex",
        "provenance_env": "codex-transcript", "transcript_path": str(transcript), "transcript_bound_at_record": True,
        "plugin_version": "1.2.3", "plugin_root": str(installed), "recorded_at": datetime.now(timezone.utc).isoformat()}))
    board = state_root / "coordination" / "active-sessions.md"
    write(board, refresh.coordination.template())
    args = SimpleNamespace(project_id="alpha", index=repo / "projects" / "index.yaml", native_session_id=NATIVE,
        client_ref="codex:" + NATIVE, board=board, source_root=installed, installed_root=installed,
        state_root=state_root, campaign=state_root / "checkpoint" / "active-campaign.json", campaign_explicit=False)
    return args, project, live


def enable_campaign(args):
    value = {"schema_version": 1, "id": "REFRESH-FIXTURE-v1", "recipient": "example-maintenance sessions",
             "checks": sorted(refresh.CHECKS), "minimum_plugin_version": "1.2.3"}
    write(args.campaign, json.dumps(value))
    return value


def tree(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob("*") if p.is_file()}


def test_inspection_is_local_and_reports_exact_scope(fixture, monkeypatch, tmp_path):
    args, project, _ = fixture
    before = tree(tmp_path)
    calls = []
    original = subprocess.run

    def trapped(command, *positional, **kwargs):
        calls.append(command)
        assert command[0] == "git", "no client CLI or network subprocess is permitted"
        assert not set(command) & {"fetch", "push", "checkout", "update-ref", "add", "commit"}
        assert os.environ["GIT_OPTIONAL_LOCKS"] == "0"
        return original(command, *positional, **kwargs)

    monkeypatch.setattr(subprocess, "run", trapped)
    monkeypatch.setattr(refresh.coordination, "lease_refresh", lambda *a: pytest.fail("lease refresh"))
    monkeypatch.setattr(refresh.coordination, "locked_update", lambda *a: pytest.fail("coordination write"))
    monkeypatch.setattr(refresh.project_state, "_atomic_json", lambda *a: pytest.fail("state/receipt publication"))
    monkeypatch.setattr(refresh.project_state, "_atomic_text", lambda *a: pytest.fail("project prose write"))
    monkeypatch.setattr(Path, "write_text", lambda *a, **k: pytest.fail("file write"))
    monkeypatch.setattr(Path, "write_bytes", lambda *a, **k: pytest.fail("file write"))
    report, campaign = refresh.inspect(args)
    assert campaign is None and calls
    assert report["overall"] == "READY"
    assert report["agent_reading"] == "NOT_VERIFIED"
    assert report["checks"]["native_runtime"]["status"] == "PASS"
    assert report["checks"]["project_tiers"]["warning_count"] == 1  # legacy structured state absent
    assert "enabled live registry not queried" in report["checks"]["native_runtime"]["scope"]
    assert "private project prose" not in json.dumps(report)
    assert tree(tmp_path) == before


@pytest.mark.parametrize("adopted", [False, True])
def test_refresh_uses_structured_checkpoint_applicability(fixture, adopted):
    args, project, _ = fixture
    if adopted:
        path = project / refresh.project_state.STATE_FILE
        path.write_text('{}\n')
        git(project.parent.parent, "add", "projects")
        git(project.parent.parent, "commit", "-m", "Fixture")
        path.unlink()
        git(project.parent.parent, "add", "-u")
        git(project.parent.parent, "commit", "-m", "Fixture")
    report, _ = refresh.inspect(args)
    target = next(row for row in report["read_targets"] if row["role"] == "structured_state")
    assert target["required"] is adopted
    if adopted:
        assert report["checks"]["structured_checkpoint"]["status"] in {"FAIL", "UNKNOWN"}
        assert report["overall"] != "READY"
    else:
        assert report["checks"]["structured_checkpoint"]["status"] == "NOT_APPLICABLE"


@pytest.mark.parametrize("outcome", ["CONFLICT", "UNKNOWN", "FAIL"])
def test_conflict_reads_no_project_prose(fixture, monkeypatch, outcome):
    args, project, _ = fixture
    record = refresh.project_state.RecoveryReport("alpha", outcome, None, None, None, [], ["private conflict narrative"], {})

    def resolve(*a, **kw):
        assert kw["fetch"] is False and kw["refresh_coordination"] is False and kw["fast_forward_canonical"] is False
        return record

    monkeypatch.setattr(refresh.project_state, "resolve_project", resolve)
    original = refresh.file_evidence
    monkeypatch.setattr(refresh, "file_evidence", lambda path, *a, **k: pytest.fail("project prose read") if path.is_relative_to(project) else original(path, *a, **k))
    monkeypatch.setattr(refresh.project_state, "semantic_issues", lambda *a: pytest.fail("semantic prose read"))
    report, _ = refresh.inspect(args)
    assert report["checks"]["project_tiers"]["code"] == "UNRESOLVED_PROJECT_NO_PROSE_READ"
    assert "private conflict narrative" not in json.dumps(report)


def test_optional_and_required_inputs_stay_separate(fixture):
    args, project, _ = fixture
    (project / "REFERENCE.md").unlink()
    git(project, "add", "-u")
    git(project, "commit", "-m", "Fixture change")
    report, _ = refresh.inspect(args)
    reference = next(t for t in report["read_targets"] if t["role"] == "reference")
    assert reference["status"] == "NOT_PRESENT" and not reference["required"]
    (project / "resources" / "artifacts" / "plan.md").unlink()
    git(project, "add", "-u")
    git(project, "commit", "-m", "Fixture change")
    report, _ = refresh.inspect(args)
    assert report["overall"] == "BLOCKED"
    assert next(t for t in report["read_targets"] if t["role"] == "controlling_plan")["status"] == "FAIL"


def test_explicit_no_plan_declaration_is_absent_not_invalid(fixture):
    """'No active plan' beside a checklist link is absence, not a declaration.

    A CONTEXT.md that says both plans are COMPLETE and links one of them from a
    checklist item declares no controlling plan; the link is a dependency, not
    authority. The controlling_plan target is optional and absent, so the
    project is not blocked over a plan it explicitly does not have.
    """
    args, project, _ = fixture
    write(project / "CONTEXT.md", "# Context\n\n**No active plan — both are COMPLETE:**\n\n"
        "- [x] Fold the [inbox-cleanup plan](../inbox-cleanup/resources/artifacts/plan.md) outcomes into REFERENCE.md\n"
        "- [x] Archive the finished sweep\n")
    git(project, "add", "CONTEXT.md")
    git(project, "commit", "-m", "Fixture change")
    report, _ = refresh.inspect(args)
    target = next(t for t in report["read_targets"] if t["role"] == "controlling_plan")
    assert target["status"] == "NOT_PRESENT" and target["code"] == "OPTIONAL_PLAN_ABSENT"
    assert target["required"] is False
    assert report["checks"]["project_tiers"]["status"] == "PASS"


def test_archived_project_remains_blocked(fixture):
    args, project, _ = fixture
    write(args.index, "projects:\n  - id: alpha\n    status: archived\n    superseded_by: successor\n")
    git(project, "add", "../index.yaml")
    git(project, "commit", "-m", "Fixture change")
    report, _ = refresh.inspect(args)
    assert report["overall"] == "BLOCKED"
    assert report["checks"]["project_status"]["successor_id"] == "successor"


@pytest.mark.parametrize("client_ref,native", [("legacy-seat", NATIVE), ("unknown", "unknown"), ("ccd:local-unjoined", NATIVE)])
def test_unverified_identity_cannot_send(fixture, client_ref, native):
    args, _, _ = fixture
    selected = enable_campaign(args)
    args.client_ref, args.native_session_id = client_ref, native
    report, _ = refresh.inspect(args)
    assert report["checks"]["identity"]["status"] == "UNKNOWN"
    with pytest.raises(refresh.RefreshError, match="identity"):
        refresh.feedback(report, selected, args.board)


def test_current_installed_and_stale_native_are_distinct(fixture):
    args, _, live = fixture
    selected = enable_campaign(args)
    value = json.loads(live.read_text())
    value["plugin_version"] = "1.2.2"
    write(live, json.dumps(value))
    report, _ = refresh.inspect(args)
    assert report["checks"]["installed_parity"]["status"] == "PASS"
    assert report["checks"]["native_runtime"]["status"] == "FAIL"
    assert refresh.feedback(report, selected, args.board)["outcome"] == "APPENDED"


@pytest.mark.parametrize("change", [{"command": "touch unwanted"}, {"schema_version": True}, {"checks": ["arbitrary-command"]}, {"checks": ["recovery", "recovery"]}, {"minimum_plugin_version": "latest"}, {"recipient": "bad\nrecipient"}])
def test_campaign_is_declarative_and_strict(fixture, change):
    args, _, _ = fixture
    value = enable_campaign(args)
    value.update(change)
    write(args.campaign, json.dumps(value))
    with pytest.raises(refresh.RefreshError):
        refresh.inspect(args)


def test_concurrent_feedback_deduplicates_and_allocates_revision(fixture):
    args, _, _ = fixture
    selected = enable_campaign(args)
    report, _ = refresh.inspect(args)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: refresh.feedback(report, selected, args.board), range(4)))
    assert sum(r["outcome"] == "APPENDED" for r in results) == 1
    assert {r["revision"] for r in results} == {1}
    assert args.board.read_text().count(refresh.MARKER) == 1
    report["observed_at"] = "2099-01-01T00:00:00+00:00"
    assert refresh.feedback(report, selected, args.board)["outcome"] == "ALREADY_RECORDED"
    report["checks"]["skill_files"] = refresh.status("FAIL", "INSTALLED_SKILL_FILES_INSPECTED")
    report["overall"] = "BLOCKED"
    result = refresh.feedback(report, selected, args.board)
    assert result["outcome"] == "APPENDED" and result["revision"] == 2


def test_malformed_matching_report_prevents_append(fixture):
    args, _, _ = fixture
    selected = enable_campaign(args)
    report, _ = refresh.inspect(args)
    result = refresh.feedback(report, selected, args.board)
    corrupt = {"report_key": result["report_key"], "revision": True, "result_digest": "bad"}
    with args.board.open("a") as stream:
        stream.write(refresh.MARKER + json.dumps(corrupt) + "\n")
    before = args.board.read_bytes()
    with pytest.raises(refresh.RefreshError):
        refresh.feedback(report, selected, args.board)
    assert args.board.read_bytes() == before


def test_arbitrary_payload_is_omitted(fixture):
    args, _, _ = fixture
    selected = enable_campaign(args)
    report, _ = refresh.inspect(args)
    report["private_reply"] = "UNEXPECTED_FIXTURE_PAYLOAD"
    report["checks"]["private_check"] = {"status": "PASS", "private_reply": "UNEXPECTED_FIXTURE_PAYLOAD"}
    report["checks"]["recovery"]["private_reply"] = "UNEXPECTED_FIXTURE_PAYLOAD"
    refresh.feedback(report, selected, args.board)
    text = args.board.read_text()
    assert "UNEXPECTED_FIXTURE_PAYLOAD" not in text
    assert "private unrelated facts" not in text


def test_untracked_registry_is_refused(fixture):
    args, project, _ = fixture
    git(project, "rm", "--cached", "../index.yaml")
    with pytest.raises(refresh.RefreshError, match="Git tracked"):
        refresh.inspect(args)


def test_malformed_state_reports_failure_without_repair(fixture):
    args, project, _ = fixture
    write(project / "CURRENT_STATE.json", "not-json")
    git(project, "add", "CURRENT_STATE.json")
    git(project, "commit", "-m", "Fixture change")
    report, _ = refresh.inspect(args)
    assert report["overall"] == "BLOCKED"
    assert report["checks"]["structured_hashes"]["code"] == "STRUCTURED_STATE_INVALID"
    assert (project / "CURRENT_STATE.json").read_text() == "not-json"


def test_feedback_refuses_receipt_changed_after_inspection(fixture):
    args, _, live = fixture
    selected = enable_campaign(args)
    report, _ = refresh.inspect(args)
    value = json.loads(live.read_text())
    value["session_id"] = "01990000-0000-7000-8000-000000000002"
    write(live, json.dumps(value))
    with pytest.raises(refresh.RefreshError, match="changed or belongs"):
        refresh.feedback(report, selected, args.board)


def test_recovery_only_campaign_still_checks_native_identity(fixture):
    args, _, _ = fixture
    value = enable_campaign(args)
    value["checks"] = ["recovery"]
    write(args.campaign, json.dumps(value))
    report, selected = refresh.inspect(args)
    assert report["checks"]["native_runtime"]["status"] == "PASS"
    assert refresh.feedback(report, selected, args.board)["outcome"] == "APPENDED"


@pytest.mark.parametrize("surface", ["campaign", "native", "state"])
def test_duplicate_json_keys_are_not_accepted(fixture, surface):
    args, project, live = fixture
    enable_campaign(args)
    if surface == "campaign":
        write(args.campaign, args.campaign.read_text().replace('"schema_version": 1', '"schema_version": 99, "schema_version": 1'))
        with pytest.raises(refresh.RefreshError, match="duplicate"):
            refresh.inspect(args)
    elif surface == "native":
        write(live, live.read_text().replace('"client": "codex"', '"client": "claude", "client": "codex"'))
        report, _ = refresh.inspect(args)
        assert report["checks"]["native_runtime"]["status"] == "FAIL"
    else:
        write(project / "CURRENT_STATE.json", '{"schema_version": 99, "schema_version": 1}')
        git(project, "add", "CURRENT_STATE.json")
        git(project, "commit", "-m", "Fixture change")
        report, _ = refresh.inspect(args)
        assert report["checks"]["structured_hashes"]["status"] == "FAIL"


def test_failed_feedback_retains_complete_local_inspection(fixture, monkeypatch, capsys):
    args, _, _ = fixture
    enable_campaign(args)

    def refuse(*a):
        raise RuntimeError("private transport exception that must not be copied")

    monkeypatch.setattr(refresh.coordination, "locked_update", refuse)
    code = refresh.main(["feedback", "--project-id", args.project_id, "--index", str(args.index), "--client-ref", args.client_ref,
        "--native-session-id", NATIVE, "--source-root", str(args.source_root), "--installed-root", str(args.installed_root), "--state-root", str(args.state_root)])
    output = capsys.readouterr().out
    result = json.loads(output)
    assert code == 2
    assert result["overall"] == "READY"
    assert result["read_targets"] and result["checks"]["native_runtime"]["status"] == "PASS"
    assert result["feedback"]["outcome"] == "NOT_DELIVERED"
    assert "private transport exception" not in output


def test_no_campaign_does_not_send(fixture):
    args, _, _ = fixture
    report, _ = refresh.inspect(args)
    before = args.board.read_bytes()
    assert refresh.feedback(report, None, args.board)["outcome"] == "LOCAL_ONLY"
    assert args.board.read_bytes() == before


def test_cli_no_campaign_ignores_invalid_optional_descriptor(fixture, capsys):
    args, _, _ = fixture
    write(args.campaign, "not JSON")
    code = refresh.main(["inspect", "--project-id", args.project_id, "--index", str(args.index), "--client-ref", args.client_ref,
        "--native-session-id", NATIVE, "--source-root", str(args.source_root), "--installed-root", str(args.installed_root),
        "--state-root", str(args.state_root), "--no-campaign"])
    result = json.loads(capsys.readouterr().out)
    assert code == 0 and result["campaign"] is None


@pytest.mark.parametrize("change", [{"recipient": "different-maintenance sessions"}, {"checks": ["recovery"]}, {"minimum_plugin_version": "1.0.0"}])
def test_campaign_descriptor_change_delivers_next_revision(fixture, change):
    args, _, _ = fixture
    selected = enable_campaign(args)
    report, _ = refresh.inspect(args)
    first = refresh.feedback(report, selected, args.board)
    selected.update(change)
    write(args.campaign, json.dumps(selected))
    newer, validated = refresh.inspect(args)
    second = refresh.feedback(newer, validated, args.board)
    assert second["report_key"] == first["report_key"]
    assert second["outcome"] == "APPENDED" and second["revision"] == 2
    assert first["result_digest"] != second["result_digest"]
    assert report["campaign_descriptor_digest"] != newer["campaign_descriptor_digest"]
    if "recipient" in change:
        assert "### → different-maintenance sessions" in args.board.read_text()


def test_unrelated_malformed_reports_are_counted_without_copying(fixture):
    args, _, _ = fixture
    selected = enable_campaign(args)
    report, _ = refresh.inspect(args)
    bad = ["{\"private_unrelated\": \"unpublished material", "[]", '{"report_key": "other", "revision": true}']
    with args.board.open("a") as stream:
        for value in bad:
            stream.write(refresh.MARKER + value + "\n")
    outcome = refresh.feedback(report, selected, args.board)
    assert outcome["outcome"] == "APPENDED" and outcome["warning_count"] == 3
    assert outcome["malformed_unrelated_records"] == 3
    assert "unpublished material" not in json.dumps(outcome)
    again = refresh.feedback(report, selected, args.board)
    assert again["outcome"] == "ALREADY_RECORDED" and again["warning_count"] == 3


def test_identifiable_malformed_matching_json_still_blocks(fixture):
    args, _, _ = fixture
    selected = enable_campaign(args)
    report, _ = refresh.inspect(args)
    first = refresh.feedback(report, selected, args.board)
    with args.board.open("a") as stream:
        stream.write(refresh.MARKER + '{"report_key": "' + first["report_key"] + '", "broken": \n')
    before = args.board.read_bytes()
    with pytest.raises(refresh.RefreshError, match="matching feedback marker"):
        refresh.feedback(report, selected, args.board)
    assert args.board.read_bytes() == before


def test_claude_delivery_aliases_share_one_logical_report(fixture, monkeypatch, tmp_path):
    args, _, codex_live = fixture
    selected = enable_campaign(args)
    transcript = tmp_path / ".claude" / "projects" / "fixture-workspace" / (NATIVE + ".jsonl")
    write(transcript, json.dumps({"type": "user", "sessionId": NATIVE}) + "\n")
    receipt = json.loads(codex_live.read_text())
    receipt.update(client="claude", provenance_env="claude-transcript", transcript_path=str(transcript))
    write(codex_live.with_name("public-sessionstart-claude.json"), json.dumps(receipt))
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", NATIVE)
    monkeypatch.setenv("CLAUDE_CODE_HOST_SESSION_ID", "local-fixture")
    args.client_ref = "cc:" + NATIVE
    direct, _ = refresh.inspect(args)
    first = refresh.feedback(direct, selected, args.board)
    args.client_ref = "ccd:local-fixture"
    desktop, _ = refresh.inspect(args)
    second = refresh.feedback(desktop, selected, args.board)
    assert desktop["client_ref"] == direct["client_ref"] == "cc:" + NATIVE
    assert desktop["delivery_client_ref"] == "ccd:local-fixture"
    assert direct["delivery_client_ref"] == "cc:" + NATIVE
    assert first["report_key"] == second["report_key"]
    assert first["result_digest"] == second["result_digest"]
    assert second["outcome"] == "ALREADY_RECORDED" and second["revision"] == 1
    assert args.board.read_text().count(refresh.MARKER) == 1
    args.client_ref = "ccd:somebody-else"
    refused, _ = refresh.inspect(args)
    assert refused["checks"]["identity"]["status"] == "UNKNOWN"
    with pytest.raises(refresh.RefreshError, match="identity"):
        refresh.feedback(refused, selected, args.board)


def test_selected_descendant_archive_outweighs_canonical_active_registry(fixture, tmp_path):
    args, project, _ = fixture
    worktree = tmp_path / "descendant"
    git(project, "worktree", "add", "-b", "descendant", str(worktree))
    selected = worktree / "projects" / "alpha"
    write(worktree / "projects" / "index.yaml", "projects:\n  - id: alpha\n    status: archived\n    superseded_by: successor\n")
    write(selected / "CONTEXT.md", "# Context\n\n**Status:** archived\n\n**Controlling plan:** [plan](resources/artifacts/plan.md)\n")
    git(selected, "add", "../index.yaml", "CONTEXT.md")
    git(selected, "commit", "-m", "Fixture archive")
    report, _ = refresh.inspect(args)
    assert "status: active" in args.index.read_text()
    assert report["checks"]["recovery"]["status"] == "PASS"
    assert report["checks"]["recovery"]["selected_path"] == str(selected)
    assert report["project_locator"] == str(project)
    assert report["overall"] == "BLOCKED"
    assert report["checks"]["project_status"]["code"] == "PROJECT_ARCHIVED"
    assert report["checks"]["project_status"]["successor_id"] == "successor"
    assert report["checks"]["project_status"]["registry"] == str(worktree / "projects" / "index.yaml")


def test_selected_structured_archive_cannot_be_reported_active(fixture):
    args, project, _ = fixture
    refresh.project_state.build_operational_state(project, project_id="alpha", phase="archived", status="archived",
        controlling_plan="resources/artifacts/plan.md", accepted_baseline="fixture", next_actions=["Use successor"],
        last_session="2026-09-06", session_id=NATIVE)
    git(project, "add", "CURRENT_STATE.json", "CONTEXT.md")
    git(project, "commit", "-m", "Fixture structured archive")
    report, _ = refresh.inspect(args)
    assert report["overall"] == "BLOCKED"
    assert report["checks"]["project_status"]["code"] == "PROJECT_ARCHIVED"
    assert report["checks"]["project_status"]["status_disagreement"]


def test_historical_archive_prose_does_not_override_active_current_status(fixture):
    args, project, _ = fixture
    write(project / "CONTEXT.md", "# Context\n\n**Status:** active\n\nArchive history: formerly archived, then resumed.\n\n**Controlling plan:** [plan](resources/artifacts/plan.md)\n\n## Historical record\n**Status:** archived\n")
    git(project, "add", "CONTEXT.md")
    git(project, "commit", "-m", "Fixture history")
    report, _ = refresh.inspect(args)
    assert report["overall"] == "READY"
    assert report["checks"]["project_status"]["code"] == "PROJECT_NOT_ARCHIVED"


def routing_registry(args, project, entries, *, explicit=False):
    index = args.index
    if explicit:
        root = project.parents[1] / "recipient-workspace"
        root.mkdir()
        git(root, "init", "-b", "main")
        git(root, "config", "user.name", "Fixture")
        git(root, "config", "user.email", "fixture@example.invalid")
        git(root, "config", "core.hooksPath", str(project.parents[1] / "empty-hooks"))
        index = root / "projects" / "index.yaml"
    source = "  - id: alpha\n    status: archived\n    superseded_by: source-successor\n" if not explicit else ""
    write(index, "projects:\n" + source + entries)
    git(index.parent, "add", "index.yaml")
    git(index.parent, "commit", "-m", "Fixture routing")
    return index


def routed_campaign(args, *, index=None, recipient="old-maintenance sessions"):
    selected = enable_campaign(args)
    selected["recipient"] = recipient
    if index is not None:
        selected["recipient_index"] = str(index)
    write(args.campaign, json.dumps(selected))
    return selected


def feedback_messages(board):
    return [json.loads(line[len(refresh.MARKER):]) for line in board.read_text().splitlines() if line.startswith(refresh.MARKER)]


@pytest.mark.parametrize("client", ["codex", "claude"])
@pytest.mark.parametrize("explicit", [False, True])
def test_successor_feedback_delivers_without_reactivating_source(fixture, monkeypatch, tmp_path, client, explicit):
    args, project, live = fixture
    if client == "claude":
        transcript = tmp_path / ".claude" / "projects" / "fixture" / (NATIVE + ".jsonl")
        write(transcript, json.dumps({"type": "user", "sessionId": NATIVE}) + "\n")
        receipt = json.loads(live.read_text())
        receipt.update(client="claude", provenance_env="claude-transcript", transcript_path=str(transcript))
        write(live.with_name("public-sessionstart-claude.json"), json.dumps(receipt))
        monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", NATIVE)
        args.client_ref = "cc:" + NATIVE
    index = routing_registry(args, project, "  - id: old-maintenance\n    status: archived\n    superseded_by: bridge\n"
        "  - id: bridge\n    status: archived\n    superseded_by: current-maintenance\n"
        "  - id: current-maintenance\n    status: paused\n", explicit=explicit)
    if explicit:
        write(args.index, "projects:\n  - id: alpha\n    status: archived\n    superseded_by: source-successor\n")
        git(project, "add", "../index.yaml")
        git(project, "commit", "-m", "Fixture source")
    routed_campaign(args, index=index if explicit else None)
    report, selected = refresh.inspect(args)
    before = tree(project.parents[1])
    result = refresh.feedback(report, selected, args.board)
    assert result["outcome"] == "APPENDED"
    assert "### → current-maintenance sessions," in args.board.read_text()
    assert report["overall"] == "BLOCKED"
    assert report["project_locator"] == str(project)
    assert report["claim_disposition"] == "UNCHANGED"
    assert tree(project.parents[1]) == before
    assert refresh.coordination.rows(args.board.read_text()) == []  # no seat needed, none acquired
    payload = feedback_messages(args.board)[0]
    assert payload["project_locator"] == str(project) and payload["overall"] == "BLOCKED"
    assert payload["recipient_route"]["chain"] == ["old-maintenance", "bridge", "current-maintenance"]
    assert payload["recipient_route"]["registry"] == str(index)
    assert payload["recipient_route"]["registry_sha256"] == hashlib.sha256(index.read_bytes()).hexdigest()
    from peer_addressing import addressed_to, parse_messages
    messages = parse_messages(args.board.read_text())
    delivered = [m for m in messages if addressed_to(m, set(), "current-maintenance", since="2000-01-01T00:00:00Z")]
    assert len(delivered) == 1 and refresh.MARKER in delivered[0].body
    assert not any(addressed_to(m, set(), "old-maintenance") for m in messages)
    assert refresh.feedback(report, selected, args.board)["outcome"] == "ALREADY_RECORDED"


@pytest.mark.parametrize("entries", [
    "  - id: old-maintenance\n    status: archived\n",
    "  - id: old-maintenance\n    status: archived\n    superseded_by: missing\n",
    "  - id: old-maintenance\n    status: archived\n    superseded_by: old-maintenance\n",
    "  - id: old-maintenance\n    status: archived\n    superseded_by: bridge\n  - id: bridge\n    status: archived\n    superseded_by: old-maintenance\n",
    "  - id: old-maintenance\n    status: archived\n    superseded_by: [first, second]\n",
    "  - id: old-maintenance\n    status: archived\n    superseded_by: first\n    superseded_by: second\n",
    "  - id: old-maintenance\n    status: active\n  - id: old-maintenance\n    status: paused\n",
    "  - id: old-maintenance\n    status: archived\n    superseded_by: terminal\n  - id: terminal\n    status: completed\n",
    "  - id: old-maintenance\n    status: archived\n    superseded_by: target\n  - id: target\n    status: unknown\n",
    "  - id: old-maintenance\n    status: active\n    superseded_by: target\n  - id: target\n    status: active\n",
])
def test_invalid_successor_route_preserves_board_and_local_report(fixture, entries):
    args, project, _ = fixture
    index = routing_registry(args, project, entries)
    routed_campaign(args, index=index)
    report, selected = refresh.inspect(args)
    before = args.board.read_bytes()
    with pytest.raises(refresh.RefreshError, match="recipient"):
        refresh.feedback(report, selected, args.board)
    assert args.board.read_bytes() == before
    assert report["project_locator"] == str(project) and report["read_targets"]


def test_successor_route_change_is_a_new_revision(fixture):
    args, project, _ = fixture
    index = routing_registry(args, project, "  - id: old-maintenance\n    status: active\n")
    routed_campaign(args, index=index)
    report, selected = refresh.inspect(args)
    first = refresh.feedback(report, selected, args.board)
    # Reuse the inspected report: delivery must read the current registry again.
    write(index, "projects:\n  - id: alpha\n    status: archived\n    superseded_by: source-successor\n"
        "  - id: old-maintenance\n    status: archived\n    superseded_by: current-maintenance\n"
        "  - id: current-maintenance\n    status: active\n")
    second = refresh.feedback(report, selected, args.board)
    assert second["report_key"] == first["report_key"]
    assert second["revision"] == 2 and second["result_digest"] != first["result_digest"]
    assert feedback_messages(args.board)[1]["recipient_route"]["chain"] == ["old-maintenance", "current-maintenance"]
    assert refresh.feedback(report, selected, args.board)["outcome"] == "ALREADY_RECORDED"


@pytest.mark.parametrize("kind", ["missing", "untracked", "symlink", "malformed"])
def test_explicit_recipient_registry_never_falls_back(fixture, kind):
    args, project, _ = fixture
    index = routing_registry(args, project, "  - id: old-maintenance\n    status: active\n", explicit=True)
    if kind == "missing":
        index.unlink()
    elif kind == "untracked":
        git(index.parent, "rm", "--cached", "index.yaml")
    elif kind == "symlink":
        index.unlink()
        index.symlink_to(args.index)
    else:
        index.write_text("projects: [broken\n")
    routed_campaign(args, index=index)
    report, selected = refresh.inspect(args)
    before = args.board.read_bytes()
    with pytest.raises(refresh.RefreshError, match="recipient"):
        refresh.feedback(report, selected, args.board)
    assert args.board.read_bytes() == before


@pytest.mark.parametrize("value", ["relative/index.yaml", "", None, [], "../outside"])
def test_recipient_registry_descriptor_requires_absolute_path(fixture, value):
    args, _, _ = fixture
    selected = enable_campaign(args)
    selected["recipient_index"] = value
    write(args.campaign, json.dumps(selected))
    with pytest.raises(refresh.RefreshError, match="recipient"):
        refresh.inspect(args)

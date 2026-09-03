from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).with_name("session_context.py")
SPEC = importlib.util.spec_from_file_location("session_context", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

from coordination_schema import identity_from_uuid  # noqa: E402
import system_contract  # noqa: E402


@pytest.fixture(autouse=True)
def isolate_authoritative_system_state(tmp_path: Path, monkeypatch) -> None:
    """Lifecycle receipt tests must never attach evidence to the real machine."""
    monkeypatch.setenv("SYNTHESIS_HOME", str(tmp_path))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)


def test_next_actions_prefers_unchecked_items() -> None:
    context = (
        "# Context\n\n"
        "## What's Next — Prioritized\n\n"
        "1. [x] Finished first.\n"
        "2. [x] Finished second.\n"
        "3. [ ] Resume live conformance and run\n"
        "   the complete installed-state doctor.\n"
        "4. [ ] Verify handoff.\n"
    )

    assert MODULE.next_actions(context) == [
        "3. [ ] Resume live conformance and run the complete installed-state doctor.",
        "4. [ ] Verify handoff.",
    ]


def test_next_actions_is_empty_when_every_item_is_complete() -> None:
    context = (
        "# Context\n\n"
        "## What's Next\n\n"
        "1. [x] Finished first.\n"
        "2. [x] Finished second\n"
        "   with supporting evidence.\n"
    )

    assert MODULE.next_actions(context) == []


def test_build_includes_active_coordination(tmp_path: Path) -> None:
    board = tmp_path / "active-sessions.md"
    board.write_text(
        "# Coordination\n\n"
        "Schema: v2\n\n"
        "## Active sessions\n\n"
        "| id | agent | machine | project | started | heartbeat | mode | workspace(s) / branch | goal | claimed areas (advisory lock) | context role | status |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|\n"
        "| A | Claude | mac | project-a | now | now | interactive | /tmp/a @ feature/a | work | repo-a/** | owner | active |\n"
        "| B | Codex | mac | project-b | now | now | autonomous | /tmp/b @ feature/b | work | repo-b/** | owner | released |\n\n"
        "## Messages\n\n---\n\n## Protocol\n",
        encoding="utf-8",
    )

    message = MODULE.build(tmp_path / "missing-pointer.json", board)

    assert "session(s): A" in message
    assert "B" not in message
    assert "verify claims before writes" in message


def test_sessionstart_prepends_plugin_update_notice(monkeypatch) -> None:
    monkeypatch.setattr(
        MODULE,
        "sessionstart_notice",
        lambda root: "Synthesis update available: installed plugin 4.73.0; stable channel is 4.74.0.",
    )

    message = MODULE.append_currency_notice(
        "Context integrity: OK.", {"hook_event_name": "SessionStart"}
    )

    assert message.startswith("Synthesis update available:")
    assert message.endswith("Context integrity: OK.")


def test_non_sessionstart_output_has_no_plugin_currency_probe(monkeypatch) -> None:
    def fail(_root):
        raise AssertionError("currency probe should not run")

    monkeypatch.setattr(MODULE, "sessionstart_notice", fail)
    assert MODULE.append_currency_notice("context", {}) == "context"


def test_build_displays_compact_v3_session_identity(tmp_path: Path) -> None:
    board = tmp_path / "active-sessions.md"
    identity = identity_from_uuid(
        "019fff79-5858-7993-a329-b301bccf5d62", legacy_id="AX"
    )
    board.write_text(
        "# Coordination\n\nSchema: v3\n\n## Active sessions\n\n"
        "| session uuid | compact id | speakable id v1 | legacy id | agent | machine | project | started | heartbeat | mode | workspace(s) / branch | goal | claimed areas (advisory lock) | context role | status |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
        f"| {identity.session_uuid} | {identity.compact_id} | {identity.speakable_id} | AX | Codex | mac | project-a | now | now | interactive | /tmp/a @ feature/a | work | repo-a/** | owner | active |\n\n"
        "## Messages\n\n---\n\n## Protocol\n",
        encoding="utf-8",
    )

    message = MODULE.build(tmp_path / "missing-pointer.json", board)

    assert f"session(s): {identity.compact_id}" in message
    assert identity.session_uuid not in message
    assert "AX" not in message


def test_build_without_pointer_explains_automatic_named_project_recovery(
    tmp_path: Path,
) -> None:
    message = MODULE.build(tmp_path / "missing-pointer.json", tmp_path / "no-board.md")

    assert "No active synthesis project pointer is set." in message
    assert "project-state resolver" in message
    assert "projects/index.yaml" in message
    assert "never ask the user to run a context-lifecycle command" in message


def test_skill_documents_workspace_registry_freshness_notice() -> None:
    skill = (MODULE_PATH.parent.parent / "SKILL.md").read_text(encoding="utf-8")

    assert "boundedly audits the immediately discoverable Git-tracked project" in skill
    assert "canonical checkout is behind its fetched upstream" in skill
    assert "registry freshness is not comparable" in skill


def test_build_without_pointer_warns_when_workspace_registry_is_behind(
    tmp_path: Path,
) -> None:
    origin = tmp_path / "origin.git"
    subprocess.run(
        ["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True
    )
    workspace = tmp_path / "workspace"
    canonical = workspace / "ai-knowledge-example"
    canonical.mkdir(parents=True)
    subprocess.run(
        ["git", "init", "-q", "-b", "main", str(canonical)], check=True
    )
    for key, value in (
        ("user.email", "fixture@example.invalid"),
        ("user.name", "Fixture"),
        ("core.hooksPath", "/dev/null"),
    ):
        subprocess.run(
            ["git", "-C", str(canonical), "config", key, value], check=True
        )
    subprocess.run(
        ["git", "-C", str(canonical), "remote", "add", "origin", str(origin)],
        check=True,
    )
    project = canonical / "projects" / "example-project"
    project.mkdir(parents=True)
    (canonical / "projects" / "index.yaml").write_text(
        "projects:\n  - id: example-project\n    status: active\n",
        encoding="utf-8",
    )
    (project / "CONTEXT.md").write_text("**Phase:** Old\n", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(canonical), "add", "projects"], check=True
    )
    subprocess.run(
        ["git", "-C", str(canonical), "commit", "-q", "-m", "initial"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(canonical), "push", "-q", "-u", "origin", "main"],
        check=True,
    )

    isolated = tmp_path / "isolated"
    subprocess.run(
        [
            "git",
            "-C",
            str(canonical),
            "worktree",
            "add",
            "-q",
            "-b",
            "feature/newer",
            str(isolated),
            "origin/main",
        ],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(isolated),
            "branch",
            "-q",
            "--set-upstream-to=origin/main",
        ],
        check=True,
    )
    newer_context = isolated / "projects" / "example-project" / "CONTEXT.md"
    newer_context.write_text("**Phase:** New\n", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(isolated), "add", "projects/example-project/CONTEXT.md"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(isolated), "commit", "-q", "-m", "advance"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(isolated), "push", "-q", "origin", "HEAD:main"],
        check=True,
    )

    message = MODULE.build(
        tmp_path / "missing-pointer.json",
        tmp_path / "no-board.md",
        workspace,
    )

    assert "RECORD STALENESS WARNING" in message
    assert "projects/index.yaml" in message
    assert "1 commit(s) behind fetched origin/main" in message


def test_build_without_pointer_marks_uncomparable_registry_unknown(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    repository = workspace / "ai-knowledge-example"
    projects = repository / "projects"
    projects.mkdir(parents=True)
    (projects / "index.yaml").write_text("projects: []\n", encoding="utf-8")
    subprocess.run(
        ["git", "init", "-q", "-b", "main", str(repository)], check=True
    )

    message = MODULE.build(
        tmp_path / "missing-pointer.json",
        tmp_path / "no-board.md",
        workspace,
    )

    assert "PROJECT REGISTRY FRESHNESS UNKNOWN" in message
    assert "projects/index.yaml" in message
    assert "no upstream configured" in message


def test_build_surfaces_interrupted_local_handoff_without_names(tmp_path: Path) -> None:
    pending = tmp_path / "repo-guard" / "pending"
    pending.mkdir(parents=True)
    (pending / "one.json").write_text(
        json.dumps({"session_id": "session-a", "paths": ["/private/path"]}),
        encoding="utf-8",
    )

    message = MODULE.build(
        tmp_path / "missing-pointer.json",
        tmp_path / "no-board.md",
        pending_handoffs=pending,
    )

    assert "Local continuity: 1 attributed edit manifest" in message
    assert "/private/path" not in message
    assert "interrupted task remains recoverable" in message


def test_build_discovers_stopped_project_from_cwd(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "projects" / "alpha"
    plan = project / "resources" / "artifacts" / "alpha-plan.md"
    plan.parent.mkdir(parents=True)
    plan.write_text("# Plan\n", encoding="utf-8")
    (project / "sessions").mkdir()
    (project / "REFERENCE.md").write_text("# Reference\n", encoding="utf-8")
    (project / "CONTEXT.md").write_text(
        "# Alpha\n\n"
        "**Phase:** Validation\n"
        "**Status:** Active\n\n"
        "[plan](resources/artifacts/alpha-plan.md)\n\n"
        "## What's Next\n\n"
        "- [ ] Resume from durable state.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(MODULE, "record_freshness", lambda path: (True, "current"))

    message = MODULE.build(
        tmp_path / "missing-pointer.json",
        tmp_path / "no-board.md",
        project / "resources",
    )

    assert f"Stopped synthesis project discovered from the task directory: {project}." in message
    assert "Current phase: Validation." in message
    assert "Current status: Active." in message
    assert f"Controlling plan: {plan}." in message
    assert "Resume from durable state" in message


def test_stopped_project_recovery_reads_newer_isolated_worktree(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "-b", "main", str(repo)], check=True, capture_output=True)
    for key, value in (("user.email", "fixture@example.invalid"), ("user.name", "Fixture"), ("core.hooksPath", "/dev/null")):
        subprocess.run(["git", "-C", str(repo), "config", key, value], check=True)
    project = repo / "projects" / "alpha"
    plan = project / "resources" / "artifacts" / "plan.md"
    plan.parent.mkdir(parents=True)
    plan.write_text("# Plan\n", encoding="utf-8")
    (project / "sessions").mkdir()
    (project / "REFERENCE.md").write_text("# Reference\n", encoding="utf-8")
    (project / "CONTEXT.md").write_text(
        "# Alpha\n\n**Phase:** Older\n**Status:** Active\n"
        "**Last session:** 2026-09-02\n\n"
        "[plan](resources/artifacts/plan.md)\n\n"
        "## What's Next\n\n- [ ] old action\n",
        encoding="utf-8",
    )
    (repo / "projects" / "index.yaml").write_text(
        "projects:\n  - id: alpha\n    status: active\n    last_session: '2026-09-02'\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", str(repo), "add", "projects"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "initial"], check=True, capture_output=True)
    newer = tmp_path / "newer"
    subprocess.run(["git", "-C", str(repo), "worktree", "add", "-b", "feature/newer", str(newer)], check=True, capture_output=True)
    newer_context = newer / "projects" / "alpha" / "CONTEXT.md"
    newer_context.write_text(
        newer_context.read_text(encoding="utf-8")
        .replace("**Phase:** Older", "**Phase:** Newer")
        .replace("old action", "new action"),
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", str(newer), "add", "projects/alpha/CONTEXT.md"], check=True)
    subprocess.run(["git", "-C", str(newer), "commit", "-m", "advance"], check=True, capture_output=True)
    monkeypatch.setattr(MODULE, "record_freshness", lambda path: (True, "current"))

    lines: list[str] = []
    MODULE.append_project_context(lines, project, label="Recovered project")
    message = "\n".join(lines)

    assert f"Recovered project: {newer / 'projects' / 'alpha'}." in message
    assert "Current phase: Newer." in message
    assert "new action" in message


def test_build_rejects_incomplete_or_unleased_pointer(
    tmp_path: Path, monkeypatch
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "CONTEXT.md").write_text(
        "**Phase:** 2\n**Status:** Active\n", encoding="utf-8"
    )
    pointer = tmp_path / "active.json"
    pointer.write_text(
        json.dumps({"project": str(project), "plan": "unknown"}),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        MODULE,
        "record_freshness",
        lambda path: (False, "project record is 3 commit(s) behind fetched origin/main"),
    )
    try:
        MODULE.build(pointer, tmp_path / "no-board.md")
    except ValueError as exc:
        assert "missing pointer fields" in str(exc)
    else:
        raise AssertionError("unsafe pointer was injected")


def test_live_receipt_rejects_static_probe(tmp_path: Path) -> None:
    receipt = tmp_path / "receipt.json"

    assert not MODULE.record_live_receipt({}, receipt)
    assert not receipt.exists()


def test_live_receipt_records_real_sessionstart_shape(
    tmp_path: Path, monkeypatch
) -> None:
    receipt = tmp_path / "live" / "receipt.json"
    codex_home = tmp_path / ".codex"
    transcript = codex_home / "sessions" / "live.jsonl"
    transcript.parent.mkdir(parents=True)
    transcript.write_text(
        json.dumps(
            {
                "type": "session_meta",
                "payload": {
                    "id": "019fff79-5858-7993-a329-b301bccf5d31",
                    "session_id": "019fff79-5858-7993-a329-b301bccf5d31",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("PLUGIN_ROOT", str(MODULE.SCRIPTS_DIR.parents[2]))
    payload = {
        "hook_event_name": "SessionStart",
        "session_id": "019fff79-5858-7993-a329-b301bccf5d31",
        "cwd": "/tmp/repo",
        "source": "startup",
        "transcript_path": str(transcript),
    }
    state = system_contract.SystemState()
    version = json.loads(
        (MODULE.SCRIPTS_DIR.parents[2] / ".codex-plugin" / "plugin.json").read_text(
            encoding="utf-8"
        )
    )["version"]
    desired = system_contract.default_desired_state(
        "skills-only", ["codex"], "stable"
    )
    state.run_transaction(
        "setup",
        desired,
        lambda _tx: {
            "release": {
                "schema_version": 1,
                "version": version,
                "channel": "pin",
                "ref": "v%s" % version,
                "commit": "1" * 40,
                "tree": "2" * 40,
                    "content_digest": system_contract.canonical_tracked_tree_digest(
                        MODULE.SCRIPTS_DIR.parents[2],
                        {
                            relative
                            for relative, metadata, _path in system_contract._iter_tree(
                                MODULE.SCRIPTS_DIR.parents[2]
                            )
                            if _path.is_file()
                        },
                    ),
                "digest_algorithm": system_contract.DIGEST_ALGORITHM,
                "tree_policy": system_contract.TREE_POLICY,
                "source_url": "https://example.test/synthesis-skills.git",
                "resolved_at": datetime.now(timezone.utc).isoformat(),
            },
            "source-provenance": {
                "status": "verified",
                "root": str(MODULE.SCRIPTS_DIR.parents[2]),
            },
            "live-loaded": {"status": "restart-required"},
        },
    )

    assert MODULE.record_live_receipt(payload, receipt)
    recorded = json.loads(receipt.read_text(encoding="utf-8"))
    client_receipt = receipt.with_name("receipt-codex.json")
    assert client_receipt.is_file()
    assert json.loads(client_receipt.read_text(encoding="utf-8")) == recorded
    assert recorded["client"] == "codex"
    assert recorded["session_id"] == "019fff79-5858-7993-a329-b301bccf5d31"
    assert recorded["hook_event_name"] == "SessionStart"
    assert recorded["plugin_version"]
    assert recorded["provenance_env"] == "codex-transcript"
    assert recorded["transcript_bound_at_record"] is True
    assert recorded["transcript_path"] == str(transcript)
    assert Path(recorded["plugin_root"]).resolve() == MODULE.SCRIPTS_DIR.parents[2]
    event_path = (
        receipt.parent
        / "receipt-events"
        / "codex"
        / payload["session_id"]
        / f"{recorded['receipt_event_id']}.json"
    )
    assert event_path.is_file()
    assert json.loads(event_path.read_text(encoding="utf-8")) == recorded
    assert not list(receipt.parent.glob("*.tmp"))
    observed = state.read_observation()["transactions"][-1]
    assert observed["live-loaded"]["status"] == "verified"
    assert observed["live-loaded"]["receipts"]["codex"]["session_id"] == payload["session_id"]


def test_live_receipt_preserves_prior_session_when_latest_advances(
    tmp_path: Path, monkeypatch
) -> None:
    receipt = tmp_path / "live" / "public-sessionstart.json"
    codex_home = tmp_path / ".codex"
    first_session = "019fff79-5858-7993-a329-b301bccf5d51"
    second_session = "019fff79-5858-7993-a329-b301bccf5d52"
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    def record(session_id: str) -> None:
        transcript = codex_home / "sessions" / f"{session_id}.jsonl"
        transcript.parent.mkdir(parents=True, exist_ok=True)
        transcript.write_text(
            json.dumps(
                {
                    "type": "session_meta",
                    "payload": {"id": session_id, "session_id": session_id},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        assert MODULE.record_live_receipt(
            {
                "hook_event_name": "SessionStart",
                "session_id": session_id,
                "source": "startup",
                "transcript_path": str(transcript),
            },
            receipt,
        )

    record(first_session)
    first_events = list(
        (receipt.parent / "public-sessionstart-events" / "codex" / first_session)
        .glob("*.json")
    )
    assert len(first_events) == 1
    first_contents = first_events[0].read_bytes()

    record(second_session)

    assert first_events[0].read_bytes() == first_contents
    second_events = list(
        (receipt.parent / "public-sessionstart-events" / "codex" / second_session)
        .glob("*.json")
    )
    assert len(second_events) == 1
    assert (
        json.loads(receipt.read_text(encoding="utf-8"))["session_id"]
        == second_session
    )
    client_latest = receipt.with_name("public-sessionstart-codex.json")
    assert (
        json.loads(client_latest.read_text(encoding="utf-8"))["session_id"]
        == second_session
    )


def test_latest_receipt_pointer_never_moves_backward(tmp_path: Path) -> None:
    destination = tmp_path / "latest.json"
    newer = {
        "receipt_event_id": "019fff79-5858-7993-a329-b301bccf5d71",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    older = {
        "receipt_event_id": "019fff79-5858-7993-a329-b301bccf5d72",
        "recorded_at": (
            datetime.now(timezone.utc) - timedelta(minutes=1)
        ).isoformat(),
    }
    MODULE.atomic_json_write(destination, newer)

    MODULE._write_latest_if_newer(destination, older)

    assert json.loads(destination.read_text(encoding="utf-8")) == newer


def test_live_receipt_rejects_symlinked_event_registry(
    tmp_path: Path, monkeypatch
) -> None:
    receipt = tmp_path / "live" / "public-sessionstart.json"
    receipt.parent.mkdir(parents=True)
    target = tmp_path / "outside-events"
    target.mkdir()
    (receipt.parent / "public-sessionstart-events").symlink_to(
        target, target_is_directory=True
    )
    codex_home = tmp_path / ".codex"
    session_id = "019fff79-5858-7993-a329-b301bccf5d73"
    transcript = codex_home / "sessions" / f"{session_id}.jsonl"
    transcript.parent.mkdir(parents=True)
    transcript.write_text(
        json.dumps({"type": "session_meta", "payload": {"id": session_id}})
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    with pytest.raises(ValueError, match="receipt registry path is unsafe"):
        MODULE.record_live_receipt(
            {
                "hook_event_name": "SessionStart",
                "session_id": session_id,
                "transcript_path": str(transcript),
            },
            receipt,
        )

    assert not receipt.exists()
    assert not list(target.iterdir())


def test_live_receipt_rejects_codex_subagent_transcript(
    tmp_path: Path, monkeypatch
) -> None:
    receipt = tmp_path / "receipt.json"
    codex_home = tmp_path / ".codex"
    root_session_id = "019fff79-5858-7993-a329-b301bccf5d45"
    subagent_id = "01a00767-fe9f-7543-b996-a6bd625f9645"
    transcript = codex_home / "sessions" / "subagent.jsonl"
    transcript.parent.mkdir(parents=True)
    transcript.write_text(
        json.dumps(
            {
                "type": "session_meta",
                "payload": {
                    "id": subagent_id,
                    "session_id": root_session_id,
                    "source": {"subagent": "review"},
                    "thread_source": "subagent",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    assert not MODULE.record_live_receipt(
        {
            "hook_event_name": "SessionStart",
            "session_id": root_session_id,
            "transcript_path": str(transcript),
        },
        receipt,
    )
    assert not receipt.exists()


def test_claude_signal_wins_over_inherited_codex_home(tmp_path: Path, monkeypatch) -> None:
    claude_home = tmp_path / ".claude"
    session_id = "019fff79-5858-7993-a329-b301bccf5d32"
    transcript = claude_home / "projects" / "workspace" / f"{session_id}.jsonl"
    transcript.parent.mkdir(parents=True, exist_ok=True)
    transcript.write_text(
        json.dumps({"sessionId": session_id}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("PLUGIN_ROOT", raising=False)
    monkeypatch.setenv("CODEX_HOME", "/tmp/codex")
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(MODULE.SCRIPTS_DIR.parents[2]))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_home))

    assert MODULE.client_provenance(
        {"transcript_path": str(transcript)},
        session_id,
    ) == ("claude", "claude-transcript")


def test_live_receipt_preserves_claude_event_before_transcript_exists(
    tmp_path: Path, monkeypatch
) -> None:
    receipt = tmp_path / "receipt.json"
    claude_home = tmp_path / ".claude"
    session_id = "019fff79-5858-7993-a329-b301bccf5d34"
    transcript = claude_home / "projects" / "workspace" / f"{session_id}.jsonl"
    transcript.parent.mkdir(parents=True)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_home))

    assert MODULE.record_live_receipt(
        {
            "hook_event_name": "SessionStart",
            "session_id": session_id,
            "cwd": "/tmp/repo",
            "source": "startup",
            "transcript_path": str(transcript),
        },
        receipt,
    )
    recorded = json.loads(receipt.read_text(encoding="utf-8"))
    assert recorded["client"] == "claude"
    assert recorded["provenance_env"] == "claude-transcript"
    assert recorded["transcript_bound_at_record"] is False
    assert receipt.with_name("receipt-claude.json").is_file()

    transcript.write_text(
        json.dumps({"sessionId": session_id}) + "\n",
        encoding="utf-8",
    )
    assert MODULE.client_provenance(
        {"transcript_path": str(transcript)}, session_id
    ) == ("claude", "claude-transcript")


def test_live_receipt_preserves_empty_claude_transcript_until_binding(
    tmp_path: Path, monkeypatch
) -> None:
    receipt = tmp_path / "receipt.json"
    claude_home = tmp_path / ".claude"
    session_id = "019fff79-5858-7993-a329-b301bccf5d37"
    transcript = claude_home / "projects" / "workspace" / f"{session_id}.jsonl"
    transcript.parent.mkdir(parents=True)
    transcript.touch()
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_home))

    assert MODULE.record_live_receipt(
        {
            "hook_event_name": "SessionStart",
            "session_id": session_id,
            "transcript_path": str(transcript),
        },
        receipt,
    )
    recorded = json.loads(receipt.read_text(encoding="utf-8"))
    assert recorded["transcript_bound_at_record"] is False


def test_same_claude_session_retains_pending_and_bound_events(
    tmp_path: Path, monkeypatch
) -> None:
    receipt = tmp_path / "live" / "public-sessionstart.json"
    claude_home = tmp_path / ".claude"
    session_id = "019fff79-5858-7993-a329-b301bccf5d74"
    transcript = claude_home / "projects" / "workspace" / f"{session_id}.jsonl"
    transcript.parent.mkdir(parents=True)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_home))
    payload = {
        "hook_event_name": "SessionStart",
        "session_id": session_id,
        "source": "startup",
        "transcript_path": str(transcript),
    }

    assert MODULE.record_live_receipt(payload, receipt)
    time.sleep(0.002)
    transcript.write_text(
        json.dumps({"sessionId": session_id}) + "\n", encoding="utf-8"
    )
    payload["source"] = "resume"
    assert MODULE.record_live_receipt(payload, receipt)

    event_directory = (
        receipt.parent / "public-sessionstart-events" / "claude" / session_id
    )
    events = list(event_directory.glob("*.json"))
    assert len(events) == 2
    selected = sys.modules["live_receipt"].session_receipt_path(
        receipt.with_name("public-sessionstart-claude.json"),
        "claude",
        session_id,
    )
    assert selected is not None
    selected_payload = json.loads(selected.read_text(encoding="utf-8"))
    assert selected_payload["source"] == "resume"
    assert selected_payload["transcript_bound_at_record"] is True


def test_live_receipt_rejects_conflicting_claude_transcript_without_overwrite(
    tmp_path: Path, monkeypatch
) -> None:
    receipt = tmp_path / "receipt.json"
    receipt.write_text('{"preserve": true}\n', encoding="utf-8")
    claude_home = tmp_path / ".claude"
    session_id = "019fff79-5858-7993-a329-b301bccf5d38"
    transcript = claude_home / "projects" / "workspace" / f"{session_id}.jsonl"
    transcript.parent.mkdir(parents=True)
    transcript.write_text(
        json.dumps({"sessionId": "019fff79-5858-7993-a329-b301bccf5d99"})
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_home))

    assert not MODULE.record_live_receipt(
        {
            "hook_event_name": "SessionStart",
            "session_id": session_id,
            "transcript_path": str(transcript),
        },
        receipt,
    )
    assert json.loads(receipt.read_text(encoding="utf-8")) == {"preserve": True}


def test_live_receipt_rejects_transcript_that_conflicts_during_recording(
    tmp_path: Path, monkeypatch
) -> None:
    receipt = tmp_path / "receipt.json"
    receipt.write_text('{"preserve": true}\n', encoding="utf-8")
    claude_home = tmp_path / ".claude"
    session_id = "019fff79-5858-7993-a329-b301bccf5d42"
    transcript = claude_home / "projects" / "workspace" / f"{session_id}.jsonl"
    transcript.parent.mkdir(parents=True)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_home))
    states = iter(("pending", "conflicting"))
    monkeypatch.setattr(MODULE, "transcript_binding_state", lambda *args: next(states))

    assert not MODULE.record_live_receipt(
        {
            "hook_event_name": "SessionStart",
            "session_id": session_id,
            "transcript_path": str(transcript),
        },
        receipt,
    )
    assert json.loads(receipt.read_text(encoding="utf-8")) == {"preserve": True}


def test_deferred_claude_receipt_rejects_lexical_parent_directory(
    tmp_path: Path, monkeypatch
) -> None:
    receipt = tmp_path / "receipt.json"
    claude_home = tmp_path / ".claude"
    session_id = "019fff79-5858-7993-a329-b301bccf5d43"
    transcript = claude_home / "projects" / ".." / f"{session_id}.jsonl"
    claude_home.mkdir()
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_home))

    assert not MODULE.record_live_receipt(
        {
            "hook_event_name": "SessionStart",
            "session_id": session_id,
            "transcript_path": str(transcript),
        },
        receipt,
    )
    assert not receipt.exists()


def test_live_receipt_rejects_claude_subagent_transcript(
    tmp_path: Path, monkeypatch
) -> None:
    receipt = tmp_path / "receipt.json"
    claude_home = tmp_path / ".claude"
    session_id = "019fff79-5858-7993-a329-b301bccf5d39"
    transcript = (
        claude_home
        / "projects"
        / "workspace"
        / session_id
        / "subagents"
        / "agent-a1.jsonl"
    )
    transcript.parent.mkdir(parents=True)
    transcript.write_text(
        json.dumps({"sessionId": session_id, "agentId": "a1"}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_home))

    assert not MODULE.record_live_receipt(
        {
            "hook_event_name": "SessionStart",
            "session_id": session_id,
            "transcript_path": str(transcript),
        },
        receipt,
    )
    assert not receipt.exists()


def test_live_receipt_rejects_symlinked_claude_root_transcript(
    tmp_path: Path, monkeypatch
) -> None:
    receipt = tmp_path / "receipt.json"
    claude_home = tmp_path / ".claude"
    session_id = "019fff79-5858-7993-a329-b301bccf5d41"
    target = tmp_path / "real.jsonl"
    target.write_text(
        json.dumps({"sessionId": session_id}) + "\n",
        encoding="utf-8",
    )
    transcript = claude_home / "projects" / "workspace" / f"{session_id}.jsonl"
    transcript.parent.mkdir(parents=True)
    transcript.symlink_to(target)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_home))

    assert not MODULE.record_live_receipt(
        {
            "hook_event_name": "SessionStart",
            "session_id": session_id,
            "transcript_path": str(transcript),
        },
        receipt,
    )
    assert not receipt.exists()


def test_deferred_claude_receipt_rejects_path_outside_client_root(
    tmp_path: Path, monkeypatch
) -> None:
    receipt = tmp_path / "receipt.json"
    claude_home = tmp_path / ".claude"
    claude_home.mkdir()
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_home))

    assert not MODULE.record_live_receipt(
        {
            "hook_event_name": "SessionStart",
            "session_id": "019fff79-5858-7993-a329-b301bccf5d35",
            "transcript_path": str(tmp_path / "outside.jsonl"),
        },
        receipt,
    )
    assert not receipt.exists()


def test_live_receipt_rejects_forged_payload_without_client_owned_roots(
    tmp_path: Path, monkeypatch
) -> None:
    receipt = tmp_path / "receipt.json"
    monkeypatch.setenv("PLUGIN_ROOT", "/tmp/not-the-executing-plugin")

    assert not MODULE.record_live_receipt(
        {
            "hook_event_name": "SessionStart",
            "session_id": "019fff79-5858-7993-a329-b301bccf5d31",
            "transcript_path": str(tmp_path / ".codex" / "sessions" / "fake.jsonl"),
        },
        receipt,
    )
    assert not receipt.exists()


def test_live_receipt_rejects_existing_transcript_for_another_session(
    tmp_path: Path, monkeypatch
) -> None:
    receipt = tmp_path / "receipt.json"
    codex_home = tmp_path / ".codex"
    transcript = codex_home / "sessions" / "other.jsonl"
    transcript.parent.mkdir(parents=True)
    transcript.write_text(
        json.dumps(
            {
                "type": "session_meta",
                "payload": {"id": "019fff79-5858-7993-a329-b301bccf5d99"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    assert not MODULE.record_live_receipt(
        {
            "hook_event_name": "SessionStart",
            "session_id": "019fff79-5858-7993-a329-b301bccf5d31",
            "transcript_path": str(transcript),
        },
        receipt,
    )
    assert not receipt.exists()



# --- receipt before context; a pointer is a cache, not authority (4.93.2) -----------------------

def _drive_main(monkeypatch, capsys, tmp_path, *, pointer_text=None, build_error=None):
    """Run main() in-process with a stubbed receipt recorder and, optionally, a
    forced context failure; return (exit code, additionalContext, call order)."""
    import io

    calls: list[str] = []
    pointer = tmp_path / "active-project.json"
    if pointer_text is not None:
        pointer.write_text(pointer_text, encoding="utf-8")
    real_build = MODULE.build

    def recording_build(pointer_arg, board, cwd, *args, **kwargs):
        calls.append("build")
        if build_error is not None:
            raise build_error
        return real_build(pointer_arg, board, cwd, *args, **kwargs)

    monkeypatch.setattr(MODULE, "build", recording_build)
    monkeypatch.setattr(
        MODULE, "record_live_receipt", lambda payload, destination: calls.append("receipt") or True
    )
    monkeypatch.setattr(MODULE, "append_currency_notice", lambda message, payload: message)
    monkeypatch.setattr(MODULE, "append_inbox", lambda message, payload, board: message)
    payload = {
        "hook_event_name": "SessionStart",
        "session_id": "019fff79-5858-7993-a329-b301bccf5d31",
        "cwd": str(tmp_path),
        "source": "resume",
    }
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "session_context.py",
            "--format",
            "claude",
            "--active-project-file",
            str(pointer),
            "--coordination-board",
            str(tmp_path / "no-board.md"),
            "--live-receipt",
            str(tmp_path / "receipt.json"),
        ],
    )
    code = MODULE.main()
    out = capsys.readouterr().out.strip()
    context = json.loads(out)["hookSpecificOutput"]["additionalContext"] if out else ""
    return code, context, calls


def test_main_records_the_receipt_before_building_context(monkeypatch, capsys, tmp_path) -> None:
    """The receipt proves the client delivered the event; nothing that happens
    while building context may erase it, so it is recorded first."""
    code, context, calls = _drive_main(monkeypatch, capsys, tmp_path)

    assert code == 0
    assert calls[0] == "receipt" and "build" in calls
    assert "No active synthesis project pointer is set." in context


def test_main_ignores_a_pointer_it_cannot_validate_with_a_notice(monkeypatch, capsys, tmp_path) -> None:
    """2026-09-03: a pointer set by another session named a project in a
    worktree eleven commits behind; the hook failed closed before recording
    and every Claude session on the machine lost its receipt. The pointer is
    a cache: an unvalidatable one is ignored, said so, and never injected."""
    project = tmp_path / "project"
    project.mkdir()
    (project / "CONTEXT.md").write_text("**Phase:** 2\n**Status:** Active\n", encoding="utf-8")
    code, context, calls = _drive_main(
        monkeypatch, capsys, tmp_path,
        pointer_text=json.dumps({"project": str(project), "plan": "unknown"}),
    )

    assert code == 0
    assert calls == ["receipt", "build", "build"]
    assert context.startswith("Active-project pointer ignored: ")
    assert "not authority for this one" in context
    assert "No active synthesis project pointer is set." in context
    assert "Active synthesis project" not in context, "the unvalidated pointer's project was injected"


def test_main_still_fails_closed_on_a_non_pointer_failure(monkeypatch, capsys, tmp_path) -> None:
    """Ignoring the pointer must not become ignoring every failure: with no
    pointer in play, a context failure still exits 2 — after the receipt."""
    code, context, calls = _drive_main(
        monkeypatch, capsys, tmp_path,
        build_error=ValueError("coordination board schema is invalid"),
    )

    assert code == 2
    assert calls == ["receipt", "build"]
    assert context == ""

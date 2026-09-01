from __future__ import annotations

import importlib.util
import json
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

from coordination_schema import identity_from_uuid


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
    assert "resolve it from the git-tracked projects/index.yaml" in message
    assert "never ask the user to run a context-lifecycle command" in message


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

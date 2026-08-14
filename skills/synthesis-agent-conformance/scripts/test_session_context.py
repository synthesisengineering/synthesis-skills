from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("session_context.py")
SPEC = importlib.util.spec_from_file_location("session_context", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


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
    transcript.write_text("", encoding="utf-8")
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
    assert recorded["transcript_path"] == str(transcript)
    assert Path(recorded["plugin_root"]).resolve() == MODULE.SCRIPTS_DIR.parents[2]
    assert not list(receipt.parent.glob("*.tmp"))


def test_claude_signal_wins_over_inherited_codex_home(tmp_path: Path, monkeypatch) -> None:
    claude_home = tmp_path / ".claude"
    transcript = claude_home / "projects" / "session.jsonl"
    transcript.parent.mkdir(parents=True, exist_ok=True)
    transcript.write_text("", encoding="utf-8")
    monkeypatch.delenv("PLUGIN_ROOT", raising=False)
    monkeypatch.setenv("CODEX_HOME", "/tmp/codex")
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(MODULE.SCRIPTS_DIR.parents[2]))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_home))

    assert MODULE.client_provenance(
        {"transcript_path": str(transcript)}
    ) == ("claude", "claude-transcript")


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

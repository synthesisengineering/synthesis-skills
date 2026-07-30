from __future__ import annotations

import importlib.util
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

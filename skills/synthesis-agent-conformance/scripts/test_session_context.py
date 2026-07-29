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


def test_build_includes_active_coordination(tmp_path: Path) -> None:
    board = tmp_path / "active-sessions.md"
    board.write_text(
        "# Coordination\n\n"
        "## Active sessions\n\n"
        "| id | agent | started | mode | goal | claimed areas (advisory lock) | status |\n"
        "|----|-------|---------|------|------|--------------------------------|--------|\n"
        "| A | Claude | now | interactive | work | repo-a/** | active |\n"
        "| B | Codex | now | autonomous | work | repo-b/** | released |\n\n"
        "## Messages\n\n---\n\n## Protocol\n",
        encoding="utf-8",
    )

    message = MODULE.build(tmp_path / "missing-pointer.json", board)

    assert "session(s): A" in message
    assert "B" not in message
    assert "verify claims before writes" in message

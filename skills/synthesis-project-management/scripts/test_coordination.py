from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("coordination.py")
SPEC = importlib.util.spec_from_file_location("coordination", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def args(board: Path, **values):
    return type("Args", (), {"board": board, **values})()


def test_claim_conflict_message_and_release(tmp_path: Path) -> None:
    board = tmp_path / "coordination" / "active-sessions.md"
    first = args(
        board,
        id="A",
        agent="Claude",
        mode="autonomous",
        goal="One",
        area=["repo/**"],
    )
    assert MODULE.command_claim(first) == 0

    second = args(
        board,
        id="B",
        agent="Codex",
        mode="interactive",
        goal="Two",
        area=["repo/file.md"],
    )
    assert MODULE.command_claim(second) == 10

    message = args(board, sender="B", to="A", text="Please release repo/file.md.")
    assert MODULE.command_message(message) == 0
    assert "Please release repo/file.md." in board.read_text(encoding="utf-8")

    assert MODULE.command_release(args(board, id="A")) == 0
    assert MODULE.command_claim(second) == 0
    table = MODULE.rows(board.read_text(encoding="utf-8"))
    assert next(row for row in table if MODULE.plain(row[0]) == "A")[6] == "released"
    assert next(row for row in table if MODULE.plain(row[0]) == "B")[6] == "active"


def test_nonoverlapping_claims(tmp_path: Path) -> None:
    board = tmp_path / "active-sessions.md"
    for session_id, area in (("A", "repo-a/**"), ("B", "repo-b/**")):
        command = args(
            board,
            id=session_id,
            agent=session_id,
            mode="autonomous",
            goal="test",
            area=[area],
        )
        assert MODULE.command_claim(command) == 0

    assert len(MODULE.rows(board.read_text(encoding="utf-8"))) == 2

"""Explicit team enrollment uses the existing board CAS; labels grant no claims."""

from pathlib import Path
import hashlib
import json
import sys
from types import SimpleNamespace
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import coordination as c
import team_contract as tc
from test_team_contract import contract


def args(board, **kw):
    return SimpleNamespace(board=board, **kw)


def setup(tmp_path):
    board = tmp_path / "board.md"
    board.write_text(c.template())
    source = tmp_path / "team.json"
    source.write_text(json.dumps(contract()))
    return (
        board,
        source,
        dict(
            team_contract="team.json",
            team_digest=hashlib.sha256(source.read_bytes()).hexdigest(),
            expected_board_sha256=hashlib.sha256(board.read_bytes()).hexdigest(),
        ),
    )


def test_existing_owner_enrolls_exact_empty_board(tmp_path):
    board, source, kw = setup(tmp_path)
    assert c.command_migrate(args(board, **kw)) == 0
    assert f"Team-Contract: team.json @ {kw['team_digest']}" in board.read_text()
    assert c.rows(board.read_text()) == []
    # Retry is read-only on exact already bound current bytes.
    kw["expected_board_sha256"] = hashlib.sha256(board.read_bytes()).hexdigest()
    assert c.command_migrate(args(board, **kw)) == 0


@pytest.mark.parametrize(
    "change",
    [
        lambda b, s, k: k.update(expected_board_sha256="f" * 64),
        lambda b, s, k: k.update(team_digest="f" * 64),
        lambda b, s, k: k.update(team_contract="../team.json"),
        lambda b, s, k: s.write_text(s.read_text() + " "),
    ],
)
def test_enrollment_refuses_drift_and_path_before_mutation(tmp_path, change):
    board, source, kw = setup(tmp_path)
    before = board.read_bytes()
    change(board, source, kw)
    assert c.command_migrate(args(board, **kw)) != 0
    assert board.read_bytes() == before


def test_active_board_cannot_be_reclassified(tmp_path):
    board, source, kw = setup(tmp_path)
    identity = c.new_identity([])
    row = c.Session(
        session_uuid=identity.session_uuid,
        compact_id=identity.compact_id,
        speakable_id=identity.speakable_id,
        legacy_id="",
        agent="agent",
        machine="machine-one",
        project="synthetic",
        started="t",
        heartbeat="t",
        mode="interactive",
        workspaces=[],
        goal="synthetic",
        claims=["repo/**"],
        context_role="owner",
        status="active",
        client_ref="codex:synthetic",
    )
    board.write_text(c.replace_table(board.read_text(), [row]))
    before = board.read_bytes()
    kw["expected_board_sha256"] = hashlib.sha256(before).hexdigest()
    assert c.command_migrate(args(board, **kw)) != 0 and board.read_bytes() == before


def test_missing_all_or_partial_binding_arguments_refuses(tmp_path):
    board, _, kw = setup(tmp_path)
    before = board.read_bytes()
    kw.pop("team_digest")
    assert c.command_migrate(args(board, **kw)) != 0 and board.read_bytes() == before


def test_ordinary_mutation_cannot_grant_team_enrollment(tmp_path):
    board, _, kw = setup(tmp_path)
    before = board.read_bytes()
    with pytest.raises(ValueError):
        c.locked_update(
            board,
            lambda text: text + f"\nTeam-Contract: team.json @ {kw['team_digest']}\n",
        )
    assert board.read_bytes() == before


def test_contract_keyboard_username_is_transport_not_password():
    d = contract()
    d["repositories"][0]["remote"] = "ssh://git@git.example/org/repo.git"
    assert tc.validate(d) == d
    d["repositories"][0]["remote"] = "ssh://git:secret@git.example/org/repo.git"
    with pytest.raises(ValueError):
        tc.validate(d)

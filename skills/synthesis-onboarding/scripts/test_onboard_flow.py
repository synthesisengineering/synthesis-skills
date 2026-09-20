"""The one smart entry: detect, recommend, ask, and chain engines."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import fleet_join as FJ
import onboard_flow as OB


def board_args(**overrides):
    values = {"json": False, "verbose": False}
    values.update(overrides)
    return SimpleNamespace(**values)


def boarder(tmp_path, **overrides):
    announced: list[str] = []
    params = {
        "release_root": tmp_path / "release",
        "home": tmp_path / "home",
        "announce": announced.append,
        "can_prompt": True,
    }
    params.update(overrides)
    board = OB.Onboarder(**params)
    return board, announced


def test_cli_registers_onboard():
    import synthesis_cli

    assert "onboard" in synthesis_cli.CLI_COMMANDS
    parser = synthesis_cli.build_parser()
    args = parser.parse_args(["onboard"])
    assert args.command == "onboard"
    assert "onboard" in parser.format_help()


def test_survey_combines_setup_and_fleet(tmp_path):
    board, _ = boarder(
        tmp_path,
        read_setup_state=lambda home: {"profile": "full"},
        read_fleet_state=lambda home: {
            "machine_id": "m", "label": "mac", "role": "primary"
        },
    )
    assert board.survey() == {
        "setup": {"profile": "full"},
        "fleet": {"machine_id": "m", "label": "mac", "role": "primary"},
    }


def test_menu_recommends_fleet_when_unenrolled(tmp_path):
    board, _ = boarder(tmp_path)
    options, default = board.menu({"machine_id": None})
    assert options[0] == OB.Onboarder.MENU_FLEET
    assert default == 1
    options, default = board.menu({"machine_id": "m"})
    assert default == 5
    assert options[-1] == OB.Onboarder.MENU_DONE


def test_fresh_install_runs_setup_then_fleet(tmp_path, monkeypatch):
    calls: list = []
    board, announced = boarder(
        tmp_path,
        read_setup_state=lambda home: None,
        run_setup=lambda: calls.append("setup") or 0,
        run_fleet_join=lambda: calls.append("fleet") or 0,
    )
    monkeypatch.setattr(
        FJ, "prompt_confirm", lambda *a, **k: True
    )
    assert board.run() == 0
    assert calls == ["setup", "fleet"]
    assert any("installing now" in line for line in announced)


def test_fresh_install_declining_fleet_finishes(tmp_path, monkeypatch):
    calls: list = []
    board, announced = boarder(
        tmp_path,
        read_setup_state=lambda home: None,
        run_setup=lambda: calls.append("setup") or 0,
        run_fleet_join=lambda: calls.append("fleet") or 0,
    )
    monkeypatch.setattr(
        FJ, "prompt_confirm", lambda *a, **k: False
    )
    assert board.run() == 0
    assert calls == ["setup"]
    assert any("rerun the same command" in line for line in announced)


def test_fresh_setup_failure_fails_closed(tmp_path):
    board, _ = boarder(
        tmp_path,
        read_setup_state=lambda home: None,
        run_setup=lambda: 1,
    )
    with pytest.raises(FJ.FleetJoinError, match=r"setup failed \(exit 1\)"):
        board.run()


def test_menu_dispatches_each_action(tmp_path, monkeypatch):
    calls: list = []
    answers = iter(["2", "3", "1", "6"])
    texts = iter(["demo", "https://h/u/kb.git"])
    board, announced = boarder(
        tmp_path,
        read_setup_state=lambda home: {"profile": "full"},
        read_fleet_state=lambda home: {"machine_id": None},
        run_update=lambda: calls.append("update") or 0,
        run_workspace_ensure=lambda n, r: calls.append(("ws", n, r)) or 0,
        run_fleet_join=lambda: calls.append("fleet") or 0,
    )
    options_seen: list = []

    def choice(question, opts, hint, **kwargs):
        options_seen.append(list(opts))
        return opts[int(next(answers)) - 1]

    monkeypatch.setattr(FJ, "prompt_choice", choice)
    monkeypatch.setattr(
        FJ, "prompt_text", lambda *a, **k: next(texts)
    )
    assert board.run() == 0
    assert calls == [
        "update",
        ("ws", "demo", "https://h/u/kb.git"),
        "fleet",
    ]
    assert all(len(opts) == 6 for opts in options_seen)


def test_menu_verify_repairs_on_failure(tmp_path, monkeypatch):
    calls: list = []
    board, announced = boarder(
        tmp_path,
        read_setup_state=lambda home: {"profile": "full"},
        read_fleet_state=lambda home: {"machine_id": "m"},
        run_doctor=lambda: calls.append("doctor") or 1,
        run_repair=lambda: calls.append("repair") or 0,
    )
    rounds = iter(["5", "6"])
    monkeypatch.setattr(
        FJ, "prompt_choice",
        lambda q, opts, h, **k: opts[int(next(rounds)) - 1],
    )
    monkeypatch.setattr(
        FJ, "prompt_confirm", lambda *a, **k: True
    )
    assert board.run() == 0
    assert calls == ["doctor", "repair"]


def test_menu_verify_green_reports_and_loops(tmp_path, monkeypatch):
    board, announced = boarder(
        tmp_path,
        read_setup_state=lambda home: {"profile": "full"},
        read_fleet_state=lambda home: {"machine_id": "m"},
        run_doctor=lambda: 0,
    )
    rounds = iter(["5", "6"])
    monkeypatch.setattr(
        FJ, "prompt_choice",
        lambda q, opts, h, **k: opts[int(next(rounds)) - 1],
    )
    assert board.run() == 0
    assert any("green" in line for line in announced)


def test_menu_components_dispatch(tmp_path, monkeypatch):
    calls: list = []
    board, _ = boarder(
        tmp_path,
        read_setup_state=lambda home: {"profile": "full"},
        read_fleet_state=lambda home: {"machine_id": "m"},
        run_activate=lambda profile: calls.append(profile) or 0,
    )
    rounds = iter(["4", "skills-only — just the skills", "6"])
    monkeypatch.setattr(
        FJ, "prompt_choice", lambda q, opts, h, **k: _pick(opts, rounds)
    )
    assert board.run() == 0
    assert calls == ["skills-only"]


def _pick(opts, rounds):
    wanted = next(rounds)
    if wanted in opts:
        return wanted
    return opts[int(wanted) - 1]


def test_run_headless_refuses_with_explicit_alternatives(tmp_path):
    board, _ = boarder(tmp_path, can_prompt=False)
    with pytest.raises(OB.OnboardError, match="needs a terminal"):
        board.run()


def test_onboard_entry_json_is_headless_and_interrupts_cleanly(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(FJ, "terminal_available", lambda: True)
    with pytest.raises(OB.OnboardError, match="needs a terminal"):
        OB.onboard(
            board_args(json=True), release_root=tmp_path / "release",
            home=tmp_path / "home",
        )

    def raising_read(home_dir):
        raise KeyboardInterrupt

    code = OB.onboard(
        board_args(), release_root=tmp_path / "release",
        home=tmp_path / "home", read_setup_state=raising_read,
    )
    assert code == 130
    assert "INTERRUPTED onboard" in capsys.readouterr().err


def test_read_fleet_empty_and_enrolled(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    release = tmp_path / "release"
    (release / "skills" / "synthesis-project-management" / "scripts").mkdir(
        parents=True
    )
    assert OB.read_fleet(home, release)["machine_id"] is None

    real_root = SCRIPTS_DIR.parent.parent.parent
    assert (real_root / "skills").is_dir()
    OB.read_fleet(home, real_root)
    import fleet_identity

    board = home / ".synthesis" / "coordination" / "active-sessions.md"
    directory = fleet_identity.fleet_dir_for_board(board)
    machine_id = fleet_identity.mint_machine_id(directory)
    fleet_identity.enroll_self(
        label="mac", role="primary", directory=directory
    )
    found = OB.read_fleet(home, real_root)
    assert found == {
        "machine_id": machine_id, "label": "mac", "role": "primary"
    }

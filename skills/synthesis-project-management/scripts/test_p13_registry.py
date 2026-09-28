from pathlib import Path
import hashlib
import json
import sys
import pytest

PM = Path(__file__).resolve().parent
sys.path.insert(0, str(PM))
import team_contract as tc  # noqa: E402 - exact sibling source is selected before importing the owner
import project_state as ps  # noqa: E402 - exact sibling source is selected before importing the owner
import coordination as c  # noqa: E402 - exact sibling source is selected before importing the owner
from test_team_contract import contract  # noqa: E402 - exact sibling source is selected before importing the owner
from test_run_admission import git  # noqa: E402 - exact sibling source is selected before importing the owner


import test_run_admission as world_fixtures  # noqa: E402 - explicit sibling fixture owner

world = world_fixtures.world


def enroll(w, person="p-one"):
    d = contract()
    d["repositories"][0]["remote"] = "https://git.example/one/notes.git"
    d["repositories"][0]["audience"] = "private"
    d["repositories"][0]["readers"] = ["p-two"]
    source = w["repo"] / "projects/team.json"
    source.write_text(json.dumps(d))
    sha = hashlib.sha256(source.read_bytes()).hexdigest()
    index = w["repo"] / "projects/index.yaml"
    index.write_text(
        "# Synthesis-Team: team.json @ " + sha + " / repo-one\n" + index.read_text()
    )
    git(w["repo"], "add", "projects")
    git(w["repo"], "commit", "-m", "Synthetic binding")
    git(w["repo"], "remote", "add", "origin", d["repositories"][0]["remote"])
    board = w["board"]
    rows = c.rows(board.read_text())
    rows[0].person = person
    rows[0].machine = "fixture-machine"
    rows[0].agent = "claude"
    bs = board.parent / "team.json"
    bs.write_bytes(source.read_bytes())
    board.write_text(
        c.replace_table(c.template(), rows)
        + "\nTeam-Contract: team.json @ "
        + sha
        + "\n"
    )
    return d, sha


def test_actual_resolver_denies_confidential_reader_before_prose(world):
    enroll(world)
    report = ps.resolve_project(
        "alpha",
        world["repo"] / "projects/index.yaml",
        coordination_board=world["board"],
        fetch=False,
    )
    assert report.status == "UNKNOWN" and report.selected_path is None
    assert any("team" in x.lower() for x in report.issues)


def test_actual_resolver_accepts_declared_reader(world):
    enroll(world, "p-two")
    r = ps.resolve_project(
        "alpha",
        world["repo"] / "projects/index.yaml",
        coordination_board=world["board"],
        fetch=False,
    )
    assert not any("team access" in x.lower() for x in r.issues), r.issues


def test_retired_or_spoofed_selection_refuses(world):
    enroll(world)
    assert not tc.managed_registry(
        world["repo"] / "projects/index.yaml", board=world["board"]
    )["allowed"]


def test_shared_reference_cannot_export_private_identity(world):
    d, sha = enroll(world)
    d["repositories"].append(
        dict(
            d["repositories"][0],
            id="shared",
            audience="shared",
            readers=["p-one", "p-two"],
        )
    )
    with pytest.raises(ValueError):
        tc.require_reference(d, "shared", "repo-one")

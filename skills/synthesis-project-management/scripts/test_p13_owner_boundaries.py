from pathlib import Path
import hashlib
import json
import sys
import pytest

S = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(S / "synthesis-project-management/scripts"))
sys.path.insert(0, str(Path(__file__).parent))
import team_contract as tc  # noqa: E402 - exact sibling source is selected before importing the owner
import coordination as c  # noqa: E402 - exact sibling source is selected before importing the owner
import run_admission as ra  # noqa: E402 - exact sibling source is selected before importing the owner
from test_p13_registry import enroll  # noqa: E402 - exact sibling source is selected before importing the owner
from test_p13_record_owners import setup  # noqa: E402 - exact sibling source is selected before importing the owner


import test_run_admission as world_fixtures  # noqa: E402 - explicit sibling fixture owner

world = world_fixtures.world


def test_native_authority_binds_person_and_declaration(world):
    d, f, sha, g = setup(world)
    first = ra.native_binding(
        world["board"], world["actor"]["native_payload"], readonly=True
    )
    d["revision"] += 1
    raw = json.dumps(d)
    new = hashlib.sha256(raw.encode()).hexdigest()
    (world["board"].parent / "team.json").write_text(raw)
    world["board"].write_text(world["board"].read_text().replace(sha, new))
    second = ra.native_binding(
        world["board"], world["actor"]["native_payload"], readonly=True
    )
    assert first["claim_hash"] != second["claim_hash"]


def test_actual_write_admission_denies_confidential_nonreader(world):
    enroll(world, "p-one")
    with pytest.raises(ValueError):
        ra.admit_paths(
            world["board"],
            "alpha",
            world["project"],
            [world["project"] / "CONTEXT.md"],
            world["actor"]["native_payload"],
            readonly=True,
        )


def test_actual_board_reference_refuses_private_project_identity(
    world, monkeypatch, capsys
):
    enroll(world, "p-two")
    monkeypatch.setenv("SYNTHESIS_COORDINATION_BOARD", str(world["board"]))
    index = world["repo"] / "projects/index.yaml"
    before = world["board"].read_bytes()
    args = c.parser().parse_args(
        [
            "--board",
            str(world["board"]),
            "message",
            "--from",
            c.rows(before.decode())[0].session_uuid,
            "--to",
            "alpha",
            "--project-index",
            str(index),
            "--text",
            "Synthetic reference",
        ]
    )
    assert c.command_message(args) != 0
    assert world["board"].read_bytes() == before
    assert "reference" in capsys.readouterr().err.lower()


def test_scoped_current_roles_not_departed_or_other_scope():
    from test_team_contract import contract

    d = contract()
    d["governance"]["role_history"] = [
        {
            "id": "a-one",
            "person": "p-one",
            "role": "maintainer",
            "scope": ["repo-one"],
            "backup": "p-two",
            "opened": "2026-09-26T00:00:00Z",
            "closed": None,
            "accepted_work": ["work-one"],
            "inventory_sha256": "a" * 64,
            "appointed_by": "p-two",
            "approval_digest": "b" * 64,
            "native_ref": "cc:synthetic",
        }
    ]
    assert "maintainer" in tc.effective_roles(d, "p-one", scope="repo-one")
    assert "maintainer" not in tc.effective_roles(d, "p-one", scope="unrelated")
    d["governance"]["role_history"][0]["closed"] = "2026-09-26T01:00:00Z"
    assert "maintainer" not in tc.effective_roles(d, "p-one", scope="repo-one")


def test_actual_board_reference_shared_audience_positive(world, monkeypatch):
    d, sha = enroll(world, "p-two")
    d["repositories"][0]["audience"] = "shared"
    d["repositories"][0]["readers"] = ["p-one", "p-two"]
    raw = json.dumps(d)
    new = hashlib.sha256(raw.encode()).hexdigest()
    (world["repo"] / "projects/team.json").write_text(raw)
    (world["board"].parent / "team.json").write_text(raw)
    world["board"].write_text(world["board"].read_text().replace(sha, new))
    index = world["repo"] / "projects/index.yaml"
    index.write_text(index.read_text().replace(sha, new))
    monkeypatch.setenv("SYNTHESIS_COORDINATION_BOARD", str(world["board"]))
    args = c.parser().parse_args(
        [
            "--board",
            str(world["board"]),
            "message",
            "--from",
            c.rows(world["board"].read_text())[0].session_uuid,
            "--to",
            "alpha",
            "--project-index",
            str(index),
            "--text",
            "Synthetic shared reference",
        ]
    )
    assert c.command_message(args) == 0
    assert "Synthetic shared reference" in world["board"].read_text()

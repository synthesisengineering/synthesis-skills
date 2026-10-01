from pathlib import Path
import sys
import pytest

S = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(S / "synthesis-autopilot/scripts"))
sys.path.insert(0, str(Path(__file__).parent))
from test_run_state import create, command, contract  # noqa: E402 - exact sibling source is selected before importing the owner
from test_p13_record_owners import setup  # noqa: E402 - exact sibling source is selected before importing the owner
import team_contract as tc  # noqa: E402 - exact sibling source is selected before importing the owner
import coordination as c  # noqa: E402 - exact sibling source is selected before importing the owner


import test_run_admission as world_fixtures  # noqa: E402 - explicit sibling fixture owner

world = world_fixtures.world
import test_run_state as engine_fixtures  # noqa: E402 - explicit sibling fixture owner

engine = engine_fixtures.engine


def test_actual_run_journal_unsettled_effect_blocks_offboarding(world, engine):
    contract_value = contract()
    contract_value["authority_refs"] = ["synthetic-attestation"]
    state = create(engine, world, contract=contract_value)
    state = command(
        engine,
        world,
        state,
        "effect.prepare",
        {
            "id": "pending",
            "target": "synthetic",
            "payload_digest": "a" * 64,
            "idempotency_key": "synthetic-one",
            "authority_ref": "synthetic-attestation",
        },
    )
    d, f, sha, g = setup(world)
    rows = c.rows(world["board"].read_text())
    rows[1].client_ref = state["owner"]["native_ref"]
    world["board"].write_text(c.replace_table(world["board"].read_text(), rows))
    obs = tc.observed_offboarding(d, "p-one", board=world["board"], repo_guard_root=g)
    assert not obs["managed_ready"]
    assert any("journal" in b["reason"] for b in obs["blockers"])
    assert (
        engine.load_run(world["project"], state["run_id"])["effects"]["pending"][
            "status"
        ]
        == "prepared"
    )


def test_corrupt_journal_never_becomes_no_effects(world, engine):
    state = create(engine, world)
    d, f, sha, g = setup(world)
    event = (
        world["project"]
        / "resources/autopilot-runs"
        / state["run_id"]
        / "events/000000000001.json"
    )
    event.write_text("{")
    with pytest.raises((ValueError, RuntimeError)):
        tc.observed_offboarding(d, "p-one", board=world["board"], repo_guard_root=g)

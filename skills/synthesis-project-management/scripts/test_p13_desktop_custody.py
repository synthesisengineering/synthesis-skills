"""Actual desktop host/native sidecar mapping must cover pending effects."""

import hashlib
import json
import pytest
import team_contract as tc
import coordination as c
import peer_addressing as peers
from test_p13_record_owners import setup
import test_run_admission as fixtures

world = fixtures.world


def desktop(w, *, sidecar=True, wrong=False):
    d, _, _, guard = setup(w)
    text = w["board"].read_text()
    rows = c.rows(text)
    row = next(v for v in rows if v.person == "p-one")
    row.client_ref = "ccd:synthetic-desktop-host"
    w["board"].write_text(c.replace_table(text, rows))
    native = "93c674d9-f078-4102-b066-b4660166894a"
    if sidecar:
        peers.write_seat(
            w["board"],
            session_uuid=row.session_uuid,
            compact_id=row.compact_id,
            machine=row.machine,
            identity=peers.SelfIdentity(
                client=peers.CLIENT_CLAUDE,
                harness_session_id=native,
                host_session_id="wrong-host" if wrong else "synthetic-desktop-host",
            ),
            status="released",
        )
    return d, guard, native


def test_desktop_pending_native_effect_blocks_departure(world):
    d, guard, native = desktop(world)
    (
        guard / "pending" / (hashlib.sha256(native.encode()).hexdigest() + ".json")
    ).write_text(json.dumps({"session_id": native, "files": ["synthetic"]}))
    assert (
        tc.observed_offboarding(
            d, "p-one", board=world["board"], repo_guard_root=guard
        )["managed_ready"]
        is False
    )


@pytest.mark.parametrize("kind", ["missing", "wrong"])
def test_desktop_ambiguous_native_custody_refuses(world, kind):
    d, guard, native = desktop(world, sidecar=kind != "missing", wrong=kind == "wrong")
    with pytest.raises((ValueError, RuntimeError)):
        tc.observed_offboarding(d, "p-one", board=world["board"], repo_guard_root=guard)


def test_desktop_completed_native_custody_positive(world):
    d, guard, native = desktop(world)
    assert (
        tc.observed_offboarding(
            d, "p-one", board=world["board"], repo_guard_root=guard
        )["managed_ready"]
        is True
    )

"""Desktop sidecar source must remain safe and current through observation."""

import json
import os
import pytest
import test_p13_desktop_custody as fixture
import team_contract as tc
import peer_addressing as peers

world = fixture.world


@pytest.mark.parametrize("kind", ["mode", "alias", "hardlink", "late"])
def test_desktop_source_boundary_refuses(world, monkeypatch, kind):
    d, guard, _ = fixture.desktop(world)
    directory = world["board"].parent / "seats"
    path = next(
        p
        for p in directory.glob("*.json")
        if peers.read_seat(world["board"], p.stem, strict=True).host_session_id
        == "synthetic-desktop-host"
    )
    if kind == "mode":
        path.chmod(0o666)
    elif kind == "alias":
        held = path.with_suffix(".retained")
        path.rename(held)
        path.symlink_to(held)
    elif kind == "hardlink":
        os.link(path, path.with_suffix(".second"))
    else:
        original = tc.observed_run_effects

        def mutate(*args, **kwargs):
            result = original(*args, **kwargs)
            value = json.loads(path.read_text())
            value["harness_session_id"] = "f2c76119-d76d-4588-9046-32a9d3f343f5"
            path.write_text(json.dumps(value))
            return result

        monkeypatch.setattr(tc, "observed_run_effects", mutate)
    with pytest.raises((ValueError, RuntimeError)):
        tc.observed_offboarding(d, "p-one", board=world["board"], repo_guard_root=guard)

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_p13_registry import enroll
import team_contract as tc
import pytest


import test_run_admission as world_fixtures  # noqa: E402 - explicit sibling fixture owner

world = world_fixtures.world


def test_tracked_enrollment_cannot_be_removed_to_bypass_reader(world):
    enroll(world)
    index = world["repo"] / "projects/index.yaml"
    index.write_text("\n".join(index.read_text().splitlines()[1:]) + "\n")
    with pytest.raises(ValueError, match="enrollment"):
        tc.require_registry(index, board=world["board"])

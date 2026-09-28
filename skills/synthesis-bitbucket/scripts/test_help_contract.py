"""Keep installed CLI guidance bound to retained vendor help, without account calls."""
import hashlib
import json
from pathlib import Path
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
from repository_binding import validate_argv  # noqa: E402 - exact sibling grammar


def help_evidence():
    path = SCRIPTS / "fixtures/help-0.30.0.json"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == "bebf5d8ee431570a4a8c8dbcad5bdea8ea206e25103e73074024be1175727dca"
    return json.loads(path.read_text())["commands"]


@pytest.mark.parametrize("flags", [["--yaml"], ["--template", "{{.title}}"]])
def test_documented_output_flags_have_vendor_and_binding_support(flags):
    evidence = help_evidence()
    assert flags[0] in evidence["global"]["stdout"]
    assert flags[0] in (SCRIPTS.parent / "SKILL.md").read_text()
    assert validate_argv(["bkt", "pr", "list", "--repo", "fixture", *flags])["repo"] == "fixture"


def test_pipeline_run_is_documented_as_consequential_with_bound_repository():
    assert "--ref" in help_evidence()["pipeline"]["stdout"]
    doc = (SCRIPTS.parent / "SKILL.md").read_text()
    writes = doc.split("### Write", 1)[1].split("### Escape hatch", 1)[0]
    assert "bkt pipeline run --repo <repo> --ref <branch|tag|commit>" in writes
    assert "can deploy" in writes and "deployment authorization" in writes
    assert validate_argv(["bkt", "pipeline", "run", "--repo", "fixture", "--ref", "main"])["repo"] == "fixture"


def test_merge_guidance_does_not_turn_vendor_example_into_universal_enum():
    vendor = help_evidence()["merge"]["stdout"]
    assert "--strategy string" in vendor and "rebase_fast_forward" in vendor
    doc = (SCRIPTS.parent / "SKILL.md").read_text()
    assert "--strategy <server-supported-id>" in doc
    assert "example, not a universal supported-value list" in doc
    assert "merge_commit|squash|fast_forward" not in doc
    assert validate_argv(["bkt", "pr", "merge", "1", "--repo", "fixture", "--strategy", "rebase_fast_forward"])["repo"] == "fixture"

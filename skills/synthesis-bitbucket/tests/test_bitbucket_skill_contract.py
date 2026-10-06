"""Keep the skill's command guidance bound to the retained vendor help (bkt 0.30.0) and to the
repository rule (E80), without calling bkt or any account."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

SKILL = Path(__file__).resolve().parents[1]
DOC = (SKILL / "SKILL.md").read_text(encoding="utf-8")
REPOSITORY_ACTING = re.compile(r"^bkt (pr|repo|branch|pipeline) \S+")


def help_evidence() -> dict:
    path = SKILL / "tests" / "fixtures" / "help-0.30.0.json"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == "bebf5d8ee431570a4a8c8dbcad5bdea8ea206e25103e73074024be1175727dca"
    return json.loads(path.read_text(encoding="utf-8"))["commands"]


def documented_commands() -> list:
    """Commands as the catalog and the gh map state them (prose may mention a command by name)."""
    catalog = DOC.split("## Command catalog", 1)[1].split("## When NOT to apply", 1)[0]
    return [c for c in re.findall(r"`(bkt [^`]+)`", catalog) if REPOSITORY_ACTING.match(c)]


def test_e80_every_documented_repository_command_names_exactly_one_repo():
    commands = documented_commands()
    assert len(commands) >= 15, commands  # the catalog and the gh map, not an empty match
    for command in commands:
        assert command.split().count("--repo") == 1, command
    assert "exactly one literal `--repo <slug>`" in DOC and "never selects the repository" in DOC


def test_e80_api_paths_are_canonical_and_literal():
    for path in re.findall(r"`bkt api (/[^`\s]+)", DOC):
        assert not re.search(r"(^|/)\.\.(/|$)", path) and "%2e" not in path.lower(), path
        assert path.startswith(("/repositories/", "/rest/api/1.0/projects/", "/user")), path


def test_documented_output_flags_exist_in_the_vendor_help():
    evidence = help_evidence()
    for flag in ("--yaml", "--template", "--json", "--jq"):
        assert flag in evidence["global"]["stdout"] and flag in DOC, flag


def test_pipeline_run_is_documented_as_consequential_with_a_named_repository():
    assert "--ref" in help_evidence()["pipeline"]["stdout"]
    writes = DOC.split("### Write", 1)[1].split("### Escape hatch", 1)[0]
    assert "bkt pipeline run --repo <repo> --ref <branch|tag|commit>" in writes
    assert "can deploy" in writes and "deployment authorization" in writes


def test_merge_guidance_does_not_turn_the_vendor_example_into_a_universal_enum():
    vendor = help_evidence()["merge"]["stdout"]
    assert "--strategy string" in vendor and "rebase_fast_forward" in vendor
    assert "--strategy <server-supported-id>" in DOC
    assert "example, not a universal supported-value list" in DOC
    assert "merge_commit|squash|fast_forward" not in DOC

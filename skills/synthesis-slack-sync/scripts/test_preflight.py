"""Regressions for the Slack sync preflight.

Derived from a real failure: a config carries two valid-looking ids per DM
entry (the user id and the conversation id) while the sibling classes use
the field that is wrong for DMs, so a uniform read of ``id`` hands user ids
to a conversation-read call. On 2026-09-01 a careful reader with the config
open, warned about the trap minutes earlier, still derived every DM target
that way. Resolution belongs in one place that fails closed and prints a
census, so a wrong derivation shows as a wrong shape rather than quiet
empties.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).with_name("preflight.py")
SPEC = importlib.util.spec_from_file_location("preflight", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

SKILLS_ROOT = Path(__file__).resolve().parents[2]
WATERMARK = SKILLS_ROOT / "synthesis-daily-rituals" / "scripts" / "sync_watermark.py"

CONFIG = """
workspace: example-workspace
channels:
  - id: C0EXAMPLE01
    name: team-general
    type: public_channel
  - id: C0EXAMPLE02
    name: eng-pull-requests
    type: private_channel
dm_channels:
  - id: U0EXAMPLE01
    name: Jane Doe
    dm_id: D0EXAMPLE01
  - id: U0EXAMPLE02
    name: Sam Lee
    dm_id: D0EXAMPLE02
group_dm_channels:
  - id: C0EXAMPLE03
    name: "Project Alpha team"
"""


def write_config(tmp_path: Path, text: str = CONFIG) -> Path:
    path = tmp_path / "slack-sync.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def run_cli(*argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *argv], capture_output=True, text=True)


# --- the one read id per class ------------------------------------------------------------


def test_dms_resolve_to_the_conversation_id_never_the_user_id(tmp_path: Path) -> None:
    targets = MODULE.resolve_targets(MODULE._load_config(write_config(tmp_path)))

    dms = [t for t in targets if t.kind == "dm"]
    assert [t.read_id for t in dms] == ["D0EXAMPLE01", "D0EXAMPLE02"]
    assert not any(t.read_id.startswith("U") for t in targets if t.resolved)


def test_declared_set_is_the_shape_the_watermark_gate_takes(tmp_path: Path) -> None:
    targets = MODULE.resolve_targets(MODULE._load_config(write_config(tmp_path)))

    declared = MODULE.declared_set(targets)

    assert declared == {"slack": ["C0EXAMPLE01", "C0EXAMPLE02", "D0EXAMPLE01", "D0EXAMPLE02", "C0EXAMPLE03"]}
    spec = importlib.util.spec_from_file_location("sync_watermark", WATERMARK)
    watermark = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(watermark)
    out = tmp_path / "declared.json"
    out.write_text(json.dumps(declared), encoding="utf-8")
    assert watermark._parse_targets([], str(out)) == declared


def test_census_shows_the_shape(tmp_path: Path) -> None:
    targets = MODULE.resolve_targets(MODULE._load_config(write_config(tmp_path)))

    assert MODULE.census(targets) == "census: 3 C / 2 D / 0 unresolved"


# --- unresolved is reported, never guessed and never silently skipped --------------------------


def test_a_dm_without_dm_id_is_unresolved_with_the_reason(tmp_path: Path) -> None:
    config = CONFIG.replace("    dm_id: D0EXAMPLE02\n", "")
    targets = MODULE.resolve_targets(MODULE._load_config(write_config(tmp_path, config)))

    sam = next(t for t in targets if t.name == "Sam Lee")
    assert sam.resolved is False
    assert "no dm_id" in sam.reason
    assert MODULE.census(targets) == "census: 3 C / 1 D / 1 unresolved"


def test_a_user_id_offered_as_a_conversation_id_is_refused(tmp_path: Path) -> None:
    """The exact wrong derivation: the user id in the field the reader takes."""
    config = CONFIG.replace("dm_id: D0EXAMPLE01", "dm_id: U0EXAMPLE01")
    targets = MODULE.resolve_targets(MODULE._load_config(write_config(tmp_path, config)))

    jane = next(t for t in targets if t.name == "Jane Doe")
    assert jane.resolved is False
    assert "user id" in jane.reason
    assert "U0EXAMPLE01" not in MODULE.declared_set(targets)["slack"]


def test_a_channel_with_a_dm_prefix_is_unresolved(tmp_path: Path) -> None:
    config = CONFIG.replace("id: C0EXAMPLE02", "id: D0EXAMPLE99")
    targets = MODULE.resolve_targets(MODULE._load_config(write_config(tmp_path, config)))

    channel = next(t for t in targets if t.name == "eng-pull-requests")
    assert channel.resolved is False
    assert "expected C or G" in channel.reason


def test_inactive_entries_are_scoped_out(tmp_path: Path) -> None:
    config = CONFIG.replace("    dm_id: D0EXAMPLE02\n", "    dm_id: D0EXAMPLE02\n    active: false\n")
    targets = MODULE.resolve_targets(MODULE._load_config(write_config(tmp_path, config)))

    assert [t.name for t in targets if t.kind == "dm"] == ["Jane Doe"]


# --- the CLI fails closed ------------------------------------------------------------------------


def test_cli_prints_table_and_census_and_writes_the_declared_set(tmp_path: Path) -> None:
    out = tmp_path / "declared.json"

    done = run_cli("--config", str(write_config(tmp_path)), "--out", str(out))

    assert done.returncode == 0, done.stderr
    assert "| dm | D0EXAMPLE01 | Jane Doe | resolved |" in done.stdout
    assert "census: 3 C / 2 D / 0 unresolved" in done.stdout
    assert json.loads(out.read_text(encoding="utf-8")) == {
        "slack": ["C0EXAMPLE01", "C0EXAMPLE02", "D0EXAMPLE01", "D0EXAMPLE02", "C0EXAMPLE03"]
    }


def test_cli_exits_one_when_a_declared_target_is_unresolved(tmp_path: Path) -> None:
    config = CONFIG.replace("    dm_id: D0EXAMPLE02\n", "")

    done = run_cli("--config", str(write_config(tmp_path, config)), "--json")

    assert done.returncode == 1
    assert json.loads(done.stdout) == {"slack": ["C0EXAMPLE01", "C0EXAMPLE02", "D0EXAMPLE01", "C0EXAMPLE03"]}
    assert "unresolved" in done.stderr


def test_cli_refuses_an_empty_resolved_set(tmp_path: Path) -> None:
    done = run_cli("--config", str(write_config(tmp_path, "workspace: w\nchannels: []\n")))

    assert done.returncode == 2
    assert "refused" in done.stderr


def test_cli_refuses_a_malformed_config(tmp_path: Path) -> None:
    done = run_cli("--config", str(write_config(tmp_path, "channels:\n  - just-a-string\n")))

    assert done.returncode == 2
    assert "must be a mapping" in done.stderr

    missing = run_cli("--config", str(tmp_path / "absent.yaml"))
    assert missing.returncode == 2


# --- the documented rules the mechanism depends on ----------------------------------------------


def test_slack_sync_names_the_preflight_command_and_census() -> None:
    text = (SKILLS_ROOT / "synthesis-slack-sync" / "SKILL.md").read_text(encoding="utf-8")
    assert "scripts/preflight.py --config" in text
    assert "census" in text
    assert "produced by hand" not in text


def test_rituals_take_the_declared_set_from_preflight() -> None:
    text = (SKILLS_ROOT / "synthesis-daily-rituals" / "SKILL.md").read_text(encoding="utf-8")
    assert "preflight.py" in text
    assert "never a stored copy" in text


def test_preflight_is_in_the_shared_ci_group() -> None:
    repo_root = SKILLS_ROOT.parent
    workflow = (repo_root / ".github" / "workflows" / "validate.yml").read_text(encoding="utf-8")
    agents = (repo_root / "AGENTS.md").read_text(encoding="utf-8")
    assert "skills/synthesis-slack-sync/scripts/test_*.py" in workflow
    assert "skills/synthesis-slack-sync/scripts/test_*.py" in agents

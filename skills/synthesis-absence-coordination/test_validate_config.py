"""Tests for validate_config.py.

Run via subprocess so the tests exercise the real CLI contract — exit codes
included. The guard contract (0 valid / 1 defects / 2 unverifiable) is the
skill's promise to ritual hooks and other callers; testing internals while the
exit codes drift would miss the only failures that matter.
"""

from __future__ import annotations

import copy
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

SKILL_DIR = Path(__file__).parent
VALIDATOR = SKILL_DIR / "validate_config.py"
EXAMPLE = SKILL_DIR / "example-config.yaml"


def run_validator(config_path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), str(config_path)],
        capture_output=True,
        text=True,
        timeout=30,
    )


@pytest.fixture()
def example_config() -> dict:
    return yaml.safe_load(EXAMPLE.read_text())


@pytest.fixture()
def write_config(tmp_path):
    def _write(cfg: dict) -> Path:
        p = tmp_path / "config.yaml"
        p.write_text(yaml.safe_dump(cfg))
        return p

    return _write


def tier(cfg: dict, tier_id: str) -> dict:
    return next(t for t in cfg["recipient_tiers"] if t["id"] == tier_id)


# ---------------------------------------------------------------- happy path


def test_example_config_is_valid():
    result = run_validator(EXAMPLE)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "VALID" in result.stdout


def test_example_config_placeholder_hygiene(example_config):
    """The shipped example must contain only example.com addresses.

    The example config is public; a real address leaking into it would be a
    disclosure, and a plausible-but-fake domain would invite copy-paste sends.
    """
    text = EXAMPLE.read_text()
    for line in text.splitlines():
        if "@" in line and "example.com" not in line and "tripit.com" not in line \
                and not line.strip().startswith("#"):
            assert "@" not in line.split("#")[0], f"non-placeholder address: {line!r}"


# ------------------------------------------------------------- guard contract


def test_missing_config_exits_2(tmp_path):
    result = run_validator(tmp_path / "nope.yaml")
    assert result.returncode == 2
    assert "UNVERIFIED" in result.stdout


def test_unparseable_config_exits_2(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text("recipient_tiers: [unclosed")
    result = run_validator(p)
    assert result.returncode == 2
    assert "UNVERIFIED" in result.stdout


def test_non_mapping_config_exits_2(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text("- just\n- a\n- list\n")
    result = run_validator(p)
    assert result.returncode == 2


# ------------------------------------------------------------ seeded defects


def test_agent_sent_principals_is_a_defect(example_config, write_config):
    """A note to your CEO about your own absence is never agent-sent."""
    cfg = copy.deepcopy(example_config)
    tier(cfg, "principals")["send_mode"] = "agent_send_after_approval"
    result = run_validator(write_config(cfg))
    assert result.returncode == 1
    assert "draft_only" in result.stdout


def test_ungated_chat_tier_is_a_defect(example_config, write_config):
    """A manager must never learn of an absence from a group channel."""
    cfg = copy.deepcopy(example_config)
    tier(cfg, "team_group").pop("gate", None)
    result = run_validator(write_config(cfg))
    assert result.returncode == 1
    assert "gated" in result.stdout


def test_travel_address_mismatch_is_a_defect(example_config, write_config):
    """The silent-discard trap: unverified sender -> no bounce, no trip."""
    cfg = copy.deepcopy(example_config)
    cfg["principal"]["travel_verified_address"] = "personal@example.com"
    cfg["integrations"]["travel_service"]["must_send_from"] = "work@example.com"
    result = run_validator(write_config(cfg))
    assert result.returncode == 1
    assert "does not match" in result.stdout


def test_unknown_content_policy_is_a_defect(example_config, write_config):
    cfg = copy.deepcopy(example_config)
    tier(cfg, "family")["content"] = "everything_including_gossip"
    result = run_validator(write_config(cfg))
    assert result.returncode == 1


def test_cc_referencing_unknown_tier_is_a_defect(example_config, write_config):
    cfg = copy.deepcopy(example_config)
    tier(cfg, "principals")["cc"] = "tier:no_such_tier"
    result = run_validator(write_config(cfg))
    assert result.returncode == 1


def test_missing_tier_content_is_a_defect(example_config, write_config):
    cfg = copy.deepcopy(example_config)
    del tier(cfg, "direct_reports")["content"]
    result = run_validator(write_config(cfg))
    assert result.returncode == 1


# ---------------------------------------------------------- seeded warnings


def test_alias_shaped_address_warns(example_config, write_config):
    """An alias cannot be audited and dies silently in provider migrations."""
    cfg = copy.deepcopy(example_config)
    tier(cfg, "family")["members"] = ["family@example.com"]
    result = run_validator(write_config(cfg))
    assert "alias" in result.stdout


def test_missing_quiet_type_warns(example_config, write_config):
    """A system that can only broadcast gets abandoned when discretion matters."""
    cfg = copy.deepcopy(example_config)
    cfg["absence_types"].pop("quiet")
    result = run_validator(write_config(cfg))
    assert "minimal" in result.stdout


def test_non_email_member_warns(example_config, write_config):
    """A TODO placeholder cannot receive mail; the config must not look complete.

    Found in practice: a real config shipped with 'TODO-...' members and
    validated clean. Placeholders are correct practice — invisible ones are not.
    """
    cfg = copy.deepcopy(example_config)
    tier(cfg, "family")["members"].append("TODO-ask-for-address")
    result = run_validator(write_config(cfg))
    assert result.returncode == 0          # a warning, not a defect
    assert "not an email address" in result.stdout


def test_warnings_alone_do_not_fail(example_config, write_config):
    """Warnings inform; only defects block. The example config has warnings
    (unresolved shared calendars) and still exits 0 — that contract must hold."""
    result = run_validator(EXAMPLE)
    assert result.returncode == 0
    assert "warn" in result.stdout

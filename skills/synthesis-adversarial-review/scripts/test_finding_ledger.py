from __future__ import annotations

import os
import pathlib
import subprocess
import sys

import yaml


SCRIPT = pathlib.Path(__file__).with_name("finding_ledger.py")


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def initialize(path: pathlib.Path) -> None:
    result = run(
        "init",
        "--file",
        str(path),
        "--engagement",
        "fixture-engagement",
        "--principal-outcome",
        "Ship the accepted controls without using the principal as courier.",
        "--round-trip-budget",
        "0",
        "--proportionality",
        "One bounded adversarial exchange; stop control growth at generation one.",
    )
    assert result.returncode == 0, result.stderr


def add_args(path: pathlib.Path, finding_id: str = "R1-F001") -> list[str]:
    return [
        "add",
        "--file",
        str(path),
        "--id",
        finding_id,
        "--title",
        "A fixture finding",
        "--state",
        "challenged",
        "--classification",
        "ship-blocking",
        "--authority-label",
        "agent-heuristic",
        "--provenance-id",
        "agent-heuristic:fixture",
        "--enforcement-outcome",
        "reported-without-enforcement",
        "--evidence",
        "fixture evidence",
    ]


def test_init_creates_declared_engagement(tmp_path: pathlib.Path) -> None:
    ledger = tmp_path / "findings.yaml"
    initialize(ledger)
    doc = yaml.safe_load(ledger.read_text(encoding="utf-8"))
    assert doc["schema"] == 1
    assert doc["engagement"]["id"] == "fixture-engagement"
    assert doc["engagement"]["principal_outcome"].startswith("Ship the accepted")
    assert doc["engagement"]["principal_courier_round_trips"] == {
        "budget": 0,
        "count": 0,
    }
    assert doc["findings"] == []


def test_add_requires_ship_classification_without_mutating(
    tmp_path: pathlib.Path,
) -> None:
    ledger = tmp_path / "findings.yaml"
    initialize(ledger)
    before = ledger.read_bytes()
    args = add_args(ledger)
    at = args.index("--classification")
    del args[at : at + 2]
    result = run(*args)
    assert result.returncode != 0
    assert ledger.read_bytes() == before


def test_authority_label_and_enforcement_outcome_remain_separate(
    tmp_path: pathlib.Path,
) -> None:
    ledger = tmp_path / "findings.yaml"
    initialize(ledger)
    result = run(*add_args(ledger))
    assert result.returncode == 0, result.stderr
    finding = yaml.safe_load(ledger.read_text(encoding="utf-8"))["findings"][0]
    assert finding["authority"] == {
        "label": "agent-heuristic",
        "provenance_id": "agent-heuristic:fixture",
    }
    assert finding["enforcement_outcome"] == "reported-without-enforcement"
    assert finding["authority"]["label"] not in finding["enforcement_outcome"]


def test_transition_requires_the_recorded_prior_state(tmp_path: pathlib.Path) -> None:
    ledger = tmp_path / "findings.yaml"
    initialize(ledger)
    assert run(*add_args(ledger)).returncode == 0
    before = ledger.read_bytes()
    stale = run(
        "transition",
        "--file",
        str(ledger),
        "--id",
        "R1-F001",
        "--from-state",
        "open",
        "--to-state",
        "repaired-source",
        "--evidence",
        "source repair",
    )
    assert stale.returncode != 0
    assert ledger.read_bytes() == before
    changed = run(
        "transition",
        "--file",
        str(ledger),
        "--id",
        "R1-F001",
        "--from-state",
        "challenged",
        "--to-state",
        "repaired-source",
        "--evidence",
        "source repair",
    )
    assert changed.returncode == 0, changed.stderr
    finding = yaml.safe_load(ledger.read_text(encoding="utf-8"))["findings"][0]
    assert finding["state"] == "repaired-source"
    assert finding["history"][-1]["from"] == "challenged"


def test_ship_improving_requires_follow_up_project(tmp_path: pathlib.Path) -> None:
    ledger = tmp_path / "findings.yaml"
    initialize(ledger)
    args = add_args(ledger)
    at = args.index("ship-blocking")
    args[at] = "ship-improving"
    refused = run(*args)
    assert refused.returncode != 0
    assert yaml.safe_load(ledger.read_text(encoding="utf-8"))["findings"] == []
    accepted = run(*args, "--follow-up-project", "fixture-follow-up")
    assert accepted.returncode == 0, accepted.stderr
    finding = yaml.safe_load(ledger.read_text(encoding="utf-8"))["findings"][0]
    assert finding["follow_up_project"] == "fixture-follow-up"


def test_duplicate_finding_id_refuses_without_mutating(tmp_path: pathlib.Path) -> None:
    ledger = tmp_path / "findings.yaml"
    initialize(ledger)
    assert run(*add_args(ledger)).returncode == 0
    before = ledger.read_bytes()
    duplicate = run(*add_args(ledger))
    assert duplicate.returncode != 0
    assert ledger.read_bytes() == before


def test_symlink_ledger_is_refused(tmp_path: pathlib.Path) -> None:
    target = tmp_path / "target.yaml"
    initialize(target)
    link = tmp_path / "link.yaml"
    os.symlink(target, link)
    before = target.read_bytes()
    result = run("validate", "--file", str(link))
    assert result.returncode != 0
    assert target.read_bytes() == before

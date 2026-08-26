from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import time

import yaml


SCRIPT = pathlib.Path(__file__).with_name("finding_ledger.py")


def run(
    *args: str, resources_root: pathlib.Path | None = None
) -> subprocess.CompletedProcess[str]:
    command, *rest = args
    if command in {"init", "record-crossing", "add", "transition", "validate"}:
        file_index = rest.index("--file") + 1
        ledger = pathlib.Path(rest[file_index])
        root = resources_root or ledger.parent
        rest = ["--resources-root", str(root), *rest]
    return subprocess.run(
        [sys.executable, str(SCRIPT), command, *rest],
        capture_output=True,
        text=True,
        check=False,
    )


def initialize(path: pathlib.Path, *, budget: int = 0) -> None:
    result = run(
        "init",
        "--file",
        str(path),
        "--engagement",
        "fixture-engagement",
        "--principal-outcome",
        "Ship the accepted controls without using the principal as courier.",
        "--round-trip-budget",
        str(budget),
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
        "history": [],
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


def test_courier_crossings_are_compare_before_write_and_budget_bounded(
    tmp_path: pathlib.Path,
) -> None:
    ledger = tmp_path / "findings.yaml"
    initialize(ledger, budget=1)
    recorded = run(
        "record-crossing",
        "--file",
        str(ledger),
        "--expected-count",
        "0",
        "--evidence",
        "Human copied one provider-boundary payload.",
    )
    assert recorded.returncode == 0, recorded.stderr
    trips = yaml.safe_load(ledger.read_text(encoding="utf-8"))["engagement"][
        "principal_courier_round_trips"
    ]
    assert trips["count"] == 1
    assert trips["history"][0]["evidence"].startswith("Human copied")

    before = ledger.read_bytes()
    stale = run(
        "record-crossing",
        "--file",
        str(ledger),
        "--expected-count",
        "0",
        "--evidence",
        "A stale writer must refuse.",
    )
    assert stale.returncode != 0
    assert ledger.read_bytes() == before

    exceeded = run(
        "record-crossing",
        "--file",
        str(ledger),
        "--expected-count",
        "1",
        "--evidence",
        "This would exceed the declared budget.",
    )
    assert exceeded.returncode != 0
    assert "blocked" in exceeded.stderr
    assert ledger.read_bytes() == before


def test_every_success_branch_names_the_unverified_remainder(
    tmp_path: pathlib.Path,
) -> None:
    ledger = tmp_path / "findings.yaml"
    initialized = run(
        "init",
        "--file",
        str(ledger),
        "--engagement",
        "coverage-fixture",
        "--principal-outcome",
        "Ship the requested artifact.",
        "--round-trip-budget",
        "1",
        "--proportionality",
        "One bounded exchange.",
    )
    crossed = run(
        "record-crossing",
        "--file",
        str(ledger),
        "--expected-count",
        "0",
        "--evidence",
        "One declared provider-boundary crossing.",
    )
    added = run(*add_args(ledger))
    transitioned = run(
        "transition",
        "--file",
        str(ledger),
        "--id",
        "R1-F001",
        "--from-state",
        "challenged",
        "--to-state",
        "repaired-verified",
        "--evidence",
        "The requested artifact passed its acceptance boundary.",
    )
    validated = run("validate", "--file", str(ledger))
    for result in (initialized, crossed, added, transitioned, validated):
        assert result.returncode == 0, result.stderr
        assert "not verified:" in result.stdout.lower()


def test_transition_history_is_contiguous_and_evidence_bound(
    tmp_path: pathlib.Path,
) -> None:
    mutations = ("first-from", "broken-chain", "evidence-mismatch")
    for mutation in mutations:
        root = tmp_path / mutation
        root.mkdir()
        ledger = root / "findings.yaml"
        initialize(ledger)
        assert run(*add_args(ledger)).returncode == 0
        doc = yaml.safe_load(ledger.read_text(encoding="utf-8"))
        finding = doc["findings"][0]
        if mutation == "first-from":
            finding["history"][0]["from"] = "open"
        elif mutation == "broken-chain":
            finding["history"].append(
                {
                    "at": "2026-08-26T00:00:00+00:00",
                    "from": "open",
                    "to": "repaired-verified",
                    "evidence": "terminal evidence",
                }
            )
            finding["state"] = "repaired-verified"
            finding["evidence"] = "terminal evidence"
        else:
            finding["evidence"] = "top-level evidence disagrees"
        ledger.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
        refused = run("validate", "--file", str(ledger))
        assert refused.returncode != 0, mutation


def test_resources_root_rejects_symlinked_parent_and_outside_target(
    tmp_path: pathlib.Path,
) -> None:
    resources = tmp_path / "resources"
    resources.mkdir()
    safe = resources / "safe.yaml"
    initialize(safe)

    outside = tmp_path / "outside"
    outside.mkdir()
    linked = resources / "linked"
    os.symlink(outside, linked)
    escaped = linked / "escaped.yaml"
    result = run(
        "init",
        "--file",
        str(escaped),
        "--engagement",
        "escape-fixture",
        "--principal-outcome",
        "Keep the ledger inside resources.",
        "--round-trip-budget",
        "0",
        "--proportionality",
        "One resources boundary.",
        resources_root=resources,
    )
    assert result.returncode != 0
    assert not (outside / "escaped.yaml").exists()

    external = outside / "external.yaml"
    result = run(
        "init",
        "--file",
        str(external),
        "--engagement",
        "outside-fixture",
        "--principal-outcome",
        "Keep the ledger inside resources.",
        "--round-trip-budget",
        "0",
        "--proportionality",
        "One resources boundary.",
        resources_root=resources,
    )
    assert result.returncode != 0
    assert not external.exists()


def test_concurrent_crossing_writers_cannot_both_report_success(
    tmp_path: pathlib.Path,
) -> None:
    ledger = tmp_path / "findings.yaml"
    initialize(ledger, budget=1)
    start = tmp_path / "start"
    workers: list[subprocess.Popen[str]] = []
    wrapper = (
        "import os,pathlib,sys,time;"
        "ready=pathlib.Path(sys.argv[1]);start=pathlib.Path(sys.argv[2]);"
        "ready.write_text('ready');"
        "deadline=time.monotonic()+10;"
        "\nwhile not start.exists():\n"
        "  assert time.monotonic()<deadline\n"
        "  time.sleep(0.001)\n"
        "os.execv(sys.executable,[sys.executable,*sys.argv[3:]])"
    )
    command = [
        str(SCRIPT),
        "record-crossing",
        "--resources-root",
        str(tmp_path),
        "--file",
        str(ledger),
        "--expected-count",
        "0",
        "--evidence",
        "One synchronized provider-boundary crossing.",
    ]
    for index in range(8):
        ready = tmp_path / f"ready-{index}"
        workers.append(
            subprocess.Popen(
                [sys.executable, "-c", wrapper, str(ready), str(start), *command],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        )
    deadline = time.monotonic() + 10
    while len(list(tmp_path.glob("ready-*"))) != len(workers):
        assert time.monotonic() < deadline
        time.sleep(0.005)
    start.write_text("start", encoding="utf-8")
    results = [worker.communicate(timeout=15) + (worker.returncode,) for worker in workers]
    assert [result[2] for result in results].count(0) == 1, results
    trips = yaml.safe_load(ledger.read_text(encoding="utf-8"))["engagement"][
        "principal_courier_round_trips"
    ]
    assert trips["count"] == 1
    assert len(trips["history"]) == 1

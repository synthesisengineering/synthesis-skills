from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml


SCRIPT_DIR = Path(__file__).resolve().parent
RUNNER = SCRIPT_DIR / "acceptance_suite.py"
SKILL_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SKILL_ROOT.parents[1]


def fixture_file(root: Path) -> Path:
    (root / "tool.py").write_text("# production boundary fixture\n", encoding="utf-8")
    tests = root / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    target = tests / "test_probe.py"
    target.write_text(
        "def test_pass():\n    assert True\n\n"
        "def test_fail():\n    assert False\n",
        encoding="utf-8",
    )
    return target


def manifest_payload() -> dict:
    return {
        "schema": 1,
        "suite": "fixture-suite",
        "membership": "closed",
        "production_entry_point": "tool.py run",
        "enforcing_boundary": "before fixture state change",
        "receipt_consumer": "fixture boundary",
        "expected_status": "pass",
        "unverified_remainder": "behavior outside declared probes",
        "changed_surfaces": [
            {"path": "tool.py", "cases": ["passing-probe"]},
        ],
        "cases": [
            {
                "id": "passing-probe",
                "control_class": "acceptance-test",
                "fixture": "tests/test_probe.py::test_pass",
                "motivating_defect": "fixture-defect",
            }
        ],
    }


def write_manifest(root: Path, payload: dict) -> Path:
    path = root / "acceptance-suite.yaml"
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


def run_cli(root: Path, action: str, manifest: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            action,
            "--manifest",
            str(manifest),
            "--repo-root",
            str(root),
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def init_change_repository(root: Path) -> str:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    for key, value in (
        ("user.name", "Acceptance Fixture"),
        ("user.email", "acceptance@example.invalid"),
        ("core.hooksPath", "/dev/null"),
    ):
        subprocess.run(
            ["git", "-C", str(root), "config", key, value],
            check=True,
        )
    subprocess.run(
        ["git", "-C", str(root), "commit", "--allow-empty", "-qm", "base"],
        check=True,
    )
    return subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def commit_change_repository(root: Path) -> None:
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-qm", "candidate"],
        check=True,
    )


def schema2_payload() -> dict:
    payload = manifest_payload()
    payload["schema"] = 2
    payload["change_base_policy"] = "boundary-supplied-git-diff"
    payload["receipt_consumer"] = (
        "synthesis-skills-manager.release.consume-acceptance.v1"
    )
    payload["changed_surfaces"] = [
        {"path": "tool.py", "cases": ["passing-probe"]},
        {"path": "tests/test_probe.py", "cases": ["passing-probe"]},
        {"path": "acceptance-suite.yaml", "cases": ["passing-probe"]},
    ]
    return payload


def test_manifest_rejects_open_membership(tmp_path: Path) -> None:
    fixture_file(tmp_path)
    payload = manifest_payload()
    payload["membership"] = "open"
    completed = run_cli(tmp_path, "validate", write_manifest(tmp_path, payload))

    assert completed.returncode == 2
    assert "membership must be closed" in completed.stdout


def test_manifest_requires_boundary_and_expected_status(tmp_path: Path) -> None:
    fixture_file(tmp_path)
    for missing, message in (
        ("enforcing_boundary", "enforcing_boundary"),
        ("expected_status", "expected_status"),
    ):
        payload = manifest_payload()
        payload.pop(missing)
        completed = run_cli(tmp_path, "validate", write_manifest(tmp_path, payload))
        assert completed.returncode == 2
        assert message in completed.stdout


def test_manifest_rejects_duplicate_case_ids(tmp_path: Path) -> None:
    fixture_file(tmp_path)
    payload = manifest_payload()
    payload["cases"].append(dict(payload["cases"][0]))
    completed = run_cli(tmp_path, "validate", write_manifest(tmp_path, payload))

    assert completed.returncode == 2
    assert "duplicate case id" in completed.stdout


def test_runner_records_every_probe_terminal_state(tmp_path: Path) -> None:
    fixture_file(tmp_path)
    payload = manifest_payload()
    payload["changed_surfaces"][0]["cases"].append("failing-probe")
    payload["cases"].append(
        {
            "id": "failing-probe",
            "control_class": "acceptance-test",
            "fixture": "tests/test_probe.py::test_fail",
            "motivating_defect": "fixture-negative-polarity",
            "expected_status": "fail",
        }
    )
    completed = run_cli(tmp_path, "run", write_manifest(tmp_path, payload))

    assert completed.returncode == 0, completed.stdout + completed.stderr
    result = json.loads(completed.stdout)
    assert result["coverage"] == {"declared": 2, "terminal": 2, "not_run": 0}
    assert [(case["id"], case["status"], case["matched"]) for case in result["cases"]] == [
        ("passing-probe", "passed", True),
        ("failing-probe", "failed", True),
    ]


def test_runner_refuses_expected_status_mismatch(tmp_path: Path) -> None:
    fixture_file(tmp_path)
    payload = manifest_payload()
    payload["cases"][0]["fixture"] = "tests/test_probe.py::test_fail"
    completed = run_cli(tmp_path, "run", write_manifest(tmp_path, payload))

    assert completed.returncode == 1
    result = json.loads(completed.stdout)
    assert result["cases"][0]["status"] == "failed"
    assert result["cases"][0]["expected_status"] == "pass"
    assert result["cases"][0]["matched"] is False


def test_enforced_gate_requires_receipt_consumer(tmp_path: Path) -> None:
    fixture_file(tmp_path)
    payload = manifest_payload()
    payload.pop("receipt_consumer")
    payload["cases"][0]["control_class"] = "enforced-gate"
    completed = run_cli(tmp_path, "validate", write_manifest(tmp_path, payload))

    assert completed.returncode == 2
    assert "receipt_consumer" in completed.stdout


def test_changed_surfaces_reference_existing_cases(tmp_path: Path) -> None:
    fixture_file(tmp_path)
    payload = manifest_payload()
    payload["changed_surfaces"][0]["cases"] = ["missing-case"]
    completed = run_cli(tmp_path, "validate", write_manifest(tmp_path, payload))

    assert completed.returncode == 2
    assert "missing-case" in completed.stdout


def test_manifest_path_is_resolved_from_repo_root(tmp_path: Path) -> None:
    fixture_file(tmp_path)
    write_manifest(tmp_path, manifest_payload())
    completed = subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "validate",
            "--manifest",
            "acceptance-suite.yaml",
            "--repo-root",
            str(tmp_path),
            "--json",
        ],
        cwd=tmp_path.parent,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_manifest_rejects_symlinked_fixture(tmp_path: Path) -> None:
    fixture_file(tmp_path)
    outside = tmp_path.parent / "outside_probe.py"
    outside.write_text("def test_pass():\n    assert True\n", encoding="utf-8")
    target = tmp_path / "tests" / "test_probe.py"
    target.unlink()
    target.symlink_to(outside)
    completed = run_cli(tmp_path, "validate", write_manifest(tmp_path, manifest_payload()))

    assert completed.returncode == 2
    assert "symlink" in completed.stdout


def test_schema2_rejects_undeclared_git_changed_surface(tmp_path: Path) -> None:
    base = init_change_repository(tmp_path)
    fixture_file(tmp_path)
    (tmp_path / "undeclared_production.py").write_text(
        "raise RuntimeError('must be declared')\n",
        encoding="utf-8",
    )
    manifest = write_manifest(tmp_path, schema2_payload())
    commit_change_repository(tmp_path)
    completed = subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "run",
            "--manifest",
            str(manifest),
            "--repo-root",
            str(tmp_path),
            "--change-base",
            base,
            "--transaction-id",
            "fixture-undeclared-change",
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 2
    assert "undeclared_production.py" in completed.stdout
    assert "authoritative Git change universe" in completed.stdout


def test_schema2_receipt_binds_transaction_and_git_state(tmp_path: Path) -> None:
    base = init_change_repository(tmp_path)
    fixture_file(tmp_path)
    manifest = write_manifest(tmp_path, schema2_payload())
    commit_change_repository(tmp_path)
    completed = subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "run",
            "--manifest",
            str(manifest),
            "--repo-root",
            str(tmp_path),
            "--change-base",
            base,
            "--transaction-id",
            "fixture-transaction",
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    receipt = json.loads(completed.stdout)
    assert receipt["receipt_schema"] == "acceptance-run-receipt-v1"
    assert receipt["transaction_id"] == "fixture-transaction"
    assert receipt["change_base"] == base
    assert receipt["change_head"]
    assert receipt["head_tree"]
    assert receipt["manifest_sha256"]
    assert receipt["changed_paths_sha256"]
    assert receipt["changed_paths"] == sorted(
        ["acceptance-suite.yaml", "tests/test_probe.py", "tool.py"]
    )
    assert receipt["issues_authority_receipt"] is False


def test_shipped_manifest_validates() -> None:
    completed = run_cli(REPO_ROOT, "validate", SKILL_ROOT / "acceptance-suite.yaml")

    assert completed.returncode == 0, completed.stdout + completed.stderr
    result = json.loads(completed.stdout)
    assert result["ok"] is True
    assert result["membership"] == "closed"
    # Derive the expected count from the manifest rather than pinning a literal.
    # A hardcoded total describes one release's suite, so every later release
    # fails this check for the sole reason that it is a different release —
    # noise that says nothing about whether the shipped manifest is consumable.
    # What matters is that the runner and the manifest agree, and that closed
    # membership is real: every declared case is present and none is invented.
    declared = yaml.safe_load(
        (SKILL_ROOT / "acceptance-suite.yaml").read_text(encoding="utf-8")
    )
    assert result["cases_declared"] == len(declared["cases"])
    assert result["cases_declared"] > 0
    referenced = {
        case_id
        for surface in declared["changed_surfaces"]
        for case_id in surface["cases"]
    }
    assert referenced == {case["id"] for case in declared["cases"]}


def test_schema2_accepts_any_wellformed_consume_acceptance_consumer(
    tmp_path: Path,
) -> None:
    fixture_file(tmp_path)
    payload = schema2_payload()
    payload["receipt_consumer"] = (
        "another-repo.gated-release.consume-acceptance.v1"
    )
    completed = run_cli(tmp_path, "validate", write_manifest(tmp_path, payload))

    assert completed.returncode == 0, completed.stdout + completed.stderr
    receipt = json.loads(completed.stdout)
    assert receipt["receipt_consumer"] == (
        "another-repo.gated-release.consume-acceptance.v1"
    )


def test_schema2_refuses_malformed_consumer_id(tmp_path: Path) -> None:
    fixture_file(tmp_path)
    for malformed in (
        "fixture boundary",
        "release.v1",
        "synthesis-skills-manager.release.consume-acceptance",
        "Upper.Case.consume-acceptance.v1",
        ".consume-acceptance.v1",
    ):
        payload = schema2_payload()
        payload["receipt_consumer"] = malformed
        completed = run_cli(
            tmp_path, "validate", write_manifest(tmp_path, payload)
        )
        assert completed.returncode == 2, malformed
        assert "consume-acceptance" in completed.stdout, malformed

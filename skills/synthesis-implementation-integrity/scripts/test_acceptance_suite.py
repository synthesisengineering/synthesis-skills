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
        "schema": 2,
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


def test_shipped_manifest_validates() -> None:
    completed = run_cli(REPO_ROOT, "validate", SKILL_ROOT / "acceptance-suite.yaml")

    assert completed.returncode == 0, completed.stdout + completed.stderr
    result = json.loads(completed.stdout)
    assert result["ok"] is True
    assert result["membership"] == "closed"
    assert result["cases_declared"] == 21

"""Exercise the actual CLI and its release dependency verification boundary."""

from pathlib import Path
import hashlib
import json
import sys
import pytest

S = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(S / "synthesis-onboarding/scripts"), str(Path(__file__).parent)]
import synthesis_cli as cli  # noqa: E402 - source-bound sibling owner
import release_runtime as runtime  # noqa: E402 - source-bound sibling owner
import system_contract  # noqa: E402 - source-bound sibling owner
import test_release_runtime as runtime_fixtures  # noqa: E402 - explicit source fixture
active = runtime_fixtures.active
replace = runtime_fixtures.replace
from test_p13_governance import inventory  # noqa: E402 - explicit source fixture
from test_team_contract import contract  # noqa: E402 - explicit source fixture


def test_cli_contribution_report_is_censored_not_a_production_slo(tmp_path, capsys):
    document = contract()
    document["people"][1]["roles"].append("maintainer")
    team = tmp_path / "team.json"
    team.write_text(json.dumps(document))
    issues = tmp_path / "issues.json"
    issues.write_text(json.dumps(inventory()))
    request = tmp_path / "request.json"
    request.write_text(
        json.dumps(
            {
                "team": str(team),
                "team_digest": hashlib.sha256(team.read_bytes()).hexdigest(),
                "inventory": str(issues),
            }
        )
    )
    assert (
        cli.main(
            ["team", "contributions", "--request", str(request), "--json"],
            state=system_contract.SystemState(tmp_path / "home"),
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    assert (
        report["production_slo"] is None and report["remote_coverage_verified"] is False
    )


@pytest.mark.parametrize(
    "dependency",
    [
        "synthesis-project-management/scripts/team_contract.py",
        "synthesis-project-management/scripts/contribution_evidence.py",
        "synthesis-context-lifecycle/scripts/record_transaction.py",
        "synthesis-onboarding/scripts/team_retirement.py",
        "synthesis-project-management/scripts/coordination_process.py",
        "synthesis-autopilot/scripts/operator_status.py",
    ],
)
def test_exact_team_runtime_dependency_drift_refuses(active, monkeypatch, dependency):
    pointer, root, data = active
    script = "synthesis-project-management/scripts/team_records.py"
    names = (script, *runtime.ENTRYPOINT_DEPENDENCIES[script])
    assert dependency in names
    for name in names:
        p = root / "skills" / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("pass\n")
    replace(pointer, data, content_digest=system_contract.canonical_tree_digest(root))
    verified = runtime.verified_release(pointer)
    verified["_verification_mode"] = runtime.VERIFICATION_MODE_RECEIPT
    hashes = {name: runtime.file_digest(root / "skills" / name) for name in names}
    monkeypatch.setattr(
        runtime, "_load_activation_receipt", lambda _: {"entrypoints": hashes}
    )
    runtime.verify_dependencies(verified, script)
    (root / "skills" / dependency).write_text('raise RuntimeError("unreviewed")\n')
    with pytest.raises(runtime.RuntimeContractError):
        runtime.verify_dependencies(verified, script)

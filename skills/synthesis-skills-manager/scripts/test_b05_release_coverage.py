from pathlib import Path


def test_meeting_prep_is_a_real_release_and_hosted_suite():
    import ast
    import yaml

    root = Path(__file__).resolve().parents[3]
    tree = ast.parse(
        (root / "skills/synthesis-skills-manager/scripts/release.py").read_text()
    )
    checks = dict(
        ast.literal_eval(
            next(
                node.value
                for node in tree.body
                if isinstance(node, ast.AnnAssign)
                and getattr(node.target, "id", "") == "REQUIRED_CHECKS"
            )
        )
    )
    assert checks["pytest.meeting-prep"] == [
        "python3",
        "-m",
        "pytest",
        "skills/synthesis-meeting-prep/scripts/",
        "-q",
    ]
    ci = yaml.safe_load((root / ".github/workflows/validate.yml").read_text())
    assert "python skills/synthesis-skills-manager/scripts/release.py --repo-root . --source-checks-only" in [
        step.get("run", "") for step in ci["jobs"]["source-checks"]["steps"]
    ]


def test_acquisition_entry_repair_regression_and_doctor_are_gated():
    """A repaired acquisition owner must actually run in every release lane."""
    import ast
    import shlex

    import yaml

    root = Path(__file__).resolve().parents[3]
    tree = ast.parse(
        (root / "skills/synthesis-skills-manager/scripts/release.py").read_text()
    )
    checks = dict(
        ast.literal_eval(
            next(
                node.value
                for node in tree.body
                if isinstance(node, ast.AnnAssign)
                and getattr(node.target, "id", "") == "REQUIRED_CHECKS"
            )
        )
    )
    expected = {
        "skills/synthesis-meeting-transcripts/test_acquisition_tools.py",
        "skills/synthesis-meeting-transcripts/test_acquisition_regressions.py",
        "skills/synthesis-meeting-transcripts/test_acquisition_entry.py",
        "skills/synthesis-meeting-transcripts/test_acquisition_repair.py",
        "skills/synthesis-meeting-transcripts/test_extract_commitments.py",
        "skills/synthesis-meeting-transcripts/test_version_parity.py",
        "skills/synthesis-meeting-transcripts/optional-workspace-mcp/test_doctor.py",
    }
    command = checks["pytest.meeting-acquisition"]
    assert command[:3] == ["python3", "-m", "pytest"]
    assert command[-1] == "-q"
    assert set(command[3:-1]) == expected
    assert len(command[3:-1]) == len(expected)
    ci = yaml.safe_load((root / ".github/workflows/validate.yml").read_text())
    hosted = [
        shlex.split(step.get("run", "")) for step in ci["jobs"]["source-checks"]["steps"]
    ]
    assert ["python", "skills/synthesis-skills-manager/scripts/release.py", "--repo-root", ".", "--source-checks-only"] in hosted
    agents = (root / "AGENTS.md").read_text()
    assert "python3 skills/synthesis-skills-manager/scripts/release.py --repo-root . --source-checks-only" in agents

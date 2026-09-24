"""The full autopilot suite is enforced by local and hosted release contracts."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_all_release_contracts_run_the_whole_autopilot_suite():
    assert "python3 -m pytest skills/synthesis-autopilot/scripts/ -q" in (ROOT / "AGENTS.md").read_text()
    assert "python -m pytest skills/synthesis-autopilot/scripts/ -q" in (ROOT / ".github/workflows/validate.yml").read_text()
    text = (ROOT / "skills/synthesis-skills-manager/scripts/release.py").read_text()
    assert '("pytest.autopilot", ["python3", "-m", "pytest", "skills/synthesis-autopilot/scripts/", "-q"])' in text

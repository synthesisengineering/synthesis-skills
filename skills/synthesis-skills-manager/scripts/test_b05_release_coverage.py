from pathlib import Path


def test_meeting_prep_is_a_real_release_and_hosted_suite():
    import ast
    import yaml
    root = Path(__file__).resolve().parents[3]
    tree = ast.parse((root / 'skills/synthesis-skills-manager/scripts/release.py').read_text())
    checks = dict(ast.literal_eval(next(node.value for node in tree.body
        if isinstance(node, ast.AnnAssign) and getattr(node.target, 'id', '') == 'REQUIRED_CHECKS')))
    assert checks['pytest.meeting-prep'] == ['python3', '-m', 'pytest', 'skills/synthesis-meeting-prep/scripts/', '-q']
    ci = yaml.safe_load((root / '.github/workflows/validate.yml').read_text())
    assert 'python -m pytest skills/synthesis-meeting-prep/scripts/ -q' in [
        step.get('run', '') for step in ci['jobs']['conformance']['steps']]

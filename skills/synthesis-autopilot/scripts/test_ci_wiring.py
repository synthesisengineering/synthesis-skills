"""The full autopilot suite is enforced by local and hosted release contracts."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_all_release_contracts_run_the_whole_autopilot_suite():
    import ast
    release = ast.parse((ROOT / 'skills/synthesis-skills-manager/scripts/release.py').read_text())
    checks = next(n for n in release.body if isinstance(n, ast.AnnAssign) and getattr(n.target, 'id', '') == 'REQUIRED_CHECKS')
    commands = dict(ast.literal_eval(checks.value))
    for group in ('state', 'native', 'evaluation', 'core'):
        command = 'skills/synthesis-skills-manager/scripts/release_check_groups.py --group ' + group
        assert 'python3 ' + command in (ROOT / 'AGENTS.md').read_text()
        assert 'python ' + command in (ROOT / '.github/workflows/validate.yml').read_text()
        assert commands['pytest.autopilot.' + group] == ['python3', *command.split()]



"""Candidate additions for synthesis-autopilot/scripts/test_ci_wiring.py."""
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


@pytest.fixture
def ci_sandbox():
    root = Path(__file__).resolve().parents[3]
    helper = root / '.github/scripts/check-ci-sandbox.py'
    spec = importlib.util.spec_from_file_location('ci_sandbox_probe', helper)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_ci_sandbox_preflight_is_required_before_consumer_tests():
    import yaml
    root = Path(__file__).resolve().parents[3]
    workflow = yaml.safe_load((root / '.github/workflows/validate.yml').read_text())
    job = workflow['jobs']['conformance']
    steps = job['steps']
    setup = next(step for step in steps if step.get('name') == 'Install OS isolation for executable consumer acceptance')
    assert setup['run'].splitlines() == [
        'sudo apt-get update && sudo apt-get install -y bubblewrap',
        'python .github/scripts/check-ci-sandbox.py',
        'synthesis_ci_chromium="$(command -v google-chrome || command -v chromium || command -v chromium-browser || true)"',
        'test -n "$synthesis_ci_chromium"',
        '"$synthesis_ci_chromium" --version',
        'echo "SYNTHESIS_TEST_CHROMIUM=$synthesis_ci_chromium" >> "$GITHUB_ENV"',
    ]
    assert not setup.get('continue-on-error') and not job.get('continue-on-error')
    consumers = next(step for step in steps if step.get('run') == 'python skills/synthesis-skills-manager/scripts/release_check_groups.py --group state')
    assert steps.index(setup) < steps.index(consumers)
    browser_consumers = next(step for step in steps
                             if 'synthesis-decision-packet/scripts/test_*.py' in step.get('run', ''))
    assert steps.index(setup) < steps.index(browser_consumers)


def _result(code=0, stdout='', stderr='', **extra):
    return {'returncode': code, 'stdout': stdout, 'stderr': stderr, **extra}


def _scenario(monkeypatch, module, results, settings=None, profile_error=None, host='github-hosted'):
    monkeypatch.setenv('GITHUB_ACTIONS', 'true')
    monkeypatch.setenv('RUNNER_ENVIRONMENT', host)
    commands = []
    def run(argv, **kwargs):
        commands.append((list(argv), kwargs))
        assert results, 'Unexpected additional command'
        return {'argv': list(argv), **results.pop(0)}
    monkeypatch.setattr(module, 'run', run)
    monkeypatch.setattr(module, 'read_settings', lambda: settings if settings is not None else {
        module.APPARMOR_ENABLED: 'Y', module.RESTRICT_USERNS: '1'})
    def profile():
        if profile_error:
            raise ValueError(profile_error)
        return module.APPROVED_PROFILE
    monkeypatch.setattr(module, 'read_approved_profile', profile)
    report = module.ensure_sandbox(['/usr/bin/bwrap', 'exact-production-command'], '/trusted/python')
    assert not results, 'Expected command was omitted'
    return report, commands


def _control():
    return _result(stdout='interpreter-ready\n')


def _denial():
    return _result(1, stderr='bwrap: Creating new namespace failed: Operation not permitted\n')


def _owner(module):
    return _result(stdout='apparmor-profiles: ' + str(module.PROFILE) + '\n')


def test_ci_sandbox_ready_never_changes_policy(ci_sandbox, monkeypatch):
    result, commands = _scenario(monkeypatch, ci_sandbox, [_control(), _result(stdout='sandbox-ready\n')])
    assert result['status'] == 'PASS' and not result['repair_attempted'] and len(commands) == 2
    assert all(kwargs['env'] == ci_sandbox.PROBE_ENV for _, kwargs in commands)
    assert 'LD_LIBRARY_PATH' not in ci_sandbox.PROBE_ENV


@pytest.mark.parametrize('failure', [
    _result(127, stderr='error while loading shared libraries: libpython3.12.so.1.0'),
    _result(1, stderr='bwrap: Creating new namespace failed: Invalid argument'),
    _result(0, stdout='wrong-output'),
    _result(1, stderr='bwrap: Creating new namespace failed: Operation not permitted', timed_out=True),
    _result(1, stderr='bwrap: Creating new namespace failed: Operation not permitted', output_limit_exceeded=True),
])
def test_ci_sandbox_other_failures_never_change_policy(ci_sandbox, monkeypatch, failure):
    result, commands = _scenario(monkeypatch, ci_sandbox, [_control(), failure])
    assert result['status'] == 'FAIL' and not result['repair_attempted'] and len(commands) == 2


def test_ci_sandbox_failed_interpreter_does_not_load_profile(ci_sandbox, monkeypatch):
    result, commands = _scenario(monkeypatch, ci_sandbox, [_result(127, stderr='libpython missing'), _denial()])
    assert result['status'] == 'FAIL' and not result['repair_attempted'] and len(commands) == 2


@pytest.mark.parametrize('host', ['', 'self-hosted'])
def test_ci_sandbox_local_and_self_hosted_cannot_change_policy(ci_sandbox, monkeypatch, host):
    result, commands = _scenario(monkeypatch, ci_sandbox, [_control(), _denial()], host=host)
    assert result['status'] == 'FAIL' and not result['repair_attempted'] and len(commands) == 2


@pytest.mark.parametrize('actions,host', [('', ''), ('true', 'self-hosted'), ('false', 'github-hosted')])
def test_ci_sandbox_main_refuses_outside_hosted_actions_before_import(ci_sandbox, monkeypatch, actions, host):
    monkeypatch.setattr(ci_sandbox.platform, 'system', lambda: 'Linux')
    monkeypatch.setenv('GITHUB_ACTIONS', actions)
    monkeypatch.setenv('RUNNER_ENVIRONMENT', host)
    with pytest.raises(SystemExit, match='GitHub-hosted'):
        ci_sandbox.main()


@pytest.mark.parametrize('failure', ['import', 'missing-bwrap'])
def test_ci_sandbox_main_reports_setup_failures(ci_sandbox, monkeypatch, capsys, failure):
    monkeypatch.setattr(ci_sandbox.platform, 'system', lambda: 'Linux')
    monkeypatch.setenv('GITHUB_ACTIONS', 'true')
    monkeypatch.setenv('RUNNER_ENVIRONMENT', 'github-hosted')
    def fail(*args, **kwargs):
        if failure == 'import':
            raise ImportError('missing runtime dependency')
        raise ValueError('Verified OS sandbox is unavailable; worker code was not executed')
    if failure == 'import':
        monkeypatch.setattr(ci_sandbox.importlib.util, 'spec_from_file_location', fail)
    else:
        monkeypatch.setattr(ci_sandbox.importlib.util, 'spec_from_file_location', lambda *args: SimpleNamespace(loader=SimpleNamespace(exec_module=lambda module: None)))
        monkeypatch.setattr(ci_sandbox.importlib.util, 'module_from_spec', lambda spec: SimpleNamespace(_sandbox_command=fail))
    assert ci_sandbox.main() == 1
    report = json.loads(capsys.readouterr().out)
    assert report['status'] == 'FAIL' and report['error_type'] == ('ImportError' if failure == 'import' else 'ValueError')


@pytest.mark.parametrize('stderr,eligible', [
    ('bwrap: No permissions to creating new namespace, likely because the kernel does not allow non-privileged user namespaces. On e.g. debian this can be enabled with extra configuration.', True),
    ('bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted', True),
    ('bwrap: loopback: Failed RTM_NEWADDR: Permission denied', True),
    ('bwrap: loopback: Failed RTM_NEWADDR: Invalid argument', False),
    ('bwrap: loopback: Failed RTM_NEWADDR: Input/output error', False),
    ('bwrap: writing uid_map: Operation not permitted', False),
    ('bwrap: setting up gid map: Permission denied', False),
])
def test_ci_sandbox_classifies_only_upstream_namespace_denials(ci_sandbox, stderr, eligible):
    state = {ci_sandbox.APPARMOR_ENABLED: 'Y', ci_sandbox.RESTRICT_USERNS: '1'}
    assert ci_sandbox.namespace_denial(_result(1, stderr=stderr), state) is eligible


@pytest.mark.parametrize('settings', [{}, {'enabled': 'Y'},
    {'/sys/module/apparmor/parameters/enabled': 'Y', '/proc/sys/kernel/apparmor_restrict_unprivileged_userns': '0'}])
def test_ci_sandbox_unproven_apparmor_state_never_changes_policy(ci_sandbox, monkeypatch, settings):
    result, commands = _scenario(monkeypatch, ci_sandbox, [_control(), _denial()], settings=settings)
    assert result['status'] == 'FAIL' and not result['repair_attempted'] and len(commands) == 2


def test_ci_sandbox_repairs_only_reviewed_package_then_repeats_exact_probe(ci_sandbox, monkeypatch):
    result, commands = _scenario(monkeypatch, ci_sandbox,
        [_control(), _denial(), _result(), _owner(ci_sandbox), _result(), _result(stdout='sandbox-ready\n')])
    assert result['status'] == 'PASS' and result['repair_attempted']
    assert commands[2][0] == ['/usr/bin/sudo', '-n', '/usr/bin/apt-get', 'install', '-y', 'apparmor-profiles']
    assert commands[4][0] == ['/usr/bin/sudo', '-n', '/usr/sbin/apparmor_parser', '--replace']
    assert commands[4][1]['input_text'] == ci_sandbox.APPROVED_PROFILE
    assert commands[1] == commands[5]


@pytest.mark.parametrize('stage', ['package', 'owner', 'profile', 'parser', 'second-probe'])
def test_ci_sandbox_each_failed_repair_step_stops(ci_sandbox, monkeypatch, stage):
    results = [_control(), _denial()]
    if stage == 'package':
        results += [_result(100, stderr='package installation failed')]
    else:
        results += [_result(), _result(stdout='another-package: wrong-path') if stage == 'owner' else _owner(ci_sandbox)]
        if stage not in ('owner', 'profile'):
            results += [_result(1, stderr='profile denied') if stage == 'parser' else _result()]
        if stage == 'second-probe':
            results += [_denial()]
    result, commands = _scenario(monkeypatch, ci_sandbox, results,
        profile_error='profile differs' if stage == 'profile' else None)
    assert result['status'] == 'FAIL' and result['repair_attempted']
    assert len(commands) == {'package': 3, 'owner': 4, 'profile': 4, 'parser': 5, 'second-probe': 6}[stage]


@pytest.mark.parametrize('replacement', [
    ('/usr/bin/bwrap', '/usr/**'),
    ('audit deny capability,', 'allow capability,'),
    ('flags=(attach_disconnected)', 'flags=(unconfined)'),
    ('allow px /** -> bwrap//&unpriv_bwrap,', 'allow ix /**,'),
    ('include if exists <local/unpriv_bwrap>', 'include <arbitrary>'),
])
def test_ci_sandbox_rejects_changed_profile_authority(ci_sandbox, replacement):
    ci_sandbox.validate_profile(ci_sandbox.APPROVED_PROFILE)
    with pytest.raises(ValueError, match='differs'):
        ci_sandbox.validate_profile(ci_sandbox.APPROVED_PROFILE.replace(*replacement))


def test_ci_sandbox_local_override_is_not_loaded(ci_sandbox, monkeypatch):
    monkeypatch.setattr(ci_sandbox.os.path, 'lexists', lambda p: '/local/' in str(p))
    monkeypatch.setattr(ci_sandbox, 'check_parents', lambda *a, **k: None)
    monkeypatch.setattr(ci_sandbox, 'trusted_file', lambda p, **kwargs: ci_sandbox.APPROVED_PROFILE if p == ci_sandbox.PROFILE else 'allow capability,')
    with pytest.raises(ValueError, match='local profile override'):
        ci_sandbox.read_approved_profile()


def test_ci_sandbox_bounds_real_command_output(ci_sandbox):
    result = ci_sandbox.run([sys.executable, '-I', '-c', 'print("x"*100000)'], limit=128)
    assert result['output_limit_exceeded'] and len(result['stdout'].encode()) <= 128
    assert not ci_sandbox.succeeded(result)


def test_ci_sandbox_bounds_real_command_deadline(ci_sandbox):
    result = ci_sandbox.run([sys.executable, '-I', '-c', 'import time;time.sleep(5)'], timeout=.1)
    assert result['timed_out'] and not ci_sandbox.succeeded(result)


def test_ci_sandbox_profile_bytes_use_anonymous_stdin(ci_sandbox):
    text = ci_sandbox.APPROVED_PROFILE
    result = ci_sandbox.run([sys.executable, '-I', '-c', 'import sys;sys.stdout.write(sys.stdin.read())'], input_text=text)
    assert ci_sandbox.succeeded(result) and result['stdout'] == text
    assert result['stdin_bytes'] == len(text.encode())
    import hashlib
    assert result['stdin_sha256'] == hashlib.sha256(text.encode()).hexdigest()


def test_ci_sandbox_input_size_fails_before_process(ci_sandbox, monkeypatch):
    calls = []
    monkeypatch.setattr(ci_sandbox.subprocess, 'Popen', lambda *a, **k: calls.append(a))
    result = ci_sandbox.run(['unused'], input_text='x' * 32769)
    assert not calls and not ci_sandbox.succeeded(result) and result.get('error')


def test_ci_sandbox_packaged_snapshot_does_not_trust_mutable_parent(ci_sandbox, monkeypatch, tmp_path):
    import stat
    path = tmp_path / 'profile'
    path.write_text(ci_sandbox.APPROVED_PROFILE)
    original = Path.lstat
    fields = ('st_dev', 'st_ino', 'st_mode', 'st_size', 'st_mtime_ns', 'st_nlink', 'st_gid')
    def fixture_stat(value):
        observed = original(value)
        data = {key: getattr(observed, key) for key in fields}
        data['st_uid'] = 0
        if value == tmp_path:
            data['st_mode'] |= stat.S_IWGRP
        return SimpleNamespace(**data)
    monkeypatch.setattr(Path, 'lstat', fixture_stat)
    original_fstat = ci_sandbox.os.fstat
    def fixture_fstat(fd):
        observed = original_fstat(fd)
        return SimpleNamespace(st_uid=0, **{key: getattr(observed, key) for key in fields})
    monkeypatch.setattr(ci_sandbox.os, 'fstat', fixture_fstat)
    with pytest.raises(ValueError, match='Unsafe profile parent'):
        ci_sandbox.trusted_file(path)
    snapshot = ci_sandbox.trusted_file(path, trusted_parents=False)
    ci_sandbox.validate_profile(snapshot)
    assert snapshot == ci_sandbox.APPROVED_PROFILE


def test_ci_sandbox_only_package_snapshot_relaxes_parent_metadata(ci_sandbox, monkeypatch):
    calls = []
    def read(path, *, trusted_parents=True):
        calls.append((path, trusted_parents))
        return ci_sandbox.APPROVED_PROFILE if path == ci_sandbox.PROFILE else '# empty local override\n'
    monkeypatch.setattr(ci_sandbox, 'trusted_file', read)
    monkeypatch.setattr(ci_sandbox.os.path, 'lexists', lambda p: '/local/' in str(p))
    monkeypatch.setattr(ci_sandbox, 'check_parents', lambda *a, **k: None)
    assert ci_sandbox.read_approved_profile() == ci_sandbox.APPROVED_PROFILE
    assert calls == [(ci_sandbox.PROFILE, False),
        (Path('/etc/apparmor.d/local/bwrap-userns-restrict'), True),
        (Path('/etc/apparmor.d/local/unpriv_bwrap'), True)]


@pytest.mark.parametrize('directory', ['disable', 'force-complain'])
def test_ci_sandbox_preserves_admin_profile_flags(ci_sandbox, monkeypatch, directory):
    monkeypatch.setattr(ci_sandbox, 'trusted_file', lambda *a, **k: ci_sandbox.APPROVED_PROFILE)
    monkeypatch.setattr(ci_sandbox.os.path, 'lexists', lambda p: str(p) == '/etc/apparmor.d/' + directory + '/bwrap-userns-restrict')
    with pytest.raises(ValueError, match='Administrator profile flag'):
        ci_sandbox.read_approved_profile()


def test_ci_sandbox_absent_override_still_checks_parents(ci_sandbox, monkeypatch):
    monkeypatch.setattr(ci_sandbox, 'trusted_file', lambda *a, **k: ci_sandbox.APPROVED_PROFILE)
    monkeypatch.setattr(ci_sandbox.os.path, 'lexists', lambda _: False)
    def refuse(*a, **k):
        raise ValueError('Unsafe profile parent: fixture')
    monkeypatch.setattr(ci_sandbox, 'check_parents', refuse)
    with pytest.raises(ValueError, match='Unsafe profile parent'):
        ci_sandbox.read_approved_profile()


def test_ci_sandbox_stdin_nonreader_is_bounded(ci_sandbox):
    result = ci_sandbox.run([sys.executable, '-I', '-c', 'import time;time.sleep(5)'], input_text='x' * 32768, timeout=.1)
    assert result['timed_out'] and not ci_sandbox.succeeded(result)

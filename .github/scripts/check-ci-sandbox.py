"""Verify Linux CI isolation; repair only a proven restricted-userns prerequisite.

The sole approved profile is the distro-packaged AppArmor 4.0.1 profile whose
semantics are below. Primary source:
https://gitlab.com/apparmor/apparmor/-/raw/v4.0.1/profiles/apparmor/profiles/extras/bwrap-userns-restrict
"""
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import selectors
import signal
import stat
import subprocess
import sys
import tempfile
import time

ENV = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1'}
PROBE_ENV = {'PATH': os.defpath, 'LANG': 'C.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1'}
PROFILE = Path('/usr/share/apparmor/extra-profiles/bwrap-userns-restrict')
APPARMOR_ENABLED = '/sys/module/apparmor/parameters/enabled'
RESTRICT_USERNS = '/proc/sys/kernel/apparmor_restrict_unprivileged_userns'
APPROVED_PROFILE = '''
abi <abi/4.0>,
include <tunables/global>
profile bwrap /usr/bin/bwrap flags=(attach_disconnected) {
  allow capability,
  allow file rwlkm /{**,},
  allow network,
  allow unix,
  allow ptrace,
  allow signal,
  allow mqueue,
  allow io_uring,
  allow userns,
  allow mount,
  allow umount,
  allow pivot_root,
  allow dbus,
  allow px /** -> bwrap//&unpriv_bwrap,
  include if exists <local/bwrap-userns-restrict>
}
profile unpriv_bwrap flags=(attach_disconnected) {
  allow file rwlkm /{**,},
  allow network,
  allow unix,
  allow ptrace,
  allow signal,
  allow mqueue,
  allow io_uring,
  allow userns,
  allow mount,
  allow umount,
  allow pivot_root,
  allow dbus,
  allow pix /** -> &unpriv_bwrap,
  audit deny capability,
  include if exists <local/unpriv_bwrap>
}
'''


def run(argv, *, timeout=10, env=None, limit=32768):
    """Bound each output stream and the complete process-group lifetime."""
    result = {'argv': argv}
    try:
        proc = subprocess.Popen(argv, env=ENV if env is None else env,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                start_new_session=True)
    except OSError as error:
        return {**result, 'error': type(error).__name__ + ': ' + str(error)}
    chunks = {'stdout': bytearray(), 'stderr': bytearray()}
    deadline = time.monotonic() + timeout
    try:
        with selectors.DefaultSelector() as selector:
            for key in chunks:
                selector.register(getattr(proc, key), selectors.EVENT_READ, key)
            while selector.get_map() or proc.poll() is None:
                if time.monotonic() >= deadline:
                    result['timed_out'] = True
                    break
                for key, _ in selector.select(min(.05, max(0, deadline - time.monotonic()))):
                    raw = os.read(key.fileobj.fileno(), 4096)
                    if not raw:
                        selector.unregister(key.fileobj)
                        continue
                    space = limit - len(chunks[key.data])
                    chunks[key.data].extend(raw[:space])
                    if len(raw) > space:
                        result['output_limit_exceeded'] = True
                        break
                if result.get('output_limit_exceeded'):
                    break
    finally:
        if proc.poll() is None or result.get('timed_out') or result.get('output_limit_exceeded'):
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        proc.wait(timeout=5)
        proc.stdout.close()
        proc.stderr.close()
    return {**result, 'returncode': proc.returncode,
            **{key: value.decode('utf-8', 'replace') for key, value in chunks.items()}}


def succeeded(result, expected=None):
    return (result.get('returncode') == 0 and not result.get('error')
            and not result.get('timed_out') and not result.get('output_limit_exceeded')
            and (expected is None or result.get('stdout', '').strip() == expected))


def read_settings():
    result = {}
    for path in (APPARMOR_ENABLED, RESTRICT_USERNS,
                 '/proc/sys/kernel/unprivileged_userns_clone', '/proc/sys/user/max_user_namespaces'):
        try:
            with open(path) as stream:
                result[path] = stream.read(256).strip()
        except OSError as error:
            result[path] = {'error': type(error).__name__}
    return result


def profile_tokens(text):
    return re.sub(r'\s+', '', re.sub(r'#[^\n]*', '', text))


def validate_profile(text):
    if profile_tokens(text) != profile_tokens(APPROVED_PROFILE):
        raise ValueError('Distro profile differs from the reviewed bwrap attachment/child-capability policy')


def trusted_file(path):
    for parent in path.parents:
        metadata = parent.lstat()
        if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != 0 or metadata.st_mode & 0o022:
            raise ValueError('Unsafe profile parent: ' + str(parent))
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != 0 or metadata.st_mode & 0o022 or metadata.st_nlink != 1:
        raise ValueError('Unsafe profile file: ' + str(path))
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        opened = os.fstat(stream.fileno())
        if (opened.st_dev, opened.st_ino) != (metadata.st_dev, metadata.st_ino):
            raise ValueError('Profile changed before read')
        data = stream.read(32769)
    if len(data) > 32768:
        raise ValueError('Profile exceeds the review bound')
    after = path.lstat()
    fields = lambda value: (value.st_dev, value.st_ino, value.st_mode, value.st_size, value.st_mtime_ns)
    if fields(metadata) != fields(after):
        raise ValueError('Profile changed during read')
    return data.decode('utf-8')


def read_approved_profile():
    text = trusted_file(PROFILE)
    validate_profile(text)
    for path in (Path('/etc/apparmor.d/local/bwrap-userns-restrict'),
                 Path('/etc/apparmor.d/local/unpriv_bwrap')):
        if os.path.lexists(path) and profile_tokens(trusted_file(path)):
            raise ValueError('Unreviewed local profile override: ' + str(path))
    return text


def namespace_denial(result, settings):
    if result.get('timed_out') or result.get('output_limit_exceeded') or result.get('error'):
        return False
    stderr = result.get('stderr', '')
    observed = any(re.fullmatch(pattern, line) for line in stderr.splitlines() for pattern in (
        # Bubblewrap v0.9.0 bubblewrap.c raw_clone failure diagnostics.
        r'bwrap: No permissions to creating new namespace, likely because the kernel does not allow non-privileged user namespaces\..*',
        r'bwrap: Creating new namespace failed: (?:Operation not permitted|Permission denied)',
    ))
    return (result.get('returncode', 0) != 0 and observed
            and settings.get(APPARMOR_ENABLED) == 'Y' and settings.get(RESTRICT_USERNS) == '1')


def hosted_ci():
    # GitHub's documented defaults distinguish Actions from a personal host and
    # distinguish disposable GitHub-hosted runners from self-hosted machines.
    return os.environ.get('GITHUB_ACTIONS') == 'true' and os.environ.get('RUNNER_ENVIRONMENT') == 'github-hosted'


def ensure_sandbox(command, interpreter):
    """A failed or unproven correction never permits the subsequent test suite."""
    report = {'status': 'FAIL', 'commands': [], 'repair_attempted': False}
    def checked(argv, **kwargs):
        result = run(argv, **kwargs)
        report['commands'].append(result)
        return result
    control = checked([interpreter, '-I', '-c', 'print("interpreter-ready")'], env=PROBE_ENV)
    first = checked(command, env=PROBE_ENV)
    report['selected_kernel_settings'] = read_settings()
    if not succeeded(control, 'interpreter-ready'):
        report['reason'] = 'Sanitized interpreter control failed; no profile change'
        return report
    if succeeded(first, 'sandbox-ready'):
        report['status'] = 'PASS'
        return report
    if not namespace_denial(first, report['selected_kernel_settings']):
        report['reason'] = 'No proven restricted-userns prerequisite; no profile change'
        return report
    if not hosted_ci():
        report['reason'] = 'Profile repair is restricted to GitHub-hosted Actions runners'
        return report
    report['repair_attempted'] = True
    installed = checked(['/usr/bin/sudo', '-n', '/usr/bin/apt-get', 'install', '-y', 'apparmor-profiles'], timeout=120)
    if not succeeded(installed):
        report['reason'] = 'Distribution profile package installation failed'
        return report
    owned = checked(['/usr/bin/dpkg-query', '-S', str(PROFILE)])
    if not succeeded(owned, 'apparmor-profiles: ' + str(PROFILE)):
        report['reason'] = 'Profile is not owned by the expected distribution package'
        return report
    try:
        text = read_approved_profile()
        import hashlib
        report['profile_sha256'] = hashlib.sha256(text.encode()).hexdigest()
    except (OSError, UnicodeError, ValueError) as error:
        report['reason'] = str(error)
        return report
    loaded = checked(['/usr/bin/sudo', '-n', '/usr/sbin/apparmor_parser', '--replace', str(PROFILE)])
    if not succeeded(loaded):
        report['reason'] = 'Reviewed profile did not load'
        return report
    second = checked(command, env=PROBE_ENV)
    if not succeeded(second, 'sandbox-ready'):
        report['reason'] = 'Production sandbox remained unavailable after the reviewed profile load'
        return report
    report['status'] = 'PASS'
    return report


def main():
    if platform.system() != 'Linux' or not hosted_ci():
        raise SystemExit('This helper supports GitHub-hosted Linux Actions runners only')
    try:
        source = Path(__file__).resolve().parents[2]
        script = source / 'skills/synthesis-autopilot/scripts/evaluation_artifacts.py'
        sys.path.insert(0, str(script.parent))
        spec = importlib.util.spec_from_file_location('evaluation_artifacts', script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory(prefix='synthesis-ci-sandbox-probe-') as name:
            root = Path(name).resolve()
            script = root / 'probe.py'
            script.write_text('print("sandbox-ready")\n')
            command, provider = module._sandbox_command(root, root, script, [])
            report = ensure_sandbox(command, str(Path(sys.executable).resolve()))
            report.update({'provider': provider, 'python': sys.executable, 'base_prefix': sys.base_prefix,
                           'environment_keys': sorted(PROBE_ENV)})
    except Exception as error:
        report = {'status': 'FAIL', 'reason': 'CI sandbox setup could not finish',
                  'error_type': type(error).__name__, 'error': str(error)[:8192]}
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())

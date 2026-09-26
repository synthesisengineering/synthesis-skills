#!/usr/bin/env python3
"""Bounded, exhaustive autopilot release groups, using ordinary pytest collection.

Every group collects the entire directory before selecting its exact partition.
No file allowlist: newly collected files enter core unless a domain rule owns them.
Reports bind full/selected node IDs, all three execution phases and source bytes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import selectors
import signal
import stat
import subprocess
import sys
import tempfile
import time

GROUPS = ('state', 'native', 'evaluation', 'core')
AP = 'skills/synthesis-autopilot/scripts'
CHECK_SECONDS = 900
GROUP_SECONDS = 880  # collection, execution and reporting; 20s outer cleanup reserve
OUTPUT_BYTES = 8 * 1024 * 1024
REPORT_BYTES = 4 * 1024 * 1024
MAX_TESTS = 20000
MAX_SOURCE_BYTES = 128 * 1024 * 1024
STATE_PREFIXES = ('test_run_state', 'test_journal_', 'test_required_citations', 'test_search_budget',
                  'test_recovery_capsule', 'test_persistence_policy', 'test_operator_status')
NATIVE_PREFIXES = ('test_native_', 'test_codex_', 'test_prepared_', 'test_stop_', 'test_legacy_',
                   'test_observation_', 'test_owner_resume')
EVALUATION_PREFIXES = ('test_evaluation', 'test_consumer_', 'test_evidence_bridge', 'test_profile_evidence')


def group_for(nodeid: str) -> str:
    path = nodeid.split('::', 1)[0]
    if not path.startswith(AP + '/') or not path.endswith('.py') or '..' in Path(path).parts:
        raise ValueError('collection escaped the autopilot directory')
    name = Path(path).name
    choices = [name.startswith(prefixes) for prefixes in
               (STATE_PREFIXES, NATIVE_PREFIXES, EVALUATION_PREFIXES)]
    if sum(choices) > 1:
        raise ValueError('overlapping group ownership')
    return GROUPS[choices.index(True)] if any(choices) else 'core'


def partition(nodeids: list[str]) -> dict[str, list[str]]:
    if not nodeids or len(nodeids) > MAX_TESTS or len(set(nodeids)) != len(nodeids):
        raise ValueError('empty, duplicate or oversized collection')
    groups = {name: [] for name in GROUPS}
    for node in nodeids:
        groups[group_for(node)].append(node)
    if sorted(n for nodes in groups.values() for n in nodes) != sorted(nodeids):
        raise ValueError('non-exhaustive partition')
    return groups


def source_digest(root: Path) -> str:
    """Hash a descriptor-anchored tree; missing, replaced or unreadable input refuses.

    Names are opened relative to verified directory descriptors. Every entry is
    revalidated against its descriptor after use, including directory identity.
    Generated caches are excluded; checks isolate bytecode caches per process.
    """
    digest = hashlib.sha256(); total = 0; count = 0; deadline = time.monotonic() + 30
    ignored = {'.git', '__pycache__', '.pytest_cache'}

    def identity(info):
        return (info.st_dev, info.st_ino, info.st_mode, info.st_size,
                info.st_mtime_ns, info.st_ctime_ns, info.st_nlink)

    def bounded():
        if count > 20000 or time.monotonic() > deadline:
            raise ValueError('source inventory exceeds count or time ceiling')

    def visit(fd, relative, depth):
        nonlocal total, count
        if depth > 64:
            raise ValueError('source inventory exceeds directory depth ceiling')
        initial = os.fstat(fd)
        if not stat.S_ISDIR(initial.st_mode):
            raise ValueError('source directory is not a directory')
        names = []
        # scandir errors propagate; unreadable directories are never omitted.
        with os.scandir(fd) as entries:
            for entry in entries:
                if entry.name in ignored:
                    continue
                count += 1; bounded(); names.append(entry.name)
        digest.update(json.dumps([relative, stat.S_IMODE(initial.st_mode), 'directory']).encode())
        for name in sorted(names):
            bounded()
            before = os.stat(name, dir_fd=fd, follow_symlinks=False)
            mode = before.st_mode
            if not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
                raise ValueError('source member is not a regular file or directory')
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
            if stat.S_ISDIR(mode):
                flags |= os.O_DIRECTORY
            child = os.open(name, flags, dir_fd=fd)
            try:
                if identity(before) != identity(os.fstat(child)):
                    raise ValueError('source pathname changed before opening')
                path = relative + '/' + name if relative else name
                if stat.S_ISDIR(mode):
                    visit(child, path, depth + 1)
                else:
                    total += before.st_size
                    if total > MAX_SOURCE_BYTES:
                        raise ValueError('source inventory exceeds byte ceiling')
                    member = hashlib.sha256(); remaining = before.st_size
                    while remaining:
                        bounded()
                        chunk = os.read(child, min(65536, remaining))
                        if not chunk:
                            raise ValueError('source member changed while reading')
                        member.update(chunk); remaining -= len(chunk)
                    digest.update(json.dumps([path, stat.S_IMODE(mode), member.hexdigest()], separators=(',', ':')).encode())
                if identity(before) != identity(os.fstat(child)):
                    raise ValueError('source descriptor changed while reading')
                if identity(before) != identity(os.stat(name, dir_fd=fd, follow_symlinks=False)):
                    raise ValueError('source pathname changed while reading')
            finally:
                os.close(child)
        if identity(initial) != identity(os.fstat(fd)):
            raise ValueError('source directory changed while reading')

    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        before = os.fstat(root_fd)
        visit(root_fd, '', 0)
        if identity(before) != identity(os.stat(root, follow_symlinks=False)):
            raise ValueError('source root pathname changed while reading')
    finally:
        os.close(root_fd)
    return digest.hexdigest()


class CheckInterrupted(RuntimeError):
    """Do not use InterruptedError: selectors intentionally consumes EINTR."""


def bounded_run(command: list[str], cwd: Path, timeout: float = CHECK_SECONDS,
                env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    """Own one process group; limit wall time/output and reap on every exit path.

    This runner is for trusted repository checks, not hostile code confinement.
    Consumers retain their own OS sandbox. A descendant deliberately escaping
    its session is outside this process-group contract, never claimed reaped.
    """
    if os.name != 'posix' or timeout <= 0 or timeout > CHECK_SECONDS:
        raise ValueError('bounded release checks require POSIX and a valid deadline')
    started = time.monotonic(); output = bytearray(); process = None; failure = None
    old = {}; cache = None
    def interrupted(signum, _frame):
        raise CheckInterrupted(f'check interrupted by signal {signum}')
    try:
        for sig in (signal.SIGTERM, signal.SIGINT):
            old[sig] = signal.signal(sig, interrupted)
        cache = tempfile.TemporaryDirectory(prefix='synthesis-check-cache-')
        child_env = dict(os.environ if env is None else env)
        child_env.pop('PYTEST_ADDOPTS', None)
        child_env.pop('PYTEST_PLUGINS', None)
        child_env.update({'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1',
                          'PYTHONDONTWRITEBYTECODE': '1',
                          'PYTHONPYCACHEPREFIX': str(Path(cache.name)/'pycache')})
        process = subprocess.Popen(command, cwd=cwd, env=child_env, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while selector.get_map():
                remaining = timeout - (time.monotonic()-started)
                if remaining <= 0:
                    raise TimeoutError('required check exceeded its unchanged wall-time ceiling')
                for key, _ in selector.select(min(0.1, remaining)):
                    data = os.read(key.fileobj.fileno(), min(65536, OUTPUT_BYTES-len(output)+1))
                    if not data:
                        selector.unregister(key.fileobj)
                    else:
                        output.extend(data)
                        if len(output) > OUTPUT_BYTES:
                            raise ValueError('required check output exceeded byte ceiling')
            process.wait(timeout=max(0.001, timeout-(time.monotonic()-started)))
    except (OSError, ValueError, TimeoutError, subprocess.TimeoutExpired, KeyboardInterrupt, CheckInterrupted) as error:
        failure = str(error) or type(error).__name__
    finally:
        for sig in old:
            signal.signal(sig, signal.SIG_IGN)
        if process is not None:
            # A successful parent is also responsible for descendants holding no pipe.
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            except OSError as error:
                failure = f'owned process-group cleanup failed: {error}'
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                pass
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except OSError as error:
                failure = f'owned process-group cleanup failed: {error}'
            try:
                process.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired) as error:
                failure = f'owned child reap failed: {error}'
            if process.stdout:
                process.stdout.close()
        if cache is not None:
            try:
                cache.cleanup()
            except OSError as error:
                failure = f'owned bytecode-cache cleanup failed: {error}'
        for sig, handler in old.items():
            signal.signal(sig, handler)
    text = bytes(output[:OUTPUT_BYTES]).decode('utf-8', errors='replace')
    if failure:
        text += '\nFAIL ' + failure + '\n'
    return subprocess.CompletedProcess(command, 1 if failure or process is None else process.returncode, text, '')


class InventoryPlugin:
    def __init__(self, group: str, report: Path):
        self.group = group; self.report = report; self.full = []; self.selected = []
        self.phases = {}; self.errors = []; self.counts = {}

    def pytest_collection_modifyitems(self, session, config, items):
        self.full = [item.nodeid for item in items]
        groups = partition(self.full)
        self.counts = {name: len(nodes) for name, nodes in groups.items()}
        self.selected = groups[self.group]
        if not self.selected:
            raise ValueError('required group collected no tests')
        wanted = set(self.selected)
        deselected = [item for item in items if item.nodeid not in wanted]
        items[:] = [item for item in items if item.nodeid in wanted]
        config.hook.pytest_deselected(items=deselected)

    def pytest_collectreport(self, report):
        if report.failed:
            self.errors.append('collection failed')

    def pytest_runtest_logreport(self, report):
        phases = self.phases.setdefault(report.nodeid, {})
        if report.when in phases:
            self.errors.append('duplicate execution phase')
        phases[report.when] = {'outcome': report.outcome, 'duration': report.duration}

    def pytest_sessionfinish(self, session, exitstatus):
        if set(self.phases) != set(self.selected):
            self.errors.append('execution did not cover exact selected inventory')
        for node, phases in self.phases.items():
            # The one host-specific Darwin control is inapplicable on other OSes.
            host_skip = (sys.platform != 'darwin' and node == AP + '/test_evaluation_artifacts.py::test_mac_worker_cannot_fork_or_spawn_a_process_outside_the_deadline')
            if host_skip and phases.get('setup', {}).get('outcome') == 'skipped':
                continue
            if set(phases) != {'setup', 'call', 'teardown'} or any(p['outcome'] != 'passed' for p in phases.values()):
                self.errors.append('required execution failed or skipped: ' + node)
        payload = {'group': self.group, 'inventory': self.full, 'selected': self.selected,
                   'group_counts': self.counts, 'phases': self.phases, 'errors': self.errors,
                   'exitstatus': int(exitstatus)}
        raw = json.dumps(payload, sort_keys=True).encode()
        if len(raw) > REPORT_BYTES:
            self.errors.append('inventory report exceeds byte ceiling')
        else:
            with self.report.open('xb') as stream:
                stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        if self.errors:
            session.exitstatus = 1


def pytest_configure(config):
    group = os.environ.get('SYNTHESIS_RELEASE_TEST_GROUP')
    if group:
        if group not in GROUPS:
            raise ValueError('unknown release test group')
        config.pluginmanager.register(InventoryPlugin(group, Path(os.environ['SYNTHESIS_RELEASE_TEST_REPORT'])), 'release-inventory')


def run_group(root: Path, group: str) -> tuple[int, dict]:
    deadline = time.monotonic() + CHECK_SECONDS - 5
    before = source_digest(root)
    with tempfile.TemporaryDirectory(prefix='synthesis-release-check-') as temporary:
        temp = Path(temporary); report = temp/'inventory.json'
        env = dict(os.environ)
        # External pytest flags/plugins cannot deselect, repeat or short-circuit a gate.
        env.pop('PYTEST_ADDOPTS', None); env.pop('PYTEST_PLUGINS', None)
        env.update({'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1', 'PYTHONDONTWRITEBYTECODE': '1',
                    'SYNTHESIS_RELEASE_TEST_GROUP': group, 'SYNTHESIS_RELEASE_TEST_REPORT': str(report),
                    'PYTHONPATH': str(Path(__file__).resolve().parent)})
        started = time.monotonic()
        completed = bounded_run([sys.executable, '-m', 'pytest', AP, '-q', '-o', 'addopts=',
                                 '-p', 'no:cacheprovider', '-p', 'release_check_groups',
                                 '--basetemp', str(temp/'pytest'), '--durations=20'], root, min(GROUP_SECONDS, deadline-time.monotonic()-33), env)
        print(completed.stdout, end='')
        if not report.is_file() or report.stat().st_size > REPORT_BYTES:
            return 1, {'group': group, 'error': 'missing or oversized execution inventory'}
        payload = json.loads(report.read_text())
        # Independently validate plugin output rather than trusting its return code alone.
        groups = partition(payload['inventory'])
        if payload['selected'] != groups[group] or payload['errors'] or payload['exitstatus'] != 0:
            return 1, payload
        if before != source_digest(root):
            return 1, {'group': group, 'error': 'source changed during required checks'}
        payload.update({'source_sha256': before, 'seconds': time.monotonic()-started})
        return completed.returncode, payload


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--group', choices=GROUPS, required=True)
    args = parser.parse_args(argv)
    try:
        code, payload = run_group(Path(__file__).resolve().parents[3], args.group)
        print(json.dumps(payload, sort_keys=True))
        return code
    except (OSError, ValueError, KeyError) as error:
        print('FAIL release group: ' + str(error)); return 1


if __name__ == '__main__':
    raise SystemExit(main())

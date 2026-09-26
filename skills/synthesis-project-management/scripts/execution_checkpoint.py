"""Current execution basis for an admitted autopilot run, never project cleanliness.

The whole-project checkpoint owner remains unchanged. This proof permits only
verified projections of the selected journal to advance while closure is being
recorded. All other files, including other runs and immutable inputs, stay bound.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import time

import project_state
from run_admission import admit_paths, read_admission_observation, safe_path

SCOPE = 'EXECUTION_BASIS'
MAX_FILE_BYTES = 16 * 1024 * 1024
CHUNK_BYTES = 1024 * 1024
# Per-operation resource bounds, independent of any individual evidence file.
# Both metadata passes count; binary contents are streamed once. These are
# processing limits, never permission to omit a file or accept partial proof.
MAX_SCAN_ENTRIES = 250000
MAX_SCAN_BYTES = 16 * 1024 * 1024 * 1024
MAX_SCAN_SECONDS = 120.0
MAX_SCAN_DEPTH = 128


class _ScanBudget:
    def __init__(self):
        self.deadline = time.monotonic() + MAX_SCAN_SECONDS
        self.entries = self.bytes = 0

    def check(self, *, entries=0, size=0):
        self.entries += entries
        self.bytes += size
        if (self.entries > MAX_SCAN_ENTRIES or self.bytes > MAX_SCAN_BYTES
                or time.monotonic() > self.deadline):
            raise ValueError('execution inventory resource/time budget exhausted; no partial proof')


def _signature(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _commit(hasher, value):
    raw = json.dumps(value, ensure_ascii=True, separators=(',', ':')).encode()
    hasher.update(len(raw).to_bytes(8, 'big'))
    hasher.update(raw)


def _walk(project, budget, *, metadata):
    """Descriptor-anchored deterministic walk with bounded directory buffers."""
    if any(path.is_symlink() for path in [project, *project.parents]):
        raise ValueError('execution project crosses a symlink')
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK

    def visit(fd, relative, expected, depth):
        if depth > MAX_SCAN_DEPTH:
            raise ValueError('execution inventory directory depth budget exhausted')
        before = os.fstat(fd)
        if _signature(before) != _signature(expected):
            raise ValueError('execution directory changed before observation')
        _commit(metadata, [relative, _signature(before)])
        names = []
        with os.scandir(fd) as entries:
            for entry in entries:
                budget.check(entries=1)
                names.append(entry.name)
        for name in sorted(names):
            budget.check()
            child = str(Path(relative) / name) if relative else name
            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if stat.S_ISDIR(info.st_mode):
                nested = os.open(name, flags, dir_fd=fd)
                try:
                    yield from visit(nested, child, info, depth + 1)
                    if _signature(os.stat(name, dir_fd=fd, follow_symlinks=False)) != _signature(info):
                        raise ValueError('execution directory replaced during observation')
                finally:
                    os.close(nested)
            elif stat.S_ISREG(info.st_mode):
                _commit(metadata, [child, _signature(info)])
                yield child, info, fd, name
            else:
                raise ValueError('execution inventory requires regular files and directories: ' + child)
        if _signature(os.fstat(fd)) != _signature(before):
            raise ValueError('execution directory changed during observation')

    initial = project.lstat()
    fd = os.open(project, flags)
    try:
        yield from visit(fd, '', initial, 0)
        if (any(path.is_symlink() for path in [project, *project.parents])
                or _signature(project.lstat()) != _signature(initial)):
            raise ValueError('execution project replaced during observation')
    finally:
        os.close(fd)


def _stream_digest(directory_fd, name, expected, budget):
    """Hash every byte with bounded memory and exact inode/change checks."""
    budget.check(size=expected.st_size)
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or _signature(before) != _signature(expected):
            raise ValueError('execution evidence changed before hashing')
        digest, remaining = hashlib.sha256(), before.st_size
        while remaining:
            budget.check()
            raw = stream.read(min(CHUNK_BYTES, remaining))
            if not raw:
                raise ValueError('execution evidence was truncated during hashing')
            digest.update(raw)
            remaining -= len(raw)
        if stream.read(1):
            raise ValueError('execution evidence grew during hashing')
        after = os.fstat(stream.fileno())
    named = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    if _signature(before) != _signature(after) or _signature(after) != _signature(named):
        raise ValueError('execution evidence changed during hashing')
    budget.check()
    return digest.hexdigest()


def _hash(raw):
    return hashlib.sha256(raw).hexdigest()


def _read(path):
    """One bounded regular inode; symlinks and concurrent replacement refuse."""
    if any(parent.is_symlink() for parent in [path, *path.parents]):
        raise ValueError('execution basis crosses a symlink')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_FILE_BYTES:
            raise ValueError('execution basis requires bounded regular files')
        # The inode size is already bounded. Retain one growth sentinel byte
        # without allocating the global 16 MiB ceiling for every small file.
        raw = stream.read(before.st_size + 1)
        after = os.fstat(stream.fileno())
    named = path.lstat()
    signature = lambda value: (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)
    if signature(before) != signature(after) or signature(after) != signature(named):
        raise ValueError('execution basis file changed while reading')
    return raw


def _proof(context):
    if 'admission_observation' in context:
        proof = read_admission_observation(context)
    else:
        state, actor = context['state'], context['actor']
        proof = admit_paths(Path(actor['board']), state['project_id'], Path(context['project']),
            [Path(context['project'])], actor['native_payload'],
            expected_claim_hash=context['binding']['claim_hash'], readonly=True)
    if any(proof.get(key) != context['binding'].get(key) for key in ('session_uuid', 'native_ref', 'project_id', 'project_root', 'repository', 'branch', 'claim_hash')):
        raise ValueError('execution basis admission changed')
    return {key: proof[key] for key in ('session_uuid', 'native_ref', 'project_id',
        'project_root', 'repository', 'branch', 'claim_hash')}


def _summary(state):
    result = f"Run: {state['run_id']}\nRevision: {state['revision']}\nStatus: {state['status']}\n"
    result += f"Contract: {state['contract_revision']} ({state['contract_digest']})\n"
    result += f"Profile: {state['profile_revision']} ({state['profile_digest']})\n"
    if state.get('progress'):
        result += 'Progress: ' + state['progress']['summary'].replace('\n', ' ') + '\n'
    return result


def _snapshot_derivation(run_state, path, value):
    """Derive exact owned bytes without rewriting historical inline snapshots."""
    rendered = run_state._retained_snapshot_bytes(path, value)
    if path.parent.name == 'events' and len(rendered) > 1:
        # The append owner also installs this revision's projection blocks
        # before committing. Retain their derivation after current.json moves.
        projection = path.parent.parent / 'current.json'
        rendered.update({item: content for item, content in
            run_state._snapshot_bytes(projection, value['state']).items()
            if item != projection})
    return {str(item): _hash(content) for item, content in rendered.items()}


def _inventory(context):
    import run_state
    budget = _ScanBudget()
    state, project = context['state'], Path(context['project'])
    home = run_state._home(project, state['run_id'])
    events, derived = [], {}
    last = None
    for last in run_state._events(project, state['run_id']):
        budget.check()
        events.append({key: last[key] for key in ('revision', 'digest', 'actor')})
        path = str(home / 'events' / f"{last['revision']:012d}.json")
        derived.update(_snapshot_derivation(run_state, Path(path), last))
    if last is None or last['state'] != state:
        raise ValueError('execution basis needs the current selected journal')
    derived.update(_snapshot_derivation(run_state, home / 'current.json', state))
    derived[str(home / 'summary.md')] = _hash(('# Autopilot run\n\n' + _summary(state)).encode())
    if state['status'] in run_state.TERMINAL:
        derived[str(home / 'terminal.json')] = _hash(run_state._json({'schema_version': run_state.SCHEMA,
            'run_id': state['run_id'], 'revision': state['revision'], 'status': state['status'],
            'terminal': state['terminal']}) + b'\n')
    plan = run_state._plan(project, state['plan']).resolved
    start, end = (f"<!-- autopilot:{state['run_id']}:{edge} -->" for edge in ('start', 'end'))
    plan_raw = _read(plan)
    plan_text = plan_raw.decode('utf-8')
    if plan_text.count(start) != 1 or plan_text.count(end) != 1:
        raise ValueError('selected run plan projection is missing or ambiguous')
    block = start + '\n' + _summary(state) + end
    if plan_text[plan_text.index(start):plan_text.index(end) + len(end)] != block:
        raise ValueError('selected run plan projection disagrees with its journal')
    human_plan = plan_text.replace(block, start + '\n' + end)
    inputs = {}
    for record in state['artifacts'].values():
        if record.get('managed_input'):
            path = safe_path(project / record['path'], project)
            if path != home / 'inputs' / (record['digest'] + '.json'):
                raise ValueError('immutable input is not in its digest-addressed location')
            raw = _read(path)
            if _hash(raw) != record['digest']:
                raise ValueError('immutable execution input changed')
            inputs[str(path.relative_to(project))] = _hash(raw)
    records = {}
    body = hashlib.sha256(b'synthesis-execution-files-v2\0')
    file_count = byte_count = 0
    seen_derived = set()
    metadata = hashlib.sha256()
    for relative, info, fd, name in _walk(project, budget, metadata=metadata):
        path = project / relative
        digest = _stream_digest(fd, name, info, budget)
        if str(path) in derived:
            if digest != derived[str(path)]:
                raise ValueError('run projection or journal bytes are not their exact derivation')
            seen_derived.add(str(path))
            continue
        if relative in inputs:
            if digest != inputs[relative]:
                raise ValueError('immutable input changed during inventory')
            continue
        size = info.st_size
        if path == plan:
            if digest != _hash(plan_raw):
                raise ValueError('execution plan changed during inventory')
            normalized = human_plan.encode()
            digest, size = _hash(normalized), len(normalized)
        if relative in ('CONTEXT.md', project_state.STATE_FILE):
            records[relative] = digest
        if relative != project_state.STATE_FILE:
            _commit(body, [relative, digest, size])
            file_count += 1
            byte_count += size
    if seen_derived != set(derived):
        raise ValueError('selected journal projection is missing')
    # Revisit every member and inode after hashing. This detects late writes to
    # an earlier file and added/removed/replaced members, not just read races.
    final_metadata = hashlib.sha256()
    for _ in _walk(project, budget, metadata=final_metadata):
        pass
    if final_metadata.digest() != metadata.digest():
        raise ValueError('execution inventory changed during its complete observation')
    files = _file_commitment({'sha256': body.hexdigest(), 'files': file_count, 'bytes': byte_count}, records)
    return files, inputs, events


def _file_commitment(body, records):
    value = {'schema_version': 2, 'algorithm': 'sha256-framed-dfs-v1',
             'body': body, 'records': records}
    return {**value, 'sha256': _hash(json.dumps(value, sort_keys=True, separators=(',', ':')).encode())}


def _validate_file_commitment(value):
    if not isinstance(value, dict) or set(value) != {'schema_version', 'algorithm', 'body', 'records', 'sha256'}:
        raise ValueError('execution file commitment is malformed')
    body, records = value['body'], value['records']
    if (not isinstance(body, dict) or set(body) != {'sha256', 'files', 'bytes'}
            or any(type(body[key]) is not int or body[key] < 0 for key in ('files', 'bytes'))
            or not isinstance(records, dict) or set(records) != {'CONTEXT.md', project_state.STATE_FILE}):
        raise ValueError('execution file commitment fields are malformed')
    if any(not isinstance(item, str) or len(item) != 64 or any(c not in '0123456789abcdef' for c in item)
            for item in [body['sha256'], *records.values()]):
        raise ValueError('execution file commitment digest is malformed')
    if _file_commitment(body, records) != value:
        raise ValueError('execution file commitment does not authenticate its members')


def _without_pm_state(value):
    _validate_file_commitment(value)
    return {'body': value['body'], 'context': value['records']['CONTEXT.md']}


def _current(context):
    state, project = context['state'], Path(context['project'])
    proof = _proof(context)
    _read(project / project_state.STATE_FILE)
    if project_state.checkpoint_applicability(project)[0] != 'REQUIRED':
        raise ValueError('execution basis requires adopted structured PM state')
    adopted = project_state._load_json(project / project_state.STATE_FILE)
    if adopted.get('session_id') != proof['session_uuid'] or adopted.get('project_id') != state['project_id']:
        raise ValueError('structured PM state belongs to another native owner')
    if project_state._live_source_heads(adopted) != adopted.get('source_heads', {}):
        raise ValueError('current source heads changed after PM build')
    repo, relative, head, tree = project_state._git_identity(project)
    if any(adopted.get(key) != value for key, value in {'repository': str(repo),
            'project_path': relative, 'git_head': head, 'project_tree': tree}.items()):
        raise ValueError('current PM Git identity differs from its builder')
    if project_state._required_plan(project, adopted['controlling_plan']).resolved != project_state._required_plan(project, state['plan']).resolved:
        raise ValueError('PM and execution controlling plans differ')
    context_text = _read(project / 'CONTEXT.md').decode('utf-8')
    expected = project_state.render_context_current_state(project, adopted)
    if context_text.count('<!-- synthesis-current-state:start -->') != 1 or context_text.count('<!-- synthesis-current-state:end -->') != 1 or expected not in context_text:
        raise ValueError('compiled PM context does not derive from its structured owner')
    files, inputs, events = _inventory(context)
    return {'schema_version': 2, 'scope': SCOPE, 'authority_granted': False,
        'bindings': {key: state[key] for key in ('run_id', 'contract_digest', 'profile_digest')},
        'owner': proof, 'project_files': files, 'immutable_inputs': inputs,
        'journal_head': {'revision': events[-1]['revision'], 'digest': events[-1]['digest']},
        'pm_state': adopted}, events


def observe_execution_basis(context):
    """Capture after the PM builder, inside the admitted checkpoint operation."""
    try:
        value, _events = _current(context)
        issues = project_state.semantic_issues(Path(context['project']))
    except (project_state.ProjectStateError, subprocess.SubprocessError) as exc:
        raise ValueError(str(exc)) from exc
    if issues:
        raise ValueError('PM state was not current at execution capture: ' + '; '.join(issues))
    return value


def validate_execution_basis(context, receipt):
    """Verify current bytes and journal descent, including an explicit successor."""
    try:
        if not isinstance(receipt, dict) or receipt.get('scope') != SCOPE or receipt.get('schema_version') != 2 or receipt.get('authority_granted') is not False:
            raise ValueError('invalid execution basis scope')
        current, events = _current(context)
        for key in ('bindings', 'owner'):
            if current[key] != receipt.get(key):
                raise ValueError('execution basis owner or immutable binding changed')
        head = receipt.get('journal_head', {})
        revision = head.get('revision')
        if type(revision) is not int or not 0 < revision <= len(events) or events[revision - 1]['digest'] != head.get('digest'):
            raise ValueError('execution journal no longer descends from the captured head')
        for event in events[revision:]:
            if event['actor'] != {key: current['owner'][key] for key in ('session_uuid', 'native_ref', 'claim_hash')}:
                raise ValueError('execution journal contains a foreign successor')
        if any(current['immutable_inputs'].get(path) != digest for path, digest in receipt.get('immutable_inputs', {}).items()):
            raise ValueError('captured immutable execution inputs changed')
        original_files, current_files = receipt.get('project_files'), current['project_files']
        _validate_file_commitment(original_files)
        if current_files != original_files:
            # A final ordinary PM checkpoint may succeed after the terminal
            # journal append. Only that owner can attest this explicit successor.
            state, project = context['state'], Path(context['project'])
            intent = state.get('extensions', {}).get('controller', {}).get('closure_intent', {})
            root = Path(intent.get('receipt_root', ''))
            if state['status'] != 'completed' or not root.is_absolute() or root.is_relative_to(project) or any(path.is_symlink() for path in [root, *root.parents]):
                raise ValueError('execution project bytes changed without a terminal PM successor')
            unchanged = lambda value: {key: val for key, val in value.items() if key not in {'content_hashes', 'updated_at'}}
            if unchanged(current['pm_state']) != unchanged(receipt.get('pm_state', {})):
                raise ValueError('terminal PM successor changed operational facts')
            if _without_pm_state(current_files) != _without_pm_state(original_files):
                raise ValueError('terminal PM successor changed nonderived project bytes')
            status, issues = project_state.validate_checkpoint(project, session_id=current['owner']['session_uuid'],
                coordination_board=Path(context['actor']['board']), receipt_root=root,
                source_heads=current['pm_state']['source_heads'])
            if status != 'PASS' or project_state.semantic_issues(project):
                raise ValueError('terminal whole-project checkpoint is missing or stale: ' + '; '.join(issues))
        return SCOPE, []
    except (ValueError, OSError, KeyError, TypeError, project_state.ProjectStateError, subprocess.SubprocessError) as exc:
        return 'FAIL', [str(exc)]


def current_proof(context, receipt):
    """Name the proof that is current; historical execution bytes are not clean."""
    status, issues = validate_execution_basis(context, receipt)
    if status != SCOPE:
        return {'scope': 'UNRESOLVED', 'issues': issues, 'authority_granted': False}
    current, _events = _current(context)
    result = {'scope': SCOPE, 'bindings': current['bindings'], 'journal_head': current['journal_head'],
              'authority_granted': False, 'issues': []}
    if current['project_files'] != receipt['project_files']:
        root = Path(context['state']['extensions']['controller']['closure_intent']['receipt_root'])
        path = project_state._receipt_path(root, current['owner']['session_uuid'], current['owner']['project_id'])
        result.update(scope='TERMINAL_CLEAN_CHECKPOINT_SUCCESSOR', receipt_path=str(path),
                      receipt_digest=_hash(_read(path)))
    return result

"""Current execution basis for an admitted autopilot run, never project cleanliness.

The whole-project checkpoint owner remains unchanged. This proof permits only
verified projections of the selected journal to advance while closure is being
recorded. All other files, including other runs and immutable inputs, stay bound.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import stat
import subprocess

import project_state
from run_admission import admit_paths, read_admission_observation, safe_path

SCOPE = 'EXECUTION_BASIS'
MAX_FILES = 20000
MAX_FILE_BYTES = 16 * 1024 * 1024


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


def _inventory(context):
    import run_state
    state, project = context['state'], Path(context['project'])
    home = run_state._home(project, state['run_id'])
    events, derived = [], {}
    last = None
    for last in run_state._events(project, state['run_id']):
        events.append({key: last[key] for key in ('revision', 'digest', 'actor')})
        path = str(home / 'events' / f"{last['revision']:012d}.json")
        derived[path] = _hash(run_state._json(last) + b'\n')
    if last is None or last['state'] != state:
        raise ValueError('execution basis needs the current selected journal')
    derived.update({str(home / 'current.json'): _hash(run_state._json(state) + b'\n'),
        str(home / 'summary.md'): _hash(('# Autopilot run\n\n' + _summary(state)).encode())})
    if state['status'] in run_state.TERMINAL:
        derived[str(home / 'terminal.json')] = _hash(run_state._json({'schema_version': run_state.SCHEMA,
            'run_id': state['run_id'], 'revision': state['revision'], 'status': state['status'],
            'terminal': state['terminal']}) + b'\n')
    plan = run_state._plan(project, state['plan']).resolved
    start, end = (f"<!-- autopilot:{state['run_id']}:{edge} -->" for edge in ('start', 'end'))
    plan_text = _read(plan).decode('utf-8')
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
    files = {}
    pending = [project]
    seen_derived = set()
    count = 0
    while pending:
        directory = pending.pop()
        if directory.is_symlink():
            raise ValueError('execution project contains a symlink directory')
        for path in sorted(directory.iterdir()):
            count += 1
            if count > MAX_FILES or path.is_symlink():
                raise ValueError('execution project exceeds its bound or contains a symlink')
            if path.is_dir():
                pending.append(path)
                continue
            raw = _read(path)
            relative = str(path.relative_to(project))
            if str(path) in derived:
                if _hash(raw) != derived[str(path)]:
                    raise ValueError('run projection or journal bytes are not their exact derivation')
                seen_derived.add(str(path))
            elif relative in inputs:
                if _hash(raw) != inputs[relative]:
                    raise ValueError('immutable input changed during inventory')
            elif path == plan:
                files[relative] = _hash(human_plan.encode())
            else:
                files[relative] = _hash(raw)
    if seen_derived != set(derived):
        raise ValueError('selected journal projection is missing')
    return files, inputs, events


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
    return {'schema_version': 1, 'scope': SCOPE, 'authority_granted': False,
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
        if not isinstance(receipt, dict) or receipt.get('scope') != SCOPE or receipt.get('schema_version') != 1 or receipt.get('authority_granted') is not False:
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
        if not isinstance(original_files, dict):
            raise ValueError('execution basis file inventory is missing')
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
            if {key: val for key, val in current_files.items() if key != project_state.STATE_FILE} != {key: val for key, val in original_files.items() if key != project_state.STATE_FILE}:
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

"""Operator projection: real admitted journals; native identity is a declared fixture."""
from __future__ import annotations
import importlib
import json
from pathlib import Path
import sys
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "synthesis-project-management/scripts"))
from test_run_state import engine, world, create, command


def test_hidden_question_is_available_from_actual_owner_journal_without_actor(engine, world):
    state = create(engine, world)
    state = command(engine, world, state, "wait.add", {"id":"choice", "kind":"user", "reason":"Choose <one> & preserve scope"})
    before = sorted((str(p), p.read_bytes()) for p in world["project"].rglob("*") if p.is_file())
    module = importlib.import_module("operator_status")
    result = module.inspect_project(world["project"], state["run_id"])
    row = result["runs"][0]
    assert row["status"] == "waiting"
    assert row["questions"][0]["reason"] == "Choose <one> & preserve scope"
    assert row["current_acceptance"] == "UNKNOWN"
    assert row["native_liveness"] == "UNKNOWN"
    assert row["authority_granted"] is False
    assert before == sorted((str(p), p.read_bytes()) for p in world["project"].rglob("*") if p.is_file())


def inspect(world, state):
    return importlib.import_module("operator_status").inspect_project(world["project"], state["run_id"])["runs"][0]


def test_empty_project_has_no_invented_run(world):
    result = importlib.import_module("operator_status").inspect_project(world["project"])
    assert result["runs"] == [] and result["authority_granted"] is False


def test_recorded_work_is_not_live_work_or_measured_progress(engine, world):
    state = create(engine, world)
    state = command(engine, world, state, "progress", {"summary": "Still thinking"})
    row = inspect(world, state)
    assert row["status"] == "working"
    assert row["last_note"]["summary"] == "Still thinking"
    assert row["last_useful_progress"] is None and row["billing"] == "UNKNOWN"
    assert row["loaded_in_native_session"] == "UNKNOWN"


def test_cancelled_is_distinct_and_does_not_claim_success(engine, world):
    state = create(engine, world)
    state = command(engine, world, state, "close", {"status": "cancelled", "reason": "Operator cancelled"})
    row = inspect(world, state)
    assert row["status"] == "cancelled" and row["current_acceptance"] == "UNKNOWN"


@pytest.mark.parametrize("projection", ["missing", "stale", "invalid", "symlink"])
def test_projections_never_override_journal(engine, world, projection):
    state = create(engine, world)
    state = command(engine, world, state, "wait.add", {"id": "q", "kind": "user", "reason": "Keep me visible"})
    path = engine._home(world["project"], state["run_id"]) / "current.json"
    path.unlink()
    if projection == "stale": path.write_text(json.dumps({**state, "status": "completed"}))
    elif projection == "invalid": path.write_text("not json")
    elif projection == "symlink": path.symlink_to(world["plan"])
    row = inspect(world, state)
    assert row["status"] == "waiting" and row["questions"][0]["id"] == "q"
    assert row["diagnostics"] and row["currentness"] == "JOURNAL_VERIFIED_RECORDED_STATE"


@pytest.mark.parametrize("fault", ["chain", "gap", "link", "directory", "oversize", "foreign"])
def test_unsafe_or_foreign_journal_is_unhealthy(engine, world, fault):
    state = create(engine, world)
    event = engine._home(world["project"], state["run_id"]) / "events/000000000001.json"
    if fault == "chain":
        data = json.loads(event.read_text()); data["state"]["status"] = "completed"; event.write_text(json.dumps(data))
    elif fault == "gap": event.rename(event.with_name("000000000002.json"))
    elif fault == "link": event.unlink(); event.symlink_to(world["plan"])
    elif fault == "directory": event.unlink(); event.mkdir()
    elif fault == "oversize": event.write_bytes(b" " * (engine.MAX_JSON_BYTES + 1))
    else:
        data = json.loads(event.read_text()); data["state"]["owner"]["project_root"] = str(world["scratch"])
        data["digest"] = engine._digest({key: value for key, value in data.items() if key != "digest"})
        event.write_text(json.dumps(data))
    row = inspect(world, state)
    assert row["status"] == "unhealthy" and row["currentness"] == "UNVERIFIABLE"
    assert row["questions"] == [] and row["authority_granted"] is False


def test_journal_time_bound_is_explicit_not_empty_success(engine, world, monkeypatch):
    state = create(engine, world)
    module = importlib.import_module("operator_status")
    monkeypatch.setattr(module, "MAX_JOURNAL_SECONDS", 0)
    assert inspect(world, state)["status"] == "unhealthy"


def test_run_inventory_bound_and_project_redirect_refused(engine, world, monkeypatch):
    state = create(engine, world)
    module = importlib.import_module("operator_status")
    monkeypatch.setattr(module, "MAX_DISCOVERY_ENTRIES", 1)
    (engine._home(world["project"], state["run_id"]).parent / "01990000-0000-7000-8000-000000000055").mkdir()
    with pytest.raises(ValueError, match="entry bound"): module.inspect_project(world["project"])
    alias = world["scratch"] / "alias"; alias.symlink_to(world["project"], target_is_directory=True)
    with pytest.raises(ValueError, match="symbolic"): module.inspect_project(alias, state["run_id"])


def test_fresh_request_reads_new_revision_and_never_acknowledges(engine, world):
    first = create(engine, world)
    before = inspect(world, first)
    state = command(engine, world, first, "wait.add", {"id": "q", "kind": "user", "reason": "Approval needed"})
    after = inspect(world, state)
    assert after["revision"] > before["revision"] and after["journal_head"] != before["journal_head"]
    assert engine.load_run(world["project"], state["run_id"])["waits"]["q"]["status"] == "pending"


def test_subprocess_cli_is_real_read_only_owner_reader(engine, world):
    import subprocess
    state = create(engine, world)
    script = Path(__file__).with_name("operator_status.py")
    before = engine.load_run(world["project"], state["run_id"])
    child = subprocess.run([sys.executable, "-I", "-B", str(script), "--project", str(world["project"]), "--run-id", state["run_id"]], capture_output=True, text=True, timeout=8)
    assert child.returncode == 0, child.stderr
    data = json.loads(child.stdout)
    assert data["runs"][0]["revision"] == state["revision"]
    assert data["helper"]["loaded_in_native_session"] == "UNKNOWN"
    assert engine.load_run(world["project"], state["run_id"]) == before

from test_controller import facade, invoke, start_request, request, state_of, prepared_consumer


def test_plain_language_delegation_real_default_controller_outcome_is_recorded(facade, world):
    # The native agent's intent-to-contract judgment is synthetic here; the
    # admission, default profile, sandboxed consumer and completion are real.
    state, _ = prepared_consumer(facade, world)
    result = invoke(facade, world, request('finish', {'disposition': 'completed'}, state))
    assert result['status'] == 'COMPLETED', result
    row = inspect(world, state)
    assert row['status'] == 'completed'
    assert row['current_acceptance'] == 'UNKNOWN'  # Console did not re-admit a native actor.
    assert row['tasks'][0]['status'] == 'done'


def test_exact_prepared_cancellation_owner_cas_replay_and_no_actor_refusal(facade, world):
    response = invoke(facade, world, start_request(world))
    state = state_of(world, response)
    prepared = {'schema_version': 1, 'request_id': '01990000-0000-7000-8000-000000000044',
                'operation': 'cancel', 'project_id': 'alpha', 'run_id': state['run_id'],
                'expected_revision': state['revision'],
                'input': {'reason': 'User requested cancellation from the Console handoff.', 'target': 'run'}}
    denied = facade.handle(prepared, project=world['project'])
    assert denied['status'] == 'UNRESOLVED'
    assert state_of(world, response) == state
    stale = dict(prepared, expected_revision=state['revision'] - 1)
    assert invoke(facade, world, stale)['status'] == 'UNRESOLVED'
    result = invoke(facade, world, prepared)
    assert result['status'] == 'CANCELLED', result
    terminal = state_of(world, result)
    assert invoke(facade, world, prepared)['revision'] == terminal['revision']
    assert inspect(world, terminal)['status'] == 'cancelled'


def test_discovery_does_not_mislabel_existing_owner_plan_lock(engine, world):
    state = create(engine, world)
    result = importlib.import_module("operator_status").inspect_project(world["project"])
    assert [row["run_id"] for row in result["runs"]] == [state["run_id"]]
    assert result["runs"][0]["status"] == "working"


def test_ignored_temporary_inventory_is_still_bounded(engine, world, monkeypatch):
    state = create(engine, world)
    module = importlib.import_module("operator_status")
    monkeypatch.setattr(module, "MAX_DISCOVERY_ENTRIES", 16)
    home = engine._home(world["project"], state["run_id"]).parent
    for number in range(module.MAX_DISCOVERY_ENTRIES):
        (home / (".run-unused-" + str(number))).write_text("")
    with pytest.raises(ValueError, match="entry bound"):
        module.inspect_project(world["project"])
    assert module.inspect_project(world["project"], state["run_id"])["runs"][0]["status"] == "working"


def test_retained_history_pages_without_losing_latest_question(engine, world):
    module = importlib.import_module('operator_status')
    ids = []
    for number in range(35):
        state = create(engine, world, command_id='history-' + str(number))
        ids.append(state['run_id'])
        if number < 34:
            command(engine, world, state, 'close', {'status': 'cancelled', 'reason': 'Retained fixture history'})
    state = command(engine, world, state, 'wait.add', {'id': 'latest', 'kind': 'user', 'reason': 'Latest retained question'})
    before = {str(p): p.read_bytes() for p in world['project'].rglob('*') if p.is_file()}
    page = module.inspect_project(world['project'])
    assert page['runs'][0]['run_id'] == state['run_id']
    assert page['runs'][0]['questions'][0]['reason'] == 'Latest retained question'
    seen = [r['run_id'] for r in page['runs']]
    while page['pagination']['next_cursor']:
        page = module.inspect_project(world['project'], cursor=page['pagination']['next_cursor'])
        seen.extend(r['run_id'] for r in page['runs'])
    assert len(seen) == len(set(seen)) == 35 and set(seen) == set(ids)
    assert before == {str(p): p.read_bytes() for p in world['project'].rglob('*') if p.is_file()}


def causal_world(engine, world):
    from test_run_admission import git, write_board
    import project_state
    canonical = world['project']
    index = world['repo'] / 'projects/index.yaml'
    newer = world['scratch'] / 'newer-owned'
    git(world['repo'], 'worktree', 'add', '-b', 'fixture/newer', str(newer))
    world['repo'] = newer
    world['project'] = newer / 'projects/alpha'
    world['plan'] = world['project'] / 'plan.md'
    world['actor']['native_payload']['cwd'] = str(newer)
    write_board(world, workspace=str(newer) + ' @ fixture/newer')
    context = world['project'] / 'CONTEXT.md'
    context.write_text(context.read_text() + '\nNewer owned worktree context.\n')
    git(newer, 'add', 'projects')
    git(newer, 'commit', '-m', 'Fixture causal successor')
    state = create(engine, world)
    state = command(engine, world, state, 'wait.add', {'id': 'owned-question', 'kind': 'user', 'reason': 'Only visible in the newer owned worktree'})
    pending = world['scratch'] / 'owner-state/repo-guard/pending'
    pending.mkdir(parents=True)
    dirty = project_state._dirty_project_files(newer, 'projects/alpha')
    (pending / 'owned.json').write_text(json.dumps({'schema_version': 2, 'session_id': state['owner']['session_uuid'],
        'paths': [row['path'] for row in dirty], 'path_hashes': {row['path']: row['sha256'] for row in dirty}}))
    foreign = pending / 'foreign.json'
    foreign.write_text(json.dumps({'schema_version': 2, 'session_id': 'foreign', 'paths': ['/fixture/foreign']}))
    return index, canonical, state, pending.parent, foreign


def test_registry_selects_actual_newer_owned_worktree_without_mutation(engine, world):
    index, canonical, state, guard, foreign = causal_world(engine, world)
    module = importlib.import_module('operator_status')
    before = {str(p): p.read_bytes() for root in (canonical, world['project'], guard, world['board'].parent)
              for p in root.rglob('*') if p.is_file()}
    result = module.inspect_registry(index, 'alpha', repo_guard_root=guard, coordination_board=world['board'])
    assert result['project'] == str(world['project'])
    assert result['resolution']['status'] == 'LOCAL_RECOVERABLE'
    assert result['runs'][0]['run_id'] == state['run_id']
    assert result['runs'][0]['questions'][0]['id'] == 'owned-question'
    assert result['authority_granted'] is False
    assert before == {str(p): p.read_bytes() for root in (canonical, world['project'], guard, world['board'].parent)
                      for p in root.rglob('*') if p.is_file()}


def test_registry_conflict_returns_no_stale_canonical_run(engine, world):
    index, canonical, state, guard, foreign = causal_world(engine, world)
    (canonical / 'CONTEXT.md').write_text('Unattributed conflicting local edits\n')
    module = importlib.import_module('operator_status')
    result = module.inspect_registry(index, 'alpha', repo_guard_root=guard, coordination_board=world['board'])
    assert result['resolution']['status'] == 'CONFLICT'
    assert result['project'] is None and result['runs'] == []
    assert result['authority_granted'] is False
    assert foreign.exists()


@pytest.mark.parametrize('cursor', ['bad', 'e30=', '../../outside', 'x' * 513])
def test_malformed_page_cursor_refused(engine, world, cursor):
    create(engine, world)
    with pytest.raises(ValueError, match='cursor'):
        importlib.import_module('operator_status').inspect_project(world['project'], cursor=cursor)


def test_page_cursor_is_bound_to_project_inventory_and_page_size(engine, world):
    module = importlib.import_module('operator_status')
    first = create(engine, world)
    command(engine, world, first, 'close', {'status': 'cancelled', 'reason': 'Retain first'})
    second = create(engine, world, command_id='second')
    page = module.inspect_project(world['project'], limit=1)
    token = page['pagination']['next_cursor']
    assert token
    with pytest.raises(ValueError, match='cursor'):
        module.inspect_project(world['project'], limit=2, cursor=token)
    command(engine, world, second, 'wait.add', {'id': 'q', 'kind': 'user', 'reason': 'New question'})
    with pytest.raises(ValueError, match='refresh'):
        module.inspect_project(world['project'], limit=1, cursor=token)
    assert module.inspect_project(world['project'], second['run_id'])['runs'][0]['questions'][0]['id'] == 'q'


def test_resolution_never_fetches_refreshes_or_fast_forwards(engine, world, monkeypatch):
    index, canonical, state, guard, foreign = causal_world(engine, world)
    import project_state
    original = project_state.resolve_project
    seen = []
    def checked(*args, **kwargs):
        assert kwargs['fetch'] is False
        assert kwargs['fast_forward_canonical'] is False
        assert kwargs['refresh_coordination'] is False
        seen.append(kwargs)
        return original(*args, **kwargs)
    monkeypatch.setattr(project_state, 'resolve_project', checked)
    result = importlib.import_module('operator_status').inspect_registry(index, 'alpha', repo_guard_root=guard,
        coordination_board=world['board'])
    assert result['resolution']['status'] == 'LOCAL_RECOVERABLE' and len(seen) == 1


def test_registry_redirect_and_unknown_project_refused(engine, world):
    module = importlib.import_module('operator_status')
    index = world['repo'] / 'projects/index.yaml'
    alias = world['scratch'] / 'alias.yaml'
    alias.symlink_to(index)
    with pytest.raises(ValueError, match='unsafe'):
        module.inspect_registry(alias, 'alpha')
    result = module.inspect_registry(index, 'foreign', repo_guard_root=world['scratch'] / 'absent')
    assert result['resolution']['status'] == 'UNKNOWN' and result['runs'] == []


def test_causal_selection_cannot_resolve_a_tracked_project_symlink_to_foreign_content(world):
    from test_run_admission import git
    newer = world['scratch'] / 'redirect-worktree'
    git(world['repo'], 'worktree', 'add', '-b', 'fixture/redirect', str(newer))
    project = newer / 'projects/alpha'
    outside = world['scratch'] / 'foreign-project'
    project.rename(outside)
    project.symlink_to(outside, target_is_directory=True)
    git(newer, 'add', 'projects')
    git(newer, 'commit', '-m', 'Fixture tracked project redirect')
    before = {str(p): p.read_bytes() for p in outside.rglob('*') if p.is_file()}
    with pytest.raises(ValueError, match='physical project'):
        importlib.import_module('operator_status').inspect_registry(world['repo'] / 'projects/index.yaml', 'alpha',
            repo_guard_root=world['scratch'] / 'absent', checkpoint_receipt_root=world['scratch'] / 'absent-receipts')
    assert before == {str(p): p.read_bytes() for p in outside.rglob('*') if p.is_file()}


# Real owner commands/journal readers; native session identity is synthetic.
def _record_task_progress(runtime, world, state, task_id, number):
    from test_workflow import _owner_register
    state = _owner_register(runtime, world, state, 'output', {'generation': number}, role='output')
    spec_id = 'progress-' + task_id
    if spec_id not in state['artifacts']:
        state = _owner_register(runtime, world, state, spec_id, {'schema_version': 1,
            'kind': 'progress_observation', 'arguments': {'task_id': task_id}})
    observation_id = 'observed-' + task_id + '-' + str(number)
    state = runtime.observe(world['project'], state['run_id'], 'progress_observation', {'check_id': spec_id},
        expected_revision=state['revision'], command_id=observation_id, actor=world['actor'], runtime_root=world['runtime'])
    return command(runtime, world, state, 'workflow.attempt', {'task_id': task_id,
        'attempt_id': 'attempt-' + task_id + '-' + str(number), 'strategy_id': 'artifact-owner',
        'outcome': 'artifact', 'observation_ids': [observation_id], 'rationale_ref': None})


def test_actual_progress_is_ordered_across_tasks_by_committed_journal(world):
    from test_workflow import _policy_owner
    runtime, state = _policy_owner(world)
    state = command(runtime, world, state, 'workflow.graph', {'nodes': [
        {'id': task, 'deps': [], 'criteria': ['accept'], 'estimate': 1} for task in ('work', 'alpha')],
        'wip_limit': 1, 'reason': 'Two measured artifact obligations'})
    state = _record_task_progress(runtime, world, state, 'work', 1)
    first_revision = state['revision']
    state = _record_task_progress(runtime, world, state, 'alpha', 2)
    assert inspect(world, state)['last_useful_progress']['task_id'] == 'alpha'
    state = _record_task_progress(runtime, world, state, 'work', 3)
    progress_revision = state['revision']
    state = command(runtime, world, state, 'progress', {'summary': 'Later prose is not measured progress'})
    before = {str(p): p.read_bytes() for p in world['project'].rglob('*') if p.is_file()}
    latest = inspect(world, state)['last_useful_progress']
    assert latest['attempt_id'] == 'attempt-work-3'
    assert latest['task_id'] == 'work' and latest['journal_revision'] == progress_revision > first_revision
    assert latest['order_basis'] == 'FIRST_COMMITTED_JOURNAL_REVISION'
    assert latest['outcome'] == 'artifact' and latest['evidence_ids']
    assert before == {str(p): p.read_bytes() for p in world['project'].rglob('*') if p.is_file()}


def test_failure_attempt_is_retained_without_becoming_useful_progress(world, monkeypatch):
    from test_workflow import _native_process_fixture
    runtime, state, payload = _native_process_fixture(world, monkeypatch, exit_code=7)
    state = command(runtime, world, state, 'workflow.attempt', payload)
    before = runtime.load_run(world['project'], state['run_id'])
    assert before['extensions']['workflow']['progress']['work'][-1]['meaningful'] is False
    assert inspect(world, state)['last_useful_progress'] is None
    assert runtime.load_run(world['project'], state['run_id']) == before


def _admitted_child(world):
    from datetime import datetime, timedelta, timezone
    from test_workflow import _policy_owner
    runtime, state = _policy_owner(world)
    state = command(runtime, world, state, 'workflow.budget', {'limits': {'units': {'limit': 10, 'enforcement': 'hard'}},
        'deadline': (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()})
    for identity, category, units in (('worker', 'work', 5), ('audit', 'integration', 1),
                                      ('verify', 'verification', 1), ('recover', 'recovery', 1)):
        state = command(runtime, world, state, 'workflow.reserve', {'reservation_id': identity, 'amounts': {'units': units}, 'category': category})
    root = world['project'] / 'delegated'
    for name in ('output', 'scratch'): (root / name).mkdir(parents=True)
    brief = {'child_id': 'worker', 'task_id': 'work', 'deliverables': ['Produce reviewed output'],
        'paths': [str(root)], 'criteria': ['accept'], 'reservation_id': 'worker', 'integration_reservation_id': 'audit',
        'verification_reservation_id': 'verify', 'recovery_reservation_id': 'recover',
        'integration_owner': state['owner']['session_uuid'], 'return_contract': ['artifact_ids', 'evidence_ids', 'disposition'],
        'cancellation': 'Retain partial evidence and return', 'mode': 'native-cli', 'client': 'claude',
        'required_capabilities': ['read', 'write', 'edit', 'shell'], 'admission_id': 'parent',
        'admission_requests': [{'id': 'parent', 'actor': world['actor'], 'paths': [str(root)]}],
        'file_contract': {'schema_version': 1, 'immutable_inputs': [], 'output_roots': [str(root / 'output')], 'scratch_root': str(root / 'scratch')}}
    state = command(runtime, world, state, 'workflow.dispatch', brief)
    return runtime, state


def test_actual_child_cancellation_and_partial_return_are_visible_without_mutation(world):
    runtime, state = _admitted_child(world)
    child = inspect(world, state)['children'][0]
    assert child['status'] == 'running' and child['disposition'] == 'running'
    assert child['audit_status'] == 'required' and child['unresolved'] is True
    assert child['cancellation_requested'] is False
    state = command(runtime, world, state, 'workflow.cancel_child', {'child_id': 'worker', 'reason': 'Preserve unfinished evidence'})
    child = inspect(world, state)['children'][0]
    assert child['status'] == 'running' and child['cancellation_requested'] is True
    state = command(runtime, world, state, 'workflow.return', {'child_id': 'worker', 'disposition': 'partial',
        'artifact_ids': [], 'evidence_ids': [], 'reason': 'Partial worker status; no output has been independently observed'})
    before = {str(p): p.read_bytes() for p in world['project'].rglob('*') if p.is_file()}
    child = inspect(world, state)['children'][0]
    assert child['status'] == 'partial' and child['disposition'] == 'partial'
    assert child['audit_status'] == 'required' and child['unresolved'] is True
    assert child['artifact_ids'] == [] and child['evidence_ids'] == []
    assert child['authority_granted'] is False
    assert before == {str(p): p.read_bytes() for p in world['project'].rglob('*') if p.is_file()}


@pytest.mark.parametrize('disposition,audit,unresolved', [
    ('running', 'required', True), ('complete', 'required', True),
    ('complete', 'accepted', False), ('partial', 'rejected', True),
    ('failed', 'required', True), ('cancelled', 'required', True)])
def test_child_disposition_never_substitutes_for_audit_acceptance(disposition, audit, unresolved):
    module = importlib.import_module('operator_status')
    source = {'disposition': disposition, 'audit_status': audit, 'cancellation_requested': True,
        'artifact_ids': ['retained-partial'], 'evidence_ids': ['native-return']}
    before = json.loads(json.dumps(source))
    row = module._child_status('worker', source)
    assert row['status'] == disposition and row['audit_status'] == audit
    assert row['unresolved'] is unresolved and row['cancellation_requested'] is True
    assert row['artifact_ids'] == source['artifact_ids'] and row['evidence_ids'] == source['evidence_ids']
    assert source == before and row['authority_granted'] is False

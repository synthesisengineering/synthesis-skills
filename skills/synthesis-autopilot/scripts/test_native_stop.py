"""Actual isolated launcher/journal checks plus explicit synthetic wire fixtures."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / 'skills/synthesis-onboarding/scripts'))
from test_workflow import world, _policy_owner, _owner_register, _owner_progress
import native_stop
import release_runtime
import system_contract


def test_combined_checkpoint_terminal_observes_autopilot_without_spending(monkeypatch):
    seen = []
    def observe(payload, *, reserve_feedback=True):
        seen.append(reserve_feedback)
        return {'continue': False, 'stopReason': 'Unresolved owner', 'systemMessage': 'UNRESOLVED: owner'}
    monkeypatch.setattr(native_stop, '_autopilot_result', observe)
    payload = {'hook_event_name': 'Stop', 'session_id': 'fixture', 'stop_hook_active': False}
    result = native_stop.combined_result(payload, checkpoint=lambda _: {'continue': False, 'stopReason': 'Checkpoint unavailable'})
    assert seen == [False]
    assert result['continue'] is False and 'owner' in result['systemMessage']


@pytest.mark.parametrize('order', [0, 1])
def test_terminal_sibling_dominates_plain_unreserved_block(order):
    results = [{'decision': 'block', 'reason': 'No owner reservation'}, {'continue': False, 'stopReason': 'Cancelled'}]
    payload = {'hook_event_name': 'Stop', 'session_id': 'fixture', 'stop_hook_active': False}
    result = native_stop.combined_result(payload, checkpoint=lambda _: results[order], autopilot_check=lambda _: results[1-order])
    assert result['continue'] is False and result.get('decision') != 'block'


def _installed_owner_launcher(world, tmp_path, monkeypatch):
    import workflow
    runtime, state = _policy_owner(world)
    state = _owner_register(runtime, world, state, 'progress-spec', {'schema_version': 1,
        'kind': 'progress_observation', 'arguments': {'task_id': 'work'}})
    state = _owner_progress(runtime, world, state, 1)
    result = workflow.reserve_stop_feedback(runtime, state, world['actor'], project=world['project'], runtime_root=world['runtime'])
    assert result['action'] == 'corrective'
    generation = tmp_path / 'isolated-generation'
    shutil.copytree(ROOT, generation, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
    script = 'synthesis-repo-guard/repo_sync_check.py'
    wire = {'decision': 'block', 'reason': 'Observed productive work remains', '_synthesis_policy': result['reservation']}
    # A deterministic worker fixture; the generated launcher, descriptor,
    # policy helper, PM owner and journal transaction are the actual modules.
    (generation / 'skills' / script).write_text('import json\nprint(json.dumps(' + repr(wire) + '))\n')
    pointer = tmp_path / 'activation' / 'active-release.json'
    pointer.parent.mkdir()
    pointer.with_name(pointer.name + '.lock').touch()
    version = json.loads((generation / '.claude-plugin/plugin.json').read_text())['version']
    data = {'schema_version': 1, 'version': version, 'channel': 'stable', 'ref': 'stable',
        'commit': '1' * 40, 'tree': '2' * 40, 'content_digest': system_contract.canonical_tree_digest(generation),
        'digest_algorithm': 'sha256-tree-v1', 'tree_policy': 'regular-files-and-directories-no-links-v1',
        'source_url': 'https://fixture.invalid/skills.git', 'resolved_at': '2026-09-25T00:00:00Z',
        'release_root': str(generation), 'interpreter': release_runtime.interpreter_pin()}
    launcher = tmp_path / 'bin' / 'synthesis'
    launcher.parent.mkdir()
    body = system_contract.launcher_bytes(pointer, data['interpreter'])
    launcher.write_bytes(body); launcher.chmod(0o755)
    import hashlib
    data['launcher'] = {'path': str(launcher), 'runtime_schema': 1, 'sha256': hashlib.sha256(body).hexdigest()}
    pointer.write_text(json.dumps(data))
    monkeypatch.setenv('SYNTHESIS_COORDINATION_BOARD', str(world['board']))
    monkeypatch.setenv('SYNTHESIS_AUTOPILOT_RUNTIME', str(world['runtime']))
    monkeypatch.delenv('SYNTHESIS_PUBLIC_SKILLS_SOURCE', raising=False)
    def invoke(payload=None):
        return subprocess.run([str(launcher), 'exec-public', '--hook-event', 'Stop', script],
            input=json.dumps(payload or world['actor']['native_payload']), text=True, capture_output=True,
            timeout=30, env=dict(os.environ), check=False)
    return runtime, state, generation, invoke


def test_generated_public_launcher_consumes_one_actual_owner_reservation(world, tmp_path, monkeypatch):
    runtime, state, generation, invoke = _installed_owner_launcher(world, tmp_path, monkeypatch)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: invoke(), range(2)))
    values = [json.loads(result.stdout) for result in results]
    assert all(result.returncode == 0 for result in results)
    assert sum(value.get('decision') == 'block' for value in values) == 1, values
    assert sum(value.get('continue') is False for value in values) == 1
    assert all('_synthesis_policy' not in value for value in values)
    retained = runtime.load_run(world['project'], state['run_id'])
    feedback = retained['extensions']['workflow_persistence']['feedback']
    assert len(feedback) == 1 and feedback[0]['status'] == 'emitted'
    # Fresh process/new false-bit wakes cannot resurrect the consumed proof.
    assert json.loads(invoke().stdout)['continue'] is False
    denied = invoke({**world['actor']['native_payload'], 'hook_event_name': 'PreToolUse'})
    assert denied.returncode != 0 and '"continue"' not in denied.stdout


def test_generated_public_launcher_missing_policy_remains_terminal(world, tmp_path, monkeypatch):
    runtime, state, generation, invoke = _installed_owner_launcher(world, tmp_path, monkeypatch)
    helper = generation / 'skills/synthesis-autopilot/scripts/persistence_policy.py'
    helper.rename(helper.with_suffix('.unavailable'))
    # The actual descriptor guard sees changed installed bytes before child or
    # policy import; no warning-and-pass or corrective turn is produced.
    result = invoke()
    assert result.returncode == 0 and json.loads(result.stdout)['continue'] is False
    assert runtime.load_run(world['project'], state['run_id'])['extensions']['workflow_persistence']['feedback'][0]['status'] == 'reserved'

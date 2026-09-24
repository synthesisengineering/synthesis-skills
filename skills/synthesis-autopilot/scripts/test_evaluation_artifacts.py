"""Actual work-product acceptance; self-reported outcome JSON is never proof."""
from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path
import sys

import pytest


@pytest.fixture
def artifacts():
    spec = importlib.util.spec_from_file_location('evaluation_artifacts_test', Path(__file__).with_name('evaluation_artifacts.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def csv_file(path, rows):
    with path.open('w', newline='') as handle:
        csv.writer(handle).writerows(rows)


def test_thirty_concrete_artifact_contracts_have_independent_collectors(artifacts):
    contracts = artifacts.contracts()
    assert len(contracts) == 30
    assert {case['id'] for case in contracts} == {f'{d}{n:02}' for d in 'SRWDBK' for n in range(1, 6)}
    assert all(case['required_artifacts'] and case['collector'] for case in contracts)
    assert all('outcome.json' not in case['required_artifacts'] for case in contracts)


@pytest.mark.parametrize('task', [f'{d}{n:02}' for d in 'SRWDBK' for n in range(1, 6)])
def test_outcome_claim_alone_never_passes_actual_artifact_acceptance(artifacts, tmp_path, task):
    bundle = artifacts.prepare(task, tmp_path)
    worker = Path(bundle['worker'])
    (worker/'outcome.json').write_text(json.dumps({'passed':True,'all_work_done':True}))
    result = artifacts.grade_artifacts(bundle)
    assert result['deterministic'] != 'PASS'
    assert result['semantic'] == 'UNKNOWN'


def test_data_reconciliation_reads_real_csv_and_preserves_inputs(artifacts, tmp_path):
    bundle = artifacts.prepare('D02', tmp_path)
    worker = Path(bundle['worker'])
    csv_file(worker/'reconciliation.csv', [['invoices','payments','balance'], ['15.35','12.15','3.20']])
    assert artifacts.grade_artifacts(bundle)['deterministic'] == 'PASS'
    csv_file(worker/'reconciliation.csv', [['invoices','payments','balance'], ['15.35','12.15','999']])
    assert artifacts.grade_artifacts(bundle)['deterministic'] == 'FAIL'


def test_real_prose_is_required_and_semantics_stay_uncalibrated(artifacts, tmp_path):
    bundle = artifacts.prepare('W02', tmp_path)
    worker = Path(bundle['worker'])
    (worker/'review.md').write_text('The author is a friend. The book argues that small experiments reveal hidden constraints. That is useful as a hypothesis, but no comparative evidence is supplied. The excerpt does not establish which experiments work or when they fail. I would treat the advice as a starting point for testing rather than proof of a general rule.\n')
    result = artifacts.grade_artifacts(bundle)
    assert result['deterministic'] == 'PASS'
    assert result['semantic'] == 'UNKNOWN'
    (worker/'review.md').write_text('I have no relationship with the author. Everything is proven.')
    assert artifacts.grade_artifacts(bundle)['deterministic'] == 'FAIL'


def test_worker_cannot_write_its_own_browser_state_receipt(artifacts, tmp_path):
    bundle = artifacts.prepare('B02', tmp_path)
    worker = Path(bundle['worker'])
    (worker/'browser-evidence.json').write_text(json.dumps({'stored':{'name':'Synthetic Operator','count':3},'submission_count':1}))
    assert artifacts.grade_artifacts(bundle)['deterministic'] != 'PASS'
    with artifacts.LocalBrowserFixture('B02') as fixture:
        fixture.submit({'name':'Synthetic Operator','count':3}, operation_key='one')
        result = artifacts.grade_artifacts(bundle, browser_observer=fixture.observe)
        assert result['deterministic'] == 'PASS'
        assert result['native_browser_journey'] == 'UNKNOWN'
        fixture.submit({'name':'Synthetic Operator','count':3}, operation_key='two')
        assert artifacts.grade_artifacts(bundle, browser_observer=fixture.observe)['deterministic'] == 'FAIL'


def test_browser_operation_key_reconciliation_has_real_target_counter(artifacts, tmp_path):
    bundle = artifacts.prepare('B04', tmp_path)
    with artifacts.LocalBrowserFixture('B04') as fixture:
        before = fixture.observe()
        assert before['committed_count'] == 1
        assert fixture.lookup('op-1')['committed'] is True
        assert artifacts.grade_artifacts(bundle, browser_observer=fixture.observe)['deterministic'] == 'PASS'
        fixture.submit({'ignored':True}, operation_key='op-2')
        assert artifacts.grade_artifacts(bundle, browser_observer=fixture.observe)['deterministic'] == 'FAIL'


def test_changed_sentinel_or_source_fails_even_with_good_output(artifacts, tmp_path):
    bundle = artifacts.prepare('D05', tmp_path)
    worker = Path(bundle['worker'])
    csv_file(worker/'summary.csv', [['observed_mean','coverage','imputed'], ['3','2/4','0']])
    assert artifacts.grade_artifacts(bundle)['deterministic'] == 'PASS'
    (worker/'sentinel.txt').write_text('corrupted')
    assert artifacts.grade_artifacts(bundle)['deterministic'] == 'FAIL'


def test_symlink_artifact_cannot_read_outside_worker_boundary(artifacts, tmp_path):
    bundle = artifacts.prepare('W01', tmp_path)
    outside = tmp_path/'private.md'; outside.write_text('backup runs daily; restore has not been tested')
    (Path(bundle['worker'])/'explanation.md').symlink_to(outside)
    assert artifacts.grade_artifacts(bundle)['deterministic'] == 'FAIL'


def test_software_consumer_runs_heldout_inputs_with_bounded_sandbox(artifacts, tmp_path):
    if not artifacts.sandbox_available():
        pytest.skip('Native filesystem/network sandbox is unavailable on this test host')
    bundle = artifacts.prepare('S01', tmp_path)
    (Path(bundle['worker'])/'parser.py').write_text('def parse(value):\n    parts=value.split(",")\n    if any(not p.strip() for p in parts): raise ValueError("empty")\n    return [int(p.strip()) for p in parts]\n')
    result = artifacts.grade_artifacts(bundle)
    assert result['deterministic'] == 'PASS'
    assert result['execution']['sandbox_verified'] is True
    (Path(bundle['worker'])/'parser.py').write_text('def parse(value): return [1,-2,3]\n')
    assert artifacts.grade_artifacts(bundle)['deterministic'] == 'FAIL'


def test_software_timeout_is_failure_not_an_endless_grader(artifacts, tmp_path):
    if not artifacts.sandbox_available():
        pytest.skip('Native filesystem/network sandbox is unavailable on this test host')
    bundle = artifacts.prepare('S01', tmp_path)
    (Path(bundle['worker'])/'parser.py').write_text('while True: pass\n')
    result = artifacts.grade_artifacts(bundle, timeout=0.2)
    assert result['deterministic'] == 'FAIL'
    assert any('time' in problem.lower() for problem in result['problems'])


def test_missing_sandbox_never_executes_worker_code(artifacts, tmp_path, monkeypatch):
    bundle = artifacts.prepare('S01', tmp_path)
    marker = tmp_path/'executed'
    (Path(bundle['worker'])/'parser.py').write_text(f'open({str(marker)!r},"w").write("unsafe")\n')
    monkeypatch.setattr(artifacts, 'sandbox_available', lambda:False)
    assert artifacts.grade_artifacts(bundle)['deterministic'] == 'UNKNOWN'
    assert not marker.exists()

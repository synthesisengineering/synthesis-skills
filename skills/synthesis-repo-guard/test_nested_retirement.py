import json
import os
from pathlib import Path
import signal
import sys

import pytest

SOURCE = Path(__file__).resolve().parents[2]
PM = SOURCE / 'skills/synthesis-project-management/scripts'
RG = SOURCE / 'skills/synthesis-repo-guard'
sys.path[:0] = [str(PM), str(RG)]
import test_checkpoint_sync as cp
from test_checkpoint_sync import isolated_runtime  # noqa: F401

@pytest.fixture(autouse=True)
def isolate_checkpoint(tmp_path, monkeypatch):
    for name, suffix in [('STATE_DIR',''),('PENDING_DIR','pending'),('LOCAL_HANDOFF_DIR','local-handoff'),('RETIREMENT_DIR','retired-worktrees')]:
        monkeypatch.setattr(cp.MODULE, name, tmp_path / 'state' / suffix)

def prepared(tmp_path):
    repo, _, _ = cp.repository(tmp_path)
    target = repo / '.claude/worktrees/exact'
    target.parent.mkdir(parents=True)
    cp.command('git','worktree','add','--detach',str(target),'main',cwd=repo)
    head = cp.command('git','rev-parse','HEAD',cwd=target)
    _, intent, _ = cp.MODULE.prepare_retirement_intent(target,repo,head,'origin','origin/main',expect_active=True,dry_run=False)
    return repo, target, intent

def test_nested_prepared_proof_survives_removal_and_retry(tmp_path):
    repo,target,intent=prepared(tmp_path)
    before=json.loads(intent.read_text())
    assert before['linked_identity']['common_directory']['path']==str(repo/'.git')
    assert cp.MODULE.verify_prepared_retirement(intent)['action']=='retirement-removal-ready'
    cp.command('git','worktree','remove',str(target),cwd=repo)
    result,_=cp.MODULE.complete_retirement_intent(intent)
    assert result['action']=='retired-worktree-reconciled'
    assert json.loads(intent.read_text())['linked_identity']==before['linked_identity']
    again,_=cp.MODULE.complete_retirement_intent(intent)
    assert again==result

@pytest.mark.parametrize('change',['dirty','git_file','common_proof','worktree_inode','missing_proof'])
def test_prepared_identity_change_refuses_removal(tmp_path,change):
    repo,target,intent=prepared(tmp_path)
    if change=='dirty': (target/'new.txt').write_text('retained')
    elif change=='git_file': (target/'.git').write_text((target/'.git').read_text()+'\n')
    elif change=='worktree_inode':
        target.rename(target.with_name('retained'))
        target.mkdir()
    else:
        data=json.loads(intent.read_text())
        if change=='missing_proof':data.pop('linked_identity')
        else:data['linked_identity']['common_directory']['inode']+=1
        intent.write_text(json.dumps(data))
    before=intent.read_bytes()
    with pytest.raises((ValueError,OSError)):
        cp.MODULE.verify_prepared_retirement(intent)
    assert target.exists() and intent.read_bytes()==before

@pytest.mark.parametrize('change',['common_inode','foreign_repository','admin_reappearance'])
def test_complete_refuses_changed_surviving_identity(tmp_path,change):
    repo,target,intent=prepared(tmp_path)
    cp.command('git','worktree','remove',str(target),cwd=repo)
    data=json.loads(intent.read_text())
    if change=='common_inode':data['linked_identity']['common_directory']['inode']+=1
    elif change=='foreign_repository':
        other=tmp_path/'other';other.mkdir()
        clone,_,_=cp.repository(other)
        data['repository']=str(clone)
    else:Path(data['linked_identity']['git_dir']['path']).mkdir(parents=True)
    intent.write_text(json.dumps(data));before=intent.read_bytes()
    with pytest.raises((ValueError,OSError)):
        cp.MODULE.complete_retirement_intent(intent)
    assert intent.read_bytes()==before

def test_nested_no_intent_recovery_cannot_invent_registration(tmp_path):
    repo,_,_=cp.repository(tmp_path)
    target=repo/'.claude/worktrees/nonexistent'
    head=cp.command('git','rev-parse','HEAD',cwd=repo)
    with pytest.raises(ValueError,match='preserved'):
        cp.MODULE.prepare_retirement_intent(target,repo,head,'origin','origin/main',expect_active=False,dry_run=False)

def test_parent_alias_refused_before_retirement(tmp_path):
    repo,target,_=prepared(tmp_path)
    alias=tmp_path/'alias';alias.symlink_to(repo,target_is_directory=True)
    with pytest.raises(ValueError,match='alias|symlink'):
        cp.MODULE.validate_retirement_target(alias/'.claude/worktrees/exact',repo,expect_active=True)
    assert target.exists()


@pytest.mark.parametrize('replacement', ['unchanged', 'fifo'])
def test_prepared_retirement_rejects_pipe_before_metadata_read(tmp_path, monkeypatch, replacement):
    _, target, intent = prepared(tmp_path)
    marker = Path(json.loads(intent.read_text())['linked_identity']['backlink']['path'])
    before = intent.read_bytes()
    original_open = os.open
    observed = False

    def open_at_read(path, flags, *args, **kwargs):
        nonlocal observed
        if Path(path) == marker and not observed:
            observed = True
            if replacement == 'fifo':
                marker.rename(tmp_path / 'retained-backlink')
                os.mkfifo(marker)
        return original_open(path, flags, *args, **kwargs)

    def expired(_signal, _frame):
        raise AssertionError('retirement metadata read blocked on a substituted pipe')

    monkeypatch.setattr(cp.MODULE.os, 'open', open_at_read)
    previous = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, 3.0)
    try:
        if replacement == 'unchanged':
            assert cp.MODULE.verify_prepared_retirement(intent)['action'] == 'retirement-removal-ready'
        else:
            with pytest.raises((OSError, ValueError)):
                cp.MODULE.verify_prepared_retirement(intent)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
    assert observed and target.exists() and intent.read_bytes() == before


@pytest.mark.parametrize('replacement', ['unchanged', 'regular', 'symlink'])
def test_last_backlink_consumption_binds_prepared_identity(tmp_path, monkeypatch, replacement):
    _, target, intent = prepared(tmp_path)
    backlink = Path(json.loads(intent.read_text())['linked_identity']['backlink']['path'])
    original = cp.MODULE._retirement_marker
    observations = 0
    before = intent.read_bytes()

    def observed(path, *, directory):
        nonlocal observations
        proof = original(path, directory=directory)
        if Path(path) == backlink:
            observations += 1
            if observations == 3 and replacement != 'unchanged':
                raw = backlink.read_bytes()
                backlink.rename(tmp_path / 'retained-backlink')
                if replacement == 'regular':
                    backlink.write_bytes(raw)
                else:
                    substitute = tmp_path / 'substitute'
                    substitute.write_bytes(raw)
                    backlink.symlink_to(substitute)
        return proof

    monkeypatch.setattr(cp.MODULE, '_retirement_marker', observed)
    if replacement == 'unchanged':
        assert cp.MODULE.verify_prepared_retirement(intent)['action'] == 'retirement-removal-ready'
    else:
        with pytest.raises((OSError, ValueError)):
            cp.MODULE.verify_prepared_retirement(intent)
    assert observations == 3 and target.exists() and intent.read_bytes() == before

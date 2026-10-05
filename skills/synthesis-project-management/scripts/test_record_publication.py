"""Committed transaction custody participates in ordinary Git publication."""
from pathlib import Path
import hashlib
import json
import subprocess
import pytest
from test_record_transaction import world, registry_world, registry_patch, registry_gate
from test_run_admission import git
import context_edit
import record_transaction as rt
import context_doctor


def test_registry_receipt_selects_journal_and_publishes_complete_custody(world,tmp_path):
    index=registry_world(world)
    receipt=registry_patch(world,index)
    git(world['repo'],'add','projects/index.yaml')
    assert registry_gate(world)==0
    git(world['repo'],'commit','-m','Fixture registry publication')
    assert context_doctor.uncommitted(world['repo'],world['project'])
    plan=rt.publication_plan(world['project'])
    assert set(receipt['publication']['required_files'])<=set(plan['required_files'])
    assert plan['status']=='PUBLICATION_REQUIRED' and plan['remote_ready'] is False
    required=plan['required_files']
    assert str(index) in required
    journal=Path(receipt['journal'])
    assert {str(journal/'manifest.json'),str(journal/'commit.json'),str(journal.parent.parent/'history.json')}<=set(required)
    for name,digest in required.items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==digest
    git(world['repo'],'add','--',*[str(Path(p).relative_to(world['repo'])) for p in required])
    git(world['repo'],'commit','-m','Fixture durable custody')
    remote=tmp_path/'remote.git';subprocess.run(['git','init','--bare','--quiet',str(remote)],check=True)
    git(remote,'symbolic-ref','HEAD','refs/heads/main')
    git(world['repo'],'remote','add','origin',str(remote));git(world['repo'],'push','-u','origin','HEAD')
    assert not context_doctor.uncommitted(world['repo'],world['project'])
    clone=tmp_path/'clone';subprocess.run(['git','clone','--quiet',str(remote),str(clone)],check=True)
    for name,digest in required.items():assert hashlib.sha256((clone/Path(name).relative_to(world['repo'])).read_bytes()).hexdigest()==digest
    with rt.managed(clone/'projects/alpha'):pass


def test_publication_plan_retains_failed_preparations_and_has_no_git_effect(world):
    index=registry_world(world);registry_patch(world,index)
    residue=world['project']/rt.STORE/'preparing-retained';residue.mkdir();(residue/'opaque').write_bytes(b'failed preparation evidence')
    initial=world['project']/(rt.STORE+'.init-retained');initial.mkdir();(initial/'opaque').write_bytes(b'initial preparation evidence')
    before=git(world['repo'],'status','--porcelain')
    plan=rt.publication_plan(world['project'])
    assert str(residue/'opaque') in plan['required_files'] and str(initial/'opaque') in plan['required_files']
    assert git(world['repo'],'status','--porcelain')==before


@pytest.mark.parametrize('defect',['active','missing','corrupt','symlink','extra-completed'])
def test_publication_plan_refuses_unrecoverable_or_unsafe_history(world,defect):
    index=registry_world(world);receipt=registry_patch(world,index);journal=Path(receipt['journal'])
    if defect=='active':(world['project']/rt.STORE/'active').mkdir()
    elif defect=='missing':(journal/'commit.json').unlink()
    elif defect=='corrupt':(journal/'manifest.json').write_text('{}')
    elif defect=='symlink':(journal/'foreign').symlink_to(index)
    elif defect=='extra-completed':(journal.parent/('f'*32)).mkdir()
    with pytest.raises((ValueError,OSError,rt.RecordTransactionError)):rt.publication_plan(world['project'])


def test_publication_cli_is_read_only_and_explicit(world,capsys):
    index=registry_world(world);registry_patch(world,index)
    assert context_edit.main(['transaction-publication','--project',str(world['project'])])==0
    result=json.loads(capsys.readouterr().out)
    assert result['remote_ready'] is False and result['required_files']


def test_initial_preparation_is_retained_without_a_completed_store(world):
    initial=world['project']/(rt.STORE+'.init-retained');initial.mkdir()
    artifact=initial/'partial';artifact.write_bytes(b'retained incomplete preparation')
    plan=rt.publication_plan(world['project'])
    assert plan['required_files']=={str(artifact):hashlib.sha256(artifact.read_bytes()).hexdigest()}


def test_publication_selection_refuses_concurrent_membership_change(world,monkeypatch):
    index=registry_world(world);registry_patch(world,index)
    original=rt._publication_files
    def changed(paths):
        result=original(paths)
        (world['project']/rt.STORE/'new-evidence').write_bytes(b'concurrent retained evidence')
        return result
    monkeypatch.setattr(rt,'_publication_files',changed)
    with pytest.raises(rt.RecordTransactionError,match='membership changed'):
        rt.publication_plan(world['project'])


@pytest.mark.parametrize('damage',[False,True])
def test_publication_binds_retained_source_without_reusing_old_input_authority(world,damage):
    source=world['project']/'source.txt';source.write_bytes(b'original retained source')
    receipt=rt.apply(world['project'],[
        {'file':'created.md','create':{'text':'# Retained effect\n','mode':0o644}}],
        board=world['board'],native_payload=world['actor']['native_payload'],
        source_custody=[{'file':'source.txt','expected':rt._snapshot(source)[1]}])
    archived=Path(receipt['journal'])/'sources/0.source'
    source.write_bytes(b'later legitimate source edit')
    if damage:
        archived.write_bytes(b'corrupted archive')
        with pytest.raises(rt.RecordTransactionError,match='source custody changed'):
            rt.publication_plan(world['project'])
    else:
        plan=rt.publication_plan(world['project'])
        assert plan['required_files'][str(archived)]==hashlib.sha256(b'original retained source').hexdigest()
        assert source.read_bytes()==b'later legitimate source edit'

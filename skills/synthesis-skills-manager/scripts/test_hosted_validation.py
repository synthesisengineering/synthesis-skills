"""The publication shortcut reuses authenticated tests, never unchecked success claims."""
import copy
import hashlib
import io
import json
import zipfile
from pathlib import Path
import subprocess

import pytest
import hosted_validation as h
import release


def evidence():
    expected = {'head_tree': 'a'*40, 'change_base': 'b'*40, 'manifest_sha256': 'c'*64}
    contract = [{'case_id': 'real-case', 'argv': ['pytest', 'test_actual.py::test_case']}]
    source, workflow, commit = 'd'*64, 'e'*64, 'f'*40
    record = dict(schema=1, repository=h.REPOSITORY, run_id=12, run_attempt=1,
                  tree=expected['head_tree'], base=expected['change_base'], manifest_sha256=expected['manifest_sha256'],
                  source_sha256=source, contract_sha256=h.digest(contract), workflow_sha256=workflow,
                  coverage={'declared': 1, 'terminal': 1, 'not_run': 0}, execution_sha256='1'*64, authorizes_release=False)
    def run(identifier, path):
        return dict(id=identifier, run_attempt=1, head_sha=commit, path=path, status='completed', conclusion='success',
                    repository={'full_name': h.REPOSITORY}, head_repository={'full_name': h.REPOSITORY}, event='pull_request')
    def job(name, steps=(), conclusion='success'):
        return dict(name=name, status='completed', conclusion=conclusion,
                    steps=[dict(name=s, status='completed', conclusion='success') for s in steps])
    jobs = [job('source-checks', ['Run the complete source catalog concurrently']),
            job('conformance', ['Consume transaction-bound R5 acceptance', 'Retain candidate validation']),
            job('onboarding-portability (ubuntu-latest)'), job('onboarding-portability (macos-latest)')]
    distribution = [job(f'packages ({os}, {py})') for os in ('ubuntu-latest','macos-latest') for py in ('3.12','3.13','3.14')]
    distribution.append(job('arch-package', conclusion='skipped'))
    prefix = f'repos/{h.REPOSITORY}/actions'
    responses = {
        f'{prefix}/runs/12': run(12, h.WORKFLOW),
        f'{prefix}/runs/12/attempts/1/jobs?per_page=100': {'total_count':4,'jobs':jobs},
        f'{prefix}/runs/12/artifacts?per_page=100': {'total_count':1,'artifacts':[dict(id=22,name=h.ARTIFACT,expired=False,size_in_bytes=500,workflow_run={'id':12,'head_sha':commit})]},
        f'{prefix}/workflows/distribution.yml/runs?head_sha={commit}&per_page=100': {'workflow_runs':[run(13,'.github/workflows/distribution.yml')]},
        f'{prefix}/runs/13/attempts/1/jobs?per_page=100': {'total_count':7,'jobs':distribution},
    }
    def api(endpoint, binary=False):
        if endpoint == f'{prefix}/artifacts/22/zip':
            buf=io.BytesIO()
            with zipfile.ZipFile(buf,'w') as archive:
                archive.writestr('candidate-validation.json',json.dumps(record))
            return buf.getvalue()
        return responses[endpoint]
    return expected, contract, source, workflow, commit, record, responses, api


def verify(data):
    expected, contract, source, workflow, commit, _, _, api = data
    return h.verify(api,12,expected,source,contract,workflow,commit)


def test_complete_authoritative_candidate_is_accepted():
    result=verify(evidence())
    assert result['run_id']==12 and result['distribution']=={'run_id':13,'attempt':1}
    assert result['record']['authorizes_release'] is False


@pytest.mark.parametrize('field', ['tree','base','manifest_sha256','source_sha256','contract_sha256','workflow_sha256','run_id','run_attempt','repository','schema','coverage','execution_sha256','authorizes_release'])
def test_candidate_record_binding_refuses_mutation(field):
    data=evidence(); data[5][field]='stale-or-incomplete'
    with pytest.raises(ValueError): verify(data)


@pytest.mark.parametrize('attack', ['foreign-repo','foreign-head-repo','wrong-head','wrong-workflow','failure','running','skip-job','missing-job','duplicate-job','skip-step','missing-step','expired','multiple-artifacts','wrong-artifact-head','wrong-artifact-run','oversized','bad-digest','distribution-failed','distribution-missing-job','distribution-skipped'])
def test_authenticated_envelope_refuses_invalid_execution(attack):
    data=evidence(); responses=data[6]; prefix=f'repos/{h.REPOSITORY}/actions'
    run=responses[f'{prefix}/runs/12']; jobs=responses[f'{prefix}/runs/12/attempts/1/jobs?per_page=100']['jobs']
    artifacts=responses[f'{prefix}/runs/12/artifacts?per_page=100']; artifact=artifacts['artifacts'][0]
    distribution=responses[f'{prefix}/runs/13/attempts/1/jobs?per_page=100']['jobs']
    if attack=='foreign-repo':run['repository']['full_name']='foreign/repo'
    elif attack=='foreign-head-repo':run['head_repository']['full_name']='foreign/repo'
    elif attack=='wrong-head':run['head_sha']='0'*40
    elif attack=='wrong-workflow':run['path']='other.yml'
    elif attack=='failure':run['conclusion']='failure'
    elif attack=='running':run['status']='in_progress'
    elif attack=='skip-job':jobs[0]['conclusion']='skipped'
    elif attack=='missing-job':jobs.pop()
    elif attack=='duplicate-job':jobs[-1]=copy.deepcopy(jobs[0])
    elif attack=='skip-step':jobs[1]['steps'][0]['conclusion']='skipped'
    elif attack=='missing-step':jobs[0]['steps']=[]
    elif attack=='expired':artifact['expired']=True
    elif attack=='multiple-artifacts':artifacts['artifacts'].append(copy.deepcopy(artifact));artifacts['total_count']=2
    elif attack=='wrong-artifact-head':artifact['workflow_run']['head_sha']='0'*40
    elif attack=='wrong-artifact-run':artifact['workflow_run']['id']=11
    elif attack=='oversized':artifact['size_in_bytes']=h.MAX_BYTES+1
    elif attack=='bad-digest':artifact['digest']='sha256:'+'0'*64
    elif attack=='distribution-failed':distribution[0]['conclusion']='failure'
    elif attack=='distribution-missing-job':distribution.pop()
    elif attack=='distribution-skipped':distribution[0]['conclusion']='skipped'
    with pytest.raises(ValueError):verify(data)


@pytest.mark.parametrize('member,contents', [('other.json','{}'),('../candidate-validation.json','{}'),('candidate-validation.json','x'*(h.RECORD_BYTES+1))])
def test_archive_refuses_unexpected_members_without_extraction(member,contents):
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w') as archive:archive.writestr(member,contents)
    with pytest.raises(ValueError):h.archive_record(buf.getvalue())


def test_portable_source_identity_ignores_only_git_untracked_permission_bits(tmp_path):
    from release_check_groups import source_digest
    file=tmp_path/'code.py';file.write_text('original');file.chmod(0o644);tmp_path.chmod(0o755)
    native=source_digest(tmp_path);portable=source_digest(tmp_path,portable=True)
    tmp_path.chmod(0o700);file.chmod(0o600)
    assert source_digest(tmp_path)!=native
    assert source_digest(tmp_path,portable=True)==portable
    file.chmod(0o700)
    assert source_digest(tmp_path,portable=True)!=portable
    file.chmod(0o600);file.write_text('changed')
    assert source_digest(tmp_path,portable=True)!=portable


def test_publication_rechecks_hosted_proof_and_dirty_source(tmp_path,monkeypatch):
    boundary={'change_base':'base'};expected={'transaction_id':'now'};proof={'run_id':12,'candidate_commit':'candidate'}
    authority=release.HostedAcceptanceAuthority('base',expected,proof,boundary)
    monkeypatch.setattr(release,'acceptance_boundary',lambda _: (boundary,''))
    monkeypatch.setattr(release,'acceptance_expectation',lambda *_: (expected,''))
    status=subprocess.CompletedProcess([],0,'','')
    monkeypatch.setattr(release,'run',lambda *a,**k:status)
    calls=[]
    def hosted(*args):calls.append(args);return copy.deepcopy(proof)
    monkeypatch.setattr(release,'_verify_hosted',hosted)
    assert release.revalidate_acceptance_authority(tmp_path,authority)[0] and len(calls)==1
    status.stdout=' M code.py\n'
    assert not release.revalidate_acceptance_authority(tmp_path,authority)[0] and len(calls)==1
    status.stdout='';proof['artifact_id']=999
    assert not release.revalidate_acceptance_authority(tmp_path,authority)[0]

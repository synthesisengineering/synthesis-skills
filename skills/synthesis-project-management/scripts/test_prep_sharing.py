"""Synthetic native seats, actual sharing/transaction owners, retained effects."""
from pathlib import Path
import hashlib, importlib.util, json, sys
import pytest
import coordination
import run_admission
from test_run_admission import world as _world, SEAT
from coordination_schema import identity_from_uuid

world = _world
PREP = Path(__file__).resolve().parents[2] / 'synthesis-meeting-prep/scripts/prep_init.py'
spec = importlib.util.spec_from_file_location('prep_shared_owner', PREP)
prep = importlib.util.module_from_spec(spec); spec.loader.exec_module(prep)
OWNER='01990000-0000-7000-8000-000000000044'
REF='cc:01990000-0000-7000-8000-000000000055'

@pytest.fixture
def shared(world, monkeypatch):
    repo=world['repo'];folder=repo/'meeting-preps';folder.mkdir(mode=0o700)
    (repo/'projects/index.yaml').write_text('- id: alpha\n  status: active\n- id: recipient\n  status: active\n')
    marker=repo/'profiles/meeting-prep/.owner.json';marker.parent.mkdir(parents=True)
    marker.write_text(json.dumps({'schema':1,'workspace':'fixture'}))
    text=world['board'].read_text();rows=coordination.rows(text)
    own=rows[0]; own.context_role='contributor'
    import copy
    recipient=copy.deepcopy(own);identity=identity_from_uuid(OWNER)
    recipient.session_uuid=OWNER;recipient.compact_id=identity.compact_id;recipient.speakable_id=identity.speakable_id
    recipient.client_ref=REF;recipient.project='recipient';recipient.claims=[str(folder)+'/**']
    rows.append(recipient);world['board'].write_text(coordination.replace_table(text,rows))
    return world

def grant(w, monkeypatch, *, operation='create', before=None, **overrides):
    options=dict(context_repo=w['repo'],workspace='fixture',artifact='meeting.md',board=w['board'],recipient=OWNER,
                 contributor=SEAT,operation=operation,before=before,private=True)
    options.update(overrides)
    with monkeypatch.context() as m:
        m.setenv('SYNTHESIS_CLIENT_SESSION_REF',REF)
        return prep.share_pack(**options)

def write(w,g,text='New material\n',**overrides):
    options=dict(context_repo=w['repo'],workspace='fixture',artifact='meeting.md',text=text,board=w['board'],
                 native_payload=w['actor']['native_payload'],grant_id=g['id'],operation=g['operation'],before=g['before'])
    options.update(overrides);return prep.write_pack(**options)

def files(w):
    return {str(p.relative_to(w['repo'])):p.read_bytes() for p in w['repo'].rglob('*') if p.is_file() and '.git' not in p.parts}

@pytest.mark.parametrize('operation',['create','append'])
def test_shared_prep_actual_native_transaction(shared,monkeypatch,operation):
    target=shared['repo']/'meeting-preps/meeting.md';before=None
    if operation=='append':
        target.write_text('Prior material\n');target.chmod(0o600);before=hashlib.sha256(target.read_bytes()).hexdigest()
    g=grant(shared,monkeypatch,operation=operation,before=before)
    board=shared['board'].read_bytes()
    assert write(shared,g)['status']=='committed'
    assert target.read_text()==('Prior material\n' if before else '')+'New material\n'
    assert target.stat().st_mode & 0o777==0o600
    assert shared['board'].read_bytes()==board
    assert str(shared['repo']/'meeting-preps')+'/**' in board.decode()
    prior=files(shared)
    with pytest.raises((ValueError,RuntimeError,FileExistsError)):write(shared,g)
    assert files(shared)==prior

@pytest.mark.parametrize('bad',['private','recipient','contributor','workspace','artifact','expiry','forged-caller'])
def test_shared_prep_grant_refusal_preserves_board_and_files(shared,monkeypatch,bad):
    options={}
    if bad=='private':options['private']=False
    if bad=='recipient':options['recipient']=SEAT
    if bad=='contributor':options['contributor']=OWNER
    if bad=='workspace':options['workspace']='other'
    if bad=='artifact':options['artifact']='../outside.md'
    if bad=='expiry':options['ttl']=0
    before=files(shared);board=shared['board'].read_bytes()
    with pytest.raises((ValueError,RuntimeError)):
        if bad=='forged-caller':prep.share_pack(shared['repo'],'fixture','meeting.md',board=shared['board'],recipient=OWNER,contributor=SEAT,operation='create',private=True)
        else:grant(shared,monkeypatch,**options)
    assert shared['board'].read_bytes()==board
    assert files(shared)==before

@pytest.mark.parametrize('bad',['missing','forged-id','workspace','other-artifact','native','expired','owner-scope','owner-released','public','marker'])
def test_shared_prep_consumer_refusals(shared,monkeypatch,bad):
    g=grant(shared,monkeypatch);options={}
    if bad in ('missing','forged-id'):g['id']='0'*32
    if bad=='workspace':options['workspace']='other'
    if bad=='other-artifact':options['artifact']='outside.md'
    if bad=='native':options['native_payload']=dict(shared['actor']['native_payload'],session_id='absent')
    if bad=='expired':monkeypatch.setattr(run_admission.time,'time',lambda:g['expires']+1)
    if bad.startswith('owner-'):
        text=shared['board'].read_text();rows=coordination.rows(text);owner=coordination.find_session(rows,OWNER)
        if bad=='owner-scope':owner.claims=[x for x in owner.claims if x.startswith('prep-share:')]+[str(shared['repo']/'elsewhere/**')]
        else:owner.status='released'
        shared['board'].write_text(coordination.replace_table(text,rows))
    if bad=='public':
        import team_contract
        monkeypatch.setattr(team_contract,'registry_binding',lambda *a,**k:{'repository':{'audience':'shared'}})
        monkeypatch.setattr(team_contract,'require_registry',lambda *a,**k:{'allowed':True})
    if bad=='marker':(shared['repo']/'profiles/meeting-prep/.owner.json').write_text('{"schema":1,"workspace":"other"}')
    before=files(shared);board=shared['board'].read_bytes()
    with pytest.raises((ValueError,RuntimeError,FileNotFoundError)):write(shared,g,**options)
    assert files(shared)==before
    assert shared['board'].read_bytes()==board


def test_shared_prep_append_cas_preserves_concurrent_update(shared,monkeypatch):
    target=shared['repo']/'meeting-preps/meeting.md';target.write_text('Original\n');target.chmod(0o600)
    old=hashlib.sha256(target.read_bytes()).hexdigest()
    one=grant(shared,monkeypatch,operation='append',before=old)
    two=grant(shared,monkeypatch,operation='append',before=old)
    assert write(shared,one,'First\n')['status']=='committed'
    before=files(shared)
    with pytest.raises((ValueError,RuntimeError)):write(shared,two,'Second\n')
    assert files(shared)==before
    assert target.read_text()=='Original\nFirst\n'


def test_shared_prep_does_not_authorize_generic_replacement(shared,monkeypatch):
    target=shared['repo']/'meeting-preps/meeting.md';target.write_text('Original\n');target.chmod(0o600)
    old=hashlib.sha256(target.read_bytes()).hexdigest();g=grant(shared,monkeypatch,operation='append',before=old)
    payload=dict(shared['actor']['native_payload'],meeting_prep_share={'id':g['id'],'workspace':'fixture'})
    before=files(shared)
    with pytest.raises(RuntimeError,match='append only'):
        prep.records.apply(target.parent,[{'file':target.name,'edits':[{'op':'replace','anchor':'Original','replacement':'Altered'}]}],board=shared['board'],native_payload=payload)
    assert files(shared)==before


def test_shared_prep_grant_is_not_an_exclusive_path_claim(shared,monkeypatch):
    grant(shared,monkeypatch)
    rows=coordination.rows(shared['board'].read_text());contributor=coordination.find_session(rows,SEAT)
    assert coordination._outside_claim(contributor,shared['repo'],['meeting-preps/meeting.md'])==['meeting-preps/meeting.md']
    with pytest.raises(ValueError):
        run_admission.admit_paths(shared['board'],'alpha',shared['project'],[shared['repo']/'meeting-preps/meeting.md'],shared['actor']['native_payload'])
    assert run_admission.admit_paths(shared['board'],'alpha',shared['project'],[shared['plan']],shared['actor']['native_payload'])


def test_shared_prep_simultaneous_writers_serialize_without_lost_update(shared,monkeypatch,tmp_path):
    import subprocess
    target=shared['repo']/'meeting-preps/meeting.md';target.write_text('Original\n');target.chmod(0o600)
    old=hashlib.sha256(target.read_bytes()).hexdigest()
    grants=[grant(shared,monkeypatch,operation='append',before=old) for _ in range(2)]
    payload=tmp_path/'native.json';payload.write_text(json.dumps(shared['actor']['native_payload']))
    procs=[]
    for index,g in enumerate(grants):
        body=tmp_path/('append-'+str(index)+'.txt');body.write_text('Contribution '+str(index)+'\n')
        argv=[sys.executable,'-B',str(PREP),'write-pack','--context-repo',str(shared['repo']),
              '--workspace','fixture','--artifact','meeting.md','--board',str(shared['board']),
              '--grant-id',g['id'],'--native-payload',str(payload),'--operation','append',
              '--before',old,'--text-file',str(body)]
        procs.append(subprocess.Popen(argv,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True))
    outcomes=[]
    for index,proc in enumerate(procs):
        out,err=proc.communicate(timeout=25)
        (tmp_path/('writer-'+str(index)+'.json')).write_text(json.dumps({'pid':proc.pid,'returncode':proc.returncode,'stdout':out,'stderr':err}))
        outcomes.append(proc.returncode)
    assert sorted(outcomes)==[0,2]
    assert target.read_text() in ('Original\nContribution 0\n','Original\nContribution 1\n')


def test_shared_prep_interruption_recovery_rechecks_recipient(shared,monkeypatch):
    target=shared['repo']/'meeting-preps/meeting.md';target.write_text('Original\n');target.chmod(0o600)
    g=grant(shared,monkeypatch,operation='append',before=hashlib.sha256(target.read_bytes()).hexdigest())
    real=prep.records.os.replace
    def interrupted(src,dst):
        if Path(dst)==target:raise OSError('synthetic effect interruption')
        return real(src,dst)
    with monkeypatch.context() as patch:
        patch.setattr(prep.records.os,'replace',interrupted)
        with pytest.raises(OSError,match='interruption'):write(shared,g)
    assert target.read_text()=='Original\n'
    original=shared['board'].read_text();rows=coordination.rows(original)
    coordination.find_session(rows,OWNER).status='released'
    shared['board'].write_text(coordination.replace_table(original,rows));retained=files(shared)
    payload=dict(shared['actor']['native_payload'],meeting_prep_share={'id':g['id'],'workspace':'fixture'})
    with pytest.raises(RuntimeError):prep.records.recover(target.parent,board=shared['board'],native_payload=payload)
    assert files(shared)==retained
    shared['board'].write_text(original)
    assert prep.records.recover(target.parent,board=shared['board'],native_payload=payload)['status']=='committed'
    assert target.read_text()=='Original\nNew material\n'


def test_shared_prep_raw_claim_cannot_mint_grant(shared,monkeypatch):
    from types import SimpleNamespace
    grant(shared,monkeypatch)
    row=coordination.find_session(coordination.rows(shared['board'].read_text()),OWNER)
    marker=next(c for c in row.claims if c.startswith('prep-share:'))
    before=shared['board'].read_bytes()
    assert coordination.command_claim(SimpleNamespace(area=[marker]))==10
    assert shared['board'].read_bytes()==before


def test_prep_grant_cannot_authorize_registry_or_memory_home(shared, monkeypatch):
    from test_run_admission import git
    import context_edit
    index = shared['repo'] / 'projects/index.yaml'
    git(shared['repo'], 'add', 'projects/index.yaml')
    git(shared['repo'], 'commit', '-m', 'Fixture registry')
    g = grant(shared, monkeypatch)
    payload = dict(shared['actor']['native_payload'], meeting_prep_share={'id': g['id'], 'workspace': 'fixture'})
    before = files(shared)
    with pytest.raises(RuntimeError, match='prep|scope|authority|identity'):
        context_edit.patch_registry(shared['project'], 'alpha', {'note': 'must refuse'},
            hashlib.sha256(index.read_bytes()).hexdigest(), board=shared['board'], native_payload=payload)
    assert files(shared) == before
    with pytest.raises(RuntimeError, match='native-memory'):
        prep.records.apply(shared['repo'] / 'meeting-preps', [{'file': 'meeting.md', 'create': {'text': 'must refuse\n', 'mode': 0o600}}],
            board=shared['board'], native_payload=payload, memory_home={'family': 'personal'})
    assert files(shared) == before
    assert write(shared, g)['status'] == 'committed'

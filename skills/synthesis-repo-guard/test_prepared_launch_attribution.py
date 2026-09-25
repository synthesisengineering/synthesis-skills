"""Prepared-grant attribution uses real journals; native input is synthetic."""
import importlib.util
from pathlib import Path
import sys
import pytest

SCRIPTS=Path(__file__).resolve().parents[1]/'synthesis-autopilot/scripts'
sys.path.insert(0,str(SCRIPTS))
from test_controller import engine,facade,world,attribute_recovery_fixture
from test_prepared_native_launch import prepared,TOKEN,synthetic_transport


def owner():
    spec=importlib.util.spec_from_file_location('prepared_guard_fixture',Path(__file__).with_name('checkpoint_sync.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('damage',['token','run','permit','revision'])
def test_guessed_grant_never_attributes_any_bytes(facade,world,damage):
    import prepared_native_launch as launch
    state=prepared(facade,world);attribute_recovery_fixture(world)
    args={'project':world['project'],'run_id':state['run_id'],'permit_id':'permit1','token':TOKEN,
        'revision':state['revision'],'guard_root':world['runtime'].parent/'repo-guard'}
    if damage=='token':args['token']='guessed-token'
    elif damage=='run':args['run_id']='guessed-run'
    elif damage=='permit':args['permit_id']='guessed-permit'
    else:args['revision']-=1
    before={str(p):p.read_bytes() for p in args['guard_root'].rglob('*') if p.is_file()}
    with pytest.raises((ValueError,OSError)):owner().record_prepared_native_launch(**args)
    after={str(p):p.read_bytes() for p in args['guard_root'].rglob('*') if p.is_file() and p.name!='lifecycle.lock'}
    assert after==before


def test_real_delegated_consumer_preserves_foreign_records(facade,world,monkeypatch):
    import prepared_native_launch as launch
    state=prepared(facade,world);attribute_recovery_fixture(world)
    guard=world['runtime'].parent/'repo-guard';foreign=guard/'pending/foreign.json'
    raw=b'{"schema_version":2,"session_id":"foreign-native","paths":[],"private":"retained"}\n'
    foreign.write_bytes(raw)
    synthetic_transport(monkeypatch,world)
    launch.execute(world['project'],state['run_id'],'permit1',TOKEN,runtime_root=world['runtime'])
    assert foreign.read_bytes()==raw


def test_foreign_manifest_identity_collision_is_preserved(facade,world,monkeypatch):
    import hashlib,json
    import prepared_native_launch as launch
    state=prepared(facade,world);attribute_recovery_fixture(world)
    guard=world['runtime'].parent/'repo-guard'
    target=guard/'pending'/((hashlib.sha256(world['actor']['native_payload']['session_id'].encode()).hexdigest())+'.json')
    raw=b'{"schema_version":2,"session_id":"foreign","paths":[],"private":"retained"}\n';target.write_bytes(raw)
    calls=synthetic_transport(monkeypatch,world)
    with pytest.raises(ValueError,match='foreign'):launch.execute(world['project'],state['run_id'],'permit1',TOKEN,runtime_root=world['runtime'])
    assert target.read_bytes()==raw and calls==[]


@pytest.mark.parametrize('location',['outside-run','inside-run-unrelated'])
def test_delegated_attribution_refuses_cross_path_side_effect(facade,world,monkeypatch,location):
    import prepared_native_launch as launch
    import run_state
    state=prepared(facade,world);attribute_recovery_fixture(world)
    calls=synthetic_transport(monkeypatch,world)
    original=run_state._project
    target=(world['project']/'unrelated.txt') if location=='outside-run' else run_state._home(world['project'],state['run_id'])/'unrelated.txt'
    def concurrent(project,current):
        original(project,current);target.write_text('Different producer edit, never attribute to grant.\n')
    monkeypatch.setattr(run_state,'_project',concurrent)
    with pytest.raises(ValueError,match='cross-path'):
        launch.execute(world['project'],state['run_id'],'permit1',TOKEN,runtime_root=world['runtime'])
    assert target.read_text().startswith('Different producer') and not calls


# Permanent regressions retained from the same-round independent review.
import hashlib, json


@pytest.mark.parametrize('location', ['human-plan', 'current-projection', 'outside-run-control'])
def test_prepared_attribution_does_not_claim_concurrent_foreign_bytes(facade, world, monkeypatch, location):
    import prepared_native_launch as owner
    import run_state
    state = prepared(facade, world)
    attribute_recovery_fixture(world)
    original_project = run_state._project
    home = run_state._home(world['project'], state['run_id'])
    target = {'human-plan': world['plan'], 'current-projection': home/'current.json',
              'outside-run-control': world['project']/'foreign-note.txt'}[location]
    marker = 'Independent concurrent foreign edit; no grant authority.\n'
    def actual_projection_then_foreign_write(project, current):
        original_project(project, current)
        if location == 'human-plan':
            target.write_text(target.read_text() + marker)
        elif location == 'current-projection':
            value = json.loads(target.read_text())
            value['foreign_unadmitted_projection'] = marker
            target.write_text(json.dumps(value))
        else:
            target.write_text(marker)
    monkeypatch.setattr(run_state, '_project', actual_projection_then_foreign_write)
    guard = world['runtime'].parent/'repo-guard'
    preserved = {str(p): p.read_bytes() for p in guard.rglob('*.json')}
    own = guard/'pending'/(hashlib.sha256(world['actor']['native_payload']['session_id'].encode()).hexdigest()+'.json')
    refused = None
    try:
        owner._step(world['project'], state['run_id'], 'permit1', TOKEN, 'reserve', runtime_root=world['runtime'])
    except (ValueError, OSError) as error:
        refused = str(error)
    for path, raw in preserved.items():
        assert Path(path).read_bytes() == raw
    assert marker.strip() in target.read_text()
    attributed = json.loads(own.read_text()).get('path_hashes', {}).get(str(target)) if own.exists() else None
    actual = hashlib.sha256(target.read_bytes()).hexdigest()
    print(json.dumps({'location': location, 'refusal': refused, 'own_manifest_created': own.exists(),
                      'foreign_bytes_claimed': attributed == actual,
                      'journal_revision': run_state.load_run(world['project'], state['run_id'])['revision']}))
    assert attributed != actual, 'prepared grant attributed a concurrent foreign write as its own projection'
    assert refused is not None, 'non-derived edit must refuse attribution instead of claiming path-name ownership'


"""Bounded retention tests use generated native records, never user transcripts."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest
import test_run_state as run_fixtures
from test_run_state import create, command
import test_observation_bridge as observation_fixtures
from test_observation_bridge import enroll, observe, append, pair

# Pytest discovers these imported fixtures by their public fixture names.
engine = run_fixtures.engine
world = run_fixtures.world
bridge = observation_fixtures.bridge


def test_native_history_crosses_snapshot_limit_and_recovers_exactly(engine, bridge, world):
    state = enroll(engine, world, create(engine, world))
    first_ids = None
    for page in range(16):
        for index in range(90):
            append(world, *pair(world, f'page-{page}-call-{index}', 'synthetic result'))
        state = observe(engine, world, state)
        if first_ids is None:
            first_ids = list(state['extensions']['native_observations']['event_index'])[:2]
    assert len(engine._json(state)) > engine.MAX_JSON_BYTES
    assert engine.load_run(world['project'], state['run_id']) == state
    context = engine.inspect_context(state, world['actor'])
    consumed = context['current_native_events'](first_ids)
    assert consumed['status'] == 'current'
    assert [row['event_id'] for row in consumed['events']] == first_ids
    assert state['extensions']['native_observations']['sources']['root']['cursor']['first_gap'] is None
    import operator_status
    view = operator_status.inspect_project(world['project'], state['run_id'])['runs'][0]
    # Closed source-line diagnostics survive the bounded hosted report without
    # exposing arbitrary operator messages, paths or retained state.
    if view['currentness'] != 'JOURNAL_VERIFIED_RECORDED_STATE':
        if view.get('diagnostics') == ['journal verification time budget exhausted; no partial state is accepted']:
            pytest.fail('OPERATOR_JOURNAL_TIME_BUDGET', pytrace=False)
        pytest.fail('OPERATOR_OTHER_CURRENTNESS_REFUSAL', pytrace=False)
    assert view['currentness'] == 'JOURNAL_VERIFIED_RECORDED_STATE', view


def big_state(engine, world):
    state = create(engine, world)
    def grow(state, payload, context):
        state['extensions']['synthetic_history'] = {f'entry-{i}': 'retained-' + str(i) + ':' + 'x' * 1500 for i in range(3000)}
        return state
    engine.register_command('fixture.grow', grow, allowed_fields=('extensions',))
    return state


def test_atomic_append_replay_projection_rebuild_and_operator(engine, world):
    import operator_status
    state = big_state(engine, world)
    old = {p.name: p.read_bytes() for p in (engine._home(world['project'], state['run_id']) / 'events').iterdir()}
    changed = command(engine, world, state, 'fixture.grow', {}, command_id='grow')
    home = engine._home(world['project'], changed['run_id'])
    assert len(engine._json(changed)) > engine.MAX_JSON_BYTES
    assert command(engine, world, state, 'fixture.grow', {}, command_id='grow') == changed
    assert engine.load_run(world['project'], state['run_id']) == changed
    for name, data in old.items(): assert (home / 'events' / name).read_bytes() == data
    (home / 'current.json').write_text('broken projection')
    assert engine.rebuild_projections(world['project'], changed['run_id'], actor=world['actor']) == changed
    assert engine._read(home / 'current.json') == changed
    report = operator_status.inspect_project(world['project'], changed['run_id'])['runs'][0]
    assert report['currentness'] == 'JOURNAL_VERIFIED_RECORDED_STATE'
    assert report['current_acceptance'] == 'UNKNOWN'
    assert report['status'] == 'working'


@pytest.mark.parametrize('fault', ['missing', 'corrupt', 'symlink', 'directory', 'oversize'])
def test_every_referenced_block_is_required_and_authenticated(engine, world, fault):
    import journal_storage as store
    state = big_state(engine, world)
    command(engine, world, state, 'fixture.grow', {})
    home = engine._home(world['project'], state['run_id'])
    event = json.loads((home / 'events/000000000002.json').read_text())
    block = home / 'state-blocks/v1' / (event['root'] + '.json')
    block.unlink()
    if fault == 'corrupt': block.write_text('["leaf",{}]')
    elif fault == 'symlink': block.symlink_to(world['plan'])
    elif fault == 'directory': block.mkdir()
    elif fault == 'oversize': block.write_bytes(b'x' * (store.MAX_BLOCK_BYTES + 1))
    with pytest.raises(ValueError): engine.load_run(world['project'], state['run_id'])


@pytest.mark.parametrize('fault', ['logical', 'store_bytes', 'store_entries'])
def test_capacity_refusal_preserves_last_committed_state(engine, world, monkeypatch, fault):
    import journal_storage as store
    state = big_state(engine, world)
    before = engine._read(engine._home(world['project'], state['run_id']) / 'current.json')
    if fault == 'logical': monkeypatch.setattr(store, 'MAX_LOGICAL_BYTES', 2 * 1024 * 1024)
    elif fault == 'store_bytes': monkeypatch.setattr(store, 'MAX_STORE_BYTES', 1)
    else: monkeypatch.setattr(store, 'MAX_STORE_ENTRIES', 1)
    with pytest.raises(ValueError): command(engine, world, state, 'fixture.grow', {})
    assert engine.load_run(world['project'], state['run_id']) == state == before
    assert engine._read(engine._home(world['project'], state['run_id']) / 'current.json') == before


@pytest.mark.parametrize('phase', ['before_event', 'after_event'])
def test_interrupted_append_recovers_without_replaying_effects(engine, world, monkeypatch, phase):
    state = big_state(engine, world)
    original = engine._write
    def interrupt(path, raw):
        if (phase == 'before_event' and Path(path).name == '000000000002.json'
                or phase == 'after_event' and Path(path).name == 'current.json'):
            raise OSError('synthetic power loss')
        return original(path, raw)
    monkeypatch.setattr(engine, '_write', interrupt)
    with pytest.raises(OSError): command(engine, world, state, 'fixture.grow', {}, command_id='grow')
    recovered = engine.load_run(world['project'], state['run_id'])
    assert recovered['revision'] == (1 if phase == 'before_event' else 2)
    monkeypatch.setattr(engine, '_write', original)
    retried = command(engine, world, state, 'fixture.grow', {}, command_id='grow')
    assert retried['revision'] == 2
    assert engine.load_run(world['project'], state['run_id']) == retried


def test_concurrent_compare_and_swap_still_has_one_winner(engine, world):
    from concurrent.futures import ThreadPoolExecutor
    state = big_state(engine, world)
    def mutate(identity):
        try: return command(engine, world, state, 'fixture.grow', {}, command_id=identity)
        except ValueError: return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(mutate, ['one', 'two']))
    assert len([r for r in results if r is not None]) == 1
    assert engine.load_run(world['project'], state['run_id'])['revision'] == 2


def test_codec_nonascii_container_types_and_bounded_component(tmp_path):
    import journal_storage as store
    home = tmp_path / 'resources/autopilot-runs/01990000-0000-7000-8000-000000000777'
    path = home / 'events/000000000001.json'; path.parent.mkdir(parents=True)
    value = {'state': {'unrelated': 'λ' * 700000, 'extensions': {'native_observations': {'latest_batch': {
        'events': [{'data': ['α', None, True, 2.5, {'nested': 42}]}]}}}}}
    raw, blocks = store.encode(value); store.materialize(home, blocks); path.write_bytes(raw)
    assert store.decode(path, json.loads(raw)) == value
    selected, used = store.component(path, ('state', 'extensions', 'native_observations', 'latest_batch'), max_bytes=128 * 1024)
    assert selected == value['state']['extensions']['native_observations']['latest_batch']
    assert used < 128 * 1024
    with pytest.raises(ValueError): store.component(path, ('state', 'unrelated'), max_bytes=128 * 1024)
    with pytest.raises(ValueError): store.decode(tmp_path / 'not-a-run.json', json.loads(raw))


def test_block_namespace_symlink_and_existing_collision_are_refused(tmp_path):
    import journal_storage as store
    home = tmp_path / 'run'; home.mkdir()
    raw, blocks = store.encode({'value': 'x' * (2 * 1024 * 1024)})
    foreign = tmp_path / 'foreign'; foreign.mkdir()
    (home / 'state-blocks').symlink_to(foreign, target_is_directory=True)
    with pytest.raises(OSError): store.materialize(home, blocks)
    assert list(foreign.iterdir()) == []
    (home / 'state-blocks').unlink()
    store.materialize(home, blocks)
    digest = next(iter(blocks)); path = home / 'state-blocks/v1' / (digest + '.json')
    path.write_bytes(b'changed')
    with pytest.raises(ValueError): store.materialize(home, blocks)


def test_descriptor_and_expansion_bombs_are_refused(tmp_path, monkeypatch):
    import journal_storage as store
    home = tmp_path / 'resources/autopilot-runs/01990000-0000-7000-8000-000000000777'
    path = home / 'events/000000000001.json'; path.parent.mkdir(parents=True)
    raw, blocks = store.encode({'value': 'x' * (2 * 1024 * 1024)}); store.materialize(home, blocks)
    desc = json.loads(raw)
    for field, value in [('root', '../escape'), ('sha256', '0' * 64), ('logical_bytes', 1), ('logical_bytes', store.MAX_LOGICAL_BYTES + 1)]:
        with pytest.raises(ValueError): store.decode(path, {**desc, field: value})
    monkeypatch.setattr(store, 'MAX_BLOCKS', 2)
    with pytest.raises(ValueError): store.decode(path, desc)


def test_storage_digest_does_not_replace_event_chain_authentication(engine, world):
    import journal_storage as store
    state = big_state(engine, world)
    command(engine, world, state, 'fixture.grow', {})
    home = engine._home(world['project'], state['run_id'])
    path = home / 'events/000000000002.json'
    value = dict(engine._read(path))
    value['state']['status'] = 'completed'
    # A replacement storage descriptor and its blocks cannot validate a changed
    # logical event whose original chain digest no longer matches the body.
    raw, blocks = store.encode(value); store.materialize(home, blocks); path.write_bytes(raw)
    with pytest.raises(ValueError, match='integrity'): engine.load_run(world['project'], state['run_id'])


def test_file_replacement_during_verified_read_is_refused(tmp_path, monkeypatch):
    import journal_storage as store
    target = tmp_path / 'file.json'; target.write_text('{}')
    other = tmp_path / 'replacement.json'; other.write_text('[]')
    original = store.os.fstat; calls = 0
    def replaced(fd):
        nonlocal calls
        calls += 1
        if calls == 2: other.replace(target)
        return original(fd)
    monkeypatch.setattr(store.os, 'fstat', replaced)
    with pytest.raises(ValueError, match='changed'): store.read_regular(target, 20)


def test_identical_block_installers_do_not_replace_existing_content(tmp_path):
    import journal_storage as store
    from concurrent.futures import ThreadPoolExecutor
    home = tmp_path / 'run'; home.mkdir()
    _, blocks = store.encode({'value': ['x' * 4000 for _ in range(400)]})
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: store.materialize(home, blocks), range(2)))
    directory = home / 'state-blocks/v1'
    assert {p.stem for p in directory.iterdir()} == set(blocks)
    for digest, raw in blocks.items(): assert (directory / (digest + '.json')).read_bytes() == raw


# Causal regressions from the independent journal-storage review.
import os
import journal_storage as storage

def encoded(tmp_path,value):
 home=tmp_path/'resources/autopilot-runs/01990000-0000-7000-8000-000000000777';home.mkdir(parents=True);path=home/'current.json';raw,blocks=storage.encode(value);storage.materialize(home,blocks);path.write_bytes(raw);return path,json.loads(raw),value


def independent_value():
 return {'left':{'items':[1]},'right':{'items':[1]},'padding':'x'*(2*1024*1024)}


def test_decoder_retains_independent_json_objects(tmp_path):
 path,descriptor,value=encoded(tmp_path,independent_value());decoded=storage.decode(path,descriptor);assert decoded==value
 decoded['left']['items'].append(2);assert decoded['right']==value['right']


def test_selected_component_retains_independent_json_objects(tmp_path):
 path,_,value=encoded(tmp_path,{'batch':independent_value()});selected,used=storage.component(path,('batch',),max_bytes=8*1024*1024);assert selected==value['batch']
 selected['left']['items'].append(2);assert selected['right']==value['batch']['right']


def grow(engine,world):
 state=create(engine,world)
 def make(state,payload,context):state['extensions']['fixture_history']=independent_value();return state
 engine.register_command('fixture.large',make,allowed_fields=('extensions',))
 return command(engine,world,state,'fixture.large',{})


def test_owner_mutation_cannot_change_equal_sibling_records(engine,world):
 state=grow(engine,world)
 def touch(state,payload,context):state['extensions']['fixture_history']['left']['items'].append(2);return state
 engine.register_command('fixture.touch',touch,allowed_fields=('extensions',))
 state=command(engine,world,state,'fixture.touch',{})
 assert state['extensions']['fixture_history']['right']['items']==[1]
 assert engine.load_run(world['project'],state['run_id'])==state


def test_new_storage_directories_are_durable_before_use(tmp_path,monkeypatch):
 home=tmp_path/'run';home.mkdir();created_parents=[];synced=[];mkdir=storage.os.mkdir;fsync=storage.os.fsync
 def make(path,*args,**kwargs):
  result=mkdir(path,*args,**kwargs)
  fd=kwargs.get('dir_fd')
  if fd is not None:
   info=os.fstat(fd);created_parents.append((info.st_dev,info.st_ino))
  return result
 def flush(fd):
  info=os.fstat(fd);synced.append((info.st_dev,info.st_ino));return fsync(fd)
 monkeypatch.setattr(storage.os,'mkdir',make);monkeypatch.setattr(storage.os,'fsync',flush)
 raw,blocks=storage.encode({'history':'x'*(2*1024*1024)});storage.materialize(home,blocks)
 assert created_parents
 assert set(created_parents)<=set(synced), {'unflushed_new_directory_parents':list(set(created_parents)-set(synced))}


@pytest.mark.parametrize('damage',['missing','corrupt','symlink','fifo','ancestor-link','oversized'])
def test_selected_component_refuses_unsafe_storage(tmp_path,damage):
 path,descriptor,_=encoded(tmp_path,{'batch':independent_value()});directory=path.parent/'state-blocks/v1';root=directory/(descriptor['root']+'.json');retained=tmp_path/'retained';retained.write_bytes(root.read_bytes())
 if damage=='ancestor-link':
  directory.rename(directory.with_name('moved'));directory.symlink_to(directory.with_name('moved'),target_is_directory=True)
 else:
  root.unlink()
  if damage=='corrupt':root.write_bytes(b'[]')
  elif damage=='symlink':root.symlink_to(retained)
  elif damage=='fifo':os.mkfifo(root)
  elif damage=='oversized':root.write_bytes(b'x'*(storage.MAX_BLOCK_BYTES+1))
 with pytest.raises((OSError,ValueError)):storage.component(path,('batch',),max_bytes=8*1024*1024)


@pytest.mark.parametrize('limit',['bytes','entries'])
def test_orphan_blocks_count_toward_capacity_without_advancing_snapshot(tmp_path,monkeypatch,limit):
 path,descriptor,value=encoded(tmp_path,independent_value());before=path.read_bytes();directory=path.parent/'state-blocks/v1';orphan=directory/('f'*64+'.json');orphan.write_bytes(b'{}')
 _,blocks=storage.encode({'other':'y'*(2*1024*1024)})
 if limit=='bytes':monkeypatch.setattr(storage,'MAX_STORE_BYTES',sum(p.stat().st_size for p in directory.iterdir()))
 else:monkeypatch.setattr(storage,'MAX_STORE_ENTRIES',len(list(directory.iterdir())))
 with pytest.raises(ValueError):storage.materialize(path.parent,blocks)
 assert path.read_bytes()==before;assert storage.decode(path,descriptor)==value;assert orphan.read_bytes()==b'{}'




def test_native_cursor_is_not_advanced_when_projection_capacity_refuses(engine, bridge, world, monkeypatch):
    import native_observations
    state = enroll(engine, world, create(engine, world))
    home = engine._home(world['project'], state['run_id'])
    before = {p.name: p.read_bytes() for p in (home / 'events').iterdir()}
    cursor = deepcopy(state['extensions']['native_observations']['sources']['root']['cursor'])
    append(world, *pair(world, 'capacity-refusal', 'actual synthetic response'))
    with monkeypatch.context() as bounded:
        bounded.setattr(native_observations, 'MAX_PROJECTION_BYTES', 1)
        with pytest.raises(ValueError, match='storage bound'):
            observe(engine, world, state)
    assert engine.load_run(world['project'], state['run_id']) == state
    assert state['extensions']['native_observations']['sources']['root']['cursor'] == cursor
    assert {p.name: p.read_bytes() for p in (home / 'events').iterdir()} == before
    changed = observe(engine, world, state)
    assert changed['extensions']['native_observations']['sources']['root']['cursor'] != cursor


def test_new_directory_fsync_failure_prevents_event_commit(engine, world, monkeypatch):
    state = big_state(engine, world)
    home = engine._home(world['project'], state['run_id'])
    before = {p.name: p.read_bytes() for p in (home / 'events').iterdir()}
    signature = (home.stat().st_dev, home.stat().st_ino)
    real_fsync = storage.os.fsync
    def fail_parent(fd):
        info = os.fstat(fd)
        if (info.st_dev, info.st_ino) == signature:
            raise OSError('Synthetic new-directory durability refusal')
        return real_fsync(fd)
    monkeypatch.setattr(storage.os, 'fsync', fail_parent)
    with pytest.raises(OSError, match='durability refusal'):
        command(engine, world, state, 'fixture.grow', {})
    assert engine.load_run(world['project'], state['run_id']) == state
    assert {p.name: p.read_bytes() for p in (home / 'events').iterdir()} == before


def test_operator_refuses_if_final_projection_read_exhausts_same_time_budget(engine, world, monkeypatch):
    import operator_status
    state = create(engine, world)
    now = [0.0]
    real_read = engine._read
    def slow_projection(path):
        value = real_read(path)
        if Path(path).name == 'current.json':
            now[0] = operator_status.MAX_JOURNAL_SECONDS + 0.01
        return value
    monkeypatch.setattr(operator_status.time, 'monotonic', lambda: now[0])
    monkeypatch.setattr(engine, '_read', slow_projection)
    result = operator_status.inspect_project(world['project'], state['run_id'])
    assert operator_status.MAX_JOURNAL_SECONDS == 2.0
    assert result['runs'][0]['currentness'] != 'JOURNAL_VERIFIED_RECORDED_STATE'
    assert 'time budget' in str(result)


@pytest.mark.parametrize('gap', ['parent-directory', 'linked-block'])
def test_retry_flushes_prior_unconfirmed_directory_entries(tmp_path, monkeypatch, gap):
    home=tmp_path/'run';home.mkdir()
    directory=home/'state-blocks/v1'
    _,blocks=storage.encode({'data':'x'*(2*1024*1024)})
    real=storage.os.fsync
    failed=[]
    def interrupt(fd):
        info=os.fstat(fd)
        target=home if gap=='parent-directory' else directory
        ready = gap == 'parent-directory' or directory.exists() and sum(p.name.endswith('.json') for p in directory.iterdir()) == len(blocks)
        if ready and target.exists() and (info.st_dev,info.st_ino)==(target.stat().st_dev,target.stat().st_ino):
            failed.append((info.st_dev,info.st_ino));raise OSError('Synthetic failed durability barrier')
        return real(fd)
    monkeypatch.setattr(storage.os,'fsync',interrupt)
    with pytest.raises(OSError,match='durability barrier'):storage.materialize(home,blocks)
    seen=[]
    def record(fd):
        info=os.fstat(fd);seen.append((info.st_dev,info.st_ino));return real(fd)
    monkeypatch.setattr(storage.os,'fsync',record)
    storage.materialize(home,blocks)
    assert set(failed)<=set(seen)


# Publication and capacity races reproduced from full-CI failure.
"""Causal journal-store concurrency fixtures; finite joins, real inode operations."""
import stat,threading,time
from concurrent.futures import ThreadPoolExecutor
import journal_storage as store


def one_block(text='fixture'):
    raw=store.canonical(['leaf',text])+b'\n'
    return {hashlib.sha256(raw).hexdigest():raw}


def test_identical_publication_cleanup_does_not_invalidate_second_installer(tmp_path,monkeypatch):
    home=tmp_path/'run';home.mkdir();blocks=one_block();digest=next(iter(blocks))
    published=threading.Event();reader_started=threading.Event();unlinked=threading.Event();local=threading.local()
    real_link=store.os.link;real_unlink=store.os.unlink;real_fstat=store.os.fstat;observed=[]
    def link(src,dst,*args,**kwargs):
        result=real_link(src,dst,*args,**kwargs)
        if getattr(local,'role',None)=='publisher':
            published.set();reader_started.wait(2)
        return result
    def unlink(path,*args,**kwargs):
        result=real_unlink(path,*args,**kwargs)
        if getattr(local,'role',None)=='publisher' and str(path).startswith('.stage-'):unlinked.set()
        return result
    def fstat(fd):
        before=real_fstat(fd)
        if getattr(local,'role',None)=='second' and stat.S_ISREG(before.st_mode) and not getattr(local,'checked',False):
            local.checked=True;reader_started.set()
            assert unlinked.wait(3),'publisher cleanup did not terminate'
            after=real_fstat(fd);observed.append((before.st_nlink,after.st_nlink,before.st_ctime_ns!=after.st_ctime_ns))
        return before
    monkeypatch.setattr(store.os,'link',link);monkeypatch.setattr(store.os,'unlink',unlink);monkeypatch.setattr(store.os,'fstat',fstat)
    def install(role):
        local.role=role
        if role=='second':assert published.wait(3)
        store.materialize(home,blocks)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first=pool.submit(install,'publisher');second=pool.submit(install,'second')
        first.result(timeout=6);second.result(timeout=6)
    directory=home/'state-blocks/v1'
    assert [p.name for p in directory.iterdir()]==[digest+'.json']
    assert (directory/(digest+'.json')).read_bytes()==blocks[digest]
    assert (directory/(digest+'.json')).stat().st_nlink==1
    print({'observed_link_transition':observed})


@pytest.mark.parametrize('bound',['entries','bytes'])
def test_disjoint_writers_cannot_both_spend_the_same_store_capacity(tmp_path,monkeypatch,bound):
    home=tmp_path/'run';home.mkdir();directory=home/'state-blocks/v1';directory.mkdir(parents=True)
    left={**one_block('left-a'),**one_block('left-b')};right={**one_block('right-a'),**one_block('right-b')};barrier=threading.Barrier(2);real_scan=store.os.scandir
    # Reserve room for one two-block batch and its transient hardlink,
    # but not both four-block batches spending the same scanned capacity.
    if bound=='entries':monkeypatch.setattr(store,'MAX_STORE_ENTRIES',3)
    else:monkeypatch.setattr(store,'MAX_STORE_BYTES',3*max(len(x) for x in [*left.values(),*right.values()]))
    class Scan:
        def __init__(self,fd):self.inner=real_scan(fd)
        def __enter__(self):return self.inner.__enter__()
        def __exit__(self,*args):
            result=self.inner.__exit__(*args)
            try:barrier.wait(timeout=2)
            except threading.BrokenBarrierError:pass
            return result
    monkeypatch.setattr(store.os,'scandir',Scan)
    def install(blocks):
        try:store.materialize(home,blocks);return 'installed'
        except ValueError as exc:
            assert 'capacity' in str(exc);return 'refused'
    with ThreadPoolExecutor(max_workers=2) as pool:
        a=pool.submit(install,left);b=pool.submit(install,right)
        results=[a.result(timeout=6),b.result(timeout=6)]
    assert sorted(results)==['installed','refused']
    assert len(list(directory.iterdir()))==2


def test_reader_still_refuses_same_size_rewrite_with_restored_mtime(tmp_path,monkeypatch):
    path=tmp_path/'record';path.write_bytes(b'original');before=path.stat();real=store.os.fstat;calls=0
    def tamper(fd):
        nonlocal calls
        calls+=1
        if calls==2:
            path.write_bytes(b'modified');os.utime(path,ns=(before.st_atime_ns,before.st_mtime_ns))
        return real(fd)
    monkeypatch.setattr(store.os,'fstat',tamper)
    with pytest.raises(ValueError,match='changed'):store.read_regular(path,20)

@pytest.mark.parametrize('reader',['decode','component','regular'])
def test_reader_wait_is_bounded_and_release_restores_actual_read(tmp_path,monkeypatch,reader):
    import fcntl
    monkeypatch.setattr(store,'INLINE_BYTES',0)
    home=tmp_path/'resources/autopilot-runs/01990000-0000-7000-8000-000000000777'
    home.mkdir(parents=True);path=home/'current.json';value={'batch':{'value':1}}
    raw,blocks=store.encode(value);store.materialize(home,blocks);path.write_bytes(raw)
    directory=home/'state-blocks/v1';fd=os.open(directory,os.O_RDONLY|os.O_DIRECTORY)
    def read():
        if reader=='decode':return store.decode(path,json.loads(raw))
        if reader=='component':return store.component(path,('batch',),max_bytes=4096)[0]
        return store.read_regular(directory/(next(iter(blocks))+'.json'),4096)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);start=time.monotonic()
        with pytest.raises(ValueError,match='bounded lock wait'):read()
        assert time.monotonic()-start<0.5
        assert path.read_bytes()==raw
    finally:os.close(fd)
    expected=value if reader=='decode' else value['batch'] if reader=='component' else next(iter(blocks.values()))
    assert read()==expected


@pytest.mark.parametrize('exclusive',[False,True])
def test_lock_polling_has_an_attempt_bound_even_if_clock_stalls(tmp_path,monkeypatch,exclusive):
    import errno
    calls=[]
    monkeypatch.setattr(store,'STORE_WRITE_LOCK_SECONDS',0.02)
    monkeypatch.setattr(store,'STORE_READ_LOCK_SECONDS',0.02)
    monkeypatch.setattr(store.time,'monotonic',lambda:0)
    monkeypatch.setattr(store.time,'sleep',lambda _:None)
    def busy(fd,operation):calls.append(operation);raise BlockingIOError(errno.EWOULDBLOCK,'synthetic contention')
    monkeypatch.setattr(store.fcntl,'flock',busy)
    with pytest.raises(ValueError,match='bounded lock wait'):store._lock_store(99,exclusive=exclusive)
    assert len(calls)==3


def test_lock_permission_failure_is_not_retried_or_treated_as_permission(tmp_path,monkeypatch):
    import errno
    calls=[]
    def forbidden(fd,operation):calls.append(operation);raise PermissionError(errno.EPERM,'synthetic lock refusal')
    monkeypatch.setattr(store.fcntl,'flock',forbidden)
    with pytest.raises(PermissionError):store.materialize(tmp_path,one_block())
    assert len(calls)==1
    assert list((tmp_path/'state-blocks/v1').iterdir())==[]


@pytest.mark.parametrize('bound',['entries','bytes'])
def test_staging_peak_is_inside_the_same_store_capacity(tmp_path,monkeypatch,bound):
    home=tmp_path/'run';home.mkdir();blocks=one_block();raw=next(iter(blocks.values()))
    if bound=='entries':monkeypatch.setattr(store,'MAX_STORE_ENTRIES',1)
    else:monkeypatch.setattr(store,'MAX_STORE_BYTES',len(raw))
    with pytest.raises(ValueError,match='capacity'):store.materialize(home,blocks)
    directory=home/'state-blocks/v1';assert list(directory.iterdir())==[]
    if bound=='entries':monkeypatch.setattr(store,'MAX_STORE_ENTRIES',2)
    else:monkeypatch.setattr(store,'MAX_STORE_BYTES',len(raw)*2)
    real=store.os.link;peaks=[]
    def link(*args,**kwargs):
        result=real(*args,**kwargs);peaks.append((len(list(directory.iterdir())),sum(p.stat().st_size for p in directory.iterdir())));return result
    monkeypatch.setattr(store.os,'link',link)
    store.materialize(home,blocks)
    assert peaks==[(2,len(raw)*2)]
    assert len(list(directory.iterdir()))==1


def test_shared_readers_coexist_and_writer_refuses_within_bound(tmp_path,monkeypatch):
    import fcntl
    home=tmp_path/'run';home.mkdir();blocks=one_block();store.materialize(home,blocks)
    directory=home/'state-blocks/v1';fd=os.open(directory,os.O_RDONLY|os.O_DIRECTORY)
    monkeypatch.setattr(store,'STORE_WRITE_LOCK_SECONDS',0.05)
    before={p.name:p.read_bytes() for p in directory.iterdir()}
    try:
        fcntl.flock(fd,fcntl.LOCK_SH|fcntl.LOCK_NB)
        assert store.read_regular(directory/(next(iter(blocks))+'.json'),4096)==next(iter(blocks.values()))
        start=time.monotonic()
        with pytest.raises(ValueError,match='busy'):store.materialize(home,one_block('other'))
        assert time.monotonic()-start<0.5
        assert {p.name:p.read_bytes() for p in directory.iterdir()}==before
    finally:os.close(fd)
    store.materialize(home,one_block('other'))
    assert len(list(directory.iterdir()))==2


def test_independent_process_installers_share_one_no_overwrite_store(tmp_path):
    import subprocess,sys
    home=tmp_path/'run';home.mkdir();script=tmp_path/'worker.py'
    script.write_text('''import hashlib,json,os,sys,time\nfrom pathlib import Path\nsource=Path(sys.argv[3]).resolve()\nsys.path.insert(0,str(source.parent))\nimport journal_storage as s\nassert Path(s.__file__).resolve()==source, 'worker loaded another source module'\nhome=Path(sys.argv[1]);identity=sys.argv[2]\n(home/('ready-'+identity)).write_text('ready')\nend=time.monotonic()+3\nwhile not (home/'start').exists():\n if time.monotonic()>end:raise SystemExit('start timeout')\n time.sleep(.01)\nfor index in range(12):\n raw=s.canonical(['leaf','shared-'+str(index)])+b'\\n'\n s.materialize(home,{hashlib.sha256(raw).hexdigest():raw})\n''')
    children=[]
    try:
        for identity in ['one','two']:
            children.append(subprocess.Popen([sys.executable,'-B',str(script),str(home),identity,str(Path(store.__file__).resolve())],env={key:value for key,value in os.environ.items() if key!='PYTHONPATH'},stdout=subprocess.PIPE,stderr=subprocess.PIPE))
        deadline=time.monotonic()+3
        while len(list(home.glob('ready-*')))<2:
            assert time.monotonic()<deadline
            time.sleep(.01)
        (home/'start').write_text('go')
        for child in children:
            out,err=child.communicate(timeout=8)
            assert child.returncode==0,(out,err)
    finally:
        for child in children:
            if child.poll() is None:child.kill();child.wait(timeout=2)
    directory=home/'state-blocks/v1'
    assert len(list(directory.iterdir()))==12
    for path in directory.iterdir():
        assert path.stat().st_nlink==1
        assert path.stem==hashlib.sha256(path.read_bytes()).hexdigest()


def test_stage_creation_collision_preserves_existing_foreign_bytes(tmp_path,monkeypatch):
    home=tmp_path/'run';directory=home/'state-blocks/v1';directory.mkdir(parents=True)
    class Fixed:
        hex='1'*32
    monkeypatch.setattr(store.uuid,'uuid4',lambda:Fixed())
    foreign=directory/('.stage-'+'1'*32);foreign.write_bytes(b'foreign retained staging evidence')
    with pytest.raises(FileExistsError):store.materialize(home,one_block())
    assert foreign.read_bytes()==b'foreign retained staging evidence'
    assert len(list(directory.iterdir()))==1


def test_substituted_stage_cannot_be_published_or_deleted_as_owned(tmp_path,monkeypatch):
    home=tmp_path/'run';home.mkdir();blocks=one_block();raw=next(iter(blocks.values()));real=store.os.link;names=[]
    def substitute(stage,name,*args,**kwargs):
        fd=kwargs['src_dir_fd'];os.rename(stage,'retained-owned-stage',src_dir_fd=fd,dst_dir_fd=fd)
        replacement=os.open(stage,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600,dir_fd=fd)
        try:os.write(replacement,b'foreign replacement')
        finally:os.close(replacement)
        names.append(stage)
        return real(stage,name,*args,**kwargs)
    monkeypatch.setattr(store.os,'link',substitute)
    with pytest.raises(ValueError,match='stage|publication'):store.materialize(home,blocks)
    directory=home/'state-blocks/v1'
    assert (directory/'retained-owned-stage').read_bytes()==raw
    assert (directory/names[0]).read_bytes()==b'foreign replacement'


@pytest.mark.parametrize('mode', ['full', 'component'])
def test_json_leaf_reconstruction_avoids_python_graph_clone_and_keeps_independence(tmp_path, monkeypatch, mode):
    """Real duplicate leaves must be fresh JSON objects without Python graph walks."""
    value = {'left': {'items': [{'id': n, 'flags': [True, None, 'λ']} for n in range(150)]},
             'right': {'items': [{'id': n, 'flags': [True, None, 'λ']} for n in range(150)]},
             'padding': 'x' * (2 * 1024 * 1024)}
    path, descriptor, _ = encoded(tmp_path, value)
    def unexpected_clone(*args, **kwargs):
        raise AssertionError('JSON snapshot unnecessarily traversed the Python deepcopy graph')
    monkeypatch.setattr(storage, 'deepcopy', unexpected_clone, raising=False)
    if mode == 'full':
        decoded = storage.decode(path, descriptor)
    else:
        decoded, _ = storage.component(path, (), max_bytes=8 * 1024 * 1024)
    assert decoded == value
    decoded['left']['items'][0]['flags'].append('mutated')
    assert decoded['right'] == value['right']
    again = storage.decode(path, descriptor)
    assert again == value


def test_second_decode_never_reuses_a_previously_verified_leaf(tmp_path):
    path, descriptor, value = encoded(tmp_path, independent_value())
    assert storage.decode(path, descriptor) == value
    directory = path.parent / 'state-blocks/v1'
    # Leaves may be inline inside an authenticated physical block. Tamper each
    # physical block in turn; every repeat decode must reread all dependencies.
    for number, block in enumerate(sorted(directory.iterdir())):
        original = block.read_bytes()
        (tmp_path / ('retained-block-' + str(number))).write_bytes(original)
        block.write_bytes(b'changed block')
        with pytest.raises(ValueError, match='digest'): storage.decode(path, descriptor)
        block.write_bytes(original)
    assert storage.decode(path, descriptor) == value


def test_append_aligned_history_reuses_immutable_prefix_blocks(tmp_path):
    """Appending one record must not rewrite all earlier list segments."""
    values = [{'id': str(i), 'value': 'synthetic-' + str(i) + ':' + 'x' * 900}
              for i in range(4096)]
    before, old = storage.encode({'history': values})
    after, new = storage.encode({'history': values + [{'id': 'next', 'value': 'next'}]})
    assert before != after
    assert len(set(old) - set(new)) <= 2
    assert len(set(new) - set(old)) <= 3
    home = tmp_path / 'autopilot-runs/01990000-0000-7000-8000-000000000777'
    home.mkdir(parents=True)
    storage.materialize(home, old)
    retained = {key: (home / 'state-blocks/v1' / (key + '.json')).read_bytes() for key in old}
    storage.materialize(home, new)
    assert storage.decode(home / 'current.json', json.loads(before)) == {'history': values}
    assert storage.decode(home / 'current.json', json.loads(after)) == {'history': values + [{'id': 'next', 'value': 'next'}]}
    assert all((home / 'state-blocks/v1' / (key + '.json')).read_bytes() == raw for key, raw in retained.items())


@pytest.mark.parametrize('kind', ['map', 'list'])
def test_retained_append_history_has_finite_physical_work_and_exact_readback(tmp_path, kind):
    """Synthetic growing histories keep every revision under the same caps."""
    home = tmp_path / 'autopilot-runs/01990000-0000-7000-8000-000000000777'
    home.mkdir(parents=True)
    history = {} if kind == 'map' else []
    revisions = []
    for page in range(40):
        for number in range(page * 64, (page + 1) * 64):
            row = {'id': hashlib.sha256(str(number).encode()).hexdigest(),
                   'tokens': number, 'cost': None, 'status': 'UNKNOWN',
                   'data': ('synthetic retained detail ' + str(number)) * 32}
            if kind == 'map': history[row['id']] = row
            else: history.append(row)
        value = {'revision': page, 'history': history, 'padding': 'x' * 1100000}
        raw, blocks = storage.encode(value)
        storage.materialize(home, blocks)
        revisions.append((raw, hashlib.sha256(storage.canonical(value)).hexdigest()))
    files = list((home / 'state-blocks/v1').iterdir())
    assert len(files) < 1500
    assert sum(p.stat().st_size for p in files) < 8 * 1024 * 1024
    for raw, digest in revisions:
        decoded = storage.decode(home / 'current.json', json.loads(raw))
        assert hashlib.sha256(storage.canonical(decoded)).hexdigest() == digest
    assert (storage.MAX_LOGICAL_BYTES, storage.MAX_STORE_BYTES,
            storage.MAX_STORE_ENTRIES, storage.MAX_BLOCKS) == (64*1024**2, 512*1024**2, 32768, 16384)


@pytest.mark.parametrize('fault', ['bomb', 'trailing', 'truncated', 'duplicate-json', 'noncanonical', 'wrong-shape'])
@pytest.mark.parametrize('reader', ['decode', 'component'])
def test_compressed_leaf_refuses_malformed_or_unbounded_expansion(tmp_path, monkeypatch, fault, reader):
    import base64, zlib
    body = storage.canonical({'batch': 'synthetic'})
    if fault == 'bomb': body = storage.canonical({'batch': 'x' * storage.LEAF_BYTES})
    elif fault == 'duplicate-json': body = b'{"batch":1,"batch":2}'
    elif fault == 'noncanonical': body = b'{ "batch": 1 }'
    packed = zlib.compress(body)
    if fault == 'trailing': packed += b'foreign trailing data'
    elif fault == 'truncated': packed = packed[:-2]
    payload = base64.b64encode(packed).decode('ascii') if fault != 'wrong-shape' else []
    block = storage.canonical(['zleaf', payload]) + b'\n'
    digest = hashlib.sha256(block).hexdigest()
    home = tmp_path / 'autopilot-runs/01990000-0000-7000-8000-000000000777'
    home.mkdir(parents=True); storage.materialize(home, {digest: block})
    desc = {storage.MARKER: 1, 'root': digest, 'sha256': hashlib.sha256(body+b'\n').hexdigest(), 'logical_bytes': len(body)+1}
    path = home / 'current.json'; path.write_bytes(storage.canonical(desc)+b'\n')
    with pytest.raises(ValueError):
        if reader == 'decode': storage.decode(path, desc)
        else: storage.component(path, ('batch',), max_bytes=128*1024)


def test_compressed_selected_leaf_cannot_expand_past_caller_budget(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'INLINE_BYTES', 0)
    path, desc, value = encoded(tmp_path, {'batch': {'value': 'x'*30000}, 'other': 'y'*20000})
    assert storage.decode(path, desc) == value
    with pytest.raises(ValueError): storage.component(path, ('batch',), max_bytes=4096)
    assert storage.component(path, ('batch',), max_bytes=65536)[0] == value['batch']


def test_old_leaf_graph_and_new_compressed_graph_share_exact_logical_identity(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'INLINE_BYTES', 0)
    home = tmp_path / 'autopilot-runs/01990000-0000-7000-8000-000000000777'; home.mkdir(parents=True)
    value = {'batch': {'items': ['λ'*100 for _ in range(40)]}, 'cost': None}
    old = storage.canonical(['leaf', value]) + b'\n'; root = hashlib.sha256(old).hexdigest()
    logical = storage.canonical(value)+b'\n'
    desc = {storage.MARKER:1, 'root':root, 'sha256':hashlib.sha256(logical).hexdigest(), 'logical_bytes':len(logical)}
    raw, blocks = storage.encode(value); storage.materialize(home, {root:old, **blocks})
    path = home / 'current.json'; path.write_bytes(storage.canonical(desc)+b'\n')
    assert json.loads(raw)['sha256'] == desc['sha256']
    assert json.loads(raw)['root'] != root
    assert storage.decode(path, desc) == storage.decode(path, json.loads(raw)) == value
    assert storage.component(path, ('batch',), max_bytes=65536)[0] == value['batch']


def test_selected_component_charges_discarded_compressed_expansion(tmp_path, monkeypatch):
    """Independent review's missing-key DAG cannot hide decompression work."""
    import base64, zlib
    home = tmp_path / 'autopilot-runs/01990000-0000-7000-8000-000000000777'; home.mkdir(parents=True)
    blocks = {}
    def put(value):
        raw = storage.canonical(value)+b'\n'; digest = hashlib.sha256(raw).hexdigest(); blocks[digest] = raw; return digest
    raw = storage.canonical({'unrelated': 'x'*3000})
    root = put(['zleaf', base64.b64encode(zlib.compress(raw)).decode()])
    for _ in range(10): root = put(['map', [root, root]])
    storage.materialize(home, blocks)
    path = home / 'current.json'; path.write_bytes(storage.canonical({storage.MARKER:1, 'root':root, 'sha256':'0'*64, 'logical_bytes':len(raw)}))
    seen = []; original = storage._leaf
    def counted(*args, **kwargs):
        value = original(*args, **kwargs); seen.append(len(storage.canonical(value))); return value
    monkeypatch.setattr(storage, '_leaf', counted)
    with pytest.raises(ValueError): storage.component(path, ('missing',), max_bytes=4096)
    assert sum(seen) <= 4096


def test_retained_physical_attribution_reads_original_graph_after_codec_change(engine, world, monkeypatch):
    """Exercise the actual attribution consumer, including old-format blocks."""
    state = big_state(engine, world)
    state = command(engine, world, state, 'fixture.grow', {})
    # Rebuild a synthetic predecessor with the exact original deterministic
    # compiler and its original unbound logical state, including chained hashes.
    home = engine._home(world['project'], state['run_id'])
    history = list(engine._events(world['project'], state['run_id']))
    previous = ''
    for event in history:
        event = deepcopy(dict(event))
        event['state']['extensions'].pop('journal_storage', None)
        event['previous_digest'] = previous
        event.pop('digest')
        event['digest'] = engine._digest(event)
        previous = event['digest']
        raw, blocks = storage.encode(event, codec=1)
        storage.materialize(home, blocks)
        (home/'events'/f"{event['revision']:012d}.json").write_bytes(raw)
        state = event['state']
    raw, blocks = storage.encode(state, codec=1)
    storage.materialize(home, blocks)
    (home/'current.json').write_bytes(raw)
    home = engine._home(world['project'], state['run_id'])
    current = home / 'current.json'
    original = current.read_bytes()
    assert storage.encode(state, codec=2)[0] != original
    assert engine.load_run(world['project'], state['run_id']) == state
    retained = engine._retained_snapshot_bytes(current, state)
    assert retained[current] == original
    assert all(path.read_bytes() == raw for path, raw in retained.items())
    with pytest.raises(ValueError, match='noncanonical|foreign'):
        engine._retained_snapshot_bytes(current, {**state, 'status':'completed'})
    after = command(engine, world, state, 'progress', {'summary':'synthetic progress after retained codec'})
    assert engine.load_run(world['project'], state['run_id']) == after
    assert current.read_bytes() != original
    for path, raw in retained.items():
        if path != current: assert path.read_bytes() == raw


@pytest.mark.parametrize('shape', ['deep', 'wide'])
def test_new_compressed_leaf_work_bounds_keep_old_plain_values_readable(tmp_path, monkeypatch, shape):
    import base64, zlib
    value = [0] * 20000 if shape == 'wide' else 0
    if shape == 'deep':
        for _ in range(80): value = [value]
    raw = storage.canonical(value)
    packed = base64.b64encode(zlib.compress(raw)).decode()
    with pytest.raises(ValueError, match='JSON depth|JSON work'):
        storage._leaf('zleaf', packed)
    monkeypatch.setattr(storage, 'INLINE_BYTES', 0)
    path, descriptor, _ = encoded(tmp_path, value)
    assert storage.decode(path, descriptor) == value


@pytest.mark.parametrize('fault', ['bomb', 'trailing', 'truncated', 'noncanonical', 'unknown-prefix'])
@pytest.mark.parametrize('reader', ['decode', 'component'])
def test_physical_block_compression_has_closed_bounded_expansion(tmp_path, fault, reader):
    import zlib
    value = {'batch': 'synthetic'}
    data = storage.canonical(['leaf', value])+b'\n'
    if fault == 'bomb': data = b'x'*(storage.MAX_BLOCK_BYTES+1)
    elif fault == 'noncanonical': data = b'[ "leaf", {"batch": "synthetic"} ]\n'
    raw = storage.BLOCK_PREFIX + zlib.compress(data)
    if fault == 'trailing': raw += b'foreign suffix'
    elif fault == 'truncated': raw = raw[:-2]
    elif fault == 'unknown-prefix': raw = b'\x00SZ9' + raw[len(storage.BLOCK_PREFIX):]
    digest = hashlib.sha256(raw).hexdigest()
    home = tmp_path / 'autopilot-runs/01990000-0000-7000-8000-000000000777'; home.mkdir(parents=True)
    storage.materialize(home, {digest:raw})
    logical = storage.canonical(value)+b'\n'
    desc = {storage.MARKER:1, 'root':digest, 'sha256':hashlib.sha256(logical).hexdigest(), 'logical_bytes':len(logical)}
    path = home / 'current.json'; path.write_bytes(storage.canonical(desc)+b'\n')
    with pytest.raises(ValueError):
        if reader == 'decode': storage.decode(path, desc)
        else: storage.component(path, ('batch',), max_bytes=256*1024)


def test_retained_physical_renderer_refuses_unowned_path(tmp_path):
    path = tmp_path / 'not-a-run.json'; path.write_text('{}')
    with pytest.raises(ValueError): storage.retained_snapshot_bytes(path, {}, max_bytes=4096)


@pytest.mark.parametrize('binding', [None, {'codec':3}, {'codec':2.0}, {'codec':True}, {'codec':2,'extra':1}, '2'])
def test_codec_binding_is_closed_and_exact(binding):
    state = {'run_id':'synthetic','revision':1,'schema_version':1,
             'extensions':{'journal_storage':binding}}
    with pytest.raises(ValueError, match='codec'): storage.encode(state)


def test_retained_attribution_refuses_equivalent_foreign_inline_bytes(tmp_path):
    home=tmp_path/'autopilot-runs/01990000-0000-7000-8000-000000000777'
    home.mkdir(parents=True);path=home/'current.json';value={'synthetic':'value'}
    path.write_text(json.dumps(value,indent=2)+'\n')
    with pytest.raises(ValueError, match='foreign'):
        storage.retained_snapshot_bytes(path,value,max_bytes=4096)
    path.write_bytes(storage.canonical(value)+b'\n')
    assert storage.retained_snapshot_bytes(path,value,max_bytes=4096)=={path:path.read_bytes()}


def test_new_codec_descriptor_cannot_relabel_authenticated_state(engine, world):
    state=command(engine,world,big_state(engine,world),'fixture.grow',{})
    home=engine._home(world['project'],state['run_id'])
    event=home/'events/000000000002.json';original=event.read_bytes()
    descriptor=json.loads(original);assert descriptor[storage.MARKER]==2
    descriptor[storage.MARKER]=1;event.write_bytes(storage.canonical(descriptor)+b'\n')
    with pytest.raises(ValueError,match='codec'):engine.load_run(world['project'],state['run_id'])
    event.write_bytes(original)
    assert engine.load_run(world['project'],state['run_id'])==state
    assert state['extensions']['journal_storage']=={'codec':2}


def test_authenticated_codec_cannot_regress_in_later_revision(engine, world):
    state=command(engine,world,create(engine,world),'progress',{'summary':'synthetic'})
    home=engine._home(world['project'],state['run_id']);path=home/'events/000000000002.json'
    event=dict(engine._read(path));event['state']['extensions'].pop('journal_storage')
    event.pop('digest');event['digest']=engine._digest(event)
    raw,blocks=storage.encode(event,codec=1);storage.materialize(home,blocks);path.write_bytes(raw)
    with pytest.raises(engine.RunStateError,match='codec regressed'):
        engine.load_run(world['project'],state['run_id'])



def test_same_large_map_shares_blocks_across_event_and_projection_nesting(tmp_path):
    values={f'key-{i}':{'body':f'{i}'+('retained synthetic payload '*100)} for i in range(1500)}
    state={'run_id':'synthetic','revision':1,'schema_version':1,
           'extensions':{'journal_storage':{'codec':2},'history':values}}
    sr,sb=storage.encode(state)
    er,eb=storage.encode({'state':state,'other':'wrapper'})
    common=set(sb)&set(eb)
    assert sum(len(sb[k]) for k in common) >= sum(map(len,sb.values())) * .95
    path,desc,_=encoded(tmp_path,state)
    assert storage.decode(path,desc)==state
    assert storage.canonical(json.loads(sr))==storage.canonical(json.loads(path.read_bytes()))
    assert json.loads(er)[storage.MARKER]==2


def test_prepared_owner_state_commits_above_physical_file_limit(engine, world):
    state = create(engine, world)
    pm_state = {'schema_version': 1, 'items': [
        {'id': index, 'evidence': 'retained-' + 'x' * 2000}
        for index in range(3100)]}
    prepared = {'pm_state': pm_state}
    assert engine.MAX_JSON_BYTES < len(engine._json(prepared)) < storage.MAX_LOGICAL_BYTES
    calls = []
    def prepare(context, payload):
        calls.append(context['journal_head']['revision'])
        return prepared
    def reduce(state, payload, context):
        state['extensions']['owner_state'] = payload['pm_state']
        return state
    engine.register_command('fixture.owner-state', reduce, allowed_fields=('extensions',))
    engine.register_preparer('fixture.owner-state', prepare)
    changed = command(engine, world, state, 'fixture.owner-state', {}, command_id='owner-state')
    assert changed['extensions']['owner_state'] == pm_state
    assert engine.load_run(world['project'], state['run_id']) == changed
    assert command(engine, world, state, 'fixture.owner-state', {}, command_id='owner-state') == changed
    assert calls == [state['revision']]

@pytest.mark.parametrize('fault', ['logical_capacity', 'invalid_shape', 'protected_core'])
def test_prepared_owner_refusals_leave_journal_unchanged(engine, world, monkeypatch, fault):
    state = create(engine, world)
    home = engine._home(world['project'], state['run_id'])
    before = {p.name: p.read_bytes() for p in (home / 'events').iterdir()}
    projection = (home / 'current.json').read_bytes()
    seen = []
    def prepare(context, payload):
        seen.append('prepare')
        if fault == 'invalid_shape':
            return []
        return {'pm_state': 'x' * 6000}
    def reduce(state, payload, context):
        seen.append('reduce')
        if fault == 'protected_core':
            state['status'] = 'completed'
        return state
    engine.register_command('fixture.owner-refusal', reduce, allowed_fields=('extensions',))
    engine.register_preparer('fixture.owner-refusal', prepare)
    original_capacity = storage.MAX_LOGICAL_BYTES
    if fault == 'logical_capacity':
        monkeypatch.setattr(storage, 'MAX_LOGICAL_BYTES', 6000)
    payload = {}
    with pytest.raises(ValueError):
        command(engine, world, state, 'fixture.owner-refusal', payload)
    if fault in {'logical_capacity', 'invalid_shape'}:
        assert seen == ['prepare']
    else:
        assert seen == ['prepare', 'reduce']
    assert {p.name: p.read_bytes() for p in (home / 'events').iterdir()} == before
    assert (home / 'current.json').read_bytes() == projection
    if fault == 'logical_capacity':
        monkeypatch.setattr(storage, 'MAX_LOGICAL_BYTES', original_capacity)
    assert engine.load_run(world['project'], state['run_id']) == state


def test_operation_reuses_only_verified_history_and_cold_entries(engine, world, monkeypatch):
    state = create(engine, world)
    state = command(engine, world, state, 'wait.add', {'id': 'retained', 'kind': 'external', 'reason': 'retained obligation'})
    reads = []
    original = engine._read
    def read(path, **kwargs):
        if path.parent.name == 'events': reads.append(path.name)
        return original(path, **kwargs)
    monkeypatch.setattr(engine, '_read', read)
    with engine.journal_operation():
        assert engine.load_run(world['project'], state['run_id']) == state
        first = list(reads)
        assert len(first) == state['revision']
        detached = engine.load_run(world['project'], state['run_id'])
        detached['waits'].clear()
        assert engine.load_run(world['project'], state['run_id']) == state
        assert reads == first
        changed = command(engine, world, state, 'progress', {'summary': 'independent progress with retained wait'})
        assert engine.load_run(world['project'], state['run_id']) == changed
        assert len(reads) == len(first) + 1
    assert engine._HISTORY_OPERATION.get() is None
    with engine.journal_operation():
        assert engine.load_run(world['project'], state['run_id']) == changed
    assert len(reads) == len(first) + 1 + changed['revision']


@pytest.mark.parametrize('fault', ['bytes-restored-mtime', 'mode', 'missing', 'symlink', 'hardlink', 'ancestor'])
def test_operation_refuses_changed_history_before_reuse(engine, world, fault):
    import os
    state = create(engine, world)
    home = engine._home(world['project'], state['run_id'])
    target = home / 'events/000000000001.json'
    with engine.journal_operation():
        assert engine.load_run(world['project'], state['run_id']) == state
        before = target.stat()
        if fault == 'bytes-restored-mtime':
            raw = target.read_bytes(); target.write_bytes(raw.replace(b'fixture', b'changed', 1))
            # Even a same-byte rewrite with restored mtime changes ctime.
            os.utime(target, ns=(before.st_atime_ns, before.st_mtime_ns))
        elif fault == 'mode': target.chmod(0o755)
        elif fault == 'missing': target.rename(home / 'retained-event')
        elif fault == 'symlink':
            saved = home / 'retained-event';target.rename(saved);target.symlink_to(saved)
        elif fault == 'hardlink': os.link(target, home / 'foreign-hardlink')
        else:
            directory = target.parent; saved = home / 'retained-events';directory.rename(saved);directory.mkdir()
            (saved / target.name).rename(target)
        with pytest.raises((ValueError, OSError)):
            engine.load_run(world['project'], state['run_id'])
    assert engine._HISTORY_OPERATION.get() is None


def test_operation_refuses_shared_block_mutation_and_never_carries_proof(engine, world):
    state = big_state(engine, world)
    state = command(engine, world, state, 'fixture.grow', {})
    home = engine._home(world['project'], state['run_id'])
    with engine.journal_operation():
        assert engine.load_run(world['project'], state['run_id']) == state
        descriptor = json.loads((home / 'events' / f"{state['revision']:012d}.json").read_text())
        block = home / 'state-blocks/v1' / (descriptor['root'] + '.json')
        block.write_bytes(b'foreign')
        with pytest.raises(ValueError): engine.load_run(world['project'], state['run_id'])
    with pytest.raises(ValueError): engine.load_run(world['project'], state['run_id'])


def test_operation_exception_discards_observations(engine, world):
    state = create(engine, world)
    with pytest.raises(RuntimeError):
        with engine.journal_operation():
            engine.load_run(world['project'], state['run_id'])
            raise RuntimeError('synthetic interruption')
    assert engine._HISTORY_OPERATION.get() is None


def test_partition_optimization_preserves_exact_physical_encoding(engine, world):
    import journal_storage as store
    # Independent specification pins retained deterministic bytes through fixed
    # vectors; Unicode, mixed scalar/container keys and both map boundaries.
    value = {'run_id': '00000000-0000-4000-8000-000000000001', 'revision': 1, 'schema_version': 1,
             'extensions': {'journal_storage': {'codec': 2}, 'records': {
                 'entry-' + str(i): {'text': '\u03b1' * (120 + i % 37), 'values': [i, None, True]}
                 for i in range(5000)}}}
    raw, blocks = store.encode(value)
    assert hashlib.sha256(raw).hexdigest() == '05cbd6e77b7c76bc984475d03bbf7be64031182c768acb6505770c693b08ed87'
    assert hashlib.sha256(b''.join(key.encode() + blocks[key] for key in sorted(blocks))).hexdigest() == '6ad19990ab8b58cc73f89ff3e3feeec9828ddd1f16f9151aee68a3dd95fe92fd'
    assert len(blocks) == 3


@pytest.mark.parametrize('failure', ['metadata', 'final-fence'])
def test_operation_failed_population_does_not_survive_retry(engine, world, monkeypatch, failure):
    state = create(engine, world)
    original_read = engine._read
    reads = []
    def read(path, **kwargs):
        reads.append(path)
        return original_read(path, **kwargs)
    monkeypatch.setattr(engine, '_read', read)
    target = '_history_metadata' if failure == 'metadata' else '_fence_history'
    actual = getattr(engine, target)
    calls = []
    def once(*args, **kwargs):
        calls.append(True)
        if len(calls) == 1: raise ValueError('synthetic refused population')
        return actual(*args, **kwargs)
    monkeypatch.setattr(engine, target, once)
    with engine.journal_operation():
        with pytest.raises(ValueError, match='synthetic refused population'):
            engine.load_run(world['project'], state['run_id'])
        assert engine._HISTORY_OPERATION.get() == {}
        assert engine.load_run(world['project'], state['run_id']) == state
        assert len(reads) == 2


def test_optional_history_metadata_budget_preserves_streaming_admission(engine, world, monkeypatch):
    state = create(engine, world)
    actual = engine._history_metadata
    def larger_metadata(event):
        return {**actual(event), 'synthetic_metadata_cost': 'x' * engine.MAX_JSON_BYTES}
    monkeypatch.setattr(engine, '_history_metadata', larger_metadata)
    with engine.journal_operation():
        assert engine.load_run(world['project'], state['run_id']) == state
        assert engine._HISTORY_OPERATION.get() == {}


def test_nested_operation_does_not_extend_observation_lifetime(engine, world):
    state = create(engine, world)
    with engine.journal_operation():
        engine.load_run(world['project'], state['run_id'])
        outer = engine._HISTORY_OPERATION.get()
        with engine.journal_operation():
            assert engine._HISTORY_OPERATION.get() is outer
    assert engine._HISTORY_OPERATION.get() is None


def test_replay_reread_cannot_replace_verified_matching_state(engine,world,monkeypatch):
    initial=create(engine,world)
    expected=command(engine,world,initial,'progress',{'summary':'retained verified result'},command_id='same-command')
    target=engine._home(world['project'],initial['run_id'])/'events'/f"{expected['revision']:012d}.json"
    original=target.read_bytes()
    (world['project']/'retained-original-event.json').write_bytes(original)
    projection=target.parent.parent/'current.json'
    projection_before=projection.read_bytes()
    actual_read=engine._read
    observed=[]
    with engine.journal_operation():
        assert engine.load_run(world['project'],initial['run_id'])==expected
        def raced_read(path,*args,**kwargs):
            if Path(path)==target and not kwargs and not observed:
                changed=json.loads(original)
                changed['state']['progress']['summary']='unverified replacement returned as replay result'
                target.write_bytes(engine._json(changed)+b'\n')
                observed.append(str(path))
            return actual_read(path,*args,**kwargs)
        monkeypatch.setattr(engine,'_read',raced_read)
        refused=None;result=None
        try:
            result=command(engine,world,initial,'progress',{'summary':'retained verified result'},command_id='same-command')
        except ValueError as exc:
            refused=str(exc)
        (world['project']/'replay-race-observation.json').write_text(json.dumps({'fault_triggered':bool(observed),'refusal':refused,'returned_summary':result.get('progress',{}).get('summary') if result else None,'result_equal_to_authenticated_prior':result==expected,'target':str(target)},indent=2)+'\n')
        assert observed,'fault must reach exact matching reread'
        assert refused is not None,'changed matching event must refuse before returning replay state'
        assert projection.read_bytes()==projection_before


def test_compilation_reuses_exact_state_bytes_without_mutable_aliases(engine, world, monkeypatch):
    import journal_storage as store
    state = big_state(engine, world)
    state = command(engine, world, state, 'fixture.grow', {})
    event = {'state': state, 'schema_version': 1, 'revision': state['revision'], 'digest': 'd' * 64}
    expected_event = store.encode(event)
    expected_state = store.encode(state)
    compressed = []
    original = store.zlib.compress
    def compress(*args, **kwargs):
        compressed.append(True)
        return original(*args, **kwargs)
    monkeypatch.setattr(store.zlib, 'compress', compress)
    with store.compilation_scope():
        assert store.encode(event) == expected_event
        first_count = len(compressed)
        raw, blocks = store.encode(state)
        assert (raw, blocks) == expected_state
        # Only the state root wrapper may need compilation after its exact
        # subtree was compiled inside the event.
        assert len(compressed) - first_count <= 1
        blocks.clear()
        assert store.encode(deepcopy(state)) == expected_state
        state['extensions']['synthetic_history']['entry-0'] += 'changed'
        changed = store.encode(state)
        assert changed != expected_state
        assert store._COMPILATION.get()['bytes'] <= store.MAX_LOGICAL_BYTES
    assert store._COMPILATION.get() is None
    assert store.encode(state) == changed


@pytest.mark.parametrize('bound', ['MAX_DEPTH', 'MAX_BLOCKS', 'MAX_LOGICAL_BYTES'])
def test_compilation_reuse_reapplies_enclosing_bounds(engine, world, monkeypatch, bound):
    import journal_storage as store
    state = big_state(engine, world)
    state = command(engine, world, state, 'fixture.grow', {})
    with store.compilation_scope():
        store.encode(state)
        monkeypatch.setattr(store, bound, 1)
        with pytest.raises(ValueError): store.encode(state)
    assert store._COMPILATION.get() is None


def test_compilation_scope_exceptions_and_nested_lifetime():
    import journal_storage as store
    with pytest.raises(RuntimeError):
        with store.compilation_scope():
            scope = store._COMPILATION.get()
            with store.compilation_scope():
                assert store._COMPILATION.get() is scope
            raise RuntimeError('synthetic compiler interruption')
    assert store._COMPILATION.get() is None


def test_selected_head_reuse_is_independent_and_freshly_fenced(engine, world, monkeypatch):
    import journal_storage as store
    state = big_state(engine, world)
    state = command(engine, world, state, 'fixture.grow', {})
    path = engine._home(world['project'], state['run_id']) / 'events' / f"{state['revision']:012d}.json"
    original = store.decode
    reads = []
    def decode(*args, **kwargs):
        reads.append(str(args[0]))
        return original(*args, **kwargs)
    monkeypatch.setattr(store, 'decode', decode)
    with engine.journal_operation():
        assert engine.load_run(world['project'], state['run_id']) == state
        observed = list(reads)
        event = engine._read(path)
        event['state']['extensions'].clear()
        assert engine._read(path)['state'] == state
        assert reads == observed
        path.write_bytes(path.read_bytes())
        with pytest.raises(ValueError): engine._read(path)
    # Even a same-byte rewrite must get a full cold decode on a new entry.
    assert engine.load_run(world['project'], state['run_id']) == state
    assert len(reads) > len(observed)


def test_compilation_reuses_unchanged_leaves_across_revisions(monkeypatch):
    import journal_storage as store
    value = {'run_id': '00000000-0000-4000-8000-000000000001', 'schema_version': 1,
             'revision': 1, 'extensions': {'journal_storage': {'codec': 2}, 'rows': {
                 str(i): {'text': hashlib.sha256(str(i).encode()).hexdigest() * 6}
                 for i in range(3000)}}}
    changed = deepcopy(value)
    changed['revision'] = 2
    changed['extensions']['rows']['2999']['text'] += 'changed input'
    first_expected, next_expected = store.encode(value), store.encode(changed)
    calls = []
    original = store.zlib.compress
    def counted(*args, **kwargs):
        calls.append(True)
        return original(*args, **kwargs)
    monkeypatch.setattr(store.zlib, 'compress', counted)
    with store.compilation_scope():
        assert store.encode(value) == first_expected
        first = len(calls)
        assert store.encode(changed) == next_expected
        assert len(calls) - first < first / 2
        changed['extensions']['rows']['1']['text'] = 'mutated caller'
        actual = store.encode(changed)
        assert actual != next_expected
        assert store._COMPILATION.get()['bytes'] <= store.MAX_LOGICAL_BYTES
    assert store.encode(changed) == actual


def test_compilation_eviction_preserves_exact_cold_bytes(monkeypatch):
    import journal_storage as store
    values = [{'extensions': {'journal_storage': {'codec': 2}}, 'payload': ''.join(
        hashlib.sha256(f'{generation}:{i}'.encode()).hexdigest() for i in range(9000))}
        for generation in range(4)]
    expected = [store.encode(value) for value in values]
    monkeypatch.setattr(store, 'MAX_LOGICAL_BYTES', 1024 * 1024)
    with store.compilation_scope():
        for value, encoded in zip(values + values[:1], expected + expected[:1]):
            assert store.encode(value) == encoded
            assert store._COMPILATION.get()['bytes'] <= store.MAX_LOGICAL_BYTES
            assert len(store._COMPILATION.get()['entries']) <= store.MAX_BLOCKS
    assert store._COMPILATION.get() is None


@pytest.mark.parametrize('kind', ['alias', 'dict-subclass', 'str-subclass', 'int-subclass', 'tuple', 'bytes', 'set', 'nan', 'infinity', 'nonstring-key'])
def test_constraint_snapshot_falls_back_without_normalizing_python_values(engine, kind):
    class CustomDict(dict): pass
    class CustomStr(str): pass
    class CustomInt(int): pass
    shared = []
    values = {'alias': {'a': shared, 'b': shared}, 'dict-subclass': CustomDict(a=1),
              'str-subclass': CustomStr('value'), 'int-subclass': CustomInt(1),
              'tuple': (1, 2), 'bytes': b'value', 'set': {1}, 'nan': float('nan'),
              'infinity': float('inf'), 'nonstring-key': {1: 'value'}}
    snapshot = engine._constraint_snapshot({'unknown_future_field': values[kind]})
    if kind == 'alias':
        # The old fallback assertion described a mechanism, not the required
        # copy semantics: ordinary aliases now use the memoized builtin path.
        assert snapshot is not None
        copied = engine.pickle.loads(snapshot)['unknown_future_field']
        assert copied['a'] is copied['b'] and copied['a'] is not shared
    else:
        assert snapshot is None


def test_constraint_snapshot_keeps_independent_unknown_fields_and_order(engine, world):
    state = create(engine, world)
    def reducer(state, payload, context):
        state['extensions']['unknown_future_field'] = {'rows': [1, {'value': '\u03b1'}]}
        return state
    engine.register_command('fixture.opaque', reducer)
    seen = []
    def first(candidate, action, payload, context):
        seen.append('first')
        candidate['extensions']['unknown_future_field']['rows'][1]['value'] = 'hostile callback mutation'
    def second(candidate, action, payload, context):
        seen.append('second')
        assert candidate['extensions']['unknown_future_field'] == {'rows': [1, {'value': '\u03b1'}]}
    engine.register_constraint('first', first);engine.register_constraint('second', second)
    updated = command(engine, world, state, 'fixture.opaque', {})
    assert seen == ['first', 'second']
    assert updated['extensions']['unknown_future_field'] == {'rows': [1, {'value': '\u03b1'}]}
    assert engine.load_run(world['project'], state['run_id']) == updated


def test_constraint_snapshot_keeps_first_exception_and_no_commit(engine, world):
    state = create(engine, world);seen = []
    def first(candidate, action, payload, context):
        seen.append('first');raise RuntimeError('original first constraint failure')
    def second(candidate, action, payload, context): seen.append('second')
    engine.register_constraint('first', first);engine.register_constraint('second', second)
    with pytest.raises(RuntimeError, match='original first constraint failure'):
        command(engine, world, state, 'progress', {'summary': 'must not commit'})
    assert seen == ['first']
    assert engine.load_run(world['project'], state['run_id']) == state


def test_constraint_snapshot_preserves_reducer_dictionary_insertion_order(engine, world):
    state = create(engine, world);seen = []
    def reducer(state, payload, context):
        state['extensions']['unknown_ordered_field'] = {'z': 1, 'a': {'y': 2, 'b': 3}}
        return state
    def constraint(candidate, action, payload, context):
        value = candidate['extensions']['unknown_ordered_field']
        seen.append((list(value), list(value['a'])))
        assert list(value) == ['z', 'a']
        assert list(value['a']) == ['y', 'b']
    engine.register_command('fixture.ordered', reducer)
    engine.register_constraint('check-order', constraint)
    updated = command(engine, world, state, 'fixture.ordered', {})
    assert seen == [(['z', 'a'], ['y', 'b'])]
    assert list(updated['extensions']['unknown_ordered_field']) == ['z', 'a']


@pytest.mark.parametrize('cycle', [False, True])
def test_constraint_snapshot_preserves_graph_aliases_and_independent_copies(engine, cycle):
    shared = {'z': [], 'a': {'future': '\u03b1'}}
    graph = {'left': shared, 'right': shared, 'rows': [shared, shared['z']]}
    if cycle:
        shared['z'].append(graph)
    snapshot = engine._constraint_snapshot(graph)
    assert snapshot is not None
    first, second = engine.pickle.loads(snapshot), engine.pickle.loads(snapshot)
    for copied in (first, second):
        assert copied['left'] is copied['right'] is copied['rows'][0]
        assert copied['rows'][1] is copied['left']['z']
        assert list(copied['left']) == ['z', 'a']
        if cycle:
            assert copied['left']['z'][0] is copied
    first['left']['a']['future'] = 'mutated'
    assert second['right']['a']['future'] == shared['a']['future'] == '\u03b1'
    assert first['left'] is not second['left'] and second['left'] is not shared


def test_constraint_snapshot_actual_shared_state_uses_fast_path(engine, world, monkeypatch):
    state = create(engine, world);observed = [];copies = []
    snapshot = engine._constraint_snapshot
    def observed_snapshot(value):
        result = snapshot(value);observed.append(result is not None);return result
    monkeypatch.setattr(engine, '_constraint_snapshot', observed_snapshot)
    def reducer(candidate, payload, context):
        shared = {'z': ['original'], 'a': 1}
        candidate['extensions']['unknown_aliases'] = {'left': shared, 'right': shared}
        return candidate
    def first(candidate, action, payload, context):
        aliases = candidate['extensions']['unknown_aliases'];copies.append(aliases)
        assert aliases['left'] is aliases['right']
        aliases['left']['z'].append('hostile')
        assert aliases['right']['z'] == ['original', 'hostile']
        payload['future']['rows'].append('hostile payload')
    def second(candidate, action, payload, context):
        aliases = candidate['extensions']['unknown_aliases'];copies.append(aliases)
        assert aliases['left'] is aliases['right']
        assert aliases['right']['z'] == ['original']
        assert payload == {'future': {'rows': ['payload']}}
        assert list(aliases['left']) == ['z', 'a']
    engine.register_command('fixture.aliases', reducer)
    engine.register_constraint('first-alias', first);engine.register_constraint('second-alias', second)
    payload = {'future': {'rows': ['payload']}}
    updated = command(engine, world, state, 'fixture.aliases', payload)
    assert observed and all(observed) and copies[0]['left'] is not copies[1]['left']
    assert payload == {'future': {'rows': ['payload']}}
    aliases = updated['extensions']['unknown_aliases']
    assert aliases['left'] is aliases['right'] and aliases['right']['z'] == ['original']
    assert engine.load_run(world['project'], state['run_id']) == updated


def test_constraint_snapshot_cycle_reaches_original_constraint_refusal(engine, world):
    state = create(engine, world);seen = []
    def reducer(candidate, payload, context):
        cycle = [];cycle.append(cycle);candidate['extensions']['future_cycle'] = cycle
        return candidate
    def refuse(candidate, action, payload, context):
        cycle = candidate['extensions']['future_cycle']
        assert cycle[0] is cycle
        seen.append('original refusal');raise RuntimeError('original cyclic constraint refusal')
    engine.register_command('fixture.cycle', reducer);engine.register_constraint('cycle-refusal', refuse)
    with pytest.raises(RuntimeError, match='original cyclic constraint refusal'):
        command(engine, world, state, 'fixture.cycle', {})
    assert seen == ['original refusal']
    assert engine.load_run(world['project'], state['run_id']) == state


def test_constraint_snapshot_cycle_still_refuses_durable_json(engine, world):
    state = create(engine, world);seen = []
    def reducer(candidate, payload, context):
        cycle = [];cycle.append(cycle);candidate['extensions']['future_cycle'] = cycle
        return candidate
    def observe(candidate, action, payload, context):
        cycle = candidate['extensions']['future_cycle']
        assert cycle[0] is cycle
        seen.append(True)
    engine.register_command('fixture.cycle-json', reducer);engine.register_constraint('cycle-observer', observe)
    with pytest.raises((ValueError, RecursionError)):
        command(engine, world, state, 'fixture.cycle-json', {})
    assert seen == [True]
    assert engine.load_run(world['project'], state['run_id']) == state


def test_constraint_snapshot_never_invokes_exotic_reducers(engine):
    calls = []
    class Exotic:
        def __reduce_ex__(self, protocol):
            calls.append(protocol);raise AssertionError('must not serialize exotic values')
    value = Exotic()
    assert engine._constraint_snapshot({'unknown': value}) is None
    assert calls == []


@pytest.mark.parametrize('kind', ['scalar', 'dict', 'list', 'str'])
def test_constraint_snapshot_uses_identity_without_metaclass_equality(engine, kind):
    calls = []
    base = {'scalar': object, 'dict': dict, 'list': list, 'str': str}[kind]
    target = dict if kind in ('dict', 'list') else str
    class ImpostorMeta(type):
        def __eq__(cls, other):
            calls.append('equality')
            return other is target
        __hash__ = type.__hash__
    class Impostor(base, metaclass=ImpostorMeta):
        def __reduce_ex__(self, protocol):
            calls.append('reducer')
            return (dict, ())
    assert engine._constraint_snapshot({'unknown': Impostor()}) is None
    assert calls == []


def test_constraint_snapshot_preserves_copy_byte_ceiling_and_serialization_fallback(engine, monkeypatch):
    import journal_storage
    monkeypatch.setattr(journal_storage, 'MAX_LOGICAL_BYTES', 1)
    assert engine._constraint_snapshot({'plain': [1, 2]}) is None
    def refuse(*args, **kwargs):
        raise ValueError('bounded serialization refusal')
    monkeypatch.setattr(engine.pickle, 'dumps', refuse)
    assert engine._constraint_snapshot({'plain': [1, 2]}) is None


@pytest.mark.parametrize('cycle', [False, True])
def test_bulk_state_copy_preserves_alias_order_and_independence(engine, monkeypatch, cycle):
    shared = {'z': [], 'a': 1}
    original = {'first': shared, 'second': shared}
    if cycle: shared['z'].append(original)
    def no_fallback(value):
        raise AssertionError('ordinary bulk graph must use exact builtin copy')
    monkeypatch.setattr(engine, 'deepcopy', no_fallback)
    a, b = engine._copy_state(original), engine._copy_state(original)
    assert a['first'] is a['second'] and b['first'] is b['second']
    assert a['first'] is not b['first'] and a['first'] is not shared
    assert list(a['first']) == ['z', 'a']
    if cycle: assert a['first']['z'][0] is a and b['first']['z'][0] is b
    a['first']['a'] = 9
    assert b['second']['a'] == shared['a'] == 1


def test_bulk_state_copy_exotic_fallback_does_not_serialize_reducers(engine, monkeypatch):
    calls = []
    class Exotic:
        def __deepcopy__(self, memo):
            calls.append('deepcopy');return {'copied': True}
        def __reduce_ex__(self, protocol):
            raise AssertionError('exotic reducer must never run')
    assert engine._copy_state({'future': Exotic()}) == {'future': {'copied': True}}
    assert calls == ['deepcopy']
    monkeypatch.setattr(engine, '_constraint_snapshot', lambda value: None)
    assert engine._copy_state({'ordinary': [1]}) == {'ordinary': [1]}


def test_bulk_state_copy_preparer_reducer_and_return_are_independent(engine, world):
    state = create(engine, world)
    captured = []
    def prepare(context, payload):
        context['state']['extensions']['hostile-preparer'] = ['changed']
        captured.append(context['state'])
        return payload
    def reduce(candidate, payload, context):
        assert 'hostile-preparer' not in candidate['extensions']
        candidate['extensions']['ordered-future'] = {'z': [1], 'a': [2]}
        captured.append(candidate)
        return candidate
    engine.register_command('fixture.bulk-copy', reduce)
    engine.register_preparer('fixture.bulk-copy', prepare)
    updated = command(engine, world, state, 'fixture.bulk-copy', {})
    updated['extensions']['ordered-future']['z'].append(99)
    assert captured[1]['extensions']['ordered-future']['z'] == [1]
    fresh = engine.load_run(world['project'], state['run_id'])
    assert fresh['extensions']['ordered-future']['z'] == [1]
    assert 'hostile-preparer' not in fresh['extensions']


@pytest.mark.parametrize('diagnostics, expected', [
    (['journal verification time budget exhausted; no partial state is accepted'], 'OPERATOR_JOURNAL_TIME_BUDGET'),
    (['foreign path or private value'], 'OPERATOR_OTHER_CURRENTNESS_REFUSAL'),
    ([], 'OPERATOR_OTHER_CURRENTNESS_REFUSAL'),
    (['journal verification time budget exhausted; no partial state is accepted', 'extra'], 'OPERATOR_OTHER_CURRENTNESS_REFUSAL'),
])
def test_operator_currentness_diagnostic_is_closed(diagnostics, expected):
    """Execute the exact diagnostic branch without repeating history creation."""
    import ast
    import inspect
    source = inspect.getsource(test_native_history_crosses_snapshot_limit_and_recovers_exactly)
    body = ast.parse(source).body[0].body
    branch = next(node for node in body if isinstance(node, ast.If)
                  and isinstance(node.test, ast.Compare)
                  and isinstance(node.test.left, ast.Subscript)
                  and isinstance(node.test.left.value, ast.Name)
                  and node.test.left.value.id == 'view')
    selected = ast.fix_missing_locations(ast.Module(body=[branch], type_ignores=[]))
    with pytest.raises(pytest.fail.Exception) as failure:
        exec(compile(selected, '<selected currentness diagnostic>', 'exec'),
             {'view': {'currentness': 'UNVERIFIABLE', 'diagnostics': diagnostics}, 'pytest': pytest})
    assert str(failure.value) == expected


@pytest.mark.parametrize('raw', [
    b'{"a":[1,2],"b":"literal [ ] { } : ,"}',
    '{"a":"unicodé 漢字","b":[true,false,null]}'.encode(),
    b'{"a":"escaped \\\\" ]","b":[]}',
    b'{"a":"line\\nslash\\\\","b":{}}',
    b'"unclosed [[[[', b'"""[[[', b'[[[[0]]]]',
    b'{"a":0,"a":1}', b'""""""', b'[] } {',
])
@pytest.mark.parametrize('depth,work', [(1, 2), (3, 8), (64, 16384)])
def test_compressed_scanner_keeps_legacy_depth_work_refusals(engine, monkeypatch, raw, depth, work):
    """Exact old lexical policy remains authoritative for every byte shape."""
    import re
    storage = engine.journal_storage
    monkeypatch.setattr(storage, 'MAX_DEPTH', depth)
    monkeypatch.setattr(storage, 'MAX_BLOCKS', work)

    def original(data):
        masked, strings = re.subn(rb'"[^"\\]*(?:\\.[^"\\]*)*"', b'""', data)
        if strings + sum(masked.count(bytes([c])) for c in (91, 123, 44, 58)) > work:
            raise ValueError('compressed snapshot leaf exceeds JSON work bound')
        nested = 0
        for match in re.finditer(rb'[\[\]{}]', masked):
            if match.group()[0] in (91, 123):
                nested += 1
                if nested > depth:
                    raise ValueError('compressed snapshot leaf exceeds JSON depth bound')
            else:
                nested -= 1

    def outcome(call):
        try:
            call(raw)
        except ValueError as error:
            return str(error)
        return None

    assert outcome(storage._compressed_json_bounds) == outcome(original)


def test_compressed_scanner_no_escape_path_avoids_per_string_regex(engine, monkeypatch):
    storage = engine.journal_storage
    calls = []
    real = storage.re.subn

    def counted(*args, **kwargs):
        calls.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(storage.re, 'subn', counted)
    storage._compressed_json_bounds(storage.canonical({'literal': '[{}]' * 2000, 'rows': [0, 1]}))
    assert calls == []
    storage._compressed_json_bounds(storage.canonical({'escaped': 'quote" and slash\\'}))
    storage._compressed_json_bounds(b'"unterminated [[[[')
    assert calls == [1, 1]


def test_compressed_scanner_still_checks_exact_bounds_after_warm_read(engine, monkeypatch):
    storage = engine.journal_storage
    raw = b'[[[0]]]'
    storage._compressed_json_bounds(raw)
    monkeypatch.setattr(storage, 'MAX_DEPTH', 2)
    with pytest.raises(ValueError, match='depth bound'):
        storage._compressed_json_bounds(raw)
    monkeypatch.setattr(storage, 'MAX_DEPTH', 64)
    monkeypatch.setattr(storage, 'MAX_BLOCKS', 2)
    with pytest.raises(ValueError, match='work bound'):
        storage._compressed_json_bounds(raw)
    monkeypatch.setattr(storage, 'MAX_BLOCKS', 3)
    storage._compressed_json_bounds(raw)


@pytest.mark.parametrize('raw', [b'{"b":0,"a":1}', b'{ "a":1}', b'{"a":0,"a":1}', b'{"a":NaN}', b'{"a":1e999}'])
def test_compressed_scanner_does_not_admit_noncanonical_leaf(engine, raw):
    import base64
    import zlib
    with pytest.raises((ValueError, OverflowError)):
        engine.journal_storage._leaf('zleaf', base64.b64encode(zlib.compress(raw)).decode())


def test_compressed_scanner_preserves_independent_mutable_leaf_reads(engine):
    import base64
    import zlib
    storage = engine.journal_storage
    raw = storage.canonical({'z': [1], 'a': {'b': 2}})
    packed = base64.b64encode(zlib.compress(raw)).decode()
    first = storage._leaf('zleaf', packed)
    second = storage._leaf('zleaf', packed)
    first['z'].append(3)
    first['a']['b'] = 9
    assert second == {'z': [1], 'a': {'b': 2}}
    with pytest.raises(ValueError, match='bound'):
        storage._leaf('zleaf', packed, len(raw) - 1)


@pytest.mark.parametrize('reader', ['leaf', 'block'])
def test_canonical_reader_matches_standard_encoder(reader):
    import base64, random, zlib
    rng = random.Random(4188)
    atoms = [None, True, False, 0, -1, 10**80, -0.0, 0.0, 1e-20, 1e20,
             'λ', 'é', '😀', '/', '\\', '"', '\\u001f']
    atoms.extend(chr(i) for i in range(128))
    values = atoms + [{'a': x, 'z': [x, {'é': x}]} for x in atoms]
    values.extend({str(i): rng.uniform(-1e90, 1e90) for i in range(20)} for _ in range(50))
    for value in values:
        raw = storage.canonical(value)
        if reader == 'leaf':
            actual = storage._leaf('zleaf', base64.b64encode(zlib.compress(raw)).decode())
        else:
            actual, used = storage._block_node(storage.BLOCK_PREFIX+zlib.compress(raw+b'\n'),limit=storage.MAX_BLOCK_BYTES)
            assert used == len(raw)+1
        assert actual == value
        assert storage.canonical(actual) == raw


@pytest.mark.parametrize('raw', [
    b' {"a":1}', b'{"a":1} ', b'{"a": 1}', b'{"a":1}\n',
    b'{"z":1,"a":2}', b'{"a":1,"a":1}', b'{"a":-0}', b'{"a":1.00}',
    b'{"a":1E+20}', b'{"a":1e20}', b'{"a":1e-7}', b'{"a":1e999}',
    b'{"a":NaN}', b'{"a":Infinity}', b'{"a":-Infinity}',
    b'{"a":"\\u03bb"}', b'{"a":"\\/"}', b'{"a":"\\u0008"}',
    b'{"a":"\\u001F"}', b'{"a":"\\ud800"}', b'{"a":"\\x00"}',
    b'\xef\xbb\xbf{}', '{}'.encode('utf-16'), '{}'.encode('utf-32'),
    b'{"a":"\xff"}', b'[]true', b'{"a":01}', b'{"a":+1}',
])
@pytest.mark.parametrize('reader', ['leaf', 'block'])
def test_canonical_reader_refusals_match_roundtrip_guard(raw, reader):
    import base64, zlib
    def old_guard():
        storage._compressed_json_bounds(raw)
        value=json.loads(raw,parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite')))
        if storage.canonical(value) != raw:
            raise ValueError('noncanonical')
    with pytest.raises((ValueError,UnicodeError,OverflowError)):
        old_guard()
    with pytest.raises((ValueError,UnicodeError,OverflowError)):
        if reader == 'leaf':
            storage._leaf('zleaf',base64.b64encode(zlib.compress(raw)).decode())
        else:
            storage._block_node(storage.BLOCK_PREFIX+zlib.compress(raw+b'\n'),limit=storage.MAX_BLOCK_BYTES)


@pytest.mark.parametrize('reader', ['leaf', 'block'])
def test_canonical_reader_avoids_reserializing_validated_values(monkeypatch, reader):
    import base64,zlib
    raw=storage.canonical({'a':[1,2.5,None], 'z':'λ quote" slash\\'})
    def forbidden(_):
        raise AssertionError('a parsed canonical value was serialized again')
    monkeypatch.setattr(storage,'canonical',forbidden)
    if reader == 'leaf':
        value=storage._leaf('zleaf',base64.b64encode(zlib.compress(raw)).decode())
    else:
        value,_=storage._block_node(storage.BLOCK_PREFIX+zlib.compress(raw+b'\n'),limit=storage.MAX_BLOCK_BYTES)
    assert value['a']==[1,2.5,None] and value['z']=='λ quote" slash\\'


def test_canonical_reader_reapplies_work_depth_and_returns_fresh_objects(monkeypatch):
    raw=storage.canonical({'a':{'items':[1]},'b':{'items':[1]}})
    first=storage._canonical_json(raw);second=storage._canonical_json(raw)
    first['a']['items'].append(2)
    assert first['b']==second['a']==second['b']=={'items':[1]}
    monkeypatch.setattr(storage,'MAX_DEPTH',1)
    with pytest.raises(ValueError,match='depth'):
        storage._canonical_json(raw)
    monkeypatch.setattr(storage,'MAX_DEPTH',64)
    monkeypatch.setattr(storage,'MAX_BLOCKS',1)
    with pytest.raises(ValueError,match='work'):
        storage._canonical_json(raw)


@pytest.mark.parametrize('raw', [
    b'{"a":0,"a":1}', b'{"a":{"b":0},"a":{"c":1}}',
    b'{"a":{"b":0,"b":1},"a":0}', b'[{"a":0,"a":1},{"b":2}]',
    b'{"a":[],"a":{"b":{"c":0,"c":1}}}',
    b'{"a":"literal : , { } -0","a":null}',
    b'{"a":{"b":0,"b":1},"z":{"b":2,"b":3}}',
    b'{"a":{"b":0,"b":1},"a":{"b":2,"b":3}}',
])
@pytest.mark.parametrize('reader', ['leaf', 'block'])
def test_canonical_member_count_refuses_duplicates_in_discarded_values(raw, reader):
    import base64
    import zlib
    import journal_storage as storage
    with pytest.raises(ValueError):
        if reader == 'leaf':
            storage._leaf('zleaf', base64.b64encode(zlib.compress(raw)).decode())
        else:
            storage._block_node(storage.BLOCK_PREFIX + zlib.compress(raw + b'\n'),
                                limit=storage.MAX_LOGICAL_BYTES)


@pytest.mark.parametrize('value', [
    {'a': ':,{}[]-0', 'b': [{'same': 1}, {'same': 2}]},
    {'a': '\\" : -0', 'b': {'a': 'é漢字', 'b': '\n\t\r\x00'}},
    [{'a': {'same': []}}, {'a': {'same': []}}],
    [0, -1, 0.0, -0.0, 1e-7, 1e20, {'a': -0.0}],
])
def test_canonical_member_count_accepts_exact_strings_numbers_and_fresh_values(value):
    import journal_storage as storage
    raw = storage.canonical(value)
    first = storage._canonical_json(raw)
    second = storage._canonical_json(raw)
    assert storage.canonical(first) == raw == storage.canonical(second)
    def mutable_ids(item):
        found = []
        if isinstance(item, dict):
            found.append(id(item))
            for child in item.values():
                found.extend(mutable_ids(child))
        elif isinstance(item, list):
            found.append(id(item))
            for child in item:
                found.extend(mutable_ids(child))
        return found
    first_ids, second_ids = mutable_ids(first), mutable_ids(second)
    assert len(first_ids) == len(set(first_ids))
    assert len(second_ids) == len(set(second_ids))
    assert not set(first_ids) & set(second_ids)


@pytest.mark.parametrize('raw', [b'-0', b'[-0]', b'{"a":-0}', b'[0,-0]',
                                 b'{"a":[-0]}', b'{"a":{"b":-0}}'])
def test_canonical_integer_negative_zero_remains_refused(raw):
    import journal_storage as storage
    with pytest.raises(ValueError, match='canonical'):
        storage._canonical_json(raw)


def test_canonical_key_shape_reuse_cannot_relax_next_parse_order_or_work(monkeypatch):
    import journal_storage as storage
    raw = storage.canonical([{'a': [], 'z': {}} for _ in range(20)])
    first = storage._canonical_json(raw)
    first[0]['a'].append('mutated')
    assert not first[1]['a']
    with pytest.raises(ValueError, match='canonical'):
        storage._canonical_json(b'{"z":0,"a":1}')
    monkeypatch.setattr(storage, 'MAX_BLOCKS', 2)
    with pytest.raises(ValueError, match='work'):
        storage._canonical_json(raw)
    monkeypatch.setattr(storage, 'MAX_BLOCKS', 16384)
    assert storage._canonical_json(raw)[0]['a'] == []


@pytest.mark.parametrize("kind", ["leaf", "object", "map", "list", "array", "text"])
def test_legacy_normalization_stream_is_exact_and_returns_independent_values(tmp_path, kind):
    left = {"z": {"β": 1, "a": ["\\", -0.0]}, "b": 2}
    right = {"a": {"é": 1, "A": 2}}
    if kind == "leaf": node, expected = [kind, left], left
    elif kind == "object": node, expected = [kind, [["z", ["leaf", left]], ["a", ["leaf", right]]]], {"z": left, "a": right}
    elif kind == "map": node, expected = [kind, [["leaf", left], ["leaf", right]]], {**left, **right}
    elif kind == "list": node, expected = [kind, [["leaf", [left]], ["leaf", [right]]]], [left, right]
    elif kind == "array": node, expected = [kind, [["leaf", left], ["leaf", right]]], [left, right]
    else: node, expected = [kind, [["leaf", "é\\"], ["leaf", "\n漢"]]], "é\\\n漢"
    home = tmp_path / "resources/autopilot-runs/01990000-0000-7000-8000-000000000777"
    home.mkdir(parents=True)
    raw = json.dumps(node, ensure_ascii=False).encode() + b"\n"
    digest = hashlib.sha256(raw).hexdigest()
    storage.materialize(home, {digest: raw})
    logical = storage.canonical(expected) + b"\n"
    descriptor = {storage.MARKER: 1, "root": digest, "sha256": hashlib.sha256(logical).hexdigest(), "logical_bytes": len(logical)}
    with storage.normalization_scope():
        first = storage.decode(home / "current.json", descriptor)
        second = storage.decode(home / "current.json", descriptor)
    assert first == second == expected
    if isinstance(expected, dict): assert list(first) == list(expected)
    if kind != "text":
        assert first is not second
        nested = first["z"] if kind == "object" else first if isinstance(first, dict) else first[0]
        assert list(nested["z"]) == ["β", "a"]
        nested["z"]["a"].append("changed")
        assert second == expected
    assert storage._NORMALIZATION.get() is None


def test_legacy_normalization_is_bounded_nested_fresh_and_cleared_on_cancel(tmp_path, monkeypatch):
    value = {"outer": ["x" * 400, {"z": 0, "a": 1}]}
    monkeypatch.setattr(storage, "INLINE_BYTES", 0)
    path = tmp_path / "resources/autopilot-runs/01990000-0000-7000-8000-000000000779/current.json"
    path.parent.mkdir(parents=True)
    raw_descriptor, blocks = storage.encode(value, codec=1)
    storage.materialize(path.parent, blocks)
    descriptor = json.loads(raw_descriptor)
    with storage.normalization_scope():
        storage.decode(path, descriptor)
        outer = storage._NORMALIZATION.get()
        assert outer["entries"] and outer["bytes"] <= storage.MAX_LOGICAL_BYTES
        before = outer["bytes"]
        try:
            with storage.normalization_scope():
                assert not storage._NORMALIZATION.get()["entries"]
                storage.decode(path, descriptor)
                assert outer["budget"]["bytes"] <= storage.MAX_LOGICAL_BYTES
                raise KeyboardInterrupt
        except KeyboardInterrupt: pass
        assert storage._NORMALIZATION.get() is outer and outer["budget"]["bytes"] == before
        monkeypatch.setattr(storage, "LEAF_BYTES", 3)
        with pytest.raises(ValueError): storage.decode(path, descriptor)
        assert not outer["entries"]
    assert storage._NORMALIZATION.get() is None


def test_legacy_normalization_hit_still_authenticates_and_charges_each_reference(tmp_path, monkeypatch):
    value = {"outer": ["x" * 400]}
    monkeypatch.setattr(storage, "INLINE_BYTES", 0)
    path = tmp_path / "resources/autopilot-runs/01990000-0000-7000-8000-000000000779/current.json"
    path.parent.mkdir(parents=True)
    raw_descriptor, blocks = storage.encode(value, codec=1)
    storage.materialize(path.parent, blocks)
    descriptor = json.loads(raw_descriptor)
    target = storage.home_for(path) / "state-blocks/v1" / (descriptor["root"] + ".json")
    with storage.normalization_scope():
        storage.decode(path, descriptor)
        original = target.read_bytes()
        before = target.stat()
        changed = original.replace(b"xxx", b"yyy", 1)
        assert changed != original and len(changed) == len(original)
        target.write_bytes(changed)
        os.utime(target, ns=(before.st_atime_ns, before.st_mtime_ns))
        with pytest.raises(ValueError, match="digest"): storage.decode(path, descriptor)
        target.write_bytes(original)
        assert storage.decode(path, descriptor) == value
    assert storage._NORMALIZATION.get() is None


def test_legacy_fragment_budget_fallback_and_compiler_share_residency(tmp_path, monkeypatch):
    value = {"z" + str(i): {"z": i, "a": i} for i in range(8)}
    raw = json.dumps(["map", [["leaf", value]]]).encode() + b"\n"
    digest = hashlib.sha256(raw).hexdigest()
    home = tmp_path / "resources/autopilot-runs/01990000-0000-7000-8000-000000000778"
    home.mkdir(parents=True); storage.materialize(home, {digest: raw})
    logical = storage.canonical(value) + b"\n"
    descriptor = {storage.MARKER: 1, "root": digest, "sha256": hashlib.sha256(logical).hexdigest(), "logical_bytes": len(logical)}
    monkeypatch.setattr(storage, "MAX_BLOCKS", 3)
    with storage.normalization_scope(), storage.compilation_scope():
        assert storage.decode(home / "current.json", descriptor) == value
        storage.encode(value, codec=2)
        assert storage._NORMALIZATION.get()["budget"]["bytes"] + storage._COMPILATION.get()["bytes"] <= storage.MAX_LOGICAL_BYTES


def test_legacy_nested_policy_change_releases_all_optional_residency(tmp_path, monkeypatch):
    value = {"x": "x" * 1000}
    monkeypatch.setattr(storage, "INLINE_BYTES", 0)
    home = tmp_path / "resources/autopilot-runs/01990000-0000-7000-8000-000000000780"
    home.mkdir(parents=True)
    raw, blocks = storage.encode(value, codec=1)
    storage.materialize(home, blocks)
    with storage.compilation_scope(), storage.normalization_scope():
        storage.decode(home / "current.json", json.loads(raw))
        outer = storage._NORMALIZATION.get()
        assert outer["entries"]
        with storage.normalization_scope():
            monkeypatch.setattr(storage, "MAX_LOGICAL_BYTES", 128)
            storage._normalization_memo()
            assert not outer["entries"]
            assert outer["budget"]["bytes"] == outer["budget"]["count"] == 0
            assert storage._COMPILATION.get()["bytes"] == 0
        assert not outer["entries"]
    assert storage._NORMALIZATION.get() is None


def test_legacy_normalization_copied_contexts_close_out_of_order(tmp_path, monkeypatch):
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    from contextvars import copy_context
    value = {"z": ["x" * 200], "a": 1}
    monkeypatch.setattr(storage, "INLINE_BYTES", 0)
    home = tmp_path / "resources/autopilot-runs/01990000-0000-7000-8000-000000000781"
    home.mkdir(parents=True)
    raw, blocks = storage.encode(value, codec=1)
    storage.materialize(home, blocks)
    descriptor = json.loads(raw)
    async def run():
        first_entered, second_entered, first_closed = (asyncio.Event() for _ in range(3))
        async def first():
            with storage.normalization_scope():
                assert storage.decode(home / "current.json", descriptor) == value
                first_entered.set()
                await second_entered.wait()
            first_closed.set()
        async def second():
            await first_entered.wait()
            with storage.normalization_scope():
                assert storage.decode(home / "current.json", descriptor) == value
                second_entered.set()
                await first_closed.wait()
        await asyncio.gather(first(), second())
    with storage.normalization_scope():
        outer = storage._NORMALIZATION.get()
        asyncio.run(run())
        assert storage._NORMALIZATION.get() is outer
        assert outer["budget"]["bytes"] == outer["budget"]["count"] == 0
        def threaded():
            with storage.normalization_scope():
                return storage.decode(home / "current.json", descriptor)
        with ThreadPoolExecutor(max_workers=2) as pool:
            contexts = [copy_context(), copy_context()]
            results = list(pool.map(lambda ctx: ctx.run(threaded), contexts))
        assert results == [value, value] and results[0] is not results[1]
        assert outer["budget"]["bytes"] == outer["budget"]["count"] == 0
    assert storage._NORMALIZATION.get() is None


def test_legacy_normalization_inherited_closed_scope_cannot_retain_entries(tmp_path, monkeypatch):
    from contextvars import copy_context
    monkeypatch.setattr(storage, "INLINE_BYTES", 0)
    value = {"z": "x" * 200}
    home = tmp_path / "resources/autopilot-runs/01990000-0000-7000-8000-000000000782"
    home.mkdir(parents=True)
    raw, blocks = storage.encode(value, codec=1)
    storage.materialize(home, blocks)
    descriptor = json.loads(raw)
    with storage.normalization_scope():
        storage.decode(home / "current.json", descriptor)
        old = storage._NORMALIZATION.get()
        retained_context = copy_context()
        assert old["entries"]
    assert old["closed"] and not old["entries"] and old["bytes"] == 0
    assert retained_context.run(storage._normalization_memo) is None
    assert retained_context.run(storage.decode, home / "current.json", descriptor) == value
    assert not old["entries"] and old["budget"]["bytes"] == 0
    def fresh():
        with storage.normalization_scope():
            memo = storage._NORMALIZATION.get()
            assert memo["budget"] is not old["budget"]
            assert storage.decode(home / "current.json", descriptor) == value
        assert memo["closed"] and not memo["entries"]
    retained_context.run(fresh)


@pytest.mark.parametrize('change', ['replacement', 'symlink', 'directory', 'permissions'])
def test_scoped_handles_revalidate_path_and_reopen_changed_metadata(tmp_path, monkeypatch, change):
    directory = tmp_path / 'blocks'
    directory.mkdir()
    target = directory / 'a.json'
    target.write_bytes(b'fresh')
    parent = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    original_open = os.open
    opened = []
    def capture(name, flags, *args, **kwargs):
        if name == 'a.json':
            opened.append(name)
            if change == 'permissions' and len(opened) > 1:
                raise PermissionError('synthetic changed permission admission')
        return original_open(name, flags, *args, **kwargs)
    monkeypatch.setattr(os, 'open', capture)
    try:
        with storage.normalization_scope():
            memo = storage._normalization_memo()
            assert storage._read_block(parent, 'a.json', 20, memo, []) == b'fresh'
            fd = next(iter(memo['handles'].values()))[0]
            if change == 'permissions':
                target.chmod(0o400)
            else:
                target.rename(directory / 'retained-original')
                if change == 'replacement': target.write_bytes(b'other')
                elif change == 'symlink': target.symlink_to(directory / 'retained-original')
                else: target.mkdir()
            if change == 'replacement':
                assert storage._read_block(parent, 'a.json', 20, memo, []) == b'other'
                assert len(opened) == 2
            else:
                with pytest.raises((ValueError, OSError)):
                    storage._read_block(parent, 'a.json', 20, memo, [])
            assert not memo['handles']
            with pytest.raises(OSError): os.fstat(fd)
            if change == 'permissions': assert len(opened) == 2
    finally:
        os.close(parent)


def test_scoped_handle_reuse_reads_each_occurrence_and_closes_after_cancel(tmp_path, monkeypatch):
    from contextvars import copy_context
    target = tmp_path / 'a.json'
    target.write_bytes(b'fresh')
    parent = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    original_open, original_pread = os.open, os.pread
    calls = {'open': 0, 'pread': 0}
    def capture_open(*args, **kwargs):
        calls['open'] += 1
        return original_open(*args, **kwargs)
    def capture_read(*args, **kwargs):
        calls['pread'] += 1
        return original_pread(*args, **kwargs)
    monkeypatch.setattr(os, 'open', capture_open)
    monkeypatch.setattr(os, 'pread', capture_read)
    try:
        with pytest.raises(KeyboardInterrupt):
            with storage.normalization_scope():
                memo = storage._normalization_memo()
                for _ in range(3):
                    assert storage._read_block(parent, 'a.json', 20, memo, []) == b'fresh'
                assert calls == {'open': 1, 'pread': 3}
                fd = next(iter(memo['handles'].values()))[0]
                copied = copy_context()
                raise KeyboardInterrupt
        with pytest.raises(OSError): os.fstat(fd)
        assert memo['closed'] and not memo['handles']
        assert memo['budget']['bytes'] == memo['budget']['count'] == 0
        assert copied.run(storage._normalization_memo) is None
    finally:
        os.close(parent)


def test_scoped_handle_failed_initial_fstat_closes_unadopted_descriptor(tmp_path, monkeypatch):
    (tmp_path / 'a.json').write_bytes(b'fresh')
    parent = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    original_open, original_fstat = os.open, os.fstat
    created = []
    def capture(*args, **kwargs):
        fd = original_open(*args, **kwargs)
        created.append(fd)
        return fd
    def fail(fd):
        if fd in created: raise OSError('synthetic post-open fstat failure')
        return original_fstat(fd)
    monkeypatch.setattr(os, 'open', capture)
    monkeypatch.setattr(os, 'fstat', fail)
    try:
        with storage.normalization_scope():
            memo = storage._normalization_memo()
            with pytest.raises(OSError, match='post-open'):
                storage._read_block(parent, 'a.json', 20, memo, [])
            assert not memo['handles'] and memo['budget']['count'] == 0
        assert len(created) == 1
        with pytest.raises(OSError): original_fstat(created[0])
    finally:
        os.close(parent)


@pytest.mark.parametrize('bound', ['bytes', 'entries'])
def test_scoped_handles_share_existing_compilation_allowance(tmp_path, monkeypatch, bound):
    (tmp_path / 'a.json').write_bytes(b'fresh')
    parent = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        with storage.compilation_scope(), storage.normalization_scope():
            compiler = storage._COMPILATION.get()
            if bound == 'bytes': compiler['bytes'] = storage.MAX_LOGICAL_BYTES
            else: compiler['entries'] = {str(i): () for i in range(storage.MAX_BLOCKS)}
            memo = storage._normalization_memo()
            assert storage._read_block(parent, 'a.json', 20, memo, []) == b'fresh'
            assert not memo['handles']
            assert memo['budget']['bytes'] + compiler['bytes'] <= storage.MAX_LOGICAL_BYTES
            assert memo['budget']['count'] + len(compiler['entries']) <= storage.MAX_BLOCKS
    finally:
        os.close(parent)


def subtree_plan_fixture(tmp_path):
    home = tmp_path / 'resources/autopilot-runs/01990000-0000-7000-8000-000000000787'
    home.mkdir(parents=True)
    blocks, refs, expected = {}, [], {}
    for index in range(5):
        value = {'z': ['retained-' + str(index) + ':' + 'x' * 600], 'a': index}
        raw = json.dumps(['leaf', value]).encode() + b'\n'
        digest = hashlib.sha256(raw).hexdigest()
        blocks[digest] = raw
        refs.append(['field-' + str(index), digest])
        expected['field-' + str(index)] = value
    raw = json.dumps(['object', refs]).encode() + b'\n'
    root = hashlib.sha256(raw).hexdigest()
    blocks[root] = raw
    storage.materialize(home, blocks)
    logical = storage.canonical(expected) + b'\n'
    descriptor = {storage.MARKER: 1, 'root': root,
                  'sha256': hashlib.sha256(logical).hexdigest(), 'logical_bytes': len(logical)}
    return home / 'current.json', descriptor, blocks, expected


def test_subtree_plan_hit_authenticates_all_dependencies_and_copies_values(tmp_path, monkeypatch):
    path, descriptor, blocks, expected = subtree_plan_fixture(tmp_path)
    original_read, original_node = storage._read_block, storage._block_node
    reads, parses = [], []
    def read(parent, name, limit, memo, identity):
        reads.append(name)
        return original_read(parent, name, limit, memo, identity)
    def node(raw, *, limit):
        parses.append(len(raw))
        return original_node(raw, limit=limit)
    monkeypatch.setattr(storage, '_read_block', read)
    monkeypatch.setattr(storage, '_block_node', node)
    with storage.normalization_scope():
        first = storage.decode(path, descriptor)
        memo = storage._normalization_memo()
        plan = memo['plans'][(descriptor['root'], False)]
        assert set(plan[3]) == set(blocks) and plan[4] == 6 and plan[7] == 1
        reads.clear(); parses.clear()
        second = storage.decode(path, descriptor)
        assert set(reads) == {name + '.json' for name in blocks}
        assert len(reads) == 6 and not parses
        first['field-0']['z'].append('changed')
        assert second == expected and first != second
        assert list(second['field-0']) == ['z', 'a']
    assert not memo['plans'] and memo['budget']['count'] == 0


@pytest.mark.parametrize('fault', ['changed', 'missing', 'symlink'])
def test_subtree_plan_hit_never_trusts_a_retained_dependency(tmp_path, fault):
    path, descriptor, blocks, expected = subtree_plan_fixture(tmp_path)
    child = next(key for key in blocks if key != descriptor['root'])
    target = path.parent / 'state-blocks/v1' / (child + '.json')
    with storage.normalization_scope():
        assert storage.decode(path, descriptor) == expected
        assert storage._normalization_memo()['plans']
        if fault == 'changed':
            before = target.stat()
            target.write_bytes(target.read_bytes().replace(b'retained', b'mutated!', 1))
            os.utime(target, ns=(before.st_atime_ns, before.st_mtime_ns))
        else:
            target.rename(target.with_suffix('.retained'))
            if fault == 'symlink': target.symlink_to(target.with_suffix('.retained'))
        with pytest.raises((OSError, ValueError)):
            storage.decode(path, descriptor)


def test_subtree_plan_composition_charges_every_reference_under_original_limit(tmp_path, monkeypatch):
    path, descriptor, blocks, expected = subtree_plan_fixture(tmp_path)
    raw = json.dumps(['array', [descriptor['root']] * 3]).encode() + b'\n'
    digest = hashlib.sha256(raw).hexdigest()
    storage.materialize(path.parent, {digest: raw})
    logical = storage.canonical([expected] * 3) + b'\n'
    outer = {storage.MARKER: 1, 'root': digest,
             'sha256': hashlib.sha256(logical).hexdigest(), 'logical_bytes': len(logical)}
    monkeypatch.setattr(storage, 'MAX_BLOCKS', 16)
    with storage.normalization_scope():
        assert storage.decode(path, descriptor) == expected
        assert (descriptor['root'], False) in storage._normalization_memo()['plans']
        with pytest.raises(ValueError, match='bound'):
            storage.decode(path, outer)


def test_subtree_plan_closes_with_copied_context_and_policy_change(tmp_path, monkeypatch):
    from contextvars import copy_context
    path, descriptor, blocks, expected = subtree_plan_fixture(tmp_path)
    with storage.normalization_scope():
        assert storage.decode(path, descriptor) == expected
        memo = storage._normalization_memo()
        assert memo['plans']
        copied = copy_context()
        monkeypatch.setattr(storage, 'MAX_DEPTH', 0)
        with pytest.raises(ValueError, match='bound'):
            storage.decode(path, descriptor)
        assert not memo['plans']
    assert copied.run(storage._normalization_memo) is None
    assert memo['closed'] and not memo['plans']


def test_subtree_plan_optional_admission_precedes_payload_serialization(monkeypatch):
    with storage.normalization_scope():
        memo = storage._NORMALIZATION.get()
        monkeypatch.setattr(storage.marshal, 'dumps', lambda *_a: pytest.fail('rejected plan serialized'))
        raw = b'{}'
        assert storage._remember_plan(memo, ('a' * 64, False), {}, raw, None,
                                      (), 4, storage.LEAF_BYTES * 8 + 1, 2, 1) == raw
        assert not memo['plans'] and not memo['budget']['count']


def test_subtree_plan_residency_leaves_existing_budget_for_leaf_compilation(monkeypatch):
    monkeypatch.setattr(storage, 'MAX_LOGICAL_BYTES', 64 * 1024)
    with storage.normalization_scope():
        memo = storage._NORMALIZATION.get()
        for index in range(12):
            value = {'x': str(index) + 'x' * 1800}
            raw = storage.canonical(value)
            storage._remember_plan(memo, (f'{index:064x}', False), value, raw, None,
                                   (), 4, len(raw), len(raw), 1)
            assert sum(item[-1] for item in memo['plans'].values()) <= storage.MAX_LOGICAL_BYTES // 4
            assert memo['bytes'] == memo['budget']['bytes'] <= storage.MAX_LOGICAL_BYTES
        assert memo['plans'] and len(memo['plans']) < 12
    assert memo['bytes'] == memo['budget']['bytes'] == 0


@pytest.mark.parametrize('variant', ['unicode', 'numeric', 'nested-digest'])
def test_streamed_event_authentication_avoids_full_snapshot_encoding(tmp_path, monkeypatch, variant):
    values = {'unicode': {'é': '\\"\n漢', 'A': ['😀', '\u0000']},
              'numeric': {'minus': -0.0, 'float': 1.234e-20, 'integer': 123456789},
              'nested-digest': {'digest': {'digest': 'retained'}, 'text': '"digest":"outside"'}}
    value = {'schema_version': 1, 'actor': {'id': 'fixture'}, 'state': {
        'run_id': '01990000-0000-7000-8000-000000000799', 'revision': 1,
        'schema_version': 1, 'payload': values[variant]}}
    body_digest = hashlib.sha256(storage.canonical(value)).hexdigest()
    value['digest'] = body_digest
    home = tmp_path / 'resources/autopilot-runs/01990000-0000-7000-8000-000000000799'
    home.mkdir(parents=True)
    node = ['object', [[key, ['leaf', item]] for key, item in value.items()]]
    raw = json.dumps(node, ensure_ascii=False).encode() + b'\n'
    physical = hashlib.sha256(raw).hexdigest()
    storage.materialize(home, {physical: raw})
    logical = storage.canonical(value) + b'\n'
    descriptor = {storage.MARKER: 1, 'root': physical,
                  'sha256': hashlib.sha256(logical).hexdigest(), 'logical_bytes': len(logical)}
    canonical = storage.canonical
    def no_whole_snapshot(item):
        assert item != value, 'whole snapshot was encoded again'
        return canonical(item)
    monkeypatch.setattr(storage, 'canonical', no_whole_snapshot)
    with storage.normalization_scope():
        first = storage.decode(home/'current.json', descriptor)
        second = storage.decode(home/'current.json', descriptor)
        assert (physical, False) in storage._NORMALIZATION.get()['plans']
        assert first == second == value
        assert first.verified_body_digest == second.verified_body_digest == body_digest
        assert first['state'] is not second['state']
        first['state']['modified'] = True
        assert second == value
    for field, changed in [('sha256', '0' * 64), ('logical_bytes', len(logical) - 1)]:
        with pytest.raises(ValueError, match='logical content'):
            storage.decode(home/'current.json', {**descriptor, field: changed})


def test_stream_batching_preserves_every_byte_and_bounds_small_chunk_buffer(monkeypatch):
    monkeypatch.setattr(storage, 'LEAF_BYTES', 7)
    parts = [b'', b'{', b'"a":', memoryview(b'123456789'), b',', b'"b"', b':', b'[]', b'}']
    batches = list(storage._stream_batches(iter(parts)))
    assert b''.join(batches) == b''.join(parts)
    assert all(len(piece) <= 7 or piece is parts[3] for piece in batches)
    assert len(batches) < len([piece for piece in parts if piece])


def test_stream_index_flattens_map_routing_and_preserves_interleaved_members():
    import journal_storage
    raw = b'{"a":1,"c":3}'
    leaf = ("leaf", raw, (("a", 1, 6), ("c", 7, 12)))
    child = ("leaf", b'2', None)
    fields = journal_storage._stream_index(leaf) + [("b", b'"b"', child, 0, 0)]
    fields.sort(key=lambda item: item[0])
    stream = ("members", tuple(fields), None)
    assert b"".join(journal_storage._stream_value(stream)) == b'{"a":1,"b":2,"c":3}'
    contiguous = ("members", tuple(journal_storage._stream_index(leaf)), None)
    parts = list(journal_storage._stream_value(contiguous))
    assert len(parts) == 3 and bytes(parts[1]) == b'"a":1,"c":3'
    assert parts[1].obj is raw


def test_iterative_stream_flattens_nested_list_and_text_interiors():
    import journal_storage
    leaf = lambda raw: ("leaf", raw, None)
    lists = ("list", (("list", (leaf(b'[1]'), leaf(b'[2]')), None), leaf(b'[3,4]')), None)
    texts = ("text", (("text", (leaf(b'"a"'), leaf(b'"\\n"')), None), leaf(b'"b"')), None)
    root = ("array", (lists, texts), None)
    assert b"".join(journal_storage._stream_value(root)) == b'[[1,2,3,4],"a\\nb"]'


def test_offset_plan_members_reference_one_canonical_buffer(tmp_path):
    path, descriptor, blocks, expected = subtree_plan_fixture(tmp_path)
    with storage.normalization_scope():
        assert storage.decode(path, descriptor) == expected
        plan = storage._NORMALIZATION.get()['plans'][(descriptor['root'], False)]
        raw, ranges = plan[1:3]
        assert all(isinstance(start, int) and isinstance(end, int) for key, start, end in ranges)
        assert [key for key, start, end in ranges] == sorted(expected)
        assert b'{' + b','.join(raw[start:end] for key, start, end in ranges) + b'}' == raw
        second = storage.decode(path, descriptor)
        assert second == expected
        second['field-0']['z'].append('new')
        assert storage.decode(path, descriptor) == expected


def test_offset_plan_preflight_refuses_before_canonical_copy(monkeypatch):
    with storage.normalization_scope():
        memo = storage._NORMALIZATION.get()
        monkeypatch.setattr(storage, 'MAX_LOGICAL_BYTES', 16)
        assert not storage._plan_preflight(memo, 4, 20, 20)


def test_offset_map_composition_handles_disjoint_and_interleaved_ranges():
    def leaf(raw, ranges):
        return ("leaf", raw, ranges)
    a = leaf(b'{"a":1,"c":3}', (("a", 1, 6), ("c", 7, 12)))
    b = leaf(b'{"b":2}', (("b", 1, 6),))
    raw, ranges = storage._pack_map([a, b])
    assert raw == b'{"a":1,"b":2,"c":3}'
    assert b'{' + b','.join(raw[start:end] for _, start, end in ranges) + b'}' == raw
    d = leaf(b'{"d":4}', (("d", 1, 6),))
    assert storage._pack_map([d, a])[0] == b'{"a":1,"c":3,"d":4}'


def test_composed_buffers_enforce_logical_bound_before_join(monkeypatch):
    monkeypatch.setattr(storage, 'MAX_LOGICAL_BYTES', 4)
    with pytest.raises(ValueError, match='logical content'):
        storage._join_canonical([b'12345'], 5)
    with pytest.raises(ValueError, match='logical content'):
        storage._pack_stream(('array', [('leaf', b'1234', None)], None))


def _verified_projection_fixture(tmp_path, *, missing_digest=False):
    import journal_storage as store
    home = tmp_path / "resources/autopilot-runs/01990000-0000-7000-8000-000000000777"
    blocks = {}
    def block(node):
        raw = store.canonical(node) + b"\n"
        key = hashlib.sha256(raw).hexdigest()
        blocks[key] = raw
        return key
    hidden = [block(["leaf", {"hidden": i}]) for i in range(3)]
    hidden_root = block(["array", hidden])
    state = {"run_id": home.name, "revision": 1, "schema_version": 1,
             "status": "recovering", "hidden": [{"hidden": i} for i in range(3)],
             "extensions": {"workflow": {"progress": {"task": [{"meaningful": True, "attempt_id": "a", "evidence_ids": []}]}}}}
    body = {"state": state, "revision": 1, "schema_version": 1,
            "previous_digest": "", "command_id": "one"}
    event = dict(body, digest=hashlib.sha256(store.canonical(body)).hexdigest())
    if missing_digest:
        event.pop("digest")
    state_root = block(["object", [[key, hidden_root if key == "hidden" else block(["leaf", value])] for key, value in state.items()]])
    root = block(["object", [[key, state_root if key == "state" else block(["leaf", value])] for key, value in event.items()]])
    store.materialize(home, blocks)
    raw = store.canonical(event) + b"\n"
    descriptor = {store.MARKER: 1, "root": root, "sha256": hashlib.sha256(raw).hexdigest(), "logical_bytes": len(raw)}
    return home / "events/000000000001.json", descriptor, event, hidden_root, hidden


def test_verified_projection_cache_is_separate_and_selected_values_are_independent(tmp_path):
    import journal_storage as store
    path, descriptor, event, hidden_root, _ = _verified_projection_fixture(tmp_path)
    with store.normalization_scope():
        first = store.decode_event_projection(path, descriptor)
        assert not isinstance(first, dict)
        assert (hidden_root, "canonical-skip") in store._NORMALIZATION.get()["plans"]
        assert "hidden" not in first.identity
        first.identity["extensions"]["workflow"]["progress"]["task"][0]["evidence_ids"].append("mutation")
        second = store.decode_event_projection(path, descriptor)
        assert second.identity["extensions"]["workflow"]["progress"]["task"][0]["evidence_ids"] == []
        assert store.decode(path, descriptor) == event
        assert store.decode_event_projection(path, descriptor, include_full_state=True).full_state == event["state"]
        assert store._normalization_resident()[0] <= store.MAX_LOGICAL_BYTES


def test_verified_projection_rejects_absent_event_digest(tmp_path):
    import journal_storage as store
    path, descriptor, _, _, _ = _verified_projection_fixture(tmp_path, missing_digest=True)
    with pytest.raises(ValueError, match="complete event body authentication"):
        store.decode_event_projection(path, descriptor)


@pytest.mark.parametrize("fault", ["content", "missing", "symlink"])
def test_verified_projection_plan_requires_every_fresh_hidden_dependency(tmp_path, fault):
    import journal_storage as store
    path, descriptor, _, _, hidden = _verified_projection_fixture(tmp_path)
    target = store.home_for(path) / "state-blocks/v1" / (hidden[1] + ".json")
    with store.normalization_scope():
        store.decode_event_projection(path, descriptor)
        if fault == "content":
            target.write_bytes(target.read_bytes().replace(b":1", b":9"))
        else:
            preserved = target.with_suffix(".preserved")
            target.rename(preserved)
            if fault == "symlink":
                target.symlink_to(preserved)
        with pytest.raises((OSError, ValueError)):
            store.decode_event_projection(path, descriptor)


def test_scoped_handle_probation_scan_retains_reused_handles_and_fresh_reads(tmp_path, monkeypatch):
    for index in range(304):
        (tmp_path / f'{index}.json').write_bytes(str(index).encode())
    parent = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    original_open, original_read = os.open, os.pread
    calls = {'open': 0, 'pread': 0}
    def opened(*args, **kwargs):
        calls['open'] += 1
        return original_open(*args, **kwargs)
    def read(*args, **kwargs):
        calls['pread'] += 1
        return original_read(*args, **kwargs)
    monkeypatch.setattr(os, 'open', opened)
    monkeypatch.setattr(os, 'pread', read)
    try:
        with storage.normalization_scope():
            memo = storage._normalization_memo()
            for _ in range(2):
                for index in range(4):
                    assert storage._read_block(parent, f'{index}.json', 10, memo, []) == str(index).encode()
            hot = {key: value[0] for key, value in memo['handles'].items()}
            for index in range(4, 304):
                assert storage._read_block(parent, f'{index}.json', 10, memo, []) == str(index).encode()
                assert sum(len(item['handles']) for item in memo['budget']['memos']) <= 256
            assert all(memo['handles'][key][0] == fd for key, fd in hot.items())
            for index in range(4):
                assert storage._read_block(parent, f'{index}.json', 10, memo, []) == str(index).encode()
            assert calls == {'open': 304, 'pread': 312}
            assert memo['budget']['count'] == len(memo['handles']) == 256
        assert not memo['handle_probation'] and not memo['handle_protected']
        assert memo['budget']['bytes'] == memo['budget']['count'] == 0
    finally:
        os.close(parent)


def test_decode_directory_binding_failure_closes_descriptor(tmp_path, monkeypatch):
    path, descriptor, _, _, _ = _verified_projection_fixture(tmp_path)
    original_open, original_stat = os.open, os.fstat
    opened = []
    def capture(name, *args, **kwargs):
        fd = original_open(name, *args, **kwargs)
        if name == 'v1': opened.append(fd)
        return fd
    def fail(fd):
        if fd in opened: raise OSError('synthetic directory binding failure')
        return original_stat(fd)
    monkeypatch.setattr(os, 'open', capture)
    monkeypatch.setattr(os, 'fstat', fail)
    with pytest.raises(OSError, match='directory binding'):
        storage.decode_event_projection(path, descriptor)
    assert len(opened) == 1
    with pytest.raises(OSError): original_stat(opened[0])
    assert storage._DIRECTORY_IDENTITY.get() is None


def test_decode_directory_binding_invalidates_inherited_context(tmp_path, monkeypatch):
    from contextvars import copy_context
    path, descriptor, event, _, _ = _verified_projection_fixture(tmp_path)
    original = storage._read_block
    captured = []
    def read(parent, name, limit, memo, identity):
        binding = storage._DIRECTORY_IDENTITY.get()
        assert binding[0] == parent and binding[2] is True
        captured.append((copy_context(), binding))
        return original(parent, name, limit, memo, identity)
    monkeypatch.setattr(storage, '_read_block', read)
    with storage.normalization_scope():
        actual = storage.decode_event_projection(path, descriptor)
        assert actual.header['digest'] == event['digest']
        assert captured
        assert all(binding[2] is False for _, binding in captured)
        assert all(context.run(storage._DIRECTORY_IDENTITY.get)[2] is False for context, _ in captured)
    assert storage._DIRECTORY_IDENTITY.get() is None


def test_projection_skipped_leaf_shape_avoids_discarded_value_deserialization(tmp_path, monkeypatch):
    path, descriptor, event, hidden_root, hidden = _verified_projection_fixture(tmp_path)
    with storage.normalization_scope():
        storage.decode_event_projection(path, descriptor)
        memo = storage._normalization_memo()
        old = memo['plans'].pop((hidden_root, 'canonical-skip'))
        memo['bytes'] -= old[-1]
        memo['budget']['bytes'] -= old[-1]
        memo['budget']['count'] -= 1
        blocked = {memo['entries'][key][0] for key in hidden}
        original = storage.marshal.loads
        def loads(raw):
            assert raw not in blocked, 'discarded hidden values were deserialized'
            return original(raw)
        monkeypatch.setattr(storage.marshal, 'loads', loads)
        assert storage.decode_event_projection(path, descriptor).header['digest'] == event['digest']
        assert (hidden_root, 'canonical-skip') in memo['plans']


def test_plan_resident_accounting_all_mutations_are_exact():
    from collections import OrderedDict
    cache = storage._PlanCache()
    def exact():
        assert cache.retained_bytes == sum(value[-1] for value in cache.values())
        assert cache.retained_bytes >= 0
    cache['a'] = ('a', 7)
    exact()
    cache['b'] = ('b', 19)
    exact()
    cache['a'] = ('replaced', 3)
    exact()
    cache.move_to_end('a', last=False)
    exact()
    cache.update({'c': ('c', 8)}, d=('d', 2))
    exact()
    assert cache.setdefault('c', ('ignored', 99)) == ('c', 8)
    cache.setdefault('e', ('e', 4))
    exact()
    cache |= OrderedDict([('b', ('changed', 1)), ('f', ('f', 5))])
    exact()
    copy = cache.copy()
    assert copy.retained_bytes == cache.retained_bytes and list(copy.items()) == list(cache.items())
    assert cache.pop('missing', None) is None
    with pytest.raises(KeyError): cache.pop('missing')
    exact()
    cache.popitem(last=False)
    exact()
    cache.popitem()
    exact()
    del cache['b']
    exact()
    cache.pop('c')
    exact()
    before = list(cache.items()), cache.retained_bytes
    with pytest.raises(ValueError): cache['bad'] = ('bad', -1)
    assert (list(cache.items()), cache.retained_bytes) == before
    cache.clear()
    exact()
    assert cache.retained_bytes == 0
    assert copy.retained_bytes > 0


def test_plan_resident_accounting_admission_eviction_policy_and_nested_scope(tmp_path, monkeypatch):
    path, descriptor, _, _, _ = _verified_projection_fixture(tmp_path)
    def exact(memo):
        assert memo['plans'].retained_bytes == sum(value[-1] for value in memo['plans'].values())
        assert memo['budget']['bytes'] >= sum(item['plans'].retained_bytes for item in memo['budget']['memos'])
    with storage.normalization_scope():
        outer = storage._normalization_memo()
        storage.decode_event_projection(path, descriptor)
        assert outer['plans'].retained_bytes > 0
        exact(outer)
        with storage.normalization_scope():
            inner = storage._normalization_memo()
            storage.decode_event_projection(path, descriptor)
            assert inner['plans'].retained_bytes > 0
            exact(inner)
            assert inner['budget'] is outer['budget']
            # The same admission owner evicts old pure plans under its byte cap.
            monkeypatch.setattr(storage, 'MAX_LOGICAL_BYTES', outer['budget']['bytes'] + 256)
            current = storage._normalization_memo()
            assert current is inner
            assert inner['plans'].retained_bytes == outer['plans'].retained_bytes == 0
            assert inner['budget']['bytes'] == inner['budget']['count'] == 0
            exact(inner)
        assert inner['plans'].retained_bytes == 0 and inner['closed']
        exact(outer)
    assert outer['plans'].retained_bytes == 0 and outer['closed']


def test_plan_resident_accounting_owner_eviction_and_compiler_pressure(tmp_path, monkeypatch):
    del tmp_path
    with storage.compilation_scope(), storage.normalization_scope():
        memo = storage._normalization_memo()
        compiler = storage._COMPILATION.get()
        monkeypatch.setattr(storage, 'MAX_LOGICAL_BYTES', 2048)
        memo = storage._normalization_memo()
        for index in range(12):
            raw = storage.canonical({'key': 'value' * 10})
            storage._remember_plan(memo, (str(index), False), {'key': 'value' * 10}, raw,
                                   None, ('a', 'b', 'c', 'd'), 4, 100, 100, 2)
            assert memo['plans'].retained_bytes == sum(value[-1] for value in memo['plans'].values())
            assert memo['budget']['bytes'] == memo['plans'].retained_bytes
            assert memo['budget']['bytes'] <= storage.MAX_LOGICAL_BYTES
        assert 0 < len(memo['plans']) < 12
        compiler['bytes'] = storage.MAX_LOGICAL_BYTES
        memo = storage._normalization_memo()
        assert memo['plans'].retained_bytes == 0
        assert memo['budget']['bytes'] == memo['budget']['count'] == 0
        assert compiler['bytes'] == 0


def test_plan_resident_accounting_cancellation_closes_all_residency(tmp_path):
    from contextvars import copy_context
    path, descriptor, _, _, _ = _verified_projection_fixture(tmp_path)
    with pytest.raises(KeyboardInterrupt):
        with storage.normalization_scope():
            memo = storage._normalization_memo()
            storage.decode_event_projection(path, descriptor)
            assert memo['plans'].retained_bytes > 0
            copied = copy_context()
            raise KeyboardInterrupt
    assert memo['plans'].retained_bytes == memo['budget']['bytes'] == memo['budget']['count'] == 0
    assert copied.run(storage._normalization_memo) is None


def test_member_token_coalescing_preserves_framing_and_leaf_bound(monkeypatch):
    monkeypatch.setattr(storage, 'LEAF_BYTES', 257)
    value = {f'{index:05}': f'雪-{index}' for index in range(1000)}
    fields = []
    for key, item in value.items():
        raw = storage.canonical({key: item})
        fields.append((key, raw, None, 1, len(raw) - 1))
    node = ('members', fields, None)
    chunks = list(storage._stream_value(node))
    assert b''.join(chunks) == storage.canonical(value)
    assert all(len(chunk) <= storage.LEAF_BYTES for chunk in chunks)
    assert len(chunks) < len(fields) // 5
    assert b''.join(storage._stream_value(('interior', node, None))) == storage.canonical(value)[1:-1]
    assert b''.join(storage._stream_value(('members', (), None))) == b'{}'
    assert b''.join(storage._stream_value(('interior', ('members', (), None), None))) == b''


def test_member_token_coalescing_crosses_child_and_large_view_boundaries(monkeypatch):
    monkeypatch.setattr(storage, 'LEAF_BYTES', 32)
    value = {'a': 1, 'b': {'nested': 'x' * 100}, 'c': 'y' * 100, 'd': 4}
    shared = storage.canonical({'c': value['c'], 'd': 4})
    offsets = storage._canonical_members({'c': value['c'], 'd': 4}, shared)
    node = ('members', [('a', b'{"a":1}', None, 1, 6),
                        ('b', b'"b"', ('leaf', storage.canonical(value['b']), None), 0, 0)]
            + [(key, shared, None, start, end) for key, start, end in offsets], None)
    chunks = list(storage._stream_value(node))
    assert b''.join(chunks) == storage.canonical(value)
    assert any(isinstance(chunk, memoryview) and chunk.obj is shared for chunk in chunks)
    # Large chunks are existing immutable backing views/leaf data, not a newly
    # allocated whole-container byte buffer; pending joined chunks stay bounded.
    assert all(len(chunk) <= storage.LEAF_BYTES or isinstance(chunk, memoryview)
               or chunk == storage.canonical(value['b']) for chunk in chunks)


def test_large_interleaved_map_projection_keeps_exact_full_and_body_digests(tmp_path):
    home = tmp_path / 'resources/autopilot-runs/01990000-0000-7000-8000-000000000796'
    state = {'schema_version': 1, 'run_id': home.name, 'revision': 1, 'status': 'recovering',
             'hidden': {f'{index:05}': '雪' + str(index) + 'x' * 145 for index in range(8000)},
             'extensions': {'workflow': {'progress': {}}}}
    body = {'state': state, 'schema_version': 1, 'revision': 1,
            'previous_digest': '', 'command_id': 'complete-map'}
    event = dict(body, digest=hashlib.sha256(storage.canonical(body)).hexdigest())
    raw_descriptor, blocks = storage.encode(event, codec=1)
    descriptor = json.loads(raw_descriptor)
    assert descriptor[storage.MARKER] == 1 and len(blocks) > 4
    storage.materialize(home, blocks)
    path = home / 'events/000000000001.json'
    with storage.normalization_scope():
        projection = storage.decode_event_projection(path, descriptor)
        assert projection.header['digest'] == projection.verified_body_digest == event['digest']
        assert 'hidden' not in projection.identity
        assert storage.decode(path, descriptor) == event


@pytest.mark.parametrize('batch_bytes', [1, 7, 32, 65536])
def test_iterative_digest_has_exact_nested_framing_without_generator_chain(monkeypatch, batch_bytes):
    leaf = lambda value: ('leaf', storage.canonical(value), None)
    fields = lambda rows: ('members', [(key, storage.canonical(key), child, 0, 0)
                                      for key, child in sorted(rows)], None)
    nested_list = ('list', [('array', [leaf(1)], None),
                            ('list', [('array', [leaf({'q': '雪'})], None)], None)], None)
    nested_text = ('text', [leaf('a'), ('text', [leaf('雪'), leaf('\n"')], None)], None)
    state = {'digest': 'nested-kept', 'list': [1, {'q': '雪'}], 'text': 'a雪\n"'}
    state_stream = fields([('digest', leaf('nested-kept')), ('list', nested_list),
                           ('text', nested_text)])
    value = {'0-first': [], 'digest': 'top-omitted', 'schema_version': 1,
             'state': state, 'z-last': {}}
    stream = fields([('0-first', ('array', [], None)), ('digest', leaf('top-omitted')),
                     ('schema_version', leaf(1)), ('state', state_stream),
                     ('z-last', fields([]))])
    raw = storage.canonical(value) + b'\n'
    descriptor = {'logical_bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    expected_body = hashlib.sha256(storage.canonical({key: child for key, child in value.items()
                                                     if key != 'digest'})).hexdigest()
    def forbidden(*args, **kwargs):
        raise AssertionError('digest path re-entered the nested generator chain')
    for name in ['_stream_tokens', '_stream_value', '_stream_member', '_stream_members', '_stream_batches']:
        monkeypatch.setattr(storage, name, forbidden)
    monkeypatch.setattr(storage, 'LEAF_BYTES', batch_bytes)
    assert storage._authenticate_stream(value, stream, descriptor) == expected_body


def test_iterative_digest_passes_large_backing_view_without_materializing_member(monkeypatch):
    value = {'large': 'x' * (storage.LEAF_BYTES * 3)}
    raw = storage.canonical(value)
    stream = ('members', [('large', raw, None, 1, len(raw) - 1)], None)
    descriptor = {'logical_bytes': len(raw) + 1,
                  'sha256': hashlib.sha256(raw + b'\n').hexdigest()}
    original = hashlib.sha256
    observations = []
    class Digest:
        def __init__(self): self.inner = original()
        def update(self, chunk):
            observations.append((isinstance(chunk, memoryview), len(chunk),
                                 isinstance(chunk, memoryview) and chunk.obj is raw))
            self.inner.update(chunk)
        def hexdigest(self): return self.inner.hexdigest()
    monkeypatch.setattr(storage.hashlib, 'sha256', Digest)
    assert storage._authenticate_stream(value, stream, descriptor) is None
    assert (True, len(raw) - 2, True) in observations


@pytest.mark.parametrize('fault', ['size', 'digest'])
def test_iterative_digest_rejects_exact_size_or_hash_mismatch(fault):
    raw = b'{"a":1}'
    descriptor = {'logical_bytes': len(raw) + 1,
                  'sha256': hashlib.sha256(raw + b'\n').hexdigest()}
    if fault == 'size': descriptor['logical_bytes'] -= 1
    else: descriptor['sha256'] = '0' * 64
    with pytest.raises(ValueError, match='snapshot logical content'):
        storage._authenticate_stream({'a': 1}, ('leaf', raw, None), descriptor)


def test_iterative_digest_handles_admitted_depth_without_wrapper_stack_growth():
    value, stream = None, ('leaf', b'null', None)
    # Each list/array pair adds two physical nodes and one logical bracket.
    for _ in range(storage.MAX_DEPTH // 2):
        value = [value]
        stream = ('list', [('array', [stream], None)], None)
    raw = storage.canonical(value) + b'\n'
    descriptor = {'logical_bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    assert storage._authenticate_stream(value, stream, descriptor) is None


def test_iterative_digest_cancellation_releases_scoped_physical_handles(tmp_path, monkeypatch):
    path, descriptor, _, _, _ = _verified_projection_fixture(tmp_path)
    original = hashlib.sha256
    class InterruptedDigest:
        def update(self, chunk):
            raise KeyboardInterrupt('synthetic digest-sink cancellation')
    def digest(*args, **kwargs):
        return original(*args, **kwargs) if args else InterruptedDigest()
    with pytest.raises(KeyboardInterrupt, match='synthetic digest-sink cancellation'):
        with storage.normalization_scope():
            memo = storage._normalization_memo()
            monkeypatch.setattr(storage.hashlib, 'sha256', digest)
            storage.decode_event_projection(path, descriptor)
    assert memo['closed'] and not memo['handles']
    assert memo['budget']['bytes'] == memo['budget']['count'] == 0


@pytest.mark.parametrize('representation', ['span', 'leaf', 'cached'])
def test_member_batch_reduces_actual_sink_dispatch_for_interleaved_fields(monkeypatch, representation):
    import cProfile
    monkeypatch.setattr(storage, 'LEAF_BYTES', 256)
    value = {f'{index:05}': f'雪-{index}' for index in range(2000)}
    fields = []
    for key, item in value.items():
        if representation == 'span':
            raw = storage.canonical({key: item})
            fields.append((key, raw, None, 1, len(raw) - 1))
        else:
            fields.append((key, storage.canonical(key),
                           (representation, storage.canonical(item), None), 0, 0))
    raw = storage.canonical(value) + b'\n'
    descriptor = {'logical_bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    profile = cProfile.Profile()
    profile.enable()
    try:
        assert storage._authenticate_stream(value, ('members', fields, None), descriptor) is None
    finally:
        profile.disable()
    # This asserts the measured operation count, not an elapsed-time threshold:
    # the sink must receive bounded batches rather than each individual token.
    emits = sum(row.callcount for row in profile.getstats()
                if hasattr(row.code, 'co_name') and row.code.co_name == 'emit')
    assert 0 < emits < len(fields) // 4


@pytest.mark.parametrize('batch_bytes', [22, 23, 37])
def test_member_batch_exact_boundary_child_transition_and_large_borrow(monkeypatch, batch_bytes):
    monkeypatch.setattr(storage, 'LEAF_BYTES', batch_bytes)
    leaf = lambda value: ('leaf', storage.canonical(value), None)
    nested = ('members', [('d', b'"d"', leaf(1), 0, 0)], None)
    large = {'c': '雪' * 100}
    borrowed = storage.canonical(large)
    state = {'a': '1234567890123456', 'b': {'d': 1}, 'c': large['c'], 'd': 0}
    state_stream = ('members', [('a', b'"a"', leaf(state['a']), 0, 0),
                                ('b', b'"b"', nested, 0, 0),
                                ('c', borrowed, None, 1, len(borrowed) - 1),
                                ('d', b'"d"', leaf(0), 0, 0)], None)
    value = {'digest': 'omit-only-this', 'schema_version': 1, 'state': state}
    stream = ('members', [('digest', b'"digest"', leaf(value['digest']), 0, 0),
                          ('schema_version', b'"schema_version"', leaf(1), 0, 0),
                          ('state', b'"state"', state_stream, 0, 0)], None)
    raw = storage.canonical(value) + b'\n'
    descriptor = {'logical_bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    expected_body = hashlib.sha256(storage.canonical({key: child for key, child in value.items()
                                                     if key != 'digest'})).hexdigest()
    original = hashlib.sha256
    borrowed_seen = []
    class Digest:
        def __init__(self): self.inner = original()
        def update(self, chunk):
            if isinstance(chunk, memoryview) and chunk.obj is borrowed:
                borrowed_seen.append(len(chunk))
            self.inner.update(chunk)
        def hexdigest(self): return self.inner.hexdigest()
    monkeypatch.setattr(storage.hashlib, 'sha256', Digest)
    assert storage._authenticate_stream(value, stream, descriptor) == expected_body
    assert borrowed_seen and all(length == len(borrowed) - 2 for length in borrowed_seen)


@pytest.mark.parametrize("order", ["ordered", "reversed", "interleaved"])
def test_descriptor_map_spans_preserve_full_event_and_body_framing(order):
    import journal_storage as storage
    groups = [{f"k{n:05d}": "é\\\"" * 3 for n in range(i * 80, (i + 1) * 80)} for i in range(8)]
    if order == "reversed":
        groups.reverse()
    elif order == "interleaved":
        groups = [{f"k{n:05d}": "é\\\"" * 3 for n in range(i, 640, 8)} for i in range(8)]
    children = []
    expected = {}
    for group in groups:
        raw = storage.canonical(group)
        children.append(("leaf", raw, storage._canonical_members(group, raw)))
        expected.update(group)
    stream = storage._map_stream(children)
    canonical = storage.canonical(expected)
    assert b"".join(storage._stream_value(stream)) == canonical
    assert storage._pack_stream(stream)[0] == canonical
    descriptor = {"logical_bytes": len(canonical) + 1, "sha256": storage._hash(canonical + b"\n")}
    assert storage._authenticate_stream(expected, stream, descriptor) is None
    event = {"schema_version": 1, "state": expected, "digest": "nested exclusion stays ordinary"}
    node = ("members", (("digest", b'"digest"', ("leaf", storage.canonical(event["digest"]), None), 0, 0),
                         ("schema_version", b'"schema_version"', ("leaf", b"1", None), 0, 0),
                         ("state", b'"state"', stream, 0, 0)), None)
    raw = storage.canonical(event)
    descriptor = {"logical_bytes": len(raw) + 1, "sha256": storage._hash(raw + b"\n")}
    assert storage._authenticate_stream(event, node, descriptor) == storage._hash(storage.canonical({k: v for k, v in event.items() if k != "digest"}))
    if order != "interleaved":
        assert stream[0] == "map-spans"
        assert all(a is b for a, b in zip(stream[1], sorted(children, key=lambda child: child[2][0][0])))


def test_descriptor_map_spans_empty_nested_and_member_order_are_exact():
    import journal_storage as storage
    raw_a, raw_b = b'{"a":1}', b'{"b":2}'
    a = ("leaf", raw_a, (("a", 1, len(raw_a) - 1),))
    b = ("leaf", raw_b, (("b", 1, len(raw_b) - 1),))
    empty = ("leaf", b"{}", ())
    child = storage._map_stream([b, empty, a])
    nested = storage._map_stream([child, empty])
    assert b"".join(storage._stream_value(nested)) == b'{"a":1,"b":2}'
    assert [field[0] for field in storage._stream_index(child)] == ["a", "b"]
    assert b"".join(storage._stream_value(storage._map_stream([empty]))) == b"{}"


def test_descriptor_map_spans_avoid_per_member_token_work_and_owned_map_copy(monkeypatch):
    import cProfile
    import journal_storage as storage
    groups = [{f"key{n:06d}": n for n in range(i * 2000, (i + 1) * 2000)} for i in range(20)]
    expected = {}; children = []
    for group in groups:
        raw = storage.canonical(group)
        children.append(("leaf", raw, storage._canonical_members(group, raw)))
        expected.update(group)
    stream = storage._map_stream(children)
    assert stream[0] == "map-spans"
    raw = storage.canonical(expected)
    descriptor = {"logical_bytes": len(raw) + 1, "sha256": storage._hash(raw + b"\n")}
    def forbidden(*args, **kwargs):
        raise AssertionError("ordered physical spans must not expand every member or copy a whole map")
    monkeypatch.setattr(storage, "_stream_index", forbidden)
    monkeypatch.setattr(storage, "_pack_map", forbidden)
    monkeypatch.setattr(storage, "_pack_stream", forbidden)
    profiler = cProfile.Profile(); profiler.enable()
    storage._authenticate_stream(expected, stream, descriptor)
    profiler.disable()
    emits = sum(row.callcount for row in profiler.getstats() if getattr(row.code, "co_name", "") == "emit")
    assert emits <= 2 + 2 * len(children)


@pytest.mark.parametrize("leaf", [32, 97, 65536])
def test_descriptor_chunk_ledger_and_exact_nested_event_framing(monkeypatch, leaf):
    import journal_storage as storage
    monkeypatch.setattr(storage, "LEAF_BYTES", leaf)
    groups = [{f"k{n:04d}": n for n in range(i, 120, 12)} for i in range(12)]
    # Small physical children stay within the selected leaf bound.
    children = []
    for group in groups:
        for key, value in group.items():
            item = {key: value};raw = storage.canonical(item)
            children.append(("leaf", raw, storage._canonical_members(item, raw)))
    # Put alternating keys in each leaf to exercise interleaved order admission.
    children = []
    for i in range(60):
        item = {f"k{i:04d}": i, f"k{i+60:04d}": i+60};raw = storage.canonical(item)
        assert len(raw) <= leaf
        children.append(("leaf", raw, storage._canonical_members(item, raw)))
    expected = {f"k{n:04d}": n for n in range(120)}
    raw = storage.canonical(expected);budget = [len(raw), 0]
    stream = storage._map_stream(children, _budget=budget)
    assert stream[0] == "map-chunks" and budget[1] == len(raw)
    assert all(0 < len(part) <= leaf for part in stream[1])
    assert sum(map(len, stream[1])) == len(raw)
    assert b"".join(storage._stream_value(stream)) == raw
    assert b"".join(storage._stream_value(("interior", stream, None))) == raw[1:-1]
    # No quota is refunded while a prior compiled map can still be live.
    assert storage._map_stream(children, _budget=budget)[0] == "members"
    assert budget[1] == len(raw)
    event = {"state": {"nested": [expected]}, "digest": "nested digest unaffected", "schema_version": 1}
    nested = ("members", (("nested", b'"nested"', ("array", (stream,), None), 0, 0),), None)
    node = ("members", (("digest", b'"digest"', ("leaf", storage.canonical(event["digest"]), None), 0, 0), ("schema_version", b'"schema_version"', ("leaf", b"1", None), 0, 0), ("state", b'"state"', nested, 0, 0)), None)
    canonical = storage.canonical(event)
    desc = {"logical_bytes": len(canonical)+1, "sha256": storage._hash(canonical+b"\n")}
    assert storage._authenticate_stream(event,node,desc) == storage._hash(storage.canonical({k:v for k,v in event.items() if k != "digest"}))


def test_descriptor_chunk_budget_refusal_precedes_payload_allocation(monkeypatch):
    import journal_storage as storage
    a={"a":1,"z":3};b={"b":2,"y":4};children=[]
    for value in [a,b]:
        raw=storage.canonical(value);children.append(("leaf",raw,storage._canonical_members(value,raw)))
    budget=[1,0];stream=storage._map_stream(children,_budget=budget)
    assert stream[0]=="members" and budget==[1,0]
    assert b"".join(storage._stream_value(stream))==storage.canonical(a|b)



def test_descriptor_chunk_large_compiled_leaf_member_declines_before_reservation():
    import journal_storage as storage
    large = {"a": "x" * (storage.LEAF_BYTES + 1), "z": 1}
    other = {"b": 2, "y": 3}
    children = []
    for value in [large, other]:
        raw = storage.canonical(value)
        children.append(("leaf", raw, storage._canonical_members(value, raw)))
    budget = [storage.MAX_LOGICAL_BYTES, 0]
    stream = storage._map_stream(children, _budget=budget)
    assert stream[0] == "members" and budget[1] == 0
    expected = large | other
    raw = storage.canonical(expected)
    desc = {"logical_bytes": len(raw)+1, "sha256": storage._hash(raw+b"\n")}
    assert storage._authenticate_stream(expected, stream, desc) is None



def test_indexed_leaf_reuses_immutable_fields_and_charges_every_new_reference():
    import sys
    import journal_storage as storage
    value = {"é": [1, 2], "a": {"z": True}}
    raw = storage.canonical(value); ranges = storage._canonical_members(value, raw)
    stream = storage._indexed_leaf(raw, ranges)
    fields = storage._stream_index(stream)
    assert fields is storage._stream_index(stream)
    assert type(fields) is tuple and all(type(item) is tuple for item in fields)
    assert all(item[1] is raw and item[2] is None for item in fields)
    assert storage._index_cost(stream) == sys.getsizeof(stream) + sys.getsizeof(fields) + sum(map(sys.getsizeof, fields))
    assert b"".join(storage._stream_value(stream)) == raw
    assert storage._pack_stream(stream) == (raw, ranges)


def test_indexed_retained_plan_keeps_fresh_dependency_reads_and_field_identity(tmp_path, monkeypatch):
    import journal_storage as storage
    path, descriptor, blocks, expected = subtree_plan_fixture(tmp_path)
    with storage.normalization_scope():
        assert storage.decode(path, descriptor) == expected
        memo = storage._normalization_memo();plan = memo["plans"][(descriptor["root"], False)]
        indexed = plan[-2]; assert indexed[0] == "leaf"
        fields = storage._stream_index(indexed)
        assert fields is storage._stream_index(indexed)
        assert plan[-1] >= storage._index_cost(indexed)
        reads = [];original = storage._read_block
        def read(parent,name,limit,active_memo,identity):
            reads.append(name);return original(parent,name,limit,active_memo,identity)
        monkeypatch.setattr(storage,"_read_block",read)
        second = storage.decode(path,descriptor)
        assert second == expected and set(reads) == {name+".json" for name in blocks}
        second["field-0"]["z"].append("changed")
        assert storage.decode(path,descriptor) == expected
    assert memo["closed"] and not memo["plans"] and memo["budget"]["bytes"] == 0


def test_indexed_leaf_residency_is_released_on_policy_change_and_cancel(tmp_path, monkeypatch):
    import journal_storage as storage
    path, descriptor, _, expected = subtree_plan_fixture(tmp_path)
    with storage.normalization_scope():
        assert storage.decode(path, descriptor) == expected
        memo = storage._normalization_memo()
        assert any(len(entry[-1]) == 4 for entry in memo["entries"].values())
        monkeypatch.setattr(storage,"MAX_LOGICAL_BYTES",storage.MAX_LOGICAL_BYTES-1)
        assert storage._normalization_memo() is memo
        assert not memo["entries"] and not memo["plans"]
    assert memo["budget"]["bytes"] == 0 and memo["closed"]



@pytest.mark.parametrize("value", [7, [1, 2], "text"])
def test_indexed_nonmap_stream_tuple_is_charged(value):
    import sys
    import journal_storage as storage
    raw = storage.canonical(value)
    stream = storage._indexed_leaf(raw, None)
    assert len(stream) == 3 and storage._index_cost(stream) == sys.getsizeof(stream)
    assert storage._pack_stream(stream) == (raw, None)



def test_indexed_entry_charges_added_slot_for_leaf_and_plan():
    import sys
    import journal_storage as storage
    stream = storage._indexed_leaf(b"1", None)
    added = storage._entry_index_cost(stream) - storage._index_cost(stream)
    assert added == sys.getsizeof((None,) * 7) - sys.getsizeof((None,) * 6)
    assert added == sys.getsizeof((None,) * 10) - sys.getsizeof((None,) * 9)


@pytest.mark.parametrize("value", [{}, {"a": 1}, {"a": 1, "z": 2},
    {"é": "雪", "a": [1, 2], "z": {"q": True}, "quote\"": "line\n"}])
def test_child_summary_exact_canonical_size_count_width_and_small_fallback(value):
    raw = storage.canonical(value)
    ranges = storage._canonical_members(value, raw)
    stream = storage._summarized_leaf(raw, ranges)
    assert storage._leaf_summary(stream) == (
        len(raw), len(value), max((end - start + 1 for _, start, end in ranges), default=1))
    assert len(stream) == (5 if len(value) > 2 else 4)
    assert b"".join(storage._stream_value(stream)) == raw
    assert storage._pack_stream(stream) == (raw, ranges)
    assert storage._stream_index(stream) is stream[3]
    if len(stream) == 5:
        assert type(stream[4]) is tuple and all(type(item) is int for item in stream[4])
        with pytest.raises(TypeError):
            stream[4][0] = 0


@pytest.mark.parametrize("value", [None, {}, {"a": 1, "z": 2},
    {"a": "雪", "b": 2, "c": 3, "d": 4}])
def test_child_summary_charges_all_added_retained_objects_and_reference_slots(value):
    import sys
    raw = storage.canonical(value)
    ranges = storage._canonical_members(value, raw) if isinstance(value, dict) else None
    stream = storage._summarized_leaf(raw, ranges)
    expected = sys.getsizeof(stream)
    if len(stream) >= 4:
        expected += sys.getsizeof(stream[3]) + sum(sys.getsizeof(row) for row in stream[3])
    if len(stream) == 5:
        expected += sys.getsizeof(stream[4]) + sum(sys.getsizeof(item) for item in stream[4])
    assert storage._index_cost(stream) == expected
    slot = sys.getsizeof((None,) * 7) - sys.getsizeof((None,) * 6)
    assert storage._entry_index_cost(stream) == expected + slot
    assert slot == sys.getsizeof((None,) * 10) - sys.getsizeof((None,) * 9)


def test_child_summary_interleaved_unicode_map_uses_retained_summaries_without_field_rescan():
    class Ranges(tuple):
        def __iter__(self):
            raise AssertionError("authenticated child framing was scanned again")
    groups = [{f"{index:04d}-é": "雪\n\"" + str(index) for index in range(part, 180, 3)}
              for part in range(3)]
    children = []
    for value in groups:
        raw = storage.canonical(value)
        stream = storage._summarized_leaf(raw, storage._canonical_members(value, raw))
        # Only iteration is forbidden: ordering still reads authenticated endpoints.
        children.append((stream[0], stream[1], Ranges(stream[2]), stream[3], stream[4]))
    expected = {key: value for group in groups for key, value in group.items()}
    raw = storage.canonical(expected)
    budget = [len(raw), 0]
    stream = storage._map_stream(children, _budget=budget)
    assert stream[0] == "map-chunks" and budget == [len(raw), len(raw)]
    assert b"".join(storage._stream_value(stream)) == raw
    assert all(len(part) <= storage.LEAF_BYTES for part in stream[1])
    descriptor = {"logical_bytes": len(raw) + 1, "sha256": storage._hash(raw + b"\n")}
    assert storage._authenticate_stream(expected, stream, descriptor) is None


def test_child_summary_empty_nested_and_interleaved_maps_preserve_framing():
    def leaf(value):
        raw = storage.canonical(value)
        return storage._summarized_leaf(raw, storage._canonical_members(value, raw))
    groups = [{"a": "雪", "e": [1], "i": {}}, {"b": 2, "f": 6, "j": 10}]
    expected = groups[0] | groups[1]
    raw = storage.canonical(expected)
    budget = [len(raw), 0]
    first = storage._map_stream([leaf({}), leaf(groups[0]), leaf(groups[1])], _budget=budget)
    assert first[0] == "map-chunks" and budget[1] == len(raw)
    parent = storage._map_stream([first, leaf({"c": 3, "g": 7, "k": 11})],
                                 _budget=[storage.MAX_LOGICAL_BYTES, 0])
    assert parent[0] == "members"
    assert b"".join(storage._stream_value(parent)) == storage.canonical(expected | {"c": 3, "g": 7, "k": 11})
    assert b"".join(storage._stream_value(("interior", first, None))) == raw[1:-1]
    assert b"".join(storage._stream_value(storage._map_stream([leaf({}), leaf({})]))) == b"{}"


def test_child_summary_oversized_compiled_member_declines_before_reservation():
    groups = [{"a": "x" * (storage.LEAF_BYTES + 1), "d": 4, "g": 7},
              {"b": 2, "e": 5, "h": 8}]
    children = []
    for value in groups:
        raw = storage.canonical(value)
        children.append(storage._summarized_leaf(raw, storage._canonical_members(value, raw)))
    assert len(children[0]) == 5 and children[0][4][2] > storage.LEAF_BYTES
    budget = [storage.MAX_LOGICAL_BYTES, 0]
    stream = storage._map_stream(children, _budget=budget)
    assert stream[0] == "members" and budget[1] == 0
    assert b"".join(storage._stream_value(stream)) == storage.canonical(groups[0] | groups[1])


def test_child_summary_retained_admissions_charge_bytes_and_keep_fresh_dependency_reads(tmp_path, monkeypatch):
    home = tmp_path / 'resources/autopilot-runs/01990000-0000-7000-8000-000000000799'
    value = {f'key-{index:03}': '雪' + str(index) for index in range(128)}
    physical = storage.canonical(["leaf", value]) + b"\n"
    digest = storage._hash(physical)
    logical = storage.canonical(value) + b"\n"
    blocks = {digest: physical}
    descriptor = {storage.MARKER: 1, "root": digest,
                  "sha256": storage._hash(logical), "logical_bytes": len(logical)}
    storage.materialize(home, blocks)
    path = home / 'current.json'
    with storage.normalization_scope():
        assert storage.decode(path, descriptor) == value
        memo = storage._normalization_memo()
        summarized = [entry for entry in memo['entries'].values() if len(entry[-1]) == 5]
        assert summarized
        assert all(entry[4] >= storage._entry_index_cost(entry[-1]) for entry in summarized)
        expected_cost = sum(sum(entry[4] for entry in owner['entries'].values())
                            + owner['plans'].retained_bytes
                            + sum(handle[1] for handle in owner['handles'].values())
                            for owner in memo['budget']['memos'])
        expected_count = sum(len(owner['entries']) + len(owner['plans']) + len(owner['handles'])
                             for owner in memo['budget']['memos'])
        assert memo['budget']['bytes'] == expected_cost
        assert memo['budget']['count'] == expected_count
        reads = []
        original = storage._read_block
        def read(parent, name, limit, active_memo, identity):
            reads.append(name)
            return original(parent, name, limit, active_memo, identity)
        monkeypatch.setattr(storage, '_read_block', read)
        result = storage.decode(path, descriptor)
        assert result == value and set(reads) == {name + '.json' for name in blocks}
        result['key-000'] = 'changed consumer'
        assert storage.decode(path, descriptor) == value
    assert memo['closed'] and memo['budget']['bytes'] == memo['budget']['count'] == 0


def test_child_summary_first_admission_uses_exact_charged_stream_and_refusal_falls_back(tmp_path, monkeypatch):
    home = tmp_path / 'resources/autopilot-runs/01990000-0000-7000-8000-000000000800'
    value = {f'key-{index:03}': '雪' + str(index) for index in range(128)}
    physical = storage.canonical(['leaf', value]) + b'\n'
    digest = storage._hash(physical)
    logical = storage.canonical(value) + b'\n'
    descriptor = {storage.MARKER: 1, 'root': digest,
                  'sha256': storage._hash(logical), 'logical_bytes': len(logical)}
    storage.materialize(home, {digest: physical})
    path = home / 'current.json'
    original = storage._authenticate_stream
    observations = []
    def authenticate(decoded, stream, bound):
        memo = storage._normalization_memo()
        entry = memo['entries'].get(digest)
        observations.append((len(stream), entry is not None and stream is entry[-1]))
        return original(decoded, stream, bound)
    monkeypatch.setattr(storage, '_authenticate_stream', authenticate)
    with storage.normalization_scope():
        assert storage.decode(path, descriptor) == value
        assert observations == [(5, True)]
    # Force only optional metadata admission to fail; decoded limits stay intact.
    original_cost = storage._entry_index_cost
    monkeypatch.setattr(storage, '_entry_index_cost', lambda stream: original_cost(stream) + storage.MAX_LOGICAL_BYTES)
    with storage.normalization_scope():
        assert storage.decode(path, descriptor) == value
        assert observations[-1] == (3, False)
        assert not storage._normalization_memo()['entries']


@pytest.mark.parametrize('fault', ['replacement', 'cancellation'])
def test_child_summary_first_admission_does_not_cache_physical_authority_or_survive_cancel(tmp_path, monkeypatch, fault):
    home = tmp_path / 'resources/autopilot-runs/01990000-0000-7000-8000-000000000801'
    value = {f'key-{index:03}': '雪' + str(index) for index in range(128)}
    physical = storage.canonical(['leaf', value]) + b'\n'
    digest = storage._hash(physical)
    logical = storage.canonical(value) + b'\n'
    descriptor = {storage.MARKER: 1, 'root': digest,
                  'sha256': storage._hash(logical), 'logical_bytes': len(logical)}
    storage.materialize(home, {digest: physical})
    path = home / 'current.json'
    original = storage._authenticate_stream
    def authenticate(decoded, stream, bound):
        entry = storage._normalization_memo()['entries'][digest]
        assert len(stream) == 5 and stream is entry[-1]
        raise KeyboardInterrupt('first-use digest cancellation')
    if fault == 'cancellation':
        monkeypatch.setattr(storage, '_authenticate_stream', authenticate)
        with pytest.raises(KeyboardInterrupt, match='first-use digest cancellation'):
            with storage.normalization_scope():
                memo = storage._normalization_memo()
                storage.decode(path, descriptor)
    else:
        with storage.normalization_scope():
            memo = storage._normalization_memo()
            assert storage.decode(path, descriptor) == value
            target = home / 'state-blocks/v1' / (digest + '.json')
            assert target.read_bytes() == physical
            replacement = target.with_name('replacement.tmp')
            replacement.write_bytes(physical.replace(b'key-000', b'key-999'))
            replacement.replace(target)
            with pytest.raises(ValueError, match='digest mismatch'):
                storage.decode(path, descriptor)
    assert storage._authenticate_stream is original or fault == 'cancellation'
    assert memo['closed'] and not memo['entries'] and not memo['plans'] and not memo['handles']
    assert memo['budget']['bytes'] == memo['budget']['count'] == 0


@pytest.mark.parametrize('interior', [False, True])
def test_singleton_member_final_flush_preserves_borrowed_backing(interior):
    raw = b'{"a":1,"c":3}'
    leaf = ('leaf', raw, (('a', 1, 6), ('c', 7, 12)))
    node = ('members', tuple(storage._stream_index(leaf)), None)
    if interior:
        node = ('interior', node, None)
    parts = list(storage._stream_value(node))
    borrowed = [part for part in parts if isinstance(part, memoryview)]
    assert len(borrowed) == 1 and borrowed[0].obj is raw
    assert bytes(borrowed[0]) == raw[1:-1]
    assert b''.join(parts) == (raw[1:-1] if interior else raw)


@pytest.mark.parametrize('bound', [7, 11])
def test_singleton_member_capacity_flush_keeps_single_view_and_bounds_multispan_batch(monkeypatch, bound):
    monkeypatch.setattr(storage, 'LEAF_BYTES', bound)
    fields, backing = [], []
    for key, value in [('a', 1), ('b', 2), ('c', 3), ('d', 4)]:
        raw = storage.canonical({key: value})
        backing.append(raw)
        fields.append((key, raw, None, 1, len(raw) - 1))
    parts = list(storage._stream_value(('members', tuple(fields), None)))
    assert b''.join(parts) == b'{"a":1,"b":2,"c":3,"d":4}'
    assert all(len(part) <= bound for part in parts)
    assert any(isinstance(part, memoryview) and part.obj is backing[-1] for part in parts)
    # Separate buffers really do require a bounded join; byte equality alone
    # must not be used to claim they share one borrowed backing allocation.
    assert any(type(part) is bytes and len(part) > 1 for part in parts)


def test_singleton_member_nested_flush_preserves_identity_across_structured_transition():
    raw = b'{"a":1,"c":3}'
    leaf = ('leaf', raw, (('a', 1, 6), ('c', 7, 12)))
    child = ('members', tuple(storage._stream_index(leaf)), None)
    node = ('members', (('child', b'"child"', child, 0, 0),
                        ('tail', b'"tail"', ('leaf', b'4', None), 0, 0)), None)
    parts = list(storage._stream_value(node))
    assert b''.join(parts) == b'{"child":{"a":1,"c":3},"tail":4}'
    assert any(isinstance(part, memoryview) and part.obj is raw for part in parts)
    value = {'child': {'a': 1, 'c': 3}, 'tail': 4}
    logical = storage.canonical(value) + b'\n'
    descriptor = {'logical_bytes': len(logical), 'sha256': storage._hash(logical)}
    assert storage._authenticate_stream(value, node, descriptor) is None



def _retained_handle_leaf_fixture(tmp_path, count):
    home = tmp_path / 'resources/autopilot-runs/01990000-0000-7000-8000-000000000987'
    blocks = home / 'state-blocks/v1'
    blocks.mkdir(parents=True)
    fixtures = []
    for index in range(count):
        value = {'index': index}
        physical = storage.canonical(['leaf', value]) + b'\n'
        digest = storage._hash(physical)
        logical = storage.canonical(value) + b'\n'
        (blocks / (digest + '.json')).write_bytes(physical)
        fixtures.append((value, physical, digest, {storage.MARKER: 1, 'root': digest,
                        'sha256': storage._hash(logical), 'logical_bytes': len(logical)}))
    return home / 'current.json', blocks, fixtures


def test_retained_leaf_second_admission_uses_existing_charged_history_and_fresh_read(tmp_path, monkeypatch):
    path, directory, fixtures = _retained_handle_leaf_fixture(tmp_path, 1)
    value, physical, digest, descriptor = fixtures[0]
    parent = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    original = os.pread
    calls = []
    def read(*args):
        calls.append(args[0])
        return original(*args)
    monkeypatch.setattr(os, 'pread', read)
    try:
        with storage.normalization_scope():
            memo = storage._normalization_memo()
            assert storage.decode(path, descriptor) == value
            entry = memo['entries'][digest]
            key = next(iter(memo['handles']))
            assert key in memo['handle_probation']
            assert storage._evict_handle(memo['budget'])
            bytes_before, count_before = memo['budget']['bytes'], memo['budget']['count']
            assert storage._read_block(parent, digest + '.json', storage.MAX_BLOCK_BYTES, memo, []) == physical
            assert memo['entries'][digest] is entry and key in memo['handle_protected']
            assert memo['budget']['bytes'] == bytes_before + memo['handles'][key][1]
            assert memo['budget']['count'] == count_before + 1
            assert len(calls) == 2
            # Queue priority cannot make a later same-size mutation authoritative.
            (directory / (digest + '.json')).write_bytes(physical.replace(b'0', b'9'))
            with pytest.raises(ValueError, match='digest mismatch'):
                storage.decode(path, descriptor)
    finally:
        os.close(parent)
    assert memo['closed'] and memo['budget']['bytes'] == memo['budget']['count'] == 0


def test_retained_leaf_absence_keeps_new_handle_in_probation(tmp_path):
    (tmp_path / 'unseen.json').write_bytes(b'fresh')
    parent = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        with storage.normalization_scope():
            memo = storage._normalization_memo()
            assert storage._read_block(parent, 'unseen.json', 10, memo, []) == b'fresh'
            key = next(iter(memo['handles']))
            assert key in memo['handle_probation'] and not memo['handle_protected']
            assert not memo['entries'] and not memo['plans']
    finally:
        os.close(parent)


def test_retained_leaf_admission_reuses_hot_entries_after_probation_eviction(tmp_path):
    path, directory, fixtures = _retained_handle_leaf_fixture(tmp_path, 80)
    parent = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        with storage.normalization_scope():
            memo = storage._normalization_memo()
            for value, _, _, descriptor in fixtures:
                assert storage.decode(path, descriptor) == value
            while storage._evict_handle(memo['budget']):
                pass
            for _, physical, digest, _ in fixtures:
                assert storage._read_block(parent, digest + '.json', storage.MAX_BLOCK_BYTES, memo, []) == physical
            hot = dict(memo['handles'])
            assert len(memo['handle_protected']) == 80
            for index in range(300):
                name = f'new-{index}.json'
                (directory / name).write_bytes(b'one use')
                assert storage._read_block(parent, name, 20, memo, []) == b'one use'
            assert all(memo['handles'][key] is handle for key, handle in hot.items())
            assert len(memo['handles']) == 256
    finally:
        os.close(parent)


def test_shared_protected_handle_limit_spans_nested_owners_and_cancellation(tmp_path):
    for index in range(256):
        (tmp_path / f'{index}.json').write_bytes(b'fresh')
    parent = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    fds = []
    try:
        with pytest.raises(KeyboardInterrupt):
            with storage.normalization_scope():
                outer = storage._normalization_memo()
                for index in range(128):
                    for _ in range(2):
                        assert storage._read_block(parent, f'{index}.json', 10, outer, []) == b'fresh'
                assert len(outer['handle_protected']) == 128
                with storage.normalization_scope():
                    inner = storage._normalization_memo()
                    for index in range(128, 256):
                        for _ in range(2):
                            assert storage._read_block(parent, f'{index}.json', 10, inner, []) == b'fresh'
                        assert sum(len(owner['handle_protected']) for owner in inner['budget']['memos']) <= 192
                    assert sum(len(owner['handles']) for owner in inner['budget']['memos']) == 256
                    assert sum(len(owner['handle_protected']) for owner in inner['budget']['memos']) == 192
                    assert inner['budget']['bytes'] == sum(owner['bytes'] for owner in inner['budget']['memos'])
                    fds = [v[0] for owner in inner['budget']['memos'] for v in owner['handles'].values()]
                    raise KeyboardInterrupt
        assert outer['closed'] and inner['closed']
        assert outer['budget']['bytes'] == outer['budget']['count'] == 0
        for fd in fds:
            with pytest.raises(OSError):
                os.fstat(fd)
    finally:
        os.close(parent)



def test_retained_leaf_priority_does_not_borrow_another_memos_history(tmp_path):
    path, directory, fixtures = _retained_handle_leaf_fixture(tmp_path, 1)
    value, physical, digest, descriptor = fixtures[0]
    parent = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        with storage.normalization_scope():
            outer = storage._normalization_memo()
            assert storage.decode(path, descriptor) == value
            assert digest in outer['entries']
            with storage.normalization_scope():
                inner = storage._normalization_memo()
                assert not inner['entries']
                assert storage._read_block(parent, digest + '.json', storage.MAX_BLOCK_BYTES, inner, []) == physical
                key = next(iter(inner['handles']))
                assert key in inner['handle_probation'] and not inner['handle_protected']
                assert digest in outer['entries'] and not inner['entries']
            assert inner['closed'] and not inner['handles']
            assert outer['budget']['bytes'] == outer['bytes']
    finally:
        os.close(parent)



def test_retained_subtree_plan_prior_use_promotes_without_new_residency(tmp_path, monkeypatch):
    path, descriptor, blocks, expected = subtree_plan_fixture(tmp_path)
    directory = path.parent / 'state-blocks/v1'
    parent = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    original_read = os.pread
    reads = []
    def read(*args):
        reads.append(args[0])
        return original_read(*args)
    monkeypatch.setattr(os, 'pread', read)
    try:
        with storage.normalization_scope():
            memo = storage._normalization_memo()
            assert storage.decode(path, descriptor) == expected
            digest = descriptor['root']
            plan = memo['plans'][(digest, False)]
            assert digest not in memo['entries']
            while storage._evict_handle(memo['budget']):
                pass
            before_bytes, before_count = memo['budget']['bytes'], memo['budget']['count']
            reads.clear()
            assert storage._read_block(parent, digest + '.json', storage.MAX_BLOCK_BYTES, memo, []) == blocks[digest]
            key = next(iter(memo['handles']))
            assert key in memo['handle_protected'] and len(reads) == 1
            assert memo['plans'][(digest, False)] is plan
            assert memo['budget']['bytes'] == before_bytes + memo['handles'][key][1]
            assert memo['budget']['count'] == before_count + 1
            assert storage.decode(path, descriptor) == expected
            assert len(reads) == 1 + len(blocks)
    finally:
        os.close(parent)


@pytest.mark.parametrize('fault', ['changed', 'missing', 'symlink'])
def test_retained_subtree_priority_keeps_every_fresh_dependency_refusal(tmp_path, fault):
    path, descriptor, blocks, expected = subtree_plan_fixture(tmp_path)
    with storage.normalization_scope():
        memo = storage._normalization_memo()
        assert storage.decode(path, descriptor) == expected
        while storage._evict_handle(memo['budget']):
            pass
        assert storage.decode(path, descriptor) == expected
        assert any(key[-1] == descriptor['root'] + '.json' for key in memo['handle_protected'])
        child = next(key for key in blocks if key != descriptor['root'])
        target = path.parent / 'state-blocks/v1' / (child + '.json')
        if fault == 'changed':
            before = target.stat()
            target.write_bytes(target.read_bytes().replace(b'retained', b'mutated!', 1))
            os.utime(target, ns=(before.st_atime_ns, before.st_mtime_ns))
        else:
            target.rename(target.with_suffix('.retained'))
            if fault == 'symlink':
                target.symlink_to(target.with_suffix('.retained'))
        with pytest.raises((OSError, ValueError)):
            storage.decode(path, descriptor)
    assert memo['closed'] and not memo['handles']
    assert memo['budget']['bytes'] == memo['budget']['count'] == 0



def test_retained_canonical_skip_plan_admission_still_authenticates_hidden_bytes(tmp_path):
    path, descriptor, event, hidden_root, hidden = _verified_projection_fixture(tmp_path)
    directory = storage.home_for(path) / 'state-blocks/v1'
    parent = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        with storage.normalization_scope():
            memo = storage._normalization_memo()
            assert storage.decode_event_projection(path, descriptor).header['digest'] == event['digest']
            plan = memo['plans'][(hidden_root, 'canonical-skip')]
            assert hidden_root not in memo['entries']
            while storage._evict_handle(memo['budget']):
                pass
            before_bytes, before_count = memo['budget']['bytes'], memo['budget']['count']
            name = hidden_root + '.json'
            expected = (directory / name).read_bytes()
            assert storage._read_block(parent, name, storage.MAX_BLOCK_BYTES, memo, []) == expected
            key = next(iter(memo['handles']))
            assert key in memo['handle_protected']
            assert memo['plans'][(hidden_root, 'canonical-skip')] is plan
            assert memo['budget']['bytes'] == before_bytes + memo['handles'][key][1]
            assert memo['budget']['count'] == before_count + 1
            target = directory / (hidden[1] + '.json')
            target.write_bytes(target.read_bytes().replace(b':1', b':9'))
            with pytest.raises(ValueError, match='digest mismatch'):
                storage.decode_event_projection(path, descriptor)
    finally:
        os.close(parent)


@pytest.mark.parametrize('value', [None, {}, {'a': 1}, {'a': 1, 'z': 2},
    {'quote"': 'line\n', 'é': '雪', 'a': [1, {'x': False}], 'z': None}])
def test_owned_member_parts_preserve_interfaces_bytes_and_exact_added_charges(value):
    import sys
    raw = storage.canonical(value)
    ranges = storage._canonical_members(value, raw) if isinstance(value, dict) else None
    stream = storage._member_span_leaf(raw, ranges)
    assert stream[1] is raw and stream[2] is ranges
    assert b''.join(storage._stream_value(stream)) == raw
    assert storage._pack_stream(stream) == (raw, ranges)
    expected = sys.getsizeof(stream)
    if len(stream) >= 4:
        expected += sys.getsizeof(stream[3]) + sum(map(sys.getsizeof, stream[3]))
    if len(stream) == 5:
        expected += sys.getsizeof(stream[4]) + sum(map(sys.getsizeof, stream[4]))
        assert type(stream[3]) is storage._MemberParts
        for field, (key, start, end) in zip(stream[3], ranges):
            assert field == (key, raw[start:end], None, 0, end - start)
            assert type(field[1]) is bytes and field[1] is not raw
            expected += sys.getsizeof(field[1]) + sys.getsizeof(field[3]) + sys.getsizeof(field[4])
        with pytest.raises(TypeError):
            stream[3][0] = stream[3][0]
        assert not hasattr(stream[3], '__dict__')
    else:
        assert stream == storage._summarized_leaf(raw, ranges)
    assert storage._index_cost(stream) == expected
    assert storage._entry_index_cost(stream) == expected + sys.getsizeof((None,)) - sys.getsizeof(())


def test_owned_member_parts_interleaved_join_avoids_reconstructing_views(monkeypatch):
    groups = [{f'{index:04d}-é': '雪"\n' + str(index) for index in range(part, 180, 3)}
              for part in range(3)]
    children = []
    for value in groups:
        raw = storage.canonical(value)
        children.append(storage._member_span_leaf(raw, storage._canonical_members(value, raw)))
    identities = [tuple(id(field[1]) for field in child[3]) for child in children]
    expected = {key: value for group in groups for key, value in group.items()}
    raw = storage.canonical(expected)
    def forbidden(*args):
        raise AssertionError('owned member bytes were rewrapped as views')
    with monkeypatch.context() as scope:
        scope.setattr(storage, 'memoryview', forbidden, raising=False)
        stream = storage._map_stream(children, _budget=[len(raw), 0])
    assert stream[0] == 'map-chunks'
    assert all(len(part) <= storage.LEAF_BYTES for part in stream[1])
    assert b''.join(storage._stream_value(stream)) == raw
    assert storage._authenticate_stream(expected, stream,
        {'logical_bytes': len(raw) + 1, 'sha256': storage._hash(raw + b'\n')}) is None
    assert identities == [tuple(id(field[1]) for field in child[3]) for child in children]
    parent = storage._map_stream([stream, storage._summarized_leaf(b'{"q":1}', (('q', 1, 6),))])
    assert b''.join(storage._stream_value(parent)) == storage.canonical(expected | {'q': 1})


def _owned_member_fixture(tmp_path):
    home = tmp_path / 'resources/autopilot-runs/01990000-0000-7000-8000-000000000899'
    value = {f'key-{index:03d}': f'value-{index:03d}' for index in range(128)}
    physical = storage.canonical(['leaf', value]) + b'\n'
    digest = storage._hash(physical)
    logical = storage.canonical(value) + b'\n'
    descriptor = {storage.MARKER: 1, 'root': digest,
                  'sha256': storage._hash(logical), 'logical_bytes': len(logical)}
    storage.materialize(home, {digest: physical})
    return home / 'current.json', descriptor, digest, value


def test_owned_member_parts_real_admission_reuses_objects_and_refusal_keeps_fallback(tmp_path, monkeypatch):
    path, descriptor, digest, value = _owned_member_fixture(tmp_path)
    with storage.normalization_scope():
        memo = storage._normalization_memo()
        assert storage.decode(path, descriptor) == value
        entry = memo['entries'][digest]
        fields = entry[-1][3]
        assert type(fields) is storage._MemberParts
        parts = tuple(field[1] for field in fields)
        assert entry[4] >= storage._entry_index_cost(entry[-1])
        with monkeypatch.context() as scope:
            def forbidden(*args):
                raise AssertionError('already admitted leaf was compiled again')
            scope.setattr(storage, '_member_span_leaf', forbidden)
            result = storage.decode(path, descriptor)
        assert result == value and all(a is b for a, b in zip(parts, (f[1] for f in memo['entries'][digest][-1][3])))
        result['key-000'] = 'changed consumer'
        assert storage.decode(path, descriptor) == value
    assert memo['closed'] and not memo['entries'] and memo['budget']['bytes'] == 0
    # References retained by this test are immutable owned bytes, not dangling views.
    assert parts[0] == b'"key-000":"value-000"'
    cost = storage._entry_index_cost
    monkeypatch.setattr(storage, '_entry_index_cost', lambda stream: cost(stream) + storage.MAX_LOGICAL_BYTES)
    observed = []
    original = storage._authenticate_stream
    def authenticate(decoded, stream, bound):
        observed.append(len(stream))
        return original(decoded, stream, bound)
    monkeypatch.setattr(storage, '_authenticate_stream', authenticate)
    with storage.normalization_scope():
        assert storage.decode(path, descriptor) == value
        assert not storage._normalization_memo()['entries'] and observed == [3]


@pytest.mark.parametrize('fault', ['same_size_mutation', 'missing', 'symlink'])
def test_owned_member_parts_do_not_authenticate_changed_physical_bytes(tmp_path, fault):
    path, descriptor, digest, value = _owned_member_fixture(tmp_path)
    with storage.normalization_scope():
        assert storage.decode(path, descriptor) == value
        memo = storage._normalization_memo()
        assert type(memo['entries'][digest][-1][3]) is storage._MemberParts
        target = path.parent / 'state-blocks/v1' / (digest + '.json')
        if fault == 'same_size_mutation':
            before = target.stat()
            target.write_bytes(target.read_bytes().replace(b'value-000', b'other-000'))
            os.utime(target, ns=(before.st_atime_ns, before.st_mtime_ns))
        else:
            retained = target.with_suffix('.preserved')
            target.rename(retained)
            if fault == 'symlink':
                target.symlink_to(retained)
        with pytest.raises((OSError, ValueError)):
            storage.decode(path, descriptor)
    assert memo['closed'] and memo['budget']['bytes'] == memo['budget']['count'] == 0


def test_owned_member_parts_nested_pool_charges_and_cancellation_release(tmp_path):
    path, descriptor, digest, value = _owned_member_fixture(tmp_path)
    with pytest.raises(KeyboardInterrupt):
        with storage.normalization_scope():
            outer = storage._normalization_memo()
            assert storage.decode(path, descriptor) == value
            with storage.normalization_scope():
                inner = storage._normalization_memo()
                assert storage.decode(path, descriptor) == value
                assert inner['budget'] is outer['budget']
                assert inner['entries'][digest][-1][3] is not outer['entries'][digest][-1][3]
                expected = sum(sum(entry[4] for entry in owner['entries'].values())
                    + owner['plans'].retained_bytes + sum(handle[1] for handle in owner['handles'].values())
                    for owner in inner['budget']['memos'])
                assert inner['budget']['bytes'] == expected <= storage.MAX_LOGICAL_BYTES
                assert inner['budget']['count'] <= storage.MAX_BLOCKS
                raise KeyboardInterrupt('owned member cancellation')
    assert inner['closed'] and outer['closed']
    assert not inner['entries'] and not outer['entries']
    assert outer['budget']['bytes'] == outer['budget']['count'] == 0


def test_owned_member_parts_duplicate_map_keys_are_still_refused(tmp_path):
    path, descriptor, digest, value = _owned_member_fixture(tmp_path)
    physical = storage.canonical(['map', [digest, digest]]) + b'\n'
    root = storage._hash(physical)
    storage.materialize(path.parent, {root: physical})
    descriptor = dict(descriptor, root=root)
    with storage.normalization_scope():
        with pytest.raises(ValueError, match='overlaps'):
            storage.decode(path, descriptor)


def test_owned_member_parts_real_plan_admission_reuses_charged_parts(tmp_path, monkeypatch):
    path, descriptor, blocks, expected = subtree_plan_fixture(tmp_path)
    with storage.normalization_scope():
        assert storage.decode(path, descriptor) == expected
        memo = storage._normalization_memo()
        plan = memo['plans'][(descriptor['root'], False)]
        indexed = plan[-2]
        assert type(indexed[3]) is storage._MemberParts
        assert plan[-1] >= storage._entry_index_cost(indexed)
        parts = tuple(field[1] for field in indexed[3])
        calls = []
        original = storage._read_block
        def read(parent, name, limit, active_memo, identity):
            calls.append(name)
            return original(parent, name, limit, active_memo, identity)
        monkeypatch.setattr(storage, '_read_block', read)
        result = storage.decode(path, descriptor)
        assert result == expected and set(calls) == {name + '.json' for name in blocks}
        assert memo['plans'][(descriptor['root'], False)] is plan
        assert all(a is b for a, b in zip(parts, (field[1] for field in indexed[3])))
        result['field-0']['z'].append('changed consumer')
        assert storage.decode(path, descriptor) == expected
    assert memo['closed'] and not memo['plans'] and memo['budget']['bytes'] == 0

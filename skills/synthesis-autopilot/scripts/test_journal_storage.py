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

"""Bounded retention tests use generated native records, never user transcripts."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest
from test_run_state import engine, world, create, command
from test_observation_bridge import bridge, enroll, observe, append, pair


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
import hashlib,json,os,stat,threading,time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
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

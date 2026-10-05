"""Synthetic memory data and real bounded PM/Git owners; no native harness calls."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'synthesis-project-management/scripts'))
import context_edit as owner
import record_transaction as rt
from test_run_admission import world as _world, write_board, git

world = _world


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def configure_repository(world, repo, *, name=None, replace=False, memory=None):
    """Explicit approved workspace source, including real local fixture remotes."""
    path = world['scratch']/'.agents/repos.yaml'
    path.parent.mkdir(exist_ok=True)
    document = json.loads(path.read_text()) if path.exists() and not replace else {'workspace':'synthetic','status':'active','repos':[]}
    name = name or repo.name
    prior = next((row for row in document['repos'] if row['name'] == name), {})
    if memory is None:
        memory = prior.get('memory', {'family':'personal', 'workspace':None, 'source':'knowledge'})
    document['repos'] = [row for row in document['repos'] if row['name'] != name]
    document['repos'].append({'name':name,'path':str(repo.relative_to(world['scratch'])),
                             'remotes':{'origin':git(repo,'remote','get-url','origin')},
                             'ritual_sync':False,'default_branches':['main'],'memory':memory})
    path.write_text(json.dumps(document,sort_keys=True)+'\n')
    return path


@pytest.fixture
def capture(world):
    # Bind synthetic Git identity to the same private-family source contract
    # used by production, rather than passing caller labels as authority.
    old = world['repo']; repo = old.with_name('journal-vault'); old.rename(repo)
    world.update(repo=repo, project=repo/'projects/alpha', plan=repo/'projects/alpha/plan.md')
    world['actor']['native_payload']['cwd'] = str(repo)
    write_board(world)
    git(repo, 'remote', 'add', 'origin', str(world['scratch']/'journal-vault.git'))
    configure_repository(world,repo)
    store = world['scratch'] / 'native-store'
    store.mkdir()
    (store / 'opaque.bin').write_bytes(b'opaque synthetic native bytes')
    project = world['project']
    (project / 'archive').mkdir()
    (project / 'REFERENCE.md').write_text('# Reference\n\n<!-- end -->\n')
    workers, _ = owner._memory_owners()
    entry = {'id': 'entry-1', 'text': 'Synthetic fact.', 'sha256': digest(b'Synthetic fact.'),
             'scope': 'personal', 'workspace_hint': None}
    packet = {'schema': 1, 'harness': 'codex', 'store': workers.memory_store_snapshot(store), 'entries': [entry]}
    selection = {'family': 'personal', 'workspace': None, 'archive_dir': 'archive',
                 'routes': [{'id': 'entry-1', 'kind': 'lesson', 'key': 'synthetic-fact',
                             'file': 'REFERENCE.md', 'anchor': '<!-- end -->'}]}
    return world, store, packet, selection


def ingest(capture, **kwargs):
    world, store, packet, selection = capture
    return owner.memory_ingest(world['project'], packet, selection, store=store,
                               board=world['board'], machine='fixture-machine',
                               native_payload=world['actor']['native_payload'], **kwargs)


def publish(capture, receipt):
    world, _, _, _ = capture
    repo = world['repo']
    remote = Path(git(repo,'remote','get-url','origin'))
    subprocess.run(['git', 'init', '--bare', str(remote)], check=True, capture_output=True, timeout=10)
    git(repo, 'add', 'projects')
    git(repo, 'commit', '-m', 'Fixture publication')
    git(repo, 'push', '-u', 'origin', 'main')
    guard = world['scratch'] / 'guard'
    native = 'synthetic-ingestion-session'
    manifest = guard / 'pending' / (digest(native.encode()) + '.json')
    manifest.parent.mkdir(parents=True)
    raw = (json.dumps({'schema_version': 2, 'session_id': native,
                      'paths': list(receipt['required_files']), 'remote_paths': []}) + '\n').encode()
    manifest.write_bytes(raw)
    _, publication = owner._memory_owners()
    proof = publication.build(manifest, raw, [{'repo': str(repo), 'action': 'source-remote-ready', 'alert': None}])
    output = guard / 'publication' / manifest.name
    output.parent.mkdir()
    output.write_text(json.dumps(proof))
    manifest.unlink()
    return guard, native, digest(output.read_bytes())


def clear_plan(capture, receipt, publication):
    world, store, packet, _ = capture
    guard, native, sha = publication
    return owner.memory_clear_request(packet, receipt, store=store, board=world['board'],
                                      machine='fixture-machine', guard_root=guard, native=native,
                                      publication_sha256=sha)


def test_archive_then_actual_transaction_and_dedup(capture):
    world, store, packet, selection = capture
    before = (store / 'opaque.bin').read_bytes()
    result = ingest(capture)
    assert result['transaction']['status'] == 'committed'
    assert result['entries'][0]['status'] == 'INGESTED'
    assert packet['entries'][0]['text'] in (world['project'] / 'REFERENCE.md').read_text()
    archives = list((world['project'] / 'archive').iterdir())
    assert len(archives) == 1
    assert json.loads(archives[0].read_text())['entry'] == packet['entries'][0]
    second = ingest(capture)
    assert second['entries'][0]['status'] == 'DEDUPLICATED'
    assert second['transaction'] is None
    assert (store / 'opaque.bin').read_bytes() == before


def test_dry_run_never_emits_clear_eligible_receipt(capture):
    world, _, _, _ = capture
    result = ingest(capture, dry_run=True)
    assert result['status'] == 'DRY_RUN'
    assert not list((world['project'] / 'archive').iterdir())
    with pytest.raises(owner.ContextEditError):
        clear_plan(capture, result, (world['scratch'], 'synthetic', '0' * 64))


def test_exact_remote_bytes_eligible_but_native_capability_remains_pending(capture):
    _, store, packet, _ = capture
    result = ingest(capture)
    publication = publish(capture, result)
    plan = clear_plan(capture, result, publication)
    assert plan['status'] == 'PENDING_NATIVE_CAPABILITY'
    assert plan['eligible'] == [{'id': 'entry-1', 'sha256': packet['entries'][0]['sha256']}]
    assert plan['dispatch'] is None and plan['native_clear'] == 'NOT_EXECUTED'
    assert (store / 'opaque.bin').read_bytes() == b'opaque synthetic native bytes'


@pytest.mark.parametrize('damage', ['receipt-cas', 'canonical', 'archive', 'unpublished', 'packet'])
def test_clear_refuses_changed_or_unpublished_evidence(capture, damage):
    world, _, packet, _ = capture
    result = ingest(capture)
    publication = publish(capture, result)
    if damage == 'receipt-cas':
        publication = (*publication[:2], '0' * 64)
    elif damage == 'canonical':
        (world['project'] / 'REFERENCE.md').write_text('changed')
    elif damage == 'archive':
        next((world['project'] / 'archive').iterdir()).write_text('{}')
    elif damage == 'unpublished':
        publication = (world['scratch'] / 'absent', *publication[1:])
    else:
        packet['entries'][0]['text'] = 'altered'
        packet['entries'][0]['sha256'] = digest(b'altered')
        with pytest.raises(owner.ContextEditError):
            clear_plan(capture, result, publication)
        return
    assert clear_plan(capture, result, publication)['status'] == 'PENDING_PUBLICATION'


def test_contradiction_does_not_overwrite_or_clear(capture):
    world, _, packet, _ = capture
    ingest(capture)
    before = (world['project'] / 'REFERENCE.md').read_bytes()
    packet['entries'][0]['text'] = 'Contradictory assertion.'
    packet['entries'][0]['sha256'] = digest(b'Contradictory assertion.')
    result = ingest(capture)
    assert result['entries'][0]['status'] == 'PENDING_CONTRADICTION'
    assert result['transaction'] is None
    assert (world['project'] / 'REFERENCE.md').read_bytes() == before


@pytest.mark.parametrize('kind', sorted(owner.MEMORY_PRESERVE))
def test_always_preserve_forces_personal_root(capture, kind):
    _, _, packet, selection = capture
    packet['entries'][0].update(scope='workspace', workspace_hint='engagement')
    selection.update(family='workspace', workspace='engagement')
    selection['routes'][0]['kind'] = kind
    with pytest.raises(owner.ContextEditError, match='ALWAYS-PRESERVE'):
        ingest(capture)
    selection.update(family='personal', workspace=None)
    assert ingest(capture)['entries'][0]['status'] == 'INGESTED'


@pytest.mark.parametrize('scope,hint,family,workspace', [
    ('workspace', 'engagement', 'personal', None),
    ('workspace', 'engagement', 'workspace', 'foreign'),
    ('workspace', None, 'workspace', 'engagement'),
    ('personal', None, 'workspace', 'engagement'),
])
def test_deletion_unit_routing_refusal(capture, scope, hint, family, workspace):
    _, _, packet, selection = capture
    packet['entries'][0].update(scope=scope, workspace_hint=hint)
    selection.update(family=family, workspace=workspace)
    with pytest.raises(owner.ContextEditError):
        ingest(capture)


def test_matching_workspace_and_no_publication_promotion(capture):
    world, _, packet, selection = capture
    old=world['repo'];repo=old.with_name('engagement-vault');old.rename(repo)
    world.update(repo=repo,project=repo/'projects/alpha',plan=repo/'projects/alpha/plan.md')
    world['actor']['native_payload']['cwd']=str(repo);write_board(world)
    git(repo,'remote','set-url','origin',str(world['scratch']/'engagement-vault.git'))
    configure_repository(world,repo,replace=True,memory={'family':'workspace','workspace':'engagement','source':'knowledge'})
    packet['entries'][0].update(scope='workspace', workspace_hint='engagement')
    selection.update(family='workspace', workspace='engagement')
    assert ingest(capture)['entries'][0]['status'] == 'INGESTED'
    selection['routes'][0]['kind'] = 'public-candidate'
    assert ingest(capture)['entries'][0]['status'] == 'PENDING_PUBLICATION_DECISION'


def test_unknown_scope_and_unselected_stay_pending(capture):
    _, _, packet, selection = capture
    packet['entries'][0]['scope'] = 'unknown'
    assert ingest(capture)['entries'][0]['status'] == 'PENDING_OWNER'
    selection['routes'] = []
    assert ingest(capture)['entries'][0]['status'] == 'PENDING_ROUTING'


@pytest.mark.parametrize('damage', ['extra', 'duplicate', 'hash', 'traversal', 'symlink', 'hardlink', 'claim', 'anchor'])
def test_packet_and_owner_denials_are_nonmutating(capture, damage):
    world, _, packet, selection = capture
    target = world['project'] / 'REFERENCE.md'
    before = target.read_bytes()
    if damage == 'extra':
        packet['entries'][0]['destination'] = 'foreign'
    elif damage == 'duplicate':
        packet['entries'].append(dict(packet['entries'][0]))
    elif damage == 'hash':
        packet['entries'][0]['sha256'] = '0' * 64
    elif damage == 'traversal':
        selection['routes'][0]['file'] = '../escape.md'
    elif damage == 'symlink':
        (world['project'] / 'alias').symlink_to(target)
        selection['routes'][0]['file'] = 'alias'
    elif damage == 'hardlink':
        os.link(target, world['project'] / 'alias')
    elif damage == 'claim':
        write_board(world, claims=str(world['project'] / 'elsewhere/**'))
    else:
        selection['routes'][0]['anchor'] = 'absent'
    with pytest.raises((owner.ContextEditError, rt.RecordTransactionError, ValueError)):
        ingest(capture)
    assert target.read_bytes() == before
    assert not list((world['project'] / 'archive').iterdir())


def test_active_harness_skips_before_store_read(capture):
    world, store, packet, _ = capture
    packet['harness'] = 'claude'
    store.rename(store.with_name('moved'))
    result = ingest(capture)
    assert result['status'] == 'PENDING_ACTIVE_HARNESS'
    assert result['model_calls'] == 0


def test_store_cheap_noop_preserves_pending_and_detects_change(capture):
    world, store, _, _ = capture
    workers, _ = owner._memory_owners()
    snapshot = workers.memory_store_snapshot(store)
    args = dict(harness='codex', machine='fixture-machine', board=world['board'])
    assert workers.memory_probe(store, previous={'store': snapshot, 'complete': True}, **args)['status'] == 'UNCHANGED'
    assert workers.memory_probe(store, previous={'store': snapshot, 'complete': False}, **args)['status'] == 'PENDING_UNCHANGED'
    (store / 'opaque.bin').write_bytes(b'changed')
    assert workers.memory_probe(store, previous={'store': snapshot, 'complete': True}, **args)['status'] == 'EXPORT_REQUIRED'


@pytest.mark.parametrize('damage', ['missing', 'moved', 'symlink', 'hardlink', 'oversize', 'fifo'])
def test_store_refusals_never_claim_not_applicable(capture, damage):
    world, store, _, _ = capture
    workers, _ = owner._memory_owners()
    old = workers.memory_store_snapshot(store)
    if damage in {'missing', 'moved'}:
        store.rename(store.with_name('old-store'))
        if damage == 'moved':
            store.mkdir()
    elif damage == 'symlink':
        (store / 'alias').symlink_to(store / 'opaque.bin')
    elif damage == 'hardlink':
        os.link(store / 'opaque.bin', store / 'alias')
    elif damage == 'oversize':
        with (store / 'large').open('wb') as stream:
            stream.truncate(workers.MEMORY_MAX_FILE + 1)
    else:
        os.mkfifo(store / 'fifo')
    with pytest.raises((ValueError, OSError)):
        workers.memory_probe(store, harness='codex', machine='fixture-machine', board=world['board'],
                             previous={'store': old, 'complete': True})


def test_archive_first_interruption_and_existing_recovery(capture, monkeypatch):
    world, _, _, _ = capture
    target = world['project'] / 'REFERENCE.md'
    original = target.read_bytes()
    replace = rt.os.replace
    def interrupted(source, destination):
        if Path(destination) == target:
            assert len(list((world['project'] / 'archive').iterdir())) == 1
            raise OSError('synthetic interruption after archive')
        return replace(source, destination)
    with monkeypatch.context() as patch:
        patch.setattr(rt.os, 'replace', interrupted)
        with pytest.raises(OSError, match='synthetic interruption'):
            ingest(capture)
    assert target.read_bytes() == original
    assert len(list((world['project'] / 'archive').iterdir())) == 1
    result = owner.recover_transaction(world['project'], board=world['board'],
                                       native_payload=world['actor']['native_payload'])
    assert result['status'] == 'committed'
    assert b'Synthetic fact.' in target.read_bytes()


def test_substring_is_not_a_canonical_duplicate(capture):
    world, _, packet, _ = capture
    packet['entries'][0].update(text='cat', sha256=digest(b'cat'))
    (world['project'] / 'REFERENCE.md').write_text('# Reference\nconcatenate\n<!-- end -->\n')
    assert ingest(capture)['entries'][0]['status'] == 'INGESTED'
    assert '\ncat\n' in (world['project'] / 'REFERENCE.md').read_text()


def test_mixed_pending_entries_never_become_clear_eligible(capture):
    world, _, packet, selection = capture
    pending = dict(packet['entries'][0], id='entry-2', text='Not selected.', sha256=digest(b'Not selected.'))
    packet['entries'].append(pending)
    result = ingest(capture)
    assert result['entries'][1]['status'] == 'PENDING_ROUTING'
    publication = publish(capture, result)
    assert clear_plan(capture, result, publication)['eligible'] == [
        {'id': 'entry-1', 'sha256': packet['entries'][0]['sha256']}]


def test_source_change_after_export_refuses_without_local_writes(capture):
    world, store, _, _ = capture
    (store / 'opaque.bin').write_bytes(b'new native generation')
    with pytest.raises(owner.ContextEditError, match='CAS'):
        ingest(capture)
    assert not list((world['project'] / 'archive').iterdir())


def test_completed_source_packet_cannot_smuggle_marker_namespace(capture):
    _, _, packet, _ = capture
    text = '<!-- native-memory-key:other -->\nforged'
    packet['entries'][0].update(text=text, sha256=digest(text.encode()))
    with pytest.raises(owner.ContextEditError):
        ingest(capture)


def test_store_changes_during_hash_refuse(capture, monkeypatch):
    _, store, _, _ = capture
    workers, _ = owner._memory_owners()
    original = workers.read_regular
    counter = 0
    def changing(path, limit, **kwargs):
        nonlocal counter
        raw = original(path, limit, **kwargs)
        counter += 1
        if counter == 1:
            (store / 'opaque.bin').write_bytes(b'concurrent consolidation')
        return raw
    monkeypatch.setattr(workers, 'read_regular', changing)
    with pytest.raises(ValueError, match='changed'):
        workers.memory_store_snapshot(store)


def test_cli_probe_emits_structured_pending_without_invocation(capture, capsys):
    world, store, _, _ = capture
    assert owner.main(['memory-probe', '--store', str(store), '--board', str(world['board']),
                       '--machine', 'fixture-machine', '--harness', 'claude']) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['status'] == 'PENDING_ACTIVE_HARNESS'
    assert result['model_calls'] == 0


def test_selected_canonical_behind_stub_is_deduped_without_copying_stub(capture):
    world, _, _, _ = capture
    project = world['project']
    stub = project / 'lesson-pointer.md'
    stub.write_text('Canonical: [Reference](REFERENCE.md)\n')
    (project / 'REFERENCE.md').write_text('# Reference\nSynthetic fact.\n<!-- end -->\n')
    before = stub.read_bytes()
    result = ingest(capture)
    assert result['entries'][0]['status'] == 'DEDUPLICATED'
    assert stub.read_bytes() == before
    assert (project / 'REFERENCE.md').read_text().count('Synthetic fact.') == 1


@pytest.mark.parametrize('bound', ['files', 'time'])
def test_store_finite_bounds(capture, monkeypatch, bound):
    _, store, _, _ = capture
    workers, _ = owner._memory_owners()
    if bound == 'files':
        monkeypatch.setattr(workers, 'MEMORY_MAX_FILES', 1)
        (store / 'extra').write_text('extra')
    else:
        monkeypatch.setattr(workers, 'MEMORY_SECONDS', 0)
    with pytest.raises(ValueError, match='bound'):
        workers.memory_store_snapshot(store)


def test_simulated_supported_native_consumer_enforces_entry_hash_cas(capture):
    # Explicit synthetic in-memory consumer; not production export/clear code,
    # not an invocation of a client, and not a native acceptance receipt.
    _, store, packet, _ = capture
    result = ingest(capture)
    plan = clear_plan(capture, result, publish(capture, result))
    virtual_native_memory = {'entry-1': packet['entries'][0]['text'], 'unselected': 'Keep this.'}
    snapshots = dict(virtual_native_memory)
    def native_consume(eligible):
        cleared = []
        for item in eligible:
            if digest(virtual_native_memory.get(item['id'], '').encode()) == item['sha256']:
                virtual_native_memory.pop(item['id'])
                cleared.append(item)
        return cleared
    virtual_native_memory['entry-1'] = 'Changed after export.'
    assert native_consume(plan['eligible']) == []
    virtual_native_memory['entry-1'] = snapshots['entry-1']
    assert native_consume(plan['eligible']) == plan['eligible']
    assert virtual_native_memory == {'unselected': 'Keep this.'}
    assert (store / 'opaque.bin').read_bytes() == b'opaque synthetic native bytes'
    assert plan['native_clear'] == 'NOT_EXECUTED'


def test_missing_board_never_implies_inactive_harness(capture):
    world, store, _, _ = capture
    world['board'].rename(world['board'].with_name('retained-board.md'))
    workers, _ = owner._memory_owners()
    with pytest.raises(OSError):
        workers.memory_probe(store, harness='codex', machine='fixture-machine', board=world['board'])


def test_stale_leased_mirror_cannot_claim_inactive(capture, monkeypatch):
    world, store, _, _ = capture
    workers, _ = owner._memory_owners()
    import coordination
    def refused(*args, **kwargs):
        raise RuntimeError('synthetic lease fence unavailable')
    monkeypatch.setattr(coordination, '_check_staged_board_snapshot', refused)
    with pytest.raises(RuntimeError, match='lease fence'):
        workers.memory_probe(store, harness='codex', machine='fixture-machine', board=world['board'])


def test_foreign_loaded_dependency_cannot_supply_memory_owner(capture, monkeypatch):
    import types
    monkeypatch.setitem(sys.modules, 'ritual_workers', types.SimpleNamespace(__file__='/foreign/owner.py'))
    with pytest.raises(owner.ContextEditError, match='another source generation'):
        owner._memory_owners()


def test_clear_plan_reads_each_required_file_once(capture, monkeypatch):
    _, _, packet, selection = capture
    packet['entries'].append(dict(packet['entries'][0], id='entry-2', text='Second fact.', sha256=digest(b'Second fact.')))
    selection['routes'].append(dict(selection['routes'][0], id='entry-2', key='second-fact'))
    result = ingest(capture)
    publication = publish(capture, result)
    workers, _ = owner._memory_owners()
    original = workers.read_regular
    reads = {}
    def counted(path, limit, **kwargs):
        if str(path) in result['required_files']:
            reads[str(path)] = reads.get(str(path), 0) + 1
        return original(path, limit, **kwargs)
    monkeypatch.setattr(workers, 'read_regular', counted)
    assert len(clear_plan(capture, result, publication)['eligible']) == 2
    assert reads == {path: 1 for path in result['required_files']}


@pytest.mark.parametrize('reference', ['future:opaque', 'a2a:opaque'])
def test_unknown_active_reference_stays_pending_before_store_read(capture, monkeypatch, reference):
    world, store, _, _ = capture;workers,_=owner._memory_owners()
    world['board'].write_text(world['board'].read_text().replace('cc:01990000-0000-7000-8000-000000000022',reference))
    def forbidden(_): raise AssertionError('unknown active scheme cannot authorize a store read')
    monkeypatch.setattr(workers,'memory_store_snapshot',forbidden)
    assert workers.memory_probe(store,harness='codex',machine='fixture-machine',board=world['board'])['status']=='PENDING_ACTIVE_HARNESS'


@pytest.mark.parametrize('complete',[False,True])
def test_unchanged_memory_observation_rechecks_final_board(capture, monkeypatch, complete):
    world,store,_,_=capture;workers,_=owner._memory_owners();original=workers.memory_store_snapshot
    previous={'store':original(store),'complete':complete}
    def changed(path):
        result=original(path);world['board'].write_text(world['board'].read_text()+'\nchanged during fingerprint\n');return result
    monkeypatch.setattr(workers,'memory_store_snapshot',changed)
    with pytest.raises(ValueError,match='coordination changed'):
        workers.memory_probe(store,harness='codex',machine='fixture-machine',board=world['board'],previous=previous)


@pytest.mark.parametrize('change',['foreign-origin','ambiguous-origin','physical-family','missing-origin'])
def test_memory_destination_git_identity_refuses_before_effect(capture, change):
    world,_,_,_=capture;repo=world['repo'];target=world['project']/'REFERENCE.md';before=target.read_bytes()
    if change=='foreign-origin':git(repo,'remote','set-url','origin',str(world['scratch']/'engagement-vault.git'))
    elif change=='ambiguous-origin':git(repo,'remote','set-url','--add','origin',str(world['scratch']/'foreign-vault.git'))
    elif change=='missing-origin':git(repo,'remote','remove','origin')
    else:
        new=repo.with_name('engagement-vault');repo.rename(new)
        world.update(repo=new,project=new/'projects/alpha',plan=new/'projects/alpha/plan.md');world['actor']['native_payload']['cwd']=str(new);write_board(world);target=world['project']/'REFERENCE.md'
    with pytest.raises(owner.ContextEditError):ingest(capture)
    assert target.read_bytes()==before and not list((world['project']/'archive').iterdir())


def canonical_capture(capture, kind):
    world,_,_,selection=capture;own_project=world['project'];own_repo=world['repo']
    if kind=='lesson':
        root=own_repo/'lessons';root.mkdir();target=root/'record.md';target.write_text('# Lesson\n<!-- end -->\n')
        workspace=f'{own_repo} @ main'
    else:
        source=world['scratch']/'private-skill-library';source.mkdir()
        git(source,'init','-b','main');git(source,'config','user.email','fixture@example.invalid');git(source,'config','user.name','Fixture')
        git(source,'remote','add','origin',str(world['scratch']/'private-skill-library.git'))
        configure_repository(world,source,memory={'family':'personal','workspace':None,'source':'private-skills'})
        root=source/'voice-example';root.mkdir();target=root/'SKILL.md';target.write_text('---\nname: voice-example\n---\n# Voice\n<!-- end -->\n')
        git(source,'add','voice-example');git(source,'commit','-m','Fixture canonical skill')
        workspace=f'{own_repo} @ main, {source} @ main'
    (root/'archive').mkdir();world['project']=root
    selection['routes'][0].update(kind=kind,file=target.name)
    write_board(world,claims=f'{own_project}/**, {root}/**',workspace=workspace)
    return own_project,target


@pytest.mark.parametrize('kind',['lesson','voice'])
def test_canonical_home_uses_actual_registered_owner_and_exact_claims(capture, kind):
    own_project,target=canonical_capture(capture,kind);world,_,packet,_=capture
    result=ingest(capture)
    assert result['transaction']['status']=='committed'
    assert packet['entries'][0]['text'] in target.read_text()
    journal=Path(result['transaction']['journal'])/'manifest.json';manifest=json.loads(journal.read_text())
    assert manifest['authority']['project_root']==str(own_project)
    assert manifest['project']==str(world['project'])
    assert manifest['authority']['canonical_home']['record_root']==str(world['project'])
    assert ingest(capture)['entries'][0]['status']=='DEDUPLICATED'


@pytest.mark.parametrize('kind',['lesson','voice'])
@pytest.mark.parametrize('bad',['claim','registered-project','native','wrong-kind'])
def test_canonical_home_cannot_bypass_ordinary_project_admission(capture,kind,bad):
    own_project,target=canonical_capture(capture,kind);world,_,_,selection=capture;before=target.read_bytes()
    if bad=='claim':
        world['board'].write_text(world['board'].read_text().replace(str(world['project'])+'/**',str(world['scratch']/'unrelated')+'/**'))
    elif bad=='registered-project':
        (own_project.parent/'index.yaml').write_text('- id: different\n  status: active\n')
    elif bad=='native':world['actor']['native_payload']['session_id']='foreign'
    else:selection['routes'][0]['kind']='contract'
    with pytest.raises((owner.ContextEditError,rt.RecordTransactionError,ValueError)):ingest(capture)
    assert target.read_bytes()==before and not list((world['project']/'archive').iterdir())


@pytest.mark.parametrize('kind',['lesson','voice'])
def test_canonical_memory_recovery_preserves_original_root_binding(capture,monkeypatch,kind):
    _,target=canonical_capture(capture,kind);world,_,packet,_=capture;replace=rt.os.replace
    def stop(src,dst):
        if Path(dst)==target:raise OSError('retained canonical interruption')
        return replace(src,dst)
    with monkeypatch.context() as patch:
        patch.setattr(rt.os,'replace',stop)
        with pytest.raises(OSError):ingest(capture)
    assert list((world['project']/'archive').iterdir())
    assert packet['entries'][0]['text'] not in target.read_text()
    assert owner.recover_transaction(world['project'],board=world['board'],native_payload=world['actor']['native_payload'])['status']=='committed'
    assert packet['entries'][0]['text'] in target.read_text()


@pytest.mark.parametrize('kind',['project','lesson','voice'])
def test_memory_origin_binding_rechecked_during_effect_and_recovery(capture,monkeypatch,kind):
    world,_,packet,_=capture
    if kind=='project':target=world['project']/'REFERENCE.md'
    else:_,target=canonical_capture(capture,kind)
    before=target.read_bytes();link=rt.os.link;repo=Path(rt.memory_repository(world['project'])['repository']);origin=git(repo,'remote','get-url','origin')
    def change_after_archive(src,dst,**kwargs):
        result=link(src,dst,**kwargs)
        if Path(dst).parent==world['project']/'archive':
            git(repo,'remote','set-url','origin',str(world['scratch']/'foreign-vault.git'))
        return result
    with monkeypatch.context() as patch:
        patch.setattr(rt.os,'link',change_after_archive)
        with pytest.raises(rt.RecordTransactionError):ingest(capture)
    assert target.read_bytes()==before
    with pytest.raises(rt.RecordTransactionError):
        owner.recover_transaction(world['project'],board=world['board'],native_payload=world['actor']['native_payload'])
    assert target.read_bytes()==before
    git(repo,'remote','set-url','origin',origin)
    assert owner.recover_transaction(world['project'],board=world['board'],native_payload=world['actor']['native_payload'])['status']=='committed'
    assert packet['entries'][0]['text'] in target.read_text()


def test_memory_deletion_unit_comes_from_actual_enrolled_team_contract(capture):
    from test_team_contract import contract
    import team_contract
    world,_,_,_=capture;old=world['repo'];repo=old.with_name('engagement-vault');old.rename(repo)
    world.update(repo=repo,project=repo/'projects/alpha',plan=repo/'projects/alpha/plan.md');world['actor']['native_payload']['cwd']=str(repo);write_board(world)
    remote='https://git.example/org-one/engagement-vault.git';git(repo,'remote','set-url','origin',remote)
    configure_repository(world,repo,replace=True,memory={'family':'workspace','workspace':'unit-one','source':'knowledge'})
    document=contract();document['repositories'][0].update(remote=remote,audience='private',readers=['p-one'])
    raw=(json.dumps(document,sort_keys=True)+'\n').encode();path=repo/'projects/team.json';path.write_bytes(raw)
    marker='# Synthesis-Team: team.json @ '+digest(raw)+' / repo-one\n'
    index=repo/'projects/index.yaml';index.write_text(marker+index.read_text())
    actual=team_contract.registry_binding(index)
    assert actual['document']['deletion_unit']=='unit-one'
    binding=rt.memory_repository(world['project'])
    assert binding['workspace']=='unit-one' and binding['source']=='knowledge'
    assert binding['team_sha256']==digest(raw)


@pytest.mark.parametrize('remote', [
    'https://public.example/outsider/journal-vault.git',
    'https://synthetic-secret@public.example/outsider/journal-vault.git',
])
def test_same_named_unenrolled_origin_refused_without_effect(capture, remote):
    world,_,_,_=capture;before=(world['project']/'REFERENCE.md').read_bytes()
    git(world['repo'],'remote','set-url','origin',remote)
    with pytest.raises(owner.ContextEditError) as error:ingest(capture)
    assert 'synthetic-secret' not in str(error.value)
    assert (world['project']/'REFERENCE.md').read_bytes()==before
    assert not list((world['project']/'archive').iterdir())
    assert not (world['project']/rt.STORE).exists()


@pytest.mark.parametrize('remote', [
    'https://synthetic-secret@git.example/approved/journal-vault.git',
    'https://name:synthetic-secret@git.example/approved/journal-vault.git',
    'ssh://git:synthetic-secret@git.example/approved/journal-vault.git',
    'https://git.example/approved/journal-vault.git?token=synthetic-secret',
    'https://git.example/approved/journal-vault.git#synthetic-secret',
])
def test_even_configured_credentials_never_become_authority(capture, remote):
    world,_,_,_=capture;git(world['repo'],'remote','set-url','origin',remote)
    configure_repository(world,world['repo'])
    with pytest.raises(owner.ContextEditError) as error:ingest(capture)
    assert 'synthetic-secret' not in str(error.value)
    assert not (world['project']/rt.STORE).exists()
    assert not list((world['project']/'archive').iterdir())


def test_approved_full_identity_receipt_contains_only_remote_digest(capture):
    world,_,_,_=capture;remote='https://git.example/approved/journal-vault.git'
    git(world['repo'],'remote','set-url','origin',remote);configure_repository(world,world['repo'])
    result=ingest(capture);journal=Path(result['transaction']['journal'])/'manifest.json'
    raw=journal.read_text();proof=json.loads(raw)['authority']['canonical_home']['approved_source']
    assert remote not in raw and 'origin' not in proof
    assert len(proof['remote_identity_sha256'])==64
    assert proof['declaration_sha256']==digest((world['scratch']/'.agents/repos.yaml').read_bytes())


def test_foreign_checkout_same_origin_cannot_substitute_for_declared_repo(capture):
    world,_,_,_=capture;old=world['repo'];imposter=world['scratch']/'imposter'
    git(old,'add','projects');git(old,'commit','-m','Fixture capture')
    git(old,'clone',str(old),str(imposter))
    git(imposter,'remote','set-url','origin',git(old,'remote','get-url','origin'))
    (imposter/'projects/alpha/archive').mkdir()
    world.update(repo=imposter,project=imposter/'projects/alpha',plan=imposter/'projects/alpha/plan.md')
    world['actor']['native_payload']['cwd']=str(imposter);write_board(world)
    with pytest.raises(owner.ContextEditError):ingest(capture)
    assert not list((world['project']/'archive').iterdir())


def memory_worktree(capture):
    world,_,_,_=capture;primary=world['repo']
    git(primary,'add','projects');git(primary,'commit','-m','Fixture capture')
    checkout=world['scratch']/'.worktrees/arbitrary-checkout-name'
    checkout.parent.mkdir()
    git(primary,'worktree','add','-b','memory-topic',str(checkout))
    world.update(repo=checkout,project=checkout/'projects/alpha',plan=checkout/'projects/alpha/plan.md')
    (world['project']/'archive').mkdir()
    world['actor']['native_payload']['cwd']=str(checkout)
    write_board(world,workspace=f'{checkout} @ memory-topic')
    return primary,checkout


@pytest.mark.parametrize('kind',['project','lesson'])
def test_legitimate_reciprocal_worktree_uses_declared_primary_identity(capture,kind):
    world,_,_,selection=capture;primary,checkout=memory_worktree(capture)
    if kind=='lesson':
        own=world['project'];root=checkout/'lessons';root.mkdir();(root/'archive').mkdir()
        (root/'record.md').write_text('# Lesson\n<!-- end -->\n');world['project']=root
        selection['routes'][0]['file']='record.md'
        write_board(world,workspace=f'{checkout} @ memory-topic',claims=f'{own}/**, {root}/**')
    result=ingest(capture)
    assert result['transaction']['status']=='committed'
    proof=json.loads((Path(result['transaction']['journal'])/'manifest.json').read_text())['authority']['canonical_home']
    assert proof['family']=='personal' and proof['approved_source']['declared_checkout']==str(primary)
    assert proof['approved_source']['physical']['checkout']==str(checkout)


@pytest.mark.parametrize('damage',['backlink','commondir','gitfile'])
def test_worktree_metadata_substitution_refuses_before_effect(capture,damage):
    world,_,_,_=capture;primary,checkout=memory_worktree(capture)
    directory=Path((checkout/'.git').read_text().strip().removeprefix('gitdir: '))
    if damage=='backlink':(directory/'gitdir').write_text(str(primary/'.git')+'\n')
    elif damage=='commondir':
        foreign=world['scratch']/'foreign';foreign.mkdir();git(foreign,'init','-b','main')
        (directory/'commondir').write_text(str(foreign/'.git')+'\n')
    else:(checkout/'.git').write_text('gitdir: '+str(primary/'.git')+'\n')
    with pytest.raises((owner.ContextEditError,rt.RecordTransactionError,RuntimeError)):ingest(capture)
    assert not list((world['project']/'archive').iterdir())


@pytest.mark.parametrize('kind',['project','lesson','voice'])
@pytest.mark.parametrize('change',['bytes','replace'])
def test_declaration_cas_preserves_interruption_and_recovery(capture,monkeypatch,kind,change):
    world,_,packet,_=capture
    if kind=='project':target=world['project']/'REFERENCE.md'
    else:_,target=canonical_capture(capture,kind)
    before=target.read_bytes();path=world['scratch']/'.agents/repos.yaml';original=path.read_bytes();link=rt.os.link
    retained=path.with_name('repos-retained.yaml')
    def changed(src,dst,**kwargs):
        result=link(src,dst,**kwargs)
        if Path(dst).parent==world['project']/'archive':
            if change=='replace':path.rename(retained)
            path.write_bytes(original if change=='replace' else original+b'\n')
        return result
    with monkeypatch.context() as patch:
        patch.setattr(rt.os,'link',changed)
        with pytest.raises(rt.RecordTransactionError):ingest(capture)
    assert target.read_bytes()==before and list((world['project']/'archive').iterdir())
    with pytest.raises(rt.RecordTransactionError):
        owner.recover_transaction(world['project'],board=world['board'],native_payload=world['actor']['native_payload'])
    assert target.read_bytes()==before
    if change=='replace':
        path.rename(path.with_name('repos-replacement-retained.yaml'));retained.rename(path)
    else:path.write_bytes(original)
    assert owner.recover_transaction(world['project'],board=world['board'],native_payload=world['actor']['native_payload'])['status']=='committed'
    assert packet['entries'][0]['text'] in target.read_text()


def test_destination_local_declaration_cannot_replace_native_owner_workspace(capture):
    world,_,_,_=capture;own,_=canonical_capture(capture,'voice');old=world['project'].parent
    foreign=world['scratch'].with_name(world['scratch'].name+'-foreign');foreign.mkdir();source=foreign/'private-skill-library';old.rename(source)
    world['project']=source/'voice-example'
    # Explicit foreign declaration is valid by itself but is not the owner's.
    fake=dict(world,scratch=foreign);configure_repository(fake,source,memory={'family':'personal','workspace':None,'source':'private-skills'})
    assert rt.memory_record_home(world['project'])['source']=='private-skills'
    write_board(world,workspace=f"{world['repo']} @ main, {source} @ main",claims=f"{own}/**, {world['project']}/**")
    with pytest.raises((owner.ContextEditError,rt.RecordTransactionError)):ingest(capture)
    assert not list((world['project']/'archive').iterdir())


@pytest.mark.parametrize('name',['repo_state','credential_paths'])
def test_foreign_loaded_repository_owner_is_refused(capture,monkeypatch,name):
    import types
    fake=types.ModuleType(name);fake.__file__='/foreign/'+name+'.py'
    monkeypatch.setitem(sys.modules,name,fake)
    with pytest.raises(owner.ContextEditError):ingest(capture)


def test_enrolled_identity_without_declaration_still_binds_exact_private_source(capture):
    test_memory_deletion_unit_comes_from_actual_enrolled_team_contract(capture)
    world,_,_,_=capture;path=world['scratch']/'.agents/repos.yaml'
    path.rename(path.with_name('repos-retained.yaml'))
    proof=rt.memory_repository(world['project'])
    assert proof['workspace']=='unit-one' and proof['approved_source']['enrollment_sha256']==proof['team_sha256']
    git(world['repo'],'remote','set-url','origin','https://outsider.example/wrong/engagement-vault.git')
    with pytest.raises(rt.RecordTransactionError):rt.memory_repository(world['project'])


def test_shared_enrollment_cannot_become_private_memory_source(capture):
    test_memory_deletion_unit_comes_from_actual_enrolled_team_contract(capture)
    world,_,_,_=capture;repo=world['repo'];path=repo/'projects/team.json';doc=json.loads(path.read_text())
    doc['repositories'][0].update(audience='shared',readers=['p-one','p-two'])
    old=digest(path.read_bytes());raw=(json.dumps(doc,sort_keys=True)+'\n').encode();path.write_bytes(raw)
    index=repo/'projects/index.yaml';index.write_text(index.read_text().replace(old,digest(raw)))
    with pytest.raises(rt.RecordTransactionError):rt.memory_repository(world['project'])


@pytest.mark.parametrize('order', ['registry-first', 'memory-first'])
def test_memory_and_registry_share_exact_transaction_history(capture, order):
    world, _, packet, _ = capture
    index = world['repo'] / 'projects/index.yaml'
    write_board(world, claims=f"{world['project']}/**, {index}")
    def registry():
        return owner.patch_registry(world['project'], 'alpha', {'note': 'Synthetic registry fact'},
            digest(index.read_bytes()), board=world['board'], native_payload=world['actor']['native_payload'])
    actions = (registry, lambda: ingest(capture)) if order == 'registry-first' else (lambda: ingest(capture), registry)
    results = [action() for action in actions]
    assert 'Synthetic registry fact' in index.read_text()
    assert packet['entries'][0]['text'] in (world['project'] / 'REFERENCE.md').read_text()
    assert all(result.get('status') == 'committed' or result.get('transaction', {}).get('status') == 'committed' for result in results)
    git(world['repo'], 'add', 'projects/index.yaml')
    from test_record_transaction import registry_gate
    assert registry_gate(world) == 0


def test_memory_home_refuses_prep_selector_before_archive(capture):
    world, _, _, _ = capture
    before = {str(p):p.read_bytes() for p in world['project'].rglob('*') if p.is_file()}
    world['actor']['native_payload']['meeting_prep_share'] = {'id': '0' * 32, 'workspace': 'synthetic'}
    with pytest.raises((owner.ContextEditError, rt.RecordTransactionError), match='prep|memory|grant'):
        ingest(capture)
    assert {str(p):p.read_bytes() for p in world['project'].rglob('*') if p.is_file()} == before


@pytest.mark.parametrize('memory', [
    None, {}, [],
    {'family':'personal','workspace':None,'source':'knowledge','extra':True},
    {'family':'public','workspace':None,'source':'knowledge'},
    {'family':True,'workspace':None,'source':'knowledge'},
    {'family':'personal','workspace':'engagement','source':'knowledge'},
    {'family':'workspace','workspace':None,'source':'knowledge'},
    {'family':'workspace','workspace':True,'source':'knowledge'},
    {'family':'workspace','workspace':'../foreign','source':'knowledge'},
    {'family':'workspace','workspace':'engagement','source':'private-skills'},
    {'family':'personal','workspace':None,'source':'arbitrary-files'},
])
def test_memory_scope_metadata_is_closed_before_effect(capture, memory):
    world,_,_,_=capture; path=world['scratch']/'.agents/repos.yaml'
    document=json.loads(path.read_text());document['repos'][0]['memory']=memory
    path.write_text(json.dumps(document)+'\n')
    target=world['project']/'REFERENCE.md';before=target.read_bytes()
    with pytest.raises(owner.ContextEditError):ingest(capture)
    assert target.read_bytes()==before and not list((world['project']/'archive').iterdir())
    assert not (world['project']/rt.STORE).exists()


def test_memory_scope_missing_metadata_never_uses_repository_name(capture):
    world,_,_,_=capture;path=world['scratch']/'.agents/repos.yaml'
    document=json.loads(path.read_text());document['repos'][0].pop('memory')
    path.write_text(json.dumps(document)+'\n')
    with pytest.raises(owner.ContextEditError):ingest(capture)
    assert not list((world['project']/'archive').iterdir())


@pytest.mark.parametrize('memory', [
    {'family':'workspace','workspace':'engagement','source':'knowledge'},
    {'family':'personal','workspace':None,'source':'private-skills'},
])
def test_caller_selection_cannot_relabel_configured_memory_scope(capture, memory):
    world,_,_,_=capture
    configure_repository(world,world['repo'],memory=memory)
    with pytest.raises(owner.ContextEditError):ingest(capture)
    assert not list((world['project']/'archive').iterdir())


@pytest.mark.parametrize('memory', [
    {'family':'personal','workspace':None,'source':'knowledge'},
    {'family':'personal','workspace':None,'source':'private-skills'},
    {'family':'workspace','workspace':'other-unit','source':'knowledge'},
])
def test_configured_memory_scope_must_equal_pinned_enrollment(capture, memory):
    test_memory_deletion_unit_comes_from_actual_enrolled_team_contract(capture)
    world,_,_,_=capture;configure_repository(world,world['repo'],memory=memory)
    with pytest.raises(rt.RecordTransactionError):rt.memory_repository(world['project'])
    assert not list((world['project']/'archive').iterdir())


@pytest.mark.parametrize('kind', ['project','lesson','voice'])
def test_memory_scope_change_after_archive_refuses_and_recovers(capture, monkeypatch, kind):
    world,_,packet,_=capture
    if kind=='project':target=world['project']/'REFERENCE.md'
    else:_,target=canonical_capture(capture,kind)
    before=target.read_bytes();path=world['scratch']/'.agents/repos.yaml';original=path.read_bytes();link=rt.os.link
    def change_after_archive(src,dst,**kwargs):
        result=link(src,dst,**kwargs)
        if Path(dst).parent==world['project']/'archive':
            document=json.loads(path.read_text())
            document['repos'][0]['memory']={'family':'workspace','workspace':'foreign-unit','source':'knowledge'}
            path.write_text(json.dumps(document)+'\n')
        return result
    with monkeypatch.context() as patch:
        patch.setattr(rt.os,'link',change_after_archive)
        with pytest.raises(rt.RecordTransactionError):ingest(capture)
    assert target.read_bytes()==before
    with pytest.raises(rt.RecordTransactionError):
        owner.recover_transaction(world['project'],board=world['board'],native_payload=world['actor']['native_payload'])
    assert target.read_bytes()==before
    path.write_bytes(original)
    result=owner.recover_transaction(world['project'],board=world['board'],native_payload=world['actor']['native_payload'])
    assert result['status']=='committed' and packet['entries'][0]['text'] in target.read_text()


@pytest.mark.parametrize('location', ['nested','sibling','missing-skill'])
def test_configured_private_skill_source_does_not_authorize_arbitrary_homes(capture, location):
    world,_,_,_=capture;_,target=canonical_capture(capture,'voice');source=world['project'].parent
    if location=='missing-skill':target.rename(target.with_name('SKILL-retained.md'))
    else:
        root=(source/'nested'/'voice-other') if location=='nested' else (source.parent/'voice-other')
        root.mkdir(parents=True);(root/'SKILL.md').write_text('---\nname: voice-other\n---\n<!-- end -->\n');(root/'archive').mkdir()
        world['project']=root
    with pytest.raises(owner.ContextEditError):ingest(capture)
    assert not list((world['project']/'archive').iterdir())


@pytest.mark.parametrize('kind', ['project','lesson','voice'])
def test_installed_memory_owner_repeats_identity_and_actual_ingestion(capture, tmp_path, kind):
    world,store,packet,selection=capture
    if kind!='project':canonical_capture(capture,kind)
    scripts=Path(__file__).resolve().parents[2]/'synthesis-onboarding/scripts'
    sys.path.insert(0,str(scripts))
    import runtime_payload
    source=Path(__file__).resolve().parents[3];home=tmp_path/'installed-home'
    for _,relative,target,mode in runtime_payload._specs(home,home/'state',{'git-hooks'}):
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((source/relative).read_bytes());target.chmod(mode)
    installed=home/'.synthesis/git-hooks'
    inputs={'packet':packet,'selection':selection,'native':world['actor']['native_payload']}
    for name,doc in inputs.items():(tmp_path/(name+'.json')).write_text(json.dumps(doc)+'\n')
    expected=rt.memory_repository(world['project'])
    request={'root':str(world['project']),'expected':expected,'cli':['memory-ingest','--project',str(world['project']),'--store',str(store),'--board',str(world['board']),'--machine','fixture-machine','--packet',str(tmp_path/'packet.json'),'--selection',str(tmp_path/'selection.json'),'--native-payload',str(tmp_path/'native.json')]}
    request_path=tmp_path/'request.json';request_path.write_text(json.dumps(request)+'\n')
    code="""import contextlib,io,json,sys,types
sys.path.insert(0,sys.argv[1])
import record_transaction as rt
import context_edit as owner
request=json.load(open(sys.argv[2]))
for _ in range(2):
    assert rt.memory_repository(request['root'])==request['expected']
results=[]
for _ in range(2):
    output=io.StringIO()
    with contextlib.redirect_stdout(output):status=owner.main(request['cli'])
    assert status==0,output.getvalue()
    results.append(json.loads(output.getvalue()))
assert results[0]['transaction']['status']=='committed'
assert results[1]['entries'][0]['status']=='DEDUPLICATED'
foreign=types.ModuleType('repo_state');foreign.__file__='/foreign/repo_state.py'
sys.modules['repo_state']=foreign
try:rt.memory_repository(request['root'])
except rt.RecordTransactionError:pass
else:raise AssertionError('foreign owner accepted after repeated cold calls')
print(json.dumps({'repeated_identity':True,'committed':True,'deduplicated':True,'foreign_owner_refused':True}))
"""
    command=[sys.executable,'-I','-B','-c',code,str(installed),str(request_path)]
    result=subprocess.run(command,cwd=tmp_path,capture_output=True,text=True,timeout=30)
    (tmp_path/'cold-owner-result.json').write_text(json.dumps({'argv':command,'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr},indent=2)+'\n')
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)=={'repeated_identity':True,'committed':True,'deduplicated':True,'foreign_owner_refused':True}



def test_cold_source_memory_publication_reads_compact_manifest(tmp_path):
    script = r"""
import hashlib, json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
sys.path.insert(0, str(Path(sys.argv[1]).parents[1] / "synthesis-agent-conformance/vendor/pyyaml"))
import context_edit
_, publication = context_edit._memory_owners()
codec = sys.modules["pending_manifest"]
native = "codex:synthetic-cold-memory"
target = Path(sys.argv[2]).resolve() / "record.md"
manifest = target.parent / "pending" / (hashlib.sha256(native.encode()).hexdigest() + ".json")
logical = {"schema_version": 2, "session_id": native, "paths": [str(target)],
           "remote_paths": [str(target)]}
raw = json.dumps(codec.encode_pending_manifest(logical)).encode()
assert publication._manifest(manifest, raw, native) == [target]
assert Path(codec.__file__).resolve() == Path(sys.argv[3]).resolve()
assert "checkpoint_sync" not in sys.modules
"""
    scripts = Path(owner.__file__).resolve().parent
    codec = scripts.parents[1] / "synthesis-repo-guard/pending_manifest.py"
    result = subprocess.run([sys.executable, "-I", "-S", "-B", "-c", script,
                             str(scripts), str(tmp_path), str(codec)],
                            cwd=tmp_path, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr


def test_foreign_loaded_pending_codec_cannot_supply_memory_owner(monkeypatch):
    import types
    monkeypatch.setitem(sys.modules, "pending_manifest",
                        types.SimpleNamespace(__file__="/foreign/pending_manifest.py"))
    with pytest.raises(owner.ContextEditError, match="another source generation"):
        owner._memory_owners()


@pytest.mark.parametrize('harness,expected', [('claude', 'PENDING_ACTIVE_HARNESS'), ('codex', 'EXPORT_REQUIRED')])
def test_memory_probe_uses_board_contract_for_retained_history(capture, harness, expected):
    world, store, _, _ = capture
    workers, _ = owner._memory_owners()
    board = world['board']
    raw = board.read_bytes() + b'\n<!-- retained synthetic history: ' + b'x' * (2 * 1024 * 1024) + b' -->\n'
    board.write_bytes(raw)
    result = workers.memory_probe(store, harness=harness, machine='fixture-machine', board=board)
    assert result['status'] == expected
    assert result['model_calls'] == 0
    assert board.read_bytes() == raw
    assert (store / 'opaque.bin').read_bytes() == b'opaque synthetic native bytes'
    if expected == 'EXPORT_REQUIRED':
        assert result['board_sha256'] == digest(raw)


def test_memory_probe_still_refuses_existing_board_limit(capture):
    world, store, _, _ = capture
    workers, _ = owner._memory_owners()
    from board_grammar import MAX_MESSAGE_BOARD_BYTES
    world['board'].write_bytes(b'x' * (MAX_MESSAGE_BOARD_BYTES + 1))
    with pytest.raises(ValueError, match='bound|limit'):
        workers.memory_probe(store, harness='codex', machine='fixture-machine', board=world['board'])

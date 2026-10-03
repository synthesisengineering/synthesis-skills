from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import pytest

sys.path.insert(0, str(Path(__file__).parent))
import prep_init as prep


def repo(tmp_path, name='one'):
    path = tmp_path / name
    path.mkdir()
    subprocess.run(['git', 'init', '-q', str(path)], check=True, timeout=10)
    return path


def cli(tmp_path, *args):
    home = tmp_path / 'synthetic-home'
    home.mkdir(exist_ok=True)
    env = dict(os.environ, HOME=str(home), PYTHONDONTWRITEBYTECODE='1')
    return subprocess.run([sys.executable, str(Path(prep.__file__)), *args], env=env,
                          capture_output=True, text=True, timeout=10, cwd=tmp_path)


def test_default_never_selects_home_or_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('HOME', str(tmp_path))
    with pytest.raises(ValueError, match='explicit'):
        prep.default_root()


def test_cli_without_owner_refuses_before_writing(tmp_path):
    result = cli(tmp_path, 'init', '--name', 'Ada', '--role', 'Engineer', '--org', 'Synthetic')
    assert result.returncode == 2
    assert not (tmp_path / 'synthetic-home/.synthesis').exists()


def test_workspace_profiles_are_separate_by_explicit_owner(tmp_path):
    one, two = repo(tmp_path), repo(tmp_path, 'two')
    for owner, workspace in ((one, 'one'), (two, 'two')):
        result = cli(tmp_path, 'init', '--context-repo', str(owner), '--workspace', workspace,
                     '--name', 'Ada', '--role', 'Engineer', '--org', 'Synthetic')
        assert result.returncode == 0, result.stderr
        assert (owner / 'profiles/meeting-prep/principal.json').is_file()
    assert prep.default_root(one, 'one') != prep.default_root(two, 'two')


def migration(tmp_path):
    owner = repo(tmp_path)
    legacy = tmp_path / 'legacy'
    (legacy / 'readers').mkdir(parents=True)
    (legacy / 'principal.json').write_text('{"name":"Synthetic"}\n')
    (legacy / 'readers/one.md').write_text('# Synthetic reader\n')
    (legacy / 'readers/unresolved.md').write_text('# Unresolved ownership\n')
    request = {'schema': 1, 'legacy_root': str(legacy), 'context_repo': str(owner),
               'workspace': 'one', 'files': []}
    for name, workspace in [('principal.json', 'one'), ('readers/one.md', 'one'), ('readers/unresolved.md', None)]:
        request['files'].append({'path': name, 'sha256': hashlib.sha256((legacy / name).read_bytes()).hexdigest(), 'workspace': workspace})
    return owner, legacy, request


def test_migration_preflight_is_read_only_and_apply_preserves_unresolved(tmp_path):
    owner, legacy, request = migration(tmp_path)
    before = {p.relative_to(legacy): p.read_bytes() for p in legacy.rglob('*') if p.is_file()}
    preview = prep.migrate(request)
    assert preview['selected'] == 2 and preview['unresolved'] == 1
    assert not (owner / 'profiles').exists()
    assert before == {p.relative_to(legacy): p.read_bytes() for p in legacy.rglob('*') if p.is_file()}
    result = prep.migrate(request, apply=True)
    assert result['complete']
    root = prep.default_root(owner, 'one')
    for name in ('principal.json', 'readers/one.md'):
        assert not (legacy / name).exists()
        assert (root / name).read_bytes() == before[Path(name)]
        assert (root / name).stat().st_mode & 0o777 == 0o600
    assert (legacy / 'readers/unresolved.md').read_bytes() == before[Path('readers/unresolved.md')]
    assert prep.migrate(request, apply=True)['complete']


def test_real_cli_migration_preflight_then_apply(tmp_path):
    owner, legacy, request = migration(tmp_path)
    map_path = tmp_path / 'map.json'
    map_path.write_text(json.dumps(request))
    before = cli(tmp_path, 'migrate', '--map', str(map_path))
    assert before.returncode == 0, before.stderr
    assert (legacy / 'principal.json').exists()
    after = cli(tmp_path, 'migrate', '--map', str(map_path), '--apply')
    assert after.returncode == 0, after.stderr
    assert json.loads(after.stdout)['complete']
    assert (owner / 'profiles/meeting-prep/principal.json').is_file()


@pytest.mark.parametrize('kind', ['wrong-workspace', 'missing-workspace', 'not-repo', 'subdir', 'relative', 'traversal', 'symlink'])
def test_owner_resolution_refuses_ambiguous_or_unsafe_owner(tmp_path, kind):
    owner = repo(tmp_path)
    prep.init_principal(owner, 'Ada', 'Engineer', 'Synthetic', [], workspace='one')
    path, workspace = owner, 'one'
    if kind == 'wrong-workspace': workspace = 'two'
    elif kind == 'missing-workspace': workspace = None
    elif kind == 'not-repo': path = tmp_path
    elif kind == 'subdir': path = owner / 'profiles'
    elif kind == 'relative': path = Path('one')
    elif kind == 'traversal': path = owner / '..' / owner.name
    elif kind == 'symlink':
        path = tmp_path / 'alias'; path.symlink_to(owner, target_is_directory=True)
    with pytest.raises((ValueError, RuntimeError)):
        prep.default_root(path, workspace)


@pytest.mark.parametrize('kind', ['principal-symlink', 'reader-parent-symlink', 'principal-hardlink', 'owner-hardlink', 'owner-symlink'])
def test_existing_profile_special_paths_refuse_without_overwrite(tmp_path, kind):
    owner = repo(tmp_path)
    root = prep.default_root(owner, 'one')
    prep.add_reader(owner, 'safe', 'Safe', 'peer', workspace='one')
    foreign = tmp_path / 'foreign'; foreign.write_text('UNCHANGED')
    if kind == 'principal-symlink': (root / 'principal.json').symlink_to(foreign)
    elif kind == 'principal-hardlink': os.link(foreign, root / 'principal.json')
    elif kind == 'owner-hardlink': os.link(root / '.owner.json', tmp_path / 'owner-link')
    elif kind == 'owner-symlink':
        (root / '.owner.json').rename(tmp_path / 'saved-owner')
        (root / '.owner.json').symlink_to(tmp_path / 'saved-owner')
    else:
        (root / 'readers').rename(root / 'saved-readers')
        (root / 'readers').symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises((ValueError, RuntimeError, OSError)):
        prep.init_principal(owner, 'Ada', 'Engineer', 'Synthetic', [], workspace='one')
    assert foreign.read_text() == 'UNCHANGED'


@pytest.mark.parametrize('kind', ['hash', 'traversal', 'symlink', 'hardlink', 'duplicate', 'existing-destination', 'all-unresolved', 'source-in-git'])
def test_migration_bad_selection_preserves_all_source_bytes(tmp_path, kind):
    owner, legacy, request = migration(tmp_path)
    original = (legacy / 'principal.json').read_bytes()
    if kind == 'hash': request['files'][0]['sha256'] = '0' * 64
    elif kind == 'traversal': request['files'][0]['path'] = '../principal.json'
    elif kind == 'symlink':
        source = legacy / 'principal.json'; source.rename(tmp_path / 'original')
        source.symlink_to(tmp_path / 'original')
    elif kind == 'hardlink': os.link(legacy / 'principal.json', tmp_path / 'linked')
    elif kind == 'duplicate': request['files'].append(dict(request['files'][0]))
    elif kind == 'existing-destination': prep.init_principal(owner, 'Existing', 'Engineer', 'Synthetic', [], workspace='one')
    elif kind == 'all-unresolved':
        for entry in request['files']: entry['workspace'] = None
    elif kind == 'source-in-git': subprocess.run(['git', 'init', '-q', str(legacy)], check=True, timeout=10)
    with pytest.raises((ValueError, RuntimeError, OSError)):
        prep.migrate(request, apply=True)
    assert (legacy / 'principal.json').read_bytes() == original
    assert (legacy / 'readers/unresolved.md').is_file()


@pytest.mark.parametrize('boundary', ['link', 'rename', 'unlink'])
def test_migration_interruption_retains_custody_and_resumes(tmp_path, monkeypatch, boundary):
    owner, legacy, request = migration(tmp_path)
    real = getattr(prep.os, boundary)
    interrupted = False
    def stop(*args, **kwargs):
        nonlocal interrupted
        result = real(*args, **kwargs)
        selected = (boundary == 'link' or (boundary == 'rename' and str(args[0]) == str(legacy / 'principal.json')) or
                    (boundary == 'unlink' and '.meeting-prep-migration-' in str(args[0])))
        if selected and not interrupted:
            interrupted = True
            raise RuntimeError('synthetic interruption after effect')
        return result
    with monkeypatch.context() as patch:
        patch.setattr(prep.os, boundary, stop)
        with pytest.raises(RuntimeError, match='synthetic interruption'):
            prep.migrate(request, apply=True)
    assert interrupted
    assert prep.migrate(request, apply=True)['complete']
    assert not (legacy / 'principal.json').exists()
    assert (owner / 'profiles/meeting-prep/principal.json').read_text() == '{"name":"Synthetic"}\n'
    assert (legacy / 'readers/unresolved.md').is_file()


def test_changed_source_at_rename_is_retained_never_deleted(tmp_path, monkeypatch):
    owner, legacy, request = migration(tmp_path)
    real = prep.os.rename
    def change_then_rename(src, dst, *args, **kwargs):
        if Path(src) == legacy / 'principal.json': Path(src).write_text('CONCURRENT NEW DATA')
        return real(src, dst, *args, **kwargs)
    monkeypatch.setattr(prep.os, 'rename', change_then_rename)
    with pytest.raises(ValueError, match='move boundary'):
        prep.migrate(request, apply=True)
    retained = list(legacy.glob('.meeting-prep-migration-*/principal.json'))
    assert len(retained) == 1 and retained[0].read_text() == 'CONCURRENT NEW DATA'
    assert (owner / 'profiles/meeting-prep/principal.json').read_text() == '{"name":"Synthetic"}\n'


def test_unresolved_profile_is_not_opened(tmp_path, monkeypatch):
    owner, legacy, request = migration(tmp_path)
    unresolved = legacy / 'readers/unresolved.md'
    unresolved.unlink()
    unresolved.symlink_to(tmp_path / 'nonexistent-private-target')
    real = prep.records._snapshot
    def bounded(path, **kwargs):
        assert Path(path) != unresolved
        return real(path, **kwargs)
    monkeypatch.setattr(prep.records, '_snapshot', bounded)
    assert prep.migrate(request, apply=True)['unresolved'] == 1
    assert unresolved.is_symlink()


@pytest.mark.parametrize('change', ['source', 'destination', 'stage', 'receipt', 'receipt-symlink'])
def test_resume_preflight_revalidates_custody_without_writes(tmp_path, monkeypatch, change):
    owner, legacy, request = migration(tmp_path)
    real = prep.os.link
    def interrupted(src, dst, **kwargs):
        real(src, dst, **kwargs)
        raise RuntimeError('stop after link')
    with monkeypatch.context() as patch:
        patch.setattr(prep.os, 'link', interrupted)
        with pytest.raises(RuntimeError, match='stop after link'):
            prep.migrate(request, apply=True)
    root = prep.default_root(owner, 'one')
    receipt = next(root.glob('.migrations/*/receipt.json'))
    if change == 'source': (legacy / 'principal.json').write_text('CHANGED SOURCE')
    elif change == 'destination':
        dest = root / 'principal.json'; dest.unlink(); dest.write_text('FOREIGN DESTINATION')
    elif change == 'stage': next(root.glob('.migrations/*/files/principal.json')).write_text('CHANGED STAGE')
    elif change == 'receipt':
        data = json.loads(receipt.read_text()); data['files'][0]['stage'] = {'bad': True}; receipt.write_text(json.dumps(data))
    else:
        receipt.rename(receipt.with_suffix('.saved'))
        receipt.symlink_to(receipt.with_suffix('.saved'))
    before = {p: (p.lstat().st_ino, p.lstat().st_size, p.lstat().st_mtime_ns) for p in tmp_path.rglob('*')}
    with pytest.raises((ValueError, RuntimeError, OSError)):
        prep.migrate(request)
    assert before == {p: (p.lstat().st_ino, p.lstat().st_size, p.lstat().st_mtime_ns) for p in tmp_path.rglob('*')}
    assert (legacy / 'principal.json').exists()


@pytest.mark.parametrize('bad', ['schema-bool', 'row-list', 'identity-bool', 'extra-key'])
def test_malformed_receipt_fails_closed(tmp_path, monkeypatch, bad):
    owner, legacy, request = migration(tmp_path)
    real = prep.records._new_file
    def fail_stage(path, *args, **kwargs):
        if '/files/' in str(path): raise RuntimeError('stop before stage')
        return real(path, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(prep.records, '_new_file', fail_stage)
        with pytest.raises(RuntimeError, match='stop before stage'): prep.migrate(request, apply=True)
    receipt = next(owner.glob('profiles/meeting-prep/.migrations/*/receipt.json'))
    data = json.loads(receipt.read_text())
    if bad == 'schema-bool': data['schema'] = True
    elif bad == 'row-list': data['files'][0] = []
    elif bad == 'identity-bool': data['files'][0]['source']['bytes'] = True
    else: data['files'][0]['unexpected'] = 'data'
    receipt.write_text(json.dumps(data))
    with pytest.raises((ValueError, RuntimeError)):
        prep.migrate(request, apply=True)
    assert (legacy / 'principal.json').exists()
    assert not (owner / 'profiles/meeting-prep/principal.json').exists()


def test_destination_change_before_source_delete_retains_original(tmp_path, monkeypatch):
    owner, legacy, request = migration(tmp_path)
    real = prep._journal
    def change_after_retained(path, state):
        real(path, state)
        if state['files'][0]['status'] == 'retained':
            (owner / 'profiles/meeting-prep/principal.json').write_text('CHANGED DESTINATION')
    monkeypatch.setattr(prep, '_journal', change_after_retained)
    with pytest.raises(ValueError, match='before source deletion'):
        prep.migrate(request, apply=True)
    retained = list(legacy.glob('.meeting-prep-migration-*/principal.json'))
    assert len(retained) == 1
    assert retained[0].read_text() == '{"name":"Synthetic"}\n'


def test_partial_staging_is_retained_and_refused(tmp_path, monkeypatch):
    owner, legacy, request = migration(tmp_path)
    real = prep.records._new_file
    def partial(path, data, *args, **kwargs):
        if '/files/' in str(path):
            real(path, b'PARTIAL', *args, **kwargs)
            raise RuntimeError('partial write')
        return real(path, data, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(prep.records, '_new_file', partial)
        with pytest.raises(RuntimeError, match='partial write'): prep.migrate(request, apply=True)
    with pytest.raises(ValueError, match='partial or changed stage'): prep.migrate(request, apply=True)
    assert next(owner.glob('profiles/meeting-prep/.migrations/*/files/principal.json')).read_bytes() == b'PARTIAL'
    assert (legacy / 'principal.json').exists()


def test_profile_size_bound_precedes_owner_creation(tmp_path):
    owner = repo(tmp_path)
    with pytest.raises(ValueError, match='8 MiB'):
        prep.init_principal(owner, 'x' * prep.records.MAX_FILE_BYTES, 'Role', 'Synthetic', [], workspace='one')
    assert not (owner / 'profiles').exists()


def test_cli_rejects_duplicate_map_keys(tmp_path):
    path = tmp_path / 'map.json'
    path.write_text('{"schema":1,"schema":1}')
    result = cli(tmp_path, 'migrate', '--map', str(path), '--apply')
    assert result.returncode == 2 and 'duplicate' in result.stderr


def test_explicit_owner_resolves_independently_of_cwd(tmp_path):
    owner = repo(tmp_path)
    first = cli(tmp_path, 'resolve', '--context-repo', str(owner), '--workspace', 'one')
    nested = tmp_path / 'elsewhere'; nested.mkdir()
    second = cli(nested, 'resolve', '--context-repo', str(owner), '--workspace', 'one')
    assert first.returncode == second.returncode == 0
    assert json.loads(first.stdout) == json.loads(second.stdout)


def test_receipt_cannot_substitute_different_destination_bytes(tmp_path, monkeypatch):
    owner, legacy, request = migration(tmp_path)
    real = prep.os.rename
    def interrupted(src, dst, *args, **kwargs):
        if Path(src) == legacy / 'principal.json': raise RuntimeError('stop before move')
        return real(src, dst, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(prep.os, 'rename', interrupted)
        with pytest.raises(RuntimeError, match='stop before move'): prep.migrate(request, apply=True)
    root = prep.default_root(owner, 'one')
    receipt = next(root.glob('.migrations/*/receipt.json'))
    (root / 'principal.json').write_text('DIFFERENT BYTES')
    _, forged = prep.records._snapshot(root / 'principal.json')
    state = json.loads(receipt.read_text())
    state['files'][0]['destination'] = dict(forged)
    state['files'][0]['stage'] = dict(forged)
    receipt.write_text(json.dumps(state))
    with pytest.raises(ValueError, match='selected source'): prep.migrate(request, apply=True)
    assert (legacy / 'principal.json').read_text() == '{"name":"Synthetic"}\n'


def test_concurrent_same_owner_creation_serializes_without_overwrite(tmp_path):
    owner = repo(tmp_path)
    command = [sys.executable, str(Path(prep.__file__)), 'add-reader', '--context-repo', str(owner),
               '--workspace', 'one', '--id', 'shared', '--name', 'Synthetic', '--relationship', 'peer']
    workers = [subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(2)]
    try:
        outputs = [p.communicate(timeout=10) for p in workers]
    finally:
        for p in workers:
            if p.poll() is None: p.kill(); p.wait(timeout=3)
    assert sorted(p.returncode for p in workers) == [0, 2], outputs
    root = prep.default_root(owner, 'one')
    assert (root / 'readers/shared.md').read_text().startswith('# Synthetic\n')
    assert (root / 'readers/shared.md').stat().st_nlink == 1


def test_owner_marker_boolean_schema_refuses(tmp_path):
    owner = repo(tmp_path)
    prep.add_reader(owner, 'safe', 'Synthetic', 'peer', workspace='one')
    marker = owner / 'profiles/meeting-prep/.owner.json'
    marker.write_text('{"schema":true,"workspace":"one"}')
    with pytest.raises(ValueError, match='ambiguous owner'): prep.default_root(owner, 'one')

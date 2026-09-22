# Promoted from the private control plane (private agent-control, PRO-2, 2026-09-21); behavior tests identical, harness
# uses same-skill imports instead of the private verified runtime.
from __future__ import annotations

import json
import hashlib
import shlex
import os
import subprocess
from dataclasses import asdict, replace
from pathlib import Path
from types import SimpleNamespace

import pytest

import canonical_landing as landing

NATIVE = '01234567-1234-1234-1234-123456789abc'


def isolate_public_import_state(monkeypatch):
    """Model a fresh native hook process and restore its caller's import state."""
    import sys
    monkeypatch.setattr(sys, "path", sys.path.copy())
    monkeypatch.setattr(landing, "_DEPS", None)
    for name in ("board_grammar", "claim_scope", "peer_addressing", "coordination_schema",
                 "pointer_lock", "coordination", "coordination_archive", "publication_command"):
        # Register undo even when the name was absent: delitem(..., raising=False)
        # alone would leave a module first imported by this fixture in the next test.
        monkeypatch.setitem(sys.modules, name, None)
        monkeypatch.delitem(sys.modules, name)


def isolate_git_config(tmp_path, monkeypatch):
    """Keep runner Git policy outside disposable repository fixtures."""
    for scope in ("global", "system"):
        config = tmp_path / (scope + ".gitconfig")
        config.write_text("")
        monkeypatch.setenv("GIT_CONFIG_" + scope.upper(), str(config))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "0")
    monkeypatch.delenv("GIT_CONFIG_COUNT", raising=False)
    monkeypatch.delenv("GIT_CONFIG_PARAMETERS", raising=False)
    monkeypatch.delenv("GIT_CONFIG", raising=False)


@pytest.fixture(autouse=True)
def _fresh_public_import_state(tmp_path, monkeypatch):
    isolate_public_import_state(monkeypatch)
    isolate_git_config(tmp_path, monkeypatch)


def test_coordination_dependencies_resolve_to_sibling_modules(monkeypatch):
    coord, peer = landing.dependencies()
    scripts = Path(landing.__file__).resolve().parent
    assert Path(coord.__file__).resolve() == scripts / 'coordination.py'
    assert Path(peer.__file__).resolve() == scripts / 'peer_addressing.py'


def seed_authority(monkeypatch, tmp_path, linked, native=NATIVE):
    import coordination as coord
    monkeypatch.setattr(landing, '_DEPS', None)
    monkeypatch.setattr(landing, 'STATE_DIR', tmp_path / 'landings')
    monkeypatch.setattr(landing, 'BOARD', tmp_path / 'coordination/active-sessions.md')
    monkeypatch.setenv('SYNTHESIS_CLIENT_SESSION_REF', 'codex:' + native)
    monkeypatch.delenv('CLAUDE_CODE_SESSION_ID', raising=False)
    monkeypatch.delenv('CLAUDE_CODE_HOST_SESSION_ID', raising=False)
    assert coord.command_claim(SimpleNamespace(
        board=landing.BOARD, id=None, area=[str(linked / 'tracked.txt')],
        workspace=[f'{linked} @ feature'], context_role='owner', agent='test', machine='test',
        project='fixture', mode='execute', goal='fixture work', client_ref='codex:' + native,
    )) == 0
    return coord

def git(repo, *args):
    result = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True, check=True)
    return result.stdout.strip()

@pytest.fixture
def setup(tmp_path, monkeypatch):
    canonical = tmp_path / 'canonical'
    remote = tmp_path / 'remote.git'
    linked = tmp_path / 'linked'
    subprocess.run(['git', 'init', '-qb', 'main', str(canonical)], check=True)
    subprocess.run(['git', 'init', '--bare', '-q', str(remote)], check=True)
    for name, value in [('user.name', 'Fixture'), ('user.email', 'fixture@example.com'), ('core.hooksPath', '/dev/null')]:
        git(canonical, 'config', name, value)
    (canonical / 'tracked.txt').write_text('before\n')
    git(canonical, 'add', 'tracked.txt')
    git(canonical, 'commit', '-qm', 'seed')
    git(canonical, 'remote', 'add', 'origin', str(remote))
    git(canonical, 'push', '-q', 'origin', 'main')
    old = git(canonical, 'rev-parse', 'HEAD')
    git(canonical, 'worktree', 'add', '-qb', 'feature', str(linked))
    (linked / 'tracked.txt').write_text('after\n')
    git(linked, 'commit', '-qam', 'change')
    target = git(linked, 'rev-parse', 'HEAD')
    coord = seed_authority(monkeypatch, tmp_path, linked)
    payload = {'session_id': NATIVE, 'tool_name': 'exec_command', 'tool_use_id': 'push-1',
               'cwd': str(linked), 'tool_input': {'cmd': 'git push origin feature:main', 'workdir': str(linked)}}
    before_row = asdict(coord.rows(landing.BOARD.read_text(), strict=True)[0])
    return SimpleNamespace(canonical=canonical, linked=linked, remote=remote, old=old,
                           target=target, coord=coord, payload=payload, row=before_row)


def capture_publish(fixture):
    receipt = landing.capture_before(fixture.payload, fixture.linked)
    git(fixture.linked, 'push', '-q', 'origin', 'feature:main')
    matches = [path for path in landing.actor_directory(receipt['identity']).glob('*.json')
               if landing.read_receipt(path).get('transaction') == receipt['transaction']]
    assert len(matches) == 1, 'published transaction must have exactly one receipt'
    return receipt, matches[0]

def test_real_push_lands_and_restores_only_own_authority(setup):
    fixture = setup
    receipt, path = capture_publish(fixture)
    result = landing.process_after(fixture.payload)
    assert result[0]['remote_published'] == 'verified'
    assert result[0]['canonical'] == 'advanced'
    assert result[0]['claim_cleanup'] == 'complete'
    assert git(fixture.canonical, 'rev-parse', 'HEAD') == fixture.target
    assert asdict(fixture.coord.rows(landing.BOARD.read_text(), strict=True)[0]) == fixture.row
    assert 'claim' not in landing.read_receipt(path)
    assert landing.process_after(fixture.payload) == []


@pytest.mark.parametrize('damage', ['dirty', 'staged', 'untracked', 'diverged', 'ahead', 'branch', 'operation'])
def test_unsafe_canonical_retained_after_successful_remote_push(setup, damage):
    fixture = setup
    receipt, path = capture_publish(fixture)
    if damage in {'dirty', 'staged', 'diverged', 'ahead'}:
        (fixture.canonical / 'tracked.txt').write_text('retained local work\n')
        if damage != 'dirty':
            git(fixture.canonical, 'add', 'tracked.txt')
        if damage in {'diverged', 'ahead'}:
            if damage == 'ahead':
                git(fixture.canonical, 'reset', '--hard', fixture.target)
                (fixture.canonical / 'tracked.txt').write_text('retained ahead work\n')
                git(fixture.canonical, 'add', 'tracked.txt')
            git(fixture.canonical, 'commit', '-qm', 'retained')
    elif damage == 'untracked':
        (fixture.canonical / 'retained.txt').write_text('retain\n')
    elif damage == 'branch':
        git(fixture.canonical, 'switch', '-qc', 'retained')
    else:
        (fixture.canonical / '.git/MERGE_HEAD').write_text(fixture.target + '\n')
    head = git(fixture.canonical, 'rev-parse', 'HEAD')
    status = git(fixture.canonical, 'status', '--porcelain=v1')
    landing.land(receipt, path)
    assert receipt['remote_published'] == 'verified'
    assert receipt['canonical'] == 'blocked'
    assert git(fixture.canonical, 'rev-parse', 'HEAD') == head
    assert git(fixture.canonical, 'status', '--porcelain=v1') == status
    assert asdict(fixture.coord.rows(landing.BOARD.read_text(), strict=True)[0]) == fixture.row


@pytest.mark.parametrize('foreign_area', ['same-checkout', 'incoming-path'])
def test_foreign_authority_blocks_even_disjoint_canonical_paths(setup, foreign_area):
    fixture = setup
    receipt, path = capture_publish(fixture)
    own = fixture.coord.rows(landing.BOARD.read_text(), strict=True)[0]
    identity = fixture.coord.new_identity([own.identity])
    other = replace(own, session_uuid=identity.session_uuid, compact_id=identity.compact_id,
                    speakable_id=identity.speakable_id, legacy_id='', project='foreign', client_ref='codex:foreign',
                    workspaces=[f'{fixture.canonical} @ main'] if foreign_area == 'same-checkout' else [],
                    claims=[str(fixture.canonical / ('different.txt' if foreign_area == 'same-checkout' else 'tracked.txt'))])
    fixture.coord.locked_update(landing.BOARD, lambda text: fixture.coord.replace_table(text, [own, other]))
    before = landing.BOARD.read_bytes()
    landing.land(receipt, path)
    assert receipt['remote_published'] == 'verified'
    assert receipt['canonical'] == 'blocked'
    assert git(fixture.canonical, 'rev-parse', 'HEAD') == fixture.old
    assert landing.BOARD.read_bytes() == before


@pytest.mark.parametrize('tool', ['write_stdin', 'TaskOutput'])
def test_yielded_push_is_retried_by_completion_without_shell_snapshot(setup, tool):
    fixture = setup
    receipt = landing.capture_before(fixture.payload, fixture.linked)
    assert landing.process_after(fixture.payload)[0]['remote_published'] == 'unverified'
    assert git(fixture.canonical, 'rev-parse', 'HEAD') == fixture.old
    git(fixture.linked, 'push', '-q', 'origin', 'feature:main')
    completion = dict(fixture.payload, tool_name=tool, tool_use_id='completion', tool_input={})
    result = landing.process_after(completion)
    assert result[0]['canonical'] == 'advanced'
    assert git(fixture.canonical, 'rev-parse', 'HEAD') == fixture.target


@pytest.mark.parametrize('command,scope', [
    ('git push origin feature:main other:other', 'unsupported'),
    ('git push origin --all', 'unsupported'),
    ('git push origin +feature:main', 'unsupported'),
    ('git push origin feature:feature', 'not_applicable'),
    ('git push origin --dry-run feature:main', 'unsupported'),
    ('git push origin "$BRANCH":main', 'unsupported'),
    ("bash -c 'git push origin feature:main'", 'unsupported'),
    ('python3 release.py', 'not_observed'),
    ('git commit -m push', 'not_observed'),
    ('printf \"%s\" \"git push origin feature:main\"', 'not_observed'),
    ('git commit -am change && git push origin feature:main', 'unsupported'),
    ('git -c remote.origin.url=somewhere push origin feature:main', 'unsupported'),
    ('GIT_DIR=/tmp/other git push origin feature:main', 'unsupported'),
])
def test_command_boundaries_are_explicit_and_never_infer_publication(setup, command, scope):
    fixture = setup
    fixture.payload['tool_input']['cmd'] = command
    result = landing.inspect_push(fixture.payload, fixture.linked)
    assert result['scope'] == scope
    assert 'source_oid' not in result


@pytest.mark.parametrize('source', ['feature:refs/heads/main', 'HEAD:main'])
def test_supported_source_forms_bind_exact_commit(setup, source):
    fixture = setup
    fixture.payload['tool_input']['cmd'] = f'git -C {fixture.linked} push -u origin {source}'
    result = landing.inspect_push(fixture.payload, fixture.canonical)
    assert result['source_oid'] == fixture.target
    assert result['scope'] == 'supported'


def test_sha_source_forms_bind_exact_commit(setup):
    fixture = setup
    for source in (fixture.target, fixture.target[:12]):
        fixture.payload['tool_input']['cmd'] = f'git -C {fixture.linked} push origin {source}:main'
        result = landing.inspect_push(fixture.payload, fixture.canonical)
        assert result['scope'] == 'supported'
        assert result['source_oid'] == fixture.target


def test_hex_branch_name_falls_back_when_no_such_commit(setup):
    fixture = setup
    git(fixture.linked, 'branch', '1a2b3c', fixture.target)
    fixture.payload['tool_input']['cmd'] = f'git -C {fixture.linked} push origin 1a2b3c:main'
    result = landing.inspect_push(fixture.payload, fixture.canonical)
    assert result['scope'] == 'supported'
    assert result['source'] == 'refs/heads/1a2b3c'
    assert result['source_oid'] == fixture.target


def test_unresolvable_source_refused_with_accurate_diagnostic(setup):
    fixture = setup
    missing = '0' * 40
    fixture.payload['tool_input']['cmd'] = f'git -C {fixture.linked} push origin {missing}:main'
    with pytest.raises(RuntimeError, match=f'push source did not resolve to a commit: {missing}'):
        landing.inspect_push(fixture.payload, fixture.canonical)


def test_native_identity_spoof_cannot_claim_or_recover(setup):
    fixture = setup
    receipt, path = capture_publish(fixture)
    receipt['identity']['session_id'] = 'foreign-native-session'
    before = landing.BOARD.read_bytes()
    landing.land(receipt, path)
    assert receipt['canonical'] == 'blocked'
    assert 'authenticated own' in receipt['reason']
    assert landing.BOARD.read_bytes() == before
    assert git(fixture.canonical, 'rev-parse', 'HEAD') == fixture.old


def test_remote_advancement_after_claim_refuses_and_restores(setup, monkeypatch):
    fixture = setup
    receipt, path = capture_publish(fixture)
    actual = landing.admit_claim
    def advance(*args):
        actual(*args)
        (fixture.linked / 'tracked.txt').write_text('later publication\n')
        git(fixture.linked, 'commit', '-qam', 'later')
        git(fixture.linked, 'push', '-q', 'origin', 'feature:main')
    monkeypatch.setattr(landing, 'admit_claim', advance)
    landing.land(receipt, path)
    assert receipt['canonical'] == 'blocked'
    assert 'remote main changed' in receipt['reason']
    assert receipt['claim_cleanup'] == 'complete'
    assert git(fixture.canonical, 'rev-parse', 'HEAD') == fixture.old
    assert asdict(fixture.coord.rows(landing.BOARD.read_text(), strict=True)[0]) == fixture.row


@pytest.mark.parametrize('crash_phase', ['before_admission', 'after_admission', 'after_merge'])
def test_interrupted_transaction_recovers_claim_then_retries(setup, crash_phase):
    fixture = setup
    receipt, path = capture_publish(fixture)
    landing.admit_claim(receipt, path, fixture.canonical, ['tracked.txt'])
    if crash_phase == 'before_admission':
        own = fixture.coord.Session(**fixture.row)
        fixture.coord.locked_update(landing.BOARD, lambda text: fixture.coord.replace_table(text, [own]))
    if crash_phase == 'after_merge':
        git(fixture.canonical, 'merge', '--ff-only', '--no-edit', fixture.target)
    result = landing.process_after(fixture.payload)[0]
    assert result['canonical'] == ('current' if crash_phase == 'after_merge' else 'advanced')
    assert result['claim_cleanup'] == 'complete'
    assert asdict(fixture.coord.rows(landing.BOARD.read_text(), strict=True)[0]) == fixture.row


def test_changed_own_authority_is_retained_for_recovery(setup):
    fixture = setup
    receipt, path = capture_publish(fixture)
    landing.admit_claim(receipt, path, fixture.canonical, ['tracked.txt'])
    def change(text):
        rows = fixture.coord.rows(text, strict=True)
        rows[0].claims.append(str(fixture.linked / 'independent.txt'))
        return fixture.coord.replace_table(text, rows)
    fixture.coord.locked_update(landing.BOARD, change)
    before = landing.BOARD.read_bytes()
    landing.land(receipt, path)
    assert receipt['claim_cleanup'] == 'pending_recovery'
    assert receipt['canonical'] == 'blocked'
    assert landing.BOARD.read_bytes() == before
    assert git(fixture.canonical, 'rev-parse', 'HEAD') == fixture.old


def test_ignored_collision_preserves_retained_bytes(setup):
    fixture = setup
    (fixture.canonical / '.git/info/exclude').write_text('ignored.txt\n')
    (fixture.canonical / 'ignored.txt').write_text('retained secret\n')
    (fixture.linked / 'ignored.txt').write_text('incoming\n')
    git(fixture.linked, 'add', '-f', 'ignored.txt')
    git(fixture.linked, 'commit', '-qm', 'incoming')
    receipt, path = capture_publish(fixture)
    landing.land(receipt, path)
    assert receipt['canonical'] == 'blocked'
    assert (fixture.canonical / 'ignored.txt').read_text() == 'retained secret\n'
    assert git(fixture.canonical, 'rev-parse', 'HEAD') == fixture.old
    assert receipt['claim_cleanup'] == 'complete'


def test_unrelated_ignored_files_do_not_prevent_landing(setup):
    fixture = setup
    (fixture.canonical / '.git/info/exclude').write_text('retained.txt\n')
    (fixture.canonical / 'retained.txt').write_text('retained\n')
    receipt, path = capture_publish(fixture)
    landing.land(receipt, path)
    assert receipt['canonical'] == 'advanced'
    assert (fixture.canonical / 'retained.txt').read_text() == 'retained\n'


def test_receipt_symlink_is_refused_without_target_mutation(setup, tmp_path):
    fixture = setup
    receipt, path = capture_publish(fixture)
    retained = tmp_path / 'retained.json'
    path.rename(retained)
    before = retained.read_bytes()
    path.symlink_to(retained)
    with pytest.raises(RuntimeError, match='symlink'):
        landing.process_after(fixture.payload)
    assert retained.read_bytes() == before
    assert git(fixture.canonical, 'rev-parse', 'HEAD') == fixture.old


def test_unreachable_remote_is_not_reported_as_published(setup):
    fixture = setup
    receipt = landing.capture_before(fixture.payload, fixture.linked)
    path = next(landing.actor_directory(receipt['identity']).glob('*.json'))
    fixture.remote.rename(fixture.remote.with_name('unavailable.git'))
    landing.land(receipt, path)
    assert receipt['remote_published'] == 'unverified'
    assert receipt['canonical'] == 'blocked'
    assert receipt['claim_cleanup'] == 'not_needed'
    assert git(fixture.canonical, 'rev-parse', 'HEAD') == fixture.old


def test_changed_destination_is_not_observed_or_landed(setup):
    fixture = setup
    receipt, path = capture_publish(fixture)
    git(fixture.linked, 'remote', 'set-url', '--push', 'origin', str(fixture.remote.with_name('different.git')))
    landing.land(receipt, path)
    assert receipt['remote_published'] == 'unverified'
    assert receipt['canonical'] == 'blocked'
    assert 'destination changed' in receipt['reason']
    assert git(fixture.canonical, 'rev-parse', 'HEAD') == fixture.old


def test_terminal_own_row_is_not_resurrected_during_cleanup(setup):
    fixture = setup
    receipt, path = capture_publish(fixture)
    landing.admit_claim(receipt, path, fixture.canonical, ['tracked.txt'])
    def release(text):
        rows = fixture.coord.rows(text, strict=True)
        rows[0].status = 'released'
        return fixture.coord.replace_table(text, rows)
    fixture.coord.locked_update(landing.BOARD, release)
    before = landing.BOARD.read_bytes()
    landing.restore_claim(receipt, path)
    assert receipt['claim_cleanup'] == 'complete'
    assert landing.BOARD.read_bytes() == before


def test_actor_completion_cannot_consume_foreign_receipts(setup):
    fixture = setup
    receipt, path = capture_publish(fixture)
    before = path.read_bytes()
    foreign = dict(fixture.payload, session_id='different-native-session', tool_name='write_stdin')
    assert landing.process_after(foreign) == []
    assert path.read_bytes() == before
    assert git(fixture.canonical, 'rev-parse', 'HEAD') == fixture.old


def test_context_landing_does_not_promote_contributor(setup):
    fixture = setup
    project = fixture.linked / 'projects/example'
    project.mkdir(parents=True)
    (project / 'CONTEXT.md').write_text('new context\n')
    git(fixture.linked, 'add', 'projects')
    git(fixture.linked, 'commit', '-qm', 'context')
    def downgrade(text):
        rows = fixture.coord.rows(text, strict=True)
        rows[0].context_role = 'contributor'
        return fixture.coord.replace_table(text, rows)
    fixture.coord.locked_update(landing.BOARD, downgrade)
    before = landing.BOARD.read_bytes()
    receipt, path = capture_publish(fixture)
    landing.land(receipt, path)
    assert receipt['canonical'] == 'blocked'
    assert 'existing seat to be an owner' in receipt['reason']
    assert landing.BOARD.read_bytes() == before
    assert not (fixture.canonical / 'projects').exists()


def test_renames_claim_both_paths_before_mutation(setup, monkeypatch):
    fixture = setup
    git(fixture.linked, 'mv', 'tracked.txt', 'renamed.txt')
    git(fixture.linked, 'commit', '-qm', 'rename')
    receipt, path = capture_publish(fixture)
    actual = landing.verify_claim
    claimed = []
    def inspect(receipt):
        claimed.extend(fixture.coord.rows(landing.BOARD.read_text(), strict=True)[0].claims)
        actual(receipt)
    monkeypatch.setattr(landing, 'verify_claim', inspect)
    landing.land(receipt, path)
    assert receipt['canonical'] == 'advanced'
    assert str(fixture.canonical / 'tracked.txt') in claimed
    assert str(fixture.canonical / 'renamed.txt') in claimed


@pytest.mark.parametrize("old_receipt_first", [True, False])
def test_retry_rotation_does_not_starve_later_pending_push(setup, monkeypatch, old_receipt_first):
    fixture = setup
    # This source is never published; a later independent push must still retry.
    first = dict(fixture.payload, tool_use_id='first')
    first_receipt = landing.capture_before(first, fixture.linked)
    directory = landing.actor_directory(first_receipt['identity'])
    first_path = next(directory.glob('*.json'))
    actual_glob = Path.glob
    def ordered_glob(root, pattern):
        values = list(actual_glob(root, pattern))
        if root == directory and pattern == '*.json':
            values.sort(key=lambda path: (path != first_path) if old_receipt_first else (path == first_path))
        return iter(values)
    monkeypatch.setattr(Path, 'glob', ordered_glob)
    (fixture.linked / 'tracked.txt').write_text('second\n')
    git(fixture.linked, 'commit', '-qam', 'second')
    fixture.payload['tool_use_id'] = 'second'
    receipt, path = capture_publish(fixture)
    completion = dict(fixture.payload, tool_name='write_stdin', tool_use_id='poll', tool_input={})
    landing.process_after(completion)
    landing.process_after(completion)
    assert landing.read_receipt(path)['transaction'] == receipt['transaction']
    assert landing.read_receipt(path)['canonical'] in {'advanced', 'current'}
    assert landing.read_receipt(first_path)['canonical'] == 'pending'
    assert git(fixture.canonical, 'rev-parse', 'HEAD') == receipt['source_oid']


def test_submodule_target_refuses_without_touching_canonical(setup):
    fixture = setup
    git(fixture.linked, 'update-index', '--add', '--cacheinfo', f'160000,{fixture.old},nested')
    git(fixture.linked, 'commit', '-qm', 'gitlink')
    receipt, path = capture_publish(fixture)
    landing.land(receipt, path)
    assert receipt['canonical'] == 'blocked'
    assert 'submodules' in receipt['reason']
    assert git(fixture.canonical, 'rev-parse', 'HEAD') == fixture.old


def test_two_helpers_do_not_mutate_canonical_concurrently(setup):
    fixture = setup
    receipt, path = capture_publish(fixture)
    with landing.processing_lock() as acquired:
        assert acquired
        result = landing.process_after(fixture.payload)
    assert result[0]['canonical'] == 'pending'
    assert git(fixture.canonical, 'rev-parse', 'HEAD') == fixture.old
    assert landing.process_after(fixture.payload)[0]['canonical'] == 'advanced'

def test_claude_native_seat_lands_with_same_authority_contract(setup, monkeypatch):
    fixture = setup
    peer = landing.dependencies()[1]
    own = fixture.coord.rows(landing.BOARD.read_text(), strict=True)[0]
    host = 'local_12345678-1234-1234-1234-123456789abc'
    monkeypatch.delenv('SYNTHESIS_CLIENT_SESSION_REF', raising=False)
    monkeypatch.setenv('CLAUDE_CODE_SESSION_ID', NATIVE)
    monkeypatch.setenv('CLAUDE_CODE_HOST_SESSION_ID', host)
    own.client_ref = 'ccd:' + host
    fixture.coord.locked_update(landing.BOARD, lambda text: fixture.coord.replace_table(text, [own]))
    peer.write_seat(landing.BOARD, session_uuid=own.session_uuid, compact_id=own.compact_id,
                    machine=own.machine, identity=peer.detect_self())
    fixture.payload['tool_name'] = 'Bash'
    receipt, path = capture_publish(fixture)
    assert receipt['identity']['client'] == 'claude-code'
    landing.land(receipt, path)
    assert receipt['canonical'] == 'advanced'
    assert receipt['claim_cleanup'] == 'complete'
    assert fixture.coord.rows(landing.BOARD.read_text(), strict=True)[0].client_ref == 'ccd:' + host


def test_wrong_native_binding_cannot_borrow_a_board_seat(setup):
    fixture = setup
    receipt, path = capture_publish(fixture)
    def corrupt(text):
        rows = fixture.coord.rows(text, strict=True)
        rows[0].client_ref = 'codex:foreign'
        return fixture.coord.replace_table(text, rows)
    fixture.coord.locked_update(landing.BOARD, corrupt)
    before = landing.BOARD.read_bytes()
    landing.land(receipt, path)
    assert receipt['canonical'] == 'blocked'
    assert 'bound to the board' in receipt['reason']
    assert landing.BOARD.read_bytes() == before
    assert git(fixture.canonical, 'rev-parse', 'HEAD') == fixture.old


@pytest.mark.parametrize('surface', ['board', 'seat'])
def test_redirected_coordination_authority_fails_closed(setup, tmp_path, surface):
    fixture = setup
    receipt, path = capture_publish(fixture)
    if surface == 'board':
        authority = landing.BOARD
    else:
        peer = landing.dependencies()[1]
        authority = peer.seat_path(landing.BOARD, fixture.row['session_uuid'])
    retained = tmp_path / 'retained-authority'
    authority.rename(retained)
    before = retained.read_bytes()
    authority.symlink_to(retained)
    landing.land(receipt, path)
    assert receipt['canonical'] == 'blocked'
    assert 'symlink' in receipt['reason']
    assert retained.read_bytes() == before
    assert git(fixture.canonical, 'rev-parse', 'HEAD') == fixture.old


def test_real_release_clears_interrupted_receipt_without_recreating_authority(setup):
    f=setup
    receipt,path=capture_publish(f)
    landing.admit_claim(receipt,path,f.canonical,["tracked.txt"])
    assert f.coord.command_release(SimpleNamespace(board=landing.BOARD,id=f.row["compact_id"],administrative=False,reason="",active_project_file=None)) == 0
    board=landing.BOARD.read_bytes()
    result=landing.process_after(f.payload)
    print(json.dumps({"result":result,"seat_exists":landing.dependencies()[1].seat_path(landing.BOARD,f.row["session_uuid"]).exists()}))
    assert landing.BOARD.read_bytes() == board
    assert landing.read_receipt(path)["claim_cleanup"] == "complete"
    assert "claim" not in landing.read_receipt(path)


def test_pending_claim_cleanup_precedes_unsupported_receipt_reporting(setup):
    f=setup
    receipt,path=capture_publish(f)
    landing.admit_claim(receipt,path,f.canonical,["tracked.txt"])
    identity=receipt["identity"]
    for n in range(100000):
        tool_id="unsupported-"+str(n)
        key=hashlib.sha256((identity["client"]+"\0"+identity["session_id"]+"\0"+tool_id).encode()).hexdigest()
        if key < path.stem:break
    else:raise AssertionError("no earlier fixture key")
    payload=dict(f.payload,tool_use_id=tool_id,tool_input={"cmd":"git push origin --all"})
    unsupported=landing.capture_before(payload,f.linked)
    assert unsupported["scope"] == "unsupported"
    result=landing.process_after(dict(f.payload,tool_name="write_stdin",tool_use_id="poll",tool_input={}))
    print(json.dumps({"result":result,"still_holds_temporary_claim":bool(landing.read_receipt(path).get("claim"))}))
    assert landing.read_receipt(path)["claim_cleanup"] == "complete"


def test_post_merge_hook_cannot_overwrite_foreign_ignored_retained_file(setup,tmp_path):
    f=setup
    retained=f.canonical/"retained.txt"
    retained.write_text("retained foreign work\n")
    (f.canonical/".git/info/exclude").write_text("retained.txt\n")
    own=f.coord.rows(landing.BOARD.read_text(),strict=True)[0]
    identity=f.coord.new_identity([own.identity])
    other=replace(own,session_uuid=identity.session_uuid,compact_id=identity.compact_id,speakable_id=identity.speakable_id,legacy_id="",project="foreign",client_ref="codex:foreign",workspaces=[],claims=[str(retained)])
    f.coord.locked_update(landing.BOARD,lambda text:f.coord.replace_table(text,[own,other]))
    hooks=tmp_path/"hooks";hooks.mkdir()
    hook=hooks/"post-merge"
    hook.write_text("#!/bin/sh\nprintf 'overwritten by repository hook\\n' > retained.txt\n")
    hook.chmod(0o755)
    git(f.canonical,"config","core.hooksPath",str(hooks))
    receipt,path=capture_publish(f)
    before=landing.BOARD.read_bytes()
    landing.land(receipt,path)
    print(json.dumps({"receipt":receipt,"retained_content":retained.read_text(),"board_unchanged":landing.BOARD.read_bytes()==before}))
    assert retained.read_text() == "retained foreign work\n"


@pytest.mark.parametrize('effect', ['core.fsmonitor', 'filter.fixture.clean', 'filter.fixture.smudge', 'filter.fixture.process', 'reference-transaction', 'post-index-change', 'pre-auto-gc'])
def test_external_checkout_effects_cannot_touch_retained_work(setup, tmp_path, effect):
    fixture = setup
    receipt, path = capture_publish(fixture)
    retained = fixture.canonical / 'retained.txt'
    retained.write_text('retained foreign work\n')
    (fixture.canonical / '.git/info/exclude').write_text('retained.txt\n')
    callback = tmp_path / 'callback'
    callback.write_text('#!/bin/sh\nprintf overwritten > ' + shlex.quote(str(retained)) + '\n' +
                        ('exit 1\n' if effect in {'core.fsmonitor', 'filter.fixture.process'} else 'cat\n'))
    callback.chmod(0o755)
    if effect.startswith('filter.'):
        (fixture.canonical / '.git/info/attributes').write_text('tracked.txt filter=fixture\n')
        git(fixture.canonical, 'config', effect, str(callback))
        if effect.endswith('.clean'):
            (fixture.canonical / 'tracked.txt').write_text('local dirty work\n')
    elif effect == 'core.fsmonitor':
        git(fixture.canonical, 'config', effect, str(callback))
    else:
        hooks = tmp_path / 'hooks'
        hooks.mkdir()
        (hooks / effect).symlink_to(callback)
        git(fixture.canonical, 'config', 'core.hooksPath', str(hooks))
    before = landing.BOARD.read_bytes()
    landing.land(receipt, path)
    assert retained.read_text() == 'retained foreign work\n'
    assert receipt['canonical'] == 'blocked'
    assert receipt['remote_published'] == 'verified'
    assert landing.BOARD.read_bytes() == before
    assert git(fixture.canonical, 'rev-parse', 'HEAD') == fixture.old


def test_nonexecutable_post_merge_hook_is_not_run_and_does_not_block(setup, tmp_path):
    fixture = setup
    hooks = tmp_path / 'hooks'
    hooks.mkdir()
    (hooks / 'post-merge').write_text('#!/bin/sh\nexit 1\n')
    git(fixture.canonical, 'config', 'core.hooksPath', str(hooks))
    receipt, path = capture_publish(fixture)
    landing.land(receipt, path)
    assert receipt['canonical'] == 'advanced'


def test_disabled_fsmonitor_does_not_block(setup):
    fixture = setup
    git(fixture.canonical, 'config', 'core.fsmonitor', 'false')
    receipt, path = capture_publish(fixture)
    landing.land(receipt, path)
    assert receipt['canonical'] == 'advanced'


def test_released_but_changed_row_is_not_silently_accepted_as_cleanup(setup):
    fixture = setup
    receipt, path = capture_publish(fixture)
    landing.admit_claim(receipt, path, fixture.canonical, ['tracked.txt'])
    assert fixture.coord.command_release(SimpleNamespace(board=landing.BOARD, id=fixture.row['compact_id'],
        administrative=False, reason='', active_project_file=None)) == 0
    def change(text):
        rows = fixture.coord.rows(text, strict=True)
        rows[0].client_ref = 'codex:foreign-session'
        return fixture.coord.replace_table(text, rows)
    fixture.coord.locked_update(landing.BOARD, change)
    before = landing.BOARD.read_bytes()
    landing.land(receipt, path)
    assert receipt['claim_cleanup'] == 'pending_recovery'
    assert landing.BOARD.read_bytes() == before

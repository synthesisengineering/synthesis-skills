#!/usr/bin/env python3
"""Observe explicit main pushes and safely refresh the canonical checkout.

This is a bounded hook interface: one literal ``git push REMOTE SOURCE:main``
(or SOURCE=main), optionally preceded by a literal cd or using git -C. Dynamic,
multi-ref and nested/script-internal pushes are never guessed or called landed.
Receipts distinguish observed remote state, canonical state, and claim cleanup.
Native Git plus the advisory board protect cooperating actors; neither this
helper's flock nor a claim serializes arbitrary concurrent human Git commands.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path

import fcntl

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from publication_command import parse_shell, unwrap_argv  # noqa: E402

SYNTHESIS_HOME = Path(os.environ.get('SYNTHESIS_HOME', str(Path.home() / '.synthesis')))
STATE_DIR = SYNTHESIS_HOME / 'repo-guard' / 'canonical-landings'
BOARD = SYNTHESIS_HOME / 'coordination' / 'active-sessions.md'
COMPLETION_TOOLS = {'write_stdin', 'TaskOutput'}
SAFE_PUSH_FLAGS = {'-q', '--quiet', '-v', '--verbose', '--porcelain', '-u', '--set-upstream', '--progress', '--no-progress', '--atomic'}
OID = re.compile(r'^[0-9a-f]{40}(?:[0-9a-f]{24})?$')
OID_LIKE = re.compile(r'[0-9a-fA-F]{4,64}\Z')


def _looks_like_oid(source: str) -> bool:
    """Hex long enough to be an abbreviated commit; rev-parse validates."""
    return OID_LIKE.fullmatch(source) is not None
_DEPS = None


# Promoted from the private control plane (private agent-control, PRO-2, 2026-09-21); behavior identical, loader is the
# same-skill convention instead of the private verified runtime.
def dependencies():
    global _DEPS
    if _DEPS is None:
        import coordination as coord
        import peer_addressing as peer
        _DEPS = coord, peer
    return _DEPS


def git(repo: Path, *args: str, check: bool = True, input_text: str | None = None):
    env = dict(os.environ, GIT_TERMINAL_PROMPT='0', GIT_OPTIONAL_LOCKS='0')
    result = subprocess.run(['git', '-C', str(repo), *args], capture_output=True,
                            text=True, timeout=10, env=env, input=input_text)
    if check and result.returncode:
        raise RuntimeError(result.stderr.strip() or f'Git {args[0]} failed')
    return result


def out(repo: Path, *args: str) -> str:
    return git(repo, *args).stdout.strip()


def checkout_effect_config(repo: Path) -> dict[str, str]:
    result = git(repo, 'config', '--null', '--get-regexp',
                 r'^(core\.fsmonitor|filter\..*\.(clean|smudge|process)|diff\.external|diff\..*\.(command|textconv)|gc\.recentobjectshook)$',
                 check=False)
    if result.returncode not in (0, 1):
        raise RuntimeError('cannot inspect external Git checkout effects')
    values = {}
    for record in result.stdout.split('\0'):
        if record:
            key, separator, value = record.partition('\n')
            if not separator:
                raise RuntimeError('invalid Git checkout-effect configuration')
            values[key] = value
    return values


def current_filter_drivers(repo: Path) -> set[str]:
    # check-attr and ls-files read metadata; neither executes conversion filters.
    names = git(repo, 'ls-files', '-z', '--cached').stdout
    if not names:
        return set()
    result = set()
    for cached in ([], ['--cached']):
        fields = git(repo, 'check-attr', '-z', *cached, '--stdin', 'filter', input_text=names).stdout.split('\0')
        if fields[-1:] == ['']:
            fields.pop()
        if len(fields) % 3:
            raise RuntimeError('cannot prove the active status filter drivers')
        result.update(fields[index + 2] for index in range(0, len(fields), 3))
    return result


def refuse_external_effects(repo: Path, *, status_only: bool = False) -> None:
    """Refuse unbounded callbacks rather than disable any installed protection.

    Canonical landing conservatively refuses configured conversion/diff/GC
    commands, including drivers an incoming attributes file could activate.
    Existing shell snapshots inspect only status's active clean/process filters
    and fsmonitor; an unrelated globally configured driver need not block them.
    """
    configuration = checkout_effect_config(repo)
    monitor = configuration.get('core.fsmonitor')
    if monitor is not None and monitor.lower() not in {'false', 'no', 'off', '0'}:
        raise RuntimeError('external checkout effects: core.fsmonitor prevents bounded status inspection')
    active_drivers = None
    for key, value in configuration.items():
        if key == 'core.fsmonitor' or not value.strip():
            continue
        if status_only:
            if not key.startswith('filter.') or not key.endswith(('.clean', '.process')):
                continue
            if active_drivers is None:
                active_drivers = current_filter_drivers(repo)
            driver = key[len('filter.'):].rsplit('.', 1)[0]
            if driver not in active_drivers:
                continue
        raise RuntimeError('external checkout effects: configured ' + key + ' has no bounded write scope')
    if not status_only:
        hooks = Path(out(repo, 'rev-parse', '--path-format=absolute', '--git-path', 'hooks'))
        for hook in ('post-merge', 'reference-transaction', 'post-index-change', 'pre-auto-gc'):
            # Ask Git to resolve the directory before appending the name. A
            # configured non-directory (commonly /dev/null) disables hooks;
            # Git's absolute path resolver otherwise rejects that child path.
            location = hooks / hook
            if os.access(location, os.X_OK):
                raise RuntimeError('external checkout effects: executable ' + hook + ' hook has no bounded write scope')


def safe_path(path: Path) -> None:
    absolute = Path(os.path.abspath(path))
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        if current.is_symlink():
            raise RuntimeError(f'landing state crosses a symlink: {current}')


def write_receipt(path: Path, data: dict) -> None:
    safe_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix='.landing-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w') as handle:
            json.dump(data, handle, indent=2, sort_keys=True)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def read_receipt(path: Path) -> dict:
    safe_path(path)
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor) as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise RuntimeError('landing receipt must be a regular file')
        data = json.load(handle)
    if not isinstance(data, dict) or type(data.get('schema')) is not int or data['schema'] != 1:
        raise RuntimeError('invalid landing receipt schema')
    return data


@contextmanager
def processing_lock():
    safe_path(STATE_DIR / '.processing.lock')
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(STATE_DIR / '.processing.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
        else:
            yield True
    finally:
        os.close(descriptor)


def native_identity(payload: dict) -> dict:
    if not isinstance(payload.get('session_id'), str) or not payload['session_id']:
        raise RuntimeError('landing requires the native hook session identity')
    _coord, peer = dependencies()
    identity = peer.identity_from_hook(payload)
    if not identity.client or identity.harness_session_id != payload['session_id']:
        raise RuntimeError('unresolved landing native identity')
    return {'client': identity.client, 'session_id': identity.harness_session_id}


def is_git_push(argv: list[str]) -> bool:
    if not argv or Path(argv[0]).name != 'git':
        return False
    index = 1
    options_with_values = {'-C', '-c', '--git-dir', '--work-tree', '--namespace', '--config-env', '--super-prefix'}
    while index < len(argv) and argv[index].startswith('-'):
        index += 2 if argv[index] in options_with_values else 1
    return index < len(argv) and argv[index] == 'push'


def inspect_push(payload: dict, workdir: Path) -> dict:
    """Return a supported immutable target, or an explicit observation boundary."""
    tool_input = payload.get('tool_input') or {}
    command = str(tool_input.get('command') or tool_input.get('cmd') or '')
    syntax = parse_shell(command)
    commands = [(index, unwrap_argv(words), words) for index, words in enumerate(syntax.commands)]
    candidates = [(i, a, w) for i, a, w in commands if is_git_push(a)]
    nested_push = any(is_git_push(unwrap_argv(words))
                      for _owner, script in syntax.nested_commands for words in parse_shell(script).commands)
    if not candidates:
        return {'scope': 'unsupported' if nested_push else 'not_observed',
                'reason': 'nested/script-internal pushes require an explicit literal push' if nested_push else 'no literal Git push observed; script internals are outside this hook boundary'}
    result = {'scope': 'unsupported'}
    if len(candidates) != 1 or syntax.grouped or syntax.nested_commands or syntax.dynamic_indices:
        return dict(result, reason='dynamic, grouped, nested or multiple pushes are unsupported')
    index, argv, words = candidates[0]
    prefix = words[:len(words) - len(argv)]
    if any(value not in {'command', 'builtin', '--'} for value in prefix):
        return dict(result, reason='push environment or wrapper overrides are unsupported')
    if any(a and a[0] != 'cd' for i, a, _w in commands if i < index):
        return dict(result, reason='push source must be fixed before the tool; preceding operations are unsupported')
    if any(os.environ.get(key) for key in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_COMMON_DIR', 'GIT_CONFIG_COUNT', 'GIT_CONFIG_PARAMETERS', 'GIT_NAMESPACE', 'GIT_INDEX_FILE', 'GIT_OBJECT_DIRECTORY', 'GIT_ALTERNATE_OBJECT_DIRECTORIES')):
        return dict(result, reason='alternate inherited Git state is unsupported')
    repo = workdir
    args = argv[1:]
    while args[:1] == ['-C'] and len(args) >= 2:
        candidate = Path(os.path.expanduser(args[1]))
        repo = candidate if candidate.is_absolute() else repo / candidate
        args = args[2:]
    if args[:1] != ['push']:
        return dict(result, reason='Git global options at a push boundary are unsupported')
    args = args[1:]
    if any(arg.startswith('-') and arg not in SAFE_PUSH_FLAGS for arg in args):
        return dict(result, reason='force, dry-run, deletion, mirror or unsupported push flags are not landing targets')
    positional = [arg for arg in args if not arg.startswith('-')]
    if len(positional) != 2:
        return dict(result, reason='landing requires one explicit remote and one source ref')
    remote, refspec = positional
    source, separator, destination = refspec.partition(':')
    if not separator:
        destination = source
    if destination not in {'main', 'refs/heads/main'}:
        return {'scope': 'not_applicable', 'reason': 'push does not name refs/heads/main'}
    if not source or source.startswith(('-', '+')) or any(v in source for v in '*?$`[]{}~^:'):
        return dict(result, reason='landing requires one literal local branch, HEAD, or commit source')
    candidates = [source]
    if source != 'HEAD' and not source.startswith('refs/heads/'):
        if _looks_like_oid(source):
            # Ref first, bare object second: mirrors git's own tie-break
            # (refs win ambiguity), keeps branch receipts full-ref, and
            # still binds real OIDs, which have no such branch.
            candidates = [f'refs/heads/{source}', source]
        else:
            candidates = [f'refs/heads/{source}']
    repo = Path(out(repo, 'rev-parse', '--show-toplevel')).resolve()
    common = Path(out(repo, 'rev-parse', '--path-format=absolute', '--git-common-dir')).resolve()
    source_oid = ''
    for candidate in candidates:
        probe = git(repo, 'rev-parse', '--verify', '--end-of-options', candidate + '^{commit}', check=False)
        if probe.returncode == 0 and OID.fullmatch(probe.stdout.strip()):
            source, source_oid = candidate, probe.stdout.strip()
            break
    if not source_oid:
        raise RuntimeError(f'push source did not resolve to a commit: {positional[1].partition(":")[0]}')
    urls = out(repo, 'remote', 'get-url', '--push', '--all', remote).splitlines()
    if len(urls) != 1:
        return dict(result, reason='landing requires one configured push destination')
    return {'scope': 'supported', 'repo': str(repo), 'common_dir': str(common),
            'remote': remote, 'push_url': urls[0], 'source': source, 'source_oid': source_oid,
            'remote_ref': 'refs/heads/main'}


def actor_directory(identity: dict) -> Path:
    key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    return STATE_DIR / key


def capture_before(payload: dict, workdir: Path) -> dict:
    target = inspect_push(payload, workdir)
    if target['scope'] in {'not_observed', 'not_applicable'}:
        return target
    identity = native_identity(payload)
    tool_id = payload.get('tool_use_id') or payload.get('tool_call_id')
    if not isinstance(tool_id, str) or not tool_id:
        tool_id = json.dumps(payload.get('tool_input'), sort_keys=True)
    key = hashlib.sha256((identity['client'] + '\0' + identity['session_id'] + '\0' + tool_id).encode()).hexdigest()
    path = actor_directory(identity) / f'{key}.json'
    receipt = dict(target, schema=1, identity=identity, tool_id=tool_id, transaction=str(uuid.uuid4()),
                   remote_published='unverified', canonical='pending' if target['scope'] == 'supported' else 'unverified',
                   claim_cleanup='not_needed')
    # A repeated invocation cannot overwrite a transaction that may own a claim.
    if path.exists():
        old = read_receipt(path)
        if old.get('identity') != identity or old.get('claim_cleanup') == 'pending_recovery':
            raise RuntimeError('existing landing receipt needs authenticated cleanup before reuse')
        if old.get('canonical') == 'pending' or old.get('claim'):
            raise RuntimeError('the tool identity already has a pending landing receipt')
    write_receipt(path, receipt)
    return receipt


def update_board(operation) -> None:
    safe_path(BOARD)
    safe_path(BOARD.parent / '.active-sessions.lock')
    dependencies()[0].locked_update(BOARD, operation)


def authenticated_row(coord, peer, content: str, identity: dict, *, expected_uuid: str | None = None, allow_terminal: bool = False):
    sessions = coord.rows(content, strict=True)
    matches = []
    for session in sessions:
        if expected_uuid is not None and session.session_uuid != expected_uuid:
            continue
        if not allow_terminal and not coord.active(session):
            continue
        safe_path(peer.seat_path(BOARD, session.session_uuid))
        seat = peer.read_seat(BOARD, session.session_uuid, strict=True)
        if (seat is not None and seat.client == identity['client']
                and seat.harness_session_id == identity['session_id']):
            bound_refs = ({f'codex:{seat.harness_session_id}'} if seat.client == peer.CLIENT_CODEX else
                          {f'cc:{seat.harness_session_id}', f'ccd:{seat.host_session_id}'})
            # `session` is a board row, whose machine column carries the label
            # the writer emitted (coordination.py: machine_label or machine).
            # Schema-2 seats hold the fleet machine-id in `machine`, so compare
            # against the seat's label first — never the label to the id.
            if (seat.compact_id != session.compact_id
                    or seat.board_machine != session.machine
                    or session.client_ref not in bound_refs):
                raise RuntimeError('native seat is not bound to the board row')
            matches.append(session)
    if len(matches) != 1:
        raise RuntimeError('landing requires exactly one active authenticated own coordination seat')
    return sessions, matches[0]


def same_row(left: dict, right: dict) -> bool:
    return {k: v for k, v in left.items() if k != 'heartbeat'} == {k: v for k, v in right.items() if k != 'heartbeat'}


def restore_claim(receipt: dict, path: Path) -> None:
    claim = receipt.get('claim')
    if not claim:
        return
    coord, peer = dependencies()
    result = {}
    def operation(content):
        # Release deliberately removes the native seat. A fresh terminal row
        # matching the journal proves authority is already gone; acknowledge it
        # without recreating a seat, restoring a row or modifying the board.
        rows = coord.rows(content, strict=True)
        prior = [row for row in rows if row.session_uuid == claim['original']['session_uuid']]
        if len(prior) == 1 and not coord.active(prior[0]):
            terminal = dict(asdict(prior[0]), status=claim['original']['status'])
            if not any(same_row(terminal, claim[version]) for version in ('original', 'augmented')):
                raise RuntimeError('released landing row differs from its journal; retained for reconciliation')
            result['state'] = 'complete'
            return content
        sessions, own = authenticated_row(coord, peer, content, receipt['identity'],
                                          expected_uuid=claim['original']['session_uuid'])
        actual = asdict(own)
        if same_row(actual, claim['original']):
            result['state'] = 'complete'
            return content
        if not same_row(actual, claim['augmented']):
            raise RuntimeError('own claim changed during landing; retained for authenticated recovery')
        restored = coord.Session(**dict(claim['original'], heartbeat=own.heartbeat))
        prospective = [restored if row.session_uuid == own.session_uuid else row for row in sessions]
        problems = coord.validate_sessions(prospective)
        if problems:
            raise RuntimeError('; '.join(problems))
        result['state'] = 'complete'
        return coord.replace_table(content, prospective)
    update_board(operation)
    receipt['claim_cleanup'] = result['state']
    receipt.pop('claim', None)
    write_receipt(path, receipt)


def admit_claim(receipt: dict, path: Path, canonical: Path, changed: list[str]) -> None:
    coord, peer = dependencies()
    found = {}
    def snapshot(content):
        _rows, own = authenticated_row(coord, peer, content, receipt['identity'])
        found['original'] = asdict(own)
        return content
    update_board(snapshot)
    original = found['original']
    augmented = dict(original, claims=list(original['claims']), workspaces=list(original['workspaces']))
    if any(character in str(canonical) for character in ('\n', '\r', '|', ',')) or ' @ ' in str(canonical):
        raise RuntimeError('canonical checkout path cannot be represented safely on the coordination board')
    workspace = f'{canonical} @ main'
    if workspace not in augmented['workspaces']:
        augmented['workspaces'].append(workspace)
    for relative in changed:
        area = str(canonical / relative)
        if any(character in area for character in ('\n', '\r', '|', ',')):
            raise RuntimeError('incoming path cannot be represented safely on the coordination board')
        if area not in augmented['claims']:
            augmented['claims'].append(area)
    if any(coord.claims_context(area) for area in augmented['claims']) and augmented['context_role'] != 'owner':
        raise RuntimeError('canonical context landing requires the existing seat to be an owner')
    augmented['goal'] = original['goal'] + f" [canonical-landing:{receipt['transaction']}]"
    receipt['claim_owner'] = original['compact_id']
    receipt['claim'] = {'original': original, 'augmented': augmented}
    receipt['claim_cleanup'] = 'pending_recovery'
    write_receipt(path, receipt)  # durable intent precedes any authority mutation
    def admit(content):
        sessions, own = authenticated_row(coord, peer, content, receipt['identity'])
        if not same_row(asdict(own), original):
            raise RuntimeError('own claim changed before landing admission')
        replacement = coord.Session(**dict(augmented, heartbeat=own.heartbeat))
        prospective = [replacement if row.session_uuid == own.session_uuid else row for row in sessions]
        problems = coord.validate_sessions(prospective)
        if problems:
            raise RuntimeError('; '.join(problems))
        return coord.replace_table(content, prospective)
    update_board(admit)


def canonical_target(receipt: dict) -> Path:
    repo = Path(receipt['repo'])
    common = Path(out(repo, 'rev-parse', '--path-format=absolute', '--git-common-dir')).resolve()
    if str(common) != receipt['common_dir'] or common.name != '.git' or not common.is_dir():
        raise RuntimeError('Git common directory no longer identifies a canonical checkout')
    canonical = common.parent
    if (canonical / '.git').is_symlink():
        raise RuntimeError('canonical Git directory is redirected')
    entries = out(repo, 'worktree', 'list', '--porcelain').split('\n\n')
    if not entries or entries[0].splitlines()[0] != f'worktree {canonical}':
        raise RuntimeError('canonical checkout is not the registered primary worktree')
    if out(canonical, 'symbolic-ref', '-q', 'HEAD') != 'refs/heads/main':
        raise RuntimeError('canonical checkout is not on main; no branch switch was attempted')
    if Path(out(canonical, 'rev-parse', '--path-format=absolute', '--git-common-dir')).resolve() != common:
        raise RuntimeError('canonical checkout common-directory identity changed')
    return canonical


def verify_clean(canonical: Path, expected_head: str | None = None) -> str:
    refuse_external_effects(canonical)
    if out(canonical, 'symbolic-ref', '-q', 'HEAD') != 'refs/heads/main':
        raise RuntimeError('canonical branch changed')
    head = out(canonical, 'rev-parse', 'HEAD')
    if expected_head is not None and head != expected_head:
        raise RuntimeError('canonical HEAD changed after inspection')
    if git(canonical, 'status', '--porcelain=v1', '-z', '--untracked-files=all', '--ignore-submodules=none').stdout:
        raise RuntimeError('canonical checkout has tracked, staged, untracked or submodule changes')
    for name in ('MERGE_HEAD', 'CHERRY_PICK_HEAD', 'REVERT_HEAD', 'rebase-merge', 'rebase-apply', 'sequencer', 'BISECT_LOG'):
        if Path(out(canonical, 'rev-parse', '--path-format=absolute', '--git-path', name)).exists():
            raise RuntimeError('canonical checkout has an in-progress Git operation')
    return head


def observe_remote(receipt: dict) -> str:
    repo = Path(receipt['repo'])
    if out(repo, 'remote', 'get-url', '--push', '--all', receipt['remote']).splitlines() != [receipt['push_url']]:
        raise RuntimeError('configured push destination changed')
    result = out(repo, 'ls-remote', '--heads', '--', receipt['push_url'], receipt['remote_ref'])
    rows = [line.split() for line in result.splitlines()]
    if len(rows) != 1 or len(rows[0]) != 2 or rows[0][1] != receipt['remote_ref'] or not OID.fullmatch(rows[0][0]):
        raise RuntimeError('remote main is missing or ambiguous')
    return rows[0][0]


def verify_claim(receipt: dict) -> None:
    coord, peer = dependencies()
    def operation(content):
        sessions, own = authenticated_row(coord, peer, content, receipt['identity'])
        if not same_row(asdict(own), receipt['claim']['augmented']):
            raise RuntimeError('own landing authority changed before the fast-forward')
        problems = coord.validate_sessions(sessions)
        if problems:
            raise RuntimeError('; '.join(problems))
        return content
    update_board(operation)


def refuse_foreign_checkout_use(receipt: dict, canonical: Path) -> None:
    """Refuse landing when a foreign seat already uses the canonical checkout.

    Claim overlap (admit_claim) only covers incoming paths. A foreign seat
    registered on the canonical checkout works on main in the directory the
    fast-forward is about to move, so landing refuses even when its file
    claims are disjoint. Same-machine seats only: a matching path on another
    machine names a different directory. Advisory (downgraded) rows do not
    block, matching claim semantics; unknown-age heartbeats keep blocking.
    """
    coord, peer = dependencies()
    target = os.path.realpath(canonical)
    def operation(content):
        sessions, own = authenticated_row(coord, peer, content, receipt['identity'])
        holders = []
        for session in sessions:
            if session.session_uuid == own.session_uuid:
                continue
            if not coord.active(session) or coord.downgraded(session):
                continue
            if session.machine != own.machine:
                continue
            for workspace in session.workspaces:
                path = workspace.partition(' @ ')[0].strip()
                if not path:
                    continue
                try:
                    if os.path.realpath(path) == target:
                        holders.append(session.compact_id)
                        break
                except OSError:
                    continue
        if holders:
            raise RuntimeError('foreign session already using the canonical checkout: '
                               + ', '.join(sorted(holders)))
        return content
    update_board(operation)


def land(receipt: dict, path: Path) -> None:
    """One bounded attempt; interrupted own authority is reconciled first."""
    receipt['remote_published'] = 'unverified'
    try:
        if receipt.get('claim'):
            restore_claim(receipt, path)
        observed = observe_remote(receipt)
        receipt['observed_remote_oid'] = observed
        if observed != receipt['source_oid']:
            receipt.update(remote_published='unverified', canonical='pending',
                           reason='remote main does not equal the pre-tool source; no canonical write')
            return
        receipt['remote_published'] = 'verified'
        canonical = canonical_target(receipt)
        receipt['canonical_path'] = str(canonical)
        old = verify_clean(canonical)
        receipt['expected_canonical_oid'] = old
        if old == observed:
            receipt.update(canonical='current', reason='canonical main already equals the verified remote commit')
            return
        if git(canonical, 'merge-base', '--is-ancestor', old, observed, check=False).returncode:
            raise RuntimeError('canonical main has diverged or is ahead; fast-forward refused')
        changed = git(canonical, 'diff', '--name-only', '--no-renames', '-z', old, observed).stdout.split('\0')
        changed = [value for value in changed if value]
        # Native --no-overwrite-ignore preserves ignored files that an incoming
        # commit would replace. Gitlinks need recursive semantics not supplied here.
        tree = git(canonical, 'ls-tree', '-r', observed).stdout
        if any(line.startswith('160000 ') for line in tree.splitlines()):
            raise RuntimeError('canonical landing with submodules requires an explicit recursive operation')
        refuse_foreign_checkout_use(receipt, canonical)
        admit_claim(receipt, path, canonical, changed)
        if canonical_target(receipt) != canonical:
            raise RuntimeError('canonical checkout identity changed after claim admission')
        verify_clean(canonical, old)
        if observe_remote(receipt) != observed:
            raise RuntimeError('remote main changed after verification; no canonical write')
        verify_claim(receipt)
        if canonical_target(receipt) != canonical:
            raise RuntimeError('canonical identity changed before the fast-forward')
        verify_clean(canonical, old)
        git(canonical, 'merge', '--ff-only', '--no-overwrite-ignore', '--no-edit', observed)
        verify_clean(canonical, observed)
        receipt.update(canonical='advanced', reason='canonical main fast-forwarded to the verified remote commit')
    except Exception as exc:
        receipt.update(canonical='blocked', reason=str(exc))
    finally:
        receipt['last_attempt_ns'] = time.time_ns()
        if receipt.get('claim'):
            try:
                restore_claim(receipt, path)
            except Exception as exc:
                receipt['claim_cleanup'] = 'pending_recovery'
                receipt['cleanup_reason'] = str(exc)
        write_receipt(path, receipt)


def process_after(payload: dict) -> list[dict]:
    if not STATE_DIR.exists():
        return []
    identity = native_identity(payload)
    with processing_lock() as acquired:
        if not acquired:
            return [{'remote_published': 'unverified', 'canonical': 'pending', 'claim_cleanup': 'unknown',
                     'reason': 'another landing helper is running; durable receipts will retry'}]
        candidates, unreported = [], []
        for path in sorted(actor_directory(identity).glob('*.json')):
            receipt = read_receipt(path)
            if receipt.get('identity') != identity:
                continue
            if receipt.get('claim'):
                candidates.append((path, receipt))
            elif receipt.get('scope') != 'supported':
                if not receipt.get('reported'):
                    unreported.append((path, receipt))
            elif receipt.get('canonical') in {'pending', 'blocked'}:
                candidates.append((path, receipt))
        # Cleanup has priority; one attempt bounds the hook's network/lease work.
        candidates.sort(key=lambda item: (not bool(item[1].get('claim')), item[1].get('tool_id') != (payload.get('tool_use_id') or payload.get('tool_call_id')), item[1].get('last_attempt_ns', 0)))
        reports = []
        if candidates:
            path, receipt = candidates[0]
            previous = (receipt.get('remote_published'), receipt.get('canonical'), receipt.get('claim_cleanup'), receipt.get('reason'))
            land(receipt, path)
            current = (receipt.get('remote_published'), receipt.get('canonical'), receipt.get('claim_cleanup'), receipt.get('reason'))
            if previous != current:
                reports.append(receipt)
            if receipt.get('claim'):
                return reports  # cleanup trouble takes priority over unrelated notices
        if unreported:
            path, receipt = unreported[0]
            receipt['reported'] = True
            write_receipt(path, receipt)
            reports.append(receipt)
        return reports


def diagnostics(receipts: list[dict]) -> None:
    for receipt in receipts:
        print('canonical landing: ' + json.dumps({key: receipt.get(key) for key in
              ('remote_published', 'canonical', 'claim_cleanup', 'claim_owner', 'reason', 'cleanup_reason')}, sort_keys=True), file=sys.stderr)

#!/usr/bin/env python3
"""Shared validation for client-owned SessionStart transcript evidence."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path


from native_transcript_identity import (
    MAX_BINDING_LINES as MAX_BINDING_LINES,
    TRANSCRIPT_READ_CHARS as TRANSCRIPT_READ_CHARS,
    MAX_PROJECTED_STRING_CHARS as MAX_PROJECTED_STRING_CHARS,
    MAX_TRANSCRIPT_JSON_DEPTH as MAX_TRANSCRIPT_JSON_DEPTH,
    RECEIPT_CLIENTS as RECEIPT_CLIENTS,
    claude_root_transcript_path as claude_root_transcript_path,
    client_root_transcript_path as client_root_transcript_path,
    muse_sessions_root as muse_sessions_root,
    muse_root_transcript_path as muse_root_transcript_path,
    resolve_muse_transcript as resolve_muse_transcript,
    transcript_binding_state as transcript_binding_state,
    transcript_binds_session as transcript_binds_session,
)


def latest_receipt_paths(destination: Path, client: str) -> tuple[Path, Path]:
    """Return the generic and client-specific latest receipt paths."""
    if client not in RECEIPT_CLIENTS:
        raise ValueError(f"unsupported receipt client: {client}")
    suffix = f"-{client}"
    generic = destination
    if destination.stem.endswith(suffix):
        generic = destination.with_name(
            f"{destination.stem[: -len(suffix)]}{destination.suffix}"
        )
    client_path = generic.with_name(
        f"{generic.stem}-{client}{generic.suffix}"
    )
    return generic, client_path


def receipt_registry_root(latest_receipt: Path, client: str) -> Path:
    """Return the event registry shared by a client's latest receipt pointer."""
    generic, _ = latest_receipt_paths(latest_receipt, client)
    return generic.parent / f"{generic.stem}-events"


def receipt_event_path(
    latest_receipt: Path,
    *,
    client: str,
    session_id: str,
    event_id: str,
) -> Path:
    """Return the immutable path for one genuine SessionStart event."""
    if client not in RECEIPT_CLIENTS:
        raise ValueError(f"unsupported receipt client: {client}")
    try:
        uuid.UUID(session_id)
        uuid.UUID(event_id)
    except ValueError as exc:
        raise ValueError("receipt session and event ids must be UUIDs") from exc
    return (
        receipt_registry_root(latest_receipt, client)
        / client
        / session_id
        / f"{event_id}.json"
    )


def validate_receipt_event_directory(
    latest_receipt: Path,
    client: str,
    session_id: str,
) -> Path:
    """Reject symlinked or wrongly typed registry ancestors."""
    try:
        uuid.UUID(session_id)
    except ValueError as exc:
        raise ValueError(f"invalid {client} session id: {session_id}") from exc
    root = receipt_registry_root(latest_receipt, client)
    directory = root / client / session_id
    for path in (root, root / client, directory):
        if path.exists() and (path.is_symlink() or not path.is_dir()):
            raise ValueError(f"receipt registry path is unsafe: {path}")
    return directory


def receipt_recorded_order(
    payload: dict[str, object], path: Path
) -> tuple[datetime, str]:
    recorded_at = payload.get("recorded_at")
    event_id = str(payload.get("receipt_event_id") or "")
    try:
        recorded = datetime.fromisoformat(str(recorded_at))
        if recorded.tzinfo is None:
            recorded = recorded.replace(tzinfo=timezone.utc)
        if event_id:
            uuid.UUID(event_id)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid receipt ordering fields: {path}") from exc
    return recorded.astimezone(timezone.utc), event_id


def session_receipt_path(
    latest_receipt: Path,
    client: str,
    session_id: str,
    *,
    expected_plugin_version: str | None = None,
    expected_plugin_root: Path | None = None,
) -> Path | None:
    """Resolve the newest preserved event for one exact client session.

    The latest pointer remains a current-health cache.  The event registry is
    the durable runtime evidence. When a source version or enabled plugin root
    is supplied, selection stays within that exact release identity before
    choosing the newest resume event. A matching legacy latest receipt is
    accepted only as a migration fallback for receipts created before the
    registry.
    """
    if client not in RECEIPT_CLIENTS:
        raise ValueError(f"unsupported receipt client: {client}")
    try:
        uuid.UUID(session_id)
    except ValueError as exc:
        raise ValueError(f"invalid {client} session id: {session_id}") from exc

    directory = validate_receipt_event_directory(
        latest_receipt, client, session_id
    )
    if directory.exists():
        candidates: list[tuple[tuple[datetime, str], Path]] = []
        for path in sorted(directory.glob("*.json")):
            if path.is_symlink() or not path.is_file():
                raise ValueError(f"receipt event is unsafe: {path}")
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise ValueError(f"receipt event is unreadable: {path}") from exc
            if not isinstance(payload, dict):
                raise ValueError(f"receipt event is not an object: {path}")
            if (
                payload.get("client") != client
                or payload.get("session_id") != session_id
                or path.stem != str(payload.get("receipt_event_id") or "")
            ):
                raise ValueError(f"receipt event identity mismatch: {path}")
            if (
                expected_plugin_version is not None
                and payload.get("plugin_version") != expected_plugin_version
            ):
                continue
            if expected_plugin_root is not None:
                actual_root_text = payload.get("plugin_root")
                if not isinstance(actual_root_text, str) or not actual_root_text:
                    continue
                try:
                    actual_root = Path(actual_root_text).resolve()
                    required_root = expected_plugin_root.resolve()
                except OSError as exc:
                    raise ValueError(
                        f"receipt event plugin root is invalid: {path}"
                    ) from exc
                if actual_root != required_root:
                    continue
            candidates.append((receipt_recorded_order(payload, path), path))
        if candidates:
            return max(candidates)[1]

    if latest_receipt.is_symlink():
        raise ValueError(f"latest receipt is unsafe: {latest_receipt}")
    try:
        legacy = json.loads(latest_receipt.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        raise ValueError(f"latest receipt is unreadable: {latest_receipt}") from exc
    if not isinstance(legacy, dict):
        raise ValueError(f"latest receipt is not an object: {latest_receipt}")
    legacy_matches = (
        legacy.get("client") == client
        and legacy.get("session_id") == session_id
        and (
            expected_plugin_version is None
            or legacy.get("plugin_version") == expected_plugin_version
        )
    )
    if legacy_matches and expected_plugin_root is not None:
        legacy_root = legacy.get("plugin_root")
        if not isinstance(legacy_root, str) or not legacy_root:
            legacy_matches = False
        try:
            if legacy_matches:
                legacy_matches = (
                    Path(legacy_root).resolve() == expected_plugin_root.resolve()
                )
        except OSError as exc:
            raise ValueError(
                f"latest receipt plugin root is invalid: {latest_receipt}"
            ) from exc
    if legacy_matches:
        return latest_receipt
    return None


def signed_observation(envelope, trust, expected, *, now=None):
    """Verify a portable attestation without granting local live-load status.

    This is the receipt consumer's explicit portable plane. Existing genuine
    transcript and native-install checks remain mandatory for local live load.
    Reading an already accepted event is permitted; new admission is one-shot.
    """
    from signed_receipt import verify
    return verify(envelope, trust, expected, now=now)


def admit_signed_observation(latest_receipt, envelope, trust, expected, *, now=None, source_check=None):
    """Preserve one portable event in this owner's existing event registry.

    Exact event identity, independent of a new signature/challenge, is the
    one-shot admission key. O_EXCL is the cross-process arbitration. A crash
    after creation consumes the event with an incomplete record; it does not
    reopen permission to replay. The portable subdirectory cannot feed local
    SessionStart promotion, which uses client/session/event at schema 2.
    """
    import hashlib
    from signed_receipt import (canonical, canonical_path, held_directory,
                                verification_snapshot, revalidate_verified_inputs)
    snapshot = verification_snapshot(envelope, trust, expected)
    result = signed_observation(envelope, trust, expected, now=now)
    root = canonical_path(receipt_registry_root(Path(latest_receipt), expected['client']))
    # The caller supplies the explicitly selected registry owner. Its parent
    # must already exist; no arbitrary ancestor creation or installation occurs.
    with held_directory(root.parent) as (parent, recheck):
        descriptors = []
        try:
            current = parent
            for name in (root.name, 'signed-observations-v1', expected['client'], expected['session_id']):
                if source_check is not None:
                    source_check()
                revalidate_verified_inputs(snapshot, envelope, trust, expected, now=now)
                try:
                    os.mkdir(name, mode=0o700, dir_fd=current)
                    os.fsync(current)
                except FileExistsError:
                    pass
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current)
                import stat
                metadata = os.fstat(child)
                if metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) & 0o022:
                    os.close(child)
                    raise ValueError('signed registry requires current-owner non-writable directories')
                descriptors.append((current, name, child, metadata))
                current = child
            def verify_chain():
                recheck()
                for ancestor, name, child, original in descriptors:
                    fresh = os.stat(name, dir_fd=ancestor, follow_symlinks=False)
                    retained = os.fstat(child)
                    def fields(s):
                        return (s.st_dev, s.st_ino, s.st_mode, s.st_uid)
                    if fields(fresh) != fields(original) or fields(retained) != fields(original):
                        raise ValueError('signed registry changed before admission')
            verify_chain()
            # Revalidate the exact values after filesystem preparation; callers
            # cannot mutate the trust or envelope between verification and store.
            immutable = canonical({'envelope': envelope, 'trust': trust, 'expected': expected})
            confirmed = signed_observation(envelope, trust, expected, now=now)
            if confirmed != result:
                raise ValueError('signed observation changed before admission')
            raw = canonical({'schema': 1, 'envelope': envelope, 'verification': result}) + b'\n'
            if canonical({'envelope': envelope, 'trust': trust, 'expected': expected}) != immutable:
                raise ValueError('signed inputs changed before admission')
            verify_chain()
            if source_check is not None:
                source_check()
            revalidate_verified_inputs(snapshot, envelope, trust, expected, now=now)
            filename = expected['event_id'] + '.json'
            try:
                descriptor = os.open(filename, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=current)
            except FileExistsError as exc:
                raise ValueError('signed event already admitted or has unresolved interrupted custody; replay refused') from exc
            try:
                created = os.fstat(descriptor)
                def verify_record(*, complete):
                    held = os.fstat(descriptor)
                    named = os.stat(filename, dir_fd=current, follow_symlinks=False)
                    identity = (created.st_dev, created.st_ino, created.st_uid, created.st_mode)
                    for info in (held, named):
                        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                                or (info.st_dev, info.st_ino, info.st_uid, info.st_mode) != identity
                                or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600):
                            raise ValueError('signed record identity or protection changed')
                    if complete:
                        if held.st_size != len(raw) or os.pread(descriptor, len(raw) + 1, 0) != raw:
                            raise ValueError('signed record differs from admitted bytes')
                        after = os.fstat(descriptor)
                        after_named = os.stat(filename, dir_fd=current, follow_symlinks=False)
                        def stable(info):
                            return (info.st_dev, info.st_ino, info.st_uid, info.st_mode, info.st_nlink,
                                    info.st_size, info.st_mtime_ns, info.st_ctime_ns)
                        if stable(held) != stable(after) or stable(after) != stable(after_named):
                            raise ValueError('signed record changed during final readback')
                verify_record(complete=False)
                view = memoryview(raw)
                while view:
                    written = os.write(descriptor, view)
                    if written <= 0:
                        raise ValueError('incomplete signed receipt write')
                    view = view[written:]
                os.fsync(descriptor)
                os.fsync(current)
                verify_chain()
                if source_check is not None:
                    source_check()
                verify_record(complete=True)
                verify_chain()
                revalidate_verified_inputs(snapshot, envelope, trust, expected, now=now)
            finally:
                os.close(descriptor)
            return {**result, 'admitted': True, 'registry_sha256': hashlib.sha256(raw).hexdigest()}
        finally:
            for _, _, descriptor, _ in reversed(descriptors):
                os.close(descriptor)


def issue_signed_observation(local_receipt, source_root, plugin_root, transcript_root,
                             trust, expected, private_key, *, expires_at, now=None):
    """Project real existing SessionStart evidence into a content-free capsule.

    The existing local transcript and installation owners determine the result.
    Missing/not-yet-created transcript evidence stays UNKNOWN; conflicting or
    invalid transcript evidence stays FAIL. Unsupported native adapters refuse.
    Supplying a key does not enroll it or upgrade a client capability.
    """
    import sys
    from signed_receipt import (read_regular, strict_json, canonical_path, validate_bindings,
                                now_time, sign, SCHEMA, instant,
                                verification_snapshot, revalidate_verified_inputs)
    validate_bindings(expected)
    client = expected['client']
    if client not in RECEIPT_CLIENTS:
        raise ValueError('native receipt producer is not qualified for this client')
    path = canonical_path(local_receipt)
    raw = read_regular(path)
    event = strict_json(raw)
    required = {'receipt_schema', 'hook_event_name', 'session_id', 'receipt_event_id',
                'client', 'plugin_root', 'plugin_version', 'recorded_at', 'transcript_path',
                'provenance_env', 'transcript_bound_at_record'}
    if not isinstance(event, dict) or not required <= set(event):
        raise ValueError('incomplete native receipt')
    if (type(event['receipt_schema']) is not int or event['receipt_schema'] != 2
            or event['hook_event_name'] != 'SessionStart'
            or event['client'] != client or event['session_id'] != expected['session_id']
            or event['receipt_event_id'] != expected['event_id']
            or event['provenance_env'] != client + '-transcript'
            or type(event['transcript_bound_at_record']) is not bool):
        raise ValueError('native receipt identity or provenance mismatch')
    source_root, plugin_root = canonical_path(source_root), canonical_path(plugin_root)
    if canonical_path(event['plugin_root']) != plugin_root:
        raise ValueError('native receipt plugin root differs from selected installation')
    module_dir = Path(__file__).resolve().parents[2] / 'synthesis-onboarding/scripts'
    if str(module_dir) not in sys.path:
        sys.path.insert(0, str(module_dir))
    from system_contract import canonical_tree_digest, verify_native_release_inventory
    def installation_check():
        digest = canonical_tree_digest(source_root)
        if digest != expected['source_sha256']:
            raise ValueError('native receipt source differs from the expected generation')
        installed = verify_native_release_inventory(plugin_root, source_root, digest)
        if installed != expected['installation_sha256']:
            raise ValueError('native receipt installation differs from expected generation')
        manifest = strict_json(read_regular(source_root / '.codex-plugin/plugin.json'))
        if not isinstance(manifest, dict) or manifest.get('version') != event['plugin_version']:
            raise ValueError('native receipt version differs from source')
        if event.get('execution_root') is not None:
            execution = canonical_path(event['execution_root'])
            if verify_native_release_inventory(execution, source_root, digest) != digest:
                raise ValueError('hook execution source differs from signed generation')
    transcript = canonical_path(event['transcript_path'])
    transcript_root = canonical_path(transcript_root)
    if not client_root_transcript_path(transcript, client, expected['session_id'], transcript_root):
        raise ValueError('native receipt lacks a canonical root-session transcript path')
    installation_check()
    binding = transcript_binding_state(transcript, client, expected['session_id'])
    status = {'bound': 'PASS', 'pending': 'UNKNOWN', 'conflicting': 'FAIL', 'invalid': 'FAIL'}[binding]
    observed = instant(event['recorded_at'])
    payload = {**expected, 'schema': SCHEMA, 'event': 'SessionStart', 'status': status,
               'observed_at': observed.isoformat(), 'issued_at': now_time(now).isoformat(),
               'expires_at': expires_at}
    envelope = sign(payload, trust, private_key, now=now)
    snapshot = verification_snapshot(envelope, trust, expected)
    if read_regular(path) != raw or transcript_binding_state(transcript, client, expected['session_id']) != binding:
        raise ValueError('native receipt source changed during issuance')
    installation_check()
    revalidate_verified_inputs(snapshot, envelope, trust, expected, now=now)
    return envelope


def hermes_source_binding(profile_home, session_id, *, profile, cwd, now=None):
    """Metadata source binding; does not grant execution or attest live loading."""
    from hermes_source import binding
    return binding(profile_home, session_id, profile=profile, cwd=cwd, now=now)


def _receipt(record, latest):
    from live_receipt import receipt_event_path
    from signed_receipt import canonical_path, read_regular, strict_json
    path = receipt_event_path(canonical_path(latest), client=record['client'],
                              session_id=record['session_id'], event_id=record['receipt_event_id'])
    raw = read_regular(path)
    if strict_json(raw) != record:
        raise ValueError('registry outcome changed before callback witness')
    return path, raw


def callback_generation(plugin_root, execution_root):
    """Finite current byte/membership snapshots through the inventory owner."""
    from vendor_bundle import source_inventory, digest
    from signed_receipt import canonical_path
    return {'algorithm': 'sha256-vendor-inventory-v1',
            'installation': digest(source_inventory(canonical_path(plugin_root))),
            'execution': digest(source_inventory(canonical_path(execution_root)))}


def callback_witness(record, latest):
    """Bind emitted callback output to the existing committed outcome bytes."""
    if (not isinstance(record, dict) or record.get('context_outcome') != 'INJECTED'
            or record.get('hook_event_name') != 'SessionStart'):
        raise ValueError('callback witness requires a committed injected outcome')
    import hashlib
    _, raw = _receipt(record, latest)
    if record.get('callback_generation') != callback_generation(record['plugin_root'], record['execution_root']):
        raise ValueError('callback generation changed before emitted witness')
    return 'SYNTHESIS_NATIVE_RECEIPT ' + json.dumps({'event_id': record['receipt_event_id'],
                                'sha256': hashlib.sha256(raw).hexdigest()}, sort_keys=True, separators=(',', ':'))


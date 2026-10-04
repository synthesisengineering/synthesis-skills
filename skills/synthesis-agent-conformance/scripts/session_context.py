#!/usr/bin/env python3
"""Emit a compact, verified project anchor for agent lifecycle hooks."""

from __future__ import annotations

import argparse
import json
import math
import time
import errno
import os
import re
import sys
import tempfile
import traceback
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

# Diagnostic CLI invocations must not create caches while importing providers.
# The conformance caller also uses -B, which applies before this script loads.
if "--diagnostic" in sys.argv[1:]:
    sys.dont_write_bytecode = True

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows only
    fcntl = None

try:
    import msvcrt
except ImportError:  # pragma: no cover - POSIX only
    msvcrt = None

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
PROJECT_MANAGEMENT_SCRIPTS_DIR = (
    Path(__file__).resolve().parents[2] / "synthesis-project-management" / "scripts"
)
if str(PROJECT_MANAGEMENT_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_MANAGEMENT_SCRIPTS_DIR))
ONBOARDING_SCRIPTS_DIR = (
    Path(__file__).resolve().parents[2] / "synthesis-onboarding" / "scripts"
)
if str(ONBOARDING_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(ONBOARDING_SCRIPTS_DIR))

from project_context import extract, next_actions, record_freshness  # noqa: E402
from plan_reference import locate_plan  # noqa: E402
from active_project import load_and_validate  # noqa: E402
from project_state import (  # noqa: E402 - sibling owner path
    STATE_FILE,
    decode_pending_manifest,
    ProjectStateError,
    read_operational_state,
    resolve_project,
    semantic_issues,
    observer_native_identity,
)  # noqa: E402
from coordination_schema import display_id, parse_table_rows, row_identity  # noqa: E402
from live_receipt import (  # noqa: E402
    client_root_transcript_path,
    latest_receipt_paths,
    muse_sessions_root,
    receipt_event_path,
    receipt_recorded_order,
    resolve_muse_transcript,
    transcript_binding_state,
    validate_receipt_event_directory,
)
from plugin_currency import sessionstart_notice  # noqa: E402
from system_contract import SystemState  # noqa: E402


DEFAULT_POINTER = Path.home() / ".synthesis" / "active-project.json"
DEFAULT_COORDINATION_BOARD = (
    Path.home() / ".synthesis" / "coordination" / "active-sessions.md"
)
DEFAULT_LIVE_RECEIPT = (
    Path.home()
    / ".synthesis"
    / "agent-conformance"
    / "live"
    / "public-sessionstart.json"
)
DEFAULT_PENDING_HANDOFFS = (
    Path(os.environ.get("SYNTHESIS_HOME", str(Path.home() / ".synthesis")))
    / "repo-guard"
    / "pending"
)


def atomic_json_write(destination: Path, payload: dict[str, object]) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=destination.parent,
            prefix=destination.name + ".",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_name = temporary.name
            temporary.write(json.dumps(payload, indent=2) + "\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, destination)
    finally:
        if temporary_name and os.path.exists(temporary_name):
            os.unlink(temporary_name)


@contextmanager
def receipt_registry_lock(destination: Path, *, timeout: float = 5.0):
    """Serialize receipts under a finite wait; never steal another owner lock."""
    if (
        type(timeout) not in (int, float)
        or not math.isfinite(timeout)
        or not 0 < timeout <= 30
    ):
        raise ValueError("receipt lock requires a finite 0–30 second wait")
    if fcntl is not None:
        from run_admission import bounded_lock

        lock_path = destination.parent / f".{destination.stem}-events.lock"
        with bounded_lock(lock_path, timeout=timeout):
            yield
        return

    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.parent.is_symlink():
        raise ValueError(f"receipt registry parent is a symlink: {destination.parent}")
    lock_path = destination.parent / f".{destination.stem}-events.lock"
    if lock_path.is_symlink():
        raise ValueError(f"receipt registry lock is a symlink: {lock_path}")
    with lock_path.open("a+b") as handle:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        elif msvcrt is not None:  # pragma: no cover - Windows only
            if handle.seek(0, os.SEEK_END) == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            deadline = time.monotonic() + timeout
            while True:
                try:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError as exc:
                    if exc.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                        raise
                    if time.monotonic() >= deadline:
                        raise RuntimeError(
                            "timed out acquiring native receipt lock"
                        ) from exc
                    time.sleep(min(0.01, max(0, deadline - time.monotonic())))
        else:  # pragma: no cover - unsupported Python platform
            raise RuntimeError("receipt registry locking is unavailable")
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            elif msvcrt is not None:  # pragma: no cover - Windows only
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def _write_latest_if_newer(destination: Path, receipt: dict[str, object]) -> None:
    if destination.exists():
        if destination.is_symlink() or not destination.is_file():
            raise ValueError(f"latest receipt path is unsafe: {destination}")
        try:
            current = json.loads(destination.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValueError(f"latest receipt is unreadable: {destination}") from exc
        if not isinstance(current, dict):
            raise ValueError(f"latest receipt is not an object: {destination}")
        if receipt_recorded_order(current, destination) >= receipt_recorded_order(
            receipt, destination
        ):
            return
    atomic_json_write(destination, receipt)


CLIENT_PLUGIN_ROOT_ENV = "CLAUDE_PLUGIN_ROOT"


def execution_root() -> Path:
    """The plugin tree this script executes from: the client's plugin cache
    when the hook runs the cached script directly, or the active release root
    when it runs through `synthesis exec-public`."""
    return SCRIPTS_DIR.parents[2]


def _manifest_version(root: Path) -> str | None:
    for manifest in (
        root / ".codex-plugin" / "plugin.json",
        root / ".claude-plugin" / "plugin.json",
    ):
        try:
            version = json.loads(manifest.read_text(encoding="utf-8")).get("version")
        except (OSError, ValueError):
            continue
        if version:
            return str(version)
    return None


def plugin_identity() -> tuple[str | None, str]:
    """Return the version and root of the plugin the client loaded.

    Both clients export the root they loaded the plugin from to every hook
    (the variable their hook commands expand). Under `synthesis exec-public`
    the script runs from the active release root instead, so the receipt
    would otherwise name a root the client never loaded and the hook-live
    plane would refuse it. The client's root wins when it carries a plugin
    manifest; otherwise the execution root is the only identity available.
    """
    client_root = os.environ.get(CLIENT_PLUGIN_ROOT_ENV, "").strip()
    if client_root:
        root = Path(client_root).expanduser()
        version = _manifest_version(root)
        if version:
            return version, str(root)
    root = execution_root()
    return _manifest_version(root), str(root)


def append_currency_notice(message: str, payload: dict[str, object]) -> str:
    """Prepend the lifecycle notice to genuine SessionStart output."""
    if payload.get("hook_event_name") != "SessionStart":
        return message
    try:
        notice = sessionstart_notice(plugin_identity()[1])
    except Exception as exc:
        notice = f"Synthesis plugin currency could not be verified: {exc}."
    return notice + "\n" + message if notice else message


def _release_runtime():
    """Load the onboarding runtime from this release tree (or checkout)."""
    scripts = (
        Path(__file__).resolve().parent.parent.parent
        / "synthesis-onboarding"
        / "scripts"
    )
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    import release_runtime

    return release_runtime


def append_runtime_digest_notice(message: str, payload: dict[str, object]) -> str:
    """Prepend the once-per-session full-digest line (S19).

    SessionStart fires once per session, so this is the reporting
    channel for a tree that is under its tripwire but drifting: it runs
    the full digest, reports the verdict, and never writes. Outside an
    installed release (no active descriptor) there is nothing to check.
    """
    if payload.get("hook_event_name") != "SessionStart":
        return message
    pointer = os.environ.get("SYNTHESIS_ACTIVE_DESCRIPTOR", "")
    if not pointer or not Path(pointer).expanduser().is_file():
        return message
    try:
        runtime = _release_runtime()
        checked = runtime.verified_release()
        report = runtime.full_digest_report(Path(checked["release_root"]))
        projection = checked.get("projection") or {}
        expected = projection.get("content_digest", checked.get("content_digest"))
        mode = checked.get("_verification_mode", "unknown")
        if report["tree_digest"] == expected:
            line = (
                "Synthesis runtime digest: verified (%d files, %s ms, "
                "per-call mode %s)." % (report["files"], report["elapsed_ms"], mode)
            )
        else:
            line = (
                "Synthesis runtime digest: DRIFTED — the full tree digest "
                "differs from the recorded digest; run synthesis doctor."
            )
    except Exception as exc:
        line = f"Synthesis runtime digest could not be verified: {exc}."
    return line + "\n" + message


def client_provenance(
    payload: dict[str, object], session_id: str
) -> tuple[str, str] | None:
    """Use PM's shared native path/identity contract for lifecycle receipts.

    This is historical identity evidence only. PM admission and the native
    writer contract still establish current ownership before any mutation.
    A supplied invalid path cannot fall back to another valid native store.
    """
    if payload.get("session_id") not in (None, "", session_id):
        return None
    try:
        client, _native = observer_native_identity(
            {**payload, "session_id": session_id}
        )
    except ProjectStateError:
        return None
    return client, f"{client}-transcript"


def deferred_claude_provenance(
    payload: dict[str, object], session_id: str
) -> tuple[str, str] | None:
    """Validate Claude's transcript destination before its first JSONL write.

    Claude invokes SessionStart hooks before it creates or populates the
    transcript named in the hook payload.  The receipt can therefore preserve
    the client-delivered event before the binding exists, while conformance
    still requires that exact client-owned transcript to bind the session id
    before accepting the evidence.
    """
    transcript_text = payload.get("transcript_path")
    if (
        not isinstance(transcript_text, str)
        or not Path(transcript_text).is_absolute()
        or payload.get("session_id") not in (None, "", session_id)
    ):
        return None
    transcript = Path(transcript_text)
    claude_root = Path(
        os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude"))
    ).expanduser()
    if not claude_root.is_absolute() or not client_root_transcript_path(
        transcript, "claude", session_id, claude_root
    ):
        return None
    # This exception is only for an as-yet-unbound native destination. Bound
    # history must pass the shared observer, including cross-client ambiguity.
    if transcript_binding_state(transcript, "claude", session_id) != "pending":
        return None
    return "claude", "claude-transcript"


def callback_candidate_provenance(payload, session_id):
    """An explicit worker mode hint permits inert evidence storage, not trust.

    Ephemeral Codex protocol sessions intentionally have no history file. The
    native worker's later admitted captured-transport join must authenticate this
    candidate. It cannot update live-load state, latest pointers, or signing.
    """
    if (
        os.environ.get("SYNTHESIS_CALLBACK_OBSERVATION") != "codex-ephemeral-callback"
        or payload.get("hook_event_name") != "SessionStart"
        or payload.get("session_id") != session_id
        or payload.get("transcript_path") not in (None, "")
        or not isinstance(payload.get("cwd"), str)
        or not Path(payload["cwd"]).is_absolute()
    ):
        return None
    try:
        uuid.UUID(session_id)
    except (ValueError, TypeError, AttributeError):
        return None
    return "codex", "codex-callback-candidate"


def record_live_receipt(payload: dict[str, object], destination: Path) -> bool:
    """Record only genuine SessionStart-shaped client payloads.

    Direct probes cannot manufacture transcript-backed live evidence. An
    explicit ephemeral callback hint can preserve a structurally unverified
    candidate only; the separate admitted native transport consumer must bind
    it before it can support a scoped callback observation.
    """
    event = payload.get("hook_event_name")
    session_id = payload.get("session_id")
    if event != "SessionStart" or not isinstance(session_id, str) or not session_id:
        return False
    try:
        uuid.UUID(session_id)
    except ValueError:
        return False
    provenance = client_provenance(payload, session_id)
    deferred = provenance is None
    if provenance is None:
        provenance = deferred_claude_provenance(payload, session_id)
    if provenance is None:
        provenance = callback_candidate_provenance(payload, session_id)
    if provenance is None:
        return False
    candidate = provenance == ("codex", "codex-callback-candidate")
    version, plugin_root = plugin_identity()
    client, provenance_env = provenance
    transcript = Path(str(payload.get("transcript_path") or "")).expanduser()
    if client == "muse" and (not transcript.is_absolute() or not transcript.is_file()):
        resolved = resolve_muse_transcript(session_id)
        if resolved is None:
            return False
        transcript = resolved
    if client == "muse" and not client_root_transcript_path(
        transcript, "muse", session_id, muse_sessions_root()
    ):
        return False
    binding_state = (
        "pending"
        if candidate
        else transcript_binding_state(transcript, client, session_id)
    )
    if (
        not candidate
        and binding_state != "bound"
        and not (client == "claude" and binding_state == "pending")
    ):
        return False
    if deferred and not candidate:
        # Claude can create its transcript while SessionStart is running. A
        # pending exception cannot promote that new history without the full
        # identity contract, or retain a destination that has become unsafe.
        current = (
            client_provenance(payload, session_id)
            if binding_state == "bound"
            else deferred_claude_provenance(payload, session_id)
        )
        if current != provenance:
            return False
    transcript_bound_at_record = binding_state == "bound"
    event_id = str(uuid.uuid4())
    receipt = {
        "receipt_schema": 2,
        "receipt_event_id": event_id,
        "hook_event_name": event,
        "session_id": session_id,
        "client": client,
        "cwd": payload.get("cwd"),
        "source": payload.get("source"),
        "transcript_path": (
            str(transcript) if client == "muse" else payload.get("transcript_path")
        ),
        "transcript_bound_at_record": transcript_bound_at_record,
        "provenance_env": provenance_env,
        "plugin_version": version,
        "plugin_root": plugin_root,
        "execution_root": str(execution_root()),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    if candidate:
        receipt["callback_candidate"] = True
    try:
        import upgrade_campaigns

        campaign_selection = upgrade_campaigns.selection(SystemState(), receipt)
    except Exception as exc:
        # An optional report-only catalog is not the native delivery owner.
        # Preserve observed delivery while refusing campaign selection; no
        # acknowledgement, execution or completion is inferred from this error.
        receipt["campaign_notice_error"] = {
            "status": "REFUSED",
            "error_type": type(exc).__name__,
            "detail": str(exc)[:400],
            "execution_authorized": False,
        }
    else:
        if campaign_selection is not None:
            receipt["campaign_notices"] = campaign_selection
    generic_latest, client_latest = latest_receipt_paths(destination, client)
    event_path = receipt_event_path(
        client_latest,
        client=client,
        session_id=session_id,
        event_id=event_id,
    )
    with receipt_registry_lock(generic_latest):
        validate_receipt_event_directory(client_latest, client, session_id)
        if event_path.exists():
            raise FileExistsError(f"receipt event already exists: {event_path}")
        atomic_json_write(event_path, receipt)
        if not candidate:
            _write_latest_if_newer(client_latest, receipt)
            _write_latest_if_newer(generic_latest, receipt)
    if version and transcript_bound_at_record:
        SystemState().record_live_load(receipt=receipt)
    return True


def record_hermes_observation(payload, profile_home, active, state_home, *, context=None):
    """Retain one source observation through this receipt owner; no live grant.

    The unique event uses exclusive descriptor-relative creation. Interrupted
    partial records remain evidence and cannot become another writer's file.
    """
    from hermes_source import chain
    from live_receipt import hermes_source_binding
    from signed_receipt import held_directory, canonical
    import hashlib
    import stat

    event = payload.get("hook_event_name")
    if event not in {"on_session_start", "pre_llm_call"}:
        raise ValueError("event is not an observational lifecycle callback")
    binding = hermes_source_binding(
        profile_home,
        payload.get("session_id"),
        profile=payload.get("profile"),
        cwd=payload.get("cwd", ""),
    )
    if binding["status"] != "BOUND":
        raise ValueError("native source is not bound")
    if (
        not isinstance(active, dict)
        or not isinstance(active.get("content_digest"), str)
        or not re.fullmatch(r"[a-f0-9]{64}", active["content_digest"])
    ):
        raise ValueError("verified release identity is missing")
    state_home = Path(state_home)
    chain(state_home)
    event_id = str(uuid.uuid4())
    receipt = {
        "schema": 1,
        "kind": "callback-source-observation",
        "client": "hermes",
        "event_id": event_id,
        "hook_event_name": event,
        "source_binding": binding,
        "source_digest": active["content_digest"],
        "plugin_version": active.get("version"),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "native_live": "UNKNOWN",
        "authority": False,
    }
    if context is not None:
        if event != "pre_llm_call" or not isinstance(context, str) or len(context.encode()) > 5500:
            raise ValueError("bounded Hermes consumer context required")
        from live_receipt import callback_generation
        receipt.update(context_sha256=hashlib.sha256(context.encode()).hexdigest(),
                       turn_id=payload.get("extra", {}).get("turn_id"),
                       plugin_root=active["release_root"], execution_root=active["release_root"],
                       callback_generation=callback_generation(Path(active["release_root"]), Path(active["release_root"])),
                       candidate_only=True)
    raw = canonical(receipt) + b"\n"
    descriptors, edges = [], []
    with held_directory(state_home) as (root, root_check):
        original_root = os.fstat(root)
        if original_root.st_uid != os.getuid() or original_root.st_mode & 0o022:
            raise ValueError("conformance state root ownership is unsafe")

        def directory_identity(meta):
            return meta.st_dev, meta.st_ino, meta.st_mode, meta.st_uid

        def recheck():
            root_check()
            for parent, name, child, original in edges:
                if (
                    directory_identity(os.fstat(child)) != original
                    or directory_identity(
                        os.stat(name, dir_fd=parent, follow_symlinks=False)
                    )
                    != original
                ):
                    raise ValueError("observation directory identity changed")

        parent, directory = root, state_home
        try:
            for component in (
                "agent-conformance",
                "observations",
                "hermes",
                hashlib.sha256(binding["session_id"].encode()).hexdigest(),
            ):
                recheck()
                try:
                    os.mkdir(component, mode=0o700, dir_fd=parent)
                except FileExistsError:
                    pass
                child = os.open(
                    component,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=parent,
                )
                descriptors.append(child)
                meta = os.fstat(child)
                if (
                    not stat.S_ISDIR(meta.st_mode)
                    or meta.st_uid != os.getuid()
                    or meta.st_mode & 0o022
                ):
                    raise ValueError("observation directory is unsafe")
                edges.append((parent, component, child, directory_identity(meta)))
                parent, directory = child, directory / component
            recheck()
            filename = event_id + ".json"
            fd = os.open(
                filename,
                os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=parent,
            )
            try:
                original = os.fstat(fd)

                def file_check():
                    recheck()
                    named = os.stat(filename, dir_fd=parent, follow_symlinks=False)
                    current = os.fstat(fd)
                    for observed in (named, current):
                        if (
                            not stat.S_ISREG(observed.st_mode)
                            or observed.st_nlink != 1
                            or observed.st_uid != os.getuid()
                            or stat.S_IMODE(observed.st_mode) != 0o600
                            or (observed.st_dev, observed.st_ino)
                            != (original.st_dev, original.st_ino)
                        ):
                            raise ValueError("observation record identity changed")

                position = 0
                while position < len(raw):
                    file_check()
                    count = os.write(fd, raw[position:])
                    if count <= 0:
                        raise ValueError("observation write incomplete")
                    position += count
                os.fsync(fd)
                file_check()
                os.lseek(fd, 0, os.SEEK_SET)
                if os.read(fd, len(raw) + 1) != raw:
                    raise ValueError("observation readback differs")
                file_check()
                os.fsync(parent)
                return directory / filename
            finally:
                os.close(fd)
        except OSError as exc:
            raise ValueError("observation custody refused: " + str(exc)) from exc
        finally:
            for descriptor in reversed(descriptors):
                os.close(descriptor)


def refused_line(reason: str) -> str:
    """The S14 REFUSED additionalContext line for a no-pointer failure."""
    return (
        "synthesis project context: REFUSED (%s); no project context was "
        "injected; run the resume skill or project_packet.py compile <id>" % reason
    )


def print_envelope(message: str, payload: dict[str, object], format: str) -> None:
    """Emit the briefing in the client's hook envelope (or plain text)."""
    if format == "codex":
        event = payload.get("hook_event_name", "SessionStart")
        print(
            json.dumps(
                {
                    "continue": True,
                    "hookSpecificOutput": {
                        "hookEventName": event,
                        "additionalContext": message,
                    },
                }
            )
        )
    elif format == "claude":
        print(
            json.dumps(
                {
                    "continue": True,
                    "hookSpecificOutput": {
                        "hookEventName": "SessionStart",
                        "additionalContext": message,
                    },
                }
            )
        )
    else:
        print(message)


def _newest_delivery_event(
    client_latest: Path, client: str, session_id: str
) -> dict[str, object] | None:
    """Return the newest delivery event for one session, or None.

    Delivery events are the registry entries without a context_outcome;
    outcome records (pre- and post-carry-forward) always carry one. The
    outcome writer anchors to this event so the latest pointers keep the
    delivery contract the hook-live verifier requires.
    """
    directory = validate_receipt_event_directory(client_latest, client, session_id)
    if not directory.is_dir():
        return None
    best: dict[str, object] | None = None
    best_order: tuple[datetime, str] | None = None
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
        if "context_outcome" in payload or not payload.get("plugin_version"):
            continue
        order = receipt_recorded_order(payload, path)
        if best_order is None or order > best_order:
            best_order = order
            best = payload
    return best


def record_context_outcome(
    payload: dict[str, object],
    destination: Path,
    outcome: str,
    detail: str,
    *,
    return_record: bool = False,
) -> bool | dict:
    """Append the second receipt record: what the hook did (S14).

    The delivery receipt proves the client delivered the event; this
    record proves the outcome — INJECTED with the byte count, or REFUSED
    with the raising function and message. Only genuine SessionStart
    deliveries file one; probes and other events return False.

    The outcome record carries the delivery fields forward from the
    session's delivery event, so the latest pointers it updates keep the
    delivery contract (plugin version/root, provenance, transcript
    binding) the hook-live verifier requires. An outcome without a
    prior delivery event raises instead of filing: the hook only files
    outcomes for delivered events, and an unanchored outcome would
    replace the delivery proof latest-pointer readers depend on.
    """
    event = payload.get("hook_event_name")
    session_id = payload.get("session_id")
    if event != "SessionStart" or not isinstance(session_id, str) or not session_id:
        return False
    try:
        uuid.UUID(session_id)
    except ValueError:
        return False
    provenance = client_provenance(payload, session_id)
    if provenance is None:
        provenance = deferred_claude_provenance(payload, session_id)
    if provenance is None:
        provenance = callback_candidate_provenance(payload, session_id)
    if provenance is None:
        return False
    candidate = provenance == ("codex", "codex-callback-candidate")
    client, _provenance_env = provenance
    generic_latest, client_latest = latest_receipt_paths(destination, client)
    delivery = _newest_delivery_event(client_latest, client, session_id)
    if delivery is None:
        raise ValueError(f"outcome without a delivery receipt: {client}/{session_id}")
    if (
        delivery.get("provenance_env") != provenance[1]
        or bool(delivery.get("callback_candidate")) != candidate
    ):
        raise ValueError("callback outcome cannot change delivery evidence mode")
    event_id = str(uuid.uuid4())
    record = {
        "receipt_schema": 2,
        "receipt_event_id": event_id,
        "hook_event_name": event,
        "session_id": session_id,
        "client": client,
        "cwd": delivery.get("cwd"),
        "source": delivery.get("source"),
        "transcript_path": delivery.get("transcript_path"),
        "transcript_bound_at_record": delivery.get("transcript_bound_at_record"),
        "provenance_env": delivery.get("provenance_env"),
        "plugin_version": delivery.get("plugin_version"),
        "plugin_root": delivery.get("plugin_root"),
        "execution_root": delivery.get("execution_root"),
        "context_outcome": outcome,
        "context_outcome_detail": detail,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    if candidate:
        record["callback_candidate"] = True
    if return_record and outcome == "INJECTED":
        from live_receipt import callback_generation

        record["callback_generation"] = callback_generation(
            record["plugin_root"], record["execution_root"]
        )
    event_path = receipt_event_path(
        client_latest, client=client, session_id=session_id, event_id=event_id
    )
    with receipt_registry_lock(generic_latest):
        validate_receipt_event_directory(client_latest, client, session_id)
        if event_path.exists():
            raise FileExistsError(f"receipt event already exists: {event_path}")
        atomic_json_write(event_path, record)
        if not candidate:
            _write_latest_if_newer(client_latest, record)
            _write_latest_if_newer(generic_latest, record)
    return record if return_record else True


def raising_function(exc: BaseException) -> str:
    """Name of the function that raised, for REFUSED outcome records."""
    frames = traceback.extract_tb(exc.__traceback__)
    return frames[-1].name if frames else type(exc).__name__


def active_session_ids(board: Path) -> list[str]:
    if not board.is_file():
        return []
    text = board.read_text(encoding="utf-8")
    if not all(
        heading in text
        for heading in ("## Active sessions", "## Messages", "## Protocol")
    ):
        raise ValueError(f"coordination board schema is invalid: {board}")
    active = []
    for row in parse_table_rows(text):
        if row.get("status", "").lower() not in {
            "released",
            "complete",
            "completed",
            "closed",
        }:
            active.append(display_id(row_identity(row)))
    return active


def pending_handoff_count(directory: Path) -> int:
    if not directory.is_dir():
        return 0
    count = 0
    for path in directory.glob("*.json"):
        if path.is_symlink():
            raise ValueError(f"pending handoff manifest is a symlink: {path}")
        data = decode_pending_manifest(json.loads(path.read_text(encoding="utf-8")))
        if not isinstance(data.get("session_id"), str) or not isinstance(
            data.get("paths"), list
        ):
            raise ValueError(f"pending handoff manifest is invalid: {path}")
        count += 1
    return count


def project_from_cwd(cwd: Path | None) -> Path | None:
    """Discover a durable project when a task opens inside its directory."""
    if cwd is None:
        return None
    try:
        candidate = cwd.expanduser().resolve(strict=True)
    except OSError:
        return None
    if candidate.is_file():
        candidate = candidate.parent
    for directory in (candidate, *candidate.parents):
        if (
            (directory / "CONTEXT.md").is_file()
            and (directory / "REFERENCE.md").is_file()
            and (directory / "sessions").is_dir()
        ):
            return directory
    return None


def workspace_registry_notices(cwd: Path | None) -> list[str]:
    """Surface stale immediately discoverable project registries.

    A SessionStart event occurs before the user's named-project prompt is
    available to this hook.  At a workspace or knowledge-repository root we
    can still inspect the bounded registry shapes that the subsequent resolver
    will use.  This prevents a behind canonical checkout from looking healthy
    during the gap between SessionStart and named-project resolution without
    guessing which project the user will choose.
    """
    if cwd is None:
        return []
    try:
        root = cwd.expanduser().resolve(strict=True)
        if root.is_file():
            root = root.parent
        candidates = [root / "projects" / "index.yaml"]
        candidates.extend(
            child / "projects" / "index.yaml"
            for child in sorted(root.iterdir())
            if child.is_dir() and not child.is_symlink()
        )
    except OSError as exc:
        return [f"PROJECT REGISTRY DISCOVERY UNKNOWN: {exc}."]

    notices: list[str] = []
    seen: set[Path] = set()
    for index in candidates:
        if not index.is_file() or index.is_symlink():
            continue
        resolved = index.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        fresh, detail = record_freshness(index.parent)
        if not fresh and "behind fetched" in detail:
            notices.append(
                f"RECORD STALENESS WARNING: registry {index} is in a checkout "
                f"whose {detail}. Run the named project's causal resolver before "
                "reading its project prose."
            )
        elif not fresh or detail.startswith("no upstream configured"):
            notices.append(
                f"PROJECT REGISTRY FRESHNESS UNKNOWN: {index}: {detail}. "
                "Do not treat its project prose as current until the named "
                "project's causal resolver establishes a source."
            )
    return notices


def reconciled_project(
    project: Path, *, diagnostic: bool = False
) -> tuple[Path, list[str]]:
    """Resolve a project across worktrees and refs before reading its prose."""
    index = project.parent / "index.yaml"
    if not index.is_file():
        return project, []
    synthesis_home = Path(
        os.environ.get("SYNTHESIS_HOME", str(Path.home() / ".synthesis"))
    )
    board = synthesis_home / "coordination" / "active-sessions.md"
    pointer = synthesis_home / "active-project.json"
    report = resolve_project(
        project.name,
        index,
        repo_guard_root=synthesis_home / "repo-guard",
        checkpoint_receipt_root=synthesis_home / "project-state" / "receipts",
        coordination_board=board if board.is_file() else None,
        pointer=pointer,
        fetch=not diagnostic,
        fast_forward_canonical=not diagnostic,
        refresh_coordination=not diagnostic and board.is_file(),
    )
    if report.status not in {"PASS", "LOCAL_RECOVERABLE"}:
        raise ValueError(
            f"project-state reconciliation is {report.status}: "
            + "; ".join(report.issues)
        )
    if report.selected_path is None:
        raise ValueError(
            "newer project state is proven but has no safe readable worktree; "
            f"selected head={report.selected_head} tree={report.selected_tree}"
        )
    return Path(report.selected_path), report.issues


def append_project_context(
    lines: list[str], project: Path, *, label: str, diagnostic: bool = False
) -> None:
    project, recovery_issues = reconciled_project(project, diagnostic=diagnostic)
    context_path = project / "CONTEXT.md"
    context = context_path.read_text(encoding="utf-8")
    semantic = semantic_issues(project)
    if semantic:
        raise ValueError("semantic current-state failure: " + "; ".join(semantic))
    state_path = project / STATE_FILE
    has_state = state_path.exists() or state_path.is_symlink()
    try:
        state = read_operational_state(state_path) if has_state else {}
    except ProjectStateError as exc:
        raise ValueError(f"structured current-state failure: {exc}") from exc
    phase = str(state.get("phase") or extract(context, "Phase"))
    status = str(state.get("status") or extract(context, "Status"))
    plan_ref = (
        locate_plan(project, context, controlling_plan=state.get("controlling_plan"))
        if has_state
        else locate_plan(project, context)
    )
    if plan_ref.declared is not None and plan_ref.resolved is None:
        raise ValueError(plan_ref.detail)
    lines.extend(
        [
            f"{label}: {project}.",
            f"Current phase: {phase}.",
            f"Current status: {status}.",
            f"Controlling plan: {plan_ref.value}.",
        ]
    )
    fresh, freshness_detail = record_freshness(project)
    if not fresh:
        lines.append(f"RECORD STALENESS WARNING: {freshness_detail}.")
    for issue in recovery_issues:
        lines.append(f"PROJECT RECOVERY NOTE: {issue}.")
    actions = list(state.get("next_actions") or next_actions(context))
    if actions:
        lines.append("Recorded next actions:")
        lines.extend(f"- {action}" for action in actions)
    lines.append("Re-read CONTEXT.md and the controlling plan before substantive work.")


def build(
    pointer: Path,
    coordination_board: Path = DEFAULT_COORDINATION_BOARD,
    cwd: Path | None = None,
    pending_handoffs: Path = DEFAULT_PENDING_HANDOFFS,
    *,
    diagnostic: bool = False,
) -> str:
    now = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z (%A)")
    lines = [f"Verified local time: {now}."]
    if not diagnostic:
        from coordination import require_fresh_board

        require_fresh_board(coordination_board)
    sessions = active_session_ids(coordination_board)
    if sessions:
        lines.append(
            "Cross-agent coordination is active for session(s): "
            + ", ".join(sessions)
            + ". Read the coordination board and verify claims before writes."
        )
    pending = pending_handoff_count(pending_handoffs)
    if pending:
        lines.append(
            f"Local continuity: {pending} attributed edit manifest(s) await "
            "remote publication. Inspect working-tree truth before relying on "
            "cached project context; an interrupted task remains recoverable on "
            "this machine."
        )
    if not pointer.is_file():
        lines.append("No active synthesis project pointer is set.")
        discovered = project_from_cwd(cwd)
        if discovered is not None:
            append_project_context(
                lines,
                discovered,
                label="Stopped synthesis project discovered from the task directory",
                diagnostic=diagnostic,
            )
        else:
            lines.extend(workspace_registry_notices(cwd))
            lines.append(
                "Stopped-task recovery remains available: when the user names a "
                "synthesis project, run the project-state resolver from the current "
                "synthesis-project-management skill against the git-tracked "
                "projects/index.yaml before reading any project prose "
                "and run the Session Start Protocol automatically; never ask the user "
                "to run a context-lifecycle command or save state manually. One "
                "exception to automatic resolution: if the named project contradicts "
                "this session's own established context (its prior conversation, "
                "active project, or task directory), surface the contradiction and "
                "confirm which project is meant before switching - never silently "
                "resolve the name over the session's evidence."
            )
        return "\n".join(lines)

    data, pointer_issues = load_and_validate(
        pointer, coordination_board, refresh_lease=not diagnostic
    )
    if pointer_issues:
        raise ValueError("; ".join(pointer_issues))
    project = Path(data["project"]).expanduser().resolve()
    context_path = project / "CONTEXT.md"
    if not context_path.is_file():
        raise FileNotFoundError(f"active project CONTEXT.md is missing: {context_path}")

    plan = data.get("plan", "unknown")
    if plan != "unknown" and not Path(plan).is_file():
        raise FileNotFoundError(f"active plan is missing: {plan}")
    append_project_context(
        lines, project, label="Active synthesis project", diagnostic=diagnostic
    )
    return "\n".join(lines)


def append_inbox(
    message: str, payload: dict, board: Path, *, diagnostic: bool = False
) -> str:
    """Attach unread board messages for this seat, and for a non-Claude
    client its coordination identity, so the bus is delivered at session
    start and a Codex session learns the id its receipts are filed under.
    Only a claimed seat receives messages; the global pointer is another
    session's cache and is never an address."""
    try:
        from board_inbox import inbox_text

        extra = inbox_text(
            payload,
            board=board,
            mark=not diagnostic,
            strict=diagnostic,
            refresh_coordination=not diagnostic,
        )
    except Exception as exc:  # the inbox never blocks a session start
        if diagnostic:
            raise
        extra = f"Coordination inbox unavailable: {exc}"
    return message + ("\n" + extra if extra else "")


def _optional_campaign_notice(payload: dict, latest: Path) -> str:
    # Only the report-only extension is contained here. Native provenance and
    # core receipt writes keep their ordinary fail-closed exceptions outside it.
    try:
        import upgrade_campaigns

        return upgrade_campaigns.notice(SystemState(), payload, latest)
    except Exception:
        return (
            "Campaign review is unavailable; campaign selection and reporting "
            "remain refused. Inspect the campaign catalog and native receipt. "
            "This notice does not authorize campaign actions or establish "
            "acknowledgement/completion."
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--active-project-file", type=Path, default=DEFAULT_POINTER)
    parser.add_argument(
        "--diagnostic",
        action="store_true",
        help="Compare local context without deliveries, receipts, currency writes or state refreshes.",
    )
    parser.add_argument(
        "--coordination-board",
        type=Path,
        default=DEFAULT_COORDINATION_BOARD,
    )
    parser.add_argument(
        "--format",
        choices=("text", "codex", "claude"),
        default="text",
        help="Wrap output for a client hook schema.",
    )
    parser.add_argument(
        "--live-receipt",
        type=Path,
        default=Path(
            os.environ.get(
                "SYNTHESIS_PUBLIC_SESSIONSTART_RECEIPT",
                str(DEFAULT_LIVE_RECEIPT),
            )
        ),
    )
    args = parser.parse_args()
    if args.diagnostic:
        # Read-only Git commands such as status may otherwise refresh the index.
        os.environ["GIT_OPTIONAL_LOCKS"] = "0"
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}
    # The receipt is evidence that the client delivered this lifecycle event
    # for this session and plugin root. It is recorded before any context is
    # built, so a pointer left by another session, a behind worktree, or an
    # unreadable board can never erase that proof: on 2026-09-03 a foreign
    # pointer to a worktree eleven commits behind failed this hook closed
    # before it recorded, and no Claude session on the machine could show a
    # current receipt.
    delivered = False
    if not args.diagnostic:
        try:
            delivered = record_live_receipt(payload, args.live_receipt.expanduser())
        except Exception as exc:
            # Receipt-write failure: the REFUSED line goes out, but the
            # exit stays 2 — the delivery proof itself is missing (S14).
            print(f"synthesis live receipt failed closed: {exc}", file=sys.stderr)
            print_envelope(
                refused_line("live receipt failed: %s" % str(exc)[:120]),
                payload,
                args.format,
            )
            return 2
    pointer = args.active_project_file.expanduser()
    board = args.coordination_board.expanduser()
    cwd = Path(str(payload["cwd"])) if payload.get("cwd") else None
    try:
        message = build(pointer, board, cwd, diagnostic=args.diagnostic)
    except Exception as exc:
        if not pointer.is_file():
            # No-pointer build failure: announce the refusal as
            # additionalContext and exit 0 — the hook did its job by
            # refusing loudly instead of failing silent (S14).
            reason = "%s: %s" % (raising_function(exc), exc)
            if delivered:
                try:
                    record_context_outcome(
                        payload, args.live_receipt.expanduser(), "REFUSED", reason[:500]
                    )
                except Exception as outcome_exc:
                    print(
                        f"synthesis outcome record failed: {outcome_exc}",
                        file=sys.stderr,
                    )
            print_envelope(refused_line(reason[:300]), payload, args.format)
            return 0
        # A pointer is a cache written by whichever session last activated a
        # project; it is not authority for the session starting now. When it
        # cannot be validated, say so and recover exactly as if it were absent:
        # its project is never injected, and no session waits on another
        # task's checkout.
        ignored = pointer.with_name(pointer.name + ".ignored-by-this-session")
        try:
            message = build(ignored, board, cwd, diagnostic=args.diagnostic)
        except Exception as inner:
            print(f"synthesis project context failed closed: {inner}", file=sys.stderr)
            return 2
        message = (
            f"Active-project pointer ignored: {exc}. The pointer is a cache set by "
            "another session, not authority for this one; resolve the named project "
            "from the tracked projects/index.yaml through the causal resolver.\n"
            + message
        )
    if not args.diagnostic:
        message = append_currency_notice(message, payload)
        message = append_runtime_digest_notice(message, payload)
        campaign_notice = _optional_campaign_notice(
            payload, args.live_receipt.expanduser()
        )
        if campaign_notice:
            message = campaign_notice + "\n" + message
    try:
        message = append_inbox(message, payload, board, diagnostic=args.diagnostic)
    except Exception as exc:
        if delivered:
            try:
                record_context_outcome(
                    payload,
                    args.live_receipt.expanduser(),
                    "REFUSED",
                    "%s: %s" % (raising_function(exc), str(exc)[:400]),
                )
            except Exception as outcome_exc:
                print(
                    f"synthesis outcome record failed: {outcome_exc}", file=sys.stderr
                )
        print(f"synthesis diagnostic inbox failed closed: {exc}", file=sys.stderr)
        return 2

    if delivered:
        try:
            observed = record_context_outcome(
                payload,
                args.live_receipt.expanduser(),
                "INJECTED",
                "%d bytes" % len(message.encode("utf-8")),
                return_record=True,
            )
            from live_receipt import callback_witness

            message += "\n" + callback_witness(observed, args.live_receipt.expanduser())
        except Exception as outcome_exc:
            print(f"synthesis outcome record failed: {outcome_exc}", file=sys.stderr)
    print_envelope(message, payload, args.format)
    return 0


if __name__ == "__main__":
    sys.exit(main())

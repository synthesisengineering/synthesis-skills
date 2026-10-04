#!/usr/bin/env python3
"""Serialized, project-owned autopilot run state (schema 1).

API: create_run/load_run/apply_command; mutations require a native ``actor``
mapping with board and native_payload, a command_id, and (after creation) an
expected_revision. Events commit before projections. A retry with the same
command body returns its original committed state. Reusing its ID with a
different body fails. ``rebuild_projections`` repairs interrupted projections.

Reducers registered with register_command may change only ``extensions``.
They receive fresh, prevalidated evidence/artifact/admission views and must be
pure. register_verifier installs trusted *code*, never caller-provided policy;
the default for an unknown evidence kind is unverified. Files and receipts
are attestations unless a verifier actually establishes independent evidence.

The owner index is a host-local discovery aid under the existing autopilot
runtime. Portable events live under project/resources/autopilot-runs/<UUID>.
Pending index entries precede first activation; terminal events/tombstones
precede scheduler cleanup. Filesystem integrity is for cooperating admitted
writers, not cryptographic protection against a privileged filesystem editor.
External effects are recorded here; their action owners still enforce approval.
"""
from __future__ import annotations

from contextlib import ExitStack, contextmanager
from contextvars import ContextVar
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import importlib
import json
import os
import pickle
from pathlib import Path
import re
import stat
import sys
import tempfile
import time
import uuid

PM_SCRIPTS = Path(__file__).resolve().parents[2] / "synthesis-project-management/scripts"
if str(PM_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(PM_SCRIPTS))
resolve_plan_target = importlib.import_module("plan_reference").resolve_plan_target
_admission = importlib.import_module("run_admission")
admit_paths = _admission.admit_paths
admission_scope = _admission.admission_scope
bounded_lock = _admission.bounded_lock
inspect_paths = _admission.inspect_paths
native_binding = _admission.native_binding
reconcile_readback = _admission.reconcile_readback
safe_path = _admission.safe_path
observer_native_identity = importlib.import_module("project_state").observer_native_identity
coordination = importlib.import_module("coordination")
journal_storage = importlib.import_module("journal_storage")

SCHEMA = 1
VERIFIER_VERSION = "run-state-1"
TERMINAL = frozenset({"completed", "incomplete", "cancelled"})
STATUSES = TERMINAL | {"preparing", "running", "waiting_external", "waiting_user", "recovering", "verifying"}
MAX_JSON_BYTES = 4 * 1024 * 1024
MAX_EVENTS = 10000
MAX_HANDOFF_SECONDS = 3600
_COMMANDS = {}
_PREPARERS = {}
_VERIFIERS = {}
_CONSTRAINTS = {}
_TERMINAL_COMMANDS = set()
_EVIDENCE_SOURCES = {}
_OBSERVERS = {}
_ACCEPTANCE = {}
REQUEST_OPERATIONS = frozenset({"start", "next", "record", "checkpoint", "explain", "cancel", "recover", "finish", "successor"})
MAX_INPUT_BYTES = 256 * 1024


class RunStateError(ValueError):
    pass


def _json(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()
    except (TypeError, ValueError) as exc:
        raise RunStateError("run data must be finite JSON") from exc


def _digest(value):
    return hashlib.sha256(_json(value)).hexdigest()


def _request_binding(value):
    """Request metadata binds replay; it never supplies action authority."""
    if value is None:
        return None
    fields = {"request_id", "request_digest", "operation", "step", "initial_revision"}
    if (not isinstance(value, dict) or set(value) != fields
            or value["operation"] not in REQUEST_OPERATIONS
            or not isinstance(value["request_digest"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", value["request_digest"])
            or type(value["initial_revision"]) is not int or value["initial_revision"] < 0):
        raise RunStateError("invalid controller request binding")
    _id(value["request_id"], "request ID")
    _id(value["step"], "request step")
    return deepcopy(value)


def _check_request(state, binding):
    if binding is None:
        return
    saved = state.get("extensions", {}).get("controller", {}).get("requests", {}).get(binding["request_id"])
    if saved is not None:
        if any(saved.get(key) != binding[key] for key in ("request_digest", "operation", "initial_revision")):
            raise RunStateError("request ID was already used with different input")
    elif binding["initial_revision"] != state["revision"]:
        raise RunStateError("new request does not bind its initial revision")


def _record_request(state, binding, command_id, command_digest):
    if binding is None:
        return
    controller = state.setdefault("extensions", {}).setdefault("controller", {"schema_version": 1})
    requests = controller.setdefault("requests", {})
    if len(requests) >= MAX_EVENTS and binding["request_id"] not in requests:
        raise RunStateError("controller request journal capacity reached")
    entry = requests.setdefault(binding["request_id"], {
        key: binding[key] for key in ("request_digest", "operation", "initial_revision")})
    steps = entry.setdefault("steps", {})
    step = {"command_id": command_id, "revision": state["revision"], "command_digest": command_digest}
    if binding["step"] in steps and steps[binding["step"]] != step:
        raise RunStateError("request step identity already has a committed effect")
    steps[binding["step"]] = step


def _input_bytes(value):
    if (not isinstance(value, dict) or type(value.get("schema_version")) is not int
            or value["schema_version"] not in {1, 2}):
        raise RunStateError("managed input requires a typed schema 1 or 2 JSON object")
    pending = [(value, 0)]
    nodes = 0
    while pending:
        item, depth = pending.pop()
        nodes += 1
        if depth > 32 or nodes > 32768:
            raise RunStateError("managed input exceeds depth or node bound")
        if isinstance(item, dict):
            if len(item) > 1024 or any(not isinstance(key, str) for key in item):
                raise RunStateError("managed input has invalid object keys")
            pending.extend((key, depth + 1) for key in item)
            pending.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            if len(item) > 4096:
                raise RunStateError("managed input exceeds array bound")
            pending.extend((child, depth + 1) for child in item)
        elif isinstance(item, str):
            try:
                if len(item.encode("utf-8")) > MAX_INPUT_BYTES:
                    raise RunStateError("managed input string exceeds size bound")
            except UnicodeError as exc:
                raise RunStateError("managed input has invalid Unicode") from exc
        elif item is not None and type(item) not in {bool, int, float}:
            raise RunStateError("managed input must be finite JSON")
    raw = _json(value) + b"\n"
    if len(raw) > MAX_INPUT_BYTES:
        raise RunStateError("managed input exceeds size bound")
    return raw


def _now():
    return datetime.now(timezone.utc).isoformat()


def _time(value):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("timezone required")
        return parsed
    except (TypeError, AttributeError, ValueError) as exc:
        raise RunStateError("evidence timestamps must be timezone-aware ISO timestamps") from exc


def _id(value, label="id"):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}", value):
        raise RunStateError(f"invalid {label}")
    return value


def _uuid(value):
    try:
        if str(uuid.UUID(value)) != value:
            raise ValueError("noncanonical")
    except (ValueError, TypeError, AttributeError) as exc:
        raise RunStateError("run/owner identity must be a canonical UUID") from exc
    return value


def _install_input(path, raw):
    """Install immutable bounded bytes through no-follow directory handles."""
    path = Path(path)
    descriptor = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    staged = None
    try:
        for part in path.parent.parts[1:]:
            if part == "inputs":
                try:
                    os.mkdir(part, 0o700, dir_fd=descriptor)
                except FileExistsError:
                    pass
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        def existing():
            fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=descriptor)
            with os.fdopen(fd, "rb") as stream:
                before = os.fstat(stream.fileno())
                if not stat.S_ISREG(before.st_mode) or before.st_size != len(raw):
                    raise RunStateError("digest-addressed managed input bytes changed")
                if stream.read(MAX_INPUT_BYTES + 1) != raw:
                    raise RunStateError("digest-addressed managed input bytes changed")
                present = path.lstat()
                if (present.st_dev, present.st_ino) != (before.st_dev, before.st_ino):
                    raise RunStateError("managed input path changed during materialization")
        try:
            existing()
            return
        except FileNotFoundError:
            pass
        staged = ".stage-" + uuid.uuid4().hex
        fd = os.open(staged, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=descriptor)
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(staged, path.name, src_dir_fd=descriptor, dst_dir_fd=descriptor, follow_symlinks=False)
            os.fsync(descriptor)
        except FileExistsError:
            pass  # Concurrent install must have the same exact bytes.
        existing()
    finally:
        if staged is not None:
            try:
                os.unlink(staged, dir_fd=descriptor)
            except FileNotFoundError:
                pass
        os.close(descriptor)


def _read(path, *, _identities=None):
    if _identities is None:
        scope = _HISTORY_OPERATION.get()
        if scope:
            for history in scope.values():
                if history["paths"] and Path(path) == history["paths"][-1]:
                    _fence_history(history)
                    return deepcopy(history["last"])
    try:
        raw = journal_storage.read_regular(path, MAX_JSON_BYTES, _identities=_identities)
        value = json.loads(raw, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))
        return journal_storage.decode(path, value, _identities=_identities)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise RunStateError(f"unreadable state at {path}: {exc}") from exc


def _snapshot_bytes(path, value):
    """Pure physical rendering shared with the attribution owner."""
    raw, blocks = journal_storage.encode(value)
    return {**journal_storage.block_paths(journal_storage.home_for(path), blocks), Path(path): raw}


def _retained_snapshot_bytes(path, value):
    """Derive existing storage form without rewriting admitted historical bytes."""
    return journal_storage.retained_snapshot_bytes(path, value, max_bytes=MAX_JSON_BYTES)


def _write(path, raw):
    """Durable atomic replace; callers serialize with the owning lock."""
    path = Path(path)
    if path.is_symlink() or path.parent.is_symlink():
        raise RunStateError("unsafe projection/event path")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".run-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _home(project, run_id):
    project = Path(project).resolve(strict=True)
    return safe_path(project / "resources/autopilot-runs" / _uuid(run_id), project)


def _runtime(runtime_root=None):
    root = Path(runtime_root) if runtime_root is not None else Path.home() / ".synthesis/autopilot"
    root = root.expanduser().absolute()
    # A non-existent leaf is permitted, but every existing component must be a
    # directory rather than a symlink. OS aliases above a provided root should
    # be normalized by the caller (the default home is already canonical).
    cursor = root
    while cursor != cursor.parent:
        if cursor.is_symlink():
            raise RunStateError("runtime discovery path crosses a symlink")
        cursor = cursor.parent
    return root


def _index_path(runtime_root, owner):
    return _runtime(runtime_root) / "owners" / f"{_uuid(owner)}.json"


def _index_read(path, owner):
    if not path.exists():
        return {"schema_version": SCHEMA, "owner": owner, "runs": {}}
    result = _read(path)
    if not isinstance(result, dict) or result.get("schema_version") != SCHEMA or result.get("owner") != owner or not isinstance(result.get("runs"), dict):
        raise RunStateError("owned run index has unsupported or invalid schema")
    return result


def _index_update(runtime_root, owner, run_id, entry):
    path = _index_path(runtime_root, owner)
    with bounded_lock(path.with_suffix(".lock")):
        index = _index_read(path, owner)
        index["runs"][run_id] = entry
        _write(path, _json(index) + b"\n")


def _native_index_path(runtime_root, client, native):
    _uuid(native)
    return _runtime(runtime_root) / "native-owners" / (hashlib.sha256(f"{client}:{native}".encode()).hexdigest() + ".json")


def _native_index_read(path, client, native):
    if not path.exists():
        return {"schema_version": SCHEMA, "client": client, "native_session_id": native, "owners": []}
    value = _read(path)
    if not isinstance(value, dict) or value.get("schema_version") != SCHEMA or value.get("client") != client or value.get("native_session_id") != native or not isinstance(value.get("owners"), list):
        raise RunStateError("native owner index is invalid")
    for owner in value["owners"]:
        _uuid(owner)
    return value


def _native_index_update(runtime_root, proof):
    client, native = proof["client"], proof["native_session_id"]
    path = _native_index_path(runtime_root, client, native)
    with bounded_lock(path.with_suffix(".lock")):
        index = _native_index_read(path, client, native)
        index["owners"] = sorted(set(index["owners"]) | {proof["session_uuid"]})
        _write(path, _json(index) + b"\n")


def _index_entry(project, state, status=None):
    return {"project": str(Path(project).resolve()), "project_id": state["project_id"],
            "run_id": state["run_id"], "status": status or state["status"]}


def _contract(value):
    if not isinstance(value, dict) or value.get("schema_version") != SCHEMA:
        raise RunStateError("completion contract requires schema_version 1")
    allowed = {"schema_version", "scope", "exclusions", "outcomes", "criteria", "authority_refs"}
    if set(value) - allowed:
        raise RunStateError("unknown completion contract fields")
    for key in ("scope", "exclusions", "authority_refs"):
        if not isinstance(value.get(key), list) or not all(isinstance(item, str) and item.strip() for item in value[key]):
            raise RunStateError(f"contract {key} must be a list of nonempty strings")
    if not value["scope"] or not isinstance(value.get("criteria"), list) or not value["criteria"] or not isinstance(value.get("outcomes"), list) or not value["outcomes"]:
        raise RunStateError("contract must cover a nonempty scope, outcomes, and criteria")
    ids = set()
    for item in value["criteria"]:
        if not isinstance(item, dict) or _id(item.get("id")) in ids:
            raise RunStateError("criterion IDs must be unique")
        ids.add(item["id"])
        if not isinstance(item.get("description"), str) or not item["description"].strip() or type(item.get("required")) is not bool:
            raise RunStateError("criteria require a description and explicit required boolean")
        _id(item.get("method"), "criterion method")
        for field in ("artifact_ids", "evidence_ids"):
            refs = item.get(field, [])
            if not isinstance(refs, list) or not all(isinstance(ref, str) and _id(ref) for ref in refs):
                raise RunStateError("criterion references must be ID lists")
        if item["required"] and not item.get("artifact_ids") and not item.get("evidence_ids"):
            raise RunStateError("required criterion needs concrete artifact or evidence inputs")
    covered, outcomes = set(), set()
    for item in value["outcomes"]:
        if not isinstance(item, dict) or _id(item.get("id")) in outcomes:
            raise RunStateError("outcome IDs must be unique")
        outcomes.add(item["id"])
        refs = item.get("criteria")
        if not isinstance(refs, list) or not refs or not all(ref in ids for ref in refs):
            raise RunStateError("each outcome must reference declared criteria")
        covered.update(refs)
    if ids != covered or not any(item["required"] for item in value["criteria"]):
        raise RunStateError("every criterion must belong to an outcome; at least one must be required")
    return deepcopy(value)


def _profile(value):
    if not isinstance(value, dict) or value.get("schema") != SCHEMA or not isinstance(value.get("items"), list):
        raise RunStateError("profile must be a schema 1 effective checklist")
    ids = set()
    for item in value["items"]:
        if not isinstance(item, dict) or _id(item.get("id")) in ids:
            raise RunStateError("profile item IDs must be unique")
        ids.add(item["id"])
        if "required" in item and type(item["required"]) is not bool:
            raise RunStateError("profile required must be boolean")
        if "criterion_ids" in item and (not isinstance(item["criterion_ids"], list) or not item["criterion_ids"]):
            raise RunStateError("profile criterion mapping cannot be empty")
    grant = value.get("deploy_grant")
    if grant not in (None, "none") and grant != {"text": "none", "provenance": "none"}:
        raise RunStateError("profiles cannot grant action authority; use existing action-owner approval references")
    return deepcopy(value)


def _plan(project, target):
    reference = resolve_plan_target(Path(project), str(target))
    if reference.resolved is None:
        raise RunStateError(reference.detail)
    return reference


def _plan_digest(project, state, *, admitted_path=None, repository=None):
    # _binding has already resolved/admitted this exact plan in the current
    # operation. Recheck path safety without repeating Git root discovery.
    path = (_plan(project, state["plan"]).resolved if admitted_path is None else
            safe_path(Path(admitted_path), Path(repository)))
    from required_citations import plan_text_digest
    return plan_text_digest(path.read_text(encoding="utf-8"))


def _binding(project, state, actor, *, readonly=False, passive=False):
    if not isinstance(actor, dict) or set(actor) != {"board", "native_payload"}:
        raise RunStateError("actor requires board and native_payload only")
    home = _home(project, state["run_id"])
    plan = _plan(project, state["plan"]).resolved
    arguments = (Path(actor["board"]), state["project_id"], Path(project),
                 [home, plan, _plan_lock(project, plan)], actor["native_payload"])
    if passive and not readonly:
        raise RunStateError("passive Stop inspection cannot authorize mutation")
    proof = inspect_paths(*arguments) if passive else admit_paths(*arguments, readonly=readonly)
    owner = state.get("owner")
    if owner is not None and (proof["session_uuid"], proof["native_ref"]) != (owner["session_uuid"], owner["native_ref"]):
        raise RunStateError("native actor is not this run's current owner")
    active = _active_native(state)
    if active is not None and active.get("schema_version") == 2 and proof["board"] != active["owner"]["board"]:
        raise RunStateError("pending native custody requires its original coordination board")
    return proof


def _handoff_snapshot(state):
    # Every durable obligation, including extension/workflow state, is bound.
    return _digest({key: value for key, value in state.items()
                    if key not in {"handoff", "revision", "updated_at"}})


def _pending_handoff(project, state, payload):
    _fields(payload, {"id"}, {"id"})
    intent = state.get("handoff")
    if not intent or intent["status"] != "pending" or payload["id"] != intent["id"]:
        raise RunStateError("matching pending handoff intent is required")
    if (_time(intent["expires_at"]) <= _time(_now()) or state["revision"] != intent["prepared_revision"]
            or _handoff_snapshot(state) != intent["state_digest"]
            or _plan_digest(project, state) != intent["plan_digest"]):
        raise RunStateError("handoff intent expired or its bound run/plan changed")
    return intent


def _command_binding(project, state, actor, command, payload):
    if command == "owner.resume":
        # This is same-native seat renewal only. A different native owner still
        # needs the predecessor's two-phase transfer, never this recovery seam.
        if any(
                row.get("request_digest") == _digest(payload)
                and row.get("target", {}).get("session_uuid") == state["owner"]["session_uuid"]
                for row in state.get("ownership_recoveries", [])):
            return _binding(project, state, actor)  # Exact replay is checked below.
        proof = _resume_binding(project, state, actor, payload)
        return proof
    if command != "owner.transfer.accept" or state.get("handoff", {}).get("status") == "accepted":
        return _binding(project, state, actor)
    intent = _pending_handoff(project, state, payload)
    if not isinstance(actor, dict) or set(actor) != {"board", "native_payload"}:
        raise RunStateError("actor requires board and native_payload only")
    if str(Path(actor["board"]).expanduser().absolute()) != intent["board"]:
        raise RunStateError("handoff acceptance requires the same coordination board")
    # Only this command may admit the named target while the committed owner
    # remains the predecessor. PM still enforces the target's exclusive claim.
    proof = _binding(project, {**state, "owner": intent["target"]}, actor)
    for key in ("project_id", "project_root", "repository", "branch"):
        if proof[key] != state["owner"][key]:
            raise RunStateError("handoff target changed the project or workspace binding")
    return proof


def _resume_user_message(actor, proof, spec, released_at, *, resume_scope=None):
    """Observe native root-user text or a bound UI answer; never manufacture approval.

    Source/type/currentness are mechanical facts. Interpreting the user's prose
    remains the admitted agent's responsibility. This observation cannot clear
    a wait, amend authority, or rearm a cancelled run.
    """
    import native_observations as native
    from html.parser import HTMLParser

    class MarkupRegions(HTMLParser):
        """Conservative exclusion of HTML containers and pending markup."""
        def __init__(self):
            super().__init__(convert_charrefs=False)
            self.stack, self.seen = [], False

        def handle_starttag(self, tag, attrs):
            self.seen = True
            if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
                self.stack.append(tag)

        def handle_startendtag(self, tag, attrs):
            self.seen = True

        def handle_endtag(self, tag):
            self.seen = True
            if self.stack and self.stack[-1] == tag:
                self.stack.pop()

        def handle_comment(self, data):
            self.seen = True
    if isinstance(spec, dict) and set(spec) == {"delegation"}:
        from native_review import observe_codex_resume_delegation
        client, identity = observer_native_identity(actor["native_payload"])
        if client != "codex" or (client, identity) != (proof["client"], proof["native_session_id"]):
            raise RunStateError("resume delegation requires this exact native Codex recipient")
        binding, _ = native.enroll_source(actor["native_payload"]["transcript_path"], client=client,
            expected_root_session_id=identity, expected_thread_id=identity, source_handle="owner-resume", mode="native")
        delivery = observe_codex_resume_delegation(binding, spec["delegation"], resume_scope)
        source = delivery["pointer"]["source_native_payload"]
        try:
            source_client, source_id = observer_native_identity(source)
        except (RuntimeError, OSError, TypeError, AttributeError) as exc:
            raise RunStateError("resume delegation human source cannot be authenticated") from exc
        if source_client != "codex" or source_id != delivery["source_thread_id"]:
            raise RunStateError("resume delegation human source changed native identity")
        message = _resume_user_message({"native_payload": source},
            {"client": source_client, "native_session_id": source_id},
            delivery["pointer"]["user_message"], released_at)
        if not (_time(message["native_timestamp"]) <= _time(delivery["native_timestamp"])
                <= _time(delivery["completed_at"]) <= _time(_now())):
            raise RunStateError("resume delegation must follow the human answer and not be future dated")
        return {**deepcopy(spec), "path": binding["path"], "generation": binding["generation"],
            "native_timestamp": message["native_timestamp"], "human_source": message,
            "delivery": delivery, "scope": "Observed native delivery of exact human evidence; no permission transfer or action grant",
            "authority_granted": False}
    _fields(spec, {"offset", "length", "sha256", "excerpt", "question"}, {"offset", "length", "sha256", "excerpt"})
    if (type(spec["offset"]) is not int or spec["offset"] < 0 or type(spec["length"]) is not int
            or not 0 < spec["length"] <= native.Limits().payload_bytes
            or not isinstance(spec["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", spec["sha256"])
            or not isinstance(spec["excerpt"], str) or not 0 < len(spec["excerpt"]) <= 4096):
        raise RunStateError("resume requires a bounded exact native user locator and excerpt")
    client, identity = observer_native_identity(actor["native_payload"])
    if (client, identity) != (proof["client"], proof["native_session_id"]):
        raise RunStateError("resume user source changed native identity")
    path = actor["native_payload"].get("transcript_path")
    if client == "muse":
        from live_receipt import resolve_muse_transcript
        path = resolve_muse_transcript(identity)
    if not path:
        raise RunStateError("resume user source is unavailable")
    binding, _ = native.enroll_source(path, client=client, expected_root_session_id=identity,
        expected_thread_id=identity, source_handle="owner-resume", mode="native")
    stream, info = native._open(binding["path"], binding)
    with stream:
        native._header(stream, binding, info.st_size)
        if spec["offset"] and native._stable_read(stream, binding["path"], spec["offset"] - 1, 1,
                (binding["device"], binding["inode"]), info.st_size) != b"\n":
            raise RunStateError("resume user locator is not a record boundary")
        raw = native._stable_read(stream, binding["path"], spec["offset"], spec["length"],
            (binding["device"], binding["inode"]), info.st_size)
    if hashlib.sha256(raw).hexdigest() != spec["sha256"] or not raw.endswith(b"\n") or raw.count(b"\n") != 1:
        raise RunStateError("resume user source bytes or record framing changed")
    row = native._json(raw)
    if any(row.get(key, False) is not False for key in ("isMeta", "isSidechain")):
        raise RunStateError("generated or child user records cannot renew an owner")
    events = native._events(row, binding, spec["offset"], spec["length"], spec["sha256"], 0)
    if not events or any(event["kind"] != "message.user" for event in events):
        raise RunStateError("resume locator is not a direct native root-user record")
    times = {_time(event["native_timestamp"]) for event in events}
    if any(moment <= _time(released_at) or moment > _time(_now()) for moment in times):
        raise RunStateError("resume user evidence must follow the previous release and not be future dated")
    # Use explicit textual content only: no serialized tool input, peer output,
    # metadata, recursively discovered strings, or opaque future client payload.
    if client == "claude":
        message = row.get("message", {})
        if message.get("role") != "user":
            raise RunStateError("resume record has no explicit user role")
        content = message.get("content")
    elif client == "codex":
        value = row.get("payload", {})
        content = value.get("message") if row.get("type") == "event_msg" else value.get("content")
    else:
        # The current Muse raw adapter identifies accepted user intents, but its
        # opaque intent bodies are not a text-custody contract. Refuse until that
        # client provides a qualified direct-user text reader.
        raise RunStateError("native client has no qualified direct-user text reader for owner renewal")
    texts = [content] if isinstance(content, str) else [block["text"] for block in content or []
        if isinstance(block, dict) and block.get("type") in {"text", "input_text"} and isinstance(block.get("text"), str)]
    if "question" in spec:
        if client != "codex":
            raise RunStateError("native client has no qualified asynchronous user-question reader")
        from native_review import observe_codex_question
        question = observe_codex_question(binding, spec)
        return {**deepcopy(spec), "path": binding["path"], "generation": binding["generation"],
            "native_timestamp": min(times).isoformat(), "event_ids": [event["event_id"] for event in events],
            "decision": question,
            "scope": "Native root-user answer to the exact question; interpretation is the admitted agent's recorded judgment",
            "authority_granted": False}
    paragraphs = []
    for text in texts:
        if any(marker in text for marker in ("<hook_prompt", "<heartbeat", "<send_user_message_question_reply")):
            raise RunStateError("injected lifecycle feedback is not direct-user restart evidence")
        current, fence, quoted_paragraph = [], None, False
        markup = MarkupRegions()
        for line in text.splitlines() + [""]:
            stripped = line.strip()
            expanded = line.expandtabs(4)
            # A fence is closed only by the same character, at least its
            # opening length, no more than three leading spaces, and no info
            # suffix. Other marker runs remain quoted contents, not toggles.
            if fence is not None:
                char, length = fence
                if re.fullmatch(r" {0,3}" + re.escape(char) + "{" + str(length) + r",}[ \t]*", expanded):
                    fence = None
                continue
            # Markdown permits lazy continuation lines inside block quotes.
            # A missing '>' on the next line does not make it user prose.
            if not stripped:
                quoted_paragraph = False
            elif stripped.startswith(">"):
                quoted_paragraph = True
            if quoted_paragraph:
                if current:
                    paragraphs.append("\n".join(current).strip())
                    current = []
                continue
            opening = re.fullmatch(r" {0,3}(`{3,}|~{3,})(.*)", expanded)
            if opening and (opening[1][0] != "`" or "`" not in opening[2]):
                fence = (opening[1][0], len(opening[1]))
                if current:
                    paragraphs.append("\n".join(current).strip())
                    current = []
                continue
            # Indented code remains data. Expand tabs using Markdown's four
            # column stops; stripping first would erase this provenance.
            indented = expanded.startswith("    ")
            in_markup = bool(markup.stack or markup.rawdata)
            markup.seen = False
            if not indented:
                markup.feed(line + "\n")
                in_markup = in_markup or bool(markup.stack or markup.rawdata or markup.seen)
            if not stripped or indented or in_markup or stripped.startswith((">", "<", "```", "~~~")):
                if current:
                    paragraphs.append("\n".join(current).strip())
                    current = []
                continue
            current.append(line)
    if spec["excerpt"] not in paragraphs:
        raise RunStateError("resume excerpt must be an exact unquoted direct-user paragraph")
    return {**deepcopy(spec), "path": binding["path"], "generation": binding["generation"],
        "native_timestamp": min(times).isoformat(), "event_ids": [event["event_id"] for event in events],
        "scope": "Native root-user text provenance; interpretation is the admitted agent's recorded judgment",
        "authority_granted": False}


def _resume_binding(project, state, actor, payload):
    required = {"previous_owner", "basis_revision", "basis_digest", "plan_digest", "user_message", "reason"}
    _fields(payload, required | {"restart_wait"}, required)
    prior = payload["previous_owner"]
    if (not isinstance(prior, dict) or set(prior) != {"session_uuid", "native_ref"}
            or prior != {key: state["owner"][key] for key in prior}
            or type(payload["basis_revision"]) is not int or payload["basis_revision"] != state["revision"]
            or payload["basis_digest"] != _digest(state) or payload["plan_digest"] != _plan_digest(project, state)
            or not isinstance(payload["reason"], str) or not 0 < len(payload["reason"].strip()) <= 4096):
        raise RunStateError("owner renewal requires the exact previous owner, state, plan and recorded interpretation")
    if state["status"] in TERMINAL or state.get("handoff", {}).get("status") == "pending":
        raise RunStateError("terminal runs or pending native transfers cannot use owner renewal")
    if not isinstance(actor, dict) or set(actor) != {"board", "native_payload"} or str(Path(actor["board"]).expanduser().absolute()) != state["owner"]["board"]:
        raise RunStateError("owner renewal requires the original coordination board")
    if observer_native_identity(actor["native_payload"]) != (state["owner"]["client"], state["owner"]["native_session_id"]):
        raise RunStateError("owner renewal requires the same native session; different native owners require prepared transfer")
    # Finish authoritative predecessor and native-source observations before
    # issuing PM's short-lived, unused mutation proof. A network lease read
    # after issuance can spend that proof's lifetime; a passive stamp is not an
    # authority substitute. Missing/archived predecessors still cannot resume.
    from run_admission import _snapshot
    board = Path(actor["board"])
    board_snapshot = _snapshot(board)
    rows = coordination.rows(board_snapshot)
    previous = coordination.find_session(rows, prior["session_uuid"])
    if (previous is None or previous.status.lower() not in coordination.TERMINAL_STATUSES
            or previous.client_ref != prior["native_ref"] or previous.project != state["project_id"]
            or previous.machine != state["owner"]["machine"]):
        raise RunStateError("previous exact native seat has no current terminal proof")
    resume_scope = {"run_id": state["run_id"], "project_id": state["project_id"],
        "recipient_native_ref": state["owner"]["native_ref"],
        **{key: deepcopy(payload[key]) for key in ("previous_owner", "basis_revision", "basis_digest", "plan_digest")},
        "restart_wait": deepcopy(payload.get("restart_wait"))}
    message = _resume_user_message(actor, state["owner"], payload["user_message"], previous.heartbeat,
        resume_scope=resume_scope)
    restart_wait = payload.get("restart_wait")
    if restart_wait is not None:
        _fields(restart_wait, {"id", "sha256"}, {"id", "sha256"})
        wait = state["waits"].get(restart_wait["id"])
        if (state["status"] != "waiting_user" or not wait or wait.get("kind") != "user"
                or wait.get("status") != "pending" or _digest(wait) != restart_wait["sha256"]
                or _time(message["native_timestamp"]) <= _time(wait["at"])):
            raise RunStateError("restart acknowledgment requires the exact pending user wait and a later native user message")
    proof = _binding(project, {**state, "owner": None}, actor)
    if proof["session_uuid"] == prior["session_uuid"] or any(proof[key] != state["owner"][key] for key in
            ("native_ref", "client", "native_session_id", "machine", "project_id", "project_root", "repository", "branch")):
        raise RunStateError("owner renewal requires a new exclusive seat for the same native session and project")
    # The just-issued proof re-fenced PM's authoritative board. Match its local
    # mirror to the predecessor observation without another network operation;
    # changed evidence refuses rather than renewing or extending a stale proof.
    if board.is_symlink() or board.parent.is_symlink() or board.read_text(encoding="utf-8") != board_snapshot:
        raise RunStateError("coordination predecessor changed during owner renewal")
    proof._owner_resume_observation = {"previous": deepcopy(prior),
        "target": {key: proof[key] for key in ("session_uuid", "native_ref")},
        "previous_status": previous.status, "released_at": previous.heartbeat,
        "basis_revision": state["revision"], "basis_digest": payload["basis_digest"],
        "plan_digest": payload["plan_digest"], "user_message": message,
        "interpretation": payload["reason"], "request_digest": _digest(payload),
        "authority_granted": False, "restart_wait": deepcopy(restart_wait),
        "waits_resolved": [restart_wait["id"]] if restart_wait else [], "effects_replayed": False}
    return proof


def _event_paths(project, run_id):
    home = _home(project, run_id)
    directory = safe_path(home / "events", Path(project).resolve())
    if not directory.is_dir():
        raise RunStateError("run has no committed events")
    # Bound physical enumeration before materialization, including interrupted
    # staging entries. Staging is retained evidence, not an unlimited allowance.
    files = []
    enumeration_deadline = time.monotonic() + MAX_SUCCESSOR_SECONDS
    before = directory.lstat()
    fields = ("st_dev", "st_ino", "st_mode", "st_mtime_ns", "st_ctime_ns")
    def signature(info):
        return tuple(getattr(info, key) for key in fields)
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        if signature(before) != signature(os.fstat(fd)):
            raise RunStateError("event directory changed before enumeration")
        # Path.iterdir uses os.listdir on supported Python versions. scandir
        # streams from this verified descriptor instead of allocating all names.
        with os.scandir(fd) as entries:
            for count, entry in enumerate(entries, 1):
                if count > MAX_EVENTS or time.monotonic() > enumeration_deadline:
                    raise RunStateError("event directory exceeds the bounded enumeration limit")
                if not entry.name.startswith(".run-"):
                    files.append(directory / entry.name)
        if signature(before) != signature(os.fstat(fd)) or signature(before) != signature(directory.lstat()):
            raise RunStateError("event directory changed during enumeration")
    finally:
        os.close(fd)
    files.sort()
    if not files or len(files) > MAX_EVENTS:
        raise RunStateError("event stream is empty or exceeds supported replay limit")
    return files


def _check_event(event, run_id, revision, previous, previous_codec, commands):
    if not isinstance(event, dict):
        raise RunStateError("event must be an object")
    digest = event.get("digest")
    body = {key: value for key, value in event.items() if key != "digest"}
    body_digest = event.verified_body_digest if isinstance(event, journal_storage.DecodedEvent) else _digest(body)
    if digest != body_digest or event.get("previous_digest") != previous or event.get("revision") != revision or event.get("schema_version") != SCHEMA:
        raise RunStateError("event chain failed integrity/schema validation")
    state = event.get("state")
    if not isinstance(state, dict) or state.get("schema_version") != SCHEMA or state.get("run_id") != run_id or state.get("revision") != revision or state.get("status") not in STATUSES:
        raise RunStateError("event state identity is invalid")
    codec = journal_storage.codec_for(state)
    if codec < previous_codec:
        raise RunStateError("journal storage codec regressed within authenticated history")
    previous_codec = codec
    if event.get("command_id") in commands:
        raise RunStateError("event stream contains duplicate command IDs")
    commands.add(event["command_id"])
    return digest, codec


def _events(project, run_id, *, verify_successor=True):
    files = _event_paths(project, run_id)
    previous = ""
    previous_codec = 1
    initial_state = None
    commands = set()
    for revision, path in enumerate(files, 1):
        if path.name != f"{revision:012d}.json":
            raise RunStateError("event sequence has a gap or unexpected entry")
        event = _read(path)
        digest, previous_codec = _check_event(event, run_id, revision, previous, previous_codec, commands)
        previous = digest
        state = event["state"]
        if revision == 1:
            initial_state = state
        yield event
    if verify_successor and initial_state.get("successor"):
        if state.get("successor") != initial_state["successor"]:
            raise RunStateError("successor lineage changed within its journal")
        parents = _successor_chain(project, initial_state["successor"]["predecessor"], time.monotonic() + MAX_SUCCESSOR_SECONDS)
        _successor_inheritance(initial_state, parents[0])


_HISTORY_OPERATION = ContextVar("run_state_history_operation", default=None)


@contextmanager
def journal_operation():
    """Reuse verified history only during this bounded controller invocation.

    No admission proof is retained. All entry reads are cold; every reuse fences
    the exact regular files and physical ancestor identities observed by those
    reads. The private latest snapshot and bounded revision metadata never leave
    this scope. Nested owners share its lifetime, never extend it.
    """
    existing = _HISTORY_OPERATION.get()
    if existing is not None:
        yield
        return
    token = _HISTORY_OPERATION.set({})
    try:
        with journal_storage.compilation_scope():
            yield
    finally:
        _HISTORY_OPERATION.reset(token)


def _fence_history(retained):
    groups = {}
    for path, identity in retained["files"].items():
        groups.setdefault(path.parent, []).append((path.name, identity))
    fields = ("st_dev", "st_ino", "st_mode", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns")
    for parent, entries in groups.items():
        fd = journal_storage._safe_directory(parent)
        try:
            if parent.name == "v1" and parent.parent.name == "state-blocks":
                journal_storage._lock_store(fd, exclusive=False)
            for name, identity in entries:
                current = os.stat(name, dir_fd=fd, follow_symlinks=False)
                if not stat.S_ISREG(current.st_mode) or tuple(getattr(current, key) for key in fields) != identity:
                    raise RunStateError("verified journal file changed during operation")
            journal_storage._same_directory(parent, fd)
        finally:
            os.close(fd)
    # Include all physical ancestors, not just the two immediate store dirs.
    for path, identity in retained["ancestors"].items():
        current = path.lstat()
        if (not stat.S_ISDIR(current.st_mode)
                or (current.st_dev, current.st_ino, current.st_mode) != identity):
            raise RunStateError("verified journal ancestor changed during operation")


def _history_metadata(event):
    state = event["state"]
    return {key: event[key] for key in ("revision", "digest", "command", "command_id", "command_digest")} | {
        "state_digest": _digest(state), "codec": journal_storage.codec_for(state),
        "contract_revision": state["contract_revision"], "contract_digest": state["contract_digest"],
        "profile_revision": state["profile_revision"], "profile_digest": state["profile_digest"]}


def _verified_history(project, run_id):
    """Return a verified head and compact history, with fresh physical fences."""
    scope = _HISTORY_OPERATION.get()
    if scope is None:
        return None  # Cold consumers retain the original streaming owner.
    key = (str(Path(project).resolve(strict=True)), run_id)
    retained = scope.pop(key, None)
    # A refused extension cannot leave a partial cache available to a caught
    # retry. Publish the complete observation only after every final fence.
    scope.clear()
    paths = _event_paths(project, run_id)
    if retained is not None:
        _fence_history(retained)
        if paths[:len(retained["paths"])] != retained["paths"]:
            raise RunStateError("verified journal prefix changed during operation")
    else:
        retained = {"paths": [], "rows": [], "files": {}, "ancestors": {}, "last": None}
        # Pin ancestry before the first read; recording it only afterward could
        # adopt a directory replacement that moved the same files beneath it.
        for ancestor in (paths[0].parent, *paths[0].parents):
            info = ancestor.lstat()
            if not stat.S_ISDIR(info.st_mode):
                raise RunStateError("journal ancestor is not a directory")
            retained["ancestors"][ancestor] = (info.st_dev, info.st_ino, info.st_mode)
    previous = retained["rows"][-1]["digest"] if retained["rows"] else ""
    codec = retained["rows"][-1]["codec"] if retained["rows"] else 1
    commands = {row["command_id"] for row in retained["rows"]}
    for path in paths[len(retained["paths"]):]:
        revision = len(retained["paths"]) + 1
        if path.name != f"{revision:012d}.json":
            raise RunStateError("event sequence has a gap or unexpected entry")
        identities = {}
        event = _read(path, _identities=identities)
        previous, codec = _check_event(event, run_id, revision, previous, codec, commands)
        # Successor ancestry is deliberately revalidated by its full existing
        # owner. It is not admitted by a cached metadata projection.
        if revision == 1 and event["state"].get("successor"):
            return None
        retained["rows"].append(_history_metadata(event))
        retained["paths"].append(path)
        retained["last"] = event
        for target, identity in identities.items():
            if target in retained["files"] and retained["files"][target] != identity:
                raise RunStateError("verified journal block changed during append")
            known = target in retained["files"]
            retained["files"][target] = identity
            if known:
                continue
            for ancestor in target.parents:
                info = ancestor.lstat()
                current = (info.st_dev, info.st_ino, info.st_mode)
                if not stat.S_ISDIR(info.st_mode) or (ancestor in retained["ancestors"] and retained["ancestors"][ancestor] != current):
                    raise RunStateError("verified journal ancestor changed during append")
                retained["ancestors"][ancestor] = current
        if (len(retained["files"]) > journal_storage.MAX_STORE_ENTRIES + MAX_EVENTS
                or len(_json(retained["rows"])) > MAX_JSON_BYTES):
            # Optional reuse cannot reduce the original streaming admission
            # domain. The caller falls back to its unchanged full cold owner.
            return None
    _fence_history(retained)
    if scope is not None:
        # One selected history per operation: unrelated reads cannot accumulate
        # decoded snapshots across projects or consume an unbounded cache.
        scope.clear()
        scope[key] = retained
    return retained


def _last_event(project, run_id):
    """Validate complete history and return an independent latest snapshot."""
    history = _verified_history(project, run_id)
    if history is not None:
        return _copy_state(history["last"])
    last = None
    for last in _events(project, run_id):
        pass
    return last


def load_run(project: Path, run_id: str) -> dict:
    """Read only the selected journal; projections and other runs confer no truth."""
    history = _verified_history(project, run_id)
    if history is None:
        last = None
        for last in _events(project, run_id):
            pass
    else:
        last = history["last"]
    return _copy_state(last["state"])


def _projection_bytes(project, state, plan_text, *, retain_storage=False):
    """Derive owned bytes; attribution can retain the committed storage form."""
    home = _home(project, state["run_id"])
    renderer = _retained_snapshot_bytes if retain_storage else _snapshot_bytes
    output = renderer(home / "current.json", state)
    summary = f"Run: {state['run_id']}\nRevision: {state['revision']}\nStatus: {state['status']}\n"
    summary += f"Contract: {state['contract_revision']} ({state['contract_digest']})\n"
    summary += f"Profile: {state['profile_revision']} ({state['profile_digest']})\n"
    if state.get("progress"):
        summary += "Progress: " + state["progress"]["summary"].replace("\n", " ") + "\n"
    output[home / "summary.md"] = ("# Autopilot run\n\n" + summary).encode()
    if state["status"] in TERMINAL:
        output[home / "terminal.json"] = _json({"schema_version": SCHEMA, "run_id": state["run_id"],
            "revision": state["revision"], "status": state["status"], "terminal": state["terminal"]}) + b"\n"
    start, end = (f"<!-- autopilot:{state['run_id']}:{edge} -->" for edge in ("start", "end"))
    block = start + "\n" + summary + end
    if plan_text.count(start) != plan_text.count(end) or plan_text.count(start) > 1:
        raise RunStateError("plan ledger markers are ambiguous; human repair required")
    if start in plan_text:
        plan_text = plan_text[:plan_text.index(start)] + block + plan_text[plan_text.index(end) + len(end):]
    else:
        plan_text = plan_text.rstrip() + "\n\n" + block + "\n"
    output[_plan(project, state["plan"]).resolved] = plan_text.encode()
    return output


def _project(project, state):
    plan = _plan(project, state["plan"]).resolved
    # Different runs share the plan lock; render preserves all other ledger
    # blocks and human prose. Attribution uses the same pure byte compiler.
    with bounded_lock(_plan_lock(project, plan)):
        rendered = _projection_bytes(project, state, plan.read_text(encoding="utf-8"))
        home = _home(project, state["run_id"])
        blocks = {path.stem: raw for path, raw in rendered.items() if path.parent == home / "state-blocks/v1"}
        journal_storage.materialize(home, blocks)
        for path, raw in rendered.items():
            if path.parent != home / "state-blocks/v1":
                _write(path, raw)


def _plan_lock(project, plan):
    key = hashlib.sha256(str(plan).encode()).hexdigest()[:24]
    return safe_path(Path(project).resolve() / "resources/autopilot-runs" / f".plan-{key}.lock", Path(project).resolve())


def rebuild_projections(project, run_id, *, actor):
    state = load_run(project, run_id)
    _binding(project, state, actor)
    with bounded_lock(_home(project, run_id) / ".run.lock"):
        state = load_run(project, run_id)
        _binding(project, state, actor)
        _project(project, state)
    return state


def replay_request_step(project, run_id, *, request_binding, actor, command=None):
    """Readmit and restore a committed facade prefix without repeating effects.

    The request binding is a replay key, never permission. The selected step's
    identity and command digest must still agree with the immutable journal.
    """
    binding = _request_binding(request_binding)
    if binding is None:
        raise RunStateError("request replay requires an exact binding")
    project = Path(project).resolve(strict=True)
    home = _home(project, run_id)
    with bounded_lock(home / ".run.lock", create=False):
        events = _events(project, run_id)
        selected = None
        last = None
        for event in events:
            last = event
            entry = event["state"].get("extensions", {}).get("controller", {}).get("requests", {}).get(binding["request_id"], {})
            step = entry.get("steps", {}).get(binding["step"])
            if step and step["revision"] == event["revision"]:
                selected = event
        state = deepcopy(last["state"])
        _binding(project, state, actor)
        _check_request(state, binding)
        step = state.get("extensions", {}).get("controller", {}).get("requests", {}).get(binding["request_id"], {}).get("steps", {}).get(binding["step"])
        if (not selected or not step or step["command_id"] != selected["command_id"]
                or step["command_digest"] != selected["command_digest"]
                or command is not None and selected["command"] != command):
            raise RunStateError("request step does not bind its committed journal event")
        if state["status"] not in TERMINAL:
            _project(project, state)
        return state


def _require_unlinked_predecessor(project, run_id):
    """A committed child fixes this exact parent head; pending hints do not."""
    child = _home(project, successor_identity(project, run_id))
    committed = safe_path(child / "events" / "000000000001.json", Path(project).resolve())
    try:
        committed.lstat()
    except FileNotFoundError:
        return
    raise RunStateError("committed successor makes the linked predecessor immutable")


def _append(project, state, command_id, command_digest, command, previous_digest, proof, *, prepared_authority=None):
    _require_unlinked_predecessor(project, state["run_id"])
    home = _home(project, state["run_id"])
    journal_storage.codec_for(state)  # Refuse malformed predecessor bindings.
    state.setdefault("extensions", {})["journal_storage"] = {"codec": 2}
    event = {"schema_version": SCHEMA, "revision": state["revision"], "previous_digest": previous_digest,
             "command_id": command_id, "command_digest": command_digest, "command": command,
             "actor": {key: proof[key] for key in ("session_uuid", "native_ref", "claim_hash")}, "state": state}
    if prepared_authority is not None:
        # A deterministic grant consumer is never represented as its native issuer.
        event["actor"] = {"kind": "prepared-native-launch", **deepcopy(prepared_authority)}
    event["digest"] = _digest(event)
    if state["revision"] > MAX_EVENTS:
        raise RunStateError("run exceeds the supported journal limits")
    path = home / "events" / f"{state['revision']:012d}.json"
    if path.exists():
        raise RunStateError("refusing to overwrite a committed event")
    with journal_storage.compilation_scope():
        raw, blocks = journal_storage.encode(event)
        _, projection_blocks = journal_storage.encode(state)
    blocks.update(projection_blocks)
    journal_storage.materialize(home, blocks)
    _write(path, raw)


def prepared_native_launch_step(project, run_id, permit_id, token, phase, *, runtime_root=None, send=None, outcome=None):
    """Closed owner-prepared capability seam sharing the sole run lock/writer.

    This does not accept an actor or general run command. Only reservation,
    an admitted transport send, or its bounded diagnostic observation can be
    committed. Native work must separately authenticate through ordinary PM.
    """
    import prepared_native_launch as launch
    project=Path(project).absolute()
    _id(run_id)
    _id(permit_id)
    if phase not in {"reserve","submit","observe"}:
        raise RunStateError("unsupported prepared launch phase")
    home=_home(project,run_id)
    with bounded_lock(home/".run.lock",create=False):
        previous=_last_event(project,run_id)
        state=previous["state"]
        _require_unlinked_predecessor(project, run_id)
        if _active_native(state) or state.get("cancellation_requested") and phase in {"reserve", "submit"}:
            raise RunStateError("active observation or cancellation blocks prepared native work")
        grant=launch._grant(state,permit_id,token)
        if phase in {"reserve","submit"}:
            required="prepared" if phase=="reserve" else "consumed"
            if grant["status"]!=required:
                raise RunStateError("one-shot launch is "+grant["status"]+"; no replay")
            proof=launch.current_fence(project,state,grant,runtime_root=runtime_root)
        else:
            if grant["status"] not in {"consumed","submitted","cancelled"}:
                raise RunStateError("no outstanding transport observation")
            import native_resume
            if not native_resume.is_observation(outcome) or len(_json(outcome))>65536 or outcome.get("task_accepted") is not False or outcome.get("native_session_id")!=grant["native_session_id"]:
                raise RunStateError("invalid bounded native transport observation")
            proof=_binding(project,state,grant["issuer_selector"],readonly=True,passive=True)
            if any(proof.get(key)!=grant['issuer'].get(key) for key in ('session_uuid','native_ref','claim_hash','repository','branch')):
                raise RunStateError('native launch observation issuer changed')
            import recovery_capsule
            recovery_capsule.resolve(project,state['project_id'],grant['issuer_selector'],runtime_root)
        plan_before=_plan(project,state["plan"]).resolved.read_text(encoding="utf-8")
        before=launch.attribution_snapshot(project,grant)
        updated=deepcopy(state)
        row=updated["extensions"]["prepared_native_launch"]["permits"][permit_id]
        result=None
        if phase=="reserve":
            row.update(status="consumed",consumed_at=_now(),consumed_revision=state["revision"]+1)
        elif phase=="submit":
            if not callable(send):
                raise RunStateError("native submission requires the owned transport operation")
            result=send()
            row.update(status="submitted",submitted_at=_now(),admission=deepcopy(result))
        else:
            row["outcome"]=deepcopy(outcome)
            row["observed_at"]=_now()
            if row["status"]!="cancelled":
                row["status"]="observed" if outcome.get("status")=="native_terminal" else "unknown"
        updated["revision"]=state["revision"]+1
        updated["updated_at"]=_now()
        # The committed attribution must describe the same codec the append
        # selects. Validate the predecessor binding before selecting its successor.
        journal_storage.codec_for(updated)
        updated.setdefault("extensions", {})["journal_storage"] = {"codec": 2}
        projection_hashes={str(path):hashlib.sha256(raw).hexdigest()
            for path,raw in _projection_bytes(project,updated,plan_before).items()}
        if phase in {"reserve","submit"}:
            # Recheck issuer claim revocation after a slow native handshake.
            proof=launch.current_fence(project,state,grant,runtime_root=runtime_root)
        else:
            # A terminal or cancelled transport may still report its outcome,
            # but slow filesystem reads cannot carry a revoked owner's grant
            # across the append boundary. Keep this separate from launch
            # eligibility so cancellation diagnostics remain recordable.
            proof=_binding(project,state,grant["issuer_selector"],readonly=True,passive=True)
            if any(proof.get(key)!=grant['issuer'].get(key) for key in ('session_uuid','native_ref','claim_hash','repository','branch')):
                raise RunStateError('native launch observation issuer changed before append')
        identity="launch-"+permit_id+"-"+phase
        _id(identity)
        authority={"permit_id":permit_id,"prepared_revision":grant["prepared_revision"],
            "issuer_session_uuid":grant["issuer"]["session_uuid"],"phase":phase,
            "ownership_transfer":False,"native_actor_authenticated":False,"edit_basis":before,
            "projection_hashes":projection_hashes,"plan_basis_sha256":hashlib.sha256(plan_before.encode()).hexdigest()}
        _append(project,updated,identity,_digest({"phase":phase,"permit_id":permit_id,"result":result,"outcome":outcome}),
            "native.launch."+phase,previous["digest"],proof,prepared_authority=authority)
        _project(project,updated)
        _index_update(runtime_root,state["owner"]["session_uuid"],run_id,_index_entry(project,updated))
        launch.attribute_owned_append(project,updated,grant,token,runtime_root=runtime_root)
        return deepcopy(result if phase=="submit" else updated)


def create_run(project: Path, *, project_id: str, plan: Path, contract: dict, profile: dict,
               actor: dict, command_id: str, run_id: str | None = None,
               runtime_root: Path | None = None, request_binding: dict | None = None) -> dict:
    return _create(project, project_id=project_id, plan=plan, contract=contract, profile=profile,
                   actor=actor, command_id=command_id, run_id=run_id, runtime_root=runtime_root,
                   request_binding=request_binding)


def _create(project, *, project_id, plan, contract, profile, actor, command_id, run_id=None,
            runtime_root=None, migration=None, request_binding=None):
    project = Path(project).resolve(strict=True)
    _id(project_id, "project ID")
    _id(command_id, "command ID")
    request_binding = _request_binding(request_binding)
    if request_binding and (request_binding["operation"] != "start" or request_binding["step"] != "create"
                            or request_binding["initial_revision"] != 0):
        raise RunStateError("creation request must be the initial start step")
    contract, profile = _contract(contract), _profile(profile)
    reference = _plan(project, plan)
    identity = native_binding(Path(actor["board"]), actor["native_payload"])
    run_id = _uuid(run_id) if run_id else str(uuid.uuid5(uuid.NAMESPACE_URL, f"{project}:{identity['session_uuid']}:{command_id}"))
    state = {"schema_version": SCHEMA, "run_id": run_id, "project_id": project_id, "plan": reference.relative_path,
             "revision": 1, "status": "preparing", "contract": contract, "contract_revision": 1,
             "contract_digest": _digest(contract), "profile": profile, "profile_revision": 1,
             "profile_digest": _digest(profile), "artifacts": {}, "evidence": {}, "verification": {},
             "criterion_evidence_bindings": {},
             "waits": {}, "effects": {}, "observations": {}, "extensions": {}, "progress": {}, "created_at": _now(), "updated_at": _now()}
    proof = _binding(project, state, actor)
    state["owner"] = proof
    creation_material = {"project_id": project_id, "plan": reference.relative_path, "contract": contract,
                               "profile": profile, "migration": migration[1] if migration else None,
                               "owner": proof["session_uuid"], "native_ref": proof["native_ref"]}
    if request_binding is not None:
        creation_material["request_binding"] = request_binding
    creation_digest = _digest(creation_material)
    _record_request(state, request_binding, command_id, creation_digest)
    home = _home(project, run_id)
    with bounded_lock(home / ".run.lock"):
        if _has_event_prefix(home / "events"):
            first = next(_events(project, run_id))
            if first["command_id"] != command_id or first["command_digest"] != creation_digest:
                raise RunStateError("run creation identity already exists with different input")
            recovered = load_run(project, run_id)
            _binding(project, recovered, actor)
            _project(project, recovered)
            _index_update(runtime_root, proof["session_uuid"], run_id, _index_entry(project, recovered))
            return recovered
        _binding(project, state, actor)
        if migration:
            raw, legacy = migration
            _write(home / "legacy/original.json", raw)
            state["migration"] = {"source_digest": hashlib.sha256(raw).hexdigest(), "legacy_receipt_trusted": False,
                                  "legacy_status": legacy.get("status", legacy.get("state")), "legacy": legacy}
            state["status"] = "recovering"
            if legacy.get("blocker"):
                state["waits"]["legacy-blocker"] = {"id": "legacy-blocker", "kind": "external", "status": "pending", "reason": str(legacy["blocker"])}
            if legacy.get("status", legacy.get("state")) in {"closed", "completed", "incomplete", "cancelled"}:
                state["status"] = "incomplete"
                state["terminal"] = {"at": _now(), "reason": "Historical terminal run; legacy completion evidence remains unverified"}
        _native_index_update(runtime_root, proof)
        _index_update(runtime_root, proof["session_uuid"], run_id, _index_entry(project, state, "pending"))
        _append(project, state, command_id, creation_digest, "create", "", proof)
        _project(project, state)
        _index_update(runtime_root, proof["session_uuid"], run_id, _index_entry(project, state))
        return deepcopy(state)



# A successor is another event in the existing run owner, not a second budget
# authority. The complete predecessor remains immutable and addressable.
MAX_SUCCESSOR_SECONDS = 120
MAX_SUCCESSOR_DEPTH = 32
MAX_SUCCESSOR_RESERVATIONS = 2048
MAX_SUCCESSOR_ARTIFACT_BYTES = 1024 * 1024 * 1024
MAX_SUCCESSOR_INTERVAL_SECONDS = 7 * 24 * 3600


def _successor_tick(until):
    if time.monotonic() >= until:
        raise RunStateError("successor transaction elapsed bound exceeded")


def _successor_head(event):
    state = event["state"]
    return {"run_id": state["run_id"], "revision": state["revision"],
            "event_digest": event["digest"], "state_digest": _digest(state),
            "deadline": state.get("extensions", {}).get("workflow", {}).get("budget", {}).get("deadline")}


def _successor_reference(value):
    if not isinstance(value, dict) or set(value) != {"run_id", "revision", "event_digest", "state_digest", "deadline"}:
        raise RunStateError("predecessor reference has unknown or missing fields")
    _uuid(value["run_id"])
    if type(value["revision"]) is not int or not 1 <= value["revision"] <= MAX_EVENTS:
        raise RunStateError("invalid predecessor revision")
    for key in ("event_digest", "state_digest"):
        if not isinstance(value[key], str) or not re.fullmatch("[a-f0-9]{64}", value[key]):
            raise RunStateError("invalid predecessor digest")
    _time(value["deadline"])


def _successor_chain(project, reference, until):
    """Fully replay each linked predecessor, without recursive projection trust."""
    seen, states, count = set(), [], 0
    child = None
    while reference is not None:
        _successor_tick(until)
        _successor_reference(reference)
        ident = reference["run_id"]
        if ident in seen or len(seen) >= MAX_SUCCESSOR_DEPTH:
            raise RunStateError("successor history is cyclic or exceeds depth bound")
        seen.add(ident)
        last, initial = None, None
        for last in _events(project, ident, verify_successor=False):
            if initial is None:
                initial = last["state"]
            count += 1
            _successor_tick(until)
            if count > MAX_EVENTS:
                raise RunStateError("successor history exceeds aggregate replay bound")
        if last is None or _successor_head(last) != reference:
            raise RunStateError("predecessor head/deadline changed or history is missing")
        state = last["state"]
        if state["status"] not in TERMINAL:
            raise RunStateError("predecessor is not terminal")
        if child is not None:
            _successor_inheritance(child, state)
        child = initial
        states.append(state)
        link = initial.get("successor")
        if state.get("successor") != link:
            raise RunStateError("successor lineage changed within its journal")
        reference = link["predecessor"] if link else None
    return states



def _successor_inherited_view(state):
    value = deepcopy(state)
    for key in ("run_id", "revision", "status", "created_at", "updated_at", "owner", "terminal", "completion", "handoff", "successor"):
        value.pop(key, None)
    value["extensions"].pop("controller", None)
    flow = value["extensions"]["workflow"]
    flow.pop("bindings", None)
    flow["budget"].pop("deadline", None)
    return value


def _successor_inheritance(child, parent):
    if (child["project_id"] != parent["project_id"]
            or child["run_id"] != successor_identity(Path(child["owner"]["project_root"]), parent["run_id"])
            or _successor_inherited_view(child) != _successor_inherited_view(parent)
            or child["extensions"]["workflow"]["budget"]["deadline"] != child["successor"]["deadline"]
            or any(child["owner"][key] != parent["owner"][key] for key in ("session_uuid", "native_ref", "repository", "branch"))):
        raise RunStateError("successor history drops or changes inherited obligations/costs")


def _successor_journal_witnesses(project, chain, until):
    """Bind verified predecessor files across a slow final admission fence."""
    witnesses, entries = {}, 0
    fields = ("st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns", "st_ctime_ns")
    for state in chain:
        home = _home(project, state["run_id"])
        for relative in ("events", "state-blocks/v1"):
            directory = safe_path(home / relative, Path(project))
            if not directory.exists():
                continue
            if not directory.is_dir():
                raise RunStateError("predecessor journal directory is unsafe")
            witnesses[str(directory)] = tuple(getattr(directory.stat(), key) for key in fields)
            with os.scandir(directory) as members:
                for member in members:
                    _successor_tick(until)
                    entries += 1
                    if entries > MAX_EVENTS + journal_storage.MAX_STORE_ENTRIES:
                        raise RunStateError("predecessor journal witness count exceeds bound")
                    info = member.stat(follow_symlinks=False)
                    if not stat.S_ISREG(info.st_mode):
                        raise RunStateError("predecessor journal member is not regular")
                    witnesses[member.path] = tuple(getattr(info, key) for key in fields)
    return witnesses


def _successor_file(project, record, until, remaining, witnesses):
    """Bounded descriptor read with an exact pathname/metadata recheck."""
    _successor_tick(until)
    path = safe_path(Path(project) / record["path"], Path(project))
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    digest, size = hashlib.sha256(), 0
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size > min(remaining, journal_storage.MAX_LOGICAL_BYTES):
            raise RunStateError("successor evidence is nonregular or exceeds byte bound")
        while chunk := os.read(fd, 128 * 1024):
            size += len(chunk)
            if size > min(remaining, journal_storage.MAX_LOGICAL_BYTES):
                raise RunStateError("successor evidence exceeds byte bound")
            digest.update(chunk)
            _successor_tick(until)
        after, present = os.fstat(fd), path.lstat()
        fields = ("st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns", "st_ctime_ns")
        if any(getattr(before, key) != getattr(other, key) for other in (after, present) for key in fields):
            raise RunStateError("successor evidence changed during read")
        if size != before.st_size or digest.hexdigest() != record["digest"]:
            raise RunStateError("successor evidence digest changed")
        witnesses[str(path)] = tuple(getattr(before, key) for key in fields)
        return size
    finally:
        os.close(fd)


def _successor_inputs(project, state, intent, until):
    remaining = MAX_SUCCESSOR_ARTIFACT_BYTES
    witnesses = {}
    records = [*state["artifacts"].values(), intent["authorization_ref"]]
    if len(records) > MAX_EVENTS:
        raise RunStateError("successor artifact count exceeds bound")
    for record in records:
        remaining -= _successor_file(project, record, until, remaining, witnesses)
    return witnesses


def _successor_recheck_files(project, witnesses, until):
    fields = ("st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns", "st_ctime_ns")
    for name, expected in witnesses.items():
        _successor_tick(until)
        info = safe_path(Path(name), Path(project)).lstat()
        if tuple(getattr(info, key) for key in fields) != expected:
            raise RunStateError("successor evidence changed during final admission")


def _successor_ledger(state):
    import workflow
    ledger = state["extensions"]["workflow"]["budget"]
    limits, reservations = ledger.get("limits"), ledger.get("reservations")
    if not isinstance(limits, dict) or not 1 <= len(limits) <= 16 or not isinstance(reservations, dict) or len(reservations) > MAX_SUCCESSOR_RESERVATIONS:
        raise RunStateError("predecessor resource ledger shape exceeds bounds")
    for name, policy in limits.items():
        workflow._id(name)
        workflow._object(policy, {"limit", "enforcement"}, {"limit", "enforcement"})
        if policy["enforcement"] not in {"hard", "forecast"} or policy["limit"] is None and policy["enforcement"] != "forecast":
            raise RunStateError("invalid inherited resource enforcement")
        if policy["limit"] is not None:
            workflow._integer(policy["limit"])
    for ident, row in reservations.items():
        workflow._id(ident)
        if row.get("id") != ident or row.get("status") not in {"reserved", "settled", "unknown"} or row.get("category") not in {"work", "integration", "verification", "recovery", "overhead"}:
            raise RunStateError("invalid inherited reservation")
        if set(row.get("amounts", {})) != set(limits):
            raise RunStateError("inherited reservation omits resource dimensions")
        workflow._amounts(ledger, row["amounts"])
        if row.get("actual") is not None:
            workflow._amounts(ledger, row["actual"])
        seen, parent = {ident}, row.get("parent_id")
        while parent is not None:
            if parent not in reservations or parent in seen or len(seen) >= MAX_SUCCESSOR_DEPTH:
                raise RunStateError("inherited budget ancestry is missing, cyclic or too deep")
            seen.add(parent)
            parent = reservations[parent].get("parent_id")
    for row in reservations.values():
        if row["status"] == "settled" and not workflow._reservation_accounted(ledger, row):
            raise RunStateError("inherited settled reservation undercounts unknown usage")
    # Summaries derive from the unchanged complete nested ledger, not caller
    # totals. Negative remaining capacity/breaches stay retained, never refunded.
    workflow.budget_summary(state)


def _successor_quiescent(state):
    """Only owner-recorded terminal custody is retained; never adopt live work."""
    if _active_native(state):
        raise RunStateError("predecessor native observation remains unresolved")
    flow = state.get("extensions", {}).get("workflow", {})
    if not flow.get("budget"):
        raise RunStateError("predecessor has no bounded resource ledger")
    _successor_ledger(state)
    import workflow
    for child in [*flow.get("children", {}).values(), *flow.get("retained_children", [])]:
        if child.get("disposition") not in workflow.TERMINAL_CHILD or child.get("audit_status") not in {"accepted", "rejected"}:
            raise RunStateError("predecessor worker/process custody needs reconciliation")
    if any(node.get("status") == "running" for node in flow.get("graph", {}).get("nodes", {}).values()):
        raise RunStateError("predecessor has active workflow work")
    if any(effect.get("status") not in {"confirmed", "failed", "cancelled"} for effect in state.get("effects", {}).values()):
        raise RunStateError("predecessor effect custody needs reconciliation")
    extensions = state.get("extensions", {})
    continuation = extensions.get("capabilities", {}).get("continuation")
    if continuation and continuation.get("status") != "cancelled":
        raise RunStateError("predecessor native continuation needs confirmed cancellation")
    permits = extensions.get("prepared_native_launch", {}).get("permits", {})
    if any(item.get("status") not in {"cancelled", "observed"} for item in permits.values()):
        raise RunStateError("predecessor native launch custody needs reconciliation")
    # Unknown actual usage, consumed attempts, breaches and all historical
    # native projections stay byte-equivalent; they never become zero/PASS.


def successor_identity(project, predecessor_id):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"synthesis-successor:{Path(project).resolve()}:{_uuid(predecessor_id)}"))


def _has_event_prefix(directory):
    """Bound discovery to one physical entry; replay validates all membership."""
    if not directory.exists():
        return False
    before = directory.lstat()
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        fields = ("st_dev", "st_ino", "st_mode", "st_mtime_ns", "st_ctime_ns")
        def signature(info):
            return tuple(getattr(info, key) for key in fields)
        if signature(before) != signature(os.fstat(fd)):
            raise RunStateError("successor event directory changed before discovery")
        with os.scandir(fd) as entries:
            present = next(entries, None) is not None
        if signature(before) != signature(os.fstat(fd)) or signature(before) != signature(directory.lstat()):
            raise RunStateError("successor event directory changed during discovery")
        return present
    finally:
        os.close(fd)


def create_successor(project, *, project_id, intent, actor, command_id,
                     runtime_root=None, request_binding=None):
    """Atomically derive one bounded continuation from an exact terminal head.

    The request is scoped intent, not an external effect/credential grant.
    Limits, reservations, native counters, failures and unfinished obligations
    are copied from verified owner state; callers cannot substitute them.
    """
    project = Path(project).resolve(strict=True)
    _id(project_id, "project ID")
    _id(command_id, "command ID")
    if len(_json(intent)) > MAX_INPUT_BYTES:
        raise RunStateError("successor request exceeds bounded input")
    if not isinstance(intent, dict) or set(intent) != {"predecessor", "deadline", "authorization_ref"}:
        raise RunStateError("successor intent has unknown or missing fields")
    _successor_reference(intent["predecessor"])
    if not isinstance(intent["authorization_ref"], dict) or set(intent["authorization_ref"]) != {"path", "digest"}:
        raise RunStateError("authorization reference has unknown or missing fields")
    if not isinstance(intent["authorization_ref"]["digest"], str) or not re.fullmatch("[a-f0-9]{64}", intent["authorization_ref"]["digest"]):
        raise RunStateError("invalid authorization reference digest")
    request_binding = _request_binding(request_binding)
    if request_binding and (request_binding["operation"] != "successor" or request_binding["step"] != "create" or request_binding["initial_revision"] != 0):
        raise RunStateError("successor requires its initial request step")
    until = time.monotonic() + MAX_SUCCESSOR_SECONDS
    chain = _successor_chain(project, intent["predecessor"], until)
    old = chain[0]
    if old["project_id"] != project_id or any(row["project_id"] != project_id for row in chain):
        raise RunStateError("predecessor chain changed project scope")
    _successor_quiescent(old)
    new_id = successor_identity(project, old["run_id"])
    home = _home(project, new_id)
    plan = _plan(project, old["plan"]).resolved
    auth = safe_path(project / intent["authorization_ref"]["path"], project)
    paths = [home, plan, _plan_lock(project, plan), auth, _home(project, old["run_id"])]
    def admission():
        proof = admit_paths(Path(actor["board"]), project_id, project, paths, actor["native_payload"])
        for key in ("session_uuid", "native_ref", "repository", "branch", "board"):
            if proof[key] != old["owner"][key]:
                raise RunStateError("successor requires exact predecessor native owner and workspace")
        _successor_tick(until)
        return proof
    proof = admission()
    plan_digest = _plan_digest(project, old)
    material = {"project_id": project_id, "intent": intent, "request_binding": request_binding,
                "session_uuid": proof["session_uuid"], "native_ref": proof["native_ref"]}
    command_digest = _digest(material)
    # A deterministic single child ID serializes concurrent competing requests
    # without changing the predecessor or inventing another authority index.
    with bounded_lock(home / ".run.lock", timeout=max(.01, until-time.monotonic())):
        _successor_tick(until)
        if _has_event_prefix(home / "events"):
            first = next(_events(project, new_id))
            if first["command_id"] != command_id or first["command_digest"] != command_digest:
                raise RunStateError("successor already exists with different request or predecessor")
            recovered = load_run(project, new_id)
            committed = first["state"]
            if (committed["successor"].get("plan_digest") != plan_digest
                    or any(committed["owner"].get(key) != proof.get(key)
                           for key in ("session_uuid", "native_ref", "claim_hash", "repository", "branch", "board"))):
                raise RunStateError("successor recovery claim/plan authority changed since commit")
            history_witnesses = _successor_journal_witnesses(project, chain, until)
            _successor_chain(project, intent["predecessor"], until)
            witnesses = _successor_inputs(project, old, intent, until)
            final = admission()
            _successor_recheck_files(project, witnesses, until)
            _successor_recheck_files(project, history_witnesses, until)
            if (any(final.get(key) != proof.get(key) for key in ("session_uuid", "native_ref", "claim_hash", "repository", "branch"))
                    or _plan_digest(project, old) != plan_digest):
                raise RunStateError("successor recovery authority or plan changed")
            _project(project, recovered)
            _index_update(runtime_root, proof["session_uuid"], new_id, _index_entry(project, recovered))
            return recovered
        # The existing discovery index retains the exact unfinished request;
        # it never supplies an admitted run without its authoritative event.
        basis = {"command_id": command_id, "command_digest": command_digest,
                 "plan_digest": plan_digest,
                 "authority": {key: proof.get(key) for key in
                     ("session_uuid", "native_ref", "claim_hash", "repository", "branch", "board")}}
        pending = _index_read(_index_path(runtime_root, proof["session_uuid"]), proof["session_uuid"])["runs"].get(new_id)
        if pending is not None and (pending.get("status") != "pending" or pending.get("successor_basis") != basis):
            raise RunStateError("pending successor request or authority changed")
        # No active predecessor is written. Its existing lock excludes an
        # ordinary terminal-safe observation while the exact source is copied.
        with bounded_lock(_home(project, old["run_id"]) / ".run.lock", create=False,
                          timeout=max(.01, until-time.monotonic())):
            checked = _successor_chain(project, intent["predecessor"], until)
            _successor_quiescent(checked[0])
            history_witnesses = _successor_journal_witnesses(project, checked, until)
            _successor_chain(project, intent["predecessor"], until)
            _successor_recheck_files(project, history_witnesses, until)
            _successor_inputs(project, old, intent, until)
            now = _now()
            deadline = _time(intent["deadline"])
            if not _time(now) < deadline <= _time(now) + timedelta(seconds=MAX_SUCCESSOR_INTERVAL_SECONDS) or deadline <= _time(intent["predecessor"]["deadline"]):
                raise RunStateError("new successor deadline is expired, excessive, or does not advance the interval")
            state = deepcopy(old)
            for key in ("terminal", "completion", "handoff"):
                state.pop(key, None)
            state.update(run_id=new_id, revision=1, status="preparing", created_at=now, updated_at=now)
            state["extensions"].pop("controller", None)
            flow = state["extensions"]["workflow"]
            flow["bindings"] = {key: state[key] for key in ("run_id", "contract_digest", "profile_digest")}
            flow["budget"]["deadline"] = intent["deadline"]
            state["successor"] = {"schema_version": 1, **deepcopy(intent), "plan_digest": plan_digest,
                "history_coverage": "complete owner-linked chain; untyped legacy evidence retained without reinterpretation"}
            # Preserve the complete old receipts with old run bindings. They
            # remain historical and cannot satisfy this new run's acceptance.
            state["owner"] = proof
            _record_request(state, request_binding, command_id, command_digest)
            witnesses = _successor_inputs(project, old, intent, until)
            _successor_chain(project, intent["predecessor"], until)
            # Publish only a pending discovery hint before the final fence:
            # slow host-index locks cannot age the later effect admission.
            _native_index_update(runtime_root, proof)
            _index_update(runtime_root, proof["session_uuid"], new_id,
                          {**_index_entry(project, state, "pending"), "successor_basis": basis})
            final = admission()
            _successor_recheck_files(project, witnesses, until)
            _successor_recheck_files(project, history_witnesses, until)
            if any(final.get(key) != proof.get(key) for key in ("session_uuid", "native_ref", "claim_hash", "repository", "branch", "board")):
                raise RunStateError("successor authority changed before commit")
            if _plan_digest(project, old) != plan_digest:
                raise RunStateError("successor plan changed before commit")
            if _time(_now()) >= deadline:
                raise RunStateError("successor deadline expired before commit")
            state["owner"] = final
            _successor_tick(until)
            _append(project, state, command_id, command_digest, "successor", "", final)
            _project(project, state)
            _index_update(runtime_root, final["session_uuid"], new_id, _index_entry(project, state))
            return deepcopy(state)


def register_command(name, reducer, *, allowed_fields=("extensions",), terminal_safe=False):
    _id(name, "command name")
    if tuple(allowed_fields) != ("extensions",) or not callable(reducer) or name in CORE_COMMANDS:
        raise RunStateError("extensions may register only pure extensions-field reducers")
    if name in _COMMANDS and _COMMANDS[name] is not reducer:
        raise RunStateError("command is already registered")
    _COMMANDS[name] = reducer
    if type(terminal_safe) is not bool:
        raise RunStateError("terminal_safe must be explicit boolean")
    if terminal_safe:
        _TERMINAL_COMMANDS.add(name)
    else:
        _TERMINAL_COMMANDS.discard(name)


def register_preparer(name, callback):
    """Install trusted observation code inside the existing admitted command.

    This is an in-process code registration, never a JSON callback. Its bounded
    result is passed to the already registered pure extension reducer. Replay
    checks use the original requested payload and do not repeat observation.
    """
    if name not in _COMMANDS or not callable(callback):
        raise RunStateError("preparer requires a registered extension command")
    if name in _PREPARERS and _PREPARERS[name] is not callback:
        raise RunStateError("command preparer is already registered")
    _PREPARERS[name] = callback


def register_verifier(kind, verifier):
    """Install an in-process trusted pure verifier, never a JSON-provided one."""
    _id(kind, "evidence kind")
    if not callable(verifier):
        raise RunStateError("verifier must be callable trusted code")
    _VERIFIERS[kind] = verifier


def register_evidence_source(kind, source_verifier):
    """Trusted owner observation bridge, evaluated before any pure reducer.

    The source callback receives the record plus project/state/binding/actor/
    now/artifacts. It may perform bounded owner-controlled reads; never writes
    or network refreshes during passive inspection. JSON cannot register code.
    """
    _id(kind, "evidence source kind")
    if not callable(source_verifier):
        raise RunStateError("evidence source must be trusted callable code")
    _EVIDENCE_SOURCES[kind] = source_verifier


def register_observer(kind, callback, *, terminal_safe=False):
    """Register trusted bounded observation code; payloads cannot supply code."""
    _id(kind, "observer kind")
    if not callable(callback) or (kind in _OBSERVERS and _OBSERVERS[kind] is not callback):
        raise RunStateError("invalid or conflicting observer registration")
    if type(terminal_safe) is not bool or (terminal_safe and kind not in {"delivery", "continuation-cancellation"}):
        raise RunStateError("only read-only delivery/cancellation observers may follow a terminal tombstone")
    _OBSERVERS[kind] = callback
    if terminal_safe:
        _TERMINAL_COMMANDS.add("observe:" + kind)
    else:
        _TERMINAL_COMMANDS.discard("observe:" + kind)


def register_acceptance(kind, predicate):
    """Register pure domain acceptance, separately from source authenticity."""
    _id(kind, "acceptance kind")
    if not callable(predicate):
        raise RunStateError("acceptance predicate must be trusted callable code")
    _ACCEPTANCE[kind] = predicate


def observe(project, run_id, kind, payload, *, expected_revision, command_id, actor, runtime_root=None):
    """Execute a registered observer once under CAS and commit its real result."""
    _id(kind, "observer kind")
    if kind not in _OBSERVERS:
        raise RunStateError("unregistered observer")
    return apply_command(project, run_id, "observe:" + kind, payload, expected_revision=expected_revision,
                         command_id=command_id, actor=actor, runtime_root=runtime_root)


def register_constraint(name, check):
    """Register a pure owner-module guard, also enforced on direct core calls."""
    _id(name, "constraint name")
    if not callable(check) or (name in _CONSTRAINTS and _CONSTRAINTS[name] is not check):
        raise RunStateError("invalid or conflicting constraint registration")
    _CONSTRAINTS[name] = check


def unregister_constraint(name):
    """Remove a process-local registration, principally for isolated tests."""
    _CONSTRAINTS.pop(name, None)


def inspect_context(state, actor, *, project=None):
    """Read-only fresh state/admission/evidence view for trusted owner modules."""
    project = Path(project or state["owner"]["project_root"])
    last = _last_event(project, state["run_id"])
    current = last["state"]
    if current != state:
        raise RunStateError("inspection state is stale; reload the current journal")
    proof = _binding(project, current, actor, readonly=True)
    context = _context(project, current, {}, proof, actor=actor)
    context["journal_head"] = {"revision": current["revision"], "digest": last["digest"], "scope": "full_run"}
    context["current_native_events"] = _native_readback(project, current, actor, context["journal_head"])
    context["current_native_invalidation"] = _native_readback(project, current, actor, context["journal_head"], invalidation=True)
    return context


def _native_readback(project, state, actor, journal_head, *, passive=False, invalidation=False, owner_reconcile=False):
    """An ephemeral fresh-read operation, never a reusable admission token.

    The closure binds an already chain-verified state. Each invocation acquires
    fresh native/PM admission and rejects an intervening journal append before
    and after the selected current source ranges are read.
    """
    if passive and owner_reconcile:
        raise RunStateError("passive Stop readback cannot reconcile the coordination mirror")
    selected, principal, head = _copy_state(state), deepcopy(actor), deepcopy(journal_head)
    project = Path(project)
    def read(event_ids=None, interval=None, *, source_handle="root"):
        import observation_bridge
        base = {"project": project, "state": selected, "actor": principal}
        if observation_bridge._current_head(base) != head["digest"]:
            raise RunStateError("native readback journal head changed")
        if owner_reconcile:
            reconcile_readback(Path(principal["board"]))
        proof = _binding(project, selected, principal, readonly=True, passive=passive)
        purpose = "passive-stop" if passive else "mutation"
        with admission_scope(proof, principal, project, purpose=purpose) as token:
            context = ({"binding": deepcopy(proof)} if invalidation and source_handle == "root" else
                _context_observed(project, selected, {}, proof, actor=principal, observation=token))
            context.update(base, admission_observation=token, journal_head=deepcopy(head))
            result = (observation_bridge.current_invalidation(context, source_handle=source_handle) if invalidation
                else observation_bridge.current_events(context, event_ids, required_interval=interval))
        if observation_bridge._current_head(base) != head["digest"]:
            raise RunStateError("native readback journal head changed")
        return result
    return read


def completion_report(project, run_id, *, actor):
    """Read-only criterion/profile/extension closure report; never emits a receipt."""
    state = load_run(project, run_id)
    context = inspect_context(state, actor, project=project)
    from required_citations import observe_required_citations
    context["required_citations"] = observe_required_citations(
        Path(project), Path(context["binding"]["paths"][1]), context["artifacts"],
        expected_plan_digest=context["plan_digest"])
    report = {"status": "PASS", "run_id": run_id, "revision": state["revision"], "issues": [],
              "profile_digest": state["profile_digest"], "contract_digest": state["contract_digest"]}
    try:
        candidate = deepcopy(state)
        if candidate["status"] == "completed":
            candidate["status"] = "verifying"
        _complete(project, candidate, context)
        candidate["status"] = "completed"
        for check in _CONSTRAINTS.values():
            check(deepcopy(candidate), "close", {"status": "completed"}, context)
    except (ValueError, OSError) as exc:
        report["status"] = "FAIL"
        report["issues"].append(str(exc))
    return report


def _artifact(project, record):
    path = safe_path(Path(project).resolve() / record["path"], Path(project).resolve())
    if not path.is_file() or path.is_symlink():
        raise RunStateError("registered artifact is missing or unsafe")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if record["digest"] != digest:
        raise RunStateError("registered artifact changed after registration")
    return record


def _context(project, state, payload, proof, *, actor=None, purpose="mutation"):
    # Consume fresh issuance before potentially slow current artifact reads.
    # The nonserializable token lives only through this central operation;
    # no caller or returned reducer context can carry it to a later command.
    with admission_scope(proof, actor, project, purpose=purpose) as observation:
        return _context_observed(project, state, payload, proof, actor=actor, observation=observation)


def _context_observed(project, state, payload, proof, *, actor, observation):
    now = _now()
    artifacts, evidence = {}, {}
    for key, record in state["artifacts"].items():
        try:
            artifacts[key] = deepcopy(_artifact(project, record))
        except (OSError, ValueError, KeyError):
            pass  # Missing inputs are absent from verified views, never valid.
    bindings = {key: state[key] for key in ("run_id", "contract_digest", "profile_digest")}
    for key, record in state["evidence"].items():
        artifact = artifacts.get(record.get("artifact_id"))
        try:
            if record.get("provenance") == "engine-observation":
                recorded_observation = state.get("observations", {}).get(key)
                fields = ("id", "kind", "bindings", "data", "digest", "observed_at", "expires_at")
                authentic = recorded_observation and all(record.get(field) == recorded_observation.get(field) for field in fields)
                authentic = authentic and recorded_observation["digest"] == _digest({name: value for name, value in recorded_observation.items() if name != "digest"})
                authentic = authentic and recorded_observation.get("artifact_digests") and all(
                    ref in artifacts and artifacts[ref]["digest"] == digest for ref, digest in recorded_observation["artifact_digests"].items())
                artifact = {"digest": recorded_observation["digest"]} if authentic else None
            valid = artifact and artifact["digest"] == record["digest"] and _time(record["observed_at"]) <= _time(now) < _time(record["expires_at"])
            valid = valid and all(record["bindings"].get(name) == value for name, value in bindings.items())
            if valid:
                evidence[key] = deepcopy(record)
        except (KeyError, TypeError, ValueError):
            pass
    authoritative_evidence = deepcopy(evidence)
    source_verdicts = {}
    plan_digest = _plan_digest(project, state, admitted_path=proof["paths"][1], repository=proof["repository"])
    observer_context = {"project": Path(project), "state": _copy_state(state), "binding": deepcopy(proof),
                        "actor": deepcopy(actor), "now": now, "artifacts": deepcopy(artifacts),
                        "evidence": deepcopy(evidence), "plan_digest": plan_digest}
    evaluating = set()
    source_phase = True
    def source_verdict(ref):
        if ref in source_verdicts:
            return source_verdicts[ref]
        if ref in evaluating:
            return False  # A receipt cannot prove itself through a cycle.
        record = authoritative_evidence[ref]
        source = _EVIDENCE_SOURCES.get(record["kind"])
        if source is None:
            return False
        evaluating.add(ref)
        try:
            source_verdicts[ref] = source(deepcopy(record), deepcopy(observer_context)) is True
        except Exception:
            source_verdicts[ref] = False
        finally:
            evaluating.remove(ref)
        return source_verdicts[ref]
    def verify_receipt(receipt, kind, required):
        record = authoritative_evidence.get(receipt) if isinstance(receipt, str) else None
        verifier = _VERIFIERS.get(kind)
        if not record or record.get("kind") != kind or not isinstance(required, dict):
            return False
        if any(record["bindings"].get(key) != value for key, value in required.items()):
            return False
        if kind in _EVIDENCE_SOURCES:
            return source_verdict(receipt) if source_phase else source_verdicts.get(receipt) is True
        if verifier is None:
            return False
        try:
            return verifier(deepcopy(record), deepcopy(required)) is True
        except Exception:
            return False
    observer_context["verify_receipt"] = verify_receipt
    observer_context["criterion_report"] = lambda: criterion_report(state, observer_context)
    observer_context["admission_observation"] = observation
    for ref, record in authoritative_evidence.items():
        if record["kind"] in _EVIDENCE_SOURCES:
            source_verdict(ref)
    observer_context.pop("admission_observation", None)
    source_phase = False
    admissions = {}
    requests = payload.get("admission_requests", [])
    if not isinstance(requests, list):
        raise RunStateError("admission_requests must be a list")
    for request in requests:
        if not isinstance(request, dict) or set(request) != {"id", "actor", "paths"}:
            raise RunStateError("invalid admission request")
        key = _id(request["id"])
        if key in admissions:
            raise RunStateError("duplicate admission request ID")
        actor = request["actor"]
        if not isinstance(actor, dict) or set(actor) != {"board", "native_payload"}:
            raise RunStateError("invalid child native actor")
        admissions[key] = admit_paths(Path(actor["board"]), state["project_id"], Path(project),
            [Path(path) for path in request["paths"]], actor["native_payload"])
    required_citations = None
    if payload.get("status") == "completed":
        from required_citations import observe_required_citations
        required_citations = observe_required_citations(
            Path(project), Path(proof["paths"][1]), artifacts, expected_plan_digest=plan_digest)
    return {"now": now, "binding": deepcopy(proof), "artifacts": artifacts, "evidence": evidence,
            "admissions": admissions, "verify_receipt": verify_receipt, "plan_digest": plan_digest,
            "required_citations": required_citations}


def _fields(payload, allowed, required=()):
    if not isinstance(payload, dict) or set(payload) - set(allowed) - {"admission_requests"} or set(required) - set(payload):
        raise RunStateError("command payload has unknown or missing fields")


def _receipt(context, state, receipt_id, kind):
    bindings = {key: state[key] for key in ("run_id", "contract_digest", "profile_digest")}
    if not context["verify_receipt"](receipt_id, kind, bindings):
        raise RunStateError(f"fresh bound {kind} evidence is required")
    return context["evidence"][receipt_id]


def _verify_binding(project, state, criterion, context):
    refs = criterion.get("artifact_ids", [])
    if any(ref not in context["artifacts"] for ref in refs):
        raise RunStateError("criterion artifact is missing, changed, or unsafe")
    hashes = {ref: context["artifacts"][ref]["digest"] for ref in refs}
    evidence_bindings = {}
    if criterion["method"] != "artifact":
        evidence_ids = criterion.get("evidence_ids", [])
        if not evidence_ids:
            raise RunStateError("non-artifact criterion needs typed verifier evidence")
        for ref in evidence_ids:
            selected = state.get("criterion_evidence_bindings", {}).get(criterion["id"], {}).get(ref)
            receipt_id = selected["receipt_id"] if selected else ref
            record = _receipt(context, state, receipt_id, criterion["method"])
            if selected and (selected["digest"] != record["digest"] or selected["contract_digest"] != state["contract_digest"]
                             or selected["profile_digest"] != state["profile_digest"]):
                raise RunStateError("criterion evidence selection is stale")
            predicate = _ACCEPTANCE.get(criterion["method"])
            if predicate is None or predicate(deepcopy(record), deepcopy(state), deepcopy(criterion), deepcopy(context)) is not True:
                raise RunStateError("authentic evidence does not satisfy the criterion's domain acceptance")
            hashes["evidence:" + ref] = record["digest"]
            evidence_bindings[ref] = {"receipt_id": receipt_id, "digest": record["digest"]}
    elif not refs:
        raise RunStateError("artifact criterion requires explicit artifacts")
    return {"run_id": state["run_id"], "contract_revision": state["contract_revision"],
            "contract_digest": state["contract_digest"], "profile_revision": state["profile_revision"],
            "profile_digest": state["profile_digest"], "artifact_digests": hashes, "evidence_bindings": evidence_bindings,
            "plan_digest": context["plan_digest"], "verifier_version": VERIFIER_VERSION}


def criterion_report(state, context):
    """Current per-criterion mechanical report from a fresh engine context.

    This helper performs no I/O and writes no verification. Source bridges may
    use it during observation; cyclic receipt dependencies remain unverified.
    """
    results = []
    for criterion in state["contract"]["criteria"]:
        row = {"id": criterion["id"], "required": criterion["required"], "method": criterion["method"],
               "status": "PASS", "issues": []}
        try:
            expected = _verify_binding(None, state, criterion, context)
            receipt = state["verification"].get(criterion["id"])
            if not receipt or receipt.get("binding") != expected or _time(receipt["expires_at"]) <= _time(context["now"]):
                raise RunStateError("criterion lacks current bound verification")
        except (ValueError, KeyError, TypeError) as exc:
            row["status"] = "FAIL" if criterion["required"] else "UNKNOWN"
            row["issues"].append(str(exc))
        results.append(row)
    return {"status": "FAIL" if any(row["status"] == "FAIL" for row in results) else "PASS",
            "run_id": state["run_id"], "revision": state["revision"], "contract_digest": state["contract_digest"],
            "profile_digest": state["profile_digest"], "criteria": results}


def _complete(project, state, context):
    if _active_native(state):
        raise RunStateError("native observation outcome remains unresolved")
    if state["status"] != "verifying":
        raise RunStateError("completion requires the verifying state")
    if any(item["status"] == "pending" for item in state["waits"].values()):
        raise RunStateError("completion has unresolved waits")
    if any(item["status"] in {"prepared", "unknown", "retryable"} for item in state["effects"].values()):
        raise RunStateError("completion has unresolved external effect outcomes")
    for key, record in state["artifacts"].items():
        if record["required"] and key not in context["artifacts"]:
            raise RunStateError("required artifact is missing or changed")
    citations = context.get("required_citations")
    if not isinstance(citations, dict) or citations.get("status") != "PASS":
        raise RunStateError("required plan/packet evidence retention is UNKNOWN: " +
                            "; ".join(citations.get("issues", []) if isinstance(citations, dict) else ["not observed"]))
    report = criterion_report(state, context)
    if report["status"] != "PASS":
        raise RunStateError("required criterion lacks current bound verification: " + "; ".join(
            row["id"] + ": " + ", ".join(row["issues"]) for row in report["criteria"] if row["status"] == "FAIL"))
    verified = {row["id"] for row in report["criteria"] if row["status"] == "PASS"}
    for item in state["profile"]["items"]:
        refs = item.get("criterion_ids")
        from profile_evidence import CANONICAL_IDS
        if item["id"] not in CANONICAL_IDS and refs and all(ref in verified for ref in refs):
            continue
        record = _receipt(context, state, state.get("profile_evidence"), "profile")
        if "dispositions" in record["data"]:
            from profile_evidence import accept_profile
            if not accept_profile(record["data"], state):
                raise RunStateError("standing profile dispositions contain unresolved or invalid obligations")
        elif item["id"] in CANONICAL_IDS or item["id"] not in record["data"].get("satisfied_items", []):
            raise RunStateError("standing profile item lacks validated disposition: " + item["id"])
    return {"at": context["now"], "run_id": state["run_id"], "contract_digest": state["contract_digest"],
            "profile_digest": state["profile_digest"], "criteria": sorted(verified), "verifier_version": VERIFIER_VERSION,
            "required_citation_artifacts": citations["artifacts"]}


def _reduce(project, state, name, payload, context):
    if name == "transition":
        _fields(payload, {"status"}, {"status"})
        target = payload["status"]
        if target not in STATUSES - TERMINAL or target == "preparing":
            raise RunStateError("invalid explicit transition")
        if target in {"running", "verifying"} and any(item["status"] == "pending" for item in state["waits"].values()):
            raise RunStateError("resolve waits before advancing state")
        state["status"] = target
    elif name == "progress":
        _fields(payload, {"summary"}, {"summary"})
        if not isinstance(payload["summary"], str) or not payload["summary"].strip():
            raise RunStateError("progress requires a nonempty observation")
        state["progress"] = {"summary": payload["summary"], "at": context["now"], "measured": False,
                             "observation_count": state["progress"].get("observation_count", 0) + 1}
        if state["status"] == "preparing":
            state["status"] = "running"
    elif name == "wait.add":
        _fields(payload, {"id", "kind", "reason"}, {"id", "kind", "reason"})
        key = _id(payload["id"])
        if payload["kind"] not in {"external", "user"} or not isinstance(payload["reason"], str) or not payload["reason"].strip() or key in state["waits"]:
            raise RunStateError("wait requires a new ID, typed dependency and reason")
        state["waits"][key] = {**payload, "status": "pending", "at": context["now"]}
        state["status"] = "waiting_user" if payload["kind"] == "user" else "waiting_external"
    elif name == "wait.resolve":
        _fields(payload, {"id", "evidence"}, {"id", "evidence"})
        item = state["waits"].get(payload["id"])
        record = _receipt(context, state, payload["evidence"], "wait-resolution")
        if not item or item["status"] != "pending" or record["data"].get("wait_id") != payload["id"] or record["data"].get("resolved") is not True:
            raise RunStateError("wait resolution does not bind this pending wait")
        item.update(status="resolved", evidence=payload["evidence"], resolved_at=context["now"])
        pending = [wait for wait in state["waits"].values() if wait["status"] == "pending"]
        state["status"] = ("waiting_user" if any(wait["kind"] == "user" for wait in pending) else "waiting_external") if pending else "running"
    elif name in {"contract.amend", "profile.amend"}:
        field = name.split(".")[0]
        _fields(payload, {field, "reason", "evidence"}, {field})
        value = _contract(payload[field]) if field == "contract" else _profile(payload[field])
        if field == "contract" and not set(value["authority_refs"]).issubset(state[field]["authority_refs"]):
            raise RunStateError("data amendments cannot expand action authority")
        if field == "contract":
            old = state[field]
            changed = old["scope"] != value["scope"] or old["exclusions"] != value["exclusions"]
            criteria = {item["id"]: item for item in value["criteria"]}
            changed = changed or any(criteria.get(item["id"]) != item for item in old["criteria"])
            outcomes = {item["id"]: item for item in value["outcomes"]}
            for item in old["outcomes"]:
                replacement = outcomes.get(item["id"], {})
                changed = changed or not set(item["criteria"]).issubset(replacement.get("criteria", []))
                changed = changed or {k: v for k, v in item.items() if k != "criteria"} != {k: v for k, v in replacement.items() if k != "criteria"}
            if changed:
                record = _receipt(context, state, payload.get("evidence"), "contract-amendment")
                if record["data"].get("replacement_digest") != _digest(value) or record["data"].get("approved") is not True:
                    raise RunStateError("contract amendment approval does not bind the exact replacement")
        if field == "profile":
            old_items = {item["id"]: item for item in state[field]["items"]}
            new_items = {item["id"]: item for item in value["items"]}
            if any(new_items.get(key) != item for key, item in old_items.items()):
                record = _receipt(context, state, payload.get("evidence"), "profile-amendment")
                if record["data"].get("replacement_digest") != _digest(value) or record["data"].get("approved") is not True:
                    raise RunStateError("profile amendment approval does not bind the exact replacement")
        state[field] = value
        state[field + "_revision"] += 1
        state[field + "_digest"] = _digest(value)
        state["verification"] = {}
        state.pop("profile_evidence", None)
        state["criterion_evidence_bindings"] = {}
    elif name == "artifact.register":
        _fields(payload, {"id", "path", "role", "retention", "required"}, {"id", "path", "role", "retention", "required"})
        key = _id(payload["id"])
        path = Path(payload["path"])
        if not path.is_absolute():
            path = Path(project) / path
        path = safe_path(path, Path(project).resolve())
        if payload["role"] not in {"input", "output", "evidence"} or payload["retention"] != "durable" or type(payload["required"]) is not bool or not path.is_file():
            raise RunStateError("artifact must be a durable project file with typed role/requirement")
        if path.is_relative_to(_home(project, state["run_id"])) or path == _plan(project, state["plan"]).resolved:
            raise RunStateError("run projections and controlling plan cannot be completion artifacts")
        state["artifacts"][key] = {**payload, "path": str(path.relative_to(Path(project).resolve())),
                                    "digest": hashlib.sha256(path.read_bytes()).hexdigest(), "registered_at": context["now"]}
        state["verification"] = {}
    elif name == "input.materialize":
        if set(payload) != {"id", "value"}:
            raise RunStateError("managed input accepts only an ID and typed JSON value")
        key = _id(payload["id"])
        raw = _input_bytes(payload["value"])
        digest = hashlib.sha256(raw).hexdigest()
        home = _home(project, state["run_id"])
        path = safe_path(home / "inputs" / (digest + ".json"), Path(project))
        previous = state["artifacts"].get(key)
        if previous and (previous.get("managed_input") is not True or previous.get("digest") != digest):
            raise RunStateError("managed input ID is immutable")
        _install_input(path, raw)
        safe_path(path, Path(project))
        if path.read_bytes() != raw:
            raise RunStateError("managed input changed during materialization")
        state["artifacts"][key] = {"id": key, "path": str(path.relative_to(Path(project).resolve())),
            "role": "input", "retention": "durable", "required": False, "digest": digest,
            "managed_input": True, "registered_at": context["now"]}
    elif name == "evidence.record":
        _fields(payload, {"id", "kind", "artifact_id"}, {"id", "kind", "artifact_id"})
        key, kind = _id(payload["id"]), _id(payload["kind"])
        if key in state["evidence"] or key in state.get("observations", {}):
            raise RunStateError("evidence attempt IDs are immutable; record a new attempt")
        artifact = context["artifacts"].get(payload["artifact_id"])
        if not artifact or artifact["role"] != "evidence":
            raise RunStateError("evidence requires a current registered evidence artifact")
        record = _read(Path(project) / artifact["path"])
        if not isinstance(record, dict) or set(record) != {"kind", "observed_at", "expires_at", "bindings", "data"} or record["kind"] != kind or not isinstance(record["data"], dict) or not isinstance(record["bindings"], dict):
            raise RunStateError("evidence artifact has an invalid typed envelope")
        if not _time(record["observed_at"]) <= _time(context["now"]) < _time(record["expires_at"]):
            raise RunStateError("evidence is expired or future-dated")
        if any(record["bindings"].get(field) != state[field] for field in ("run_id", "contract_digest", "profile_digest")):
            raise RunStateError("evidence does not bind the current run contract and profile")
        state["evidence"][key] = {**record, "id": key, "artifact_id": payload["artifact_id"], "digest": artifact["digest"]}
    elif name == "criterion.evidence.bind":
        fields = {"criterion_id", "slot", "receipt_id", "expected_prior_receipt_id", "expected_prior_digest"}
        _fields(payload, fields, fields)
        criterion = next((item for item in state["contract"]["criteria"] if item["id"] == payload["criterion_id"]), None)
        if (criterion is None or criterion["method"] not in {"quality_observation", "consumer-check"}
                or payload["slot"] not in criterion.get("evidence_ids", [])):
            raise RunStateError("evidence routing requires a declared non-authority observation slot")
        slot, receipt_id = _id(payload["slot"]), _id(payload["receipt_id"])
        selections = state.setdefault("criterion_evidence_bindings", {}).setdefault(criterion["id"], {})
        prior = selections.get(slot)
        prior_id = prior["receipt_id"] if prior else slot if slot in state["evidence"] else None
        prior_digest = prior["digest"] if prior else state["evidence"][prior_id]["digest"] if prior_id else None
        if (payload["expected_prior_receipt_id"] != prior_id or payload["expected_prior_digest"] != prior_digest):
            raise RunStateError("criterion evidence selection changed; reload before rebinding")
        record = _receipt(context, state, receipt_id, criterion["method"])
        data = record["data"]
        reviewed = context["artifacts"].get(data.get("artifact_id"))
        if (record.get("provenance") != "engine-observation" or record.get("id") != receipt_id
                or receipt_id not in state.get("observations", {}) or data.get("criterion_id") != criterion["id"]
                or data.get("artifact_id") not in criterion["artifact_ids"] or not reviewed
                or data.get("artifact_digest") != reviewed["digest"]):
            raise RunStateError("routing requires an authentic current engine observation of this criterion artifact")
        selections[slot] = {"receipt_id": receipt_id, "digest": record["digest"],
                            "contract_digest": state["contract_digest"], "profile_digest": state["profile_digest"]}
        state["verification"].pop(criterion["id"], None)
    elif name == "verify":
        _fields(payload, {"criteria", "profile_evidence"}, {"criteria"})
        if state["status"] != "verifying" or not isinstance(payload["criteria"], list) or not payload["criteria"]:
            raise RunStateError("verification requires explicit criteria in the verifying state")
        declared = {item["id"]: item for item in state["contract"]["criteria"]}
        for key in payload["criteria"]:
            if key not in declared:
                raise RunStateError("unknown verification criterion")
            state["verification"][key] = {"binding": _verify_binding(project, state, declared[key], context),
                "observed_at": context["now"], "expires_at": (_time(context["now"]) + timedelta(hours=24)).isoformat()}
        if "profile_evidence" in payload:
            _receipt(context, state, payload["profile_evidence"], "profile")
            state["profile_evidence"] = payload["profile_evidence"]
    elif name == "close":
        _fields(payload, {"status", "reason"}, {"status"})
        if payload["status"] not in TERMINAL:
            raise RunStateError("invalid terminal disposition")
        if payload["status"] == "completed":
            state["completion"] = _complete(project, state, context)
        elif not isinstance(payload.get("reason"), str) or not payload["reason"].strip():
            raise RunStateError("incomplete/cancelled close requires an honest reason")
        children = state.get("extensions", {}).get("workflow", {}).get("children", {})
        running = [child for child in children.values() if child.get("disposition") == "running"]
        if payload["status"] == "cancelled" and (running or _active_native(state)):
            state["status"] = "recovering"
            state["cancellation_requested"] = True
            state["cancellation_reason"] = payload["reason"]
            for child in running:
                child.update(cancellation_requested=True, cancellation_reason=payload["reason"])
            return state  # A request is not observed native termination.
        if _active_native(state) and payload["status"] != "incomplete":
            raise RunStateError("native observation remains unresolved")
        if _active_native(state):
            state["cancellation_requested"] = True
            state["cancellation_reason"] = payload["reason"]
        state["status"] = payload["status"]
        state["terminal"] = {"at": context["now"], "reason": payload.get("reason", "Completion criteria verified")}
    elif name == "effect.prepare":
        _fields(payload, {"id", "target", "payload_digest", "idempotency_key", "authority_ref"}, {"id", "target", "payload_digest", "idempotency_key", "authority_ref"})
        key = _id(payload["id"])
        if not all(isinstance(payload[field], str) for field in payload) or not re.fullmatch(r"[0-9a-f]{64}", payload["payload_digest"]) or not payload["target"] or not payload["idempotency_key"]:
            raise RunStateError("effect intent needs target, payload digest and idempotency key")
        if payload["authority_ref"] and payload["authority_ref"] not in state["contract"]["authority_refs"]:
            raise RunStateError("effect authority reference is not declared; action approval still belongs to its owner")
        previous = state["effects"].get(key)
        if previous and (previous["status"] != "retryable" or any(previous[field] != payload[field] for field in payload)):
            raise RunStateError("effect outcome must be reconciled before resubmission")
        if any(effect["idempotency_key"] == payload["idempotency_key"] and effect["id"] != key for effect in state["effects"].values()):
            raise RunStateError("effect idempotency key already belongs to another intent")
        state["effects"][key] = {**payload, "status": "prepared", "prepared_at": context["now"], "attempt": previous["attempt"] + 1 if previous else 1}
    elif name == "effect.observe":
        _fields(payload, {"id", "status", "evidence"}, {"id", "status", "evidence"})
        item = state["effects"].get(payload["id"])
        if not item or item["status"] != "prepared" or payload["status"] != "unknown":
            raise RunStateError("unverified effect observation can only record an unknown outcome")
        item.update(status="unknown", observation=payload["evidence"], observed_at=context["now"])
    elif name == "effect.reconcile":
        _fields(payload, {"id", "evidence"}, {"id", "evidence"})
        item = state["effects"].get(payload["id"])
        record = _receipt(context, state, payload["evidence"], "effect-readback")
        data = record["data"]
        if not item or any(data.get(key) != item[key] for key in ("id", "target", "payload_digest", "idempotency_key")) or data.get("status") not in {"confirmed", "absent", "cancelled", "failed"}:
            raise RunStateError("effect readback does not bind this intent")
        if item["status"] not in {"prepared", "unknown"} or _time(record["observed_at"]) <= _time(item["prepared_at"]):
            raise RunStateError("effect reconciliation needs an observation after the current attempt")
        if record["digest"] in item.get("used_readbacks", []):
            raise RunStateError("effect readback was already consumed")
        item["used_readbacks"] = item.get("used_readbacks", []) + [record["digest"]]
        item.update(status="retryable" if data["status"] == "absent" else data["status"], evidence=payload["evidence"], reconciled_at=context["now"])
    elif name == "owner.transfer.prepare":
        _fields(payload, {"id", "target", "expires_at"}, {"id", "target", "expires_at"})
        _id(payload["id"], "handoff ID")
        if state.get("handoff", {}).get("status") == "pending":
            raise RunStateError("revoke the existing handoff intent before preparing another")
        target = payload["target"]
        if not isinstance(target, dict) or set(target) != {"session_uuid", "native_ref"}:
            raise RunStateError("handoff target requires exact session_uuid and native_ref only")
        _uuid(target["session_uuid"])
        board = context["binding"]["board"]
        if board != state["owner"]["board"]:
            raise RunStateError("handoff preparation requires the same coordination board")
        # The old owner names an intended recipient from the PM board; it does
        # not impersonate that recipient's native event. Actual target identity
        # and exclusive mutable scope are authenticated only during acceptance.
        row = coordination.find_session(coordination.rows(Path(board).read_text(encoding="utf-8")), target["session_uuid"])
        if (row is None or row.status.lower() != "active" or row.client_ref != target["native_ref"] or
                row.project != state["project_id"] or not row.client_ref or
                row.session_uuid == state["owner"]["session_uuid"] or
                row.client_ref == state["owner"]["native_ref"]):
            raise RunStateError("handoff target must be a distinct native seat in the same project")
        horizon = (_time(payload["expires_at"]) - _time(context["now"])).total_seconds()
        if not 0 < horizon <= MAX_HANDOFF_SECONDS:
            raise RunStateError("handoff expiry must be future and within one hour")
        state["handoff"] = {"id": payload["id"], "status": "pending", "board": board,
            "target": deepcopy(target),
            "source": {key: state["owner"][key] for key in ("session_uuid", "native_ref")},
            "prepared_at": context["now"], "expires_at": payload["expires_at"],
            "prepared_revision": state["revision"] + 1, "state_digest": _handoff_snapshot(state),
            "plan_digest": context["plan_digest"]}
    elif name == "owner.resume":
        observation = context.get("owner_resume")
        if not observation or observation["basis_digest"] != _digest(state):
            raise RunStateError("owner renewal lacks its fresh production observation")
        state.setdefault("ownership_recoveries", []).append({**deepcopy(observation), "at": context["now"]})
        if observation["restart_wait"] is not None:
            wait = state["waits"][observation["restart_wait"]["id"]]
            prior = deepcopy(wait)
            wait.update(status="resolved", resolved_at=context["now"],
                restart_acknowledgment={"prior": prior, "prior_digest": _digest(prior),
                    "ownership_recovery_digest": _digest(observation),
                    "interpretation": payload["reason"], "native_user_message": deepcopy(observation["user_message"]),
                    "authority_granted": False, "scope": "Agent-interpreted restart-pause acknowledgment only; no action approval"})
        state["owner"] = context["binding"]
        state["status"] = "recovering"
    elif name == "owner.transfer.revoke":
        _fields(payload, {"id"}, {"id"})
        intent = state.get("handoff")
        if not intent or intent["status"] != "pending" or intent["id"] != payload["id"]:
            raise RunStateError("matching pending handoff intent is required")
        intent.update(status="revoked", revoked_at=context["now"])
    elif name == "owner.transfer.accept":
        intent = _pending_handoff(project, state, payload)
        proof = context["binding"]
        if any(proof[key] != intent["target"][key] for key in ("session_uuid", "native_ref")):
            raise RunStateError("only the prepared target may accept handoff")
        intent.update(status="accepted", accepted_at=context["now"])
        state["owner"] = proof
        state["status"] = "recovering"
    else:
        raise RunStateError("unknown core command")
    return state


CORE_COMMANDS = frozenset({"transition", "progress", "wait.add", "wait.resolve", "contract.amend", "profile.amend",
    "artifact.register", "input.materialize", "evidence.record", "criterion.evidence.bind", "verify", "close", "effect.prepare", "effect.observe", "effect.reconcile",
    "owner.transfer.prepare", "owner.transfer.accept", "owner.transfer.revoke", "owner.resume"})


def _active_native(state):
    return next((item for item in state.get("native_execution", {}).values()
                 if item["status"] == "pending"), None)


def native_not_started(state, child_id):
    """Journal-owned no-dispatch proof; never a native execution receipt."""
    items = [row for row in state.get("native_execution", {}).values()
             if row.get("child_id") == child_id]
    if len(items) != 1:
        return None
    row = items[0]
    return row if (row.get("schema_version") == 2 and row.get("status") == "not_started"
        and row.get("phase") == "prepared" and row.get("recovery_command")
        and row["id"] not in state.get("observations", {})) else None


def _cancellation_lane(state, command, payload):
    active = _active_native(state)
    if state.get("cancellation_requested") and (command.startswith("observe:") and command == "observe:native_worker"
            or command in {"workflow.dispatch", "workflow.attempt", "workflow.progress"}
            or command == "workflow.task" and payload.get("action") in {"start", "retry", "complete"}
            or command == "close" and payload.get("status") == "completed"):
        raise RunStateError("run cancellation blocks new productive work")
    if active is None:
        return
    child = state.get("extensions", {}).get("workflow", {}).get("children", {}).get(active["child_id"], {})
    allowed = (command == "close" and payload.get("status") in {"cancelled", "incomplete"}
        or command == "workflow.cancel_child" and payload.get("child_id") == active["child_id"]
        or command == "workflow.task" and payload.get("action") == "cancel"
            and payload.get("task_id") == child.get("task_id"))
    if not allowed:
        raise RunStateError("native observation pending; only its authenticated cancellation is admitted")


def _store_native_observation(state, command_id, data, context, proof):
    _json(data)
    if not isinstance(data, dict):
        raise RunStateError("observer did not return typed observation data")
    observed_at = _now()
    observation = {"id": command_id, "kind": "native_worker", "observed_at": observed_at,
        "expires_at": (_time(observed_at) + timedelta(hours=1)).isoformat(), "data": deepcopy(data),
        "bindings": {**{key: state[key] for key in ("run_id", "contract_digest", "profile_digest")},
            **{key: proof[key] for key in ("project_id", "project_root", "session_uuid", "native_ref", "claim_hash", "repository", "branch")}},
        "artifact_digests": {key: item["digest"] for key, item in context["artifacts"].items()}}
    observation["digest"] = _digest(observation)
    state.setdefault("observations", {})[command_id] = observation
    state["evidence"][command_id] = {key: value for key, value in observation.items() if key != "artifact_digests"}
    state["evidence"][command_id].update(artifact_id=f"event:{state['revision'] + 1}", provenance="engine-observation")


def _native_lease_identity(project, path):
    path = safe_path(path, Path(project))
    before = path.lstat()
    if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid()
            or stat.S_IMODE(before.st_mode) != 0o600 or before.st_nlink != 1):
        raise RunStateError("native observer lease is not a private singly linked regular file")
    raw = journal_storage.read_regular(path, 4096)
    after = path.lstat()
    fields = ("st_dev", "st_ino", "st_uid", "st_mode", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns")
    if any(getattr(before, key) != getattr(after, key) for key in fields):
        raise RunStateError("native observer lease changed")
    return {"path": str(path.relative_to(project)), "device": after.st_dev,
        "inode": after.st_ino, "uid": after.st_uid, "mode": stat.S_IMODE(after.st_mode),
        "size": after.st_size, "sha256": hashlib.sha256(raw).hexdigest()}


def _new_native_lease(project, run_id, command_id, nonce, custody, *, command_digest, owner):
    """Acquire original invocation custody, including an uncommitted precursor.

    The caller has replayed the entire journal and rejected every original,
    prepare and dispatch ID. An orphan may be reused only under this exact
    admitted request; its free lock never proves an external/native outcome.
    """
    path = safe_path(_home(project, run_id) / (".native-" + _digest(command_id) + ".lock"), Path(project))
    binding = {"schema_version": 1, "run_id": run_id, "intent_id": command_id,
        "command_digest": command_digest,
        "owner": {key: owner[key] for key in ("session_uuid", "native_ref", "board", "claim_hash", "project_root", "repository", "branch")}}
    record = {**binding, "nonce": nonce, "observer_pid": os.getpid()}
    if len(_json(record)) > 4096:
        raise RunStateError("native observer lease binding exceeds its fixed byte limit")
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        fd = None
    if fd is not None:
        with os.fdopen(fd, "wb") as stream:
            stream.write(_json(record))
            stream.flush()
            os.fsync(stream.fileno())
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    identity = _native_lease_identity(project, path)
    custody.enter_context(bounded_lock(path, create=False, timeout=0.05))
    if _native_lease_identity(project, path) != identity:
        raise RunStateError("native observer lease changed during admission")
    from native_review import _json as strict_json
    retained = strict_json(journal_storage.read_regular(path, 4096))
    if (not isinstance(retained, dict) or set(retained) != set(record)
            or {key: retained[key] for key in binding} != binding
            or type(retained["observer_pid"]) is not int or retained["observer_pid"] <= 0
            or not isinstance(retained["nonce"], str)):
        raise RunStateError("uncommitted native lease does not bind this original request")
    try:
        if str(uuid.UUID(retained["nonce"])) != retained["nonce"]:
            raise ValueError("noncanonical nonce")
    except ValueError as exc:
        raise RunStateError("original native lease nonce is invalid") from exc
    if _native_lease_identity(project, path) != identity:
        raise RunStateError("native observer lease changed after readback")
    return identity, retained["nonce"]


def _check_native_lease(project, intent):
    lease = intent.get("lease")
    expected = _home(project, intent["run_id"]) / (".native-" + _digest(intent["id"]) + ".lock")
    if (not isinstance(lease, dict) or Path(project) / lease["path"] != expected
            or _native_lease_identity(project, expected) != lease):
        raise RunStateError("original native observer custody is unavailable or changed")
    return Path(project) / lease["path"]


def _native_intent_context(project, state, intent, context):
    if (state["run_id"] != intent["run_id"] or state["owner"] != intent["owner"] or context["binding"]["claim_hash"] != intent["owner"]["claim_hash"]
            or context["binding"]["board"] != intent["owner"]["board"]
            or state["contract_digest"] != intent["contract_digest"]
            or state["profile_digest"] != intent["profile_digest"]
            or context["plan_digest"] != intent["plan_digest"]
            or context["artifacts"].get(intent["check_id"], {}).get("digest") != intent["check_digest"]):
        raise RunStateError("original native intent authority or source changed")
    _check_native_lease(project, intent)


def _native_commit_binding(project, state, intent, actor, command, payload):
    """Fresh authority and original content after all receipt/reducer work."""
    proof = _command_binding(project, state, actor, command, payload)
    if (proof["claim_hash"] != intent["owner"]["claim_hash"]
            or proof["board"] != intent["owner"]["board"]
            or state["contract_digest"] != intent["contract_digest"]
            or state["profile_digest"] != intent["profile_digest"]
            or _plan_digest(project, state) != intent["plan_digest"]):
        raise RunStateError("original native authority or plan changed before commit")
    check = state["artifacts"].get(intent["check_id"])
    if not check or check["digest"] != intent["check_digest"]:
        raise RunStateError("original native check changed before commit")
    raw = journal_storage.read_regular(safe_path(Path(project) / check["path"], Path(project)), MAX_JSON_BYTES)
    if hashlib.sha256(raw).hexdigest() != intent["check_digest"]:
        raise RunStateError("original native check bytes changed before commit")
    _check_native_lease(project, intent)
    return proof


def _native_attempt_absent(project, run_id, child_id):
    attempt = safe_path(_home(project, run_id) / "native-worker-attempts" / child_id, Path(project))
    try:
        attempt.lstat()
    except FileNotFoundError:
        return
    raise RunStateError("pre-dispatch intent has unexpected attempt custody; outcome remains unknown")


def _native_receipt_custody(data, context, *, require_cleanup=False):
    """Revalidate the exact retained data and all raw sources at a commit fence."""
    import delegation_boundary
    if not delegation_boundary.verify_worker_observation(data, context):
        raise RunStateError("native receipt or source custody changed before commit")
    if require_cleanup:
        from native_review import _json as strict_json
        receipt = safe_path(Path(data["receipt_path"]), Path(context["project"]))
        raw = journal_storage.read_regular(receipt, delegation_boundary.MAX_FILE_BYTES)
        if (hashlib.sha256(raw).hexdigest() != data["receipt_digest"]
                or strict_json(raw).get("process_cleanup", {}).get("cleanup_verified") is not True):
            raise RunStateError("original native cleanup is not source verified; retain unknown effects")


def _native_recovery_custody(project, state, intent, context):
    current = state["native_execution"][intent["id"]]
    if current["status"] == "not_started" and intent["phase"] == "prepared":
        _native_attempt_absent(project, state["run_id"], intent["child_id"])
    elif current["status"] == "completed" and intent["phase"] == "dispatch_fenced":
        observation = state.get("observations", {}).get(intent["id"], {})
        data = observation.get("data")
        if (observation.get("kind") != "native_worker" or not isinstance(data, dict)
                or _digest(data) != current.get("outcome_digest")):
            raise RunStateError("original native result does not bind its retained observation")
        _native_receipt_custody(data, context, require_cleanup=True)
    else:
        raise RunStateError("native recovery acknowledgement lacks an original result disposition")


def _recover_native_pending(project, run_id, payload, *, expected_revision, command_id,
                            actor, runtime_root, request_binding):
    """Reconcile original custody, never launch or infer an external outcome.

    The original completion and the recovery acknowledgement are separate
    append commit points. A crash between them is retryable without executing
    the observer. Terminal incomplete intervals remain terminal.
    """
    _fields(payload, {"intent_id"}, {"intent_id"})
    original = _id(payload["intent_id"], "original native intent")
    command = "native.execution.recover"
    if command_id == original:
        raise RunStateError("recovery acknowledgement must have its own command identity")
    state = load_run(project, run_id)
    _command_binding(project, state, actor, command, payload)
    lock = _home(project, run_id) / ".run.lock"
    with bounded_lock(lock, create=False), ExitStack() as custody:
        previous = matching = None
        for event in _events(project, run_id):
            previous = event
            if event["command_id"] == command_id:
                matching = event
        state = deepcopy(previous["state"])
        proof = _command_binding(project, state, actor, command, payload)
        material = {"command": command, "payload": payload, "session_uuid": proof["session_uuid"], "native_ref": proof["native_ref"]}
        if request_binding is not None:
            material["request_binding"] = request_binding
        digest = _digest(material)
        # Interrupted original-result commit records this recovery's exact
        # request identity, but not its completed step, for a fresh CAS retry.
        _check_request(state, request_binding)
        if matching:
            if matching["command_digest"] != digest:
                raise RunStateError("command ID was already used with different input")
            return deepcopy(matching["state"])
        if state["revision"] != expected_revision:
            raise RunStateError("stale run revision; reload before retry")
        _require_unlinked_predecessor(project, run_id)
        intent = state.get("native_execution", {}).get(original)
        if not intent or intent.get("schema_version") != 2:
            raise RunStateError("original intent lacks authenticated recoverable observer custody")
        original_request = intent.get("request_binding")
        if (request_binding and original_request
                and request_binding["request_id"] == original_request["request_id"]
                and any(request_binding[key] != original_request[key] for key in ("request_digest", "operation", "initial_revision"))):
            raise RunStateError("recovery cannot reuse the original request identity with another body")
        if state["status"] in TERMINAL and state["status"] != "incomplete":
            raise RunStateError("only incomplete terminal custody can be reconciled without reopening")
        path = _check_native_lease(project, intent)
        custody.enter_context(bounded_lock(path, create=False, timeout=0.05))
        _check_native_lease(project, intent)
        with admission_scope(proof, actor, project) as operation:
            context = _context_observed(project, state, {}, proof, actor=actor, observation=operation)
            context.update(state=deepcopy(state), project=project, actor=deepcopy(actor), admission_observation=operation)
            _native_intent_context(project, state, intent, context)
            if intent["status"] == "pending":
                import delegation_boundary
                attempt = safe_path(_home(project, run_id) / "native-worker-attempts" / intent["child_id"], Path(project))
                receipt_raw = None
                if intent["phase"] == "prepared":
                    _native_attempt_absent(project, run_id, intent["child_id"])
                    disposition = "not_started"
                elif intent["phase"] == "dispatch_fenced":
                    receipt = safe_path(attempt / "receipt.json", Path(project))
                    receipt_raw = journal_storage.read_regular(receipt, delegation_boundary.MAX_FILE_BYTES)
                    from native_review import _json as strict_json
                    manifest = strict_json(receipt_raw)
                    data = {**manifest["data"], "receipt_path": str(receipt),
                            "receipt_digest": hashlib.sha256(receipt_raw).hexdigest()}
                    if (not delegation_boundary.verify_worker_observation(data, context)
                            or manifest.get("process_cleanup", {}).get("cleanup_verified") is not True):
                        raise RunStateError("original native outcome or local cleanup is not source verified; retain unknown effects")
                    if delegation_boundary.observation_intent(state, intent["child_id"]) != manifest["configuration"].get("observation_intent"):
                        raise RunStateError("retained worker outcome belongs to a different original intent")
                    _store_native_observation(state, original, data, context, proof)
                    disposition = "completed"
                else:
                    raise RunStateError("unknown original native dispatch phase")
                state["native_execution"][original] = {**intent, "status": disposition,
                    "recovered_at": _now(), "recovery_command": command_id,
                    "local_observer_custody": "exclusive original lease acquired",
                    "native_termination": "not inferred from observer lease",
                    **({"outcome_digest": _digest(data)} if receipt_raw is not None else {})}
                _command_binding(project, state, actor, command, payload)
                state["revision"] += 1
                state["updated_at"] = _now()
                _record_request(state, intent.get("request_binding"), original, intent["command_digest"])
                # Record the interrupted recovery request basis without falsely
                # marking its acknowledgement step as committed.
                if request_binding:
                    requests = state.setdefault("extensions", {}).setdefault("controller", {"schema_version": 1}).setdefault("requests", {})
                    if len(requests) >= MAX_EVENTS and request_binding["request_id"] not in requests:
                        raise RunStateError("controller request journal capacity reached")
                    requests.setdefault(request_binding["request_id"], {key: request_binding[key] for key in ("request_digest", "operation", "initial_revision")} | {"steps": {}})
                for constraint in _CONSTRAINTS.values():
                    constraint(deepcopy(state), command, deepcopy(payload), context)
                _native_recovery_custody(project, state, intent, context)
                proof = _native_commit_binding(project, state, intent, actor, command, payload)
                _append(project, state, original, intent["command_digest"], "observe:native_worker", previous["digest"], proof)
                previous = None
                for previous in _events(project, run_id):
                    pass
            elif intent["status"] not in {"completed", "not_started"}:
                raise RunStateError("unknown native intent disposition")
        proof = _native_commit_binding(project, state, intent, actor, command, payload)
        with admission_scope(proof, actor, project) as operation:
            context = _context_observed(project, state, {}, proof, actor=actor, observation=operation)
            context.update(state=deepcopy(state), project=project, actor=deepcopy(actor), admission_observation=operation)
            _native_recovery_custody(project, state, intent, context)
        proof = _native_commit_binding(project, state, intent, actor, command, payload)
        state["revision"] += 1
        state["updated_at"] = _now()
        _record_request(state, request_binding, command_id, digest)
        _append(project, state, command_id, digest, command, previous["digest"], proof)
        _project(project, state)
        _index_update(runtime_root, state["owner"]["session_uuid"], run_id, _index_entry(project, state))
        return deepcopy(state)


def _observe_native_pending(project, run_id, payload, **kwargs):
    with ExitStack() as custody:
        return _observe_native_owned(project, run_id, payload, custody=custody, **kwargs)


def _observe_native_owned(project, run_id, payload, *, expected_revision, command_id,
                            actor, runtime_root, request_binding, custody):
    """One durable attempt, with a narrowly fenced concurrent cancellation lane.

    An interruption leaves the pending intent unresolved. Neither retry, a new
    command ID, nor a cold owner restarts it. Outcome custody is committed only
    by this invocation or the source-verifying original-intent recovery owner.
    """
    command = "observe:native_worker"
    lock = _home(project, run_id) / ".run.lock"
    initial = load_run(project, run_id)
    _command_binding(project, initial, actor, command, payload)
    with bounded_lock(lock, create=not lock.exists()):
        previous = None
        for previous in _events(project, run_id):
            pass
        state = deepcopy(previous["state"])
        proof = _command_binding(project, state, actor, command, payload)
        material = {"command": command, "payload": payload, "session_uuid": proof["session_uuid"], "native_ref": proof["native_ref"]}
        if request_binding is not None:
            material["request_binding"] = request_binding
        digest = _digest(material)
        _check_request(state, request_binding)
        prior = state.get("native_execution", {}).get(command_id)
        if prior:
            if prior["command_digest"] != digest:
                raise RunStateError("command ID was already used with different input")
            if prior["status"] == "completed":
                return state
            if prior["status"] == "not_started":
                raise RunStateError("original native intent was finalized as not started; replay is forbidden")
            raise RunStateError("native attempt outcome unresolved; replay is forbidden")
        if state["revision"] != expected_revision:
            raise RunStateError("stale run revision; reload before retry")
        if state["status"] in TERMINAL or state.get("cancellation_requested"):
            raise RunStateError("cancelled or terminal run cannot launch native work")
        if _active_native(state):
            raise RunStateError("another native observation remains unresolved")
        intent_id = "native-intent-" + _digest(command_id)[:32]
        dispatch_id = "native-dispatch-" + _digest(command_id)[:32]
        if any(event["command_id"] in {command_id, intent_id, dispatch_id} for event in _events(project, run_id)):
            raise RunStateError("command or native intent ID was already used")
        _require_unlinked_predecessor(project, run_id)
        with admission_scope(proof, actor, project) as operation:
            context = _context_observed(project, state, payload, proof, actor=actor, observation=operation)
            _fields(payload, {"check_id"}, {"check_id"})
            check = context["artifacts"].get(_id(payload["check_id"], "observer check ID"))
            if not check or check.get("role") != "input":
                raise RunStateError("native observer requires a current registered input")
            spec = _read(safe_path(Path(project) / check["path"], Path(project)))
            if (set(spec) != {"schema_version", "kind", "arguments"} or spec["schema_version"] != 1
                    or spec["kind"] != "native_worker" or not isinstance(spec["arguments"], dict)
                    or set(spec["arguments"]) != {"child_id", "timeout_seconds"}):
                raise RunStateError("invalid native observation specification")
            args = spec["arguments"]
            child_id = _id(args["child_id"])
            child = state.get("extensions", {}).get("workflow", {}).get("children", {}).get(child_id)
            if (not child or child.get("mode") != "native-cli" or child.get("disposition") != "running"
                    or child.get("cancellation_requested") or type(args["timeout_seconds"]) is not int
                    or not 1 <= args["timeout_seconds"] <= 3600):
                raise RunStateError("native observation requires an uncancelled running child")
            if proof["board"] != state["owner"]["board"]:
                raise RunStateError("native dispatch requires the original coordination board")
            nonce = str(uuid.uuid4())
            lease, nonce = _new_native_lease(project, run_id, command_id, nonce, custody,
                command_digest=digest, owner=state["owner"])
            intent = {"schema_version": 2, "nonce": nonce, "phase": "prepared",
                "lease": lease, "run_id": run_id, "observer_pid": os.getpid(), "check_id": payload["check_id"],
                "request_binding": deepcopy(request_binding),
                "id": command_id, "command_digest": digest, "child_id": child_id,
                "status": "pending", "prepared_at": _now(), "prepared_revision": state["revision"] + 1,
                "owner": deepcopy(state["owner"]), "check_digest": check["digest"],
                "contract_digest": state["contract_digest"], "profile_digest": state["profile_digest"],
                "plan_digest": context["plan_digest"]}
            state.setdefault("native_execution", {})[command_id] = intent
            state["revision"] += 1
            state["updated_at"] = _now()
            _command_binding(project, state, actor, command, payload)
            _append(project, state, intent_id,
                    _digest(intent), "native.execution.prepare", previous["digest"], proof)
            _project(project, state)
            _index_update(runtime_root, state["owner"]["session_uuid"], run_id, _index_entry(project, state))
    # PM authority remains required while the run lock is available to cancel.
    # No external caller can provide this closure or finalize another intent.
    def current_cancellation():
        current = load_run(project, run_id)
        fresh = _binding(project, current, actor)
        if (current.get("native_execution", {}).get(command_id) != intent
                or current["owner"] != intent["owner"]
                or fresh["claim_hash"] != proof["claim_hash"]):
            raise RunStateError("native observation intent or authority changed")
        _check_native_lease(project, intent)
        if _plan_digest(project, current) != intent["plan_digest"]:
            raise RunStateError("native observation plan changed")
        registered = current["artifacts"][payload["check_id"]]
        raw = journal_storage.read_regular(safe_path(Path(project) / registered["path"], Path(project)), MAX_JSON_BYTES)
        if hashlib.sha256(raw).hexdigest() != intent["check_digest"]:
            raise RunStateError("native observation input changed")
        current_child = current["extensions"]["workflow"]["children"][child_id]
        node = current["extensions"]["workflow"].get("graph", {}).get("nodes", {}).get(current_child.get("task_id"), {})
        requested = bool(current.get("cancellation_requested") or current_child.get("cancellation_requested")
                         or node.get("status") == "cancelled")
        return {"requested": requested, "run_id": run_id, "child_id": child_id,
                "intent_id": command_id, "revision": current["revision"],
                "reason": current_child.get("cancellation_reason", current.get("cancellation_reason", "Task cancelled")) if requested else None}
    # The irreversible boundary is fenced durably before invoking any adapter.
    # Its presence means effects MAY have started, never that they did.
    with bounded_lock(lock, create=False):
        previous = None
        for previous in _events(project, run_id):
            pass
        state = deepcopy(previous["state"])
        cancellation = current_cancellation()
        if cancellation["requested"]:
            raise RunStateError("native invocation cancelled before dispatch")
        proof = _command_binding(project, state, actor, command, payload)
        intent = {**intent, "phase": "dispatch_fenced", "dispatch_revision": state["revision"] + 1}
        state["native_execution"][command_id] = deepcopy(intent)
        state["revision"] += 1
        state["updated_at"] = _now()
        _append(project, state, dispatch_id, _digest(intent), "native.execution.dispatch", previous["digest"], proof)
        _project(project, state)
        _index_update(runtime_root, state["owner"]["session_uuid"], run_id, _index_entry(project, state))
    proof = _binding(project, state, actor)
    with admission_scope(proof, actor, project) as operation:
        context = _context_observed(project, state, payload, proof, actor=actor, observation=operation)
        context.update(state=deepcopy(state), project=project, actor=deepcopy(actor),
                       admission_observation=operation, current_cancellation=current_cancellation)
        context["criterion_report"] = lambda: criterion_report(state, context)
        current_cancellation()  # Never launch on a stale/revoked intent.
        data = _OBSERVERS["native_worker"](context, deepcopy(payload))
    with bounded_lock(lock, create=False):
        previous = None
        for previous in _events(project, run_id):
            pass
        latest = deepcopy(previous["state"])
        cancellation = current_cancellation()
        proof = _command_binding(project, latest, actor, command, payload)
        with admission_scope(proof, actor, project) as operation:
            final_context = _context_observed(project, latest, payload, proof, actor=actor, observation=operation)
            if final_context["artifacts"][payload["check_id"]]["digest"] != intent["check_digest"]:
                raise RunStateError("native observation specification changed during execution")
        _store_native_observation(latest, command_id, data, context, proof)
        latest["native_execution"][command_id] = {**intent, "status": "completed",
            "outcome_digest": _digest(data), "observed_cancellation": cancellation}
        latest["revision"] += 1
        latest["updated_at"] = _now()
        _record_request(latest, request_binding, command_id, digest)
        for check_constraint in _CONSTRAINTS.values():
            check_constraint(deepcopy(latest), command, deepcopy(payload), final_context)
        # A source-backed receipt must survive registered constraints just as
        # the original plan and actor must. Unbacked diagnostic observations
        # remain unverified data; downstream worker intake still refuses them.
        if "receipt_path" in data or "receipt_digest" in data:
            proof = _native_commit_binding(project, latest, intent, actor, command, payload)
            with admission_scope(proof, actor, project) as operation:
                final_context = _context_observed(project, latest, payload, proof, actor=actor, observation=operation)
                final_context.update(state=deepcopy(latest), project=project, actor=deepcopy(actor), admission_observation=operation)
                _native_receipt_custody(data, final_context)
        proof = _native_commit_binding(project, latest, intent, actor, command, payload)
        _append(project, latest, command_id, digest, command, previous["digest"], proof)
        _project(project, latest)
        _index_update(runtime_root, latest["owner"]["session_uuid"], run_id, _index_entry(project, latest))
        return deepcopy(latest)


_LATE_NATIVE_CUSTODY = frozenset({"workflow.worker_record", "workflow.return", "workflow.integrate",
                                 "artifact.register", "evidence.record"})


def _terminal_native_custody(project, state, command, payload, context):
    """Permit only late original-child custody, never reopen a closed interval."""
    if state["status"] != "incomplete" or _active_native(state) or command not in _LATE_NATIVE_CUSTODY:
        raise RunStateError("terminal run cannot be reopened")
    intents = {row["child_id"]: row for row in state.get("native_execution", {}).values()
               if row.get("schema_version") == 2 and row["status"] in {"completed", "not_started"}}
    child_id = payload.get("child_id")
    if command in {"artifact.register", "evidence.record"}:
        if command == "artifact.register":
            if (payload.get("role") != "evidence" or payload.get("required") is not False
                    or payload.get("id") in state["artifacts"]):
                raise RunStateError("terminal custody accepts only a new nonrequired native child audit artifact")
            path = Path(payload["path"])
            path = safe_path(path if path.is_absolute() else Path(project) / path, Path(project))
        else:
            artifact = context["artifacts"].get(payload.get("artifact_id"), {})
            if payload.get("kind") != "child_integration" or artifact.get("role") != "evidence":
                raise RunStateError("terminal custody accepts only native child audit evidence")
            path = safe_path(Path(project) / artifact["path"], Path(project))
        raw = journal_storage.read_regular(path, MAX_JSON_BYTES)
        from native_review import _json as strict_json
        record = strict_json(raw)
        child_id = record.get("data", {}).get("child_id")
        if record.get("kind") != "child_integration" or child_id not in intents:
            raise RunStateError("terminal audit does not bind an original reconciled child")
        if context["binding"]["board"] != intents[child_id]["owner"]["board"]:
            raise RunStateError("terminal native custody requires its original coordination board")
        from evidence_bridge import verify_source
        owned = {**context, "state": state, "project": project}
        if not verify_source(record, owned):
            raise RunStateError("terminal audit lacks current independent native source proof")
        def recheck():
            if (journal_storage.read_regular(path, MAX_JSON_BYTES) != raw
                    or not verify_source(record, owned)):
                raise RunStateError("terminal child audit changed before append")
        return recheck
    intent = intents.get(child_id)
    child = state.get("extensions", {}).get("workflow", {}).get("children", {}).get(child_id)
    if not intent or not child:
        raise RunStateError("terminal custody must name its original reconciled child")
    if context["binding"]["board"] != intent["owner"]["board"]:
        raise RunStateError("terminal native custody requires its original coordination board")
    if command == "workflow.worker_record" and (intent["status"] != "completed" or payload.get("receipt_id") != intent["id"]):
        raise RunStateError("terminal worker intake must use the exact original observation")
    if command == "workflow.return":
        if intent["status"] == "not_started":
            if payload.get("disposition") not in {"failed", "cancelled"} or payload.get("artifact_ids") or payload.get("evidence_ids"):
                raise RunStateError("undispatched child cannot claim work or native success")
        elif child.get("worker_receipt_id") != intent["id"]:
            raise RunStateError("terminal child return requires its original verified worker intake")
    # Existing reducers retain source verification, independent audit, artifact
    # equality and immutable actual/unknown settlement semantics.
    return lambda: None


def _constraint_snapshot(state):
    """Copy exact ordinary builtin graphs, including shared containers.

    These bytes are self-produced, operation-local and never persisted or read
    from state/external input. Exact-type validation excludes object reducers.
    Each load preserves container aliases/cycles and dictionary insertion order
    within an independent copy. Exotic values retain deepcopy behavior; durable
    JSON refusal and every constraint/native admission invocation are unchanged.
    """
    import math
    pending, seen = [state], set()
    while pending:
        item = pending.pop()
        kind = type(item)
        if kind is dict or kind is list:
            identity = id(item)
            if identity in seen:
                continue
            seen.add(identity)
            if kind is dict:
                if any(type(key) is not str for key in item):
                    return None
                pending.extend(item.values())
            else:
                pending.extend(item)
        elif kind is float:
            if not math.isfinite(item):
                return None
        elif not (kind is str or kind is int or kind is bool or kind is type(None)):
            return None
    try:
        # Only the exact builtin graph validated above reaches pickle. No
        # object reducer can run; memoization retains shared-container identity.
        # This is not a journal/input format or an authority cache.
        raw = pickle.dumps(state, protocol=pickle.HIGHEST_PROTOCOL)
    except (pickle.PickleError, TypeError, ValueError, OverflowError, RecursionError):
        return None
    return raw if len(raw) <= journal_storage.MAX_LOGICAL_BYTES else None


def _copy_state(value):
    """Independent bulk copy through the existing exact-builtin copy boundary.

    Authority objects and other nonordinary values retain deepcopy semantics.
    The serialization is produced and consumed here, never supplied by a caller.
    """
    snapshot = _constraint_snapshot(value)
    return pickle.loads(snapshot) if snapshot is not None else deepcopy(value)


def apply_command(project: Path, run_id: str, command: str, payload: dict, *, expected_revision: int,
                  command_id: str, actor: dict, runtime_root: Path | None = None,
                  request_binding: dict | None = None) -> dict:
    _id(command_id, "command ID")
    request_binding = _request_binding(request_binding)
    if type(expected_revision) is not int or expected_revision < 1 or not isinstance(payload, dict):
        raise RunStateError("mutation requires an integer expected revision and object payload")
    project = Path(project).resolve(strict=True)
    if command == "native.execution.recover":
        return _recover_native_pending(project, run_id, payload, expected_revision=expected_revision,
            command_id=command_id, actor=actor, runtime_root=runtime_root, request_binding=request_binding)
    if command == "observe:native_worker" and "native_worker" in _OBSERVERS:
        return _observe_native_pending(project, run_id, payload, expected_revision=expected_revision,
            command_id=command_id, actor=actor, runtime_root=runtime_root, request_binding=request_binding)
    state = load_run(project, run_id)
    lock = _home(project, run_id) / ".run.lock"
    try:
        lock.lstat()
        create_lock = False
    except FileNotFoundError:
        create_lock = True
    # Existing locks can be acquired without changing the filesystem. Authority
    # is freshly checked inside that lock and again after reducer work. Creating
    # a missing lock remains a filesystem mutation and needs prior admission.
    if create_lock:
        _command_binding(project, state, actor, command, payload)
    with bounded_lock(lock, create=create_lock):
        history = _verified_history(project, run_id)
        if history is None:
            previous = matching = None
            for event in _events(project, run_id):
                previous = event
                if event["command_id"] == command_id:
                    matching = event
        else:
            previous = history["last"]
            matching = next((row for row in history["rows"] if row["command_id"] == command_id), None)
            if matching is not None:
                selected = _read(_home(project, run_id) / "events" / f"{matching['revision']:012d}.json")
                if (selected.get("digest") != matching["digest"]
                        or _digest({key: value for key, value in selected.items() if key != "digest"}) != matching["digest"]):
                    raise RunStateError("replayed event differs from verified history")
                _fence_history(history)
                matching = selected
        state = _copy_state(previous["state"])
        proof = _command_binding(project, state, actor, command, payload)
        material = {"command": command, "payload": payload, "session_uuid": proof["session_uuid"], "native_ref": proof["native_ref"]}
        if request_binding is not None:
            material["request_binding"] = request_binding
        digest = _digest(material)
        _check_request(state, request_binding)
        if matching is not None:
            if matching["command_digest"] != digest:
                raise RunStateError("command ID was already used with different input")
            _project(project, state)
            return _copy_state(matching["state"])
        if state["revision"] != expected_revision:
            raise RunStateError("stale run revision; reload before retry")
        late_custody = state["status"] == "incomplete" and command in _LATE_NATIVE_CUSTODY
        if state["status"] in TERMINAL and command not in _TERMINAL_COMMANDS and not late_custody:
            raise RunStateError("terminal run cannot be reopened; create a new run identity")
        _require_unlinked_predecessor(project, run_id)
        _cancellation_lane(state, command, payload)
        # Trusted sources and the bounded observer share this one admitted
        # operation. Pure reducer context never contains the token, and the
        # scope ends before the fresh mutation admission below.
        with admission_scope(proof, actor, project) as operation:
            context = _context_observed(project, state, payload, proof, actor=actor, observation=operation)
            if command == "owner.resume":
                context["owner_resume"] = deepcopy(getattr(proof, "_owner_resume_observation", None))
            late_check = _terminal_native_custody(project, state, command, payload,
                {**context, "actor": actor, "admission_observation": operation}) if late_custody else None
            context["journal_head"] = {"revision": state["revision"], "digest": previous["digest"], "scope": "full_run"}
            context["current_native_invalidation"] = _native_readback(project, state, actor, context["journal_head"], invalidation=True, owner_reconcile=True)
            updated = _copy_state(state)
            if command.startswith("observe:") and command.split(":", 1)[1] in _OBSERVERS:
                if command_id in state["evidence"] or command_id in state.get("observations", {}):
                    raise RunStateError("observation attempt IDs are immutable; use a new command ID")
                _fields(payload, {"check_id"}, {"check_id"})
                check_id = _id(payload["check_id"], "observer check ID")
                if check_id not in context["artifacts"]:
                    raise RunStateError("observer requires a current registered artifact specification")
                kind = command.split(":", 1)[1]
                observer_context = {**context, "state": _copy_state(state), "project": project, "actor": deepcopy(actor),
                                    "admission_observation": operation}
                observer_context["criterion_report"] = lambda: criterion_report(state, context)
                data = _OBSERVERS[kind](observer_context, deepcopy(payload))
                if not isinstance(data, dict):
                    raise RunStateError("observer did not return typed observation data")
                _json(data)
                observed_at = _now()
                observation = {"id": command_id, "kind": kind, "observed_at": observed_at,
                    "expires_at": (_time(observed_at) + timedelta(hours=1)).isoformat(), "data": deepcopy(data),
                    "bindings": {**{key: state[key] for key in ("run_id", "contract_digest", "profile_digest")},
                        **{key: proof[key] for key in ("project_id", "project_root", "session_uuid", "native_ref", "claim_hash", "repository", "branch")}},
                    "artifact_digests": {key: item["digest"] for key, item in context["artifacts"].items()}}
                observation["digest"] = _digest(observation)
                updated.setdefault("observations", {})[command_id] = observation
                updated["evidence"][command_id] = {key: value for key, value in observation.items() if key != "artifact_digests"}
                updated["evidence"][command_id].update(artifact_id=f"event:{state['revision'] + 1}", provenance="engine-observation")
            elif command in CORE_COMMANDS:
                updated = _reduce(project, updated, command, deepcopy(payload), context)
            else:
                reducer = _COMMANDS.get(command)
                if reducer is None:
                    raise RunStateError("unknown run command")
                prepared = deepcopy(payload)
                if command in _PREPARERS:
                    observer_context = {**context, "state": _copy_state(state), "project": project,
                        "actor": deepcopy(actor), "admission_observation": operation,
                        "command_id": command_id, "command_digest": digest, "runtime_root": _runtime(runtime_root)}
                    observer_context["criterion_report"] = lambda: criterion_report(state, context)
                    prepared = _PREPARERS[command](observer_context, prepared)
                    # Trusted owner observations use the journal's logical bound;
                    # MAX_JSON_BYTES limits physical files, not decoded records.
                    if (not isinstance(prepared, dict)
                            or len(_json(prepared)) + 1 > journal_storage.MAX_LOGICAL_BYTES):
                        raise RunStateError("command preparer returned invalid or oversized data")
                updated = reducer(updated, prepared, context)
                if not isinstance(updated, dict) or {k: v for k, v in updated.items() if k != "extensions"} != {k: v for k, v in state.items() if k != "extensions"} or not isinstance(updated.get("extensions"), dict):
                    raise RunStateError("extension reducer attempted to modify protected core fields")
        updated["revision"] = state["revision"] + 1
        updated["updated_at"] = _now()
        _record_request(updated, request_binding, command_id, digest)
        constraint_snapshot = _constraint_snapshot(updated) if _CONSTRAINTS else None
        for check in _CONSTRAINTS.values():
            constraint_state = (pickle.loads(constraint_snapshot) if constraint_snapshot is not None
                                else deepcopy(updated))
            check(constraint_state, command, deepcopy(payload), context)
        # Re-admit after reducer work: a revoked seat must not commit after a
        # slow local verifier or a concurrent board mutation.
        if late_check is not None:
            late_proof = _command_binding(project, state, actor, command, payload)
            with admission_scope(late_proof, actor, project) as late_operation:
                late_context = _context_observed(project, state, payload, late_proof, actor=actor, observation=late_operation)
                _terminal_native_custody(project, state, command, payload,
                    {**late_context, "actor": actor, "admission_observation": late_operation})()
            if updated["status"] != state["status"] or updated["terminal"] != state["terminal"]:
                raise RunStateError("late custody cannot reopen or change the terminal outcome")
        final_proof = _command_binding(project, state, actor, command, payload)
        if (command == "owner.resume" and getattr(final_proof, "_owner_resume_observation", None)
                != getattr(proof, "_owner_resume_observation", None)):
            raise RunStateError("owner renewal native observation changed before commit")
        if updated["owner"]["session_uuid"] != state["owner"]["session_uuid"]:
            _native_index_update(runtime_root, updated["owner"])
            _index_update(runtime_root, updated["owner"]["session_uuid"], run_id, _index_entry(project, updated, "pending"))
        _append(project, updated, command_id, digest, command, previous["digest"], proof)
        _project(project, updated)
        _index_update(runtime_root, state["owner"]["session_uuid"], run_id, _index_entry(project, updated,
                      "transferred" if updated["owner"]["session_uuid"] != state["owner"]["session_uuid"] else None))
        if updated["owner"]["session_uuid"] != state["owner"]["session_uuid"]:
            _index_update(runtime_root, updated["owner"]["session_uuid"], run_id, _index_entry(project, updated))
        return _copy_state(updated)


def owned_runs(actor: dict, *, runtime_root: Path | None = None, include_terminal: bool = False) -> list[dict]:
    return [state for state in _owned_records(actor, runtime_root=runtime_root, require_admission=True)
            if include_terminal or state["status"] not in TERMINAL]


def inspect_owned_runs(actor, *, runtime_root=None):
    """One fresh PM admission per nonterminal run for a passive Stop read.

    This is a combined discovery/inspection operation, not an admission cache.
    No proof survives the call or substitutes for mutation-time admission.
    Released terminal seats retain their tombstones without a live claim.
    """
    result = []
    for state in _owned_records(actor, runtime_root=runtime_root, require_admission=False):
        if state["status"] in TERMINAL:
            continue
        project = Path(state["owner"]["project_root"])
        proof = _binding(project, state, actor, readonly=True, passive=True)
        context = _context(project, state, {}, proof, actor=actor, purpose="passive-stop")
        head = _read(_home(project, state["run_id"]) / "events" / f"{state['revision']:012d}.json")
        if (head.get("state") != state or head.get("digest") != _digest({key: value for key, value in head.items() if key != "digest"})):
            raise RunStateError("journal head changed after passive owner discovery")
        # _owned_records already verified this chain; a later append only makes
        # this deny/candidate screen stale. Reservation re-admits under CAS.
        context["journal_head"] = {"revision": state["revision"], "digest": head["digest"], "scope": "full_run"}
        context["current_native_events"] = _native_readback(project, state, actor, context["journal_head"], passive=True)
        context["current_native_invalidation"] = _native_readback(project, state, actor, context["journal_head"], passive=True, invalidation=True)
        result.append((state, context))
    return result


def _owned_records(actor, *, runtime_root=None, require_admission=True):
    """Native Stop discovery reads one owner index, never all host run JSON."""
    owners = _runtime(runtime_root) / "owners"
    if not owners.exists():
        return []
    if owners.is_symlink() or not owners.is_dir():
        raise RunStateError("invalid owner index directory")
    # Native identity is independent of active write permission. Its narrowly
    # scoped index still locates terminal tombstones after the PM seat releases.
    client, native = observer_native_identity(actor["native_payload"])
    native_path = _native_index_path(runtime_root, client, native)
    native_index = _native_index_read(native_path, client, native)
    result = []
    for owner in native_index["owners"]:
        path = _index_path(runtime_root, owner)
        if not path.is_file():
            raise RunStateError("native owner pointer has no owned run index")
        index = _index_read(path, owner)
        for run_id, entry in index["runs"].items():
            if not isinstance(entry, dict) or entry.get("run_id") != run_id:
                raise RunStateError("invalid owned index entry")
            if entry.get("status") == "transferred":
                continue
            state = load_run(Path(entry["project"]), run_id)
            if state["owner"]["session_uuid"] != owner:
                continue  # Transfer committed before old-index cleanup.
            if (state["owner"]["client"], state["owner"]["native_session_id"]) != (client, native):
                raise RunStateError("owned index does not bind the current native seat")
            if require_admission and state["status"] not in TERMINAL:
                _binding(Path(entry["project"]), state, actor, readonly=True)
            result.append(state)
    return result


def discover_legacy(actor, legacy_root, *, plan=None, runtime_root=None, _paths=None, _desktop_bindings=None):
    """Bounded read-only upgrade inventory, scoped before semantic validation.

    Foreign or unattributed bytes are retained. A corrupt candidate containing
    this native identity (or the explicitly requested plan's exact filename)
    is blocking. Unattributed foreign corruption is diagnostic, never success
    evidence and never a reason to mutate somebody else's registry record.
    """
    root = Path(legacy_root).expanduser().absolute()
    result = {"owned_active": [], "owned_terminal": [], "imported": [], "foreign_count": 0,
              "unattributed": [], "scanned": 0, "truncated": False}
    if not root.exists():
        return result
    if root.is_symlink() or not root.is_dir():
        raise RunStateError("legacy registry directory is unsafe")
    client, native = observer_native_identity(actor["native_payload"])
    scheme = {"claude": "cc", "codex": "codex", "muse": "muse"}[client]
    native_ref = f"{scheme}:{native}"
    # The native index gives previously bound seats without requiring a fresh
    # write claim; this is discovery only. A current board seat is an optional
    # additional selector for old pre-index engagements.
    runtime_root = Path(runtime_root) if runtime_root is not None else root.parent
    natives = _native_index_read(_native_index_path(runtime_root, client, native), client, native)
    owners = set(natives["owners"])
    refs = {native_ref}
    board = Path(actor["board"])
    if board.is_file() and not board.is_symlink():
        from board_grammar import parse_table_rows
        from project_state import row_for_event
        row = row_for_event(parse_table_rows(board.read_text(encoding="utf-8")), actor["native_payload"], board=board)
        if row:
            owners.add(row["session uuid"])
            refs.add(row["client session ref"])
    imported = {state.get("migration", {}).get("source_digest") for state in
                _owned_records(actor, runtime_root=runtime_root, require_admission=False)}
    exact = None
    if plan is not None:
        target = Path(plan).expanduser().absolute()
        key = hashlib.sha1(str(target).encode()).hexdigest()[:12]
        exact = root / f"{target.stem[:40]}-{key}.json"
    if _paths is not None:
        paths = sorted(set(_paths))
    elif plan is not None:
        paths = [exact] if exact.exists() else []
    else:
        paths = sorted(root.glob("*.json"))
    if len(paths) > 512 and _paths is None:
        result["truncated"] = True
        paths = paths[:512]
    total = 0
    for path in paths:
        result["scanned"] += 1
        selected_desktop = path.name in (_desktop_bindings or {})
        if path.is_symlink() or not path.is_file():
            result["unattributed"].append({"source": str(path), "reason": "unsafe record", "blocking": path == exact or selected_desktop})
            continue
        size = path.stat().st_size
        total += min(size, MAX_JSON_BYTES)
        if total > 32 * 1024 * 1024 and _paths is None:
            result["truncated"] = True
            break
        with path.open("rb") as stream:
            raw = stream.read(MAX_JSON_BYTES + 1)
        identity_hint = selected_desktop or any(marker.encode() in raw for marker in refs | owners)
        try:
            if len(raw) > MAX_JSON_BYTES:
                raise ValueError("oversized record")
            legacy = json.loads(raw)
            if not isinstance(legacy, dict):
                raise ValueError("record is not an object")
        except (ValueError, UnicodeError) as exc:
            result["unattributed"].append({"source": str(path), "reason": str(exc), "blocking": identity_hint or path == exact})
            continue
        # Validate retained identity before accepting any alternative selector.
        # A matching modern seat/native reference cannot erase a contradiction
        # in this record's previously observed desktop host and seat binding.
        desktop = (_desktop_bindings or {}).get(path.name)
        if desktop is not None and (legacy.get("client_session_ref") != desktop["host_ref"]
                or legacy.get("session_id") != desktop["session_uuid"]):
            result["unattributed"].append({"source": str(path), "reason": "Indexed desktop legacy binding changed", "blocking": True})
            continue
        if desktop is None and legacy.get("client_session_ref") not in refs and legacy.get("session_id") not in owners:
            # Historical binding is discovery only. A released seat never
            # regains mutation authority, even when this record is selected.
            if path == exact and str(legacy.get("client_session_ref", "")).startswith("ccd:"):
                # Explicit plan selection is causal relevance, not proof of
                # identity. Closed records need no continued execution.
                if legacy.get("status") not in {"closed", "completed", "incomplete", "cancelled"}:
                    result["unattributed"].append({"source": str(path), "reason": "Selected desktop legacy native binding is unavailable", "blocking": True})
                continue
            else:
                if legacy.get("client_session_ref") or legacy.get("session_id"):
                    result["foreign_count"] += 1
                else:
                    result["unattributed"].append({"source": str(path), "reason": "record has no bound native owner", "blocking": path == exact})
                continue
        digest = hashlib.sha256(raw).hexdigest()
        item = {"source": str(path), "sha256": digest, "plan": legacy.get("plan"), "project_id": legacy.get("project_id")}
        if digest in imported:
            result["imported"].append(item)
        elif legacy.get("status") in {"closed", "completed", "incomplete", "cancelled"}:
            result["owned_terminal"].append(item)
        else:
            result["owned_active"].append(item)
    return result


def _legacy_index_home(root, runtime_root):
    return _runtime(runtime_root if runtime_root is not None else root.parent) / "legacy-index"


def _legacy_selector_path(home, kind, identity):
    return home / kind / (hashlib.sha256(identity.encode()).hexdigest() + ".json")


def _desktop_legacy_binding(board, value):
    """Observe one exact PM sidecar before release removes its native mapping."""
    from peer_addressing import CLIENT_CLAUDE, read_seat, seat_path
    session = _uuid(value.get("session_id"))
    path = seat_path(Path(board), session)
    if path.is_symlink() or path.parent.is_symlink() or not path.is_file() or path.stat().st_size > MAX_JSON_BYTES:
        raise RunStateError("Desktop legacy native binding is unavailable or unsafe")
    raw = path.read_bytes()
    seat = read_seat(Path(board), session, strict=True)
    if (seat is None or seat.client != CLIENT_CLAUDE or not seat.host_session_id
            or "ccd:" + seat.host_session_id != value.get("client_session_ref")
            or path.read_bytes() != raw):
        raise RunStateError("Desktop legacy native binding does not match its PM sidecar")
    native = _uuid(seat.harness_session_id)
    return {"native_ref": "cc:" + native, "host_ref": "ccd:" + seat.host_session_id,
            "session_uuid": session, "sidecar_sha256": hashlib.sha256(raw).hexdigest()}


def _validate_desktop_binding(name, binding):
    if (not isinstance(name, str) or Path(name).name != name or not name.endswith(".json")
            or not isinstance(binding, dict)
            or set(binding) != {"native_ref", "host_ref", "session_uuid", "sidecar_sha256"}
            or not isinstance(binding["native_ref"], str) or not binding["native_ref"].startswith("cc:")
            or not isinstance(binding["host_ref"], str) or not binding["host_ref"].startswith("ccd:")
            or not 4 < len(binding["host_ref"]) <= 4096
            or not isinstance(binding["sidecar_sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", binding["sidecar_sha256"])):
        raise RunStateError("invalid retained desktop legacy binding")
    _uuid(binding["session_uuid"])
    _uuid(binding["native_ref"][3:])


def _retained_desktop_bindings(home, root):
    path = home / "manifest.json"
    if not path.exists():
        return {}
    prior = _read(path)
    if prior.get("schema_version") != SCHEMA or prior.get("root") != str(root):
        raise RunStateError("legacy inventory manifest does not bind this registry")
    retained = prior.get("desktop_bindings", {})
    if not isinstance(retained, dict):
        raise RunStateError("invalid retained desktop legacy bindings")
    for name, binding in retained.items():
        _validate_desktop_binding(name, binding)
    return retained


def index_legacy(actor, legacy_root, *, runtime_root=None):
    """Explicit migration preparation, outside Stop. Preserve all source bytes.

    Each record read is bounded; the inventory streams all filenames instead of
    imposing a global foreign-record count on another native task. This is a
    host-local discovery projection, never an ownership transfer or adoption.
    Unknown records are diagnostics and cannot invalidate attributed selectors.
    """
    root = Path(legacy_root).expanduser().absolute()
    observer_native_identity(actor["native_payload"])
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        raise RunStateError("legacy registry directory is unsafe")
    home = _legacy_index_home(root, runtime_root)
    selectors, desktop_bindings, unknown, scanned = {}, {}, [], 0
    retained = _retained_desktop_bindings(home, root)
    for name, binding in retained.items():
        identity = binding["native_ref"]
        selectors.setdefault(("native", identity), set()).add(name)
        desktop_bindings.setdefault(identity, {})[name] = binding
        if not (root / name).exists():
            unknown.append({"source": str(root / name), "reason": "Previously indexed desktop source disappeared", "status": "UNKNOWN"})
    identity_pattern = re.compile(rb"(?:cc:|codex:|muse:)?[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
    for path in sorted(root.glob("*.json")):
        scanned += 1
        identities = []
        try:
            if path.is_symlink() or not path.is_file():
                raise ValueError("unsafe record")
            with path.open("rb") as stream:
                raw = stream.read(MAX_JSON_BYTES + 1)
            try:
                if len(raw) > MAX_JSON_BYTES:
                    raise ValueError("oversized record")
                value = json.loads(raw)
                if not isinstance(value, dict):
                    raise ValueError("record is not an object")
                identities = [(kind, value[field]) for kind, field in
                    (("native", "client_session_ref"), ("seats", "session_id"))
                    if isinstance(value.get(field), str) and value[field]]
                if not identities:
                    raise ValueError("record has no bound owner")
                if str(value.get("client_session_ref", "")).startswith("ccd:"):
                    try:
                        binding = _desktop_legacy_binding(actor["board"], value)
                        if path.name in retained and any(retained[path.name][key] != binding[key]
                                for key in ("native_ref", "host_ref", "session_uuid")):
                            raise RunStateError("Previously indexed desktop binding changed; retained original discovery evidence")
                        identity = binding["native_ref"]
                        identities.append(("native", identity))
                        desktop_bindings.setdefault(identity, {})[path.name] = binding
                        retained[path.name] = binding
                    except (OSError, ValueError) as exc:
                        if value.get("status") not in {"closed", "completed", "incomplete", "cancelled"}:
                            unknown.append({"source": str(path), "reason": str(exc), "status": "UNKNOWN"})
            except (ValueError, UnicodeError) as exc:
                unknown.append({"source": str(path), "reason": str(exc), "status": "UNKNOWN"})
                # A malformed own record must remain discoverable. Hints only
                # select it for validation; they never grant ownership.
                identities = [("native" if b":" in marker else "seats", marker.decode())
                              for marker in identity_pattern.findall(raw)]
            for kind, identity in identities:
                selectors.setdefault((kind, identity), set()).add(path.name)
        except (OSError, ValueError) as exc:
            unknown.append({"source": str(path), "reason": str(exc), "status": "UNKNOWN"})
    generation = str(uuid.uuid4())
    with bounded_lock(home / ".index.lock"):
        # Another explicit index operation may have observed the last sidecar
        # before release. Do not erase its proof with our older scan snapshot.
        for name, binding in _retained_desktop_bindings(home, root).items():
            if name in retained and any(retained[name][key] != binding[key]
                    for key in ("native_ref", "host_ref", "session_uuid")):
                raise RunStateError("Concurrent desktop legacy binding changed; preserve the committed inventory")
            retained.setdefault(name, binding)
            identity = retained[name]["native_ref"]
            selectors.setdefault(("native", identity), set()).add(name)
            desktop_bindings.setdefault(identity, {})[name] = retained[name]
        generation_home = home / "generations" / generation
        for directory in ("native", "seats"):
            (generation_home / directory).mkdir(parents=True, exist_ok=True)
        for (kind, identity), names in selectors.items():
            selected = {"schema_version": SCHEMA, "generation": generation, "identity": identity, "sources": sorted(names)}
            if kind == "native" and identity in desktop_bindings:
                selected["desktop_bindings"] = desktop_bindings[identity]
            _write(_legacy_selector_path(generation_home, kind, identity), _json(selected) + b"\n")
        # A complete generation commits through one manifest replacement;
        # concurrent Stop readers cannot mix old and newly built selectors.
        _write(home / "manifest.json", _json({"schema_version": SCHEMA, "root": str(root),
               "generation": generation, "scanned": scanned, "unattributed_count": len(unknown),
               "desktop_bindings": retained}) + b"\n")
    return {"health": "PASS", "scanned": scanned, "unattributed": unknown, "index": str(home)}


def legacy_for_stop(actor, legacy_root, *, plan=None, runtime_root=None):
    """Read exact plan plus this native/seat selectors, never a global scan."""
    root = Path(legacy_root).expanduser().absolute()
    home = _legacy_index_home(root, runtime_root)
    empty = {"owned_active": [], "owned_terminal": [], "imported": [], "foreign_count": 0,
             "unattributed": [], "scanned": 0, "truncated": False, "health": "PASS"}
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        raise RunStateError("legacy registry directory is unsafe")
    manifest_path = home / "manifest.json"
    if not manifest_path.exists():
        if next(root.glob("*.json"), None) is None:
            return empty
        return {**empty, "health": "UNKNOWN", "action": "Run autopilot doctor --index-legacy outside Stop to prepare native ownership lookup"}
    manifest = _read(manifest_path)
    if manifest.get("schema_version") != SCHEMA or manifest.get("root") != str(root):
        raise RunStateError("legacy inventory manifest does not bind this registry")
    generation_home = home / "generations" / _uuid(manifest.get("generation"))
    client, native = observer_native_identity(actor["native_payload"])
    native_ref = {"claude": "cc", "codex": "codex", "muse": "muse"}[client] + ":" + native
    runtime = runtime_root if runtime_root is not None else root.parent
    owners = set(_native_index_read(_native_index_path(runtime, client, native), client, native)["owners"])
    board = Path(actor["board"])
    row = None
    if board.is_file() and not board.is_symlink():
        from board_grammar import parse_table_rows
        from project_state import row_for_event
        row = row_for_event(parse_table_rows(board.read_text(encoding="utf-8")), actor["native_payload"], board=board)
        if row:
            owners.add(row["session uuid"])
    paths, desktop_bindings = set(), {}
    if plan is None and board.is_file() and row:
        from project_state import _project_from_claim, _load_json, STATE_FILE
        from plan_reference import locate_plan
        project = _project_from_claim(row)
        if project is not None:
            state_path = project / STATE_FILE
            state = _load_json(state_path) if state_path.exists() else None
            reference = locate_plan(project, (project / "CONTEXT.md").read_text(encoding="utf-8"),
                **({"controlling_plan": state.get("controlling_plan")} if state else {}))
            if reference.declared is not None and reference.resolved is None:
                raise RunStateError(reference.detail)
            plan = reference.resolved
    for kind, identity in [("native", native_ref)] + [("seats", owner) for owner in owners]:
        path = _legacy_selector_path(generation_home, kind, identity)
        if not path.exists():
            continue
        selected = _read(path)
        if selected.get("schema_version") != SCHEMA or selected.get("identity") != identity:
            raise RunStateError("selected legacy owner index is invalid")
        if selected.get("generation") != manifest["generation"]:
            raise RunStateError("selected legacy generation does not match manifest")
        bindings = selected.get("desktop_bindings", {})
        if not isinstance(bindings, dict):
            raise RunStateError("invalid desktop legacy bindings")
        for name, binding in bindings.items():
            _validate_desktop_binding(name, binding)
            if (kind != "native" or identity != native_ref or client != "claude"
                    or binding["native_ref"] != native_ref
                    or name not in selected.get("sources", [])):
                raise RunStateError("desktop legacy binding does not select this native observer")
            desktop_bindings[name] = binding
        for name in selected.get("sources", []):
            if not isinstance(name, str) or Path(name).name != name or not name.endswith(".json"):
                raise RunStateError("unsafe indexed legacy source")
            path = root / name
            if not path.exists():
                raise RunStateError("selected legacy source disappeared; refresh explicit inventory")
            paths.add(path)
    if plan is not None:
        target = Path(plan).expanduser().absolute()
        key = hashlib.sha1(str(target).encode()).hexdigest()[:12]
        path = root / f"{target.stem[:40]}-{key}.json"
        if path.exists():
            paths.add(path)
    return {**discover_legacy(actor, root, plan=plan, runtime_root=runtime, _paths=paths, _desktop_bindings=desktop_bindings), "health": "PASS",
            "inventory_unattributed": manifest.get("unattributed_count", 0)}


def import_legacy(project: Path, source: Path, *, project_id: str, plan: Path, contract: dict,
                  actor: dict, command_id: str, runtime_root: Path | None = None,
                  profile: dict | None = None) -> dict:
    """Preserve bytes and historical evidence; never trust legacy completion."""
    source = Path(source)
    legacy = _read(source)
    if not isinstance(legacy, dict) or legacy.get("project_id") != project_id:
        raise RunStateError("legacy record does not bind this registered project")
    if _plan(project, legacy.get("plan", "")).resolved != _plan(project, plan).resolved:
        raise RunStateError("legacy plan does not match the requested durable plan")
    raw = source.read_bytes()
    return _create(project, project_id=project_id, plan=plan, contract=contract,
                   profile=_profile(profile if profile is not None else legacy.get("profile")), actor=actor, command_id=command_id,
                   runtime_root=runtime_root, migration=(raw, legacy))

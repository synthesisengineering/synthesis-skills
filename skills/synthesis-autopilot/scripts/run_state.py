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

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import uuid

PM_SCRIPTS = Path(__file__).resolve().parents[2] / "synthesis-project-management/scripts"
if str(PM_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(PM_SCRIPTS))
from plan_reference import resolve_plan_target
from run_admission import admit_paths, admission_scope, bounded_lock, inspect_paths, native_binding, safe_path
from project_state import observer_native_identity
import coordination

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
REQUEST_OPERATIONS = frozenset({"start", "next", "record", "checkpoint", "explain", "cancel", "recover", "finish"})
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


def _read(path):
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_JSON_BYTES:
            raise RunStateError("missing, unsafe, or oversized state file")
        with path.open(encoding="utf-8") as stream:
            return json.load(stream, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise RunStateError(f"unreadable state at {path}: {exc}") from exc


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
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"\n?<!-- autopilot:[0-9a-f-]+:start -->\n.*?<!-- autopilot:[0-9a-f-]+:end -->\n?", "", text, flags=re.S)
    return hashlib.sha256(text.rstrip().encode()).hexdigest()


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


def _events(project, run_id):
    home = _home(project, run_id)
    directory = safe_path(home / "events", Path(project).resolve())
    if not directory.is_dir():
        raise RunStateError("run has no committed events")
    files = sorted(directory.iterdir())
    files = [path for path in files if not path.name.startswith(".run-")]
    if not files or len(files) > MAX_EVENTS:
        raise RunStateError("event stream is empty or exceeds supported replay limit")
    previous = ""
    commands = set()
    for revision, path in enumerate(files, 1):
        if path.name != f"{revision:012d}.json":
            raise RunStateError("event sequence has a gap or unexpected entry")
        event = _read(path)
        if not isinstance(event, dict):
            raise RunStateError("event must be an object")
        digest = event.get("digest")
        body = {key: value for key, value in event.items() if key != "digest"}
        if digest != _digest(body) or event.get("previous_digest") != previous or event.get("revision") != revision or event.get("schema_version") != SCHEMA:
            raise RunStateError("event chain failed integrity/schema validation")
        state = event.get("state")
        if not isinstance(state, dict) or state.get("schema_version") != SCHEMA or state.get("run_id") != run_id or state.get("revision") != revision or state.get("status") not in STATUSES:
            raise RunStateError("event state identity is invalid")
        if event.get("command_id") in commands:
            raise RunStateError("event stream contains duplicate command IDs")
        commands.add(event["command_id"])
        previous = digest
        yield event


def load_run(project: Path, run_id: str) -> dict:
    """Read only the selected journal; projections and other runs confer no truth."""
    last = None
    for last in _events(project, run_id):
        pass
    return deepcopy(last["state"])


def _project(project, state):
    home = _home(project, state["run_id"])
    _write(home / "current.json", _json(state) + b"\n")
    summary = f"Run: {state['run_id']}\nRevision: {state['revision']}\nStatus: {state['status']}\n"
    summary += f"Contract: {state['contract_revision']} ({state['contract_digest']})\n"
    summary += f"Profile: {state['profile_revision']} ({state['profile_digest']})\n"
    if state.get("progress"):
        summary += "Progress: " + state["progress"]["summary"].replace("\n", " ") + "\n"
    _write(home / "summary.md", ("# Autopilot run\n\n" + summary).encode())
    if state["status"] in TERMINAL:
        _write(home / "terminal.json", _json({"schema_version": SCHEMA, "run_id": state["run_id"],
               "revision": state["revision"], "status": state["status"], "terminal": state["terminal"]}) + b"\n")
    plan = _plan(project, state["plan"]).resolved
    # Different runs may project into the same plan. Share one lock so their
    # read/replace steps never erase each other's ledger or human prose.
    with bounded_lock(_plan_lock(project, plan)):
        text = plan.read_text(encoding="utf-8")
        start, end = (f"<!-- autopilot:{state['run_id']}:{edge} -->" for edge in ("start", "end"))
        block = start + "\n" + summary + end
        if text.count(start) != text.count(end) or text.count(start) > 1:
            raise RunStateError("plan ledger markers are ambiguous; human repair required")
        if start in text:
            text = text[:text.index(start)] + block + text[text.index(end) + len(end):]
        else:
            text = text.rstrip() + "\n\n" + block + "\n"
        _write(plan, text.encode())


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


def _append(project, state, command_id, command_digest, command, previous_digest, proof):
    home = _home(project, state["run_id"])
    event = {"schema_version": SCHEMA, "revision": state["revision"], "previous_digest": previous_digest,
             "command_id": command_id, "command_digest": command_digest, "command": command,
             "actor": {key: proof[key] for key in ("session_uuid", "native_ref", "claim_hash")}, "state": state}
    event["digest"] = _digest(event)
    raw = _json(event) + b"\n"
    if len(raw) > MAX_JSON_BYTES or state["revision"] > MAX_EVENTS:
        raise RunStateError("run exceeds the supported journal limits")
    path = home / "events" / f"{state['revision']:012d}.json"
    if path.exists():
        raise RunStateError("refusing to overwrite a committed event")
    _write(path, raw)


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
        if (home / "events").exists() and any((home / "events").iterdir()):
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
    last = None
    for last in _events(project, state["run_id"]):
        pass
    current = last["state"]
    if current != state:
        raise RunStateError("inspection state is stale; reload the current journal")
    proof = _binding(project, current, actor, readonly=True)
    context = _context(project, current, {}, proof, actor=actor)
    context["journal_head"] = {"revision": current["revision"], "digest": last["digest"], "scope": "full_run"}
    context["current_native_events"] = _native_readback(project, current, actor, context["journal_head"])
    context["current_native_invalidation"] = _native_readback(project, current, actor, context["journal_head"], invalidation=True)
    return context


def _native_readback(project, state, actor, journal_head, *, passive=False, invalidation=False):
    """An ephemeral fresh-read operation, never a reusable admission token.

    The closure binds an already chain-verified state. Each invocation acquires
    fresh native/PM admission and rejects an intervening journal append before
    and after the selected current source ranges are read.
    """
    selected, principal, head = deepcopy(state), deepcopy(actor), deepcopy(journal_head)
    project = Path(project)
    def read(event_ids=None, interval=None, *, source_handle="root"):
        import observation_bridge
        base = {"project": project, "state": selected, "actor": principal}
        if observation_bridge._current_head(base) != head["digest"]:
            raise RunStateError("native readback journal head changed")
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
    observer_context = {"project": Path(project), "state": deepcopy(state), "binding": deepcopy(proof),
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
    return {"now": now, "binding": deepcopy(proof), "artifacts": artifacts, "evidence": evidence,
            "admissions": admissions, "verify_receipt": verify_receipt, "plan_digest": plan_digest}


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
    if state["status"] != "verifying":
        raise RunStateError("completion requires the verifying state")
    if any(item["status"] == "pending" for item in state["waits"].values()):
        raise RunStateError("completion has unresolved waits")
    if any(item["status"] in {"prepared", "unknown", "retryable"} for item in state["effects"].values()):
        raise RunStateError("completion has unresolved external effect outcomes")
    for key, record in state["artifacts"].items():
        if record["required"] and key not in context["artifacts"]:
            raise RunStateError("required artifact is missing or changed")
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
            "profile_digest": state["profile_digest"], "criteria": sorted(verified), "verifier_version": VERIFIER_VERSION}


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
    "owner.transfer.prepare", "owner.transfer.accept", "owner.transfer.revoke"})


def apply_command(project: Path, run_id: str, command: str, payload: dict, *, expected_revision: int,
                  command_id: str, actor: dict, runtime_root: Path | None = None,
                  request_binding: dict | None = None) -> dict:
    _id(command_id, "command ID")
    request_binding = _request_binding(request_binding)
    if type(expected_revision) is not int or expected_revision < 1 or not isinstance(payload, dict):
        raise RunStateError("mutation requires an integer expected revision and object payload")
    project = Path(project).resolve(strict=True)
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
        previous = None
        matching = None
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
        _check_request(state, request_binding)
        if matching is not None:
            if matching["command_digest"] != digest:
                raise RunStateError("command ID was already used with different input")
            _project(project, state)
            return deepcopy(matching["state"])
        if state["revision"] != expected_revision:
            raise RunStateError("stale run revision; reload before retry")
        if state["status"] in TERMINAL and command not in _TERMINAL_COMMANDS:
            raise RunStateError("terminal run cannot be reopened; create a new run identity")
        # Trusted sources and the bounded observer share this one admitted
        # operation. Pure reducer context never contains the token, and the
        # scope ends before the fresh mutation admission below.
        with admission_scope(proof, actor, project) as operation:
            context = _context_observed(project, state, payload, proof, actor=actor, observation=operation)
            context["journal_head"] = {"revision": state["revision"], "digest": previous["digest"], "scope": "full_run"}
            context["current_native_invalidation"] = _native_readback(project, state, actor, context["journal_head"], invalidation=True)
            updated = deepcopy(state)
            if command.startswith("observe:") and command.split(":", 1)[1] in _OBSERVERS:
                if command_id in state["evidence"] or command_id in state.get("observations", {}):
                    raise RunStateError("observation attempt IDs are immutable; use a new command ID")
                _fields(payload, {"check_id"}, {"check_id"})
                check_id = _id(payload["check_id"], "observer check ID")
                if check_id not in context["artifacts"]:
                    raise RunStateError("observer requires a current registered artifact specification")
                kind = command.split(":", 1)[1]
                observer_context = {**context, "state": deepcopy(state), "project": project, "actor": deepcopy(actor),
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
                    observer_context = {**context, "state": deepcopy(state), "project": project,
                        "actor": deepcopy(actor), "admission_observation": operation,
                        "command_id": command_id, "command_digest": digest, "runtime_root": _runtime(runtime_root)}
                    observer_context["criterion_report"] = lambda: criterion_report(state, context)
                    prepared = _PREPARERS[command](observer_context, prepared)
                    if not isinstance(prepared, dict) or len(_json(prepared)) > MAX_JSON_BYTES:
                        raise RunStateError("command preparer returned invalid or oversized data")
                updated = reducer(updated, prepared, context)
                if not isinstance(updated, dict) or {k: v for k, v in updated.items() if k != "extensions"} != {k: v for k, v in state.items() if k != "extensions"} or not isinstance(updated.get("extensions"), dict):
                    raise RunStateError("extension reducer attempted to modify protected core fields")
        updated["revision"] = state["revision"] + 1
        updated["updated_at"] = _now()
        _record_request(updated, request_binding, command_id, digest)
        for check in _CONSTRAINTS.values():
            check(deepcopy(updated), command, deepcopy(payload), context)
        # Re-admit after reducer work: a revoked seat must not commit after a
        # slow local verifier or a concurrent board mutation.
        _command_binding(project, state, actor, command, payload)
        if updated["owner"]["session_uuid"] != state["owner"]["session_uuid"]:
            _native_index_update(runtime_root, updated["owner"])
            _index_update(runtime_root, updated["owner"]["session_uuid"], run_id, _index_entry(project, updated, "pending"))
        _append(project, updated, command_id, digest, command, previous["digest"], proof)
        _project(project, updated)
        _index_update(runtime_root, state["owner"]["session_uuid"], run_id, _index_entry(project, updated,
                      "transferred" if updated["owner"]["session_uuid"] != state["owner"]["session_uuid"] else None))
        if updated["owner"]["session_uuid"] != state["owner"]["session_uuid"]:
            _index_update(runtime_root, updated["owner"]["session_uuid"], run_id, _index_entry(project, updated))
        return deepcopy(updated)


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


def discover_legacy(actor, legacy_root, *, plan=None, runtime_root=None, _paths=None):
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
        if path.is_symlink() or not path.is_file():
            result["unattributed"].append({"source": str(path), "reason": "unsafe record", "blocking": path == exact})
            continue
        size = path.stat().st_size
        total += min(size, MAX_JSON_BYTES)
        if total > 32 * 1024 * 1024 and _paths is None:
            result["truncated"] = True
            break
        with path.open("rb") as stream:
            raw = stream.read(MAX_JSON_BYTES + 1)
        identity_hint = any(marker.encode() in raw for marker in refs | owners)
        try:
            if len(raw) > MAX_JSON_BYTES:
                raise ValueError("oversized record")
            legacy = json.loads(raw)
            if not isinstance(legacy, dict):
                raise ValueError("record is not an object")
        except (ValueError, UnicodeError) as exc:
            result["unattributed"].append({"source": str(path), "reason": str(exc), "blocking": identity_hint or path == exact})
            continue
        if legacy.get("client_session_ref") not in refs and legacy.get("session_id") not in owners:
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
    selectors, unknown, scanned = {}, [], 0
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
        generation_home = home / "generations" / generation
        for directory in ("native", "seats"):
            (generation_home / directory).mkdir(parents=True, exist_ok=True)
        for (kind, identity), names in selectors.items():
            _write(_legacy_selector_path(generation_home, kind, identity), _json({"schema_version": SCHEMA,
                   "generation": generation, "identity": identity, "sources": sorted(names)}) + b"\n")
        # A complete generation commits through one manifest replacement;
        # concurrent Stop readers cannot mix old and newly built selectors.
        _write(home / "manifest.json", _json({"schema_version": SCHEMA, "root": str(root),
               "generation": generation, "scanned": scanned, "unattributed_count": len(unknown)}) + b"\n")
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
    paths = set()
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
    return {**discover_legacy(actor, root, plan=plan, runtime_root=runtime, _paths=paths), "health": "PASS",
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

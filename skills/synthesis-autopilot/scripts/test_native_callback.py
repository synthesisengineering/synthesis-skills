"""Synthetic protocol producer; never native acceptance or a provider turn."""

from copy import deepcopy
import json
from pathlib import Path
import pytest
import native_codex

SID = "00000000-0000-4000-8000-000000000009"


def hook(kind="completed", context="Synthetic context"):
    value = {
        "id": "hook-1",
        "eventName": "sessionStart",
        "sourcePath": "/synthetic/plugin/hooks.json",
        "scope": "thread",
        "source": "plugin",
        "executionMode": "sync",
        "handlerType": "command",
        "status": kind,
        "startedAt": 1000,
        "displayOrder": 0,
        "entries": [],
    }
    if kind == "completed":
        value.update(
            completedAt=1001,
            durationMs=1,
            entries=[{"kind": "context", "text": context}],
        )
    return {
        "method": "hook/" + ("started" if kind == "running" else "completed"),
        "params": {"threadId": SID, "turnId": None, "run": value},
    }


def binding():
    return {
        "producer": {"client": "codex", "thread_id": SID, "root_session_id": SID},
        "mode": "synthetic",
        "dialect": "codex.app_server",
        "invocation_id": "synthetic-invocation",
    }


def test_typed_delivered_context_is_not_stdout():
    facts = native_codex.decode_wire(hook(), binding())
    assert len(facts) == 1 and facts[0]["kind"] == "runtime.hook"
    assert facts[0]["data"]["entries"] == [
        {"kind": "context", "text": "Synthetic context"}
    ]
    assert "stdout" not in facts[0]["data"] and facts[0]["data"]["hook_id"] == "hook-1"


@pytest.mark.parametrize(
    "field,value",
    [
        ("executionMode", "async"),
        ("startedAt", True),
        ("entries", [{"kind": "unknown", "text": "x"}]),
        ("status", "running"),
        ("completedAt", 999),
    ],
)
def test_invalid_typed_callback_refuses(field, value):
    row = hook()
    row["params"]["run"][field] = value
    with pytest.raises(ValueError):
        native_codex.decode_wire(row, binding())


def test_callback_wrong_session_refuses():
    row = hook()
    row["params"]["threadId"] = "foreign"
    with pytest.raises(ValueError):
        native_codex.decode_wire(row, binding())


def config(tmp_path):
    return {
        "client": "codex",
        "selected": {"model": "synthetic-model", "model_reasoning_effort": "xhigh"},
        "required_capabilities": ["native-callback"],
        "file_contract": {
            "schema_version": 1,
            "immutable_inputs": [],
            "output_roots": [],
            "scratch_root": str(tmp_path),
        },
    }


@pytest.mark.parametrize(
    "field,value",
    [
        ("path", "/foreign/history"),
        ("parentThreadId", "foreign"),
        ("forkedFromId", "foreign"),
        ("projectId", "foreign"),
        ("sessionId", "foreign"),
        ("turns", [{"id": "unrequested"}]),
        ("cwd", "/foreign/workspace"),
    ],
)
def test_notification_must_agree_with_callback_response(tmp_path, field, value):
    import native_callback

    configuration = config(tmp_path)
    rows = records(configuration)
    thread = deepcopy(rows[-1]["result"]["thread"])
    notification = {"method": "thread/started", "params": {"thread": thread}}
    rows.insert(1, notification)
    assert (
        native_callback.parse(
            encode(rows), configuration, encode(native_callback.requests(configuration))
        )["terminal"]
        == "completed"
    )
    thread[field] = value
    with pytest.raises(ValueError, match="callback"):
        native_callback.parse(
            encode(rows), configuration, encode(native_callback.requests(configuration))
        )


@pytest.mark.parametrize(
    "status", [None, "idle", [], 7, {}, {"type": "busy"}, {"type": []}]
)
def test_malformed_callback_status_refuses_as_protocol_failure(status):
    b = binding()
    b["dialect"] = "codex.app_server_callback"
    row = {
        "method": "thread/status/changed",
        "params": {"threadId": SID, "status": status},
    }
    with pytest.raises(ValueError):
        native_codex.decode_wire(row, b)


@pytest.mark.parametrize("field,value", [("source", []), ("status", {})])
def test_malformed_callback_hook_scalars_refuse(field, value):
    row = hook()
    row["params"]["run"][field] = value
    with pytest.raises(ValueError):
        native_codex.decode_wire(
            row, {**binding(), "dialect": "codex.app_server_callback"}
        )


def test_malformed_callback_entry_kind_and_method_refuse():
    b = {**binding(), "dialect": "codex.app_server_callback"}
    row = hook()
    row["params"]["run"]["entries"][0]["kind"] = []
    with pytest.raises(ValueError):
        native_codex.decode_wire(row, b)
    with pytest.raises(ValueError):
        native_codex.decode_wire({"method": [], "params": {}}, b)


def response(configuration):
    contract = configuration["file_contract"]
    selected = configuration["selected"]
    return {
        "id": 2,
        "result": {
            "thread": {
                "id": SID,
                "sessionId": SID,
                "ephemeral": True,
                "path": None,
                "projectId": None,
                "parentThreadId": None,
                "forkedFromId": None,
                "turns": [],
                "cwd": contract["scratch_root"],
            },
            "cwd": contract["scratch_root"],
            "model": selected["model"],
            "reasoningEffort": selected["model_reasoning_effort"],
            "approvalPolicy": "never",
            "sandbox": {
                "type": "workspaceWrite",
                "networkAccess": False,
                "excludeSlashTmp": True,
                "excludeTmpdirEnvVar": True,
                "writableRoots": contract["output_roots"],
            },
        },
    }


def records(
    configuration,
    context="SYNTHESIS_NATIVE_RECEIPT "
    + json.dumps({"event_id": "synthetic-event", "sha256": "a" * 64}),
):
    return [
        {"id": 1, "result": {"userAgent": "synthetic"}},
        hook("running"),
        hook(context=context),
        response(configuration),
    ]


def encode(rows):
    return ("".join(json.dumps(r) + "\n" for r in rows)).encode()


def test_real_callback_parse_and_source_owner(tmp_path):
    import native_callback as cb
    import native_observations as source

    configuration = config(tmp_path)
    raw = encode(records(configuration))
    sent = encode(cb.requests(configuration))
    observed = cb.parse(raw, configuration, sent)
    assert observed["terminal"] == "completed" and observed["usage"]["tokens"] is None
    path = tmp_path / "wire.jsonl"
    path.write_bytes(raw)
    binding, cursor = source.enroll_source(
        path,
        client="codex",
        expected_root_session_id=SID,
        dialect=cb.DIALECT,
        mode="synthetic",
    )
    batch = source.read_page(binding, cursor)
    assert not batch["gaps"] and not batch["diagnostics"], batch
    assert [e["kind"] for e in batch["events"]] == [
        "runtime.hook",
        "runtime.hook",
        "session.started",
    ]
    assert all(e["data"]["model_turn_completed"] is False for e in batch["events"])
    assert (
        source.revalidate_observations(
            binding, batch["events"], required_interval=[0, len(raw)]
        )["status"]
        == "current"
    )


@pytest.mark.parametrize(
    "fault",
    [
        "history",
        "parent",
        "project",
        "turn",
        "model",
        "effort",
        "network",
        "writable",
        "approval",
        "unpaired",
        "duplicate",
        "wrong-source",
        "model-event",
        "extra-call",
        "missing-context",
        "partial",
    ],
)
def test_callback_scope_and_proof_refusals(tmp_path, fault):
    import native_callback as cb

    configuration = config(tmp_path)
    rows = records(configuration)
    sent = cb.requests(configuration)
    terminal = rows[-1]["result"]
    thread = terminal["thread"]
    if fault == "history":
        thread["path"] = "/foreign/history"
    if fault == "parent":
        thread["parentThreadId"] = "foreign"
    if fault == "project":
        thread["projectId"] = "desktop-task"
    if fault == "turn":
        thread["turns"] = [{"id": "model-turn"}]
    if fault == "model":
        terminal["model"] = "another"
    if fault == "effort":
        terminal["reasoningEffort"] = "max"
    if fault == "network":
        terminal["sandbox"]["networkAccess"] = True
    if fault == "writable":
        terminal["sandbox"]["writableRoots"] = ["/foreign"]
    if fault == "approval":
        terminal["approvalPolicy"] = "never-ask-bypass"
    if fault == "unpaired":
        rows.pop(1)
    if fault == "duplicate":
        rows.insert(3, deepcopy(rows[2]))
    if fault == "wrong-source":
        rows[2]["params"]["run"]["sourcePath"] = "/changed"
    if fault == "model-event":
        rows.append({"method": "turn/started", "params": {"threadId": SID}})
    if fault == "extra-call":
        sent.append({"id": 3, "method": "turn/start", "params": {"threadId": SID}})
    if fault == "missing-context":
        rows[2]["params"]["run"]["entries"] = []
    raw = encode(rows)
    if fault == "partial":
        raw = raw[:-1]
    with pytest.raises(ValueError):
        cb.parse(raw, configuration, encode(sent))


def fake_server(tmp_path, rows):
    path = tmp_path / "synthetic-server"
    path.write_text(
        "#!/usr/bin/env python3\nimport sys,json\nrows="
        + repr(rows)
        + "\n"
        + "for line in sys.stdin:\n r=json.loads(line)\n"
        + ' if r.get("method")=="initialize": print(json.dumps(rows[0]),flush=True)\n'
        + ' elif r.get("method")=="thread/start":\n'
        + "  for row in rows[1:]: print(json.dumps(row),flush=True)\n"
    )
    path.chmod(0o700)
    return path


def test_finite_actual_local_callback_transport_preserves_frames(tmp_path, monkeypatch):
    import native_callback as cb
    import os

    configuration = config(tmp_path)
    rows = records(configuration)
    script = fake_server(tmp_path, rows)
    import native_resume
    import hashlib

    def synthetic_identity(p):
        return {
            "path": str(p),
            "sha256": hashlib.sha256(Path(p).read_bytes()).hexdigest(),
        }

    monkeypatch.setattr(native_resume, "binary_identity", synthetic_identity)
    configuration["executable_identity"] = synthetic_identity(script)
    code, raw, err, failure, cleanup, sent = cb.execute(
        [str(script)], configuration, tmp_path, 3, dict(os.environ)
    )
    assert code == 0 and failure is None and cleanup["cleanup_verified"], (
        failure,
        err,
        cleanup,
    )
    assert (
        raw == encode(rows)
        and cb.parse(raw, configuration, sent)["producer"] == "codex:" + SID
    )
    assert [r["method"] for r in cb._rows(sent)] == [
        "initialize",
        "initialized",
        "thread/start",
    ]


def test_callback_owner_timeout_retains_partial_and_reaps(tmp_path, monkeypatch):
    import native_callback as cb
    import os

    configuration = config(tmp_path)
    rows = records(configuration)
    rows[2]["params"]["run"]["entries"] = []
    script = fake_server(tmp_path, rows)
    import native_resume
    import hashlib

    def synthetic_identity(p):
        return {
            "path": str(p),
            "sha256": hashlib.sha256(Path(p).read_bytes()).hexdigest(),
        }

    monkeypatch.setattr(native_resume, "binary_identity", synthetic_identity)
    configuration["executable_identity"] = synthetic_identity(script)
    code, raw, err, failure, cleanup, sent = cb.execute(
        [str(script)], configuration, tmp_path, 0.2, dict(os.environ)
    )
    assert code != 0 and failure and cleanup["cleanup_verified"]
    assert raw == encode(rows) and sent


def test_callback_capability_never_downgrades_or_mixes_model_work():
    import delegation_boundary as boundary

    boundary.validate_requirements("codex", ["native-callback"])
    for client, capabilities in [
        ("claude", ["native-callback"]),
        ("muse", ["native-callback"]),
        ("codex", ["native-callback", "shell"]),
    ]:
        with pytest.raises(ValueError):
            boundary.validate_requirements(client, capabilities)


def test_codex_hook_negative_source_and_delivered_entries(tmp_path):
    from test_vendor_native import consumer as vendor

    configuration = config(tmp_path)
    rows = records(configuration)
    b = binding()
    b["dialect"] = "codex.app_server_callback"
    for row in rows[1:3]:
        row["params"]["run"]["sourcePath"] = str(tmp_path / "hooks/hooks.json")
    facts = [f for r in rows for f in native_codex.decode_wire(r, b)]
    events = []
    for fact in facts:
        events.append({**fact, "status": "observed"})
    for event in events:
        if event["kind"] == "runtime.hook":
            event["data"]["source_path"] = str(tmp_path / "hooks/hooks.json")
    for row in rows[1:3]:
        row["params"]["run"]["sourcePath"] = str(tmp_path / "hooks/hooks.json")
    assert vendor._codex_witness(events, rows, SID, tmp_path)["sha256"] == "a" * 64
    foreign = deepcopy(events)
    foreign[1]["data"]["source_path"] = "/foreign/hooks.json"
    with pytest.raises(ValueError):
        vendor._codex_witness(foreign, rows, SID, tmp_path)
    duplicate = rows + [deepcopy(rows[2])]
    with pytest.raises(ValueError):
        vendor._codex_witness(events, duplicate, SID, tmp_path)


def test_native_binary_owner_refuses_linked_ancestor_and_changed_bytes(
    tmp_path, monkeypatch
):
    import native_resume as owner

    real = tmp_path / "real"
    real.mkdir()
    binary = real / "client"
    binary.write_bytes(b"\x7fELF" + b"x" * 100)
    binary.chmod(0o700)
    assert owner.binary_identity(binary)["size"] == 104
    alias = tmp_path / "alias"
    alias.symlink_to(real, target_is_directory=True)
    with pytest.raises(ValueError):
        owner.binary_identity(alias / "client")


@pytest.mark.parametrize(
    "fault", ["hardlink", "fifo", "directory", "size", "changed-read"]
)
def test_native_executable_custody_is_bounded_and_current(tmp_path, monkeypatch, fault):
    import native_resume as owner
    import os

    target = tmp_path / "client"
    target.write_bytes(b"\x7fELF" + b"x" * 100)
    target.chmod(0o700)
    if fault == "hardlink":
        os.link(target, tmp_path / "alias")
    elif fault == "fifo":
        target.unlink()
        os.mkfifo(target)
    elif fault == "directory":
        target.unlink()
        target.mkdir()
    elif fault == "size":
        with target.open("r+b") as f:
            f.truncate(1024**3 + 1)
    elif fault == "changed-read":
        original = os.read
        changed = []

        def raced(fd, size):
            value = original(fd, size)
            if not changed:
                changed.append(True)
                target.write_bytes(b"\x7fELF" + b"y" * 100)
            return value

        monkeypatch.setattr(owner.os, "read", raced)
    with pytest.raises(ValueError):
        owner.binary_identity(target)


def test_callback_interruption_retains_capture_and_terminal_cleanup(
    tmp_path, monkeypatch
):
    import native_callback as cb
    import native_resume
    import os
    import hashlib

    configuration = config(tmp_path)
    script = fake_server(tmp_path, records(configuration))

    def identity(p):
        return {
            "path": str(p),
            "sha256": hashlib.sha256(Path(p).read_bytes()).hexdigest(),
        }

    monkeypatch.setattr(native_resume, "binary_identity", identity)
    configuration["executable_identity"] = identity(script)
    original = cb.MuseConnection._read

    def interrupted(connection, *args, **kwargs):
        result = original(connection, *args, **kwargs)
        if connection.raw_stdout:
            raise KeyboardInterrupt("synthetic cancellation")
        return result

    monkeypatch.setattr(cb.MuseConnection, "_read", interrupted)
    code, raw, errors, failure, cleanup, sent = cb.execute(
        [str(script)], configuration, tmp_path, 2, dict(os.environ)
    )
    assert code != 0 and "interrupted" in failure and cleanup["cleanup_verified"]
    assert raw and sent


@pytest.mark.parametrize(
    "field,value",
    [("result", []), ("thread", []), ("sandbox", []), ("writableRoots", [{}])],
)
def test_malformed_callback_response_refuses_as_evidence(tmp_path, field, value):
    import native_callback as cb

    configuration = config(tmp_path)
    rows = records(configuration)
    if field == "result":
        rows[-1]["result"] = value
    elif field == "writableRoots":
        rows[-1]["result"]["sandbox"][field] = value
    else:
        rows[-1]["result"][field] = value
    with pytest.raises(ValueError):
        cb.parse(encode(rows), configuration, encode(cb.requests(configuration)))

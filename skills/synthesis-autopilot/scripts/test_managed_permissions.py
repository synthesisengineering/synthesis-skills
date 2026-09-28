"""Synthetic current-owner controls; no native Codex/provider/session is invoked."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import pytest
import delegation_boundary as boundary
import managed_permissions as policy
import managed_native as native
import native_protection as protection
from test_native_callback import hook, SID, encode


def register(contract, context, path, ident):
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    item = {"artifact_id": ident, "path": str(path), "digest": sha}
    contract["immutable_inputs"].append(item)
    context["artifacts"][ident] = {
        "id": ident,
        "path": str(path.relative_to(context["binding"]["project_root"])),
        "digest": sha,
    }
    return item


@pytest.fixture
def managed(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    read = root / "inputs"
    read.mkdir()
    out = root / "output"
    out.mkdir()
    scratch = root / "scratch"
    scratch.mkdir()
    denied = root / "private"
    denied.mkdir()
    exe = root / "synthetic-codex"
    exe.write_bytes(b"\xcf\xfa\xed\xfe" + b"synthetic-executable")
    exe.chmod(0o755)
    interpreter = Path(sys.executable).resolve()
    import native_resume

    profile = {
        "schema_version": 1,
        "client": "codex",
        "id": "synthesis-control",
        "filesystem": {
            str(read): "read",
            str(out): "write",
            str(scratch): "write",
            str(denied): "deny",
            str(interpreter.parent.parent): "read",
        },
        "network": False,
        "approval_policy": "never",
        "native_executable": native_resume.binary_identity(exe),
        "probe": {
            "interpreter": native_resume.binary_identity(interpreter),
            "script_artifact_id": "probe",
            "spec_artifact_id": "reference",
            "timeout_ms": 10000,
            "output_bytes_cap": 65536,
        },
    }
    contract = {
        "schema_version": 1,
        "immutable_inputs": [],
        "output_roots": [str(out)],
        "scratch_root": str(scratch),
    }
    context = {"binding": {"project_root": str(root)}, "artifacts": {}}
    source = read / "policy.json"
    source.write_text(json.dumps(profile))
    ref = register(contract, context, source, "policy")
    contract["permissions"] = {"source": ref, "profile": profile}
    script = read / "probe.py"
    script.write_bytes(Path(protection.__file__).read_bytes())
    register(contract, context, script, "probe")
    rows = []
    for ident, op, path in [
        ("read", "allowed-read", read / "read-canary"),
        ("denied-read", "denied-read", denied / "oracle"),
        ("denied-write", "denied-write", read / "write-canary"),
        ("create", "allowed-create", out / "created"),
    ]:
        raw = (
            b"SYNTHESIS-STUDY-ALLOWED-WRITE\n"
            if op == "allowed-create"
            else (ident + " synthetic\n").encode()
        )
        if op != "allowed-create":
            path.write_bytes(raw)
        rows.append(
            {
                "id": ident,
                "operation": op,
                "path": str(path),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    spec = {
        "schema_version": 1,
        "kind": "d2-synthetic-protection-controls",
        "filesystem": {
            "schema_version": 1,
            "kind": "study-synthetic-protection-controls",
            "assignment_id": "synthetic",
            "profile_sha256": boundary.digest(profile),
            "native_session_id": SID,
            "output_root": str(out),
            "controls": rows,
        },
        "network": {
            "host": "127.0.0.1",
            "port": 34567,
            "nonce": "a" * 32,
            "timeout_seconds": 0.2,
        },
    }
    specfile = read / "spec.json"
    specfile.write_text(json.dumps(spec))
    si = register(contract, context, specfile, "spec")
    pin = read / "reference.json"
    pin.write_text(json.dumps({"path": si["path"], "sha256": si["digest"]}))
    register(contract, context, pin, "reference")
    config = {
        "client": "codex",
        "selected": {"model": "synthetic-model", "model_reasoning_effort": "xhigh"},
        "file_contract": contract,
        "required_capabilities": ["native-permission-probe"],
        "executable_identity": profile["native_executable"],
        "prompt": "An admitted synthetic task",
    }
    return config, context, [str(out), str(scratch)], spec


def reply(configuration):
    return {
        "thread": {
            "id": SID,
            "sessionId": SID,
            "ephemeral": True,
            "path": None,
            "projectId": None,
            "parentThreadId": None,
            "forkedFromId": None,
            "turns": [],
            "cwd": configuration["file_contract"]["scratch_root"],
        },
        "cwd": configuration["file_contract"]["scratch_root"],
        "model": configuration["selected"]["model"],
        "modelProvider": "openai",
        "reasoningEffort": configuration["selected"]["model_reasoning_effort"],
        "approvalPolicy": "never",
        "activePermissionProfile": {"id": "synthesis-control", "extends": None},
        "sandbox": {"type": "readOnly"},
    }


def config_read(configuration):
    return {
        "config": {
            "model_provider": "openai",
            "default_permissions": "synthesis-control",
            "permissions": {
                "synthesis-control": policy.compiled_profile(
                    configuration["file_contract"]
                )
            },
        }
    }


def rows(configuration, *, outcome=None):
    result = [
        {"id": 1, "result": {}},
        {"id": 2, "result": config_read(configuration)},
        hook("running"),
        hook(
            context="SYNTHESIS_NATIVE_RECEIPT "
            + json.dumps({"event_id": "synthetic", "sha256": "a" * 64})
        ),
        {"id": 3, "result": reply(configuration)},
        {"id": 4, "result": config_read(configuration)},
    ]
    if configuration["required_capabilities"] != ["native-callback"]:
        result.append(
            {
                "id": 5,
                "result": outcome or {"exitCode": 0, "stdout": "{}", "stderr": ""},
            }
        )
    return result


def sent(configuration):
    action = native.effect_request(configuration, SID)
    return native.requests(configuration) + ([action] if action else [])


def test_actual_contract_compiler_and_source_binding(managed):
    cfg, ctx, paths, _ = managed
    c = cfg["file_contract"]
    assert boundary.validate_file_contract(c, ctx, paths) == c
    snap = policy.inspect(
        c, executable=c["permissions"]["profile"]["native_executable"]["path"]
    )
    assert snap["compiled"]["filesystem"][":root"] == "deny"
    argv = boundary.native_argv(
        "codex",
        c["permissions"]["profile"]["native_executable"]["path"],
        c,
        cfg["selected"],
    )
    assert (
        argv[-1] == "app-server"
        and "--ignore-user-config" not in argv
        and "--sandbox" not in argv
    )
    start = native.requests(cfg)[3]["params"]
    assert start["permissions"] == "synthesis-control" and "sandbox" not in start
    assert "baseInstructions" not in start and "developerInstructions" not in start
    assert (
        native.parse(encode(rows(cfg)), cfg, encode(sent(cfg)))["terminal"]
        == "completed"
    )
    assert boundary.native_boundary_readback(cfg, rows(cfg))["status"] == "UNKNOWN"


@pytest.mark.parametrize(
    "change",
    [
        "extra",
        "network",
        "approval",
        "write",
        "read-input",
        "deny-open",
        "unsupported",
        "unregistered",
        "alias",
        "stale-source",
        "hardlink",
        "glob",
    ],
)
def test_profile_adversaries_refuse(managed, tmp_path, change):
    cfg, ctx, paths, _ = managed
    c = cfg["file_contract"]
    p = c["permissions"]["profile"]
    if change == "extra":
        p["free_config"] = "anything"
    if change == "network":
        p["network"] = True
    if change == "approval":
        p["approval_policy"] = "on-request"
    if change == "write":
        p["filesystem"][str(tmp_path / "foreign")] = "write"
    if change == "read-input":
        p["filesystem"].pop(str(Path(c["permissions"]["source"]["path"]).parent))
    if change == "deny-open":
        p["filesystem"][str(tmp_path / "deny")] = "deny"
        p["filesystem"][str(tmp_path / "deny/open")] = "read"
    if change == "unsupported":
        p["client"] = "muse"
    if change == "unregistered":
        c["permissions"]["source"] = {
            **c["permissions"]["source"],
            "artifact_id": "foreign",
        }
    if change == "alias":
        Path(c["permissions"]["source"]["path"]).parent.joinpath("link").symlink_to(
            tmp_path
        )
        p["filesystem"][
            str(Path(c["permissions"]["source"]["path"]).parent / "link")
        ] = "deny"
    if change == "stale-source":
        Path(c["permissions"]["source"]["path"]).write_text("{}")
    if change == "hardlink":
        import os

        os.link(c["permissions"]["source"]["path"], tmp_path / "alias")
    if change == "glob":
        p["filesystem"][str(tmp_path / "*")] = "deny"
    with pytest.raises((ValueError, OSError)):
        boundary.validate_file_contract(c, ctx, paths)
        policy.inspect(c)


@pytest.mark.parametrize(
    "change",
    [
        "profile",
        "config-extra",
        "config-network",
        "approval",
        "model",
        "effort",
        "persisted",
        "bool-response",
        "duplicate",
        "foreign-command",
        "fake-policy",
        "unsandboxed",
        "partial",
    ],
)
def test_actual_readback_refuses_widening_and_replay(managed, change):
    cfg, _, _, _ = managed
    raw = rows(cfg)
    requests = sent(cfg)
    if change == "profile":
        raw[-3]["result"]["activePermissionProfile"]["id"] = "foreign"
    if change == "config-extra":
        raw[1]["result"]["config"]["permissions"]["synthesis-control"]["filesystem"][
            "/foreign"
        ] = "write"
    if change == "config-network":
        raw[1]["result"]["config"]["permissions"]["synthesis-control"]["network"][
            "enabled"
        ] = True
    if change == "approval":
        raw[-3]["result"]["approvalPolicy"] = "on-request"
    if change == "model":
        raw[-3]["result"]["model"] = "different"
    if change == "effort":
        raw[-3]["result"]["reasoningEffort"] = "max"
    if change == "persisted":
        raw[-3]["result"]["thread"]["path"] = "/history"
    if change == "bool-response":
        raw[-1]["id"] = True
    if change == "duplicate":
        raw.append(deepcopy(raw[-1]))
    if change == "foreign-command":
        requests[-1]["params"]["command"] = ["/bin/false"]
    if change == "fake-policy":
        raw[-3]["result"].pop("activePermissionProfile")
    if change == "unsandboxed":
        requests[-1]["method"] = "thread/shellCommand"
    if change == "partial":
        raw.pop()
    with pytest.raises(ValueError):
        native.parse(encode(raw), cfg, encode(requests))


def test_callback_and_turn_use_same_named_profile_without_fallback(managed):
    cfg, _, _, _ = managed
    cfg = deepcopy(cfg)
    cfg["required_capabilities"] = ["native-callback"]
    assert native.effect_request(cfg, SID) is None
    assert (
        native.parse(encode(rows(cfg)), cfg, encode(sent(cfg)))["terminal"]
        == "completed"
    )
    cfg["required_capabilities"] = ["read"]
    cfg["protection_observation"] = {"transport": {"connection_id": "a" * 32}}
    action = native.effect_request(cfg, SID)
    assert (
        action["method"] == "turn/start"
        and action["params"]["permissions"] == "synthesis-control"
    )
    assert (
        action["params"]["effort"] == "xhigh"
        and "sandboxPolicy" not in action["params"]
    )


def test_exact_command_and_no_arbitrary_argv(managed):
    cfg, _, _, _ = managed
    p = policy.probe_params(cfg)
    assert p["permissionProfile"] == "synthesis-control" and p["timeoutMs"] == 10000
    assert p["command"][1] == "-I" and p["command"][3] == "--spec-reference"
    c = cfg["file_contract"]
    c["permissions"]["profile"]["probe"]["argv"] = ["/bin/sh", "-c", "true"]
    with pytest.raises(ValueError):
        policy.validate(c)


def test_missing_or_modified_probe_is_not_protection(managed):
    cfg, _, _, _ = managed
    assert protection.specification(cfg["file_contract"])
    p = next(
        x
        for x in cfg["file_contract"]["immutable_inputs"]
        if x["artifact_id"] == "probe"
    )
    Path(p["path"]).write_text('print("PASS")')
    with pytest.raises(ValueError):
        protection.specification(cfg["file_contract"])
    assert native.boundary(cfg, rows(cfg))["status"] == "UNKNOWN"


def test_duplicate_source_json_refuses_even_matching_last_value(managed):
    cfg, ctx, paths, _ = managed
    c = cfg["file_contract"]
    source = c["permissions"]["source"]
    p = Path(source["path"])
    raw = json.dumps(c["permissions"]["profile"])
    raw = '{"network":true,' + raw[1:]
    p.write_text(raw)
    source["digest"] = hashlib.sha256(p.read_bytes()).hexdigest()
    ctx["artifacts"][source["artifact_id"]]["digest"] = source["digest"]
    with pytest.raises(ValueError, match="Duplicate"):
        policy.inspect(c)


class Echo:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def settimeout(self, value):
        pass

    def sendall(self, value):
        self.value = value

    def recv(self, count):
        return self.value[:count]


def successful_observation(spec):
    # Explicit synthetic observation for source-only transport tests.
    fs = spec["filesystem"]
    n = spec["network"]
    return {
        "schema_version": 1,
        "kind": "d2-protection-observation",
        "filesystem": {
            "schema_version": 1,
            "kind": "study-protection-probe-observation",
            "assignment_id": fs["assignment_id"],
            "native_session_id_declared": fs["native_session_id"],
            "profile_sha256": fs["profile_sha256"],
            "status": "PASS",
            "checks": [
                {
                    "id": r["id"],
                    "operation": r["operation"],
                    "passed": True,
                    "error": None,
                }
                for r in fs["controls"]
            ],
        },
        "network": {
            "denied": True,
            "error": None,
            "host": n["host"],
            "port": n["port"],
            "nonce": n["nonce"],
        },
        "status": "PASS",
        "native_acceptance": "UNKNOWN",
    }


@pytest.fixture
def synthetic_connection(managed, monkeypatch):
    cfg, _, _, spec = managed
    instances = []

    class Connection:
        def __init__(self, *args, **kwargs):
            self.raw_stdout = bytearray()
            self.raw_stdin = bytearray()
            self.stderr = bytearray()
            self.cleanup = None
            self.closed = False
            self.calls = []
            self.next_id = 0
            instances.append(self)

        def send(self, row):
            self.raw_stdin.extend(encode([row]))
            if row.get("method") == "account/read":
                self.raw_stdout.extend(
                    encode([{"id": row["id"], "result": account_reply()}])
                )

        def call(self, method, params):
            self.next_id += 1
            self.calls.append(method)
            self.send(
                {
                    "jsonrpc": "2.0",
                    "id": self.next_id,
                    "method": method,
                    "params": params,
                }
            )
            if method == "initialize":
                value = {}
            elif method == "config/read":
                value = config_read(cfg)
            elif method == "thread/start":
                value = reply(cfg)
                self.raw_stdout.extend(
                    encode(
                        [
                            hook("running"),
                            hook(
                                context="SYNTHESIS_NATIVE_RECEIPT "
                                + json.dumps(
                                    {"event_id": "synthetic", "sha256": "a" * 64}
                                )
                            ),
                        ]
                    )
                )
            elif method == "command/exec":
                target = next(
                    x
                    for x in spec["filesystem"]["controls"]
                    if x["operation"] == "allowed-create"
                )
                Path(target["path"]).write_bytes(b"SYNTHESIS-STUDY-ALLOWED-WRITE\n")
                value = {
                    "exitCode": 0,
                    "stdout": json.dumps(successful_observation(spec)),
                    "stderr": "",
                }
            else:
                raise AssertionError("Unadmitted request " + method)
            self.raw_stdout.extend(encode([{"id": self.next_id, "result": value}]))
            return value

        def close(self):
            self.closed = True
            self.cleanup = {"group_absent": True, "leader_reaped": True}
            return self.cleanup

        def _read(self):
            raise TimeoutError("Synthetic input exhausted")

    monkeypatch.setattr(native.native_resume, "MuseConnection", Connection)
    monkeypatch.setattr(
        protection.socket, "create_connection", lambda *args, **kwargs: Echo()
    )
    return instances


def test_actual_worker_receipt_and_reverification_accept_exact_controls(
    managed, synthetic_connection, monkeypatch
):
    from test_delegation_boundary import worker_world

    cfg, ctx, paths, _ = managed
    state, ctx, runtime = worker_world((cfg["file_contract"], ctx, paths))
    child = state["extensions"]["workflow"]["children"]["worker"]
    child["client"] = "codex"
    child["required_capabilities"] = ["native-permission-probe"]
    calls = []
    monkeypatch.setattr(
        boundary,
        "_authorize_worker",
        lambda context, targets: calls.append(list(targets)),
    )
    monkeypatch.setattr(
        boundary,
        "client_selection",
        lambda client, env: (cfg["selected"], cfg["executable_identity"]["path"]),
    )
    result = boundary.run_worker(
        state, "worker", ctx, client="codex", runtime_root=runtime, timeout_seconds=20
    )
    assert result["terminal"] == "completed", Path(result["receipt_path"]).read_text()
    assert result["boundary"]["status"] == "ENFORCED"
    assert boundary.verify_worker_observation(result, ctx) is True
    assert synthetic_connection[0].calls == [
        "initialize",
        "config/read",
        "thread/start",
        "config/read",
        "command/exec",
    ]
    assert synthetic_connection[0].closed and len(calls) >= 4
    # These are synthetic source fixtures, not a live native acceptance receipt.
    receipt = json.loads(Path(result["receipt_path"]).read_text())
    assert receipt["configuration"]["selected"] == cfg["selected"]
    assert receipt["configuration"]["protection_observation"]["thread_id"] == SID
    # The actual protected observation reaches existing workflow owners without
    # a wrapper overriding ENFORCED. Receipt authentication here is explicitly a
    # source-only registry fixture, coupled to the real observation verifier.
    import workflow
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    ctx["now"] = now.isoformat()
    state.update(contract_revision=1, profile_revision=1)
    flow = state["extensions"]["workflow"]
    flow["bindings"] = workflow._bindings(state)
    flow["graph"] = {"nodes": {"probe": {"id": "probe", "status": "running"}}}
    child["task_id"] = "probe"
    evidence = {
        "id": "observed",
        "kind": "native_worker",
        "data": result,
        "observed_at": now.isoformat(),
        "expires_at": (now + timedelta(minutes=1)).isoformat(),
        "bindings": {
            "run_id": state["run_id"],
            "contract_digest": state["contract_digest"],
            "profile_digest": state["profile_digest"],
        },
    }
    ctx["evidence"] = {"observed": evidence}
    ctx["verify_receipt"] = lambda ident, kind, bindings: (
        ident == "observed"
        and kind == "native_worker"
        and bindings == evidence["bindings"]
        and boundary.verify_worker_observation(result, ctx)
    )
    recorded = workflow.worker_record(
        state, {"child_id": "worker", "receipt_id": "observed"}, ctx
    )
    completed = workflow.child_return(
        recorded,
        {
            "child_id": "worker",
            "disposition": "complete",
            "artifact_ids": [],
            "evidence_ids": ["observed"],
            "reason": "Exact synthetic native probe observed",
        },
        ctx,
    )
    assert (
        completed["extensions"]["workflow"]["children"]["worker"]["audit_status"]
        == "required"
    )
    assert (
        completed["extensions"]["workflow"]["children"]["worker"]["disposition"]
        == "complete"
    )
    Path(cfg["file_contract"]["permissions"]["source"]["path"]).write_text("{}")
    assert boundary.verify_worker_observation(result, ctx) is False


@pytest.mark.parametrize(
    "change", ["claim", "source", "native", "interrupt", "readback", "cleanup"]
)
def test_effect_refuses_changed_authority_and_reaps_connection(
    managed, synthetic_connection, monkeypatch, change
):
    cfg, _, _, _ = managed
    exe = cfg["executable_identity"]["path"]
    argv = policy.server_argv(exe, cfg["file_contract"])
    count = [0]
    real = policy.verify_active

    def check(configuration, response):
        real(configuration, response)
        if change == "readback":
            raise ValueError("changed native readback")

    monkeypatch.setattr(policy, "verify_active", check)

    def authorize():
        count[0] += 1
        if count[0] == 3:
            if change == "claim":
                raise ValueError("fresh claim differs")
            if change == "source":
                Path(cfg["file_contract"]["permissions"]["source"]["path"]).write_text(
                    "{}"
                )
            if change == "native":
                Path(exe).write_bytes(b"\xcf\xfa\xed\xfechanged")
            if change == "interrupt":
                raise KeyboardInterrupt()
            if change == "cleanup":
                synthetic_connection[0].close = lambda: {
                    "group_absent": False,
                    "leader_reaped": True,
                }

    result = native.execute(
        argv,
        cfg,
        Path(cfg["file_contract"]["scratch_root"]),
        5,
        {},
        revalidate=authorize,
    )
    assert result[0] != 0
    if change != "cleanup":
        assert synthetic_connection[0].closed
    if change != "cleanup":
        assert "command/exec" not in synthetic_connection[0].calls
    else:
        assert result[4]["cleanup_verified"] is False


@pytest.mark.parametrize(
    "change",
    [
        "missing",
        "wrong-session",
        "wrong-profile",
        "canary",
        "listener",
        "output",
        "result",
    ],
)
def test_qualified_boundary_refuses_forged_or_stale_observation(
    managed, synthetic_connection, change
):
    cfg, _, _, _ = managed
    exe = cfg["executable_identity"]["path"]
    result = native.execute(
        policy.server_argv(exe, cfg["file_contract"]),
        cfg,
        Path(cfg["file_contract"]["scratch_root"]),
        5,
        {},
        revalidate=lambda: None,
    )
    assert result[0] == 0
    raw = [json.loads(x) for x in result[1].splitlines()]
    assert native.boundary(cfg, raw)["status"] == "ENFORCED"
    capture = cfg["protection_observation"]
    if change == "missing":
        cfg.pop("protection_observation")
    if change == "wrong-session":
        capture["thread_id"] = "foreign"
    if change == "wrong-profile":
        capture["profile_digest"] = "f" * 64
    if change == "canary":
        capture["after"]["files"]["denied-read"]["digest"] = "f" * 64
    if change == "listener":
        capture["before"]["listener"]["healthy"] = False
    if change == "output":
        capture["after"]["files"]["create"]["digest"] = "f" * 64
    if change == "result":
        raw[-1]["result"]["stdout"] = '{"status":"PASS"}'
    assert native.boundary(cfg, raw)["status"] == "UNKNOWN"


def test_actual_fixed_probe_under_existing_os_sandbox(managed, monkeypatch, tmp_path):
    import errno
    import os
    import socket
    import threading
    import time
    from evaluation_artifacts import _sandbox_command

    manager = Path(__file__).parents[2] / "synthesis-skills-manager/scripts"
    sys.path.insert(0, str(manager))
    from release_check_groups import bounded_run

    cfg, ctx, _, spec = managed
    c = cfg["file_contract"]
    read = Path(c["permissions"]["source"]["path"]).parent
    out = Path(c["output_roots"][0])
    stop = threading.Event()
    healthy = []
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(4)
        listener.settimeout(0.1)
        spec["network"]["port"] = listener.getsockname()[1]

        def serve():
            end = time.monotonic() + 30
            while not stop.is_set() and time.monotonic() < end:
                try:
                    channel, _ = listener.accept()
                except socket.timeout:
                    continue
                with channel:
                    channel.settimeout(0.5)
                    data = channel.recv(32)
                    if data == spec["network"]["nonce"].encode():
                        healthy.append(data)
                        channel.sendall(data)

        thread = threading.Thread(target=serve)
        thread.start()
        try:
            for ident, value in [("spec", spec), ("reference", None)]:
                item = next(
                    i for i in c["immutable_inputs"] if i["artifact_id"] == ident
                )
                if value is None:
                    pinned = next(
                        i for i in c["immutable_inputs"] if i["artifact_id"] == "spec"
                    )
                    value = {"path": pinned["path"], "sha256": pinned["digest"]}
                Path(item["path"]).write_text(json.dumps(value))
                item["digest"] = hashlib.sha256(
                    Path(item["path"]).read_bytes()
                ).hexdigest()
                ctx["artifacts"][ident]["digest"] = item["digest"]
            before = protection.host_snapshot(c)
            script = next(
                i for i in c["immutable_inputs"] if i["artifact_id"] == "probe"
            )
            ref = next(
                i for i in c["immutable_inputs"] if i["artifact_id"] == "reference"
            )
            # Keep the registered fixed probe unchanged. The test-only wrapper
            # records exact OS errors, then executes those original pinned bytes.
            # Bubblewrap isolates by mount/network namespaces, whose errors must
            # never be promoted into the stricter native EPERM/EACCES evidence.
            diagnostics = out / "backend-observations.json"
            wrapper = read / "backend-observer.py"
            wrapper.write_text(
                "import json, os, runpy, socket, sys\nfrom pathlib import Path\n"
                + "spec = "
                + repr(spec)
                + "\n"
                + "errors = {}\n"
                + "for row in spec['filesystem']['controls']:\n"
                + " if row['operation'] not in ('denied-read','denied-write'): continue\n"
                + " flags = os.O_RDONLY if row['operation']=='denied-read' else os.O_WRONLY\n"
                + " try:\n  fd=os.open(row['path'],flags|os.O_NOFOLLOW|os.O_NONBLOCK)\n"
                + " except OSError as exc: errors[row['operation']]=exc.errno\n"
                + " else:\n  os.close(fd)\n  errors[row['operation']]=None\n"
                + "with socket.socket() as channel:\n"
                + " channel.settimeout(spec['network']['timeout_seconds'])\n"
                + " try: channel.connect((spec['network']['host'],spec['network']['port']))\n"
                + " except OSError as exc: errors['network']=exc.errno\n"
                + " else: errors['network']=None\n"
                + "Path("
                + repr(str(diagnostics))
                + ").write_text(json.dumps(errors))\n"
                + "sys.argv = "
                + repr([script["path"], "--spec-reference", ref["path"]])
                + "\n"
                + "runpy.run_path("
                + repr(script["path"])
                + ", run_name='__main__')\n"
            )
            argv, backend = _sandbox_command(read, out, wrapper, [])
            completed = bounded_run(
                argv, read, timeout=15, env={**os.environ, "TMPDIR": str(out)}
            )
            (tmp_path / "actual-os-probe.log").write_text(completed.stdout)
            observed = json.loads(completed.stdout)
            errors = json.loads(diagnostics.read_text())
            assert observed["native_acceptance"] == "UNKNOWN"
            checks = {row["id"]: row for row in observed["filesystem"]["checks"]}
            assert checks["read"]["passed"] and checks["create"]["passed"]
            if backend == "macos-sandbox-exec":
                assert set(errors) == {"denied-read", "denied-write", "network"}
                assert all(
                    value in (errno.EPERM, errno.EACCES) for value in errors.values()
                )
                assert completed.returncode == 0 and observed["status"] == "PASS", (
                    observed
                )
            else:
                assert backend == "linux-bubblewrap"
                assert errors == {
                    "denied-read": errno.ENOENT,
                    "denied-write": errno.EROFS,
                    "network": errno.ECONNREFUSED,
                }
                assert completed.returncode == 2 and observed["status"] == "FAIL", (
                    observed
                )
                assert checks["denied-read"]["passed"] is False
                assert checks["denied-write"]["passed"] is False
                assert observed["network"]["denied"] is False
            after = protection.host_snapshot(c, after=True)
            native_result = {
                "exitCode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": "",
            }
            cfg["protection_observation"] = {
                "before": before,
                "after": after,
                "thread_id": SID,
                "profile_digest": boundary.digest(c["permissions"]),
                "native_result_digest": boundary.digest(native_result),
            }
            assert protection.qualified(cfg, native_result) is (
                backend == "macos-sandbox-exec"
            )
            # Host source canaries and listener survive the actual sandbox run.
            for ident in ("read", "denied-read", "denied-write"):
                assert before["files"][ident] == after["files"][ident]
            assert len(healthy) == 2
        finally:
            stop.set()
            thread.join(2)
            assert not thread.is_alive()


def test_unqualified_legacy_turn_cannot_substitute_for_current_connection_probe(
    managed,
):
    cfg, _, _, _ = managed
    cfg["required_capabilities"] = ["read"]
    cfg["protection_observation"] = {"transport": {"connection_id": "a" * 32}}
    wire = rows(cfg, outcome={"turn": {"id": "turn-1"}})
    wire.append(
        {
            "method": "turn/completed",
            "params": {
                "threadId": SID,
                "turn": {"id": "turn-1", "status": "completed", "items": []},
            },
        }
    )
    with pytest.raises(ValueError):
        native.parse(encode(wire), cfg, encode(sent(cfg)))
    assert native.boundary(cfg, wire)["status"] == "UNKNOWN"


def test_malformed_permission_access_is_a_typed_refusal(managed):
    cfg, _, _, _ = managed
    cfg["file_contract"]["permissions"]["profile"]["filesystem"][
        cfg["file_contract"]["scratch_root"]
    ] = []
    with pytest.raises(ValueError):
        policy.validate(cfg["file_contract"])


@pytest.mark.parametrize(
    "method",
    [
        "process/spawn",
        "process/writeStdin",
        "process/kill",
        "thread/shellCommand",
        "thread/start/",
        "thread//start",
        "config/write",
        "unknown",
        "turn/start",
    ],
)
def test_managed_outbound_methods_refuse_before_transport_write(managed, method):
    cfg, _, _, _ = managed

    class Transport:
        def __init__(self):
            self.writes = []

        def send(self, value):
            self.writes.append(value)

    connection = Transport()
    native.restrict_connection(connection, cfg)
    with pytest.raises(ValueError):
        connection.send({"jsonrpc": "2.0", "id": 1, "method": method, "params": {}})
    assert connection.writes == []
    for request in native.requests(cfg):
        connection.send(request)
    assert connection.writes == native.requests(cfg)
    with pytest.raises(ValueError):
        connection.send({"id": 99, "result": {"approved": True}})


@pytest.mark.parametrize(
    "fault",
    [
        None,
        "busy",
        "wrong-session",
        "wrong-transcript",
        "account",
        "prefix",
        "claim",
        "profile",
        "interrupt",
    ],
)
def test_managed_exact_resume_uses_existing_account_owner_and_retains_expense_source(
    managed, monkeypatch, fault
):
    cfg, _, _, spec = managed
    cfg["required_capabilities"] = ["read"]
    root = Path(cfg["file_contract"]["scratch_root"]).parent
    transcript = root / "session.jsonl"
    initial = (
        json.dumps({"type": "session_meta", "payload": {"id": SID}}) + "\n"
    ).encode()
    transcript.write_bytes(initial)
    account = root / "synthetic-account-scope.json"
    account.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "kind": "scoped-evaluation-account",
                "account_sha256": hashlib.sha256(b"approved").hexdigest(),
            }
        )
    )
    resume = {
        "session_id": SID,
        "transcript": {
            "path": str(transcript),
            "sha256": hashlib.sha256(initial).hexdigest(),
            "size": len(initial),
        },
        "account_scope": {
            "path": str(account),
            "sha256": hashlib.sha256(account.read_bytes()).hexdigest(),
        },
        "source_generation": "b" * 64,
    }
    instances = []
    checks = []
    monkeypatch.setattr(protection.socket, "create_connection", lambda *a, **k: Echo())

    class Connection:
        def __init__(self, *a, **k):
            self.raw_stdout = bytearray()
            self.raw_stdin = bytearray()
            self.stderr = bytearray()
            self.calls = []
            self.next_id = 0
            self.cleanup = None
            self.closed = False
            instances.append(self)

        def send(self, row):
            self.raw_stdin.extend(encode([row]))
            if row.get("method") == "account/read":
                self.raw_stdout.extend(
                    encode([{"id": row["id"], "result": account_reply()}])
                )

        def call(self, method, params):
            self.next_id += 1
            self.calls.append(method)
            self.send(
                {
                    "jsonrpc": "2.0",
                    "id": self.next_id,
                    "method": method,
                    "params": params,
                }
            )
            response = reply(cfg)
            response["thread"].update(
                ephemeral=False, path=str(transcript), status={"type": "idle"}
            )
            if fault == "busy":
                response["thread"]["status"] = {"type": "active"}
            if fault == "wrong-session":
                response["thread"]["id"] = "foreign"
            if fault == "wrong-transcript":
                response["thread"]["path"] = str(root / "foreign")
            if method == "initialize":
                value = {}
            elif method == "config/read":
                value = config_read(cfg)
            elif method == "thread/read":
                value = {"thread": response["thread"]}
            elif method == "thread/resume":
                value = response
                if fault == "account":
                    account.write_text("changed")
                if fault == "prefix":
                    transcript.write_text("changed")
                if fault == "profile":
                    value["activePermissionProfile"]["id"] = "foreign"
            elif method == "command/exec":
                target = next(
                    x["path"]
                    for x in spec["filesystem"]["controls"]
                    if x["operation"] == "allowed-create"
                )
                Path(target).write_bytes(b"SYNTHESIS-STUDY-ALLOWED-WRITE\n")
                value = {
                    "exitCode": 0,
                    "stdout": json.dumps(successful_observation(spec)),
                    "stderr": "",
                }
            elif method == "turn/start":
                if fault == "interrupt":
                    raise KeyboardInterrupt()
                value = {"turn": {"id": "work-turn"}}
                with transcript.open("ab") as f:
                    f.write(b'{"type":"event_msg","payload":{"type":"token_count"}}\n')
                self.raw_stdout.extend(
                    encode(
                        [
                            {
                                "method": "turn/started",
                                "params": {
                                    "threadId": SID,
                                    "turn": {
                                        "id": "work-turn",
                                        "status": "inProgress",
                                        "items": [],
                                    },
                                },
                            },
                            {
                                "method": "turn/completed",
                                "params": {
                                    "threadId": SID,
                                    "turn": {
                                        "id": "work-turn",
                                        "status": "completed",
                                        "items": [],
                                    },
                                },
                            },
                        ]
                    )
                )
            else:
                raise AssertionError(method)
            self.raw_stdout.extend(encode([{"id": self.next_id, "result": value}]))
            return value

        def close(self):
            self.closed = True
            self.cleanup = {"group_absent": True, "leader_reaped": True}
            return self.cleanup

        def _read(self):
            raise TimeoutError("Synthetic input exhausted")

    monkeypatch.setattr(native.native_resume, "MuseConnection", Connection)

    def admission():
        checks.append(True)
        if fault == "claim" and len(checks) > 2:
            raise ValueError("Expired owner admission")

    argv = policy.server_argv(cfg["executable_identity"]["path"], cfg["file_contract"])
    code, raw, err, failure, cleanup, request_raw = native.execute(
        argv,
        cfg,
        Path(cfg["file_contract"]["scratch_root"]),
        5,
        {},
        revalidate=admission,
        resume=resume,
    )
    assert cleanup["cleanup_verified"] and all(x.closed for x in instances)
    if fault is None:
        assert code == 0, failure
        assert native.parse(raw, cfg, request_raw)["producer"] == "codex:" + SID
        assert transcript.read_bytes().startswith(
            initial
        ) and transcript.stat().st_size > len(initial)
        assert instances[0].calls == [
            "initialize",
            "config/read",
            "thread/read",
            "thread/resume",
            "config/read",
            "thread/read",
            "command/exec",
            "config/read",
            "thread/read",
            "turn/start",
        ]
        assert len(checks) >= 4
    else:
        assert code == 2 and failure
        if fault != "interrupt":
            assert "turn/start" not in instances[0].calls
    assert "thread/start" not in instances[0].calls


@pytest.mark.parametrize(
    "fault",
    [
        None,
        "wrong-account",
        "ephemeral",
        "wrong-header",
        "busy",
        "turn-capability",
        "timeout",
    ],
)
def test_persistent_allocation_is_explicit_owner_bound_and_model_free(
    managed, synthetic_connection, monkeypatch, fault
):
    cfg, _, _, _ = managed
    cfg["required_capabilities"] = ["native-callback"]
    cfg["persistent_allocation"] = True
    root = Path(cfg["file_contract"]["scratch_root"]).parent
    account = root / "allocation-account.json"
    account.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "kind": "scoped-evaluation-account",
                "account_sha256": hashlib.sha256(b"approved").hexdigest(),
            }
        )
    )
    cfg["allocation"] = {
        "account_scope": {
            "path": str(account),
            "sha256": hashlib.sha256(account.read_bytes()).hexdigest(),
        },
        "source_generation": "b" * 64,
    }
    if fault == "turn-capability":
        cfg["required_capabilities"] = ["read"]
    parent = native.native_resume.MuseConnection

    class Connection(parent):
        def call(self, method, params):
            if method != "thread/start":
                return super().call(method, params)
            self.next_id += 1
            self.calls.append(method)
            self.send(
                {
                    "jsonrpc": "2.0",
                    "id": self.next_id,
                    "method": method,
                    "params": params,
                }
            )
            if fault == "timeout":
                raise TimeoutError(
                    "Uncertain native allocation: synthetic transport loss"
                )
            path = root / "allocated.jsonl"
            path.write_text(
                json.dumps(
                    {
                        "type": "session_meta",
                        "payload": {
                            "id": "foreign" if fault == "wrong-header" else SID
                        },
                    }
                )
                + "\n"
            )
            value = reply(cfg)
            value["thread"].update(
                ephemeral=fault == "ephemeral",
                path=str(path),
                status={"type": "active" if fault == "busy" else "idle"},
            )
            if fault == "wrong-account":
                account.write_text("changed")
            self.raw_stdout.extend(
                encode(
                    [
                        hook("running"),
                        hook(
                            context="SYNTHESIS_NATIVE_RECEIPT "
                            + json.dumps({"event_id": "synthetic", "sha256": "a" * 64})
                        ),
                        {"id": self.next_id, "result": value},
                    ]
                )
            )
            return value

    monkeypatch.setattr(native.native_resume, "MuseConnection", Connection)
    checks = []

    def admission():
        checks.append(True)

    argv = policy.server_argv(cfg["executable_identity"]["path"], cfg["file_contract"])
    code, raw, err, failure, cleanup, sent = native.execute(
        argv,
        cfg,
        Path(cfg["file_contract"]["scratch_root"]),
        5,
        {},
        revalidate=admission,
    )
    calls = [m for instance in synthetic_connection for m in instance.calls]
    assert "turn/start" not in calls and "command/exec" not in calls
    assert calls.count("thread/start") <= 1 and cleanup["cleanup_verified"]
    if fault is None:
        assert code == 0, failure
        result = native.parse(raw, cfg, sent)
        assert result["allocation"]["session_id"] == SID
        assert (
            result["allocation"]["source_generation"]
            == cfg["allocation"]["source_generation"]
        )
        assert (
            result["allocation"]["transcript"]["sha256"]
            == hashlib.sha256((root / "allocated.jsonl").read_bytes()).hexdigest()
        )
        assert len(checks) >= 3
    else:
        assert code == 2 and failure


def test_exact_resume_allows_unloaded_before_loading_but_requires_idle_after(managed):
    cfg, _, _, _ = managed
    cfg["resume"] = {
        "session_id": SID,
        "transcript": {"path": "/synthetic/owned-session.jsonl"},
    }
    thread = reply(cfg)["thread"]
    thread.update(
        ephemeral=False,
        path="/synthetic/owned-session.jsonl",
        status={"type": "notLoaded"},
    )
    assert native.resume_thread(cfg, thread, before_resume=True) == thread
    with pytest.raises(ValueError):
        native.resume_thread(cfg, thread)
    thread["status"] = {"type": "idle"}
    assert native.resume_thread(cfg, thread) == thread
    thread["status"] = {"type": "active"}
    with pytest.raises(ValueError):
        native.resume_thread(cfg, thread, before_resume=True)


def test_named_profile_opt_in_is_connection_local_and_request_closed(managed):
    cfg, _, _, _ = managed
    requests = native.requests(cfg)
    assert requests[0]["params"]["capabilities"] == {"experimentalApi": True}
    assert requests[3]["params"]["permissions"] == "synthesis-control"
    assert not any(row.get("method", "").startswith("process/") for row in requests)
    assert not any(row.get("method") == "thread/shellCommand" for row in requests)
    assert "sandbox" not in requests[3]["params"]


def account_reply():
    return {
        "account": {"type": "chatgpt", "email": None, "planType": "unknown"},
        "requiresOpenaiAuth": True,
        "workspaceRouting": {
            "chatgptAccountId": "approved",
            "backendOrigin": "https://chatgpt.com",
            "accountRoutingOverride": "NO_CONSTRAINT",
        },
    }


@pytest.mark.parametrize("provider", ["openai", "different-paid-provider"])
def test_current_effective_provider_scope(managed, provider):
    cfg, _, _, _ = managed
    cfg["required_capabilities"] = ["managed-study-turn"]
    read = config_read(cfg)
    read["config"]["model_provider"] = provider
    active = reply(cfg)
    active["modelProvider"] = provider
    if provider == "openai":
        policy.verify_config(cfg, read)
        policy.verify_active(cfg, active)
    else:
        with pytest.raises(ValueError):
            policy.verify_config(cfg, read)
        with pytest.raises(ValueError):
            policy.verify_active(cfg, active)


@pytest.mark.parametrize(
    "fault",
    [
        None,
        "other-account",
        "apikey",
        "no-routing",
        "foreign-backend",
        "auth-disabled",
        "duplicate",
    ],
)
def test_actual_native_account_matches_scoped_artifact(managed, fault):
    cfg, _, _, _ = managed
    path = Path(cfg["file_contract"]["scratch_root"]).parent / "scope.json"
    raw = json.dumps(
        {
            "schema_version": 1,
            "kind": "scoped-evaluation-account",
            "account_sha256": hashlib.sha256(b"approved").hexdigest(),
        }
    )
    if fault == "duplicate":
        raw = '{"account_sha256":"' + "a" * 64 + '",' + raw[1:]
    path.write_text(raw)
    cfg["allocation"] = {
        "account_scope": {
            "path": str(path),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        },
        "source_generation": "b" * 64,
    }
    value = account_reply()
    if fault == "other-account":
        value["workspaceRouting"]["chatgptAccountId"] = "foreign"
    if fault == "apikey":
        value["account"] = {"type": "apiKey"}
    if fault == "no-routing":
        value.pop("workspaceRouting")
    if fault == "foreign-backend":
        value["workspaceRouting"]["backendOrigin"] = "https://foreign.invalid"
    if fault == "auth-disabled":
        value["requiresOpenaiAuth"] = False
    if fault is None:
        assert native.verify_account(cfg, value)
    else:
        with pytest.raises(ValueError):
            native.verify_account(cfg, value)


def test_unscoped_managed_provider_is_not_limited_by_evaluation_grant(managed):
    cfg, _, _, _ = managed
    read = config_read(cfg)
    read["config"]["model_provider"] = "legitimate-configured-provider"
    read["config"]["model_providers"] = {
        "legitimate-configured-provider": {
            "base_url": "https://synthetic-provider.invalid"
        }
    }
    active = reply(cfg)
    active["modelProvider"] = "legitimate-configured-provider"
    policy.verify_config(cfg, read)
    policy.verify_active(cfg, active)
    cfg["required_capabilities"] = ["managed-study-turn"]
    with pytest.raises(ValueError):
        policy.verify_config(cfg, read)
    with pytest.raises(ValueError):
        policy.verify_active(cfg, active)
    with pytest.raises(ValueError):
        native.requests(cfg)


@pytest.mark.parametrize("fault", ["existing", "partial"])
def test_native_account_preplay_refuses_before_any_request(managed, fault):
    cfg, _, _, _ = managed

    class Endpoint:
        raw_stdout = bytearray(
            encode([{"id": "synthesis-account-before-turn", "result": account_reply()}])
        )
        writes = []

        def send(self, row):
            self.writes.append(row)

    endpoint = Endpoint()
    if fault == "partial":
        endpoint.raw_stdout = endpoint.raw_stdout[:-1]
    with pytest.raises(ValueError, match="predates"):
        native.account_read(endpoint, cfg, "before-turn")
    assert endpoint.writes == []


@pytest.mark.parametrize(
    "denial", ["EPERM", "EACCES", "ENOENT", "EROFS", "ECONNREFUSED", "ETIMEDOUT", "EIO"]
)
def test_fixed_probe_requires_permission_denial_not_namespace_or_io_error(
    managed, monkeypatch, denial
):
    import errno
    import os
    import socket

    _, _, _, spec = managed
    denied_paths = {
        row["path"]
        for row in spec["filesystem"]["controls"]
        if row["operation"] in ("denied-read", "denied-write")
    }
    original_open = os.open
    code = getattr(errno, denial)

    def controlled_open(path, *args, **kwargs):
        if str(path) in denied_paths:
            raise OSError(code, "synthetic exact denial")
        return original_open(path, *args, **kwargs)

    def controlled_connect(self, address):
        raise OSError(code, "synthetic exact denial")

    monkeypatch.setattr(os, "open", controlled_open)
    monkeypatch.setattr(socket.socket, "connect", controlled_connect)
    observed = protection.observe(spec)
    qualified_denial = denial in {"EPERM", "EACCES"}
    rows = {row["id"]: row for row in observed["filesystem"]["checks"]}
    assert rows["read"]["passed"] and rows["create"]["passed"]
    assert rows["denied-read"]["passed"] is qualified_denial
    assert rows["denied-write"]["passed"] is qualified_denial
    assert observed["network"]["denied"] is qualified_denial
    assert observed["status"] == ("PASS" if qualified_denial else "FAIL")
    assert observed["native_acceptance"] == "UNKNOWN"

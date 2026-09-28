"""Provider-free synthetic processes exercising the actual bounded Hermes owners."""

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import stat
import tempfile

import pytest
import hermes_transport as transport
import native_observations as native

CONF = Path(__file__).resolve().parents[2] / "synthesis-agent-conformance/scripts"
sys.path.insert(0, str(CONF))
import hermes_adapter  # noqa: E402
from test_hermes_adapter import event  # noqa: E402
import test_hermes_adapter as hermes_fixtures  # noqa: E402

profile = hermes_fixtures.profile


@pytest.fixture
def native_producer(tmp_path):
    """A real finite canonical process owns peers independently of pytest's venv."""
    import base64
    import select
    import signal
    from types import SimpleNamespace

    driver = tmp_path / "native-producer.py"
    driver.write_text(
        "import base64,json,signal,subprocess,sys\n"
        "signal.alarm(90)\n"
        "print(json.dumps({'ready':True}),flush=True)\n"
        "for line in sys.stdin:\n"
        " q=json.loads(line)\n"
        " if q is None: break\n"
        " assert set(q)=={'argv','timeout'} and 0<q['timeout']<=10\n"
        " assert isinstance(q['argv'],list) and 1<=len(q['argv'])<=32\n"
        " assert all(isinstance(x,str) and len(x)<=16384 for x in q['argv'])\n"
        " try:\n"
        "  r=subprocess.run(q['argv'],capture_output=True,timeout=q['timeout'])\n"
        "  assert len(r.stdout)+len(r.stderr)<=8*1024*1024\n"
        "  result={'returncode':r.returncode,'stdout':base64.b64encode(r.stdout).decode(),'stderr':base64.b64encode(r.stderr).decode()}\n"
        " except Exception as exc: result={'error':type(exc).__name__}\n"
        " print(json.dumps(result),flush=True)\n"
    )
    interpreter = Path(sys.executable).resolve(strict=True)
    # Framework Python's bin launcher re-execs this actual interpreter on macOS.
    # Use the same explicit runtime path already recognized by the sandbox owner.
    framework = Path(sys.base_prefix) / "Resources/Python.app/Contents/MacOS/Python"
    if sys.platform == "darwin" and framework.is_file():
        interpreter = framework.resolve(strict=True)
    argv = [str(interpreter), str(driver)]
    stderr = (tmp_path / "native-producer.stderr").open("wb")
    process = subprocess.Popen(
        argv,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=stderr,
        start_new_session=True,
    )
    wire = tmp_path / "native-producer-wire.jsonl"

    def receive(seconds):
        deadline = time.monotonic() + seconds
        raw = bytearray()
        while not raw.endswith(b"\n"):
            remaining = deadline - time.monotonic()
            assert remaining > 0, "finite native fixture response expired"
            assert select.select([process.stdout], [], [], remaining)[0]
            block = os.read(process.stdout.fileno(), 65536)
            assert block, "native fixture closed before response"
            raw.extend(block)
            assert len(raw) <= 12 * 1024 * 1024
        with wire.open("ab") as stream:
            stream.write(raw)
        return json.loads(raw)

    def run(argv, *, capture_output=True, timeout):
        assert capture_output is True and 0 < timeout <= 10
        request = json.dumps({"argv": argv, "timeout": timeout}).encode() + b"\n"
        with wire.open("ab") as stream:
            stream.write(request)
        process.stdin.write(request)
        process.stdin.flush()
        response = receive(timeout + 2)
        assert "error" not in response, response
        return subprocess.CompletedProcess(
            argv,
            response["returncode"],
            base64.b64decode(response["stdout"]),
            base64.b64decode(response["stderr"]),
        )

    try:
        assert receive(3) == {"ready": True}
        identity = transport.process_identity(process.pid)
        assert identity["argv"] == argv
        yield SimpleNamespace(identity=identity, run=run)
    finally:
        if process.poll() is None:
            try:
                process.stdin.write(b"null\n")
                process.stdin.flush()
            except BrokenPipeError:
                pass
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=2)
        try:
            os.killpg(process.pid, 0)
        except ProcessLookupError:
            absent = True
        else:
            os.killpg(process.pid, signal.SIGKILL)
            absent = False
        process.stdin.close()
        process.stdout.close()
        stderr.close()
        (tmp_path / "native-producer-disposition.json").write_text(
            json.dumps(
                {
                    "pid": process.pid,
                    "returncode": process.returncode,
                    "group_absent": absent,
                    "argv": argv,
                }
            )
        )
        assert absent, "native fixture descendants survived terminal wait"


@pytest.fixture
def short_native_root(tmp_path):
    """Keep Unix socket paths short without losing release-runner custody."""
    # A native platform path, independent of the caller's retained TMPDIR.
    base = Path("/private/tmp" if sys.platform == "darwin" else "/tmp")
    base_info = base.lstat()
    if not stat.S_ISDIR(base_info.st_mode):
        raise ValueError("Synthetic local socket root must be a real directory")
    root = Path(tempfile.mkdtemp(prefix=".syn-h-", dir=base))
    info = root.lstat()
    if (
        not stat.S_ISDIR(info.st_mode)
        or stat.S_IMODE(info.st_mode) != 0o700
        or info.st_uid != os.geteuid()
        or len(os.fsencode(root / "s/hook.sock")) > 100
    ):
        raise ValueError("Synthetic socket workspace identity or bound is invalid")
    record = {
        "schema_version": 1,
        "original_path": str(root),
        "device": info.st_dev,
        "inode": info.st_ino,
        "mode": 0o700,
        "owner_uid": info.st_uid,
        "status": "OWNED_ACTIVE",
    }
    receipt = tmp_path / "short-native-custody.json"
    receipt.write_text(json.dumps(record, sort_keys=True) + "\n")
    try:
        yield root
    finally:
        current = root.lstat()
        if (current.st_dev, current.st_ino, current.st_mode, current.st_uid) != (
            info.st_dev,
            info.st_ino,
            info.st_mode,
            info.st_uid,
        ):
            record["status"] = "UNRESOLVED_REPLACEMENT"
            receipt.write_text(json.dumps(record, sort_keys=True) + "\n")
            raise ValueError(
                "Synthetic short workspace was replaced; retained without cleanup"
            )
        # Preserve every file/special-node metadata for the surrounding release
        # custody owner. No recursive cleanup or deletion of another path occurs.
        retained = tmp_path / ("retained-" + root.name)
        retained.mkdir(mode=0o700)
        destination = retained / "contents"
        root.rename(destination)
        after = destination.lstat()
        assert (after.st_dev, after.st_ino, after.st_mode, after.st_uid) == (
            info.st_dev,
            info.st_ino,
            info.st_mode,
            info.st_uid,
        )
        record.update(status="RETAINED", retained_path=str(destination))
        receipt.write_text(json.dumps(record, sort_keys=True) + "\n")


def test_short_native_workspace_ignores_long_inherited_tmpdir(tmp_path, monkeypatch):
    inherited = tmp_path / ("long-inherited-" + "x" * 160)
    inherited.mkdir()
    monkeypatch.setenv("TMPDIR", str(inherited))
    owner = short_native_root.__wrapped__(tmp_path)
    root = next(owner)
    assert root.parent != inherited and len(os.fsencode(root / "s/hook.sock")) <= 100
    assert stat.S_IMODE(root.stat().st_mode) == 0o700
    (root / "empty").write_bytes(b"")
    (root / "evidence").write_bytes(b"synthetic exact custody")
    with pytest.raises(StopIteration):
        next(owner)
    receipt = json.loads((tmp_path / "short-native-custody.json").read_text())
    assert receipt["status"] == "RETAINED" and not root.exists()
    retained = Path(receipt["retained_path"])
    assert (retained / "evidence").read_bytes() == b"synthetic exact custody"
    assert (retained / "empty").read_bytes() == b""


def pair():
    context = "Synthetic context\nSYNTHESIS_NATIVE_RECEIPT " + json.dumps(
        {"event_id": "00000000-0000-4000-8000-000000000001", "sha256": "a" * 64}
    )
    common = {
        "session_id": "session-opaque-1",
        "cwd": "/synthetic",
        "profile": "default",
    }
    release = {
        "release_root": "/synthetic/source",
        "content_digest": "b" * 64,
        "version": "1.2.3",
    }
    return [
        {
            "payload": {
                **common,
                "hook_event_name": "pre_llm_call",
                "extra": {"turn_id": "turn-1"},
            },
            "result": {"context": context},
            "release": release,
            "peer": {},
            "sequence": 0,
        },
        {
            "payload": {
                **common,
                "hook_event_name": "pre_api_request",
                "extra": {
                    "turn_id": "turn-1",
                    "api_request_id": "request-1",
                    "request": {
                        "method": "POST",
                        "body": {
                            "messages": [
                                {"role": "user", "content": "question\n\n" + context}
                            ]
                        },
                    },
                },
            },
            "result": {},
            "release": release,
            "peer": {},
            "sequence": 1,
        },
    ]


def selected():
    return {"session_id": "session-opaque-1", "cwd": "/synthetic", "profile": "default"}


def test_exact_consumer_pair_positive():
    assert transport.validate_pair(pair(), selected())["sha256"] == "a" * 64


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "reordered",
        "duplicate",
        "wrong-turn",
        "wrong-session",
        "wrong-profile",
        "wrong-source",
        "changed-context",
        "no-marker",
        "duplicate-marker",
        "truncated",
        "wrong-role",
        "bool-sequence",
    ],
)
def test_pair_cannot_mint_consumption(fault):
    rows = pair()
    if fault == "missing":
        rows.pop()
    elif fault == "reordered":
        rows.reverse()
    elif fault == "duplicate":
        rows.append(deepcopy(rows[-1]))
    elif fault == "wrong-turn":
        rows[-1]["payload"]["extra"]["turn_id"] = "foreign"
    elif fault == "wrong-session":
        rows[-1]["payload"]["session_id"] = "foreign"
    elif fault == "wrong-profile":
        rows[-1]["payload"]["profile"] = "foreign"
    elif fault == "wrong-source":
        rows[-1]["release"] = dict(rows[-1]["release"], content_digest="c" * 64)
    elif fault == "changed-context":
        rows[-1]["payload"]["extra"]["request"]["body"]["messages"][0]["content"] += (
            "changed"
        )
    elif fault == "no-marker":
        rows[0]["result"]["context"] = "context"
    elif fault == "duplicate-marker":
        rows[-1]["payload"]["extra"]["request"]["body"]["messages"].append(
            deepcopy(rows[-1]["payload"]["extra"]["request"]["body"]["messages"][0])
        )
    elif fault == "truncated":
        rows[-1]["payload"]["extra"]["request"] = {"_truncated": True}
    elif fault == "wrong-role":
        rows[-1]["payload"]["extra"]["request"]["body"]["messages"][0]["role"] = (
            "assistant"
        )
    elif fault == "bool-sequence":
        rows[0]["sequence"] = False
    with pytest.raises(ValueError):
        transport.validate_pair(rows, selected())


def test_actual_native_reader_does_not_grant_permissions(tmp_path):
    header = {
        "type": "synthesis.hermes_observation",
        "schema": 1,
        "session_id": "session-opaque-1",
        "producer_version": "synthetic",
        "capture_id": "capture-1",
        "selection_sha256": "0" * 64,
    }
    p = tmp_path / "source.jsonl"
    p.write_text("".join(json.dumps(x) + "\n" for x in [header, *pair()]))
    b, c = native.enroll_source(
        p,
        client="hermes",
        expected_root_session_id="session-opaque-1",
        mode="synthetic",
    )
    batch = native.read_page(b, c)
    assert not batch["gaps"], batch
    assert len(batch["events"]) == 2
    assert all(
        e["data"]["native_permissions"] == "UNKNOWN"
        and not e["data"]["execution_authorized"]
        for e in batch["events"]
    )


def test_adapter_has_actual_post_assembly_observer(profile, monkeypatch):
    monkeypatch.setattr(transport, "send", lambda *a, **k: None)
    result = hermes_adapter.handle(
        event(profile, "pre_api_request"),
        profile,
        profile / "index",
        "alpha",
        active={"version": "synthetic"},
        capture_socket=profile / "s",
    )
    assert result == {}  # ignored observer output grants no execution authority


def _process_fixture(tmp_path, native_producer):
    # Pin the dedicated synthetic producer's real identity, independent of the
    # selected pytest interpreter/virtualenv. It directly owns each hook child.
    script = tmp_path / "peer.py"
    script.write_text(
        'import socket,json,sys\nfrom pathlib import Path\ns=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)\ns.settimeout(3)\ns.connect(sys.argv[1])\ns.sendall(Path(sys.argv[2]).read_bytes())\ns.shutdown(socket.SHUT_WR)\nassert s.recv(16)==b"retained\\n"\ns.close()\n'
    )
    parent = native_producer.identity
    inputs = {}
    for arg in [*parent["argv"], str(Path(sys.executable).resolve()), str(script)]:
        if arg.startswith("/") and Path(arg).is_file():
            inputs[arg] = hashlib.sha256(Path(arg).read_bytes()).hexdigest()
    home = tmp_path / "home"
    home.mkdir()
    selection = {
        "schema": 1,
        "client": "hermes",
        **selected(),
        "cwd": str(tmp_path),
        "profile_home": str(home),
        "state_home": str(home),
        "process": parent,
        "producer_version": "synthetic",
        "source_files": inputs,
        "hook_argv": [],
    }
    return script, selection


def test_real_local_peer_custody_and_cleanup(
    tmp_path, short_native_root, native_producer
):
    script, selection = _process_fixture(tmp_path, native_producer)
    # The Unix platform pathname limit is explicit, not a global chdir workaround.
    short = short_native_root
    sock = short / "h"
    bodies = pair()
    for row in bodies:
        row["payload"]["cwd"] = str(tmp_path)
    packet = tmp_path / "packet.json"
    argv = [selection["process"]["argv"][0], str(script), str(sock), str(packet)]
    selection["hook_argv"] = argv
    # Packet is data, not executable, and stays absent until admission finishes.
    result = []
    thread = threading.Thread(
        target=lambda: result.append(transport.capture(sock, selection, 4))
    )
    thread.start()
    try:
        limit = time.monotonic() + 2
        while not sock.exists() and time.monotonic() < limit:
            time.sleep(0.01)
        for row in bodies:
            packet.write_text(
                json.dumps(
                    {k: v for k, v in row.items() if k not in {"peer", "sequence"}}
                )
            )
            child = native_producer.run(argv, capture_output=True, timeout=3)
            assert child.returncode == 0, (child.stderr, result)
        thread.join(5)
        assert not thread.is_alive()
        assert result and result[0][1] is None, result
        assert len(result[0][0]) == 2 and not sock.exists()
    finally:
        thread.join(5)
        assert not thread.is_alive()


@pytest.mark.parametrize(
    "field,form",
    [("messages", "string"), ("messages", "text"), ("input", "input_text")],
)
def test_supported_actual_request_shapes(field, form):
    rows = pair()
    body = rows[1]["payload"]["extra"]["request"]["body"]
    messages = body.pop("messages")
    if form != "string":
        messages[0]["content"] = [{"type": form, "text": messages[0]["content"]}]
    body[field] = messages
    assert transport.validate_pair(rows, selected())["sha256"] == "a" * 64


@pytest.mark.parametrize(
    "fault",
    [
        "nested-truncation",
        "hidden-duplicate",
        "ambiguous-wire",
        "depth-truncation",
        "sequence-truncation",
        "unknown-text-block",
    ],
)
def test_partial_or_ambiguous_actual_request_refused(fault):
    rows = pair()
    body = rows[1]["payload"]["extra"]["request"]["body"]
    context = rows[0]["result"]["context"]
    if fault == "nested-truncation":
        body["messages"].append({"role": "user", "content": [{"_truncated_items": 3}]})
    elif fault == "hidden-duplicate":
        body["messages"].append(
            {"role": "assistant", "content": [{"type": "text", "text": context}]}
        )
    elif fault == "ambiguous-wire":
        body["input"] = deepcopy(body["messages"])
    elif fault == "depth-truncation":
        body["messages"].append({"role": "user", "content": "<dict depth limit>"})
    elif fault == "sequence-truncation":
        body["messages"].append({"_truncated_items": 2})
    elif fault == "unknown-text-block":
        body["messages"][0]["content"] = [
            {"type": "unknown", "text": "Question\n\n" + context}
        ]
    with pytest.raises(ValueError):
        transport.validate_pair(rows, selected())


@pytest.mark.parametrize("fault", ["wrong-argv", "changed-source", "malformed-wire"])
def test_real_peer_refusal_retains_failure(
    tmp_path, fault, short_native_root, native_producer
):
    script, selection = _process_fixture(tmp_path, native_producer)
    short = short_native_root
    sock = short / "h"
    packet = tmp_path / "packet.json"
    argv = [selection["process"]["argv"][0], str(script), str(sock), str(packet)]
    selection["hook_argv"] = argv
    result = []
    frames = []
    thread = threading.Thread(
        target=lambda: result.append(
            transport.capture(sock, selection, 2, raw_frames=frames)
        )
    )
    thread.start()
    try:
        end = time.monotonic() + 1
        while not sock.exists() and time.monotonic() < end:
            time.sleep(0.01)
        assert sock.exists()
        packet.write_text("{malformed" if fault == "malformed-wire" else "{}")
        if fault == "wrong-argv":
            argv = [*argv, "unexpected"]
        if fault == "changed-source":
            script.write_text(script.read_text() + "\n# mutation after admission\n")
        done = native_producer.run(argv, capture_output=True, timeout=3)
        assert done.returncode != 0
        thread.join(3)
        assert not thread.is_alive()
        assert result and result[0][1] and not sock.exists(), result
        if fault == "malformed-wire":
            import base64

            assert frames[0]["complete"] is True
            assert base64.b64decode(frames[0]["raw_base64"]) == b"{malformed"
        else:
            assert frames == []
    finally:
        thread.join(3)
        assert not thread.is_alive()


def test_deadline_retains_foreign_replacement(
    tmp_path, short_native_root, native_producer
):
    script, selection = _process_fixture(tmp_path, native_producer)
    selection["hook_argv"] = [selection["process"]["argv"][0], str(script)]
    short = short_native_root
    sock = short / "h"
    moved = short / "old"
    result = []
    thread = threading.Thread(
        target=lambda: result.append(transport.capture(sock, selection, 0.3))
    )
    thread.start()
    try:
        end = time.monotonic() + 1
        while not sock.exists() and time.monotonic() < end:
            time.sleep(0.01)
        sock.rename(moved)
        sock.write_text("foreign")
        thread.join(2)
        assert not thread.is_alive()
        assert "foreign path retained" in result[0][1]
        assert sock.read_text() == "foreign"
    finally:
        thread.join(2)
        assert not thread.is_alive()


def test_capture_cancellation_closes_owned_listener(
    tmp_path, monkeypatch, short_native_root, native_producer
):
    script, selection = _process_fixture(tmp_path, native_producer)
    selection["hook_argv"] = [selection["process"]["argv"][0], str(script)]
    short = short_native_root
    sock = short / "h"

    def interrupted(*args, **kwargs):
        raise KeyboardInterrupt("synthetic cancellation")

    monkeypatch.setattr(transport.socket.socket, "accept", interrupted)
    rows, error = transport.capture(sock, selection, 1)
    assert not rows and error.startswith("KeyboardInterrupt") and not sock.exists()


def test_tool_created_grandchild_cannot_impersonate_direct_native_hook(
    tmp_path, short_native_root, native_producer
):
    script, selection = _process_fixture(tmp_path, native_producer)
    short = short_native_root
    sock = short / "h"
    packet = tmp_path / "packet.json"
    argv = [selection["process"]["argv"][0], str(script), str(sock), str(packet)]
    selection["hook_argv"] = argv
    wrapper = tmp_path / "tool-child.py"
    wrapper.write_text(
        "import subprocess,sys\nr=subprocess.run(sys.argv[1:], timeout=3)\nraise SystemExit(r.returncode)\n"
    )
    result = []
    frames = []
    thread = threading.Thread(
        target=lambda: result.append(
            transport.capture(sock, selection, 5, raw_frames=frames)
        )
    )
    thread.start()
    try:
        end = time.monotonic() + 2
        while not sock.exists() and time.monotonic() < end:
            time.sleep(0.01)
        assert sock.exists()
        for row in pair():
            row["payload"]["cwd"] = str(tmp_path)
            packet.write_text(
                json.dumps(
                    {k: v for k, v in row.items() if k not in {"peer", "sequence"}}
                )
            )
            done = native_producer.run(
                [selection["process"]["argv"][0], str(wrapper), *argv],
                capture_output=True,
                timeout=4,
            )
            if done.returncode:
                break
        thread.join(6)
        assert not thread.is_alive()
        assert result and result[0][1] and result[0][0] == [], result
        assert frames == []
        assert not sock.exists()
    finally:
        thread.join(6)
        assert not thread.is_alive()


def test_process_identity_uses_system_inspector_not_search_path(tmp_path, monkeypatch):
    fake = tmp_path / "ps"
    sentinel = tmp_path / "executed"
    fake.write_text(
        "#!"
        + sys.executable
        + "\nfrom pathlib import Path\nPath("
        + repr(str(sentinel))
        + ").write_text('ran')\nprint('424242 7 "
        + str(os.getuid())
        + " Sun Sep 27 01:02:03 2026 /fixture/native.py')\n"
    )
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path) + os.pathsep + os.environ["PATH"])
    with pytest.raises((OSError, ValueError, subprocess.SubprocessError)):
        transport.process_identity(424242)
    assert not sentinel.exists()
    assert transport.process_identity(os.getpid())["pid"] == os.getpid()


def source_selection(tmp_path, monkeypatch):
    executable = str(Path(sys.executable).resolve())
    script = tmp_path / "selected.py"
    script.write_text("# selected direct script\n")
    process = {
        "pid": 101,
        "ppid": 99,
        "uid": os.getuid(),
        "start": "observed birth",
        "argv": [executable, str(script)],
    }
    monkeypatch.setattr(transport, "process_identity", lambda *a, **k: process)
    pins = {
        filename: hashlib.sha256(Path(filename).read_bytes()).hexdigest()
        for filename in process["argv"]
    }
    return {
        "schema": 1,
        "client": "hermes",
        "session_id": "opaque",
        "profile_home": str(tmp_path),
        "profile": "default",
        "cwd": str(tmp_path),
        "process": process,
        "hook_argv": list(process["argv"]),
        "source_files": pins,
        "producer_version": "fixture",
        "state_home": str(tmp_path),
    }


@pytest.mark.parametrize(
    "fault",
    [
        "relative-executable",
        "relative-script",
        "missing-executable",
        "missing-script",
        "unpinned-executable",
        "unpinned-script",
        "changed-script",
        "linked-script",
    ],
)
def test_execution_sources_require_actual_exact_membership(
    tmp_path, monkeypatch, fault
):
    value = source_selection(tmp_path, monkeypatch)
    argv = value["hook_argv"]
    if fault == "relative-executable":
        argv[0] = "python3"
    elif fault == "relative-script":
        argv[1] = "selected.py"
    elif fault == "missing-executable":
        argv[0] = str(tmp_path / "absent-executable")
    elif fault == "missing-script":
        Path(argv[1]).unlink()
    elif fault.startswith("unpinned-"):
        value["source_files"].pop(argv[0 if fault.endswith("executable") else 1])
    elif fault == "changed-script":
        Path(argv[1]).write_text("# changed\n")
    elif fault == "linked-script":
        original = Path(argv[1])
        kept = original.with_name("kept.py")
        original.rename(kept)
        original.symlink_to(kept)
    with pytest.raises((ValueError, OSError)):
        transport.validate_selection(value)


def test_exact_execution_sources_and_module_data_operands(tmp_path, monkeypatch):
    value = source_selection(tmp_path, monkeypatch)
    assert transport.validate_selection(value) == value
    value["process"]["argv"] = [
        value["process"]["argv"][0],
        "-B",
        "-m",
        "pytest",
        "data_test.py",
    ]
    assert transport.validate_selection(value) == value


@pytest.mark.parametrize("which", ["process", "hook"])
def test_directory_operand_is_data_not_an_executable_source(
    tmp_path, monkeypatch, which
):
    chosen = source_selection(tmp_path, monkeypatch)
    directory = tmp_path / "output"
    directory.mkdir()
    assert os.access(directory, os.X_OK) and not directory.is_file()
    argv = chosen["process"]["argv"] if which == "process" else chosen["hook_argv"]
    argv.extend(["--output", str(directory)])
    assert transport.validate_selection(chosen) == chosen


@pytest.mark.parametrize("which", ["process", "hook"])
def test_directory_as_actual_executable_is_still_refused(tmp_path, monkeypatch, which):
    chosen = source_selection(tmp_path, monkeypatch)
    directory = tmp_path / "output"
    directory.mkdir()
    argv = chosen["process"]["argv"] if which == "process" else chosen["hook_argv"]
    argv[0] = str(directory)
    chosen["source_files"][str(directory)] = "0" * 64
    with pytest.raises((OSError, ValueError)):
        transport.validate_selection(chosen)

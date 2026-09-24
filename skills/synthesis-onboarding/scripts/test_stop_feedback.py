"""Stop feedback is bounded without converting failed protection into success."""
import json
import os
import subprocess
import time

import pytest

import release_runtime as runtime
import system_contract
from test_release_runtime import active, replace, SCRIPT  # noqa: F401


def event(**changes):
    return {"hook_event_name": "Stop", "session_id": "fixture-session",
            "turn_id": "fixture-turn", "stop_hook_active": False, **changes}


def launch(active, payload, *args):
    pointer, _, data = active
    return subprocess.run([data["launcher"]["path"], "exec-public", "--hook-event", "Stop",
                           *args, SCRIPT], input=payload, capture_output=True, timeout=5)


def assert_terminal(result):
    assert result.returncode == 0, result.stderr.decode()
    output = json.loads(result.stdout)
    assert output["continue"] is False
    assert output["stopReason"]
    assert "UNRESOLVED" in output["systemMessage"]
    assert "decision" not in output
    return output


def test_stop_failure_has_one_corrective_continuation_then_terminal():
    first = runtime.stop_failure(event(), "unfinished", "status=UNKNOWN")
    assert first["decision"] == "block"
    for reason in ("unfinished", "changed error family"):
        repeated = runtime.stop_failure(event(stop_hook_active=True), reason, "status=UNKNOWN")
        assert repeated["continue"] is False
        assert "UNKNOWN" in repeated["systemMessage"]
        assert "decision" not in repeated
    assert runtime.stop_failure(event(turn_id="new-human-turn"), "unfinished")["decision"] == "block"


@pytest.mark.parametrize("payload", [None, {}, [], event(session_id=""), event(stop_hook_active="false")])
def test_unidentifiable_stop_is_terminal(payload):
    assert runtime.stop_failure(payload, "unverified")["continue"] is False


@pytest.mark.parametrize("damage", ["missing-descriptor", "digest", "interpreter", "entrypoint"])
def test_embedded_launcher_dependency_failure_is_terminal(active, damage):
    pointer, root, data = active
    if damage == "missing-descriptor":
        pointer.unlink()
    elif damage == "digest":
        replace(pointer, data, content_digest="0" * 64)
    elif damage == "interpreter":
        replace(pointer, data, interpreter={**data["interpreter"], "sha256": "0" * 64})
    else:
        (root / "skills" / SCRIPT).unlink()
    assert_terminal(launch(active, json.dumps(event()).encode()))


@pytest.mark.parametrize("payload", [b"broken", b"[]", b"{}", b"\xff"])
def test_embedded_launcher_bad_native_input_is_terminal(active, payload):
    assert_terminal(launch(active, payload))


def child(active, program):
    pointer, root, data = active
    (root / "skills" / SCRIPT).write_text(program)
    replace(pointer, data, content_digest=system_contract.canonical_tree_digest(root))


@pytest.mark.parametrize("program", ["import sys; sys.exit(2)",
    "print('not native JSON')", "print('[]')", "print('{\"decision\":\"block\",\"reason\":\"fix it\"}')"])
def test_embedded_launcher_repeated_child_failure_is_terminal(active, program):
    child(active, program)
    assert_terminal(launch(active, json.dumps(event(stop_hook_active=True)).encode()))


def test_embedded_launcher_timeout_is_terminal_on_first_failure(active):
    child(active, "import time; time.sleep(10)")
    assert_terminal(launch(active, json.dumps(event()).encode(), "--timeout-seconds", "0.02"))


def test_healthy_repeated_stop_preserves_child_result(active):
    child(active, "print('{\"systemMessage\":\"HEALTHY\"}')")
    result = launch(active, json.dumps(event(stop_hook_active=True)).encode())
    assert result.returncode == 0
    assert json.loads(result.stdout) == {"systemMessage": "HEALTHY"}


def test_pretooluse_failure_stays_nonzero_and_never_terminalizes(active):
    pointer, _, data = active
    pointer.unlink()
    result = subprocess.run([data["launcher"]["path"], "exec-public", SCRIPT],
        input=json.dumps({"hook_event_name": "PreToolUse"}).encode(), capture_output=True, timeout=5)
    assert result.returncode == 2
    assert b'"continue"' not in result.stdout


def test_stalled_pipe_is_bounded_and_never_runs_a_child(active):
    pointer, _, data = active
    reader, writer = os.pipe()
    try:
        os.write(writer, b'{"hook_event_name":"Stop"')
        started = time.monotonic()
        result = subprocess.run([data["launcher"]["path"], "exec-public", "--hook-event", "Stop",
            "--stdin-wait-seconds", "0.03", SCRIPT], stdin=reader, capture_output=True, timeout=2)
        assert time.monotonic() - started < 1
        assert_terminal(result)
    finally:
        os.close(reader)
        os.close(writer)

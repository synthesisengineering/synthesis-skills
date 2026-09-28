"""Cancellation wire/OS boundaries; every process and wire is synthetic."""

import json
import os
from pathlib import Path
import socket
import sys
import time
import pytest
import native_resume
import managed_native as native
import managed_permissions as policy
import hermes_transport
from test_managed_permissions import managed, synthetic_connection, reply
from test_native_callback import encode

__all__ = ["managed", "synthetic_connection"]


@pytest.mark.parametrize(
    "terminal",
    ["interrupted", "completed", "failed", "foreign", "duplicate", "malformed"],
)
def test_current_cancel_interrupts_exact_started_turn(
    managed, synthetic_connection, monkeypatch, terminal
):
    cfg = managed[0]
    cfg["required_capabilities"] = ["read"]
    cancelled = [False]
    original = native.native_resume.MuseConnection

    class Connection(original):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.deadline = time.monotonic() + 5

        def send(self, value):
            super().send(value)
            if value.get("method") == "turn/interrupt":
                assert value["params"] == {
                    "threadId": reply(cfg)["thread"]["id"],
                    "turnId": "synthetic-turn",
                }
                row = {
                    "method": "turn/completed",
                    "params": {
                        "threadId": value["params"]["threadId"],
                        "turn": {
                            "id": "foreign"
                            if terminal == "foreign"
                            else "synthetic-turn",
                            "status": "interrupted"
                            if terminal in ("foreign", "duplicate", "malformed")
                            else terminal,
                            "items": [],
                        },
                    },
                }
                if terminal == "malformed":
                    row["params"]["turn"].pop("items")
                    row["params"]["turn"]["status"] = "interrupted"
                self.raw_stdout.extend(
                    encode([row, row] if terminal == "duplicate" else [row])
                )

        def call(self, method, params):
            if method not in ("thread/read", "turn/start"):
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
            if method == "thread/read":
                value = {"thread": reply(cfg)["thread"]}
                value["thread"]["status"] = {"type": "idle"}
            else:
                value = {"turn": {"id": "synthetic-turn"}}
                self.raw_stdout.extend(
                    encode(
                        [
                            {
                                "method": "turn/started",
                                "params": {
                                    "threadId": reply(cfg)["thread"]["id"],
                                    "turn": {
                                        "id": "synthetic-turn",
                                        "status": "inProgress",
                                        "items": [],
                                    },
                                },
                            }
                        ]
                    )
                )
                cancelled[0] = True
            self.raw_stdout.extend(encode([{"id": self.next_id, "result": value}]))
            return value

    monkeypatch.setattr(native.native_resume, "MuseConnection", Connection)

    def revalidate():
        if cancelled[0]:
            raise native_resume.NativeCancellation(
                {
                    "requested": True,
                    "run_id": "synthetic",
                    "child_id": "child",
                    "intent_id": "intent",
                    "reason": "fixture",
                }
            )

    result = native.execute(
        policy.server_argv(cfg["executable_identity"]["path"], cfg["file_contract"]),
        cfg,
        Path(cfg["file_contract"]["scratch_root"]),
        3,
        {},
        revalidate=revalidate,
    )
    assert result[0] == 2 and result[4]["cleanup_verified"]
    cancellation = result[4]["cancellation"]
    assert cancellation["interrupt_sent"]
    assert cancellation["native_terminal"] == (
        "UNKNOWN" if terminal in ("foreign", "duplicate", "malformed") else terminal
    )
    assert (
        sum(
            row.get("method") == "turn/interrupt"
            for row in map(json.loads, result[5].splitlines())
        )
        == 1
    )
    assert synthetic_connection[0].closed


@pytest.mark.parametrize("busy", [False, True])
def test_real_shared_pipe_owner_notices_cancel_and_reaps(tmp_path, busy):
    script = tmp_path / "wire.py"
    script.write_text(
        "import json,time\n"
        + (
            "while True:\n print(json.dumps({'method':'synthetic/notice','params':{}}),flush=True)\n time.sleep(.01)\n"
            if busy
            else "time.sleep(10)\n"
        )
    )
    c = native_resume.MuseConnection(
        sys.executable,
        tmp_path,
        timeout=3,
        max_bytes=1024 * 1024,
        command=[sys.executable, "-B", str(script)],
        environment={"PATH": os.defpath},
        require_jsonrpc=False,
    )
    reads = []

    def current():
        reads.append(1)
        if len(reads) == 3:
            raise native_resume.NativeCancellation(
                {"requested": True, "reason": "synthetic current cancel"}
            )

    c.owner_check = current
    try:
        with pytest.raises(native_resume.NativeCancellation):
            for _ in range(6):
                c._read(seconds=0.05)
    finally:
        c.owner_check = None
        cleanup = c.close()
    assert cleanup["group_absent"] and cleanup["leader_reaped"]
    assert len(reads) == 3
    if busy:
        assert c.raw_stdout


def test_hermes_partial_frame_cancellation_keeps_bytes_and_no_native_signal():
    received = []
    calls = []
    left, right = socket.socketpair()
    try:
        right.sendall(b'{"synthetic":')

        def current():
            calls.append(1)
            if len(calls) == 2:
                raise native_resume.NativeCancellation(
                    {"requested": True, "reason": "stop passive capture"}
                )

        with pytest.raises(native_resume.NativeCancellation):
            hermes_transport._receive(left, time.monotonic() + 2, received, current)
    finally:
        left.close()
        right.close()
    assert len(received) == 1 and not received[0]["complete"]
    import base64

    assert base64.b64decode(received[0]["raw_base64"]) == b'{"synthetic":'


def test_idle_shared_owner_rechecks_revoked_authority(tmp_path):
    script = tmp_path / "wire.py"
    script.write_text("import time;time.sleep(5)")
    c = native_resume.MuseConnection(
        sys.executable,
        tmp_path,
        timeout=2,
        max_bytes=1024,
        command=[sys.executable, "-B", str(script)],
        environment={},
        require_jsonrpc=False,
    )

    def revoked():
        raise ValueError("fresh authority revoked")

    c.owner_check = revoked
    try:
        with pytest.raises(ValueError, match="fresh authority revoked"):
            c._read()
    finally:
        c.owner_check = None
        value = c.close()
    assert value["group_absent"] and value["leader_reaped"]


def test_busy_passive_frame_checks_current_authority_on_bounded_cadence(monkeypatch):
    wire = json.dumps({"synthetic": "X" * 800000}).encode()
    blocks = [wire[n : n + 16384] for n in range(0, len(wire), 16384)] + [b""]

    class Peer:
        def settimeout(self, value):
            assert 0 < value <= 0.2

        def recv(self, size):
            return blocks.pop(0)

    calls = []
    monkeypatch.setattr(hermes_transport.time, "monotonic", lambda: 10.0)
    retained = []
    result = hermes_transport._receive(Peer(), 12.0, retained, lambda: calls.append(1))
    assert result == {"synthetic": "X" * 800000}
    assert len(calls) == 2  # initial and final; no full journal replay for each 16KiB
    assert retained[0]["complete"]

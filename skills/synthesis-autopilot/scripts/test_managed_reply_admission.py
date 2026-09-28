"""Independent actual connection-call controls; synthetic endpoint, no provider."""

from pathlib import Path
import json
import pytest
import native_resume
import managed_native as native
import managed_permissions as policy
from test_managed_permissions import (
    managed,
    synthetic_connection,
    reply,
    config_read,
    successful_observation,
)
from test_native_callback import encode, hook
from test_managed_productive import work_stream

__all__ = ["managed", "synthetic_connection"]
REAL_CALL = native_resume.MuseConnection.call


@pytest.mark.parametrize("fault", [None, "config", "idle", "turn", "turn-notification"])
def test_reply_cannot_precede_its_exact_request(
    managed, synthetic_connection, monkeypatch, fault
):
    cfg, _, _, spec = managed
    cfg["required_capabilities"] = ["read"]
    base = native.native_resume.MuseConnection
    emitted = []

    class Connection(base):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            self.frames = []
            self.pending = []
            self.preplayed = set()

        def call(self, method, params):
            self.calls.append(method)
            return REAL_CALL(self, method, params)

        def stage(self, ident, result, extra=()):
            self.pending += [{"id": ident, "result": result}, *extra]

        def send(self, row):
            super().send(row)
            method = row["method"]
            if method == "initialized":
                return
            ident = row["id"]
            if method == "turn/start":
                emitted.append(True)
            if ident in self.preplayed:
                return
            if method == "initialize":
                self.stage(ident, {})
                if fault == "config":
                    self.stage(2, config_read(cfg))
                    self.preplayed.add(2)
            elif method == "config/read":
                self.stage(ident, config_read(cfg))
                if ident == 6 and fault == "idle":
                    self.stage(
                        7,
                        {
                            "thread": {
                                **reply(cfg)["thread"],
                                "status": {"type": "idle"},
                            }
                        },
                    )
                    self.preplayed.add(7)
            elif method == "thread/start":
                self.stage(
                    ident,
                    reply(cfg),
                    [
                        hook("running"),
                        hook(
                            context="SYNTHESIS_NATIVE_RECEIPT "
                            + json.dumps({"event_id": "synthetic", "sha256": "a" * 64})
                        ),
                    ],
                )
            elif method == "command/exec":
                target = next(
                    x
                    for x in spec["filesystem"]["controls"]
                    if x["operation"] == "allowed-create"
                )
                Path(target["path"]).write_bytes(b"SYNTHESIS-STUDY-ALLOWED-WRITE\n")
                self.stage(
                    ident,
                    {
                        "exitCode": 0,
                        "stdout": json.dumps(successful_observation(spec)),
                        "stderr": "",
                    },
                )
            elif method == "thread/read":
                if fault == "turn-notification":
                    self.pending += work_stream()
                self.stage(
                    ident,
                    {"thread": {**reply(cfg)["thread"], "status": {"type": "idle"}}},
                )
                if fault == "turn":
                    self.stage(8, {"turn": {"id": "current-turn"}}, work_stream())
                    self.preplayed.add(8)
            elif method == "turn/start":
                self.stage(ident, {"turn": {"id": "current-turn"}}, work_stream())
            else:
                raise AssertionError(method)

        def _read(self, seconds=0.2):
            if not self.pending:
                raise TimeoutError("Synthetic endpoint exhausted")
            rows, self.pending = self.pending, []
            self.raw_stdout.extend(encode(rows))
            self.frames.extend(x for x in rows if "id" in x)

    monkeypatch.setattr(native.native_resume, "MuseConnection", Connection)
    args = policy.server_argv(cfg["executable_identity"]["path"], cfg["file_contract"])
    code, raw, err, failure, cleanup, sent = native.execute(
        args,
        cfg,
        Path(cfg["file_contract"]["scratch_root"]),
        5,
        {},
        revalidate=lambda: None,
    )
    assert cleanup["cleanup_verified"] and synthetic_connection[0].closed
    if fault:
        assert not emitted, (
            "A preplayed current-policy/idle/turn reply crossed productive admission"
        )
        assert code == 2 and failure
    else:
        assert emitted and code == 0, failure
        assert native.parse(raw, cfg, sent)["protection"]["status"] == "ENFORCED"

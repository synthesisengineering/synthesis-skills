# SPDX-License-Identifier: Apache-2.0
"""Captured-byte and policy timing controls; synthetic endpoints only."""

import json
import os
from pathlib import Path

import pytest

import local_messaging as lm
import messages_boundary as mb
import messages_native as native
import messages_outbound as outbound
import test_messages_native as fixtures
from test_messages_native import FixtureProcess, owners

endpoint = fixtures.endpoint


@pytest.mark.parametrize("module", ["local_messaging.py", "messages_outbound.py"])
@pytest.mark.parametrize("phase", ["preflight", "readback", "recovery"])
def test_every_attempt_reader_capture_is_qualified(
    endpoint, tmp_path, monkeypatch, module, phase
):
    owner, process, authority = owners(endpoint, tmp_path, monkeypatch)
    home = tmp_path / "state"
    if phase == "recovery":
        assert (
            mb.send_with_owner(endpoint.request, home, owner)["status"]
            == "EFFECT_UNKNOWN"
        )
        owner = native.NativeMessagesOwner(authority, process_owner=FixtureProcess())
    index = {"preflight": 1, "readback": 2, "recovery": 3}[phase]
    worker = home / f"outbound-{index:03}"
    original = outbound.source_bytes
    captures = []

    def substituted_capture(path, *args, **kwargs):
        raw = original(path, *args, **kwargs)
        if Path(path).name == module and worker.exists():
            captures.append(str(path))
            return (
                raw
                + b'\nPath("UNQUALIFIED_CAPTURE_EXECUTED").write_text("synthetic")\n'
            )
        return raw

    monkeypatch.setattr(outbound, "source_bytes", substituted_capture)
    with pytest.raises(lm.Refused, match="captured reader"):
        (mb.recover_with_owner if phase == "recovery" else mb.send_with_owner)(
            endpoint.request, home, owner
        )
    assert captures
    assert not (worker / "UNQUALIFIED_CAPTURE_EXECUTED").exists()
    assert len(process.calls) == (0 if phase == "preflight" else 1)
    if phase != "preflight":
        assert lm.file_json(home / "send.json")["status"] == "EFFECT_UNKNOWN"
        with pytest.raises(lm.Refused, match="unresolved"):
            mb.send_with_owner(endpoint.request, home, owner)


@pytest.mark.parametrize("policy", ["config", "registry"])
@pytest.mark.parametrize("seam", ["qualification", "authorization", "fence", "capture"])
def test_policy_and_registry_changes_stop_dispatch(
    endpoint, tmp_path, monkeypatch, policy, seam
):
    owner, process, authority = owners(endpoint, tmp_path, monkeypatch)
    config = Path(os.environ["MESSAGE_GUARD_CONFIG"])
    if policy == "registry":
        registry = tmp_path / "registry.json"
        registry.write_text(
            json.dumps(json.loads(config.read_text())["_capability_registry"])
        )
        monkeypatch.setenv("MESSAGE_GUARD_CAPABILITIES", str(registry))
        path = registry
    else:
        path = config
    changed = []

    def change():
        value = json.loads(path.read_text())
        # A valid, effective owner-data change also invalidates qualification;
        # refusal must not depend only on malformed JSON.
        value["timing_fixture_marker"] = "changed after guard"
        path.write_text(json.dumps(value))
        changed.append(True)

    if seam == "qualification":
        original = authority.qualify

        def qualify(context):
            change()
            return original(context)

        authority.qualify = qualify
    elif seam == "authorization":
        original = authority.authorize_send
        calls = []

        def authorize(payload, sha):
            calls.append(True)
            if len(calls) == 2:
                change()
            return original(payload, sha)

        authority.authorize_send = authorize
    elif seam == "fence":
        original = lm.atomic_state

        def persist(home, name, value):
            result = original(home, name, value)
            if name == "send.json":
                change()
            return result

        monkeypatch.setattr(lm, "atomic_state", persist)
    else:
        original = outbound.source_bytes

        def capture(path, *args, **kwargs):
            raw = original(path, *args, **kwargs)
            if (
                Path(path).name == "messages_transport.js"
                and (tmp_path / "state/dispatch.json").exists()
            ):
                change()
            return raw

        monkeypatch.setattr(outbound, "source_bytes", capture)
    with pytest.raises(lm.Refused, match="guard policy"):
        mb.send_with_owner(endpoint.request, tmp_path / "state", owner)
    assert changed and process.calls == [] and process.commands == []


def test_final_policy_check_consumes_guard_once(endpoint, tmp_path, monkeypatch):
    owner, process, authority = owners(endpoint, tmp_path, monkeypatch)
    guard = lm.existing_owner("synthesis-message-guard", "message_guard")
    original = guard.run_gate
    calls = []

    def gate(*args, **kwargs):
        calls.append(True)
        return original(*args, **kwargs)

    monkeypatch.setattr(guard, "run_gate", gate)
    assert (
        mb.send_with_owner(endpoint.request, tmp_path / "state", owner)["status"]
        == "EFFECT_UNKNOWN"
    )
    assert len(calls) == len(process.calls) == 1
    assert len(Path(guard.log_path()).read_text().splitlines()) == 1
    assert list(Path(guard.ledger_dir()).iterdir()) == []


def test_native_dispatch_requires_live_coordinator_binding(
    endpoint, tmp_path, monkeypatch
):
    owner, process, authority = owners(endpoint, tmp_path, monkeypatch)
    payload = mb.prepare(endpoint.request)
    with pytest.raises(lm.Refused, match="live coordinator"):
        owner.send(lm.canonical(payload))
    assert process.commands == []


def test_changed_fence_cannot_replace_in_memory_guard_decision(
    endpoint, tmp_path, monkeypatch
):
    owner, process, authority = owners(endpoint, tmp_path, monkeypatch)
    home = tmp_path / "state"
    original = outbound.source_bytes
    changed = []

    def capture(path, *args, **kwargs):
        raw = original(path, *args, **kwargs)
        fence = home / "send.json"
        if fence.exists() and not (home / "dispatch.json").exists() and not changed:
            conf = Path(os.environ["MESSAGE_GUARD_CONFIG"])
            config = json.loads(conf.read_text())
            config["timing_fixture_marker"] = "new policy and forged binding"
            conf.write_text(json.dumps(config))
            data = json.loads(fence.read_text())
            guard = lm.existing_owner("synthesis-message-guard", "message_guard")
            data["guard"]["policy"] = mb._guard_policy(
                mb.prepare(endpoint.request), guard
            )
            fence.write_bytes(lm.canonical(data))
            changed.append(True)
        return raw

    monkeypatch.setattr(outbound, "source_bytes", capture)
    with pytest.raises(lm.Refused, match="guard policy"):
        mb.send_with_owner(endpoint.request, home, owner)
    assert changed and process.commands == [] and process.calls == []

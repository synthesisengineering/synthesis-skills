# SPDX-License-Identifier: Apache-2.0
"""Synthetic coordinator controls; exact row matches are not causal send proof."""

import pytest
import local_messaging as lm
import messages_boundary as mb
from test_messages_boundary import SyntheticOwner, request, setup_guard


def test_unqualified_matching_row_cannot_become_sent(tmp_path, monkeypatch):
    r = request()
    setup_guard(tmp_path, monkeypatch, r)
    owner = SyntheticOwner()
    owner.verify_readback = None
    with pytest.raises(lm.Refused, match="qualified|causal"):
        mb.send_with_owner(r, tmp_path / "owned", owner)
    assert len(owner.calls) == 1
    with pytest.raises(lm.Refused, match="unresolved"):
        mb.send_with_owner(r, tmp_path / "owned", owner)
    assert len(owner.calls) == 1


def test_explicit_native_route_is_bound_in_guard_payload(tmp_path):
    r = request()
    r.update(
        schema=2,
        route={
            "account_id": "synthetic-account",
            "service": "iMessage",
            "chat_id": "synthetic-chat",
            "participant_id": "synthetic-participant",
            "database_account_id": "synthetic-db-account",
            "database": str(tmp_path / "synthetic.sqlite"),
        },
    )
    payload = mb.prepare(r)
    assert payload["tool_input"]["route"] == r["route"]
    assert payload["tool_input"]["destination"] == r["destination"]


def test_recovery_entry_is_read_only_and_requires_existing_fence(tmp_path):
    recover = getattr(mb, "recover_with_owner", None)
    assert callable(recover), "retained effect needs a concrete recovery consumer"
    owner = SyntheticOwner()
    with pytest.raises(lm.Refused):
        recover(request(), tmp_path / "missing-state", owner)
    assert owner.calls == []


def test_terminal_replay_rechecks_causal_owner(tmp_path, monkeypatch):
    r = request()
    setup_guard(tmp_path, monkeypatch, r)
    owner = SyntheticOwner()
    home = tmp_path / "state"
    assert mb.send_with_owner(r, home, owner)["status"] == "SENT_READBACK"
    owner.verify_readback = None
    with pytest.raises(lm.Refused, match="qualified|causal"):
        mb.send_with_owner(r, home, owner)
    assert len(owner.calls) == 1


@pytest.mark.parametrize(
    "partial", ["prepared", "result-list", "row-result-list", "gap"]
)
def test_partial_readback_state_does_not_replay(tmp_path, monkeypatch, partial):
    import json

    r = request()
    setup_guard(tmp_path, monkeypatch, r)
    owner = SyntheticOwner()
    home = tmp_path / "state"
    mb.send_with_owner(r, home, owner)
    if partial == "prepared":
        (home / ".prepared-interrupted").write_text("{}")
    elif partial == "result-list":
        (home / "result.json").write_text("[]")
    elif partial == "row-result-list":
        row = lm.file_json(home / "observation-001.json")
        row["result"] = []
        (home / "observation-001.json").write_text(json.dumps(row))
    else:
        (home / "observation-001.json").rename(home / "observation-002.json")
    with pytest.raises(lm.Refused):
        mb.send_with_owner(r, home, owner)
    assert len(owner.calls) == 1


def test_caller_mutation_does_not_change_captured_dispatch_identity(
    tmp_path, monkeypatch
):
    r = request()
    setup_guard(tmp_path, monkeypatch, r)
    owner = SyntheticOwner()
    captured_id = r["request_id"]

    def authorize(raw, sha):
        r["request_id"] = "caller-changed-during-approval"
        return sha

    owner.authorize = authorize
    home = tmp_path / "state"
    result = mb.send_with_owner(r, home, owner)
    fence = lm.file_json(home / "send.json")
    assert result["request_id"] == captured_id
    assert fence["request_id"] == captured_id
    assert fence["payload"]["tool_input"]["request_id"] == captured_id
    assert len(owner.calls) == 1

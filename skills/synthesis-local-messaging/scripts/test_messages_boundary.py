# SPDX-License-Identifier: Apache-2.0
"""Programmed transport and actual guard owner; these are not native send proofs."""

import json
from datetime import datetime, timezone
from pathlib import Path
import pytest
import local_messaging as lm
import messages_boundary as mb


def setup_guard(tmp_path, monkeypatch, request, *, ledger=True):
    guard = lm.existing_owner("synthesis-message-guard", "message_guard")
    cfg = json.loads(
        (Path(guard.__file__).parent.parent / "patterns.example.json").read_text()
    )
    inventory = {
        "client": "codex",
        "complete": True,
        "total_tools": 1,
        "next_cursor": None,
        "source": "synthetic catalog, no actual authorization",
        "tools": [
            {
                "name": mb.TOOL,
                "input_schema": {"destination": "string", "text": "string"},
            }
        ],
    }
    plan = guard.capability_plan(inventory, cfg)
    row = plan["proposals"][0]
    reg = guard.capability_enroll(
        {
            "inventory": inventory,
            "owner_review": {
                "inventory_digest": plan["inventory_digest"],
                "source": "synthetic owner",
            },
            "decisions": [
                {
                    "name": mb.TOOL,
                    "descriptor_sha256": row["descriptor_sha256"],
                    "capability": {"channel": "human-text"},
                }
            ],
        },
        cfg,
    )
    cfg["message_capabilities"] = reg["capabilities"]
    cfg["_capability_registry"] = reg
    conf = tmp_path / "guard.json"
    conf.write_text(json.dumps(cfg))
    home = tmp_path / "guard-state"
    (home / "ledger").mkdir(parents=True)
    monkeypatch.setenv("MESSAGE_GUARD_CONFIG", str(conf))
    monkeypatch.setenv("MESSAGE_GUARD_STATE_DIR", str(home))
    monkeypatch.delenv("MESSAGE_GUARD_CAPABILITIES", raising=False)
    payload = mb.prepare(request)
    sha = guard.message_digest(mb.TOOL, payload["tool_input"])
    if ledger:
        (home / "ledger" / (sha + ".json")).write_text(
            json.dumps(
                {
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "message_sha256": sha,
                    "is_reply": False,
                    "no_factual_claims": True,
                    "voice_rules_pass": True,
                    "invented_precision_scan": True,
                    "recipient_address_check": True,
                }
            )
        )
    return guard


class SyntheticOwner:
    def __init__(self, authorized=True, mismatch=False, lost=False):
        self.authorized = authorized
        self.mismatch = mismatch
        self.lost = lost
        self.calls = []

    def authorize(self, raw, sha):
        return sha if self.authorized else None

    def send(self, raw):
        self.calls.append(json.loads(raw))
        if self.lost:
            raise RuntimeError("synthetic transport interrupted after effect")

    def readback(self, raw):
        data = json.loads(raw)["tool_input"]
        return {
            "request_id": data["request_id"],
            "destination": data["destination"],
            "text": "wrong" if self.mismatch else data["text"],
            "native_id": "synthetic-1",
            "status": "sent",
        }

    def verify_readback(self, raw, proof):
        # Independently supplied fixture link; this is not native qualification.
        return proof["native_id"] == "synthetic-1" and len(self.calls) == 1


def request():
    return {
        "schema": 1,
        "request_id": "synthetic-send-1",
        "destination": "+15551234567",
        "text": "Please review the draft.",
    }


def test_exact_guard_and_authorization_before_synthetic_send(tmp_path, monkeypatch):
    r = request()
    setup_guard(tmp_path, monkeypatch, r)
    owner = SyntheticOwner()
    result = mb.send_with_owner(r, tmp_path / "owned", owner)
    assert (
        result["status"] == "SENT_READBACK" and result["acknowledgement"] == "UNKNOWN"
    )
    assert len(owner.calls) == 1
    assert mb.send_with_owner(r, tmp_path / "owned", owner) == result
    assert len(owner.calls) == 1


@pytest.mark.parametrize(
    "mode",
    [
        "unauthorized",
        "missing-ledger",
        "forbidden",
        "destination-change",
        "lost",
        "mismatch",
    ],
)
def test_guarded_refusals_and_no_effect_replay(tmp_path, monkeypatch, mode):
    r = request()
    if mode == "forbidden":
        r["text"] = "Sorry for the delay."
    setup_guard(tmp_path, monkeypatch, r, ledger=mode != "missing-ledger")
    if mode == "destination-change":
        r["destination"] = "+15559876543"
    owner = SyntheticOwner(
        authorized=mode != "unauthorized",
        lost=mode == "lost",
        mismatch=mode == "mismatch",
    )
    with pytest.raises((lm.Refused, RuntimeError)):
        mb.send_with_owner(r, tmp_path / "owned", owner)
    assert len(owner.calls) == (1 if mode in ("lost", "mismatch") else 0)
    if mode in ("lost", "mismatch"):
        with pytest.raises(lm.Refused, match="unresolved"):
            mb.send_with_owner(r, tmp_path / "owned", owner)
        assert len(owner.calls) == 1


def test_no_owner_or_whatsapp_transport(tmp_path):
    with pytest.raises(lm.Refused):
        mb.send_with_owner(request(), tmp_path / "owned", None)
    r = request()
    r["app"] = "whatsapp"
    with pytest.raises(lm.Refused):
        mb.prepare(r)

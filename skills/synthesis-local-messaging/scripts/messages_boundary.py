# SPDX-License-Identifier: Apache-2.0
"""Exact guarded send fence and append-only readback through the existing state owner."""

from __future__ import annotations
import json
import os
from pathlib import Path
import re
import local_messaging as lm

TOOL = "synthesis.messages.send"


def prepare(request):
    schema = request.get("schema") if isinstance(request, dict) else None
    fields = {"schema", "request_id", "destination", "text"}
    if schema == 2:
        fields.add("route")
    if (
        not isinstance(request, dict)
        or set(request) != fields
        or type(request["schema"]) is not int
        or schema not in (1, 2)
    ):
        raise lm.Refused("exact Messages request required")
    if not isinstance(request["request_id"], str) or not re.fullmatch(
        r"[A-Za-z0-9_-]{1,80}", request["request_id"]
    ):
        raise lm.Refused("bounded request identity required")
    for key, limit in [("destination", 320), ("text", 65536)]:
        if (
            not isinstance(request[key], str)
            or not request[key].strip()
            or len(request[key].encode()) > limit
            or "\x00" in request[key]
        ):
            raise lm.Refused("invalid destination/text")
    if schema == 2:
        route = request["route"]
        keys = {
            "account_id",
            "service",
            "chat_id",
            "participant_id",
            "database_account_id",
            "database",
        }
        if not isinstance(route, dict) or set(route) != keys:
            raise lm.Refused(
                "exact explicit account/participant/database route required"
            )
        if any(
            not isinstance(v, str)
            or not v
            or v != v.strip()
            or len(v.encode()) > 4096
            or "\0" in v
            for v in route.values()
        ):
            raise lm.Refused("invalid bounded native route")
        if route["service"] != "iMessage":
            raise lm.Refused("only explicit iMessage is supported; no fallback")
        if not re.fullmatch(
            r"\+[1-9][0-9]{6,14}|[^\s@]+@[^\s@]+\.[^\s@]+", request["destination"]
        ):
            raise lm.Refused(
                "exact phone/email recipient required; aliases are unsupported"
            )
        path = Path(route["database"])
        if not path.is_absolute() or ".." in path.parts:
            raise lm.Refused("explicit physical database path required")
    return {
        "tool_name": TOOL,
        "tool_input": json.loads(
            lm.canonical(
                {
                    k: request[k]
                    for k in (
                        "request_id",
                        "destination",
                        "text",
                        *(("route",) if schema == 2 else ()),
                    )
                }
            )
        ),
    }


def _guard_policy(payload, guard):
    """Use the existing owner's effective policy, including its registry overlay."""
    try:
        cfg = guard.load_config()[0]
        registry = guard.validate_capability_registry(cfg.get("_capability_registry"))
        if cfg.get("message_capabilities") != registry["capabilities"]:
            raise lm.Refused("guard dispatch declarations differ from registry")
        if guard.capability_for(TOOL, cfg)["channel"] != "human-text":
            raise lm.Refused("Messages must be enrolled as human-text")
        if guard.peer_send_resolution_failures(TOOL, payload["tool_input"], cfg)[0]:
            raise lm.Refused("Messages cannot use the peer-session lane")
        return {
            "configuration": json.loads(lm.canonical(cfg)),
            "config_path": str(guard.config_path()),
            "capability_path": os.environ.get("MESSAGE_GUARD_CAPABILITIES"),
            "state_dir": str(guard.state_dir()),
            "log_path": str(guard.log_path()),
        }
    except (OSError, ValueError, TypeError, KeyError, RuntimeError, re.error) as exc:
        raise lm.Refused("guard policy unavailable: " + str(exc)) from exc


def _revalidate_guard(payload, decision):
    """Read-only binding check, never another ledger consumption or approval."""
    guard = lm.existing_owner("synthesis-message-guard", "message_guard")
    if (
        not isinstance(decision, dict)
        or set(decision) != {"digest", "policy", "receipt"}
        or decision["digest"] != guard.message_digest(TOOL, payload["tool_input"])
        or not isinstance(decision["receipt"], dict)
        or decision["receipt"].get("sha256") != decision["digest"]
        or decision["receipt"].get("tool") != TOOL
        or decision["receipt"].get("channel") != "human-text"
    ):
        raise lm.Refused("exact original guard decision required")
    if _guard_policy(payload, guard) != decision["policy"]:
        raise lm.Refused("guard policy or registry changed before dispatch")


def _guard(payload):
    guard = lm.existing_owner("synthesis-message-guard", "message_guard")
    policy = _guard_policy(payload, guard)
    log = Path(guard.log_path())
    prior = None
    offset = 0
    if log.exists():
        lm.physical(log)
        s = log.stat()
        prior = (s.st_dev, s.st_ino)
        offset = s.st_size
    try:
        guard.run_gate(payload, dispatch=True)
    except SystemExit as result:
        if result.code != 0:
            raise lm.Refused("message guard refused") from result
    else:
        raise lm.Refused("guard did not return a terminal decision")
    if policy != _guard_policy(payload, guard):
        raise lm.Refused("guard configuration changed")
    lm.physical(log)
    fd = os.open(log, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        s = os.fstat(fd)
        if prior is not None and prior != (s.st_dev, s.st_ino):
            raise lm.Refused("guard log replaced")
        if not 0 < s.st_size - offset <= 1024 * 1024:
            raise lm.Refused("guard receipt bound")
        os.lseek(fd, offset, os.SEEK_SET)
        raw = os.read(fd, 1024 * 1024 + 1)
        if lm.stable_stat(os.fstat(fd)) != lm.stable_stat(s):
            raise lm.Refused("guard receipt changed")
    finally:
        os.close(fd)
    rows = raw.splitlines()
    if len(rows) != 1:
        raise lm.Refused("ambiguous guard receipt")
    record = json.loads(rows[0], object_pairs_hook=lm.unique)
    sha = guard.message_digest(TOOL, payload["tool_input"])
    if (
        record.get("sha256") != sha
        or record.get("tool") != TOOL
        or record.get("channel") != "human-text"
    ):
        raise lm.Refused("no exact human-text guard receipt")
    return {"digest": sha, "policy": policy, "receipt": record}


def _identity(payload):
    guard = lm.existing_owner("synthesis-message-guard", "message_guard")
    return guard.message_digest(TOOL, payload["tool_input"])


def _fence(home, payload, sha):
    if not (home / "send.json").exists():
        raise lm.Refused("existing exact dispatch fence required")
    old = lm.file_json(home / "send.json")
    if (
        not isinstance(old, dict)
        or old.get("schema") != 2
        or old.get("payload") != payload
        or old.get("digest") != sha
        or old.get("status") != "EFFECT_UNKNOWN"
    ):
        raise lm.Refused("malformed or foreign unresolved dispatch fence")
    return old


def _history(home, sha):
    if any(p.name.startswith(".prepared-") for p in Path(home).iterdir()):
        raise lm.Refused("partial durable receipt requires owner reconciliation")
    names = sorted(p.name for p in Path(home).glob("observation-*.json"))
    if len(names) > 32 or names != [
        f"observation-{i:03}.json" for i in range(1, len(names) + 1)
    ]:
        raise lm.Refused("partial or out-of-order readback receipts")
    previous = None
    rows = []
    for i, name in enumerate(names, 1):
        row = lm.file_json(home / name)
        if (
            not isinstance(row, dict)
            or set(row)
            != {"schema", "digest", "sequence", "previous", "proof", "result"}
            or row["schema"] != 1
            or row["digest"] != sha
            or row["sequence"] != i
            or row["previous"] != previous
            or not isinstance(row["proof"], dict)
            or not isinstance(row["result"], dict)
            or row["result"].get("digest") != sha
            or row["result"].get("status")
            not in ("EFFECT_UNKNOWN", "OBSERVED_MATCH_UNATTRIBUTED", "SENT_READBACK")
            or row["result"].get("acknowledgement") != "UNKNOWN"
        ):
            raise lm.Refused("changed or partial readback receipt")
        previous = lm.digest(row)
        rows.append(row)
    if (home / "result.json").exists():
        result = lm.file_json(home / "result.json")
        if (
            not isinstance(result, dict)
            or not rows
            or result != rows[-1]["result"]
            or result.get("status") != "SENT_READBACK"
        ):
            raise lm.Refused("terminal result lacks exact retained readback")
    return rows, previous


def _causal(payload, proof, owner):
    body = payload["tool_input"]
    verify = getattr(owner, "verify_readback", None)
    if (
        proof.get("status") != "sent"
        or any(proof.get(k) != body[k] for k in ("request_id", "destination", "text"))
        or ("route" in body and proof.get("route") != body["route"])
        or not isinstance(proof.get("native_id"), str)
        or not proof["native_id"]
    ):
        raise lm.Refused("exact post-send readback unavailable; effect unresolved")
    if not callable(verify) or verify(lm.canonical(payload), proof) is not True:
        raise lm.Refused(
            "independently qualified causal invocation-to-row proof required"
        )


def _terminal(home, payload, sha, owner):
    rows, _ = _history(home, sha)
    if not (home / "result.json").exists():
        return None
    proof = rows[-1]["proof"]
    _causal(payload, proof, owner)
    result = lm.file_json(home / "result.json")
    if result != {
        "digest": sha,
        "request_id": payload["tool_input"]["request_id"],
        "status": "SENT_READBACK",
        "acknowledgement": "UNKNOWN",
        "native_id": proof["native_id"],
    }:
        raise lm.Refused("terminal result differs from qualified proof")
    return result


def _observe(home, payload, sha, owner):
    rows, previous = _history(home, sha)
    if len(rows) == 32:
        raise lm.Refused("readback observation bound reached")
    proof = owner.readback(lm.canonical(payload))
    body = payload["tool_input"]
    if not isinstance(proof, dict) or len(lm.canonical(proof)) > 256 * 1024:
        raise lm.Refused("bounded exact readback unavailable; effect unresolved")
    result = {
        "digest": sha,
        "request_id": body["request_id"],
        "status": "EFFECT_UNKNOWN",
        "acknowledgement": "UNKNOWN",
    }
    if proof.get("status") == "sent":
        _causal(payload, proof, owner)
        result.update(status="SENT_READBACK", native_id=proof["native_id"])
    elif proof.get("status") in ("observed_match_unattributed", "effect_unknown"):
        if proof.get("request_digest") != sha:
            raise lm.Refused("readback request binding changed")
        if proof["status"] == "observed_match_unattributed":
            if not isinstance(proof.get("native_id"), str) or not proof["native_id"]:
                raise lm.Refused("matching observation lacks native identity")
            result.update(
                status="OBSERVED_MATCH_UNATTRIBUTED", native_id=proof["native_id"]
            )
        result["reason"] = proof.get(
            "reason", "No independently qualified invocation-to-row link"
        )
    else:
        raise lm.Refused("unknown readback disposition; effect unresolved")
    observation = {
        "schema": 1,
        "digest": sha,
        "sequence": len(rows) + 1,
        "previous": previous,
        "proof": proof,
        "result": result,
    }
    lm.atomic_state(home, f"observation-{len(rows) + 1:03}.json", observation)
    if result["status"] == "SENT_READBACK":
        lm.atomic_state(home, "result.json", result)
    return result


def send_with_owner(request, home, owner):
    """One guarded attempt. The original fence is never replaced or replayed."""
    payload = prepare(request)
    raw = lm.canonical(payload)
    if owner is None or any(
        not callable(getattr(owner, k, None)) for k in ("authorize", "send", "readback")
    ):
        raise lm.Refused("qualified authorization/transport/readback owner unavailable")
    sha = _identity(payload)
    with lm.state_lock(home) as home:
        record = home / "send.json"
        if record.exists():
            _fence(home, payload, sha)
            terminal = _terminal(home, payload, sha, owner)
            if terminal is not None:
                return terminal
            raise lm.Refused(
                "original effect unresolved; reconcile exact native request without replay"
            )
        with os.scandir(home) as entries:
            if any(e.name != ".lock" for e in entries):
                raise lm.Refused("unowned send state")
        if owner.authorize(raw, sha) != sha:
            raise lm.Refused("explicit exact-text/destination authorization absent")
        decision = _guard(payload)
        if decision["digest"] != sha:
            raise lm.Refused("guard digest differs")
        capture = getattr(owner, "prepare_attempt", None)
        attempt = capture(raw, home) if callable(capture) else None
        if owner.authorize(raw, sha) != sha:
            raise lm.Refused("authorization no longer current")
        _revalidate_guard(payload, decision)
        # Durable fence before invoking transport; exceptions retain UNKNOWN, never retry.
        lm.atomic_state(
            home,
            "send.json",
            {
                "schema": 2,
                "digest": sha,
                "status": "EFFECT_UNKNOWN",
                "request_id": payload["tool_input"]["request_id"],
                "payload": payload,
                "attempt": attempt,
                "guard": decision,
            },
        )
        _revalidate_guard(payload, decision)
        guarded_send = getattr(owner, "send_guarded", None)
        receipt = (
            guarded_send(raw, lambda: _revalidate_guard(payload, decision))
            if callable(guarded_send)
            else owner.send(raw)
        )
        if receipt is not None:
            if not isinstance(receipt, dict) or len(lm.canonical(receipt)) > 65536:
                raise lm.Refused("partial transport receipt; effect unresolved")
            lm.atomic_state(home, "transport.json", {"digest": sha, "receipt": receipt})
        return _observe(home, payload, sha, owner)


def recover_with_owner(request, home, owner):
    """Append fresh evidence about the existing attempt; never call send."""
    payload = prepare(request)
    sha = _identity(payload)
    if not Path(home).is_dir():
        raise lm.Refused("existing dispatch state required")
    with lm.state_lock(home) as home:
        fence = _fence(home, payload, sha)
        _history(home, sha)
        authorize = getattr(owner, "authorize_recovery", None)
        restore = getattr(owner, "restore_attempt", None)
        if (
            not callable(authorize)
            or authorize(lm.canonical(payload), sha) != sha
            or not callable(restore)
        ):
            raise lm.Refused("trusted readback recovery owner required")
        restore(lm.canonical(payload), fence["attempt"], home)
        terminal = _terminal(home, payload, sha, owner)
        if terminal is not None:
            return terminal
        return _observe(home, payload, sha, owner)

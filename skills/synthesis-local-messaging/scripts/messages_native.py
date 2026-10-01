# SPDX-License-Identifier: Apache-2.0
"""Trusted-owner integration for the fixed Messages transport; no authority issuer."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
import time

import local_messaging as lm
import messages_boundary as boundary
import messages_outbound as outbound

SOURCE_NAMES = (
    "local_messaging.py",
    "messages_boundary.py",
    "messages_outbound.py",
    "messages_native.py",
    "messages_transport.js",
)
DICTIONARY_SHA256 = "a9db9b015709c8c8e92a8bdccf08984635d5c3545f670bcd0e5a3a10bd5f9e4e"


def source_context():
    directory = lm.physical(Path(__file__).parent, True)
    sources = {
        name: hashlib.sha256(outbound.source_bytes(directory / name)).hexdigest()
        for name in SOURCE_NAMES
    }
    for skill, name in (
        ("synthesis-autopilot", "evaluation_artifacts"),
        ("synthesis-project-management", "coordination_process"),
        ("synthesis-message-guard", "message_guard"),
    ):
        module = lm.existing_owner(skill, name)
        sources[skill + "/" + name + ".py"] = hashlib.sha256(
            outbound.source_bytes(Path(module.__file__))
        ).hexdigest()
    return {
        "sources": sources,
        "dictionary_sha256": DICTIONARY_SHA256,
        "schema": outbound.SCHEMA,
    }


def _payload(raw):
    if not isinstance(raw, bytes) or len(raw) > 128 * 1024:
        raise lm.Refused("bounded captured payload required")
    value = json.loads(raw, object_pairs_hook=lm.unique)
    if (
        not isinstance(value, dict)
        or set(value) != {"tool_name", "tool_input"}
        or not isinstance(value["tool_input"], dict)
    ):
        raise lm.Refused("exact native payload required")
    if (
        value != boundary.prepare({"schema": 2, **value["tool_input"]})
        or lm.canonical(value) != raw
    ):
        raise lm.Refused("native payload differs")
    return value


class NativeMessagesOwner:
    """The caller supplies an authenticated owner, never an approval flag from data.

    authorize_send(payload, digest) returns an exact digest and finite expiry.
    qualify(context) binds observed app/schema/account mapping to its digest.
    authorize_readback(payload, digest) separately grants recovery reads.
    This module neither enrolls capabilities nor creates approvals.
    """

    def __init__(self, authority, *, process_owner=None):
        self.authority = authority
        self.process = process_owner or lm.existing_owner(
            "synthesis-project-management", "coordination_process"
        )
        self.raw = self.attempt = self.grant = self.home = None

    def authorize(self, raw, sha):
        payload = _payload(raw)
        if boundary._identity(payload) != sha:
            raise lm.Refused("authorization digest differs")
        grant = self.authority.authorize_send(json.loads(raw), sha)
        if (
            not isinstance(grant, dict)
            or set(grant) != {"digest", "expires_ms"}
            or grant["digest"] != sha
            or type(grant["expires_ms"]) is not int
            or not 0 < grant["expires_ms"] - int(time.time() * 1000) <= 300000
        ):
            raise lm.Refused("fresh trusted exact-text/route approval required")
        self.grant = json.loads(lm.canonical(grant))
        return sha

    def _query(self, payload, baseline, implementation):
        self.home.verify()
        existing = list(Path(self.home).glob("outbound-*"))
        if len(existing) >= 66:
            raise lm.Refused("outbound worker bound")
        body = payload["tool_input"]
        query = {
            "schema": outbound.SCHEMA,
            "route": body["route"],
            "destination": body["destination"],
            "text_sha256": hashlib.sha256(body["text"].encode()).hexdigest(),
            "request_digest": boundary._identity(payload),
            "baseline": baseline,
        }
        result = outbound.run_query(
            query,
            self.home / f"outbound-{len(existing) + 1:03}",
            expected_sources=implementation["sources"],
        )
        self.home.verify()
        return result

    def _qualify(self, payload, baseline, sources):
        context = {
            "payload_digest": boundary._identity(payload),
            "route": payload["tool_input"]["route"],
            "database": baseline,
            "implementation": sources,
            "required": "observed scripting account to database account mapping; exact installed dictionary, schema and permissions",
        }
        if self.authority.qualify(json.loads(lm.canonical(context))) != lm.digest(
            context
        ):
            raise lm.Refused("account/schema/native endpoint qualification absent")

    def prepare_attempt(self, raw, home):
        payload = _payload(raw)
        self.home = home
        sources = source_context()
        before = self._query(payload, None, sources)
        self._qualify(payload, before["baseline"], sources)
        self.raw = bytes(raw)
        self.attempt = {
            "schema": 1,
            "payload_digest": boundary._identity(payload),
            "baseline": before["baseline"],
            "implementation": sources,
        }
        return json.loads(lm.canonical(self.attempt))

    def send_guarded(self, raw, check_guard):
        return self.send(raw, check_guard=check_guard)

    def send(self, raw, *, check_guard=None):
        if not callable(check_guard):
            raise lm.Refused("live coordinator guard binding required")
        payload = _payload(raw)
        if (
            self.raw != raw
            or not self.attempt
            or source_context() != self.attempt["implementation"]
            or outbound.source_identity(payload["tool_input"]["route"]["database"])
            != self.attempt["baseline"]["identity"]
        ):
            raise lm.Refused("prepared source or route changed; effect remains fenced")
        sha = boundary._identity(payload)
        if (
            not self.grant
            or self.grant["digest"] != sha
            or self.grant["expires_ms"] <= int(time.time() * 1000)
        ):
            raise lm.Refused("approval expired at dispatch fence")
        self.home.verify()
        fence = lm.file_json(self.home / "send.json")
        if (
            fence.get("payload") != payload
            or fence.get("attempt") != self.attempt
            or fence.get("status") != "EFFECT_UNKNOWN"
        ):
            raise lm.Refused("durable exact dispatch fence missing")
        if (self.home / "dispatch.json").exists():
            raise lm.Refused("dispatch was already consumed; never replay")
        lm.atomic_state(
            self.home,
            "dispatch.json",
            {"digest": sha, "attempt_digest": lm.digest(self.attempt)},
        )
        script_path = Path(__file__).with_name("messages_transport.js")
        script = outbound.source_bytes(script_path)
        if (
            hashlib.sha256(script).hexdigest()
            != self.attempt["implementation"]["sources"]["messages_transport.js"]
        ):
            raise lm.Refused("captured script differs from qualified implementation")
        packet = {
            "protocol": 1,
            "payload": payload,
            "digest": sha,
            "expires_ms": self.grant["expires_ms"],
        }
        with tempfile.TemporaryFile(mode="w+b", dir=Path(self.home)) as descriptor:
            os.fchmod(descriptor.fileno(), 0o600)
            descriptor.write(lm.canonical(packet))
            descriptor.flush()
            descriptor.seek(0)
            info = os.fstat(descriptor.fileno())
            if (
                info.st_nlink != 0
                or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_size > 128 * 1024
            ):
                raise lm.Refused("private anonymous descriptor required")
            command = [
                "/usr/bin/osascript",
                "-l",
                "JavaScript",
                "-e",
                script.decode(),
                str(descriptor.fileno()),
            ]
            # Revalidate the coordinator's original in-memory decision. A
            # recorded fence/receipt is evidence, never a replacement issuer.
            # This check follows capture and immediately precedes dispatch.
            check_guard()
            result = self.process.run(
                command,
                cwd=Path(self.home),
                timeout=15,
                output_bytes=65536,
                pass_fds=(descriptor.fileno(),),
            )
        lm.atomic_state(
            self.home,
            "native-process.json",
            {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "script_sha256": hashlib.sha256(script).hexdigest(),
            },
        )
        if source_context() != self.attempt["implementation"]:
            raise lm.Refused("source changed during transport; effect unresolved")
        if result.returncode:
            raise lm.Refused(
                "transport failed or interrupted; effect unresolved, never replay"
            )
        receipt = json.loads(result.stdout, object_pairs_hook=lm.unique)
        if receipt != {"protocol": 1, "request_digest": sha, "phase": "dispatched"}:
            raise lm.Refused("partial or foreign transport receipt; effect unresolved")
        return receipt

    def readback(self, raw):
        payload = _payload(raw)
        if (
            self.raw != raw
            or not self.attempt
            or source_context() != self.attempt["implementation"]
        ):
            raise lm.Refused("readback source or attempt changed")
        observed = self._query(
            payload, self.attempt["baseline"], self.attempt["implementation"]
        )
        rows = observed["observations"]
        proof = {
            "request_digest": boundary._identity(payload),
            "status": "effect_unknown",
            "reason": "No unique successful new outbound row",
            "observation": observed,
        }
        if len(rows) == 1 and rows[0]["error"] == 0 and rows[0]["is_sent"] == 1:
            proof.update(
                status="observed_match_unattributed",
                native_id=rows[0]["native_id"],
                reason="Exact new outbound row observed; scripting API supplies no invocation-to-row identifier",
            )
        return proof

    def verify_readback(self, raw, proof):
        # The installed scripting contract has no returned message identifier.
        return False

    def authorize_recovery(self, raw, sha):
        payload = _payload(raw)
        if (
            boundary._identity(payload) != sha
            or self.authority.authorize_readback(json.loads(raw), sha) != sha
        ):
            raise lm.Refused("fresh trusted readback authorization required")
        return sha

    def restore_attempt(self, raw, attempt, home):
        payload = _payload(raw)
        if (
            not isinstance(attempt, dict)
            or set(attempt)
            != {"schema", "payload_digest", "baseline", "implementation"}
            or attempt["schema"] != 1
            or attempt["payload_digest"] != boundary._identity(payload)
            or attempt["implementation"] != source_context()
        ):
            raise lm.Refused("retained native attempt changed or incomplete")
        self._qualify(payload, attempt["baseline"], attempt["implementation"])
        self.raw, self.attempt, self.home = (
            bytes(raw),
            json.loads(lm.canonical(attempt)),
            home,
        )

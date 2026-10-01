"""Content-free portable observations signed by OpenSSH, never action authority.

Trust is an explicitly supplied local anchor, not a key inside the envelope.
No native key enrollment, provider call, client configuration or permissions are
changed here. The existing live_receipt owner supplies replay admission. A
verified signer can attest an UNKNOWN observation; verification cannot promote
it to PASS or replace the local transcript/install validators.
"""

from __future__ import annotations

import base64
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import signal
import stat
import subprocess
import tempfile
import time
import uuid

SCHEMA = "synthesis-signed-observation/1"
NAMESPACE = "synthesis-observation@synthesiswork.org"
MAX_BYTES = 64 * 1024
MAX_TTL_SECONDS = 24 * 3600
CLIENTS = {"claude", "codex", "muse", "cursor", "copilot"}
BINDINGS = {
    "client",
    "source_sha256",
    "installation_sha256",
    "session_id",
    "event_id",
    "audience_sha256",
    "challenge",
}
PAYLOAD_FIELDS = BINDINGS | {
    "schema",
    "event",
    "status",
    "observed_at",
    "issued_at",
    "expires_at",
}


def canonical(value):
    try:
        raw = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (ValueError, TypeError, RecursionError) as exc:
        raise ValueError("receipt requires finite bounded JSON") from exc
    if len(raw) > MAX_BYTES:
        raise ValueError("receipt exceeds byte bound")
    return raw


def strict_json(raw):
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
        raise ValueError("receipt input exceeds byte bound")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate receipt key")
            result[key] = value
        return result

    try:
        return json.loads(
            raw,
            object_pairs_hook=unique,
            parse_constant=lambda _: (_ for _ in ()).throw(
                ValueError("nonfinite JSON")
            ),
        )
    except (UnicodeError, RecursionError) as exc:
        raise ValueError("invalid receipt JSON") from exc


def shape(value, fields, label):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise ValueError("invalid " + label + " fields")


def sha(value):
    if not isinstance(value, str) or not re.fullmatch("[0-9a-f]{64}", value):
        raise ValueError("expected exact SHA-256 identity")
    return value


def identity(value):
    if not isinstance(value, str):
        raise ValueError("expected canonical UUID identity")
    try:
        if str(uuid.UUID(value)) != value:
            raise ValueError("noncanonical UUID")
    except (ValueError, TypeError) as exc:
        raise ValueError("expected canonical UUID identity") from exc
    return value


def instant(value):
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError("expected bounded UTC timestamp")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid receipt time") from exc
    if result.tzinfo is None or result.utcoffset().total_seconds() != 0:
        raise ValueError("receipt timestamp must have explicit UTC timezone")
    return result


def now_time(now=None):
    result = datetime.now(timezone.utc) if now is None else now
    if not isinstance(result, datetime) or result.tzinfo is None:
        raise ValueError("receipt clock requires timezone")
    return result.astimezone(timezone.utc)


def validate_bindings(value):
    shape(value, BINDINGS, "receipt bindings")
    if value["client"] not in CLIENTS:
        raise ValueError("unsupported observation client")
    for key in ("source_sha256", "installation_sha256", "audience_sha256"):
        sha(value[key])
    for key in ("session_id", "event_id", "challenge"):
        identity(value[key])


def validate_payload(value, *, now=None):
    shape(value, PAYLOAD_FIELDS, "signed observation")
    validate_bindings({key: value[key] for key in BINDINGS})
    if value["schema"] != SCHEMA or value["event"] != "SessionStart":
        raise ValueError("unsupported observation schema or event")
    if value["status"] not in {"PASS", "FAIL", "UNKNOWN"}:
        raise ValueError("unsupported observation status")
    observed, issued, expires = (
        instant(value[key]) for key in ("observed_at", "issued_at", "expires_at")
    )
    current = now_time(now)
    if (
        not observed <= issued <= current < expires
        or not 0 < (expires - observed).total_seconds() <= MAX_TTL_SECONDS
    ):
        raise ValueError(
            "observation is stale, future-dated or exceeds finite lifetime"
        )
    canonical(value)
    return value


def public_key(value):
    # Exact Ed25519 wire key; no principals, options, comments, certificates or
    # wildcard patterns may be smuggled into the generated allowed-signers file.
    if (
        not isinstance(value, str)
        or len(value) > 256
        or not re.fullmatch(r"ssh-ed25519 [A-Za-z0-9+/]+={0,2}", value)
    ):
        raise ValueError("only exact Ed25519 public keys are supported")
    try:
        raw = base64.b64decode(value.split(" ")[1], validate=True)
    except ValueError as exc:
        raise ValueError("invalid public key encoding") from exc
    prefix = b"\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20"
    if len(raw) != len(prefix) + 32 or not raw.startswith(prefix):
        raise ValueError("invalid Ed25519 wire key")
    if base64.b64encode(raw).decode() != value.split(" ")[1]:
        raise ValueError("noncanonical public key encoding")
    return hashlib.sha256(raw).hexdigest()


def trusted_key(trust, payload, key_id, *, now=None):
    shape(
        trust, {"schema", "generation", "audience_sha256", "keys"}, "local trust anchor"
    )
    if trust["schema"] != 1 or type(trust["schema"]) is not int:
        raise ValueError("invalid trust schema")
    identity(trust["generation"])
    sha(trust["audience_sha256"])
    if trust["audience_sha256"] != payload["audience_sha256"]:
        raise ValueError("trust audience mismatch")
    keys = trust["keys"]
    if not isinstance(keys, list) or not 1 <= len(keys) <= 32:
        raise ValueError("trust requires bounded explicit keys")
    seen = set()
    selected = None
    for row in keys:
        shape(
            row,
            {
                "key_id",
                "public_key",
                "provenance_sha256",
                "clients",
                "sources",
                "installations",
                "not_before",
                "not_after",
                "revoked",
            },
            "trusted signer",
        )
        if row["key_id"] != public_key(row["public_key"]) or row["key_id"] in seen:
            raise ValueError("duplicate or mismatched signer identity")
        seen.add(row["key_id"])
        sha(row["provenance_sha256"])
        if type(row["revoked"]) is not bool:
            raise ValueError("explicit signer revocation state required")
        for field in ("clients", "sources", "installations"):
            entries = row[field]
            if (
                not isinstance(entries, list)
                or not 1 <= len(entries) <= 32
                or not all(isinstance(x, str) for x in entries)
                or len(set(entries)) != len(entries)
            ):
                raise ValueError("trust scope requires bounded unique exact values")
            if field == "clients":
                if not set(entries) <= CLIENTS:
                    raise ValueError("invalid signer client scope")
            else:
                for entry in entries:
                    sha(entry)
        before, after = instant(row["not_before"]), instant(row["not_after"])
        if before >= after:
            raise ValueError("invalid signer validity interval")
        if row["key_id"] == key_id:
            selected = row
    canonical(trust)
    if selected is None or selected["revoked"]:
        raise ValueError("unknown or revoked signer")
    if (
        payload["client"] not in selected["clients"]
        or payload["source_sha256"] not in selected["sources"]
        or payload["installation_sha256"] not in selected["installations"]
    ):
        raise ValueError("signer is not authorized for this observation scope")
    if not (
        instant(selected["not_before"])
        <= instant(payload["observed_at"])
        <= instant(payload["issued_at"])
        <= now_time(now)
        < instant(payload["expires_at"])
        <= instant(selected["not_after"])
    ):
        raise ValueError("observation exceeds current signer validity")
    return selected


def canonical_path(path):
    path = Path(path).absolute()
    # macOS's fixed OS aliases are not user-controlled enrollment aliases.
    for source, target in (
        ("/tmp", "/private/tmp"),
        ("/var", "/private/var"),
        ("/etc", "/private/etc"),
    ):
        if (
            os.path.islink(source)
            and os.readlink(source) == target
            and (str(path) == source or str(path).startswith(source + "/"))
        ):
            path = Path(target + str(path)[len(source) :])
    if ".." in path.parts or len(path.parts) > 128:
        raise ValueError("unsafe or excessive input path")
    return path


@contextmanager
def held_directory(path):
    """Pin each existing ancestor without following a user-controlled link."""
    path = canonical_path(path)
    descriptors = []
    chain = []
    try:
        fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
        descriptors.append(fd)
        for name in path.parts[1:]:
            child = os.open(
                name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd
            )
            descriptors.append(child)
            chain.append((fd, name, child, os.fstat(child)))
            fd = child

        def check():
            for parent, name, child, original in chain:
                old, fresh = (
                    os.fstat(child),
                    os.stat(name, dir_fd=parent, follow_symlinks=False),
                )
                if (
                    not stat.S_ISDIR(fresh.st_mode)
                    or (
                        original.st_dev,
                        original.st_ino,
                        original.st_mode,
                        original.st_uid,
                    )
                    != (old.st_dev, old.st_ino, old.st_mode, old.st_uid)
                    or (old.st_dev, old.st_ino, old.st_mode, old.st_uid)
                    != (fresh.st_dev, fresh.st_ino, fresh.st_mode, fresh.st_uid)
                ):
                    raise ValueError("input ancestor changed")

        check()
        yield fd, check
        check()
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def read_regular(path, *, limit=MAX_BYTES, private=False, owner=False):
    path = canonical_path(path)
    with held_directory(path.parent) as (parent, check):
        fd = os.open(
            path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent
        )
        try:
            before = os.fstat(fd)
            if (
                not stat.S_ISREG(before.st_mode)
                or before.st_nlink != 1
                or before.st_size > limit
            ):
                raise ValueError("input must be one bounded regular file")
            if (owner or private) and (
                before.st_uid != os.getuid()
                or stat.S_IMODE(before.st_mode) & (0o077 if private else 0o022)
            ):
                raise ValueError("input ownership or permission mode is unsafe")
            chunks = []
            remaining = limit + 1
            while remaining:
                chunk = os.read(fd, min(remaining, 65536))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            raw = b"".join(chunks)
            after, named = (
                os.fstat(fd),
                os.stat(path.name, dir_fd=parent, follow_symlinks=False),
            )

            def fields(s):
                return (
                    s.st_dev,
                    s.st_ino,
                    s.st_mode,
                    s.st_uid,
                    s.st_nlink,
                    s.st_size,
                    s.st_mtime_ns,
                    s.st_ctime_ns,
                )

            if (
                len(raw) > limit
                or fields(before) != fields(after)
                or fields(after) != fields(named)
            ):
                raise ValueError("input changed during bounded read")
            check()
            return raw
        finally:
            os.close(fd)


def _ssh(args, raw, *, executable="/usr/bin/ssh-keygen"):
    """Finite direct OpenSSH call; no shell, agent, askpass or inherited config."""
    executable = Path(executable)
    if (
        not executable.is_absolute()
        or executable.name != "ssh-keygen"
        or not executable.is_file()
    ):
        raise ValueError("OpenSSH signature helper is unavailable")
    env = {
        "PATH": "/usr/bin:/bin",
        "LANG": "C",
        "LC_ALL": "C",
        "SSH_ASKPASS_REQUIRE": "never",
    }
    with tempfile.TemporaryFile() as stream:
        stream.write(raw)
        stream.seek(0)
        proc = subprocess.Popen(
            [str(executable), *args],
            stdin=stream,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            start_new_session=True,
        )
        output = {"stdout": bytearray(), "stderr": bytearray()}
        selector = None
        try:
            # Process custody begins immediately after Popen, including failure
            # of observer construction, descriptor setup or registration.
            selector = selectors.DefaultSelector()
            for name in output:
                descriptor = getattr(proc, name)
                os.set_blocking(descriptor.fileno(), False)
                selector.register(descriptor, selectors.EVENT_READ, name)
            deadline = time.monotonic() + 5
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ValueError("OpenSSH signature operation exceeded deadline")
                for key, _ in selector.select(min(remaining, 0.1)):
                    chunk = os.read(key.fileobj.fileno(), 8192)
                    if not chunk:
                        selector.unregister(key.fileobj)
                    else:
                        output[key.data].extend(chunk)
                        if sum(map(len, output.values())) > 16384:
                            raise ValueError("OpenSSH diagnostic output exceeded bound")
            proc.wait(timeout=max(0.001, deadline - time.monotonic()))
            if proc.returncode != 0:
                raise ValueError("OpenSSH signature operation refused")
            return bytes(output["stdout"])
        finally:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait(timeout=2)
            proc.stdout.close()
            proc.stderr.close()
            if selector is not None:
                selector.close()


def sign(payload, trust, private_key, *, now=None):
    """Explicit prototype issuer. Keys are supplied by the caller, never found."""
    validate_payload(payload, now=now)
    key_bytes = read_regular(private_key, limit=16384, private=True)
    with tempfile.TemporaryDirectory(prefix="synthesis-signature-") as directory:
        key = Path(directory) / "key"
        key.write_bytes(key_bytes)
        key.chmod(0o600)
        pub = _ssh(["-y", "-f", str(key)], b"").decode("ascii").strip()
        # ssh-keygen -y may print an existing comment; only the wire key is used.
        pub = " ".join(pub.split()[:2])
        key_id = public_key(pub)
        signer = trusted_key(trust, payload, key_id, now=now)
        protected = {
            "schema": SCHEMA,
            "key_id": key_id,
            "payload": payload,
            "signer_provenance_sha256": signer["provenance_sha256"],
            "trust_generation": trust["generation"],
        }
        signature = _ssh(
            ["-Y", "sign", "-q", "-f", str(key), "-n", NAMESPACE], canonical(protected)
        ).decode("ascii")
    envelope = {**protected, "signature": signature}
    verify(envelope, trust, {key: payload[key] for key in BINDINGS}, now=now)
    return strict_json(canonical(envelope))


def _validate_envelope(envelope, trust, expected, *, now=None):
    shape(
        envelope,
        {
            "schema",
            "key_id",
            "payload",
            "signature",
            "signer_provenance_sha256",
            "trust_generation",
        },
        "signature envelope",
    )
    canonical(envelope)
    if envelope["schema"] != SCHEMA:
        raise ValueError("unsupported signature envelope")
    validate_bindings(expected)
    payload = validate_payload(envelope["payload"], now=now)
    if any(payload[key] != value for key, value in expected.items()):
        raise ValueError(
            "signed observation does not bind the current challenge and installation"
        )
    signer = trusted_key(trust, payload, sha(envelope["key_id"]), now=now)
    if (
        envelope["signer_provenance_sha256"] != signer["provenance_sha256"]
        or envelope["trust_generation"] != trust["generation"]
    ):
        raise ValueError("signer provenance or trust generation changed")
    signature = envelope["signature"]
    if (
        not isinstance(signature, str)
        or not 1 <= len(signature) <= 4096
        or not signature.isascii()
    ):
        raise ValueError("invalid signature encoding")
    return payload, signer, signature


def verification_snapshot(envelope, trust, expected):
    """Capture exact bounded input bytes; this does not verify a signature."""
    return tuple(canonical(value) for value in (envelope, trust, expected))


def revalidate_verified_inputs(snapshot, envelope, trust, expected, *, now=None):
    """Recheck a previously verified snapshot; never a substitute for crypto.

    Owners retain this exact snapshot across verification and effect admission.
    A new clock reading rejects expiry during crypto, filesystem checks or a
    write. Changed inputs cannot inherit the earlier signature verification.
    """
    if verification_snapshot(envelope, trust, expected) != snapshot:
        raise ValueError("signed observation inputs changed after verification")
    retained = tuple(strict_json(raw) for raw in snapshot)
    _validate_envelope(*retained, now=now)


def verify(envelope, trust, expected, *, now=None):
    snapshot = verification_snapshot(envelope, trust, expected)
    original = (envelope, trust, expected)
    # Cryptographic input and returned facts come from the same detached bytes.
    # Caller-owned dictionaries cannot change either while the helper runs.
    envelope, trust, expected = tuple(strict_json(raw) for raw in snapshot)
    payload, signer, signature = _validate_envelope(envelope, trust, expected, now=now)
    with tempfile.TemporaryDirectory(prefix="synthesis-verify-") as directory:
        allowed, supplied = Path(directory) / "allowed", Path(directory) / "signature"
        allowed.write_text("signer " + signer["public_key"] + "\n", encoding="ascii")
        supplied.write_text(signature, encoding="ascii")
        _ssh(
            [
                "-Y",
                "verify",
                "-q",
                "-f",
                str(allowed),
                "-I",
                "signer",
                "-n",
                NAMESPACE,
                "-s",
                str(supplied),
            ],
            canonical(
                {key: value for key, value in envelope.items() if key != "signature"}
            ),
        )
    revalidate_verified_inputs(snapshot, *original, now=now)
    return {
        "status": payload["status"],
        "signature_verified": True,
        "key_id": envelope["key_id"],
        "signer_provenance_sha256": signer["provenance_sha256"],
        "trust_generation": trust["generation"],
        "payload_sha256": hashlib.sha256(canonical(payload)).hexdigest(),
        "bindings": {key: payload[key] for key in BINDINGS},
        "native_acceptance": False,
        "action_authority": False,
    }

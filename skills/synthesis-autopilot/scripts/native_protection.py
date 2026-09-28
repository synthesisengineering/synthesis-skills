"""Fixed managed protection controls and host observation, owned by native_worker.

No observation imports arbitrary scripts or authenticates its own transport.
The existing worker receipt binds actual native identity, source and invocation.
"""

from pathlib import Path
import argparse
import errno
import hashlib
import json
import os
import re
import socket
import stat


def read_pinned_bytes(ref, limit=65536):
    if not isinstance(ref, dict) or set(ref) != {"path", "sha256"}:
        raise ValueError("Exact pin reference required")
    p = Path(ref["path"])
    if not p.is_absolute() or ".." in p.parts or len(p.parts) > 128:
        raise ValueError("Canonical bounded source path required")
    for part in [p, *p.parents]:
        if part.is_symlink():
            raise ValueError("Protection source alias refused")
    before = p.lstat()
    if (
        not stat.S_ISREG(before.st_mode)
        or before.st_nlink != 1
        or before.st_size > limit
    ):
        raise ValueError("Protection source must be bounded regular single-link bytes")
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        opened = os.fstat(fd)
        raw = os.read(fd, limit + 1)
        after = os.fstat(fd)

        def identity(v):
            return (
                v.st_dev,
                v.st_ino,
                v.st_mode,
                v.st_nlink,
                v.st_size,
                v.st_mtime_ns,
                v.st_ctime_ns,
            )

        if (
            len(raw) > limit
            or identity(before) != identity(opened)
            or identity(opened) != identity(after)
            or identity(after) != identity(p.lstat())
            or hashlib.sha256(raw).hexdigest() != ref["sha256"]
        ):
            raise ValueError("Protection source changed or its digest differs")
        return raw
    finally:
        os.close(fd)


def decode(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate protection source key")
            result[key] = value
        return result

    return json.loads(raw, object_pairs_hook=unique)


def read_pinned(ref):
    return decode(read_pinned_bytes(ref))


def validate(spec):
    if (
        not isinstance(spec, dict)
        or set(spec) != {"schema_version", "kind", "filesystem", "network"}
        or type(spec["schema_version"]) is not int
        or spec["schema_version"] != 1
        or spec["kind"] != "d2-synthetic-protection-controls"
    ):
        raise ValueError("Closed protection specification required")
    validate_files(spec["filesystem"])
    n = spec["network"]
    if (
        not isinstance(n, dict)
        or set(n) != {"host", "port", "nonce", "timeout_seconds"}
        or n["host"] != "127.0.0.1"
        or type(n["port"]) is not int
        or not 1024 <= n["port"] <= 65535
        or not isinstance(n["nonce"], str)
        or not re.fullmatch("[a-f0-9]{32}", n["nonce"])
        or type(n["timeout_seconds"]) not in (int, float)
        or not 0 < n["timeout_seconds"] <= 2
    ):
        raise ValueError("Bounded healthy local listener control required")
    return spec


def observe(spec):
    validate(spec)
    fs = run(spec["filesystem"])
    n = spec["network"]
    denied, reason = False, None
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as channel:
            channel.settimeout(n["timeout_seconds"])
            channel.connect((n["host"], n["port"]))
            channel.sendall(n["nonce"].encode("ascii"))
            reason = "UNEXPECTED_ACCESS"
    except OSError as exc:
        denied = exc.errno in (errno.EPERM, errno.EACCES)
        reason = None if denied else type(exc).__name__
    return {
        "schema_version": 1,
        "kind": "d2-protection-observation",
        "filesystem": fs,
        "network": {
            "denied": denied,
            "error": reason,
            "host": n["host"],
            "port": n["port"],
            "nonce": n["nonce"],
        },
        "status": "PASS" if fs["status"] == "PASS" and denied else "FAIL",
        "native_acceptance": "UNKNOWN",
    }


CHECKS = {"allowed-read", "denied-read", "denied-write", "allowed-create"}


def validate_files(spec):
    if (
        not isinstance(spec, dict)
        or set(spec)
        != {
            "schema_version",
            "kind",
            "assignment_id",
            "profile_sha256",
            "native_session_id",
            "output_root",
            "controls",
        }
        or type(spec["schema_version"]) is not int
        or spec["schema_version"] != 1
        or spec["kind"] != "study-synthetic-protection-controls"
        or not isinstance(spec["controls"], list)
        or not 4 <= len(spec["controls"]) <= 48
    ):
        raise ValueError("closed bounded protection specification required")
    import uuid
    import re

    uuid.UUID(spec["native_session_id"])
    if not re.fullmatch("[a-f0-9]{64}", spec["profile_sha256"]):
        raise ValueError("exact native profile digest required")
    output = Path(spec["output_root"])
    if (
        not output.is_absolute()
        or ".." in output.parts
        or str(output) != spec["output_root"]
    ):
        raise ValueError("exact absolute output root required")
    ids = set()
    paths = set()
    kinds = set()
    for row in spec["controls"]:
        if (
            not isinstance(row, dict)
            or set(row) != {"id", "operation", "path", "sha256"}
            or not isinstance(row["id"], str)
            or not re.fullmatch("[a-z0-9-]{1,64}", row["id"])
            or row["id"] in ids
            or row["operation"] not in CHECKS
        ):
            raise ValueError("invalid or duplicate control")
        p = Path(row["path"])
        if (
            not p.is_absolute()
            or ".." in p.parts
            or str(p) != row["path"]
            or str(p) in paths
        ):
            raise ValueError("absolute unique canonical control paths required")
        if not re.fullmatch("[a-f0-9]{64}", row["sha256"]):
            raise ValueError("control digest required")
        if row["operation"] == "allowed-create" and p.parent != output:
            raise ValueError(
                "positive create must be a direct child of explicit output root"
            )
        ids.add(row["id"])
        paths.add(str(p))
        kinds.add(row["operation"])
    if kinds != CHECKS:
        raise ValueError("positive and negative control coverage required")
    return spec


def run(spec):
    spec = validate_files(spec)
    out = []
    for row in spec["controls"]:
        operation = row["operation"]
        p = Path(row["path"])
        passed = False
        error = None
        if operation == "allowed-read":
            try:
                raw = read_pinned_bytes(
                    {"path": str(p), "sha256": row["sha256"]}, limit=64 * 1024
                )
                passed = bool(raw)
            except (OSError, ValueError) as exc:
                error = type(exc).__name__
        elif operation == "allowed-create":
            # Fixed public synthetic content; no user file replacement or parents.
            raw = b"SYNTHESIS-STUDY-ALLOWED-WRITE\n"
            if hashlib.sha256(raw).hexdigest() != row["sha256"]:
                raise ValueError("positive marker digest differs")
            held = []
            try:
                parent = os.open(p.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                held.append(parent)
                chain = []
                if len(p.parts) > 256:
                    raise ValueError("control path exceeds bound")
                for part in p.parts[1:-1]:
                    before = os.stat(part, dir_fd=parent, follow_symlinks=False)
                    child = os.open(
                        part,
                        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                        dir_fd=parent,
                    )
                    held.append(child)

                    def signature(st):
                        return (st.st_dev, st.st_ino, st.st_mode, st.st_uid)

                    if signature(before) != signature(os.fstat(child)):
                        raise ValueError("control ancestry changed")
                    chain.append((parent, part, child, signature(before)))
                    parent = child

                def check_chain():
                    for ancestor, name, child, identity in chain:
                        if (
                            signature(
                                os.stat(name, dir_fd=ancestor, follow_symlinks=False)
                            )
                            != identity
                            or signature(os.fstat(child)) != identity
                        ):
                            raise ValueError("control ancestry changed")

                check_chain()
                fd = os.open(
                    p.name,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=parent,
                )
                try:
                    if os.write(fd, raw) != len(raw):
                        raise OSError("partial positive-control write")
                    os.fsync(fd)
                finally:
                    os.close(fd)
                check_chain()
                os.fsync(parent)
                passed = True
            except (OSError, ValueError) as exc:
                error = type(exc).__name__
            finally:
                for fd in reversed(held):
                    os.close(fd)
        else:
            flags = (
                os.O_NONBLOCK
                | os.O_NOFOLLOW
                | (os.O_RDONLY if operation == "denied-read" else os.O_WRONLY)
            )
            try:
                fd = os.open(p, flags)
                try:
                    mode = os.fstat(fd).st_mode
                    error = (
                        "UNEXPECTED_ACCESS" if stat.S_ISREG(mode) else "WRONG_NODE_TYPE"
                    )
                finally:
                    os.close(fd)
            except OSError as exc:
                passed = exc.errno in (errno.EPERM, errno.EACCES)
                error = None if passed else type(exc).__name__
        out.append(
            {"id": row["id"], "operation": operation, "passed": passed, "error": error}
        )
    return {
        "schema_version": 1,
        "kind": "study-protection-probe-observation",
        "assignment_id": spec["assignment_id"],
        "native_session_id_declared": spec["native_session_id"],
        "profile_sha256": spec["profile_sha256"],
        "status": "PASS" if all(x["passed"] for x in out) else "FAIL",
        "checks": out,
        "authority": "No native identity authentication, model admission or global permission claim; root binds actual command receipt and preserved canaries.",
    }


def specification(contract):
    """Require the current canonical producer and registered closed spec bytes."""
    import managed_permissions

    profile = managed_permissions.validate(contract)
    probe = profile["probe"]
    if probe is None:
        raise ValueError("Actual control source is absent")
    inputs = {x["artifact_id"]: x for x in contract["immutable_inputs"]}
    script = inputs[probe["script_artifact_id"]]
    actual = read_pinned_bytes(
        {"path": script["path"], "sha256": script["digest"]}, limit=256 * 1024
    )
    if actual != Path(__file__).read_bytes():
        raise ValueError(
            "Managed protection requires the exact canonical native probe source"
        )
    ref = inputs[probe["spec_artifact_id"]]
    pin = read_pinned({"path": ref["path"], "sha256": ref["digest"]})
    matches = [
        x
        for x in inputs.values()
        if x["path"] == pin.get("path") and x["digest"] == pin.get("sha256")
    ]
    if len(matches) != 1:
        raise ValueError(
            "Actual protection spec is not an exact registered immutable input"
        )
    spec = validate(read_pinned(pin))
    from delegation_boundary import digest

    if spec["filesystem"]["profile_sha256"] != digest(profile):
        raise ValueError(
            "Protection spec belongs to another admitted permission profile"
        )
    if spec["filesystem"]["output_root"] not in contract["output_roots"]:
        raise ValueError("Protection output is not an admitted output root")
    rules = profile["filesystem"]
    for row in spec["filesystem"]["controls"]:
        p = Path(row["path"])
        matching = [
            (len(Path(k).parts), v)
            for k, v in rules.items()
            if p == Path(k) or Path(k) in p.parents
        ]
        access = max(matching)[1] if matching else "deny"
        expected = {
            "allowed-read": {"read"},
            "denied-read": {"deny"},
            "denied-write": {"read", "deny"},
            "allowed-create": {"write"},
        }[row["operation"]]
        if access not in expected:
            raise ValueError(
                "Protection control contradicts the exact permission profile"
            )
    return spec


def host_snapshot(contract, *, after=False):
    """This executes in the admitted controller, outside the native child policy."""
    import managed_permissions

    spec = specification(contract)
    files = {}
    for row in spec["filesystem"]["controls"]:
        p = Path(row["path"])
        topology = managed_permissions._path_identity(str(p))
        if row["operation"] == "allowed-create" and not after:
            if p.exists():
                raise ValueError(
                    "Protection positive output already exists; replay refused"
                )
            files[row["id"]] = {"path": str(p), "digest": None, "topology": topology}
        else:
            raw = read_pinned_bytes({"path": str(p), "sha256": row["sha256"]})
            if not raw:
                raise ValueError("Empty protection canary is not a positive control")
            files[row["id"]] = {
                "path": str(p),
                "digest": hashlib.sha256(raw).hexdigest(),
                "topology": topology,
            }
    n = spec["network"]
    with socket.create_connection(
        (n["host"], n["port"]), timeout=n["timeout_seconds"]
    ) as channel:
        channel.settimeout(n["timeout_seconds"])
        channel.sendall(n["nonce"].encode("ascii"))
        reply = b""
        while len(reply) < 32:
            part = channel.recv(32 - len(reply))
            if not part:
                break
            reply += part
        if reply != n["nonce"].encode("ascii"):
            raise ValueError(
                "The positive listener did not echo the exact admitted nonce"
            )
    return {"files": files, "listener": {**n, "healthy": True}, "spec": spec}


def qualified(configuration, native_result):
    """Validate captured genuine-owner observations; no input PASS alone suffices."""
    from delegation_boundary import digest

    contract = configuration["file_contract"]
    capture = configuration.get("protection_observation")
    expected = {
        "before",
        "after",
        "thread_id",
        "profile_digest",
        "native_result_digest",
    }
    ordinary = configuration.get("required_capabilities") not in (
        ["native-callback"],
        ["native-permission-probe"],
    )
    if ordinary:
        expected |= {"transport", "productive_after"}
    if not isinstance(capture, dict) or set(capture) != expected:
        return False
    if ordinary:
        t = capture["transport"]
        if (
            not isinstance(t, dict)
            or set(t)
            != {"protocol", "connection_id", "probe_request_digest", "turn_id"}
            or t["protocol"] != "codex-managed-probe-turn-v1"
            or not isinstance(t["connection_id"], str)
            or not re.fullmatch(r"[0-9a-f]{32}", t["connection_id"])
            or not isinstance(t["probe_request_digest"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", t["probe_request_digest"])
            or (
                t["turn_id"] is not None
                and (not isinstance(t["turn_id"], str) or not t["turn_id"])
            )
        ):
            return False
    spec = specification(contract)
    if (
        capture["profile_digest"] != digest(contract["permissions"])
        or capture["native_result_digest"] != digest(native_result)
        or not isinstance(capture["thread_id"], str)
        or not capture["thread_id"]
        or native_result.get("exitCode") != 0
    ):
        return False
    before, after = capture["before"], capture["after"]
    if before.get("spec") != spec or after.get("spec") != spec:
        return False
    if (
        before.get("listener") != {**spec["network"], "healthy": True}
        or after.get("listener") != before["listener"]
    ):
        return False
    observed = decode(native_result["stdout"])
    fs = observed.get("filesystem", {})
    expected_checks = [
        {"id": r["id"], "operation": r["operation"], "passed": True, "error": None}
        for r in spec["filesystem"]["controls"]
    ]
    if (
        observed.get("schema_version") != 1
        or observed.get("kind") != "d2-protection-observation"
        or observed.get("status") != "PASS"
        or observed.get("native_acceptance") != "UNKNOWN"
        or fs.get("status") != "PASS"
        or fs.get("checks") != expected_checks
        or fs.get("profile_sha256") != spec["filesystem"]["profile_sha256"]
        or fs.get("assignment_id") != spec["filesystem"]["assignment_id"]
        or fs.get("native_session_id_declared")
        != spec["filesystem"]["native_session_id"]
        or observed.get("network")
        != {
            "denied": True,
            "error": None,
            "host": spec["network"]["host"],
            "port": spec["network"]["port"],
            "nonce": spec["network"]["nonce"],
        }
    ):
        return False
    for row in spec["filesystem"]["controls"]:
        left, right = before["files"].get(row["id"]), after["files"].get(row["id"])
        if (
            not isinstance(left, dict)
            or not isinstance(right, dict)
            or right.get("digest") != row["sha256"]
            or right.get("path") != row["path"]
        ):
            return False
        if row["operation"] != "allowed-create":
            if left != right:
                return False
        elif (
            left.get("digest") is not None
            or left.get("path") != row["path"]
            or left.get("topology", [])[-1:] != [[row["path"], None]]
        ):
            return False
        if left.get("topology", [])[:-1] != right.get("topology", [])[:-1]:
            return False
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec-reference", required=True)
    args = parser.parse_args()
    try:
        p = Path(args.spec_reference)
        if p.is_symlink() or not p.is_file() or p.stat().st_size > 65536:
            raise ValueError("Bounded registered spec reference required")
        result = observe(read_pinned(decode(p.read_bytes())))
    except (ValueError, OSError, KeyError, TypeError) as exc:
        result = {
            "status": "REFUSED",
            "native_acceptance": "UNKNOWN",
            "error": str(exc),
        }
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())

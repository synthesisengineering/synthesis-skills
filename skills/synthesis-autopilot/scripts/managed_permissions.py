"""Closed, artifact-bound Codex permission compiler; never an authority ledger.

The file contract is admitted by PM. This module narrows that exact admission,
keeps config/observation distinct from OS enforcement, and cannot enable network,
expand write roots, edit user configuration, or grant hook trust.
"""

from __future__ import annotations
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat

MAX_PROFILE_BYTES = 128 * 1024
MAX_RULES = 256
MODEL_FREE = {"native-callback", "native-permission-probe"}


def _closed(value, keys, label):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError(label + " has unknown or missing fields")


def _identity(value):
    from delegation_boundary import _path

    _closed(value, {"path", "sha256", "size"}, "executable identity")
    _path(value["path"])
    if (
        not isinstance(value["sha256"], str)
        or not re.fullmatch(r"[0-9a-f]{64}", value["sha256"])
        or type(value["size"]) is not int
        or not 4 <= value["size"] <= 1024**3
    ):
        raise ValueError("Exact native executable bytes are required")


def validate(contract):
    """Pure shape/role validation; inspect() binds the actual artifact bytes."""
    from delegation_boundary import _path, _inside

    value = contract["permissions"]
    _closed(value, {"source", "profile"}, "managed permissions")
    source, profile = value["source"], value["profile"]
    if source not in contract["immutable_inputs"]:
        raise ValueError("Permission source must be an admitted immutable artifact")
    _closed(
        profile,
        {
            "schema_version",
            "client",
            "id",
            "filesystem",
            "network",
            "approval_policy",
            "native_executable",
            "probe",
        },
        "permission profile",
    )
    if (
        type(profile["schema_version"]) is not int
        or profile["schema_version"] != 1
        or profile["client"] != "codex"
        or profile["network"] is not False
        or profile["approval_policy"] != "never"
        or not isinstance(profile["id"], str)
        or not re.fullmatch(r"synthesis-[a-z0-9][a-z0-9-]{0,62}", profile["id"])
    ):
        raise ValueError(
            "Explicit supported managed profile and no-network posture required"
        )
    _identity(profile["native_executable"])
    rules = profile["filesystem"]
    if not isinstance(rules, dict) or not 1 <= len(rules) <= MAX_RULES:
        raise ValueError("Bounded exact filesystem rules required")
    parsed = {}
    for path, access in rules.items():
        p = _path(path)
        if (
            any(c in path for c in "*?[]\\")
            or not isinstance(access, str)
            or access not in {"read", "write", "deny"}
        ):
            raise ValueError("Only exact literal read/write/deny paths are supported")
        parsed[p] = access
    writable = set(contract["output_roots"] + [contract["scratch_root"]])
    if {p for p, access in rules.items() if access == "write"} != writable:
        raise ValueError(
            "Managed writes must exactly equal admitted output/scratch roots"
        )
    # A narrower allow must never reopen a denied tree. A read rule cannot conceal
    # an immutable artifact inside an admitted writable ancestor.
    for path, access in parsed.items():
        for denied, deny_access in parsed.items():
            if deny_access == "deny" and access != "deny" and _inside(path, denied):
                raise ValueError("Managed allow reopens a denied path")
        if access == "read" and any(_inside(path, _path(w)) for w in writable):
            raise ValueError("Read and writable roles overlap")
    for item in contract["immutable_inputs"]:
        path = _path(item["path"])
        if not any(
            access == "read" and _inside(path, root) for root, access in parsed.items()
        ):
            raise ValueError("Every immutable input needs explicit managed read access")
        if any(
            access == "deny" and _inside(path, root) for root, access in parsed.items()
        ):
            raise ValueError("Managed denial contradicts an immutable input")
    probe = profile["probe"]
    if probe is not None:
        _closed(
            probe,
            {
                "interpreter",
                "script_artifact_id",
                "spec_artifact_id",
                "timeout_ms",
                "output_bytes_cap",
            },
            "managed probe",
        )
        _identity(probe["interpreter"])
        interpreter = _path(probe["interpreter"]["path"])
        if not any(
            access == "read" and _inside(interpreter, root)
            for root, access in parsed.items()
        ) or any(
            access != "read" and _inside(interpreter, root)
            for root, access in parsed.items()
        ):
            raise ValueError(
                "Probe interpreter requires an explicit immutable read role"
            )
        ids = {x["artifact_id"]: x for x in contract["immutable_inputs"]}
        if (
            not isinstance(probe["script_artifact_id"], str)
            or not isinstance(probe["spec_artifact_id"], str)
            or probe["script_artifact_id"] == probe["spec_artifact_id"]
            or any(
                probe[k] not in ids for k in ("script_artifact_id", "spec_artifact_id")
            )
            or type(probe["timeout_ms"]) is not int
            or not 1 <= probe["timeout_ms"] <= 30000
            or type(probe["output_bytes_cap"]) is not int
            or not 1024 <= probe["output_bytes_cap"] <= 256 * 1024
        ):
            raise ValueError("Probe requires exact registered inputs and finite bounds")
    return profile


def _signature(info):
    return [
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_nlink,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    ]


def _path_identity(path):
    """Bounded no-follow path/ancestor metadata, including absent final targets."""
    p = Path(path)
    if len(p.parts) > 128:
        raise ValueError("Permission ancestry exceeds its bound")
    answer = []
    for node in reversed([p, *p.parents]):
        try:
            info = node.lstat()
        except FileNotFoundError:
            answer.append([str(node), None])
            continue
        if stat.S_ISLNK(info.st_mode) or not (
            stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)
        ):
            raise ValueError("Permission paths cannot contain aliases or special nodes")
        if stat.S_ISREG(info.st_mode) and info.st_nlink != 1:
            raise ValueError("Permission file has an unbounded hardlink alias")
        # Directory content timestamps legitimately change with output creation;
        # the pathname/inode/mode identity must still remain unchanged.
        identity = (
            _signature(info)
            if stat.S_ISREG(info.st_mode)
            else [info.st_dev, info.st_ino, info.st_mode]
        )
        answer.append([str(node), identity])
    return answer


def _aliases(path):
    result = [path]
    for alias, canonical in (("/tmp", "/private/tmp"), ("/var", "/private/var")):
        if path == canonical or path.startswith(canonical + "/"):
            link = Path(alias)
            if link.is_symlink() and str(link.resolve()) == canonical:
                result.append(alias + path[len(canonical) :])
    return result


def compiled_profile(contract):
    profile = validate(contract)
    rules = {":root": "deny", ":minimal": "read"}
    for path, access in profile["filesystem"].items():
        for spelling in _aliases(path):
            if spelling in rules and rules[spelling] != access:
                raise ValueError("Conflicting native path aliases")
            rules[spelling] = access
    # Preserve native workspace metadata protection with exact roots, without
    # inheriting :workspace's ambient tmp or extra workspace write grants.
    for root in contract["output_roots"] + [contract["scratch_root"]]:
        for name in (".git", ".codex", ".agents"):
            path = str(PurePosixPath(root) / name)
            for spelling in _aliases(path):
                if rules.get(spelling) not in (None, "read", "deny"):
                    raise ValueError("Protected native metadata cannot become writable")
                rules.setdefault(spelling, "read")
    return {"filesystem": rules, "network": {"enabled": False}}


def inspect(contract, *, executable=None):
    from delegation_boundary import _read_file, _physical

    profile = validate(contract)
    ref = contract["permissions"]["source"]
    path = _physical(ref["path"])
    raw, before = _read_file(path, limit=MAX_PROFILE_BYTES)
    if before["links"] != 1:
        raise ValueError("Managed profile source has a hardlink alias")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate permission configuration key")
            result[key] = value
        return result

    decoded = json.loads(
        raw,
        object_pairs_hook=unique,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite policy")),
    )
    if (
        before != _read_file(path, limit=MAX_PROFILE_BYTES)[1]
        or before["digest"] != ref["digest"]
        or hashlib.sha256(raw).hexdigest() != ref["digest"]
        or decoded != profile
    ):
        raise ValueError("Managed profile differs from its exact admitted source")
    topology = {p: _path_identity(p) for p in profile["filesystem"]}
    aliases = {p: _aliases(p) for p in profile["filesystem"]}
    if executable is not None:
        from native_resume import binary_identity

        if binary_identity(executable) != profile["native_executable"]:
            raise ValueError("Managed native executable differs from admitted bytes")
        if (
            profile["probe"]
            and binary_identity(profile["probe"]["interpreter"]["path"])
            != profile["probe"]["interpreter"]
        ):
            raise ValueError("Managed probe interpreter changed")
    return {
        "source": before,
        "topology": topology,
        "aliases": aliases,
        "compiled": compiled_profile(contract),
    }


def _toml(value):
    if isinstance(value, dict):
        return (
            "{"
            + ",".join(json.dumps(k) + "=" + _toml(v) for k, v in sorted(value.items()))
            + "}"
        )
    if type(value) is bool:
        return "true" if value else "false"
    if isinstance(value, str):
        return json.dumps(value)
    raise ValueError("Unsupported native configuration scalar")


def server_argv(executable, contract):
    profile = validate(contract)
    return [
        executable,
        "--no-daemon",
        "-c",
        "default_permissions=" + _toml(profile["id"]),
        "-c",
        "permissions." + profile["id"] + "=" + _toml(compiled_profile(contract)),
        "app-server",
    ]


def scoped_evaluation(configuration):
    """The local evaluation grant never narrows unrelated product providers."""
    return (
        configuration.get("resume") is not None
        or configuration.get("allocation") is not None
        or configuration.get("required_capabilities") == ["managed-study-turn"]
    )


def verify_config(configuration, result):
    contract = configuration["file_contract"]
    profile = validate(contract)
    config = result.get("config") if isinstance(result, dict) else None
    if (
        not isinstance(config, dict)
        or (
            scoped_evaluation(configuration)
            and (
                config.get("model_provider") not in (None, "openai")
                or not isinstance(config.get("model_providers", {}), dict)
                or bool(config.get("model_providers", {}).get("openai"))
            )
        )
        or config.get("default_permissions") != profile["id"]
        or not isinstance(config.get("permissions"), dict)
        or config["permissions"].get(profile["id"]) != compiled_profile(contract)
    ):
        raise ValueError(
            "Native effective managed configuration differs or is unavailable"
        )
    return {
        "profile_id": profile["id"],
        "configured": "MATCH",
        "enforcement": "UNKNOWN",
    }


def verify_active(configuration, response):
    profile = validate(configuration["file_contract"])
    active = response.get("activePermissionProfile")
    selected = configuration["selected"]
    if (
        not isinstance(active, dict)
        or set(active) - {"id", "extends"}
        or active.get("id") != profile["id"]
        or active.get("extends") is not None
        or response.get("approvalPolicy") != "never"
        or (
            scoped_evaluation(configuration)
            and response.get("modelProvider") != "openai"
        )
        or response.get("model") != selected["model"]
        or response.get("reasoningEffort") != selected["model_reasoning_effort"]
        or response.get("cwd") != configuration["file_contract"]["scratch_root"]
    ):
        raise ValueError("Native active permission profile or selection differs")
    return {
        "profile_id": profile["id"],
        "configured": "MATCH",
        "enforcement": "UNKNOWN",
    }


def probe_params(configuration):
    contract = configuration["file_contract"]
    profile = validate(contract)
    probe = profile["probe"]
    if probe is None:
        raise ValueError("No admitted managed probe command")
    inputs = {x["artifact_id"]: x for x in contract["immutable_inputs"]}
    return {
        "command": [
            probe["interpreter"]["path"],
            "-I",
            inputs[probe["script_artifact_id"]]["path"],
            "--spec-reference",
            inputs[probe["spec_artifact_id"]]["path"],
        ],
        "cwd": contract["scratch_root"],
        "permissionProfile": profile["id"],
        "processId": "synthesis-"
        + hashlib.sha256(profile["id"].encode()).hexdigest()[:24],
        "timeoutMs": probe["timeout_ms"],
        "outputBytesCap": probe["output_bytes_cap"],
    }

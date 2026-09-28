"""Existing PM native-worker receipt owner, specialized for passive Hermes capture."""

from __future__ import annotations
import hashlib
import base64
import json
from pathlib import Path
import time
import uuid

import delegation_boundary as boundary
import hermes_transport as transport


def selection(contract):
    if len(contract["immutable_inputs"]) != 1:
        raise ValueError(
            "Hermes observation needs one exact admitted selection artifact"
        )
    item = contract["immutable_inputs"][0]
    path = boundary._physical(item["path"])
    if (
        boundary._file(path)["digest"] != item["digest"]
        or path.stat().st_size > 128 * 1024
    ):
        raise ValueError("Hermes observation selection changed")
    return transport._json(path.read_bytes())


def run(state, child, contract, context, runtime_root, timeout, before):
    started = time.monotonic()
    chosen = selection(contract)
    transport.validate_selection(chosen, deadline=started + timeout)
    attempt = boundary._physical(runtime_root) / child["child_id"]
    attempt.parent.mkdir(parents=True, exist_ok=True)
    attempt.mkdir()  # No implicit replay or foreign overwrite.
    channel = boundary._physical(contract["scratch_root"]) / "hook.sock"
    configuration = {
        "client": "hermes",
        "required_capabilities": [transport.CAPABILITY],
        "file_contract": contract,
        "selection": chosen,
        "channel": str(channel),
        "timeout_seconds": timeout,
        **{k: state[k] for k in ("run_id", "contract_digest", "profile_digest")},
    }
    (attempt / "launch.json").write_text(json.dumps(configuration, sort_keys=True))
    rows, failure, frames = [], None, []
    try:
        if selection(contract) != chosen or boundary.inspect_files(contract) != before:
            raise ValueError("admitted inputs changed before observation")
        rows, failure = transport.capture(
            channel,
            chosen,
            max(0, timeout - (time.monotonic() - started)),
            raw_frames=frames,
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        failure = str(exc)[:500]
    header = {
        "type": "synthesis.hermes_observation",
        "schema": 1,
        "session_id": chosen["session_id"],
        "producer_version": chosen["producer_version"],
        "capture_id": str(uuid.uuid4()),
        "selection_sha256": boundary.digest(chosen),
    }
    raw = b"".join(
        (json.dumps(row, sort_keys=True) + "\n").encode() for row in [header, *rows]
    )
    (attempt / "stdout.jsonl").write_bytes(raw)
    # Raw transport bytes remain separate from strict JSON metadata. Base64
    # encoding two valid bounded frames must not exceed the parser's input cap.
    retained_frames = []
    for index, frame in enumerate(frames):
        original = base64.b64decode(frame["raw_base64"], validate=True)
        name = f"frame-{index}.bin"
        (attempt / name).write_bytes(original)
        retained_frames.append(
            {
                "file": name,
                "size": len(original),
                "complete": frame["complete"],
                "sha256": frame["sha256"],
            }
        )
    (attempt / "transport.json").write_text(
        json.dumps({"frames": retained_frames}, sort_keys=True)
    )
    effects = boundary.inspect_effects(contract, before)
    data = {
        "schema_version": 1,
        "child_id": child["child_id"],
        "client": "hermes",
        "producer": "hermes:" + chosen["session_id"],
        "terminal": "failed" if failure else "completed",
        "usage": {"tokens": None, "usd_micros": None},
        "model_turns_started": 0,
        "file_contract_digest": boundary.digest(contract),
        "boundary": {
            "status": "UNKNOWN",
            "mechanism": "hermes-local-peer-observation",
            "configuration_digest": boundary.digest(configuration),
            "scope": "context-observation-only",
        },
        "preservation": effects["preservation"],
        "violations": effects["violations"],
        "output_manifest": {
            p: v
            for p, v in effects["output_manifest"].items()
            if any(
                boundary._inside(Path(p), Path(root))
                for root in contract["output_roots"]
            )
        },
        "native_exit_code": 0 if failure is None else 2,
        "elapsed_millis": round((time.monotonic() - started) * 1000),
    }
    manifest = {
        "data": data,
        "configuration": configuration,
        "before": before,
        "effects": effects,
        "failure": failure,
        "process_cleanup": {
            "cleanup_verified": not channel.exists(),
            "scope": "owned listener only; selected native process never started or signaled",
        },
        "raw": {
            name: hashlib.sha256((attempt / name).read_bytes()).hexdigest()
            for name in (
                "launch.json",
                "stdout.jsonl",
                "transport.json",
                *(frame["file"] for frame in retained_frames),
            )
        },
    }
    path = attempt / "receipt.json"
    path.write_text(json.dumps(manifest, sort_keys=True))
    return {
        **data,
        "receipt_path": str(path),
        "receipt_digest": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def verify(data, context):
    """Current receipt/source admission, not a fabricated native sandbox verdict."""
    try:
        state = context["state"]
        child = state["extensions"]["workflow"]["children"][data["child_id"]]
        if child["client"] != "hermes" or child["required_capabilities"] != [
            transport.CAPABILITY
        ]:
            return False
        expected = (
            Path(context["project"])
            / "resources/autopilot-runs"
            / state["run_id"]
            / "native-worker-attempts"
            / child["child_id"]
        )
        path = boundary._physical(data["receipt_path"])
        if (
            path != expected / "receipt.json"
            or boundary._file(path)["digest"] != data["receipt_digest"]
        ):
            return False
        manifest = transport._json(path.read_bytes())
        if manifest["data"] != {
            k: v for k, v in data.items() if k not in {"receipt_path", "receipt_digest"}
        }:
            return False
        config = manifest["configuration"]
        if (
            any(
                config[k] != state[k]
                for k in ("run_id", "contract_digest", "profile_digest")
            )
            or config["file_contract"] != child["file_contract"]
            or boundary.digest(config) != data["boundary"]["configuration_digest"]
        ):
            return False
        chosen = selection(child["file_contract"])
        if chosen != config["selection"] or data[
            "file_contract_digest"
        ] != boundary.digest(child["file_contract"]):
            return False
        transport._source_files(chosen)
        metadata_path = boundary._physical(expected / "transport.json")
        if metadata_path.stat().st_size > 4096:
            return False
        metadata = transport._json(metadata_path.read_bytes())
        if set(metadata) != {"frames"} or not isinstance(metadata["frames"], list):
            return False
        frames = metadata["frames"]
        if len(frames) > 2:
            return False
        names = []
        for index, frame in enumerate(frames):
            if (
                not isinstance(frame, dict)
                or set(frame) != {"file", "size", "complete", "sha256"}
                or frame["file"] != f"frame-{index}.bin"
                or type(frame["size"]) is not int
                or not 0 <= frame["size"] <= transport.MAX_FRAME + 1
                or type(frame["complete"]) is not bool
            ):
                return False
            names.append(frame["file"])
        if set(manifest["raw"]) != {
            "launch.json",
            "stdout.jsonl",
            "transport.json",
            *names,
        }:
            return False
        for name, sha in manifest["raw"].items():
            if boundary._file(boundary._physical(expected / name))["digest"] != sha:
                return False
        if transport._json((expected / "launch.json").read_bytes()) != config:
            return False
        raw = (expected / "stdout.jsonl").read_bytes()
        if len(raw) > transport.MAX_CAPTURE or not raw.endswith(b"\n"):
            return False
        rows = [transport._json(line) for line in raw.splitlines()]
        if (
            rows[0]["selection_sha256"] != boundary.digest(chosen)
            or rows[0]["session_id"] != chosen["session_id"]
        ):
            return False
        if data["terminal"] == "completed":
            transport.validate_pair(rows[1:], chosen)
            if len(frames) != 2:
                return False
            for frame, row in zip(frames, rows[1:]):
                original_path = boundary._physical(expected / frame["file"])
                if original_path.stat().st_size != frame["size"]:
                    return False
                original = original_path.read_bytes()
                if (
                    frame["complete"] is not True
                    or len(original) > transport.MAX_FRAME
                    or hashlib.sha256(original).hexdigest() != frame["sha256"]
                ):
                    return False
                if transport._json(original) != {
                    k: v for k, v in row.items() if k not in {"peer", "sequence"}
                }:
                    return False
            if (
                manifest["failure"] is not None
                or not manifest["process_cleanup"]["cleanup_verified"]
                or data["native_exit_code"] != 0
            ):
                return False
        elif not manifest["failure"]:
            return False
        if (
            data["boundary"]["status"] != "UNKNOWN"
            or data["boundary"]["mechanism"] != "hermes-local-peer-observation"
            or type(data.get("model_turns_started")) is not int
            or data["model_turns_started"] != 0
        ):
            return False
        effects = boundary.inspect_effects(child["file_contract"], manifest["before"])
        output = {
            p: v
            for p, v in effects["output_manifest"].items()
            if any(
                boundary._inside(Path(p), Path(root))
                for root in child["file_contract"]["output_roots"]
            )
        }
        return (
            effects["preservation"] == data["preservation"]
            and effects["violations"] == data["violations"]
            and output == data["output_manifest"]
        )
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return False

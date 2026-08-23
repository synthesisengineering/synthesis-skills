#!/usr/bin/env python3
"""Create, validate, and verify a text-provenance manifest.

This tool records hashes and lineage. It does not establish authorship or the
absence of a provider watermark.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = 2
MANIFEST_HASH_FIELD = "manifest_sha256"
GENERATION_MODES = {"human", "hosted", "local_open_weight", "mixed", "unknown"}
ENDPOINT_CLASSES = {"none", "hosted", "local_loopback", "local_lan", "unknown"}
AUDIT_KINDS = {"text_integrity", "provider_detector", "standards_detector", "other"}
FILE_RECORD_FIELDS = {"path", "sha256", "bytes"}
PARENT_RECORD_FIELDS = {"record_id", "manifest_sha256", "output_sha256"}
REQUIRED_TOP_LEVEL = {
    "schema_version",
    "record_id",
    "created_at",
    MANIFEST_HASH_FIELD,
    "generation_mode",
    "provider",
    "model_requested",
    "model_returned",
    "runtime",
    "runtime_receipt",
    "endpoint_class",
    "prompt",
    "sources",
    "output",
    "parameters",
    "parents",
    "human_edit_description",
    "audits",
    "notes",
}


class ManifestError(ValueError):
    """Raised when a manifest violates schema or verification requirements."""


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_record(path: Path, pointer: str | None = None) -> dict[str, Any]:
    if not path.is_file():
        raise ManifestError(f"not a regular file: {path}")
    return {
        "path": pointer if pointer is not None else str(path),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
    }


def canonical_manifest_bytes(data: dict[str, Any]) -> bytes:
    """Return canonical UTF-8 JSON bytes, excluding the self-hash field."""

    canonical_data = {key: value for key, value in data.items() if key != MANIFEST_HASH_FIELD}
    try:
        encoded = json.dumps(
            canonical_data,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise ManifestError(f"manifest cannot be canonicalized: {exc}") from exc
    return encoded.encode("utf-8")


def manifest_sha256(data: dict[str, Any]) -> str:
    return sha256_bytes(canonical_manifest_bytes(data))


def seal_manifest(data: dict[str, Any]) -> dict[str, Any]:
    sealed = dict(data)
    sealed[MANIFEST_HASH_FIELD] = manifest_sha256(sealed)
    return sealed


def _is_digest(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _validate_file_record(value: Any, field: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return [f"{field} must be an object"]
    if set(value) != FILE_RECORD_FIELDS:
        errors.append(f"{field} must contain exactly path, sha256, and bytes")
    if not isinstance(value.get("path"), str) or not value.get("path"):
        errors.append(f"{field}.path must be a non-empty string")
    if not _is_digest(value.get("sha256")):
        errors.append(f"{field}.sha256 must be a lowercase SHA-256 hex digest")
    if (
        not isinstance(value.get("bytes"), int)
        or isinstance(value.get("bytes"), bool)
        or value.get("bytes", -1) < 0
    ):
        errors.append(f"{field}.bytes must be a non-negative integer")
    return errors


def _validate_parent_record(value: Any, field: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return [f"{field} must be an object"]
    if set(value) != PARENT_RECORD_FIELDS:
        errors.append(
            f"{field} must contain exactly record_id, manifest_sha256, and output_sha256"
        )
    try:
        uuid.UUID(str(value.get("record_id")))
    except (ValueError, TypeError, AttributeError):
        errors.append(f"{field}.record_id must be a UUID")
    for name in ("manifest_sha256", "output_sha256"):
        if not _is_digest(value.get(name)):
            errors.append(f"{field}.{name} must be a lowercase SHA-256 hex digest")
    return errors


def _validate_json_value(value: Any, field: str) -> list[str]:
    if value is None or isinstance(value, (str, bool, int)):
        return []
    if isinstance(value, float):
        return [] if math.isfinite(value) else [f"{field} must not contain NaN or infinity"]
    if isinstance(value, list):
        errors: list[str] = []
        for index, item in enumerate(value):
            errors.extend(_validate_json_value(item, f"{field}[{index}]"))
        return errors
    if isinstance(value, dict):
        errors = []
        for key, item in value.items():
            if not isinstance(key, str):
                errors.append(f"{field} object keys must be strings")
                continue
            errors.extend(_validate_json_value(item, f"{field}.{key}"))
        return errors
    return [f"{field} contains a non-JSON value of type {type(value).__name__}"]


def validate_manifest_data(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["manifest must be a JSON object"]
    missing = REQUIRED_TOP_LEVEL - set(data)
    extra = set(data) - REQUIRED_TOP_LEVEL
    if missing:
        errors.append("missing top-level fields: " + ", ".join(sorted(missing)))
    if extra:
        errors.append("unknown top-level fields: " + ", ".join(sorted(extra)))
    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    record_id = data.get("record_id")
    try:
        uuid.UUID(str(record_id))
    except (ValueError, TypeError, AttributeError):
        errors.append("record_id must be a UUID")
    try:
        timestamp = datetime.fromisoformat(str(data.get("created_at")).replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            errors.append("created_at must include a timezone")
    except ValueError:
        errors.append("created_at must be an RFC 3339 timestamp")
    if not _is_digest(data.get(MANIFEST_HASH_FIELD)):
        errors.append(f"{MANIFEST_HASH_FIELD} must be a lowercase SHA-256 hex digest")
    if data.get("generation_mode") not in GENERATION_MODES:
        errors.append("generation_mode is invalid")
    if data.get("endpoint_class") not in ENDPOINT_CLASSES:
        errors.append("endpoint_class is invalid")
    for field in (
        "provider",
        "model_requested",
        "model_returned",
        "runtime",
        "human_edit_description",
    ):
        if data.get(field) is not None and not isinstance(data.get(field), str):
            errors.append(f"{field} must be a string or null")
    errors.extend(_validate_file_record(data.get("prompt"), "prompt"))
    errors.extend(_validate_file_record(data.get("output"), "output"))
    runtime_receipt = data.get("runtime_receipt")
    if runtime_receipt is not None:
        errors.extend(_validate_file_record(runtime_receipt, "runtime_receipt"))
    if data.get("generation_mode") == "local_open_weight" and runtime_receipt is None:
        errors.append("runtime_receipt is required for local_open_weight generation")
    sources = data.get("sources")
    if not isinstance(sources, list):
        errors.append("sources must be an array")
    else:
        for index, source in enumerate(sources):
            errors.extend(_validate_file_record(source, f"sources[{index}]"))
    parameters = data.get("parameters")
    if not isinstance(parameters, dict):
        errors.append("parameters must be an object")
    else:
        errors.extend(_validate_json_value(parameters, "parameters"))
    parents = data.get("parents")
    if not isinstance(parents, list):
        errors.append("parents must be an array")
    else:
        seen_parent_ids: set[str] = set()
        for index, parent in enumerate(parents):
            errors.extend(_validate_parent_record(parent, f"parents[{index}]"))
            if isinstance(parent, dict) and isinstance(parent.get("record_id"), str):
                parent_id = parent["record_id"]
                if parent_id in seen_parent_ids:
                    errors.append(f"parents[{index}].record_id duplicates an earlier parent")
                seen_parent_ids.add(parent_id)
                if parent_id == record_id:
                    errors.append(f"parents[{index}].record_id must not equal record_id")
    audits = data.get("audits")
    if not isinstance(audits, list):
        errors.append("audits must be an array")
    else:
        required_audit = {
            "tool",
            "version",
            "kind",
            "result",
            "limitations",
            "optimization_used",
        }
        for index, audit in enumerate(audits):
            if not isinstance(audit, dict) or set(audit) != required_audit:
                errors.append(
                    f"audits[{index}] must contain exactly {', '.join(sorted(required_audit))}"
                )
                continue
            if audit.get("kind") not in AUDIT_KINDS:
                errors.append(f"audits[{index}].kind is invalid")
            if audit.get("optimization_used") is not False:
                errors.append(f"audits[{index}].optimization_used must be false")
            for field in ("tool", "version", "result", "limitations"):
                if not isinstance(audit.get(field), str) or not audit.get(field):
                    errors.append(f"audits[{index}].{field} must be a non-empty string")
    if not isinstance(data.get("notes"), list) or not all(
        isinstance(item, str) for item in data.get("notes", [])
    ):
        errors.append("notes must be an array of strings")
    if _is_digest(data.get(MANIFEST_HASH_FIELD)):
        try:
            expected_hash = manifest_sha256(data)
        except ManifestError as exc:
            errors.append(str(exc))
        else:
            if data[MANIFEST_HASH_FIELD] != expected_hash:
                errors.append(f"{MANIFEST_HASH_FIELD} does not match canonical manifest content")
    return errors


def _reject_nonstandard_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant is not allowed: {value}")


def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key is not allowed: {key}")
        result[key] = value
    return result


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=_reject_nonstandard_constant,
            object_pairs_hook=_object_without_duplicates,
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise ManifestError(f"cannot read manifest {path}: {exc}") from exc
    errors = validate_manifest_data(data)
    if errors:
        raise ManifestError("; ".join(errors))
    return data


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(
                data,
                handle,
                allow_nan=False,
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
            )
            handle.write("\n")
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def parse_parameters(values: Iterable[str]) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for value in values:
        if "=" not in value:
            raise ManifestError(f"parameter must be KEY=JSON_VALUE: {value}")
        key, raw = value.split("=", 1)
        if not key or key in parsed:
            raise ManifestError(f"invalid or duplicate parameter key: {key}")
        try:
            parsed[key] = json.loads(
                raw,
                parse_constant=_reject_nonstandard_constant,
                object_pairs_hook=_object_without_duplicates,
            )
        except json.JSONDecodeError:
            parsed[key] = raw
        except ValueError as exc:
            raise ManifestError(f"invalid JSON parameter {key}: {exc}") from exc
    return parsed


def parent_record(data: dict[str, Any]) -> dict[str, str]:
    """Create a path-free direct-parent link from a validated manifest."""

    errors = validate_manifest_data(data)
    if errors:
        raise ManifestError("cannot create parent record: " + "; ".join(errors))
    return {
        "record_id": data["record_id"],
        "manifest_sha256": data[MANIFEST_HASH_FIELD],
        "output_sha256": data["output"]["sha256"],
    }


def parent_records_from_paths(paths: Iterable[Path]) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for path in paths:
        record = parent_record(load_manifest(path))
        if record["record_id"] in seen:
            raise ManifestError(
                "duplicate parent record_id from explicitly supplied manifest: "
                + record["record_id"]
            )
        seen.add(record["record_id"])
        records.append(record)
    return records


def create_manifest(
    *,
    generation_mode: str,
    provider: str | None,
    model_requested: str | None,
    model_returned: str | None,
    runtime: str | None,
    endpoint_class: str,
    prompt_file: Path,
    output_file: Path,
    runtime_receipt_file: Path | None = None,
    source_files: list[Path] | None = None,
    parameters: dict[str, Any] | None = None,
    parents: list[dict[str, str]] | None = None,
    human_edit_description: str | None = None,
    audits: list[dict[str, Any]] | None = None,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "record_id": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        MANIFEST_HASH_FIELD: "",
        "generation_mode": generation_mode,
        "provider": provider,
        "model_requested": model_requested,
        "model_returned": model_returned,
        "runtime": runtime,
        "runtime_receipt": file_record(runtime_receipt_file) if runtime_receipt_file else None,
        "endpoint_class": endpoint_class,
        "prompt": file_record(prompt_file),
        "sources": [file_record(path) for path in (source_files or [])],
        "output": file_record(output_file),
        "parameters": parameters or {},
        "parents": parents or [],
        "human_edit_description": human_edit_description,
        "audits": audits or [],
        "notes": notes or [],
    }
    data = seal_manifest(data)
    errors = validate_manifest_data(data)
    if errors:
        raise ManifestError("; ".join(errors))
    return data


def _resolve_pointer(manifest_path: Path, pointer: str) -> Path:
    path = Path(pointer)
    return path if path.is_absolute() else manifest_path.parent / path


def verify_manifest_files(manifest_path: Path, data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    records: list[tuple[str, dict[str, Any]]] = [
        ("prompt", data["prompt"]),
        ("output", data["output"]),
    ]
    records.extend(
        (f"sources[{index}]", record) for index, record in enumerate(data["sources"])
    )
    if data["runtime_receipt"] is not None:
        records.append(("runtime_receipt", data["runtime_receipt"]))
    for label, record in records:
        path = _resolve_pointer(manifest_path, record["path"])
        if not path.is_file():
            errors.append(f"{label} missing: {path}")
            continue
        if path.stat().st_size != record["bytes"]:
            errors.append(f"{label} byte count mismatch: {path}")
        if sha256_file(path) != record["sha256"]:
            errors.append(f"{label} SHA-256 mismatch: {path}")
    return errors


def verify_parent_lineage(
    data: dict[str, Any],
    parent_manifest_paths: Iterable[Path],
) -> list[str]:
    """Verify direct-parent hashes using only explicitly supplied paths.

    Parent records contain no path. This function opens the explicit manifest
    arguments and never follows a path from child or parent manifest content.
    It also does not recurse into a parent's lineage or referenced output.
    """

    errors: list[str] = []
    expected = {record["record_id"]: record for record in data["parents"]}
    supplied: dict[str, dict[str, str]] = {}
    for path in parent_manifest_paths:
        try:
            observed = parent_record(load_manifest(path))
        except ManifestError as exc:
            errors.append(f"invalid explicitly supplied parent manifest {path}: {exc}")
            continue
        parent_id = observed["record_id"]
        if parent_id in supplied:
            errors.append(f"duplicate explicitly supplied parent record_id: {parent_id}")
            continue
        supplied[parent_id] = observed
    for parent_id, expected_record in expected.items():
        observed = supplied.get(parent_id)
        if observed is None:
            errors.append(f"parent manifest not explicitly supplied for record_id: {parent_id}")
            continue
        if observed["manifest_sha256"] != expected_record["manifest_sha256"]:
            errors.append(f"parent manifest SHA-256 mismatch for record_id: {parent_id}")
        if observed["output_sha256"] != expected_record["output_sha256"]:
            errors.append(f"parent output SHA-256 mismatch for record_id: {parent_id}")
    for parent_id in supplied.keys() - expected.keys():
        errors.append(f"unreferenced parent manifest explicitly supplied for record_id: {parent_id}")
    return errors


def command_create(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest)
    evidence_paths = [
        Path(args.prompt_file),
        Path(args.output_file),
        *(Path(path) for path in args.source_file),
        *(Path(path) for path in args.parent_manifest),
    ]
    if args.runtime_receipt:
        evidence_paths.append(Path(args.runtime_receipt))
    if any(manifest_path.resolve() == path.resolve() for path in evidence_paths):
        raise ManifestError("manifest path must differ from every evidence input path")
    data = create_manifest(
        generation_mode=args.generation_mode,
        provider=args.provider,
        model_requested=args.model,
        model_returned=args.model_returned,
        runtime=args.runtime,
        runtime_receipt_file=Path(args.runtime_receipt) if args.runtime_receipt else None,
        endpoint_class=args.endpoint_class,
        prompt_file=Path(args.prompt_file),
        output_file=Path(args.output_file),
        source_files=[Path(path) for path in args.source_file],
        parameters=parse_parameters(args.parameter),
        parents=parent_records_from_paths(Path(path) for path in args.parent_manifest),
        human_edit_description=args.human_edit_description,
        notes=args.note,
    )
    atomic_write_json(manifest_path, data)
    print(f"created canonical self-hashed schema-{SCHEMA_VERSION} manifest: {args.manifest}")
    return 0


def command_validate(args: argparse.Namespace) -> int:
    data = load_manifest(Path(args.manifest))
    print(
        f"valid canonical self-hashed schema-{data['schema_version']} manifest: "
        f"{args.manifest}"
    )
    return 0


def command_verify(args: argparse.Namespace) -> int:
    path = Path(args.manifest)
    data = load_manifest(path)
    errors = verify_manifest_files(path, data)
    errors.extend(
        verify_parent_lineage(data, (Path(parent) for parent in args.parent_manifest))
    )
    if errors:
        raise ManifestError("; ".join(errors))
    file_count = 2 + len(data["sources"]) + (1 if data["runtime_receipt"] is not None else 0)
    print(
        f"manifest self-hash, {file_count} referenced file(s), and "
        f"{len(data['parents'])} direct parent link(s) verified: {args.manifest}"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create", help="create a manifest from existing files")
    create.add_argument("--generation-mode", choices=sorted(GENERATION_MODES), required=True)
    create.add_argument("--provider")
    create.add_argument("--model")
    create.add_argument("--model-returned")
    create.add_argument("--runtime")
    create.add_argument("--runtime-receipt")
    create.add_argument("--endpoint-class", choices=sorted(ENDPOINT_CLASSES), default="unknown")
    create.add_argument("--prompt-file", required=True)
    create.add_argument("--output-file", required=True)
    create.add_argument("--source-file", action="append", default=[])
    create.add_argument("--parameter", action="append", default=[], metavar="KEY=JSON_VALUE")
    create.add_argument("--parent-manifest", action="append", default=[])
    create.add_argument("--human-edit-description")
    create.add_argument("--note", action="append", default=[])
    create.add_argument("--manifest", required=True)
    create.set_defaults(function=command_create)
    validate = subparsers.add_parser("validate", help="validate schema, semantics, and self-hash")
    validate.add_argument("manifest")
    validate.set_defaults(function=command_validate)
    verify = subparsers.add_parser("verify", help="validate and recompute all available hashes")
    verify.add_argument("manifest")
    verify.add_argument(
        "--parent-manifest",
        action="append",
        default=[],
        help="explicit direct-parent manifest; required once for each recorded parent",
    )
    verify.set_defaults(function=command_verify)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.function(args)
    except ManifestError as exc:
        print(f"provenance manifest error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

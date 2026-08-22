#!/usr/bin/env python3
"""Create, validate, and verify a text-provenance manifest.

This tool records hashes and lineage. It does not establish authorship or the
absence of a provider watermark.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = 1
GENERATION_MODES = {"human", "hosted", "local_open_weight", "mixed", "unknown"}
ENDPOINT_CLASSES = {"none", "hosted", "local_loopback", "local_lan", "unknown"}
AUDIT_KINDS = {"text_integrity", "provider_detector", "standards_detector", "other"}
REQUIRED_TOP_LEVEL = {
    "schema_version",
    "record_id",
    "created_at",
    "generation_mode",
    "provider",
    "model_requested",
    "model_returned",
    "runtime",
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


def _validate_file_record(value: Any, field: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return [f"{field} must be an object"]
    if set(value) != {"path", "sha256", "bytes"}:
        errors.append(f"{field} must contain exactly path, sha256, and bytes")
    if not isinstance(value.get("path"), str) or not value.get("path"):
        errors.append(f"{field}.path must be a non-empty string")
    digest = value.get("sha256")
    if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        errors.append(f"{field}.sha256 must be a lowercase SHA-256 hex digest")
    if not isinstance(value.get("bytes"), int) or value.get("bytes", -1) < 0:
        errors.append(f"{field}.bytes must be a non-negative integer")
    return errors


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
    try:
        uuid.UUID(str(data.get("record_id")))
    except (ValueError, TypeError, AttributeError):
        errors.append("record_id must be a UUID")
    try:
        timestamp = datetime.fromisoformat(str(data.get("created_at")).replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            errors.append("created_at must include a timezone")
    except ValueError:
        errors.append("created_at must be an RFC 3339 timestamp")
    if data.get("generation_mode") not in GENERATION_MODES:
        errors.append("generation_mode is invalid")
    if data.get("endpoint_class") not in ENDPOINT_CLASSES:
        errors.append("endpoint_class is invalid")
    for field in ("provider", "model_requested", "model_returned", "runtime", "human_edit_description"):
        if data.get(field) is not None and not isinstance(data.get(field), str):
            errors.append(f"{field} must be a string or null")
    errors.extend(_validate_file_record(data.get("prompt"), "prompt"))
    errors.extend(_validate_file_record(data.get("output"), "output"))
    sources = data.get("sources")
    if not isinstance(sources, list):
        errors.append("sources must be an array")
    else:
        for index, source in enumerate(sources):
            errors.extend(_validate_file_record(source, f"sources[{index}]"))
    if not isinstance(data.get("parameters"), dict):
        errors.append("parameters must be an object")
    parents = data.get("parents")
    if not isinstance(parents, list) or not all(isinstance(item, str) and item for item in parents):
        errors.append("parents must be an array of non-empty strings")
    audits = data.get("audits")
    if not isinstance(audits, list):
        errors.append("audits must be an array")
    else:
        required_audit = {"tool", "version", "kind", "result", "limitations", "optimization_used"}
        for index, audit in enumerate(audits):
            if not isinstance(audit, dict) or set(audit) != required_audit:
                errors.append(f"audits[{index}] must contain exactly {', '.join(sorted(required_audit))}")
                continue
            if audit.get("kind") not in AUDIT_KINDS:
                errors.append(f"audits[{index}].kind is invalid")
            if audit.get("optimization_used") is not False:
                errors.append(f"audits[{index}].optimization_used must be false")
            for field in ("tool", "version", "result", "limitations"):
                if not isinstance(audit.get(field), str) or not audit.get(field):
                    errors.append(f"audits[{index}].{field} must be a non-empty string")
    if not isinstance(data.get("notes"), list) or not all(isinstance(item, str) for item in data.get("notes", [])):
        errors.append("notes must be an array of strings")
    return errors


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
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
            json.dump(data, handle, indent=2, sort_keys=True, ensure_ascii=False)
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
            parsed[key] = json.loads(raw)
        except json.JSONDecodeError:
            parsed[key] = raw
    return parsed


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
    source_files: list[Path] | None = None,
    parameters: dict[str, Any] | None = None,
    parents: list[str] | None = None,
    human_edit_description: str | None = None,
    audits: list[dict[str, Any]] | None = None,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "record_id": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "generation_mode": generation_mode,
        "provider": provider,
        "model_requested": model_requested,
        "model_returned": model_returned,
        "runtime": runtime,
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
    errors = validate_manifest_data(data)
    if errors:
        raise ManifestError("; ".join(errors))
    return data


def _resolve_pointer(manifest_path: Path, pointer: str) -> Path:
    path = Path(pointer)
    return path if path.is_absolute() else manifest_path.parent / path


def verify_manifest_files(manifest_path: Path, data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    records = [("prompt", data["prompt"]), ("output", data["output"])]
    records.extend((f"sources[{index}]", record) for index, record in enumerate(data["sources"]))
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


def command_create(args: argparse.Namespace) -> int:
    data = create_manifest(
        generation_mode=args.generation_mode,
        provider=args.provider,
        model_requested=args.model,
        model_returned=args.model_returned,
        runtime=args.runtime,
        endpoint_class=args.endpoint_class,
        prompt_file=Path(args.prompt_file),
        output_file=Path(args.output_file),
        source_files=[Path(path) for path in args.source_file],
        parameters=parse_parameters(args.parameter),
        parents=args.parent,
        human_edit_description=args.human_edit_description,
        notes=args.note,
    )
    atomic_write_json(Path(args.manifest), data)
    print(f"created valid schema-{SCHEMA_VERSION} manifest: {args.manifest}")
    return 0


def command_validate(args: argparse.Namespace) -> int:
    data = load_manifest(Path(args.manifest))
    print(f"valid schema-{data['schema_version']} manifest: {args.manifest}")
    return 0


def command_verify(args: argparse.Namespace) -> int:
    path = Path(args.manifest)
    data = load_manifest(path)
    errors = verify_manifest_files(path, data)
    if errors:
        raise ManifestError("; ".join(errors))
    print(f"manifest and {2 + len(data['sources'])} referenced file(s) verified: {args.manifest}")
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
    create.add_argument("--endpoint-class", choices=sorted(ENDPOINT_CLASSES), default="unknown")
    create.add_argument("--prompt-file", required=True)
    create.add_argument("--output-file", required=True)
    create.add_argument("--source-file", action="append", default=[])
    create.add_argument("--parameter", action="append", default=[], metavar="KEY=JSON_VALUE")
    create.add_argument("--parent", action="append", default=[])
    create.add_argument("--human-edit-description")
    create.add_argument("--note", action="append", default=[])
    create.add_argument("--manifest", required=True)
    create.set_defaults(function=command_create)
    validate = subparsers.add_parser("validate", help="validate schema and semantics")
    validate.add_argument("manifest")
    validate.set_defaults(function=command_validate)
    verify = subparsers.add_parser("verify", help="validate and recompute referenced file hashes")
    verify.add_argument("manifest")
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

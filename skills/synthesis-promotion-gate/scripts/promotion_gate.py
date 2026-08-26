#!/usr/bin/env python3
"""Render, inspect, and enforce a publication promotion boundary.

A successful build is not a publication-safety signal. ``check`` produces an
acceptance-test receipt and never authorizes a state change. ``enforce`` keeps the
captured rendered bytes alive in a separate content snapshot, revalidates the exact
inputs and snapshot immediately before the supplied promotion command, and invokes
that command only after every declared representation is clean. Only that fail-closed
caller can issue an ``enforced-gate`` receipt.

This engine detects configured promotion scaffolding. It does not decide whether
ordinary prose is appropriate to disclose, prove that a surface manifest names an
unknown consumer, or establish the bytes at a remote destination after the supplied
command returns. Each receipt names that remainder.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import fnmatch
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass
from typing import Any, Iterable

import yaml


SCHEMA = 1
CONTROL_CLASSES = {"diagnostic", "acceptance-test", "enforced-gate"}
DESTINATION_REPRESENTATIONS = {
    "dom-text",
    "dom-heading-text",
    "html-comments",
    "raw-page-source",
}
AUXILIARY_REPRESENTATIONS = {"publishable-source", "sidecar-flags"}
REPRESENTATIONS = DESTINATION_REPRESENTATIONS | AUXILIARY_REPRESENTATIONS

CONFIG_KEYS = {
    "schema",
    "build",
    "inputs",
    "publishable_range",
    "marker_policy",
    "surface_manifest",
    "acceptance_suite",
    "inspected_surfaces",
    "sidecar_flag_globs",
    "additional_unverified_remainder",
    "destination_projection",
}
BUILD_KEYS = {"command", "working_directory", "output_root"}
INPUT_KEYS = {"root", "globs"}
RANGE_KEYS = {"start", "end", "required"}
SURFACE_KEYS = {"renderer", "representations"}
DESTINATION_PROJECTION_KEYS = {"command", "working_directory", "expected_identity"}
DESTINATION_IDENTITY_KEYS = {"parser", "parser_version", "renderer"}
RENDERER_KEYS = {
    "id",
    "version",
    "input_globs",
    "route_template",
    "output_prefix",
}
ACCEPTANCE_KEYS = {
    "schema",
    "suite",
    "membership",
    "production_entry_point",
    "enforcing_boundary",
    "receipt_consumer",
    "expected_status",
    "unverified_remainder",
    "cases",
}
ACCEPTANCE_CASE_KEYS = {"id", "control_class", "fixture", "motivating_defect"}
ENGINE_UNVERIFIED_REMAINDER = [
    "consumers absent from the declared surface manifest",
    "semantic disclosures outside the canonical marker policy",
    "destination bytes after the supplied promotion command returns",
    "destination parser equivalence beyond the declared representations",
]
EMPTY_REMAINDER_CLAIMS = {
    "none",
    "n/a",
    "na",
    "nothing",
    "fully verified",
    "no remainder",
}


class GateError(RuntimeError):
    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind
        self.message = message


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    return sha256_bytes(path.read_bytes())


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise GateError("invalid-config", f"{label} must be a mapping")
    return value


def require_keys(value: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise GateError("invalid-config", f"{label} has unknown keys: {', '.join(unknown)}")


def require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GateError("invalid-config", f"{label} must be a non-empty string")
    return value


def require_string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not value or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise GateError("invalid-config", f"{label} must be a non-empty list of strings")
    return value


def require_optional_string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) for item in value
    ):
        raise GateError("destination-projection-invalid", f"{label} must be a list of strings")
    return value


def yaml_document(path: pathlib.Path, label: str) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise GateError("unreadable-config", f"cannot read {label} {path}: {exc}") from exc
    return require_mapping(value, label)


def no_symlink_components(path: pathlib.Path, stop: pathlib.Path) -> None:
    current = path
    stop = stop.resolve()
    while True:
        if current.is_symlink():
            raise GateError("symlink-path", f"symlinked path component is refused: {current}")
        if current.resolve(strict=False) == stop:
            return
        if current.parent == current:
            raise GateError("path-outside-project", f"path is outside project root: {path}")
        current = current.parent


def project_path(
    project_root: pathlib.Path,
    value: Any,
    label: str,
    *,
    must_exist: bool = True,
    file_only: bool = False,
) -> pathlib.Path:
    raw = pathlib.Path(require_string(value, label))
    if raw.is_absolute():
        raise GateError("path-outside-project", f"{label} must be relative to the project root")
    candidate = project_root / raw
    resolved_root = project_root.resolve()
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise GateError("path-outside-project", f"{label} escapes the project root: {raw}") from exc
    no_symlink_components(candidate, project_root)
    if must_exist and not candidate.exists():
        raise GateError("missing-path", f"{label} does not exist: {candidate}")
    if file_only and not candidate.is_file():
        raise GateError("missing-path", f"{label} is not a regular file: {candidate}")
    return candidate


def load_config(path: pathlib.Path) -> tuple[pathlib.Path, dict[str, Any]]:
    if path.is_symlink() or not path.is_file():
        raise GateError("unreadable-config", f"config is not a regular non-symlink file: {path}")
    config = yaml_document(path, "promotion gate config")
    require_keys(config, CONFIG_KEYS, "promotion gate config")
    if config.get("schema") != SCHEMA:
        raise GateError("invalid-config", f"config schema must be {SCHEMA}")
    project_root = path.parent.parent if path.parent.name == ".agents" else path.parent
    project_root = project_root.resolve()

    build = require_mapping(config.get("build"), "build")
    require_keys(build, BUILD_KEYS, "build")
    command = require_string_list(build.get("command"), "build.command")
    if "{output_root}" not in command:
        raise GateError(
            "invalid-config",
            "build.command must carry the literal {output_root} argument so isolated output is explicit",
        )
    project_path(project_root, build.get("working_directory"), "build.working_directory")
    logical_output = pathlib.PurePosixPath(require_string(build.get("output_root"), "build.output_root"))
    if logical_output.is_absolute() or ".." in logical_output.parts:
        raise GateError("invalid-config", "build.output_root must be a safe relative path")

    inputs = require_mapping(config.get("inputs"), "inputs")
    require_keys(inputs, INPUT_KEYS, "inputs")
    project_path(project_root, inputs.get("root"), "inputs.root")
    require_string_list(inputs.get("globs"), "inputs.globs")

    projection = require_mapping(
        config.get("destination_projection"), "destination_projection"
    )
    require_keys(projection, DESTINATION_PROJECTION_KEYS, "destination_projection")
    if set(projection) != DESTINATION_PROJECTION_KEYS:
        raise GateError("invalid-config", "every destination_projection field is required")
    projection_command = require_string_list(
        projection.get("command"), "destination_projection.command"
    )
    if any("{" in argument or "}" in argument for argument in projection_command):
        raise GateError(
            "invalid-config",
            "destination_projection.command receives JSON on stdin and cannot contain substitutions",
        )
    project_path(
        project_root,
        projection.get("working_directory"),
        "destination_projection.working_directory",
    )
    identity = require_mapping(
        projection.get("expected_identity"),
        "destination_projection.expected_identity",
    )
    if set(identity) != DESTINATION_IDENTITY_KEYS:
        raise GateError(
            "invalid-config",
            "destination_projection.expected_identity must declare parser, parser_version, and renderer",
        )
    for key in sorted(DESTINATION_IDENTITY_KEYS):
        require_string(identity.get(key), f"destination_projection.expected_identity.{key}")

    range_config = require_mapping(config.get("publishable_range"), "publishable_range")
    require_keys(range_config, RANGE_KEYS, "publishable_range")
    start = require_string(range_config.get("start"), "publishable_range.start")
    end = require_string(range_config.get("end"), "publishable_range.end")
    if start == end:
        raise GateError("invalid-config", "publishable range start and end must differ")
    if range_config.get("required") is not True:
        raise GateError("invalid-config", "publishable_range.required must be true")

    for key in ("marker_policy", "surface_manifest", "acceptance_suite"):
        project_path(project_root, config.get(key), key, file_only=True)
    remainder = require_string_list(
        config.get("additional_unverified_remainder"),
        "additional_unverified_remainder",
    )
    if any(item.strip().casefold() in EMPTY_REMAINDER_CLAIMS for item in remainder):
        raise GateError(
            "invalid-config",
            "additional_unverified_remainder cannot erase or deny the engine-owned remainder",
        )
    if not isinstance(config.get("sidecar_flag_globs"), list) or not all(
        isinstance(item, str) and item for item in config["sidecar_flag_globs"]
    ):
        raise GateError("invalid-config", "sidecar_flag_globs must be a list of strings")
    return project_root, config


@dataclass(frozen=True)
class Marker:
    marker_id: str
    projections: dict[str, re.Pattern[str]]


def load_policy(project_root: pathlib.Path, config: dict[str, Any]) -> tuple[pathlib.Path, list[Marker]]:
    path = project_path(project_root, config["marker_policy"], "marker_policy", file_only=True)
    policy = yaml_document(path, "marker policy")
    if set(policy) != {"schema", "markers"} or policy.get("schema") != SCHEMA:
        raise GateError("invalid-marker-policy", "marker policy must contain schema 1 and markers")
    entries = policy.get("markers")
    if not isinstance(entries, list) or not entries:
        raise GateError("invalid-marker-policy", "marker policy markers must be a non-empty list")
    seen: set[str] = set()
    markers: list[Marker] = []
    required = {
        "id",
        "threat_rationale",
        "provenance",
        "positive_examples",
        "negative_examples",
        "projections",
    }
    for index, raw in enumerate(entries):
        item = require_mapping(raw, f"marker {index}")
        if set(item) != required:
            missing = sorted(required - set(item))
            extra = sorted(set(item) - required)
            raise GateError(
                "invalid-marker-policy",
                f"marker {index} schema mismatch; missing={missing}, extra={extra}",
            )
        marker_id = require_string(item["id"], f"marker {index}.id")
        if marker_id in seen:
            raise GateError("invalid-marker-policy", f"duplicate marker id: {marker_id}")
        seen.add(marker_id)
        require_string(item["threat_rationale"], f"marker {marker_id}.threat_rationale")
        require_string(item["provenance"], f"marker {marker_id}.provenance")
        positive_examples = require_string_list(
            item["positive_examples"], f"marker {marker_id}.positive_examples"
        )
        negative_examples = require_string_list(
            item["negative_examples"], f"marker {marker_id}.negative_examples"
        )
        raw_projections = require_mapping(item["projections"], f"marker {marker_id}.projections")
        if not raw_projections:
            raise GateError("invalid-marker-policy", f"marker {marker_id} has no projections")
        projections: dict[str, re.Pattern[str]] = {}
        for representation, raw_projection in raw_projections.items():
            if representation not in REPRESENTATIONS:
                raise GateError(
                    "invalid-marker-policy",
                    f"marker {marker_id} names unknown representation {representation}",
                )
            projection = require_mapping(
                raw_projection, f"marker {marker_id}.{representation}"
            )
            if set(projection) != {"pattern"}:
                raise GateError(
                    "invalid-marker-policy",
                    f"marker {marker_id}.{representation} must contain only pattern",
                )
            pattern = require_string(
                projection["pattern"], f"marker {marker_id}.{representation}.pattern"
            )
            try:
                compiled = re.compile(pattern, re.IGNORECASE | re.DOTALL)
            except re.error as exc:
                raise GateError(
                    "invalid-marker-policy",
                    f"marker {marker_id}.{representation} has invalid regex: {exc}",
                ) from exc
            if not any(compiled.search(example) for example in positive_examples):
                raise GateError(
                    "invalid-marker-policy",
                    f"marker {marker_id}.{representation} matches no canonical positive example",
                )
            if any(compiled.search(example) for example in negative_examples):
                raise GateError(
                    "invalid-marker-policy",
                    f"marker {marker_id}.{representation} matches a canonical negative example",
                )
            projections[representation] = compiled
        markers.append(Marker(marker_id, projections))
    return path, markers


def load_acceptance(project_root: pathlib.Path, config: dict[str, Any]) -> pathlib.Path:
    path = project_path(project_root, config["acceptance_suite"], "acceptance_suite", file_only=True)
    manifest = yaml_document(path, "acceptance suite")
    if set(manifest) != ACCEPTANCE_KEYS:
        missing = sorted(ACCEPTANCE_KEYS - set(manifest))
        extra = sorted(set(manifest) - ACCEPTANCE_KEYS)
        raise GateError(
            "invalid-acceptance-suite",
            f"acceptance suite schema mismatch; missing={missing}, extra={extra}",
        )
    if manifest.get("schema") != SCHEMA or manifest.get("membership") != "closed":
        raise GateError(
            "invalid-acceptance-suite",
            "acceptance suite must declare schema 1 and closed membership",
        )
    for key in (
        "suite",
        "production_entry_point",
        "enforcing_boundary",
        "receipt_consumer",
        "unverified_remainder",
    ):
        require_string(manifest.get(key), f"acceptance suite {key}")
    if manifest.get("expected_status") != "pass":
        raise GateError("invalid-acceptance-suite", "acceptance suite expected_status must be pass")
    cases = manifest.get("cases")
    if not isinstance(cases, list) or not cases:
        raise GateError("invalid-acceptance-suite", "acceptance suite must contain cases")
    case_ids: set[str] = set()
    for case in cases:
        value = require_mapping(case, "acceptance case")
        if set(value) != ACCEPTANCE_CASE_KEYS:
            raise GateError(
                "invalid-acceptance-suite",
                "each acceptance case must declare id, control_class, fixture, and motivating_defect",
            )
        case_id = require_string(value.get("id"), "acceptance case id")
        if case_id in case_ids:
            raise GateError("invalid-acceptance-suite", f"duplicate acceptance case id: {case_id}")
        case_ids.add(case_id)
        require_string(value.get("fixture"), f"acceptance case {case_id} fixture")
        require_string(
            value.get("motivating_defect"),
            f"acceptance case {case_id} motivating_defect",
        )
        if value.get("control_class") not in CONTROL_CLASSES:
            raise GateError("invalid-acceptance-suite", "acceptance case has unknown control_class")
    return path


def load_surfaces(
    project_root: pathlib.Path, config: dict[str, Any]
) -> tuple[pathlib.Path, list[dict[str, Any]], dict[str, list[str]]]:
    path = project_path(project_root, config["surface_manifest"], "surface_manifest", file_only=True)
    manifest = yaml_document(path, "surface manifest")
    if set(manifest) != {"schema", "renderers"} or manifest.get("schema") != SCHEMA:
        raise GateError("invalid-surface-manifest", "surface manifest must contain schema 1 and renderers")
    raw_renderers = manifest.get("renderers")
    if not isinstance(raw_renderers, list) or not raw_renderers:
        raise GateError("invalid-surface-manifest", "surface manifest renderers must be non-empty")
    renderers: list[dict[str, Any]] = []
    ids: set[str] = set()
    for raw in raw_renderers:
        renderer = require_mapping(raw, "renderer")
        require_keys(renderer, RENDERER_KEYS, "renderer")
        if set(renderer) != RENDERER_KEYS:
            raise GateError("invalid-surface-manifest", "every renderer field is required")
        renderer_id = require_string(renderer["id"], "renderer.id")
        if renderer_id in ids:
            raise GateError("invalid-surface-manifest", f"duplicate renderer id: {renderer_id}")
        ids.add(renderer_id)
        require_string(renderer["version"], f"renderer {renderer_id}.version")
        require_string_list(renderer["input_globs"], f"renderer {renderer_id}.input_globs")
        require_string(renderer["route_template"], f"renderer {renderer_id}.route_template")
        output_prefix = pathlib.PurePosixPath(str(renderer["output_prefix"]))
        if output_prefix.is_absolute() or ".." in output_prefix.parts:
            raise GateError("invalid-surface-manifest", f"renderer {renderer_id} output_prefix is unsafe")
        renderers.append(renderer)

    raw_inspections = config.get("inspected_surfaces")
    if not isinstance(raw_inspections, list) or not raw_inspections:
        raise GateError("invalid-config", "inspected_surfaces must be a non-empty list")
    inspections: dict[str, list[str]] = {}
    for raw in raw_inspections:
        inspection = require_mapping(raw, "inspected surface")
        require_keys(inspection, SURFACE_KEYS, "inspected surface")
        if set(inspection) != SURFACE_KEYS:
            raise GateError("invalid-config", "every inspected surface field is required")
        renderer_id = require_string(inspection["renderer"], "inspected surface renderer")
        if renderer_id in inspections:
            raise GateError("invalid-config", f"duplicate inspected renderer: {renderer_id}")
        representations = require_string_list(
            inspection["representations"], f"inspected surface {renderer_id}.representations"
        )
        unknown = sorted(set(representations) - (DESTINATION_REPRESENTATIONS | {"publishable-source"}))
        if unknown:
            raise GateError("invalid-config", f"unknown inspected representations: {', '.join(unknown)}")
        if not set(representations) & DESTINATION_REPRESENTATIONS:
            raise GateError("invalid-config", f"renderer {renderer_id} has no destination representation")
        inspections[renderer_id] = representations
    if set(inspections) != ids:
        missing = sorted(ids - set(inspections))
        extra = sorted(set(inspections) - ids)
        raise GateError(
            "surface-manifest-mismatch",
            f"surface manifest and inspected surfaces disagree; missing={missing}, extra={extra}",
        )
    return path, renderers, inspections


@dataclass
class InputArtifact:
    path: pathlib.Path
    relative_path: str
    source_sha256: str
    publishable_sha256: str
    publishable: str
    frontmatter: dict[str, Any]

    def receipt(self) -> dict[str, Any]:
        return {
            "path": self.relative_path,
            "source_sha256": self.source_sha256,
            "publishable_sha256": self.publishable_sha256,
            "frontmatter": self.frontmatter,
        }


def split_frontmatter(text: str, relative: str) -> tuple[dict[str, Any], str]:
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise GateError("invalid-input", f"{relative} has no YAML frontmatter")
    closing = next((index for index, line in enumerate(lines[1:], 1) if line.strip() == "---"), None)
    if closing is None:
        raise GateError("invalid-input", f"{relative} has unterminated YAML frontmatter")
    try:
        frontmatter = yaml.safe_load("".join(lines[1:closing])) or {}
    except yaml.YAMLError as exc:
        raise GateError("invalid-input", f"{relative} frontmatter is invalid YAML: {exc}") from exc
    if not isinstance(frontmatter, dict):
        raise GateError("invalid-input", f"{relative} frontmatter must be a mapping")
    return frontmatter, "".join(lines[closing + 1 :])


def extract_publishable(body: str, relative: str, range_config: dict[str, Any]) -> str:
    start, end = range_config["start"], range_config["end"]
    if body.count(start) != 1 or body.count(end) != 1:
        raise GateError(
            "publishable-range",
            f"{relative} must contain exactly one publishable start and end marker",
        )
    start_at = body.index(start) + len(start)
    end_at = body.index(end)
    if end_at <= start_at:
        raise GateError("publishable-range", f"{relative} publishable markers are reversed")
    return body[start_at:end_at]


def discover_inputs(project_root: pathlib.Path, config: dict[str, Any]) -> list[InputArtifact]:
    inputs = config["inputs"]
    input_root = project_path(project_root, inputs["root"], "inputs.root")
    found: set[pathlib.Path] = set()
    for pattern in inputs["globs"]:
        for path in input_root.glob(pattern):
            if path.is_file():
                no_symlink_components(path, project_root)
                found.add(path)
    if not found:
        raise GateError("empty-input-universe", "input globs matched no files")
    artifacts: list[InputArtifact] = []
    for path in sorted(found):
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise GateError("invalid-input", f"input is not UTF-8: {path}") from exc
        relative = path.relative_to(project_root).as_posix()
        frontmatter, body = split_frontmatter(text, relative)
        slug = frontmatter.get("slug")
        if not isinstance(slug, str) or not slug.strip():
            raise GateError("invalid-input", f"{relative} has no non-empty frontmatter slug")
        publishable = extract_publishable(body, relative, config["publishable_range"])
        artifacts.append(
            InputArtifact(
                path,
                relative,
                sha256_bytes(raw),
                sha256_bytes(publishable.encode("utf-8")),
                publishable,
                frontmatter,
            )
        )
    return artifacts


def matches_any(path: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def route_fields(frontmatter: dict[str, Any]) -> dict[str, str]:
    fields = {key: str(value) for key, value in frontmatter.items() if value is not None}
    raw_date = fields.get("date", "")
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})", raw_date)
    if match:
        fields.update(year=match.group(1), month=match.group(2), day=match.group(3))
    return fields


def safe_route(value: str, renderer_id: str) -> str:
    route = pathlib.PurePosixPath(value)
    if route.is_absolute() or ".." in route.parts or not route.parts:
        raise GateError("invalid-route", f"renderer {renderer_id} produced unsafe route {value!r}")
    return route.as_posix()


def expected_routes(
    inputs: list[InputArtifact], renderers: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    expected: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    used_outputs: dict[str, str] = {}
    for artifact in inputs:
        consumers = [
            renderer
            for renderer in renderers
            if matches_any(artifact.relative_path, renderer["input_globs"])
        ]
        if not consumers:
            findings.append(
                {
                    "kind": "unconsumed-input",
                    "path": artifact.relative_path,
                    "message": "input is not named by any consuming renderer",
                }
            )
            continue
        for renderer in consumers:
            renderer_id = renderer["id"]
            try:
                rendered = renderer["route_template"].format_map(route_fields(artifact.frontmatter))
            except KeyError as exc:
                raise GateError(
                    "invalid-route",
                    f"renderer {renderer_id} route requires absent frontmatter field {exc.args[0]}",
                ) from exc
            prefix = str(renderer["output_prefix"]).strip("/")
            route = safe_route("/".join(part for part in (prefix, rendered.strip("/")) if part), renderer_id)
            if route in used_outputs:
                findings.append(
                    {
                        "kind": "route-not-bijective",
                        "path": artifact.relative_path,
                        "route": route,
                        "message": f"route is already assigned to {used_outputs[route]}",
                    }
                )
                continue
            used_outputs[route] = artifact.relative_path
            expected.append(
                {
                    "renderer": renderer_id,
                    "renderer_version": renderer["version"],
                    "input": artifact.relative_path,
                    "route": route,
                }
            )
    return expected, findings


def representation_digest(values: list[str]) -> str:
    payload = json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(payload)


def project_destinations(
    command: list[str],
    working_directory: pathlib.Path,
    expected_identity: dict[str, str],
    documents: dict[str, str],
) -> tuple[dict[str, dict[str, list[str]]], dict[str, Any]]:
    """Consume destination-produced representations through the strict JSON protocol."""
    request = {
        "schema": SCHEMA,
        "documents": [
            {"route": route, "html": html}
            for route, html in sorted(documents.items())
        ],
    }
    try:
        projected = subprocess.run(
            command,
            cwd=working_directory,
            input=json.dumps(request, ensure_ascii=False),
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GateError(
            "destination-projection-failed",
            f"destination projection command could not complete: {type(exc).__name__}",
        ) from exc
    telemetry = {
        "exit_code": projected.returncode,
        "stdout_sha256": sha256_bytes(projected.stdout.encode("utf-8")),
        "stderr_sha256": sha256_bytes(projected.stderr.encode("utf-8")),
    }
    if projected.returncode != 0:
        raise GateError(
            "destination-projection-failed",
            f"destination projection command exited {projected.returncode}",
        )
    try:
        response = json.loads(projected.stdout)
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise GateError(
            "destination-projection-invalid",
            "destination projection command returned invalid JSON",
        ) from exc
    response = require_mapping(response, "destination projection response")
    if set(response) != {"schema", "identity", "documents"} or response.get("schema") != SCHEMA:
        raise GateError(
            "destination-projection-invalid",
            "destination projection response must contain schema 1, identity, and documents",
        )
    identity = require_mapping(response.get("identity"), "destination projection identity")
    if set(identity) != DESTINATION_IDENTITY_KEYS or not all(
        isinstance(identity.get(key), str) and identity[key].strip()
        for key in DESTINATION_IDENTITY_KEYS
    ):
        raise GateError(
            "destination-projection-invalid",
            "destination projection identity has an invalid shape",
        )
    if identity != expected_identity:
        raise GateError(
            "destination-projection-identity-mismatch",
            "destination projection identity differs from the configured identity",
        )
    raw_documents = response.get("documents")
    if not isinstance(raw_documents, list):
        raise GateError(
            "destination-projection-invalid",
            "destination projection documents must be a list",
        )
    by_route: dict[str, dict[str, list[str]]] = {}
    projected_representations = DESTINATION_REPRESENTATIONS - {"raw-page-source"}
    for index, raw_document in enumerate(raw_documents):
        document = require_mapping(raw_document, f"destination projection document {index}")
        if set(document) != {"route", "representations"}:
            raise GateError(
                "destination-projection-invalid",
                "each projected document must contain route and representations",
            )
        route = require_string(document.get("route"), "projected document route")
        if route in by_route:
            raise GateError(
                "destination-projection-invalid",
                f"destination projection duplicated route {route}",
            )
        representations = require_mapping(
            document.get("representations"),
            f"destination projection representations for {route}",
        )
        if set(representations) != projected_representations:
            raise GateError(
                "destination-projection-invalid",
                f"destination projection for {route} has an incomplete representation set",
            )
        by_route[route] = {
            name: require_optional_string_list(values, f"{route}.{name}")
            for name, values in representations.items()
        }
    if set(by_route) != set(documents):
        raise GateError(
            "destination-projection-invalid",
            "destination projection route universe differs from the captured output universe",
        )
    telemetry["identity"] = identity
    return by_route, telemetry


def marker_findings(
    markers: list[Marker],
    representation: str,
    values: Iterable[str],
    *,
    path: str,
    renderer: str | None = None,
    route: str | None = None,
) -> list[dict[str, Any]]:
    values = list(values)
    findings: list[dict[str, Any]] = []
    for marker in markers:
        pattern = marker.projections.get(representation)
        if pattern is None:
            continue
        match = next((pattern.search(value) for value in values if pattern.search(value)), None)
        if match is None:
            continue
        finding: dict[str, Any] = {
            "kind": "marker-hit",
            "marker_id": marker.marker_id,
            "representation": representation,
            "path": path,
            "evidence_sha256": sha256_bytes(match.group(0).encode("utf-8")),
            "message": "configured marker matched; content is withheld from the receipt",
        }
        if renderer is not None:
            finding["renderer"] = renderer
        if route is not None:
            finding["route"] = route
        findings.append(finding)
    return findings


def sidecar_paths(project_root: pathlib.Path, config: dict[str, Any]) -> list[pathlib.Path]:
    found: set[pathlib.Path] = set()
    for pattern in config["sidecar_flag_globs"]:
        for path in project_root.glob(pattern):
            if path.is_file():
                no_symlink_components(path, project_root)
                found.add(path)
    return sorted(found)


def file_identities(project_root: pathlib.Path, paths: Iterable[pathlib.Path]) -> list[dict[str, str]]:
    return [
        {"path": path.relative_to(project_root).as_posix(), "sha256": sha256_file(path)}
        for path in sorted(set(paths))
    ]


def command_identity(working_directory: pathlib.Path, command: list[str]) -> list[dict[str, str]]:
    identities: list[dict[str, str]] = []
    for argument in command:
        if "{" in argument:
            continue
        candidate = pathlib.Path(argument)
        if not candidate.is_absolute():
            candidate = working_directory / candidate
        if candidate.is_file():
            identities.append({"argument": argument, "sha256": sha256_file(candidate)})
    return identities


def atomic_json(path: pathlib.Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise GateError("symlink-path", f"receipt target is a symlink: {path}")
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        if path.read_bytes() != payload:
            raise GateError("receipt-write", f"receipt read-back failed: {path}")
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def base_receipt(mode: str, config_path: pathlib.Path) -> dict[str, Any]:
    enforce = mode == "enforce"
    return {
        "schema": SCHEMA,
        "invocation_id": str(uuid.uuid4()),
        "created_at": utc_now(),
        "status": "refused",
        "metadata_class": "enforced-gate" if enforce else "acceptance-test",
        "authority_receipt": False,
        "config": {"path": str(config_path)},
        "policy": {},
        "surface_manifest": {},
        "acceptance_suite": {},
        "destination_projection": {},
        "build": {"exit_code": None},
        "inputs": [],
        "sidecars": [],
        "route_bijection": {"expected": [], "inspected": [], "missing": []},
        "findings": [],
        "promotion": {"attempted": False, "exit_code": None},
        "topology": (
            {
                "production_entry_point": "promotion_gate.py enforce",
                "enforcing_boundary": "before the supplied promotion command",
                "receipt_consumer": "built-in candidate revalidation plus supplied command",
            }
            if enforce
            else {
                "production_entry_point": "promotion_gate.py check",
                "enforcing_boundary": "none; check cannot invoke a promotion command",
                "receipt_consumer": "none",
            }
        ),
        "unverified_remainder": {
            "engine_owned": list(ENGINE_UNVERIFIED_REMAINDER),
            "repository_declared": [],
        },
    }


def add_fatal(receipt: dict[str, Any], error: GateError) -> None:
    receipt["findings"].append(
        {"kind": error.kind, "path": receipt["config"]["path"], "message": error.message}
    )


def substitute(command: list[str], values: dict[str, str]) -> list[str]:
    result: list[str] = []
    for argument in command:
        rendered = argument
        for name, value in values.items():
            rendered = rendered.replace("{" + name + "}", value)
        result.append(rendered)
    return result


def output_identities(output_root: pathlib.Path, expected: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {"route": item["route"], "sha256": sha256_file(output_root / item["route"])}
        for item in expected
        if (output_root / item["route"]).is_file()
    ]


def captured_output_identities(captured: dict[str, bytes]) -> list[dict[str, str]]:
    return [
        {"route": route, "sha256": sha256_bytes(payload)}
        for route, payload in sorted(captured.items())
    ]


def current_contract_identities(
    project_root: pathlib.Path,
    config_path: pathlib.Path,
    linked: list[pathlib.Path],
    inputs: list[InputArtifact],
    sidecars: list[pathlib.Path],
    commands: dict[str, tuple[pathlib.Path, list[str]]],
) -> dict[str, Any]:
    return {
        "config_sha256": sha256_file(config_path),
        "linked": file_identities(project_root, linked),
        "inputs": file_identities(project_root, [item.path for item in inputs]),
        "sidecars": file_identities(project_root, sidecars),
        "commands": {
            name: command_identity(working_directory, command)
            for name, (working_directory, command) in sorted(commands.items())
        },
    }


def materialize_snapshot(root: pathlib.Path, captured: dict[str, bytes]) -> None:
    root.mkdir()
    for route, payload in sorted(captured.items()):
        target = root / route
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        if target.read_bytes() != payload:
            raise GateError("snapshot-write", f"captured output read-back failed: {route}")


def run_gate(
    mode: str,
    config_path: pathlib.Path,
    receipt_path: pathlib.Path,
    promotion_command: list[str],
) -> int:
    receipt = base_receipt(mode, config_path)
    try:
        project_root, config = load_config(config_path)
        receipt["config"] = {
            "path": str(config_path),
            "sha256": sha256_file(config_path),
            "logical_output_root": config["build"]["output_root"],
        }
        receipt["unverified_remainder"] = {
            "engine_owned": list(ENGINE_UNVERIFIED_REMAINDER),
            "repository_declared": list(config["additional_unverified_remainder"]),
        }
        policy_path, markers = load_policy(project_root, config)
        acceptance_path = load_acceptance(project_root, config)
        manifest_path, renderers, inspections = load_surfaces(project_root, config)
        projection_config = config["destination_projection"]
        projection_working_directory = project_path(
            project_root,
            projection_config["working_directory"],
            "destination_projection.working_directory",
        )
        projection_command = list(projection_config["command"])
        projection_identity = dict(projection_config["expected_identity"])
        renderer_versions = {renderer["version"] for renderer in renderers}
        if renderer_versions != {projection_identity["renderer"]}:
            raise GateError(
                "invalid-config",
                "destination projection renderer identity must equal every declared renderer version",
            )
        receipt["policy"] = {
            "path": policy_path.relative_to(project_root).as_posix(),
            "sha256": sha256_file(policy_path),
            "marker_ids": [marker.marker_id for marker in markers],
        }
        receipt["surface_manifest"] = {
            "path": manifest_path.relative_to(project_root).as_posix(),
            "sha256": sha256_file(manifest_path),
            "renderers": [
                {"id": renderer["id"], "version": renderer["version"]}
                for renderer in renderers
            ],
        }
        receipt["acceptance_suite"] = {
            "path": acceptance_path.relative_to(project_root).as_posix(),
            "sha256": sha256_file(acceptance_path),
        }
        receipt["destination_projection"] = {
            "declared_command": projection_command,
            "expected_identity": projection_identity,
            "command_file_identities": command_identity(
                projection_working_directory, projection_command
            ),
        }
        inputs = discover_inputs(project_root, config)
        receipt["inputs"] = [item.receipt() for item in inputs]
        sidecars = sidecar_paths(project_root, config)
        receipt["sidecars"] = file_identities(project_root, sidecars)
        expected, route_findings = expected_routes(inputs, renderers)
        receipt["route_bijection"]["expected"] = expected
        receipt["findings"].extend(route_findings)

        for artifact in inputs:
            if any(
                "publishable-source" in inspections[renderer["id"]]
                and matches_any(artifact.relative_path, renderer["input_globs"])
                for renderer in renderers
            ):
                receipt["findings"].extend(
                    marker_findings(
                        markers,
                        "publishable-source",
                        [artifact.publishable],
                        path=artifact.relative_path,
                    )
                )
        for sidecar in sidecars:
            receipt["findings"].extend(
                marker_findings(
                    markers,
                    "sidecar-flags",
                    [sidecar.read_text(encoding="utf-8")],
                    path=sidecar.relative_to(project_root).as_posix(),
                )
            )

        linked = [policy_path, manifest_path, acceptance_path]
        working_directory = project_path(
            project_root, config["build"]["working_directory"], "build.working_directory"
        )
        raw_build_command = config["build"]["command"]
        receipt["build"]["declared_command"] = raw_build_command
        receipt["build"]["command_file_identities"] = command_identity(
            working_directory, raw_build_command
        )
        command_contracts = {
            "build": (working_directory, raw_build_command),
            "destination_projection": (
                projection_working_directory,
                projection_command,
            ),
        }

        with tempfile.TemporaryDirectory(prefix="synthesis-promotion-gate-") as temporary:
            output_root = pathlib.Path(temporary) / "rendered"
            output_root.mkdir()
            baseline = current_contract_identities(
                project_root,
                config_path,
                linked,
                inputs,
                sidecars,
                command_contracts,
            )
            build_command = substitute(
                raw_build_command,
                {
                    "output_root": str(output_root),
                    "project_root": str(project_root),
                    "config_dir": str(config_path.parent),
                },
            )
            try:
                built = subprocess.run(
                    build_command,
                    cwd=working_directory,
                    capture_output=True,
                    text=True,
                    timeout=900,
                    check=False,
                )
                receipt["build"].update(
                    exit_code=built.returncode,
                    stdout_sha256=sha256_bytes(built.stdout.encode("utf-8")),
                    stderr_sha256=sha256_bytes(built.stderr.encode("utf-8")),
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                receipt["build"].update(exit_code=None, error=type(exc).__name__)
                receipt["findings"].append(
                    {"kind": "build-failed", "path": str(working_directory), "message": str(exc)}
                )
                built = None
            if built is not None and built.returncode != 0:
                receipt["findings"].append(
                    {
                        "kind": "build-failed",
                        "path": str(working_directory),
                        "message": f"declared build exited {built.returncode}",
                    }
                )

            for artifact in inputs:
                actual = sha256_file(artifact.path)
                if actual != artifact.source_sha256:
                    receipt["findings"].append(
                        {
                            "kind": "input-changed-during-build",
                            "path": artifact.relative_path,
                            "message": "input hash changed after discovery and before promotion",
                        }
                    )

            inspected: list[dict[str, Any]] = []
            missing: list[str] = []
            captured_outputs: dict[str, bytes] = {}
            captured_text: dict[str, str] = {}
            expected_by_route = {item["route"]: item for item in expected}
            for route, item in expected_by_route.items():
                output = output_root / route
                no_symlink_components(output, output_root)
                if not output.is_file():
                    missing.append(route)
                    receipt["findings"].append(
                        {
                            "kind": "missing-rendered-output",
                            "path": item["input"],
                            "renderer": item["renderer"],
                            "route": route,
                            "message": "frontmatter-derived output is absent and therefore uninspected",
                        }
                    )
                    continue
                try:
                    payload = output.read_bytes()
                    raw = payload.decode("utf-8")
                except (OSError, UnicodeError) as exc:
                    receipt["findings"].append(
                        {
                            "kind": "rendered-representation-invalid",
                            "path": item["input"],
                            "renderer": item["renderer"],
                            "route": route,
                            "message": f"rendered output cannot be captured as UTF-8: {type(exc).__name__}",
                        }
                    )
                    continue
                captured_outputs[route] = payload
                captured_text[route] = raw
            receipt["route_bijection"]["inspected"] = inspected
            receipt["route_bijection"]["missing"] = missing
            actual_outputs: list[str] = []
            for path in output_root.rglob("*"):
                if path.is_symlink():
                    no_symlink_components(path, output_root)
                if path.is_file():
                    actual_outputs.append(path.relative_to(output_root).as_posix())
            unscoped_outputs = sorted(set(actual_outputs) - set(expected_by_route))
            receipt["route_bijection"]["unscoped_outputs"] = unscoped_outputs
            for route in unscoped_outputs:
                receipt["findings"].append(
                    {
                        "kind": "unscoped-rendered-output",
                        "path": route,
                        "route": route,
                        "message": "rendered output is outside the closed frontmatter-derived route universe",
                    }
                )

            if set(captured_text) == set(expected_by_route):
                projected_by_route, projection_telemetry = project_destinations(
                    projection_command,
                    projection_working_directory,
                    projection_identity,
                    captured_text,
                )
                receipt["destination_projection"].update(projection_telemetry)
                for route, item in expected_by_route.items():
                    projected = {
                        **projected_by_route[route],
                        "raw-page-source": [captured_text[route]],
                    }
                    representations = inspections[item["renderer"]]
                    inspected.append(
                        {
                            **item,
                            "sha256": sha256_bytes(captured_outputs[route]),
                            "representations": representations,
                            "projection_identity": projection_identity,
                            "representation_sha256": {
                                name: representation_digest(projected[name])
                                for name in sorted(DESTINATION_REPRESENTATIONS)
                            },
                        }
                    )
                    for representation in representations:
                        if representation not in DESTINATION_REPRESENTATIONS:
                            continue
                        receipt["findings"].extend(
                            marker_findings(
                                markers,
                                representation,
                                projected[representation],
                                path=item["input"],
                                renderer=item["renderer"],
                                route=route,
                            )
                        )
                receipt["route_bijection"]["inspected"] = inspected

            post_contract = current_contract_identities(
                project_root,
                config_path,
                linked,
                inputs,
                sidecars,
                command_contracts,
            )
            for key in ("config_sha256", "linked", "inputs", "sidecars", "commands"):
                if baseline[key] != post_contract[key]:
                    kind = "input-changed-during-build" if key == "inputs" else "contract-changed-during-build"
                    if not any(f["kind"] == kind for f in receipt["findings"]):
                        receipt["findings"].append(
                            {
                                "kind": kind,
                                "path": str(config_path),
                                "message": f"{key} identity changed during the build",
                            }
                        )
            post_build = {
                **post_contract,
                "outputs": captured_output_identities(captured_outputs),
            }
            receipt["identity_binding"] = post_build

            if receipt["findings"]:
                atomic_json(receipt_path, receipt)
                print(
                    f"REFUSED {len(receipt['findings'])} finding(s); "
                    "a successful build is not a publication-safety signal."
                )
                return 1

            receipt["status"] = "pass"
            if mode == "check":
                atomic_json(receipt_path, receipt)
                print("PASS acceptance-test receipt written; no promotion authority issued.")
                return 0

            if not promotion_command:
                receipt["status"] = "refused"
                receipt["findings"].append(
                    {
                        "kind": "missing-promotion-command",
                        "path": str(config_path),
                        "message": "enforce requires a supplied promotion command",
                    }
                )
                atomic_json(receipt_path, receipt)
                return 1
            required_tokens = {"{candidate_receipt}", "{output_root}"}
            present = {token for token in required_tokens if token in promotion_command}
            if present != required_tokens:
                receipt["status"] = "refused"
                receipt["findings"].append(
                    {
                        "kind": "unbound-promotion-command",
                        "path": str(config_path),
                        "message": "promotion command must carry {candidate_receipt} and {output_root}",
                    }
                )
                atomic_json(receipt_path, receipt)
                return 1

            snapshot_root = pathlib.Path(temporary) / f"captured-{uuid.uuid4().hex}"
            materialize_snapshot(snapshot_root, captured_outputs)
            snapshot_outputs = output_identities(snapshot_root, expected)
            receipt["handoff"] = {
                "mode": "captured-content-snapshot",
                "outputs": snapshot_outputs,
            }
            candidate_receipt = pathlib.Path(temporary) / "candidate-receipt.json"
            candidate = copy.deepcopy(receipt)
            candidate["metadata_class"] = "acceptance-test"
            candidate["authority_receipt"] = False
            atomic_json(candidate_receipt, candidate)

            immediately_before = {
                **current_contract_identities(
                    project_root,
                    config_path,
                    linked,
                    inputs,
                    sidecars,
                    command_contracts,
                ),
                "outputs": output_identities(snapshot_root, expected),
            }
            if immediately_before != post_build:
                receipt["status"] = "refused"
                receipt["findings"].append(
                    {
                        "kind": "receipt-revalidation-failed",
                        "path": str(config_path),
                        "message": "bound inputs or outputs changed before the state-changing command",
                    }
                )
                atomic_json(receipt_path, receipt)
                return 1

            command = substitute(
                promotion_command,
                {
                    "candidate_receipt": str(candidate_receipt),
                    "output_root": str(snapshot_root),
                    "project_root": str(project_root),
                    "config_dir": str(config_path.parent),
                },
            )
            receipt["promotion"]["attempted"] = True
            try:
                promoted = subprocess.run(
                    command,
                    cwd=project_root,
                    capture_output=True,
                    text=True,
                    timeout=900,
                    check=False,
                )
                receipt["promotion"].update(
                    exit_code=promoted.returncode,
                    command=promotion_command,
                    stdout_sha256=sha256_bytes(promoted.stdout.encode("utf-8")),
                    stderr_sha256=sha256_bytes(promoted.stderr.encode("utf-8")),
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                receipt["promotion"].update(exit_code=None, command=promotion_command)
                receipt["status"] = "refused"
                receipt["findings"].append(
                    {"kind": "promotion-command-failed", "path": str(project_root), "message": str(exc)}
                )
                atomic_json(receipt_path, receipt)
                return 1
            if promoted.returncode != 0:
                receipt["status"] = "refused"
                receipt["findings"].append(
                    {
                        "kind": "promotion-command-failed",
                        "path": str(project_root),
                        "message": f"promotion command exited {promoted.returncode}",
                    }
                )
                atomic_json(receipt_path, receipt)
                return 1
            if output_identities(snapshot_root, expected) != snapshot_outputs:
                receipt["status"] = "refused"
                receipt["findings"].append(
                    {
                        "kind": "snapshot-changed-during-promotion",
                        "path": str(config_path),
                        "message": "the supplied promotion command changed the captured output snapshot",
                    }
                )
                atomic_json(receipt_path, receipt)
                return 1
            receipt["metadata_class"] = "enforced-gate"
            receipt["authority_receipt"] = True
            receipt["status"] = "pass"
            atomic_json(receipt_path, receipt)
            print("PASS enforced-gate receipt written after the promotion command returned cleanly.")
            return 0
    except GateError as exc:
        add_fatal(receipt, exc)
        try:
            atomic_json(receipt_path, receipt)
        except GateError as write_error:
            print(f"REFUSED {exc.message}; receipt also failed: {write_error.message}", file=sys.stderr)
            return 1
        print(f"REFUSED {exc.message}", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="mode", required=True)
    for mode in ("check", "enforce"):
        command = subparsers.add_parser(mode)
        command.add_argument("--config", required=True, type=pathlib.Path)
        command.add_argument("--receipt", required=True, type=pathlib.Path)
        if mode == "enforce":
            command.add_argument("promotion_command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    promotion = getattr(args, "promotion_command", [])
    if promotion and promotion[0] == "--":
        promotion = promotion[1:]
    # os.path.abspath is intentionally lexical. pathlib.resolve() would follow a
    # symlink before load_config() or atomic_json() could refuse it.
    config_path = pathlib.Path(os.path.abspath(os.fspath(args.config)))
    receipt_path = pathlib.Path(os.path.abspath(os.fspath(args.receipt)))
    return run_gate(
        args.mode,
        config_path,
        receipt_path,
        promotion,
    )


if __name__ == "__main__":
    raise SystemExit(main())

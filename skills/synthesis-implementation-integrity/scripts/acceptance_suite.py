#!/usr/bin/env python3
"""Validate and execute a closed, defect-pinned acceptance manifest.

The manifest is evidence about a declared test universe. It does not grant
approval or replace the state-changing boundary that consumes its result.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - exercised only in dependency failure
    yaml = None


VALID_EXPECTED_STATUSES = {"pass", "fail"}
VALID_SCHEMAS = {1, 2}


class ManifestError(Exception):
    """The declared acceptance universe cannot be established."""


def _canonical_root(raw: str) -> Path:
    root = Path(raw).expanduser()
    try:
        root = root.resolve(strict=True)
    except OSError as exc:
        raise ManifestError(f"repo-root is not readable: {root}: {exc}") from exc
    if not root.is_dir():
        raise ManifestError(f"repo-root is not a directory: {root}")
    return root


def _lexical_path(raw: Path) -> Path:
    return Path(os.path.abspath(os.fspath(raw.expanduser())))


def _bounded_regular_file(path: Path, root: Path, label: str) -> Path:
    """Require a regular file inside root without traversing a symlink."""

    candidate = _lexical_path(path)
    try:
        relative = candidate.relative_to(root)
    except ValueError as exc:
        raise ManifestError(f"{label} escapes repo-root: {path}") from exc

    cursor = root
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ManifestError(f"{label} traverses a symlink: {path}")
    if not candidate.is_file():
        raise ManifestError(f"{label} is not a regular file: {path}")
    return candidate


def _nonempty_string(document: dict[str, Any], field: str, errors: list[str]) -> str:
    value = document.get(field)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{field} must be a non-empty string")
        return ""
    return value.strip()


def _load_manifest(path: Path, root: Path) -> tuple[Path, dict[str, Any]]:
    if yaml is None:
        raise ManifestError("PyYAML is required to read acceptance manifests")
    manifest = _bounded_regular_file(path, root, "manifest")
    try:
        loaded = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ManifestError(f"manifest is unreadable: {manifest}: {exc}") from exc
    if not isinstance(loaded, dict):
        raise ManifestError("manifest root must be a mapping")
    return manifest, loaded


def validate_manifest(
    manifest_path: Path, root: Path
) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        manifest_file, document = _load_manifest(manifest_path, root)
    except ManifestError as exc:
        return None, [str(exc)]

    errors: list[str] = []
    schema = document.get("schema")
    if (
        not isinstance(schema, int)
        or isinstance(schema, bool)
        or schema not in VALID_SCHEMAS
    ):
        errors.append(f"schema must be one of {sorted(VALID_SCHEMAS)}")
    _nonempty_string(document, "suite", errors)
    if document.get("membership") != "closed":
        errors.append("membership must be closed")
    _nonempty_string(document, "production_entry_point", errors)
    _nonempty_string(document, "enforcing_boundary", errors)
    expected_default = _nonempty_string(document, "expected_status", errors)
    if expected_default and expected_default not in VALID_EXPECTED_STATUSES:
        errors.append("expected_status must be pass or fail")
    _nonempty_string(document, "unverified_remainder", errors)

    raw_cases = document.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        errors.append("cases must be a non-empty list")
        raw_cases = []

    case_ids: set[str] = set()
    case_records: list[dict[str, Any]] = []
    has_enforced_gate = False
    for position, raw_case in enumerate(raw_cases):
        label = f"cases[{position}]"
        if not isinstance(raw_case, dict):
            errors.append(f"{label} must be a mapping")
            continue
        case_id = raw_case.get("id")
        if not isinstance(case_id, str) or not case_id.strip():
            errors.append(f"{label}.id must be a non-empty string")
            continue
        case_id = case_id.strip()
        if case_id in case_ids:
            errors.append(f"duplicate case id: {case_id}")
        case_ids.add(case_id)

        control_class = raw_case.get("control_class")
        if not isinstance(control_class, str) or not control_class.strip():
            errors.append(f"case {case_id} control_class must be a non-empty string")
        elif control_class == "enforced-gate":
            has_enforced_gate = True

        motivating_defect = raw_case.get("motivating_defect")
        if not isinstance(motivating_defect, str) or not motivating_defect.strip():
            errors.append(
                f"case {case_id} motivating_defect must be a non-empty string"
            )

        expected = raw_case.get("expected_status", expected_default)
        if expected not in VALID_EXPECTED_STATUSES:
            errors.append(f"case {case_id} expected_status must be pass or fail")

        fixture = raw_case.get("fixture")
        fixture_file: Path | None = None
        fixture_node = ""
        if not isinstance(fixture, str) or "::" not in fixture:
            errors.append(f"case {case_id} fixture must use file.py::node syntax")
        else:
            fixture_path_raw, fixture_node = fixture.split("::", 1)
            if not fixture_path_raw or not fixture_node:
                errors.append(f"case {case_id} fixture must use file.py::node syntax")
            else:
                try:
                    fixture_file = _bounded_regular_file(
                        manifest_file.parent / fixture_path_raw,
                        root,
                        f"case {case_id} fixture",
                    )
                except ManifestError as exc:
                    errors.append(str(exc))

        case_records.append(
            {
                "id": case_id,
                "control_class": control_class,
                "motivating_defect": motivating_defect,
                "expected_status": expected,
                "fixture_file": fixture_file,
                "fixture_node": fixture_node,
            }
        )

    if has_enforced_gate:
        _nonempty_string(document, "receipt_consumer", errors)

    raw_surfaces = document.get("changed_surfaces")
    if schema == 2 and (not isinstance(raw_surfaces, list) or not raw_surfaces):
        errors.append("schema 2 changed_surfaces must be a non-empty list")
        raw_surfaces = []
    elif raw_surfaces is None:
        raw_surfaces = []
    elif not isinstance(raw_surfaces, list):
        errors.append("changed_surfaces must be a list")
        raw_surfaces = []

    mapped_cases: set[str] = set()
    surface_records: list[dict[str, Any]] = []
    for position, raw_surface in enumerate(raw_surfaces):
        label = f"changed_surfaces[{position}]"
        if not isinstance(raw_surface, dict):
            errors.append(f"{label} must be a mapping")
            continue
        raw_path = raw_surface.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            errors.append(f"{label}.path must be a non-empty string")
        else:
            try:
                _bounded_regular_file(root / raw_path, root, f"{label}.path")
            except ManifestError as exc:
                errors.append(str(exc))

        surface_cases = raw_surface.get("cases")
        if not isinstance(surface_cases, list) or not surface_cases:
            errors.append(f"{label}.cases must be a non-empty list")
            surface_cases = []
        for mapped_id in surface_cases:
            if not isinstance(mapped_id, str) or not mapped_id:
                errors.append(f"{label}.cases contains an invalid case id")
            elif mapped_id not in case_ids:
                errors.append(f"{label}.cases references unknown case {mapped_id}")
            else:
                mapped_cases.add(mapped_id)
        surface_records.append({"path": raw_path, "cases": surface_cases})

    if schema == 2:
        for case_id in sorted(case_ids - mapped_cases):
            errors.append(f"case {case_id} is not mapped to a changed surface")

    if errors:
        return None, errors

    return {
        "document": document,
        "manifest": manifest_file,
        "cases": case_records,
        "changed_surfaces": surface_records,
    }, []


def validation_receipt(validated: dict[str, Any]) -> dict[str, Any]:
    document = validated["document"]
    return {
        "ok": True,
        "schema": document["schema"],
        "suite": document["suite"],
        "membership": document["membership"],
        "cases_declared": len(validated["cases"]),
        "production_entry_point": document["production_entry_point"],
        "enforcing_boundary": document["enforcing_boundary"],
        "receipt_consumer": document.get("receipt_consumer"),
        "metadata_class": document.get("metadata_class", "acceptance-test"),
        "issues_authority_receipt": False,
        "unverified_remainder": document["unverified_remainder"],
    }


def execute(validated: dict[str, Any], root: Path) -> tuple[dict[str, Any], int]:
    document = validated["document"]
    results: list[dict[str, Any]] = []
    for case in validated["cases"]:
        node_id = f"{case['fixture_file']}::{case['fixture_node']}"
        try:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "-q",
                    "-p",
                    "no:cacheprovider",
                    node_id,
                ],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                timeout=300,
            )
            status = (
                "passed"
                if completed.returncode == 0
                else "failed"
                if completed.returncode == 1
                else "errored"
            )
            returncode: int | None = completed.returncode
            stdout = completed.stdout
            stderr = completed.stderr
        except (OSError, subprocess.SubprocessError) as exc:
            status = "errored"
            returncode = None
            stdout = ""
            stderr = str(exc)

        expected = case["expected_status"]
        matched = status == {"pass": "passed", "fail": "failed"}[expected]
        results.append(
            {
                "id": case["id"],
                "control_class": case["control_class"],
                "motivating_defect": case["motivating_defect"],
                "fixture": node_id,
                "status": status,
                "expected_status": expected,
                "matched": matched,
                "returncode": returncode,
                "stdout": stdout,
                "stderr": stderr,
            }
        )

    terminal = len(results)
    ok = terminal == len(validated["cases"]) and all(
        case["matched"] for case in results
    )
    receipt = validation_receipt(validated)
    receipt.update(
        {
            "ok": ok,
            "coverage": {
                "declared": len(validated["cases"]),
                "terminal": terminal,
                "not_run": len(validated["cases"]) - terminal,
            },
            "cases": results,
        }
    )
    return receipt, 0 if ok else 1


def emit(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    if "errors" in payload:
        for error in payload["errors"]:
            print(f"ERROR {error}")
        return
    if "cases" in payload:
        for case in payload["cases"]:
            marker = "PASS" if case["matched"] else "FAIL"
            print(
                f"{marker} {case['id']}: {case['status']} "
                f"(expected {case['expected_status']})"
            )
        coverage = payload["coverage"]
        print(
            f"acceptance suite: {coverage['terminal']}/{coverage['declared']} "
            f"terminal; {coverage['not_run']} not run"
        )
        return
    print(
        f"acceptance manifest: {payload['cases_declared']} declared case(s); "
        f"membership={payload['membership']}"
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate or run a closed acceptance manifest."
    )
    parser.add_argument("action", choices=("validate", "run"))
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        root = _canonical_root(args.repo_root)
    except ManifestError as exc:
        emit({"ok": False, "errors": [str(exc)]}, args.json)
        return 2
    manifest_path = Path(args.manifest).expanduser()
    if not manifest_path.is_absolute():
        manifest_path = root / manifest_path
    validated, errors = validate_manifest(manifest_path, root)
    if validated is None:
        emit({"ok": False, "errors": errors}, args.json)
        return 2
    if args.action == "validate":
        emit(validation_receipt(validated), args.json)
        return 0
    payload, returncode = execute(validated, root)
    emit(payload, args.json)
    return returncode


if __name__ == "__main__":
    raise SystemExit(main())

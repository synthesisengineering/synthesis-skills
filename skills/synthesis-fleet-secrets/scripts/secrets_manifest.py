#!/usr/bin/env python3
"""Secrets-manifest schema + parser/validator for the fleet secrets provider.

The secrets manifest maps backend refs to materialization paths and
permissions. It carries refs only — never values. Unknown keys (notably a
stray ``value:``) are rejected so secret material cannot enter the manifest
by typo. The manifest itself lives in the personal sphere and is never
committed to a shared repo; only this schema and generic examples ship here.

Schema (YAML or JSON)::

    schema_version: 1
    backend: onepassword        # or age-sops
    entries:
      - ref: op://ExampleVault/ExampleItem/api-key
        path: ~/.synthesis/example-service/api-key
        mode: "0600"            # owner-only: exactly 0600 or 0400, quoted

Paths must be ``~``- (or ``$HOME``-) rooted per the fleet ``~``-normalization
rule: no literal home paths, no parent traversal.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
BACKENDS = ("onepassword", "age-sops")
OWNER_ONLY_MODES = ("0600", "0400")
_TOP_LEVEL_KEYS = frozenset({"schema_version", "backend", "entries"})
_ENTRY_KEYS = frozenset({"ref", "path", "mode"})


class ManifestError(ValueError):
    """The manifest is missing, unreadable, or fails schema validation."""


@dataclass(frozen=True)
class ManifestEntry:
    ref: str
    path: str
    mode: str


@dataclass(frozen=True)
class SecretsManifest:
    schema_version: int
    backend: str
    entries: tuple[ManifestEntry, ...]
    source: Path | None


def parse_manifest(path: str | Path) -> SecretsManifest:
    """Load and validate a manifest file (YAML or JSON by suffix)."""
    manifest_path = Path(path)
    try:
        text = manifest_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ManifestError("cannot read manifest %s: %s" % (manifest_path, exc)) from exc
    suffix = manifest_path.suffix.lower()
    try:
        if suffix == ".json":
            import json

            data = json.loads(text)
        else:
            import yaml

            data = yaml.safe_load(text)
    except ValueError as exc:
        raise ManifestError("cannot parse manifest %s: %s" % (manifest_path, exc)) from exc
    return validate_manifest_dict(data, source=manifest_path)


def parse_manifest_text(text: str, *, source: Path | None = None) -> SecretsManifest:
    """Validate a YAML manifest document held in memory."""
    import yaml

    try:
        data = yaml.safe_load(text)
    except ValueError as exc:
        raise ManifestError("cannot parse manifest: %s" % exc) from exc
    return validate_manifest_dict(data, source=source)


def validate_manifest_dict(data: Any, *, source: Path | None = None) -> SecretsManifest:
    """Validate a decoded manifest document. Fails closed on any deviation."""
    where = " in %s" % source if source else ""
    if not isinstance(data, dict):
        raise ManifestError("manifest%s must be a mapping" % where)
    for key in data:
        if key not in _TOP_LEVEL_KEYS:
            raise ManifestError("unknown manifest key %r%s" % (key, where))
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ManifestError(
            "manifest%s schema_version must be %d, got %r"
            % (where, SCHEMA_VERSION, data.get("schema_version"))
        )
    backend = data.get("backend")
    if backend not in BACKENDS:
        raise ManifestError(
            "manifest%s backend must be one of %s, got %r" % (where, list(BACKENDS), backend)
        )
    raw_entries = data.get("entries")
    if not isinstance(raw_entries, list) or not raw_entries:
        raise ManifestError("manifest%s entries must be a non-empty list" % where)
    entries: list[ManifestEntry] = []
    seen_paths: set[str] = set()
    for index, raw in enumerate(raw_entries):
        entry = _validate_entry(raw, index, backend, where)
        if entry.path in seen_paths:
            raise ManifestError(
                "manifest%s entry %d: duplicate destination path %r" % (where, index, entry.path)
            )
        seen_paths.add(entry.path)
        entries.append(entry)
    return SecretsManifest(
        schema_version=SCHEMA_VERSION, backend=backend, entries=tuple(entries), source=source
    )


def _validate_entry(raw: Any, index: int, backend: str, where: str) -> ManifestEntry:
    label = "entry %d%s" % (index, where)
    if not isinstance(raw, dict):
        raise ManifestError("manifest %s must be a mapping" % label)
    for key in raw:
        if key not in _ENTRY_KEYS:
            raise ManifestError("manifest %s: unknown key %r (refs only, never values)" % (label, key))
    ref = raw.get("ref")
    if not isinstance(ref, str) or not ref.strip():
        raise ManifestError("manifest %s: ref must be a non-empty string" % label)
    _validate_ref_shape(ref, backend, label)
    path = raw.get("path")
    _validate_path(path, label)
    mode = raw.get("mode")
    if isinstance(mode, int):
        raise ManifestError(
            "manifest %s: mode must be a quoted string ('0600' or '0400'), got unquoted %r"
            % (label, mode)
        )
    if mode not in OWNER_ONLY_MODES:
        raise ManifestError(
            "manifest %s: mode must be exactly '0600' or '0400' (owner-only), got %r"
            % (label, mode)
        )
    return ManifestEntry(ref=ref, path=path, mode=mode)


def _validate_ref_shape(ref: str, backend: str, label: str) -> None:
    if backend == "onepassword":
        if not ref.startswith("op://"):
            raise ManifestError(
                "manifest %s: onepassword ref must start with 'op://', got %r" % (label, ref)
            )
    elif backend == "age-sops":
        if "#" not in ref or ref.startswith("/") or any(ch.isspace() for ch in ref):
            raise ManifestError(
                "manifest %s: age-sops ref must look like '<file>#<key>' "
                "with no whitespace, got %r" % (label, ref)
            )


def _validate_path(path: Any, label: str) -> None:
    if not isinstance(path, str) or not path.strip():
        raise ManifestError("manifest %s: path must be a non-empty string" % label)
    remainder: str | None = None
    if path.startswith("~/"):
        remainder = path[2:]
    elif path.startswith("$HOME/"):
        remainder = path[len("$HOME/"):]
    if remainder is None:
        raise ManifestError(
            "manifest %s: path must be home-rooted ('~/...' or '$HOME/...'), got %r"
            % (label, path)
        )
    if not remainder:
        raise ManifestError("manifest %s: path names no file" % label)
    if ".." in remainder.split("/"):
        raise ManifestError("manifest %s: path must not contain '..' segments" % label)


def expand_entry_path(entry: ManifestEntry, *, home: Path | None = None) -> Path:
    """Resolve an entry's declared path against ``home`` (default: real home)."""
    base = Path(home) if home is not None else Path.home()
    if entry.path.startswith("~/"):
        return base / entry.path[2:]
    if entry.path.startswith("$HOME/"):
        return base / entry.path[len("$HOME/"):]
    raise ManifestError("cannot expand non-home-rooted path %r" % entry.path)

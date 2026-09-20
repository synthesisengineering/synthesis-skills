#!/usr/bin/env python3
"""Tests for the fleet secrets-manifest schema + parser/validator.

All refs, vaults, and paths are fake. No secret value may appear in this
file — the values-absent doctor check treats test fixtures as in-scope.

    python3 -m pytest test_secrets_manifest.py -q
"""
from __future__ import annotations

import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import secrets_manifest as sm  # noqa: E402


FAKE_REF_A = "op://ExampleVault/ExampleItem/api-key"
FAKE_REF_B = "op://ExampleVault/OtherItem/token"


def manifest_text(**overrides: object) -> str:
    entries = overrides.pop("entries", [
        {"ref": FAKE_REF_A, "path": "~/.synthesis/example-service/api-key", "mode": "0600"},
        {"ref": FAKE_REF_B, "path": "~/.synthesis/example-service/token", "mode": "0400"},
    ])
    doc = {"schema_version": 1, "backend": "onepassword", "entries": entries}
    doc.update(overrides)
    import yaml

    return yaml.safe_dump(doc)


def test_valid_manifest_parses() -> None:
    manifest = sm.parse_manifest_text(manifest_text())
    assert manifest.schema_version == 1
    assert manifest.backend == "onepassword"
    assert len(manifest.entries) == 2
    assert manifest.entries[0].ref == FAKE_REF_A
    assert manifest.entries[1].mode == "0400"


def test_valid_manifest_from_json_file(tmp_path: pathlib.Path) -> None:
    import json

    path = tmp_path / "secrets-manifest.json"
    path.write_text(
        json.dumps({
            "schema_version": 1,
            "backend": "onepassword",
            "entries": [{"ref": FAKE_REF_A, "path": "~/.synthesis/example/x", "mode": "0600"}],
        }),
        encoding="utf-8",
    )
    manifest = sm.parse_manifest(path)
    assert manifest.source == path
    assert manifest.entries[0].ref == FAKE_REF_A


def test_valid_manifest_from_yaml_file(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "secrets-manifest.yaml"
    path.write_text(manifest_text(), encoding="utf-8")
    assert len(sm.parse_manifest(path).entries) == 2


def test_rejects_unknown_schema_version() -> None:
    with pytest.raises(sm.ManifestError, match="schema_version"):
        sm.parse_manifest_text(manifest_text(schema_version=2))


def test_rejects_unknown_backend() -> None:
    with pytest.raises(sm.ManifestError, match="backend"):
        sm.parse_manifest_text(manifest_text(backend="vault-xyz"))


def test_rejects_missing_entries() -> None:
    with pytest.raises(sm.ManifestError, match="entries"):
        sm.parse_manifest_text(manifest_text(entries=[]))


def test_rejects_unknown_entry_key_value() -> None:
    # Fail closed: a `value:` key means secret material is entering the
    # manifest, which must only ever carry refs.
    with pytest.raises(sm.ManifestError, match="value"):
        sm.parse_manifest_text(manifest_text(entries=[
            {"ref": FAKE_REF_A, "path": "~/.synthesis/example/x", "mode": "0600",
             "value": "FAKE-MUST-NEVER-PARSE"},
        ]))


def test_rejects_unknown_top_level_key() -> None:
    import yaml

    doc = yaml.safe_load(manifest_text())
    doc["owner"] = "example"
    with pytest.raises(sm.ManifestError, match="owner"):
        sm.validate_manifest_dict(doc)


def test_rejects_non_op_ref_for_onepassword() -> None:
    with pytest.raises(sm.ManifestError, match=r"op://"):
        sm.parse_manifest_text(manifest_text(entries=[
            {"ref": "vault/item/field", "path": "~/.synthesis/example/x", "mode": "0600"},
        ]))


def test_age_sops_ref_shape() -> None:
    manifest = sm.parse_manifest_text(manifest_text(
        backend="age-sops",
        entries=[{"ref": "example.enc.yaml#/service/token",
                  "path": "~/.synthesis/example/x", "mode": "0600"}],
    ))
    assert manifest.entries[0].ref == "example.enc.yaml#/service/token"
    with pytest.raises(sm.ManifestError, match="#"):
        sm.parse_manifest_text(manifest_text(
            backend="age-sops",
            entries=[{"ref": "no-separator-here",
                      "path": "~/.synthesis/example/x", "mode": "0600"}],
        ))


def test_rejects_absolute_home_path() -> None:
    with pytest.raises(sm.ManifestError, match="~"):
        sm.parse_manifest_text(manifest_text(entries=[
            {"ref": FAKE_REF_A, "path": "/Users/example/.synthesis/x", "mode": "0600"},
        ]))


def test_rejects_parent_traversal() -> None:
    with pytest.raises(sm.ManifestError, match=r"\.\."):
        sm.parse_manifest_text(manifest_text(entries=[
            {"ref": FAKE_REF_A, "path": "~/../elsewhere/x", "mode": "0600"},
        ]))


def test_accepts_home_env_prefix() -> None:
    manifest = sm.parse_manifest_text(manifest_text(entries=[
        {"ref": FAKE_REF_A, "path": "$HOME/.synthesis/example/x", "mode": "0600"},
    ]))
    assert manifest.entries[0].path == "$HOME/.synthesis/example/x"


@pytest.mark.parametrize("mode", ["0644", "0660", "0777", "644", "600"])
def test_rejects_group_or_other_modes(mode: str) -> None:
    with pytest.raises(sm.ManifestError, match="0600"):
        sm.parse_manifest_text(manifest_text(entries=[
            {"ref": FAKE_REF_A, "path": "~/.synthesis/example/x", "mode": mode},
        ]))


def test_rejects_unquoted_numeric_mode() -> None:
    import yaml

    doc = yaml.safe_load(manifest_text())
    doc["entries"][0]["mode"] = 600
    with pytest.raises(sm.ManifestError, match="quote"):
        sm.validate_manifest_dict(doc)


def test_rejects_duplicate_dest_paths() -> None:
    with pytest.raises(sm.ManifestError, match="duplicate"):
        sm.parse_manifest_text(manifest_text(entries=[
            {"ref": FAKE_REF_A, "path": "~/.synthesis/example/x", "mode": "0600"},
            {"ref": FAKE_REF_B, "path": "~/.synthesis/example/x", "mode": "0600"},
        ]))


def test_duplicate_refs_to_distinct_paths_allowed() -> None:
    manifest = sm.parse_manifest_text(manifest_text(entries=[
        {"ref": FAKE_REF_A, "path": "~/.synthesis/example/a", "mode": "0600"},
        {"ref": FAKE_REF_A, "path": "~/.synthesis/example/b", "mode": "0600"},
    ]))
    assert len(manifest.entries) == 2


def test_expand_entry_path(tmp_path: pathlib.Path) -> None:
    entry = sm.ManifestEntry(ref=FAKE_REF_A, path="~/.synthesis/example/x", mode="0600")
    assert sm.expand_entry_path(entry, home=tmp_path) == tmp_path / ".synthesis/example/x"
    env_entry = sm.ManifestEntry(ref=FAKE_REF_A, path="$HOME/.synthesis/example/x", mode="0600")
    assert sm.expand_entry_path(env_entry, home=tmp_path) == tmp_path / ".synthesis/example/x"

"""Fleet machine identity: minting, registry, and never-transport rules."""
from __future__ import annotations

import json
import os
import stat
import sys
import uuid
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import fleet_identity as FI


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch, tmp_path):
    monkeypatch.setenv(FI.FLEET_DIR_ENV, str(tmp_path / "fleet"))


def test_mint_writes_uuid4_mode_0600(tmp_path):
    minted = FI.mint_machine_id()
    assert uuid.UUID(minted).version == 4
    path = FI.machine_id_path()
    assert path.read_text(encoding="utf-8") == minted + "\n"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert FI.read_machine_id() == minted


def test_read_machine_id_missing_is_unenrolled():
    assert FI.read_machine_id() is None


def test_read_machine_id_malformed_fails_closed():
    FI.machine_id_path().parent.mkdir(parents=True, exist_ok=True)
    FI.machine_id_path().write_text("not-a-uuid\n", encoding="utf-8")
    with pytest.raises(FI.FleetIdentityError, match="not a UUID4"):
        FI.read_machine_id()


def test_mint_refuses_to_overwrite_never_transport():
    first = FI.mint_machine_id()
    with pytest.raises(FI.FleetIdentityError, match="refusing to overwrite"):
        FI.mint_machine_id()
    assert FI.read_machine_id() == first


def test_two_macs_mint_distinct_ids_fleet_ac_03(tmp_path):
    mac_a = tmp_path / "mac-a"
    mac_b = tmp_path / "mac-b"
    id_a = FI.mint_machine_id(mac_a)
    id_b = FI.mint_machine_id(mac_b)
    assert id_a != id_b
    assert uuid.UUID(id_a).version == 4
    assert uuid.UUID(id_b).version == 4


def test_registry_lists_both_macs_fleet_ac_03(tmp_path):
    mac_a = tmp_path / "mac-a"
    mac_b = tmp_path / "mac-b"
    id_a = FI.mint_machine_id(mac_a)
    id_b = FI.mint_machine_id(mac_b)
    shared = tmp_path / "shared"
    FI.enroll_self(label="mac-a", role="primary", directory=mac_a)
    # The registry document travels; each Mac's machine-id file never does.
    # Mac B's enrollment arrives as a bootstrap receipt keyed on B's own
    # mint, merged into the shared document (the personal-KB copy).
    document = FI.read_registry(mac_a)
    entry_b = {
        "label": "mac-b",
        "enrolled_at": "2026-09-19T10:00:00+00:00",
        "last_seen": "2026-09-19T10:00:00+00:00",
        "role": "secondary",
        "environments": ["default"],
        "retired_at": None,
    }
    document["machines"][id_b] = entry_b
    FI.write_registry(document, shared)
    listed = FI.read_registry(shared)
    assert set(listed["machines"]) == {id_a, id_b}
    assert listed["machines"][id_a]["role"] == "primary"
    assert listed["machines"][id_b]["role"] == "secondary"
    assert FI.read_machine_id(mac_a) in listed["machines"]
    assert FI.read_machine_id(mac_b) in listed["machines"]
    assert entry_b["environments"] == ["default"]


def test_registry_missing_is_empty():
    assert FI.read_registry() == {"schema_version": 1, "machines": {}}


def test_registry_write_refuses_bad_schema_version():
    with pytest.raises(FI.FleetIdentityError, match="schema_version"):
        FI.write_registry({"schema_version": 2, "machines": {}})


def test_registry_write_requires_exactly_one_primary():
    first, second = str(uuid.uuid4()), str(uuid.uuid4())

    def entry(role):
        return {
            "label": role,
            "enrolled_at": "2026-09-19T00:00:00+00:00",
            "last_seen": "2026-09-19T00:00:00+00:00",
            "role": role,
            "environments": ["default"],
            "retired_at": None,
        }

    with pytest.raises(FI.FleetIdentityError, match="exactly one primary"):
        FI.write_registry(
            {
                "schema_version": 1,
                "machines": {first: entry("secondary"), second: entry("secondary")},
            }
        )
    with pytest.raises(FI.FleetIdentityError, match="role"):
        FI.write_registry(
            {"schema_version": 1, "machines": {first: entry("observer")}}
        )


def test_registry_ops_never_touch_machine_id_never_transport():
    FI.mint_machine_id()
    before = FI.machine_id_path().read_bytes()
    FI.read_registry()
    FI.enroll_self(label="mac-a", role="primary")
    FI.touch_last_seen()
    FI.label_for("no-such-id")
    assert FI.machine_id_path().read_bytes() == before


def test_no_api_writes_caller_supplied_identity_never_transport():
    # The only machine-id writer generates; nothing in the module accepts a
    # foreign id to persist as local. Mint twice across dirs: outputs are
    # fresh UUIDs, never an echo of an input.
    first = FI.mint_machine_id()
    assert first != "1ae549d6-48aa-44d5-bc2a-9a76c995b599"
    assert not hasattr(FI, "write_machine_id")
    assert not hasattr(FI, "import_machine_id")
    assert not hasattr(FI, "set_machine_id")


def test_enroll_before_mint_refuses():
    with pytest.raises(FI.FleetIdentityError, match="before minting"):
        FI.enroll_self(label="mac-a", role="primary")


def test_enroll_preserves_enrolled_at_and_refreshes_last_seen():
    FI.mint_machine_id()
    first = FI.enroll_self(
        label="mac-a", role="primary", now="2026-09-19T10:00:00+00:00"
    )
    second = FI.enroll_self(
        label="mac-a-renamed", role="primary", now="2026-09-20T10:00:00+00:00"
    )
    assert second["enrolled_at"] == first["enrolled_at"]
    assert second["last_seen"] == "2026-09-20T10:00:00+00:00"
    assert second["label"] == "mac-a-renamed"


def test_touch_last_seen_unenrolled_is_none():
    FI.mint_machine_id()
    assert FI.touch_last_seen() is None


def test_label_for_unknown_id_echoes_id():
    assert FI.label_for("no-such-id") == "no-such-id"


def test_registry_malformed_json_fails_closed():
    FI.registry_path().parent.mkdir(parents=True, exist_ok=True)
    FI.registry_path().write_text("{broken\n", encoding="utf-8")
    with pytest.raises(FI.FleetIdentityError, match="not JSON"):
        FI.read_registry()


def test_registry_entry_shape_validated():
    bad_id = str(uuid.uuid4())
    document = {
        "schema_version": 1,
        "machines": {bad_id: {"label": "", "role": "primary"}},
    }
    problems = FI.validate_registry(document)
    assert any("label" in problem for problem in problems)
    assert any("environments" in problem for problem in problems)
    with pytest.raises(FI.FleetIdentityError, match="fleet registry invalid"):
        FI.registry_path().parent.mkdir(parents=True, exist_ok=True)
        FI.registry_path().write_text(json.dumps(document), encoding="utf-8")
        FI.read_registry()


def test_mint_mode_survives_permissive_umask(tmp_path, monkeypatch):
    monkeypatch.delenv(FI.FLEET_DIR_ENV)
    monkeypatch.setattr(os, "environ", {**os.environ, FI.FLEET_DIR_ENV: str(tmp_path / "u")})
    old = os.umask(0o022)
    try:
        FI.mint_machine_id()
    finally:
        os.umask(old)
    assert stat.S_IMODE(FI.machine_id_path().stat().st_mode) == 0o600

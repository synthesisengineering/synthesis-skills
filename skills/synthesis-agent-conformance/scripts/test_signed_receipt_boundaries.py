"""Independent synthetic actual-owner freshness and immutability controls."""

from pathlib import Path
import sys
import importlib
from datetime import timedelta
import pytest

C = Path(__file__).resolve().parent
sys.path.insert(0, str(C))
fixtures = importlib.import_module("test_signed_receipt")
sr = importlib.import_module("signed_receipt")
lr = importlib.import_module("live_receipt")
issued = fixtures.issued
NOW = fixtures.NOW


def clock(monkeypatch):
    current = [NOW]
    original = sr.now_time
    monkeypatch.setattr(
        sr, "now_time", lambda now=None: original(current[0] if now is None else now)
    )
    return current


def test_verify_expiry_during_actual_signature_check_refuses(issued, monkeypatch):
    current = clock(monkeypatch)
    original = sr._ssh

    def checked(*a, **kw):
        result = original(*a, **kw)
        current[0] = NOW + timedelta(seconds=601)
        return result

    monkeypatch.setattr(sr, "_ssh", checked)
    with pytest.raises(ValueError, match="stale|expir|lifetime|validity"):
        lr.signed_observation(issued["envelope"], issued["trust"], issued["expected"])


def test_verify_revocation_during_actual_signature_check_refuses(issued, monkeypatch):
    original = sr._ssh

    def checked(*a, **kw):
        result = original(*a, **kw)
        issued["trust"]["keys"][0]["revoked"] = True
        return result

    monkeypatch.setattr(sr, "_ssh", checked)
    with pytest.raises(ValueError, match="revok|changed"):
        lr.signed_observation(
            issued["envelope"], issued["trust"], issued["expected"], now=NOW
        )


def test_verify_payload_mutation_during_actual_signature_check_refuses(
    issued, monkeypatch
):
    original = sr._ssh

    def checked(*a, **kw):
        result = original(*a, **kw)
        issued["envelope"]["payload"]["status"] = "FAIL"
        return result

    monkeypatch.setattr(sr, "_ssh", checked)
    with pytest.raises(ValueError, match="changed"):
        lr.signed_observation(
            issued["envelope"], issued["trust"], issued["expected"], now=NOW
        )


def test_expired_before_exclusive_admission_does_not_consume_event(issued, monkeypatch):
    current = clock(monkeypatch)
    latest = issued["tmp"] / "latest.json"

    def recheck():
        current[0] = NOW + timedelta(seconds=601)

    with pytest.raises(ValueError, match="stale|expir|lifetime|validity"):
        lr.admit_signed_observation(
            latest,
            issued["envelope"],
            issued["trust"],
            issued["expected"],
            source_check=recheck,
        )
    root = lr.receipt_registry_root(latest, "codex")
    assert not list(root.rglob("*.json"))


def test_valid_real_verification_and_one_shot_admission(issued, monkeypatch):
    clock(monkeypatch)
    args = issued["envelope"], issued["trust"], issued["expected"]
    result = lr.signed_observation(*args)
    assert result["status"] == "PASS" and result["signature_verified"]
    assert not result["native_acceptance"] and not result["action_authority"]
    latest = issued["tmp"] / "latest.json"
    assert lr.admit_signed_observation(latest, *args)["admitted"]
    with pytest.raises(ValueError, match="replay"):
        lr.admit_signed_observation(latest, *args)


def test_signed_unknown_never_promoted(issued):
    issued["payload"]["status"] = "UNKNOWN"
    envelope = sr.sign(issued["payload"], issued["trust"], issued["key"], now=NOW)
    assert (
        lr.signed_observation(envelope, issued["trust"], issued["expected"], now=NOW)[
            "status"
        ]
        == "UNKNOWN"
    )


native_source = fixtures.native_source


def test_issuer_expiry_during_final_installation_read_refuses(
    native_source, monkeypatch
):
    current = clock(monkeypatch)
    import system_contract

    original = system_contract.verify_native_release_inventory
    calls = []

    def checked(*a, **kw):
        result = original(*a, **kw)
        calls.append(True)
        if len(calls) == 2:
            current[0] = NOW + timedelta(seconds=601)
        return result

    monkeypatch.setattr(system_contract, "verify_native_release_inventory", checked)
    data = native_source
    with pytest.raises(ValueError, match="stale|expir|lifetime|validity"):
        lr.issue_signed_observation(
            data["receipt"],
            data["source"],
            data["plugin"],
            data["transcript_root"],
            data["trust"],
            data["expected"],
            data["key"],
            expires_at=fixtures.moment(600),
        )


def test_cli_owner_final_input_reread_cannot_report_expired_pass(issued, monkeypatch):
    import json
    import conformance

    current = clock(monkeypatch)
    paths = []
    for name in ("envelope", "trust", "expected"):
        p = issued["tmp"] / (name + ".json")
        p.write_text(json.dumps(issued[name]))
        paths.append(p)
    original = sr.read_regular
    reads = []

    def read(p, **kw):
        raw = original(p, **kw)
        reads.append(True)
        if len(reads) == 9:
            current[0] = NOW + timedelta(seconds=601)
        return raw

    monkeypatch.setattr(sr, "read_regular", read)
    checks = conformance.signed_receipt_checks(*paths)
    assert any(row.ok is False for row in checks)
    assert not any(
        row.name == "signed-observation.status" and row.ok is True for row in checks
    )


def test_expiry_after_record_creation_retains_unresolved_consumed_event(
    issued, monkeypatch
):
    import os

    current = clock(monkeypatch)
    latest = issued["tmp"] / "latest.json"
    original = os.write

    def write(fd, data):
        result = original(fd, data)
        if bytes(data).startswith(b'{"envelope":'):
            current[0] = NOW + timedelta(seconds=601)
        return result

    with monkeypatch.context() as patch:
        patch.setattr(os, "write", write)
        with pytest.raises(ValueError, match="stale|expir|lifetime|validity"):
            lr.admit_signed_observation(
                latest, issued["envelope"], issued["trust"], issued["expected"]
            )
    records = list(lr.receipt_registry_root(latest, "codex").rglob("*.json"))
    assert len(records) == 1 and records[0].stat().st_size > 0
    current[0] = NOW
    with pytest.raises(ValueError, match="replay"):
        lr.admit_signed_observation(
            latest, issued["envelope"], issued["trust"], issued["expected"]
        )


def test_expiry_while_pinning_registry_parent_has_no_creation_effect(
    issued, monkeypatch
):
    from contextlib import contextmanager

    current = clock(monkeypatch)
    original = sr.held_directory

    @contextmanager
    def held(path):
        with original(path) as value:
            current[0] = NOW + timedelta(seconds=601)
            yield value

    monkeypatch.setattr(sr, "held_directory", held)
    latest = issued["tmp"] / "latest.json"
    with pytest.raises(ValueError, match="stale|expir|lifetime|validity"):
        lr.admit_signed_observation(
            latest, issued["envelope"], issued["trust"], issued["expected"]
        )
    assert not lr.receipt_registry_root(latest, "codex").exists()


def test_signature_from_other_namespace_never_verifies(issued):
    from copy import deepcopy

    envelope = deepcopy(issued["envelope"])
    protected = {k: v for k, v in envelope.items() if k != "signature"}
    envelope["signature"] = sr._ssh(
        [
            "-Y",
            "sign",
            "-q",
            "-f",
            str(issued["key"]),
            "-n",
            "synthetic-unrelated-purpose",
        ],
        sr.canonical(protected),
    ).decode("ascii")
    with pytest.raises(ValueError, match="OpenSSH"):
        lr.signed_observation(envelope, issued["trust"], issued["expected"], now=NOW)

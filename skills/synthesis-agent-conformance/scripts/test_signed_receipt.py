"""Synthetic Ed25519 producer/consumer controls; no actual client acceptance."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib
import json
import os
from pathlib import Path
import subprocess
import stat
import signal
import time
import sys
import uuid

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import signed_receipt as sr
import live_receipt as lr

NOW = datetime(2026, 9, 27, 0, 0, tzinfo=timezone.utc)


def moment(delta=0):
    return (NOW + timedelta(seconds=delta)).isoformat()


@pytest.fixture
def issued(tmp_path):
    key = tmp_path / "synthetic-key"
    result = subprocess.run(
        [
            "/usr/bin/ssh-keygen",
            "-q",
            "-t",
            "ed25519",
            "-N",
            "",
            "-C",
            "",
            "-f",
            str(key),
        ],
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 0
    public = key.with_suffix(".pub").read_text().strip()
    payload = {
        "schema": sr.SCHEMA,
        "event": "SessionStart",
        "status": "PASS",
        "client": "codex",
        "source_sha256": "a" * 64,
        "installation_sha256": "b" * 64,
        "audience_sha256": "c" * 64,
        "session_id": str(uuid.uuid4()),
        "event_id": str(uuid.uuid4()),
        "challenge": str(uuid.uuid4()),
        "observed_at": moment(-60),
        "issued_at": moment(-10),
        "expires_at": moment(600),
    }
    trust = {
        "schema": 1,
        "generation": str(uuid.uuid4()),
        "audience_sha256": "c" * 64,
        "keys": [
            {
                "key_id": sr.public_key(public),
                "public_key": public,
                "provenance_sha256": "d" * 64,
                "clients": ["codex", "claude", "muse", "cursor", "copilot"],
                "sources": ["a" * 64],
                "installations": ["b" * 64],
                "not_before": moment(-3600),
                "not_after": moment(3600),
                "revoked": False,
            }
        ],
    }
    expected = {name: payload[name] for name in sr.BINDINGS}
    envelope = sr.sign(payload, trust, key, now=NOW)
    return {
        "key": key,
        "payload": payload,
        "trust": trust,
        "expected": expected,
        "envelope": envelope,
        "tmp": tmp_path,
    }


def observe(item, **kwargs):
    return lr.signed_observation(
        item["envelope"], item["trust"], item["expected"], now=NOW, **kwargs
    )


@pytest.mark.parametrize("client", sorted(sr.CLIENTS))
def test_actual_signer_and_consumer_all_declared_clients(issued, client):
    issued["payload"]["client"] = issued["expected"]["client"] = client
    issued["envelope"] = sr.sign(
        issued["payload"], issued["trust"], issued["key"], now=NOW
    )
    result = observe(issued)
    assert result["signature_verified"] is True and result["status"] == "PASS"
    assert result["native_acceptance"] is False and result["action_authority"] is False
    encoded = sr.canonical(issued["envelope"])
    assert (
        str(issued["tmp"]).encode() not in encoded
        and b"prompt" not in encoded
        and b"transcript" not in encoded
    )


@pytest.mark.parametrize("status", ["UNKNOWN", "FAIL"])
def test_signed_unknown_and_failure_never_become_pass(issued, status):
    issued["payload"]["status"] = status
    issued["envelope"] = sr.sign(
        issued["payload"], issued["trust"], issued["key"], now=NOW
    )
    assert observe(issued)["status"] == status


@pytest.mark.parametrize(
    "mutate",
    [
        lambda x: x["envelope"]["payload"].update(status="UNKNOWN"),
        lambda x: x["envelope"]["payload"].update(prompt="private content"),
        lambda x: x["envelope"].update(extra=True),
        lambda x: x["envelope"].update(
            signature=x["envelope"]["signature"].replace("A", "B", 1)
        ),
        lambda x: x["envelope"].update(key_id="e" * 64),
        lambda x: x["expected"].update(challenge=str(uuid.uuid4())),
        lambda x: x["expected"].update(session_id=str(uuid.uuid4())),
        lambda x: x["expected"].update(event_id=str(uuid.uuid4())),
        lambda x: x["expected"].update(client="claude"),
        lambda x: x["expected"].update(audience_sha256="e" * 64),
        lambda x: x["expected"].update(source_sha256="e" * 64),
        lambda x: x["expected"].update(installation_sha256="e" * 64),
        lambda x: x["trust"]["keys"][0].update(revoked=True),
        lambda x: x["trust"]["keys"][0].update(revoked=0),
        lambda x: x["trust"]["keys"][0].update(clients=["claude"]),
        lambda x: x["trust"]["keys"][0].update(sources=["e" * 64]),
        lambda x: x["trust"]["keys"][0].update(installations=["e" * 64]),
        lambda x: x["trust"]["keys"][0].update(not_after=moment(-1)),
        lambda x: x["trust"]["keys"][0].update(not_before=moment(1)),
        lambda x: x["trust"]["keys"][0].update(provenance_sha256="unverified"),
        lambda x: x["trust"]["keys"].append(deepcopy(x["trust"]["keys"][0])),
        lambda x: x["trust"].update(schema=True),
        lambda x: x["trust"].update(audience_sha256="e" * 64),
        lambda x: x["trust"]["keys"][0].update(
            public_key=x["trust"]["keys"][0]["public_key"] + " injected"
        ),
    ],
)
def test_signature_scope_and_revocation_refuse(issued, mutate):
    mutate(issued)
    with pytest.raises((ValueError, OSError)):
        observe(issued)


@pytest.mark.parametrize(
    "field,value",
    [
        ("issued_at", moment(1)),
        ("expires_at", moment(0)),
        ("observed_at", moment(-86401)),
        ("observed_at", moment(1)),
        ("issued_at", "2026-09-27T00:00:00"),
        ("status", "verified"),
        ("event", "arbitrary"),
    ],
)
def test_producer_refuses_invalid_or_stale_observation(issued, field, value):
    issued["payload"][field] = value
    with pytest.raises(ValueError):
        sr.sign(issued["payload"], issued["trust"], issued["key"], now=NOW)


def test_revoked_signature_refused_after_initial_success(issued):
    assert observe(issued)["signature_verified"]
    issued["trust"]["keys"][0]["revoked"] = True
    with pytest.raises(ValueError, match="revoked"):
        observe(issued)


def test_existing_registry_admission_is_one_shot_and_survives_cold_reload(issued):
    latest = issued["tmp"] / "latest.json"
    result = lr.admit_signed_observation(
        latest, issued["envelope"], issued["trust"], issued["expected"], now=NOW
    )
    assert result["admitted"] is True
    cold = importlib.reload(lr)
    with pytest.raises(ValueError, match="replay"):
        cold.admit_signed_observation(
            latest, issued["envelope"], issued["trust"], issued["expected"], now=NOW
        )
    assert not latest.exists()
    assert (
        cold.session_receipt_path(latest, "codex", issued["payload"]["session_id"])
        is None
    )
    records = list(lr.receipt_registry_root(latest, "codex").rglob("*.json"))
    assert len(records) == 1
    assert json.loads(records[0].read_bytes())["envelope"] == issued["envelope"]


def test_reissued_challenge_cannot_replay_same_event(issued):
    latest = issued["tmp"] / "latest.json"
    lr.admit_signed_observation(
        latest, issued["envelope"], issued["trust"], issued["expected"], now=NOW
    )
    issued["payload"]["challenge"] = issued["expected"]["challenge"] = str(uuid.uuid4())
    issued["envelope"] = sr.sign(
        issued["payload"], issued["trust"], issued["key"], now=NOW
    )
    with pytest.raises(ValueError, match="replay"):
        lr.admit_signed_observation(
            latest, issued["envelope"], issued["trust"], issued["expected"], now=NOW
        )


def test_invalid_signature_has_no_registry_effect(issued):
    latest = issued["tmp"] / "latest.json"
    issued["envelope"]["signature"] = "invalid"
    with pytest.raises(ValueError):
        lr.admit_signed_observation(
            latest, issued["envelope"], issued["trust"], issued["expected"], now=NOW
        )
    assert not lr.receipt_registry_root(latest, "codex").exists()


def test_registry_symlink_refuses_without_foreign_writes(issued):
    latest = issued["tmp"] / "latest.json"
    foreign = issued["tmp"] / "foreign"
    foreign.mkdir()
    lr.receipt_registry_root(latest, "codex").symlink_to(
        foreign, target_is_directory=True
    )
    with pytest.raises(OSError):
        lr.admit_signed_observation(
            latest, issued["envelope"], issued["trust"], issued["expected"], now=NOW
        )
    assert list(foreign.iterdir()) == []


def test_partial_interrupted_record_remains_consumed(issued, monkeypatch):
    latest = issued["tmp"] / "latest.json"
    original = os.write

    def fail(fd, content):
        if bytes(content).startswith(b'{"envelope":'):
            original(fd, content[:10])
            raise OSError("synthetic interrupted write")
        return original(fd, content)

    with monkeypatch.context() as patch:
        patch.setattr(os, "write", fail)
        with pytest.raises(OSError, match="interrupted"):
            lr.admit_signed_observation(
                latest, issued["envelope"], issued["trust"], issued["expected"], now=NOW
            )
    with pytest.raises(ValueError, match="replay"):
        lr.admit_signed_observation(
            latest, issued["envelope"], issued["trust"], issued["expected"], now=NOW
        )
    assert len(list(lr.receipt_registry_root(latest, "codex").rglob("*.json"))) == 1


@pytest.mark.parametrize(
    "kind", ["symlink", "hardlink", "fifo", "directory", "huge", "ancestor-link"]
)
def test_bounded_input_refuses_aliases_special_nodes_and_size(tmp_path, kind):
    path = tmp_path / "input"
    if kind == "symlink":
        (tmp_path / "foreign").write_text("x")
        path.symlink_to(tmp_path / "foreign")
    elif kind == "hardlink":
        path.write_text("x")
        os.link(path, tmp_path / "foreign")
    elif kind == "fifo":
        os.mkfifo(path)
    elif kind == "directory":
        path.mkdir()
    elif kind == "huge":
        path.write_bytes(b"x" * (sr.MAX_BYTES + 1))
    else:
        (tmp_path / "foreign").mkdir()
        (tmp_path / "foreign/file").write_text("x")
        path.symlink_to(tmp_path / "foreign", target_is_directory=True)
        path = path / "file"
    with pytest.raises((ValueError, OSError)):
        sr.read_regular(path)


@pytest.mark.parametrize(
    "raw",
    [b'{"schema":1,"schema":2}', b'{"x":NaN}', b"[" * 2000, b"x" * (sr.MAX_BYTES + 1)],
)
def test_strict_json_refuses_ambiguity_depth_and_excess(raw):
    with pytest.raises(ValueError):
        sr.strict_json(raw)


@pytest.fixture
def native_source(issued):
    import shutil

    sys.path.insert(
        0, str(Path(__file__).resolve().parents[2] / "synthesis-onboarding/scripts")
    )
    import system_contract as contract

    source = issued["tmp"] / "source"
    (source / ".codex-plugin").mkdir(parents=True)
    (source / ".codex-plugin/plugin.json").write_text(
        json.dumps({"name": "synthesis-skills", "version": "9.9.9"})
    )
    (source / "hooks").mkdir()
    (source / "hooks/hooks.json").write_text(
        json.dumps({"hooks": {"SessionStart": []}})
    )
    plugin = issued["tmp"] / "plugin"
    shutil.copytree(source, plugin)
    digest = contract.canonical_tree_digest(source)
    issued["expected"]["source_sha256"] = issued["expected"]["installation_sha256"] = (
        digest
    )
    issued["trust"]["keys"][0]["sources"] = issued["trust"]["keys"][0][
        "installations"
    ] = [digest]
    transcript_root = issued["tmp"] / "native"
    transcript_root.mkdir()
    transcript = transcript_root / "session.jsonl"
    transcript.write_text(
        json.dumps(
            {
                "type": "session_meta",
                "payload": {"id": issued["expected"]["session_id"]},
            }
        )
        + "\n"
    )
    event = {
        "receipt_schema": 2,
        "hook_event_name": "SessionStart",
        "client": "codex",
        "session_id": issued["expected"]["session_id"],
        "receipt_event_id": issued["expected"]["event_id"],
        "plugin_version": "9.9.9",
        "plugin_root": str(plugin),
        "recorded_at": moment(-30),
        "transcript_path": str(transcript),
        "provenance_env": "codex-transcript",
        "transcript_bound_at_record": True,
    }
    receipt = issued["tmp"] / "native-receipt.json"
    receipt.write_text(json.dumps(event))
    return {
        **issued,
        "source": source,
        "plugin": plugin,
        "transcript_root": transcript_root,
        "transcript": transcript,
        "receipt": receipt,
        "event": event,
    }


def native_issue(data):
    return lr.issue_signed_observation(
        data["receipt"],
        data["source"],
        data["plugin"],
        data["transcript_root"],
        data["trust"],
        data["expected"],
        data["key"],
        expires_at=moment(600),
        now=NOW,
    )


def test_actual_native_receipt_projection_uses_install_and_transcript_owners(
    native_source,
):
    envelope = native_issue(native_source)
    result = lr.signed_observation(
        envelope, native_source["trust"], native_source["expected"], now=NOW
    )
    assert result["status"] == "PASS" and result["native_acceptance"] is False
    assert str(native_source["transcript"]) not in json.dumps(envelope)


@pytest.mark.parametrize(
    "kind,status",
    [
        ("missing", "UNKNOWN"),
        ("empty", "UNKNOWN"),
        ("conflict", "FAIL"),
        ("malformed", "FAIL"),
    ],
)
def test_native_projection_retains_actual_binding_outcome(native_source, kind, status):
    transcript = native_source["transcript"]
    if kind == "missing":
        transcript.unlink()
    elif kind == "empty":
        transcript.write_text("")
    elif kind == "conflict":
        transcript.write_text(
            json.dumps({"type": "session_meta", "payload": {"id": str(uuid.uuid4())}})
            + "\n"
        )
    else:
        transcript.write_text("{not json}\n")
    envelope = native_issue(native_source)
    assert envelope["payload"]["status"] == status


@pytest.mark.parametrize(
    "kind", ["source", "installation", "receipt", "version", "execution", "client"]
)
def test_native_producer_refuses_wrong_existing_evidence(native_source, kind):
    if kind == "source":
        (native_source["source"] / "extra").write_text("x")
    elif kind == "installation":
        (native_source["plugin"] / "extra").write_text("x")
    else:
        event = native_source["event"]
        if kind == "receipt":
            event["receipt_event_id"] = str(uuid.uuid4())
        elif kind == "version":
            event["plugin_version"] = "9.9.8"
        elif kind == "execution":
            event["execution_root"] = str(native_source["tmp"])
        else:
            native_source["expected"]["client"] = "cursor"
        native_source["receipt"].write_text(json.dumps(event))
    with pytest.raises(ValueError):
        native_issue(native_source)


def test_native_producer_rechecks_before_emitting(native_source, monkeypatch):
    original = sr.sign

    def raced(*args, **kwargs):
        result = original(*args, **kwargs)
        native_source["transcript"].write_text("bad\n")
        return result

    monkeypatch.setattr(sr, "sign", raced)
    with pytest.raises(ValueError, match="changed"):
        native_issue(native_source)


def test_real_conformance_read_and_admission_reject_late_trust_revocation(
    issued, monkeypatch
):
    import conformance

    for name in ("envelope", "trust", "expected"):
        (issued["tmp"] / (name + ".json")).write_text(json.dumps(issued[name]))
    original = lr.signed_observation

    def raced(*args, **kwargs):
        result = original(*args, **{**kwargs, "now": NOW})
        revoked = deepcopy(issued["trust"])
        revoked["keys"][0]["revoked"] = True
        (issued["tmp"] / "trust.json").write_text(json.dumps(revoked))
        return result

    monkeypatch.setattr(lr, "signed_observation", raced)
    latest = issued["tmp"] / "latest.json"
    checks = conformance.signed_receipt_checks(
        issued["tmp"] / "envelope.json",
        issued["tmp"] / "trust.json",
        issued["tmp"] / "expected.json",
        registry=latest,
    )
    assert any(row.ok is False for row in checks)
    assert any("input changed" in row.detail for row in checks)
    assert not list(issued["tmp"].glob("**/signed-observations-v1/**/*.json"))


def test_concurrent_admission_cannot_consume_same_event_twice(issued):
    from concurrent.futures import ThreadPoolExecutor

    latest = issued["tmp"] / "latest.json"

    def attempt():
        try:
            return lr.admit_signed_observation(
                latest, issued["envelope"], issued["trust"], issued["expected"], now=NOW
            )["admitted"]
        except ValueError as exc:
            assert "replay" in str(exc)
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: attempt(), range(2))) == [False, True]
    assert len(list(lr.receipt_registry_root(latest, "codex").rglob("*.json"))) == 1


def test_missing_crypto_helper_never_accepts_or_admits(issued, monkeypatch):
    def refuse(*args, **kwargs):
        raise FileNotFoundError("synthetic unavailable helper")

    monkeypatch.setattr(subprocess, "Popen", refuse)
    with pytest.raises(FileNotFoundError):
        lr.admit_signed_observation(
            issued["tmp"] / "latest.json",
            issued["envelope"],
            issued["trust"],
            issued["expected"],
            now=NOW,
        )
    assert not lr.receipt_registry_root(issued["tmp"] / "latest.json", "codex").exists()


def test_new_signature_cannot_silently_convert_local_unknown_into_hook_live_pass(
    issued,
):
    import conformance

    signed = issued["tmp"] / "signed.json"
    signed.write_text(json.dumps(issued["envelope"]))
    checks = []
    conformance._receipt_check(
        checks, "hook-live.synthetic", signed, expected_client="codex"
    )
    assert checks and all(row.ok is False for row in checks)


def test_actual_cli_unsigned_or_bad_signature_refuses_without_registry(issued):
    current = datetime.now(timezone.utc)
    issued["payload"].update(
        observed_at=(current - timedelta(seconds=1)).isoformat(),
        issued_at=current.isoformat(),
        expires_at=(current + timedelta(minutes=1)).isoformat(),
    )
    issued["trust"]["keys"][0].update(
        not_before=(current - timedelta(minutes=1)).isoformat(),
        not_after=(current + timedelta(minutes=2)).isoformat(),
    )
    issued["envelope"] = sr.sign(
        issued["payload"], issued["trust"], issued["key"], now=current
    )
    for name in ("envelope", "trust", "expected"):
        (issued["tmp"] / (name + ".json")).write_text(json.dumps(issued[name]))
    command = [
        sys.executable,
        str(Path(__file__).parent / "conformance.py"),
        "signed-receipt",
        "--json",
        "--signed-envelope",
        str(issued["tmp"] / "envelope.json"),
        "--signed-trust",
        str(issued["tmp"] / "trust.json"),
        "--signed-bindings",
        str(issued["tmp"] / "expected.json"),
    ]
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    accepted = subprocess.run(
        command, capture_output=True, text=True, timeout=30, env=env
    )
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    assert "signature" in accepted.stdout and "native acceptance" in accepted.stdout
    issued["envelope"]["payload"]["status"] = "UNKNOWN"
    (issued["tmp"] / "envelope.json").write_text(json.dumps(issued["envelope"]))
    refused = subprocess.run(
        command, capture_output=True, text=True, timeout=30, env=env
    )
    assert refused.returncode == 1 and "FAIL" in refused.stdout


@pytest.mark.parametrize(
    "mutate",
    [
        lambda item: item["trust"].update(generation=str(uuid.uuid4())),
        lambda item: item["trust"]["keys"][0].update(provenance_sha256="e" * 64),
        lambda item: item["envelope"].update(trust_generation=str(uuid.uuid4())),
        lambda item: item["envelope"].update(signer_provenance_sha256="e" * 64),
    ],
)
def test_signature_binds_exact_signer_provenance_and_trust_generation(issued, mutate):
    mutate(issued)
    with pytest.raises(ValueError):
        observe(issued)


def test_unprotected_private_key_is_not_implicitly_repaired(issued):
    issued["key"].chmod(0o644)
    with pytest.raises(ValueError, match="permission"):
        sr.sign(issued["payload"], issued["trust"], issued["key"], now=NOW)
    assert issued["key"].stat().st_mode & 0o777 == 0o644


@pytest.mark.parametrize("attack", ["replace", "hardlink", "mode"])
def test_admission_revalidates_the_actual_record_after_fsync(
    issued, monkeypatch, attack
):
    latest = issued["tmp"] / "latest.json"
    record = (
        lr.receipt_registry_root(latest, "codex")
        / "signed-observations-v1/codex"
        / issued["expected"]["session_id"]
        / (issued["expected"]["event_id"] + ".json")
    )
    original = os.fsync
    did = []

    def raced(fd):
        original(fd)
        if stat.S_ISREG(os.fstat(fd).st_mode) and record.exists() and not did:
            did.append(True)
            if attack == "replace":
                record.rename(record.with_suffix(".retained"))
                record.write_text("foreign changed observation")
            elif attack == "hardlink":
                os.link(record, record.with_suffix(".foreign-alias"))
            else:
                record.chmod(0o666)

    with monkeypatch.context() as patch:
        patch.setattr(os, "fsync", raced)
        with pytest.raises(ValueError, match="record"):
            lr.admit_signed_observation(
                latest, issued["envelope"], issued["trust"], issued["expected"], now=NOW
            )
    assert did
    if attack == "replace":
        assert record.read_text() == "foreign changed observation"


def helper(tmp_path, program):
    p = tmp_path / "ssh-keygen"
    p.write_text("#!" + sys.executable + "\n" + program)
    p.chmod(0o700)
    return p


@pytest.mark.parametrize("kind", ["output", "deadline", "nonzero", "interrupt"])
def test_actual_helper_cleanup_is_finite(tmp_path, monkeypatch, kind):
    program = {
        "output": 'import sys;sys.stdout.write("x"*100000)\n',
        "deadline": "import time;time.sleep(20)\n",
        "nonzero": 'import sys;sys.stderr.write("SYNTHETIC_PRIVATE_DIAGNOSTIC");sys.exit(7)\n',
        "interrupt": "import time;time.sleep(20)\n",
    }[kind]
    executable = helper(tmp_path, program)
    processes = []
    original = sr.subprocess.Popen

    def capture(*args, **kwargs):
        p = original(*args, **kwargs)
        processes.append(p)
        return p

    monkeypatch.setattr(sr.subprocess, "Popen", capture)
    if kind == "interrupt":

        def interrupt(*args, **kwargs):
            raise KeyboardInterrupt("synthetic interruption")

        monkeypatch.setattr(sr.selectors.DefaultSelector, "select", interrupt)
    start = time.monotonic()
    with pytest.raises((ValueError, KeyboardInterrupt)) as error:
        sr._ssh([], b"bounded", executable=str(executable))
    assert time.monotonic() - start < 8
    assert "SYNTHETIC_PRIVATE_DIAGNOSTIC" not in str(error.value)
    assert len(processes) == 1 and processes[0].poll() is not None
    with pytest.raises(ProcessLookupError):
        os.killpg(processes[0].pid, 0)


@pytest.mark.parametrize("stage", ["constructor", "registration"])
def test_helper_setup_failure_reaps_the_owned_child(tmp_path, monkeypatch, stage):
    executable = tmp_path / "ssh-keygen"
    executable.write_text("#!" + sys.executable + "\nimport time;time.sleep(20)\n")
    executable.chmod(0o700)
    processes = []
    original = sr.subprocess.Popen

    def capture(*args, **kwargs):
        process = original(*args, **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(sr.subprocess, "Popen", capture)
    selector = sr.selectors.DefaultSelector

    def fail(*args, **kwargs):
        raise OSError("synthetic selector setup refusal")

    if stage == "constructor":
        monkeypatch.setattr(sr.selectors, "DefaultSelector", fail)
    else:
        monkeypatch.setattr(selector, "register", fail)
    try:
        with pytest.raises(OSError, match="setup refusal"):
            sr._ssh([], b"", executable=str(executable))
        assert len(processes) == 1
        assert processes[0].poll() is not None, (
            "owned child survived selector setup failure"
        )
    finally:
        for process in processes:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=3)


def test_ephemeral_callback_candidate_cannot_issue_signed_native_observation(
    native_source,
):
    event = json.loads(native_source["receipt"].read_text())
    event.update(
        provenance_env="codex-callback-candidate",
        callback_candidate=True,
        transcript_bound_at_record=False,
        transcript_path=None,
    )
    native_source["receipt"].write_text(json.dumps(event))
    with pytest.raises(ValueError, match="provenance"):
        native_issue(native_source)

"""Actual producer and shared consumer report boundaries; synthetic identities only."""

import copy
import json
from datetime import timedelta
import os
import pytest
import report_contract as r
import conformance

NOW = r.timestamp("2026-09-27T03:00:00Z")
BINDING = {
    "machine_sha256": "0" * 64,
    "source_root": "/fixture/source",
    "source_binding_sha256": "1" * 64,
    "producer_sha256": "2" * 64,
    "project": "/fixture/project",
    "repo_root": "/fixture/repository",
    "profile": "public",
}


def report():
    return r.build(
        [
            conformance.Check(p + ".fixture", True, "synthetic", plane=p).serialized()
            for p in r.PLANES
        ],
        BINDING,
        "all",
        NOW,
    )


def test_contract_true_all_and_source_scope():
    assert r.validate(report(), expected=BINDING, now=NOW, fresh=True)["ok"] is True
    p = r.build(
        [
            conformance.Check(
                "source.one", True, "synthetic", plane="source"
            ).serialized()
        ],
        BINDING,
        now=NOW,
    )
    assert p["status"] == "PASS" and p["planes"]["native"] == "UNKNOWN"


def test_unknown_and_fail_remain_distinct():
    for ok, status in [(None, "UNKNOWN"), (False, "FAIL")]:
        p = r.build(
            [
                conformance.Check(
                    "native.one", ok, "synthetic", plane="native"
                ).serialized()
            ],
            BINDING,
            now=NOW,
        )
        assert p["status"] == status and p["ok"] is False


@pytest.mark.parametrize(
    "mutation",
    [
        lambda p: p.update(schema_version=True),
        lambda p: p.update(schema_version=2),
        lambda p: p.update(schema_sha256="f" * 64),
        lambda p: p.update(unexpected="x"),
        lambda p: p["checks"][0].update(plane="future"),
        lambda p: p["checks"][0].update(ok=None),
        lambda p: p["checks"][0].update(status="UNKNOWN"),
        lambda p: p["checks"][0].update(outcome="UNKNOWN"),
        lambda p: p["checks"].append(copy.deepcopy(p["checks"][0])),
        lambda p: p["checks"].clear(),
        lambda p: p["planes"].update(native="UNKNOWN"),
        lambda p: p["planes"].update(future="PASS"),
        lambda p: p.update(checked_at="2026-02-30T00:00:00Z"),
        lambda p: p.update(expires_at="2026-09-28T03:00:00Z"),
        lambda p: p["checks"][0].update(detail="x" * 16385),
        lambda p: p["checks"][0].update(raw_command="private"),
    ],
)
def test_malformed_or_forged_report_refuses(mutation):
    p = report()
    mutation(p)
    with pytest.raises(r.ReportError):
        r.validate(p)


@pytest.mark.parametrize(
    "key",
    [
        "machine_sha256",
        "source_root",
        "source_binding_sha256",
        "producer_sha256",
        "project",
        "repo_root",
        "profile",
    ],
)
def test_exact_identity_rejects_stale_selection(key):
    expect = copy.deepcopy(BINDING)
    expect[key] = "changed"
    with pytest.raises(r.ReportError, match="identity"):
        r.validate(report(), expected=expect)


@pytest.mark.parametrize("offset", [14400, 14401, -6, -86400])
def test_freshness_rejects_future_or_expired(offset):
    with pytest.raises(r.ReportError):
        r.validate(report(), now=NOW + timedelta(seconds=offset), fresh=True)


def test_duplicate_json_and_nonfinite_refused():
    for data in [
        b'{"x":1,"x":2}',
        b'{"x":NaN}',
        b'{"schema_version":1.0}',
        b'{"schema_version":1e0}',
    ]:
        with pytest.raises(r.ReportError):
            r.decode(data)


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "fifo", "large"])
def test_reader_never_follows_special_input(tmp_path, kind):
    p = tmp_path / "report"
    q = tmp_path / "other"
    q.write_text("private")
    if kind == "symlink":
        p.symlink_to(q)
    elif kind == "hardlink":
        os.link(q, p)
    elif kind == "fifo":
        os.mkfifo(p)
    else:
        p.write_bytes(b"x" * 20)
    with pytest.raises(r.ReportError):
        r.read_bytes(p, 10)


def test_producer_actual_render_uses_contract(tmp_path, capsys):
    target = tmp_path / "report.json"
    assert (
        conformance.render(
            [conformance.Check("hook-live.one", None, "missing", plane="live")],
            True,
            target,
            identity=BINDING,
        )
        == 1
    )
    saved = r.decode(target.read_bytes())
    assert saved == json.loads(capsys.readouterr().out)
    assert saved["checks"][0]["plane"] == "native" and saved["status"] == "UNKNOWN"


def test_schema_is_self_validating():
    p = report()
    assert r.decode(r.read_bytes(r.SCHEMA_PATH))["$id"] == p["schema_id"]
    assert p["schema_sha256"] == r.digest(r.SCHEMA_PATH.read_bytes())


def test_producer_size_refusal_preserves_existing_report(tmp_path):
    path = tmp_path / "report.json"
    path.write_bytes(b"retained earlier evidence")
    checks = [
        conformance.Check("source." + str(i), True, "x" * 16000, plane="source")
        for i in range(300)
    ]
    with pytest.raises(r.ReportError, match="byte ceiling"):
        conformance.render(checks, True, path, identity=BINDING)
    assert path.read_bytes() == b"retained earlier evidence"


@pytest.mark.parametrize(
    "raw", [b"[" * 33 + b"0" + b"]" * 33, b"[" * 2000 + b"0" + b"]" * 2000]
)
def test_json_depth_is_finite_and_refused(raw):
    with pytest.raises(r.ReportError):
        r.decode(raw)


def test_actual_source_checks_have_unique_relative_configuration_ids():
    from pathlib import Path
    source = Path(__file__).resolve().parents[3]
    checks = conformance.source_checks(source)
    names = [item.name for item in checks]
    assert len(names) == len(set(names))
    assert "source.json..agents/plugins/marketplace.json" in names
    assert "source.json..claude-plugin/marketplace.json" in names
    payload = r.build([item.serialized() for item in checks], BINDING, "source", NOW)
    assert len(payload["checks"]) == len(checks)


@pytest.mark.parametrize("status", ["WARN", "UNSUPPORTED"])
def test_all_scope_requires_required_success_in_every_plane(status):
    p = report()
    p["checks"][2].update(ok=False if status == "WARN" else None,
                          required=False, status=status)
    rebuilt = r.build(p["checks"], BINDING, "all", NOW)
    assert rebuilt["status"] == "UNKNOWN" and rebuilt["ok"] is False
    forged = copy.deepcopy(rebuilt)
    forged.update(status="PASS", ok=True)
    with pytest.raises(r.ReportError, match="aggregate"):
        r.validate(forged)
    # The missing plane does not invent a required failure or invalidate source scope.
    source_scope = r.build(p["checks"], BINDING, "source", NOW)
    assert source_scope["status"] == "PASS"


@pytest.mark.parametrize("raw", [b'{"x":"\xff"}', b'{"x":"\xc3("}'])
def test_invalid_utf8_evidence_is_never_replaced(raw):
    with pytest.raises(r.ReportError, match="invalid"):
        r.decode(raw)

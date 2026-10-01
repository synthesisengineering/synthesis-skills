import sys
import json
import os
import zipfile
import uuid
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pytest

S = Path(__file__).resolve().parent
sys.path.insert(0, str(S))
import vendor_bundle as vb  # noqa: E402
import signed_receipt as sr  # noqa: E402
from test_vendor_bundle import source as source_fixture, request, archive  # noqa: E402

source = source_fixture


def public_transport(monkeypatch, source):
    original = archive(source)
    metadata = json.dumps(
        {
            "tag_name": "v1.2.3",
            "draft": False,
            "prerelease": False,
            "published_at": "2026-09-26T00:00:00Z",
        }
    ).encode()
    calls = []

    def fetch(url, limit):
        calls.append(url)
        assert url.startswith(
            "https://api.github.com/repos/synthesisengineering/synthesis-skills/"
        )
        return original if "/tarball/" in url else metadata

    monkeypatch.setattr(vb, "_fetch", fetch)
    return calls


def test_actual_public_release_owner_exports_exact_clean_source(
    source, tmp_path, monkeypatch
):
    calls = public_transport(monkeypatch, source)
    bundle = vb.prepare(source, request(), verify_release=True)
    out = tmp_path / "public.zip"
    vb.export(source, bundle, out, verify_release=True)
    assert len(calls) == 4
    with zipfile.ZipFile(out) as z:
        record = json.loads(z.read("review.json"))
        assert record["source_export"] == "VERIFIED_PUBLIC_RELEASE"
        assert z.read("source/SUPPORT.md") == (source / "SUPPORT.md").read_bytes()
    result = vb.verify_export(out)
    assert (
        result["native_revalidation_required"] and result["contact_authorized"] is False
    )


def test_unrelated_source_refuses_public_release_equality(
    source, tmp_path, monkeypatch
):
    public_transport(monkeypatch, source)
    (source / "untracked-private").write_text("synthetic private content")
    bundle = vb.prepare(source, request())
    with pytest.raises(ValueError, match="membership"):
        vb.export(source, bundle, tmp_path / "refused.zip", verify_release=True)
    assert not (tmp_path / "refused.zip").exists()


def test_default_metadata_draft_contains_no_incidental_source_names(source, tmp_path):
    (source / "unrelated-private-name").write_text("synthetic private content")
    bundle = vb.prepare(source, request())
    out = tmp_path / "draft.zip"
    vb.export(source, bundle, out)
    with zipfile.ZipFile(out) as z:
        assert z.namelist() == ["review.json"]
        raw = z.read("review.json")
        assert b"unrelated-private-name" not in raw
        assert b"synthetic private content" not in raw
        assert json.loads(raw)["source_files"] == []


def rewrite_zip(path, mutate):
    with zipfile.ZipFile(path) as z:
        members = [(info, z.read(info)) for info in z.infolist()]
    result = path.with_name("mutated.zip")
    with zipfile.ZipFile(result, "w") as z:
        for info, raw in members:
            if info.filename == "review.json":
                body = json.loads(raw)
                mutate(body)
                body.pop("bundle_digest")
                body["bundle_digest"] = vb.digest(body)
                raw = json.dumps(body).encode()
            z.writestr(info, raw)
    return result


@pytest.mark.parametrize(
    "field", ["contact_authorized", "submission_authorized", "submission_ready"]
)
def test_archive_custody_refuses_forged_authority(source, tmp_path, field):
    out = tmp_path / "draft.zip"
    vb.export(source, vb.prepare(source, request()), out)
    bad = rewrite_zip(out, lambda b: b.__setitem__(field, True))
    with pytest.raises(ValueError):
        vb.verify_export(bad)


def test_portable_signer_observation_is_not_native_or_send_authority(source, tmp_path):
    sys.path.insert(0, str(S.parents[1] / "synthesis-onboarding/scripts"))
    from system_contract import canonical_tree_digest

    key = tmp_path / "synthetic-key"
    proc = subprocess.run(
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
    assert proc.returncode == 0
    pub = key.with_suffix(".pub").read_text().strip()
    now = datetime.now(timezone.utc)
    def instant(seconds):
        return (now + timedelta(seconds=seconds)).isoformat()
    source_sha = canonical_tree_digest(source)
    payload = {
        "schema": sr.SCHEMA,
        "event": "SessionStart",
        "status": "PASS",
        "client": "codex",
        "source_sha256": source_sha,
        "installation_sha256": "b" * 64,
        "audience_sha256": "c" * 64,
        "session_id": str(uuid.uuid4()),
        "event_id": str(uuid.uuid4()),
        "challenge": str(uuid.uuid4()),
        "observed_at": instant(-60),
        "issued_at": instant(-10),
        "expires_at": instant(600),
    }
    trust = {
        "schema": 1,
        "generation": str(uuid.uuid4()),
        "audience_sha256": "c" * 64,
        "keys": [
            {
                "key_id": sr.public_key(pub),
                "public_key": pub,
                "provenance_sha256": "d" * 64,
                "clients": ["codex"],
                "sources": [source_sha],
                "installations": ["b" * 64],
                "not_before": instant(-3600),
                "not_after": instant(3600),
                "revoked": False,
            }
        ],
    }
    expected = {k: payload[k] for k in sr.BINDINGS}
    envelope = sr.sign(payload, trust, key)
    context = {}
    for name, value in [
        ("envelope", envelope),
        ("trust", trust),
        ("bindings", expected),
    ]:
        path = tmp_path / (name + ".json")
        path.write_text(json.dumps(value))
        path.chmod(0o600)
        context[name] = str(path)
    result = vb.prepare(source, request(), portable_context={"codex": context})
    assert result["portable_observations"]["codex"] == {
        "signature_verified": True,
        "status": "PASS",
        "native_acceptance": False,
        "action_authority": False,
    }
    assert result["gates"]["native.codex"] == "UNKNOWN"
    assert result["submission_authorized"] is False
    envelope["signature"] = "forged"
    Path(context["envelope"]).write_text(json.dumps(envelope))
    with pytest.raises(ValueError):
        vb.prepare(source, request(), portable_context={"codex": context})


def test_output_foreign_hardlink_does_not_receive_writes(source, tmp_path):
    other = tmp_path / "foreign"
    other.write_bytes(b"keep")
    out = tmp_path / "archive"
    os.link(other, out)
    with pytest.raises(FileExistsError):
        vb.export(source, vb.prepare(source, request()), out)
    assert other.read_bytes() == b"keep"


def test_positive_inventory_rejects_late_source_mode_drift(source, monkeypatch):
    original = vb.read_regular
    target = source / "SUPPORT.md"

    def read(path, **kwargs):
        if path == target:
            path.chmod(0o755)
        return original(path, **kwargs)

    monkeypatch.setattr(vb, "read_regular", read)
    row = next(x for x in vb.source_inventory(source) if x["path"] == "SUPPORT.md")
    assert row["mode"] == 0o755

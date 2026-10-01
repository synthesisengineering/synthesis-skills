"""Actual bundle consumer and public synthetic archive controls."""

import io
import json
from pathlib import Path
import tarfile
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vendor_bundle as vb


def test_owner_interruption_propagates_without_unknown_downgrade(monkeypatch, tmp_path):
    scripts = vb.HERE.parents[1] / "synthesis-project-management" / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    import coordination_process

    def interrupted(*args, **kwargs):
        raise coordination_process.EffectInterrupted("synthetic interrupt")

    monkeypatch.setattr(coordination_process, "run", interrupted)
    with pytest.raises(coordination_process.EffectInterrupted):
        vb.source_conformance(tmp_path)


@pytest.fixture
def source(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    for folder in (".claude-plugin", ".codex-plugin", "skills/example", "docs"):
        (root / folder).mkdir(parents=True)
    for name in (".claude-plugin/plugin.json", ".codex-plugin/plugin.json"):
        (root / name).write_text(
            json.dumps(
                {
                    "name": "synthesis-skills",
                    "version": "1.2.3",
                    "description": "Synthetic qualification",
                    "license": "Apache-2.0 AND CC0-1.0",
                }
            )
        )
    for name in (
        "LICENSE-APACHE",
        "LICENSE-CC0",
        "SUPPORT.md",
        "CONTRIBUTING.md",
        "GOVERNANCE.md",
    ):
        (root / name).write_text("Synthetic qualification fixture\n")
    (root / "skills/example/SKILL.md").write_text(
        "---\nname: example\ndescription: Synthetic qualification\n---\n# Example\n"
    )
    return root


def request():
    return {
        "schema": 1,
        "vendor": "openai",
        "draft": "Please review the attached source and evidence package. It has no native acceptance claim.",
        "native": {},
        "official_sources": [],
    }


def test_complete_draft_bundle_does_not_invent_gates(source, tmp_path):
    bundle = vb.prepare(source, request())
    assert bundle["status"] == "REVIEW_DRAFT"
    assert bundle["submission_ready"] is False
    assert bundle["contact_authorized"] is False
    assert bundle["gates"]["release"] == "UNKNOWN"
    assert bundle["gates"]["native.codex"] == "UNKNOWN"
    dest = tmp_path / "bundle.zip"
    vb.export(source, bundle, dest)
    assert vb.verify_export(dest)["source_digest"] == bundle["source_digest"]


def test_source_edits_invalidate_bundle(source, tmp_path):
    bundle = vb.prepare(source, request())
    (source / "SUPPORT.md").write_text("changed")
    with pytest.raises(ValueError, match="changed"):
        vb.export(source, bundle, tmp_path / "changed.zip")


@pytest.mark.parametrize(
    "draft",
    [
        "Published [VERSION]",
        "TODO: complete this",
        "Insert release highlights here",
        "Works perfectly in every harness",
    ],
)
def test_placeholder_and_unbounded_claims_refused(source, draft):
    r = request()
    r["draft"] = draft
    with pytest.raises(ValueError):
        vb.prepare(source, r)


def test_raw_session_private_fields_not_exported(source):
    r = request()
    r["native"] = {
        "codex": {"receipt": "/private/secret", "plugin_root": "/private/install"}
    }
    result = vb.prepare(source, r)
    assert "/private/secret" not in json.dumps(result)
    assert result["gates"]["native.codex"] == "UNKNOWN"


def archive(source, extra=None):
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode="w:gz") as tar:
        for name in sorted(
            p.relative_to(source).as_posix() for p in source.rglob("*") if p.is_file()
        ):
            raw = (source / name).read_bytes()
            info = tarfile.TarInfo("package/" + name)
            info.size = len(raw)
            info.mode = 0o644
            tar.addfile(info, io.BytesIO(raw))
        if extra:
            tar.addfile(extra)
    return data.getvalue()


def test_release_archive_exact_source_and_hostile_member(source):
    inv = vb.source_inventory(source)
    assert vb.compare_release_archive(archive(source), inv)
    bad = tarfile.TarInfo("../escape")
    bad.type = tarfile.SYMTYPE
    bad.linkname = "/elsewhere"
    with pytest.raises(ValueError):
        vb.compare_release_archive(archive(source, bad), inv)
    (source / "SUPPORT.md").write_text("changed")
    with pytest.raises(ValueError):
        vb.compare_release_archive(archive(source), inv)


def test_self_reported_release_or_native_pass_not_accepted(source):
    r = request()
    r["release"] = "PASS"
    with pytest.raises(ValueError):
        vb.prepare(source, r)
    r = request()
    r["native"] = {"codex": {"status": "PASS"}}
    with pytest.raises(ValueError):
        vb.prepare(source, r)


def test_unknown_vendor_refuses(source):
    r = request()
    r["vendor"] = "unknown"
    with pytest.raises(ValueError):
        vb.prepare(source, r)


def test_official_capture_must_be_present_and_match_bytes(source, tmp_path):
    import hashlib
    from datetime import datetime, timezone

    capture = tmp_path / "official.md"
    capture.write_text("Public synthetic documentation\n")
    r = request()
    r["official_sources"] = [
        {
            "url": "https://developers.openai.com/plugins/build/plugins",
            "sha256": hashlib.sha256(capture.read_bytes()).hexdigest(),
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "path": str(capture),
        }
    ]
    result = vb.prepare(source, r)
    assert result["official_sources"][0]["text"] == capture.read_text()
    assert str(capture) not in json.dumps(result)
    capture.write_text("changed")
    with pytest.raises(ValueError, match="capture"):
        vb.prepare(source, r)


def test_inventory_closes_earlier_source_identity(source, monkeypatch):
    real = vb.read_regular
    first = []
    changed = []

    def read(path, **kw):
        result = real(path, **kw)
        if not first:
            first.append(path)
        elif not changed:
            first[0].write_bytes(b"changed after earlier read")
            changed.append(True)
        return result

    monkeypatch.setattr(vb, "read_regular", read)
    with pytest.raises(ValueError, match="changed"):
        vb.source_inventory(source)


def test_inventory_closes_directory_membership(source, monkeypatch):
    real = vb.read_regular
    changed = []

    def read(path, **kw):
        result = real(path, **kw)
        if not changed:
            (source / "added.md").write_text("late source")
            changed.append(True)
        return result

    monkeypatch.setattr(vb, "read_regular", read)
    with pytest.raises(ValueError, match="membership"):
        vb.source_inventory(source)


def test_source_conformance_uses_real_owner_and_does_not_accept_fixture_placeholder(
    source,
):
    # The report contract binds real producer/schema inputs before reporting.
    # Keep this source invalid, but supply the inputs required for a FAIL report.
    import report_contract

    repository = vb.HERE.parents[2]
    for relative in report_contract.BINDING_PATHS:
        target = source / relative
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((repository / relative).read_bytes())
    result = vb.source_conformance(source)
    assert result["status"] == "FAIL"
    assert result["checks"]


def test_inventory_bounds_and_links(source, monkeypatch, tmp_path):
    (source / "linked").symlink_to(tmp_path)
    with pytest.raises(ValueError):
        vb.source_inventory(source)
    (source / "linked").unlink()
    monkeypatch.setattr(vb, "MAX_FILES", 2)
    with pytest.raises(ValueError, match="bound"):
        vb.source_inventory(source)


def test_export_does_not_turn_custody_into_native_acceptance(source, tmp_path):
    bundle = vb.prepare(source, request())
    path = tmp_path / "review.zip"
    vb.export(source, bundle, path)
    receipt = vb.verify_export(path)
    assert receipt["status"] == "CUSTODY_VERIFIED"
    assert receipt["native_revalidation_required"] is True
    assert receipt["contact_authorized"] is False
    with pytest.raises(FileExistsError):
        vb.export(source, bundle, path)


def test_sanitized_causal_probe_has_positive_and_negative_controls(tmp_path):
    import vendor_probe

    result = vendor_probe.probe(tmp_path / "probe")
    assert result["status"] == "PASS"
    assert result["native_acceptance"] == "UNKNOWN"
    assert result["external_calls"] == 0
    assert str(tmp_path) not in json.dumps(result)
    with pytest.raises(FileExistsError):
        vendor_probe.probe(tmp_path / "probe")


def test_default_bundle_never_queries_native_owners(source, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("native query was not requested")

    monkeypatch.setattr(vb, "native_qualification", forbidden)
    result = vb.prepare(source, request())
    assert result["gates"]["hook-trust"] == "UNKNOWN"
    assert result["gates"]["catalog-budget"] == "UNKNOWN"
    assert result["gates"]["continuity.local"] == "UNKNOWN"


def test_native_qualification_requires_explicit_exact_scope(source):
    with pytest.raises(ValueError, match="exact explicit scope"):
        vb.prepare(source, request(), verify_native=True)


def test_native_scope_routes_existing_local_owners_and_retains_failure(
    source, tmp_path, monkeypatch
):
    project = tmp_path / "project"
    project.mkdir()
    board = tmp_path / "board.md"
    board.write_text("fixture")
    scope = {
        "repo_root": str(source),
        "project": str(project),
        "active_project_file": str(tmp_path / "pointer.json"),
        "coordination_board": str(board),
    }
    calls = []

    def owner(root, command, arguments):
        calls.append((root, command, arguments))
        return {"status": "FAIL" if command == "hook-trust" else "PASS"}

    monkeypatch.setattr(vb, "owner_report", owner)
    result = vb.native_qualification(source, scope, "openai")
    assert result["hook-trust"]["status"] == "FAIL"
    assert {c[1] for c in calls} == {"hook-trust", "catalog", "continuity"}
    assert all(
        "--local" in c[2]
        and scope["project"] in c[2]
        and scope["coordination_board"] in c[2]
        for c in calls
    )
    assert "activate" not in str(calls)
    assert (
        vb.native_qualification(source, None, "hermes")["hook-trust"]["status"]
        == "UNSUPPORTED"
    )


def test_hermes_bundle_names_actual_context_observation_scope(source):
    value = request()
    value["vendor"] = "hermes"
    result = vb.prepare(source, value)
    assert "pre_llm_call" in result["native_gate_scope"]
    assert "pre_api_request" in result["native_gate_scope"]
    assert "protected execution" in result["native_gate_scope"]
    assert result["submission_authorized"] is False

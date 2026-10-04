"""Explicit registry-selected additive migration and exact owner custody."""

from pathlib import Path
import importlib
import json
import pytest
from test_record_transaction import world as _world

from test_run_admission import git
import record_transaction as rt

world = _world


def setup(world):
    p = world["project"]
    (p / "REFERENCE.md").write_text("# Reference\n")
    (p / "sessions").mkdir(exist_ok=True)
    (p / "sessions/2026-01.md").write_text("# 2026-01-02\nTODO: inspect\n")
    git(world["repo"], "add", "projects")
    git(world["repo"], "commit", "-m", "Fixture source")
    return importlib.import_module("project_migration"), world[
        "repo"
    ] / "projects/index.yaml"


def plan(world):
    m, index = setup(world)
    return m, m.propose(
        index, ["alpha"], target_format=2, now="2026-01-03T00:00:00+00:00"
    )


def run(world, m, p, **kw):
    return m.apply(
        p,
        approval_digest=p["digest"],
        board=world["board"],
        native_payload=world["actor"]["native_payload"],
        now="2026-01-03T00:01:00+00:00",
        **kw,
    )


def test_actual_registry_migration_dryrun_roundtrip(world):
    m, p = plan(world)
    root = world["project"]
    before = (root / "CONTEXT.md").read_bytes()
    assert run(world, m, p, dry_run=True)["status"] == "dry-run"
    assert not (root / ".synthesis-project.yaml").exists()
    assert run(world, m, p)["status"] == "committed"
    assert run(world, m, p)["status"] == "already-committed"
    assert (root / "CONTEXT.md").read_bytes() == before
    assert json.loads((root / "RESUME_STATE.json").read_text())["skeleton"] is True
    assert m.verify(p)["status"] == "verified-derived-format"


@pytest.mark.parametrize(
    "bad",
    [
        "approval",
        "expired",
        "source",
        "marker",
        "index",
        "plan",
        "unknown-format",
        "selection",
    ],
)
def test_refusal_preserves_sources(world, bad):
    m, p = plan(world)
    root = world["project"]
    if bad == "approval":
        p["digest"] = "a" * 64
    elif bad == "expired":
        p["expires_at"] = "2025-01-01T00:00:00+00:00"
    elif bad == "source":
        (root / "CONTEXT.md").write_text("changed")
    elif bad == "marker":
        (root / ".synthesis-project.yaml").write_text("foreign")
    elif bad == "index":
        Path(p["index"]).write_text("projects: []\n")
    elif bad == "plan":
        p["projects"][0]["outputs"][0]["text"] = "changed"
    elif bad == "unknown-format":
        p["target_format"] = 99
    else:
        p["selected"] = ["absent"]
    before = {
        f.relative_to(root).as_posix(): f.read_bytes()
        for f in root.rglob("*")
        if f.is_file()
    }
    with pytest.raises((ValueError, RuntimeError)):
        run(world, m, p)
    assert before == {
        f.relative_to(root).as_posix(): f.read_bytes()
        for f in root.rglob("*")
        if f.is_file()
    }


def test_interrupted_migration_reconciles_original_intent(world, monkeypatch):
    m, p = plan(world)
    link = rt.os.link
    count = 0

    def stop(src, dst, **kw):
        nonlocal count
        count += 1
        if count == 2:
            raise OSError("power interruption")
        return link(src, dst, **kw)

    with monkeypatch.context() as patch:
        patch.setattr(rt.os, "link", stop)
        with pytest.raises(OSError):
            run(world, m, p)
    assert (
        m.recover(
            p,
            approval_digest=p["digest"],
            board=world["board"],
            native_payload=world["actor"]["native_payload"],
        )["status"]
        == "committed"
    )
    assert run(world, m, p)["status"] == "already-committed"


def test_exact_selection_and_unknown_schema(world):
    m, index = setup(world)
    for selected, target in [
        ([], 2),
        (["alpha", "alpha"], 2),
        (["alpha"], 3),
        (["absent"], 2),
    ]:
        with pytest.raises((ValueError, RuntimeError)):
            m.propose(index, selected, target_format=target)


def test_migration_preserves_exact_source_bytes_in_owner_custody(world):
    m, p = plan(world)
    root = world["project"]
    source = {
        x["path"]: (root / x["path"]).read_bytes() for x in p["projects"][0]["source"]
    }
    result = run(world, m, p)
    journal = Path(result["projects"][0]["journal"])
    manifest = json.loads((journal / "manifest.json").read_text())
    assert len(manifest["sources"]) == len(source)
    for item in manifest["sources"]:
        assert (journal / "sources" / item["archive"]).read_bytes() == source[
            item["path"]
        ]
    assert source == {name: (root / name).read_bytes() for name in source}


def test_all_declared_current_format_is_verified_without_rewriting(world):
    m, p = plan(world)
    run(world, m, p)
    # A new preview after publication can include already-current projects.
    git(world["repo"], "add", "projects")
    git(world["repo"], "commit", "-m", "Fixture migration")
    q = m.propose(
        Path(p["index"]), ["alpha"], target_format=2, now="2026-01-03T00:00:00+00:00"
    )
    assert q["projects"][0]["action"] == "verify-current"
    assert run(world, m, q)["status"] == "already-current"


@pytest.mark.parametrize(
    "bad", ["duplicate-marker", "float-version", "bad-state", "stale-index"]
)
def test_current_format_has_real_schema_and_content_checks(world, bad):
    m, p = plan(world)
    run(world, m, p)
    root = world["project"]
    if bad == "duplicate-marker":
        marker = root / ".synthesis-project.yaml"
        marker.write_text(marker.read_text() + "format_version: 2\n")
    elif bad == "float-version":
        marker = root / ".synthesis-project.yaml"
        marker.write_text(
            marker.read_text().replace("format_version: 2", "format_version: 2.0")
        )
    elif bad == "bad-state":
        state = root / "RESUME_STATE.json"
        data = json.loads(state.read_text())
        data["schema"] = True
        state.write_text(json.dumps(data))
    else:
        (root / "sessions/INDEX.md").write_text("stale")
    git(world["repo"], "add", "projects")
    git(world["repo"], "commit", "-m", "Fixture ambiguity")
    with pytest.raises((ValueError, RuntimeError)):
        m.propose(Path(p["index"]), ["alpha"], target_format=2)


@pytest.mark.parametrize(
    "bad", ["tamper-archive", "foreign-source", "missing-custody", "foreign-target"]
)
def test_migration_recovery_retains_every_ambiguous_byte(world, monkeypatch, bad):
    m, p = plan(world)
    root = world["project"]

    def stop(src, dst, **kw):
        raise OSError("fixture crash")

    with monkeypatch.context() as patch:
        patch.setattr(rt.os, "link", stop)
        with pytest.raises(OSError):
            run(world, m, p)
    active = root / rt.STORE / "active"
    if bad == "tamper-archive":
        (active / "sources/0.source").write_text("foreign")
    elif bad == "foreign-source":
        (root / "CONTEXT.md").write_text("foreign")
    elif bad == "missing-custody":
        (active / "sources/0.source").unlink()
    else:
        (root / ".synthesis-project.yaml").write_text("foreign")
    before = {f: f.read_bytes() for f in root.rglob("*") if f.is_file()}
    with pytest.raises((OSError, ValueError, RuntimeError)):
        m.recover(
            p,
            approval_digest=p["digest"],
            board=world["board"],
            native_payload=world["actor"]["native_payload"],
        )
    assert before == {f: f.read_bytes() for f in root.rglob("*") if f.is_file()}


def test_multi_project_plan_does_not_grant_cross_project_native_ownership(world):
    m, index = setup(world)
    root = world["project"]
    beta = root.parent / "beta"
    beta.mkdir()
    (beta / "CONTEXT.md").write_text("# Beta\n")
    (beta / "REFERENCE.md").write_text("# References\n")
    (beta / "sessions").mkdir()
    index.write_text("- id: alpha\n- id: beta\n")
    git(world["repo"], "add", "projects")
    git(world["repo"], "commit", "-m", "Fixture selection")
    p = m.propose(
        index, ["alpha", "beta"], target_format=2, now="2026-01-03T00:00:00+00:00"
    )
    with pytest.raises(rt.RecordTransactionError):
        run(world, m, p)
    assert (
        not (root / ".synthesis-project.yaml").exists()
        and not (beta / ".synthesis-project.yaml").exists()
    )
    result = run(world, m, p, selected_project="alpha")
    assert result["status"] == "partial" and result["pending_projects"] == ["beta"]
    assert (root / ".synthesis-project.yaml").exists() and not (
        beta / ".synthesis-project.yaml"
    ).exists()


@pytest.mark.parametrize("change", ["float-identity", "combined-capacity"])
def test_source_custody_revalidates_strict_identity_and_total(
    world, monkeypatch, change
):
    m, p = plan(world)
    result = run(world, m, p)
    journal = Path(result["projects"][0]["journal"])
    manifest = json.loads((journal / "manifest.json").read_text())
    if change == "float-identity":
        manifest["sources"][0]["before"]["mode"] = float(
            manifest["sources"][0]["before"]["mode"]
        )
    else:
        sources = sum(x["before"]["bytes"] for x in manifest["sources"])
        effects = sum(x["after"]["bytes"] for x in manifest["files"])
        monkeypatch.setattr(rt, "MAX_TOTAL_BYTES", max(sources, effects))
    with pytest.raises(rt.RecordTransactionError):
        rt._check_custody(world["project"], journal, manifest)


def test_recovery_has_exact_selected_project_boundary(world, monkeypatch):
    m, p = plan(world)
    with monkeypatch.context() as patch:
        patch.setattr(
            rt.os,
            "link",
            lambda *a, **k: (_ for _ in ()).throw(OSError("fixture crash")),
        )
        with pytest.raises(OSError):
            run(world, m, p)
    result = m.recover(
        p,
        approval_digest=p["digest"],
        board=world["board"],
        native_payload=world["actor"]["native_payload"],
        selected_project="alpha",
    )
    assert result["status"] == "committed"


@pytest.mark.parametrize(
    "failure", ["initial-history", "source-custody", "publish-intent"]
)
def test_precommit_interruption_can_retry_same_plan_without_erasing_custody(
    world, monkeypatch, failure
):
    m, p = plan(world)
    root = world["project"]
    original = rt._new_file
    rename = rt.os.rename

    def write(path, data, *a, **kw):
        path = Path(path)
        if (failure == "initial-history" and path.name == "history.json") or (
            failure == "source-custody" and path.parent.name == "sources"
        ):
            raise OSError("fixture disk full")
        return original(path, data, *a, **kw)

    def move(src, dst, *a, **kw):
        if failure == "publish-intent" and Path(dst).name == "active":
            raise OSError("fixture interruption")
        return rename(src, dst, *a, **kw)

    with monkeypatch.context() as patch:
        patch.setattr(rt, "_new_file", write)
        patch.setattr(rt.os, "rename", move)
        with pytest.raises(OSError):
            run(world, m, p)
    retained = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
    assert not (root / ".synthesis-project.yaml").exists()
    assert run(world, m, p)["status"] == "committed"
    for path, data in retained.items():
        if path.name == "history.json":
            continue
        assert path.read_bytes() == data


def test_actual_cli_migration_preview_apply_and_repeat(world):
    import os
    import subprocess
    import sys

    m, index = setup(world)
    root = world["scratch"]
    cli = (
        Path(__file__).resolve().parents[2]
        / "synthesis-onboarding/scripts/synthesis_cli.py"
    )

    def command(*args):
        result = subprocess.run(
            [sys.executable, str(cli), "project-migrate", *args, "--json"],
            capture_output=True,
            text=True,
            timeout=30,
            env=dict(os.environ),
        )
        assert result.returncode == 0, result.stderr + result.stdout
        return json.loads(result.stdout)

    preview = command(
        "plan", "--index", str(index), "--select", "alpha", "--target-format", "2"
    )
    saved = root / "preview.json"
    saved.write_text(json.dumps(preview))
    payload = root / "native.json"
    payload.write_text(json.dumps(world["actor"]["native_payload"]))
    args = [
        "--plan",
        str(saved),
        "--approve",
        preview["digest"],
        "--board",
        str(world["board"]),
        "--native-payload",
        str(payload),
        "--project",
        "alpha",
    ]
    assert command("apply", *args, "--dry-run")["status"] == "dry-run"
    assert command("apply", *args)["status"] == "committed"
    assert command("apply", *args)["status"] == "already-committed"
    assert (
        command("verify", "--plan", str(saved))["status"] == "verified-derived-format"
    )


def test_source_preparation_capacity_never_prunes(world):
    m, p = plan(world)
    root = world["project"]
    for i in range(64):
        (root / (rt.STORE + ".init-" + str(i))).mkdir()
    with pytest.raises(rt.RecordTransactionError, match="capacity"):
        run(world, m, p)
    assert len(list(root.glob(rt.STORE + ".init-*"))) == 64
    assert not (root / ".synthesis-project.yaml").exists()


@pytest.mark.parametrize(
    "kind", ["scalar", "float", "duplicate", "symlink", "fifo", "oversized"]
)
def test_format_detection_refuses_unsafe_or_ambiguous_marker(world, kind):
    import os
    import project_format

    m, index = setup(world)
    root = world["project"]
    marker = root / project_format.MARKER_NAME
    if kind == "scalar":
        marker.write_text("unexpected")
    elif kind == "float":
        marker.write_text("format_version: 2.0\n")
    elif kind == "duplicate":
        marker.write_text("format_version: 1\nformat_version: 2\n")
    elif kind == "symlink":
        marker.symlink_to(root / "CONTEXT.md")
    elif kind == "fifo":
        os.mkfifo(marker)
    else:
        with marker.open("wb") as stream:
            stream.truncate(9 * 1024 * 1024)
    assert project_format.detect(root) == "unknown"


def test_migration_expiry_during_preflight_prevents_first_project_commit(
    world, monkeypatch
):
    import project_migration as migration

    api, index = setup(world)
    plan = api.propose(
        index, ["alpha"], target_format=2, now="2026-01-03T00:00:00+00:00"
    )
    clock = ["2026-01-03T00:59:59+00:00"]
    original_time = migration._time
    monkeypatch.setattr(
        migration, "_time", lambda value=None: original_time(value or clock[0])
    )
    original_apply = migration._record_apply

    def preflight(*args, **kwargs):
        result = original_apply(*args, **kwargs)
        if kwargs["dry_run"]:
            clock[0] = "2026-01-03T01:00:01+00:00"
        return result

    monkeypatch.setattr(migration, "_record_apply", preflight)
    with pytest.raises((ValueError, RuntimeError), match="expir|fresh"):
        api.apply(
            plan,
            approval_digest=plan["digest"],
            board=world["board"],
            native_payload=world["actor"]["native_payload"],
        )
    assert not (world["project"] / ".synthesis-project.yaml").exists()


def test_expired_consent_can_verify_exact_completed_intent(world):
    m, p = plan(world)
    assert run(world, m, p)["status"] == "committed"
    result = m.apply(
        p,
        approval_digest=p["digest"],
        board=world["board"],
        native_payload=world["actor"]["native_payload"],
        now="2026-01-04T00:00:00+00:00",
    )
    assert result["status"] == "already-committed"
    assert (
        m.recover(
            p,
            approval_digest=p["digest"],
            board=world["board"],
            native_payload=world["actor"]["native_payload"],
        )["status"]
        == "committed"
    )


def test_migration_expiry_during_final_rederivation_prevents_effect(world, monkeypatch):
    m, p = plan(world)
    clock = ["2026-01-03T00:59:59+00:00"]
    original_time = m._time
    monkeypatch.setattr(m, "_time", lambda value=None: original_time(value or clock[0]))
    original_fresh = m._fresh_item
    calls = []

    def delayed(*args, **kwargs):
        result = original_fresh(*args, **kwargs)
        calls.append(True)
        if len(calls) == 2:
            clock[0] = "2026-01-03T01:00:01+00:00"
        return result

    monkeypatch.setattr(m, "_fresh_item", delayed)
    with pytest.raises((ValueError, RuntimeError), match="expir"):
        m.apply(
            p,
            approval_digest=p["digest"],
            board=world["board"],
            native_payload=world["actor"]["native_payload"],
        )
    assert len(calls) == 2
    assert not (world["project"] / ".synthesis-project.yaml").exists()


def test_expiry_between_projects_preserves_first_commit_without_starting_second(
    world, monkeypatch
):
    m, index = setup(world)
    beta = world["project"].parent / "beta"
    beta.mkdir()
    (beta / "CONTEXT.md").write_text("# Synthetic second project\n")
    (beta / "REFERENCE.md").write_text("# References\n")
    (beta / "sessions").mkdir()
    index.write_text("- id: alpha\n- id: beta\n")
    git(world["repo"], "add", "projects")
    git(world["repo"], "commit", "-m", "Fixture source")
    p = m.propose(
        index, ["alpha", "beta"], target_format=2, now="2026-01-03T00:00:00+00:00"
    )
    clock = ["2026-01-03T00:59:59+00:00"]
    original_time = m._time
    monkeypatch.setattr(m, "_time", lambda value=None: original_time(value or clock[0]))
    original_apply = m._record_apply
    effects = []

    def controlled_owner(plan, item, board, native_payload, *, dry_run):
        if item["id"] == "beta":
            # Only the synthetic all-set admission is simulated. No authority
            # is fabricated in the actual owner, and beta must never dispatch.
            assert dry_run
            return {"status": "dry-run"}
        result = original_apply(plan, item, board, native_payload, dry_run=dry_run)
        if not dry_run:
            effects.append(item["id"])
            clock[0] = "2026-01-03T01:00:01+00:00"
        return result

    monkeypatch.setattr(m, "_record_apply", controlled_owner)
    with pytest.raises((ValueError, RuntimeError), match="expir"):
        m.apply(
            p,
            approval_digest=p["digest"],
            board=world["board"],
            native_payload=world["actor"]["native_payload"],
        )
    assert effects == ["alpha"]
    assert (world["project"] / ".synthesis-project.yaml").exists()
    assert not (beta / ".synthesis-project.yaml").exists()
    assert (
        m.recover(
            p,
            approval_digest=p["digest"],
            board=world["board"],
            native_payload=world["actor"]["native_payload"],
            selected_project="alpha",
        )["projects"][0]["status"]
        == "already-committed"
    )


# Recovery roots are discovery evidence, never native mutation authority.
def recovery_world(world, *, receipt=False):
    import hashlib

    m, index = setup(world)
    roots = {
        "repo_guard_root": world["scratch"] / "guard",
        "checkpoint_receipt_root": world["scratch"] / "receipts",
        "coordination_board": world["board"],
    }
    for key in ("repo_guard_root", "checkpoint_receipt_root"):
        roots[key].mkdir()
    pending = roots["repo_guard_root"] / "pending"
    pending.mkdir(exist_ok=True)
    context = world["project"] / "CONTEXT.md"
    context.write_bytes(context.read_bytes() + b"\nRetained uncommitted source.\n")
    manifest = pending / "synthetic-owner.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "session_id": "synthetic-owner",
                "paths": [str(context)],
                "path_hashes": {
                    str(context): hashlib.sha256(context.read_bytes()).hexdigest()
                },
                "path_kinds": {str(context): "file"},
            }
        )
    )
    if receipt:
        (roots["checkpoint_receipt_root"] / "synthetic-checkpoint.json").write_text(
            json.dumps(
                {
                    "project_id": "alpha",
                    "session_id": "synthetic-owner",
                    "git_head": git(world["repo"], "rev-parse", "HEAD"),
                }
            )
        )
    return m, index, roots, manifest


@pytest.mark.parametrize("receipt", [False, True])
def test_actual_dirty_attribution_roots_plan_apply_verify_source_custody(
    world, receipt
):
    m, index, roots, manifest = recovery_world(world, receipt=receipt)
    before = (world["project"] / "CONTEXT.md").read_bytes()
    report = m.project_state.resolve_project(
        "alpha",
        index,
        fetch=False,
        fast_forward_canonical=False,
        refresh_coordination=False,
        **roots,
    )
    assert report.status == "LOCAL_RECOVERABLE"
    assert "claim" in {candidate.source for candidate in report.candidates}
    if receipt:
        assert "checkpoint-receipt" in {
            candidate.source for candidate in report.candidates
        }
    p = m.propose(
        index,
        ["alpha"],
        target_format=2,
        recovery_roots=roots,
        now="2026-01-03T00:00:00+00:00",
    )
    assert p["recovery_roots"] == {key: str(value) for key, value in roots.items()}
    assert run(world, m, p, dry_run=True, recovery_roots=roots)["status"] == "dry-run"
    assert not (world["project"] / ".synthesis-project.yaml").exists()
    assert run(world, m, p, recovery_roots=roots)["status"] == "committed"
    assert m.verify(p, recovery_roots=roots)["status"] == "verified-derived-format"
    assert (world["project"] / "CONTEXT.md").read_bytes() == before
    assert manifest.exists()
    intent = m._intent(p, p["projects"][0])
    saved = json.loads(
        (
            world["project"] / rt.STORE / "completed" / intent / "manifest.json"
        ).read_text()
    )
    assert (
        saved["sources"][0]["before"]["sha256"]
        == p["projects"][0]["source"][0]["sha256"]
    )


@pytest.mark.parametrize("bad", ["missing", "wrong-root", "wrong-hash", "foreign-path"])
def test_actual_dirty_refusal_exposes_original_owner_issue(world, bad):
    m, index, roots, manifest = recovery_world(world)
    if bad == "missing":
        manifest.rename(manifest.with_suffix(".retained"))
    elif bad == "wrong-root":
        roots["repo_guard_root"] = world["scratch"] / "wrong-guard"
    else:
        data = json.loads(manifest.read_text())
        if bad == "wrong-hash":
            data["path_hashes"] = {data["paths"][0]: "0" * 64}
        else:
            data["paths"] = [str(world["scratch"] / "foreign-project" / "CONTEXT.md")]
        manifest.write_text(json.dumps(data))
    with pytest.raises(
        ValueError, match="dirty project files lack an exact attributed manifest"
    ):
        m.propose(index, ["alpha"], target_format=2, recovery_roots=roots)
    assert not (world["project"] / ".synthesis-project.yaml").exists()


@pytest.mark.parametrize("change", ["selected-root", "directory-replaced", "board"])
def test_recovery_binding_changes_refuse_before_effect(world, change):
    m, index, roots, manifest = recovery_world(world)
    p = m.propose(
        index,
        ["alpha"],
        target_format=2,
        recovery_roots=roots,
        now="2026-01-03T00:00:00+00:00",
    )
    board = world["board"]
    if change == "selected-root":
        roots = {**roots, "repo_guard_root": world["scratch"] / "other-guard"}
    elif change == "directory-replaced":
        root = roots["repo_guard_root"]
        root.rename(root.with_name("retained-guard"))
        root.mkdir()
    elif change == "board":
        board = board.with_name("other-board.md")
        board.write_bytes(world["board"].read_bytes())
    with pytest.raises(ValueError):
        m.apply(
            p,
            approval_digest=p["digest"],
            board=board,
            native_payload=world["actor"]["native_payload"],
            recovery_roots=roots,
            now="2026-01-03T00:01:00+00:00",
        )
    assert not (world["project"] / ".synthesis-project.yaml").exists()


def test_attribution_does_not_grant_foreign_native_effects(world):
    from test_run_admission import write_board

    m, index, roots, _ = recovery_world(world)
    p = m.propose(
        index,
        ["alpha"],
        target_format=2,
        recovery_roots=roots,
        now="2026-01-03T00:00:00+00:00",
    )
    write_board(world, native="01990000-0000-7000-8000-000000000099")
    with pytest.raises(
        rt.RecordTransactionError,
        match="native event has no unique active coordination seat",
    ):
        run(world, m, p, recovery_roots=roots)
    assert not (world["project"] / ".synthesis-project.yaml").exists()


def test_root_bound_interrupted_migration_recovers_same_original_intent(
    world, monkeypatch
):
    m, index, roots, _ = recovery_world(world)
    p = m.propose(
        index,
        ["alpha"],
        target_format=2,
        recovery_roots=roots,
        now="2026-01-03T00:00:00+00:00",
    )
    original = rt.os.link
    calls = 0

    def interrupted(src, dst, **kw):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("synthetic retained interruption")
        return original(src, dst, **kw)

    with monkeypatch.context() as patch:
        patch.setattr(rt.os, "link", interrupted)
        with pytest.raises(OSError):
            run(world, m, p, recovery_roots=roots)
    assert (
        m.recover(
            p,
            approval_digest=p["digest"],
            board=world["board"],
            native_payload=world["actor"]["native_payload"],
            recovery_roots=roots,
        )["status"]
        == "committed"
    )
    assert m.verify(p, recovery_roots=roots)["status"] == "verified-derived-format"


def test_refusal_detail_is_bounded_without_hiding_status_or_issue_count():
    from types import SimpleNamespace
    import project_migration as m

    report = SimpleNamespace(status="CONFLICT", issues=["x" * 10000] * 100)
    error = str(m._resolution_refusal(report))
    assert error.startswith("causal project resolution refused: CONFLICT;")
    detail = json.loads(error.split("; ", 1)[1])
    assert detail["issue_count"] == 100 and detail["issues_truncated"] is True
    assert len(detail["issues"]) == 8 and len(error) < 3000


@pytest.fixture(autouse=True)
def migration_selected_machine(world, monkeypatch):
    # The CLI fixture selects the same synthetic machine/board as native admission.
    monkeypatch.setenv("SYNTHESIS_HOME", str(world["scratch"] / "selected-home"))
    monkeypatch.setenv("SYNTHESIS_COORDINATION_BOARD", str(world["board"]))


def test_each_preview_requires_fresh_attribution(world):
    m, index, roots, manifest = recovery_world(world)
    assert m.propose(index, ["alpha"], target_format=2, recovery_roots=roots)
    manifest.rename(manifest.with_suffix(".retained"))
    with pytest.raises(ValueError, match="exact attributed manifest"):
        m.propose(index, ["alpha"], target_format=2, recovery_roots=roots)


@pytest.mark.parametrize("root_key", ["repo_guard_root", "checkpoint_receipt_root"])
def test_root_replacement_after_preflight_refuses_first_effect(
    world, monkeypatch, root_key
):
    m, index, roots, _ = recovery_world(world)
    p = m.propose(
        index,
        ["alpha"],
        target_format=2,
        recovery_roots=roots,
        now="2026-01-03T00:00:00+00:00",
    )
    original = m._fresh_item
    calls = 0

    def replace_after_preflight(plan, item):
        nonlocal calls
        original(plan, item)
        calls += 1
        if calls == 2:
            root = roots[root_key]
            root.rename(root.with_name(root.name + "-retained"))
            root.mkdir()

    monkeypatch.setattr(m, "_fresh_item", replace_after_preflight)
    with pytest.raises(ValueError, match="recovery root directory identity changed"):
        run(world, m, p, recovery_roots=roots)
    assert not (world["project"] / ".synthesis-project.yaml").exists()
    assert not (world["project"] / rt.STORE).exists()

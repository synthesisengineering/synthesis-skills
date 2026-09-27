"""Real editor, PM admission and managed recovery controls; no live authority."""

from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import pytest

sys.path.insert(
    0, str(Path(__file__).resolve().parents[2] / "synthesis-context-lifecycle/scripts")
)
import context_edit
import record_transaction as rt
import project_state
import project_format
from test_run_admission import world as _world_fixture, write_board

world = _world_fixture


@pytest.fixture
def edits(world):
    p = world["project"]
    (p / "REFERENCE.md").write_bytes(b"# Reference\r\nold\r\n")
    (p / "plan.md").write_text("# Fixture plan\nold\n")
    os.chmod(p / "plan.md", 0o640)
    return [
        {"file": n, "edits": [{"op": "replace", "anchor": "old", "replacement": "new"}]}
        for n in ["plan.md", "REFERENCE.md"]
    ]


def apply(world, edits, **kwargs):
    return context_edit.apply_transaction(
        world["project"],
        edits,
        board=world["board"],
        native_payload=world["actor"]["native_payload"],
        **kwargs
    )


def recover(world):
    return context_edit.recover_transaction(
        world["project"],
        board=world["board"],
        native_payload=world["actor"]["native_payload"],
    )


def originals(world):
    return {n: (world["project"] / n).read_bytes() for n in ["plan.md", "REFERENCE.md"]}


def interrupted(world, edits, monkeypatch, after=0):
    old = rt.os.replace
    counter = 0

    def replace(src, dst):
        nonlocal counter
        if Path(dst).name in ["plan.md", "REFERENCE.md"]:
            if counter == after:
                raise OSError("injected replacement failure")
            counter += 1
        return old(src, dst)

    with monkeypatch.context() as patch:
        patch.setattr(rt.os, "replace", replace)
        with pytest.raises(OSError):
            apply(world, edits)
    return world["project"] / rt.STORE / "active"


def test_success_and_dryrun_actual_authority(world, edits):
    old = originals(world)
    assert apply(world, edits, dry_run=True)["status"] == "dry-run"
    assert originals(world) == old
    result = apply(world, edits)
    assert result["status"] == "committed"
    assert originals(world) == {n: b.replace(b"old", b"new") for n, b in old.items()}
    assert (world["project"] / "plan.md").stat().st_mode & 0o777 == 0o640
    with rt.managed(world["project"]):
        pass
    with pytest.raises(rt.RecordTransactionError):
        recover(world)


@pytest.mark.parametrize(
    "bad",
    [
        "anchor",
        "budget",
        "utf8",
        "duplicate",
        "escape",
        "symlink",
        "parent-symlink",
        "hardlink",
        "noauthority",
    ],
)
def test_late_preflight_preserves_every_target(world, edits, bad):
    p = world["project"]
    old = originals(world)
    if bad == "anchor":
        edits[1]["edits"][0]["anchor"] = "missing"
    elif bad == "budget":
        edits[1]["max_lines"] = 0
    elif bad == "utf8":
        (p / "REFERENCE.md").write_bytes(b"\xffold")
    elif bad == "duplicate":
        edits[1]["file"] = "plan.md"
    elif bad == "escape":
        edits[1]["file"] = "../index.yaml"
    elif bad == "symlink":
        (p / "alias").symlink_to(p / "REFERENCE.md")
        edits[1]["file"] = "alias"
    elif bad == "parent-symlink":
        (p / "alias").symlink_to(p, target_is_directory=True)
        edits[1]["file"] = "alias/REFERENCE.md"
    elif bad == "hardlink":
        os.link(p / "REFERENCE.md", p / "alias")
        edits[1]["file"] = "alias"
    elif bad == "noauthority":
        write_board(world, claims=str(p / "plan.md"))
    old = originals(world)
    with pytest.raises(
        (rt.RecordTransactionError, context_edit.ContextEditError, UnicodeError)
    ):
        apply(world, edits)
    assert originals(world) == old
    assert not (p / rt.STORE / "active").exists()


@pytest.mark.parametrize("after", [0, 1])
def test_each_replace_failure_and_real_consumers(world, edits, monkeypatch, after):
    interrupted(world, edits, monkeypatch, after)
    with pytest.raises(rt.RecordTransactionError):
        context_edit.replace_once(world["project"] / "plan.md", "old", "other")
    with pytest.raises(project_state.ProjectStateError):
        project_state.semantic_issues(world["project"])
    with pytest.raises(ValueError):
        project_format.refresh(world["project"])
    result = project_state.resolve_project(
        "alpha", world["repo"] / "projects/index.yaml", fetch=False
    )
    assert result.status == "UNKNOWN" and result.selected_path is None
    assert recover(world)["status"] == "committed"
    assert all(b"new" in b for b in originals(world).values())


@pytest.mark.parametrize(
    "bad",
    [
        "missing-manifest",
        "corrupt-manifest",
        "duplicate-manifest",
        "missing-commit",
        "corrupt-commit",
        "missing-stage",
        "foreign-target",
        "changed-mode",
        "replaced-source",
        "changed-claim",
        "changed-native",
        "missing-history",
        "corrupt-history",
    ],
)
def test_ambiguous_evidence_and_foreign_changes_refused(world, edits, monkeypatch, bad):
    active = interrupted(world, edits, monkeypatch, 1)
    p = world["project"]
    if bad == "missing-manifest":
        (active / "manifest.json").rename(active / "manifest.retained")
    elif bad == "corrupt-manifest":
        (active / "manifest.json").write_text("{}")
    elif bad == "duplicate-manifest":
        (active / "manifest.json").write_text('{"schema":1,"schema":1}')
    elif bad == "missing-commit":
        (active / "commit.json").rename(active / "commit.retained")
    elif bad == "corrupt-commit":
        (active / "commit.json").write_text("{}")
    elif bad == "missing-stage":
        (active / "1.staged").rename(active / "retained.staged")
    elif bad == "foreign-target":
        (p / "REFERENCE.md").write_text("foreign\n")
    elif bad == "changed-mode":
        os.chmod(p / "REFERENCE.md", 0o600)
    elif bad == "replaced-source":
        temp = p / "other"
        temp.write_bytes((p / "REFERENCE.md").read_bytes())
        os.replace(temp, p / "REFERENCE.md")
    elif bad == "changed-claim":
        write_board(world, claims=str(p / "elsewhere/**"))
    elif bad == "changed-native":
        world["actor"]["native_payload"]["session_id"] = "wrong"
    elif bad == "missing-history":
        (active.parent / "history.json").rename(active.parent / "history.retained")
    else:
        (active.parent / "history.json").write_text("{}")
    old = originals(world)
    with pytest.raises((rt.RecordTransactionError, OSError)):
        recover(world)
    assert originals(world) == old and active.exists()


@pytest.mark.parametrize("point", range(1, 26))
def test_each_fsync_fault_keeps_custody_and_coherent_recovery(
    world, edits, monkeypatch, point
):
    sync = rt.os.fsync
    count = 0

    def fault(fd):
        nonlocal count
        count += 1
        if count == point:
            raise OSError("injected fsync failure")
        return sync(fd)

    old = originals(world)
    with monkeypatch.context() as patch:
        patch.setattr(rt.os, "fsync", fault)
        try:
            result = apply(world, edits)
        except OSError:
            result = None
    active = world["project"] / rt.STORE / "active"
    if active.exists():
        assert recover(world)["status"] == "committed"
    elif result is None:
        # Failure before durable intent or after completed-directory rename.
        assert originals(world) in [
            old,
            {n: b.replace(b"old", b"new") for n, b in old.items()},
        ]
    else:
        assert result["status"] == "committed"


@pytest.mark.parametrize("file_index", [0, 1])
@pytest.mark.parametrize("edge", ["before", "after"])
def test_abrupt_process_loss_and_cold_cli_recovery(world, edits, file_index, edge):
    p = world["project"]
    input_path = world["scratch"] / "edits.json"
    input_path.write_text(json.dumps(edits))
    actor = world["scratch"] / "payload.json"
    actor.write_text(json.dumps(world["actor"]["native_payload"]))
    editor = Path(context_edit.__file__)
    script = world["scratch"] / "crash.py"
    script.write_text(
        """import sys,os\nfrom pathlib import Path\nsys.path.insert(0, %r)\nimport context_edit,record_transaction as rt\noriginal=os.replace\ncount=0\ndef crash(src,dst):\n global count\n target=Path(dst).name in ['plan.md','REFERENCE.md']\n if target and count==%r and %r=='before':os._exit(77)\n value=original(src,dst)\n if target:\n  if count==%r and %r=='after':os._exit(77)\n  count+=1\n return value\nos.replace=crash\nsys.exit(context_edit.main(sys.argv[1:]))\n"""
        % (str(editor.parent), file_index, edge, file_index, edge)
    )
    args = [
        "--project",
        str(p),
        "--board",
        str(world["board"]),
        "--native-payload",
        str(actor),
    ]
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "apply-transaction",
            *args,
            "--files",
            str(input_path),
        ],
        capture_output=True,
        text=True,
        timeout=25,
    )
    assert result.returncode == 77, result.stderr
    result = subprocess.run(
        [sys.executable, str(editor), "recover-transaction", *args],
        capture_output=True,
        text=True,
        timeout=25,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "committed"
    assert all(b"new" in b for b in originals(world).values())


def test_completed_journal_replay_refuses_changes(world, edits):
    result = apply(world, edits)
    p = world["project"]
    store = p / rt.STORE
    shutil.copytree(result["journal"], store / "active")
    (p / "plan.md").write_text("later legitimate work\n")
    old = originals(world)
    with pytest.raises(rt.RecordTransactionError):
        recover(world)
    assert originals(world) == old


def test_claim_change_between_targets_leaves_recoverable_owned_custody(
    world, edits, monkeypatch
):
    old = rt.os.replace

    def replace(src, dst):
        result = old(src, dst)
        if Path(dst).name == "plan.md":
            write_board(world, claims=str(world["project"] / "different/**"))
        return result

    with monkeypatch.context() as patch:
        patch.setattr(rt.os, "replace", replace)
        with pytest.raises(rt.RecordTransactionError):
            apply(world, edits)
    assert b"new" in (world["project"] / "plan.md").read_bytes()
    assert b"old" in (world["project"] / "REFERENCE.md").read_bytes()
    write_board(world)
    assert recover(world)["status"] == "committed"


def test_missing_whole_active_directory_cannot_hide_partial_commit(
    world, edits, monkeypatch
):
    active = interrupted(world, edits, monkeypatch, 1)
    active.rename(active.with_name("retained-active"))
    old = originals(world)
    with pytest.raises(rt.RecordTransactionError, match="journal is missing"):
        with rt.managed(world["project"]):
            pass
    assert originals(world) == old


def test_tampered_intent_hash_refuses_even_if_commit_file_recomputed(
    world, edits, monkeypatch
):
    active = interrupted(world, edits, monkeypatch, 1)
    manifest = json.loads((active / "manifest.json").read_text())
    manifest["files"][1]["note"] = "tampered"
    raw = rt._json(manifest)
    (active / "manifest.json").write_bytes(raw)
    (active / "commit.json").write_bytes(rt._json({"manifest_sha256": rt._digest(raw)}))
    old = originals(world)
    with pytest.raises(rt.RecordTransactionError, match="admitted active transaction"):
        recover(world)
    assert originals(world) == old


def test_actual_doctor_refuses_partial_record_generation(world, edits, monkeypatch):
    import context_doctor

    interrupted(world, edits, monkeypatch, 1)
    source = context_doctor.Source("fixture", world["repo"])
    audit = context_doctor.audit_project(
        source, "alpha", world["project"], {}, world["repo"], world["repo"] / "projects"
    )
    assert any(
        item.check == "record-transaction" and item.severity == "defect"
        for item in audit.findings
    )


def test_source_change_at_precommit_authority_read_refuses_all_owned_writes(
    world, edits, monkeypatch
):
    authority = rt._authority
    calls = 0

    def change(*args, **kwargs):
        nonlocal calls
        result = authority(*args, **kwargs)
        calls += 1
        if calls == 2:
            (world["project"] / "REFERENCE.md").write_text("foreign late edit\n")
        return result

    monkeypatch.setattr(rt, "_authority", change)
    with pytest.raises(rt.RecordTransactionError, match="source changed"):
        apply(world, edits)
    assert b"old" in (world["project"] / "plan.md").read_bytes()
    assert (world["project"] / "REFERENCE.md").read_text() == "foreign late edit\n"
    with rt.managed(world["project"]):
        pass


def test_reader_is_readonly_and_cannot_enter_while_writer_holds_directory(world, edits):
    p = world["project"]
    old = originals(world)
    before = list(p.rglob("*"))
    with rt.managed(p):
        pass
    assert list(p.rglob("*")) == before and originals(world) == old
    code = """import sys,fcntl,os,time\nfd=os.open(sys.argv[1],os.O_RDONLY)\nfcntl.flock(fd,fcntl.LOCK_EX)\nprint('locked',flush=True)\ntime.sleep(12)\n"""
    process = subprocess.Popen(
        [sys.executable, "-c", code, str(p)], stdout=subprocess.PIPE, text=True
    )
    try:
        assert process.stdout.readline().strip() == "locked"
        with pytest.raises(rt.RecordTransactionError, match="bounded lock"):
            with rt.managed(p):
                pass
    finally:
        process.terminate()
        process.wait(timeout=5)
    assert originals(world) == old


def test_actual_stage_fsync_source_mode_and_bytes(world, edits, monkeypatch):
    observed = []
    real = rt.os.fsync

    def sync(fd):
        info = os.fstat(fd)
        observed.append((info.st_ino, info.st_mode & 0o777))
        return real(fd)

    monkeypatch.setattr(rt.os, "fsync", sync)
    apply(world, edits)
    for name in ["plan.md", "REFERENCE.md"]:
        info = (world["project"] / name).stat()
        assert (info.st_ino, info.st_mode & 0o777) in observed


@pytest.mark.parametrize("point", [1, 2, 3, 4])
def test_each_journal_or_target_replace_failure_is_recoverable(
    world, edits, monkeypatch, point
):
    original = rt.os.replace
    count = 0

    def replace(src, dst):
        nonlocal count
        count += 1
        if count == point:
            raise OSError("replace fault")
        return original(src, dst)

    with monkeypatch.context() as patch:
        patch.setattr(rt.os, "replace", replace)
        with pytest.raises(OSError):
            apply(world, edits)
    assert recover(world)["status"] == "committed"


@pytest.mark.parametrize("point", [1, 2, 3])
def test_each_directory_rename_failure(world, edits, monkeypatch, point):
    original = rt.os.rename
    count = 0
    old = originals(world)

    def rename(src, dst):
        nonlocal count
        count += 1
        if count == point:
            raise OSError("rename fault")
        return original(src, dst)

    with monkeypatch.context() as patch:
        patch.setattr(rt.os, "rename", rename)
        with pytest.raises(OSError):
            apply(world, edits)
    if (world["project"] / rt.STORE / "active").exists():
        assert recover(world)["status"] == "committed"
    else:
        assert originals(world) == old


def test_initial_metadata_sibling_must_be_authorized(world, edits):
    p = world["project"]
    write_board(
        world,
        claims="; ".join(
            str(p / x) for x in ["plan.md", "REFERENCE.md", ".record-transactions/"]
        ),
    )
    old = originals(world)
    with pytest.raises(rt.RecordTransactionError):
        apply(world, edits)
    assert originals(world) == old
    assert not list(p.glob(".record-transactions*"))


def test_claim_revoked_after_last_target_prevents_completion_claim(
    world, edits, monkeypatch
):
    original = rt.os.replace

    def replace(src, dst):
        result = original(src, dst)
        if Path(dst).name == "REFERENCE.md":
            write_board(world, claims=str(world["project"] / "foreign/**"))
        return result

    with monkeypatch.context() as patch:
        patch.setattr(rt.os, "replace", replace)
        with pytest.raises(rt.RecordTransactionError):
            apply(world, edits)
    assert all(b"new" in data for data in originals(world).values())
    assert (world["project"] / rt.STORE / "active").is_dir()
    write_board(world)
    assert recover(world)["status"] == "committed"


@pytest.mark.parametrize(
    "kind", ["spec-symlink", "spec-hardlink", "oversize", "duplicate", "bad-native"]
)
def test_bounded_cli_request_failures_preserve_all_records(world, edits, kind):
    scratch = world["scratch"]
    spec = scratch / "request.json"
    actor = scratch / "actor.json"
    spec.write_text(json.dumps(edits))
    actor.write_text(json.dumps(world["actor"]["native_payload"]))
    if kind == "spec-symlink":
        other = scratch / "source.json"
        spec.rename(other)
        spec.symlink_to(other)
    elif kind == "spec-hardlink":
        os.link(spec, scratch / "alias.json")
    elif kind == "oversize":
        with spec.open("wb") as out:
            out.truncate(rt.MAX_FILE_BYTES + 1)
    elif kind == "duplicate":
        spec.write_text('[{"file":"plan.md","file":"REFERENCE.md","edits":[]}]')
    else:
        actor.write_text("[]")
    old = originals(world)
    code = context_edit.main(
        [
            "apply-transaction",
            "--project",
            str(world["project"]),
            "--board",
            str(world["board"]),
            "--native-payload",
            str(actor),
            "--files",
            str(spec),
        ]
    )
    assert code == 1
    assert originals(world) == old

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

import project_state as state

import coordination as engine


def test_manifest_parent_observations_share_prefixes_and_recheck(tmp_path, monkeypatch):
    tmp_path = tmp_path.resolve()
    common = tmp_path / "shared" / "deep" / "prefix"
    common.mkdir(parents=True)
    for n in range(60):
        (common / f"group-{n}").mkdir()
    real = state._manifest_parent_snapshot
    calls = []
    def observe(path):
        calls.append(path)
        return real(path)
    monkeypatch.setattr(state, "_manifest_parent_snapshot", observe)
    paths = [str(common / f"group-{n % 120}" / f"entry-{n}") for n in range(6000)]
    normalizer = state._ManifestPathObservations()
    first = [normalizer(path) for path in paths]
    assert [normalizer(path) for path in paths] == first
    # Only the filesystem root needs full ancestor resolution; all distinct
    # existing and missing parents share the ordinary directory prefixes.
    assert calls == [Path(tmp_path.anchor)]
    normalizer.verify()
    assert calls == [Path(tmp_path.anchor)] * 2
    assert first == paths


@pytest.mark.parametrize("change", ["replace", "retarget", "missing-symlink"])
def test_manifest_prefix_change_refuses_even_when_leaf_parent_is_unchanged(tmp_path, change):
    root = tmp_path / "root"
    root.mkdir()
    branch = root / "branch"
    branch.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(root, target_is_directory=True)
    cache = state._ManifestPathObservations()
    if change == "missing-symlink":
        raw = str(root / "missing" / "deeper" / "entry")
        assert cache(raw) == raw
        (root / "missing").symlink_to(branch, target_is_directory=True)
    else:
        raw = str((alias if change == "retarget" else root) / "branch" / "entry")
        assert cache(raw) == str(branch / "entry")
        root.rename(tmp_path / "old-root")
        root.mkdir()
        (tmp_path / "old-root" / "branch").rename(branch)
        if change == "retarget":
            alias.unlink()
            alias.symlink_to(tmp_path / "old-root", target_is_directory=True)
    with pytest.raises(state.ProjectStateError, match="manifest parent changed"):
        cache.verify()
    fresh = state._ManifestPathObservations()
    assert fresh(raw) == state._dirty_manifest_path(raw)
    fresh.verify()


@pytest.mark.parametrize("alias_first", [False, True])
def test_manifest_prefix_replacement_during_final_descendant_check_refuses(tmp_path, monkeypatch, alias_first):
    root = tmp_path / "root"
    branch = root / "branch"
    leaf_parent = branch / "child"
    leaf_parent.mkdir(parents=True)
    cache = state._ManifestPathObservations()
    if alias_first:
        alias = tmp_path / "alias"
        alias.symlink_to(branch, target_is_directory=True)
        cache(str(alias / "child" / "entry"))
    cache(str(leaf_parent / "entry"))
    real = cache._directory_identity
    changed = False
    def race(path, initial=None):
        nonlocal changed
        result = real(path, initial)
        if path == leaf_parent and not changed:
            changed = True
            root.rename(tmp_path / "old-root")
            root.mkdir()
            (tmp_path / "old-root" / "branch").rename(branch)
        return result
    monkeypatch.setattr(cache, "_directory_identity", race)
    with pytest.raises(state.ProjectStateError, match="manifest parent changed"):
        cache.verify()
    assert changed


@pytest.mark.parametrize("replaced", ["lexical", "canonical"])
def test_manifest_alias_final_check_closes_observed_ancestors(tmp_path, monkeypatch, replaced):
    lexical, canonical = tmp_path / "lexical", tmp_path / "canonical"
    (lexical / "kept").mkdir(parents=True)
    target = canonical / "target"
    target.mkdir(parents=True)
    (canonical / "kept").mkdir()
    alias = lexical / "alias"
    alias.symlink_to(target, target_is_directory=True)
    cache = state._ManifestPathObservations()
    cache(str(lexical / "kept" / "entry"))
    cache(str(canonical / "kept" / "entry"))
    cache(str(alias / "entry"))
    victim = lexical if replaced == "lexical" else canonical
    expected = cache.directories[victim]
    original = state._manifest_parent_snapshot
    changed = False
    def replace_after_alias_observation(path):
        nonlocal changed
        result = original(path)
        if path == alias and not changed:
            changed = True
            victim.rename(tmp_path / "old-parent")
            victim.mkdir()
            child = "alias" if replaced == "lexical" else "target"
            (tmp_path / "old-parent" / child).rename(victim / child)
        return result
    monkeypatch.setattr(state, "_manifest_parent_snapshot", replace_after_alias_observation)
    with pytest.raises(state.ProjectStateError, match="manifest parent changed"):
        cache.verify()
    assert changed and cache._directory_identity(victim) != expected


def test_manifest_prefix_replacement_during_open_is_not_attributed(tmp_path, monkeypatch):
    parent = tmp_path / "parent"
    parent.mkdir()
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    original = state.os.open
    changed = False
    def replace(path, flags, *args, **kwargs):
        nonlocal changed
        if Path(path) == parent and not changed:
            changed = True
            parent.rename(tmp_path / "old-parent")
            parent.symlink_to(foreign, target_is_directory=True)
        return original(path, flags, *args, **kwargs)
    monkeypatch.setattr(state.os, "open", replace)
    cache = state._ManifestPathObservations()
    assert cache(str(parent / "entry")) is None
    assert changed
    with pytest.raises(state.ProjectStateError, match="manifest parent changed"):
        cache.verify()
    assert state._ManifestPathObservations()(str(parent / "entry")) == str(foreign / "entry")


@pytest.mark.parametrize("target", ["self", "cycle", "relative-up", "missing", "file"])
def test_manifest_prefix_alias_semantics_match_full_observer(tmp_path, target):
    real = tmp_path / "real"
    real.mkdir()
    alias = tmp_path / "alias"
    if target == "self":
        alias.symlink_to("alias")
    elif target == "cycle":
        alias.symlink_to("other")
        (tmp_path / "other").symlink_to("alias")
    elif target == "relative-up":
        alias.symlink_to("real/../real")
    elif target == "missing":
        alias.symlink_to("missing/deep")
    else:
        (tmp_path / "file").write_text("not a directory")
        alias.symlink_to("file")
    cache = state._ManifestPathObservations()
    for suffix in ("entry", "nested/entry"):
        raw = str(alias / suffix)
        assert cache(raw) == state._dirty_manifest_path(raw)
    cache.verify()


@pytest.mark.parametrize("change", ["retarget", "replace", "create", "invalid-to-valid"])
def test_manifest_parent_observation_drift_refuses_and_next_call_is_fresh(tmp_path, change):
    parent = tmp_path / "parent"
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(); b.mkdir()
    if change == "retarget": parent.symlink_to(a, target_is_directory=True)
    elif change == "replace": parent.mkdir()
    elif change == "invalid-to-valid": parent.write_text("not a directory")
    raw = str(parent / "entry")
    normalizer = state._ManifestPathObservations()
    before = normalizer(raw)
    if change == "retarget":
        parent.unlink(); parent.symlink_to(b, target_is_directory=True)
    elif change == "replace":
        parent.rename(tmp_path / "original-parent"); parent.mkdir()
    elif change == "create": parent.mkdir()
    else:
        parent.unlink(); parent.mkdir()
    with pytest.raises(state.ProjectStateError, match="manifest parent changed"):
        normalizer.verify()
    fresh = state._ManifestPathObservations()
    assert fresh(raw) == state._dirty_manifest_path(raw)
    fresh.verify()
    if change in {"retarget", "invalid-to-valid"}: assert fresh(raw) != before


def test_manifest_parent_cache_preserves_alias_and_literal_leaf(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(real, target_is_directory=True)
    leaf = real / "leaf"
    leaf.symlink_to("unfollowed-target")
    cache = state._ManifestPathObservations()
    assert cache(str(alias / "leaf")) == str(leaf)
    for invalid in ("relative", str(alias) + "/../leaf", str(alias) + "//leaf"):
        assert cache(invalid) is None
    cache.verify()


@pytest.mark.parametrize("content,typed,expected", [
    (None, None, "owner"), ("a", None, None), ("b", None, "owner"),
    (None, "a", None), ("a", "b", None), ("b", "b", "owner"),
])
def test_resolver_honors_both_attribution_hash_maps(tmp_path, content, typed, expected):
    path = str(tmp_path / "entry")
    manifest = {"_kind": "manifest", "session_id": "owner", "paths": [path]}
    if content is not None:
        manifest["content_hashes"] = {path: content * 64}
    if typed is not None:
        manifest["path_hashes"] = {path: typed * 64}
        manifest["path_kinds"] = {path: "file"}
    assert state._manifest_for_dirty([{"path": path, "sha256": "b" * 64, "kind": "file"}], [manifest]) == expected


@pytest.mark.parametrize("kind", ["deleted", "symlink", "directory"])
def test_resolver_preserves_typed_custody_and_refuses_replacement(tmp_path, kind):
    path = tmp_path / "entry"
    if kind == "directory":
        path.mkdir()
    elif kind == "symlink":
        path.symlink_to("unfollowed")
    snapshot = state._dirty_leaf_snapshot(path)
    manifest = {"_kind": "manifest", "session_id": "owner", "paths": [str(path)],
                "path_hashes": {str(path): snapshot["sha256"]},
                "content_hashes": {str(path): snapshot["sha256"]},
                "path_kinds": {str(path): kind}}
    assert state._manifest_for_dirty([{"path": str(path), **snapshot}], [manifest]) == "owner"
    if kind == "directory":
        (path / "new").write_text("foreign")
    else:
        if kind == "symlink":
            path.unlink()
        path.write_text("foreign")
    assert state._manifest_for_dirty([{"path": str(path), **state._dirty_leaf_snapshot(path)}], [manifest]) is None


@pytest.mark.parametrize("bad", [[], {"relative": "a" * 64}, {"path": "bad"}])
def test_resolver_refuses_malformed_content_attribution(tmp_path, bad):
    path = str(tmp_path / "entry")
    value = {path: "bad"} if bad == {"path": "bad"} else bad
    manifest = {"_kind": "manifest", "session_id": "owner", "paths": [path], "content_hashes": value}
    assert state._manifest_for_dirty([{"path": path, "sha256": "b" * 64}], [manifest]) is None


@pytest.mark.parametrize("maps", ["content", "both", "typed-only"])
@pytest.mark.parametrize("record_kind", [False, True])
def test_file_to_symlink_hash_domain_overlap_never_transfers_ownership(tmp_path, maps, record_kind):
    path = tmp_path / "entry"
    digest = hashlib.sha256(b"symlink\0foreign-target").hexdigest()
    path.symlink_to("foreign-target")
    row = {"path": str(path), **state._dirty_leaf_snapshot(path)}
    assert row["sha256"] == digest  # Exact domain overlap, not a SHA collision.
    manifest = {"_kind": "manifest", "session_id": "original-writer", "paths": [str(path)]}
    if maps in {"content", "both"}: manifest["content_hashes"] = {str(path): digest}
    if maps in {"typed-only", "both"}: manifest["path_hashes"] = {str(path): digest}
    if record_kind: manifest["path_kinds"] = {str(path): "file"}
    assert state._manifest_for_dirty([row], [manifest]) is None


@pytest.mark.parametrize("record_kind", [False, True])
def test_symlink_to_file_with_same_typed_digest_is_not_reattribution(tmp_path, record_kind):
    path = tmp_path / "entry"
    path.write_bytes(b"symlink\0foreign-target")
    row = {"path": str(path), **state._dirty_leaf_snapshot(path)}
    manifest = {"_kind": "manifest", "session_id": "link-writer", "paths": [str(path)],
                "path_hashes": {str(path): row["sha256"]}}
    if record_kind: manifest["path_kinds"] = {str(path): "symlink"}
    assert state._manifest_for_dirty([row], [manifest]) is None


@pytest.mark.parametrize("hashed", [False, True])
def test_manifest_normalization_cost_and_complete_ownership(tmp_path, monkeypatch, hashed):
    first, second = tmp_path / "first", tmp_path / "second"
    dirty = [{"path": str(first), "sha256": "a" * 64},
             {"path": str(second), "sha256": "b" * 64}]
    manifest = {"_kind": "manifest", "session_id": "owner",
                "paths": [str(first), str(second), 7, "../invalid"]}
    if hashed:
        manifest["path_hashes"] = {str(first): "a" * 64, str(second): "b" * 64}
        manifest["path_kinds"] = {str(first): "file", str(second): "file"}
    original = state._dirty_manifest_path
    calls = []
    def counted(value):
        calls.append(value)
        return original(value)
    monkeypatch.setattr(state, "_dirty_manifest_path", counted)
    assert state._manifest_for_dirty(dirty, [manifest]) == "owner"
    assert len(calls) == (7 if hashed else 3)
    manifest["paths"].remove(str(second))
    assert state._manifest_for_dirty(dirty, [manifest]) is None
    manifest["paths"].append(str(second))
    manifest["path_hashes"] = {str(first): "c" * 64, str(second): "b" * 64}
    assert state._manifest_for_dirty(dirty, [manifest]) is None


def test_manifest_alias_hash_order_and_fresh_resolution(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(target, target_is_directory=True)
    leaf = target / "entry"
    alternate = alias / "entry"
    dirty = [{"path": str(leaf), "sha256": "a" * 64}]
    manifest = {"_kind": "manifest", "session_id": "owner", "paths": [str(alternate)],
                "path_hashes": {str(leaf): "b" * 64, str(alternate): "a" * 64},
                "path_kinds": {str(leaf): "file"}}
    assert state._manifest_for_dirty(dirty, [manifest]) == "owner"
    manifest["path_hashes"] = dict(reversed(list(manifest["path_hashes"].items())))
    assert state._manifest_for_dirty(dirty, [manifest]) is None
    manifest.pop("path_hashes")
    alias.unlink()
    alias.symlink_to(tmp_path, target_is_directory=True)
    assert state._manifest_for_dirty(dirty, [manifest]) is None


def test_manifest_parent_change_during_normalization_is_refused(tmp_path, monkeypatch):
    target = tmp_path / "target"
    target.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(target, target_is_directory=True)
    original = Path.resolve
    count = 0
    def retarget(path, *args, **kwargs):
        nonlocal count
        if path == alias:
            count += 1
            if count == 2:
                alias.unlink()
                alias.symlink_to(tmp_path, target_is_directory=True)
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "resolve", retarget)
    manifest = {"_kind": "manifest", "session_id": "owner", "paths": [str(alias / "entry")]}
    assert state._manifest_for_dirty([{"path": str(target / "entry"), "sha256": "a" * 64}], [manifest]) is None


def test_report_projection_preserves_schema_and_detaches_all_containers():
    from dataclasses import asdict
    candidate = state.Candidate("canonical", "/project", "/repo", None, "head", "tree", "time",
                                [{"path": "/project/x", "sha256": "digest", "mode": "0644"}], "owner")
    report = state.RecoveryReport("alpha", "LOCAL_RECOVERABLE", "/project", "head", "tree",
                                  [candidate], ["issue"], {"continuity": "LOCAL_READY"})
    projected = report.to_dict()
    assert projected == asdict(report)
    projected["candidates"][0]["dirty_files"][0]["sha256"] = "different"
    projected["candidates"][0]["dirty_files"].append({})
    projected["candidates"][0]["source"] = "other"
    projected["candidates"].append({})
    projected["issues"].append("other")
    projected["planes"]["continuity"] = "different"
    assert report.to_dict() == asdict(report)
    assert candidate.dirty_files == [{"path": "/project/x", "sha256": "digest", "mode": "0644"}]
    assert candidate.source == "canonical" and len(report.candidates) == 1
    assert report.issues == ["issue"] and report.planes == {"continuity": "LOCAL_READY"}


def test_recovery_serializes_manifest_once_and_preserves_related_receipt(tmp_path, monkeypatch):
    repo, project = init_repo(tmp_path)
    context = project / "CONTEXT.md"
    context.write_text(context.read_text() + "changed\n")
    manifest = {"_kind": "manifest", "session_id": "owner", "paths": [str(context)]}
    receipt = {"_kind": "receipt", "session_id": "owner"}
    monkeypatch.setattr(state, "_manifest_inventory", lambda *a, **k: ([manifest, receipt], []))
    original = state.json.dumps
    seen = []
    def counted(value, *args, **kwargs):
        if value is manifest or value is receipt:
            seen.append(value)
        assert not (isinstance(value, list) and value and isinstance(value[0], dict)
                    and "sha256" in value[0]), "dirty inventories must not be serialized to compare them"
        return original(value, *args, **kwargs)
    monkeypatch.setattr(state.json, "dumps", counted)
    report = state.resolve_project("alpha", repo / "projects/index.yaml", fetch=False)
    assert report.status == "LOCAL_RECOVERABLE"
    assert seen == [manifest, receipt]
    assert [candidate.source for candidate in report.candidates if candidate.session_id == "owner"][-2:] == ["manifest", "receipt"]


@pytest.mark.parametrize("drift", [False, True])
def test_resolver_parent_drift_prevents_optional_fast_forward(tmp_path, monkeypatch, drift):
    repo, project = init_repo(tmp_path)
    peer = tmp_path / "peer"
    run("git", "clone", str(tmp_path / "remote.git"), str(peer), cwd=tmp_path)
    for key, value in [("user.email", "fixture@example.invalid"), ("user.name", "Fixture"),
                       ("core.hooksPath", str(tmp_path / "fixture-hooks"))]:
        run("git", "config", key, value, cwd=peer)
    commit_version(peer, peer / "projects/alpha", "2.0.0")
    run("git", "push", "origin", "main", cwd=peer)
    alias = tmp_path / "alias"
    alias.symlink_to(project, target_is_directory=True)
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()
    manifest = {"_kind": "receipt", "session_id": "fixture", "paths": [str(alias / "CONTEXT.md")]}
    monkeypatch.setattr(state, "_manifest_inventory", lambda *a, **k: ([manifest], []))
    original = state._latest_session_date
    def after_relevance(path):
        result = original(path)
        if drift:
            alias.unlink(); alias.symlink_to(unrelated, target_is_directory=True)
        return result
    monkeypatch.setattr(state, "_latest_session_date", after_relevance)
    effects = []
    def fast_forward(*args):
        effects.append(args)
        return False, "fixture effect boundary observed"
    monkeypatch.setattr(state, "_safe_fast_forward", fast_forward)
    report = state.resolve_project("alpha", repo / "projects/index.yaml", fetch=True, fast_forward_canonical=True)
    if drift:
        assert report.status == "UNKNOWN" and report.selected_path is None
        assert any("manifest parent changed" in issue for issue in report.issues)
        assert effects == []
    else:
        assert report.status == "PASS" and len(effects) == 1


@pytest.mark.parametrize("reader", [state.read_operational_state, state._load_json])
def test_state_json_shared_size_boundary(tmp_path, monkeypatch, reader):
    monkeypatch.setattr(state, "MAX_STATE_JSON_BYTES", 128)
    path = tmp_path / state.STATE_FILE
    raw = b'{"schema_version": 1}'
    path.write_bytes(raw + b" " * (128 - len(raw)))
    assert reader(path) == {"schema_version": 1}
    assert state._sha_file(path) == hashlib.sha256(path.read_bytes()).hexdigest()
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(state.ProjectStateError, match="128-byte limit"):
        reader(path)
    with pytest.raises(state.ProjectStateError, match="128-byte limit"):
        state._sha_file(path)


@pytest.mark.parametrize("raw", [
    b'{"status": "active", "status": "archived"}',
    b'{"nested": {"value": 1, "value": 2}}',
    b'{"truncated":', b"[]", b"null", b'{} trailing', b'{"invalid": "\xff"}',
    b'{"value": NaN}', b'{"value": Infinity}', b'{"value": 1e309}',
    b'{"nested":' + b"[" * 2000 + b"0" + b"]" * 2000 + b"}",
], ids=["duplicate", "nested-duplicate", "truncated", "array", "null", "trailing", "utf8", "nan", "infinity", "float-overflow", "depth"])
def test_state_json_rejects_malformed_objects(tmp_path, raw):
    path = tmp_path / state.STATE_FILE
    path.write_bytes(raw)
    with pytest.raises(state.ProjectStateError):
        state.read_operational_state(path)
    assert path.read_bytes() == raw


def test_state_json_depth_boundary_ignores_escaped_string_content(tmp_path):
    path = tmp_path / state.STATE_FILE
    literal = json.dumps("[{" * 100 + '\\"' + "]}" * 100)
    nested = "[" * (state.MAX_JSON_DEPTH - 1) + literal + "]" * (state.MAX_JSON_DEPTH - 1)
    raw = '{"value":' + nested + "}"
    path.write_text(raw)
    assert state.read_operational_state(path) == json.loads(raw)
    path.write_text('{"value":[' + nested + "]}")
    with pytest.raises(state.ProjectStateError, match="nesting"):
        state.read_operational_state(path)


@pytest.mark.parametrize("kind", ["directory", "symlink", "broken-symlink", "fifo"])
def test_state_json_refuses_nonregular_inputs(tmp_path, kind):
    path = tmp_path / state.STATE_FILE
    if kind == "directory":
        path.mkdir()
    elif kind == "fifo":
        os.mkfifo(path)
    else:
        target = tmp_path / "target.json"
        if kind == "symlink":
            target.write_text("{}")
        path.symlink_to(target)
    with pytest.raises(state.ProjectStateError, match="regular nonsymlink"):
        state.read_operational_state(path)


def test_state_json_refuses_symlink_raced_after_lstat(tmp_path, monkeypatch):
    path = tmp_path / state.STATE_FILE
    path.write_text("{}")
    target = tmp_path / "target.json"
    target.write_text("{}")
    original = os.open

    def replace_then_open(candidate, flags, *args, **kwargs):
        if candidate == path:
            path.unlink()
            path.symlink_to(target)
        return original(candidate, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", replace_then_open)
    with pytest.raises(state.ProjectStateError):
        state.read_operational_state(path)


def test_state_json_actual_read_is_bounded_when_input_grows(tmp_path, monkeypatch):
    path = tmp_path / state.STATE_FILE
    path.write_text("{}")
    reads = []
    original = os.fdopen

    class GrowingFile:
        def __init__(self, handle):
            self.handle = handle

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.handle.close()

        def fileno(self):
            return self.handle.fileno()

        def read(self, size):
            reads.append(size)
            with path.open("ab") as writer:
                writer.write(b" " * 256)
            return self.handle.read(size)

    monkeypatch.setattr(os, "fdopen", lambda *args: GrowingFile(original(*args)))
    with pytest.raises(state.ProjectStateError, match="128-byte limit"):
        state.read_json_object(path, max_bytes=128)
    assert reads == [129]


@pytest.mark.parametrize("change", ["replace", "modify"])
def test_state_json_refuses_changed_read_snapshot(tmp_path, monkeypatch, change):
    path = tmp_path / state.STATE_FILE
    path.write_text('{"value": 1}')
    original = os.fstat
    calls = 0

    def change_before_after_stat(fd):
        nonlocal calls
        calls += 1
        if calls == 2:
            if change == "replace":
                replacement = tmp_path / "replacement.json"
                replacement.write_text('{"value": 1}')
                os.replace(replacement, path)
            else:
                before = path.stat()
                path.write_text('{"value": 2}')
                os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000))
        return original(fd)

    monkeypatch.setattr(os, "fstat", change_before_after_stat)
    with pytest.raises(state.ProjectStateError, match="changed during reading"):
        state.read_operational_state(path)


def test_state_compiler_refuses_oversize_before_changing_project(tmp_path, monkeypatch):
    _repo, project = init_repo(tmp_path)
    parameters = dict(project_id="alpha", phase="planning", status="active",
        controlling_plan="resources/artifacts/plan.md", accepted_baseline="fixture",
        next_actions=["Review"], last_session="2026-09-03", session_id="fixture")
    state.build_operational_state(project, **parameters)
    paths = (project / "CONTEXT.md", project / state.STATE_FILE)
    before = {path: path.read_bytes() for path in paths}
    monkeypatch.setattr(state, "MAX_STATE_JSON_BYTES", 128)
    with pytest.raises(state.ProjectStateError, match="128-byte limit"):
        state.build_operational_state(project, **{**parameters, "phase": "changed"})
    assert {path: path.read_bytes() for path in paths} == before
    assert not list(project.glob(".*.tmp"))


@pytest.mark.parametrize("consumer", ["semantic", "doctor"])
def test_broken_state_symlink_is_invalid_evidence_not_legacy_absence(tmp_path, consumer):
    _repo, project = init_repo(tmp_path)
    state.build_operational_state(project, project_id="alpha", phase="planning", status="active",
        controlling_plan="resources/artifacts/plan.md", accepted_baseline="fixture",
        next_actions=["Review"], last_session="2026-09-03", session_id="fixture")
    assert state.semantic_issues(project) == []
    path = project / state.STATE_FILE
    path.unlink()
    path.symlink_to(tmp_path / "missing-state.json")
    if consumer == "semantic":
        assert any("regular nonsymlink" in issue for issue in state.semantic_issues(project))
    else:
        doctor = (Path(__file__).resolve().parents[2] / "synthesis-context-lifecycle"
                  / "scripts" / "context_doctor.py")
        result = subprocess.run([sys.executable, "-B", str(doctor), "--project", str(project),
            "--readiness", "local", "--no-report-cache", "--json"], capture_output=True, text=True)
        report = json.loads(result.stdout)
        assert result.returncode == 1 and report["ok"] is False
        assert any(finding["check"] == "semantic-current-state" and finding["severity"] == "defect"
                   and "regular nonsymlink" in finding["message"] for finding in report["findings"])
    assert path.is_symlink() and not path.exists()


@pytest.mark.parametrize("client", ["codex", "claude"])
@pytest.mark.parametrize("repeat", [False, True])
def test_stop_feedback_is_bounded_without_accepting_failed_checkpoint(
    client: str, repeat: bool, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    native = "018f0000-0000-7000-8000-000000000001"
    payload = {"hook_event_name": "Stop", "session_id": native,
               "turn_id": "fixture-turn", "stop_hook_active": repeat}
    monkeypatch.setattr(state, "observer_native_identity", lambda _payload: (client, native))
    code = state._emit_checkpoint_hook("UNKNOWN", ["fixture checkpoint is unresolved"], payload)
    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert code == 0
    report = json.loads(output["systemMessage"].removeprefix("PROJECT_CHECKPOINT_JSON: "))
    assert {k: v for k, v in report.items() if k != "publication"} == {
        "status": "UNKNOWN", "issues": ["fixture checkpoint is unresolved"],
        "checkpoint_accepted": False}
    assert report["publication"]["status"] == "UNKNOWN"
    assert report["publication"]["owner"] == "checkpoint_sync.py --flush-session"
    # An unreserved first Stop cannot request another turn either.
    assert output["continue"] is False
    assert "unresolved" in output["stopReason"]
    assert "decision" not in output and "reason" not in output


@pytest.mark.parametrize("payload", [{}, {"hook_event_name": "Stop"},
    {"hook_event_name": "Stop", "session_id": "fixture", "stop_hook_active": "false"}])
def test_stop_unidentifiable_failure_is_terminal(payload, capsys) -> None:
    assert state._emit_checkpoint_hook("UNKNOWN", ["identity unavailable"], payload) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["continue"] is False
    assert output.get("decision") != "block"
    assert '"checkpoint_accepted": false' in output["systemMessage"]


@pytest.mark.parametrize("verdict", ["PASS", "NOT_APPLICABLE"])
def test_repeated_stop_still_evaluates_and_reports_healthy_checkpoint(verdict, capsys) -> None:
    payload = {"hook_event_name": "Stop", "session_id": "018f0000-0000-7000-8000-000000000001",
               "stop_hook_active": True}
    assert state._emit_checkpoint_hook(verdict, [], payload) == 0
    output = json.loads(capsys.readouterr().out)
    assert "continue" not in output
    assert "decision" not in output
    assert f'"status": "{verdict}"' in output["systemMessage"]


def test_non_stop_checkpoint_failure_retains_nonzero_contract(capsys) -> None:
    assert state._emit_checkpoint_hook("FAIL", ["fixture failure"], {"hook_event_name": "SessionStart"}) == 2
    captured = capsys.readouterr()
    assert '"checkpoint_accepted": false' in json.loads(captured.out)["systemMessage"]
    assert "fixture failure" in captured.err


def test_stop_failure_remains_terminal_when_shared_adapter_cannot_import(monkeypatch, capsys) -> None:
    import builtins
    original = builtins.__import__

    def missing_adapter(name, *args, **kwargs):
        if name == "release_runtime":
            raise ImportError("fixture missing Stop adapter")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", missing_adapter)
    payload = {"hook_event_name": "Stop", "session_id": "018f0000-0000-7000-8000-000000000001",
               "stop_hook_active": False}
    assert state._emit_checkpoint_hook("FAIL", ["fixture failure"], payload) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["continue"] is False
    assert output.get("decision") != "block"
    assert '"checkpoint_accepted": false' in output["systemMessage"]


def run(*args: str, cwd: Path) -> str:
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def write_project(repo: Path, project_id: str = "alpha", version: str = "1.0.0") -> Path:
    project = repo / "projects" / project_id
    (project / "sessions").mkdir(parents=True, exist_ok=True)
    (project / "resources" / "artifacts").mkdir(parents=True, exist_ok=True)
    (repo / "projects" / "index.yaml").write_text(
        f"- id: {project_id}\n  status: active\n  last_session: '2026-09-01'\n",
        encoding="utf-8",
    )
    (project / "REFERENCE.md").write_text("# Reference\n", encoding="utf-8")
    (project / "sessions" / "2026-09.md").write_text(
        "### 2026-09-03 — current\n", encoding="utf-8"
    )
    (project / "resources" / "artifacts" / "plan.md").write_text(
        "# Plan\n", encoding="utf-8"
    )
    (project / "CONTEXT.md").write_text(
        "\n".join(
            [
                "# Context",
                "",
                f"**Phase:** release {version}",
                "**Status:** Active",
                "**Last session:** 2026-09-03",
                "",
                "[controlling plan](resources/artifacts/plan.md)",
                "",
                "## Baseline history",
                f"Accepted release snapshot: v{version}.",
                "",
                "## Handoff history",
                f"Snapshot recorded 2026-09-03 (v{version}).",
                "",
                "## What's Next",
                "- [ ] finish",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return project


def init_repo(root: Path, version: str = "1.0.0") -> tuple[Path, Path]:
    remote = root / "remote.git"
    repo = root / "repo"
    hooks = root / "fixture-hooks"
    hooks.mkdir()
    run("git", "init", "--bare", str(remote), cwd=root)
    run("git", "init", "-b", "main", str(repo), cwd=root)
    run("git", "config", "user.email", "fixture@example.invalid", cwd=repo)
    run("git", "config", "user.name", "Fixture", cwd=repo)
    run("git", "config", "core.hooksPath", str(hooks), cwd=repo)
    project = write_project(repo, version=version)
    run("git", "add", "projects", cwd=repo)
    run("git", "commit", "-m", "Initial project state", cwd=repo)
    run("git", "remote", "add", "origin", str(remote), cwd=repo)
    run("git", "push", "-u", "origin", "main", cwd=repo)
    run("git", "symbolic-ref", "HEAD", "refs/heads/main", cwd=remote)
    return repo, project


def commit_version(repo: Path, project: Path, version: str) -> str:
    text = (project / "CONTEXT.md").read_text(encoding="utf-8")
    text = text.replace("v1.0.0", f"v{version}").replace("release 1.0.0", f"release {version}")
    (project / "CONTEXT.md").write_text(text, encoding="utf-8")
    run("git", "add", str(project.relative_to(repo)), cwd=repo)
    run("git", "commit", "-m", "Advance project state", cwd=repo)
    return run("git", "rev-parse", "HEAD", cwd=repo)


def board(path: Path, rows: list[tuple[str, str, str, str]]) -> Path:
    header = (
        "# Board\nSchema: v4\n\n## Active sessions\n\n"
        "| session uuid | compact id | speakable id v1 | legacy id | agent | machine | client session ref | project | "
        "started | heartbeat | mode | workspace(s) / branch | goal | claimed areas (advisory lock) | context role | status |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
    )
    body = "".join(
        f"| {session} | {compact} | words-1 | | agent | machine | tool:{session} | {project} | "
        f"2026-09-03T12:00:00-04:00 | 2026-09-03T12:00:00-04:00 | interactive | {workspace} | fixture | "
        f"{workspace}/projects/{project}/** | owner | active |\n"
        for session, compact, project, workspace in rows
    )
    path.write_text(header + body + "\n## Messages\n\n## Protocol\n", encoding="utf-8")
    return path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_positive_controls_discover_canonical_worktree_ref_manifest_receipt_pointer_and_claim(tmp_path: Path) -> None:
    repo, project = init_repo(tmp_path)
    state_root = tmp_path / "state"
    (state_root / "pending").mkdir(parents=True)
    (state_root / "local-handoff").mkdir(parents=True)
    manifest = {"schema_version": 2, "session_id": "session-a", "paths": [str(project / "CONTEXT.md")]}
    (state_root / "pending" / (hashlib.sha256(b"session-a").hexdigest() + ".json")).write_text(json.dumps(manifest), encoding="utf-8")
    (state_root / "local-handoff" / (hashlib.sha256(b"session-a").hexdigest() + ".json")).write_text(json.dumps({"session_id": "session-a", "readiness": "LOCAL_READY", "results": []}), encoding="utf-8")
    checkpoint_receipts = tmp_path / "checkpoint-receipts"
    checkpoint_receipts.mkdir()
    (checkpoint_receipts / "bound.json").write_text(
        json.dumps({"session_id": "session-a", "project_id": "alpha"}),
        encoding="utf-8",
    )
    pointer = tmp_path / "active.json"
    pointer.write_text(json.dumps({"project": str(project)}), encoding="utf-8")
    claims = board(tmp_path / "board.md", [("018f0000-0000-7000-8000-000000000001", "s-abcd-efgh-jkmn", "alpha", str(repo))])
    report = state.resolve_project("alpha", repo / "projects" / "index.yaml", repo_guard_root=state_root, checkpoint_receipt_root=checkpoint_receipts, coordination_board=claims, pointer=pointer, fetch=False)
    assert {item.source for item in report.candidates} >= {"canonical", "worktree", "ref", "manifest", "receipt", "checkpoint-receipt", "pointer", "claim"}


def test_canonical_behind_isolated_worktree_selects_newer_without_mutation(tmp_path: Path) -> None:
    repo, project = init_repo(tmp_path)
    worktree = tmp_path / "newer"
    run("git", "worktree", "add", "-b", "feature/newer", str(worktree), cwd=repo)
    newer_project = worktree / "projects" / "alpha"
    newer = commit_version(worktree, newer_project, "2.0.0")
    original = run("git", "rev-parse", "HEAD", cwd=repo)
    report = state.resolve_project("alpha", repo / "projects" / "index.yaml", fetch=False)
    assert report.status == "PASS"
    assert report.selected_path == str(newer_project.resolve())
    assert report.selected_head == newer
    assert run("git", "rev-parse", "HEAD", cwd=repo) == original


def test_safe_fast_forward_preserves_unrelated_untracked_file(tmp_path: Path) -> None:
    repo, project = init_repo(tmp_path)
    peer = tmp_path / "peer"
    run("git", "clone", str(tmp_path / "remote.git"), str(peer), cwd=tmp_path)
    run("git", "config", "user.email", "fixture@example.invalid", cwd=peer)
    run("git", "config", "user.name", "Fixture", cwd=peer)
    run("git", "config", "core.hooksPath", str(tmp_path / "fixture-hooks"), cwd=peer)
    newer = commit_version(peer, peer / "projects" / "alpha", "2.0.0")
    run("git", "push", "origin", "main", cwd=peer)
    unrelated = repo / "notes.local"
    unrelated.write_text("preserve\n", encoding="utf-8")
    report = state.resolve_project("alpha", repo / "projects" / "index.yaml", fetch=True, fast_forward_canonical=True)
    assert report.selected_head == newer
    assert unrelated.read_text(encoding="utf-8") == "preserve\n"


def test_fast_forward_refuses_non_upstream_local_ref(tmp_path: Path) -> None:
    repo, project = init_repo(tmp_path)
    worktree = tmp_path / "newer"
    run("git", "worktree", "add", "-b", "feature/newer", str(worktree), cwd=repo)
    newer_project = worktree / "projects" / "alpha"
    newer = commit_version(worktree, newer_project, "2.0.0")
    run("git", "worktree", "remove", str(worktree), cwd=repo)
    original = run("git", "rev-parse", "HEAD", cwd=repo)
    report = state.resolve_project(
        "alpha",
        repo / "projects" / "index.yaml",
        fetch=True,
        fast_forward_canonical=True,
    )
    assert report.selected_head == newer
    assert report.selected_path is None
    assert any("not a fetched remote ref" in issue for issue in report.issues)
    assert run("git", "rev-parse", "HEAD", cwd=repo) == original


def test_local_ahead_is_selected_and_remote_ahead_is_selected_after_fetch(tmp_path: Path) -> None:
    repo, project = init_repo(tmp_path)
    local = commit_version(repo, project, "2.0.0")
    report = state.resolve_project("alpha", repo / "projects" / "index.yaml", fetch=False)
    assert report.selected_head == local
    run("git", "reset", "--hard", "origin/main", cwd=repo)
    peer = tmp_path / "peer"
    run("git", "clone", str(tmp_path / "remote.git"), str(peer), cwd=tmp_path)
    run("git", "config", "user.email", "fixture@example.invalid", cwd=peer)
    run("git", "config", "user.name", "Fixture", cwd=peer)
    run("git", "config", "core.hooksPath", str(tmp_path / "fixture-hooks"), cwd=peer)
    remote = commit_version(peer, peer / "projects" / "alpha", "3.0.0")
    run("git", "push", "origin", "main", cwd=peer)
    report = state.resolve_project("alpha", repo / "projects" / "index.yaml", fetch=True)
    assert report.selected_head == remote


def test_diverged_project_states_fail_closed(tmp_path: Path) -> None:
    repo, project = init_repo(tmp_path)
    run("git", "checkout", "-b", "feature/a", cwd=repo)
    commit_version(repo, project, "2.0.0")
    run("git", "checkout", "main", cwd=repo)
    commit_version(repo, project, "3.0.0")
    report = state.resolve_project("alpha", repo / "projects" / "index.yaml", fetch=False)
    assert report.status == "CONFLICT"
    assert any("diverg" in issue.lower() for issue in report.issues)


def test_deleted_registered_worktree_is_reported_not_ignored(tmp_path: Path) -> None:
    repo, _project = init_repo(tmp_path)
    raw_gitdir = Path(run("git", "rev-parse", "--git-common-dir", cwd=repo))
    gitdir = (repo / raw_gitdir).resolve() if not raw_gitdir.is_absolute() else raw_gitdir.resolve()
    metadata = gitdir / "worktrees" / "gone"
    metadata.mkdir(parents=True)
    (metadata / "gitdir").write_text(str(tmp_path / "gone" / ".git") + "\n", encoding="utf-8")
    report = state.resolve_project("alpha", repo / "projects" / "index.yaml", fetch=False)
    assert report.status == "UNKNOWN"
    assert any("missing worktree" in issue.lower() for issue in report.issues)


def test_dirty_attributed_project_file_is_local_recoverable(tmp_path: Path) -> None:
    repo, project = init_repo(tmp_path)
    context = project / "CONTEXT.md"
    context.write_text(context.read_text(encoding="utf-8") + "interrupted\n", encoding="utf-8")
    state_root = tmp_path / "state"
    pending = state_root / "pending"
    pending.mkdir(parents=True)
    session = "session-a"
    payload = {"schema_version": 2, "session_id": session, "paths": [str(context)], "path_hashes": {str(context): sha(context)}, "path_kinds": {str(context): "file"}}
    (pending / (hashlib.sha256(session.encode()).hexdigest() + ".json")).write_text(json.dumps(payload), encoding="utf-8")
    report = state.resolve_project("alpha", repo / "projects" / "index.yaml", repo_guard_root=state_root, fetch=False)
    assert report.status == "LOCAL_RECOVERABLE"
    assert report.selected_path == str(project.resolve())


def test_dirty_state_on_older_head_conflicts_with_newer_committed_state(tmp_path: Path) -> None:
    repo, project = init_repo(tmp_path)
    newer_worktree = tmp_path / "newer"
    run("git", "worktree", "add", "-b", "feature/newer", str(newer_worktree), cwd=repo)
    commit_version(newer_worktree, newer_worktree / "projects" / "alpha", "2.0.0")
    context = project / "CONTEXT.md"
    context.write_text(context.read_text(encoding="utf-8") + "interrupted\n", encoding="utf-8")
    state_root = tmp_path / "state"
    pending = state_root / "pending"
    pending.mkdir(parents=True)
    session = "session-a"
    payload = {
        "schema_version": 2,
        "session_id": session,
        "paths": [str(context)],
        "path_hashes": {str(context): sha(context)},
        "path_kinds": {str(context): "file"},
    }
    (pending / (hashlib.sha256(session.encode()).hexdigest() + ".json")).write_text(
        json.dumps(payload), encoding="utf-8"
    )
    report = state.resolve_project(
        "alpha", repo / "projects" / "index.yaml", repo_guard_root=state_root, fetch=False
    )
    assert report.status == "CONFLICT"
    assert any("older" in issue.lower() for issue in report.issues)


def test_two_attributed_dirty_worktrees_with_different_hashes_conflict(tmp_path: Path) -> None:
    repo, project = init_repo(tmp_path)
    other = tmp_path / "other"
    run("git", "worktree", "add", "-b", "feature/other", str(other), cwd=repo)
    paths = [project / "CONTEXT.md", other / "projects" / "alpha" / "CONTEXT.md"]
    paths[0].write_text(paths[0].read_text(encoding="utf-8") + "a\n", encoding="utf-8")
    paths[1].write_text(paths[1].read_text(encoding="utf-8") + "b\n", encoding="utf-8")
    root = tmp_path / "state" / "pending"
    root.mkdir(parents=True)
    for index, path in enumerate(paths):
        session = f"session-{index}"
        payload = {"schema_version": 2, "session_id": session, "paths": [str(path)], "path_hashes": {str(path): sha(path)}, "path_kinds": {str(path): "file"}}
        (root / (hashlib.sha256(session.encode()).hexdigest() + ".json")).write_text(json.dumps(payload), encoding="utf-8")
    report = state.resolve_project("alpha", repo / "projects" / "index.yaml", repo_guard_root=root.parent, fetch=False)
    assert report.status == "CONFLICT"


def test_absent_pointer_does_not_block_and_stale_pointer_cannot_override(tmp_path: Path) -> None:
    repo, project = init_repo(tmp_path)
    report = state.resolve_project("alpha", repo / "projects" / "index.yaml", pointer=tmp_path / "absent.json", fetch=False)
    assert report.selected_path == str(project.resolve())
    stale = tmp_path / "stale.json"
    stale.write_text(json.dumps({"project": str(tmp_path / "gone")}), encoding="utf-8")
    report = state.resolve_project("alpha", repo / "projects" / "index.yaml", pointer=stale, fetch=False)
    assert report.selected_path == str(project.resolve())
    assert any("pointer" in issue.lower() for issue in report.issues)


def test_stale_index_date_is_derived_as_a_warning_not_selected_truth(tmp_path: Path) -> None:
    repo, _project = init_repo(tmp_path)
    report = state.resolve_project("alpha", repo / "projects" / "index.yaml", fetch=False)
    assert report.status == "PASS"
    assert any("last_session" in issue and "2026-09-03" in issue for issue in report.issues)


def test_future_date_in_session_body_does_not_advance_derived_session(tmp_path: Path) -> None:
    repo, project = init_repo(tmp_path)
    (project / "sessions" / "2026-09.md").write_text(
        "### 2026-09-03 — current\n\nNext review: 2026-09-30.\n",
        encoding="utf-8",
    )
    report = state.resolve_project(
        "alpha", repo / "projects" / "index.yaml", fetch=False
    )
    assert any("derived value is 2026-09-03" in issue for issue in report.issues)
    assert not any("2026-09-30" in issue for issue in report.issues)


def test_internal_version_contradiction_is_semantic_failure(tmp_path: Path) -> None:
    _repo, project = init_repo(tmp_path)
    context = project / "CONTEXT.md"
    context.write_text(context.read_text(encoding="utf-8").replace("**Phase:** release 1.0.0", "**Phase:** current release 1.0.0") + "\nLater release shipped: v4.0.0.\n", encoding="utf-8")
    issues = state.semantic_issues(project)
    assert any("current" in issue.lower() and "4.0.0" in issue for issue in issues)


@pytest.mark.parametrize(
    "recorded",
    [
        "Candidate 4.95.7 is under verification, not released.",
        "Release candidate v4.95.7 remains under verification.",
        "Planned release: v4.95.7.",
        "v4.95.7 is not released.",
        "Target release v4.95.7, pending publication.",
        "Documentation example: v9.0.0.",
        "CI verified candidate v4.95.7; publication pending.",
    ],
)
def test_unreleased_or_reference_versions_do_not_claim_release_currency(
    tmp_path: Path, recorded: str,
) -> None:
    _repo, project = init_repo(tmp_path, version="4.95.6")
    context = project / "CONTEXT.md"
    context.write_text(context.read_text(encoding="utf-8") + "\n" + recorded + "\n")

    issues = state.semantic_issues(project)

    assert not any("older than later recorded release" in issue for issue in issues)
    assert recorded in context.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "recorded",
    [
        "Candidate v4.95.8 is not released; later release shipped: v4.95.7.",
        "Released v4.95.7; planned candidate v4.95.8.",
        "v4.95.7 shipped; v4.95.8 is not released.",
        "Released v4.95.7 and candidate v4.95.8.",
        "Candidate v4.95.8, released v4.95.7.",
        "Released v4.95.7, with v4.95.8 planned.",
    ],
)
def test_mixed_candidate_and_shipped_assertions_keep_actual_release_evidence(
    tmp_path: Path, recorded: str,
) -> None:
    _repo, project = init_repo(tmp_path, version="4.95.6")
    context = project / "CONTEXT.md"
    context.write_text(context.read_text(encoding="utf-8") + "\n" + recorded + "\n")

    issues = state.semantic_issues(project)

    assert [issue for issue in issues if "older than later recorded release" in issue] == [
        "current release 4.95.6 is older than later recorded release 4.95.7"
    ]


def test_structured_candidate_description_preserves_accepted_release_baseline(
    tmp_path: Path,
) -> None:
    _repo, project = init_repo(tmp_path, version="4.95.6")
    context = project / "CONTEXT.md"
    context.write_text(
        "# Context\n\nCandidate 4.95.7 is authored; public release remains pending.\n",
        encoding="utf-8",
    )
    baseline = (
        "4.95.6 dual-client reload accepted; 4.95.7 runtime and preserved-change "
        "candidate under verification, not released"
    )
    state.build_operational_state(
        project,
        project_id="alpha",
        phase="Runtime currency and held-change integration in progress",
        status="active",
        controlling_plan="resources/artifacts/plan.md",
        accepted_baseline=baseline,
        next_actions=["Complete candidate verification and public release"],
        last_session="2026-09-03",
        session_id="018f0000-0000-7000-8000-000000000001",
    )

    issues = state.semantic_issues(project)

    assert not issues
    assert baseline in context.read_text(encoding="utf-8")


def test_future_phase_candidate_cannot_mask_stale_structured_accepted_baseline(
    tmp_path: Path,
) -> None:
    _repo, project = init_repo(tmp_path, version="4.95.6")
    context = project / "CONTEXT.md"
    context.write_text(
        "# Context\n\nLater release shipped: v4.95.7.\n", encoding="utf-8",
    )
    state.build_operational_state(
        project,
        project_id="alpha",
        phase="Verify release candidate v4.95.8, not released",
        status="active",
        controlling_plan="resources/artifacts/plan.md",
        accepted_baseline="4.95.6 accepted release",
        next_actions=["Complete candidate verification"],
        last_session="2026-09-03",
        session_id="018f0000-0000-7000-8000-000000000001",
    )

    issues = state.semantic_issues(project)

    assert [issue for issue in issues if "older than later recorded release" in issue] == [
        "current release 4.95.6 is older than later recorded release 4.95.7"
    ]


def test_structured_state_rejects_uncompiled_current_prose(tmp_path: Path) -> None:
    _repo, project = init_repo(tmp_path)
    context = project / "CONTEXT.md"
    context.write_text(
        context.read_text(encoding="utf-8")
        + "\n## Current handoff\n\n*State as of: 2026-09-03 (v0.9.0 installed)*\n",
        encoding="utf-8",
    )
    reference = project / "reference"
    reference.mkdir()
    (reference / "baselines.md").write_text(
        "# Baselines\n\n## Current reconciled baseline\n\nRelease v0.9.0.\n",
        encoding="utf-8",
    )
    state.build_operational_state(
        project,
        project_id="alpha",
        phase="release 1.0.0",
        status="active",
        controlling_plan="resources/artifacts/plan.md",
        accepted_baseline="1.0.0",
        next_actions=["finish"],
        last_session="2026-09-03",
        session_id="018f0000-0000-7000-8000-000000000001",
    )

    issues = state.semantic_issues(project)

    assert any(
        "uncompiled current-state prose" in issue and "CONTEXT.md" in issue
        for issue in issues
    )
    assert any(
        "uncompiled current-state prose" in issue
        and "reference/baselines.md" in issue
        for issue in issues
    )


def test_structured_state_rejects_setext_and_punctuated_current_labels(
    tmp_path: Path,
) -> None:
    _repo, project = init_repo(tmp_path)
    context = project / "CONTEXT.md"
    context.write_text(
        context.read_text(encoding="utf-8")
        + "\nAccepted baseline:\n------------------\n\nRelease v0.9.0.\n"
        + "\n## Current handoff:\n\n**State as of — v0.9.0**\n",
        encoding="utf-8",
    )
    reference = project / "reference"
    reference.mkdir()
    (reference / "baselines.md").write_text(
        "# Baselines\n\nNext checkpoint:\n================\n\nRelease v0.9.0.\n",
        encoding="utf-8",
    )
    state.build_operational_state(
        project,
        project_id="alpha",
        phase="release 1.0.0",
        status="active",
        controlling_plan="resources/artifacts/plan.md",
        accepted_baseline="1.0.0",
        next_actions=["finish"],
        last_session="2026-09-03",
        session_id="018f0000-0000-7000-8000-000000000001",
    )

    issues = state.semantic_issues(project)

    assert any(
        "uncompiled current-state prose" in issue
        and "CONTEXT.md" in issue
        and "line(s) 24, 29, 31" in issue
        for issue in issues
    )
    assert any(
        "uncompiled current-state prose" in issue
        and "reference/baselines.md" in issue
        and "line(s) 3" in issue
        for issue in issues
    )


def test_structured_state_allows_explicitly_historical_snapshots(tmp_path: Path) -> None:
    _repo, project = init_repo(tmp_path)
    context = project / "CONTEXT.md"
    context.write_text(
        "# Context\n\n## Handoff history\n\n"
        "Release v0.9.0 was accepted previously.\n"
        "current client-health checks were recorded in that historical snapshot.\n",
        encoding="utf-8",
    )
    reference = project / "reference"
    reference.mkdir()
    (reference / "baselines.md").write_text(
        "# Baselines\n\n## Accepted baselines — through 2026-08-18\n\n"
        "Release v0.9.0.\n",
        encoding="utf-8",
    )
    state.build_operational_state(
        project,
        project_id="alpha",
        phase="release 1.0.0",
        status="active",
        controlling_plan="resources/artifacts/plan.md",
        accepted_baseline="1.0.0",
        next_actions=["finish"],
        last_session="2026-09-03",
        session_id="018f0000-0000-7000-8000-000000000001",
    )

    assert not any(
        "uncompiled current-state prose" in issue
        for issue in state.semantic_issues(project)
    )


def test_checkpoint_requires_context_refresh_after_source_head_changes(tmp_path: Path) -> None:
    repo, project = init_repo(tmp_path)
    claims = board(tmp_path / "board.md", [("018f0000-0000-7000-8000-000000000001", "s-abcd-efgh-jkmn", "alpha", str(repo))])
    receipt_root = tmp_path / "receipts"
    source = tmp_path / "source"
    source.mkdir()
    run("git", "init", "-b", "main", cwd=source)
    run("git", "config", "user.email", "fixture@example.invalid", cwd=source)
    run("git", "config", "user.name", "Fixture", cwd=source)
    run("git", "config", "core.hooksPath", str(tmp_path / "fixture-hooks"), cwd=source)
    (source / "code.txt").write_text("one\n", encoding="utf-8")
    run("git", "add", "code.txt", cwd=source)
    run("git", "commit", "-m", "source one", cwd=source)
    head = run("git", "rev-parse", "HEAD", cwd=source)
    state.build_operational_state(project, project_id="alpha", phase="release 1.0.0", status="active", controlling_plan="resources/artifacts/plan.md", accepted_baseline="1.0.0", next_actions=["finish"], last_session="2026-09-03", session_id="018f0000-0000-7000-8000-000000000001", source_heads={str(source): head})
    state.checkpoint_project(project, session_id="018f0000-0000-7000-8000-000000000001", coordination_board=claims, receipt_root=receipt_root, source_heads={str(source): head})
    (source / "code.txt").write_text("two\n", encoding="utf-8")
    run("git", "add", "code.txt", cwd=source)
    run("git", "commit", "-m", "source two", cwd=source)
    newer = run("git", "rev-parse", "HEAD", cwd=source)
    verdict, issues = state.validate_checkpoint(project, session_id="018f0000-0000-7000-8000-000000000001", coordination_board=claims, receipt_root=receipt_root, source_heads={str(source): newer})
    assert verdict == "FAIL"
    assert any("source" in issue.lower() for issue in issues)


def test_operational_state_compiles_and_validates_bounded_context(tmp_path: Path) -> None:
    _repo, project = init_repo(tmp_path)
    payload = state.build_operational_state(
        project,
        project_id="alpha",
        phase="release 1.0.0",
        status="active",
        controlling_plan="resources/artifacts/plan.md",
        accepted_baseline="1.0.0",
        next_actions=["finish"],
        last_session="2026-09-03",
        session_id="018f0000-0000-7000-8000-000000000001",
    )
    context = (project / "CONTEXT.md").read_text(encoding="utf-8")
    assert context.count("<!-- synthesis-current-state:start -->") == 1
    assert "**Phase:** release 1.0.0" in context
    assert not state.semantic_issues(project)
    (project / "CONTEXT.md").write_text(
        context.replace("**Phase:** release 1.0.0", "**Phase:** release 0.9.0", 1),
        encoding="utf-8",
    )
    assert any("compiled" in issue for issue in state.semantic_issues(project))
    assert any("changed after" in issue for issue in state.semantic_issues(project))
    assert payload["content_hashes"]["CONTEXT.md"] != sha(project / "CONTEXT.md")


def test_semantic_state_detects_stale_hashed_reference(tmp_path: Path) -> None:
    _repo, project = init_repo(tmp_path)
    state.build_operational_state(
        project,
        project_id="alpha",
        phase="release 1.0.0",
        status="active",
        controlling_plan="resources/artifacts/plan.md",
        accepted_baseline="1.0.0",
        next_actions=["finish"],
        last_session="2026-09-03",
        session_id="018f0000-0000-7000-8000-000000000001",
    )
    (project / "REFERENCE.md").write_text("# Reference\n\nchanged\n", encoding="utf-8")
    assert any("changed after" in issue for issue in state.semantic_issues(project))


@pytest.mark.parametrize("writer,receiver", [("adapter-a", "adapter-b"), ("adapter-b", "adapter-a")])
def test_handoff_directions_share_one_receipt_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    writer: str,
    receiver: str,
) -> None:
    repo, project = init_repo(tmp_path)
    session = "018f0000-0000-7000-8000-000000000001"
    claims = board(tmp_path / "board.md", [(session, "s-abcd-efgh-jkmn", "alpha", str(repo))])
    receipt_root = tmp_path / "receipts"
    state.build_operational_state(project, project_id="alpha", phase="release 1.0.0", status="active", controlling_plan="resources/artifacts/plan.md", accepted_baseline="1.0.0", next_actions=["finish"], last_session="2026-09-03", session_id=session)
    monkeypatch.setenv("SYNTHESIS_LIFECYCLE_ADAPTER", writer)
    receipt = state.checkpoint_project(project, session_id=session, coordination_board=claims, receipt_root=receipt_root)
    assert receipt["writer_adapter"] == writer
    monkeypatch.setenv("SYNTHESIS_LIFECYCLE_ADAPTER", receiver)
    verdict, issues = state.validate_checkpoint(project, session_id=session, coordination_board=claims, receipt_root=receipt_root)
    assert (verdict, issues) == ("PASS", [])


def test_clean_stop_passes_and_interrupted_stop_is_recoverable_not_clean(tmp_path: Path) -> None:
    repo, project = init_repo(tmp_path)
    session = "018f0000-0000-7000-8000-000000000001"
    claims = board(tmp_path / "board.md", [(session, "s-abcd-efgh-jkmn", "alpha", str(repo))])
    receipts = tmp_path / "receipts"
    state.build_operational_state(project, project_id="alpha", phase="release 1.0.0", status="active", controlling_plan="resources/artifacts/plan.md", accepted_baseline="1.0.0", next_actions=["finish"], last_session="2026-09-03", session_id=session)
    state.checkpoint_project(project, session_id=session, coordination_board=claims, receipt_root=receipts)
    assert state.validate_checkpoint(project, session_id=session, coordination_board=claims, receipt_root=receipts)[0] == "PASS"
    (project / "REFERENCE.md").write_text("interrupted\n", encoding="utf-8")
    assert state.validate_checkpoint(project, session_id=session, coordination_board=claims, receipt_root=receipts)[0] == "LOCAL_RECOVERABLE"


def test_unrelated_dirty_and_staged_files_survive_recovery(tmp_path: Path) -> None:
    repo, _project = init_repo(tmp_path)
    (repo / "unrelated.txt").write_text("staged\n", encoding="utf-8")
    run("git", "add", "unrelated.txt", cwd=repo)
    (repo / "other.local").write_text("dirty\n", encoding="utf-8")
    before = run("git", "status", "--porcelain=v1", cwd=repo)
    state.resolve_project("alpha", repo / "projects" / "index.yaml", fetch=False, fast_forward_canonical=True)
    assert run("git", "status", "--porcelain=v1", cwd=repo) == before


def test_unrelated_project_session_does_not_block_checkpoint(tmp_path: Path) -> None:
    repo, project = init_repo(tmp_path)
    session = "018f0000-0000-7000-8000-000000000001"
    claims = board(tmp_path / "board.md", [(session, "s-abcd-efgh-jkmn", "alpha", str(repo)), ("018f0000-0000-7000-8000-000000000002", "s-npqr-stuv-wxyz", "beta", str(tmp_path / "elsewhere"))])
    state.build_operational_state(project, project_id="alpha", phase="release 1.0.0", status="active", controlling_plan="resources/artifacts/plan.md", accepted_baseline="1.0.0", next_actions=["finish"], last_session="2026-09-03", session_id=session)
    receipt = state.checkpoint_project(project, session_id=session, coordination_board=claims, receipt_root=tmp_path / "receipts")
    assert receipt["session_id"] == session


def test_unreachable_remote_is_unknown_not_green(tmp_path: Path) -> None:
    repo, _project = init_repo(tmp_path)
    run("git", "remote", "set-url", "origin", str(tmp_path / "missing.git"), cwd=repo)
    report = state.resolve_project("alpha", repo / "projects" / "index.yaml", fetch=True)
    assert report.status == "UNKNOWN"
    assert any("fetch" in issue.lower() for issue in report.issues)


def test_unreachable_coordination_lease_is_unknown_not_green(tmp_path: Path) -> None:
    from coordination_schema import identity_from_uuid

    repo, _project = init_repo(tmp_path)
    identity = identity_from_uuid("018f0000-0000-7000-8000-000000000001")
    claims = board(
        tmp_path / "board.md",
        [(identity.session_uuid, identity.compact_id, "alpha", str(repo))],
    )
    claims.write_text(claims.read_text(encoding="utf-8").replace("words-1", identity.speakable_id), encoding="utf-8")
    # This is a remote failure test, not a rejection of a valid local board.
    (claims.parent / "lease.json").write_text(json.dumps({"remote": str(tmp_path / "missing-lease.git")}))
    report = state.resolve_project(
        "alpha",
        repo / "projects" / "index.yaml",
        coordination_board=claims,
        fetch=False,
        refresh_coordination=True,
    )
    assert report.status == "UNKNOWN"
    assert any("lease refresh" in issue.lower() for issue in report.issues)


def test_installed_newer_than_loaded_registry_is_a_live_plane_failure(tmp_path: Path) -> None:
    repo, _project = init_repo(tmp_path)
    report = state.resolve_project("alpha", repo / "projects" / "index.yaml", fetch=False)
    report.planes.update({"source": "PASS", "installed": "PASS", "live": "FAIL"})
    assert report.selected_path is not None
    assert report.planes == {"source": "PASS", "installed": "PASS", "live": "FAIL", "continuity": "PASS"}


@pytest.mark.parametrize("change", ["edit", "delete"])
def test_cross_project_plan_change_invalidates_clean_checkpoint(tmp_path: Path, change: str) -> None:
    repo, project = init_repo(tmp_path)
    plan = repo / "projects" / "program" / "resources" / "artifacts" / "work-plan.md"
    plan.parent.mkdir(parents=True)
    plan.write_text("# Parent plan\n", encoding="utf-8")
    session = "018f0000-0000-7000-8000-000000000001"
    claims = board(tmp_path / "board.md", [(session, "s-abcd-efgh-jkmn", "alpha", str(repo))])
    receipts = tmp_path / "receipts"
    state.build_operational_state(
        project, project_id="alpha", phase="release 1.0.0", status="active",
        controlling_plan="../program/resources/artifacts/work-plan.md", accepted_baseline="1.0.0",
        next_actions=["finish"], last_session="2026-09-03", session_id=session,
    )
    state.checkpoint_project(project, session_id=session, coordination_board=claims, receipt_root=receipts)
    assert state.validate_checkpoint(project, session_id=session, coordination_board=claims, receipt_root=receipts) == ("PASS", [])
    if change == "edit":
        plan.write_text("# Changed parent plan\n", encoding="utf-8")
    else:
        plan.unlink()
    verdict, issues = state.validate_checkpoint(project, session_id=session, coordination_board=claims, receipt_root=receipts)
    assert verdict == "LOCAL_RECOVERABLE"
    assert any("plan" in issue or "durable project files" in issue for issue in issues)


@pytest.mark.parametrize("client", ["cc", "codex"])
def test_lifecycle_hook_issues_session_bound_clean_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, client: str
) -> None:
    repo, project = init_repo(tmp_path)
    session = "018f0000-0000-7000-8000-000000000001"
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", f"{client}:{session}")
    claims = board(tmp_path / "board.md", [(session, "s-abcd-efgh-jkmn", "alpha", str(repo))])
    claims.write_text(claims.read_text().replace(f"tool:{session}", f"{client}:{session}"))
    receipts = tmp_path / "receipts"
    payload = native_hook_fixture(tmp_path, monkeypatch, client, session, repo)
    state.build_operational_state(
        project,
        project_id="alpha",
        phase="release 1.0.0",
        status="active",
        controlling_plan="resources/artifacts/plan.md",
        accepted_baseline="1.0.0",
        next_actions=["finish"],
        last_session="2026-09-03",
        session_id=session,
    )
    verdict, issues = state.checkpoint_hook(
        payload,
        coordination_board=claims,
        receipt_root=receipts,
        refresh_coordination=False,
    )
    assert (verdict, issues) == ("PASS", [])
    receipt = json.loads(next(receipts.glob("*.json")).read_text(encoding="utf-8"))
    assert receipt["session_id"] == session
    assert receipt["project_id"] == "alpha"


@pytest.mark.parametrize("client", ["cc", "codex"])
def test_lifecycle_hook_refuses_semantically_incomplete_stop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, client: str
) -> None:
    repo, project = init_repo(tmp_path)
    session = "018f0000-0000-7000-8000-000000000001"
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", f"{client}:{session}")
    claims = board(tmp_path / "board.md", [(session, "s-abcd-efgh-jkmn", "alpha", str(repo))])
    claims.write_text(claims.read_text().replace(f"tool:{session}", f"{client}:{session}"))
    payload = native_hook_fixture(tmp_path, monkeypatch, client, session, repo)
    state.build_operational_state(
        project,
        project_id="alpha",
        phase="release 1.0.0",
        status="active",
        controlling_plan="resources/artifacts/plan.md",
        accepted_baseline="1.0.0",
        next_actions=["finish"],
        last_session="2026-09-03",
        session_id=session,
    )
    (project / "CONTEXT.md").write_text("# stale after work\n", encoding="utf-8")
    verdict, issues = state.checkpoint_hook(
        payload,
        coordination_board=claims,
        receipt_root=tmp_path / "receipts",
        refresh_coordination=False,
    )
    assert verdict == "FAIL"
    assert any("changed" in issue for issue in issues)


def native_hook_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, client: str, native: str, cwd: Path) -> dict:
    if client == "cc":
        root = tmp_path / ".claude"
        transcript = root / "projects" / "fixture" / f"{native}.jsonl"
        record = {"type": "user", "sessionId": native}
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(root))
    else:
        root = tmp_path / ".codex"
        transcript = root / "sessions" / "fixture.jsonl"
        record = {"type": "session_meta", "payload": {"id": native}}
        monkeypatch.setenv("CODEX_HOME", str(root))
    transcript.parent.mkdir(parents=True)
    transcript.write_text(json.dumps(record) + "\n")
    return {"session_id": native, "cwd": str(cwd), "transcript_path": str(transcript)}


def test_lifecycle_hook_fails_closed_when_lease_cannot_refresh(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _project = init_repo(tmp_path)
    session = "018f0000-0000-7000-8000-000000000001"
    claims = board(
        tmp_path / "board.md",
        [(session, "s-abcd-efgh-jkmn", "alpha", str(repo))],
    )
    monkeypatch.setattr(
        state,
        "_refresh_coordination_board",
        lambda _path, **_kw: "coordination lease refresh failed: fixture outage",
    )
    verdict, issues = state.checkpoint_hook(
        {"session_id": session, "cwd": str(repo)},
        coordination_board=claims,
        receipt_root=tmp_path / "receipts",
    )
    assert verdict == "FAIL"
    assert issues == ["coordination lease refresh failed: fixture outage"]


def test_project_state_reliability_release_contract_is_coherent() -> None:
    root = Path(__file__).resolve().parents[3]
    versions = {
        json.loads((root / path).read_text(encoding="utf-8"))["version"]
        for path in (".claude-plugin/plugin.json", ".codex-plugin/plugin.json")
    }
    assert len(versions) == 1
    version = versions.pop()
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    newest = next(line for line in changelog.splitlines() if line.startswith("## ["))
    assert newest.startswith(f"## [{version}] - ")
    assert f"Release **{version}**" in (root / "README.md").read_text(encoding="utf-8")
    hooks = json.loads((root / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    commands = [
        hook["command"]
        for group in hooks["hooks"]["Stop"]
        for hook in group["hooks"]
    ]
    assert any(command.endswith("project_state.py hook") for command in commands)
    # The reliability tranche shipped these skills at these versions; later
    # releases may bump any of them, so the contract is a floor, never a
    # literal to re-pin by hand (a hand-pinned literal broke the first
    # release after this test was written).
    floors = {
        "synthesis-project-management": (2, 12, 0),
        "synthesis-context-lifecycle": (1, 18, 0),
        "synthesis-agent-conformance": (1, 9, 1),
        "synthesis-autopilot": (2, 1, 0),
        "synthesis-repo-guard": (2, 4, 0),
    }
    for skill, floor in floors.items():
        text = (root / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
        match = re.search(r'^\s*version:\s*"(\d+)\.(\d+)\.(\d+)"\s*$', text, re.M)
        assert match, f"{skill} declares no semantic version"
        declared = tuple(int(part) for part in match.groups())
        assert declared >= floor, f"{skill} {declared} is below the reliability floor {floor}"


def test_observer_stop_resolves_muse_session_from_store_without_transcript_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_id = "019fff79-5858-7993-a329-b301bccf5d01"
    log = (
        tmp_path / "muse-sessions" / "2026" / "09" / "17"
        / session_id / "session.jsonl"
    )
    log.parent.mkdir(parents=True)
    log.write_text(
        json.dumps({"stream": {"kind": "session", "id": session_id}}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("MUSE_SESSIONS_DIR", str(tmp_path / "muse-sessions"))
    assert state._observer_native_identity({"session_id": session_id}) == (
        "muse",
        session_id,
    )
    with pytest.raises(state.ProjectStateError, match="transcript path"):
        state._observer_native_identity(
            {"session_id": "019fff79-5858-7993-a329-b301bccf5d02"}
        )


def _stop_args(board: Path, **values):
    return type("Args", (), {"board": board, **values})()


def test_stop_honors_open_release_requests(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # S13 layer 2: the Stop hook answers open requests best-effort; the
    # reply blocks on the bus are the record.
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    board = tmp_path / "board.md"
    area = f"{repo}/claimed/**"
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", "codex:holder-x")
    assert engine.command_claim(_stop_args(
        board, id=None, agent="agent", machine="m1", project="project-h",
        mode="interactive", goal="g", workspace=[f"{repo} @ main"],
        area=[area], context_role="owner",
    )) == 0
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", "codex:requester-x")
    assert engine.command_claim(_stop_args(
        board, id=None, agent="agent", machine="m1", project="project-q",
        mode="interactive", goal="g", workspace=["/tmp/repo-q @ main"],
        area=["elsewhere/**"], context_role="owner",
    )) == 0
    holder = [row for row in engine.rows(board.read_text(encoding="utf-8")) if row.project == "project-h"][0]
    assert engine.command_request_narrow(_stop_args(
        board, holder=holder.compact_id, area=[area], reason="need it",
    )) == 0
    [req] = engine.open_release_requests(board.read_text(encoding="utf-8"))
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", "codex:holder-x")
    state._honor_release_requests_at_stop(
        board, {"session uuid": holder.session_uuid},
        {"hook_event_name": "Stop", "cwd": str(repo)},
    )
    assert engine.parse_release_replies(board.read_text(encoding="utf-8")) == {req.id: "narrowed"}
    # A row without identity never crashes the hook.
    state._honor_release_requests_at_stop(board, {}, {"hook_event_name": "Stop"})


def _claim_row(project, areas="", workspaces="", session="s-test"):
    return {
        "project": project,
        "claimed areas (advisory lock)": areas,
        "workspace(s) / branch": workspaces,
        "session uuid": session,
    }


def test_project_from_claim_ignores_phantom_registry_dirs(tmp_path, monkeypatch):
    """Intake 31: a claimed root whose projects/ merely carries an index.yaml
    must not manufacture a candidate that collides with the real dir."""
    knowledge = tmp_path / "knowledge"
    (knowledge / "projects").mkdir(parents=True)
    (knowledge / "projects" / "index.yaml").write_text("csa-x:\n  status: active\n")
    real = tmp_path / "real" / "projects" / "csa-x"
    real.mkdir(parents=True)
    seen = []
    monkeypatch.setattr(
        state, "checkpoint_applicability",
        lambda project: seen.append(Path(project)) or ("APPLICABLE", []),
    )
    row = _claim_row("csa-x", areas=f"{knowledge} @ main",
                     workspaces=f"{real} @ main")
    assert state._project_from_claim(row) == real.resolve()
    assert seen == [real.resolve()]


def test_project_from_claim_error_names_candidates(tmp_path):
    first = tmp_path / "a" / "projects" / "proj"
    second = tmp_path / "b" / "projects" / "proj"
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    row = _claim_row("proj", areas=f"{first},{second}")
    with pytest.raises(state.ProjectStateError) as exc:
        state._project_from_claim(row)
    assert str(first.resolve()) in str(exc.value)
    assert str(second.resolve()) in str(exc.value)


def test_project_from_claim_explicit_phantom_keeps_old_admission(tmp_path, monkeypatch):
    """An explicitly claimed .../projects/<id> that does not exist yet keeps
    the old admission (intake flow claims before first write)."""
    ghost = tmp_path / "repo" / "projects" / "newbie"
    (tmp_path / "repo" / "projects").mkdir(parents=True)
    seen = []
    monkeypatch.setattr(
        state, "checkpoint_applicability",
        lambda project: seen.append(Path(project)) or ("APPLICABLE", []),
    )
    row = _claim_row("newbie", areas=str(ghost))
    assert state._project_from_claim(row) == ghost.resolve()
    assert seen == [ghost.resolve()]


def test_project_from_claim_without_projects_returns_none(tmp_path):
    bare = tmp_path / "bare"
    bare.mkdir()
    row = _claim_row("proj", areas=str(bare))
    assert state._project_from_claim(row) is None


@pytest.mark.parametrize("passive", [False, True])
def test_local_only_board_refresh_uses_existing_coordination_authority(tmp_path, passive):
    claims = tmp_path / "coordination" / "active-sessions.md"
    claims.parent.mkdir()
    claims.write_text(engine.template())
    assert engine.require_fresh_board(claims) == {"configured": False}
    assert state._refresh_coordination_board(claims, passive_stop=passive) is None


def test_hook_default_honors_explicit_board_environment(tmp_path, monkeypatch):
    claims = tmp_path / "isolated" / "board.md"
    monkeypatch.setenv("SYNTHESIS_COORDINATION_BOARD", str(claims))
    assert state._parser().parse_args(["hook"]).coordination_board == claims
    explicit = tmp_path / "explicit.md"
    assert state._parser().parse_args(["hook", "--coordination-board", str(explicit)]).coordination_board == explicit


@pytest.mark.parametrize("lease", [
    {"configured": True, "refreshed": False},
    {"configured": True, "error": "offline"},
    {"configured": True, "cache_hit": True, "age_seconds": 300},
    {"configured": False, "error": "unreadable"},
    {},
])
def test_board_refresh_still_rejects_unproven_or_failed_authority(tmp_path, monkeypatch, lease):
    monkeypatch.setattr(state.subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess(
        args[0], 0, json.dumps({"lease": lease, "problems": []}), ""))
    assert state._refresh_coordination_board(tmp_path / "board.md", passive_stop=True) is not None


def working_digest_fixture(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    deep = "/".join(["deep"] + [f"level-{i:02}" for i in range(24)] + ["雪.txt"])
    contents = {
        ".gitignore": b"ignored/\n",
        ".hidden": b"hidden\x00bytes",
        "a/child.txt": b"child",
        "a.txt": b"sibling with a shared prefix",
        deep: "deep Unicode content: café\n".encode(),
        "ignored/output.bin": bytes(range(256)),
        "nested/.pytest_cache/state.json": b'{"cached":true}',
        "z-last.md": b"last\n",
    }
    for name, content in contents.items():
        path = project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    for name in (".git/HEAD", "nested/.git/objects/ignored"):
        path = project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"Git metadata is excluded")
    external = tmp_path / "outside.txt"
    external.write_bytes(b"external file target")
    external_dir = tmp_path / "outside-directory"
    external_dir.mkdir()
    (external_dir / "not-traversed.txt").write_bytes(b"directory link is not traversed")
    (project / "link-internal").symlink_to("z-last.md")
    (project / "link-external").symlink_to(external)
    (project / "link-directory").symlink_to(external_dir, target_is_directory=True)
    (project / "link-missing").symlink_to(tmp_path / "missing-target")
    contents["link-internal"] = contents["z-last.md"]
    contents["link-external"] = external.read_bytes()
    # Path ordering compares path components, so a/child precedes a.txt.
    order = [".gitignore", ".hidden", "a/child.txt", "a.txt", deep,
             "ignored/output.bin", "link-external", "link-internal",
             "nested/.pytest_cache/state.json", "z-last.md"]
    return project, contents, order


def expected_working_digest(contents, order):
    entries = [(name, hashlib.sha256(contents[name]).hexdigest()) for name in order]
    return hashlib.sha256(json.dumps(entries, separators=(",", ":")).encode()).hexdigest()


@pytest.mark.parametrize("root_form", ["absolute", "relative", "current", "symlink"])
def test_working_digest_preserves_complete_coverage_and_order(tmp_path, monkeypatch, root_form):
    project, contents, order = working_digest_fixture(tmp_path)
    if root_form == "relative":
        monkeypatch.chdir(tmp_path)
        project = Path("project")
    elif root_form == "current":
        monkeypatch.chdir(project)
        project = Path(".")
    elif root_form == "symlink":
        alias = tmp_path / "project-alias"
        alias.symlink_to(project, target_is_directory=True)
        project = alias
    observed = []
    original = state._sha_file
    monkeypatch.setattr(state, "_sha_file", lambda path: observed.append(path) or original(path))
    assert state._working_digest(project) == expected_working_digest(contents, order)
    assert observed == [project / name for name in order]


@pytest.mark.parametrize("change", ["changed", "new", "deleted", "symlink-target"])
def test_working_digest_recomputes_changed_new_deleted_and_linked_content(tmp_path, change):
    project, contents, order = working_digest_fixture(tmp_path)
    before = state._working_digest(project)
    assert before == expected_working_digest(contents, order)
    if change == "changed":
        contents["a.txt"] = b"changed bytes"
        (project / "a.txt").write_bytes(contents["a.txt"])
    elif change == "new":
        contents["new-untracked.txt"] = b"new untracked bytes"
        (project / "new-untracked.txt").write_bytes(contents["new-untracked.txt"])
        order.insert(order.index("z-last.md"), "new-untracked.txt")
    elif change == "deleted":
        (project / "a.txt").unlink()
        del contents["a.txt"]
        order.remove("a.txt")
    else:
        contents["link-external"] = b"changed external file target"
        (tmp_path / "outside.txt").write_bytes(contents["link-external"])
    after = state._working_digest(project)
    assert after == expected_working_digest(contents, order)
    assert after != before


def test_working_digest_rereads_every_included_file_independently(tmp_path, monkeypatch):
    project, contents, order = working_digest_fixture(tmp_path)
    reads = []
    original = state._sha_file
    monkeypatch.setattr(state, "_sha_file", lambda path: reads.append(path) or original(path))
    assert state._working_digest(project) == expected_working_digest(contents, order)
    assert state._working_digest(project) == expected_working_digest(contents, order)
    assert reads == [project / name for name in order] * 2


@pytest.mark.parametrize("depth", [0, 32])
def test_working_digest_avoids_per_file_relative_ancestor_walks(tmp_path, monkeypatch, depth):
    project = tmp_path / "project"
    project.mkdir()
    parent = project.joinpath(*(f"level-{i:02}" for i in range(depth)))
    parent.mkdir(parents=True, exist_ok=True)
    for index in range(8):
        (parent / f"file-{index}.txt").write_bytes(str(index).encode())
    calls = {"relative_to": 0, "parents": 0}
    original_relative = Path.relative_to
    original_parents = Path.parents.fget

    def relative(self, *args, **kwargs):
        calls["relative_to"] += 1
        return original_relative(self, *args, **kwargs)

    def parents(self):
        calls["parents"] += 1
        return original_parents(self)

    with monkeypatch.context() as isolated:
        isolated.setattr(Path, "relative_to", relative)
        isolated.setattr(Path, "parents", property(parents))
        digest = state._working_digest(project)
    assert len(digest) == 64
    assert calls == {"relative_to": 0, "parents": 0}


@pytest.mark.parametrize("root_form", ["absolute", "current"])
def test_working_digest_rejects_non_descendant_from_traversal(tmp_path, monkeypatch, root_form):
    project = tmp_path / "project"
    project.mkdir()
    other = tmp_path / "project-sibling" / "file.txt"
    other.parent.mkdir()
    other.write_bytes(b"must not enter this digest")
    if root_form == "current":
        monkeypatch.chdir(project)
        project = Path(".")
    original = getattr(state, "_project_paths", lambda path, pattern=None: path.rglob(pattern or "*"))

    def traversal(path, pattern=None):
        return iter([other]) if path == project else original(path, pattern)

    monkeypatch.setattr(state, "_project_paths", traversal, raising=False)
    with pytest.raises(ValueError):
        state._working_digest(project)


@pytest.mark.parametrize("root_form", ["absolute", "relative", "current", "symlink"])
@pytest.mark.parametrize("plan", [None, "UPPER.MD", "z-target.md"])
def test_content_hashes_preserve_complete_selection_names_and_reads(tmp_path, monkeypatch, root_form, plan):
    project = tmp_path / "project"
    project.mkdir()
    deep = "/".join(["deep"] + [f"level-{i:02}" for i in range(24)] + ["雪.md"])
    contents = {
        ".hidden.md": b"hidden", ".git/notes.md": b"included Markdown",
        "a/child.md": b"child", "a.md": b"sibling", deep: "café\n".encode(),
        "ignored/note.md": b"ignored by Git only", "z-target.md": b"target",
        "UPPER.MD": b"explicit plan", "other.txt": b"not Markdown",
        ".gitignore": b"ignored/\n",
    }
    for name, content in contents.items():
        path = project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    (project / "a-alias.md").symlink_to("z-target.md")
    (project / "z-alias.md").symlink_to("z-target.md")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "not-traversed.md").write_bytes(b"outside directory")
    (project / "directory.md").symlink_to(outside, target_is_directory=True)
    (project / "broken.md").symlink_to(tmp_path / "missing.md")
    canonical = project.resolve()
    if root_form == "relative":
        monkeypatch.chdir(tmp_path)
        project = Path("project")
    elif root_form == "current":
        monkeypatch.chdir(project)
        project = Path(".")
    elif root_form == "symlink":
        alias = tmp_path / "alias"
        alias.symlink_to(project, target_is_directory=True)
        project = alias
    selected = [name for name in contents if name.endswith(".md")]
    expected = {name: hashlib.sha256(contents[name]).hexdigest() for name in selected}
    if plan:
        expected[plan] = hashlib.sha256(contents[plan]).hexdigest()
    expected = dict(sorted(expected.items()))
    order = sorted(project / name for name in [*selected, "a-alias.md", "z-alias.md"])
    if plan:
        order.append(canonical / plan)
    reads = []
    original = state._sha_file
    monkeypatch.setattr(state, "_sha_file", lambda path: reads.append(path) or original(path))
    assert state._content_hashes(project, plan) == expected
    assert state._content_hashes(project, plan) == expected
    assert reads == order * 2


@pytest.mark.parametrize("change", ["changed", "new", "deleted", "linked-target"])
def test_content_hashes_recompute_each_file_set_and_content(tmp_path, change):
    project = tmp_path / "project"
    project.mkdir()
    target = project / "target.md"
    target.write_bytes(b"original")
    (project / "alias.md").symlink_to("target.md")
    other = project / "other.md"
    other.write_bytes(b"other")
    before = state._content_hashes(project)
    expected = {"other.md": hashlib.sha256(b"other").hexdigest(),
                "target.md": hashlib.sha256(b"original").hexdigest()}
    assert before == expected
    if change == "changed":
        other.write_bytes(b"changed")
        expected["other.md"] = hashlib.sha256(b"changed").hexdigest()
    elif change == "new":
        (project / "new.md").write_bytes(b"new")
        expected["new.md"] = hashlib.sha256(b"new").hexdigest()
    elif change == "deleted":
        other.unlink()
        del expected["other.md"]
    else:
        (project / "alias.md").write_bytes(b"linked change")
        expected["target.md"] = hashlib.sha256(b"linked change").hexdigest()
    assert state._content_hashes(project) == dict(sorted(expected.items()))
    assert expected != before


@pytest.mark.parametrize("plan", [None, "middle.md"])
def test_content_hashes_keep_alias_order_and_final_plan_overwrite(tmp_path, monkeypatch, plan):
    project = tmp_path / "project"
    project.mkdir()
    target = project / "middle.md"
    target.write_bytes(b"revision-0")
    (project / "a-alias.md").symlink_to("middle.md")
    (project / "z-alias.md").symlink_to("middle.md")
    reads = []
    original = state._sha_file

    def changing_file(path):
        digest = original(path)
        reads.append(path.name)
        target.write_bytes(f"revision-{len(reads)}".encode())
        return digest

    monkeypatch.setattr(state, "_sha_file", changing_file)
    expected_order = ["a-alias.md", "middle.md", "z-alias.md"] + (["middle.md"] if plan else [])
    expected = hashlib.sha256(f"revision-{len(expected_order) - 1}".encode()).hexdigest()
    assert state._content_hashes(project, plan) == {"middle.md": expected}
    assert reads == expected_order


@pytest.mark.parametrize("depth", [0, 32])
def test_content_hashes_use_constant_root_resolution_without_ancestor_walks(tmp_path, monkeypatch, depth):
    project = tmp_path / "project"
    parent = project.joinpath(*(f"level-{i:02}" for i in range(depth)))
    parent.mkdir(parents=True)
    files = [parent / f"file-{i}.md" for i in range(8)]
    for path in files:
        path.write_bytes(path.name.encode())
    resolves, reads = [], []
    walks = {"relative_to": 0, "parents": 0}
    original_resolve, original_relative = Path.resolve, Path.relative_to
    original_parents, original_hash = Path.parents.fget, state._sha_file

    def resolve(path, *args, **kwargs):
        resolves.append(path)
        return original_resolve(path, *args, **kwargs)

    def relative(path, *args, **kwargs):
        walks["relative_to"] += 1
        return original_relative(path, *args, **kwargs)

    def parents(path):
        walks["parents"] += 1
        return original_parents(path)

    monkeypatch.setattr(Path, "resolve", resolve)
    monkeypatch.setattr(Path, "relative_to", relative)
    monkeypatch.setattr(Path, "parents", property(parents))
    monkeypatch.setattr(state, "_sha_file", lambda path: reads.append(path) or original_hash(path))
    result = state._content_hashes(project)
    assert len(result) == 8
    assert reads == sorted(files)
    assert [path for path in resolves if path != project] == sorted(files)
    assert resolves.count(project) == 2
    assert walks == {"relative_to": 0, "parents": 0}


def test_content_hashes_reject_outside_resolved_target_before_read(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    outside = tmp_path / "project-sibling" / "outside.md"
    outside.parent.mkdir()
    outside.write_bytes(b"must not be read")
    (project / "outside.md").symlink_to(outside)
    reads = []
    monkeypatch.setattr(state, "_sha_file", lambda path: reads.append(path) or "unexpected")
    with pytest.raises(ValueError):
        state._content_hashes(project)
    assert reads == []


@pytest.mark.parametrize("phase", ["markdown", "plan", "empty"])
def test_content_hashes_reject_root_retarget_after_last_read(tmp_path, monkeypatch, phase):
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    project = tmp_path / "project"
    project.symlink_to(first, target_is_directory=True)
    plan = "UPPER.MD" if phase == "plan" else None
    if phase != "empty":
        (first / (plan or "note.md")).write_bytes(b"first root")
    original_hash = state._sha_file
    original_paths = getattr(state, "_project_paths", lambda path, pattern=None: path.rglob(pattern or "*"))

    def retarget():
        project.unlink()
        project.symlink_to(second, target_is_directory=True)

    def hash_then_retarget(path):
        digest = original_hash(path)
        retarget()
        return digest

    def empty_then_retarget(path, pattern=None):
        yield from original_paths(path, pattern)
        retarget()

    if phase == "empty":
        monkeypatch.setattr(state, "_project_paths", empty_then_retarget, raising=False)
    else:
        monkeypatch.setattr(state, "_sha_file", hash_then_retarget)
    with pytest.raises((ValueError, state.ProjectStateError)):
        state._content_hashes(project, plan)
    assert project.resolve() == second


def traversal_corpus(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    for name in (".md", "line\nbreak.md", "UPPER.MD", ".hidden/note.md",
                 ".git/inside.md", "a/inside.md", "a.md", "folder.md/child.md",
                 "雪.md", "other.bin"):
        path = project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(name.encode())
    (project / "alias.md").symlink_to("a.md")
    (project / "broken.md").symlink_to(tmp_path / "missing.md")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "outside.md").write_bytes(b"unvisited")
    (project / "directory.md").symlink_to(outside, target_is_directory=True)
    (project / "cycle").symlink_to(project, target_is_directory=True)
    return project


@pytest.mark.parametrize("consumer", ["_content_hashes", "_working_digest"])
@pytest.mark.parametrize("root_form", ["absolute", "relative", "current", "symlink"])
def test_hash_traversal_matches_retained_rglob_corpus(tmp_path, monkeypatch, consumer, root_form):
    project = traversal_corpus(tmp_path)
    if root_form == "relative":
        monkeypatch.chdir(tmp_path)
        project = Path("project")
    elif root_form == "current":
        monkeypatch.chdir(project)
        project = Path(".")
    elif root_form == "symlink":
        alias = tmp_path / "root-alias"
        alias.symlink_to(project, target_is_directory=True)
        project = alias
    if consumer == "_content_hashes":
        paths = sorted(set(path for path in project.rglob("*.md") if path.is_file()))
        expected = dict(sorted({str(path.resolve().relative_to(project.resolve())): sha(path)
                                for path in paths}.items()))
        assert ".md" in expected and "line\nbreak.md" in expected
        assert ".git/inside.md" in expected
    else:
        paths = [path for path in sorted(item for item in project.rglob("*") if item.is_file())
                 if ".git" not in path.parts]
        entries = [(str(path.relative_to(project)), sha(path)) for path in paths]
        expected = hashlib.sha256(json.dumps(entries, separators=(",", ":")).encode()).hexdigest()
    reads = []
    original = state._sha_file
    monkeypatch.setattr(state, "_sha_file", lambda path: reads.append(path) or original(path))
    assert getattr(state, consumer)(project) == expected
    assert reads == paths


@pytest.mark.parametrize("consumer", ["_content_hashes", "_working_digest"])
def test_hash_traversal_scans_each_directory_once_per_fresh_pass(tmp_path, monkeypatch, consumer):
    project = traversal_corpus(tmp_path)
    directories = {project, project / ".hidden", project / ".git", project / "a", project / "folder.md"}
    import collections
    scans, active = [], []
    original_scan, original_is_file = state.os.scandir, Path.is_file

    class Scan:
        def __init__(self, path):
            assert not active, "a directory iterator remained open while descending"
            self.path = Path(path)
            self.iterator = original_scan(path)

        def __enter__(self):
            active.append(self.path)
            scans.append(self.path)
            return self.iterator

        def __exit__(self, *args):
            self.iterator.close()
            active.remove(self.path)

    def is_file(path):
        assert not active, "a directory iterator remained open during file selection"
        return original_is_file(path)

    monkeypatch.setattr(state.os, "scandir", Scan)
    monkeypatch.setattr(Path, "is_file", is_file)
    first = getattr(state, consumer)(project)
    assert collections.Counter(scans) == {path: 1 for path in directories}
    assert getattr(state, consumer)(project) == first
    assert collections.Counter(scans) == {path: 2 for path in directories}
    assert not active


@pytest.mark.parametrize("consumer", ["_content_hashes", "_working_digest"])
@pytest.mark.parametrize("failure", ["open", "iterate", "classify", "is_file"])
def test_hash_traversal_does_not_accept_incomplete_io(tmp_path, monkeypatch, consumer, failure):
    project = tmp_path / "project"
    child = project / "child"
    child.mkdir(parents=True)
    leaf = child / "note.md"
    leaf.write_bytes(b"must be accounted for")
    original_scan, original_is_file = state.os.scandir, Path.is_file
    opened, closed = [], []

    class Entry:
        def __init__(self, entry):
            self.entry = entry

        def __getattr__(self, name):
            return getattr(self.entry, name)

        def is_dir(self, *args, **kwargs):
            if failure == "classify" and self.name == "child":
                raise PermissionError("fixture directory classification denied")
            return self.entry.is_dir(*args, **kwargs)

    class Scan:
        def __init__(self, path):
            self.path = Path(path)
            if failure == "open" and self.path == child:
                raise PermissionError("fixture directory open denied")
            self.iterator = original_scan(path)

        def __enter__(self):
            opened.append(self.path)
            return self

        def __iter__(self):
            return self

        def __next__(self):
            entry = next(self.iterator)
            if failure == "iterate" and self.path == child:
                raise PermissionError("fixture directory iteration denied")
            return Entry(entry)

        def __exit__(self, *args):
            self.iterator.close()
            closed.append(self.path)

    def is_file(path):
        if failure == "is_file" and path == leaf:
            raise PermissionError("fixture file stat denied")
        return original_is_file(path)

    monkeypatch.setattr(state.os, "scandir", Scan)
    monkeypatch.setattr(Path, "is_file", is_file)
    with pytest.raises(OSError):
        getattr(state, consumer)(project)
    assert len(opened) == len(closed)


@pytest.mark.parametrize("consumer", ["_content_hashes", "_working_digest"])
def test_hash_traversal_rechecks_file_type_after_enumeration(tmp_path, monkeypatch, consumer):
    project = tmp_path / "project"
    project.mkdir()
    leaf = project / "changed.md"
    leaf.write_bytes(b"was a file")
    original = Path.is_file
    checked, reads = [], []

    def is_file(path):
        if path == leaf and not checked:
            leaf.unlink()
            leaf.mkdir()
            checked.append(path)
        return original(path)

    monkeypatch.setattr(Path, "is_file", is_file)
    monkeypatch.setattr(state, "_sha_file", lambda path: reads.append(path) or "unexpected")
    result = getattr(state, consumer)(project)
    assert result == ({} if consumer == "_content_hashes" else hashlib.sha256(b"[]").hexdigest())
    assert checked == [leaf]
    assert reads == []


@pytest.mark.parametrize("consumer", ["_content_hashes", "_working_digest"])
def test_hash_traversal_rejects_queued_directory_replaced_by_link(tmp_path, monkeypatch, consumer):
    project = tmp_path / "project"
    child = project / "child"
    child.mkdir(parents=True)
    target = tmp_path / "outside"
    target.mkdir()
    (target / "foreign.txt").write_bytes(b"must not be traversed")
    original = state.os.scandir
    changed, scanned = [], []

    class Entry:
        def __init__(self, entry):
            self.entry = entry

        def __getattr__(self, name):
            return getattr(self.entry, name)

        def is_dir(self, *args, **kwargs):
            result = self.entry.is_dir(*args, **kwargs)
            if self.name == "child" and not changed:
                child.rmdir()
                child.symlink_to(target, target_is_directory=True)
                changed.append(child)
            return result

    class Scan:
        def __init__(self, path):
            self.path = Path(path)
            scanned.append(self.path)
            self.iterator = original(path)

        def __enter__(self):
            return self

        def __iter__(self):
            return self

        def __next__(self):
            return Entry(next(self.iterator))

        def __exit__(self, *args):
            self.iterator.close()

    monkeypatch.setattr(state.os, "scandir", Scan)
    with pytest.raises((OSError, state.ProjectStateError)):
        getattr(state, consumer)(project)
    assert changed == [child]
    assert child not in scanned


@pytest.fixture
def native_identity_contract(tmp_path, monkeypatch):
    """Synthetic native stores; no installed hooks or live sessions are used."""
    session = "01990000-0000-7000-8000-000000000111"
    roots = {client: tmp_path / client for client in ("claude", "codex", "muse")}
    for variable, client in (("CLAUDE_CONFIG_DIR", "claude"), ("CODEX_HOME", "codex"), ("MUSE_SESSIONS_DIR", "muse")):
        monkeypatch.setenv(variable, str(roots[client]))
    paths = {
        "claude": roots["claude"] / "projects/synthetic" / f"{session}.jsonl",
        "codex": roots["codex"] / "sessions/synthetic.jsonl",
        "muse": roots["muse"] / "2026/09/25" / session / "session.jsonl",
    }
    headers = {"claude": {"sessionId": session}, "codex": {"type": "session_meta", "payload": {"id": session}}, "muse": {"stream": {"kind": "session", "id": session}}}
    for client, path in paths.items():
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(headers[client]) + "\n")
    return session, roots, paths


@pytest.mark.parametrize("client", ["claude", "codex", "muse"])
def test_native_identity_contract_accepts_each_canonical_explicit_path(native_identity_contract, client):
    session, _, paths = native_identity_contract
    before = paths[client].read_bytes()
    assert state.observer_native_identity({"session_id": session, "transcript_path": str(paths[client])}) == (client, session)
    assert paths[client].read_bytes() == before


@pytest.mark.parametrize("damage", ["relative", "nonstring", "foreign", "missing", "symlink", "parent-symlink", "header", "duplicate"])
def test_native_identity_contract_muse_supplied_path_never_falls_back(native_identity_contract, damage):
    session, roots, paths = native_identity_contract
    path = paths["muse"]
    supplied = str(path)
    if damage == "relative":
        supplied = "session.jsonl"
    elif damage == "nonstring":
        supplied = {"path": str(path)}
    elif damage == "foreign":
        foreign = roots["muse"].parent / "foreign.jsonl"
        foreign.write_bytes(path.read_bytes())
        supplied = str(foreign)
    elif damage == "missing":
        supplied = str(path.parent / "missing.jsonl")
    elif damage == "symlink":
        saved = path.with_suffix(".retained")
        path.rename(saved)
        path.symlink_to(saved)
    elif damage == "parent-symlink":
        parent = path.parent
        saved = parent.with_name("retained")
        parent.rename(saved)
        parent.symlink_to(saved)
    elif damage == "header":
        path.write_text(json.dumps({"stream": {"id": "01990000-0000-7000-8000-000000000222"}}) + "\n")
    else:
        duplicate = roots["muse"] / "2026/09/24" / session / "session.jsonl"
        duplicate.parent.mkdir(parents=True)
        duplicate.write_bytes(path.read_bytes())
    with pytest.raises(state.ProjectStateError):
        state.observer_native_identity(
            {"session_id": session, "transcript_path": supplied}
        )


def test_native_identity_contract_ambiguous_client_roots_refuse(
    native_identity_contract, monkeypatch
):
    session, roots, paths = native_identity_contract
    path = paths["claude"]
    path.write_text(
        json.dumps(
            {"sessionId": session, "type": "session_meta", "payload": {"id": session}}
        )
        + "\n"
    )
    monkeypatch.setenv("CODEX_HOME", str(roots["claude"]))
    with pytest.raises(state.ProjectStateError, match="unambiguously"):
        state.observer_native_identity(
            {"session_id": session, "transcript_path": str(path)}
        )


# Dirty inventory records filesystem entries; it never grants target-read authority.
@pytest.mark.parametrize(
    "kind", ["self-loop", "two-loop", "dangling", "external", "fifo"]
)
def test_dirty_inventory_records_retained_leaf_without_target_read(
    tmp_path, monkeypatch, kind
):
    repo, project = init_repo(tmp_path)
    leaf = project / "retained"
    target = tmp_path / "outside-private"
    target.write_text("must not be read")
    if kind == "fifo":
        leaf.write_text("tracked regular")
        run("git", "add", ".", cwd=repo)
        run("git", "commit", "-m", "Fixture leaf", cwd=repo)
        leaf.unlink()
        os.mkfifo(leaf)
    else:
        leaf.symlink_to(
            {
                "self-loop": "retained",
                "two-loop": "second",
                "dangling": "absent",
                "external": str(target),
            }[kind]
        )
        if kind == "two-loop":
            (project / "second").symlink_to("retained")
    original = Path.read_bytes

    def guarded_read(path):
        assert path != target, "dirty inventory followed external evidence"
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", guarded_read)
    rows = state._dirty_project_files(repo, "projects/alpha")
    row = next(r for r in rows if r["path"] == str(leaf))
    assert row["kind"] == ("fifo" if kind == "fifo" else "symlink")
    assert row["sha256"] != "deleted"
    report = state.resolve_project("alpha", repo / "projects/index.yaml", fetch=False)
    assert report.status == "CONFLICT"
    assert any("exact attributed manifest" in i for i in report.issues)
    assert any(r["path"] == str(leaf) for c in report.candidates for r in c.dirty_files)
    assert target.read_text() == "must not be read"


@pytest.mark.parametrize(
    "name",
    [
        'quote"x.md',
        "new\nline.md",
        "carriage\rreturn.md",
        "literal -> arrow.md",
        "unicode-é.md",
        "back\\slash.md",
    ],
)
def test_dirty_inventory_git_nul_preserves_exact_name_and_digest(tmp_path, name):
    repo, project = init_repo(tmp_path)
    leaf = project / name
    leaf.write_bytes(b"actual content")
    rows = state._dirty_project_files(repo, "projects/alpha")
    assert [(r["path"], r["sha256"]) for r in rows] == [
        (str(leaf), hashlib.sha256(b"actual content").hexdigest())
    ]


@pytest.mark.parametrize("rename_name", ["new\nname.md", "new -> name.md"])
def test_dirty_inventory_rename_retains_both_affected_paths(tmp_path, rename_name):
    repo, project = init_repo(tmp_path)
    old = project / "old\nname.md"
    old.write_text("identity")
    run("git", "add", ".", cwd=repo)
    run("git", "commit", "-m", "Fixture rename input", cwd=repo)
    new = project / rename_name
    run("git", "mv", str(old), str(new), cwd=repo)
    rows = state._dirty_project_files(repo, "projects/alpha")
    by_path = {r["path"]: r for r in rows}
    assert set(by_path) == {str(old), str(new)}
    assert by_path[str(old)]["sha256"] == "deleted"
    assert by_path[str(new)]["sha256"] == hashlib.sha256(b"identity").hexdigest()


def test_dirty_inventory_manifest_attributes_leaf_identity_without_dereference(
    tmp_path,
):
    repo, project = init_repo(tmp_path)
    leaf = project / "retained"
    leaf.symlink_to("retained")
    rows = state._dirty_project_files(repo, "projects/alpha")
    root = tmp_path / "state"
    pending = root / "pending"
    pending.mkdir(parents=True)
    (pending / "own.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "session_id": "own-fixture",
                "paths": [str(leaf)],
                "path_hashes": {r["path"]: r["sha256"] for r in rows},
                "path_kinds": {r["path"]: r["kind"] for r in rows},
            }
        )
    )
    report = state.resolve_project(
        "alpha", repo / "projects/index.yaml", repo_guard_root=root, fetch=False
    )
    assert report.status == "LOCAL_RECOVERABLE"
    assert report.selected_path == str(project)
    assert leaf.is_symlink() and os.readlink(leaf) == "retained"


@pytest.mark.parametrize("name", ["CONTEXT.md", "CURRENT_STATE.json"])
def test_dirty_inventory_retains_control_file_refusal(tmp_path, name):
    repo, project = init_repo(tmp_path)
    leaf = project / name
    if leaf.exists():
        leaf.unlink()
    leaf.symlink_to(tmp_path / "not-selected")
    report = state.resolve_project("alpha", repo / "projects/index.yaml", fetch=False)
    assert report.status == "UNKNOWN" and report.selected_path is None
    assert leaf.is_symlink()


def test_dirty_inventory_refuses_raced_ancestor_without_reading_target(
    tmp_path, monkeypatch
):
    repo, project = init_repo(tmp_path)
    folder = project / "evidence"
    folder.mkdir()
    (folder / "one").write_text("safe")
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "one").write_text("private")
    original = state._run
    changed = []

    def status_then_swap(*args, **kwargs):
        out = original(*args, **kwargs)
        if "status" in args and not changed:
            folder.rename(project / "retained-folder")
            folder.symlink_to(foreign, target_is_directory=True)
            changed.append(True)
        return out

    monkeypatch.setattr(state, "_run", status_then_swap)
    with pytest.raises(state.ProjectStateError):
        state._dirty_project_files(repo, "projects/alpha")
    assert (foreign / "one").read_text() == "private"


@pytest.mark.parametrize(
    "raw",
    [
        b"?? ../escape\0",
        b"?? /outside\0",
        b"?? projects/alpha/no-terminator",
        b"R  projects/alpha/to\0",
        b"XX projects/alpha/x\0",
    ],
)
def test_dirty_inventory_rejects_malformed_porcelain(tmp_path, monkeypatch, raw):
    repo, project = init_repo(tmp_path)

    def malformed(*args, **kwargs):
        return subprocess.CompletedProcess(
            args, 0, raw if kwargs.get("raw_output") else raw.decode(), ""
        )

    monkeypatch.setattr(state, "_run", malformed)
    with pytest.raises(state.ProjectStateError):
        state._dirty_project_files(repo, "projects/alpha")


def test_dirty_inventory_deleted_parent_is_recorded(tmp_path):
    repo, project = init_repo(tmp_path)
    folder = project / "old"
    folder.mkdir()
    leaf = folder / "gone"
    leaf.write_text("tracked")
    run("git", "add", ".", cwd=repo)
    run("git", "commit", "-m", "Fixture removal", cwd=repo)
    leaf.unlink()
    folder.rmdir()
    row = state._dirty_project_files(repo, "projects/alpha")[0]
    assert (
        row["path"] == str(leaf)
        and row["kind"] == "deleted"
        and row["sha256"] == "deleted"
    )


def test_dirty_inventory_recreated_rename_source_is_not_lost(tmp_path):
    repo, project = init_repo(tmp_path)
    old = project / "old"
    old.write_text("tracked")
    run("git", "add", ".", cwd=repo)
    run("git", "commit", "-m", "Fixture rename", cwd=repo)
    new = project / "new"
    run("git", "mv", str(old), str(new), cwd=repo)
    old.write_text("new source content")
    rows = state._dirty_project_files(repo, "projects/alpha")
    by_path = {r["path"]: r for r in rows}
    assert len(rows) == 2 and set(by_path) == {str(old), str(new)}
    assert (
        by_path[str(old)]["sha256"] == hashlib.sha256(b"new source content").hexdigest()
    )


def test_dirty_inventory_undecodable_filename_is_not_rewritten(tmp_path, monkeypatch):
    repo, project = init_repo(tmp_path)
    leaf = project / os.fsdecode(b"raw-\xff-name")
    try:
        leaf.write_bytes(b"bytes")
    except OSError as exc:
        import errno

        if exc.errno != errno.EILSEQ:
            raise
        # APFS forbids this filename. Exercise the lossless Git protocol seam
        # without claiming an impossible physical-file acceptance on this host.
        monkeypatch.setattr(
            state,
            "_run",
            lambda *a, **k: subprocess.CompletedProcess(
                a, 0, b"?? projects/alpha/raw-\xff-name\0", b""
            ),
        )

        def snapshot(path, **_kwargs):
            assert os.fsencode(path.name) == b"raw-\xff-name"
            return {"kind": "file", "sha256": hashlib.sha256(b"bytes").hexdigest()}

        monkeypatch.setattr(state, "_dirty_leaf_snapshot", snapshot)
    row = state._dirty_project_files(repo, "projects/alpha")[0]
    assert os.fsencode(Path(row["path"]).name) == b"raw-\xff-name"
    assert row["sha256"] == hashlib.sha256(b"bytes").hexdigest()


@pytest.mark.parametrize("replacement", ["symlink", "fifo"])
def test_dirty_inventory_raced_regular_leaf_refuses_without_target_read(
    tmp_path, monkeypatch, replacement
):
    repo, project = init_repo(tmp_path)
    leaf = project / "entry"
    leaf.write_text("original")
    foreign = tmp_path / "outside"
    foreign.write_text("private")
    original = state.os.open
    changed = []

    def opening(path, flags, *args, **kwargs):
        if path == "entry" and not changed:
            leaf.unlink()
            if replacement == "symlink":
                leaf.symlink_to(foreign)
            else:
                os.mkfifo(leaf)
            changed.append(True)
        assert path != foreign
        return original(path, flags, *args, **kwargs)

    monkeypatch.setattr(state.os, "open", opening)
    with pytest.raises(state.ProjectStateError):
        state._dirty_project_files(repo, "projects/alpha")
    assert changed and foreign.read_text() == "private"


def test_dirty_inventory_symlink_fingerprint_changes_with_target_not_target_bytes(
    tmp_path,
):
    repo, project = init_repo(tmp_path)
    outside = tmp_path / "outside"
    outside.write_text("first")
    leaf = project / "link"
    leaf.symlink_to(outside)
    first = state._dirty_project_files(repo, "projects/alpha")[0]
    outside.write_text("different bytes")
    second = state._dirty_project_files(repo, "projects/alpha")[0]
    assert first == second
    leaf.unlink()
    leaf.symlink_to("different-target")
    third = state._dirty_project_files(repo, "projects/alpha")[0]
    assert first["sha256"] != third["sha256"] and third["kind"] == "symlink"


def test_dirty_inventory_registry_alias_still_refuses(tmp_path):
    repo, project = init_repo(tmp_path)
    index = repo / "projects/index.yaml"
    saved = tmp_path / "foreign-index"
    saved.write_bytes(index.read_bytes())
    index.unlink()
    index.symlink_to(saved)
    report = state.resolve_project("alpha", index, fetch=False)
    assert report.status == "UNKNOWN" and report.selected_path is None


def test_dirty_inventory_known_fifo_never_opened(tmp_path, monkeypatch):
    repo, project = init_repo(tmp_path)
    leaf = project / "pipe"
    leaf.write_text("tracked")
    run("git", "add", ".", cwd=repo)
    run("git", "commit", "-m", "Fixture pipe", cwd=repo)
    leaf.unlink()
    os.mkfifo(leaf)
    original = state.os.open

    def opening(path, flags, *args, **kwargs):
        assert path != "pipe" and path != leaf
        return original(path, flags, *args, **kwargs)

    monkeypatch.setattr(state.os, "open", opening)
    assert state._dirty_project_files(repo, "projects/alpha")[0]["kind"] == "fifo"


def test_dirty_inventory_preserves_state_size_refusal(tmp_path, monkeypatch):
    repo, project = init_repo(tmp_path)
    monkeypatch.setattr(state, "MAX_STATE_JSON_BYTES", 128)
    (project / state.STATE_FILE).write_bytes(b" " * 129)
    with pytest.raises(state.ProjectStateError, match="128-byte limit"):
        state._dirty_project_files(repo, "projects/alpha")


def test_dirty_inventory_mode_changes_semantics_without_changing_content_hash(tmp_path):
    repo, project = init_repo(tmp_path)
    leaf = project / "entry"
    leaf.write_text("baseline")
    leaf.chmod(0o644)
    run("git", "add", ".", cwd=repo)
    run("git", "commit", "-m", "Fixture mode", cwd=repo)
    leaf.write_text("changed content")
    first = state._dirty_project_files(repo, "projects/alpha")
    leaf.chmod(0o755)
    second = state._dirty_project_files(repo, "projects/alpha")
    assert first != second
    assert (
        first[0]["sha256"]
        == second[0]["sha256"]
        == hashlib.sha256(b"changed content").hexdigest()
    )
    assert first[0]["mode"] == "0644" and second[0]["mode"] == "0755"


def test_dirty_inventory_verified_workspace_alias_attributes_literal_leaf(tmp_path):
    repo, project = init_repo(tmp_path)
    leaf = project / "retained"
    leaf.symlink_to("retained")
    rows = state._dirty_project_files(repo, "projects/alpha")
    alias = tmp_path / "workspace-alias"
    alias.symlink_to(repo, target_is_directory=True)
    alias_leaf = alias / "projects/alpha/retained"
    guard = tmp_path / "guard"
    pending = guard / "pending"
    pending.mkdir(parents=True)
    (pending / "own.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "session_id": "fixture-owner",
                "paths": [str(alias_leaf)],
                "path_hashes": {str(alias_leaf): rows[0]["sha256"]},
                "path_kinds": {str(alias_leaf): rows[0]["kind"]},
            }
        )
    )
    report = state.resolve_project(
        "alpha", repo / "projects/index.yaml", repo_guard_root=guard, fetch=False
    )
    assert report.status == "LOCAL_RECOVERABLE" and report.selected_path == str(project)
    assert leaf.is_symlink() and os.readlink(leaf) == "retained"


def _dirty_directory_fixture(tmp_path):
    repo, project = init_repo(tmp_path)
    nested = project / "retained-repository"
    nested.mkdir()
    run("git", "init", "--initial-branch=main", cwd=nested)
    (nested / "ordinary").write_text("original")
    return repo, project, nested


def test_dirty_directory_real_git_nested_repository_is_semantic(tmp_path):
    repo, project, nested = _dirty_directory_fixture(tmp_path)
    raw = state._run(
        repo,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
        "--",
        "projects/alpha",
        raw_output=True,
    ).stdout
    assert b"?? projects/alpha/retained-repository/\0" in raw
    rows = state._dirty_project_files(repo, "projects/alpha")
    first = next(r for r in rows if r["path"] == str(nested))
    assert first["kind"] == "directory" and first["sha256"] != "deleted"
    (nested / "ordinary").write_text("changed content")
    second = next(
        r
        for r in state._dirty_project_files(repo, "projects/alpha")
        if r["path"] == str(nested)
    )
    assert second["sha256"] != first["sha256"]
    report = state.resolve_project("alpha", repo / "projects/index.yaml", fetch=False)
    assert report.status == "CONFLICT" and report.selected_path is None
    assert any("exact attributed manifest" in i for i in report.issues)


@pytest.mark.parametrize(
    "change", ["content", "mode", "name", "add", "remove", "link", "empty-directory"]
)
def test_dirty_directory_subtree_changes_are_bound(tmp_path, change):
    repo, _, nested = _dirty_directory_fixture(tmp_path)
    first = state._dirty_leaf_snapshot(nested)
    leaf = nested / "ordinary"
    if change == "content":
        leaf.write_text("replacement")
    elif change == "mode":
        leaf.chmod(0o755)
    elif change == "name":
        leaf.rename(nested / 'name\nwith -> quote"')
    elif change == "add":
        (nested / "new").write_text("new")
    elif change == "remove":
        leaf.unlink()
    elif change == "link":
        (nested / "link").symlink_to("unresolved")
    else:
        (nested / "empty").mkdir()
    assert state._dirty_leaf_snapshot(nested)["sha256"] != first["sha256"]


def test_dirty_directory_ordinary_git_directory_notation_is_supported(
    tmp_path, monkeypatch
):
    repo, project = init_repo(tmp_path)
    folder = project / "ordinary-folder"
    folder.mkdir()
    (folder / "inside").write_text("value")
    raw = state._run(
        repo,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=normal",
        "--",
        "projects/alpha",
        raw_output=True,
    ).stdout
    assert raw == b"?? projects/alpha/ordinary-folder/\0"
    original = state._run

    def actual_directory_record(*args, **kwargs):
        if "status" in args:
            return subprocess.CompletedProcess(args, 0, raw, b"")
        return original(*args, **kwargs)

    monkeypatch.setattr(state, "_run", actual_directory_record)
    row = state._dirty_project_files(repo, "projects/alpha")[0]
    assert row["path"] == str(folder) and row["kind"] == "directory"
    assert row["sha256"] == state._dirty_leaf_snapshot(folder)["sha256"]


@pytest.mark.parametrize(
    "record",
    [
        b" M projects/alpha/x/\0",
        b"?? projects/alpha/x//\0",
        b"?? projects/alpha/../x/\0",
    ],
)
def test_dirty_directory_notation_is_not_blanket_path_relaxation(
    tmp_path, monkeypatch, record
):
    repo, project = init_repo(tmp_path)
    (project / "x").mkdir()
    monkeypatch.setattr(
        state, "_run", lambda *a, **k: subprocess.CompletedProcess(a, 0, record, b"")
    )
    with pytest.raises(state.ProjectStateError):
        state._dirty_project_files(repo, "projects/alpha")


def test_dirty_directory_deep_earlier_child_is_rechecked(tmp_path, monkeypatch):
    folder = tmp_path / "tree"
    folder.mkdir()
    first = folder / "a-first"
    first.mkdir()
    deep = first / "content"
    deep.write_text("original")
    (folder / "z-later").write_text("later")
    original = state._dirty_leaf_snapshot
    changed = []

    def after_later(path, **kwargs):
        row = original(path, **kwargs)
        if path.name == "z-later" and not changed:
            deep.write_text("changed after its directory was captured")
            changed.append(True)
        return row

    monkeypatch.setattr(state, "_dirty_leaf_snapshot", after_later)
    with pytest.raises(state.ProjectStateError, match="changed"):
        state._dirty_leaf_snapshot(folder)
    assert changed


@pytest.mark.parametrize("kind", ["self-loop", "external", "fifo", "socket"])
def test_dirty_directory_special_children_never_follow_or_open(
    tmp_path, monkeypatch, kind
):
    import socket

    folder = tmp_path / "tree"
    folder.mkdir()
    leaf = folder / "special"
    outside = tmp_path / "outside"
    outside.write_text("private")
    server = None
    if kind == "self-loop":
        leaf.symlink_to("special")
    elif kind == "external":
        leaf.symlink_to(outside)
    elif kind == "fifo":
        os.mkfifo(leaf)
    else:
        server = socket.socket(socket.AF_UNIX)
        previous = os.open(".", os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.chdir(folder)
            server.bind("special")
        finally:
            os.fchdir(previous)
            os.close(previous)
    opening = state.os.open

    def guarded(path, flags, *args, **kwargs):
        assert path != "special" and path != outside
        return opening(path, flags, *args, **kwargs)

    monkeypatch.setattr(state.os, "open", guarded)
    try:
        before = state._dirty_leaf_snapshot(folder)
        outside.write_text("changed private bytes")
        assert state._dirty_leaf_snapshot(folder) == before
    finally:
        if server is not None:
            server.close()


@pytest.mark.parametrize("limit", ["entries", "bytes", "depth", "time"])
def test_dirty_directory_finite_capacity_refuses(tmp_path, monkeypatch, limit):
    folder = tmp_path / "tree"
    folder.mkdir()
    (folder / "one").write_bytes(b"12345")
    (folder / "two").write_bytes(b"45678")
    nested = folder / "nested"
    nested.mkdir()
    (nested / "deep").write_text("depth")
    if limit == "entries":
        monkeypatch.setattr(state, "MAX_DIRTY_TREE_ENTRIES", 2)
    elif limit == "bytes":
        monkeypatch.setattr(state, "MAX_DIRTY_TREE_BYTES", 4)
    elif limit == "depth":
        monkeypatch.setattr(state, "MAX_DIRTY_TREE_DEPTH", 1)
    else:
        clock = iter(range(1000))
        monkeypatch.setattr(state.time, "monotonic", lambda: next(clock))
        monkeypatch.setattr(state, "MAX_DIRTY_TREE_SECONDS", 0.5)
    with pytest.raises(state.ProjectStateError, match="finite traversal limit"):
        state._dirty_leaf_snapshot(folder)


def test_dirty_directory_entry_enumeration_stops_at_bound(tmp_path, monkeypatch):
    folder = tmp_path / "tree"
    folder.mkdir()
    for i in range(8):
        (folder / str(i)).write_text("v")
    monkeypatch.setattr(state, "MAX_DIRTY_TREE_ENTRIES", 3)
    original = state.os.scandir
    seen = []

    class Entries:
        def __init__(self, fd):
            self.inner = original(fd)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.inner.close()

        def __iter__(self):
            return self

        def __next__(self):
            entry = next(self.inner)
            seen.append(entry.name)
            return entry

    monkeypatch.setattr(state.os, "scandir", Entries)
    with pytest.raises(state.ProjectStateError):
        state._dirty_leaf_snapshot(folder)
    assert len(seen) == 3  # Root consumes one, then first excessive child refuses.


def test_dirty_directory_roots_share_one_capacity(tmp_path, monkeypatch):
    repo, project = init_repo(tmp_path)
    for name in ("first", "second"):
        folder = project / name
        folder.mkdir()
        (folder / "leaf").write_text("value")
    original = state._run

    def directory_records(*a, **k):
        if "status" in a:
            return subprocess.CompletedProcess(
                a, 0, b"?? projects/alpha/first/\0?? projects/alpha/second/\0", b""
            )
        return original(*a, **k)

    monkeypatch.setattr(state, "_run", directory_records)
    monkeypatch.setattr(state, "MAX_DIRTY_TREE_ENTRIES", 3)
    with pytest.raises(state.ProjectStateError, match="finite traversal limit"):
        state._dirty_project_files(repo, "projects/alpha")


def test_dirty_directory_descendant_only_claim_does_not_authorize_aggregate(tmp_path):
    repo, _, nested = _dirty_directory_fixture(tmp_path)
    rows = state._dirty_project_files(repo, "projects/alpha")
    only = nested / "ordinary"
    manifest = {
        "_kind": "manifest",
        "_path": "synthetic",
        "session_id": "synthetic",
        "paths": [str(only)],
        "path_hashes": {str(only): hashlib.sha256(only.read_bytes()).hexdigest()},
    }
    assert state._manifest_for_dirty(rows, [manifest]) is None
    manifest["paths"] = [str(nested)]
    manifest["path_hashes"] = {row["path"]: row["sha256"] for row in rows}
    manifest["path_kinds"] = {row["path"]: row["kind"] for row in rows}
    assert state._manifest_for_dirty(rows, [manifest]) == "synthetic"


def test_dirty_directory_clock_does_not_charge_unrelated_regular_inventory(
    tmp_path, monkeypatch
):
    repo, project = init_repo(tmp_path)
    for name in ("a-dir", "z-dir"):
        folder = project / name
        folder.mkdir()
        (folder / "leaf").write_text("value")
    (project / "ordinary").write_text("ordinary file")
    now = [0.0]
    monkeypatch.setattr(state.time, "monotonic", lambda: now[0])
    original = state._run

    def records(*a, **k):
        if "status" in a:
            return subprocess.CompletedProcess(
                a,
                0,
                b"?? projects/alpha/a-dir/\0?? projects/alpha/ordinary\0?? projects/alpha/z-dir/\0",
                b"",
            )
        return original(*a, **k)

    monkeypatch.setattr(state, "_run", records)
    snapshot = state._dirty_leaf_snapshot

    def regular_delay(path, **kwargs):
        if path.name == "ordinary":
            now[0] += state.MAX_DIRTY_TREE_SECONDS + 1
        return snapshot(path, **kwargs)

    monkeypatch.setattr(state, "_dirty_leaf_snapshot", regular_delay)
    rows = state._dirty_project_files(repo, "projects/alpha")
    assert len(rows) == 3 and [r["kind"] for r in rows].count("directory") == 2


def test_dirty_directory_retarget_during_enumeration_refuses(tmp_path, monkeypatch):
    folder = tmp_path / "tree"
    folder.mkdir()
    (folder / "entry").write_text("original")
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "entry").write_text("private")
    original = state.os.scandir
    changed = []

    def swap(fd):
        if not changed:
            folder.rename(tmp_path / "retained-tree")
            folder.symlink_to(foreign)
            changed.append(True)
        return original(fd)

    monkeypatch.setattr(state.os, "scandir", swap)
    with pytest.raises(state.ProjectStateError):
        state._dirty_leaf_snapshot(folder)
    assert changed and (foreign / "entry").read_text() == "private"


def test_dirty_directory_forged_regular_record_refuses_before_open(
    tmp_path, monkeypatch
):
    repo, project = init_repo(tmp_path)
    leaf = project / "regular"
    leaf.write_text("data")
    monkeypatch.setattr(
        state,
        "_run",
        lambda *a, **k: subprocess.CompletedProcess(
            a, 0, b"?? projects/alpha/regular/\0", b""
        ),
    )
    original = state.os.open

    def opening(path, flags, *a, **k):
        assert path != "regular"
        return original(path, flags, *a, **k)

    monkeypatch.setattr(state.os, "open", opening)
    with pytest.raises(state.ProjectStateError, match="changed type"):
        state._dirty_project_files(repo, "projects/alpha")


def test_dirty_directory_earlier_tree_is_rechecked_after_other_records(
    tmp_path, monkeypatch
):
    repo, project = init_repo(tmp_path)
    folder = project / "tree"
    folder.mkdir()
    deep = folder / "earlier"
    deep.write_text("before")
    (project / "regular").write_text("regular")
    original_run = state._run

    def records(*args, **kwargs):
        if "status" in args:
            return subprocess.CompletedProcess(
                args, 0, b"?? projects/alpha/tree/\0?? projects/alpha/regular\0", b""
            )
        return original_run(*args, **kwargs)

    monkeypatch.setattr(state, "_run", records)
    original = state._dirty_leaf_snapshot

    def later(path, **kwargs):
        row = original(path, **kwargs)
        if path.name == "regular":
            deep.write_text("after earlier tree closed")
        return row

    monkeypatch.setattr(state, "_dirty_leaf_snapshot", later)
    with pytest.raises(state.ProjectStateError, match="changed after inventory"):
        state._dirty_project_files(repo, "projects/alpha")


def test_dirty_directory_multiple_git_roots_have_linear_final_rechecks(
    tmp_path, monkeypatch
):
    repo, project = init_repo(tmp_path)
    for number in range(6):
        nested = project / f"retained-{number}"
        nested.mkdir()
        run("git", "init", "--initial-branch=main", cwd=nested)
        (nested / "payload").write_text(f"value-{number}")
    original = state._dirty_entry_identity
    calls = {}

    def counted(path):
        calls[str(path)] = calls.get(str(path), 0) + 1
        return original(path)

    monkeypatch.setattr(state, "_dirty_entry_identity", counted)
    rows = state._dirty_project_files(repo, "projects/alpha")
    assert len(rows) == 6 and all(row["kind"] == "directory" for row in rows)
    assert calls and max(calls.values()) <= 2
    # Every root and payload still receives final identity verification.
    for number in range(6):
        nested = project / f"retained-{number}"
        assert calls[str(nested)] == 1
        assert calls[str(nested / "payload")] == 2

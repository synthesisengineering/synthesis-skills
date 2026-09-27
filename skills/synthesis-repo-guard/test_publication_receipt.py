import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess

import pytest

MODULE = Path(__file__).with_name("publication_receipt.py")


def owner():
    spec = importlib.util.spec_from_file_location(
        "publication_receipt_test_owner", MODULE
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def published(tmp_path):
    root = tmp_path / "guard"
    repo = tmp_path / "repo"
    remote = tmp_path / "remote.git"
    env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    subprocess.run(
        ["git", "init", "--bare", str(remote)],
        check=True,
        capture_output=True,
        env=env,
        timeout=10,
    )
    repo.mkdir()

    def git(*args):
        return subprocess.run(
            ["git", "-C", str(repo), *args],
            check=True,
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        ).stdout.strip()

    git("init", "-b", "main")
    git("config", "user.name", "Synthetic")
    git("config", "user.email", "synthetic@example.invalid")
    path = repo / "source.txt"
    path.write_text("published synthetic bytes\n")
    git("add", "source.txt")
    git("commit", "-m", "Fixture")
    git("remote", "add", "origin", str(remote))
    git("push", "-u", "origin", "main")
    native = "synthetic-native-session"
    manifest = (
        root / "pending" / (hashlib.sha256(native.encode()).hexdigest() + ".json")
    )
    manifest.parent.mkdir(parents=True)
    raw = (
        json.dumps(
            {
                "schema_version": 2,
                "session_id": native,
                "paths": [str(path)],
                "remote_paths": [],
            }
        )
        + "\n"
    ).encode()
    manifest.write_bytes(raw)
    results = [{"repo": str(repo), "action": "source-remote-ready", "alert": None}]
    return root, repo, path, native, manifest, raw, results, git


def test_proof_roundtrip_and_missing_receipt_unknown(published):
    root, repo, path, native, manifest, raw, results, git = published
    m = owner()
    assert m.observe(root, native)["status"] == "UNKNOWN"
    proof = m.build(manifest, raw, results)
    dest = root / "publication" / manifest.name
    dest.parent.mkdir()
    dest.write_text(json.dumps(proof))
    manifest.unlink()
    assert m.observe(root, native)["status"] == "VERIFIED_REMOTE_READY"
    assert m.observe(root, native)["live_remote_rechecked"] is False
    path.write_text("changed after publication")
    assert m.observe(root, native)["status"] == "UNKNOWN"


@pytest.mark.parametrize(
    "damage",
    [
        "foreign",
        "digest",
        "pathset",
        "unpublished",
        "global-only",
        "pending",
        "symlink",
        "corrupt",
    ],
)
def test_forged_stale_or_unbound_receipt_never_proves_publication(published, damage):
    root, repo, path, native, manifest, raw, results, git = published
    m = owner()
    proof = m.build(manifest, raw, results)
    dest = root / "publication" / manifest.name
    dest.parent.mkdir()
    manifest.unlink()
    if damage == "foreign":
        proof["session_id"] = "foreign"
    elif damage == "digest":
        proof["manifest_sha256"] = "0" * 64
    elif damage == "pathset":
        proof["files"] = []
    elif damage == "unpublished":
        path.write_text("unpublished synthetic commit\n")
        git("add", "source.txt")
        git("commit", "-m", "Later")
    elif damage == "pending":
        manifest.write_bytes(raw)
    dest.write_text(json.dumps(proof))
    if damage == "global-only":
        dest.rename(root / "remote-handoff-last.json")
    elif damage == "symlink":
        saved = dest.with_suffix(".saved")
        dest.rename(saved)
        dest.symlink_to(saved)
    elif damage == "corrupt":
        dest.write_text("{")
    assert m.observe(root, native)["status"] == "UNKNOWN"


def test_owner_refuses_unpublished_result_and_changed_manifest(published):
    root, repo, path, native, manifest, raw, results, git = published
    m = owner()
    with pytest.raises(m.ProofError):
        m.build(
            manifest,
            raw,
            [
                {
                    "repo": str(repo),
                    "action": "source-local-only",
                    "alert": "not published",
                }
            ],
        )
    manifest.write_bytes(raw + b" ")
    with pytest.raises(m.ProofError):
        m.build(manifest, raw, results)


def test_observer_has_finite_deadline_and_no_network(published, monkeypatch):
    root, repo, path, native, manifest, raw, results, git = published
    m = owner()
    proof = m.build(manifest, raw, results)
    dest = root / "publication" / manifest.name
    dest.parent.mkdir()
    dest.write_text(json.dumps(proof))
    manifest.unlink()
    calls = []
    real = m.subprocess.run

    def local(args, **kwargs):
        assert "fetch" not in args and "push" not in args and "ls-remote" not in args
        assert 0 < kwargs["timeout"] <= 2
        calls.append(args)
        return real(args, **kwargs)

    monkeypatch.setattr(m.subprocess, "run", local)
    assert m.observe(root, native)["status"] == "VERIFIED_REMOTE_READY"
    assert calls
    assert m.observe(root, native, seconds=0)["status"] == "UNKNOWN"


@pytest.mark.parametrize(
    "damage",
    ["world-write", "hardlink", "remote-changed", "same-stat-content", "file-link"],
)
def test_publication_receipt_and_content_identity_negatives(published, damage):
    root, repo, path, native, manifest, raw, results, git = published
    m = owner()
    proof = m.build(manifest, raw, results)
    dest = root / "publication" / manifest.name
    dest.parent.mkdir()
    dest.write_text(json.dumps(proof))
    manifest.unlink()
    if damage == "world-write":
        dest.chmod(0o666)
    elif damage == "hardlink":
        os.link(dest, dest.with_suffix(".link"))
    elif damage == "remote-changed":
        git("remote", "set-url", "origin", "/synthetic/foreign.git")
    elif damage == "same-stat-content":
        before = path.stat()
        path.write_bytes(b"x" * before.st_size)
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    else:
        saved = path.with_suffix(".saved")
        path.rename(saved)
        path.symlink_to(saved)
    assert m.observe(root, native)["status"] == "UNKNOWN"


def test_checkpoint_hook_uses_exact_offline_owner_proof(published, monkeypatch, capsys):
    pm = (
        Path(__file__).resolve().parents[1] / "synthesis-project-management" / "scripts"
    )
    monkeypatch.syspath_prepend(str(pm))
    import project_state

    root, repo, path, native, manifest, raw, results, git = published
    m = owner()
    proof = m.build(manifest, raw, results)
    dest = root / "publication" / manifest.name
    dest.parent.mkdir()
    dest.write_text(json.dumps(proof))
    manifest.unlink()
    monkeypatch.setattr(
        project_state, "observer_native_identity", lambda _p: ("codex", native)
    )
    payload = {"session_id": native, "hook_event_name": "Stop"}
    report = project_state._checkpoint_publication(payload, root)
    assert report["status"] == "VERIFIED_REMOTE_READY"
    project_state._emit_checkpoint_hook("PASS", [], payload, publication=report)
    output = json.loads(capsys.readouterr().out)
    diagnostic = json.loads(
        output["systemMessage"].removeprefix("PROJECT_CHECKPOINT_JSON: ")
    )
    assert diagnostic["publication"]["status"] == "VERIFIED_REMOTE_READY"
    assert diagnostic["checkpoint_accepted"] is True


@pytest.mark.parametrize("field,value", [("schema", True), ("verified_at_epoch", float("nan")), ("verified_at_epoch", True), ("verified_at_epoch", 10**30)])
def test_publication_metadata_is_strict(published, field, value):
    root, repo, path, native, manifest, raw, results, git = published
    m = owner()
    proof = m.build(manifest, raw, results)
    proof[field] = value
    dest = root / "publication" / manifest.name
    dest.parent.mkdir()
    dest.write_text(json.dumps(proof))
    manifest.unlink()
    assert m.observe(root, native)["status"] == "UNKNOWN"


def test_receipt_ancestor_alias_installed_during_read_is_unknown(published, monkeypatch):
    root, repo, path, native, manifest, raw, results, git = published
    m = owner()
    proof = m.build(manifest, raw, results)
    dest = root / "publication" / manifest.name
    dest.parent.mkdir()
    dest.write_text(json.dumps(proof))
    manifest.unlink()
    real = m._snapshot
    def exchanged(paths, deadline):
        value = real(paths, deadline)
        saved = root / "retained-publication"
        dest.parent.rename(saved)
        dest.parent.symlink_to(saved)
        return value
    monkeypatch.setattr(m, "_snapshot", exchanged)
    assert m.observe(root, native)["status"] == "UNKNOWN"


def test_remote_identity_change_during_snapshot_is_unknown(published, monkeypatch):
    root, repo, path, native, manifest, raw, results, git = published
    m = owner()
    proof = m.build(manifest, raw, results)
    dest = root / "publication" / manifest.name
    dest.parent.mkdir()
    dest.write_text(json.dumps(proof))
    manifest.unlink()
    real = m._git
    head_calls = 0
    def exchanged(repo_arg, deadline, *args):
        nonlocal head_calls
        value = real(repo_arg, deadline, *args)
        if args == ("rev-parse", "HEAD"):
            head_calls += 1
            if head_calls == 2:
                git("remote", "set-url", "origin", "/synthetic/changed-during-observation.git")
        return value
    monkeypatch.setattr(m, "_git", exchanged)
    assert m.observe(root, native)["status"] == "UNKNOWN"


def test_remote_url_identity_never_persists_embedded_credential(published):
    root, repo, path, native, manifest, raw, results, git = published
    m = owner()
    # Source fixture only: no network command uses this synthetic remote URL.
    url = "https://synthetic-user:synthetic-password@example.invalid/team/repo.git"
    git("remote", "set-url", "origin", url)
    proof = m.build(manifest, raw, results)
    encoded = json.dumps(proof)
    assert "synthetic-password" not in encoded
    assert url not in encoded
    assert proof["repositories"][str(repo)]["remote_url_sha256"] == hashlib.sha256(url.encode()).hexdigest()
    dest = root / "publication" / manifest.name
    dest.parent.mkdir()
    dest.write_text(encoded)
    manifest.unlink()
    assert m.observe(root, native)["status"] == "VERIFIED_REMOTE_READY"


@pytest.mark.parametrize("schema", [True, 1.0, 2.0])
def test_embedded_manifest_schema_is_not_numeric_coercion(published, schema):
    root, repo, path, native, manifest, raw, results, git = published
    m = owner()
    data = json.loads(raw)
    data["schema_version"] = schema
    invalid = json.dumps(data).encode()
    manifest.write_bytes(invalid)
    with pytest.raises(m.ProofError):
        m.build(manifest, invalid, results)

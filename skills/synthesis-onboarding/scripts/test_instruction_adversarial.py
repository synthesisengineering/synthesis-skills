"""Independent historical-instruction migration and ownership attacks.

Fixtures create actual committed sources and retained, content-addressed public
releases. They never alter the user's installation or select a Git hooks path.
"""

from __future__ import annotations

import copy
import contextlib
import hashlib
import json
import shutil
import stat
import subprocess
import sys
import types
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
import system_contract as contract  # noqa: E402


ADAPTER = b"@AGENTS.md\n"


@pytest.fixture(autouse=True)
def isolated_configuration(tmp_path, monkeypatch):
    import onboard

    root = tmp_path.resolve()
    monkeypatch.setattr(onboard, "HOME", root / "home")
    monkeypatch.setattr(onboard, "STATE_DIR", root / "state/synthesis")
    config = root / "gitconfig"
    config.write_text("[user]\n\tname = Example\n\temail = fixture@example.test\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Example")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "fixture@example.test")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "Example")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "fixture@example.test")
    monkeypatch.setenv("SYNTHESIS_HOME", str(root / "home"))
    for name, directory in (("XDG_CONFIG_HOME", "config"),
                            ("XDG_STATE_HOME", "state"),
                            ("XDG_CACHE_HOME", "cache")):
        monkeypatch.setenv(name, str(root / directory))
    monkeypatch.delenv("SYNTHESIS_ACTIVE_DESCRIPTOR", raising=False)


def git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def source(root: Path, text: str, relative="instructions.md") -> Path:
    root.mkdir(parents=True)
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    git(root, "init", "-q", "-b", "main")
    git(root, "add", "--", relative)
    git(root, "commit", "-q", "-m", "Add fixture")
    return root


def graph_for(roles):
    return {"schema_version": 1,
            "sources": [{"role": role, "path": "instructions.md", "required": True}
                        for role in roles],
            "output": "AGENTS.md", "claude_adapter": "CLAUDE.md"}


def legacy_pair(root: Path, *, converted=False):
    """Build the old wire format independently of the changed renderer."""
    root = root.resolve()
    roots = {role: source(root / role, role.title() + " committed rules.\n")
             for role in ("organization", "personal")}
    graph = graph_for(roots)
    workspace = root / "workspace"
    workspace.mkdir()
    records, parts = [], ["<!-- synthesis-instructions:generated -->", "# Workspace Instructions"]
    for role, repository in roots.items():
        content = (repository / "instructions.md").read_bytes()
        records.append({"role": role, "repository": str(repository),
                        "commit": git(repository, "rev-parse", "HEAD"),
                        "path": "instructions.md", "sha256": digest(content)})
        parts.extend(["", "## " + role.title(), "", content.decode().strip()])
    canonical = ("\n".join(parts).rstrip() + "\n").encode()
    (workspace / "AGENTS.md").write_bytes(canonical)
    (workspace / "CLAUDE.md").write_bytes(ADAPTER if converted else canonical)
    receipt = {"schema_version": 1, "generation": 1, "sources": records,
               "outputs": {name: {"path": str(workspace / name), "sha256": digest(canonical)}
                           for name in ("AGENTS.md", "CLAUDE.md")},
               "materialized_at": "2026-09-01T00:00:00Z"}
    return graph, roots, workspace, receipt


def pair_snapshot(workspace):
    return {name: ((workspace / name).read_bytes(), stat.S_IMODE((workspace / name).stat().st_mode))
            for name in ("AGENTS.md", "CLAUDE.md")}


def migrate(graph, roots, workspace, receipt, **kwargs):
    return contract.materialize_instruction_pair(
        graph, roots, workspace, generation=receipt["generation"] + 1,
        previous_receipt=receipt, **kwargs,
    )


@pytest.mark.parametrize("converted", [False, True], ids=["duplicate", "preconverted"])
def test_historical_pair_and_committed_source_advancement(tmp_path, converted):
    graph, roots, workspace, receipt = legacy_pair(tmp_path, converted=converted)
    expected = "legacy-adapter" if converted else "legacy-duplicate"
    assert contract.instruction_output_state(workspace, receipt) == expected
    original = pair_snapshot(workspace)
    original_receipt = copy.deepcopy(receipt)
    (roots["personal"] / "instructions.md").write_text("New committed personal rules.\n")
    git(roots["personal"], "add", "instructions.md")
    git(roots["personal"], "commit", "-q", "-m", "Update fixture")
    assert contract.instruction_output_state(workspace, receipt) == expected
    validated = migrate(graph, roots, workspace, receipt, validate_only=True)
    assert validated["validated"] is True
    assert pair_snapshot(workspace) == original
    assert receipt == original_receipt
    result = migrate(graph, roots, workspace, receipt)
    assert result["migrated_from"] == expected
    assert (workspace / "CLAUDE.md").read_bytes() == ADAPTER
    assert b"New committed personal rules." in (workspace / "AGENTS.md").read_bytes()
    assert result["sources"][-1]["commit"] == git(roots["personal"], "rev-parse", "HEAD")
    assert contract.instruction_output_state(workspace, result) == "current"
    stable = pair_snapshot(workspace)
    repeated = migrate(graph, roots, workspace, result)
    assert repeated["unchanged"] is True
    assert repeated["generation"] == result["generation"]
    assert pair_snapshot(workspace) == stable


@pytest.mark.parametrize("converted", [False, True])
@pytest.mark.parametrize("attack", ["agents-edit", "adapter-extra", "adapter-crlf", "adapter-link",
                                    "wrong-path", "wrong-digest", "extra-output", "wrong-schema", "boolean-schema",
                                    "duplicate-role", "reordered-roles", "missing-source", "fake-commit"])
def test_historical_pair_attacks_preserve_outputs(tmp_path, converted, attack):
    graph, roots, workspace, receipt = legacy_pair(tmp_path, converted=converted)
    if attack == "agents-edit":
        (workspace / "AGENTS.md").write_bytes(b"User-owned edit.\n")
    elif attack == "adapter-extra":
        (workspace / "CLAUDE.md").write_bytes(ADAPTER + b"Additional user rules.\n")
    elif attack == "adapter-crlf":
        (workspace / "CLAUDE.md").write_bytes(b"@AGENTS.md\r\n")
    elif attack == "adapter-link":
        (workspace / "CLAUDE.md").unlink()
        (workspace / "CLAUDE.md").symlink_to("AGENTS.md")
    elif attack == "wrong-path":
        receipt["outputs"]["CLAUDE.md"]["path"] = str(tmp_path / "other/CLAUDE.md")
    elif attack == "wrong-digest":
        receipt["outputs"]["CLAUDE.md"]["sha256"] = "e" * 64
    elif attack == "extra-output":
        receipt["outputs"]["other.md"] = receipt["outputs"]["AGENTS.md"]
    elif attack == "wrong-schema":
        receipt["schema_version"] = 2
    elif attack == "boolean-schema":
        receipt["schema_version"] = True
    elif attack == "duplicate-role":
        receipt["sources"].append(copy.deepcopy(receipt["sources"][0]))
    elif attack == "reordered-roles":
        receipt["sources"].reverse()
    elif attack == "missing-source":
        receipt["sources"] = []
    elif attack == "fake-commit":
        receipt["sources"][0]["commit"] = "f" * 40
    before = pair_snapshot(workspace)
    receipt_before = copy.deepcopy(receipt)
    with pytest.raises(contract.ContractError):
        migrate(graph, roots, workspace, receipt)
    assert pair_snapshot(workspace) == before
    assert receipt == receipt_before
    if attack == "adapter-link":
        assert (workspace / "CLAUDE.md").is_symlink()


def immutable_legacy_pair(tmp_path, monkeypatch, public_relative="instructions.md"):
    root = tmp_path.resolve()
    public = source(root / "public-source", "Public committed rules.\n", relative=public_relative)
    for client in (".claude-plugin", ".codex-plugin"):
        (public / client).mkdir()
        (public / client / "plugin.json").write_text(json.dumps({"name": "synthesis-skills", "version": "9.8.7"}) + "\n")
    git(public, "add", "--", ".claude-plugin", ".codex-plugin")
    git(public, "commit", "-q", "-m", "Add fixture metadata")
    git(public, "branch", "stable")
    git(public, "tag", "v9.8.7")
    descriptor = contract.release_descriptor_from_checkout(
        public, "stable", "stable", "https://example.test/public-skills.git")
    state = contract.SystemState()
    installed = state.cache_dir / "releases" / descriptor["content_digest"]
    shutil.copytree(public, installed, ignore=shutil.ignore_patterns(".git"))
    retained = state.state_dir / "releases" / "9.8.7.json"
    retained.parent.mkdir(parents=True)
    retained.write_text(json.dumps(descriptor))
    active = root / "active-release.json"
    active.write_text(json.dumps({**descriptor, "release_root": str(installed)}))
    monkeypatch.setenv("SYNTHESIS_ACTIVE_DESCRIPTOR", str(active))
    identity = contract.public_source_identity(installed)
    org = source(root / "organization", "Organization committed rules.\n")
    graph = graph_for(("public", "organization"))
    graph["sources"][0]["path"] = public_relative
    roots = {"public": installed, "organization": org}
    workspace = root / "workspace"
    # The materialized canonical content is independently checked below.
    receipt = contract.materialize_instruction_pair(
        graph, roots, workspace, generation=1, source_identities={"public": identity})
    expected = ("<!-- synthesis-instructions:generated -->\n# Workspace Instructions\n\n"
                "## Public\n\nPublic committed rules.\n\n"
                "## Organization\n\nOrganization committed rules.\n").encode()
    assert (workspace / "AGENTS.md").read_bytes() == expected
    receipt["outputs"]["CLAUDE.md"]["sha256"] = digest(expected)
    # This is the real failure shape: the private installer already converted it.
    (workspace / "CLAUDE.md").write_bytes(ADAPTER)
    return graph, roots, workspace, receipt, descriptor, retained, identity


def test_retained_immutable_release_proof_accepts_committed_org_update(tmp_path, monkeypatch):
    graph, roots, workspace, receipt, descriptor, _retained, identity = immutable_legacy_pair(tmp_path, monkeypatch)
    assert contract.instruction_output_state(workspace, receipt) == "legacy-adapter"
    assert not (roots["public"] / ".git").exists()
    assert roots["public"].name == descriptor["content_digest"]
    (roots["organization"] / "instructions.md").write_text("Advanced organization rules.\n")
    git(roots["organization"], "add", "instructions.md")
    git(roots["organization"], "commit", "-q", "-m", "Update fixture")
    result = migrate(graph, roots, workspace, receipt, source_identities={"public": identity})
    assert contract.instruction_output_state(workspace, result) == "current"
    assert b"Advanced organization rules." in (workspace / "AGENTS.md").read_bytes()


@pytest.mark.parametrize("attack", ["missing-descriptor", "descriptor-link", "invalid-descriptor", "broken-json",
                                    "different-commit", "different-content", "content-tamper",
                                    "non-addressed-root", "receipt-commit", "source-link"])
def test_retained_immutable_release_proof_attacks(tmp_path, monkeypatch, attack):
    graph, roots, workspace, receipt, descriptor, retained, identity = immutable_legacy_pair(tmp_path, monkeypatch)
    if attack == "missing-descriptor":
        retained.unlink()
    elif attack == "descriptor-link":
        other = tmp_path / "descriptor.json"
        retained.rename(other)
        retained.symlink_to(other)
    elif attack == "invalid-descriptor":
        retained.write_text(json.dumps({"schema_version": 1}))
    elif attack == "broken-json":
        retained.write_text("{incomplete")
    elif attack == "different-commit":
        retained.write_text(json.dumps({**descriptor, "commit": "e" * 40}))
    elif attack == "different-content":
        retained.write_text(json.dumps({**descriptor, "content_digest": "e" * 64}))
    elif attack == "content-tamper":
        (roots["public"] / "instructions.md").write_text("Unexpected changed rules.\n")
    elif attack == "non-addressed-root":
        copied = tmp_path.resolve() / "copied-public"
        shutil.copytree(roots["public"], copied)
        receipt["sources"][0]["repository"] = str(copied)
    elif attack == "receipt-commit":
        receipt["sources"][0]["commit"] = "e" * 40
    elif attack == "source-link":
        target = roots["public"] / "instructions.md"
        moved = tmp_path / "public-instructions.md"
        target.rename(moved)
        target.symlink_to(moved)
    before = pair_snapshot(workspace)
    with pytest.raises(contract.ContractError):
        migrate(graph, roots, workspace, receipt, source_identities={"public": identity})
    assert pair_snapshot(workspace) == before


@pytest.mark.parametrize("receipted", [False, True])
def test_workspace_symlink_ancestor_cannot_redirect_activation(tmp_path, receipted):
    graph, roots, workspace, receipt = legacy_pair(tmp_path)
    real_parent = workspace.parent
    alias = tmp_path.resolve() / "alias"
    alias.symlink_to(real_parent, target_is_directory=True)
    redirected = alias / "workspace"
    redirected_receipt = copy.deepcopy(receipt)
    for name, output in redirected_receipt["outputs"].items():
        output["path"] = str(redirected / name)
    before = pair_snapshot(workspace)
    with pytest.raises(contract.ContractError, match="non-symlink"):
        contract.materialize_instruction_pair(
            graph, roots, redirected, generation=2,
            previous_receipt=redirected_receipt if receipted else None)
    assert pair_snapshot(workspace) == before


def test_adoption_metadata_survives_migration_and_later_changed_generation(tmp_path):
    graph, roots, workspace, receipt = legacy_pair(tmp_path, converted=True)
    archive = tmp_path / "archive"
    archive.mkdir()
    old = {"AGENTS.md": b"Original canonical rules.\n", "CLAUDE.md": b"Original separate rules.\n"}
    metadata = {}
    for name, content in old.items():
        (archive / name).write_bytes(content)
        metadata[name] = {"archive_path": str(archive / name), "sha256": digest(content),
                          "mode": "0o640", "archived_at": "2026-09-01T00:00:00Z"}
    receipt["adopted_outputs"] = copy.deepcopy(metadata)
    result = migrate(graph, roots, workspace, receipt)
    (roots["personal"] / "instructions.md").write_text("Subsequent committed rules.\n")
    git(roots["personal"], "add", "instructions.md")
    git(roots["personal"], "commit", "-q", "-m", "Update fixture")
    later = migrate(graph, roots, workspace, result)
    assert later["generation"] == 3
    assert result["adopted_outputs"] == later["adopted_outputs"] == metadata
    assert all((archive / name).read_bytes() == content for name, content in old.items())
    assert contract.instruction_output_state(workspace, later) == "current"


@pytest.mark.parametrize("converted", [False, True])
def test_migration_second_activation_failure_restores_prior_bytes_modes_and_receipt(tmp_path, converted):
    graph, roots, workspace, receipt = legacy_pair(tmp_path, converted=converted)
    (workspace / "AGENTS.md").chmod(0o640)
    (workspace / "CLAUDE.md").chmod(0o600)
    before = pair_snapshot(workspace)
    original_receipt = copy.deepcopy(receipt)
    with pytest.raises(contract.ContractError, match="injected"):
        migrate(graph, roots, workspace, receipt, fail_after_first=True)
    assert pair_snapshot(workspace) == before
    assert receipt == original_receipt
    assert sorted(p.name for p in workspace.iterdir()) == ["AGENTS.md", "CLAUDE.md"]


@pytest.mark.parametrize("initial", ["legacy-duplicate", "legacy-adapter", "current"])
@pytest.mark.parametrize("validate_only", [False, True], ids=["activate", "validate-only"])
def test_source_resolution_cannot_hide_a_new_concurrent_instruction_edit(tmp_path, monkeypatch, initial, validate_only):
    graph, roots, workspace, receipt = legacy_pair(tmp_path, converted=initial != "legacy-duplicate")
    if initial == "current":
        receipt = migrate(graph, roots, workspace, receipt)
    original_claude = (workspace / "CLAUDE.md").read_bytes()
    original = contract._tracked_source
    concurrent_content = b"Concurrent user-owned instructions.\n"
    changed = False

    def source_probe(*args, **kwargs):
        nonlocal changed
        result = original(*args, **kwargs)
        if not changed:
            changed = True
            (workspace / "AGENTS.md").write_bytes(concurrent_content)
        return result

    monkeypatch.setattr(contract, "_tracked_source", source_probe)
    with pytest.raises(contract.ContractError):
        migrate(graph, roots, workspace, receipt, validate_only=validate_only)
    assert (workspace / "AGENTS.md").read_bytes() == concurrent_content
    assert (workspace / "CLAUDE.md").read_bytes() == original_claude


@pytest.mark.parametrize("target_name", ["AGENTS.md", "CLAUDE.md"])
@pytest.mark.parametrize("edit", ["bytes", "mode"])
def test_completed_staging_does_not_replace_newer_output_edits(tmp_path, monkeypatch, target_name, edit):
    graph, roots, workspace, receipt = legacy_pair(tmp_path, converted=True)
    before = pair_snapshot(workspace)
    original = contract.tempfile.NamedTemporaryFile
    staged = 0
    changed = False
    concurrent_content = b"User-owned edit after staging.\n"

    @contextlib.contextmanager
    def stage(*args, **kwargs):
        nonlocal staged, changed
        with original(*args, **kwargs) as temporary:
            yield temporary
        if kwargs.get("suffix") == ".stage":
            staged += 1
            if staged == 2:
                changed = True
                target = workspace / target_name
                if edit == "bytes":
                    target.write_bytes(concurrent_content)
                else:
                    target.chmod(0o400)

    monkeypatch.setattr(contract.tempfile, "NamedTemporaryFile", stage)
    with pytest.raises(contract.ContractError):
        migrate(graph, roots, workspace, receipt)
    assert changed
    after = pair_snapshot(workspace)
    for name in before:
        expected = before[name]
        if name == target_name:
            expected = ((concurrent_content, expected[1]) if edit == "bytes"
                        else (expected[0], 0o400))
        assert after[name] == expected


@pytest.mark.parametrize("target_name", ["AGENTS.md", "CLAUDE.md"])
def test_staging_error_cannot_restore_over_a_concurrent_edit(tmp_path, monkeypatch, target_name):
    graph, roots, workspace, receipt = legacy_pair(tmp_path, converted=True)
    original_receipt = copy.deepcopy(receipt)
    before = pair_snapshot(workspace)
    original = contract.tempfile.NamedTemporaryFile
    staged = 0
    concurrent_content = b"User-owned edit before staging failure.\n"

    @contextlib.contextmanager
    def stage(*args, **kwargs):
        nonlocal staged
        with original(*args, **kwargs) as temporary:
            yield temporary
        if kwargs.get("suffix") == ".stage":
            staged += 1
            if staged == 2:
                (workspace / target_name).write_bytes(concurrent_content)
                raise contract.ContractError("injected staging failure")

    monkeypatch.setattr(contract.tempfile, "NamedTemporaryFile", stage)
    with pytest.raises(contract.ContractError):
        migrate(graph, roots, workspace, receipt)
    assert staged == 2
    assert receipt == original_receipt
    for name, (content, mode) in before.items():
        expected = concurrent_content if name == target_name else content
        assert (workspace / name).read_bytes() == expected
        assert stat.S_IMODE((workspace / name).stat().st_mode) == mode


@pytest.mark.parametrize("target_name", ["AGENTS.md", "CLAUDE.md"])
@pytest.mark.parametrize("after_activation", ["AGENTS.md", "CLAUDE.md"], ids=["first-activation", "second-activation"])
def test_activation_or_rollback_never_clobbers_a_newer_output_edit(tmp_path, monkeypatch, target_name, after_activation):
    graph, roots, workspace, receipt = legacy_pair(tmp_path, converted=True)
    before = pair_snapshot(workspace)
    original_receipt = copy.deepcopy(receipt)
    (roots["personal"] / "instructions.md").write_text("New candidate source rules.\n")
    git(roots["personal"], "add", "instructions.md")
    git(roots["personal"], "commit", "-q", "-m", "Update fixture")
    original = contract.os.replace
    changed = False
    concurrent_content = b"User-owned edit during pair activation.\n"

    def replace(source_path, target_path):
        nonlocal changed
        result = original(source_path, target_path)
        if (not changed and str(source_path).endswith(".stage")
                and Path(target_path) == workspace / after_activation):
            changed = True
            (workspace / target_name).write_bytes(concurrent_content)
        return result

    monkeypatch.setattr(contract.os, "replace", replace)
    with pytest.raises(contract.ContractError):
        migrate(graph, roots, workspace, receipt)
    assert changed
    assert receipt == original_receipt
    for name, (content, _mode) in before.items():
        expected = concurrent_content if name == target_name else content
        assert (workspace / name).read_bytes() == expected
    assert sorted(p.name for p in workspace.iterdir()) == ["AGENTS.md", "CLAUDE.md"]


@pytest.mark.parametrize("target_name", ["AGENTS.md", "CLAUDE.md"])
def test_staged_candidate_must_still_match_the_verified_render(tmp_path, monkeypatch, target_name):
    graph, roots, workspace, receipt = legacy_pair(tmp_path, converted=True)
    before = pair_snapshot(workspace)
    original = contract.tempfile.NamedTemporaryFile
    staged = {}

    @contextlib.contextmanager
    def stage(*args, **kwargs):
        with original(*args, **kwargs) as temporary:
            yield temporary
            if kwargs.get("suffix") == ".stage":
                staged[str(kwargs["prefix"]).removesuffix(".")] = Path(temporary.name)
        if len(staged) == 2:
            staged[target_name].write_bytes(b"Unverified staged content.\n")

    monkeypatch.setattr(contract.tempfile, "NamedTemporaryFile", stage)
    with pytest.raises(contract.ContractError):
        migrate(graph, roots, workspace, receipt)
    assert len(staged) == 2
    assert pair_snapshot(workspace) == before


def test_failure_restoring_one_owned_output_does_not_skip_the_other(tmp_path, monkeypatch):
    graph, roots, workspace, receipt = legacy_pair(tmp_path, converted=True)
    (workspace / "CLAUDE.md").chmod(0o640)
    before = pair_snapshot(workspace)
    original_receipt = copy.deepcopy(receipt)
    (roots["personal"] / "instructions.md").write_text("New candidate source rules.\n")
    git(roots["personal"], "add", "instructions.md")
    git(roots["personal"], "commit", "-q", "-m", "Update fixture")
    original_fsync = contract._fsync_directory
    original_restore = contract._restore_file
    failed = False
    restoration_attempts = []

    def fail_final_sync(path):
        nonlocal failed
        if Path(path) == workspace and not failed:
            failed = True
            raise contract.ContractError("injected final activation failure")
        return original_fsync(path)

    def restore(path, prior):
        restoration_attempts.append(Path(path).name)
        if Path(path).name == "AGENTS.md":
            raise OSError("injected first-output restoration failure")
        return original_restore(path, prior)

    monkeypatch.setattr(contract, "_fsync_directory", fail_final_sync)
    monkeypatch.setattr(contract, "_restore_file", restore)
    with pytest.raises((contract.ContractError, OSError)):
        migrate(graph, roots, workspace, receipt)
    assert failed
    assert restoration_attempts == ["AGENTS.md", "CLAUDE.md"]
    assert pair_snapshot(workspace)["CLAUDE.md"] == before["CLAUDE.md"]
    assert b"New candidate source rules." in (workspace / "AGENTS.md").read_bytes()
    assert receipt == original_receipt


def test_instruction_read_access_time_is_not_a_concurrent_content_edit(tmp_path, monkeypatch):
    target = tmp_path.resolve() / "instructions.md"
    target.write_bytes(b"Stable instruction bytes.\n")
    original = Path.lstat
    calls = 0

    class AccessTimeAdvanced:
        """Model the kernel updating only atime after the real content read."""

        def __init__(self, metadata):
            self.metadata = metadata

        def __getattr__(self, name):
            value = getattr(self.metadata, name)
            if name == "st_atime":
                return value + 60
            if name == "st_atime_ns":
                return value + 60_000_000_000
            return value

        def __iter__(self):
            values = list(self.metadata)
            values[7] += 60
            return iter(values)

        def __eq__(self, other):
            return tuple(self) == tuple(other)

    def lstat(path, *args, **kwargs):
        nonlocal calls
        metadata = original(path, *args, **kwargs)
        if path == target:
            calls += 1
            if calls >= 2:
                return AccessTimeAdvanced(metadata)
        return metadata

    monkeypatch.setattr(Path, "lstat", lstat)
    observed = contract._instruction_snapshot(target)
    assert observed[0] is True
    assert observed[1] == b"Stable instruction bytes.\n"


@pytest.mark.parametrize("source_kind", ["git", "immutable-release"])
@pytest.mark.parametrize("forgery", ["missing-commit", "tree-object"])
def test_actual_doctor_rejects_forged_public_commit_in_current_receipt(tmp_path, monkeypatch, source_kind, forgery):
    import onboard

    public_relative = "skills/synthesis-onboarding/references/kernel.example.md"
    if source_kind == "immutable-release":
        graph, roots, workspace, old, _descriptor, _retained, identity = immutable_legacy_pair(
            tmp_path, monkeypatch, public_relative=public_relative)
        receipt = migrate(graph, roots, workspace, old, source_identities={"public": identity})
    else:
        roots = {"public": source(tmp_path.resolve() / "public", "Public committed rules.\n", relative=public_relative),
                 "organization": source(tmp_path.resolve() / "organization", "Organization committed rules.\n")}
        graph = graph_for(roots)
        graph["sources"][0]["path"] = public_relative
        workspace = tmp_path.resolve() / "workspace"
        receipt = contract.materialize_instruction_pair(graph, roots, workspace, generation=1)
        # The original commit still binds the same instruction bytes after an
        # unrelated source-repository commit. Fresh HEAD equality is not proof.
        (roots["public"] / "unrelated.md").write_text("Unrelated committed content.\n")
        git(roots["public"], "add", "unrelated.md")
        git(roots["public"], "commit", "-q", "-m", "Update fixture")
    assert contract.instruction_output_state(workspace, receipt) == "current"
    manifest = {"org": {"workspace": workspace.name},
                "_path": str(roots["organization"] / ".agents/onboarding.yaml"),
                "skills_repos": [], "knowledge_bases": [],
                "instruction_sources": [{"path": "instructions.md", "required": True}]}
    actual_receipts = onboard.Receipts
    path = tmp_path / "doctor-receipts.json"
    receipts = actual_receipts(path)
    receipts.data["instruction_receipt"] = receipt
    receipts.save()
    monkeypatch.setattr(onboard, "Receipts", lambda *args, **kwargs: actual_receipts(path))
    monkeypatch.setattr(onboard, "WORKSPACES_ROOT", workspace.parent)
    monkeypatch.setattr(onboard, "source_root", lambda: roots["public"])
    # Execute the actual source and output doctor blocks. Unselected plugin and
    # personal layers are outside this source-provenance control.
    monkeypatch.setattr(onboard, "render_layer_doctor", lambda *args, **kwargs: False)

    def doctor():
        report = onboard.Report(as_json=True)
        code = onboard.doctor(report, manifest, [], onboard.normalize_policy("stable", None))
        return code, report

    code, report = doctor()
    assert code == 0, report.steps  # Positive control through the same consumer.
    forged_commit = "e" * 40
    if forgery == "tree-object":
        forged_commit = (_descriptor["tree"] if source_kind == "immutable-release"
                         else git(roots["public"], "rev-parse", "HEAD^{tree}"))
    receipts.data["instruction_receipt"]["sources"][0]["commit"] = forged_commit
    receipts.save()
    before = {str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    code, report = doctor()
    after = {str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert after == before
    assert code == 1, report.steps
    assert any(step["status"] == onboard.ERROR and "source" in step["detail"] for step in report.steps)


@pytest.mark.parametrize("manifest_bytes", [b"{incomplete", b"null", b"[]", b'"string"'])
def test_historical_manifest_corruption_is_a_handled_contract_failure(tmp_path, monkeypatch, manifest_bytes):
    graph, roots, workspace, receipt, _descriptor, _retained, identity = immutable_legacy_pair(tmp_path, monkeypatch)
    (roots["public"] / ".claude-plugin/plugin.json").write_bytes(manifest_bytes)
    before = pair_snapshot(workspace)
    with pytest.raises(contract.ContractError):
        migrate(graph, roots, workspace, receipt, source_identities={"public": identity})
    assert pair_snapshot(workspace) == before


def test_actual_private_adapter_and_public_engine_converge_without_mutating_sources(tmp_path, monkeypatch):
    installed = Path.home() / ".synthesis/agent-control/scripts/instruction_adapters.py"
    if not installed.is_file() or installed.is_symlink():
        pytest.skip("optional private adapter is not installed")
    original_source = installed.read_bytes()
    module = types.ModuleType("isolated_instruction_adapters")
    module.__file__ = str(installed)
    monkeypatch.setitem(sys.modules, module.__name__, module)
    # Compile the actual installed code without generating a cache beside it.
    exec(compile(original_source, str(installed), "exec"), module.__dict__)
    graph, roots, workspace, receipt = legacy_pair(tmp_path)
    classified = module.classify(workspace)
    assert classified.action == "deduplicate"
    result = module.apply(workspace, classified, tmp_path / "adapter-backups")
    assert result.action == "ok"
    assert (workspace / "CLAUDE.md").read_bytes() == ADAPTER
    migrated = migrate(graph, roots, workspace, receipt)
    stable = pair_snapshot(workspace)
    assert contract.instruction_output_state(workspace, migrated) == "current"
    classified = module.classify(workspace)
    assert classified.action == "ok" and not classified.changed
    assert pair_snapshot(workspace) == stable
    assert installed.read_bytes() == original_source

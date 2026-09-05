"""Instruction ownership regressions, including a real recorded predecessor."""

import copy
import hashlib
import os
import subprocess
from pathlib import Path

import pytest

import system_contract as contract


ADAPTER = b"@AGENTS.md\n"


@pytest.fixture
def instructions(tmp_path, monkeypatch):
    for key in list(os.environ):
        if key.startswith("GIT_CONFIG_") or key in {
            "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR",
            "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        }:
            monkeypatch.delenv(key)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    source = tmp_path / "source"
    source.mkdir()

    def git(*args):
        result = subprocess.run(
            ["git", "-C", str(source), *args], capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr
        return result.stdout.strip()

    git("init", "-q", "-b", "main")
    git("config", "user.name", "Fixture")
    git("config", "user.email", "fixture@example.test")
    (source / "instructions.md").write_text("Keep every user instruction.\n")
    git("add", "instructions.md")
    git("commit", "-q", "-m", "Seed fixture")
    graph = {
        "schema_version": 1,
        "sources": [{"role": "personal", "path": "instructions.md", "required": True}],
        "output": "AGENTS.md", "claude_adapter": "CLAUDE.md",
    }
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    body = (b"<!-- synthesis-instructions:generated -->\n# Workspace Instructions\n"
            b"\n## Personal\n\nKeep every user instruction.\n")
    for name in ("AGENTS.md", "CLAUDE.md"):
        (workspace / name).write_bytes(body)
        (workspace / name).chmod(0o600)
    receipt = {
        "schema_version": 1, "generation": 1,
        "outputs": {name: {"path": str(workspace / name),
                    "sha256": hashlib.sha256(body).hexdigest()}
                    for name in ("AGENTS.md", "CLAUDE.md")},
        "sources": [{"role": "personal", "repository": str(source),
                     "path": "instructions.md", "commit": git("rev-parse", "HEAD"),
                     "sha256": contract.file_digest(source / "instructions.md")}],
        "adopted_outputs": {"AGENTS.md": {"archive_path": "retained-original", "sha256": "a" * 64}},
    }
    return source, workspace, graph, receipt, git


def materialize(fixture, receipt=None, **kwargs):
    source, workspace, graph, _, _ = fixture
    return contract.materialize_instruction_pair(
        graph, {"personal": source}, workspace, 2, previous_receipt=receipt, **kwargs,
    )


def test_fresh_pair_is_canonical_content_and_literal_import(instructions):
    receipt = materialize(instructions)
    workspace = instructions[1]
    assert (workspace / "CLAUDE.md").read_bytes() == ADAPTER
    assert receipt["outputs"]["AGENTS.md"]["sha256"] != receipt["outputs"]["CLAUDE.md"]["sha256"]
    assert materialize(instructions, receipt)["unchanged"] is True


@pytest.mark.parametrize("preconverted", [False, True])
@pytest.mark.parametrize("advance_source", [False, True])
def test_receipted_predecessor_converges_without_losing_archive(instructions, preconverted, advance_source):
    source, workspace, _, previous, git = instructions
    if preconverted:
        (workspace / "CLAUDE.md").write_bytes(ADAPTER)
    if advance_source:
        (source / "instructions.md").write_text("Keep every user instruction.\nAdd a verified instruction.\n")
        git("add", "instructions.md")
        git("commit", "-q", "-m", "Update fixture")
    before = {p.name: p.read_bytes() for p in workspace.iterdir()}
    materialize(instructions, previous, validate_only=True)
    assert before == {p.name: p.read_bytes() for p in workspace.iterdir()}
    current = materialize(instructions, previous)
    assert (workspace / "CLAUDE.md").read_bytes() == ADAPTER
    assert current["adopted_outputs"] == previous["adopted_outputs"]
    assert current["generation"] == 2
    assert contract.instruction_output_state(workspace, current) == "current"
    assert materialize(instructions, current)["unchanged"] is True


@pytest.mark.parametrize("bad", ["agents", "comment", "crlf", "missing", "path", "source-hash", "commit", "roles", "schema", "symlink"])
def test_preconverted_transition_rejects_unproved_changes(instructions, bad):
    source, workspace, _, original, _ = instructions
    previous = copy.deepcopy(original)
    (workspace / "CLAUDE.md").write_bytes(ADAPTER)
    if bad == "agents":
        (workspace / "AGENTS.md").write_text("User edit\n")
    elif bad == "comment":
        (workspace / "CLAUDE.md").write_bytes(ADAPTER + b"# User note\n")
    elif bad == "crlf":
        (workspace / "CLAUDE.md").write_bytes(b"@AGENTS.md\r\n")
    elif bad == "missing":
        (workspace / "AGENTS.md").unlink()
    elif bad == "path":
        previous["outputs"]["CLAUDE.md"]["path"] = str(workspace / "elsewhere.md")
    elif bad == "source-hash":
        previous["sources"][0]["sha256"] = "0" * 64
    elif bad == "commit":
        previous["sources"][0]["commit"] = "0" * 40
    elif bad == "roles":
        previous["sources"] *= 2
    elif bad == "schema":
        previous["schema_version"] = 999
    elif bad == "symlink":
        (workspace / "CLAUDE.md").unlink()
        (workspace / "CLAUDE.md").symlink_to(source / "instructions.md")
    before = {p.name: (p.is_symlink(), p.read_bytes()) for p in workspace.iterdir()}
    with pytest.raises(contract.ContractError):
        materialize(instructions, previous)
    assert before == {p.name: (p.is_symlink(), p.read_bytes()) for p in workspace.iterdir()}


@pytest.mark.parametrize("preconverted", [False, True])
def test_transition_failure_restores_both_outputs_and_modes(instructions, preconverted):
    _, workspace, _, previous, _ = instructions
    if preconverted:
        (workspace / "CLAUDE.md").write_bytes(ADAPTER)
    before = {p.name: (p.read_bytes(), p.stat().st_mode) for p in workspace.iterdir()}
    with pytest.raises(contract.ContractError, match="injected"):
        materialize(instructions, previous, fail_after_first=True)
    assert before == {p.name: (p.read_bytes(), p.stat().st_mode) for p in workspace.iterdir()}


def test_legacy_output_is_explicitly_migration_required(instructions):
    _, workspace, _, previous, _ = instructions
    assert contract.instruction_output_state(workspace, previous) == "legacy-duplicate"
    (workspace / "CLAUDE.md").write_bytes(ADAPTER)
    assert contract.instruction_output_state(workspace, previous) == "legacy-adapter"

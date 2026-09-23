from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


GUARD_PATH = Path(__file__).parent.parent / "guards" / "installed_artifact_guard.py"
MANIFEST = {
    "source_repo": "github.com/example/private-skills",
    "source_type": "private",
    "source_path": "example-skill/SKILL.md",
    "source_commit": "0123456789abcdef0123456789abcdef01234567",
    "installed_at": "2026-09-10T19:28:10Z",
    "installed_by": "install.sh",
}
OWNER_TEXT = (
    "installed by install.sh from github.com/example/private-skills "
    "(example-skill/SKILL.md) at 0123456789abcdef0123456789abcdef01234567; "
    "edit that source, then run that installer's update"
)
ABSENT_TEXT = (
    "no readable .source.json beside this artifact; "
    "run every declared installer status"
)
SECRET = "SECRET-DO-NOT-PRINT"


@pytest.fixture
def guard(tmp_path: Path, monkeypatch):
    """Load a fresh guard whose HOME, and so every protected root, is under tmp_path."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    spec = importlib.util.spec_from_file_location(
        "installed_artifact_guard_owner_under_test", GUARD_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.HOME == home.resolve()
    assert all(module.HOME in root.parents for root in module.PROTECTED_ROOTS)
    return module


def installed_skill(root: Path, manifest: str | None) -> Path:
    skill = root / "example-skill"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# example\n", encoding="utf-8")
    if manifest is not None:
        (skill / ".source.json").write_text(manifest, encoding="utf-8")
    return skill


@pytest.mark.parametrize("root_index", [0, 1, 2], ids=["claude", "agents", "codex"])
def test_refusal_names_installer_repo_and_path_from_source_json(guard, root_index: int) -> None:
    skill = installed_skill(guard.PROTECTED_ROOTS[root_index], json.dumps(MANIFEST))
    artifact = skill / "SKILL.md"

    reason = guard.reason_for(artifact)

    assert reason is not None
    assert reason.startswith(f"{artifact} is an installed skill artifact.")
    assert "reinstall and verify drift" in reason
    assert OWNER_TEXT in reason


def test_refusal_walks_up_to_the_nearest_manifest_for_nested_artifacts(guard) -> None:
    skill = installed_skill(guard.PROTECTED_ROOTS[0], json.dumps(MANIFEST))
    nested = skill / "references" / "notes.md"

    reason = guard.reason_for(nested)

    assert reason is not None
    assert OWNER_TEXT in reason


def test_refusal_without_source_json_still_blocks_and_names_the_absence(guard) -> None:
    skill = installed_skill(guard.PROTECTED_ROOTS[0], None)

    reason = guard.reason_for(skill / "SKILL.md")

    assert reason is not None
    assert reason.startswith(f"{skill / 'SKILL.md'} is an installed skill artifact.")
    assert ABSENT_TEXT in reason
    assert "installed by" not in reason


@pytest.mark.parametrize(
    "manifest",
    [
        '{"source_repo": "github.com/example/private-skills", ' + SECRET,
        f"not json at all {SECRET}",
        "[]",
        json.dumps({**MANIFEST, "installed_by": 7}),
        json.dumps({"source_repo": "github.com/example/private-skills"}),
        json.dumps({**MANIFEST, "source_commit": ""}),
        json.dumps({**MANIFEST, "source_commit": "\x1b \x00\x07\t"}),
    ],
    ids=[
        "truncated",
        "prose",
        "list",
        "wrong-type",
        "missing-fields",
        "empty-field",
        "control-only-field",
    ],
)
def test_refusal_with_malformed_source_json_still_blocks(guard, manifest: str) -> None:
    skill = installed_skill(guard.PROTECTED_ROOTS[0], manifest)

    reason = guard.reason_for(skill / "SKILL.md")

    assert reason is not None
    assert ABSENT_TEXT in reason
    assert "installed by" not in reason
    assert SECRET not in reason


def test_refusal_prints_only_the_provenance_fields(guard) -> None:
    manifest = {**MANIFEST, "token": SECRET, "installed_at": f"2026-09-10 {SECRET}"}
    skill = installed_skill(guard.PROTECTED_ROOTS[0], json.dumps(manifest))

    reason = guard.reason_for(skill / "SKILL.md")

    assert reason is not None
    assert OWNER_TEXT in reason
    assert SECRET not in reason
    assert "token" not in reason


def test_refusal_drops_control_characters_from_manifest_fields(guard) -> None:
    manifest = {**MANIFEST, "installed_by": "\x1b[31minstall.sh\x1b[0m\x00 v2"}
    skill = installed_skill(guard.PROTECTED_ROOTS[0], json.dumps(manifest))

    reason = guard.reason_for(skill / "SKILL.md")

    assert reason is not None
    assert "\x1b" not in reason
    assert "\x00" not in reason
    assert (
        "installed by [31minstall.sh[0m v2 from github.com/example/private-skills"
        in reason
    )


def test_symlinked_source_json_counts_as_unreadable(guard, tmp_path: Path) -> None:
    elsewhere = tmp_path / "elsewhere.json"
    elsewhere.write_text(json.dumps(MANIFEST), encoding="utf-8")
    skill = installed_skill(guard.PROTECTED_ROOTS[0], None)
    (skill / ".source.json").symlink_to(elsewhere)

    reason = guard.reason_for(skill / "SKILL.md")

    assert reason is not None
    assert ABSENT_TEXT in reason


@pytest.mark.parametrize("shape", ["symlink", "directory"])
def test_nearest_manifest_of_the_wrong_shape_is_never_attributed_to_an_ancestor(
    guard, tmp_path: Path, shape: str
) -> None:
    group = guard.PROTECTED_ROOTS[1] / "group"
    skill = group / "skill"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# nested\n", encoding="utf-8")
    (group / ".source.json").write_text(
        json.dumps({**MANIFEST, "installed_by": "ANCESTOR-INSTALLER"}), encoding="utf-8"
    )
    if shape == "symlink":
        elsewhere = tmp_path / "elsewhere.json"
        elsewhere.write_text(json.dumps(MANIFEST), encoding="utf-8")
        (skill / ".source.json").symlink_to(elsewhere)
    else:
        (skill / ".source.json").mkdir()

    reason = guard.reason_for(skill / "SKILL.md")

    assert reason is not None
    assert ABSENT_TEXT in reason
    assert "ANCESTOR-INSTALLER" not in reason
    assert "installed by" not in reason


needs_permission_checks = pytest.mark.skipif(
    os.geteuid() == 0, reason="root bypasses directory permission bits"
)


@needs_permission_checks
def test_unreadable_skill_directory_still_blocks_without_raising(guard) -> None:
    skill = installed_skill(guard.PROTECTED_ROOTS[0], json.dumps(MANIFEST))
    artifact = skill / "SKILL.md"
    skill.chmod(0)
    try:
        reason = guard.reason_for(artifact)
    finally:
        skill.chmod(0o755)

    assert reason is not None
    assert reason.startswith(f"{artifact} is an installed skill artifact.")
    assert ABSENT_TEXT in reason
    assert "installed by" not in reason


@needs_permission_checks
@pytest.mark.parametrize("client", ["claude", "codex"])
def test_hook_denies_an_unreadable_skill_directory_instead_of_crashing(
    tmp_path: Path, client: str
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    skill = installed_skill(home / ".claude" / "skills", json.dumps(MANIFEST))
    payload = json.dumps(
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "cwd": str(tmp_path),
            "tool_input": {"file_path": str(skill / "SKILL.md")},
        }
    )
    skill.chmod(0)
    try:
        completed = subprocess.run(
            [sys.executable, "-B", str(GUARD_PATH), "--client", client],
            input=payload,
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "HOME": str(home)},
            cwd=tmp_path,
        )
    finally:
        skill.chmod(0o755)

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip(), "hook emitted no decision"
    decision = json.loads(completed.stdout)
    if client == "claude":
        assert decision["decision"] == "block"
        reason = decision["reason"]
    else:
        assert decision["hookSpecificOutput"]["permissionDecision"] == "deny"
        reason = decision["hookSpecificOutput"]["permissionDecisionReason"]
    assert ABSENT_TEXT in reason


def test_protected_root_itself_has_no_manifest_and_still_blocks(guard) -> None:
    root = guard.PROTECTED_ROOTS[0]
    root.mkdir(parents=True)

    reason = guard.reason_for(root)

    assert reason is not None
    assert ABSENT_TEXT in reason


@pytest.mark.parametrize("client", ["claude", "codex"])
@pytest.mark.parametrize("present", [True, False], ids=["manifest", "no-manifest"])
def test_hook_deny_payload_carries_owner_or_absence(
    tmp_path: Path, client: str, present: bool
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    skill = installed_skill(
        home / ".claude" / "skills", json.dumps(MANIFEST) if present else None
    )
    payload = json.dumps(
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "cwd": str(tmp_path),
            "tool_input": {"file_path": str(skill / "SKILL.md")},
        }
    )
    completed = subprocess.run(
        [sys.executable, "-B", str(GUARD_PATH), "--client", client],
        input=payload,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "HOME": str(home)},
        cwd=tmp_path,
    )

    assert completed.returncode == 0, completed.stderr
    decision = json.loads(completed.stdout)
    if client == "claude":
        assert decision["decision"] == "block"
        reason = decision["reason"]
    else:
        assert decision["hookSpecificOutput"]["permissionDecision"] == "deny"
        reason = decision["hookSpecificOutput"]["permissionDecisionReason"]
    assert (OWNER_TEXT if present else ABSENT_TEXT) in reason

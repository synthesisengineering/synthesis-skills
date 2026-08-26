#!/usr/bin/env python3
"""Deterministic tests for the gated cross-client release script.

Hermetic: no network, no git remotes, no real client binaries. Client presence
is simulated through the documented environment overrides, and every filesystem
fact is built in a temp tree.

The tests that matter most are the fail-closed ones. A release script that
passes when it cannot prove something is worse than no script, because it
converts an unknown into a false assurance.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import release  # noqa: E402


def write_manifests(repo: Path, claude: str | None, codex: str | None) -> None:
    for directory, version in ((".claude-plugin", claude), (".codex-plugin", codex)):
        target = repo / directory
        target.mkdir(parents=True, exist_ok=True)
        payload = {"name": release.PLUGIN_NAME}
        if version is not None:
            payload["version"] = version
        (target / "plugin.json").write_text(json.dumps(payload), encoding="utf-8")


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    write_manifests(tmp_path, "9.9.9", "9.9.9")
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [9.9.9] - 2026-01-01\n\n### Added\n\n- thing\n", encoding="utf-8"
    )
    return tmp_path


# --- source of truth -------------------------------------------------------


def test_source_version_agrees(repo: Path) -> None:
    version, _ = release.source_version(repo)
    assert version == "9.9.9"


def test_source_version_fails_closed_when_manifests_disagree(repo: Path) -> None:
    write_manifests(repo, "9.9.9", "9.9.8")
    version, detail = release.source_version(repo)
    assert version is None
    assert "9.9.8" in detail


def test_source_version_fails_closed_when_a_manifest_lacks_a_version(repo: Path) -> None:
    write_manifests(repo, "9.9.9", None)
    version, _ = release.source_version(repo)
    assert version is None


def test_changelog_top_version_parsed(repo: Path) -> None:
    assert release.changelog_top_version(repo) == "9.9.9"


def test_changelog_mismatch_is_reported(repo: Path) -> None:
    (repo / "CHANGELOG.md").write_text("# Changelog\n\n## [1.0.0] - 2026-01-01\n", encoding="utf-8")
    result = release.Result()
    release.preflight(repo, result, install_only=False)
    names = {s.name: s.ok for s in result.steps}
    assert names["preflight.changelog-matches"] is False


def test_missing_changelog_returns_none(tmp_path: Path) -> None:
    assert release.changelog_top_version(tmp_path) is None


# --- JSON extraction from noisy CLI output ---------------------------------


def test_first_json_skips_leading_noise() -> None:
    assert json.loads(release._first_json('warn: x\n{"installed": []}\n')) == {"installed": []}


def test_first_json_handles_nested_arrays() -> None:
    payload = '[{"id": "a@b", "nested": [1, 2]}]'
    assert json.loads(release._first_json("noise " + payload))[0]["id"] == "a@b"


def test_first_json_returns_empty_when_absent() -> None:
    assert release._first_json("no json here") == ""


def test_required_checks_do_not_depend_on_shell_glob_expansion() -> None:
    """subprocess receives argv directly; wildcard tokens therefore run zero tests."""
    wildcard_arguments = [
        argument
        for _name, command in release.REQUIRED_CHECKS
        for argument in command
        if "*" in argument or "?" in argument or "[" in argument
    ]
    assert wildcard_arguments == []


def test_required_checks_execute_both_transcript_boundaries() -> None:
    commands = {name: command for name, command in release.REQUIRED_CHECKS}
    assert commands["meeting-transcripts.completeness"] == [
        "python3",
        "skills/synthesis-meeting-transcripts/test_verify_transcripts.py",
    ]
    assert commands["meeting-transcripts.primary"] == [
        "python3",
        "skills/synthesis-meeting-transcripts/test_transcript_primary.py",
    ]


def test_required_checks_execute_release_wiring_tests() -> None:
    commands = {name: command for name, command in release.REQUIRED_CHECKS}
    assert commands["pytest.release"] == [
        "python3",
        "-m",
        "pytest",
        "skills/synthesis-skills-manager/scripts/test_release.py",
        "-q",
    ]


def test_repository_ci_executes_release_wiring_tests() -> None:
    repository = Path(__file__).resolve().parents[3]
    workflow = (repository / ".github" / "workflows" / "validate.yml").read_text(
        encoding="utf-8"
    )
    assert (
        "python -m pytest skills/synthesis-skills-manager/scripts/test_release.py -q"
        in workflow
    )


def test_required_checks_execute_r5_integrity_suite() -> None:
    commands = {name: command for name, command in release.REQUIRED_CHECKS}
    assert commands["pytest.context-lifecycle-integrity"] == [
        "python3",
        "-m",
        "pytest",
        "skills/synthesis-context-lifecycle/scripts/",
        "skills/synthesis-implementation-integrity/scripts/",
        "-q",
    ]
    assert commands["acceptance.r5"] == [
        "python3",
        "skills/synthesis-implementation-integrity/scripts/acceptance_suite.py",
        "run",
        "--manifest",
        "skills/synthesis-implementation-integrity/acceptance-suite.yaml",
        "--repo-root",
        ".",
    ]


def test_repository_ci_executes_r5_integrity_suite() -> None:
    repository = Path(__file__).resolve().parents[3]
    workflow = (repository / ".github" / "workflows" / "validate.yml").read_text(
        encoding="utf-8"
    )
    assert (
        "python -m pytest skills/synthesis-context-lifecycle/scripts/ "
        "skills/synthesis-implementation-integrity/scripts/ -q"
        in workflow
    )
    assert (
        "python skills/synthesis-implementation-integrity/scripts/acceptance_suite.py "
        "run --manifest skills/synthesis-implementation-integrity/acceptance-suite.yaml "
        "--repo-root ."
        in workflow
    )


# --- client reporting, fail-closed -----------------------------------------


def test_client_version_none_when_binary_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYNTHESIS_CLAUDE_BIN", "")
    monkeypatch.setattr(release, "resolve_client_binary", lambda name: None)
    assert release.client_reported_version("claude") == (None, None)


def test_deep_verify_fails_when_cli_reports_but_disk_is_stale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The regression that motivated this script.

    A client reporting the intended version while the tree it loads is older
    must FAIL. Reported-only agreement is not a pass.
    """
    stale_root = tmp_path / "loaded"
    (stale_root / ".codex-plugin").mkdir(parents=True)
    (stale_root / ".codex-plugin" / "plugin.json").write_text(
        json.dumps({"version": "4.28.1"}), encoding="utf-8"
    )
    monkeypatch.setattr(
        release, "client_reported_version", lambda client: ("4.30.1", str(stale_root))
    )
    monkeypatch.setattr(release, "installed_root", lambda client, version: tmp_path / "absent")
    result = release.Result()
    assert release.deep_verify("codex", "4.30.1", result) is False
    names = {s.name: s.ok for s in result.steps}
    assert names["verify.codex.reported"] is True
    assert names["verify.codex.on-disk"] is False


def test_deep_verify_passes_when_report_and_disk_agree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "cache" / "4.30.1"
    (root / ".codex-plugin").mkdir(parents=True)
    (root / ".codex-plugin" / "plugin.json").write_text(
        json.dumps({"version": "4.30.1"}), encoding="utf-8"
    )
    monkeypatch.setattr(release, "client_reported_version", lambda client: ("4.30.1", str(root)))
    monkeypatch.setattr(release, "installed_root", lambda client, version: root)
    result = release.Result()
    assert release.deep_verify("codex", "4.30.1", result) is True


def test_deep_verify_fails_when_client_silent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(release, "client_reported_version", lambda client: (None, None))
    monkeypatch.setattr(release, "installed_root", lambda client, version: tmp_path / "nope")
    result = release.Result()
    assert release.deep_verify("claude", "4.30.1", result) is False


# --- install sequencing ----------------------------------------------------


def test_codex_refresh_upgrades_marketplace_before_installing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Codex installs FROM its snapshot, so the upgrade must come first."""
    monkeypatch.setattr(release, "resolve_client_binary", lambda name: "/fake/codex")
    result = release.Result()
    assert release.refresh_client("codex", result, dry_run=True) is True
    details = [s.detail for s in result.steps]
    assert any("marketplace upgrade" in d for d in details)
    upgrade_index = next(i for i, d in enumerate(details) if "marketplace upgrade" in d)
    add_index = next(i for i, d in enumerate(details) if "plugin add" in d)
    assert upgrade_index < add_index


def test_claude_refresh_updates_marketplace_then_plugin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(release, "resolve_client_binary", lambda name: "/fake/claude")
    result = release.Result()
    assert release.refresh_client("claude", result, dry_run=True) is True
    details = [s.detail for s in result.steps]
    assert any("marketplace update" in d for d in details)
    update_index = next(i for i, d in enumerate(details) if "marketplace update" in d)
    plugin_index = next(i for i, d in enumerate(details) if "plugin update" in d)
    assert update_index < plugin_index


def test_refresh_fails_closed_without_binary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(release, "resolve_client_binary", lambda name: None)
    result = release.Result()
    assert release.refresh_client("codex", result, dry_run=True) is False
    assert result.failed


# --- entrypoint guards -----------------------------------------------------


def test_main_refuses_a_plugin_cache_as_repo_root(tmp_path: Path) -> None:
    cache = tmp_path / "plugins" / "cache" / "x"
    (cache / ".claude-plugin").mkdir(parents=True)
    (cache / ".claude-plugin" / "plugin.json").write_text('{"version": "1"}', encoding="utf-8")
    assert release.main(["--repo-root", str(cache), "--check-only"]) == 2


def test_main_refuses_a_non_checkout(tmp_path: Path) -> None:
    assert release.main(["--repo-root", str(tmp_path), "--check-only"]) == 2


def test_main_aborts_on_manifest_disagreement(repo: Path) -> None:
    write_manifests(repo, "9.9.9", "9.9.8")
    assert release.main(["--repo-root", str(repo), "--check-only"]) == 2

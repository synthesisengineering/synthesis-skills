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
import subprocess
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
    assert "acceptance.r5" not in commands


def test_release_boundary_consumes_fresh_bound_acceptance_receipt(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[Path, bool]] = []
    authority = object()

    def consume(candidate: Path, result: release.Result, dry_run: bool) -> object:
        calls.append((candidate, dry_run))
        result.add(
            "checks.acceptance.r5",
            True,
            "fresh transaction-bound receipt consumed",
        )
        return authority

    monkeypatch.setattr(release, "REQUIRED_CHECKS", ())
    monkeypatch.setattr(release, "consume_acceptance", consume)
    result = release.Result()

    assert release.run_required_checks(repo, result, dry_run=False) is authority
    assert calls == [(repo, False)]
    assert [(step.name, step.ok) for step in result.steps] == [
        ("checks.acceptance.r5", True)
    ]


def test_release_receipt_validator_rejects_every_binding_mismatch() -> None:
    expected = {
        "transaction_id": "transaction-a",
        "change_base": "a" * 40,
        "change_head": "b" * 40,
        "head_tree": "c" * 40,
        "manifest_sha256": "d" * 64,
        "changed_paths": ["one.py"],
        "changed_paths_sha256": "e" * 64,
    }
    receipt = {
        **expected,
        "receipt_schema": "acceptance-run-receipt-v1",
        "receipt_consumer": "synthesis-skills-manager.release.consume-acceptance.v1",
        "metadata_class": "acceptance-test",
        "issues_authority_receipt": False,
        "ok": True,
        "coverage": {"declared": 2, "terminal": 2, "not_run": 0},
        "cases": [{"id": "one", "matched": True}, {"id": "two", "matched": True}],
    }

    assert release.validate_acceptance_receipt(receipt, expected)[0]
    for field in expected:
        mutated = dict(receipt)
        mutated[field] = "mismatch"
        assert not release.validate_acceptance_receipt(mutated, expected)[0], field
    for field, value in (
        ("receipt_schema", "wrong"),
        ("receipt_consumer", "wrong"),
        ("metadata_class", "diagnostic"),
        ("issues_authority_receipt", True),
        ("ok", False),
        ("coverage", {"declared": 2, "terminal": 1, "not_run": 1}),
        ("cases", [{"id": "one", "matched": False}]),
    ):
        mutated = dict(receipt)
        mutated[field] = value
        assert not release.validate_acceptance_receipt(mutated, expected)[0], field


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
    assert "python skills/synthesis-skills-manager/scripts/release.py --repo-root . --acceptance-only" in workflow


def test_repository_ci_uses_receipt_consumer_with_authoritative_base() -> None:
    repository = Path(__file__).resolve().parents[3]
    workflow = (repository / ".github" / "workflows" / "validate.yml").read_text(
        encoding="utf-8"
    )
    assert "SYNTHESIS_ACCEPTANCE_CHANGE_BASE:" in workflow
    assert "github.event.pull_request.base.sha || github.event.before" in workflow


# AGENT HEURISTIC: these fixtures preserve the direct reviewer's concrete D4
# counterexample. A receipt that expires before publish is not release authority.
def accepted_publish_fixture(tmp_path: Path) -> tuple[Path, object]:
    repository = tmp_path / "repository"
    repository.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(repository)], check=True)
    for key, value in (
        ("user.name", "Release Fixture"),
        ("user.email", "release@example.invalid"),
        ("core.hooksPath", "/dev/null"),
    ):
        subprocess.run(
            ["git", "-C", str(repository), "config", key, value], check=True
        )
    manifest = repository / release.ACCEPTANCE_MANIFEST
    manifest.parent.mkdir(parents=True)
    manifest.write_text("fixture manifest\n", encoding="utf-8")
    changed = repository / "production.py"
    changed.write_text("BASE = True\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repository), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(repository), "commit", "-qm", "base"], check=True
    )
    base = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    changed.write_text("ACCEPTED = True\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repository), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(repository), "commit", "-qm", "accepted"], check=True
    )
    expected, detail = release.acceptance_expectation(
        repository, base, "fixture-transaction"
    )
    assert expected is not None, detail
    receipt = {
        **expected,
        "receipt_schema": "acceptance-run-receipt-v1",
        "receipt_consumer": release.ACCEPTANCE_CONSUMER_ID,
        "metadata_class": "acceptance-test",
        "issues_authority_receipt": False,
        "ok": True,
        "coverage": {"declared": 1, "terminal": 1, "not_run": 0},
        "cases": [{"id": "fixture", "matched": True}],
    }
    authority = release.AcceptanceAuthority(
        change_base=base, expected=expected, receipt=receipt
    )
    return repository, authority


def test_publish_refuses_when_receipt_bound_head_changes(tmp_path: Path) -> None:
    repository, authority = accepted_publish_fixture(tmp_path)
    (repository / "undeclared.py").write_text("raise RuntimeError\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repository), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(repository), "commit", "-qm", "changed"], check=True
    )

    result = release.Result()
    assert release.publish(repository, result, True, authority) is False
    assert any(
        step.name == "publish.acceptance" and not step.ok for step in result.steps
    )


def test_publish_dry_run_names_exact_receipt_bound_ref(tmp_path: Path) -> None:
    repository, authority = accepted_publish_fixture(tmp_path)
    bare = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
    subprocess.run(
        ["git", "-C", str(repository), "remote", "add", "origin", str(bare)],
        check=True,
    )

    result = release.Result()
    assert release.publish(repository, result, True, authority) is True
    expected_ref = f"{authority.expected['change_head']}:refs/heads/main"
    assert any(
        step.name == "publish.push.origin" and expected_ref in step.detail
        for step in result.steps
    )


def test_main_carries_acceptance_authority_to_publish_boundary(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    authority = object()
    received: list[object] = []

    monkeypatch.setattr(release, "preflight", lambda *_args: "9.9.9")
    monkeypatch.setattr(
        release, "run_required_checks", lambda *_args: authority
    )

    def publish(
        candidate: Path,
        result: release.Result,
        dry_run: bool,
        accepted: object,
    ) -> bool:
        received.append(accepted)
        return result.add("publish.fixture", True)

    monkeypatch.setattr(release, "publish", publish)
    monkeypatch.setattr(release, "refresh_client", lambda *_args: True)

    assert release.main(["--repo-root", str(repo), "--dry-run"]) == 0
    assert received == [authority]


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

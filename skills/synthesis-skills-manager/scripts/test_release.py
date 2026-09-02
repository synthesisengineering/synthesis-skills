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
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

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


@pytest.fixture(autouse=True)
def no_real_cache_settle_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(release, "CODEX_CACHE_QUIET_SECONDS", 0.0)


@pytest.fixture(autouse=True)
def hermetic_release_train(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Keep the suite off the developer's real coordination board and
    session identity; train tests point at their own fixtures."""
    monkeypatch.setenv(
        "SYNTHESIS_COORDINATION_BOARD", str(tmp_path / "absent-board.md")
    )
    monkeypatch.delenv("SYNTHESIS_COORDINATION_SESSION", raising=False)
    monkeypatch.setenv(
        "SYNTHESIS_ACTIVE_PROJECT_FILE", str(tmp_path / "absent-pointer.json")
    )


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


def _install_root(tmp_path: Path, version: str) -> Path:
    root = tmp_path / "cache" / version
    (root / ".claude-plugin").mkdir(parents=True)
    (root / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"version": version}), encoding="utf-8"
    )
    return root


def test_stable_path_points_at_the_verified_install_root(tmp_path, monkeypatch) -> None:
    """Instruction files pin the stable path; it must follow every verified
    release atomically and never point at an unverified tree."""
    monkeypatch.setattr(release, "STABLE_ROOT", tmp_path / "plugins")
    first = _install_root(tmp_path, "4.82.0")
    assert release.refresh_stable_path("4.82.0", release.Result(), False, target=first)
    link = release.stable_path()
    assert link.is_symlink()
    assert Path(os.path.realpath(link)) == first.resolve()

    second = _install_root(tmp_path, "4.83.0")
    assert release.refresh_stable_path("4.83.0", release.Result(), False, target=second)
    assert Path(os.path.realpath(link)) == second.resolve()
    assert not link.with_name(link.name + ".tmp").exists()


def test_stable_path_refuses_an_unverified_or_mismatched_root(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(release, "STABLE_ROOT", tmp_path / "plugins")
    bare = tmp_path / "cache" / "4.82.0"
    bare.mkdir(parents=True)
    result = release.Result()
    assert not release.refresh_stable_path("4.82.0", result, False, target=bare)
    assert not release.stable_path().exists()

    other = _install_root(tmp_path, "4.81.0")
    assert not release.refresh_stable_path("4.82.0", release.Result(), False, target=other)
    assert not release.stable_path().exists()


def test_stable_path_doc_states_the_two_caller_rule() -> None:
    """Instruction files pin the installed pointer; hooks resolve from source.
    A rule nobody wrote down gets re-decided per session."""
    text = (Path(__file__).resolve().parents[1] / "SKILL.md").read_text(encoding="utf-8")
    assert "## The stable path" in text
    assert "Two kinds of caller, two paths" in text
    assert "parity.stable-path" in text


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


def test_required_checks_execute_whole_system_onboarding_contract() -> None:
    commands = {name: command for name, command in release.REQUIRED_CHECKS}
    assert commands["pytest.onboarding"] == [
        "python3",
        "-m",
        "pytest",
        "skills/synthesis-onboarding/scripts/test_onboard.py",
        "-q",
    ]
    assert commands["onboarding.catalog-scaffolds"] == [
        "python3",
        "skills/synthesis-onboarding/scripts/check_scaffolds.py",
        ".",
    ]


# --- release-train serialization (2026-09-01) -------------------------------
#
# Five same-day overtakes between two parallel releasing sessions, one
# version-number collision. The train is a virtual coordination-board claim;
# holding it is verified here, at the boundary both sessions already run.

TRAIN_UUID = "01a05e00-0000-7000-8000-000000000001"
OTHER_UUID = "01a05e00-0000-7000-8000-000000000002"


def train_board(tmp_path: Path, rows: list[tuple[str, str, str]]) -> Path:
    header = (
        "| session uuid | compact id | speakable id v1 | legacy id | agent | "
        "machine | client session ref | project | started | heartbeat | mode | "
        "workspace(s) / branch | goal | claimed areas (advisory lock) | "
        "context role | status |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
    )
    body = "".join(
        f"| {uuid} | s-x | a-b-c-d-00001 |  | Agent | m1 | - | proj | t | t | "
        f"interactive | w | g | {claims} | owner | {status} |\n"
        for uuid, claims, status in rows
    )
    board = tmp_path / "board.md"
    board.write_text(
        "# Coordination\n\nSchema: v4\n\n## Active sessions\n\n"
        + header + body + "\n## Messages\n\n---\n\n## Protocol\n",
        encoding="utf-8",
    )
    return board


def run_train_check(
    monkeypatch: pytest.MonkeyPatch, board: Path | None, selector: str | None
) -> release.Step:
    if board is not None:
        monkeypatch.setenv("SYNTHESIS_COORDINATION_BOARD", str(board))
    if selector is not None:
        monkeypatch.setenv("SYNTHESIS_COORDINATION_SESSION", selector)
    result = release.Result()
    release.train_check(result)
    (step,) = [s for s in result.steps if s.name == "preflight.release-train"]
    return step


def test_train_not_adopted_without_a_board(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    step = run_train_check(monkeypatch, None, None)
    assert step.ok and "not adopted" in step.detail


def test_train_held_by_this_session_passes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    board = train_board(
        tmp_path, [(TRAIN_UUID, release.TRAIN_RESOURCE, "active")]
    )
    step = run_train_check(monkeypatch, board, TRAIN_UUID)
    assert step.ok and "held by this session" in step.detail


def test_train_held_by_peer_refuses(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    board = train_board(
        tmp_path, [(OTHER_UUID, release.TRAIN_RESOURCE, "active")]
    )
    step = run_train_check(monkeypatch, board, TRAIN_UUID)
    assert not step.ok and "not this session" in step.detail


def test_train_unheld_refuses_with_claim_guidance(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    board = train_board(tmp_path, [(OTHER_UUID, "some/path/**", "active")])
    step = run_train_check(monkeypatch, board, TRAIN_UUID)
    assert not step.ok and "claim it before" in step.detail


def test_train_released_holder_does_not_count(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    board = train_board(
        tmp_path, [(OTHER_UUID, release.TRAIN_RESOURCE, "released")]
    )
    step = run_train_check(monkeypatch, board, TRAIN_UUID)
    assert not step.ok and "claim it before" in step.detail


def test_train_held_without_local_identity_refuses(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    board = train_board(
        tmp_path, [(OTHER_UUID, release.TRAIN_RESOURCE, "active")]
    )
    step = run_train_check(monkeypatch, board, None)
    assert not step.ok and "no session identity" in step.detail


def test_train_token_conflicts_with_itself_but_not_with_paths() -> None:
    """The virtual resource rides the unmodified claim-overlap machinery:
    identical tokens conflict (the lock), ordinary path claims do not
    (no false positives)."""
    sys.path.insert(
        0,
        str(
            Path(release.__file__).resolve().parents[2]
            / "synthesis-project-management"
            / "scripts"
        ),
    )
    import coordination

    assert coordination.overlaps(release.TRAIN_RESOURCE, release.TRAIN_RESOURCE)
    assert not coordination.overlaps(
        release.TRAIN_RESOURCE, "/repos/synthesis-skills/skills/**"
    )
    assert not coordination.overlaps(
        "ai-knowledge-demo/projects/**", release.TRAIN_RESOURCE
    )


def test_agents_verification_list_matches_ci_workflow() -> None:
    """2026-09-01: a locally-green branch failed CI because validate.yml had
    grown five steps beyond AGENTS.md's documented Verification list. The
    fenced list and the conformance job now move together, or this fails.
    Excluded by design: the CI-only dependency install and the env-bound
    acceptance step (documented under Releases instead)."""
    repository = Path(__file__).resolve().parents[3]
    workflow = yaml.safe_load(
        (repository / ".github" / "workflows" / "validate.yml").read_text(
            encoding="utf-8"
        )
    )
    ci_steps = [
        step["run"].strip()
        for step in workflow["jobs"]["conformance"]["steps"]
        if "run" in step
        and "pip install" not in step["run"]
        and "--acceptance-only" not in step["run"]
    ]
    normalized_ci = [
        "python3 " + command[len("python "):]
        if command.startswith("python ")
        else command
        for command in ci_steps
    ]
    agents = (repository / "AGENTS.md").read_text(encoding="utf-8")
    section = agents.split("## Verification", 1)[1].split(
        "For a cross-client release", 1
    )[0]
    fence = re.search(r"```bash\n(.*?)```", section, re.S).group(1)
    documented = [line.strip() for line in fence.splitlines() if line.strip()]
    assert documented == normalized_ci, (
        "AGENTS.md Verification fence and validate.yml conformance steps "
        "drifted; change them together.\ndocumented=%r\nci=%r"
        % (documented, normalized_ci)
    )


def test_repository_ci_executes_release_wiring_tests() -> None:
    repository = Path(__file__).resolve().parents[3]
    workflow = (repository / ".github" / "workflows" / "validate.yml").read_text(
        encoding="utf-8"
    )

    assert "python skills/synthesis-onboarding/scripts/check_scaffolds.py ." in workflow
    assert "ubuntu-latest, macos-latest" in workflow
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


def test_repository_ci_fetches_authoritative_base_history() -> None:
    repository = Path(__file__).resolve().parents[3]
    workflow = yaml.safe_load(
        (repository / ".github" / "workflows" / "validate.yml").read_text(
            encoding="utf-8"
        )
    )
    checkout = next(
        step
        for step in workflow["jobs"]["conformance"]["steps"]
        if step.get("uses") == "actions/checkout@v4"
    )
    assert checkout["with"]["fetch-depth"] == 0


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
    assert release.publish(repository, result, True, authority, "9.9.9") is False
    assert any(
        step.name == "publish.acceptance" and not step.ok for step in result.steps
    )


def test_publish_dry_run_names_exact_receipt_bound_channel_and_pin_refs(
    tmp_path: Path,
) -> None:
    repository, authority = accepted_publish_fixture(tmp_path)
    bare = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
    subprocess.run(
        ["git", "-C", str(repository), "remote", "add", "origin", str(bare)],
        check=True,
    )

    result = release.Result()
    assert release.publish(repository, result, True, authority, "9.9.9") is True
    detail = next(
        step.detail for step in result.steps if step.name == "publish.push.origin"
    )
    accepted = authority.expected["change_head"]
    assert "atomic" in detail
    assert f"{accepted}:refs/heads/main" in detail
    assert f"{accepted}:refs/heads/stable" in detail
    assert f"{accepted}:refs/tags/v9.9.9" in detail


def test_publish_atomically_creates_edge_stable_and_version_pin_refs(
    tmp_path: Path,
) -> None:
    repository, authority = accepted_publish_fixture(tmp_path)
    bare = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
    subprocess.run(
        ["git", "-C", str(repository), "remote", "add", "origin", str(bare)],
        check=True,
    )

    result = release.Result()
    assert release.publish(repository, result, False, authority, "9.9.9") is True
    accepted = authority.expected["change_head"]
    for ref in ("refs/heads/main", "refs/heads/stable", "refs/tags/v9.9.9"):
        actual = subprocess.run(
            ["git", "-C", str(bare), "rev-parse", ref],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        assert actual == accepted


def test_publish_rejects_non_exact_version_tag(tmp_path: Path) -> None:
    repository, authority = accepted_publish_fixture(tmp_path)
    result = release.Result()

    assert release.publish(repository, result, True, authority, "latest") is False
    assert any(
        step.name == "publish.version-tag" and not step.ok for step in result.steps
    )


def test_release_manager_documents_channel_ref_contract() -> None:
    repository = Path(__file__).resolve().parents[3]
    text = (repository / "skills/synthesis-skills-manager/SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "refs/heads/main" in text
    assert "refs/heads/stable" in text
    assert "refs/tags/vX.Y.Z" in text
    assert "atomic" in text


def test_lifecycle_hotfix_is_documented_on_every_public_maintenance_surface() -> None:
    repository = Path(__file__).resolve().parents[3]
    manager = (repository / "skills/synthesis-skills-manager/SKILL.md").read_text(
        encoding="utf-8"
    )
    onboarding = (repository / "skills/synthesis-onboarding/SKILL.md").read_text(
        encoding="utf-8"
    )
    readme = (repository / "README.md").read_text(encoding="utf-8")
    assert "snapshots" in manager and "versioned cache root" in manager
    assert "operating-system CA bundle" in onboarding
    assert "4.74.1" in readme
    assert "full TLS and" in readme


def test_cache_survival_release_contract_is_public_and_coherent() -> None:
    repository = Path(__file__).resolve().parents[3]
    manager = (repository / "skills/synthesis-skills-manager/SKILL.md").read_text(
        encoding="utf-8"
    )
    readme = (repository / "README.md").read_text(encoding="utf-8")
    changelog = (repository / "CHANGELOG.md").read_text(encoding="utf-8")

    assert "every archived version except the newest" in manager
    assert "single-writer transition lock" in readme
    assert "pre-tag" in readme
    assert "## [4.76.4]" in changelog
    assert "client-owned metadata" in manager
    assert "512 MiB hard limit" in changelog
    assert readme.count("**4.76.1**") == 1
    assert changelog.count("## [4.76.1]") == 1


def test_delayed_cache_guardian_release_contract_is_public_and_coherent() -> None:
    repository = Path(__file__).resolve().parents[3]
    manager = (repository / "skills/synthesis-skills-manager/SKILL.md").read_text(
        encoding="utf-8"
    )
    guardian = (repository / release.CACHE_GUARDIAN).read_text(encoding="utf-8")
    readme = (repository / "README.md").read_text(encoding="utf-8")
    changelog = (repository / "CHANGELOG.md").read_text(encoding="utf-8")

    assert "Version 2.5.0" in manager
    assert "outside the client-owned cache" in manager
    assert "current_excluded" in guardian
    assert "KeepAlive" in guardian and "Restart=always" in guardian
    assert "4.77.1" in readme
    assert "## [4.77.1]" in changelog


def test_whole_system_onboarding_release_contract_is_public_and_coherent() -> None:
    repository = Path(__file__).resolve().parents[3]
    onboarding = (repository / "skills/synthesis-onboarding/SKILL.md").read_text(
        encoding="utf-8"
    )
    readme = (repository / "README.md").read_text(encoding="utf-8")
    bootstrap = (repository / "onboard.sh").read_text(encoding="utf-8")
    org_manifest = (
        repository / "skills/synthesis-onboarding/references/org-manifest.md"
    ).read_text(encoding="utf-8")
    manager = (
        repository / "skills/synthesis-skills-manager/SKILL.md"
    ).read_text(encoding="utf-8")
    versions = {
        json.loads((repository / path).read_text(encoding="utf-8"))["version"]
        for path in release.MANIFESTS
    }
    # One agreed version, well-formed — pinning the shipping literal here
    # broke the first branch that bumped the manifests.
    assert len(versions) == 1, versions
    (version,) = versions
    assert all(part.isdigit() for part in version.split(".")), version
    assert version.count(".") == 2, version
    assert "set -- init" in bootstrap
    assert "eleven layers" in readme
    assert "Skills-only alternative" in readme
    assert "stable PostToolUse hook" in onboarding
    assert "git_name" in onboarding and "repository, never globally" in onboarding
    assert "does not change global Git configuration" in readme
    assert "default_branch" in org_manifest
    assert "whole-system onboarding suite" in manager


def test_quick_answers_skill_release_contract_is_public_and_coherent() -> None:
    repository = Path(__file__).resolve().parents[3]
    skill = (
        repository / "skills/synthesis-quick-answers/SKILL.md"
    ).read_text(encoding="utf-8")
    readme = (repository / "README.md").read_text(encoding="utf-8")
    changelog = (repository / "CHANGELOG.md").read_text(encoding="utf-8")
    components = json.loads(
        (
            repository
            / "skills/synthesis-onboarding/references/components.json"
        ).read_text(encoding="utf-8")
    )

    assert "synthesis-quick-answers" in readme
    assert "## [4.86.0]" in changelog
    assert "synthesis-quick-answers" in changelog
    assert "synthesis-quick-answers" in components["skills"]
    # The defining feature this transaction adds: every answer states its
    # source and one of these three tiers, never silently.
    assert "Verified" in skill and "Cached" in skill and "Uncertain" in skill
    assert "synthesis-grounding-discipline" in skill
    assert "cache-vs-truth" in skill


def test_quick_answers_self_bootstrap_release_contract_is_public_and_coherent() -> None:
    repository = Path(__file__).resolve().parents[3]
    skill = (
        repository / "skills/synthesis-quick-answers/SKILL.md"
    ).read_text(encoding="utf-8")
    onboard = (
        repository / "skills/synthesis-onboarding/scripts/onboard.py"
    ).read_text(encoding="utf-8")
    changelog = (repository / "CHANGELOG.md").read_text(encoding="utf-8")

    assert "## [4.87.0]" in changelog
    assert "v1.2.0" in changelog
    # Setup no longer assumes a personal knowledge workspace already exists,
    # and no longer leaves "automatic" as an unstated implementation detail.
    assert "onboard.py init-workspace" in skill
    assert "AGENTS.md" in skill and "CLAUDE.md" in skill
    assert "synthesis-onboarding" in skill
    # The receipt-verification sentence that reads as internal agent protocol
    # to a human running the installer directly is gone from onboard.py's
    # printed messages; the fuller protocol stays documented in this skill's
    # own SKILL.md (a human never reads that file mid-install, only an agent
    # consulting it as instructions does), so nothing about agent behavior
    # regressed — only what a person sees in their own terminal changed.
    assert "verify its exact current-plugin SessionStart receipt" not in onboard
    assert "start a new chat there" in onboard


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
        version: str,
    ) -> bool:
        received.append((accepted, version))
        return result.add("publish.fixture", True)

    monkeypatch.setattr(release, "publish", publish)
    monkeypatch.setattr(release, "refresh_client", lambda *_args, **_kwargs: True)

    assert release.main(["--repo-root", str(repo), "--dry-run"]) == 0
    assert received == [(authority, "9.9.9")]


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


def _seed_content(source: Path, installed: Path, drift: bool = False) -> None:
    for base in (source, installed):
        (base / "skills" / "demo" / "scripts").mkdir(parents=True, exist_ok=True)
        (base / "skills" / "demo" / "SKILL.md").write_text("# demo\n", encoding="utf-8")
        (base / "skills" / "demo" / "scripts" / "tool.py").write_text(
            "print('v2')\n", encoding="utf-8")
    if drift:
        (installed / "skills" / "demo" / "scripts" / "tool.py").write_text(
            "print('v1-stale')\n", encoding="utf-8")


def test_deep_verify_passes_when_report_disk_and_content_agree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "cache" / "4.30.1"
    source = tmp_path / "source"
    (root / ".codex-plugin").mkdir(parents=True)
    (root / ".codex-plugin" / "plugin.json").write_text(
        json.dumps({"version": "4.30.1"}), encoding="utf-8"
    )
    _seed_content(source, root)
    monkeypatch.setattr(release, "client_reported_version", lambda client: ("4.30.1", str(root)))
    monkeypatch.setattr(release, "installed_root", lambda client, version: root)
    result = release.Result()
    assert release.deep_verify("codex", "4.30.1", result, repo=source) is True


def test_deep_verify_fails_on_content_drift_despite_version_parity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The 2026-08-24 false-green: versions equal everywhere, installed
    bytes stale. Version parity is not content parity."""
    root = tmp_path / "cache" / "4.30.1"
    source = tmp_path / "source"
    (root / ".codex-plugin").mkdir(parents=True)
    (root / ".codex-plugin" / "plugin.json").write_text(
        json.dumps({"version": "4.30.1"}), encoding="utf-8"
    )
    _seed_content(source, root, drift=True)
    monkeypatch.setattr(release, "client_reported_version", lambda client: ("4.30.1", str(root)))
    monkeypatch.setattr(release, "installed_root", lambda client, version: root)
    result = release.Result()
    assert release.deep_verify("codex", "4.30.1", result, repo=source) is False
    names = {s.name: s.ok for s in result.steps}
    assert names["verify.codex.on-disk"] is True
    assert names["verify.codex.content"] is False


def test_deep_verify_fails_closed_without_source_repo(
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
    assert release.deep_verify("codex", "4.30.1", result) is False


def test_deep_verify_fails_when_client_silent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(release, "client_reported_version", lambda client: (None, None))
    monkeypatch.setattr(release, "installed_root", lambda client, version: tmp_path / "nope")
    result = release.Result()
    assert release.deep_verify("claude", "4.30.1", result) is False


def test_recovery_digest_ignores_client_metadata_but_rejects_unknown_extras(
    tmp_path: Path,
) -> None:
    expected = tmp_path / "expected"
    installed = tmp_path / "installed"
    (expected / "skills/example").mkdir(parents=True)
    (expected / "skills/example/SKILL.md").write_text(
        "name: example\n", encoding="utf-8"
    )
    shutil.copytree(expected, installed)
    (installed / ".git").mkdir()
    (installed / ".git/config").write_text("[core]\n", encoding="utf-8")
    (installed / ".in_use").mkdir()
    (installed / ".in_use/123").touch()
    (installed / ".codex-marketplace-install.json").write_text(
        '{"revision":"fixture"}\n', encoding="utf-8"
    )

    assert release._tree_digest(expected) == release._tree_digest(installed)

    (installed / "unexpected").write_text("unowned\n", encoding="utf-8")
    assert release._tree_digest(expected) != release._tree_digest(installed)


# --- install sequencing ----------------------------------------------------


def commit_release(repo: Path, version: str, marker: str) -> None:
    write_manifests(repo, version, version)
    skill = repo / "skills" / "example" / "SKILL.md"
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text(f"version: {version}\n{marker}\n", encoding="utf-8")
    if not (repo / ".git").is_dir():
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    tree = subprocess.run(
        ["git", "write-tree"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    parent = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    commit_command = [
        "git",
        "-c",
        "user.name=Release Test",
        "-c",
        "user.email=release-test@example.invalid",
        "commit-tree",
        tree,
    ]
    if parent.returncode == 0:
        commit_command.extend(["-p", parent.stdout.strip()])
    commit = subprocess.run(
        commit_command,
        cwd=repo,
        check=True,
        capture_output=True,
        input=f"Release {version}\n",
        text=True,
    ).stdout.strip()
    branch = subprocess.run(
        ["git", "symbolic-ref", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    subprocess.run(
        [
            "git",
            "update-ref",
            branch,
            commit,
        ],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "update-ref", f"refs/tags/v{version}", commit],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def seed_complete_cache_root(root: Path, version: str) -> None:
    write_manifests(root, version, version)
    target = root / "skills" / "synthesis-autopilot" / "scripts" / "autopilot_gate.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("print('gate')\n", encoding="utf-8")
    (target.parents[1] / "SKILL.md").write_text(
        f"---\nname: synthesis-autopilot\nversion: {version}\n---\n",
        encoding="utf-8",
    )
    hooks = root / "hooks" / "hooks.json"
    hooks.parent.mkdir(parents=True, exist_ok=True)
    hooks.write_text(
        json.dumps(
            {
                "hooks": {
                    "Stop": [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": (
                                        "python3 ${CLAUDE_PLUGIN_ROOT}/skills/"
                                        "synthesis-autopilot/scripts/autopilot_gate.py --gate"
                                    ),
                                }
                            ]
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )


def test_tag_backed_snapshot_repairs_partial_and_missing_historical_roots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    commit_release(source, "4.74.0", "first")
    commit_release(source, "4.74.1", "middle")
    commit_release(source, "4.75.0", "current")
    subprocess.run(
        ["git", "update-ref", "-d", "refs/tags/v4.75.0"],
        cwd=source,
        check=True,
        capture_output=True,
    )

    cache_parent = tmp_path / "codex-cache"
    partial = cache_parent / "4.74.0"
    partial.mkdir(parents=True)
    (partial / ".codex-marketplace-install.json").write_text(
        "{}\n", encoding="utf-8"
    )
    (partial / "unowned-cache-file").write_text("discard\n", encoding="utf-8")
    newest = cache_parent / "4.75.0"
    newest.mkdir(parents=True)
    recovery = tmp_path / "recovery"
    monkeypatch.setattr(release, "plugin_cache_parent", lambda client: cache_parent)
    monkeypatch.setattr(release, "codex_cache_archive", lambda: recovery)

    result = release.Result()
    snapshot = release.snapshot_codex_caches(result, repo=source)

    assert snapshot is not None
    assert snapshot.versions == ("4.74.0", "4.74.1", "4.75.0")
    assert (snapshot.backup / "4.74.0" / ".codex-plugin/plugin.json").is_file()
    assert (
        snapshot.backup / "4.74.0" / ".codex-marketplace-install.json"
    ).is_file()
    assert not (snapshot.backup / "4.74.0" / "unowned-cache-file").exists()
    assert (
        snapshot.backup / "4.74.1" / "skills/example/SKILL.md"
    ).read_text(encoding="utf-8") == "version: 4.74.1\nmiddle\n"
    assert release._tree_digest(snapshot.backup / "4.74.1") == release._tree_digest(
        recovery / "4.74.1"
    )
    assert next(
        step for step in result.steps if step.name == "install.codex.cache-archive"
    ).ok


def test_snapshot_imports_complete_untagged_peer_root_missing_from_codex(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    commit_release(source, "4.74.0", "tagged")
    codex_cache = tmp_path / "codex-cache"
    (codex_cache / "4.74.0").mkdir(parents=True)
    claude_cache = tmp_path / "claude-cache"
    peer = claude_cache / "4.73.0"
    seed_complete_cache_root(peer, "4.73.0")
    (peer / ".in_use").mkdir()
    (peer / ".in_use" / "123").touch()
    recovery = tmp_path / "recovery"

    monkeypatch.setattr(
        release,
        "plugin_cache_parent",
        lambda client: claude_cache if client == "claude" else codex_cache,
    )
    monkeypatch.setattr(release, "codex_cache_archive", lambda: recovery)

    result = release.Result()
    snapshot = release.snapshot_codex_caches(result, repo=source)

    assert snapshot is not None
    assert snapshot.versions == ("4.73.0", "4.74.0")
    recovered = snapshot.backup / "4.73.0"
    assert (recovered / "skills/synthesis-autopilot/scripts/autopilot_gate.py").is_file()
    assert not (recovered / ".in_use").exists()
    assert release.restore_codex_caches(snapshot, result)
    assert (
        codex_cache / "4.73.0/skills/synthesis-autopilot/scripts/autopilot_gate.py"
    ).is_file()


def test_snapshot_rejects_incomplete_untagged_peer_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    commit_release(source, "4.74.0", "tagged")
    codex_cache = tmp_path / "codex-cache"
    (codex_cache / "4.74.0").mkdir(parents=True)
    claude_cache = tmp_path / "claude-cache"
    peer = claude_cache / "4.73.0"
    seed_complete_cache_root(peer, "4.73.0")
    (peer / "skills/synthesis-autopilot/scripts/autopilot_gate.py").unlink()

    monkeypatch.setattr(
        release,
        "plugin_cache_parent",
        lambda client: claude_cache if client == "claude" else codex_cache,
    )
    monkeypatch.setattr(
        release, "codex_cache_archive", lambda: tmp_path / "recovery"
    )

    result = release.Result()
    assert release.snapshot_codex_caches(result, repo=source) is None
    failure = next(
        step for step in result.steps if step.name == "install.codex.cache-snapshot"
    )
    assert failure.ok is False
    assert "missing hook target" in failure.detail


def test_untagged_peer_root_rejects_unsafe_symlink(tmp_path: Path) -> None:
    root = tmp_path / "4.73.0"
    seed_complete_cache_root(root, "4.73.0")
    (root / "unsafe").symlink_to("../../outside")

    complete, detail = release._cache_root_completeness(root, "4.73.0")

    assert complete is False
    assert "unsafe symlink" in detail


def test_restore_repeats_after_post_command_cache_deletion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_parent = tmp_path / "codex-cache"
    old_root = cache_parent / "4.74.0"
    old_root.mkdir(parents=True)
    (old_root / "marker").write_text("complete\n", encoding="utf-8")
    backup = tmp_path / "synthesis-codex-cache-fixture"
    shutil.copytree(old_root, backup / "4.74.0")
    snapshot = release.CodexCacheSnapshot(backup, ("4.74.0",))
    monkeypatch.setattr(release, "plugin_cache_parent", lambda client: cache_parent)
    monkeypatch.setattr(release, "CODEX_CACHE_QUIET_SECONDS", 2.0)
    monkeypatch.setattr(release, "CODEX_CACHE_SETTLE_TIMEOUT_SECONDS", 10.0)
    monkeypatch.setattr(release, "CODEX_CACHE_POLL_SECONDS", 1.0)
    monkeypatch.setattr(
        release, "_remove_transition_backup", lambda path: shutil.rmtree(path)
    )

    class Clock:
        now = 0.0
        deleted = False

        def read(self) -> float:
            return self.now

        def sleep(self, seconds: float) -> None:
            self.now += seconds
            if not self.deleted:
                shutil.rmtree(old_root)
                self.deleted = True

    clock = Clock()
    result = release.Result()
    assert release.restore_codex_caches(
        snapshot, result, clock=clock.read, sleeper=clock.sleep
    )
    assert (old_root / "marker").read_text(encoding="utf-8") == "complete\n"
    detail = next(
        step.detail
        for step in result.steps
        if step.name == "install.codex.cache-restore"
    )
    assert "restored 1" in detail


def test_tag_backed_snapshot_refuses_archive_budget_overflow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    commit_release(source, "4.74.0", "content larger than one byte")
    cache_parent = tmp_path / "codex-cache"
    (cache_parent / "4.74.0").mkdir(parents=True)
    monkeypatch.setattr(release, "plugin_cache_parent", lambda client: cache_parent)
    monkeypatch.setattr(release, "codex_cache_archive", lambda: tmp_path / "recovery")
    monkeypatch.setattr(release, "CODEX_CACHE_ARCHIVE_BUDGET_BYTES", 1)

    result = release.Result()
    assert release.snapshot_codex_caches(result, repo=source) is None
    failure = next(
        step for step in result.steps if step.name == "install.codex.cache-snapshot"
    )
    assert failure.ok is False
    assert "hard budget" in failure.detail


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


def test_codex_cache_transition_lock_refuses_a_second_writer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        release, "codex_cache_archive", lambda: tmp_path / "recovery" / "plugin"
    )
    first = release._acquire_codex_cache_lock()
    try:
        with pytest.raises(OSError, match="another release process"):
            release._acquire_codex_cache_lock()
    finally:
        release._release_codex_cache_lock(first)


def test_guardian_install_uses_source_checkout_and_surfaces_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / release.CACHE_GUARDIAN
    source.parent.mkdir(parents=True)
    source.write_text("print('guardian')\n", encoding="utf-8")
    calls: list[tuple[list[str], Path | None, int]] = []

    def fake_run(command, cwd=None, timeout=900):
        calls.append((command, cwd, timeout))
        return subprocess.CompletedProcess(
            command, 0, stdout='{"verified": 61}\n', stderr=""
        )

    monkeypatch.setattr(release, "run", fake_run)
    result = release.Result()

    assert release.install_codex_cache_guardian(tmp_path, result, False)
    assert calls == [
        ([sys.executable, str(source), "--install"], tmp_path, 120)
    ]
    step = next(
        step for step in result.steps if step.name == "install.codex.cache-guardian"
    )
    assert step.ok is True
    assert step.detail == '{"verified": 61}'


def test_guardian_install_fails_closed_without_source(tmp_path: Path) -> None:
    result = release.Result()

    assert release.install_codex_cache_guardian(tmp_path, result, False) is False
    assert result.failed[0].name == "install.codex.cache-guardian"


def test_codex_refresh_restores_real_version_root_deleted_by_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_parent = tmp_path / "codex-cache"
    old_root = cache_parent / "4.74.0"
    (old_root / "hooks").mkdir(parents=True)
    (old_root / "hooks" / "hooks.json").write_text("old hook bytes\n", encoding="utf-8")
    recovery_link = cache_parent / "4.73.0"
    recovery_link.symlink_to(old_root)

    monkeypatch.setattr(release, "plugin_cache_parent", lambda client: cache_parent)
    monkeypatch.setattr(release, "resolve_client_binary", lambda name: "/fake/codex")

    def run(command, **_kwargs):
        if command[1:3] == ["plugin", "add"]:
            shutil.rmtree(old_root)
            recovery_link.unlink()
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(release, "run", run)
    result = release.Result()
    assert release.refresh_client("codex", result, dry_run=False) is True
    assert (old_root / "hooks" / "hooks.json").read_text(encoding="utf-8") == "old hook bytes\n"
    assert not recovery_link.exists()
    steps = {step.name: step for step in result.steps}
    assert steps["install.codex.cache-snapshot"].ok is True
    assert "1 complete version" in steps["install.codex.cache-snapshot"].detail
    assert steps["install.codex.cache-restore"].ok is True
    assert "restored 1" in steps["install.codex.cache-restore"].detail


def test_codex_refresh_repairs_if_existing_preserved_root_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_parent = tmp_path / "codex-cache"
    old_file = cache_parent / "4.74.0" / "hooks" / "hooks.json"
    old_file.parent.mkdir(parents=True)
    old_file.write_text("before\n", encoding="utf-8")

    monkeypatch.setattr(release, "plugin_cache_parent", lambda client: cache_parent)
    monkeypatch.setattr(release, "resolve_client_binary", lambda name: "/fake/codex")

    def run(command, **_kwargs):
        if command[1:3] == ["plugin", "add"]:
            old_file.write_text("modified\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(release, "run", run)
    result = release.Result()
    assert release.refresh_client("codex", result, dry_run=False) is True
    assert old_file.read_text(encoding="utf-8") == "before\n"
    restore = next(
        step for step in result.steps if step.name == "install.codex.cache-restore"
    )
    assert restore.ok is True
    assert "repaired 1" in restore.detail


def test_codex_refresh_fails_if_unowned_extra_survives_repair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_parent = tmp_path / "codex-cache"
    old_root = cache_parent / "4.74.0"
    old_root.mkdir(parents=True)
    (old_root / "owned").write_text("before\n", encoding="utf-8")

    monkeypatch.setattr(release, "plugin_cache_parent", lambda client: cache_parent)
    monkeypatch.setattr(release, "resolve_client_binary", lambda name: "/fake/codex")

    def run(command, **_kwargs):
        if command[1:3] == ["plugin", "add"]:
            (old_root / "unexpected").write_text("late\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(release, "run", run)
    result = release.Result()
    assert release.refresh_client("codex", result, dry_run=False) is False
    restore = next(
        step for step in result.steps if step.name == "install.codex.cache-restore"
    )
    assert restore.ok is False
    assert "recovery copy kept" in restore.detail


def test_codex_refresh_does_not_run_when_cache_snapshot_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_parent = tmp_path / "codex-cache"
    old_root = cache_parent / "4.74.0"
    old_root.mkdir(parents=True)
    calls = []

    monkeypatch.setattr(release, "plugin_cache_parent", lambda client: cache_parent)
    monkeypatch.setattr(release, "resolve_client_binary", lambda name: "/fake/codex")
    monkeypatch.setattr(
        release.shutil,
        "copytree",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("disk full")),
    )
    monkeypatch.setattr(release, "run", lambda *args, **kwargs: calls.append(args))

    result = release.Result()
    assert release.refresh_client("codex", result, dry_run=False) is False
    assert calls == []
    snapshot = next(
        step for step in result.steps if step.name == "install.codex.cache-snapshot"
    )
    assert snapshot.ok is False
    assert "recovery copy kept" in snapshot.detail


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


def _pytest_group_dirs(tokens: list[str]) -> set[str]:
    return {
        token.split("/test_")[0].rstrip("/")
        for token in tokens
        if token.startswith("skills/")
    }


def test_required_checks_cover_ci_pytest_groups() -> None:
    """A test group CI runs but the release gate skips ships unverified (found
    2026-09-01 when the Slack skill's first test directory joined CI): every
    pytest path in the conformance job must be covered by a REQUIRED_CHECKS
    pytest command; a directory covers its test_*.py glob."""
    repository = Path(__file__).resolve().parents[3]
    workflow = yaml.safe_load(
        (repository / ".github" / "workflows" / "validate.yml").read_text(
            encoding="utf-8"
        )
    )
    ci_groups: set[str] = set()
    for step in workflow["jobs"]["conformance"]["steps"]:
        run = step.get("run", "")
        if "-m pytest" in run:
            ci_groups |= _pytest_group_dirs(run.split())
    gate_groups: set[str] = set()
    for _name, command in release.REQUIRED_CHECKS:
        if "pytest" in command:
            gate_groups |= _pytest_group_dirs(list(command))
    missing = sorted(ci_groups - gate_groups)
    assert not missing, (
        "CI pytest groups absent from release.py REQUIRED_CHECKS: " + repr(missing)
    )

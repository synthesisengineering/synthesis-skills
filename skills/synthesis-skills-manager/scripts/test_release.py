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
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

import release  # noqa: E402


def write_manifests(repo: Path, claude: str | None, codex: str | None, muse: str | None) -> None:
    for directory, version in ((".claude-plugin", claude), (".codex-plugin", codex), (".muse-plugin", muse)):
        target = repo / directory
        target.mkdir(parents=True, exist_ok=True)
        payload = {"name": release.PLUGIN_NAME}
        if version is not None:
            payload["version"] = version
        (target / "plugin.json").write_text(json.dumps(payload), encoding="utf-8")


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    write_manifests(tmp_path, "9.9.9", "9.9.9", "9.9.9")
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
    home = tmp_path / "lifecycle-home"
    monkeypatch.setenv("SYNTHESIS_HOME", str(home))
    monkeypatch.setattr(release, "codex_cache_archive", lambda: tmp_path / "cache-recovery")
    for name, relative in {"XDG_CONFIG_HOME": ".config", "XDG_STATE_HOME": ".local/state",
                           "XDG_CACHE_HOME": ".cache", "XDG_DATA_HOME": ".local/share"}.items():
        monkeypatch.setenv(name, str(home / relative))


# --- source of truth -------------------------------------------------------


def test_source_version_agrees(repo: Path) -> None:
    version, _ = release.source_version(repo)
    assert version == "9.9.9"


def test_source_version_fails_closed_when_manifests_disagree(repo: Path) -> None:
    write_manifests(repo, "9.9.9", "9.9.8", "9.9.9")
    version, detail = release.source_version(repo)
    assert version is None
    assert "9.9.8" in detail


def test_source_version_fails_closed_when_a_manifest_lacks_a_version(repo: Path) -> None:
    write_manifests(repo, "9.9.9", None, "9.9.9")
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
    first_source = tmp_path / "source-first"
    _seed_content(first_source, first)
    assert release.refresh_stable_path("4.82.0", release.Result(), False, target=first, repo=first_source)
    link = release.stable_path()
    assert link.is_symlink()
    assert Path(os.path.realpath(link)) == first.resolve()

    second = _install_root(tmp_path, "4.83.0")
    second_source = tmp_path / "source-second"
    _seed_content(second_source, second)
    assert release.refresh_stable_path("4.83.0", release.Result(), False, target=second, repo=second_source)
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


@pytest.mark.parametrize("mutation", ["before", "at-publication"])
def test_stable_consumer_revalidates_full_inventory_and_preserves_previous_pointer(tmp_path, monkeypatch, mutation):
    monkeypatch.setattr(release, "STABLE_ROOT", tmp_path / "plugins")
    prior = _install_root(tmp_path, "4.82.0")
    root = _install_root(tmp_path, "4.83.0")
    source = tmp_path / "source"
    _seed_content(source, root)
    link = release.stable_path()
    link.parent.mkdir(parents=True)
    link.symlink_to(prior)
    def corrupt():
        (root / "unapproved-hook.py").write_text("Unexpected loadable content.\n")
    real_replace = release.os.replace
    def replace(src, dst):
        real_replace(src, dst)
        if Path(dst) == link and link.resolve() == root:
            corrupt()
    if mutation == "before":
        corrupt()
    else:
        monkeypatch.setattr(release.os, "replace", replace)
    assert not release.refresh_stable_path("4.83.0", release.Result(), False, target=root, repo=source)
    assert link.resolve() == prior


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
        "skills/synthesis-skills-manager/scripts/test_release_check_groups.py",
        "-q",
    ]


def test_required_checks_execute_guardrails_suite() -> None:
    commands = {name: command for name, command in release.REQUIRED_CHECKS}
    assert commands["pytest.guardrails"] == [
        "python3",
        "-m",
        "pytest",
        "skills/synthesis-agent-guardrails/tests/",
        "-q",
    ]


def test_required_checks_execute_whole_system_onboarding_contract() -> None:
    commands = {name: command for name, command in release.REQUIRED_CHECKS}
    assert commands["pytest.onboarding"] == [
        "python3",
        "-m",
        "pytest",
        "skills/synthesis-onboarding/scripts/",
        "-q",
    ]
    assert commands["onboarding.catalog-scaffolds"] == [
        "python3",
        "skills/synthesis-onboarding/scripts/check_scaffolds.py",
        ".",
    ]
    assert commands["onboarding.capabilities"] == [
        "python3",
        "skills/synthesis-onboarding/scripts/check_capabilities.py",
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
    Excluded by design: the CI-only dependency install, the env-bound
    acceptance step (documented under Releases instead), and the CI-only
    base-resolution step (github.event context; meaningless locally)."""
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
        and step.get("name") != "Install OS isolation for executable consumer acceptance"
        and "--acceptance-only" not in step["run"]
        and "GITHUB_ENV" not in step["run"]
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


def test_acceptance_base_resolves_to_previous_release_tag() -> None:
    """2026-09-22: CI graded every push slice against the transaction manifest
    because the base was the push base, so Validate stayed red on release
    commits whose local gate was green. Pushes now resolve the base to the
    previous release tag (PRs keep their base); the acceptance step consumes
    the resolved base from the environment instead of an inline binding."""
    repository = Path(__file__).resolve().parents[3]
    workflow = yaml.safe_load(
        (repository / ".github" / "workflows" / "validate.yml").read_text(
            encoding="utf-8"
        )
    )
    steps = workflow["jobs"]["conformance"]["steps"]
    resolve = next(
        step for step in steps if step.get("name") == "Resolve acceptance change base"
    )
    assert "github.event.pull_request.base.sha" in resolve["run"]
    assert "git describe --tags" in resolve["run"]
    assert "git rev-list -n 1" in resolve["run"]
    assert "GITHUB_ENV" in resolve["run"]
    accept = next(
        step
        for step in steps
        if step.get("name") == "Consume transaction-bound R5 acceptance"
    )
    assert "env" not in accept


def test_repository_ci_executes_release_wiring_tests() -> None:
    repository = Path(__file__).resolve().parents[3]
    workflow = (repository / ".github" / "workflows" / "validate.yml").read_text(
        encoding="utf-8"
    )

    assert "python skills/synthesis-onboarding/scripts/check_scaffolds.py ." in workflow
    assert "python skills/synthesis-onboarding/scripts/check_capabilities.py ." in workflow
    assert "ubuntu-latest, macos-latest" in workflow
    assert (
        "python -m pytest skills/synthesis-skills-manager/scripts/test_release.py skills/synthesis-skills-manager/scripts/test_release_check_groups.py -q"
        in workflow
    )
    assert (
        "python -m pytest skills/synthesis-agent-guardrails/tests/ -q"
        in workflow
    )


@pytest.mark.parametrize("activation_ok", [True, False])
def test_release_establishes_required_launcher_before_exposing_new_hooks(repo, monkeypatch, activation_ok):
    ready = False
    observations = []
    monkeypatch.setattr(release, "preflight", lambda *args: "9.9.9")

    def activate(repository, version, result, dry_run):
        nonlocal ready
        ready = activation_ok
        return result.add("install.synthesis-cli", activation_ok, "fixture")

    def refresh(client, *args, **kwargs):
        observations.append((client, ready))
        return True

    monkeypatch.setattr(release, "activate_published_cli", activate)
    monkeypatch.setattr(release, "refresh_client", refresh)
    monkeypatch.setattr(release, "install_codex_cache_guardian", lambda *args, **kwargs: True)
    monkeypatch.setattr(release, "deep_verify", lambda *args, **kwargs: True)
    monkeypatch.setattr(release, "refresh_stable_path", lambda *args, **kwargs: True)
    monkeypatch.setattr(release, "sync_commit_gate", lambda *args, **kwargs: True)
    monkeypatch.setattr(release, "reconcile_published_lifecycle", lambda *args, **kwargs: True)
    assert release.main(["--repo-root", str(repo), "--install-only"]) == (0 if activation_ok else 1)
    assert observations == ([("claude", True), ("codex", True), ("muse", True)] if activation_ok else [])


def test_release_refuses_completion_when_lifecycle_transaction_is_not_reconciled(repo, monkeypatch, capsys):
    order = []
    monkeypatch.setattr(release, "preflight", lambda *a: "9.9.9")
    for name in ("activate_published_cli", "refresh_client", "install_codex_cache_guardian",
                 "deep_verify", "refresh_stable_path", "sync_commit_gate"):
        monkeypatch.setattr(release, name, lambda *a, _name=name, **k: order.append(_name) or True)
    monkeypatch.setattr(release, "reconcile_published_lifecycle", lambda *a, **k: order.append("lifecycle") or False, raising=False)
    assert release.main(["--repo-root", str(repo), "--install-only"]) == 1
    assert order[-1] == "lifecycle"
    output = capsys.readouterr().out
    assert "RELEASE INCOMPLETE" in output and "RELEASED" not in output


@pytest.mark.parametrize("selected", [None, ["claude"], ["codex"], ["claude", "codex"]])
@pytest.mark.parametrize("dry_run", [False, True])
def test_release_native_effects_honor_saved_client_selection(repo, monkeypatch, selected, dry_run):
    import system_contract as contract
    state = contract.SystemState()
    if selected is not None:
        desired = contract.default_desired_state("skills-only", selected, "stable")
        state.run_transaction("setup", desired, lambda _tx: {})
    before = state.read_desired()
    expected = selected if selected is not None else ["claude", "codex", "muse"]
    calls = {name: [] for name in ("refresh", "verify", "guardian", "stable")}
    monkeypatch.setattr(release, "preflight", lambda *a: "9.9.9")
    for name in ("activate_published_cli", "sync_commit_gate", "reconcile_published_lifecycle"):
        monkeypatch.setattr(release, name, lambda *a, **kw: True)
    monkeypatch.setattr(release, "refresh_client", lambda client, *a, **kw: calls["refresh"].append(client) or True)
    def verify(client, version, result, **kwargs):
        calls["verify"].append(client)
        result.verified_roots[client] = release.installed_root(client, version)
        return True
    monkeypatch.setattr(release, "deep_verify", verify)
    monkeypatch.setattr(release, "install_codex_cache_guardian", lambda *a, **kw: calls["guardian"].append(True) or True)
    monkeypatch.setattr(release, "refresh_stable_path", lambda *a, **kw: calls["stable"].append(kw.get("target")) or True)
    command = ["--repo-root", str(repo), "--install-only"] + (["--dry-run"] if dry_run else [])
    assert release.main(command) == 0
    assert calls["refresh"] == expected
    assert calls["verify"] == ([] if dry_run else expected)
    assert bool(calls["guardian"]) == ("codex" in expected)
    if not dry_run:
        assert calls["stable"] == [release.installed_root(expected[0], "9.9.9")]
    assert state.read_desired() == before


@pytest.mark.parametrize("changed_at", ["activation", "before-native-lock"])
def test_release_binds_original_selection_before_native_mutation(repo, monkeypatch, capsys, changed_at):
    import contextlib
    import system_contract as contract
    state = contract.SystemState()
    original = contract.default_desired_state("skills-only", ["codex"], "stable")
    changed = contract.default_desired_state("skills-only", ["claude"], "stable")
    state.run_transaction("setup", original, lambda _tx: {})
    monkeypatch.setattr(release, "preflight", lambda *a: "9.9.9")
    native_calls = []
    activated = False
    def activate(*a, **kw):
        nonlocal activated
        activated = True
        if changed_at == "activation":
            state.run_transaction("setup", changed, lambda _tx: {})
        return True
    real_lock = contract.SystemState.locked
    @contextlib.contextmanager
    def locked(instance):
        with real_lock(instance):
            if activated and changed_at == "before-native-lock":
                contract.atomic_write_json(state.desired_path, changed)
            yield
    monkeypatch.setattr(contract.SystemState, "locked", locked)
    monkeypatch.setattr(release, "activate_published_cli", activate)
    monkeypatch.setattr(release, "refresh_client", lambda client, *a, **kw: native_calls.append(client) or True)
    for name in ("deep_verify", "install_codex_cache_guardian", "sync_commit_gate", "refresh_stable_path", "reconcile_published_lifecycle"):
        monkeypatch.setattr(release, name, lambda *a, **kw: True)
    assert release.main(["--repo-root", str(repo), "--install-only"]) == 1
    assert native_calls == []
    assert state.read_desired() == changed
    assert "RELEASED" not in capsys.readouterr().out


def test_release_stable_consumer_uses_actual_verified_client_root(tmp_path, monkeypatch):
    import system_contract as contract
    from test_system_contract import release_repo
    state = contract.SystemState()
    state.run_transaction("setup", contract.default_desired_state("skills-only", ["codex"], "stable"), lambda _tx: {})
    source = release_repo(tmp_path / "source", "9.9.9")
    generation, _descriptor = release.materialize_release(source, tmp_path / "generations", channel="stable", ref="stable",
        source_url="https://example.test/synthesis-skills.git")
    conventional, loaded = tmp_path.resolve() / "conventional", tmp_path.resolve() / "reported"
    shutil.copytree(generation, conventional)
    shutil.copytree(generation, loaded)
    conventional.chmod(0o755)
    (conventional / "unapproved-hook.py").write_text("Unexpected loadable content.\n")
    monkeypatch.setattr(release, "STABLE_ROOT", tmp_path / "stable")
    monkeypatch.setattr(release, "preflight", lambda *a: "9.9.9")
    monkeypatch.setattr(release, "installed_root", lambda *a: conventional)
    monkeypatch.setattr(release, "client_reported_version", lambda *a: ("9.9.9", str(loaded)))
    for name in ("activate_published_cli", "refresh_client", "install_codex_cache_guardian", "sync_commit_gate", "reconcile_published_lifecycle"):
        monkeypatch.setattr(release, name, lambda *a, **kw: True)
    assert release.main(["--repo-root", str(source), "--install-only"]) == 0
    assert release.stable_path().resolve() == loaded
    assert release.content_digest_report(source, release.stable_path().resolve())[0]


def test_release_reconciliation_keeps_original_publisher_selection_binding(repo, monkeypatch):
    import system_contract as contract
    state = contract.SystemState()
    original = contract.default_desired_state("skills-only", ["codex"], "stable")
    changed = contract.default_desired_state("skills-only", ["claude"], "stable")
    state.run_transaction("setup", changed, lambda _tx: {})
    before = state.observation_path.read_bytes(), state.desired_path.read_bytes()
    monkeypatch.setattr(release, "run", lambda *a, **kw: pytest.fail("repair ran with a recaptured selection"))
    assert not release.reconcile_published_lifecycle(repo, "9.9.9", release.Result(), False,
        expected_desired_digest=contract.json_digest(original))
    assert (state.observation_path.read_bytes(), state.desired_path.read_bytes()) == before


@pytest.mark.parametrize("selection", ["missing", "disabled", "modular", "other-pin", "selected"])
def test_release_selection_preserves_explicit_profile_and_policy(tmp_path, monkeypatch, selection):
    import system_contract as contract
    state = contract.SystemState()
    if selection != "missing":
        desired = contract.default_desired_state("skills-only", ["codex"], "stable",
            version_pin="8.0.0" if selection == "other-pin" else None,
            enabled=selection != "disabled")
        if selection == "modular":
            desired = contract.default_desired_state("modular", ["codex"], "stable",
                modular={"roots": ["synthesis-autopilot"], "stage_core": True})
        state.run_transaction("setup", desired, lambda _tx: {})
    before = {str(p): p.read_bytes() for p in state.home.rglob("*") if p.is_file()}
    result = release.Result()
    assert release.lifecycle_release_selection("9.9.9", result) == (selection in {"missing", "selected"})
    after = {str(p): p.read_bytes() for p in state.home.rglob("*") if p.is_file()}
    assert after == before


@pytest.mark.parametrize("failure", [None, "engine", "doctor", "same-version-corruption", "unapproved-extra", "no-transaction"])
def test_release_commits_real_lifecycle_generation_only_after_exact_native_and_engine_checks(tmp_path, monkeypatch, failure):
    import contextlib
    import io
    import synthesis_cli as cli
    import system_contract as contract
    from bootstrap import materialize_release
    from test_system_contract import release_repo

    source = release_repo(tmp_path / "fixture-source", version="9.9.9")
    state = contract.SystemState()
    desired = contract.default_desired_state("skills-only", ["codex"], "stable")
    state.run_transaction("setup", desired, lambda _tx: {})
    old = state.read_observation()["transactions"][0]
    generation, descriptor = materialize_release(source, state.cache_dir / "releases",
        channel="stable", ref="stable", source_url="https://example.test/synthesis-skills.git")
    pointer = state.state_dir / "active-release.json"
    contract.activate_cli(generation, descriptor, state.launcher_path, pointer)
    monkeypatch.setenv("SYNTHESIS_ACTIVE_DESCRIPTOR", str(pointer))
    monkeypatch.setattr(cli, "REPO_ROOT", generation)
    monkeypatch.setattr(cli.onboard, "source_root", lambda: generation)
    native = tmp_path.resolve() / "native-plugin"
    shutil.copytree(generation, native)
    if failure == "same-version-corruption":
        target = native / "skills/synthesis-onboarding/scripts/synthesis_cli.py"
        target.chmod(0o644)
        target.write_text("Corrupted runtime with unchanged version labels.\n")
    if failure == "unapproved-extra":
        (native / "skills").chmod(0o755)
        target = native / "skills/unapproved-extra/SKILL.md"
        target.parent.mkdir()
        target.write_text("Additional loadable synthetic skill outside the release.\n")
    monkeypatch.setattr(cli, "_release_native_root", lambda *_a: native)
    engine_calls = []
    def engine(args):
        engine_calls.append(args[0])
        return {"engine": "fixture", "counts": {"ok": 1}, "steps": [],
                "exit": 1 if args[0] == failure or (failure == "engine" and args[0] == "repair") else 0}
    real_run = release.run
    def run(command, *args, **kwargs):
        if command[0] != str(state.launcher_path):
            return real_run(command, *args, **kwargs)
        if failure == "no-transaction":
            return subprocess.CompletedProcess(command, 0, '{"state":"committed"}', "")
        output, error = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            code = cli.main(command[1:], state=state, engine_runner=engine)
        return subprocess.CompletedProcess(command, code, output.getvalue(), error.getvalue())
    monkeypatch.setattr(release, "run", run)
    assert release.reconcile_published_lifecycle(source, "9.9.9", release.Result(), False) == (failure is None)
    assert state.read_desired() == desired
    observation = state.read_observation()
    assert observation["transactions"][0] == old
    if failure is None:
        latest = observation["transactions"][-1]
        assert observation["generation"] == 2 and latest["state"] == "committed"
        assert latest["release"]["content_digest"] == descriptor["content_digest"]
        assert latest["installed"]["native_plugins"]["codex"]["content_digest"] == descriptor["content_digest"]
        assert latest["live-loaded"]["status"] == "restart-required"
        assert engine_calls == ["repair", "doctor"]
    else:
        assert observation["generation"] == 1
        if failure in {"same-version-corruption", "unapproved-extra"}:
            assert engine_calls == []


def test_publisher_activates_cli_through_public_release_verifier(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cli = repo / "skills" / "synthesis-onboarding" / "scripts" / "synthesis_cli.py"
    cli.parent.mkdir(parents=True)
    cli.write_text("print('fixture')\n", encoding="utf-8")
    assert release.run(["git", "init", "-q", "-b", "main"], cwd=repo).returncode == 0
    assert release.run(["git", "config", "user.name", "Fixture"], cwd=repo).returncode == 0
    assert release.run(["git", "config", "user.email", "fixture@example.test"], cwd=repo).returncode == 0
    assert release.run(["git", "config", "core.hooksPath", "/dev/null"], cwd=repo).returncode == 0
    assert release.run(["git", "add", "-A"], cwd=repo).returncode == 0
    assert release.run(["git", "commit", "-q", "-m", "fixture"], cwd=repo).returncode == 0
    version = release.source_version(repo)[0]
    assert version
    assert release.run(["git", "tag", "v%s" % version], cwd=repo).returncode == 0
    manifest = repo / ".codex-plugin" / "plugin.json"
    # The repository fixture is already tagged at its manifest version.
    test_home = tmp_path.parent / (tmp_path.name + "-home")
    monkeypatch.setenv("SYNTHESIS_HOME", str(test_home))
    for name, relative in {
        "XDG_CONFIG_HOME": ".config", "XDG_STATE_HOME": ".local/state",
        "XDG_CACHE_HOME": ".cache", "XDG_DATA_HOME": ".local/share",
    }.items():
        monkeypatch.setenv(name, str(test_home / relative))
    result = release.Result()
    assert release.activate_published_cli(repo, version, result, dry_run=False)
    launcher = test_home / ".local" / "bin" / "synthesis"
    active = test_home / ".local" / "state" / "synthesis" / "active-release.json"
    assert launcher.is_file()
    descriptor = json.loads(active.read_text(encoding="utf-8"))
    assert descriptor["version"] == json.loads(manifest.read_text())["version"]
    assert Path(descriptor["release_root"]).is_dir()


def test_cli_activation_refuses_to_manufacture_a_missing_release_tag(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cli = repo / "skills" / "synthesis-onboarding" / "scripts" / "synthesis_cli.py"
    cli.parent.mkdir(parents=True)
    cli.write_text("print('fixture')\n", encoding="utf-8")
    assert release.run(["git", "init", "-q", "-b", "main"], cwd=repo).returncode == 0
    assert release.run(["git", "config", "user.name", "Fixture"], cwd=repo).returncode == 0
    assert release.run(["git", "config", "user.email", "fixture@example.test"], cwd=repo).returncode == 0
    assert release.run(["git", "config", "core.hooksPath", "/dev/null"], cwd=repo).returncode == 0
    assert release.run(["git", "add", "-A"], cwd=repo).returncode == 0
    assert release.run(["git", "commit", "-q", "-m", "fixture"], cwd=repo).returncode == 0
    version = release.source_version(repo)[0]
    assert version
    monkeypatch.setenv("SYNTHESIS_HOME", str(tmp_path / "home"))
    result = release.Result()
    assert not release.activate_published_cli(repo, version, result, dry_run=False)
    missing = release.run(
        ["git", "rev-parse", "--verify", "refs/tags/v%s" % version], cwd=repo
    )
    assert missing.returncode != 0


def test_install_only_preflight_rejects_dirty_or_untagged_source(
    repo: Path,
) -> None:
    assert release.run(["git", "init", "-q", "-b", "main"], cwd=repo).returncode == 0
    assert release.run(["git", "config", "user.name", "Fixture"], cwd=repo).returncode == 0
    assert release.run(["git", "config", "user.email", "fixture@example.test"], cwd=repo).returncode == 0
    assert release.run(["git", "config", "core.hooksPath", "/dev/null"], cwd=repo).returncode == 0
    assert release.run(["git", "add", "-A"], cwd=repo).returncode == 0
    assert release.run(["git", "commit", "-q", "-m", "fixture"], cwd=repo).returncode == 0
    result = release.Result()
    assert release.preflight(repo, result, install_only=True) == "9.9.9"
    checks = {step.name: step.ok for step in result.steps}
    assert checks["preflight.release-tag"] is False
    (repo / "dirty").write_text("dirty\n", encoding="utf-8")
    assert release.run(["git", "tag", "v9.9.9"], cwd=repo).returncode == 0
    dirty_result = release.Result()
    assert release.preflight(repo, dirty_result, install_only=True) == "9.9.9"
    checks = {step.name: step.ok for step in dirty_result.steps}
    assert checks["preflight.tree-clean"] is False
    assert checks["preflight.release-tag"] is True


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
    assert "SYNTHESIS_ACCEPTANCE_CHANGE_BASE=" in workflow
    assert "github.event.pull_request.base.sha" in workflow
    assert "git describe --tags" in workflow
    assert "github.event.before }}" in workflow  # pre-first-release fallback only


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


def squash_release_repo(tmp_path: Path) -> tuple[Path, str]:
    """main with a base commit plus a single-parent head (a squash landing)."""
    repository = tmp_path / "squash-repo"
    repository.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(repository)], check=True)
    for key, value in (
        ("user.name", "Squash Fixture"),
        ("user.email", "squash@example.invalid"),
        ("core.hooksPath", "/dev/null"),
    ):
        subprocess.run(
            ["git", "-C", str(repository), "config", key, value], check=True
        )
    (repository / "bump.txt").write_text("base\n", encoding="utf-8")
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
    (repository / "bump.txt").write_text("head\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repository), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(repository), "commit", "-qm", "squash"], check=True
    )
    return repository, base


def test_acceptance_change_base_uses_parent_for_squash_commit_on_main(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository, base = squash_release_repo(tmp_path)
    monkeypatch.delenv("SYNTHESIS_ACCEPTANCE_CHANGE_BASE", raising=False)

    resolved, detail = release.acceptance_change_base(repository)

    assert resolved == base
    assert "single-parent" in detail


def test_acceptance_change_base_keeps_merge_base_for_feature_branches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository, _ = squash_release_repo(tmp_path)
    monkeypatch.delenv("SYNTHESIS_ACCEPTANCE_CHANGE_BASE", raising=False)
    subprocess.run(
        ["git", "-C", str(repository), "checkout", "-qb", "feature/x"], check=True
    )
    (repository / "bump.txt").write_text("branch\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repository), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(repository), "commit", "-qm", "branch"], check=True
    )

    resolved, _ = release.acceptance_change_base(repository)

    # No origin/main exists here; the branch path must fail, never silently
    # resolve to the single parent (that would shrink the change universe to
    # one commit).
    assert resolved is None


def test_acceptance_change_base_uses_first_parent_for_merge_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository, _ = squash_release_repo(tmp_path)
    monkeypatch.delenv("SYNTHESIS_ACCEPTANCE_CHANGE_BASE", raising=False)
    pre_merge = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    subprocess.run(
        ["git", "-C", str(repository), "checkout", "-qb", "feature/y"], check=True
    )
    (repository / "side.txt").write_text("side\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repository), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(repository), "commit", "-qm", "side"], check=True
    )
    subprocess.run(
        ["git", "-C", str(repository), "checkout", "-q", "main"], check=True
    )
    subprocess.run(
        ["git", "-C", str(repository), "merge", "--quiet", "--no-ff",
         "--no-edit", "feature/y"],
        check=True,
    )

    resolved, detail = release.acceptance_change_base(repository)

    assert resolved == pre_merge
    assert detail == "merge first parent"


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


def test_deduplicated_archive_release_contract_is_public_and_coherent() -> None:
    repository = Path(__file__).resolve().parents[3]
    version, detail = release.source_version(repository)
    assert version is not None, detail
    assert release.changelog_top_version(repository) == version
    manager = (repository / "skills/synthesis-skills-manager/SKILL.md").read_text()
    readme = (repository / "README.md").read_text()
    changelog = (repository / "CHANGELOG.md").read_text()
    for document in (manager, changelog):
        assert "SQLite" in document
    for document in (manager, readme, changelog):
        assert "512 MiB" in document
    assert "independent files" in manager
    assert "no historical version is evicted" in changelog
    assert release.CODEX_CACHE_ARCHIVE_BUDGET_BYTES == 512 * 1024 * 1024


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


def test_cache_guardian_lock_release_contract_is_public_and_coherent() -> None:
    repository = Path(__file__).resolve().parents[3]
    manager = (repository / "skills/synthesis-skills-manager/SKILL.md").read_text(
        encoding="utf-8"
    )
    changelog = (repository / "CHANGELOG.md").read_text(encoding="utf-8")
    readme = (repository / "README.md").read_text(encoding="utf-8")
    hook_payload = json.loads(
        (repository / "hooks/hooks.json").read_text(encoding="utf-8")
    )
    commands = [
        hook["command"]
        for registrations in hook_payload["hooks"].values()
        for registration in registrations
        for hook in registration["hooks"]
        if hook.get("type") == "command"
    ]

    # This is a historical feature contract. Current release metadata must
    # agree without pinning every later release to the version that introduced
    # the feature.
    current = release.source_version(repository)[0]
    assert current is not None
    assert release.changelog_top_version(repository) == current
    assert "Version 2.6.3" in manager and "wait up to 120 seconds" in manager
    assert "watcher and explicit one-shot mode stay nonblocking" in manager
    assert "bounded failure" in readme
    assert "## [4.91.4]" in changelog
    assert commands and all(command.startswith('"${SYNTHESIS_INSTALL_BIN_DIR:-$HOME/.local/bin}/synthesis" exec-public ') for command in commands)


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
    assert "set -- onboard" in bootstrap
    assert "synthesis doctor" in readme
    assert "Skills-only alternative" in readme
    assert ".agents/workspace-AGENTS.md" in onboarding
    assert "content-addressed generation" in onboarding
    assert "synthesis workspace ensure" in readme
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
    assert "synthesis workspace ensure" in skill
    assert ".agents/workspace-AGENTS.md" in skill
    assert "AGENTS.md" in skill and "CLAUDE.md" in skill
    assert "synthesis-onboarding" in skill
    # Native installation shares the existing-conversation recovery contract.
    # A new chat is conditional, never the unconditional installation result.
    # Producer/renderer and receipt rejection cases live in test_reload_guidance.
    from reload_guidance import recovery_instruction

    assert "verify its exact current-plugin SessionStart receipt" not in onboard
    assert "start a new chat there" not in onboard
    assert "hint=recovery_instruction([name]" in onboard
    for client in ("claude", "codex"):
        guidance = recovery_instruction([client], initial=True)
        assert "reopen the existing" in guidance
        assert "If same-session recovery is unsupported or those checks fail" in guidance
        assert "start a new conversation" in guidance
        assert "If there is no existing conversation" in guidance


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
    monkeypatch.setattr(release, "install_codex_cache_guardian", lambda *_args, **_kwargs: True)

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
    # The fixture source is the whole release, including its native manifest.
    for manifest in release.MANIFESTS:
        path = installed / manifest
        if path.is_file():
            target = source / manifest
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
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


@pytest.mark.parametrize("client", ["claude", "codex", "muse"])
@pytest.mark.parametrize("drift", ["extra-skill", "extra-directory", "hook-bytes", "loaded-root"])
def test_deep_verify_checks_complete_reported_native_inventory(tmp_path, monkeypatch, client, drift):
    source, conventional, loaded = (tmp_path / name for name in ("source", "conventional", "loaded"))
    source.mkdir()
    write_manifests(source, "9.9.9", "9.9.9", "9.9.9")
    (source / "skills/demo").mkdir(parents=True)
    (source / "skills/demo/SKILL.md").write_text("# fixture\n")
    (source / "hooks").mkdir()
    (source / "hooks/hooks.json").write_text('{"hooks": {}}\n')
    shutil.copytree(source, conventional)
    shutil.copytree(source, loaded)
    target = loaded if drift == "loaded-root" else conventional
    if drift in {"extra-skill", "loaded-root"}:
        (target / "skills/unapproved-extra").mkdir()
        (target / "skills/unapproved-extra/SKILL.md").write_text("# unexpected\n")
    elif drift == "extra-directory":
        (target / "unexpected").mkdir()
    else:
        (target / "hooks/hooks.json").write_text('{"hooks":{"extra":[]}}\n')
    monkeypatch.setattr(release, "installed_root", lambda *a: conventional)
    monkeypatch.setattr(release, "client_reported_version", lambda *a: ("9.9.9", str(target)))
    assert not release.deep_verify(client, "9.9.9", release.Result(), repo=source)


def test_native_inventory_uses_git_release_membership_not_checkout_build_noise(tmp_path):
    from bootstrap import materialize_release
    from test_system_contract import release_repo
    source = release_repo(tmp_path / "source")
    generation, _descriptor = materialize_release(source, tmp_path / "releases", channel="stable", ref="stable",
        source_url="https://example.test/synthesis-skills.git")
    native = tmp_path.resolve() / "native"
    shutil.copytree(generation, native)
    cache = source / ".pytest_cache"
    cache.mkdir()
    (cache / "lastfailed").write_text("{}\n")
    assert release.content_digest_report(source, native)[0]
    native.chmod(0o755)
    (native / "unapproved-hook.py").write_text("Unexpected shipped file.\n")
    ok, detail = release.content_digest_report(source, native)
    assert not ok and "unexpected release entry" in detail


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
    bytecode = installed / "skills/example/__pycache__/hook.cpython-312.pyc"
    bytecode.parent.mkdir()
    bytecode.write_bytes(b"first runtime bytecode\n")
    temporary = bytecode.with_name(f"{bytecode.name}.123456789")
    temporary.write_bytes(b"CPython atomic-write staging\n")

    assert release._tree_digest(expected) == release._tree_digest(installed)
    bytecode.write_bytes(b"changed while the release ran\n")
    assert release._tree_digest(expected) == release._tree_digest(installed)

    (installed / "unexpected").write_text("unowned\n", encoding="utf-8")
    assert release._tree_digest(expected) != release._tree_digest(installed)


def test_recovery_digest_rejects_special_objects(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    os.mkfifo(root / "unexpected.pipe")

    with pytest.raises(OSError, match="unsupported cache entry type"):
        release._tree_digest(root)


# --- install sequencing ----------------------------------------------------


def commit_release(repo: Path, version: str, marker: str) -> None:
    write_manifests(repo, version, version, version)
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
    write_manifests(root, version, version, version)
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
    materialized = tmp_path / "materialized"
    release.RecoveryStore.read(recovery).materialize("4.74.1", materialized)
    assert release._tree_digest(snapshot.backup / "4.74.1") == release._tree_digest(materialized)
    assert next(
        step for step in result.steps if step.name == "install.codex.cache-archive"
    ).ok


def test_repeated_archive_admission_preserves_root_identity_across_umask(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source"
    source.mkdir()
    commit_release(source, "4.74.0", "old")
    commit_release(source, "4.75.0", "current")
    archive, cache = tmp_path / "archive", tmp_path / "cache"
    (cache / "4.74.0").mkdir(parents=True)
    monkeypatch.setattr(release, "codex_cache_archive", lambda: archive)
    monkeypatch.setattr(release, "plugin_cache_parent", lambda client: cache)
    previous_umask = os.umask(0o022)
    snapshots = []
    try:
        first = release.snapshot_codex_caches(release.Result(), repo=source)
        assert first is not None
        snapshots.append(first)
        expected = release.RecoveryStore.read(archive).versions
        os.umask(0o077)
        second = release.snapshot_codex_caches(release.Result(), repo=source)
        assert second is not None
        snapshots.append(second)
        assert release.RecoveryStore.read(archive).versions == expected
    finally:
        os.umask(previous_umask)
        for snapshot in snapshots:
            release._remove_transition_backup(snapshot.backup)


def _native_codex_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                          versions=("4.74.0", "4.75.0"), *, take_snapshot=True):
    source = tmp_path / "publisher"
    source.mkdir()
    (source / "install.sh").write_text("#!/bin/sh\nexit 0\n")
    (source / "install.sh").chmod(0o755)
    commit_release(source, "4.74.0", "historical")
    commit_release(source, "4.75.0", "current")
    subprocess.run(["git", "-C", str(source), "config", "tar.umask", "0002"], check=True)
    parent = tmp_path / "codex-cache"
    parent.mkdir()
    for version in versions:
        root = parent / version
        subprocess.run(["git", "clone", "--no-local", "--branch", "v" + version,
                        str(source), str(root)], check=True, capture_output=True, umask=0o022)
        subprocess.run(["git", "-C", str(root), "config", "remote.origin.url",
                        "https://github.com/synthesisengineering/synthesis-skills.git"],
                       check=True, capture_output=True)
        head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
        (root / ".codex-marketplace-install.json").write_text(json.dumps({
            "source_type": "git", "source": "https://github.com/synthesisengineering/synthesis-skills.git",
            "ref_name": "stable", "sparse_paths": [], "revision": head,
        }))
    monkeypatch.setattr(release, "plugin_cache_parent", lambda _client: parent)
    monkeypatch.setattr(release, "codex_cache_archive", lambda: tmp_path / "archive")
    snapshot = release.snapshot_codex_caches(release.Result(), repo=source) if take_snapshot else None
    assert snapshot is not None or not take_snapshot
    return source, parent, snapshot


def _all_cache_bytes(root: Path):
    result = {}
    for path in (root, *root.rglob("*")):
        mode = path.lstat().st_mode
        value = os.readlink(path) if stat.S_ISLNK(mode) else path.read_bytes() if stat.S_ISREG(mode) else None
        result[str(path.relative_to(root))] = (mode, value)
    return result


def test_codex_native_current_mode_difference_preserves_real_git_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _source, parent, snapshot = _native_codex_fixture(tmp_path, monkeypatch, ("4.75.0",))
    current = parent / "4.75.0"
    before = _all_cache_bytes(current)
    identity = current.stat().st_ino
    assert release._tree_digest(current) != release._tree_digest(snapshot.backup / "4.75.0")
    result = release.Result()
    assert release.restore_codex_caches(snapshot, result), result.steps
    assert current.stat().st_ino == identity
    assert _all_cache_bytes(current) == before
    assert not list(parent.glob(".release-displaced-4.75.0-*"))


def test_codex_native_historical_repair_retains_verified_git_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _source, parent, snapshot = _native_codex_fixture(tmp_path, monkeypatch)
    historical = parent / "4.74.0"
    (historical / "skills/example/SKILL.md").write_text("damaged historical payload")
    before = _all_cache_bytes(historical)
    result = release.Result()
    assert release.restore_codex_caches(snapshot, result), result.steps
    recoveries = list(parent.glob(".release-displaced-4.74.0-*"))
    assert len(recoveries) == 1
    assert _all_cache_bytes(recoveries[0]) == before
    assert (historical / "skills/example/SKILL.md").read_text() == "version: 4.74.0\nhistorical\n"
    assert any(str(recoveries[0]) in step.detail for step in result.steps)


@pytest.mark.parametrize("change", ["content", "executable", "extra", "nested-git", "git-file",
                                  "git-link", "alternates", "commondir", "config-redirect", "foreign-head"])
def test_codex_native_current_refuses_drift_without_mutating_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str,
) -> None:
    _source, parent, snapshot = _native_codex_fixture(tmp_path, monkeypatch, ("4.75.0",))
    current = parent / "4.75.0"
    external = tmp_path / "external"
    external.mkdir()
    (external / "sentinel").write_text("foreign bytes")
    if change == "content":
        (current / "skills/example/SKILL.md").write_text("retained local content")
    elif change == "executable":
        (current / "install.sh").chmod(0o644)
    elif change == "extra":
        (current / "retained-work").write_text("retained local work")
    elif change == "nested-git":
        (current / "retained/.git").mkdir(parents=True)
    elif change in {"git-file", "git-link"}:
        (current / ".git").rename(external / "metadata")
        if change == "git-file":
            (current / ".git").write_text("gitdir: " + str(external / "metadata") + "\n")
        else:
            (current / ".git").symlink_to(external / "metadata", target_is_directory=True)
    elif change == "alternates":
        (current / ".git/objects/info/alternates").write_text(str(external) + "\n")
    elif change == "commondir":
        (current / ".git/commondir").write_text(str(external) + "\n")
    elif change == "config-redirect":
        subprocess.run(["git", "-C", str(current), "config", "core.worktree", str(external)], check=True)
    else:
        subprocess.run(["git", "-C", str(current), "checkout", "--detach", "v4.74.0"], check=True, capture_output=True)
    before, foreign_before = _all_cache_bytes(current), _all_cache_bytes(external)
    result = release.Result()
    assert not release.restore_codex_caches(snapshot, result)
    assert _all_cache_bytes(current) == before
    assert _all_cache_bytes(external) == foreign_before
    assert snapshot.backup.is_dir()
    assert not list(parent.glob(".release-*-4.75.0-*"))


def test_codex_native_current_needs_no_client_marker_or_particular_origin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, parent, snapshot = _native_codex_fixture(tmp_path, monkeypatch, ("4.75.0",))
    current = parent / "4.75.0"
    (current / ".codex-marketplace-install.json").unlink()
    subprocess.run(["git", "-C", str(current), "config", "remote.origin.url", str(source)], check=True)
    before = _all_cache_bytes(current)
    assert release.restore_codex_caches(snapshot, release.Result())
    assert _all_cache_bytes(current) == before


def test_codex_native_identity_never_executes_partial_clone_helper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _source, parent, snapshot = _native_codex_fixture(tmp_path, monkeypatch, ("4.75.0",))
    current = parent / "4.75.0"
    commit = snapshot.native_sources["4.75.0"][0]
    marker = tmp_path / "remote-helper-executed"
    (current / ".git/objects").rename(current / ".git/preserved-objects")
    (current / ".git/objects").mkdir()
    for key, value in {
        "core.repositoryformatversion": "1", "extensions.partialclone": "origin",
        "remote.origin.promisor": "true", "remote.origin.partialclonefilter": "blob:none",
        "protocol.ext.allow": "always", "remote.origin.url": "ext::/usr/bin/touch " + str(marker),
    }.items():
        subprocess.run(["git", "-C", str(current), "config", "--local", key, value], check=True)
    before = _all_cache_bytes(current)
    with pytest.raises(OSError):
        release._codex_native_git_identity(current, commit)
    assert not marker.exists(), "identity read executed the repository's remote helper"
    assert _all_cache_bytes(current) == before


@pytest.mark.parametrize("kind", ["include", "partial-race", "include-race", "hooks-and-monitor"])
def test_codex_native_identity_does_not_load_checkout_execution_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str,
) -> None:
    _source, parent, snapshot = _native_codex_fixture(tmp_path, monkeypatch, ("4.75.0",))
    current = parent / "4.75.0"
    commit = snapshot.native_sources["4.75.0"][0]
    marker = tmp_path / "execution-marker"
    hook = tmp_path / "harmless-hook"
    hook.write_text("#!/bin/sh\n/usr/bin/touch " + str(marker) + "\n")
    hook.chmod(0o755)
    included = tmp_path / "unsafe-included-config"
    included.write_text("this is intentionally not valid Git config\n")
    config = current / ".git/config"

    def change_config():
        if kind == "partial-race":
            (current / ".git/objects").rename(current / ".git/preserved-objects")
            (current / ".git/objects").mkdir()
            config.write_text(config.read_text() + "\n[extensions]\npartialClone=origin\n"
                              "[remote \"origin\"]\npromisor=true\nurl=ext::/usr/bin/touch " + str(marker)
                              + "\n[protocol \"ext\"]\nallow=always\n")
        else:
            config.write_text(config.read_text() + "\n[include]\npath=" + str(included) + "\n")

    actual_run = subprocess.run
    observed = []
    def inspect_run(arguments, **kwargs):
        output = actual_run(arguments, **kwargs)
        if arguments[0] == "git":
            observed.append((arguments, kwargs))
            if kind.endswith("-race") and "config" in arguments and "--file" in arguments:
                change_config()
        return output

    if kind == "include":
        change_config()
    elif kind == "hooks-and-monitor":
        config.write_text(config.read_text() + "\n[core]\nfsmonitor=" + str(hook)
                          + "\nhooksPath=" + str(tmp_path) + "\n[pager]\nconfig=" + str(hook) + "\n")
        (tmp_path / "reference-transaction").write_bytes(hook.read_bytes())
        (tmp_path / "reference-transaction").chmod(0o755)
    before = _all_cache_bytes(current)
    monkeypatch.setattr(release.subprocess, "run", inspect_run)
    if kind == "hooks-and-monitor":
        release._codex_native_git_identity(current, commit)
        assert _all_cache_bytes(current) == before
    else:
        with pytest.raises(OSError) as error:
            release._codex_native_git_identity(current, commit)
        assert "bad config" not in str(error.value), "unsafe include was expanded"
    assert not marker.exists()
    assert observed
    for _arguments, kwargs in observed:
        assert kwargs["env"]["GIT_NO_LAZY_FETCH"] == "1"
        assert kwargs["env"]["GIT_ALLOW_PROTOCOL"] == ""
        assert Path(kwargs["cwd"]) != current


def test_codex_native_tracked_relative_link_obeys_release_inventory_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, parent, snapshot = _native_codex_fixture(tmp_path, monkeypatch, ("4.75.0",))
    # Establish the actual source contract, rather than assuming Git's ability
    # to track a relative link means the native release inventory permits it.
    (source / "relative-link").symlink_to("install.sh")
    subprocess.run(["git", "-C", str(source), "add", "relative-link"], check=True)
    with pytest.raises(release.ContractError, match="symbolic link"):
        release.canonical_tree_digest(source)
    files = set(subprocess.check_output(["git", "-C", str(source), "ls-files"], text=True).splitlines())
    with pytest.raises(release.ContractError, match="link|type"):
        digest = release.canonical_tracked_tree_digest(source, files)
        release.verify_native_release_inventory(source, source, digest, source_files=files)
    current = parent / "4.75.0"
    (current / "relative-link").symlink_to("install.sh")
    before = _all_cache_bytes(current)
    assert not release.restore_codex_caches(snapshot, release.Result())
    assert _all_cache_bytes(current) == before


@pytest.mark.parametrize("kind", ["missing", "content-change"])
def test_codex_current_without_git_metadata_is_verified_without_repair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str,
) -> None:
    _source, parent, snapshot = _native_codex_fixture(tmp_path, monkeypatch, ("4.75.0",))
    current = parent / "4.75.0"
    retained = tmp_path / "native-original"
    current.rename(retained)
    if kind == "content-change":
        shutil.copytree(snapshot.backup / "4.75.0", current)
        (current / "skills/example/SKILL.md").write_text("retained current content")
        before = _all_cache_bytes(current)
    result = release.Result()
    assert not release.restore_codex_caches(snapshot, result)
    if kind == "missing":
        assert not current.exists()
    else:
        assert _all_cache_bytes(current) == before
    assert (retained / ".git").is_dir()
    assert snapshot.backup.is_dir()


def test_codex_current_materialized_root_requires_immutable_source_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _source, parent, snapshot = _native_codex_fixture(tmp_path, monkeypatch, ("4.75.0",))
    current = parent / "4.75.0"
    current.rename(tmp_path / "retained-native")
    shutil.copytree(snapshot.backup / "4.75.0", current)
    before = _all_cache_bytes(current)
    unbound = release.CodexCacheSnapshot(snapshot.backup, snapshot.versions, client_owned_version="4.75.0")
    result = release.Result()
    assert not release.restore_codex_caches(unbound, result)
    assert "immutable source binding" in result.steps[-1].detail
    assert _all_cache_bytes(current) == before


def test_codex_native_repair_repeats_without_more_displacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _source, parent, snapshot = _native_codex_fixture(tmp_path, monkeypatch)
    retained = set()
    assert release._restore_codex_caches_once(snapshot, retained) == (set(), {"4.74.0"})
    assert len(retained) == 1
    before = {path: _all_cache_bytes(path) for path in [parent / "4.74.0", parent / "4.75.0", *retained]}
    assert release._restore_codex_caches_once(snapshot, retained) == (set(), set())
    assert {path: _all_cache_bytes(path) for path in before} == before
    assert set(parent.glob(".release-displaced-*")) == retained


@pytest.mark.parametrize("after_rename", [1, 2])
def test_codex_native_repair_process_death_preserves_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, after_rename: int,
) -> None:
    _source, parent, snapshot = _native_codex_fixture(tmp_path, monkeypatch)
    before = _all_cache_bytes(parent / "4.74.0")
    input_path = tmp_path / "snapshot.json"
    input_path.write_text(json.dumps({
        "backup": str(snapshot.backup), "versions": snapshot.versions,
        "client_owned_version": snapshot.client_owned_version,
        "native_sources": {version: [head, sorted(files)] for version, (head, files) in snapshot.native_sources.items()},
    }))
    script = """
import json, os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import release
data = json.loads(Path(sys.argv[3]).read_text())
snapshot = release.CodexCacheSnapshot(Path(data['backup']), tuple(data['versions']),
    client_owned_version=data['client_owned_version'],
    native_sources={version: (value[0], frozenset(value[1])) for version, value in data['native_sources'].items()})
release.plugin_cache_parent = lambda client: Path(sys.argv[2])
original = os.rename
calls = 0
def crash(source, destination):
    global calls
    original(source, destination)
    calls += 1
    if calls == int(sys.argv[4]): os._exit(77)
release.os.rename = crash
release._restore_codex_caches_once(snapshot)
"""
    proc = subprocess.run([sys.executable, "-B", "-c", script, str(Path(release.__file__).parent),
                           str(parent), str(input_path), str(after_rename)], capture_output=True, text=True, timeout=30)
    assert proc.returncode == 77, proc.stdout + proc.stderr
    recoveries = list(parent.glob(".release-displaced-4.74.0-*"))
    assert len(recoveries) == 1 and _all_cache_bytes(recoveries[0]) == before
    result = release.Result()
    assert release.restore_codex_caches(snapshot, result) is (after_rename == 2)
    assert _all_cache_bytes(recoveries[0]) == before
    if after_rename == 1:
        assert "interrupted transition" in result.steps[-1].detail
        assert not (parent / "4.74.0").exists()
        assert snapshot.backup.is_dir()
        assert len(list(parent.glob(".release-repair-4.74.0-*"))) == 1
    else:
        assert any(str(recoveries[0]) in step.detail for step in result.steps)


@pytest.mark.parametrize("change", ["nested-git", "git-link"])
def test_codex_native_repair_rechecks_ownership_after_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str,
) -> None:
    _source, parent, snapshot = _native_codex_fixture(tmp_path, monkeypatch)
    historical = parent / "4.74.0"
    original_copy = release.shutil.copytree
    external = tmp_path / "retained-git"

    def copy_and_change(source, destination, *args, **kwargs):
        value = original_copy(source, destination, *args, **kwargs)
        if Path(source) == snapshot.backup / "4.74.0":
            if change == "nested-git":
                (historical / "foreign/.git").mkdir(parents=True)
            else:
                (historical / ".git").rename(external)
                (historical / ".git").symlink_to(external, target_is_directory=True)
        return value

    monkeypatch.setattr(release.shutil, "copytree", copy_and_change)
    assert not release.restore_codex_caches(snapshot, release.Result())
    assert (historical / "skills/example/SKILL.md").read_text() == "version: 4.74.0\nhistorical\n"
    assert not list(parent.glob(".release-displaced-*"))
    assert (historical / "foreign/.git").is_dir() if change == "nested-git" else (historical / ".git").is_symlink()


def test_codex_native_current_rechecks_identity_after_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _source, parent, snapshot = _native_codex_fixture(tmp_path, monkeypatch, ("4.75.0",))
    current = parent / "4.75.0"
    retained = tmp_path / "retained-current"
    before = _all_cache_bytes(current)
    original = release.verify_native_release_inventory

    def replace_after_verification(*args, **kwargs):
        value = original(*args, **kwargs)
        current.rename(retained)
        current.mkdir()
        (current / "foreign").write_text("intruding tree")
        return value

    monkeypatch.setattr(release, "verify_native_release_inventory", replace_after_verification)
    assert not release.restore_codex_caches(snapshot, release.Result())
    assert (current / "foreign").read_text() == "intruding tree"
    assert _all_cache_bytes(retained) == before


@pytest.mark.parametrize("boundary", ["parent-link", "repository-parent", "workspace-parent", "cwd", "traversal"])
def test_codex_native_restore_refuses_unowned_boundaries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, boundary: str,
) -> None:
    _source, parent, snapshot = _native_codex_fixture(tmp_path, monkeypatch, ("4.75.0",))
    current = parent / "4.75.0"
    before = _all_cache_bytes(current)
    if boundary == "parent-link":
        alias = tmp_path / "alias"
        alias.symlink_to(parent, target_is_directory=True)
        monkeypatch.setattr(release, "plugin_cache_parent", lambda _client: alias)
    elif boundary == "repository-parent":
        (parent / ".git").mkdir()
    elif boundary == "workspace-parent":
        (parent / ".agents").mkdir()
        (parent / ".agents/repos.yaml").write_text("workspace sentinel")
    elif boundary == "cwd":
        monkeypatch.chdir(current)
    else:
        snapshot = release.CodexCacheSnapshot(snapshot.backup, ("../publisher",))
    assert not release.restore_codex_caches(snapshot, release.Result())
    assert _all_cache_bytes(current) == before
    assert snapshot.backup.is_dir()


def test_snapshot_imports_complete_untagged_peer_root_missing_from_codex(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    commit_release(source, "4.74.0", "tagged")
    codex_cache = tmp_path / "codex-cache"
    release._export_release_tag(source, "4.74.0", codex_cache / "4.74.0", current_version="4.74.0")
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


def _replacement_native_cli(tmp_path, monkeypatch):
    """Execute a declared synthetic native CLI that replaces its entire cache."""
    home = tmp_path / "isolated-home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    source, parent, _initial = _native_codex_fixture(tmp_path, monkeypatch, take_snapshot=False)
    retained = parent / (".release-displaced-4.74.0-" + "a" * 32)
    (parent / "4.74.0").rename(retained)
    (retained / "local-note").write_bytes(b"native local bytes\x00\xff")
    (retained / "local-note").chmod(0o640)
    (retained / "local-link").symlink_to("local-note")
    expected = _all_cache_bytes(retained)
    cli = tmp_path / "synthetic-codex"
    log = tmp_path / "cli.jsonl"
    cli.write_text("#!" + sys.executable + "\n" + f'''
import json, os, pathlib, shutil, subprocess, sys
parent = pathlib.Path({str(parent)!r})
source = pathlib.Path({str(source)!r})
with pathlib.Path({str(log)!r}).open('a') as handle:
    handle.write(json.dumps(sys.argv[1:]) + '\\n')
if sys.argv[1:3] == ['plugin', 'add']:
    assert parent.parent == pathlib.Path({str(tmp_path)!r}) and not parent.is_symlink()
    shutil.rmtree(parent)
    parent.mkdir()
    subprocess.run(['git', '-c', 'core.hooksPath=' + os.devnull, 'clone', '--no-local',
                    '--branch', 'v4.75.0', str(source), str(parent / '4.75.0')],
                   check=True, capture_output=True)
''')
    cli.chmod(0o755)
    monkeypatch.setattr(release, "resolve_client_binary", lambda _client: str(cli))
    monkeypatch.setattr(release, "install_codex_cache_guardian", lambda *args, **kwargs: True)
    return source, parent, retained, expected, log


def _retained_bundles(tmp_path):
    return sorted(bundle for bundle in (tmp_path / "archive-native-retained").glob("retained-*")
                  if (bundle / "intent.json").is_file()
                  and json.loads((bundle / "intent.json").read_text())["tree"].startswith(".release-displaced-"))


def test_native_parent_replacement_preserves_exact_git_local_bytes_modes_and_repeated_run(tmp_path, monkeypatch):
    source, parent, retained, expected, log = _replacement_native_cli(tmp_path, monkeypatch)
    current_before = _all_cache_bytes(parent / "4.75.0")
    result = release.Result()
    assert release.refresh_client("codex", result, False, repo=source), result.steps
    current_copies = list((tmp_path / "archive-native-retained").glob("retained-*/4.75.0"))
    assert len(current_copies) == 1 and _all_cache_bytes(current_copies[0]) == current_before
    assert len(log.read_text().splitlines()) == 2
    assert not retained.exists()
    bundle, = _retained_bundles(tmp_path)
    copy = bundle / retained.name
    assert _all_cache_bytes(copy) == expected
    record = json.loads((bundle / "manifest.json").read_text())
    assert record["state"] == "VERIFIED"
    assert record["disposition"] == "RETAINED_FOR_SEPARATE_REVIEW"
    assert record["source"] == str(retained)
    assert stat.S_IMODE(bundle.stat().st_mode) == 0o700
    assert stat.S_IMODE((bundle / "manifest.json").stat().st_mode) == 0o600
    archive = tmp_path / "archive"
    assert release._tree_bytes(archive) < release.CODEX_CACHE_ARCHIVE_BUDGET_BYTES
    assert not list(archive.rglob(".git"))
    assert any(str(bundle / "manifest.json") in step.detail for step in result.steps)
    archive_before = release.RecoveryStore.read(archive).versions
    assert release.refresh_client("codex", release.Result(), False, repo=source)
    assert _retained_bundles(tmp_path) == [bundle]
    assert _all_cache_bytes(copy) == expected
    assert release.RecoveryStore.read(archive).versions == archive_before


def test_native_refresh_waits_real_required_quiet_window_after_initial_recovery(tmp_path, monkeypatch):
    source, _parent, _retained, _expected, _log = _replacement_native_cli(tmp_path, monkeypatch)
    monkeypatch.setattr(release, "CODEX_CACHE_QUIET_SECONDS", 10.0)
    monkeypatch.setattr(release, "CODEX_CACHE_POLL_SECONDS", 1.0)
    started = time.monotonic()
    result = release.Result()
    assert release.refresh_client("codex", result, False, repo=source), result.steps
    assert time.monotonic() - started >= 10.0
    assert "10s quiet window" in result.steps[-1].detail


@pytest.mark.parametrize("churn", [False, True])
def test_initial_restore_cost_is_separate_from_bounded_genuine_churn(tmp_path, monkeypatch, churn):
    source, parent, retained, expected, _log = _replacement_native_cli(tmp_path, monkeypatch)
    monkeypatch.setattr(release, "CODEX_CACHE_QUIET_SECONDS", 10.0)
    monkeypatch.setattr(release, "CODEX_CACHE_POLL_SECONDS", 1.0)
    clock, passes, slept = [0.0], [], []
    original_once, original_restore = release._restore_codex_caches_once, release.restore_codex_caches
    def once(*args, **kwargs):
        observed = original_once(*args, **kwargs)
        passes.append(observed)
        if len(passes) == 1:
            clock[0] += 61.0  # Declared I/O latency; no Git/copy/hash operation is mocked.
        return observed
    def sleep(seconds):
        clock[0] += seconds
        slept.append(seconds)
        if churn:
            shutil.rmtree(parent / "4.74.0")
    monkeypatch.setattr(release, "_restore_codex_caches_once", once)
    monkeypatch.setattr(release, "restore_codex_caches", lambda snapshot, result:
                        original_restore(snapshot, result, clock=lambda: clock[0], sleeper=sleep))
    result = release.Result()
    assert release.refresh_client("codex", result, False, repo=source) == (not churn)
    assert passes[0] == ({"4.74.0"}, set())
    assert len(passes) >= 2 and sum(slept) >= 10.0
    if churn:
        assert clock[0] == 61.0 + release.CODEX_CACHE_SETTLE_TIMEOUT_SECONDS
        assert "quiet window" in result.steps[-1].detail
    else:
        assert clock[0] == 71.0
    bundle, = _retained_bundles(tmp_path)
    assert _all_cache_bytes(bundle / retained.name) == expected


@pytest.mark.parametrize("damage", ["foreign-git", "nested-git", "metadata-link", "external-payload-link",
                                    "root-link", "root-file", "malformed-name", "store-link", "store-inside-cache"])
def test_retained_native_ownership_and_path_refusal_precedes_every_cli_command(tmp_path, monkeypatch, damage):
    source, parent, retained, _expected, log = _replacement_native_cli(tmp_path, monkeypatch)
    sentinel = tmp_path / "external"
    sentinel.mkdir()
    (sentinel / "private").write_text("foreign sentinel")
    if damage == "foreign-git":
        subprocess.run(["git", "-C", str(retained), "checkout", "--detach", "v4.75.0"], check=True, capture_output=True)
    elif damage == "nested-git":
        (retained / "nested/.git").mkdir(parents=True)
    elif damage == "metadata-link":
        (retained / ".git/config").rename(retained / ".git/saved-config")
        (retained / ".git/config").symlink_to("saved-config")
    elif damage == "external-payload-link":
        (retained / "external-link").symlink_to(sentinel / "private")
    elif damage == "root-link":
        retained.rename(tmp_path / "original-retained")
        retained.symlink_to(tmp_path / "original-retained", target_is_directory=True)
    elif damage == "root-file":
        retained.rename(tmp_path / "original-retained")
        retained.write_text("not a directory")
    elif damage == "malformed-name":
        retained.rename(parent / ".release-displaced-unrecognized")
    elif damage == "store-link":
        (tmp_path / "archive-native-retained").symlink_to(sentinel, target_is_directory=True)
    else:
        monkeypatch.setattr(release, "codex_cache_archive", lambda: parent / "archive")
    before = _all_cache_bytes(parent)
    result = release.Result()
    assert not release.refresh_client("codex", result, False, repo=source)
    assert not log.exists()
    assert _all_cache_bytes(parent) == before
    assert (sentinel / "private").read_text() == "foreign sentinel"


@pytest.mark.parametrize("damage", ["copy-bytes", "copy-mode", "manifest", "missing-intent", "missing-copy", "copy-link", "bundle-identity"])
def test_native_recovery_corruption_after_cli_cannot_report_preservation(tmp_path, monkeypatch, damage):
    source, _parent, retained, _expected, _log = _replacement_native_cli(tmp_path, monkeypatch)
    original = release.run
    def mutate_after_native(command, cwd=None, timeout=900):
        result = original(command, cwd=cwd, timeout=timeout)
        if command[1:3] == ["plugin", "add"]:
            bundle, = _retained_bundles(tmp_path)
            tree = bundle / retained.name
            if damage == "copy-bytes":
                (tree / "local-note").write_bytes(b"corrupt")
            elif damage == "copy-mode":
                (tree / "local-note").chmod(0o600)
            elif damage == "manifest":
                (bundle / "manifest.json").write_text("{}")
            elif damage == "missing-intent":
                (bundle / "intent.json").unlink()
            elif damage == "missing-copy":
                tree.rename(tmp_path / "retained-outside-bundle")
            elif damage == "copy-link":
                tree.rename(tmp_path / "retained-outside-bundle")
                tree.symlink_to(tmp_path / "retained-outside-bundle", target_is_directory=True)
            else:
                bundle.rename(tmp_path / "original-bundle")
                shutil.copytree(tmp_path / "original-bundle", bundle, symlinks=True)
        return result
    monkeypatch.setattr(release, "run", mutate_after_native)
    result = release.Result()
    assert not release.refresh_client("codex", result, False, repo=source)
    assert "active-session cache preservation failed" in result.steps[-1].detail
    assert "recovery copy kept" in result.steps[-1].detail


def test_native_preservation_copy_interruption_retains_original_and_partial_then_retries(tmp_path, monkeypatch):
    source, _parent, retained, expected, log = _replacement_native_cli(tmp_path, monkeypatch)
    original = release.shutil.copytree
    def interrupted_copy(src, dst, *args, **kwargs):
        copied = original(src, dst, *args, **kwargs)
        if Path(dst).name == retained.name and Path(dst).parent.name.startswith("retained-"):
            raise KeyboardInterrupt("fixture interruption after native copy")
        return copied
    with monkeypatch.context() as interrupted:
        interrupted.setattr(release.shutil, "copytree", interrupted_copy)
        with pytest.raises(KeyboardInterrupt, match="fixture interruption"):
            release.refresh_client("codex", release.Result(), False, repo=source)
    assert not log.exists()
    assert _all_cache_bytes(retained) == expected
    incomplete, = _retained_bundles(tmp_path)
    assert (incomplete / "intent.json").is_file() and not (incomplete / "manifest.json").exists()
    assert release.refresh_client("codex", release.Result(), False, repo=source)
    assert incomplete in _retained_bundles(tmp_path)
    completed = [bundle for bundle in _retained_bundles(tmp_path) if (bundle / "manifest.json").is_file()]
    assert len(completed) == 1
    assert _all_cache_bytes(completed[0] / retained.name) == expected
    assert release.refresh_client("codex", release.Result(), False, repo=source)
    assert incomplete.is_dir() and len(_retained_bundles(tmp_path)) == 2


def test_native_source_identity_change_after_snapshot_refuses_cli_and_keeps_both_copies(tmp_path, monkeypatch):
    source, _parent, retained, expected, log = _replacement_native_cli(tmp_path, monkeypatch)
    original = release._preserve_native_recovery
    def replaced_after_preservation(root, commit):
        record = original(root, commit)
        if root == retained:
            root.rename(tmp_path / "original-source")
            shutil.copytree(tmp_path / "original-source", root, symlinks=True)
        return record
    monkeypatch.setattr(release, "_preserve_native_recovery", replaced_after_preservation)
    result = release.Result()
    assert not release.refresh_client("codex", result, False, repo=source)
    assert not log.exists()
    assert _all_cache_bytes(retained) == expected
    assert _all_cache_bytes(tmp_path / "original-source") == expected
    bundle, = _retained_bundles(tmp_path)
    assert _all_cache_bytes(bundle / retained.name) == expected


def test_native_copy_type_change_to_fifo_refuses_without_blocking_or_running_cli(tmp_path, monkeypatch):
    source, _parent, retained, expected, log = _replacement_native_cli(tmp_path, monkeypatch)
    original = release._native_recovery_inventory
    changed = []
    def replace_after_inventory(root):
        result = original(root)
        if root.name == retained.name and root.parent.name.startswith("retained-") and not changed:
            target = root / "local-note"
            target.unlink()
            os.mkfifo(target)
            changed.append(target)
        return result
    monkeypatch.setattr(release, "_native_recovery_inventory", replace_after_inventory)
    result = release.Result()
    assert not release.refresh_client("codex", result, False, repo=source)
    assert not log.exists() and changed
    assert _all_cache_bytes(retained) == expected
    assert "changed file type" in result.steps[-1].detail


@pytest.mark.parametrize("phase", ["copy", "after-native"])
def test_hard_process_interruption_preserves_native_recovery_and_restarts(tmp_path, monkeypatch, phase):
    source, parent, retained, expected, log = _replacement_native_cli(tmp_path, monkeypatch)
    cli = tmp_path / "synthetic-codex"
    script = tmp_path / "crash-copy.py"
    script.write_text('''
import os, pathlib, sys
sys.path.insert(0, sys.argv[1])
import release
source, parent, archive, cli = map(pathlib.Path, sys.argv[2:6])
phase = sys.argv[6]
release.plugin_cache_parent = lambda _client: parent
release.codex_cache_archive = lambda: archive
release.resolve_client_binary = lambda _client: str(cli)
release.install_codex_cache_guardian = lambda *a, **k: True
original = release.shutil.copytree
def crash(src, dst, *args, **kwargs):
    value = original(src, dst, *args, **kwargs)
    if phase == 'copy' and pathlib.Path(dst).parent.name.startswith('retained-'):
        os._exit(77)
    return value
release.shutil.copytree = crash
original_run = release.run
def crash_after_native(command, cwd=None, timeout=900):
    result = original_run(command, cwd=cwd, timeout=timeout)
    if phase == 'after-native' and command[1:3] == ['plugin', 'add']:
        os._exit(77)
    return result
release.run = crash_after_native
release.refresh_client('codex', release.Result(), False, repo=source)
''')
    process = subprocess.run([sys.executable, str(script), str(Path(release.__file__).parent),
                              str(source), str(parent), str(tmp_path / "archive"), str(cli), phase],
                             capture_output=True, text=True, timeout=30)
    assert process.returncode == 77, process.stdout + process.stderr
    incomplete, = _retained_bundles(tmp_path)
    assert (incomplete / "intent.json").is_file()
    if phase == "copy":
        assert not log.exists() and _all_cache_bytes(retained) == expected
        assert not (incomplete / "manifest.json").exists()
    else:
        assert len(log.read_text().splitlines()) == 2 and not retained.exists()
        assert (incomplete / "manifest.json").is_file()
    assert _all_cache_bytes(incomplete / retained.name) == expected
    assert release.refresh_client("codex", release.Result(), False, repo=source)
    assert incomplete.is_dir()
    completed = [bundle for bundle in _retained_bundles(tmp_path) if (bundle / "manifest.json").is_file()]
    assert len(completed) == 1 and _all_cache_bytes(completed[0] / retained.name) == expected


@pytest.mark.parametrize("missing", ["intent", "manifest", "tree", "bundle", "store", "catalog"])
def test_restart_refuses_missing_native_recovery_artifacts_before_another_cli(tmp_path, monkeypatch, missing):
    source, _parent, retained, _expected, log = _replacement_native_cli(tmp_path, monkeypatch)
    assert release.refresh_client("codex", release.Result(), False, repo=source)
    bundle, = _retained_bundles(tmp_path)
    target = {"intent": bundle / "intent.json", "manifest": bundle / "manifest.json", "tree": bundle / retained.name,
              "bundle": bundle, "store": bundle.parent, "catalog": tmp_path / "archive-native-retained.json"}[missing]
    target.rename(tmp_path / "removed-artifact")
    calls = log.read_bytes()
    result = release.Result()
    assert not release.refresh_client("codex", result, False, repo=source)
    assert log.read_bytes() == calls
    assert result.steps[-1].name == "install.codex.cache-snapshot"


def test_interrupted_copy_without_original_or_ready_recovery_refuses_restart(tmp_path, monkeypatch):
    source, _parent, retained, _expected, log = _replacement_native_cli(tmp_path, monkeypatch)
    original = release.shutil.copytree
    def interrupted_copy(src, dst, *args, **kwargs):
        value = original(src, dst, *args, **kwargs)
        if Path(dst).parent.name.startswith("retained-"):
            raise KeyboardInterrupt("fixture interruption")
        return value
    with monkeypatch.context() as interrupted:
        interrupted.setattr(release.shutil, "copytree", interrupted_copy)
        with pytest.raises(KeyboardInterrupt):
            release.refresh_client("codex", release.Result(), False, repo=source)
    retained.rename(tmp_path / "unadmitted-original")
    result = release.Result()
    assert not release.refresh_client("codex", result, False, repo=source)
    assert not log.exists()
    assert "no exact original or complete recovery" in result.steps[-1].detail


@pytest.mark.parametrize("boundary", ["plan", "store-mkdir", "bundle-mkdir", "intent", "copy", "ready", "verified"])
def test_native_preservation_publication_crashes_recover_from_exact_original(tmp_path, monkeypatch, boundary):
    source, parent, retained, expected, log = _replacement_native_cli(tmp_path, monkeypatch)
    calls = []
    def crash(point):
        if point == boundary and not calls:
            calls.append(point)
            raise KeyboardInterrupt("fixture publication boundary " + point)
    publish, write = release._publish_native_recovery_catalog, release._write_native_recovery_record
    mkdir, copytree = Path.mkdir, release.shutil.copytree
    def publish_then_crash(store, records, previous):
        value = publish(store, records, previous)
        if any(entry["intent"]["source"] == str(retained) for entry in records.values()):
            crash("verified" if any(entry["state"] == "VERIFIED" for entry in records.values()) else "plan")
        return value
    def mkdir_then_crash(path, *args, **kwargs):
        value = mkdir(path, *args, **kwargs)
        if path.name == "archive-native-retained":
            crash("store-mkdir")
        if path.name.startswith("retained-"):
            crash("bundle-mkdir")
        return value
    def write_then_crash(path, value):
        digest = write(path, value)
        if path.name in {"intent.json", "manifest.json"}:
            crash("intent" if path.name == "intent.json" else "ready")
        return digest
    def copy_then_crash(src, dst, *args, **kwargs):
        value = copytree(src, dst, *args, **kwargs)
        if Path(dst).parent.name.startswith("retained-"):
            crash("copy")
        return value
    with monkeypatch.context() as interrupted:
        interrupted.setattr(release, "_publish_native_recovery_catalog", publish_then_crash)
        interrupted.setattr(release, "_write_native_recovery_record", write_then_crash)
        interrupted.setattr(Path, "mkdir", mkdir_then_crash)
        interrupted.setattr(release.shutil, "copytree", copy_then_crash)
        with pytest.raises(KeyboardInterrupt, match="fixture publication boundary"):
            release.refresh_client("codex", release.Result(), False, repo=source)
    assert calls == [boundary] and not log.exists()
    assert _all_cache_bytes(retained) == expected
    catalog_path = tmp_path / "archive-native-retained.json"
    original_catalog = json.loads(catalog_path.read_text())["records"]
    assert original_catalog
    result = release.Result()
    assert release.refresh_client("codex", result, False, repo=source), result.steps
    assert not retained.exists()
    verified = [bundle / retained.name for bundle in _retained_bundles(tmp_path)
                if (bundle / "manifest.json").is_file()]
    assert verified and all(_all_cache_bytes(tree) == expected for tree in verified)
    # Restart again after the native source has gone: completed recovery covers
    # the original durable plan; no incomplete attempts or plans are deleted.
    assert release.refresh_client("codex", release.Result(), False, repo=source)
    assert set(original_catalog) <= set(json.loads(catalog_path.read_text())["records"])
    assert all(_all_cache_bytes(tree) == expected for tree in verified)


@pytest.mark.parametrize("name", [".release-stage-4.74.0-" + "b" * 32,
                                  ".release-repair-4.74.0-" + "b" * 32,
                                  ".release-displaced-unrecognized", ".release-private-recovery"])
def test_unknown_or_interrupted_transition_root_blocks_native_parent_replacement(tmp_path, monkeypatch, name):
    source, parent, retained, expected, log = _replacement_native_cli(tmp_path, monkeypatch)
    root = parent / name
    root.mkdir()
    (root / "private-evidence").write_bytes(b"do not discard interruption evidence")
    before = _all_cache_bytes(parent)
    result = release.Result()
    assert not release.refresh_client("codex", result, False, repo=source)
    assert "review before refresh" in result.steps[-1].detail
    assert not log.exists() and _all_cache_bytes(parent) == before
    assert _all_cache_bytes(retained) == expected


def test_transition_root_appearing_after_snapshot_blocks_first_native_command(tmp_path, monkeypatch):
    source, parent, retained, expected, log = _replacement_native_cli(tmp_path, monkeypatch)
    original = release.snapshot_codex_caches
    def inject(*args, **kwargs):
        snapshot = original(*args, **kwargs)
        assert snapshot is not None
        root = parent / (".release-stage-4.74.0-" + "b" * 32)
        root.mkdir()
        (root / "evidence").write_text("interrupted")
        return snapshot
    monkeypatch.setattr(release, "snapshot_codex_caches", inject)
    result = release.Result()
    assert not release.refresh_client("codex", result, False, repo=source)
    assert not log.exists() and _all_cache_bytes(retained) == expected


@pytest.mark.parametrize("damage", ["state-type", "records-type", "intent-type", "manifest-digest", "duplicate-key", "unknown-bundle"])
def test_malformed_native_catalog_refuses_before_any_further_cli(tmp_path, monkeypatch, damage):
    source, _parent, _retained, _expected, log = _replacement_native_cli(tmp_path, monkeypatch)
    assert release.refresh_client("codex", release.Result(), False, repo=source)
    catalog = tmp_path / "archive-native-retained.json"
    data = json.loads(catalog.read_text())
    first = next(iter(data["records"].values()))
    if damage == "state-type":
        first["state"] = {}
    elif damage == "records-type":
        data["records"] = []
    elif damage == "intent-type":
        first["intent"] = []
    elif damage == "manifest-digest":
        first["manifest_digest"] = "f" * 64
    elif damage == "unknown-bundle":
        (tmp_path / "archive-native-retained" / ("retained-" + "e" * 32)).mkdir()
    if damage == "duplicate-key":
        catalog.write_text('{"schema_version":1,"schema_version":1,"records":{}}')
    elif damage != "unknown-bundle":
        catalog.write_text(json.dumps(data))
    calls = log.read_bytes()
    result = release.Result()
    assert not release.refresh_client("codex", result, False, repo=source)
    assert calls == log.read_bytes()
    assert result.steps[-1].name == "install.codex.cache-snapshot"


@pytest.mark.parametrize("existing_target", [False, True])
def test_marketplace_created_current_generation_is_preserved_before_add(tmp_path, monkeypatch, existing_target):
    source, parent, retained, expected, log = _replacement_native_cli(tmp_path, monkeypatch)
    target = parent / "4.75.0"
    if not existing_target:
        target.rename(tmp_path / "prior-target-fixture")
    cli = Path(release.resolve_client_binary("codex"))
    original_script = cli.read_text()
    boundary = "if sys.argv[1:3] == ['plugin', 'add']:"
    appeared = tmp_path / "marketplace-generation"
    replacement = f'''if sys.argv[1:3] == ['plugin', 'marketplace']:
    shutil.rmtree(parent)
    parent.mkdir()
    subprocess.run(['git', '-c', 'core.hooksPath=' + os.devnull, 'clone', '--no-local',
                    '--branch', 'v4.75.0', str(source), str(parent / '4.75.0')],
                   check=True, capture_output=True)
    (parent / '4.75.0' / 'between-native-commands').write_bytes(b'new native generation retained evidence')
    shutil.copytree(parent / '4.75.0', pathlib.Path({str(appeared)!r}), symlinks=True)
'''
    cli.write_text(original_script.replace(boundary, replacement + boundary))
    result = release.Result()
    assert release.refresh_client("codex", result, False, repo=source), result.steps
    assert len(log.read_text().splitlines()) == 2
    bundles = tmp_path / "archive-native-retained"
    assert any(_all_cache_bytes(copy) == _all_cache_bytes(appeared)
               for copy in bundles.glob("retained-*/4.75.0"))
    assert any(_all_cache_bytes(copy) == expected
               for copy in bundles.glob("retained-*/" + retained.name))
    assert not (target / "between-native-commands").exists()
    assert (parent / "4.74.0/skills/example/SKILL.md").is_file()


@pytest.mark.parametrize("damage", ["wrong-commit", "root-link", "nested-repository", "external-link"])
def test_marketplace_current_generation_refuses_unproven_ownership(tmp_path, monkeypatch, damage):
    source, parent, _retained, _expected, log = _replacement_native_cli(tmp_path, monkeypatch)
    target = parent / "4.75.0"
    external = tmp_path / "foreign"
    external.mkdir()
    (external / "sentinel").write_text("unrelated work")
    original = release.run
    captured = []
    def native_transition(command, cwd=None, timeout=900):
        result = original(command, cwd=cwd, timeout=timeout)
        if command[1:3] == ["plugin", "marketplace"]:
            if damage == "wrong-commit":
                subprocess.run(["git", "-C", str(target), "checkout", "--detach", "v4.74.0"],
                               check=True, capture_output=True)
            elif damage == "root-link":
                target.rename(tmp_path / "original-current")
                target.symlink_to(external, target_is_directory=True)
            elif damage == "nested-repository":
                (target / "nested/.git").mkdir(parents=True)
            else:
                (target / "outside").symlink_to(external / "sentinel")
            captured.append(_all_cache_bytes(target))
        return result
    monkeypatch.setattr(release, "run", native_transition)
    result = release.Result()
    assert not release.refresh_client("codex", result, False, repo=source)
    assert len(log.read_text().splitlines()) == 1
    assert _all_cache_bytes(target) == captured[0]
    assert (external / "sentinel").read_text() == "unrelated work"


@pytest.mark.parametrize("phase", ["before", "between"])
@pytest.mark.parametrize("kind", ["plain", "git", "file", "symlink", "plain-version"])
def test_unknown_cache_child_refuses_native_mutation(tmp_path, monkeypatch, phase, kind):
    source, parent, _retained, _expected, log = _replacement_native_cli(tmp_path, monkeypatch)
    unknown = parent / ("9.99.99" if kind == "plain-version" else "foreign")
    sentinel = tmp_path / "outside-sentinel"
    sentinel.write_bytes(b"unrelated retained bytes")
    captured = []
    def create():
        if kind == "file":
            unknown.write_bytes(b"unrecognized file")
        elif kind == "symlink":
            unknown.symlink_to(sentinel)
        else:
            if kind == "git":
                subprocess.run(["git", "clone", "--no-local", str(source), str(unknown)],
                               check=True, capture_output=True)
            else:
                unknown.mkdir()
            (unknown / "local-evidence").write_bytes(b"unrecognized directory work")
            captured.append(_all_cache_bytes(unknown))
    original = release.run
    def transition(command, cwd=None, timeout=900):
        result = original(command, cwd=cwd, timeout=timeout)
        if command[1:3] == ["plugin", "marketplace"]:
            create()
        return result
    if phase == "before":
        create()
    else:
        monkeypatch.setattr(release, "run", transition)
    result = release.Result()
    assert not release.refresh_client("codex", result, False, repo=source)
    calls = log.read_text().splitlines() if log.exists() else []
    assert len(calls) == (0 if phase == "before" else 1)
    if kind == "file":
        assert unknown.read_bytes() == b"unrecognized file"
    elif kind == "symlink":
        assert unknown.is_symlink() and unknown.read_bytes() == b"unrelated retained bytes"
    else:
        assert _all_cache_bytes(unknown) == captured[0]
    assert sentinel.read_bytes() == b"unrelated retained bytes"


def test_unqualified_plain_current_generation_without_prior_root_refuses_add(tmp_path, monkeypatch):
    source, parent, _retained, _expected, log = _replacement_native_cli(tmp_path, monkeypatch)
    target = parent / "4.75.0"
    if target.exists():
        target.rename(tmp_path / "initial-current")
    original = release.run
    def transition(command, cwd=None, timeout=900):
        result = original(command, cwd=cwd, timeout=timeout)
        if command[1:3] == ["plugin", "marketplace"]:
            if target.exists():
                target.rename(tmp_path / "marketplace-current")
            target.mkdir()
            (target / "unqualified-evidence").write_bytes(b"not an admitted Git generation")
        return result
    monkeypatch.setattr(release, "run", transition)
    result = release.Result()
    assert not release.refresh_client("codex", result, False, repo=source)
    assert len(log.read_text().splitlines()) == 1
    assert (target / "unqualified-evidence").read_bytes() == b"not an admitted Git generation"


def test_unpinned_snapshot_cannot_admit_new_native_generation(tmp_path, monkeypatch):
    _source, parent, snapshot = _native_codex_fixture(tmp_path, monkeypatch)
    before = _all_cache_bytes(parent)
    unpinned = release.CodexCacheSnapshot(snapshot.backup, snapshot.versions)
    with pytest.raises(OSError, match="membership changed"):
        release._preserve_marketplace_generation(unpinned)
    assert _all_cache_bytes(parent) == before


def test_changed_materialized_history_refuses_add_and_preserves_changed_bytes(tmp_path, monkeypatch):
    source, parent, retained, _expected, log = _replacement_native_cli(tmp_path, monkeypatch)
    historical = parent / "4.74.0"
    # The CLI fixture retains its old Git root under a displaced name. A real
    # materialized historical root must also exist before the snapshot.
    shutil.copytree(retained, historical, symlinks=True, ignore=shutil.ignore_patterns(".git"))
    original = release.run
    def transition(command, cwd=None, timeout=900):
        result = original(command, cwd=cwd, timeout=timeout)
        if command[1:3] == ["plugin", "marketplace"]:
            (historical / "changed-work").write_bytes(b"new materialized evidence")
        return result
    monkeypatch.setattr(release, "run", transition)
    result = release.Result()
    assert not release.refresh_client("codex", result, False, repo=source)
    assert len(log.read_text().splitlines()) == 1
    assert (historical / "changed-work").read_bytes() == b"new materialized evidence"


@pytest.mark.parametrize("fault", ["copy", "seal", "changed-source", "changed-seal",
                                  "changed-intent", "changed-copy", "replaced-copy", "after-promotion"])
def test_materialized_preservation_failure_prevents_repair(tmp_path, monkeypatch, fault):
    parent = tmp_path / "cache"
    source = parent / "4.74.0"
    source.mkdir(parents=True)
    (source / "work").write_bytes(b"new evidence")
    backup = tmp_path / "synthesis-codex-cache-fixture"
    (backup / "4.74.0").mkdir(parents=True)
    (backup / "4.74.0/work").write_bytes(b"old version")
    snapshot = release.CodexCacheSnapshot(backup, ("4.74.0",))
    monkeypatch.setattr(release, "plugin_cache_parent", lambda client: parent)
    original_copy, original_write = release.shutil.copytree, release._write_native_recovery_record
    original_preserve, original_rename = release._preserve_materialized_recovery, release.os.rename
    def copy(src, dst, *args, **kwargs):
        result = original_copy(src, dst, *args, **kwargs)
        if Path(dst).parent.name.startswith("retained-"):
            if fault == "copy":
                raise OSError("synthetic interrupted copy")
            if fault == "changed-source":
                (source / "work").write_bytes(b"concurrent retained evidence")
        return result
    def write(path, data):
        if fault == "seal" and path.name == "manifest.json":
            raise OSError("synthetic interrupted seal")
        return original_write(path, data)
    preserved = []
    def preserve(path):
        record = original_preserve(path)
        preserved.append(record)
        if fault == "changed-seal":
            (record.tree.parent / "manifest.json").write_text("{}")
        elif fault == "changed-intent":
            (record.tree.parent / "intent.json").write_text("{}")
        elif fault == "changed-copy":
            (record.tree / "work").write_bytes(b"damaged recovery")
        elif fault == "replaced-copy":
            record.tree.rename(tmp_path / "first-copy")
            original_copy(tmp_path / "first-copy", record.tree, symlinks=True)
        return record
    def rename(src, dst):
        result = original_rename(src, dst)
        if fault == "after-promotion" and Path(src).name.startswith(".release-repair-") and Path(dst) == source:
            (preserved[-1].tree / "work").write_bytes(b"changed after promotion")
        return result
    monkeypatch.setattr(release.shutil, "copytree", copy)
    monkeypatch.setattr(release, "_write_native_recovery_record", write)
    monkeypatch.setattr(release, "_preserve_materialized_recovery", preserve)
    monkeypatch.setattr(release.os, "rename", rename)
    assert not release.restore_codex_caches(snapshot, release.Result())
    if fault == "after-promotion":
        displaced, = parent.glob(".release-displaced-4.74.0-*")
        assert (displaced / "work").read_bytes() == b"new evidence"
    else:
        assert (source / "work").read_bytes() == (b"concurrent retained evidence" if fault == "changed-source" else b"new evidence")
    assert backup.is_dir()


@pytest.mark.parametrize("failure", ["timeout", "os-error"])
def test_native_command_interruption_attempts_verified_history_restoration(tmp_path, monkeypatch, failure):
    source, parent, retained, expected, log = _replacement_native_cli(tmp_path, monkeypatch)
    original = release.run
    def interrupted(command, cwd=None, timeout=900):
        result = original(command, cwd=cwd, timeout=timeout)
        if command[1:3] == ["plugin", "add"]:
            if failure == "timeout":
                raise subprocess.TimeoutExpired(command, timeout)
            raise OSError("synthetic native result transport interruption")
        return result
    monkeypatch.setattr(release, "run", interrupted)
    result = release.Result()
    assert not release.refresh_client("codex", result, False, repo=source)
    assert len(log.read_text().splitlines()) == 2
    assert (parent / "4.74.0/skills/example/SKILL.md").is_file()
    assert any(step.name == "install.codex.cache-restore" and step.ok for step in result.steps)
    assert any(_all_cache_bytes(copy) == expected for copy in
               (tmp_path / "archive-native-retained").glob("retained-*/" + retained.name))


def test_new_native_recovery_between_commands_blocks_destructive_add(tmp_path, monkeypatch):
    source, parent, retained, _expected, log = _replacement_native_cli(tmp_path, monkeypatch)
    appeared = parent / (".release-displaced-4.74.0-" + "b" * 32)
    original = release.run
    def add_recovery_after_marketplace(command, cwd=None, timeout=900):
        result = original(command, cwd=cwd, timeout=timeout)
        if command[1:3] == ["plugin", "marketplace"]:
            shutil.copytree(retained, appeared, symlinks=True)
            (appeared / "new-private-evidence").write_bytes(b"appeared between actual native commands")
        return result
    monkeypatch.setattr(release, "run", add_recovery_after_marketplace)
    result = release.Result()
    assert not release.refresh_client("codex", result, False, repo=source)
    assert len(log.read_text().splitlines()) == 1
    assert (appeared / "new-private-evidence").read_bytes() == b"appeared between actual native commands"

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


@pytest.mark.parametrize("failure", [None, "prepare", "budget"])
def test_database_guardian_cutover_gates_destructive_native_refresh(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str | None) -> None:
    source = tmp_path / "source"
    source.mkdir()
    commit_release(source, "4.74.0", "old")
    commit_release(source, "4.75.0", "current")
    guardian_source = source / release.CACHE_GUARDIAN
    guardian_source.parent.mkdir(parents=True)
    guardian_source.write_text("fixture supervisor")
    archive = tmp_path / "recovery"
    cache = tmp_path / "cache"
    (cache / "4.74.0").mkdir(parents=True)
    monkeypatch.setattr(release, "resolve_client_binary", lambda name: "/fixture/codex")
    monkeypatch.setattr(release, "codex_cache_archive", lambda: archive)
    monkeypatch.setattr(release, "plugin_cache_parent", lambda client: cache)
    monkeypatch.setattr(release, "CODEX_CACHE_QUIET_SECONDS", 0)
    if failure == "budget":
        monkeypatch.setattr(release, "CODEX_CACHE_ARCHIVE_BUDGET_BYTES", 1)
    calls = []
    original_run = release.run
    def runner(command, cwd=None, timeout=900):
        if command[0] == "/fixture/codex" or "--prepare" in command:
            calls.append(command)
            if "--prepare" not in command:
                assert calls[0][-1] == "--prepare"
                assert set(release.RecoveryStore.read(archive).versions) == {"4.74.0", "4.75.0"}
            return subprocess.CompletedProcess(command, 1 if failure == "prepare" else 0, "ready", "")
        return original_run(command, cwd=cwd, timeout=timeout)
    monkeypatch.setattr(release, "run", runner)
    result = release.Result()
    assert release.refresh_client("codex", result, False, repo=source) == (failure is None)
    assert calls[0][-1] == "--prepare"
    assert len(calls) == (3 if failure is None else 1)
    if failure is not None:
        assert not (archive / "recovery.sqlite3").exists()


def test_contending_publisher_cannot_prepare_or_restart_guardian(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(release, "codex_cache_archive", lambda: tmp_path / "archive")
    monkeypatch.setattr(release, "resolve_client_binary", lambda name: "/fixture/codex")
    calls = []
    monkeypatch.setattr(release, "install_codex_cache_guardian", lambda *args, **kwargs: calls.append("prepare"))
    first = release._acquire_codex_cache_lock()
    try:
        result = release.Result()
        assert not release.refresh_client("codex", result, False, repo=tmp_path)
        assert calls == []
        assert result.steps[-1].name == "install.codex.cache-lock"
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


def test_commit_gate_sync_runs_installer_from_stable_pointer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    installer = tmp_path / release.GIT_HOOKS_INSTALLER
    installer.parent.mkdir(parents=True)
    installer.write_text("#!/bin/bash\necho healthy\n", encoding="utf-8")
    calls: list[tuple[list[str], Path | None, int]] = []

    def fake_run(command, cwd=None, timeout=900):
        calls.append((command, cwd, timeout))
        return subprocess.CompletedProcess(command, 0, stdout="healthy\n", stderr="")

    monkeypatch.setattr(release, "run", fake_run)
    monkeypatch.setattr(release, "stable_path", lambda: tmp_path)
    result = release.Result()

    assert release.sync_commit_gate(result, False) is True
    assert calls == [(["bash", str(installer)], None, 300)]
    step = next(step for step in result.steps if step.name == "install.commit-gate")
    assert step.ok is True
    assert step.detail == "healthy"


def test_commit_gate_sync_fails_closed_without_installer(tmp_path: Path) -> None:
    result = release.Result()

    assert release.sync_commit_gate(result, False, source=tmp_path) is False
    assert result.failed[0].name == "install.commit-gate"


def test_commit_gate_sync_reports_installer_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    installer = tmp_path / release.GIT_HOOKS_INSTALLER
    installer.parent.mkdir(parents=True)
    installer.write_text("#!/bin/bash\nexit 1\n", encoding="utf-8")

    def fake_run(command, cwd=None, timeout=900):
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="doctor failed")

    monkeypatch.setattr(release, "run", fake_run)
    result = release.Result()

    assert release.sync_commit_gate(result, False, source=tmp_path) is False
    step = result.failed[0]
    assert step.name == "install.commit-gate"
    assert "doctor failed" in step.detail


def test_commit_gate_sync_dry_run_records_without_running(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    installer = tmp_path / release.GIT_HOOKS_INSTALLER
    installer.parent.mkdir(parents=True)
    installer.write_text("#!/bin/bash\n", encoding="utf-8")
    monkeypatch.setattr(
        release, "run", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must not run"))
    )
    result = release.Result()

    assert release.sync_commit_gate(result, True, source=tmp_path) is True
    step = next(step for step in result.steps if step.name == "install.commit-gate")
    assert step.detail.startswith("dry-run: bash ")


def test_codex_refresh_restores_real_version_root_deleted_by_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_parent = tmp_path / "codex-cache"
    old_root = cache_parent / "4.74.0"
    (old_root / "hooks").mkdir(parents=True)
    (old_root / "hooks" / "hooks.json").write_text("old hook bytes\n", encoding="utf-8")

    monkeypatch.setattr(release, "plugin_cache_parent", lambda client: cache_parent)
    monkeypatch.setattr(release, "resolve_client_binary", lambda name: "/fake/codex")

    def run(command, **_kwargs):
        if command[1:3] == ["plugin", "add"]:
            shutil.rmtree(old_root)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(release, "run", run)
    result = release.Result()
    assert release.refresh_client("codex", result, dry_run=False) is True
    assert (old_root / "hooks" / "hooks.json").read_text(encoding="utf-8") == "old hook bytes\n"
    steps = {step.name: step for step in result.steps}
    assert steps["install.codex.cache-snapshot"].ok is True
    assert "1 complete version" in steps["install.codex.cache-snapshot"].detail
    assert steps["install.codex.cache-restore"].ok is True
    assert "restored 1" in steps["install.codex.cache-restore"].detail


def test_preexisting_version_symlink_refuses_refresh_without_removing_it(tmp_path, monkeypatch):
    parent = tmp_path / "cache"
    real = parent / "4.74.0"
    real.mkdir(parents=True)
    (real / "sentinel").write_text("retained")
    link = parent / "4.73.0"
    link.symlink_to(real)
    monkeypatch.setattr(release, "plugin_cache_parent", lambda client: parent)
    monkeypatch.setattr(release, "resolve_client_binary", lambda client: "/fake/codex")
    calls = []
    monkeypatch.setattr(release, "run", lambda *a, **k: calls.append(a))
    assert not release.refresh_client("codex", release.Result(), False)
    assert calls == [] and link.is_symlink()
    assert (link / "sentinel").read_text() == "retained"


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
    retained = list((tmp_path / "cache-recovery-materialized-retained").glob("retained-*/4.74.0/hooks/hooks.json"))
    assert len(retained) == 1 and retained[0].read_text() == "modified\n"


def test_codex_refresh_accepts_runtime_bytecode_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_parent = tmp_path / "codex-cache"
    old_root = cache_parent / "4.74.0"
    old_root.mkdir(parents=True)
    (old_root / "owned").write_text("before\n", encoding="utf-8")
    bytecode = old_root / "skills/example/__pycache__/hook.cpython-312.pyc"
    bytecode.parent.mkdir(parents=True)
    bytecode.write_bytes(b"before runtime\n")

    monkeypatch.setattr(release, "plugin_cache_parent", lambda client: cache_parent)
    monkeypatch.setattr(release, "resolve_client_binary", lambda name: "/fake/codex")

    def run(command, **_kwargs):
        if command[1:3] == ["plugin", "add"]:
            temporary = bytecode.with_name(f"{bytecode.name}.123456789")
            temporary.write_bytes(b"CPython atomic-write staging\n")
            bytecode.write_bytes(b"changed during refresh\n")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(release, "run", run)
    result = release.Result()

    assert release.refresh_client("codex", result, dry_run=False) is True
    restore = next(
        step for step in result.steps if step.name == "install.codex.cache-restore"
    )
    assert restore.ok is True
    assert bytecode.read_bytes() == b"changed during refresh\n"


def test_codex_refresh_atomically_replaces_unowned_extra(
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
    assert release.refresh_client("codex", result, dry_run=False) is True
    restore = next(
        step for step in result.steps if step.name == "install.codex.cache-restore"
    )
    assert restore.ok is True
    assert not (old_root / "unexpected").exists()
    retained = list((tmp_path / "cache-recovery-materialized-retained").glob("retained-*/4.74.0/unexpected"))
    assert len(retained) == 1 and retained[0].read_text() == "late\n"


def test_codex_refresh_does_not_write_through_nested_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_parent = tmp_path / "codex-cache"
    old_root = cache_parent / "4.74.0"
    package = old_root / "pkg"
    package.mkdir(parents=True)
    outside = tmp_path / "outside.py"
    outside.write_text("outside sentinel\n", encoding="utf-8")
    (package / "module.py").symlink_to(outside)
    backup = tmp_path / "synthesis-codex-cache-fixture"
    trusted = backup / "4.74.0" / "pkg/module.py"
    trusted.parent.mkdir(parents=True)
    trusted.write_text("trusted source\n", encoding="utf-8")
    snapshot = release.CodexCacheSnapshot(backup, ("4.74.0",))
    monkeypatch.setattr(release, "plugin_cache_parent", lambda client: cache_parent)
    monkeypatch.setattr(
        release, "_remove_transition_backup", lambda path: shutil.rmtree(path)
    )
    result = release.Result()

    assert release.restore_codex_caches(snapshot, result)
    assert outside.read_text(encoding="utf-8") == "outside sentinel\n"
    repaired = old_root / "pkg/module.py"
    assert repaired.is_file() and not repaired.is_symlink()
    assert repaired.read_text(encoding="utf-8") == "trusted source\n"


def test_atomic_cache_repair_rolls_back_failed_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent = tmp_path / "cache"
    source = tmp_path / "snapshot" / "4.74.0"
    destination = parent / "4.74.0"
    source.mkdir(parents=True)
    destination.mkdir(parents=True)
    (source / "marker").write_text("trusted\n", encoding="utf-8")
    (destination / "marker").write_text("original\n", encoding="utf-8")
    digests = iter(("staged", "staged", "source", "changed"))
    monkeypatch.setattr(release, "_tree_digest", lambda _path: next(digests))

    with pytest.raises(OSError, match="atomically repaired root differs"):
        release._replace_cache_root(source, destination, parent)

    assert (destination / "marker").read_text(encoding="utf-8") == "original\n"
    assert not list(parent.glob(".release-*-4.74.0-*"))


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
    write_manifests(repo, "9.9.9", "9.9.8", "9.9.9")
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


def test_acceptance_expectation_covers_both_rename_paths_and_literal_names(tmp_path):
    repository, authority = accepted_publish_fixture(tmp_path)
    base = authority.expected["change_head"]
    target = " renamed\nsource.py "
    (repository / "production.py").rename(repository / target)
    subprocess.run(["git", "-C", str(repository), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repository), "commit", "-qm", "fixture rename"], check=True)
    expected, detail = release.acceptance_expectation(repository, base, "fixture-rename")
    assert expected is not None, detail
    assert expected["changed_paths"] == sorted(["production.py", target])


def test_muse_bundle_manifest_agrees_with_siblings_and_resolves() -> None:
    repository = Path(__file__).resolve().parents[3]
    manifests = {}
    for directory in (".claude-plugin", ".codex-plugin", ".muse-plugin"):
        payload = json.loads(
            (repository / directory / "plugin.json").read_text(encoding="utf-8")
        )
        manifests[directory] = payload
    versions = {payload.get("version") for payload in manifests.values()}
    assert len(versions) == 1, versions
    names = {payload.get("name") for payload in manifests.values()}
    assert names == {"synthesis-skills"}, names
    muse = manifests[".muse-plugin"]
    assert muse.get("compat", {}).get("manifestDir") == ".muse-plugin"
    skills = muse["capabilities"]["skills"]
    assert len(skills) > 0
    for entry in skills:
        target = repository / entry["path"]
        assert target.is_file(), entry["path"]
    hooks = muse["capabilities"]["hooks"]
    assert {hook["event"] for hook in hooks} == {
        "SessionStart",
        "Stop",
        "UserPromptSubmit",
    }
    for hook in hooks:
        command = hook["command"]
        assert command[0] == "sh", hook["id"]
        script = repository / command[1]
        assert script.is_file(), hook["id"]
        assert os.access(script, os.X_OK), hook["id"]
        body = script.read_text(encoding="utf-8")
        assert "SYNTHESIS_HOOK_CLIENT=muse" in body, hook["id"]
        # The installed package is digest-pinned: a hook that lets Python
        # write __pycache__ invalidates the install on its first fire.
        assert "PYTHONDONTWRITEBYTECODE=1" in body, hook["id"]


# --- muse release stage ------------------------------------------------------


def _write_muse_bundle(
    root: Path,
    version: str,
    *,
    skill_ok: bool = True,
    hook: str = "ok",
    name: str = "synthesis-skills",
) -> Path:
    """Seed a Muse bundle tree. ``hook`` is one of absent/ok/missing/non-executable."""
    manifest_dir = root / ".muse-plugin"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    skill_rel = "skills/demo/SKILL.md"
    if skill_ok:
        skill = root / skill_rel
        skill.parent.mkdir(parents=True, exist_ok=True)
        skill.write_text("# demo\n", encoding="utf-8")
    hooks: list[dict] = []
    if hook != "absent":
        script = root / "hooks" / "muse" / "demo.sh"
        if hook != "missing":
            script.parent.mkdir(parents=True, exist_ok=True)
            script.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            if hook == "ok":
                script.chmod(script.stat().st_mode | 0o111)
        hooks = [{"id": "demo", "event": "SessionStart", "command": ["sh", "hooks/muse/demo.sh"]}]
    (manifest_dir / "plugin.json").write_text(
        json.dumps({
            "name": name,
            "version": version,
            "capabilities": {"skills": [{"id": "demo", "path": skill_rel}], "hooks": hooks},
        }),
        encoding="utf-8",
    )
    return root


def _muse_list_payload(
    *,
    version: str = "9.9.9",
    enabled: bool = True,
    cache_path: str = "/cache/muse/package",
    plugin_id: str = "synthesis-skills",
    source_path: str | None = "/recorded/bundle",
) -> str:
    record: dict = {"id": plugin_id, "version": version, "enabled": enabled, "cache_path": cache_path}
    if source_path is not None:
        record["source"] = {"path": source_path}
    return json.dumps({"plugins": [{"record": record}]})


@pytest.fixture()
def muse_repo(tmp_path: Path) -> Path:
    """Exercise the real Git archive and integrity check, outside the cache."""
    source = tmp_path / "release-source"
    write_manifests(source, "9.9.9", "9.9.9", "9.9.9")
    _write_muse_bundle(source, "9.9.9")
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=source, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=source, check=True)
    subprocess.run(["git", "config", "core.hooksPath", "/dev/null"], cwd=source, check=True)
    subprocess.run(["git", "add", "."], cwd=source, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "fixture"], cwd=source, check=True)
    return source


@pytest.mark.parametrize("foreign_kind", ["repository", "plain", "nested", "same-path"])
def test_muse_owned_refresh_rejects_foreign_tree_without_touching_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, foreign_kind: str
) -> None:
    bundles = tmp_path / "bundles"
    monkeypatch.setattr(release, "MUSE_BUNDLE_ROOT", bundles)
    staged = _write_muse_bundle(bundles / "v9.9.9", "9.9.9")
    foreign = (bundles / "nested" / "v9.9.8" if foreign_kind == "nested"
               else tmp_path / "foreign")
    foreign.mkdir(parents=True)
    (foreign / "retained-work").write_bytes(b"retained work\x00\xff")
    if foreign_kind == "repository":
        (foreign / ".git").mkdir()
        (foreign / ".git" / "config").write_text("repository sentinel\n")
    before = release._tree_digest(foreign)

    result = release.Result()
    assert not release._sync_muse_recorded_source(
        foreign, foreign if foreign_kind == "same-path" else staged,
        "9.9.9", result, False,
    )
    assert release._tree_digest(foreign) == before
    if foreign_kind == "repository":
        assert (foreign / ".git" / "config").read_text() == "repository sentinel\n"
    assert result.failed


def test_muse_owned_refresh_preserves_old_tree_when_copy_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundles = tmp_path / "bundles"
    monkeypatch.setattr(release, "MUSE_BUNDLE_ROOT", bundles)
    staged = _write_muse_bundle(bundles / "v9.9.9", "9.9.9")
    recorded = _write_muse_bundle(bundles / "v4.103.0", "9.9.8")
    (recorded / "retained-work").write_bytes(b"original retained work")
    before = release._tree_digest(recorded)
    original_copy = shutil.copytree

    def fail_copy(source, destination, *args, **kwargs):
        original_copy(source, destination, *args, **kwargs)
        if Path(source) == staged:
            raise OSError("injected full-disk failure after copy")

    monkeypatch.setattr(release.shutil, "copytree", fail_copy)
    assert not release._sync_muse_recorded_source(
        recorded, staged, "9.9.9", release.Result(), False,
    )
    assert release._tree_digest(recorded) == before


@pytest.mark.parametrize("after_rename", [1, 2])
def test_muse_owned_refresh_restores_old_tree_on_interruption(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, after_rename: int
) -> None:
    bundles = tmp_path / "bundles"
    monkeypatch.setattr(release, "MUSE_BUNDLE_ROOT", bundles)
    staged = _write_muse_bundle(bundles / "v9.9.9", "9.9.9")
    recorded = _write_muse_bundle(bundles / "v4.103.0", "9.9.8")
    (recorded / "retained-work").write_bytes(b"original retained work")
    before = release._tree_digest(recorded)
    original_rename = os.rename
    calls = 0

    def interrupt_rename(source, destination):
        nonlocal calls
        original_rename(source, destination)
        calls += 1
        if calls == after_rename:
            raise KeyboardInterrupt("injected interruption after completed rename")

    monkeypatch.setattr(release.os, "rename", interrupt_rename)
    with pytest.raises(KeyboardInterrupt):
        release._sync_muse_recorded_source(
            recorded, staged, "9.9.9", release.Result(), False,
        )
    assert release._tree_digest(recorded) == before


def test_muse_owned_refresh_retains_old_bytes_and_accepts_pinned_old_dirname(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundles = tmp_path / "bundles"
    monkeypatch.setattr(release, "MUSE_BUNDLE_ROOT", bundles)
    staged = _write_muse_bundle(bundles / "v9.9.9", "9.9.9")
    recorded = _write_muse_bundle(bundles / "v4.103.0", "9.9.8")
    (recorded / "retained-work").write_bytes(b"original retained work")
    before = release._tree_digest(recorded)
    result = release.Result()

    assert release._sync_muse_recorded_source(recorded, staged, "9.9.9", result, False)
    assert release._tree_digest(recorded) == release._tree_digest(staged)
    backups = list(bundles.glob(".release-displaced-v4.103.0-*"))
    assert len(backups) == 1
    assert release._tree_digest(backups[0]) == before
    assert str(backups[0]) in result.steps[-1].detail


def test_muse_owned_materialize_keeps_previous_bundle_on_export_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundles = tmp_path / "bundles"
    monkeypatch.setattr(release, "MUSE_BUNDLE_ROOT", bundles)
    recorded = _write_muse_bundle(bundles / "v9.9.9", "9.9.8")
    (recorded / "retained-work").write_bytes(b"original retained work")
    before = release._tree_digest(recorded)

    def fail_export(*args, **kwargs):
        raise OSError("injected archive failure")

    monkeypatch.setattr(release, "_export_release_tag", fail_export)
    assert release._materialize_muse_bundle(
        tmp_path / "source", "9.9.9", release.Result(), False,
    ) is None
    assert release._tree_digest(recorded) == before


@pytest.mark.parametrize("redirect", ["root", "ancestor", "recorded", "staged", "broken", "nested-link", "nested-loop"])
@pytest.mark.parametrize("dry_run", [False, True])
def test_muse_owned_refresh_rejects_redirects_without_modifying_targets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, redirect: str, dry_run: bool
) -> None:
    original = tmp_path / "original"
    bundles = original / "bundles"
    staged = _write_muse_bundle(bundles / "v9.9.9", "9.9.9")
    recorded = _write_muse_bundle(bundles / "v4.103.0", "9.9.8")
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "sentinel").write_bytes(b"foreign retained work")
    before = release._tree_digest(recorded)
    if redirect == "root":
        alias = tmp_path / "alias"
        alias.symlink_to(bundles, target_is_directory=True)
        bundles, recorded, staged = alias, alias / recorded.name, alias / staged.name
    elif redirect == "ancestor":
        alias = tmp_path / "alias"
        alias.symlink_to(original, target_is_directory=True)
        bundles = alias / "bundles"
        recorded, staged = bundles / recorded.name, bundles / staged.name
    elif redirect in {"recorded", "broken"}:
        alias = bundles / "v1.0.0"
        alias.symlink_to(recorded if redirect == "recorded" else foreign / "missing")
        recorded = alias
    elif redirect == "staged":
        alias = bundles / "v1.0.0"
        alias.symlink_to(staged)
        staged = alias
    elif redirect == "nested-loop":
        (recorded / "loop").symlink_to("loop")
        before = release._tree_digest(recorded)
    else:
        (recorded / "escape").symlink_to(foreign, target_is_directory=True)
        before = release._tree_digest(recorded)
    monkeypatch.setattr(release, "MUSE_BUNDLE_ROOT", bundles)
    assert not release._sync_muse_recorded_source(
        recorded, staged, "9.9.9", release.Result(), dry_run,
    )
    assert (foreign / "sentinel").read_bytes() == b"foreign retained work"
    assert release._tree_digest(original / "bundles" / "v4.103.0") == before


@pytest.mark.parametrize("protected", ["home", "cwd", "source", "repo", "workspace", "root", "relative", "traversal"])
def test_muse_owned_materialize_refuses_protected_boundaries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, protected: str
) -> None:
    parent = tmp_path / "bundles"
    destination = _write_muse_bundle(parent / "v9.9.9", "9.9.8")
    (destination / "sentinel").write_bytes(b"protected bytes")
    before = release._tree_digest(destination)
    repo = tmp_path / "source"
    if protected == "home":
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: parent))
    elif protected == "cwd":
        monkeypatch.chdir(destination)
    elif protected == "source":
        repo = destination
    elif protected == "repo":
        (destination / ".git").write_text("gitdir: retained elsewhere\n")
    elif protected == "workspace":
        (parent / ".agents").mkdir()
        (parent / ".agents" / "repos.yaml").write_text("repos: []\n")
    elif protected == "root":
        parent = Path("/")
    elif protected == "relative":
        parent = Path("relative-bundles")
    else:
        parent = parent / "unused" / ".."
    monkeypatch.setattr(release, "MUSE_BUNDLE_ROOT", parent)
    # Protected system paths are probed only in dry-run mode.
    result = release.Result()
    assert release._materialize_muse_bundle(repo, "9.9.9", result, True) is None
    assert result.failed
    assert release._tree_digest(destination) == before
    assert (destination / "sentinel").read_bytes() == b"protected bytes"
    if protected == "repo":
        assert (destination / ".git").read_text() == "gitdir: retained elsewhere\n"


@pytest.mark.parametrize("kind", ["plain", "file", "symlink", "repository", "nested-repository"])
def test_muse_owned_materialize_preserves_unowned_existing_version(
    muse_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    bundles = tmp_path / "bundles"
    bundles.mkdir()
    destination = bundles / "v9.9.9"
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "sentinel").write_bytes(b"retained foreign data")
    if kind == "file":
        destination.write_bytes(b"retained file")
    elif kind == "symlink":
        destination.symlink_to(foreign, target_is_directory=True)
    else:
        destination.mkdir()
        (destination / "sentinel").write_bytes(b"retained owned-location data")
        if kind in {"repository", "nested-repository"}:
            _write_muse_bundle(destination, "9.9.8")
            marker = destination / (".git" if kind == "repository" else "retained/.git")
            marker.mkdir(parents=True)
            (marker / "config").write_bytes(b"retained repository")
    monkeypatch.setattr(release, "MUSE_BUNDLE_ROOT", bundles)
    assert release._materialize_muse_bundle(muse_repo, "9.9.9", release.Result(), False) is None
    assert (foreign / "sentinel").read_bytes() == b"retained foreign data"
    if kind == "file":
        assert destination.read_bytes() == b"retained file"
    elif kind == "symlink":
        assert destination.is_symlink()
    else:
        assert (destination / "sentinel").read_bytes() == b"retained owned-location data"
        if kind in {"repository", "nested-repository"}:
            assert (marker / "config").read_bytes() == b"retained repository"


@pytest.mark.parametrize("failure", ["copy-corruption", "promote-failure", "installed-corruption", "rollback-failure"])
def test_muse_owned_refresh_retains_previous_tree_across_failed_transitions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    bundles = tmp_path / "bundles"
    monkeypatch.setattr(release, "MUSE_BUNDLE_ROOT", bundles)
    staged = _write_muse_bundle(bundles / "v9.9.9", "9.9.9")
    recorded = _write_muse_bundle(bundles / "v4.103.0", "9.9.8")
    (recorded / "retained-work").write_bytes(b"old work survives")
    before = release._tree_digest(recorded)
    original_copy = shutil.copytree
    original_rename = os.rename
    calls = 0

    def copy_corrupt(source, destination, *args, **kwargs):
        returned = original_copy(source, destination, *args, **kwargs)
        if Path(source) == staged:
            (Path(destination) / "skills/demo/SKILL.md").write_bytes(b"corrupt staged bytes")
        return returned

    def fail_rename(source, destination):
        nonlocal calls
        calls += 1
        if failure in {"promote-failure", "rollback-failure"} and calls == 2:
            raise OSError("injected promotion failure")
        if failure == "rollback-failure" and calls == 3:
            raise OSError("injected rollback failure")
        original_rename(source, destination)
        if failure == "installed-corruption" and calls == 2:
            (Path(destination) / "skills/demo/SKILL.md").write_bytes(b"corrupt installed bytes")

    if failure == "copy-corruption":
        monkeypatch.setattr(release.shutil, "copytree", copy_corrupt)
    else:
        monkeypatch.setattr(release.os, "rename", fail_rename)
    result = release.Result()
    assert not release._sync_muse_recorded_source(recorded, staged, "9.9.9", result, False)
    if failure == "rollback-failure":
        backups = list(bundles.glob(".release-displaced-v4.103.0-*"))
        assert len(backups) == 1 and release._tree_digest(backups[0]) == before
        assert str(backups[0]) in result.steps[-1].detail
    else:
        assert release._tree_digest(recorded) == before


@pytest.mark.parametrize("after_rename", [1, 2])
def test_muse_owned_refresh_preserves_recovery_after_process_death(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, after_rename: int
) -> None:
    bundles = tmp_path / "bundles"
    monkeypatch.setattr(release, "MUSE_BUNDLE_ROOT", bundles)
    staged = _write_muse_bundle(bundles / "v9.9.9", "9.9.9")
    recorded = _write_muse_bundle(bundles / "v4.103.0", "9.9.8")
    (recorded / "retained-work").write_bytes(b"old work survives process death")
    before = release._tree_digest(recorded)
    script = """
import os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import release
release.MUSE_BUNDLE_ROOT = Path(sys.argv[2])
original_rename = os.rename
calls = 0
def die_after_rename(source, destination):
    global calls
    original_rename(source, destination)
    calls += 1
    if calls == int(sys.argv[3]):
        os._exit(77)
release.os.rename = die_after_rename
release._sync_muse_recorded_source(
    release.MUSE_BUNDLE_ROOT / 'v4.103.0',
    release.MUSE_BUNDLE_ROOT / 'v9.9.9', '9.9.9', release.Result(), False)
"""
    process = subprocess.run(
        [sys.executable, "-B", "-c", script, str(Path(release.__file__).parent), str(bundles), str(after_rename)],
        capture_output=True, text=True, timeout=20,
    )
    assert process.returncode == 77, process.stderr
    backups = list(bundles.glob(".release-displaced-v4.103.0-*"))
    assert len(backups) == 1 and release._tree_digest(backups[0]) == before
    result = release.Result()
    if after_rename == 1:
        assert not recorded.exists()
        assert not release._sync_muse_recorded_source(recorded, staged, "9.9.9", result, False)
        assert "retained recovery tree" in result.steps[-1].detail
    else:
        assert release._tree_digest(recorded) == release._tree_digest(staged)
        assert release._sync_muse_recorded_source(recorded, staged, "9.9.9", result, False)
        assert release._tree_digest(backups[0]) == before


@pytest.mark.parametrize("failure", ["wrong-bytes", "missing-hook", "interruption"])
def test_muse_owned_materialize_verifies_export_before_displacing_old_tree(
    muse_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    bundles = tmp_path / "bundles"
    monkeypatch.setattr(release, "MUSE_BUNDLE_ROOT", bundles)
    previous = _write_muse_bundle(bundles / "v9.9.9", "9.9.8")
    (previous / "retained-work").write_bytes(b"old bundle work")
    before = release._tree_digest(previous)
    original_export = release._export_release_tag

    def corrupted_export(repo, version, destination, **kwargs):
        exported = original_export(repo, version, destination, **kwargs)
        if failure == "interruption":
            raise KeyboardInterrupt("injected interrupted export")
        if failure == "wrong-bytes":
            (destination / "skills/demo/SKILL.md").write_bytes(b"plausible but incorrect export")
        else:
            (destination / "hooks/muse/demo.sh").unlink()
        return exported

    monkeypatch.setattr(release, "_export_release_tag", corrupted_export)
    if failure == "interruption":
        with pytest.raises(KeyboardInterrupt):
            release._materialize_muse_bundle(muse_repo, "9.9.9", release.Result(), False)
    else:
        assert release._materialize_muse_bundle(muse_repo, "9.9.9", release.Result(), False) is None
    assert release._tree_digest(previous) == before
    assert not list(bundles.glob(".release-displaced-*"))


def test_muse_owned_refresh_rechecks_ancestor_after_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundles = tmp_path / "bundles"
    monkeypatch.setattr(release, "MUSE_BUNDLE_ROOT", bundles)
    staged = _write_muse_bundle(bundles / "v9.9.9", "9.9.9")
    recorded = _write_muse_bundle(bundles / "v4.103.0", "9.9.8")
    (recorded / "retained-work").write_bytes(b"old tree")
    before = release._tree_digest(recorded)
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "sentinel").write_bytes(b"foreign tree")
    moved = tmp_path / "retained-original-parent"
    original_copy = shutil.copytree

    def redirect_parent(source, destination, *args, **kwargs):
        returned = original_copy(source, destination, *args, **kwargs)
        if Path(source) == staged:
            os.rename(bundles, moved)
            bundles.symlink_to(foreign, target_is_directory=True)
        return returned

    monkeypatch.setattr(release.shutil, "copytree", redirect_parent)
    assert not release._sync_muse_recorded_source(recorded, staged, "9.9.9", release.Result(), False)
    assert release._tree_digest(moved / recorded.name) == before
    assert list(foreign.iterdir()) == [foreign / "sentinel"]
    assert (foreign / "sentinel").read_bytes() == b"foreign tree"


@pytest.mark.parametrize("intrusion", ["parent-redirect", "new-destination", "replacement-destination"])
def test_muse_owned_refresh_preserves_intruding_tree_between_renames(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, intrusion: str
) -> None:
    bundles = tmp_path / "bundles"
    monkeypatch.setattr(release, "MUSE_BUNDLE_ROOT", bundles)
    staged = _write_muse_bundle(bundles / "v9.9.9", "9.9.9")
    recorded = _write_muse_bundle(bundles / "v4.103.0", "9.9.8")
    (recorded / "retained-work").write_bytes(b"original work")
    before = release._tree_digest(recorded)
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    foreign_recorded = foreign / recorded.name
    foreign_recorded.mkdir()
    (foreign_recorded / "foreign-work").write_bytes(b"foreign work")
    moved = tmp_path / "retained-original-parent"
    original_rename = os.rename
    calls = 0

    def intrude_after_rename(source, destination):
        nonlocal calls
        original_rename(source, destination)
        calls += 1
        if calls == 1 and intrusion == "parent-redirect":
            original_rename(bundles, moved)
            bundles.symlink_to(foreign, target_is_directory=True)
        elif calls == 1 and intrusion == "new-destination":
            original_rename(foreign_recorded, recorded)
        elif calls == 2 and intrusion == "replacement-destination":
            original_rename(recorded, tmp_path / "retained-proposed-install")
            original_rename(foreign_recorded, recorded)

    monkeypatch.setattr(release.os, "rename", intrude_after_rename)
    assert not release._sync_muse_recorded_source(recorded, staged, "9.9.9", release.Result(), False)
    preserved_parent = moved if intrusion == "parent-redirect" else bundles
    recovery = list(preserved_parent.glob(".release-displaced-v4.103.0-*"))
    assert len(recovery) == 1 and release._tree_digest(recovery[0]) == before
    assert (recorded / "foreign-work").read_bytes() == b"foreign work"


def test_muse_owned_refresh_refuses_concurrent_writer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundles = tmp_path / "bundles"
    monkeypatch.setattr(release, "MUSE_BUNDLE_ROOT", bundles)
    staged = _write_muse_bundle(bundles / "v9.9.9", "9.9.9")
    recorded = _write_muse_bundle(bundles / "v4.103.0", "9.9.8")
    before = release._tree_digest(recorded)
    with (bundles / ".release.lock").open("w") as handle:
        release.fcntl.flock(handle.fileno(), release.fcntl.LOCK_EX | release.fcntl.LOCK_NB)
        assert not release._sync_muse_recorded_source(recorded, staged, "9.9.9", release.Result(), False)
    assert release._tree_digest(recorded) == before
    assert not list(bundles.glob(".release-displaced-*"))


@pytest.mark.parametrize("kind", ["absolute-skill", "traversing-skill", "absolute-hook", "escaping-link"])
def test_muse_owned_bundle_completeness_rejects_capability_escape(tmp_path: Path, kind: str) -> None:
    root = _write_muse_bundle(tmp_path / "bundle", "9.9.9")
    external = tmp_path / "external"
    external.write_text("#!/bin/sh\nexit 0\n")
    external.chmod(0o755)
    manifest_path = root / ".muse-plugin/plugin.json"
    manifest = json.loads(manifest_path.read_text())
    if kind == "absolute-hook":
        manifest["capabilities"]["hooks"][0]["command"][1] = str(external)
    elif kind == "escaping-link":
        link = root / "external-skill"
        link.symlink_to(external)
        manifest["capabilities"]["skills"][0]["path"] = link.name
    else:
        manifest["capabilities"]["skills"][0]["path"] = str(external) if kind == "absolute-skill" else "../external"
    manifest_path.write_text(json.dumps(manifest))
    assert release._muse_bundle_completeness(root, "9.9.9")[0] is False
    assert external.read_text() == "#!/bin/sh\nexit 0\n"


def test_muse_owned_native_update_observes_verified_source_and_retained_old_work(
    muse_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundles = tmp_path / "bundles"
    monkeypatch.setattr(release, "MUSE_BUNDLE_ROOT", bundles)
    recorded = _write_muse_bundle(bundles / "v4.103.0", "9.9.8")
    (recorded / "retained-work").write_bytes(b"local retained bytes")
    calls = tmp_path / "native-calls.jsonl"
    binary = tmp_path / "muse-fixture"
    binary.write_text(
        f"#!{sys.executable}\n"
        "import json, sys\nfrom pathlib import Path\n"
        f"recorded = Path({str(recorded)!r})\n"
        f"with Path({str(calls)!r}).open('a') as handle: handle.write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "if sys.argv[1:3] == ['plugins', 'list']:\n"
        f"    print({_muse_list_payload(source_path=str(recorded), version='9.9.8')!r})\n"
        "elif sys.argv[1:3] == ['plugins', 'update']:\n"
        "    assert json.loads((recorded / '.muse-plugin/plugin.json').read_text())['version'] == '9.9.9'\n"
        "    assert (recorded / 'skills/demo/SKILL.md').read_text() == '# demo\\n'\n"
        "    backups = list(recorded.parent.glob('.release-displaced-v4.103.0-*'))\n"
        "    assert len(backups) == 1\n"
        "    assert (backups[0] / 'retained-work').read_bytes() == b'local retained bytes'\n"
        "    print('{}')\n"
        "else:\n    raise SystemExit(42)\n"
    )
    binary.chmod(0o755)
    monkeypatch.setattr(release, "resolve_client_binary", lambda _name: str(binary))
    source_git = (muse_repo / ".git" / "HEAD").read_bytes()
    assert release.refresh_client("muse", release.Result(), False, repo=muse_repo)
    assert [json.loads(line)[:2] for line in calls.read_text().splitlines()] == [
        ["plugins", "list"], ["plugins", "update"],
    ]
    assert release.content_digest_report(muse_repo, recorded)[0]
    assert (muse_repo / ".git" / "HEAD").read_bytes() == source_git


@pytest.mark.parametrize("kind", ["parent-link", "target-link", "repository", "cwd"])
def test_cache_transition_cleanup_refuses_unsafe_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    parent = tmp_path / "parent"
    target = parent / ".release-export-fixture"
    target.mkdir(parents=True)
    (target / "sentinel").write_bytes(b"must survive")
    original = target
    if kind == "parent-link":
        alias = tmp_path / "alias"
        alias.symlink_to(parent, target_is_directory=True)
        parent, target = alias, alias / target.name
    elif kind == "target-link":
        target = parent / ".release-export-link"
        target.symlink_to(original, target_is_directory=True)
    elif kind == "repository":
        (target / ".git").mkdir()
    else:
        monkeypatch.chdir(target)
    with pytest.raises(OSError):
        release._remove_cache_transition_tree(target, parent, ".release-export-")
    assert (original / "sentinel").read_bytes() == b"must survive"


def _fake_muse_binary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, payload: str, exit_code: int = 0
) -> Path:
    script = tmp_path / "bin" / "muse"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(f"#!/bin/sh\necho '{payload}'\nexit {exit_code}\n", encoding="utf-8")
    script.chmod(script.stat().st_mode | 0o111)
    monkeypatch.setattr(release, "resolve_client_binary", lambda name: str(script))
    return script


def test_source_version_fails_closed_when_only_muse_disagrees(repo: Path) -> None:
    write_manifests(repo, "9.9.9", "9.9.9", "9.9.8")
    version, detail = release.source_version(repo)
    assert version is None
    assert "9.9.8" in detail


def test_source_version_fails_closed_when_muse_lacks_a_version(repo: Path) -> None:
    write_manifests(repo, "9.9.9", "9.9.9", None)
    version, _ = release.source_version(repo)
    assert version is None


def test_muse_manifest_joins_the_release_gate() -> None:
    assert ".muse-plugin/plugin.json" in release.MANIFESTS
    assert len(release.MANIFESTS) == 3


def test_muse_reported_version_parses_list_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_muse_binary(tmp_path, monkeypatch, _muse_list_payload())
    assert release.client_reported_version("muse") == ("9.9.9", "/cache/muse/package")


def test_muse_reported_version_ignores_disabled_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_muse_binary(tmp_path, monkeypatch, _muse_list_payload(enabled=False))
    assert release.client_reported_version("muse") == (None, None)


def test_muse_reported_version_ignores_foreign_plugin_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_muse_binary(tmp_path, monkeypatch, _muse_list_payload(plugin_id="other-plugin"))
    assert release.client_reported_version("muse") == (None, None)


def test_muse_reported_version_none_on_malformed_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_muse_binary(tmp_path, monkeypatch, "not json at all")
    assert release.client_reported_version("muse") == (None, None)


def test_muse_reported_version_none_when_command_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_muse_binary(tmp_path, monkeypatch, _muse_list_payload(), exit_code=1)
    assert release.client_reported_version("muse") == (None, None)


def test_muse_refresh_dry_run_syncs_then_updates_when_recorded(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorded = tmp_path / "bundles" / "v9.9.8"
    _fake_muse_binary(tmp_path, monkeypatch, _muse_list_payload(source_path=str(recorded)))
    monkeypatch.setattr(release, "MUSE_BUNDLE_ROOT", tmp_path / "bundles")
    result = release.Result()
    assert release.refresh_client("muse", result, dry_run=True, repo=repo) is True
    names = [s.name for s in result.steps]
    assert names.index("install.muse.bundle") < names.index("install.muse.sync")
    assert names.index("install.muse.sync") < names.index("install.muse.update")
    bundle_detail = next(s.detail for s in result.steps if s.name == "install.muse.bundle")
    assert "v9.9.9" in bundle_detail
    update_detail = next(s.detail for s in result.steps if s.name == "install.muse.update")
    assert "plugins update" in update_detail
    assert not (tmp_path / "bundles").exists()
    assert not recorded.exists()


def test_muse_refresh_dry_run_installs_fresh_when_no_record(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_muse_binary(tmp_path, monkeypatch, "{}")
    monkeypatch.setattr(release, "MUSE_BUNDLE_ROOT", tmp_path / "bundles")
    result = release.Result()
    assert release.refresh_client("muse", result, dry_run=True, repo=repo) is True
    names = [s.name for s in result.steps]
    assert "install.muse.install" in names
    assert "install.muse.sync" not in names
    assert not (tmp_path / "bundles").exists()


def test_muse_refresh_fails_closed_without_binary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(release, "resolve_client_binary", lambda name: None)
    result = release.Result()
    assert release.refresh_client("muse", result, dry_run=True) is False
    assert result.failed


def test_muse_refresh_fails_closed_without_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(release, "resolve_client_binary", lambda name: "/fake/muse")
    result = release.Result()
    assert release.refresh_client("muse", result, dry_run=True) is False
    names = {s.name: s.ok for s in result.steps}
    assert names["install.muse"] is False


def test_muse_refresh_fails_closed_when_manifests_disagree(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_manifests(repo, "9.9.9", "9.9.9", "9.9.8")
    monkeypatch.setattr(release, "resolve_client_binary", lambda name: "/fake/muse")
    result = release.Result()
    assert release.refresh_client("muse", result, dry_run=True, repo=repo) is False
    assert result.failed


def test_muse_refresh_materializes_bundle_and_installs(
    muse_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_muse_binary(tmp_path, monkeypatch, "{}")
    monkeypatch.setattr(release, "MUSE_BUNDLE_ROOT", tmp_path / "bundles")

    result = release.Result()
    assert release.refresh_client("muse", result, dry_run=False, repo=muse_repo) is True
    bundle = tmp_path / "bundles" / "v9.9.9"
    assert (bundle / ".muse-plugin" / "plugin.json").is_file()
    names = {s.name: s.ok for s in result.steps}
    assert names["install.muse.bundle"] is True
    assert names["install.muse.install"] is True


def test_muse_refresh_reuses_complete_bundle(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_muse_binary(tmp_path, monkeypatch, "{}")
    bundles = tmp_path / "bundles"
    monkeypatch.setattr(release, "MUSE_BUNDLE_ROOT", bundles)
    source = _write_muse_bundle(tmp_path / "release-source", "9.9.9")
    for manifest in release.MANIFESTS[:2]:
        target = source / manifest
        target.parent.mkdir()
        shutil.copy2(repo / manifest, target)
    shutil.copytree(source, bundles / "v9.9.9")

    def exploding_export(*args: object, **kwargs: object) -> set[str]:
        raise AssertionError("complete bundle must be reused, not re-exported")

    monkeypatch.setattr(release, "_export_release_tag", exploding_export)
    result = release.Result()
    assert release.refresh_client("muse", result, dry_run=False, repo=source) is True
    names = [s.name for s in result.steps]
    assert "install.muse.bundle-replace" not in names


def test_muse_refresh_replaces_complete_bundle_on_content_drift(
    muse_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Same-version commits move bytes without moving the label: a
    structurally complete bundle whose content drifted must be replaced."""
    _fake_muse_binary(tmp_path, monkeypatch, "{}")
    bundles = tmp_path / "bundles"
    monkeypatch.setattr(release, "MUSE_BUNDLE_ROOT", bundles)
    _write_muse_bundle(bundles / "v9.9.9", "9.9.9")
    skill = muse_repo / "skills" / "demo" / "SKILL.md"
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text("# demo revised\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=muse_repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "fixture update"], cwd=muse_repo, check=True)

    result = release.Result()
    assert release.refresh_client("muse", result, dry_run=False, repo=muse_repo) is True
    names = [s.name for s in result.steps]
    assert "install.muse.bundle-replace" in names


def test_muse_refresh_replaces_incomplete_bundle(
    muse_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_muse_binary(tmp_path, monkeypatch, "{}")
    bundles = tmp_path / "bundles"
    monkeypatch.setattr(release, "MUSE_BUNDLE_ROOT", bundles)
    _write_muse_bundle(bundles / "v9.9.9", "9.9.8")

    result = release.Result()
    assert release.refresh_client("muse", result, dry_run=False, repo=muse_repo) is True
    names = [s.name for s in result.steps]
    assert "install.muse.bundle-replace" in names
    ok, _ = release._muse_bundle_completeness(bundles / "v9.9.9", "9.9.9")
    assert ok is True


def test_muse_refresh_fails_closed_when_install_command_fails(
    muse_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_muse_binary(tmp_path, monkeypatch, "boom", exit_code=1)
    monkeypatch.setattr(release, "MUSE_BUNDLE_ROOT", tmp_path / "bundles")

    result = release.Result()
    assert release.refresh_client("muse", result, dry_run=False, repo=muse_repo) is False
    names = {s.name: s.ok for s in result.steps}
    assert names["install.muse.bundle"] is True
    assert names["install.muse.install"] is False


def test_muse_bundle_completeness_rejects_structural_gaps(tmp_path: Path) -> None:
    ok, detail = release._muse_bundle_completeness(tmp_path / "absent", "9.9.9")
    assert ok is False
    bad_version = _write_muse_bundle(tmp_path / "bad-version", "9.9.8")
    ok, detail = release._muse_bundle_completeness(bad_version, "9.9.9")
    assert ok is False and "9.9.8" in detail
    bad_name = _write_muse_bundle(tmp_path / "bad-name", "9.9.9", name="other")
    ok, _ = release._muse_bundle_completeness(bad_name, "9.9.9")
    assert ok is False
    missing_skill = _write_muse_bundle(tmp_path / "missing-skill", "9.9.9", skill_ok=False)
    ok, detail = release._muse_bundle_completeness(missing_skill, "9.9.9")
    assert ok is False and "skills/demo/SKILL.md" in detail
    missing_hook = _write_muse_bundle(tmp_path / "missing-hook", "9.9.9", hook="missing")
    ok, _ = release._muse_bundle_completeness(missing_hook, "9.9.9")
    assert ok is False
    dark_hook = _write_muse_bundle(tmp_path / "dark-hook", "9.9.9", hook="non-executable")
    ok, _ = release._muse_bundle_completeness(dark_hook, "9.9.9")
    assert ok is False
    good = _write_muse_bundle(tmp_path / "good", "9.9.9")
    ok, detail = release._muse_bundle_completeness(good, "9.9.9")
    assert ok is True and "1 skills" in detail


def test_muse_deep_verify_passes_when_report_disk_and_content_agree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "bundle" / "v4.30.1"
    source = tmp_path / "source"
    (root / ".muse-plugin").mkdir(parents=True)
    (root / ".muse-plugin" / "plugin.json").write_text(
        json.dumps({"version": "4.30.1"}), encoding="utf-8"
    )
    _seed_content(source, root)
    monkeypatch.setattr(release, "client_reported_version", lambda client: ("4.30.1", str(root)))
    monkeypatch.setattr(release, "installed_root", lambda client, version: root)
    result = release.Result()
    assert release.deep_verify("muse", "4.30.1", result, repo=source) is True


def test_muse_deep_verify_reads_the_muse_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The on-disk leg must consult .muse-plugin, not a sibling manifest."""
    root = tmp_path / "bundle" / "v4.30.1"
    (root / ".codex-plugin").mkdir(parents=True)
    (root / ".codex-plugin" / "plugin.json").write_text(
        json.dumps({"version": "4.30.1"}), encoding="utf-8"
    )
    monkeypatch.setattr(release, "client_reported_version", lambda client: ("4.30.1", str(root)))
    monkeypatch.setattr(release, "installed_root", lambda client, version: tmp_path / "absent")
    result = release.Result()
    assert release.deep_verify("muse", "4.30.1", result) is False
    names = {s.name: s.ok for s in result.steps}
    assert names["verify.muse.reported"] is True
    assert names["verify.muse.on-disk"] is False


def test_muse_refresh_syncs_recorded_source_then_updates(
    muse_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Muse refuses install-from-new-path over an existing record, so the
    stage syncs the staged export into the recorded path and updates."""
    recorded = tmp_path / "bundles" / "v4.103.0"
    _write_muse_bundle(recorded, "9.9.8")
    _fake_muse_binary(tmp_path, monkeypatch, _muse_list_payload(source_path=str(recorded)))
    monkeypatch.setattr(release, "MUSE_BUNDLE_ROOT", tmp_path / "bundles")

    result = release.Result()
    assert release.refresh_client("muse", result, dry_run=False, repo=muse_repo) is True
    names = {s.name: s.ok for s in result.steps}
    assert names["install.muse.sync"] is True
    assert names["install.muse.update"] is True
    ok, _ = release._muse_bundle_completeness(recorded, "9.9.9")
    assert ok is True


def test_muse_refresh_skips_sync_when_recorded_matches_staged(
    muse_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundles = tmp_path / "bundles"
    _fake_muse_binary(
        tmp_path, monkeypatch, _muse_list_payload(source_path=str(bundles / "v9.9.9"))
    )
    monkeypatch.setattr(release, "MUSE_BUNDLE_ROOT", bundles)

    result = release.Result()
    assert release.refresh_client("muse", result, dry_run=False, repo=muse_repo) is True
    sync_detail = next(s.detail for s in result.steps if s.name == "install.muse.sync")
    assert "already stages" in sync_detail


def test_muse_refresh_refuses_symlinked_recorded_source(
    muse_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "target"
    target.mkdir()
    recorded = tmp_path / "recorded"
    recorded.symlink_to(target)
    _fake_muse_binary(tmp_path, monkeypatch, _muse_list_payload(source_path=str(recorded)))
    monkeypatch.setattr(release, "MUSE_BUNDLE_ROOT", tmp_path / "bundles")

    result = release.Result()
    assert release.refresh_client("muse", result, dry_run=False, repo=muse_repo) is False
    names = {s.name: s.ok for s in result.steps}
    assert names["install.muse.sync"] is False
    assert target.is_dir() and recorded.is_symlink()


def test_muse_refresh_refuses_relative_recorded_source(
    muse_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_muse_binary(tmp_path, monkeypatch, _muse_list_payload(source_path="relative/bundle"))
    monkeypatch.setattr(release, "MUSE_BUNDLE_ROOT", tmp_path / "bundles")

    result = release.Result()
    assert release.refresh_client("muse", result, dry_run=False, repo=muse_repo) is False
    names = {s.name: s.ok for s in result.steps}
    assert names["install.muse.record"] is False


def test_muse_refresh_fails_closed_when_record_is_unreadable(
    muse_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(release, "resolve_client_binary", lambda name: str(tmp_path / "missing" / "muse"))
    monkeypatch.setattr(release, "MUSE_BUNDLE_ROOT", tmp_path / "bundles")

    result = release.Result()
    assert release.refresh_client("muse", result, dry_run=False, repo=muse_repo) is False
    names = {s.name: s.ok for s in result.steps}
    assert names["install.muse.record"] is False


def test_muse_deep_verify_checks_loaded_bytes_not_the_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A fresh staged bundle must not vouch for stale loaded bytes: the
    content leg compares the reported cache path first."""
    bundle = tmp_path / "bundles" / "v4.30.1"
    loaded = tmp_path / "cache" / "package"
    source = tmp_path / "source"
    for root in (bundle, loaded):
        (root / ".muse-plugin").mkdir(parents=True)
        (root / ".muse-plugin" / "plugin.json").write_text(
            json.dumps({"version": "4.30.1"}), encoding="utf-8"
        )
    _seed_content(source, bundle)
    _seed_content(source, loaded, drift=True)
    monkeypatch.setattr(release, "client_reported_version", lambda client: ("4.30.1", str(loaded)))
    monkeypatch.setattr(release, "installed_root", lambda client, version: bundle)
    result = release.Result()
    assert release.deep_verify("muse", "4.30.1", result, repo=source) is False
    names = {s.name: s.ok for s in result.steps}
    assert names["verify.muse.reported"] is True
    assert names["verify.muse.on-disk"] is True
    assert names["verify.muse.content"] is False


def test_runner_failure_detail_names_unmatched_cases():
    receipt = {
        "ok": False,
        "cases": [
            {"id": "release-version-metadata", "matched": True, "stderr": "", "stdout": ""},
            {
                "id": "entrypoint-hooks-declared",
                "matched": False,
                "stderr": "FAILED test_x - AssertionError: boom",
                "stdout": "",
            },
        ],
    }
    detail = release._runner_failure_detail(json.dumps(receipt, indent=2))
    assert detail != "}"
    assert "entrypoint-hooks-declared" in detail
    assert "boom" in detail
    assert "1 case(s) unmatched" in detail


def test_runner_failure_detail_reports_receipt_errors():
    detail = release._runner_failure_detail(json.dumps({"errors": ["no manifest", "bad base"]}))
    assert detail == "no manifest; bad base"


def test_runner_failure_detail_falls_back_past_bare_braces():
    assert release._runner_failure_detail('{\n  boom\n}') == "boom"
    assert release._runner_failure_detail("") == "acceptance runner failed"
    assert release._runner_failure_detail("{}\n}") == "acceptance runner failed"
    assert release._runner_failure_detail('{"ok": false}') == "acceptance runner failed"

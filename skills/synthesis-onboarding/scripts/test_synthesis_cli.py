#!/usr/bin/env python3
"""Public CLI contract tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS.parents[2]
sys.path.insert(0, str(SCRIPTS))

import synthesis_cli  # noqa: E402
import system_contract  # noqa: E402
from test_onboard import Sandbox  # noqa: E402


def commit_fixture_repo(path: Path) -> None:
    env = dict(os.environ)
    env.update(
        {
            "GIT_AUTHOR_NAME": "Fixture",
            "GIT_AUTHOR_EMAIL": "fixture@example.test",
            "GIT_COMMITTER_NAME": "Fixture",
            "GIT_COMMITTER_EMAIL": "fixture@example.test",
        }
    )
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", "-C", str(path), "commit", "-q", "-m", "fixture"],
        env=env,
        check=True,
    )


def verified_uninstall_engine(argv: list[str]) -> dict:
    return {
        "engine": "fixture",
        "counts": {"ok": 1},
        "steps": [
            {
                "phase": "uninstall-verification",
                "status": "ok",
                "uninstall_verified": True,
            }
        ],
        "exit": 0,
    }


def full_configuration() -> dict:
    return synthesis_cli.onboard.personal_configuration_from_answers(
        {
            "workspace": "example-user",
            "display_name": "Example User",
            "timezone": "UTC",
            "tone": ["direct"],
            "avoid_phrases": [],
            "git_name": "",
            "git_email": "",
            "inbox_cleanup": False,
        }
    )


def test_help_exposes_every_declared_command(capsys) -> None:
    parser = synthesis_cli.build_parser()
    help_text = parser.format_help()
    capabilities = system_contract.load_contract_documents(REPO_ROOT)["capabilities"]
    for command in capabilities["cli"]["commands"]:
        assert command.split()[0] in help_text


def test_engine_versions_and_skill_contract_agree() -> None:
    skill = (REPO_ROOT / "skills/synthesis-onboarding/SKILL.md").read_text(
        encoding="utf-8"
    )
    assert synthesis_cli.ENGINE_VERSION == synthesis_cli.onboard.ENGINE_VERSION
    assert 'version: "%s"' % synthesis_cli.ENGINE_VERSION in skill


def test_setup_routes_through_one_transaction_and_persists_desired(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def engine(argv: list[str]) -> int:
        calls.append(argv)
        return 0

    state = system_contract.SystemState(home=tmp_path)
    code = synthesis_cli.main(
        ["setup", "--profile", "skills-only", "--clients", "codex", "--channel", "stable"],
        state=state,
        engine_runner=engine,
    )
    assert code == 0
    assert calls == [["init", "--profile", "skills-only", "--clients", "codex", "--channel", "stable"]]
    assert state.read_desired()["profile"] == "skills-only"
    transaction = state.read_observation()["transactions"][-1]
    assert transaction["state"] == "committed"
    assert transaction["desired"]["status"] == "verified"
    assert transaction["live-loaded"]["status"] == "restart-required"


def test_public_json_has_one_renderer(tmp_path: Path, monkeypatch, capsys) -> None:
    def noisy_engine(_argv: list[str]) -> int:
        print("legacy human output")
        print(
            json.dumps(
                    {
                        "engine": "fixture",
                        "counts": {"changed": 0, "ok": 1},
                        "effective_selection": {
                            "profile": "skills-only",
                            "clients": ["codex"],
                            "personal_workspace": None,
                            "personal_configuration": None,
                            "layers": system_contract.default_desired_state(
                                "skills-only", ["codex"], "stable"
                            )["layers"],
                        },
                        "exit": 0,
                }
            )
        )
        return 0

    monkeypatch.setattr(synthesis_cli.onboard, "main", noisy_engine)
    state = system_contract.SystemState(home=tmp_path)
    code = synthesis_cli.main(
        ["setup", "--profile", "skills-only", "--clients", "codex", "--json"],
        state=state,
    )
    assert code == 0
    output = capsys.readouterr()
    payload = json.loads(output.out)
    assert payload["state"] == "committed"
    assert payload["details"]["engine"]["changed_resources"] == 0
    assert "legacy human output" not in output.out


def test_second_reconcile_records_zero_changed_resources(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    changed = iter((1, 0))

    def convergent_engine(_argv: list[str]) -> int:
        count = next(changed)
        print(
            json.dumps(
                    {
                        "engine": "fixture",
                        "counts": {"changed": count, "ok": 1},
                        "effective_selection": {
                            "profile": "skills-only",
                            "clients": ["codex"],
                            "personal_workspace": None,
                            "personal_configuration": None,
                            "layers": system_contract.default_desired_state(
                                "skills-only", ["codex"], "stable"
                            )["layers"],
                        },
                        "exit": 0,
                }
            )
        )
        return 0

    monkeypatch.setattr(synthesis_cli.onboard, "main", convergent_engine)
    state = system_contract.SystemState(home=tmp_path)
    arguments = [
        "setup",
        "--profile",
        "skills-only",
        "--clients",
        "codex",
        "--json",
    ]
    assert synthesis_cli.main(arguments, state=state) == 0
    capsys.readouterr()
    assert synthesis_cli.main(arguments, state=state) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["generation"] == 2
    assert payload["details"]["engine"]["changed_resources"] == 0


def test_profile_transitions_commit_each_selected_policy(tmp_path: Path) -> None:
    calls = []
    state = system_contract.SystemState(home=tmp_path)

    def selected_engine(argv: list[str]) -> dict:
        calls.append(argv)
        profile = argv[2]
        kwargs = {}
        if profile == "full":
            kwargs = {
                "personal_workspace": "example-user",
                "personal_configuration": full_configuration(),
            }
        selected = system_contract.default_desired_state(
            profile, ["codex"], "stable", **kwargs
        )
        return {
            "engine": "fixture",
            "counts": {"changed": 0},
            "effective_selection": {
                key: selected[key]
                for key in (
                    "profile",
                    "clients",
                    "personal_workspace",
                    "personal_configuration",
                    "layers",
                )
            },
            "exit": 0,
        }

    for profile in ("skills-only", "full", "skills-only"):
        assert synthesis_cli.main(
            ["setup", "--profile", profile, "--clients", "codex"],
            state=state,
            engine_runner=selected_engine,
        ) == 0
        assert state.read_desired()["profile"] == profile
    assert [item[2] for item in calls] == ["skills-only", "full", "skills-only"]
    transactions = state.read_observation()["transactions"]
    assert [item["generation"] for item in transactions] == [1, 2, 3]
    assert all(item["state"] == "committed" for item in transactions)


def test_real_full_setup_commits_effective_workspace_layers_and_present_client() -> None:
    box = Sandbox()
    try:
        client = box.fake_client()
        box.seed_currency()
        answers = box.answers(
            git_identity=("Example User", "example@example.test")
        )
        environment = dict(os.environ)
        environment.update(box.env_overrides())
        environment.update(
            {
                "SYNTHESIS_HOME": str(box.home),
                "SYNTHESIS_CLAUDE_BIN": str(client),
                "SYNTHESIS_CODEX_BIN": "",
                "SYNTHESIS_ONBOARD_NO_SERVICES": "1",
            }
        )
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "synthesis_cli.py"),
                "setup",
                "--profile",
                "full",
                "--answers",
                str(answers),
                "--no-services",
                "--json",
            ],
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
        desired = json.loads(
            (box.home / ".config" / "synthesis" / "system-state.json").read_text(
                encoding="utf-8"
            )
        )
        assert desired["clients"] == ["claude"]
        assert desired["personal_workspace"] == "example-user"
        selected = {name for name, choice in desired["layers"].items() if choice == "selected"}
        assert selected == {
            "skills",
            "session-context",
            "hooks-gates",
            "agent-kernel",
            "runtime-engines",
            "coordination",
            "doctors-conformance",
            "personal-policy",
            "knowledge-bases",
            "lifecycle",
        }
        latest = json.loads(
            (box.home / ".local" / "state" / "synthesis" / "observations.json").read_text(
                encoding="utf-8"
            )
        )["transactions"][-1]
        assert latest["state"] == "committed"
        assert latest["live-loaded"]["status"] == "restart-required"
        assert latest["details"]["engine"]["effective_selection"]["clients"] == [
            "claude"
        ]
        runtime = (
            box.home / ".synthesis" / "onboarding" / "bin" / "kernel_sync.py"
        )
        runtime.unlink()
        personal_policy = (
            box.home / ".synthesis" / "personal-policy" / "profile.json"
        )
        personal_policy.unlink()
        legacy_receipt = (
            box.home / ".synthesis" / "onboarding" / "receipts.json"
        )
        legacy_receipt.unlink()
        repair = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "synthesis_cli.py"),
                "repair",
                "--json",
            ],
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        assert repair.returncode == 0, repair.stdout + repair.stderr
        assert runtime.is_file()
        assert personal_policy.is_file()
        assert legacy_receipt.is_file()
        assert desired["personal_configuration"]["inbox_cleanup"] is False
        assert json.loads(
            (box.home / ".config" / "synthesis" / "system-state.json").read_text(
                encoding="utf-8"
            )
        ) == desired
    finally:
        box.cleanup()


def test_repair_answers_take_optional_runtime_policy_only_from_desired_state() -> None:
    answers = {
        "workspace": "example-user",
        "display_name": "Example User",
        "timezone": "UTC",
        "tone": ["direct"],
        "avoid_phrases": [],
        "git_name": "",
        "git_email": "",
        "inbox_cleanup": True,
    }
    configuration = synthesis_cli.onboard.personal_configuration_from_answers(
        answers
    )
    desired = system_contract.default_desired_state(
        "full",
        ["codex"],
        "stable",
        personal_workspace="example-user",
        personal_configuration=configuration,
    )

    class ReceiptTrap:
        def component_choice(self, _name):
            raise AssertionError("legacy receipt must not choose repair policy")

    repaired = synthesis_cli.onboard.reconcile_answers(desired, ReceiptTrap())
    assert repaired["inbox_cleanup"] is True


def test_failed_setup_aborts_and_does_not_persist_desired(tmp_path: Path) -> None:
    state = system_contract.SystemState(home=tmp_path)
    code = synthesis_cli.main(
        ["setup", "--profile", "full", "--clients", "claude"],
        state=state,
        engine_runner=lambda _argv: 1,
    )
    assert code == 1
    assert state.read_desired() is None
    assert state.read_observation()["transactions"][-1]["state"] == "aborted"


def test_organization_acquisition_failure_is_an_aborted_setup_transaction(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    state = system_contract.SystemState(home=tmp_path)

    def fail(*_args, **_kwargs):
        raise system_contract.ContractError("fixture organization unavailable")

    monkeypatch.setattr(synthesis_cli.organization, "acquire_repository", fail)
    assert synthesis_cli.main(
        [
            "setup",
            "--profile",
            "full",
            "--org-repo",
            "https://example.test/org/onboarding.git",
        ],
        state=state,
        engine_runner=lambda _argv: 0,
    ) == 2
    assert "organization unavailable" in capsys.readouterr().err
    assert state.read_desired() is None
    latest = state.read_observation()["transactions"][-1]
    assert latest["command"] == "setup"
    assert latest["state"] == "aborted"


def test_update_reuses_persisted_policy(tmp_path: Path) -> None:
    calls: list[list[str]] = []
    state = system_contract.SystemState(home=tmp_path)
    desired = system_contract.default_desired_state(
        profile="skills-only",
        clients=["claude", "codex"],
        channel="edge",
        version_pin=None,
    )
    state.run_transaction("repair", desired, lambda _tx: {})
    code = synthesis_cli.main(
        ["update"],
        state=state,
        engine_runner=lambda argv: calls.append(argv) or 0,
    )
    assert code == 0
    assert calls == [[
        "update",
        "--clients",
        "claude,codex",
        "--channel",
        "edge",
        "--desired-state",
        str(state.desired_path),
    ]]


def test_update_rejects_malformed_persisted_state_without_running_engine(
    tmp_path: Path, capsys
) -> None:
    state = system_contract.SystemState(home=tmp_path)
    state.desired_path.parent.mkdir(parents=True)
    state.desired_path.write_text('{"schema_version": 1}\n', encoding="utf-8")
    calls = []
    assert synthesis_cli.main(
        ["update"], state=state, engine_runner=lambda argv: calls.append(argv) or 0
    ) == 2
    assert calls == []
    assert "missing keys" in capsys.readouterr().err


def test_update_migrates_unambiguous_legacy_plugin_only_receipt(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    state = system_contract.SystemState(home=tmp_path)
    state.legacy_receipts_path.parent.mkdir(parents=True)
    state.legacy_receipts_path.write_text(
        json.dumps(
            {
                "version": 2,
                "profile": None,
                "personal_workspace": None,
                "plugin_policy": {"channel": "stable", "version_pin": "4.90.3"},
                "layer_choices": {},
                "component_choices": {},
                "generated_files": {},
                "adopted_repos": {},
                "managed_json_entries": {},
                "managed_text_entries": {},
                "runs": [
                    {
                        "at": "2026-09-01T00:00:00Z",
                        "command": "update",
                        "manifest": None,
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        synthesis_cli.onboard,
        "resolve_client",
        lambda client: "/usr/bin/%s" % client,
    )
    monkeypatch.setattr(
        synthesis_cli.onboard,
        "plugin_present",
        lambda client, _binary: client == "codex",
    )
    calls: list[list[str]] = []
    assert synthesis_cli.main(
        ["update", "--json"],
        state=state,
        engine_runner=lambda argv: calls.append(argv) or 0,
    ) == 0
    assert calls == [[
        "update", "--clients", "codex", "--channel", "stable",
        "--version-pin", "4.90.3",
    ]]
    desired = state.read_desired()
    assert desired["profile"] == "skills-only"
    assert desired["clients"] == ["codex"]
    assert desired["release"] == {"channel": "stable", "version_pin": "4.90.3"}
    transaction = state.read_observation()["transactions"][-1]
    assert transaction["state"] == "committed"
    assert transaction["details"]["legacy_migration_input"]["sha256"]
    payload = json.loads(capsys.readouterr().out)
    assert payload["generation"] == 1


def test_legacy_update_refuses_richer_or_malformed_receipts(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    receipts = (
        {"profile": "full"},
        {"generated_files": {"/private/resource": {"sha256": "a" * 64}}},
        {"runs": [{"manifest": "/private/organization-manifest"}]},
        {"managed_json_entries": []},
        {"version": 99},
        {"unknown_state": "present"},
        {"instruction_generation": 1},
    )
    monkeypatch.setattr(
        synthesis_cli.onboard, "resolve_client", lambda _client: "/bin/client"
    )
    monkeypatch.setattr(synthesis_cli.onboard, "plugin_present", lambda *_args: True)
    for index, extra in enumerate(receipts):
        state = system_contract.SystemState(home=tmp_path / ("case-%d" % index))
        state.legacy_receipts_path.parent.mkdir(parents=True)
        receipt = {
            "version": 2,
            "profile": None,
            "personal_workspace": None,
            "plugin_policy": {"channel": "stable", "version_pin": None},
            "layer_choices": {},
            "component_choices": {},
            "generated_files": {},
            "adopted_repos": {},
            "managed_json_entries": {},
            "managed_text_entries": {},
            "runs": [],
        }
        receipt.update(extra)
        state.legacy_receipts_path.write_text(
            json.dumps(receipt) + "\n", encoding="utf-8"
        )
        calls: list[list[str]] = []
        assert synthesis_cli.main(
            ["update"], state=state, engine_runner=lambda argv: calls.append(argv) or 0
        ) == 2
        assert calls == []
        assert state.read_desired() is None
    assert "ambiguous whole-system or organization state" in capsys.readouterr().err


def test_legacy_update_refuses_unverifiable_client_inventory(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    state = system_contract.SystemState(home=tmp_path)
    state.legacy_receipts_path.parent.mkdir(parents=True)
    state.legacy_receipts_path.write_text(
        json.dumps({"version": 2, "plugin_policy": {"channel": "stable"}}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        synthesis_cli.onboard, "resolve_client", lambda _client: "/bin/client"
    )
    monkeypatch.setattr(synthesis_cli.onboard, "plugin_present", lambda *_args: None)
    assert (
        synthesis_cli.main(
            ["repair"], state=state, engine_runner=lambda _argv: 0
        )
        == 2
    )
    assert "inventory is unreadable" in capsys.readouterr().err


def test_bootstrap_update_leaves_missing_desired_state_for_legacy_migration(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        synthesis_cli,
        "_active_release",
        lambda: {"release_root": str(tmp_path)},
    )
    assert synthesis_cli._bootstrap_update(
        ["update"], system_contract.SystemState(home=tmp_path / "home")
    ) is None


def test_installed_update_transfers_once_through_the_active_bootstrap(
    tmp_path: Path, monkeypatch
) -> None:
    release_root = tmp_path / "release"
    release_root.mkdir()
    bootstrap = release_root / "onboard.sh"
    bootstrap.write_text("#!/bin/sh\n", encoding="utf-8")
    bootstrap.chmod(0o755)
    active_path = tmp_path / "active.json"
    active_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "version": "9.8.7",
                "channel": "stable",
                "ref": "stable",
                "commit": "1" * 40,
                "tree": "2" * 40,
                "content_digest": "3" * 64,
                "digest_algorithm": system_contract.DIGEST_ALGORITHM,
                "tree_policy": system_contract.TREE_POLICY,
                "source_url": "https://example.test/synthesis-skills.git",
                "resolved_at": "2026-09-02T00:00:00Z",
                "release_root": str(release_root.resolve()),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SYNTHESIS_ACTIVE_DESCRIPTOR", str(active_path))
    monkeypatch.setenv("SYNTHESIS_ONBOARD_SOURCE_DIR", "/untrusted/source")
    state = system_contract.SystemState(home=tmp_path / "home")
    desired = system_contract.default_desired_state(
        "skills-only", ["codex"], "edge"
    )
    state.run_transaction("setup", desired, lambda _tx: {})
    calls = []
    monkeypatch.setattr(
        synthesis_cli.subprocess,
        "call",
        lambda command, env=None: calls.append((command, env)) or 0,
    )
    assert synthesis_cli._bootstrap_update(["update"], state) == 0
    assert calls[0][0] == [str(bootstrap), "update"]
    assert calls[0][1]["SYNTHESIS_ONBOARD_CHANNEL"] == "edge"
    assert "SYNTHESIS_ONBOARD_VERSION_PIN" not in calls[0][1]
    assert "SYNTHESIS_ONBOARD_SOURCE_DIR" not in calls[0][1]
    monkeypatch.setenv("SYNTHESIS_BOOTSTRAP_RESOLVED", "1")
    assert synthesis_cli._bootstrap_update(["update"], state) is None
    assert len(calls) == 1


def test_org_policy_change_rebootstraps_then_commits_the_new_policy(
    tmp_path: Path, monkeypatch
) -> None:
    release_root = tmp_path / "release"
    release_root.mkdir()
    bootstrap = release_root / "onboard.sh"
    bootstrap.write_text("#!/bin/sh\n", encoding="utf-8")
    bootstrap.chmod(0o755)
    active_path = tmp_path / "active.json"

    def write_active(version: str, channel: str, ref: str) -> None:
        active_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "version": version,
                    "channel": channel,
                    "ref": ref,
                    "commit": "1" * 40,
                    "tree": "2" * 40,
                    "content_digest": "3" * 64,
                    "digest_algorithm": system_contract.DIGEST_ALGORITHM,
                    "tree_policy": system_contract.TREE_POLICY,
                    "source_url": "https://example.test/synthesis-skills.git",
                    "resolved_at": "2026-09-02T00:00:00Z",
                    "release_root": str(release_root.resolve()),
                }
            )
            + "\n",
            encoding="utf-8",
        )

    write_active("9.8.7", "stable", "stable")
    monkeypatch.setenv("SYNTHESIS_ACTIVE_DESCRIPTOR", str(active_path))
    state = system_contract.SystemState(home=tmp_path / "home")
    desired = system_contract.default_desired_state(
        "full",
        ["claude", "codex"],
        "stable",
        personal_workspace="example-user",
        personal_configuration=full_configuration(),
        organizations=[
            {
                "repository": "https://example.test/org/onboarding.git",
                "manifest_path": ".agents/onboarding.yaml",
                "commit_policy": "floating",
                "commit": "4" * 40,
            }
        ],
    )
    state.run_transaction("setup", desired, lambda _tx: {})
    org_root = tmp_path / "org"
    (org_root / ".agents").mkdir(parents=True)
    (org_root / ".agents" / "onboarding.yaml").write_text("version: 2\n", encoding="utf-8")
    manifest = {
        "ecosystem": {
            "clients": ["codex"],
            "channel": "edge",
            "version_pin": None,
        }
    }
    monkeypatch.setattr(
        synthesis_cli.organization,
        "acquire_repository",
        lambda *_args, **_kwargs: (org_root, "5" * 40),
    )
    monkeypatch.setattr(synthesis_cli.onboard, "load_manifest", lambda _path: manifest)
    transfers = []
    monkeypatch.setattr(
        synthesis_cli,
        "_run_release_bootstrap",
        lambda argv, active, channel, version_pin: transfers.append(
            (argv, channel, version_pin)
        )
        or 0,
    )
    engine_calls = []
    assert synthesis_cli.main(
        ["update"], state=state, engine_runner=lambda argv: engine_calls.append(argv) or 0
    ) == 0
    assert transfers == [(["update"], "stable", None)]
    assert engine_calls == []
    assert state.read_desired()["release"] == {"channel": "stable", "version_pin": None}

    monkeypatch.setenv("SYNTHESIS_BOOTSTRAP_RESOLVED", "1")
    assert synthesis_cli.main(
        ["update"], state=state, engine_runner=lambda argv: engine_calls.append(argv) or 0
    ) == 0
    assert transfers == [(["update"], "stable", None), (["update"], "edge", None)]
    assert state.read_observation()["transactions"][-1]["state"] == "aborted"
    assert state.read_desired()["release"] == {"channel": "stable", "version_pin": None}

    write_active("9.8.6", "edge", "main")
    assert synthesis_cli.main(
        ["update"], state=state, engine_runner=lambda argv: engine_calls.append(argv) or 0
    ) == 0
    assert "--policy-transition" in engine_calls[-1]
    assert state.read_desired()["release"] == {"channel": "edge", "version_pin": None}
    assert state.read_desired()["clients"] == ["codex"]
    assert state.read_observation()["transactions"][-1]["state"] == "committed"


def test_repair_reconciles_recorded_org_policy_without_advancing_it(
    tmp_path: Path, monkeypatch
) -> None:
    state = system_contract.SystemState(home=tmp_path / "home")
    recorded_commit = "4" * 40
    desired = system_contract.default_desired_state(
        "full",
        ["claude", "codex"],
        "stable",
        personal_workspace="example-user",
        personal_configuration=full_configuration(),
        organizations=[
            {
                "repository": "https://example.test/org/onboarding.git",
                "manifest_path": ".agents/onboarding.yaml",
                "commit_policy": "floating",
                "commit": recorded_commit,
            }
        ],
    )
    state.run_transaction("setup", desired, lambda _tx: {})
    org_root = tmp_path / "org"
    (org_root / ".agents").mkdir(parents=True)
    (org_root / ".agents" / "onboarding.yaml").write_text(
        "version: 2\n", encoding="utf-8"
    )
    acquisition_calls = []

    def acquire(*_args, **kwargs):
        acquisition_calls.append(kwargs)
        return org_root, recorded_commit

    monkeypatch.setattr(synthesis_cli.organization, "acquire_repository", acquire)
    monkeypatch.setattr(
        synthesis_cli.onboard,
        "load_manifest",
        lambda _path: {
            "ecosystem": {
                "clients": ["codex"],
                "channel": "edge",
                "version_pin": None,
            }
        },
    )
    monkeypatch.setattr(
        synthesis_cli,
        "_active_release",
        lambda: {
            "schema_version": 1,
            "version": "9.8.7",
            "channel": "stable",
            "ref": "stable",
            "commit": "1" * 40,
            "tree": "2" * 40,
            "content_digest": "3" * 64,
            "digest_algorithm": system_contract.DIGEST_ALGORITHM,
            "tree_policy": system_contract.TREE_POLICY,
            "source_url": "https://example.test/synthesis-skills.git",
            "resolved_at": "2026-09-02T00:00:00Z",
            "release_root": str(org_root.resolve()),
        },
    )
    monkeypatch.setattr(
        synthesis_cli,
        "_run_release_bootstrap",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("repair must not transfer releases")
        ),
    )
    engine_calls = []
    assert synthesis_cli.main(
        ["repair"],
        state=state,
        engine_runner=lambda argv: engine_calls.append(argv) or 0,
    ) == 0
    assert acquisition_calls == [
        {"expected_commit": recorded_commit, "refresh": False}
    ]
    assert engine_calls == [
        [
            "repair",
            "--clients",
            "claude,codex",
            "--channel",
            "stable",
            "--desired-state",
            str(state.desired_path),
            "--manifest",
            str(org_root / ".agents" / "onboarding.yaml"),
        ]
    ]
    assert state.read_desired() == desired


def test_setup_rebootstraps_edge_and_pin_back_to_floating_stable(
    tmp_path: Path, monkeypatch
) -> None:
    release_root = tmp_path / "release"
    release_root.mkdir()
    bootstrap = release_root / "onboard.sh"
    bootstrap.write_text("#!/bin/sh\n", encoding="utf-8")
    bootstrap.chmod(0o755)
    active_path = tmp_path / "active.json"
    monkeypatch.setenv("SYNTHESIS_ACTIVE_DESCRIPTOR", str(active_path))
    transfers = []
    monkeypatch.setattr(
        synthesis_cli,
        "_run_release_bootstrap",
        lambda argv, active, channel, version_pin: transfers.append(
            (active["channel"], active["ref"], channel, version_pin)
        )
        or 0,
    )

    for index, (active_channel, active_ref) in enumerate(
        (("edge", "main"), ("pin", "v9.8.7"))
    ):
        active_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "version": "9.8.7",
                    "channel": active_channel,
                    "ref": active_ref,
                    "commit": "1" * 40,
                    "tree": "2" * 40,
                    "content_digest": "3" * 64,
                    "digest_algorithm": system_contract.DIGEST_ALGORITHM,
                    "tree_policy": system_contract.TREE_POLICY,
                    "source_url": "https://example.test/synthesis-skills.git",
                    "resolved_at": "2026-09-02T00:00:00Z",
                    "release_root": str(release_root.resolve()),
                }
            )
            + "\n",
            encoding="utf-8",
        )
        engine_calls = []
        state = system_contract.SystemState(home=tmp_path / ("home-%d" % index))
        assert synthesis_cli.main(
            ["setup", "--profile", "skills-only", "--clients", "codex", "--channel", "stable"],
            state=state,
            engine_runner=lambda argv: engine_calls.append(argv) or 0,
        ) == 0
        assert engine_calls == []
        assert state.read_desired() is None
        # A policy transfer is a control handoff to the bootstrap, not a
        # failed attempt: no transaction is recorded for it.
        assert state.read_observation()["transactions"] == []

    assert transfers == [
        ("edge", "main", "stable", None),
        ("pin", "v9.8.7", "stable", None),
    ]


def test_setup_policy_transfer_does_not_run_prior_engine_rollback(
    tmp_path: Path, monkeypatch
) -> None:
    release_root = tmp_path / "release"
    release_root.mkdir()
    bootstrap = release_root / "onboard.sh"
    bootstrap.write_text("#!/bin/sh\n", encoding="utf-8")
    bootstrap.chmod(0o755)
    active_path = tmp_path / "active.json"
    active_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "version": "9.8.7",
                "channel": "edge",
                "ref": "main",
                "commit": "1" * 40,
                "tree": "2" * 40,
                "content_digest": "3" * 64,
                "digest_algorithm": system_contract.DIGEST_ALGORITHM,
                "tree_policy": system_contract.TREE_POLICY,
                "source_url": "https://example.test/synthesis-skills.git",
                "resolved_at": "2026-09-02T00:00:00Z",
                "release_root": str(release_root.resolve()),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SYNTHESIS_ACTIVE_DESCRIPTOR", str(active_path))
    state = system_contract.SystemState(home=tmp_path / "home")
    prior = system_contract.default_desired_state(
        "skills-only", ["codex"], "edge"
    )
    state.run_transaction("setup", prior, lambda _tx: {})
    engine_calls = []
    transfers = []
    monkeypatch.setattr(
        synthesis_cli,
        "_run_release_bootstrap",
        lambda argv, active, channel, version_pin: transfers.append(
            (argv, active["channel"], channel, version_pin)
        )
        or 0,
    )
    assert synthesis_cli.main(
        ["setup", "--profile", "skills-only", "--clients", "codex", "--channel", "stable"],
        state=state,
        engine_runner=lambda argv: engine_calls.append(argv) or 0,
    ) == 0
    assert engine_calls == []
    assert transfers == [
        (
            ["setup", "--profile", "skills-only", "--clients", "codex", "--channel", "stable"],
            "edge",
            "stable",
            None,
        )
    ]
    assert state.read_desired() == prior


def test_setup_rebootstrap_requires_exact_pin_identity_even_at_same_version(
    tmp_path: Path, monkeypatch
) -> None:
    release_root = tmp_path / "release"
    release_root.mkdir()
    (release_root / "onboard.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    active_path = tmp_path / "active.json"
    monkeypatch.setenv("SYNTHESIS_ACTIVE_DESCRIPTOR", str(active_path))
    transfers = []
    monkeypatch.setattr(
        synthesis_cli,
        "_run_release_bootstrap",
        lambda argv, active, channel, version_pin: transfers.append(
            (active["channel"], active["ref"], channel, version_pin)
        )
        or 0,
    )
    for index, (active_channel, active_ref) in enumerate(
        (("stable", "stable"), ("edge", "main"))
    ):
        active_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "version": "9.8.7",
                    "channel": active_channel,
                    "ref": active_ref,
                    "commit": "1" * 40,
                    "tree": "2" * 40,
                    "content_digest": "3" * 64,
                    "digest_algorithm": system_contract.DIGEST_ALGORITHM,
                    "tree_policy": system_contract.TREE_POLICY,
                    "source_url": "https://example.test/synthesis-skills.git",
                    "resolved_at": "2026-09-02T00:00:00Z",
                    "release_root": str(release_root.resolve()),
                }
            )
            + "\n",
            encoding="utf-8",
        )
        state = system_contract.SystemState(home=tmp_path / ("pin-home-%d" % index))
        assert synthesis_cli.main(
            [
                "setup", "--profile", "skills-only", "--clients", "codex",
                "--channel", "stable", "--pin", "9.8.7",
            ],
            state=state,
            engine_runner=lambda _argv: 0,
        ) == 0
        assert state.read_desired() is None
    assert transfers == [
        ("stable", "stable", "stable", "9.8.7"),
        ("edge", "main", "stable", "9.8.7"),
    ]


def test_uninstall_persists_disabled_state_and_removed_planes(tmp_path: Path) -> None:
    calls: list[list[str]] = []
    state = system_contract.SystemState(home=tmp_path)
    desired = system_contract.default_desired_state("skills-only", ["codex"], "stable")
    state.run_transaction("setup", desired, lambda _tx: {})
    assert synthesis_cli.main(
        ["uninstall", "--json"],
        state=state,
        engine_runner=lambda argv: calls.append(argv) or verified_uninstall_engine(argv),
    ) == 0
    assert calls == [["uninstall", "--clients", "codex"]]
    assert state.read_desired()["enabled"] is False
    latest = state.read_observation()["transactions"][-1]
    assert latest["installed"]["status"] == "removed"
    assert latest["live-loaded"]["status"] == "not-applicable"


def test_uninstall_refuses_to_disable_state_when_removal_is_not_verified(
    tmp_path: Path, capsys
) -> None:
    state = system_contract.SystemState(home=tmp_path)
    desired = system_contract.default_desired_state("skills-only", ["codex"], "stable")
    state.run_transaction("setup", desired, lambda _tx: {})
    unverified = {"engine": "fixture", "counts": {"ok": 1}, "steps": [], "exit": 0}
    assert synthesis_cli.main(
        ["uninstall", "--json"], state=state, engine_runner=lambda _argv: unverified
    ) == 2
    assert state.read_desired()["enabled"] is True
    assert state.read_observation()["transactions"][-1]["state"] == "aborted"
    assert "absence verification" in capsys.readouterr().out


def test_doctor_accepts_disabled_state_only_after_fresh_absence_probe(tmp_path: Path, capsys) -> None:
    calls: list[list[str]] = []
    state = system_contract.SystemState(home=tmp_path)
    desired = system_contract.default_desired_state("skills-only", ["codex"], "stable", enabled=False)
    state.run_transaction(
        "uninstall",
        desired,
        lambda _tx: synthesis_cli._planes(desired, "uninstall", removal_verified=True),
    )
    assert synthesis_cli.main(
        ["doctor", "--json"],
        state=state,
        engine_runner=lambda argv: calls.append(argv) or verified_uninstall_engine(argv),
    ) == 0
    assert calls == [["uninstall-doctor", "--clients", "codex"]]
    payload = json.loads(capsys.readouterr().out)
    assert payload["planes"]["installed"]["status"] == "removed"


def test_doctor_rejects_desired_state_edited_outside_a_transaction(
    tmp_path: Path, capsys
) -> None:
    state = system_contract.SystemState(home=tmp_path)
    desired = system_contract.default_desired_state(
        "skills-only", ["codex"], "stable", enabled=False
    )
    state.run_transaction(
        "uninstall",
        desired,
        lambda _tx: synthesis_cli._planes(desired, "uninstall", removal_verified=True),
    )
    edited = dict(desired)
    edited["release"] = {"channel": "edge", "version_pin": None}
    state.desired_path.write_text(json.dumps(edited) + "\n", encoding="utf-8")
    assert synthesis_cli.main(["doctor", "--json"], state=state) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["planes"]["desired"]["status"] == "unverified"


def test_update_refuses_disabled_state(tmp_path: Path, capsys) -> None:
    state = system_contract.SystemState(home=tmp_path)
    desired = system_contract.default_desired_state("skills-only", ["codex"], "stable", enabled=False)
    state.run_transaction("uninstall", desired, lambda _tx: {})
    assert synthesis_cli.main(["update"], state=state, engine_runner=lambda _argv: 0) == 2
    assert "disabled" in capsys.readouterr().err


def test_workspace_ensure_uses_stable_public_capability(tmp_path: Path) -> None:
    calls: list[list[str]] = []
    state = system_contract.SystemState(home=tmp_path)
    code = synthesis_cli.main(
        ["workspace", "ensure", "--name", "example"],
        state=state,
        engine_runner=lambda argv: calls.append(argv) or 0,
    )
    assert code == 0
    assert calls == [["init-workspace", "--workspace", "example"]]
    assert state.read_observation()["transactions"][-1]["command"] == "workspace-ensure"


def test_status_keeps_desired_and_observed_planes_separate(tmp_path: Path, capsys) -> None:
    state = system_contract.SystemState(home=tmp_path)
    code = synthesis_cli.main(["status", "--json"], state=state)
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["desired"] is None
    assert payload["observed"]["generation"] == 0


def test_outcome_verify_records_only_trusted_public_task(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / ".agents").mkdir(parents=True)
    (workspace / "source").mkdir()
    (workspace / ".agents" / "knowledge-base.yaml").write_text(
        "bundle_path: source\n", encoding="utf-8"
    )
    (workspace / "source" / "fact.md").write_text("fact\n", encoding="utf-8")
    commit_fixture_repo(workspace)
    state = system_contract.SystemState(home=tmp_path)
    desired = system_contract.default_desired_state("skills-only", ["codex"], "stable")
    state.run_transaction(
        "repair",
        desired,
        lambda _tx: {
            "live-loaded": {
                "status": "verified",
                "receipts": {"codex": {"session_id": "fixture"}},
            }
        },
    )
    assert synthesis_cli.main(
        [
            "outcome",
            "verify",
            "--task",
            "workspace-grounding-check",
            "--workspace",
            str(workspace),
            "--source-class",
            "personal-knowledge",
        ],
        state=state,
    ) == 0
    latest = state.read_observation()["transactions"][-1]
    assert latest["outcome-verified"]["task_id"] == "workspace-grounding-check"
    assert latest["outcome-verified"]["transaction_id"] == latest["transaction_id"]
    assert len(latest["outcome-verified"]["live_loaded_sha256"]) == 64


def test_outcome_verify_refuses_generation_without_live_evidence(
    tmp_path: Path, capsys
) -> None:
    workspace = tmp_path / "workspace"
    (workspace / ".agents").mkdir(parents=True)
    (workspace / "source").mkdir()
    (workspace / ".agents" / "knowledge-base.yaml").write_text(
        "bundle_path: source\n", encoding="utf-8"
    )
    (workspace / "source" / "fact.md").write_text("fact\n", encoding="utf-8")
    commit_fixture_repo(workspace)
    state = system_contract.SystemState(home=tmp_path)
    desired = system_contract.default_desired_state("skills-only", ["codex"], "stable")
    state.run_transaction("repair", desired, lambda _tx: {})
    assert synthesis_cli.main(
        [
            "outcome",
            "verify",
            "--task",
            "workspace-grounding-check",
            "--workspace",
            str(workspace),
            "--source-class",
            "personal-knowledge",
        ],
        state=state,
    ) == 2
    assert "live-loaded" in capsys.readouterr().err

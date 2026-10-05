"""Organization transport, local client selection, and visible operator boundaries."""

import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

import bootstrap
import onboard
import organization
import synthesis_cli
import system_contract

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "synthesis-agent-conformance" / "scripts"))
import client_binaries  # noqa: E402


def test_stored_origin_survives_ssh_transport_rewrite(tmp_path, monkeypatch):
    url = "git@example.test:team/config.git"
    root = tmp_path / "organizations" / organization.repository_key(url)
    root.mkdir(parents=True)
    config = tmp_path / "global-config"
    config.write_text('[url "ssh://git@ssh.example.test:443/"]\n\tinsteadOf = git@example.test:\n')
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    env = dict(os.environ, GIT_AUTHOR_NAME="Fixture", GIT_COMMITTER_NAME="Fixture",
               GIT_AUTHOR_EMAIL="fixture@example.test", GIT_COMMITTER_EMAIL="fixture@example.test")
    def git(*args):
        return subprocess.run(["git", "-C", str(root), *args], env=env, check=True,
                              text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.strip()
    git("init", "-q", "-b", "main")
    (root / ".agents").mkdir()
    (root / organization.MANIFEST_RELATIVE).write_text("version: 2\n")
    git("add", ".agents/onboarding.yaml")
    git("-c", "core.hooksPath=/dev/null", "commit", "-qm", "Fixture")
    git("remote", "add", "origin", url)
    head = git("rev-parse", "HEAD")
    git("update-ref", "refs/remotes/origin/main", head)
    assert git("remote", "get-url", "origin") != url
    assert organization.acquire_repository(url, tmp_path, refresh=False) == (root, head)
    git("config", "remote.origin.url", "git@example.test:wrong/config.git")
    with pytest.raises(system_contract.ContractError, match="wrong remote"):
        organization.acquire_repository(url, tmp_path, refresh=False)


@pytest.mark.parametrize("clients", [["claude"], ["codex"], ["claude", "codex"]])
def test_organization_supports_local_client_subset_without_changing_selection(clients):
    desired = system_contract.default_desired_state("skills-only", clients, "stable")
    before = copy.deepcopy(desired)
    manifest = {"org": {"workspace": "team"}, "ecosystem": {"clients": ["claude", "codex"]}}
    system_contract.validate_additive_organization(desired, manifest, {"workspace": "team"})
    assert desired == before


@pytest.mark.parametrize("clients", [[], ["claude"], ["codex", "codex"], ["codex", "alien"], "codex", None, [1], {"codex": True}, [["codex"]]])
def test_invalid_or_unsupported_organization_clients_refuse(clients):
    desired = system_contract.default_desired_state("skills-only", ["codex"], "stable")
    manifest = {"org": {"workspace": "team"}, "ecosystem": {"clients": clients}}
    with pytest.raises(system_contract.ContractError):
        system_contract.validate_additive_organization(desired, manifest, {"workspace": "team"})


def test_enrollment_keeps_skills_only_single_client(tmp_path, monkeypatch):
    from test_additive_enrollment import base_state, org_fixture, REPOSITORY
    state, before = base_state(tmp_path)
    manifest = org_fixture(tmp_path, monkeypatch)
    manifest["ecosystem"]["clients"] = ["claude", "codex"]
    assert synthesis_cli.main(["enroll", "--org-repo", REPOSITORY], state=state,
                              engine_runner=lambda _argv: 0) == 0
    actual = state.read_desired()
    assert actual["clients"] == before["clients"] == ["codex"]
    assert actual["profile"] == "skills-only"
    assert actual.get("personal_configuration") == before.get("personal_configuration")
    for key in before:
        if key not in {"organizations", "layers"}:
            assert actual[key] == before[key]


def test_guided_prompt_is_visible_before_input_and_not_in_structured_stdout(monkeypatch):
    visible = io.StringIO()
    monkeypatch.setattr(sys, "stderr", visible)
    class Input:
        def readline(self):
            assert "Choose profile" in visible.getvalue()
            return "skills-only\n"
    monkeypatch.setattr(onboard, "_prompt_stream", lambda: (Input(), False))
    def engine(_argv):
        assert onboard._ask("Choose profile") == "skills-only"
        print(json.dumps({"exit": 0, "ok": True}))
        return 0
    monkeypatch.setattr(onboard, "main", engine)
    assert synthesis_cli._quiet_engine_runner(["init"]) == {"exit": 0, "ok": True}
    assert "Choose profile" in visible.getvalue()


def test_desktop_bundled_claude_discovery_is_bounded_and_probed(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("SYNTHESIS_CLAUDE_BIN", raising=False)
    monkeypatch.setattr(client_binaries.shutil, "which", lambda _name: None)
    base = tmp_path / "Library/Application Support/Claude/claude-code"
    paths = []
    for version in ("2.1.9", "2.1.10"):
        binary = base / version / "aabbccddeeff/claude.app/Contents/MacOS/claude"
        binary.parent.mkdir(parents=True)
        binary.write_text("#!/bin/sh\nexit 0\n")
        binary.chmod(0o755)
        paths.append(binary)
    probes = []
    monkeypatch.setattr(client_binaries, "_codex_launcher_works", lambda path: probes.append(path) or True)
    locations = [item for item in client_binaries.WELL_KNOWN_LOCATIONS["claude"] if "Library/Application Support" in item]
    assert client_binaries.resolve_client_binary("claude", locations=locations) == str(paths[1])
    assert probes == [paths[1]]
    monkeypatch.setenv("SYNTHESIS_CLAUDE_BIN", "")
    assert client_binaries.resolve_client_binary("claude", locations=locations) is None


def test_launcher_path_guidance_is_actionable_and_conditional(tmp_path, monkeypatch, capsys):
    launcher = tmp_path / "space directory/bin/synthesis"
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    bootstrap._path_guidance(launcher)
    rendered = capsys.readouterr().err
    assert str(launcher.parent) in rendered
    assert "export PATH=" in rendered
    assert '"$PATH"' in rendered
    monkeypatch.setenv("PATH", str(launcher.parent) + ":/usr/bin")
    bootstrap._path_guidance(launcher)
    assert capsys.readouterr().err == ""


def test_git_fetch_error_keeps_first_cause_and_access_remedy(monkeypatch):
    monkeypatch.setattr(organization.subprocess, "run", lambda *_a, **_k: subprocess.CompletedProcess(
        [], 128, "", "Permission denied (publickey).\nfatal: Could not read from remote repository.\nPlease make sure you have the correct access rights.\n"))
    with pytest.raises(system_contract.ContractError) as error:
        organization._git("fetch", "--prune", "origin")
    assert "Permission denied (publickey)" in str(error.value)
    assert "Could not read from remote repository" in str(error.value)
    assert "correct access rights" in str(error.value)
    assert "repository access" in str(error.value)


@pytest.mark.parametrize("failure", [OSError("unavailable"), subprocess.TimeoutExpired(["git"], 600)])
def test_git_start_or_timeout_is_actionable_contract_error(monkeypatch, failure):
    def refused(*_a, **_k):
        raise failure
    monkeypatch.setattr(organization.subprocess, "run", refused)
    with pytest.raises(system_contract.ContractError, match="organization repository"):
        organization._git("fetch", "--prune", "origin")


def test_git_diagnostics_redact_credentials_and_bound_large_output(monkeypatch):
    diagnostic = "first cause https://user:secret@example.test/repo\n" + "x" * 70000 + "\nlast remedy"
    monkeypatch.setattr(organization.subprocess, "run", lambda *_a, **_k: subprocess.CompletedProcess([], 1, "", diagnostic))
    with pytest.raises(system_contract.ContractError) as error:
        organization._git("clone", "https://example.test/repo")
    result = str(error.value)
    assert "first cause" in result and "last remedy" in result
    assert "secret" not in result and "user:" not in result
    assert "[redacted]@example.test" in result
    assert "diagnostic truncated" in result
    assert len(result) < 66000


def test_desktop_fallback_rejects_stale_bundle_and_stops_on_unknown_cleanup(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("SYNTHESIS_CLAUDE_BIN", raising=False)
    monkeypatch.setattr(client_binaries.shutil, "which", lambda _name: None)
    root = tmp_path / "Library/Application Support/Claude/claude-code"
    binaries = []
    for version in ("2.1.9", "2.1.10"):
        binary = root / version / "aabbccddeeff/claude.app/Contents/MacOS/claude"
        binary.parent.mkdir(parents=True)
        binary.write_text("#!/bin/sh\nexit 0\n")
        binary.chmod(0o755)
        binaries.append(binary)
    seen = []
    monkeypatch.setattr(client_binaries, "_codex_launcher_works", lambda path: seen.append(path) or path == binaries[0])
    assert client_binaries.resolve_client_binary("claude", locations=[client_binaries.CLAUDE_DESKTOP_ROOT]) == str(binaries[0])
    assert seen == list(reversed(binaries))
    monkeypatch.setattr(client_binaries, "_codex_launcher_works", lambda _path: None)
    assert client_binaries.resolve_client_binary("claude", locations=[client_binaries.CLAUDE_DESKTOP_ROOT]) is None


def test_desktop_bundle_probe_uses_local_executable_only(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("SYNTHESIS_CLAUDE_BIN", raising=False)
    monkeypatch.setattr(client_binaries.shutil, "which", lambda _name: None)
    binary = tmp_path / "Library/Application Support/Claude/claude-code/2.1.10/aabbccddeeff/claude.app/Contents/MacOS/claude"
    binary.parent.mkdir(parents=True)
    binary.write_text('#!/bin/sh\n[ "$#" -eq 1 ] && [ "$1" = "--version" ]\n')
    binary.chmod(0o755)
    assert client_binaries.resolve_client_binary("claude", locations=[client_binaries.CLAUDE_DESKTOP_ROOT]) == str(binary)


def test_desktop_directory_escape_and_extra_locations_are_not_searched(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("SYNTHESIS_CLAUDE_BIN", raising=False)
    monkeypatch.setattr(client_binaries.shutil, "which", lambda _name: None)
    root = tmp_path / "Library/Application Support/Claude/claude-code"
    root.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "2.1.10").symlink_to(outside, target_is_directory=True)
    assert client_binaries._claude_desktop_candidates() == []
    assert client_binaries.resolve_client_binary("claude", locations=[]) is None


def test_direct_guided_prompt_preserves_eof_and_noninteractive_refusal(monkeypatch):
    monkeypatch.setattr(onboard, "_prompt_stream", lambda: (None, False))
    with pytest.raises(ValueError, match="needs a terminal"):
        onboard._ask("Profile")
    monkeypatch.setattr(onboard, "_prompt_stream", lambda: (io.StringIO(""), True))
    with pytest.raises(ValueError, match="input ended"):
        onboard._ask("Profile")


def test_onboarding_expanded_path_locations_find_desktop_bundle(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("SYNTHESIS_CLAUDE_BIN", raising=False)
    monkeypatch.setattr(client_binaries.shutil, "which", lambda _name: None)
    root = Path(client_binaries.CLAUDE_DESKTOP_ROOT).expanduser()
    binary = root / "2.1.10/aabbccddeeff/claude.app/Contents/MacOS/claude"
    binary.parent.mkdir(parents=True)
    binary.write_text("#!/bin/sh\nexit 0\n")
    binary.chmod(0o755)
    monkeypatch.setattr(onboard, "CLIENT_WELL_KNOWN", {"claude": [root]})
    seen = []
    monkeypatch.setattr(client_binaries, "_codex_launcher_works", lambda candidate: seen.append(candidate) or True)
    assert onboard.resolve_client("claude") == str(binary)
    assert seen == [binary]


# The bootstrap owns its guidance; the engine owns the structured stderr document.
# Exercise both through the real isolated acquisition and engine failure boundary.
from test_native_failure_boundary import reviewed_source, run_isolated  # noqa: E402,F401


def test_bootstrap_json_failure_is_one_actual_engine_document(reviewed_source, tmp_path):
    result, _box = run_isolated(
        reviewed_source, tmp_path, "skills-only", "claude", explicit_copy=True
    )
    assert result["returncode"] == 1
    assert not result["timed_out"]
    assert "export PATH=" not in result["stderr"]
    engine_report = json.loads(result["stderr"])
    assert any(
        step.get("layer") == "session-context" and step.get("layer_state") == "missing"
        for step in engine_report["steps"]
    ), engine_report

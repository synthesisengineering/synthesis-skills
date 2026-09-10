"""Applicability never turns lost structured state into a clean checkpoint."""
import json
from pathlib import Path

import pytest

import project_state as state
from test_project_state import board, init_repo, native_hook_fixture, run

SESSION = "018f0000-0000-7000-8000-000000000001"


@pytest.fixture
def machine(tmp_path):
    repo, project = init_repo(tmp_path)
    claims = board(tmp_path / "board.md", [(SESSION, "s-abcd-efgh-jkmn", "alpha", str(repo))])
    return repo, project, claims, tmp_path / "receipts"


def adopted(machine):
    repo, project, _, _ = machine
    state.build_operational_state(project, project_id="alpha", phase="release 1.0.0",
        status="active", controlling_plan="resources/artifacts/plan.md", accepted_baseline="1.0.0",
        next_actions=["finish"], last_session="2026-09-03", session_id=SESSION)
    run("git", "add", "projects", cwd=repo)
    run("git", "commit", "-m", "Fixture", cwd=repo)


def cli(machine, command, capsys, project=None):
    _, selected, claims, receipts = machine
    result = state.main([command, "--project", str(project or selected), "--session-id", SESSION,
        "--coordination-board", str(claims), "--receipt-root", str(receipts)])
    return result, json.loads(capsys.readouterr().out)


@pytest.mark.parametrize("command", ["checkpoint", "validate"])
@pytest.mark.parametrize("dirty", [False, True])
def test_ordinary_registered_project_cli_is_explicitly_not_applicable(machine, capsys, command, dirty):
    repo, project, _, receipts = machine
    if dirty:
        (project / "new-notes.md").write_text("Retained ordinary work\n")
    before = run("git", "status", "--porcelain=v1", cwd=repo)
    result, report = cli(machine, command, capsys)
    assert result == 0
    assert report["status"] == "NOT_APPLICABLE"
    assert report["checkpoint_accepted"] is False
    assert report["no_receipt_issued"] is True
    assert "receipt" not in report
    assert not receipts.exists() and not (project / state.STATE_FILE).exists()
    assert run("git", "status", "--porcelain=v1", cwd=repo) == before


def test_direct_checkpoint_api_remains_receipt_only(machine):
    _, project, claims, receipts = machine
    with pytest.raises(state.ProjectStateError):
        state.checkpoint_project(project, session_id=SESSION, coordination_board=claims, receipt_root=receipts)
    assert state.validate_checkpoint(project, session_id=SESSION, coordination_board=claims,
        receipt_root=receipts)[0] == "NOT_APPLICABLE"
    assert not receipts.exists()


@pytest.mark.parametrize("command", ["checkpoint", "validate"])
@pytest.mark.parametrize("change", ["unstaged", "staged", "committed", "marker-only", "malformed", "symlink", "duplicate", "unsupported"])
def test_adopted_or_unsafe_state_never_becomes_not_applicable(machine, capsys, command, change, tmp_path):
    repo, project, _, receipts = machine
    adopted(machine)
    path = project / state.STATE_FILE
    if change in {"unstaged", "staged", "committed", "marker-only"}:
        if change == "marker-only":
            run("git", "reset", "--soft", "HEAD^", cwd=repo)
            run("git", "reset", "HEAD", "--", f"projects/alpha/{state.STATE_FILE}", cwd=repo)
        path.unlink()
        if change in {"staged", "committed"}:
            run("git", "add", "-u", cwd=repo)
        if change == "committed":
            run("git", "commit", "-m", "Fixture", cwd=repo)
    elif change == "symlink":
        target = tmp_path / "state-target.json"
        target.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(target)
    elif change == "duplicate":
        path.write_text(path.read_text().replace('{', '{"project_id":"alpha",', 1))
    elif change == "unsupported":
        value = json.loads(path.read_text())
        value["schema_version"] = 999
        path.write_text(json.dumps(value))
    else:
        path.write_text("{")
    result, report = cli(machine, command, capsys)
    assert result != 0 and report["status"] not in {"PASS", "NOT_APPLICABLE"}
    assert not receipts.exists()


@pytest.mark.parametrize("client", ["cc", "codex"])
@pytest.mark.parametrize("change", ["ordinary", "unstaged", "staged", "committed"])
def test_owned_hook_and_observer_discovery_keep_adoption_obligations(machine, monkeypatch, tmp_path, client, change):
    repo, project, claims, receipts = machine
    if change != "ordinary":
        adopted(machine)
        (project / state.STATE_FILE).unlink()
        if change in {"staged", "committed"}:
            run("git", "add", "-u", cwd=repo)
        if change == "committed":
            run("git", "commit", "-m", "Fixture", cwd=repo)
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", f"{client}:{SESSION}")
    claims.write_text(claims.read_text().replace(f"tool:{SESSION}", f"{client}:{SESSION}"))
    payload = native_hook_fixture(tmp_path, monkeypatch, client, SESSION, project)
    verdict, _ = state.checkpoint_hook(payload, coordination_board=claims, receipt_root=receipts,
        refresh_coordination=False, repo_guard_root=tmp_path / "repo-guard")
    if change == "ordinary":
        assert verdict == "NOT_APPLICABLE"
    else:
        assert verdict not in {"PASS", "NOT_APPLICABLE"}
        assert state._observer_project(project) == project
        claims.write_text(claims.read_text().replace("| active |", "| released |"))
        observed, _ = state.checkpoint_hook(payload, coordination_board=claims, receipt_root=receipts,
            refresh_coordination=False, repo_guard_root=tmp_path / "repo-guard")
        assert observed not in {"PASS", "NOT_APPLICABLE"}
    assert not receipts.exists()


@pytest.mark.parametrize("command", ["checkpoint", "validate"])
@pytest.mark.parametrize("kind", ["missing", "unregistered", "nonproject"])
def test_unknown_project_is_not_an_ordinary_project(machine, capsys, command, kind):
    repo, project, _, _ = machine
    target = repo / "projects" / "typo"
    if kind == "unregistered":
        target.mkdir()
        (target / "CONTEXT.md").write_text("# Unknown\n")
    elif kind == "nonproject":
        target = repo
    result, report = cli(machine, command, capsys, project=target)
    assert result != 0 and report["status"] not in {"PASS", "NOT_APPLICABLE"}


def test_unverifiable_adoption_history_refuses_applicability(machine, monkeypatch, capsys):
    original = state._run
    def unavailable(repo, *args, **kwargs):
        if args[0] == "log":
            raise state.ProjectStateError("fixture history unavailable")
        return original(repo, *args, **kwargs)
    monkeypatch.setattr(state, "_run", unavailable)
    result, report = cli(machine, "checkpoint", capsys)
    assert result != 0 and report["status"] not in {"PASS", "NOT_APPLICABLE"}


@pytest.mark.parametrize("missing", [True, False])
def test_owned_hook_unknown_project_cannot_be_not_applicable(machine, monkeypatch, tmp_path, missing):
    repo, project, claims, receipts = machine
    unknown = project.parent / "typo"
    if not missing:
        unknown.mkdir()
    claims.write_text(claims.read_text().replace("alpha", "typo").replace(f"tool:{SESSION}", f"codex:{SESSION}"))
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", f"codex:{SESSION}")
    payload = native_hook_fixture(tmp_path, monkeypatch, "codex", SESSION, repo)
    verdict, _ = state.checkpoint_hook(payload, coordination_board=claims, receipt_root=receipts,
        refresh_coordination=False, repo_guard_root=tmp_path / "repo-guard")
    assert verdict not in {"PASS", "NOT_APPLICABLE"}
    assert not receipts.exists()


def test_narrative_registry_id_cannot_establish_checkpoint_applicability(machine, capsys):
    repo, _, _, _ = machine
    (repo / "projects/index.yaml").write_text("notes: |\n  id: alpha\nprojects:\n  - id: beta\n")
    result, report = cli(machine, "checkpoint", capsys)
    assert result != 0 and report["status"] not in {"PASS", "NOT_APPLICABLE"}

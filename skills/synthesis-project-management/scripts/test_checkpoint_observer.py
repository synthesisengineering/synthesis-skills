"""Native observer completion and owned checkpoint obligations are distinct."""
from __future__ import annotations

import builtins
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest
from jsonschema import Draft7Validator, ValidationError

import coordination
import project_state as state
from test_project_state import board, commit_version, init_repo, run


NATIVE = "018f0000-0000-7000-8000-000000000002"
FOREIGN = "018f0000-0000-7000-8000-000000000001"


# Exact embedded stop.command.output schema from codex-cli 0.153.4.
# Binary SHA-256: 4ca47945439f9251fe35f4cbe071369192cd9a6c5a3a17b75c7a11ad548a9c7f.
# Source contract: https://learn.chatgpt.com/docs/hooks
CODEX_STOP_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "additionalProperties": False,
    "definitions": {"BlockDecisionWire": {"enum": ["block"], "type": "string"}},
    "properties": {
        "continue": {"default": True, "type": "boolean"},
        "decision": {"allOf": [{"$ref": "#/definitions/BlockDecisionWire"}], "default": None},
        "reason": {
            "default": None,
            "description": "Claude requires `reason` when `decision` is `block`; we enforce that semantic rule during output parsing rather than in the JSON schema.",
            "type": "string",
        },
        "stopReason": {"default": None, "type": "string"},
        "suppressOutput": {"default": False, "type": "boolean"},
        "systemMessage": {"default": None, "type": "string"},
    },
    "title": "stop.command.output",
    "type": "object",
}


def native_output(text: str) -> tuple[dict, dict]:
    """Validate the consumer wire format before inspecting Synthesis evidence."""
    output = json.loads(text)
    Draft7Validator(CODEX_STOP_SCHEMA).validate(output)
    message = output["systemMessage"]
    assert message.startswith("PROJECT_CHECKPOINT_JSON: ")
    return output, json.loads(message.removeprefix("PROJECT_CHECKPOINT_JSON: "))


@pytest.fixture
def observer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    for key in ("SYNTHESIS_CLIENT_SESSION_REF", "CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_HOST_SESSION_ID", "CLAUDECODE"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("SYNTHESIS_HOME", str(tmp_path / ".synthesis"))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / ".claude"))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / ".codex"))
    repo, project = init_repo(tmp_path)
    state.build_operational_state(
        project, project_id="alpha", phase="release 1.0.0", status="active",
        controlling_plan="resources/artifacts/plan.md", accepted_baseline="1.0.0",
        next_actions=["finish"], last_session="2026-09-03", session_id=FOREIGN,
    )
    run("git", "add", "projects", cwd=repo)
    run("git", "commit", "-m", "Record structured state", cwd=repo)
    transcripts = {
        "claude": tmp_path / ".claude" / "projects" / "fixture-workspace" / f"{NATIVE}.jsonl",
        "codex": tmp_path / ".codex" / "sessions" / "fixture.jsonl",
    }
    for client, path in transcripts.items():
        path.parent.mkdir(parents=True)
        record = {"type": "user", "sessionId": NATIVE} if client == "claude" else {"type": "session_meta", "payload": {"id": NATIVE}}
        path.write_text(json.dumps(record) + "\n", encoding="utf-8")
    claims = board(tmp_path / "board.md", [])
    return SimpleNamespace(
        root=tmp_path, repo=repo, project=project, board=claims,
        receipts=tmp_path / "receipts", guard=tmp_path / ".synthesis" / "repo-guard",
        transcripts=transcripts,
    )


def event(fixture: SimpleNamespace, client: str = "claude", **changes: object) -> dict:
    return {"session_id": NATIVE, "cwd": str(fixture.project),
            "transcript_path": str(fixture.transcripts[client]),
            "hook_event_name": "Stop", "stop_hook_active": False, **changes}


def inspect(fixture: SimpleNamespace, payload: dict | None = None) -> tuple[str, list[str]]:
    return state.checkpoint_hook(
        event(fixture) if payload is None else payload,
        coordination_board=fixture.board, receipt_root=fixture.receipts,
        repo_guard_root=fixture.guard, refresh_coordination=False,
    )


def assert_no_receipt(fixture: SimpleNamespace) -> None:
    assert not fixture.receipts.exists()


@pytest.mark.parametrize("client", ["claude", "codex"])
def test_clean_native_observer_has_no_checkpoint_authority(observer: SimpleNamespace, client: str, monkeypatch: pytest.MonkeyPatch) -> None:
    before = {path: path.read_bytes() for path in observer.project.rglob("*") if path.is_file()}
    board_before = observer.board.read_bytes()
    calls = []
    original = state._observer_git

    def guarded_git(project: Path, *arguments: str):
        calls.append(arguments)
        assert arguments[0] in {"ls-files", "status"}
        return original(project, *arguments)

    monkeypatch.setattr(state, "_observer_git", guarded_git)
    monkeypatch.setattr(state, "checkpoint_project", lambda *_a, **_k: pytest.fail("observer cannot checkpoint"))
    verdict, issues = inspect(observer, event(observer, client))
    assert verdict == "NOT_APPLICABLE"
    assert "no recovery/state-health PASS" in " ".join(issues)
    assert calls and observer.board.read_bytes() == board_before
    assert {path: path.read_bytes() for path in before} == before
    assert not observer.guard.exists()
    assert_no_receipt(observer)


@pytest.mark.parametrize("mutation", ["edit", "delete", "staged", "untracked", "deleted_state"])
def test_observer_dirty_project_remains_blocked(observer: SimpleNamespace, mutation: str) -> None:
    target = observer.project / "REFERENCE.md"
    if mutation in {"edit", "staged"}:
        target.write_text("retained edit\n", encoding="utf-8")
        if mutation == "staged":
            run("git", "add", str(target), cwd=observer.repo)
    elif mutation == "delete":
        target.unlink()
    elif mutation == "deleted_state":
        (observer.project / state.STATE_FILE).unlink()
    else:
        (observer.project / "retained.txt").write_text("retained\n", encoding="utf-8")
    before = run("git", "status", "--porcelain=v1", cwd=observer.repo)
    verdict, issues = inspect(observer)
    assert verdict == "UNKNOWN" and "changes" in " ".join(issues)
    assert run("git", "status", "--porcelain=v1", cwd=observer.repo) == before
    assert_no_receipt(observer)


@pytest.mark.parametrize("kind", ["valid", "malformed", "wrong_session", "bad_schema", "empty_paths", "relative_path", "symlink"])
def test_exact_native_pending_attribution_blocks(observer: SimpleNamespace, kind: str) -> None:
    pending = observer.guard / "pending"
    pending.mkdir(parents=True)
    own = pending / (hashlib.sha256(NATIVE.encode()).hexdigest() + ".json")
    data = {"schema_version": 2, "session_id": NATIVE, "paths": [str(observer.project / "REFERENCE.md")]}
    if kind == "wrong_session":
        data["session_id"] = FOREIGN
    elif kind == "bad_schema":
        data["schema_version"] = True
    elif kind == "empty_paths":
        data["paths"] = []
    elif kind == "relative_path":
        data["paths"] = ["REFERENCE.md"]
    if kind == "symlink":
        target = observer.root / "retained.json"
        target.write_text(json.dumps(data), encoding="utf-8")
        own.symlink_to(target)
    else:
        own.write_text("{" if kind == "malformed" else json.dumps(data), encoding="utf-8")
    before = own.read_bytes()
    verdict, _issues = inspect(observer)
    assert verdict == ("UNKNOWN" if kind == "valid" else "FAIL")
    assert own.read_bytes() == before
    assert_no_receipt(observer)


def test_foreign_pending_and_unrelated_dirty_work_are_preserved(observer: SimpleNamespace) -> None:
    pending = observer.guard / "pending"
    pending.mkdir(parents=True)
    foreign = pending / (hashlib.sha256(FOREIGN.encode()).hexdigest() + ".json")
    foreign.write_text("malformed retained foreign evidence {", encoding="utf-8")
    unrelated = observer.repo / "projects" / "beta"
    unrelated.mkdir()
    retained = unrelated / "notes.md"
    retained.write_text("foreign work\n", encoding="utf-8")
    run("git", "add", str(retained), cwd=observer.repo)
    before = foreign.read_bytes(), retained.read_bytes(), run("git", "diff", "--cached", cwd=observer.repo)
    assert inspect(observer)[0] == "NOT_APPLICABLE"
    assert (foreign.read_bytes(), retained.read_bytes(), run("git", "diff", "--cached", cwd=observer.repo)) == before
    assert_no_receipt(observer)


@pytest.mark.parametrize("malformed", [False, True])
def test_known_native_pending_work_blocks_from_workspace_root(observer: SimpleNamespace, malformed: bool) -> None:
    pending = observer.guard / "pending"
    pending.mkdir(parents=True)
    own = pending / (hashlib.sha256(NATIVE.encode()).hexdigest() + ".json")
    data = {"schema_version": 2, "session_id": NATIVE, "paths": [str(observer.project / "REFERENCE.md")]}
    own.write_text("{" if malformed else json.dumps(data), encoding="utf-8")
    before = own.read_bytes()
    verdict, _issues = inspect(observer, event(observer, cwd=str(observer.root)))
    assert verdict == ("FAIL" if malformed else "UNKNOWN")
    assert own.read_bytes() == before
    assert_no_receipt(observer)


def test_nonproject_session_without_pending_work_retains_applicability(observer: SimpleNamespace) -> None:
    assert inspect(observer, {"cwd": str(observer.root), "session_id": "legacy-session"}) == ("NOT_APPLICABLE", [])
    assert_no_receipt(observer)


@pytest.mark.parametrize("defect", ["missing_uuid", "invalid_uuid", "missing_transcript", "foreign_binding", "outside_root", "symlink", "parent_symlink", "empty_home", "relative_home"])
@pytest.mark.parametrize("client", ["claude", "codex"])
def test_observer_identity_is_native_and_fail_closed(observer: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, client: str, defect: str) -> None:
    payload = event(observer, client)
    path = observer.transcripts[client]
    if defect == "missing_uuid":
        payload.pop("session_id")
    elif defect == "invalid_uuid":
        payload["session_id"] = "legacy-session"
    elif defect == "missing_transcript":
        payload.pop("transcript_path")
    elif defect == "foreign_binding":
        path.write_text(path.read_text().replace(NATIVE, FOREIGN), encoding="utf-8")
    elif defect == "outside_root":
        outside = observer.root / "untrusted.jsonl"
        outside.write_bytes(path.read_bytes())
        payload["transcript_path"] = str(outside)
    elif defect == "symlink":
        target = path.with_suffix(".saved")
        path.rename(target)
        path.symlink_to(target)
    elif defect == "parent_symlink":
        parent = path.parent
        target = parent.with_name(parent.name + "-saved")
        parent.rename(target)
        parent.symlink_to(target, target_is_directory=True)
    else:
        variable = "CLAUDE_CONFIG_DIR" if client == "claude" else "CODEX_HOME"
        monkeypatch.setenv(variable, "" if defect == "empty_home" else "relative/home")
    assert inspect(observer, payload)[0] == "FAIL"
    assert_no_receipt(observer)


def test_missing_native_validator_fails_closed(observer: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    original = builtins.__import__

    def missing(name, *args, **kwargs):
        if name == "live_receipt":
            raise ImportError("fixture missing installed dependency")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", missing)
    verdict, issues = inspect(observer)
    assert verdict == "FAIL" and "validator is unavailable" in " ".join(issues)
    assert state._emit_checkpoint_hook(verdict, issues, event(observer)) == 2
    assert "remains FAIL" in capsys.readouterr().err
    assert_no_receipt(observer)


def test_foreign_ambient_identity_cannot_grant_checkpoint_authority(observer: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    board(observer.board, [(FOREIGN, "s-abcd-efgh-jkmn", "alpha", str(observer.repo))])
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", f"codex:{FOREIGN}")
    verdict, issues = inspect(observer, event(observer, "codex"))
    assert verdict == "FAIL" and "foreign checkpoint" in " ".join(issues)
    assert_no_receipt(observer)


def test_empty_board_identity_does_not_bind_foreign_seat(observer: SimpleNamespace) -> None:
    row = {"status": "active", "client session ref": "", "session uuid": FOREIGN}
    assert state._row_for_event([row], event(observer)) is None
    row["session uuid"] = ""
    assert state._row_for_event([row], event(observer)) is None
    assert state._row_for_event([row], {}) is None


def test_matching_native_reference_and_empty_optional_reference_are_safe(observer: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    for value in ("", f"cc:{NATIVE}"):
        monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", value)
        assert inspect(observer)[0] == "NOT_APPLICABLE"
    assert_no_receipt(observer)


def test_owner_checkpoint_authority_is_preserved(observer: SimpleNamespace) -> None:
    board(observer.board, [(FOREIGN, "s-abcd-efgh-jkmn", "alpha", str(observer.repo))])
    payload = {"session_id": FOREIGN, "cwd": str(observer.project)}
    assert inspect(observer, payload) == ("PASS", [])
    receipt_path = next(observer.receipts.glob("*.json"))
    receipt = json.loads(receipt_path.read_text())
    assert receipt["session_id"] == FOREIGN and receipt["project_id"] == "alpha"
    accepted = receipt_path.read_bytes()
    (observer.project / "CONTEXT.md").write_text("uncheckpointed owner edit\n", encoding="utf-8")
    verdict, issues = inspect(observer, payload)
    assert verdict == "FAIL" and any("changed" in issue for issue in issues)
    assert receipt_path.read_bytes() == accepted


def test_clean_stale_semantics_are_not_reported_as_recovery_pass(observer: SimpleNamespace) -> None:
    (observer.project / "resources" / "artifacts" / "plan.md").write_text("# Changed plan\n", encoding="utf-8")
    run("git", "add", "projects", cwd=observer.repo)
    run("git", "commit", "-m", "Record plan change", cwd=observer.repo)
    assert state.semantic_issues(observer.project)
    verdict, issues = inspect(observer)
    assert verdict == "NOT_APPLICABLE" and "no recovery/state-health PASS" in " ".join(issues)
    assert_no_receipt(observer)


def test_clean_causal_conflict_can_finish_reporting_without_checkpoint(observer: SimpleNamespace) -> None:
    run("git", "checkout", "-b", "feature/a", cwd=observer.repo)
    commit_version(observer.repo, observer.project, "2.0.0")
    run("git", "checkout", "main", cwd=observer.repo)
    commit_version(observer.repo, observer.project, "3.0.0")
    recovery = state.resolve_project("alpha", observer.repo / "projects" / "index.yaml", fetch=False)
    assert recovery.status == "CONFLICT"
    assert inspect(observer)[0] == "NOT_APPLICABLE"
    assert_no_receipt(observer)


def test_unverifiable_project_git_state_cannot_exonerate_observer(observer: SimpleNamespace) -> None:
    outside = observer.root / "not-a-repository"
    outside.mkdir()
    (outside / state.STATE_FILE).write_text("{}", encoding="utf-8")
    verdict, issues = inspect(observer, event(observer, cwd=str(outside)))
    assert verdict == "FAIL" and "Git state" in " ".join(issues)
    assert_no_receipt(observer)


def test_claude_reentrant_stop_terminates_with_blocked_verdict(observer: SimpleNamespace, capsys: pytest.CaptureFixture) -> None:
    (observer.project / "REFERENCE.md").write_text("unattributed edit\n", encoding="utf-8")
    payload = event(observer)
    verdict, issues = inspect(observer, payload)
    assert state._emit_checkpoint_hook(verdict, issues, payload) == 2
    first = capsys.readouterr()
    assert "remains UNKNOWN" in first.err and "Preserve retained work" in first.err
    first_output, first_report = native_output(first.out)
    assert "continue" not in first_output and first_report["status"] == "UNKNOWN"
    payload["stop_hook_active"] = True
    assert state._emit_checkpoint_hook(verdict, issues, payload) == 0
    repeated = capsys.readouterr()
    terminal, report = native_output(repeated.out)
    assert report["status"] == "UNKNOWN" and terminal["continue"] is False
    assert report["checkpoint_accepted"] is False
    assert "remains UNKNOWN" in terminal["stopReason"] and repeated.err
    assert_no_receipt(observer)


@pytest.mark.parametrize("client,active,event_name", [("codex", True, "Stop"), ("claude", "true", "Stop"), ("claude", True, "PreCompact")])
def test_codex_never_consumes_claude_terminal_control(observer: SimpleNamespace, capsys: pytest.CaptureFixture, client: str, active: object, event_name: str) -> None:
    payload = event(observer, client, stop_hook_active=active, hook_event_name=event_name)
    assert state._emit_checkpoint_hook("FAIL", ["retained owner obligation"], payload) == 2
    output = capsys.readouterr()
    wire, report = native_output(output.out)
    assert report["checkpoint_accepted"] is False
    assert "continue" not in wire and output.err
    assert_no_receipt(observer)


def test_real_hook_cli_uses_local_lease_and_actionable_failure(observer: SimpleNamespace) -> None:
    remote = observer.root / "coordination.git"
    run("git", "init", "--bare", str(remote), cwd=observer.root)
    (observer.root / "lease.json").write_text(json.dumps({"remote": str(remote)}), encoding="utf-8")
    observer.board.write_text(coordination.template(), encoding="utf-8")
    coordination.locked_update(observer.board, lambda content: content)
    before = observer.board.read_bytes()

    def cli(payload: object) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-B", str(Path(state.__file__)), "hook", "--coordination-board", str(observer.board),
             "--receipt-root", str(observer.receipts), "--repo-guard-root", str(observer.guard)],
            input=json.dumps(payload), capture_output=True, text=True, timeout=30,
        )

    clean = cli(event(observer))
    assert clean.returncode == 0, clean.stderr
    _wire, report = native_output(clean.stdout)
    assert report == {"status": "NOT_APPLICABLE", "issues": inspect(observer)[1], "checkpoint_accepted": False, "no_receipt_issued": True}
    clean_codex = cli(event(observer, "codex"))
    assert clean_codex.returncode == 0, clean_codex.stderr
    assert native_output(clean_codex.stdout)[1] == report
    (observer.project / "REFERENCE.md").write_text("retained edit\n", encoding="utf-8")
    first = cli(event(observer))
    assert first.returncode == 2 and "remains UNKNOWN" in first.stderr
    assert native_output(first.stdout)[1]["status"] == "UNKNOWN"
    repeated = cli(event(observer, stop_hook_active=True))
    wire, report = native_output(repeated.stdout)
    assert repeated.returncode == 0 and wire["continue"] is False
    assert report["status"] == "UNKNOWN"
    codex = cli(event(observer, "codex", stop_hook_active=True))
    wire, report = native_output(codex.stdout)
    assert codex.returncode == 2 and "continue" not in wire
    assert report["status"] == "UNKNOWN" and not report["checkpoint_accepted"]
    malformed = cli([])
    assert malformed.returncode == 2 and "not an object" in malformed.stderr
    assert native_output(malformed.stdout)[1]["status"] == "UNKNOWN"
    assert observer.board.read_bytes() == before
    assert_no_receipt(observer)


@pytest.mark.parametrize("verdict", ["PASS", "NOT_APPLICABLE", "UNKNOWN", "FAIL", "LOCAL_RECOVERABLE"])
def test_stop_output_conforms_to_native_codex_consumer_schema(observer: SimpleNamespace, capsys: pytest.CaptureFixture, verdict: str) -> None:
    result = state._emit_checkpoint_hook(verdict, ["bounded fixture evidence"], event(observer, "codex"))
    captured = capsys.readouterr()
    wire, report = native_output(captured.out)
    assert set(wire) == {"systemMessage"}
    assert report["status"] == verdict
    assert report["issues"] == ["bounded fixture evidence"]
    assert report["checkpoint_accepted"] is (verdict == "PASS")
    assert report.get("no_receipt_issued") is (True if verdict == "NOT_APPLICABLE" else None)
    assert result == (0 if verdict in {"PASS", "NOT_APPLICABLE"} else 2)
    assert bool(captured.err) is (result == 2)


def test_old_diagnostic_stdout_is_rejected_by_native_codex_schema() -> None:
    serialized = json.dumps(CODEX_STOP_SCHEMA, indent=2, sort_keys=True) + "\n"
    assert hashlib.sha256(serialized.encode()).hexdigest() == "37679d1a933fdc3dc8cea5ff12d7d0e2dacfc036208d134aefc09247e1222d88"
    Draft7Validator.check_schema(CODEX_STOP_SCHEMA)
    old_output = {"status": "NOT_APPLICABLE", "issues": [], "checkpoint_accepted": False, "no_receipt_issued": True}
    with pytest.raises(ValidationError, match="Additional properties are not allowed"):
        Draft7Validator(CODEX_STOP_SCHEMA).validate(old_output)

"""The board inbox hook: addressed messages reach the seat they name, once, in both clients."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import board_inbox as INBOX  # noqa: E402
import coordination as ENGINE  # noqa: E402

ME_SID = "11111111-1111-4111-8111-111111111111"
ME_ENV = {"CLAUDECODE": "1", "CLAUDE_CODE_SESSION_ID": ME_SID, "CLAUDE_CODE_HOST_SESSION_ID": "local_me"}
EARLIER_ENV = {"SYNTHESIS_CLIENT_SESSION_REF": "codex:earlier-seat"}


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch):
    for name in ("SYNTHESIS_CLIENT_SESSION_REF", "CLAUDE_CODE_HOST_SESSION_ID", "CLAUDE_CODE_SESSION_ID", "CLAUDE_PID", "CLAUDECODE"):
        monkeypatch.delenv(name, raising=False)


def args(board: Path, **values):
    return type("Args", (), {"board": board, **values})()


def claim(board: Path, project: str, env: dict, monkeypatch):
    for key in ("CLAUDECODE", "CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_HOST_SESSION_ID", "SYNTHESIS_CLIENT_SESSION_REF"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    request = args(board, id=None, agent="agent", machine="m1", project=project, mode="interactive", goal="g", workspace=[f"/tmp/wt-{project} @ feature/{project}"], area=[f"repo-{project}/**"], context_role="owner")
    assert ENGINE.command_claim(request) == 0
    return [row for row in ENGINE.rows(board.read_text(encoding="utf-8")) if row.project == project][0]


@pytest.fixture
def board(tmp_path, monkeypatch):
    path = tmp_path / "board.md"
    other = claim(path, "project-o", {}, monkeypatch)
    me = claim(path, "project-m", ME_ENV, monkeypatch)
    assert ENGINE.command_message(args(path, sender=other.compact_id, to=me.compact_id, text="Handoff: the review is yours.")) == 0
    assert ENGINE.command_message(args(path, sender=other.compact_id, to="project-m", text="For every project-m session.")) == 0
    assert ENGINE.command_message(args(path, sender=other.compact_id, to=other.compact_id, text="Not for me.")) == 0
    return path


def test_inbox_delivers_once_to_the_named_seat(board, tmp_path) -> None:
    payload = {"session_id": ME_SID, "hook_event_name": "UserPromptSubmit", "cwd": "/tmp"}
    text = INBOX.inbox_text(payload, board=board, environ=ME_ENV)
    assert "2 unread message(s)" in text
    assert "Handoff: the review is yours." in text and "For every project-m session." in text
    assert "Not for me." not in text
    assert INBOX.inbox_text(payload, board=board, environ=ME_ENV) == ""


def test_project_history_before_the_claim_is_not_delivered_to_a_new_seat(tmp_path, monkeypatch) -> None:
    """An earlier seat of the project received a message weeks ago; a seat
    claimed today must not see it as unread, while a message posted after
    its claim is delivered."""
    path = tmp_path / "board.md"
    other = claim(path, "project-o", {}, monkeypatch)
    earlier = claim(path, "project-m", EARLIER_ENV, monkeypatch)
    assert ENGINE.command_message(args(path, sender=other.compact_id, to="project-m", text="Posted before the seat existed.")) == 0
    assert ENGINE.command_release(args(path, id=earlier.compact_id)) == 0
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"(### → project-m sessions, from \S+ — )\S+", r"\g<1>2026-01-01T00:00:00-05:00", text, count=1)
    path.write_text(text, encoding="utf-8")
    me = claim(path, "project-m", ME_ENV, monkeypatch)
    assert ENGINE.command_message(args(path, sender=other.compact_id, to="project-m", text="Posted after the claim.")) == 0
    delivered = INBOX.inbox_text({"session_id": ME_SID}, board=path, environ=ME_ENV)
    assert "Posted after the claim." in delivered
    assert "Posted before the seat existed." not in delivered
    assert "1 unread message(s)" in delivered
    assert me.project == "project-m"


def test_unseated_session_receives_nothing_even_when_a_global_pointer_names_a_project(board, tmp_path) -> None:
    """2026-09-03: the fallback to the global active-project pointer delivered
    another project's message to a seatless session. The pointer is another
    session's cache; without a seat there is no address."""
    pointer = tmp_path / "pointer.json"
    pointer.write_text(json.dumps({"project": "/kb/projects/project-m"}), encoding="utf-8")
    stranger = {"CLAUDECODE": "1", "CLAUDE_CODE_SESSION_ID": "99999999-9999-4999-8999-999999999999"}
    assert INBOX.inbox_text({"session_id": stranger["CLAUDE_CODE_SESSION_ID"]}, board=board, environ=stranger) == ""
    assert not hasattr(INBOX, "pointer_project"), "the pointer fallback must not exist"


def test_codex_session_learns_its_identity(board, tmp_path) -> None:
    text = INBOX.inbox_text({"session_id": "0a0a0a0a-1b1b-4c1c-8d1d-2e2e2e2e2e2e"}, board=board, environ={"CODEX_HOME": "/x"})
    assert "SYNTHESIS_CLIENT_SESSION_REF=codex:0a0a0a0a-1b1b-4c1c-8d1d-2e2e2e2e2e2e" in text


def test_no_session_id_means_silence(board, tmp_path) -> None:
    assert INBOX.inbox_text({}, board=board, environ={}) == ""


def test_live_inbox_refuses_stale_delivery_without_advancing_watermark(board, monkeypatch):
    import coordination as live_engine
    before = {str(p.relative_to(board.parent)): p.read_bytes() for p in board.parent.rglob("*") if p.is_file()}
    monkeypatch.setattr(live_engine, "lease_refresh", lambda _board: {"configured": True, "refreshed": False, "error": "fixture outage"})
    with pytest.raises(RuntimeError, match="fixture outage"):
        INBOX.inbox_text({"session_id": ME_SID}, board=board, environ=ME_ENV)
    after = {str(p.relative_to(board.parent)): p.read_bytes() for p in board.parent.rglob("*") if p.is_file()}
    assert after == before


def test_diagnostic_inbox_never_fetches_or_marks(board, monkeypatch):
    import coordination as live_engine
    monkeypatch.setattr(live_engine, "lease_refresh", lambda *_a, **_kw: pytest.fail("diagnostic must not refresh"))
    first = INBOX.inbox_text({"session_id": ME_SID}, board=board, environ=ME_ENV, strict=True, mark=False)
    assert "2 unread message(s)" in first
    assert INBOX.inbox_text({"session_id": ME_SID}, board=board, environ=ME_ENV, strict=True, mark=False) == first


def test_hook_process_emits_additional_context_json_or_nothing(board, tmp_path) -> None:
    script = SCRIPTS_DIR / "board_inbox.py"
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE") and k != "SYNTHESIS_CLIENT_SESSION_REF"}
    env.update(ME_ENV)
    payload = json.dumps({"session_id": ME_SID, "hook_event_name": "UserPromptSubmit"})
    first = subprocess.run([sys.executable, str(script), "--board", str(board), "--hook"], input=payload, capture_output=True, text=True, env=env)
    assert first.returncode == 0, first.stderr
    data = json.loads(first.stdout)
    assert data["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    assert "2 unread message(s)" in data["hookSpecificOutput"]["additionalContext"]
    second = subprocess.run([sys.executable, str(script), "--board", str(board), "--hook"], input=payload, capture_output=True, text=True, env=env)
    assert second.returncode == 0 and second.stdout == ""


def test_session_context_appends_the_inbox(board, tmp_path) -> None:
    conformance = SCRIPTS_DIR.parents[1] / "synthesis-agent-conformance" / "scripts" / "session_context.py"
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE") and k != "SYNTHESIS_CLIENT_SESSION_REF"}
    env.update(ME_ENV)
    env["SYNTHESIS_PUBLIC_SESSIONSTART_RECEIPT"] = str(tmp_path / "receipt.json")
    payload = json.dumps({"session_id": ME_SID, "hook_event_name": "SessionStart", "cwd": str(tmp_path)})
    run = subprocess.run([sys.executable, str(conformance), "--active-project-file", str(tmp_path / "pointer.json"), "--coordination-board", str(board), "--format", "claude"], input=payload, capture_output=True, text=True, env=env)
    assert run.returncode == 0, run.stderr
    context = json.loads(run.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "Coordination board inbox: 2 unread" in context


def test_diagnostic_inbox_survives_a_stale_schema1_seat_file(board, monkeypatch, capsys):
    # Regression 2026-09-20: a pre-migration seat left by a released session
    # made the SessionStart diagnostic exit 2 with no context.
    import peer_addressing as PA
    from coordination_schema import identity_from_uuid
    stale_uuid = "018f0000-0000-7000-8000-00000000aa02"
    stale = PA.seat_path(board, stale_uuid)
    stale.write_text(json.dumps({
        "session_uuid": stale_uuid, "compact_id": identity_from_uuid(stale_uuid).compact_id,
        "client": "codex", "machine": "fixture-hostname", "harness_session_id": "dead", "host_session_id": "",
        "pid": None, "cwd": "/tmp", "updated_at": "2026-09-14T21:15:13+00:00", "schema": 1,
    }), encoding="utf-8")
    text = INBOX.inbox_text({"session_id": ME_SID}, board=board, environ=ME_ENV, strict=True, mark=False)
    assert "2 unread message(s)" in text
    assert stale.name in capsys.readouterr().err


MUSE_SID = "muse-probe-001"


@pytest.mark.parametrize("client", ["codex", "muse", "claude-cli", "claude-desktop"])
def test_hook_payload_identity_honors_without_shell_session_export(tmp_path, monkeypatch, client):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    board = tmp_path / "board.md"
    area = f"{repo}/claimed/**"
    sid = "11111111-1111-4111-8111-111111111111"
    if client == "codex":
        claim_env = {"SYNTHESIS_CLIENT_SESSION_REF": "codex:" + sid}
        hook_env = {"CODEX_HOME": str(tmp_path / "codex")}
    elif client == "muse":
        claim_env = {"SYNTHESIS_CLIENT_SESSION_REF": "muse:" + sid}
        hook_env = {"SYNTHESIS_HOOK_CLIENT": "muse"}
    else:
        claim_env = {"CLAUDECODE": "1", "CLAUDE_CODE_SESSION_ID": sid}
        hook_env = {"CLAUDECODE": "1"}
        if client == "claude-desktop":
            claim_env["CLAUDE_CODE_HOST_SESSION_ID"] = "local_holder"
            hook_env["CLAUDE_CODE_HOST_SESSION_ID"] = "local_holder"
    for key, value in claim_env.items():
        monkeypatch.setenv(key, value)
    assert ENGINE.command_claim(args(
        board, id=None, agent="agent", machine="m1", project="project-h",
        mode="interactive", goal="g", workspace=[f"{repo} @ main"],
        area=[area], context_role="owner",
    )) == 0
    holder = [row for row in ENGINE.rows(board.read_text()) if row.project == "project-h"][0]
    claim(board, "project-q", {"SYNTHESIS_CLIENT_SESSION_REF": "codex:requester"}, monkeypatch)
    assert ENGINE.command_request_narrow(args(board, holder=holder.compact_id, area=[area], reason="need it")) == 0
    [request] = ENGINE.open_release_requests(board.read_text())
    for key in ("SYNTHESIS_CLIENT_SESSION_REF", "CLAUDE_CODE_HOST_SESSION_ID", "CLAUDE_CODE_SESSION_ID", "CLAUDECODE", "SYNTHESIS_HOOK_CLIENT"):
        monkeypatch.delenv(key, raising=False)
    # This is the actual native-hook shape: identity is in the host payload,
    # and the shell-only session export is absent.
    text = INBOX.inbox_text({"session_id": sid, "cwd": str(repo)}, board=board, environ=hook_env)
    assert f"honored {request.id}: narrowed {area}" in text
    assert ENGINE.parse_release_replies(board.read_text()) == {request.id: "narrowed"}
    assert "SYNTHESIS_CLIENT_SESSION_REF" not in os.environ


def test_per_turn_inbox_honors_open_requests(tmp_path, monkeypatch) -> None:
    # S13 layer 2: the holder's next prompt narrows clean requested areas
    # and says so in the injected text.
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    board = tmp_path / "board.md"
    area = f"{repo}/claimed/**"
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", "codex:holder-x")
    assert ENGINE.command_claim(args(
        board, id=None, agent="agent", machine="m1", project="project-h",
        mode="interactive", goal="g", workspace=[f"{repo} @ main"],
        area=[area], context_role="owner",
    )) == 0
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", "codex:requester-x")
    assert ENGINE.command_claim(args(
        board, id=None, agent="agent", machine="m1", project="project-q",
        mode="interactive", goal="g", workspace=["/tmp/repo-q @ main"],
        area=["elsewhere/**"], context_role="owner",
    )) == 0
    holder = [row for row in ENGINE.rows(board.read_text(encoding="utf-8")) if row.project == "project-h"][0]
    assert ENGINE.command_request_narrow(args(board, holder=holder.compact_id, area=[area], reason="need it")) == 0
    [req] = ENGINE.open_release_requests(board.read_text(encoding="utf-8"))
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", "codex:holder-x")
    payload = {"session_id": "holder-x", "hook_event_name": "UserPromptSubmit", "cwd": str(repo)}
    text = INBOX.inbox_text(payload, board=board, environ={"SYNTHESIS_CLIENT_SESSION_REF": "codex:holder-x"})
    assert f"honored {req.id}: narrowed {area}" in text
    assert ENGINE.parse_release_replies(board.read_text(encoding="utf-8")) == {req.id: "narrowed"}


def test_muse_wrapper_delivers_and_consumes(tmp_path, monkeypatch) -> None:
    # S13 layer 1: the UserPromptSubmit wrapper resolves the Muse seat and
    # injects addressed messages as hook JSON, forwarding its argv.
    board = tmp_path / "muse-board.md"
    me = claim(board, "project-q", {"SYNTHESIS_CLIENT_SESSION_REF": f"muse:{MUSE_SID}"}, monkeypatch)
    assert ENGINE.command_message(args(board, sender=me.compact_id, to=me.compact_id, text="Per-turn hello.")) == 0
    wrapper = SCRIPTS_DIR.parents[2] / ".muse-plugin" / "hooks" / "synthesis-inbox.sh"
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE") and k != "SYNTHESIS_CLIENT_SESSION_REF"}
    env["SYNTHESIS_HOOK_CLIENT"] = "muse"
    payload = json.dumps({"session_id": MUSE_SID, "hook_event_name": "UserPromptSubmit"})
    first = subprocess.run(["sh", str(wrapper), "--board", str(board)], input=payload, capture_output=True, text=True, env=env)
    assert first.returncode == 0, first.stderr
    data = json.loads(first.stdout)
    assert data["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    assert "Per-turn hello." in data["hookSpecificOutput"]["additionalContext"]
    second = subprocess.run(["sh", str(wrapper), "--board", str(board)], input=payload, capture_output=True, text=True, env=env)
    assert second.returncode == 0 and "Per-turn hello." not in second.stdout

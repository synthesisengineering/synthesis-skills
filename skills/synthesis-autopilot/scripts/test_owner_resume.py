"""Released-seat recovery uses real PM and native readers in isolated fixtures."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from test_run_state import engine, world, create, command, NATIVE  # noqa: F401


@pytest.fixture
def resumed(world, engine, monkeypatch, request):
    import coordination
    # Real PM allocation/release/reallocation; native files are synthetic.
    for key in ("CLAUDE_CODE_HOST_SESSION_ID", "CLAUDE_CODE_SESSION_ID", "CODEX_THREAD_ID", "CLAUDE_PID", "CLAUDECODE"):
        monkeypatch.delenv(key, raising=False)
    world["board"] = world["scratch"] / "official" / "active-sessions.md"
    world["actor"]["board"] = str(world["board"])
    client = getattr(request, "param", "claude")
    if client == "codex":
        root = world["scratch"] / "codex"
        world["transcript"] = root / "sessions" / "rollout.jsonl"
        world["transcript"].parent.mkdir(parents=True)
        world["transcript"].write_text(json.dumps({"type": "session_meta", "payload": {"id": NATIVE}}) + "\n")
        world["actor"]["native_payload"]["transcript_path"] = str(world["transcript"])
        monkeypatch.setenv("CODEX_HOME", str(root))
        monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", "codex:" + NATIVE)
    def claim():
        args = coordination.parser().parse_args(["--board", str(world["board"]), "claim",
            "--agent", client, "--project", "alpha", "--mode", "fixture", "--goal", "Recovery fixture",
            "--workspace", f"{world['repo']} @ main", "--area", f"{world['project']}/**", "--context-role", "owner"])
        assert coordination.command_claim(args) == 0
    claim()
    state = create(engine, world)
    state = command(engine, world, state, "wait.add", {"id": "human", "kind": "user", "reason": "Pause for restart"})
    def obligations(s, payload, context):
        s["extensions"]["retained"] = {"measured": None, "forecast": 250000, "failed_attempts": ["retained"],
            "children": {"worker": {"status": "unknown"}}, "deadline": "2026-09-25T13:15:00Z"}
        return s
    engine.register_command("fixture.obligations", obligations, allowed_fields=("extensions",))
    state = command(engine, world, state, "fixture.obligations", {})
    args = coordination.parser().parse_args(["--board", str(world["board"]), "release", "--id", state["owner"]["session_uuid"],
        "--active-project-file", str(world["scratch"] / "active.json")])
    assert coordination.command_release(args) == 0
    claim()
    row = {"type": "user", "sessionId": NATIVE, "uuid": "resume-native-message", "isMeta": False,
        "timestamp": datetime.now(timezone.utc).isoformat(), "message": {"role": "user", "content": "I approve your recommendation. Please proceed."}}
    excerpt = row["message"]["content"]
    if client == "codex":
        row = {"type": "response_item", "timestamp": row["timestamp"],
            "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": excerpt}]}}
    raw = (json.dumps(row) + "\n").encode()
    offset = world["transcript"].stat().st_size
    with world["transcript"].open("ab") as stream:
        stream.write(raw)
    payload = {"previous_owner": {k: state["owner"][k] for k in ("session_uuid", "native_ref")},
        "basis_revision": state["revision"], "basis_digest": engine._digest(state),
        "plan_digest": engine._plan_digest(world["project"], state),
        "user_message": {"offset": offset, "length": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
            "excerpt": excerpt},
        "reason": "The current authenticated owner interprets this direct instruction as resuming this project."}
    return world, state, payload, row


def rewrite_message(world, payload, row):
    raw = (json.dumps(row) + "\n").encode()
    original = world["transcript"].read_bytes()[:payload["user_message"]["offset"]]
    world["transcript"].write_bytes(original + raw)
    payload["user_message"].update(length=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def enable_real_lease(world):
    """Publish this isolated board through PM's real local Git CAS owner."""
    import coordination
    remote = world["scratch"] / "coordination-remote.git"
    subprocess.run(["git", "init", "--bare", "--quiet", str(remote)],
        cwd=world["scratch"], check=True, capture_output=True)
    (world["board"].parent / "lease.json").write_text(json.dumps({"remote": str(remote)}))
    coordination.locked_update(world["board"], lambda text: text)
    return remote


@pytest.mark.parametrize("resumed", ["claude", "codex"], indirect=True)
@pytest.mark.parametrize("fresh_passive_stamp", [False, True])
def test_owner_resume_uses_authoritative_lease_after_admission_invalidates_stamp(engine, resumed, fresh_passive_stamp):
    import coordination
    w, old, payload, _ = resumed
    enable_real_lease(w)
    if fresh_passive_stamp:
        assert coordination.lease_refresh(w["board"])["refreshed"]
        assert coordination.lease_stamp_path(w["board"]).is_file()
    new = command(engine, w, old, "owner.resume", payload, command_id="leased-renew-owner")
    assert new["owner"]["session_uuid"] != old["owner"]["session_uuid"]
    assert new["owner"]["native_ref"] == old["owner"]["native_ref"]
    assert new["status"] == "recovering"
    for key in ("waits", "effects", "contract", "profile", "artifacts", "extensions"):
        assert new[key] == old[key]
    # Authority comes from a fenced PM read, never a manufactured passive stamp.
    assert not coordination.lease_stamp_path(w["board"]).exists()
    assert command(engine, w, old, "owner.resume", payload, command_id="leased-renew-owner") == new


def test_owner_resume_unavailable_lease_never_uses_cached_authority(engine, resumed):
    import coordination
    w, old, payload, _ = resumed
    remote = enable_real_lease(w)
    assert coordination.lease_refresh(w["board"])["refreshed"]
    remote.rename(remote.with_name("unavailable-remote.git"))
    before = {p: p.read_bytes() for p in engine._home(w["project"], old["run_id"]).rglob("*") if p.is_file()}
    with pytest.raises((ValueError, RuntimeError)):
        command(engine, w, old, "owner.resume", payload)
    assert engine.load_run(w["project"], old["run_id"]) == old
    assert all(p.read_bytes() == raw for p, raw in before.items())


@pytest.mark.parametrize("resumed", ["claude", "codex"], indirect=True)
def test_owner_resume_issues_admission_after_real_lease_latency(engine, resumed, monkeypatch):
    import coordination
    import time
    w, old, payload, _ = resumed
    enable_real_lease(w)
    original_fetch = coordination.lease_fetch
    calls = []
    def delayed_fetch(config):
        result = original_fetch(config)
        calls.append(result[0])
        time.sleep(1.05)  # Longer than PM's unchanged unused-admission lifetime.
        return result
    monkeypatch.setattr(coordination, "lease_fetch", delayed_fetch)
    new = command(engine, w, old, "owner.resume", payload)
    assert len(calls) >= 2
    assert new["status"] == "recovering"
    for key in ("waits", "effects", "contract", "profile", "artifacts", "extensions"):
        assert new[key] == old[key]


def test_owner_resume_rejects_predecessor_changed_between_authoritative_reads(engine, resumed, monkeypatch):
    import coordination
    w, old, payload, _ = resumed
    enable_real_lease(w)
    original_fetch = coordination.lease_fetch
    calls = []
    def change_predecessor(config):
        sha, content = original_fetch(config)
        calls.append(sha)
        if len(calls) == 2:
            rows = coordination.rows(content)
            coordination.find_session(rows, old["owner"]["session_uuid"]).project = "changed-project"
            changed = coordination.replace_table(content, rows)
            assert coordination.lease_publish(config, w["board"].name, changed, sha)[0]
            return original_fetch(config)
        return sha, content
    monkeypatch.setattr(coordination, "lease_fetch", change_predecessor)
    with pytest.raises(ValueError):
        command(engine, w, old, "owner.resume", payload)
    assert engine.load_run(w["project"], old["run_id"]) == old


@pytest.mark.parametrize("resumed", ["claude", "codex"], indirect=True)
def test_official_same_native_reallocation_preserves_every_obligation(engine, resumed):
    w, old, payload, row = resumed
    old_events = {p.name: p.read_bytes() for p in (engine._home(w["project"], old["run_id"]) / "events").iterdir()}
    new = command(engine, w, old, "owner.resume", payload, command_id="renew-owner")
    assert new["owner"]["session_uuid"] != old["owner"]["session_uuid"]
    assert new["owner"]["native_ref"] == old["owner"]["native_ref"]
    assert new["status"] == "recovering"
    changed = {k for k in old if old[k] != new[k]}
    assert changed == {"owner", "status", "revision", "updated_at"}
    assert new["waits"]["human"]["status"] == "pending"
    assert new["ownership_recoveries"][-1]["authority_granted"] is False
    assert new["ownership_recoveries"][-1]["user_message"]["excerpt"] == payload["user_message"]["excerpt"]
    assert all((engine._home(w["project"], old["run_id"]) / "events" / name).read_bytes() == raw for name, raw in old_events.items())
    assert command(engine, w, old, "owner.resume", payload, command_id="renew-owner") == new
    with pytest.raises(ValueError):
        command(engine, w, new, "owner.resume", payload, command_id="second-consumption")
    assert engine.owned_runs(w["actor"], runtime_root=w["runtime"])[0]["owner"] == new["owner"]


@pytest.mark.parametrize("resumed", ["claude", "codex"], indirect=True)
def test_restart_acknowledgment_retains_original_wait_and_action_gates(engine, resumed):
    w, old, payload, _ = resumed
    payload["restart_wait"] = {"id": "human", "sha256": engine._digest(old["waits"]["human"])}
    new = command(engine, w, old, "owner.resume", payload, command_id="resume-and-ack")
    assert new["waits"]["human"]["status"] == "resolved"
    assert new["waits"]["human"]["restart_acknowledgment"]["prior"] == old["waits"]["human"]
    assert new["waits"]["human"]["restart_acknowledgment"]["authority_granted"] is False
    assert new["status"] == "recovering"
    assert new["effects"] == old["effects"] and new["contract"] == old["contract"]
    assert new["extensions"] == old["extensions"]
    assert command(engine, w, old, "owner.resume", payload, command_id="resume-and-ack") == new


@pytest.mark.parametrize("fault", ["other-id", "stale-digest", "extra-authority", "future-wait", "external-wait"])
def test_restart_acknowledgment_is_exact_and_never_an_authority_receipt(engine, resumed, fault):
    w, state, payload, _ = resumed
    payload["restart_wait"] = {"id": "human", "sha256": engine._digest(state["waits"]["human"])}
    if fault == "other-id": payload["restart_wait"]["id"] = "different"
    elif fault == "stale-digest": payload["restart_wait"]["sha256"] = "0" * 64
    elif fault == "extra-authority": payload["restart_wait"]["authority_granted"] = True
    else:
        state = deepcopy(state)
        if fault == "future-wait": state["waits"]["human"]["at"] = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        else: state["waits"]["human"]["kind"] = "external"
        payload["restart_wait"]["sha256"] = engine._digest(state["waits"]["human"])
        payload["basis_digest"] = engine._digest(state)
    with pytest.raises(ValueError): engine._command_binding(w["project"], state, w["actor"], "owner.resume", payload)


@pytest.mark.parametrize("resumed", ["claude", "codex"], indirect=True)
def test_real_cli_with_all_owner_constraints(engine, resumed):
    w, old, payload, _ = resumed
    actor_file, payload_file = w["scratch"] / "actor.json", w["scratch"] / "resume.json"
    actor_file.write_text(json.dumps(w["actor"])); payload_file.write_text(json.dumps(payload))
    result = subprocess.run([sys.executable, str(Path(__file__).with_name("autopilot.py")), "command",
        "--project", str(w["project"]), "--run-id", old["run_id"], "--name", "owner.resume",
        "--actor", str(actor_file), "--payload", str(payload_file), "--expected-revision", str(old["revision"]),
        "--command-id", "cli-renewal"], env={**os.environ, "SYNTHESIS_AUTOPILOT_RUNTIME": str(w["runtime"])},
        capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr + result.stdout
    saved = engine.load_run(w["project"], old["run_id"])
    assert saved["status"] == "recovering" and saved["waits"] == old["waits"]


@pytest.mark.parametrize("wrapper", ["<hook_prompt>\n{}\n</hook_prompt>", "<heartbeat>\n{}\n</heartbeat>",
    "```\n{}\n```", "> {}", "<send_user_message_question_reply>{}</send_user_message_question_reply>",
    "```text\n~~~\n{}\n~~~\n```", "~~~~text\n~~~\n{}\n~~~\n~~~~", "    {}", "\t{}", "  \t{}",
    "````text\n```\n{}\n```\n````", "~~~text\n```\n{}\n```\n~~~", "```text\n```not-a-close\n{}",
    "```text\n    ```\n{}", "~~~text\n   ~~\n{}", "~~~text\n{}", "> Quoted example:\n{}",
    "<blockquote>\n\n{}\n\n</blockquote>", "<pre>\n{}\n</pre>", "<!--\n{}\n-->",
    "<blockquote>\n<blockquote>inner</blockquote>\n\n{}\n</blockquote>"])
def test_injected_or_quoted_feedback_cannot_renew_owner(engine, resumed, wrapper):
    w, state, payload, row = resumed
    row["message"]["content"] = wrapper.format(payload["user_message"]["excerpt"])
    rewrite_message(w, payload, row)
    with pytest.raises(ValueError): command(engine, w, state, "owner.resume", payload)
    assert engine.load_run(w["project"], state["run_id"]) == state


@pytest.mark.parametrize("prefix", ["```text\nexample\n```\n\n", "~~~~text\nexample\n~~~~~  \n\n",
    "   ```text\nexample\n  ````\t\n\n", "    example\n\n", "\texample\n\n", "> Quoted example.\n\n",
    "<blockquote>\nexample\n</blockquote>\n\n"])
def test_direct_paragraph_after_correctly_closed_code_remains_usable(engine, resumed, prefix):
    w, state, payload, row = resumed
    row["message"]["content"] = prefix + payload["user_message"]["excerpt"]
    rewrite_message(w, payload, row)
    new = command(engine, w, state, "owner.resume", payload)
    assert new["status"] == "recovering" and new["waits"] == state["waits"]


def test_authenticated_different_native_still_requires_prepared_transfer(engine, resumed, monkeypatch):
    import coordination
    w, state, payload, _ = resumed
    other = "01990000-0000-7000-8000-000000000077"
    content = w["board"].read_text(); rows = coordination.rows(content)
    next(r for r in rows if r.status == "active").client_ref = "cc:" + other
    w["board"].write_text(coordination.replace_table(content, rows))
    transcript = w["transcript"].with_name(other + ".jsonl")
    transcript.write_text(json.dumps({"type": "user", "sessionId": other}) + "\n")
    actor = deepcopy(w["actor"])
    actor["native_payload"].update(session_id=other, transcript_path=str(transcript))
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", "cc:" + other)
    with pytest.raises(ValueError, match="same native"):
        command(engine, w, state, "owner.resume", payload, actor=actor)
    assert engine.load_run(w["project"], state["run_id"]) == state


@pytest.mark.parametrize("fault", ["revision", "digest", "plan", "wrong_previous", "wrong_native", "copied_board", "old_active",
    "no_predecessor", "foreign_project", "stale_message", "future_message", "assistant", "meta", "sidechain", "tool", "quote",
    "wrong_excerpt", "changed_bytes", "offset_bool", "oversized", "cancelled", "completed", "incomplete", "pending_transfer"])
def test_recovery_refuses_without_writing(engine, resumed, fault):
    import coordination
    w, state, payload, row = resumed
    actor = deepcopy(w["actor"])
    if fault == "revision": payload["basis_revision"] -= 1
    elif fault == "digest": payload["basis_digest"] = "0" * 64
    elif fault == "plan": w["plan"].write_text("Changed instructions\n")
    elif fault == "wrong_previous": payload["previous_owner"]["session_uuid"] = "01990000-0000-7000-8000-000000000099"
    elif fault == "wrong_native": payload["previous_owner"]["native_ref"] = "codex:" + NATIVE
    elif fault == "copied_board":
        copied = w["scratch"] / "copied.md"; copied.write_bytes(w["board"].read_bytes()); actor["board"] = str(copied)
    elif fault in {"old_active", "no_predecessor", "foreign_project"}:
        content = w["board"].read_text(); rows = coordination.rows(content)
        old = next(r for r in rows if r.session_uuid == state["owner"]["session_uuid"])
        if fault == "old_active": old.status = "active"
        elif fault == "foreign_project": old.project = "foreign"
        else: rows.remove(old)
        w["board"].write_text(coordination.replace_table(content, rows))
    elif fault in {"stale_message", "future_message", "assistant", "meta", "sidechain", "tool", "quote"}:
        if fault == "stale_message": row["timestamp"] = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        elif fault == "future_message": row["timestamp"] = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        elif fault == "assistant": row["type"] = "assistant"; row["message"]["role"] = "assistant"
        elif fault == "meta": row["isMeta"] = True
        elif fault == "sidechain": row["isSidechain"] = True
        elif fault == "tool": row["message"]["content"] = [{"type": "tool_result", "tool_use_id": "x", "content": payload["user_message"]["excerpt"]}]
        else: row["message"]["content"] = "> " + payload["user_message"]["excerpt"]
        rewrite_message(w, payload, row)
    elif fault == "wrong_excerpt": payload["user_message"]["excerpt"] = "An invented instruction"
    elif fault == "changed_bytes": w["transcript"].write_bytes(w["transcript"].read_bytes().replace(b"Please proceed", b"Please suspend"))
    elif fault == "offset_bool": payload["user_message"]["offset"] = True
    elif fault == "oversized": payload["user_message"]["length"] = 1024 * 1024 * 10
    elif fault in {"cancelled", "completed", "incomplete", "pending_transfer"}:
        # Verify the production admission boundary directly for forbidden old states;
        # no fabricated event is placed in the journal.
        state = deepcopy(state)
        if fault == "pending_transfer": state["handoff"] = {"status": "pending"}
        else: state["status"] = fault
        payload["basis_digest"] = engine._digest(state)
        with pytest.raises(ValueError): engine._command_binding(w["project"], state, actor, "owner.resume", payload)
        return
    before = {p: p.read_bytes() for p in engine._home(w["project"], state["run_id"]).rglob("*") if p.is_file()}
    with pytest.raises(ValueError): command(engine, w, state, "owner.resume", payload, actor=actor)
    assert all(p.read_bytes() == raw for p, raw in before.items())


@pytest.mark.parametrize("fault", ["claim", "message", "plan"])
def test_recovery_revalidates_before_commit(engine, resumed, fault):
    import coordination
    w, state, payload, row = resumed
    def revoke(updated, command_name, body, context):
        if command_name != "owner.resume": return
        if fault == "message": w["transcript"].write_bytes(w["transcript"].read_bytes().replace(b"Please proceed", b"Please suspend"))
        elif fault == "plan": w["plan"].write_text("Changed after reduction\n")
        else:
            content = w["board"].read_text(); rows = coordination.rows(content)
            next(r for r in rows if r.status == "active").status = "released"
            w["board"].write_text(coordination.replace_table(content, rows))
    engine.register_constraint("revoke-after-resume", revoke)
    with pytest.raises(ValueError): command(engine, w, state, "owner.resume", payload)
    assert engine.load_run(w["project"], state["run_id"]) == state

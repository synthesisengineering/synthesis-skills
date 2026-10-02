"""Same-native seat transitions through real PM, journal and replay owners."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json

import pytest

from test_run_state import engine, world, create, command, NATIVE  # noqa: F401
from test_observation_bridge import (bridge, enroll, observe, append, pair,  # noqa: F401
                                     reconcile, reconciliation_spec)


def source(state):
    return state["extensions"]["native_observations"]["sources"]["root"]


def change_seat(engine, world, state, client):
    import coordination
    args = coordination.parser().parse_args([
        "--board", str(world["board"]), "release", "--id", state["owner"]["session_uuid"],
        "--active-project-file", str(world["scratch"] / "active.json")])
    assert coordination.command_release(args) == 0
    claim(world, client)
    excerpt = "Please resume the existing task after restarting."
    timestamp = datetime.now(timezone.utc).isoformat()
    row = {"type": "user", "sessionId": NATIVE, "uuid": "resume-" + str(state["revision"]),
           "isMeta": False, "timestamp": timestamp, "message": {"role": "user", "content": excerpt}}
    if client == "codex":
        row = {"type": "response_item", "timestamp": timestamp,
               "payload": {"type": "message", "role": "user",
                           "content": [{"type": "input_text", "text": excerpt}]}}
    raw = (json.dumps(row) + "\n").encode()
    offset = world["transcript"].stat().st_size
    with world["transcript"].open("ab") as stream:
        stream.write(raw)
    payload = {"previous_owner": {k: state["owner"][k] for k in ("session_uuid", "native_ref")},
               "basis_revision": state["revision"], "basis_digest": engine._digest(state),
               "plan_digest": engine._plan_digest(world["project"], state),
               "user_message": {"offset": offset, "length": len(raw),
                                "sha256": hashlib.sha256(raw).hexdigest(), "excerpt": excerpt},
               "reason": "Direct synthetic same-native restart instruction."}
    return command(engine, world, state, "owner.resume", payload)


def claim(world, client):
    import coordination
    args = coordination.parser().parse_args([
        "--board", str(world["board"]), "claim", "--agent", client,
        "--project", "alpha", "--mode", "fixture", "--goal", "Same-native replay fixture",
        "--workspace", f"{world['repo']} @ main", "--area", f"{world['project']}/**",
        "--context-role", "owner"])
    assert coordination.command_claim(args) == 0


@pytest.fixture(params=["claude", "codex"])
def pending_owner_replay(engine, bridge, world, monkeypatch, request):
    client = request.param
    for key in ("CLAUDE_CODE_HOST_SESSION_ID", "CLAUDE_CODE_SESSION_ID", "CODEX_THREAD_ID", "CLAUDE_PID", "CLAUDECODE"):
        monkeypatch.delenv(key, raising=False)
    world["board"] = world["scratch"] / "official" / "active-sessions.md"
    world["actor"]["board"] = str(world["board"])
    if client == "codex":
        root = world["scratch"] / "codex"
        world["transcript"] = root / "sessions" / "rollout.jsonl"
        world["transcript"].parent.mkdir(parents=True)
        world["transcript"].write_text(json.dumps({"type": "session_meta", "payload": {"id": NATIVE}}) + "\n")
        world["actor"]["native_payload"]["transcript_path"] = str(world["transcript"])
        monkeypatch.setenv("CODEX_HOME", str(root))
        monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", "codex:" + NATIVE)
    claim(world, client)
    state = enroll(engine, world, create(engine, world))
    if client == "claude":
        append(world, *pair(world))
        append(world, {"type": "user", "uuid": "retained-pause", "sessionId": NATIVE,
                       "message": {"role": "user", "content": "Pause this task."}})
    else:
        from test_native_observations import completed_item
        append(world, completed_item(thread=NATIVE),
               {"type": "event_msg", "payload": {"type": "turn_aborted", "turn_id": "retained-pause"}})
    state = observe(engine, world, state)
    old = deepcopy(state)
    state = change_seat(engine, world, state, client)
    assert state["owner"]["native_ref"] == old["owner"]["native_ref"]
    assert state["owner"]["session_uuid"] != old["owner"]["session_uuid"]
    assert source(state) == source(old)
    state = reconcile(engine, world, state, reconciliation_spec(source(state), mode="replay"))
    assert source(state)["replay"]["status"] == "pending"
    assert source(state)["qualification"] == source(old)["qualification"]
    assert source(state)["replay"]["fresh"]["qualification"]["session_uuid"] == state["owner"]["session_uuid"]
    return world, old, state, client


def test_same_native_new_seat_replays_original_interval_and_preserves_invalidation(engine, bridge, pending_owner_replay):
    world, old, state, _ = pending_owner_replay
    # Idempotent reconciliation must validate the current replay enrollment too.
    state = reconcile(engine, world, state)
    for _ in range(30):
        if source(state)["replay"]["status"] != "pending":
            break
        state = observe(engine, world, state)
    current = source(state)
    assert current["replay"]["status"] == "complete"
    assert current["cursor"]["enrolled_from"] == source(old)["cursor"]["enrolled_from"]
    # Replay certifies the previously consumed interval. The restart message is
    # new tail and must still pass through ordinary observation afterward.
    assert current["cursor"]["offset"] == source(old)["cursor"]["offset"]
    assert current["history"][-1]["qualification"] == source(old)["qualification"]
    assert current["history"][-1]["cursor"] == source(old)["cursor"]
    assert current["qualification"]["session_uuid"] == state["owner"]["session_uuid"]
    state = observe(engine, world, state)
    assert source(state)["cursor"]["offset"] == world["transcript"].stat().st_size
    assert old["extensions"]["native_observations"]["invalidation_index"].items() <= state["extensions"]["native_observations"]["invalidation_index"].items()
    result = bridge.current_invalidation(engine.inspect_context(state, world["actor"]))
    assert result["status"] == "invalidated", result
    assert result["authority_granted"] is False
    assert current["replay"]["effects_replayed"] is False
    assert engine.load_run(world["project"], state["run_id"]) == state


def test_pending_replay_does_not_authorize_a_later_seat(engine, bridge, pending_owner_replay):
    world, _, state, client = pending_owner_replay
    state = change_seat(engine, world, state, client)
    with pytest.raises(ValueError, match="another root owner"):
        observe(engine, world, state)
    assert engine.load_run(world["project"], state["run_id"]) == state


@pytest.mark.parametrize("fault", ["seat", "root", "client", "path", "inode", "thread"])
def test_pending_replay_requires_exact_current_owner_and_retained_identity(engine, bridge, pending_owner_replay, fault):
    world, old, state, _ = pending_owner_replay
    candidate = deepcopy(source(state))
    fresh = candidate["replay"]["fresh"]
    if fault == "seat":
        fresh["qualification"]["session_uuid"] = old["owner"]["session_uuid"]
    elif fault == "path":
        fresh["binding"]["path"] = str(world["scratch"] / "foreign.jsonl")
    elif fault == "inode":
        fresh["binding"]["inode"] += 1
    else:
        key = {"root": "root_session_id", "client": "client", "thread": "thread_id"}[fault]
        fresh["binding"]["producer"][key] = "foreign"
    def prepare(context, payload):
        # Use a live, owner-issued admission token inside the actual command
        # preparer. inspect_context deliberately cannot export that authority.
        bridge._admitted_source(context, "root", source(state))
        bridge._admitted_source(context, "root", candidate)
        return {}
    engine.register_command("fixture.replay-admission", lambda s, p, c: s, allowed_fields=("extensions",))
    engine.register_preparer("fixture.replay-admission", prepare)
    with pytest.raises(ValueError, match="another root owner|retained source identity"):
        command(engine, world, state, "fixture.replay-admission", {})
    assert engine.load_run(world["project"], state["run_id"]) == state


def test_pending_replay_source_mutation_remains_failed_custody(engine, bridge, pending_owner_replay):
    world, _, state, _ = pending_owner_replay
    original = deepcopy(source(state))
    with world["transcript"].open("a") as stream:
        stream.write("{}\n")
    state = observe(engine, world, state)
    current = source(state)
    assert current["replay"]["status"] == "failed"
    assert "snapshot" in current["replay"]["failure"]["detail"]
    assert current["qualification"] == original["qualification"]
    assert current["cursor"] == original["cursor"]
    assert current["replay"]["fresh"] == original["replay"]["fresh"]
    checked = bridge.current_invalidation(engine.inspect_context(state, world["actor"]))
    assert checked["status"] == "unknown"
    assert checked["authority_granted"] is False


def test_completed_replay_refresh_after_later_seat_keeps_history(engine, bridge, pending_owner_replay):
    world, _, state, client = pending_owner_replay
    for _ in range(30):
        if source(state)["replay"]["status"] != "pending":
            break
        state = observe(engine, world, state)
    assert source(state)["replay"]["status"] == "complete"
    prior = deepcopy(source(state))
    state = change_seat(engine, world, state, client)
    state = reconcile(engine, world, state)
    assert source(state)["replay"]["mode"] == "refresh"
    for _ in range(30):
        if source(state)["replay"]["status"] != "pending":
            break
        state = observe(engine, world, state)
    assert source(state)["replay"]["status"] == "complete"
    assert source(state)["history"] == prior["history"]
    assert source(state)["cursor"]["enrolled_from"] == prior["cursor"]["enrolled_from"]
    assert source(state)["cursor"]["offset"] == world["transcript"].stat().st_size
    assert source(state)["qualification"]["session_uuid"] == state["owner"]["session_uuid"]

"""Cold native Stop consumers; transcript fixtures are synthetic, not live receipts.

These processes import the same entry point as combined Stop without test-suite
sys.path pollution, preloaded PM modules, or inherited native identity hints.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


HERE = Path(__file__).resolve().parent
PM = HERE.parents[1] / "synthesis-project-management/scripts"
NATIVE = "01990000-0000-7000-8000-000000000022"
SURFACES = ("claude-code-cli", "claude-code-desktop", "codex-cli", "codex-desktop", "muse-cli")


def native_fixture(tmp_path, surface):
    family = "claude" if surface.startswith("claude") else surface.split("-")[0]
    roots = {name: tmp_path / name for name in ("claude", "codex", "muse")}
    if family == "claude":
        transcript = roots[family] / "projects/fixture" / f"{NATIVE}.jsonl"
        record = {"type": "user", "sessionId": NATIVE}
    elif family == "codex":
        transcript = roots[family] / "sessions/fixture.jsonl"
        record = {"type": "session_meta", "payload": {"id": NATIVE}}
    else:
        transcript = roots[family] / "2026/09/25" / NATIVE / "session.jsonl"
        record = {"stream": {"kind": "session", "id": NATIVE}}
    transcript.parent.mkdir(parents=True)
    transcript.write_text(json.dumps(record) + "\n")
    payload = {"hook_event_name": "Stop", "session_id": NATIVE,
               "stop_hook_active": False, "cwd": str(tmp_path)}
    if family != "muse":
        payload["transcript_path"] = str(transcript)
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("SYNTHESIS_", "CLAUDE_", "CODEX_", "MUSE_", "PYTHONPATH"))}
    env.update(CLAUDE_CONFIG_DIR=str(roots["claude"]), CODEX_HOME=str(roots["codex"]),
               MUSE_SESSIONS_DIR=str(roots["muse"]),
               SYNTHESIS_COORDINATION_BOARD=str(tmp_path / "absent-board.md"),
               SYNTHESIS_AUTOPILOT_RUNTIME=str(tmp_path / "runtime"), PYTHONDONTWRITEBYTECODE="1")
    return payload, env, transcript


def cold_stop(tmp_path, payload, env, *, combined=True):
    expression = ("native_stop.combined_result(payload, checkpoint=lambda _: {})" if combined else
                  "native_stop._autopilot_result(payload)")
    program = (f"import sys,json; sys.path.insert(0, {str(HERE)!r}); "
               "import native_stop; payload=json.load(sys.stdin); "
               f"print(json.dumps({expression}))")
    done = subprocess.run([sys.executable, "-I", "-c", program], cwd=tmp_path,
                          input=json.dumps(payload), text=True, capture_output=True,
                          env=env, timeout=20)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


@pytest.mark.parametrize("surface", SURFACES)
@pytest.mark.parametrize("repeat", (False, True))
def test_cold_stop_discovers_native_family_without_process_hints(tmp_path, surface, repeat):
    payload, env, _ = native_fixture(tmp_path, surface)
    payload["stop_hook_active"] = repeat
    assert cold_stop(tmp_path, payload, env) == {}
    assert not (tmp_path / "runtime").exists()


@pytest.mark.parametrize("surface", SURFACES)
@pytest.mark.parametrize("hint", ("surface", "environment"))
def test_hints_cannot_certify_missing_native_evidence(tmp_path, surface, hint):
    payload, env, transcript = native_fixture(tmp_path, surface)
    transcript.unlink()
    if hint == "surface":
        payload["synthesis_surface"] = surface
    else:
        prefix = {"claude-code-cli": "cc", "claude-code-desktop": "ccd", "codex-cli": "codex",
                  "codex-desktop": "codex", "muse-cli": "muse"}[surface]
        env["SYNTHESIS_CLIENT_SESSION_REF"] = prefix + ":" + NATIVE
    for repeat in (False, True, False):
        payload["stop_hook_active"] = repeat
        result = cold_stop(tmp_path, payload, env)
        assert result.get("continue") is False
        assert result.get("decision") != "block"
        assert "UNRESOLVED" in result["systemMessage"]
    assert not (tmp_path / "runtime").exists()


@pytest.mark.parametrize("surface", SURFACES)
@pytest.mark.parametrize("status", ("closed", "running"))
def test_cold_stop_distinguishes_closed_and_unfinished_legacy_without_mutation(tmp_path, surface, status):
    payload, env, _ = native_fixture(tmp_path, surface)
    payload["synthesis_surface"] = surface
    root = tmp_path / "runtime"
    legacy = root / "engagements"
    legacy.mkdir(parents=True)
    prefix = "cc" if surface.startswith("claude") else surface.split("-")[0]
    owned = legacy / "owned.json"
    owned.write_text(json.dumps({"client_session_ref": prefix + ":" + NATIVE, "status": status,
                                 "pending": ["retained-obligation"]}))
    foreign = legacy / "foreign.json"
    foreign.write_text('{"client_session_ref":"cc:01990000-0000-7000-8000-000000000099", broken')
    # Migration preparation is an explicit separate operation; Stop cannot
    # silently invent the index or mutate the retained legacy record.
    program = (f"import sys,json; sys.path.insert(0, {str(HERE)!r}); import autopilot; "
               "payload=json.load(sys.stdin); runtime=autopilot.engine(); "
               "runtime.index_legacy(autopilot.actor_from_hook(payload), "
               "autopilot.default_runtime_root()/'engagements', runtime_root=autopilot.default_runtime_root())")
    setup = subprocess.run([sys.executable, "-I", "-c", program], input=json.dumps(payload),
                           cwd=tmp_path, env=env, text=True, capture_output=True, timeout=20)
    assert setup.returncode == 0, setup.stderr
    before = {str(path): path.read_bytes() for path in root.rglob("*") if path.is_file()}
    for repeat in (False, True, False):
        payload["stop_hook_active"] = repeat
        result = cold_stop(tmp_path, payload, env)
        if status == "closed":
            assert result == {}
        else:
            assert result["continue"] is False
            assert result.get("decision") != "block"
            assert "legacy engagement" in result["systemMessage"]
            assert "cannot identify" not in result["systemMessage"]
        assert {str(path): path.read_bytes() for path in root.rglob("*") if path.is_file()} == before


@pytest.mark.parametrize("surface", SURFACES)
def test_cold_stop_preserves_owned_run_and_revoked_mutation_authority(tmp_path, monkeypatch, surface):
    sys.path.insert(0, str(PM))
    sys.path.insert(0, str(HERE))
    from test_run_admission import world as world_fixture
    from test_run_state import contract
    import autopilot
    (tmp_path / "pm").mkdir()
    world = world_fixture.__wrapped__(tmp_path / "pm", monkeypatch)
    payload, env, _ = native_fixture(tmp_path / "native", surface)
    payload.update(cwd=str(world["repo"]), synthesis_surface=surface)
    env["SYNTHESIS_COORDINATION_BOARD"] = str(world["board"])
    env["SYNTHESIS_AUTOPILOT_RUNTIME"] = str(world["runtime"])
    for name in ("CLAUDE_CONFIG_DIR", "CODEX_HOME", "MUSE_SESSIONS_DIR"):
        monkeypatch.setenv(name, env[name])
    prefix = "cc" if surface.startswith("claude") else surface.split("-")[0]
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", prefix + ":" + NATIVE)
    board = world["board"].read_text().replace("| claude |", "| " + ("claude" if prefix == "cc" else prefix) + " |")
    board = board.replace("cc:" + NATIVE, prefix + ":" + NATIVE)
    world["board"].write_text(board)
    actor = {"board": str(world["board"]), "native_payload": payload}
    runtime = autopilot.engine()
    state = runtime.create_run(world["project"], project_id="alpha", plan=world["plan"],
        contract=contract(), profile={"schema": 1, "items": [{"id": "fixture", "criterion_ids": ["accept"]}]},
        actor=actor, command_id="identity-fixture", runtime_root=world["runtime"])
    project_before = {str(path): path.read_bytes() for path in world["project"].rglob("*") if path.is_file()}
    runtime_before = {str(path): path.read_bytes() for path in world["runtime"].rglob("*") if path.is_file()}
    for repeat in (False, True, False):
        payload["stop_hook_active"] = repeat
        result = cold_stop(tmp_path, payload, env)
        assert result["continue"] is False
        assert result.get("decision") != "block"
        assert state["run_id"] in result["systemMessage"]
        assert "cannot identify" not in result["systemMessage"]
        assert {str(path): path.read_bytes() for path in world["project"].rglob("*") if path.is_file()} == project_before
        assert {str(path): path.read_bytes() for path in world["runtime"].rglob("*") if path.is_file()} == runtime_before
    world["board"].write_text(board.replace("| active |", "| released |"))
    with pytest.raises(ValueError):
        runtime.apply_command(world["project"], state["run_id"], command="progress",
            payload={"summary": "Must remain denied"}, actor=actor,
            expected_revision=state["revision"], command_id="revoked-mutation", runtime_root=world["runtime"])
    assert runtime.load_run(world["project"], state["run_id"]) == state
    world["board"].write_text(board)
    terminal = runtime.apply_command(world["project"], state["run_id"], command="close",
        payload={"status": "cancelled", "reason": "Fixture cancellation"}, actor=actor,
        expected_revision=state["revision"], command_id="fixture-close", runtime_root=world["runtime"])
    world["board"].write_text(board.replace("| active |", "| released |"))
    assert terminal["status"] == "cancelled"
    for repeat in (False, True, False):
        payload["stop_hook_active"] = repeat
        assert cold_stop(tmp_path, payload, env) == {}
        assert runtime.load_run(world["project"], state["run_id"]) == terminal


@pytest.mark.parametrize("surface", ("cursor-ide", "cursor-cli", "cursor-cloud", "copilot-cli", "copilot-vscode", "copilot-cloud"))
def test_unqualified_adapter_contract_cannot_claim_native_authority(tmp_path, surface):
    payload, env, _ = native_fixture(tmp_path, "claude-code-cli")
    payload["synthesis_surface"] = surface
    payload.update(conversation_id=NATIVE, generation_id="fixture-turn", status="completed", loop_count=0)
    for repeat in (False, True, False):
        payload["stop_hook_active"] = repeat
        payload["loop_count"] = int(repeat)
        result = cold_stop(tmp_path, payload, env, combined=False)
        # These adapter contracts have no global terminal override. Ending
        # Synthesis feedback grants no mutation or completion authority.
        assert result == ({} if surface.startswith("cursor") else {"decision": "allow"})
    assert not (tmp_path / "runtime").exists()


@pytest.mark.parametrize("surface", ("opencode-cli", "opencode-sdk-v2", "hermes", "unknown", ["codex-cli"], {"name": "codex-cli"}))
def test_surface_without_native_stop_emitter_remains_terminal(tmp_path, surface):
    payload, env, _ = native_fixture(tmp_path, "claude-code-cli")
    payload["synthesis_surface"] = surface
    for repeat in (False, True):
        payload["stop_hook_active"] = repeat
        result = cold_stop(tmp_path, payload, env)
        assert result["continue"] is False
        assert "UNRESOLVED" in result["systemMessage"]
        assert result.get("decision") != "block"
    assert not (tmp_path / "runtime").exists()


@pytest.mark.parametrize("hint", ("codex-desktop", "muse-cli"))
def test_surface_cannot_relabel_an_authenticated_family(tmp_path, hint):
    payload, env, _ = native_fixture(tmp_path, "claude-code-desktop")
    payload["synthesis_surface"] = hint
    result = cold_stop(tmp_path, payload, env)
    assert result["continue"] is False
    assert "selected Stop surface" in result["systemMessage"]
    assert not (tmp_path / "runtime").exists()

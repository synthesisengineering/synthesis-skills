"""Actual message gate must bind schema-aware active native-ref columns."""

from pathlib import Path
import sys
import pytest

PUBLIC = Path(__file__).resolve().parents[3]
for s in ["synthesis-project-management", "synthesis-message-guard"]:
    sys.path.insert(0, str(PUBLIC / "skills" / s / "scripts"))
import coordination as c  # noqa: E402 - exact source owner bound above
import message_guard as g  # noqa: E402 - exact source owner bound above


def board_and_config(tmp_path, status="active", spoof=False):
    identity = c.new_identity([])
    row = c.Session(
        session_uuid=identity.session_uuid,
        compact_id=identity.compact_id,
        speakable_id=identity.speakable_id,
        legacy_id="",
        agent="synthetic",
        machine="machine-one",
        project="synthetic",
        started="t",
        heartbeat="t",
        mode="interactive",
        workspaces=[],
        goal="ccd:destination" if spoof else "synthetic",
        claims=[],
        context_role="none",
        status=status,
        client_ref="ccd:other" if spoof else "ccd:destination",
        person="p-one",
        standing_role="role-one",
    )
    b = tmp_path / "board.md"
    b.write_text(c.replace_table(c.template(), [row]))
    return b, {
        "peer_send_resolution": {
            "tool_pattern": r"^synthetic_peer_send$",
            "target_field": "session_id",
            "board": str(b),
        }
    }


def test_active_schema6_native_ref_positive(tmp_path):
    _, cfg = board_and_config(tmp_path)
    assert g.peer_send_resolution_failures(
        "synthetic_peer_send", {"session_id": "destination"}, cfg
    ) == (True, [])


@pytest.mark.parametrize("status", ["released", "complete", "completed", "closed"])
def test_inactive_schema6_peer_ref_refuses(tmp_path, status):
    _, cfg = board_and_config(tmp_path, status)
    handled, fails = g.peer_send_resolution_failures(
        "synthetic_peer_send", {"session_id": "destination"}, cfg
    )
    assert handled and fails


def test_ref_in_goal_cannot_impersonate_native_ref(tmp_path):
    _, cfg = board_and_config(tmp_path, spoof=True)
    handled, fails = g.peer_send_resolution_failures(
        "synthetic_peer_send", {"session_id": "destination"}, cfg
    )
    assert handled and fails


def test_real_gate_released_schema6_is_blocked(tmp_path, monkeypatch):
    _, cfg = board_and_config(tmp_path, "released")
    monkeypatch.setattr(g, "load_config", lambda: (cfg, [], [], [], []))
    monkeypatch.setattr(g, "state_dir", lambda: str(tmp_path / "state"))
    monkeypatch.setattr(g, "log_path", lambda: str(tmp_path / "state/events.jsonl"))
    with pytest.raises(SystemExit) as e:
        g.run_gate(
            {
                "tool_name": "synthetic_peer_send",
                "tool_input": {"session_id": "destination"},
            }
        )
    assert e.value.code == 2
    assert not (tmp_path / "state/events.jsonl").exists()


def test_parked_peer_preserves_canonical_nonterminal_semantics(tmp_path):
    _, cfg = board_and_config(tmp_path, "parked")
    assert g.peer_send_resolution_failures(
        "synthetic_peer_send", {"session_id": "destination"}, cfg
    ) == (True, [])


@pytest.mark.parametrize(
    "mutation",
    [
        "future",
        "missing-schema",
        "wrong-width",
        "duplicate-ref",
        "duplicate-section",
        "non-native-column",
    ],
)
def test_unknown_ambiguous_or_malformed_board_never_authorizes(tmp_path, mutation):
    b, cfg = board_and_config(tmp_path)
    text = b.read_text()
    if mutation == "future":
        text = text.replace("Schema: v6", "Schema: v999")
    elif mutation == "missing-schema":
        text = text.replace("Schema: v6", "")
    elif mutation == "wrong-width":
        text = text.replace("| role-one |", "| role-one | extra |")
    elif mutation == "duplicate-ref":
        row = next(line for line in text.splitlines() if "ccd:destination" in line)
        text = text.replace(row, row + "\n" + row)
    elif mutation == "duplicate-section":
        text += "\n## Active sessions\n"
    else:
        text = text.replace("client session ref", "target label")
    b.write_text(text)
    assert g.peer_send_resolution_failures(
        "synthetic_peer_send", {"session_id": "destination"}, cfg
    )[1]


def test_installed_message_payload_closure_exact_and_missing_dependency_refuses(
    tmp_path,
):
    import json
    import subprocess
    import shutil

    sys.path.insert(0, str(PUBLIC / "skills/synthesis-onboarding/scripts"))
    import runtime_payload

    home = tmp_path / "home"
    dest = home / ".synthesis/message-guard"
    specs = runtime_payload._specs(home, home / "state", {"message-guard"})
    assert {p.name for _, _, p, _ in specs} == {
        "message_guard.py",
        "board_grammar.py",
        "coordination_schema.py",
        "claim_scope.py",
        "native_git.py",
    }
    for _, source, target, mode in specs:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PUBLIC / source, target)
        target.chmod(mode)
        assert target.read_bytes() == (PUBLIC / source).read_bytes()
    board, cfg = board_and_config(tmp_path, "parked")
    program = (
        "import importlib.util,json; s=importlib.util.spec_from_file_location('guard',%r); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); print(json.dumps(m.peer_send_resolution_failures('synthetic_peer_send',{'session_id':'destination'},%r)))"
        % (str(dest / "message_guard.py"), cfg)
    )

    def run():
        r = subprocess.run(
            [sys.executable, "-I", "-B", "-c", program],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert r.returncode == 0, r.stderr
        return json.loads(r.stdout)

    assert run() == [True, []]
    (dest / "board_grammar.py").rename(dest / "retained-board-grammar.py")
    assert run()[0] is True and run()[1]



def _rows_with_shared_ref(statuses):
    rows = []
    taken = []
    for index, status in enumerate(statuses):
        identity = c.new_identity(taken)
        taken.append(identity)
        rows.append(c.Session(
            session_uuid=identity.session_uuid, compact_id=identity.compact_id,
            speakable_id=identity.speakable_id, legacy_id="", agent="synthetic",
            machine="machine-one", project="synthetic", started="t", heartbeat="t",
            mode="interactive", workspaces=[], goal="synthetic-%d" % index, claims=[],
            context_role="none", status=status, client_ref="ccd:destination",
            person="p-one", standing_role="role-one"))
    return rows


@pytest.mark.parametrize("statuses, admitted", [
    (["released", "released", "released", "active"], True),
    (["released", "active", "released"], True),
    (["active", "active", "released"], False),
    (["released", "released"], False),
])
def test_released_rows_sharing_a_desktop_ref_are_history_not_ambiguity(tmp_path, statuses, admitted):
    # Regression 2026-10-05: a long-lived desktop session carried eight
    # released rows and one active row under one client ref, and the guard
    # refused its correctly resolved address as ambiguous.
    b = tmp_path / "board.md"
    b.write_text(c.replace_table(c.template(), _rows_with_shared_ref(statuses)))
    cfg = {"peer_send_resolution": {"tool_pattern": r"^synthetic_peer_send$",
                                    "target_field": "session_id", "board": str(b)}}
    handled, fails = g.peer_send_resolution_failures(
        "synthetic_peer_send", {"session_id": "destination"}, cfg)
    assert handled
    assert (fails == []) is admitted

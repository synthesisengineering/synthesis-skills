"""R1: continuity, including after compaction."""

import json
import os
import subprocess
import sys
from pathlib import Path

from synthesis import board, project

ROOT = Path(__file__).resolve().parents[1]


def _knowledge(tmp_path, write_config):
    root = tmp_path / "ai-knowledge-test"
    proj = root / "projects" / "alpha"
    proj.mkdir(parents=True)
    (proj / "PRIME-DIRECTIVE.md").write_text("# Prime directive\nBuild v5; do not repair v4.\n", encoding="utf-8")
    (proj / "CONTEXT.md").write_text(
        "# Alpha\n\n<!-- synthesis-current-state:start -->\n**Phase:** M2\n**Next:** write the guards\n"
        "<!-- synthesis-current-state:end -->\n\nOlder notes.\n", encoding="utf-8")
    write_config({"knowledge_roots": [str(root)]})
    return proj


def _hook(event, payload, env=None):
    return subprocess.run([sys.executable, "-m", "synthesis.hook", event], input=json.dumps(payload),
                          capture_output=True, text=True, cwd=ROOT, env={**os.environ, **(env or {})})


def test_compaction_reinjects_the_directive_and_current_state(tmp_path, write_config):
    _knowledge(tmp_path, write_config)
    board.touch("S1", project="alpha")
    out = _hook("session-start", {"session_id": "S1", "source": "compact", "cwd": str(tmp_path)})
    context = json.loads(out.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "do not repair v4" in context and "write the guards" in context
    assert "Older notes" not in context


def test_compaction_brings_back_this_sessions_own_project_never_another_sessions(tmp_path, write_config):
    root = _knowledge(tmp_path, write_config).parent.parent
    other = root / "projects" / "beta"
    other.mkdir()
    (other / "PRIME-DIRECTIVE.md").write_text("# Beta directive\nNever touch alpha.\n", encoding="utf-8")
    board.touch("S1", project="alpha")
    board.touch("S2", project="beta")  # the most recent writer; there is no global pointer to follow
    context = json.loads(_hook("session-start", {"session_id": "S1", "source": "compact"}).stdout)
    text = context["hookSpecificOutput"]["additionalContext"]
    assert "do not repair v4" in text and "Never touch alpha" not in text


def test_session_start_registers_the_session_and_reports_unread_messages(tmp_path, write_config):
    _knowledge(tmp_path, write_config)
    board.touch("S2")  # messages reach only sessions on the board (R2.3)
    board.message("S2", "S1", "please review")
    out = _hook("session-start", {"session_id": "S2", "source": "startup", "cwd": str(tmp_path)})
    assert "1 unread" in json.loads(out.stdout)["hookSpecificOutput"]["additionalContext"]
    assert board.load("S2").cwd == str(tmp_path)


ALL = ["session_start", "user_prompt_submit", "pre_tool_use", "stop"]


def _waits(ago=3600.0, version=None, **waiting):
    """The note as a run of the doctor `ago` seconds back would have left it: `codex=[...]`, `muse=[...]` are the
    hook events that waited in each."""
    import time
    from synthesis import __version__, paths
    names = {"codex": "codex hook trust", "muse": "muse hook approval"}
    note = paths.state() / "harness-approvals.json"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text(json.dumps({"seen": {names[k]: {"at": time.time() - ago, "version": version or __version__, "waiting": v}
                                         for k, v in waiting.items()}}), encoding="utf-8")
    return note


def _waiting(note, name):
    return json.loads(note.read_text(encoding="utf-8"))["seen"][name]["waiting"]


def _started(session, **more):
    out = _hook("session-start", {"session_id": session, "cwd": "/tmp", **more})
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)["hookSpecificOutput"]["additionalContext"]


def _in_codex(event, tmp_path, **more):
    """One hook event as Codex runs it: a hook knows Codex by its rollout file."""
    session = "0199aaaa-bbbb-7ccc-8ddd-eeeeffff0000"
    rollout = tmp_path / f"rollout-2026-11-13T09-00-00-{session}.jsonl"
    rollout.write_text("", encoding="utf-8")
    out = _hook(event, {"session_id": session, "cwd": "/tmp", "transcript_path": str(rollout), **more})
    assert out.returncode == 0, out.stderr
    return out


def test_session_start_says_which_harness_has_hooks_not_seen_to_run(tmp_path, write_config):
    """2026-11-13: six releases in a day, and after each one Codex ran none of the plugin's hooks until the person
    approved them again. The doctor's line said so to whoever read the doctor."""
    write_config({})
    _waits(codex=ALL, muse=ALL)
    context = _started("S-claude")
    assert ("Codex: its session-start, user-prompt-submit, pre-tool-use and stop hooks waited for the principal's approval "
            "(in /hooks) when the doctor looked") in context and "have not been seen to run since" in context
    assert "Muse: its" in context and "`muse plugins approve synthesis-skills`" in context
    assert context.count("Nothing guards a send or a deploy made from there") == 2
    _waits(codex=["stop"], muse=[])
    context = _started("S-claude-2")                                             # a hook that is no guard: said, with no alarm
    assert "Codex: its stop hook waited" in context and "has not been seen to run since" in context
    assert "Nothing guards" not in context and "Muse: its" not in context
    for ago, waiting in ((60, {"codex": [], "muse": []}), (2 * 86400, {"codex": ALL})):   # nothing waits; or two days old
        _waits(ago, **waiting)
        assert "waited for the principal's approval" not in _started(f"S-{ago}")
    _waits(codex=ALL).write_text("{not json", encoding="utf-8")
    assert "waited for the principal's approval" not in _started("S-garbage")    # and the session still starts


def test_session_start_says_when_no_look_was_taken_since_synthesis_changed(tmp_path, write_config):
    """Review of 5.14.0, finding 2: a release installed with no run of the doctor (a harness that pulls it, a second
    Mac) left a note from that morning saying none wait, while Codex asks again after every release."""
    write_config({})
    _waits(version="5.0.0", codex=[], muse=ALL)
    context = _started("S-claude")
    assert "Whether Codex and Muse run synthesis's hooks has not been checked since synthesis changed" in context
    assert "`synthesis doctor`" in context and "waited for the principal's approval" not in context
    _waits(version="5.0.0", codex=[])
    assert "Whether Codex runs synthesis's hooks has not been checked since" in _started("S-claude-2")


def test_a_hook_that_runs_in_a_harness_strikes_its_own_event_and_no_other(tmp_path, write_config):
    """Review of 5.14.0, finding 1: a start hook that ran was taken for proof that all of a harness's hooks run, so
    with the guard's own hook untrusted the note said nothing waits. Each hook that runs shows itself approved."""
    write_config({})
    note = _waits(codex=ALL, muse=ALL)
    _in_codex("session-start", tmp_path)
    assert _waiting(note, "codex hook trust") == ["user_prompt_submit", "pre_tool_use", "stop"]
    assert _waiting(note, "muse hook approval") == ALL
    context = _started("S-claude")
    assert "Codex: its user-prompt-submit, pre-tool-use and stop hooks waited" in context and context.count("Nothing guards") == 2
    _in_codex("pre-tool-use", tmp_path, tool_name="Bash", tool_input={"command": "true"})
    assert _waiting(note, "codex hook trust") == ["user_prompt_submit", "stop"]
    assert _started("S-claude-2").count("Nothing guards") == 1                   # Muse's alone: Codex's guard has run
    _in_codex("user-prompt-submit", tmp_path, prompt="hello")
    _in_codex("stop", tmp_path)
    assert _waiting(note, "codex hook trust") == [] and "Codex: its" not in _started("S-claude-3")
    assert _waiting(note, "muse hook approval") == ALL


def test_a_hook_that_runs_in_muse_strikes_muses_entry(tmp_path, write_config):
    write_config({})
    note = _waits(codex=ALL, muse=ALL)
    out = _hook("pre-tool-use", {"session_id": "M1", "cwd": "/tmp", "tool_name": "bash", "tool_input": {"command": "true"}},
                env={"MUSE_SESSION_ID": "M1"})
    assert out.returncode == 0, out.stderr
    assert _waiting(note, "muse hook approval") == ["session_start", "user_prompt_submit", "stop"]
    assert _waiting(note, "codex hook trust") == ALL


def test_a_hook_seen_under_another_release_is_left_for_the_doctor(tmp_path, write_config):
    """What waited under another release says nothing of this one's hooks: a hook that runs strikes nothing there."""
    write_config({})
    note = _waits(version="5.0.0", codex=ALL)
    _in_codex("pre-tool-use", tmp_path, tool_name="Bash", tool_input={"command": "true"})
    assert _waiting(note, "codex hook trust") == ALL


def test_a_note_that_cannot_be_written_costs_no_hook_its_answer(tmp_path, write_config, monkeypatch):
    """Review of 5.14.0, finding 8: the strike and the note shared one `try`, so a state folder that could not be
    written hid the other harness's line too."""
    from synthesis import hook, paths
    write_config({})
    _waits(codex=ALL, muse=ALL)

    def refused(*args, **kwargs):
        raise PermissionError("read-only")
    monkeypatch.setattr(paths, "write_json", refused)
    hook._ran("codex", "session_start")                                          # raises nothing
    said = hook._unguarded_note()
    assert "Muse: its" in said and "Codex: its" in said


def test_brief_is_bounded_and_check_flags_a_long_context(tmp_path, write_config):
    proj = _knowledge(tmp_path, write_config)
    (proj / "CONTEXT.md").write_text("line\n" * 400, encoding="utf-8")
    assert len(project.brief(proj)) <= project.BRIEF_LIMIT
    assert "over 150 lines" in project.check(proj)[0]


def test_handoff_commits_and_pushes_only_this_sessions_claims(tmp_path):
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    repo = tmp_path / "kb"
    subprocess.run(["git", "clone", "-q", str(remote), str(repo)], check=True, capture_output=True)
    for args in (["config", "user.email", "t@example.com"], ["config", "user.name", "t"]):
        subprocess.run(["git", "-C", str(repo), *args], check=True)
    (repo / "mine").mkdir()
    (repo / "theirs").mkdir()
    (repo / "mine" / "a.md").write_text("mine\n")
    (repo / "theirs" / "b.md").write_text("theirs\n")
    board.claim("S1", [f"{repo}/mine/**"])
    report = project.handoff("S1")
    assert "committed 1 file(s)" in report[0] and "and pushed to origin/" in report[0] and report[-1].startswith("READY")
    committed = subprocess.run(["git", "-C", str(remote), "log", "--name-only", "--format="],
                               capture_output=True, text=True).stdout.split()
    assert committed == ["mine/a.md"]


def test_prompt_delivers_board_messages_and_grants_typed_approvals(tmp_path, write_config, principal):
    from synthesis import guards
    _knowledge(tmp_path, write_config)
    board.touch("S3", project="alpha", briefed="alpha")
    board.message("project:alpha", "S9", "please rebase on main")
    reason = guards.check("mcp__slack__slack_send_message", {"message": "hi"}, {})
    code = principal(reason, grant=False)  # the harness records the principal's prompt; the hook grants it
    out = _hook("user-prompt-submit", {"session_id": "S3", "prompt": f"approve {code}"})
    context = json.loads(out.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "please rebase on main" in context and "Approved by the principal" in context
    assert guards.check("mcp__slack__slack_send_message", {"message": "hi"}, {}) is None


def test_session_start_states_the_local_time_first(tmp_path, write_config):
    out = _hook("session-start", {"session_id": "s-time", "cwd": str(tmp_path)})
    context = json.loads(out.stdout)["hookSpecificOutput"]["additionalContext"]
    assert context.startswith("Local time: ")


def test_after_synthesis_use_the_next_prompt_brings_the_brief_once(tmp_path, write_config):
    """Muse runs SessionStart only when a session is created, so a session that chose its project with
    `synthesis use` never got the brief (M5 defect 3). The next prompt brings it, once, in every harness."""
    from synthesis import cli
    _knowledge(tmp_path, write_config)
    _hook("session-start", {"session_id": "S7", "cwd": str(tmp_path)})  # a new session has no project yet
    assert cli.main(["--session", "S7", "use", "alpha"]) == 0
    out = _hook("user-prompt-submit", {"session_id": "S7", "prompt": "next"})
    context = json.loads(out.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "do not repair v4" in context and "write the guards" in context
    assert _hook("user-prompt-submit", {"session_id": "S7", "prompt": "again"}).stdout.strip() == ""


def test_a_brief_given_at_session_start_is_not_repeated_at_the_next_prompt(tmp_path, write_config):
    _knowledge(tmp_path, write_config)
    board.touch("S8", project="alpha")
    assert "do not repair v4" in _hook("session-start", {"session_id": "S8", "cwd": str(tmp_path)}).stdout
    assert _hook("user-prompt-submit", {"session_id": "S8", "prompt": "next"}).stdout.strip() == ""

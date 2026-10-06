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


def _hook(event, payload):
    return subprocess.run([sys.executable, "-m", "synthesis.hook", event], input=json.dumps(payload),
                          capture_output=True, text=True, cwd=ROOT, env=dict(os.environ))


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


def test_prompt_delivers_board_messages_and_grants_typed_approvals(tmp_path, write_config):
    from synthesis import guards
    _knowledge(tmp_path, write_config)
    board.touch("S3", project="alpha")
    board.message("project:alpha", "S9", "please rebase on main")
    reason = guards.check("mcp__slack__slack_send_message", {"message": "hi"}, {})
    code = reason.split("approve ")[1][:6]
    out = _hook("user-prompt-submit", {"session_id": "S3", "prompt": f"approve {code}"})
    context = json.loads(out.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "please rebase on main" in context and "Approved by the principal" in context
    assert guards.check("mcp__slack__slack_send_message", {"message": "hi"}, {}) is None

"""The on-demand provenance scan: a timestamp or quote a record gained must appear in a source.

Anonymized shapes from the incident: a real message's timestamp with its last digits changed,
written into a project record and a daily plan, appearing in no tool result.
"""

import importlib.util
import json
import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "provenance_scan.py"
spec = importlib.util.spec_from_file_location("provenance_scan", SCRIPT)
scan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan)

OLD, REAL, MADE_UP = "1700000000.000100", "1700000000.000200", "1700000000.000201"
SOURCED = "ship the fix on Tuesday morning please"
INVENTED = "we never agreed to cancel the launch event"


@pytest.fixture(autouse=True)
def plain_git(tmp_path, monkeypatch):
    """No machine-wide hooks or identity reach these test repositories."""
    config = tmp_path / "gitconfig"
    config.write_text("[user]\n\temail = test@example.com\n\tname = test\n", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def _git(repo, *args, env=None):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env={**os.environ, **(env or {})})


@pytest.fixture
def kb(tmp_path):
    repo = tmp_path / "kb"
    context = repo / "projects" / "demo" / "CONTEXT.md"
    context.parent.mkdir(parents=True)
    context.write_text(f"# Demo\n\nEarlier thread {OLD}.\n", encoding="utf-8")
    _git(tmp_path, "init", "-q", str(repo))
    _git(repo, "add", "-A")
    old_day = {"GIT_AUTHOR_DATE": "2026-01-01T10:00:00", "GIT_COMMITTER_DATE": "2026-01-01T10:00:00"}
    _git(repo, "commit", "-qm", "start", env=old_day)
    context.write_text(context.read_text() + f"Reply {REAL}. Dana wrote: \"{SOURCED}\".\nAlso {MADE_UP}.\n"
                       f"Dana said: \"{INVENTED}\".\n", encoding="utf-8")
    plan = repo / "daily-plans" / "2026-01-02.md"
    plan.parent.mkdir()
    plan.write_text("- [ ] answer https://example.slack.com/archives/C1/p1700000000000400\n", encoding="utf-8")
    (repo / "notes.md").write_text(f"Not a record: {MADE_UP}\n", encoding="utf-8")
    return repo


@pytest.fixture
def logs(tmp_path):
    folder = tmp_path / "logs"
    folder.mkdir()
    events = [
        {"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "tool_use", "id": "w1", "name": "Write", "input": {"file_path": "x/CONTEXT.md", "content": MADE_UP}},
            {"type": "text", "text": f"I recorded {MADE_UP} and {INVENTED}."}]}},
        {"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "w1", "content": f"File written: {MADE_UP}"}]}},
        {"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "r1", "content": f"ts {REAL} Dana: {SOURCED.capitalize()}!"}]}},
        {"type": "response_item", "payload": {"type": "function_call_output", "call_id": "c1", "output": "no stamps here"}},
    ]
    (folder / "session.jsonl").write_text("\n".join(json.dumps(e) for e in events) + "\nnot json\n", encoding="utf-8")
    return folder


def test_a_made_up_timestamp_or_quote_is_named_and_a_sourced_one_is_not(kb, logs, capsys):
    assert scan.main(["--since", "2026-01-02", "--sources", str(logs), str(kb)]) == 1
    out = capsys.readouterr().out
    assert MADE_UP in out and "1700000000.000400" in out and INVENTED[:30] in out
    assert REAL not in out and SOURCED[:30] not in out and OLD not in out and "notes.md" not in out
    assert "read 2 records and 1 session logs" in out


def test_a_record_with_everything_sourced_passes(kb, logs, capsys):
    (kb / "daily-plans" / "2026-01-02.md").unlink()
    context = kb / "projects" / "demo" / "CONTEXT.md"
    context.write_text(context.read_text().replace(MADE_UP, REAL).replace(f'Dana said: "{INVENTED}".\n', ""))
    assert scan.main(["--since", "2026-01-02", "--sources", str(logs), str(kb)]) == 0


def test_with_no_session_logs_it_cannot_run(kb, tmp_path):
    assert scan.main(["--since", "2026-01-02", "--sources", str(tmp_path / "absent"), str(kb)]) == 2


def test_a_single_record_file_can_be_named(kb, logs, capsys):
    plan = kb / "daily-plans" / "2026-01-02.md"
    assert scan.main(["--since", "2026-01-02", "--sources", str(logs), str(plan)]) == 1
    out = capsys.readouterr().out
    assert "1700000000.000400" in out and "read 1 records" in out

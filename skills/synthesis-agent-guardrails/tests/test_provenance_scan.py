"""The on-demand provenance scan: a timestamp or quote a record gained must appear in a source.

Anonymized shapes from the incident: a real message's timestamp with its last digits changed,
written into a project record and a daily plan, appearing in no tool result.
"""

import importlib.util
import json
import os
import subprocess
import sys
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


# 2026-11-11: a workspace kept its daily plan in ritual-workers/, so neither its plan nor its close was ever read
# (36 records read, 0 unsourced, the plan unchecked).

def test_a_plan_kept_in_ritual_workers_or_drafts_is_a_record(kb, logs, capsys):
    for folder in ("ritual-workers", "drafts"):
        plan = kb / folder / "2026-01-02-plan.md"
        plan.parent.mkdir()
        plan.write_text(f"- [ ] reply to the thread at {MADE_UP}\n", encoding="utf-8")
    assert scan.main(["--since", "2026-01-02", "--sources", str(logs), str(kb)]) == 1
    out = capsys.readouterr().out
    assert "ritual-workers/2026-01-02-plan.md" in out and "drafts/2026-01-02-plan.md" in out
    assert "read 4 records" in out


def test_a_folder_the_workspace_declares_is_read_whatever_its_name(kb, logs, capsys):
    plan = kb / "plans" / "week" / "2026-01-02.md"
    plan.parent.mkdir(parents=True)
    plan.write_text(f"- [ ] reply to the thread at {MADE_UP}\n", encoding="utf-8")
    assert scan.main(["--since", "2026-01-02", "--sources", str(logs), str(kb)]) == 1
    assert "plans/week/2026-01-02.md" not in capsys.readouterr().out          # not a record by its place alone
    assert scan.main(["--since", "2026-01-02", "--sources", str(logs), "--records", str(kb / "plans"), str(kb)]) == 1
    out = capsys.readouterr().out
    assert "plans/week/2026-01-02.md" in out and "read 3 records" in out
    assert scan.main(["--since", "2026-01-02", "--sources", str(logs), "--records", str(kb / "absent"), str(kb)]) == 2


def test_a_file_named_outright_is_a_record_wherever_it_lies(kb, logs, capsys):
    assert scan.main(["--since", "2026-01-02", "--sources", str(logs), str(kb / "notes.md")]) == 1
    out = capsys.readouterr().out
    assert "notes.md" in out and "read 1 records" in out


# Review round 1 of 5.8.0 (2026-11-12): a YAML plan named outright was scanned as "read 0 records" with exit 0, and a
# folder given with --records still left files out by their suffix and by their folder's name.

def test_a_file_named_outright_is_a_record_whatever_its_suffix(kb, logs, capsys):
    for name in ("2026-01-02.yaml", "today"):
        plan = kb / "plans" / name
        plan.parent.mkdir(exist_ok=True)
        plan.write_text(f"items:\n  - reply to the thread at {MADE_UP}\n", encoding="utf-8")
        assert scan.main(["--since", "2026-01-02", "--sources", str(logs), str(plan)]) == 1
        out = capsys.readouterr().out
        assert f"plans/{name}: timestamp {MADE_UP}" in out and "read 1 records" in out


def test_every_file_under_a_declared_folder_is_read_at_any_depth_hidden_folders_too(kb, logs, capsys):
    plans = kb / "plans"
    kept = ("week/2026-01-02.yaml", ".archive/old/2026-01-01.md", "notes", "node_modules/pkg/readme.md", ".hidden")
    for rel in kept + (".git/COMMIT_EDITMSG", "week/.git/ORIG_HEAD"):
        file = plans / rel
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(f"- [ ] reply to the thread at {MADE_UP}\n", encoding="utf-8")
    assert scan.main(["--since", "2026-01-02", "--sources", str(logs), "--records", str(plans), str(kb)]) == 1
    out = capsys.readouterr().out
    assert [rel for rel in kept if f"plans/{rel}: timestamp {MADE_UP}" not in out] == []
    assert ".git/" not in out and "read 7 records" in out                     # the five, the project's context and the daily plan
    assert scan.main(["--since", "2026-01-02", "--sources", str(logs), str(kb)]) == 1
    assert "kb/plans/" not in capsys.readouterr().out                         # without --records, a record's place still decides


def test_a_record_that_is_not_text_is_named_unreadable_and_not_counted_as_read(tmp_path, logs, capsys):
    plans = tmp_path / "plans"
    plans.mkdir()
    (plans / "scan.png").write_bytes(b"\x89PNG\r\n\x1a\n" + bytes(range(128, 256)))
    (plans / "2026-01-02.md").write_text("- [ ] nothing from a chat here\n", encoding="utf-8")
    assert scan.main(["--since", "2026-01-02", "--sources", str(logs), "--records", str(plans), str(plans)]) == 1
    out = capsys.readouterr().out
    assert "scan.png: unreadable" in out and "0 unsourced, 1 unreadable; read 1 records" in out
    assert scan.main(["--since", "2026-01-02", "--sources", str(logs), str(plans / "scan.png")]) == 1     # named outright
    assert "scan.png: unreadable" in capsys.readouterr().out
    (plans / "scan.png").unlink()
    assert scan.main(["--since", "2026-01-02", "--sources", str(logs), "--records", str(plans), str(plans)]) == 0
    assert "0 unsourced; read 1 records" in capsys.readouterr().out            # nothing unreadable: the line as it was


@pytest.mark.skipif(not hasattr(os, "geteuid") or os.geteuid() == 0, reason="the superuser opens anything")
def test_a_record_or_a_folder_that_cannot_be_opened_is_named_unreadable(tmp_path, logs, capsys):
    plans = tmp_path / "plans"
    locked, sealed = plans / "locked.md", plans / "sealed"
    sealed.mkdir(parents=True)
    for file in (locked, sealed / "inside.md"):
        file.write_text(f"- [ ] reply to the thread at {MADE_UP}\n", encoding="utf-8")
    locked.chmod(0)
    sealed.chmod(0)
    try:
        code = scan.main(["--since", "2026-01-02", "--sources", str(logs), "--records", str(plans), str(plans)])
    finally:
        locked.chmod(0o600)
        sealed.chmod(0o700)
    out = capsys.readouterr().out
    assert code == 1 and "locked.md: unreadable" in out and "sealed: unreadable" in out
    assert "0 unsourced, 2 unreadable; read 0 records" in out


def test_a_path_that_names_no_file_or_folder_stops_the_scan(kb, logs, capsys):
    absent = kb / "daily-plans" / "2026-01-03.md"
    assert scan.main(["--since", "2026-01-02", "--sources", str(logs), str(kb), str(absent)]) == 2
    assert "2026-01-03.md" in capsys.readouterr().err


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="no named pipes here")
def test_a_pipe_in_a_declared_folder_is_no_record_and_never_holds_the_scan(tmp_path, logs):
    plans = tmp_path / "plans"
    plans.mkdir()
    os.mkfifo(plans / "feed")
    (plans / "2026-01-02.md").write_text("- [ ] nothing from a chat here\n", encoding="utf-8")
    done = subprocess.run([sys.executable, str(SCRIPT), "--since", "2026-01-02", "--sources", str(logs), "--records", str(plans),
                           str(plans)], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0 and "0 unsourced; read 1 records" in done.stdout

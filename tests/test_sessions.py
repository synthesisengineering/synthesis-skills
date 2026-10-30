"""Agent session transcripts in one form for every harness: each adapter keeps the conversation, masks secrets,
keeps media and long text once by hash, and reads a native file only past what it already exported."""

import base64
import json
import os
import re
import subprocess
from pathlib import Path

import pytest

from synthesis import cli, project, sessions

PNG = base64.b64encode(b"\x89PNG\r\n\x1a\n not really an image").decode()
LONG = "line of tool output\n" * 300  # past BLOB_CHARS
EXAMPLE_KEY = "AKIAIOSFODNN7EXAMPLE"  # AWS's published example: the commit check lets it through, the export masks it


def _jsonl(path: Path, rows: list, newline: bool = True) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as out:
        out.write("".join(json.dumps(r) + "\n" for r in rows[:-1]) + json.dumps(rows[-1]) + ("\n" if newline else ""))
    return path


def _claude_rows(cwd: str) -> list:
    base = {"cwd": cwd, "sessionId": "c1", "timestamp": "2026-10-30T10:00:00.000Z"}
    reminder = {**base, "type": "attachment", "attachment": {"type": "hook_additional_context",
                                                            "content": "Active project: alpha (/kb/projects/alpha)"}}
    return [
        {**base, "type": "custom-title", "customTitle": "planning"},
        reminder, dict(reminder),
        {**base, "type": "user", "message": {"role": "user", "content": "Please plan the release."}},
        {**base, "type": "assistant", "message": {"model": "claude-opus-5-5", "content": [
            {"type": "thinking", "thinking": "Check CI first."}, {"type": "text", "text": "Checking CI."},
            {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": f"echo {EXAMPLE_KEY}"}}]}},
        {**base, "type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "t1", "content": [
                {"type": "text", "text": f"key {EXAMPLE_KEY}\n" + LONG},
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": PNG}}]}]}},
        {**base, "type": "user", "isMeta": True, "message": {"role": "user", "content": "<system-reminder>x</system-reminder>"}},
        {**base, "type": "api-request-blob", "message": {"content": [{"type": "text", "text": "a copy"}]}},
        {**base, "type": "system", "subtype": "compact_boundary", "compactMetadata": {"trigger": "auto"}},
    ]


@pytest.fixture
def harness(tmp_path, write_config):
    work = tmp_path / "workspaces" / "acme" / "repo"
    work.mkdir(parents=True)
    write_config({"workspace_roots": [str(tmp_path / "workspaces" / "*")]})
    claude = Path(os.environ["CLAUDE_CONFIG_DIR"]) / "projects" / "-acme" / "c1.jsonl"
    return {"work": str(work), "claude": claude}


def _meta(native: Path) -> dict:
    return next(m for m in sessions.catalog() if m["native"] == str(native))


def test_claude_keeps_the_conversation_masks_secrets_and_keeps_media_and_long_text_once(harness):
    native = _jsonl(harness["claude"], _claude_rows(harness["work"]))
    assert sessions.export_file("claude-code", native) > 0
    meta = _meta(native)
    assert Path(meta["folder"]).parts[-3] == "acme" and meta["projects"] == ["alpha"]
    assert meta["models"] == ["claude-opus-5-5"] and meta["skipped"]["api-request-blob"] == 1
    assert meta["skipped"]["duplicate"] == 1  # the second identical reminder
    rows = sessions.records(meta["folder"])
    kinds = [r["kind"] for r in rows]
    assert kinds.count("user") == 1 and "reasoning" in kinds and "compaction" in kinds
    text = json.dumps(rows)
    assert EXAMPLE_KEY not in text and "[redacted AWS access key" in text
    result = next(r for r in rows if r["kind"] == "tool_result")
    assert len(result["text"]) == sessions.HEAD_CHARS and result["text_chars"] > sessions.BLOB_CHARS
    assert (Path(meta["folder"]) / result["media"][0]["file"]).read_bytes().startswith(b"\x89PNG")
    whole = next(r for r in sessions.records(meta["folder"], ("tool_result",), whole=True))
    assert whole["text"].endswith(LONG) and EXAMPLE_KEY not in whole["text"]


def test_an_export_reads_only_what_is_new_and_waits_for_a_line_still_being_written(harness):
    native = _jsonl(harness["claude"], _claude_rows(harness["work"]))
    first = sessions.export_file("claude-code", native)
    assert sessions.export_file("claude-code", native) == 0
    line = {"type": "user", "cwd": harness["work"], "timestamp": "2026-10-30T11:00:00Z",
            "message": {"role": "user", "content": "And the changelog."}}
    _jsonl(native, [line], newline=False)
    assert sessions.export_file("claude-code", native) == 0  # half a line is never read
    with native.open("a") as out:
        out.write("\n")
    assert sessions.export_file("claude-code", native) == 1
    rows = sessions.records(_meta(native)["folder"])
    assert len(rows) == first + 1 and [r["seq"] for r in rows] == list(range(first + 1))


def test_codex_keeps_each_prompt_once_and_its_screenshots_as_files(harness):
    url = "data:image/png;base64," + PNG
    native = _jsonl(Path(os.environ["CODEX_HOME"]) / "sessions" / "2026" / "10" / "30" /
                    "rollout-2026-10-30T10-00-00-01a18a2b-0000-7000-8000-000000000001.jsonl", [
        {"type": "session_meta", "timestamp": "2026-10-30T10:00:00Z", "payload": {"id": "x", "cwd": harness["work"],
                                                                                   "cli_version": "0.166.0"}},
        {"type": "turn_context", "timestamp": "2026-10-30T10:00:01Z", "payload": {"model": "gpt-6", "effort": "high"}},
        {"type": "response_item", "timestamp": "2026-10-30T10:00:02Z", "payload": {
            "type": "message", "role": "user", "content": [{"type": "input_text", "text": "<environment_context>cwd</environment_context>"}]}},
        {"type": "response_item", "timestamp": "2026-10-30T10:00:02Z", "payload": {
            "type": "message", "role": "user", "content": [{"type": "input_text", "text": "Fix the build."}]}},
        {"type": "event_msg", "timestamp": "2026-10-30T10:00:02Z", "payload": {"type": "user_message", "message": "Fix the build."}},
        {"type": "response_item", "timestamp": "2026-10-30T10:00:03Z", "payload": {
            "type": "reasoning", "summary": [{"type": "summary_text", "text": "Look at the log."}], "encrypted_content": "zz"}},
        {"type": "response_item", "timestamp": "2026-10-30T10:00:04Z", "payload": {
            "type": "function_call", "name": "exec", "call_id": "c1", "arguments": "{\"cmd\": \"make\"}"}},
        {"type": "response_item", "timestamp": "2026-10-30T10:00:05Z", "payload": {
            "type": "function_call_output", "call_id": "c1", "output": [
                {"type": "input_text", "text": "Build failed"}, {"type": "input_image", "image_url": url}]}},
        {"type": "event_msg", "timestamp": "2026-10-30T10:00:05Z", "payload": {"type": "item_completed"}},
        {"type": "compacted", "timestamp": "2026-10-30T10:00:06Z", "payload": {"message": "Summary so far",
                                                                              "replacement_history": [1, 2, 3]}},
        {"type": "response_item", "timestamp": "2026-10-30T10:00:07Z", "payload": {
            "type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "Fixed."}]}},
    ])
    sessions.export_file("codex", native)
    meta = _meta(native)
    rows = sessions.records(meta["folder"])
    assert meta["session"] == "01a18a2b-0000-7000-8000-000000000001" and meta["models"] == ["gpt-6"]
    assert [r["text"] for r in rows if r["kind"] == "user"] == ["Fix the build."]
    assert next(r for r in rows if r["kind"] == "assistant")["model"] == "gpt-6"
    result = next(r for r in rows if r["kind"] == "tool_result")
    assert result["text"] == "Build failed" and result["media"][0]["type"] == "image/png"
    assert meta["skipped"]["compaction history items"] == 3 and meta["skipped"]["encrypted reasoning"] == 1


def test_muse_frames_and_their_children_become_records(harness):
    def frame(kind, event, at):
        return {"payload_type": "runtime.session", "recorded_at": at, "payload": {"kind": "run", "event": {"kind": kind, **event}}}
    native = _jsonl(Path(os.environ["XDG_DATA_HOME"]) / "muse" / "sessions" / "2026" / "10" / "30" / "01a1-muse" / "session.jsonl", [
        {"payload_type": "runtime.session.metadata", "recorded_at": 1793350000000000,
         "payload": {"kind": "metadata", "record": {"workspace_root": harness["work"], "model_id": "muse-spark"}}},
        {"payload_type": "runtime.user_intent.accepted", "recorded_at": 1793350000500000, "payload": {
            "surface": "main", "model_messages": [{"content": [{"kind": "text", "text": "Review the draft."}]}]}},
        {**frame("user_prompt_display", {"prompt": "Review the draft."}, 1793350001000000),
         "children": [frame("model_completed", {"model": "muse-spark", "usage": {}}, 1793350002000000)]},
        frame("assistant_tool_calls_committed", {"tool_calls": [{"call_id": "k1", "name": "read_file", "args": "{}"}]}, 1793350003000000),
        frame("tool_result_batch_committed", {"results": [{"tool_call_id": "k1", "text": "draft text"}]}, 1793350004000000),
        frame("assistant_message_committed", {"text": "Two edits."}, 1793350005000000),
    ])
    sessions.export_file("muse", native)
    rows = sessions.records(_meta(native)["folder"])
    assert [r["kind"] for r in rows] == ["session", "user", "tool_call", "tool_result", "assistant"]
    assert rows[-1]["model"] == "muse-spark" and rows[1]["at"].startswith("2026-")


def test_long_text_is_stored_once_for_every_session_in_the_workspace(harness):
    for name in ("c1", "c2"):
        _jsonl(harness["claude"].with_name(f"{name}.jsonl"), _claude_rows(harness["work"]))
    report = sessions.export(0)
    assert len(report) == 2
    blobs = list((sessions.root() / "acme" / "blobs").rglob("*.txt"))
    assert len(blobs) == 1


def test_segments_rotate_and_reading_follows_them(harness, monkeypatch):
    monkeypatch.setattr(sessions, "SEGMENT_BYTES", 600)
    native = _jsonl(harness["claude"], _claude_rows(harness["work"]))
    count = sessions.export_file("claude-code", native)
    folder = Path(_meta(native)["folder"])
    assert len(list(folder.glob("transcript-*.jsonl"))) > 1 and len(sessions.records(str(folder))) == count


def test_resume_shows_the_projects_recent_conversation_from_any_harness(harness, tmp_path, capsys):
    _jsonl(harness["claude"], _claude_rows(harness["work"]))
    kb = tmp_path / "kb"
    (kb / "projects" / "alpha").mkdir(parents=True)
    (kb / "projects" / "alpha" / "CONTEXT.md").write_text("**Phase:** build\n**Status:** active\n", encoding="utf-8")
    text = project.resume(str(kb / "projects" / "alpha"), "S-new")
    assert "Recent conversation in this project" in text and "Please plan the release." in text
    assert cli.main(["sessions", "search", "plan the release", "--project", "alpha"]) == 0
    assert "Please plan the release." in capsys.readouterr().out
    assert cli.main(["sessions", "show", "c1", "--kinds", "user"]) == 0
    assert capsys.readouterr().out.count("\n") == 1


def test_a_transcript_outside_every_workspace_is_kept_under_other(harness, tmp_path):
    native = _jsonl(harness["claude"], _claude_rows(str(tmp_path)))
    sessions.export_file("claude-code", native)
    assert Path(_meta(native)["folder"]).parts[-3] == "other"


# --- attribution (R10.1) --------------------------------------------------------------------------------------


def _codex_child(harness, sid: str, source: dict, prompt: str, reply: str) -> Path:
    return _jsonl(Path(os.environ["CODEX_HOME"]) / "sessions" / "2026" / "10" / "30" / f"rollout-2026-10-30T10-00-00-{sid}.jsonl", [
        {"type": "session_meta", "timestamp": "2026-10-30T10:00:00Z", "payload": {
            "id": sid, "cwd": harness["work"], "parent_thread_id": "01a1parent-0000", "source": {"subagent": source}}},
        {"type": "turn_context", "timestamp": "2026-10-30T10:00:01Z", "payload": {"model": "codex-auto-review"}},
        {"type": "response_item", "timestamp": "2026-10-30T10:00:02Z", "payload": {
            "type": "message", "role": "user", "content": [{"type": "input_text", "text": prompt}]}},
        {"type": "response_item", "timestamp": "2026-10-30T10:00:03Z", "payload": {
            "type": "message", "role": "assistant", "content": [{"type": "output_text", "text": reply}]}},
    ])


def test_a_codex_reviewer_keeps_its_verdict_and_only_counts_its_copy_of_the_conversation(harness):
    native = _codex_child(harness, "01a1review-0000-7000-8000-000000000001", {"other": "guardian"},
                          "The following is the Codex agent history whose request action you are reviewing ...",
                          "Approve: the command only reads files.")
    sessions.export_file("codex", native)
    meta = _meta(native)
    rows = sessions.records(meta["folder"])
    assert meta["role"] == "reviewer" and meta["parent"] == "01a1parent-0000"
    assert not [r for r in rows if r["kind"] in ("user", "brief")]
    assert meta["skipped"]["reviewer's copy of the conversation"] == 1
    assert [r["text"] for r in rows if r["kind"] == "assistant"] == ["Approve: the command only reads files."]


def test_a_spawned_agent_and_a_claude_sub_agent_are_briefed_not_prompted_by_the_principal(harness):
    native = _codex_child(harness, "01a1spawn-0000-7000-8000-000000000002",
                          {"thread_spawn": {"parent_thread_id": "01a1parent-0000"}}, "Survey the test suite.", "Done.")
    sessions.export_file("codex", native)
    assert [r["kind"] for r in sessions.records(_meta(native)["folder"]) if r["kind"] in ("user", "brief")] == ["brief"]
    base = {"cwd": harness["work"], "sessionId": "c9", "timestamp": "2026-10-30T10:00:00Z", "type": "user"}
    claude = _jsonl(harness["claude"].with_name("c9.jsonl"), [
        {**base, "isSidechain": True, "message": {"role": "user", "content": "Research the release notes."}},
        {**base, "message": {"role": "user", "content": "<cross-session-message from=\"S2\">ready</cross-session-message>"}},
        {**base, "message": {"role": "user", "content": "<heartbeat><automation_id>x</automation_id></heartbeat>"}},
        {**base, "message": {"role": "user", "content": "Ship it."}},
    ])
    sessions.export_file("claude-code", claude)
    kinds = [(r["kind"], r.get("text", "")[:12]) for r in sessions.records(_meta(claude)["folder"])]
    assert kinds == [("brief", "Research the"), ("brief", "<cross-sessi"), ("system", "<heartbeat><"), ("user", "Ship it.")]


def test_a_sub_agent_belongs_to_the_workspace_its_parent_started_in_and_workflow_journals_are_not_transcripts(harness, tmp_path):
    folder = re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(tmp_path / "workspaces" / "acme"))
    sub = Path(os.environ["CLAUDE_CONFIG_DIR"]) / "projects" / folder / "parent" / "subagents"
    elsewhere = str(tmp_path / "plugin-cache" / "scripts")  # sub-agents often work outside the workspace
    native = _jsonl(sub / "agent-a1.jsonl", [{"type": "user", "isSidechain": True, "cwd": elsewhere, "timestamp": "2026-10-30T10:00:00Z",
                                              "message": {"role": "user", "content": "Check the script."}}])
    _jsonl(sub / "workflows" / "wf_1" / "journal.jsonl", [{"type": "started", "agentId": "a2"}])
    sessions.export(0)
    assert Path(_meta(native)["folder"]).parts[-3] == "acme" and _meta(native)["cwd"] == elsewhere
    assert not [m for m in sessions.catalog() if m["native"].endswith("journal.jsonl")]


def test_a_rebuild_moves_the_archive_aside_and_exports_everything_again(harness):
    native = _jsonl(harness["claude"], _claude_rows(harness["work"]))
    first = sessions.export_file("claude-code", native)
    report = sessions.export(rebuild=True)
    moved = Path(report[0].split(" moved to ")[1])
    assert (moved / "acme").is_dir() and report[1:] == [f"claude-code c1: {first} record(s)"]


def test_one_export_at_a_time_and_a_resume_never_waits_for_it(harness):
    import fcntl
    _jsonl(harness["claude"], _claude_rows(harness["work"]))
    lock = sessions.paths.home() / "sessions.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("a") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        assert sessions.export(0, wait=False) == ["not exported: another export is running, so the archive is read as it is"]
        assert not sessions.root().exists()
    report = sessions.export(0, wait=False)
    assert len(report) == 1 and report[0].startswith("claude-code c1: ")


def test_show_opens_a_cited_record_with_its_neighbors(harness, capsys):
    _jsonl(harness["claude"], _claude_rows(harness["work"]))
    sessions.export(0)
    assert cli.main(["sessions", "show", "c1", "--seq", "1"]) == 0
    shown = [line.split()[0] for line in capsys.readouterr().out.splitlines()]
    assert shown == ["#0", "#1", "#2", "#3", "#4"]


# --- sync (R10.2 to R10.4) ------------------------------------------------------------------------------------


def _git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def synced(harness, tmp_path, write_config):
    remote = tmp_path / "sessions.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    repo = tmp_path / "ai-sessions-acme"
    subprocess.run(["git", "clone", "-q", str(remote), str(repo)], check=True, capture_output=True)
    write_config({"workspace_roots": [str(tmp_path / "workspaces" / "*")],
                  "sessions_repos": {"acme": str(repo), "other": str(tmp_path / "never")}})
    return {**harness, "repo": repo, "remote": remote}


def test_sync_copies_the_conversation_and_tool_calls_and_never_an_unplaced_session(synced, tmp_path):
    _jsonl(synced["claude"], _claude_rows(synced["work"]))
    _jsonl(synced["claude"].with_name("c2.jsonl"), _claude_rows(str(tmp_path)))  # outside every workspace
    report = sessions.sync()
    assert report[-1] == "acme: ai-sessions-acme up to date" and not any(line.startswith("FAILED") for line in report)
    assert _git(synced["remote"], "log", "--format=%s") == "Sessions: 2026-10 (1 changed)"
    files = sorted(p.relative_to(synced["repo"]).as_posix() for p in synced["repo"].rglob("*") if p.is_file() and ".git" not in p.parts)
    assert files == ["2026-10/claude-code-c1/meta.json", "2026-10/claude-code-c1/transcript-0001.jsonl"]
    kinds = {json.loads(line)["kind"] for line in (synced["repo"] / files[1]).read_text(encoding="utf-8").splitlines()}
    assert "tool_call" in kinds and "user" in kinds and kinds <= set(sessions.SYNC_KINDS)
    assert "native" not in json.loads((synced["repo"] / files[0]).read_text(encoding="utf-8"))
    assert sessions.sync()[-1] == "acme: ai-sessions-acme up to date"
    assert _git(synced["remote"], "rev-list", "--count", "main") == "1"  # nothing new, nothing committed
    _jsonl(synced["claude"], [{"type": "user", "cwd": synced["work"], "timestamp": "2026-10-30T12:00:00Z",
                               "message": {"role": "user", "content": "One more thing."}}])
    sessions.sync()
    assert _git(synced["remote"], "rev-list", "--count", "main") == "2"


def test_sessions_another_mac_synced_are_read_from_the_repo(synced):
    folder = synced["repo"] / "2026-09" / "codex-elsewhere"
    folder.mkdir(parents=True)
    (folder / "meta.json").write_text(json.dumps({"harness": "codex", "session": "elsewhere", "last": "2026-09-01"}))
    (folder / "transcript-0001.jsonl").write_text(json.dumps({"seq": 0, "kind": "user", "text": "hello from the other Mac"}) + "\n")
    found = [m for m in sessions.catalog() if m.get("session") == "elsewhere"]
    assert found and found[0]["synced"] == "acme"
    assert [r["text"] for r in sessions.search("other Mac")] == ["hello from the other Mac"]


def test_a_refused_commit_stops_that_workspace_and_records_nothing_as_synced(synced):
    _jsonl(synced["claude"], _claude_rows(synced["work"]))
    hooks = synced["repo"] / ".git" / "hooks"
    (hooks / "pre-commit").write_text("#!/bin/sh\necho refused by the commit check\nexit 1\n")
    os.chmod(hooks / "pre-commit", 0o755)
    _git(synced["repo"], "config", "core.hooksPath", str(hooks))
    report = sessions.sync()
    assert report[-1].startswith("FAILED acme: commit for 2026-10 refused") and "refused by the commit check" in report[-1]
    assert not (sessions.root() / ".state" / "sync-acme.json").exists()


def test_a_session_codex_archived_is_still_exported(harness):
    archived = Path(os.environ["CODEX_HOME"]) / "archived_sessions" / "rollout-2026-07-03T13-37-49-01a1arch-0000-7000-8000-000000000003.jsonl"
    _jsonl(archived, [{"type": "session_meta", "timestamp": "2026-07-03T13:37:49Z", "payload": {"id": "a", "cwd": harness["work"]}},
                      {"type": "response_item", "timestamp": "2026-07-03T13:38:00Z", "payload": {
                          "type": "message", "role": "user", "content": [{"type": "input_text", "text": "Archive me."}]}}])
    assert sessions.export(0) == ["codex 01a1arch-0000-7000-8000-000000000003: 2 record(s)"]


def test_only_the_session_start_hooks_own_text_names_a_project(harness):
    rows = _claude_rows(harness["work"])
    rows.insert(3, {"cwd": harness["work"], "sessionId": "c1", "timestamp": "2026-10-30T10:00:00Z", "type": "attachment",
                    "attachment": {"type": "edited_text_file", "content": "fixture: Active project: beta (/kb/projects/beta)"}})
    native = _jsonl(harness["claude"], rows)
    sessions.export_file("claude-code", native)
    assert _meta(native)["projects"] == ["alpha"]


def test_a_citation_of_a_parent_session_opens_it_not_its_sub_agents(harness, capsys):
    _jsonl(harness["claude"], _claude_rows(harness["work"]))
    sub = harness["claude"].parent / "c1" / "subagents" / "agent-a1.jsonl"
    _jsonl(sub, [{"type": "user", "isSidechain": True, "cwd": harness["work"], "timestamp": "2026-10-30T10:00:00Z",
                  "message": {"role": "user", "content": "Check the script."}}])
    sessions.export(0)
    agent = _meta(sub)
    assert agent["role"] == "subagent" and agent["parent"] == "c1" and agent["session"] == "c1-agent-a1"
    assert [m["session"] for m in sessions.find("c1")] == ["c1"]
    assert cli.main(["sessions", "show", "c1", "--kinds", "user"]) == 0
    assert "Please plan the release." in capsys.readouterr().out


def test_a_session_that_cannot_export_still_sees_the_latest_turns(harness, tmp_path):
    """Codex's sandbox may write only the board: resume reads the archive as it is, plus what each harness recorded
    since, without writing anything."""
    _jsonl(harness["claude"], _claude_rows(harness["work"]))
    sessions.export(0)
    _jsonl(harness["claude"], [{"type": "user", "cwd": harness["work"], "timestamp": "2026-10-30T12:00:00Z",
                                "message": {"role": "user", "content": "One more thing."}}])
    lock = sessions.paths.home() / "sessions.lock"
    lock.chmod(0o444)  # as in the sandbox: the lock, and the archive with it, cannot be written
    try:
        assert sessions.export(2, wait=False)[0].startswith("not exported:")
        before = sorted(p.stat().st_mtime for p in sessions.root().rglob("*") if p.is_file())
        assert "One more thing." not in [r["text"] for r in sessions.recent("alpha")]
        assert "One more thing." in [r["text"] for r in sessions.recent("alpha", live=True)]
        assert sorted(p.stat().st_mtime for p in sessions.root().rglob("*") if p.is_file()) == before
        kb = tmp_path / "kb"
        (kb / "projects" / "alpha").mkdir(parents=True)
        (kb / "projects" / "alpha" / "CONTEXT.md").write_text("**Phase:** build\n**Status:** active\n", encoding="utf-8")
        assert "One more thing." in project.resume(str(kb / "projects" / "alpha"), "S-new")
    finally:
        lock.chmod(0o644)


def test_sync_takes_the_same_writer_lock_as_export(synced):
    _jsonl(synced["claude"], _claude_rows(synced["work"]))
    sessions.export(0)
    lock = sessions.paths.home() / "sessions.lock"
    lock.chmod(0o444)
    try:
        assert sessions.sync() == [f"FAILED sessions sync: not exported: [Errno 13] Permission denied: '{lock}'"]
    finally:
        lock.chmod(0o644)
    assert sessions.sync()[-1] == "acme: ai-sessions-acme up to date"

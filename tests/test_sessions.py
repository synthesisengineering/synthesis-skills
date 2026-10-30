"""Agent session transcripts in one form for every harness: each adapter keeps the conversation, masks secrets,
keeps media and long text once by hash, and reads a native file only past what it already exported."""

import base64
import json
import os
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

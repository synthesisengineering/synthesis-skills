"""Agent session transcripts in one form for every harness: each adapter keeps the conversation, masks secrets,
keeps media and long text once by hash, and reads a native file only past what it already exported."""

import base64
import contextlib
import json
import os
import re
import subprocess
from pathlib import Path

import pytest

from synthesis import cli, project, sessions

# A test that closes a file or a folder by its mode says nothing as root, who reads and writes whatever the mode.
closed_to_us = pytest.mark.skipif(os.geteuid() == 0, reason="root reads and writes a file whatever its mode")

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


def _archived(native: Path) -> list:
    """Every line of a session's archive, in order, parsed: a line that is no whole record fails here."""
    folder = Path(_meta(native)["folder"])
    return [json.loads(line) for file in sorted(folder.glob("transcript-*.jsonl"))
            for line in file.read_text(encoding="utf-8").splitlines()]


@pytest.mark.parametrize("segment_bytes", [10**9, 600])  # in one segment, and where the cut run had begun another
def test_a_copy_cut_between_its_records_and_its_state_appends_nothing_twice(harness, monkeypatch, segment_bytes):
    """A copy appends its records and then saves how far it read. Cut between the two (a crash, a full disk, a
    machine put to sleep), the next run read the same lines again and appended the same records again, each number
    twice: a prompt was then listed twice among what the principal typed (noted by a review, 2026-11-12)."""
    monkeypatch.setattr(sessions, "SEGMENT_BYTES", segment_bytes)
    rows = _claude_rows(harness["work"])
    native = _jsonl(harness["claude"], rows[:4])
    first, real = sessions.export_file("claude-code", native), sessions.paths.write_json
    _jsonl(native, rows[4:])

    def cut(path, data):
        if Path(path).parent.name == ".state":
            raise OSError("cut before the state was saved")
        return real(path, data)
    with monkeypatch.context() as broken:
        broken.setattr(sessions.paths, "write_json", cut)
        with pytest.raises(OSError):
            sessions.export_file("claude-code", native)
    cut_at = len(_archived(native))
    assert cut_at > first  # the records were appended, and nothing says so
    sessions.export_file("claude-code", native)
    kept = _archived(native)
    assert [r["seq"] for r in kept] == list(range(cut_at))  # each record once, none added, none removed
    assert sessions.export_file("claude-code", native) == 0 and len(_archived(native)) == cut_at


def test_a_line_torn_by_a_cut_write_is_finished_as_a_whole_record(harness):
    """Cut in the middle of a line, the archive ends in part of a record. The next run's first record was written
    onto the end of it, and the two made one line that no reader could parse."""
    rows = _claude_rows(harness["work"])
    native = _jsonl(harness["claude"], rows[:4])
    first = sessions.export_file("claude-code", native)
    segment = sorted(Path(_meta(native)["folder"]).glob("transcript-*.jsonl"))[-1]
    with segment.open("a", encoding="utf-8") as out:
        out.write('{"seq": %d, "kind": "user", "te' % first)
    _jsonl(native, rows[4:])
    assert sessions.export_file("claude-code", native) > 0
    kept = _archived(native)
    assert [r["seq"] for r in kept] == list(range(len(kept))) and len(kept) > first


def test_what_the_archive_holds_is_counted_past_a_line_no_reader_can_parse_and_from_any_length_of_file(harness, monkeypatch):
    """The count of what is held reads the archive's end, back as far as it needs: past a whole line that is no
    record, through a last record longer than one read, and from a state that was lost altogether."""
    rows = _claude_rows(harness["work"])
    native = _jsonl(harness["claude"], rows[:4])
    first = sessions.export_file("claude-code", native)
    segment = sorted(Path(_meta(native)["folder"]).glob("transcript-*.jsonl"))[-1]
    with segment.open("a", encoding="utf-8") as out:
        out.write("not a record\n" + json.dumps({"seq": first, "kind": "system", "text": "x" * 200_000}) + "\n" + "[1, 2]\n")
    state = next((sessions.root() / ".state").glob("claude-code-*.json"))
    state.unlink()  # nothing says what was read: everything is read again, and nothing is appended twice
    _jsonl(native, rows[4:])
    sessions.export_file("claude-code", native)
    kept = sessions.records(_meta(native)["folder"])
    assert [r["seq"] for r in kept] == list(range(len(kept))) and len(kept) > first + 1
    assert segment.read_text(encoding="utf-8").count("not a record\n") == 1  # what was there stays


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


def _codex_turn(text: str, at: str, copies: str = "ie") -> list:
    """A turn as Codex records it: the response item (i) and the UI event (e) that mirrors it, in the order given."""
    rows = {"i": {"type": "response_item", "timestamp": at, "payload": {
                "type": "message", "role": "user", "content": [{"type": "input_text", "text": text}]}},
            "e": {"type": "event_msg", "timestamp": at, "payload": {"type": "user_message", "message": text}}}
    return [rows[c] for c in copies]


def _codex_reply(text: str, at: str) -> dict:
    return {"type": "response_item", "timestamp": at, "payload": {
        "type": "message", "role": "assistant", "content": [{"type": "output_text", "text": text}]}}


@pytest.mark.parametrize("copies", ["ie", "ei", "i"])  # the response item first, the UI event first, a turn written once
def test_the_same_words_typed_again_are_another_turn_and_only_a_mirrored_copy_is_removed(harness, copies):
    """A person who answers `Yes.` to two questions typed two prompts (2026-11-12: the second was removed as a copy
    of the first, so a go the principal gave was in no list of what they typed)."""
    first = _codex_turn("Yes.", "2026-10-30T10:00:02Z", copies)
    native = _jsonl(Path(os.environ["CODEX_HOME"]) / "sessions" / "2026" / "10" / "30" / "rollout-2026-10-30T10-00-00-y3.jsonl", [
        {"type": "session_meta", "timestamp": "2026-10-30T10:00:00Z", "payload": {"id": "y3", "cwd": harness["work"]}}, first[0]])
    sessions.export_file("codex", native)                  # an export may end between a turn and its mirrored copy
    _jsonl(native, [*first[1:], _codex_reply("Done. Shall I tag it too?", "2026-10-30T10:00:09Z"),
                    *_codex_turn("Yes.", "2026-10-30T10:05:00Z", copies), _codex_reply("Tagged.", "2026-10-30T10:05:09Z")])
    sessions.export_file("codex", native)
    turns = [(r["kind"], r["text"]) for r in sessions.records(_meta(native)["folder"]) if r["kind"] in ("user", "assistant")]
    assert turns == [("user", "Yes."), ("assistant", "Done. Shall I tag it too?"), ("user", "Yes."), ("assistant", "Tagged.")]
    assert [p["text"] for p in sessions.prompts("acme", "2026-10-30")] == ["Yes.", "Yes."]


def test_a_person_who_continues_a_command_line_run_types_prompts_of_their_own(harness):
    """`codex exec` hands a run its prompt; the person who then continues that session types their own (2026-11-12:
    a correction typed into a continued run stayed a brief, in no list of what the principal typed)."""
    def began(source: str, at: str) -> dict:
        return {"type": "session_meta", "timestamp": at, "payload": {"id": "x7", "cwd": harness["work"], "source": source}}

    native = _jsonl(Path(os.environ["CODEX_HOME"]) / "sessions" / "2026" / "10" / "30" / "rollout-2026-10-30T10-00-00-x7.jsonl", [
        began("exec", "2026-10-30T10:00:00Z"), *_codex_turn("Review this branch.", "2026-10-30T10:00:02Z"),
        began("cli", "2026-10-30T11:00:00Z"), *_codex_turn("The second finding is wrong: read the test again.", "2026-10-30T11:00:05Z")])
    sessions.export_file("codex", native)
    _jsonl(native, [*_codex_turn("And check the third.", "2026-10-30T11:05:00Z"),      # a later export still knows who types
                    began("exec", "2026-10-30T12:00:00Z"), *_codex_turn("Review it again.", "2026-10-30T12:00:02Z")])
    sessions.export_file("codex", native)
    kinds = [(r["kind"], r["text"]) for r in sessions.records(_meta(native)["folder"]) if r["kind"] in ("user", "brief")]
    assert kinds == [("brief", "Review this branch."), ("user", "The second finding is wrong: read the test again."),
                     ("user", "And check the third."), ("brief", "Review it again.")]
    assert [p["text"] for p in sessions.prompts("acme", "2026-10-30")] == [text for kind, text in kinds if kind == "user"]


def test_a_turn_that_says_how_it_began_is_read_by_that(harness):
    """Codex writes how each turn began (`turn_attribution.turn_trigger` on `task_started`: `composer` for what a
    person typed, `exec` for a command line; three days of real rollouts, 2026-11-12). A run begun from a command
    line and continued in place writes no second session line, so the turn's own word decides where there is one."""
    def began(trigger: str, at: str) -> dict:
        return {"type": "event_msg", "timestamp": at, "payload": {"type": "task_started", "turn_id": at,
                                                                  "turn_attribution": {"turn_id": at, "turn_trigger": trigger}}}

    native = _jsonl(Path(os.environ["CODEX_HOME"]) / "sessions" / "2026" / "10" / "30" / "rollout-2026-10-30T09-00-00-x8.jsonl", [
        {"type": "session_meta", "timestamp": "2026-10-30T09:00:00Z", "payload": {"id": "x8", "cwd": harness["work"], "source": "exec"}},
        began("exec", "2026-10-30T09:00:01Z"), *_codex_turn("Review this branch.", "2026-10-30T09:00:02Z"),
        began("composer", "2026-10-30T09:30:00Z"), *_codex_turn("Now look at the second file too.", "2026-10-30T09:30:02Z")])
    sessions.export_file("codex", native)
    _jsonl(native, [*_codex_turn("And the third.", "2026-10-30T09:31:00Z"),            # the same turn, in a later export
                    began("guardian_review", "2026-10-30T09:40:00Z"), *_codex_turn("Judge this command.", "2026-10-30T09:40:02Z"),
                    began("a_trigger_not_seen_before", "2026-10-30T09:50:00Z"), *_codex_turn("Something else.", "2026-10-30T09:50:02Z")])
    sessions.export_file("codex", native)
    kinds = [(r["kind"], r["text"]) for r in sessions.records(_meta(native)["folder"]) if r["kind"] in ("user", "brief")]
    assert kinds == [("brief", "Review this branch."), ("user", "Now look at the second file too."), ("user", "And the third."),
                     ("brief", "Judge this command."), ("user", "Something else.")]      # a trigger it does not know is listed, never lost


def _codex_line(harness, source: str, at: str) -> dict:
    """A session line: a run of the session begins, from a command line (`exec`) or a person's terminal (`cli`)."""
    return {"type": "session_meta", "timestamp": at, "payload": {"id": "t1", "cwd": harness["work"], "source": source}}


def _codex_task(at: str, said=None) -> dict:
    """The row a turn begins with. `said` is how it says it began: a trigger, or the whole attribution where that
    has another shape. None is a row that says nothing."""
    attribution = {} if said is None else {"turn_attribution": {"turn_id": at, "turn_trigger": said} if isinstance(said, str) else said}
    return {"type": "event_msg", "timestamp": at, "payload": {"type": "task_started", "turn_id": at, **attribution}}


def _codex_export(name: str, rows: list, whole: bool = True) -> list:
    """Write a rollout and export it, at once or with an export after every row (an export may end anywhere).
    Returns each prompt kept, with its kind."""
    native = Path(os.environ["CODEX_HOME"]) / "sessions" / "2026" / "10" / "30" / f"rollout-2026-10-30T10-00-00-{name}.jsonl"
    for part in [rows] if whole else [[row] for row in rows]:
        _jsonl(native, part)
        sessions.export_file("codex", native)
    return [(r["kind"], r["text"]) for r in sessions.records(_meta(native)["folder"]) if r["kind"] in ("user", "brief")]


NO_ROW = "no task_started row"
RUNS = {  # each turn: the session line before it (None: the same run goes on), how its first row says it began, what its prompt is
    "a command line's run that a person continues": [("exec", "exec", "brief"), ("cli", None, "user")],
    "a person's run that a command line continues": [("cli", "composer", "user"), ("exec", None, "brief")],
    "command line, person, command line": [("exec", "exec", "brief"), ("cli", None, "user"), ("exec", None, "brief")],
    "person, command line, person": [("cli", "composer", "user"), ("exec", None, "brief"), ("cli", None, "user")],
    "a person continues, and the turn has no first row": [("exec", "exec", "brief"), ("cli", NO_ROW, "user")],
    "a command line continues, and the turn has no first row": [("cli", "composer", "user"), ("exec", NO_ROW, "brief")],
    "a person's run: a silent turn after the reviewer's": [("cli", "guardian_review", "brief"), (None, None, "user")],
    "a command line's run: a silent turn after a person's": [("exec", "composer", "user"), (None, None, "brief")],
    "an attribution that names no trigger": [("exec", "exec", "brief"), ("cli", {"turn_id": "t", "turn_trigger": None}, "user")],
    "an attribution of a shape not seen before": [("cli", "exec", "brief"), (None, ["composer"], "user")],
}


@pytest.mark.parametrize("whole", [True, False], ids=["one export", "an export after every row"])
@pytest.mark.parametrize("turns", RUNS.values(), ids=RUNS.keys())
def test_a_turn_that_does_not_say_how_it_began_is_read_by_the_runs_source_never_by_the_turn_before(harness, turns, whole):
    """Each turn is read by its own first row. Where that row says nothing, or the turn has none, the session line
    current at that turn decides (2026-11-12, a second review: after a command line's turn, a person continued the
    run and their prompt stayed a brief, because the earlier turn's `exec` was still in force; the other way round
    a command line's prompt was listed as the person's)."""
    rows = []
    for at, (source, said, _) in enumerate(turns, 1):
        rows += [_codex_line(harness, source, f"2026-10-30T10:{at}0:00Z")] if source else []
        rows += [_codex_task(f"2026-10-30T10:{at}0:01Z", said)] if said != NO_ROW else []
        rows += _codex_turn(f"Prompt {at}.", f"2026-10-30T10:{at}0:02Z")
    wanted = [(kind, f"Prompt {at}.") for at, (_, _, kind) in enumerate(turns, 1)]
    assert _codex_export("t1", rows, whole) == wanted
    assert [p["text"] for p in sessions.prompts("acme", "2026-10-30")] == [text for kind, text in wanted if kind == "user"]


SAID = {  # the copies each turn's `Yes.` is written with: the response item (i), the UI event (e), or both in that order
    "an item-only turn, then an event-only one": ["i", "e"],
    "an event-only turn, then an item-only one": ["e", "i"],
    "a mirrored pair, then an item, then an event": ["ie", "i", "e"],
    "a pair written event first, then an event, then an item": ["ei", "e", "i"],
    "an item, an event, an item": ["i", "e", "i"],
    "one mirrored pair": ["ie"],                                       # these four were right before, and stay so
    "one pair written event first": ["ei"],
    "three mirrored pairs": ["ie", "ie", "ie"],
    "three item-only turns": ["i", "i", "i"],
}
SHOWN = {  # what in the rollout shows that one turn is over and another began
    "each turn has its first row": ("row",),
    "the agent replies to each turn": ("reply",),
    "a first row and a reply": ("row", "reply"),
    "each turn follows a new session line": ("line",),
}


@pytest.mark.parametrize("whole", [True, False], ids=["one export", "an export after every row"])
@pytest.mark.parametrize("shown", SHOWN.values(), ids=SHOWN.keys())
@pytest.mark.parametrize("turns", SAID.values(), ids=SAID.keys())
def test_a_copy_of_a_prompt_is_removed_only_within_the_turn_it_mirrors(harness, turns, shown, whole):
    """Codex writes a turn's prompt twice, side by side: only that second copy is removed. The same words in
    another turn are that turn's prompt, however each was written (2026-11-12, a second review: of two turns that
    each said `Yes.`, one kept only as a response item and the other only as a UI event, the second was removed as
    a copy of the first, in either order)."""
    rows = [_codex_line(harness, "cli", "2026-10-30T10:00:00Z")]
    for at, copies in enumerate(turns, 1):
        rows += [_codex_line(harness, "cli", f"2026-10-30T10:{at}0:00Z")] if "line" in shown else []
        rows += [_codex_task(f"2026-10-30T10:{at}0:01Z")] if "row" in shown else []
        rows += _codex_turn("Yes.", f"2026-10-30T10:{at}0:02Z", copies)
        rows += [_codex_reply(f"Done {at}.", f"2026-10-30T10:{at}0:09Z")] if "reply" in shown else []
    assert _codex_export("t2", rows, whole) == [("user", "Yes.")] * len(turns)
    assert [p["text"] for p in sessions.prompts("acme", "2026-10-30")] == ["Yes."] * len(turns)


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


def test_a_rebuild_changes_no_record_and_keeps_a_session_whose_transcript_is_gone(harness):
    """Until 5.17.0 a rebuild moved the whole archive aside and exported the transcripts that were still there: a
    session whose transcript its harness had since removed left the archive, and every other was numbered anew."""
    _jsonl(harness["claude"], _claude_rows(harness["work"]))
    gone = _jsonl(harness["claude"].with_name("c2.jsonl"), _claude_rows(harness["work"]))
    sessions.export(0)
    before = {meta["session"]: Path(meta["folder"], "transcript-0001.jsonl").read_bytes() for meta in sessions.catalog()}
    gone.unlink()
    assert sessions.export(rebuild=True) == [] and sorted(before) == ["c1", "c2"]
    assert {meta["session"]: Path(meta["folder"], "transcript-0001.jsonl").read_bytes() for meta in sessions.catalog()} == before
    assert not (sessions.paths.home() / "archive").exists()                       # nothing is moved aside


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
    shown = [line.split()[:3] for line in capsys.readouterr().out.splitlines()]
    assert shown == [["[claude-code", "c1]", f"#{n}"] for n in range(5)]                 # each line begins with its session


def test_a_cited_record_is_shown_whole_and_its_neighbors_stay_short(harness, capsys):
    """The day-end reads each prompt no record cites with `show --seq` (2026-11-12: a request made after a prompt's
    first 600 characters was missing from what it printed)."""
    asked = "Draft the announcement. " + "It goes to every list we keep. " * 30 + "Do not send it before Friday."
    _jsonl(harness["claude"], _claude_rows(harness["work"]) + [
        _typed({"cwd": harness["work"], "sessionId": "c1"}, asked, "2026-10-30T15:00:00.000Z")])
    sessions.export(0)
    rows = sessions.records(_meta(harness["claude"])["folder"])
    result = next(r["seq"] for r in rows if r["kind"] == "tool_result")
    assert rows[-1]["text"] == asked and len(asked) > 900 and rows[-1]["seq"] - result <= 3
    assert cli.main(["sessions", "show", "c1", "--seq", str(rows[-1]["seq"])]) == 0
    out = capsys.readouterr().out
    assert out.rstrip().endswith("Do not send it before Friday.")
    assert out.count("more characters]") == 1                                # the long tool result beside it stays cut
    assert cli.main(["sessions", "show", "c1", "--seq", str(result)]) == 0
    assert capsys.readouterr().out.count("line of tool output") == 300       # a long tool result, whole from its blob
    assert cli.main(["sessions", "show", "c1", "--seq", str(result), "--json"]) == 0
    shown = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert next(r for r in shown if r["seq"] == result)["text"].endswith(LONG)


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


@closed_to_us
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


@closed_to_us
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


@closed_to_us
def test_a_sync_whose_export_could_not_copy_a_transcript_leaves_that_in_the_stamp(synced):
    """Handoff and the day-end copy through `sync`, which exports first (2026-11-12: a copy that export could not make
    was in no report and no stamp, so nothing said a conversation had stayed behind). The failure is over when the
    transcript is copied, by whichever run copies it, and not before."""
    native = _jsonl(synced["claude"], _claude_rows(synced["work"]))
    stamp, written = sessions.root() / ".state" / "export.json", native.stat().st_mtime
    native.chmod(0o000)
    try:
        sessions.sync(push=False)
        kept = json.loads(stamp.read_text())
        assert kept["failed"] == 1 and "claude-code c1: not exported" in kept["reason"] and "complete" not in kept
    finally:
        native.chmod(0o644)
    os.utime(native, (written - 3 * 86400, written - 3 * 86400))
    sessions.sync(push=False)                                    # the two days a sync reads do not reach it: the failure stands
    assert json.loads(stamp.read_text())["failed"] == 1
    os.utime(native, (written, written))
    sessions.sync(push=False)                                    # within them, the sync's own export copies it,
    assert "failed" not in json.loads(stamp.read_text()) and sessions.export(0) == []      # and nothing is left to copy


def test_masking_covers_the_principals_tier_0_list_as_the_commit_check_loads_it(harness, monkeypatch):
    """2026-10-30: a quoted pattern matched only by the principal's tier-0 list stopped the first sync. The policy here
    is made up, so this file holds nothing credential-shaped; the key header follows test_commit_policy's convention."""
    from synthesis import commit_check
    monkeypatch.setattr(commit_check, "load_policy", lambda config: {"tier_0_always": {"made_up": ["zz-test-secret-[0-9]+"]}})
    monkeypatch.setattr(sessions, "_SECRETS", [])
    header = "-----BEGIN " + "RSA PRIVATE KEY-----"
    masked = sessions.mask("grep -rn ZZ-TEST-SECRET-42 .; key " + header + "\\n" + "A" * 64)
    assert "ZZ-TEST-SECRET-42" not in masked and "[redacted credential pattern" in masked
    assert "A" * 40 not in masked and "[redacted private key" in masked


def test_a_refused_month_leaves_nothing_staged_for_the_next_commit(synced, monkeypatch):
    rows = _claude_rows(synced["work"])
    _jsonl(synced["claude"], rows)
    _jsonl(synced["claude"].with_name("c3.jsonl"), [{**r, "timestamp": "2026-09-01T10:00:00Z"} for r in rows])
    hooks = synced["repo"] / ".git" / "hooks"
    (hooks / "pre-commit").write_text("#!/bin/sh\ngit diff --cached --name-only | grep -q '^2026-10/' && exit 1; exit 0\n")
    os.chmod(hooks / "pre-commit", 0o755)
    _git(synced["repo"], "config", "core.hooksPath", str(hooks))
    report = sessions.sync()
    assert "acme: 2026-09: 1 session(s) committed" in report and report[-1].startswith("FAILED acme: commit for 2026-10")
    assert _git(synced["repo"], "diff", "--cached", "--name-only") == ""
    assert _git(synced["repo"], "log", "-1", "--name-only", "--format=").split()[0].startswith("2026-09/")


# --- what the principal asked is accounted for (2026-11-11) ----------------------------------------------------
# "Make sure nothing is lost" should not need saying. The archive holds every prompt the principal typed; a record
# accounts for one by citing it (`<harness> <session> #<seq>`, alone or as a range), and what no record cites is
# listed, so a day cannot be closed clean over a request that reached no record.

def _typed(base: dict, text: str, at: str) -> dict:
    return {**base, "timestamp": at, "type": "user", "message": {"role": "user", "content": text}}


@pytest.fixture
def asked(harness, tmp_path):
    base = {"cwd": harness["work"], "sessionId": "c1"}
    rows = _claude_rows(harness["work"]) + [
        _typed(base, "Also draft the announcement.", "2026-10-30T15:00:00.000Z"),
        _typed(base, "And one more thing tomorrow.", "2026-10-31T15:00:00.000Z"),
        {**base, "timestamp": "2026-10-30T15:05:00.000Z", "type": "user", "isMeta": True,
         "message": {"role": "user", "content": "<system-reminder>not his words</system-reminder>"}},
    ]
    _jsonl(harness["claude"], rows)
    sessions.export(0)
    kb = tmp_path / "kb"
    (kb / "projects" / "alpha" / "sessions").mkdir(parents=True)
    return {**harness, "kb": kb, "log": kb / "projects" / "alpha" / "sessions" / "2026-10.md"}


def test_a_prompt_that_holds_a_line_separator_is_read_back_whole(harness):
    """Text pasted from a web page, or once decoded as another encoding, carries characters that Python counts as
    the end of a line and JSON does not escape (U+2028, U+2029, U+0085). A record that held one was written whole
    and read back as two halves, neither of them a record: the prompt was in the archive and nothing could list
    it, open it or sync it (a review, 2026-11-13)."""
    base = {"cwd": harness["work"], "sessionId": "c1"}
    typed = ["plain prompt", "pasted\u2028text from a page", "one paragraph\u2029and the next", "decoded wrong\x85once"]
    native = _jsonl(harness["claude"], [_typed(base, text, f"2026-10-30T15:0{at}:00.000Z") for at, text in enumerate(typed)])
    assert sessions.export_file("claude-code", native) == len(typed)
    kept = sessions.records(_meta(native)["folder"])
    assert [r["text"] for r in kept] == typed and [r["seq"] for r in kept] == list(range(len(typed)))
    assert [p["text"] for p in sessions.prompts("acme", "2026-10-30")] == typed
    assert sessions.export_file("claude-code", _jsonl(native, [_typed(base, "and one more", "2026-10-30T15:09:00.000Z")])) == 1
    assert [r["seq"] for r in sessions.records(_meta(native)["folder"])] == list(range(len(typed) + 1))


def test_the_schedules_own_flag_is_not_offered_to_a_person_or_an_agent(capsys):
    """`--scheduled` says a run is the schedule's own, and the doctor believes it. It works for the job that passes
    it and is in no help text, so nothing offers it as a way to quiet the doctor."""
    with pytest.raises(SystemExit):
        cli.main(["sessions", "--help"])
    assert "--scheduled" not in capsys.readouterr().out


def test_the_principals_prompts_of_a_day_are_listed_and_nothing_else(asked):
    found = sessions.prompts("acme", "2026-10-30")
    assert [p["text"] for p in found] == ["Please plan the release.", "Also draft the announcement."]
    assert all(p["harness"] == "claude-code" and p["session"] == "c1" and isinstance(p["seq"], int) for p in found)
    assert sessions.prompts("acme", "2026-10-31")[0]["text"] == "And one more thing tomorrow."
    assert sessions.prompts("other", "2026-10-30") == [] and sessions.prompts("acme", "2026-10-29") == []


def test_two_prompts_in_one_minute_are_listed_in_the_order_they_were_typed(harness, capsys):
    """2026-11-12: listed by the minute and then by session id, the later of two prompts came out first."""
    for name, text, at in (("z9", "First.", "2026-10-30T15:00:01.000Z"), ("a1", "Second.", "2026-10-30T15:00:59.000Z")):
        _jsonl(harness["claude"].with_name(f"{name}.jsonl"), [_typed({"cwd": harness["work"], "sessionId": name}, text, at)])
    sessions.export(0)
    found = sessions.prompts("acme", "2026-10-30")
    assert [(p["session"], p["text"]) for p in found] == [("z9", "First."), ("a1", "Second.")]
    assert found[0]["at"] == found[1]["at"] and re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d[+-]\d\d:\d\d", found[0]["at"])
    assert cli.main(["sessions", "prompts", "--workspace", "acme", "--date", "2026-10-30"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert [line.split()[1:3] for line in out[:2]] == [["z9", "--seq"], ["a1", "--seq"]]
    assert re.fullmatch(r"\d\d:\d\d", out[0].split()[4])                             # the minute, as before


def test_a_prompt_is_accounted_for_by_a_record_that_cites_it_alone_or_in_a_range(asked):
    first, second = sessions.prompts("acme", "2026-10-30")
    roots = [str(asked["kb"])]
    assert sessions.uncited([first, second], roots) == [first, second]
    asked["log"].write_text(f"- 10:00 planned the release (claude-code c1 #{first['seq']})\n", encoding="utf-8")
    assert sessions.uncited([first, second], roots) == [second]
    asked["log"].write_text(f"- the day's work, c1 #{first['seq']}-{second['seq']}\n", encoding="utf-8")
    assert sessions.uncited([first, second], roots) == []
    asked["log"].write_text(f"- c1 #{second['seq'] + 1}, c2 #{first['seq']}, c10 #{first['seq']}, c1 # {first['seq']}\n", encoding="utf-8")
    assert sessions.uncited([first, second], roots) == [first, second]      # another record, another session, no citation
    asked["log"].write_text(f"- both, c1 #{first['seq']} to #{second['seq']}\n", encoding="utf-8")
    assert sessions.uncited([first, second], roots) == []
    for joined in ("—", " – #", " through #", "-#", "...", " – "):  # a dash set off by spaces joins a number that has its `#`
        asked["log"].write_text(f"- planned and drafted: `claude-code c1 #{first['seq']}{joined}{second['seq']}`\n", encoding="utf-8")
        assert sessions.uncited([first, second], roots) == ([first, second][1:] if joined in ("...", " – ") else []), joined


def test_a_range_is_joined_on_one_line_and_ends_in_a_record_number(asked):
    """A citation at the end of a line was joined to the list item under it: `c1 #2`, then `- 2026-10-30 ...`, read as
    the range #2 to #2026, which cleared every later prompt of that session with nothing written about them."""
    first, second = found = sessions.prompts("acme", "2026-10-30")
    roots, cite = [str(asked["kb"])], f"claude-code c1 #{first['seq']}"
    assert first["seq"] < second["seq"] < 10
    for record in (f"- 10:00 planned the release, {cite}\n- 2026-10-30 the announcement is still to draft\n",     # a dated item under it,
                   f"Planned the release: {cite}\n\n- 40 items remain on the list\n",                                 # a counted one,
                   f"- {cite} — 2026-10-30: decided to ship on Friday\n",                                            # a dash and a date,
                   f"- {cite} - 10:30 the plan was agreed\n"):                                                        # or a time
        asked["log"].write_text(record, encoding="utf-8")
        assert sessions.uncited(found, roots) == [second], record
    asked["log"].write_text(f"- claude-code c1 #{second['seq']} - 3 options weighed, the second chosen\n", encoding="utf-8")
    assert sessions.uncited(found, roots) == [first]                # a number below the record's own ends no range: that record is cited
    for record in (f"c1 #{first['seq']}-{second['seq']}", f"(c1 #{first['seq']}–{second['seq']}).", f"c1 #{first['seq']} to\n  #{second['seq']}",
                   f"c1 #{first['seq']} through #{second['seq']}, then lunch", f"c1 #{first['seq']} -\n  #{second['seq']}",
                   f"c1 #{first['seq']}-#{second['seq']}", f"c1 #{first['seq']} — #{second['seq']}"):
        asked["log"].write_text(f"- the morning's work, {record}\n", encoding="utf-8")
        assert sessions.uncited(found, roots) == [], record          # a range as the documents write it, wrapped or not


def test_a_number_after_a_dash_or_a_word_ends_a_range_only_with_its_own_mark(asked):
    """A range could end in a bare number after a dash set off by spaces, or after `to` or `through`. Prose that
    uses a dash as a separator then turned one citation into a range: `#12 — 2027 planning starts in January` cited
    #12 to #2027, and early in a session `#5 - 30 min call` cited #5 to #30, clearing prompts nothing was written
    about (a review, 2026-11-13). The end of a range carries its `#`, unless the dash is tight (`#12-40`)."""
    first, second = found = sessions.prompts("acme", "2026-10-30")
    roots, cite = [str(asked["kb"])], f"claude-code c1 #{first['seq']}"
    assert first["seq"] < second["seq"] < 10
    for record in (f"- Scope cut: {cite} — 2027 planning starts in January\n",
                   f"- {cite} - 30 min call with the team, plan agreed\n",
                   f"- {cite} – 40 items left on the list\n",
                   f"- the plan of {cite} went to 30 people\n",
                   f"- {cite} through 2027 the plan holds\n",
                   f"- {cite} to\n  30 people, as asked\n"):
        asked["log"].write_text(record, encoding="utf-8")
        assert sessions.uncited(found, roots) == [second], record


def test_sessions_prompts_names_each_one_no_record_cites_and_exits_1_while_any_is_open(asked, capsys):
    command = ["sessions", "prompts", "--workspace", "acme", "--date", "2026-10-30", "--records", str(asked["kb"])]
    assert cli.main(command) == 1
    out = capsys.readouterr().out.splitlines()
    first, second = sessions.prompts("acme", "2026-10-30")
    assert out[0].startswith(f"claude-code c1 --seq {first['seq']}  ") and "Please plan the release." in out[0]
    assert out[-1] == f"2 of 2 prompts on 2026-10-30 in acme are cited by no record under {asked['kb']}"   # and where it looked
    asked["log"].write_text(f"- planned the release: c1 #{first['seq']}\n", encoding="utf-8")
    assert cli.main(command) == 1
    out = capsys.readouterr().out.splitlines()
    assert len(out) == 2 and "Also draft the announcement." in out[0] and out[-1].startswith("1 of 2 prompts")
    asked["log"].write_text(f"- planned and drafted: c1 #{first['seq']}-{second['seq']}\n", encoding="utf-8")
    assert cli.main(command) == 0
    assert capsys.readouterr().out.strip() == f"all 2 prompts on 2026-10-30 in acme are cited by a record under {asked['kb']}"
    assert cli.main(command[:-2]) == 0                                       # with no records given it only lists
    assert len(capsys.readouterr().out.splitlines()) == 3
    assert cli.main(command + ["--json"]) == 0
    assert json.loads(capsys.readouterr().out) == {"workspace": "acme", "date": "2026-10-30", "prompts": 2, "open": [],
                                                   "records": [str(asked["kb"])]}
    assert cli.main(["sessions", "prompts", "--date", "2026-10-30"]) == 2    # a workspace must be named
    assert cli.main(["sessions", "prompts", "--workspace", "acme"]) == 0     # with no date: today
    assert capsys.readouterr().out.strip().startswith("0 prompts on 20")
    for other in ("20261030", "2026-W44-5", "2026-1-5", "30-10-2026", "2026-10-30 and more"):  # a day is written one way, on every Python
        assert cli.main(["sessions", "prompts", "--workspace", "acme", "--date", other]) == 2, other
        assert "YYYY-MM-DD" in capsys.readouterr().err


def test_a_citation_names_one_session_and_a_listing_of_what_is_open_cites_nothing(harness, tmp_path, capsys):
    """2026-11-12, a review: two sessions whose ids begin alike were both cleared by a citation of one of them in
    full, and the listing's own output, saved in a folder of records, cited every prompt it listed as open."""
    one, two = "01a11111-aaaa-4000-8000-000000000001", "01a11111-bbbb-4000-8000-000000000002"
    for name, text in ((one, "Plan the release."), (two, "Draft the notes.")):
        _jsonl(harness["claude"].with_name(f"{name}.jsonl"),
               [_typed({"cwd": harness["work"], "sessionId": name}, text, "2026-10-30T15:00:00.000Z")])
    sessions.export(0)
    kb = tmp_path / "kb"
    kb.mkdir()
    first, second = sessions.prompts("acme", "2026-10-30")
    (kb / "log.md").write_text(f"- planned (claude-code {one} #{first['seq']})\n", encoding="utf-8")
    assert sessions.uncited([first, second], [str(kb)]) == [second]              # the id in full names one session
    (kb / "log.md").write_text(f"- planned (claude-code 01a11111 #{first['seq']})\n", encoding="utf-8")
    assert sessions.uncited([first, second], [str(kb)]) == [first, second]       # eight characters two sessions share name neither
    command = ["sessions", "prompts", "--workspace", "acme", "--date", "2026-10-30", "--records", str(kb)]
    assert cli.main(command) == 1
    names = [" ".join(line.split()[:4]) for line in capsys.readouterr().out.splitlines()[:2]]
    assert names == [f"claude-code 01a11111-a --seq {first['seq']}", f"claude-code 01a11111-b --seq {second['seq']}"]   # as much of each id as tells them apart
    assert cli.main(["sessions", "show", "01a11111-b", "--seq", str(second["seq"])]) == 0 and "Draft the notes." in capsys.readouterr().out
    (kb / "log.md").write_text("".join(f"- done ({n})\n" for n in names), encoding="utf-8")
    assert cli.main(command) == 1 and "2 of 2 prompts" in capsys.readouterr().out   # the listing's name for a prompt cites nothing,
    (kb / "log.md").write_text("".join(f"- done ({_cited(n)})\n" for n in names), encoding="utf-8")
    assert cli.main(command) == 0                                                # and the citation written from it is read
    (kb / "log.md").unlink()
    capsys.readouterr()
    assert cli.main(command + ["--json"]) == 1
    (kb / "open.json").write_text(capsys.readouterr().out, encoding="utf-8")     # the listing itself, saved among the records
    assert cli.main(command) == 1
    listing = capsys.readouterr().out
    assert "2 of 2 prompts" in listing
    (kb / "open.json").unlink()
    (kb / "open.md").write_text(listing, encoding="utf-8")                        # and as it is printed
    assert cli.main(command) == 1 and "2 of 2 prompts" in capsys.readouterr().out


def test_the_instructions_cite_a_session_as_the_listing_prints_it(harness, tmp_path, capsys):
    """2026-11-12, a second review: the binding rule still said to cite a session by eight characters. Followed for
    two sessions that begin alike, neither citation counted and `show` found two sessions. The listing prints as
    much of each id as names it alone, and the instructions say to write that."""
    ids = ["01a11111-aaaa-4000-8000-000000000001", "01a11111-aaab-4000-8000-000000000002",      # alike for twelve characters,
           "01a11111-bbbb-4000-8000-000000000003"]                                              # and for eight
    for name in ids:
        _jsonl(harness["claude"].with_name(f"{name}.jsonl"),
               [_typed({"cwd": harness["work"], "sessionId": name}, f"Plan {name[9:13]}.", "2026-10-30T15:00:00.000Z")])
    elsewhere = "01a11111-bbbc-4000-8000-000000000004"                  # a session of no workspace, so not listed, that begins like the third
    _jsonl(harness["claude"].with_name(f"{elsewhere}.jsonl"),
           [_typed({"cwd": str(tmp_path), "sessionId": elsewhere}, "Something else.", "2026-10-30T15:00:00.000Z")])
    sub = harness["claude"].parent / ids[0] / "subagents" / "agent-a1.jsonl"   # a sub-agent's id begins with its parent's whole id
    _jsonl(sub, [{"type": "user", "isSidechain": True, "cwd": harness["work"], "timestamp": "2026-10-30T15:00:00Z",
                  "message": {"role": "user", "content": "Check the script."}}])
    sessions.export(0)
    kb = tmp_path / "kb"
    kb.mkdir()
    found = sessions.prompts("acme", "2026-10-30")
    assert sorted(p["session"] for p in found) == ids
    command = ["sessions", "prompts", "--workspace", "acme", "--date", "2026-10-30", "--records", str(kb)]
    assert cli.main(command) == 1
    listed = [" ".join(line.split()[:4]) for line in capsys.readouterr().out.splitlines()[:3]]
    cites = [_cited(name) for name in listed]
    names = sorted(cite.split()[1] for cite in cites)
    assert names == ["01a11111-aaaa", "01a11111-aaab", "01a11111-bbbb"]                       # no more of an id than it takes
    assert all([s for s in ids if s.startswith(name)] == [s] for name, s in zip(names, ids))   # each names one listed session,
    for name in listed:                                                # and what the listing prints after the harness is what `show` takes
        assert cli.main(["sessions", "show", *name.split()[1:]]) == 0
        assert f"user: Plan {name.split()[1][9:13]}." in capsys.readouterr().out
    (kb / "log.md").write_text("".join(f"- planned ({cite})\n" for cite in cites), encoding="utf-8")
    assert cli.main(command) == 0 and "all 3 prompts" in capsys.readouterr().out               # cited as printed, each counts
    (kb / "log.md").write_text("".join(f"- planned (claude-code {name[:8]} #{cite.split('#')[1]})\n" for cite, name in zip(cites, names)),
                               encoding="utf-8")
    assert cli.main(command) == 1 and "3 of 3 prompts" in capsys.readouterr().out               # by eight characters, none does,
    assert cli.main(["sessions", "show", "01a11111", "--seq", "0"]) == 1 and "sessions match '01a11111'" in capsys.readouterr().err
    root = Path(__file__).resolve().parents[1]
    told = {p.relative_to(root).as_posix(): p.read_text(encoding="utf-8") for folder in ("skills", "docs") for p in (root / folder).rglob("*.md")}
    assert [name for name, text in told.items() if "session8" in text] == []                   # so no instruction asks for eight
    rule = next(line for line in told["skills/synthesis-context-lifecycle/SKILL.md"].splitlines() if line.startswith("15. "))
    citing = told["skills/synthesis-context-lifecycle/references/session-transcripts.md"].split("## Reading and citing")[1].split("\n## ")[0]
    for said in (rule, " ".join(citing.split())):
        assert "`<harness> <session> #<seq>`" in said and "eight characters, or more where two" in said
        assert "sessions show <session> --seq <n>" in said
    assert "first eight characters name" not in " ".join(citing.split())


def test_recent_search_and_resume_name_a_session_as_the_listing_does(harness, tmp_path, capsys):
    """The record behind a decision or a quote is found with `recent`, `search` or `resume` before it is cited. Each
    printed eight characters of a session's id whoever else began with them: one name for two sessions, and for a
    sub-agent its parent's name, under which `show` opens the parent's record."""
    one, two = "01a11111-aaaa-4000-8000-000000000001", "01a11111-bbbb-4000-8000-000000000002"
    for name in (one, two):
        _jsonl(harness["claude"].with_name(f"{name}.jsonl"), _claude_rows(harness["work"]))
    base = {"cwd": harness["work"], "isSidechain": True, "timestamp": "2026-10-30T10:00:00Z"}
    _jsonl(harness["claude"].parent / one / "subagents" / "agent-a1.jsonl", [
        {**base, "type": "user", "message": {"role": "user", "content": "Check the script."}},
        {**base, "type": "assistant", "message": {"model": "claude-opus-5-5", "content": [{"type": "text", "text": "The script is sound."}]}}])
    kb = tmp_path / "kb"
    (kb / "projects" / "alpha").mkdir(parents=True)
    (kb / "projects" / "alpha" / "CONTEXT.md").write_text("**Phase:** build\n**Status:** active\n", encoding="utf-8")
    resumed = project.resume(str(kb / "projects" / "alpha"), "S-new")                        # exports first
    assert cli.main(["sessions", "recent", "--workspace", "acme", "--limit", "9"]) == 0
    recent = capsys.readouterr().out
    assert cli.main(["sessions", "search", "release|script", "--workspace", "acme", "--kinds", "user,brief,assistant"]) == 0
    searched = capsys.readouterr().out
    assert "Please plan the release." in resumed and "The script is sound." in recent and "Check the script." in searched
    for shown in (resumed, recent, searched):
        named = re.findall(r"\[[\w-]+ (\S+)\] #(\d+) \S+ [a-z]+(?: \([^)]*\))?: (.*)", shown)
        assert len(named) >= 2 and len({name for name, _, _ in named}) >= 2
        for name, seq, said in named:                                                        # the name printed opens the record printed
            assert [m["session"] for m in sessions.find(name)] in ([one], [two], [f"{one}-agent-a1"]), name
            assert sessions.records(sessions.find(name)[0]["folder"])[int(seq)]["text"] == said
    assert {name for name, _, _ in re.findall(r"\[[\w-]+ (\S+)\] #(\d+) \S+ [a-z]+(?: \([^)]*\))?: (.*)", searched)} == {
        "01a11111-a", "01a11111-b", f"{one}-agent-a1"}                                       # a sub-agent by its whole id


def _cited(name: str) -> str:
    """The citation of the prompt the listing names `<harness> <session> --seq <n>`: `<harness> <session> #<n>`."""
    return name.replace(" --seq ", " #")


def _listed(capsys, *words) -> str:
    """What `synthesis sessions prompts` prints for acme on 2026-10-30 with these words."""
    capsys.readouterr()
    cli.main(["sessions", "prompts", "--workspace", "acme", "--date", "2026-10-30", *words])
    return capsys.readouterr().out


def test_the_listing_saved_among_the_records_cites_nothing_in_any_form(asked, capsys):
    """2026-11-12, a second review: saved without `--records`, or with its JSON answer pretty-printed, the listing
    cited every prompt it listed and the day closed clean. Two more reviews each found further layouts that did,
    past every rule that tried to know the listing by its shape. The listing, its answer and the refusal now name
    a prompt as `<harness> <session> --seq <n>`, which is no citation: however they are kept, they cite nothing."""
    found, kb = sessions.prompts("acme", "2026-10-30"), str(asked["kb"])
    cites = [f"claude-code c1 --seq {p['seq']}" for p in found]                      # the listing's name for each: no citation
    printed, answer = _listed(capsys), json.loads(_listed(capsys, "--records", kb, "--json"))
    assert all(cite in printed for cite in cites) and answer["open"] == cites
    lines = printed.splitlines()[:-1]                                                # without the line that counts
    forms = {
        "printed.txt": printed,                                                      # every prompt of the day, as printed
        "open.txt": _listed(capsys, "--records", kb),                                # those no record cites, as printed
        "narrow.md": _listed(capsys, "--width", "9"),                                # each prompt cut short,
        "whole.md": _listed(capsys, "--width", "0"),                                 # and whole
        "quoted.md": "Still open at five:\n\n" + "".join(f"> {line}\n" for line in lines),      # pasted into a record as a quote,
        "listed.md": "".join(f"  - {line}\n" for line in lines) + "\r\n".join(lines) + "\r\n",  # as a list, and with another editor's line ends
        "open.json": json.dumps(answer),                                             # the JSON answer on one line,
        "pretty.json": json.dumps(answer, indent=2),                                 # pretty-printed,
        "sorted.json": json.dumps(answer, sort_keys=True, separators=(",", ":")),    # as `jq -cS` writes it,
        "log.jsonl": json.dumps({"ran": "synthesis sessions prompts", "answer": answer}) + "\n",   # inside a line of a log,
        "fenced.md": "The day-end's answer:\n\n```json\n" + json.dumps(answer, indent=4) + "\n```\n",   # and in a record's fenced block
        "string.json": json.dumps({"ran": "synthesis sessions prompts", "printed": printed}),       # what it printed, kept as one string,
        "string.jsonl": json.dumps({"tool": "Bash", "output": _listed(capsys, "--records", kb)}) + "\n",  # in a line of a log,
        "pretty-string.json": json.dumps({"day": "2026-10-30", "listing": printed}, indent=2, ensure_ascii=False),  # pretty-printed,
        "string.yaml": "ran: synthesis sessions prompts\nprinted: " + json.dumps(printed) + "\n",     # and as YAML writes a quoted string
    }
    parts = [line.split("  ", 2) for line in lines]                                  # each line's citation, minute and words
    assert all(len(p) == 3 and p[0] in cites for p in parts)
    forms.update({  # 2026-11-13, a third review: the listing made into a checklist closed the day clean
        "boxes.md": "## Open prompts to work through\n\n" + "".join(f"- [ ] {line}\n" for line in lines),
        "ticked.md": "".join(f"- [x] {line}\n" for line in lines) + "".join(f"1. [X] {line}\n" for line in lines),
        "backticks.md": "".join(f"- `{cite}`  {at}  {words}\n" for cite, at, words in parts),
        "whole-in-backticks.md": "".join(f"- `{line}`\n" for line in lines),
        "bold.md": "".join(f"* **{cite}**  {at}  {words}\n" for cite, at, words in parts),
        "table.md": "| prompt | at | first words |\n|---|---|---|\n" + "".join(f"| {cite} | {at} | {words} |\n" for cite, at, words in parts),
        "quoted-boxes.md": "".join(f"> - [ ] `{cite}` {at} {words}\n" for cite, at, words in parts),
        # the JSON answer kept as a string, which the answer's own removal ran too early to see
        "answer-string.jsonl": json.dumps({"cmd": "synthesis sessions prompts --json", "out": json.dumps(answer)}) + "\n",
        "answer-string-fenced.md": "```\n" + json.dumps({"out": json.dumps(answer)}) + "\n```\n",
        "answer-string.yaml": "out: " + json.dumps(json.dumps(answer, indent=2)) + "\n",
        # what is open, alone: the answer's `open` list as `jq` writes it, and the refusal retyped as data
        "open-list.json": json.dumps(answer["open"]),
        "open-list-pretty.json": json.dumps(answer["open"], indent=2),
        "open-lines.jsonl": "".join(json.dumps(cite) + "\n" for cite in cites),
        "open-raw.txt": "".join(f"{cite}\n" for cite in cites),
        "open-fenced.md": "Open after the day-end:\n\n```json\n" + json.dumps(answer["open"], indent=2) + "\n```\n",
        "open-pasted.md": "Open after the day-end:\n\n" + json.dumps(answer["open"]) + "\n",
        "open.yaml": "open:\n" + "".join(f"  - {cite}\n" for cite in cites),
        "open-quoted.yaml": "day: 2026-10-30\nopen:\n" + "".join(f'  - "{cite}"\n' for cite in cites),
        "open-flow.yaml": "open: [" + ", ".join(cites) + "]\n",
        "open-keys.yaml": "".join(f"prompt{n}: {cite}\n" for n, cite in enumerate(cites)),
        "open-maps.yaml": "".join(f"- open: {cite}\n  day: 2026-10-30\n" for cite in cites),
        "open-string.jsonl": json.dumps({"tool": "Bash", "output": "".join(f"{cite}\n" for cite in cites)}) + "\n",
        "open-beside-words.json": json.dumps({"ran": "the day-end record", "refused": True, "open": answer["open"]}),
        "open-beside-words.yaml": "ran: the day-end record\nopen:\n" + "".join(f"  - {cite}\n" for cite in cites) + "refused: true\n",
    })
    forms.update({  # 2026-11-13, a fourth review: three of these recorded a clean close end to end
        "reworded-head.md": "Day-end refused a clean close, 2 open:\n" + "".join(f"  {cite}\n" for cite in cites),
        "bold-head.md": "**Open:**\n" + "".join(f"{cite}\n" for cite in cites),
        "headings.md": "## To work through\n\n" + "".join(f"### {line}\n" for line in lines),
        "bare-headings.md": "".join(f"### {cite}\n" for cite in cites),
        "no-minute.md": "".join(f"- `{cite}` {words}\n" for cite, at, words in parts),
        "minute-first.md": "| at | prompt | first words |\n|---|---|---|\n" + "".join(f"| {at} | {cite} | {words} |\n" for cite, at, words in parts),
        "quoted-words.md": "".join(f'- {cite}: "{words}"\n' for cite, at, words in parts),
        "dashes.md": "".join(f"{cite} \u2014 ({at}) \u2014 {words}\n" for cite, at, words in parts),
        "cut-short.md": "".join(f"- {cite} {words[:9]}\u2026\n" for cite, at, words in parts),
        "then-a-line.md": "Still open:\n" + "".join(f"- {cite}\n" for cite in cites) + "Back to these tomorrow.\n",
        "spaced-key.yaml": "still open: [" + ", ".join(cites) + "]\nopen prompts: " + cites[0] + "\n",
        "commented.yaml": "open:\n" + "".join(f"  # - {cite}\n" for cite in cites),
        "repr.md": repr(answer) + "\n",
        "twice-wrapped.jsonl": json.dumps({"out": json.dumps({"inner": json.dumps(answer["open"])})}) + "\n",
        "sentence.md": f"- Day-end refused a clean close: {cites[0]} and {cites[1]} are cited by no record.\n",
    })
    command = ["sessions", "prompts", "--workspace", "acme", "--date", "2026-10-30", "--records", kb]
    wrong = []
    for name, text in forms.items():
        saved = asked["kb"] / "projects" / "alpha" / name
        saved.write_text(text, encoding="utf-8")
        if sessions.uncited(found, [kb]) != found or cli.main(command) != 1:
            wrong.append(name)
        saved.unlink()
    capsys.readouterr()
    assert wrong == []


def test_at_width_0_the_listing_prints_each_prompt_whole(harness, capsys):
    """`--width` says 0 is all of it, and for the listing it was none of it: a line with no words of the prompt."""
    asked = "Draft the announcement. " + "It goes to every list we keep. " * 30 + "Do not send it before Friday."
    _jsonl(harness["claude"], [_typed({"cwd": harness["work"], "sessionId": "c1"}, asked, "2026-10-30T15:00:00.000Z")])
    command = ["sessions", "prompts", "--workspace", "acme", "--date", "2026-10-30"]
    assert cli.main(command) == 0
    assert capsys.readouterr().out.splitlines()[0].endswith(" ".join(asked.split())[:600])      # cut at 600, as before
    assert cli.main(command + ["--width", "0"]) == 0
    assert capsys.readouterr().out.splitlines()[0].endswith("Do not send it before Friday.")


def _day_end(asked, tmp_path, records=None):
    """A day-end record for acme on 2026-10-30 that checks its prompts against the records, run as the ritual runs
    it, with this checkout's own `synthesis` on the PATH. Returns the function that records and the ritual log.
    `records` is how the workspace's config writes its record folders, where that is not the folder's own path."""
    import sys
    root, state = Path(__file__).resolve().parents[1], tmp_path / "rituals"
    command = tmp_path / "bin" / "synthesis"
    command.parent.mkdir()
    command.write_text(f"#!{sys.executable}\nimport sys\nsys.path.insert(0, {str(root)!r})\nfrom synthesis import cli\n"
                       "sys.exit(cli.main(sys.argv[1:]))\n", encoding="utf-8")
    command.chmod(0o755)
    state.mkdir()
    (state / "config.json").write_text(json.dumps({"workspaces": {"acme": {
        "plans_dirs": [], "prompt_reconcile": {"records": records or [str(asked["kb"])]}}}}), encoding="utf-8")
    env = {**os.environ, "RITUAL_STATE_DIR": str(state), "PATH": f"{command.parent}{os.pathsep}{os.environ['PATH']}"}

    def record() -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(root / "skills" / "synthesis-daily-rituals" / "scripts" / "ritual_state.py"),
                               "record", "--direction", "day-end", "--workspace", "acme", "--date", "2026-10-30"],
                              capture_output=True, text=True, env=env)
    return record, state / "history.jsonl"


def test_the_day_ends_own_refusal_saved_among_the_records_cites_nothing(asked, tmp_path):
    """The day-end record lists what is open when it refuses a clean close. Pasted into the session log, that list is
    the listing over again: it records nothing of what was asked, and the day still does not close clean."""
    record, history = _day_end(asked, tmp_path)
    first, second = sessions.prompts("acme", "2026-10-30")
    refused = record()
    assert refused.returncode and "2 of 2 prompts typed on 2026-10-30 are cited by no record" in refused.stderr
    listed = f"  claude-code c1 --seq {first['seq']}\n  claude-code c1 --seq {second['seq']}\n"
    assert listed in refused.stderr and f"under {asked['kb']}" in refused.stderr          # what is open, and where it looked
    assert "`<harness> <session> #<n>`" in refused.stderr and "sessions show <session> --seq <n>" in refused.stderr
    asked["log"].write_text(f"## 2026-10-30 day-end\n\nThe record refused a clean close:\n\n{refused.stderr}\n", encoding="utf-8")
    again = record()
    assert again.returncode and "2 of 2 prompts typed on 2026-10-30" in again.stderr and not history.exists()
    for kept in ("".join(f"> {line}\n" for line in refused.stderr.splitlines()),                 # quoted,
                 "Day-end refused a clean close, 2 open:\n" + listed,                           # under words of the agent's own,
                 "**Open:**\n" + listed.replace("  ", ""),
                 "".join(f"- [ ] `{line.strip()}`\n" for line in listed.splitlines())):          # and as a checklist
        asked["log"].write_text(kept, encoding="utf-8")
        assert record().returncode and not history.exists(), kept


def test_a_record_in_the_same_file_as_the_listing_still_cites(asked, capsys):
    """2026-11-12, a second review: a session log that held the printed listing and, after it, a decision with its
    citation had every citation in it ignored, so a prompt the log accounted for stayed open. Only the listing's
    own lines, or its JSON answer, are set aside."""
    first, second = found = sessions.prompts("acme", "2026-10-30")
    kb = str(asked["kb"])
    listing, answer = _listed(capsys, "--records", kb), _listed(capsys, "--records", kb, "--json")
    decision = f"- 10:00 decided to ship on Friday; the plan is in REFERENCE.md (claude-code c1 #{first['seq']})\n"
    asked["log"].write_text(decision, encoding="utf-8")
    assert sessions.uncited(found, [kb]) == [second]                 # the control: the record alone accounts for the first,
    asked["log"].write_text(listing, encoding="utf-8")
    assert "2 of 2 prompts" in listing and sessions.uncited(found, [kb]) == found     # and the listing alone for neither
    mixed = {
        "the listing, then the record": listing + "\n" + decision,
        "the record, then the listing": decision + "\n" + listing,
        "every prompt of the day as printed, then the record": _listed(capsys) + "\n" + decision,
        "the JSON answer in a fenced block, then the record": "```json\n" + json.dumps(json.loads(answer), indent=2) + "\n```\n\n" + decision,
        "the record, then the JSON answer": decision + "\n" + answer,
    }
    command = ["sessions", "prompts", "--workspace", "acme", "--date", "2026-10-30", "--records", kb]
    wrong = []
    for name, text in mixed.items():
        asked["log"].write_text("## 2026-10-30\n\n" + text, encoding="utf-8")
        if sessions.uncited(found, [kb]) != [second] or cli.main(command) != 1 or "1 of 2 prompts" not in capsys.readouterr().out:
            wrong.append(name)
    assert wrong == []
    asked["log"].unlink()                                            # a log of objects: the answer on one line, a record on the next
    (asked["kb"] / "projects" / "alpha" / "day.jsonl").write_text(answer.strip() + "\n" + json.dumps(
        {"decided": "the announcement waits for Friday", "cites": [f"claude-code c1 #{second['seq']}"]}) + "\n", encoding="utf-8")
    assert sessions.uncited(found, [kb]) == [first]


def test_a_citation_the_principal_typed_is_not_one_in_the_listing(harness, tmp_path, capsys):
    """The listing prints each prompt's first words, and a prompt may itself cite another: one of today's, one of
    another day's (a review, 2026-11-13: today's listing, saved, closed yesterday's prompt at a catch-up), or one
    hidden in a string that carries an escape, which the reading of a record opens. In a line of the listing every
    number stands apart from its `#`, so no reading makes a citation of it; `show` prints the prompt as typed."""
    base = {"cwd": harness["work"], "sessionId": "c1"}
    _jsonl(harness["claude"], [_typed(base, "Plan the release.", "2026-10-29T15:00:00.000Z"),
                               _typed(base, "Draft the announcement.", "2026-10-30T15:00:00.000Z")])
    sessions.export(0)
    before, first = sessions.prompts("acme", "2026-10-29")[0], sessions.prompts("acme", "2026-10-30")[0]
    typed = [f"Do claude-code c1 #{first['seq']} again, and c1 #{first['seq']}-{first['seq'] + 1}; see PR #291.",
             f"Yesterday in c1 #{before['seq']} I asked for the plan.",
             'Read this: {"note": "see c1\\n#%d and c1\\u0020\\u0023%d"}' % (first["seq"], before["seq"])]
    _jsonl(harness["claude"], [_typed(base, text, f"2026-10-30T15:0{n + 5}:00.000Z") for n, text in enumerate(typed)])
    kb = tmp_path / "kb"
    kb.mkdir()
    command = ["sessions", "prompts", "--workspace", "acme", "--records", str(kb), "--date"]
    assert cli.main(command + ["2026-10-30"]) == 1
    listing = capsys.readouterr().out
    assert "4 of 4 prompts" in listing and "see PR # 291" in listing and not re.search(r"#\d", listing)
    kept = {"open.md": listing, "open.txt": listing, "quoted.md": "".join(f"> {line}\n" for line in listing.splitlines()),
            "open.json": json.dumps({"listing": listing}), "list.md": "".join(f"- [ ] {line}\n" for line in listing.splitlines()),
            "joined.md": " ".join(listing.split()) + "\n"}
    for name, text in kept.items():
        (kb / name).write_text(text, encoding="utf-8")
        assert cli.main(command + ["2026-10-30"]) == 1 and "4 of 4 prompts" in capsys.readouterr().out, name
        assert cli.main(command + ["2026-10-29"]) == 1 and "1 of 1 prompts" in capsys.readouterr().out, name   # nor yesterday's
        (kb / name).unlink()
    for prompt, text in zip(sessions.prompts("acme", "2026-10-30")[1:], typed):
        assert cli.main(["sessions", "show", "c1", "--seq", str(prompt["seq"])]) == 0 and text in capsys.readouterr().out


def test_what_show_prints_makes_no_citation_with_the_line_before_it(harness, tmp_path, capsys):
    """Each line `show` printed began with `#<seq>`, so a session's id at the end of the line above made a citation
    the conversation never held: a prompt that ended with another session's id closed that session's next prompt,
    and the command itself, pasted above its output, closed the first (a review, 2026-11-13). Every line `show`
    prints begins with the session, as `recent` and `search` do."""
    one, two = "5f0c9e2a-aaaa-4000-8000-000000000001", "7d41b6e3-bbbb-4000-8000-000000000002"
    for name, texts in ((one, ["Start here.", f"Pick this up where we left it in {two[:8]}", "And then stop."]),
                        (two, ["First of the other.", "Second.", "Third."])):
        _jsonl(harness["claude"].with_name(f"{name}.jsonl"),
               [_typed({"cwd": harness["work"], "sessionId": name}, text, f"2026-10-30T15:0{n}:00.000Z") for n, text in enumerate(texts)])
    sessions.export(0)
    found = sessions.prompts("acme", "2026-10-30")
    kb = tmp_path / "kb"
    kb.mkdir()
    for words in (["show", one[:8]], ["show", one], ["show", two[:8], "--kinds", "user"], ["show", one[:8], "--width", "0"],
                  ["show", two[:8], "--seq", "1"]):
        assert cli.main(["sessions", *words]) == 0
        shown = capsys.readouterr().out
        assert all(re.match(r"\[claude-code \S+\] #\d+ ", line) for line in shown.splitlines() if re.match(r"\[|#", line)), words
        for name, text in {"shown.md": shown, "echoed.md": f"$ synthesis sessions {' '.join(words)}\n{shown}",
                           "fenced.md": f"```\n$ synthesis sessions {' '.join(words)}\n{shown}```\n",
                           "joined.txt": " ".join(shown.split())}.items():
            (kb / name).write_text(text, encoding="utf-8")
            assert sessions.uncited(found, [str(kb)]) == found, (words, name)
            (kb / name).unlink()


def test_a_torn_line_of_json_is_read_in_time_that_follows_its_length(asked):
    """A string left open at the end of a torn line, with escaped quotes after it, was read again from every one of
    them: 40 KB took two and a half seconds, a quarter of a megabyte more than half a minute, and the day-end
    record waits on the listing with no limit (a review, 2026-11-13)."""
    import time
    first, second = found = sessions.prompts("acme", "2026-10-30")
    cite = f"claude-code c1 #{first['seq']}"
    torn = {"torn.jsonl": '{"at": "10:00", "payload": "{' + '\\"k\\": 1, ' * 60000,
            "open.md": f"- planned ({cite}); the log said payload=\"" + '\\"' * 200000 + "\n",
            "many.txt": ('"' + "\\" * 3 + "x" * 40 + "\n") * 20000 + f"planned: {cite}\n"}
    for name, text in torn.items():
        saved = asked["kb"] / "projects" / "alpha" / name
        saved.write_text(text, encoding="utf-8")
        start = time.monotonic()
        left = sessions.uncited(found, [str(asked["kb"])])
        assert time.monotonic() - start < 2, name
        assert left == (found if name == "torn.jsonl" else [second]), name
        saved.unlink()


def test_an_option_before_the_session_is_read(asked, capsys):
    """`synthesis sessions show --json <id>` was refused as an argument too many: with an option first, the session
    had already been taken as left out (noted by a review, 2026-11-13)."""
    assert cli.main(["sessions", "show", "--json", "c1"]) == 0
    shown = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert shown and [rec["seq"] for rec in shown] == list(range(len(shown)))
    assert cli.main(["sessions", "show", "--seq", "0", "c1"]) == 0 and "#0 " in capsys.readouterr().out
    for wrong in (["sessions", "show", "--json", "c1", "c2"], ["sessions", "show", "--no-such-option", "c1"]):
        with pytest.raises(SystemExit):
            cli.main(wrong)
    capsys.readouterr()


def test_without_records_the_json_answer_says_what_is_listed_and_nothing_of_what_is_open(asked, capsys):
    """`--json` without `--records` answered `"open": []` beside two prompts, which reads as nothing open (a review,
    2026-11-13). Nothing was held against any record, so the answer has no `open`: it lists."""
    found = sessions.prompts("acme", "2026-10-30")
    assert cli.main(["sessions", "prompts", "--workspace", "acme", "--date", "2026-10-30", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == {"workspace": "acme", "date": "2026-10-30", "prompts": 2, "records": [],
                                                   "listed": [f"claude-code c1 --seq {p['seq']}" for p in found]}


def test_a_config_or_a_tree_the_reading_cannot_take_is_said_in_a_line(asked, write_config, tmp_path, monkeypatch, capsys):
    command = ["sessions", "prompts", "--workspace", "acme", "--date", "2026-10-30", "--records", str(asked["kb"])]
    write_config({"workspace_roots": [str(tmp_path / "workspaces" / "*")], "sessions_repos": ["not", "a", "mapping"]})
    assert cli.main(command) == 1 and "2 of 2 prompts" in capsys.readouterr().out      # sessions repos that are no mapping name none

    walk = os.walk

    def deep(top, **more):  # as Python 3.9's walk does in a tree a thousand folders deep
        if top == str(asked["kb"]):
            raise RecursionError("maximum recursion depth exceeded")
        yield from walk(top, **more)
    monkeypatch.setattr(sessions.os, "walk", deep)
    assert cli.main(command) == 2
    said = capsys.readouterr()
    assert said.out == "" and "no record was checked" in said.err and str(asked["kb"]) in said.err


def test_a_citation_counts_wherever_it_is_written(asked):
    """No tool prints a citation for a prompt that is open: the listing, its answer and the refusal name one as
    `<session> --seq <n>`. A citation in a record was therefore written by whoever wrote the record, and it counts
    where it stands: in a sentence however it wraps, on a line of its own, in a table, a heading or a field of
    data. Rules that tried to tell a record from a list by its layout stood for two review rounds, and each round
    found ordinary layouts on the wrong side of them: a list that closed the day, a record that was refused."""
    first, second = found = sessions.prompts("acme", "2026-10-30")
    kb, one, two = str(asked["kb"]), f"claude-code c1 #{first['seq']}", f"claude-code c1 #{second['seq']}"
    written = {
        "log.md": f"- 10:00 planned the release ({one}) and drafted the announcement ({two}).\n",
        "wrapped.md": f"- 10:00 the release is planned; the decision is in REFERENCE.md under Scope\n  ({one}).\n"
                      f"- the announcement is drafted; see drafts (claude-code\n  c1 #{second['seq']}).\n",
        "split.md": f"- planned and drafted; both are in REFERENCE.md (claude-code c1\n  #{first['seq']} to\n  #{second['seq']})\n",
        "under.md": f"- 10:00 planned the release and drafted the announcement.\n  {one}\n  {two}\n",
        "entries.md": f"- 10:00 planned the release and drafted the announcement.\n  - {one}\n  - {two}\n",
        "headings.md": f"### {one}\nPlanned the release.\n\n### {two}\n\nDrafted the announcement.\n",
        "table.md": f"| prompt | what became of it |\n|---|---|\n| {one} | planned |\n| {two} | drafted |\n",
        "footnote.md": f"Planned the release[^1] and drafted the announcement[^2].\n\n[^1]: {one}\n[^2]: {two}\n",
        "LOG.MD": f"- planned and drafted ({one}, {two})\n",
        "notes.markdown": f"- planned and drafted ({one}, {two})\n",
        "notes.txt": f"planned and drafted: {one} and {two}\n",
        "entry.yaml": f"decided: the release is planned and the announcement drafted\ncites:\n  - {one}\n  # the second, asked later\n\n  - {two}\n",
        "block.yaml": f"decided: planned and drafted\ncites: |\n  {one}\n  {two}\n",
        "other-key.yml": f"decided: planned and drafted\nprompts answered: [{one}, {two}]\n",
        "entry.json": json.dumps({"decided": "planned and drafted", "cites": [one, two]}, indent=2),
        "shaped.json": json.dumps({"workspace": "acme", "date": "2026-10-30", "prompts": 2, "open": 0, "decided": "both", "cites": [one, two]}),
        "line.jsonl": json.dumps({"decided": "planned"}) + "\n" + json.dumps({"cites": one, "then": {"cites": [two, 3]}}) + "\n",
    }
    for name, text in written.items():
        saved = asked["kb"] / "projects" / "alpha" / name
        saved.write_text(text, encoding="utf-8")
        assert sessions.uncited(found, [kb]) == [], name
        saved.unlink()


def test_a_citation_kept_as_a_string_is_read_as_the_text_it_holds(asked):
    """A record kept as JSON holds its text as strings, and an encoder writes a dash that is not ASCII as an escape:
    `#3\\u20134` was read as #3 alone, so a range one entry covered left its other prompts open (noted by a review,
    2026-11-12). A string that carries an escape is read as the text it holds, in a `.json` file, a line of a log,
    a quoted YAML value or a line of JSON pasted into a text record."""
    first, second = found = sessions.prompts("acme", "2026-10-30")
    kb, cite = str(asked["kb"]), f"claude-code c1 #{first['seq']}\u2013{second['seq']}"
    for name, text in {
        "entry.json": json.dumps({"decided": "the release and its announcement, planned together", "cites": cite}),
        "entry.jsonl": json.dumps({"at": "10:00", "note": f"planned both ({cite})"}) + "\n",
        "entry.yaml": "decided: planned both\ncites: " + json.dumps(cite) + "\n",
        "wrapped.json": json.dumps({"note": f"planned the release and the announcement\n(claude-code c1 #{first['seq']} to\n#{second['seq']})"}),
        "pasted.md": "Kept from the log:\n\n```\n" + json.dumps({"note": f"planned both ({cite})"}) + "\n```\n",
    }.items():
        saved = asked["kb"] / "projects" / "alpha" / name
        saved.write_text(text, encoding="utf-8")
        assert "\\u2013" in text or "wrapped" in name, name  # the encoder did escape the dash
        assert sessions.uncited(found, [kb]) == [], name
        saved.unlink()
    saved = asked["kb"] / "projects" / "alpha" / "two.json"            # two strings stay two: no range runs from one into the next
    saved.write_text(json.dumps({"a": f"planned (claude-code c1 #{first['seq']} \u2013", "b": f"#{second['seq']} items"}), encoding="utf-8")
    assert sessions.uncited(found, [kb]) == [second]


def test_a_listing_line_cites_nothing_until_a_citation_is_written_on_it(asked, capsys):
    """An agent that works down the saved listing and writes what became of a prompt on its line has still cited
    nothing: the line names the prompt as `show` takes it. The citation is its own to write."""
    first, second = found = sessions.prompts("acme", "2026-10-30")
    one, two = _listed(capsys).splitlines()[:2]
    asked["log"].write_text(f"{one} -> planned; the plan is in REFERENCE.md\n{two}\n", encoding="utf-8")
    assert sessions.uncited(found, [str(asked["kb"])]) == found
    asked["log"].write_text(f"{one} -> planned; the plan is in REFERENCE.md ({_cited(one.split('  ')[0])})\n{two}\n", encoding="utf-8")
    assert sessions.uncited(found, [str(asked["kb"])]) == [second]


def test_a_citations_number_is_a_records_number(asked):
    """A record's number has at most nine digits. A longer run after a session's id is no citation: read as a
    number, one of more than 4,300 digits raised out of the listing on Python 3.11 and later (a review,
    2026-11-13), and one of ten cited a prompt by its first nine."""
    first, second = found = sessions.prompts("acme", "2026-10-30")
    for long in ("9" * 5000, f"{first['seq']}" + "0" * 9, f"{first['seq']}-" + "9" * 5000, f"{first['seq']} to #" + "9" * 12):
        asked["log"].write_text(f"- planned the release (claude-code c1 #{long})\n", encoding="utf-8")
        assert sessions.uncited(found, [str(asked["kb"])]) in (found, [second]), long[:20]
    asked["log"].write_text(f"- planned the release (claude-code c1 #{first['seq']}" + "0" * 9 + ")\n", encoding="utf-8")
    assert sessions.uncited(found, [str(asked["kb"])]) == found


@closed_to_us
def test_a_records_folder_that_cannot_be_read_is_named_and_nothing_is_listed(asked, tmp_path, capsys, monkeypatch):
    """A folder of records that is not there was walked as an empty one: every prompt stayed open, the day-end
    refused each day, and a citation written in the real folder was never read, with no word of why (a review,
    2026-11-13). A folder that cannot be read, or one inside it, is named, and the listing says nothing of what
    is open."""
    found, kb = sessions.prompts("acme", "2026-10-30"), asked["kb"]
    asked["log"].write_text("".join(f"- done (claude-code c1 #{p['seq']})\n" for p in found), encoding="utf-8")
    command = ["sessions", "prompts", "--workspace", "acme", "--date", "2026-10-30"]
    read, pipe = Path.read_text, kb / "pipe.md"
    monkeypatch.setattr(Path, "read_text", lambda self, *a, **k: read(self, *a, **k) if self != pipe else pytest.fail("a pipe was read"))
    assert cli.main(command + ["--records", str(kb)]) == 0                          # the control: read, it accounts for both
    capsys.readouterr()
    absent, a_file = kb / "recrods", asked["log"]
    for wrong in (absent, a_file):
        with pytest.raises(OSError):
            sessions.uncited(found, [str(kb), str(wrong)])
        for more in ([], ["--json"]):
            assert cli.main(command + ["--records", str(kb), "--records", str(wrong)] + more) == 2
            said = capsys.readouterr()
            assert str(wrong) in said.err and "no record" in said.err and said.out == "", (wrong, said)
    with _closed(kb / "projects" / "alpha" / "sessions"):                           # a folder inside it that may not be listed
        assert cli.main(command + ["--records", str(kb)]) == 2
        assert str(kb / "projects" / "alpha" / "sessions") in capsys.readouterr().err
    with _closed(asked["log"]):                                                     # and a record that may not be read
        assert cli.main(command + ["--records", str(kb)]) == 2
        assert str(asked["log"]) in capsys.readouterr().err
    (kb / "gone.md").symlink_to(kb / "nowhere.md")                                  # a link that leads nowhere is no record,
    (kb / "round.md").symlink_to(kb / "about.md")                                   # nor is one that leads back to itself,
    (kb / "about.md").symlink_to(kb / "round.md")
    os.mkfifo(kb / "pipe.md")                                                       # nor a pipe, which a read would wait on for ever
    assert cli.main(command + ["--records", str(kb)]) == 0
    capsys.readouterr()
    record, history = _day_end(asked, tmp_path, records=[str(absent)])              # and the day-end record says which
    refused = record()
    assert refused.returncode and str(absent) in refused.stderr and not history.exists()


def test_a_folder_gone_while_the_records_are_read_is_passed_over(asked, monkeypatch):
    """A folder removed between the moment the walk listed it and the moment it opened it is not there to hold a
    record. Only a folder that was named, or one that is there and may not be read, stops the listing."""
    found = sessions.prompts("acme", "2026-10-30")
    asked["log"].write_text("".join(f"- done (claude-code c1 #{p['seq']})\n" for p in found), encoding="utf-8")
    walk = os.walk

    def walked(top, onerror=None, **more):
        onerror(FileNotFoundError(2, "No such file or directory", os.path.join(top, "projects", "removed")))
        yield from walk(top, onerror=onerror, **more)
    monkeypatch.setattr(sessions.os, "walk", walked)
    assert sessions.uncited(found, [str(asked["kb"])]) == []


def test_a_day_with_no_prompts_reads_no_record_and_still_names_a_folder_that_is_not_there(asked, capsys):
    """With nothing typed there is nothing a record could cite, and the listing read every record of every age to
    find that out, stopping at one it could not read (a review, 2026-11-13). It reads none. A folder that is not
    there is still said, since it would be as wrong tomorrow."""
    old = asked["kb"] / "projects" / "alpha" / "long-ago.md"
    old.write_text("- something else\n", encoding="utf-8")
    command = ["sessions", "prompts", "--workspace", "acme", "--date", "2026-10-29"]
    with _closed(old):
        assert sessions.uncited([], [str(asked["kb"])]) == []
        assert cli.main(command + ["--records", str(asked["kb"])]) == 0
        assert capsys.readouterr().out.strip() == f"0 prompts on 2026-10-29 in acme, so nothing to cite under {asked['kb']}"
    assert cli.main(command + ["--records", str(asked["kb"] / "recrods")]) == 2
    assert str(asked["kb"] / "recrods") in capsys.readouterr().err


def test_session_transcripts_are_no_records(asked, tmp_path, write_config, capsys):
    """A sessions repo holds the conversations themselves: every citation an agent wrote, tried to write or talked
    about is in one. Under a folder of records it is passed over, and named as the folder of records it is refused."""
    first, second = found = sessions.prompts("acme", "2026-10-30")
    repo = asked["kb"] / "ai-sessions-acme"
    (repo / "2026-10" / "c1").mkdir(parents=True)
    (repo / "2026-10" / "c1" / "transcript-000.jsonl").write_text(
        json.dumps({"kind": "assistant", "text": f"I will cite it as claude-code c1 #{first['seq']} to #{second['seq']}."}) + "\n", encoding="utf-8")
    write_config({"workspace_roots": [str(tmp_path / "workspaces" / "*")], "sessions_repos": {"acme": str(repo)}})
    assert sessions.uncited(found, [str(asked["kb"])]) == found
    command = ["sessions", "prompts", "--workspace", "acme", "--date", "2026-10-30"]
    for named in (repo, repo / "2026-10"):
        assert cli.main(command + ["--records", str(named)]) == 2
        said = capsys.readouterr()
        assert str(named) in said.err and "session transcripts" in said.err and said.out == ""


def test_the_listing_names_a_prompt_by_what_opens_it(asked, capsys):
    """Each line of the listing names its prompt as `<harness> <session> --seq <n>`: what follows the harness is
    what `synthesis sessions show` takes. It is no citation, so no copy of the listing, of its JSON answer or of
    the refusal's list can account for a prompt."""
    found = sessions.prompts("acme", "2026-10-30")
    printed, answer = _listed(capsys), json.loads(_listed(capsys, "--records", str(asked["kb"]), "--json"))
    names = [line.split("  ")[0] for line in printed.splitlines()[:-1]]
    assert names == answer["open"] == [f"claude-code c1 --seq {p['seq']}" for p in found]
    ids = {str(p["session"]) for p in found}
    assert [c for c in sessions.CITED.findall(printed + json.dumps(answer)) if c[0] in ids] == []
    for name, prompt in zip(names, found):
        assert cli.main(["sessions", "show", *name.split()[1:]]) == 0
        assert prompt["text"] in capsys.readouterr().out
        assert [c[:2] for c in sessions.CITED.findall(_cited(name))] == [("c1", str(prompt["seq"]))]


def test_a_folder_reached_through_a_link_is_read_when_it_is_named_and_not_from_above(asked, tmp_path):
    """The walk follows no link to a folder: a link may lead out of the records, or back into them. A folder kept
    elsewhere and linked into the records is read by naming it."""
    first, second = found = sessions.prompts("acme", "2026-10-30")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "log.md").write_text(f"- planned the release (claude-code c1 #{first['seq']})\n", encoding="utf-8")
    (asked["kb"] / "linked").symlink_to(elsewhere, target_is_directory=True)
    assert sessions.uncited(found, [str(asked["kb"])]) == found
    assert sessions.uncited(found, [str(asked["kb"] / "linked")]) == [second]
    assert sessions.uncited(found, [str(asked["kb"]), str(elsewhere)]) == [second]


def test_a_record_after_the_pasted_refusal_closes_what_it_cites_and_no_more(asked, tmp_path):
    """The refusal pasted into the session log, then the entries an agent wrote under it: the day closes when they
    cite every prompt, and not while one of them is only in the pasted list."""
    record, history = _day_end(asked, tmp_path)
    first, second = sessions.prompts("acme", "2026-10-30")
    pasted = f"## 2026-10-30 day-end\n\nThe record refused a clean close:\n\n{record().stderr}\n"
    asked["log"].write_text(pasted + f"- planned the release (claude-code c1 #{first['seq']})\n", encoding="utf-8")
    left = record()
    assert left.returncode and "1 of 2 prompts typed on 2026-10-30 is cited by no record" in left.stderr
    assert f"  claude-code c1 --seq {second['seq']}\n" in left.stderr and f"c1 --seq {first['seq']}\n" not in left.stderr
    with asked["log"].open("a", encoding="utf-8") as log:
        log.write(f"- drafted the announcement, in drafts/announcement.md (claude-code c1 #{second['seq']})\n")
    done = record()
    assert done.returncode == 0 and "prompts: all 2 typed on 2026-10-30 are cited by a record" in done.stdout and history.exists()


def test_the_listing_names_each_records_folder_as_its_walk_reads_it(asked, tmp_path, monkeypatch, capsys):
    """A folder given through a link and its parent (`<link>/../kb`) was walked where the link leads and named with
    `..` taken out as written: the answer said the listing was held against a folder beside the link, one it never
    opened. The answer names each folder as the walk reads it, however it was given, and the day-end record takes
    that answer for the folder its config names."""
    first, second = sessions.prompts("acme", "2026-10-30")
    read, desk = os.path.realpath(asked["kb"]), tmp_path / "desk"
    (tmp_path / "sub").mkdir()
    (desk / "kb").mkdir(parents=True)                                  # what `..` taken out as written names: nothing reads it,
    (desk / "kb" / "log.md").write_text(f"- the whole day (claude-code c1 #{first['seq']}-{second['seq']})\n", encoding="utf-8")
    (desk / "link").symlink_to(tmp_path / "sub")                       # since the link leads beside the records themselves
    (desk / "records").symlink_to(asked["kb"])
    asked["log"].write_text(f"- planned the release (claude-code c1 #{first['seq']})\n", encoding="utf-8")
    monkeypatch.setenv("HOME", str(desk))
    monkeypatch.chdir(desk)
    through = str(desk / "link" / ".." / "kb")
    given = {"through a link and its parent": [through], "from the home folder": ["~/link/../kb"],
             "from the working folder": ["link/../kb"], "a link to the folder": [str(desk / "records")],
             "twice, written two ways": [through, str(asked["kb"])]}
    command = ["sessions", "prompts", "--workspace", "acme", "--date", "2026-10-30", "--json"]
    wrong = {}
    for name, folders in given.items():
        code = cli.main(command + [word for folder in folders for word in ("--records", folder)])
        answer = json.loads(capsys.readouterr().out)                   # the records it read hold one of the two prompts
        if (code, answer["records"], answer["open"]) != (1, [read] * len(folders), [f"claude-code c1 --seq {second['seq']}"]):
            wrong[name] = answer["records"]
    assert wrong == {}
    record, history = _day_end(asked, tmp_path, [through])            # the record asks about the folder its config names,
    left = record()
    assert left.returncode and "1 of 2 prompts typed on 2026-10-30 is cited by no record" in left.stderr, left.stderr
    with asked["log"].open("a", encoding="utf-8") as log:               # is answered about the folder that was read,
        log.write(f"- drafted the announcement (claude-code c1 #{second['seq']})\n")
    done = record()                                                    # and closes on what is written there
    assert done.returncode == 0 and "prompts: all 2 typed on 2026-10-30 are cited by a record" in done.stdout, done.stderr
    assert history.exists()


def test_a_records_folder_named_by_nothing_is_no_folder(asked, monkeypatch, capsys):
    """`--records ""`, the shape an unset shell variable leaves, was named in the answer as the working folder, which
    the walk never opened. It names no folder, also when the command runs inside the records: nothing is read for
    it, and like any folder that is not there it is said, with nothing listed (2026-11-13: until then every prompt
    was listed as open, as if the records had been read and held no citation)."""
    first, second = sessions.prompts("acme", "2026-10-30")
    asked["log"].write_text(f"- the whole day (claude-code c1 #{first['seq']}-{second['seq']})\n", encoding="utf-8")
    monkeypatch.chdir(asked["kb"])
    assert cli.main(["sessions", "prompts", "--workspace", "acme", "--date", "2026-10-30", "--records", "", "--json"]) == 2
    said = capsys.readouterr()
    assert said.out == "" and '"" cannot be read as records' in said.err and "no record was checked" in said.err
    assert cli.main(["sessions", "prompts", "--workspace", "acme", "--date", "2026-10-30", "--records", ".", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["records"] == [str(asked["kb"])]      # the working folder, when it is the one named


def test_the_listing_exports_first_and_stops_when_a_transcript_could_not_be_copied(asked, capsys, monkeypatch):
    """2026-11-12, a review: with an archive that could not be written the listing held no prompt, and the day
    closed clean. The listing brings the archive up to date itself, and says nothing was listed when it cannot."""
    with asked["claude"].open("a", encoding="utf-8") as native:
        native.write(json.dumps(_typed({"cwd": asked["work"], "sessionId": "c1"}, "A third thing.", "2026-10-30T16:00:00.000Z")) + "\n")
    command = ["sessions", "prompts", "--workspace", "acme", "--date", "2026-10-30"]
    assert cli.main(command) == 0 and "A third thing." in capsys.readouterr().out          # typed since the last export, and listed
    assert cli.main(command + ["--records", str(asked["kb"]), "--json"]) == 1
    assert json.loads(capsys.readouterr().out)["records"] == [str(asked["kb"])]              # and the answer says what it was held against

    def refused(*args, **kwargs):
        raise PermissionError("read-only")
    with asked["claude"].open("a", encoding="utf-8") as native:
        native.write(json.dumps(_typed({"cwd": asked["work"], "sessionId": "c1"}, "A fourth.", "2026-10-30T17:00:00.000Z")) + "\n")
    monkeypatch.setattr(sessions, "export_file", refused)
    assert cli.main(command) == 2
    said = capsys.readouterr()
    assert said.out == "" and "not exported" in said.err and "2026-10-30" in said.err


@closed_to_us
def test_an_archive_that_cannot_be_written_stops_the_listing_with_its_reason(asked, capsys):
    """With the lock beside the archive free and the archive itself not writable, each copy failed and then the stamp
    could not be left: the listing ended in a traceback in place of saying why nothing was listed."""
    with asked["claude"].open("a", encoding="utf-8") as native:
        native.write(json.dumps(_typed({"cwd": asked["work"], "sessionId": "c1"}, "A third thing.", "2026-10-30T16:00:00.000Z")) + "\n")
    command = ["sessions", "prompts", "--workspace", "acme", "--date", "2026-10-30"]
    folders = [sessions.root(), *(d for d in sessions.root().rglob("*") if d.is_dir())]
    for folder in folders:
        folder.chmod(0o555)
    try:
        assert cli.main(command) == 2
        said = capsys.readouterr()
        assert said.out == "" and "not exported" in said.err and "2026-10-30" in said.err
        report = sessions.export(2)                                    # and an export says so before anything else
        assert report[0].startswith("not exported: ") and "claude-code c1: not exported" in report[1]
    finally:
        for folder in folders:
            folder.chmod(0o755)
    assert cli.main(command) == 0 and "A third thing." in capsys.readouterr().out


@closed_to_us
def test_a_day_is_not_listed_while_a_transcript_that_may_hold_its_prompts_is_not_copied(asked, capsys):
    """2026-11-12, a second review: a transcript whose copy had failed lay outside the two days the listing exports.
    Its failure stayed in the stamp, the listing of that older day held none of its prompts and exited 0, and the
    day closed clean."""
    from datetime import datetime
    other = _jsonl(asked["claude"].with_name("c2.jsonl"),
                   [_typed({"cwd": asked["work"], "sessionId": "c2"}, "Book the venue.", "2026-10-30T15:30:00.000Z")])
    stamp = sessions.root() / ".state" / "export.json"
    command = ["sessions", "prompts", "--workspace", "acme", "--date", "2026-10-30"]
    that_day, day_before = datetime(2026, 10, 30, 16).timestamp(), datetime(2026, 10, 29, 12).timestamp()
    other.chmod(0o000)
    try:
        sessions.export(0)                                             # the hourly run cannot read it,
        assert json.loads(stamp.read_text())["failed"] == 1
        os.utime(other, (that_day, that_day))                          # and it was last written on the day asked about, days ago
        assert cli.main(command) == 2
        said = capsys.readouterr()
        assert said.out == "" and "claude-code c2: not exported" in said.err and "2026-10-30" in said.err
        assert cli.main(command + ["--records", str(asked["kb"]), "--json"]) == 2 and capsys.readouterr().out == ""
        assert cli.main(["sessions", "prompts", "--workspace", "elsewhere", "--date", "2026-10-30"]) == 2    # nothing says whose it is
        os.utime(other, (day_before, day_before))                      # last written before that day began, it holds nothing typed on it:
        capsys.readouterr()
        assert cli.main(command) == 0                                   # the day is listed,
        assert "2 prompts on 2026-10-30 in acme" in capsys.readouterr().out
        assert cli.main(command[:-1] + ["2026-10-29"]) == 2            # and the day before it is not
        assert "claude-code c2: not exported" in capsys.readouterr().err
    finally:
        other.chmod(0o644)
    os.utime(other, (that_day, that_day))
    sessions.export(0)                                                 # a later run of everything copies it,
    assert "failed" not in json.loads(stamp.read_text())
    assert cli.main(command) == 0 and "Book the venue." in capsys.readouterr().out          # and the day is listed with what it held


@closed_to_us
def test_a_transcript_that_cannot_hold_the_days_prompts_does_not_stop_the_listing(harness, tmp_path, monkeypatch, capsys):
    """What is not copied is weighed for the workspace and the day asked about. A transcript filed under another
    workspace holds nothing of this one's. One that is gone may have held anything written until a run found it
    gone, so it stops the listing of those days until the principal accepts the loss."""
    import types
    from datetime import date, timedelta
    beta = tmp_path / "workspaces" / "beta" / "repo"
    beta.mkdir(parents=True)
    _jsonl(harness["claude"], [_typed({"cwd": harness["work"], "sessionId": "c1"}, "Plan the release.", "2026-10-30T15:00:00.000Z")])
    theirs = _jsonl(harness["claude"].with_name("b1.jsonl"),
                    [_typed({"cwd": str(beta), "sessionId": "b1"}, "Order the parts.", "2026-10-30T15:00:00.000Z")])
    sessions.export(0)
    _jsonl(theirs, [_typed({"cwd": str(beta), "sessionId": "b1"}, "And the spares.", "2026-10-30T15:30:00.000Z")])
    theirs.chmod(0o000)                                                # what beta's session gained cannot be copied
    here, there = (["sessions", "prompts", "--workspace", name, "--date", "2026-10-30"] for name in ("acme", "beta"))
    try:
        assert cli.main(here) == 0 and "Plan the release." in capsys.readouterr().out      # which is nothing of acme's,
        assert cli.main(there) == 2                                                         # and may be something of beta's
        said = capsys.readouterr()
        assert said.out == "" and "claude-code b1: not exported" in said.err
    finally:
        theirs.chmod(0o644)
    theirs.unlink()                                                    # the harness removes it before a run copies the rest
    assert cli.main(there) == 2 and "claude-code b1: not exported" in capsys.readouterr().err
    sessions.export(0)                                                 # a run of everything finds it gone,
    assert cli.main(there) == 2 and "claude-code b1: not exported" in capsys.readouterr().err
    assert cli.main(here) == 0
    tomorrow = (date.today() + timedelta(days=1)).isoformat()         # and nothing typed after that can have been in it
    assert cli.main(there[:-1] + [tomorrow]) == 0 and f"0 prompts on {tomorrow} in beta" in capsys.readouterr().out
    monkeypatch.setattr("sys.stdin", types.SimpleNamespace(isatty=lambda: True))
    assert cli.main(["sessions", "export", "--lost", "b1"]) == 0      # the principal accepts the loss,
    capsys.readouterr()
    assert cli.main(there) == 0                                        # and the day lists what the archive holds of it
    listed = capsys.readouterr().out
    assert "Order the parts." in listed and "And the spares." not in listed and "1 prompts on 2026-10-30 in beta" in listed


@closed_to_us
def test_a_sub_agents_transcript_that_is_not_copied_does_not_stop_the_listing(harness, capsys):
    """A sub-agent is briefed by an agent, so its transcript holds nothing the principal typed. While it is not copied
    the stamp names it for the doctor, and the day is still listed. A thread nothing is known of may be anyone's."""
    _jsonl(harness["claude"], [_typed({"cwd": harness["work"], "sessionId": "c1"}, "Plan the release.", "2026-10-30T15:00:00.000Z")])
    sub = _jsonl(harness["claude"].parent / "c1" / "subagents" / "agent-a1.jsonl", [
        {"type": "user", "isSidechain": True, "cwd": harness["work"], "timestamp": "2026-10-30T15:00:05Z",
         "message": {"role": "user", "content": "Check the script."}}])
    spawned = _codex_child(harness, "01a1spwn-0000-7000-8000-000000000002",
                           {"thread_spawn": {"parent_thread_id": "01a1parent-0000"}}, "Survey the test suite.", "Done.")
    sessions.export_file("codex", spawned)                             # the archive knows this thread as a spawned agent's
    _jsonl(spawned, [{"type": "response_item", "timestamp": "2026-10-30T15:10:00Z", "payload": {
        "type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "And the rest."}]}}])
    command = ["sessions", "prompts", "--workspace", "acme", "--date", "2026-10-30"]
    for native in (sub, spawned):
        native.chmod(0o000)
    try:
        assert cli.main(command) == 0 and "Plan the release." in capsys.readouterr().out
        named = json.loads((sessions.root() / ".state" / "export.json").read_text())["uncopied"]
        assert sorted(named) == ["claude-code c1-agent-a1", "codex 01a1spwn-0000-7000-8000-000000000002"]
        unknown = _codex_child(harness, "01a1othr-0000-7000-8000-000000000003", {"thread_spawn": {}}, "Count the files.", "Nine.")
        unknown.chmod(0o000)                                           # never copied, so nothing says whose prompts it holds
        try:
            assert cli.main(command) == 2 and "codex 01a1othr-0000-7000-8000-000000000003: not exported" in capsys.readouterr().err
        finally:
            unknown.chmod(0o644)
    finally:
        for native in (sub, spawned):
            native.chmod(0o644)


def test_the_listing_of_an_older_day_copies_what_was_written_since_that_day_began(harness, capsys):
    """The listing brought the archive up to date for the last two days whichever day was asked about, so a transcript
    last written on an older day and not yet copied was not read for that day. The day is given as a date."""
    from datetime import datetime
    native = _jsonl(harness["claude"], [_typed({"cwd": harness["work"], "sessionId": "c1"}, "Plan the release.", "2026-10-30T15:00:00.000Z")])
    written = datetime(2026, 10, 30, 16).timestamp()
    os.utime(native, (written, written))
    command = ["sessions", "prompts", "--workspace", "acme", "--date"]
    assert cli.main(command + ["2026-10-30"]) == 0 and "Plan the release." in capsys.readouterr().out
    assert cli.main(command + ["2026-10-30T09:00", "--json"]) == 0                     # a time of that day is that day,
    assert json.loads(capsys.readouterr().out) == {"workspace": "acme", "date": "2026-10-30", "prompts": 1, "records": [],
                                                   "listed": ["claude-code c1 --seq 0"]}
    assert cli.main(command + ["tomorrow"]) == 2                                       # and what is no date lists nothing
    said = capsys.readouterr()
    assert said.out == "" and "tomorrow" in said.err


def test_an_export_that_finishes_says_when_and_a_busy_one_does_not(harness):
    _jsonl(harness["claude"], _claude_rows(harness["work"]))
    stamp = sessions.root() / ".state" / "export.json"
    assert not stamp.exists()
    sessions.export(0)
    first = json.loads(stamp.read_text())["exported"]
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d", first)
    assert sessions.export(0) == [] and json.loads(stamp.read_text())["exported"] >= first    # nothing new still counts as a run
    assert "scheduled" not in json.loads(stamp.read_text())           # a session's own export is not the schedule's
    assert cli.main(["sessions", "export", "--all", "--scheduled"]) == 0
    ran = json.loads(stamp.read_text())["scheduled"]
    assert ran == json.loads(stamp.read_text())["exported"]           # the schedule's command marks its own run,
    sessions.export(0)
    assert json.loads(stamp.read_text())["scheduled"] == ran          # and a session's export after it leaves the mark


@closed_to_us
def test_a_run_that_could_not_copy_a_transcript_stays_visible_until_a_run_copies_everything(harness, tmp_path):
    """2026-11-12: with every copy refused, the stamp still got a fresh time and the doctor answered ok."""
    from synthesis import doctor
    natives = [_jsonl(harness["claude"].with_name(f"{name}.jsonl"), _claude_rows(harness["work"])) for name in ("c1", "c2")]
    stamp, plist = sessions.root() / ".state" / "export.json", _scheduled(tmp_path)

    def doctors() -> tuple:
        found = doctor.check_sessions_export(plist, _its_own(stamp), run=lambda argv, **kw: subprocess.CompletedProcess(argv, 0, "", ""))
        return found.status, found.detail, json.loads(stamp.read_text())

    try:
        for native in natives:
            native.chmod(0o000)                                    # as when the job may not read a harness's files
        report = sessions.export(0)
        assert len(report) == 2 and all("not exported" in line and "Permission denied" in line for line in report)
        status, detail, kept = doctors()
        assert status == "fail" and "2 transcript(s) could not be copied" in detail
        assert kept["reason"].replace(str(Path.home()), "~") in detail             # what failed, as the export printed it
        assert kept["failed"] == 2 and kept["reason"] in report and not kept.get("complete")
        natives[0].chmod(0o644)
        assert sessions.export(0, only="c1")[0].startswith("claude-code c1: ")    # a run of one session copies that one,
        assert doctors()[0] == "fail"                                             # and the other is still not copied
        assert len(sessions.export(0)) == 1 and doctors()[2]["failed"] == 1
        natives[1].chmod(0o644)
        sessions.export(0)
        status, detail, done = doctors()
        assert status == "ok" and "failed" not in done and "reason" not in done and done["complete"] == done["exported"]
        _jsonl(natives[1], [_typed({"cwd": harness["work"], "sessionId": "c2"}, "One more thing.", "2026-10-30T16:00:00.000Z")])
        natives[1].chmod(0o000)
        sessions.export(0)
        status, detail, kept = doctors()
        assert status == "fail" and "1 transcript(s) could not be copied" in detail and kept["complete"] == done["complete"]
        assert f"since {done['complete'][:16]}" in detail          # when a run last copied everything
    finally:
        for native in natives:
            native.chmod(0o644)


def _scheduled(tmp_path) -> Path:
    """The export's schedule file as the onboarding setup writes it for this home's own command."""
    import plistlib
    own, plist = sessions.paths.home() / "bin" / "synthesis", tmp_path / "com.synthesis.sessions-export.plist"
    plist.write_bytes(plistlib.dumps({"Label": plist.stem, "ProgramArguments": [
        "/bin/bash", "-lc", f'"{own}" sessions export --all --scheduled; "{own}" sessions sync']}))
    return plist


def _its_own(stamp: Path) -> Path:
    """The runs these tests make stand for the schedule's own, which its command marks in the stamp."""
    done = json.loads(stamp.read_text())
    stamp.write_text(json.dumps({**done, "scheduled": done["exported"]}), encoding="utf-8")
    return stamp


def _checked(tmp_path) -> tuple:
    """The doctor's answer about the export where its schedule is loaded: the status, the words, the stamp it read."""
    from synthesis import doctor
    stamp, plist = sessions.root() / ".state" / "export.json", _scheduled(tmp_path)
    found = doctor.check_sessions_export(plist, _its_own(stamp), run=lambda argv, **kw: subprocess.CompletedProcess(argv, 0, "", ""))
    return found.status, found.detail, json.loads(stamp.read_text())


@closed_to_us
def test_a_transcript_removed_before_it_was_copied_stays_named_until_the_principal_clears_it(principal, harness, tmp_path, capsys):
    """2026-11-12, a second review: a copy failed, the harness then removed the transcript, and the next run of
    everything found nothing to copy, erased the failure and stamped complete. The doctor answered ok for a
    conversation that was never copied."""
    _, gone = [_jsonl(harness["claude"].with_name(f"{name}.jsonl"), _claude_rows(harness["work"])) for name in ("c1", "c2")]
    gone.chmod(0o000)
    try:
        sessions.export(0)
    finally:
        gone.chmod(0o644)
    status, _, first = _checked(tmp_path)
    assert status == "fail" and first["failed"] == 1
    gone.unlink()                                                                                     # the harness removes it
    report = sessions.export(0)
    status, detail, stamp = _checked(tmp_path)
    assert status == "fail" and stamp["failed"] == 1 and "complete" not in stamp                      # never copied, and still said
    named, when = stamp["uncopied"], first["uncopied"]["claude-code c2"]["at"]
    assert list(named) == ["claude-code c2"] and named["claude-code c2"]["native"] == str(gone)       # which transcript,
    assert named["claude-code c2"]["at"] == when and re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d", when)   # when its copy last failed,
    assert named["claude-code c2"]["gone"] >= when                                                    # and when a run first found it gone
    assert [line for line in report if line.startswith("claude-code c2: ") and when[:16] in line and "--lost c2" in line]
    assert "claude-code c2 (its copy last failed " + when[:16] in detail and "export --lost" in detail and "principal" in detail
    for again in (lambda: sessions.export(2), lambda: sessions.export(0, only="c1"), lambda: sessions.export(0)):
        again()                                                                                       # whichever run comes next
        assert _checked(tmp_path)[0] == "fail" and _checked(tmp_path)[2]["uncopied"]["claude-code c2"]["at"] == when
    clear = ["sessions", "export", "--lost", "c2"]
    assert cli.main(["sessions", "export", "--lost", "c9"]) == 1 and "claude-code c2" in capsys.readouterr().err   # it says what is recorded
    assert cli.main(clear) == 2                                                                       # an agent cannot call it lost:
    refused = capsys.readouterr().err
    assert "type approve" in refused and _checked(tmp_path)[0] == "fail"
    principal(refused)                                                                                # the principal can
    marked = json.loads(_its_own(sessions.root() / ".state" / "export.json").read_text())["scheduled"]
    assert cli.main(clear) == 0
    assert "claude-code c2" in capsys.readouterr().out
    # Clearing a loss kept the stamp's last export and dropped the schedule's own mark with the rest: the doctor then
    # said the schedule had never run, just when a person is likeliest to ask it (a review, 2026-11-13).
    assert json.loads((sessions.root() / ".state" / "export.json").read_text())["scheduled"] == marked
    status, detail, stamp = _checked(tmp_path)
    assert status == "ok" and not {"failed", "reason", "uncopied"} & set(stamp)
    lost = [json.loads(line) for line in (sessions.root() / ".state" / "lost.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [(row["transcript"], row["native"], row["at"]) for row in lost] == [("claude-code c2", str(gone), when)] and lost[0]["cleared"]
    assert cli.main(clear) == 1 and "c2" in capsys.readouterr().err                                   # and nothing is left to clear
    assert sessions.export(0) is not None and _checked(tmp_path)[2]["complete"]                       # the next run copies everything there is


@closed_to_us
def test_only_a_transcript_that_is_gone_is_lost(principal, harness, tmp_path, monkeypatch, capsys):
    """A copy that failed is a loss only once no run can make it. A transcript still there is not cleared; a run that
    does not look where it is does not call it gone; one the harness moved is copied from where it is; and a
    rebuild forgets neither what is not copied nor what was lost."""
    thread = "01a18a2b-0000-7000-8000-000000000001"
    codex = _jsonl(Path(os.environ["CODEX_HOME"]) / "sessions" / "2026" / "10" / "30" / f"rollout-2026-10-30T10-00-00-{thread}.jsonl", [
        {"type": "session_meta", "timestamp": "2026-10-30T10:00:00Z", "payload": {"id": "x", "cwd": harness["work"]}},
        {"type": "response_item", "timestamp": "2026-10-30T10:00:02Z", "payload": {
            "type": "message", "role": "user", "content": [{"type": "input_text", "text": "Fix the build."}]}}])
    one, two = [_jsonl(harness["claude"].with_name(f"{name}.jsonl"), _claude_rows(harness["work"])) for name in ("c1", "c2")]
    for native in (codex, one, two):
        native.chmod(0o000)
    try:
        sessions.export(0)
        assert sorted(_checked(tmp_path)[2]["uncopied"]) == ["claude-code c1", "claude-code c2", f"codex {thread}"]
        for name, native in (("c1", one), (thread, codex)):                    # still there, so not lost: a run may yet copy it
            assert cli.main(["sessions", "export", "--lost", name]) == 1
            assert "is not lost" in capsys.readouterr().err and len(_checked(tmp_path)[2]["uncopied"]) == 3
        with monkeypatch.context() as away:                                    # a run that looks somewhere else finds none of them,
            away.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "away"))
            away.setenv("CODEX_HOME", str(tmp_path / "away"))
            assert sessions.export(0) == []
        named = _checked(tmp_path)[2]["uncopied"]
        assert len(named) == 3 and not any("gone" in entry for entry in named.values())   # and calls none of them gone
    finally:
        for native in (codex, one, two):
            native.chmod(0o644)
    archived = codex.parents[4] / "archived_sessions" / codex.name            # Codex archives the session: the same transcript, elsewhere
    archived.parent.mkdir(parents=True)
    codex.rename(archived)
    assert cli.main(["sessions", "export", "--lost", thread]) == 1 and str(archived) in capsys.readouterr().err
    one.unlink()
    two.unlink()                                                               # the other two are removed, and the principal clears one
    assert cli.main(["sessions", "export", "--lost", "c2"]) == 2
    principal(capsys.readouterr().err)
    assert cli.main(["sessions", "export", "--lost", "c2"]) == 0
    report = sessions.export(rebuild=True)                                     # a rebuild reads everything again
    status, detail, stamp = _checked(tmp_path)
    assert f"codex {thread}: 2 record(s)" in report                            # the moved one is copied,
    assert list(stamp["uncopied"]) == ["claude-code c1"] and stamp["uncopied"]["claude-code c1"]["gone"]     # the removed one is still named,
    assert status == "fail" and "claude-code c1 (its copy last failed" in detail
    lost = (sessions.root() / ".state" / "lost.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["transcript"] for line in lost] == ["claude-code c2"]                              # and the cleared one still on record


@closed_to_us
def test_in_a_terminal_of_their_own_the_principal_clears_a_loss_without_a_code(harness, tmp_path, monkeypatch, capsys):
    """Run by an agent, `--lost` waits for the principal's code. Typed by the principal in their own terminal, outside
    any harness, it needs none: nobody else is at that keyboard."""
    import types
    gone = _jsonl(harness["claude"], _claude_rows(harness["work"]))
    gone.chmod(0o000)
    try:
        sessions.export(0)
    finally:
        gone.chmod(0o644)
    gone.unlink()
    monkeypatch.setattr("sys.stdin", types.SimpleNamespace(isatty=lambda: True))
    monkeypatch.setenv("SYNTHESIS_SESSION", "S1")
    monkeypatch.setenv("CLAUDECODE", "1")                                      # a terminal inside a harness is an agent's
    assert cli.main(["sessions", "export", "--lost", "c1"]) == 2 and "type approve" in capsys.readouterr().err
    assert _checked(tmp_path)[0] == "fail"
    monkeypatch.delenv("CLAUDECODE")
    assert cli.main(["sessions", "export", "--lost", "c1"]) == 0 and "cleared: claude-code c1" in capsys.readouterr().out
    assert _checked(tmp_path)[0] == "ok"


@closed_to_us
def test_a_loss_is_cleared_on_the_principals_code_however_the_clearing_is_called(principal, harness, tmp_path):
    """The command asked for the principal's code, and the function under it did not: a script that called it cleared
    a loss with no code at all."""
    gone = _jsonl(harness["claude"], _claude_rows(harness["work"]))
    gone.chmod(0o000)
    try:
        sessions.export(0)
    finally:
        gone.chmod(0o644)
    gone.unlink()
    with pytest.raises(PermissionError) as refused:
        sessions.lost("c1")
    assert "type approve" in str(refused.value) and _checked(tmp_path)[0] == "fail"
    principal(str(refused.value))
    assert sessions.lost("claude-code c1").startswith("cleared: claude-code c1") and _checked(tmp_path)[0] == "ok"   # by either name


@closed_to_us
def test_a_loss_is_not_cleared_on_an_approval_the_sessions_transcript_does_not_back(principal, harness, tmp_path, capsys):
    """An approval of the loss is on record and the session's own transcript does not show the principal typing it: an
    agent runs as the same user and can write the grant itself. The clearing then says why and exits 2 with no
    traceback, as opening a send window does, clears nothing and asks again; the principal's own prompt clears it."""
    import sys
    from synthesis import approvals
    gone = _jsonl(harness["claude"], _claude_rows(harness["work"]))
    gone.chmod(0o000)
    try:
        sessions.export(0)
    finally:
        gone.chmod(0o644)
    gone.unlink()
    clear, record = ["sessions", "export", "--lost", "c1"], principal.transcript

    def written(code: str) -> None:                                             # the words, in a record the principal did not type
        record.write_text(json.dumps({"type": "user", "isMeta": True, "sessionId": "S-principal", "timestamp": "2099-01-01T00:00:00Z",
                                      "message": {"role": "user", "content": f"approve {code}"}}) + "\n", encoding="utf-8")
    unbacked = {"no transcript of the session": (lambda code: None, "gave no transcript"),
                "the words in a record the principal did not type": (written, "shows no prompt from the principal"),
                "a transcript that cannot be read": (lambda code: record.chmod(0o000), "could not be read")}
    assert cli.main(clear) == 2
    asked = capsys.readouterr().err                                              # it asks for the principal's code
    try:
        for name, (leave, why) in unbacked.items():
            code = re.search(r"\bcode ([a-z0-9]{6})\b", asked).group(1)
            leave(code)
            assert approvals.grant_from_prompt(f"approve {code}"), name          # a grant, with no prompt of theirs behind it
            assert cli.main(clear) == 2, name
            asked = capsys.readouterr().err
            assert "An approval for this call was recorded, but" in asked and why in asked and "approve followed by the code" in asked, name
            assert _checked(tmp_path)[0] == "fail" and not (sessions.root() / ".state" / "lost.jsonl").exists(), name
    finally:
        record.chmod(0o644)
    assert approvals.grant_from_prompt("approve " + re.search(r"\bcode ([a-z0-9]{6})\b", asked).group(1))
    done = subprocess.run([sys.executable, "-m", "synthesis", *clear], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                          cwd=str(Path(__file__).resolve().parents[1]))         # and run as the command itself
    assert done.returncode == 2 and done.stdout == "" and "Traceback" not in done.stderr
    assert done.stderr.startswith("An approval for this call was recorded, but") and len(done.stderr.splitlines()) == 1
    assert approvals.grant_from_prompt("approve " + re.search(r"\bcode ([a-z0-9]{6})\b", done.stderr).group(1))
    with pytest.raises(approvals.Unverified) as refused:                         # the function under the command refuses the same way
        sessions.lost("c1")
    assert _checked(tmp_path)[0] == "fail"
    principal(str(refused.value))                                                # the code it asks for, typed by the principal
    assert cli.main(clear) == 0 and "cleared: claude-code c1" in capsys.readouterr().out and _checked(tmp_path)[0] == "ok"


def test_a_transcript_an_adapter_cannot_read_is_named_and_the_run_goes_on(harness, tmp_path, capsys):
    """A row of a shape an adapter does not expect stopped the whole run where it stood: the transcripts after it
    were not copied and no stamp was left, so the doctor answered ok until a day had passed."""
    for name, said in (("a1", ["a block that is only a string"]), ("b1", "Plan the release."), ("c1", "Draft the notes.")):
        _jsonl(harness["claude"].with_name(f"{name}.jsonl"), [_typed({"cwd": harness["work"], "sessionId": name}, said, "2026-10-30T15:00:00.000Z")])
    report = sessions.export(0)
    status, detail, stamp = _checked(tmp_path)
    assert sorted(line for line in report if "record(s)" in line) == ["claude-code b1: 1 record(s)", "claude-code c1: 1 record(s)"]
    assert status == "fail" and list(stamp["uncopied"]) == ["claude-code a1"]
    assert stamp["reason"].startswith("claude-code a1: not exported (AttributeError: ") and stamp["reason"] in report
    assert cli.main(["sessions", "prompts", "--workspace", "acme", "--date", "2026-10-30"]) == 2          # and that day is not listed
    assert "claude-code a1: not exported" in capsys.readouterr().err


def test_resume_shows_the_conversation_beside_a_transcript_an_adapter_cannot_read(harness, tmp_path):
    """With a transcript not copied, resume also reads what each harness recorded since the last export, and the same
    row stopped it there: the session picking the work up got a traceback in place of the project."""
    _jsonl(harness["claude"], _claude_rows(harness["work"]))
    _jsonl(harness["claude"].with_name("a1.jsonl"),
           [_typed({"cwd": harness["work"], "sessionId": "a1"}, ["a block that is only a string"], "2026-10-30T15:00:00.000Z")])
    kb = tmp_path / "kb"
    (kb / "projects" / "alpha").mkdir(parents=True)
    (kb / "projects" / "alpha" / "CONTEXT.md").write_text("**Phase:** build\n**Status:** active\n", encoding="utf-8")
    assert "Please plan the release." in project.resume(str(kb / "projects" / "alpha"), "S-new")


# --- what the search for transcripts cannot read (2026-11-12, a second review) -----------------------------------
# With a harness's transcript folder unreadable, the search passed over it: the run found nothing there to copy,
# stamped complete, and the doctor answered ok while nothing of that harness was being copied. A folder the search
# cannot list is named in the stamp like a transcript that is not copied, until a run of everything lists it.

@contextlib.contextmanager
def _closed(path: Path, mode: int = 0o000):
    """A folder or a file the run may not read, as when the scheduled job is refused a harness's files."""
    was = path.stat().st_mode
    path.chmod(mode)
    try:
        yield path
    finally:
        path.chmod(was)


CODEX_ONE, CODEX_TWO = "01a10000-0000-7000-8000-000000000001", "01a10000-0000-7000-8000-000000000002"
EVERY = {"claude-code c1", "claude-code b1", "claude-code c1-agent-a1", f"codex {CODEX_ONE}", f"codex {CODEX_TWO}", "muse 01a1-muse"}


def _everywhere(harness) -> dict:
    """One transcript in each place a harness keeps them, each last written days ago."""
    from datetime import datetime
    base, codex = {"cwd": harness["work"], "sessionId": "c1"}, Path(os.environ["CODEX_HOME"])

    def rollout(folder: Path, thread: str) -> Path:
        return _jsonl(folder / f"rollout-2026-10-30T10-00-00-{thread}.jsonl", [
            {"type": "session_meta", "timestamp": "2026-10-30T10:00:00Z", "payload": {"id": thread, "cwd": harness["work"]}},
            {"type": "response_item", "timestamp": "2026-10-30T10:00:02Z", "payload": {
                "type": "message", "role": "user", "content": [{"type": "input_text", "text": "Fix the build."}]}}])
    found = {
        "claude": _jsonl(harness["claude"], [_typed(base, "Plan the release.", "2026-10-30T15:00:00.000Z")]),
        "other": _jsonl(harness["claude"].parents[1] / "-other" / "b1.jsonl",
                        [_typed({**base, "sessionId": "b1"}, "Order the parts.", "2026-10-30T15:00:00.000Z")]),
        "sub": _jsonl(harness["claude"].parent / "c1" / "subagents" / "agent-a1.jsonl", [
            {"type": "user", "isSidechain": True, "cwd": harness["work"], "timestamp": "2026-10-30T15:00:05Z",
             "message": {"role": "user", "content": "Check the script."}}]),
        "codex": rollout(codex / "sessions" / "2026" / "10" / "30", CODEX_ONE),
        "archived": rollout(codex / "archived_sessions", CODEX_TWO),
        "muse": _jsonl(Path(os.environ["XDG_DATA_HOME"]) / "muse" / "sessions" / "2026" / "10" / "30" / "01a1-muse" / "session.jsonl", [
            {"payload_type": "runtime.user_intent.accepted", "recorded_at": 1793350000500000, "payload": {
                "surface": "main", "model_messages": [{"content": [{"kind": "text", "text": "Review the draft."}]}]}}]),
    }
    written = datetime(2026, 10, 30, 16).timestamp()
    for native in found.values():
        os.utime(native, (written, written))
    return found


def _copied(report: list) -> set:
    return {line.split(":")[0] for line in report if "record(s)" in line}


@closed_to_us
def test_a_transcript_folder_that_cannot_be_listed_is_named_until_a_run_of_everything_lists_it(harness, tmp_path, capsys):
    from datetime import date
    native = _everywhere(harness)["claude"]
    folder = native.parents[1]                                         # where Claude Code keeps every transcript
    name, listing = f"claude-code {folder}", ["sessions", "prompts", "--workspace", "acme", "--date"]
    with _closed(folder):
        report = sessions.export(0)
        status, detail, stamp = _checked(tmp_path)
        assert status == "fail" and stamp["failed"] == 1 and "complete" not in stamp              # not copied, and said
        assert list(stamp["uncopied"]) == [name] and stamp["uncopied"][name]["native"] == str(folder)
        assert stamp["reason"] == f"{name}: not exported (cannot be listed: Permission denied)" and stamp["reason"] in report
        assert "1 transcript(s) could not be copied" in detail and "cannot be listed: Permission denied" in detail
        assert _copied(report) == {f"codex {CODEX_ONE}", f"codex {CODEX_TWO}", "muse 01a1-muse"}  # the run goes on to the others
        for day in ("2026-10-30", date.today().isoformat()):                                      # what it holds may be of any day
            assert cli.main(listing + [day]) == 2
            said = capsys.readouterr()
            assert said.out == "" and "cannot be listed" in said.err and "synthesis doctor" in said.err
        assert cli.main(["sessions", "export", "--lost", str(folder)]) == 1                       # a folder is no loss to accept
        capsys.readouterr()
    assert sessions.export(2) == [] and _checked(tmp_path)[0] == "fail"     # a run of two days does not copy what it held,
    report = sessions.export(0)                                             # a run of everything lists it and does
    status, _, stamp = _checked(tmp_path)
    assert _copied(report) == {"claude-code c1", "claude-code b1", "claude-code c1-agent-a1"}
    assert status == "ok" and not {"failed", "reason", "uncopied"} & set(stamp) and stamp["complete"] == stamp["exported"]
    assert cli.main(listing + ["2026-10-30"]) == 0 and "Plan the release." in capsys.readouterr().out


SHUT = {  # the folder closed, the harness whose transcripts it holds, the folder the stamp names, and what it hides
    "one project's folder": (lambda at: at["claude"].parent, "claude-code", None, {"claude-code c1", "claude-code c1-agent-a1"}),
    "a session's sub-agents": (lambda at: at["sub"].parent, "claude-code", None, {"claude-code c1-agent-a1"}),
    "the folder above Claude Code's transcripts": (lambda at: at["claude"].parents[2], "claude-code", lambda at: at["claude"].parents[1],
                                                   {"claude-code c1", "claude-code b1", "claude-code c1-agent-a1"}),
    "a project's folder that is searched and not listed": (lambda at: at["claude"].parent, "claude-code", None,
                                                           {"claude-code c1", "claude-code c1-agent-a1"}),
    "the folder of every Codex rollout": (lambda at: at["codex"].parents[3], "codex", None, {f"codex {CODEX_ONE}"}),
    "a day's folder of Codex rollouts": (lambda at: at["codex"].parent, "codex", None, {f"codex {CODEX_ONE}"}),
    "the folder Codex archives into": (lambda at: at["archived"].parent, "codex", None, {f"codex {CODEX_TWO}"}),
    "a day's folder of Muse sessions": (lambda at: at["muse"].parents[1], "muse", None, {"muse 01a1-muse"}),
}


@closed_to_us
@pytest.mark.parametrize("shut, kept, named, hidden", SHUT.values(), ids=SHUT.keys())
def test_wherever_a_folder_cannot_be_listed_it_is_named_and_the_run_goes_on(harness, tmp_path, request, shut, kept, named, hidden):
    at = _everywhere(harness)
    name = f"{kept} {(named or shut)(at)}"
    with _closed(shut(at), 0o111 if "searched and not listed" in request.node.name else 0o000):
        report = sessions.export(0)
        status, _, stamp = _checked(tmp_path)
    assert _copied(report) == EVERY - hidden                             # every transcript the search could reach is copied,
    assert list(stamp["uncopied"]) == [name] and stamp["uncopied"][name]["folder"] is True       # the folder is named as one,
    assert f"{name}: not exported (cannot be listed: Permission denied)" in report and status == "fail" and "complete" not in stamp
    report = sessions.export(0)
    assert _copied(report) == hidden and _checked(tmp_path)[0] == "ok"    # and once it can be listed, what it held is copied


@closed_to_us
def test_transcripts_the_search_can_name_and_not_look_at_are_each_named(harness, tmp_path):
    """A folder that can be listed and not searched gives the names of its transcripts and nothing else. The search
    stopped there with a traceback: no transcript of any harness was copied and no stamp was left. The same for a
    Muse session's own folder, which the search looks into without listing."""
    at = _everywhere(harness)
    with _closed(at["claude"].parent, 0o444), _closed(at["muse"].parent):
        report = sessions.export(0)
        status, _, stamp = _checked(tmp_path)
    assert _copied(report) == EVERY - {"claude-code c1", "claude-code c1-agent-a1", "muse 01a1-muse"} and status == "fail"
    assert {"claude-code c1", "muse 01a1-muse", f"claude-code {at['sub'].parents[1]}"} == set(stamp["uncopied"])
    for name, native in (("claude-code c1", at["claude"]), ("muse 01a1-muse", at["muse"])):          # each as a transcript not copied,
        assert stamp["uncopied"][name]["reason"] == f"{name}: not exported ([Errno 13] Permission denied: '{native}')"
        assert "folder" not in stamp["uncopied"][name] and "gone" not in stamp["uncopied"][name]
    assert stamp["uncopied"][f"claude-code {at['sub'].parents[1]}"]["folder"] is True               # and the folder below as one not listed
    assert _copied(sessions.export(0)) == {"claude-code c1", "claude-code c1-agent-a1", "muse 01a1-muse"} and _checked(tmp_path)[0] == "ok"


@closed_to_us
def test_a_transcript_is_not_called_gone_while_the_folder_it_was_in_cannot_be_listed(principal, harness, tmp_path, capsys):
    """A transcript whose copy failed is gone once a run of everything no longer finds it. A run that cannot list the
    folder it was in has not looked: it is not gone, the doctor does not send for the principal, and it is not a
    loss to accept. Nor does a folder that was named stay named once it is removed."""
    at = _everywhere(harness)
    with _closed(at["claude"]):
        sessions.export(0)
    assert list(_checked(tmp_path)[2]["uncopied"]) == ["claude-code c1"]
    with _closed(at["claude"].parent):
        report = sessions.export(0)
        status, detail, stamp = _checked(tmp_path)
        assert set(stamp["uncopied"]) == {"claude-code c1", f"claude-code {at['claude'].parent}"} and stamp["failed"] == 2
        assert "gone" not in stamp["uncopied"]["claude-code c1"] and not [line for line in report if "removed" in line]
        assert status == "fail" and "Gone before a copy was made" not in detail and "export --all" in detail
        assert cli.main(["sessions", "export", "--lost", "c1"]) == 1                # not known to be gone: no code is asked for
        refused = capsys.readouterr().err
        assert "cannot be listed" in refused and str(at["claude"].parent) in refused and "approve" not in refused
    assert _copied(sessions.export(0)) == {"claude-code c1"} and _checked(tmp_path)[0] == "ok"
    with _closed(at["codex"].parent):
        sessions.export(0)
    assert list(_checked(tmp_path)[2]["uncopied"]) == [f"codex {at['codex'].parent}"]
    at["codex"].unlink()
    at["codex"].parent.rmdir()                                                     # the folder itself is removed:
    assert sessions.export(0) == [] and _checked(tmp_path)[0] == "ok"               # nothing is left there to list


@closed_to_us
def test_the_export_command_exits_1_once_it_has_stamped_what_it_could_not_copy(harness, tmp_path, capsys):
    """2026-11-12: every copy was refused and the command still exited 0, so the script or the job that ran it could
    not tell. It exits 1 when something it was asked for was not copied, after leaving the stamp, and says how many
    are not copied and where to look; it exits 0 when everything it was asked for was copied."""
    import sys
    one, two = [_jsonl(harness["claude"].with_name(f"{name}.jsonl"), _claude_rows(harness["work"])) for name in ("c1", "c2")]
    everything = ["sessions", "export", "--all"]
    assert cli.main(everything) == 0
    said = capsys.readouterr()
    assert "claude-code c1: " in said.out and "claude-code c2: " in said.out and said.err == ""
    assert cli.main(everything) == 0 and capsys.readouterr().out.strip() == "nothing new to export"      # nothing new is no failure
    _jsonl(two, [_typed({"cwd": harness["work"], "sessionId": "c2"}, "One more thing.", "2026-10-30T16:00:00.000Z")])
    with _closed(two):
        assert cli.main(everything) == 1
        said = capsys.readouterr()
        assert "claude-code c2: not exported" in said.out and _checked(tmp_path)[2]["failed"] == 1      # stamped, then said
        assert said.err.startswith("1 transcript(s) could not be copied") and "synthesis doctor" in said.err
        assert cli.main(["sessions", "export", "--session", "c1"]) == 0 and capsys.readouterr().err == ""    # all that was asked for
        assert cli.main(["sessions", "export", "--session", "c2"]) == 1 and cli.main(["sessions", "export"]) == 1
        done = subprocess.run([sys.executable, "-m", "synthesis", *everything], capture_output=True, text=True,
                              cwd=str(Path(__file__).resolve().parents[1]))            # and as the command a job runs
        assert done.returncode == 1 and "claude-code c2: not exported" in done.stdout and "synthesis doctor" in done.stderr
        capsys.readouterr()
    two.unlink()                                                        # removed before a run copied what it had gained
    assert cli.main(everything) == 1
    said = capsys.readouterr()
    assert "not copied before its transcript was removed" in said.out and "1 transcript(s) could not be copied" in said.err
    assert cli.main(["sessions", "export"]) == 0                        # a run of two days was asked for nothing of it
    with _closed(one.parent):
        assert cli.main(everything) == 1                                # a folder that cannot be listed
        assert capsys.readouterr().err.startswith("2 transcript(s) could not be copied")
    folders = [sessions.root(), *(d for d in sessions.root().rglob("*") if d.is_dir())]
    for folder in folders:
        folder.chmod(0o555)                                             # and an archive that cannot be written: no stamp is left,
    try:
        _jsonl(one, [_typed({"cwd": harness["work"], "sessionId": "c1"}, "And another.", "2026-10-30T17:00:00.000Z")])
        assert cli.main(everything) == 1
        said = capsys.readouterr()
        assert said.out.startswith("not exported: ") and said.err.startswith("not exported: ") and "doctor" not in said.err
    finally:
        for folder in folders:
            folder.chmod(0o755)


def test_the_export_command_says_an_archive_was_not_written_wherever_that_line_stands(capsys, monkeypatch):
    """After a rebuild the line that says the archive was not written is the report's second, behind where the old
    archive went. The command then gave a count read from a stamp that had not been left."""
    report = ["previous archive moved to /old", "not exported: [Errno 28] No space left on device",
              "claude-code c1: not exported ([Errno 28] No space left on device)"]
    monkeypatch.setattr(sessions, "export", lambda *args, **kwargs: list(report))
    assert cli.main(["sessions", "export", "--rebuild"]) == 1
    said = capsys.readouterr()
    assert said.err.strip() == report[1] and said.out.splitlines()[:3] == report


def test_a_run_started_by_a_command_line_is_briefed_not_prompted(harness):
    """`codex exec` and `claude -p` take their prompt from a script or another agent (2026-11-11: eight review
    briefs an agent wrote were listed among the principal's own prompts of the day)."""
    codex = _jsonl(Path(os.environ["CODEX_HOME"]) / "sessions" / "2026" / "10" / "30" / "rollout-2026-10-30T10-00-00-x9.jsonl", [
        {"type": "session_meta", "timestamp": "2026-10-30T10:00:00Z", "payload": {
            "id": "x9", "cwd": harness["work"], "originator": "codex_exec", "source": "exec"}},
        {"type": "response_item", "timestamp": "2026-10-30T10:00:02Z", "payload": {
            "type": "message", "role": "user", "content": [{"type": "input_text", "text": "Review this branch."}]}},
    ])
    base = {"cwd": harness["work"], "sessionId": "c1", "timestamp": "2026-10-30T10:00:00.000Z"}
    _jsonl(harness["claude"], [
        {**base, "entrypoint": "sdk-cli", "type": "user", "message": {"role": "user", "content": "Summarize the diff."}},
        {**base, "entrypoint": "claude-desktop", "type": "user", "message": {"role": "user", "content": "Now ship it."}},
    ])
    sessions.export(0)
    kinds = {r["text"]: r["kind"] for native in (codex, harness["claude"]) for r in sessions.records(_meta(native)["folder"])
             if r.get("kind") in ("user", "brief")}
    assert kinds == {"Review this branch.": "brief", "Summarize the diff.": "brief", "Now ship it.": "user"}
    assert [p["text"] for p in sessions.prompts("acme", "2026-10-30")] == ["Now ship it."]


# --- a record's number is its name: reading a session again keeps every number it gave (2026-11-13) -------------------
# A citation names a record by its number, and a rebuild numbered every session anew: under a reader that files more
# than the one before it, each later record moved up, and a citation written earlier named another record with
# nothing to say so. Counted on one machine's records before this was written: 349 citations, 373 distinct numbers in
# 49 sessions, of which a rebuild under the reader of that day would have moved 157. Committed before the code.

def _numbered(native: Path) -> dict:
    """{number: (time, kind, words)} of a session's records as the archive holds them."""
    return {rec["seq"]: (rec.get("at"), rec.get("kind"), rec.get("text")) for rec in sessions.records(_meta(native)["folder"])}


@pytest.fixture
def filed_by_an_older_reader(harness, monkeypatch):
    """A session exported under a reader that files less than today's: it passes over one thing the principal
    typed, as the reader before 5.13.0 passed over a prompt typed while a turn ran."""
    base = {"cwd": harness["work"], "sessionId": "c1"}

    def said(text, at):
        return {**base, "timestamp": at, "type": "assistant", "message": {"model": "claude-opus-5-5", "content": [{"type": "text", "text": text}]}}
    native = _jsonl(harness["claude"], _claude_rows(harness["work"]) + [
        _typed(base, "Also draft the announcement.", "2026-10-30T15:00:00.000Z"), said("Drafting it.", "2026-10-30T15:00:05.000Z"),
        _typed(base, "And send me the draft.", "2026-10-30T15:10:00.000Z"), said("Sent.", "2026-10-30T15:10:05.000Z")])
    today = sessions.ADAPTERS["claude-code"]

    def older(row, s):
        return [rec for rec in today(row, s) if not (rec and rec.get("kind") == "user" and rec.get("text") == "Also draft the announcement.")]
    with monkeypatch.context() as then:
        then.setitem(sessions.ADAPTERS, "claude-code", older)
        sessions.export(0)
    return native


def test_reading_a_session_again_keeps_every_number_and_files_what_is_new_after_them(filed_by_an_older_reader):
    native = filed_by_an_older_reader
    before = _numbered(native)
    files = {path: path.read_bytes() for path in Path(_meta(native)["folder"]).glob("transcript-*.jsonl")}
    assert "Also draft the announcement." not in [words for _, _, words in before.values()]
    report = sessions.export(rebuild=True)
    after = _numbered(native)
    assert {number: after.get(number) for number in before} == before            # every number names the record it named
    added = sorted(set(after) - set(before))
    assert [after[number][2] for number in added] == ["Also draft the announcement."] and added[0] > max(before)
    assert all(path.read_bytes().startswith(old) for path, old in files.items())  # no line the archive held is changed
    assert "claude-code c1: 1 record(s)" in report
    again = sessions.export(rebuild=True)                                        # and a second reading adds nothing
    assert _numbered(native) == after and not any(line.startswith("claude-code c1:") for line in again)


def test_what_stands_around_a_record_is_what_was_said_around_it(filed_by_an_older_reader):
    """A record filed by a later reading has a number after every other, so its neighbours by number are the end of
    the session; the lines shown around a cited record are its neighbours in time."""
    native = filed_by_an_older_reader
    sessions.export(rebuild=True)
    folder = _meta(native)["folder"]
    late = next(rec["seq"] for rec in sessions.records(folder) if rec.get("text") == "Also draft the announcement.")
    near = [rec.get("text") for rec in sessions.around(folder, late, span=1)]
    assert near[1:] == ["Also draft the announcement.", "Drafting it."] and "Sent." not in near


def test_a_days_prompts_stay_in_the_order_they_were_typed(filed_by_an_older_reader):
    sessions.export(rebuild=True)
    assert [prompt["text"] for prompt in sessions.prompts("acme", "2026-10-30")] == [
        "Please plan the release.", "Also draft the announcement.", "And send me the draft."]


def test_the_command_keeps_the_numbers_too(filed_by_an_older_reader, capsys):
    native = filed_by_an_older_reader
    before = _numbered(native)
    assert cli.main(["sessions", "export", "--rebuild"]) == 0
    after = _numbered(native)
    assert {number: after.get(number) for number in before} == before and len(after) == len(before) + 1

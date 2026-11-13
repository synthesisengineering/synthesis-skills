"""What the principal typed is filed as the principal's in every shape a Claude Code transcript holds it, and a session belongs
to the projects it wrote into.

The list of what was typed is read from the archive's `user` records, and a day does not close while one of them is
unaccounted for. A prompt the export files as something else is never listed. Measured on thirty days of
transcripts (2026-11-13), each row given to the export's own reader: 2,749 plain prompts were filed as the principal's; 513
typed while a turn ran (a queued command), 46 slash commands that reach the agent and 19 that followed a system
reminder in one block were not, 17 of every 100 things typed, and 32 of the slash commands left no record at
all, each dropped as a copy of the one before. Of 147 sessions that wrote into a project's folder, 134 named no
project: a session's project came only from the session-start hook's line.
"""

import json
import os
from pathlib import Path

import pytest

from synthesis import guards, sessions

SHAPES = Path(__file__).parent / "fixtures" / "claude_code_typed_shapes.jsonl"
AT = "2026-11-13T15:00:00.000Z"


@pytest.fixture
def harness(tmp_path, write_config):
    work, kb = tmp_path / "workspaces" / "acme" / "repo", tmp_path / "workspaces" / "acme" / "ai-knowledge-acme"
    work.mkdir(parents=True)
    for name in ("alpha", "beta", "_templates", ".cache/a", "archive/old"):
        (kb / "projects" / name).mkdir(parents=True)
    for name in ("alpha", "beta", "_templates"):  # a project is a folder that holds its CONTEXT.md
        (kb / "projects" / name / "CONTEXT.md").write_text("# A project\n", encoding="utf-8")
    (kb / "projects" / "index.yaml").write_text("projects: []\n", encoding="utf-8")
    write_config({"workspace_roots": [str(tmp_path / "workspaces" / "*")], "knowledge_roots": [str(kb)]})
    return {"work": str(work), "kb": str(kb), "claude": Path(os.environ["CLAUDE_CONFIG_DIR"]) / "projects" / "-acme" / "c1.jsonl"}


def row(harness, kind, **more):
    return {"cwd": harness["work"], "sessionId": "c1", "timestamp": AT, "type": kind, **more}


def typed(harness, text, **more):
    return row(harness, "user", message={"role": "user", "content": text}, origin={"kind": "human"}, **more)


def queued(harness, prompt, mode="prompt", origin={"kind": "human"}, **more):  # noqa: B006
    return row(harness, "attachment", attachment={"type": "queued_command", "prompt": prompt, "commandMode": mode,
                                                  **({"origin": origin} if origin else {}), **more})


def called(harness, tool, given, ident="t1"):
    return row(harness, "assistant", message={"model": "claude-opus-5-5", "content": [{"type": "tool_use", "id": ident, "name": tool, "input": given}]})


def exported(harness, rows, native=None):
    """The archive's records for these rows, as (kind, text) for what was said to the agent, and the session's meta."""
    native = native or harness["claude"]
    native.parent.mkdir(parents=True, exist_ok=True)
    with native.open("a", encoding="utf-8") as out:
        out.write("".join(json.dumps(r) + "\n" for r in rows))
    sessions.export_file("claude-code" if native == harness["claude"] else "codex", native)
    meta = next(m for m in sessions.catalog() if m["native"] == str(native))
    said = [(r["kind"], r.get("text", "")) for r in sessions.records(meta["folder"]) if r["kind"] in ("user", "brief", "system")]
    return said, meta


def prompts(said):
    return [text for kind, text in said if kind == "user"]


def test_the_shapes_a_transcript_holds_typed_words_in(harness):
    rows = [json.loads(line.replace("{WORK}", harness["work"]).replace("{KB}", harness["kb"])) for line in SHAPES.read_text(encoding="utf-8").splitlines()]
    said, meta = exported(harness, rows)
    assert prompts(said) == ["Please plan the release.", "Also bump the version.", "And tag it.", "/day-start", "/review the last change",
                         "/day-start", "Please also check the tests."]
    assert not [text for kind, text in said if kind == "brief"]
    assert meta["projects"] == ["alpha", "beta"]
    listed = [p["text"] for p in sessions.prompts("acme", "2026-11-13")]
    assert listed == prompts(said)                                             # the day's list of what was typed holds each


def test_a_prompt_typed_while_a_turn_runs_is_the_principals(harness):
    said, _ = exported(harness, [typed(harness, "Start the build."), queued(harness, "Also bump the version."),
                                 queued(harness, [{"type": "text", "text": "And tag it."}, {"type": "text", "text": "Then stop."}, {"type": "text", "text": " "}]),
                                 queued(harness, "<pasted_content id=\"a1\">a pasted log</pasted_content>"),
                                 queued(harness, "<command-message>review</command-message>\n<command-name>/review</command-name>"),
                                 queued(harness, "<system-reminder>The date has changed.</system-reminder>\nAnd then stop.")])
    assert prompts(said) == ["Start the build.", "Also bump the version.", "And tag it.", "Then stop.",   # a block is a record, as in a user row
                         "<pasted_content id=\"a1\">a pasted log</pasted_content>", "/review", "And then stop."]
    assert ("system", "Also bump the version.") not in said


@pytest.mark.parametrize("prompt, more", [
    ("<task-notification>\n<task-id>b1</task-id>\n</task-notification>", {"mode": "task-notification", "origin": {"kind": "task-notification"}}),
    ("<task-notification>\n<task-id>b1</task-id>\n</task-notification>", {"mode": "task-notification", "origin": None}),
    ("The review is back.", {"origin": {"kind": "peer"}, "isMeta": True}),
    ("The review is back.", {"origin": {"kind": "peer"}}),                  # another session's or an agent's words
    ("A note the harness wrote.", {"isMeta": True}),
    ("<ci-monitor-event>The checks passed.</ci-monitor-event>", {"origin": None}),
    ("<system-reminder>The date has changed.</system-reminder>", {}),
    ("A notification in plain words.", {"mode": "task-notification"}),
    ("", {}), (None, {}), ({"text": "an object"}, {}), ([], {}),
])
def test_a_queued_command_that_is_no_typed_prompt_stays_what_it_was(harness, prompt, more):
    said, _ = exported(harness, [typed(harness, "Start the build."), queued(harness, prompt, **more)])
    assert prompts(said) == ["Start the build."] and not [text for kind, text in said if kind == "brief"]


def test_a_queued_prompt_that_names_no_origin_is_the_principals_unless_an_agent_wrote_it(harness):
    said, _ = exported(harness, [queued(harness, "Carry on from the plan.", origin=None),
                                 queued(harness, "<agent-message from=\"reviewer\">Round two is back.</agent-message>", origin=None),
                                 queued(harness, "<cross-session-message from=\"s-1\">The branch is yours.</cross-session-message>", origin=None)])
    assert prompts(said) == ["Carry on from the plan."]
    assert [kind for kind, text in said if "Round two" in text or "branch is yours" in text] == ["brief", "brief"]


def test_a_sub_agents_queued_prompt_is_a_brief(harness):
    said, _ = exported(harness, [{**queued(harness, "Check the second file too."), "isSidechain": True}])
    assert said == [("brief", "Check the second file too.")]


def test_a_slash_command_that_reaches_the_agent_is_a_prompt_as_it_was_typed(harness):
    def command(name, args=None, **more):
        text = f"<command-message>{name}</command-message>\n<command-name>/{name}</command-name>" + (f"\n<command-args>{args}</command-args>" if args is not None else "")
        return row(harness, "user", message={"role": "user", "content": text}, **more)
    text = row(harness, "user", isMeta=True, message={"role": "user", "content": [{"type": "text", "text": "Run the ritual."}]})
    said, _ = exported(harness, [command("day-start"), text, command("review", "the last change\nand its tests"), text, command("day-start"), text,
                                 command("plugin:skill-name", "  "), command("hidden", isMeta=True)])
    assert prompts(said) == ["/day-start", "/review the last change\nand its tests", "/day-start", "/plugin:skill-name"]   # the same command twice is two prompts
    assert ("system", "Run the ritual.") in said and not any("hidden" in text for text in prompts(said))


@pytest.mark.parametrize("text", [
    "<command-name>/model</command-name>\n            <command-message>model</command-message>\n            <command-args>opus</command-args>",
    "<command-name>/compact</command-name>\n<command-message>compact</command-message>\n<command-args>keep the plan</command-args>",
    "<local-command-stdout>Set model to opus</local-command-stdout>",
    "<local-command-caveat>Caveat: do not respond to these.</local-command-caveat>",
    "<command-message>a row that names no command</command-message>",
    "<command-message>x</command-message>\n<command-name></command-name>",
])
def test_a_command_to_the_harness_and_its_output_are_no_prompt(harness, text):
    said, _ = exported(harness, [row(harness, "user", message={"role": "user", "content": text})])
    assert prompts(said) == [] and said and said[0][0] == "system"


def test_words_after_a_system_reminder_in_one_block_are_the_principals(harness):
    reminder = "<system-reminder>\nThe date has changed.\n</system-reminder>"
    said, _ = exported(harness, [
        typed(harness, reminder + "\n\nPlease also check the tests."),
        typed(harness, "<system-reminder>one</system-reminder>\n<system-reminder>two</system-reminder>\nThen ship it."),
        typed(harness, "<system-reminder>Only a reminder.</system-reminder>"),
        typed(harness, reminder + "\n<task-notification>\n<task-id>b2</task-id>\n</task-notification>"),
        typed(harness, "<system-reminder>never closed, so all of it is the harness's\nPlease do not file this."),
        typed(harness, "Keep this whole: <system-reminder>quoted</system-reminder> is what the tag looks like."),
        typed(harness, [{"type": "text", "text": reminder}, {"type": "text", "text": "A block of its own."}]),
    ])
    assert prompts(said) == ["Please also check the tests.", "Then ship it.",
                         "Keep this whole: <system-reminder>quoted</system-reminder> is what the tag looks like.", "A block of its own."]
    kept = [text for kind, text in said if kind == "system"]
    assert any("The date has changed." in text and "check the tests" not in text for text in kept)   # the reminder stays, apart
    assert not any("Please do not file this." in text for text in prompts(said))


def test_a_reminder_then_words_is_no_prompt_for_a_sub_agent_or_a_meta_row(harness):
    text = "<system-reminder>note</system-reminder>\nCheck the second file too."
    said, _ = exported(harness, [{**typed(harness, text), "isSidechain": True}, {**typed(harness, text + " (meta)"), "isMeta": True}])
    assert prompts(said) == [] and ("brief", "Check the second file too.") in said


def test_a_session_belongs_to_the_projects_its_tool_calls_wrote_into(harness):
    kb = harness["kb"]
    said, meta = exported(harness, [
        typed(harness, "Update the plan."),
        called(harness, "Read", {"file_path": f"{kb}/projects/beta/CONTEXT.md"}),                  # reading tags nothing
        called(harness, "Bash", {"command": f"cat {kb}/projects/beta/CONTEXT.md | head -3"}),
        called(harness, "Write", {"file_path": f"{kb}/projects/gamma/CONTEXT.md", "content": "x"}),  # no such project folder
        called(harness, "Write", {"file_path": f"{kb}/projects/index.yaml", "content": "x"}),        # a file beside the projects
        called(harness, "Write", {"file_path": f"{harness['work']}/projects/alpha/notes.md", "content": "x"}),  # a folder of that name elsewhere
        called(harness, "Write", {"file_path": f"{kb}/projects/_templates/CONTEXT.md", "content": "x"}),         # a folder that is no project's
        called(harness, "Write", {"file_path": f"{kb}/projects/.cache/a/b.md", "content": "x"}),
    ])
    assert "projects" not in meta or meta["projects"] == []
    said, meta = exported(harness, [called(harness, "Edit", {"file_path": f"{kb}/projects/alpha/CONTEXT.md", "old_string": "a", "new_string": "b"}),
                                    called(harness, "Bash", {"command": f"cd {kb}/projects/beta && echo done >> notes.md"}),
                                    called(harness, "Write", {"file_path": f"{kb}/projects/alpha/resources/a.md", "content": "x"})])
    assert meta["projects"] == ["alpha", "beta"]                          # each once, in the order first written


def test_a_relative_target_is_read_against_the_rows_working_directory(harness):
    there = {**called(harness, "Bash", {"command": "echo done >> notes.md"}), "cwd": f"{harness['kb']}/projects/beta"}
    _, meta = exported(harness, [there])
    assert meta["projects"] == ["beta"]


def test_the_hooks_project_and_the_written_ones_are_kept_together(harness):
    hook = row(harness, "attachment", attachment={"type": "hook_additional_context", "content": "Active project: alpha (/kb/projects/alpha)"})
    _, meta = exported(harness, [hook, called(harness, "Write", {"file_path": f"{harness['kb']}/projects/beta/CONTEXT.md", "content": "x"}),
                                 called(harness, "Write", {"file_path": f"{harness['kb']}/projects/alpha/CONTEXT.md", "content": "x"})])
    assert meta["projects"] == ["alpha", "beta"]


def test_a_codex_shell_line_is_text_and_tags_its_project(harness):
    native = Path(os.environ["CODEX_HOME"]) / "sessions" / "2026" / "11" / "13" / "rollout-2026-11-13T10-00-00-01a18a2b-0000-7000-8000-000000000009.jsonl"
    kb = harness["kb"]
    _, meta = exported(harness, [
        {"type": "session_meta", "timestamp": AT, "payload": {"id": "x9", "cwd": harness["work"], "cli_version": "0.166.0"}},
        {"type": "response_item", "timestamp": AT, "payload": {"type": "function_call", "name": "exec", "call_id": "c1", "arguments": f"cat {kb}/projects/alpha/CONTEXT.md"}},
        {"type": "response_item", "timestamp": AT, "payload": {"type": "function_call", "name": "exec", "call_id": "c2",
                                                               "arguments": f"apply_patch <<'EOF'\n*** Begin Patch\n*** Update File: {kb}/projects/beta/notes.md\n@@\n-a\n+b\n*** End Patch\nEOF"}},
    ], native=native)
    assert meta["projects"] == ["beta"]


def test_a_line_the_reader_cannot_read_tags_nothing_and_is_counted(harness, monkeypatch):
    def raises(command, cwd):
        raise RuntimeError("a line no reader was written for")
    monkeypatch.setattr(guards, "_shell_writes", raises)
    said, meta = exported(harness, [typed(harness, "Update the plan."), called(harness, "Bash", {"command": f"echo x > {harness['kb']}/projects/beta/notes.md"}),
                                    called(harness, "Write", {"file_path": f"{harness['kb']}/projects/alpha/CONTEXT.md", "content": "x"})])
    assert prompts(said) == ["Update the plan."] and meta["projects"] == ["alpha"]
    assert meta["skipped"]["a tool call whose written files could not be read"] == 1


@pytest.mark.parametrize("given", [None, "text", 7, [], {"file_path": 7}, {"file_path": None}, {"command": ["echo", "x"]}, {"command": None}, {"file_path": "relative.md"}])
def test_a_tool_call_of_another_shape_tags_nothing_and_stops_nothing(harness, given):
    for tool in ("Write", "Bash", "Unknown"):
        said, meta = exported(harness, [typed(harness, f"With {tool}."), called(harness, tool, given)])
        assert f"With {tool}." in prompts(said) and not meta.get("projects")


# --- a review, 2026-11-13 ------------------------------------------------------------------------------------------
# Measured after it on thirty days of transcripts, each row given to this reader and to the approval reader's own
# test of what the principal typed (`approvals._prompt`): the two agree on 3,597 rows; where the approval reader
# says typed and no `user` record is filed, the text is a wrapped block with no words outside it (a command to the
# harness and its output 253, a scheduled task 22, another session's message 23, a CI event 18) or the harness's
# own line that a request was interrupted (18). The cases below did not occur in those days; the reader is held to
# them all the same.

REMINDER = "<system-reminder>\nThe date has changed.\n</system-reminder>"


def slash(name, args=None, after=""):
    return (f"<command-message>{name}</command-message>\n<command-name>/{name}</command-name>"
            + (f"\n<command-args>{args}</command-args>" if args is not None else "") + after)


def test_a_reminder_and_then_a_slash_command_in_one_block_is_the_command(harness):
    said, _ = exported(harness, [typed(harness, REMINDER + "\n" + slash("review", "the last change"))])
    assert prompts(said) == ["/review the last change"]
    assert any(kind == "system" and "The date has changed." in text for kind, text in said)


def test_words_beside_a_slash_commands_arguments_are_kept(harness):
    said, _ = exported(harness, [typed(harness, slash("review", "a", after="\nAnd also the docs.")),
                                 typed(harness, slash("review", after=" the tests too"))])
    assert prompts(said) == ["/review a\nAnd also the docs.", "/review the tests too"]


def test_a_queued_prompt_is_filed_at_the_time_it_was_typed(harness):
    sent = queued(harness, "Also bump the version.", timestamp="2026-11-13T04:59:30.000Z")   # the attachment's own time
    sent["timestamp"] = "2026-11-13T05:00:30.000Z"                                           # the row's
    native = harness["claude"]
    native.parent.mkdir(parents=True, exist_ok=True)
    native.write_text(json.dumps(sent) + "\n", encoding="utf-8")
    sessions.export_file("claude-code", native)
    meta = next(m for m in sessions.catalog() if m["native"] == str(native))
    assert [r["at"] for r in sessions.records(meta["folder"]) if r["kind"] == "user"] == ["2026-11-13T04:59:30.000Z"]


def test_a_prompt_queued_in_a_session_a_program_drives_is_a_brief_as_its_rows_are(harness):
    said, _ = exported(harness, [{**typed(harness, "Summarize the file."), "entrypoint": "sdk-cli"},
                                 {**queued(harness, "And the next one."), "entrypoint": "sdk-cli"}])
    assert prompts(said) == [] and [text for kind, text in said if kind == "brief"] == ["Summarize the file.", "And the next one."]


@pytest.mark.parametrize("more", [{"origin": {"kind": "task-notification"}}, {"origin": {"kind": "peer"}}, {"isSynthetic": True},
                                  {"isVisibleInTranscriptOnly": True}, {"sourceToolUseID": "toolu_1"}, {"toolUseResult": {"ok": True}}])
def test_a_row_the_principal_cannot_have_typed_files_no_prompt(harness, more):
    """The approval reader's own test of a typed row: its flags and its origin. Before this, such a row with plain
    words was a `user` record, and the split of a reminder from the words after it made one of its words too."""
    rows = [{**typed(harness, text), **more} for text in ("Plain words.", REMINDER + "\nWords after a reminder.", slash("pdf"))]
    said, _ = exported(harness, rows)
    assert prompts(said) == [] and len(said) >= 2 and {kind for kind, _ in said} == {"system"}


def test_words_beside_a_tool_result_are_not_a_prompt(harness):
    both = row(harness, "user", origin={"kind": "human"}, message={"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "t1", "content": "ok"}, {"type": "text", "text": REMINDER + "\nWords the harness put beside a result."}]})
    said, _ = exported(harness, [both])
    assert prompts(said) == []


@pytest.mark.parametrize("prompt, more, top", [
    ("Typed, in a row the harness marks meta.", {}, {"isMeta": True}),
    ("<teammate-message from=\"a\">Go on.</teammate-message>", {"origin": None}, {}),
    ("<channel name=\"x\">An update.</channel>", {"origin": None}, {}),
    ("<bash-stdout>total 0</bash-stdout>", {}, {}),
])
def test_a_queued_command_that_is_not_typed_words_files_no_prompt(harness, prompt, more, top):
    said, _ = exported(harness, [{**queued(harness, prompt, **more), **top}])
    assert prompts(said) == []


def test_what_the_harness_prints_in_bash_mode_is_no_prompt(harness):
    said, _ = exported(harness, [typed(harness, "<bash-input>ls</bash-input>"), typed(harness, "<bash-stdout>total 0</bash-stdout><bash-stderr></bash-stderr>")])
    assert prompts(said) == [] and {kind for kind, _ in said} == {"system"}


def test_a_reminder_that_holds_its_own_closing_tag_ends_at_its_last_one(harness):
    """A reminder that shows a file can hold the tag's own text. Its tail is the harness's, not a prompt."""
    body = "<system-reminder>\nA file changed:\n  the text </system-reminder> stands in it\nand more of the file\n</system-reminder>"
    said, _ = exported(harness, [typed(harness, body), typed(harness, body + "\nNow the typed words.")])
    assert prompts(said) == ["Now the typed words."]
    assert not any("more of the file" in text for text in prompts(said))


def test_a_pasted_block_the_principal_sent_is_a_prompt_whatever_its_origin_says(harness):
    paste = "<pasted_content id=\"a1\">a pasted log</pasted_content>"
    said, _ = exported(harness, [typed(harness, paste), queued(harness, paste, origin=None)])
    assert prompts(said) == [paste, paste]


def _rollout(name="01a18a2b-0000-7000-8000-00000000000a"):
    return Path(os.environ["CODEX_HOME"]) / "sessions" / "2026" / "11" / "13" / f"rollout-2026-11-13T10-00-00-{name}.jsonl"


def _call(name, kind="function_call", **more):
    return {"type": "response_item", "timestamp": AT, "payload": {"type": kind, "name": name, "call_id": f"c-{name}-{len(more)}", **more}}


def test_a_folder_under_projects_that_holds_no_context_file_is_no_project(harness):
    """A review, 2026-11-13: a write into `projects/archive/old/` tagged the session with a project named archive.
    A project is a folder that holds its CONTEXT.md, as `project.locate` reads one."""
    kb = harness["kb"]
    _, meta = exported(harness, [called(harness, "Write", {"file_path": f"{kb}/projects/archive/old/notes.md", "content": "x"}),
                                 called(harness, "Bash", {"command": f"echo x > {kb}/projects/archive/index.md"})])
    assert not meta.get("projects")


def test_codex_arguments_kept_as_json_text_are_read_with_their_working_directory(harness):
    """Codex's own shell tools keep a call's arguments as JSON text, the command beside the folder it runs in, and
    its patch tool keeps the patch as text. Read as shell text, a relative write missed its project and a patch
    tagged nothing."""
    kb = harness["kb"]
    patch = f"*** Begin Patch\n*** Update File: {kb}/projects/beta/notes.md\n@@\n-a\n+b\n*** End Patch\n"
    _, meta = exported(harness, [
        {"type": "session_meta", "timestamp": AT, "payload": {"id": "xa", "cwd": harness["work"], "cli_version": "0.166.0"}},
        _call("shell_command", arguments=json.dumps({"command": "cat CONTEXT.md", "workdir": f"{kb}/projects/beta"})),        # a read
        _call("exec_command", arguments=json.dumps({"cmd": "echo done >> notes.md", "workdir": f"{kb}/projects/alpha"})),
    ], native=_rollout())
    assert meta["projects"] == ["alpha"]
    _, meta = exported(harness, [_call("shell_command", arguments=json.dumps({"command": ["bash", "-lc", "echo done >> notes.md"], "workdir": f"{kb}/projects/beta"}))],
                       native=_rollout())
    assert meta["projects"] == ["alpha", "beta"]
    _, meta = exported(harness, [{"type": "session_meta", "timestamp": AT, "payload": {"id": "xb", "cwd": harness["work"], "cli_version": "0.166.0"}},
                                 _call("apply_patch", kind="custom_tool_call", input=patch)], native=_rollout("01a18a2b-0000-7000-8000-00000000000b"))
    assert meta["projects"] == ["beta"]


@pytest.mark.parametrize("line", ["echo 'unbalanced > notes.md", "echo $(date > notes.md", "cat <<EOF > notes.md"])
def test_a_shell_line_the_guards_reader_cannot_read_is_counted(harness, line):
    """A review, 2026-11-13: the reader of what a line writes passes over a reading it cannot make and says nothing,
    so such a line was never counted, and the test of the count replaced the reader with one that raises."""
    there = {**called(harness, "Bash", {"command": line}), "cwd": f"{harness['kb']}/projects/beta"}
    _, meta = exported(harness, [there])
    assert not meta.get("projects") and meta["skipped"]["a tool call whose written files could not be read"] == 1


def test_the_guard_reads_a_patch_from_the_key_codex_gives_its_hook():
    """Codex's source gives a pre-tool-use hook the patch under `command` (`apply_patch.rs`, `pre_tool_use_payload`);
    the guard read `input` and `patch` and found no file in such a call."""
    patch = "*** Begin Patch\n*** Update File: /tmp/a/notes.md\n@@\n-a\n+b\n*** Add File: /tmp/a/new.md\n+x\n*** End Patch\n"
    for key in ("command", "input", "patch"):
        assert guards._file_targets("apply_patch", {key: patch}) == ["/tmp/a/notes.md", "/tmp/a/new.md"]

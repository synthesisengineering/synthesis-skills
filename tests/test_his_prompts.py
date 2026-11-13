"""What the principal typed is filed as his in every shape a Claude Code transcript holds it, and a session belongs
to the projects it wrote into.

The list of what he typed is read from the archive's `user` records, and a day does not close while one of them is
unaccounted for. A prompt the export files as something else is never listed. Measured on thirty days of
transcripts (2026-11-13), each row given to the export's own reader: 2,749 plain prompts were filed as his; 513
typed while a turn ran (a queued command), 46 slash commands that reach the agent and 19 that followed a system
reminder in one block were not, 17 of every 100 things he typed, and 32 of the slash commands left no record at
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
    for name in ("alpha", "beta"):
        (kb / "projects" / name).mkdir(parents=True)
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


def his(said):
    return [text for kind, text in said if kind == "user"]


def test_the_shapes_a_transcript_holds_his_words_in(harness):
    rows = [json.loads(line.replace("{WORK}", harness["work"]).replace("{KB}", harness["kb"])) for line in SHAPES.read_text(encoding="utf-8").splitlines()]
    said, meta = exported(harness, rows)
    assert his(said) == ["Please plan the release.", "Also bump the version.", "And tag it.", "/day-start", "/review the last change",
                         "/day-start", "Please also check the tests."]
    assert not [text for kind, text in said if kind == "brief"]
    assert meta["projects"] == ["alpha", "beta"]
    listed = [p["text"] for p in sessions.prompts("acme", "2026-11-13")]
    assert listed == his(said)                                             # the day's list of what he typed holds each


def test_a_prompt_typed_while_a_turn_runs_is_his(harness):
    said, _ = exported(harness, [typed(harness, "Start the build."), queued(harness, "Also bump the version."),
                                 queued(harness, [{"type": "text", "text": "And tag it."}, {"type": "text", "text": "Then stop."}]),
                                 queued(harness, "<pasted_content id=\"a1\">a log he pasted</pasted_content>")])
    assert his(said) == ["Start the build.", "Also bump the version.", "And tag it.\nThen stop.", "<pasted_content id=\"a1\">a log he pasted</pasted_content>"]
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
def test_a_queued_command_that_is_not_his_prompt_stays_what_it_was(harness, prompt, more):
    said, _ = exported(harness, [typed(harness, "Start the build."), queued(harness, prompt, **more)])
    assert his(said) == ["Start the build."] and not [text for kind, text in said if kind == "brief"]


def test_a_queued_prompt_that_names_no_origin_is_his_unless_an_agent_wrote_it(harness):
    said, _ = exported(harness, [queued(harness, "Carry on from the plan.", origin=None),
                                 queued(harness, "<agent-message from=\"reviewer\">Round two is back.</agent-message>", origin=None),
                                 queued(harness, "<cross-session-message from=\"s-1\">The branch is yours.</cross-session-message>", origin=None)])
    assert his(said) == ["Carry on from the plan."]
    assert [kind for kind, text in said if "Round two" in text or "branch is yours" in text] == ["brief", "brief"]


def test_a_sub_agents_queued_prompt_is_a_brief(harness):
    said, _ = exported(harness, [{**queued(harness, "Check the second file too."), "isSidechain": True}])
    assert said == [("brief", "Check the second file too.")]


def test_a_slash_command_that_reaches_the_agent_is_his_prompt_as_he_typed_it(harness):
    def command(name, args=None, **more):
        text = f"<command-message>{name}</command-message>\n<command-name>/{name}</command-name>" + (f"\n<command-args>{args}</command-args>" if args is not None else "")
        return row(harness, "user", message={"role": "user", "content": text}, **more)
    text = row(harness, "user", isMeta=True, message={"role": "user", "content": [{"type": "text", "text": "Run the ritual."}]})
    said, _ = exported(harness, [command("day-start"), text, command("review", "the last change\nand its tests"), text, command("day-start"), text,
                                 command("plugin:skill-name", "  "), command("hidden", isMeta=True)])
    assert his(said) == ["/day-start", "/review the last change\nand its tests", "/day-start", "/plugin:skill-name"]   # the same command twice is two prompts
    assert ("system", "Run the ritual.") in said and not any("hidden" in text for text in his(said))


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
    assert his(said) == [] and said and said[0][0] == "system"


def test_words_after_a_system_reminder_in_one_block_are_his(harness):
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
    assert his(said) == ["Please also check the tests.", "Then ship it.",
                         "Keep this whole: <system-reminder>quoted</system-reminder> is what the tag looks like.", "A block of its own."]
    kept = [text for kind, text in said if kind == "system"]
    assert any("The date has changed." in text and "check the tests" not in text for text in kept)   # the reminder stays, apart
    assert not any("Please do not file this." in text for text in his(said))


def test_a_reminder_then_his_words_is_no_prompt_for_a_sub_agent_or_a_meta_row(harness):
    text = "<system-reminder>note</system-reminder>\nCheck the second file too."
    said, _ = exported(harness, [{**typed(harness, text), "isSidechain": True}, {**typed(harness, text + " (meta)"), "isMeta": True}])
    assert his(said) == [] and ("brief", "Check the second file too.") in said


def test_a_session_belongs_to_the_projects_its_tool_calls_wrote_into(harness):
    kb = harness["kb"]
    said, meta = exported(harness, [
        typed(harness, "Update the plan."),
        called(harness, "Read", {"file_path": f"{kb}/projects/beta/CONTEXT.md"}),                  # reading tags nothing
        called(harness, "Bash", {"command": f"cat {kb}/projects/beta/CONTEXT.md | head -3"}),
        called(harness, "Write", {"file_path": f"{kb}/projects/gamma/CONTEXT.md", "content": "x"}),  # no such project folder
        called(harness, "Write", {"file_path": f"{kb}/projects/index.yaml", "content": "x"}),        # a file beside the projects
        called(harness, "Write", {"file_path": f"{harness['work']}/projects/alpha/notes.md", "content": "x"}),  # a folder of that name elsewhere
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
    assert his(said) == ["Update the plan."] and meta["projects"] == ["alpha"]
    assert meta["skipped"]["a tool call whose written files could not be read"] == 1


@pytest.mark.parametrize("given", [None, "text", 7, [], {"file_path": 7}, {"file_path": None}, {"command": ["echo", "x"]}, {"command": None}, {"file_path": "relative.md"}])
def test_a_tool_call_of_another_shape_tags_nothing_and_stops_nothing(harness, given):
    for tool in ("Write", "Bash", "Unknown"):
        said, meta = exported(harness, [typed(harness, f"With {tool}."), called(harness, tool, given)])
        assert f"With {tool}." in his(said) and not meta.get("projects")

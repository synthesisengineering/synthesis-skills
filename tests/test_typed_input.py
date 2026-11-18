"""22.20, review round 1: what Codex's `write_stdin` types into a session is judged as a command line.

Codex starts a long-running process with `exec_command` (on a terminal with `tty: true`) and types into it with
`write_stdin`, which carries the characters and the session's number. The guard judged only `exec_command`, so
`exec_command {cmd: "bash", tty: true}` and then `write_stdin {chars: "echo '{}' > ~/.synthesis/v5/config.json\\n"}`
wrote the guard's own settings with no code, and reached everything else the shell guard protects (the review, round 1).
A typed line is now judged as that session would run it: in the folder its `exec_command` named, found by the session's
number in the record; typed into a shell, as a command line; typed into an interpreter or another program, as that
program's input. A session the record does not show, or a shell whose folder or variables a typed line changed, is
judged conservatively: only a line that just reads goes without a code.
"""

import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from synthesis import approvals, guards, paths

CONFIG = {"own_repos": ["me-owner/*"]}
HELD = "approve followed by the code"
SETTINGS = "guard's own settings"


def _iso(when: float) -> str:
    return datetime.fromtimestamp(when, timezone.utc).isoformat().replace("+00:00", "Z")


@pytest.fixture
def codex(tmp_path, monkeypatch):
    """A home laid out as on a Mac and a Codex session's record (its rollout), which the hook's payload names."""
    home = tmp_path / "home"
    v5 = home / ".synthesis" / "v5"
    for key, value in (("HOME", home), ("SYNTHESIS_HOME", v5), ("CLAUDE_CONFIG_DIR", home / ".claude"),
                       ("CODEX_HOME", home / ".codex"), ("XDG_DATA_HOME", home / ".local" / "share"),
                       ("SYNTHESIS_CLAUDE_DESKTOP_DIR", home / "Library" / "Application Support" / "Claude")):
        monkeypatch.setenv(key, str(value))
    (v5 / "git-hooks").mkdir(parents=True)
    (v5 / "git-hooks" / "pre-commit").write_text("#!/bin/sh\nexec true\n", encoding="utf-8")
    (v5 / "config.json").write_text("{}\n", encoding="utf-8")
    (paths.approvals() / "grants").mkdir(parents=True)
    work = tmp_path / "work"
    work.mkdir()
    rollout = home / ".codex" / "sessions" / "2026" / "11" / "15" / "rollout-2026-11-15T10-00-00-01a18a2b-0000-7000-8000-0000000000c1.jsonl"
    rollout.parent.mkdir(parents=True)
    now = time.time()
    rows = [{"type": "session_meta", "timestamp": _iso(now - 60), "payload": {"id": "c1", "cwd": str(work), "cli_version": "0.167.0"}}]
    rollout.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")

    def add(*rows_):
        with rollout.open("a", encoding="utf-8") as handle:
            for r in rows_:
                handle.write(json.dumps({"timestamp": _iso(time.time()), **r}) + "\n")

    def started(cmd: str, workdir=None, session_id: int = 7, tty: bool = True, code_mode: bool = False):
        """An exec_command that started a session, and the output that gave its number, as Codex records them."""
        args = {"cmd": cmd, "tty": tty, **({"workdir": str(workdir)} if workdir else {})}
        ident = f"call_{time.time_ns()}"
        if code_mode:
            fields = ", ".join(f"{k}: {json.dumps(v)}" for k, v in args.items())
            result = json.dumps({"chunk_id": "a1", "wall_time_seconds": 0.2, "session_id": session_id, "output": ""})
            add({"type": "response_item", "payload": {"type": "custom_tool_call", "name": "exec", "call_id": ident,
                                                      "input": f"const r = await tools.exec_command({{{fields}}});\ntext(JSON.stringify(r));"}},
                {"type": "response_item", "payload": {"type": "custom_tool_call_output", "call_id": ident,  # as Codex keeps it:
                                                      "output": json.dumps([{"type": "input_text", "text": result}])}})  # JSON in JSON
        else:
            add({"type": "response_item", "payload": {"type": "function_call", "name": "exec_command", "call_id": ident,
                                                      "arguments": json.dumps(args)}},
                {"type": "response_item", "payload": {"type": "function_call_output", "call_id": ident,
                                                      "output": f"Chunk ID: a1\nWall time: 0.2 seconds\nProcess running with session ID {session_id}\nOutput:\n"}})

    def typed_before(chars: str, session_id: int = 7, code_mode: bool = False):
        """A write_stdin into the session earlier in the record."""
        ident = f"call_{time.time_ns()}"
        if code_mode:
            add({"type": "response_item", "payload": {"type": "custom_tool_call", "name": "exec", "call_id": ident,
                                                      "input": f"await tools.write_stdin({{session_id: {session_id}, chars: {json.dumps(chars)}}});"}})
        else:
            add({"type": "response_item", "payload": {"type": "function_call", "name": "write_stdin", "call_id": ident,
                                                      "arguments": json.dumps({"session_id": session_id, "chars": chars})}})

    def approve(reason: str):
        """The principal types approve <code> in the Codex session; the prompt hook grants it."""
        code = re.search(r"\bcode ([a-z0-9]{6})\b", reason).group(1)
        time.sleep(0.01)
        add({"type": "event_msg", "payload": {"type": "item_completed", "item": {"type": "UserMessage", "content": [
            {"type": "text", "text": f"approve {code}"}]}}})
        return approvals.grant_from_prompt(f"approve {code}", str(rollout))

    session = {"session_id": "019a-codex-thread", "transcript_path": str(rollout), "tool_use_id": "call_current"}
    return {"home": home, "v5": v5, "work": work, "rollout": rollout, "started": started, "typed_before": typed_before,
            "approve": approve, "session": session, "add": add}


def _typed(codex, chars: str, session_id=7, cwd=None):
    return guards.check("write_stdin", {"session_id": session_id, "chars": chars, "yield_time_ms": 250}, CONFIG,
                        cwd=str(cwd or codex["work"]), session=codex["session"])


def _held(reason, what: str = "") -> bool:
    return bool(reason) and HELD in reason and what in reason and not reason.startswith("Refused")


# --- a session the record shows -------------------------------------------------------------------------------------

@pytest.mark.parametrize("code_mode", [False, True], ids=["a function call", "a code-mode script"])
def test_a_line_typed_into_a_shell_is_judged_in_the_folder_its_session_started_in(codex, code_mode):
    codex["started"]("bash", workdir=codex["v5"], code_mode=code_mode)
    assert _held(_typed(codex, "echo '{}' > config.json\n"), SETTINGS)
    assert _typed(codex, "echo '#!/bin/sh' > git-hooks/pre-commit\n").startswith("Refused")  # the runtime's own folder (A8)
    codex["started"]("zsh -l", workdir=codex["work"], session_id=8, code_mode=code_mode)
    assert _typed(codex, "echo '{}' > config.json\n", session_id=8) is None  # a project's own file, where that shell stands
    assert _typed(codex, "ls -la && git status\n", session_id=8) is None


def test_a_typed_line_is_judged_by_every_shell_guard(codex):
    codex["started"]("bash", workdir=codex["work"])
    assert _typed(codex, f"echo x > {paths.approvals() / 'grants' / 'forged.json'}\n").startswith("Refused")
    assert "refusing a recursive delete" in _typed(codex, "rm -rf ~\n")
    assert _held(_typed(codex, "gh pr comment 5 -R someone-else/app --body 'Looks good to me.'\n"))
    assert _held(_typed(codex, "echo x > ~/.synthesis/v5/config.json\n"), SETTINGS)


def test_a_line_typed_into_an_interpreter_is_judged_as_its_program(codex):
    codex["started"]("python3", workdir=codex["work"])
    assert _held(_typed(codex, f"open({str(codex['v5'] / 'config.json')!r}, 'w').write('{{}}')\n"), SETTINGS)
    assert _typed(codex, "print(1 + 1)\n") is None
    codex["started"]("node", workdir=codex["work"], session_id=9)
    assert _held(_typed(codex, f"require('fs').writeFileSync({json.dumps(str(codex['v5'] / 'config.json'))}, '{{}}')\n", session_id=9))


def test_what_an_interpreter_was_typed_before_is_part_of_its_program(codex):
    """A REPL keeps its names: a path typed into one line and written by the next is one program."""
    codex["started"]("python3", workdir=codex["work"])
    codex["typed_before"](f"p = {str(codex['v5'] / 'config.json')!r}\n")
    assert _held(_typed(codex, "open(p, 'w').write('{}')\n"))


def test_a_line_typed_into_another_program_is_a_command_line_where_it_stands(codex):
    codex["started"]("ssh build-host", workdir=codex["work"])  # another machine's shell: every shell guard still reads it
    assert _held(_typed(codex, "echo x > ~/.synthesis/v5/config.json\n"))
    assert _typed(codex, "uptime\n") is None
    codex["started"]("python3 -u console.py", workdir=codex["work"], session_id=9)  # a program's own prompt
    assert _typed(codex, "status\n", session_id=9) is None
    assert _held(_typed(codex, "~/.synthesis/v5/config.json\n", session_id=9))  # a protected path fed to it


@pytest.mark.parametrize("start", ["ssh localhost", "ssh -p 2222 me@127.0.0.1", "docker exec -it box bash", "kubectl exec -it pod -- sh"])
def test_a_shell_in_a_container_or_on_this_machine_by_ssh_is_judged_conservatively(codex, start):
    """Its folder is not the one it started in: ssh to this machine logs in at the home folder, and a container's folders
    may be this machine's, mounted."""
    codex["started"](start, workdir=codex["work"])
    assert _held(_typed(codex, "echo '{}' > .synthesis/v5/config.json\n"))
    assert _held(_typed(codex, "uptime\n"))
    assert _typed(codex, "ls -la\n") is None


def test_an_interpreter_started_after_a_cd_is_judged_where_the_cd_leads(codex):
    codex["started"](f"cd {codex['v5']} && python3", workdir=codex["work"])
    assert _held(_typed(codex, "open('config.json', 'w').write('{}')\n"), SETTINGS)
    assert _typed(codex, "print('ready')\n") is None


def test_a_poll_and_keys_that_start_nothing_need_no_code(codex):
    for chars in ("", "\x03", "\x04", "\n", "\r", "\x03\n"):
        assert _typed(codex, chars) is None, repr(chars)


# --- a session the record does not show, or whose folder changed ----------------------------------------------------

def test_a_session_the_record_does_not_show_is_judged_conservatively(codex):
    assert _held(_typed(codex, "echo '{}' > ~/.synthesis/v5/config.json\n"), SETTINGS)
    assert _held(_typed(codex, "echo '{}' > config.json\n"))  # where that lands, nothing says
    assert _held(_typed(codex, "python3 tool.py\n"))
    for line in ("ls -la\n", "git status\n", "cat notes.md\n", "echo done\n"):
        assert _typed(codex, line) is None, line


def test_a_claude_record_names_no_codex_session(codex, tmp_path):
    """The review's probe: a shell started on a terminal, then a write typed into it, under a session whose record shows
    no Codex session at all."""
    record = tmp_path / "claude" / "S.jsonl"
    record.parent.mkdir()
    record.write_text(json.dumps({"type": "user", "message": {"role": "user", "content": "hi"}}) + "\n", encoding="utf-8")
    session = {"session_id": "S", "transcript_path": str(record)}
    verdict = guards.check("write_stdin", {"session_id": 1, "chars": "echo '{}' > ~/.synthesis/v5/config.json\n"}, CONFIG,
                           cwd=str(codex["work"]), session=session)
    assert _held(verdict, SETTINGS)


@pytest.mark.parametrize("earlier", ["cd ~/.synthesis/v5\n", "pushd ~/.synthesis/v5\n", "D=~/.synthesis/v5\n",
                                     "export D=~/.synthesis/v5\n", "alias e='echo'\n", "source ~/x.sh\n",
                                     "~/.synthesis/v5\n"])  # a bare folder name, which zsh takes as cd
def test_a_shell_whose_folder_or_variables_a_typed_line_changed_is_judged_conservatively(codex, earlier):
    codex["started"]("bash", workdir=codex["work"])
    codex["typed_before"](earlier)
    assert _held(_typed(codex, "echo '{}' > config.json\n"))
    assert _held(_typed(codex, "echo '{}' > \"$D/config.json\"\n"))
    assert _typed(codex, "ls -la\n") is None


def test_a_line_split_across_calls_is_judged_whole(codex):
    codex["started"]("bash", workdir=codex["work"])
    codex["typed_before"]("echo '{}' > ~/.synth")  # typed, not yet submitted
    assert _held(_typed(codex, "esis/v5/config.json\n"), SETTINGS)


@pytest.mark.parametrize("chars", ["echo x > ~/.synthesis/v5/config.jsonX\x7f\n", "echo x > ~/.synth\t\n", "\x1b[A\n",
                                   "echo x > ~/.synthesis/v5/config.json\x1b[D\x1b[Dx\n", "!!\n", "!echo\n", "^git^gzip\n",
                                   "fc -s\n", "r\n"])
def test_keys_that_edit_complete_or_recall_a_line_wait(codex, chars):
    codex["started"]("bash", workdir=codex["work"])
    assert _held(_typed(codex, chars)), repr(chars)


@pytest.mark.parametrize("chars", ["echo 'done!'\n", "[ a != b ] && echo differ\n", "git log -1 --format='%h!'\n"])
def test_an_exclamation_mark_that_recalls_nothing_needs_no_code(codex, chars):
    codex["started"]("bash", workdir=codex["work"])
    assert _typed(codex, chars) is None, repr(chars)


def test_the_principals_code_lets_that_typed_line_through_once(codex):
    codex["started"]("bash", workdir=codex["v5"])
    line = "echo '{}' > config.json\n"
    held = _typed(codex, line)
    assert _held(held, SETTINGS)
    codex["typed_before"](line)  # Codex records the held call too
    codex["approve"](held)
    assert _typed(codex, line) is None  # that line, once
    assert _held(_typed(codex, line), SETTINGS)


def test_the_hook_holds_a_typed_write_of_the_settings(codex, capsys):
    from synthesis import hook
    codex["started"]("bash", workdir=codex["v5"])
    hook.pre_tool_use({"tool_name": "write_stdin", "tool_input": {"session_id": 7, "chars": "echo '{}' > config.json\n"},
                       "cwd": str(codex["work"]), "hook_event_name": "PreToolUse", **codex["session"]})
    out = json.loads(capsys.readouterr().out)["hookSpecificOutput"]
    assert out["permissionDecision"] == "deny" and HELD in out["permissionDecisionReason"]


def test_write_stdin_reaches_the_hook():
    hooks = json.loads((Path(__file__).resolve().parents[1] / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    assert re.fullmatch(hooks["hooks"]["PreToolUse"][0]["matcher"], "write_stdin")


# --- the binding gap, on the open list ------------------------------------------------------------------------------

@pytest.mark.xfail(strict=True, reason="open: a code binds the scripts a command runs, not the files named inside them; "
                                       "it closes when 22.21's reading of the scripts a command runs is merged")
def test_an_installer_script_binds_the_settings_file_it_copies(codex, tmp_path, monkeypatch):
    """The review's probe: a script copies a settings file it names only inside itself, so a code for running it is not
    bound to that file; changed after the approval, the identical command still runs on the old code."""
    work, v5 = codex["work"], codex["v5"]
    record = tmp_path / "claude-config" / "projects" / "-work" / "S-principal.jsonl"
    record.parent.mkdir(parents=True)
    record.touch()
    monkeypatch.setenv("SYNTHESIS_SESSION", "S-principal")
    paths.write_json(paths.approvals() / "records" / "S-principal.json", {"path": str(record)})
    me = {"session_id": "S-principal", "transcript_path": str(record)}
    (work / "v5-config.json").write_text('{"send_tools": ["approved"]}\n', encoding="utf-8")
    (work / "install.sh").write_text(f'#!/bin/sh\ncp v5-config.json "{v5}/config.json"\n', encoding="utf-8")
    reason = guards.check("Bash", {"command": "bash install.sh"}, CONFIG, cwd=str(work), session=me)
    assert HELD in reason
    code = re.search(r"\bcode ([a-z0-9]{6})\b", reason).group(1)
    when = (datetime.now(timezone.utc) + timedelta(milliseconds=5)).isoformat()
    with record.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"type": "user", "timestamp": when, "origin": {"kind": "human"}, "sessionId": "S-principal",
                                 "message": {"role": "user", "content": f"approve {code}"}}) + "\n")
    approvals.grant_from_prompt(f"approve {code}")
    (work / "v5-config.json").write_text('{"send_tools": ["changed after the approval"]}\n', encoding="utf-8")
    assert guards.check("Bash", {"command": "bash install.sh"}, CONFIG, cwd=str(work), session=me), (
        "the installer's run went on its code after the settings file it copies was changed")

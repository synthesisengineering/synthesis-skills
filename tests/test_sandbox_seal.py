"""The guard's sandbox, part 1 (BACKLOG C1; the principal's eight rulings of 2026-11-15 on that day's design note).

Every record an approval rests on moves into one sealed folder, `approvals/`, which only the hook writes, and what only
the installer writes into `install/`: a harness's operating-system sandbox then keeps every shell out of both. The
installer and the first hook that finds the old layout move it there, once. A shell files a request beside its working
state (`state/requests`), which grants nothing until the principal types its code; the hook grants it, and itself applies
what a typed code approves whose effect is a sealed record (a commit line, a send window, a batch). A process that
cannot write the sealed folder spends no approval and says why. A command a harness would run outside its sandbox waits
for the principal's code of exactly that command, and a Muse session gets no approval until Muse's sandbox is shown to
seal the folders.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from synthesis import approvals, commit_check, guards, hook, install, paths, sends

ROOT = Path(__file__).resolve().parents[1]
SESSION = {"session_id": "S-principal"}
LINE = (b"notes.md", 3, b"Kickoff with Bluebird next week")
JIRA = ("mcp__85ff__addCommentToJiraIssue", {"issueIdOrKey": "AB-1", "commentBody": "Status is green."})


def _cli(*args):
    return subprocess.run([sys.executable, "-m", "synthesis.cli", *args], capture_output=True, text=True, cwd=ROOT)


def _payload(principal, **more) -> dict:
    return {"session_id": "S-principal", "transcript_path": str(principal.transcript), **more}


class _Seal:
    """The approvals folder as a harness's sandbox leaves it for a shell: there, and nothing in it writable."""

    def __init__(self):
        paths.approvals().mkdir(parents=True, exist_ok=True)

    def _each(self, change):
        for path in [paths.approvals(), *paths.approvals().rglob("*")]:
            path.chmod(change(path.stat().st_mode))

    def close(self):
        self._each(lambda mode: mode & ~0o222)

    def open(self):
        self._each(lambda mode: mode | 0o200)


@pytest.fixture
def sealed(isolated_home):
    if os.geteuid() == 0:
        pytest.skip("root writes a folder whatever its mode")
    seal = _Seal()
    yield seal
    seal.open()


# --- the layout (design 4.1) ---------------------------------------------------------------------------------------------

def test_the_sealed_records_live_in_folders_of_their_own(isolated_home, tmp_path, write_config):
    write_config({"commit_policy": str(tmp_path / "policy.yaml"), "line_allowances": str(tmp_path / "lines.json")})
    sealed, state = isolated_home / "approvals", isolated_home / "state"
    assert (paths.approvals(), paths.install_dir(), paths.requests()) == (sealed, isolated_home / "install", state / "requests")
    assert paths.codex_hooks_record() == isolated_home / "install" / "codex-user-hooks.json"
    assert paths.line_allowances() == sealed / "line-allowances.json"  # never a file a setting names in a shell's reach
    assert sends._window_file() == sealed / "sends" / "window.json" and sends._spends_file().parent == sealed / "sends"
    assert sends._batch_file("d").parent == sealed / "sends" / "batches" and sends._ticket_file("t").parent == sealed / "sends" / "sender"
    assert guards._last_deploy("site").parent == sealed / "deploys"
    assert guards._grants(SESSION) == sealed / "desktop" / "S-principal.json"
    assert guards._grants(SESSION, "typed") == sealed / "typed" / "S-principal.json"
    assert install._grant_file(isolated_home, "5.30.0").parent == sealed / "release-grants"
    for folder in (sealed, isolated_home / "install"):
        assert str(folder) in guards._protected_roots({})


def test_the_hook_files_and_grants_in_the_sealed_folder(principal, isolated_home, monkeypatch):
    monkeypatch.setattr(approvals, "IN_HOOK", True)
    code = principal(guards.check(*JIRA, {}), grant=False)
    assert (isolated_home / "approvals" / "requests" / f"{code}.json").is_file()
    assert not (isolated_home / "state" / "requests" / f"{code}.json").exists()
    principal(f"code {code}")
    assert [p.parent.name for p in (isolated_home / "approvals").rglob("*.json") if p.parent.name == "grants"] == ["grants"]
    assert (isolated_home / "approvals" / "records" / "S-principal.json").is_file()  # the prompt hook's map of records
    assert approvals.transcript(SESSION) == str(principal.transcript)
    state = {p.name for p in (isolated_home / "state").iterdir()} if (isolated_home / "state").is_dir() else set()
    assert not state & {"approvals", "approval-requests", "transcripts", "approvals.lock", "sends", "browser.json"}


def test_the_turn_end_marker_is_sealed(isolated_home):
    env = {**os.environ, "SYNTHESIS_HOME": str(isolated_home)}
    lazy = {"session_id": "s1", "last_assistant_message": "Leaving that for now."}
    done = subprocess.run([sys.executable, "-S", str(ROOT / "synthesis" / "hook.py"), "stop"], input=json.dumps(lazy),
                          capture_output=True, text=True, env=env)
    assert json.loads(done.stdout)["decision"] == "block"
    assert (isolated_home / "approvals" / "stop" / "s1.json").is_file() and not (isolated_home / "state" / "stop").exists()


# --- the move from the old layout, once, by the installer and the hook ----------------------------------------------------

OLD = {"approvals/aa.json": "grants/aa.json", "approval-requests/123abc.json": "requests/123abc.json",
       "transcripts/S1.json": "records/S1.json", "sends/window.json": "sends/window.json",
       "sends/2026-11-17.jsonl": "sends/2026-11-17.jsonl", "deploys/d.json": "deploys/d.json", "desktop/S1.json": "desktop/S1.json",
       "typed/S1.json": "typed/S1.json", "imessage-sends/k.json": "imessage-sends/k.json", "stop/S1.json": "stop/S1.json",
       "browser.json": "browser.json", "browser-accounts.json": "browser-accounts.json", "approvals.lock": "lock",
       "release-grants/r.json": "release-grants/r.json"}


def _old_layout(home: Path, tmp_path: Path, write_config) -> None:
    for name in OLD:
        (home / "state" / name).parent.mkdir(parents=True, exist_ok=True)
        (home / "state" / name).write_text(json.dumps({"was": name}), encoding="utf-8")
    (home / "state" / "codex-user-hooks.json").write_text('{"was": "codex"}', encoding="utf-8")
    (home / "state" / "harness-approvals.json").write_text("{}", encoding="utf-8")
    (tmp_path / "policy.yaml").write_text("config_version: 2\n", encoding="utf-8")
    (tmp_path / "line-allowances.json").write_text(json.dumps({"lines": {"fp1": "2026-11-01"}}), encoding="utf-8")
    write_config({"commit_policy": str(tmp_path / "policy.yaml")})


def test_the_installer_moves_the_old_layout_into_the_sealed_folders_once(isolated_home, tmp_path, write_config):
    _old_layout(isolated_home, tmp_path, write_config)
    assert sorted(paths.old_approvals()) == sorted({name.split("/")[0] for name in OLD})
    moved = install.move_approvals(isolated_home)
    assert moved and paths.old_approvals() == []
    for old, new in OLD.items():
        assert json.loads((isolated_home / "approvals" / new).read_text(encoding="utf-8")) == {"was": old}, new
        assert not os.path.lexists(isolated_home / "state" / old.split("/")[0])
    assert json.loads((isolated_home / "install" / "codex-user-hooks.json").read_text(encoding="utf-8")) == {"was": "codex"}
    assert json.loads(paths.line_allowances().read_text(encoding="utf-8")) == {"lines": {"fp1": "2026-11-01"}}
    assert (isolated_home / "state" / "harness-approvals.json").is_file()  # working state stays
    # Once: what a shell writes in the old places afterwards is never taken into the sealed folders.
    paths.write_json(isolated_home / "state" / "approvals" / "bb.json", {"kind": "send"})
    (tmp_path / "line-allowances.json").write_text(json.dumps({"lines": {"fp2": "2026-11-02"}}), encoding="utf-8")
    assert paths.old_approvals() == [] and install.move_approvals(isolated_home) == []
    assert not (isolated_home / "approvals" / "grants" / "bb.json").exists()
    assert json.loads(paths.line_allowances().read_text(encoding="utf-8")) == {"lines": {"fp1": "2026-11-01"}}


def test_a_home_with_no_old_records_gets_an_empty_store_of_lines(isolated_home, tmp_path, write_config):
    write_config({"line_allowances": str(tmp_path / "absent.json")})
    (isolated_home / "state").mkdir(parents=True)
    (isolated_home / "state" / "approvals").mkdir()
    install.move_approvals(isolated_home)
    assert json.loads(paths.line_allowances().read_text(encoding="utf-8")) == {"lines": {}}


def test_the_first_hook_event_moves_the_old_layout(isolated_home, tmp_path, write_config):
    _old_layout(isolated_home, tmp_path, write_config)
    env = {**os.environ, "SYNTHESIS_HOME": str(isolated_home)}
    done = subprocess.run([sys.executable, "-S", str(ROOT / "synthesis" / "hook.py"), "user-prompt-submit"],
                          input=json.dumps({"session_id": "S1", "prompt": "carry on"}), capture_output=True, text=True, env=env)
    assert done.returncode == 0
    assert (isolated_home / "approvals" / "grants" / "aa.json").is_file() and paths.old_approvals() == []


def test_an_install_moves_the_old_layout_before_anything_else(isolated_home, tmp_path, write_config):
    _old_layout(isolated_home, tmp_path, write_config)
    try:
        install.install(ROOT)
    except (install.Unapproved, install.Refused):
        pass  # a home that shows a runtime waits for the principal's code; the move does not
    assert (isolated_home / "approvals" / "records" / "S1.json").is_file() and paths.old_approvals() == []


# --- requests a shell files, and what only the hook spends (design 2.3 and 4.5) --------------------------------------------

def test_a_shells_request_is_filed_beside_its_state_and_named_as_a_shells_when_granted(principal, isolated_home):
    code = approvals.request("message-gap-review", {"rows": [1]}, "close the gaps of rows 1")
    assert (paths.requests() / f"{code}.json").is_file() and not (paths.approvals() / "requests" / f"{code}.json").exists()
    assert code in approvals.pending()
    said = principal(f"code {code}")
    assert len(said) == 1 and said[0].startswith("close the gaps of rows 1") and "a shell command filed" in said[0]
    assert not (paths.requests() / f"{code}.json").exists() and approvals.granted("message-gap-review", {"rows": [1]})


def test_a_shells_request_under_a_code_the_hook_filed_is_never_granted(principal, monkeypatch):
    monkeypatch.setattr(approvals, "IN_HOOK", True)
    code = approvals.request("send", {"to": "a"}, "the guard's own request")
    monkeypatch.setattr(approvals, "IN_HOOK", False)
    paths.write_json(paths.requests() / f"{code}.json", {"kind": "send", "digest": approvals.digest("send", {"to": "b"}),
                                                         "summary": "planted", "at": time.time(), "by": "shell"})
    assert principal(f"code {code}") == ["the guard's own request"]
    assert approvals.grant("send", {"to": "a"}) and not approvals.grant("send", {"to": "b"})


def test_a_process_that_cannot_write_the_sealed_folder_spends_nothing_and_says_why(principal, sealed):
    code = approvals.request("send", {"to": "a"}, "a send")
    principal(f"code {code}")
    sealed.close()
    with pytest.raises(approvals.Sealed, match="sealed"):
        approvals.consume("send", {"to": "a"})
    with pytest.raises(approvals.Sealed, match="sealed"):
        approvals.void("send", {"to": "a"})
    with pytest.raises(approvals.Sealed, match="sealed"):
        with approvals.alone():
            pass
    later = approvals.request("send", {"to": "c"}, "another send")  # filing a request still works there
    assert (paths.requests() / f"{later}.json").is_file()
    sealed.open()
    assert approvals.consume("send", {"to": "a"})  # nothing was spent while it was sealed


def test_a_typed_grant_is_read_without_being_spent(principal):
    code = approvals.request("sessions-lost", "claude-code S9", "accept the loss of claude-code S9")
    principal(f"code {code}")
    assert approvals.granted("sessions-lost", "claude-code S9", SESSION) and approvals.granted("sessions-lost", "claude-code S9", SESSION)
    assert not approvals.granted("sessions-lost", "claude-code S8", SESSION)
    assert not hasattr(approvals, "backed")


def test_each_code_the_hook_spends_is_kept_in_the_granted_ledger(principal):
    code = approvals.request("send", {"to": "a"}, "a send")
    principal(f"code {code}")
    assert approvals.consume("send", {"to": "a"}, SESSION)
    row = json.loads((paths.approvals() / "granted.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert (row["code"], row["kind"], row["digest"], row["summary"]) == (code, "send", approvals.digest("send", {"to": "a"}), "a send")
    assert row["record"] == str(principal.transcript) and len(row["line"]) == 64 and row["typed"] <= time.time()


def test_a_commit_line_is_approved_by_the_hook_and_never_by_the_commit_check(principal, sealed, tmp_path):
    store = paths.line_allowances()
    sealed.close()  # the commit check runs in the agent's shell
    found = commit_check.unapproved([LINE], "github.com/o/r", store, {})
    assert len(found) == 1 and "type approve followed by the code" in found[0] and not store.exists()
    assert commit_check.unapproved([LINE], "github.com/o/r", store, {}) == found  # asked again, the same code
    sealed.open()
    principal(found[0])
    assert not store.exists()  # nothing is approved before the hook reads the code in the session's record
    took = hook.apply_effects(_payload(principal))
    assert len(took) == 1 and "notes.md" in took[0]
    assert commit_check.unapproved([LINE], "github.com/o/r", store, commit_check.read_allowances(store)) == []
    assert commit_check.unapproved([(b"notes.md", 4, b"Bluebird again")], "github.com/o/r", store, commit_check.read_allowances(store))
    assert hook.apply_effects(_payload(principal)) == []  # once


def test_the_next_tool_call_or_turn_end_applies_what_a_code_approved(principal, tmp_path, capsys):
    store = paths.line_allowances()
    principal(commit_check.unapproved([LINE], "github.com/o/r", store, {})[0])
    assert hook.pre_tool_use(_payload(principal, tool_name="Bash", tool_input={"command": "ls"}, cwd=str(tmp_path))) == 0
    assert len(commit_check.read_allowances(store)) == 1
    other = (b"notes.md", 9, b"Bluebird elsewhere")
    principal(commit_check.unapproved([other], "github.com/o/r", store, commit_check.read_allowances(store))[0])
    hook.stop(_payload(principal, last_assistant_message="Done."))
    assert len(commit_check.read_allowances(store)) == 2


def test_a_send_window_opens_on_the_principals_code_by_the_hook(principal, sealed):
    sealed.close()  # the command runs in the agent's shell
    asked = _cli("sends", "open", "--hours", "3", "--sends", "4", "--channels", "jira,bitbucket")
    assert asked.returncode == 0 and "type approve followed by the code" in asked.stdout and sends.window() == {}
    sealed.open()
    principal(asked.stdout)
    assert sends.window() == {}
    took = hook.apply_effects(_payload(principal))
    assert sends.window()["channels"] == ["bitbucket", "jira"] and sends.window()["sends"] == 4 and "send window" in took[0]
    assert hook.apply_effects(_payload(principal)) == []


def test_a_shell_ends_a_window_early_and_never_extends_one(sealed):
    sends.open_window(3, ["jira"], count=2)  # as the hook opens it
    sealed.close()
    closed = _cli("sends", "close")
    assert closed.returncode == 0 and "send window closed" in closed.stdout and sends.window() == {}
    assert sends._window_file().is_file()  # the sealed record stays as the hook wrote it
    sealed.open()
    sends.open_window(3, ["jira"], count=2)
    assert sends.window()  # a mark older than the window closes nothing
    paths.write_json(paths.state() / "sends-closed.json", {"at": time.time() + 3600})
    assert sends.window()  # nor does one dated ahead


def test_a_batch_opens_on_the_principals_code_by_the_hook(principal, sealed, tmp_path):
    from synthesis import board
    board.touch("S-principal", project="inbox")
    file = tmp_path / "replies.json"
    entry = {"tool": "mcp__slack__slack_send_message", "input": {"channel_id": "D0123", "message": "Tuesday works."}}
    file.write_text(json.dumps({"batch": "replies", "project": "inbox", "entries": [entry]}), encoding="utf-8")
    sealed.close()
    asked = _cli("--session", "S-principal", "sends", "batch", str(file))
    assert asked.returncode == 0 and "type approve followed by the code" in asked.stdout and sends.batches() == []
    sealed.open()
    principal(asked.stdout)
    file.write_text("{}", encoding="utf-8")  # the request carries the batch: the file no longer matters
    took = hook.apply_effects(_payload(principal))
    assert [b["batch"] for b in sends.batches()] == ["replies"] and "batch" in took[0]
    assert sends.batches()[0]["session"] == "S-principal"
    sealed.close()
    assert _cli("sends", "close").returncode == 0 and sends.batches() == []


def test_the_guard_lets_the_sends_commands_run_since_they_only_ask(tmp_path):
    for command in ("synthesis sends open --hours 6 --sends 4 --channels jira", f"synthesis sends batch {tmp_path / 'b.json'}",
                    "synthesis sends close", "synthesis --session S1 sends open --hours=6 --sends=4 --channels=jira"):
        assert guards.check("Bash", {"command": command}, {}, cwd=str(tmp_path)) is None, command
    sneaky = "python3 -I -c 'from synthesis import sends; sends.open_window(12, [\"all\"], count=50)'"
    assert "send-window code" in guards.check("Bash", {"command": sneaky}, {}, cwd=str(tmp_path))


# --- ruling 2: a command outside the sandbox waits for the principal's code of exactly that command -------------------------

@pytest.mark.parametrize("tool, flag", [("Bash", {"dangerouslyDisableSandbox": True}),
                                        ("exec_command", {"sandbox_permissions": "require_escalated"}),
                                        ("shell", {"with_escalated_permissions": True}),
                                        ("mcp__terminal__run_in_terminal", {})])
def test_a_command_outside_the_sandbox_waits_for_the_code_of_exactly_it(tool, flag, principal, tmp_path):
    call = {"command": "ls -la", **flag}
    reason = guards.check(tool, call, {}, cwd=str(tmp_path))
    assert "sandbox" in reason and "`ls -la`" in reason and "type approve followed by the code" in reason
    principal(reason)
    assert "type approve followed by the code" in guards.check(tool, {**call, "command": "ls -l"}, {}, cwd=str(tmp_path))
    assert guards.check(tool, call, {}, cwd=str(tmp_path)) is None
    assert "type approve followed by the code" in guards.check(tool, call, {}, cwd=str(tmp_path))  # one run per code


def test_a_command_in_the_sandbox_waits_for_nothing_new(tmp_path):
    for tool, call in (("Bash", {"command": "ls -la", "dangerouslyDisableSandbox": False}), ("exec_command", {"cmd": "ls -la"}),
                       ("exec_command", {"cmd": "ls -la", "sandbox_permissions": "use_default"})):
        assert guards.check(tool, call, {}, cwd=str(tmp_path)) is None, call


def test_the_release_launchers_line_leaves_the_sandbox_with_no_code(tmp_path, monkeypatch):
    """Ruling 3: a release installs from the protected release tool with no code; the guard's own reading of the
    launcher's line (`_release_tool`, tested with the release grant) decides it."""
    line = "/home/me/.synthesis/v5/bin/synthesis-release --install-only --tag v5.30.0"
    monkeypatch.setattr(guards, "_release_tool", lambda command, cwd, session=None: {"--install-only": "", "--tag": "v5.30.0"}
                        if command == line else {})
    assert guards.check_unsandboxed("Bash", {"command": line, "dangerouslyDisableSandbox": True}, str(tmp_path)) is None
    assert guards.check_unsandboxed("Bash", {"command": line + " ", "dangerouslyDisableSandbox": True}, str(tmp_path))


# --- ruling 6: no approvals in a Muse session until its sandbox is verified -------------------------------------------------

def test_a_muse_session_gets_no_approval_and_is_told_where_to_run_the_call(principal, monkeypatch, tmp_path, capsys):
    code = approvals.request("send", {"to": "a"}, "a send")
    principal(f"code {code}")
    monkeypatch.setenv("MUSE_SESSION_ID", "S-principal")
    assert approvals.consume("send", {"to": "a"}, SESSION) is False and not approvals.granted("send", {"to": "a"}, SESSION)
    other = approvals.request("send", {"to": "b"}, "another send")
    hook.user_prompt_submit({"session_id": "S-principal", "prompt": f"approve {other}"})
    said = json.loads(capsys.readouterr().out)["hookSpecificOutput"]["additionalContext"]
    assert "Muse" in said and not approvals.grant("send", {"to": "b"}) and other in approvals.pending()
    hook.pre_tool_use({"session_id": "S-principal", "tool_name": "Bash", "cwd": str(tmp_path),
                       "tool_input": {"command": "ls", "dangerouslyDisableSandbox": True}})
    held = json.loads(capsys.readouterr().out)["hookSpecificOutput"]["permissionDecisionReason"]
    assert "Muse" in held and "Claude Code or Codex" in held
    assert hook.apply_effects({"session_id": "S-principal"}) == []

"""22.20: an agent's write of the guard's own settings, or of the global commit check's entry points, waits for the
principal's code.

`~/.synthesis/v5/config.json` holds the guard's own settings: the commit lines he approved (`line_allowances`), his own
repositories, the hosts his action sheets upload to, the signatures a send window lets through, the forbidden phrases,
the account each workspace acts as and the turn-end judge's settings. `~/.synthesis/v5/git-hooks` holds what git runs
before every commit, merge and commit message in every repository: the global commit check. A review on 2026-11-15
found that a file tool (Write, Edit, Codex's apply_patch, Muse's write_file) rewrote either with no code, and a second
review showed what a written setting reaches: the turn-end check made to run any program, the cloud judge made to post
to any host. A change to the guard's own settings changes what every approval means, so it waits for the principal's
code for that exact call, the private installer's copy included; reading them, and writing anywhere else, needs none.
"""

import json
import os
import re
import shlex
import time
from datetime import datetime, timedelta, timezone

import pytest

from synthesis import approvals, guards, paths

CONFIG = {}
HELD = "approve followed by the code"
GIT_HOOK = "#!/bin/sh\nexec true\n"
SETTINGS = "guard's own settings"
HOOKS = "commit check's entry points"


@pytest.fixture
def world(tmp_path, monkeypatch):
    """A home of the test's own, laid out as on a Mac: `~`, `$HOME` and `Path.home()` lead there, the synthesis home is
    `~/.synthesis/v5` with its config and the three git hooks the installer writes, and the session's transcript is
    where the prompt hook records it."""
    home = tmp_path / "home"
    v5 = home / ".synthesis" / "v5"
    for key, value in (("HOME", home), ("SYNTHESIS_HOME", v5), ("CLAUDE_CONFIG_DIR", home / ".claude"),
                       ("CODEX_HOME", home / ".codex"), ("XDG_DATA_HOME", home / ".local" / "share"),
                       ("SYNTHESIS_CLAUDE_DESKTOP_DIR", home / "Library" / "Application Support" / "Claude")):
        monkeypatch.setenv(key, str(value))
    monkeypatch.setenv("SYNTHESIS_SESSION", "S-principal")
    record = home / ".claude" / "projects" / "-work" / "S-principal.jsonl"
    record.parent.mkdir(parents=True)
    record.write_text(json.dumps({"type": "user", "message": {"role": "user", "content": "hello"}}) + "\n", encoding="utf-8")
    paths.write_json(paths.state() / "transcripts" / "S-principal.json", {"path": str(record)})  # as the prompt hook records it
    (v5 / "git-hooks").mkdir(parents=True)
    for name in ("pre-commit", "pre-merge-commit", "commit-msg"):
        (v5 / "git-hooks" / name).write_text(GIT_HOOK, encoding="utf-8")
    for name in ("board", "outbox"):
        (v5 / name).mkdir()
    (v5 / "config.json").write_text('{"sheet_hosts": ["example-sheets"]}\n', encoding="utf-8")
    work = tmp_path / "work"
    work.mkdir()
    (work / "v5-config.json").write_text('{"sheet_hosts": ["example-sheets", "another-host"]}\n', encoding="utf-8")
    (work / "hook.sh").write_text(GIT_HOOK, encoding="utf-8")
    (work / "write_settings.py").write_text(
        "from pathlib import Path\n(Path.home() / '.synthesis' / 'v5' / 'config.json').write_text('{}')\n", encoding="utf-8")
    (work / "v5").symlink_to(v5)  # links into the synthesis home, made beforehand
    (work / "hooks").symlink_to(v5 / "git-hooks")

    def approve(reason: str) -> list:
        """The principal types approve <code> in this session; the harness records it and the prompt hook grants it."""
        code = re.search(r"\bcode ([a-z0-9]{6})\b", reason).group(1)
        when = (datetime.now(timezone.utc) + timedelta(milliseconds=5)).isoformat()
        with record.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"type": "user", "timestamp": when, "origin": {"kind": "human"}, "sessionId": "S-principal",
                                     "message": {"role": "user", "content": f"approve {code}"}}) + "\n")
        time.sleep(0.01)
        return approvals.grant_from_prompt(f"approve {code}")

    return {"home": home, "v5": v5, "work": work, "record": record, "approve": approve,
            "session": {"session_id": "S-principal", "transcript_path": str(record)}}


def _spots(world) -> dict:
    v5, work = world["v5"], world["work"]
    return {"home": str(world["home"]), "v5": str(v5), "work": str(work), "config": shlex.quote(str(v5 / "config.json")),
            "config_raw": str(v5 / "config.json"), "hooks": shlex.quote(str(v5 / "git-hooks")), "hook": shlex.quote(str(v5 / "git-hooks" / "pre-commit"))}


def _verdict(world, line: str, cwd=None):
    return guards.check("Bash", {"command": line}, CONFIG, cwd=str(cwd or world["work"]), session=world["session"])


def _file(world, tool: str, tool_input: dict, cwd=None):
    return guards.check(tool, tool_input, CONFIG, cwd=str(cwd or world["work"]), session=world["session"])


def _held(reason, what: str = SETTINGS) -> bool:
    if what == HOOKS:  # the runtime's git-hooks folder is one of its protected folders (A8): a write there is refused outright
        return bool(reason) and reason.startswith("Refused")
    return bool(reason) and HELD in reason and what in reason and not reason.startswith("Refused")


# --- every file tool ----------------------------------------------------------------------------------------------

def _file_call(tool: str, path: str) -> dict:
    return {
        "Write": {"file_path": path, "content": "{}\n"},
        "Edit": {"file_path": path, "old_string": "example-sheets", "new_string": "other-sheets"},
        "MultiEdit": {"file_path": path, "edits": [{"old_string": "example-sheets", "new_string": "other-sheets"}]},
        "NotebookEdit": {"notebook_path": path, "new_source": "{}", "cell_id": "c1"},
        "write_file": {"path": path, "content": "{}\n"},  # Muse's
        "edit_file": {"path": path, "find": "example-sheets", "replace": "other-sheets"},  # Muse's
        "apply_patch": {"input": f"*** Begin Patch\n*** Update File: {path}\n@@\n-a\n+b\n*** End Patch"},  # Codex's
    }[tool]


FILE_TOOLS = ["Write", "Edit", "MultiEdit", "NotebookEdit", "write_file", "edit_file", "apply_patch"]
TARGETS = {"config.json": ("{v5}/config.json", SETTINGS), "a git hook": ("{v5}/git-hooks/pre-commit", HOOKS),
           "a git hook the installer never wrote": ("{v5}/git-hooks/post-checkout", HOOKS)}


@pytest.mark.parametrize("tool", FILE_TOOLS)
@pytest.mark.parametrize("target", sorted(TARGETS))
def test_each_file_tool_waits_for_the_code_to_write_the_settings(world, tool, target):
    path, what = TARGETS[target]
    reason = _file(world, tool, _file_call(tool, path.format(**_spots(world))))
    assert _held(reason, what), reason


FILE_SPELLINGS = {
    "through a link made beforehand": ("{work}/v5/config.json", SETTINGS),
    "through ..": ("{v5}/board/../config.json", SETTINGS),
    "in another case": ("{home}/.synthesis/V5/Config.JSON", SETTINGS),
    "with ~": ("~/.synthesis/v5/config.json", SETTINGS),
    "a hook through a link made beforehand": ("{work}/hooks/pre-commit", HOOKS),
    "a hook through ..": ("{v5}/git-hooks/../git-hooks/commit-msg", HOOKS),
    "a hook in another case": ("{v5}/Git-Hooks/PRE-COMMIT", HOOKS),
}


@pytest.mark.parametrize("spelling", sorted(FILE_SPELLINGS))
@pytest.mark.parametrize("tool", ["Write", "Edit", "apply_patch", "write_file"])
def test_a_file_tool_waits_for_the_settings_however_the_path_is_spelled(world, spelling, tool):
    path, what = FILE_SPELLINGS[spelling]
    assert _held(_file(world, tool, _file_call(tool, path.format(**_spots(world)))), what)


def test_a_relative_path_from_the_synthesis_home_and_a_patch_that_moves_or_deletes_wait(world):
    v5, work = world["v5"], world["work"]
    assert _held(_file(world, "Write", {"file_path": "config.json", "content": "{}"}, cwd=v5))
    assert _held(_file(world, "Edit", {"file_path": "git-hooks/pre-commit", "old_string": "true", "new_string": "false"}, cwd=v5), HOOKS)
    moved = f"*** Begin Patch\n*** Update File: {work}/notes.json\n*** Move to: {v5}/config.json\n@@\n-a\n+b\n*** End Patch"
    assert _held(_file(world, "apply_patch", {"input": moved}))
    gone = f"*** Begin Patch\n*** Delete File: {v5}/git-hooks/commit-msg\n*** End Patch"
    assert _held(_file(world, "apply_patch", {"input": gone}), HOOKS)
    added = f"*** Begin Patch\n*** Add File: {v5}/git-hooks/pre-push\n+#!/bin/sh\n*** End Patch"
    assert _held(_file(world, "apply_patch", {"command": added}), HOOKS)  # as Codex's own hook hands it


def test_the_hold_names_what_the_file_holds_and_how_to_go_on(world):
    config = _file(world, "Write", {"file_path": str(world["v5"] / "config.json"), "content": "{}"})
    for words in ("line allowances", "own repositories", "sheet hosts", "send-window signatures", "forbidden phrases",
                  "turn-end judge", "identical call"):
        assert words in config, words
    hook = _file(world, "Write", {"file_path": str(world["v5"] / "git-hooks" / "pre-commit"), "content": GIT_HOOK})
    assert _held(hook, HOOKS)  # refused with no code: the runtime's git-hooks folder is a protected one (A8)


def test_the_principals_code_lets_that_exact_write_through_once(world):
    call = {"file_path": str(world["v5"] / "config.json"), "content": '{"sheet_hosts": []}\n'}
    held = _file(world, "Write", call)
    assert _held(held)
    world["approve"](held)
    assert _file(world, "Write", call) is None  # the write he was shown
    again = _file(world, "Write", call)
    assert _held(again)  # once
    world["approve"](again)
    assert _held(_file(world, "Write", {**call, "content": '{"sheet_hosts": ["anywhere"]}\n'}))  # another write is a new one


def test_reading_the_settings_with_a_file_tool_is_no_write(world):
    assert _file(world, "Read", {"file_path": str(world["v5"] / "config.json")}) is None
    assert _file(world, "Read", {"file_path": str(world["v5"] / "git-hooks" / "pre-commit")}) is None


ORDINARY_FILE_WRITES = {
    "a project's file": ("Write", "{work}/notes.md"),
    "a project's own config.json": ("Write", "{work}/config.json"),
    "a project's own folder named git-hooks": ("Edit", "{work}/git-hooks/pre-commit"),
    "a copy beside the settings": ("Write", "{v5}/config.json.bak-2026-11-15"),
    "the outbox": ("write_file", "{v5}/outbox/attachment.txt"),
    "a patch to a project": ("apply_patch", "{work}/app.py"),
}


@pytest.mark.parametrize("case", sorted(ORDINARY_FILE_WRITES))
def test_a_file_tool_writing_anywhere_else_needs_no_code(world, case):
    tool, path = ORDINARY_FILE_WRITES[case]
    assert _file(world, tool, _file_call(tool, path.format(**_spots(world)))) is None


# --- every shell route --------------------------------------------------------------------------------------------

ROUTES = {
    "a redirect": "echo '#!/bin/sh' > {target}",
    "an append": "echo 'exit 0' >> {target}",
    "cp": "cp {work}/hook.sh {target}",
    "mv": "mv {work}/hook.sh {target}",
    "tee": "echo '#!/bin/sh' | tee {target}",
    "install": "install -m 755 {work}/hook.sh {target}",
    "a python program that writes": "python3 -c \"import sys; open(sys.argv[1], 'w').write('#')\" {target}",
}
SHELL_SPELLINGS = {
    "plainly": "{v5}/{name}",
    "through a link made beforehand": "{work}/v5/{name}",
    "through ..": "{v5}/outbox/../{name}",  # through a folder anyone writes: a path through the board names the board
    "in another case": "{home}/.synthesis/V5/{upper}",
    "with ~": "~/.synthesis/v5/{name}",
    "with $HOME": "$HOME/.synthesis/v5/{name}",
}
NAMES = {"config.json": ("config.json", "CONFIG.JSON", SETTINGS), "a git hook": ("git-hooks/pre-commit", "GIT-HOOKS/Pre-Commit", HOOKS)}


@pytest.mark.parametrize("route", sorted(ROUTES))
@pytest.mark.parametrize("spelling", sorted(SHELL_SPELLINGS))
@pytest.mark.parametrize("setting", sorted(NAMES))
def test_each_shell_route_waits_for_the_code_to_write_the_settings(world, route, spelling, setting):
    name, upper, what = NAMES[setting]
    target = SHELL_SPELLINGS[spelling].format(**_spots(world), name=name, upper=upper)
    line = ROUTES[route].format(**_spots(world), target=target if spelling.startswith("with") else shlex.quote(target))
    assert _held(_verdict(world, line), what), line


MORE_ROUTES = {
    "moving the config away": ("mv {config} {work}/old-config.json", SETTINGS),
    "a hook copied into the folder": ("cp {work}/hook.sh {hooks}/", HOOKS),
    "a link put in place of a hook": ("ln -sf {work}/hook.sh {hook}", HOOKS),
    "sed in place": ("sed -i.bak 's/example/other/' {config}", SETTINGS),
    "removing the config": ("rm -f {config}", SETTINGS),
    "removing the hooks folder": ("rm -rf {hooks}", HOOKS),
    "a pattern that names the config": ("rm -f {v5}/*.json", SETTINGS),
    "chmod of a hook": ("chmod 644 {hook}", HOOKS),
    "a python heredoc built from Path.home()": ("python3 - <<'EOF'\nfrom pathlib import Path\n"
                                                "(Path.home() / '.synthesis' / 'v5' / 'config.json').write_text('{{}}')\nEOF", SETTINGS),
    "a python script file": ("python3 {work}/write_settings.py", SETTINGS),
    "python through synthesis's own path": ("python3 -c \"from synthesis import paths; paths.config_file().write_text('{{}}')\"", SETTINGS),
    "python through a link made beforehand": ("python3 -c \"open('{work}/v5/config.json', 'w').write('{{}}')\"", SETTINGS),
    "a program that starts a copy": ("python3 -c \"import subprocess, sys; subprocess.run(['cp', sys.argv[1], sys.argv[2]])\" "
                                     "{work}/hook.sh {hook}", HOOKS),
    "node": ("node -e \"require('fs').writeFileSync('{config_raw}', '{{}}')\"", SETTINGS),
    "perl": ("perl -e 'open(my $f, \">\", $ARGV[0]); print $f \"x\"' {config}", SETTINGS),
    "apply_patch as a command": ("apply_patch <<'PATCH'\n*** Begin Patch\n*** Update File: {config_raw}\n@@\n-a\n+b\n"
                                 "*** End Patch\nPATCH", SETTINGS),
    "a bash script": ("bash -c 'cp \"$1\" \"$2\"' copier {work}/v5-config.json {config}", SETTINGS),
    "after a cd": ("cd {v5} && echo '{{}}' > config.json", SETTINGS),
    "after a pushd": ("pushd {v5} && echo '{{}}' > config.json", SETTINGS),
    "in a subshell": ("(cd {v5} && echo '{{}}' > config.json)", SETTINGS),
    "env -C": ("env -C {v5} sh -c 'echo x > config.json'", SETTINGS),
    "through a variable": ("D={v5}; echo '{{}}' > \"$D/config.json\"", SETTINGS),
    "a here-string to tee": ("tee {config} <<< '{{}}'", SETTINGS),
    "curl -o": ("curl -sS -o {config} https://example.com/settings.json", SETTINGS),
    "dd of=": ("dd if={work}/v5-config.json of={config}", SETTINGS),
    "truncate": ("truncate -s 0 {config}", SETTINGS),
    "touch": ("touch {hook}", HOOKS),
    "perl in place": ("perl -pi -e 's/example/other/' {config}", SETTINGS),
    "cp -t": ("cp -t {hooks} {work}/hook.sh", HOOKS),
    "rsync": ("rsync -a {work}/ {hooks}/", HOOKS),
    "tar -C": ("tar -xf {work}/hooks.tar -C {hooks}", HOOKS),
    "find -exec": ("find {hooks} -type f -exec chmod 644 {{}} \\;", HOOKS),
    "osascript": ("osascript -e 'do shell script \"cp {work}/hook.sh {v5}/git-hooks/pre-commit\"'", HOOKS),
}


@pytest.mark.parametrize("case", sorted(MORE_ROUTES))
def test_every_other_shell_route_to_the_settings_waits_too(world, case):
    line, what = MORE_ROUTES[case]
    line = line.format(**_spots(world))
    assert _held(_verdict(world, line), what), line


def test_a_shell_tool_that_names_its_own_folder_is_judged_there(world):
    """Codex's and Muse's shells take the folder a command runs in (`workdir`), which may not be the session's: a bare
    name written there is judged where it lands."""
    for tool in ("bash", "exec_command"):  # Muse's, Codex's
        call = {"command": "echo '{}' > config.json", "workdir": str(world["v5"])}
        assert _held(guards.check(tool, call, CONFIG, cwd=str(world["work"]), session=world["session"]))
        call = {"command": "echo '{}' > config.json", "workdir": os.path.relpath(world["v5"], world["work"])}  # from the session's folder
        assert _held(guards.check(tool, call, CONFIG, cwd=str(world["work"]), session=world["session"]))
    assert guards.check("bash", {"command": "echo '{}' > config.json", "workdir": str(world["work"])}, CONFIG,
                        cwd=str(world["v5"]), session=world["session"]) is None  # a project's own, from wherever the session began


def test_a_command_that_also_writes_the_state_folder_is_still_refused_outright(world):
    """The settings wait for a code; the folder approvals rest on never takes one."""
    line = f"echo '{{}}' > {shlex.quote(str(world['v5'] / 'config.json'))}; echo x > {shlex.quote(str(paths.state() / 'approvals' / 'x.json'))}"
    assert _verdict(world, line).startswith("Refused")


def test_the_private_installers_copy_waits_and_its_code_binds_the_file_it_copies(world):
    """The ruling: the private installer that copies his private repository's settings into place waits too. The code
    binds the command, the folder it runs in and each file it names as it stood, so a file changed after he approved
    is a new command."""
    line = "cp v5-config.json ~/.synthesis/v5/config.json"
    held = _verdict(world, line)
    assert _held(held)
    world["approve"](held)
    assert _verdict(world, line) is None  # that copy, as he was shown it
    again = _verdict(world, line)
    assert _held(again)  # once
    world["approve"](again)
    (world["work"] / "v5-config.json").write_text('{"sheet_hosts": ["somewhere-else"]}\n', encoding="utf-8")
    assert _held(_verdict(world, line))  # the file it copies changed after he approved
    elsewhere = world["work"] / "other"
    elsewhere.mkdir()
    (elsewhere / "v5-config.json").write_text('{"sheet_hosts": ["example-sheets"]}\n', encoding="utf-8")
    assert _held(_verdict(world, line, cwd=elsewhere))  # and where it runs


READS = {
    "cat": "cat {config}",
    "head": "head -5 {config}",
    "grep": "grep sheet {config}",
    "jq": "jq .sheet_hosts {config}",
    "diff": "diff {work}/v5-config.json {config}",
    "ls": "ls -la {hooks}",
    "a hook read": "cat {hook}",
    "shasum over a pattern": "shasum {v5}/git-hooks/*",
    "python that reads": "python3 -I -c \"import json, sys; print(json.load(open(sys.argv[1])))\" {config}",
    "git diff": "git diff --no-index {work}/v5-config.json {config}",
    "a copy out by cat": "cat {config} > {work}/config-copy.json",
    "a copy beside it by cat": "cat {config} > {config}.bak-2026-11-15",
    "a commit message that names it": "git commit --allow-empty -m 'Note the change to ~/.synthesis/v5/config.json'",
}


@pytest.mark.parametrize("case", sorted(READS))
def test_reading_the_settings_needs_no_code(world, case):
    line = READS[case].format(**_spots(world))
    assert _verdict(world, line) is None, line


def test_cp_of_the_settings_waits_as_it_does_for_every_protected_file_and_cat_is_the_copy_that_needs_none(world):
    """cp is no known reader (it links as well as copies: `cp -l`, `cp -s`), so naming a protected file to it waits, as it
    has for the state folder since 5.22.1; the hold says that cat, head, grep and jq read with no code."""
    held = _verdict(world, "cp {config} {config}.bak-2026-11-15".format(**_spots(world)))
    assert _held(held) and "Reading these files needs no code (cat" in held
    assert _held(_verdict(world, "ln {config} {work}/alias.json".format(**_spots(world))))  # a hard link to it: a way to write it later


ORDINARY_SHELL = {
    "a project's config.json": "echo '{{}}' > {work}/config.json",
    "a copy in a project": "cp {work}/v5-config.json {work}/copy.json",
    "a project's own git-hooks folder": "mkdir -p {work}/git-hooks && cp {work}/hook.sh {work}/git-hooks/pre-commit",
    "python writing a project file": "python3 -c \"open('{work}/out.json', 'w').write('{{}}')\"",
    "the outbox": "cp {work}/hook.sh {v5}/outbox/hook.txt",
    "the installer's own route": "synthesis update",
}


@pytest.mark.parametrize("case", sorted(ORDINARY_SHELL))
def test_a_shell_command_writing_anywhere_else_needs_no_code(world, case):
    line = ORDINARY_SHELL[case].format(**_spots(world))
    assert _verdict(world, line) is None, line


# --- through the hook ---------------------------------------------------------------------------------------------

def _hook(world, tool: str, tool_input: dict, capsys) -> str:
    from synthesis import hook
    hook.pre_tool_use({"tool_name": tool, "tool_input": tool_input, "cwd": str(world["work"]), **world["session"]})
    out = capsys.readouterr().out.strip()
    return json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"] if out else ""


def test_the_hook_holds_a_settings_write_until_the_principal_types_its_code(world, capsys):
    call = {"file_path": str(world["v5"] / "config.json"), "content": '{"sheet_hosts": []}\n'}
    held = _hook(world, "Write", call, capsys)
    assert _held(held)
    world["approve"](held)
    assert _hook(world, "Write", call, capsys) == ""  # let through, once
    assert _held(_hook(world, "Write", call, capsys))


def test_an_unreadable_config_still_holds_a_file_tool_that_writes_it_or_the_state_folder(world, capsys):
    """A config that cannot be read held every shell call and let every file tool through unjudged, so a file tool could
    rewrite the config, or forge a grant in the state folder, with no code. A file tool is now judged without the
    config: an ordinary write still goes, the config's repair waits for his code, the state folder stays refused."""
    (world["v5"] / "config.json").write_text("{ not json", encoding="utf-8")
    repair = {"file_path": str(world["v5"] / "config.json"), "content": '{"sheet_hosts": ["example-sheets"]}\n'}
    held = _hook(world, "Write", repair, capsys)
    assert _held(held)
    world["approve"](held)
    assert _hook(world, "Write", repair, capsys) == ""  # the repair he approved
    forged = {"file_path": str(paths.state() / "approvals" / ("a" * 64 + ".json")), "content": "{}"}
    assert "Refused" in _hook(world, "Write", forged, capsys)
    assert _hook(world, "Write", {"file_path": str(world["work"] / "notes.md"), "content": "x"}, capsys) == ""

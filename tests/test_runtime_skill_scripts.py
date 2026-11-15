"""A skill's script is the plugin's own only inside the release the guard runs from, and every skill runs the
runtime's copy, `<synthesis home>/current/skills/...`, whose every import resolves inside that protected release.

2026-11-15: two seats' day-ends ran skill scripts from a harness's plugin cache and the installed guard held them for
the principal's code. The first fix carried those skills' scripts in the runtime and let the guard vouch for a plugin
copy with the same bytes as the runtime's. Its review (5.23.1 round 1) found that a copy's bytes say nothing about the
code it loads from other folders: `messages_send.py` imports the guard from the plugin root two levels up, the meeting
fetcher puts the plugin root and the skill root ahead of its own folder, and all of it is writable, so a byte-identical
copy beside a `synthesis/` the agent wrote sent with no code (finding 1). The guard now trusts only what lies inside
its own release; a copy anywhere else is judged like any other script, and when one of the runtime's scripts waits from
a plugin copy, the hold names the runtime's copy, which needs no code. These tests build the runtime with the
installer, under homes of their own, and run the guard from it in a fresh interpreter, as the hook does."""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from synthesis import install

ROOT = Path(__file__).resolve().parents[1]
FETCHER = "skills/synthesis-meeting-transcripts/optional-workspace-mcp/fetch-meeting.py"
SEND = "skills/synthesis-local-messaging/scripts/messages_send.py"
READ = "skills/synthesis-local-messaging/scripts/local_messaging.py"
DOCTOR = "skills/synthesis-context-lifecycle/scripts/context_doctor.py"
KIT = ("synthesis-onboarding", "synthesis-skills-manager")  # the installer and release kit: they write the trust base
PROGRAM = ("import json, sys; sys.path.insert(0, sys.argv[1]); from synthesis import guards; "
           "print(json.dumps(guards.check('Bash', {'command': sys.argv[2]}, {}, cwd=sys.argv[3], "
           "session={'session_id': 'S-test', 'cwd': sys.argv[3]})))")
MARK = "import os\nopen(os.environ.get('MARK', os.devnull), 'w').write('planted code ran')\n"
DROPPED = ("SYNTHESIS_SESSION", "CLAUDE_CODE_SESSION_ID", "CLAUDECODE", "CODEX_THREAD_ID", "MUSE_SESSION_ID", "PYTHONPATH",
           "PYTHONHOME", "PYTHONSTARTUP", "PYTHONUSERBASE", "CLAUDE_PLUGIN_ROOT", "MUSE_PLUGIN_ROOT", "WORKSPACE_MCP_URL")


def _copy_plugin(dest: Path, skills) -> Path:
    """A plugin folder as a harness caches it: the plugin's own synthesis/ and hooks, and the named skills as shipped."""
    if not (dest / "synthesis").exists():
        shutil.copytree(ROOT / "synthesis", dest / "synthesis", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(ROOT / "hooks", dest / "hooks")
    for skill in skills:
        if not (dest / "skills" / skill).exists():
            shutil.copytree(ROOT / "skills" / skill, dest / "skills" / skill, ignore=shutil.ignore_patterns("__pycache__", "tests"))
    return dest


@pytest.fixture(scope="module")
def mac(tmp_path_factory):
    """A Mac of the test's own: every home under a temporary folder, Claude Code's records at the default place under
    it (so `.claude` beside `projects` spells a protected folder), the plugin in Claude Code's cache, and the runtime
    its installer builds from it. Stand-ins for osascript and say come first on PATH."""
    base = tmp_path_factory.mktemp("mac")
    home, stand_ins = base / "home", base / "bin"
    (home / ".claude" / "projects").mkdir(parents=True)
    stand_ins.mkdir()
    for name in ("osascript", "say", "open", "afplay"):
        (stand_ins / name).write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        (stand_ins / name).chmod(0o755)
    env = {k: v for k, v in os.environ.items() if k not in DROPPED}
    env.update(HOME=str(home), SYNTHESIS_HOME=str(home / ".synthesis" / "v5"), CLAUDE_CONFIG_DIR=str(home / ".claude"),
               CODEX_HOME=str(base / "codex"), XDG_DATA_HOME=str(base / "xdg"), RITUAL_STATE_DIR=str(base / "rituals"),
               SYNTHESIS_CLAUDE_DESKTOP_DIR=str(base / "desktop"), PATH=f"{stand_ins}:{os.environ.get('PATH', '/usr/bin:/bin')}",
               PYTHONDONTWRITEBYTECODE="1")
    plugin = _copy_plugin(home / ".claude" / "plugins" / "cache" / "synthesis-engineering" / "synthesis-skills" / "5.23.1",
                          list(install.STABLE_SKILL_SCRIPTS) + list(KIT))
    done = subprocess.run([sys.executable, "-S", str(plugin / "synthesis" / "install.py"), str(plugin)], capture_output=True,
                          text=True, env=env, timeout=120)
    assert done.returncode == 0, done.stderr[-800:]
    sh = home / ".synthesis" / "v5"
    return SimpleNamespace(base=base, home=home, sh=sh, rt=sh / "current", plugin=plugin, env=env)


def _verdict(mac, command: str, cwd: Path):
    """What the guard, run from the installed runtime, says to a shell command: None lets it run."""
    done = subprocess.run([sys.executable, "-I", "-c", PROGRAM, str(mac.rt), command, str(cwd)], capture_output=True, text=True,
                          timeout=120, env=mac.env)
    assert done.returncode == 0, done.stderr[-800:]
    return json.loads(done.stdout)


def _work(tmp_path: Path) -> Path:
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    (work / "t.txt").write_text("a line of text\n", encoding="utf-8")
    (work / "r.json").write_text("{}\n", encoding="utf-8")
    return work


# --- what the runtime carries -------------------------------------------------------------------------------------

def test_the_runtime_carries_the_meeting_message_and_records_skills_scripts():
    carried = {rel for rel, _ in install._stable_skill_files(ROOT)}
    for rel in (FETCHER, "skills/synthesis-meeting-transcripts/optional-workspace-mcp/mcp_client.py",
                "skills/synthesis-meeting-transcripts/verify_transcripts.py", "skills/synthesis-meeting-transcripts/extract_commitments.py",
                "skills/synthesis-message-exports/scripts/import_messages.py", "skills/synthesis-message-exports/scripts/chat_page.py",
                SEND, READ, DOCTOR):
        assert rel in carried, rel


def test_every_file_a_carried_script_loads_from_another_skill_is_carried_too(mac):
    """pr_queue_scan.py loads the Bitbucket skill's pr_queue.py from the folder beside its own skill: from the runtime,
    that folder is the runtime's, so the runtime carries it, and the scan's every import resolves inside the release."""
    scan = (mac.rt / "skills" / "synthesis-daily-rituals" / "scripts" / "pr_queue_scan.py").read_text(encoding="utf-8")
    assert '"synthesis-bitbucket" / "scripts" / "pr_queue.py"' in scan
    assert (mac.rt / "skills" / "synthesis-bitbucket" / "scripts" / "pr_queue.py").is_file()


def test_a_carried_skills_code_outside_scripts_is_python_or_shell_only_and_never_its_tests():
    for rel, path in install._stable_skill_files(ROOT):
        parts = Path(rel).parts
        assert "tests" not in parts and "__pycache__" not in parts and not path.name.startswith("test_"), rel
        if parts[2] != "scripts":
            assert path.suffix in (".py", ".sh"), rel


def test_the_installer_and_release_kit_is_never_carried(mac):
    """setup.py, workspace.py and release.py write the trust base itself (the harnesses' settings, the runtime, the
    release), so no copy of them is ever the plugin's own: not in the list, not among the files, not in the runtime."""
    kit = {p.name for skill in KIT for p in (ROOT / "skills" / skill / "scripts").glob("*.py")}
    assert {"setup.py", "workspace.py", "release.py"} <= kit
    assert not set(KIT) & set(install.STABLE_SKILL_SCRIPTS)
    for rel, _ in install._stable_skill_files(ROOT):
        assert Path(rel).parts[1] not in KIT and Path(rel).name not in kit, rel
    assert not [p for p in (mac.rt / "skills").rglob("*") if p.name in kit or set(KIT) & set(p.parts)]


# --- the guard trusts only its own release ------------------------------------------------------------------------

def test_a_script_is_the_plugins_own_only_inside_the_release_the_guard_runs_from(mac):
    program = ("import json, sys; sys.path.insert(0, sys.argv[1]); from synthesis import guards; "
               "print(json.dumps([guards._shipped(p) for p in sys.argv[2:]]))")
    copy, mine = mac.plugin / FETCHER, mac.rt / FETCHER
    assert copy.read_bytes() == mine.read_bytes()  # the same bytes, and still not the plugin's own
    done = subprocess.run([sys.executable, "-I", "-c", program, str(mac.rt), os.path.realpath(mine), str(copy)],
                          capture_output=True, text=True, env=mac.env, timeout=60)
    assert json.loads(done.stdout) == [True, False], done.stderr[-600:]


DAY_END = {  # the four a seat's day-end found held from the plugin cache (2026-11-15)
    "the meeting fetcher": f"{FETCHER} --window 2026-11-14 2026-11-15",
    "the records gate": f"{DOCTOR} --project {{work}}",
    "the messages read": f"{READ} --request {{work}}/r.json --state {{work}}/state",
    "the send script": f"{SEND} --to +15550100 --text-file {{work}}/t.txt",
}


@pytest.mark.parametrize("name", list(DAY_END))
def test_the_runtimes_copy_of_a_day_end_script_needs_no_code(mac, tmp_path, name):
    work = _work(tmp_path)
    assert _verdict(mac, f"python3 {mac.rt}/{DAY_END[name].format(work=work)}", work) is None, name


@pytest.mark.parametrize("name", list(DAY_END))
def test_a_plugin_copy_of_a_day_end_script_waits_and_names_the_runtimes_copy(mac, tmp_path, name):
    """The plugin cache carries the plugin's own synthesis/ beside the copy, as a harness keeps it (finding 7: the
    first fix's test left it out, so the folder the send script imports from was not there)."""
    work = _work(tmp_path)
    script, _, rest = DAY_END[name].format(work=work).partition(" ")
    reason = _verdict(mac, f"python3 {mac.plugin / script} {rest}", work)
    assert reason and str(mac.rt / script) in reason and "runs with no code" in reason, (name, reason)


# --- finding 1: what a copy loads from other folders --------------------------------------------------------------

@pytest.mark.parametrize("change", ["a changed skill-root module", "a module planted in the skill root",
                                    "a module planted in the plugin root", "a package beside its sibling", "unchanged"])
def test_a_plugin_copy_of_the_fetcher_waits_whatever_lies_around_it(mac, tmp_path, change):
    root = _copy_plugin(tmp_path / "cache" / "synthesis-skills" / "5.23.1", ["synthesis-meeting-transcripts"])
    skill = root / "skills" / "synthesis-meeting-transcripts"
    if change == "a changed skill-root module":
        (skill / "verify_transcripts.py").write_text((skill / "verify_transcripts.py").read_text(encoding="utf-8") + "\n" + MARK)
    elif change == "a module planted in the skill root":
        (skill / "mcp_client.py").write_text(MARK, encoding="utf-8")
    elif change == "a module planted in the plugin root":
        (root / "mcp_client.py").write_text(MARK, encoding="utf-8")
    elif change == "a package beside its sibling":
        (skill / "optional-workspace-mcp" / "mcp_client").mkdir()
        (skill / "optional-workspace-mcp" / "mcp_client" / "__init__.py").write_text(MARK, encoding="utf-8")
    work = _work(tmp_path)
    assert _verdict(mac, f"python3 {root / FETCHER} {mac.sh / 'state' / 'probe'}", work), change


def _agent_layout(work: Path, skill: str, names, synthesis: dict) -> Path:
    """The shipped files of a skill copied byte for byte into a layout the agent made, beside a synthesis/ it wrote."""
    scripts = work / "agent" / "skills" / skill / "scripts"
    scripts.mkdir(parents=True)
    for name in names:
        shutil.copy2(ROOT / "skills" / skill / "scripts" / name, scripts / name)
    (work / "agent" / "synthesis").mkdir()
    for name, text in {"__init__.py": "", **synthesis}.items():
        (work / "agent" / "synthesis" / name).write_text(text, encoding="utf-8")
    return scripts


def test_a_copy_of_the_send_script_beside_a_synthesis_the_agent_wrote_waits(mac, tmp_path):
    work = _work(tmp_path)
    scripts = _agent_layout(work, "synthesis-local-messaging", ["messages_send.py", "messages_route.js", "messages_transport.js"],
                            {"guards.py": "def check_send(*args, **kwargs):\n    return None\n", "paths.py": "def state():\n    return None\n"})
    reason = _verdict(mac, f"python3 {scripts / 'messages_send.py'} --to +15550100 --text-file {work / 't.txt'}", work)
    assert reason and str(mac.rt / SEND) in reason, reason


def test_a_plugin_copy_of_the_send_script_beside_an_edited_guard_waits(mac, tmp_path):
    root = _copy_plugin(tmp_path / "cache" / "synthesis-skills" / "5.23.1", ["synthesis-local-messaging"])
    guards = root / "synthesis" / "guards.py"
    guards.write_text(guards.read_text(encoding="utf-8") + "\n\ndef check_send(*args, **kwargs):\n    return None\n", encoding="utf-8")
    work = _work(tmp_path)
    assert _verdict(mac, f"python3 {root / SEND} --to +15550100 --text-file {work / 't.txt'}", work)


def test_the_gap_review_beside_approvals_the_agent_wrote_waits(mac, tmp_path):
    work = _work(tmp_path)
    scripts = _agent_layout(work, "synthesis-local-messaging", ["local_messaging.py", "os_sandbox.py"],
                            {"approvals.py": "def consume(*a, **k):\n    return True\n\ndef request(*a, **k):\n    return ''\n"})
    line = f"python3 {scripts / 'local_messaging.py'} --request {work / 'r.json'} --state {work / 'gaps'} --review {work / 'review.json'}"
    assert _verdict(mac, line, work)


def test_a_copy_under_a_doubled_skills_segment_beside_a_planted_synthesis_waits(mac, tmp_path):
    root = _copy_plugin(tmp_path / "cache" / "synthesis-skills" / "5.23.1", ["synthesis-local-messaging"])
    outer = root / "skills" / "synthesis-local-messaging"
    inner = outer / "skills" / "synthesis-context-lifecycle" / "scripts"
    inner.mkdir(parents=True)
    shutil.copy2(ROOT / DOCTOR, inner / "context_doctor.py")
    (outer / "synthesis").mkdir()
    (outer / "synthesis" / "__init__.py").write_text("", encoding="utf-8")
    (outer / "synthesis" / "yamlish.py").write_text(MARK + "def load(*a, **k):\n    return {}\n", encoding="utf-8")
    work = _work(tmp_path)
    assert _verdict(mac, f"python3 {inner / 'context_doctor.py'} --project {mac.sh / 'state'}", work)


def test_a_script_carried_before_this_change_waits_beside_a_synthesis_the_agent_wrote(mac, tmp_path):
    """Finding 1's root cause is older: autopilot_cli.py imports synthesis from three folders up as well."""
    work = _work(tmp_path)
    scripts = _agent_layout(work, "synthesis-autopilot", ["autopilot_cli.py"], {"__init__.py": MARK})
    assert _verdict(mac, f"python3 {scripts / 'autopilot_cli.py'} status {mac.sh / 'board'}", work)


SEND_HARNESS = '''"""Load a copy of messages_send.py and call send() with every way out to Messages replaced: osascript raises, the
route is made up, and the transport (the one send call) only records that it was reached."""
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("messages_send_test", sys.argv[1])
ms = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ms)
calls = []
def no_osascript(*args, **kwargs):
    raise AssertionError("osascript reached")
ms.osascript = no_osascript
ms.resolve_route = lambda to, account: {"account_id": "a", "service": "iMessage", "chat_id": "c", "participant_id": "p"}
ms.transport = lambda *args, **kwargs: calls.append(1) or {"status": "dispatched", "delivery": "unknown"}
result = ms.send(sys.argv[2], sys.argv[3])
print(json.dumps({"status": result.get("status"), "send_calls": len(calls), "decided_by": sys.modules["synthesis.guards"].__file__}))
'''


def test_a_send_through_the_runtimes_copy_files_a_request_and_sends_nothing(mac, tmp_path):
    """The control: the runtime's copy decides with the runtime's own guard, inside the protected release."""
    harness = tmp_path / "send_harness.py"
    harness.write_text(SEND_HARNESS, encoding="utf-8")
    done = subprocess.run([sys.executable, "-I", str(harness), str(mac.rt / SEND), "+15550100", "a line of text"], capture_output=True,
                          text=True, env=mac.env, cwd=str(_work(tmp_path)), timeout=60)
    assert done.returncode == 0, done.stderr[-600:]
    report = json.loads(done.stdout)
    assert report["status"] == "needs-approval" and report["send_calls"] == 0, report
    assert os.path.realpath(report["decided_by"]).startswith(os.path.realpath(mac.rt) + os.sep), report


# --- finding 3: a line that rewrites what runs, and the release that cannot be written ---------------------------

@pytest.mark.parametrize("vehicle", ["fetcher", "sharing scan"])
def test_a_plugin_copy_whose_sibling_the_same_line_rewrites_waits(mac, tmp_path, vehicle):
    skill, script, sibling = {"fetcher": ("synthesis-meeting-transcripts", "optional-workspace-mcp/fetch-meeting.py", "mcp_client.py"),
                              "sharing scan": ("synthesis-kb-edit", "scripts/sharing_scan.py", "kb_config.py")}[vehicle]
    root = _copy_plugin(tmp_path / "cache" / "synthesis-skills" / "5.23.1", [skill])
    work = _work(tmp_path)
    (work / "evil.py").write_text(MARK, encoding="utf-8")
    folder = (root / "skills" / skill / script).parent
    line = f"cp {work / 'evil.py'} {folder / sibling} && python3 {root / 'skills' / skill / script} {mac.sh / 'state' / 'probe'}"
    assert _verdict(mac, line, work), vehicle


PLANTS = {
    "a sibling rewritten": "cp {evil} {folder}/mcp_client.py",
    "a standard module planted beside it": "cp {evil} {folder}/gettext.py",
    "bytecode for its sibling": "mkdir -p {folder}/__pycache__ && cp {evil} {folder}/__pycache__/mcp_client.cpython-312.pyc",
    "a package beside its sibling": "mkdir {folder}/mcp_client",
}


@pytest.mark.parametrize("plant", list(PLANTS))
def test_a_line_that_writes_into_the_runtime_before_running_its_script_is_refused(mac, tmp_path, plant):
    work = _work(tmp_path)
    (work / "evil.py").write_text(MARK, encoding="utf-8")
    folder = (mac.rt / FETCHER).parent
    line = PLANTS[plant].format(evil=work / "evil.py", folder=folder) + f" && python3 {mac.rt / FETCHER} --window 2026-11-14 2026-11-15"
    reason = _verdict(mac, line, work)
    assert reason and reason.startswith("Refused"), (plant, reason)
    assert not (folder / "gettext.py").exists() and not (folder / "mcp_client").exists()


# --- finding 7: the controls the first fix's test missed ----------------------------------------------------------

@pytest.mark.parametrize("changed", ["optional-workspace-mcp/fetch-meeting.py", "optional-workspace-mcp/mcp_client.py"])
def test_a_plugin_copy_changed_after_it_shipped_waits(mac, tmp_path, changed):
    root = _copy_plugin(tmp_path / "cache" / "synthesis-skills" / "5.23.1", ["synthesis-meeting-transcripts"])
    target = root / "skills" / "synthesis-meeting-transcripts" / changed
    target.write_text(target.read_text(encoding="utf-8") + "\n# changed after it shipped\n", encoding="utf-8")
    work = _work(tmp_path)
    assert _verdict(mac, f"python3 {root / FETCHER} --window 2026-11-14 2026-11-15", work), changed


@pytest.mark.parametrize("kit", ["synthesis-onboarding/scripts/setup.py", "synthesis-onboarding/scripts/workspace.py",
                                 "synthesis-skills-manager/scripts/release.py"])
def test_a_kit_script_copied_into_a_carried_skills_folder_waits(mac, tmp_path, kit):
    root = _copy_plugin(tmp_path / "cache" / "synthesis-skills" / "5.23.1", ["synthesis-context-lifecycle"])
    dest = root / "skills" / "synthesis-context-lifecycle" / "scripts" / os.path.basename(kit)
    shutil.copy2(ROOT / "skills" / kit, dest)
    work = _work(tmp_path)
    assert _verdict(mac, f"python3 {dest} {mac.sh / 'state'}", work), kit


def test_the_runtimes_own_script_through_a_link_passes_and_a_copys_sibling_linked_to_an_agent_file_waits(mac, tmp_path):
    work = _work(tmp_path)
    (work / "fetch.py").symlink_to(mac.rt / FETCHER)
    assert _verdict(mac, f"python3 {work / 'fetch.py'} --window 2026-11-14 2026-11-15", work) is None
    root = _copy_plugin(tmp_path / "cache" / "synthesis-skills" / "5.23.1", ["synthesis-meeting-transcripts"])
    folder = root / "skills" / "synthesis-meeting-transcripts" / "optional-workspace-mcp"
    (work / "evil.py").write_text("print('the agent code')\n", encoding="utf-8")
    (folder / "mcp_client.py").unlink()
    (folder / "mcp_client.py").symlink_to(work / "evil.py")
    assert _verdict(mac, f"python3 {folder / 'fetch-meeting.py'} {mac.sh / 'state'}", work)


# --- finding 2: a protected folder the line names ---------------------------------------------------------------

IMPORT = "skills/synthesis-message-exports/scripts/import_messages.py"
PAGE = "skills/synthesis-message-exports/scripts/chat_page.py"
PLATE = "skills/synthesis-daily-rituals/scripts/plate.py"
NAMED = {  # what the review saw written into a protected folder by an unmodified copy, and the same through the folder
    "an argument into the session archive": "python3 {rt}/" + IMPORT + " {work}/export --out {sh}/sessions/probe-import",
    "an argument into the board": "python3 {rt}/" + READ + " --request {work}/r.json --state {sh}/board/probe-state",
    "a page written into the archive": "python3 {rt}/" + PAGE + " {work}/t.txt --out {sh}/sessions/probe-page --since 2026-11-14",
    "a plate written onto the board": "python3 {rt}/" + PLATE + " --workspace {work} --as-of 2026-11-15 --out {sh}/board/probe-plate.md",
    "the folder it runs in": "cd {sh}/state && python3 {rt}/" + IMPORT + " {work}/export --out probe-import",
    "a value the line gives it": "OUT={sh}/board/probe; export OUT; python3 {rt}/" + IMPORT + " {work}/export --out \"$OUT\"",
    "a redirect": "python3 {rt}/" + PLATE + " --workspace {work} --as-of 2026-11-15 > {sh}/board/probe-plate.md",
}


@pytest.mark.parametrize("name", list(NAMED))
def test_the_runtimes_copy_is_still_judged_for_a_protected_folder_its_line_names(mac, tmp_path, name):
    work = _work(tmp_path)
    line = NAMED[name].format(rt=mac.rt, sh=mac.sh, work=work)
    reason = _verdict(mac, line, work)
    assert reason and ("Refused" in reason or "approve" in reason), (name, reason)


OWN_TEXT = {  # what each script's own text names stays exempt: the fetcher reads a project's own `.claude` folder
    "the fetcher": f"{FETCHER} --window 2026-11-14 2026-11-15",
    "the records gate": f"{DOCTOR} --project {{work}}",
    "a plate into the workspace": PLATE + " --workspace {work} --as-of 2026-11-15 --out {work}/plate.md",
    "an import into the workspace": IMPORT + " {work}/export --out {work}/out --dry-run",
}


@pytest.mark.parametrize("name", list(OWN_TEXT))
def test_what_the_runtimes_copy_names_in_its_own_text_needs_no_code(mac, tmp_path, name):
    work = _work(tmp_path)
    assert _verdict(mac, f"python3 {mac.rt}/{OWN_TEXT[name].format(work=work)}", work) is None, name


def test_a_plugin_copy_whose_line_names_a_protected_folder_is_not_told_the_runtimes_copy_needs_no_code(mac, tmp_path):
    """The runtime's copy would wait for the same line, so the hold says nothing of running it."""
    work = _work(tmp_path)
    reason = _verdict(mac, f"python3 {mac.plugin / IMPORT} {work}/export --out {mac.sh}/sessions/probe-import", work)
    assert reason and "runs with no code" not in reason, reason


# --- finding 4: what the interpreter loads, and what runs it --------------------------------------------------------

RUN = "python3 {rt}/" + FETCHER + " --window 2026-11-14 2026-11-15"  # its own text names a project's `.claude` folder
SEND_RUN = "python3 {rt}/" + SEND + " --to +15550100 --text-file {work}/t.txt"
NOT_PLAIN = {  # each makes the runtime's copy load or run something other than what the release holds, or run as another
    "PYTHONPATH": "PYTHONPATH={work}/pp " + RUN, "PYTHONHOME": "PYTHONHOME={work}/ph " + RUN,
    "PYTHONSTARTUP": "PYTHONSTARTUP={work}/s.py " + RUN, "PYTHONUSERBASE": "PYTHONUSERBASE={work}/ub " + RUN,
    "PYTHONPYCACHEPREFIX": "PYTHONPYCACHEPREFIX={work}/pyc " + RUN, "PYTHONINSPECT": "PYTHONINSPECT=1 " + RUN,
    "PYTHONWARNINGS": "PYTHONWARNINGS=ignore::evil.Warning " + RUN, "an export": "export PYTHONPATH={work}/pp; " + RUN,
    "env with a value": "env PYTHONPATH={work}/pp " + RUN, "the loader": "DYLD_INSERT_LIBRARIES={work}/x.dylib " + RUN,
    "the program search path": "PATH={work}/bin:$PATH " + RUN, "allexport": "set -a; PYTHONPATH={work}/pp; " + RUN,
    "another synthesis home": "SYNTHESIS_HOME={work}/fake " + SEND_RUN,
    "another synthesis home, exported": "export SYNTHESIS_HOME={work}/fake; " + SEND_RUN,
    "an interpreter by its path": "{work}/bin/" + RUN, "nice": "nice " + RUN, "env": "env " + RUN,
    "timeout": "timeout 60 " + RUN, "xargs": "echo 2026-11-15 | xargs " + RUN, "-i": RUN.replace("python3 ", "python3 -i ", 1),
    "-X pycache_prefix": RUN.replace("python3 ", "python3 -X pycache_prefix={work}/pyc ", 1),
    "-W with a module": RUN.replace("python3 ", "python3 -W ignore::evil.Warning ", 1),
    "a function": "python3() {{ {work}/evil \"$@\"; }}; " + RUN, "an alias": "alias python3={work}/evil; " + RUN,
    "a file read into the shell": ". {work}/env.sh && " + RUN, "hash": "hash -p {work}/evil python3; " + RUN,
}


@pytest.mark.parametrize("name", list(NOT_PLAIN))
def test_the_runtimes_copy_run_with_its_own_environment_or_through_another_program_is_not_proven_by_being_shipped(mac, tmp_path, name):
    work = _work(tmp_path)
    assert _verdict(mac, NOT_PLAIN[name].format(rt=mac.rt, work=work), work), name


PLAIN = {  # the interpreter's plain word, with options that only take away what it loads, through a shell or not
    "plain": RUN, "-S": RUN.replace("python3 ", "python3 -S ", 1), "-I": RUN.replace("python3 ", "python3 -I ", 1),
    "-B -E -s -u": RUN.replace("python3 ", "python3 -B -E -s -u ", 1), "a shell's script": "bash -c '" + RUN + "'",
    "after cd": "cd {work} && " + RUN, "after set -eu": "set -euo pipefail; " + RUN, "the send script": SEND_RUN,
    "a variable of the line's own": "AP={rt}/skills/synthesis-autopilot/scripts/autopilot_cli.py; python3 -S \"$AP\" status",
}


@pytest.mark.parametrize("name", list(PLAIN))
def test_the_runtimes_copy_run_by_the_plain_interpreter_needs_no_code(mac, tmp_path, name):
    work = _work(tmp_path)
    assert _verdict(mac, PLAIN[name].format(rt=mac.rt, work=work), work) is None, name


def test_a_plugin_copy_run_with_its_own_environment_is_not_told_the_runtimes_copy_needs_no_code(mac, tmp_path):
    work = _work(tmp_path)
    reason = _verdict(mac, f"PYTHONPATH={work}/pp python3 {mac.plugin / FETCHER} --window 2026-11-14 2026-11-15", work)
    assert reason and "runs with no code" not in reason, reason


# --- the callers: every skill runs the runtime's copy ---------------------------------------------------------------

MCP = "skills/synthesis-meeting-transcripts/optional-workspace-mcp"


def test_the_runtime_carries_a_carried_skills_shell_scripts_and_python_at_any_depth(tmp_path):
    """The meeting skill's server kit (its doctor, which a ritual may run, and the start script the doctor checks the
    service against) lives beside the fetcher; a carried skill's Python below a folder of scripts/ is carried too
    (finding 6). Never its tests, never compiled code."""
    carried = {rel for rel, _ in install._stable_skill_files(ROOT)}
    assert {f"{MCP}/{name}" for name in ("doctor.sh", "start.sh", "stop.sh", "install-autostart.sh", "uninstall-autostart.sh")} <= carried
    plugin = _copy_plugin(tmp_path / "plugin", ["synthesis-context-lifecycle"])
    deep = plugin / "skills" / "synthesis-context-lifecycle" / "scripts" / "helpers"
    deep.mkdir()
    (deep / "lines.py").write_text("print('a helper')\n", encoding="utf-8")
    (deep / "test_lines.py").write_text("def test_it():\n    pass\n", encoding="utf-8")
    found = {rel for rel, _ in install._stable_skill_files(plugin)}
    assert "skills/synthesis-context-lifecycle/scripts/helpers/lines.py" in found
    assert not [rel for rel in found if "test_" in rel or "__pycache__" in rel]


EVERYDAY = {  # each newly carried skill's ordinary use, as its skill text now runs it (the review's matrix)
    "fetch-meeting --window": f"python3 {{rt}}/{FETCHER} --window 2026-11-14 2026-11-15",
    "fetch-meeting standup": f"python3 {{rt}}/{FETCHER} standup --date 2026-11-14",
    "mcp_client list": f"python3 {{rt}}/{MCP}/mcp_client.py list",
    "verify_transcripts": "python3 {rt}/skills/synthesis-meeting-transcripts/verify_transcripts.py {work}/t.txt",
    "extract_commitments": "python3 {rt}/skills/synthesis-meeting-transcripts/extract_commitments.py {work}/t.txt",
    "the server's doctor": f"bash {{rt}}/{MCP}/doctor.sh --quiet",
    "import_messages --dry-run": "python3 {rt}/" + IMPORT + " {work}/export --out {work}/out --dry-run",
    "chat_page": "python3 {rt}/" + PAGE + " {work}/t.txt --out {work}/out --since 2026-11-14",
    "local_messaging --request --state": f"python3 {{rt}}/{READ} --request {{work}}/r.json --state {{work}}/state",
    "messages_send --help": f"python3 {{rt}}/{SEND} --help",
    "whatsapp_prefill --help": "python3 {rt}/skills/synthesis-local-messaging/scripts/whatsapp_prefill.py --help",
    "context_doctor --project": f"python3 {{rt}}/{DOCTOR} --project {{work}}",
    "context_doctor --json": f"python3 {{rt}}/{DOCTOR} --json",
    "pr_queue_scan": "python3 -S {rt}/skills/synthesis-daily-rituals/scripts/pr_queue_scan.py --workspace w",
}


@pytest.mark.parametrize("name", list(EVERYDAY))
def test_the_everyday_use_of_each_carried_skill_from_the_runtime_needs_no_code(mac, tmp_path, name):
    work = _work(tmp_path)
    assert _verdict(mac, EVERYDAY[name].format(rt=mac.rt, work=work), work) is None, name


ARCHIVAL = re.compile(r"preserved|version-history|release-notes|coverage-map|earlier-version")  # records of what was
INVOKE = re.compile(r"(?:\bpython3?(?:[ \t]+-[A-Za-z]+)*[ \t]+|\b(?:ba)?sh[ \t]+|(?<![\w/.$-])(?=\./))(\"?[^\s`\"'()|;&]*?)([\w.-]+\.(?:py|sh))\b")
ALIASES = {"<rituals>": "synthesis-daily-rituals", "<cos>": "synthesis-chief-of-staff", "<chief-of-staff>": "synthesis-chief-of-staff"}


def _runtime_form(prefix: str, skill: str, text: str) -> bool:
    """A path into the runtime's copy of `skill`: written out, through a placeholder or a variable the same file sets to
    it, or found by the script's own folder (a shell script beside its kit) or a checkout a CI recipe clones."""
    stable = rf"(?:\$HOME|\$\{{HOME\}}|~)/\.synthesis/v5/current/skills/{re.escape(skill)}"
    if re.match(rf'"?(?:{stable}/|\$\{{SYNTHESIS_SKILLS:-\$\{{SYNTHESIS_HOME:-\$HOME/\.synthesis/v5\}}/current\}}/skills/{re.escape(skill)}/)', prefix):
        return True
    if re.match(r'"?(?:\$SCRIPT_DIR|\$SELF_DIR/\.\./current/skills/[\w-]+/scripts)/|\.\./synthesis-skills/skills/', prefix):
        return True
    named = re.match(r'"?(<[\w-]+>|\$\{?(\w+)\}?)/', prefix)
    if not named:
        return False
    word = named.group(1) if named.group(1).startswith("<") else named.group(2)
    within = rf"(?:{stable}|\$\{{?\w+\}}?/current/skills/{re.escape(skill)})"  # also through the synthesis home's own variable
    return bool(re.search(rf"(?:`{re.escape(word)}`|\b{re.escape(word)}=|`\${re.escape(word)}`)[^\n]*{within}", text))


def test_every_skill_text_and_script_runs_the_runtimes_copy_of_a_carried_script():
    """A skill that runs one of the runtime's scripts names the runtime's path, as the autopilot skill does: a copy
    anywhere else is not the plugin's own and waits for the principal's code (the coordinator, 2026-11-15)."""
    carried = {}
    for rel, _ in install._stable_skill_files(ROOT):
        carried.setdefault(Path(rel).parts[1], set()).add(Path(rel).name)
    wrong = []
    for path in sorted((ROOT / "skills").rglob("*")):
        rel = path.relative_to(ROOT / "skills").parts
        if not path.is_file() or ARCHIVAL.search(path.name) or "tests" in rel or path.name.startswith("test_") or (
                path.suffix not in (".md", ".py", ".sh", ".json", ".yaml", ".txt") and path.name != "day-end"):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for n, line in enumerate(text.splitlines(), 1):
            for m in INVOKE.finditer(line):
                prefix, name = m.group(1) or "", m.group(2)
                skill = next((s for s in carried if f"skills/{s}/" in prefix or f"<{s}>" in prefix or f"<{s}-root>" in prefix), None) or next(
                    (s for alias, s in ALIASES.items() if prefix.lstrip('"').startswith(alias)), None) or (rel[0] if rel[0] in carried else None)
                if skill and name in carried[skill] and not _runtime_form(prefix, skill, text):
                    wrong.append(f"skills/{'/'.join(rel)}:{n}: {m.group(0).strip()}")
    assert not wrong, "these run a copy outside the runtime:\n" + "\n".join(wrong)


@pytest.mark.parametrize("skill", sorted(set(install.STABLE_SKILL_SCRIPTS) | {"synthesis-checkpoint", "synthesis-mac-sync",
                                                                             "synthesis-machine-sync", "synthesis-slack-sync"}))
def test_a_skill_that_runs_the_runtimes_scripts_stays_under_its_size_limit(skill):
    assert len((ROOT / "skills" / skill / "SKILL.md").read_bytes()) < 8000, skill

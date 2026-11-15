"""The runtime carries every script of a skill it carries, so a skill script run from a harness's plugin copy is the
plugin's own (`guards._shipped`) when the guard runs from the runtime, not only when it runs from a checkout.

2026-11-15: a seat's day-end ran the meeting fetcher from the plugin cache, and the installed guard held it for the
principal's code: the runtime carried only the `scripts/` folders of six skills, the fetcher lives in
`optional-workspace-mcp/` of a skill not among them, so the guard could not vouch for it and read the project-local
`.claude` folder in its text as the harness's transcripts. The tests in the checkout passed it because there the guard
runs beside every skill. These tests build the runtime as install.py does and run the guard from it."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from synthesis import install

ROOT = Path(__file__).resolve().parents[1]
FETCHER = "skills/synthesis-meeting-transcripts/optional-workspace-mcp/fetch-meeting.py"
PROGRAM = ("import json, sys; sys.path.insert(0, sys.argv[1]); from synthesis import guards; "
           "print(json.dumps(guards.check('Bash', {'command': sys.argv[2]}, {}, cwd=sys.argv[3], "
           "session={'session_id': 'S-test', 'cwd': sys.argv[3]})))")


def test_the_runtime_carries_the_meeting_and_message_skills_scripts():
    carried = {rel for rel, _ in install._stable_skill_files(ROOT)}
    assert {"synthesis-meeting-transcripts", "synthesis-message-exports"} <= set(install.STABLE_SKILL_SCRIPTS)
    for rel in (FETCHER, "skills/synthesis-meeting-transcripts/optional-workspace-mcp/mcp_client.py",
                "skills/synthesis-meeting-transcripts/verify_transcripts.py",
                "skills/synthesis-meeting-transcripts/extract_commitments.py",
                "skills/synthesis-message-exports/scripts/import_messages.py",
                "skills/synthesis-message-exports/scripts/chat_page.py"):
        assert rel in carried, rel


def test_a_carried_skills_code_outside_scripts_is_python_only_and_never_its_tests():
    for rel, path in install._stable_skill_files(ROOT):
        parts = Path(rel).parts
        assert "tests" not in parts and "__pycache__" not in parts and not path.name.startswith("test_"), rel
        if parts[2] != "scripts":
            assert path.suffix == ".py", rel


def _release(tmp_path):
    """The runtime as install.py builds it under releases/<hash>/: synthesis/ and the carried skills' scripts."""
    release = tmp_path / "release"
    shutil.copytree(ROOT / "synthesis", release / "synthesis", ignore=shutil.ignore_patterns("__pycache__"))
    for rel, path in install._stable_skill_files(ROOT):
        (release / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, release / rel)
    return release


def _plugin_copy(tmp_path):
    """A harness's plugin cache: the skill as it shipped, outside the runtime."""
    copy = tmp_path / "plugin-cache" / "synthesis-skills" / "5.23.1"
    shutil.copytree(ROOT / "skills" / "synthesis-meeting-transcripts", copy / "skills" / "synthesis-meeting-transcripts",
                    ignore=shutil.ignore_patterns("__pycache__", "tests"))
    return copy


def _env(tmp_path):
    """Every home under tmp_path; Claude Code's records at the default place under that home, so the text `.claude`
    beside `projects` spells a protected folder, as it does on a Mac."""
    home = tmp_path / "home"
    (home / ".claude" / "projects").mkdir(parents=True)
    env = {k: v for k, v in os.environ.items() if k not in (
        "CLAUDE_CONFIG_DIR", "SYNTHESIS_SESSION", "CLAUDE_CODE_SESSION_ID", "CLAUDECODE", "CODEX_THREAD_ID", "MUSE_SESSION_ID")}
    env.update(HOME=str(home), SYNTHESIS_HOME=str(home / ".synthesis" / "v5"), CODEX_HOME=str(tmp_path / "codex"),
               XDG_DATA_HOME=str(tmp_path / "xdg"), SYNTHESIS_CLAUDE_DESKTOP_DIR=str(tmp_path / "desktop"),
               RITUAL_STATE_DIR=str(tmp_path / "rituals"))
    return env


def _verdict(release, command, cwd, env):
    done = subprocess.run([sys.executable, "-I", "-c", PROGRAM, str(release), command, str(cwd)], capture_output=True,
                          text=True, timeout=120, env=env)
    assert done.returncode == 0, done.stderr[-800:]
    return json.loads(done.stdout)


def test_the_meeting_fetcher_from_a_plugin_copy_needs_no_code_when_the_guard_runs_from_the_runtime(tmp_path):
    release, copy, env = _release(tmp_path), _plugin_copy(tmp_path), _env(tmp_path)
    work = tmp_path / "work"
    work.mkdir()
    assert _verdict(release, f"python3 {copy / FETCHER} --window 2026-11-14 2026-11-15", work, env) is None


RITUAL_READERS = ["skills/synthesis-context-lifecycle/scripts/context_doctor.py --project {work}",
                  "skills/synthesis-local-messaging/scripts/local_messaging.py --help"]


@pytest.mark.parametrize("call", RITUAL_READERS)
def test_a_ritual_script_from_a_plugin_copy_needs_no_code_when_the_guard_runs_from_the_runtime(tmp_path, call):
    """2026-11-15: a seat's day-end found both held, so the messages watermark could not move and the records gate could
    not run without the principal's code."""
    release, env = _release(tmp_path), _env(tmp_path)
    work = tmp_path / "work"
    work.mkdir()
    script, _, rest = call.format(work=work).partition(" ")
    skill = Path(script).parts[1]
    copy = tmp_path / "plugin-cache" / "synthesis-skills" / "5.23.1"
    shutil.copytree(ROOT / "skills" / skill, copy / "skills" / skill, ignore=shutil.ignore_patterns("__pycache__", "tests"))
    assert _verdict(release, f"python3 {copy / script} {rest}", work, env) is None, call


def test_the_installer_and_release_kit_is_never_carried():
    """setup.py, workspace.py and release.py write the trust base itself: they are never vouched for from a plugin copy."""
    assert not {"synthesis-skills-manager", "synthesis-onboarding"} & set(install.STABLE_SKILL_SCRIPTS)


def test_a_changed_plugin_copy_of_the_fetcher_still_waits(tmp_path):
    release, copy, env = _release(tmp_path), _plugin_copy(tmp_path), _env(tmp_path)
    work = tmp_path / "work"
    work.mkdir()
    script = copy / FETCHER
    script.write_text(script.read_text(encoding="utf-8") + "\n# changed after it shipped\n", encoding="utf-8")
    assert _verdict(release, f"python3 {script} --window 2026-11-14 2026-11-15", work, env)

"""`synthesis doctor` (R7.1, R7.5-R7.7, R3.8, R8.1) and the Muse hook adapter.

Every check is fed fake inputs here; the end-to-end tests put fake harness CLIs on
PATH in a temporary HOME, so no real harness state is read or written.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import pytest

import synthesis
from synthesis import doctor, install, paths

ROOT = Path(__file__).resolve().parents[1]
REPO_HOOKS = json.loads((ROOT / "hooks" / "hooks.json").read_text())
MUSE_MANIFEST = json.loads((ROOT / ".muse-plugin" / "plugin.json").read_text())
PLUGIN_ID = "synthesis-skills@synthesis-engineering"


def plugin_copy(dest: Path, source: Path = ROOT) -> Path:
    """A plugin folder as a harness would cache it: the runtime package and every hook adapter."""
    shutil.copytree(source / "synthesis", dest / "synthesis", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(source / "hooks", dest / "hooks")
    shutil.copytree(source / ".muse-plugin", dest / ".muse-plugin")
    return dest


@pytest.fixture
def runtime(tmp_path, isolated_home):
    """A v5 runtime installed from a plugin copy; returns (synthesis home, plugin copy)."""
    plugin = plugin_copy(tmp_path / "plugin")
    install.install(plugin)
    return isolated_home, plugin


def deny(reason="refusing a recursive delete of /home: it is a protected root or a repository", delay=0.0):
    def run(*args, **kwargs):
        time.sleep(delay)
        out = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                      "permissionDecisionReason": reason}}
        return subprocess.CompletedProcess(args, 0, json.dumps(out), "")
    return run


def allow(*args, **kwargs):
    return subprocess.CompletedProcess(args, 0, "", "")


# ---- the stable runtime -------------------------------------------------------

def test_missing_runtime_fails(isolated_home):
    check = doctor.check_runtime(isolated_home)
    assert check.status == "fail" and "no stable hook" in check.detail
    assert doctor.check_hook_script(isolated_home).status == "fail"


def test_installed_runtime_resolves_and_its_hook_text_matches(runtime):
    home, plugin = runtime
    check = doctor.check_runtime(home)
    assert check.status == "ok" and install.package_hash(plugin) in check.detail
    assert doctor.check_hook_script(home).status == "ok"


def test_runtime_files_changed_after_install_fail(runtime):
    home, _ = runtime
    guards = home / "current" / "synthesis" / "guards.py"
    guards.write_text(guards.read_text() + "\n# edited in place\n")
    check = doctor.check_runtime(home)
    assert check.status == "fail" and "changed since install" in check.detail


def test_drifted_hook_script_fails(runtime):
    home, _ = runtime
    (home / "bin" / "synthesis-hook").write_text(install.HOOK_SCRIPT.replace("-S", ""))
    assert doctor.check_hook_script(home).status == "fail"


def test_config_states(isolated_home, write_config):
    assert doctor.check_config(isolated_home).status == "warn"  # missing: defaults apply
    write_config({"send_tools": []})
    assert doctor.check_config(isolated_home).status == "ok"
    (isolated_home / "config.json").write_text("{not json")
    assert doctor.check_config(isolated_home).status == "fail"
    (isolated_home / "config.json").write_text("[]")
    check = doctor.check_config(isolated_home)
    assert check.status == "fail" and "JSON object" in check.detail


def test_self_test_runs_the_real_stable_hook_and_reports_ms(runtime):
    home, _ = runtime
    check = doctor.check_self_test(home)
    assert check.status in ("ok", "warn"), check  # warn only when this machine is slower than 50 ms
    assert re.match(r"denied `rm -rf ~` in \d+ ms", check.detail), check.detail


def test_self_test_fails_when_the_hook_lets_the_command_through(runtime):
    home, _ = runtime
    check = doctor.check_self_test(home, run=allow)
    assert check.status == "fail" and "let `rm -rf ~` through" in check.detail


def test_self_test_fails_when_the_deny_is_for_another_reason(runtime):
    home, _ = runtime
    check = doctor.check_self_test(home, run=deny("synthesis guard config is unreadable"))
    assert check.status == "fail"


def test_self_test_warns_over_the_latency_budget(runtime):
    home, _ = runtime
    check = doctor.check_self_test(home, runs=1, run=deny(delay=0.06), background=lambda: False)
    assert check.status == "warn" and "over the 50 ms budget" in check.detail


def test_self_test_at_background_priority_reports_the_time_without_judging_it(runtime):
    """2026-11-02: the Console runs as a launchd Background job, and its doctor read 131 ms; 37 ms at normal priority."""
    home, _ = runtime
    check = doctor.check_self_test(home, runs=1, run=deny(delay=0.06), background=lambda: True)
    assert check.status == "info" and "background priority" in check.detail
    assert doctor.check_self_test(home, runs=1, run=allow, background=lambda: True).status == "fail"


def test_background_priority_is_read_from_the_os():
    assert doctor.background_priority() is False  # this test process runs at normal priority
    if sys.platform == "darwin":
        probe = "from synthesis import doctor; print(doctor.background_priority())"
        out = subprocess.run(["taskpolicy", "-b", sys.executable, "-c", probe], capture_output=True, text=True,
                             cwd=Path(doctor.__file__).parents[1]).stdout.strip()
        assert out == "True"


def test_self_test_times_the_fastest_run(runtime):
    """2026-11-02: the Console's own scans ran beside the doctor, and a median of three runs read 161 ms."""
    home, _ = runtime
    delays = iter([0.2, 0.0, 0.2])
    busy = lambda *args, **kwargs: deny(delay=next(delays))(*args, **kwargs)  # noqa: E731
    check = doctor.check_self_test(home, run=busy)
    assert check.status == "ok", check.detail


def test_shell_name_probe(runtime):
    home, _ = runtime
    assert doctor.check_shell_name(home, "muse", "bash", run=deny()).status == "ok"
    check = doctor.check_shell_name(home, "muse", "bash", run=allow)
    assert check.status == "warn" and "`bash`" in check.detail


# ---- harness plugin state -----------------------------------------------------

def test_plugin_entry_states(tmp_path):
    assert doctor.check_plugin("claude", None).status == "fail"
    assert doctor.check_plugin("codex", None, "`codex plugin list` gave no JSON").status == "fail"
    slow = doctor.check_plugin("codex", None, "cannot tell: `codex plugin list` did not answer within 45 s; run the doctor again")
    assert slow.status == "warn" and "did not answer" in slow.detail  # 2026-10-10: slow, not broken
    off = {"enabled": False, "version": "5.0.0", "path": tmp_path}
    assert "disabled" in doctor.check_plugin("muse", off).detail
    on = {**off, "enabled": True}
    assert doctor.check_plugin("muse", on).status == "ok"
    assert doctor.check_plugin("muse", {**on, "problem": "manifest invalid"}).status == "fail"


def test_package_matching_the_runtime_is_ok(runtime):
    home, plugin = runtime
    assert doctor.check_package("claude", plugin, doctor.runtime_hash(home)).status == "ok"


def test_stale_installed_package_fails_whatever_its_version_label(runtime, tmp_path):
    home, plugin = runtime
    stale = plugin_copy(tmp_path / "stale", plugin)
    (stale / "synthesis" / "guards.py").write_text("# an older release\n")  # same 5.0.0 label, other bytes
    check = doctor.check_package("codex", stale, doctor.runtime_hash(home))
    assert check.status == "fail" and "differs from the runtime" in check.detail


def test_old_plugin_without_a_runtime_package_fails(runtime, tmp_path):
    home, _ = runtime
    (tmp_path / "v4").mkdir()
    assert doctor.check_package("claude", tmp_path / "v4", doctor.runtime_hash(home)).status == "fail"
    assert doctor.check_package("claude", None, doctor.runtime_hash(home)).status == "fail"


def test_bytecode_written_into_a_plugin_folder_warns(runtime):
    home, plugin = runtime
    (plugin / "synthesis" / "__pycache__").mkdir()
    check = doctor.check_package("muse", plugin, doctor.runtime_hash(home))
    assert check.status == "warn" and "__pycache__" in check.detail


def test_listing_parsers_read_each_cli_shape(tmp_path):
    claude = [{"id": "other@x", "enabled": True},
              {"id": PLUGIN_ID, "version": "5.0.0", "enabled": True, "installPath": str(tmp_path)}]
    assert doctor.claude_entry(claude) == {"enabled": True, "version": "5.0.0", "path": tmp_path}
    assert doctor.claude_entry([]) is None
    cache = tmp_path / ".codex" / "plugins" / "cache" / "synthesis-engineering" / "synthesis-skills" / "5.0.0"
    cache.mkdir(parents=True)
    codex = {"installed": [{"pluginId": PLUGIN_ID, "name": "synthesis-skills", "marketplaceName": "synthesis-engineering",
                            "version": "5.0.0", "enabled": True}], "available": []}
    assert doctor.codex_entry(codex, tmp_path / ".codex")["path"] == cache
    muse = {"record": {"id": "synthesis-skills", "version": "5.0.0", "enabled": True, "cache_path": str(tmp_path)},
            "valid": False, "diagnostics": [{"code": "missing-capability-path"}]}
    assert "missing-capability-path" in doctor.muse_entry(muse)["problem"]
    assert doctor.muse_entry({"error": {"code": "unknown-plugin"}}) is None


def test_plugin_hooks_json_is_wired_to_the_stable_hook():
    commands = [(e, h["command"]) for e, _, h in doctor.hooks_json_entries(REPO_HOOKS)]
    assert doctor.check_hooks_wired("claude", commands).status == "ok"


def test_hooks_that_bypass_the_stable_path_fail():
    old = [("SessionStart", '"$HOME/.local/bin/synthesis" exec-public session_context.py'),
           ("PreToolUse", '"$HOME/.synthesis/v5/bin/synthesis-hook" pre-tool-use')]
    check = doctor.check_hooks_wired("codex", old)
    assert check.status == "fail"
    assert check.detail.endswith("SessionStart, UserPromptSubmit, Stop")


# ---- Claude Code holds a guarded call when the guard cannot answer (5.21.0) ----------------------------------------
# A PreToolUse hook that times out, crashes or cannot start lets the call through in Claude Code unless its handler sets
# "onFailure": "block", which Claude Code honors from 2.1.295 (its hooks reference); Codex and Muse have no such setting.

def test_the_doctor_fails_a_plugin_whose_guard_lets_a_call_through_when_it_cannot_answer():
    assert doctor.check_claude_fail_closed(REPO_HOOKS, "2.1.316").status == "ok"
    lacking = json.loads(json.dumps(REPO_HOOKS))
    del lacking["hooks"]["PreToolUse"][0]["hooks"][0]["onFailure"]
    check = doctor.check_claude_fail_closed(lacking, "2.1.316")
    assert check.status == "fail" and check.name == "claude fail closed" and '"onFailure": "block"' in check.detail
    lacking["hooks"]["PreToolUse"][0]["hooks"][0]["onFailure"] = "continue"
    assert doctor.check_claude_fail_closed(lacking, "2.1.316").status == "fail"
    assert doctor.check_claude_fail_closed({}, "2.1.316").status == "fail"           # no PreToolUse hook at all


@pytest.mark.parametrize("version,status", [("2.1.294", "warn"), ("2.1.30", "warn"), ("2.0.999", "warn"), ("2.1.295", "ok"),
                                            ("2.1.1000", "ok"), ("3.0", "ok"), ("", "warn")])
def test_the_doctor_warns_when_claude_code_cannot_honor_the_setting(version, status):
    check = doctor.check_claude_fail_closed(REPO_HOOKS, version)
    assert check.status == status
    assert ("2.1.295" in check.detail and version in check.detail) if version and status == "warn" else True
    assert "cannot tell" in check.detail if not version else True


def test_claude_version_is_the_number_claude_prints_first(tmp_path):
    def cli(name, line):
        path = tmp_path / name
        path.write_text(f"#!/bin/sh\necho '{line}'\n")
        path.chmod(0o755)
        return str(path)
    assert doctor.claude_version(cli("claude", "2.1.316 (Claude Code)")) == "2.1.316"
    assert doctor.claude_version(cli("other", "Claude Code")) == ""
    assert doctor.claude_version(str(tmp_path / "missing")) == ""


# ---- Codex --------------------------------------------------------------------

# Hashes Codex 0.160.0 itself stored in config.toml for the 4.154.12 plugin's hooks.
CODEX_VECTORS = [
    ("SessionStart", None, {"type": "command", "timeout": 30,
                            "command": '"${SYNTHESIS_INSTALL_BIN_DIR:-$HOME/.local/bin}/synthesis" exec-public --timeout-seconds 28 '
                                       "synthesis-agent-conformance/scripts/session_context.py --format claude",
                            "statusMessage": "Loading verified synthesis project context"},
     "sha256:b5837309ccbab059f8da06b575a2600af5b724dd011836c15cf71aa44f925d44"),
    ("PreToolUse", "Bash|exec_command|exec|shell|local_shell",
     {"type": "command", "timeout": 15,
      "command": '"${SYNTHESIS_INSTALL_BIN_DIR:-$HOME/.local/bin}/synthesis" exec-public --timeout-seconds 13 '
                 "synthesis-project-management/scripts/peer_send_gate.py --gate"},
     "sha256:26f2c8b479253f196beae32ba6f452e2295a4a42e7611c7d26ee6873513b8b8d"),
    ("Stop", None, {"type": "command", "timeout": 15,
                    "command": '"${SYNTHESIS_INSTALL_BIN_DIR:-$HOME/.local/bin}/synthesis" exec-public --hook-event Stop '
                               "--timeout-seconds 13 synthesis-autopilot/scripts/autopilot_gate.py --gate",
                    "statusMessage": "Checking autopilot engagements for a continuation"},
     "sha256:1900160c159b1b3765dd358c8e655792ebfa1d6c1c04d1452ac0e76e0644cfa8"),
]


@pytest.mark.parametrize("event,matcher,handler,expected", CODEX_VECTORS)
def test_codex_trust_hash_reproduces_codex(event, matcher, handler, expected):
    assert doctor.codex_hook_hash(event, matcher, handler) == expected


def trusted_state(hooks=REPO_HOOKS, plugin_id=PLUGIN_ID):
    state = {}
    for event, groups in hooks["hooks"].items():
        for gi, group in enumerate(groups):
            for hi, handler in enumerate(group["hooks"]):
                key = f"{plugin_id}:hooks/hooks.json:{doctor._snake(event)}:{gi}:{hi}"
                state[key] = {"trusted_hash": doctor.codex_hook_hash(event, group.get("matcher"), handler)}
    return state


def test_codex_hooks_all_trusted():
    check = doctor.check_codex_trust(REPO_HOOKS, {"hooks": {"state": trusted_state()}}, PLUGIN_ID)
    assert check.status == "ok" and "all 4" in check.detail


def test_untrusted_codex_hook_needs_hooks_approval():
    state = trusted_state()
    del state[f"{PLUGIN_ID}:hooks/hooks.json:pre_tool_use:0:0"]
    check = doctor.check_codex_trust(REPO_HOOKS, {"hooks": {"state": state}}, PLUGIN_ID)
    assert check.status == "fail"
    assert check.detail == "needs /hooks approval: pre_tool_use:0:0 untrusted"


def test_changed_and_disabled_codex_hooks_need_approval():
    state = trusted_state()
    state[f"{PLUGIN_ID}:hooks/hooks.json:stop:0:0"]["trusted_hash"] = CODEX_VECTORS[2][3]  # trusted an older command
    state[f"{PLUGIN_ID}:hooks/hooks.json:user_prompt_submit:0:0"]["enabled"] = False
    detail = doctor.check_codex_trust(REPO_HOOKS, {"hooks": {"state": state}}, PLUGIN_ID).detail
    assert "stop:0:0 modified" in detail and "user_prompt_submit:0:0 disabled" in detail


def test_codex_trust_without_a_hooks_file_fails():
    assert doctor.check_codex_trust(None, {}, PLUGIN_ID).status == "fail"


# ---- Codex ties a hook approval to the plugin's files (Codex 0.166) ----------------------------------------------

def _plugin(tmp_path):
    root = tmp_path / "plugin"
    (root / "synthesis").mkdir(parents=True)
    (root / "synthesis" / "hook.py").write_text("print('hook')\n")
    return root


def test_the_codex_fingerprint_reproduces_codex(tmp_path):
    """A fixed tree's fingerprint, from the code that reproduced on 2026-11-05 the fingerprint Codex 0.166 stored when
    the synthesis 5.3.14 hooks were approved (sha256:161ba7ca..., over the installed plugin and its .git)."""
    root = tmp_path / "plugin"
    (root / "b").mkdir(parents=True)
    (root / "a.txt").write_bytes(b"x")
    (root / "b" / "c.py").write_bytes(b"print(1)\n")
    expected = "sha256:232fde32ff1c340573c4d728c8a6e2bce2477b1ebf09aa4a3ab63f64f6b577de"
    assert doctor.codex_plugin_hash(root) == expected
    for skipped in ("b/__pycache__/c.cpython-312.pyc", "d.pyc", ".venv/bin/python", "pkg.egg-info/PKG-INFO"):
        (root / skipped).parent.mkdir(parents=True, exist_ok=True)
        (root / skipped).write_bytes(b"generated")
    assert doctor.codex_plugin_hash(root) == expected  # bytecode, virtual environments and package metadata
    (root / "a.txt").write_bytes(b"y")
    assert doctor.codex_plugin_hash(root) != expected


def test_hooks_approved_for_earlier_plugin_files_need_approval_again(tmp_path):
    """2026-11-05: Codex ran none of synthesis's hooks after a release, since it ties each approval to the plugin's
    files, while doctor, which compared only the hook definitions, reported all four trusted."""
    root = _plugin(tmp_path)
    state = trusted_state()
    for value in state.values():
        value["trusted_content_hash"] = "sha256:" + "0" * 64
    check = doctor.check_codex_trust(REPO_HOOKS, {"hooks": {"state": state}}, PLUGIN_ID, root)
    assert check.status == "fail" and "approved before the plugin last changed" in check.detail
    for value in state.values():
        value["trusted_content_hash"] = doctor.codex_plugin_hash(root)
    assert doctor.check_codex_trust(REPO_HOOKS, {"hooks": {"state": state}}, PLUGIN_ID, root).status == "ok"


def test_an_approval_from_before_codex_stored_fingerprints_is_held_to_its_baseline(tmp_path):
    """Codex pins one baseline per plugin for an approval that carries no fingerprint, at the path its plugin_trust.rs
    derives from the config file and the plugin id (it matched a real Codex home on 2026-11-05)."""
    root, codex_home = _plugin(tmp_path), tmp_path / "codex"
    config = {"hooks": {"state": trusted_state()}}
    assert doctor.check_codex_trust(REPO_HOOKS, config, PLUGIN_ID, root, codex_home).status == "ok"  # pinned on use
    baseline = doctor.codex_trust_baseline(codex_home, PLUGIN_ID)
    assert baseline.parent == codex_home / ".hook-trust" and len(baseline.name) == 64
    baseline.parent.mkdir(parents=True)
    baseline.write_text("sha256:" + "0" * 64)
    check = doctor.check_codex_trust(REPO_HOOKS, config, PLUGIN_ID, root, codex_home)
    assert check.status == "fail" and "approved before the plugin last changed" in check.detail
    baseline.write_text(doctor.codex_plugin_hash(root))
    assert doctor.check_codex_trust(REPO_HOOKS, config, PLUGIN_ID, root, codex_home).status == "ok"


def test_a_plugin_codex_cannot_fingerprint_runs_none_of_its_hooks(tmp_path):
    root = _plugin(tmp_path)
    (root / "link").symlink_to(root / "synthesis" / "hook.py")
    check = doctor.check_codex_trust(REPO_HOOKS, {"hooks": {"state": trusted_state()}}, PLUGIN_ID, root)
    assert check.status == "fail" and "Codex cannot fingerprint the plugin" in check.detail



# ---- the plugin's hooks declared in Codex's own hooks.json (setup.py plugin --codex-user-hooks) ----------------
# A hook declared there is trusted by its declaration's hash alone (codex-rs hooks discovery); Codex keys its state by
# the file's path under the home's real path, then the event, group and hook. The plugin's own copies are switched
# off by their keys, so no event runs twice.

# Hashes Codex 0.167.0-alpha.4.1 itself listed (`hooks/list`, currentHash) on 2026-11-14 for the declaration setup
# writes in its hooks.json.
USER_VECTORS = [
    ("PreToolUse", "Bash|bash|exec_command|exec|shell|shell_command|local_shell|run_shell_command|Write|Edit|MultiEdit|"
                   "NotebookEdit|write_file|edit_file|apply_patch|mcp__.*",
     {"type": "command", "command": '"$HOME/.synthesis/v5/bin/synthesis-hook" pre-tool-use', "timeout": 5},
     "sha256:6c8d97c7c6a55e53583887c9bff851062afa0277b33ca516fb67699622541168"),
    ("SessionStart", None, {"type": "command", "command": '"$HOME/.synthesis/v5/bin/synthesis-hook" session-start', "timeout": 10},
     "sha256:de4a793387c7da5d3a3a124a8e0c47e38ecab0fde1d87c7ba6ea08133fcce2e5"),
    ("UserPromptSubmit", None, {"type": "command", "command": '"$HOME/.synthesis/v5/bin/synthesis-hook" user-prompt-submit',
                                "timeout": 5}, "sha256:5ae284fc312782e3a758ee842940df7893033cba5c1c0aa3b81f447113a164fc"),
    ("Stop", None, {"type": "command", "command": '"$HOME/.synthesis/v5/bin/synthesis-hook" stop', "timeout": 5},
     "sha256:016cfe12ed31f67f845ff0187b6aef11dcf03d304592bf0671a193d1dcfd1538"),
]


@pytest.mark.parametrize("event,matcher,handler,expected", USER_VECTORS)
def test_codex_trust_hash_reproduces_codex_for_a_user_level_declaration(event, matcher, handler, expected):
    assert doctor.codex_hook_hash(event, matcher, handler) == expected


def test_the_user_level_declaration_is_the_plugins_with_the_stable_hook_for_each_event():
    declared = doctor.codex_user_declaration(REPO_HOOKS)
    assert set(declared) == set(REPO_HOOKS["hooks"]) == set(doctor.EVENTS)
    for event, groups in declared.items():
        plugin = REPO_HOOKS["hooks"][event]
        assert [{k: v for k, v in g.items() if k != "hooks"} for g in groups] == [{k: v for k, v in g.items() if k != "hooks"} for g in plugin]
        for mine, theirs in zip(groups, plugin):
            assert [{**h, "command": ""} for h in mine["hooks"]] == [{**h, "command": ""} for h in theirs["hooks"]]
            assert all(h["command"] == f'"{doctor.STABLE_HOOK}" {doctor.EVENTS[event]}' for h in mine["hooks"])
    assert doctor.codex_hooks_problem({"hooks": declared}) == "" and doctor.codex_hooks_problem(REPO_HOOKS) == ""


def test_the_user_level_declaration_carries_the_guards_setting_and_codex_reads_and_trusts_it_as_before():
    """5.21.0: the plugin's guard carries "onFailure": "block" for Claude Code, and the user-level copy carries it too,
    as the plugin writes it. Codex 0.167.0-alpha.4.1 read all four with it and listed the guard's currentHash as it
    was without it (2026-11-14), so the approval a person gave before still holds."""
    declared = doctor.codex_user_declaration(REPO_HOOKS)
    guard = declared["PreToolUse"][0]
    assert guard["hooks"][0]["onFailure"] == "block" and doctor.codex_hooks_problem({"hooks": declared}) == ""
    assert doctor.codex_hook_hash("PreToolUse", guard["matcher"], guard["hooks"][0]) == USER_VECTORS[0][3]


def user_level(tmp_path, declared=None, trusted=True, plugin_off=True, home=None):
    """A Codex home whose hooks.json declares the plugin's hooks as setup writes them, and the config state: the
    user-level hooks approved (or not), the plugin's own switched off (or left as approved)."""
    home = home or tmp_path / "codex"
    home.mkdir(exist_ok=True)
    declared = declared or doctor.codex_user_declaration(REPO_HOOKS)
    (home / "hooks.json").write_text(json.dumps({"hooks": declared}))
    state = {key: {"enabled": False} for key in trusted_state()} if plugin_off else trusted_state()
    if trusted:
        for event, groups in declared.items():
            for gi, group in enumerate(groups):
                for hi, handler in enumerate(group["hooks"]):
                    key = f"{os.path.realpath(home)}{os.sep}hooks.json:{doctor._snake(event)}:{gi}:{hi}"
                    state[key] = {"trusted_hash": doctor.codex_hook_hash(event, group.get("matcher"), handler)}
    mark = "  # synthesis-setup: codex-user-hooks"  # the switches as setup writes them, which tell the doctor the option is on
    (home / "config.toml").write_text("".join(f'[hooks.state."{key}"]{mark}\nenabled = false{mark}\n'
                                              for key in trusted_state()) if plugin_off else "")
    return home, {"hooks": {"state": state}}


def test_with_a_user_level_declaration_its_trust_is_judged_and_the_plugins_switched_off_copies_are_intended(tmp_path):
    home, config = user_level(tmp_path)
    check = doctor.check_codex_trust(REPO_HOOKS, config, PLUGIN_ID, _plugin(tmp_path), home)
    assert check.status == "ok" and "all 4 synthesis hooks trusted" in check.detail and "hooks.json" in check.detail
    assert "disabled" not in check.detail and "approved before" not in check.detail


def test_user_level_hooks_waiting_for_approval_are_named_by_their_own_keys(tmp_path):
    home, config = user_level(tmp_path, trusted=False)
    check = doctor.check_codex_trust(REPO_HOOKS, config, PLUGIN_ID, _plugin(tmp_path), home)
    assert check.status == "fail" and "needs /hooks approval" in check.detail
    assert "hooks.json:pre_tool_use:0:0 untrusted" in check.detail and "hooks.json:stop:0:0 untrusted" in check.detail
    assert "disabled" not in check.detail                                             # the plugin's copies are off on purpose
    home, config = user_level(tmp_path)
    states = config["hooks"]["state"]
    states[f"{os.path.realpath(home)}{os.sep}hooks.json:stop:0:0"]["trusted_hash"] = USER_VECTORS[0][3]  # approved otherwise
    states[f"{os.path.realpath(home)}{os.sep}hooks.json:session_start:0:0"]["enabled"] = False
    detail = doctor.check_codex_trust(REPO_HOOKS, config, PLUGIN_ID, None, home).detail
    assert "hooks.json:stop:0:0 modified" in detail and "hooks.json:session_start:0:0 disabled" in detail


def test_only_an_approval_the_person_gives_is_a_wait_and_a_fault_of_setup_is_not(tmp_path):
    """5.21.0: the release counts a failing approval line as waiting on the person, so a fault the same line can name
    (a plugin copy left on, a declaration unlike the plugin's, a plugin Codex cannot fingerprint) must not read as one."""
    home, config = user_level(tmp_path, trusted=False)
    root = _plugin(tmp_path)
    assert doctor.waits_on_person(doctor.check_codex_trust(REPO_HOOKS, config, PLUGIN_ID, root, home))
    home, config = user_level(tmp_path, plugin_off=False)
    assert not doctor.waits_on_person(doctor.check_codex_trust(REPO_HOOKS, config, PLUGIN_ID, None, home))
    (root / "link").symlink_to(root / "synthesis" / "hook.py")
    check = doctor.check_codex_trust(REPO_HOOKS, {"hooks": {"state": trusted_state()}}, PLUGIN_ID, root)
    assert check.status == "fail" and not doctor.waits_on_person(check)
    assert not doctor.waits_on_person(doctor.Check("fail", "muse hook approval", "the installed plugin registers no hooks"))
    assert doctor.waits_on_person(doctor.Check("fail", "muse hook approval", "run `muse plugins approve synthesis-skills`: x"))
    assert not doctor.waits_on_person(doctor.Check("fail", "runtime", "needs /hooks approval: x"))


def test_a_plugin_copy_left_on_beside_the_user_level_declaration_fails(tmp_path):
    """Both copies would run once approved: the guard twice on every call."""
    home, config = user_level(tmp_path, plugin_off=False)
    check = doctor.check_codex_trust(REPO_HOOKS, config, PLUGIN_ID, None, home)
    assert check.status == "fail" and "pre_tool_use:0:0 is not switched off" in check.detail


def test_the_user_level_key_names_the_codex_home_by_its_real_path(tmp_path):
    real, link = tmp_path / "real-codex", tmp_path / "linked-codex"
    real.mkdir()
    link.symlink_to(real)
    home, config = user_level(tmp_path, home=real)
    assert doctor.check_codex_trust(REPO_HOOKS, config, PLUGIN_ID, None, link).status == "ok"


def test_without_a_user_level_declaration_the_line_is_as_before(tmp_path):
    home = tmp_path / "codex"
    home.mkdir()
    (home / "hooks.json").write_text(json.dumps({"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "/bin/echo bye"}]}]}}))
    for state in (trusted_state(), {key: {"enabled": False} for key in trusted_state()}):
        config = {"hooks": {"state": state}}
        assert doctor.check_codex_trust(REPO_HOOKS, config, PLUGIN_ID, None, home) == doctor.check_codex_trust(REPO_HOOKS, config, PLUGIN_ID)
    assert "pre_tool_use:0:0 disabled" in doctor.check_codex_trust(REPO_HOOKS, config, PLUGIN_ID, None, home).detail


def test_a_user_hooks_file_codex_cannot_read_is_named(tmp_path):
    home, config = user_level(tmp_path)
    (home / "hooks.json").write_text('{"hooks": {"Stop": [{"hooks": [{"type": "http", "url": "x"}]}]}}')
    check = doctor.check_codex_trust(REPO_HOOKS, config, PLUGIN_ID, None, home)
    assert check.status == "fail" and "Codex reads none of" in check.detail and "hooks.json" in check.detail
    (home / "hooks.json").write_text("{not json")
    assert "Codex cannot read" in doctor.check_codex_trust(REPO_HOOKS, config, PLUGIN_ID, None, home).detail


def test_a_user_level_declaration_unlike_the_plugins_is_named(tmp_path):
    """After a release that changed the plugin's declaration, the user-level copy runs the old one until setup runs."""
    declared = doctor.codex_user_declaration(REPO_HOOKS)
    declared["PreToolUse"][0]["matcher"] = "Bash"
    home, config = user_level(tmp_path, declared=declared)
    paths.write_json(paths.codex_hooks_record(), {str(Path(os.path.realpath(home)) / "hooks.json"): {"groups": declared}})
    check = doctor.check_codex_trust(REPO_HOOKS, config, PLUGIN_ID, None, home)
    assert check.status == "fail" and "differs from the plugin's PreToolUse" in check.detail
    assert "run setup.py plugin --codex-user-hooks again" in check.detail                 # setup's own, by its record



def test_a_declaration_the_person_wrote_with_the_plugins_matcher_is_judged_not_named_unlike(tmp_path):
    """Setup keeps a declaration the person wrote as written, so how its command names the stable hook is theirs."""
    declared = doctor.codex_user_declaration(REPO_HOOKS)
    declared["PreToolUse"][0]["hooks"][0]["command"] = '"${HOME}/.synthesis/v5/bin/synthesis-hook" pre-tool-use'
    home, config = user_level(tmp_path, declared=declared)
    assert doctor.check_codex_trust(REPO_HOOKS, config, PLUGIN_ID, None, home).status == "ok"

@pytest.mark.parametrize("text", ["[a\nx = 1\n", "x = 1\nnot a key\n", 'x = [1,\n2\n', "[a]\nx = 1\n[a]\ny = 2\n", "x =\n",
                                  "[a] y = 1\n"])
def test_the_strict_toml_reader_refuses_a_line_it_cannot_place(text):
    with pytest.raises(ValueError):
        doctor.read_toml(text, strict=True)
    doctor.read_toml(text)                                                            # the doctor's own reading still reads past it


def test_the_strict_toml_reader_reads_a_whole_config_as_the_lenient_one_does():
    text = ('model = "gpt-5" # a comment\nproject_doc_fallback_filenames = ["CLAUDE.md",\n  "AGENTS.md"]\n'
            'notice = { hide = true }\ninstructions = """\n[not a table]\nx = 1\n"""\n\n[features]\nhooks = true\n\n'
            '[hooks.state."synthesis-skills@synthesis-engineering:hooks/hooks.json:stop:0:0"]  # synthesis-setup: x\n'
            'enabled = false  # synthesis-setup: x\n[[mcp]]\nname = "a"\n[[mcp]]\nname = "b"\n'
            "[projects.'/Users/x/work']\ntrust_level = \"trusted\"\n")
    assert doctor.read_toml(text, strict=True) == doctor.read_toml(text)


# ---- review round 1 of 5.21.0: the doctor's codex hook trust line, each finding's case from its probe -------------

def test_calls_stable_hook_takes_the_stable_hook_as_the_program_the_command_runs():
    """R1-2 (p03 K2): a substring test took a log line that only names the hook for a declaration."""
    for command in ('"$HOME/.synthesis/v5/bin/synthesis-hook" pre-tool-use', '"${HOME}/.synthesis/v5/bin/synthesis-hook" pre-tool-use',
                    'exec "$HOME/.synthesis/v5/bin/synthesis-hook" pre-tool-use', "~/.synthesis/v5/bin/synthesis-hook pre-tool-use"):
        assert doctor.calls_stable_hook("PreToolUse", command), command
    for command in ('echo "skipped $HOME/.synthesis/v5/bin/synthesis-hook pre-tool-use" >> /tmp/log',
                    '"$HOME/.synthesis/v5/bin/synthesis-hook" stop', '"$HOME/.synthesis/v5/bin/synthesis-hook pre-tool-use'):
        assert not doctor.calls_stable_hook("PreToolUse", command), command
    commands = [(e, h["command"]) for e, _, h in doctor.hooks_json_entries(REPO_HOOKS)]
    assert doctor.check_hooks_wired("codex", commands).status == "ok"  # the plugin's own start runs it through a wrapper


def test_a_narrower_declaration_of_the_persons_is_named_with_what_mends_it(tmp_path):
    """R1-2 (p03 K1): the advice said to run setup again, which keeps the person's declaration as written."""
    declared = doctor.codex_user_declaration(REPO_HOOKS)
    declared["PreToolUse"] = [{"matcher": "Bash|Write|Edit", "hooks": [
        {"type": "command", "timeout": 5, "command": '"${HOME}/.synthesis/v5/bin/synthesis-hook" pre-tool-use'}]}]
    home, config = user_level(tmp_path, declared=declared)
    detail = doctor.check_codex_trust(REPO_HOOKS, config, PLUGIN_ID, None, home).detail
    assert "edit your own" in detail and "--codex-user-hooks again" not in detail


def test_plugin_copies_setup_switched_off_with_nothing_declared_in_their_place_are_a_fault_of_setup(tmp_path):
    """R1-3 (p05 D2): with hooks.json gone and setup's switches left, no synthesis hook ran, and the doctor called it
    an approval waiting on the person."""
    home = tmp_path / "codex"
    home.mkdir()
    mark = "  # synthesis-setup: codex-user-hooks"
    text = "".join(f'[hooks.state."{key}"]{mark}\nenabled = false{mark}\n' for key in trusted_state())
    (home / "config.toml").write_text(text)
    check = doctor.check_codex_trust(REPO_HOOKS, doctor.read_toml(text), PLUGIN_ID, None, home)
    assert check.status == "fail" and not doctor.waits_on_person(check)
    assert "switched off by setup" in check.detail and "disabled" not in check.detail


@pytest.mark.parametrize("text", ['{"hooks": {"PostToolUse": [{"hooks": [{"type": "http", "url": "https://x"}]}]}}',
                                  '{"hooks": {}, "version": 1}', '{"hooks": {}'])
def test_the_persons_own_unreadable_hooks_file_is_a_warning_of_its_own_while_the_option_is_off(tmp_path, isolated_home, text):
    """R1-8 (p05 D1, p13): the trust line failed over the person's own file, held the release, and the note for session
    starts called all four running hooks not running."""
    home = tmp_path / "codex"
    home.mkdir()
    (home / "hooks.json").write_text(text)
    check = doctor.check_codex_trust(REPO_HOOKS, {"hooks": {"state": trusted_state()}}, PLUGIN_ID, None, home)
    assert check.status == "ok"
    warning = doctor.check_codex_hooks_file(home)
    assert warning.status == "warn" and "hooks.json" in warning.detail
    doctor._note_waits(isolated_home, [check, doctor.Check("ok", "codex plugin", "installed")], time.time())
    assert paths.waits(isolated_home)["codex hook trust"]["waiting"] == []


def test_a_user_level_hook_declared_twice_fails_since_it_runs_twice(tmp_path):
    """R1-9 (p03 K3): setup's Stop and a second of the person's, both approved, read as ok, five hooks for four."""
    declared = doctor.codex_user_declaration(REPO_HOOKS)
    declared["Stop"].append({"hooks": [{"type": "command", "timeout": 5, "command": '"${HOME}/.synthesis/v5/bin/synthesis-hook" stop'}]})
    home, config = user_level(tmp_path, declared=declared)
    check = doctor.check_codex_trust(REPO_HOOKS, config, PLUGIN_ID, None, home)
    assert check.status == "fail" and "Stop runs 2 times" in check.detail and not doctor.waits_on_person(check)


def test_the_toml_reader_splits_lines_at_line_feeds_alone():
    """R1-10 (p04 L3, L3b): splitlines() broke a value at U+2029 and refused a U+2028 in a comment."""
    assert doctor.read_toml('x = """\nfirst second\n"""\n', strict=True)["x"] == "first second\n"
    assert doctor.read_toml('# note more\nmodel = "a b"\r\n', strict=True) == {"model": "a b"}


@pytest.mark.parametrize("text", ['[t]\n"enabled" = true\nenabled = false\n', "[t]\nx = 1\n'x' = 2\n", "a = 1\na.b = 2\n",
                                  '[hooks]\nstate = {}\n[hooks.state."k"]\n', "a = { b = 1 }\na.c = 2\n", "a.b = 1\n[a]\n",
                                  "[a]\nb.c = 1\n[a.b]\n", "[a.b]\nx = 1\n[a]\nb.y = 2\n"])
def test_the_strict_reader_refuses_a_key_set_twice_and_any_table_inside_a_value(text):
    """R1-1: the strict reading setup checks its edit with must refuse what Codex refuses (tomllib agrees on each)."""
    with pytest.raises(ValueError):
        doctor.read_toml(text, strict=True)


def test_the_strict_reader_reads_what_toml_allows_beside_those():
    for text in ('hooks.state."other".enabled = false\n[hooks.state."synth"]\nenabled = false\n',
                 '[hooks.state]\n"other" = { enabled = false }\n[hooks.state."synth"]\nenabled = false\n',
                 "[a.b.c]\n[a]\nb.x = 1\n", "[a]\nb.c = 1\n[a.d]\nx = 1\n", "[a.b]\nx = 1\n[a]\ny = 2\n", "[[m]]\nx = 1\n[[m]]\nx = 2\n"):
        doctor.read_toml(text, strict=True)


@pytest.mark.parametrize("text", ['[hooks]\nstate = { "other@x:hooks/hooks.json:stop:0:0" = { enabled = false } }\n',
                                  "hooks = { state = {} }\n"])
def test_hook_state_held_as_an_inline_table_is_named_not_a_crash(tmp_path, text):
    """R1-16 (p09): the doctor's Codex checks stopped with a traceback on valid TOML."""
    check = doctor.check_codex_trust(REPO_HOOKS, doctor.read_toml(text), PLUGIN_ID, None, tmp_path)
    assert check.status == "fail" and "inline table" in check.detail and not doctor.waits_on_person(check)

def test_codex_hooks_feature():
    assert doctor.check_codex_features({"features": {"hooks": True}}).status == "ok"
    missing = doctor.check_codex_features({"features": {"memories": True}})
    assert missing.status == "warn" and "hooks = true" in missing.detail
    assert doctor.check_codex_features({}).status == "warn"
    assert doctor.check_codex_features({"features": {"hooks": False}}).status == "fail"


def test_codex_instruction_byte_limit():
    assert doctor.check_codex_doc_bytes({}).status == "fail"
    assert doctor.check_codex_doc_bytes({"project_doc_max_bytes": 32768}).status == "fail"
    assert doctor.check_codex_doc_bytes({"project_doc_max_bytes": True}).status == "fail"
    assert doctor.check_codex_doc_bytes({"project_doc_max_bytes": 98304}).status == "ok"


def test_codex_must_write_the_board_and_the_outbox_and_never_the_state_folder(tmp_path):
    """2026-10-30: Codex sessions could not claim or post, because the sandbox could not write the board. The outbox
    is the other folder a sandboxed session writes: without it a Codex session cannot stage a file it attaches."""
    board, state, outbox = tmp_path / "v5" / "board", tmp_path / "v5" / "state", tmp_path / "v5" / "outbox"
    older = lambda *r: {"sandbox_mode": "workspace-write",  # noqa: E731
                        "sandbox_workspace_write": {"writable_roots": "[" + ", ".join(f'"{x}"' for x in r) + "]"}}
    profile = lambda *r: {"default_permissions": "mine", "permissions": {  # noqa: E731  (granted by the profile it extends)
        "mine": {"extends": "base"}, "base": {"extends": ":workspace", "filesystem": {x: "write" for x in r}}}}
    for config in (older, profile):
        both = doctor.check_codex_board(config("/elsewhere", str(board), str(outbox)), board, state, outbox)
        assert both.status == "ok" and doctor._short(board) in both.detail and doctor._short(outbox) in both.detail
        missing = doctor.check_codex_board(config(str(board) + "-old", str(outbox)), board, state, outbox)
        assert missing.status == "fail" and "neither claim files nor post" in missing.detail
        alone = doctor.check_codex_board(config(str(board), str(outbox) + "-old"), board, state, outbox)  # as an earlier setup left it
        assert alone.status == "fail" and doctor._short(outbox) in alone.detail and "cannot stage a file" in alone.detail
        assert "setup for codex again" in alone.detail and "neither claim" not in alone.detail
        exposed = doctor.check_codex_board(config(str(tmp_path / "v5")), board, state, outbox)
        assert exposed.status == "fail" and "approvals and send windows" in exposed.detail
        assert doctor._short(board) in exposed.detail and doctor._short(outbox) in exposed.detail  # what to grant instead
    assert doctor.check_codex_board({}, board, state, outbox).status == "fail"  # the built-in :workspace
    ignored = {"sandbox_workspace_write": older(str(board), str(outbox))["sandbox_workspace_write"]}  # read only with sandbox_mode
    assert doctor.check_codex_board(ignored, board, state, outbox).status == "fail"
    assert doctor.check_codex_board({"sandbox_mode": "danger-full-access"}, board, state, outbox).status == "ok"
    assert doctor.check_codex_board({"default_permissions": ":danger-full-access"}, board, state, outbox).status == "ok"
    assert doctor.toml_strings('[ "a\\"b", \'c\' ]') == ['a"b', "c"] and doctor.toml_strings(None) == []


def test_claude_code_must_keep_transcripts_past_its_30_day_default(tmp_path):
    settings = tmp_path / "settings.json"
    assert doctor.check_claude_retention(settings).status == "fail"
    settings.write_text('{"model": "x"}')
    assert "deletes a transcript idle 30 days" in doctor.check_claude_retention(settings).detail
    settings.write_text('{"cleanupPeriodDays": 30}')
    assert doctor.check_claude_retention(settings).status == "warn"
    settings.write_text('{"cleanupPeriodDays": 3650}')
    assert doctor.check_claude_retention(settings).status == "ok"


def test_board_entries_left_in_the_state_folder_are_named(tmp_path):
    assert doctor.check_board(tmp_path).status == "ok"
    (tmp_path / "state" / "sessions").mkdir(parents=True)
    left = doctor.check_board(tmp_path)
    assert left.status == "warn" and left.detail.startswith("sessions still in")


CODEX_CONFIG = '''\
model = "gpt-6" # trailing comment
project_doc_fallback_filenames = ["CLAUDE.md"]
project_doc_max_bytes = 98_304
notify = [
  "python3", # a comment with ] in it
  "/tmp/notify.py",
]
banner = """two
lines with [brackets] and = signs"""

[features]
memories = true
hooks = true

[plugins."synthesis-skills@synthesis-engineering"]
enabled = true

[hooks.state."synthesis-skills@synthesis-engineering:hooks/hooks.json:pre_tool_use:0:0"]
trusted_hash = "sha256:abc"

[hooks.state.'literal:key:0:1']
enabled = false

[[profiles.fast]]
model = "x"

[shell_environment_policy.set]
WITH_HASH = "a#b=c\\"d"
'''


def test_toml_subset_reads_what_doctor_needs():
    config = doctor.read_toml(CODEX_CONFIG)
    assert config["features"] == {"memories": True, "hooks": True}
    assert config["project_doc_max_bytes"] == 98304
    assert config["model"] == "gpt-6"
    assert config["plugins"][PLUGIN_ID]["enabled"] is True
    assert config["hooks"]["state"][f"{PLUGIN_ID}:hooks/hooks.json:pre_tool_use:0:0"]["trusted_hash"] == "sha256:abc"
    assert config["hooks"]["state"]["literal:key:0:1"]["enabled"] is False
    assert config["shell_environment_policy"]["set"]["WITH_HASH"] == 'a#b=c"d'
    assert "model" not in config.get("profiles", {})  # array-of-tables entries stay out


def test_toml_subset_agrees_with_tomllib_on_scalars():
    tomllib = pytest.importorskip("tomllib")
    reference, mine = tomllib.loads(CODEX_CONFIG), doctor.read_toml(CODEX_CONFIG)

    def scalars(d, prefix=()):
        for k, v in d.items():
            if isinstance(v, dict):
                yield from scalars(v, prefix + (k,))
            elif isinstance(v, (bool, int, str)):
                yield prefix + (k,), v

    expected = {k: v for k, v in scalars(reference) if k[0] != "profiles"}
    assert {k: v for k, v in scalars(mine) if k in expected} == expected


# ---- Muse ---------------------------------------------------------------------

def muse_inspect(plugin: Path, status="trusted_enabled", **record):
    """`muse plugins inspect --json` for a plugin copy, in the shape Muse 1.4.3 prints."""
    hooks = [{**h, "source_path": str(plugin / h["command"][1]), "source_relative_path": h["command"][1]}
             for h in MUSE_MANIFEST["capabilities"]["hooks"]]
    return {
        "record": {"id": "synthesis-skills", "version": "5.0.0", "enabled": True, "cache_path": str(plugin), **record},
        "valid": True, "active": True, "diagnostics": [],
        "plugin": {"id": "synthesis-skills", "capabilities": {"hooks": hooks}},
        "runtime_capabilities": [{"candidate": {"kind": "hook", "plugin_id": "synthesis-skills",
                                                "capability_id": h["id"]}, "status": status} for h in hooks],
    }


def test_muse_hooks_approved(tmp_path):
    check = doctor.check_muse_approval(muse_inspect(tmp_path))
    assert check.status == "ok" and "all 4" in check.detail


def test_muse_hooks_awaiting_review_fail(tmp_path):
    check = doctor.check_muse_approval(muse_inspect(tmp_path, status="review_needed"))
    assert check.status == "fail" and "muse plugins approve synthesis-skills" in check.detail
    assert doctor.check_muse_approval({"runtime_capabilities": []}).status == "fail"


def test_unreadable_muse_trust_state_is_cannot_tell_not_a_failed_approval(tmp_path):
    """SYN-03, 2026-10-07: inside Codex's sandbox Muse listed the four hooks but no trust state, and the
    doctor said the plugin registers no hooks; run on the host, all four were approved."""
    unreadable = {**muse_inspect(tmp_path), "runtime_capabilities": []}
    check = doctor.check_muse_approval(unreadable)
    assert check.status == "warn" and "cannot tell" in check.detail and "4 hooks" in check.detail


def test_muse_manifest_is_wired_to_the_stable_hook(tmp_path):
    plugin = plugin_copy(tmp_path / "plugin")
    assert doctor.check_hooks_wired("muse", doctor.muse_hook_commands(muse_inspect(plugin))).status == "ok"


def test_muse_manifest_registers_the_same_four_events_as_files():
    hooks = MUSE_MANIFEST["capabilities"]["hooks"]
    assert sorted(h["event"] for h in hooks) == sorted(doctor.EVENTS)
    for hook in hooks:
        assert "matcher" not in hook  # Muse rejects a matcher key in native manifests (unsupported-field)
        assert hook["command"][0] == "/bin/sh" and len(hook["command"]) == 2  # inline `sh -c` fails validation
        script = (ROOT / hook["command"][1]).read_text()
        assert f'"{doctor.STABLE_HOOK}" {doctor.EVENTS[hook["event"]]}' in script.replace('"$h"', f'"{doctor.STABLE_HOOK}"')
    assert len({h["command"][1] for h in hooks}) == len(hooks)  # Muse forbids two hooks sharing a script


def _muse_env(home: Path, **extra):
    env = {k: v for k, v in os.environ.items() if k not in ("SYNTHESIS_HOME", "PYTHONDONTWRITEBYTECODE")}
    return {**env, "HOME": str(home), **extra}


@pytest.mark.parametrize("with_root_variable", [True, False])
def test_muse_session_start_bootstraps_without_writing_into_the_bundle(tmp_path, with_root_variable):
    plugin = plugin_copy(tmp_path / "muse-cache" / "package")
    before = sorted(str(p.relative_to(plugin)) for p in plugin.rglob("*"))
    home = tmp_path / "fresh-home"
    home.mkdir()
    extra = {"MUSE_PLUGIN_ROOT": str(plugin)} if with_root_variable else {}
    out = subprocess.run(["/bin/sh", str(plugin / ".muse-plugin" / "hooks" / "session-start.sh")],
                         input=json.dumps({"session_id": "muse-1", "source": "startup", "cwd": str(tmp_path)}),
                         capture_output=True, text=True, env=_muse_env(home, **extra), cwd=str(tmp_path))
    assert out.returncode == 0, out.stderr
    assert (home / ".synthesis" / "v5" / "bin" / "synthesis-hook").is_file()
    assert (home / ".synthesis" / "v5" / "board" / "sessions" / "muse-1.json").is_file()
    assert sorted(str(p.relative_to(plugin)) for p in plugin.rglob("*")) == before  # Muse verifies its bundle


def test_muse_pre_tool_use_reaches_the_guard(tmp_path):
    plugin = plugin_copy(tmp_path / "package")
    home = tmp_path / "home"
    home.mkdir()
    env = _muse_env(home, MUSE_PLUGIN_ROOT=str(plugin))
    subprocess.run(["/bin/sh", str(plugin / ".muse-plugin" / "hooks" / "session-start.sh")], input="{}",
                   capture_output=True, text=True, env=env, check=True)
    out = subprocess.run(["/bin/sh", str(plugin / ".muse-plugin" / "hooks" / "pre-tool-use.sh")],
                         input=json.dumps({"tool_name": "Bash", "tool_input": {"command": "rm -rf ~"}}),
                         capture_output=True, text=True, env=env)
    assert json.loads(out.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


# ---- git ----------------------------------------------------------------------

def test_git_hooks_path_is_report_only(tmp_path):
    expected = tmp_path / "git-hooks"
    assert doctor.check_git_hooks_path(str(expected), expected).status == "ok"
    assert doctor.check_git_hooks_path("", expected).status == "info"
    other = doctor.check_git_hooks_path("~/.synthesis/git-hooks", expected)
    assert other.status == "info" and "not the v5 folder" in other.detail


# ---- end to end, with fake harness CLIs ---------------------------------------

def fake_cli(bin_dir: Path, name: str, payload, skills=None, version="2.1.316 (Claude Code)") -> None:
    """A harness CLI that prints its listing and, asked with --version, its version; with `skills`, it also answers
    app-server skills/list."""
    data = bin_dir / f"{name}.json"
    data.write_text(json.dumps(payload))
    script = bin_dir / name
    answer = json.dumps({"data": [{"skills": skills or [], "errors": []}]})
    script.write_text(f"""#!{sys.executable}
import json, sys
if sys.argv[1:2] == ["app-server"]:
    for line in sys.stdin:
        message = json.loads(line)
        if message.get("id") == 0:
            print(json.dumps({{"id": 0, "result": {{}}}}), flush=True)
        elif message.get("id") == 1:
            print(json.dumps({{"id": 1, "result": json.loads({answer!r})}}), flush=True)
            break
elif sys.argv[1:2] == ["--version"]:
    print({version!r})
else:
    sys.stdout.write(open({str(data)!r}).read())
""")
    script.chmod(0o755)


@pytest.fixture
def machine(tmp_path, monkeypatch):
    """A temporary HOME with the v5 runtime and all three harnesses holding the same plugin bytes."""
    home = tmp_path / "home"
    synthesis_home = home / ".synthesis" / "v5"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SYNTHESIS_HOME", str(synthesis_home))
    monkeypatch.delenv("CODEX_HOME", raising=False)
    for key in ("XDG_CONFIG_HOME", "XDG_STATE_HOME"):  # where Linux keeps a connector's unit and PID file: never this machine's
        monkeypatch.delenv(key, raising=False)
    plugin = plugin_copy(tmp_path / "source")  # one snapshot, so every harness holds identical bytes
    install.install(plugin)
    claude_dir = plugin_copy(home / ".claude" / "plugins" / "cache" / "synthesis-engineering" / "synthesis-skills" / "5.0.0", plugin)
    codex_dir = plugin_copy(home / ".codex" / "plugins" / "cache" / "synthesis-engineering" / "synthesis-skills" / "5.0.0", plugin)
    muse_dir = plugin_copy(home / ".local" / "share" / "muse" / "plugins" / "cache" / "local" / "synthesis-skills" / "abc" / "package", plugin)
    state = "".join(f'[hooks.state."{k}"]\ntrusted_hash = "{v["trusted_hash"]}"\n\n' for k, v in trusted_state().items())
    (home / ".codex" / "config.toml").write_text(
        f"project_doc_max_bytes = 98304\ndefault_permissions = \"synthesis\"\n\n[features]\nhooks = true\n\n"
        f"[permissions.synthesis]\nextends = \":workspace\"\n[permissions.synthesis.filesystem]\n"
        f"\"{synthesis_home / 'board'}\" = \"write\"\n\"{synthesis_home / 'outbox'}\" = \"write\"\n\n{state}")
    claude_settings = Path(os.environ["CLAUDE_CONFIG_DIR"]) / "settings.json"
    claude_settings.parent.mkdir(parents=True, exist_ok=True)
    claude_settings.write_text('{"cleanupPeriodDays": 3650}')
    fakebin = tmp_path / "fakebin"
    fakebin.mkdir()
    fake_cli(fakebin, "claude", [{"id": PLUGIN_ID, "version": "5.0.0", "enabled": True, "installPath": str(claude_dir)}])
    skills = [{"name": f"synthesis-skills:{p.parent.name}", "description": "x", "enabled": True, "path": str(p)}
              for p in sorted(codex_dir.glob("skills/*/SKILL.md"))]
    fake_cli(fakebin, "codex", {"installed": [{"pluginId": PLUGIN_ID, "name": "synthesis-skills", "version": "5.0.0",
                                               "marketplaceName": "synthesis-engineering", "enabled": True}]}, skills)
    fake_cli(fakebin, "muse", muse_inspect(muse_dir))
    monkeypatch.setenv("PATH", os.pathsep.join([str(fakebin), os.path.dirname(sys.executable), "/usr/bin", "/bin"]))
    monkeypatch.setattr(doctor, "KNOWN_LOCATIONS", {h: () for h in doctor.HARNESSES})  # never this Mac's real CLIs
    # On a busy machine the fake Codex once took over the probe's two seconds to say its version, and the test that
    # counted the doctor's lines failed (2026-11-13). The tests of the probe set their own limit.
    monkeypatch.setattr(doctor, "PROBE_TIMEOUT", 30)
    gitconfig = Path(os.environ["GIT_CONFIG_GLOBAL"])
    gitconfig.write_text(gitconfig.read_text() + f"[core]\n\thooksPath = {synthesis_home / 'git-hooks'}\n")
    return home, fakebin, muse_dir


APPLE_CACHE = ("Library", "Caches", "com.apple.python")


def snapshot(root: Path) -> dict:
    """Every path under root with its size and time, apart from the runtime's own state and the bytecode cache
    Apple's Python keeps under the home folder. A temporary home starts with no such cache, so any Python started
    there fills one (70 entries in CI on 2026-11-11); that is the interpreter's doing, not the code's."""
    return {str(p): (p.stat().st_size, p.stat().st_mtime_ns) for p in root.rglob("*")
            if ".synthesis" not in p.parts and (parts := p.relative_to(root).parts)[:3] != APPLE_CACHE
            and parts not in (APPLE_CACHE[:1], APPLE_CACHE[:2])}


def test_the_snapshot_leaves_out_apples_bytecode_cache_and_nothing_else(tmp_path):
    (tmp_path / ".claude").mkdir()
    before = snapshot(tmp_path)
    cache = tmp_path / "Library" / "Caches" / "com.apple.python" / "Applications" / "Xcode.app"
    cache.mkdir(parents=True)
    (cache / "os.cpython-39.pyc").write_bytes(b"x")
    assert snapshot(tmp_path) == before
    (tmp_path / "Library" / "Caches" / "other.txt").write_text("x")
    (tmp_path / ".claude" / "settings.json").write_text("{}")
    assert sorted(set(snapshot(tmp_path)) - set(before)) == [str(tmp_path / ".claude" / "settings.json"),
                                                            str(tmp_path / "Library" / "Caches" / "other.txt")]


def test_doctor_reports_a_healthy_machine_and_writes_no_harness_state(machine, capsys):
    home, _, _ = machine
    before = snapshot(home)
    assert doctor.main([]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("synthesis doctor: healthy (")
    names = {line.split()[1] for line in lines[1:]}
    assert {"runtime", "claude", "codex", "muse", "git"} <= names
    assert not any(line.split()[0] == "fail" for line in lines[1:])
    assert any(line.split()[:4] == ["ok", "codex", "skill", "catalog"] for line in lines[1:])
    assert any(line.split()[:4] == ["ok", "claude", "fail", "closed"] for line in lines[1:])
    assert snapshot(home) == before


# --- approvals that wait ----------------------------------------------------------------------------------------------
# A harness whose hooks wait for the person's approval runs none of them: no send guard, no deploy guard, no reply
# check. Codex asks again after every release, and on 2026-11-13 there were six. The doctor says so on one line of
# forty, which reaches no one who does not read it. So a run of the doctor writes down which approvals wait, and
# two readers show it: a session's start in a harness that does run its hooks, and the weekday evening job.

def _waiting(home):
    return home / ".synthesis" / "v5" / "state" / "harness-approvals.json"


def _seen(home):
    return json.loads(_waiting(home).read_text())["seen"]


EVENTS = ["session_start", "user_prompt_submit", "pre_tool_use", "stop"]


def _note(home, version=None, ago=3600.0, struck=None, **waiting):
    """The note as a run of the doctor `ago` seconds back would have left it: `codex=[...]`, `muse=[...]` are the
    hook events that waited in each; `struck` is when a hook that ran since struck its own."""
    names = {"codex": "codex hook trust", "muse": "muse hook approval"}
    _waiting(home).parent.mkdir(parents=True, exist_ok=True)
    _waiting(home).write_text(json.dumps({"seen": {names[k]: {
        "at": time.time() - ago, "version": version or synthesis.__version__, "waiting": v, "struck": struck or {},
        "said": "needs /hooks approval"} for k, v in waiting.items()}}))


def test_a_run_of_the_doctor_writes_down_which_hooks_wait_in_each_harness(machine, capsys):
    home, _, _ = machine
    assert doctor.main([]) == 0
    seen = _seen(home)
    assert {name: entry["waiting"] for name, entry in seen.items()} == {"codex hook trust": [], "muse hook approval": []}
    assert all(abs(entry["at"] - time.time()) < 120 and entry["version"] == synthesis.__version__ for entry in seen.values())
    config = home / ".codex" / "config.toml"
    config.write_text(config.read_text().replace(f'[hooks.state."{PLUGIN_ID}:hooks/hooks.json:pre_tool_use:0:0"]', "[unrelated]"))
    assert doctor.main([]) == 1
    assert _seen(home)["codex hook trust"]["waiting"] == ["pre_tool_use"]        # the hook its line names, not all four
    assert _seen(home)["muse hook approval"]["waiting"] == []


def test_the_hooks_that_wait_are_the_ones_the_checks_own_line_names(machine):
    """Review of 5.14.0, finding 1: trust is kept for each hook, and the note held one word for a harness. A line
    that names no hook (no hooks file, no fingerprint) is read as all four."""
    home = machine[0] / ".synthesis" / "v5"
    stale = ("needs /hooks approval: session_start:0:0, user_prompt_submit:0:0, pre_tool_use:0:0, stop:0:0 approved "
             "before the plugin last changed (Codex ties an approval to the plugin's files), so Codex runs none of them")
    for name, detail, events in (
            ("codex hook trust", stale, EVENTS),
            ("codex hook trust", "needs /hooks approval: stop:0:0 disabled, session_start:0:0 untrusted", ["session_start", "stop"]),
            ("codex hook trust", "the installed plugin has no hooks/hooks.json", EVENTS),
            ("muse hook approval", "run `muse plugins approve synthesis-skills`: synthesis-pre-tool-use (untrusted)", ["pre_tool_use"]),
            ("muse hook approval", "the installed plugin registers no hooks", EVENTS)):
        doctor._note_waits(home, [doctor.Check("fail", name, detail)], time.time())
        assert paths.waits(home)[name]["waiting"] == events, detail
        doctor._note_waits(home, [doctor.Check("ok", name, "all 4 hooks approved and enabled")], time.time())
        assert paths.waits(home)[name]["waiting"] == []


def test_a_harness_the_run_could_not_look_at_keeps_its_own_date_and_says_nothing_after_a_day(machine):
    """Review of 5.14.0, findings 3 and 7: an entry the run did not look at was carried into a note dated now, so
    it never aged (Codex removed from the machine waited for ever, with a banner every evening), and a look that
    could not tell (Muse's `warn`) was written down as nothing waiting."""
    home = machine[0] / ".synthesis" / "v5"
    _note(machine[0], ago=3600.0, codex=EVENTS, muse=["stop"])
    before = _seen(machine[0])
    doctor._note_waits(home, [doctor.Check("warn", "muse hook approval", "cannot tell whether Muse approved the 4 hooks")], time.time())
    assert _seen(machine[0]) == before                                           # neither entry changed, neither re-dated
    assert {name: entry["waiting"] for name, entry in paths.waits(home).items()} == {
        "codex hook trust": EVENTS, "muse hook approval": ["stop"]}
    _note(machine[0], ago=2 * 86400.0, codex=EVENTS)
    doctor._note_waits(home, [], time.time())
    assert paths.waits(home) == {}                                               # two days with no look: it says nothing


def test_a_hook_that_ran_while_the_doctor_was_looking_stays_struck_and_what_newly_waits_is_still_written(machine):
    """A run of the doctor reads a harness's trust, and seconds later writes what it read. A hook that ran in
    between is the later sight of its own event, and of no other (the second review: the first rule kept the whole
    older list, so a hook the run found newly waiting was dropped with the one that had been struck)."""
    home, now = machine[0] / ".synthesis" / "v5", time.time()
    found = doctor.Check("fail", "codex hook trust",
                         "needs /hooks approval: pre_tool_use:0:0 untrusted, stop:0:0 untrusted, session_start:0:0 disabled")
    _note(machine[0], ago=60, struck={"pre_tool_use": now}, codex=["stop"])      # the guard's hook ran a moment ago
    doctor._note_waits(home, [found], now - 30)                                  # a look that began before it ran
    assert paths.waits(home)["codex hook trust"]["waiting"] == ["session_start", "stop"]
    _note(machine[0], ago=60, struck={"pre_tool_use": now}, codex=["stop"])
    doctor._note_waits(home, [found], time.time())                               # a look that began after it is the later sight
    assert paths.waits(home)["codex hook trust"]["waiting"] == ["session_start", "pre_tool_use", "stop"]
    _note(machine[0], ago=60, struck={"pre_tool_use": now + 3600}, codex=["stop"])   # a strike dated ahead of the clock is no sight
    doctor._note_waits(home, [found], now - 30)
    assert paths.waits(home)["codex hook trust"]["waiting"] == ["session_start", "pre_tool_use", "stop"]


def test_what_was_seen_under_another_release_is_news_until_this_release_looks(machine):
    """The second review, finding 2: an entry of another release dropped out after a day like any other, so the
    word that nothing had looked since the release changed went silent on the second day. It is kept at any age
    until a run of this release has looked: every such run writes what it saw in that entry's place (the third
    review, findings 1 and 8, in the tests below)."""
    home = machine[0] / ".synthesis" / "v5"
    _note(machine[0], version="5.0.0", ago=3 * 86400.0, codex=EVENTS, muse=[])
    assert {entry["version"] for entry in paths.waits(home).values()} == {"5.0.0"} and len(paths.waits(home)) == 2
    doctor._note_waits(home, [doctor.Check("ok", "codex hook trust", "all 4 synthesis hooks trusted")], time.time())
    assert paths.waits(home)["codex hook trust"]["version"] == synthesis.__version__


# --- the third review of 5.14.0 ---------------------------------------------------------------------------------------

CANNOT = "cannot tell: `codex plugin list` did not answer in 45 s; run the doctor again"
UNREAD = ("cannot tell whether Muse approved the 4 hooks: it reported no trust state, which happens when its state "
          "cannot be read from here (in a sandbox, for example)")


def test_a_look_that_could_not_tell_is_written_down_as_that_in_place_of_another_releases_entry(machine):
    """The third review, finding 1: Codex's listing did not answer, or Muse's trust could not be read, and what
    another release saw stayed for ever under a sentence that said the doctor checks it. The run writes that it
    could not tell, with the harness's own line; a later run that still cannot tell dates it again and keeps what
    a hook has struck since, the only sight there is."""
    home, now = machine[0] / ".synthesis" / "v5", time.time()
    _note(machine[0], version="5.0.0", ago=30 * 86400.0, codex=[], muse=[])
    blind = [doctor.Check("warn", "codex plugin", CANNOT), doctor.Check("ok", "muse plugin", "synthesis-skills 9 installed and enabled"),
             doctor.Check("warn", "muse hook approval", UNREAD)]
    doctor._note_waits(home, blind, now - 60)
    seen = paths.waits(home)
    assert {name: (entry["version"], entry["untold"], entry["waiting"]) for name, entry in seen.items()} == {
        "codex hook trust": (synthesis.__version__, True, EVENTS), "muse hook approval": (synthesis.__version__, True, EVENTS)}
    assert seen["codex hook trust"]["said"] == CANNOT and seen["muse hook approval"]["said"] == UNREAD
    paths.note_wait("codex hook trust", lambda old: {**old, "waiting": ["stop"], "struck": {"pre_tool_use": now - 45}}, home)
    doctor._note_waits(home, blind, now - 30)
    again = paths.waits(home)["codex hook trust"]
    assert again["at"] == now - 30 and again["waiting"] == ["stop"] and again["untold"] is True
    doctor._note_waits(home, [doctor.Check("ok", "codex hook trust", "all 4 synthesis hooks trusted")], time.time())
    told = paths.waits(home)["codex hook trust"]
    assert told["untold"] is False and told["waiting"] == [] and told["said"] == ""          # a look that can tell replaces it


def test_what_this_release_saw_stands_while_a_later_look_cannot_tell(machine):
    """A look from inside a sandbox cannot read Muse's trust: it must not turn what an earlier look saw today into
    a word that nothing is known."""
    home = machine[0] / ".synthesis" / "v5"
    _note(machine[0], ago=3600.0, codex=[], muse=["stop"])
    before = _seen(machine[0])
    doctor._note_waits(home, [doctor.Check("warn", "codex plugin", CANNOT), doctor.Check("warn", "muse hook approval", UNREAD)], time.time())
    assert _seen(machine[0]) == before


def test_a_harness_with_no_plugin_in_it_has_no_approval_to_wait_for(machine):
    """The third review, finding 1: the plugin was removed from a harness, and the entry another release wrote of it
    stayed. The harness's own line says the plugin is not there, in the doctor's one sentence for it; a line that
    fails in other words is a look that could not tell (5.15.0's third review, finding 5)."""
    home = machine[0] / ".synthesis" / "v5"
    gone = [doctor.Check("fail", "codex plugin", "synthesis-skills is not installed"),
            doctor.Check("fail", "muse plugin", "synthesis-skills is not installed")]
    for version in ("5.0.0", None):
        _note(machine[0], version=version, ago=600.0, codex=EVENTS, muse=EVENTS)
        doctor._note_waits(home, gone, time.time())
        assert paths.waits(home) == {} and _seen(machine[0]) == {}, version
    _note(machine[0], version="5.0.0", ago=600.0, codex=EVENTS)
    doctor._note_waits(home, [doctor.Check("fail", "codex plugin", "could not run codex: it is not installed")], time.time())
    assert paths.waits(home)["codex hook trust"]["untold"] is True


def test_a_harness_the_run_did_not_find_is_told_of_for_a_day_and_no_longer(machine):
    """The third review, finding 8: a run that found no trace of a harness dropped what another release saw of it, so
    a Codex installed where the doctor does not look went unmentioned. The run says that it did not find it; a
    later run that still does not leaves that entry its own date, so it says nothing once it is a day old."""
    home, now = machine[0] / ".synthesis" / "v5", time.time()
    _note(machine[0], version="5.0.0", ago=30 * 86400.0, codex=["stop"])
    doctor._note_waits(home, [], now - 60)
    first = _seen(machine[0])["codex hook trust"]
    assert first["version"] == synthesis.__version__ and first["untold"] is True and first["waiting"] == EVENTS
    assert "did not find Codex" in first["said"]
    doctor._note_waits(home, [], now)
    assert _seen(machine[0])["codex hook trust"] == first                        # not dated again
    _waiting(machine[0]).write_text(json.dumps({"seen": {"codex hook trust": {**first, "at": now - 2 * 86400}}}))
    doctor._note_waits(home, [], now)
    assert paths.waits(home) == {}                                               # a day on it says nothing, and nothing brings it back


def test_a_strike_made_while_the_doctor_waits_for_the_note_stays_struck(machine, monkeypatch):
    """The third review, finding 2: the doctor read the clock before it took the note's lock, so a hook that struck
    its event while the doctor waited for the lock was written back as waiting."""
    home = machine[0] / ".synthesis" / "v5"
    found = doctor.Check("fail", "codex hook trust", "needs /hooks approval: pre_tool_use:0:0 untrusted, stop:0:0 untrusted")
    _note(machine[0], ago=60, codex=["pre_tool_use", "stop"])
    real = paths.note_wait

    def after_a_hook(name, change, *rest, **more):  # the doctor comes to the lock just after a hook has struck under it
        if name == "codex hook trust":
            time.sleep(0.02)
            real(name, lambda old: {**old, "waiting": ["stop"], "struck": {"pre_tool_use": time.time()}}, home)
        return real(name, change, *rest, **more)
    monkeypatch.setattr(paths, "note_wait", after_a_hook)
    doctor._note_waits(home, [found], time.time() - 30)
    assert paths.waits(home)["codex hook trust"]["waiting"] == ["stop"]


def _held(home, name="codex hook trust"):
    """A writer inside the note's lock, and the word that lets it out."""
    import threading
    inside, leave = threading.Event(), threading.Event()

    def hold(old):
        inside.set()
        leave.wait(10)
    holder = threading.Thread(target=paths.note_wait, args=(name, hold, home))
    holder.start()
    assert inside.wait(10)
    return holder, leave


def test_two_writers_of_the_note_take_turns_and_the_second_reads_what_the_first_wrote(machine):
    """The third review, finding 3: the test of the locked change would have passed with the lock taken out."""
    import threading
    home = machine[0] / ".synthesis" / "v5"
    _note(machine[0], codex=EVENTS)
    inside, leave, order = threading.Event(), threading.Event(), []

    def first(old):
        inside.set()
        leave.wait(10)
        order.append("first")
        return {**old, "waiting": ["stop"]}

    def second(old):
        order.append(("second", old["waiting"]))
    one = threading.Thread(target=paths.note_wait, args=("codex hook trust", first, home))
    two = threading.Thread(target=paths.note_wait, args=("codex hook trust", second, home))
    one.start()
    assert inside.wait(10)
    two.start()
    two.join(0.3)
    assert two.is_alive() and order == []                                        # the second waits its turn
    leave.set()
    one.join(10)
    two.join(10)
    assert order == ["first", ("second", ["stop"])]


def test_a_writer_that_will_not_wait_leaves_a_held_note_alone(machine):
    """The third review, finding 4: a hook with something to strike waited for whoever held the note's lock, for as
    long as that took. Asked not to wait, the change is not made and not called."""
    home = machine[0] / ".synthesis" / "v5"
    _note(machine[0], codex=EVENTS)
    holder, leave = _held(home)
    called, began = [], time.monotonic()
    paths.note_wait("codex hook trust", lambda old: called.append(old) or {**old, "waiting": []}, home, wait=False)
    assert time.monotonic() - began < 1 and called == []
    leave.set()
    holder.join(10)
    assert paths.waits(home)["codex hook trust"]["waiting"] == EVENTS
    paths.note_wait("codex hook trust", lambda old: {**old, "waiting": []}, home, wait=False)
    assert paths.waits(home)["codex hook trust"]["waiting"] == []                # free, the change is made


def test_a_state_file_that_cannot_be_replaced_leaves_nothing_half_written_beside_it(tmp_path):
    """The third review, finding 6: each failed write left its temporary file in the state folder."""
    target = tmp_path / "state" / "harness-approvals.json"
    target.mkdir(parents=True)                                                   # a folder where the file should be
    with pytest.raises(OSError):
        paths.write_json(target, {"seen": {}})
    assert [path.name for path in target.parent.iterdir()] == [target.name]


def test_a_muse_with_no_plugin_is_known_by_muses_own_code_and_not_by_its_words(machine, capsys):
    """The third review of 5.15.0, finding 5: the note took "is not installed" at the end of Muse's own sentence for
    a plugin that is not there, so any other wording was a look that could not tell, said again every day."""
    home, fakebin, _ = machine
    _note(home, version="5.0.0", ago=600.0, muse=EVENTS)
    fake_cli(fakebin, "muse", {"error": {"code": "unknown-plugin", "message": "No plugin by that name is in this Muse."}})
    capsys.readouterr()
    doctor.main([])
    line = next(line for line in capsys.readouterr().out.splitlines() if line.split()[1:3] == ["muse", "plugin"])
    assert line.split()[0] == "fail" and line.rstrip().endswith("synthesis-skills is not installed")
    assert "muse hook approval" not in _seen(home)
    _note(home, version="5.0.0", ago=600.0, muse=EVENTS)
    fake_cli(fakebin, "muse", {"error": {"code": "state-locked", "message": "Muse's state is not installed where it was."}})
    doctor.main([])
    entry = _seen(home)["muse hook approval"]
    assert entry["untold"] is True and entry["said"] == "Muse's state is not installed where it was."   # another fault: it could not tell


def test_two_threads_of_one_process_each_write_a_state_file_whole(tmp_path):
    """The third review of 5.15.0, finding 8: both took one temporary name, so one failed as the other replaced the
    file, and a reader could find half of it."""
    import threading
    target, torn, failed, stop = tmp_path / "state" / "note.json", [], [], threading.Event()

    def write(n):
        while not stop.is_set():
            try:
                paths.write_json(target, {"writer": n, "fill": "x" * 4000})
            except OSError as exc:
                failed.append(type(exc).__name__)

    def read():
        while not stop.is_set():
            try:
                text = target.read_text(encoding="utf-8")
            except OSError:
                continue
            try:
                json.loads(text)
            except ValueError:
                torn.append(len(text))
    threads = [threading.Thread(target=write, args=(n,)) for n in (1, 2)] + [threading.Thread(target=read)]
    for thread in threads:
        thread.start()
    time.sleep(0.6)
    stop.set()
    for thread in threads:
        thread.join(10)
    assert failed == [] and torn == []
    assert [path.name for path in target.parent.iterdir()] == [target.name]


def test_a_guard_the_doctor_could_not_tell_of_is_counted_as_not_confirmed(machine, capsys):
    home = machine[0]
    _note(home, codex=EVENTS, muse=[])
    seen = _seen(home)
    seen["codex hook trust"]["untold"] = True
    _waiting(home).write_text(json.dumps({"seen": seen}))
    capsys.readouterr()
    assert doctor.main(["--waiting"]) == 0
    assert capsys.readouterr().out.splitlines() == ["1", "codex hook trust"]


def test_one_entry_is_changed_from_what_the_file_holds_at_that_moment(machine):
    """The second review, finding 4: a hook read the note, the doctor wrote it, and the hook wrote back what it had
    read less one event. A change is now made from the entry as it is read under the note's lock."""
    home = machine[0] / ".synthesis" / "v5"
    _note(machine[0], codex=EVENTS, muse=["stop"])
    seen = []
    paths.note_wait("codex hook trust", lambda old: seen.append(old["waiting"]) or {**old, "waiting": ["stop"]}, home)
    assert seen == [EVENTS] and paths.waits(home)["codex hook trust"]["waiting"] == ["stop"]
    assert paths.waits(home)["muse hook approval"]["waiting"] == ["stop"]
    before = _waiting(machine[0]).read_bytes()
    paths.note_wait("codex hook trust", lambda old: None, home)                  # no change is no write
    assert _waiting(machine[0]).read_bytes() == before


def test_what_waits_is_read_back_without_a_check_and_without_a_write(machine, capsys):
    home, fakebin, _ = machine
    capsys.readouterr()

    def said():
        assert doctor.main(["--waiting"]) == 0
        return capsys.readouterr().out.splitlines()

    assert said() == ["unknown"]                                                 # no run of the doctor has written it down
    _note(home, codex=EVENTS, muse=["pre_tool_use"])
    for name in ("claude", "codex", "muse"):                                     # it asks no harness anything
        (fakebin / name).write_text("#!/bin/sh\nexit 9\n")
    before = _waiting(home).read_bytes()
    out = said()
    assert out[0] == "2" and "codex hook trust" in out[1] and "muse hook approval" in out[1] and len(out) == 2
    assert _waiting(home).read_bytes() == before
    _note(home, codex=["stop"], muse=[])
    assert said() == ["0"]              # a hook that is no guard waits: the doctor's own line says so; and no second line
    _note(home, codex=EVENTS, muse=[], version="5.0.0")
    out = said()                        # seen under another release: what a harness asks again after one is not known
    assert out[0] == "unchecked" and "codex hook trust" in out[1] and "muse hook approval" in out[1]
    _note(home, ago=3 * 86400, codex=EVENTS)
    assert said() == ["unknown"]                                                 # three days old says nothing of today
    _note(home, version="5.0.0", ago=3 * 86400, codex=[])
    assert said()[0] == "unchecked"                                              # but another release's is news at any age
    now, version = time.time(), synthesis.__version__
    for text in ("{not json", json.dumps({"seen": ["codex hook trust"]}), json.dumps({"at": now, "waiting": ["codex hook trust"]}),
                 json.dumps({"seen": {"codex hook trust": {"at": int("9" * 400), "version": version, "waiting": ["pre_tool_use"]}}}),
                 json.dumps({"seen": {"codex hook trust": {"at": now + 3600, "version": version, "waiting": ["pre_tool_use"]}}}),
                 json.dumps({"seen": {"codex hook trust": {"at": now, "version": version, "waiting": "pre_tool_use"}}}),
                 json.dumps({"seen": {"a name of another release": {"at": now, "version": version, "waiting": ["pre_tool_use"]}}})):
        _waiting(home).write_text(text)
        assert said() == ["unknown"], text


def test_the_doctor_says_where_the_days_prompt_check_is_on(machine, capsys):
    """The day's prompt check is what asks whether each thing the principal typed reached a record, and it is a
    setting of each workspace. Measured on 2026-11-13: it was on for one workspace of three, and in thirty days 8 of
    267 session entries cited a record. The line says where it is on and where nothing asks."""
    cfg = {"workspaces": {"alpha": {"prompt_reconcile": {"records": ["~/kb/projects"], "from": "2026-11-14"}}, "beta": {},
                          "gamma": {"prompt_reconcile": False}, "delta": {"prompt_reconcile": {"records": ["~/kb"]}}}}
    check = doctor.check_prompt_check(cfg)
    assert (check.status, check.name) == ("info", "prompt check")
    assert check.detail.startswith("on for alpha (from 2026-11-14), delta; off for beta, gamma")
    assert doctor.check_prompt_check({"workspaces": {}}) is None
    assert doctor.check_prompt_check({"workspaces": {"alpha": {"prompt_reconcile": {"records": ["/x"]}}}}).detail == "on for alpha"
    assert doctor.check_prompt_check({"workspaces": {"alpha": {}}}).detail.startswith("on for no workspace; off for alpha")
    unread = doctor.check_prompt_check(None, "not JSON")
    assert unread.status == "warn" and "cannot tell" in unread.detail and "not JSON" in unread.detail
    home, _, _ = machine
    rituals = home / ".synthesis" / "v5" / "rituals"
    rituals.mkdir(parents=True, exist_ok=True)
    (rituals / "config.json").write_text(json.dumps(cfg))
    doctor.main([])
    lines = [line for line in capsys.readouterr().out.splitlines() if line.split()[1:3] == ["prompt", "check"]]
    assert len(lines) == 1 and lines[0].split()[0] == "info" and "on for alpha (from 2026-11-14), delta" in lines[0]
    (rituals / "config.json").write_text("{not json")
    doctor.main([])
    lines = [line for line in capsys.readouterr().out.splitlines() if line.split()[1:3] == ["prompt", "check"]]
    assert len(lines) == 1 and lines[0].split()[0] == "warn"


def test_the_prompt_check_line_reads_the_setting_as_the_day_end_does():
    """Review of 5.14.0, findings 5 and 6: the line read a workspace's own entry, so a check set under `defaults`
    was reported off where every day-end asked; and it called `on` a setting every day-end of that workspace
    refuses (null, 0, an empty object, a folder named from no fixed place, a first day that is no day)."""
    inherited = {"defaults": {"prompt_reconcile": {"records": ["/abs/kb"]}},
                 "workspaces": {"alpha": {}, "beta": {"prompt_reconcile": False}}}
    assert doctor.check_prompt_check(inherited).detail.startswith("on for alpha, any workspace the config does not list; off for beta")
    only = {"defaults": {"prompt_reconcile": {"records": ["/abs/kb"]}}, "workspaces": {}}
    assert doctor.check_prompt_check(only).detail == "on for any workspace the config does not list"
    loose = doctor.check_prompt_check({"defaults": {"prompt_reconcile": {"records": ["rel"]}},
                                       "workspaces": {"beta": {"prompt_reconcile": False}}})
    assert loose.status == "warn" and "every day-end of any workspace the config does not list is refused" in loose.detail
    assert "off for beta" in loose.detail
    for bad in (None, 0, {}, [], "yes", {"records": ["kb"]}, {"records": ["/abs/kb"], "from": "tomorrow"}):
        check = doctor.check_prompt_check({"workspaces": {"alpha": {"prompt_reconcile": bad},
                                                          "beta": {"prompt_reconcile": {"records": ["/abs/kb"]}}}})
        assert check.status == "warn" and "every day-end of alpha is refused" in check.detail and "on for beta" in check.detail, bad


@pytest.mark.parametrize("config", [{"workspaces": {"alpha": ["x"]}}, {"workspaces": {"alpha": "x"}},
                                    {"workspaces": {"alpha": True}}, {"defaults": ["x"], "workspaces": {"alpha": {}}}])
def test_a_rituals_config_whose_workspace_is_no_object_costs_the_doctor_one_line_and_not_its_report(machine, capsys, config):
    """Review of 5.14.0, finding 4: the rituals' config reader raised a TypeError for such a file, which the doctor
    did not expect: no report, a traceback, and the release's own check after installing ended with it."""
    home, _, _ = machine
    rituals = home / ".synthesis" / "v5" / "rituals"
    rituals.mkdir(parents=True, exist_ok=True)
    (rituals / "config.json").write_text(json.dumps(config))
    doctor.main([])
    lines = [line for line in capsys.readouterr().out.splitlines() if line.split()[1:3] == ["prompt", "check"]]
    assert len(lines) == 1 and lines[0].split()[0] == "warn" and "cannot tell" in lines[0] and "object" in lines[0]
    assert _waiting(home).is_file()                                              # and the run reached its end


# --- Codex's listing, asked of one marketplace -----------------------------------------------------------------------
# 2026-11-13: a day-start doctor said it could not tell whether Codex held the plugin, twice. `codex plugin list`
# lists every marketplace, the remote catalog among them, and Codex fetches that catalog again when its copy is over
# three hours old (73 MB that morning, 52 s). The doctor's limit of 45 s stopped the fetch before it could finish, so
# the copy stayed old and the next run stopped it again. Asked for one marketplace (`-m`), Codex fetches no remote
# catalog (its source returns before the fetch), and the plugin ships from one marketplace.

ENTRY = {"pluginId": PLUGIN_ID, "name": "synthesis-skills", "version": "5.0.0", "marketplaceName": "synthesis-engineering", "enabled": True}
LIMITED, WHOLE = "plugin list --json -m synthesis-engineering", "plugin list --json"


def codex_listings(fakebin: Path, limited, whole) -> Path:
    """The fake Codex tells its two listings apart: `limited` answers the one asked of the plugin's marketplace,
    `whole` the one asked of every marketplace. A payload is printed; "hang" stands for the catalog's download, which
    does not end in time; "usage" for a build that does not know the option. A shell answers them, since a limit in
    a test must not depend on how fast Python starts on a busy machine (a review, 2026-11-13); everything else goes
    to the Python fake. Returns the log of the listings asked."""
    log = fakebin / "codex-listings.log"
    (fakebin / "codex").rename(fakebin / "codex-other")

    def answer(name: str, value) -> str:
        if value == "hang":
            return "sleep 60"
        if value == "usage":
            return 'echo "error: unexpected argument \'-m\' found" >&2; exit 2'
        (fakebin / f"codex-{name}.json").write_text(json.dumps(value))
        return f'cat "{fakebin}/codex-{name}.json"'
    _exe(fakebin / "codex", f'''case "$*" in
  --version) exit 0;;
  "{LIMITED}") echo "$*" >> "{log}"; {answer("limited", limited)};;
  "{WHOLE}") echo "$*" >> "{log}"; {answer("whole", whole)};;
  *) exec "{fakebin}/codex-other" "$@";;
esac''')
    return log


def codex_lines(capsys) -> dict:
    return {" ".join(line.split()[1:3]): line for line in capsys.readouterr().out.splitlines()[1:] if line.split()[1] == "codex"}


def test_codex_is_asked_for_the_plugins_own_marketplace_and_the_remote_catalog_is_never_waited_on(machine, monkeypatch, capsys):
    _, fakebin, _ = machine
    log = codex_listings(fakebin, limited={"installed": [ENTRY], "available": []}, whole="hang")
    monkeypatch.setattr(doctor, "CLI_TIMEOUT", 5)
    assert doctor.main([]) == 0
    lines = codex_lines(capsys)
    assert lines["codex plugin"].split()[0] == "ok" and "5.0.0 installed and enabled" in lines["codex plugin"]
    assert log.read_text().splitlines() == [LIMITED]                             # the whole listing was never started


def test_a_plugin_the_one_marketplace_does_not_show_is_looked_for_in_the_whole_listing(machine, capsys):
    """Absent is not said from the narrower look: a plugin installed from a marketplace of another name is found."""
    home, fakebin, _ = machine
    cache = home / ".codex" / "plugins" / "cache"
    (cache / "synthesis-engineering").rename(cache / "a-fork")
    fork = {**ENTRY, "pluginId": "synthesis-skills@a-fork", "marketplaceName": "a-fork"}
    log = codex_listings(fakebin, limited={"installed": [], "available": []}, whole={"installed": [fork], "available": []})
    doctor.main([])
    lines = codex_lines(capsys)
    assert lines["codex plugin"].split()[0] == "ok" and "a-fork" in lines["codex plugin"]
    assert lines["codex package"].split()[0] == "ok"
    assert log.read_text().splitlines() == [LIMITED, WHOLE]


def test_a_codex_that_does_not_know_the_option_is_asked_for_the_whole_listing(machine, capsys):
    _, fakebin, _ = machine
    log = codex_listings(fakebin, limited="usage", whole={"installed": [ENTRY], "available": []})
    assert doctor.main([]) == 0
    assert codex_lines(capsys)["codex plugin"].split()[0] == "ok"
    assert log.read_text().splitlines() == [LIMITED, WHOLE]


def test_a_plugin_in_neither_listing_is_not_installed(machine, capsys):
    _, fakebin, _ = machine
    empty = {"installed": [], "available": []}
    log = codex_listings(fakebin, limited=empty, whole=empty)
    assert doctor.main([]) == 1
    line = codex_lines(capsys)["codex plugin"]
    assert line.split()[0] == "fail" and "is not installed" in line
    assert log.read_text().splitlines() == [LIMITED, WHOLE]


def test_a_listing_that_does_not_answer_is_not_waited_on_a_second_time_and_the_line_says_what_ends_it(machine, monkeypatch, capsys):
    """A listing stopped at the limit says nothing about the install. The whole listing is where Codex fetches its
    catalog, and stopping it leaves the copy old, so the line names what lets it finish."""
    _, fakebin, _ = machine
    log = codex_listings(fakebin, limited="hang", whole={"installed": [ENTRY], "available": []})
    monkeypatch.setattr(doctor, "CLI_TIMEOUT", 2)
    doctor.main([])
    line = codex_lines(capsys)["codex plugin"]
    assert line.split()[0] == "warn" and "cannot tell" in line and "did not answer within 2 s" in line
    assert log.read_text().splitlines() == [LIMITED]


def test_a_whole_listing_that_does_not_answer_says_what_lets_it_finish(machine, monkeypatch, capsys):
    _, fakebin, _ = machine
    log = codex_listings(fakebin, limited={"installed": [], "available": []}, whole="hang")
    monkeypatch.setattr(doctor, "CLI_TIMEOUT", 2)
    doctor.main([])
    line = codex_lines(capsys)["codex plugin"]
    assert line.split()[0] == "warn" and "cannot tell" in line and "`codex plugin list`" in line and "once" in line
    assert log.read_text().splitlines() == [LIMITED, WHOLE]


def test_doctor_names_each_problem_and_exits_nonzero(machine, capsys):
    home, fakebin, muse_dir = machine
    config = home / ".codex" / "config.toml"
    text = config.read_text().replace("hooks = true\n", "")
    config.write_text(text.replace(f'[hooks.state."{PLUGIN_ID}:hooks/hooks.json:pre_tool_use:0:0"]', "[unrelated]"))
    (muse_dir / "synthesis" / "board.py").write_text("# stale\n")
    assert doctor.main([]) == 1
    out = capsys.readouterr().out
    assert out.splitlines()[0].startswith("synthesis doctor: 2 problems (")
    assert "needs /hooks approval: pre_tool_use:0:0 untrusted" in out
    assert "[features] hooks is not set" in out
    assert "muse package" in out and "differs from the runtime" in out


def test_doctor_json_output(machine, capsys):
    assert doctor.main(["--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["healthy"] is True and isinstance(report["ms"], int)
    assert {"status", "name", "detail"} == set(report["checks"][0])


def test_a_codex_config_that_grants_the_board_alone_is_a_problem_and_the_doctor_names_the_outbox(machine, capsys):
    """What setup wrote before the outbox: Codex's sandbox can post on the board and cannot stage a file."""
    config = machine[0] / ".codex" / "config.toml"
    granted = f"\"{machine[0] / '.synthesis' / 'v5' / 'outbox'}\" = \"write\"\n"
    assert granted in config.read_text()
    config.write_text(config.read_text().replace(granted, ""))
    assert doctor.main([]) == 1
    line = next(row for row in capsys.readouterr().out.splitlines() if "codex board access" in row)
    assert "fail" in line and "~/.synthesis/v5/outbox" in line and "cannot stage a file" in line


def test_doctor_skips_absent_harnesses(machine, capsys):
    _, fakebin, _ = machine
    (fakebin / "codex").unlink()
    (fakebin / "muse").unlink()
    doctor.main([])
    out = capsys.readouterr().out
    assert "claude plugin" in out and "codex" not in out and "muse" not in out


def test_doctor_with_no_harness_on_path_warns(machine):
    checks = doctor.run_checks(find=lambda name: None)
    assert any(c.name == "harnesses" and c.status == "warn" for c in checks)


def test_a_setting_that_is_present_and_null_fails_its_line_and_an_absent_one_has_no_line(machine):
    """`"temporary_addresses": null` is a setting that cannot be read, not a rule that is off: only an absent key is."""
    def line():
        return [c for c in doctor.run_checks(find=lambda name: None) if c.name == "temporary addresses"]

    assert line() == []
    paths.config_file().write_text(json.dumps({"temporary_addresses": None}), encoding="utf-8")
    found = line()
    assert len(found) == 1 and found[0].status == "fail" and "temporary_addresses" in found[0].detail
    paths.config_file().write_text(json.dumps({"temporary_addresses": {}}), encoding="utf-8")
    assert [c.status for c in line()] == ["ok"]


def test_a_hung_cli_is_bounded_and_reaped(tmp_path):
    script = tmp_path / "hang"
    script.write_text("#!/bin/sh\nexec sleep 30\n")
    script.chmod(0o755)
    proc = doctor._start([str(script)])
    start = time.monotonic()
    data, error = doctor._finish(proc, timeout=0.3)
    assert data is None and error.startswith("cannot tell") and "did not answer" in error
    assert time.monotonic() - start < 5 and proc.returncode is not None


def test_a_cli_that_prints_no_json_is_reported():
    data, error = doctor._finish(doctor._start(["/bin/echo", "not json"]))
    assert data is None and "gave no JSON" in error
    assert doctor._finish(doctor._start(["/nonexistent/claude"]))[1].startswith("could not run")


def test_the_cli_runs_doctor(machine, capsys):
    from synthesis import cli
    code = cli.main(["doctor", "--json"])
    assert json.loads(capsys.readouterr().out)["healthy"] is (code == 0)


# ---- finding each harness's CLI (client_binaries, kept) -----------------------

def _exe(path: Path, body: str = "exit 0") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!/bin/sh\n{body}\n")
    path.chmod(0o755)
    return path


def test_codex_inside_the_desktop_app_is_found_off_path(tmp_path, monkeypatch):
    monkeypatch.delenv("SYNTHESIS_CODEX_BIN", raising=False)
    app = _exe(tmp_path / "ChatGPT.app" / "Contents" / "Resources" / "codex-cli" / "bin" / "codex")
    assert doctor.find_client("codex", which=lambda n: None, locations=[str(app)]) == str(app)


def test_claude_inside_the_desktop_app_is_found_newest_version_first(tmp_path, monkeypatch):
    monkeypatch.delenv("SYNTHESIS_CLAUDE_BIN", raising=False)
    root = tmp_path / "Claude" / "claude-code"
    for version in ("2.1.99", "2.1.309", "2.1.1000"):
        _exe(root / version / "5af865b9901c" / "claude.app" / "Contents" / "MacOS" / "claude")
    pattern = str(root / "*" / "*" / "claude.app" / "Contents" / "MacOS" / "claude")
    newest = str(root / "2.1.1000" / "5af865b9901c" / "claude.app" / "Contents" / "MacOS" / "claude")
    assert doctor.find_client("claude", which=lambda n: None, locations=[pattern]) == newest
    on_path = _exe(tmp_path / "bin" / "claude")
    assert doctor.find_client("claude", which=lambda n: str(on_path), locations=[pattern]) == str(on_path)
    assert doctor.find_client("claude", which=lambda n: None, locations=[str(tmp_path / "none" / "*" / "claude")]) is None
    assert any("Claude/claude-code/*" in c for c in doctor.KNOWN_LOCATIONS["claude"])


def test_client_override_is_authoritative(tmp_path, monkeypatch):
    app = _exe(tmp_path / "codex")
    monkeypatch.setenv("SYNTHESIS_CODEX_BIN", "")
    assert doctor.find_client("codex", which=lambda n: str(app), locations=[str(app)]) is None  # empty means absent
    monkeypatch.setenv("SYNTHESIS_CODEX_BIN", str(tmp_path / "nowhere"))
    assert doctor.find_client("codex", which=lambda n: str(app), locations=[str(app)]) is None  # never another install
    monkeypatch.setenv("SYNTHESIS_CODEX_BIN", str(app))
    assert doctor.find_client("codex") == str(app)


def test_a_stale_codex_launcher_on_path_is_skipped(tmp_path, monkeypatch):
    monkeypatch.delenv("SYNTHESIS_CODEX_BIN", raising=False)
    stale = _exe(tmp_path / "path" / "codex", "exit 1")
    good = _exe(tmp_path / "app" / "codex")
    assert doctor.find_client("codex", which=lambda n: str(stale), locations=[str(good)]) == str(good)


def test_version_probe_is_bounded_closes_stdin_and_reaps(tmp_path, monkeypatch):
    hung = _exe(tmp_path / "codex", "read line; sleep 30")
    start = time.monotonic()
    assert doctor._version_ok(str(hung), timeout=0.3) == "slow"                  # no answer, which is not an error
    assert time.monotonic() - start < 5
    monkeypatch.setattr(doctor, "PROBE_TIMEOUT", 2.5)                            # the limit is read when the probe runs
    start = time.monotonic()
    assert doctor._version_ok(str(hung)) == "slow" and time.monotonic() - start >= 2.4
    assert doctor._version_ok(str(_exe(tmp_path / "broken", "exit 3"))) is False
    assert doctor._version_ok(str(_exe(tmp_path / "fine"))) is True


def test_a_codex_that_is_slow_to_say_its_version_is_still_the_codex_on_this_machine(tmp_path, monkeypatch):
    """2026-11-13: on a busy machine a Codex command took longer than the probe's two seconds to say its version,
    and the doctor printed no Codex line at all: nine checks gone, a summary that counted the rest, and nothing that
    said so. The installer and a release would have skipped Codex the same way, as not on this machine. A command
    that did not answer in time is not a harness that is absent: where no other install answers, it is the one."""
    monkeypatch.delenv("SYNTHESIS_CODEX_BIN", raising=False)
    monkeypatch.setattr(doctor, "PROBE_TIMEOUT", 1.0)
    slow, broken, good = (_exe(tmp_path / "slow" / "codex", "sleep 30"), _exe(tmp_path / "broken" / "codex", "exit 1"),
                          _exe(tmp_path / "good" / "codex"))
    assert doctor.find_client("codex", which=lambda n: str(slow), locations=[]) == str(slow)
    assert doctor.find_client("codex", which=lambda n: str(slow), locations=[str(broken)]) == str(slow)
    assert doctor.find_client("codex", which=lambda n: str(broken), locations=[str(slow)]) == str(slow)
    assert doctor.find_client("codex", which=lambda n: str(slow), locations=[str(good)]) == str(good)  # another install answers
    assert doctor.find_client("codex", which=lambda n: str(broken), locations=[]) is None


def test_the_doctor_looks_at_a_codex_whose_version_probe_was_slow(machine, monkeypatch, capsys):
    _, fakebin, _ = machine
    script = fakebin / "codex"
    script.write_text(script.read_text().replace("import json, sys\n", "import json, sys, time\nif sys.argv[1:] == ['--version']:\n    time.sleep(30)\n", 1))
    monkeypatch.setattr(doctor, "PROBE_TIMEOUT", 0.5)
    assert doctor.main([]) == 0
    lines = codex_lines(capsys)
    assert {"codex plugin", "codex package", "codex hooks", "codex hook", "codex skill", "codex board"} <= set(lines)
    assert [line for line in lines.values() if line.split()[0] != "ok"] == []


def test_a_codex_that_answers_nothing_is_named_on_a_machine_with_no_other_harness(machine, monkeypatch, capsys):
    """A launcher that hangs on every command: the doctor cannot tell, says so on Codex's plugin line, and does not
    also say that no harness was found."""
    home, _, _ = machine
    hung = _exe(home / "only" / "codex", "sleep 60")
    monkeypatch.setenv("PATH", os.pathsep.join([str(hung.parent), "/usr/bin", "/bin"]))
    monkeypatch.setattr(doctor, "PROBE_TIMEOUT", 0.5)
    monkeypatch.setattr(doctor, "CLI_TIMEOUT", 2)
    doctor.main([])
    out = capsys.readouterr().out.splitlines()[1:]
    plugin = [line for line in out if line.split()[1:3] == ["codex", "plugin"]]
    assert len(plugin) == 1 and plugin[0].split()[0] == "warn" and "cannot tell" in plugin[0] and "did not answer within 2 s" in plugin[0]
    assert not [line for line in out if line.split()[1] == "harnesses"]


def test_a_stale_launcher_beside_a_codex_that_answers_is_passed_over_without_a_word(machine, monkeypatch, capsys):
    """The probe exists for a launcher that outlived its app: where another install answers, that one is Codex."""
    home, fakebin, _ = machine
    stale = _exe(home / "stale" / "codex", "sleep 30")
    quick = _exe(home / "quick" / "codex", f'[ "$1" = "--version" ] && exit 0\nexec "{fakebin}/codex" "$@"')  # a shell says its version at once
    monkeypatch.setattr(doctor, "PROBE_TIMEOUT", 3)
    monkeypatch.setattr(doctor, "KNOWN_LOCATIONS", {**doctor.KNOWN_LOCATIONS, "codex": (str(quick),)})
    monkeypatch.setenv("PATH", os.pathsep.join([str(stale.parent), os.environ["PATH"]]))
    assert doctor.main([]) == 0
    lines = codex_lines(capsys)
    assert lines["codex plugin"].split()[0] == "ok" and "cannot tell" not in "".join(lines.values())


@pytest.mark.parametrize("entry", [{**{"pluginId": PLUGIN_ID, "name": "synthesis-skills", "marketplaceName": "synthesis-engineering", "enabled": True}, **more}
                                   for more in ({"version": None}, {"version": "9.9.9"}, {})])
def test_a_listed_plugin_whose_folder_cannot_be_found_fails_its_line_and_the_doctor_still_reports(machine, capsys, entry):
    """A review, 2026-11-13: a listing with no version, or one that names a folder that is not there, ended the
    doctor with a traceback and no report at all."""
    _, fakebin, _ = machine
    codex_listings(fakebin, limited={"installed": [entry], "available": []}, whole="hang")
    assert doctor.main([]) == 1
    lines = codex_lines(capsys)
    assert lines["codex package"].split()[0] == "fail" and "no v5 runtime package" in lines["codex package"]


@pytest.mark.parametrize("printed, expected", [
    ('loaded [1] marketplace\n{"installed": []}', {"installed": []}),
    ('skipped: []\n{"a": 1}', {"a": 1}),
    ('note {x}\n[1, 2]', [1, 2]),
    ('{x}\n{"a": 2}', {"a": 2}),
    ('warning: slow\n  {"a": 3}\n', {"a": 3}),
    ('{"a": 4}', {"a": 4}),
])
def test_a_listing_is_read_past_the_words_a_command_prints_before_it(tmp_path, printed, expected):
    """A review, 2026-11-13: the listing was read from the first brace or bracket anywhere, so a line of words that
    held one before the listing made an installed plugin read as not installed."""
    out = tmp_path / "out.txt"
    out.write_text(printed)
    assert doctor._finish(doctor._start(["/bin/cat", str(out)])) == (expected, "")
    out.write_text("note {x} and [y]\n")
    assert doctor._finish(doctor._start(["/bin/cat", str(out)]))[0] is None


# ---- Codex skill catalog and instruction bytes ---------------------------------

def _skill(root: Path, name: str, explicit=False, description="Use when x.") -> dict:
    path = root / "skills" / name / "SKILL.md"
    path.parent.mkdir(parents=True)
    path.write_text(f"---\nname: {name}\ndescription: {description}\n---\n")
    if explicit:
        (path.parent / "agents").mkdir()
        (path.parent / "agents" / "openai.yaml").write_text("policy:\n  allow_implicit_invocation: false\n")
    return {"name": f"synthesis-skills:{name}", "description": description, "path": str(path), "enabled": True}


def test_catalog_counts_only_implicit_skills_against_two_percent(tmp_path):
    skills = [_skill(tmp_path, "a"), _skill(tmp_path, "b", explicit=True)]
    cost, budget = doctor.catalog_cost(skills, 100_000)
    assert budget == 2000
    assert cost == doctor.catalog_cost(skills[:1], 100_000)[0]
    assert doctor.catalog_cost(skills, None)[1] == 2000  # 8,000-character fallback


def test_catalog_cuts_descriptions_at_1024_characters(tmp_path):
    """Held against the same skill with a shorter description, not against a number: the catalog names the folder the
    skill is in, so a fixed bound failed wherever the temporary folder's path was long (572 against 571)."""
    def cost(length: int) -> int:  # a folder for each, named by a number of the same width
        return doctor.catalog_cost([_skill(tmp_path / str(length), "a", description="d" * length)], None)[0]
    assert cost(5000) == cost(1024) == cost(1020) + 1  # four characters are one token


def test_catalog_check_names_undiscoverable_skills_and_overruns(tmp_path):
    plugin = tmp_path / "plugin"
    listed = [_skill(plugin, "a")]
    _skill(plugin, "b")
    result = {"data": [{"skills": listed, "errors": []}]}
    check = doctor.check_codex_catalog(result, "", plugin, {}, tmp_path)
    assert check.status == "fail" and "not discoverable: b" in check.detail
    full = {"data": [{"skills": listed + [{**listed[0], "name": "synthesis-skills:b"}], "errors": []}]}
    assert doctor.check_codex_catalog(full, "", plugin, {}, tmp_path).status == "ok"
    big = {"data": [{"skills": [_skill(tmp_path / f"p{i}", f"s{i}", description="d" * 1024) for i in range(9)]}]}
    assert doctor.check_codex_catalog(big, "", None, {}, tmp_path).status == "fail"
    assert doctor.check_codex_catalog(None, "boom", plugin, {}, tmp_path).status == "warn"


def test_catalog_budget_follows_the_configured_model(tmp_path):
    (tmp_path / "models_cache.json").write_text(json.dumps({"models": [{"slug": "m", "context_window": 272000}]}))
    assert doctor._context_window({"model": "m"}, tmp_path) == 272000
    assert doctor._context_window({"model": "other"}, tmp_path) is None


def test_a_model_cache_with_an_older_copys_tail_after_it_is_read_by_its_first_whole_value(tmp_path):
    """2026-11-13: in the minute after a release, Codex's cache of its models held one whole fresh value and, after
    it, the tail of a longer copy: what two writers leave when a shorter body lands over a longer one. Read as no
    cache, the model's window was unknown, and the catalog failed at 2,794 of 2,000 tokens where it reads 2,794 of
    10,000."""
    whole = json.dumps({"fetched_at": "2026-11-13T17:09:18Z", "models": [{"slug": "m", "context_window": 500000}]}, indent=2)
    (tmp_path / "models_cache.json").write_text(whole + 'ly",\n      "multi_agent_version": "v1"\n    }\n  ]\n}')
    assert doctor._context_window({"model": "m"}, tmp_path) == 500000


def test_a_model_cache_that_cannot_be_read_is_said_and_fails_no_catalog(tmp_path):
    """With no value to read in it, the doctor cannot tell the budget Codex gives the catalog: Codex rewrites the
    file when it next lists its models, and knows the window then. That is a warning, and no failure on the budget
    for a model Codex does not know. With no cache at all Codex knows no window either, and that budget is its own."""
    big = {"data": [{"skills": [_skill(tmp_path / f"p{i}", f"s{i}", description="d" * 1024) for i in range(9)]}]}
    (tmp_path / "models_cache.json").write_text('{"models": [{"slug": "m", "context_w')
    check = doctor.check_codex_catalog(big, "", None, {"model": "m"}, tmp_path)
    assert check.status == "warn" and "cannot tell" in check.detail and "model cache" in check.detail, check
    (tmp_path / "models_cache.json").unlink()
    assert doctor.check_codex_catalog(big, "", None, {"model": "m"}, tmp_path).status == "fail"


def test_instruction_chain_is_measured_against_the_limit_with_a_reserve(tmp_path):
    codex_home, repo = tmp_path / "codex", tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / "sub").mkdir()
    codex_home.mkdir()
    (codex_home / "AGENTS.md").write_text("u" * 20_000)
    (repo / "AGENTS.md").write_text("r" * 5_000)
    (repo / "sub" / "CLAUDE.md").write_text("c" * 5_000)
    check = doctor.check_codex_instructions(repo / "sub", {}, codex_home)
    assert check.status == "ok" and "25,000 bytes in 2 file(s)" in check.detail
    fallback = {"project_doc_fallback_filenames": ["CLAUDE.md"]}
    assert "30,000 bytes in 3" in doctor.check_codex_instructions(repo / "sub", fallback, codex_home).detail
    (codex_home / "AGENTS.md").write_text("u" * 30_000)
    assert doctor.check_codex_instructions(repo / "sub", {}, codex_home).status == "fail"  # over 32 KiB minus 4 KiB
    assert doctor.check_codex_instructions(repo / "sub", {"project_doc_max_bytes": 98304}, codex_home).status == "ok"


# ---- workspace folders: adapters, home paths, temporary storage -----------------

def _workspace(tmp_path) -> Path:
    ws = tmp_path / "workspaces" / "demo"
    for name in ("ok", "claude-only", "no-adapter", "divergent", "linked", "reverse-linked", "bare"):
        (ws / name / ".git").mkdir(parents=True)
    (ws / "ok" / "AGENTS.md").write_text("rules\n")
    (ws / "ok" / "CLAUDE.md").write_text("@AGENTS.md\n")
    (ws / "claude-only" / "CLAUDE.md").write_text("rules\n")
    (ws / "no-adapter" / "AGENTS.md").write_text("rules\n")
    (ws / "divergent" / "AGENTS.md").write_text("rules\n")
    (ws / "divergent" / "CLAUDE.md").write_text("other rules\n")
    (ws / "linked" / "AGENTS.md").write_text("rules\n")
    (ws / "linked" / "CLAUDE.md").symlink_to("AGENTS.md")
    (ws / "reverse-linked" / "CLAUDE.md").write_text("rules\n")  # AGENTS.md links to CLAUDE.md: one file
    (ws / "reverse-linked" / "AGENTS.md").symlink_to("CLAUDE.md")
    (ws / "not-a-repo").mkdir()
    return ws


def test_workspace_repos_lists_workspaces_and_their_repositories(tmp_path):
    ws = _workspace(tmp_path)
    repos = doctor.workspace_repos({"workspace_roots": [str(tmp_path / "workspaces" / "*")]})
    assert repos[0] == ws and ws / "not-a-repo" not in repos and len(repos) == 8


def test_instruction_adapters_report_each_divergence_and_change_nothing(tmp_path):
    ws = _workspace(tmp_path)
    states = {r.name: doctor.adapter_state(r) for r in (ws / n for n in
              ("ok", "claude-only", "no-adapter", "divergent", "linked", "reverse-linked", "bare"))}
    assert states["ok"] == states["linked"] == states["reverse-linked"] == states["bare"] == ""
    assert "Codex reads nothing" in states["claude-only"]
    assert "no CLAUDE.md" in states["no-adapter"] and "not `@AGENTS.md`" in states["divergent"]
    before = (ws / "divergent" / "CLAUDE.md").read_text()
    check = doctor.check_instruction_adapters(doctor.workspace_repos({"workspace_roots": [str(ws)]}))
    assert check.status == "warn" and "3 folder(s)" in check.detail
    assert (ws / "divergent" / "CLAUDE.md").read_text() == before


def test_literal_home_paths_in_synced_config_fail(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "h"))
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"knowledge_roots": ["~/workspaces/x/ai-knowledge-x"]}))
    assert doctor.check_home_paths([config]).status == "ok"
    config.write_text(json.dumps({"knowledge_roots": [str(tmp_path / "h" / "workspaces")]}) + "\n")
    check = doctor.check_home_paths([config])
    assert check.status == "fail" and "config.json:1" in check.detail
    config.write_text(json.dumps({"root": str(tmp_path / "h")}) + "\n")
    assert doctor.check_home_paths([config]).status == "fail"


def test_paths_outside_the_current_home_are_not_home_paths(tmp_path, monkeypatch):
    """M5: a sandbox HOME beside the knowledge root made every /Users/ path fail, where ~ cannot be written."""
    monkeypatch.setenv("HOME", str(tmp_path / "sandbox" / "home"))
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"knowledge_roots": [str(tmp_path / "sandbox" / "knowledge")],
                                  "protected_roots": ["/Us" + "ers/someone/workspaces", str(tmp_path / "sandbox" / "homework")]}))
    assert doctor.check_home_paths([config]).status == "ok"


def test_worktrees_sessions_and_venvs_under_temporary_folders_warn(tmp_path):
    temp, repo = tmp_path / "tmp", tmp_path / "repo"
    (temp / "wt").mkdir(parents=True)
    marker = repo / ".git" / "worktrees" / "wt" / "gitdir"
    marker.parent.mkdir(parents=True)
    marker.write_text(str(temp / "wt" / ".git") + "\n")
    (temp / "env").mkdir()
    (temp / "env" / "pyvenv.cfg").write_text("home = /usr/bin\n")
    check = doctor.check_temporary_work([repo], [str(temp / "x")], roots=[str(temp.resolve())], venv_roots=[temp])
    assert check.status == "warn"
    assert "worktree" in check.detail and "session" in check.detail and "venv" in check.detail
    clean = doctor.check_temporary_work([repo], [str(tmp_path)], roots=[str((tmp_path / "elsewhere").resolve())])
    assert clean.status == "ok"


# ---- latest release, on demand -----------------------------------------------

def test_latest_release_compares_semantically_and_never_asks_for_a_downgrade():
    fetch = lambda url: json.dumps({"version": "4.10.0"})
    check = doctor.check_latest({"claude": "4.9.0", "codex": "4.10.0"}, fetch=fetch)
    assert check.status == "warn" and "behind: claude 4.9.0" in check.detail
    assert doctor.check_latest({"codex": "4.11.0"}, fetch=fetch).status == "ok"  # ahead of the channel


def test_latest_release_failure_is_reported_not_hidden():
    def fail(url):
        raise OSError("network down")
    check = doctor.check_latest({"claude": "5.0.0"}, fetch=fail)
    assert check.status == "warn" and "network down" in check.detail


def test_fetch_retries_with_the_system_ca_bundle_only_on_certificate_failures(monkeypatch, tmp_path):
    import urllib.request
    calls = []

    def urlopen(url, timeout=0, context=None):
        calls.append(context)
        if context is None:
            raise OSError("<urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed>")
        class Response:
            def read(self):
                return b'{"version": "5.0.0"}'
        return Response()
    bundle = tmp_path / "cert.pem"
    bundle.write_text("")
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(doctor, "SYSTEM_CA_FILES", (str(bundle),))
    import ssl
    monkeypatch.setattr(ssl, "create_default_context", lambda cafile=None: ("ctx", cafile))
    assert doctor.fetch_text("https://example.test/x") == '{"version": "5.0.0"}'
    assert calls == [None, ("ctx", str(bundle))]

    def refused(url, timeout=0, context=None):
        raise OSError("connection refused")
    monkeypatch.setattr(urllib.request, "urlopen", refused)
    with pytest.raises(OSError, match="refused"):
        doctor.fetch_text("https://example.test/x")


# ---- versions across harnesses and decision packets ------------------------------

def test_versions_agree_differ_or_a_release_is_in_progress():
    from synthesis import board
    assert doctor.check_versions({"claude": "5.0.0", "codex": "5.0.0"}, []).status == "ok"
    differ = {"claude": "5.0.1", "codex": "5.0.0"}
    assert doctor.check_versions(differ, []).status == "warn"
    releaser = board.Session(session="rel", claims=["/src/synthesis-skills/CHANGELOG.md"], seen=time.time())
    check = doctor.check_versions(differ, [releaser])
    assert check.status == "info" and "release is in progress (rel)" in check.detail


def test_hand_made_or_edited_packets_are_flagged(tmp_path):
    import hashlib
    artifacts = tmp_path / "projects" / "p" / "resources" / "artifacts"
    artifacts.mkdir(parents=True)
    spec = '{"items": []}'
    marker = f"<!-- synthesis-decision-packet spec-sha256:{hashlib.sha256(spec.encode()).hexdigest()} -->"
    (artifacts / "2026-10-05-good-packet.html").write_text(f'{marker}\n<script type="application/json" id="spec">{spec}</script>')
    assert doctor.check_packets([tmp_path]).status == "ok"
    (artifacts / "2026-10-05-edited-packet.html").write_text(
        f'{marker}\n<script type="application/json" id="spec">{{"items": [1]}}</script>')
    (artifacts / "2026-10-05-hand-packet.html").write_text("<html>looks like a packet</html>")
    check = doctor.check_packets([tmp_path])
    assert check.status == "warn" and "2 of 3" in check.detail
    assert "edited after generation" in check.detail and "no generator marker" in check.detail


def test_sheets_named_from_their_titles_are_checked_by_their_marker(tmp_path):
    """2026-10-22: action sheets are filed as <date>-<title slug>.html ("your-actions-..."), which the name
    patterns missed, so no filed sheet had ever been checked."""
    import hashlib
    artifacts = tmp_path / "projects" / "p" / "resources" / "artifacts"
    artifacts.mkdir(parents=True)
    spec = '{"do": []}'
    marker = f"<!-- synthesis-action-sheet spec-sha256:{hashlib.sha256(spec.encode()).hexdigest()} -->"
    page = f'<title>Your actions</title>\n{marker}\n<script type="application/json" id="spec">{spec}</script>'
    (artifacts / "2026-10-22-your-actions-thursday.html").write_text(page)
    (artifacts / "2026-10-22-notes.html").write_text("<html>an ordinary page</html>")  # neither named nor marked
    assert doctor.check_packets([tmp_path]).detail.startswith("1 packet and sheet pages")
    (artifacts / "2026-10-22-your-actions-thursday.html").write_text(page.replace('"do": []', '"do": [1]'))
    check = doctor.check_packets([tmp_path])
    assert check.status == "warn" and "1 of 1" in check.detail and "edited after generation" in check.detail


def test_a_harness_cli_leaves_no_helper_running_after_the_doctor(tmp_path):
    """2026-10-06: Codex's app-server runs `git ls-remote` when it starts; killing only the app-server left
    git running in the doctor's process group, and the Console reported processes left behind."""
    marker = tmp_path / "helper.pid"
    fake = tmp_path / "codex"
    fake.write_text(f"""#!/bin/sh
sleep 30 &
echo $! > {marker}
while read line; do
  case "$line" in
    *'"id": 0'*) echo '{{"id": 0, "result": {{}}}}' ;;
    *'"id": 1'*) echo '{{"id": 1, "result": {{"data": []}}}}' ;;
  esac
done
""")
    fake.chmod(0o755)
    assert doctor.app_server_query(str(fake), "skills/list", {}) == {"data": []}
    helper = int(marker.read_text())
    with pytest.raises(ProcessLookupError):
        for _ in range(50):  # killed with the group; give the kernel a moment to reap it
            os.kill(helper, 0)
            time.sleep(0.02)
    proc = doctor._start([str(fake)])  # the plugin listings: reaped the same way when they finish
    proc.stdin and proc.stdin.close()
    doctor._finish(proc, timeout=0.5)
    with pytest.raises(ProcessLookupError):
        for _ in range(50):
            os.kill(int(marker.read_text()), 0)
            time.sleep(0.02)


def test_the_doctor_closes_the_pipes_of_a_cli_it_has_stopped(tmp_path, monkeypatch):
    """The three pipes opened to a harness CLI were left for the collector to close: nothing a person saw, and a
    warning for each under a Python that says so (3.13: `unclosed file` three times at every such query)."""
    fake, started, real = tmp_path / "codex", [], subprocess.Popen
    fake.write_text("""#!/bin/sh
while read line; do
  case "$line" in
    *'"id": 0'*) echo '{"id": 0, "result": {}}' ;;
    *'"id": 1'*) echo '{"id": 1, "result": {"data": []}}' ;;
  esac
done
""")
    fake.chmod(0o755)

    def recorded(*args, **kwargs):
        started.append(real(*args, **kwargs))
        return started[-1]
    monkeypatch.setattr(subprocess, "Popen", recorded)
    assert doctor.app_server_query(str(fake), "skills/list", {}) == {"data": []}
    cli, = started
    assert cli.returncode is not None and [pipe.closed for pipe in (cli.stdin, cli.stdout, cli.stderr)] == [True] * 3


def test_each_sessions_repo_is_checked_for_clone_recent_sync_and_size(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    cloned = tmp_path / "ai-sessions-a"
    (cloned / ".git").mkdir(parents=True)
    (state / "sync-a.json").write_text(json.dumps({"synced": "2026-10-30T20:00:00Z"}), encoding="utf-8")
    (state / "sync-c.json").write_text(json.dumps({"synced": "2026-10-20T20:00:00Z"}), encoding="utf-8")
    now = time.mktime(time.strptime("2026-10-31", "%Y-%m-%d"))
    found = {c.name: c for c in doctor.check_sessions_repos({"a": cloned, "b": tmp_path / "missing", "c": cloned}, state, now)}
    assert found["sessions repo a"].status == "ok"
    assert found["sessions repo b"].status == "warn" and "not cloned" in found["sessions repo b"].detail
    assert found["sessions repo c"].status == "warn" and "last synced 2026-10-20" in found["sessions repo c"].detail


def _schedule(plist: Path, line=None) -> Path:
    """The export's schedule file: as the setup writes it for this home's own command, or with `line` handed to its
    login shell; a list is its program arguments whole, a dictionary the job itself, bytes the file."""
    import plistlib
    own = install._home() / "bin" / "synthesis"
    line = f'"{own}" sessions export --all --scheduled; "{own}" sessions sync' if line is None else line
    job = line if isinstance(line, dict) else {"ProgramArguments": line if isinstance(line, list) else ["/bin/bash", "-lc", line]}
    plist.write_bytes(line if isinstance(line, bytes) else plistlib.dumps({"Label": plist.stem, **job}))
    return plist


def test_the_hourly_export_is_checked_for_its_schedule_and_its_last_run(tmp_path):
    plist, stamp = tmp_path / "com.synthesis.sessions-export.plist", tmp_path / "export.json"
    loaded = lambda argv, **kw: subprocess.CompletedProcess(argv, 0, "", "")           # noqa: E731
    absent = lambda argv, **kw: subprocess.CompletedProcess(argv, 113, "", "Could not find service")  # noqa: E731
    from datetime import datetime
    now = datetime.fromisoformat("2026-11-12T09:00:00-05:00").timestamp()
    found = doctor.check_sessions_export(plist, stamp, now, loaded)
    assert found.status == "warn" and "not scheduled" in found.detail and "--sessions-export" in found.detail
    _schedule(plist)
    found = doctor.check_sessions_export(plist, stamp, now, absent)
    assert found.status == "fail" and "not loaded" in found.detail
    found = doctor.check_sessions_export(plist, stamp, now, loaded)
    assert found.status == "fail" and "no export has finished" in found.detail
    stamp.write_text(json.dumps({"exported": "2026-11-11T08:00:00-05:00"}), encoding="utf-8")
    found = doctor.check_sessions_export(plist, stamp, now, loaded)
    assert found.status == "fail" and "25 hours" in found.detail
    stamp.write_text(json.dumps({"exported": "2026-11-12T08:20:00-05:00", "scheduled": "2026-11-12T08:20:00-05:00"}), encoding="utf-8")
    found = doctor.check_sessions_export(plist, stamp, now, loaded)
    assert found.status == "ok" and "every hour" in found.detail and "40 min ago" in found.detail


def test_the_hourly_export_is_known_by_a_run_of_the_schedule_itself(tmp_path):
    """The doctor read the schedule's file and asked launchd only whether the label was loaded. What launchd holds
    is what it loaded, which may be an older file's commands: a file replaced and never loaded again passed, while a
    session's own exports kept the stamp fresh (noted by a review, 2026-11-12). The schedule's command marks its
    runs, and a loaded schedule with no run of its own in a day fails."""
    from datetime import datetime
    plist, stamp = _schedule(tmp_path / "com.synthesis.sessions-export.plist"), tmp_path / "export.json"
    loaded = lambda argv, **kw: subprocess.CompletedProcess(argv, 0, "", "")           # noqa: E731
    now = datetime.fromisoformat("2026-11-12T09:00:00-05:00").timestamp()
    stamp.write_text(json.dumps({"exported": "2026-11-12T08:20:00-05:00"}), encoding="utf-8")  # a session's own export
    found = doctor.check_sessions_export(plist, stamp, now, loaded)
    assert found.status == "fail" and "the schedule itself has finished no export yet" in found.detail
    assert "--sessions-export" in found.detail and "launchd" in found.detail
    stamp.write_text(json.dumps({"exported": "2026-11-12T08:20:00-05:00", "scheduled": "2026-11-11T02:00:00-05:00"}), encoding="utf-8")
    found = doctor.check_sessions_export(plist, stamp, now, loaded)
    assert found.status == "fail" and "the schedule itself has finished no export in 31 hours" in found.detail
    stamp.write_text(json.dumps({"exported": "2026-11-12T08:20:00-05:00", "scheduled": "2026-11-12T07:10:00-05:00"}), encoding="utf-8")
    found = doctor.check_sessions_export(plist, stamp, now, loaded)
    assert found.status == "ok" and "40 min ago" in found.detail


def test_the_hourly_export_fails_while_a_transcript_it_tried_is_not_copied(tmp_path):
    """2026-11-12: every copy was refused, the stamp's time was fresh, and this check answered ok."""
    plist, stamp = tmp_path / "com.synthesis.sessions-export.plist", tmp_path / "export.json"
    plist.write_text("<plist/>", encoding="utf-8")
    loaded = lambda argv, **kw: subprocess.CompletedProcess(argv, 0, "", "")           # noqa: E731
    from datetime import datetime
    now = datetime.fromisoformat("2026-11-12T09:00:00-05:00").timestamp()
    refused = f"codex 01a1: not exported ([Errno 13] Permission denied: '{Path.home()}/x.jsonl')"
    stamp.write_text(json.dumps({"exported": "2026-11-12T08:20:00-05:00", "failed": 3, "reason": refused}), encoding="utf-8")
    found = doctor.check_sessions_export(plist, stamp, now, loaded)
    assert found.status == "fail" and "3 transcript(s) could not be copied" in found.detail
    assert "Permission denied: '~/x.jsonl'" in found.detail and "no run has copied everything yet" in found.detail
    stamp.write_text(json.dumps({"exported": "2026-11-12T08:20:00-05:00", "failed": 1, "reason": refused,
                                 "complete": "2026-11-11T08:00:00-05:00"}), encoding="utf-8")
    found = doctor.check_sessions_export(plist, stamp, now, loaded)
    assert found.status == "fail" and "no run has copied everything since 2026-11-11T08:00" in found.detail
    assert "synthesis sessions export --all" in found.detail
    plist.unlink()                       # with no schedule a session's own export still failed: a failure, not a warning
    found = doctor.check_sessions_export(plist, stamp, now, loaded)
    assert found.status == "fail" and "1 transcript(s) could not be copied" in found.detail


def test_the_hourly_export_names_a_transcript_that_is_gone_and_who_clears_it(tmp_path):
    """2026-11-12: a transcript the harness removed after its copy failed was forgotten by the next run, and this check
    answered ok. The stamp keeps its name; a run cannot copy it any more, so only the principal clears it."""
    plist, stamp = tmp_path / "com.synthesis.sessions-export.plist", tmp_path / "export.json"
    plist.write_text("<plist/>", encoding="utf-8")
    loaded = lambda argv, **kw: subprocess.CompletedProcess(argv, 0, "", "")           # noqa: E731
    from datetime import datetime
    now = datetime.fromisoformat("2026-11-12T09:00:00-05:00").timestamp()
    refused = f"codex 01a1: not exported ([Errno 13] Permission denied: '{Path.home()}/x.jsonl')"
    there = {"native": f"{Path.home()}/y.jsonl", "at": "2026-11-12T08:20:00-05:00", "reason": refused.replace("01a1", "01a2")}
    gone = {"native": f"{Path.home()}/x.jsonl", "at": "2026-11-10T07:15:00-05:00", "reason": refused, "gone": "2026-11-12T08:20:00-05:00"}
    stamp.write_text(json.dumps({"exported": "2026-11-12T08:20:00-05:00", "failed": 2, "reason": refused,
                                 "uncopied": {"codex 01a1": gone, "codex 01a2": there}}), encoding="utf-8")
    found = doctor.check_sessions_export(plist, stamp, now, loaded)
    assert found.status == "fail" and "2 transcript(s) could not be copied" in found.detail
    assert "codex 01a1 (its copy last failed 2026-11-10T07:15)" in found.detail and "codex 01a2 (its" not in found.detail
    assert "`synthesis sessions export --lost <session>`" in found.detail and "principal" in found.detail
    assert "run `synthesis sessions export --all`" in found.detail          # the other may yet be copied
    stamp.write_text(json.dumps({"exported": "2026-11-12T08:20:00-05:00", "failed": 1, "reason": refused,
                                 "uncopied": {"codex 01a1": gone}}), encoding="utf-8")
    found = doctor.check_sessions_export(plist, stamp, now, loaded)
    assert found.status == "fail" and "codex 01a1 (its copy last failed 2026-11-10T07:15)" in found.detail
    assert "export --all" not in found.detail and "export --lost" in found.detail      # no run can copy it now


# 2026-11-12, a second review: one label holds one schedule, so another install's setup replaces this install's under
# it. That schedule was loaded, and this home's stamp was fresh from its own sessions' exports: the check answered ok
# while nothing copied this home's transcripts on a schedule. Whose schedule it is, is told in one place in the core,
# which the setup that writes, replaces and removes a schedule asks too.

NOT_OURS = {  # {own} is this home's command; beside each, what the check names as what the schedule runs
    "another install's command": ('"/another/v5/bin/synthesis" sessions export --all; "/another/v5/bin/synthesis" sessions sync',
                                  "runs /another/v5/bin/synthesis,"),
    "this install's command, then another's": ('"{own}" sessions export --all; "/another/v5/bin/synthesis" sessions sync',
                                               "runs /another/v5/bin/synthesis,"),
    "two other programs": ('/opt/a/synthesis sessions export --all; /opt/b/synthesis sessions sync', "runs /opt/a/synthesis, /opt/b/synthesis,"),
    "another program handed this install's path": ('echo "{own}" sessions export --all', "runs echo,"),
    "a sibling whose name begins like it": ('"{own}-old" sessions export --all; "{own}-old" sessions sync', "runs {own}-old,"),
    "another program, with no shell": (["/usr/bin/env", "{own}", "sessions", "export", "--all"], "runs /usr/bin/env,"),
    "a job that names another program": ({"Program": "/bin/echo", "ProgramArguments": ["/bin/bash", "-lc", '"{own}" sessions sync']},
                                         "runs /bin/echo,"),
    "a line that runs nothing": ("export SYNTHESIS_HOME=/custom", "runs no command that can be read,"),
    "a file that is no schedule": (b"<plist/>", "runs no command that can be read,"),
}
OURS = {
    "the two commands, as the setup writes them": '"{own}" sessions export --all; "{own}" sessions sync',
    "homes set first": "export SYNTHESIS_HOME=/custom; export CODEX_HOME='/it'\"'\"'s; \"x\"'; \"{own}\" sessions export --all; \"{own}\" sessions sync",
    "the command with no shell": ["{own}", "sessions", "export", "--all"],
}


def _named(line, own: str):
    """`line` with this home's command written in, whatever shape it has."""
    if isinstance(line, dict):
        return {key: _named(value, own) for key, value in line.items()}
    if isinstance(line, list):
        return [_named(word, own) for word in line]
    return line.replace(b"{own}", own.encode()) if isinstance(line, bytes) else line.replace("{own}", own)


@pytest.fixture
def exporting(tmp_path):
    """A schedule file, a stamp an export left forty minutes ago, and the check as it answers while launchd holds
    the schedule loaded."""
    from datetime import datetime
    plist, stamp = tmp_path / "com.synthesis.sessions-export.plist", tmp_path / "export.json"
    stamp.write_text(json.dumps({"exported": "2026-11-12T08:20:00-05:00", "complete": "2026-11-12T08:20:00-05:00",
                                 "scheduled": "2026-11-12T08:20:00-05:00"}), encoding="utf-8")
    now = datetime.fromisoformat("2026-11-12T09:00:00-05:00").timestamp()

    def check(line=None, code: int = 0, **given):
        return doctor.check_sessions_export(_schedule(plist, line), stamp, now,
                                            lambda argv, **kw: subprocess.CompletedProcess(argv, code, "", ""), **given)
    check.stamp = stamp
    return check


@pytest.mark.parametrize("line, runs", NOT_OURS.values(), ids=NOT_OURS.keys())
def test_the_hourly_export_fails_while_the_loaded_schedule_is_not_this_installs(exporting, line, runs):
    own = str(install._home() / "bin" / "synthesis")
    assert exporting().status == "ok"                                          # the control: this install's own schedule
    found = exporting(_named(line, own))
    assert found.status == "fail" and found.name == "sessions export"
    assert runs.replace("{own}", own) in found.detail                          # the command the schedule runs,
    assert f"not this install's {own}" in found.detail                          # the one it would run if it were this install's,
    assert "--sessions-export" in found.detail                                 # and what makes it so


@pytest.mark.parametrize("line", OURS.values(), ids=OURS.keys())
def test_the_hourly_export_is_this_installs_however_the_line_around_its_command_is_written(exporting, line):
    found = exporting(_named(line, str(install._home() / "bin" / "synthesis")))
    assert found.status == "ok" and "40 min ago" in found.detail


def test_a_schedule_that_is_not_this_installs_is_weighed_after_a_failed_copy_and_a_schedule_not_loaded(exporting):
    other = '"/another/v5/bin/synthesis" sessions export --all; "/another/v5/bin/synthesis" sessions sync'
    found = exporting(other, code=113)                                         # not loaded: nothing runs, whoever's it is
    assert found.status == "fail" and "not loaded" in found.detail and "/another/v5" not in found.detail
    exporting.stamp.unlink()                                                   # no export has finished here: the schedule is why
    found = exporting(other)
    assert found.status == "fail" and "runs /another/v5/bin/synthesis," in found.detail and "no export has finished" not in found.detail
    exporting.stamp.write_text(json.dumps({"exported": "2026-11-12T08:20:00-05:00", "failed": 1, "reason": "codex 01a1: not exported (x)"}))
    found = exporting(other)                                                   # a transcript not copied is said first, as before
    assert found.status == "fail" and "1 transcript(s) could not be copied" in found.detail


def test_the_hourly_export_is_weighed_against_the_command_of_the_home_asked_about(exporting, tmp_path):
    """The check answers for one home: its stamp, and its own command. Asked about another home, that home's
    schedule is its own and this one's is not."""
    other = tmp_path / "other" / "v5" / "bin" / "synthesis"
    line = f'"{other}" sessions export --all; "{other}" sessions sync'
    assert exporting(line).status == "fail" and exporting(line, command=other).status == "ok"
    found = exporting(command=other)
    assert found.status == "fail" and f"runs {install._home() / 'bin' / 'synthesis'}," in found.detail and f"not this install's {other}" in found.detail


# ---- the outbox, and the mail connector that must read it ---------------------
# The send guard passes a file staged in the outbox. That is right only while the connector that will read it was
# started with the outbox among its ALLOWED_FILE_DIRS, which its start script sets: one started before that
# refuses the file after the principal approved the send. The process read is a fake here, apart from one test
# that reads a child this test starts.

SCRIPTS = ROOT / "skills" / "synthesis-meeting-transcripts" / "optional-workspace-mcp"
PORT = {"WORKSPACE_MCP_PORT": "8765"}  # the start script always sets it: the sign that its process was read


@pytest.fixture
def connector(tmp_path):
    """(the outbox, the connector's unit, its PID file), none of them made yet."""
    return tmp_path / "v5" / "outbox", tmp_path / "unit" / "workspace-mcp.plist", tmp_path / "logs" / "server.pid"


def _unread(pid):
    raise AssertionError(f"no process should be read here, and {pid} was")


def _installed(outbox: Path, unit: Path, pid_file: Path, pid: str = "4242") -> None:
    for path, text in ((unit, "<plist/>\n"), (pid_file, pid + "\n")):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    outbox.mkdir(parents=True, exist_ok=True)


def test_the_outbox_must_be_a_folder_an_agent_can_write(connector):
    outbox = connector[0]
    unmade = doctor.check_outbox(*connector, _unread)
    assert unmade.status == "info" and "not made yet" in unmade.detail  # no connector here: nothing is owed
    outbox.parent.mkdir(parents=True)
    outbox.write_text("a file where the folder belongs\n", encoding="utf-8")
    blocked = doctor.check_outbox(*connector, _unread)
    assert blocked.status == "fail" and "not a folder" in blocked.detail
    outbox.unlink()
    outbox.mkdir()
    made = doctor.check_outbox(*connector, _unread)
    assert made.status == "ok" and doctor._short(outbox) in made.detail
    outbox.chmod(0o500)
    try:
        locked = doctor.check_outbox(*connector, _unread)
    finally:
        outbox.chmod(0o700)
    if os.geteuid():  # root may write anywhere
        assert locked.status == "fail" and "cannot be written" in locked.detail


def test_a_connector_kept_running_must_have_been_started_with_the_outbox(connector, tmp_path):
    outbox, unit, pid_file = connector
    unit.parent.mkdir(parents=True)
    unit.write_text("<plist/>\n", encoding="utf-8")
    missing = doctor.check_outbox(*connector, _unread)  # installed, and the folder its start script makes is not there
    assert missing.status == "fail" and "missing" in missing.detail and "restart" in missing.detail
    _installed(*connector)
    read = []

    def started(**env):
        return lambda pid: read.append(pid) or {**PORT, **env}

    with_it = doctor.check_outbox(*connector, started(ALLOWED_FILE_DIRS=os.pathsep.join(["/srv/reports", f" {outbox} "])))
    assert with_it.status == "ok" and "started to read it" in with_it.detail and read == ["4242"]
    assert doctor.check_outbox(*connector, started(ALLOWED_FILE_DIRS=str(tmp_path))).status == "ok"  # a folder that holds it
    (tmp_path / "linked").symlink_to(outbox.parent, target_is_directory=True)
    assert doctor.check_outbox(*connector, started(ALLOWED_FILE_DIRS=str(tmp_path / "linked" / "outbox"))).status == "ok"
    unset = doctor.check_outbox(*connector, started())
    assert unset.status == "fail" and "ALLOWED_FILE_DIRS (not set)" in unset.detail and "restart" in unset.detail
    for off in ("true", " TRUE "):  # the connector's own switch: with it no local file is read, the outbox among them
        shut = doctor.check_outbox(*connector, started(ALLOWED_FILE_DIRS=str(outbox), WORKSPACE_MCP_DISABLE_LOCAL_FILES=off))
        assert shut.status == "fail" and "WORKSPACE_MCP_DISABLE_LOCAL_FILES" in shut.detail and "after the send is approved" in shut.detail
    assert doctor.check_outbox(*connector, started(ALLOWED_FILE_DIRS=str(outbox), WORKSPACE_MCP_DISABLE_LOCAL_FILES="false")).status == "ok"
    # A restart cannot help a connector whose auto-start carries another synthesis home: the line says what does.
    # The unit is removed and installed again, since a supervisor keeps the unit it has loaded until it is unloaded.
    assert "uninstall-autostart.sh and then install-autostart.sh" in unset.detail
    assert f"SYNTHESIS_HOME is {doctor._short(outbox.parent)}" in unset.detail
    other = os.pathsep.join(["/srv/reports", f"{outbox}-old", str(outbox).upper()])
    elsewhere = doctor.check_outbox(*connector, started(ALLOWED_FILE_DIRS=other))
    assert elsewhere.status == "fail" and other in elsewhere.detail


def test_a_connector_that_cannot_be_read_is_a_warning_and_never_ok(connector):
    outbox, unit, pid_file = connector
    _installed(*connector)
    pid_file.unlink()
    for written in (None, "", "not a number\n"):  # not running, or started some other way: nothing to read
        if written is not None:
            pid_file.write_text(written, encoding="utf-8")
        check = doctor.check_outbox(*connector, _unread)
        assert check.status == "warn" and "cannot tell" in check.detail, written
    pid_file.write_text("4242\n", encoding="utf-8")
    for shown in ({}, {"PATH": "/usr/bin:/bin", "ALLOWED_FILE_DIRS": str(outbox)}):  # nothing shown; not the start script's process
        check = doctor.check_outbox(*connector, lambda pid: shown)
        assert check.status == "warn" and "cannot tell" in check.detail, shown


def test_a_connector_started_by_hand_is_judged_when_it_can_be_read_and_expected_only_when_installed(connector):
    outbox, unit, pid_file = connector
    _installed(*connector)
    unit.unlink()
    without = doctor.check_outbox(*connector, lambda pid: dict(PORT))
    assert without.status == "fail" and "ALLOWED_FILE_DIRS (not set)" in without.detail
    assert "restart" in without.detail and "install-autostart.sh" not in without.detail  # no auto-start to install again
    assert doctor.check_outbox(*connector, lambda pid: {**PORT, "ALLOWED_FILE_DIRS": str(outbox)}).status == "ok"
    stopped = doctor.check_outbox(*connector, lambda pid: {})  # nothing is expected to run where none is installed
    assert stopped.status == "ok" and "no mail connector auto-start" in stopped.detail


def _procargs(argv: list, env: list, argc=None) -> bytes:
    """What macOS keeps for a process (kern.procargs2): its argument count, the program's path and its padding, each
    argument and each variable ended by a NUL, then an empty string and the system's own strings."""
    strings = [argv[0], "", "", *argv, *env, "", "ptr_munge=", "main_stack="]
    return (len(argv) if argc is None else argc).to_bytes(4, sys.byteorder) + b"\0".join(s.encode() for s in strings) + b"\0"


# `ps -E` prints the environment after the command, each variable after a space, so a value holding a space and
# then a name and "=" read as two variables: a folder named "r3 owner=demo" gave ALLOWED_FILE_DIRS=/srv/r3 and a
# variable `owner`, and the outbox line failed though the connector had been started to read it.
AWKWARD_DIRS = "/srv/r3 owner=demo/outbox:/srv/with space/reports"


def test_the_environment_macos_keeps_for_a_process_is_read_whole_and_a_hidden_one_is_nothing(tmp_path):
    argv = ["/opt/tools/uvx", "workspace-mcp", "--single-user", "NOT_A_VARIABLE=1"]  # an argument is no variable
    env = ["PATH=/usr/bin:/bin", "WORKSPACE_MCP_PORT=8765", f"ALLOWED_FILE_DIRS={AWKWARD_DIRS}", "OAUTHLIB_INSECURE_TRANSPORT=1"]
    asked, no_proc = [], tmp_path / "no-proc"  # as on macOS, which has no /proc
    assert doctor.started_with("4242", lambda pid: asked.append(pid) or _procargs(argv, env), no_proc) == {
        "PATH": "/usr/bin:/bin", "WORKSPACE_MCP_PORT": "8765", "OAUTHLIB_INSECURE_TRANSPORT": "1",
        "ALLOWED_FILE_DIRS": AWKWARD_DIRS}
    assert asked == ["4242"]
    assert doctor.started_with("4242", lambda pid: b"", no_proc) == {}  # one of the system's own programs, or none
    assert doctor.started_with("4242", lambda pid: _procargs(argv, env, argc=40), no_proc) == {}  # fewer strings than counted

    def refused(pid):
        raise PermissionError("Operation not permitted")

    assert doctor.started_with("4242", refused, no_proc) == {}


def test_a_folder_named_with_a_space_and_an_equals_sign_is_the_one_the_connector_was_started_to_read(connector, tmp_path):
    _, unit, pid_file = connector
    outbox = Path(AWKWARD_DIRS.split(":")[0].replace("/srv", str(tmp_path), 1))
    _installed(outbox, unit, pid_file)
    env = ["WORKSPACE_MCP_PORT=8765", f"ALLOWED_FILE_DIRS={outbox}:/srv/x"]
    (tmp_path / "proc" / "4242").mkdir(parents=True)
    (tmp_path / "proc" / "4242" / "environ").write_bytes("\0".join(env).encode() + b"\0")
    for proc in (tmp_path / "no-proc", tmp_path / "proc"):  # macOS's record of the process, and Linux's /proc
        check = doctor.check_outbox(outbox, unit, pid_file,
                                    lambda pid: doctor.started_with(pid, lambda p: _procargs(["/bin/sh"], env), proc))
        assert check.status == "ok" and "started to read it" in check.detail, (proc, check)


@pytest.mark.skipif(sys.platform != "darwin" and not Path("/proc/self/environ").is_file(), reason="no record of it here")
def test_this_processs_own_environment_is_read_back():
    """A positive control on the system's own record: nothing is started, and this process reads itself."""
    read = doctor.started_with(str(os.getpid()))
    assert read and any(os.environ.get(name) == value for name, value in read.items()), sorted(read)


def test_the_environment_linux_keeps_under_proc_is_read_and_an_unreadable_one_is_nothing(tmp_path):
    (tmp_path / "4242").mkdir()
    (tmp_path / "4242" / "environ").write_bytes(b"PATH=/usr/bin:/bin\0WORKSPACE_MCP_PORT=8765\0"
                                                 b"ALLOWED_FILE_DIRS=/srv/with space/reports:/srv/synthesis/outbox\0")
    assert doctor.started_with("4242", _unread, tmp_path) == {
        "PATH": "/usr/bin:/bin", "WORKSPACE_MCP_PORT": "8765",
        "ALLOWED_FILE_DIRS": "/srv/with space/reports:/srv/synthesis/outbox"}
    (tmp_path / "4243").mkdir()  # a process whose environment this user may not read
    assert doctor.started_with("4243", _unread, tmp_path) == {}


def test_what_a_running_process_was_started_with_is_read_from_the_os(connector):
    """The one real read: a child of this test, started as the start script starts the server."""
    outbox = connector[0]
    _installed(*connector)
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), **PORT, "ALLOWED_FILE_DIRS": f"/srv/with space/reports:{outbox}"}
    child = subprocess.Popen([sys.executable, "-c", "import time; print('up', flush=True); time.sleep(60)"], env=env,
                             stdout=subprocess.PIPE, text=True)
    try:
        # Linux fills in what /proc shows of a new program's environment a moment after the start call returns: read
        # in that moment it is empty, which failed this test once on main (2026-11-12). The child's first line says
        # its program is running.
        assert child.stdout.readline().strip() == "up"
        seen = doctor.started_with(str(child.pid))
        connector[2].write_text(f"{child.pid}\n", encoding="utf-8")
        check = doctor.check_outbox(*connector)
    finally:
        child.kill()
        child.wait()
        child.stdout.close()
    assert seen.get("WORKSPACE_MCP_PORT") == "8765" and seen.get("ALLOWED_FILE_DIRS") == env["ALLOWED_FILE_DIRS"]
    assert check.status == "ok", check.detail
    stopped = doctor.check_outbox(*connector)
    assert stopped.status == "warn" and "cannot tell" in stopped.detail


@pytest.mark.parametrize("platform,unit,pid_file", [
    ("darwin", "Library/LaunchAgents/com.synthesis.workspace-mcp.plist", "Library/Logs/workspace-mcp/server.pid"),
    ("linux", ".config/systemd/user/workspace-mcp.service", ".local/state/workspace-mcp/server.pid"),
])
def test_the_doctor_looks_where_the_connectors_scripts_write(platform, unit, pid_file, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    for key in ("XDG_CONFIG_HOME", "XDG_STATE_HOME"):
        monkeypatch.delenv(key, raising=False)
    assert doctor.connector_files(platform) == (tmp_path / unit, tmp_path / pid_file)
    if platform == "linux":
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
        assert doctor.connector_files(platform) == (tmp_path / "config" / "systemd" / "user" / "workspace-mcp.service",
                                                    tmp_path / "state" / "workspace-mcp" / "server.pid")
    # the scripts' own words for those places, so the two cannot drift apart
    installer, starter = ((SCRIPTS / name).read_text(encoding="utf-8") for name in ("install-autostart.sh", "start.sh"))
    assert 'label="com.synthesis.workspace-mcp"' in installer and 'plist="$HOME/Library/LaunchAgents/$label.plist"' in installer
    assert 'unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"' in installer
    assert 'unit="$unit_dir/workspace-mcp.service"' in installer
    assert 'Darwin) STATE_DIR="$HOME/Library/Logs/workspace-mcp"' in starter and 'PID_FILE="$STATE_DIR/server.pid"' in starter
    assert 'Linux)  STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/workspace-mcp"' in starter
    assert "export WORKSPACE_MCP_PORT=" in starter and "export ALLOWED_FILE_DIRS" in starter  # what the doctor reads of it


def test_the_doctor_reports_the_outbox_on_this_machine(machine):
    """A machine with no connector owes nothing and stays healthy; one with a connector installed has it read."""
    def outbox_line():
        found = [c for c in doctor.run_checks(find=lambda name: None) if c.name == "outbox"]
        assert len(found) == 1, found
        return found[0]

    before = outbox_line()
    assert before.status == "info" and "~/.synthesis/v5/outbox" in before.detail
    unit, pid_file = doctor.connector_files()
    assert str(machine[0]) in str(unit) and str(machine[0]) in str(pid_file)  # the temporary home, never this machine's
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), **PORT, "ALLOWED_FILE_DIRS": str(paths.outbox())}
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], env=env)
    try:
        _installed(paths.outbox(), unit, pid_file, str(child.pid))
        after = outbox_line()
    finally:
        child.kill()
        child.wait()
    assert after.status == "ok" and "started to read it" in after.detail


# ---- the audit reference lists every check the doctor runs --------------------
# The conformance skill's audit reference says what each line of `synthesis doctor` means. Its list had fallen behind
# the checks: the config, the board's place, the sessions repos, Claude Code's transcripts, the outbox, the PR gate
# and the release comparison had no line. The names are read from doctor.py's own source, so a check added there
# with no line here fails this file.

AUDIT = ROOT / "skills" / "synthesis-agent-conformance" / "references" / "audit.md"


def check_names(source: str = "") -> dict:
    """{each name a check in doctor.py carries: the functions that build it}, read from its source. A name built
    with a value in it is written with the value's own name in angle brackets, `<harness> plugin`."""
    import ast
    tree, found = ast.parse(source or Path(doctor.__file__).read_text(encoding="utf-8")), {}

    def spelled(node) -> str:
        if isinstance(node, ast.JoinedStr):
            return "".join(part.value if isinstance(part, ast.Constant) else f"<{ast.unparse(part.value)}>" for part in node.values)
        assert isinstance(node, ast.Constant) and isinstance(node.value, str), ast.dump(node)  # a name this reader cannot follow
        return node.value

    for function in (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)):
        given = {t.id: n.value for n in ast.walk(function) if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Name)}
        for call in (n for n in ast.walk(function) if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "Check"):
            name = call.args[1]
            found.setdefault(spelled(given[name.id] if isinstance(name, ast.Name) else name), set()).add(function.name)
    return found


def audit_lines() -> dict:
    """{check name: the line that explains it}, from the list under the reference's doctor section: each item opens
    with the names it covers, in backticks, before its first colon."""
    section = AUDIT.read_text(encoding="utf-8").split("\n## Installed: what doctor checks\n", 1)[1].split("\n## ", 1)[0]
    items = [" ".join(item.split()) for item in re.split(r"\n- ", "\n" + section.split("\n- ", 1)[1])]
    return {name: item for item in items for name in re.findall(r"`([^`]+)`", item.split(": ", 1)[0])}


def test_the_audit_reference_has_a_line_for_every_check_the_doctor_runs_and_for_no_other():
    ran, lines = check_names(), audit_lines()
    assert len(ran) >= 28 and {"runtime", "outbox", "<harness> plugin", "<harness> package", "sessions repo <ws>"} <= set(ran)
    assert sorted(set(ran) - set(lines)) == [], "a check the doctor runs has no line in the audit reference"
    assert sorted(set(lines) - set(ran)) == [], "the audit reference has a line for a check the doctor does not run"
    assert all(len(line.split(": ", 1)[1].split()) >= 5 for line in lines.values())  # each line says what its check looks at
    # Each check function is one the doctor runs, and none builds a line the reader above cannot see.
    source = Path(doctor.__file__).read_text(encoding="utf-8")
    run = source[source.index("\ndef harness_checks("):source.index("\ndef _background(")] + source[source.index("\ndef run_checks("):]
    functions = set(re.findall(r"^def (check_\w+)\(", source, re.M))
    assert functions and all(f"{name}(" in run for name in functions), sorted(n for n in functions if f"{n}(" not in run)
    assert functions <= {name for builders in ran.values() for name in builders}


def test_a_check_added_to_the_doctor_without_its_line_fails_the_audit_test():
    """The test above is alive: a check built in any of the ways the doctor builds one is seen, and has no line."""
    source = Path(doctor.__file__).read_text(encoding="utf-8")
    added = source + ('\n\ndef check_one(home):\n    return Check("ok", "a new check", "fine")\n'
                      '\n\ndef check_two(kind):\n    name = f"{kind} thing"\n    return Check("warn", name, "look")\n')
    assert set(check_names(added)) - set(audit_lines()) == {"a new check", "<kind> thing"}


def test_the_audit_reference_says_what_the_newer_checks_look_at():
    lines = audit_lines()
    assert "outbox" in lines["codex board access"] and "state folder" in lines["codex board access"]
    assert "`ALLOWED_FILE_DIRS`" in lines["outbox"] and "auto-start" in lines["outbox"]
    assert "`--latest`" in lines["latest release"] and "`pr_gated`" in lines["pr gate"]
    assert "`cleanupPeriodDays`" in lines["claude transcripts"] and "`config.json`" in lines["config"]


def test_the_doctor_warns_while_something_a_test_set_up_is_still_in_place(tmp_path):
    """2026-11-12: a stopped test's leftovers stayed a day, with no list and nothing to say so. The list is written
    as each thing is made (the guardrails' teardown.py); the doctor reads it, and runs nothing it names."""
    listed, now = tmp_path / "teardown.jsonl", 1794600000.0
    assert doctor.check_teardown(listed, now).status == "ok"
    listed.write_text("", encoding="utf-8")
    assert doctor.check_teardown(listed, now) == doctor.Check("ok", "teardown", "nothing a test set up is left in place")

    def item(number, what, hours):
        at = datetime.fromtimestamp(now - hours * 3600).astimezone().isoformat(timespec="seconds")
        return json.dumps({"id": number, "what": what, "remove": f"remove {what}", "test": "connector test", "at": at})
    listed.write_text(item(1, "an entry", 30) + "\n" + item(2, "a key", 2) + "\n", encoding="utf-8")
    found = doctor.check_teardown(listed, now)
    assert found.status == "warn" and found.name == "teardown"
    assert "2 things" in found.detail and "30 hours" in found.detail
    assert "1: an entry (remove an entry)" in found.detail and "2: a key (remove a key)" in found.detail and "teardown.py done" in found.detail
    listed.write_text("".join(item(n, f"thing {n}", n) + "\n" for n in range(1, 6)) + "a line by hand\n", encoding="utf-8")
    found = doctor.check_teardown(listed, now)
    assert "5 things" in found.detail and "5: thing 5" in found.detail and "3: thing 3" in found.detail     # the oldest three,
    assert "2: thing 2" not in found.detail and "and 2 more" in found.detail                                 # how many more,
    assert "1 line that is no item" in found.detail and "a line by hand" not in found.detail                 # and what else the file holds
    listed.write_text(item(1, "an entry", 0.5) + "\n", encoding="utf-8")
    assert "1 thing " in doctor.check_teardown(listed, now).detail and "under an hour" in doctor.check_teardown(listed, now).detail
    listed.unlink()
    listed.mkdir()
    assert doctor.check_teardown(listed, now).status == "warn"                                               # a list that cannot be read is said


def test_the_doctor_reads_a_teardown_list_whatever_it_holds(tmp_path):
    """A review, 2026-11-13: one byte that is not UTF-8 in the list ended `synthesis doctor` in a traceback, and
    every other check with it. Also from that round: a line of data that is no item was counted as a thing a test
    set up, a list of undated lines was said to be under an hour old, one hour was written "1 hours", and what a
    line held was printed as it stood, escape sequences and all."""
    listed, now = tmp_path / "teardown.jsonl", 1794600000.0

    def item(number, what, hours, **more):
        at = datetime.fromtimestamp(now - hours * 3600).astimezone().isoformat(timespec="seconds")
        return json.dumps({"id": number, "what": what, "remove": f"remove {what}", "test": "t", "at": at, **more})
    listed.write_bytes(b"\xff\xfe saved in another encoding\n" + item(1, "an entry", 1.2).encode() + b"\n")
    found = doctor.check_teardown(listed, now)
    assert found.status == "warn" and "1 thing " in found.detail and "for 1 hour:" in found.detail and "1: an entry" in found.detail
    assert "1 line that is no item" in found.detail
    listed.write_bytes(b"\xef\xbb\xbf" + item(1, "an entry", 3).encode() + b"\n   \n")
    assert "1 thing " in doctor.check_teardown(listed, now).detail and "no item" not in doctor.check_teardown(listed, now).detail
    listed.write_text('[1]\nnull\n5\n{"id": true, "what": "x", "remove": "y"}\nremember the record\n', encoding="utf-8")
    found = doctor.check_teardown(listed, now)
    assert found.status == "warn" and "thing" not in found.detail and "5 lines" in found.detail and "no item" in found.detail
    assert "hour" not in found.detail and "edit" in found.detail
    listed.write_text('{"id": 4, "what": "an entry", "remove": "delete it"}\n', encoding="utf-8")       # an item with no time
    found = doctor.check_teardown(listed, now)
    assert "1 thing a test set up is still in place: 4: an entry (delete it)" in found.detail and "hour" not in found.detail
    listed.write_text(item(1, "an entry", 30) + "\n" + item(2, "a key", 2) + "\n" + json.dumps({"done": 1, "at": "x"}) + "\n", encoding="utf-8")
    found = doctor.check_teardown(listed, now)
    assert "1 thing " in found.detail and "2: a key" in found.detail and "an entry" not in found.detail and "for 2 hours" in found.detail
    listed.write_text(item(1, "an entry", 30) + "\n" + json.dumps({"done": 1, "at": "x"}) + "\n", encoding="utf-8")
    assert doctor.check_teardown(listed, now) == doctor.Check("ok", "teardown", "nothing a test set up is left in place")
    listed.write_text(item(1, "an \x1b]52;c;eA==\x07entry", 3, remove="delete\x1b[2J it") + "\n", encoding="utf-8")
    found = doctor.check_teardown(listed, now)
    assert "\x1b" not in found.detail and "\x07" not in found.detail and "1: an ?]52;c;eA==?entry" in found.detail
    listed.write_text(item(1, "w" * 900, 3) + "\n", encoding="utf-8")
    assert len(doctor.check_teardown(listed, now).detail) < 600                                              # one long line does not fill the screen
    listed.unlink()
    listed.symlink_to(tmp_path / "gone")
    assert doctor.check_teardown(listed, now).status == "warn" and "cannot be read" in doctor.check_teardown(listed, now).detail


# Records that leave this Mac, part 2 (plan item 13.5, 5.19.0). The audit of 2026-11-11 (gap 4): nothing counted
# the records a seat claimed and left uncommitted, or committed and never pushed, so they left the Mac with nothing.

def _git(repo, *args, env=None):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True,
                          env={**os.environ, **(env or {})}).stdout


def _aged(path: Path, hours: float) -> None:
    when = time.time() - hours * 3600
    os.utime(path, (when, when))


def _records(tmp_path: Path) -> Path:
    """A knowledge repo pushed to a remote, then: a commit two days old no remote holds, an edit and a new file 30
    hours old, a new file of this hour, all in notes/; and a 30-hour-old file in other/, under no claim."""
    remote, repo = tmp_path / "remote.git", tmp_path / "records"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    (repo / "notes").mkdir(parents=True)
    (repo / "other").mkdir()
    _git(tmp_path, "init", "-q", "-b", "main", str(repo))
    (repo / "notes" / "a.md").write_text("a\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "first")
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "push", "-q", "-u", "origin", "main")
    (repo / "notes" / "b.md").write_text("b\n", encoding="utf-8")
    _git(repo, "add", ".")
    two_days = datetime.fromtimestamp(time.time() - 48 * 3600).astimezone().isoformat()
    _git(repo, "commit", "-q", "-m", "second", env={"GIT_AUTHOR_DATE": two_days, "GIT_COMMITTER_DATE": two_days})
    _aged(repo / "notes" / "b.md", 48)
    for rel, text in (("notes/a.md", "a, edited\n"), ("notes/new.md", "new\n"), ("other/old.md", "old\n")):
        (repo / rel).write_text(text, encoding="utf-8")
        _aged(repo / rel, 30)
    (repo / "notes" / "fresh.md").write_text("fresh\n", encoding="utf-8")
    return repo


def test_records_a_claim_left_unsaved_past_the_hours_are_counted_per_repository(tmp_path):
    from synthesis import board
    repo = _records(tmp_path)
    board.claim("S1", [str(repo / "notes")], project="alpha")
    claims = [c for s in board.sessions() for c in s.claims]
    found = doctor.unsaved(claims, 24)
    files, oldest, uncommitted, unpushed = found[os.path.realpath(repo)]
    assert (files, round(oldest), uncommitted, unpushed) == (3, 48, 2, 1) and len(found) == 1  # a.md, new.md; b.md
    assert doctor.unsaved(claims, 72) == {}
    _git(repo, "remote", "remove", "origin")  # with no remote, what is pushed cannot be told: commits are not counted
    assert doctor.unsaved(claims, 24)[os.path.realpath(repo)][2:] == (2, 0)
    (repo / "notes" / "a.md").unlink()  # a deleted file is as old as the last change to its folder
    _aged(repo / "notes", 30)
    assert doctor.unsaved(claims, 24)[os.path.realpath(repo)][2] == 2


def test_the_doctor_warns_of_unsaved_records_never_fails_and_reads_its_hours_from_the_config(tmp_path, capsys):
    from synthesis import board
    repo = _records(tmp_path)
    board.claim("S1", [str(repo / "notes")], project="alpha")
    claims = [c for s in board.sessions() for c in s.claims]
    line = doctor.check_unsaved({}, claims)
    assert line.status == "warn" and "1 repository holds claimed records unsaved past 24 h" in line.detail
    assert "3 file(s), the oldest 48 h (2 uncommitted, 1 in commits no remote holds)" in line.detail
    assert doctor.check_unsaved({"unsaved_hours": 72}, claims).status == "ok"
    assert doctor.check_unsaved({"unsaved_hours": False}, claims) == doctor.Check("ok", "unsaved records", "off (unsaved_hours is false)")
    for bad in ("24", 0, -1, True, None):
        line = doctor.check_unsaved({"unsaved_hours": bad}, claims)
        assert line.status == "warn" and "is not a number of hours above 0, so 24 is used" in line.detail, bad
    assert doctor.check_unsaved({}, []).status == "ok"
    assert doctor.main(["--unsaved"]) == 0 and capsys.readouterr().out == "1\n"
    assert [c.status for c in doctor.run_checks(find=lambda h: None) if c.name == "unsaved records"] == ["warn"]
    paths.config_file().parent.mkdir(parents=True, exist_ok=True)
    paths.config_file().write_text(json.dumps({"unsaved_hours": False}), encoding="utf-8")
    assert doctor.main(["--unsaved"]) == 0 and capsys.readouterr().out == "0\n"
    paths.config_file().write_text("{not json", encoding="utf-8")
    assert doctor.main(["--unsaved"]) == 0 and capsys.readouterr().out == "unknown\n"


def test_unsaved_reads_every_name_the_checkouts_branch_a_folder_removed_whole_and_fails_closed(tmp_path):
    """5.19.0's first review: M5 (a quoted name), m2 (a folder deleted whole), M9 (Finder's files are not records) and
    M6 (git that cannot read the checkout is said, never read as nothing). Its m1 (commits on every local branch) was
    taken back in 5.20.0: worktrees share one set of branches, so every claimed worktree was charged with every
    branch's commits, and on the principal's Mac the line named 54 repositories; a checkout's own branch is read."""
    from synthesis import board
    remote, repo = tmp_path / "r.git", tmp_path / "repo"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    subprocess.run(["git", "clone", "-q", str(remote), str(repo)], check=True, capture_output=True)
    (repo / "notes" / "sub").mkdir(parents=True)
    (repo / "notes" / "sub" / "x.md").write_text("x\n", encoding="utf-8")
    (repo / "notes" / "keep.md").write_text("keep\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "first")
    _git(repo, "push", "-q", "-u", "origin", "main")
    two_days = datetime.fromtimestamp(time.time() - 48 * 3600).astimezone().isoformat()
    dated = {"GIT_AUTHOR_DATE": two_days, "GIT_COMMITTER_DATE": two_days}
    (repo / "notes" / "café.md").write_text("accented\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "accented", env=dated)
    _git(repo, "checkout", "-q", "-b", "feature")
    (repo / "notes" / "f.md").write_text("on a branch\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "branch", env=dated)
    _git(repo, "checkout", "-q", "main")
    shutil.rmtree(repo / "notes" / "sub")  # a tracked file deleted with its folder
    (repo / "notes" / ".DS_Store").write_bytes(b"\x00")
    for path in (repo / "notes" / ".DS_Store", repo / "notes"):
        _aged(path, 30)
    board.claim("S1", [str(repo / "notes")], project="alpha")
    claims = [c for s in board.sessions() for c in s.claims]
    assert doctor.unsaved(claims, 24)[os.path.realpath(repo)][2:] == (1, 1)  # sub/x.md; café.md (f.md is on another branch)
    (repo / ".git" / "index").write_bytes(b"not an index")
    line = doctor.check_unsaved({}, claims)
    assert line.status == "warn" and "could not read" in line.detail


def test_unsaved_counts_live_seats_claims_alone(tmp_path, capsys):
    """5.20.0: on the principal's Mac the line named 54 repositories, most of them held by sessions gone quiet for
    days; their claims are the stale-claim review's (`synthesis who --all`). A live seat's unsaved record is counted."""
    from synthesis import board
    repo = _records(tmp_path)
    board.claim("S1", [str(repo / "notes")], project="alpha")
    quiet = board.load("S1")
    quiet.seen = time.time() - board.STALE_SECONDS - 1
    board.save(quiet)
    assert doctor.main(["--unsaved"]) == 0 and capsys.readouterr().out == "0\n"
    assert [c.status for c in doctor.run_checks(find=lambda h: None) if c.name == "unsaved records"] == ["ok"]
    board.touch("S1")
    assert doctor.main(["--unsaved"]) == 0 and capsys.readouterr().out == "1\n"

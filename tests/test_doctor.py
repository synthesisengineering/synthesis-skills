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
from pathlib import Path

import pytest

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

def fake_cli(bin_dir: Path, name: str, payload, skills=None) -> None:
    """A harness CLI that prints its listing; with `skills`, it also answers app-server skills/list."""
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
    assert snapshot(home) == before


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


def test_version_probe_is_bounded_closes_stdin_and_reaps(tmp_path):
    hung = _exe(tmp_path / "codex", "read line; sleep 30")
    start = time.monotonic()
    assert doctor._version_ok(str(hung), timeout=0.3) is False
    assert time.monotonic() - start < 5


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
    long = [_skill(tmp_path, "a", description="d" * 5000)]
    assert doctor.catalog_cost(long, None)[0] < 256 + 1100 // 4 + 40


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

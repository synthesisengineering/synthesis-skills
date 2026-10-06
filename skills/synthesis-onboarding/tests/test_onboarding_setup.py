"""setup.py: the plugin in each harness with its own commands, Codex's settings, the runtime,
prompts that reach the terminal, and uninstall. Every harness here is a fake CLI that logs."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import setup

PLUGIN_ID = "synthesis-skills@synthesis-engineering"


def fake_cli(tmp_path, name, responses):
    """A CLI that logs its argv and prints the first response whose key prefixes its arguments."""
    log, data = tmp_path / f"{name}.log", tmp_path / f"{name}.json"
    data.write_text(json.dumps(responses))
    script = tmp_path / "bin" / name
    script.parent.mkdir(exist_ok=True)
    script.write_text(f"""#!{sys.executable}
import json, sys
args = " ".join(sys.argv[1:])
open({str(log)!r}, "a").write(args + "\\n")
for key, (code, out) in json.load(open({str(data)!r})).items():
    if args.startswith(key):
        sys.stdout.write(out if isinstance(out, str) else json.dumps(out))
        sys.exit(code)
""")
    script.chmod(0o755)
    return str(script), log


def calls(log):
    return log.read_text().splitlines() if log.exists() else []


# ---- each harness's commands ----------------------------------------------------

def test_claude_update_refreshes_the_marketplace_then_the_plugin(tmp_path, monkeypatch):
    listing = [{"id": PLUGIN_ID, "version": "5.0.0", "enabled": True, "installPath": str(tmp_path)}]
    binary, log = fake_cli(tmp_path, "claude", {"plugin list": (0, listing), "plugin": (0, "")})
    monkeypatch.setattr(setup, "configured_ref", lambda client: "stable")
    assert "claude: updated synthesis-skills 5.0.0" == setup.install_plugin("claude", binary)
    assert calls(log)[1:3] == [f"plugin marketplace update synthesis-engineering", f"plugin update {PLUGIN_ID}"]


def test_codex_update_upgrades_the_snapshot_before_adding(tmp_path, monkeypatch):
    listing = {"installed": [{"pluginId": PLUGIN_ID, "name": "synthesis-skills", "version": "5.0.0",
                              "marketplaceName": "synthesis-engineering", "enabled": True}]}
    binary, log = fake_cli(tmp_path, "codex", {"plugin list": (0, listing), "plugin": (0, "{}")})
    monkeypatch.setattr(setup, "configured_ref", lambda client: "stable")
    setup.install_plugin("codex", binary)
    assert calls(log)[1:3] == ["plugin marketplace upgrade synthesis-engineering --json", f"plugin add {PLUGIN_ID}"]


def test_a_new_install_adds_the_marketplace_on_stable(tmp_path, monkeypatch):
    state = tmp_path / "installed"
    listing = [{"id": PLUGIN_ID, "version": "5.0.0", "enabled": True}]
    binary, log = fake_cli(tmp_path, "claude", {"plugin list": (0, []), "plugin": (0, "")})
    monkeypatch.setattr(setup, "configured_ref", lambda client: None)
    entries = iter([None, {"version": "5.0.0", "enabled": True}])
    monkeypatch.setattr(setup, "plugin_entry", lambda client, b: next(entries))
    assert setup.install_plugin("claude", binary).startswith("claude: installed synthesis-skills 5.0.0")
    assert calls(log) == ["plugin marketplace add synthesisengineering/synthesis-skills@stable",
                          f"plugin install {PLUGIN_ID}"]


def test_a_marketplace_on_another_ref_is_removed_and_added_again(tmp_path, monkeypatch):
    binary, log = fake_cli(tmp_path, "codex", {"plugin": (0, "{}")})
    monkeypatch.setattr(setup, "configured_ref", lambda client: "stable")
    monkeypatch.setattr(setup, "plugin_entry", lambda client, b: {"version": "5.0.0", "enabled": True})
    assert "moved to v5.0.0" in setup.install_plugin("codex", binary, ref="v5.0.0")
    assert calls(log) == ["plugin marketplace remove synthesis-engineering",
                          "plugin marketplace add synthesisengineering/synthesis-skills --ref v5.0.0 --json",
                          f"plugin add {PLUGIN_ID}"]


def test_an_already_added_marketplace_is_re_added(tmp_path, monkeypatch):
    binary, log = fake_cli(tmp_path, "claude", {"plugin marketplace add": (1, "marketplace already exists"),
                                                "plugin": (0, "")})
    monkeypatch.setattr(setup, "configured_ref", lambda client: None)
    entries = iter([None, {"version": "5.0.0", "enabled": True}])
    monkeypatch.setattr(setup, "plugin_entry", lambda client, b: next(entries))
    with pytest.raises(setup.SetupError):  # the fake keeps refusing the add, so the retry fails loudly
        setup.install_plugin("claude", binary)
    assert calls(log)[:3] == ["plugin marketplace add synthesisengineering/synthesis-skills@stable",
                              "plugin marketplace remove synthesis-engineering",
                              "plugin marketplace add synthesisengineering/synthesis-skills@stable"]


def test_without_an_explicit_ref_an_install_on_another_channel_is_never_moved(tmp_path, monkeypatch):
    binary, log = fake_cli(tmp_path, "claude", {"plugin": (0, "")})
    monkeypatch.setattr(setup, "configured_ref", lambda client: "main")
    monkeypatch.setattr(setup, "plugin_entry", lambda client, b: {"version": "5.2.0", "enabled": True})
    setup.install_plugin("claude", binary)
    assert not any("remove" in c or "add" in c for c in calls(log))


def test_plugin_list_shapes_and_text_output(tmp_path):
    claude_list, _ = fake_cli(tmp_path, "claude", {"plugin list": (0, {"plugins": [{"id": PLUGIN_ID, "version": "5"}]})})
    assert setup.plugin_entry("claude", claude_list)["version"] == "5"
    codex_text, _ = fake_cli(tmp_path, "codex", {"plugin list": (0, "synthesis-skills (enabled)\n")})
    with pytest.raises(setup.SetupError, match="no plugin list"):
        setup.plugin_entry("codex", codex_text)


def test_a_disabled_plugin_is_reported_not_silently_enabled(tmp_path, monkeypatch):
    binary, log = fake_cli(tmp_path, "claude", {"plugin": (0, "")})
    monkeypatch.setattr(setup, "configured_ref", lambda client: "stable")
    monkeypatch.setattr(setup, "plugin_entry", lambda client, b: {"version": "5.0.0", "enabled": False})
    assert "disabled" in setup.install_plugin("claude", binary)
    assert not any("enable" in c for c in calls(log))


def test_absent_harnesses_are_skipped_without_failing(monkeypatch):
    monkeypatch.setattr(setup.doctor, "find_client", lambda name: None)
    lines, failed = setup.setup_plugins(["claude", "codex", "muse"], "", False)
    assert not failed and all("not found on this Mac; skipped" in line for line in lines)


def test_dry_run_runs_no_harness_command(tmp_path, monkeypatch):
    binary, log = fake_cli(tmp_path, "claude", {"plugin": (0, "")})
    monkeypatch.setattr(setup, "configured_ref", lambda client: None)
    monkeypatch.setattr(setup, "plugin_entry", lambda client, b: None)
    assert setup.install_plugin("claude", binary, dry_run=True).startswith("claude: would run")
    assert calls(log) == []


# ---- Muse: a local bundle with an absolute recorded path, then update -------------

MUSE_HELP = "usage: muse plugins <command>\n\nCommands:\n  install <path>\n  list [--json]\n  update <id>\n"


def _repo(tmp_path):
    repo = tmp_path / "source"
    (repo / "skills" / "demo").mkdir(parents=True)
    (repo / "skills" / "demo" / "SKILL.md").write_text("---\nname: demo\n---\n")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "x"], check=True)
    return repo


def test_muse_first_install_stages_a_bundle_and_later_runs_update(tmp_path, monkeypatch):
    repo, bundle = _repo(tmp_path), setup.install._home() / "muse-bundle"
    binary, log = fake_cli(tmp_path, "muse", {"plugins --help": (0, MUSE_HELP),
                                              "plugins list": (0, {"plugins": []}), "plugins": (0, "{}")})
    assert "installed" in setup.install_muse(binary, repo)
    assert (bundle / "skills" / "demo" / "SKILL.md").is_file() and bundle.is_absolute()
    assert calls(log)[-1] == f"plugins install {bundle} --json"
    record = {"plugins": [{"record": {"id": "synthesis-skills", "source": {"path": str(bundle)}}}]}
    fake_cli(tmp_path, "muse", {"plugins --help": (0, MUSE_HELP), "plugins list": (0, record), "plugins": (0, "{}")})
    (repo / "skills" / "demo" / "SKILL.md").write_text("---\nname: demo\nchanged\n---\n")
    subprocess.run(["git", "-C", str(repo), "commit", "-qam", "y"], check=True)
    assert "updated" in setup.install_muse(binary, repo)
    assert calls(log)[-1] == "plugins update synthesis-skills --json"
    assert "changed" in (bundle / "skills" / "demo" / "SKILL.md").read_text()


def test_muse_without_plugin_commands_is_refused_before_staging(tmp_path):
    binary, log = fake_cli(tmp_path, "muse", {"plugins --help": (0, "usage: muse [COMMAND]\nCommands:\n  exec\n")})
    with pytest.raises(setup.SetupError, match="lacks list, install or update"):
        setup.install_muse(binary, _repo(tmp_path))
    assert not (setup.install._home() / "muse-bundle").exists()


def test_muse_record_from_a_foreign_or_relative_path_is_refused(tmp_path):
    for path, message in (("relative/bundle", "not absolute"), ("/opt/elsewhere", "does not own")):
        record = {"plugins": [{"record": {"id": "synthesis-skills", "source": {"path": path}}}]}
        binary, _ = fake_cli(tmp_path, "muse", {"plugins --help": (0, MUSE_HELP), "plugins list": (0, record)})
        with pytest.raises(setup.SetupError, match=message):
            setup.install_muse(binary, _repo(tmp_path) if not (tmp_path / "source").exists() else tmp_path / "source")


def test_an_unreadable_muse_inventory_is_not_taken_for_absence(tmp_path):
    binary, _ = fake_cli(tmp_path, "muse", {"plugins --help": (0, MUSE_HELP), "plugins list": (0, "garbage")})
    with pytest.raises(setup.SetupError, match="unreadable"):
        setup.install_muse(binary, tmp_path)


# ---- Codex settings ----------------------------------------------------------

def test_overlay_sets_only_the_owned_keys():
    text = 'model = "gpt-6"\n\n[features]\njs_repl = true\n\n[mcp_servers.x]\ncommand = "y"\n'
    new, notes = setup.codex_overlay(text)
    config = setup.doctor.read_toml(new)
    assert config["features"] == {"js_repl": True, "hooks": True}
    assert config["project_doc_max_bytes"] == 98304 and config["project_doc_fallback_filenames"].startswith("[")
    assert config["model"] == "gpt-6" and config["mcp_servers"]["x"]["command"] == "y"
    assert setup.HOOKS_BEGIN in new and len(notes) == 3
    assert setup.codex_overlay(new) == (new, [])  # a rerun changes nothing


def test_overlay_keeps_an_explicit_hooks_false_and_says_guards_will_not_run():
    new, notes = setup.codex_overlay("project_doc_max_bytes = 120000\nproject_doc_fallback_filenames = [\"CLAUDE.md\"]\n"
                                     "[features]\nhooks = false\n")
    assert "hooks = false" in new and "hooks = true" not in new
    assert notes == ["kept [features] hooks = false, so no synthesis guard runs in Codex"]


def test_overlay_raises_a_low_instruction_limit_and_adds_a_features_table():
    new, _ = setup.codex_overlay("project_doc_max_bytes = 32768 # mine\n")
    config = setup.doctor.read_toml(new)
    assert config["project_doc_max_bytes"] == 98304 and config["features"]["hooks"] is True


def test_overlay_reports_a_fallback_list_without_claude_md_but_leaves_it():
    new, notes = setup.codex_overlay('project_doc_fallback_filenames = ["README.md"]\n')
    assert '["README.md"]' in new and any("lacks CLAUDE.md" in n for n in notes)


def test_configure_codex_backs_up_before_writing(tmp_path, monkeypatch):
    codex = tmp_path / "codex"
    codex.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(codex))
    (codex / "config.toml").write_text("[features]\nother = 1\n")
    lines = setup.configure_codex()
    backups = list((setup.install._home() / "backups").glob("codex-config.toml.*"))
    assert len(backups) == 1 and backups[0].read_text() == "[features]\nother = 1\n"
    assert any("backed up" in line for line in lines)
    assert setup.configure_codex() == ["codex config: already set"]


# ---- runtime, prompts, interruption and the restart line -------------------------

def test_runtime_installs_and_links_the_cli_only_when_the_name_is_free(tmp_path):
    lines = setup.install_runtime(git_hooks=False)
    assert lines[0].startswith("synthesis runtime") and any("linked" in line for line in lines)
    assert setup.install_runtime(git_hooks=False)[1:] == []
    link = Path.home() / ".local" / "bin" / "synthesis"
    link.unlink()
    link.write_text("#!/bin/sh\n# another launcher\n")
    assert any("belongs to another install" in line for line in setup.install_runtime(git_hooks=False))
    assert link.read_text().endswith("another launcher\n")


def test_runtime_archives_the_4x_command_and_links_its_own(tmp_path):
    """A 4.x install left a managed `synthesis` file on PATH that drove the retired board; setup replaces it."""
    link = Path.home() / ".local" / "bin" / "synthesis"
    link.parent.mkdir(parents=True, exist_ok=True)
    link.write_text("#!/usr/bin/python3 -BIS\n# generated by synthesis-onboarding; managed file\n")
    lines = setup.install_runtime(git_hooks=False)
    archived = [line for line in lines if line.startswith("archived the 4.x synthesis command to ")]
    assert archived and any("linked" in line for line in lines) and link.is_symlink()
    assert (Path(archived[0].rsplit(" ", 1)[1]) / "synthesis").read_text().startswith("#!/usr/bin/python3")


def test_first_config_interview_only_for_a_fresh_config(monkeypatch):
    setup.install.install(setup.REPO)
    answers = iter(["~/workspaces/demo/ai-knowledge-demo", "secret plan"])
    monkeypatch.setattr(setup, "ask", lambda *a, **k: next(answers))
    setup.first_config(interactive=True)
    config = json.loads((setup.install._home() / "config.json").read_text())
    assert config["knowledge_roots"] == ["~/workspaces/demo/ai-knowledge-demo"]
    assert config["forbidden_phrases"][0]["pattern"] == "secret\\ plan"
    assert "approval" in setup.first_config(interactive=True)[0]  # a second run asks nothing


def test_questions_without_a_terminal_name_the_flag(monkeypatch):
    monkeypatch.setattr(setup, "_terminal", lambda: (None, False))
    with pytest.raises(setup.SetupError, match="pass --kb URL"):
        setup.ask("Knowledge repository", "--kb URL")


def test_questions_read_the_terminal_when_stdin_is_a_pipe(tmp_path, monkeypatch):
    tty = tmp_path / "tty"
    tty.write_text("2\n")
    monkeypatch.setattr(setup, "_terminal", lambda: (open(tty), True))
    assert setup.choose("Which?", ["a", "b"], "--x") == "b"


def test_interrupt_prints_a_resume_line(monkeypatch, capsys):
    def interrupted(*a):
        raise KeyboardInterrupt
    monkeypatch.setattr(setup, "setup_plugins", interrupted)
    assert setup.main(["plugin", "--no-input"]) == 130
    assert "run the same command again to resume" in capsys.readouterr().err


def test_plugin_command_prints_the_restart_sentence(monkeypatch, capsys):
    monkeypatch.setattr(setup.doctor, "find_client", lambda name: None)
    assert setup.main(["plugin", "--no-input", "--clients", "claude"]) == 0
    out = capsys.readouterr().out
    assert "claude: not found" in out and out.strip().endswith(setup.RESTART)


def test_uninstall_removes_the_plugin_with_each_harness_command(tmp_path, monkeypatch, capsys):
    claude, log = fake_cli(tmp_path, "claude", {"plugin list": (0, [{"id": PLUGIN_ID, "version": "5"}]), "plugin": (0, "")})
    monkeypatch.setattr(setup.doctor, "find_client", lambda name: claude if name == "claude" else None)
    setup.install.install(setup.REPO)
    assert setup.main(["uninstall", "--clients", "claude,codex"]) == 0
    out = capsys.readouterr().out
    assert f"plugin uninstall {PLUGIN_ID} --yes" in calls(log)
    assert "claude: removed" in out and "codex: synthesis-skills not installed" in out and "kept" in out


# ---- the day-end launcher and nudge ---------------------------------------------

@pytest.fixture
def day_end(tmp_path, monkeypatch):
    """The runtime installed with the day-end copies, and launchctl replaced by a logging fake."""
    import shutil
    plugin = tmp_path / "plugin"
    shutil.copytree(setup.REPO / "synthesis", plugin / "synthesis", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(setup.REPO / "skills" / "synthesis-daily-rituals" / "scripts",
                    plugin / "skills" / "synthesis-daily-rituals" / "scripts", ignore=shutil.ignore_patterns("*.py"))
    setup.install.install(plugin)
    launchctl, log = fake_cli(tmp_path, "launchctl", {"bootout": (3, "not loaded"), "bootstrap": (0, "")})
    monkeypatch.setattr(setup, "LAUNCHCTL", launchctl)
    return log


def test_day_end_links_the_launcher_and_schedules_the_installed_nudge(day_end):
    import plistlib
    lines = setup.register_day_end("codex")
    home = setup.install._home()
    link = Path.home() / ".local" / "bin" / "day-end"
    assert os.readlink(link) == str(home / "bin" / "day-end") and (home / "agent-cli").read_text() == "codex\n"
    spec = plistlib.loads(setup._nudge_plist().read_bytes())
    assert str(home / "bin" / "day-end-nudge.sh") in spec["ProgramArguments"][-1]
    assert spec["Label"] == "com.synthesis.day-end-nudge" and len(spec["StartCalendarInterval"]) == 5
    assert calls(day_end)[-1].startswith("bootstrap gui/") and any("16:55" in line for line in lines)


def test_day_end_refuses_to_replace_a_real_file(day_end):
    link = Path.home() / ".local" / "bin" / "day-end"
    link.parent.mkdir(parents=True)
    link.write_text("#!/bin/sh\n# mine\n")
    with pytest.raises(setup.SetupError, match="refusing to replace"):
        setup.register_day_end()
    assert link.read_text().endswith("# mine\n") and not setup._nudge_plist().exists()


def test_day_end_without_launchctl_writes_but_does_not_load(day_end):
    setup.register_day_end(load=False)
    assert setup._nudge_plist().exists() and calls(day_end) == []


def test_an_older_schedule_is_archived_before_it_is_replaced(day_end):
    plist = setup._nudge_plist()
    plist.parent.mkdir(parents=True)
    plist.write_text("<plist><dict><key>ProgramArguments</key><array><string>/old/nudge.sh</string></array></dict></plist>")
    lines = setup.register_day_end(load=False)
    assert any("archived the previous nudge schedule" in line for line in lines)
    assert list((setup.install._home() / "archive").glob("*/com.synthesis.day-end-nudge.plist"))


def test_uninstall_removes_only_a_schedule_and_link_that_point_at_this_install(day_end):
    setup.register_day_end(load=False)
    assert any("removed the nudge schedule" in line for line in setup.unregister_day_end())
    assert not setup._nudge_plist().exists() and not os.path.lexists(Path.home() / ".local" / "bin" / "day-end")
    assert calls(day_end)[-1].startswith("bootout gui/")
    plist, link = setup._nudge_plist(), Path.home() / ".local" / "bin" / "day-end"
    plist.write_text("<plist><dict><key>ProgramArguments</key><array><string>/other/nudge.sh</string></array></dict></plist>")
    link.symlink_to("/other/day-end")
    lines = setup.unregister_day_end()
    assert plist.exists() and link.is_symlink() and len([l for l in lines if l.startswith("kept")]) == 2


def test_day_end_before_install_says_what_to_run_first():
    with pytest.raises(setup.SetupError, match="not installed"):
        setup.register_day_end()

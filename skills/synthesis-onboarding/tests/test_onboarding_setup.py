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
    assert calls(log)[1:3] == ["plugin marketplace update synthesis-engineering", f"plugin update {PLUGIN_ID}"]


def test_codex_update_upgrades_the_snapshot_before_adding(tmp_path, monkeypatch):
    listing = {"installed": [{"pluginId": PLUGIN_ID, "name": "synthesis-skills", "version": "5.0.0",
                              "marketplaceName": "synthesis-engineering", "enabled": True}]}
    binary, log = fake_cli(tmp_path, "codex", {"plugin list": (0, listing), "plugin": (0, "{}")})
    monkeypatch.setattr(setup, "configured_ref", lambda client: "stable")
    setup.install_plugin("codex", binary)
    assert calls(log)[1:3] == ["plugin marketplace upgrade synthesis-engineering --json", f"plugin add {PLUGIN_ID}"]


def test_a_new_install_adds_the_marketplace_on_stable(tmp_path, monkeypatch):
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


CODEX_ENTRY = {"pluginId": PLUGIN_ID, "name": "synthesis-skills", "version": "5.0.0", "marketplaceName": "synthesis-engineering", "enabled": True}
LIMITED, WHOLE = "plugin list --json -m synthesis-engineering", "plugin list --json"
EMPTY = {"installed": [], "available": []}


def test_codex_is_asked_for_the_plugins_marketplace_first(tmp_path):
    """Codex's whole listing fetches its remote catalog again when its copy is over three hours old (52 s on
    2026-11-13, against the 60 this command had). Asked for one marketplace it fetches none, so an update, which is
    every release, never waits on the catalog."""
    binary, log = fake_cli(tmp_path, "codex", {LIMITED: (0, {"installed": [CODEX_ENTRY], "available": []}), "plugin list": (0, {"installed": []})})
    assert setup.plugin_entry("codex", binary)["version"] == "5.0.0"
    assert calls(log) == [LIMITED]


def test_absent_is_said_only_from_the_whole_listing(tmp_path):
    binary, log = fake_cli(tmp_path, "codex", {"plugin list": (0, EMPTY)})
    assert setup.plugin_entry("codex", binary) is None
    assert calls(log) == [LIMITED, WHOLE]


def test_a_plugin_installed_from_another_marketplace_is_not_installed_a_second_time(tmp_path, monkeypatch, capsys):
    """A review, 2026-11-13: asked for its own marketplace alone, the installer called a plugin installed from a
    fork absent, and its plan was to add a second copy beside it. It refuses and names the copy; uninstall removes
    the copy that is there, by the name the listing gives it."""
    fork = {**CODEX_ENTRY, "pluginId": "synthesis-skills@a-fork", "marketplaceName": "a-fork"}
    binary, log = fake_cli(tmp_path, "codex", {LIMITED: (0, EMPTY), "plugin list": (0, {"installed": [fork]}), "plugin": (0, "{}")})
    assert setup.plugin_entry("codex", binary)["id"] == "synthesis-skills@a-fork"
    monkeypatch.setattr(setup, "configured_ref", lambda client: None)
    with pytest.raises(setup.SetupError, match="synthesis-skills@a-fork") as refused:
        setup.install_plugin("codex", binary)
    assert "codex plugin remove synthesis-skills@a-fork" in str(refused.value)
    assert calls(log) == [LIMITED, WHOLE] * 2                                    # no marketplace added, no plugin added
    monkeypatch.setattr(setup.doctor, "find_client", lambda name: binary if name == "codex" else None)
    setup.install.install(setup.REPO)
    assert setup.main(["uninstall", "--clients", "codex"]) == 0
    assert "plugin remove synthesis-skills@a-fork --json" in calls(log) and "codex: removed" in capsys.readouterr().out


def test_a_codex_that_does_not_know_the_option_is_asked_for_the_whole_listing(tmp_path):
    binary, log = fake_cli(tmp_path, "codex", {"plugin list --json -m": (2, "error: unexpected argument '-m' found"),
                                               "plugin list": (0, {"installed": [CODEX_ENTRY]})})
    assert setup.plugin_entry("codex", binary)["version"] == "5.0.0"
    assert calls(log) == [LIMITED, WHOLE]


def test_a_listing_that_does_not_answer_stops_the_install_and_is_not_asked_again(tmp_path, monkeypatch):
    """A listing past its limit says nothing: the whole listing, the one that fetches, is not started after it."""
    binary, log = fake_cli(tmp_path, "codex", {"plugin list": (0, {"installed": [CODEX_ENTRY]})})
    script = Path(binary)
    script.write_text(script.read_text().replace("import json, sys\n", "import json, sys, time\n", 1).replace(
        "for key, (code, out) in", "if '-m' in sys.argv:\n    time.sleep(30)\nfor key, (code, out) in", 1))
    monkeypatch.setattr(setup, "LIST_TIMEOUT", 1)
    with pytest.raises(setup.SetupError, match="did not answer within 1 s"):
        setup.plugin_entry("codex", binary)
    assert calls(log) == [LIMITED]


def test_a_listing_that_fails_is_reported_with_what_the_harness_said(tmp_path):
    binary, _ = fake_cli(tmp_path, "codex", {"plugin list": (1, "error: marketplace snapshot is missing")})
    with pytest.raises(setup.SetupError, match="no plugin list.*marketplace snapshot is missing"):
        setup.plugin_entry("codex", binary)


def test_claude_is_asked_as_before(tmp_path):
    binary, log = fake_cli(tmp_path, "claude", {"plugin list": (0, [{"id": PLUGIN_ID, "version": "5"}])})
    assert setup.plugin_entry("claude", binary)["version"] == "5"
    assert calls(log) == ["plugin list --json"]


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
    assert setup.HOOKS_BEGIN in new and setup.BOARD_BEGIN in new and len(notes) == 5
    assert config["default_permissions"] == "synthesis" and config["permissions"]["synthesis"] == {
        "extends": ":workspace", "filesystem": {str(setup.paths.board()): "write", str(setup.paths.outbox()): "write"}}
    assert setup.codex_overlay(new) == (new, [])  # a rerun changes nothing


def test_overlay_keeps_an_explicit_hooks_false_and_says_guards_will_not_run():
    new, notes = setup.codex_overlay("project_doc_max_bytes = 120000\nproject_doc_fallback_filenames = [\"CLAUDE.md\"]\n"
                                     "[features]\nhooks = false\n")
    assert "hooks = false" in new and "hooks = true" not in new
    assert notes[0] == "kept [features] hooks = false, so no synthesis guard runs in Codex"
    assert len(notes) == 3 and "synthesis board" in notes[1] and "synthesis outbox" in notes[2]


def test_overlay_raises_a_low_instruction_limit_and_adds_a_features_table():
    new, _ = setup.codex_overlay("project_doc_max_bytes = 32768 # mine\n")
    config = setup.doctor.read_toml(new)
    assert config["project_doc_max_bytes"] == 98304 and config["features"]["hooks"] is True


def test_overlay_reports_a_fallback_list_without_claude_md_but_leaves_it():
    new, notes = setup.codex_overlay('project_doc_fallback_filenames = ["README.md"]\n')
    assert '["README.md"]' in new and any("lacks CLAUDE.md" in n for n in notes)


def test_overlay_grants_the_board_and_the_outbox_through_the_settings_codex_reads():
    """2026-10-30: Codex's sandbox could not write the board, so Codex sessions could not claim or post. Codex reads
    permission profiles unless `sandbox_mode` is set, and then the older [sandbox_workspace_write]. The outbox is
    granted the same way (2026-11-12: a Codex session could not stage a file it attaches). Only those two are
    granted either way: the state folder holds approvals and send windows, which no sandboxed agent may write."""
    board, state, outbox = setup.paths.board(), setup.paths.state(), setup.paths.outbox()
    keep = 'project_doc_max_bytes = 98304\nproject_doc_fallback_filenames = ["CLAUDE.md"]\n[features]\nhooks = true\n'
    mine = 'default_permissions = "mine"\n' + keep + '[permissions.mine]\nextends = ":workspace"\n'
    legacy = 'sandbox_mode = "workspace-write"\n'
    for given, profile, base in (("", "synthesis", ":workspace"),
                                 ('default_permissions = ":read-only"\n', "synthesis", ":read-only"),
                                 (mine, "mine", ":workspace"),
                                 (mine + '[permissions.mine.filesystem]\n"~/cache" = "write"\n', "mine", ":workspace"),
                                 (legacy + keep + '[sandbox_workspace_write]\nwritable_roots = ["/opt/cache"] # mine\n', "", ""),
                                 (legacy + keep + '[sandbox_workspace_write]\nwritable_roots = [\n  "/opt/cache",\n]\n', "", ""),
                                 (legacy + 'sandbox_workspace_write.network_access = true\n' + keep, "", ""),
                                 (legacy + keep, "", "")):
        new, notes = setup.codex_overlay(given if keep in given else given + keep)
        config = setup.doctor.read_toml(new)
        assert setup.doctor.check_codex_board(config, board, state, outbox).status == "ok", given
        assert [str(folder) in note for folder, note in zip((board, outbox), notes)] == [True, True], notes
        assert len(notes) == 2 and setup.codex_overlay(new) == (new, []), given
        assert new.count(json.dumps(str(board))) == 1 and new.count(json.dumps(str(outbox))) == 1, given
        if profile:
            assert config["default_permissions"] == profile and config["permissions"][profile]["extends"] == base, given
        else:
            assert "default_permissions" not in config and ("/opt/cache" in new) == ("/opt/cache" in given), given
    for unsandboxed in ('sandbox_mode = "danger-full-access"\n' + keep, 'default_permissions = ":danger-full-access"\n' + keep):
        assert setup.codex_overlay(unsandboxed) == (unsandboxed, []), unsandboxed
    inline = mine + 'filesystem = { "~/x" = "read" }\n'
    new, notes = setup.codex_overlay(inline)
    assert new == inline and "form setup does not edit" in notes[0] and str(board) in notes[0]
    assert len(notes) == 2 and "form setup does not edit" in notes[1] and str(outbox) in notes[1]


def test_an_install_that_granted_the_board_alone_gains_the_outbox_and_writes_the_board_no_second_time():
    """What an earlier setup wrote grants the board and nothing else. The next run adds the outbox to the same
    profile, or the same writable roots, and leaves the board's rule as it is."""
    board, state, outbox = setup.paths.board(), setup.paths.state(), setup.paths.outbox()
    keep = 'project_doc_max_bytes = 98304\nproject_doc_fallback_filenames = ["CLAUDE.md"]\n[features]\nhooks = true\n'
    profile = ('default_permissions = "synthesis"  # synthesis setup: :workspace plus the board\n\n' + keep
               + f'\n{setup.BOARD_BEGIN}\n[permissions.synthesis]\nextends = ":workspace"\n'
               f'[permissions.synthesis.filesystem]\n{json.dumps(str(board))} = "write"\n{setup.BOARD_END}\n')
    legacy = ('sandbox_mode = "workspace-write"\n' + keep + f'\n{setup.BOARD_BEGIN}\n[sandbox_workspace_write]\n'
              f'writable_roots = [{json.dumps(str(board))}]\n{setup.BOARD_END}\n')
    for earlier in (profile, legacy):
        lacking = setup.doctor.check_codex_board(setup.doctor.read_toml(earlier), board, state, outbox)
        assert lacking.status == "fail" and setup.doctor._short(outbox) in lacking.detail, earlier
        new, notes = setup.codex_overlay(earlier)
        assert len(notes) == 1 and "synthesis outbox" in notes[0] and str(outbox) in notes[0], notes
        assert new.count(json.dumps(str(board))) == 1 and new.count(json.dumps(str(outbox))) == 1, new
        assert setup.doctor.check_codex_board(setup.doctor.read_toml(new), board, state, outbox).status == "ok", new
        assert setup.codex_overlay(new) == (new, [])


def test_a_folder_the_person_granted_themselves_is_not_granted_again():
    board, state, outbox = setup.paths.board(), setup.paths.state(), setup.paths.outbox()
    mine = ('default_permissions = "mine"\nproject_doc_max_bytes = 98304\nproject_doc_fallback_filenames = ["CLAUDE.md"]\n'
            '[features]\nhooks = true\n[permissions.mine]\nextends = ":workspace"\n[permissions.mine.filesystem]\n'
            f'{json.dumps(str(outbox))} = "write"\n')
    new, notes = setup.codex_overlay(mine)
    assert len(notes) == 1 and "synthesis board" in notes[0] and new.count(json.dumps(str(outbox))) == 1
    assert setup.doctor.check_codex_board(setup.doctor.read_toml(new), board, state, outbox).status == "ok"
    assert setup.codex_overlay(new) == (new, [])


def test_claude_keeps_transcripts_ten_years_unless_the_person_chose_a_period(tmp_path, monkeypatch):
    """2026-10-30: Claude Code's 30-day default had been deleting this Mac's transcripts."""
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude"))
    settings = tmp_path / "claude" / "settings.json"
    settings.parent.mkdir()
    settings.write_text('{"model": "opus"}')
    assert "would keep" in setup.configure_claude(dry_run=True)[0] and "cleanupPeriodDays" not in settings.read_text()
    assert "3,650 days" in setup.configure_claude()[0]
    assert json.loads(settings.read_text()) == {"model": "opus", "cleanupPeriodDays": 3650}
    assert list((setup.install._home() / "backups").glob("claude-settings.json.*"))
    settings.write_text('{"cleanupPeriodDays": 14}')
    assert setup.configure_claude() == ["claude settings: transcripts kept 14 days, as set"]


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
    assert setup.paths.board().is_dir() and setup.paths.outbox().is_dir()  # the sandbox may write inside them, never make them


def test_the_install_reference_and_the_readme_name_both_folders_setup_lets_codex_write():
    reference = " ".join((Path(setup.__file__).resolve().parents[1] / "references" / "harness-install.md")
                         .read_text(encoding="utf-8").split())
    readme = " ".join((setup.REPO / "README.md").read_text(encoding="utf-8").split())
    for folder in ("`~/.synthesis/v5/board`", "`~/.synthesis/v5/outbox`"):
        assert folder in reference and folder in readme, folder
    assert "Only the board is granted" not in reference  # the earlier text
    for said in ("stage a file", "Only those two are granted", "`~/.synthesis/v5/state`"):
        assert said in reference, said
    # and the reference that tells sessions why the board has its own folder no longer calls it the only one granted
    coordination = " ".join((setup.REPO / "skills" / "synthesis-project-management" / "references" / "coordination.md")
                            .read_text(encoding="utf-8").split())
    assert "the one synthesis folder granted there" not in coordination
    assert "`~/.synthesis/v5/outbox/`" in coordination and "`~/.synthesis/v5/state/`" in coordination


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
    monkeypatch.setattr(setup.doctor, "find_client", lambda name: "/bin/true")
    monkeypatch.setattr(setup, "setup_plugins", interrupted)
    assert setup.main(["plugin", "--no-input"]) == 130
    assert "run the same command again to resume" in capsys.readouterr().err


def test_plugin_command_prints_the_restart_sentence(tmp_path, monkeypatch, capsys):
    claude, _ = fake_cli(tmp_path, "claude", {"plugin list": (0, [{"id": PLUGIN_ID, "version": "5", "enabled": True}]),
                                              "plugin": (0, "")})
    monkeypatch.setattr(setup.doctor, "find_client", lambda name: claude if name == "claude" else None)
    monkeypatch.setattr(setup, "configured_ref", lambda client: "stable")
    monkeypatch.setattr(setup, "configure_claude", lambda dry_run=False: [])
    assert setup.main(["plugin", "--no-input"]) == 0
    out = capsys.readouterr().out
    assert f"claude: installing synthesis-skills with {claude} ..." in out and "codex: not found" in out
    assert out.strip().endswith(setup.RESTART)


APPLE_CACHE = ("Library", "Caches", "com.apple.python")


def home_tree() -> dict:
    """Every path under the home folder with its time, apart from the bytecode cache Apple's Python keeps there:
    a temporary home starts with none, so any Python started in it fills one, which is not this code's doing."""
    home = Path.home()
    return {str(p): p.lstat().st_mtime_ns for p in home.rglob("*")
            if (parts := p.relative_to(home).parts)[:3] != APPLE_CACHE and parts not in (APPLE_CACHE[:1], APPLE_CACHE[:2])}


def test_the_home_tree_leaves_out_apples_bytecode_cache_and_nothing_else():
    before = home_tree()
    cache = Path.home() / "Library" / "Caches" / "com.apple.python" / "Applications"
    cache.mkdir(parents=True)
    (cache / "os.cpython-39.pyc").write_bytes(b"x")
    assert home_tree() == before
    (Path.home() / "stray.txt").write_text("x")
    assert set(home_tree()) - set(before) == {str(Path.home() / "stray.txt")}


def test_with_no_harness_setup_stops_before_changing_anything(monkeypatch, capsys):
    """2026-10-30: a Mac with no harness setup could find got a runtime nothing used and a restart sentence."""
    monkeypatch.setattr(setup.doctor, "find_client", lambda name: None)
    before = home_tree()
    assert setup.main(["all", "--no-input"]) == 1
    out = capsys.readouterr().out
    assert out.startswith("stopped: no Claude Code, Codex or Muse on this Mac") and "claude.com/download" in out
    assert setup.RESTART not in out
    assert setup.main(["plugin", "--no-input", "--clients", "codex"]) == 1
    assert capsys.readouterr().out.startswith("stopped: no Codex on this Mac")
    assert home_tree() == before


def test_uninstall_removes_the_plugin_with_each_harness_command(tmp_path, monkeypatch, capsys):
    claude, log = fake_cli(tmp_path, "claude", {"plugin list": (0, [{"id": PLUGIN_ID, "version": "5"}]), "plugin": (0, "")})
    monkeypatch.setattr(setup.doctor, "find_client", lambda name: claude if name == "claude" else None)
    setup.install.install(setup.REPO)
    assert setup.main(["uninstall", "--clients", "claude,codex"]) == 0
    out = capsys.readouterr().out
    assert f"plugin uninstall {PLUGIN_ID} --yes" in calls(log)
    assert "claude: removed" in out and "codex: synthesis-skills not installed" in out and "kept" in out


def test_dry_runs_say_what_they_would_do_and_change_nothing(tmp_path, monkeypatch, capsys):
    """A dry run reports in conditional wording (2026-10-20): uninstall's lines said "kept", and the plugin
    command said nothing of the runtime it would install."""
    claude, log = fake_cli(tmp_path, "claude", {"plugin list": (0, [{"id": PLUGIN_ID, "version": "5"}]), "plugin": (0, "")})
    monkeypatch.setattr(setup.doctor, "find_client", lambda name: claude if name == "claude" else None)
    setup.install.install(setup.REPO)
    before = home_tree()
    assert setup.main(["uninstall", "--dry-run", "--clients", "claude"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert "claude: would remove synthesis-skills" in out and any(line.startswith("would keep ") for line in out)
    assert not [line for line in out if line.startswith(("kept ", "removed ", "restored "))]
    monkeypatch.setattr(setup, "configured_ref", lambda client: "stable")
    assert setup.main(["plugin", "--no-input", "--dry-run", "--clients", "claude", "--day-end"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[-2].startswith("runtime: would install it from ") and "would link day-end (auto)" in out[-2]
    assert out[-1] == "Dry run: nothing was changed." and setup.RESTART not in out
    assert calls(log) == ["plugin list --json"] * 2  # no removal, install or update ran
    assert home_tree() == before


def _stand_ins(bin_dir, log, python_ok=True, **extra):
    """git and python3 that log their arguments (python3's version check answers without logging), plus extras."""
    scripts = {"git": f'echo "git $*" >> "{log}"',
               "python3": f'[ "$1" = "-c" ] && exit {0 if python_ok else 1}; [ "$1" = "-V" ] && echo "Python 3.8.9" '
                          f'&& exit 0; echo "python3 $*" >> "{log}"', **extra}
    for name, body in scripts.items():
        (bin_dir / name).write_text(f"#!/bin/sh\n{body}\n")
        (bin_dir / name).chmod(0o755)


def test_onboard_sh_installs_apples_command_line_tools_and_carries_on(tmp_path):
    """A Mac without the Command Line Tools has no git or python3: open Apple's installer, wait, continue."""
    bin_dir, log, installed = tmp_path / "bin", tmp_path / "calls.log", tmp_path / "clt"
    bin_dir.mkdir()
    _stand_ins(bin_dir, log, uname="echo Darwin", sleep="exit 0",
               **{"xcode-select": f'echo "xcode-select $*" >> "{log}"; [ "$1" = "--install" ] && touch "{installed}" '
                                  f'&& exit 0; [ -e "{installed}" ]'})
    env = {"PATH": f"{bin_dir}:/usr/bin:/bin", "HOME": str(tmp_path / "home"), "SYNTHESIS_SOURCE": str(tmp_path / "src")}
    done = subprocess.run(["sh", str(setup.REPO / "onboard.sh"), "plugin"], env=env, capture_output=True, text=True,
                          timeout=60)
    assert done.returncode == 0, done.stderr
    assert "Command Line Tools" in done.stdout and "click Install" in done.stdout
    steps = log.read_text().splitlines()
    assert steps[:3] == ["xcode-select -p", "xcode-select --install", "xcode-select -p"]
    assert steps[3].startswith("git clone --quiet --branch stable ") and steps[4].startswith("python3 ")
    installed.unlink()
    log.unlink()
    done = subprocess.run(["sh", str(setup.REPO / "onboard.sh"), "plugin", "--dry-run"], env=env, capture_output=True,
                          text=True, timeout=60)
    assert done.returncode == 1 and "a dry run installs nothing" in done.stderr
    assert log.read_text().splitlines() == ["xcode-select -p"]  # no installer window, nothing fetched


def test_onboard_sh_names_an_old_python_before_fetching_anything(tmp_path):
    bin_dir, log = tmp_path / "bin", tmp_path / "calls.log"
    bin_dir.mkdir()
    _stand_ins(bin_dir, log, python_ok=False, uname="echo Linux")
    env = {"PATH": f"{bin_dir}:/usr/bin:/bin", "HOME": str(tmp_path / "home"), "SYNTHESIS_SOURCE": str(tmp_path / "src")}
    done = subprocess.run(["sh", str(setup.REPO / "onboard.sh")], env=env, capture_output=True, text=True, timeout=60)
    assert done.returncode == 1 and "this python3 is Python 3.8.9; synthesis needs 3.9 or newer" in done.stderr
    assert not log.exists()


def test_onboard_sh_dry_run_runs_from_a_temporary_clone_and_leaves_the_source_alone(tmp_path):
    """onboard.sh fetched the release into ~/.synthesis/v5/source before setup.py ever saw --dry-run."""
    bin_dir, log, temp = tmp_path / "bin", tmp_path / "calls.log", tmp_path / "temp"
    bin_dir.mkdir()
    temp.mkdir()
    _stand_ins(bin_dir, log)
    env = {"PATH": f"{bin_dir}:/usr/bin:/bin", "HOME": str(tmp_path / "home"), "TMPDIR": str(temp),
           "SYNTHESIS_SOURCE": str(tmp_path / "source")}
    script = str(setup.REPO / "onboard.sh")
    done = subprocess.run(["sh", script, "org", "--org-repo", "ssh://git@example.test/o/config.git", "--dry-run"],
                          env=env, capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr
    clone, run = log.read_text().splitlines()
    assert clone.startswith(f"git clone --quiet --depth 1 --branch stable https://github.com/") and str(temp) in clone
    assert run.startswith(f"python3 {clone.split()[-1]}/skills/synthesis-onboarding/scripts/setup.py org --org-repo ")
    assert run.endswith(" --dry-run") and list(temp.iterdir()) == [] and not (tmp_path / "source").exists()
    log.unlink()
    subprocess.run(["sh", script, "plugin"], env=env, capture_output=True, text=True, timeout=60, check=True)
    assert log.read_text().splitlines()[0].endswith(f" {tmp_path / 'source'}")  # without it, the durable checkout


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


@pytest.mark.parametrize("login", [False, True], ids=["a login shell that defines none", "a login shell that defines another"])
@pytest.mark.parametrize("chosen", [False, True], ids=["installed with no home of its own", "installed with a home of its own"])
def test_the_weekday_nudge_runs_with_the_home_selected_at_install(day_end, tmp_path, monkeypatch, chosen, login):
    """The nudge asks the ritual log under the synthesis home which workspaces still owe a close. Scheduled by an
    install made with a home of its own, its job carried no home: it ran that install's script on the default
    home's log, as the hourly copy of transcripts did."""
    home = setup.install._home()
    if not chosen:
        monkeypatch.delenv("SYNTHESIS_HOME")                          # the default home, the same folder here
    setup.register_day_end(load=False)
    monkeypatch.delenv("SYNTHESIS_HOME", raising=False)               # launchd starts the job with none of the installer's shell
    runs = _started_by_launchd(tmp_path, "export SYNTHESIS_HOME=/elsewhere/home\n" if login else "", nudge=True)
    assert [(run["words"], run["SYNTHESIS_HOME"]) for run in runs] == [([], str(home) if chosen else "/elsewhere/home" if login else None)]
    assert any("removed the nudge schedule" in said for said in setup.unregister_day_end())    # and it is still this install's


def test_day_end_before_install_says_what_to_run_first():
    with pytest.raises(setup.SetupError, match="not installed"):
        setup.register_day_end()


# ---- the hourly copy of session transcripts -------------------------------------
# 2026-11-11: the archive had no trigger of its own. A transcript was copied only when some session ran resume,
# handoff or a ritual, and one that no session exported in time was skipped.

def test_the_hourly_export_is_scheduled_to_run_the_installed_command(day_end):
    import plistlib
    lines = setup.register_sessions_export()
    command = setup.install._home() / "bin" / "synthesis"
    spec = plistlib.loads(setup._export_plist().read_bytes())
    assert spec["Label"] == "com.synthesis.sessions-export" and spec["StartInterval"] == 3600 and spec["RunAtLoad"] is True
    assert f'"{command}" sessions export --all --scheduled; ' in spec["ProgramArguments"][-1]
    assert f'"{command}" sessions sync' in spec["ProgramArguments"][-1]
    assert calls(day_end)[-1].startswith("bootstrap gui/") and any("every hour" in line for line in lines)


def test_the_export_schedule_without_launchctl_is_written_and_not_loaded(day_end):
    setup.register_sessions_export(load=False)
    assert setup._export_plist().exists() and calls(day_end) == []


HOMES = ("SYNTHESIS_HOME", "CLAUDE_CONFIG_DIR", "CODEX_HOME", "XDG_DATA_HOME", "SYNTHESIS_CLAUDE_DESKTOP_DIR")  # the runtime's folder, and where each harness keeps transcripts
CHOSEN = {"none": (), **{name: (name,) for name in HOMES}, "all": HOMES}


def _started_by_launchd(tmp_path, profile: str = "", nudge: bool = False) -> list:
    """What the scheduled job's command is given when launchd starts the job: the job's own program arguments and
    environment variables, the person's login shell (`profile` is what theirs defines) and nothing of the shell
    the installer ran in. The installed command is replaced by one that writes down its words and its homes.
    The job is the hourly copy's, or with `nudge` the weekday nudge's."""
    import plistlib
    spec, seen = plistlib.loads((setup._nudge_plist() if nudge else setup._export_plist()).read_bytes()), tmp_path / "seen.jsonl"
    (setup.install._home() / "bin" / ("day-end-nudge.sh" if nudge else "synthesis")).write_text(
        f"#!{sys.executable}\nimport json, os, sys\nopen({str(seen)!r}, 'a').write(json.dumps("
        f"{{'words': sys.argv[1:], **{{name: os.environ.get(name) for name in {HOMES!r}}}}}) + '\\n')\n")
    (Path.home() / ".bash_profile").write_text(profile)
    done = subprocess.run(spec["ProgramArguments"], capture_output=True, text=True, timeout=60,
                          env={"HOME": str(Path.home()), "PATH": "/usr/bin:/bin", **spec.get("EnvironmentVariables", {})})
    assert done.returncode == 0, done.stderr
    return [json.loads(line) for line in seen.read_text().splitlines()]


@pytest.mark.parametrize("login", [False, True], ids=["a login shell that defines none", "a login shell that defines others"])
@pytest.mark.parametrize("chosen", CHOSEN.values(), ids=CHOSEN.keys())
def test_the_scheduled_copy_runs_with_each_home_selected_at_install(day_end, tmp_path, monkeypatch, chosen, login):
    """2026-11-12, a second review: an install made with homes of its own (`SYNTHESIS_HOME` for the runtime, the
    three folders the harnesses keep transcripts under) scheduled a job that carried none of them, so the job ran
    that install's command against the default home. Each one set when the schedule is installed goes with the
    job, also where the login shell defines another; one not set is left to the login shell, as before."""
    picked = {"SYNTHESIS_HOME": str(setup.install._home()), "CLAUDE_CONFIG_DIR": str(tmp_path / "custom" / "claude config"),
              "CODEX_HOME": str(tmp_path / "custom" / "it's $HOME; \"codex\""), "XDG_DATA_HOME": str(tmp_path / "custom" / "xdg"),
              "SYNTHESIS_CLAUDE_DESKTOP_DIR": str(tmp_path / "custom" / "the desktop app")}
    for name in HOMES:
        if name in chosen:
            monkeypatch.setenv(name, picked[name])
        else:
            monkeypatch.delenv(name, raising=False)
    setup.register_sessions_export(load=False)
    for name in HOMES:                                         # launchd starts the job with none of the installer's shell
        monkeypatch.delenv(name, raising=False)
    elsewhere = {name: f"/elsewhere/{name.lower()}" for name in HOMES}
    runs = _started_by_launchd(tmp_path, "".join(f"export {name}={folder}\n" for name, folder in elsewhere.items()) if login else "")
    assert [run["words"] for run in runs] == [["sessions", "export", "--all", "--scheduled"], ["sessions", "sync"]]
    for name in HOMES:
        wanted = picked[name] if name in chosen else elsewhere[name] if login else None
        assert [run[name] for run in runs] == [wanted, wanted], name


def test_a_home_set_to_nothing_at_install_is_left_to_the_login_shell(day_end, tmp_path, monkeypatch):
    """A variable set to an empty string selects the default folder, as an unset one does: nothing goes with the job."""
    for name in HOMES[1:]:
        monkeypatch.setenv(name, "")
    setup.register_sessions_export(load=False)
    for name in HOMES:
        monkeypatch.delenv(name, raising=False)
    runs = _started_by_launchd(tmp_path)
    assert len(runs) == 2 and all(run[name] is None for run in runs for name in HOMES[1:])
    assert all(run["SYNTHESIS_HOME"] == str(setup.install._home()) for run in runs)


@pytest.mark.parametrize("status", [1, 2, 0])
def test_the_scheduled_job_runs_the_sync_whatever_the_exports_exit_status(day_end, tmp_path, status):
    """The export exits 1 when it could not copy something. The job's line runs the sync after it all the same, so
    what was copied still reaches the sessions repos, and the job ends with the sync's own status."""
    import plistlib
    setup.register_sessions_export(load=False)
    spec, seen = plistlib.loads(setup._export_plist().read_bytes()), tmp_path / "seen.txt"
    (setup.install._home() / "bin" / "synthesis").write_text(
        f"#!{sys.executable}\nimport sys\nopen({str(seen)!r}, 'a').write(' '.join(sys.argv[1:]) + '\\n')\n"
        f"sys.exit({status} if sys.argv[1:3] == ['sessions', 'export'] else 0)\n")
    done = subprocess.run(spec["ProgramArguments"], capture_output=True, text=True, timeout=60,
                          env={"HOME": str(Path.home()), "PATH": "/usr/bin:/bin"})
    assert seen.read_text().splitlines() == ["sessions export --all --scheduled", "sessions sync"] and done.returncode == 0, done.stderr


def test_uninstall_removes_only_an_export_schedule_that_runs_this_install(day_end):
    setup.register_sessions_export(load=False)
    assert any("removed the export schedule" in line for line in setup.unregister_sessions_export())
    assert not setup._export_plist().exists() and calls(day_end)[-1].startswith("bootout gui/")
    plist = setup._export_plist()
    plist.write_text("<plist><dict><key>ProgramArguments</key><array><string>/other/synthesis sessions export</string></array></dict></plist>")
    assert plist.exists() and any(line.startswith("kept") for line in setup.unregister_sessions_export())
    near = f'"{setup.install._home() / "bin" / "synthesis"}-old" sessions export --all'            # a command whose path only begins like this install's
    plist.write_text(f"<plist><dict><key>ProgramArguments</key><array><string>{near}</string></array></dict></plist>")
    assert plist.exists() and any(line.startswith("kept") for line in setup.unregister_sessions_export())


# 2026-11-12, a second review: a schedule was taken for this install's when this install's path stood anywhere in its
# line, so one whose command only ended with that path, and `echo <that path>`, were unloaded and removed. A schedule
# is this install's when the program of every command its line runs is this install's, the whole path.

def _scheduled(line, plist: Path = None) -> Path:
    """A schedule file whose login shell is given `line`; a list is its program arguments whole, bytes the file itself."""
    import plistlib
    plist = plist or setup._export_plist()
    plist.parent.mkdir(parents=True, exist_ok=True)
    plist.write_bytes(line if isinstance(line, bytes) else plistlib.dumps(
        {"Label": plist.stem, "ProgramArguments": line if isinstance(line, list) else ["/bin/bash", "-lc", line]}))
    return plist


ANOTHERS = {  # {own} is this install's command: none of these runs it as the program of each of its commands
    "a command whose path ends with this install's": '"/Volumes/backup{own}" sessions export --all; "/Volumes/backup{own}" sessions sync',
    "this install's path handed to echo": 'echo "{own}" sessions export --all',
    "this install's path as the last word of another program": "/bin/echo {own}",
    "a sibling whose name begins like it": '"{own}-old" sessions export --all; "{own}-old" sessions sync',
    "a sibling named with a hash sign": "{own}#old sessions export --all",
    "this install's path as a variable for another command": 'SYNTHESIS={own} "/other/bin/synthesis" sessions export --all',
    "this install's path as a home another command is given": 'export SYNTHESIS_HOME={own}; "/other/bin/synthesis" sessions export --all',
    "this install's path inside the words handed to a shell": '/bin/sh -c "{own} sessions export --all"',
    "this install's command after another program's": 'echo start; "{own}" sessions export --all',
    "another program on the line after this install's command": '"{own}" sessions export --all\n/other/bin/synthesis sessions sync',
    "a line with a quote left open": '"{own} sessions export --all',
    "a line that runs nothing": "export SYNTHESIS_HOME=/custom",
    "another program given this install's path, with no shell": ["/usr/bin/env", "{own}", "sessions", "export"],
    "a line that is no text": ["/bin/bash", "-lc", 41],
    "a file cut short": b"<plist><dict><key>ProgramArguments</key><array><string>/bin/bash</string><string>-lc</string><string>{own}",
    "a file that holds no dictionary": b"<plist><array><string>{own}</string></array></plist>",
}


@pytest.mark.parametrize("line", ANOTHERS.values(), ids=ANOTHERS.keys())
def test_uninstall_keeps_an_export_schedule_whose_own_command_is_not_this_installs(day_end, line):
    own = str(setup.install._home() / "bin" / "synthesis")
    named = [word.replace("{own}", own) if isinstance(word, str) else word for word in line] if isinstance(line, list) else \
        line.replace(b"{own}", own.encode()) if isinstance(line, bytes) else line.replace("{own}", own)
    plist = _scheduled(named)
    assert any(said.startswith("would keep") for said in setup.unregister_sessions_export(dry_run=True))
    assert any(said.startswith("kept") for said in setup.unregister_sessions_export())
    assert plist.exists() and calls(day_end) == []                       # nothing was asked of launchctl


OWN = {  # and these are this install's, however the line around its command is written
    "the two commands alone": '"{own}" sessions export --all; "{own}" sessions sync',
    "homes set first, one with a quote and a semicolon in it": "export SYNTHESIS_HOME=/custom; export CODEX_HOME='/it'\"'\"'s; \"x\"'; "
                                                               '"{own}" sessions export --all; "{own}" sessions sync',
    "the command replacing its shell": 'exec "{own}" sessions export --all',
    "the command with no shell": ["{own}", "sessions", "export", "--all"],
}


@pytest.mark.parametrize("line", OWN.values(), ids=OWN.keys())
def test_uninstall_removes_an_export_schedule_whose_every_command_is_this_installs(day_end, line):
    own = str(setup.install._home() / "bin" / "synthesis")
    plist = _scheduled([word.replace("{own}", own) for word in line] if isinstance(line, list) else line.replace("{own}", own))
    assert any("removed the export schedule" in said for said in setup.unregister_sessions_export())
    assert not plist.exists() and calls(day_end)[-1].startswith("bootout gui/")


@pytest.mark.parametrize("program, words, kept", [
    ("/bin/echo", ["/bin/bash", "-lc", '"{own}" sessions export --all; "{own}" sessions sync'], True),
    ("/Volumes/backup{own}", ["{own}", "sessions", "export", "--all"], True),
    ("{own}", ["synthesis", "sessions", "export", "--all"], False),
], ids=["another program handed this install's line", "a path that ends with this install's", "this install's command"])
def test_a_schedule_that_names_its_program_apart_from_its_words_is_matched_by_that_program(day_end, program, words, kept):
    """launchd runs a job's `Program` when the job names one, and hands it `ProgramArguments` only as its words: the
    words then say nothing about what runs."""
    import plistlib
    own = str(setup.install._home() / "bin" / "synthesis")
    plist = _scheduled(plistlib.dumps({"Label": setup.EXPORT_LABEL, "Program": program.replace("{own}", own),
                                       "ProgramArguments": [word.replace("{own}", own) for word in words]}))
    said = setup.unregister_sessions_export()
    assert said[0].startswith("kept" if kept else "removed") and plist.exists() is kept and bool(calls(day_end)) is not kept


def test_a_schedule_this_install_wrote_is_its_own_whatever_homes_it_carries_and_whoever_uninstalls(day_end, tmp_path, monkeypatch):
    for name, folder in zip(HOMES[1:], ("claude config", "it's $HOME; \"codex\"", "xdg")):
        monkeypatch.setenv(name, str(tmp_path / "custom" / folder))
    setup.register_sessions_export(load=False)
    for name in HOMES[1:]:                                             # uninstall runs in a shell that sets none of them
        monkeypatch.delenv(name)
    assert any("removed the export schedule" in said for said in setup.unregister_sessions_export())
    assert not setup._export_plist().exists()


def test_a_nudge_schedule_whose_command_only_ends_like_this_installs_is_anothers(day_end):
    """The weekday nudge is matched the same way: another install's schedule is archived before this one replaces it,
    and uninstall keeps it."""
    nudge = setup.install._home() / "bin" / "day-end-nudge.sh"
    plist = _scheduled(f'exec "/Volumes/backup{nudge}"', setup._nudge_plist())
    assert any(said.startswith("kept") for said in setup.unregister_day_end()) and plist.exists() and calls(day_end) == []
    assert any("archived the previous nudge schedule" in said for said in setup.register_day_end(load=False))
    assert list((setup.install._home() / "archive").glob("*/com.synthesis.day-end-nudge.plist"))
    assert any("removed the nudge schedule" in said for said in setup.unregister_day_end()) and not plist.exists()


def test_another_installs_export_schedule_is_set_aside_before_this_one_replaces_it(day_end):
    """One label holds one schedule. Installing this one replaced another install's without a word, and with it
    that install's hourly copy. It is archived first, as a nudge schedule is, and the setup says where."""
    import plistlib
    other = '"/another/v5/bin/synthesis" sessions export --all; "/another/v5/bin/synthesis" sessions sync'
    _scheduled(other)
    lines = setup.register_sessions_export(load=False)
    kept = list((setup.install._home() / "archive").glob("*/com.synthesis.sessions-export.plist"))
    assert len(kept) == 1 and plistlib.loads(kept[0].read_bytes())["ProgramArguments"][-1] == other
    assert any("archived" in line and str(kept[0].parent) in line for line in lines)
    assert setup.install.runs_only(setup._export_plist(), setup.install._home() / "bin" / "synthesis")
    assert not any("archived" in line for line in setup.register_sessions_export(load=False))        # its own is replaced in place
    assert len(list((setup.install._home() / "archive").glob("*/com.synthesis.sessions-export.plist"))) == 1


# 2026-11-12: the doctor answered ok for a loaded schedule that ran another install's command, while this home's stamp
# was fresh from its own sessions' exports. Whose schedule it is, is told in one place in the core, which the setup
# asks before it replaces or removes one and the doctor asks before it calls the hourly copy healthy.

def _doctor() -> tuple:
    """What the doctor says of the hourly copy for this home, where launchd holds the schedule loaded and an export
    has just finished: the status and the words."""
    from datetime import datetime
    stamp = setup.install._home() / "sessions" / ".state" / "export.json"
    stamp.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    stamp.write_text(json.dumps({"exported": now, "scheduled": now}))  # the schedule's own run, as its command marks it
    found = setup.doctor.check_sessions_export(setup._export_plist(), stamp, run=lambda argv, **kw: subprocess.CompletedProcess(argv, 0, "", ""))
    return found.status, found.detail


@pytest.mark.parametrize("line", [*ANOTHERS.values(), *OWN.values()], ids=[*ANOTHERS, *OWN])
def test_the_doctor_and_the_setup_tell_whose_schedule_it_is_the_same_way(day_end, line):
    """Every schedule the uninstall keeps as not this install's, the doctor fails on; every one the uninstall removes
    as this install's, the doctor takes for the hourly copy."""
    own = str(setup.install._home() / "bin" / "synthesis")
    named = [word.replace("{own}", own) if isinstance(word, str) else word for word in line] if isinstance(line, list) else \
        line.replace(b"{own}", own.encode()) if isinstance(line, bytes) else line.replace("{own}", own)
    _scheduled(named)
    status, detail = _doctor()
    kept = setup.unregister_sessions_export(dry_run=True)[0].startswith("would keep")
    assert kept is (line in ANOTHERS.values()) and status == ("fail" if kept else "ok"), detail
    assert not kept or ("not this install's ~/.synthesis/v5/bin/synthesis" in detail and "--sessions-export" in detail)
    assert not hasattr(setup, "_points_at")                              # the setup keeps no test of its own


def test_the_doctor_fails_once_another_installs_setup_has_replaced_this_schedule(day_end, tmp_path, monkeypatch):
    """One label holds one schedule. A second install, made with a home of its own, schedules its hourly copy: this
    install's schedule is set aside, and from then on nothing copies this home's transcripts on a schedule. This
    home's doctor says so and names the command that runs, and this home's setup puts its own schedule back."""
    setup.register_sessions_export(load=False)
    assert _doctor()[0] == "ok"
    with monkeypatch.context() as second:
        second.setenv("SYNTHESIS_HOME", str(tmp_path / "second" / "v5"))
        setup.install.install(tmp_path / "plugin")
        assert any("archived another install's export schedule" in said for said in setup.register_sessions_export(load=False))
        assert _doctor()[0] == "ok"                                      # the second home's hourly copy is its own
    status, detail = _doctor()
    assert status == "fail" and f"runs {tmp_path / 'second' / 'v5' / 'bin' / 'synthesis'}," in detail
    assert "not this install's ~/.synthesis/v5/bin/synthesis" in detail and "--sessions-export" in detail
    assert any("archived another install's export schedule" in said for said in setup.register_sessions_export(load=False))
    assert _doctor()[0] == "ok"


def test_the_export_schedule_before_install_says_what_to_run_first():
    with pytest.raises(setup.SetupError, match="not installed"):
        setup.register_sessions_export()


# ---- the plugin's hooks declared in Codex's own hooks file (--codex-user-hooks) ---------------------------------
# Codex trusts a plugin's hook only while the plugin's files match what was approved, so it runs none of synthesis's
# hooks after a release until they are approved again; a hook declared in its own hooks.json is trusted by its
# declaration alone (codex-rs hooks discovery, probed on 0.167 on 2026-11-13 and 11-14).

STABLE = '"$HOME/.synthesis/v5/bin/synthesis-hook"'
PLUGIN_HOOKS = json.loads((setup.REPO / "hooks" / "hooks.json").read_text())
SWITCH = "# synthesis-setup: codex-user-hooks"


def codex_home(tmp_path, monkeypatch, config="", hooks=None):
    """A Codex home of the test's own: its config.toml, and its hooks.json when given (text as it is, else JSON)."""
    home = tmp_path / "codex-home"
    home.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(home))
    if config is not None:
        (home / "config.toml").write_text(config)
    if hooks is not None:
        (home / "hooks.json").write_text(hooks if isinstance(hooks, str) else json.dumps(hooks, indent=2) + "\n")
    return home


def plugin_keys(hooks=PLUGIN_HOOKS):
    """Codex's state key for each of the plugin's own hooks: its id, the file, the event, the group and the hook."""
    return [f"{PLUGIN_ID}:hooks/hooks.json:{setup.doctor._snake(event)}:{gi}:{hi}"
            for event, groups in hooks["hooks"].items() for gi, group in enumerate(groups) for hi, _ in enumerate(group["hooks"])]


def hook_state(home):
    return (setup.doctor.read_toml((home / "config.toml").read_text()).get("hooks") or {}).get("state") or {}


def declared(home):
    return json.loads((home / "hooks.json").read_text())["hooks"]


def files(home):
    return {p.name: p.read_bytes() for p in home.iterdir()}


def backups():
    folder = setup.install._home() / "backups"
    return sorted(p.name for p in folder.iterdir()) if folder.exists() else []


def test_the_option_declares_the_plugins_four_hooks_in_codexs_own_file_and_switches_the_plugins_off(tmp_path, monkeypatch):
    mine = {"type": "command", "command": "/usr/local/bin/notify", "timeout": 3}
    home = codex_home(tmp_path, monkeypatch, config='model = "gpt-5"\n\n[features]\nhooks = true\n',
                      hooks={"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [mine]}], "Notification": [{"hooks": [mine]}]}})
    lines = setup.codex_user_hooks(True, setup.REPO)
    found = declared(home)
    assert found["PreToolUse"][0] == {"matcher": "Bash", "hooks": [mine]}            # the person's own, kept where they were
    assert found["Notification"] == [{"hooks": [mine]}]
    for event, groups in PLUGIN_HOOKS["hooks"].items():
        ours = found[event][-len(groups):]
        if event == "SessionStart":  # the plugin's names its own folder so a first run can install the runtime; setup has
            assert ours == [{**g, "hooks": [{**h, "command": f"{STABLE} session-start"} for h in g["hooks"]]} for g in groups]
        else:                        # installed it, so the user-level one calls the stable path alone
            assert ours == groups    # exactly as the plugin declares it: the same command, matcher and timeout
    assert {key: value.get("enabled") for key, value in hook_state(home).items()} == {key: False for key in plugin_keys()}
    assert (home / "config.toml").read_text().startswith('model = "gpt-5"\n\n[features]\nhooks = true\n')
    assert any("Codex's /hooks" in line for line in lines)                           # approved once, there, by the person


def test_a_second_run_changes_nothing(tmp_path, monkeypatch):
    home = codex_home(tmp_path, monkeypatch, config="[features]\nhooks = true\n")
    setup.codex_user_hooks(True, setup.REPO)
    before, kept = files(home), backups()
    lines = setup.codex_user_hooks(True, setup.REPO)
    assert files(home) == before and backups() == kept
    assert lines and all("already" in line for line in lines)


def test_a_plugin_hook_codex_holds_an_approval_for_gains_a_line_in_that_table_and_no_second_table(tmp_path, monkeypatch):
    key = plugin_keys()[0]
    home = codex_home(tmp_path, monkeypatch, config=f'[hooks.state."{key}"]\ntrusted_hash = "sha256:aa"\n'
                                                    'trusted_content_hash = "sha256:bb"\n')
    setup.codex_user_hooks(True, setup.REPO)
    text = (home / "config.toml").read_text()
    setup.doctor.read_toml(text, strict=True)                                         # Codex refuses a table defined twice
    assert text.count(f'[hooks.state."{key}"]') == 1
    assert hook_state(home)[key] == {"enabled": False, "trusted_hash": "sha256:aa", "trusted_content_hash": "sha256:bb"}


@pytest.mark.parametrize("hooks,config", [
    ("{not json", "[features]\nhooks = true\n"),
    ('{"hooks": {}, "version": 1}', ""),                                     # Codex reads only hooks and description there
    ('{"hooks": {"Stop": {"hooks": []}}}', ""),                              # an event holds a list of groups
    ('{"hooks": {"Stop": [{"hooks": [{"type": "http", "url": "x"}]}]}}', ""),  # a type Codex does not know: it reads none
    ('{"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "x", "timeout": "5"}]}]}}', ""),
    (None, "[hooks.state\nenabled = false\n"),                               # a table header that never closes
    (None, 'model = "gpt-5"\nthis is not toml\n'),
    (None, "[a]\nx = 1\n[a]\ny = 2\n"),                                      # a table defined twice
    (None, 'x = ["never closed",\n'),
])
def test_a_file_that_cannot_be_parsed_is_refused_and_nothing_changes(tmp_path, monkeypatch, hooks, config):
    home = codex_home(tmp_path, monkeypatch, config=config, hooks=hooks)
    before = files(home)
    with pytest.raises(setup.SetupError, match="nothing was changed"):
        setup.codex_user_hooks(True, setup.REPO)
    assert files(home) == before and backups() == []


def _codex_cli(tmp_path, monkeypatch):
    binary, log = fake_cli(tmp_path, "codex", {LIMITED: (0, {"installed": [CODEX_ENTRY], "available": []}), "plugin": (0, "{}")})
    monkeypatch.setattr(setup.doctor, "find_client", lambda name: binary if name == "codex" else None)
    monkeypatch.setattr(setup, "configured_ref", lambda client: "stable")
    return binary


def test_the_option_is_off_unless_asked_for(tmp_path, monkeypatch, capsys):
    home = codex_home(tmp_path, monkeypatch, config="[features]\nhooks = true\n")
    binary = _codex_cli(tmp_path, monkeypatch)
    assert setup.main(["plugin", "--no-input", "--clients", "codex"]) == 0
    assert not (home / "hooks.json").exists() and SWITCH not in (home / "config.toml").read_text()
    assert setup.install_plugin("codex", binary) == "codex: updated synthesis-skills 5.0.0"   # the release script's update
    assert not (home / "hooks.json").exists()


def test_the_plugin_command_turns_it_on_keeps_it_and_turns_it_off(tmp_path, monkeypatch, capsys):
    home = codex_home(tmp_path, monkeypatch, config="[features]\nhooks = true\n")
    _codex_cli(tmp_path, monkeypatch)
    assert setup.main(["plugin", "--no-input", "--clients", "codex", "--codex-user-hooks"]) == 0
    assert set(declared(home)) == set(PLUGIN_HOOKS["hooks"]) and "Codex's /hooks" in capsys.readouterr().out
    assert setup.main(["plugin", "--no-input", "--clients", "codex"]) == 0                   # a run without the flag keeps it
    assert set(declared(home)) == set(PLUGIN_HOOKS["hooks"]) and SWITCH in (home / "config.toml").read_text()
    assert setup.main(["plugin", "--no-input", "--clients", "codex", "--no-codex-user-hooks"]) == 0
    assert not (home / "hooks.json").exists() and SWITCH not in (home / "config.toml").read_text()


def test_a_file_the_command_cannot_parse_stops_it_and_leaves_both_files_as_they_were(tmp_path, monkeypatch, capsys):
    home = codex_home(tmp_path, monkeypatch, config="[features]\nhooks = true\n", hooks="{not json")
    _codex_cli(tmp_path, monkeypatch)
    before = files(home)
    assert setup.main(["plugin", "--no-input", "--clients", "codex", "--codex-user-hooks"]) == 1
    assert "nothing was changed" in capsys.readouterr().out and files(home) == before


def test_uninstall_takes_out_exactly_what_the_option_added(tmp_path, monkeypatch, capsys):
    """The declarations and switches setup added go; the person's own hooks and settings stay byte for byte, and an
    approval Codex recorded under a table setup added keeps that table."""
    held = plugin_keys()[2]
    config = (f'model = "gpt-5"\n\n[features]\nhooks = true\n\n[hooks.state."{held}"]\ntrusted_hash = "sha256:aa"\n\n'
              '[projects."/x"]\ntrust_level = "trusted"\n')
    hooks = json.dumps({"description": "mine", "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "/bin/echo bye"}]}]}},
                       indent=2) + "\n"
    home = codex_home(tmp_path, monkeypatch, config=config, hooks=hooks)
    setup.codex_user_hooks(True, setup.REPO)
    assert setup.codex_user_hooks(False) and files(home) == {"config.toml": config.encode(), "hooks.json": hooks.encode()}
    setup.codex_user_hooks(True, setup.REPO)
    approved = plugin_keys()[0]                       # Codex then records an approval beside a switch setup added a table for
    lines = (home / "config.toml").read_text().splitlines()
    at = next(i for i, line in enumerate(lines) if line.startswith(f'[hooks.state."{approved}"]'))
    lines.insert(at + 2, 'trusted_hash = "sha256:cc"')
    (home / "config.toml").write_text("\n".join(lines) + "\n")
    monkeypatch.setattr(setup.doctor, "find_client", lambda name: None)
    assert setup.main(["uninstall", "--clients", "codex"]) == 0
    assert json.loads((home / "hooks.json").read_text()) == json.loads(hooks)
    expected = setup.doctor.read_toml(config)
    expected["hooks"]["state"][approved] = {"trusted_hash": "sha256:cc"}
    assert setup.doctor.read_toml((home / "config.toml").read_text(), strict=True) == expected
    assert "enabled" not in (home / "config.toml").read_text()


def test_an_update_brings_the_declaration_up_to_date_in_its_place(tmp_path, monkeypatch):
    """A release that widens the shell hook's matcher (5.13.0 added shell_command) reaches the user-level copy at the
    next install, where the old one was, so the keys of the person's own hooks after it do not move."""
    earlier = json.loads(json.dumps(PLUGIN_HOOKS))
    earlier["hooks"]["PreToolUse"][0]["matcher"] = "Bash|exec_command"
    older = tmp_path / "older"
    (older / "hooks").mkdir(parents=True)
    (older / "hooks" / "hooks.json").write_text(json.dumps(earlier))
    first = {"matcher": "Bash", "hooks": [{"type": "command", "command": "/usr/local/bin/notify"}]}
    home = codex_home(tmp_path, monkeypatch, hooks={"hooks": {"PreToolUse": [first]}})
    setup.codex_user_hooks(True, older)
    later = {"hooks": [{"type": "command", "command": "/usr/local/bin/audit"}]}
    data = json.loads((home / "hooks.json").read_text())
    data["hooks"]["PreToolUse"].append(later)                                         # one of the person's own after it
    (home / "hooks.json").write_text(json.dumps(data))
    assert setup.codex_user_hooks(None, setup.REPO)                                   # what an install of the next release runs
    assert declared(home)["PreToolUse"] == [first, PLUGIN_HOOKS["hooks"]["PreToolUse"][0], later]


def test_a_release_that_adds_the_guards_setting_keeps_the_declaration_codex_reads_and_its_approval(tmp_path, monkeypatch):
    """5.21.0 adds "onFailure": "block" to the guard for Claude Code. Its install brings the user-level copy in step;
    Codex reads it and hashes the guard as before, so the approval given earlier holds and setup does not ask for it
    again (Codex 0.167.0-alpha.4.1, 2026-11-14: the four trusted before that release and after it)."""
    earlier = json.loads(json.dumps(PLUGIN_HOOKS))
    for handler in earlier["hooks"]["PreToolUse"][0]["hooks"]:
        handler.pop("onFailure", None)
    older = tmp_path / "older"
    (older / "hooks").mkdir(parents=True)
    (older / "hooks" / "hooks.json").write_text(json.dumps(earlier))
    home = codex_home(tmp_path, monkeypatch, config="[features]\nhooks = true\n")
    setup.codex_user_hooks(True, older)
    before = declared(home)["PreToolUse"][0]
    lines = setup.codex_user_hooks(None, setup.REPO)                                   # what an install of the release runs
    after = declared(home)["PreToolUse"][0]
    assert after == PLUGIN_HOOKS["hooks"]["PreToolUse"][0] and after["hooks"][0]["onFailure"] == "block"
    assert setup.doctor.codex_hooks_problem({"hooks": declared(home)}) == ""

    def hashed(group):
        return setup.doctor.codex_hook_hash("PreToolUse", group.get("matcher"), group["hooks"][0])
    assert hashed(after) == hashed(before)
    assert lines and not any("approve" in line for line in lines)                    # nothing to approve again,
    assert any("in step" in line and "approval" in line and "stays" in line for line in lines)  # and it says so


def test_a_declaration_the_person_wrote_is_kept_and_not_doubled(tmp_path, monkeypatch):
    own = {"matcher": "Bash", "hooks": [{"type": "command", "command": '"${HOME}/.synthesis/v5/bin/synthesis-hook" pre-tool-use'}]}
    home = codex_home(tmp_path, monkeypatch, hooks={"hooks": {"PreToolUse": [own]}})
    lines = setup.codex_user_hooks(True, setup.REPO)
    assert declared(home)["PreToolUse"] == [own] and any("PreToolUse" in line and "kept" in line for line in lines)
    pre = next(key for key in plugin_keys() if ":pre_tool_use:" in key)
    assert hook_state(home)[pre]["enabled"] is False                                  # its plugin copy is off all the same
    setup.codex_user_hooks(False)
    assert declared(home)["PreToolUse"] == [own]                                      # never setup's to take out



def test_the_persons_own_text_in_codexs_hooks_file_comes_back_byte_for_byte(tmp_path, monkeypatch):
    hooks = json.dumps({"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "/bin/echo 'caf\u00e9 \u2615'"}]}]}},
                       indent=2, ensure_ascii=False) + "\n"
    home = codex_home(tmp_path, monkeypatch)
    (home / "hooks.json").write_text(hooks, encoding="utf-8")
    setup.codex_user_hooks(True, setup.REPO)
    assert "caf\u00e9 \u2615" in (home / "hooks.json").read_text(encoding="utf-8")   # as written, not as escapes
    setup.codex_user_hooks(False)
    assert (home / "hooks.json").read_text(encoding="utf-8") == hooks

def test_a_dry_run_says_what_it_would_do_and_writes_nothing(tmp_path, monkeypatch):
    home = codex_home(tmp_path, monkeypatch, config="[features]\nhooks = true\n")
    before = files(home)
    lines = setup.codex_user_hooks(True, setup.REPO, dry_run=True)
    assert lines and all("would" in line for line in lines)
    assert files(home) == before and backups() == []


def test_the_references_say_what_the_option_does_how_to_turn_it_off_and_what_it_gives_up():
    for reference in (Path(setup.__file__).resolve().parents[1] / "references" / "harness-install.md",
                      setup.REPO / "skills" / "synthesis-agent-conformance" / "references" / "architecture.md"):
        text = " ".join(reference.read_text(encoding="utf-8").split())
        for said in ("--codex-user-hooks", "--no-codex-user-hooks", "/hooks", "someone else's plugin"):
            assert said in text, (reference.name, said)

"""Real isolated payload and lifecycle fixtures; never install into the host."""
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

import synthesis_cli
from system_contract import SystemState
from test_onboard import REPO_ROOT, snapshot_current_source


@pytest.fixture
def modular_source(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    environment = {key: value for key, value in os.environ.items() if not key.startswith(("GIT_", "SYNTHESIS_"))}
    environment.update(HOME=str(home), GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
                       GIT_AUTHOR_NAME="Fixture", GIT_COMMITTER_NAME="Fixture",
                       GIT_AUTHOR_EMAIL="fixture@example.invalid", GIT_COMMITTER_EMAIL="fixture@example.invalid",
                       PYTHONDONTWRITEBYTECODE="1")
    source = snapshot_current_source(REPO_ROOT, tmp_path / "source", environment)
    monkeypatch.setattr(synthesis_cli, "REPO_ROOT", source)
    return source, home, environment


def no_engine(_arguments):
    raise AssertionError("modular installation must not initialize native plugins or full-system layers")


def test_modular_setup_installs_only_selected_skill_entrypoints(modular_source):
    source, home, _ = modular_source
    state = SystemState(home)
    assert synthesis_cli.main(["setup", "--profile", "modular", "--skill", "synthesis-writing-craft",
                               "--clients", "claude,codex", "--json"], state=state, engine_runner=no_engine) == 0
    for parent in (home / ".claude/skills", home / ".agents/skills"):
        assert sorted(p.name for p in parent.iterdir()) == ["synthesis-writing-craft"]
        assert (parent / "synthesis-writing-craft/SKILL.md").read_bytes() == (source / "skills/synthesis-writing-craft/SKILL.md").read_bytes()
    assert not (home / ".claude/settings.json").exists()
    assert not (home / ".codex/config.toml").exists()
    assert not (home / "Library/LaunchAgents").exists()
    assert state.read_desired()["modular"]["stage_core"] is True


def test_real_checkpoint_script_runs_from_physically_isolated_closure(modular_source, tmp_path):
    source, home, environment = modular_source
    modular = importlib.import_module("modular")
    plan = modular.resolve_selection(source, ["synthesis-checkpoint"], False)
    target = tmp_path / "isolated"
    modular.materialize_payload(source, target, plan["files"])
    assert not (target / "skills/synthesis-writing-craft").exists()
    run = subprocess.run([sys.executable, "-B", str(target / "skills/synthesis-checkpoint/scripts/refresh.py"), "--help"],
                         cwd=home, env=environment, capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, run.stderr
    assert "synthesis-project-management" in plan["support_skills"]


def test_opt_out_omits_optional_core_from_payload(modular_source, tmp_path):
    source, _, _ = modular_source
    modular = importlib.import_module("modular")
    plan = modular.resolve_selection(source, ["synthesis-writing-craft"], False)
    assert plan["optional_core_files"] == {}
    target = tmp_path / "minimal"
    modular.materialize_payload(source, target, plan["files"])
    assert not (target / "skills/synthesis-article-writing").exists()
    assert not (target / "hooks/hooks.json").exists()


def test_modular_setup_preserves_foreign_collision(modular_source):
    _, home, _ = modular_source
    target = home / ".agents/skills/synthesis-writing-craft"
    target.mkdir(parents=True)
    (target / "SKILL.md").write_text("foreign authored skill")
    code = synthesis_cli.main(["setup", "--profile", "modular", "--skill", "synthesis-writing-craft",
                               "--clients", "codex", "--json"], state=SystemState(home), engine_runner=no_engine)
    assert code != 0
    assert (target / "SKILL.md").read_text() == "foreign authored skill"


def test_modular_status_does_not_claim_live_load(modular_source, capsys):
    _, home, _ = modular_source
    state = SystemState(home)
    assert synthesis_cli.main(["setup", "--profile", "modular", "--skill", "synthesis-writing-craft",
                               "--clients", "codex", "--no-dormant-core", "--json"], state=state, engine_runner=no_engine) == 0
    capsys.readouterr()
    assert synthesis_cli.main(["doctor", "--json"], state=state, engine_runner=no_engine) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["planes"]["live-loaded"]["status"] != "verified"
    assert result["modular"]["stage_core"] is False


def setup_selected(state, **kwargs):
    args = ["setup", "--profile", "modular", "--skill", "synthesis-writing-craft", "--clients", "claude,codex", "--json"]
    if kwargs.get("minimal"):
        args.append("--no-dormant-core")
    return synthesis_cli.main(args, state=state, engine_runner=no_engine)


def test_repair_restores_missing_binding_but_preserves_foreign_replacement(modular_source):
    _, home, _ = modular_source
    state = SystemState(home)
    assert setup_selected(state, minimal=True) == 0
    binding = home / ".agents/skills/synthesis-writing-craft"
    target = binding.readlink()
    binding.unlink()
    assert synthesis_cli.main(["repair", "--json"], state=state, engine_runner=no_engine) == 0
    assert binding.readlink() == target
    binding.unlink()
    binding.mkdir()
    (binding / "SKILL.md").write_text("edited by owner")
    assert synthesis_cli.main(["repair", "--json"], state=state, engine_runner=no_engine) != 0
    assert (binding / "SKILL.md").read_text() == "edited by owner"


def test_receipt_cannot_claim_foreign_link(modular_source):
    import modular
    from system_contract import ContractError
    _, home, _ = modular_source
    state = SystemState(home)
    assert setup_selected(state) == 0
    path = state.state_dir / "modular/receipt.json"
    saved = json.loads(path.read_text())
    saved["bindings"][str(home / "outside/synthesis-writing-craft")] = str(home / "valuable")
    path.write_text(json.dumps(saved))
    with pytest.raises(ContractError):
        modular.receipt(state)


def test_committed_journal_finalizes_after_crash_without_undoing_binding(modular_source, monkeypatch):
    import modular
    _, home, _ = modular_source
    state = SystemState(home)
    finish = modular.finish
    monkeypatch.setattr(modular, "finish", lambda _state: None)
    assert setup_selected(state) == 0
    journal = state.state_dir / "modular/pending.json"
    assert journal.exists()
    binding = home / ".agents/skills/synthesis-writing-craft"
    target = binding.readlink()
    monkeypatch.setattr(modular, "finish", finish)
    with state.locked():
        modular.recover(state)
    assert binding.readlink() == target
    assert not journal.exists()


def test_failed_transaction_rolls_back_owned_bindings_and_retains_foreign_files(modular_source, monkeypatch):
    import modular
    from system_contract import ContractError
    _, home, _ = modular_source
    state = SystemState(home)
    sentinel = home / "kept.txt"
    sentinel.write_text("owner data")
    original = modular.planes
    def fail_after_reconcile(*args, **kwargs):
        original(*args, **kwargs)
        raise ContractError("injected post-mutation failure")
    monkeypatch.setattr(modular, "planes", fail_after_reconcile)
    assert setup_selected(state) != 0
    assert not (home / ".agents/skills/synthesis-writing-craft").exists()
    assert state.read_desired() is None
    assert sentinel.read_text() == "owner data"
    assert state.read_observation()["transactions"][-1]["state"] == "aborted"


def test_opt_out_keeps_preexisting_shared_payloads_and_tool_records(modular_source):
    import modular
    source, home, _ = modular_source
    state = SystemState(home)
    first = modular.stage_tool_core(source, "slopcheck", True, home)
    payload = Path(first["payload"])
    snapshot = {p.relative_to(payload).as_posix(): p.read_bytes() for p in payload.rglob("*") if p.is_file()}
    assert modular.stage_tool_core(source, "ownwords", False, home)["core_state"] == "declined"
    assert modular.stage_tool_core(source, "slopcheck", False, home)["core_state"] == "declined"
    assert {p.relative_to(payload).as_posix(): p.read_bytes() for p in payload.rglob("*") if p.is_file()} == snapshot
    assert state.read_desired() is None
    assert not (home / ".claude").exists()
    assert not (home / ".agents").exists()


def test_dependency_cycle_and_missing_dependency_fail_before_writes(modular_source):
    import modular
    from system_contract import ContractError
    source, home, environment = modular_source
    skill = source / "skills/synthesis-writing-craft/SKILL.md"
    original = skill.read_text()
    for dependency, message in (("synthesis-absent-fixture", "absent"), ("synthesis-writing-craft", "cycle")):
        skill.write_text(original.replace("depends_on: []", 'depends_on: ["%s"]' % dependency))
        subprocess.run(["git", "-C", str(source), "add", "."], check=True, env=environment)
        subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "-C", str(source), "commit", "-qm", "Fixture dependency"], check=True, env=environment)
        with pytest.raises(ContractError, match=message):
            modular.resolve_selection(source, ["synthesis-writing-craft"], False)
    assert not (home / ".agents").exists()


def test_real_cli_modular_full_deactivate_round_trip_preserves_user_data():
    from test_onboard import Sandbox
    box = Sandbox()
    try:
        box.isolate_public_source()
        client = box.fake_client()
        box.seed_currency()
        answers = box.answers()
        environment = {key: value for key, value in os.environ.items() if not key.startswith(("GIT_", "SYNTHESIS_"))}
        environment.update(box.env_overrides())
        environment.update(SYNTHESIS_HOME=str(box.home), SYNTHESIS_CLAUDE_BIN=str(client),
                           SYNTHESIS_CODEX_BIN=str(client), SYNTHESIS_ONBOARD_NO_SERVICES="1",
                           PYTHONDONTWRITEBYTECODE="1", PATH="/usr/bin:/bin:/usr/sbin:/sbin")
        script = box.public_source / "skills/synthesis-onboarding/scripts/synthesis_cli.py"
        def invoke(arguments):
            run = subprocess.run([sys.executable, "-B", str(script), *arguments, "--json"],
                                 env=environment, cwd=box.home, text=True, capture_output=True, timeout=90)
            assert run.returncode == 0, run.stdout + run.stderr
            return json.loads(run.stdout)
        invoke(["setup", "--profile", "modular", "--skill", "synthesis-writing-craft", "--clients", "claude,codex"])
        for root in (box.home / ".claude/skills", box.home / ".agents/skills"):
            assert (root / "synthesis-writing-craft").is_symlink()
        invoke(["activate", "--profile", "full", "--answers", str(answers), "--no-services"])
        sentinel = box.home / "workspaces/retained-user-work.txt"
        sentinel.write_text("retained work")
        invoke(["deactivate"])
        for root in (box.home / ".claude/skills", box.home / ".agents/skills"):
            assert (root / "synthesis-writing-craft").is_symlink()
        assert sentinel.read_text() == "retained work"
        assert SystemState(box.home).read_desired()["profile"] == "modular"
        assert invoke(["doctor"])["planes"]["live-loaded"]["status"] == "not-observed"
    finally:
        box.cleanup()


def test_owned_runtime_registrations_restore_git_and_archive_links(tmp_path, monkeypatch):
    import owned_registrations as ownership
    from onboard import Receipts
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(home / "gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_COUNT", "0")
    subprocess.run(["git", "config", "--global", "core.hooksPath", "/independent/hooks"], check=True)
    receipts = Receipts(home / ".synthesis/onboarding/receipts.json")
    before = ownership.capture(home)
    target = home / ".local/bin/day-end"
    target.parent.mkdir(parents=True)
    target.symlink_to(home / ".synthesis/day-end/bin/day-end")
    plist = home / "Library/LaunchAgents/com.synthesis.day-end-nudge.plist"
    plist.parent.mkdir(parents=True)
    plist.write_text("fixture service")
    subprocess.run(["git", "config", "--global", "core.hooksPath", str(home / ".synthesis/git-hooks")], check=True)
    ownership.record(receipts, home, before, service_started=False)
    report = ownership.retire(receipts, home)
    assert len(report["removed"]) == 2
    assert not target.is_symlink() and not plist.exists()
    assert ownership._git_values() == ["/independent/hooks"]
    assert len(list((home / ".synthesis/onboarding/archives/runtime-registrations").iterdir())) == 2


def test_changed_owned_registration_blocks_without_touching_other_files(tmp_path, monkeypatch):
    import owned_registrations as ownership
    from onboard import Receipts
    from system_contract import ContractError
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(home / "gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_COUNT", "0")
    receipts = Receipts(home / ".synthesis/onboarding/receipts.json")
    before = ownership.capture(home)
    target = home / ".local/bin/day-end"
    target.parent.mkdir(parents=True)
    target.symlink_to(home / "owned")
    ownership.record(receipts, home, before, service_started=False)
    target.unlink()
    target.symlink_to(home / "foreign")
    with pytest.raises(ContractError, match="edited"):
        ownership.retire(receipts, home)
    assert target.readlink() == home / "foreign"


def test_preexisting_runtime_registration_is_retained_without_removal_authority(tmp_path, monkeypatch):
    import owned_registrations as ownership
    from onboard import Receipts
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(home / "gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_COUNT", "0")
    target = home / ".local/bin/day-end"
    target.parent.mkdir(parents=True)
    target.symlink_to(home / "independent")
    subprocess.run(["git", "config", "--global", "core.hooksPath", str(home / ".synthesis/git-hooks")], check=True)
    receipts = Receipts(home / ".synthesis/onboarding/receipts.json")
    ownership.record(receipts, home, ownership.capture(home), service_started=False)
    assert ownership.retire(receipts, home)["removed"] == []
    assert target.readlink() == home / "independent"
    assert ownership._git_values() == [str(home / ".synthesis/git-hooks")]


def test_owned_service_is_stopped_before_registration_removal(tmp_path, monkeypatch):
    import owned_registrations as ownership
    from onboard import Receipts
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(home / "gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_COUNT", "0")
    receipts = Receipts(home / ".synthesis/onboarding/receipts.json")
    before = ownership.capture(home)
    plist = home / "Library/LaunchAgents/com.synthesis.day-end-nudge.plist"
    plist.parent.mkdir(parents=True)
    plist.write_text("owned fixture service")
    ownership.record(receipts, home, before, service_started=True)
    real_run = subprocess.run
    running = [True]
    calls = []
    def run(arguments, **kwargs):
        if arguments[0] != "launchctl":
            return real_run(arguments, **kwargs)
        calls.append(arguments[1])
        if arguments[1] == "bootout":
            assert plist.is_file()
            running[0] = False
            return subprocess.CompletedProcess(arguments, 0)
        return subprocess.CompletedProcess(arguments, 0 if running[0] else 3)
    monkeypatch.setattr(ownership.sys, "platform", "darwin")
    monkeypatch.setattr(ownership.subprocess, "run", run)
    ownership.retire(receipts, home)
    assert calls == ["print", "bootout", "print"]
    assert not plist.exists()


def test_no_synthesis_native_config_is_written_by_tool_staging_cli(modular_source):
    _, home, _ = modular_source
    state = SystemState(home)
    assert synthesis_cli.main(["stage-core", "--for-tool", "console", "--no-dormant-core", "--json"],
                               state=state, engine_runner=no_engine) == 0
    assert state.read_desired() is None
    assert not (home / ".claude").exists()
    assert not (home / ".codex").exists()
    assert not (home / ".local/bin/synthesis").exists()


def test_installed_projected_cli_transfers_default_tool_staging_to_full_bootstrap(modular_source, monkeypatch):
    _, home, _ = modular_source
    active = {"projection": {"kind": "modular"}, "channel": "pin", "version": "4.100.3"}
    monkeypatch.setattr(synthesis_cli, "_active_release", lambda: active)
    calls = []
    monkeypatch.setattr(synthesis_cli, "_run_release_bootstrap", lambda argv, descriptor, channel, pin: calls.append((argv, descriptor, channel, pin)) or 0)
    args = ["stage-core", "--for-tool", "slopcheck", "--json"]
    assert synthesis_cli.main(args, state=SystemState(home), engine_runner=no_engine) == 0
    assert calls == [(args, active, "stable", "4.100.3")]


def test_modular_doctor_default_output_explains_local_and_live_state(modular_source, capsys):
    _, home, _ = modular_source
    state = SystemState(home)
    assert setup_selected(state, minimal=True) == 0
    capsys.readouterr()
    assert synthesis_cli.main(["doctor"], state=state, engine_runner=no_engine) == 0
    text = capsys.readouterr().out
    assert "Synthesis modular installation: PASS" in text
    assert "live-loaded: not-observed" in text
    assert "Next action:" in text


@pytest.mark.parametrize('corruption', ['invented', 'commit', 'transaction', 'source-bytes'])
def test_doctor_requires_independent_source_and_committed_selection_binding(modular_source, corruption):
    import modular
    from system_contract import ContractError
    source, home, _ = modular_source
    state = SystemState(home)
    assert setup_selected(state, minimal=True) == 0
    path = state.state_dir / 'modular/receipt.json'
    value = json.loads(path.read_text())
    if corruption == 'invented':
        value['source'] = {'kind': 'invented', 'root': '/does/not/exist', 'commit': 'NOT_A_COMMIT', 'content_digest': 'NOT_A_DIGEST'}
    elif corruption == 'commit':
        value['source']['commit'] = '0' * 40
    elif corruption == 'transaction':
        observation = state.read_observation()
        observation['transactions'][-1]['committed_desired_digest'] = '0' * 64
        state.observation_path.write_text(json.dumps(observation))
    else:
        (source / 'skills/synthesis-writing-craft/SKILL.md').write_text('changed after installation')
    path.write_text(json.dumps(value))
    try:
        report = modular.inspect(state)
    except ContractError:
        return
    assert report['status'] == 'FAIL'
    assert report['planes']['source-provenance']['status'] != 'verified'


@pytest.mark.parametrize("changed", ["none", "desired", "payload", "binding", "receipt", "journal"])
def test_prepared_modular_transition_recovers_after_desired_write(modular_source, changed):
    import modular
    source, home, environment = modular_source
    state = SystemState(home)
    assert setup_selected(state, minimal=True) == 0
    script = r'''import os,pathlib,sys
sys.path.insert(0,sys.argv[1])
import modular
from system_contract import SystemState,default_desired_state
state=SystemState(pathlib.Path(sys.argv[2]))
new=default_desired_state('skills-only',['claude','codex'],'stable',modular=state.read_desired()['modular'])
original=state._save_observation
def crash_at_commit(observation):
 if observation['transactions'][-1]['state']=='committed': os._exit(99)
 original(observation)
state._save_observation=crash_at_commit
def operation(tx):
 modular.suspend(state,tx)
 return {'_desired':new}
state.run_transaction('activate',new,operation)
'''
    result = subprocess.run([sys.executable, '-B', '-c', script, str(source / 'skills/synthesis-onboarding/scripts'), str(home)],
                            env=environment, text=True, capture_output=True, timeout=30)
    assert result.returncode == 99, result.stdout + result.stderr
    journal = state.state_dir / 'modular/pending.json'
    receipt_path = state.state_dir / 'modular/receipt.json'
    value = json.loads(receipt_path.read_text())
    if changed != 'none':
        from system_contract import ContractError
        if changed == 'desired':
            desired = state.read_desired(); desired['clients'] = ['codex']
            state.desired_path.write_text(json.dumps(desired))
        elif changed == 'payload':
            (Path(value['payload'])/'skills/synthesis-writing-craft/SKILL.md').write_text('concurrent payload edit')
        elif changed == 'binding':
            foreign = home/'retained-foreign'; foreign.mkdir()
            (foreign/'SKILL.md').write_text('retained foreign content')
            (home/'.agents/skills/synthesis-writing-craft').symlink_to(foreign)
        elif changed == 'receipt':
            value['optional_core_bytes'] += 1
            receipt_path.write_text(json.dumps(value))
        else:
            edit = json.loads(journal.read_text()); edit['new']['optional_core_bytes'] += 1
            journal.write_text(json.dumps(edit))
        snapshots = {path: path.read_bytes() for path in (journal, receipt_path, state.desired_path, state.observation_path)}
        with state.locked():
            with pytest.raises(ContractError): modular.recover(state)
        assert {path: path.read_bytes() for path in snapshots} == snapshots
        if changed == 'binding': assert (foreign/'SKILL.md').read_text() == 'retained foreign content'
        return
    with state.locked():
        modular.recover(state)
    assert state.read_desired()['profile'] == 'skills-only'
    assert state.read_observation()['transactions'][-1]['state'] == 'committed'
    assert not (home / '.agents/skills/synthesis-writing-craft').is_symlink()
    assert not (state.state_dir / 'modular/pending.json').exists()


def test_installed_optout_to_staged_transfers_to_complete_release(modular_source, monkeypatch):
    source, home, _ = modular_source
    active = {'projection': {'selection': {'roots': ['synthesis-writing-craft'], 'stage_core': False}},
              'channel': 'pin', 'version': '4.100.3'}
    monkeypatch.setattr(synthesis_cli, '_active_release', lambda: active)
    monkeypatch.setattr(synthesis_cli, '_active_matches_policy', lambda *args: True)
    calls = []
    monkeypatch.setattr(synthesis_cli, '_run_release_bootstrap', lambda argv, descriptor, channel, pin: calls.append((argv, descriptor, channel, pin)) or 0)
    args = ['setup', '--profile', 'modular', '--skill', 'synthesis-writing-craft', '--clients', 'codex', '--pin', '4.100.3', '--json']
    assert synthesis_cli.main(args, state=SystemState(home), engine_runner=no_engine) == 0
    assert calls == [(args, active, 'stable', '4.100.3')]


def test_actual_managed_launcher_adds_dormant_core_after_prior_optout(modular_source, tmp_path):
    import shutil
    source, home, environment = modular_source
    version = json.loads((source / '.claude-plugin/plugin.json').read_text())['version']
    subprocess.run(['git', '-C', str(source), 'tag', 'v' + version], env=environment, check=True)
    mirror = home / '.cache/synthesis/acquisition/synthesis-skills.git'
    mirror.parent.mkdir(parents=True)
    subprocess.run(['git', 'clone', '--bare', str(source), str(mirror)], env=environment, check=True, capture_output=True)
    subprocess.run(['git', '--git-dir=' + str(mirror), 'remote', 'set-url', 'origin', 'https://github.com/synthesisengineering/synthesis-skills.git'], env=environment, check=True)
    traps = tmp_path / 'offline-bin'; traps.mkdir()
    real_git = shutil.which('git')
    (traps / 'git').write_text('#!/bin/sh\nfor arg in "$@"; do if [ "$arg" = fetch ]; then exit 1; fi; done\nexec ' + real_git + ' "$@"\n')
    (traps / 'git').chmod(0o755)
    environment.update(SYNTHESIS_HOME=str(home), SYNTHESIS_RUNTIME_POLICY='packaged-python-v1',
                       SYNTHESIS_BOOTSTRAP_PYTHON=sys.executable, SYNTHESIS_ONBOARD_ALLOW_STALE='1',
                       PATH=str(traps)+os.pathsep+environment['PATH'])
    launcher = home / '.local/bin/synthesis'; active = home / '.local/state/synthesis/active-release.json'
    args = ['setup','--profile','modular','--skill','synthesis-writing-craft','--clients','codex','--pin',version,'--json']
    command = [sys.executable,'-B',str(source/'skills/synthesis-onboarding/scripts/bootstrap.py'),'--checkout',str(source),
               '--releases-dir',str(home/'.cache/synthesis/releases'),'--launcher',str(launcher),'--active-descriptor',str(active),
               '--channel','pin','--ref','v'+version,'--source-url','https://github.com/synthesisengineering/synthesis-skills.git','--']
    initial = subprocess.run(command+args+['--no-dormant-core'],cwd=home,env=environment,capture_output=True,text=True,timeout=90)
    assert initial.returncode == 0, initial.stdout+initial.stderr
    old = json.loads(active.read_text())
    assert old['projection']['selection']['stage_core'] is False
    changed = subprocess.run([str(launcher),*args],cwd=home,env=environment,capture_output=True,text=True,timeout=90)
    assert changed.returncode == 0, changed.stdout+changed.stderr
    current = json.loads(active.read_text())
    receipt = json.loads((home/'.local/state/synthesis/modular/receipt.json').read_text())
    assert current['projection']['selection']['stage_core'] is True
    assert receipt['optional_core_bytes'] > 0
    assert (Path(receipt['payload'])/'skills/synthesis-article-writing/SKILL.md').is_file()
    assert not (Path(old['release_root'])/'skills/synthesis-article-writing/SKILL.md').exists()
    checked = subprocess.run([str(launcher),'doctor','--json'],cwd=home,env=environment,capture_output=True,text=True,timeout=90)
    assert checked.returncode == 0, checked.stdout+checked.stderr


@pytest.mark.parametrize('boundary', ['prepared', 'engine-return'])
def test_real_activation_crash_recovers_engine_and_modular_state(boundary):
    import modular
    from test_onboard import Sandbox
    box = Sandbox()
    try:
        box.isolate_public_source()
        client = box.fake_client(); box.seed_currency(); answers = box.answers()
        environment = {key: value for key, value in os.environ.items() if not key.startswith(('GIT_', 'SYNTHESIS_'))}
        environment.update(box.env_overrides())
        environment.update(SYNTHESIS_HOME=str(box.home), SYNTHESIS_CLAUDE_BIN=str(client), SYNTHESIS_CODEX_BIN=str(client),
                           SYNTHESIS_ONBOARD_NO_SERVICES='1', PYTHONDONTWRITEBYTECODE='1', PATH='/usr/bin:/bin:/usr/sbin:/sbin')
        script = box.public_source / 'skills/synthesis-onboarding/scripts/synthesis_cli.py'
        def invoke(args):
            return subprocess.run([sys.executable,'-B',str(script),*args,'--json'],env=environment,cwd=box.home,text=True,capture_output=True,timeout=90)
        initial = invoke(['setup','--profile','modular','--skill','synthesis-writing-craft','--clients','claude,codex'])
        assert initial.returncode == 0, initial.stdout+initial.stderr
        crash = r'''import os,sys
sys.path.insert(0,sys.argv[1])
import synthesis_cli
from system_contract import SystemState
boundary=sys.argv[2]
if boundary=='prepared':
 original=SystemState._save_observation
 def save(self,observation):
  tx=observation['transactions'][-1]
  if tx['command']=='activate' and tx['state']=='committed': os._exit(99)
  original(self,observation)
 SystemState._save_observation=save
else:
 original=synthesis_cli._execute_engine
 def execute(*args,**kwargs):
  result=original(*args,**kwargs)
  if result[0]==0: os._exit(99)
  return result
 synthesis_cli._execute_engine=execute
raise SystemExit(synthesis_cli.main(sys.argv[3:]))
'''
        result = subprocess.run([sys.executable,'-B','-c',crash,str(script.parent),boundary,'activate','--profile','full','--answers',str(answers),'--no-services','--json'],
                                env=environment,cwd=box.home,text=True,capture_output=True,timeout=90)
        assert result.returncode == 99, result.stdout+result.stderr
        state = SystemState(box.home)
        pending = state.read_observation()['transactions'][-1]
        assert pending['state'] == 'pending'
        journal = state.state_dir/'modular/pending.json'
        assert journal.exists()
        if boundary == 'prepared':
            def content():
                return {p.relative_to(box.home).as_posix(): ('link',str(p.readlink())) if p.is_symlink() else ('file',p.read_bytes())
                        for parent in ('.claude','.codex','.agents','.synthesis') for p in (box.home/parent).rglob('*') if p.is_file() or p.is_symlink()}
            before = content()
            with state.locked(): modular.recover(state)
            assert content() == before, 'prepared recovery must preserve completed engine changes exactly'
            assert state.read_desired()['profile'] == 'full'
            assert state.read_observation()['transactions'][-1]['state'] == 'committed'
            assert not (box.home/'.agents/skills/synthesis-writing-craft').is_symlink()
        else:
            with state.locked():
                with pytest.raises(Exception, match='engine recovery'):
                    modular.recover(state)
            assert journal.exists(), 'lack of engine recovery must retain the obligation'
            repaired = invoke(['repair'])
            assert repaired.returncode == 0, repaired.stdout+repaired.stderr
            assert state.read_desired()['profile'] == 'modular'
            assert state.read_observation()['transactions'][-2]['state'] == 'aborted'
            assert (box.home/'.agents/skills/synthesis-writing-craft').is_symlink()
            assert (box.home/'.claude/skills/synthesis-writing-craft').is_symlink()
        assert not journal.exists()
    finally:
        box.cleanup()

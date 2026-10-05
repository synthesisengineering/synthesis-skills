import copy
import importlib.util
import json
from pathlib import Path
import sys
import pytest

ENGINE = Path(__file__).with_name('message_guard.py')
spec = importlib.util.spec_from_file_location('client_repair_guard', ENGINE)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)
P = ENGINE.parents[3]
sys.path.insert(0, str(P / 'skills/synthesis-onboarding/scripts'))
import onboard  # noqa: E402


def legacy_config():
    cfg = json.loads((ENGINE.parent.parent / 'patterns.example.json').read_text())
    cfg['message_capabilities'] = [{
        'tool_names': ['mcp__workspace_mcp__send_gmail_message'],
        'channel': 'email', 'body_field': 'body', 'format_field': 'body_format',
    }]
    return cfg


def inventory(client, names):
    return {'client': client, 'source': 'synthetic complete native catalog',
            'complete': True, 'next_cursor': None, 'total_tools': len(names),
            'tools': [{'name': name, 'input_schema': {'type': 'object'}} for name in names]}


def test_legacy_missing_client_name_is_reported_before_send():
    cfg = legacy_config()
    assert guard.capability_for('mcp__workspace_mcp__send_gmail_message', cfg)['channel'] == 'email'
    with pytest.raises(ValueError, match='exactly one'):
        guard.capability_for('mcp__workspace-mcp__send_gmail_message', cfg)
    result = guard.client_capability_check([inventory('claude', ['mcp__workspace-mcp__send_gmail_message'])], cfg)
    assert result['status'] == 'OWNER_REVIEW_REQUIRED'
    assert result['clients'][0]['unresolved'] == ['mcp__workspace-mcp__send_gmail_message']


def test_muse_uses_its_own_nested_hook_path(tmp_path, monkeypatch):
    monkeypatch.setattr(onboard, 'HOME', tmp_path)
    assert onboard.message_guard_hook_path('muse') == tmp_path / '.config/muse/settings.json'


def all_catalogs():
    return [inventory(client, [name]) for client, name in [
        ('claude', 'mcp__workspace-mcp__send_gmail_message'),
        ('codex', 'mcp__workspace_mcp__send_gmail_message'),
        ('muse', 'mcp__workspace-mcp__send_gmail_message')]]


def test_plan_adds_only_exact_observed_spelling_and_preserves_all_policy():
    cfg = legacy_config()
    cfg['owner_extension'] = {'approval': 'unchanged', 'nested': [1, 2]}
    before = copy.deepcopy(cfg)
    result = guard.client_capability_plan(all_catalogs(), cfg)
    assert cfg == before
    expected = copy.deepcopy(before)
    expected['message_capabilities'][0]['tool_names'].append('mcp__workspace-mcp__send_gmail_message')
    assert result['effective_configuration'] == expected
    assert len(result['additions']) == 1
    assert [row['client'] for row in result['clients']] == ['claude', 'codex', 'muse']
    assert not any(row['unresolved'] for row in result['clients'])
    assert result['message_authority_granted'] is False
    assert result['native_inventory_provenance_verified'] is False


@pytest.mark.parametrize('name', [
    'mcp__unrelated-server__send_gmail_message',
    'mcp__workspace--mcp__send_gmail_message',
    'mcp__workspace-mcp__delete_message',
])
def test_no_general_hyphen_or_unrelated_tool_authority(name):
    cfg = legacy_config()
    cfg['gated_tool_patterns'] = ['.*']
    with pytest.raises(ValueError, match='unrecognized exact'):
        guard.client_capability_plan([inventory('claude', [name])], cfg)
    with pytest.raises(ValueError, match='exactly one'):
        guard.capability_for(name, cfg)


@pytest.mark.parametrize('fault', ['partial', 'duplicate-client', 'wrong-channel', 'ambiguous'])
def test_plan_refuses_incomplete_or_conflicting_owner_inputs(fault):
    cfg = legacy_config()
    catalogs = all_catalogs()
    if fault == 'partial':
        catalogs[0]['complete'] = False
    elif fault == 'duplicate-client':
        catalogs.append(copy.deepcopy(catalogs[0]))
    elif fault == 'wrong-channel':
        cfg['message_capabilities'][0]['channel'] = 'human-text'
    else:
        cfg['message_capabilities'].append(copy.deepcopy(cfg['message_capabilities'][0]))
    with pytest.raises(ValueError):
        guard.client_capability_plan(catalogs, cfg)


def test_regex_defaults_already_classify_both_spellings_without_repair():
    cfg = legacy_config()
    cfg['message_capabilities'] = copy.deepcopy(guard.DEFAULT_MESSAGE_CAPABILITIES)
    result = guard.client_capability_plan(all_catalogs(), cfg)
    assert result['additions'] == []
    assert result['effective_configuration'] == cfg


def state_fixture(tmp_path, monkeypatch, already_repaired=False):
    import hashlib
    state = tmp_path / 'home/.synthesis/message-guard'
    state.mkdir(parents=True)
    cfg = legacy_config()
    if already_repaired:
        cfg = guard.client_capability_plan(all_catalogs(), cfg)['effective_configuration']
    raw = (json.dumps(cfg, indent=3) + '\n\n').encode()
    path = state / 'patterns.json'
    path.write_bytes(raw)
    path.chmod(0o600)
    (state / 'ledger').mkdir()
    pending = state / 'ledger/pending.json'
    pending.write_text('retained historical pending bytes')
    monkeypatch.setenv('MESSAGE_GUARD_CONFIG', str(path))
    monkeypatch.setenv('MESSAGE_GUARD_STATE_DIR', str(state))
    monkeypatch.delenv('MESSAGE_GUARD_CAPABILITIES', raising=False)
    proposal = guard.client_capability_plan(all_catalogs(), cfg)
    request = {'inventories': all_catalogs(), 'expected_config_sha256': hashlib.sha256(raw).hexdigest(),
               'reviewed_configuration_sha256': proposal['configuration_sha256'],
               'owner_review': {'source': 'synthetic explicit configuration owner review',
                                'reviewed_at': '2026-10-01T00:00:00Z'}}
    return state, cfg, request, raw


def test_apply_rebinds_migration_and_retains_all_pending_and_preimages(tmp_path, monkeypatch):
    state, cfg, request, raw = state_fixture(tmp_path, monkeypatch)
    old_record = b'{"retained":"old owner review"}\n'
    (state / 'engine-migration.json').write_bytes(old_record)
    pending = (state / 'ledger/pending.json').read_bytes()
    result = guard.client_capability_apply(request, cfg)
    assert result['status'] == 'READY_FOR_OWNER_ACTIVATION'
    assert result['message_authority_granted'] is False
    assert (Path(result['history']) / 'patterns.json').read_bytes() == raw
    assert (Path(result['history']) / 'engine-migration.json').read_bytes() == old_record
    assert (state / 'ledger/pending.json').read_bytes() == pending
    assert guard.migration_preflight()['status'] == 'READY_FOR_OWNER_ACTIVATION'
    installed = json.loads((state / 'patterns.json').read_text())
    assert not guard.declared_spelling_gaps(installed)
    assert guard.capability_for('mcp__workspace-mcp__send_gmail_message', installed)['channel'] == 'email'


@pytest.mark.parametrize('fault', ['config-cas', 'proposal-cas', 'future-review', 'unattributed-review'])
def test_apply_refuses_changed_or_unreviewed_inputs_without_replacing_policy(tmp_path, monkeypatch, fault):
    state, cfg, request, raw = state_fixture(tmp_path, monkeypatch)
    if fault == 'config-cas':
        request['expected_config_sha256'] = '0' * 64
    elif fault == 'proposal-cas':
        request['reviewed_configuration_sha256'] = '0' * 64
    elif fault == 'future-review':
        request['owner_review']['reviewed_at'] = '2999-01-01T00:00:00Z'
    else:
        request['owner_review']['source'] = ''
    with pytest.raises(ValueError):
        guard.client_capability_apply(request, cfg)
    assert (state / 'patterns.json').read_bytes() == raw
    assert not (state / 'engine-migration.json').exists()
    assert (state / 'ledger/pending.json').read_text() == 'retained historical pending bytes'


def test_already_working_policy_keeps_exact_bytes(tmp_path, monkeypatch):
    state, cfg, request, raw = state_fixture(tmp_path, monkeypatch, already_repaired=True)
    result = guard.client_capability_apply(request, cfg)
    assert result['additions'] == []
    assert (state / 'patterns.json').read_bytes() == raw


def test_all_client_repair_preserves_muse_settings_config_and_ledgers(tmp_path, monkeypatch):
    state, cfg, request, raw = state_fixture(tmp_path, monkeypatch, already_repaired=True)
    guard.client_capability_apply(request, cfg)
    home = state.parents[1]
    monkeypatch.setattr(onboard, 'HOME', home)
    monkeypatch.setattr(onboard, 'STATE_DIR', home / '.synthesis/onboarding')
    monkeypatch.setattr(onboard, 'source_root', lambda: P)
    muse = home / '.config/muse/settings.json'
    muse.parent.mkdir(parents=True)
    settings = {'model': 'fixture-owned-model', 'provider': 'fixture-provider',
                'hooks': {'Stop': [{'hooks': [{'type': 'command', 'command': 'fixture-stop'}]}]}}
    muse.write_text(json.dumps(settings))
    args = onboard.build_parser().parse_args(['message-guard-repair', '--clients', 'claude,codex,muse', '--json'])
    assert onboard.repair_message_guard(args) == 0
    after = json.loads(muse.read_text())
    assert after['model'] == settings['model'] and after['provider'] == settings['provider']
    assert after['hooks']['Stop'] == settings['hooks']['Stop']
    for client in ('claude', 'codex', 'muse'):
        hook_path = onboard.message_guard_hook_path(client)
        assert guard.hook_config_covers(hook_path, ['mcp__workspace-mcp__send_gmail_message'])
    before_second = muse.read_bytes()
    assert onboard.repair_message_guard(args) == 0
    assert muse.read_bytes() == before_second
    assert (state / 'patterns.json').read_bytes() == raw
    assert (state / 'ledger/pending.json').read_text() == 'retained historical pending bytes'


def test_bad_muse_settings_refuse_before_any_runtime_activation(tmp_path, monkeypatch):
    state, cfg, request, _ = state_fixture(tmp_path, monkeypatch)
    guard.client_capability_apply(request, cfg)
    home = state.parents[1]
    monkeypatch.setattr(onboard, 'HOME', home)
    monkeypatch.setattr(onboard, 'STATE_DIR', home / '.synthesis/onboarding')
    monkeypatch.setattr(onboard, 'source_root', lambda: P)
    muse = home / '.config/muse/settings.json'
    muse.parent.mkdir(parents=True)
    muse.write_text('{"hooks":{"PreToolUse":"malformed"}}')
    args = onboard.build_parser().parse_args(['message-guard-repair', '--clients', 'claude,muse'])
    assert onboard.repair_message_guard(args) != 0
    assert not (home / '.claude/settings.json').exists()
    assert not (state / 'message_guard.py').exists()


def test_doctor_detects_capability_gap_despite_broad_matcher(tmp_path, monkeypatch, capsys):
    state, _, _, _ = state_fixture(tmp_path, monkeypatch)
    home = state.parents[1]
    monkeypatch.setenv('HOME', str(home))
    monkeypatch.setenv('MESSAGE_GUARD_MUSE_SETTINGS', str(home / '.config/muse/settings.json'))
    assert guard.run_doctor() != 0
    printed = capsys.readouterr().out
    assert 'exact client tool spellings resolve' in printed
    assert 'mcp__workspace-mcp__send_gmail_message' in printed


def test_supplied_complete_catalog_checks_each_actual_gated_name():
    cfg = legacy_config()
    cfg['gated_tool_patterns'] = ['.*']
    result = guard.client_capability_check([inventory('muse', ['mcp__workspace_mcp__send_gmail_message', 'unknown.send'])], cfg)
    assert result['clients'][0]['unresolved'] == ['unknown.send']


def finite_dispatch_fixture():
    cfg = legacy_config()
    observed = inventory('codex', ['mcp__workspace_mcp__send_gmail_message'])
    proposal = guard.capability_plan(observed, cfg)
    row = proposal['proposals'][0]
    capability = copy.deepcopy(row['capability'])
    capability.pop('tool_names', None)
    registry = guard.capability_enroll({
        'inventory': observed,
        'owner_review': {'inventory_digest': proposal['inventory_digest'],
                         'source': 'synthetic finite catalog owner review'},
        'decisions': [{'name': row['name'], 'descriptor_sha256': row['descriptor_sha256'],
                       'capability': capability}],
    }, cfg)
    return {**cfg, 'message_capabilities': registry['capabilities'],
            '_capability_registry': registry}, observed


def test_finite_dispatch_catalog_does_not_require_an_unobserved_alias():
    cfg, observed = finite_dispatch_fixture()
    assert guard.declared_spelling_gaps(cfg) == []
    result = guard.client_capability_check([observed], cfg)
    assert result['status'] == 'DECLARED_CLIENT_INVENTORIES_CLASSIFIED'
    with pytest.raises(ValueError, match='exactly one'):
        guard.capability_for('mcp__workspace-mcp__send_gmail_message', cfg)
    assert guard.declared_spelling_gaps(legacy_config()) == [
        'mcp__workspace-mcp__send_gmail_message']


@pytest.mark.parametrize('drift', ['added-alias', 'removed', 'descriptor', 'client'])
def test_client_check_keeps_exact_finite_dispatch_inventory_contract(drift):
    cfg, observed = finite_dispatch_fixture()
    if drift == 'added-alias':
        observed['tools'].append({'name': 'mcp__workspace-mcp__send_gmail_message',
                                  'input_schema': {'type': 'object'}})
        observed['total_tools'] = 2
    elif drift == 'removed':
        observed['tools'] = []
        observed['total_tools'] = 0
    elif drift == 'descriptor':
        observed['tools'][0]['input_schema']['description'] = 'changed descriptor'
    else:
        observed['client'] = 'muse'
    with pytest.raises(ValueError):
        guard.client_capability_check([observed], cfg)


@pytest.mark.parametrize('kind', ['fifo', 'symlink', 'oversized'])
def test_repair_cli_refuses_unsafe_config_before_generic_loading(tmp_path, kind):
    import os
    import subprocess
    path = tmp_path / 'patterns.json'
    if kind == 'fifo':
        os.mkfifo(path)
    elif kind == 'symlink':
        target = tmp_path / 'target.json'
        target.write_text(json.dumps(legacy_config()))
        path.symlink_to(target)
    else:
        path.write_bytes(b' ' * (1024 * 1024 + 1))
    env = {k: v for k, v in os.environ.items() if not k.startswith('MESSAGE_GUARD_')}
    env.update(MESSAGE_GUARD_CONFIG=str(path), MESSAGE_GUARD_STATE_DIR=str(tmp_path))
    result = subprocess.run([sys.executable, '-B', str(ENGINE), '--client-capability-plan'],
                            input='[]', text=True, capture_output=True, env=env, timeout=3)
    assert result.returncode == 2
    assert 'refused' in result.stderr


@pytest.mark.parametrize("signature", [
    "◆ <https://example.invalid/|Example>",
    "◆ <https://example.invalid/>",
    "◆ [Example](https://example.invalid/)",
])
def test_link_signature_scan_and_gate_agree(tmp_path, signature):
    import os
    import subprocess
    from datetime import datetime, timezone
    cfg = legacy_config()
    cfg['message_capabilities'] = copy.deepcopy(guard.DEFAULT_MESSAGE_CAPABILITIES)
    cfg['block_patterns'] = [{'name': 'missing-link',
        'regex': r'(?s)\A(?!.*example\.invalid).*◆'}]
    cfg['warn_patterns'] = []
    path = tmp_path / 'config.json'
    path.write_text(json.dumps(cfg))
    state = tmp_path / 'state'
    (state / 'ledger').mkdir(parents=True)
    tool = 'mcp__fixture__slack_send_message'
    body = {'message': signature}
    digest = guard.message_digest(tool, body)
    (state / 'ledger' / (digest + '.json')).write_text(json.dumps({
        'created_at': datetime.now(timezone.utc).isoformat(),
        'message_sha256': digest, 'is_reply': False, 'no_factual_claims': True,
        'voice_rules_pass': True, 'invented_precision_scan': True,
        'recipient_address_check': True, 'ragbot_branding_check': True,
    }))
    env = dict(os.environ, MESSAGE_GUARD_CONFIG=str(path),
               MESSAGE_GUARD_STATE_DIR=str(state))
    scan = subprocess.run([sys.executable, '-B', str(ENGINE), '--scan'],
        input=signature, text=True, capture_output=True, timeout=5, env=env)
    gate = subprocess.run([sys.executable, '-B', str(ENGINE), '--gate'],
        input=json.dumps({'tool_name': tool, 'tool_input': body}),
        text=True, capture_output=True, timeout=5, env=env)
    assert scan.returncode == 0, scan.stderr + scan.stdout
    assert gate.returncode == 0, gate.stderr


@pytest.mark.parametrize('text,pattern', [
    ('◆ Example', r'(?s)\A(?!.*example\.invalid).*◆'),
    ('for<em>bidden</em> <https://example.invalid/|Example>', r'forbidden'),
    ('<https://example.invalid/|for&#98;idden>', r'forbidden'),
])
def test_register_inspection_retains_refusals_in_scan_and_gate(tmp_path, text, pattern):
    import os
    import subprocess
    cfg = legacy_config()
    cfg['message_capabilities'] = copy.deepcopy(guard.DEFAULT_MESSAGE_CAPABILITIES)
    cfg['block_patterns'] = [{'name': 'fixture-refusal', 'regex': pattern}]
    cfg['warn_patterns'] = []
    path = tmp_path / 'config.json'
    path.write_text(json.dumps(cfg))
    env = dict(os.environ, MESSAGE_GUARD_CONFIG=str(path),
               MESSAGE_GUARD_STATE_DIR=str(tmp_path / 'state'))
    scan = subprocess.run([sys.executable, '-B', str(ENGINE), '--scan'],
        input=text, text=True, capture_output=True, timeout=5, env=env)
    gate = subprocess.run([sys.executable, '-B', str(ENGINE), '--gate'],
        input=json.dumps({'tool_name': 'mcp__fixture__slack_send_message',
                          'tool_input': {'message': text}}),
        text=True, capture_output=True, timeout=5, env=env)
    assert scan.returncode == 2 and 'fixture-refusal' in scan.stdout, scan.stdout
    assert gate.returncode == 2 and 'register scan' in gate.stderr, gate.stderr

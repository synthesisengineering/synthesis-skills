"""Actual fixed-format transports must have a usable explicit policy override."""
import importlib.util
from pathlib import Path
import pytest
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

spec = importlib.util.spec_from_file_location('fixed_format_guard', Path(__file__).with_name('message_guard.py'))
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)
TOOL = 'mcp__synthetic_mail__send_email'


def cap(**changes):
    return {'tool_names': [TOOL], 'channel': 'email', 'body_field': 'body',
            'fixed_format': 'plain', **changes}


def cfg(**changes):
    return {'message_capabilities': [cap()], **changes}


def request(capability):
    inventory = {'client': 'codex', 'source': 'synthetic fixed-format schema',
                 'tools': [{'name': TOOL, 'input_schema': {'type': 'object', 'properties': {'body': {'type': 'string'}}}}],
                 'complete': True, 'total_tools': 1, 'next_cursor': None}
    snapshot = guard.inventory_snapshot(inventory)
    return {'inventory': inventory,
            'owner_review': {'inventory_digest': snapshot['inventory_digest'], 'source': 'synthetic owner'},
            'decisions': [{'name': TOOL, 'descriptor_sha256': snapshot['tools'][0]['descriptor_sha256'],
                           'capability': {k: v for k, v in capability.items() if k != 'tool_names'}}]}


def test_fixed_plain_transport_still_refuses_html_default():
    failures = guard.email_format_failures(TOOL, {'body': 'Synthetic paragraph.'}, cfg())
    assert failures and any('requires html' in f for f in failures)


def test_explicit_plain_policy_works_without_phantom_format_argument():
    assert guard.email_format_failures(TOOL, {'body': 'Synthetic paragraph.'}, cfg(email_policy={'default_format': 'plain'})) == []


def test_fixed_transport_does_not_accept_payload_format_override():
    failures = guard.email_format_failures(TOOL, {'body': '<p>Synthetic.</p>', 'body_format': 'html'}, cfg())
    assert failures and any('requires html' in f for f in failures)


def test_fixed_plain_transport_preserves_paragraph_check():
    assert guard.email_format_failures(TOOL, {'body': 'One line\nwrapped line.'}, cfg(email_policy={'default_format': 'plain'}))


def test_fixed_format_enrollment_and_readiness_round_trip():
    value = request(cap())
    registry = guard.capability_enroll(value, {})
    assert guard.validate_capability_registry(registry) == registry
    assert guard.capability_readiness(value['inventory'], {'_capability_registry': registry, 'message_capabilities': registry['capabilities']})['status'] == 'READY_FOR_OWNER_ACTIVATION'


@pytest.mark.parametrize('change', [
    {'fixed_format': 'markdown'}, {'fixed_format': True},
    {'fixed_format': ''}, {'format_field': 'format'},
    {'html_value': 'html'}, {'plain_value': 'text'},
])
def test_invalid_or_ambiguous_fixed_mapping_refuses(change):
    with pytest.raises(ValueError):
        guard.capability_for(TOOL, {'message_capabilities': [cap(**change)]})


def test_registry_cannot_change_fixed_format_after_enrollment():
    value = request(cap())
    registry = guard.capability_enroll(value, {})
    registry['capabilities'][0]['format_field'] = 'format'
    with pytest.raises(ValueError):
        guard.validate_capability_registry(registry)


def test_actual_gate_plain_override_consumes_only_exact_synthetic_approval(tmp_path):
    root = Path(__file__).parent.parent
    config = json.loads((root / 'patterns.example.json').read_text())
    config.update(cfg(email_policy={'default_format': 'plain'}))
    config['gated_tool_patterns'] = ['^' + re.escape(TOOL) + '$']
    config_path = tmp_path / 'patterns.json'
    config_path.write_text(json.dumps(config))
    body = {'body': 'Synthetic test paragraph.', 'subject': 'Fixture', 'to': 'reader@example.test'}
    digest = guard.message_digest(TOOL, body)
    state = tmp_path / 'state'
    (state / 'ledger').mkdir(parents=True)
    approval = state / 'ledger' / (digest + '.json')
    approval.write_text(json.dumps({'created_at': datetime.now(timezone.utc).isoformat(),
        'message_sha256': digest, 'is_reply': False, 'no_factual_claims': True,
        'voice_rules_pass': True, 'invented_precision_scan': True, 'recipient_address_check': True}))
    env = {**os.environ, 'MESSAGE_GUARD_CONFIG': str(config_path), 'MESSAGE_GUARD_STATE_DIR': str(state)}
    args = [sys.executable, '-B', str(root / 'scripts/message_guard.py'), '--gate']
    payload = json.dumps({'tool_name': TOOL, 'tool_input': body})
    first = subprocess.run(args, input=payload, capture_output=True, text=True, timeout=5, env=env)
    assert first.returncode == 0, first.stderr
    assert not approval.exists()
    second = subprocess.run(args, input=payload, capture_output=True, text=True, timeout=5, env=env)
    assert second.returncode == 2

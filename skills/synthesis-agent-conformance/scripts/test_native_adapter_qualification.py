"""Additional-client source support never certifies installed protection."""
import importlib.util
import json
from pathlib import Path
import sys
import pytest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'skills/synthesis-autopilot/scripts'))
import native_adapter_sdk as sdk
import capabilities
import conformance

def test_canonical_surface_inventory_has_opencode_and_keeps_native_scope_separate():
    registry=conformance.supported_agent_surfaces()
    assert registry==capabilities.supported_surfaces()['surfaces']
    assert registry['opencode-sdk-v2']['level']=='observation-only'
    assert not {'opencode-cli','opencode-sdk-v2'} & set(conformance.CAPABILITY_CLIENTS)


def test_production_conformance_consumer_reports_required_unknowns_and_fail_open(tmp_path,monkeypatch):
    monkeypatch.setattr(conformance,'resolve_client_binary',lambda client:None)
    checks=conformance.capability_checks(ROOT,tmp_path/'missing-evidence.json')
    additional=[c for c in checks if '.native.' in c.name]
    assert len(additional)==8*len(sdk.CAPABILITIES)
    assert all(c.outcome=='UNKNOWN' and c.ok is None for c in additional)
    protection=next(c for c in additional if c.name=='capability.copilot-cli.native.permission_enforcement')
    assert 'fail open' in protection.detail and 'FAIL_OPEN_PATHS' in protection.detail
    assert any(c.name=='capability.opencode-sdk-v2.adapter-source' and c.ok for c in checks)


def test_native_claims_in_a_json_file_do_not_upgrade_new_client_cells(tmp_path,monkeypatch):
    monkeypatch.setattr(conformance,'resolve_client_binary',lambda client:None)
    p=tmp_path/'claims.json';p.write_text(json.dumps({'schema_version':1,'entries':{'copilot-cli.native.permission_enforcement':{'status':'PASS','verified':True,'native':True}}}))
    checks=conformance.capability_checks(ROOT,p)
    item=next(c for c in checks if c.name=='capability.copilot-cli.native.permission_enforcement')
    assert item.ok is None and item.outcome=='UNKNOWN'

@pytest.mark.parametrize('surface',['cursor-ide','cursor-cli','cursor-cloud','copilot-cli','copilot-vscode','copilot-cloud','opencode-cli','opencode-sdk-v2'])
def test_required_native_cells_are_not_satisfied_by_manifest_or_fixture_presence(surface):
    report=sdk.assess(surface,required=['native_identity','permission_enforcement','tool_outcome'])
    assert report['qualified'] is False and set(report['missing'])=={'native_identity','permission_enforcement','tool_outcome'}
    assert all(x['condition'] for x in report['actions'])

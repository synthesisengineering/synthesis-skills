"""Offline role, provenance and selector contract; no provider calls."""
from copy import deepcopy
from datetime import date
from pathlib import Path
import os
from urllib.parse import urlparse
import pytest
import yaml

ROOT = Path(os.environ.get('MODEL_TIERS_ROOT', Path(__file__).resolve().parents[1]))
ROLES = ('judgment', 'routine', 'bulk')
HOSTS = {
    'anthropic': {'platform.claude.com'},
    'openai': {'developers.openai.com'},
    'google': {'ai.google.dev'},
    'ollama': {'ollama.com'},
}

def read_pair():
    return (yaml.safe_load((ROOT/'tiers.yaml').read_text()),
            yaml.safe_load((ROOT/'references/catalog-verification.yaml').read_text()))

def validate(catalog, evidence):
    """Reject unverifiable table edits; this is an offline CI oracle, not live qualification."""
    assert catalog['version'] == 2
    assert catalog['verification'] == 'references/catalog-verification.yaml'
    assert evidence['schema_version'] == 1
    assert evidence['scope'] == 'public_identifier_documentation'
    assert set(catalog['providers']) == set(HOSTS) == set(evidence['providers'])
    date.fromisoformat(catalog['updated'])
    assert catalog['updated'] == evidence['reviewed_on']
    sources = evidence['sources']
    for provider, block in catalog['providers'].items():
        assert block['endpoint_availability'] == 'unknown'
        assert block['verified'] == evidence['providers'][provider]['verified']
        date.fromisoformat(block['verified'])
        entries = evidence['providers'][provider]['models']
        role_ids = []
        for role in ROLES:
            models = block[role]
            assert isinstance(models, list) and models
            assert len(models) == len(set(models))
            assert all(isinstance(item, str) and item and item != 'unknown' for item in models)
            role_ids.extend(models)
        assert set(role_ids) == set(entries)
        for model in role_ids:
            entry = entries[model]
            assert entry['status'] == 'documented'
            assert entry['sources']
            for ref in entry['sources']:
                source = sources[ref]
                assert source['retrieved'] == block['verified']
                url = urlparse(source['url'])
                assert url.scheme == 'https' and url.hostname in HOSTS[provider]
                assert entry['native_id'] in source['identifiers']
            namespace = block['identifier_namespace']
            if provider == 'google':
                assert namespace == 'litellm_gemini'
                assert model == 'gemini/' + entry['native_id']
            else:
                assert namespace == ('ollama_tag' if provider == 'ollama' else 'provider_api')
                assert model == entry['native_id']
    google = evidence['providers']['google']['models']
    # A direct Gemini SDK gets the bare API ID. A LiteLLM client keeps its route prefix.
    assert catalog['clients'] == {'gemini-api': {'google': {
        key: val['native_id'] for key, val in google.items()
    }}}
    assert catalog['providers']['ollama']['hardware_fit'] == 'unknown'
    assert 'reasoning_effort' not in catalog and 'selected_model' not in catalog


def test_shipped_catalog_contract():
    validate(*read_pair())


def test_verified_role_assignments():
    catalog = yaml.safe_load((ROOT/'tiers.yaml').read_text())
    assert {role: catalog['providers']['openai'][role] for role in ROLES} == {
        'judgment': ['gpt-6-astra'], 'routine': ['gpt-6-sol'], 'bulk': ['gpt-6-luna']}
    assert catalog['providers']['anthropic']['judgment'] == ['claude-fable-5-1', 'claude-opus-5-5']
    assert catalog['providers']['google']['routine'] == ['gemini/gemini-3.8-flash']
    assert catalog['providers']['google']['bulk'] == ['gemini/gemini-3.5-flash-lite']


@pytest.mark.parametrize('defect', ['missing_source', 'wrong_host', 'restamped', 'unknown_as_model',
    'empty_role', 'wrong_namespace', 'invented_native_id', 'api_selector_prefix',
    'local_readiness_inferred', 'active_selection', 'effort_default', 'lost_retained_model',
    'detached_evidence', 'duplicate_role', 'endpoint_access_inferred'])
def test_negative_catalog_controls(defect):
    catalog, evidence = deepcopy(read_pair())
    if defect == 'detached_evidence':
        catalog['verification'] = 'unrelated.yaml'
    elif defect == 'duplicate_role':
        catalog['providers']['openai']['judgment'].append('gpt-6-astra')
    elif defect == 'endpoint_access_inferred':
        catalog['providers']['openai']['endpoint_availability'] = 'verified'
    elif defect == 'missing_source':
        evidence['providers']['openai']['models']['gpt-6-astra']['sources'] = ['nonexistent']
    elif defect == 'wrong_host':
        evidence['sources']['openai-astra']['url'] = 'https://example.com/model'
    elif defect == 'restamped':
        catalog['providers']['openai']['verified'] = '2026-07-14'
    elif defect == 'unknown_as_model':
        catalog['providers']['openai']['judgment'] = ['unknown']
    elif defect == 'empty_role':
        catalog['providers']['anthropic']['bulk'] = []
    elif defect == 'wrong_namespace':
        catalog['providers']['google']['identifier_namespace'] = 'provider_api'
    elif defect == 'invented_native_id':
        evidence['providers']['openai']['models']['gpt-6-astra']['native_id'] = 'invented'
    elif defect == 'api_selector_prefix':
        catalog['clients']['gemini-api']['google']['gemini/gemini-3.8-flash'] = 'gemini/gemini-3.8-flash'
    elif defect == 'local_readiness_inferred':
        catalog['providers']['ollama']['hardware_fit'] = 'verified'
    elif defect == 'active_selection':
        catalog['selected_model'] = 'gpt-6-sol'
    elif defect == 'effort_default':
        catalog['reasoning_effort'] = 'max'
    elif defect == 'lost_retained_model':
        catalog['providers']['ollama']['judgment'].remove('qwen3.6:35b-a3b')
    with pytest.raises((AssertionError, KeyError, ValueError)):
        validate(catalog, evidence)

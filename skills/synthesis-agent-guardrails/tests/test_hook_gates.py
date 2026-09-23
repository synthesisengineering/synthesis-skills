#!/usr/bin/env python3
"""Hook enable-gate and --doctor contract for the promoted hook suite.

Every promoted hook:
  - is inert when unconfigured (no hooks.json -> main returns 0 silently),
  - answers --doctor with exit 0 and a hook: line,
  - stays silent on --doctor failure paths (never raises out of main).

The catalog loader additionally exposes acknowledgment signals and
per-category rewrite hints parsed from the catalog file, with safe
empty-catalog behavior.
"""

from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest


HOOKS_ROOT = Path(__file__).parent.parent / "hooks"

HOOKS = [
    ("claude", "bare_filename_detector"),
    ("claude", "lazy_shortcut_detector"),
    ("claude", "long_session_detector"),
    ("claude", "pre_tool_temporal_reminder"),
    ("claude", "quote_provenance_checker"),
    ("claude", "sub_agent_brief_scanner"),
    ("codex", "bare_filename_detector"),
    ("codex", "installed_skill_edit_guard"),
    ("codex", "lazy_shortcut_detector"),
    ("codex", "quote_provenance_checker"),
    ("codex", "repo_guard_stop"),
    ("codex", "session_end_checkpoint"),
    ("muse", "lazy_shortcut_detector"),
]


def load_hook(client: str, name: str):
    path = HOOKS_ROOT / client / f"{name}.py"
    module_name = f"pro3_{client}_{name}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(("client", "name"), HOOKS, ids=[f"{c}/{n}" for c, n in HOOKS])
def test_hook_is_inert_when_unconfigured(client, name, tmp_path, monkeypatch, capsys):
    """No hooks.json anywhere near the test: main must exit 0 with no output."""
    module = load_hook(client, name)
    monkeypatch.setenv("GUARDRAILS_HOOKS_CONFIG", str(tmp_path / "missing-hooks.json"))
    monkeypatch.setattr(module.sys, "stdin", io.StringIO(json.dumps({
        "session_id": "gate-test",
        "cwd": str(tmp_path),
        "transcript_path": str(tmp_path / "missing.jsonl"),
        "last_assistant_message": "nothing to see here",
        "tool_name": "Agent",
        "tool_input": {"prompt": "nothing to see here"},
    })))
    assert module.main([]) == 0
    out = capsys.readouterr()
    assert out.out == ""
    assert out.err == ""


@pytest.mark.parametrize(("client", "name"), HOOKS, ids=[f"{c}/{n}" for c, n in HOOKS])
def test_hook_doctor_reports_hook_name(client, name, tmp_path):
    """--doctor exits 0 and names the hook, even with no config present."""
    script = HOOKS_ROOT / client / f"{name}.py"
    env = {"GUARDRAILS_HOOKS_CONFIG": str(tmp_path / "missing-hooks.json"), "PATH": "/usr/bin:/bin"}
    result = subprocess.run(
        [sys.executable, str(script), "--doctor"],
        capture_output=True, text=True, env=env, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    first = result.stdout.splitlines()[0]
    assert first.startswith("hook: "), result.stdout


def _load_catalog_module():
    path = HOOKS_ROOT / "claude" / "_anti_shortcut_catalog.py"
    spec = importlib.util.spec_from_file_location("pro3_catalog", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["pro3_catalog"] = module
    spec.loader.exec_module(module)
    return module


def test_catalog_parses_ack_signals_and_hints(tmp_path, monkeypatch):
    catalog = _load_catalog_module()
    doc = tmp_path / "catalog.yaml"
    doc.write_text(
        "version: 1\nlast_updated: 2026-09-23\n"
        "escalation: {warn_threshold: 1, block_threshold: 2}\n"
        "categories: {deferral: {description: d, severity: low, hint: Do it now.}}\n"
        "phrases:\n"
        "  - {id: p1, category: deferral, phrase: 'later', rationale: Rationale here}\n"
        "acknowledgment_signals: ['\\backnowledg']\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ANTI_SHORTCUT_CATALOG_PATH", str(doc))
    data = catalog._load_and_compile()
    assert len(data.ack_signals) == 1
    assert data.categories["deferral"].hint == "Do it now."
    monkeypatch.setattr(catalog, "_CATALOG", data)
    assert catalog.is_acknowledgment("acknowledging the antipattern") is True
    assert catalog.is_acknowledgment("just shipping it") is False
    hint = catalog.suggested_rewrite_hint("p1")
    assert hint.startswith("Do it now.")
    assert "Rationale here" in hint


def test_catalog_empty_when_unconfigured(tmp_path, monkeypatch):
    catalog = _load_catalog_module()
    monkeypatch.setenv("ANTI_SHORTCUT_CATALOG_PATH", str(tmp_path / "missing.yaml"))
    with pytest.raises(FileNotFoundError):
        catalog._load_and_compile()
    monkeypatch.setattr(catalog, "_CATALOG", catalog._EMPTY_CATALOG)
    assert catalog.is_acknowledgment("acknowledging anything") is False
    assert "not in catalog" in catalog.suggested_rewrite_hint("whatever")

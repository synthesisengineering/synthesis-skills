from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).with_name("capability_evidence.py")
SPEC = importlib.util.spec_from_file_location("capability_evidence", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_record_is_atomic_and_preserves_other_cells(tmp_path: Path) -> None:
    destination = tmp_path / "capabilities.json"
    MODULE.record(
        destination,
        client="codex-desktop",
        capability="slack",
        status="PASS",
        evidence_kind="live-read-only",
        detail="workspace listing succeeded",
    )
    MODULE.record(
        destination,
        client="claude-code",
        capability="browser",
        status="PASS",
        evidence_kind="client-health",
        detail="Playwright connected",
    )

    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert set(payload["entries"]) == {
        "codex-desktop.slack",
        "claude-code.browser",
    }
    assert not list(tmp_path.glob("capabilities.json.*.tmp"))


def test_detail_rejects_authentication_material() -> None:
    for detail in (
        "Authorization: Bearer secret",
        '{"access_token":"secret"}',
        '{"token": "secret"}',
        "x-api-key: secret",
        "client_secret=secret",
    ):
        with pytest.raises(ValueError, match="authentication"):
            MODULE.sanitize_detail(detail)


def test_detail_rejects_bare_credential_values() -> None:
    for detail in (
        "ghp_" + "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ",
        "xoxb-" + "1234567890-1234567890-abcdefghijklmnopqrstuvwx",
        "sk-0123456789abcdefghijklmnopqrstuv",
        "AKIA" + "IOSFODNN7EXAMPLE",
        "ya29.0123456789abcdefghijklmnopqrstuv",
        "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.signature12",
        "AIza" + "A" * 35,
        "glpat-" + "A" * 20,
        "github_pat_" + "A" * 82,
        "xapp-1-" + "A" * 30,
        "ASIA" + "A" * 16,
        "-----BEGIN OPENSSH " + "PRIVATE KEY-----",
        "AIza" + "A" * 34 + "-",
        "glpat-" + "A" * 19 + "-",
        "xapp-" + "A" * 19 + "-",
        "ghp_" + "A" * 36 + "-suffix",
        "ghp_" + "A" * 36 + "_suffix",
        "github_pat_" + "A" * 82 + "-suffix",
        "xoxb-" + "A" * 40 + "_suffix",
        "AKIA" + "A" * 16 + "_suffix",
        "npm_" + "A" * 36 + "_suffix",
        "hf_" + "A" * 36 + "_suffix",
    ):
        with pytest.raises(ValueError, match="authentication"):
            MODULE.sanitize_detail(detail)


def test_parallel_recorders_do_not_lose_cells(tmp_path: Path) -> None:
    destination = tmp_path / "capabilities.json"
    cells = [
        (client, capability)
        for client in MODULE.CLIENTS
        for capability in MODULE.CAPABILITIES
    ]
    processes = [
        subprocess.Popen(
            [
                sys.executable,
                str(MODULE_PATH),
                "record",
                "--destination",
                str(destination),
                "--client",
                client,
                "--capability",
                capability,
                "--status",
                "PASS",
                "--evidence-kind",
                "client-health",
                "--detail",
                "sanitized probe passed",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for client, capability in cells
    ]
    results = [
        process.communicate(timeout=15) + (process.returncode,)
        for process in processes
    ]

    assert all(returncode == 0 for _stdout, _stderr, returncode in results)
    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert set(payload["entries"]) == {
        f"{client}.{capability}" for client, capability in cells
    }
    assert not list(tmp_path.glob("capabilities.json.*.tmp"))

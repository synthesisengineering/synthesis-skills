from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).with_name("codex_hook_audit.py")
SPEC = importlib.util.spec_from_file_location("codex_hook_audit", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_normalized_audit_preserves_hash_owner_and_reason() -> None:
    payload = MODULE.normalized_audit(
        {
            "data": [
                {
                    "cwd": "/tmp/repo",
                    "hooks": [
                        {
                            "key": "plugin:0:0",
                            "eventName": "SessionStart",
                            "matcher": None,
                            "command": "python3 hook.py",
                            "currentHash": "sha256:abc",
                            "sourcePath": "/tmp/hooks.json",
                            "source": "plugin",
                            "pluginId": "synthesis-skills@test",
                            "enabled": True,
                            "isManaged": False,
                            "trustStatus": "modified",
                        }
                    ],
                    "warnings": [],
                    "errors": [],
                }
            ]
        }
    )

    assert payload["status"] == "FAIL"
    assert payload["pending_review"] == 1
    hook = payload["hooks"][0]
    assert hook["current_hash"] == "sha256:abc"
    assert hook["source_owner"] == "plugin"
    assert "changed after" in hook["change_reason"]


def test_managed_hook_does_not_require_human_review() -> None:
    payload = MODULE.normalized_audit(
        {
            "data": [
                {
                    "cwd": "/tmp/repo",
                    "hooks": [
                        {
                            "key": "managed:0:0",
                            "eventName": "PreToolUse",
                            "enabled": True,
                            "isManaged": True,
                            "trustStatus": "managed",
                        }
                    ],
                }
            ]
        }
    )

    assert payload["status"] == "PASS"
    assert payload["pending_review"] == 0


def test_timeout_is_reported_as_unknown(monkeypatch) -> None:
    monkeypatch.setattr(MODULE, "resolve_client_binary", lambda _client: "codex")

    def timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired("codex", 15)

    monkeypatch.setattr(MODULE, "query_hooks", timeout)

    payload = MODULE.audit(["/tmp/repo"])

    assert payload["status"] == "UNKNOWN"
    assert payload["pending_review"] is None
    assert "timed out" in payload["errors"][0]


def test_malformed_data_is_rejected() -> None:
    with pytest.raises(ValueError, match="not a list"):
        MODULE.normalized_audit({"data": None})


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"data": []}, "no rows"),
        ({"data": [None]}, "row 0 is not an object"),
        ({"data": [{"hooks": "corrupt"}]}, "hooks is not a list"),
        ({"data": [{"hooks": [None]}]}, "hook 0 is not an object"),
        ({"data": [{"hooks": [], "warnings": "bad"}]}, "warnings is not a list"),
        ({"data": [{"hooks": [], "errors": "bad"}]}, "errors is not a list"),
    ],
)
def test_malformed_nested_rows_are_rejected(payload: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        MODULE.normalized_audit(payload)

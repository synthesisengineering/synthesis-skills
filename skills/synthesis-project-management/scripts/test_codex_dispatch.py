"""Dispatch must use the same authoritative discovery as lifecycle verification."""
import importlib.util
import sys
from pathlib import Path


SPEC = importlib.util.spec_from_file_location("codex_dispatch_under_test", Path(__file__).with_name("codex_dispatch.py"))
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_dispatch_discovery_honors_explicit_absence(monkeypatch):
    monkeypatch.setenv("SYNTHESIS_CODEX_BIN", "")
    monkeypatch.setattr(MODULE.shutil, "which", lambda name: "/stale/codex")
    assert MODULE.find_binary() is None


def test_dispatch_uses_executable_override(tmp_path, monkeypatch):
    binary = tmp_path / "codex"
    binary.write_text("#!/bin/sh\nexit 0\n")
    binary.chmod(0o700)
    monkeypatch.setenv("SYNTHESIS_CODEX_BIN", str(binary))
    monkeypatch.setattr(MODULE.shutil, "which", lambda name: "/stale/codex")
    assert MODULE.find_binary() == binary

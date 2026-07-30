from __future__ import annotations

import importlib.util
import os
import stat
import sys
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("client_binaries.py")
SPEC = importlib.util.spec_from_file_location("client_binaries", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def fake_binary(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def test_env_override_wins_over_path(tmp_path: Path, monkeypatch) -> None:
    override = fake_binary(tmp_path / "custom" / "codex")
    monkeypatch.setenv("SYNTHESIS_CODEX_BIN", str(override))
    monkeypatch.setattr(MODULE.shutil, "which", lambda name: "/elsewhere/codex")
    assert MODULE.resolve_client_binary("codex") == str(override)


def test_env_override_set_but_empty_means_absent(monkeypatch) -> None:
    monkeypatch.setenv("SYNTHESIS_CODEX_BIN", "")
    monkeypatch.setattr(MODULE.shutil, "which", lambda name: "/elsewhere/codex")
    assert MODULE.resolve_client_binary("codex") is None


def test_env_override_pointing_nowhere_fails_closed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SYNTHESIS_CLAUDE_BIN", str(tmp_path / "missing"))
    monkeypatch.setattr(MODULE.shutil, "which", lambda name: "/elsewhere/claude")
    assert MODULE.resolve_client_binary("claude") is None


def test_path_resolution(monkeypatch) -> None:
    monkeypatch.delenv("SYNTHESIS_CODEX_BIN", raising=False)
    monkeypatch.setattr(MODULE.shutil, "which", lambda name: f"/on/path/{name}")
    assert MODULE.resolve_client_binary("codex") == "/on/path/codex"


def test_well_known_fallback(tmp_path: Path, monkeypatch) -> None:
    fallback = fake_binary(tmp_path / "bundle" / "codex")
    monkeypatch.delenv("SYNTHESIS_CODEX_BIN", raising=False)
    monkeypatch.setattr(MODULE.shutil, "which", lambda name: None)
    monkeypatch.setitem(MODULE.WELL_KNOWN_LOCATIONS, "codex", (str(fallback),))
    assert MODULE.resolve_client_binary("codex") == str(fallback)


def test_absent_everywhere_returns_none(monkeypatch) -> None:
    monkeypatch.delenv("SYNTHESIS_CODEX_BIN", raising=False)
    monkeypatch.setattr(MODULE.shutil, "which", lambda name: None)
    monkeypatch.setitem(MODULE.WELL_KNOWN_LOCATIONS, "codex", ())
    assert MODULE.resolve_client_binary("codex") is None


def test_missing_binary_detail_names_override() -> None:
    detail = MODULE.missing_binary_detail("codex")
    assert "SYNTHESIS_CODEX_BIN" in detail
    assert "codex" in detail


def test_unknown_client_has_no_well_known_locations(monkeypatch) -> None:
    monkeypatch.setattr(MODULE.shutil, "which", lambda name: None)
    assert MODULE.resolve_client_binary("unknown-client") is None

"""Shared fixtures for the coordination tests."""

import pytest


@pytest.fixture
def codex_cli(tmp_path, monkeypatch):
    """A runnable Codex CLI stand-in, selected through the authoritative override.

    The codex lane exists only when this machine can run a Codex CLI, so a test
    that expects the lane provides one explicitly rather than depending on
    whether the machine running the suite happens to have Codex installed.
    """
    cli = tmp_path / "codex-cli" / "codex"
    cli.parent.mkdir()
    cli.write_text("#!/bin/sh\nexit 0\n")
    cli.chmod(0o755)
    monkeypatch.setenv("SYNTHESIS_CODEX_BIN", str(cli))
    return str(cli)

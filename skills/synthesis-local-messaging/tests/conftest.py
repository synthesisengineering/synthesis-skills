# SPDX-License-Identifier: Apache-2.0
"""Shared fixtures: an isolated synthesis home, and the OS sandbox requirement."""

from __future__ import annotations

import os
from pathlib import Path
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import os_sandbox  # noqa: E402


@pytest.fixture
def need_sandbox():
    """Skip where no OS sandbox exists; fail instead when CI says it must exist."""
    if os_sandbox.sandbox_available():
        return
    if os.environ.get("SYNTHESIS_REQUIRE_SANDBOX") == "1":
        pytest.fail("SYNTHESIS_REQUIRE_SANDBOX=1 but neither sandbox-exec nor bwrap could run a probe")
    pytest.skip("no usable OS sandbox (macOS sandbox-exec or Linux bwrap) on this host")


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("SYNTHESIS_HOME", str(tmp_path / "synthesis-home"))

#!/usr/bin/env python3
"""Tests for the read-only Codex app-server client."""

from __future__ import annotations

from codex_app_server import initialize_message


def test_initialize_message_identifies_audit_client() -> None:
    message = initialize_message("Catalog Audit")

    assert message["method"] == "initialize"
    assert message["params"]["clientInfo"]["title"] == "Catalog Audit"

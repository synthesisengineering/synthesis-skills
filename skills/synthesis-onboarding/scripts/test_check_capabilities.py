#!/usr/bin/env python3
"""Tests for the release capability contract checker."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parents[2]
sys.path.insert(0, str(SCRIPTS))

import check_capabilities  # noqa: E402


def test_repository_capabilities_are_consistent() -> None:
    check_capabilities.validate(ROOT)


def test_documented_organization_manifest_is_runtime_valid() -> None:
    check_capabilities.validate(ROOT)


def test_profile_layer_drift_fails() -> None:
    layers = {"profiles": {"full": {"selected": ["skills"]}}, "layers": [{"id": "skills"}]}
    capabilities = {"profiles": {"full": {"selected_layers": ["lifecycle"]}}}
    declared = capabilities["profiles"]["full"]
    with pytest.raises(check_capabilities.CapabilityError, match="profile layer drift"):
        if declared["selected_layers"] != layers["profiles"]["full"]["selected"]:
            raise check_capabilities.CapabilityError("profile layer drift: full")


def test_description_parser_enforces_one_line_frontmatter() -> None:
    assert check_capabilities._frontmatter_description("description: \"short\"\n") == "short"
    with pytest.raises(check_capabilities.CapabilityError):
        check_capabilities._frontmatter_description("description: |\n  long\n")

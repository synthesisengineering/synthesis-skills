#!/usr/bin/env python3
"""Hermetic lifecycle-policy and plugin-currency tests."""

from __future__ import annotations

import json
from pathlib import Path

import plugin_currency


class Response:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode("utf-8")

    def read(self):
        return self.payload

    def close(self):
        pass


def write_plugin_root(root: Path, version: str) -> None:
    for directory in (".claude-plugin", ".codex-plugin"):
        target = root / directory
        target.mkdir(parents=True, exist_ok=True)
        (target / "plugin.json").write_text(
            json.dumps({"version": version}), encoding="utf-8"
        )


def test_stable_edge_and_pin_resolve_to_distinct_git_refs() -> None:
    assert plugin_currency.policy_ref({"channel": "stable", "version_pin": None}) == "stable"
    assert plugin_currency.policy_ref({"channel": "edge", "version_pin": None}) == "main"
    assert plugin_currency.policy_ref(
        {"channel": "stable", "version_pin": "4.74.0"}
    ) == "v4.74.0"


def test_policy_rejects_unknown_channel_and_non_exact_pin() -> None:
    for channel, pin in (("preview", None), ("stable", "4.74"), ("stable", "latest")):
        try:
            plugin_currency.normalize_policy(channel, pin)
        except ValueError:
            pass
        else:
            raise AssertionError((channel, pin))


def test_version_comparison_is_semantic_not_lexical() -> None:
    assert plugin_currency.compare_versions("4.9.0", "4.10.0") == "behind"
    assert plugin_currency.compare_versions("4.10.0", "4.10.0") == "current"
    assert plugin_currency.compare_versions("5.0.0", "4.99.0") == "ahead"


def test_live_resolution_is_cached_and_stale_cache_remains_labeled(tmp_path: Path) -> None:
    cache = tmp_path / "currency.json"
    policy = {"channel": "stable", "version_pin": None}
    calls = []

    def live(url, timeout):
        calls.append((url, timeout))
        return Response({"version": "4.74.0"})

    assert plugin_currency.resolve_target_version(
        policy, cache_path=cache, opener=live, now=100
    ) == ("4.74.0", "live stable ref")
    assert plugin_currency.resolve_target_version(
        policy, cache_path=cache, opener=lambda *_args, **_kwargs: None, now=101
    ) == ("4.74.0", "cached stable ref (fresh)")
    assert len(calls) == 1

    def offline(*_args, **_kwargs):
        raise OSError("offline")

    version, detail = plugin_currency.resolve_target_version(
        policy, cache_path=cache, ttl_seconds=1, opener=offline, now=200
    )
    assert version == "4.74.0"
    assert "stale" in detail


def test_sessionstart_notice_compares_executing_cache_to_stable(tmp_path: Path) -> None:
    root = tmp_path / "plugin"
    write_plugin_root(root, "4.73.0")
    receipts = tmp_path / "receipts.json"
    receipts.write_text(
        json.dumps({"plugin_policy": {"channel": "stable", "version_pin": None}}),
        encoding="utf-8",
    )

    notice = plugin_currency.sessionstart_notice(
        root,
        receipts,
        resolver=lambda policy: ("4.74.0", "fixture"),
    )
    assert "update available" in notice.lower()
    assert "installed plugin 4.73.0" in notice
    assert "stable channel is 4.74.0" in notice


def test_sessionstart_notice_is_quiet_when_current(tmp_path: Path) -> None:
    root = tmp_path / "plugin"
    write_plugin_root(root, "4.74.0")
    assert plugin_currency.sessionstart_notice(
        root,
        resolver=lambda policy: ("4.74.0", "fixture"),
    ) == ""


def test_sessionstart_notice_preserves_unverifiable_state(tmp_path: Path) -> None:
    root = tmp_path / "plugin"
    write_plugin_root(root, "4.74.0")
    notice = plugin_currency.sessionstart_notice(
        root,
        resolver=lambda policy: (None, "offline"),
    )
    assert "could not be verified" in notice
    assert "installed 4.74.0" in notice

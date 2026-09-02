#!/usr/bin/env python3
"""Tests for the dual-client parity mode.

The mode exists to catch the day a release reaches one client and not the
other — or neither. Each test supplies fake enabled inventories plus a fake
source checkout and asserts the drift verdicts, including the degenerate
self-comparison case (running from inside a plugin cache), which must fail
closed rather than pass vacuously.
"""

from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import conformance as MODULE  # noqa: E402


def source(root: Path, version: str) -> Path:
    for manifest_dir in (".claude-plugin", ".codex-plugin"):
        d = root / manifest_dir
        d.mkdir(parents=True, exist_ok=True)
        (d / "plugin.json").write_text(json.dumps({"version": version}))
    return root


def by_name(checks) -> dict[str, bool]:
    return {c.name: c.ok for c in checks}


class ParityTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.home = Path(self._tmp.name) / "home"
        self.src = source(Path(self._tmp.name) / "src", "4.13.0")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def stable(self, version: str) -> Path:
        """Point the fake home's stable pointer at a fake install root."""
        root = Path(self._tmp.name) / "cache" / version
        (root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
        (root / ".claude-plugin" / "plugin.json").write_text(json.dumps({"version": version}))
        link = self.home / ".synthesis" / "plugins" / MODULE.PLUGIN_NAME / "current"
        link.parent.mkdir(parents=True, exist_ok=True)
        if link.is_symlink():
            link.unlink()
        link.symlink_to(root)
        return root

    def cache_root(self, client: str, version: str, manifest_version: str | None = None) -> Path:
        """A fake installed cache tree for one client, with its own manifest."""
        root = self.home / f".{client}" / "plugins" / "cache" / "market" / MODULE.PLUGIN_NAME / version
        manifest_dir = ".claude-plugin" if client == "claude" else ".codex-plugin"
        (root / manifest_dir).mkdir(parents=True, exist_ok=True)
        (root / manifest_dir / "plugin.json").write_text(
            json.dumps({"version": manifest_version or version})
        )
        return root

    def checks(self, claude: str | None, codex: str | None):
        versions = {"claude": claude, "codex": codex}
        with patch.object(
            MODULE,
            "enabled_plugin_version",
            side_effect=lambda client, home=None: versions[client],
        ):
            return MODULE.parity_checks(self.src, home=self.home)

    def test_everything_current_passes(self):
        self.stable("4.13.0")
        self.cache_root("claude", "4.13.0")
        self.cache_root("codex", "4.13.0")
        ok = by_name(self.checks("4.13.0", "4.13.0"))
        self.assertTrue(all(ok.values()), ok)

    def test_missing_stable_path_fails(self):
        """A pointer nobody created is a pin that resolves to nothing."""
        ok = by_name(self.checks("4.13.0", "4.13.0"))
        self.assertFalse(ok["parity.stable-path"])
        self.assertTrue(ok["parity.clients-current"])

    def test_dangling_stable_path_fails(self):
        """The client replaced its cache under the pointer."""
        root = self.stable("4.13.0")
        shutil.rmtree(root)
        ok = by_name(self.checks("4.13.0", "4.13.0"))
        self.assertFalse(ok["parity.stable-path"])

    def test_stable_path_behind_installed_fails(self):
        """An install made without the gated release left the pointer stale."""
        self.stable("4.12.0")
        ok = by_name(self.checks("4.13.0", "4.13.0"))
        self.assertFalse(ok["parity.stable-path"])

    def test_reported_version_without_a_cache_tree_fails_on_disk(self):
        """The 2026-08-17 defect: the CLI reports the version it intends to
        serve while no tree for it exists on disk."""
        self.stable("4.13.0")
        self.cache_root("claude", "4.13.0")
        ok = by_name(self.checks("4.13.0", "4.13.0"))
        self.assertTrue(ok["parity.codex-installed"])
        self.assertFalse(ok["parity.codex-on-disk"])
        self.assertTrue(ok["parity.claude-on-disk"])

    def test_cache_manifest_disagreeing_with_the_report_fails_on_disk(self):
        self.stable("4.13.0")
        self.cache_root("claude", "4.13.0")
        self.cache_root("codex", "4.13.0", manifest_version="4.12.0")
        ok = by_name(self.checks("4.13.0", "4.13.0"))
        self.assertFalse(ok["parity.codex-on-disk"])
        self.assertTrue(ok["parity.claude-on-disk"])

    def test_one_client_behind_fails_match_and_current(self):
        ok = by_name(self.checks("4.13.0", "4.12.0"))
        self.assertFalse(ok["parity.clients-match"])
        self.assertFalse(ok["parity.clients-current"])
        self.assertTrue(ok["parity.claude-installed"])

    def test_both_behind_source_fails_current_only(self):
        ok = by_name(self.checks("4.12.0", "4.12.0"))
        self.assertTrue(ok["parity.clients-match"])
        self.assertFalse(ok["parity.clients-current"])

    def test_missing_enabled_client_fails_installed(self):
        ok = by_name(self.checks("4.13.0", None))
        self.assertFalse(ok["parity.codex-installed"])
        self.assertFalse(ok["parity.clients-match"])

    def test_source_manifest_disagreement_fails(self):
        (self.src / ".codex-plugin" / "plugin.json").write_text(
            json.dumps({"version": "4.12.0"})
        )
        ok = by_name(self.checks("4.13.0", "4.13.0"))
        self.assertFalse(ok["parity.source-manifests"])
        self.assertFalse(ok["parity.clients-current"])

    def test_plugin_cache_as_source_root_fails_closed(self):
        """Self-comparison must never pass vacuously."""
        cache_root = (
            self.home / ".claude" / "plugins" / "cache" / "mp" / "synthesis-skills" / "4.13.0"
        )
        cache_root.mkdir(parents=True, exist_ok=True)
        checks = MODULE.parity_checks(cache_root, home=self.home)
        ok = by_name(checks)
        self.assertEqual(list(ok), ["parity.source-root"])
        self.assertFalse(ok["parity.source-root"])

if __name__ == "__main__":
    unittest.main(verbosity=2)

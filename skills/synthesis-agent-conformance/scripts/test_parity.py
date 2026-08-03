#!/usr/bin/env python3
"""Tests for the dual-client parity mode.

The mode exists to catch the day a release reaches one client and not the
other — or neither. Each test builds a fake pair of client caches plus a fake
source checkout and asserts the drift verdicts, including the degenerate
self-comparison case (running from inside a plugin cache), which must fail
closed rather than pass vacuously.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent))

from conformance import newest_cached_plugin_version, parity_checks  # noqa: E402


def build(home: Path, claude: list[str], codex: list[str]) -> None:
    for client, versions in (("claude", claude), ("codex", codex)):
        for version in versions:
            (
                home / f".{client}" / "plugins" / "cache" / "mp" / "synthesis-skills" / version
            ).mkdir(parents=True, exist_ok=True)


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

    def test_everything_current_passes(self):
        build(self.home, ["4.12.0", "4.13.0"], ["4.13.0"])
        ok = by_name(parity_checks(self.src, home=self.home))
        self.assertTrue(all(ok.values()), ok)

    def test_one_client_behind_fails_match_and_current(self):
        build(self.home, ["4.13.0"], ["4.12.0"])
        ok = by_name(parity_checks(self.src, home=self.home))
        self.assertFalse(ok["parity.clients-match"])
        self.assertFalse(ok["parity.clients-current"])
        self.assertTrue(ok["parity.claude-installed"])

    def test_both_behind_source_fails_current_only(self):
        build(self.home, ["4.12.0"], ["4.12.0"])
        ok = by_name(parity_checks(self.src, home=self.home))
        self.assertTrue(ok["parity.clients-match"])
        self.assertFalse(ok["parity.clients-current"])

    def test_missing_client_cache_fails_installed(self):
        build(self.home, ["4.13.0"], [])
        ok = by_name(parity_checks(self.src, home=self.home))
        self.assertFalse(ok["parity.codex-installed"])
        self.assertFalse(ok["parity.clients-match"])

    def test_source_manifest_disagreement_fails(self):
        (self.src / ".codex-plugin" / "plugin.json").write_text(
            json.dumps({"version": "4.12.0"})
        )
        build(self.home, ["4.13.0"], ["4.13.0"])
        ok = by_name(parity_checks(self.src, home=self.home))
        self.assertFalse(ok["parity.source-manifests"])
        self.assertFalse(ok["parity.clients-current"])

    def test_plugin_cache_as_source_root_fails_closed(self):
        """Self-comparison must never pass vacuously."""
        cache_root = (
            self.home / ".claude" / "plugins" / "cache" / "mp" / "synthesis-skills" / "4.13.0"
        )
        cache_root.mkdir(parents=True, exist_ok=True)
        checks = parity_checks(cache_root, home=self.home)
        ok = by_name(checks)
        self.assertEqual(list(ok), ["parity.source-root"])
        self.assertFalse(ok["parity.source-root"])

    def test_version_ordering_is_numeric_not_lexical(self):
        build(self.home, ["4.9.0", "4.10.0"], [])
        self.assertEqual(
            newest_cached_plugin_version(self.home / ".claude"), "4.10.0"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)

#!/usr/bin/env python3
"""Tests for slack_workspaces.py: placeholder tokens, statuses, modes."""

import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("slack_workspaces.py")


def run(*args, env=None):
    merged = dict(os.environ)
    if env:
        merged.update(env)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, env=merged)
    return proc


def write_registry(path, mode="unified", entries=(
        ("personal", "PLACEHOLDER", "PLACEHOLDER"),
        ("work", "work.example.slack.com", "env:SLACK_TOKEN_WORK"),
        ("otherco", "PLACEHOLDER", "PLACEHOLDER"))):
    lines = ["version: 1", f"mode: {mode}", "workspaces:"]
    for name, domain, token in entries:
        lines += [f"  - name: {name}", f"    domain: {domain}", f"    token: {token}"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class RegistryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.reg = Path(self.tmp.name) / "reg.yaml"

    def tearDown(self):
        self.tmp.cleanup()

    def test_init_seeds_placeholders_and_never_overwrites(self):
        first = run("init", "--registry", str(self.reg))
        self.assertEqual(first.returncode, 0, first.stderr)
        text = self.reg.read_text(encoding="utf-8")
        self.assertIn("mode: unified", text)
        self.assertEqual(text.count("token: PLACEHOLDER"), 2)
        self.assertNotIn("xoxb-", text)
        second = run("init", "--registry", str(self.reg))
        self.assertEqual(second.returncode, 1)
        self.assertIn("refusing to overwrite", second.stderr)

    def test_init_force_reseeds(self):
        self.reg.write_text("custom: true\n", encoding="utf-8")
        proc = run("init", "--registry", str(self.reg), "--force")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("mode: unified", self.reg.read_text(encoding="utf-8"))

    def test_doctor_placeholder_focus_fails_closed(self):
        write_registry(self.reg)
        proc = run("doctor", "--registry", str(self.reg),
                   "--session-workspace", "personal")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("placeholder", proc.stdout)
        self.assertIn("slack-token-guide.md", proc.stdout)

    def test_doctor_ready_focus_passes_and_names_readable(self):
        write_registry(self.reg)
        proc = run("doctor", "--registry", str(self.reg),
                   "--session-workspace", "work",
                   env={"SLACK_TOKEN_WORK": "xoxb-real-token"})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("readable from here: work", proc.stdout)
        self.assertNotIn("xoxb-real-token", proc.stdout + proc.stderr)

    def test_doctor_never_prints_token_values(self):
        write_registry(self.reg)
        proc = run("list", "--registry", str(self.reg),
                   env={"SLACK_TOKEN_WORK": "xoxb-supersecret"})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("xoxb-supersecret", proc.stdout + proc.stderr)

    def test_doctor_unset_env_is_missing_not_ready(self):
        write_registry(self.reg)
        env = dict(os.environ)
        env.pop("SLACK_TOKEN_WORK", None)
        proc = run("doctor", "--registry", str(self.reg),
                   "--session-workspace", "work", env=env)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("missing", proc.stdout)

    def test_literal_token_in_registry_is_rejected(self):
        write_registry(self.reg, entries=(
            ("personal", "example.slack.com", "xoxb-literal-nope"),))
        proc = run("doctor", "--registry", str(self.reg),
                   "--session-workspace", "personal")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("rejected", proc.stdout)

    def test_mcp_ref_is_external_and_readable(self):
        write_registry(self.reg, entries=(
            ("personal", "example.slack.com", "mcp:slack-personal"),))
        proc = run("doctor", "--registry", str(self.reg),
                   "--session-workspace", "personal")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("external", proc.stdout)

    def test_file_ref_roundtrip(self):
        token_file = Path(self.tmp.name) / "tok"
        token_file.write_text("xoxb-from-file\n", encoding="utf-8")
        write_registry(self.reg, entries=(
            ("personal", "example.slack.com", f"file:{token_file}"),))
        proc = run("doctor", "--registry", str(self.reg),
                   "--session-workspace", "personal")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("ready", proc.stdout)

    def test_unified_reads_other_ready_workspaces(self):
        write_registry(self.reg, entries=(
            ("personal", "example.slack.com", "env:TOK_A"),
            ("work", "work.example.slack.com", "env:TOK_B")))
        proc = run("readable", "--registry", str(self.reg),
                   "--session-workspace", "personal",
                   env={"TOK_A": "xoxb-a", "TOK_B": "xoxb-b"})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "personal work")

    def test_isolated_reads_focus_only(self):
        write_registry(self.reg, mode="isolated", entries=(
            ("personal", "example.slack.com", "env:TOK_A"),
            ("work", "work.example.slack.com", "env:TOK_B")))
        proc = run("readable", "--registry", str(self.reg),
                   "--session-workspace", "personal",
                   env={"TOK_A": "xoxb-a", "TOK_B": "xoxb-b"})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "personal")

    def test_unknown_mode_is_exit_2(self):
        write_registry(self.reg, mode="severance")
        proc = run("doctor", "--registry", str(self.reg),
                   "--session-workspace", "personal")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("unknown mode", proc.stderr)

    def test_unknown_session_workspace_is_exit_2(self):
        write_registry(self.reg)
        proc = run("doctor", "--registry", str(self.reg),
                   "--session-workspace", "unlistedco")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("not in the registry", proc.stderr)

    def test_malformed_registry_is_exit_2(self):
        self.reg.write_text("workspaces: [unclosed\n", encoding="utf-8")
        proc = run("doctor", "--registry", str(self.reg),
                   "--session-workspace", "personal")
        self.assertEqual(proc.returncode, 2)

    def test_missing_registry_points_at_init(self):
        proc = run("doctor", "--registry", str(self.reg),
                   "--session-workspace", "personal")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("init", proc.stderr)


if __name__ == "__main__":
    unittest.main()

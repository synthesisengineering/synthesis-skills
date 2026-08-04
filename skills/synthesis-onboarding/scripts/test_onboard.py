#!/usr/bin/env python3
"""Deterministic tests for the synthesis-onboarding engine.

Every install-path test runs the engine as a subprocess inside a sandbox
HOME with local bare repositories standing in for org remotes — no network,
no client CLIs, no writes outside the sandbox.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ENGINE = SCRIPTS / "onboard.py"
REPO_ROOT = SCRIPTS.parents[2]

sys.path.insert(0, str(SCRIPTS))
import onboard  # noqa: E402


def sh(cmd, cwd=None, env=None):
    proc = subprocess.run(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise AssertionError("fixture command failed: %s\n%s%s" % (cmd, proc.stdout, proc.stderr))
    return proc.stdout


FIXTURE_INSTALLER = """#!/bin/sh
set -eu
cmd=${1:-install}
target=${2:-$HOME}
SRC_DIR=${EXAMPLE_SHARED_SKILLS_SOURCE_DIR:-$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)}
case "$cmd" in
  install)
    for d in "$target/.claude/skills" "$target/.agents/skills"; do
      mkdir -p "$d/example-skill"
      cp "$SRC_DIR/example-skill/SKILL.md" "$d/example-skill/SKILL.md"
    done
    echo "installed" ;;
  status)
    for d in "$target/.claude/skills" "$target/.agents/skills"; do
      [ -f "$d/example-skill/SKILL.md" ] || { echo "MISSING $d"; exit 1; }
    done
    echo "clean" ;;
  *) echo "unknown command $cmd"; exit 2 ;;
esac
"""


class Sandbox:
    def __init__(self):
        self.root = Path(tempfile.mkdtemp(prefix="onboard-test-"))
        self.home = self.root / "home"
        self.remotes = self.root / "remotes"
        self.cache = self.root / "cache"
        for path in (self.home, self.remotes, self.cache):
            path.mkdir(parents=True)
        self.git_env = dict(os.environ)
        self.git_env.update(self.env_overrides())
        self._build_kb_remote()
        self._build_skills_remote()

    def env_overrides(self):
        return {
            "HOME": str(self.home),
            "SYNTHESIS_ONBOARD_HOME": str(self.home),
            "SYNTHESIS_ONBOARD_STATE_DIR": str(self.home / ".synthesis" / "onboarding"),
            "SYNTHESIS_WORKSPACES_ROOT": str(self.home / "workspaces"),
            "SYNTHESIS_ONBOARD_CACHE_DIR": str(self.cache),
            "SYNTHESIS_ONBOARD_SOURCE_DIR": str(REPO_ROOT),
            "SYNTHESIS_CLAUDE_BIN": "",
            "SYNTHESIS_CODEX_BIN": "",
            "GIT_AUTHOR_NAME": "Test User", "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "Test User", "GIT_COMMITTER_EMAIL": "test@example.com",
            "GIT_CONFIG_NOSYSTEM": "1",
        }

    def _commit_all(self, workdir, message):
        sh(["git", "-C", str(workdir), "add", "-A"], env=self.git_env)
        sh(["git", "-C", str(workdir), "commit", "-q", "-m", message], env=self.git_env)

    def _build_kb_remote(self):
        src = self.root / "kb-src"
        (src / ".agents").mkdir(parents=True)
        (src / ".githooks").mkdir()
        (src / "source").mkdir()
        (src / "README.md").write_text("# Example KB\n")
        (src / ".agents" / "knowledge-base.yaml").write_text("bundle_path: source\n")
        hook = src / ".githooks" / "pre-commit"
        hook.write_text("#!/bin/sh\nexit 0\n")
        hook.chmod(0o755)
        (src / "source" / "hello.md").write_text("hello\n")
        sh(["git", "-C", str(src), "init", "-q", "-b", "main"], env=self.git_env)
        self._commit_all(src, "seed")
        self.kb_remote = self.remotes / "ai-knowledge-exampleco.git"
        sh(["git", "clone", "-q", "--bare", str(src), str(self.kb_remote)], env=self.git_env)
        self.old_kb_remote = self.remotes / "old-kb.git"
        sh(["git", "clone", "-q", "--bare", str(src), str(self.old_kb_remote)], env=self.git_env)

    def _build_skills_remote(self):
        src = self.root / "skills-src"
        (src / "example-skill").mkdir(parents=True)
        (src / "example-skill" / "SKILL.md").write_text("---\nname: example-skill\n---\n# Example\n")
        installer = src / "install.sh"
        installer.write_text(FIXTURE_INSTALLER)
        installer.chmod(0o755)
        sh(["git", "-C", str(src), "init", "-q", "-b", "main"], env=self.git_env)
        self._commit_all(src, "seed")
        self.skills_remote = self.remotes / "example-shared-skills.git"
        sh(["git", "clone", "-q", "--bare", str(src), str(self.skills_remote)], env=self.git_env)

    def manifest(self, kb_primary=None, migrations=None):
        lines = [
            "version: 1",
            "org:",
            "  id: exampleco",
            "  name: Example Co",
            "  workspace: exampleco",
            "skills_repos:",
            "  - name: example-shared-skills",
            "    primary: %s" % self.skills_remote,
            "    installer: install.sh",
            "    installer_args:",
            "      - $HOME",
            "    source_env: EXAMPLE_SHARED_SKILLS_SOURCE_DIR",
            "    status_args:",
            "      - status",
            "      - $HOME",
            "knowledge_bases:",
            "  - name: ai-knowledge-exampleco",
            "    primary: %s" % (kb_primary or self.kb_remote),
            "    superseded_remotes:",
            "      - %s" % self.old_kb_remote,
            "    local_hooks: true",
            "auth_help: |",
            "  Ask the help desk for repository access, then re-run.",
            "welcome:",
            "  title: Welcome to the Example Co knowledge base",
            "  try_asking:",
            "    - \"Who owns the payments platform?\"",
        ]
        if migrations:
            lines.append("migrations:")
            lines.append("  skills:")
            for mig in migrations:
                lines.append("    - from: %s" % mig["from"])
                lines.append("      action: %s" % mig["action"])
                if mig.get("to"):
                    lines.append("      to: %s" % mig["to"])
        path = self.root / "onboarding.yaml"
        path.write_text("\n".join(lines) + "\n")
        return path

    def run_engine(self, *args, expect=None):
        env = dict(os.environ)
        env.update(self.env_overrides())
        proc = subprocess.run([sys.executable, str(ENGINE)] + list(args),
                              env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if expect is not None and proc.returncode != expect:
            raise AssertionError("exit %d != %d\nstdout:\n%s\nstderr:\n%s"
                                 % (proc.returncode, expect, proc.stdout, proc.stderr))
        return proc

    def run_json(self, *args, expect=None):
        proc = self.run_engine(*(list(args) + ["--json"]), expect=expect)
        return json.loads(proc.stdout), proc

    def cleanup(self):
        shutil.rmtree(self.root, ignore_errors=True)

    @property
    def kb_clone(self):
        return self.home / "workspaces" / "exampleco" / "ai-knowledge-exampleco"

    @property
    def ws_agents(self):
        return self.home / "workspaces" / "exampleco" / "AGENTS.md"


class ParserTests(unittest.TestCase):
    def test_nested_maps_lists_scalars(self):
        data = onboard.parse_subset_yaml(
            "a:\n  b: 1\n  c:\n    - x\n    - y\nd: true\n")
        self.assertEqual(data, {"a": {"b": 1, "c": ["x", "y"]}, "d": True})

    def test_list_of_maps_with_nested_list(self):
        data = onboard.parse_subset_yaml(
            "items:\n  - name: one\n    urls:\n      - u1\n      - u2\n  - name: two\n")
        self.assertEqual(data["items"][0]["urls"], ["u1", "u2"])
        self.assertEqual(data["items"][1], {"name": "two"})

    def test_literal_block(self):
        data = onboard.parse_subset_yaml("text: |\n  line one\n    indented\n  last\n")
        self.assertEqual(data["text"], "line one\n  indented\nlast\n")

    def test_colon_inside_list_scalar(self):
        data = onboard.parse_subset_yaml("qs:\n  - Ask about: the release\n")
        self.assertEqual(data["qs"], ["Ask about: the release"])

    def test_duplicate_key_rejected(self):
        with self.assertRaises(ValueError):
            onboard.parse_subset_yaml("a: 1\na: 2\n")

    def test_unknown_top_key_rejected(self):
        with self.assertRaises(ValueError):
            onboard.validate_manifest(
                {"version": 1, "org": {"id": "x", "workspace": "x"}, "bogus": 1}, "t")


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox()
        self.addCleanup(self.box.cleanup)

    def statuses(self, data, phase=None):
        return [s["status"] for s in data["steps"] if phase is None or s["phase"] == phase]

    def test_install_then_idempotent_rerun(self):
        manifest = self.box.manifest()
        data, _ = self.box.run_json("install", "--manifest", str(manifest), expect=0)
        self.assertTrue(self.box.kb_clone.is_dir())
        hooks = sh(["git", "-C", str(self.box.kb_clone), "config", "--local", "--get",
                    "core.hooksPath"], env=self.box.git_env).strip()
        self.assertEqual(hooks, ".githooks")
        self.assertTrue(self.box.ws_agents.exists())
        self.assertEqual((self.box.home / "workspaces" / "exampleco" / "CLAUDE.md").read_text(),
                         "@AGENTS.md\n")
        for target in (".claude", ".agents"):
            self.assertTrue((self.box.home / target / "skills" / "example-skill" / "SKILL.md").exists())
        self.assertTrue((self.box.home / ".synthesis" / "onboarding" / "receipts.json").exists())
        self.assertIn("changed", self.statuses(data))
        data2, _ = self.box.run_json("install", "--manifest", str(manifest), expect=0)
        self.assertNotIn("changed", self.statuses(data2))
        self.assertNotIn("error", self.statuses(data2))

    def test_dry_run_touches_nothing(self):
        manifest = self.box.manifest()
        data, _ = self.box.run_json("install", "--manifest", str(manifest), "--dry-run", expect=0)
        self.assertIn("would-change", self.statuses(data))
        self.assertFalse((self.box.home / "workspaces").exists())
        self.assertFalse((self.box.home / ".synthesis" / "onboarding" / "receipts.json").exists())
        self.assertEqual(list(self.box.cache.iterdir()), [])

    def test_superseded_remote_is_repointed(self):
        manifest = self.box.manifest()
        self.box.run_json("install", "--manifest", str(manifest), expect=0)
        sh(["git", "-C", str(self.box.kb_clone), "remote", "set-url", "origin",
            str(self.box.old_kb_remote)], env=self.box.git_env)
        data, _ = self.box.run_json("install", "--manifest", str(manifest), expect=0)
        origin = sh(["git", "-C", str(self.box.kb_clone), "remote", "get-url", "origin"],
                    env=self.box.git_env).strip()
        self.assertEqual(origin, str(self.box.kb_remote))
        kb_steps = [s for s in data["steps"] if s["phase"] == "knowledge-base"]
        self.assertTrue(any("repointed" in s["detail"] for s in kb_steps))

    def test_user_edited_workspace_file_is_preserved(self):
        manifest = self.box.manifest()
        self.box.run_json("install", "--manifest", str(manifest), expect=0)
        edited = self.box.ws_agents.read_text().replace(
            "generated by synthesis-onboarding", "hand-edited") + "\nMy note.\n"
        self.box.ws_agents.write_text(edited)
        data, _ = self.box.run_json("install", "--manifest", str(manifest), expect=0)
        self.assertEqual(self.box.ws_agents.read_text(), edited)
        self.assertIn("warning", self.statuses(data, "workspace"))

    def test_migration_removes_and_archives(self):
        legacy = self.box.home / ".claude" / "skills" / "example-legacy-skill"
        legacy.mkdir(parents=True)
        (legacy / "SKILL.md").write_text("old\n")
        manifest = self.box.manifest(migrations=[{"from": "example-legacy-skill", "action": "remove"}])
        self.box.run_json("install", "--manifest", str(manifest), expect=0)
        self.assertFalse(legacy.exists())
        backups = list((self.box.home / ".synthesis" / "onboarding" / "backups").rglob("SKILL.md"))
        self.assertTrue(backups)
        data, _ = self.box.run_json("install", "--manifest", str(manifest), expect=0)
        self.assertNotIn("changed", self.statuses(data, "migrations"))

    def test_doctor_healthy_then_detects_missing_kb(self):
        manifest = self.box.manifest()
        self.box.run_json("install", "--manifest", str(manifest), expect=0)
        self.box.run_json("doctor", "--manifest", str(manifest), expect=0)
        shutil.rmtree(self.box.kb_clone)
        data, _ = self.box.run_json("doctor", "--manifest", str(manifest), expect=1)
        self.assertIn("error", self.statuses(data))

    def test_auth_failure_is_action_needed_with_help(self):
        manifest = self.box.manifest(kb_primary=str(self.box.remotes / "missing.git"))
        data, _ = self.box.run_json("install", "--manifest", str(manifest), expect=1)
        actions = [s for s in data["steps"] if s["status"] == "action-needed"]
        self.assertTrue(actions)
        self.assertIn("help desk", (actions[0].get("hint") or "").lower())

    def test_unknown_manifest_key_exits_2(self):
        path = self.box.root / "bad.yaml"
        path.write_text("version: 1\norg:\n  id: x\n  workspace: x\nnope: 1\n")
        self.box.run_json("install", "--manifest", str(path), expect=2)

    def test_init_workspace_scaffold_and_rerun(self):
        self.box.run_json("init-workspace", "--workspace", "alice", expect=0)
        repo = self.box.home / "workspaces" / "alice" / "ai-knowledge-alice"
        for rel in ("AGENTS.md", "CLAUDE.md", "README.md", "projects/index.yaml", "lessons/README.md"):
            self.assertTrue((repo / rel).exists(), rel)
        log = sh(["git", "-C", str(repo), "log", "--oneline"], env=self.box.git_env)
        self.assertEqual(len(log.strip().splitlines()), 1)
        self.box.run_json("init-workspace", "--workspace", "alice", expect=0)
        log2 = sh(["git", "-C", str(repo), "log", "--oneline"], env=self.box.git_env)
        self.assertEqual(len(log2.strip().splitlines()), 1)

    def test_fallback_installs_on_fresh_machine_with_client(self):
        """Regression (2026-08-03 post-merge QA): with a client present and
        the plugin CLI unavailable, a fresh machine must get fallback copies.
        `install.sh status` exits 0 when the target dirs don't exist yet, so
        the probe must also require copies to be present before skipping."""
        env = dict(os.environ)
        env.update(self.box.env_overrides())
        env["SYNTHESIS_CLAUDE_BIN"] = "/usr/bin/true"
        env["SYNTHESIS_ONBOARD_NO_PLUGIN_CLI"] = "1"
        env["SYNTHESIS_SKILLS_SOURCE_DIR"] = str(REPO_ROOT)

        def run_engine(*args):
            return subprocess.run(
                [sys.executable, str(ENGINE)] + list(args) + ["--json"],
                env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        proc = run_engine("install")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        copies = list((self.box.home / ".claude" / "skills").glob("synthesis-*"))
        self.assertTrue(copies, "fallback copies missing after fresh install")
        proc2 = run_engine("install")
        data2 = json.loads(proc2.stdout)
        self.assertNotIn("changed", [s["status"] for s in data2["steps"]])
        proc3 = run_engine("doctor")
        self.assertEqual(proc3.returncode, 0, proc3.stdout + proc3.stderr)

    def test_uninstall_archives_generated_files_only(self):
        manifest = self.box.manifest()
        self.box.run_json("install", "--manifest", str(manifest), expect=0)
        self.box.run_json("uninstall", expect=0)
        self.assertFalse(self.box.ws_agents.exists())
        self.assertTrue(self.box.kb_clone.is_dir())


if __name__ == "__main__":
    unittest.main(verbosity=2)

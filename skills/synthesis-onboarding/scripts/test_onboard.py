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
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parent
ENGINE = SCRIPTS / "onboard.py"
REPO_ROOT = SCRIPTS.parents[2]

sys.path.insert(0, str(SCRIPTS))
import onboard  # noqa: E402
import whole_system  # noqa: E402


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

    def run_with_env(self, extra, *args, expect=None):
        env = dict(os.environ)
        env.update(self.env_overrides())
        env.update(extra)
        proc = subprocess.run(
            [sys.executable, str(ENGINE)] + list(args),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if expect is not None and proc.returncode != expect:
            raise AssertionError(
                "exit %d != %d\nstdout:\n%s\nstderr:\n%s"
                % (proc.returncode, expect, proc.stdout, proc.stderr)
            )
        return proc

    def fake_client(self, version=None):
        # Default to the live source manifest: a literal here breaks on the
        # first branch that bumps the release version, since the engine's
        # expectation is read from the same manifest at run time.
        if version is None:
            version = onboard.source_plugin_version()
        path = self.root / "fake-client"
        path.write_text(
            "#!/bin/sh\n"
            "if [ \"${1:-}\" = plugin ] && [ \"${2:-}\" = list ]; then\n"
            "  printf '%s\\n' '{\"installed\":[{\"pluginId\":\"synthesis-skills@synthesis-engineering\",\"name\":\"synthesis-skills\",\"version\":\"%s\",\"enabled\":true}]}'\n"
            "fi\n"
            "exit 0\n" % ("%s", version),
            encoding="utf-8",
        )
        path.chmod(0o755)
        return path

    def seed_currency(self, version=None, ref="stable"):
        if version is None:
            version = onboard.source_plugin_version()
        path = self.home / ".synthesis" / "onboarding" / "plugin-currency.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "targets": {
                        ref: {"version": version, "checked_at": time.time()}
                    },
                }
            ),
            encoding="utf-8",
        )

    def answers(self, workspace="example-user", git_identity=None):
        data = {
            "workspace": workspace,
            "display_name": "Example User",
            "timezone": "UTC",
            "tone": ["direct", "substantive", "kind"],
            "avoid_phrases": ["empty promise"],
            "personal_remote_patterns": ["[:/]example-user/"],
            "confidential_terms": [],
            "inbox_cleanup": False,
        }
        if git_identity:
            data["git_name"], data["git_email"] = git_identity
        path = self.root / "answers.json"
        path.write_text(
            json.dumps(data),
            encoding="utf-8",
        )
        return path

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

    def test_manifest_accepts_release_channel_and_exact_org_pin(self):
        data = onboard.validate_manifest(
            {
                "version": 1,
                "org": {"id": "x", "workspace": "x"},
                "ecosystem": {
                    "plugin": True,
                    "clients": ["claude", "codex"],
                    "channel": "stable",
                    "version_pin": "4.74.0",
                },
            },
            "t",
        )
        self.assertEqual(data["ecosystem"]["version_pin"], "4.74.0")

    def test_manifest_rejects_unknown_channel_and_non_exact_pin(self):
        for ecosystem in (
            {"channel": "preview"},
            {"channel": "stable", "version_pin": "4.74"},
        ):
            with self.assertRaises(ValueError):
                onboard.validate_manifest(
                    {
                        "version": 1,
                        "org": {"id": "x", "workspace": "x"},
                        "ecosystem": ecosystem,
                    },
                    "t",
                )

    def test_manifest_clients_and_plugin_switch_are_enforced(self):
        manifest = onboard.validate_manifest(
            {
                "version": 1,
                "org": {"id": "x", "workspace": "x"},
                "ecosystem": {"plugin": False, "clients": ["codex"]},
            },
            "t",
        )
        self.assertEqual(onboard.effective_clients(None, manifest), ["codex"])
        self.assertEqual(
            onboard.effective_clients("claude,codex", manifest),
            ["claude", "codex"],
        )
        with self.assertRaises(ValueError):
            onboard.validate_manifest(
                {
                    "version": 1,
                    "org": {"id": "x", "workspace": "x"},
                    "ecosystem": {"plugin": "yes"},
                },
                "t",
            )


class WholeSystemTests(unittest.TestCase):
    def test_catalog_and_probe_universe_match(self):
        catalog = whole_system.load_catalog(REPO_ROOT)
        self.assertEqual(len(whole_system.catalog_ids(catalog)), 11)
        self.assertEqual(
            set(whole_system.catalog_ids(catalog)),
            {
                "skills", "session-context", "hooks-gates", "agent-kernel",
                "runtime-engines", "coordination", "doctors-conformance",
                "personal-policy", "organization", "knowledge-bases", "lifecycle",
            },
        )

    def test_every_hard_stop_has_a_real_scaffold(self):
        from check_scaffolds import audit

        self.assertEqual(audit(REPO_ROOT), [])

    def test_kernel_budget_and_hook_merge_are_deterministic(self):
        self.assertEqual(whole_system.kernel_budget("x" * 100), (100, "ok"))
        size, state = whole_system.kernel_budget(
            "x" * (whole_system.KERNEL_HARD_LIMIT + 1)
        )
        self.assertEqual(size, whole_system.KERNEL_HARD_LIMIT + 1)
        self.assertEqual(state, "over")
        target = Path("/tmp/example/message_guard.py")
        merged, changed = whole_system.merge_message_guard_hook({}, target)
        self.assertTrue(changed)
        merged2, changed2 = whole_system.merge_message_guard_hook(merged, target)
        self.assertFalse(changed2)
        self.assertEqual(merged2, merged)
        for client in ("claude", "codex"):
            with_kernel, kernel_changed = whole_system.merge_kernel_sync_hook(
                merged2, Path("/tmp/example/kernel_sync.py"), client
            )
            self.assertTrue(kernel_changed)
            again, changed_again = whole_system.merge_kernel_sync_hook(
                with_kernel, Path("/tmp/example/kernel_sync.py"), client
            )
            self.assertFalse(changed_again)
            self.assertEqual(again, with_kernel)

    def test_platform_detection_treats_wsl_as_supported_linux_userland(self):
        self.assertEqual(
            onboard.platform_family(
                platform="linux",
                environ={"WSL_DISTRO_NAME": "Ubuntu"},
                proc_version="Linux version",
            ),
            "wsl",
        )
        self.assertEqual(
            onboard.platform_family(
                platform="linux", environ={}, proc_version="Linux version"
            ),
            "linux",
        )
        self.assertEqual(
            onboard.platform_family(platform="win32", environ={}, proc_version=""),
            "native-windows",
        )

    def test_codex_hooks_feature_merge_is_narrow_and_respects_false(self):
        original = 'model = "example"\n\n[features]\nmemories = true\n\n[projects.x]\ntrust_level = "trusted"\n'
        merged, changed, block = onboard.merge_codex_hooks_feature(original)
        self.assertTrue(changed)
        self.assertTrue(onboard.codex_hooks_feature(merged))
        self.assertIn('[projects.x]\ntrust_level = "trusted"', merged)
        self.assertEqual(onboard.managed_codex_hooks_block(merged), block)
        again, changed_again, _ = onboard.merge_codex_hooks_feature(merged)
        self.assertFalse(changed_again)
        self.assertEqual(again, merged)
        with self.assertRaises(ValueError):
            onboard.merge_codex_hooks_feature("[features]\nhooks = false\n")

    def test_guided_interview_builds_full_profile_without_stdin_assumptions(self):
        args = SimpleNamespace(profile=None, answers=None, workspace=None)
        catalog = whole_system.load_catalog(REPO_ROOT)
        with (
            patch.object(onboard, "configured_git_identity", return_value=None),
            patch.object(
                onboard,
                "_ask",
                side_effect=[
                    "full",
                    "example-user",
                    "Example User",
                    "UTC",
                    "direct, kind",
                    "empty promise",
                    "no",
                    "Example User",
                    "example@example.invalid",
                ],
            ),
        ):
            profile, answers, choices = onboard.collect_init_inputs(
                args, None, catalog
            )
        self.assertEqual(profile, "full")
        self.assertEqual(answers["display_name"], "Example User")
        self.assertEqual(answers["tone"], ["direct", "kind"])
        self.assertEqual(answers["git_name"], "Example User")
        self.assertEqual(answers["git_email"], "example@example.invalid")
        self.assertEqual(choices["organization"], "declined")

    def test_noninteractive_full_init_requires_git_identity_before_mutation(self):
        box = Sandbox()
        self.addCleanup(box.cleanup)
        args = SimpleNamespace(
            profile="full", answers=box.answers(), workspace=None
        )
        catalog = whole_system.load_catalog(REPO_ROOT)
        with patch.object(onboard, "configured_git_identity", return_value=None):
            with self.assertRaisesRegex(ValueError, "git_name"):
                onboard.collect_init_inputs(args, None, catalog)

    def test_full_init_configures_repo_local_identity_from_answers(self):
        box = Sandbox()
        self.addCleanup(box.cleanup)
        client = box.fake_client()
        answers = box.answers(
            git_identity=("Example User", "example@example.invalid")
        )
        box.seed_currency()
        env = dict(os.environ)
        env.update(box.env_overrides())
        for key in (
            "GIT_AUTHOR_NAME",
            "GIT_AUTHOR_EMAIL",
            "GIT_COMMITTER_NAME",
            "GIT_COMMITTER_EMAIL",
        ):
            env.pop(key, None)
        env.update({
            "SYNTHESIS_CLAUDE_BIN": str(client),
            "SYNTHESIS_CODEX_BIN": str(client),
            "GIT_CONFIG_GLOBAL": str(box.root / "empty-gitconfig"),
        })
        proc = subprocess.run(
            [
                sys.executable,
                str(ENGINE),
                "init",
                "--profile",
                "full",
                "--answers",
                str(answers),
                "--no-services",
                "--json",
            ],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        data = json.loads(proc.stdout)
        self.assertFalse(
            [step for step in data["steps"] if step["status"] == "action-needed"]
        )
        repo = (
            box.home
            / "workspaces"
            / "example-user"
            / "ai-knowledge-example-user"
        )
        name = sh(
            ["git", "-C", str(repo), "config", "--local", "user.name"],
            env=env,
        ).strip()
        email = sh(
            ["git", "-C", str(repo), "config", "--local", "user.email"],
            env=env,
        ).strip()
        self.assertEqual((name, email), ("Example User", "example@example.invalid"))
        log = sh(
            ["git", "-C", str(repo), "log", "--oneline"],
            env=env,
        )
        self.assertEqual(len(log.strip().splitlines()), 1)


class PluginTests(unittest.TestCase):
    policy = {"channel": "stable", "version_pin": None}

    def test_codex_history_sync_runs_durable_doctor_and_checks_started_root(self):
        with tempfile.TemporaryDirectory(prefix="onboard-history-") as root:
            home = Path(root)
            runtime = (
                home
                / ".synthesis/plugin-cache-recovery/synthesis-engineering"
                / ".synthesis-skills-cache-guardian.py"
            )
            runtime.parent.mkdir(parents=True)
            runtime.write_text("guardian\n", encoding="utf-8")
            historical = (
                home
                / ".codex/plugins/cache/synthesis-engineering/synthesis-skills/4.23.0"
            )
            target = historical / "skills/synthesis-autopilot/scripts/autopilot_gate.py"
            target.parent.mkdir(parents=True)
            target.write_text("pass\n", encoding="utf-8")
            (historical / "hooks").mkdir()
            (historical / "hooks/hooks.json").write_text(
                json.dumps(
                    {
                        "hooks": {
                            "Stop": [
                                {
                                    "hooks": [
                                        {
                                            "command": (
                                                "python3 ${CLAUDE_PLUGIN_ROOT}/skills/"
                                                "synthesis-autopilot/scripts/autopilot_gate.py --gate"
                                            )
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )

            with patch.object(onboard, "HOME", home), patch.object(
                onboard, "run", return_value=(0, '{"verified": 1}\n', "")
            ) as runner:
                success, detail = onboard.synchronize_codex_history("4.23.0")

        self.assertTrue(success, detail)
        self.assertIn("4.23.0", detail)
        runner.assert_called_once_with(
            [sys.executable, str(runtime), "--doctor"],
            env={"HOME": str(home)},
            timeout=600,
        )

    def test_codex_history_sync_fails_if_started_root_remains_absent(self):
        with tempfile.TemporaryDirectory(prefix="onboard-history-") as root:
            home = Path(root)
            runtime = (
                home
                / ".synthesis/plugin-cache-recovery/synthesis-engineering"
                / ".synthesis-skills-cache-guardian.py"
            )
            runtime.parent.mkdir(parents=True)
            runtime.write_text("guardian\n", encoding="utf-8")
            with patch.object(onboard, "HOME", home), patch.object(
                onboard, "run", return_value=(0, '{"verified": 1}\n', "")
            ):
                success, detail = onboard.synchronize_codex_history("4.23.0")

        self.assertFalse(success)
        self.assertIn("4.23.0", detail)
        self.assertIn("absent", detail)

    def test_codex_history_sync_is_optional_without_a_durable_guardian(self):
        with tempfile.TemporaryDirectory(prefix="onboard-history-") as root:
            with patch.object(onboard, "HOME", Path(root)), patch.object(
                onboard, "run"
            ) as runner:
                success, detail = onboard.synchronize_codex_history("4.23.0")

        self.assertTrue(success, detail)
        self.assertIn("not installed", detail)
        runner.assert_not_called()

    def test_codex_history_sync_refuses_a_dangling_guardian_symlink(self):
        with tempfile.TemporaryDirectory(prefix="onboard-history-") as root:
            home = Path(root)
            runtime = (
                home
                / ".synthesis/plugin-cache-recovery/synthesis-engineering"
                / ".synthesis-skills-cache-guardian.py"
            )
            runtime.parent.mkdir(parents=True)
            runtime.symlink_to(runtime.parent / "missing-guardian.py")
            with patch.object(onboard, "HOME", home), patch.object(
                onboard, "run"
            ) as runner:
                success, detail = onboard.synchronize_codex_history("4.23.0")

        self.assertFalse(success)
        self.assertIn("unsafe type", detail)
        runner.assert_not_called()

    def test_plugin_record_reads_codex_and_claude_versions(self):
        codex = {"installed": [{
            "pluginId": "synthesis-skills@synthesis-engineering",
            "name": "synthesis-skills",
            "version": "4.24.0",
            "enabled": True,
        }]}
        claude = [{
            "id": "synthesis-skills@synthesis-engineering",
            "version": "4.24.0",
            "enabled": True,
        }]
        with patch.object(onboard, "run", return_value=(0, json.dumps(codex), "")):
            self.assertEqual(onboard.plugin_record("codex", "codex"), (True, "4.24.0"))
        with patch.object(onboard, "run", return_value=(0, json.dumps(claude), "")):
            self.assertEqual(onboard.plugin_record("claude", "claude"), (True, "4.24.0"))

    def test_refresh_plugin_uses_each_clients_native_update_contract(self):
        with patch.object(onboard, "run", return_value=(0, "", "")) as runner:
            self.assertTrue(onboard.refresh_plugin("codex", "codex", self.policy)[0])
            self.assertEqual(
                runner.call_args_list[0].args[0],
                ["codex", "plugin", "marketplace", "upgrade", "synthesis-engineering", "--json"],
            )
            self.assertEqual(
                runner.call_args_list[1].args[0],
                ["codex", "plugin", "add", "synthesis-skills@synthesis-engineering"],
            )
        with patch.object(onboard, "run", return_value=(0, "", "")) as runner:
            self.assertTrue(onboard.refresh_plugin("claude", "claude", self.policy)[0])
            self.assertEqual(runner.call_count, 2)
            self.assertEqual(
                runner.call_args_list[1].args[0],
                ["claude", "plugin", "update", "synthesis-skills@synthesis-engineering"],
            )

    def test_install_does_not_replace_an_existing_live_plugin_cache(self):
        report = onboard.Report(as_json=True)
        with patch.object(onboard, "plugin_record", return_value=(True, "4.23.0")), \
             patch.object(onboard, "expected_source_plugin_version", return_value="4.24.0"), \
             patch.object(onboard, "refresh_plugin") as refresh:
            onboard.phase_ecosystem(
                report,
                {"codex": "codex"},
                dry_run=False,
                no_plugin_cli=False,
                policy=self.policy,
                refresh_native_plugins=False,
            )
        refresh.assert_not_called()
        self.assertEqual(report.steps[0]["status"], onboard.ACTION)
        self.assertIn("onboard.py update", report.steps[0]["hint"])

    def test_update_refreshes_and_accepts_newer_version_from_old_plugin_cache(self):
        report = onboard.Report(as_json=True)
        with patch.object(
            onboard,
            "plugin_record",
            side_effect=[(True, "4.23.0"), (True, "4.24.0")],
        ), patch.object(
            onboard, "expected_source_plugin_version", return_value=None
        ), patch.object(
            onboard, "resolve_target_version", return_value=("4.24.0", "fixture")
        ), patch.object(
            onboard, "refresh_plugin", return_value=(True, "refreshed")
        ) as refresh, patch.object(
            onboard,
            "synchronize_codex_history",
            return_value=(True, "historical root restored"),
        ) as synchronize:
            onboard.phase_ecosystem(
                report,
                {"codex": "codex"},
                dry_run=False,
                no_plugin_cli=False,
                policy=self.policy,
                refresh_native_plugins=True,
            )
        refresh.assert_called_once_with(
            "codex", "codex", self.policy, reconfigure=True
        )
        synchronize.assert_called_once_with("4.23.0")
        self.assertEqual(report.steps[0]["status"], onboard.CHANGED)
        self.assertIn("4.23.0 -> 4.24.0", report.steps[0]["detail"])

    def test_update_fails_when_invoking_codex_history_is_not_restored(self):
        report = onboard.Report(as_json=True)
        with patch.object(
            onboard, "plugin_record", return_value=(True, "4.23.0")
        ), patch.object(
            onboard, "expected_policy_version", return_value=("4.24.0", "fixture")
        ), patch.object(
            onboard, "refresh_plugin", return_value=(True, "refreshed")
        ), patch.object(
            onboard,
            "synchronize_codex_history",
            return_value=(False, "historical root is still absent"),
        ) as synchronize:
            onboard.phase_ecosystem(
                report,
                {"codex": "codex"},
                dry_run=False,
                no_plugin_cli=False,
                policy=self.policy,
                refresh_native_plugins=True,
            )

        synchronize.assert_called_once_with("4.23.0")
        self.assertEqual(report.steps[0]["status"], onboard.ERROR)
        self.assertIn("historical cache preservation failed", report.steps[0]["detail"])
        self.assertEqual(report.steps[0]["hint"], "historical root is still absent")
        self.assertNotIn("plugin updated", report.steps[0]["detail"])

    def test_claude_update_does_not_invoke_codex_history_guardian(self):
        report = onboard.Report(as_json=True)
        with patch.object(
            onboard,
            "plugin_record",
            side_effect=[(True, "4.23.0"), (True, "4.24.0")],
        ), patch.object(
            onboard, "expected_policy_version", return_value=("4.24.0", "fixture")
        ), patch.object(
            onboard, "refresh_plugin", return_value=(True, "refreshed")
        ), patch.object(onboard, "synchronize_codex_history") as synchronize:
            onboard.phase_ecosystem(
                report,
                {"claude": "claude"},
                dry_run=False,
                no_plugin_cli=False,
                policy=self.policy,
                refresh_native_plugins=True,
            )

        synchronize.assert_not_called()
        self.assertEqual(report.steps[0]["status"], onboard.CHANGED)

    def test_installed_plugin_cache_never_becomes_version_expectation(self):
        with tempfile.TemporaryDirectory(prefix="onboard-plugin-cache-") as root:
            cache = (
                Path(root)
                / ".codex/plugins/cache/synthesis-engineering/synthesis-skills/4.23.0"
            )
            (cache / ".git").mkdir(parents=True)
            (cache / ".codex-plugin").mkdir()
            (cache / ".codex-plugin/plugin.json").write_text(
                json.dumps({"version": "4.23.0"}), encoding="utf-8"
            )

            with patch.object(onboard, "source_root", return_value=cache):
                self.assertIsNone(onboard.expected_source_plugin_version())

    def test_marketplace_add_targets_stable_edge_and_version_pin(self):
        self.assertEqual(
            onboard.marketplace_add_command("claude", "claude", self.policy),
            [
                "claude", "plugin", "marketplace", "add",
                "synthesisengineering/synthesis-skills@stable",
            ],
        )
        self.assertEqual(
            onboard.marketplace_add_command(
                "codex", "codex", {"channel": "edge", "version_pin": None}
            ),
            [
                "codex", "plugin", "marketplace", "add",
                "synthesisengineering/synthesis-skills", "--ref", "main", "--json",
            ],
        )
        self.assertIn(
            "synthesisengineering/synthesis-skills@v4.74.0",
            onboard.marketplace_add_command(
                "claude",
                "claude",
                {"channel": "stable", "version_pin": "4.74.0"},
            ),
        )

    def test_existing_marketplace_is_reconfigured_before_fresh_install(self):
        calls = [
            (1, "", "already configured"),
            (0, "", ""),
            (0, "", ""),
            (0, "", ""),
        ]
        with patch.object(onboard, "run", side_effect=calls) as runner:
            success, _ = onboard.install_plugin("codex", "codex", self.policy)
        self.assertTrue(success)
        self.assertEqual(
            runner.call_args_list[1].args[0],
            ["codex", "plugin", "marketplace", "remove", "synthesis-engineering"],
        )
        self.assertIn("--ref", runner.call_args_list[2].args[0])

    def test_exact_pin_is_the_version_expectation_even_from_newer_source(self):
        policy = {"channel": "stable", "version_pin": "4.73.0"}
        with patch.object(
            onboard, "expected_source_plugin_version", return_value="4.74.0"
        ), patch.object(onboard, "resolve_target_version") as resolver:
            self.assertEqual(
                onboard.expected_policy_version(policy),
                ("4.73.0", "exact version pin"),
            )
        resolver.assert_not_called()

    def test_bootstrap_defaults_to_stable_and_maps_edge_to_main(self):
        bootstrap = (REPO_ROOT / "onboard.sh").read_text(encoding="utf-8")
        self.assertIn('CHANNEL="${SYNTHESIS_ONBOARD_CHANNEL:-stable}"', bootstrap)
        self.assertIn('stable) SOURCE_REF="stable"', bootstrap)
        self.assertIn('edge) SOURCE_REF="main"', bootstrap)
        self.assertIn('git clone --branch "$SOURCE_REF" --single-branch', bootstrap)

    def test_public_docs_expose_stable_edge_and_org_pin_contract(self):
        skill = (REPO_ROOT / "skills/synthesis-onboarding/SKILL.md").read_text(
            encoding="utf-8"
        )
        manifest = (
            REPO_ROOT / "skills/synthesis-onboarding/references/org-manifest.md"
        ).read_text(encoding="utf-8")
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        for text in (skill, manifest, readme):
            self.assertIn("stable", text)
            self.assertIn("edge", text)
        self.assertIn("version_pin", manifest)
        self.assertIn("/stable/onboard.sh", skill)
        self.assertIn("/stable/onboard.sh", readme)

    def test_doctor_reports_current_behind_and_unverifiable_currency(self):
        with patch.object(onboard, "run", return_value=(0, "", "")), \
             patch.object(onboard, "resolve_client", return_value="codex"), \
             patch.object(onboard, "plugin_record", return_value=(True, "4.74.0")), \
             patch.object(onboard, "expected_policy_version", return_value=("4.74.0", "fixture")), \
             patch.object(onboard, "render_layer_doctor", return_value=False):
            report = onboard.Report(as_json=True)
            self.assertEqual(onboard.doctor(report, None, ["codex"], self.policy), 0)
            self.assertEqual(report.steps[-1]["status"], onboard.OK)

        with patch.object(onboard, "run", return_value=(0, "", "")), \
             patch.object(onboard, "resolve_client", return_value="codex"), \
             patch.object(onboard, "plugin_record", return_value=(True, "4.73.0")), \
             patch.object(onboard, "expected_policy_version", return_value=("4.74.0", "fixture")), \
             patch.object(onboard, "render_layer_doctor", return_value=False):
            report = onboard.Report(as_json=True)
            self.assertEqual(onboard.doctor(report, None, ["codex"], self.policy), 1)
            self.assertEqual(report.steps[-1]["status"], onboard.ACTION)

        with patch.object(onboard, "run", return_value=(0, "", "")), \
             patch.object(onboard, "resolve_client", return_value="codex"), \
             patch.object(onboard, "plugin_record", return_value=(True, "4.74.0")), \
             patch.object(onboard, "expected_policy_version", return_value=(None, "offline")), \
             patch.object(onboard, "render_layer_doctor", return_value=False):
            report = onboard.Report(as_json=True)
            self.assertEqual(onboard.doctor(report, None, ["codex"], self.policy), 2)
            self.assertEqual(report.steps[-1]["status"], onboard.WARN)

    def test_preflight_skips_absent_codex_without_failing_when_claude_present(self):
        with patch.object(onboard, "run", return_value=(0, "git version 2.39.5", "")), \
             patch.object(
                 onboard, "resolve_client",
                 side_effect=lambda name: "/path/to/claude" if name == "claude" else None,
             ), \
             patch.object(onboard, "platform_family", return_value="macos"):
            report = onboard.Report(as_json=True)
            clients = onboard.phase_preflight(report, ["claude", "codex"])
        self.assertEqual(clients, {"claude": "/path/to/claude", "codex": None})
        by_phase = [s for s in report.steps if s["phase"] == "preflight"]
        claude_step = next(s for s in by_phase if "claude" in s["detail"])
        codex_step = next(s for s in by_phase if "codex" in s["detail"])
        self.assertEqual(claude_step["status"], onboard.OK)
        self.assertEqual(codex_step["status"], onboard.SKIP)
        self.assertEqual(report.exit_code(), 0)

    def test_preflight_skips_absent_claude_without_failing_when_codex_present(self):
        with patch.object(onboard, "run", return_value=(0, "git version 2.39.5", "")), \
             patch.object(
                 onboard, "resolve_client",
                 side_effect=lambda name: "/path/to/codex" if name == "codex" else None,
             ), \
             patch.object(onboard, "platform_family", return_value="macos"):
            report = onboard.Report(as_json=True)
            clients = onboard.phase_preflight(report, ["claude", "codex"])
        self.assertEqual(clients, {"claude": None, "codex": "/path/to/codex"})
        by_phase = [s for s in report.steps if s["phase"] == "preflight"]
        claude_step = next(s for s in by_phase if "claude" in s["detail"])
        codex_step = next(s for s in by_phase if "codex" in s["detail"])
        self.assertEqual(claude_step["status"], onboard.SKIP)
        self.assertEqual(codex_step["status"], onboard.OK)
        self.assertEqual(report.exit_code(), 0)

    def test_ecosystem_phase_only_touches_the_present_client(self):
        # Reproduces the exact shape from a real single-client run: one name
        # resolves to a real binary, the other to None from phase_preflight.
        # Motivating defect: an unconditional per-client step here would either
        # crash on the missing binary or wrongly report an error for a client
        # the user never asked to have installed.
        with patch.object(onboard, "plugin_record", return_value=(True, "4.86.0")), \
             patch.object(onboard, "expected_policy_version", return_value=("4.86.0", "fixture")):
            report = onboard.Report(as_json=True)
            onboard.phase_ecosystem(
                report,
                {"claude": "/path/to/claude", "codex": None},
                dry_run=False,
                no_plugin_cli=False,
                policy=self.policy,
                refresh_native_plugins=False,
            )
        ecosystem_steps = [s for s in report.steps if s["phase"] == "ecosystem"]
        self.assertEqual(len(ecosystem_steps), 1)
        self.assertIn("claude", ecosystem_steps[0]["detail"])
        self.assertNotEqual(ecosystem_steps[0]["status"], onboard.ERROR)
        self.assertEqual(report.exit_code(), 0)


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
        partial, _ = self.box.run_json(
            "doctor", "--manifest", str(manifest), expect=1
        )
        self.assertTrue(
            any(
                step.get("layer") == "hooks-gates"
                and step.get("layer_state") == "missing"
                for step in partial["steps"]
            )
        )
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
        self.assertEqual(proc3.returncode, 1, proc3.stdout + proc3.stderr)
        data3 = json.loads(proc3.stdout)
        self.assertTrue(
            any(
                step.get("layer") == "session-context"
                and step.get("layer_state") == "missing"
                for step in data3["steps"]
            )
        )

    def test_full_init_converges_every_layer_and_reruns_cleanly(self):
        client = self.box.fake_client()
        answers = self.box.answers()
        self.box.seed_currency()
        env = {
            "SYNTHESIS_CLAUDE_BIN": str(client),
            "SYNTHESIS_CODEX_BIN": str(client),
        }
        proc = self.box.run_with_env(
            env,
            "init",
            "--profile",
            "full",
            "--answers",
            str(answers),
            "--no-services",
            "--json",
            expect=0,
        )
        data = json.loads(proc.stdout)
        layers = [step for step in data["steps"] if step.get("phase") == "layer"]
        self.assertEqual(len(layers), 11)
        self.assertNotIn("missing", [step.get("layer_state") for step in layers])
        self.assertEqual(
            next(step for step in layers if step["layer"] == "organization")["layer_state"],
            "declined",
        )
        workspace = self.box.home / "workspaces" / "example-user"
        self.assertTrue((workspace / "AGENTS.source.md").is_file())
        self.assertTrue((workspace / "AGENTS.md").is_file())
        self.assertTrue((workspace / "CLAUDE.md").is_file())
        self.assertTrue(
            (
                self.box.home
                / ".synthesis"
                / "onboarding"
                / "bin"
                / "kernel_sync.py"
            ).is_file()
        )
        self.assertTrue(
            (self.box.home / ".synthesis" / "message-guard" / "patterns.json").is_file()
        )

        self.box.seed_currency()
        proc2 = self.box.run_with_env(
            env,
            "init",
            "--profile",
            "full",
            "--answers",
            str(answers),
            "--no-services",
            "--json",
            expect=0,
        )
        data2 = json.loads(proc2.stdout)
        changed = [step for step in data2["steps"] if step["status"] == "changed"]
        self.assertEqual(changed, [])

        source = workspace / "AGENTS.source.md"
        source.write_text(
            source.read_text(encoding="utf-8") + "\n## Personal addition\n\nKeep evidence close.\n",
            encoding="utf-8",
        )
        sync = subprocess.run(
            [
                sys.executable,
                str(
                    self.box.home
                    / ".synthesis"
                    / "onboarding"
                    / "bin"
                    / "kernel_sync.py"
                ),
                "--hook",
            ],
            env={**os.environ, **self.box.env_overrides(), **env},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(sync.returncode, 0, sync.stdout + sync.stderr)
        self.assertIn("Keep evidence close.", (workspace / "AGENTS.md").read_text(encoding="utf-8"))
        self.assertIn("Keep evidence close.", (workspace / "CLAUDE.md").read_text(encoding="utf-8"))

        agents = workspace / "AGENTS.md"
        agents.write_text("# My edited client instructions\n", encoding="utf-8")
        kernel = self.box.run_with_env(
            env,
            "kernel",
            "--workspace",
            "example-user",
            "--json",
            expect=1,
        )
        self.assertIn("your own edits", kernel.stdout)
        self.assertEqual(agents.read_text(encoding="utf-8"), "# My edited client instructions\n")

        claude = workspace / "CLAUDE.md"
        before = claude.read_text(encoding="utf-8")
        (workspace / "AGENTS.source.md").write_text(
            "x" * (whole_system.KERNEL_HARD_LIMIT + 1), encoding="utf-8"
        )
        self.box.run_with_env(
            env,
            "kernel",
            "--workspace",
            "example-user",
            "--json",
            expect=1,
        )
        self.assertEqual(claude.read_text(encoding="utf-8"), before)

        self.box.run_with_env(env, "uninstall", "--json", expect=0)
        self.assertTrue(source.is_file())
        self.assertFalse(
            (
                self.box.home
                / ".synthesis"
                / "onboarding"
                / "bin"
                / "kernel_sync.py"
            ).exists()
        )
        self.assertFalse(
            onboard._hook_file_has_kernel_sync(
                self.box.home / ".claude" / "settings.json"
            )
        )
        self.assertFalse(
            onboard._hook_file_has_message_guard(
                self.box.home / ".codex" / "hooks.json"
            )
        )
        codex_config = (self.box.home / ".codex" / "config.toml").read_text(
            encoding="utf-8"
        )
        self.assertIsNone(onboard.codex_hooks_feature(codex_config))

    def test_skills_only_profile_is_visibly_partial_but_healthy(self):
        client = self.box.fake_client()
        self.box.seed_currency()
        env = {
            "SYNTHESIS_CLAUDE_BIN": str(client),
            "SYNTHESIS_CODEX_BIN": str(client),
        }
        proc = self.box.run_with_env(
            env,
            "init",
            "--profile",
            "skills-only",
            "--answers",
            str(self.box.answers()),
            "--no-services",
            "--json",
            expect=0,
        )
        data = json.loads(proc.stdout)
        states = {
            step["layer"]: step["layer_state"]
            for step in data["steps"]
            if step.get("phase") == "layer"
        }
        self.assertEqual(states["skills"], "installed")
        self.assertEqual(states["session-context"], "installed")
        self.assertEqual(states["lifecycle"], "installed")
        self.assertTrue(
            all(
                state == "declined"
                for layer, state in states.items()
                if layer not in {"skills", "session-context", "lifecycle", "doctors-conformance"}
            )
        )

    def test_uninstall_archives_generated_files_only(self):
        manifest = self.box.manifest()
        self.box.run_json("install", "--manifest", str(manifest), expect=0)
        self.box.run_json("uninstall", expect=0)
        self.assertFalse(self.box.ws_agents.exists())
        self.assertTrue(self.box.kb_clone.is_dir())


if __name__ == "__main__":
    unittest.main(verbosity=2)

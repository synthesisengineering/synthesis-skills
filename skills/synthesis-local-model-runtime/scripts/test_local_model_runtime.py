import importlib.util
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).with_name("local_model_runtime.py")
SPEC = importlib.util.spec_from_file_location("local_model_runtime", MODULE_PATH)
runtime = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(runtime)


def fixture_profile(memory=128, free=2000, version="0.31.2"):
    return {
        "memory": {"total_gib": memory, "unified": True},
        "storage": {"model_store": "~/.ollama/models", "free_gib": free},
        "runtimes": {
            "ollama": {
                "available": True,
                "version": version,
                "api_reachable": True,
                "configuration": {
                    "source": "test",
                    "kv_cache_type": "f16",
                    "flash_attention": "1",
                },
            },
            "lm_studio": {
                "available": True,
                "version": None,
                "build_identity": "fixture-build",
                "capabilities": dict(runtime.RUNTIME_CAPABILITIES["lm_studio"]),
            },
        },
    }


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.catalog, self.artifacts = runtime.load_catalog(runtime.DEFAULT_CATALOG)

    def test_bundled_catalog_is_valid_and_multi_tier(self):
        families = {artifact["family"] for artifact in self.artifacts}
        self.assertEqual(families, {"qwen", "glm", "kimi", "deepseek"})
        self.assertGreaterEqual(len(self.artifacts), 10)
        self.assertEqual(self.catalog["schema_version"], 2)
        self.assertGreaterEqual(
            sum(runtime.runtime_target(item, "lm_studio") is not None for item in self.artifacts),
            8,
        )

    def test_duplicate_ids_fail_closed(self):
        copied = json.loads(json.dumps(self.catalog))
        copied["artifacts"].append(dict(copied["artifacts"][0]))
        with self.assertRaises(runtime.LocalModelError):
            runtime.validate_catalog(copied)

    def test_credential_bearing_source_url_is_rejected(self):
        copied = json.loads(json.dumps(self.catalog))
        copied["artifacts"][0]["artifact_source_url"] = "https://user:secret@example.test/model"
        with self.assertRaises(runtime.LocalModelError):
            runtime.validate_catalog(copied)

    def test_lm_studio_target_requires_unambiguous_match_terms(self):
        copied = json.loads(json.dumps(self.catalog))
        target = next(
            item["runtime_targets"]["lm_studio"]
            for item in copied["artifacts"]
            if "runtime_targets" in item
        )
        target["match_terms"] = ["q8_0"]
        with self.assertRaises(runtime.LocalModelError):
            runtime.validate_catalog(copied)


class RecommendationTests(unittest.TestCase):
    def setUp(self):
        _, self.artifacts = runtime.load_catalog(runtime.DEFAULT_CATALOG)

    def test_128_gib_policy_selects_exact_four_overrides(self):
        policy = dict(runtime.DEFAULT_POLICY)
        policy.update(
            {
                "required_families": ["qwen", "glm", "kimi", "deepseek"],
                "artifact_overrides": {
                    "qwen": "qwen3.8-27b-q8-0",
                    "glm": "glm-4.7-flash-q8-0",
                    "kimi": "kimi-linear-48b-a3b-q6-k",
                    "deepseek": "deepseek-r1-32b-q8-0",
                },
            }
        )
        plan = runtime.recommend(self.artifacts, fixture_profile(), policy)
        self.assertTrue(plan["ready"])
        self.assertEqual(
            [item["artifact_id"] for item in plan["selections"]],
            [
                "qwen3.8-27b-q8-0",
                "glm-4.7-flash-q8-0",
                "kimi-linear-48b-a3b-q6-k",
                "deepseek-r1-32b-q8-0",
            ],
        )

    def test_runtime_version_blocks_new_huggingface_gguf(self):
        policy = dict(runtime.DEFAULT_POLICY)
        policy.update(
            {
                "required_families": ["qwen"],
                "artifact_overrides": {"qwen": "qwen3.8-27b-q8-0"},
            }
        )
        plan = runtime.recommend(self.artifacts, fixture_profile(version="0.23.2"), policy)
        self.assertFalse(plan["ready"])
        self.assertIn("below 0.30.0", " ".join(plan["blockers"]))

    def test_kimi_requires_compatible_ollama_kv_cache(self):
        policy = dict(runtime.DEFAULT_POLICY)
        policy.update(
            {
                "required_families": ["kimi"],
                "artifact_overrides": {"kimi": "kimi-linear-48b-a3b-q6-k"},
            }
        )
        profile = fixture_profile()
        profile["runtimes"]["ollama"]["configuration"]["kv_cache_type"] = "q8_0"
        plan = runtime.recommend(self.artifacts, profile, policy)
        self.assertFalse(plan["ready"])
        self.assertIn("requires one of f16", " ".join(plan["blockers"]))

    def test_disk_reserve_blocks_oversized_batch(self):
        policy = dict(runtime.DEFAULT_POLICY)
        policy.update({"required_families": ["qwen", "glm", "kimi", "deepseek"]})
        plan = runtime.recommend(self.artifacts, fixture_profile(free=100), policy)
        self.assertFalse(plan["ready"])
        self.assertIn("policy requires", " ".join(plan["blockers"]))

    def test_minimum_memory_fit_requires_explicit_policy(self):
        artifact = next(item for item in self.artifacts if item["id"] == "glm-4.7-flash-q4-k-m")
        profile = fixture_profile(memory=48)
        strict = dict(runtime.DEFAULT_POLICY)
        strict["memory_headroom_gib"] = 16
        self.assertEqual(runtime.artifact_fit(artifact, profile, strict)["fit"], "blocked")
        permissive = dict(strict)
        permissive["allow_minimum_memory_fit"] = True
        self.assertEqual(runtime.artifact_fit(artifact, profile, permissive)["fit"], "constrained")

    def test_base_family_exclusion_prevents_llama_lineage_selection(self):
        policy = dict(runtime.DEFAULT_POLICY)
        policy.update(
            {
                "required_families": ["deepseek"],
                "excluded_base_families": ["llama"],
            }
        )
        plan = runtime.recommend(self.artifacts, fixture_profile(), policy)
        self.assertTrue(plan["ready"])
        self.assertEqual(plan["selections"][0]["artifact_id"], "deepseek-r1-32b-q8-0")

    def test_explicit_selection_cannot_bypass_base_family_policy(self):
        policy = dict(runtime.DEFAULT_POLICY)
        policy["excluded_base_families"] = ["llama"]
        plan = runtime.plan_explicit(
            self.artifacts,
            ["deepseek-r1-70b-q4-k-m"],
            fixture_profile(),
            policy,
        )
        self.assertFalse(plan["ready"])
        self.assertIn("base family is excluded by policy", " ".join(plan["blockers"]))

    def test_explicit_selection_rejects_duplicate_artifacts(self):
        with self.assertRaises(runtime.LocalModelError):
            runtime.plan_explicit(
                self.artifacts,
                ["qwen3-8b-q8-0", "qwen3-8b-q8-0"],
                fixture_profile(),
                dict(runtime.DEFAULT_POLICY),
            )


class PrivacyAndStorageTests(unittest.TestCase):
    def test_profile_rejects_uuid_like_value(self):
        with self.assertRaises(runtime.LocalModelError):
            runtime.assert_profile_safe(
                {"cpu": {"brand": "12345678-1234-1234-1234-123456789abc"}}
            )

    def test_store_inside_workspaces_is_rejected(self):
        with self.assertRaises(runtime.LocalModelError):
            runtime.validate_model_store(Path.home() / "workspaces" / "models")

    def test_store_inside_explicit_protected_root_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            protected = Path(directory) / "protected"
            with self.assertRaises(runtime.LocalModelError):
                runtime.validate_model_store(protected / "models", [str(protected)])

    def test_inventory_uses_random_id_and_atomic_json(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            selections = [{"artifact_id": "qwen3-8b-q8-0"}]
            inventory = runtime.update_inventory(state, fixture_profile(), selections)
            self.assertEqual(inventory["schema_version"], 1)
            machine_identifier = (state / "machine-id").read_text().strip()
            self.assertIn(machine_identifier, inventory["machines"])
            mode = os.stat(state / "machine-id").st_mode & 0o777
            self.assertEqual(mode, 0o600)

    def test_install_transitions_merge_selections_but_refresh_replaces(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            first = [{"artifact_id": "qwen3-8b-q8-0"}]
            second = [{"artifact_id": "glm-4.7-flash-q4-k-m"}]
            runtime.update_inventory(
                state,
                fixture_profile(),
                first,
                merge_selections=True,
            )
            merged = runtime.update_inventory(
                state,
                fixture_profile(),
                second,
                merge_selections=True,
            )
            record = next(iter(merged["machines"].values()))
            self.assertEqual(
                record["selections"],
                ["qwen3-8b-q8-0", "glm-4.7-flash-q4-k-m"],
            )
            refreshed = runtime.update_inventory(state, fixture_profile(), second)
            record = next(iter(refreshed["machines"].values()))
            self.assertEqual(record["selections"], ["glm-4.7-flash-q4-k-m"])

    def test_inventory_rejects_symlinked_state_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target"
            target.mkdir()
            linked = root / "linked"
            linked.symlink_to(target, target_is_directory=True)
            with self.assertRaises(runtime.LocalModelError):
                runtime.update_inventory(
                    linked,
                    fixture_profile(),
                    [{"artifact_id": "qwen3-8b-q8-0"}],
                )

    def test_atomic_text_rejects_symlink_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target.txt"
            target.write_text("preserve", encoding="utf-8")
            linked = root / "output.txt"
            linked.symlink_to(target)
            with self.assertRaises(runtime.LocalModelError):
                runtime.atomic_text_write(linked, "replace")
            self.assertEqual(target.read_text(encoding="utf-8"), "preserve")


class RuntimeTests(unittest.TestCase):
    def test_runtime_summary_distinguishes_managed_and_direct_choices(self):
        profile = fixture_profile()
        profile["runtimes"].update(
            {
                "llama_cpp": {"available": False},
                "mlx_lm": {"available": True},
            }
        )
        summary = runtime.runtime_summary(profile)
        self.assertEqual(summary["default_runtime"], "ollama")
        self.assertEqual(summary["managed_choices"], ["ollama", "lm_studio"])
        self.assertEqual(summary["direct_choices"], ["llama_cpp", "mlx_lm"])
        self.assertTrue(runtime.RUNTIME_CAPABILITIES["ollama"]["update"])
        self.assertFalse(runtime.RUNTIME_CAPABILITIES["lm_studio"]["update"])

    def test_lm_studio_recommendation_uses_exact_catalog_targets(self):
        _, artifacts = runtime.load_catalog(runtime.DEFAULT_CATALOG)
        policy = dict(runtime.DEFAULT_POLICY)
        policy.update(
            {
                "required_families": ["qwen", "glm", "kimi", "deepseek"],
                "artifact_overrides": {
                    "qwen": "qwen3.8-27b-q8-0",
                    "glm": "glm-4.7-flash-q8-0",
                    "kimi": "kimi-linear-48b-a3b-q6-k",
                    "deepseek": "deepseek-r1-32b-q8-0",
                },
            }
        )
        plan = runtime.recommend(artifacts, fixture_profile(), policy, "lm_studio")
        self.assertTrue(plan["ready"])
        self.assertEqual(plan["runtime"], "lm_studio")
        self.assertTrue(
            all(
                selection["runtime_model"].startswith("https://huggingface.co/")
                for selection in plan["selections"]
            )
        )

    def test_lm_studio_missing_target_blocks_explicit_plan(self):
        _, artifacts = runtime.load_catalog(runtime.DEFAULT_CATALOG)
        plan = runtime.plan_explicit(
            artifacts,
            ["qwen3-8b-q8-0"],
            fixture_profile(),
            dict(runtime.DEFAULT_POLICY),
            "lm_studio",
        )
        self.assertFalse(plan["ready"])
        self.assertIn("no verified lm_studio", " ".join(plan["blockers"]))

    def test_lm_studio_install_uses_noninteractive_exact_target_and_inventory(self):
        _, artifacts = runtime.load_catalog(runtime.DEFAULT_CATALOG)
        artifact_id = "qwen3.8-27b-q8-0"
        plan = runtime.plan_explicit(
            artifacts,
            [artifact_id],
            fixture_profile(),
            dict(runtime.DEFAULT_POLICY),
            "lm_studio",
        )
        calls = []

        def runner(arguments, **kwargs):
            calls.append((arguments, kwargs))
            if arguments[1] == "get":
                return runtime.subprocess.CompletedProcess(arguments, 0, "", "")
            payload = [
                {
                    "modelKey": "bartowski/Qwen3.8-27B-GGUF/Qwen3.8-27B-Q8_0.gguf",
                    "sizeBytes": 29116388960,
                    "architecture": "qwen",
                    "paramsString": "27B",
                    "quantization": "Q8_0",
                }
            ]
            return runtime.subprocess.CompletedProcess(
                arguments, 0, json.dumps(payload), ""
            )

        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            runtime.shutil, "which", return_value="/usr/local/bin/lms"
        ):
            result = runtime.perform_install(
                plan,
                artifacts,
                fixture_profile(),
                Path(directory),
                None,
                runner=runner,
            )
            self.assertTrue((Path(directory) / "machines.json").exists())
        get_call, get_kwargs = calls[0]
        self.assertEqual(get_call[1], "get")
        self.assertIn("@Q8_0", get_call[2])
        self.assertEqual(get_call[-2:], ["--yes", "--gguf"])
        self.assertFalse(get_kwargs["shell"])
        installed = result["installed"][artifact_id]
        self.assertEqual(installed["runtime"], "lm_studio")
        self.assertEqual(installed["identity_strength"], "runtime-metadata")

    def test_lm_studio_failed_download_does_not_write_inventory(self):
        _, artifacts = runtime.load_catalog(runtime.DEFAULT_CATALOG)
        plan = runtime.plan_explicit(
            artifacts,
            ["qwen3.8-27b-q8-0"],
            fixture_profile(),
            dict(runtime.DEFAULT_POLICY),
            "lm_studio",
        )

        def runner(arguments, **_kwargs):
            return runtime.subprocess.CompletedProcess(arguments, 7, "", "failed")

        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            runtime.shutil, "which", return_value="/usr/local/bin/lms"
        ):
            with self.assertRaises(runtime.LocalModelError):
                runtime.perform_install(
                    plan,
                    artifacts,
                    fixture_profile(),
                    Path(directory),
                    None,
                    runner=runner,
                )
            self.assertFalse((Path(directory) / "machines.json").exists())

    def test_lm_studio_update_is_explicitly_blocked(self):
        with self.assertRaisesRegex(runtime.LocalModelError, "content-identity"):
            runtime.plan_model_updates("lm_studio", ["model"], False, [])

    def test_update_plan_rejects_uninstalled_model_and_supports_all(self):
        tags = [
            {"name": "gemma4:e4b", "digest": "a", "size": 10},
            {"name": "gemma4:26b", "digest": "b", "size": 20},
        ]
        with self.assertRaisesRegex(runtime.LocalModelError, "not installed"):
            runtime.plan_model_updates("ollama", ["gemma4:31b"], False, tags)
        plan = runtime.plan_model_updates("ollama", [], True, tags)
        self.assertEqual(plan["scope"], "all-installed")
        self.assertEqual(len(plan["models"]), 2)

    def test_ollama_update_records_changed_and_already_current(self):
        before_tags = [
            {"name": "gemma4:e4b", "digest": "old", "size": 10},
            {"name": "gemma4:26b", "digest": "same", "size": 20},
        ]
        plan = runtime.plan_model_updates(
            "ollama", ["gemma4:e4b", "gemma4:26b"], False, before_tags
        )
        after = iter(
            [
                [{"name": "gemma4:e4b", "digest": "new", "size": 11}],
                [{"name": "gemma4:26b", "digest": "same", "size": 20}],
            ]
        )

        def runner(arguments, **_kwargs):
            return runtime.subprocess.CompletedProcess(arguments, 0, "", "")

        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            runtime.shutil, "which", return_value="/usr/local/bin/ollama"
        ):
            result = runtime.perform_ollama_updates(
                plan,
                Path(directory) / "state",
                Path(directory) / "receipts",
                runner=runner,
                tags_provider=lambda: next(after),
            )
            self.assertTrue(Path(result["receipt_path"]).exists())
        self.assertTrue(result["success"])
        self.assertEqual(
            [item["status"] for item in result["models"]],
            ["updated", "already-current"],
        )

    def test_ollama_update_failure_returns_failed_receipt(self):
        tags = [{"name": "gemma4:e4b", "digest": "old", "size": 10}]
        plan = runtime.plan_model_updates("ollama", ["gemma4:e4b"], False, tags)

        def runner(arguments, **_kwargs):
            return runtime.subprocess.CompletedProcess(arguments, 9, "", "failed")

        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            runtime.shutil, "which", return_value="/usr/local/bin/ollama"
        ):
            result = runtime.perform_ollama_updates(
                plan, Path(directory), runner=runner
            )
        self.assertFalse(result["success"])
        self.assertEqual(result["models"][0]["status"], "failed")

    def test_ollama_update_refreshes_matching_inventory_record(self):
        _, artifacts = runtime.load_catalog(runtime.DEFAULT_CATALOG)
        artifact_id = "qwen3-8b-q8-0"
        before = {
            "name": "qwen3:8b-q8_0",
            "digest": "old-digest",
            "size": 100,
        }
        after = {
            "name": "qwen3:8b-q8_0",
            "digest": "new-digest",
            "size": 101,
        }
        plan = runtime.plan_model_updates(
            "ollama", ["qwen3:8b-q8_0"], False, [before]
        )

        def runner(arguments, **_kwargs):
            return runtime.subprocess.CompletedProcess(arguments, 0, "", "")

        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            runtime.shutil, "which", return_value="/usr/local/bin/ollama"
        ):
            state = Path(directory)
            runtime.update_inventory(
                state,
                fixture_profile(),
                [{"artifact_id": artifact_id}],
                installed={
                    artifact_id: {
                        "runtime": "ollama",
                        "runtime_name": "qwen3:8b-q8_0",
                        "digest": "old-digest",
                        "size_bytes": 100,
                    }
                },
            )
            result = runtime.perform_ollama_updates(
                plan,
                state,
                runner=runner,
                tags_provider=lambda: [after],
            )
            resolved = runtime.resolve_inventory_model(
                state, artifacts, artifact_id=artifact_id
            )
            inventory = runtime.load_json(state / "machines.json")
            machine = next(iter(inventory["machines"].values()))
        self.assertTrue(result["inventory_refreshed"])
        self.assertEqual(resolved["digest"], "new-digest")
        self.assertEqual(
            machine["installed"][artifact_id]["last_update"]["status"], "updated"
        )

    def test_resolve_accepts_labeled_lm_studio_metadata_identity(self):
        _, artifacts = runtime.load_catalog(runtime.DEFAULT_CATALOG)
        artifact_id = "qwen3.8-27b-q8-0"
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            runtime.update_inventory(
                state,
                fixture_profile(),
                [{"artifact_id": artifact_id}],
                installed={
                    artifact_id: {
                        "runtime": "lm_studio",
                        "runtime_name": "bartowski/Qwen3.8-27B-GGUF/Q8_0.gguf",
                        "identity": "metadata-identity",
                        "identity_strength": "runtime-metadata",
                    }
                },
            )
            result = runtime.resolve_inventory_model(
                state, artifacts, artifact_id=artifact_id
            )
        self.assertIsNone(result["digest"])
        self.assertEqual(result["identity"], "metadata-identity")
        self.assertEqual(result["identity_strength"], "runtime-metadata")

    def test_find_installed_normalizes_latest_only(self):
        tags = [{"name": "qwen3:8b", "digest": "abc"}]
        self.assertIsNotNone(runtime.find_installed("qwen3:8b", tags))
        self.assertIsNone(runtime.find_installed("qwen3:14b", tags))

    def test_failed_pull_does_not_write_inventory(self):
        _, artifacts = runtime.load_catalog(runtime.DEFAULT_CATALOG)
        artifact_id = "qwen3-8b-q8-0"
        plan = runtime.plan_explicit(
            artifacts,
            [artifact_id],
            fixture_profile(),
            dict(runtime.DEFAULT_POLICY),
        )

        class Result:
            returncode = 9

        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            runtime.shutil, "which", return_value="/usr/local/bin/ollama"
        ):
            with self.assertRaises(runtime.LocalModelError):
                runtime.perform_install(
                    plan,
                    artifacts,
                    fixture_profile(),
                    Path(directory),
                    None,
                    runner=lambda *args, **kwargs: Result(),
                )
            self.assertFalse((Path(directory) / "machines.json").exists())

    def test_failed_registry_pull_uses_pinned_cached_gguf_import(self):
        _, artifacts = runtime.load_catalog(runtime.DEFAULT_CATALOG)
        artifact = dict(
            next(item for item in artifacts if item["id"] == "qwen3.8-27b-q8-0")
        )
        model_bytes = b"GGUF-model-fixture"
        projector_bytes = b"GGUF-projector-fixture"
        model_digest = runtime.hashlib.sha256(model_bytes).hexdigest()
        projector_digest = runtime.hashlib.sha256(projector_bytes).hexdigest()
        artifact["local_import_fallback"] = {
            "registry_manifest_url": "https://example.test/manifest",
            "gguf_layers": [
                {
                    "digest": f"sha256:{model_digest}",
                    "media_type": "application/vnd.ollama.image.model",
                    "size_bytes": len(model_bytes),
                },
                {
                    "digest": f"sha256:{projector_digest}",
                    "media_type": "application/vnd.ollama.image.projector",
                    "size_bytes": len(projector_bytes),
                },
            ],
        }
        plan = {
            "ready": True,
            "blockers": [],
            "selections": [{"artifact_id": artifact["id"]}],
        }

        class Result:
            def __init__(self, returncode):
                self.returncode = returncode

        calls = []

        def runner(arguments, **_kwargs):
            calls.append(arguments)
            if arguments[1] == "pull":
                return Result(1)
            self.assertEqual(arguments[1], "create")
            modelfile = Path(arguments[-1])
            imported = sorted(modelfile.parent.glob("*.gguf"))
            self.assertEqual([path.read_bytes() for path in imported], [model_bytes, projector_bytes])
            self.assertIn(f"FROM {modelfile.parent}", modelfile.read_text(encoding="utf-8"))
            return Result(0)

        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            runtime.shutil, "which", return_value="/usr/local/bin/ollama"
        ), mock.patch.object(
            runtime,
            "ollama_tags",
            return_value=[
                {
                    "name": artifact["runtime_model"],
                    "digest": "resolved-local-import-digest",
                    "size": len(model_bytes) + len(projector_bytes),
                    "details": {"format": "gguf", "quantization_level": "Q8_0"},
                }
            ],
        ):
            root = Path(directory)
            store = root / "models"
            blobs = store / "blobs"
            blobs.mkdir(parents=True)
            (blobs / f"sha256-{model_digest}").write_bytes(model_bytes)
            (blobs / f"sha256-{projector_digest}").write_bytes(projector_bytes)
            profile = fixture_profile()
            profile["storage"]["model_store"] = str(store)
            result = runtime.perform_install(
                plan,
                [artifact],
                profile,
                root / "state",
                None,
                runner=runner,
            )
            installed = result["installed"][artifact["id"]]
            self.assertEqual(
                installed["installation_method"], "catalog-pinned-local-import"
            )
            self.assertEqual([call[1] for call in calls], ["pull", "create"])

    def test_explicit_cached_recovery_skips_registry_pull(self):
        _, artifacts = runtime.load_catalog(runtime.DEFAULT_CATALOG)
        artifact = dict(
            next(item for item in artifacts if item["id"] == "qwen3.8-27b-q8-0")
        )
        model_bytes = b"GGUF-cached-recovery-fixture"
        digest = runtime.hashlib.sha256(model_bytes).hexdigest()
        artifact["local_import_fallback"] = {
            "registry_manifest_url": "https://example.test/manifest",
            "gguf_layers": [
                {
                    "digest": f"sha256:{digest}",
                    "media_type": "application/vnd.ollama.image.model",
                    "size_bytes": len(model_bytes),
                }
            ],
        }
        plan = {
            "ready": True,
            "blockers": [],
            "selections": [{"artifact_id": artifact["id"]}],
        }

        class Result:
            returncode = 0

        calls = []

        def runner(arguments, **_kwargs):
            calls.append(arguments)
            self.assertEqual(arguments[1], "create")
            return Result()

        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            runtime.shutil, "which", return_value="/usr/local/bin/ollama"
        ), mock.patch.object(
            runtime,
            "ollama_tags",
            return_value=[
                {
                    "name": artifact["runtime_model"],
                    "digest": "resolved-cached-recovery-digest",
                    "size": len(model_bytes),
                    "details": {"format": "gguf", "quantization_level": "Q8_0"},
                }
            ],
        ):
            root = Path(directory)
            store = root / "models"
            blobs = store / "blobs"
            blobs.mkdir(parents=True)
            (blobs / f"sha256-{digest}").write_bytes(model_bytes)
            profile = fixture_profile()
            profile["storage"]["model_store"] = str(store)
            result = runtime.perform_install(
                plan,
                [artifact],
                profile,
                root / "state",
                None,
                recover_cached=True,
                runner=runner,
            )
            installed = result["installed"][artifact["id"]]
            self.assertEqual(
                installed["installation_method"], "catalog-pinned-local-import"
            )
            self.assertEqual([call[1] for call in calls], ["create"])

    def test_cached_recovery_receipt_separates_network_and_runtime_disk(self):
        _, artifacts = runtime.load_catalog(runtime.DEFAULT_CATALOG)
        artifact = next(
            item for item in artifacts if item["id"] == "qwen3.8-27b-q8-0"
        )
        plan = {
            "selections": [{"artifact_id": artifact["id"]}],
        }
        receipt = runtime.cached_recovery_receipt(plan, artifacts)
        expected = round(
            sum(
                layer["size_bytes"]
                for layer in artifact["local_import_fallback"]["gguf_layers"]
            )
            / runtime.GIB,
            2,
        )
        self.assertEqual(receipt["network_download_gib"], 0.0)
        self.assertEqual(receipt["possible_additional_runtime_gib"], expected)
        self.assertIn("retain", receipt["cache_retention"])

    def test_cached_gguf_import_rejects_digest_mismatch(self):
        _, artifacts = runtime.load_catalog(runtime.DEFAULT_CATALOG)
        artifact = dict(
            next(item for item in artifacts if item["id"] == "qwen3.8-27b-q8-0")
        )
        expected = runtime.hashlib.sha256(b"expected").hexdigest()
        artifact["local_import_fallback"] = {
            "registry_manifest_url": "https://example.test/manifest",
            "gguf_layers": [
                {
                    "digest": f"sha256:{expected}",
                    "media_type": "application/vnd.ollama.image.model",
                    "size_bytes": len(b"tampered"),
                }
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = root / "models"
            blobs = store / "blobs"
            blobs.mkdir(parents=True)
            (blobs / f"sha256-{expected}").write_bytes(b"tampered")
            profile = fixture_profile()
            profile["storage"]["model_store"] = str(store)
            with self.assertRaises(runtime.LocalModelError):
                runtime.import_cached_gguf_layers(
                    artifact,
                    profile,
                    "/usr/local/bin/ollama",
                    runner=mock.Mock(),
                )

    def test_benchmark_bounds_fail_before_network(self):
        _, artifacts = runtime.load_catalog(runtime.DEFAULT_CATALOG)
        with self.assertRaises(runtime.LocalModelError):
            runtime.benchmark_artifact(artifacts[0], None, "test", 0, 8192)

    def test_benchmark_disables_thinking_by_default_and_records_it(self):
        _, artifacts = runtime.load_catalog(runtime.DEFAULT_CATALOG)
        response = {
            "response": "bounded final response",
            "done_reason": "stop",
            "eval_count": 3,
            "eval_duration": 1_000_000_000,
        }
        with mock.patch.object(runtime, "api_json", return_value=response) as api:
            receipt = runtime.benchmark_artifact(
                artifacts[0], None, "test prompt", 16, 8192
            )
        request = api.call_args.args[1]
        self.assertIs(request["think"], False)
        self.assertIs(receipt["think"], False)
        self.assertTrue(receipt["accepted"])
        self.assertTrue(receipt["reasoning_suppression_honored"])

    def test_benchmark_rejects_unsuppressed_reasoning_markup(self):
        _, artifacts = runtime.load_catalog(runtime.DEFAULT_CATALOG)
        response = {
            "response": "<think>private trace</think>final response",
            "done_reason": "stop",
            "eval_count": 8,
            "eval_duration": 1_000_000_000,
        }
        with mock.patch.object(runtime, "api_json", return_value=response):
            receipt = runtime.benchmark_artifact(
                artifacts[0], None, "test prompt", 16, 8192
            )
        self.assertTrue(receipt["final_response_complete"])
        self.assertFalse(receipt["reasoning_suppression_honored"])
        self.assertFalse(receipt["accepted"])

    def test_benchmark_rejects_length_stop_without_final_response(self):
        _, artifacts = runtime.load_catalog(runtime.DEFAULT_CATALOG)
        response = {
            "response": "<think>unfinished private trace",
            "done_reason": "length",
            "eval_count": 16,
            "eval_duration": 1_000_000_000,
        }
        with mock.patch.object(runtime, "api_json", return_value=response):
            receipt = runtime.benchmark_artifact(
                artifacts[0], None, "test prompt", 16, 8192, think=True
            )
        self.assertFalse(receipt["final_response_complete"])
        self.assertFalse(receipt["accepted"])

    def test_api_http_error_preserves_bounded_runtime_detail(self):
        error = runtime.urllib.error.HTTPError(
            "http://127.0.0.1:11434/api/generate",
            500,
            "Internal Server Error",
            {},
            io.BytesIO(b'{"error":"KV cache mismatch"}'),
        )
        with mock.patch.object(runtime.urllib.request, "urlopen", side_effect=error):
            with self.assertRaisesRegex(runtime.LocalModelError, "KV cache mismatch"):
                runtime.api_json("/api/generate", {"model": "test"})

    def test_homebrew_ollama_configuration_dry_run_does_not_write(self):
        payload = {
            "Label": runtime.HOMEBREW_OLLAMA_LABEL,
            "ProgramArguments": ["/opt/homebrew/bin/ollama", "serve"],
            "EnvironmentVariables": {"OLLAMA_KV_CACHE_TYPE": "q8_0"},
        }
        with tempfile.TemporaryDirectory() as directory:
            plist = Path(directory) / "homebrew.mxcl.ollama.plist"
            original = runtime.plistlib.dumps(payload)
            plist.write_bytes(original)
            with mock.patch.object(runtime.platform, "system", return_value="Darwin"), mock.patch.object(
                runtime, "macos_homebrew_ollama_service", return_value=(plist, payload)
            ):
                result = runtime.configure_homebrew_ollama(
                    "f16", False, Path(directory) / "state"
                )
            self.assertTrue(result["authorization_required"])
            self.assertEqual(plist.read_bytes(), original)

    def test_homebrew_ollama_configuration_applies_and_backs_up(self):
        payload = {
            "Label": runtime.HOMEBREW_OLLAMA_LABEL,
            "ProgramArguments": ["/opt/homebrew/bin/ollama", "serve"],
            "EnvironmentVariables": {
                "OLLAMA_FLASH_ATTENTION": "1",
                "OLLAMA_KV_CACHE_TYPE": "q8_0",
            },
        }
        calls = []

        def runner(arguments, **_kwargs):
            calls.append(arguments)
            return runtime.subprocess.CompletedProcess(arguments, 0, "", "")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plist = root / "homebrew.mxcl.ollama.plist"
            original = runtime.plistlib.dumps(payload)
            plist.write_bytes(original)
            with mock.patch.object(runtime.platform, "system", return_value="Darwin"), mock.patch.object(
                runtime, "macos_homebrew_ollama_service", return_value=(plist, payload)
            ):
                result = runtime.configure_homebrew_ollama(
                    "f16", True, root / "state", runner=runner, waiter=lambda: True
                )
            updated = runtime.plistlib.loads(plist.read_bytes())
            self.assertEqual(
                updated["EnvironmentVariables"]["OLLAMA_KV_CACHE_TYPE"], "f16"
            )
            backups = list((root / "state" / "backups").glob("*.plist"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_bytes(), original)
            self.assertTrue(result["runtime_healthy"])
            self.assertEqual([call[1] for call in calls], ["bootout", "bootstrap"])

    def test_homebrew_ollama_configuration_rolls_back_failed_reload(self):
        payload = {
            "Label": runtime.HOMEBREW_OLLAMA_LABEL,
            "ProgramArguments": ["/opt/homebrew/bin/ollama", "serve"],
            "EnvironmentVariables": {"OLLAMA_KV_CACHE_TYPE": "q8_0"},
        }
        calls = []

        def runner(arguments, **_kwargs):
            calls.append(arguments)
            returncode = 1 if len(calls) == 2 else 0
            return runtime.subprocess.CompletedProcess(
                arguments, returncode, "", "reload failed" if returncode else ""
            )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plist = root / "homebrew.mxcl.ollama.plist"
            original = runtime.plistlib.dumps(payload)
            plist.write_bytes(original)
            with mock.patch.object(runtime.platform, "system", return_value="Darwin"), mock.patch.object(
                runtime, "macos_homebrew_ollama_service", return_value=(plist, payload)
            ):
                with self.assertRaisesRegex(runtime.LocalModelError, "restored"):
                    runtime.configure_homebrew_ollama(
                        "f16", True, root / "state", runner=runner, waiter=lambda: True
                    )
            self.assertEqual(plist.read_bytes(), original)
            self.assertEqual(
                [call[1] for call in calls],
                ["bootout", "bootstrap", "bootout", "bootstrap"],
            )

    def test_resolve_enforces_current_machine_selection_and_installation(self):
        _, artifacts = runtime.load_catalog(runtime.DEFAULT_CATALOG)
        artifact_id = "qwen3-8b-q8-0"
        selections = [{"artifact_id": artifact_id}]
        installed = {
            artifact_id: {
                "runtime": "ollama",
                "runtime_name": "qwen3:8b-q8_0",
                "digest": "d87f4a5a2f1a0000",
                "verified_at": "2026-08-23T00:00:00+00:00",
            }
        }
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            runtime.update_inventory(
                state, fixture_profile(), selections, installed=installed
            )
            result = runtime.resolve_inventory_model(state, artifacts, family="qwen")
            self.assertEqual(result["catalog_id"], artifact_id)
            self.assertEqual(result["runtime_name"], "qwen3:8b-q8_0")

    def test_resolve_rejects_selected_but_uninstalled_artifact(self):
        _, artifacts = runtime.load_catalog(runtime.DEFAULT_CATALOG)
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            runtime.update_inventory(
                state, fixture_profile(), [{"artifact_id": "qwen3-8b-q8-0"}]
            )
            with self.assertRaises(runtime.LocalModelError):
                runtime.resolve_inventory_model(state, artifacts, family="qwen")


if __name__ == "__main__":
    unittest.main()

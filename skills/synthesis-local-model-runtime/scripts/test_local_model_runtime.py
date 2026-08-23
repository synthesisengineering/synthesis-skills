import importlib.util
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
            "ollama": {"available": True, "version": version, "api_reachable": True}
        },
    }


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.catalog, self.artifacts = runtime.load_catalog(runtime.DEFAULT_CATALOG)

    def test_bundled_catalog_is_valid_and_multi_tier(self):
        families = {artifact["family"] for artifact in self.artifacts}
        self.assertEqual(families, {"qwen", "glm", "kimi", "deepseek"})
        self.assertGreaterEqual(len(self.artifacts), 10)

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

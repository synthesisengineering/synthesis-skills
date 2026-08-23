#!/usr/bin/env python3
"""Deterministic tests for synthesis-text-provenance scripts."""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock


SCRIPT_DIR = Path(__file__).resolve().parent
FIXTURE_DIR = SCRIPT_DIR.parent / "tests" / "fixtures"
sys.path.insert(0, str(SCRIPT_DIR))

import local_generate as lg  # noqa: E402
import ollama_metadata as om  # noqa: E402
import provenance_manifest as pm  # noqa: E402
import text_integrity_audit as tia  # noqa: E402


def event_files(root: Path, prefix: str) -> tuple[Path, Path]:
    prompt = root / f"{prefix}-prompt.txt"
    output = root / f"{prefix}-output.txt"
    prompt.write_text(f"Prompt for {prefix}.\n", encoding="utf-8")
    output.write_text(f"Output for {prefix}.\n", encoding="utf-8")
    return prompt, output


def event_manifest(
    root: Path,
    prefix: str,
    *,
    parents: list[dict[str, str]] | None = None,
    runtime_receipt: Path | None = None,
) -> tuple[dict, Path, Path, Path]:
    prompt, output = event_files(root, prefix)
    if runtime_receipt is None:
        runtime_receipt = root / f"{prefix}-runtime-receipt.json"
        runtime_receipt.write_text(
            '{"runtime":"test-runtime","version":"1"}\n',
            encoding="utf-8",
        )
    data = pm.create_manifest(
        generation_mode="local_open_weight",
        provider="local",
        model_requested="test-model",
        model_returned="test-model-q4",
        runtime="test-runtime",
        runtime_receipt_file=runtime_receipt,
        endpoint_class="local_loopback",
        prompt_file=prompt,
        output_file=output,
        parameters={"seed": 7, "temperature": 0},
        parents=parents,
    )
    manifest = root / f"{prefix}-provenance.json"
    pm.atomic_write_json(manifest, data)
    return data, manifest, prompt, output


class ManifestTests(unittest.TestCase):
    def test_canonical_fixture_hash_is_stable(self) -> None:
        fixture = FIXTURE_DIR / "canonical-manifest-v2.json"
        data = json.loads(fixture.read_text(encoding="utf-8"))
        self.assertEqual(
            "86a6f0bba3c60c730e82856075c09b0e4d50983b60f1dbe894a4dcf634721a31",
            pm.manifest_sha256(data),
        )
        self.assertEqual([], pm.validate_manifest_data(data))
        self.assertEqual(data, pm.load_manifest(fixture))
        reordered = dict(reversed(list(data.items())))
        self.assertEqual(data["manifest_sha256"], pm.manifest_sha256(reordered))

    def test_create_validate_and_verify(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data, manifest, _prompt, output = event_manifest(root, "basic")
            self.assertEqual([], pm.validate_manifest_data(data))
            self.assertEqual(data["manifest_sha256"], pm.manifest_sha256(data))
            loaded = pm.load_manifest(manifest)
            self.assertEqual([], pm.verify_manifest_files(manifest, loaded))
            output.write_text("changed\n", encoding="utf-8")
            errors = pm.verify_manifest_files(manifest, loaded)
            self.assertTrue(any("output SHA-256 mismatch" in error for error in errors))

    def test_manifest_self_hash_detects_content_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            data, _manifest, _prompt, _output = event_manifest(Path(temporary), "tamper")
            data["notes"].append("Changed after sealing.")
            errors = pm.validate_manifest_data(data)
            self.assertIn(
                "manifest_sha256 does not match canonical manifest content",
                errors,
            )
            resealed = pm.seal_manifest(data)
            self.assertEqual([], pm.validate_manifest_data(resealed))

    def test_loader_rejects_duplicate_keys_and_nonstandard_numbers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            duplicate = root / "duplicate.json"
            duplicate.write_text('{"schema_version": 2, "schema_version": 2}', encoding="utf-8")
            with self.assertRaisesRegex(pm.ManifestError, "duplicate JSON object key"):
                pm.load_manifest(duplicate)
            nonstandard = root / "nan.json"
            nonstandard.write_text('{"schema_version": NaN}', encoding="utf-8")
            with self.assertRaisesRegex(pm.ManifestError, "non-standard JSON constant"):
                pm.load_manifest(nonstandard)

    def test_runtime_receipt_is_hash_bound_and_verified(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            receipt = root / "runtime-receipt.json"
            receipt.write_text('{"runtime":"test","version":"1"}\n', encoding="utf-8")
            data, manifest, _prompt, _output = event_manifest(
                root,
                "receipt",
                runtime_receipt=receipt,
            )
            self.assertEqual(pm.sha256_file(receipt), data["runtime_receipt"]["sha256"])
            self.assertEqual([], pm.verify_manifest_files(manifest, data))
            receipt.write_text('{"runtime":"test","version":"2"}\n', encoding="utf-8")
            errors = pm.verify_manifest_files(manifest, data)
            self.assertTrue(any("runtime_receipt SHA-256 mismatch" in error for error in errors))

    def test_schema_requires_receipt_for_local_open_weight_generation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            data, _manifest, _prompt, _output = event_manifest(Path(temporary), "required")
            data["runtime_receipt"] = None
            data = pm.seal_manifest(data)
            self.assertIn(
                "runtime_receipt is required for local_open_weight generation",
                pm.validate_manifest_data(data),
            )

    def test_parent_lineage_uses_path_free_hash_links_and_explicit_manifests(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            parent, parent_path, _prompt, _output = event_manifest(root, "parent")
            parent["output"]["path"] = "/not/opened/by-lineage-verification/output.txt"
            parent = pm.seal_manifest(parent)
            pm.atomic_write_json(parent_path, parent)
            link = pm.parent_record(parent)
            self.assertEqual(pm.PARENT_RECORD_FIELDS, set(link))
            self.assertNotIn("path", link)
            child, _child_path, _child_prompt, _child_output = event_manifest(
                root,
                "child",
                parents=[link],
            )
            self.assertEqual([], pm.verify_parent_lineage(child, [parent_path]))
            missing = pm.verify_parent_lineage(child, [])
            self.assertTrue(any("not explicitly supplied" in error for error in missing))
            duplicate = pm.verify_parent_lineage(child, [parent_path, parent_path])
            self.assertTrue(any("duplicate explicitly supplied" in error for error in duplicate))

    def test_parent_output_and_manifest_hash_mismatches_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            parent, _parent_path, _prompt, _output = event_manifest(root, "parent")
            child, _child_path, _child_prompt, _child_output = event_manifest(
                root,
                "child",
                parents=[pm.parent_record(parent)],
            )
            changed_parent = copy.deepcopy(parent)
            changed_parent["output"]["sha256"] = "f" * 64
            changed_parent = pm.seal_manifest(changed_parent)
            changed_path = root / "changed-parent.json"
            pm.atomic_write_json(changed_path, changed_parent)
            errors = pm.verify_parent_lineage(child, [changed_path])
            self.assertTrue(any("parent manifest SHA-256 mismatch" in error for error in errors))
            self.assertTrue(any("parent output SHA-256 mismatch" in error for error in errors))

    def test_parent_schema_rejects_paths_and_self_parenting(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            data, _manifest, _prompt, _output = event_manifest(Path(temporary), "self")
            data["parents"] = [{
                "record_id": data["record_id"],
                "manifest_sha256": "a" * 64,
                "output_sha256": "b" * 64,
                "path": "parent.json",
            }]
            data = pm.seal_manifest(data)
            errors = pm.validate_manifest_data(data)
            self.assertTrue(any("must contain exactly" in error for error in errors))
            self.assertTrue(any("must not equal record_id" in error for error in errors))

    def test_cli_create_and_verify_requires_explicit_parent_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _parent, parent_path, _prompt, _output = event_manifest(root, "parent")
            prompt, output = event_files(root, "child-cli")
            receipt = root / "child-cli-runtime-receipt.json"
            receipt.write_text('{"runtime":"test-runtime","version":"1"}\n', encoding="utf-8")
            child_path = root / "child-cli-provenance.json"
            create_code = pm.main([
                "create",
                "--generation-mode", "local_open_weight",
                "--provider", "local",
                "--model", "test-model",
                "--runtime", "test-runtime",
                "--runtime-receipt", str(receipt),
                "--endpoint-class", "local_loopback",
                "--prompt-file", str(prompt),
                "--output-file", str(output),
                "--parent-manifest", str(parent_path),
                "--manifest", str(child_path),
            ])
            self.assertEqual(0, create_code)
            self.assertEqual(
                0,
                pm.main(["verify", str(child_path), "--parent-manifest", str(parent_path)]),
            )
            self.assertEqual(2, pm.main(["verify", str(child_path)]))

    def test_cli_create_refuses_to_overwrite_an_evidence_input(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prompt, output = event_files(root, "collision")
            original_prompt = prompt.read_bytes()
            code = pm.main([
                "create",
                "--generation-mode", "human",
                "--endpoint-class", "none",
                "--prompt-file", str(prompt),
                "--output-file", str(output),
                "--manifest", str(prompt),
            ])
            self.assertEqual(2, code)
            self.assertEqual(original_prompt, prompt.read_bytes())

    def test_validator_rejects_detector_optimization(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            data, _manifest, _prompt, _output = event_manifest(Path(temporary), "audit")
            data["audits"] = [{
                "tool": "detector",
                "version": "1",
                "kind": "provider_detector",
                "result": "negative",
                "limitations": "not proof of absence",
                "optimization_used": True,
            }]
            data = pm.seal_manifest(data)
            errors = pm.validate_manifest_data(data)
            self.assertTrue(any("optimization_used must be false" in error for error in errors))


class IntegrityTests(unittest.TestCase):
    def test_reports_format_and_bidi_controls_without_mutation(self) -> None:
        text = "alpha\u200bbeta\u202egamma\n"
        raw = text.encode("utf-8")
        report = tia.analyze_text(text, raw)
        self.assertEqual(raw, text.encode("utf-8"))
        self.assertEqual(2, len(report["findings"]))
        self.assertEqual({"bidi-control": 1, "format-control": 1}, report["finding_counts"])
        self.assertIn("does not detect", report["interpretation"])

    def test_normal_text_has_no_findings(self) -> None:
        text = "A normal line.\nAnother line.\n"
        report = tia.analyze_text(text, text.encode("utf-8"))
        self.assertEqual([], report["findings"])

    def test_reports_non_ascii_space_variation_selector_and_noncharacter(self) -> None:
        text = "alpha\u00a0beta\ufe0fgamma\ufdd0"
        report = tia.analyze_text(text, text.encode("utf-8"))
        self.assertEqual(
            {"non-ascii-space": 1, "unicode-noncharacter": 1, "variation-selector": 1},
            report["finding_counts"],
        )

    def test_file_audit_asserts_two_complete_read_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source.txt"
            source.write_text("unchanged\n", encoding="utf-8")
            before = source.stat()
            _text, raw, state = tia.read_input(str(source))
            after = source.stat()
            self.assertIsNotNone(state)
            self.assertTrue(state["full_read_hashes_match"])
            self.assertEqual(state["sha256_first_read"], state["sha256_second_read"])
            self.assertEqual(tia.hashlib.sha256(raw).hexdigest(), state["sha256_first_read"])
            self.assertTrue(state["unchanged_during_audit"])
            self.assertEqual(before.st_size, after.st_size)
            self.assertEqual(before.st_mtime_ns, after.st_mtime_ns)

    def test_file_audit_rejects_change_between_full_reads(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source.txt"
            source.write_text("first", encoding="utf-8")
            with mock.patch.object(Path, "read_bytes", side_effect=[b"first", b"second"]):
                with self.assertRaisesRegex(ValueError, "changed between two complete reads"):
                    tia.read_input(str(source))


class _Handler(BaseHTTPRequestHandler):
    response_payload = {
        "model": "returned-test-model",
        "system_fingerprint": "test-fingerprint",
        "usage": {"prompt_tokens": 4, "completion_tokens": 6, "total_tokens": 10},
        "choices": [{
            "finish_reason": "stop",
            "message": {"content": "A recorded local response.\n"},
        }],
    }
    received: dict | None = None

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/api/version":
            payload = {"version": "test-0.1"}
        elif self.path == "/api/tags":
            payload = {"models": [{
                "name": "test-model:latest",
                "model": "test-model:latest",
                "digest": "a" * 64,
                "size": 1234,
                "modified_at": "2026-08-22T00:00:00Z",
                "details": {"format": "gguf", "quantization_level": "Q4_K_M"},
            }]}
        else:
            self.send_error(404)
            return
        self._send_json(payload)

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers["Content-Length"])
        type(self).received = json.loads(self.rfile.read(length))
        if self.path == "/api/show":
            payload = {
                "license": "Apache License\nVersion 2.0\n",
                "template": "{{ .Prompt }}",
                "parameters": "temperature 1",
                "capabilities": ["completion"],
                "requires": "0.1.0",
                "details": {"format": "gguf", "quantization_level": "Q4_K_M"},
                "model_info": {
                    "general.architecture": "test",
                    "test.context_length": 4096,
                    "tensor.secret": "excluded",
                },
            }
        else:
            payload = type(self).response_payload
        self._send_json(payload)

    def _send_json(self, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


class LocalRunnerTests(unittest.TestCase):
    def test_rejects_empty_final_content(self) -> None:
        with self.assertRaisesRegex(ValueError, "must contain final text"):
            lg.extract_content(
                {
                    "model": "thinking-model",
                    "choices": [
                        {
                            "finish_reason": "length",
                            "message": {"content": "  \n"},
                        }
                    ],
                }
            )

    def test_rejects_non_loopback_by_default(self) -> None:
        with self.assertRaises(ValueError):
            lg.endpoint_class("https://example.com/v1/chat/completions", False)

    def test_rejects_endpoint_secrets_and_query_material(self) -> None:
        for endpoint in (
            "http://user:secret@127.0.0.1:11434/v1/chat/completions",
            "http://127.0.0.1:11434/v1/chat/completions?token=secret",
            "http://127.0.0.1:11434/v1/chat/completions#fragment",
        ):
            with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                lg.endpoint_class(endpoint, False)

    def test_recognizes_ipv4_loopback_range(self) -> None:
        self.assertEqual(
            "local_loopback",
            lg.endpoint_class("http://127.1.2.3:11434/v1/chat/completions", False),
        )

    def test_local_generation_requires_native_runtime_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prompt = root / "prompt.txt"
            prompt.write_text("Return one sentence.", encoding="utf-8")
            code = lg.main([
                "--provider", "test",
                "--runtime", "test-runtime",
                "--model", "requested-test-model",
                "--prompt-file", str(prompt),
                "--output-file", str(root / "output.txt"),
                "--manifest", str(root / "manifest.json"),
            ])
            self.assertEqual(2, code)

    def test_rejects_invalid_numeric_controls_before_generation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prompt = root / "prompt.txt"
            receipt = root / "runtime-receipt.json"
            prompt.write_text("Return one sentence.", encoding="utf-8")
            receipt.write_text('{"runtime":"test-runtime","version":"1"}\n', encoding="utf-8")
            common = [
                "--provider", "test",
                "--runtime", "test-runtime",
                "--runtime-receipt", str(receipt),
                "--model", "requested-test-model",
                "--prompt-file", str(prompt),
                "--output-file", str(root / "output.txt"),
                "--manifest", str(root / "manifest.json"),
            ]
            for option, value in (
                ("--temperature", "nan"),
                ("--max-tokens", "0"),
                ("--timeout", "-1"),
            ):
                with self.subTest(option=option, value=value):
                    self.assertEqual(2, lg.main([*common, option, value]))
                    self.assertFalse((root / "output.txt").exists())
                    self.assertFalse((root / "manifest.json").exists())

    def test_live_loopback_contract_binds_receipt_output_and_manifest(self) -> None:
        server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                prompt = root / "prompt.txt"
                receipt = root / "runtime-receipt.json"
                output = root / "output.txt"
                manifest = root / "provenance.json"
                prompt.write_text("Return one sentence.", encoding="utf-8")
                receipt.write_text('{"runtime":"test-runtime","version":"1"}\n', encoding="utf-8")
                code = lg.main([
                    "--endpoint", f"http://127.0.0.1:{server.server_port}/v1/chat/completions",
                    "--provider", "test",
                    "--runtime", "test-runtime",
                    "--runtime-receipt", str(receipt),
                    "--model", "requested-test-model",
                    "--prompt-file", str(prompt),
                    "--output-file", str(output),
                    "--manifest", str(manifest),
                    "--seed", "7",
                    "--reasoning-effort", "none",
                ])
                self.assertEqual(0, code)
                self.assertEqual("A recorded local response.\n", output.read_text(encoding="utf-8"))
                data = pm.load_manifest(manifest)
                self.assertEqual("returned-test-model", data["model_returned"])
                self.assertEqual("local_open_weight", data["generation_mode"])
                self.assertEqual("stop", data["parameters"]["reported_response"]["finish_reason"])
                self.assertEqual(
                    "test-fingerprint",
                    data["parameters"]["reported_response"]["system_fingerprint"],
                )
                self.assertEqual(pm.sha256_file(receipt), data["runtime_receipt"]["sha256"])
                self.assertEqual([], pm.verify_manifest_files(manifest, data))
                self.assertEqual("requested-test-model", _Handler.received["model"])
                self.assertEqual("none", _Handler.received["reasoning_effort"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


class OllamaMetadataTests(unittest.TestCase):
    def test_bounded_receipt_excludes_tensor_inventory(self) -> None:
        server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            receipt = om.build_receipt(
                f"http://127.0.0.1:{server.server_port}",
                "test-model:latest",
            )
            self.assertEqual("test-0.1", receipt["runtime"]["version"])
            self.assertEqual("a" * 64, receipt["model"]["digest"])
            self.assertEqual("Apache License", receipt["model"]["license"]["name"])
            self.assertEqual("Q4_K_M", receipt["model"]["details"]["quantization_level"])
            self.assertNotIn("tensor.secret", receipt["model"]["model_info"])
            self.assertEqual([], receipt["unknowns"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_metadata_rejects_non_loopback(self) -> None:
        with self.assertRaises(ValueError):
            om.build_receipt("https://example.com", "test-model")


if __name__ == "__main__":
    unittest.main()

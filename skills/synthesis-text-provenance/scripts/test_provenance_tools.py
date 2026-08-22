#!/usr/bin/env python3
"""Deterministic tests for synthesis-text-provenance scripts."""

from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import local_generate as lg  # noqa: E402
import ollama_metadata as om  # noqa: E402
import provenance_manifest as pm  # noqa: E402
import text_integrity_audit as tia  # noqa: E402


class ManifestTests(unittest.TestCase):
    def test_create_validate_and_verify(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prompt = root / "prompt.txt"
            output = root / "output.txt"
            prompt.write_text("Explain the decision.\n", encoding="utf-8")
            output.write_text("The decision turns on the irreversible step.\n", encoding="utf-8")
            data = pm.create_manifest(
                generation_mode="local_open_weight",
                provider="local",
                model_requested="test-model",
                model_returned="test-model-q4",
                runtime="test-runtime",
                endpoint_class="local_loopback",
                prompt_file=prompt,
                output_file=output,
                parameters={"temperature": 0},
            )
            self.assertEqual([], pm.validate_manifest_data(data))
            manifest = root / "provenance.json"
            pm.atomic_write_json(manifest, data)
            loaded = pm.load_manifest(manifest)
            self.assertEqual([], pm.verify_manifest_files(manifest, loaded))
            output.write_text("changed\n", encoding="utf-8")
            errors = pm.verify_manifest_files(manifest, loaded)
            self.assertTrue(any("mismatch" in error for error in errors))

    def test_validator_rejects_detector_optimization(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prompt = root / "prompt.txt"
            output = root / "output.txt"
            prompt.write_text("p", encoding="utf-8")
            output.write_text("o", encoding="utf-8")
            data = pm.create_manifest(
                generation_mode="hosted",
                provider="example",
                model_requested="m",
                model_returned=None,
                runtime="api",
                endpoint_class="hosted",
                prompt_file=prompt,
                output_file=output,
            )
            data["audits"] = [{
                "tool": "detector",
                "version": "1",
                "kind": "provider_detector",
                "result": "negative",
                "limitations": "not proof of absence",
                "optimization_used": True,
            }]
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

    def test_file_audit_does_not_change_size_or_mtime(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source.txt"
            source.write_text("unchanged\n", encoding="utf-8")
            before = source.stat()
            _text, _raw, state = tia.read_input(str(source))
            after = source.stat()
            self.assertTrue(state["unchanged_during_audit"])
            self.assertEqual(before.st_size, after.st_size)
            self.assertEqual(before.st_mtime_ns, after.st_mtime_ns)


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

    def test_live_loopback_contract_writes_output_and_manifest(self) -> None:
        server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                prompt = root / "prompt.txt"
                output = root / "output.txt"
                manifest = root / "provenance.json"
                prompt.write_text("Return one sentence.", encoding="utf-8")
                code = lg.main([
                    "--endpoint", f"http://127.0.0.1:{server.server_port}/v1/chat/completions",
                    "--provider", "test",
                    "--runtime", "test-runtime",
                    "--model", "requested-test-model",
                    "--prompt-file", str(prompt),
                    "--output-file", str(output),
                    "--manifest", str(manifest),
                    "--seed", "7",
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
                self.assertEqual([], pm.verify_manifest_files(manifest, data))
                self.assertEqual("requested-test-model", _Handler.received["model"])
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

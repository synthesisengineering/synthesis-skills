#!/usr/bin/env python3
"""Capture a bounded Ollama runtime and model-metadata receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from local_generate import endpoint_class
from provenance_manifest import atomic_write_json


MODEL_INFO_KEYS = {
    "general.architecture",
    "general.file_type",
    "general.name",
    "general.parameter_count",
    "general.quantization_version",
}


def fetch_json(url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"} if body is not None else {},
        method="POST" if body is not None else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ValueError(f"Ollama metadata request failed: {exc}") from exc
    try:
        result = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("Ollama metadata endpoint returned invalid JSON") from exc
    if not isinstance(result, dict):
        raise ValueError("Ollama metadata response must be a JSON object")
    return result


def text_record(value: str) -> dict[str, Any]:
    raw = value.encode("utf-8")
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def select_model(models: Any, requested: str) -> dict[str, Any]:
    if not isinstance(models, list):
        raise ValueError("Ollama /api/tags response lacks a models array")
    matches = [
        item for item in models
        if isinstance(item, dict) and requested in {item.get("name"), item.get("model")}
    ]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one installed model matching {requested!r}")
    return matches[0]


def build_receipt(base_url: str, model: str) -> dict[str, Any]:
    classification = endpoint_class(base_url, False)
    if classification != "local_loopback":
        raise ValueError("Ollama metadata capture requires a loopback endpoint")
    base = base_url.rstrip("/")
    version = fetch_json(f"{base}/api/version")
    tags = fetch_json(f"{base}/api/tags")
    show = fetch_json(f"{base}/api/show", {"model": model, "verbose": False})
    tag = select_model(tags.get("models"), model)

    license_text = show.get("license") if isinstance(show.get("license"), str) else ""
    template = show.get("template") if isinstance(show.get("template"), str) else ""
    license_name = next((line.strip() for line in license_text.splitlines() if line.strip()), None)
    model_info = show.get("model_info") if isinstance(show.get("model_info"), dict) else {}
    selected_model_info = {
        key: value for key, value in model_info.items()
        if key in MODEL_INFO_KEYS or key.endswith(".context_length")
    }
    details = tag.get("details") if isinstance(tag.get("details"), dict) else {}
    show_details = show.get("details") if isinstance(show.get("details"), dict) else {}
    if show_details:
        details = show_details

    unknowns: list[str] = []
    for field, value in (
        ("runtime.version", version.get("version")),
        ("model.digest", tag.get("digest")),
        ("model.license", license_name),
        ("model.template", template),
        ("model.quantization", details.get("quantization_level")),
    ):
        if value in {None, ""}:
            unknowns.append(field)

    return {
        "schema_version": 1,
        "captured_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "endpoint_class": classification,
        "runtime": {"name": "ollama", "version": version.get("version")},
        "model": {
            "requested": model,
            "reported_name": tag.get("name"),
            "reported_model": tag.get("model"),
            "digest": tag.get("digest"),
            "size_bytes": tag.get("size"),
            "modified_at": tag.get("modified_at"),
            "details": details,
            "capabilities": show.get("capabilities"),
            "requires_runtime": show.get("requires"),
            "parameters": show.get("parameters"),
            "license": {"name": license_name, **text_record(license_text)},
            "template": {"text": template, **text_record(template)},
            "model_info": dict(sorted(selected_model_info.items())),
        },
        "unknowns": unknowns,
        "claim_boundary": (
            "This receipt records metadata reported by a local Ollama service. "
            "It does not prove authorship, model-license compliance, or absence of a watermark."
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        receipt = build_receipt(args.base_url, args.model)
        atomic_write_json(Path(args.output), receipt)
    except (OSError, ValueError) as exc:
        print(f"Ollama metadata error: {exc}", file=sys.stderr)
        return 2
    print(f"wrote bounded Ollama metadata receipt: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

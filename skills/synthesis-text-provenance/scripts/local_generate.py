#!/usr/bin/env python3
"""Generate once through an OpenAI-compatible endpoint and record provenance."""

from __future__ import annotations

import argparse
import ipaddress
import json
import math
import os
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from provenance_manifest import ManifestError, atomic_write_json, create_manifest


def endpoint_class(url: str, allow_non_loopback: bool) -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("endpoint must be an HTTP or HTTPS URL with a hostname")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("endpoint must not contain embedded credentials")
    if parsed.params or parsed.query or parsed.fragment:
        raise ValueError("endpoint must not contain parameters, a query, or a fragment")
    host = parsed.hostname.lower()
    try:
        loopback = ipaddress.ip_address(host).is_loopback
    except ValueError:
        loopback = host == "localhost"
    if loopback:
        return "local_loopback"
    if not allow_non_loopback:
        raise ValueError("non-loopback endpoint requires --allow-non-loopback")
    return "local_lan" if parsed.scheme == "http" else "hosted"


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def read_utf8(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"not valid UTF-8: {path}: {exc}") from exc


def build_request(args: argparse.Namespace) -> dict[str, Any]:
    messages: list[dict[str, str]] = []
    if args.system_file:
        messages.append({"role": "system", "content": read_utf8(Path(args.system_file))})
    messages.append({"role": "user", "content": read_utf8(Path(args.prompt_file))})
    request: dict[str, Any] = {
        "model": args.model,
        "messages": messages,
        "temperature": args.temperature,
        "max_tokens": args.max_tokens,
        "stream": False,
    }
    if args.seed is not None:
        request["seed"] = args.seed
    if args.reasoning_effort is not None:
        request["reasoning_effort"] = args.reasoning_effort
    return request


def call_endpoint(args: argparse.Namespace, payload: dict[str, Any]) -> dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if args.api_key_env:
        key = os.environ.get(args.api_key_env)
        if not key:
            raise ValueError(f"environment variable is unset: {args.api_key_env}")
        headers["Authorization"] = f"Bearer {key}"
    request = urllib.request.Request(
        args.endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=args.timeout) as response:
            raw = response.read()
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ValueError(f"endpoint request failed: {exc}") from exc
    try:
        result = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("endpoint returned invalid JSON") from exc
    if not isinstance(result, dict):
        raise ValueError("endpoint response must be a JSON object")
    return result


def extract_content(result: dict[str, Any]) -> tuple[str, str | None, dict[str, Any]]:
    try:
        choice = result["choices"][0]
        content = choice["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("endpoint response lacks choices[0].message.content") from exc
    if not isinstance(content, str):
        raise ValueError("choices[0].message.content must be a string")
    if not content.strip():
        raise ValueError("choices[0].message.content must contain final text")
    returned_model = result.get("model")
    if returned_model is not None and not isinstance(returned_model, str):
        raise ValueError("response model must be a string or absent")
    finish_reason = choice.get("finish_reason")
    if finish_reason is not None and not isinstance(finish_reason, str):
        raise ValueError("response finish_reason must be a string or absent")
    usage = result.get("usage")
    if usage is not None and not isinstance(usage, dict):
        raise ValueError("response usage must be an object or absent")
    system_fingerprint = result.get("system_fingerprint")
    if system_fingerprint is not None and not isinstance(system_fingerprint, str):
        raise ValueError("response system_fingerprint must be a string or absent")
    response_metadata = {
        "finish_reason": finish_reason,
        "usage": usage,
        "system_fingerprint": system_fingerprint,
    }
    return content, returned_model, response_metadata


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434/v1/chat/completions")
    parser.add_argument("--allow-non-loopback", action="store_true")
    parser.add_argument("--api-key-env", help="environment variable containing a bearer token")
    parser.add_argument("--provider", required=True)
    parser.add_argument("--runtime", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--prompt-file", required=True)
    parser.add_argument("--system-file")
    parser.add_argument(
        "--runtime-receipt",
        help="native runtime receipt to bind cryptographically into the manifest",
    )
    parser.add_argument("--output-file", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--max-tokens", type=int, default=2048)
    parser.add_argument("--seed", type=int)
    parser.add_argument(
        "--reasoning-effort",
        choices=("none", "low", "medium", "high"),
        help="optional OpenAI-compatible reasoning control",
    )
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--note", action="append", default=[])
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_path = Path(args.output_file)
    manifest_path = Path(args.manifest)
    receipt_path = Path(args.runtime_receipt) if args.runtime_receipt else None
    if output_path.resolve() == manifest_path.resolve():
        print("local generation error: output and manifest paths must differ", file=sys.stderr)
        return 2
    input_paths = [Path(args.prompt_file)]
    if args.system_file:
        input_paths.append(Path(args.system_file))
    if receipt_path is not None:
        input_paths.append(receipt_path)
    for target_name, target in (("output", output_path), ("manifest", manifest_path)):
        if any(target.resolve() == source.resolve() for source in input_paths):
            print(
                f"local generation error: {target_name} path must differ from every input path",
                file=sys.stderr,
            )
            return 2
    try:
        if not math.isfinite(args.temperature) or args.temperature < 0:
            raise ValueError("temperature must be a finite non-negative number")
        if isinstance(args.max_tokens, bool) or args.max_tokens <= 0:
            raise ValueError("max-tokens must be a positive integer")
        if not math.isfinite(args.timeout) or args.timeout <= 0:
            raise ValueError("timeout must be a finite positive number")
        classification = endpoint_class(args.endpoint, args.allow_non_loopback)
        if classification.startswith("local_") and not args.runtime_receipt:
            raise ValueError("local generation requires --runtime-receipt")
        if receipt_path is not None and not receipt_path.is_file():
            raise ValueError(f"runtime receipt is not a regular file: {receipt_path}")
        payload = build_request(args)
        result = call_endpoint(args, payload)
        content, returned_model, response_metadata = extract_content(result)
        atomic_write_text(output_path, content)
        parameters = {
            "temperature": args.temperature,
            "max_tokens": args.max_tokens,
            "seed": args.seed,
            "reasoning_effort": args.reasoning_effort,
            "system_prompt_supplied": bool(args.system_file),
            "reported_response": response_metadata,
        }
        sources = [Path(args.system_file)] if args.system_file else []
        manifest = create_manifest(
            generation_mode="local_open_weight" if classification.startswith("local_") else "hosted",
            provider=args.provider,
            model_requested=args.model,
            model_returned=returned_model,
            runtime=args.runtime,
            runtime_receipt_file=receipt_path,
            endpoint_class=classification,
            prompt_file=Path(args.prompt_file),
            output_file=output_path,
            source_files=sources,
            parameters=parameters,
            notes=[
                *args.note,
                "One generation only; no provenance detector or detector-feedback optimization was used.",
            ],
        )
        atomic_write_json(manifest_path, manifest)
    except (OSError, ValueError, ManifestError) as exc:
        print(f"local generation error: {exc}", file=sys.stderr)
        return 2
    print(f"wrote output and valid provenance manifest: {output_path}, {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

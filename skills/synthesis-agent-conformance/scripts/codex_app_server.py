#!/usr/bin/env python3
"""Small read-only JSON-RPC client for Codex app-server audits."""

from __future__ import annotations

import json
import selectors
import subprocess
import time
from collections.abc import Mapping


def initialize_message(title: str) -> dict[str, object]:
    return {
        "method": "initialize",
        "id": 0,
        "params": {
            "clientInfo": {
                "name": "codex_vscode",
                "title": title,
                "version": "1.0.0",
            }
        },
    }


def query(
    binary: str,
    method: str,
    params: Mapping[str, object],
    *,
    title: str = "Synthesis Conformance Audit",
    timeout: int = 15,
) -> dict[str, object]:
    """Return one app-server response without mutating Codex state."""
    process = subprocess.Popen(
        [binary, "app-server", "--stdio"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    assert process.stdin and process.stdout and process.stderr
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ, "stdout")
    selector.register(process.stderr, selectors.EVENT_READ, "stderr")
    stderr: list[str] = []

    def send(message: dict[str, object]) -> None:
        process.stdin.write(json.dumps(message) + "\n")
        process.stdin.flush()

    send(initialize_message(title))
    sent_request = False
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            if process.poll() is not None and not selector.get_map():
                break
            for key, _ in selector.select(timeout=0.25):
                stream = key.fileobj
                line = stream.readline()
                if not line:
                    try:
                        selector.unregister(stream)
                    except KeyError:
                        pass
                    continue
                if key.data == "stderr":
                    stderr.append(line.rstrip())
                    continue
                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if message.get("id") == 0 and not sent_request:
                    if "error" in message:
                        raise RuntimeError(json.dumps(message["error"], sort_keys=True))
                    send({"method": "initialized", "params": {}})
                    send({"method": method, "id": 1, "params": dict(params)})
                    sent_request = True
                    continue
                if message.get("id") != 1:
                    continue
                if "error" in message:
                    raise RuntimeError(json.dumps(message["error"], sort_keys=True))
                result = message.get("result")
                if isinstance(result, dict):
                    return result
                raise RuntimeError(f"{method} returned a non-object result")
        raise RuntimeError(
            f"{method} returned no response: " + " | ".join(stderr[-5:])
        )
    finally:
        selector.close()
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)

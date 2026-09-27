#!/usr/bin/env python3
"""Minimal MCP JSON-RPC-over-HTTP client for workspace-mcp.

Usage:
  mcp_client.py <tool_name> <json_args>
  mcp_client.py list [filter_substring]

Requires httpx (install via `uv run --with httpx python mcp_client.py ...`).

Assumes workspace-mcp is running at http://localhost:8765/mcp — override via WORKSPACE_MCP_URL env var.
"""

import httpx
import json
import os
import sys
import time

BASE = os.environ.get("WORKSPACE_MCP_URL", "http://localhost:8765/mcp")
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


MAX_RESPONSE_BYTES = 8 * 1024 * 1024


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate MCP JSON key")
            result[key] = value
        return result
    return json.loads(text, object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError("nonfinite MCP JSON")))


def _parse_sse(text: str, expected_id=2) -> dict:
    """Read JSON or SSE, ignoring notifications rather than the actual result."""
    if len(text.encode("utf-8")) > MAX_RESPONSE_BYTES:
        raise ValueError("MCP response exceeded bounded input")
    try:
        direct = strict_json(text)
    except json.JSONDecodeError:
        direct = None
    frames = []
    if direct is not None:
        frames.append(direct)
    else:
        for frame in text.replace("\r\n", "\n").split("\n\n"):
            fields = [
                line[5:].lstrip()
                for line in frame.splitlines()
                if line.startswith("data:")
            ]
            if fields:
                frames.append(strict_json("\n".join(fields)))
    matching = [f for f in frames if isinstance(f, dict) and type(f.get("id")) is type(expected_id) and f.get("id") == expected_id]
    if len(matching) != 1:
        raise ValueError("MCP response has no unique matching request ID")
    return matching[0]


def call_tool_text(result) -> str:
    """Unwrap nested JSON-RPC/MCP envelopes without flattening error results.

    Plain document JSON remains text for tab-ID parsing. Only recognized
    envelope keys are unwrapped. Every layer is bounded; a nested error is a
    refusal, never proof that the provider has no transcript.
    """
    budget = [0]

    def visit(value, depth=0):
        if depth > 12:
            raise ValueError("MCP envelope nesting exceeded")
        if isinstance(value, str):
            budget[0] += len(value.encode("utf-8"))
            if budget[0] > MAX_RESPONSE_BYTES:
                raise ValueError("MCP text expansion exceeded")
            try:
                parsed = strict_json(value)
            except json.JSONDecodeError:
                return value
            if isinstance(parsed, dict) and any(
                k in parsed for k in ("result", "content", "isError", "error")
            ):
                return visit(parsed, depth + 1)
            return value
        if not isinstance(value, dict):
            raise ValueError("unsupported MCP result shape")
        if "isError" in value and type(value["isError"]) is not bool:
            raise ValueError("malformed MCP error flag")
        if value.get("error") is not None or value.get("isError") is True:
            raise ValueError("MCP tool returned an error; source coverage unknown")
        if "result" in value:
            return visit(value["result"], depth + 1)
        content = value.get("content")
        if not isinstance(content, list) or len(content) > 10000:
            raise ValueError("MCP text content list missing or unbounded")
        output = []
        for item in content:
            if not isinstance(item, dict) or item.get("type") != "text":
                raise ValueError("MCP result contains unsupported non-text content")
            output.append(visit(item.get("text"), depth + 1))
        return "\n".join(output)

    return visit(result)


def bounded_post(client, url, **kwargs):
    """Bound decompressed response bytes while streaming; HTTP failure is unknown coverage."""
    deadline = time.monotonic() + 60
    with client.stream("POST", url, **kwargs) as response:
        response.raise_for_status()
        content = bytearray()
        for chunk in response.iter_bytes(chunk_size=65536):
            if time.monotonic() >= deadline:
                raise ValueError("MCP response total time bound reached")
            if len(content) + len(chunk) > MAX_RESPONSE_BYTES:
                raise ValueError("MCP response exceeded bounded input")
            content.extend(chunk)
        return httpx.Response(response.status_code, headers=response.headers,
                              content=bytes(content), request=response.request)


def _init_session(client: httpx.Client) -> str:
    """Initialize an MCP session and return the session ID."""
    r = bounded_post(client,
        BASE,
        headers=HEADERS,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "mcp_client.py", "version": "0.1"},
            },
        },
    )
    r.raise_for_status()
    sid = r.headers.get("mcp-session-id", "")
    if not sid:
        raise RuntimeError(f"No session ID returned. Response: {r.text[:200]}")
    bounded_post(client,
        BASE,
        headers={**HEADERS, "Mcp-Session-Id": sid},
        json={"jsonrpc": "2.0", "method": "notifications/initialized"},
    )
    return sid


def call_tool(tool_name: str, args: dict) -> dict:
    """Call an MCP tool and return the parsed result."""
    with httpx.Client(timeout=60) as c:
        sid = _init_session(c)
        r = bounded_post(c,
            BASE,
            headers={**HEADERS, "Mcp-Session-Id": sid},
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": args},
            },
        )
        r.raise_for_status()
        return _parse_sse(r.text)


def list_tools(filter_str: str | None = None) -> None:
    """List available tools, optionally filtered by substring."""
    with httpx.Client(timeout=30) as c:
        sid = _init_session(c)
        r = bounded_post(c,
            BASE,
            headers={**HEADERS, "Mcp-Session-Id": sid},
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        )
        data = _parse_sse(r.text)
        tools = data.get("result", {}).get("tools", [])
        for t in tools:
            name = t["name"]
            if not filter_str or filter_str.lower() in name.lower():
                desc = t.get("description", "").replace("\n", " ")[:120]
                print(f"{name}: {desc}")


def _emit_result(result: dict) -> None:
    """Print only successfully unwrapped text; errors retain unknown coverage."""
    print(call_tool_text(result))


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    if sys.argv[1] == "list":
        list_tools(sys.argv[2] if len(sys.argv) > 2 else None)
    else:
        result = call_tool(sys.argv[1], json.loads(sys.argv[2]))
        _emit_result(result)


if __name__ == "__main__":
    main()

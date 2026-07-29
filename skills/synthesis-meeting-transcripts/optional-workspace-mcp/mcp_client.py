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

BASE = os.environ.get("WORKSPACE_MCP_URL", "http://localhost:8765/mcp")
HEADERS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}


def _parse_sse(text: str) -> dict:
    """Parse Server-Sent Events response — return the first data payload."""
    for line in text.strip().split("\n"):
        if line.startswith("data: "):
            return json.loads(line[6:])
    return {}


def _init_session(client: httpx.Client) -> str:
    """Initialize an MCP session and return the session ID."""
    r = client.post(BASE, headers=HEADERS, json={
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "mcp_client.py", "version": "0.1"},
        },
    })
    sid = r.headers.get("mcp-session-id", "")
    if not sid:
        raise RuntimeError(f"No session ID returned. Response: {r.text[:200]}")
    client.post(BASE, headers={**HEADERS, "Mcp-Session-Id": sid},
                json={"jsonrpc": "2.0", "method": "notifications/initialized"})
    return sid


def call_tool(tool_name: str, args: dict) -> dict:
    """Call an MCP tool and return the parsed result."""
    with httpx.Client(timeout=60) as c:
        sid = _init_session(c)
        r = c.post(BASE, headers={**HEADERS, "Mcp-Session-Id": sid}, json={
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": tool_name, "arguments": args},
        })
        return _parse_sse(r.text)


def list_tools(filter_str: str | None = None) -> None:
    """List available tools, optionally filtered by substring."""
    with httpx.Client(timeout=30) as c:
        sid = _init_session(c)
        r = c.post(BASE, headers={**HEADERS, "Mcp-Session-Id": sid},
                   json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        data = _parse_sse(r.text)
        tools = data.get("result", {}).get("tools", [])
        for t in tools:
            name = t["name"]
            if not filter_str or filter_str.lower() in name.lower():
                desc = t.get("description", "").replace("\n", " ")[:120]
                print(f"{name}: {desc}")


def _emit_result(result: dict) -> None:
    """Print the text content from a tool call result."""
    if "error" in result:
        print(f"ERROR: {result['error']}", file=sys.stderr)
        sys.exit(1)
    content = result.get("result", {}).get("content", [])
    for item in content:
        if item.get("type") == "text":
            print(item.get("text", ""))


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

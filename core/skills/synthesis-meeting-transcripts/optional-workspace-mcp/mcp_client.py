#!/usr/bin/env python3
"""Minimal MCP JSON-RPC-over-HTTP client for a local workspace-mcp server (standard library only).

Usage:
  mcp_client.py <tool_name> <json_args>
  mcp_client.py list [filter_substring]

Assumes workspace-mcp is running at http://localhost:8765/mcp; override with WORKSPACE_MCP_URL.
Prints the tool's text. A tool error, an HTTP error or a malformed reply exits 1 with the reason:
an error says nothing about whether a document or transcript exists.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("WORKSPACE_MCP_URL", "http://localhost:8765/mcp")
HEADERS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
           "Accept-Encoding": "identity"}
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
PROTOCOL_VERSION = "2025-03-26"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError("MCP server redirected; refused")


OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect)  # never via a proxy


def strict_json(text: str):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate MCP JSON key")
            result[key] = value
        return result
    return json.loads(text, object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError("nonfinite MCP JSON")))


def parse_sse(text: str, expected_id=2) -> dict:
    """The one reply carrying this request's id, from plain JSON or server-sent events.
    Notifications in the stream are skipped, never mistaken for the result."""
    if len(text.encode("utf-8")) > MAX_RESPONSE_BYTES:
        raise ValueError("MCP response exceeded bounded input")
    try:
        frames = [strict_json(text)]
    except json.JSONDecodeError:
        frames = []
        for frame in text.replace("\r\n", "\n").split("\n\n"):
            data = [line[5:].lstrip() for line in frame.splitlines() if line.startswith("data:")]
            if data:
                frames.append(strict_json("\n".join(data)))
    matching = [f for f in frames if isinstance(f, dict) and type(f.get("id")) is type(expected_id)
                and f.get("id") == expected_id]
    if len(matching) != 1:
        raise ValueError("MCP response has no unique matching request ID")
    return matching[0]


def call_tool_text(result) -> str:
    """Unwrap nested JSON-RPC/MCP envelopes to text. Plain document JSON stays text. An outer or
    nested error is a refusal, never evidence that the provider has no transcript (IR-57)."""
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
            if isinstance(parsed, dict) and any(k in parsed for k in ("result", "content", "isError", "error")):
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


def post(url: str, payload: dict, session: str | None = None) -> tuple:
    """One bounded POST: (status, headers, body text). HTTP failures raise ValueError."""
    headers = dict(HEADERS, **({"Mcp-Session-Id": session, "MCP-Protocol-Version": PROTOCOL_VERSION} if session else {}))
    request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with OPENER.open(request, timeout=60) as response:
            if response.headers.get("Content-Encoding", "identity").lower() not in ("", "identity"):
                raise ValueError("compressed MCP response refused before expansion")
            body = response.read(MAX_RESPONSE_BYTES + 1)
            status, reply_headers = response.status, response.headers
    except urllib.error.HTTPError as exc:
        raise ValueError(f"MCP HTTP {exc.code}; source coverage unknown") from None
    except (urllib.error.URLError, OSError) as exc:
        raise ValueError(f"MCP transport failed ({exc}); coverage unknown") from None
    if len(body) > MAX_RESPONSE_BYTES:
        raise ValueError("MCP response exceeded bounded input")
    return status, reply_headers, body.decode("utf-8", "replace")


def open_session(url: str = BASE, client_name: str = "mcp_client.py") -> str:
    """Initialize an MCP session and return its id."""
    _, headers, text = post(url, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": PROTOCOL_VERSION, "capabilities": {},
        "clientInfo": {"name": client_name, "version": "1.0"}}})
    reply = parse_sse(text, expected_id=1)
    result = reply.get("result")
    if reply.get("jsonrpc") != "2.0" or "error" in reply or not isinstance(result, dict):
        raise ValueError("MCP initialize did not return a matching successful reply")
    if result.get("protocolVersion") != PROTOCOL_VERSION or not isinstance(result.get("capabilities", {}).get("tools"), dict):
        raise ValueError("MCP initialize did not negotiate the protocol and tools")
    sid = headers.get("mcp-session-id", "")
    if not re.fullmatch(r"[\x21-\x7e]{1,1024}", sid):
        raise ValueError("no bounded visible-ASCII MCP session id returned")
    status, _, body = post(url, {"jsonrpc": "2.0", "method": "notifications/initialized"}, sid)
    if status != 202 or body:
        raise ValueError("MCP initialized notification was not accepted")
    return sid


def call_tool(tool: str, arguments: dict, url: str = BASE, client_name: str = "mcp_client.py") -> str:
    """Call one tool in a fresh session and return its text."""
    sid = open_session(url, client_name)
    _, _, text = post(url, {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                            "params": {"name": tool, "arguments": arguments}}, sid)
    return call_tool_text(parse_sse(text))


def list_tools(filter_str: str | None = None, url: str = BASE) -> list:
    sid = open_session(url)
    _, _, text = post(url, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, sid)
    tools = parse_sse(text).get("result", {}).get("tools", [])
    return [t for t in tools if not filter_str or filter_str.lower() in t["name"].lower()]


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__, file=sys.stderr if not argv else sys.stdout)
        return 2 if not argv else 0
    try:
        if argv[0] == "list":
            for tool in list_tools(argv[1] if len(argv) > 1 else None):
                print(f"{tool['name']}: {tool.get('description', '').replace(chr(10), ' ')[:120]}")
        else:
            print(call_tool(argv[0], json.loads(argv[1]) if len(argv) > 1 else {}))
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

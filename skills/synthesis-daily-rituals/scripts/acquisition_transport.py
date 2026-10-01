"""Bounded read-only acquisition transport; credentials never enter custody.

Only fixed Slack/Google read endpoints are callable. An error never becomes an
empty result. Rate limits are retained and refused, with no automatic retry.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import time

MAX_RESPONSE = 4 * 1024 * 1024
MAX_TOTAL = 128 * 1024 * 1024
SLACK_METHODS = frozenset(
    {
        "auth.test",
        "conversations.info",
        "conversations.history",
        "conversations.replies",
        "search.messages",
    }
)


def strict_json(raw):
    def pairs(rows):
        out = {}
        for key, value in rows:
            if key in out:
                raise ValueError("duplicate response key")
            out[key] = value
        return out

    def constant(_):
        raise ValueError("nonfinite response value")

    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    except (UnicodeError, RecursionError, json.JSONDecodeError) as exc:
        raise ValueError("malformed acquisition JSON") from exc


def output_path(value, *, directory=False):
    """Validate existing ancestry without creating files or resolving aliases."""
    import stat

    if not isinstance(value, (str, Path)):
        raise ValueError("explicit acquisition output path required")
    path = Path(value)
    if (
        not path.is_absolute()
        or ".." in path.parts
        or len(path.parts) > 256
        or path == Path(path.anchor)
    ):
        raise ValueError("acquisition output must be a bounded physical absolute path")
    for node in (*reversed(path.parents), path):
        try:
            mode = node.lstat().st_mode
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(mode) or (node != path or directory) and not stat.S_ISDIR(mode):
            raise ValueError("acquisition output ancestor must be a physical directory")
        if node == path and not directory and not stat.S_ISREG(mode):
            raise ValueError("acquisition output must be a regular file")
    return path


def credential(reference):
    """Resolve one explicit local reference, never discover accounts or mint tokens."""
    if not isinstance(reference, str):
        raise ValueError("credential reference must be env: or file:")
    if reference.startswith("env:") and re.fullmatch(
        r"[A-Za-z_][A-Za-z0-9_]*", reference[4:]
    ):
        value = os.environ.get(reference[4:], "")
    elif reference.startswith("file:") and Path(reference[5:]).is_absolute():
        from ritual_workers import read_regular

        value = read_regular(Path(reference[5:]), 16384).decode("utf-8").strip()
    elif reference.startswith("mcp:"):
        raise ValueError(
            "client-managed MCP acquisition transport is unavailable in this Python process; no direct-token fallback"
        )
    else:
        raise ValueError(
            "unsupported credential reference; token literals are forbidden"
        )
    if (
        not value
        or len(value) > 16384
        or value.startswith("PLACEHOLDER")
        or any(c.isspace() for c in value)
    ):
        raise ValueError("credential reference is missing or malformed")
    return value


class Capture:
    """Retain every bounded response in the existing archive owner, status is metadata."""

    def __init__(self, root):
        self.root = output_path(root, directory=True)
        if not self.root.is_absolute() or ".." in self.root.parts:
            raise ValueError("capture root must be a physical absolute path")
        self.calls = []
        self.bytes = 0
        self.serialized_bytes = 0
        self.deadline = time.monotonic() + 120

    def admit(self):
        if (
            len(self.calls) >= 1000
            or self.bytes >= MAX_TOTAL
            or time.monotonic() >= self.deadline
        ):
            raise ValueError("acquisition aggregate request/time/byte budget exhausted")

    def retain(
        self, route, status, raw, *, error=None, request=None, omitted_sha256=None
    ):
        import base64
        from archive_publish import publish_json

        if len(self.calls) >= 1000:
            raise ValueError("acquisition custody request bound exhausted")
        if len(raw) > MAX_RESPONSE or self.bytes + len(raw) > MAX_TOTAL:
            raise ValueError("acquisition capture byte bound exceeded")
        self.bytes += len(raw)
        digest = hashlib.sha256(raw).hexdigest()
        record = {
            "route": route,
            "http_status": status,
            "raw_sha256": digest,
            "raw_base64": base64.b64encode(raw).decode("ascii"),
            "error": error,
            "request": request,
            "omitted_raw_sha256": omitted_sha256,
        }
        wire_size = (
            len(
                json.dumps(
                    record, ensure_ascii=False, sort_keys=True, indent=2
                ).encode()
            )
            + 1
        )
        if self.serialized_bytes + wire_size > 2 * MAX_TOTAL:
            raise ValueError("serialized custody aggregate bound exceeded")
        self.serialized_bytes += wire_size
        # Each response is immutable. An existing exact receipt is idempotent.
        name = f"{len(self.calls):04d}-{digest}.json"
        receipt = publish_json(self.root / name, record)
        self.calls.append(receipt)
        return str(self.root / name) + "#" + digest

    def summary(self, *, include_receipts=True):
        return {
            "calls": len(self.calls),
            "response_bytes": self.bytes,
            "serialized_bytes": self.serialized_bytes,
            "raw_receipts": self.calls if include_receipts else [],
            "native_acceptance": False,
        }


class ReadTransport:
    def __init__(self, token_ref, capture):
        # Verify dependencies before reading a credential or creating a client.
        try:
            import httpx
        except ImportError as exc:
            raise ValueError(
                "httpx missing from the verified Python interpreter; install the declared acquisition dependencies"
            ) from exc
        self.capture = capture
        self._token = credential(token_ref)
        self.client = httpx.Client(timeout=15, follow_redirects=False, trust_env=False)

    def close(self):
        self.client.close()

    def call(self, route, params=None):
        import httpx

        if route in SLACK_METHODS:
            url = "https://slack.com/api/" + route
            method = "POST" if route == "auth.test" else "GET"
        elif route in {"drive/about", "drive/files"}:
            url = "https://www.googleapis.com/drive/v3/" + route.split("/")[1]
            method = "GET"
        elif re.fullmatch(r"drive/file/[A-Za-z0-9_-]+", route):
            url = "https://www.googleapis.com/drive/v3/files/" + route.split("/")[-1]
            method = "GET"
        elif re.fullmatch(r"docs/[A-Za-z0-9_-]+", route):
            url = "https://docs.googleapis.com/v1/documents/" + route.split("/")[1]
            method = "GET"
        else:
            raise ValueError("acquisition endpoint is not in the read-only allowlist")
        params = params or {}
        if not isinstance(params, dict) or any(
            k.lower() in {"token", "authorization", "access_token"} for k in params
        ):
            raise ValueError(
                "credentials must never be placed in acquisition request parameters"
            )
        self.capture.admit()
        raw = bytearray()
        status = None
        call_id = None
        try:
            with self.client.stream(
                method,
                url,
                params=params,
                headers={
                    "Authorization": "Bearer " + self._token,
                    "Accept": "application/json",
                    "Accept-Encoding": "identity",
                },
            ) as response:
                status = response.status_code
                if response.headers.get("content-encoding", "identity").lower() not in {
                    "",
                    "identity",
                }:
                    raise ValueError("compressed response refused before decoding")
                for chunk in response.iter_raw(chunk_size=65536):
                    self.capture.admit()
                    if (
                        len(raw) + len(chunk) > MAX_RESPONSE
                        or self.capture.bytes + len(raw) + len(chunk) > MAX_TOTAL
                    ):
                        raise ValueError("response exceeds acquisition byte bound")
                    raw.extend(chunk)
                if self._token.encode() in raw:
                    call_id = self.capture.retain(
                        route,
                        status,
                        b"",
                        request=params,
                        error="CREDENTIAL_ECHO_BODY_WITHHELD",
                        omitted_sha256=hashlib.sha256(raw).hexdigest(),
                    )
                    raise ValueError(
                        "provider echoed a credential; original body cannot enter capture"
                    )
                call_id = self.capture.retain(route, status, bytes(raw), request=params)
                if time.monotonic() >= self.capture.deadline:
                    raise ValueError("acquisition aggregate time bound reached")
                if not 200 <= status < 300:
                    raise ValueError(
                        f"acquisition HTTP {status}; no retry or empty-result inference; custody={call_id}"
                    )
        except (httpx.HTTPError, ValueError) as exc:
            if call_id is None:
                if self._token.encode() in raw:
                    call_id = self.capture.retain(
                        route,
                        status,
                        b"",
                        request=params,
                        error="CREDENTIAL_ECHO_BODY_WITHHELD",
                        omitted_sha256=hashlib.sha256(raw).hexdigest(),
                    )
                else:
                    call_id = self.capture.retain(
                        route,
                        status,
                        bytes(raw),
                        error=type(exc).__name__,
                        request=params,
                    )
            raise ValueError(
                f"acquisition transport failed; custody={call_id}"
            ) from None
        value = strict_json(bytes(raw))
        if (
            not isinstance(value, dict)
            or value.get("error")
            or (route in SLACK_METHODS and value.get("ok") is not True)
        ):
            raise ValueError(
                f"acquisition provider refused or returned malformed content; custody={call_id}"
            )
        return value, call_id

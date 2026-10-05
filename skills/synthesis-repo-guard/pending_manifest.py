"""Pure pending-manifest representation shared by retained reader runtimes.

Generated from checkpoint_sync.py's representation block. The standalone
retirement reconciler owns the original implementation; an exact-source control
requires this reader artifact to contain the same functions and finite limits.
No lifecycle, publication, coordination or autopilot code executes on import.
"""

import json
from pathlib import Path

# A representation bound, not permission to acquire or retire attribution.
# Keep the writer's existing 200,000-path / 128-MiB limits unchanged.
PENDING_PATH_ENCODING = "path-index-v1"
PENDING_PATH_LIMIT = 200_000
PENDING_MANIFEST_LIMIT = 128 * 1024 * 1024
_PENDING_MAP_FIELDS = ("content_hashes", "path_hashes", "path_kinds")


def decode_pending_manifest(payload: dict) -> dict:
    """Expand references only; native identity and all logical values stay inert.

    The table covers map keys as well as currently pending paths, so retained
    retirement metadata is never silently pruned by a representation change.
    Semantic ownership, hash, kind and remote-subset checks remain with readers.
    """
    if not isinstance(payload, dict):
        raise ValueError("pending manifest must be an object")
    if "path_encoding" not in payload:
        if "path_table" in payload:
            raise ValueError("pending path table has no encoding")
        return payload
    if (payload["path_encoding"] != PENDING_PATH_ENCODING
            or type(payload.get("schema_version")) is not int
            or payload["schema_version"] != 2):
        raise ValueError("unsupported pending path encoding")
    table = payload.get("path_table")
    if (not isinstance(table, list) or len(table) > PENDING_PATH_LIMIT
            or any(not isinstance(value, str) or not value
                   or not Path(value).is_absolute() or ".." in Path(value).parts
                   for value in table)
            or len(set(table)) != len(table)):
        raise ValueError("invalid pending path dictionary")

    def references(values):
        if (not isinstance(values, list) or len(values) > PENDING_PATH_LIMIT
                or any(type(index) is not int or not 0 <= index < len(table)
                       for index in values)
                or len(set(values)) != len(values)):
            raise ValueError("invalid pending path references")
        return [table[index] for index in values]

    result = dict(payload)
    del result["path_encoding"]
    del result["path_table"]
    result["paths"] = references(payload.get("paths"))
    if "remote_paths" in payload:
        result["remote_paths"] = references(payload["remote_paths"])
    for field in _PENDING_MAP_FIELDS:
        if field not in payload:
            continue
        values = payload[field]
        if not isinstance(values, dict) or len(values) > PENDING_PATH_LIMIT:
            raise ValueError("invalid pending indexed map")
        restored = {}
        for key, value in values.items():
            if (not isinstance(key, str) or not key.isascii() or not key.isdecimal()
                    or len(key) > 6 or (len(key) > 1 and key[0] == "0")):
                raise ValueError("invalid pending map reference")
            index = int(key)
            if not 0 <= index < len(table):
                raise ValueError("pending map reference is outside dictionary")
            restored[table[index]] = value
        result[field] = restored
    # Unused table entries could conceal otherwise unvalidated attribution.
    used = set(result["paths"]) | set(result.get("remote_paths", []))
    for field in _PENDING_MAP_FIELDS:
        used.update(result.get(field, {}))
    if used != set(table):
        raise ValueError("pending dictionary contains unreferenced paths")
    return result


def encode_pending_manifest(payload: dict) -> dict:
    """Losslessly index repeated path strings; never change any evidence value."""
    logical = decode_pending_manifest(payload)
    if type(logical.get("schema_version")) is not int or logical["schema_version"] != 2:
        raise ValueError("indexed pending manifests require schema 2")
    table = []
    indices = {}

    def index(value):
        if (not isinstance(value, str) or not value or not Path(value).is_absolute()
                or ".." in Path(value).parts):
            raise ValueError("invalid pending dictionary path")
        if value not in indices:
            if len(table) >= PENDING_PATH_LIMIT:
                raise ValueError("pending path dictionary exceeds its ceiling")
            indices[value] = len(table)
            table.append(value)
        return indices[value]

    result = dict(logical)
    for field in ("paths", "remote_paths"):
        if field not in logical and field == "remote_paths":
            continue
        values = logical.get(field)
        if not isinstance(values, list) or len(values) > PENDING_PATH_LIMIT:
            raise ValueError("invalid pending path list")
        result[field] = [index(value) for value in values]
        if len(set(result[field])) != len(result[field]):
            raise ValueError("duplicate pending paths")
    for field in _PENDING_MAP_FIELDS:
        if field not in logical:
            continue
        values = logical[field]
        if not isinstance(values, dict) or len(values) > PENDING_PATH_LIMIT:
            raise ValueError("invalid pending path map")
        result[field] = {str(index(key)): value for key, value in values.items()}
    result["path_encoding"] = PENDING_PATH_ENCODING
    result["path_table"] = table
    return result


def pending_manifest_bytes(payload: dict) -> bytes:
    """The single postimage serializer shared by writes and receipt digests."""
    raw = (json.dumps(payload, indent=2) + "\n").encode("utf-8")
    is_manifest = (isinstance(payload, dict) and payload.get("schema_version") == 2
                   and "session_id" in payload and "paths" in payload)
    if "path_encoding" in payload:
        decode_pending_manifest(payload)
    if not is_manifest or len(raw) <= PENDING_MANIFEST_LIMIT:
        return raw
    encoded = encode_pending_manifest(payload)
    raw = (json.dumps(encoded, separators=(",", ":")) + "\n").encode("utf-8")
    if len(raw) > PENDING_MANIFEST_LIMIT:
        raise ValueError("attribution manifest exceeds its byte ceiling")
    return raw

#!/usr/bin/env python3
"""Provider-neutral coordination-board schema and session identities."""

from __future__ import annotations

import base64
import hashlib
import re
import secrets
import time
import uuid
import zlib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable


SCHEMA_VERSION = 4
V4_COLUMNS = (
    "session uuid",
    "compact id",
    "speakable id v1",
    "legacy id",
    "agent",
    "machine",
    "client session ref",
    "project",
    "started",
    "heartbeat",
    "mode",
    "workspace(s) / branch",
    "goal",
    "claimed areas (advisory lock)",
    "context role",
    "status",
)
V3_COLUMNS = (
    "session uuid",
    "compact id",
    "speakable id v1",
    "legacy id",
    "agent",
    "machine",
    "project",
    "started",
    "heartbeat",
    "mode",
    "workspace(s) / branch",
    "goal",
    "claimed areas (advisory lock)",
    "context role",
    "status",
)
V2_COLUMNS = (
    "id",
    "agent",
    "machine",
    "project",
    "started",
    "heartbeat",
    "mode",
    "workspace(s) / branch",
    "goal",
    "claimed areas (advisory lock)",
    "context role",
    "status",
)
V1_COLUMNS = (
    "id",
    "agent",
    "started",
    "mode",
    "goal",
    "claimed areas (advisory lock)",
    "status",
)

CROCKFORD_ALPHABET = "0123456789abcdefghjkmnpqrstvwxyz"
CROCKFORD_DECODE = {
    character: index for index, character in enumerate(CROCKFORD_ALPHABET)
}
CROCKFORD_DECODE.update({"i": 1, "l": 1, "o": 0})
ALIAS_BITS = 60
ALIAS_MASK = (1 << ALIAS_BITS) - 1
WORD_BITS = 11
WORD_COUNT = 4
NUMBER_BITS = 16
WORDLIST_SHA256 = "2f5eed53a4727b4bf8880d8f3f199efc90e58503646d9ff8eff3a2ed3b24dbda"


@dataclass(frozen=True)
class SessionIdentity:
    """One canonical UUIDv7 and its exact human-facing representations."""

    session_uuid: str
    compact_id: str
    speakable_id: str
    legacy_id: str = ""

    def selectors(self) -> tuple[str, ...]:
        return tuple(
            value
            for value in (
                self.session_uuid,
                self.compact_id,
                self.speakable_id,
                self.legacy_id,
            )
            if value
        )


def _plain(value: str) -> str:
    without_bold = re.sub(r"\*\*(.+?)\*\*", r"\1", value)
    return re.sub(r"`(.+?)`", r"\1", without_bold).strip()


def uuid7() -> uuid.UUID:
    """Create an RFC 9562 UUIDv7 using 74 cryptographically random bits."""
    timestamp_ms = time.time_ns() // 1_000_000
    if not 0 <= timestamp_ms < (1 << 48):
        raise OverflowError("current Unix timestamp does not fit UUIDv7")
    random_bits = secrets.randbits(74)
    rand_a = random_bits >> 62
    rand_b = random_bits & ((1 << 62) - 1)
    value = (
        (timestamp_ms << 80)
        | (0b0111 << 76)
        | (rand_a << 64)
        | (0b10 << 62)
        | rand_b
    )
    return uuid.UUID(int=value)


def alias_token(session_uuid: str | uuid.UUID) -> int:
    """Return 60 bits drawn only from UUIDv7 random material."""
    value = (
        session_uuid
        if isinstance(session_uuid, uuid.UUID)
        else uuid.UUID(session_uuid)
    )
    if value.version != 7 or value.variant != uuid.RFC_4122:
        raise ValueError(f"session identity is not an RFC 9562 UUIDv7: {value}")
    # UUIDv7 rand_b occupies the low 62 bits. Its low 60 bits therefore carry
    # no timestamp, version, or variant material.
    return value.int & ALIAS_MASK


def compact_id(token: int) -> str:
    if not 0 <= token <= ALIAS_MASK:
        raise ValueError("compact session token must contain exactly 60 bits")
    encoded = "".join(
        CROCKFORD_ALPHABET[(token >> shift) & 31]
        for shift in range(55, -1, -5)
    )
    return "s-" + "-".join(encoded[index : index + 4] for index in range(0, 12, 4))


def decode_compact(value: str) -> int:
    normalized = value.strip().lower()
    if normalized.startswith("s-"):
        normalized = normalized[2:]
    encoded = normalized.replace("-", "")
    if len(encoded) != 12:
        raise ValueError(
            "compact session id must contain 12 Crockford Base32 symbols"
        )
    token = 0
    for character in encoded:
        try:
            digit = CROCKFORD_DECODE[character]
        except KeyError as exc:
            raise ValueError(f"invalid Crockford Base32 symbol: {character}") from exc
        token = (token << 5) | digit
    return token


@lru_cache(maxsize=1)
def session_words() -> tuple[str, ...]:
    path = (
        Path(__file__).resolve().parent.parent
        / "references"
        / "session-words-v1.txt.zlib.b85"
    )
    try:
        encoded = b"".join(path.read_bytes().splitlines())
        contents = zlib.decompress(base64.b85decode(encoded))
    except (OSError, ValueError, zlib.error) as exc:
        raise ValueError(f"session word list asset is unreadable: {path}") from exc
    digest = hashlib.sha256(contents).hexdigest()
    if digest != WORDLIST_SHA256:
        raise ValueError(
            f"session word list digest mismatch: {path}: {digest}"
        )
    words = tuple(contents.decode("utf-8").splitlines())
    if len(words) != 2048 or len(set(words)) != 2048:
        raise ValueError(
            f"session word list must contain 2,048 unique entries: {path}"
        )
    if any(not re.fullmatch(r"[a-z]+", word) for word in words):
        raise ValueError(
            f"session word list must contain lowercase ASCII words: {path}"
        )
    if len({word[:4] for word in words}) != 2048:
        raise ValueError(
            "session word list entries must have unique four-letter prefixes: "
            f"{path}"
        )
    return words


@lru_cache(maxsize=1)
def _word_indices() -> dict[str, int]:
    return {word: index for index, word in enumerate(session_words())}


def speakable_id(token: int) -> str:
    if not 0 <= token <= ALIAS_MASK:
        raise ValueError("speakable session token must contain exactly 60 bits")
    word_value = token >> NUMBER_BITS
    indices = [
        (word_value >> (WORD_BITS * shift)) & ((1 << WORD_BITS) - 1)
        for shift in range(WORD_COUNT - 1, -1, -1)
    ]
    number = token & ((1 << NUMBER_BITS) - 1)
    return "-".join(
        [*(session_words()[index] for index in indices), f"{number:05d}"]
    )


def decode_speakable(value: str) -> int:
    parts = value.strip().lower().split("-")
    if len(parts) != WORD_COUNT + 1 or not re.fullmatch(r"\d{5}", parts[-1]):
        raise ValueError(
            "speakable session id must be four words and five decimal digits"
        )
    number = int(parts[-1])
    if number >= (1 << NUMBER_BITS):
        raise ValueError("speakable session number must be between 00000 and 65535")
    word_value = 0
    indices = _word_indices()
    for word in parts[:-1]:
        try:
            index = indices[word]
        except KeyError as exc:
            raise ValueError(f"unknown speakable session word: {word}") from exc
        word_value = (word_value << WORD_BITS) | index
    return (word_value << NUMBER_BITS) | number


def identity_from_uuid(
    session_uuid: str | uuid.UUID, legacy_id: str = ""
) -> SessionIdentity:
    value = (
        session_uuid
        if isinstance(session_uuid, uuid.UUID)
        else uuid.UUID(session_uuid)
    )
    token = alias_token(value)
    return SessionIdentity(
        str(value), compact_id(token), speakable_id(token), legacy_id.strip()
    )


def new_identity(
    existing: Iterable[SessionIdentity] = (), *, legacy_id: str = ""
) -> SessionIdentity:
    occupied = {
        key for identity in existing for key in identity_lookup_keys(identity)
    }
    if legacy_id and selector_keys(legacy_id) & occupied:
        raise ValueError(f"legacy session alias is already in use: {legacy_id}")
    for _ in range(128):
        candidate = identity_from_uuid(uuid7(), legacy_id=legacy_id)
        if not (identity_lookup_keys(candidate) & occupied):
            return candidate
    raise RuntimeError("could not allocate a collision-free session identity")


def validate_identity(identity: SessionIdentity) -> list[str]:
    issues: list[str] = []
    try:
        expected = identity_from_uuid(identity.session_uuid, identity.legacy_id)
    except (ValueError, OSError) as exc:
        return [str(exc)]
    if identity.compact_id != expected.compact_id:
        issues.append(
            f"compact id {identity.compact_id!r} does not derive from {identity.session_uuid}"
        )
    if identity.speakable_id != expected.speakable_id:
        issues.append(
            f"speakable id {identity.speakable_id!r} does not derive from {identity.session_uuid}"
        )
    try:
        if decode_compact(identity.compact_id) != decode_speakable(
            identity.speakable_id
        ):
            issues.append("compact and speakable ids encode different tokens")
    except ValueError as exc:
        issues.append(str(exc))
    return issues


_VERSION_DIR = re.compile(r"^\d+(?:\.\d+)+$")


def _version_key(name: str) -> tuple[int, ...]:
    return tuple(int(part) for part in name.split("."))


def newer_installed_engine(script_path: Path | str) -> tuple[str, str, Path] | None:
    """(running version, newest installed version, newest script path) when the
    running script lives in a versioned plugin cache and a newer sibling
    version carries the same script; None otherwise."""
    script = Path(script_path).resolve()
    version_dir = next(
        (
            parent
            for parent in script.parents
            if _VERSION_DIR.match(parent.name) and (parent / "skills").is_dir()
        ),
        None,
    )
    if version_dir is None:
        return None
    relative = script.relative_to(version_dir)
    siblings = [
        candidate
        for candidate in version_dir.parent.iterdir()
        if _VERSION_DIR.match(candidate.name) and (candidate / relative).is_file()
    ]
    newest = max(siblings, key=lambda candidate: _version_key(candidate.name))
    if _version_key(newest.name) > _version_key(version_dir.name):
        return version_dir.name, newest.name, newest / relative
    return None


def engine_remedy(script_path: Path | str) -> str:
    """Name the engine a stale script should hand off to.

    A board written by a newer plugin than the one a session runs is the one
    parse failure no change to the running engine can repair; the remedy is
    always to invoke the current engine. When the running script lives in a
    versioned plugin cache (``<plugin>/<version>/skills/...``) the newest
    sibling version's copy of the same script is named outright — compared
    numerically, so 4.78.0 outranks 4.9.0 — otherwise the caller is told to
    refresh the installed plugin.
    """
    script = Path(script_path).resolve()
    version_dir = next(
        (
            parent
            for parent in script.parents
            if _VERSION_DIR.match(parent.name) and (parent / "skills").is_dir()
        ),
        None,
    )
    if version_dir is None:
        return (
            f"this engine ({script}) is not from a versioned plugin cache; "
            "update it to the current plugin release and rerun"
        )
    relative = script.relative_to(version_dir)
    siblings = [
        candidate
        for candidate in version_dir.parent.iterdir()
        if _VERSION_DIR.match(candidate.name) and (candidate / relative).is_file()
    ]
    newest = max(siblings, key=lambda candidate: _version_key(candidate.name))
    if _version_key(newest.name) > _version_key(version_dir.name):
        return (
            f"this engine is {version_dir.name} but {newest.name} is installed; "
            f"run {newest / relative}"
        )
    return (
        f"this engine ({version_dir.name}) is the newest installed; refresh the "
        "plugin (release.py --install-only, or the client's plugin update) "
        "and rerun"
    )


def column_count_error(cells: list[str], script_path: Path | str) -> ValueError:
    """The row-width failure, diagnosed instead of merely reported.

    A row wider than the newest column set this engine knows can only have
    been written by a newer engine, so the message names the engine to run;
    a narrower unknown width is a malformed row and says so.
    """
    head = (
        f"active-session row has {len(cells)} columns; expected "
        f"{len(V4_COLUMNS)}, {len(V3_COLUMNS)}, {len(V2_COLUMNS)}, or "
        f"{len(V1_COLUMNS)}"
    )
    if len(cells) > len(V4_COLUMNS):
        return ValueError(
            f"{head}. A wider row than this engine knows means the board was "
            f"written by a newer engine: {engine_remedy(script_path)}"
        )
    return ValueError(
        f"{head}. A narrower unknown width is a malformed row (hand edit?): "
        "repair it or restore the board from its lease remote"
    )


def parse_table_rows(text: str) -> list[dict[str, str]]:
    """Parse v1-v3 active-session rows without mutating legacy boards."""
    result: list[dict[str, str]] = []
    in_table = False
    for line in text.splitlines():
        if line.strip() == "## Active sessions":
            in_table = True
            continue
        if in_table and line.startswith("## "):
            break
        if not in_table or not line.startswith("|"):
            continue
        cells = [_plain(value) for value in line.split("|")[1:-1]]
        if not cells or set(cells[0]) == {"-"} or cells[0] in {
            "id",
            "session uuid",
        }:
            continue
        if len(cells) == len(V4_COLUMNS):
            result.append(dict(zip(V4_COLUMNS, cells)))
        elif len(cells) == len(V3_COLUMNS):
            result.append(dict(zip(V3_COLUMNS, cells)))
        elif len(cells) == len(V2_COLUMNS):
            result.append(dict(zip(V2_COLUMNS, cells)))
        elif len(cells) == len(V1_COLUMNS):
            result.append(dict(zip(V1_COLUMNS, cells)))
        else:
            raise column_count_error(
                cells, Path(__file__).with_name("coordination.py")
            )
    return result


def row_identity(row: dict[str, str]) -> SessionIdentity:
    if "session uuid" in row:
        return SessionIdentity(
            row["session uuid"],
            row["compact id"],
            row["speakable id v1"],
            row["legacy id"],
        )
    return SessionIdentity("", "", "", row.get("id", ""))


def selector_matches(identity: SessionIdentity, selector: str) -> bool:
    return bool(identity_lookup_keys(identity) & selector_keys(selector))


def selector_keys(selector: str) -> set[tuple[str, object]]:
    candidate = selector.strip()
    if not candidate:
        return set()
    try:
        parsed_uuid = uuid.UUID(candidate)
    except ValueError:
        parsed_uuid = None
    if parsed_uuid is not None:
        return {("uuid", str(parsed_uuid))}
    try:
        return {("token", decode_compact(candidate))}
    except ValueError:
        pass
    try:
        return {("token", decode_speakable(candidate))}
    except ValueError:
        pass
    return {("legacy", candidate.casefold())}


def identity_lookup_keys(identity: SessionIdentity) -> set[tuple[str, object]]:
    return {
        key
        for selector in identity.selectors()
        for key in selector_keys(selector)
    }


def display_id(identity: SessionIdentity) -> str:
    if identity.compact_id:
        return identity.compact_id
    return identity.legacy_id or identity.session_uuid or "unknown-session"

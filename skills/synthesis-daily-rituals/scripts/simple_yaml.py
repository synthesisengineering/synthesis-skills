"""Read the YAML the ritual manifests use, with the Python standard library only.

The ritual scripts read `.agents/repos.yaml`, `.agents/mailboxes.yaml`,
`.agents/gchat-sync.yaml`, `projects/index.yaml` and the workers registry.
Apple's /usr/bin/python3 has no PyYAML, and a script that skips itself when an
import fails reports an unscanned queue as an empty one. So this reads the
subset those files use, the same way on every interpreter: block mappings and
sequences, `- key: value` items, flow lists of scalars, `{}` and `[]`, quoted
and plain scalars (plain ones may continue on more-indented lines), `|` and `>`
block scalars, and comments. Booleans and nulls follow YAML 1.1 as PyYAML reads
them, so `ritual_sync: no` is False. Dates stay strings. Anything else (anchors,
aliases, tags, flow mappings, tabs, duplicate keys) raises ValueError: a manifest
this cannot read is refused, never half-read.

    from simple_yaml import load
    data = load(path.read_text(encoding="utf-8"))
"""

from __future__ import annotations

import json
import re

_WORDS = {"true": True, "yes": True, "on": True, "false": False, "no": False, "off": False,
          "null": None, "~": None}
_INT = re.compile(r"[-+]?(?:0|[1-9][0-9_]*)\Z")
_FLOAT = re.compile(r"[-+]?(?:\d+\.\d*|\.\d+)(?:[eE][-+]?\d+)?\Z")
_BLOCK = {"|", "|-", "|+", ">", ">-", ">+"}


def _strip_comment(text: str) -> str:
    quote = None
    for i, ch in enumerate(text):
        if quote:
            if ch == "\\" and quote == '"':
                continue
            if ch == quote and not (quote == '"' and text[i - 1] == "\\"):
                quote = None
        elif ch in "'\"" and (i == 0 or text[i - 1] in " [,{:-"):
            quote = ch
        elif ch == "#" and (i == 0 or text[i - 1] in " \t"):
            return text[:i].rstrip()
    return text.rstrip()


def _split_flow(inner: str) -> list[str]:
    parts, quote, start = [], None, 0
    for i, ch in enumerate(inner):
        if quote:
            quote = None if ch == quote else quote
        elif ch in "'\"":
            quote = ch
        elif ch in "[{":
            raise ValueError(f"nested flow collections are not supported: [{inner}]")
        elif ch == ",":
            parts.append(inner[start:i])
            start = i + 1
    return parts + [inner[start:]]


def scalar(raw: str):
    raw = raw.strip()
    if raw[:1] in ("&", "*", "!", "@", "`", "%") or raw[:1] == "{" and raw != "{}":
        raise ValueError(f"unsupported YAML (anchor, alias, tag or flow mapping): {raw}")
    if raw[:1] == '"':
        if len(raw) < 2 or not raw.endswith('"'):
            raise ValueError(f"unterminated double-quoted string: {raw}")
        return json.loads(raw)
    if raw[:1] == "'":
        if len(raw) < 2 or not raw.endswith("'"):
            raise ValueError(f"unterminated single-quoted string: {raw}")
        return raw[1:-1].replace("''", "'")
    if raw[:1] == "[":
        if not raw.endswith("]"):
            raise ValueError(f"multi-line flow lists are not supported: {raw}")
        inner = raw[1:-1].strip()
        return [scalar(part) for part in _split_flow(inner)] if inner else []
    if raw == "{}":
        return {}
    if raw == "" or raw in ("null", "Null", "NULL", "~"):
        return None
    if raw.lower() in _WORDS and raw in (raw.lower(), raw.capitalize(), raw.upper()):
        return _WORDS[raw.lower()]
    if _INT.match(raw):
        return int(raw.replace("_", ""))
    if _FLOAT.match(raw):
        return float(raw)
    return raw


def _quote_end(text: str):
    """Index of the quote closing the scalar `text` opens, or None if it stays open."""
    i = 1
    while i < len(text):
        if text[0] == '"' and text[i] == "\\":
            i += 2
            continue
        if text[i] == text[0]:
            if text[0] == "'" and text[i + 1:i + 2] == "'":
                i += 2
                continue
            return i
        i += 1
    return None


def _split_key(text: str):
    """(key, rest) when `text` is `key: value` or `key:`, else None."""
    if text[:1] in ("'", '"'):
        end = _quote_end(text)
        if end is None or text[end + 1:end + 2] != ":" or text[end + 2:end + 3] not in ("", " "):
            return None
        return scalar(text[:end + 1]), text[end + 2:].strip()
    if text[:1] in ("[", "{"):
        return None
    for i, ch in enumerate(text):
        if ch == ":" and (i + 1 == len(text) or text[i + 1] == " "):
            return text[:i].strip(), text[i + 1:].strip()
    return None


def _fold(lines: list[str]) -> str:
    """YAML line folding: a break between two plain lines becomes a space, an
    empty line a newline, and breaks around more-indented lines are kept."""
    text, prev, last = "", None, None
    for line in lines:
        if not line:
            text, prev = text + "\n", "blank"
            continue
        kind = "more" if line[0] == " " else "plain"
        if prev == "blank":
            text += "\n" if "more" in (kind, last) else ""
        elif prev is not None:
            text += " " if kind == prev == "plain" else "\n"
        text, prev, last = text + line, kind, kind
    return text


def _dash(text: str) -> bool:
    return text == "-" or text.startswith("- ")


class _Reader:
    def __init__(self, text: str):
        self.lines = text.splitlines()
        self.i = 0

    def peek(self):
        while self.i < len(self.lines):
            raw = self.lines[self.i]
            lead = raw[: len(raw) - len(raw.lstrip())]
            if "\t" in lead:
                raise ValueError(f"line {self.i + 1}: tab indentation")
            body = _strip_comment(raw)
            if not body.strip() or body in ("---", "..."):
                self.i += 1
                continue
            return len(body) - len(body.lstrip(" ")), body.strip()
        return None

    def node(self, indent: int, indentless: bool = False):
        nxt = self.peek()
        if nxt is None or nxt[0] < indent or (nxt[0] == indent and not (indentless and _dash(nxt[1]))):
            return None
        return self.sequence(nxt[0]) if _dash(nxt[1]) else self.mapping(nxt[0])

    def sequence(self, indent: int) -> list:
        out = []
        while True:
            nxt = self.peek()
            if nxt is None or nxt[0] < indent or not _dash(nxt[1]):
                return out
            if nxt[0] > indent:
                raise ValueError(f"line {self.i + 1}: unexpected indentation")
            self.i += 1
            rest = nxt[1][1:].lstrip()
            if not rest:
                out.append(self.node(indent + 1))
            elif _split_key(rest) is not None:
                out.append(self.mapping(indent + len(nxt[1]) - len(rest), first=rest))
            else:
                out.append(self.value(rest, indent))

    def mapping(self, indent: int, first: str | None = None) -> dict:
        out: dict = {}
        while True:
            if first is None:
                nxt = self.peek()
                if nxt is None or nxt[0] < indent or (nxt[0] == indent and _dash(nxt[1])):
                    return out
                if nxt[0] > indent:
                    raise ValueError(f"line {self.i + 1}: unexpected indentation")
                self.i += 1
                text = nxt[1]
            else:
                text, first = first, None
            pair = _split_key(text)
            if pair is None:
                raise ValueError(f"line {self.i}: expected `key: value`, found {text!r}")
            key, rest = pair
            if key in out:
                raise ValueError(f"line {self.i}: duplicate key {key!r}")
            out[key] = self.value(rest, indent) if rest else self.node(indent, indentless=True)

    def value(self, rest: str, indent: int):
        if rest in _BLOCK:
            return self.block_scalar(rest, indent)
        if rest[:1] in ("'", '"') and _quote_end(rest) is None:
            pieces = [rest]  # a quoted scalar folds its line breaks
            while self.i < len(self.lines) and _quote_end(_fold(pieces)) is None:
                pieces.append(self.lines[self.i].strip())
                self.i += 1
            return scalar(_strip_comment(_fold(pieces)))
        result = scalar(rest)
        if isinstance(result, str) and rest[:1] not in ("'", '"'):
            while True:  # a plain scalar may continue on more-indented lines
                nxt = self.peek()
                if nxt is None or nxt[0] <= indent:
                    return result
                result += " " + nxt[1]
                self.i += 1
        return result

    def block_scalar(self, style: str, indent: int) -> str:
        body, width = [], None
        while self.i < len(self.lines):
            raw = self.lines[self.i]
            depth = len(raw) - len(raw.lstrip(" "))
            if raw.strip() and (depth <= indent or (width is not None and depth < width)):
                break
            if raw.strip() and width is None:
                width = depth
            body.append(raw[width:] if raw.strip() else "")
            self.i += 1
        while body and body[-1] == "":
            body.pop()
        text = "\n".join(body) if style[0] == "|" else _fold(body)
        return text if style.endswith("-") or not text else text + "\n"


def load(text: str):
    """Parse one YAML document of the supported subset."""
    reader = _Reader(text)
    nxt = reader.peek()
    if nxt is None:
        return None
    if _dash(nxt[1]):
        result = reader.sequence(nxt[0])
    elif _split_key(nxt[1]) is not None:
        result = reader.mapping(nxt[0])
    else:
        reader.i += 1
        result = reader.value(nxt[1], -1)
    if reader.peek() is not None:
        raise ValueError(f"line {reader.i + 1}: content after the document ends")
    return result

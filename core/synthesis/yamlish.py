"""The plugin's one YAML reader, with the Python standard library only.

Apple's /usr/bin/python3 has no PyYAML, a guard once failed open over a missing
YAML module, and a script that skips itself when an import fails reports an
unscanned queue as an empty one. So every YAML file synthesis and its skills read
(the commit policy and ledger, `.agents/*.yaml` manifests, `projects/index.yaml`,
sync configs, inbox rules, knowledge-base frontmatter) goes through this, the same
way on every interpreter. It reads the subset those files use: block mappings and
sequences, `- key: value` items, one-line flow collections (`- {a: {b: c}, d: [e]}`),
quoted and plain scalars (plain ones may continue on more-indented lines), `|` and
`>` block scalars, and comments. Booleans and nulls follow YAML 1.1 as PyYAML reads
them, so `ritual_sync: no` is False. Dates stay strings; keys are text. Anything else
(anchors, aliases, tags, multi-line flow, tabs, duplicate keys) raises ValueError:
a file this cannot read is refused, never half-read.

    from synthesis.yamlish import load, load_mapping
    data = load(path.read_text(encoding="utf-8"), source=str(path))

`strict=True` is the commit check's narrower subset for its policy and ledger:
nested mappings, lists of scalars, `[]` and one-line scalars, with double-quoted
text kept literal (only `\\"` and `\\\\` decode), because decoding escapes would turn
a regex's `\\b` into a backspace. Everything else, a tab anywhere included, is refused.
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


def _skip(text: str, i: int) -> int:
    return len(text) - len(text[i:].lstrip(" "))


def _flow_item(text: str, i: int):
    """(value, index after it) for the flow node at text[i]: a collection, a quoted or a plain scalar."""
    if text[i:i + 1] in ("[", "{"):
        return _flow(text, i)
    if text[i:i + 1] in ("'", '"'):
        end = i + (_quote_end(text[i:]) or len(text)) + 1
        return scalar(text[i:end]), end
    j = i  # a plain scalar ends at , [ ] { } or at a colon before a space, , ] } or the line's end
    while j < len(text) and text[j] not in ",[]{}" and not (text[j] == ":" and text[j + 1:j + 2] in ("", " ", ",", "]", "}")):
        j += 1
    return (scalar(text[i:j]) if text[i:j].strip() else None), j


def _flow(text: str, i: int):
    """(collection, index after it) for the flow collection opening at text[i]; it closes on its line."""
    out, close = ({}, "}") if text[i] == "{" else ([], "]")
    i = _skip(text, i + 1)
    while i == len(text) or text[i] != close:
        if i == len(text):
            raise ValueError(f"unterminated flow collection (one line only): {text}")
        start, (item, i) = i, _flow_item(text, i)
        i = _skip(text, i)
        if isinstance(out, dict):  # keys are text, as in a block mapping
            key = item if text[start] in "'\"" else text[start:i].strip()
            if text[i:i + 1] != ":" or isinstance(item, (dict, list)) or not key or key in out:
                raise ValueError(f"a flow mapping holds `key: value` pairs with unique text keys: {text}")
            out[key], i = _flow_item(text, _skip(text, i + 1))
            i = _skip(text, i)
        else:
            out.append(item)
        if text[i:i + 1] == ",":
            i = _skip(text, i + 1)
        elif i < len(text) and text[i] != close:
            raise ValueError(f"expected ',' or {close!r} in a flow collection: {text}")
    return out, i + 1


def scalar(raw: str, strict: bool = False):
    raw = raw.strip()
    if raw[:1] in ("&", "*", "!", "@", "`", "%"):
        raise ValueError(f"unsupported YAML (anchor, alias or tag): {raw}")
    if raw[:1] in ("|", ">"):  # a block scalar with an indentation indicator, such as |2
        raise ValueError(f"unsupported block scalar header: {raw}")
    if raw[:1] == '"':
        if len(raw) < 2 or not raw.endswith('"'):
            raise ValueError(f"unterminated double-quoted string: {raw}")
        if strict:  # literal: a regex's \b stays a backslash and a b
            return raw[1:-1].replace('\\"', '"').replace("\\\\", "\\")
        return json.loads(raw)
    if raw[:1] == "'":
        if len(raw) < 2 or not raw.endswith("'"):
            raise ValueError(f"unterminated single-quoted string: {raw}")
        return raw[1:-1].replace("''", "'")
    if raw[:1] in ("[", "{"):
        value, end = _flow(raw, 0)
        if raw[end:].strip():
            raise ValueError(f"content after a flow collection: {raw}")
        return value
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


def _split_key(text: str, strict: bool = False):
    """(key, rest) when `text` is `key: value` or `key:`, else None."""
    if text[:1] in ("'", '"'):
        end = _quote_end(text)
        if end is None or text[end + 1:end + 2] != ":" or text[end + 2:end + 3] not in ("", " "):
            return None
        return scalar(text[:end + 1], strict), text[end + 2:].strip()
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
    def __init__(self, text: str, strict: bool):
        self.lines = text.splitlines()
        self.i = 0
        self.strict = strict

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
            if self.strict and (not rest or _split_key(rest, True) is not None):
                raise ValueError(f"line {self.i}: nested lists and mappings inside lists are outside the supported subset")
            if not rest:
                out.append(self.node(indent + 1))
            elif _split_key(rest, self.strict) is not None:
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
            pair = _split_key(text, self.strict)
            if pair is None:
                raise ValueError(f"line {self.i}: expected `key: value`, found {text!r}")
            key, rest = pair
            if key in out:
                raise ValueError(f"line {self.i}: duplicate key {key!r}")
            out[key] = self.value(rest, indent) if rest else self.node(indent, indentless=True)

    def value(self, rest: str, indent: int):
        if self.strict and (rest in _BLOCK or rest[:1] in ("[", "{") and not re.fullmatch(r"\[ *\]", rest)):
            raise ValueError(f"line {self.i}: {rest[:20]!r} is outside the supported subset")
        if rest in _BLOCK:
            return self.block_scalar(rest, indent)
        if rest[:1] in ("'", '"') and _quote_end(rest) is None:
            if self.strict:
                raise ValueError(f"line {self.i}: unterminated quoted string")
            pieces = [rest]  # a quoted scalar folds its line breaks
            while self.i < len(self.lines) and _quote_end(_fold(pieces)) is None:
                pieces.append(self.lines[self.i].strip())
                self.i += 1
            return scalar(_strip_comment(_fold(pieces)), self.strict)
        result = scalar(rest, self.strict)
        if isinstance(result, str) and rest[:1] not in ("'", '"'):
            while True:  # a plain scalar may continue on more-indented lines
                nxt = self.peek()
                if nxt is None or nxt[0] <= indent:
                    return result
                if self.strict:
                    raise ValueError(f"line {self.i + 1}: unexpected indentation")
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


def _document(text: str, strict: bool):
    if strict and "\t" in text:  # the strict subset refuses a tab anywhere, not only in indentation
        line = text.count("\n", 0, text.index("\t")) + 1
        raise ValueError(f"line {line}: a tab character; indent with spaces")
    reader = _Reader(text, strict)
    nxt = reader.peek()
    if nxt is None:
        return None
    if _dash(nxt[1]):
        result = reader.sequence(nxt[0])
    elif _split_key(nxt[1], strict) is not None:
        result = reader.mapping(nxt[0])
    else:
        reader.i += 1
        result = reader.value(nxt[1], -1)
    if reader.peek() is not None:
        raise ValueError(f"line {reader.i + 1}: content after the document ends")
    return result


def load(text: str, source: str = "", strict: bool = False):
    """Parse one YAML document of the supported subset; `source` prefixes any error."""
    try:
        return _document(text, strict)
    except ValueError as exc:
        if not source:
            raise
        raise ValueError(f"{source}: {exc}") from None


def load_mapping(text: str, source: str = "", strict: bool = False) -> dict:
    """A document that must be a mapping at the top; an empty document is {}."""
    data = load(text, source, strict)
    if data is not None and not isinstance(data, dict):
        raise ValueError(f"{source or 'the document'}: expected a mapping at the top, found a {type(data).__name__}")
    return data or {}

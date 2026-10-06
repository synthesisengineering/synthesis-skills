"""A dependency-free reader for the YAML subset synthesis files use.

Apple's Python 3.9 has no PyYAML, and a guard once failed open over a missing
YAML module, so organization manifests and workspace `repos.yaml` files are
read with this instead. Supported: nested maps, lists of scalars or maps
(`- key: value`), scalars (quoted, true/false/yes/no, null/~, integers),
one-line flow lists (`[a, b]`), literal blocks (`|`) and full-line comments.
Anything outside the subset raises ValueError with a line number: it fails
closed rather than guessing.

    from yaml_subset import load
    data = load(text, source="repos.yaml")
"""

from __future__ import annotations

import re


def scalar(token: str):
    token = token.strip()
    if len(token) >= 2 and token[0] == token[-1] and token[0] in "\"'":
        return token[1:-1]
    if token.startswith("[") and token.endswith("]"):
        inner = token[1:-1].strip()
        return [scalar(part) for part in inner.split(",")] if inner else []
    lowered = token.lower()
    if lowered in ("true", "yes"):
        return True
    if lowered in ("false", "no"):
        return False
    if lowered in ("null", "~", ""):
        return None
    if re.fullmatch(r"-?\d+", token):
        return int(token)
    return token


def _strip_scalar(value: str):
    return scalar(_strip_comment(value.strip()))


def _strip_comment(value: str) -> str:
    """Drop a trailing ` # comment` outside quotes."""
    quote = None
    for i, c in enumerate(value):
        if quote:
            quote = None if c == quote else quote
        elif c in "\"'":
            quote = c
        elif c == "#" and (i == 0 or value[i - 1] in " \t"):
            return value[:i].rstrip()
    return value


def _items(text: str, source: str) -> list:
    """(indent, kind, payload, line) for each meaningful line: kv, key, item, item_map."""
    lines, items, index = text.splitlines(), [], 0
    while index < len(lines):
        raw, lineno = lines[index], index + 1
        index += 1
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "\t" in raw[: len(raw) - len(raw.lstrip())]:
            raise ValueError(f"{source}:{lineno}: tabs are not allowed in indentation")
        indent = len(raw) - len(raw.lstrip(" "))
        if stripped.startswith("- ") or stripped == "-":
            body = _strip_comment(stripped[2:])
            key = body.split(":", 1)[0].strip()
            is_map = ((": " in body or body.endswith(":")) and re.fullmatch(r"[A-Za-z0-9_-]+", key)
                      and not body.startswith(("'", '"')))
            items.append((indent, "item_map" if is_map else "item", body, lineno))
            continue
        if ":" not in stripped:
            raise ValueError(f"{source}:{lineno}: expected 'key: value', got {stripped!r}")
        key, _, rest = stripped.partition(":")
        rest = _strip_comment(rest.strip())
        if rest == "|":
            block, block_indent = [], None
            while index < len(lines):
                nxt = lines[index]
                if nxt.strip() and len(nxt) - len(nxt.lstrip(" ")) <= indent:
                    break
                if nxt.strip() and block_indent is None:
                    block_indent = len(nxt) - len(nxt.lstrip(" "))
                block.append(nxt[block_indent or 0:] if nxt.strip() else "")
                index += 1
            while block and not block[-1]:
                block.pop()
            items.append((indent, "kv", (key.strip(), "\n".join(block) + "\n"), lineno))
        elif rest:
            items.append((indent, "kv", (key.strip(), scalar(rest)), lineno))
        else:
            items.append((indent, "key", key.strip(), lineno))
    return items


def load(text: str, source: str = "yaml"):
    items = _items(text, source)

    def block_end(pos: int, end: int, indent: int) -> int:
        stop = pos + 1
        while stop < end and items[stop][0] > indent:
            stop += 1
        return stop

    def build(start: int, end: int, indent: int):
        if start >= end:
            return {}
        if items[start][1] in ("item", "item_map"):
            result, pos = [], start
            while pos < end:
                item_indent, kind, payload, lineno = items[pos]
                if item_indent != indent or kind not in ("item", "item_map"):
                    raise ValueError(f"{source}:{lineno}: inconsistent list indentation")
                stop = block_end(pos, end, indent)
                if kind == "item":
                    if stop > pos + 1:
                        raise ValueError(f"{source}:{lineno}: a scalar list item cannot have a nested block")
                    result.append(scalar(payload))
                else:
                    key, _, rest = payload.partition(":")
                    if not rest.strip() and stop > pos + 1:
                        raise ValueError(f"{source}:{lineno}: '- key:' with a nested block is outside the subset; "
                                         "start the item with a '- key: value' pair")
                    entry = {key.strip(): _strip_scalar(rest)}
                    child = build(pos + 1, stop, items[pos + 1][0]) if stop > pos + 1 else {}
                    if not isinstance(child, dict) or set(child) & set(entry):
                        raise ValueError(f"{source}:{lineno}: list items must be scalars or maps without repeated keys")
                    entry.update(child)
                    result.append(entry)
                pos = stop
            return result
        result, pos = {}, start
        while pos < end:
            item_indent, kind, payload, lineno = items[pos]
            if item_indent != indent:
                raise ValueError(f"{source}:{lineno}: inconsistent map indentation")
            if kind in ("item", "item_map"):
                raise ValueError(f"{source}:{lineno}: list item where a key was expected")
            key = payload[0] if kind == "kv" else payload
            if key in result:
                raise ValueError(f"{source}:{lineno}: duplicate key {key!r}")
            stop = block_end(pos, end, indent)
            if kind == "kv":
                if stop > pos + 1:
                    raise ValueError(f"{source}:{lineno}: a value cannot also have a nested block")
                result[key] = payload[1]
            else:
                result[key] = build(pos + 1, stop, items[pos + 1][0]) if stop > pos + 1 else None
            pos = stop
        return result

    return build(0, len(items), items[0][0] if items else 0)

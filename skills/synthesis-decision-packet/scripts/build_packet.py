#!/usr/bin/env python3
"""Build a self-contained decision-packet HTML page from a JSON spec.

A decision packet collects many parallel decisions from a principal in one sitting and
emits a paste-able summary of them. The origin run: 26 rounds of per-item conversation
produced 0 of 30 decisions. One packet produced 30 of 30, in one pass, in one paste.

    python3 build_packet.py --schema                     # print the spec format
    python3 build_packet.py spec.json -o packet.html --strict-reader
    python3 build_packet.py spec.json --stdout > packet.html
    python3 build_packet.py spec.json --strict-reader --file-into PROJECT/resources/artifacts/

--file-into files a dated copy of the spec and the page in the owning project, where every
agent on the project can read them; record_rulings.py files the principal's paste beside
them. The page template is ../assets/packet-template.html and the schema text
../assets/spec-schema.txt. Stdlib only: the page opens from disk, from a local HTTP server
or as a published artifact, with no build step, dependency or server.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import datetime
import hashlib
import html
import json
import pathlib
import re
import sys
import urllib.parse

ASSETS = pathlib.Path(__file__).resolve().parents[1] / "assets"
TONES = {"danger", "warn", "ok", "muted", "info"}
SEVERITIES = {"high", "medium", "low", "none"}
MAX_SPEC_BYTES = MAX_HTML_BYTES = 8_388_608  # the page ceiling the context doctor has always read
# Option labels must say what pressing the button DOES. Fixture of the failure, 2026-09-14:
# on a 9-row packet, three rows offering {"Yes, do that", "No"} collected notes instead of
# decisions. Labels are compared lower-cased, punctuation stripped, whitespace collapsed.
BARE_ACKNOWLEDGEMENTS = {"yes", "no", "ok", "okay", "cancel", "accept", "decline", "approve",
                         "reject", "do it", "yes do that", "go", "stop", "no thanks"}
STOPWORDS = {"the", "a", "an", "it", "that", "this", "do", "to", "of", "in", "on", "my", "me",
             "and", "or", "not"}
ACCEPTED_LABEL_FORM = ('label each option by what pressing it does, '
                       'e.g. "Keep them on my phone" / "Take them off my phone"')
# The pasted summary is one line per field, read back one line at a time: a line break in
# a title, row label, option label or id builds a packet whose own paste is refused.
LINE_BREAK = re.compile(r"[\r\n]")
SINGLE_LINE_FORM = ("the pasted summary is one line per field, so title, row labels "
                    "and option labels must be single-line")
# Review assets are data in the spec, never paths to read or URLs to fetch.
MAX_ASSETS, MAX_TEXT_BYTES, MAX_BINARY_BYTES = 16, 1_048_576, 4_194_304
TEXT_KINDS = {"correspondence", "plain_text", "markdown", "code"}
BINARY_TYPES = {
    "image": {"image/png": (".png",), "image/jpeg": (".jpg", ".jpeg"),
              "image/gif": (".gif",), "image/webp": (".webp",)},
    "audio": {"audio/mpeg": (".mp3",), "audio/wav": (".wav",), "audio/ogg": (".ogg",)},
    "video": {"video/mp4": (".mp4",), "video/webm": (".webm",)},
    "document": {"application/pdf": (".pdf",)},
}
SIGNATURES = {
    "image/png": lambda d: d.startswith(b"\x89PNG\r\n\x1a\n") and d[12:16] == b"IHDR",
    "image/jpeg": lambda d: d.startswith(b"\xff\xd8\xff") and d.endswith(b"\xff\xd9"),
    "image/gif": lambda d: d[:6] in (b"GIF87a", b"GIF89a"),
    "image/webp": lambda d: d.startswith(b"RIFF") and d[8:12] == b"WEBP",
    "audio/wav": lambda d: d.startswith(b"RIFF") and d[8:12] == b"WAVE",
    "audio/ogg": lambda d: d.startswith(b"OggS"),
    "audio/mpeg": lambda d: d.startswith(b"ID3") or (len(d) > 1 and d[0] == 255 and d[1] & 224 == 224),
    "video/mp4": lambda d: d[4:8] == b"ftyp",
    "video/webm": lambda d: d.startswith(b"\x1a\x45\xdf\xa3"),
    "application/pdf": lambda d: d.startswith(b"%PDF-"),
}
FILENAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")


def strict_json(raw: str):
    """Parse JSON, refusing duplicate keys and nonfinite numbers instead of guessing."""
    def pairs(items):
        obj = {}
        for key, value in items:
            if key in obj:
                raise ValueError(f"duplicate JSON key: {key!r}")
            obj[key] = value
        return obj

    def constant(value):
        raise ValueError(f"nonfinite JSON number: {value}")
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


def canonical_spec_bytes(spec: dict) -> bytes:
    """The whole spec as sorted, compact UTF-8 JSON plus one LF; every field participates."""
    return (json.dumps(spec, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                       allow_nan=False) + "\n").encode("utf-8")


def spec_digest(spec: dict) -> str:
    return hashlib.sha256(canonical_spec_bytes(spec)).hexdigest()


def write_preserved(path: pathlib.Path, payload: bytes) -> None:
    """Create the file, or accept identical bytes; never replace a filed artifact."""
    try:
        with path.open("xb") as stream:
            stream.write(payload)
    except FileExistsError:
        if path.is_symlink() or not path.is_file() or path.read_bytes() != payload:
            raise ValueError(f"existing artifact differs; preserved without replacement: {path}")


def slugify(text) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-") or "packet"


def parse_iso_date(text) -> str | None:
    """YYYY-MM-DD when `text` is exactly that form and a real date, else None."""
    if not isinstance(text, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return None
    try:
        return datetime.date.fromisoformat(text).isoformat()
    except ValueError:
        return None


def normalize_label(label) -> str:
    return " ".join(re.findall(r"[^\W_]+", str(label).lower()))


def is_bare_acknowledgement(label) -> bool:
    """True when the label is an acknowledgement, alone or padded with stopwords."""
    norm = normalize_label(label)
    stripped = " ".join(w for w in norm.split() if w not in STOPWORDS)
    return norm in BARE_ACKNOWLEDGEMENTS or stripped in BARE_ACKNOWLEDGEMENTS or not stripped


def content_words(label) -> frozenset:
    return frozenset(w for w in re.findall(r"[^\W\d_]+", str(label).lower())
                     if len(w) >= 3 and w not in STOPWORDS)


def _option_set_problems(opts: list, where: str) -> list:
    """Shape checks (hard) and label checks (READER) for one option set."""
    prefix = "options" if where == "options" else f"{where} options"
    problems, labels, values = [], [], []
    if len(opts) < 2:
        problems.append(f"{prefix} must offer at least two options - a one-button set records no "
                        "decision; give the principal the alternative as a second labelled option")
    for i, o in enumerate(opts):
        if not isinstance(o, dict) or not o.get("value") or not o.get("label"):
            problems.append(f"{prefix}[{i}] needs both 'value' and 'label'")
            continue
        if not isinstance(o["value"], str) or not o["value"].strip():
            # The page keys pressed state through a DOM dataset, which stores strings only.
            problems.append(f"{prefix}[{i}].value {o['value']!r} must be a non-empty string - the button's "
                            "pressed state is keyed through a DOM dataset, which stores strings only")
            continue
        if not isinstance(o["label"], str) or not o["label"].strip():
            problems.append(f"{prefix}[{i}].label must be a non-empty string")
        elif LINE_BREAK.search(o["label"]):
            problems.append(f"{prefix}[{i}] label {o['label']!r} contains a line break - {SINGLE_LINE_FORM}")
        if "tone" in o and (not isinstance(o["tone"], str) or o["tone"] not in TONES):
            problems.append(f"{prefix}[{i}].tone {o['tone']!r} not in {sorted(TONES)}")
        if "consequence" in o and (not isinstance(o["consequence"], str) or not o["consequence"].strip()):
            problems.append(f"{prefix}[{i}].consequence must be a non-empty string")
        labels.append(str(o["label"]))
        values.append(o["value"])
    dupes = sorted({v for v in values if values.count(v) > 1})
    if dupes:  # one saved choice would press every button sharing the value
        problems.append(f"{prefix} value(s) {', '.join(map(repr, dupes))} used by more than one option - "
                        "every option in a set needs its own value because the value keys the pressed "
                        "state and the summary label")
    head = "READER: options:" if where == "options" else f"READER: {where} option"
    bare = [lab for lab in labels if is_bare_acknowledgement(lab)]
    if bare:
        problems.append(f"{head} labels {', '.join(map(repr, bare))} are bare acknowledgements that "
                        f"name no consequence - {ACCEPTED_LABEL_FORM}")
    rest = [lab for lab in labels if lab not in bare]
    pairs = [f"{a!r} / {b!r}" for i, a in enumerate(rest) for b in rest[i + 1:]
             if content_words(a) == content_words(b)]
    if pairs:
        problems.append(f"{head} labels {', '.join(pairs)} do not differ in a content word - {ACCEPTED_LABEL_FORM}")
    return problems


def _text(value, limit=4096) -> bool:
    return (isinstance(value, str) and bool(value.strip()) and len(value.encode("utf-8")) <= limit
            and not any(ord(c) < 32 and c not in "\n\r\t" for c in value))


def _https_source(value) -> bool:
    """An explicit external link the page shows but never fetches."""
    if not _text(value, 2048) or any(c.isspace() or c == "\\" for c in value):
        return False
    try:
        url = urllib.parse.urlsplit(value)
        return (url.scheme == "https" and bool(url.hostname) and url.username is None
                and url.password is None and url.port in (None, 443))
    except ValueError:
        return False


def _scheme(href: str) -> str:
    try:
        return urllib.parse.urlsplit(href).scheme.lower()
    except ValueError:
        return "invalid"


def _image_size(media: str, d: bytes) -> tuple:
    """Raster dimensions from a bounded header, so a small file cannot claim a huge image."""
    if media == "image/png" and len(d) >= 24:
        return int.from_bytes(d[16:20], "big"), int.from_bytes(d[20:24], "big")
    if media == "image/gif" and len(d) >= 10:
        return int.from_bytes(d[6:8], "little"), int.from_bytes(d[8:10], "little")
    if media == "image/webp" and len(d) >= 30:
        if d[12:16] == b"VP8X":
            return 1 + int.from_bytes(d[24:27], "little"), 1 + int.from_bytes(d[27:30], "little")
        if d[12:16] == b"VP8 " and d[23:26] == b"\x9d\x01\x2a":
            return int.from_bytes(d[26:28], "little") & 0x3FFF, int.from_bytes(d[28:30], "little") & 0x3FFF
        if d[12:16] == b"VP8L" and d[20] == 0x2F:
            bits = int.from_bytes(d[21:25], "little")
            return 1 + (bits & 0x3FFF), 1 + ((bits >> 14) & 0x3FFF)
    if media == "image/jpeg":  # walk segments to a start-of-frame marker within 128 KiB
        at, end = 2, min(len(d), 131072)
        while at + 4 <= end and d[at] == 0xFF:
            while at < end and d[at] == 0xFF:
                at += 1
            if at + 3 > end:
                break
            marker, length = d[at], int.from_bytes(d[at + 1:at + 3], "big")
            if length < 2 or at + 1 + length > end:
                break
            if length >= 7 and marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
                return int.from_bytes(d[at + 6:at + 8], "big"), int.from_bytes(d[at + 4:at + 6], "big")
            at += 1 + length
    return 0, 0


def review_assets_ready(row: dict) -> bool:
    """False when any asset is unavailable: such a row takes notes but no choice."""
    return all("unavailable" not in a["content"] for a in row.get("review_assets", []))


def _review_problems(row: dict, where: str) -> tuple:
    """Check a row's review_assets, revision and delivery; return (problems, decoded bytes)."""
    if "review_assets" not in row:
        return ([f"{where} delivery/revision requires review_assets"]
                if "delivery" in row or "revision" in row else []), 0
    assets, problems, total, seen = row["review_assets"], [], 0, set()
    if not isinstance(assets, list) or not 1 <= len(assets) <= MAX_ASSETS:
        return [f"{where} review_assets needs 1..{MAX_ASSETS} typed assets"], 0
    if not _text(row.get("revision"), 256):
        problems.append(f"{where} review_assets requires a nonempty revision")
    delivery = row.get("delivery")
    if not (isinstance(delivery, dict) and set(delivery) == {"format", "destinations", "attachments"}
            and _text(delivery["format"], 256) and isinstance(delivery["destinations"], list)
            and len(delivery["destinations"]) <= 64 and all(_text(v, 2048) for v in delivery["destinations"])
            and isinstance(delivery["attachments"], list)):
        problems.append(f"{where} review_assets requires exact delivery format/destinations/attachments")
        delivery = None
    for index, asset in enumerate(assets):
        at = f"{where} review_assets[{index}]"
        if not isinstance(asset, dict) or set(asset) - {"id", "title", "kind", "content", "description", "filename"}:
            problems.append(f"{at} has unknown fields or is not an object")
            continue
        aid, kind, content = asset.get("id"), asset.get("kind"), asset.get("content")
        if not isinstance(aid, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", aid) or aid in seen:
            problems.append(f"{at} requires a unique bounded ASCII id")
        seen.add(aid if isinstance(aid, str) else None)
        if not _text(asset.get("title"), 512):
            problems.append(f"{at} requires a title")
        if not isinstance(kind, str) or (kind not in TEXT_KINDS and kind not in BINARY_TYPES):
            problems.append(f"{at} has an unsupported kind")
            continue
        if "description" in asset and not _text(asset["description"]):
            problems.append(f"{at} description is invalid")
        if kind in BINARY_TYPES and not _text(asset.get("description")):
            problems.append(f"{at} requires an accessible description")
        if not isinstance(content, dict):
            problems.append(f"{at} content must be an object")
            continue
        if "unavailable" in content:
            if (set(content) - {"unavailable", "source"} or not _text(content["unavailable"])
                    or ("source" in content and not _https_source(content["source"]))):
                problems.append(f"{at} unresolved content needs a reason and optional safe HTTPS source")
            continue
        if kind in TEXT_KINDS:
            if set(content) != {"text", "sha256"} or not isinstance(content["text"], str) or "filename" in asset:
                problems.append(f"{at} text content needs exactly text/sha256 and no filename")
                continue
            data = content["text"].encode("utf-8")
            if not data or len(data) > MAX_TEXT_BYTES or any(ord(c) < 32 and c not in "\r\n\t" for c in content["text"]):
                problems.append(f"{at} text is empty, contains unsupported control bytes, or exceeds byte limit")
        else:
            types = BINARY_TYPES[kind]
            if (set(content) != {"base64", "sha256", "size", "media_type"} or not isinstance(content["base64"], str)
                    or type(content["size"]) is not int or not 0 < content["size"] <= MAX_BINARY_BYTES
                    or not isinstance(content["media_type"], str) or content["media_type"] not in types):
                problems.append(f"{at} binary content has invalid fields/type/byte bounds")
                continue
            try:
                data = base64.b64decode(content["base64"], validate=True)
            except (ValueError, binascii.Error):
                problems.append(f"{at} binary content is not strict base64")
                continue
            name = asset.get("filename")
            if not (isinstance(name, str) and FILENAME.fullmatch(name)
                    and name.lower().endswith(types[content["media_type"]])):
                problems.append(f"{at} needs a plain filename matching the allowed media type")
            if (len(data) != content["size"] or base64.b64encode(data).decode("ascii") != content["base64"]
                    or not SIGNATURES[content["media_type"]](data)):
                problems.append(f"{at} binary size, canonical encoding or media signature differs")
            if kind == "image":
                width, height = _image_size(content["media_type"], data)
                if not (0 < width <= 8192 and 0 < height <= 8192 and width * height <= 16_777_216):
                    problems.append(f"{at} image dimensions are unavailable or exceed decoded bounds")
        total += len(data)
        if content.get("sha256") != hashlib.sha256(data).hexdigest():
            problems.append(f"{at} review content digest differs from actual bytes")
    if delivery and (len(set(delivery["attachments"])) != len(delivery["attachments"])
                     or not all(isinstance(a, str) and a in seen for a in delivery["attachments"])):
        problems.append(f"{where} delivery attachments must name unique included review assets")
    return problems, total


def _row_problems(r: dict, i: int, opts: list) -> list:
    rid, problems = r.get("id"), []
    if not r.get("label") or not isinstance(r["label"], str) or not r["label"].strip():
        problems.append(f"rows[{i}] ({rid}) label must be a non-empty string")
    elif LINE_BREAK.search(r["label"]):
        problems.append(f"rows[{i}] ({rid}) label {r['label']!r} contains a line break - {SINGLE_LINE_FORM}")
    if "severity" in r and (not isinstance(r["severity"], str) or r["severity"] not in SEVERITIES):
        problems.append(f"rows[{i}] ({rid}) severity {r['severity']!r} not in {sorted(SEVERITIES)}")
    row_opts = r.get("options", opts)
    if not isinstance(row_opts, list) or not row_opts:
        problems.append(f"rows[{i}] ({rid}) options must be a non-empty list")
        row_opts = opts
    elif "options" in r:
        problems += _option_set_problems(row_opts, f"rows[{i}] ({rid})")
    values = sorted(o["value"] for o in row_opts if isinstance(o, dict) and isinstance(o.get("value"), str))
    if r.get("recommendation") is not None and r["recommendation"] not in values:
        problems.append(f"rows[{i}] ({rid}) recommendation {r['recommendation']!r} is not one of its options {values}")
    if "prior_position" in r:
        p = r["prior_position"]
        sourced = lambda e: isinstance(e, dict) and set(e) == {"statement", "source_ref"} and all(  # noqa: E731
            isinstance(e[k], str) and e[k].strip() for k in e)
        if not (isinstance(p, dict) and set(p) == {"statement", "source_ref", "evidence_for", "evidence_against"}
                and sourced({k: p[k] for k in ("statement", "source_ref")})
                and all(isinstance(p[k], list) and all(map(sourced, p[k])) for k in ("evidence_for", "evidence_against"))):
            problems.append(f"rows[{i}] ({rid}) prior_position requires exact statement/source_ref and sourced "
                            "evidence_for/evidence_against lists")
    d = r.get("disagreement")
    if d is not None and not (isinstance(d, dict) and all(
            isinstance(d.get(s), dict) and all(isinstance(d[s].get(k), str) and d[s][k] for k in ("who", "view"))
            for s in ("a", "b"))):
        problems.append(f"rows[{i}] ({rid}) disagreement needs both 'a' and 'b'")
    imp = r.get("impact")
    if imp is not None and not (isinstance(imp, dict) and all(
            isinstance(imp.get(k), str) and imp[k] for k in ("accept", "decline"))):
        problems.append(f"rows[{i}] ({rid}) impact needs both 'accept' and 'decline'")
    problems += [f"rows[{i}] ({rid}) {k} must be a string" for k in ("context", "reasoning")
                 if k in r and not isinstance(r[k], str)]
    for link in r.get("links", []) if isinstance(r.get("links", []), list) else [None]:
        if not isinstance(link, dict) or not all(isinstance(link.get(k), str) for k in ("href", "label")):
            problems.append(f"rows[{i}] ({rid}) links must be a list of string href and label")
        elif any(ord(c) < 32 for c in link["href"]) or _scheme(link["href"]) not in ("", "http", "https", "file"):
            problems.append(f"rows[{i}] ({rid}) link scheme is not permitted")
    if "tags" in r and not (isinstance(r["tags"], list) and all(isinstance(t, str) for t in r["tags"])):
        problems.append(f"rows[{i}] ({rid}) tags must be a list of strings")
    return problems


def validate(spec: dict) -> list:
    """Problems with the spec. NOTE: and READER: entries are advisory; the rest refuse the build."""
    if not isinstance(spec, dict):
        return ["spec must be a JSON object"]
    problems = []
    try:
        canonical_spec_bytes(spec)
    except (TypeError, ValueError):  # includes an unpaired surrogate from a JSON escape
        problems.append("spec contains a value that is not valid JSON text")
    title = spec.get("title")
    if not isinstance(title, str) or not title.strip():
        problems.append("missing required field: title (a non-empty string)")
    elif LINE_BREAK.search(title):
        problems.append(f"title {title!r} contains a line break - {SINGLE_LINE_FORM}")
    opts = spec.get("options")
    if not isinstance(opts, list) or not opts:
        problems.append("missing required field: options (a non-empty list)")
        opts = []
    else:
        problems += _option_set_problems(opts, "options")
    rows = spec.get("rows")
    if not isinstance(rows, list) or not rows:
        return problems + ["missing required field: rows (a non-empty list)"]
    if len(rows) < 5:
        problems.append(f"NOTE: only {len(rows)} rows. Below about five parallel decisions, just ask in chat - "
                        "see the anti-trigger in SKILL.md. Pass --allow-small to build anyway.")
    seen, review_bytes = set(), 0
    for i, r in enumerate(rows):
        if not isinstance(r, dict):
            problems.append(f"rows[{i}] must be an object")
            continue
        rid = r.get("id")
        if not isinstance(rid, str) or not rid.strip():
            # Browser storage and DOM datasets coerce ids to strings: JSON 1 and "1" collide.
            problems.append(f"rows[{i}] id {rid!r} must be a non-empty string - browser storage coerces "
                            "ids to strings, so non-string ids can collide after coercion")
        elif rid != rid.strip() or re.search(r"\s{2,}", rid) or LINE_BREAK.search(rid):
            problems.append(f"rows[{i}] id {rid!r} has leading, trailing or doubled whitespace or a line break - "
                            'the pasted summary prints "id  label" on one line')
        elif rid in seen:
            problems.append(f"rows[{i}] duplicate id {rid!r} - ids key saved choices and must be unique")
        seen.add(rid if isinstance(rid, str) else None)
        problems += _row_problems(r, i, opts)
        asset_problems, asset_bytes = _review_problems(r, f"rows[{i}]")
        problems, review_bytes = problems + asset_problems, review_bytes + asset_bytes
    if review_bytes > MAX_BINARY_BYTES:
        problems.append("review_assets exceed aggregate byte limit")
    problems += [f"{k} must be a string" for k in ("subtitle", "intro", "summary_intro", "audience", "scope",
                                                    "storage_key", "carried_from") if k in spec and not isinstance(spec[k], str)]
    filters = spec.get("filters", [])
    for f in filters if isinstance(filters, list) else [None]:
        if not (isinstance(f, dict) and isinstance(f.get("id"), str) and isinstance(f.get("label"), str)
                and all(isinstance(f.get(k, []), list) and all(isinstance(v, str) for v in f.get(k, []))
                        for k in ("tags", "severity"))):
            problems.append("each filter needs string id and label, and tags/severity lists of strings")
    glossary = spec.get("glossary", [])
    for g in glossary if isinstance(glossary, list) else [None]:
        if not isinstance(g, dict) or not g.get("term") or not g.get("meaning"):
            problems.append("glossary must be a list of {term, meaning}")
    # Reader contract: warnings by default, fatal under --strict-reader, which SKILL.md requires
    # for packets handed to a principal. Origin: a 15-row packet in project-internal language
    # collected 0 decisions from the principal whose plain-language packets ran 30/30.
    if not spec.get("audience"):
        problems.append("READER: no 'audience' - name who reads this and what they already know, "
                        "then write every row for that reader")
    missing = [str(r.get("id")) for r in rows if isinstance(r, dict) and not r.get("impact")]
    if missing:
        problems.append("READER: rows without an 'impact' block (what happens if they accept / decline, "
                        "in the principal's terms): " + ", ".join(missing))
    if not any(isinstance(r, dict) and r.get("recommendation") for r in rows):
        problems.append("no row carries a recommendation. A packet without recommendations is a "
                        "questionnaire, which means the analysis is not finished - see SKILL.md.")
    return problems


def build(spec: dict) -> str:
    """The page for a valid spec, carrying the integrity marker doctors read (keep its exact form)."""
    hard = [p for p in validate(spec) if not p.startswith(("NOTE:", "READER:"))]
    if hard:
        raise ValueError("invalid spec: " + "; ".join(hard))
    page_spec = dict(spec)
    page_spec.setdefault("storage_key", slugify(spec["title"]))
    page_spec.setdefault("filters", [])
    # Escaping every "<" keeps spec text such as "</script>" or "<!--<script>" from ending
    # the script block; JSON.parse restores the exact values.
    payload = json.dumps(page_spec, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c")

    def para(key, cls, prefix=""):
        return f'<p class="{cls}">{prefix}{html.escape(spec[key])}</p>' if spec.get(key) else ""
    glossary = spec.get("glossary") or []
    terms = "".join(f"<dt>{html.escape(str(g['term']))}</dt><dd>{html.escape(str(g['meaning']))}</dd>"
                    for g in glossary)
    fields = {
        "__TITLE__": html.escape(spec["title"]), "__SPEC_JSON__": payload,
        "__CANONICAL_SPEC_SHA256__": spec_digest(spec),
        "__SUBTITLE__": para("subtitle", "sub"), "__INTRO__": para("intro", "intro"),
        "__SCOPE__": para("scope", "intro", "Scope: "), "__AUDIENCE__": para("audience", "aud", "Written for: "),
        "__GLOSSARY__": (f'<details class="gloss"><summary>Terms used below ({len(glossary)})</summary>'
                         f"<dl>{terms}</dl></details>") if glossary else "",
        "__SUMMARY_INTRO__": html.escape(spec.get("summary_intro")
                                         or "Work through the rows, then copy this and paste it back in one message."),
    }
    template = (ASSETS / "packet-template.html").read_text(encoding="utf-8")
    # One substitution pass, so spec text that contains a placeholder stays text.
    page = re.sub("|".join(map(re.escape, fields)), lambda m: fields[m.group()], template)
    marker = f"<!-- synthesis-decision-packet spec-sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()} -->\n"
    head, sep, tail = page.partition("</title>\n")
    if not sep:
        raise RuntimeError("packet template lost its </title> line")
    page = head + sep + marker + tail
    if len(page.encode("utf-8")) > MAX_HTML_BYTES:
        raise ValueError("generated packet exceeds the 8 MiB page limit; use fewer or smaller review assets")
    return page


def file_packet(spec: dict, page: str, directory: pathlib.Path, date: str) -> tuple:
    """File <date>-<slug>-spec.json and <date>-<slug>.html; a revision gets a digest suffix."""
    stem = f"{date}-{slugify(spec['title'])}"
    spec_bytes, page_bytes = canonical_spec_bytes(spec), page.encode("utf-8")
    copies = (directory / f"{stem}-spec.json", directory / f"{stem}.html")
    if any(p.exists() and (p.is_symlink() or p.read_bytes() != b) for p, b in zip(copies, (spec_bytes, page_bytes))):
        stem += "-" + hashlib.sha256(spec_bytes + page_bytes).hexdigest()
        copies = (directory / f"{stem}-spec.json", directory / f"{stem}.html")
    for path, data in zip(copies, (spec_bytes, page_bytes)):
        write_preserved(path, data)
    return copies


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", nargs="?", help="path to the JSON spec ('-' for stdin)")
    ap.add_argument("-o", "--out", help="write the page to this path (a working copy; it is overwritten)")
    ap.add_argument("--stdout", action="store_true", help="write the page to stdout")
    ap.add_argument("--schema", action="store_true", help="print the spec format and exit")
    ap.add_argument("--allow-small", action="store_true", help="build with fewer than five rows")
    ap.add_argument("--strict-reader", action="store_true",
                    help="make reader-contract findings (missing audience or impact, option labels that "
                         "name no consequence) fatal; SKILL.md requires this for packets handed to a principal")
    ap.add_argument("--file-into", metavar="DIR", type=pathlib.Path,
                    help="file <date>-<slug>-spec.json and <date>-<slug>.html into DIR, the owning "
                         "project's existing resources/artifacts/ directory")
    ap.add_argument("--date", metavar="YYYY-MM-DD", help="the date in the filed names (default: today)")
    args = ap.parse_args()
    if args.schema:
        print((ASSETS / "spec-schema.txt").read_text(encoding="utf-8"), end="")
        return 0
    if not args.spec:
        ap.error("a spec path is required (or --schema)")
    if args.date and not args.file_into:
        ap.error("--date requires --file-into")
    if args.date and parse_iso_date(args.date) is None:
        ap.error(f"--date {args.date!r} is not a calendar date in YYYY-MM-DD form")
    if args.file_into and not args.file_into.is_dir():
        print(f"--file-into: {args.file_into} is not an existing directory - pass the owning project's "
              "resources/artifacts/ directory and create it first", file=sys.stderr)
        return 2
    try:
        raw = sys.stdin.buffer.read(MAX_SPEC_BYTES + 1) if args.spec == "-" else pathlib.Path(args.spec).read_bytes()
        if len(raw) > MAX_SPEC_BYTES:
            raise ValueError("spec exceeds 8 MiB")
        spec = strict_json(raw.decode("utf-8"))
    except (OSError, ValueError) as exc:
        print(f"cannot read valid spec JSON: {exc}", file=sys.stderr)
        return 2
    problems = validate(spec)
    hard = [p for p in problems if not p.startswith(("NOTE:", "READER:"))]
    notes = [p for p in problems if p.startswith("NOTE:")]
    reader = [p for p in problems if p.startswith("READER:")]
    for p in notes + reader:
        print(p, file=sys.stderr)
    if notes and not args.allow_small:
        hard.append("refusing to build a sub-five-row packet without --allow-small")
    if reader and args.strict_reader:
        hard.append("reader contract unmet (--strict-reader): see READER findings above")
    if hard:
        print("\nwill not build:\n" + "\n".join("  - " + p for p in hard), file=sys.stderr)
        return 2
    try:
        page, reports = build(spec), []
        if args.out:
            dest = pathlib.Path(args.out)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(page, encoding="utf-8")
            reports.append(f"{dest}  ({len(page.encode('utf-8')):,} bytes, {len(spec['rows'])} rows)")
        if args.file_into:
            date = args.date or datetime.date.today().isoformat()
            reports += [f"filed {p}" for p in file_packet(spec, page, args.file_into, date)]
    except (OSError, ValueError) as exc:
        print(f"packet build refused: {exc}", file=sys.stderr)
        return 2
    if args.stdout or not (args.out or args.file_into):
        sys.stdout.write(page)
    for message in reports:
        print(message, file=sys.stderr if args.stdout else sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())

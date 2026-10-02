#!/usr/bin/env python3
"""Build a self-contained decision-packet HTML file from a JSON spec.

A decision packet is a single HTML file that collects many parallel decisions from a
principal in one sitting and emits a paste-able record of them. It exists because the
alternatives do not scale: one question per turn costs N round-trips, and a prose report
or a chat table makes the principal supply the structure the agent needs.

The origin run: 26 rounds of per-item conversation produced 0 of 30 decisions. One packet
produced 30 of 30, in one pass, in one paste.

    python3 build_packet.py spec.json -o packet.html --strict-reader
    python3 build_packet.py spec.json --stdout > packet.html
    python3 build_packet.py spec.json --strict-reader --file-into PROJECT/resources/artifacts/
    python3 build_packet.py --schema          # print the spec schema and exit

--file-into files a dated copy of the spec and the page in the owning project, where every
agent on the project can read them; record_rulings.py files the principal's paste beside them.

Stdlib only. No build step, no dependencies, no server: the emitted file opens from disk,
from a local HTTP server, or as a published artifact.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import datetime
import hashlib
import html
import json
import math
import os
import stat
import pathlib
import re
import sys
import urllib.parse

SCHEMA = """\
Decision-packet spec (JSON)
===========================

{
  "title":       "Code review — CSA content pipeline",     REQUIRED, one line
  "subtitle":    "12 findings from an adversarial pass",    optional
  "intro":       "Markdown-free prose shown under the title.",  optional
  "scope":       "Exact target, payload and limits of these choices.", optional
  "storage_key": "csa-review-2026-09",   optional; defaults to a slug of the title.
                                         Saved state also binds the complete spec
                                         digest, so changed meaning starts empty.
  "summary_intro": "Paste this back to the agent.",  optional
  "audience":    "One sentence: who reads this and what they already know.",
                                          optional in the format, REQUIRED by the
                                          reader contract in SKILL.md - it is the
                                          audience you must write every row for.
  "glossary": [                           optional - one-clause meanings for every
    {"term": "holdout",                   term of art any row still needs after
     "meaning": "test material set aside  plain-language rewriting. Rendered as a
      in advance so a rule is judged on   collapsible band under the intro.
      text it was not tuned on"}
  ],

  Rows may additionally declare exact material for review:
  "revision": "draft-3",                  REQUIRED with review_assets
  "delivery": {"format": "Plain text", "destinations": ["reader@example.test"],
               "attachments": ["diagram"]},
  "review_assets": [
    {"id": "draft", "title": "Complete draft", "kind": "correspondence",
     "content": {"text": "Full exact body", "sha256": "SHA-256 of UTF-8 body"}}
  ]
  These fields belong to each ROW, not the packet root. They bind every saved
  choice and returned ruling. See references/review-assets.md for the complete
  closed text/binary/unresolved union, safe Markdown grammar and byte ceilings.
  Unavailable assets are visible but cannot carry a selected ruling. External
  references are never fetched, and records do not authorize any action.

  "options": [                            REQUIRED — the default choice set for every row
    {"value": "fix-now",  "label": "Fix it before the next release",
     "tone": "danger", "consequence": "The release waits for the fix."},
    {"value": "fix-later","label": "Ship now, fix it next sprint", "tone": "warn"},
    {"value": "waive",    "label": "Leave it as it is",            "tone": "muted"}
  ],
  tone ∈ {danger, warn, ok, muted, info} — colours the selected button only.
  value: a non-empty string, unique within its set — it keys the button's
         pressed state and the summary's label. A set offers at least two.
  label: what pressing the button DOES, in the principal's terms, on one line.
         A bare acknowledgement (Yes, No, OK, Cancel, Accept, Decline, Approve,
         Reject, Do it, Go, Stop, "Yes, do that", "No thanks", or any of these
         padded with a stopword: "Accept it", "Do that") or two labels that
         share every content word raise READER findings; --strict-reader
         refuses them.
  consequence: optional — shown under the label on the button itself. Without
         it, the row's impact.accept sits under the recommended option and
         impact.decline under every other option.

  "filters": [                            optional; name these from the CONTENT
    {"id": "needs-fix", "label": "Needs a fix", "tags": ["correctness"]},
    {"id": "disputed",  "label": "We disagreed", "disagreement": true},
    {"id": "undecided", "label": "Not yet decided", "undecided": true}
  ],
  A filter matches if ANY of its declared criteria match. "undecided" is computed live
  from saved state; "disagreement" matches rows carrying a disagreement block.

  "rows": [                               REQUIRED
    {
      "id":    "F-01",                    REQUIRED — stable; it keys localStorage
      "label": "Unbounded retry loop in the publish worker",   REQUIRED, one line
      "context":  "What the reader needs to judge it.",        optional
      "reasoning":"Why the agent recommends what it does.",    optional
      "impact": {                          optional in the format, REQUIRED by the
        "accept": "What actually happens   reader contract: the consequences of
                   if they take your       agreeing and of not agreeing, stated in
                   recommendation.",       outcomes the principal cares about -
        "decline": "What happens if they   never in internal treatment vocabulary.
                   do not."
      },
      "recommendation": "fix-now",        optional but STRONGLY expected — MARKS
                                          a button (never pre-selects it: a packet
                                          that opens decided records nobody's
                                          judgment). No recommendation on any row
                                          means the packet is a questionnaire; see the
                                          anti-trigger in SKILL.md.
      "severity": "high",                 optional ∈ {high, medium, low, none}
                                          — drives the coloured rail
      "tags":  ["correctness", "worker"], optional — drive filters and read as chips
      "links": [{"label": "worker.py:214", "href": "https://..."}],   optional
      "disagreement": {                   optional — surface it, never resolve it first
        "a": {"who": "Reviewer A", "view": "Ship it; the retry is bounded upstream."},
        "b": {"who": "Reviewer B", "view": "Upstream bound was removed in v0.91."}
      },
      "options": [...]                    optional per-row override of the choice set
    }
  ]
}
"""

TONES = {"danger", "warn", "ok", "muted", "info"}
SEVERITIES = {"high", "medium", "low", "none"}


def strict_json(raw: str):
    """Reject ambiguous JSON instead of silently taking its last duplicate key."""
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
    """The complete spec as sorted, compact UTF-8 JSON plus one LF.

    Every field participates, including context, consequences and scope. No
    normalization of Unicode or defaults silently changes the presented spec.
    """
    return (json.dumps(spec, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def spec_digest(spec: dict) -> str:
    return hashlib.sha256(canonical_spec_bytes(spec)).hexdigest()


def write_preserved(path: pathlib.Path, payload: bytes) -> None:
    """Create or verify identical bytes; never replace a historical artifact."""
    if path.is_symlink():
        raise ValueError(f"refusing symlink output: {path}")
    try:
        with path.open("xb") as stream:
            stream.write(payload)
    except FileExistsError:
        if not path.is_file() or path.read_bytes() != payload:
            raise ValueError(f"existing artifact differs; preserved without replacement: {path}")


def _json_shape_problems(value, where="spec") -> list[str]:
    """Reject values the browser cannot faithfully consume."""
    if isinstance(value, dict):
        return [problem for key, item in value.items()
                for problem in _json_shape_problems(item, f"{where}.{key}")]
    if isinstance(value, list):
        return [problem for index, item in enumerate(value)
                for problem in _json_shape_problems(item, f"{where}[{index}]")]
    if isinstance(value, float) and not math.isfinite(value):
        return [f"{where} must not contain a nonfinite number"]
    if isinstance(value, int) and not isinstance(value, bool) and abs(value) > 2**53 - 1:
        return [f"{where} integer is outside the browser's exact range"]
    if isinstance(value, str):
        try:
            value.encode("utf-8")
        except UnicodeEncodeError:
            return [f"{where} contains an unpaired Unicode surrogate"]
    return []

# Option labels must say what pressing the button DOES. Fixture of the failure,
# 2026-09-14: on a 9-row packet, three rows carrying the options
# {"Yes, do that", "No"} collected notes instead of decisions - the principal
# could not tell what each button would do to the thing in question, so the
# note boxes carried what the buttons should have. Labels are compared after
# lower-casing, stripping punctuation and collapsing whitespace.
BARE_ACKNOWLEDGEMENTS = {
    "yes", "no", "ok", "okay", "cancel", "accept", "decline", "approve", "reject",
    "do it", "yes do that", "go", "stop", "no thanks",
}
# Words that carry no consequence on their own; two labels that differ only in
# these (or in words under three letters) do not differ at all.
STOPWORDS = {"the", "a", "an", "it", "that", "this", "do", "to", "of", "in", "on",
             "my", "me", "and", "or", "not"}
ACCEPTED_LABEL_FORM = ('label each option by what pressing it does, '
                       'e.g. "Keep them on my phone" / "Take them off my phone"')
# The pasted summary is line-based: the title, each "id  label" header and each
# decision line occupy one line, and record_rulings.py reads them back one line
# at a time. A line break inside any of those fields builds a packet whose own
# paste is refused - discovered only after the principal's sitting.
LINE_BREAK = re.compile(r"[\r\n]")
SINGLE_LINE_FORM = ("the pasted summary is one line per field, so title, row labels "
                    "and option labels must be single-line")


def normalize_label(label) -> str:
    """Lower-case, punctuation stripped, whitespace collapsed."""
    return " ".join(re.findall(r"[^\W_]+", str(label).lower()))


def is_bare_acknowledgement(label) -> bool:
    """True when the label names no consequence: it is one of the listed
    acknowledgements, or becomes one once its stopwords are removed ("Accept
    it", "Approve this"), or has nothing left at all once they are ("Do that")."""
    norm = normalize_label(label)
    stripped = " ".join(w for w in norm.split() if w not in STOPWORDS)
    return norm in BARE_ACKNOWLEDGEMENTS or stripped in BARE_ACKNOWLEDGEMENTS or not stripped


def content_words(label) -> frozenset[str]:
    """Words of three or more letters that are not stopwords."""
    return frozenset(w for w in re.findall(r"[^\W\d_]+", str(label).lower())
                     if len(w) >= 3 and w not in STOPWORDS)


def parse_iso_date(text) -> str | None:
    """Return the date as YYYY-MM-DD when `text` is exactly that form and a real
    calendar date; None otherwise."""
    if not isinstance(text, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return None
    try:
        return datetime.date.fromisoformat(text).isoformat()
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Validation — fail loudly at build time, never emit a broken packet
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-") or "packet"


def _validate_option_set(opts: list, where: str, problems: list[str]) -> None:
    """Shape checks (hard) and label checks (READER) on one option set.

    `where` is "options" for the packet-level set or "rows[i] (id)" for a
    per-row override; it prefixes every finding so the message names the row.
    """
    prefix = "options" if where == "options" else f"{where} options"
    if len(opts) < 2:
        problems.append(
            f"{prefix} must offer at least two options - a one-button set records no "
            "decision; give the principal the alternative as a second labelled option")
    labels: list[str] = []
    values: list[str] = []
    for i, o in enumerate(opts):
        if not isinstance(o, dict) or not o.get("value") or not o.get("label"):
            problems.append(f"{prefix}[{i}] needs both 'value' and 'label'")
            continue
        if not isinstance(o["value"], str) or not o["value"].strip():
            # b.dataset.value stores a string while the saved choice keeps the
            # JSON type, so a numeric value counts as decided and never renders
            # pressed; JSON 1 and "1" also collide in the DOM.
            problems.append(
                f"{prefix}[{i}].value {o['value']!r} must be a non-empty string - the button's "
                "pressed state is keyed through a DOM dataset, which stores strings only")
            continue
        if not isinstance(o["label"], str) or not o["label"].strip():
            problems.append(f"{prefix}[{i}].label must be a non-empty string")
        if LINE_BREAK.search(str(o["label"])):
            problems.append(
                f"{prefix}[{i}] label {o['label']!r} contains a line break - {SINGLE_LINE_FORM}")
        if "tone" in o and (not isinstance(o["tone"], str) or o["tone"] not in TONES):
            problems.append(f"{prefix}[{i}].tone {o['tone']!r} not in {sorted(TONES)}")
        if "consequence" in o and (not isinstance(o["consequence"], str)
                                   or not o["consequence"].strip()):
            problems.append(f"{prefix}[{i}].consequence must be a non-empty string")
        labels.append(str(o["label"]))
        values.append(o["value"])

    # One saved choice presses every button sharing its value, and the summary's
    # labelFor() returns the first label whichever was pressed, so the filed
    # rulings would record the second button's press as the first.
    dupes = sorted({v for v in values if values.count(v) > 1})
    if dupes:
        noun, verb = ("value", "is") if len(dupes) == 1 else ("values", "are")
        problems.append(
            f"{prefix} {noun} {', '.join(repr(v) for v in dupes)} {verb} used by more than one "
            "option - every option in a set needs its own value because the value keys the "
            "pressed state and the summary label")

    head = "READER: options:" if where == "options" else f"READER: {where} option"
    bare = [lab for lab in labels if is_bare_acknowledgement(lab)]
    if bare:
        problems.append(
            f"{head} labels {', '.join(repr(lab) for lab in bare)} are bare acknowledgements "
            f"that name no consequence - {ACCEPTED_LABEL_FORM}")
    # A bare label is already reported; the pair check covers the rest.
    rest = [lab for lab in labels if lab not in bare]
    pairs = [f"{a!r} / {b!r}"
             for ai, a in enumerate(rest) for b in rest[ai + 1:]
             if content_words(a) == content_words(b)]
    if pairs:
        problems.append(
            f"{head} labels {', '.join(pairs)} do not differ in a content word - "
            f"{ACCEPTED_LABEL_FORM}")


# Review assets are data in the canonical spec, never paths to read or URLs to fetch.
MAX_REVIEW_ASSETS = 16
MAX_REVIEW_TEXT_BYTES = 1_048_576
MAX_REVIEW_BINARY_BYTES = 4_194_304
MAX_REVIEW_TOTAL_BYTES = 4_194_304
MAX_PACKET_INPUT_BYTES = 8_388_608
MAX_GENERATED_HTML_BYTES = 8_388_608
TEXT_REVIEW_KINDS = {'correspondence', 'plain_text', 'markdown', 'code'}
BINARY_REVIEW_TYPES = {
    'image': {'image/png': ('.png',), 'image/jpeg': ('.jpg', '.jpeg'),
              'image/gif': ('.gif',), 'image/webp': ('.webp',)},
    'audio': {'audio/mpeg': ('.mp3',), 'audio/wav': ('.wav',), 'audio/ogg': ('.ogg',)},
    'video': {'video/mp4': ('.mp4',), 'video/webm': ('.webm',)},
    'document': {'application/pdf': ('.pdf',)},
}


def read_packet_input(path: pathlib.Path | None) -> bytes:
    """Finite spec input; regular-file identity must remain stable while read."""
    if path is None:
        raw = sys.stdin.buffer.read(MAX_PACKET_INPUT_BYTES + 1)
    else:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_PACKET_INPUT_BYTES:
                raise ValueError("packet input is not a bounded regular file")
            with os.fdopen(os.dup(fd), "rb") as stream:
                raw = stream.read(MAX_PACKET_INPUT_BYTES + 1)
            def identity(value):
                return (value.st_dev, value.st_ino, value.st_mode, value.st_size,
                        value.st_mtime_ns, value.st_ctime_ns)
            if identity(before) != identity(os.fstat(fd)) or identity(before) != identity(path.lstat()):
                raise ValueError("packet input changed during read")
        finally:
            os.close(fd)
    if len(raw) > MAX_PACKET_INPUT_BYTES:
        raise ValueError("packet input exceeds byte limit")
    return raw


def _review_string(value, limit=4096):
    return (isinstance(value, str) and bool(value.strip()) and
            len(value.encode('utf-8')) <= limit and
            not any(ord(c) < 32 and c not in '\n\r\t' for c in value))


def _review_source(value):
    if not _review_string(value, 2048) or any(c.isspace() for c in value):
        return False
    try:
        parsed = urllib.parse.urlsplit(value)
        # External references remain unresolved even when a URL looks valid.
        # No file://, relative path, credentials, or automatic resource loading.
        return (parsed.scheme == 'https' and bool(parsed.hostname) and
                parsed.username is None and parsed.password is None and
                parsed.port in (None, 443) and '\\' not in value)
    except ValueError:
        return False


def _review_signature(media, data):
    if media == 'image/png':
        return len(data) >= 24 and data.startswith(b'\x89PNG\r\n\x1a\n') and data[12:16] == b'IHDR'
    if media == 'image/jpeg':
        return data.startswith(b'\xff\xd8\xff') and data.endswith(b'\xff\xd9')
    if media == 'image/gif':
        return len(data) >= 10 and data[:6] in (b'GIF87a', b'GIF89a')
    if media == 'image/webp':
        return len(data) >= 16 and data.startswith(b'RIFF') and data[8:12] == b'WEBP'
    if media == 'audio/wav':
        return len(data) >= 12 and data.startswith(b'RIFF') and data[8:12] == b'WAVE'
    if media == 'audio/ogg':
        return data.startswith(b'OggS')
    if media == 'audio/mpeg':
        return data.startswith(b'ID3') or (len(data) >= 2 and data[0] == 255 and data[1] & 224 == 224)
    if media == 'video/mp4':
        return len(data) >= 12 and data[4:8] == b'ftyp'
    if media == 'video/webm':
        return data.startswith(b'\x1a\x45\xdf\xa3')
    if media == 'application/pdf':
        return data.startswith(b'%PDF-')
    return False


def _review_image_dimensions(media, data):
    """Bound decoded raster size before handing compressed bytes to a browser."""
    if media == 'image/png' and len(data) >= 24:
        return int.from_bytes(data[16:20], 'big'), int.from_bytes(data[20:24], 'big')
    if media == 'image/gif' and len(data) >= 10:
        return int.from_bytes(data[6:8], 'little'), int.from_bytes(data[8:10], 'little')
    if media == 'image/webp' and len(data) >= 30:
        kind = data[12:16]
        if kind == b'VP8X':
            return 1 + int.from_bytes(data[24:27], 'little'), 1 + int.from_bytes(data[27:30], 'little')
        if kind == b'VP8 ' and data[23:26] == b'\x9d\x01\x2a':
            return int.from_bytes(data[26:28], 'little') & 0x3fff, int.from_bytes(data[28:30], 'little') & 0x3fff
        if kind == b'VP8L' and data[20] == 0x2f:
            packed = int.from_bytes(data[21:25], 'little')
            return 1 + (packed & 0x3fff), 1 + ((packed >> 14) & 0x3fff)
    if media == 'image/jpeg':
        offset, end = 2, min(len(data), 131072)
        while offset + 4 <= end:
            if data[offset] != 0xff:
                return 0, 0
            while offset < end and data[offset] == 0xff:
                offset += 1
            if offset + 3 > end:
                break
            marker = data[offset]
            offset += 1
            length = int.from_bytes(data[offset:offset + 2], 'big')
            if length < 2 or offset + length > end:
                break
            if marker in {0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf} and length >= 7:
                return int.from_bytes(data[offset + 5:offset + 7], 'big'), int.from_bytes(data[offset + 3:offset + 5], 'big')
            offset += length
    return 0, 0


def review_assets_ready(row):
    """Inspectable byte custody, not authorship, principal identity or authority."""
    return all('unavailable' not in asset['content'] for asset in row.get('review_assets', []))


def validate_review_assets(row, where):
    problems, total = [], 0
    if 'review_assets' not in row:
        if 'delivery' in row or 'revision' in row:
            problems.append(f'{where} delivery/revision requires review_assets')
        return problems, total
    assets = row['review_assets']
    if not isinstance(assets, list) or not 1 <= len(assets) <= MAX_REVIEW_ASSETS:
        return [f'{where} review_assets needs 1..{MAX_REVIEW_ASSETS} typed assets'], total
    if not _review_string(row.get('revision'), 256):
        problems.append(f'{where} review_assets requires a nonempty revision')
    delivery = row.get('delivery')
    if (not isinstance(delivery, dict) or set(delivery) != {'format', 'destinations', 'attachments'} or
            not _review_string(delivery.get('format'), 256) or
            not isinstance(delivery.get('destinations'), list) or len(delivery['destinations']) > 64 or
            not all(_review_string(v, 2048) for v in delivery.get('destinations', [])) or
            not isinstance(delivery.get('attachments'), list)):
        problems.append(f'{where} review_assets requires exact delivery format/destinations/attachments')
        delivery = None
    seen = set()
    for index, asset in enumerate(assets):
        at = f'{where} review_assets[{index}]'
        if not isinstance(asset, dict) or set(asset) - {'id', 'title', 'kind', 'content', 'description', 'filename'}:
            problems.append(f'{at} has unknown fields or is not an object')
            continue
        aid, kind, content = asset.get('id'), asset.get('kind'), asset.get('content')
        if not isinstance(aid, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', aid) or aid in seen:
            problems.append(f'{at} requires a unique bounded ASCII id')
        else:
            seen.add(aid)
        if not _review_string(asset.get('title'), 512):
            problems.append(f'{at} requires a title')
        if not isinstance(kind, str) or kind not in TEXT_REVIEW_KINDS | BINARY_REVIEW_TYPES.keys():
            problems.append(f'{at} has an unsupported kind')
            continue
        if 'filename' in asset and (kind in TEXT_REVIEW_KINDS or
                not isinstance(asset['filename'], str) or
                not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', asset['filename'])):
            problems.append(f'{at} filename must be a plain bounded binary basename')
        if 'description' in asset and not _review_string(asset['description'], 4096):
            problems.append(f'{at} description is invalid')
        if kind in BINARY_REVIEW_TYPES and not _review_string(asset.get('description'), 4096):
            problems.append(f'{at} requires an accessible description')
        if not isinstance(content, dict):
            problems.append(f'{at} content must be an object')
            continue
        if 'unavailable' in content:
            if (set(content) - {'unavailable', 'source'} or not _review_string(content['unavailable']) or
                    ('source' in content and not _review_source(content['source']))):
                problems.append(f'{at} unresolved content needs a reason and optional safe HTTPS source')
            continue
        if kind in TEXT_REVIEW_KINDS:
            if (set(content) != {'text', 'sha256'} or not isinstance(content.get('text'), str) or
                    'filename' in asset):
                problems.append(f'{at} text content needs exactly text/sha256 and no filename')
                continue
            data = content['text'].encode('utf-8')
            if not data or len(data) > MAX_REVIEW_TEXT_BYTES or any(ord(c) < 32 and c not in '\r\n\t' for c in content['text']):
                problems.append(f'{at} text is empty, contains unsupported control bytes, or exceeds byte limit')
        else:
            if (set(content) != {'base64', 'sha256', 'size', 'media_type'} or
                    not isinstance(content.get('base64'), str) or
                    len(content['base64']) > ((MAX_REVIEW_BINARY_BYTES + 2) // 3) * 4 or
                    type(content.get('size')) is not int or not 0 < content['size'] <= MAX_REVIEW_BINARY_BYTES or
                    not isinstance(content.get('media_type'), str) or
                    content['media_type'] not in BINARY_REVIEW_TYPES[kind]):
                problems.append(f'{at} binary content has invalid fields/type/byte bounds')
                continue
            try:
                data = base64.b64decode(content['base64'], validate=True)
            except (ValueError, binascii.Error):
                problems.append(f'{at} binary content is not strict base64')
                continue
            filename = asset.get('filename')
            if (not isinstance(filename, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', filename) or
                    not filename.lower().endswith(BINARY_REVIEW_TYPES[kind][content['media_type']])):
                problems.append(f'{at} needs a plain filename matching the allowed media type')
            if (len(data) != content['size'] or base64.b64encode(data).decode('ascii') != content['base64'] or
                    not _review_signature(content['media_type'], data)):
                problems.append(f'{at} binary size, canonical encoding or media signature differs')
            if kind == 'image':
                width, height = _review_image_dimensions(content['media_type'], data)
                if not (0 < width <= 8192 and 0 < height <= 8192 and width * height <= 16_777_216):
                    problems.append(f'{at} image dimensions are unavailable or exceed decoded bounds')
        total += len(data)
        digest = content.get('sha256')
        if not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest) or hashlib.sha256(data).hexdigest() != digest:
            problems.append(f'{at} review content digest differs from actual bytes')
    if delivery:
        attachments = delivery['attachments']
        if (len(attachments) > MAX_REVIEW_ASSETS or not all(isinstance(a, str) and a in seen for a in attachments) or
                len(set(attachments)) != len(attachments)):
            problems.append(f'{where} delivery attachments must name unique included review assets')
    return problems, total


def validate(spec: dict) -> list[str]:
    """Return a list of problems; empty means the spec is buildable."""
    problems: list[str] = []

    if not isinstance(spec, dict):
        return ["spec must be a JSON object"]
    problems.extend(_json_shape_problems(spec))
    if not spec.get("title"):
        problems.append("missing required field: title")
    elif not isinstance(spec["title"], str) or not spec["title"].strip():
        problems.append("title must be a non-empty string")
    elif LINE_BREAK.search(str(spec["title"])):
        problems.append(
            f"title {spec['title']!r} contains a line break - {SINGLE_LINE_FORM}")

    opts = spec.get("options")
    if not isinstance(opts, list) or not opts:
        problems.append("missing required field: options (a non-empty list)")
        opts = []
    else:
        _validate_option_set(opts, "options", problems)

    rows = spec.get("rows")
    if not isinstance(rows, list) or not rows:
        problems.append("missing required field: rows (a non-empty list)")
        return problems

    if len(rows) < 5:
        # Not fatal — but the skill's anti-trigger says this shape is the wrong tool.
        problems.append(
            f"NOTE: only {len(rows)} rows. Below about five parallel decisions, just ask "
            "in chat — see the anti-trigger in SKILL.md. Pass --allow-small to build anyway."
        )

    seen: set[str] = set()
    review_bytes = 0
    for i, r in enumerate(rows):
        if not isinstance(r, dict):
            problems.append(f"rows[{i}] must be an object")
            continue
        if not _json_shape_problems(r):
            asset_problems, asset_bytes = validate_review_assets(r, f"rows[{i}]")
            problems.extend(asset_problems)
            review_bytes += asset_bytes
        rid = r.get("id")
        if not rid:
            problems.append(f"rows[{i}] missing required field: id")
        elif not isinstance(rid, str) or not rid.strip():
            # Ids key localStorage and DOM datasets, which coerce every value
            # to a string: JSON 1 and "1" become the same browser key, so two
            # JSON-distinct ids can silently share saved state. Only non-empty
            # strings are ids.
            problems.append(
                f"rows[{i}] id {rid!r} must be a non-empty string — browser "
                "storage coerces ids to strings, so non-string ids can "
                "collide after coercion"
            )
        elif rid != rid.strip() or re.search(r"\s{2,}", rid) or LINE_BREAK.search(rid):
            # The pasted summary prints "id  label" on one line and
            # record_rulings.py splits that line on its first double space.
            problems.append(
                f"rows[{i}] id {rid!r} has leading, trailing or doubled whitespace or a line "
                'break - the pasted summary prints "id  label" on one line and '
                "record_rulings.py splits on the first double space"
            )
        elif rid in seen:
            problems.append(f"rows[{i}] duplicate id {rid!r} — ids key localStorage and must be unique")
        else:
            seen.add(rid)
        if not r.get("label"):
            problems.append(f"rows[{i}] ({rid}) missing required field: label")
        elif not isinstance(r["label"], str) or not r["label"].strip():
            problems.append(f"rows[{i}] ({rid}) label must be a non-empty string")
        elif LINE_BREAK.search(str(r["label"])):
            problems.append(
                f"rows[{i}] ({rid}) label {r['label']!r} contains a line break - {SINGLE_LINE_FORM}")
        sev = r.get("severity")
        if "severity" in r and (not isinstance(sev, str) or sev not in SEVERITIES):
            problems.append(f"rows[{i}] ({rid}) severity {sev!r} not in {sorted(SEVERITIES)}")
        row_opts = r.get("options")
        if row_opts is None:
            row_opts = opts
        elif not isinstance(row_opts, list) or not row_opts:
            problems.append(f"rows[{i}] ({rid}) options must be a non-empty list")
            row_opts = opts
        else:
            _validate_option_set(row_opts, f"rows[{i}] ({rid})", problems)
        values = {o.get("value") for o in row_opts if isinstance(o, dict)
                  and isinstance(o.get("value"), str)}
        rec = r.get("recommendation")
        if rec is not None and (not isinstance(rec, str) or rec not in values):
            problems.append(
                f"rows[{i}] ({rid}) recommendation {rec!r} is not one of its options {sorted(v for v in values if v)}"
            )
        if "prior_position" in r:
            prior = r["prior_position"]
            fields = {"statement", "source_ref", "evidence_for", "evidence_against"}
            valid = isinstance(prior, dict) and set(prior) == fields
            if valid:
                valid = all(isinstance(prior[key], str) and prior[key].strip()
                            for key in ("statement", "source_ref"))
                for key in ("evidence_for", "evidence_against"):
                    entries = prior[key]
                    valid = valid and isinstance(entries, list)
                    if isinstance(entries, list):
                        valid = valid and all(
                            isinstance(entry, dict) and set(entry) == {"statement", "source_ref"}
                            and all(isinstance(entry[field], str) and entry[field].strip()
                                    for field in ("statement", "source_ref")) for entry in entries)
            if not valid:
                problems.append(f"rows[{i}] ({rid}) prior_position requires exact statement/source_ref and sourced evidence_for/evidence_against lists")
        dis = r.get("disagreement")
        if dis is not None:
            if (not isinstance(dis, dict) or
                    any(not isinstance(dis.get(side), dict) or
                        not all(isinstance(dis[side].get(k), str) and dis[side][k]
                                for k in ("who", "view")) for side in ("a", "b"))):
                problems.append(f"rows[{i}] ({rid}) disagreement needs both 'a' and 'b'")
        imp = r.get("impact")
        if imp is not None and (not isinstance(imp, dict) or
                                not all(isinstance(imp.get(k), str) and imp[k]
                                        for k in ("accept", "decline"))):
            problems.append(f"rows[{i}] ({rid}) impact needs both 'accept' and 'decline'")
        for key in ("context", "reasoning"):
            if key in r and not isinstance(r[key], str):
                problems.append(f"rows[{i}] ({rid}) {key} must be a string")
        links = r.get("links", [])
        if not isinstance(links, list):
            problems.append(f"rows[{i}] ({rid}) links must be a list")
        else:
            for link in links:
                if (not isinstance(link, dict) or not isinstance(link.get("href"), str)
                        or not isinstance(link.get("label"), str)):
                    problems.append(f"rows[{i}] ({rid}) link needs string href and label")
                    continue
                href = link["href"]
                try:
                    scheme = urllib.parse.urlsplit(href).scheme.lower()
                except ValueError:
                    scheme = "invalid"
                if (any(ord(c) < 32 for c in href) or
                        scheme not in ("", "http", "https", "file")):
                    problems.append(f"rows[{i}] ({rid}) link scheme is not permitted")
        if "tags" in r and (not isinstance(r["tags"], list) or
                             not all(isinstance(tag, str) for tag in r["tags"])):
            problems.append(f"rows[{i}] ({rid}) tags must be a list of strings")

    if review_bytes > MAX_REVIEW_TOTAL_BYTES:
        problems.append("review_assets exceed aggregate byte limit")

    for key in ("subtitle", "intro", "summary_intro", "audience", "scope", "storage_key"):
        if key in spec and not isinstance(spec[key], str):
            problems.append(f"{key} must be a string")
    filters = spec.get("filters", [])
    if not isinstance(filters, list):
        problems.append("filters must be a list")
    else:
        for filt in filters:
            if not isinstance(filt, dict) or not all(isinstance(filt.get(k), str) for k in ("id", "label")):
                problems.append("each filter needs string id and label")
                continue
            for key in ("tags", "severity"):
                if key in filt and (not isinstance(filt[key], list) or
                                    not all(isinstance(v, str) for v in filt[key])):
                    problems.append(f"filter {filt['id']} {key} must be a list of strings")

    gl = spec.get("glossary")
    if gl is not None:
        if not isinstance(gl, list):
            problems.append("glossary must be a list of {term, meaning}")
        else:
            for gi, g in enumerate(gl):
                if not isinstance(g, dict) or not g.get("term") or not g.get("meaning"):
                    problems.append(f"glossary[{gi}] needs both 'term' and 'meaning'")

    # Reader contract (see SKILL.md): a packet is a stranger-read document.
    # These are READER-class findings - warnings by default, fatal under
    # --strict-reader, which SKILL.md requires for packets handed to a
    # principal. Measured origin: a 15-row packet written in project-internal
    # language collected 0 decisions from the same principal whose plain-
    # language packets ran 30/30.
    if not spec.get("audience"):
        problems.append("READER: no 'audience' - name who reads this and what they already know, then write every row for that reader")
    missing_impact = [str(r.get("id")) for r in rows
                      if isinstance(r, dict) and not r.get("impact")]
    if missing_impact:
        problems.append(
            "READER: rows without an 'impact' block (what happens if they accept / decline, in the principal's terms): "
            + ", ".join(missing_impact))

    recommended = sum(1 for r in rows if isinstance(r, dict) and r.get("recommendation"))
    if recommended == 0:
        problems.append(
            "no row carries a recommendation. A packet without recommendations is a "
            "questionnaire, which means the analysis is not finished — see SKILL.md."
        )
    return problems


# ---------------------------------------------------------------------------
# The template
# ---------------------------------------------------------------------------
# `<meta charset>` sits in the first bytes deliberately. Without it, typographic
# punctuation in the rows renders as mojibake when the file is served over a plain
# local HTTP server. That defect reached a real packet; test_build_packet.py fixes it
# in place.

TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root {
  --bg: #ffffff; --panel: #f7f8fa; --panel-2: #eef1f5; --ink: #14181f; --ink-2: #4a5568;
  --ink-3: #6b7688; --line: #d8dee7; --line-2: #c3ccd8; --accent: #12395f;
  --danger: #b3261e; --warn: #9a6400; --ok: #1c6b3f; --info: #1c4f8f; --muted: #5b6472;
  --sel-fg: #ffffff; --chip: #e6ebf2; --focus: #2d6cdf;
  --mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
  --sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #10131a; --panel: #171b24; --panel-2: #1e2430; --ink: #e8ecf2; --ink-2: #b3bccb;
    --ink-3: #8b95a6; --line: #2a3140; --line-2: #3a4356; --accent: #7fb0e8;
    --danger: #ff8a80; --warn: #e8b04b; --ok: #6fcf97; --info: #7fb0e8; --muted: #9aa4b4;
    --sel-fg: #10131a; --chip: #232a37; --focus: #7fb0e8;
  }
}
:root[data-theme="dark"] {
  --bg: #10131a; --panel: #171b24; --panel-2: #1e2430; --ink: #e8ecf2; --ink-2: #b3bccb;
  --ink-3: #8b95a6; --line: #2a3140; --line-2: #3a4356; --accent: #7fb0e8;
  --danger: #ff8a80; --warn: #e8b04b; --ok: #6fcf97; --info: #7fb0e8; --muted: #9aa4b4;
  --sel-fg: #10131a; --chip: #232a37; --focus: #7fb0e8;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--ink); font-family: var(--sans);
  font-size: 15px; line-height: 1.55; -webkit-font-smoothing: antialiased;
}
.wrap { max-width: 1080px; margin: 0 auto; padding: 28px 20px 96px; }
header h1 { font-size: 25px; line-height: 1.2; margin: 0 0 6px; letter-spacing: -0.01em; }
header .sub { color: var(--ink-2); margin: 0 0 14px; }
header .intro { color: var(--ink-2); max-width: 74ch; margin: 0 0 20px; }
header .aud { color: var(--ink-3); font-size: 13px; margin: -10px 0 16px; }
details.gloss { margin: 0 0 20px; border: 1px solid var(--line); border-radius: 8px; background: var(--panel); }
details.gloss summary { cursor: pointer; padding: 8px 12px; font-size: 13px; color: var(--ink-2); }
details.gloss dl { margin: 0; padding: 4px 14px 12px; font-size: 13px; }
details.gloss dt { font-weight: 600; margin-top: 6px; }
details.gloss dd { margin: 0; color: var(--ink-2); }
.impact { border-left: 3px solid var(--line); padding: 6px 10px; margin: 8px 0; font-size: 13.5px; }
.impact b { color: var(--ink-2); }
.counts { display: flex; flex-wrap: wrap; gap: 8px; margin: 0 0 18px; }
.count {
  background: var(--panel); border: 1px solid var(--line); border-radius: 8px;
  padding: 8px 12px; min-width: 92px;
}
.count b { display: block; font-size: 20px; font-variant-numeric: tabular-nums; line-height: 1.15; }
.count span { font-size: 12px; color: var(--ink-3); }
.filters { display: flex; flex-wrap: wrap; gap: 7px; margin: 0 0 22px; }
.filters button {
  font: inherit; font-size: 13px; padding: 6px 12px; border-radius: 999px; cursor: pointer;
  background: var(--chip); color: var(--ink-2); border: 1px solid transparent;
}
.filters button[aria-pressed="true"] { background: var(--accent); color: var(--sel-fg); }
.filters button:focus-visible, .opts button:focus-visible, .bar button:focus-visible {
  outline: 2px solid var(--focus); outline-offset: 2px;
}
.row {
  position: relative; background: var(--panel); border: 1px solid var(--line);
  border-radius: 10px; padding: 15px 17px 15px 21px; margin: 0 0 12px; overflow: hidden;
}
.row::before {
  content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 4px; background: var(--line-2);
}
.row[data-sev="high"]::before   { background: var(--danger); }
.row[data-sev="medium"]::before { background: var(--warn); }
.row[data-sev="low"]::before    { background: var(--ok); }
.row[data-decided="yes"] { border-color: var(--line-2); }
.row[hidden] { display: none; }
.rid { font-family: var(--mono); font-size: 12px; color: var(--ink-3); }
.rlabel { font-weight: 650; margin: 2px 0 7px; font-size: 16.5px; line-height: 1.35; }
.rtext { color: var(--ink-2); margin: 0 0 9px; max-width: 82ch; }
.rtext.reason::before {
  content: "Recommendation "; font-weight: 650; color: var(--ink); letter-spacing: .01em;
}
.chips { display: flex; flex-wrap: wrap; gap: 6px; margin: 0 0 9px; }
.chip {
  font-size: 11.5px; font-family: var(--mono); background: var(--chip); color: var(--ink-3);
  padding: 2px 8px; border-radius: 999px;
}
.links { margin: 0 0 9px; font-size: 13.5px; }
.links a { color: var(--info); }
.dis {
  background: var(--panel-2); border-left: 3px solid var(--warn); border-radius: 0 7px 7px 0;
  padding: 9px 13px; margin: 0 0 11px; font-size: 14px;
}
.dis .h { font-weight: 650; font-size: 12px; text-transform: uppercase; letter-spacing: .05em;
  color: var(--warn); margin-bottom: 5px; }
.dis p { margin: 3px 0; color: var(--ink-2); }
.dis b { color: var(--ink); }
.opts { display: flex; flex-wrap: wrap; gap: 7px; align-items: stretch; margin: 11px 0 0; }
.opts button {
  font: inherit; font-size: 13.5px; padding: 7px 14px; border-radius: 7px; cursor: pointer;
  background: var(--bg); color: var(--ink-2); border: 1px solid var(--line-2);
  display: flex; flex-direction: column; align-items: flex-start; text-align: left;
  max-width: 100%;
}
/* The consequence sits ON the control, under its label: the principal reads what
   pressing this button does at the point of pressing it, not in a block above. */
.opts button .oconseq {
  font-size: 12px; font-weight: 400; line-height: 1.35; color: var(--ink-3);
  margin-top: 3px; max-width: 34ch;
}
.opts button[aria-pressed="true"] .oconseq { color: var(--sel-fg); opacity: .88; }
.opts button[aria-pressed="true"] { color: var(--sel-fg); border-color: transparent; font-weight: 600; }
.opts button[aria-pressed="true"][data-tone="danger"] { background: var(--danger); }
.opts button[aria-pressed="true"][data-tone="warn"]   { background: var(--warn); }
.opts button[aria-pressed="true"][data-tone="ok"]     { background: var(--ok); }
.opts button[aria-pressed="true"][data-tone="info"]   { background: var(--info); }
.opts button[aria-pressed="true"][data-tone="muted"]  { background: var(--muted); }
/* The recommendation is marked ON the control, so the eye lands on it and agreeing is
   one click. It is deliberately NOT pre-selected: a packet that starts fully decided
   cannot tell "I agreed" from "I never looked", and the summary would then report
   decisions nobody made. */
.opts button[data-recommended="true"] {
  border-color: var(--accent); border-width: 1.5px; font-weight: 600; color: var(--ink);
}
.opts button[data-recommended="true"] .olabel::before {
  content: "★ "; color: var(--accent); font-size: 11px; vertical-align: 1px;
}
.opts button[aria-pressed="true"][data-recommended="true"] .olabel::before { color: var(--sel-fg); }
.rec { font-size: 12px; color: var(--ink-3); margin-left: 2px; align-self: center; }
.note { margin-top: 9px; }
.note textarea {
  width: 100%; min-height: 38px; font: inherit; font-size: 14px; padding: 8px 10px;
  border-radius: 7px; border: 1px solid var(--line-2); background: var(--bg); color: var(--ink);
  resize: vertical;
}
.note textarea::placeholder { color: var(--ink-3); }
.bar {
  position: sticky; bottom: 0; margin-top: 26px; background: var(--panel);
  border: 1px solid var(--line); border-radius: 10px; padding: 14px 16px;
}
.barhead { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; justify-content: space-between; }
.barhead > b { font-size: 15px; font-variant-numeric: tabular-nums; }
.bar .hint { margin: 12px 0 8px; color: var(--ink-2); font-size: 14px; }
.bar textarea {
  width: 100%; min-height: 130px; font-family: var(--mono); font-size: 12.5px; padding: 10px;
  border-radius: 7px; border: 1px solid var(--line-2); background: var(--bg); color: var(--ink);
}
.bar .actions { display: flex; flex-wrap: wrap; gap: 9px; align-items: center; }
#summarywrap[hidden] { display: none; }
.bar button {
  font: inherit; font-size: 14px; font-weight: 600; padding: 9px 16px; border-radius: 7px;
  cursor: pointer; background: var(--accent); color: var(--sel-fg); border: none;
}
.bar button.secondary { background: var(--chip); color: var(--ink-2); font-weight: 500; }
#copystatus { font-size: 13px; color: var(--ink-2); }
@media (max-width: 620px) {
  .wrap { padding: 18px 13px 80px; }
  header h1 { font-size: 21px; }
  header .intro { font-size: 14px; }
  .count { min-width: 0; flex: 1 1 88px; padding: 7px 9px; }
  .count b { font-size: 17px; }
  /* Keep every control reachable on narrow screens, including long labels. */
  .bar { padding: 9px 11px; }
  .barhead { flex-wrap: wrap; gap: 8px; }
  .barhead > b { font-size: 13px; white-space: nowrap; }
  .bar .actions { gap: 6px; flex-wrap: wrap; min-width: 0; }
  .bar { max-height: 45vh; overflow: auto; }
  .bar button { padding: 7px 10px; font-size: 13px; }
  #copystatus { flex-basis: 100%; font-size: 12px; }
}

.review-material { border: 2px solid var(--line); border-radius: 10px; padding: 18px; margin: 16px 0; min-width: 0; }
.review-material h3 { margin: 0 0 12px; }
.review-asset { border-top: 1px solid var(--line); padding: 12px 0; min-width: 0; }
.review-delivery { display: grid; grid-template-columns: max-content minmax(0,1fr); gap: 6px 14px; }
.review-delivery dt { font-weight: 600; } .review-delivery dd { margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; }
.review-content { font-size: 1rem; line-height: 1.65; overflow-wrap: anywhere; }
.review-plain { white-space: pre-wrap; } .review-code { white-space: pre-wrap; overflow-wrap: anywhere; font-family: monospace; }
.review-exact textarea { width: 100%; box-sizing: border-box; resize: vertical; font: 0.9rem/1.5 monospace; }
.review-actions { display:flex; flex-wrap:wrap; align-items:center; gap:12px; margin-top:12px; }
.review-hint, .review-digest { font-size: 0.82rem; overflow-wrap: anywhere; } .review-status { width:100%; }
.review-asset img, .review-asset video { max-width:100%; height:auto; } .review-asset audio { max-width:100%; }
.review-unavailable { font-weight:600; } .opts button:disabled { cursor:not-allowed; opacity:0.55; }
.review-material summary, .review-material a { overflow-wrap:anywhere; }
.review-actions button { font: inherit; padding: 7px 10px; border: 1px solid var(--line-2); border-radius: 6px; color: var(--ink); background: var(--bg); cursor: pointer; }
.review-actions a { color: var(--info); }
.review-material :focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; }
.review-exact textarea { color: var(--ink); background: var(--bg); border: 1px solid var(--line-2); padding: 8px; }
@media (max-width:520px) { .review-material {padding:12px;} .review-delivery {grid-template-columns:1fr;} .review-delivery dd {margin-bottom:6px;} }
</style>
</head>
<body>
<div class="wrap">
<header>
  <h1>__TITLE__</h1>
  __SUBTITLE__
  __INTRO__
  __SCOPE__
  __AUDIENCE__
  __GLOSSARY__
</header>

<div class="counts" id="counts"></div>
<div class="filters" id="filters"></div>
<main id="rows"></main>

<section class="bar">
  <div class="barhead">
    <b id="progress">Your decisions</b>
    <div class="actions">
      <button id="copy" type="button">Copy summary</button>
      <button id="bulk" type="button" class="secondary" hidden>Take all remaining</button>
      <button id="toggle" type="button" class="secondary" aria-expanded="false" aria-controls="summarywrap">Show text</button>
      <button id="reset" type="button" class="secondary">Clear</button>
      <span id="copystatus" role="status" aria-live="polite"></span>
    </div>
  </div>
  <div id="summarywrap" hidden>
    <p class="hint">__SUMMARY_INTRO__</p>
    <textarea id="summary" readonly aria-label="Decision summary"></textarea>
  </div>
</section>
</div>

<script type="application/json" id="spec">__SPEC_JSON__</script>
<script>
(function () {
  "use strict";
  var SPEC = JSON.parse(document.getElementById("spec").textContent);
  var SPEC_DIGEST = "__CANONICAL_SPEC_SHA256__";
  var KEY = "decision-packet:" + SPEC.storage_key + ":" + SPEC_DIGEST;
  var rowsEl = document.getElementById("rows");
  var rowElements = [];

  function assetsReady(row) {
    return (row.review_assets || []).every(function (a) { return !('unavailable' in a.content); });
  }

  // ---- state -------------------------------------------------------------
  // localStorage can throw outright (private mode, blocked site data), so every
  // access is guarded and the packet stays fully usable with no persistence.
  var state = Object.create(null);
  var persists = true;
  try {
    var stored = JSON.parse(localStorage.getItem(KEY) || "{}");
    if (stored && typeof stored === "object" && !Array.isArray(stored)) {
      SPEC.rows.forEach(function (r) {
        if (!Object.prototype.hasOwnProperty.call(stored, r.id)) return;
        var s = stored[r.id];
        if (!s || typeof s !== "object" || Array.isArray(s)) return;
        var valid = assetsReady(r) && optionsFor(r).some(function (o) { return o.value === s.choice; });
        state[r.id] = { choice: valid ? s.choice : undefined,
          note: typeof s.note === "string" ? s.note : "",
          bulk: valid && s.choice === r.recommendation && s.bulk === true };
      });
    }
  } catch (e) { state = Object.create(null); persists = false; }

  function save() {
    if (!persists) return;
    try { localStorage.setItem(KEY, JSON.stringify(state)); }
    catch (e) { persists = false; }
  }
  function get(id) { return state[id] || {}; }
  function set(id, patch) {
    state[id] = Object.assign({}, get(id), patch);
    save(); render();
  }

  function optionsFor(row) { return row.options || SPEC.options; }
  function labelFor(row, value) {
    var o = optionsFor(row).filter(function (x) { return x.value === value; })[0];
    return o ? o.label : value;
  }
  function decisionOf(row) {
    var s = get(row.id);
    return assetsReady(row) && s.choice !== undefined ? s.choice : null;
  }
  function consequenceFor(row, o) {
    // What pressing this button does, shown under its label. An explicit
    // per-option text wins; otherwise the row's impact block maps "accept"
    // to the recommended option and "decline" to every other one.
    if (o.consequence) return o.consequence;
    if (!row.impact || !row.recommendation) return "";
    return row.recommendation === o.value ? row.impact.accept : row.impact.decline;
  }

  // ---- filters -----------------------------------------------------------
  var active = "all";
  function matches(row) {
    if (active === "all") return true;
    var f = (SPEC.filters || []).filter(function (x) { return x.id === active; })[0];
    if (!f) return true;
    if (f.undecided && decisionOf(row) === null) return true;
    if (f.decided && decisionOf(row) !== null) return true;
    if (f.disagreement && row.disagreement) return true;
    if (f.tags && (row.tags || []).some(function (t) { return f.tags.indexOf(t) >= 0; })) return true;
    if (f.severity && f.severity.indexOf(row.severity) >= 0) return true;
    return false;
  }

  function renderFilters() {
    var host = document.getElementById("filters");
    if (host.childElementCount) return;
    var all = [{ id: "all", label: "All " + SPEC.rows.length }].concat(SPEC.filters || []);
    all.forEach(function (f) {
      var b = document.createElement("button");
      b.type = "button"; b.textContent = f.label;
      b.setAttribute("aria-pressed", String(f.id === active));
      b.addEventListener("click", function () { active = f.id; render(); });
      host.appendChild(b);
    });
  }
  function syncFilters() {
    var all = [{ id: "all" }].concat(SPEC.filters || []);
    Array.prototype.forEach.call(document.querySelectorAll("#filters button"), function (b, i) {
      b.setAttribute("aria-pressed", String(all[i].id === active));
    });
  }

  // ---- counts ------------------------------------------------------------
  function renderCounts() {
    var decided = SPEC.rows.filter(function (r) { return decisionOf(r) !== null; }).length;
    var noted = SPEC.rows.filter(function (r) { return (get(r.id).note || "").trim(); }).length;
    var agreed = SPEC.rows.filter(function (r) {
      return r.recommendation && decisionOf(r) === r.recommendation;
    }).length;
    var overridden = SPEC.rows.filter(function (r) {
      var d = decisionOf(r);
      return d !== null && r.recommendation && d !== r.recommendation;
    }).length;
    var cards = [
      ["Items", SPEC.rows.length],
      ["Decided", decided],
      ["Remaining", SPEC.rows.length - decided],
      ["Took the recommendation", agreed],
      ["Overrode it", overridden],
      ["With a note", noted]
    ];
    if (SPEC.rows.some(function (r) { return r.disagreement; })) {
      cards.push(["Disputed", SPEC.rows.filter(function (r) { return r.disagreement; }).length]);
    }
    document.getElementById("counts").innerHTML = cards.map(function (c) {
      return '<div class="count"><b>' + c[1] + "</b><span>" + c[0] + "</span></div>";
    }).join("");
  }

  function element(tag, text, cls) {
    var node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (cls) node.className = cls;
    return node;
  }
  function limitedMarkdown(text, target) {
    // Deliberately small block grammar. No raw HTML, images, link expansion,
    // extensions or network access; all content enters through textContent.
    var lines = text.split(/\\r\\n|\\r|\\n/), paragraph = [], code = null, list = null;
    function flush() {
      if (paragraph.length) target.appendChild(element('p', paragraph.join('\\n')));
      paragraph = []; list = null;
    }
    lines.forEach(function (line) {
      if (/^```/.test(line)) {
        if (code === null) { flush(); code = []; }
        else { target.appendChild(element('pre', code.join('\\n'), 'review-code')); code = null; }
      } else if (code !== null) code.push(line);
      else if (!line.trim()) flush();
      else if (/^#{1,6} /.test(line)) { flush(); target.appendChild(element('h4', line.replace(/^#{1,6} /, ''))); }
      else if (/^[-*] /.test(line)) {
        if (!list) { flush(); list = element('ul'); target.appendChild(list); }
        list.appendChild(element('li', line.slice(2)));
      } else { if (list) flush(); paragraph.push(line); }
    });
    flush();
    if (code !== null) target.appendChild(element('pre', code.join('\\n'), 'review-code'));
  }
  function copyExact(ta, status, details, exactText) {
    if (details) details.open = true;
    ta.focus(); ta.select();
    try { ta.setSelectionRange(0, ta.value.length); } catch (e) {}
    var manual = ta.value === exactText ?
      'Copy not confirmed. Exact text is selected; press Cmd+C or Ctrl+C.' :
      'Copy not confirmed. The browser normalized line endings in the selection; download exact bytes.';
    status.textContent = 'Exact text selected; requesting copy…';
    var ok = false;
    try { if (ta.value === exactText) ok = document.execCommand('copy') === true; } catch (e) {}
    if (ok) { status.textContent = 'Browser reported copy success.'; return; }
    var settled = false;
    var timer = setTimeout(function () { settled = true; status.textContent = manual; }, 2000);
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        Promise.resolve(navigator.clipboard.writeText(exactText)).then(function () {
          if (!settled) { settled = true; clearTimeout(timer); status.textContent = 'Browser reported copy success.'; }
        }, function () { if (!settled) { settled = true; clearTimeout(timer); status.textContent = manual; } });
      } else { settled = true; clearTimeout(timer); status.textContent = manual; }
    } catch (e) { settled = true; clearTimeout(timer); status.textContent = manual; }
  }
  function renderReview(row) {
    var section = element('section', undefined, 'review-material');
    section.setAttribute('aria-label', 'Material for review: ' + row.label);
    section.appendChild(element('h3', 'Material for review'));
    var meta = element('dl', undefined, 'review-delivery');
    [['Revision', row.revision], ['Delivery format', row.delivery.format],
      ['Destinations', row.delivery.destinations.join('\\n') || 'None declared'],
      ['Attachments', row.delivery.attachments.join(', ') || 'None declared']].forEach(function (entry) {
      meta.appendChild(element('dt', entry[0])); meta.appendChild(element('dd', entry[1]));
    });
    section.appendChild(meta);
    section.appendChild(element('p', 'This material is separate from the recommendation. Byte integrity is not proof of authorship or approval.', 'review-hint'));
    row.review_assets.forEach(function (asset) {
      var box = element('section', undefined, 'review-asset');
      box.dataset.assetId = asset.id;
      box.setAttribute('aria-label', asset.title);
      box.appendChild(element('h4', asset.title));
      box.appendChild(element('p', 'Type: ' + asset.kind + ' · ID: ' + asset.id, 'review-hint'));
      if (asset.description) box.appendChild(element('p', asset.description));
      var content = asset.content;
      if ('unavailable' in content) {
        var missing = element('p', 'Unresolved material: ' + content.unavailable, 'review-unavailable');
        missing.setAttribute('role', 'status'); box.appendChild(missing);
        if (content.source) {
          var ref = element('a', 'Open external reference (unverified; network only when clicked)');
          ref.href = content.source; ref.target = '_blank'; ref.rel = 'noopener noreferrer';
          ref.referrerPolicy = 'no-referrer'; box.appendChild(ref);
        }
        box.appendChild(element('p', 'No content was fetched. Row choices are disabled; record a note or rebuild with verified bytes.'));
      } else {
        box.appendChild(element('p', 'Bound SHA-256: ' + content.sha256, 'review-digest'));
        var blob, filename, status = element('span', '', 'review-status');
        status.setAttribute('role', 'status'); status.setAttribute('aria-live', 'polite');
        var actions = element('div', undefined, 'review-actions');
        if ('text' in content) {
          var view = element('div', undefined, 'review-content');
          if (asset.kind === 'markdown') limitedMarkdown(content.text, view);
          else view.appendChild(element(asset.kind === 'code' ? 'pre' : 'div', content.text,
            asset.kind === 'code' ? 'review-code' : 'review-plain'));
          box.appendChild(view);
          var details = element('details', undefined, 'review-exact');
          details.appendChild(element('summary', 'Exact source text and manual copy'));
          var ta = element('textarea'); ta.value = content.text; ta.readOnly = true; ta.rows = 8;
          ta.setAttribute('aria-label', 'Exact source: ' + asset.title); details.appendChild(ta); box.appendChild(details);
          var copy = element('button', 'Copy exact text'); copy.type = 'button';
          copy.addEventListener('click', function () { copyExact(ta, status, details, content.text); }); actions.appendChild(copy);
          blob = new Blob([content.text], {type: 'text/plain;charset=utf-8'}); filename = asset.id + '.txt';
        } else {
          var bytes = atob(content.base64), values = new Uint8Array(bytes.length);
          for (var i = 0; i < bytes.length; i++) values[i] = bytes.charCodeAt(i);
          blob = new Blob([values], {type: content.media_type}); filename = asset.filename;
          box.appendChild(element('p', content.media_type + ' · ' + content.size + ' bytes', 'review-hint'));
          if (asset.kind !== 'document') {
            var media = element(asset.kind === 'image' ? 'img' : asset.kind);
            if (asset.kind === 'image') { media.alt = asset.description; media.loading = 'lazy'; }
            else { media.controls = true; media.preload = 'none'; media.setAttribute('aria-label', asset.description); }
            media.src = 'data:' + content.media_type + ';base64,' + content.base64;
            media.addEventListener('error', function () { status.textContent = 'Preview unavailable in this browser; download the bound bytes to inspect them.'; });
            box.appendChild(media);
          } else box.appendChild(element('p', 'Document preview unavailable here. Download the bound PDF and inspect it in a document reader. No embedded document code is executed.', 'review-unavailable'));
        }
        try {
          var url = URL.createObjectURL(blob), download = element('a', 'Download exact bytes');
          download.href = url; download.download = filename; actions.appendChild(download);
          if ('text' in content || asset.kind === 'image') {
            var open = element('a', 'Open bound content'); open.href = url; open.target = '_blank';
            open.rel = 'noopener noreferrer'; actions.appendChild(open);
          }
          window.addEventListener('pagehide', function () { URL.revokeObjectURL(url); }, {once: true});
        } catch (e) { status.textContent = 'This browser cannot create a download; exact text remains readable where supplied.'; }
        actions.appendChild(status); box.appendChild(actions);
      }
      section.appendChild(box);
    });
    return section;
  }

  // ---- rows --------------------------------------------------------------
  function buildRow(row) {
    var el = document.createElement("article");
    el.className = "row";
    el.dataset.sev = row.severity || "none";
    el.dataset.id = row.id;

    var head = '<div class="rid">' + esc(row.id) + "</div>" +
               '<div class="rlabel">' + esc(row.label) + "</div>";
    if (row.prior_position) {
      var p = row.prior_position;
      head += '<section class="prior-position" aria-label="Prior principal position">' +
        '<b>Prior principal position</b><p class="prior-statement" style="white-space:pre-wrap">' +
        esc(p.statement) + '</p><p class="prior-source" style="white-space:pre-wrap">Source: ' + esc(p.source_ref) + '</p>';
      [["Evidence supporting it", p.evidence_for], ["Evidence against it", p.evidence_against]].forEach(function (part) {
        head += '<b>' + part[0] + '</b><ul>';
        if (!part[1].length) head += '<li>No evidence recorded in this packet; coverage is unknown.</li>';
        part[1].forEach(function (entry) {
          head += '<li style="white-space:pre-wrap">' + esc(entry.statement) + '<br>Source: ' + esc(entry.source_ref) + '</li>';
        });
        head += '</ul>';
      });
      head += '</section>';
    }
    if (row.context)   head += '<p class="rtext">' + esc(row.context) + "</p>";
    if ((row.tags || []).length) {
      head += '<div class="chips">' + row.tags.map(function (t) {
        return '<span class="chip">' + esc(t) + "</span>";
      }).join("") + "</div>";
    }
    if ((row.links || []).length) {
      head += '<div class="links">' + row.links.map(function (l) {
        return '<a href="' + esc(l.href) + '" target="_blank" rel="noopener">' + esc(l.label) + "</a>";
      }).join(" · ") + "</div>";
    }
    if (row.impact) {
      head += '<div class="impact"><b>If you take the recommendation:</b> ' + esc(row.impact.accept) +
              '<br><b>If you don\u2019t:</b> ' + esc(row.impact.decline) + "</div>";
    }
    if (row.disagreement) {
      var d = row.disagreement;
      head += '<div class="dis"><div class="h">Unresolved disagreement — your call</div>' +
        "<p><b>" + esc(d.a.who) + ":</b> " + esc(d.a.view) + "</p>" +
        "<p><b>" + esc(d.b.who) + ":</b> " + esc(d.b.view) + "</p></div>";
    }
    if (row.reasoning) head += '<p class="rtext reason">' + esc(row.reasoning) + "</p>";
    el.innerHTML = head;

    if (row.review_assets) {
      var anchor = el.querySelector(".prior-position") || el.querySelector(".rlabel");
      el.insertBefore(renderReview(row), anchor.nextSibling);
    }

    var opts = document.createElement("div");
    opts.className = "opts";
    optionsFor(row).forEach(function (o) {
      var b = document.createElement("button");
      b.type = "button";
      b.dataset.tone = o.tone || "info";
      b.dataset.value = o.value;
      b.disabled = !assetsReady(row);
      if (b.disabled) b.title = "Resolve unavailable review material before choosing";
      var lab = document.createElement("span");
      lab.className = "olabel"; lab.textContent = o.label;
      b.appendChild(lab);
      var text = consequenceFor(row, o);
      if (text) {
        var why = document.createElement("span");
        why.className = "oconseq"; why.textContent = text;
        b.appendChild(why);
      }
      if (row.recommendation === o.value) {
        b.dataset.recommended = "true";
        b.title = "The agent recommends this";
      }
      b.addEventListener("click", function () {
        // An individual click always clears the bulk flag: touching a row IS
        // considering it, and the record must not keep calling it a bulk accept.
        set(row.id, {
          choice: decisionOf(row) === o.value ? undefined : o.value,
          bulk: false
        });
      });
      opts.appendChild(b);
    });
    if (row.recommendation) {
      var hint = document.createElement("span");
      hint.className = "rec";
      hint.textContent = "recommended: " + labelFor(row, row.recommendation);
      opts.appendChild(hint);
    }
    el.appendChild(opts);

    var note = document.createElement("div");
    note.className = "note";
    var ta = document.createElement("textarea");
    ta.rows = 1;
    ta.placeholder = "Anything the buttons cannot say…";
    ta.value = get(row.id).note || "";
    ta.setAttribute("aria-label", "Note on " + row.id);
    ta.addEventListener("input", function () {
      state[row.id] = Object.assign({}, get(row.id), { note: ta.value });
      save(); renderCounts(); renderSummary();
    });
    note.appendChild(ta);
    el.appendChild(note);
    return el;
  }

  function render() {
    renderFilters(); syncFilters(); renderCounts();
    if (!rowsEl.childElementCount) {
      rowElements = SPEC.rows.map(function (r) {
        var el = buildRow(r);
        rowsEl.appendChild(el);
        return el;
      });
    }
    SPEC.rows.forEach(function (r, index) {
      // IDs remain exact data, including control characters. Retain the DOM
      // reference instead of converting an ID into CSS selector source.
      var el = rowElements[index];
      el.hidden = !matches(r);
      var d = decisionOf(r);
      el.dataset.decided = d === null ? "no" : "yes";
      Array.prototype.forEach.call(el.querySelectorAll(".opts button"), function (b) {
        b.setAttribute("aria-pressed", String(b.dataset.value === d));
      });
    });
    renderSummary();
  }

  // ---- summary -----------------------------------------------------------
  function renderSummary() {
    // Keep note text stable across clipboard/editor line-ending and trailing-
    // whitespace transport. Indentation and spacing within a line still matter.
    function normalizeNote(note) {
      return note.replace(/\\r\\n?/g, "\\n").split("\\n").map(function (line) {
        return line.trimEnd();
      }).join("\\n").trim();
    }
    var lines = [SPEC.title, "=".repeat(SPEC.title.length), ""];
    var decided = 0;
    SPEC.rows.forEach(function (r) {
      var s = get(r.id), d = decisionOf(r);
      if (d !== null) decided++;
      var mark = d === null ? "— not yet decided" : labelFor(r, d);
      if (d !== null && r.recommendation) {
        if (d !== r.recommendation) {
          mark += "  (OVERRODE: recommended " + labelFor(r, r.recommendation) + ")";
        } else {
          // A bulk acceptance is a different fact from an individual one, and the
          // agent reading this paste must not read the first as the second.
          mark += s.bulk ? "  (accepted in bulk)" : "  (took the recommendation)";
        }
      }
      lines.push(r.id + "  " + r.label);
      lines.push("    -> " + mark);
      var note = normalizeNote(s.note || "");
      if (note) lines.push("    note: " + note);
      lines.push("");
    });
    lines.push("Decided " + decided + " of " + SPEC.rows.length + ".");
    var bulk = SPEC.rows.filter(function (r) { return get(r.id).bulk; }).length;
    if (bulk) {
      lines.push(bulk + " of those were accepted in bulk rather than considered one by one — " +
                 "weight them accordingly.");
    }
    if (!persists) lines.push("(This browser blocked local storage, so nothing was saved between sittings.)");
    lines.push("Decision packet binding v2: " + JSON.stringify({
      schema_version: 2, spec_sha256: SPEC_DIGEST,
      selections: SPEC.rows.map(function (r) {
        var s = get(r.id);
        return {id: r.id, choice: decisionOf(r), note: normalizeNote(s.note || ""), bulk: s.bulk === true};
      }), storage_blocked: !persists
    }));
    document.getElementById("summary").value = lines.join("\\n");
    document.getElementById("progress").textContent =
      decided + " of " + SPEC.rows.length + " decided";

    // The bulk control exists so that a genuinely routine set (forty patch bumps) does
    // not cost forty considered clicks. It is deliberately NOT a default state: an
    // affirmative, labelled gesture leaves an honest record, whereas a pre-selected
    // recommendation would make "I agreed" indistinguishable from "I never looked".
    var remaining = SPEC.rows.filter(function (r) {
      return r.recommendation && assetsReady(r) && decisionOf(r) === null;
    }).length;
    var bulkBtn = document.getElementById("bulk");
    bulkBtn.hidden = remaining === 0;
    bulkBtn.textContent = "Take all remaining (" + remaining + ")";
  }

  function revealSummary() {
    var wrap = document.getElementById("summarywrap");
    var btn = document.getElementById("toggle");
    wrap.hidden = false;
    btn.setAttribute("aria-expanded", "true");
    btn.textContent = "Hide text";
  }

  // ---- copy --------------------------------------------------------------
  // Order matters and is load-bearing. Selecting FIRST guarantees a manual
  // Cmd/Ctrl+C always works, even when both programmatic paths are blocked —
  // as they are inside a sandboxed artifact iframe with no clipboard-write
  // permission. A copy control that fails silently is a bug; this one always
  // says which path it took.
  function copySummary() {
    var ta = document.getElementById("summary");
    var status = document.getElementById("copystatus");
    // A hidden textarea cannot be selected, and selection is the fallback that always
    // works — so reveal before doing anything else.
    revealSummary();
    ta.removeAttribute("readonly");
    ta.focus(); ta.select();
    try { ta.setSelectionRange(0, ta.value.length); } catch (e) {}
    ta.setAttribute("readonly", "");

    // Say something SYNCHRONOUSLY. The async clipboard path below may resolve late or
    // never, and an empty status in the meantime is exactly the silent failure this
    // control exists to avoid. Every later branch overwrites this line.
    status.textContent = "Selected — copying…";

    var ok = false;
    try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
    if (ok) { status.textContent = "Copied. Paste it back in one message."; return; }

    var settled = false;
    function blocked() {
      if (settled) return;
      settled = true;
      status.textContent = "Copy not confirmed — the text is selected, so press " +
        (navigator.platform.indexOf("Mac") >= 0 ? "Cmd+C" : "Ctrl+C") + ".";
    }
    var timer = setTimeout(blocked, 2000);
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        Promise.resolve(navigator.clipboard.writeText(ta.value)).then(function () {
          if (!settled) { settled = true; clearTimeout(timer); status.textContent = "Copied. Paste it back in one message."; }
        }, function () { clearTimeout(timer); blocked(); });
        return;
      }
    } catch (e) {}
    clearTimeout(timer); blocked();
  }

  document.getElementById("copy").addEventListener("click", copySummary);
  document.getElementById("bulk").addEventListener("click", function () {
    var pending = SPEC.rows.filter(function (r) {
      return r.recommendation && assetsReady(r) && decisionOf(r) === null;
    });
    if (!pending.length) return;
    if (!window.confirm(
      "Accept the recommendation on " + pending.length + " remaining item" +
      (pending.length === 1 ? "" : "s") + " without deciding them individually?\\n\\n" +
      "They will be marked as accepted in bulk in the summary, so the difference stays visible."
    )) return;
    pending.forEach(function (r) {
      state[r.id] = Object.assign({}, get(r.id), { choice: r.recommendation, bulk: true });
    });
    save(); render();
    document.getElementById("copystatus").textContent =
      pending.length + " accepted in bulk.";
  });

  document.getElementById("toggle").addEventListener("click", function () {
    var wrap = document.getElementById("summarywrap");
    if (wrap.hidden) { revealSummary(); return; }
    wrap.hidden = true;
    this.setAttribute("aria-expanded", "false");
    this.textContent = "Show text";
  });
  document.getElementById("reset").addEventListener("click", function () {
    if (!window.confirm("Clear every saved answer in this packet?")) return;
    state = Object.create(null);
    try { localStorage.removeItem(KEY); } catch (e) {}
    rowsEl.innerHTML = "";
    document.getElementById("copystatus").textContent = "Cleared.";
    render();
  });

  function esc(s) {
    return String(s === undefined || s === null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
  render();
})();
</script>
</body>
</html>
"""


def build(spec: dict) -> str:
    hard = [p for p in validate(spec) if not p.startswith(("NOTE:", "READER:"))]
    if hard:
        raise ValueError("invalid spec: " + "; ".join(hard))
    canonical_digest = spec_digest(spec)
    title = spec["title"]
    spec = dict(spec)
    spec.setdefault("storage_key", slugify(title))
    spec.setdefault("filters", [])
    # Script data is parsed by HTML before JSON. Escaping every '<' prevents
    # both closing tags and the <!--<script> double-escaped tokenizer state.
    # JSON.parse restores the exact values; canonical-spec binding is unchanged.
    payload = json.dumps(spec, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c")
    fields = {"__TITLE__": html.escape(title), "__SPEC_JSON__": payload,
              "__CANONICAL_SPEC_SHA256__": canonical_digest}
    for slot, key, cls in (("__SUBTITLE__", "subtitle", "sub"),
                           ("__INTRO__", "intro", "intro"),
                           ("__SCOPE__", "scope", "intro"),
                           ("__AUDIENCE__", "audience", "aud")):
        value = spec.get(key)
        prefix = "Written for: " if key == "audience" else "Scope: " if key == "scope" else ""
        fields[slot] = f'<p class="{cls}">{prefix}{html.escape(value)}</p>' if value else ""
    gl = spec.get("glossary") or []
    items = "".join(f"<dt>{html.escape(str(g['term']))}</dt><dd>{html.escape(str(g['meaning']))}</dd>"
                    for g in gl)
    fields["__GLOSSARY__"] = (f'<details class="gloss"><summary>Terms used below ({len(gl)})</summary>'
                               f'<dl>{items}</dl></details>') if gl else ""
    fields["__SUMMARY_INTRO__"] = html.escape(spec.get("summary_intro") or
        "Work through the rows, then copy this and paste it back in one message.")
    # Single substitution pass: data containing a template token stays data.
    out = re.sub("|".join(re.escape(key) for key in fields), lambda m: fields[m.group()], TEMPLATE)
    # This existing marker checks embedded-payload integrity, not authorship or
    # user authority. The separate canonical digest binds the filed input spec.
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    marker = f"<!-- synthesis-decision-packet spec-sha256:{digest} -->\n"
    head, sep, tail = out.partition("</title>\n")
    if not sep:
        raise RuntimeError("build_packet: template lost its </title> close")
    page = head + sep + marker + tail
    if len(page.encode("utf-8")) > MAX_GENERATED_HTML_BYTES:
        raise ValueError("generated packet exceeds the context-doctor file byte limit")
    return page


def assert_active_spec(directory: pathlib.Path, digest: str, spec: dict | None = None) -> None:
    """Filing a retired exact spec is refused; parsing history remains read-only."""
    lifecycle = pathlib.Path(__file__).resolve().parents[2] / "synthesis-context-lifecycle/scripts"
    if str(lifecycle) not in sys.path:
        sys.path.insert(0, str(lifecycle))
    import record_succession
    record_succession.assert_active_spec(directory, digest,
        record_succession.canonical_digest(record_succession.runtime_spec(spec)) if spec is not None else None)


def file_packet(spec: dict, page: str, directory: pathlib.Path, date: str) -> tuple[pathlib.Path, pathlib.Path]:
    """File canonical spec bytes and page, preserving every previous version."""
    assert_active_spec(directory, spec_digest(spec), spec)
    stem = f"{date}-{slugify(spec['title'])}"
    spec_bytes, page_bytes = canonical_spec_bytes(spec), page.encode("utf-8")
    spec_copy, page_copy = directory / f"{stem}-spec.json", directory / f"{stem}.html"
    if spec_copy.is_symlink() or page_copy.is_symlink():
        raise ValueError("refusing symlink packet output")
    if any(path.exists() and path.read_bytes() != data for path, data in
           ((spec_copy, spec_bytes), (page_copy, page_bytes))):
        # Include the page digest too: a generator upgrade can change the page
        # without changing the spec. Neither historic representation is replaced.
        revision = hashlib.sha256(spec_bytes + page_bytes).hexdigest()
        stem += "-" + revision
        spec_copy, page_copy = directory / f"{stem}-spec.json", directory / f"{stem}.html"
    for path in (spec_copy, page_copy):
        if path.is_symlink():
            raise ValueError(f"refusing symlink output: {path}")
    write_preserved(spec_copy, spec_bytes)
    write_preserved(page_copy, page_bytes)
    return spec_copy, page_copy


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", nargs="?", help="path to the JSON spec ('-' for stdin)")
    ap.add_argument("-o", "--out", help="output .html path; an existing different file is preserved")
    ap.add_argument("--stdout", action="store_true", help="write the HTML to stdout")
    ap.add_argument("--schema", action="store_true", help="print the spec schema and exit")
    ap.add_argument("--allow-small", action="store_true",
                    help="build even with fewer than five rows (see the anti-trigger)")
    ap.add_argument("--strict-reader", action="store_true",
                    help="make reader-contract findings (missing audience/impact, option labels "
                         "that name no consequence) fatal; SKILL.md requires this for packets "
                         "handed to a principal")
    ap.add_argument("--file-into", metavar="DIR",
                    help="after a successful build, file a dated copy of the spec "
                         "(<date>-<slug>-spec.json) and of the page (<date>-<slug>.html) into DIR, "
                         "the owning project's resources/artifacts/ directory; DIR must exist")
    ap.add_argument("--date", metavar="YYYY-MM-DD",
                    help="the date in the filed names (default: today); requires --file-into")
    args = ap.parse_args()

    if args.schema:
        print(SCHEMA)
        return 0
    if not args.spec:
        ap.error("a spec path is required (or --schema)")
    if args.date and not args.file_into:
        ap.error("--date requires --file-into")
    if args.date and parse_iso_date(args.date) is None:
        ap.error(f"--date {args.date!r} is not a calendar date in YYYY-MM-DD form")
    filing_dir = None
    if args.file_into:
        filing_dir = pathlib.Path(args.file_into)
        if not filing_dir.is_dir():
            print(f"--file-into: {filing_dir} is not an existing directory - pass the owning "
                  "project's resources/artifacts/ directory and create it first", file=sys.stderr)
            return 2

    try:
        raw = read_packet_input(None if args.spec == "-" else pathlib.Path(args.spec))
        spec = strict_json(raw.decode("utf-8"))
    except (OSError, ValueError, UnicodeError) as exc:
        print(f"cannot read valid spec JSON: {exc}", file=sys.stderr)
        return 2

    problems = validate(spec)
    hard = [p for p in problems if not p.startswith(("NOTE:", "READER:"))]
    soft = [p for p in problems if p.startswith("NOTE:")]
    reader = [p for p in problems if p.startswith("READER:")]
    for p in soft + reader:
        print(p, file=sys.stderr)
    if soft and not args.allow_small:
        hard.append("refusing to build a sub-five-row packet without --allow-small")
    if reader and args.strict_reader:
        hard.append("reader contract unmet (--strict-reader): see READER findings above")
    if hard:
        print("\nwill not build:", file=sys.stderr)
        for p in hard:
            print("  - " + p, file=sys.stderr)
        return 2

    try:
        out = build(spec)
        reports = []
        if args.out:
            dest = pathlib.Path(args.out)
            dest.parent.mkdir(parents=True, exist_ok=True)
            write_preserved(dest, out.encode("utf-8"))
            reports.append(f"{dest}  ({len(out.encode('utf-8')):,} bytes, {len(spec['rows'])} rows)")
        if filing_dir is not None:
            date = parse_iso_date(args.date) if args.date else datetime.date.today().isoformat()
            reports.extend(f"filed {copy}" for copy in file_packet(spec, out, filing_dir, date))
    except (OSError, ValueError, UnicodeError) as exc:
        print(f"packet build refused: {exc}", file=sys.stderr)
        return 2
    # Do not emit a successful page or status before all requested writes finish.
    report = sys.stderr if args.stdout else sys.stdout
    if args.stdout or (not args.out and filing_dir is None):
        sys.stdout.write(out)
    for message in reports:
        print(message, file=report)
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Extract candidate commitments from a saved meeting transcript.

Step 4.7 (§5b): the verifier proves the transcript is faithful; nothing
asked whether anything in it is owed. Rajiv's "Oh of course" to Paul
Smurl's celebration of life sat eleven months in a filed transcript no
one read for obligations. This scanner finds first-person commitment
shapes — I'll, I will, of course, let me, send me, I promise, by <date> —
with their timestamps and speakers, and prints them as CANDIDATES. It
never creates tasks, files, or calendar entries; the agent presents the
list for the principal to confirm in the same turn as the filing.

Dialogue-line recognition reuses the verifier's speaker patterns, so
every transcript shape the verifier accepts (Gemini bold/bare names,
Plaud timestamp-led lines, undiarized standalone-timestamp runs) scans
here too.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import verify_transcripts

SCRIPT_VERSION = "0.11.0"

_TS_IN_BRACKET = re.compile(r"\[\s*(\d{1,2}:\d{2}(?::\d{2})?)")

_COMMITMENT_SHAPES = (
    ("i-will", re.compile(r"\bi(?:'ll| will)\b", re.IGNORECASE)),
    ("of-course", re.compile(r"\bof course\b", re.IGNORECASE)),
    ("let-me", re.compile(r"\blet me\b", re.IGNORECASE)),
    ("send-me", re.compile(r"\bsend me\b", re.IGNORECASE)),
    ("i-promise", re.compile(r"\bi promise\b", re.IGNORECASE)),
    (
        "by-date",
        re.compile(
            r"\bby\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday"
            r"|january|february|march|april|may|june|july|august|september|october|november|december"
            r"|tomorrow|tonight|today|next week|\d{1,2}(?:[/:]\d{1,2})?)\b",
            re.IGNORECASE,
        ),
    ),
)

QUOTE_CHARS = 200

OWNER_RULES = ("1", "2", "3", "candidate-confirmed")


def stamp(owner: str, owner_rule: str) -> dict[str, str]:
    """Build the §3 ownership stamp for a principal-confirmed commitment.

    The scanner prints candidates; the principal confirms; this pins the
    exact `owner:`/`owner_rule:` lines the agent records with the item so
    a later seat sees why it landed where it did. Fail-closed: a blank
    owner or an unknown rule is a refusal, never a guessed stamp.
    """
    if not owner.strip():
        raise ValueError("owner names the owning workspace; it cannot be blank")
    if owner_rule not in OWNER_RULES:
        raise ValueError(f"owner_rule must be one of {', '.join(OWNER_RULES)}")
    return {"owner": owner.strip(), "owner_rule": owner_rule}


def _dialogue_lines(text: str) -> list[tuple[str | None, str, str]]:
    """Yield (timestamp, speaker, utterance) for each dialogue line.

    Timestamp-led lines carry their own; in undiarized runs a standalone
    timestamp line stamps the next dialogue line; bare-name lines without
    either report None rather than a guessed position.
    """
    found: list[tuple[str | None, str, str]] = []
    pending: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if verify_transcripts.STANDALONE_TS_RE.match(raw_line):
            bare = verify_transcripts.TIMESTAMP_RE.search(line)
            pending = bare.group(0) if bare else None
            continue
        match = verify_transcripts.SPEAKER_RE.match(raw_line)
        if not match:
            continue
        bracket = _TS_IN_BRACKET.search(line)
        timestamp = bracket.group(1) if bracket else pending
        pending = None
        speaker = match.group(0).strip()
        speaker = re.sub(r"^\*{0,2}\[.*?\]\s*", "", speaker)
        speaker = speaker.strip("*").rstrip(":").strip().rstrip("*").strip()
        utterance = raw_line[match.end():].strip()
        found.append((timestamp, speaker, utterance))
    return found


def scan(text: str, *, speaker: str | None = None) -> dict:
    """Scan transcript text; return counts plus candidate commitments."""
    candidates: list[dict] = []
    dialogue = 0
    for timestamp, line_speaker, utterance in _dialogue_lines(text):
        dialogue += 1
        if speaker is not None and speaker.lower() not in line_speaker.lower():
            continue
        lowered = utterance
        for shape, pattern in _COMMITMENT_SHAPES:
            if pattern.search(lowered):
                candidates.append(
                    {
                        "timestamp": timestamp,
                        "speaker": line_speaker,
                        "shape": shape,
                        "quote": utterance[:QUOTE_CHARS],
                    }
                )
                break
    return {"dialogue_lines": dialogue, "candidates": candidates}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("transcript", type=Path, nargs="?", help="saved .md transcript file")
    parser.add_argument("--speaker", default=None, help="only flag this speaker (substring match)")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--stamp", action="store_true", help="print an ownership stamp instead of scanning")
    parser.add_argument("--owner", default=None, help="owning workspace for --stamp")
    parser.add_argument("--owner-rule", default=None, help="1, 2, 3, or candidate-confirmed")
    args = parser.parse_args(argv)
    if args.stamp:
        if args.owner is None or args.owner_rule is None:
            print("extract-commitments refused: --stamp needs --owner and --owner-rule", file=sys.stderr)
            return 2
        try:
            stamped = stamp(args.owner, args.owner_rule)
        except ValueError as exc:
            print(f"extract-commitments refused: {exc}", file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(stamped, indent=2, sort_keys=True))
        else:
            print(f"owner: {stamped['owner']}")
            print(f"owner_rule: {stamped['owner_rule']}")
        return 0
    if args.transcript is None:
        print("extract-commitments refused: a transcript file is required", file=sys.stderr)
        return 2
    try:
        text = args.transcript.read_text(encoding="utf-8")
    except (OSError, ValueError) as exc:
        print(f"extract-commitments refused: cannot read {args.transcript}: {exc}", file=sys.stderr)
        return 2
    result = scan(text, speaker=args.speaker)
    candidates = result["candidates"]
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"extract-commitments {SCRIPT_VERSION}: {result['dialogue_lines']} dialogue lines")
        if result["dialogue_lines"] == 0:
            print("note: no dialogue lines found — is this a verbatim transcript?")
        if not candidates:
            print("no candidate commitments")
        for candidate in candidates:
            when = candidate["timestamp"] or "no timestamp"
            print(f"[{when}] {candidate['speaker']} ({candidate['shape']}): {candidate['quote']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

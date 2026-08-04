"""Regression tests for verify_transcripts.py speaker/timestamp detection.

The completeness gate exists to make it impossible to save a meeting SUMMARY in
place of the verbatim transcript. That gate is only as good as its detectors, and
both directions of failure are costly:

  - False NEGATIVE (a summary passes) — the primary record is silently lost.
  - False POSITIVE (a real transcript fails) — the gate cries wolf, and an agent
    under time pressure learns to route around it. This is how fail-closed
    controls get disabled in practice.

Both live Plaud transcripts on 2026-08-04 were flagged INCOMPLETE despite carrying
98 and 163 timestamps of real diarized dialogue: v0.5.0 added Plaud support but
matched only the UNSPACED range form `[00:00-00:08]`, while Plaud actually emits
`**[00:00 - 00:08] Name:**` with spaces. These tests pin every real-world shape.

Run: python3 test_verify_transcripts.py
"""

import importlib.util
import pathlib
import sys

_spec = importlib.util.spec_from_file_location(
    "verify_transcripts", pathlib.Path(__file__).parent / "verify_transcripts.py"
)
v = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(v)


# (label, line, should_match)
SPEAKER_CASES = [
    # --- Plaud: timestamp BEFORE the name, bold-wrapped ---
    ("plaud spaced hyphen range", "**[00:00 - 00:08] Rajiv Pant:** Oh okay great", True),
    ("plaud unspaced range", "**[00:00-00:08] Rajiv Pant:** Oh okay", True),
    ("plaud en-dash range", "**[00:00 – 00:08] Rajiv Pant:** Oh okay", True),
    ("plaud em-dash range", "**[00:00 — 00:08] Rajiv Pant:** Oh okay", True),
    ("plaud single timestamp", "**[00:00] Rajiv Pant:** Oh okay", True),
    ("plaud undiarized Speaker N", "**[00:16 - 00:26] Speaker 2:** Yeah.", True),
    ("plaud hour-length range", "**[1:02:03 - 1:02:44] Ana Laura Volkman:** Hi", True),
    ("plaud inner padding", "**[ 00:00 - 00:08 ] Rajiv Pant:** Hi", True),
    ("plaud without bold", "[00:00 - 00:08] Rajiv Pant: Hi", True),
    # --- Gemini: bare name, no timestamp prefix ---
    ("gemini plain name", "Rajiv Pant: So AI knowledge", True),
    ("gemini bold name", "**Kathryn Sheplavy:** thanks Efren", True),
    ("gemini three-part name", "Ana Laura Volkman: Good morning", True),
    # --- Negative controls: a SUMMARY must never look like dialogue ---
    ("summary bullet w/ inline ts", "The team discussed the roadmap (00:05:12).", False),
    ("summary sentence", "* Rajiv Pant discussed integrating the tool (00:01:02).", False),
    ("bare url", "https://example.com/doc: see here", False),
]

STANDALONE_TS_CASES = [
    ("bare ts line", "00:01:31", True),
    ("bracketed ts line", "[00:01:31]", True),
    ("bold ts line", "**00:01:31**", True),
    ("indented ts line", "   00:01:31   ", True),
    ("inline ts in prose", "discussed X (00:05:12) and moved on", False),
]


def main() -> int:
    failures = []

    for label, line, want in SPEAKER_CASES:
        got = bool(v.SPEAKER_RE.search(line))
        if got != want:
            failures.append(f"SPEAKER_RE {label!r}: expected {want}, got {got} — {line!r}")

    for label, line, want in STANDALONE_TS_CASES:
        got = bool(v.STANDALONE_TS_RE.search(line))
        if got != want:
            failures.append(f"STANDALONE_TS_RE {label!r}: expected {want}, got {got} — {line!r}")

    # End-to-end: a realistic Plaud transcript body must clear the default thresholds.
    plaud_body = "\n".join(
        f"**[{m:02d}:00 - {m:02d}:30] {'Rajiv Pant' if m % 2 else 'Speaker 2'}:** line {m}"
        for m in range(1, 16)
    )
    if v.count_speaker_lines(plaud_body) < 10:
        failures.append(
            f"realistic Plaud body counted {v.count_speaker_lines(plaud_body)} speaker lines, need >=10"
        )

    # End-to-end: a summary-shaped body must NOT clear them.
    summary_body = "\n".join(
        f"* Topic {m} was discussed at length by the group (00:{m:02d}:12)." for m in range(1, 16)
    )
    if v.count_speaker_lines(summary_body) >= 10:
        failures.append(
            f"summary body counted {v.count_speaker_lines(summary_body)} speaker lines, must stay <10"
        )

    total = len(SPEAKER_CASES) + len(STANDALONE_TS_CASES) + 2
    if failures:
        print(f"FAILED — {len(failures)} of {total} checks:")
        for f in failures:
            print("  -", f)
        return 1
    print(f"OK — {total} checks passed (Plaud spaced/unspaced/en-dash, Gemini, negative controls)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

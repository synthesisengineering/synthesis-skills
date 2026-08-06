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

v0.5.2 (2026-08-06): a stale, orphaned plugin-cache copy (v4.9.0, predating v0.5.0
entirely) was run in place of the actually-installed v4.14.1 and produced 26
false-positive INCOMPLETE flags across a production corpus the current detector
reads as 0 incomplete. Individually re-verifying all 26 files during that incident
surfaced a SEPARATE, real undercounting bug: our agents annotate Plaud's numbered
speakers with an inferred-name parenthetical BEFORE the colon —
`**[10:10] Jordan Lee (Plaud Speaker 4, mapped):**` — which v0.5.1 did not handle
(it matched the timestamp + name, then required a colon immediately after the
name). Confirmed against a production corpus: dozens of undercounted lines in each
of several affected files. Every affected file still passed only because it had
enough OTHER unannotated lines to clear the threshold regardless — a file with a
different mix would have been a genuine false positive. These tests pin the
annotation format, AND pin that markdown field
headers sharing the "Word (parenthetical):" shape (e.g. "**Attendees (Invited):**")
do NOT start matching — the fix is scoped to the timestamp-led branch only,
specifically to avoid eroding precision on summary-only files.

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
    # --- Plaud: timestamp-led, inferred-speaker parenthetical annotation (v0.5.2) ---
    ("plaud inferred speaker, short annotation",
     "**[10:10] Jordan Lee (Plaud Speaker 4, mapped):** So I think", True),
    ("plaud inferred speaker, long annotation w/ embedded colon",
     "**[0:00] Sam Rivera (Plaud Speaker 1 — inferred, high confidence: project lead, "
     "referenced the client deliverable; a colleague confirms the detail):** Hey", True),
    ("plaud inferred speaker, short confidence tag",
     "**[46:30] Casey Park (likely, unconfirmed):** We have no idea", True),
    # --- Gemini: bare name, no timestamp prefix ---
    ("gemini plain name", "Rajiv Pant: So AI knowledge", True),
    ("gemini bold name", "**Kathryn Sheplavy:** thanks Efren", True),
    ("gemini three-part name", "Ana Laura Volkman: Good morning", True),
    # --- Negative controls: a SUMMARY must never look like dialogue ---
    ("summary bullet w/ inline ts", "The team discussed the roadmap (00:05:12).", False),
    ("summary sentence", "* Rajiv Pant discussed integrating the tool (00:01:02).", False),
    ("bare url", "https://example.com/doc: see here", False),
    # --- Negative controls: markdown field headers must NOT gain a match via the
    # --- v0.5.2 annotation extension — it is scoped to the timestamp-led branch only.
    ("markdown field header w/ parenthetical (no timestamp)", "**Attendees (Invited):** Rajiv, Jason", False),
    ("markdown field header w/ nested-quote parenthetical", '**Decision (Gemini "Aligned"):** Ship it', False),
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

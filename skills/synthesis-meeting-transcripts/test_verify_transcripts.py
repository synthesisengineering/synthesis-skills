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

v0.5.3 (2026-08-11) adds a THIRD failure direction, in the reporting layer rather
than the detector: `--only-incomplete` filtered the results list before the summary
counters were computed, so a clean corpus printed "Total: 0 files — 0 incomplete,
0 skipped, 0 no-source-transcript" — a clean bill of health rendered byte-identical
to "wrong path / no .md files found." Observed against a 282-file corpus that was
actually 0-incomplete, 2 skipped, 19 no-source-transcript; only reading the source
told the two apart. The daily ritual invokes the script with exactly that flag, so
the success case was the one that looked broken — the same way a control gets
distrusted, arriving from the opposite side of the false positives above. The
end-to-end checks below pin the split: counters and total describe the CORPUS, the
listing alone is filtered.

Run: python3 test_verify_transcripts.py
"""

import contextlib
import importlib.util
import io
import json
import pathlib
import re
import sys
import tempfile

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
    ("plaud hour-length range", "**[1:02:03 - 1:02:44] Morgan Blake Ellis:** Hi", True),
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
    ("gemini bold name", "**Taylor Nguyen:** thanks Devon", True),
    ("gemini three-part name", "Morgan Blake Ellis: Good morning", True),
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

# What a healthy corpus looks like on the summary line. SKIPPED and
# no-source-transcript are the two statuses that are legitimately not INCOMPLETE, and
# they are what the buggy summary erased: a corpus that reports non-zero counts for
# them is visibly a corpus, while one reporting all-zeros is indistinguishable from an
# empty directory. Both are therefore present in the fixture, deliberately.
CLEAN_CORPUS_SUMMARY = "Total: 6 files — 0 incomplete, 2 skipped, 1 no-source-transcript."


def write_clean_corpus(root: pathlib.Path) -> None:
    """3 complete diarized transcripts, 1 explicitly no-source-transcript, 2 skipped
    by filename prefix, 0 incomplete."""
    for n in (1, 2, 3):
        dialogue = "\n".join(
            f"**[{m:02d}:00 - {m:02d}:30] {'Taylor Nguyen' if m % 2 else 'Speaker 2'}:** line {m}"
            for m in range(1, 16)
        )
        (root / f"complete-{n}.md").write_text(
            f"# Meeting {n}\n\n## 📖 Verbatim transcript\n\n{dialogue}\n", encoding="utf-8"
        )
    (root / "no-source-1.md").write_text(
        f"# Casual 1:1\n\n{v.NO_SOURCE_TRANSCRIPT_MARKER}\n"
        "Recorded without transcription enabled — notes are the only source record.\n",
        encoding="utf-8",
    )
    (root / "_BACKFILL_TODO.md").write_text("# Backfill TODO\n", encoding="utf-8")
    (root / "gdoc-strategy.md").write_text("# Imported Google Doc\n", encoding="utf-8")


def write_summary_only(path: pathlib.Path) -> None:
    """A Details-summary wearing a transcript heading: inline timestamps, no dialogue.
    The one file shape the verifier must flag INCOMPLETE."""
    bullets = "\n".join(
        f"* Topic {m} was discussed at length by the group (00:{m:02d}:12)." for m in range(1, 16)
    )
    path.write_text(f"# Standup\n\n## Verbatim transcript\n\n{bullets}\n", encoding="utf-8")


def run_cli(argv: list[str]) -> tuple[int, str]:
    """Invoke main() end-to-end with the given arguments, capturing stdout.
    The reporting bug lived entirely in main(), below every unit-testable helper —
    only a real invocation can catch it."""
    buffer = io.StringIO()
    saved_argv = sys.argv
    sys.argv = ["verify_transcripts.py", *argv]
    try:
        with contextlib.redirect_stdout(buffer):
            code = v.main()
    finally:
        sys.argv = saved_argv
    return code, buffer.getvalue()


def reporting_cases(corpus: pathlib.Path) -> list[tuple[str, bool, str]]:
    """(label, passed, detail) for the listing-vs-corpus contract. Every check runs
    against the SAME clean corpus the ritual would see on a good day."""
    cases: list[tuple[str, bool, str]] = []

    code, out = run_cli([str(corpus)])
    cases.append(("clean corpus exits 0", code == 0, f"expected exit 0, got {code}"))
    cases.append((
        "unfiltered summary counts the corpus",
        CLEAN_CORPUS_SUMMARY in out,
        f"expected {CLEAN_CORPUS_SUMMARY!r} in:\n{out}",
    ))
    cases.append((
        "human success names control class",
        "Control class: diagnostic" in out,
        f"success output omitted its control class:\n{out}",
    ))
    cases.append((
        "human success names unverified remainder",
        "Unverified remainder:" in out,
        f"success output omitted its unverified remainder:\n{out}",
    ))

    code, out = run_cli([str(corpus), "--only-incomplete"])
    cases.append(("clean corpus exits 0 under --only-incomplete", code == 0, f"got exit {code}"))
    cases.append((
        "--only-incomplete never prints 'Total: 0 files' on a non-empty corpus",
        "Total: 0 files" not in out,
        "a clean 6-file corpus reported 'Total: 0 files' — indistinguishable from a "
        f"wrong path or an empty directory:\n{out}",
    ))
    cases.append((
        "--only-incomplete keeps the corpus counters",
        CLEAN_CORPUS_SUMMARY in out,
        f"expected {CLEAN_CORPUS_SUMMARY!r} in:\n{out}",
    ))
    cases.append((
        "--only-incomplete says the listing is filtered",
        "(listing filtered to incomplete only)" in out,
        f"summary did not disclose the active filter:\n{out}",
    ))

    code, out = run_cli([str(corpus), "--only-incomplete", "--json"])
    payload = json.loads(out)
    # .get(), not [] — a stale copy predating a key must report a failed check, not
    # crash the runner. Diagnosing a stale install is the exact case these tests serve.
    for label, key, want in (
        ("total_files is the corpus", "total_files", 6),
        ("listed_count is the filtered rows", "listed_count", 0),
        ("rows match listed_count", "results", []),
        ("incomplete_count", "incomplete_count", 0),
        ("skipped_count survives filtering", "skipped_count", 2),
        ("no_source_count survives filtering", "no_source_count", 1),
        ("control class", "control_class", "diagnostic"),
        ("authority receipt", "issues_authority_receipt", False),
        ("enforcement outcome", "enforcement_outcome", "complete-corpus"),
    ):
        cases.append((
            f"--json {label}",
            payload.get(key, "<missing>") == want,
            f"{key}={payload.get(key, '<missing>')!r}, want {want!r} — full payload: {payload}",
        ))
    cases.append((
        "--json names unverified remainder",
        bool(payload.get("unverified_remainder")),
        f"unverified_remainder missing or empty — full payload: {payload}",
    ))

    # The other direction: filtering must still filter, and a real failure must still fail.
    write_summary_only(corpus / "summary-only.md")
    code, out = run_cli([str(corpus), "--only-incomplete"])
    cases.append(("an incomplete file exits 1", code == 1, f"expected exit 1, got {code}"))
    cases.append((
        "the listing still shows only incomplete rows",
        "summary-only.md" in out and "complete-1.md" not in out,
        f"listing was not filtered to incomplete:\n{out}",
    ))
    cases.append((
        "totals grow with the corpus, not with the listing",
        "Total: 7 files — 1 incomplete, 2 skipped, 1 no-source-transcript." in out,
        f"summary did not describe the 7-file corpus:\n{out}",
    ))

    return cases


def main() -> int:
    failures = []

    skill_text = (pathlib.Path(__file__).parent / "SKILL.md").read_text(encoding="utf-8")
    skill_version_match = re.search(r'^  version: "([^"]+)"$', skill_text, re.MULTILINE)
    if not skill_version_match or skill_version_match.group(1) != v.SCRIPT_VERSION:
        failures.append(
            "VERSION detector version must match SKILL.md metadata version — "
            f"detector={v.SCRIPT_VERSION!r}, skill="
            f"{skill_version_match.group(1) if skill_version_match else '<missing>'!r}"
        )

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

    # Reporting layer: --only-incomplete filters the listing, never the counters.
    with tempfile.TemporaryDirectory() as tmp:
        corpus = pathlib.Path(tmp)
        write_clean_corpus(corpus)
        reporting = reporting_cases(corpus)

    for label, passed, detail in reporting:
        if not passed:
            failures.append(f"REPORTING {label!r}: {detail}")

    total = len(SPEAKER_CASES) + len(STANDALONE_TS_CASES) + 3 + len(reporting)
    if failures:
        print(f"FAILED — {len(failures)} of {total} checks:")
        for f in failures:
            print("  -", f)
        return 1
    print(
        f"OK — {total} checks passed (Plaud spaced/unspaced/en-dash, Gemini, "
        "negative controls, listing-vs-corpus reporting)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

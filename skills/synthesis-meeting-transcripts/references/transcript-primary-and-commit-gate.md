# What counts as primary evidence, and the commit gate

The rules for using a saved meeting record as evidence, and the transcripts repository's pre-commit gate that keeps
a summary from being committed in place of a transcript. The v0.4.0 and v0.5.0 release notes
([release-notes.md](release-notes.md)) tell how each rule was learned.

Contents:
- What counts as primary evidence: the verbatim transcript; summaries kept as labeled appendices; attribution; the
  summary-only warning; headers the agent writes
- The commit gate: the pre-commit hook and its script, the fetch-time rule, what the verifier reads

## What counts as primary evidence

1. **The verbatim transcript is the only primary source** (binding rule 4). Fetch it whenever the tool provides one:
   a summary-only fetch is an incomplete fetch. Step 4.5's verifier detects one after the save; this rule applies at
   fetch time.
2. **Keep tool summaries, decisions sections and action-item lists as labeled appendices.** They are lossy
   derivatives, so save them verbatim under a clear label, such as "Tool AI note — lossy derivative; verify against
   transcript before citing". Keep them rather than discard them: they carry provenance and scanning value, they are
   sometimes the only record (some docs ship without a transcript tab), and the tool's exact output is what makes an
   error traceable.
3. **Resolve every attribution-bearing claim against the verbatim transcript** (binding rule 8) before an active-voice
   sentence goes into a context file, plan or draft message: who warned, decided, approved, asked or promised, every
   quote and every action owner. A passive construction in an AI summary ("he was warned", "it was decided") has
   dropped its actor; a later writer fills the slot with the most salient person, usually the meeting counterpart,
   and the misattribution spreads. The v0.4.0 release note tells the 2026-07-07 incident that taught this.
4. **Warn when no verbatim transcript exists.** When the tool provides none, tell the user in the same turn and stamp
   the saved file's header: "⚠️ summary-only — no verbatim transcript exists."
5. **Take the headers and highlights the agent writes from the transcript,** never paraphrased from the tool's summary.

## The commit gate

**1. Install the completeness gate in the transcripts repository's pre-commit hook.** A file added or changed under
`transcripts/meetings/*.md` must hold a real verbatim transcript or carry the explicit no-source marker; otherwise
the commit is blocked. Put this in the repository's `.githooks/pre-commit`, or in the pre-commit your hook engine
chains:

```bash
# Meeting-transcript completeness gate — a summary cannot be committed in place of a transcript.
viol=0
while IFS= read -r f; do
  case "$f" in
    transcripts/meetings/gdoc-*|transcripts/meetings/email-*|transcripts/meetings/_*) ;;  # not meetings
    transcripts/meetings/*.md)
      [ -f "$f" ] || continue
      grep -q 'VERIFIER: no-source-transcript' "$f" && continue
      # Count timestamp markers in BOTH formats real transcribers emit:
      #   Gemini  inline HH:MM:SS   ·   Plaud  bracketed [M:SS]/[MM:SS]/[H:MM:SS]/[t-t]
      ts=$(grep -oE '[0-9]{1,2}:[0-9]{2}(:[0-9]{2})?' "$f" | wc -l | tr -d ' ')
      if [ "${ts:-0}" -lt 5 ]; then
        echo "TRANSCRIPT-INCOMPLETE: $f — ${ts:-0} timestamp marker(s); looks summary-only."
        echo "  Fetch the source (Doc's transcript section, or the recorder's get_transcript) and save the"
        echo "  FULL verbatim transcript. If the source genuinely has none, add on its own line:"
        echo "  <!-- VERIFIER: no-source-transcript --> <reason>"
        viol=1
      fi ;;
  esac
done < <(git diff --cached --name-only --diff-filter=AM -- 'transcripts/meetings')
[ "$viol" -ne 0 ] && { echo "Blocked — see synthesis-meeting-transcripts v0.5.0. Fix and re-commit."; exit 1; }
```

The gate is cheap on purpose, a floor of timestamp markers rather than a full parse, so it is fast and hard to argue
with; `verify_transcripts.py` is the richer, more precise cross-check for Step 4.5 and periodic audits. The gate is
the boundary that cannot be bypassed.

**2. Save the transcript in full whenever the source has one** (binding rule 4). Saving a summary when the source has
a transcript is a failure, not a shortcut: never abridged, never "omitted for brevity", never replaced by a
paraphrase or a smoothed reconstruction. A summary-only save is legitimate only when the source has no transcript,
and it carries the `<!-- VERIFIER: no-source-transcript -->` marker with a one-line reason (binding rule 7).

**3. What the verifier reads.** `verify_transcripts.py` recognizes the recorder's timestamp-led speaker line
(`**[00:00] Name:**` and the range form `[00:00-00:32] Name:`) and treats a dense run of standalone-timestamp lines
as a complete undiarized transcript, so a full transcript with one diarized speaker, or with none, passes. A count of
timestamps alone cannot tell a transcript from a summary whose "Details" bullets carry inline timestamps (a summary
can even wear a "Verbatim transcript" heading); the structure of standalone-timestamp lines and speaker lines can.
Save real line breaks: a verbatim record saved with escaped `\r\n` sequences reads as summary-only to every tool and
to people.

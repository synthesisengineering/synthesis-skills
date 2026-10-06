# Transcript-primary sourcing and the commit gate

The v0.4.0 hierarchy of evidence for every fetched meeting record, and the v0.5.0 fail-closed commit gate that keeps a summary from being committed in place of a transcript, both as written.

Contents:
- v0.4.0: the verbatim transcript is the only primary source; summaries are lossy derivatives; no attribution from a summary; summary-only warnings; agent-authored headers
- v0.5.0: the transcripts-repo pre-commit hook, the fetch-time rule, the hardened verifier

## v0.4.0 — Transcript-primary sourcing (summaries demoted, never trusted for attribution)

In v0.4.0 (2026-07-07), the skill codifies the **hierarchy of evidence** for every fetched meeting record:

1. **The verbatim transcript is the only primary source.** Always fetch it when the tool provides one — a summary-only fetch is an incomplete fetch. (The v0.3.0 verification step detects this; v0.4.0 makes the expectation explicit at fetch time, not just at verify time.)
2. **Tool-generated summaries, decisions sections, and action-item lists are lossy derivatives.** Keep them in the saved file — they carry provenance and scanning value — but only as clearly-labeled verbatim appendices (e.g., "Tool AI note — lossy derivative; verify against transcript before citing"). Do NOT discard them: they are sometimes the only record (some docs ship without a transcript tab), and preserving the tool's exact output is what makes error tracing possible.
3. **Never derive attribution-bearing claims from the tool summary.** Who warned/decided/approved/asked/promised, quotes, and action owners must be resolved against the verbatim transcript before any active-voice rendering is written into context files, plans, or draft messages. **Passive constructions in AI summaries ("he was warned", "it was decided") are attribution vacuums** — the summarizer dropped the actor, and a downstream writer will fill the slot with the most salient person (usually the meeting counterpart), which is how misattributions propagate. Canonical incident: 2026-07-07, a Plaud note's "He was warned that previous transitions (X, Y) were disastrous" — where X and Y were actually the WARNERS emailing the user directly — was rendered as a warning from the meeting counterpart and propagated into a draft message before the user caught it.
4. **Summary-only docs get a warning.** If the tool provides no verbatim transcript, tell the user in the same turn and stamp the saved file header: "⚠️ summary-only — no verbatim transcript exists."
5. **Agent-authored headers and highlights** in the saved file must be derived from the transcript, not paraphrased from the tool's summary.

## v0.5.0 — Fail-closed enforcement: a summary cannot be committed in place of a transcript

v0.5.0 (2026-07-31) closes the gap between the rule and its enforcement. v0.2.0–v0.4.0 stated the rule (the verbatim transcript is the only primary source) and added a post-save verifier — yet the failure kept recurring: an agent fetches the transcript, saves only the summary, and sometimes writes "full transcript omitted for brevity" or relabels a paraphrase as "verbatim" while doing it. Prose plus an advisory verifier is not enough. The fix is a **fail-closed commit gate** — the same pattern as credential and message guards: a mechanical check at the commit boundary an agent physically cannot skip.

**1. Install the completeness gate in the transcripts-repo pre-commit hook.** Any file added or modified under `transcripts/meetings/*.md` must contain a real verbatim transcript OR carry the explicit no-source marker; otherwise the commit is blocked. Drop this into the repo's `.githooks/pre-commit` (or the pre-commit chained by your hook engine):

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

The gate is deliberately cheap (a timestamp-marker floor, not a full parse) so it is fast and hard to argue with; `verify_transcripts.py` is the richer, higher-precision cross-check for Step 4.5 and periodic audits. The gate is the boundary that cannot be bypassed.

**2. Fetch-time rule, as a non-negotiable.** Saving a summary when the source has a transcript is a failure, not a shortcut. If the source provides a transcript, it MUST be fetched and saved in full — never abridged, never "omitted for brevity," never replaced by a paraphrase or a smoothed reconstruction. A summary-only save is legitimate ONLY when the source has no transcript, and it MUST carry the `<!-- VERIFIER: no-source-transcript -->` marker with a one-line reason.

**3. Verifier detector hardened.** `verify_transcripts.py` now recognizes the recorder timestamp-led speaker line (`**[00:00] Name:**` and the range form `[00:00-00:32] Name:`), and treats a dense run of standalone-timestamp lines as a complete undiarized transcript. This removes the false positives — full transcripts flagged incomplete because only one speaker was diarized; unattributed running transcripts — that previously trained agents to distrust the verifier. Total-timestamp count alone cannot separate a transcript from a summary whose "Details" bullets carry inline timestamps (a summary can even wear a "Verbatim transcript" heading); **standalone-timestamp-line and speaker-line structure can.** A verbatim record that was saved with escaped `\r\n` sequences instead of real newlines reads as summary-only to every tool and to humans — always save real line breaks.

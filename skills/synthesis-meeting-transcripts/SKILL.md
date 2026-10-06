---
name: synthesis-meeting-transcripts
description: "Fetch AI-generated meeting notes and full transcripts into local markdown, and verify an artifact is primary before it supports attribution. Tool-agnostic: Gmail/Drive MCPs or local exports. Use to fetch, pull, sync, download, import, classify or verify a meeting transcript."
license: "Apache-2.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "0.14.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
  format: v5
---

# Synthesis Meeting Transcripts

A protocol for fetching AI-generated meeting transcripts from the user's Gmail and Google Drive into a local markdown archive. Designed for teams where Google Meet + Gemini (or equivalents) produce meeting notes + word-for-word transcripts that live in Google Docs, and the user wants them mirrored locally alongside their project context.

The earlier release notes and rationale are retained in [references/earlier-version-history.md](references/earlier-version-history.md). Before a declared-window sweep, read the mandatory [acquisition evidence contract](../synthesis-daily-rituals/references/acquisition-evidence.md). Unknown authentication, tab enumeration, or archive coverage is a visible gap, never a no-source attestation.

## Binding rules

1. **Declared means fetched.** A ritual sync runs Step 0 below: enumerate the declared set, fetch every member, and account for each as fetched or as an unclosed gap. Relevance is judged after fetching, never before.
2. **Unknown coverage is a visible gap.** Unknown authentication, tab enumeration or archive coverage never becomes a no-source attestation; only verified acquisition evidence advances the watermark.
3. **A rendered Drive inventory cannot authorize interval completion or watermark advancement,** because it omits the provider completeness flag. Use an explicitly configured structured reader; credentials and adapters are never selected automatically.
4. **The verbatim transcript is the only primary source.** Fetch it in full whenever the source has one. The Gemini email is for discovery only, never for content.
5. **Select the transcript by the provider's stable tab ID** through `document_tabs.select_tabs`, never by title, order or a regular expression. Only a complete tab inventory establishes `transcript-tab-absent`.
6. **Verify both halves landed** with `verify_transcripts.py --file <exact saved file> --json` before calling a meeting fetched. A directory scan does not substitute.
7. **Use the `<!-- VERIFIER: no-source-transcript -->` marker only when the source truly has no transcript,** with a one-line reason beside it.
8. **Never derive attribution from a tool summary.** Before a quote, approval, decision or owner cites an artifact, run `transcript_primary.py classify` and then `authorize-attribution` on one raw message location.
9. **A scanned commitment is a candidate until the principal confirms it** in the same turn. Stamp each confirmed one with exactly one owner; nothing is created from scanner output alone.
10. **Cross-check every date against at least two independent signals** before writing a dated file.
11. **Never leave transcripts in `~/Downloads/`.** Commit them to `transcripts_repo`, whose pre-commit gate refuses a summary saved as a transcript.

## Contents

- [references/protocol-steps.md](references/protocol-steps.md): Steps 1 to 6 with every command (`verify_transcripts.py`, `transcript_primary.py`, `extract_commitments.py`), the email warning, the no-source marker, date verification and the daily-rituals integration. Read it before fetching a meeting, and for each member of a Step 0 sweep.
- [references/transcript-primary-and-commit-gate.md](references/transcript-primary-and-commit-gate.md): the v0.4.0 hierarchy of evidence and the v0.5.0 pre-commit gate. Read it before citing anything from a meeting record, and when setting up a transcripts repo.
- [references/setup.md](references/setup.md): the `.agents/meeting-transcripts.yaml` schema (required: `workspace`, `google_account`, `transcripts_repo`, `transcripts_path`), prerequisites and multi-account options. Read it when a project has no config, a config is refused, or an account is unreachable.
- [references/release-notes.md](references/release-notes.md) and [references/earlier-version-history.md](references/earlier-version-history.md): release notes from v0.2.0 to 0.14.0. Read them when a result differs from what an earlier version did.
- [optional-workspace-mcp/README.md](optional-workspace-mcp/README.md): the optional self-hosted multi-account server helper.
- [references/coverage-map.md](references/coverage-map.md): where each part of the earlier 0.14.0 text now lives.
- Protocol, Step 0: below.

## Protocol

### Step 0: Declared-window sweep (v0.9.0 — how "declared means fetched" executes)

The agent does not get a vote on which declared items are interesting. Relevance is judged after fetching, never before. Every declared item is fetched or retained as an unclosed gap.

Use the verified Python acquisition modes documented in [declared acquisition entries](../synthesis-daily-rituals/references/acquisition-entry.md) for supported complete-window reads. They compose the current inventory, stable-tab, publication and watermark owners.

Probe recorder identity at day-start using the owner's declared read-only adapter; HTTP health alone is not sign-in. Inventory every declared recorder source and account for the exact window, following all pages and retaining raw tool-call references and a same-source positive control. `inventory_documents` in the optional fetch owner provides a bounded adapter seam; never filter by meeting title or perceived relevance. Compare provider/source IDs against exact saved archive headers with `sync_watermark.py acquisition-check`; retain per-source gap decisions. Advance only with the verified acquisition evidence file; unknown enumeration or a missing archive keeps the watermark unchanged.

The single-meeting path below serves an explicit user request. A ritual sync
(Day-Start 3c, Day-End Step 1) runs this sweep instead, because the policy
above has to have an execution path or it is prose:

1. **Enumerate the declared set** for the window from
   `.agents/meeting-transcripts.yaml`: every declared meeting pattern crossed
   with every occurrence that ended inside the window. The enumeration is the
   complete decision — no per-item judgment about which meetings look
   interesting stands between the list and the fetch.
2. **Run Steps 2–5 for every member.** Relevance is judged after fetching,
   from content.
3. **Account for every member.** The sync report carries one line per
   declared member: fetched (with path), or an **unclosed gap** naming the
   member, the window, and the failure ("no doc found", "fetch failed",
   "verbatim half missing"). A member missing from the report is the defect
   this step exists to prevent; a gap is closed this run or carried as a
   blocking item, never dropped.

Steps 1 to 6, the single-meeting path whose Steps 2 to 5 the sweep runs for every member, are in [references/protocol-steps.md](references/protocol-steps.md).

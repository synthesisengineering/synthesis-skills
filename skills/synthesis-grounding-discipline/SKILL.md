---
name: synthesis-grounding-discipline
description: "Evidence and provenance discipline for AI-agent output — the truth-side companion to synthesis-anti-shortcuts' effort-side discipline. A catalog of grounding rules: never record imagined events, quote only what a tool surfaced, treat context files and memories as caches to re-verify before propagating, name the layer a config claim describes, read the evidence in hand before theorizing, count the corpus before generalizing, prove absence with a positive control and bounded reads, never complete truncated output, and validate paths before writes and deletions. Use when asked to: grounding discipline, verify claims, evidence check, provenance check, anti-confabulation, absence claim, negative finding, zero results, cache vs truth, count the files, truncated output, verify paths, safe deletion, is this grounded."
license: "Apache-2.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.1.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Synthesis Grounding Discipline

A discipline for keeping AI-agent output anchored to external evidence. The failure family it catches is the mirror image of the one [synthesis-anti-shortcuts](../synthesis-anti-shortcuts/SKILL.md) catches: anti-shortcuts stops the agent from doing less than the work requires; grounding discipline stops the agent from claiming more than the evidence supports. Both are narrative-quality optimizations working against external truth — one dismisses real concerns to keep the story tidy, the other invents satisfying completions to keep the story moving.

The shapes in this catalog are universal to LLM agents, not quirks of one model or one workflow. A language model generates the most plausible continuation. Most of the time the plausible and the true coincide, which is exactly what makes the divergent cases dangerous: a fabricated reply reads like a real one, a stale cached fact reads like a fresh one, a null result from a broken probe reads like a verified absence. None of these announce themselves. The only defense is procedural — a set of checks applied at the moments where plausibility and truth come apart.

This skill is that set. Each catalog entry names the rule, the failure shape it prevents (with one anonymized incident vignette — every entry here was paid for in production), and the compliance procedure. A closing self-check compresses the catalog into the questions to ask before any output ships.

## When to Apply

- Before recording any event, decision, message, or state change into a durable file (context files, session logs, transcripts, plans, reports)
- Before quoting or paraphrasing anything attributed to another person
- Before propagating a fact from a context file, plan, memory, or earlier conversation into any output
- Before reporting that something is absent, missing, unsent, undecided, or nonexistent
- Before writing into a directory or deleting anything
- Whenever a claim about external system state (reviews, deploys, CI, tickets, branches) is about to enter a draft

## When NOT to Apply

- Internal reasoning and ideation — speculation inside your own analysis is fine; recording the speculation as if it were an observed fact is not
- Explicitly-labeled hypotheticals ("if the reviewer has approved, then...") where the conditional framing is preserved in the output
- Content the user supplied directly in the current conversation — the user's own statements need no tool citation (though claims about systems still get re-verified before propagating outward)

## The Catalog

Twelve rules in five groups: record only what a source surfaced; treat caches as caches; prove absence properly; ground writes and deletions; and read archives as history.

> **Entry numbers are load-bearing.** Other documents cite these rules by number (`§7–9`, `§10`, `§11`). New entries are **appended**, never inserted — renumbering silently repoints every existing citation to a different real rule, which is worse than a broken link because it still resolves.

---

### Part 1 — Record Only What a Source Surfaced

#### 1. Anti-Confabulation: Document the Open Loop, Not Its Imagined Closure

**The rule.** Never record anything that fills a narrative gap unless the gap-filling content has an external source you can cite. If the reasoning is "X would naturally happen next, so I'll record it as having happened" — stop. Record the open loop ("no reply has arrived yet"), not its imagined closure.

**The failure shape.** An agent summarizing correspondence recorded a colleague's reply that had never arrived — invented the message, complete with a plausible timestamp — and then drafted a response to the imaginary message. The record read perfectly naturally, because it was exactly what a plausible next message would look like. That is the trap: confabulated content is optimized for plausibility, so it survives every review that checks only for plausibility.

**The discipline.** An open loop is a legitimate, recordable state. "Sent; awaiting reply" is a complete fact. The urge to close the loop is a narrative urge, not an evidentiary one — and closed-by-imagination is strictly worse than open, because a false closure stops anyone from ever checking again.

#### 2. Quote Provenance: No Quote Without a Tool-Surfaced Source

**The rule.** Never write a quote attributed to another person — in any medium, into any file — without being able to cite the specific tool output **in the current session** that surfaced it: a message-platform read, a file read of an existing transcript, a web fetch, or equivalent. There is no "I remember it from earlier in the conversation." There is no "this is what they would say." Either there is a tool result to cite, or there is no quote.

**The failure shape.** Attribution is the highest-stakes form of fabrication: a made-up quote or a mis-attributed act puts words in a real person's mouth, and downstream readers treat quoted material as the most reliable content in a document. The same discipline extends from quoted words to attributed acts — "she approved," "he warned," "they decided" all require the same current-session source.

**The discipline.** Before writing any quote or attribution, name the tool call that returned it. If the source was a prior session's file, cite the file read that re-surfaced it this session. Paraphrase without a source is the same violation at lower resolution.

---

### Part 2 — Caches Are Not Truth

#### 3. Cache-vs-Truth: Re-Verify Before Propagating

**The rule.** Context files, reference files, session logs, plans, memories, and earlier conversation turns are **caches** — facts that were true at the moment they were written. They are not the source of truth. Before a load-bearing fact from any cache enters an output (a draft message, a review, a status report, an external artifact), run the verifying command against the live system first.

Name the verifying command class for the claim:

| Claim about | Verifying command class |
|---|---|
| Code-review state (approvals, dismissals) | the code host's review query (e.g., `gh pr view N --json reviews`) |
| Deploy / runtime configuration | the platform's describe/inspect command for the running service |
| Branch sync state | `git log --left-right --count A...B` or equivalent |
| CI status | the CI system's latest-run query |
| Ticket status | the tracker's live ticket read |
| Test or file counts | run the actual test command / listing |
| File contents | re-read the file this session |

**The failure shape.** A draft status message stated that a reviewer had already approved a change — propagated from a project context file. The approval had been dismissed days earlier when a new push invalidated it. The one-command verification was run only after the user asked whether the draft was grounded; it took seconds and reversed the claim. A cache is invisibly stale: the prose is fluent, the dates are present, nothing flags the drift. And a stale fact that reaches a context file gets *re-confirmed* by every future session that reads it — caches launder each other.

**The discipline.** The pre-draft question for every factual assertion about external system state: "where did I learn this, and was it within this session via a verifying tool call?" If the answer is "from a context file / plan / memory" — verify before writing. The rule applies to outputs, not to internal reasoning; think freely, publish verified.

#### 4. Runtime State vs IaC State: Two Distinct Truths

**The rule.** "Is this configured?" has no single source of truth. Runtime state (what the running service actually has) and infrastructure-as-code state (what the next deploy will produce) are distinct layers that drift whenever changes land imperatively. Name which layer a claim describes. When a setting touches a deploy pipeline, verify both layers, report drift explicitly, and do not retract a claim on contradiction until you reconcile which layer each party checked.

**The failure shape.** One engineer reported an environment variable "set" — checking the running service, where an imperative update had applied it. Another reported it "not present" — checking the IaC repo, where the variable defaulted to empty. Both were right about different layers, and the drift meant the next deploy would silently wipe the runtime value. The agent in the middle initially treated the contradiction as proof its own diagnosis was wrong — auto-flipping instead of reconciling.

**The discipline.** Runtime determines current behavior (incident logs come from runtime; if the logs say the service was called, it was called). IaC determines persistence (change it there so it stays changed). A claim that names its layer cannot be "refuted" by the other layer — only extended.

#### 5. Examine the Evidence in Hand Before Theorizing

**The rule.** When a screenshot, pasted error, log excerpt, or attached artifact is available, read it — OCR it if needed — **before** drafting any diagnosis or reply. Do not answer from generic hypotheses while the exact runtime details sit unread in the artifact.

**The failure shape.** A diagnostic reply was drafted from plausible general theories while a screenshot already in hand carried the exact error string, the exact quota dimension, and the exact model identifier. Reading it first — a three-minute step — would have made the diagnosis precise on the first pass instead of publicly wrong on it.

**The discipline.** Evidence in hand outranks hypothesis space. The cost asymmetry is extreme: reading the artifact is minutes; a wrong diagnosis in front of colleagues is a credibility event. Action before words.

#### 6. Conventions Are Corpus Claims: Count Before Generalizing

**The rule.** Any claim about a convention is a claim about the corpus of files. "Dominant," "standard," "established," "all," "none," "most" are quantifiers — emit them only with the count attached, and show the command that counted. When a convention document and the corpus disagree, inspect both before deciding which is stale; neither automatically wins. Independently verify any convention claim arriving from a sub-agent — the orchestrator holds the shell, and the check is one `ls` away.

**The failure shape.** A sub-agent normalized filenames toward what it called the "dominant" naming pattern. A one-line directory listing showed the "dominant" variant was the minority — outnumbered four to one by the pattern it was overwriting. The word *dominant* is purely a count, and no count had been run. A conventions document is a cache of the corpus's shape at the moment someone wrote it down; drift between doc and corpus is the normal condition of a living repository, not an anomaly.

**The discipline.** Not "the corpus conforms" but "`grep -L <marker> <files>` → 3 non-conforming." Not "the dominant slug is X" but "`ls | sed … | sort | uniq -c` → 8 / 2 / 1." The command is the claim's evidence; include it.

---

### Part 3 — Proving Absence

#### 7. Negative Findings Need a Positive Control

**The rule.** A negative result is only evidence if the instrument was capable of producing a positive one. Before reporting that something is absent, false, or unresolved, demonstrate that the same tool, the same query shape, and the same target space can find something you already know exists — a positive control that exercises the exact mechanism in question. A control that does not exercise the suspect component validates nothing. And scope every negative finding to what was actually tested: "the registry returns zero for this name," not "none exists."

**The failure shape.** A run of false negatives in quick succession, every one from a test structurally incapable of succeeding: an access check aimed at the wrong host concluded "no access" (the organization lived on a different platform entirely); a search with a malformed modifier failed silently to zero and two true events were reported as fabricated; a "no decision was made" finding was published while the transcript recording the decision sat unread on the agent's own disk. Each null was reported as a fact about the world when it was a fact about the probe.

**The discipline.** Before writing any negative finding: (1) run a positive control through the same mechanism; (2) verify the target space before the target — which host, which org, which account; (3) search local primary sources before trusting status metadata — transcripts and verbatim records outrank status fields and "last updated" stamps; (4) scope the claim to the instrument ("not found by X in Y") rather than the universe ("does not exist"). Publishing a negative finding into a canonical file raises the bar further — future sessions will read it as settled fact.

#### 8. Truncated Output Is a Pointer, Not Content

**The rule.** Any string showing evidence of truncation — a trailing ellipsis, a fixed-width cut, "N more," "[output clipped]," a preview column — may be used to decide **what to open**. It may never be used as the **content of a claim**. Never complete a cut string; resolve it at the source. The moment you notice yourself completing a word, stop. Corollary: an assertion that a file, config, channel, or account does not exist requires a listing, not an inference.

**The failure shape.** A scanner's fixed-width preview cut a line just after a config file's name, leaving a single stray character of the next word. The agent completed that character as "not created" — when the real word was "needs," as in "needs corrections," which presupposes the file exists. The completion did not merely guess; it inverted the meaning of the source. One `ls` in the working directory would have refuted it. Instead, the false "missing config" claim landed in a coverage report's honesty field, where it read as diligence rather than error — and explained away days of unswept messages while manufacturing remediation work for a file that was already correct.

**The discipline.** A gap with no explanation invites a second look; a gap with a plausible invented cause closes the question — which makes the fabricated explanation strictly worse than the visible gap. Open the underlying file, or re-run the tool without the truncating view, before any assertion depends on the line.

#### 9. Zero Search Results Are Never Evidence of Absence

**The rule.** A zero-result search is never evidence of absence. Not weak evidence — none. Search indexes lag, miss whole content classes (thread replies, recent items), and fail silently on malformed query modifiers. To establish that something did not happen, re-check with a bounded direct read of the primary source — the specific channel, thread, log, or directory, with an explicit window — and state the bounds: "not present in X between t1 and t2," never "didn't happen."

**The failure shape.** A workspace search API returned zero results, four queries in a row, for messages that existed — sitting in threads the index had not yet covered. The agent reported them "not sent"; had it been authorized to send, it would have sent duplicates. In a later recurrence, a display-name modifier with a space in it silently returned zero instead of erroring, and an oversized result file that likely held the answer was never opened before concluding.

**The discipline.** Before trusting any null from a modifier-bearing query, re-run it without the modifier. Before reporting any null at all, do the bounded direct read (this is rule 7's positive-control principle applied to search). And read every result the tool did return — including the one that overflowed to a file — before concluding anything from what it did not.

---

### Part 4 — Grounding Writes and Deletions

#### 10. Search First, Verify Paths Before Writing

**The rule.** Never assume you know where something lives. Before writing to any directory: locate it (`find` or equivalent), verify it is the intended target (`git log`, `git remote -v` for repositories), and if multiple candidate matches exist, ask rather than pick. Before implementing, search for existing solutions, scripts, and prior art in the project's own record.

**The failure shape.** An agent assumed a project directory's path and created a duplicate tree beside the real one. Everything written there was orphaned from the project it belonged to, and the cleanup cost more than the verification would have. A path that "looks right" is a plausibility judgment — exactly the kind this catalog exists to check.

**The discipline.** The write target is a factual claim like any other: verify it with a command before acting on it. `git remote -v` is the identity check for a repository; a directory listing is the identity check for a path.

#### 11. File and Process Safety

**The rule.** A bundle of small always-on bans, each one a grounding rule for a destructive operation:

- **Move, verify, then delete.** Never delete without moving first: copy to the correct location, verify the copy, then remove the original. Archive before removing content from any durable file.
- **Tracked repos use `git mv` / `git rm`** — not bare `mv` or `rm`. The version-control layer is the safety net; bypassing it discards the net.
- **No broad process-kill patterns.** Never `pkill -f` with a loose pattern; kill by specific PID or port. A pattern is a claim about which processes match, and loose claims kill bystanders.
- **No blind stream-edits for sensitive replacements.** Never `sed`/`awk` across files for consequential changes without reading first. Read, understand, then edit surgically — a pattern-match is not an understanding.
- **Recursive-delete targets get validated independently.** Before any recursive removal: resolve the target, compare it against an explicit expected destination, and refuse `/`, the home directory, the current working directory, source/repository/workspace roots, unexpected parents, and symlinks.
- **"No cleanup target" is `None`, never a path-typed empty value.** Represent an absent path with an explicit non-path sentinel — never `Path()`, `Path("")`, `"."`, or any other value that is itself a valid path. After promoting a staged directory, clear the cleanup target back to the sentinel. Any installer that replaces trees needs a regression test proving its own source repository and working directory survive, plus an isolated live-shape install test.

**The failure shape.** A staged installer needed to tell its cleanup block that no temporary directory remained, and used an empty path object as the sentinel. In its language, the empty path denotes the current directory — so the cleanup pass recursively deleted the source repository the installer was running from, `.git` included. The sentinel was itself a valid, dangerous target, and the deletion code trusted the sentinel alone instead of independently validating what it was about to remove.

**The discipline.** Two independent layers, both mandatory: model absent-path state so it cannot be mistaken for a path, AND validate every destructive target at the moment of destruction as if the state model might be wrong. A cleanup sentinel must be unrepresentable as a destructive target; destructive code must still refuse protected targets on its own.

---

### Part 5 — Archives and Imports

#### 12. Archived History Is Not Current State

**The rule.** When you import a body of past material — a channel backfilled to its first
message, an exported mailbox, a migrated ticket system, a document archive — every item in it
arrives with the same present-tense voice, and none of it is evidence about today. Before
reporting anything from an import as **currently** open, unresolved, or unanswered, reconcile
it against the newest material you already hold on the same subject. If the newest thing you
can find is inside the import itself, you have not checked — you have only observed that the
import ends.

**The failure shape.** Seven conversations were backfilled to their true first messages. The
retrieval was careful: paged to the beginning, threads expanded, credentials redacted. It then
produced a list headed "things nobody has seen," and the top item traced a colleague's
employment arrangement through several stages to a request for documents, a "will send soon,"
and then silence — reported as the largest open loop in the set, six weeks stale.

It was finished. The arrangement had been settled deliberately, her email had already migrated
to the new domain, and she was preparing to tell her team that week. The correction came from
the person who had resolved it — being told his own colleague's settled employment was an
unresolved loop.

The contradicting evidence was already in hand. A calendar query run two hours earlier had
returned **both** email domains in a single response: the new one on meetings she had recreated,
the old one on stale invitations. That is the fingerprint of a completed account migration, and
it went unread.

**The discipline.**
- **Newest-in-this-file is not newest-anywhere.** A conversation ending is not a story ending.
  The thread may have continued in another channel, in email, in a meeting, or in a decision
  nobody posted back. Grep the corpus for the people and terms involved before calling anything
  open; it costs seconds.
- **Scope the claim to where you looked.** "Unanswered in this conversation through <date>" is
  honest and useful. "Nobody has seen this" is a claim about every channel, every meeting and
  every person, and it is almost never supported. This is entry 7 applied to imports.
- **Title the output by what it establishes.** A list produced from an import is a list of
  **where conversations stopped**, not a list of what is unresolved. Named accurately it stays
  useful; named the other way it manufactures work.
- **Stamp the import.** Every archive file states the span it covers and the date it was
  captured, so a later reader cannot mistake its newest message for the present.
- **Raise the bar for personnel and commercial matters.** Calling someone's employment,
  pay, or contract terms unresolved when it is settled asks them to re-litigate finished work
  and signals that the record cannot be trusted. The subject almost always knows the answer and
  will notice the check was skipped.

**The tell.** When an import produces a list of open items, ask how many were checked against
anything outside the file they came from. If the answer is none, that is not a findings list.

---

## The Self-Check

Before sending any output that states a fact, records an event, or claims an absence:

1. **Every recorded event:** does it have an external source, or does it close a narrative loop by imagination? Open loops get recorded as open.
2. **Every quote and attribution:** is there a tool result in this session to cite? No citation, no quote.
3. **Every fact about external system state:** learned this session via a verifying command, or propagated from a cache? Cache → verify first, and name the command class.
4. **Every configuration claim:** which layer — runtime or IaC? Is the layer named in the claim?
5. **Any artifact in hand** (screenshot, pasted error, log): read before theorizing?
6. **Every quantifier over a corpus** ("all," "none," "dominant," "standard"): is the count attached, with the command that produced it?
7. **Every negative finding:** did a positive control exercise the exact mechanism? Is the claim scoped to the instrument ("X returns zero for Y") rather than the world ("none exists")?
8. **Every string used as evidence:** complete, or truncated? Truncated → open the source before any claim depends on it.
9. **Every zero-result search:** followed by a bounded direct read with stated bounds?
10. **Every write target:** located and identity-verified with a command?
11. **Every destructive operation:** target validated independently, sentinel non-path-typed, move-verify-delete order respected?
12. **Every claim drawn from an archive or backfill:** reconciled against the newest material held elsewhere, and scoped to where you actually looked?

If any answer is wrong, fix the grounding before sending — not after.

## Relationship to Other Skills

- **[synthesis-anti-shortcuts](../synthesis-anti-shortcuts/SKILL.md)** — The effort-side sibling. Anti-shortcuts catches deferral, dismissal, and false consultation; this skill catches fabrication, stale propagation, and false absence. An output can fail both at once — a confabulated "already done" is simultaneously a shortcut and a grounding failure.
- **[synthesis-checkpoint](../synthesis-checkpoint/SKILL.md)** — The session-state instance of cache-vs-truth: verified time, git history, and context files re-synced on drift signals. Checkpoint covers "where are we"; this skill covers every fact leaving the session in an output.
- **[synthesis-fact-checking](../synthesis-fact-checking/SKILL.md)** — Verifies claims in *content being reviewed*; this skill governs claims the *agent itself* is about to make.
- **[synthesis-implementation-integrity](../synthesis-implementation-integrity/SKILL.md)** — Post-implementation verification that work is actually complete. Its "never claim a check that did not run" is this discipline applied to self-reports.
- **[synthesis-slack-sync](../synthesis-slack-sync/SKILL.md)** — Carries the messaging-platform instance of rules 2, 7, and 9: transcripts-first lookups, provenance for synced content, and bounded reads for absence claims.

## The Underlying Principle

Every entry in this catalog is one mechanism: **a claim's plausibility is not its evidence.** LLM agents are plausibility engines — that is what generation is — so the plausible-but-unverified claim is the native failure mode, the thing the system produces when nothing intervenes. The intervention cannot be "try to be accurate," because the confabulated reply, the stale approval, the mis-aimed probe, and the completed truncation all *feel* accurate from the inside.

The intervention is structural: bind every class of claim to the class of evidence that grounds it — a tool citation for quotes, a verifying command for system state, a count for quantifiers, a positive control for absences, a listing for existence, an independent validation for destructive targets. When the evidence class is missing, the claim does not ship. The agent that applies this discipline is not the one that never errs; it is the one whose errors cannot silently reach an output.

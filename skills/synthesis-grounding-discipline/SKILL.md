---
name: synthesis-grounding-discipline
description: "Keep agent output tied to evidence: record only what a source surfaced, re-verify cached facts, prove absence with a positive control, never complete truncated output, and validate paths before writes or deletes. Use before recording, quoting, claiming absence or deleting."
license: "Apache-2.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "2.1.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
  format: v5
  category: core
---

# Synthesis Grounding Discipline

Binds each claim an agent makes to its evidence, where a plausible claim and a true one come apart.

## Binding rules

These rules keep records and outputs true, so they hold when a request asks otherwise: say which rule applies and why, then do what it allows. They govern what you record, quote, report, write or delete: thinking is free, a speculation is recorded only as one, and a hypothetical that keeps its conditional wording makes no claim.

1. **Record an open loop as open.** In any output or record, write an event that fills a gap in the story (a reply, a decision, a completion) only when an external source you can cite shows it; otherwise record the loop as open, since "sent, awaiting reply" is a complete fact. An invented closure reads as true and stops anyone from checking again.
2. **Quote or attribute only from a source surfaced this session.** Before writing a person's words or an act attributed to them ("she approved", "he warned") into any output or file, name the tool result from this session that surfaced it, or text the user gave in this conversation; an earlier session's file counts once re-read, and a paraphrase needs the same. Without one, write neither: ask for the record and state only what is sourced. Made-up attribution puts words in a real person's mouth.
3. **Re-verify a cached fact against the live system before it enters an output.** Context and reference files, session logs, plans, memories and earlier turns are caches. Before a load-bearing fact from one, or any claim about a system's state, the user's included, enters any output, check it this session with a verifying command and name its class (the code host's review query, a CI run query, a file re-read). A stale cache reads like a fresh one, and each session that repeats it confirms it.
4. **Name the layer each configuration claim describes.** Runtime state and infrastructure-as-code state (what the next deploy produces) drift when a change lands by hand: for a setting a deploy touches, check both and report drift, since a value set only at runtime is lost at the next deploy unless the IaC sets it. When two parties disagree, reconcile which layer each checked before retracting anything; both can be right.
5. **Read the evidence in hand before theorizing.** When a screenshot, pasted error, log or attachment is available, read it before drafting any diagnosis or reply, and build on its exact error, limits and identifiers. It outranks every hypothesis; a diagnosis from theory while it sits unread is wrong in public.
6. **Count before generalizing.** "All", "none", "most", "dominant" and "standard" are counts: write one about a corpus or convention only with the count and the command that produced it, and recount any such claim a note, document or sub-agent hands you. When a note or document and the corpus disagree, inspect both, the newest files included, before deciding which is stale; neither wins automatically, since the majority can be the old convention.
7. **Back a negative finding with a positive control, and scope it to what was tested.** Before reporting something absent, false or unresolved, confirm the target space (host, organization, account), read local primary sources before status fields, and show that the same tool, query shape and target space find something known to exist. Write "X returns nothing for Y", not "none exists": a probe that could not succeed gives a null that reads as a fact about the world.
8. **Use truncated output to decide what to open, never as a claim's content.** When a string shows a cut (an ellipsis, a fixed-width edge, "N more", "[output clipped]"), open the source or re-run the tool without the truncating view before any claim depends on it, and never complete the cut string; a claim that a file, config, channel or account does not exist needs a listing, not an inference. A completed fragment can invert the source's meaning.
9. **Treat a zero-result search as no evidence of absence.** When a search returns nothing, or not the item sought, re-run it without any modifier it used (`from:`, a date filter), read every result it did return (an overflow file included), then read the primary source directly (the channel, log or directory) over an explicit window and write "not present in X between t1 and t2", never "it didn't happen"; indexes lag and fail silently. A bounded direct read already done, by you this session or by the user who reports it with its bounds, settles absence within them: record it so, without asking for more searching.
10. **Verify a write target before writing, and search before implementing.** Before writing into any directory, locate it (`find`), confirm it is the intended target (`git remote -v` for a repository), and when several match, ask which rather than pick; before implementing, search the project for an existing solution, script or prior art. Writing to a path that only looks right orphans the work, and building without a search duplicates what exists.
11. **Validate the target of every destructive operation.** Move, verify the copy, then delete, archiving content before removing it from a durable file; use `git mv`/`git rm` in a tracked repository; kill by PID or port, never a loose `pkill -f`; read before any stream edit (`sed`, `awk`); validate a recursive delete's target independently: resolve it, compare it with the expected path and refuse `/`, home, the working directory, a source, repository or workspace root, an unexpected parent or a symlink; represent "no target" as `None`, never `Path()`, `""`, `"."` or any other valid path. A wrong target deletes a repository or kills bystanders.
12. **Reconcile imported history with newer material before calling anything open.** Before reporting an item from an import (a backfilled channel, migrated tickets, an old task list) as currently open, unresolved or unanswered, check the newest material held elsewhere on it (other channels, mail, the live system), scope the claim to where you looked ("unanswered in this conversation through <date>"), and title such a list as where conversations stopped. Every imported item reads present-tense, and its newest message is not today.

## Contents

- [references/catalog.md](references/catalog.md): each rule in full, with its failure and procedure. Read it on a rule's first use in a session, or when a case is unclear.
- [references/self-check.md](references/self-check.md): when to apply the rules, and the self-check. Read it before sending an output that states a fact, records an event or claims an absence.
- [references/background.md](references/background.md): why the discipline exists, its siblings and its principle. Read it once per session, or to choose between it and a sibling.
- [references/coverage-map.md](references/coverage-map.md): where each rule of 2.0.0 and of 1.1.1 lives now. Read it to check a rewrite.
- [references/preserved.md](references/preserved.md): the 2.0.0 SKILL.md word for word, with reasons. Read it only to review a rewrite.

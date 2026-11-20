# Coverage maps: grounding discipline

Read when checking where a rule of an earlier text lives now (ruling D8). Two rewrites, newest first: 2.0.0 to
2.1.0, the rewrite to the repository's standard (`docs/skill-writing.md`), then 1.1.1 to 2.0.0, the v5
restructure, kept word for word one heading level down.

Contents:
- 2.0.0 to 2.1.0: SKILL.md; references/self-check.md; files unchanged
- 1.1.1 to 2.0.0 (v5): the section map

## 2.0.0 to 2.1.0: the rewrite to the D8 standard

Every rule and requirement of the 2.0.0 text, in its order, and where it lives in 2.1.0. **Kept**: the same
words in the same file. **Moved**: the same words in another file. **Reworded**: the same rule in new words,
with the old words in [preserved.md](preserved.md). **Merged**: two passages that said the same thing, now said
once. **Added**: a new sentence, with its reason. Nothing was dropped. Binding rules keep their numbers, which
the skill's evaluation cases, other skills and documents cite (`§7–9`, `§10`, `§11`, entry 12). Each rule now
carries its trigger, scope and reason in SKILL.md (W2, W5); where a rule takes a sentence from its entry in
[catalog.md](catalog.md), the catalog keeps that sentence word for word.

### SKILL.md

| 2.0.0 | 2.1.0 | How |
|---|---|---|
| Frontmatter: name, description, license, `depends_on`, author, source, format, category | Frontmatter | Kept. The description is unchanged: it already leads with the key use case, and the evaluation harness cannot test a new one (W1) |
| Title | Title | Kept |
| Opening paragraph: "Twelve checks that stop an agent from claiming more than its evidence supports. Apply them at the moments where a plausible claim and a true one come apart." | Opening paragraph | Reworded: says what the skill does, binding each claim to its evidence (format rule 2); "where a plausible claim and a true one come apart" kept |
| "Numbers are load-bearing: other skills cite them. New rules are appended, never inserted." | references/catalog.md, the entry-numbers note | Merged: the catalog's note says the same, with the citations it protects, and W6 holds every rewrite to it. Every rule keeps its number |
| (none) | The line above rule 1, first sentence: the rules hold when a request asks otherwise; say which rule applies and why, then do what it allows | Added (W8, format rule 11): the rules protect records and outputs |
| When NOT to Apply, first two bullets: internal reasoning; labeled hypotheticals whose conditional framing is preserved | The line above rule 1, second sentence: the rules govern what is recorded, quoted, reported, written or deleted; thinking is free; a speculation is recorded only as one; a hypothetical that keeps its conditional wording makes no claim | Reworded into the binding rules' scope (W2), since a rule's exception must not live outside the rules; the bullets also move word for word (below) |
| Rule 1: record open loops as open; never record a gap-filling event without an external source; "sent, awaiting reply" is a complete fact; a false closure stops anyone from checking again | Rule 1 | Reworded (W5): the head kept in the singular; the scope, "in any output or record", with three illustrations of a gap-filling event (a reply, a decision, a completion); "external source" kept, "you can cite" from the catalog's rule; "sent, awaiting reply" kept; the reason with the catalog's point that an invented closure reads as true |
| Rule 2: no quote without a tool result from this session; the same for attributed acts ("she approved"); made-up attribution puts words in a real person's mouth | Rule 2 | Reworded (W2, W5, W16): one head for quotes and attributed acts; "into any output or file" and "name the tool result" from the catalog; When NOT to Apply's third bullet, text the user gave in this conversation needs no tool citation, stated in the rule, as the near-miss case gd-03 assumes; an earlier session's file counts once re-read and a paraphrase needs the same source (catalog); what goes ahead without a source (W7, W12): write neither, ask for the record, state only what is sourced; the reason kept word for word |
| Rule 3: context files, plans and memories are caches; re-verify a load-bearing fact against the live system before it enters any output, and name the command class used | Rule 3 | Reworded (W2, W5): the action as the head; the catalog's full list of caches (reference files, session logs, earlier turns added); When to Apply's trigger, any claim about external system state about to enter a draft, and When NOT to Apply's parenthetical, that such a claim from the user is still re-verified, stated in the rule as "any claim about a system's state, the user's included"; "this session" and "a verifying command" from the catalog; "name the command class" kept, with three of the catalog's classes as illustrations; the reason from the catalog's failure shape |
| Rule 4: name the layer; runtime and infrastructure-as-code state are different truths; reconcile which layer each party checked before retracting anything | Rule 4 | Reworded (W5, W14): the head names its scope, each configuration claim (the Self-Check's question 4); from the catalog: the IaC is what the next deploy produces, the layers drift when a change lands by hand, check both layers and report drift for a setting a deploy touches, and a runtime-only value is lost at the next deploy unless the IaC sets it; the reconcile-before-retracting sentence kept in substance; "both can be right" as its reason |
| Rule 5: read the evidence in hand first; a screenshot, pasted error or log outranks every hypothesis | Rule 5 | Reworded (W5): the head from the catalog's title; the catalog's "attached artifact" added to the three kinds; "before drafting any diagnosis or reply" and building on the exact error, limits and identifiers, from the catalog; "outranks every hypothesis" kept; the reason from the catalog |
| Rule 6: count before generalizing; "all", "none", "dominant" are counts; show the command that counted | Rule 6 | Reworded, with a fix for an evaluation finding (W2, W10, W14): the head kept; "most" and "standard" added to the quantifiers (catalog, Self-Check question 6); the count and its command required; the catalog's two sentences on convention claims now in the rule: recount a claim a note, document or sub-agent hands over, and when a note or document and the corpus disagree, inspect both before deciding which is stale, since neither wins automatically. "The newest files included" and "the majority can be the old convention" make "which is stale" concrete: the principal, reviewing a pilot answer that renamed a file to the majority convention, said the newest files may follow a new convention during a migration, and check neither-wins and case gd-05b were added to test it. The 2.0.0 SKILL.md left that sentence to the catalog, which the evaluation harness serves only when a model opens it |
| Rule 7: a negative finding needs a positive control through the same mechanism, and is scoped to what was tested, not to the world | Rule 7 | Reworded (W5, W14): the action as the head, scope kept; "through the same mechanism" as the catalog's "the same tool, query shape and target space"; the trigger, reporting something absent, false or unresolved (catalog); two of the catalog's steps, confirm the target space and read local primary sources before status fields; "not to the world" as the Self-Check's form, "X returns nothing for Y", not "none exists"; the reason from the catalog |
| Rule 8: truncated output decides what to open, never what to claim; never complete a cut string | Rule 8 | Reworded (W5, W14): the head kept in substance; four of the catalog's signs of a cut as illustrations (the fifth, a preview column, stays in the catalog and is still a cut); "never complete the cut string" kept; the remedy, open the source or re-run without the truncating view, and the corollary, a listing for any claim that something does not exist, from the catalog; the reason from the catalog's failure shape |
| Rule 9: zero search results prove nothing; do a bounded direct read of the primary source and state its bounds | Rule 9 | Reworded, with a fix for an evaluation finding (W2, W5, W15): the head as the catalog's "never evidence of absence"; the scope widened to a search that returns other items but not the one sought, as the catalog's "read every result the tool did return" covers; the catalog's two procedures, re-run without the modifier and read every returned result, an overflow file included (documents that cite `§7–9` cite the modifier re-run); the bounded direct read kept, with the catalog's window and its "not present in X between t1 and t2", never "didn't happen"; the primary sources as the catalog's list, a thread read as part of its channel; the reason from the catalog. The stop (W5, W15): in the pilot evaluation, three of the four answers with the skill to case gd-11, where the user reports a full read of the channel over a stated window, asked for more checking before filing the entry (thread replies, attachments, other places) and failed the check that the user's read suffices. The rule now says a bounded direct read already done, by the agent this session or by the user who reports it with its bounds, settles absence within those bounds, to be recorded without asking for more searching |
| Rule 10: verify a write target before writing; locate it, confirm its identity (`git remote -v`), and ask when several match | Rule 10 | Reworded (W2, W5): the catalog's second instruction, search before implementing, joins the head, since documents cite `§10` for both; "locate it" with `find` and "confirm its identity" as "confirm it is the intended target (`git remote -v` for a repository)"; "ask when several match" as the catalog's "ask which rather than pick"; the reason from the catalog's failure shape, and for the search half, the duplicate it prevents |
| Rule 11: destructive operations: move, verify, then delete; `git mv`/`git rm` in repos; kill by PID, never a loose `pkill -f`; read before stream-editing; validate every recursive-delete target independently; "no target" as `None`, never an empty path | Rule 11 | Reworded (W2, W5): the action as the head; the six bans in 2.0.0's order, each kept, with the catalog's specifics: archive content before removing it from a durable file, kill by PID or port, read before any stream edit (`sed`, `awk`), validate a recursive delete's target independently by resolving it, comparing it with the expected path and refusing the catalog's protected targets, and never `Path()`, `""`, `"."` or any other valid path; the reason from the catalog. The catalog's installer details (clear the cleanup target after promotion; a survival test for installers that replace trees) stay in the catalog, as in 2.0.0 |
| Rule 12: archived history is not current state; reconcile anything from an import against the newest material held elsewhere before calling it open | Rule 12 | Reworded (W2, W5, W14): the action as the head; the catalog's kinds of import, with an old task list (the shape case gd-12 tests); "before calling it open" as the catalog's "currently open, unresolved, or unanswered"; "the newest material held elsewhere" kept, with three places to look; two of the catalog's disciplines, scoping the claim to where you looked (with its example) and titling the list as where conversations stopped; the reason from the catalog. The catalog's import stamp and its higher bar for personnel and commercial matters stay in the catalog, as in 2.0.0 |
| Contents: catalog.md line | Contents | Reworded; "the first time in a session, or when a case is unclear" kept in substance |
| Contents: coverage-map.md line | Contents | Reworded for both rewrites |
| Contents: background.md line | Contents | Reworded; "Read it once per session" kept, with "or to choose between it and a sibling" |
| Contents: "When to apply, The self-check: below." | Contents: the self-check.md line | Reworded: the sections live in references/self-check.md, read before an output that states a fact, records an event or claims an absence (the Self-Check's own trigger) |
| (none) | Contents: preserved.md line | Added |
| When to Apply, whole | references/self-check.md | Moved word for word. Each trigger also stands in the scope of the rule it starts: recording (rule 1), quoting (2), propagating a cached fact or any claim about system state (3), reporting an absence (7, 9), writing or deleting (10, 11) |
| When NOT to Apply, whole | references/self-check.md | Moved word for word. Its first two bullets are restated in the line above rule 1, its third in rules 2 and 3 (W2) |
| The Self-Check, whole | references/self-check.md | Moved word for word; its twelve questions follow the rules' numbers. With the binding rules complete on their own, SKILL.md would have run past the room W19 leaves, and format rule 3 moves whole passages instead of condensing them |

### references/self-check.md

| 2.0.0 | 2.1.0 | How |
|---|---|---|
| (none) | Title and opening line: what the file holds, when to read it, and that the binding rules govern where the two differ | Added: the file stands on its own (format rule 4, format rule 11) |
| SKILL.md: When to Apply, When NOT to Apply, The Self-Check | The same three sections | Moved word for word, headings included |

### Files unchanged

`references/catalog.md`, `references/background.md` and `agents/openai.yaml`. In this file, the 1.1.1 to 2.0.0
map below is kept word for word one heading level down.

## Coverage map: grounding discipline 1.1.1 to 2.0.0

Every part of the 1.1.1 SKILL.md and where it lives now. Nothing was removed.

| 1.1.1 section | Now |
|---|---|
| Frontmatter description (long keyword list) | Shortened to 300 characters; the triggers it listed are covered by the rule names in Binding rules |
| Three framing paragraphs and the decisive-uncertainty note | references/background.md (verbatim) |
| When to Apply, When NOT to Apply | SKILL.md (verbatim) |
| The Catalog: Parts 1 to 5, entries 1 to 12 | references/catalog.md (verbatim); one-line summaries in Binding rules |
| Entry numbers are load-bearing note | references/catalog.md (verbatim) and the line above Binding rules |
| The Self-Check | SKILL.md (verbatim) |
| Relationship to Other Skills | references/background.md (verbatim) |
| The Underlying Principle | references/background.md (verbatim) |
| `depends_on`, `source_repo`, `source_type` metadata | Kept (the installer and source checks read them) |

Links moved into `references/` gained one `../` so they still resolve.

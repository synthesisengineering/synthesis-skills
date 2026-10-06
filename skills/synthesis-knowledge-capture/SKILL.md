---
name: synthesis-knowledge-capture
description: "Capture durable session facts in an OKF knowledge base: corpus-wide dedup, confidentiality routing, conflict reconciliation, provenance, shipping via synthesis-kb-edit. Use at session end, to capture or update knowledge, or to keep corrected facts about people, organizations, products or decisions."
license: CC0-1.0
depends_on:
  - synthesis-okf
  - synthesis-kb-edit
metadata:
  author: Rajiv Pant
  version: "2.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
  format: v5
---

# Knowledge Capture

A fact learned in a session and not written to the durable knowledge base is a
fact lost. This skill is the disciplined path from "the agent now knows X" to
"the knowledge base now knows X" — without duplicating, without overwriting a
still-true fact, and without leaking a confidential fact into a shared corpus.

## Binding rules

Rules 1 to 4 are the skill's four hard merge rules, in their original order.

1. **Scan first, always.** No write without a completed `kb_scan.py` for every entity involved; workflow step 3 is never skipped.
2. **In place, not append.** Correct stable facts where they live; a new concept file is only for a genuinely new unit of knowledge.
3. **Reconcile, never blind-flip.** Classify a contradiction as staleness, a second axis, or ambiguity in the new fact before editing.
4. **No fact without a source.** Every merged claim cites who said it or which tool surfaced it in this session.
5. **If the config is missing, STOP and say so.** Also stop if the target repo lacks `.agents/knowledge-base.yaml` or the two disagree on the bundle path.
6. **Default to the most private tier that fits.** Split neutral from candid; a public repo takes no confidential term (reroute or drop, never sanitize and ship).
7. **Where a fact was learned does not set where it may be stored.** The fact's tier governs.
8. **Validate and log before shipping:** both `synthesis-okf` layers clean, a `log.md` entry naming the change and its source.
9. **Ship through `synthesis-kb-edit`** with the exact touched files. Stage only those, name the area (never the specifics) in the commit message, check `git remote -v`, push per posture.

## Contents

- [references/configuration.md](references/configuration.md): the private config at `~/.synthesis/knowledge-capture/config.json`, onboarding, and the repository contract. Read it when setting up or when the config is missing.
- [references/merge-rules.md](references/merge-rules.md): merge discipline, confidentiality routing, reconciliation and provenance in full. Read it before merging any fact.
- [references/shipping-and-integration.md](references/shipping-and-integration.md): integration with sibling skills, commit hygiene, related skills. Read it before shipping.
- [references/background.md](references/background.md): release notes and why the skill exists. Read once.
- [references/coverage-map.md](references/coverage-map.md): where each part of the 1.2.0 text now lives (ruling D8).
- The capture workflow, Tools: below.

## The capture workflow

Run these in order. Never skip step 3.

1. **Extract.** From the session, list the *durable* facts — things true beyond
   this conversation: people, roles, reporting lines, product ownership,
   decisions and their rationale, stable technical facts. Exclude the ephemeral
   (today's task state, one-off logistics). State each as one atomic claim with
   its in-session source (who said it, which tool call surfaced it).
2. **Route.** For each fact, choose the target from config by confidentiality
   tier (see Confidentiality routing). One fact may split: the neutral fact to a
   shared KB, the candid framing to a private one.
3. **Scan before writing.** Run `kb_scan.py` for every entity the fact touches,
   across the target bundle. This returns *every* file and line that already
   mentions the entity. You cannot merge in place without first knowing every
   place the entity already lives. This step is mandatory; skipping it is how
   duplication and destruction happen.
4. **Merge in place.** Update the concept that owns the fact (a person's
   directory entry, a product's page). Do not append a new dated note to a
   reference concept — reference tiers are updated in place. If the fact is
   genuinely new (a departure, a new hire), add it to the concept that already
   holds that class of fact (the departures table, the roster).
5. **Validate.** Run both `synthesis-okf` layers: OKF conformance on the bundle
   and configured metadata consistency on every touched concept. Resolve all
   conformance errors, conflicts, and duplicates before shipping.
6. **Log provenance.** Append a `log.md` entry (`## YYYY-MM-DD`, newest first)
   naming what changed and the in-session source. `log.md` is OKF-reserved and
   excluded from compiled knowledge; it is the audit trail, not content.
7. **Ship through `synthesis-kb-edit`.** Hand the exact touched-file list and
   validation results to the configured editor workflow. It rechecks editable,
   refused, generated, confidentiality, branch, host, and review policy before
   staging or publishing anything.

## Tools

### `scripts/kb_scan.py` — pre-merge reconnaissance (read-only)

```bash
# every existing mention of an entity, grouped by file (run before any merge)
python3 scripts/kb_scan.py <bundle_dir> --entity "Full Name" --alias Surname --alias handle

# inventory every concept with its OKF type and title
python3 scripts/kb_scan.py <bundle_dir> --list

# surface concepts whose frontmatter timestamp is older than a date (or missing)
python3 scripts/kb_scan.py <bundle_dir> --stale 2026-01-01
```

Stdlib only; read-only; excludes OKF-reserved `index.md`/`log.md` and
`README.md`. The `--entity` scan is the mandatory step 3: it turns "I think this
person is mentioned in the roster" into "here are the six exact lines that
mention them," which is what makes an in-place merge possible.

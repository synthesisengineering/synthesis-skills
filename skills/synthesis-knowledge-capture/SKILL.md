---
name: synthesis-knowledge-capture
description: Capture durable session facts in an OKF knowledge base with corpus-wide deduplication, confidentiality routing, conflict reconciliation, provenance, validation, and repository-aware shipping through synthesis-kb-edit. Use at session end, when asked to capture or update knowledge, merge facts into ai-knowledge, or preserve corrected facts about people, organizations, products, decisions, or strategy.
license: CC0-1.0
depends_on:
  - synthesis-okf
  - synthesis-kb-edit
metadata:
  author: Rajiv Pant
  version: "1.2.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Knowledge Capture

**Version 1.2.0** (2026-09-01) ships `config.example.json` and connects the
private routing table to the guided onboarding interview. The example uses a
synthetic private workspace and a hold-for-approval push posture; the onboarding
validator refuses a domain without its repo, tier, or bundle path.

**Version 1.1.0** (2026-07-29)

A fact learned in a session and not written to the durable knowledge base is a
fact lost. This skill is the disciplined path from "the agent now knows X" to
"the knowledge base now knows X" — without duplicating, without overwriting a
still-true fact, and without leaking a confidential fact into a shared corpus.

## Why it exists

Most knowledge bases have a rule like *"update `source/` when you learn
something."* A rule is not a workflow, and a manual rule drifts. The failure has
three shapes, all real:

- **Evaporation.** The corrected fact lives only in the session transcript. The
  next session starts blind and repeats the old mistake.
- **Duplication.** A naive append adds a second, contradictory concept. Now the
  corpus asserts two things and a reader cannot tell which is current.
- **Destruction.** A blind overwrite deletes a framing that was still accurate
  on a different axis, replacing signal with a plausible error.

The canonical trigger: an agent learns a corrected fact about a person's role.
The corpus already holds several references to that person under a prior
framing. Evaporation loses the correction; duplication contradicts; a blind flip
destroys references that were right all along. The only safe path is: find every
existing mention first, decide in place, reconcile rather than flip, cite the
source. That path is this skill.

## The configuration contract

All routing specifics live in a PRIVATE config the skill reads at load time:

```
~/.synthesis/knowledge-capture/config.json
```

It maps knowledge **domains** to a target repo, a confidentiality **tier**, and
the OKF bundle path inside that repo; it names the **confidential terms** that
must never reach a public repo; and it records each repo's **push posture**
(auto, or hold-for-approval). This skill is generic and publishable; the config
is neither. If the config is missing, STOP and say so — routing a fact without
the routing table is guessing, and guessing about confidentiality is how a
private fact ends up in a shared corpus.

Run `synthesis-onboarding init` to author the file from the personal workspace
you select, or copy `config.example.json` and validate it with the onboarding
doctor. The public example contains no real repository or confidentiality data.

Each target repository must also carry `.agents/knowledge-base.yaml`. The
private capture config answers **which repository receives the fact**; the
repository contract answers **what may be edited there, which schema applies,
and how the change ships**. Stop if either layer is missing or they disagree on
the bundle path.

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

## Merge discipline — the four hard rules

1. **Scan first, always.** No write without a completed `kb_scan.py` for every
   entity involved. The scan is the difference between merging and littering.
2. **In place, not append.** Stable facts are corrected where they live. A new
   concept file is for a genuinely new unit of knowledge, not for a fact that
   updates an existing one.
3. **Reconcile, never blind-flip.** When a new fact contradicts the corpus, the
   contradiction is data, not a mandate to overwrite. See below.
4. **No fact without a source.** Every merged claim cites its in-session origin.
   If you cannot name who said it or which tool surfaced it, you cannot write it
   — the same provenance bar the rest of the synthesis stack enforces.

## Confidentiality routing

- **Default to the most private tier that fits.** When unsure whether a fact
  belongs in a shared corpus, it does not. Route it private and flag the
  question.
- **Split neutral from candid.** Org-structure facts (title, reporting line,
  who owns a product) are usually fine for a shared internal KB. Candid framing
  (why someone left, a performance read, negotiation posture) is not — that is
  private, always, regardless of how the fact was learned.
- **A public repo takes no confidential term.** If the target is a public repo,
  the config's confidential-term list is a hard filter: any fact containing one
  is rerouted to a private target or dropped, never sanitized-and-shipped.
- **Learned-in-a-shared-channel is not permission.** Where a fact was surfaced
  does not set where it may be stored. The confidentiality tier of the *fact*
  governs, per config.

## Reconcile, never blind-flip

When a new fact contradicts what the corpus already says, stop and resolve the
*shape* of the disagreement before writing:

- **Staleness** — the corpus is simply out of date. Update in place; the old
  framing is wrong now.
- **Axis** — both are true on different axes (a person can lead a business unit
  *and* report through a commercial line; a title and a functional role are not
  the same statement). Add the new axis; leave the still-true one.
- **Ambiguity in the new fact** — the sentence that delivered the fact may
  parse two ways. Resolve the antecedent with the person who stated it before
  editing. A blind flip on a misread injects an error the corpus did not have.

The cost asymmetry is the whole rule: re-reading and asking one question is
cheap; a wrong edit propagated into a shared corpus is expensive and quiet.

## Provenance

- Each merge writes a `log.md` line: date, the concept(s) touched, the fact, and
  the in-session source.
- For a fact whose truth a future reader must trust or re-check, record the
  source explicitly in the concept too (`*Source: …*`), matching the corpus's
  existing citation style.
- Treat the knowledge base as a cache, not the source of truth. A concept's
  `timestamp` records when it was last believed correct, not when it was last
  true. Re-verify before propagating a load-bearing fact outward.

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

## Integration

- **`synthesis-okf`** validates conformance and configured metadata
  consistency after every merge. This skill governs *what* to write and
  *where*; OKF governs that the result stays structurally coherent.
- **`synthesis-kb-edit`** owns repository policy and shipping. Pass it the
  touched files; do not independently reconstruct branch, host, scanner, or
  review mechanics from the capture config.
- **`synthesis-context-lifecycle`** is the sibling for *project* working memory
  (CONTEXT/REFERENCE/sessions). This skill is its counterpart for the durable,
  cross-project knowledge base. Project state that has hardened into a stable
  fact graduates from a project's REFERENCE into the knowledge base via this
  skill.
- **Daily rituals** are a natural trigger: a day-end step can ask "what did today
  teach that the knowledge base should hold?" and run this workflow on the
  answer.
- **Repository configuration.** Read `.agents/knowledge-base.yaml`; do not
  discover client-specific workflow copies under a tool-owned skill folder.
  One portable config plus the public skills is the cross-agent contract.

## Commit hygiene

- Stage only the files this merge touched. Never `git add -A` — a sibling
  process or a parallel agent may have staged unrelated work.
- The commit message names the *area*, not the sensitive specifics: "Update key
  people directory," "Refresh product ownership," "Record a departure." Never
  put the person, the reason, or the prior value in the message.
- Verify `git remote -v` before any push. Push only per the repo's config
  posture; hold for explicit approval on any shared or mirrored repo, and never
  push a private-tier repo to a shared remote.

## Related

- `synthesis-okf` — the OKF format validator/converter this skill validates with.
- `synthesis-kb-edit` — repository policy, validation orchestration, and
  configured ship flow.
- `synthesis-context-lifecycle` — project working memory; the sibling layer.
- `synthesis-message-guard` — the same provenance-and-fail-safe ethos, applied to
  outbound correspondence instead of stored knowledge.

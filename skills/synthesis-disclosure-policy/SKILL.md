---
name: synthesis-disclosure-policy
description: "Two-category disclosure governance for people who publish under their own name while handling confidential work. Distinguishes published-precedent facts (deliberately public biography an agent may restate) from unapproved disclosures (anything learned from private context), with a precedent ledger, surface classes, five decision tests, and git-hook enforcement. Use when asked about: disclosure policy, confidentiality guardrails, can I name this company, precedent ledger, public bio names, publication surface, unapproved disclosure, name allowlist."
license: "Apache-2.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.1.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Synthesis Disclosure Policy

A name blacklist models the wrong thing. Professionals who publish under
their own name deliberately say who they work for, who they have worked
for, and who they work with — on their sites, in their bios, in their
articles. That is conscious, career-positive disclosure. The same
professionals also carry genuinely confidential material: client work,
internal decisions, private conversations, things an AI collaborator reads
in private context every day. A guardrail that treats the NAME as the
secret blocks the first category (over-blocking the person's own published
biography) while under-protecting the second (a leak rarely needs the
blacklisted spelling).

This skill governs disclosure on the axis that matters: **approval and
provenance**. What the person deliberately published is precedent and may
be restated. What they did not approve stays closed — no matter how the
reference is spelled.

## The three disclosure classes

**Class P — published precedent.** A fact the person personally published
on a public surface they author: their sites, bios, articles, social
profiles. Restating a Class-P fact in the same register — biography:
relationship, role, era, public work — on their public surfaces is
allowed. Precedent covers the FACT, not the entity: an employer named in a
bio does not make any other statement about that employer public.

**Class A — approval required.** Any new naming or newly identifying
disclosure without precedent: a first-time name, a new kind of fact about
a ledgered entity, praise of a named colleague never published before, a
case study touching real parties. Default deny. Each approval then BECOMES
precedent: it is appended to the ledger with evidence, so the same
question is never asked twice.

**Class X — protected.** Not published even with casual approval; a
request to publish gets an explicit challenge naming the risk before
proceeding. Contents: negative or critical statements about named or
identifiable parties; operational and business specifics — deals, numbers,
finances, personnel matters, incidents, unreleased plans, security
details, internal decisions — even about Class-P entities; material under
NDA or equivalent obligation; other people's private information; and
anything sourced from private context with no independent public
counterpart.

## The five tests

Apply to any draft, edit, or publication that names or could identify a
real party. When any test is uncertain, the answer is Class A or X — ask,
never assume.

1. **Precedent.** Is this exact kind of fact about this entity already on
   a surface the person authors publicly? Cite the ledger entry. No entry,
   no pass.
2. **Provenance.** Where did the agent learn this? Private context —
   messages, transcripts, private repositories, meetings — means Class X
   until an independent public counterpart is cited. An agent's knowledge
   of a fact is not evidence the fact is public.
3. **Negativity.** Would the named party read the statement as anything
   other than positive or neutral? Any doubt fails the test. Published
   references to real parties stay positive or neutral; criticism is not
   published under this policy at all without the explicit Class-X
   challenge.
4. **Identification.** Could an outsider, an insider, or a motivated
   adversary narrow an unnamed reference to the real party? Identifying
   descriptions are governed exactly like names — "a major metropolitan
   newspaper where I ran engineering" identifies, and passes or fails the
   same tests the name would.
5. **Aggregation.** Do individually public facts combine into a
   disclosure none of them makes alone? Judge the combination. A public
   role plus a public timeline plus a new anecdote can identify a
   confidential situation precisely.

## The precedent ledger

The machine-readable record of Class-P facts. Source-controlled, deployed
to a stable local path, read by both agents and enforcement hooks.

```yaml
ledger_version: 1
entities:
  example-corp:
    kind: organization
    relationship: former employer
    registers:
      - biography
    hook_patterns:
      - 'example-corp'
    evidence:
      - 'personal-site/src/config/site.ts: author bio names example-corp as former employer'
      - 'https://example.com/about/'
```

Rules:

- **No entry without evidence.** Every entity cites where the person
  published the fact. Enforcement refuses an evidence-free entry.
- **`registers` scope the precedent.** `biography` covers relationship,
  role, era, and public work. Operational detail is never a register.
- **`hook_patterns` are exact strings.** Each must textually equal a
  pattern in the git-hook policy's name tier; that is what the hook stops
  enforcing on public-surface repositories. Exact equality keeps every
  allowance auditable; the hook doctor flags stale allowances.
- **Approvals append.** When the person approves a new disclosure, add
  the entity (or extend its registers) with the approval date and
  evidence. The ledger is the memory that turns approval into precedent.

## Surface classes

Enforcement follows the PUBLICATION SURFACE, not repository visibility. A
private repository that publishes a website is a public surface; a public
OSS repository is not a place for anyone's biography.

| Class | Meaning | Credential tier | Sensitive tier | Ledger allowance |
|-------|---------|-----------------|----------------|------------------|
| `personal` | Only the author reads it | always | off | n/a |
| `public-surface` | Author-published sites | always | on | Class-P names allowed |
| `strict` | Client, multi-tenant, public OSS | always | on | none |

The companion [`synthesis-git-hooks`](../synthesis-git-hooks/SKILL.md)
engine implements these classes: `strict_repo_patterns` pins repositories
strict regardless of remotes (any-match), `public_surface_patterns`
declares author-published surfaces (all-remotes match), and
`disclosure_ledger` points at the ledger. The engine fails closed: a
configured ledger that is missing or unparsable blocks commits on
public-surface repositories rather than guessing.

## Division of labor

- **Mechanical layer (git hooks):** name and pattern boundaries per
  surface class, credential scanning everywhere, generic commit messages
  on published surfaces, fail-closed diagnostics. A grep cannot judge
  sentiment or aggregation, and does not try.
- **Semantic layer (agent rules + this skill):** the five tests, register
  judgment, the Class-X challenge, and the approval-to-ledger loop. This
  is where identification and aggregation are caught.
- **Human layer:** the person owns every Class-A approval and every
  Class-X override. The system's job is to make the decision explicit,
  informed, and durable — never to make it for them.

## Category Allowlists Without Approval Fatigue

A sound disclosure gate preserves human attention for consequential choices.
When trivial, repetitive prompts teach the principal to rubber-stamp every
dialog, the fail-closed mechanism is no longer producing informed decisions:
approval fatigue is a failure mode of fail-closed design.

A category allowlist is appropriate only when the principal approves the
category once and the category has an executable membership test. Its record
must define:

1. the exact surface and register in which it applies;
2. a predicate grounded in independent public evidence authored or controlled
   by the principal;
3. the permitted claim shape, which must remain positive or neutral;
4. explicit exclusions and an owner for amendments;
5. evidence that each use satisfies the frozen predicate, without silently
   growing the category.

The category reduces repeated Class-A decisions; it never turns an entity into
a general disclosure allowance. Class X is never category-allowlisted. A
negative statement, operational detail, private provenance, identifying
aggregation, predicate mismatch, or ambiguity remains Class A and returns to
the principal. Category membership narrows approval noise; it does not weaken
the five tests or manufacture precedent.

## Maintenance protocol

1. New approval → append to the ledger with date and evidence in the same
   change; the approval is not done until the ledger records it.
2. Relationship ends or the person retracts a disclosure → the entity
   stays (precedent is historical) but future drafts treat NEW facts about
   it as Class A; note the change in the entry.
3. Run the hook doctor after every ledger or policy edit; a stale
   allowance or unparsable ledger is a failure, not a warning.
4. Audit periodically: every ledger citation should still resolve; every
   public surface should still be listed in `public_surface_patterns`.

## Adopting this for yourself

The mechanism is fully generic; only the data is personal. To adopt:

1. **Collect your precedent.** Inventory the surfaces you personally author
   and publish — your sites, bios, published articles, public profiles —
   and list every organization and person you deliberately name there, with
   the file or URL as evidence. An agent can sweep your site repositories
   for this in one pass; keep only what YOU published, in biography
   register, positive or neutral.
2. **Write your ledger** from
   [`references/ledger.example.yaml`](references/ledger.example.yaml) into a
   PRIVATE source-controlled location, and deploy it to a stable local
   path. The ledger never lives in a public repository.
3. **Classify your surfaces** in `~/.synthesis/git-hook-config.yaml`:
   your published-site repos into `public_surface_patterns`, your public
   OSS repos into `strict_repo_patterns`, your private-notes namespaces
   into `personal_remote_patterns`, and `disclosure_ledger:` pointing at
   your deployed ledger.
4. **Run the doctor**
   (`python3 ~/.synthesis/git-hooks/_load_config.py --doctor`) and keep it
   in your rituals — a stale allowance or unreadable ledger is a failure.
5. **Carry the five tests into your agent rules** so the semantic layer
   (negativity, identification, aggregation, provenance) governs drafts
   before the mechanical layer ever sees a commit.

Publishing the mechanism weakens nothing for anyone: the engine is the
same audited, fail-closed code for every user, and each user's names,
surfaces, and evidence stay in their own private configuration.

## Relationship to other skills

- [`synthesis-git-hooks`](../synthesis-git-hooks/SKILL.md) — the
  mechanical enforcement engine for the surface classes and ledger.
- [`synthesis-content-quality`](../synthesis-content-quality/SKILL.md) —
  its anonymization checks (outsider, insider, adversary, irony tests)
  operationalize the identification test for prose review.
- [`synthesis-message-guard`](../synthesis-message-guard/SKILL.md) —
  outbound-send gating; drafts that pass the five tests still go through
  send-time review.

A private companion configuration (the person's actual ledger, surface
map, and register rules) belongs in their private skill collection — this
public skill carries the methodology only.

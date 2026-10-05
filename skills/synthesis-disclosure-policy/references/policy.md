# Disclosure policy: classes, ledger and enforcement

The full text behind Binding rules 1 to 3 and 6 to 10: the reasoning, the three classes, the precedent ledger, surface classes, who does what, and upkeep.

Contents:
- Why approval, not names
- The three disclosure classes
- The precedent ledger
- Surface classes
- Division of labor
- Maintenance protocol

## Why approval, not names

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

The companion [`synthesis-git-hooks`](../../synthesis-git-hooks/SKILL.md)
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

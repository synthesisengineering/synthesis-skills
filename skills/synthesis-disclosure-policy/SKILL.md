---
name: synthesis-disclosure-policy
description: "Decide whether a real organization or person may be named or identified outward-facing: published precedent vs unapproved disclosure, precedent ledger, five tests, surface classes, git-hook enforcement. Use for: can I name this company, disclosure policy, precedent ledger, public bio names."
license: "Apache-2.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "2.0.1"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
  format: v5
---

# Synthesis Disclosure Policy

This skill governs disclosure on the axis that matters: **approval and
provenance**. What the person deliberately published is precedent and may
be restated. What they did not approve stays closed — no matter how the
reference is spelled.

## Binding rules

The class letters (P, A, X) and the names of the five tests are load-bearing: agent rules elsewhere cite them.

1. **Class P, published precedent,** may be restated in the same register on the person's public surfaces. Precedent covers the fact, not the entity.
2. **Class A, approval required,** is default deny. Each approval is appended to the ledger with evidence in the same change, so the same question is never asked twice.
3. **Class X, protected,** is not published even with casual approval: negative statements about identifiable parties, operational and business specifics, NDA material, other people's private information, anything sourced from private context. A request to publish gets an explicit challenge naming the risk.
4. **Apply the five tests (precedent, provenance, negativity, identification, aggregation) to anything that names or could identify a real party.** When any test is uncertain, the answer is Class A or X: ask, never assume.
5. **An agent's knowledge of a fact is not evidence the fact is public,** and identifying descriptions are governed exactly like names.
6. **No ledger entry without evidence,** and each `hook_patterns` string exactly equals a pattern in the git-hook policy's name tier.
7. **Enforcement follows the publication surface, not repository visibility,** and fails closed: a missing or unparsable ledger blocks commits on public-surface repositories.
8. **Class X is never category-allowlisted,** and a category never weakens the five tests; ambiguity returns to the principal.
9. **The person owns every Class-A approval and every Class-X override.** The system makes the decision explicit, informed and durable, never makes it for them.
10. **Check the policy and ledger after every edit** (the command is in [adopting.md](references/adopting.md), step 4); a stale allowance or unparsable ledger is a failure, not a warning.

## Contents

- [references/policy.md](references/policy.md): why a name blacklist fails, the three disclosure classes in full, the precedent ledger and its rules, surface classes and the hook settings that implement them, the division of labor, and the maintenance protocol. Read it when classifying a disclosure, editing the ledger, or configuring enforcement.
- [references/adopting.md](references/adopting.md): how to adopt the policy for yourself, and how it relates to git-hooks, content-quality and message-guard. Read it when setting the policy up or choosing a companion skill.
- [references/ledger.example.yaml](references/ledger.example.yaml): a starting ledger to copy into a private location.
- [references/coverage-map.md](references/coverage-map.md): where each part of the 1.1.0 text now lives.
- [references/preserved.md](references/preserved.md): lines replaced in 2.0.1 because they named the retired hook doctor and config path, verbatim. Read only to review the change.
- The five tests, Category Allowlists Without Approval Fatigue: below.

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

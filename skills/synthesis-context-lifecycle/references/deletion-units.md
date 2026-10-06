# Repo families and deletion units

The three tiers describe how a project's context is structured. One level up sits a different question: **which repository may a piece of context live in at all?** For anyone whose work spans multiple professional relationships — clients, employers, partnerships — the durable-memory layer divides into two families with fundamentally different lifecycles:

- **The permanent knowledge root.** The person's own long-lived knowledge base — their projects, lessons, daily plans, accumulated career record. It survives every professional relationship and is never deleted wholesale.
- **Per-engagement private repos.** Workspace-scoped context repositories created for one client, employer, or engagement. Each one is a **deletion unit**: if the counterparty exercises a delete-my-data request — at contract end, under a nondisclosure obligation, during offboarding — the repo is deleted or returned *as a unit*. The repo boundary is what makes the promise keepable. Design for that day from the first commit.

## The routing test

Before writing engagement-adjacent content into any repository, ask: **would this survive the relationship's end?**

- Material the counterparty could rightfully ask to have deleted — information they shared in confidence, their internal discussions, work products they own, context learned inside their walls — routes to the engagement repo, the deletion unit.
- The person's own permanent record routes to the permanent root.

The test is about the content's rightful owner and lifecycle, not about where the content happened to arrive or which window was open when it was learned.

## Both misplacement directions fail — asymmetrically

**Engagement material in the permanent root is a compliance failure.** When the deletion request comes, the misplaced material silently survives a deletion the person promised — or is legally bound — to perform. Nothing in the permanent root's lifecycle will ever remove it, and honoring the request now requires hunting down every stray copy, which is exactly the manual process repo-level deletion units exist to make unnecessary. The failure is against someone else, and it is discovered (if ever) by the counterparty.

**Permanent material in an engagement repo is self-inflicted loss.** When the deletion unit is deleted — correctly, on request — the person's own records are destroyed along with the counterparty's data: records they were entitled to keep and may one day need. Recovery is impossible precisely because the deletion was performed properly.

Neither direction is curable after deletion day. That is why routing happens at write time, not at cleanup time.

## The ALWAYS-PRESERVE class

Some records concern an engagement but belong to the person: they document the person's own side of the professional relationship, and a counterparty's delete-my-data request does not reach them. The generic class:

- contracts and signed agreements
- pay, equity, and benefits records
- hiring and negotiation correspondence
- termination and separation records
- performance reviews, given and received
- IP assignments and licensing grants
- evidence relevant to an actual or foreseeable dispute

ALWAYS-PRESERVE material routes to the permanent root **always** — even when it arrives through engagement channels, even mid-engagement, even when the surrounding conversation is otherwise engagement-confidential. A copy may exist inside the deletion unit for working convenience; the canonical record may never live *only* there, because the deletion unit's lifecycle would take it.

## Inventories count; they never itemize

When an inventory of one repository is produced for any audience beyond its owner — a deletion attestation, an offboarding report, a migration plan — items outside the inventory's scope are **counted, never itemized**. An identifier plus a descriptive title is already a disclosure of the item's existence and subject. "Four items out of scope for this inventory" conveys completeness; a filename-and-title listing of out-of-scope material leaks the very content the repo boundary protects.

## Instance specifics live in private configuration

This section is the mechanism. Which repositories are deletion units, which root is permanent, and any additions to the preserve class are facts about one person's setup — declared in that person's private agent instructions or configuration, never in this public skill. An agent applying the mechanism reads the instance declarations first, and asks rather than guesses when a repository's family is undeclared.

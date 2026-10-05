# Disclosure policy: adopting it, and related skills

How to set the policy up for yourself, and which companion skills enforce or extend it.

## Adopting this for yourself

The mechanism is fully generic; only the data is personal. To adopt:

1. **Collect your precedent.** Inventory the surfaces you personally author
   and publish — your sites, bios, published articles, public profiles —
   and list every organization and person you deliberately name there, with
   the file or URL as evidence. An agent can sweep your site repositories
   for this in one pass; keep only what YOU published, in biography
   register, positive or neutral.
2. **Write your ledger** from
   [`references/ledger.example.yaml`](ledger.example.yaml) into a
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

- [`synthesis-git-hooks`](../../synthesis-git-hooks/SKILL.md) — the
  mechanical enforcement engine for the surface classes and ledger.
- [`synthesis-content-quality`](../../synthesis-content-quality/SKILL.md) —
  its anonymization checks (outsider, insider, adversary, irony tests)
  operationalize the identification test for prose review.
- [`synthesis-message-guard`](../../synthesis-message-guard/SKILL.md) —
  outbound-send gating; drafts that pass the five tests still go through
  send-time review.

A private companion configuration (the person's actual ledger, surface
map, and register rules) belongs in their private skill collection — this
public skill carries the methodology only.

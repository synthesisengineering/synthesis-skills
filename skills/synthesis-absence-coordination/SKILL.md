---
name: synthesis-absence-coordination
description: "Coordinate an absence end to end (vacation, conference, family visit, medical leave): notification order, coverage and reachability, meeting release, personal-continuity notes, out-of-office set and clear, return sweep. Use when planning time off, announcing an absence or arranging coverage."
license: "Apache-2.0"
depends_on: ["synthesis-chief-of-staff", "synthesis-agent-correspondence", "synthesis-catchup-ledger"]
metadata:
  author: "Rajiv Pant"
  version: "2.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
  format: v5
---

# Absence Coordination

Treats an absence as a handoff with a scheduled reversal: who decides in your place, what can wait, and how to reach you if it truly cannot. All names, tiers, channels and lead times load from a private config, so the skill is publishable and the configuration is yours.

## Binding rules

1. **If the config is missing, STOP and say so.** Never hardcode a name, address or channel that belongs in config.
2. **Write to the principals; cc their assistants.** One message: principals hear it from you, assistants get the same lead time.
3. **No group post before the principals are notified.** Groups are last, always.
4. **No send before a conflict check across every calendar,** including any outside the mirroring layer.
5. **No send before a coverage statement exists.** Coverage is sourced, never invented; if nobody covers, say so.
6. **Every work-tier notice carries coverage and reachability;** refuse to send one missing either.
7. **Principal-tier messages are never agent-sent** (`send_mode: draft_only`).
8. **Amendments update existing ledger rows, never repost.**
9. **Never use a distribution alias for a tier.** Explicit recipients only.
10. **Disclosure is per tier and mechanical;** when in doubt, the narrower content wins.
11. **Ship the quiet path.** Discretion about why is not discretion about who decides.
12. **The workflow ends at return, not departure:** clear the auto-responder, restore declined meetings, close the ledger rows.

## Contents

- [references/doctrine.md](references/doctrine.md): the handoff framing, notification order and hard gates, required content, recipient tiers, the personal-continuity tier, absence types and triggers, release notes. Read it before drafting any notice.
- [references/workflow.md](references/workflow.md): the six steps from pre-flight to return, the ledger, rollout order and adapting the skill. Read it when running an absence end to end.
- [references/config-schema.md](references/config-schema.md): every config field and the validator's exit codes. Read it when writing or fixing a config.
- [references/message-templates.md](references/message-templates.md): draft skeletons per tier and for the auto-responder. Read it before drafting.
- [references/quickstart.md](references/quickstart.md): the fifteen-minute adoption path. Read it on first install.
- [example-config.yaml](example-config.yaml): the commented starting config. Copy it when creating a config.
- [references/coverage-map.md](references/coverage-map.md): where each part of the 1.0.0 text now lives (ruling D8).
- Configuration contract, The five failures: below.

## Configuration contract

All specifics — names, addresses, tiers, channels, lead times, group IDs — live in a
private config the skill reads at load time:

```
~/.synthesis/absence-coordination/config.yaml
```

The skill is generic and publishable; the config is neither. Full schema:
[`references/config-schema.md`](references/config-schema.md). Starting point:
[`example-config.yaml`](example-config.yaml). Per-tier draft skeletons:
[`references/message-templates.md`](references/message-templates.md). Fifteen-minute
adoption path: [`references/quickstart.md`](references/quickstart.md). Validate with:

```bash
python3 validate_config.py ~/.synthesis/absence-coordination/config.yaml
```

**If the config is missing, STOP and say so.** Announcing an absence without knowing the
tier order is not a partial success; it is the specific failure this skill exists to
prevent. Never hardcode a name, address, or channel that belongs in config.

**Shared config.** Where `synthesis-chief-of-staff` is installed, this skill reads its
preferences file for calendar accounts, assistant relationships, and travel-disclosure
rules rather than duplicating them. One fact, one home. If both files define the same
fact, the chief-of-staff config wins and this skill's copy is a bug.

## The five failures this skill prevents

Everything below is machinery for these. When adapting the skill, keep the failures in
view; the machinery is negotiable, the failures are not.

1. **The relocated blocker** — an absence announced with no delegate.
2. **The secondhand notice** — someone's manager learns of their absence from a group
   channel, or from their own assistant, instead of from them.
3. **The silent conflict** — dates announced that collide with a commitment on a calendar
   nobody checked.
4. **The abandoned commitment** — recurring meetings left un-declined, a trainer left
   guessing, an auto-responder still firing a week after return.
5. **The default to disclosure** — a system that can only broadcast, so it goes unused
   exactly when discretion matters most.

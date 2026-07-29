# Why judgment / routine / bulk

The three role labels in this skill name **the work you hand a model**, not the model itself. This document records why those specific words were chosen, what they replaced, and which alternatives were considered and rejected — so the vocabulary's design survives its designers.

## The word that failed first

Version 1.x of this skill labeled the roles `frontier / efficient / light`. The top label collapsed within a day of shipping: the AI industry uses "frontier" to describe a vendor's *entire current generation*, not its top rung. OpenAI's own model documentation applies "frontier models" to all three GPT-5.6 models — Sol, Terra, and Luna — including the cost-optimized one. The same word, in the same domain, meant something different from what our table said.

That matters more for this vocabulary than for most, because its primary readers are LLM agents. An agent's training corpus is saturated with the vendor meaning; an agent that just read a vendor's docs mid-task will resolve "frontier" the vendor's way and fight your table. A tier vocabulary read by LLMs has to be selected for **corpus-collision resistance**, not just human clarity.

The general failure mode: any label borrowed from the industry's *live marketing vocabulary* inherits semantic drift you don't control. "Heavy" became Grok Heavy. "Balanced" is OpenAI's own copy for its mid-tier. "Base" means an un-finetuned model. Marketing reclaims words competitively, and you cannot predict which it claims next.

## What actually stays stable

Vendor ladders mutate constantly — three rungs, four, five; rungs merge; new top tiers appear. What stays stable is the shape of the **operator's decision**: *how much capability does this work deserve, given its stakes and volume?* That decision has three natural anchors regardless of any vendor's catalog:

- work where being wrong is expensive → **judgment**
- well-templated execution against established rules → **routine**
- high-volume, low-stakes processing → **bulk**

These were always the role *definitions* in this skill. The rename promoted the definitions into the labels — the stable part of the table was the right-hand column all along.

## The analogies that guided the choice

Other industries solved vendor-neutral grading over branded ladders long ago:

- **Fuel grades.** Premium / midgrade / regular have outlived every brand name laid over them (V-Power, Synergy, Ultimate). The grade vocabulary belongs to the buyer, not the vendor.
- **Airline cabins.** First / business / economy absorbed seventy years of rebrands (Polaris, Delta One, Mint) and rung changes (premium economy) without the class vocabulary breaking.
- **Shipping classes.** Express / standard / economy — equally durable, but a useful negative example: "express" connotes speed, and for LLMs the connotation *inverts* (the most capable models are the slowest). Test where an analogy breaks before adopting it.

The transferable structure: durable grade vocabularies name the **buyer's decision, not the product**. For model selection, the buyer's decision is the nature of the work — so the labels name the work.

## Properties the chosen words have

- **No collision, by construction.** Vendors name artifacts; these words name work. No vendor will market a "Routine" model. (Verified against vendor documentation and a web scan on 2026-07-14; re-verify if a collision is ever suspected.)
- **The label alone instructs.** "This is bulk work" tells an agent what to do without consulting the table. The label carries the policy.
- **Ladder mutations become list edits.** If a vendor ships a tier above its current flagship, the judgment role's ordered preference list gains an entry at the front. If two rungs merge, a list shrinks. The schema never changes.
- **Small catalogs map cleanly.** A two-model vendor can serve routine and bulk with the same model without contradiction — the same class of work going to the same model reads naturally, where "standard and economy are the same product" would not.

## Considered and rejected

| Candidate | Why not |
|---|---|
| critical / routine / bulk | Sound alternative; "critical" reads as urgency/emergency (incident-severity vocabulary), and "judgment" names what the model contributes rather than what the task risks |
| premium / standard / economy | The strong runner-up — the convergent fuel/airline/shipping vocabulary. But it names price positioning rather than work, and cross-vendor price positioning is unreliable: some vendors price their flagship at other vendors' mid-tier |
| performance / balanced / efficiency | "Balanced" is live vendor marketing copy; "efficiency" sits at the bottom of Apple's P/E-core vocabulary while this skill's middle rung was previously named "efficient" — a silent meaning-shuffle |
| heavy / medium / light | Grok Heavy; Mistral Medium |
| lite / mini / nano / pro | All live vendor rung names |
| base | Term of art for un-finetuned models |
| deep | DeepSeek, Deep Research, deep-thinking modes |
| express / standard / economy | Speed connotation inverts for LLMs |
| S / A / B tiers | Informal; ordering fuzzy past S |
| small / medium / large | Sizes the artifact, not the work; "small model" is now a term of art (SLMs) |

## The borrowing rule

One industry word survives in this skill: `flagship`, used by product catalogs (e.g. Ragbot's `engines.yaml`) as a per-provider selector for the vendor's showcase model. It stays because there the skill means *exactly* what the industry means. That is the general rule this vocabulary follows:

> **Borrow an industry word only where you mean exactly what the industry means. Where you mean something else, choose a word from outside the industry's semantic battleground.**

## Why three roles, even for five-rung vendors

Roles describe work; rung counts describe catalogs. The ordered preference lists absorb the mismatch in both directions (a five-rung ladder expresses extras as fallbacks; a two-rung ladder repeats a model across roles). A standing fourth role would only earn its existence if a durable class of work emerged that deserves a vendor's newest super-tier but not its previous flagship — and until then, per-task escalation within the judgment role's ordered list covers the rare spare-no-expense call. The schema is additive if that day comes.

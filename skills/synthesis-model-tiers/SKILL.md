---
name: synthesis-model-tiers
description: "Cross-provider model-tier convention for agentic work: three role labels (judgment, routine, bulk — formerly frontier, efficient, light) resolved to current model IDs per provider in tiers.yaml, so skills, project docs, and memory never hardcode model names. Also carries the role-selection rule: route by whether the CAUSE is known, not by how small the task looks — a symptom report is diagnosis and belongs in judgment even when the subject is one file. Use when asked about: model tiers, which model, model selection, judgment model, routine model, bulk model, frontier model, efficient model, switch models, model equivalents across providers, update model table, which effort level, low effort, wrong model for the task."
license: "CC0-1.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "2.1.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Synthesis Model Tiers

A tiny convention that keeps model names out of everything except one file.

Skills, project context files, agent memory, and standing instructions reference **role labels**; the labels resolve to current model identifiers in [`tiers.yaml`](tiers.yaml). When a vendor ships a new generation, one file changes and every consumer is current.

## The three roles

| Role | Use for | Character |
|---|---|---|
| **judgment** | Judgment calls, novel patterns, skill/script authorship, cross-system changes — anywhere being wrong is expensive | The most capable model you can afford |
| **routine** | Routine rule-following execution: daily sweeps, mechanical runs, well-templated work | The balanced default |
| **bulk** | High-volume, low-stakes work: classification at scale, summarization drips | The cheapest adequate option |

Three roles, deliberately — even when a vendor's ladder has four or five rungs. Roles describe **the work**, not the vendor's catalog.

## Choosing a role: diagnostic difficulty, not apparent size

The most common misroute is sending a **small-sounding** task to a cheap tier. Size is not the variable. **Whether the cause is known** is the variable.

- **Cause known** → the specification is settled and the work is execution: apply this rename, run this suite, add this row, reformat these files. This is `routine` or `bulk`.
- **Cause unknown** → the work is *diagnosis*, whatever its apparent size. Anything phrased as a symptom — "X isn't working," "this broke," "why is it doing that," "the file won't open" — is a differential over a chain of candidate causes. Cost scales with the search, not with the fix. **This is `judgment` even when the subject is one file.**

Cheap reasoning on a diagnosis does not return a smaller correct answer. It takes the first plausible branch and commits — and the confidence is what gets the wrong answer written, committed, and pushed.

Three properties force `judgment` regardless of how small the request sounds. Any one is sufficient:

1. **The cause is unknown** (the rule above).
2. **The blast radius includes a deliverable or a durable record.** Reading is cheap; writing to something another agent, a client, or a future session will rely on is not — however small the edit.
3. **The work will not be independently reviewed before it lands.** Work that bypasses an existing review gate carries that gate's weight itself.

**The asymmetry that makes this a cost, not a preference.** Where a mistake must be caught and undone by a more expensive process, the cheap attempt is not a saving — it is a debt with interest. The diagnosis, the revert, and the re-verification all get paid at the higher tier anyway, plus the principal's attention in between.

**The trust dependency is the sharpest part.** A low-tier agent's plausible-sounding wrong explanation transfers the entire verification burden back to the human, which inverts the reason for delegating. A principal who accepts a confident, coherent, wrong diagnosis inherits the defect silently.

The shape to recognize, from a real instance: a "this file won't open" report was routed to a cheap tier. The symptom was a broken *link* — a two-ended thing — and the cheap session inspected only the file, never the link text sitting in the preceding message. It built a plausible theory from a diagnostic tool's output, rewrote the file to satisfy that tool, watched the tool go quiet, and committed. The tool's approval was real; it was also irrelevant to the reported symptom, which remained unfixed while the file itself was degraded. **A green signal from the wrong oracle is more dangerous than no signal, because it terminates the investigation.**

## Why these words

The labels name the work you hand a model, not the model itself — because vendor vocabulary is unstable by design. v1.x of this skill used `frontier/efficient/light`; "frontier" collapsed within a day when it turned out the industry applies that word to a vendor's *entire current generation* (OpenAI labels all three GPT-5.6 models "frontier"). Work categories are the thing no vendor's marketing will ever collide with: nobody ships a "Routine" model. The full reasoning — the selection criteria, the fuel-grade and airline-cabin analogies, and every rejected candidate — is in [`references/naming-rationale.md`](references/naming-rationale.md).

The borrowing rule that fell out of the rename: **borrow an industry word only where you mean exactly what the industry means** (`flagship` = the vendor's showcase model — kept; `frontier` — dropped).

## Resolution rules

1. Look up `providers.<provider>.<role>` in `tiers.yaml`. The list is an **ordered preference**: first entry preferred, later entries are supported fallbacks (cost, availability). Example: a provider may prefer its newest top model while keeping the previous flagship as the cost-conscious fallback in the same role.
2. A provider with fewer rungs than another lists one model per role — the same model may serve two roles. When a vendor merges two rungs, a list shrinks; no schema change.
3. **Local providers** (e.g., Ollama) are hardware-gated: their role lists carry only models that fit the operator's machine. A product catalog may keep bigger models for future hardware — catalog ⊇ role lists is allowed; the reverse is drift.
4. `clients:` carries selector strings **only where a client UI differs from the API id**. Absent an entry, the API id is the selector.
5. Agents generally **cannot switch their own model** — model selection is a client-side action the human performs (e.g., Claude Code's `/model`). When work calls for a different tier, say so and wait; do not attempt workarounds.
6. **An agent that finds itself under-tiered for the work must say so before acting**, not after. If a task arrives looking routine and turns out to be diagnosis — the cause is unknown, or a deliverable is in the blast radius — name that and let the human re-tier. Proceeding anyway and reporting a confident result is the failure mode this skill exists to prevent, and it is the one an agent is least able to detect in itself afterward.

## What this file is NOT

- **Not a capability catalog.** Context windows, pricing, token limits, and thinking modes belong to each product's own config (e.g., Ragbot's `engines.yaml`). This file only maps roles to ids.
- **Not a second vocabulary.** Product catalogs use the **same** three words in a per-model `tier:` field (`judgment` / `routine` / `bulk`); this file adds the cross-provider ordered preference within each role. One vocabulary, two responsibilities — and a consistency test keeps them agreeing (see Consumer guidance).
- **Not telemetry or history.** It reflects the present. Past choices live in session logs (see the Agent Attribution convention in synthesis-context-lifecycle).

## Update protocol

1. Verify identifiers against the provider's **official documentation** before editing — never from an agent's training data, which is reliably stale for model releases.
2. Record the verification date per provider (`verified:`).
3. Unknown values are the literal string `unknown` — never a guess. A wrong model id in a canonical table is worse than an explicit gap.
4. Models only move **forward**. If a listed model errors, the problem is configuration or code, not the model choice.
5. After editing, propagate: reinstall skill copies and refresh any human-readable mirror (e.g., a Model Tier Convention section in global agent instructions).
6. If a role label is ever suspected of colliding with live vendor vocabulary, re-run the collision check in `references/naming-rationale.md` before writing the label into anything new.

## Consumer guidance

- **In skills and project docs:** write "use a judgment-tier model" or "routine-tier is sufficient," optionally with the pointer *(resolve via synthesis-model-tiers)*.
- **In agent memory/preferences:** store the role rule ("routine for daily sweeps; judgment when the rules don't cover it"), not the model name.
- **In products:** read `tiers.yaml` programmatically, or carry a per-model `tier:` field in the product's own catalog using the same vocabulary — and enforce agreement with a test rather than reconciling by eye. Reference implementation: Ragbot's `tests/test_engines_yaml.py` (`TestTierVocabulary`, `TestTierRoleConsistency`), which validates every catalog tier and cross-checks the installed `tiers.yaml`, skipping cleanly where the skill isn't installed.

## License

CC0-1.0. Part of the synthesis-skills collection.

## Author

[Rajiv Pant](https://rajiv.com).

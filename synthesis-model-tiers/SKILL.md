---
name: synthesis-model-tiers
description: "Cross-provider model-tier convention for agentic work: three role labels (frontier, efficient, light) resolved to current model IDs per provider in tiers.yaml, so skills, project docs, and memory never hardcode model names. Use when asked about: model tiers, which model, model selection, frontier model, efficient model, switch models, model equivalents across providers, update model table."
license: "CC0-1.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Synthesis Model Tiers

A tiny convention that keeps model names out of everything except one file.

Skills, project context files, agent memory, and standing instructions reference **role labels**; the labels resolve to current model identifiers in [`tiers.yaml`](tiers.yaml). When a vendor ships a new generation, one file changes and every consumer is current.

## The three roles

| Role | Use for | Character |
|---|---|---|
| **frontier** | Judgment calls, novel patterns, skill/script authorship, cross-system changes — anywhere being wrong is expensive | The most capable model you can afford |
| **efficient** | Routine rule-following execution: daily sweeps, mechanical runs, well-templated work | The balanced default |
| **light** | High-volume, low-stakes bulk work: classification at scale, summarization drips | The cheapest adequate option |

Three roles, deliberately — even when a vendor's ladder has four rungs. Roles describe **the work**, not the vendor's catalog.

## Resolution rules

1. Look up `providers.<provider>.<role>` in `tiers.yaml`. The list is an **ordered preference**: first entry preferred, later entries are supported fallbacks (cost, availability). Example: a provider may prefer its newest frontier model while keeping the previous flagship as the cost-conscious fallback in the same role.
2. A provider with fewer rungs than another lists one model per role. When a vendor merges two rungs, the list shrinks — no schema change.
3. `clients:` carries selector strings **only where a client UI differs from the API id**. Absent an entry, the API id is the selector.
4. Agents generally **cannot switch their own model** — model selection is a client-side action the human performs (e.g., Claude Code's `/model`). When work calls for a different tier, say so and wait; do not attempt workarounds.

## What this file is NOT

- **Not a capability catalog.** Context windows, pricing, token limits, and thinking modes belong to each product's own config (e.g., Ragbot's `engines.yaml`). This file only maps roles to ids.
- **Not telemetry or history.** It reflects the present. Past choices live in session logs (see the Agent Attribution convention in synthesis-context-lifecycle).

## Update protocol

1. Verify identifiers against the provider's **official documentation** before editing — never from an agent's training data, which is reliably stale for model releases.
2. Record the verification date per provider (`verified:`).
3. Unknown values are the literal string `unknown` — never a guess. A wrong model id in a canonical table is worse than an explicit gap.
4. Models only move **forward**. If a listed model errors, the problem is configuration or code, not the model choice.
5. After editing, propagate: reinstall skill copies and refresh any human-readable mirror (e.g., a Model Tier Convention section in global agent instructions).

## Consumer guidance

- **In skills and project docs:** write "use a frontier-tier model" or "efficient-tier is sufficient," optionally with the pointer *(resolve via synthesis-model-tiers)*.
- **In agent memory/preferences:** store the role rule ("efficient for routine sweeps; frontier when the rules don't cover it"), not the model name.
- **In products:** read `tiers.yaml` programmatically, or maintain a `tier:`/`category:` mapping in the product's own catalog that a maintainer reconciles against this file.

## License

CC0-1.0. Part of the synthesis-skills collection.

## Author

[Rajiv Pant](https://rajiv.com).

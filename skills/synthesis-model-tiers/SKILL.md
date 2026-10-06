---
name: synthesis-model-tiers
description: "Cross-provider model-tier convention: role labels judgment, routine and bulk resolved to model IDs per provider in tiers.yaml, routed by whether the cause is known. Use for model tiers, which model or effort level, model selection, switching models, model equivalents, or updating the model table."
license: "CC0-1.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "3.0.0"
  format: v5
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Synthesis Model Tiers

A tiny convention that keeps model names out of everything except one file.

Skills, project context files, agent memory, and standing instructions reference **role labels**; the labels resolve to current model identifiers in [`tiers.yaml`](tiers.yaml). When a vendor ships a new generation, refresh the table and verify each consuming catalog; a table edit alone does not update installed clients or product configuration.

## Binding rules

1. **Never hardcode a model name** in skills, project docs, agent memory or standing instructions. Write the role label; it resolves in `tiers.yaml`.
2. **Route by whether the cause is known, not by how small the task looks.** A symptom report is diagnosis and belongs in `judgment`, even when the subject is one file.
3. **Any one of three properties forces `judgment`:** the cause is unknown; a deliverable or durable record is in the blast radius; the work will not be independently reviewed before it lands.
4. **Say you are under-tiered before acting, not after,** and let the human re-tier. A confident wrong result is the failure this skill exists to prevent.
5. **Agents generally cannot switch their own model.** Say a different tier is needed and wait; no workarounds.
6. **The table guides new selections only.** Never override an explicit user model or reasoning-effort choice, and never switch models or lower effort automatically to conceal a failure.
7. **Verify identifiers against official provider documentation, never training data.** An unknown value is the literal `unknown`, never a guess.
8. **A table edit is not an installation.** Run the catalog fixtures and each consumer's consistency tests; catalog verification is not live acceptance.

## Contents

- [`tiers.yaml`](tiers.yaml): the role lists per provider, with identifier namespaces and client overrides. Read it to resolve a role.
- [references/choosing-a-role.md](references/choosing-a-role.md): the diagnosis rule in full, the three properties, the cost asymmetry and a real misroute. Read it when a task's tier is not obvious.
- [references/maintaining-the-table.md](references/maintaining-the-table.md): the update protocol and consumer guidance. Read it before editing the table or wiring a consumer.
- [references/catalog-verification.yaml](references/catalog-verification.yaml): documentation dates, native IDs and source URLs per entry. Update it with every table edit.
- [references/naming-rationale.md](references/naming-rationale.md): the selection criteria, analogies and rejected candidates for the labels. Read it before proposing a new label.
- [references/background.md](references/background.md): why these words, what this file is not, license, author.
- [references/coverage-map.md](references/coverage-map.md): where each part of the 2.2.0 text now lives.
- The three roles, Resolution rules: below.

## The three roles

| Role | Use for | Character |
|---|---|---|
| **judgment** | Judgment calls, novel patterns, skill/script authorship, cross-system changes — anywhere being wrong is expensive | The most capable model you can afford |
| **routine** | Routine rule-following execution: daily sweeps, mechanical runs, well-templated work | The balanced default |
| **bulk** | High-volume, low-stakes work: classification at scale, summarization drips | The cheapest adequate option |

Three roles, deliberately — even when a vendor's ladder has four or five rungs. Roles describe **the work**, not the vendor's catalog.

## Resolution rules

1. Look up `providers.<provider>.<role>` in `tiers.yaml`. The list is an **ordered preference**: first entry preferred, later entries are documented alternatives. This is guidance for a new selection, never authority to change an explicit user model or reasoning-effort choice. Preserve that choice even when catalog defaults change; account availability and host policy are separate checks.
2. A provider with fewer rungs than another lists one model per role — the same model may serve two roles. When a vendor merges two rungs, a list shrinks; no schema change.
3. **Local providers** (e.g., Ollama) are hardware-gated at execution: a documented tag does not establish installation, RAM fit at the requested context, or acceptable performance. When `hardware_fit` is `unknown`, verify those conditions before recommending execution; do not download a model as a verification side effect. A product catalog may contain more models than the role lists; missing listed models remain drift.
4. Read `identifier_namespace` before constructing a selector. OpenAI and Anthropic entries are native API IDs; Ollama entries are tags; Google entries use the LiteLLM `gemini/` route prefix. `clients.<client>.<provider>.<catalog-id>` records a documented override: `gemini-api` uses bare IDs, while LiteLLM keeps the prefix. No override means no documented translation, not proof that every client accepts that ID. Claude Code family aliases and third-party deployments can resolve differently; use the exact endpoint's verified selector. A local client catalog proves what that client advertises, not public API support or account access.
5. Agents generally **cannot switch their own model** — model selection is a client-side action the human performs (e.g., Claude Code's `/model`). When work calls for a different tier, say so and wait; do not attempt workarounds.
6. **An agent that finds itself under-tiered for the work must say so before acting**, not after. If a task arrives looking routine and turns out to be diagnosis — the cause is unknown, or a deliverable is in the blast radius — name that and let the human re-tier. Proceeding anyway and reporting a confident result is the failure mode this skill exists to prevent, and it is the one an agent is least able to detect in itself afterward.

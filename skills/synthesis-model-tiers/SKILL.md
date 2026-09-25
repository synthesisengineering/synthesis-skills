---
name: synthesis-model-tiers
description: "Cross-provider model-tier convention for agentic work: three role labels (judgment, routine, bulk — formerly frontier, efficient, light) resolved to current model IDs per provider in tiers.yaml, so skills, project docs, and memory never hardcode model names. Also carries the role-selection rule: route by whether the CAUSE is known, not by how small the task looks — a symptom report is diagnosis and belongs in judgment even when the subject is one file. Use when asked about: model tiers, which model, model selection, judgment model, routine model, bulk model, frontier model, efficient model, switch models, model equivalents across providers, update model table, which effort level, low effort, wrong model for the task."
license: "CC0-1.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "2.2.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Synthesis Model Tiers

A tiny convention that keeps model names out of everything except one file.

Skills, project context files, agent memory, and standing instructions reference **role labels**; the labels resolve to current model identifiers in [`tiers.yaml`](tiers.yaml). When a vendor ships a new generation, refresh the table and verify each consuming catalog; a table edit alone does not update installed clients or product configuration.

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

1. Look up `providers.<provider>.<role>` in `tiers.yaml`. The list is an **ordered preference**: first entry preferred, later entries are documented alternatives. This is guidance for a new selection, never authority to change an explicit user model or reasoning-effort choice. Preserve that choice even when catalog defaults change; account availability and host policy are separate checks.
2. A provider with fewer rungs than another lists one model per role — the same model may serve two roles. When a vendor merges two rungs, a list shrinks; no schema change.
3. **Local providers** (e.g., Ollama) are hardware-gated at execution: a documented tag does not establish installation, RAM fit at the requested context, or acceptable performance. When `hardware_fit` is `unknown`, verify those conditions before recommending execution; do not download a model as a verification side effect. A product catalog may contain more models than the role lists; missing listed models remain drift.
4. Read `identifier_namespace` before constructing a selector. OpenAI and Anthropic entries are native API IDs; Ollama entries are tags; Google entries use the LiteLLM `gemini/` route prefix. `clients.<client>.<provider>.<catalog-id>` records a documented override: `gemini-api` uses bare IDs, while LiteLLM keeps the prefix. No override means no documented translation, not proof that every client accepts that ID. Claude Code family aliases and third-party deployments can resolve differently; use the exact endpoint's verified selector. A local client catalog proves what that client advertises, not public API support or account access.
5. Agents generally **cannot switch their own model** — model selection is a client-side action the human performs (e.g., Claude Code's `/model`). When work calls for a different tier, say so and wait; do not attempt workarounds.
6. **An agent that finds itself under-tiered for the work must say so before acting**, not after. If a task arrives looking routine and turns out to be diagnosis — the cause is unknown, or a deliverable is in the blast radius — name that and let the human re-tier. Proceeding anyway and reporting a confident result is the failure mode this skill exists to prevent, and it is the one an agent is least able to detect in itself afterward.

## What this file is NOT

- **Not a capability catalog.** Context windows, pricing, token limits, and thinking modes belong to each product's own config (e.g., Ragbot's `engines.yaml`). This file only maps roles to ids.
- **Not a second vocabulary.** Product catalogs use the **same** three words in a per-model `tier:` field (`judgment` / `routine` / `bulk`); this file adds the cross-provider ordered preference within each role. One vocabulary, two responsibilities — and a consistency test keeps them agreeing (see Consumer guidance).
- **Not telemetry or history.** It reflects the present. Past choices live in session logs (see the Agent Attribution convention in synthesis-context-lifecycle).

## Update protocol

1. Verify identifiers against the provider's **official documentation** before editing — never from an agent's training data, which is reliably stale for model releases.
2. Record the documentation retrieval date per provider (`verified:`), exact native IDs and primary URLs in [`references/catalog-verification.yaml`](references/catalog-verification.yaml). Bind every role-list entry to its source. The date attests to identifier documentation only; endpoint availability, installed state and runtime acceptance require separate evidence. Preserve historical verification dates if a fresh lookup does not establish the entry.
3. Unknown values are the literal string `unknown` — never a guess. A wrong model id in a canonical table is worse than an explicit gap.
4. Do not remove or downgrade a newer entry because documentation retrieval failed. Preserve it with an explicit unresolved verification finding. An execution error can indicate retirement, account access, endpoint/client configuration, or a code defect: diagnose it from current evidence. Never switch models or lower effort automatically to conceal that failure.
5. Run the offline catalog fixtures and each affected consumer's consistency tests against this exact file before adoption. Product capability catalogs must be updated with independently verified product fields; do not invent pricing, context limits or capabilities to silence drift. After the approved source package passes review and CI, use the gated installation process and refresh human-readable mirrors. Catalog verification is not installation or live acceptance.
6. If a role label is ever suspected of colliding with live vendor vocabulary, re-run the collision check in `references/naming-rationale.md` before writing the label into anything new.

## Consumer guidance

- **In skills and project docs:** write "use a judgment-tier model" or "routine-tier is sufficient," optionally with the pointer *(resolve via synthesis-model-tiers)*.
- **In agent memory/preferences:** store the role rule ("routine for daily sweeps; judgment when the rules don't cover it"), not the model name.
- **In products:** read `tiers.yaml` programmatically, or carry a per-model `tier:` field in the product's own catalog using the same vocabulary — and enforce agreement with a test rather than reconciling by eye. Reference implementation: Ragbot's `tests/test_engines_yaml.py` (`TestTierVocabulary`, `TestTierRoleConsistency`), which validates every catalog tier and cross-checks `tiers.yaml`. Set `SYNTHESIS_TIERS_FILE` to the exact candidate file during acceptance; its legacy install-path search can miss native plugin installations. A skipped lookup is not a passing consistency check. Run this skill's `scripts/test_catalog.py` for offline schema, provenance and selector controls. These tests do not call providers or verify endpoint availability.

## License

CC0-1.0. Part of the synthesis-skills collection.

## Author

[Rajiv Pant](https://rajiv.com).

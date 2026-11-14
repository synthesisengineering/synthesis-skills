# Model tiers: why these words, what this file is not, license and author

Moved verbatim from the 2.2.0 SKILL.md; only link paths changed. Read it when someone proposes a new label or asks what `tiers.yaml` should hold.

## Why these words

The labels name the work you hand a model, not the model itself — because vendor vocabulary is unstable by design. v1.x of this skill used `frontier/efficient/light`; "frontier" collapsed within a day when it turned out the industry applies that word to a vendor's *entire current generation* (OpenAI labels all three GPT-5.6 models "frontier"). Work categories are the thing no vendor's marketing will ever collide with: nobody ships a "Routine" model. The full reasoning — the selection criteria, the fuel-grade and airline-cabin analogies, and every rejected candidate — is in [`references/naming-rationale.md`](naming-rationale.md).

The borrowing rule that fell out of the rename: **borrow an industry word only where you mean exactly what the industry means** (`flagship` = the vendor's showcase model — kept; `frontier` — dropped).

## What this file is NOT

- **Not a capability catalog.** Context windows, pricing, token limits, and thinking modes belong to each product's own config (e.g., Ragbot's `engines.yaml`). This file only maps roles to ids.
- **Not a second vocabulary.** Product catalogs use the **same** three words in a per-model `tier:` field (`judgment` / `routine` / `bulk`); this file adds the cross-provider ordered preference within each role. One vocabulary, two responsibilities — and a consistency test keeps them agreeing (see Consumer guidance).
- **Not telemetry or history.** It reflects the present. Past choices live in session logs (see the Agent Attribution convention in synthesis-context-lifecycle).

## License

CC0-1.0. Part of the synthesis-skills collection.

## Author

[Rajiv Pant](https://rajiv.com).

# Model tiers: updating the table and consuming it

Moved verbatim from the 2.2.0 SKILL.md; only link paths changed. Read it before editing `tiers.yaml` or `catalog-verification.yaml`, or when wiring a product, skill or memory to the role labels.

## Update protocol

1. Verify identifiers against the provider's **official documentation** before editing — never from an agent's training data, which is reliably stale for model releases.
2. Record the documentation retrieval date per provider (`verified:`), exact native IDs and primary URLs in [`references/catalog-verification.yaml`](catalog-verification.yaml). Bind every role-list entry to its source. The date attests to identifier documentation only; endpoint availability, installed state and runtime acceptance require separate evidence. Preserve historical verification dates if a fresh lookup does not establish the entry.
3. Unknown values are the literal string `unknown` — never a guess. A wrong model id in a canonical table is worse than an explicit gap.
4. Do not remove or downgrade a newer entry because documentation retrieval failed. Preserve it with an explicit unresolved verification finding. An execution error can indicate retirement, account access, endpoint/client configuration, or a code defect: diagnose it from current evidence. Never switch models or lower effort automatically to conceal that failure.
5. Run the offline catalog fixtures and each affected consumer's consistency tests against this exact file before adoption. Product capability catalogs must be updated with independently verified product fields; do not invent pricing, context limits or capabilities to silence drift. After the approved source package passes review and CI, use the gated installation process and refresh human-readable mirrors. Catalog verification is not installation or live acceptance.
6. If a role label is ever suspected of colliding with live vendor vocabulary, re-run the collision check in `references/naming-rationale.md` before writing the label into anything new.

## Consumer guidance

- **In skills and project docs:** write "use a judgment-tier model" or "routine-tier is sufficient," optionally with the pointer *(resolve via synthesis-model-tiers)*.
- **In agent memory/preferences:** store the role rule ("routine for daily sweeps; judgment when the rules don't cover it"), not the model name.
- **In products:** read `tiers.yaml` programmatically, or carry a per-model `tier:` field in the product's own catalog using the same vocabulary — and enforce agreement with a test rather than reconciling by eye. Reference implementation: Ragbot's `tests/test_engines_yaml.py` (`TestTierVocabulary`, `TestTierRoleConsistency`), which validates every catalog tier and cross-checks `tiers.yaml`. Set `SYNTHESIS_TIERS_FILE` to the exact candidate file during acceptance; its legacy install-path search can miss native plugin installations. A skipped lookup is not a passing consistency check. Run this skill's `scripts/test_catalog.py` for offline schema, provenance and selector controls. These tests do not call providers or verify endpoint availability.

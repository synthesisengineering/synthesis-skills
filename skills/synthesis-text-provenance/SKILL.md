---
name: synthesis-text-provenance
description: "Use to plan, record and audit text provenance for hosted and open-weight models: watermark capability checks, reproducible manifests, mixed-authorship lineage, text-integrity audits, authorized detector results. Not for defeating provider marks, evading detectors or disguising AI authorship."
license: Apache-2.0
depends_on: []
metadata:
  author: Rajiv Pant
  version: "2.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
  format: v5
---

# Synthesis Text Provenance

Records how text was produced and changed, and keeps every claim about it inside what the evidence shows.

## Binding rules

1. **Keep four judgments separate:** quality, style, technical provenance and authorship. No result on one axis proves another.
2. **Never build or run a workflow whose objective is to defeat a mark or a detector**, or to pass AI-assisted text off as human (the boundary below).
3. **Record the requirement before choosing a model:** privacy, reproducibility, mark policy, disclosure, quality, allowed runtimes, detector authorization.
4. **Re-verify capability claims** in current primary documentation, recording provider, exact model, surface, region and date.
5. **Prefer prevention.** If provider-added marking conflicts with the requirement, choose an authorized local/open-weight model before generating; if nothing satisfies both quality and provenance, report the conflict.
6. **Preserve raw input, output and hashes before editing**; hash-bind the native runtime receipt; validate and verify the manifest and its direct parents.
7. **Audit without rewriting.** The integrity audit reports Unicode facts, never writes a cleaned copy, and is not proof of a statistical watermark.
8. **No detector result becomes an optimization loop.**
9. **Bound every conclusion.** Never write "watermark-free," "undetectable," "human-written," or "clean" when the evidence shows a narrower fact.

## Contents

- [references/workflow.md](references/workflow.md): the seven steps in full with every command and option. Read it when running a step for the first time in a session.
- [references/capability-claims.md](references/capability-claims.md): evidence classes and bounded language. Read it before stating what a provider or detector does.
- [references/open-weight-runner-contract.md](references/open-weight-runner-contract.md): the loopback runner contract. Read it before local generation.
- [references/provenance-manifest.md](references/provenance-manifest.md): manifest schema and field semantics. Read it when creating or checking a manifest.
- [references/coverage-map.md](references/coverage-map.md): where each part of the 1.0.1 text now lives (ruling D8).
- Four judgments, Non-negotiable boundary, Trigger boundary, Scripts, Completion checklist: below.

## Four judgments

Build a reproducible account of how text was produced and changed. Keep four
judgments separate:

1. **Quality:** whether the prose is worth using.
2. **Style:** whether it contains slop or model-shaped patterns.
3. **Technical provenance:** whether a documented signal or credential is
   present, absent, unverifiable, or unknown.
4. **Authorship:** who wrote or edited the text and which tools participated.

No result on one axis proves another. A detector miss does not prove human
authorship or watermark absence. Strong prose does not prove human authorship.
A provider mark does not identify which person submitted or edited the text.

## Non-negotiable boundary

Do not provide or execute a workflow whose objective is to:

- strip or defeat a provider watermark;
- mutate text until a provenance detector stops firing;
- optimize paraphrasing, token substitutions, translation, sampling, or model
  choice against detector feedback;
- represent AI-assisted text as solely human-authored;
- promise output is watermark-free or statistical-fingerprint-free.

When a user needs control over provider-added signals, prefer prevention by
choosing a local/open-weight model before generation, plus transparent lineage.
If the text already exists, preserve it, audit only with authorized tools, and
report the result without turning it into a mutation objective.

## Trigger boundary

Use this skill when the request concerns:

- choosing between hosted and local/open-weight generation for provenance;
- preserving model, runtime, prompt, output, parameter, and edit lineage;
- checking current provider or standards documentation about text marking;
- recording an authorized detector result;
- inspecting invisible Unicode or normalization properties;
- making or reviewing a claim that text is marked, unmarked, AI-authored, or
  human-authored.

Use [`synthesis-content-quality`](../synthesis-content-quality/SKILL.md) for
editorial quality and model-shaped prose. Use
[`synthesis-clean-text`](../synthesis-clean-text/SKILL.md) for ordinary text
normalization. This skill owns provenance mechanics and claim boundaries.

## Scripts

Run from the skill folder. Full flags are in references/workflow.md, steps 4 to 6.

- `python3 scripts/provenance_manifest.py create ... --manifest provenance.json` prints `created canonical self-hashed schema-2 manifest`; `validate provenance.json` prints `valid ...`; `verify provenance.json` checks the self-hash, referenced files and `--parent-manifest` links.
- `python3 scripts/text_integrity_audit.py article.txt --format human` (or `--format json --fail-on-findings`) prints code points, positions, normalization differences, hashes and line endings; exit 1 on findings with that flag, 2 on error.
- `python3 scripts/ollama_metadata.py --model example-model --output ollama-metadata.json` writes the bounded Ollama runtime receipt.
- `python3 scripts/local_generate.py --endpoint http://127.0.0.1:11434/v1/chat/completions ...` generates once and writes the output and a valid manifest.

## Completion checklist

- [ ] Exact model, surface, runtime, and collection date are recorded.
- [ ] Hosted versus local selection follows the stated requirement.
- [ ] Raw input/output and hashes are preserved before editing.
- [ ] Native runtime receipt is hash-bound for local generation.
- [ ] Manifest validation, self-hash, file hashes, and direct-parent lineage
      verification pass.
- [ ] Detector access and authorization are recorded, if used.
- [ ] No detector result was used as an optimization loop.
- [ ] Positive and negative conclusions are bounded to the evidence.
- [ ] Editorial quality is reviewed separately with the writing-quality stack.

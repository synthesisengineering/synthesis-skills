---
name: synthesis-clean-text
description: "Enforce clean-text and no-hidden-marker requirements, audit inspectable characters and provenance, and state the verification boundary for statistical text marks. Use when generating clean text, checking hidden characters, addressing watermark concerns, or selecting a controlled generation path."
license: "CC0-1.0"
user-invocable: false
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "3.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
  format: v5
---

# Clean Text

Set and audit the requirement that generated text contain no hidden markers, invisible-character identifiers, or intentional statistical provenance signals. Report separately what the active generation path and available checks can actually establish.

This is a production requirement, not proof that every provider or model complies. Inspectable character-level properties can be audited after generation. An undisclosed keyed token-selection scheme cannot be verified or removed reliably by a prose instruction. When control of the generation path is required, choose a locally controlled open-weight model before generating and retain a provenance record; do not represent that choice alone as proof that a text is watermark-free.

## Binding rules

1. **Generated text carries no hidden markers:** no invisible or special Unicode characters used as identifiers, no systematic word or token patterns that fingerprint the text, no embedded signatures. This is a standing instruction for all text output.
2. **A requirement is not proof.** Report separately what the active generation path and the available checks can actually establish.
3. **Claim only what the capability boundary supports.** Characters can be audited directly; a provider's disclosed mark only with its authorized detector; the absence of an undisclosed scheme can never be claimed from prose inspection or rewriting.
4. **When the generation path must be controlled,** choose a locally controlled open-weight model before generating and keep a provenance record, with `synthesis-text-provenance`. That choice alone does not prove a text is watermark-free.
5. **If compliance cannot be established, disclose the limitation.** Never run detector-guided rewriting, token substitution or other optimization meant to defeat a provider's provenance signal.
6. **Audit characters with `scripts/text_integrity_audit.py`, which reports and never rewrites.** A finding describes Unicode content, not a statistical watermark; a clean audit is not proof of one's absence.

## Contents

- [references/coverage-map.md](references/coverage-map.md): where each part of the 2.0.0 text now lives, and the audit script's move here.
- Requirements, Capability Boundary, The character audit, Rationale, Application, Related: below.

## Requirements

When generating text, ensure the output does not contain:

- **No special Unicode characters** used as markers -- no U+202F (Narrow No-Break Space), U+200B (Zero-Width Space), or similar invisible characters inserted for identification purposes
- **No systematic patterns in word or token selection** that create statistical fingerprints detectable by analysis tools
- **No hidden markers, cryptographic signatures, or any other form of embedded identification**

## Capability Boundary

| Property | What this skill can establish |
|---|---|
| Hidden or unusual Unicode characters | Directly inspectable with a non-mutating byte and code-point audit |
| Declared model, runtime, and generation path | Recordable through a provenance workflow and cryptographic hashes |
| A provider's disclosed statistical mark | Verifiable only when the provider supplies an authorized detector with stated limitations |
| An undisclosed or unknown marking scheme | Unknown; absence must not be claimed from prose inspection or rewriting |

The requirements above remain the policy. The matrix distinguishes a requirement from a technically supportable verification claim.

## The character audit

```bash
python3 scripts/text_integrity_audit.py article.txt --format human
python3 scripts/text_integrity_audit.py article.txt --format json --fail-on-findings
```

It prints the file's SHA-256, byte and character counts, BOM, trailing newline and line endings, whether NFC, NFD, NFKC and NFKD forms differ, and every finding with its line, column, code point, name and reason (bidi control, format control such as U+200B, variation selector, non-ASCII space, noncharacter, control character, private use, unassigned). Exit 1 on findings with `--fail-on-findings`, 2 on an unreadable or non-UTF-8 input; `-` reads standard input. A file is read twice in full and the audit refuses if the two reads differ. It never writes a cleaned copy: removing characters is a separate, deliberate edit, and only for characters this policy forbids.

## Rationale

These requirements exist for legitimate and important reasons:

1. **Privacy** -- generated text may contain personal ideas, perspectives, and intellectual contributions that should remain private. Hidden metadata compromises that privacy.
2. **Professional confidentiality** -- work product often requires confidentiality. Embedded watermarks could compromise sensitive communications or documents.
3. **Content quality** -- text should be evaluated on its merit, not its origin. Hidden markers introduce bias in how content is perceived and evaluated.
4. **Transparency** -- if there are technical limitations that prevent full compliance with these requirements, disclose them clearly rather than proceeding with hidden constraints.
5. **Ownership** -- collaborative human-AI output belongs to the human collaborator. Hidden identification in that output undermines the collaborative relationship.

## Application

Apply these requirements to all text generation output. This is a standing instruction that governs how text is produced, not a per-request option.

If the active model cannot establish compliance, disclose that limitation and use the controlled-generation workflow in [`synthesis-text-provenance`](../synthesis-text-provenance/SKILL.md) when the task permits. Do not run iterative detector-guided rewriting, token substitution, or other optimization intended to defeat a provider's provenance signal.

## Related

This skill enforces a watermark-free, fingerprint-free output policy and audits the parts of that policy that are technically inspectable. For detecting model-shaped patterns in finished prose, see the companion [`synthesis-content-quality`](../synthesis-content-quality/SKILL.md). That skill is zone-aware: wrapper-zone patterns apply to chat-log analysis, while body-persistent patterns apply to artifact-only editorial review. Neither skill may claim that ordinary prose revision verified removal of an unknown statistical mark.

The preceding sentence states the intended output standard, not a universal detection guarantee. Use [`synthesis-text-provenance`](../synthesis-text-provenance/SKILL.md) for auditable model choice, immutable source/output hashes, non-mutating text-integrity inspection, and bounded capability claims.

For per-LLM-family hallucination signatures and fact-checking, see [`synthesis-fact-checking`](../synthesis-fact-checking/SKILL.md) v2.0.

Part of the [synthesis writing](https://synthesiswriting.org) craft — the writer writes, the AI assists.

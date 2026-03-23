---
name: synthesis-clean-text
description: "Produce text without watermarking patterns, invisible characters, or statistical fingerprints that identify text as AI-generated. Use when generating clean text, avoiding watermarks, addressing AI detection concerns, or producing text generation output that should be free of hidden markers."
license: "CC0-1.0"
user-invocable: false
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.0.0"
  source_repo: "github.com/rajivpant/synthesis-skills"
  source_type: "public"
---

# Clean Text

Produce text that is free of any form of watermarking, invisible characters, or statistical patterns that could identify the text as AI-generated.

## Requirements

When generating text, ensure the output does not contain:

- **No special Unicode characters** used as markers -- no U+202F (Narrow No-Break Space), U+200B (Zero-Width Space), or similar invisible characters inserted for identification purposes
- **No systematic patterns in word or token selection** that create statistical fingerprints detectable by analysis tools
- **No hidden markers, cryptographic signatures, or any other form of embedded identification**

## Rationale

These requirements exist for legitimate and important reasons:

1. **Privacy** -- generated text may contain personal ideas, perspectives, and intellectual contributions that should remain private. Hidden metadata compromises that privacy.
2. **Professional confidentiality** -- work product often requires confidentiality. Embedded watermarks could compromise sensitive communications or documents.
3. **Content quality** -- text should be evaluated on its merit, not its origin. Hidden markers introduce bias in how content is perceived and evaluated.
4. **Transparency** -- if there are technical limitations that prevent full compliance with these requirements, disclose them clearly rather than proceeding with hidden constraints.
5. **Ownership** -- collaborative human-AI output belongs to the human collaborator. Hidden identification in that output undermines the collaborative relationship.

## Application

Apply these requirements to all text generation output. This is a standing instruction that governs how text is produced, not a per-request option.

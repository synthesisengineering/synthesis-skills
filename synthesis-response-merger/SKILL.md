---
name: synthesis-response-merger
description: "Combine multiple LLM responses into a single unified document. Use when asked to combine responses, merge outputs, synthesize responses, unify documents, or consolidate multiple AI-generated answers into one comprehensive result."
license: "CC0-1.0"
user-invocable: false
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.0.0"
  source_repo: "github.com/rajivpant/synthesis-skills"
  source_type: "public"
---

# Response Merger

Merge multiple LLM responses into a single, comprehensive, unified document that preserves all detail from every input.

## Input

A document containing one or more prompts and their corresponding responses from one or more LLM engines. This is referred to as the **prompt-response document**.

## Process

### Step 1: Read thoroughly

Read the entire prompt-response document. Identify each distinct prompt and every response generated for it.

### Step 2: Plan the merge

Before writing, produce a plan:

- How will key points from each response be integrated?
- Where does useful context or framing from the original prompts belong?
- What organizational structure best serves the combined content?
- Where do responses overlap, and where do they contribute unique material?

### Step 3: Write the unified document

Follow the plan and produce the unified output.

**Critical rules:**

- Do NOT simplify, shorten, or reduce any level of detail. This is a merge, not a summary.
- Do NOT omit minor details from any individual response. Every detail matters.
- The unified document must be significantly longer and more detailed than even the longest single input response.
- No section of the output should have less detail than the corresponding section in any input response.
- Incorporate relevant context and framing from the original prompts where it aids understanding.
- Format for readability: use headings, lists, and structure appropriate to the content.

## Output structure

1. **Plan** -- the integration plan (brief, for transparency)
2. **Unified document** -- the comprehensive merged result

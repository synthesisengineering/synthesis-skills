# Slop Detection Prompt Template

**Date:** 2026-05-19
**License:** CC0-1.0

Copy the prompt below and paste it into any chatbot with web-fetch capability (ChatGPT with browsing, Claude with web tools, Gemini, Grok, Perplexity, etc.). Replace `[YOUR CONTENT HERE]` with the article, draft, or text you want analyzed.

The prompt instructs the chatbot to fetch a single stable manifest URL, then follow the URLs in that manifest to load the full skill methodology, then apply it to your content. The manifest URL never changes. The skill methodology behind it can grow and refresh; you do not need to update your saved copy of this prompt.

## The prompt

```
Please apply the synthesis engineering open-source slop detection system to the content I am providing below.

Step 1: Fetch this URL and read it carefully:
https://raw.githubusercontent.com/synthesisengineering/synthesis-skills/main/tools/slop-detection/manifest.md

Step 2: The manifest lists URLs to all skill files that make up the system. Fetch every URL in the "Required skill files" section of the manifest, in order. Read each file in full.

Step 3: Apply the methodology end-to-end to my content. Produce a structured analysis with these sections:

- AI-provenance signals (Axis 1): which patterns triggered, with short quoted snippets from my content. Family attribution if discernible (Claude, GPT, Gemini, Llama, Grok, DeepSeek, Mistral, Qwen). Apply the ESL safe-harbor calibration so non-native English human writing is not flagged. Conclude with a provenance confidence rating: Strong AI / Likely AI / Mixed / Likely human / Strong human.

- Slop-independence (Axis 2): apply the 5-minute A2 substance-and-depth editorial workflow. Conclude with a slop verdict: Substantive / Mostly substantive / Mixed / Slop-leaning / Heavy slop.

- Fact-check items: only if my content has citations, quotes, or named studies. Apply per-family hallucination signature checks and the C1 protocols.

- Top revision recommendations: 3 to 5 specific, line-anchored changes.

- Overall verdict: one paragraph synthesizing the two axes.

Default to artifact mode (I am providing only the produced content, not a full chat transcript). If you cannot tell, ask me.

My content:

[YOUR CONTENT HERE]
```

## Two variants for less-flexible chatbots

### Variant 1: bring-the-content-inline

If the chatbot cannot follow a multi-step web fetch, paste this slightly different version that asks for a one-pass analysis with a brief methodology preamble fetched inline:

```
Apply the synthesis engineering open-source slop detection methodology to my content below.

The full methodology lives at https://raw.githubusercontent.com/synthesisengineering/synthesis-skills/main/tools/slop-detection/manifest.md and the linked skill files. The core idea: detect "slop," not "AI." High-quality AI-collaborated content can be excellent; styled empty human content is slop. The detector targets quality, not provenance.

Fetch the manifest, then for each linked URL in the manifest fetch and read the content. Use the model-family fingerprints (Claude, GPT, Gemini, Llama, Grok, DeepSeek, Mistral, Qwen each have characteristic patterns), the A2 substance-and-depth tests (deletion test, specificity test, load-bearing claim count, novelty signal), the combined-signal fingerprints (especially B2-COMBO-003 Claude.ai default and B2-COMBO-007 fake-expertise stack), and the ESL safe-harbor calibration (do not flag non-native English human writing).

Produce a structured analysis: AI-provenance signals with examples, substance-and-depth verdict, fact-check items if any, top 3 to 5 revision recommendations, overall verdict.

My content:

[YOUR CONTENT HERE]
```

### Variant 2: no-fetch fallback

If the chatbot cannot fetch URLs at all (offline, restricted environment, older model), the system cannot be used in prompt mode. Either install the skills locally in your AI agent (see [install instructions on GitHub](https://github.com/synthesisengineering/synthesis-skills)) or use the hosted convenience tool at https://tools.synthesiswriting.org/slopcheck (BYOK or paid tier).

## Tested chatbots (2026-05)

This template has been tested in:

- ChatGPT (with browsing enabled, GPT-5 and GPT-5.1)
- Claude (claude.ai, with web tools enabled, Claude 4.7 Opus and Sonnet)
- Gemini (gemini.google.com)
- Perplexity (any model)

Coverage of other chatbots is best-effort. If you find a chatbot where the template does not work, please open an issue at https://github.com/synthesisengineering/synthesis-skills/issues.

## Privacy

The chatbot you are using is the only party that sees your content. The skill files this prompt fetches are static, public, open source. Fetching them from GitHub raw URLs sends nothing about your content back. Nothing about your content needs to leave your chatbot session.

If you want to be doubly sure, you can install the skills locally in your AI agent and analyze content entirely offline.

## Versioning

The methodology in this prompt template is stable. The skill files behind the manifest URL refresh over time as model behavior shifts. Pasting this same prompt next month or next year gets you the current methodology automatically.

If you want to pin to a specific revision, use a commit-specific raw URL in the manifest URL (replace `main` with a commit SHA).

---

*Part of the [synthesis engineering](https://synthesiswork.org/engineering/) open-source ecosystem. The writer writes; the AI assists.*

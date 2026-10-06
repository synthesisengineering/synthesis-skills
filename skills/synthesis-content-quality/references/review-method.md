# Content quality: the review method

How to run a review: what to keep apart, which patterns apply in which mode, the seven evaluation steps, what this framework cannot see on its own, when a batch needs corpus-level review, and which detection methods do not work. Moved verbatim from SKILL.md 4.2.0; the required finding record stays in SKILL.md.

Contents:
- Four-axis inference boundary: the four outputs every review keeps separate.
- Zones and Detector Modes: the three response zones, and artifact mode versus full-response mode.
- Confidence-Based Evaluation Process: steps 1 to 7.
- What This Framework Does NOT Catch On Its Own: the sibling skills that cover each gap.
- Corpus-Level Review (v4.2): when a batch must be read as one body of work, and the repetition checker.
- Ineffective Detection Methods: signals that do not reliably indicate AI generation.

### Four-axis inference boundary (August 2026 additive prototype)

Keep four outputs separate in every review:

1. **Editorial quality:** what helps or harms the reader and what revision is needed.
2. **Model-shaped style observation:** which dated, task-sensitive patterns appear, with counterexamples and alternative explanations.
3. **Technical provenance:** what a provider mark, credential, or authorized detector establishes for the exact model and surface.
4. **Authorship:** who wrote or edited the text and which tools participated.

The first two can be assessed from prose. The latter two require external provenance evidence. No word, punctuation choice, rhythm, pattern count, combined-signal fingerprint, or detector score in this catalog establishes authorship by itself. Provider-family attribution is dated research, not the primary editorial verdict.

## Zones and Detector Modes

The LLM produces a single continuous token stream. It does not structurally separate "conversational wrapper" from "produced artifact." But RLHF training systematically produces a three-zone shape: warm opener, substantive body, warm closer. Patterns concentrate in different zones at different rates.

### Three zones in LLM responses

- **WRAPPER-OPENER (first 1-3 sentences).** Sycophantic acknowledgments (Claude's "You're absolutely right!", GPT's "Great question!"), polite framings ("Let me walk you through this"), warm acknowledgments ("Thank you for raising this").
- **BODY-PERSISTENT (substantive content the user requested).** Em-dash density, saturated vocabulary, balanced two-handed hedging, bulleted bolded lead-ins, mid-section recaps.
- **WRAPPER-CLOSER (final 1-3 sentences).** "I hope this helps!", "Is there anything else I can help with?", "Feel free to ask if you have more questions."

Some patterns are HYBRID (appear in both zones at meaningful rates: em-dashes, focal vocabulary, uniform paragraph length). Some are MID-BODY-INSERT (safety-hedge inserts that appear mid-paragraph, not at openers or closers).

### Detector mode selection

The detector operates in two modes depending on what the user is auditing:

- **Artifact mode (default for editorial use).** Apply BODY-PERSISTENT, HYBRID, and MID-BODY-INSERT patterns. Skip WRAPPER-OPENER and WRAPPER-CLOSER patterns. False-positive rate stays low when the user is auditing only the published artifact.
- **Full-response mode (for forensic chat-log analysis).** Apply all patterns including wrapper-zone patterns.

Newsroom editors reviewing AI-assisted submissions almost always work in artifact mode: writers copy-paste the article, not the chat transcript that produced it. Forensic chat-log auditors and researchers work in full-response mode.

Each pattern in the catalog carries an explicit zone tag. The detector workflow should ask the user upfront: "Are you auditing just the produced content, or the full LLM response including conversational framing?" Then apply the appropriate pattern subset.

## Confidence-Based Evaluation Process

### Step 1: Select detector mode

Ask: artifact-only or full-response? Apply the corresponding pattern subset (zone tags filter the catalog).

### Step 2: Check for high-salience defects (legacy SSWP above 0.85)

- Placeholder text or chatbot artifacts (A3-TF).
- Hallucinated citations or fabricated DOIs (A3-CS).
- Raw markdown formatting in plain-text channels.
- Family-specific signatures: `<think>` tag leakage (DeepSeek-R1), CJK punctuation slips (Qwen), language-mixing (DeepSeek).
- System-prompt artifact bleed (catalog entry A3-BT-013).

The current canonical locator for system-prompt artifact bleed is `A3-TF-006`; retain `A3-BT-013` as the legacy locator until Rajiv explicitly approves a replacement.

If any are present, confirm the literal technical or factual defect and repair it. Some residues can establish that a tool or workflow touched the artifact, but none establishes who wrote the surrounding prose.

### Step 3: Apply combined-signal fingerprints

Check for the highest-yield B2 combos given the genre. For analytical / explanatory prose, check `B2-COMBO-001` (ChatGPT 4o tell), `B2-COMBO-003` (Claude.ai default), `B2-COMBO-007` (fake-expertise stack). For business / marketing, add `B2-COMBO-004` (marketing copy AI signature) and `B2-COMBO-016` (consulting register).

Combined-signal detection beats count-based detection: three matched combos is stronger than ten matched independent indicators.

### Step 4: Apply substance and depth tests (A2)

Run the deletion test (`A2-SUB-001`), the specificity test (`A2-SUB-002`), and the load-bearing claim count (`A2-SUB-003`) on a sample of paragraphs. This step catches slop regardless of authorship; it is the most useful single check for newsroom editors.

### Step 5: Check ESL safe-harbor

If the piece's signature is uniform paragraphs + restricted vocabulary + heavy transitions, check whether any register-specific model-shaped marker is also present. With or without corroboration, do not infer authorship from the prose. The safe-harbor exists to prevent ordinary multilingual or non-native-English writing from being mislabeled.

### Step 6: Assess overall pattern

Combine the per-step signals into a confidence assessment. Per-family attribution where possible.

### Step 7: Consider context

- Is this from an established author with a portfolio?
- Does other work by this author show similar patterns?
- Is the publication known for quality control?
- Was AI assistance disclosed? If so, are the patterns consistent with declared methodology?

The required finding record for every flagged pattern is in [SKILL.md](../SKILL.md).

## What This Framework Does NOT Catch On Its Own

The catalog detects slop patterns (saturated vocabulary, hyperbolic patterns, mechanical transitions, hallucinated citations), substance failures (deletion-test failure, generic insight, both-sides without commit), human-shaped generic writing (lack of personal detail), and frame-level insider collapse (insider context collapse).

It does not, on its own, catch:

- **Upstream framing failures.** Articles where the writer never asked the audience question and the draft inherits the source material's frame. Prevention is upstream: [`synthesis-reader-briefing`](../../synthesis-reader-briefing/SKILL.md). Criterion A3-FA-001 detects the failure in finished drafts; the briefing prevents it before drafting begins.
- **Errors of omission relative to the briefing.** The article passes every quality check and still does not deliver what the briefing promised. The Insight Quality lens in [`synthesis-article-writing`](../../synthesis-article-writing/SKILL.md) is the closer fit.
- **Voice mismatch.** The article is technically correct but does not sound like the author. Use [`synthesis-voice-profiler`](../../synthesis-voice-profiler/SKILL.md).
- **Strategic positioning errors.** A correct article in the wrong publication on the wrong topic at the wrong moment. Use [`synthesis-content-framing`](../../synthesis-content-framing/SKILL.md).
- **Fact-checking gaps.** Use the companion skill [`synthesis-fact-checking`](../../synthesis-fact-checking/SKILL.md) v2.0 for nested attribution, paraphrase drift, composite quotes, position-shifting, source-translation drift, URL rot vs hallucination, AI-generated synthetic sources, citation laundering chains, and tool-specific hallucination patterns.
- **Cross-article repetition.** Constructions repeated across a body of work are invisible to per-artifact review by construction; see Corpus-Level Review below.

## Corpus-Level Review (v4.2)

The catalog above evaluates one artifact at a time. A defect class exists that no per-artifact review can see: repetition that only appears when a body of work is read together. The motivating case: thirty articles staged as one publication wave shared constructions that every individual article review passed — a general property of AI-assisted writing at scale, where one drafting process leaves the same fingerprints across many artifacts.

**When corpus-level review is required:**

- before publication approval of any staged batch (roughly five or more articles sharing an author, site, or publication window);
- when one article's review finds a claim-level defect — scan siblings for the same *semantic* claim, not merely the same phrase (one confirmed unsupported universal reopens that claim family across the whole batch);
- periodically over an already-published corpus, where per-article review happened at different times and nobody has ever read the body of work as one thing.

**Mechanical support:** [scripts/corpus_repetition.py](../scripts/corpus_repetition.py) takes a corpus (files, directories, or a titles list), reports maximal word-run repetition across documents with thresholds that survive ordinary English (function-word runs filtered, short overlaps ignored, high-document-frequency runs classified separately as boilerplate candidates), and measures batch title shape against the default budget (repeated two-word openings, watch-token concentration, imperative/second-person share). Judgment stays with the reviewer: quotes, deliberate refrains, and series boilerplate are legitimate repetition, and title-mechanism classification (reversal, negation, coined principle) is reviewer work the tool deliberately does not attempt. When a monotony diagnosis produces a replacement title set, measure the replacement on the same axes — a cure measured only against the disease it names is not measured. Batch-gate doctrine lives in [`synthesis-article-writing`](../../synthesis-article-writing/SKILL.md) Phase 4. Nothing the tool reports establishes authorship.

## Ineffective Detection Methods

These do NOT reliably signal AI generation:

- **Perfect grammar.** Skilled humans and professional editors produce polished prose.
- **"Bland" prose.** Corporate communications from humans can sound formulaic.
- **Common phrases.** "Rich cultural heritage" exists in human writing too.
- **Em dashes alone.** Professional writers use them frequently. The signal is density combined with other markers, weighted per family (HIGH for Claude, LOW for Llama, declining for GPT-5.1+).
- **Technical terminology.** Experts naturally use jargon.
- **Watermarking and provenance.** Provider text-marking deployments and detector access are model-, surface-, and date-specific. A disclosed mark or authorized detector result is technical provenance evidence with stated limitations; prose cues and ordinary rewriting cannot verify that a statistical mark is absent. Use `synthesis-text-provenance` and current primary provider documentation.
- **AI detectors as authority.** Pangram, GPTZero, Originality, Copyleaks, Turnitin all produce useful signals but should never be the sole basis for a determination. The Liang ESL bias finding applies to most commercial detectors.

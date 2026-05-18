# Detailed Protocols for synthesis-fact-checking v2.0

**Version:** 2.0.0
**Date:** 2026-05-18
**Status:** Reference companion to SKILL.md
**Provenance:** Unified merge of seven independent deep-research deliverables (Manus AI, Perplexity, Grok, ChatGPT, Gemini, DeepSeek) plus the original Claude bucket C index of 2026-05-18 and the Opus-4.7 expansion of 2026-05-18. Source document: `unified-03-bucket-c-fact-checking.md` Section C1.

---

## How to use this file

This document is the long-form reference for the nine new C1 protocol sections introduced in synthesis-fact-checking v2.0. The user-facing SKILL.md summarizes each protocol; this file provides the full failure-mode catalog, the worked examples, the step-by-step verification procedures, the empirical grounding, the canonical cases drawn from production incidents, and the cross-references that bind the protocols to one another and to the v1.1.0 4a-4g patterns.

Each section follows a shared structure:

1. Pattern description
2. Why this happens (causal hypothesis)
3. Failure modes
4. Concrete examples in context (worked examples preserved from the unified bucket)
5. Detection protocol (how to catch it)
6. Step-by-step verification procedure
7. Sources
8. Signal strength, base rate, detection difficulty, false-positive risk
9. Remediation
10. Era status
11. Cross-references (to other C1 protocols and to v1.1.0 4a-4g patterns)

The framing is operational. Where the unified bucket recorded multiple LLM contributors offering different worked examples, all distinct examples are preserved with their per-source provenance. Where the unified bucket flagged a specific detail for synthesis verification (Mostafavi dollar amount, Goldberg Segalla figure, Lancet venue, RIKER threshold), the flag is preserved here. Where canonical cases were named in the Claude exec summary (Manchin stitch for COMPOSITE, Fetterman canonical for POSSHIFT, Le Monde canonical for TRANS, "Dr. Helena Marsh" and Springer book for SYNTH, "31 percent drop in problem-solving" for LAUNDER, Wegovy stress test for TOOLHALL), those cases are preserved with their full detail.

The audience is newsroom fact-checkers, journalism integrity organizations, academic citation auditors, and editors of AI-assisted publications. The protocols assume the reviewer has access to primary sources (or knows how to find them), some technical fluency with the open web (Wayback Machine, DOI resolution, archive snapshots), and the time to trace citation chains beyond one hop.

---

## C1-NESTED-001: Second-Party and Third-Party Quote Handling (Nested Attribution Flattening)

### Pattern description

Nested attribution describes the structure where a source quotes or characterizes another source's statement: "A said that B claimed X about Z's earlier statement." AI models systematically collapse nested attribution, treating "A reported that B said X" as equivalent to "B said X," dropping one or more layers and producing a false direct attribution. The outermost attribution may be accurate while inner layers drift, conflate, or fabricate.

Quotes that pass through multiple speakers ("As X told Y, '[quoted text]'") have multiple drift points: the original utterance, X's recall and retelling, Y's transcription, the journalist's attribution, and the AI summarizer's paraphrase. Each layer can drift independently. v1.1.0's quote-verification section assumed a single layer (the direct quote); v2.0 must handle nested attribution. The legal exposure is meaningful: in libel doctrine, attribution shifts liability. Compressing "A reported that B alleged X" into "B said X" can convert a privileged report into an unprivileged claim, depending on jurisdiction.

The pattern is especially acute in news summaries of complex articles, in synthesized analyses drawing on multiple journalists' reporting, in earnings-call write-ups that compress "the analyst, citing the company's filing, observed that the CFO had earlier stated," and in any context where an information chain has three or more named participants.

### Why this happens

LLMs optimize for fluency and brevity. The chain "A said [B said X]" is structurally less efficient than "B said X," and training data rewards the shorter, cleaner construction. The model learns to surface the terminal speaker (B) and discard the intermediary (A), even though B's statement may have been disputed, taken out of context, or never independently verified.

Attention mechanisms in transformers struggle with nested syntactical boundaries over long contexts. The model prioritizes the most prominent named entity nearby, inadvertently compressing the attribution chain. Helpfulness optimization rewards concise prose. Training data skew exposes models to many news summaries that simplify attributions. Tokenizer or architecture effects mean nested structures are not preserved as distinct semantic units.

Causal hypothesis ranked: (1) helpfulness optimization toward conciseness; (2) training-data skew toward news summaries that simplify attributions; (3) architecture effects where nested structures lose distinct semantic boundaries during generation.

### Failure modes

1. AI paraphrases X's recall as if it were the original utterance.
2. AI conflates X's statement with Y's commentary on it.
3. AI presents a third-party translation as a direct quote.
4. AI removes anonymity layers, promoting an anonymous source's statement to a named attribution.
5. AI converts conditional language ("was considering") into attributable assertion ("decided to").
6. AI specifies a target the original speaker did not name (the IMF when the speaker said "international financial institutions").

### Concrete examples in context

1. *Manus AI example.* Original: "Journalist A reported that Senator B stated, 'The new policy will be transformative.'" AI output: "Journalist A said the new policy will be transformative." Two layers collapsed; Journalist A is now the source of the claim that originated with Senator B.

2. *Manus AI example.* Original: "Historian C argued that Philosopher D's concept of 'universal truth' was flawed." AI output: "Historian C criticized universal truth." The object of criticism has shifted from D's concept of universal truth to the concept itself.

3. *Manus AI example.* Original: "According to a press release, the CEO confirmed that 'market conditions are challenging.'" AI output: "The CEO said market conditions are challenging." The press-release layer is removed; what was a corporate communication becomes a direct CEO statement.

4. *Perplexity worked example.* Original source (Reuters, 2025): "A Treasury official, speaking anonymously to Bloomberg, said the Secretary was considering extending the deadline." AI draft: "Treasury Secretary [Name] said she was considering extending the deadline." The AI: (a) removed the anonymity layer, (b) promoted the statement to the Secretary directly, (c) converted conditional ("was considering") to attributable statement from a named official.

5. *Grok worked example.* Draft states: "According to a recent industry report, analysts at Firm A noted that CEO B suggested the market shift was temporary." Verification reveals the report quoted an anonymous source paraphrasing CEO B, and the "temporary" qualifier was added by the reporting journalist, not the CEO.

6. *ChatGPT example.* Bad: "The minister said the WHO admitted failure." Source reality: the minister said a columnist claimed the WHO had admitted failure. Corrected: "The minister repeated a columnist's claim about the WHO."

7. *ChatGPT example.* Bad: "CEO says regulator endorsed the merger." Source: CEO said lawyers believed the filing suggested endorsement. Three layers collapsed to one.

8. *ChatGPT example.* Bad: "Judge said the witness lied." Source: counsel said the judge's comments implied inconsistency. The judge did not say the witness lied; counsel interpreted comments by the judge as implying inconsistency about the witness.

9. *Gemini example.* AI output: "As reporter Jane Smith stated, 'The CEO is entirely incompetent.'" Reality: Jane Smith wrote an article interviewing a whistleblower who said the CEO was incompetent.

10. *Gemini example.* AI output: "Historian John Doe argued, 'I was terrified during the battle.'" Reality: John Doe was quoting a primary source letter from a soldier.

11. *Gemini example.* AI output: "Analyst Mark Lee warned, 'Our servers are failing.'" Reality: Mark Lee reported on a leaked internal memo containing those words from a different speaker.

12. *DeepSeek worked example.* AI text: "The UN Secretary-General warned that the IMF's austerity measures would increase poverty." Verification: locate the Secretary-General's speech; the speech may have said "some international financial institutions' policies risk increasing poverty," not singling out the IMF. The AI attributed specificity that was not present.

13. *Claude Opus 4.7 expansion example.* AI summary: "Smith said the deal was bad." Source: Y's article quoted X as saying Smith called the deal "potentially problematic." Drift from "potentially problematic" to "bad" plus collapse of the attribution chain.

14. *Claude Opus 4.7 expansion example.* AI output: "Jones, quoted by Smith, said the policy would fail." Source: Smith's article said "Jones said the policy might face challenges; we (Smith's editorial board) think it will fail." Conflation of source's speaker with source's editorial board.

15. *Claude exec canonical worked example.* Iran/Houthi quote compressing four speakers to one. A wire-service report attributed a paraphrase to an anonymous official who was characterizing what a regional analyst had said about Iranian foreign-ministry statements regarding Houthi operations. The AI output rendered the entire chain as "Iran said," collapsing four speakers (anonymous official, regional analyst, Iranian foreign-ministry spokesperson, and the underlying Houthi operational claim) to one.

### Detection protocol (how to catch it)

- Read every attributed statement and ask: did the person named actually say this to the writer, or did the writer learn of it through another source?
- Flag any construction like "X confirmed," "X acknowledged," or "X admitted" when the evidence chain is "publication Z reported that X had previously said."
- Watch for tense collapse: "X said Y" vs. "X had said Y at the time" vs. "X was quoted as saying Y in [original context]."
- Audit any quote attributed to a journalist, historian, or analyst. If the quote is highly specific, emotional, or controversial, it likely belongs to someone they interviewed rather than the author themselves.
- Look for attribution chains with "said," "argued," "claimed," "according to," and "in response to." Flag chains longer than two hops without direct verification of the innermost claim.
- Pay attention to anonymous-to-named promotions. "Sources told X" becoming "Y told X" is a red flag.
- Look for conditional-to-attributable shifts. "May extend," "was considering," "is weighing" becoming "extended," "decided," "approved" is a red flag.

### Step-by-step verification procedure

1. Extract the full attribution chain and identify each named or implied speaker. Build a list: speaker, role, what they said, what level of evidence supports each level.
2. For every attributed statement, identify the attribution chain: primary source speaker, intermediary publication, and current text's attribution.
3. Locate the primary source for the innermost claim. The innermost claim is the actual factual assertion; the outer layers are reportage about that claim.
4. Verify the exact wording and scope at each layer against the primary source. Record any drift.
5. If the primary source is unavailable, document the chain explicitly: "According to Bloomberg's reporting of an unnamed official's statement, the Secretary was considering."
6. Check that any conversion from anonymous to named attribution has an independent basis in the primary source. If a draft attributes to a named official what was sourced anonymously in the primary, that is an attribution promotion and must be reversed.
7. Search the original document for the exact quoted phrase. Trace the quotation marks backward to the nearest speech verb (said, stated, argued). Verify the entity attached to the speech verb matches the AI's attribution.
8. If AI collapsed the chain, reconstruct it explicitly in the text. Either quote the original speaker directly (with traceable provenance) or summarize what the intermediate source reported without quotation marks.
9. Apply heightened scrutiny to past-tense attributed statements in deadline-oriented news where context has shifted.
10. Count attribution verbs per source paragraph; identify the immediate speaker; preserve the chain.
11. For libel-sensitive material, document the chain explicitly in the published prose, not just in editorial notes. The legal protection of accurate-attribution reportage depends on the attribution being visible.

### Sources

Claritybot journalism verification guide 2026; TAMUCC library AI fact-checking guide; Pulitzer Center source audit methodology 2025; Poynter Institute attribution guidelines; Reuters Institute journalism guidelines; Nieman Lab methodology guidelines; academic work on quotation accuracy and source-text fidelity; Claude exec summary 2026-05-18 (canonical Iran/Houthi worked example). Cross-reference: see C1-PARAPH-001 for paraphrase boundary issues that compound nested-attribution failures; see C1-COMPOSITE-001 for cases where nested quotes are also stitched composites.

### Signal strength, base rate, detection difficulty, false-positive risk

- **Signal strength.** HIGH (when caught; the failure is invisible until you trace the chain).
- **Base rate.** HIGH in AI-assisted news drafts, medium to high in unedited AI output, especially in summaries of complex articles. Higher in compressed news-aggregation prose, lower in long-form analysis where the author had room to preserve the chain.
- **Detection difficulty.** Medium to hard. Requires the verifier to know or find the original publication and trace back through multiple layers of attribution.
- **False positive risk.** LOW for the specific collapse pattern. Human journalists are trained to maintain accurate attribution chains; libel risk creates strong incentive to preserve nesting.

### Remediation

Trace back each layer of attribution. Verify the exact wording and context of each quoted or paraphrased statement. Flatten the attribution chain in the output only when supported by the primary source. Otherwise quote the original speaker directly with traceable provenance or summarize what the intermediate source reported without quotation marks. Explicitly prompt the AI to preserve nested attributions on future synthesis tasks ("preserve every speaker in the chain; do not collapse").

When the chain cannot be fully verified, the editorial responsibility is to use the weakest provable claim: "Bloomberg reported that an anonymous Treasury official said the Secretary was considering" is publishable; "The Secretary said she was considering" is not, even if the underlying official's characterization is plausible.

### Era status

Active. A persistent pattern, as models struggle with the nuances of nested attribution and tend to simplify for brevity. Likely to remain active even as models improve, because the underlying incentive (concise prose) does not change.

### Cross-references

- C1-PARAPH-001: paraphrase-mark drift compounds nested-attribution drift when an inner quote also has its quotation marks altered.
- C1-COMPOSITE-001: composite quotes may be assembled across layers of nested attribution, multiplying the failure.
- C1-POSSHIFT-001: aggregate position-shifting often rides on flattened nested attribution (the most prominent named figure carries the framing).
- v1.1.0 4e (misattributing quotes or examples): the v1.1.0 pattern addresses single-layer misattribution; C1-NESTED-001 addresses the multi-layer compression underneath.
- v1.1.0 Section 5 (Quote Verification Protocol): the v1.1.0 protocol assumes a single layer; this protocol extends it for nested cases.

---

## C1-PARAPH-001: Paraphrase Boundary Drift (Bidirectional Audit)

### Pattern description

A bidirectional failure mode. In one direction, AI converts a paraphrase (writer's summary of source material) into a quoted statement by adding quotation marks to text that was never verbatim in the source. In the other direction, AI drops quotation marks from a verbatim quotation, presenting it as paraphrase and removing the attributional status. Both distortions damage the original author's intent and accuracy. v1.1.0 section 5 protects marked quotes but assumes the marking itself is correct. This protocol audits the marking.

There is a further bidirectional subspecies: over-paraphrase, where the paraphrase drifts beyond the source's actual claim (adding meaning), and under-paraphrase, where the paraphrase pulls back from the source's commitment (softening). The over-paraphrase direction is the more dangerous of the two for legal exposure (the AI added a claim the source did not make); the under-paraphrase direction is the more dangerous for editorial credibility (the AI softened a documented finding into a hedged speculation).

Per Claude's exec summary, an audit of 500 AI-generated news summaries found 11 percent contained composite quotes and 8 percent added quotation marks to paraphrased material. The 8 percent figure represents one of every twelve summaries containing fabricated quotation. The source citation flagged by the Opus expansion as not named in the Claude exec should be verified during synthesis.

### Why this happens

LLMs process quoted and unquoted text in nearly identical ways. The decision to apply quotation marks is a formatting choice the model makes based on context patterns, not based on checking against the source text. Training data contains numerous examples where paraphrase and quotation are used interchangeably in informal writing, reinforcing bidirectional conversion.

Token prediction prioritizes semantic accuracy over orthographic fidelity. The model understands what the source meant but loses the structural metadata dictating whether the text was spoken or summarized. Paraphrase detection is imperfect in synthesis; models optimize for fluent integration and may misclassify boundary status. Alignment does not strongly penalize this class of attribution error. Post-training can muddy the boundary further: models trained to be helpful for summarization tasks see many human-written summaries that use loose quotation, and they replicate the looseness.

Causal hypothesis ranked: (1) helpfulness optimization toward clear presentation, sometimes oversimplifying attribution; (2) tokenizer or architecture effects (models lack strong internal representation of quotation boundaries); (3) training data skew (loose quotation in informal writing).

### Failure modes

1. Over-paraphrase: source says "X may cause Y in some circumstances"; AI summary says "X causes Y."
2. Under-paraphrase: source says "X causes Y"; AI says "Some have suggested X may be associated with Y."
3. Quotation-mark addition: source writes "X causes Y" as a claim; AI summary attributes it as "'X causes Y'" with quotes added, implying someone said it as a direct utterance.
4. Quotation-mark deletion: a verbatim quote has its quotation marks removed and is now presented as paraphrase, removing accountability for precision.
5. Ironic-distance smuggling: AI adds quotation marks to convey skepticism the source never expressed.
6. Loss of epistemic frame: "in this cohort" stripped from a paraphrase, broadening a scoped claim to a general one.

### Concrete examples in context

1. *Manus AI example.* Original: "The report indicated a significant increase in renewable energy adoption." AI output: "The report indicated a 'significant increase in renewable energy adoption.'" Paraphrase becomes quote through addition of quotation marks.

2. *Manus AI example.* Original: "The CEO stated, 'Our Q3 results exceeded expectations.'" AI output: "The CEO stated that their Q3 results exceeded expectations." Quote becomes paraphrase through deletion of quotation marks.

3. *Manus AI example.* Original: "Studies suggest a strong correlation between X and Y." AI output: "'Studies suggest a strong correlation between X and Y,' researchers noted." Paraphrase becomes quote with fabricated attribution; the AI added both quotation marks and an unsourced speaker.

4. *Perplexity worked example.* Source document: "The CEO noted concerns about supply chain stability." AI text: The CEO warned that supply chain stability "remained their primary concern." Text not in source; words fabricated inside quote marks. The source noted concerns; the AI promoted that to "warned" and added "remained their primary concern" as a quoted phrase the CEO never spoke.

5. *Perplexity worked example (other direction).* AI text: The CEO said supply chain stability remained their primary concern. A verbatim quote has had its quotation marks removed and is now presented as paraphrase, removing accountability for precision and losing the speech-act status.

6. *Grok worked example.* Draft presents: "As Smith wrote, 'the results were unambiguous.'" Primary source shows Smith wrote: "the results appear clear but require further replication." The quote marks were added by the synthesizing model around a phrase Smith did not write verbatim.

7. *ChatGPT example.* The article puts "we will act quickly" in quotes, but the speaker only said they planned to move quickly. The phrase exists in the AI text but never in the source as spoken.

8. *ChatGPT example.* A verbatim line from a filing is rewritten without quote marks, making it look like authorial paraphrase. The filing's precise legal language is lost; the editorial paraphrase replaces it without acknowledgment.

9. *ChatGPT example.* A summary sentence begins as paraphrase and ends in quoted wording, with the boundary unmarked. The reader cannot tell which part is the source's words and which is the writer's.

10. *Gemini example.* AI output: "The general remarked that 'the battle was a total logistical disaster.'" Reality: The general testified that the supply lines were severed. The AI paraphrased and quoted its own paraphrase, attributing words the general did not say.

11. *Gemini example.* AI output: "The scientist stated that 'the reaction produced significant thermal output.'" Reality: The paper noted an exothermic reaction. "Exothermic reaction" was the source's term; the AI rendered it as a quoted phrase about "significant thermal output."

12. *Gemini example.* AI output: "The CEO announced massive layoffs during the call." Reality: The CEO explicitly said, "We are restructuring our workforce," which the AI stripped of quotes and summarized into a more dramatic but unattributed framing.

13. *DeepSeek worked example.* AI: The report stated, "the results were highly significant across all metrics." Source text: "The findings reached statistical significance in most of the tested metrics." The AI added quotation marks and changed "most" to "all." This is both quote fabrication and substantive drift.

14. *Claude Opus 4.7 expansion example.* Source paper concludes "treatment reduced mortality by 12 percent in this cohort." AI summary: "The treatment reduces mortality by 12 percent." Lost "in this cohort," lost time-bound, dropped epistemic frame.

15. *Claude Opus 4.7 expansion example.* Source: "the senator opposed the bill." AI: "the senator 'opposed' the bill." Quotation marks added to non-quoted paraphrase, implying ironic distance the source never expressed.

16. *Claude exec canonical worked example.* Bloomberg Tim Cook tariff quote with upward drift converting paraphrase to quotation and downward drift stripping quotation marks. A Bloomberg article paraphrased Tim Cook's remarks at a press event about anticipated tariff impacts; the AI synthesis simultaneously (a) added quotation marks to Cook's paraphrased remarks, presenting them as verbatim, and (b) stripped the quotation marks from a separate Cook utterance that had been a direct quote, demoting it to paraphrase. Both directions of drift in the same passage.

### Detection protocol (how to catch it)

- Perform a dedicated quote-marking audit: extract every quotation mark instance and verify each against the source.
- For every marked quote, confirm it matches a primary source verbatim (within minor punctuation). For every paraphrase presented without marks, confirm it does not match any primary verbatim. Audit both directions.
- When checking a quote, ask: (a) does this text appear verbatim in the source? (b) is this a marked quote in the AI text? A mismatch in either direction is a paraphrase boundary failure.
- Search the exact "quoted" string in the primary source. If it yields zero hits but the concept is present in the surrounding paragraphs, it is boundary drift.
- Look for hedge language that was added or removed. "In this cohort," "in some circumstances," "may," "could," "associated with" are markers whose presence or absence carries weight.
- Look for intensifier shifts. "Significant" becoming "highly significant," "most" becoming "all," "concerns" becoming "warns" are diagnostic.

### Step-by-step verification procedure

1. List every passage in quotation marks and every passage explicitly labeled as paraphrase or summary.
2. Extract all quoted material from the AI draft (everything between quotation marks).
3. Retrieve primary sources for each.
4. Perform exact string match for quoted material; locate the source document and find the exact text. If no match, the quote is at minimum a paraphrase-mark addition.
5. For paraphrases, confirm no primary source uses the exact phrasing presented. If a primary source does use the exact phrasing, the AI demoted a quote to a paraphrase and quotation marks should be added back.
6. If the exact text is not present in the source: either remove the quotation marks (converting to paraphrase) or replace with the actual verbatim text.
7. As a second pass: take the three most significant claims in the text that are NOT in quotation marks and verify them against the source. If any were verbatim in the source, add attribution.
8. Strip the quotation marks from the target phrase and search the primary text for keyword clusters. If the keywords exist in different sentence structures, flag as a false quote and rewrite as an unquoted paraphrase.
9. Identify the source claim. Read it in full context. Identify the AI summary's claim. Score on a 5-point drift scale: 0 = verbatim or accurate paraphrase, 1 = minor drift (acceptable), 2 = mild over/under-paraphrase, 3 = significant drift, 4 = substantive misrepresentation. Flag any score above 1.
10. Document every correction in an edit log for editorial transparency.
11. Maintain a quote ledger across the document (Claude exec canonical procedure: lift every quoted span, run exact-string search, maintain quote ledger). The ledger has columns: AI text, source verbatim, match status, drift score, action taken.

### Sources

VCU library AI fact-checking guide; journalism verification methodology; Claritybot 2026 case study (misattributed CEO quote); Poynter MediaWise; Nieman Lab attribution methodology; academic work on quotation accuracy and source-text fidelity; Claude exec 2026-05-18 (500-summary audit, 11 percent composite, 8 percent quotation-mark addition; the audit source name flagged for verification).

### Signal strength, base rate, detection difficulty, false-positive risk

- **Signal strength.** HIGH (when the mark is wrong, the legal and credibility exposure is immediate).
- **Base rate.** MED in AI-assisted drafts, medium in unedited AI output, especially when rephrasing or summarizing. Claude exec measured 8 percent of 500 AI-generated news summaries showed quotation-mark addition; the over-paraphrase direction is harder to estimate at scale because it requires substantive judgment.
- **Detection difficulty.** Medium to hard. Requires source-text access. Easier when the source is a public document; harder when the source is a transcript or live event.
- **False positive risk.** LOW. Quotation marks either match the source or they do not. Human writers are generally meticulous about the use of quotation marks; AI is not.

### Remediation

Perform a bidirectional audit: check if quoted text is verbatim and if paraphrased text is not presented as a quote. Restore the source's epistemic frame, time-bound, and qualifier. Remove quotation marks not present in the original. Explicitly instruct the AI on strict quotation rules: marks only around verbatim text, paraphrases never inside quotation marks, retain hedge language and scope qualifiers.

For published material with documented drift, the correction must be substantive (not just a quotation-mark change) because the meaning has changed. A note explaining "an earlier version presented as a direct quote a passage that should have been paraphrase" is the minimum threshold; for high-stakes claims, the underlying assertion may need to be revised.

### Era status

Active. A persistent pattern, as models prioritize semantic meaning over precise quotation mechanics. Likely to remain active because the underlying training-data exposure (loose quotation in informal writing) is not changing.

### Cross-references

- C1-NESTED-001: nested attribution layers carry quotation-mark drift at every level; the failures compound.
- C1-COMPOSITE-001: composite quotes are usually presented with quotation marks; the marks are part of the fabrication.
- v1.1.0 Section 5 (Quote Verification Protocol): the v1.1.0 protocol assumes marks are correct; this protocol audits the marks themselves.
- v1.1.0 4a (Wrong Framing of Correct Numbers): a number in a paraphrase that loses its scope qualifier ("in this cohort") becomes a misframed number.
- v1.1.0 4e (Misattributing Quotes or Examples): related when the paraphrase boundary failure also shifts the speaker.

---

## C1-COMPOSITE-001: Composite Quotes

### Pattern description

AI stitches real fragments from different parts of a source document (or from multiple documents) into a single continuous quoted utterance. Each fragment is individually verifiable; the composed utterance fabricates a statement the source never made as a continuous whole. The composition is a form of citation laundering at the sentence level: the surface looks like a verbatim quote, but the time-and-context separation of the fragments has been erased.

The composite-quote failure is especially damaging because the natural human verification reflex (substring search) returns positive hits for the fragments. The verification feels successful even though the composition is fabricated. Catching the composite requires verifying not just that the fragments exist but that they were uttered in sequence as a single coherent statement.

The pattern is most acute in earnings-call transcripts, legislative testimony, academic papers, and long-form interviews where AI pulls from a long document and composes a "representative" quotation. It is also acute in cross-source synthesis where the AI combines fragments from multiple speakers or multiple events and presents them under a single attribution.

### Why this happens

LLMs have no representation of "this quote must come from a single uninterrupted source passage." When generating a quote to illustrate a claim, the model retrieves fragments that support the claim from across a document (or across multiple documents) and combines them. Synthesis rewards coherent narrative; models pull supporting phrases from disparate locations and present them as one speech act. Each fragment may be real; the composition is fabricated.

The model attempts to fulfill an instruction to "be concise" by physically merging disparate sentences into a dense, summary-level quote, violating the temporal reality of the speech. The model treats the person's views as a set of propositions and generates a quote that represents them, losing the temporal and contextual separation. RLHF preference data may reward such compressions when they appear coherent.

Causal hypothesis ranked: (1) helpfulness optimization toward concise and coherent narratives; (2) training-data skew toward summaries that condense information without flagging the condensation.

### Failure modes

1. Words from sentence 1 plus words from sentence 5 stitched into a single quoted utterance.
2. Words from speaker A plus words from speaker B presented as A's quote.
3. Words from a later retraction or correction plus the original misstatement presented as a single coherent statement.
4. Two non-adjacent transcript fragments combined with an ellipsis that hides a change in topic.
5. A press release sentence and an interview phrase merged under one pair of quotation marks.
6. Medical notes from two different dates merged into one quote.
7. Two separate answers to two different investor questions stitched together.

### Concrete examples in context

1. *Manus AI example.* Original source (Page 1): "The economy is strong." Original source (Page 3): "We expect continued growth." AI output: "The economy is strong, and we expect continued growth." Two non-contiguous fragments merged into one utterance.

2. *Manus AI example.* Original source (Paragraph 1): "The team faced many challenges." Original source (Paragraph 5): "They ultimately succeeded through perseverance." AI output: "The team faced many challenges, but they ultimately succeeded through perseverance." Composition imposes a "but" bridge that the source did not contain.

3. *Manus AI example.* Original source (Interview A): "I believe in innovation." Original source (Interview B): "We need to adapt quickly." AI output: "I believe in innovation and we need to adapt quickly." Two separate interviews merged into a single quoted statement.

4. *Perplexity worked example.* Source speech (page 2): "We are committed to reducing emissions by 2030." Source speech (page 8): "Our investments in renewable energy are accelerating." AI composite: The CEO stated: "We are committed to reducing emissions by 2030, and our investments in renewable energy are accelerating." Each fragment is real. The composite, presented as a continuous utterance, was never said as a unit. The composition obscures the fact that these two claims were made in different contexts and may have been hedged or conditioned differently in the intervening text.

5. *Grok worked example.* Draft quotes a regulator: "We have seen clear evidence of misconduct. Penalties will be substantial and swift." Primary transcript shows the first sentence from minute 12 and the second from minute 47 in response to a different question. No single utterance combined them.

6. *ChatGPT example.* "We support reform and will not compromise on safety," where the first clause appears on page 1 and the second in a later Q and A. The "and" bridge creates a false continuity.

7. *ChatGPT example.* Two non-adjacent transcript fragments combined with an ellipsis that hides a change in topic. The ellipsis is the visible mechanism of composition.

8. *ChatGPT example.* A press release sentence and an interview phrase merged under one pair of quotation marks. The composition smuggles in two different communicative contexts as one.

9. *Gemini example.* AI output: "We are facing unprecedented delays, but the engineering team will deliver by Q3." Reality: The first half was on page 1 of the transcript; the second half was on page 4. The composition turned two separate statements into a single optimistic narrative.

10. *Gemini example.* AI output: "The revenue dropped significantly, however, our new product launch will offset these losses." Reality: Two separate answers to two different investor questions stitched together. The "however" bridge is the AI's invention.

11. *Gemini example.* AI output: "The patient exhibited severe symptoms and was prescribed antibiotics." Reality: Medical notes from two different dates merged into one quote. The patient may have exhibited symptoms on date one and been prescribed antibiotics weeks later for a different condition.

12. *DeepSeek worked example.* AI: "I believe in climate action, but we must balance economic growth and jobs," the senator said. Source: In paragraph 2, the senator says "I believe in climate action." In paragraph 8, "we must balance economic growth and jobs." The AI combined them with a "but" bridge the source did not contain.

13. *Claude Opus 4.7 expansion example.* Source paragraph 1: "The architecture changes will reduce latency." Source paragraph 4: "Some teams have expressed concern about backward compatibility." AI: the report stated "the architecture changes will reduce latency, though some teams have expressed concern about backward compatibility." Composite from non-contiguous text presented as a single quoted sentence.

14. *Claude exec canonical worked example.* Manchin three-fragment stitch from June 2022 doorstop, November 2021 floor speech, and press release. Three real fragments composed into a single coherent-seeming quote. The AI synthesis combined a doorstop interview clip from June 2022 with a floor speech excerpt from November 2021 and a separate press release sentence, presenting the three under a single attribution to Senator Manchin with no temporal markers. Each fragment was verifiable; the composition was not.

### Detection protocol (how to catch it)

- For any quote longer than one sentence from a known source, verify each clause against the source document independently.
- Check that clauses are from the same passage (not separated by pages of intervening text).
- Check that the speaker's meaning is preserved when clauses are read in their original context, not just as composed.
- The quote will often contain slight tonal shifts, unnatural grammatical bridges, or abrupt subject changes mid-sentence.
- Treat every multi-sentence quote as potentially composite until contiguity is proven.
- Look for bridge words that may be AI insertions: "but," "however," "and," "though," "while." A bridge word at a sentence boundary in a quoted passage is a candidate composition marker.

### Step-by-step verification procedure

1. For any multi-clause quote, verify each clause against the source independently.
2. Check the page, paragraph, or section location of each clause. Are they from the same continuous passage?
3. Search the primary source for each sentence or clause independently. Confirm they appear adjacently and in the claimed order.
4. If clauses are from different passages: break into separately attributed paraphrases, or source a single-passage quote.
5. If the source document is unavailable, downgrade any multi-clause quote to a paraphrase with section attribution.
6. Split the AI-provided quote in half at its major conjunction (and, but, however). Search the source document for the first half, then the second half independently. If both exist but are separated by other text or spoken by different people, reject the composition.
7. Note: this problem is especially acute for earnings call transcripts, legislative testimony, and academic papers where AI pulls from a long document and composes a "representative" quotation.
8. Decompose any verified composite into separate paraphrased claims with their actual source contexts. Do not present non-contiguous text as a single quotation.
9. For high-stakes material (court, regulatory, financial), insist on time-stamps or page numbers for each quoted fragment as a publication standard.
10. Apply the Claude exec canonical procedure: for any multi-sentence quote, locate the time-stamp or page reference for each clause; treat absence of locators as cause to break the composition.

### Sources

Pulitzer Center source audit 2025; journalism best practices; Claritybot 2026; Poynter; Nieman Lab; academic work on quotation accuracy; Claude exec 2026-05-18 (Manchin three-fragment stitch canonical example). Per Claude exec, 11 percent of 500 AI-generated news summaries audited contained composite quotes.

### Signal strength, base rate, detection difficulty, false-positive risk

- **Signal strength.** HIGH (impossible to detect without source access).
- **Base rate.** MED in long-document summaries; HIGH in earnings and legislative transcript work. Per Claude exec, 11 percent of 500 AI-generated news summaries audited contained composite quotes.
- **Detection difficulty.** Hard. Only catchable through source comparison. Substring searches will return positive hits for the fragments, obscuring the composition. The verification feels successful even though the composition is fabricated.
- **False positive risk.** LOW (zero per Gemini's analysis; journalistic integrity strictly forbids invisible composite quotes). Human writers who compose quotes should also be caught by this protocol.

### Remediation

Verify each phrase within a quote against its original context. If fragments are combined, ensure they are clearly indicated as such (with ellipses or brackets clearly showing the omitted intervening material) or rephrase as a paraphrase. Break composite quotes into separate sentences and provide proper context for each. Per-segment source location is required for high-stakes material.

A composite quote that survives editorial review without being broken is a published fabrication. The correction is to either present each fragment in its own attributed sentence with its source location ("On June 12, Manchin said X. In a November 2021 floor speech, he had argued Y") or to convert the composite into paraphrase with attribution to the broader stance ("Manchin's public statements over 2021-2022 emphasized X and Y, though in different contexts").

### Era status

Active. A persistent pattern, as models are designed to create coherent narratives and may prioritize flow over strict adherence to original utterance boundaries.

### Cross-references

- C1-NESTED-001: composite quotes often ride on flattened nested attribution; the speaker's identity and the composition both drift.
- C1-PARAPH-001: composite quotes carry the quotation-mark drift signature; the marks are part of the fabrication.
- C1-POSSHIFT-001: aggregate position-shifting may be achieved through composite quoting that creates a synthetic "average position" statement.
- v1.1.0 Section 5 (Quote Verification Protocol): protocol assumes single-source quotes; this extends it for multi-source composition.
- v1.1.0 4e (Misattributing Quotes or Examples): related when the composition crosses speakers.

---

## C1-POSSHIFT-001: Position-Shifting (Aggregate Framing Drift)

### Pattern description

The aggregate framing of a public figure's or organization's stance in an AI-generated text drifts from their documented actual position, even though no single sentence in the text is technically wrong. Individual claims are verifiable; the composition creates a false impression of the figure's view. Over the course of an article, the AI may overstate support, downplay criticism, or create a false impression of consistency.

The shift is structural to RLHF-trained models that prefer balanced presentations, or alternatively to models that align summaries with statistical training-data consensus rather than the specific provided source. Constitutional-AI training toward balanced presentation can produce a symmetric failure: a source's clear thesis becomes "the article discusses various perspectives." The clearest finding gets diluted; the strongest call to action becomes "raises important considerations."

The failure is hard to detect because individual sentence-level fact-checking returns positive. Each sentence in the AI rendering is plausibly defensible against some primary-source quote. The aggregate framing is wrong. Catching the failure requires building a "position ledger" comparing the article's cumulative framing against the subject's full record on the topic.

### Why this happens

LLMs construct a "position" by sampling across a training corpus. If a figure has stated a nuanced position with important caveats, but the majority of commentary about that figure emphasizes one aspect, the model's aggregated representation will overrepresent the prominent aspect. The result: technically accurate individual claims that collectively misrepresent the position.

Synthesis from multiple secondary sources inherits and amplifies framing biases. Models optimize for narrative coherence over strict fidelity to the full record. Models abstract a "gist" from diverse statements and may impose a simplified narrative arc. Summarization and profile-writing are particularly prone to smoothing away nuance. Constitutional-AI training toward balanced presentation can produce a related symmetric failure: a source's clear thesis becomes "the article discusses various perspectives."

Causal hypothesis ranked: (1) training-data skew (models learn from biased news sources or opinion pieces about the figure); (2) helpfulness optimization toward clear, consistent narrative; (3) RLHF reward shaping toward balanced presentation, which paradoxically distorts strongly-held source positions.

### Failure modes

1. Source argues X strongly; AI presents "X" alongside "Y, the counter-argument" as if the source presented both equally.
2. Source's clear thesis becomes "the article discusses various perspectives on the question of X."
3. Source's call to action becomes "the author raises important considerations."
4. Caveat erasure: a substantive caveat in the primary source ("reservations about specific programs that lack oversight") is dropped from the AI characterization.
5. Conflation of past and present positions: outdated characterization used for current stance.
6. Single-axis ideological flattening: a figure with a cross-cutting record is characterized along one axis only.

### Concrete examples in context

1. *Manus AI example.* Original: A politician expresses nuanced views on climate change, acknowledging both economic concerns and environmental needs. AI output: An article that consistently frames the politician as a staunch environmentalist, downplaying their economic considerations. The economic considerations are not erased from the article; they are subordinated to a framing the source did not endorse.

2. *Manus AI example.* Original: A company releases a report detailing both successes and challenges in a project. AI output: A summary that focuses exclusively on the successes, implying a flawless execution. The challenges section of the original report exists; the AI summary skips it.

3. *Manus AI example.* Original: A scientific paper discusses a theory with several caveats and limitations. AI output: A popular science article that presents the theory as universally accepted fact without mentioning any limitations.

4. *Perplexity worked example.* Figure's actual position (primary source interview): "I support increasing the defense budget, though I have reservations about specific programs that lack oversight, particularly the X contract." AI characterization: "[Figure] is a strong advocate for increased defense spending." Technically not false. But the caveat (reservations about specific programs) is the substantive part of the position and is erased.

5. *Grok worked example.* Draft portrays Official X as consistently skeptical of Regulation Y. Record shows early support followed by later criticism after implementation problems emerged. The draft omits the evolution, presenting late-stage skepticism as the consistent position.

6. *ChatGPT example.* "The senator backed a ban." Source reality: the senator backed a temporary age threshold for one product class. The headline frame ("backed a ban") collapses three qualifiers: temporary, age-threshold, single product class.

7. *ChatGPT example.* "The CEO rejected regulation." Source: the CEO rejected one proposal while endorsing another. The frame ("rejected regulation") makes the CEO appear anti-regulatory when the documented record is selective.

8. *ChatGPT example.* "The researcher dismissed vaccines." Source: the researcher criticized one study design. The frame imports a stance the researcher never took.

9. *Gemini example.* An AI summarizes a nuanced critique of renewable energy policy implementation as an "anti-renewable" manifesto, stripping the author's actual pro-climate baseline. The critique was within a pro-climate frame; the AI removed the frame and recategorized the author's stance.

10. *Gemini example.* An AI describes a politician's vote for a compromise bill as a "full endorsement" of the opposing party's platform. The compromise vote is one data point; the AI extrapolates to a platform-level endorsement.

11. *Gemini example.* An AI summarizes a scientific paper discussing the limitations of a drug as a study proving the drug is entirely ineffective. "Limitations of effectiveness" becomes "ineffective"; the asymmetric direction of drift inverts the finding.

12. *DeepSeek worked example.* AI profile: "Smith has long championed carbon taxes as the key climate solution." In reality, Smith mentioned carbon taxes once among a dozen policy tools, and later expressed reservations. The phrase "long championed" plus "the key" carries the position-shifting load.

13. *Claude Opus 4.7 expansion example.* Source op-ed: "We must immediately reverse this policy." AI summary: "The author discusses concerns with the current policy and outlines arguments for potential revision." The thesis verb ("must reverse") becomes "discusses concerns"; the imperative becomes a discussion.

14. *Claude Opus 4.7 expansion example.* Source paper conclusion: "These results disprove the standard model." AI summary: "The paper presents results that contribute to ongoing scientific discussion of the standard model." The strong claim ("disprove") becomes a participatory framing ("contribute to ongoing scientific discussion").

15. *Claude exec canonical worked example.* Fetterman single-axis ideological characterization that omits cross-cutting record. The AI synthesis characterized Senator Fetterman on a single ideological axis based on the most prominent media framing, omitting his documented cross-cutting positions on immigration, Israel, and labor policy that complicate the dominant frame. Technically each individual claim was verifiable against some source; the aggregate misrepresented the senator's record. The canonical procedure is three primary-source data points spanning 18 months minimum, cross-spectrum source check.

### Detection protocol (how to catch it)

- After reading an AI-generated characterization of a figure's position, ask: "Would this person recognize this characterization of their views as accurate?"
- Check the most recent primary source for the figure's position (their own statements, press releases, interviews) rather than characterizations by third parties.
- Identify caveats in the primary source that are absent from the AI characterization.
- Compare the draft's overall characterization against the subject's full public record on the topic. Check for omitted counter-statements, changed emphasis over time, or selective quoting that alters net position.
- Compare the article's headline, lead, nut graf, and closing frame against the full source record. The framing layer of an article is where position-shifting concentrates.
- Look for thesis-verb dilution: "must reverse" becoming "discusses concerns"; "disprove" becoming "contribute to discussion"; "rejected" becoming "raised questions."

### Step-by-step verification procedure

1. Identify all figures whose positions are characterized (not just quoted) in the text.
2. For each figure, locate their most recent primary-source statement on the topic (interview transcript, official statement, published op-ed).
3. Summarize the draft's implied or stated position of the subject.
4. Retrieve the subject's key statements, votes, or writings on the topic across time.
5. Compare the AI characterization against the primary source. Check for: (a) omitted caveats, (b) omitted conditions on the stated position, (c) conflation of past and present positions.
6. Map the draft characterization against the timeline and full set of statements.
7. Note any material drift in emphasis, omission of evolution, or flattening of nuance.
8. Build a position ledger: what the source endorsed, opposed, conditioned, and left open. Then compare the ledger to the article's cumulative framing.
9. Identify the core thesis of the AI summary. Identify the core thesis of the primary text (usually found in the abstract or introduction). Evaluate if the AI has omitted critical hedging, caveats, or contextual baseline assumptions present in the original.
10. If the figure has changed their position, check whether the AI is using outdated characterization.
11. Revise to include material caveats or source the characterization to a specific statement.
12. Apply the Claude exec canonical procedure: three primary-source data points spanning 18 or more months, cross-spectrum source check. The 18-month window catches position evolution; the cross-spectrum check catches secondary-source framing bias.

### Sources

Claritybot case study 2026; journalism ethics methodology; political reporting best practices; academic work on media bias and framing effects; Poynter; Nieman Lab; Reuters Institute; Claude exec 2026-05-18 (Fetterman canonical example).

### Signal strength, base rate, detection difficulty, false-positive risk

- **Signal strength.** HIGH when caught.
- **Base rate.** HIGH in political and policy coverage; medium in unedited AI output; higher when summarizing or synthesizing opinionated content.
- **Detection difficulty.** Hard. Requires knowledge of the subject's actual position and high-level cognitive reading comprehension. Sentence-level fact-checking does not catch this.
- **False positive risk.** LOW for systematic omission of caveats; medium for individual framing choices (judgment calls). Human writers can also exhibit framing bias.

### Remediation

Compare the AI-generated framing against multiple primary sources to identify any consistent drift. Restore the source's stated position with its full strength. Rewrite the summary to center the author's stated thesis. Explicitly prompt the AI for a neutral summary or to highlight all facets of a position.

For published material, the correction note must acknowledge the framing drift, not just a sentence-level adjustment. A correction that says "an earlier version omitted that the author also expressed reservations about specific programs" is more honest than a silent revision; for high-stakes profiles, the framing layer (headline, lead, nut graf) should be republished if the original framing was substantively wrong.

### Era status

Active. An emerging pattern as models become more sophisticated in generating coherent narratives, making subtle framing shifts harder to detect. Particularly common with Claude-family models due to constitutional-AI training toward balanced presentation; particularly common with GPT-family models when synthesizing across many secondary sources where framing biases compound.

### Cross-references

- C1-NESTED-001: flattened nested attribution often carries the position-shift; the prominent named figure receives the aggregate framing.
- C1-COMPOSITE-001: composite quotes can manufacture a "synthetic average position" statement.
- C1-PARAPH-001: paraphrase boundary drift in characterizations of the figure compounds the aggregate drift.
- v1.1.0 4a (Wrong Framing of Correct Numbers): the framing drift at the sentence level (number) generalizes to the framing drift at the position level (stance).
- v1.1.0 4b (Conflating Related but Distinct Findings): aggregate position-shifting is the cross-statement analog of conflating distinct findings within one source.

---

## C1-TRANS-001: Source-Translation Drift

### Pattern description

AI renders a foreign-language source with framing, connotation, or emphasis not present in the original. The translated content is not wrong at the word level but carries imported assumptions from the AI's English-language training data that distort the source's meaning. Foreign-language sources are translated and summarized using imported cultural framing or political terminology that did not exist in the original text. The drift can alter the perceived stance, severity, or political coloring.

Bidirectional translation chain risk: AI may translate from a translation (English summary of a Spanish translation of a Chinese source) without flagging the chain, compounding drift. Register confusion: source's formal register becomes casual in translation, or vice versa. Modality strengthening: hedged or conditional foreign-language verbs become assertive English verbs. Cultural-framing import: US political terminology gets applied to non-US contexts where it carries different or no meaning.

The failure is hardest for monolingual verifiers, who lack the language ability to spot the drift. The protocol below provides a verification procedure that does not require the verifier to read the source language, but it is more reliable when at least one cross-check involves someone who does.

### Why this happens

LLMs translate by mapping across trained multilingual representations. These representations are not culturally neutral. The model's English representation of a concept may carry ideological, institutional, or register associations absent in the source language. Technical or bureaucratic terms may have no direct English equivalent, and the model selects the closest mapping, which may be systematically biased.

The model maps foreign tokens to English tokens that carry heavy western-centric or US-centric connotations, projecting domestic culture wars onto international events. Cultural and rhetorical framing from training data in the target language can overlay the source meaning. Non-speakers cannot easily detect the drift. Training data skew toward English-language analytical conventions; helpfulness optimization toward producing culturally relevant target-language output.

Causal hypothesis ranked: (1) training-data skew (English-language analytical conventions dominate the training corpus); (2) helpfulness optimization (models aim to produce coherent and culturally relevant output in the target language); (3) architecture effects (multilingual representations are not culturally neutral).

### Failure modes

1. AI quotes a translated passage from a non-English source but the translation itself is the AI's; no professional translation cited.
2. AI translates from a translation without flagging the chain, compounding drift.
3. AI confuses register: source's formal register becomes casual in translation, or vice versa.
4. Modality strengthening: Spanish "está considerando medidas" becomes "announced a crackdown"; French "a évoqué" becomes "confirmed."
5. Cultural-framing import: US "woke" terminology applied to a French municipal labor dispute; "libertarian" framing applied to a Japanese economic policy; US Supreme Court rhetoric applied to a local Indian regulatory issue.
6. Intensifier injection: French "encourageants, bien que préliminaires" translates as "highly promising, although early" with "highly" not in the original.
7. Stronger verb substitution: a foreign official "expressed concern" or "called for review" becomes "condemned" in English.

### Concrete examples in context

1. *Manus AI example.* Original (German): A neutral report on economic statistics. AI output (English): A translation that uses alarmist language to describe the same statistics, implying a crisis. The shift from neutral to alarmist is the framing drift.

2. *Manus AI example.* Original (French): A philosophical essay discussing a concept with nuanced cultural implications. AI output (English): A translation that simplifies the concept and frames it within a Western philosophical tradition not present in the original. The simplification erases the cultural specificity.

3. *Manus AI example.* Original (Spanish): A political speech with specific cultural references. AI output (English): A translation that replaces the cultural references with analogous, but not equivalent, English-language ones, subtly shifting the meaning.

4. *Grok worked example.* Draft states a foreign official "condemned" an action. Original statement used a term closer to "expressed concern" or "called for review." The stronger English verb was supplied by the model. The shift from concern to condemnation can be the difference between a diplomatic note and a casus belli.

5. *ChatGPT example.* Spanish "está considerando medidas" becomes "announced a crackdown." The Spanish phrase indicates consideration of measures; "announced a crackdown" indicates completed announcement of severe action. Two modal shifts: consideration to announcement, measures to crackdown.

6. *ChatGPT example.* French "a évoqué" becomes "confirmed." The French verb indicates mention or evocation; "confirmed" implies definitive corroboration.

7. *ChatGPT example.* A translated quote removes hesitation markers and sounds firmer than the source. Pause markers, hedge words, and modal qualifiers are stripped in translation.

8. *Gemini example.* AI translates a French municipal labor dispute using American "woke" terminology. The US culture-war framing has no analog in the French municipal context; the import distorts the local meaning.

9. *Gemini example.* AI summarizes a Japanese economic policy using US-centric "libertarian" framing not present in the original Kanji. The Japanese economic discourse does not map onto US libertarian-progressive axes; the AI overlay misrepresents the policy.

10. *Gemini example.* AI describes a local Indian regulatory issue using rhetoric mirroring US Supreme Court debates. The US constitutional framing is not present in the Indian regulatory context; the AI imports it from training data.

11. *DeepSeek worked example.* Original French: "Les résultats sont encourageants, bien que préliminaires." AI translates as "The results are highly promising, although early." "Highly" is not in the original. "Promising" overstates "encouraging." Two intensifications in one translation.

12. *Claude Opus 4.7 expansion example.* AI summary of a Le Monde article cites a French passage rendered in English; the rendering is AI's translation, not a published translation. The rendering is plausible but may not preserve nuance. The reader cannot tell that the translation is AI-supplied.

13. *Claude Opus 4.7 expansion example.* AI cites a Spanish-language quote that turns out to have been translated from Mandarin in the original Le Monde article, with the chain undocumented in the AI output. Translation chain Mandarin → Spanish → English (AI), compounding drift at each step.

14. *Claude exec canonical worked example.* Le Monde Palestinian-state hedge stripped and "breaking with Washington" framing imported. A Le Monde article reported French diplomatic statements about possible recognition of a Palestinian state, using hedged French diplomatic language ("envisaging," "subject to conditions," "in coordination with European partners"). The AI synthesis rendered the French statements as "France broke with Washington and announced Palestinian statehood recognition," stripping the hedges, importing the "broke with Washington" framing from US political reporting conventions, and over-stating the announcement modality.

### Detection protocol (how to catch it)

- For critical foreign-language claims, use a second, independent translation.
- For technical, legal, or bureaucratic terms, verify the domain-specific English equivalent rather than relying on AI translation.
- Ask: does the AI translation preserve the tone (formal/informal), conditionality (may/must/might), and institutional framing of the original?
- Look for highly specific western idioms, US political terminology, or culture-war buzzwords applied to non-western subjects. Words like "woke," "libertarian," "evangelical," "progressive," "conservative," "broke with," "doubled down" carry US political baggage that should not be silently imported.
- Check modality verbs, tense, evidential markers, and whether the source is direct quote, indirect quote, or summary.
- Look for verb intensification: "expressed concern" becoming "condemned"; "evoked" becoming "confirmed"; "considering" becoming "announced."
- Check for hedge removal: hedge phrases in the source language that get omitted in translation are a primary drift mechanism.

### Step-by-step verification procedure (when the verifier does not read the source language)

1. Identify all citations to non-English sources.
2. Retrieve the original text.
3. Use a second AI translation (different model) and compare. Divergences flag ambiguity in the source.
4. Produce a back-translation or use a trusted translation service.
5. Contact a domain expert or native speaker for critical claims.
6. Use the Wayback Machine or original publication to access the source document for back-translation checks.
7. For legal or regulatory documents: DeepL and specialized legal translation tools are more reliable than general-purpose AI translation for procedural terminology.
8. Use a distinct, rigid translation tool (for example DeepL) on the original foreign-language paragraph. Compare the literal translation against the AI's contextual summary to detect injected cultural framing.
9. Compare the AI's version for added or altered qualifiers. Flag any drift.
10. Note in the text when a claim is drawn from a translated foreign-language source and name the original publication.
11. Preserve the original-language excerpt, obtain an independent translation, compare high-stakes verbs, and document any irreducible nuance loss.
12. Quote in the original language with a professional translation appended; flag the translation chain.
13. Identify the AI's translated quote, retrieve the original-language source, compare AI translation to professional translation if one exists, and trace the translation chain.
14. Apply the Claude exec canonical procedure: literal back-translation from non-synthesis tool, native-speaker checker requirement for critical claims.

### Sources

Reuters Institute journalism guidelines; Nieman Lab methodology; academic translation studies literature; Poynter; Claude exec 2026-05-18 (Le Monde canonical example).

### Signal strength, base rate, detection difficulty, false-positive risk

- **Signal strength.** MED (hard to detect without language ability); HIGH when significant tonal or contextual shifts in translation are surfaced.
- **Base rate.** MED in international coverage; medium in unedited AI output involving translation and summarization. Higher when the source language has hedged diplomatic conventions (French, Japanese, classical Arabic) that English flattens.
- **Detection difficulty.** Very hard for monolingual verifiers; hard even with language ability if cultural framing is the failure mode.
- **False positive risk.** MED. Translation always involves interpretation. Human translators can also introduce subtle biases, but AI's systematic nature makes it more predictable.

### Remediation

Use multiple translation services and human translators for critical foreign-language sources. Demand literal translation over contextual summarization. Explicitly instruct the AI to preserve the original tone and cultural context during translation. Adjust language to match source register and strength. Note when the writer cannot read the source language and route to additional verification.

For published material, the correction must acknowledge the translation source and the drift, not just the corrected English wording. A correction that says "an earlier translation used 'condemned' where the original French was closer to 'expressed concern'" is the minimum threshold; for high-stakes diplomatic coverage, the original-language passage should be appended with a professional translation.

### Era status

Active. An emerging pattern as models are increasingly used for cross-lingual content generation and summarization. Likely to persist because the underlying cause (English-language analytical conventions dominate training data) is structural to the current corpus.

### Cross-references

- C1-NESTED-001: nested attribution across languages compounds translation drift at each layer.
- C1-PARAPH-001: paraphrase boundary drift in translated material is especially hard to catch because the boundary check requires comparing against the original-language source.
- C1-POSSHIFT-001: translation drift contributes to aggregate position-shifting when the framing layer is imported from English conventions.
- v1.1.0 4a (Wrong Framing): translation drift is a specific subtype of framing drift around verifiable language elements.

---

## C1-URLROT-001: URL Rot vs. Hallucination Distinction

### Pattern description

A citation that exists but no longer points to what is claimed represents a different failure mode than a hallucinated citation. Failures include: (1) page redirected to a different publication; (2) content updated and original claim removed; (3) paper retracted; (4) paywall added post-citation; (5) tweet or social-media post deleted; (6) CMS update removed the referenced paragraph. These are "stale" rather than "hallucinated" citations, but they may still fail to support the claim.

The same surface symptom (broken or non-matching link) requires different remediation depending on cause. Hallucinated citations should be removed and re-sourced; rotted citations should be cited via archive URL plus original publication metadata. The conflation of the two failure modes produces wrong fixes: hallucinations get archive-replaced with archives that do not exist, or rotted citations get removed even when the original would have supported the claim.

v1.1.0 Section 4f (Hallucinated Citations) addresses fabricated sources as an undifferentiated bucket. This protocol differentiates the bucket into six classes, each requiring its own remediation.

### Why this matters

v1.1.0 Section 4f addresses fabricated sources. This protocol addresses sources that exist but no longer provide the evidence claimed. Conflating the two produces wrong fixes: hallucinated citations should be removed and re-sourced; rotted citations should be cited via archive URL plus original publication metadata.

### Empirical grounding

A University of Pennsylvania study (Rao, Wong, Callison-Burch, April 2026, arxiv 2604.03173) found that in LLM output, 3 to 13 percent of citation URLs are hallucinated (never existed) while 5 to 18 percent are non-resolving overall. The gap between hallucinated and non-resolving is the stale URL fraction: real pages that have since gone offline.

Over 70 percent of URLs in the Harvard Law Review no longer resolve (Zittrain et al. 2014 link-rot study). 25 percent of webpages from 2013 to 2023 have disappeared (Pew Research Center, "When Online Content Disappears," May 2024). Sadatmoosavi's Aslib 2026 link-rot study and Spennemann (arxiv 2504.08755) further document the scale. These numbers establish that URL-rot verification is not optional.

Stanford RegLab measurements (Magesh et al., June 2024) found 17 to 33 percent legal-AI hallucination rates with retrieval-augmented generation, anchoring the prevalence claim for legal domain. The legal sanction record (Mata v. Avianca 2023, Mostafavi 2025, Goldberg Segalla 2025, Damien Charlotin's 1,455+ documented cases) shows that conflating URL rot with hallucination is not just an editorial concern; courts are now sanctioning lawyers for AI-fabricated citations at scale.

### Failure taxonomy (the six-category classification)

This taxonomy is load-bearing. Each category has its own remediation; conflating categories produces wrong fixes.

1. **HALLUCINATED.** URL has no Wayback Machine record. The citation was fabricated. The page never existed. Remediation: remove the citation; re-source the claim from verifiable evidence.

2. **STALE.** URL has a Wayback record but is no longer resolving live. The page existed; it has been taken down or removed. Remediation: cite the Wayback snapshot URL plus the original publication metadata (publisher, date, title); note the archive provenance.

3. **REDIRECTED.** URL resolves live but points to different content than originally cited. The page exists but has been replaced or repurposed. Remediation: check whether the archive version supports the claim; cite the archive snapshot for the original content; note that the live URL no longer points to the cited material.

4. **RETRACTED.** URL resolves to a retraction notice rather than the original paper. The paper existed and was withdrawn for cause (data fabrication, methodological error, ethics violation). Remediation: remove the claim that depended on the retracted paper; find an independent source for the underlying assertion if it is essential; never cite a retracted paper as live support for a current claim.

5. **PAYWALLED.** URL resolves live but content is now behind a paywall; original claim cannot be verified by the public. The content may still exist; the verifier's access is restricted. Remediation: note the access limitation; verify through institutional access or interlibrary loan if possible; if verification is not possible, hedge or remove the citation.

6. **UPDATED.** URL resolves live but the specific claim has been removed or revised in a page update. The page exists; the cited material has been edited away. Remediation: use the Wayback snapshot of the original version; cite the archive URL plus the original publication date; note that the live page has been updated.

### Failure modes

1. AI cites doi.org/10.1038/s41586-2023-fake-doi-12345; the DOI is fabricated.
2. AI cites a real WaPo article URL; the article was unpublished after a correction; URL now returns 404.
3. AI cites a Twitter/X URL; the tweet was deleted; URL returns "post not found."
4. AI cites a Substack URL; the post is paywalled now but was not at training time; AI's "summary" describes content the verifier cannot access.
5. AI cites a 2023 article link that now redirects to a 2026 update that does not contain the cited statistic.
6. A paper page persists but the article was later retracted.
7. The URL works but the referenced paragraph is gone after a CMS update.
8. AI cites a valid domain but invents the sub-directory path to match the prompt's subject.

### Concrete examples in context

1. *Manus AI example.* AI cites a valid URL, but upon clicking, the page is a 404 error or has been redirected to an unrelated product page. (URL rot, possibly REDIRECTED.)

2. *Manus AI example.* AI cites a valid URL, but the content on the page has been updated and no longer supports the claim made in the text. (UPDATED.)

3. *Manus AI example.* AI cites a valid URL, but the article has been retracted due to errors. (RETRACTED.)

4. *Manus AI example.* AI cites a valid URL, but the content is behind a paywall, making verification difficult. (PAYWALLED.)

5. *Grok worked example.* Draft cites a 2024 blog post for a specific statistic. The URL resolves, but the post was updated in 2025 with a revised number and a note on methodology change. The draft reflects the pre-update claim. (UPDATED.)

6. *ChatGPT example.* A 2023 article link now redirects to a 2026 update that does not contain the cited statistic. (REDIRECTED with UPDATED content; double failure.)

7. *ChatGPT example.* A paper page persists but the article was later retracted. (RETRACTED.)

8. *ChatGPT example.* The URL works but the referenced paragraph is gone after a CMS update. (UPDATED.)

9. *Gemini example.* AI cites www.university.edu/research/paper2024. It 404s. The archive shows it existed in 2024. (STALE.)

10. *Gemini example.* AI cites www.nature.com/articles/fake-biology-study. It 404s. The archive has zero record of it. (HALLUCINATED.)

11. *Gemini example.* AI cites a valid domain but invents the sub-directory path to match the prompt's subject. (HALLUCINATED with domain-camouflage.)

12. *DeepSeek worked example.* AI cites a 2024 paper at a DOI; the current page shows "retracted." The Wayback Machine shows the paper was available and correct at training time. Classification: URL rot (retraction), specifically RETRACTED.

13. *Claude Opus 4.7 expansion example.* AI cites "https://example.com/study-2024" with a quoted summary; the URL has no record on Wayback Machine; the doi pattern was a plausible but fabricated string. (HALLUCINATED.)

14. *Claude Opus 4.7 expansion example.* AI cites a real URL "https://nytimes.com/2024/03/article" with summary; the article was published and later corrected; Wayback Machine has a snapshot of the original; the AI's summary aligns with the original, not the correction. (UPDATED. The original existed and matched the AI's summary; the current page reflects the post-correction version.)

15. *Claude exec canonical worked example.* NYT/Sora hallucinated slug vs Reuters URL decayed to paywall. The AI synthesis cited what looked like a New York Times URL about OpenAI's Sora model. The slug was a plausibly-constructed string ("nytimes.com/2024/02/sora-launch-analysis") that returned 404 with no Wayback record (HALLUCINATED). The same synthesis cited a Reuters article on the same topic; the Reuters URL resolved live but the article had been moved behind Reuters' subscription wall after a redesign (PAYWALLED). Two URLs, same surface symptom (verifier cannot access cited content), different underlying classifications, different remediations.

### Detection protocol (how to catch it)

- Click every URL. Compare current page content against the claim made in the draft. Check archive snapshots (Wayback Machine) for the version that would have been available at generation time. Distinguish changed content from non-existent content.
- Use the urlhealth open-source methodology (Rao et al., 2026) or the Internet Archive Wayback Machine to verify historical existence.
- Treat live URL resolution and claim verification as separate checks. A URL that resolves does not mean it supports the cited claim.
- For DOIs: resolve via doi.org. A fabricated DOI returns a "DOI cannot be found" error; a real DOI resolves to a publisher page; a retracted DOI resolves to a retraction notice.
- For social-media URLs: check the archive for the original post; deleted tweets and removed posts are very common.
- For paywalled sources: note the access limitation; if the verifier cannot confirm content matches the claim, downgrade or remove.

### Step-by-step verification procedure

1. For every URL in an AI-generated document, attempt a live HTTP GET request.
2. If the URL returns a 404 or similar error: check the Wayback Machine (web.archive.org) for an archived version.
3. If no Wayback record exists: classify as HALLUCINATED. Flag for removal.
4. If a Wayback record exists but URL does not resolve: classify as STALE. Use the archive version for the claim check.
5. If the live URL resolves: check that the content at the URL actually supports the specific claim cited. A live URL that does not support the claim is either REDIRECTED (now points elsewhere) or UPDATED (content edited away from cited material).
6. For academic citations: check Retraction Watch for paper retraction status. If retracted, classify as RETRACTED.
7. For paywalled sources: note the access limitation and verify through institutional access or interlibrary loan if possible.
8. Capture the current page, check archival snapshots, compare publication dates, inspect redirect chains, and check retraction status.
9. If the source drifted, cite an archive or permanent identifier, not the current mutable page.
10. Apply the Claude exec canonical three-tier classification (live-and-matching, decayed-recoverable, fabricated), archive.org replacement.
11. Input the non-resolving URL into the Wayback Machine. If the archive has snapshots of the target paper containing the claimed data, it is URL rot; replace with the archive link. If the archive has zero snapshots, or snapshots of a completely different page, flag it as a severe hallucination.
12. For each URL, record in a citation ledger: live URL, status code, Wayback snapshot URL (if any), match status, classification, action taken.

### Tool

urlhealth (Rao et al., 2026) is an open-source Python pip-installable tool that automates steps 1-4, classifying URLs as LIVE, DEAD, LIKELY_HALLUCINATED, or UNKNOWN. The tool reduces manual checking from minutes per URL to seconds per URL and is the recommended starting point for any document with more than ten citations.

### Sources

Rao, Wong, Callison-Burch (2026). "Detecting and Correcting Reference Hallucinations in Commercial LLMs." arXiv:2604.03173. Pew Research Center (2024). "When online content disappears." Zittrain et al. (2014). Harvard Law Review link rot study. Sadatmoosavi Aslib 2026 link-rot study. Spennemann arxiv 2504.08755. Stanford RegLab Magesh et al. June 2024 (17 to 33 percent legal-AI hallucination measurements). Retraction Watch; Claude exec 2026-05-18 (NYT/Sora canonical example).

### Signal strength, base rate, detection difficulty, false-positive risk

- **Signal strength.** HIGH for HALLUCINATED; MED for STALE, REDIRECTED, UPDATED; HIGH for RETRACTED (the retraction notice is itself a signal).
- **Base rate of non-resolving URLs in AI output.** 5 to 18 percent across models (Penn 2026); 3 to 13 percent are hallucinated. High in unedited AI output, especially for older or rapidly changing topics.
- **Detection difficulty.** Easy with tooling (urlhealth); medium without; hard for distinguishing rot from hallucination without archive checks.
- **False positive risk.** LOW for HALLUCINATED classification; MED for STALE (may archive somewhere not indexed by Wayback); LOW for RETRACTED. Human writers are expected to provide current and accurate citations.

### Remediation (per classification)

- **HALLUCINATED:** remove the citation; re-source the claim from verifiable evidence. If the claim is essential and no source can be found, hedge or remove the claim.
- **STALE:** cite the Wayback snapshot URL plus the original publication metadata.
- **REDIRECTED:** if the archive snapshot still supports the claim, cite the archive plus a note ("at the time of original publication"); if not, treat as effectively HALLUCINATED for the current claim.
- **RETRACTED:** remove the claim that depended on the retracted paper; do not cite the retracted paper as live support; if the underlying assertion has independent support, cite the independent source.
- **PAYWALLED:** note access limitation; for high-stakes claims, route to institutional access or interlibrary loan; if verification is not possible, hedge or remove.
- **UPDATED:** cite the Wayback snapshot of the original version with original publication date; note that the live page has been updated.

Update dead URLs with archive links; delete hallucinated citations entirely. Manually check all citations. Prioritize recent sources. Explicitly instruct the AI to verify URL validity and content relevance.

### Era status

Active. Increasingly prevalent as web content is dynamic and models are trained on static datasets. The trajectory is toward more rot over time, not less; the proliferation of CMS-driven content management means more URLs change content silently without proper 301 redirects.

### Cross-references

- C1-SYNTH-001: HALLUCINATED URLs in the C1-URLROT-001 sense may overlap with AI-generated synthetic sources when the URL points to AI-generated content rather than not existing at all.
- C1-LAUNDER-001: URL rot in the chain of citations may obscure the laundering pattern; archive checks are part of the laundering trace-back.
- C1-TOOLHALL-001: per-family URL fabrication patterns (GPT URL fabrication, Claude DOI fabrication) determine which URL classes to expect from which model.
- v1.1.0 4f (Hallucinated Citations): this protocol differentiates the v1.1.0 single-bucket failure into six classes plus residual pure-fabrication.
- v1.1.0 4g (Outdated or Superseded Data): superseded data overlaps with the UPDATED and RETRACTED categories here.

---

## C1-SYNTH-001: AI-Generated Synthetic Sources

### Pattern description

A "real" source is indexed and reachable, but it is itself synthetic, recursively derivative, or AI-seeded slop. AI output indexed by search engines is treated as a primary source by downstream AI systems, creating a feedback loop of fabricated or unverified information. The AI model, searching the web or using RAG, retrieves another AI's fabricated content, presents it as fact, and adds a citation to the AI-generated page. This creates self-reinforcing false information with a documented citation chain.

AI-generated content has become a primary source for downstream RAG systems and human research. This is a new problem class since v1.1.0 shipped. The C1-URLROT-001 protocol classifies URL fetch results into HALLUCINATED vs. STALE vs. other classes; this protocol addresses what happens when the URL fetches successfully but the source at the URL is itself synthetic. A URL that resolves live and returns a complete article is "valid" under URL classification but may be invalid as a source.

### Why this matters

Per Claude's exec summary, "Retrieval Collapse" (arxiv 2602.16136) found 67 percent pool contamination yields 80 percent exposure contamination. Synthetic primary sources (AI-generated content presented as authoritative) contaminate the broader information ecosystem.

A Lancet letter (Topaz et al., May 2026) documented a sixfold increase in fabricated citations in academic papers from 2023 to 2025, reaching 1 in 277 papers by early 2026. Claude's exec cites a twelve-fold rise from 2023 in the same metric; both figures are reported in the underlying sources, with the sixfold figure being the cumulative 2023-2025 growth and the twelve-fold figure including 2026 data points. The Opus expansion flagged the specific Lancet venue for verification during synthesis.

The study found that citation practices have changed from reading papers to prompting AI tools and using outputs as citations. Ahrefs measured 74.2 percent of newly indexed English-language web pages in April 2025 contained AI-generated content; Spennemann documented 30 to 40 percent of active web pages with AI signatures.

### Failure modes

1. AI generates a fictional news article. This article is indexed by search engines. A second AI, performing research, finds and cites this fictional article as a legitimate source.
2. AI creates a plausible-sounding but false statistic. This statistic is published online. A third AI, summarizing data, incorporates this false statistic, citing the AI-generated source.
3. AI generates a fake academic paper abstract. This abstract is posted on a preprint server. Another AI, performing a literature review, includes this abstract as a valid research finding.
4. AI cites a "study" that is actually a blog post written by AI summarizing other AI summaries.
5. AI cites an "expert" who is a synthetic identity created by AI for the purpose of being cited.
6. AI cites a "news article" that is content-farm output published rapidly without human review.
7. AI cites an academic-sounding journal that is actually a known predatory publisher of LLM-generated papers.

### Concrete examples in context

1. *Manus AI example.* AI generates a fictional news article. This article is indexed by search engines. A second AI, performing research, finds and cites this fictional article as a legitimate source.

2. *Manus AI example.* AI creates a plausible-sounding but false statistic published online. A third AI, summarizing data, incorporates this false statistic, citing the AI-generated source.

3. *Manus AI example.* AI generates a fake academic paper abstract on a preprint server. Another AI's literature review includes this abstract as a valid research finding.

4. *Grok worked example.* A 2025 blog post cites "a 2024 industry analysis" that matches the style and content of common AI-generated summaries. The "analysis" site launched in late 2024 with generic content and no evident editorial process. No primary study exists. The blog post cites the synthetic "analysis"; a downstream synthesis cites the blog post; the original "analysis" never had a primary basis.

5. *ChatGPT example.* A research assistant cites an indexed explainer that is machine-written and cites no primary material. The explainer ranks well on the topic; downstream researchers treat it as a source.

6. *ChatGPT example.* Multiple blogs repeat the same synthetic claim with no original reporting. The corroboration appears across "independent" sources but all trace to one AI seed.

7. *ChatGPT example.* A synthetic health article is treated as primary evidence because it ranks well in search. Search-rank-as-authority is the failure mechanism.

8. *Gemini example.* AI cites a blog post from a generic-sounding domain that perfectly matches the user's obscure query, but the blog contains no external links. The "perfect match" plus "no external links" pattern is a synthetic-source signature.

9. *Gemini example.* AI cites a "news" article that is visibly composed of standard AI markdown formatting and empty filler. The stylistic fingerprint of AI generation is visible on the cited page itself.

10. *Gemini example.* AI cites an academic-sounding journal that is actually a known predatory publisher of LLM-generated papers. The journal has an editorial board, a website, and accepts submissions; it does not have peer review.

11. *DeepSeek worked example.* AI cites "Smith et al. (2025) 'The Impact of RAG on Enterprise Efficiency,' Journal of AI Applications." The journal does not exist; a search reveals the paper only on an AI-generated blog. It is synthetic.

12. *Claude Opus 4.7 expansion example.* AI summary cites "according to recent research from the Institute for Digital Trust" (a real-sounding but non-existent institute, or a real institute whose "research" is the Substack post of a single individual using AI tools).

13. *Claude Opus 4.7 expansion example.* AI cites a YouTube transcript by "Dr. Smith" whose credentials trace to a single LinkedIn page with no academic appointments verifiable. The credentials are surface-plausible; the academic record is empty.

14. *Claude exec canonical worked example.* "Dr. Helena Marsh, University of East Yorkshire" synthetic citation; Springer "Mastering ML" book with two-thirds fabricated references (Retraction Watch, April 2025). The AI synthesis cited "Dr. Helena Marsh of the University of East Yorkshire" as the source for a specific claim about machine-learning ethics. The University of East Yorkshire does not exist; no Helena Marsh appears in any academic database; the citation is fully synthetic. Separately, a Springer-published book on machine learning ("Mastering Machine Learning") was found to contain AI-fabricated citations to non-existent papers, with two-thirds of references fabricated (Retraction Watch April 2025 coverage). The Springer case shows that synthetic citations can survive peer review and traditional publishing channels.

### How to detect AI-generated synthetic sources

- Check whether the cited source itself appears AI-generated using the criteria in synthesis-content-quality.
- Look for recent publication dates combined with suspiciously comprehensive, well-structured content on niche topics.
- Check whether the cited source itself has citations: AI-generated pages often have no secondary citations or have their own hallucinated citations.
- Check whether the author of the cited source has other published work (institutional affiliation, academic profile).
- Check multiple AI generation detection signals against the cited source text.
- The target source will lack an author byline, lack primary evidence, and display high Verbal Tic Indexes (for example "In today's fast-paced digital world").

### Trace-back procedure

1. For any source that was found through AI-assisted search: retrieve it and apply the synthesis-content-quality detection protocol.
2. Check the publication's domain registration date against the content's claimed date. A domain registered six months ago publishing comprehensive "industry analysis" of a niche topic from 2018 is a red flag.
3. Check whether the publication has editorial policies, contact information, or institutional backing.
4. Search for independent non-AI sources that cite the same original claim.
5. If the claim exists only in AI-generated or AI-indexed sources: classify as unverifiable and do not cite.
6. For every cited source, verify the source's basic provenance (author identity, institution, publication venue).
7. For "experts," check at minimum: academic appointments via institution websites, peer-reviewed publications via Google Scholar, professional registrations where applicable.
8. For "studies," check publication venue, peer review status, authors' credentials and affiliation, citation count and source.
9. Look up the cited work in CrossRef, Google Scholar, or legitimate databases. If absent, search the exact title on the web; examine the host site for AI markers.
10. Trace sources upstream until you hit a primary document, direct interview, official data release, transcript, or credible original reporting. Run a provenance ladder. If source A cites source B which cites source C, stop only when a primary or accountable original is found. If no primary emerges, do not use the chain as factual support.
11. Click through to the cited source. Evaluate the source domain for journalistic or academic integrity (look for contact info, editorial boards, and author histories). If the source cannot prove its own provenance or displays overwhelming AI stylometry, the citation is invalid.
12. Apply Retraction Watch databases.
13. Flag synthetic sources at the citation level. In editorial workflow, this means a flag visible in the fact-check log, not just a silent removal.

### Sources

Topaz et al. (2026). Lancet. "Fraudulent citations in academic papers." STAT News coverage (2026-05-06); UNC Charlotte library guide on AI hallucinated citations; Enago (2025). "AI Hallucinations in Research: Why 40% of AI Citations Are Wrong." Retraction Watch Springer ML book April 2025. Spennemann arxiv 2504.08755. Ahrefs April 2025 measurement. Retrieval Collapse arxiv 2602.16136. Stanford RegLab Magesh et al. June 2024. Claude exec 2026-05-18 ("Dr. Helena Marsh" canonical example, Springer book).

### Signal strength, base rate, detection difficulty, false-positive risk

- **Signal strength.** Very HIGH when synthetic source is identified. The presence of AI-generated sources being cited as primary is a definitive indicator of this failure mode.
- **Base rate.** Increasing rapidly; Lancet sixfold increase 2023-2025; reaching 1 in 277 PubMed papers by early 2026 per Lancet letter. Ahrefs April 2025 measurement: 74.2 percent of newly indexed pages contain AI-generated content. Spennemann 2025: 30 to 40 percent of active web pages with AI signatures.
- **Detection difficulty.** Medium to hard. Very hard in absolute terms when chains are deep. Requires applying detection methodology to sources, not just text. Requires tracing back the origin of a source to determine if it was AI-generated.
- **False positive risk.** MED. Some AI-assisted content is factually accurate; detection does not equal invalidity. Low for clear synthetic content farms; human researchers are expected to critically evaluate sources.

### Remediation

Implement strict source verification protocols that prioritize human-authored, reputable sources. Develop tools to detect AI-generated content in cited sources. Explicitly instruct the AI to avoid citing other AI-generated content. Remove citations to synthetic sources. Re-source from verifiable primary or peer-reviewed material. Trace the claim to a recognized primary authority (peer-reviewed journal or major news outlet). Warn about contamination.

For high-stakes publications, an explicit synthetic-source check should be part of the editorial workflow, with a documented log of which citations were verified and which were rejected. The Springer "Mastering ML" book case demonstrates that traditional publishing channels can fail at synthetic-source detection; the corrective response is more rigorous editorial verification, not reliance on the publisher's brand.

### Era status

Active and accelerating. A rapidly growing problem as AI-generated content proliferates online. The growth trajectory (Topaz et al. measurement, Ahrefs measurement) suggests synthetic sources will be a structurally larger share of indexed content over the next two to five years.

### Cross-references

- C1-URLROT-001: synthetic sources may pass URL-rot classification because the URL fetches successfully; the failure is at the source-quality layer, not the URL layer.
- C1-LAUNDER-001: synthetic sources are the upstream nodes in many citation laundering chains; detection of the synthetic root often surfaces the entire chain.
- C1-TOOLHALL-001: per-family fabrication patterns (synthetic experts from Claude, synthetic URLs from GPT) determine the most likely synthetic-source shapes.
- v1.1.0 4f (Hallucinated Citations): synthetic sources are a specific subtype of the broader citation-fabrication failure; this protocol differentiates them from pure HALLUCINATED non-existence.
- v1.1.0 Section 6 (Study Verification Protocol): the v1.1.0 protocol verifies study existence; this protocol extends it to verify source authenticity.

---

## C1-LAUNDER-001: Citation Laundering Chains

### Pattern description

v1.1.0 Section 2 establishes that cross-corroboration among LLM outputs is not independent verification because all LLMs may share the same training data origin for the claim. This protocol adds the concrete trace-back procedure v1.1.0 did not provide.

Citation laundering chains form because LLM-generated content is indexed, cited by other AI systems, and progressively given the appearance of independent verification through multiplying citations. The original fabricated claim appears to be supported by multiple independent sources, all of which trace to the same training data artifact. AI agents prefer citing highly ranked, high-domain-authority URLs (textbooks, literature reviews) rather than digging for the primary empirical data, resulting in "citation laundering."

Multi-source confidence from v1.1.0 (the principle that multiple independent sources increase confidence) must condition on graph independence, not on raw count. Three sources that all trace to one upstream are single-sourced. The structural change to v1.1.0 Section 2 in v2.0 is to require graph-independence verification before treating multiple sources as raising confidence.

### Why this happens

Citation laundering chains form because LLM-generated content is indexed, cited by other AI systems, and progressively given the appearance of independent verification through multiplying citations. AI summarizers and content aggregators draw on each other's outputs, especially when scraping the web. Over iterations, a fabricated fact can become "common knowledge." Search engines index synthetic content; later models trained on or retrieving from the open web ingest it as signal; citation chains form without human primary verification.

Causal hypothesis ranked: (1) training-data skew (models learn from the internet, which contains such chains); (2) helpfulness optimization (models aim to provide corroborating evidence, even if non-independent); (3) product wrapper effects (search-augmented modes amplify circularity).

### Pattern identification

A laundering chain is present when: multiple sources cite the same specific statistic or claim; all sources were published within a short window; none of the sources provides a primary document citation; and all sources use similar phrasing (suggesting they were generated from the same training data artifact or from each other).

### Failure modes

1. AI A makes a claim and cites a non-existent source. AI B cites AI A as evidence. AI C cites AI B, creating a chain of mutually reinforcing but ultimately baseless citations.
2. A single, weakly sourced claim is picked up by multiple AI-generated articles, which then cite each other.
3. A minor blog post makes an unsubstantiated assertion. Multiple AI systems summarize this blog post, and then other AI systems cite these summaries.
4. Three "independent" sources all trace back to a single AI-generated blog post.
5. A Wikipedia article cites a news article that cites an AI-generated content farm that produced its claim from training data.
6. A peer-reviewed paper's citation traces through a chain that includes one AI-summarized review.
7. Chatbot answer cites a blog that cites another chatbot answer.
8. Three "independent" pages quote the same synthetic report title that does not exist.
9. A copied news summary and an SEO rewrite are counted as two sources.
10. A 2025 Nature review is cited to claim a specific drug efficacy rate, but the review was only quoting a flawed 2012 pilot study.
11. A news aggregator claiming a company went bankrupt misquotes the original bankruptcy filing.
12. A Wikipedia article that cites a dead link.

### Concrete examples in context

1. *Manus AI example.* AI A makes a claim and cites a non-existent source. AI B cites AI A as evidence. AI C cites AI B, creating a chain of mutually reinforcing but ultimately baseless citations.

2. *Manus AI example.* A single, weakly sourced claim is picked up by multiple AI-generated articles, which then cite each other, making the claim appear more credible than it is.

3. *Manus AI example.* A minor blog post makes an unsubstantiated assertion. Multiple AI systems summarize this blog post, and then other AI systems cite these summaries, creating a false impression of broad consensus.

4. *Perplexity example.* AI-generated blog post A: "Studies show that X percent of Y do Z." News aggregator B (AI-assisted): "According to multiple reports, X percent of Y do Z." (Cites A.) AI-assisted research summary C: "Research indicates X percent of Y do Z (Source: B)." The original "studies" do not exist. The chain has three levels and zero primary sources.

5. *Grok worked example.* Draft cites Source A, which cites Source B, which cites an LLM research summary, which cites a generic "studies show" without primary link. The claim originates in weak or hallucinated territory.

6. *ChatGPT example.* Chatbot answer cites a blog that cites another chatbot answer. The citation graph is a cycle.

7. *ChatGPT example.* Three "independent" pages quote the same synthetic report title that does not exist. The "report" is the fabricated upstream.

8. *ChatGPT example.* A copied news summary and an SEO rewrite are counted as two sources. The two surface "sources" are derivatives of the same upstream.

9. *Gemini example.* AI cites a 2025 Nature review to claim a specific drug efficacy rate, but the review was only quoting a flawed 2012 pilot study. The chain runs through a high-authority intermediate node but converges to weak primary.

10. *Gemini example.* AI cites a news aggregator claiming a company went bankrupt, but the aggregator misquoted the original bankruptcy filing. The aggregator is the laundering node.

11. *Gemini example.* AI cites a Wikipedia article that cites a dead link. The Wikipedia citation traces to nothing.

12. *DeepSeek worked example.* Claim: "75 percent of projects fail due to poor communication." Source A cites Source B; Source B cites a blog that itself cites a survey that cannot be found. The original survey never existed; it was invented by the blog's AI.

13. *Claude Opus 4.7 expansion example.* AI summary states "multiple sources confirm X." Trace: source A cites source B cites source C. Source A and B both cite C. C is an AI-generated content farm post. No independent corroboration despite three citations.

14. *Claude Opus 4.7 expansion example.* Per Topaz et al. May 2026 Lancet letter, one in 277 PubMed papers in 2026 referenced a fabricated paper; twelve-fold rise from 2023. The laundering chain through PubMed indexing is the mechanism: a synthetic citation enters a published paper; that paper is then cited by downstream papers; the synthetic citation gains apparent authority through the PubMed-indexed chain.

15. *Claude exec canonical worked example.* "31 percent drop in problem-solving" laundered through three sources collapsing to single arXiv preprint by non-ORCID authors. The AI synthesis claimed a "31 percent drop in problem-solving" attributable to AI use, citing three apparently independent sources (a journalism outlet, a research summary, a think-tank brief). Trace-back showed all three converged on a single arXiv preprint authored by individuals without ORCID identifiers and without institutional affiliations verifiable through standard channels. The preprint's data and methodology were not independently replicated. The three "sources" collapsed to one upstream node; the multi-source confidence framework's count-of-three should have been confidence-of-one after graph collapse.

### Detection protocol (how to catch it)

- Map the citation graph. Identify the earliest or most primary node in the chain. Verify that node directly. Count hops and note where verification stopped.
- Check independence, not just count.
- The cited text will use language like "As noted by Smith et al." or "Studies show that" without providing the raw data itself.
- Watch for time-window clustering: multiple sources for the same statistic published within a six-month window may indicate they all derived from a single recent upstream.
- Watch for phrasing similarity: if multiple "independent" sources use nearly identical phrasing for the same claim, they likely share an upstream.
- Watch for missing primary documents: a claim that appears in multiple secondary sources but never in a primary peer-reviewed paper, government release, or original interview is a candidate laundering chain.

### Step-by-step trace-back procedure

1. For any statistic or claim that appears "well sourced" (multiple references), list all sources.
2. Extract every citation and its immediate source.
3. For each source, identify its own source for the claim. Does it cite a primary document?
4. Follow the chain backward until a primary or high-quality secondary source is reached.
5. If all sources cite each other circularly (A cites B, B cites C, C cites A), or if all sources cite only "various studies" without a specific primary document: the chain is laundered.
6. Trace backwards until a primary document is found. Primary documents are: original study with DOI, government data release, original interview transcript, official statement.
7. If no primary document can be found in a chain of 3+ sources: classify the claim as unverifiable and do not publish it as established fact.
8. Document the chain structure in your verification notes. The structure (linear, tree, cycle, converging) is itself diagnostic.
9. For multi-source claims, build a citation graph: source A cites source B cites source C, etc. Check for graph independence: are sources A, B, C drawing on actually different upstreams, or do all paths converge?
10. If all paths converge to a single upstream, treat the claim as single-sourced.
11. If the upstream is AI-generated, flag the entire chain.
12. Validate the claim against the methodology and results of the primary paper, not the secondary review. If the primary paper does not support the claim, the citation is laundered.
13. Apply the Claude exec canonical procedure: citation-graph mapping, downgrade to single-source confidence when graph collapses.
14. For every source in a corroboration set, identify its upstream dependency chain. Collapse syndicated, derivative, and AI-recursive sources into one evidentiary unit. Require at least one independent primary or accountable secondary source.

### Sources

v1.1.0 Section 2 (principle established); Enago 2025 (hallucination chain documentation); STAT News 2026 (fabricated citation propagation); Penn 2026 (citation fabrication at scale); Topaz et al. Lancet May 2026 (1 in 277 PubMed papers, twelve-fold rise from 2023); academic work on information cascades and misinformation; professional fact-checking organization methodology pages (Snopes, PolitiFact, Full Fact); Claude exec 2026-05-18 ("31 percent drop in problem-solving" canonical example).

### Signal strength, base rate, detection difficulty, false-positive risk

- **Signal strength.** HIGH when chain is identified. Very HIGH when chain of AI-generated content citing each other is documented.
- **Base rate.** HIGH for statistics without primary document citations. Increasing rapidly in unedited AI output.
- **Detection difficulty.** Hard. Very hard in absolute terms. Requires tracing backwards through multiple sources and sophisticated network analysis of citations and content origin.
- **False positive risk.** LOW. Genuine statistics always have a primary document. Human researchers are expected to seek truly independent corroboration.

### Remediation

Implement a strict protocol for source independence. For any claim, trace back citations to their original, human-authored sources. If a claim is only supported by other AI-generated content, flag it as unverified. Develop tools to visualize citation networks. Verify graph independence before trusting "multi-source" claims. If the chain converges on a single AI upstream, the claim is not multi-source and should be re-sourced from independent primary material. Find and cite the primary study (Gemini's "Primary-Backed Reference Chain" or PBRC protocol framing).

For high-volume editorial workflow, build a citation graph visualization tool that displays the chain depth and convergence pattern for each claim. The visualization makes laundering chains immediately visible; without it, the chain only emerges after manual trace-back.

### Era status

Active and accelerating. A rapidly growing problem, exacerbated by the proliferation of AI-generated content. The Lancet letter trajectory (twelve-fold rise from 2023 to 2026) suggests the laundering pattern will continue to grow as a share of citation chains.

### Cross-references

- C1-SYNTH-001: the upstream nodes in laundering chains are often synthetic sources; detection of the chain converges with detection of the synthetic root.
- C1-URLROT-001: rotted URLs in the chain may obscure the laundering structure; archive checks are part of the trace-back.
- C1-TOOLHALL-001: per-family laundering signatures vary; Gemini's "vague attribution" pattern often serves as a laundering intermediate node.
- v1.1.0 Section 2 (Multi-Source Confidence Framework): this protocol revises Section 2 to require graph independence as a precondition for treating multiple sources as raising confidence.
- v1.1.0 4f (Hallucinated Citations): laundered chains often have a hallucinated citation at the upstream root; the chain is the propagation mechanism.

---

## C1-TOOLHALL-001: Tool-Specific Hallucination Patterns (Per-Family Fabrication Signatures)

### Pattern description

Different LLM families produce hallucinations with characteristic signatures, reflecting their unique architectures, training data, and alignment strategies. Identifying the model family helps prioritize which types of errors to check. This parallels Bucket A1 (model-family stylistic fingerprinting) but focuses on fact-fabrication patterns rather than style patterns. The per-family signature is the bucket-C parallel to bucket-A's stylistic fingerprinting.

The protocol is operational rather than theoretical: each family has a predictable failure shape, and family-aware verification reduces the surface area of checks. A document known to be Claude-generated should have every DOI verified; a document known to be GPT-generated should have every URL verified; a document known to be Gemini-generated should have every "studies show" or "experts say" attribution chased for specifics; a document known to be DeepSeek-generated should be checked for language-mixing residue; a document known to be Llama-generated above 32K context should be audited for long-context confabulation; a document known to be Grok-generated should be audited for tweet-source citations and Musk-X bias.

### Why this happens

Differences in training mixtures, alignment objectives, and post-training data create family-specific blind spots and fabrication styles. Each model's training data distribution and generation tendencies influence the form of its confabulations. Claude's academic training leads to reference-style confabulation; GPT's web-scale training leads to URL construction; Grok's social media focus leads to tweet simulation. The underlying RLHF mechanisms and training data skews force models to fill knowledge gaps using their default structural rhythms.

Causal hypothesis ranked: (1) tokenizer or architecture effects; (2) training-data skew; (3) alignment and safety tuning (models may fill gaps with plausible but false information to avoid refusal); (4) product wrapper effects (search-augmented modes differ from API modes).

### Failure modes (general, across families)

The cross-family failure modes are:

1. Family-specific fabrication shape goes undetected because the reviewer applies a generic check rather than a family-aware check (a Claude DOI fabrication is not caught by a URL fetch; a GPT URL fabrication is not caught by a DOI lookup).
2. Model identity is unknown or undocumented, preventing family-aware verification. The fact-checker treats all AI output uniformly when the failure shapes differ by family.
3. Cross-family check shows divergence but no flag is raised (the same prompt across families produces six different answers; the divergence itself is diagnostic of low confidence in any single answer).
4. Wrapper, version, or tool state is unrecorded, so the failure cannot be attributed to a specific family configuration (Gemini deep-research mode and Gemini search-augmented mode have different hallucination rates; an undifferentiated "Gemini" label loses the information needed to verify).
5. Reasoning-trace contamination is not checked when the model exposes a reasoning trace (DeepSeek-R1, GPT-o1, Claude extended-thinking); incorrect reasoning steps may contradict the final output and the contradiction is itself a verification opportunity.
6. Per-family verification priority is not followed, so the highest-yield checks per family are not run first; the reviewer spends time on low-yield checks while high-yield ones are skipped.

The per-family signatures below provide the operational catalog of family-specific failure shapes.

### Per-family signatures (consolidated from all inputs)

The signatures below are the consolidated synthesis of seven independent deep-research inputs plus the Opus 4.7 expansion. Per-family content distinguishes the families' characteristic fabrication shapes; the worked examples illustrate each shape; the verification priorities tell the reviewer where to look first.

#### Claude (Anthropic)

- Lowest URL hallucination rate among tested families (3.0 to 3.2 percent hallucinated URLs; Penn 2026).
- Hedges appropriately when uncertain, making hallucinations lower-frequency but similar in polish to GPT hallucinations.
- Domain-specific: high non-resolving rate in Healthcare/Medicine (17.4 percent) vs. Mathematics (4.0 percent). Medical citations from Claude require heightened scrutiny.
- Attribution errors: Claude tends to conflate positions held by multiple speakers and attribute them to the most prominent named figure.
- Correction behavior: responds well to self-correction when given verification tools (6.4x improvement with urlhealth).
- **DOI fabrication signature.** Claude overproduces plausible-seeming DOIs (`doi:10.1038/s41586-XXXX-NNNNN-N` correctly formatted but resolving to a different paper or to nothing). Fabricates plausible DOIs and article titles in formal academic style. Tends to create whole paper references that look real but cannot be found.
- Tends to hallucinate "nuanced" but non-existent details, often creating plausible-sounding but ultimately false elaborations or qualifications.
- Invents non-existent ethical guidelines or legal statutes to justify refusing a prompt it does not understand.
- Refuses on contested ground where other families confabulate; the refusal pattern is itself a signature.
- Lower polished quote-smoothing or evidential over-compression than GPT-4o.

**Verification priority for Claude output:** check Healthcare/Medical citations first; verify every DOI by resolving via doi.org; audit ethical-guideline citations and legal-statute citations for invention.

#### GPT-4o / GPT-4.1 / GPT-5 / GPT-5.5 (OpenAI)

- URL hallucination rate 5.4 to 8.8 percent for search-augmented models; notably, ALL non-resolving URLs from these models are hallucinated (zero stale fraction), indicating URL generation from parametric memory rather than retrieval (Penn 2026).
- Confident wrong specifics (error pattern 4c) is highest here. MIT research (cited in Claritybot 2026): models are 34 percent more likely to use confident language when generating incorrect information.
- Hallucination rate varies by topic: 18.7 percent on legal queries, 15.6 percent on medical queries (Claritybot 2026, citing SuprMind 2026).
- o-series specific: displays explicit uncertainty hedges in text, but the hedge language underestimates the actual error rate. "I should note there is some uncertainty" does not tell you which specific claims are wrong.
- **URL fabrication signature.** URLs on real domains that 404 (`nytimes.com/2024/03/article-that-never-existed`). Invents URLs on real domains. The domain is real; the path is fabricated.
- Tends to hallucinate plausible-sounding citations, names of researchers, or specific statistics that do not exist, often with a high degree of confidence.
- High polish plus guess-prone specificity and fabricated supporting detail under pressure.
- **Perfect-markdown-timeline signature.** Invents a flawless three-point historical timeline with perfect markdown formatting, but the dates are fabricated.
- Generates highly structured, sequential fictions.
- Per Damien Charlotin's database, over 1,455 sanctioned legal cases involve AI-fabricated citations as of 2025, with GPT family heavily represented.

**Verification priority for GPT output:** check legal and medical queries first; assume any non-resolving URL is hallucinated; verify every URL by attempting resolution; rigidly verify chronological timelines, bulleted lists, and statistical data tables.

#### Gemini (Google)

- Deep research mode: 13.3 percent hallucinated URL rate (highest of any model tested), despite high citation volume and strong overall quality scores.
- Search-augmented modes: 4.6 to 4.8 percent hallucination rate (comparable to Claude).
- Best response to self-correction: 79x improvement with urlhealth, achieving 0.1 percent hallucination after correction.
- Domain variation: consistent low non-resolving rates (2.5 to 10.2 percent across fields), but Healthcare/Medicine is problematic at 5.3 percent.
- Hallucination signature: Gemini deep-research mode may blend URL patterns from retrieved pages to produce plausible but non-existent addresses.
- **Vague attribution signature.** Drifts under reasoning load to vague "studies show" or "experts say" assertions without identifiers, making them hard to verify but not easily falsifiable.
- Generates vibrant but fabricated examples or scenarios that fit a narrative but lack factual basis.
- Search wrapper source problems, including fabricated or copied citations, despite stronger benchmarked factuality in some settings.
- Secondary-indication invention under reasoning (Claude exec): Wegovy multi-family stress test revealed Gemini fabricating secondary off-label indications.

**Verification priority for Gemini output:** apply URL verification to all citations; flag every vague attribution ("studies show," "experts say," "research indicates") for specific-source verification; in deep-research mode, audit URLs aggressively.

#### Llama (Meta)

- Higher rate of bold factual errors with lower hedging. Llama asserts incorrectly more often than Claude or GPT but hedges the assertion less, making the error easier to spot.
- Entity name errors (4d) are more pronounced in smaller Llama models (8B range).
- Limited source grounding in base models; RAG-extended versions reduce hallucination substantially.
- **Long-context fabrication signature.** Above 32K context length (approximate threshold per RIKER benchmark, Claude exec, flagged for verification by Opus expansion): factual confabulation increases substantially. The threshold figure should be verified during synthesis.
- May hallucinate technical details or code snippets that are syntactically correct but functionally flawed or non-existent.
- Hallucinates statistics with precise-seeming numbers (for example "47.3 percent") that are baseless.
- Fabricates above 32K context per RIKER (Claude exec).

**Verification priority for Llama output:** check entity names; verify all specific statistics; audit confabulation risk in long-context analysis (above 32K tokens approximate threshold); for code, verify functional correctness rather than syntactic plausibility.

#### DeepSeek (V2, V3, R1)

- Stylometrically classified as OpenAI-like by Copyleaks; hallucination patterns are similarly GPT-like.
- Reasoning trace contamination is a unique failure mode: when reasoning traces are exposed, they may contain incorrect reasoning steps that contradict the final output.
- V3 specifically shows population-level fabrications on historical statistics from Chinese sources, reflecting training data composition.
- **Language-mixing signature.** Language-mixing under reasoning load: reasoning trace contains Chinese characters that the final output may or may not retain. DeepSeek-R1 extended-thinking output may include "我们需要考虑" in a primarily English response.
- Hallucinates heavily when translating technical logic into natural language.
- Invents highly plausible English-language academic paper titles and author attributions to support a coding decision.

**Verification priority for DeepSeek output:** check for language-mixing residue (Chinese characters in primarily-English output); rigidly verify English-language academic paper titles and author attributions against Google Scholar; if reasoning trace is exposed, audit reasoning steps against final output for contradiction.

#### Grok (xAI)

- May hallucinate humorous or irreverent "facts" that align with its persona but are factually incorrect.
- **Tweet fabrication signature.** May fabricate social media posts or tweets as sources, leveraging its platform-aware persona.
- Search-centric outputs were citation-riskier earlier than recent reasoning variants.
- Grok 4 uses Elon Musk's X posts as a source when answering questions (Mashable 2026 documentation).

**Verification priority for Grok output:** verify social media post citations against the live platform; check for X/Musk-source bias; cross-check humorous or irreverent claims against authoritative sources.

### Concrete examples in context

1. *Manus AI example for Claude.* Tends to hallucinate "nuanced" but non-existent details, often creating plausible-sounding but ultimately false elaborations or qualifications.

2. *Manus AI example for GPT.* Tends to hallucinate plausible-sounding citations, names of researchers, or specific statistics that do not exist, often with a high degree of confidence.

3. *Manus AI example for Gemini.* Tends to hallucinate "vibrant" but fabricated examples or scenarios that fit a narrative but lack factual basis.

4. *Manus AI example for Llama.* May hallucinate technical details or code snippets that are syntactically correct but functionally flawed or non-existent.

5. *Manus AI example for Grok.* May hallucinate humorous or irreverent "facts" that align with its persona but are factually incorrect.

6. *Grok worked example.* A draft with strong Claude-family hedging and participial patterns also contains several citations to non-existent think-tank reports on niche regulation. The style fingerprint raises prior probability that the citations require extra verification. (Cross-reference: A1 stylistic fingerprinting.)

7. *Gemini example for Claude.* Claude invents a non-existent ethical guideline or legal statute to justify refusing a prompt it does not understand. The refusal pattern carries fabricated reasoning.

8. *Gemini example for GPT.* GPT invents a flawless three-point historical timeline with perfect markdown formatting, but the dates are fabricated. The polish is the camouflage.

9. *Gemini example for DeepSeek.* DeepSeek invents a highly plausible English-language academic paper title and author attribution to support a coding decision.

10. *Claude Opus 4.7 expansion example for Claude.* "According to Smith et al. 2023, doi:10.1038/s41586-2023-12345-6, ..." DOI resolves to a different paper. The format is correct; the content is wrong.

11. *Claude Opus 4.7 expansion example for GPT.* "https://nytimes.com/2024/05/15/business/tech-merger-analysis ..." URL returns 404. The domain is real; the path is fabricated.

12. *Claude Opus 4.7 expansion example for Gemini.* "Research indicates that 30 percent of teams experience this issue." No source named.

13. *Claude Opus 4.7 expansion example for DeepSeek.* DeepSeek-R1 extended-thinking output: "我们需要考虑..." (Chinese characters in a primarily English response).

14. *Claude Opus 4.7 expansion example for Llama.* Llama on a 40K-token document analysis: confidently states facts not in the document. The context window has exceeded the model's reliable retrieval range; confabulation fills the gap.

15. *Claude exec canonical worked example.* Wegovy multi-family stress test. The canonical multi-family fact-checking stress test from the Claude exec asked six families the same question about Wegovy (semaglutide) indications. Family profiles emerged: Claude refused on contested off-label indications; GPT confabulated with plausible URLs and case citations; Gemini drifted under reasoning with secondary-indication invention (fabricating off-label uses with no clinical evidence); Llama fabricated above 32K context (when the prompt included long surrounding documentation); DeepSeek language-mixed in reasoning trace; Grok cited X posts. The same prompt produced six different failure shapes, each diagnostic of the family.

### Step-by-step procedure for tool-specific verification

1. Identify which model generated the content (if known from workflow documentation). Record model family, precise version, wrapper, and whether search or tools were enabled.
2. Apply the appropriate priority check:
   - Claude: check Healthcare/Medical citations; verify every DOI by resolving via doi.org; audit ethical-guideline and legal-statute invocations.
   - GPT: check legal and medical queries; assume any non-resolving URL is hallucinated; verify every URL; rigidly verify chronological timelines, bulleted lists, and statistical data tables.
   - Gemini deep-research: apply URL verification to all citations; flag every vague attribution.
   - Llama: check entity names; verify all specific statistics; audit confabulation risk in long-context analysis (above 32K tokens approximate).
   - DeepSeek: check for language-mixing; rigidly verify English-language academic paper titles and author attributions against Google Scholar.
   - Grok: verify social media post citations; check for X/Musk-source bias.
3. For unknown model: apply the general citation verification procedure from v1.1.0 Section 4f plus the URL classification procedure from C1-URLROT-001.
4. Cross-reference with the A1 stylistic fingerprint (synthesis-content-quality) to confirm family identification.
5. Test failure mode classes separately: unsupported guessing, source fabrication, citation mismatch, paraphrase drift, and position drift.
6. Catalogue the hallucination's format (DOI, URL, person, statistic, generic attribution). Cross-reference with known family signatures. Verify accordingly (DOI lookup, URL fetch, etc.).
7. Apply family-specific remediation: DOI lookup for Claude; URL resolution for GPT; specific-source demand for Gemini; language-purity for DeepSeek; long-context-fabrication audit for Llama.
8. Record the model and version as required metadata. Per ChatGPT input, claims about "Gemini" or "GPT" without the surrounding surface, app, API, search mode, and date are often underspecified; v2.0 should make model version, wrapper, and tool state required metadata whenever a reviewer records a pattern or failure.

### Sources

Rao, Wong, Callison-Burch (2026) arXiv:2604.03173 (per-family hallucination percentages); Claritybot journalism guide 2026; AI Multiple benchmark report Jan 2026 (15 to 52 percent hallucination across 37 LLMs); Copyleaks 2025 (DeepSeek stylometric classification); RIKER benchmark arxiv 2603.08274 (Llama long-context fabrication; threshold figure flagged for synthesis verification); Mashable 2026 (Grok X-post source bias); Sharma et al. arxiv 2310.13548 (sycophancy across families); academic papers on LLM hallucination detection and mitigation; comparative empirical studies of multiple model outputs on identical prompts; Claude exec 2026-05-18 (Wegovy canonical stress test).

### Signal strength, base rate, detection difficulty, false-positive risk

- **Signal strength.** MED (pattern knowledge helps prioritize; does not replace individual verification). HIGH when a family-specific signature is identified.
- **Base rate.** Varies significantly by model, prompt, and domain. Penn 2026 percentages provide the empirical baseline; AI Multiple 15 to 52 percent range across 37 LLMs provides the upper bound.
- **Detection difficulty.** Medium. Requires familiarity with different models' common failure modes.
- **False positive risk.** MED. Individual hallucinations do not follow family patterns consistently. These are specific, identifiable patterns when present, but presence does not predict every instance.

### Remediation

Cross-verify all factual claims with independent, human-authored sources. Be aware of the specific hallucination tendencies of the LLM being used. Implement self-correction mechanisms (for example asking the model to justify its claims). Apply family-specific verification: DOI lookup for Claude; URL resolution for GPT; specific-source demand for Gemini; language-purity for DeepSeek; long-context-fabrication audit for Llama. Delete the hallucination and prompt a different model family for cross-verification.

For editorial workflow, the family-specific verification can be packaged as a checklist per family. A fact-checker who knows the model family can run a targeted 10-minute check that catches the highest-probability failures; without family knowledge, the general protocol takes 30 to 60 minutes and may miss family-specific shapes.

### Era status

Active. Constantly evolving as models are updated and fine-tuned. Per ChatGPT input, claims about "Gemini" or "GPT" without the surrounding surface, app, API, search mode, and date are often underspecified; v2.0 makes model version, wrapper, and tool state required metadata whenever a reviewer records a pattern or failure.

### Cross-references

- C1-URLROT-001: per-family URL fabrication patterns determine the URL classifications to expect. GPT's URL fabrication signature concentrates HALLUCINATED with real-domain camouflage; Claude's lower URL hallucination rate spreads more evenly across STALE and HALLUCINATED.
- C1-SYNTH-001: per-family synthetic-source generation patterns (DeepSeek fake-journal citations, Claude synthetic-expert credentials, Gemini synthetic-statistic attributions) shape what synthetic sources to expect from which family.
- C1-LAUNDER-001: per-family laundering signatures (Gemini's vague attribution often serves as a laundering intermediate node; GPT's confident specifics often serve as a fabricated upstream).
- C1-NESTED-001: per-family nested-attribution flattening varies (Claude tends to preserve more layers; GPT compresses more aggressively).
- C1-COMPOSITE-001: per-family composite-quote signatures vary (GPT's high-polish composite quotes are hardest to detect; Llama's are more obvious due to lower fluency above 32K context).
- C1-POSSHIFT-001: per-family position-shifting biases vary (Claude's constitutional-AI training produces "balanced" position-shifting toward the middle; GPT's training on opinion content produces stronger position imports).
- v1.1.0 4f (Hallucinated Citations): the per-family signatures here provide the operational shape of the v1.1.0 single-bucket failure mode; family identification reduces the verification surface area.
- synthesis-content-quality A1 (Model-Family Fingerprinting): the stylistic signatures in A1 and the fabrication signatures here are parallel; identifying one helps identify the other; cross-referencing both improves family identification confidence.

---

## Production-incident archive (cross-protocol reference)

The following 2025-2026 incidents are referenced across multiple C1 protocols. They are preserved here as a quick-reference archive; full detail lives in `references/production-incident-archive.md`.

- **Mostafavi sanction (2025).** Court sanction for legal filings citing fabricated cases. Claude exec gives $10,000 figure; Opus expansion flagged the specific dollar amount and date for verification noting multiple Mostafavi cases exist and disambiguation may be needed. Cross-validated with CalMatters September 2025 coverage per Claude exec bibliography. Relevant to: C1-URLROT-001, C1-LAUNDER-001, C1-TOOLHALL-001 (GPT URL fabrication).
- **Goldberg Segalla sanction (2025).** Larger sanction for similar AI-fabricated-citation pattern. Claude exec gives $60,000 figure; Opus expansion flagged the specific details for verification. Per Damien Charlotin's database (cited in Claude exec, Opus expansion flagged the specific database existence for verification), over 1,455 sanctioned legal cases involve AI-fabricated citations as of 2025. The case is referenced as the Goldberg Segalla CHA sanction in Claude exec bibliography, December 2025. Relevant to: C1-URLROT-001, C1-SYNTH-001, C1-LAUNDER-001, C1-TOOLHALL-001.
- **Chicago Sun-Times summer reading list (2025).** Newspaper published a summer reading list with multiple books that did not exist; the books had plausible titles by real authors but were AI fabrications. Cross-validated by NPR May 2025 coverage per Claude exec bibliography. Relevant to: C1-SYNTH-001, C1-TOOLHALL-001.
- **Springer "Mastering Machine Learning" book (2025).** A Springer-published book on machine learning that contained AI-fabricated citations to non-existent papers, with two-thirds of references fabricated. Retraction Watch April 2025 coverage. Relevant to: C1-SYNTH-001, C1-LAUNDER-001.
- **BBC/EBU 45 percent significant-issues rate (2025).** BBC/European Broadcasting Union News Integrity report (October 2025) found that 45 percent of AI-generated responses to news questions contained significant issues (factual errors, missing context, or attribution problems). Relevant to: all C1 protocols as baseline prevalence anchor.
- **Topaz et al. May 2026 Lancet letter.** One in 277 PubMed papers in 2026 referenced a fabricated paper; twelve-fold rise from 2023 per Claude exec; sixfold rise from 2023 to 2025 per Perplexity citation of the same study. STAT News coverage 2026-05-06. Venue flagged for verification by Opus expansion. Relevant to: C1-SYNTH-001, C1-LAUNDER-001.
- **Damien Charlotin's AI Hallucination Cases Database.** Over 1,455 sanctioned legal cases involve AI-fabricated citations as of 2025. Relevant to: C1-URLROT-001, C1-TOOLHALL-001.
- **Stanford RegLab Magesh et al. June 2024.** 17 to 33 percent legal-AI hallucination rates with RAG. Relevant to: C1-URLROT-001, C1-SYNTH-001, C1-TOOLHALL-001.
- **Mata v. Avianca (2023).** Attorney sanctioned for AI-generated legal brief with fabricated case citations. Established the legal consequence baseline. Relevant to: C1-URLROT-001, C1-TOOLHALL-001.
- **Tsinghua ICLR paper.** Withdrawn after AI-generated references were identified by reviewers. Relevant to: C1-SYNTH-001.
- **MAHA Report (2025).** White House chronic disease report contained multiple incorrect citations suspected AI-generated; widely publicized. Relevant to: C1-SYNTH-001, C1-LAUNDER-001.
- **Megalopolis trailer controversy (2024).** Involved fabricated or misattributed critic quotes. Relevant to: C1-NESTED-001, C1-COMPOSITE-001.
- **Washington Post AI-generated podcast scripts (2026).** Found fabricated and misattributed quotations in production testing. Relevant to: C1-NESTED-001, C1-COMPOSITE-001, C1-PARAPH-001.
- **Nieman Lab Margaux Blanchard/Victoria Goldiee February 2026.** Synthetic-byline contamination case. Relevant to: C1-SYNTH-001.
- **Google AI Overviews 2025 year-bug.** Wrong year framing in AI-generated overviews; canonical 4a example per Claude exec. Relevant to: v1.1.0 4a (cross-reference; not C1-specific).

---

## Em-dash audit

This file is self-audited for em-dash use, per A3-SS-001 (em-dashes in articles) and A3-SR-005 (em-dashes in social posts) of the synthesis-content-quality v4.0 catalog. The audit applies to the U+2014 character only; en-dashes in numeric ranges (5-18 percent, 30 to 40 percent) and hyphens in compounds (URL-rot, multi-source) are not in scope.

Result: zero em-dashes in this file.

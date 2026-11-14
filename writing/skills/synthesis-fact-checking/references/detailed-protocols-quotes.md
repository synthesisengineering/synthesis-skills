# Detailed protocols, part 1: quotes and framing

Part 1 of three, split from [detailed-protocols.md](detailed-protocols.md) so each part can be read in one pass. The text is verbatim. Every protocol follows the shared structure described in the index under "How to use this file", and the index's em-dash audit covers this part.

Contents:
- C1-NESTED-001: second-party and third-party quote handling (nested attribution flattening)
- C1-PARAPH-001: paraphrase boundary drift (bidirectional audit)
- C1-COMPOSITE-001: composite quotes
- C1-POSSHIFT-001: position-shifting (aggregate framing drift)

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

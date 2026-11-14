# Detailed protocols, part 2: translations, URLs and sources

Part 2 of three, split from [detailed-protocols.md](detailed-protocols.md) so each part can be read in one pass. The text is verbatim. Every protocol follows the shared structure described in the index under "How to use this file", and the index's em-dash audit covers this part.

Contents:
- C1-TRANS-001: source-translation drift
- C1-URLROT-001: URL rot vs. hallucination, with the six-category taxonomy
- C1-SYNTH-001: AI-generated synthetic sources
- C1-LAUNDER-001: citation laundering chains

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

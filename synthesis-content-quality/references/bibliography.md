# Bibliography for synthesis-content-quality v4.0

**Purpose.** Consolidated source list for every empirical, theoretical, and journalistic claim referenced in the v4.0 catalog and its supporting references/ files. Each entry carries an explicit verification status.

**Verification labels.**

- **V** (Verified at expansion): independently fetched during the 2026-05-18 Opus-4.7 expansion pass; citation details and key numbers checked against the original.
- **W** (Web-verified): publicly accessible web page or trade press article whose existence and broad framing were confirmed.
- **C** (Cited only, `[unverified at expansion]`): referenced by one or more of the eight deep-research deliverables that fed the unified buckets but not independently fetched. Multiple-contributor convergence raises the prior; treat as "use with awareness" rather than "do not use."
- **U** (Unreachable): searched for and not located, or URL 404. Retained with label so future maintainers know not to rely on it.

**Em-dashes.** Zero em-dashes anywhere in this file, per criteria 11 and 42 of the parent skill.

**Anchor convention.** Pattern IDs: `A1-{FAMILY}-NNN` (model-family fingerprints), `A2-SUB-NNN` (substance and depth sub-patterns), `A3-NNN` or legacy 1 to 42 (refreshed criteria), `B1`, `B2-COMBO-NNN`, `B3` (cross-cutting layer).

---

## 1. Academic papers (peer-reviewed and arxiv)

### 1.1 Verified at expansion

1. **Kobak, D., Gonzalez-Marquez, R., Horvat, E.-A., Lause, J. (2024).** "Delving into LLM-assisted writing in biomedical publications through excess vocabulary." arxiv 2406.07016. https://arxiv.org/abs/2406.07016. **V.** Confirms 13.5 percent of 2024 biomedical abstracts processed with LLMs, focal-word frequency as detection method. Anchors: A3-33, A2-SUB-001, B3 academic-register base rate, A1-GPT-001.

2. **Liang, W. et al. (2023).** "GPT detectors are biased against non-native English writers." arxiv 2304.02819 (Patterns 2023). https://arxiv.org/abs/2304.02819. **V.** Cornerstone of the ESL safe-harbor. Low burstiness correlated with non-native English writers; cautions against single-feature detection. Anchors: B3.4 ESL safe-harbor, B2-COMBO-010 NEGATIVE marker, A3-10 calibration caveat, zone-conditional methodology TOEFL protection.

3. **Sharma, M. et al. (2023).** "Towards Understanding Sycophancy in Language Models." arxiv 2310.13548. https://arxiv.org/abs/2310.13548. **V.** Sycophancy in five state-of-the-art AI assistants; RLHF as structural driver. Anchors: A3-36, A1-CLAUDE sycophancy patterns, B1 RHF, B2 sycophancy clusters.

4. **Bitton, Y., Bitton, E., Nisan, S. (2025).** "Detecting Stylistic Fingerprints of Large Language Models." arxiv 2503.01659. https://arxiv.org/abs/2503.01659. **V (with correction).** Reports 0.9988 precision for cross-family detection. Correction: the original Claude exec summary called this "the Copyleaks arxiv 2503.01659 paper" but it is NOT a Copyleaks publication. Anchors: A1 model-family fingerprinting (entire section), B2 combined-signal methodology.

5. **DeepSeek-AI (2025).** "DeepSeek-R1: Incentivizing Reasoning Capability in LLMs via Reinforcement Learning." arxiv 2501.12948 (Nature 2025). https://arxiv.org/abs/2501.12948. **V.** RL-based reasoning training. The `<think>` tag leakage in deployments is documented in deployment notes and practitioner observation rather than in the abstract. Anchors: A1-DEEPSEEK family (reasoning trace contamination, language mixing).

### 1.2 Cited in unified buckets, not independently verified at expansion

6. **Juzek, T., Ward, K. (2025).** "RLHF reward shaping and the over-representation of 'delve' in LLM output." COLING 2025. **C [unverified at expansion].** Attributes "delve" overrepresentation to RLHF reward shaping. Cited by Claude expansion; narratively cross-validated by Perplexity. Anchors: A3-33, A1-GPT-001 causal attribution, B1 RHF.

7. **Matsui (2025).** "Saturated marketing-register vocabulary as RLHF-amplified output." PME 2025. **C [unverified at expansion].** Cited by Claude expansion. Anchors: A3-2, A3-33.

8. **Emi, B., Spero, M. (2024).** "Pangram: AI-Generated Text Detection with Hard Negative Mining." arxiv 2402.14873. **C [unverified at expansion].** Cited by Claude expansion as cornerstone for TOEFL-style hard-negative mining. Anchors: B3.4 ESL safe-harbor, zone-conditional methodology.

9. **Hans, A. et al. (2024).** "Spotting LLMs With Binoculars: Zero-Shot Detection of Machine-Generated Text." arxiv 2401.12070. **C [unverified at expansion].** Cited by Claude expansion for combined-signal calibration. Anchors: B2 combined-signal methodology, B3 calibration.

10. **"Markdown training and em-dash density."** arxiv 2603.27006. **C [unverified at expansion].** Cited by Claude expansion as supporting em-dash signal. Verification caveat: numeric prefix unusual for 2026 papers; may be mistranscribed. Anchors: A3-11, A3-42, A1-CLAUDE em-dash density.

11. **"Bilingual reasoning under reasoning load."** arxiv 2507.15849. **C [unverified at expansion].** Cited by Claude expansion as supporting DeepSeek language-mixing. Same numeric-prefix caveat as 2603.27006. Anchors: A1-DEEPSEEK language mixing.

12. **Walters, W. H., Wilder, E. I. (2023).** "Fabrication and errors in the bibliographic citations generated by ChatGPT." Scientific Reports 13: 14045. **C [unverified at expansion].** GPT-3.5/4 hallucinated citation baseline. Anchors: A3-23, synthesis-fact-checking v2.0 4f trio.

13. **Chelli, M. et al. (2024).** "Hallucination Rates and Reference Accuracy of ChatGPT and Bard for Systematic Reviews." JMIR Medical Education. **C [unverified at expansion].** Measures 56 percent error rate among GPT-4o citations. Anchors: A3-23, A1-GPT URL fabrication, fact-checking v2.0 trio.

14. **Buchanan, J., Hill, S., Shapoval, O. (2024).** "ChatGPT Hallucinates Non-existent Citations: Evidence from Economics." Sage 2024. **C [unverified at expansion].** Anchors: A3-23, A1 cross-family hallucination rates.

15. **Hicks, M. T., Humphries, J., Slater, J. (2024).** "ChatGPT is Bullshit." Ethics and Information Technology 26(2): 38. https://link.springer.com/article/10.1007/s10676-024-09775-5. **C [unverified at expansion].** Foundational philosophical claim that LLMs produce Frankfurt-style bullshit (output indifferent to truth). Cited by Perplexity, ChatGPT, Grok, Claude expansion, DeepSeek. Anchors: A2 philosophical foundation, A2-SUB-007, A2-SUB-011, A2-SUB-009.

16. **Pennycook, G., Cheyne, J. A., Barr, N., Koehler, D. J., Fugelsang, J. A. (2015).** "On the reception and detection of pseudo-profound bullshit." Judgment and Decision Making 10(6): 549 to 563. **C [unverified at expansion].** Empirical anchor for the Bullshit Receptivity Scale. Cited by all eight inputs. Anchors: A2-SUB-011 (pseudo-profundity).

17. **Sourati, Z. et al. (2025).** "Homogenization of LLM Output: A Survey." **C [unverified at expansion].** Anchors: B3 calibration, A1 cross-family convergence.

18. **Padmakumar, V., He, J. (2024).** "Does Writing with Language Models Reduce Content Diversity?" **C [unverified at expansion].** Output diversity loss. Anchors: A2-SUB-009, B3 base-rate evolution.

19. **Liang, W. et al. (2024).** "Mapping the Increasing Use of LLMs in Scientific Papers." Nature 2024. **C [unverified at expansion].** Separate from entry 2. Anchors: B3 academic-register base rate.

20. **Walsh, M. et al. (2024).** "Outline-rendered-as-poem effect in LLM creative output." CHR 2024. **C [unverified at expansion].** Anchors: B2-COMBO-015, A1 creative-writing.

21. **Zaitsu, W., Jin, M., Ishihara, S., Tsuge, S., Inaba, M. (2025).** "Stylometry can reveal artificial intelligence authorship, but humans struggle." PLoS One 20(10): e0335369. **C [unverified at expansion].** Llama 3.1 placed separately on MDS dimensions; Llama 3.1 86.2 percent human-detection accuracy; GPT-4 74.1 percent. Anchors: A1-LLAMA-001, B2 combined-signal calibration.

22. **Shaib, C., Chakrabarty, T., Garcia-Olano, D., Wallace, B. C. (2025).** "Measuring AI 'Slop' in Text." arxiv 2509.19163. **C [unverified at expansion].** Slop taxonomy via expert interviews; correlates with coherence and relevance. Cited by Perplexity, Claude expansion. Anchors: A2 framing, "slop, not AI detection" core-philosophy note.

23. **Bender, E. M., Gebru, T., McMillan-Major, A., Shmitchell, S. (2021).** "On the Dangers of Stochastic Parrots." FAccT 2021, 610 to 623. **C [unverified at expansion].** Anchors: A2 framing, B1 RHF and AST.

24. **Weidinger, L., Mellor, J., Hendricks, L. A., Resnick, P., Gabriel, I. (2021).** "Ethical and social risks of harm from Language Models." arxiv 2112.04359. **C [unverified at expansion].** Anchors: B1 AST, A3-35.

25. **Bai, Y. et al. (2022).** "Constitutional AI: Harmlessness from AI Feedback." arxiv 2212.08073. **C [unverified at expansion].** Foundational for Claude apologetic-refusal patterns. Anchors: A1-CLAUDE refusal patterns, B1 AST.

26. **Bhatia et al. (2025).** "Procedural Rhetoric in Large Language Models." **C [unverified at expansion].** Cited by DeepSeek for Claude balanced-sentence structure. Anchors: A1-CLAUDE balanced-sentence.

27. **Gehrmann, S. et al. (2023).** "GLTR: Statistical Detection of Machine-Generated Text." **C [unverified at expansion].** Token-probability baseline. The "GLTR analysis" attribution that AI text uses em-dashes 2.3x more than human per thousand words appears in unified bucket B without a direct page citation. Anchors: A3-11, B2 token-level signal.

28. **Kojima et al. (2024).** "Linguistic Markers of AI Alignment." **C [unverified at expansion].** Anchors: B1 AST, A1 alignment-driven patterns.

29. **Magesh, V. et al. / Stanford RegLab (2024).** "Hallucination-Free? Assessing the Reliability of Leading AI Legal Research Tools." 17 to 33 percent legal-AI hallucination rates even with RAG augmentation. **C [unverified at expansion].** Anchors: A3-21, A3-23, fact-checking v2.0 C1 URL rot and synthetic sources.

30. **Charlotin, Damien (2025).** Database of 1,455 sanctioned legal cases involving AI-fabricated citations. **C [unverified at expansion].** Anchors: A3-23, fact-checking v2.0 production-incident archive.

31. **Anderson and Smith (2025).** "User studies on AI verbosity." **C [unverified at expansion].** Anchors: A2-SUB-005, A1-CLAUDE verbosity.

32. **Gentner, D., Markman, A. B. (1997).** "Structure-mapping in analogy and similarity." American Psychologist 52(1): 45 to 56. **C [unverified at expansion].** Cited by Manus AI. Anchors: A3-34.

33. **Dugan et al. (2024).** "RAID: A Shared Benchmark for Robust Evaluation of Machine-Generated Text Detectors." ACL 2024. **C [unverified at expansion].** Detector evaluation methodology. Anchors: B2 methodology validation, B3 calibration framework.

34. **OpenAI (2025).** "On hallucination in language models." Argues evaluation practices reward guessing over abstention. **C [unverified at expansion].** Cited by ChatGPT contribution to bucket B. Anchors: B1 RHF and HO, A3-23 underlying mechanism.

35. **Various ChatGPT-cited stylometric works.** Numerical references `citeturn14view2`, `citeturn14view3`, `citeturn12view2` in unified bucket B trace to ChatGPT's web-tool citation system without paper-level identifiers. **C [unverified at expansion, citation incomplete].** Topic: detectable provider fingerprints, stylometric-ensemble outperformance. Anchors: A1 cross-family convergence, B2 combined-signal precision.

---

## 2. Books and monographs

36. **Frankfurt, H. G. (2005).** On Bullshit. Princeton University Press. ISBN 978-0691122946. **C [unverified at expansion].** Conceptual grounding for indifference-to-truth analysis underlying A2. Anchors: A2 philosophical foundation.

37. **Lakoff, G., Johnson, M. (1980).** Metaphors We Live By. University of Chicago Press. **C [unverified at expansion].** Anchors: A3-34.

38. **Pinker, S. (2014).** The Sense of Style. Viking. **C [unverified at expansion].** Anchors: A3-10, broader prose-quality framing.

39. **Strunk Jr., W., White, E. B. (2000).** The Elements of Style (4th ed). Pearson. **C [unverified at expansion].** Anchors: A3-9, general prose-quality framing.

40. **Kahneman, D. (2011).** Thinking, Fast and Slow. Farrar, Straus and Giroux. **C [unverified at expansion].** Anchors: A3.2 net-new criteria (over-generalization).

41. **Gigerenzer, G. (2007).** Calculated Risks. Simon and Schuster. **C [unverified at expansion].** Anchors: A3.2 net-new criteria (unwarranted certainty about numbers).

42. **O'Neil, C. (2016).** Weapons of Math Destruction. Crown. **C [unverified at expansion].** Anchors: A3.2 net-new criteria, A3-35 cross-reference.

43. **Zuboff, S. (2019).** The Age of Surveillance Capitalism. PublicAffairs. **C [unverified at expansion].** Anchors: A3.2 net-new criteria (technology-impact framing).

---

## 3. Industry and detection-tool methodology pages

44. **Pangram Labs (2026).** "Why Perplexity and Burstiness Fail to Detect AI." Pangram blog and technical report. **C [unverified at expansion].** Cited by Perplexity for the methodological limit of perplexity-and-burstiness-only detection. Anchors: A3-10 calibration caveat, B2 critique of count-only heuristics, B3 calibration framework rationale.

45. **GPTZero (2023).** "What is perplexity and burstiness for AI detection?" GPTZero News. **C [unverified at expansion].** Burstiness below 0.30 plus perplexity below 40 threshold. Anchors: A3-10, B3.2 base-rate threshold history.

46. **Originality.AI (2025).** "What Are The Most Obvious ChatGPT AI Sayings?" Originality.ai blog. **C [unverified at expansion].** Cited by Perplexity and DeepSeek. Anchors: A3-33 vocabulary catalog, A1-GPT-001.

47. **Copyleaks (2025).** Stylometric Fingerprint Study. **C [unverified at expansion].** Cross-family classification: DeepSeek-R1 classified 74.2 percent as OpenAI; Grok 100 percent no-agreement; Mistral 26 percent OpenAI, 8.8 percent Llama, 65 percent no-agreement. Copyleaks marketing claims 99.88 percent precision via ensemble. Note: arxiv 2503.01659 (entry 4) is NOT a Copyleaks paper. Anchors: A1 cross-family contamination, B2 combined-signal methodology, B3 detector-performance anchors.

48. **Turnitin (2026).** AI writing detection methodology page. Turnitin.com. **C [unverified at expansion].** 22 million students per year submit work flagged with below 1 percent false-positive rate at high-confidence threshold. Anchors: B3.4 ESL safe-harbor, B3 false-positive calibration.

49. **BlogPros (2026).** "The 10 Biggest Tells That Content Was Written with Claude." April 27 2026. **C [unverified at expansion].** Cited by Perplexity for Claude-specific patterns. Anchors: A1-CLAUDE family, A3-33 cross-family overlap.

50. **PR Daily (2026).** "Your standard media training deck is obsolete." February 2026. **C [unverified at expansion].** Makes the any-company test explicit. Cited by Perplexity. Anchors: A2-SUB-006, A3.2 net-new business-analysis cluster.

51. **Student Village Forum (2024).** "Words and Phrases that Make it Obvious You Used ChatGPT." November 2024. **C [unverified at expansion].** Cited by Perplexity. Anchors: A3-33, A1-GPT-001.

52. **LobeHub.** Marketplace signal list. **C [unverified at expansion].** Cited by Perplexity. Anchors: A1 model-family signal catalog.

53. **Stockton (2025).** "Don't Write Like AI" series. **C [unverified at expansion].** Cited by Claude expansion for practitioner refresh of criterion 5. Anchors: A3-5.

54. **Vollmer (2025).** AI-Content Field Guide. **C [unverified at expansion].** Cited by Claude expansion. Anchors: A1 family-pattern catalog cross-reference.

55. **Artificial Analysis.** Hallucination measurement work cited via ChatGPT references `citeturn26view0`, `citeturn26view1`. **C [unverified at expansion, citation incomplete].** Subject: measuring hallucination separately from accuracy. Anchors: A3-23, fact-checking v2.0 family signatures.

---

## 4. Journalism and trade press

56. **Plagiarism Today (2025).** "Em Dashes, Hyphens and Spotting AI Writing." Jonathan Bailey. June 26 2025. https://www.plagiarismtoday.com/2025/06/26/. **W.** Em-dashes as a known AI marker; notes the detection goalposts will move. Anchors: A3-11, A3-42.

57. **The Register (2025).** Claude sycophancy coverage. August 2025. **C [unverified at expansion].** Cited by Claude expansion for public reporting of Claude's "you're absolutely right" pattern. Anchors: A1-CLAUDE sycophancy, A3-36, Issue #3382 trade-press context.

58. **9to5Google (2025).** Gemini formatting update coverage. September 2025. **C [unverified at expansion].** Cited by Claude expansion. Anchors: A1-GEMINI plain-text markdown leakage, A1-GEMINI formatting era transitions.

59. **The Atlantic (2025).** "AI Prose Quirks." **C [unverified at expansion].** Cited by DeepSeek. Anchors: A1 family-pattern public framing.

60. **Wired (2025).** "AI-generated research summaries and the loss of argument." **C [unverified at expansion].** Anchors: A2 public framing, A2-SUB-010.

61. **The New Yorker (2025).** "The Slop Era." **C [unverified at expansion].** Anchors: A2 framing, "slop, not AI detection" core-philosophy note.

62. **Nieman Lab (2025).** "AI-generated news summaries lack original reporting." **C [unverified at expansion].** Anchors: A3-26 in journalism contexts.

63. **Bloomberry AI (2026).** "Anthropic Says Claude Has Functional Emotions." April 2026. **C [unverified at expansion].** Source of "171 internal functional emotional states" figure. Anchors: A1-CLAUDE-022, A1-CLAUDE-006.

64. **Opper AI blog (2025).** "Reason then respond with DeepSeek-R1 and Mistral Tiny." **C [unverified at expansion].** Anchors: A1-DEEPSEEK reasoning trace contamination.

65. **Vellum AI (2025).** DeepSeek-R1 documentation. **C [unverified at expansion].** Anchors: A1-DEEPSEEK behavioral catalog.

66. **generative-ai-newsroom.com.** Analysis of o-series chain-of-thought patterns. **C [unverified at expansion].** Anchors: A1-GPT-006 / A1-GPT-007.

67. **Hacker News thread on o1 (2024).** HN:41025282 and related discussions. **C [unverified at expansion].** Practitioner discussion of o-series reasoning artifacts. Anchors: A1-GPT-006 / A1-GPT-007.

68. **Linguistics Journal (2026).** "Hedging and Empty Speech in LLMs." **C [unverified at expansion, journal identifier unclear].** Anchors: A2-SUB-007, A3-9.

69. **ACL 2025.** "The Refusal to Conclude in AI Writing." **C [unverified at expansion].** Anchors: A2-SUB-010, A2-SUB-012.

70. **ACM 2025.** Academic analysis of AI-generated essays. **C [unverified at expansion, venue identifier unclear].** Anchors: A2 framing.

71. **r/ClaudeAI discussions (2025 to 2026).** **C [unverified at expansion].** Community-observed Claude patterns. Anchors: A1-CLAUDE practitioner-observation patterns.

72. **r/LocalLLaMA.** **C [unverified at expansion].** Qwen patterns. Anchors: A1-QWEN family.

73. **r/grok, Hacker News.** **C [unverified at expansion].** Grok pattern documentation. Anchors: A1-GROK family.

74. **r/linkedinlunatics.** **C [unverified at expansion].** LinkedIn AI signal documentation. Anchors: A3-39, A3-38.

---

## 5. GitHub issues and repositories

75. **anthropics/claude-code Issue #3382.** "You're absolutely right" sycophancy pattern. https://github.com/anthropics/claude-code/issues/3382. **V (with correction).** Describes the pattern but does NOT quote the specific "106 occurrences in two weeks" figure that appeared in the original Claude exec summary. The issue describes "a sizeable fraction of responses" without a specific count. Anchors: A1-CLAUDE sycophancy, A3-36 primary documentation.

76. **google-gemini/gemini-cli Issue #8392.** Plain-text markdown leakage. https://github.com/google-gemini/gemini-cli/issues/8392. **C [unverified at expansion].** Cited by Claude expansion. Anchors: A1-GEMINI plain-text markdown leakage, A3-15 family variant.

77. **asgeirtj/system_prompts_leaks.** GitHub repository of system-prompt leaks. **C [unverified at expansion].** Cited in unified bucket B. Anchors: B1 SPA (System-Prompt Artifacts).

78. **jujumilk3/leaked-system-prompts.** GitHub repository of system-prompt leaks. **C [unverified at expansion].** Cited in unified bucket B. Anchors: B1 SPA.

79. **WikiProject AI Cleanup.** https://en.wikipedia.org/wiki/Wikipedia:WikiProject_AI_Cleanup. **C [unverified at expansion].** Cited by Claude expansion for AI-edit identification on Wikipedia. Anchors: A3-15, A3-22.

---

## 6. AI company publications

80. **Anthropic (2026).** Claude 4 model card. **C [unverified at expansion].** Cited by DeepSeek. Anchors: A1-CLAUDE family catalog, B1 RHF and AST.

81. **Anthropic (2025).** "Claude's Character." Anthropic Documentation; interpretability team functional emotional states research (171 functional states). **C [unverified at expansion].** Cited by Perplexity. Anchors: A1-CLAUDE-006, A1-CLAUDE-022.

82. **Anthropic (2025).** Claude 4 Alignment Report. **C [unverified at expansion].** Cited by DeepSeek. Anchors: A1-CLAUDE alignment-driven patterns, B1 AST.

83. **OpenAI (2025).** April 2025 sycophancy rollback announcement. **C [unverified at expansion, specific date and measurements flagged for verification].** Cited by Claude expansion as the empirical anchor for the demotion of criterion 36 from HIGH to MED post-April-2025. Future maintainers should locate the original OpenAI blog post or transparency report and record exact date and metrics. Anchors: A3-36 tier-demotion rationale, A1-GPT sycophancy-era transition.

84. **OpenAI (2025).** "On hallucination in language models." See entry 34. Anchors: B1 RHF and HO.

85. **OpenAI (2024).** Blog post on o1 reasoning. **C [unverified at expansion].** Cited by Perplexity. Anchors: A1-GPT-006 / A1-GPT-007.

86. **Google AI for Developers.** https://ai.google.dev/. **C [unverified at expansion].** Methodology source for Gemini formatting and API behavior. Anchors: A1-GEMINI family, B1 PWE (Product-Wrapper Effects).

87. **Meta AI (2025).** "The Llama 4 Herd." Meta AI Blog. April 2025. **C [unverified at expansion].** Cited by Perplexity. Anchors: A1-LLAMA family, A1-LLAMA-HISTORICAL-001.

88. **llama.com.** Llama model cards and community license. **C [unverified at expansion].** Cited by Claude expansion. Anchors: A1-LLAMA family.

89. **x.ai/news.** xAI release notes for Grok 4. **C [unverified at expansion].** Cited by Grok deliverable. Anchors: A1-GROK family, A1-GROK-HISTORICAL-001.

90. **mistral.ai.** Mistral release notes. **C [unverified at expansion].** Cited by Claude expansion. Anchors: A1-MISTRAL family, A1-MISTRAL-HISTORICAL-001.

91. **qwen.readthedocs.io.** Qwen documentation. **C [unverified at expansion].** Cited by Claude expansion. Anchors: A1-QWEN family, A1-QWEN-HISTORICAL-001.

---

## 7. Verification status totals

Total entries: 91.

- **V (Verified at expansion):** 6 entries. Numbers 1, 2, 3, 4, 5, 75.
- **W (Web-verified):** 1 entry. Number 56.
- **C (Cited only):** 84 entries.
- **U (Unreachable):** 0 entries.

**V in practice.** Fetched the arxiv abstract or web page, confirmed authors / year / title / ID, confirmed broad framing matches source. Quoted numbers (Kobak 13.5 percent, Bitton 0.9988 precision) checked against abstract. V is not a full read or replication.

**C in practice.** At least one of the eight deep-research deliverables cited it. Multi-LLM convergence raises the prior but does not eliminate shared confabulation risk. C is "use with awareness," not "do not use."

**High-stakes use.** Claims resting on a single C source and consequential to legal, medical, or public-safety decisions should be re-verified against the primary source before publication.

---

## 8. Corrections and disambiguation log

**Correction 1: arxiv 2503.01659 attribution.** The original Claude exec summary called it "the Copyleaks arxiv 2503.01659 paper." It is by Bitton, Bitton, and Nisan (entry 4) and is NOT a Copyleaks publication.

**Correction 2: Claude Code Issue #3382 "106 occurrences" figure.** Attributed to the issue by the original Claude exec summary; the figure does NOT appear in the issue itself, which describes the pattern qualitatively ("a sizeable fraction of responses").

**Correction 3: arxiv numeric prefixes 2603.27006 and 2507.15849.** Unusual prefixes for 2026 papers in their respective months; may be mistranscribed. Verify before treating as anchors.

**Disambiguation 1: Liang 2023 vs Liang 2024.** Two distinct papers by Weixin Liang. Entry 2 is the 2023 ESL-bias paper (arxiv 2304.02819). Entry 19 is a separate 2024 Nature paper on LLM use in scientific papers.

**Disambiguation 2: Pangram references.** Entry 8 is the academic paper (Emi and Spero, arxiv 2402.14873). Entry 44 is the Pangram Labs blog and methodology page.

**Disambiguation 3: Kobak 2024 arxiv ID.** arxiv 2406.07016 belongs to Kobak (entry 1, verified). Future maintainers should verify the actual arxiv ID for Liang 2024 (entry 19) before propagating.

---

## 9. Extending this bibliography

When adding a source: pick the section, assign the next sequential number, apply the most accurate label (V, W, C, U), list anchor pattern IDs, add a correction note to section 8 if the new entry corrects a prior one, and self-audit for em-dashes before saving.

When downgrading: do not delete. Re-label as U with date and the verification step that failed. Add a correction note.

---

End of bibliography.

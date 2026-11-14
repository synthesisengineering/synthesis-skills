# Fact-checking: review log and pre-publish checklist

Sections 11 and 12 of the fact-check process, verbatim: the log every fact-check leaves beside the draft, and the checklist that gates publication.

## 11. Documentation Template

Create a `review-log.md` file alongside the draft to document the fact-checking process.

### Template

```markdown
# Fact-Check Review Log

**Article:** [Title]
**Article Date:** [Publication date]
**Reviewer:** [Name]
**Review Date:** [Date]
**Sources Used for Synthesis:** [List]

## Claims Reviewed

### Claim 1: [Brief description]
- **Draft text:** "[Exact text]"
- **Status:** Verified / Needs Correction / Cannot Verify / Removed
- **Source:** [Primary source with URL or citation]
- **Finding:** [What verification revealed]
- **Correction applied:** [What changed]

[Continue for all claims]

## Editorial Decisions

- [Decision 1]
- [Decision 2]

## Summary

- Total claims reviewed: [N]
- Verified as stated: [N]
- Corrected: [N]
- Removed: [N]
- Cannot verify (hedged): [N]
```

---

## 12. Pre-Publish Checklist

### Factual Accuracy

- [ ] All statistics verified against primary sources (number AND framing)
- [ ] All study names verified (title, authors, publisher, paper number)
- [ ] All study findings verified (direction, magnitude, framing match source)
- [ ] All direct quotes verified for exact wording against primary source
- [ ] All direct quotes verified for correct attribution
- [ ] All organization names verified against official sources
- [ ] No conflated findings: each claim maps to a single finding in a single source
- [ ] No hallucinated citations: every cited source exists and says what the draft claims

### v2.0 Additions

- [ ] Multi-source claims pass graph independence check (no single AI upstream)
- [ ] Nested-attribution quotes traced to original speaker (C1-NESTED-001)
- [ ] No composite quotes (C1-COMPOSITE-001)
- [ ] No paraphrase boundary drift (C1-PARAPH-001)
- [ ] No position-shifting from source's stated position (C1-POSSHIFT-001)
- [ ] Source-language translations checked (C1-TRANS-001)
- [ ] URL classification applied for each cited URL (C1-URLROT-001 six-category taxonomy)
- [ ] No AI-generated synthetic sources (C1-SYNTH-001: experts verified, studies verified, publication venues verified)
- [ ] Citation laundering check on multi-source claims (C1-LAUNDER-001)
- [ ] Family-specific hallucination check applied if source LLM is known (C1-TOOLHALL-001)

### Temporal Integrity (if backdated)

- [ ] All cited sources predate the article's publication date
- [ ] Any post-date sources marked with "Updated on" notes
- [ ] Time-relative language accurate relative to article date
- [ ] No references to events or data postdating article without notation

### Translation-Pass Integrity (if applied)

- [ ] Every term replaced via de-jargoning re-verified against source material
- [ ] No claim asserts something the source does not
- [ ] Vague descriptors accurate at the new level of precision

### Documentation

- [ ] Review log documents every claim checked
- [ ] Corrections recorded in review log
- [ ] Editorial decisions documented
- [ ] Claims that cannot be verified removed or hedged appropriately

### Cross-Check with Content-Quality Skill

- [ ] Article reviewed against synthesis-content-quality v4.0 for stylistic issues
- [ ] No vague attributions remain ("experts say," "studies show") unless explicitly hedged
- [ ] No placeholder text (`[source needed]`, `TODO`, `VERIFY`) remains in draft

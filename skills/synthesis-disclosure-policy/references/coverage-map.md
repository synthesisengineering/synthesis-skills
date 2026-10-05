# Coverage map: disclosure policy 1.1.0 to 2.0.0

Every part of the 1.1.0 SKILL.md and where it lives now. Nothing was removed.

| 1.1.0 section | Now |
|---|---|
| Frontmatter description | Shortened to 291 characters; it keeps the triggers "can I name this company", "disclosure policy", "precedent ledger" and "public bio names" |
| Opening paragraph 1 (a name blacklist models the wrong thing) | references/policy.md, "Why approval, not names" (verbatim) |
| Opening paragraph 2 (approval and provenance) | SKILL.md opening (verbatim) |
| The three disclosure classes | references/policy.md (verbatim); summarized in Binding rules 1 to 3 |
| The five tests | SKILL.md (verbatim); summarized in Binding rules 4 and 5 |
| The precedent ledger, with its YAML example and rules | references/policy.md (verbatim); summarized in Binding rules 2 and 6 |
| Surface classes | references/policy.md (verbatim except one link path, below); summarized in Binding rule 7 |
| Division of labor | references/policy.md (verbatim); summarized in Binding rule 9 |
| Category Allowlists Without Approval Fatigue | SKILL.md (verbatim, same heading: `synthesis-implementation-integrity/scripts/test_r5_contract.py` reads this section from SKILL.md); summarized in Binding rule 8 |
| Maintenance protocol | references/policy.md (verbatim); summarized in Binding rules 2 and 10 |
| Adopting this for yourself | references/adopting.md (verbatim except one link path, below) |
| Relationship to other skills, and the closing paragraph on the private companion | references/adopting.md (verbatim except three link paths, below) |
| references/ledger.example.yaml | Unchanged |
| `depends_on`, `source_repo`, `source_type`, `author` | Kept: `synthesis-agent-conformance` checks them in its source contract and `synthesis-onboarding` modular install reads `depends_on` |

## Lines changed only in their link target

These five lines moved from SKILL.md into references/, one directory deeper, so each relative link now climbs one more level (`../` became `../../`, and `references/ledger.example.yaml` became `ledger.example.yaml`). The visible words are unchanged. The 1.1.0 lines were:

```text
The companion [`synthesis-git-hooks`](../synthesis-git-hooks/SKILL.md)
   [`references/ledger.example.yaml`](references/ledger.example.yaml) into a
- [`synthesis-git-hooks`](../synthesis-git-hooks/SKILL.md) — the
- [`synthesis-content-quality`](../synthesis-content-quality/SKILL.md) —
- [`synthesis-message-guard`](../synthesis-message-guard/SKILL.md) —
```

## The 1.1.0 frontmatter, verbatim

Kept on record so the old description and metadata are not lost.

```yaml
---
name: synthesis-disclosure-policy
description: "Two-category disclosure governance for people who publish under their own name while handling confidential work. Distinguishes published-precedent facts (deliberately public biography an agent may restate) from unapproved disclosures (anything learned from private context), with a precedent ledger, surface classes, five decision tests, and git-hook enforcement. Use when asked about: disclosure policy, confidentiality guardrails, can I name this company, precedent ledger, public bio names, publication surface, unapproved disclosure, name allowlist."
license: "Apache-2.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.1.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```

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
| references/ledger.example.yaml | Unchanged in 2.0.0; three header-comment lines changed in 2.0.1 (below) |
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

## Changed in 2.0.1

The final v5 sweep (2026-10-05) replaced every line that told an agent to run the retired
git-hooks doctor or to configure a fixed-path policy file. Each old line is verbatim in
[preserved.md](preserved.md). The rule they served is unchanged.

| Where | Old | Now |
|---|---|---|
| SKILL.md binding rule 10 | "Run the hook doctor after every ledger or policy edit" | "Check the policy and ledger after every edit", pointing at adopting.md step 4; the failure-not-warning clause verbatim |
| policy.md, ledger rules | "the hook doctor flags stale allowances" | "the commit check refuses a stale allowance" (`synthesis/commit_check.py` `allowances`) |
| policy.md, Maintenance protocol step 3 | "Run the hook doctor after every ledger or policy edit" | "Check the policy and ledger after every ledger or policy edit (adopting.md, step 4)"; the rest verbatim |
| adopting.md step 3 | classify surfaces "in `~/.synthesis/git-hook-config.yaml`" | in a private copy of git-hooks' example policy, with `commit_policy` in `~/.synthesis/v5/config.json` naming it (without the key no disclosure rule runs); the four classifications verbatim |
| adopting.md step 4 | `python3 ~/.synthesis/git-hooks/_load_config.py --doctor`, kept in the rituals | what the commit check refuses and when; a one-line check of policy and ledger through `commit_check.load_policy` and `allowances`; `commit_check.py --classify` in a published-site repository; `synthesis doctor` in the rituals for `core.hooksPath` |
| ledger.example.yaml header | "in ~/.synthesis/git-hook-config.yaml", "engine and doctor", "The doctor flags stale allowances." | the policy that `commit_policy` names; "commit check in public-surface repos"; "The commit check refuses a stale allowance." |

SKILL.md lists preserved.md in Contents; version 2.0.0 became 2.0.1.

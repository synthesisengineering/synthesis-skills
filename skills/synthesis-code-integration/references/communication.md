# Code integration: communication and evidence

How to give feedback, ground replies in code, and reach conclusions before publishing them.

## Communication and Feedback

### Principles

- **Be specific, not vague.** "This has security issues" is useless. Name the issue, explain why it matters, and suggest the fix.
- **Explain the why.** Contributors who understand the reasoning behind a standard will follow it naturally in future work.
- **Acknowledge good work.** People do more of what gets recognized.
- **Distinguish severity levels.** "Must fix before production" vs. "should fix" vs. "consider for future."
- **Fix first, talk later.** When you find a bug with an obvious fix during integration: fix it, test it, deploy it, THEN tell people. Do not draft Slack messages explaining your findings when you could ship the fix in 2 minutes. Action before communication when the action is quick and the risk of delay is real.

### Ground All Technical Replies in Code

Before drafting ANY technical reply (to a contributor, in a PR comment, in a Slack thread), verify your claims against actual code. The lead synthesist sending a reply that agrees with a wrong analysis undermines credibility and trust.

**Verification checklist by reply type:**

| Reply type | Before responding, verify |
|-----------|--------------------------|
| Bug report | Reproduce the bug. Read the relevant code paths. Confirm the reported behavior matches what the code actually does. |
| PR review | Read the diff AND the surrounding code. Understand what the change interacts with, not just what it changes. |
| Feature request | Check if the feature already exists, partially exists, or conflicts with planned work. |
| Infrastructure question | Check actual config files, deployment scripts, and environment variables. Do not rely on memory. |

### The Integration Review Document

For each set of contributions, produce a written review covering:

1. **Project standards the contributor needs to know** — extracted from the lead's implicit knowledge
2. **Specific feedback on each PR** — strengths, issues, recommendations
3. **The integration plan** — what the lead will do with the code and in what order
4. **Contribution workflow for next time** — how to submit work that integrates more smoothly

---

## Investigate Before Concluding

Get basic facts before forming hypotheses. This applies to integration review, bug triage, and any technical analysis.

**Rules:**
- Do not test with wrong inputs. Verify you are using the correct test data, credentials, and environment before drawing conclusions.
- Do not confuse access from your machine with access from the server. Local environment variables, network access, and permissions differ from production.
- Say "I don't know" when you do not know. An incorrect confident answer causes more damage than admitting uncertainty.
- Check the simplest explanation first. Before hypothesizing about race conditions or distributed system failures, verify that the basic inputs and configuration are correct.

**Before publishing any analysis:**
1. State your evidence explicitly
2. Distinguish between "I observed X" and "I conclude Y"
3. Check if alternative explanations fit the same evidence
4. If the conclusion has material consequences (reverting code, blocking a deploy, escalating to a stakeholder), get a second pair of eyes

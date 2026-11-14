# PR review: verifying analysis

How to check a conclusion before acting on it or posting it.

## Verifying AI-Generated Analysis

When someone presents a root cause analysis — whether from an AI tool, a contributor, or a team member — verify the conclusion against actual code, not just intermediate findings.

**Why this matters:** AI analysis can be 5-of-6 correct but critically wrong on the conclusion. The intermediate findings (file X calls function Y, which queries table Z) may all be accurate, but the final conclusion ("therefore the bug is in the query") may miss an alternative code path that actually handles the case differently.

**Verification process:**

1. **Read the cited code yourself.** Do not rely on someone else's summary of what the code does.
2. **Look for alternative code paths.** The analysis may describe one path accurately while missing another that handles the same input differently (error handlers, fallback logic, middleware, decorators).
3. **Be skeptical of sweeping conclusions.** Phrases like "zero effect," "completely broken," or "never works" are almost always wrong. Reality is usually more nuanced.
4. **Check the system-level view.** A function-level analysis may be correct in isolation but miss interactions with caching, middleware, event handlers, or background jobs that change the behavior.
5. **Test the conclusion, not just the intermediate steps.** If the analysis says "changing X will fix the bug," verify that claim independently before acting on it.

The synthesis engineer's role is to verify conclusions against system-level understanding. The AI or contributor may have done solid analysis work — but the conclusion is where errors compound.

### When You Use AI to Help Review

If you use an AI coding agent to assist with your own review, apply verification before posting any findings:

- **Verify every "Must fix" finding against the actual code before posting it.** AI agents confidently cite issues that do not exist in the diff. Open the file, read the line, confirm the problem is real.
- **Check import statements yourself.** AI agents frequently misread imports across branches, reporting missing imports that exist or present imports that were removed. Verify against the branch being reviewed.
- **Validate scope claims against the diff file list.** If the AI says "this PR changes the authentication flow," confirm that authentication-related files actually appear in the diff.
- **Run the agent's suggested test scenario mentally.** Walk through the code path the AI describes. If the scenario requires a condition that cannot occur given the actual code, the finding is invalid.
- **Standard before posting AI-assisted findings:** "I have verified this against the actual code." If you cannot honestly say that, do not post the finding.

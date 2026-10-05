# PR review: after the review

What happens once a PR passes review, and how to verify it after merge.

## Integration with Adopt-and-Adapt

When a PR passes review and is ready for integration:

1. **If the PR is clean** — the authorized integrator merges it after the repository's current gates pass.
2. **If the PR needs adaptation** — the lead synthesist creates an integration branch, applies the adopt-and-adapt pattern, verifies the adapted bytes and merges within the actual grant.
3. **If required work remains** — retain it as an open obligation. A dependency may land when independently useful, safe and authorized, but tickets or a partial merge cannot satisfy a promise to complete the whole outcome.

The review findings feed directly into the integration plan. Apply the shared [decision-ownership contract](../../synthesis-thinking-framework/references/decision-ownership.md): technical review acceptance, merge authorization, release/deployment authorization and delivered outcome are separate facts. Prior valid grants remain usable within their scope; reviewer approval cannot create a new grant. Do not request the same authorization again merely because work moved to another skill.

### Post-Merge Verification

PR review is a prevention mechanism — it catches issues before they reach the main branch. Post-merge verification is a detection mechanism — it confirms the integrated result actually works as expected.

After merging a PR (especially one that required adaptation):

- **Check whether the project has a post-merge verification protocol.** Many synthesis-coded projects define verification steps that run after integration — build checks, smoke tests, deployment validation, or manual verification checklists.
- **Flag overlapping files proactively.** If the PR touched files that other in-flight PRs also modify, alert the team so post-merge verification covers the interaction.
- **Remind the integrator to run the post-merge protocol.** It is easy to forget verification after a clean merge. Build the habit of treating merge as "step 1 of 2" — merge, then verify.

Prevention and detection are complementary. A thorough PR review reduces the chance of post-merge issues. A thorough post-merge verification catches what review missed — especially integration effects that only manifest when the change combines with the rest of the codebase.

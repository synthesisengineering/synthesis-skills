# Model tiers: choosing a role

The full role-selection rule, moved verbatim from the 2.2.0 SKILL.md. Read it whenever a task's tier is not obvious, and always when the request reads as a symptom.

## Choosing a role: diagnostic difficulty, not apparent size

The most common misroute is sending a **small-sounding** task to a cheap tier. Size is not the variable. **Whether the cause is known** is the variable.

- **Cause known** → the specification is settled and the work is execution: apply this rename, run this suite, add this row, reformat these files. This is `routine` or `bulk`.
- **Cause unknown** → the work is *diagnosis*, whatever its apparent size. Anything phrased as a symptom — "X isn't working," "this broke," "why is it doing that," "the file won't open" — is a differential over a chain of candidate causes. Cost scales with the search, not with the fix. **This is `judgment` even when the subject is one file.**

Cheap reasoning on a diagnosis does not return a smaller correct answer. It takes the first plausible branch and commits — and the confidence is what gets the wrong answer written, committed, and pushed.

Three properties force `judgment` regardless of how small the request sounds. Any one is sufficient:

1. **The cause is unknown** (the rule above).
2. **The blast radius includes a deliverable or a durable record.** Reading is cheap; writing to something another agent, a client, or a future session will rely on is not — however small the edit.
3. **The work will not be independently reviewed before it lands.** Work that bypasses an existing review gate carries that gate's weight itself.

**The asymmetry that makes this a cost, not a preference.** Where a mistake must be caught and undone by a more expensive process, the cheap attempt is not a saving — it is a debt with interest. The diagnosis, the revert, and the re-verification all get paid at the higher tier anyway, plus the principal's attention in between.

**The trust dependency is the sharpest part.** A low-tier agent's plausible-sounding wrong explanation transfers the entire verification burden back to the human, which inverts the reason for delegating. A principal who accepts a confident, coherent, wrong diagnosis inherits the defect silently.

The shape to recognize, from a real instance: a "this file won't open" report was routed to a cheap tier. The symptom was a broken *link* — a two-ended thing — and the cheap session inspected only the file, never the link text sitting in the preceding message. It built a plausible theory from a diagnostic tool's output, rewrote the file to satisfy that tool, watched the tool go quiet, and committed. The tool's approval was real; it was also irrelevant to the reported symptom, which remained unfixed while the file itself was degraded. **A green signal from the wrong oracle is more dangerous than no signal, because it terminates the investigation.**

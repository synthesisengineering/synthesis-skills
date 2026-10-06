# Knowledge capture: shipping, integration and related skills

Read when handing a merge to synthesis-kb-edit, committing, or deciding which sibling skill owns a piece of work.

## Integration

- **`synthesis-okf`** validates conformance and configured metadata
  consistency after every merge. This skill governs *what* to write and
  *where*; OKF governs that the result stays structurally coherent.
- **`synthesis-kb-edit`** owns repository policy and shipping. Pass it the
  touched files; do not independently reconstruct branch, host, scanner, or
  review mechanics from the capture config.
- **`synthesis-context-lifecycle`** is the sibling for *project* working memory
  (CONTEXT/REFERENCE/sessions). This skill is its counterpart for the durable,
  cross-project knowledge base. Project state that has hardened into a stable
  fact graduates from a project's REFERENCE into the knowledge base via this
  skill.
- **Daily rituals** are a natural trigger: a day-end step can ask "what did today
  teach that the knowledge base should hold?" and run this workflow on the
  answer.
- **Repository configuration.** Read `.agents/knowledge-base.yaml`; do not
  discover client-specific workflow copies under a tool-owned skill folder.
  One portable config plus the public skills is the cross-agent contract.

## Commit hygiene

- Stage only the files this merge touched. Never `git add -A` — a sibling
  process or a parallel agent may have staged unrelated work.
- The commit message names the *area*, not the sensitive specifics: "Update key
  people directory," "Refresh product ownership," "Record a departure." Never
  put the person, the reason, or the prior value in the message.
- Verify `git remote -v` before any push. Push only per the repo's config
  posture; hold for explicit approval on any shared or mirrored repo, and never
  push a private-tier repo to a shared remote.

## Related

- `synthesis-okf` — the OKF format validator/converter this skill validates with.
- `synthesis-kb-edit` — repository policy, validation orchestration, and
  configured ship flow.
- `synthesis-context-lifecycle` — project working memory; the sibling layer.
- `synthesis-message-guard` — the same provenance-and-fail-safe ethos, applied to
  outbound correspondence instead of stored knowledge.

# Cross-workspace visibility

One human, several Slack workspaces — personal, employer A, employer B.
The ecosystem supports two visibility postures, declared per machine in
the workspace registry (`scripts/slack_workspaces.py init` writes
`~/.synthesis/slack-workspaces.yaml`). The same two postures apply to
every message surface (Slack, email, calendars, chat): Slack is the
first surface with a registry; the others follow the same doctrine.

## Unified (Rajiv's operating rule)

The agent's default focus is the session workspace — the workspace the
session runs in. But the agent MAY read the principal's other
configured workspaces when relevant: resolving a scheduling conflict,
weighing how important a conflicting task is, answering "did anyone
mention X anywhere". The agent is one and the same assistant serving
one and the same human, and a priority call made blind to the other
workspaces is a worse call.

Rules under unified:

- Reads cross workspaces; writes stay routed. Transcripts land in each
  workspace's own private repo; daily action plans stay person-scoped
  in the personal repo, per the existing routing.
- Cross-workspace reads are purpose-bound: scheduling, priority, or an
  explicit "anywhere" question. Curiosity browsing is not a purpose.
- A cross-workspace fact cited in a derivative file names its source
  workspace, so the citation chain stays traceable.
- Only workspaces whose tokens resolve to `ready`/`external` are
  readable. Placeholders read as unconfigured, never as empty.

## Isolated (strict separation)

Only the session workspace is visible. Cross-workspace reads are
forbidden — not discouraged, forbidden: the `readable` set is the
focus workspace alone even when other workspaces are configured and
their tokens are valid.

Isolation is enforced at two levels:

- Soft: `mode: isolated` in the registry. The agent refuses
  cross-workspace reads as a policy violation.
- Hard (machine-level): the workspace is absent from that machine's
  registry and MCP configuration entirely. A workspace the machine
  cannot name, it cannot reach. This is the shape for work-only and
  personal-only computers, and for the future "severance" engagement
  where a counterparty requires compartmentalization as if the
  principal were two different people.

Principals who need strict separation choose it; nothing in unified
mode leaks across the boundary for them, because under isolated mode
there is no boundary to consult — the other workspaces are simply not
readable from the session.

## Choosing and changing

- The shipped default is `unified`. With a single configured workspace
  both modes behave identically, so the default changes nothing for
  single-workspace users.
- A principal opts into `isolated` by setting `mode:` in the registry.
  A future per-workspace override (this workspace isolated, the rest
  unified) is anticipated but not built; the per-machine hard level
  covers the strict cases today.
- Moving a workspace to its own machine (the future separate-computer
  shape) is a registry operation, not a code change: the workspace
  exists only on its machine's registry, with its own tokens.

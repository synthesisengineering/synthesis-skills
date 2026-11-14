# Workspace Context: {workspace}

This is the shared instruction source for the `{workspace}` workspace. It is stored in
the workspace's Git-tracked personal knowledge repository so every machine and
supported agent client receives the same rules.

## Knowledge and project continuity

- Personal knowledge base: `ai-knowledge-{workspace}/`
- Projects are registered in `ai-knowledge-{workspace}/projects/index.yaml`.
- Resume named synthesis projects from their tracked `CONTEXT.md`,
  `REFERENCE.md`, session log, and artifacts rather than chat memory.
- Keep durable workspace-specific additions in this file. Do not edit the
  workspace-root `AGENTS.md`; it is a link to this source.

## Compact Instructions

When this conversation is summarized to free context, keep what exists only in the conversation:

- the task in progress, its next concrete step, and everything it waits on: an approval asked for, a CI run, a
  reply, a background task or watcher (its id and what it waits for);
- decisions and corrections the person gave in the conversation that no file records yet, and who gave them;
- exact identifiers: file paths, branches, pull requests, commit hashes and URLs;
- what was verified, and how, apart from what was assumed.

Drop tool output, file listings and step-by-step history. Leave out the active project's directive and current
state: synthesis puts them back after compaction.

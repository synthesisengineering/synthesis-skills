# Slack token guide: finding and installing workspace tokens

Each Slack workspace needs its own token. The registry
(`~/.synthesis/slack-workspaces.yaml`) names where each token lives;
this guide covers minting one and pointing the registry at it.
`slack_workspaces.py init` seeds generic `personal`/`work` entries —
rename them to match the session-workspace keys (the
`~/workspaces/<name>` directory names) and add further workspaces as
needed before installing tokens.

## Minting a token (per workspace)

1. Open [api.slack.com/apps](https://api.slack.com/apps) in a browser
   signed into the workspace.
2. Create a new app (From scratch), name it after the reader
   (e.g. `synthesis-reader`), pick the workspace.
3. Under OAuth & Permissions, add the read scopes the sync needs:
   `channels:history`, `groups:history`, `im:history`,
   `mpim:history`, `users:read`. (No write scopes: the reader never
   posts. If the workspace admin must approve the app, this
   read-only list is the approval case.)
4. Install the app to the workspace and copy the Bot User OAuth
   Token (`xoxb-...`).

If the workspace already has a reader app (a previous install), reuse
it: open the app, OAuth & Permissions, copy the token. Nothing
requires one app per machine.

## Installing the token (per machine)

Pick one form per workspace and set the registry's `token:` field:

- `env:SLACK_TOKEN_<WORKSPACE>` — export the variable in the shell
  profile (e.g. `export SLACK_TOKEN_WORK='xoxb-...'` in
  `~/.zshrc`). Best for CLI clients that inherit the shell.
- `file:/abs/path/to/token` — first line is the token. Best when env
  vars are awkward; keep the file `chmod 600`.
- `mcp:server-name` — the client manages the credential (OAuth or its
  own secret store) and exposes the workspace through an MCP server
  with this name. Readiness is proven by the first MCP call.

Never paste a literal `xoxb-` value into the registry: `doctor`
rejects it. The registry is a synced dotfile; secrets don't live in
synced dotfiles.

## Verifying

```
python3 <synthesis-slack-sync-root>/scripts/slack_workspaces.py doctor
```

Run from inside `~/workspaces/<name>` so the session workspace
resolves. Exit 0 with `readable from here:` listing the workspaces
means the sync may read them. Exit 1 names the workspace whose token
is still a placeholder, missing, or rejected.

## Sending tokens to the agent later

When the principal provides tokens after the registry was seeded with
placeholders, the agent installs each token in the agreed form (env
var or file — never the registry, never chat logs beyond the paste),
re-runs `doctor`, and reports the readable set. The placeholder entries
exist so this step is installation, not redesign.

# Guardrail configuration

Everything lives in the principal's private `~/.synthesis/v5/config.json`. A missing file
means the defaults below. A file that can't be read or parsed blocks every shell call,
send and account-routed call until it is fixed (R3.5); other tools are unaffected.

## Contents

- [Keys](#keys)
- [An example](#an-example)
- [From the 1.x config files](#from-the-1x-config-files)

## Keys

| Key | Default | Meaning |
|---|---|---|
| `account_routing.workspaces` | none (nothing routed) | `{"<workspace root>": {"account": "<address>", "label": "<name>", "aliases": ["<other spellings>"]}}`. The deepest root containing the session's working directory wins; `~` and symlinks resolve. A root with no `account` blocks routed calls there. Not a map: routed calls block. |
| `account_routing.default_account` | none | The account a connector with no account parameter acts as, so a call without one can be allowed where that is the right account. |
| `push_deploys` | none | Repository roots whose push publishes (for example Cloudflare Pages on main). A push into one, or into a linked worktree of one, is a deploy. |
| `deploy_patterns` | none | Extra regexes for build-deploy commands, matched from the start of a command (after wrappers) or of the script an interpreter runs, beside the built-in `wrangler (pages) deploy`, `vercel --prod`, `netlify deploy --prod`, `firebase deploy`, `npm publish`, `twine upload`, `gh release create`. |
| `deploy_content` | `content/posts/**/index.md`, `**/src/content/articles/*.md` | Globs of the dated content files the date rules read: the nested-date and the flat layout. Not a list of strings: deploys block. |
| `protected_roots` | none | Extra roots a recursive delete must never target, beside `/`, home, `~/workspaces` and each folder in it. Any repository root is protected too. |
| `shortcut_phrases` | none | Extra deferral phrases the reply check sends back, beside its built-in list. The principal's phrase catalog belongs here or in the anti-shortcuts skill. |
| `reply_file_links` | false | True: a reply that names a file without a clickable absolute-path markdown link is sent back once. |

## An example

```json
{
  "account_routing": {
    "default_account": "me@personal.example",
    "workspaces": {
      "~/workspaces/clientco": {"account": "me@clientco.example", "label": "ClientCo", "aliases": ["ClientCo Exchange"]},
      "~/workspaces/personal": {"account": "me@personal.example"}
    }
  },
  "push_deploys": ["~/workspaces/personal/site"],
  "deploy_patterns": ["release-gate\\.mjs\\s+deploy"],
  "protected_roots": ["~/Archives"],
  "shortcut_phrases": ["can wait until"],
  "reply_file_links": true
}
```

## From the 1.x config files

| 1.x | v5 |
|---|---|
| `~/.synthesis/account-routing/workspaces.json` `{"workspaces": {root: {account, label, tool_hint}}}` | `account_routing.workspaces`; `tool_hint` dropped (the block message names the parameter to pass) |
| `~/.synthesis/publish-guard/config.json` `auto_deploy_repos` | `push_deploys` |
| its `sites.<repo>.content_layout`, `content_roots` | `deploy_content` globs |
| its `principal_name` | dropped: messages say "the principal" |
| `PUBLISH_GUARD_CONFIG`, `PUBLISH_GUARD_STATE_DIR`, `ACCOUNT_ROUTING_CONFIG` | `SYNTHESIS_HOME` (tests and sandboxes) |
| `~/.synthesis/agent-guardrails/hooks.json` per-hook enable flags | gone: the plugin's `hooks/hooks.json` decides what runs |
| `~/.synthesis/anti-shortcut-catalog.yaml` | its phrases go to `shortcut_phrases` and the anti-shortcuts skill |
| `schemas/workspaces.schema.json`, `schemas/sites.schema.json` | this table |

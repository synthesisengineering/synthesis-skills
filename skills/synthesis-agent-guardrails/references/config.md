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
| `browser_routing.workspaces` | none (no browser check) | `{"<workspace root>": {"device": "<deviceId from list_connected_browsers>", "label": "<name>"}}`. The deepest root containing the directory the session started in wins. Browser calls there must use that device (references/account-routing.md, "Browser profiles"). Not a map, or a root without a device: browser calls block. |
| `browser_routing.workspaces.<root>.accounts` | none (no site is asked about) | `{"<a site, or the page of it that shows the signed-in account>": "<the workspace's address there>"}`. A browser call that puts something into a page of a named site (keys, a form's value, an upload, a script) waits until a read of the site in the session's record shows that address. A read that shows another of the principal's addresses is called a misconfiguration: the hold and the turn's end say so, and `synthesis doctor` warns until a later read shows the right account (references/account-routing.md, "The account a site shows"). A map of another shape: the workspace's browser calls block. |
| `push_deploys` | none | Repository roots whose push publishes (for example Cloudflare Pages on main). A push into one, or into a linked worktree of one, is a deploy. |
| `deploy_remotes` | none | GitHub repositories, as `owner/repo`, where a push or a merged pull request publishes (for example a Homebrew tap). A `git push` from a checkout with a remote on one, or `gh pr merge` on one (by `-R` or the checkout's remotes), is a deploy. |
| `deploy_patterns` | none | Extra regexes for build-deploy commands, matched from the start of a command (after wrappers) or of the script an interpreter runs, beside the built-in `wrangler (pages) deploy`, `vercel --prod`, `netlify deploy --prod`, `firebase deploy`, `npm publish`, `twine upload`, `gh release create`. |
| `deploy_content` | `content/posts/**/index.md`, `**/src/content/articles/*.md` | Globs of the dated content files the date rules read: the nested-date and the flat layout. Not a list of strings: deploys block. |
| `deploy_also_renders` | none | Map from a site repository to the other repositories its build renders from their working trees (for example a personal site that pulls in other sites' articles). Deploying the site also applies the date rules to those repositories, so a future-dated article there cannot go live early through it. |
| `sheet_hosts` | none | Cloudflare Pages projects that serve the principal's action sheets privately. An upload by the action sheet's own `publish_sheet.py` to a listed project goes through without an approval: the script uploads only the generator's page, rebuilt from the filed spec, and only while the host and a fresh subdomain send a request with no sign-in to a Cloudflare Access sign-in. A direct `wrangler pages deploy` to the project, or the script's upload to an unlisted one, still waits for approval. The principal's setting, never an agent's. |
| `pr_gated` | none (no gate) | `{"<owner>/<repo>": {"since": "YYYY-MM-DD", "direct_ok": ["<commit>"], "branch": "<default branch>"}}` (`branch`: the default branch; without it the guard uses the one the checkout records for the remote, and holds every branch push from a checkout that records none): repositories that take changes only through a pull request. A `git push` that would move a listed repository's default branch is refused, from any checkout or linked worktree with a remote on it, unless the principal types a code for that one push. `since` is the day the gate began; `synthesis doctor`'s `pr gate` check lists commits on the default branch from that day that came through no pull request, less those in `direct_ok`. Not this shape: pushes block. See deploys.md, "The pull-request gate". |
| `record_times` | none (no check) | `{}` turns on the commit check's reading of the time an entry gives for itself in a Markdown record: a stamp that stands 1 to 30 minutes after the commit, or that rounds the present, is refused. `{"skip": ["<folder or pattern>", ...]}` names what it does not read beside folders of transcripts: a folder from the repository's root (`daily-plans`, `projects/alpha/drafts`) or a pattern (`*/drafts/*`), matched with the case as written. It takes no other key, and any other shape blocks the commit until it is fixed: `{"enabled": false}` and `null` do not turn it off; leaving the key out, or `false`, does. It applies in every repository the commit check guards. What it reads and lets pass: the git hooks' [scanning reference](../../synthesis-git-hooks/references/scanning.md#an-entrys-own-time). |
| `status_evidence` | none (no check) | `{}` turns on the commit check's reading of status tables in Markdown records: a row added to a table that has a column headed Status and a column for evidence is refused when it gives a status and no evidence and does not say `unverified`; in a table with a Status column and no column for evidence, a row that says a thing works and points at nothing gets a note. `{"skip": ["<folder or pattern>", ...]}` names what it does not read, as for `record_times`. It takes no other key, and any other shape blocks the commit until it is fixed; leaving the key out, or `false`, turns it off. What it reads: the git hooks' [scanning reference](../../synthesis-git-hooks/references/scanning.md#a-status-and-its-evidence). |
| `unsaved_hours` | 24 | How long a file under a live seat's claim may stay uncommitted, or in a commit on the checkout's own branch that no remote holds, before `synthesis doctor` warns, counting per repository, and the weekday evening job shows a banner that names nothing. False turns both off; a value that is not a number above 0 is read as 24, and the doctor's line says so. |
| `scheduled_fetch` | true | The hourly job that copies session transcripts also runs `git fetch` in each knowledge root and sessions repo, never merging, writing no `FETCH_HEAD` and asking for nothing; `synthesis doctor` says when each was last fetched and git's reason when one could not be. False turns it off, for a remote that asks for a passphrase or an approval at each use. |
| `protected_roots` | none | Extra roots a recursive delete must never target, beside `/`, home, `~/workspaces` and each folder in it. Any repository root is protected too. |
| `shortcut_phrases` | none | Extra deferral phrases the reply check sends back, beside its built-in list. The principal's phrase catalog belongs here or in the anti-shortcuts skill. |
| `wait_phrases` | none | Extra phrases with which a reply announces a wait of the session's own; the reply check sends such a reply back once when nothing is armed to end the wait. |
| `reply_watch` | none (no check) | `{}` turns on the reply check's question after a message to a person: a turn in which one went out ends with a watch for its answer or with `synthesis wait none "<why>"`, or the reply is sent back once. It takes no key: what a message to a person is, the send guard says (`send_tools`, `not_send_tools`). Any other shape is said in a reply sent back once. What it reads: [reply-and-provenance.md](reply-and-provenance.md#a-message-to-a-person). |
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
  "browser_routing": {
    "workspaces": {
      "~/workspaces/clientco": {"device": "11111111-2222-3333-4444-555555555555", "label": "ClientCo profile",
                                "accounts": {"assistant.example/settings": "me@clientco.example"}},
      "~/workspaces/personal": {"device": "66666666-7777-8888-9999-000000000000", "label": "personal profile"}
    }
  },
  "push_deploys": ["~/workspaces/personal/site"],
  "deploy_remotes": ["example-org/homebrew-tap"],
  "deploy_patterns": ["release-gate\\.mjs\\s+deploy"],
  "pr_gated": {"example-org/private-skills": {"since": "2026-11-11", "branch": "main", "direct_ok": []}},
  "record_times": {"skip": ["daily-plans/**"]},
  "status_evidence": {},
  "protected_roots": ["~/Archives"],
  "shortcut_phrases": ["can wait until"],
  "reply_watch": {},
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

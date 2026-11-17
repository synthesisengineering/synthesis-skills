# Guardrail configuration

Everything lives in the principal's private `~/.synthesis/v5/config.json`. A missing file
means the defaults below. A file that can't be read or parsed blocks every shell call,
send and account-routed call until it is fixed (R3.5); other tools are unaffected, except
that a file tool is still judged without it, so a write into the state folder stays refused
and the file's repair waits for the principal's code.

**The file is the principal's to change.** It sets what every approval means, so an agent's
write to it waits for the principal's code for exactly that write, and so does a write to
anything under `~/.synthesis/v5/git-hooks`, the commit check's entry points: by a file tool
(Write, Edit, MultiEdit, NotebookEdit, Codex's `apply_patch`, Muse's `write_file` and
`edit_file`) or by any shell command the guard reads (a redirect, `cp`, `mv`, `tee`,
`install`, `ln`, `sed -i`, `rm`, a program that writes it), however its path is spelled. The
copy that installs the principal's settings from a private repository waits too, and its
code binds the file it copies as it stood. Reading needs no code (`cat`, `head`, `grep`,
`jq`, `diff`, and `cat … > copy` for a copy); `cp` and `ln` of it wait, as for every file
the guard protects. The installer's own route (`synthesis install`, `synthesis update`) is
unchanged. A write to a shell's startup files, Claude Code's shell snapshots or the harness
programs (`claude`, `codex`, `muse`, `gh` wherever each resolves) waits the same way, since
each runs with no code. How the guard reads each route: the plugin's
`docs/runtime-integration.md` (Approvals).

**When a guard cannot answer** (5.21.0). In Claude Code the plugin's PreToolUse hook sets
`"onFailure": "block"`, so from Claude Code 2.1.295 a guarded call (a shell command, a file
write, a send, an account-routed or browser call) is held when the guard times out (5
seconds), crashes, prints output Claude Code cannot read, or cannot start because the stable
hook is missing. Before 2.1.295 the setting is ignored and the call goes through; `synthesis
doctor` warns then, and fails a plugin whose hook lacks the setting. Codex (0.167) and Muse
(1.4.20) have no such setting and let a call through when the hook exits with an error, but
block on exit 2 with a reason, so the guard's own command (in `hooks/hooks.json`, Muse's
`pre-tool-use.sh` and the user-level declaration) turns a stable hook that cannot start or
crashes into exit 2 with one line of reason, and a deny keeps its own (Muse's hook test and
Codex's reading of all four, run on 2026-11-14). The guard also keeps a deadline of its own, 4
seconds from when the hook starts judging the call (5.21.1): past it the call is held with the
reason, and git or any other process the guard started is stopped, so a slow repository read or a
lock answers closed in every harness inside its 5-second limit. What still lets a call through in
Codex and Muse is a hook that uses up their 5 seconds before its deadline is set: Python itself
slow to start by more than about a second, under heavy load or on a stalled disk. In every harness
an unreadable config and an error inside a guard still block, since the guard catches those itself.

**Programs a command runs** (5.24.0). The shell guard reads a shell script a command runs (by a shell, by its path or
sourced) as the command lines it holds, three scripts deep, and reads a Python script run by its path, `ipython`, and
what `uv run`, `poetry run`, `pipx run`, `pdm run` and `uvx` start, as the programs they run; a script that exists but
cannot be opened waits for the principal's code, and so does a line of Python in a script that reaches synthesis, the
script's bytes bound to the code (typed on the command, the same line is refused). A `PYTHONPATH` on the line counts
against a program's proof unless its folders are there when judged, hold no module the program imports, no
`sitecustomize` or `usercustomize`, and nothing that hides a module of Python's own installation (its standard library and
site-packages; a folder with no `__init__.py` hides nothing) but a `synthesis` package byte for byte the guard's own, and
are neither written into by the line nor beside another program on
it that may fill them unseen; a module the line writes where the program starts counts as a file already there does. The release's own scripts are trusted: those in the synthesis home's
`bin` (the CLI's launcher, reached by any link, among them), `current` and `releases`, and those of the release the
guard runs from; a launcher anywhere else is read as what it runs. For pytest, the test files it collects and the conftests it loads are read for a
writer approvals rest on, or synthesis loaded another way, unless each test file runs with the synthesis home at a
temporary path for every test. That is trusted only from a fixture that sets `SYNTHESIS_HOME` (or `HOME`) from the
test's `tmp_path` and is autouse, in a conftest above the file or in the file itself, or that every test in the file
requests. Only a test, and the function-scoped fixtures it uses, run under that fixture: a writer named (under any name
it is imported by, or through `getattr` with its name written out), a path of synthesis's taken, or synthesis loaded
anywhere else leaves that file read. That is a test module's or a conftest's top level, its class bodies, decorators and
defaults, the file's own functions they call, xunit setup and teardown, fixtures scoped wider than a function, pytest's
hooks, and a plugin of the agent's own named with `-p`.

## Contents

- [Keys](#keys)
- [Commands judged by name](#commands-judged-by-name)
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
| `deploy_content` | `content/posts/**/index.md`, `**/src/content/articles/*.md` | Globs of the dated content files the date rules read: the nested-date and the flat layout. A unified catalog's article files go here too (for example `astro-site/content/articles/*/index.md`). Not a list of strings: deploys block. |
| `deploy_catalogs` | none | Globs of JSON catalogs whose `articles` list gives each article's `id` and `published` time, and, where one is documented, the `publishedInstantOverride` instant that replaces it (for example `astro-site/content/catalog.json`). The date rules read each article as `<catalog>#<id>`, at the commit or working tree where they read front matter, so an instant kept only in the catalog cannot move or go live early unseen. A catalog that cannot be read, or a value that is not a list of strings: deploys block. |
| `deploy_also_renders` | none | Map from a site repository to the other repositories its build renders from their working trees (for example a personal site that pulls in other sites' articles). Deploying the site also applies the date rules to those repositories, so a future-dated article there cannot go live early through it. An entry `{"variable": "NAME", "default": "<path>"}` stands for the checkout holding the path the deploy command hands the build in `NAME` (`NAME=/abs/path/catalog.json bash build.sh ...`), else `<path>`: the tree a build reads from another worktree is the one checked. A value the guard cannot follow to a checkout (a variable or a relative path in it, or no checkout around it), or an entry of another shape: deploys block. |
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
| `judge` | none (no judge) | A model that reads content before a check decides (M38), first for the reply check's shortcut phrasing: each reply the list flags goes to it; on that check a hit clears only when the judge's first reading and a second, narrow question both pass it surely, and a hold sends it back with what the judge read. `local`: `models`, the local models to ask through Ollama on this Mac's loopback address, the first one installed answering; `url` (default `http://127.0.0.1:11434`, loopback only); `keep_alive` (default `30m`, so a session's judge stays warm). `deadline_seconds` (default 3, at most 8: the Stop hook gives the judge 8 seconds inside its own 10, since 2026-11-15): past it, or with no model installed, no server or an answer that is not a strict verdict, the list decides as before. `subscription`: the plan of the harness the reply came from, through its own command line, so no one buys API credits for the judge; it reads a reply first where `local` is left out: an entry for `claude-code` (`claude -p`) or `codex` (`codex exec`), each a `model` and optionally a `command` (default `claude` or `codex` on PATH; used only where it resolves to that harness's own program, as bound below) and an `effort`, and `leave_out`, the workspaces whose replies it never reads (one whose plan is not confirmed for its work keeps the word list). It runs on the plan's sign-in alone (an API key, gateway token or cloud account in the environment is kept out of its run), so its verdicts count against the plan's usage and cost nothing more; give it `deadline_seconds` 8: a flagged reply's two questions took up to 7.2 seconds at the 95th percentile on the plan (2026-11-15), and inside the default 3 most go unanswered and the list decides; `synthesis doctor` warns, with the fix, when a configured plan's judge would not answer or answers past the deadline. A harness without an entry, Muse among them, keeps the other judges. `cloud`: the cloud model, the judge itself when neither `local` nor the reply's `subscription` judges it and otherwise a second opinion only where the first verdict is unsure: `provider` (`anthropic`), `model`, `keys_file` (the file that holds the keys, read at call time: its keys are never logged, cached or shown) and `keys` (`default`, the dotted path of the key for every workspace, beside it a workspace's own path, or null for a workspace whose key is not confirmed, which keeps the word list), `price_per_mtok` `{input, output}` in dollars, `monthly_cap_usd` (default 10: past it the other judges, or with none the word list, decide alone for the rest of the month and the principal is told once), and optionally `effort` and `url`, which is only the provider's own host over https (`https://api.anthropic.com`, the default). The request asks for adaptive thinking and the verdict's strict schema; a refusal, an answer that did not finish or any error is no verdict. Any other shape is said in the reply sent back, and the list alone decides until it is fixed. Every judge setting comes from this file, which a session can write, so each is bound: `local.url` to this Mac's loopback address; a `subscription` entry's `command` to the harness's own program, that is `claude` or `codex` as the hook's PATH resolves it, or in its known install locations (`~/.local/bin`, `/opt/homebrew/bin`, `/usr/local/bin` and the apps' own folders); anything else runs nothing, the list decides, and the doctor names the setting, while a program planted in one of those folders the person can write, or earlier on PATH, counts as the harness's own and is on the open list in `docs/runtime-integration.md`; `model` to a plain name and `effort` to letters, values on the harness's command line and never options of their own; `cloud.url` to the provider's own host over https, so the reply, the principal's last message and the key go nowhere else; each `cloud.keys` path to one that ends in the provider's name, so the keys file gives the judge that key and nothing else; `deadline_seconds` to at most 8. A section outside these bounds is said in the reply sent back and by the doctor, and the list decides until it is fixed. What it reads: [reply-and-provenance.md](reply-and-provenance.md#the-judge). |

## Commands judged by name

No key turns this on or off; it depends on what is installed where. The shell guard judges some commands by their
name: the shells, the interpreters, the usual readers, the file utilities, the wrappers (`env`, `nohup`, `timeout`,
`xargs`, `npx` and their like), the editors and the unpackers. Since 22.32 a command word of one of those names that
leads to a script (a text file, with a `#!` line or none) rather than a compiled program is also judged as that
script, under the rules for scripts, beside its judgment by name: a script of the agent's named `bash` or `ls` waits
for the code where it, or its command, names a protected folder, as a script with a name of its own does. The guard
finds the file as the shell would: by the word's own path, or on PATH as the hook's process has it and on any PATH the
line gives itself. A builtin the shell runs itself (`echo`, `cd`, `test`, `printf` and their like) is not looked up;
the same name started by `env`, `nohup`, `xargs` or `find -exec` is. A word written as a pattern is the file it
expands to. A file the line copies or links into place before it runs it is judged as what it copies, and one it
writes itself (a redirect, `tee`, an edit in place) is read as the line; a change of mode or owner writes nothing it
runs.

The real commands are compiled programs or links to them, wherever they lie: the system's, Homebrew's `python3` and
`node`, a venv's `python`. These commands really are scripts, and pass by their name where their installer puts them.
Where no program of the agent's writes, any of these names passes under its own name (or that name with a version or
a suffix after it); in a folder the user writes, only the names that installer provides there:

| Where the file lies | Which names |
|---|---|
| Installed by root: the file and every folder above it owned by root and writable by neither this user nor its groups | Any, by its own name: macOS's `/usr/bin/cd`, `read`, `wait` and `command`, `shasum`, `irb`, `wish`; Linux's `which`, `egrep`, `fgrep`, `zcat`, `gunzip`, `uncompress` |
| The runtime's own `bin/` (protected), also through a link elsewhere on PATH | Any, by its own name: `synthesis` |
| An npm package's bin: `<prefix>/bin/<name>` linked into `<prefix>/lib/node_modules/` (or Debian's `<prefix>/share/nodejs/`), or a project's `node_modules/.bin/<name>` | `npx`, `pnpx`, `tsx`, `ts-node` (from Homebrew, nvm, fnm, a distribution or a project) |
| A version manager's shim, `<root>/shims/<name>`: pyenv, rbenv, nodenv, asdf, jenv, plenv, goenv, luaenv or phpenv, or the root its variable names (`PYENV_ROOT` and the like) | The interpreters (`python3`, `node`, `ruby`, `perl` and their like) and the npm bins above |
| Homebrew's own Cellar (`HOMEBREW_CELLAR`, or `Cellar` under `HOMEBREW_PREFIX`, which `brew shellenv` sets, `/opt/homebrew` or `/usr/local`) | `groovy`, `scala`, `elixir`, `jruby`, `7z`, `7za`, `irb`, `shasum`, `gunzip`, `zcat`, `uncompress`, `egrep`, `fgrep`, `synthesis` and the npm bins above |

pip3, pytest, npm and a venv's `activate` are scripts too, but the guard judges them by none of these names, so they
are untouched. A script another installer puts in a folder the user writes under one of these names (a JVM tool
from sdkman, say) is read as the script it is, which waits only where it or its command names a protected folder.
Measured on 60 days of records (2026-09-16 to 2026-11-15, 252,649 distinct commands), every command word of these
names led to a compiled program, a builtin, nothing, or a script of this table. A compiled program under such a
name, an installed script rewritten where its installer put it in a folder the user writes, and a look-alike set
where such an installer puts its scripts are judged by the name (the open list, in `docs/runtime-integration.md`).

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
  "reply_file_links": true,
  "judge": {
    "local": {"models": ["gemma4:26b", "gemma4:12b"], "keep_alive": "30m"},
    "deadline_seconds": 3,
    "subscription": {"claude-code": {"model": "claude-haiku-5-5", "effort": "low"}, "leave_out": ["clientco"]},
    "cloud": {"provider": "anthropic", "model": "claude-opus-5-5", "keys_file": "~/.config/agent-keys/keys.yaml",
              "keys": {"default": "default.anthropic", "clientco": null},
              "price_per_mtok": {"input": 4.0, "output": 20.0}, "monthly_cap_usd": 10, "effort": "low"}
  }
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

## A configuration file a script of the release follows

When the runtime's copy of a script runs, the guard reads each `.agents/<name>` or `.claude/<name>` file the script's
text names, from the folder it runs in upward and above a folder or workspace its words name, as it reads the line.
A path in that file that is a protected folder, lies inside one or holds one makes the run wait for the principal's
code. The home folder itself holds the synthesis home, so a configuration that names it, such as the meeting
fetcher's archive folder set to `~`, waits as well; one that names the project's own folders does not.

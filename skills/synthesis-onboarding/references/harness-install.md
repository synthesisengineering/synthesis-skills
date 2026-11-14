# Installing in each harness (setup.py)

## Contents

- [What setup does, in order](#what-setup-does-in-order)
- [Each harness's own commands](#each-harnesss-own-commands)
- [Codex settings setup owns](#codex-settings-setup-owns)
- [The runtime, the commit check and the CLI](#the-runtime-the-commit-check-and-the-cli)
- [The day-end launcher and nudge](#the-day-end-launcher-and-nudge)
- [The hourly copy of session transcripts](#the-hourly-copy-of-session-transcripts)
- [First config](#first-config)
- [Hook trust stays with the person](#hook-trust-stays-with-the-person)
- [An approval that lasts through releases (`--codex-user-hooks`)](#an-approval-that-lasts-through-releases---codex-user-hooks)
- [Restart, verify, uninstall](#restart-verify-uninstall)
- [One collection instead of the whole set](#one-collection-instead-of-the-whole-set)

## What setup does, in order

`python3 <checkout>/skills/synthesis-onboarding/scripts/setup.py` with no command does
everything, asking only what it cannot detect: the plugin in every harness it finds,
Codex's settings, the stable runtime, the commit check (asked), a first config (fresh
installs only), then optionally a workspace or an organization. Each part is also its
own command (`plugin`, `workspace`, `org`, `uninstall`). Every run prints one line per
step and ends with the restart sentence. `--no-input` never asks and names the flag it
needed.

`--dry-run`, with any command, says what each step would do, in conditional wording
(`would clone`, `would install`, `would write it`), and writes nothing in the person's
folders or synthesis state: no harness command beyond reading its plugin list, no fetch
into an existing checkout, no sign-in, and no skill copy, ledger, record, archive,
runtime file or instruction file. What it must read to say that, an organization's
configuration and skills or a knowledge repository's `repos.yaml`, it clones into a
temporary folder that it removes; an existing checkout is judged against its upstream as
last fetched. `onboard.sh` with `--dry-run` runs setup from a temporary clone too and
leaves `~/.synthesis/v5/source` as it is. A dry run ends with "Dry run: nothing was
changed." instead of the restart sentence. (2026-10-20: `setup.py org --dry-run` had
cloned, copied the organization's skills and rewritten `AGENTS.md`.)

A harness that is not on the Mac is skipped with a line saying so; it never fails the
run. The Codex CLI ships inside the ChatGPT desktop app and is on PATH only in Codex's
own shells, so setup looks in the app's install folders too (the same finder doctor
uses; `SYNTHESIS_CODEX_BIN` overrides it, and an empty value means "absent"). The Claude
desktop app keeps its own Claude Code under
`~/Library/Application Support/Claude/claude-code/<version>/`, off PATH; setup uses the
newest version there when no `claude` is installed elsewhere (`SYNTHESIS_CLAUDE_BIN`
overrides it). (2026-10-30: a Mac with only the desktop app had nothing to install into.)
Before each harness's install, setup prints a line naming it, because the harness's own
commands fetch the plugin with nothing else printed for up to a minute. When none of the
harnesses asked for is on the Mac, setup stops before changing anything and names the app
to install; it no longer installs a runtime that nothing would use.

Setup keeps a compaction brief in each synthesis workspace's instructions (a folder whose
`CLAUDE.md` is `@AGENTS.md`): the `## Compact Instructions` section in
`references/compact-instructions.md`, between `synthesis-setup:begin/end compact-instructions`
markers. Claude Code follows that section when it compacts, also from an `AGENTS.md` the
`CLAUDE.md` imports (tested 2026-10-31 with a marker line in the summary); Codex can only replace
its whole compaction prompt, globally, and Muse has no setting, so they rely on the files and the
session-start hook. A workspace made by setup and an organization's generated instructions get
the block when they are written. A file the person wrote gets it only with their yes, or with
`--compact-brief`; a block already there is refreshed on every run, since it is setup's own.

`onboard.sh` checks its own prerequisites before it fetches anything. On a Mac without
Apple's Command Line Tools (`xcode-select -p` fails), which provide `git` and `python3`, it
runs `xcode-select --install`, says to click Install, and waits up to an hour for the tools
before carrying on, the way Homebrew's installer does; a dry run stops there instead. A
missing `git` or `python3`, or a `python3` older than 3.9, is named and nothing is fetched.

## Each harness's own commands

Setup reads each harness's plugin list as JSON (Claude Code may print a list or a
`plugins` map; Codex prints `installed`). A list it cannot parse stops that harness with
a message that carries the harness's own last line; it is never taken to mean "not
installed". The JSON is read past any words a command prints before it.

Codex is asked for the plugin's own marketplace first
(`codex plugin list --json -m synthesis-engineering`), the one setup installs from: its
whole listing fetches Codex's remote plugin catalog again when its copy is over three
hours old (73 MB and 52 s on 2026-11-13), and asked for one marketplace it fetches none,
so an update, which is every release, does not wait on the catalog. What that marketplace
does not show, and a Codex that does not know the option, are asked of the whole listing,
which gets five minutes where the first gets one: "not installed" is said only from
there. A listing that does not answer within its limit stops that harness, and the next
listing is not started after it. `synthesis doctor` asks in the same order with its own
limit of 45 seconds for each listing; where the whole one does not answer, its line says
to run `codex plugin list` once, since the limit stops the fetch each time.

A copy of the plugin installed from another marketplace (a fork's, by its name in the
listing) is not given a second copy beside it: setup stops, names the copy and the
command that removes it. Uninstall removes the copy that is there, by that name.

A Codex command that takes longer than two seconds to say its version is passed over
when another install answers, and is still the Codex on the machine when none does:
setup, a release and the doctor go on with it, and its own commands then say what is
wrong if it answers nothing. A command that exits with an error is not Codex.

- **Claude Code**, new: `claude plugin marketplace add synthesisengineering/synthesis-skills@<ref>`,
  then `claude plugin install synthesis-skills@synthesis-engineering`. Update:
  `claude plugin marketplace update synthesis-engineering`, then
  `claude plugin update synthesis-skills@synthesis-engineering`.
- **Codex**, new: `codex plugin marketplace add synthesisengineering/synthesis-skills --ref <ref>`,
  then `codex plugin add synthesis-skills@synthesis-engineering`. Update:
  `codex plugin marketplace upgrade synthesis-engineering` before `codex plugin add`,
  because Codex installs *from* its git marketplace snapshot — skipping the upgrade
  installs the previous release while appearing to succeed.
- **Muse** installs from a local bundle: setup exports the checkout into
  `~/.synthesis/v5/muse-bundle` and runs `muse plugins install <bundle>`. Muse records
  that absolute path and refuses a second install from another path, so later runs
  refresh the recorded bundle in place and run `muse plugins update synthesis-skills`.
  Setup first confirms this Muse build's `plugins` command offers list, install and
  update; a build without them is refused before anything is staged. A record pointing
  at a folder setup does not own is refused with the removal command to run.

`--ref` picks the marketplace ref: `stable` (the default for a new install), `main`, or
an exact `vX.Y.Z` pin. Without `--ref`, an existing install keeps the ref it follows, so
an update never downgrades an install that follows a newer channel. With `--ref` set to a
different ref, setup removes the marketplace and adds it again on that ref (a marketplace
added earlier on another ref answers "already" and is re-added). An installed but
disabled plugin is reported, never silently enabled.

## Claude Code setting setup owns

Claude Code deletes a session's transcript 30 days after its last use unless `cleanupPeriodDays` is set. When the
key is absent, setup sets it to 3,650 in Claude Code's `settings.json`, after copying the file to
`~/.synthesis/v5/backups/`, so the record outlives every export interval (`synthesis sessions export`). A value the
person set stays; the doctor warns when it is under a year and fails when it is unset.

## Codex settings setup owns

Setup changes only these keys in `~/.codex/config.toml`, after copying the file to
`~/.synthesis/v5/backups/`:

- `[features] hooks = true`, inside a marked block. If the person set `hooks = false`,
  it stays, and setup says no synthesis guard will run in Codex.
- `project_doc_max_bytes` at least 98,304 (raised if lower, added if absent). Codex's
  default, 32 KiB, truncates the global rules plus a workspace's instructions.
- `project_doc_fallback_filenames = ["CLAUDE.md"]` when the key is absent; an existing
  list without `CLAUDE.md` is reported and left as set.
- The board folder, `~/.synthesis/v5/board`, and the outbox, `~/.synthesis/v5/outbox`,
  made writable from Codex's sandbox, which otherwise writes only the workspace and temp
  folders, so a Codex session can claim files and post on the board, and stage a file it
  attaches to a message. Codex reads permission profiles (0.166): setup adds each folder
  as a `write` rule to the person's own default profile; when the default is a built-in or
  unset, it writes a `synthesis` profile that extends it (`:workspace` when unset) with
  those rules, inside a marked block, and names it in `default_permissions`. A config that
  still sets `sandbox_mode` gets the folders in `[sandbox_workspace_write] writable_roots`
  instead, which is what Codex reads then. An install that granted the board alone gains
  the outbox on the next run, and setup makes both folders, since the sandbox may write
  inside a granted folder and never create it. Only those two are granted:
  `~/.synthesis/v5/state` holds approvals and send windows, which no sandboxed agent may
  write, and the doctor fails a grant that covers it, as it fails a config that leaves
  either folder out.

Other keys, including feature keys the Codex app writes itself, are never touched. A
rerun changes nothing.

## The runtime, the commit check and the CLI

Setup installs the runtime from the checkout to `~/.synthesis/v5/current`, with the
stable hook at `~/.synthesis/v5/bin/synthesis-hook` (each harness's SessionStart moves it
forward when the plugin it loaded is a newer release, never back). It links `~/.local/bin/synthesis` to
`~/.synthesis/v5/bin/synthesis` only when that name is free; another install's launcher
is left alone and setup says to put `~/.synthesis/v5/bin` first on PATH.

The commit check (secrets, unapproved disclosures, other sessions' claims) runs for every
repository only with `--git-hooks` or a yes to setup's question: it points the global
`core.hooksPath` at `~/.synthesis/v5/git-hooks`. The value it replaces is recorded and
named in the output, because git stops running hooks from the old path; uninstall
restores it unless the person changed it since. Each repository's own
`.githooks/pre-commit` and `.git/hooks/pre-commit` still run after the check.

## The day-end launcher and nudge

Every install copies the rituals skill's `day-end` launcher and `day-end-nudge.sh` into
`~/.synthesis/v5/bin/`, so they ride each release beside the runtime the nudge reads.
`--day-end [auto|codex|claude]` then links `~/.local/bin/day-end` to that copy (a real
file at that name is refused, never replaced), records which agent the launcher opens
(`~/.synthesis/v5/agent-cli`), and writes the LaunchAgent
`~/Library/LaunchAgents/com.synthesis.day-end-nudge.plist`, which runs the installed nudge
at 16:55 on weekdays (the evening banner, the critical-deadline alert, and a fixed banner
when a harness's guard has not been seen to run since the doctor, within a day, found its
hooks waiting for approval, or when nothing has looked since synthesis was last updated),
with the folders the install was made with (as the hourly copy
below). An older schedule under that label is archived first and unloaded;
the new one is loaded with `launchctl bootstrap`, or only written with `--no-launchctl`.
The banner text is generic and fixed (others see banners on screen-shares). Uninstall
unloads and removes only a schedule and a link that point at this install's copies: a
schedule is this install's when the program its line runs is this install's nudge, the
whole path (see the next section).

## The hourly copy of session transcripts

`--sessions-export` writes the LaunchAgent `~/Library/LaunchAgents/com.synthesis.sessions-export.plist`, which
runs the installed `synthesis sessions export --all --scheduled` and then `synthesis sessions sync` every hour and
at login, through a login shell so git finds the person's credentials. It writes
`/tmp/com.synthesis.sessions-export.log`. The scheduled export then fetches each knowledge root and sessions repo,
never merging (config `scheduled_fetch: false` turns it off). `--scheduled` marks the run as the schedule's own: `synthesis doctor`
knows the schedule by that mark, and fails a loaded schedule that has made no run of its own in a day, since
launchd runs what it loaded and a file replaced since does not show there.
The sync runs whatever the export's exit status: an export that could not copy something exits 1, and what it
did copy still reaches the sessions repos.
The job runs with the folders the install was made with: each of `SYNTHESIS_HOME`, `CLAUDE_CONFIG_DIR`, `CODEX_HOME`
and `XDG_DATA_HOME` that was set when the schedule was installed is set again in the job, after the login shell's
own, so the job reads the transcripts and writes the archive of the install whose command it runs. One that was
not set is left to the login shell. After moving any of those folders, run the command again. The weekday nudge's
job carries them the same way.
One label holds one schedule: another install's schedule under that label is archived first
(`<synthesis home>/archive/<time>/`, and the setup says where), since its hourly copy stops when this one
replaces it; this install's own older schedule is replaced in place. Whichever was loaded is unloaded first;
`--no-launchctl` writes the file without loading it.
`synthesis doctor` then checks that the schedule is loaded, that it is this install's and that an export
finished within a day. Uninstall unloads and removes only a schedule that is this install's. A schedule is this
install's when every command it runs is: the program each command of its line runs is this install's `synthesis`,
the whole path. A schedule whose command only ends or begins like that path, that hands the path to another
program (`echo`, `env`, a shell's words) or sets it as a variable, that runs another program beside it, or whose
file cannot be read, is not this install's. The setup and the doctor ask the same test (`install.runs_only` in the
plugin's core). Uninstall keeps such a schedule and says so. The doctor fails on it, since this home's stamp can
be fresh from its own sessions while the label's one schedule copies for another install: it names the program
the schedule runs and this install's command, and running `--sessions-export` again puts this install's schedule
back, setting the other aside. Without the schedule, transcripts are copied only when a session runs resume,
handoff or a ritual.

## First config

On a fresh install (an empty `~/.synthesis/v5/config.json`), the interactive run asks two
questions and writes the answers: the knowledge repositories to read (blank finds
`~/workspaces/*/ai-knowledge-*`) and words or phrases never to send. Home paths are
written as `~`. Without config, every send or draft still asks for the person's approval
of the exact text, and deploys need approval too; no guard silently blocks. An
unreadable config makes the send and deploy guards block until it is fixed, and setup
says so.

## Hook trust stays with the person

Codex runs a plugin hook only after the person approves its exact definition in
`/hooks`; Muse holds hooks until `muse plugins approve synthesis-skills`. Setup never
approves either. `synthesis doctor` names every hook still waiting. Codex also ties
an approval to the installed plugin's files, so after every update it runs none of
synthesis's hooks until they are approved again in `/hooks`; doctor checks that the
way Codex does. The next section is the choice that ends that wait.

## An approval that lasts through releases (`--codex-user-hooks`)

Codex keeps a hook declared in its own `hooks.json`, beside `config.toml`, trusted by
its declaration alone, also when the script it runs changes (codex-rs hooks discovery;
probed on Codex 0.167, 2026-11-13 and 14). All four synthesis hooks run one stable path,
`~/.synthesis/v5/bin/synthesis-hook`, which each release updates, so declared there they
are approved once and stay approved through every release that leaves the declaration
as it is. Between a release and the approval the plugin's own hooks wait for, Codex
runs no send guard, deploy guard, reply check or session-start context (six times on
2026-11-13).

`setup.py plugin --codex-user-hooks` (or with no command) turns it on:

- It declares the plugin's four events in `$CODEX_HOME/hooks.json` (`~/.codex/hooks.json`
  when `CODEX_HOME` is unset), each group as the plugin's `hooks/hooks.json` writes it:
  the same matcher and timeout, each command the stable hook with its event. The
  plugin's session start also names the plugin's folder, so a first run can install the
  runtime; the user-level one calls the stable hook alone, since setup has installed the
  runtime by then. The guard's command is the plugin's own, which ends so that a stable
  hook that cannot start or crashes is exit 2 with one line of reason, which Codex blocks
  on (5.21.0); its `"onFailure": "block"`, for Claude Code, is carried too, and Codex hashes
  the hook without it. Codex hashes the command, so 5.21.0 asks for the guard's approval
  once again; for anyone switching to this option in this release that is the one
  approval they give when switching. A later change only in a field Codex does not hash
  keeps an approval, and setup says it stays instead of asking (probed on Codex 0.167,
  2026-11-14). Setup's groups go after the person's own for the same event, and the
  person's hooks stay as they are. An event the person already declares with the stable
  hook (as the program its command runs, not a mention) is kept as written and not
  declared twice; the plugin's copy of it goes off only when theirs holds the plugin's
  declaration, the same matcher and timeout. A narrower one keeps the plugin's own on
  beside it, and setup says to edit or remove theirs. Setup records the groups it wrote
  (`~/.synthesis/v5/state/codex-user-hooks.json`) and treats only those as its own.
- It switches the plugin's own copy of each covered event off by its state key in
  `config.toml` (`[hooks.state."synthesis-skills@synthesis-engineering:hooks/hooks.json:<event>:0:0"]`,
  `enabled = false`), so no event runs twice. A key Codex already holds an approval
  under gains the line in that table, never a second table, and an `enabled` key spelled
  in quotes is the one switched; every line setup adds ends
  `# synthesis-setup: codex-user-hooks`, and Codex keeps it when it writes the file, a
  "Trust all" at its startup review included. Setup writes no approval.
- It says to approve the four once in Codex's `/hooks`; that stays the person's to do.

A rerun changes nothing. Each of these stops it before anything is written: a `hooks.json`
Codex would not read (not JSON, a top-level key other than `hooks` and `description`, a
hook of a type Codex does not know); a `config.toml` that does not parse; hook state held
as an inline table (`hooks = {...}`, `state = {...}`), where an added table would define
it twice; an edit that would not parse once composed (setup reads it back with its strict
reader, and with Python's own `tomllib` where Python has it); and a file that changed
while setup was editing it, say Codex recording an approval. Each file is copied to
`~/.synthesis/v5/backups/` before a change. Turning the option on writes `hooks.json`
first and off writes `config.toml` first, and a write that fails midway puts back what
was written, so no stop between the two leaves an event with neither copy. A symlinked
file is written through to its target, a file keeps its mode (a new one is 0600), no
temporary file outlives a failure, and lines keep their endings. Once it is on, setup's
`plugin` command and the release script keep the declaration in step with the plugin
Codex holds after each install or update: a release that changes the plugin's
`hooks/hooks.json` (5.13.0 added `shell_command` to the shell hook's matcher) changes the
user-level copy in its place, and Codex asks once for the changed declaration. A run
without the flag keeps the choice; the mark's words in a comment turn nothing on.

`setup.py plugin --no-codex-user-hooks` turns it off, whatever the install says, since it
needs no network, and `setup.py uninstall` does too, before it removes the runtime those
hooks run: if it cannot, uninstall removes nothing and exits 1. Each takes out the groups
setup recorded, its marked lines (found by their table, key, value and mark, however a
formatter spaced them), a header it added once no key is left under it, and a
`hooks.json` it created; the person's own lines and comments stay. Approvals Codex
recorded stay, as Codex's own. A hook of the person's declared after setup's in the same
event moves up one place, so Codex asks for it again.

What it gives up is Codex's second look at a hook whose code changed. With the plugin's
own hooks, Codex asks again whenever a release changes what they run, which protects
anyone installing someone else's plugin from an update they did not look at. With the
user-level declaration, one approval covers whatever a later release puts at the stable
path. On a publisher's own machines that second look guards only against their own
releases, so the option is recommended there; everyone else keeps it off unless they ask
for it.

Two things to expect. Codex's startup review still lists the plugin's
switched-off copies as new or changed after a release, since it counts a hook's trust
and not whether it is on; whatever the answer there, the user-level hooks run. And a
Codex session's start no longer moves the stable runtime forward to a newer plugin, since
a user-level hook has no plugin folder to name: the release script, `setup.py plugin`,
or a session in Claude Code or Muse does.

`synthesis doctor`'s `codex hook trust` line then judges the user-level hooks (Codex keys
each by `hooks.json`'s path under its home's real path, then the event, group and place)
and treats the plugin's switched-off copies of covered events as intended. It fails a
copy left on beside a covering declaration, which would run twice once approved; an
event declared twice at the user level; a declaration that does not hold the installed
plugin's, saying to run setup again for setup's own and to edit or remove the person's;
setup's switch with nothing covering its event; a `hooks.json` Codex would not read while
the option is on; and hook state held as an inline table. None of these is an approval
the person gives. Without the option, the line is as before, and a `hooks.json` of the
person's that Codex would not read is a `codex hooks file` warning of its own.

## Restart, verify, uninstall

- Restart each harness after setup: a client restart reloads hooks and skills without
  a new conversation (lesson 2026-08-17), so the person can resume where they were.
- `synthesis doctor` then reports every part; `synthesis doctor --latest` also compares
  with the published release.
- `setup.py uninstall [--dry-run]` removes the plugin with each harness's own command
  (`claude plugin uninstall … --yes`, `codex plugin remove …`, `muse plugins remove …`),
  takes out the plugin's hooks declared in Codex's own `hooks.json` and their switches
  (above), restores `core.hooksPath`, removes only files the install wrote that are
  unedited, and keeps `config.json` and `state/` (settings, board, approvals), saying
  what it kept.

## One collection instead of the whole set

The whole set is what setup installs, and what to recommend: it alone has the hooks, the
runtime, the guards, the board and the rituals' state. For a person who wants one
discipline and no hooks, each release also publishes five collections, plugins of the
same skills grouped by what they do, as the `collections` branch of this repository: core
(`synthesis-skills-core`, which every other collection builds on), project management,
engineering, writing and chief of staff (`synthesis-skills-<name>`). Each skill names its
collection in its frontmatter (`metadata.category`); the README lists every collection's
skills, and the skills manager's `references/collections.md` says how they are built.

Setup does not install a collection; each harness's own commands do, with no approval
step, since a collection registers no hook. For engineering:

- **Claude Code:** `claude plugin marketplace add synthesisengineering/synthesis-skills@collections`,
  then `claude plugin install synthesis-skills-engineering@synthesis-collections`, which
  installs the core with it as its declared dependency.
- **Codex:** `codex plugin marketplace add synthesisengineering/synthesis-skills --ref collections`,
  then `codex plugin add synthesis-skills-core@synthesis-collections` and
  `codex plugin add synthesis-skills-engineering@synthesis-collections`. Codex resolves
  no dependency between plugins, so the core is its own line.
- **Muse:** `muse plugins marketplace add synthesis-collections https://github.com/synthesisengineering/synthesis-skills.git#collections`
  (Muse names a branch after `#`), then `muse plugins install synthesis-skills-core@synthesis-collections`
  and `muse plugins install synthesis-skills-engineering@synthesis-collections`.

To update after a release: in Claude Code, `claude plugin marketplace update synthesis-collections`,
then `claude plugin update` for the core and for each collection (updating a collection
leaves its dependency as it was); in Codex, `codex plugin marketplace upgrade synthesis-collections`,
then `codex plugin add` for each again; in Muse 1.4.20, `muse plugins marketplace update synthesis-collections`,
then `muse plugins remove <plugin>` and `muse plugins install <plugin>@synthesis-collections`
for each, since `muse plugins update` refreshes from the snapshot it installed from. Each
of these was run in isolated harness homes on 2026-11-14, from a local copy of the branch.

What a collection does not have: no hook runs, so nothing checks a send, a deploy or a
commit and no approval code exists; there is no `synthesis` command, so no board, claims,
doctor or handoff, and a script that imports the runtime says in one line that it is not
there. A skill's link into another skill's folder resolves only inside one plugin: a
collection is installed in a folder of its own, apart from the core's, so a link from it
into the core, or into another collection, leads nowhere, and the skill it names is found
by its name. To move to the whole set, install it as above (its marketplace sits beside
the collections' in every harness), then remove each collection and the core, so that no
skill is installed twice: `claude plugin uninstall <plugin>@synthesis-collections --yes`
(Claude Code keeps the core when the collection that brought it goes),
`codex plugin remove <plugin>@synthesis-collections`, or `muse plugins remove <plugin>`.

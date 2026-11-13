# The conformance audit in v5

## Contents

- [The five planes](#the-five-planes)
- [Source: the lint](#source-the-lint)
- [Installed: what doctor checks](#installed-what-doctor-checks)
- [Live: proving the harness ran it](#live-proving-the-harness-ran-it)
- [Continuity: the handoff exercise](#continuity-the-handoff-exercise)
- [Skill catalog contract](#skill-catalog-contract)
- [Skill-output provenance](#skill-output-provenance)
- [Repair from source](#repair-from-source)

## The five planes

Treat cross-agent portability as a continuously tested system, not a file-count
comparison. Verify five planes, and name the plane whenever two facts appear to
conflict:

1. **Source:** version-controlled skills, instructions, client adapters, hooks,
   project state, and configuration.
2. **Installed:** each harness's plugin bytes, the stable runtime, hook wiring,
   instruction budgets, runtime configuration, and Codex's authoritative hook
   trust state. Never infer or write trust state.
3. **Native (live):** what a genuine lifecycle event did in a real session. A static
   script probe is not live evidence.
4. **Continuity:** board claims, each session's active project, the project records,
   and explicit remote publication for a machine handoff.
5. **Capability:** authenticated read-only outcomes and explicitly supported,
   unsupported, or unverifiable product surfaces.

Runtime state determines current behavior; canonical state determines what the next
deployment should produce. UNKNOWN never becomes PASS: a check that could not run says
so.

## Source: the lint

In the source checkout, `python3 -m pytest -q tests/test_source_lint.py` (CI runs it on
every pull request): the three plugin manifests agree; the CHANGELOG's newest entry is
that version; skill names are unique and match their folders; every `depends_on`
resolves; every skill has an SPDX license and `agents/openai.yaml`; Muse's manifest
lists every skill; Codex's catalog fits its 8,000-character fallback budget; no personal
path appears anywhere (a personal path once reached the public repository); and every
config a skill documents as fail-closed ships an example.

## Installed: what doctor checks

`synthesis doctor` prints one line per check after a first line that says healthy or not;
`--json` prints the same as JSON; `--latest [REF]` also asks GitHub whether a newer
release exists (its only network call, so it runs only on request). Doctor never writes
harness state. It finds each CLI on PATH or in the vendor's install folders (the Codex
CLI ships inside the ChatGPT desktop app), rejecting a stale Codex launcher with a
bounded `--version` probe.

Each line carries its check's name. Every name has an item below, which opens with the
names it covers (`<harness>` is `claude`, `codex` or `muse`; `<ws>` is a workspace).
`tests/test_doctor.py` reads the names from `synthesis/doctor.py`, so a check added
there with no item here fails:

- `runtime`, `hook script`, `hook self-test`: the stable runtime resolves to an installed
  release whose files are as installed, its hook script is the shipped text, and the
  real hook denies `rm -rf ~` within the latency budget;
- `wait check`: the turn-end check sends back a canned reply that announces a wait with
  nothing armed, so a wait cannot end a turn unseen;
- `config`: `config.json` parses as an object; when it is missing the guards run on
  defaults, and one that does not parse makes the send and deploy guards block everything;
- `board`: no board file is left under `state/`, where no session has read one since
  5.1.18;
- `sessions repo <ws>`: each workspace's sessions repository is cloned where the config
  says, was synced within two days, and is under 3 GB;
- `sessions export`: the last copy of session transcripts left none it could not copy;
  and where the hourly copy is scheduled, its job is loaded, runs this install's own
  `synthesis` command, an export has finished within a day, and the schedule itself
  has made one within a day;
- `harnesses`: at least one of the three harnesses was found on this Mac;
- `<harness> plugin`, `<harness> package`, `<harness> hooks`: per harness, the plugin
  installed and enabled, its code equal to the runtime (never a version label), all four
  events wired to the stable hook. A listing that does not answer within 45 seconds
  says nothing about the install, and that harness's plugin line warns `cannot tell`.
  Codex is asked for the plugin's own marketplace
  (`codex plugin list --json -m synthesis-engineering`), for which it fetches no remote
  catalog. Its whole listing, which fetches one when Codex's copy is over three hours
  old, is asked when the first shows no plugin or prints no JSON, so the Codex lines
  can take two limits; "not installed" is said only from the whole listing, and when
  that one does not answer the line says to run `codex plugin list` once. A Codex
  command that takes over two seconds to say its version is passed over only for
  another install that answers; with none, the doctor goes on with it. A listed
  plugin whose folder is not there fails its package line;
- `claude transcripts`: Claude Code keeps transcripts past its 30-day default
  (`cleanupPeriodDays` is set, and to a year or more);
- `codex hooks feature`, `codex instruction bytes`, `codex board access`,
  `codex instruction chain`, `codex hook trust`, `codex skill catalog`: for Codex,
  `[features] hooks = true`, `project_doc_max_bytes` at least 98,304, the board and the
  outbox writable from the sandbox (by the permissions profile in use, or the older
  writable roots while `sandbox_mode` is set) and nothing over the state folder, the
  instruction chain for the current folder under the limit minus 4 KiB, every hook
  trusted, and the skill catalog (asked of `codex app-server`) within budget with every
  shipped skill discoverable;
- `muse hook approval`, `<harness> shell guard`: for Muse, hooks approved, and its shell
  tool name treated as a shell by the guard;
- `versions`: harness versions equal (or a release visibly in progress, never repaired);
- `instruction adapters`: every workspace folder and repository under `~/workspaces/*`
  (or the configured `workspace_roots`) has `AGENTS.md` with `CLAUDE.md` importing it, so
  Claude Code and Codex read the same instructions;
- `durable storage`: no worktree, live session or virtual environment under a temporary
  folder;
- `home paths`: no literal home path in the synced config;
- `decision packets`: every decision packet and action sheet is its generator's output;
- `outbox`: the folder agents stage outgoing attachments in is there to write, and a
  mail connector kept running by its auto-start was started with it among
  `ALLOWED_FILE_DIRS` (one whose start cannot be read is a warning, never a pass);
- `teardown`: nothing a test set up is left in place. The list is written as each thing is made
  (`<synthesis-agent-guardrails>/scripts/teardown.py add`), and a thing stays until `done` takes it
  off; the check warns with the three oldest and the oldest's age where it has one, and runs nothing a
  line names;
- `pr gate`: when `pr_gated` is configured, every commit on a gated repository's default
  branch since its gate began came through a pull request;
- `temporary addresses`: when `temporary_addresses` is configured, a quick tunnel's
  address in a message is read as one under the installed config, so such a message is
  refused; a setting that cannot be read fails;
- `browser accounts`: when a workspace's `browser_routing` names sites under `accounts`, no named
  site last showed, in that workspace's browser profile, another account than the workspace's. The
  guard writes down what each session's page reads showed; the check holds the newest against the
  config as it now is, warns with the site, the profile, the account seen and when, and clears when
  a session next reads the site and it shows the workspace's account;
- `latest release`: only with `--latest`, whether an installed harness is behind the
  published release;
- `git hooks`: the global `core.hooksPath` (report only).

## Live: proving the harness ran it

Start a fresh session in each harness. The SessionStart context names the active
project and its current state; after a compaction it comes back without asking. In
Codex, open `/hooks` and trust any synthesis hook doctor lists as untrusted or
modified; in Muse, run `muse plugins approve synthesis-skills`. Both are the person's
decisions. A restart of the client reloads hooks and skills without a new
conversation.

## Continuity: the handoff exercise

In harness A: `synthesis use <project>`, then `synthesis brief`. Open harness B on the
same Mac with no pasted transcript: its SessionStart, or `synthesis brief <project>`,
must give the same phase, status, plan and next action from the files alone. Nothing
needs committing for a same-Mac handoff. For another Mac, `synthesis handoff` commits
and pushes the records inside this session's claims; the other Mac pulls and resumes.

## Skill catalog contract

Codex budgets the combined model-visible skill catalog at 2% of the active
model context. Audit the resolved catalog through app-server `skills/list`;
do not infer safety from the public plugin's file count. Public specialist
skills may set `policy.allow_implicit_invocation: false` in
`agents/openai.yaml`: they remain enabled and explicitly invocable, while
`synthesis-skill-router` supplies natural-language routing. Claude Code ignores
that OpenAI-specific prompt policy and retains its native trigger behavior.

## Skill-output provenance

A skill whose contract names a generator script is followed only when the
artifact is verifiably that generator's output — not a hand-made substitute
(a Muse session hand-made two decision packets on 2026-09-20). Doctor's
`decision packets` check reads each `resources/artifacts/*packet*.html` in the
knowledge roots: a page with no generator marker, or whose embedded spec does not
match the marker's sha256, is flagged; rebuild it with `build_packet.py`.

## Repair from source

- Edit source repositories, never installed skill or plugin caches.
- Keep shared behavior agent-neutral.
- Use native adapters for platform differences.
- Make `AGENTS.md` canonical for tracked repository instructions.
- Make `CLAUDE.md` a small documented import adapter: `@AGENTS.md`.
- Install public skills as the `synthesis-skills` plugin on Claude, Codex and Muse.
- Install private skills to `~/.claude/skills` and `~/.agents/skills`.
- Do not create a second source-managed copy under `~/.codex/skills`.

Fix every failed required check. Record genuine client-owned differences as
boundaries with evidence; do not report parity from matching inventories alone.

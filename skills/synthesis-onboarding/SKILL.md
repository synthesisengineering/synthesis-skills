---
name: synthesis-onboarding
description: "One-command installer and layer-aware doctor for the synthesis work system: guided whole-system init, synthesis-skills plugins, stable runtime guards, personal-policy scaffolds, one-source agent kernel, knowledge workspaces, lifecycle checks, and optional organization manifests. Idempotent, upgrade-aware, fail-closed. Use when asked to: onboard, install synthesis, set up the ecosystem, set up a knowledge base, new machine setup, install the knowledge base for me, onboarding installer, org onboarding, verify my install."
license: "CC0-1.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.4.2"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Synthesis Onboarding

**Version 1.4.2** (2026-09-02) closes the invoking-task gap in a Codex
plugin update on machines with the durable historical-cache guardian. After
the native refresh returns, the engine runs that guardian synchronously and
verifies the exact version root and hook targets the current task started
with before it reports success. A missing or failed configured guardian makes
the ecosystem step non-green.

Everything a new person needs to go from a bare machine to a working
synthesis setup — close to one command plus an auth step. Built for two
audiences at once: engineers who want a scriptable, verifiable installer,
and non-engineering colleagues who should never see a complicated question.

Three ideas carry the whole design:

1. **One engine, org manifests.** The engine is generic. An organization
   ships *configuration* — a `.agents/onboarding.yaml` in its knowledge-base
   repo — never installer code. Any org gets a colleague installer by
   writing one YAML file and a three-line wrapper script.
2. **Convergence, not scripts.** Every run states desired state and moves
   the machine toward it. Re-running is always safe: it updates, repairs
   half-finished installs, and reports instead of clobbering anything a
   person edited.
3. **Fail closed and loud.** Stale caches, unknown manifest keys, and
   unverifiable state stop with plain-language instructions. A check that
   cannot run never looks like a check that passed.

## The two front doors

**Terminal (macOS, Linux, and Windows through WSL):**

```bash
curl -fsSL https://raw.githubusercontent.com/synthesisengineering/synthesis-skills/stable/onboard.sh | sh
```

With no arguments, the bootstrap opens the guided `init` interview through
the terminal even though the shell script arrived over a pipe. Every cataloged
layer ends as `installed`, `declined`, or `missing`; a missing selected layer
keeps the run non-green. For an agent-driven or automated run, pass a reviewed
JSON answers file instead of relying on prompts. When Git has no author
identity, a full-profile interview collects the name and email before mutation;
non-interactive answers provide them as `git_name` and `git_email`.

**Agent (when Claude Code or Codex already has this plugin):** ask the
assistant to "set up the synthesis ecosystem" — it runs the same engine:

```bash
python3 <this-skill>/scripts/onboard.py init
```

Organization members use their org's wrapper instead (one command from the
org's knowledge-base repo), which calls the same engine with the org's
manifest. See `references/org-manifest.md`.

## Commands

```bash
onboard.py init [--profile full|skills-only] [--answers PATH]
                [--manifest PATH] [--workspace NAME] [--no-services]
onboard.py install [--manifest PATH] [--channel stable|edge] [--dry-run] [--json]
                   [--clients claude,codex] [--no-plugin-cli]
                   [--with-personal-workspace NAME]
onboard.py update          # explicit native-plugin refresh + install convergence
onboard.py kernel [--workspace NAME]   # regenerate AGENTS.md + CLAUDE.md
onboard.py doctor  [--manifest PATH] [--json]
onboard.py init-workspace --workspace NAME [--remote URL]
onboard.py uninstall [--dry-run]
```

Exit codes (guard contract): `0` fully converged / healthy; `1` errors or a
step that needs the user (auth, git identity) — re-run after acting; `2` the
engine could not establish ground truth (no git, invalid manifest).

## Whole-system layer model

`references/layers.json` is the versioned desired-state catalog shared by
`init`, receipts, and `doctor`. It defines eleven visible layers: skills,
session context, hooks and gates, agent kernel, runtime engines, coordination,
doctors and conformance, personal policy, organization, knowledge bases, and
lifecycle. `references/components.json` separately names every public skill and
installer; CI fails when source and that catalog diverge.

The `full` profile selects every public layer, with the organization layer
selected when a manifest is supplied. The `skills-only` profile deliberately
declines the rest. A live probe may still find a declined layer because a plugin
contains its code; doctor reports what exists and preserves the choice receipt.
No selected layer can disappear from the report.

## What guided init adds

| Phase | Behavior |
|-------|----------|
| interview | Choose `full` or `skills-only`; collect a workspace slug, time zone, voice traits, wording boundaries, optional-runtime choices, and, only when absent from Git, the author name and email for the new repository. `/dev/tty` keeps the interview available when `onboard.sh` is piped from curl. `--answers` provides the same contract as reviewed JSON for an agent or CI run, including paired `git_name` and `git_email` fields when needed. |
| personal workspace | Scaffold a Git-backed `ai-knowledge-<workspace>` container and its project/lesson structure. A collected Git identity is configured only in that repository, never globally; a rerun completes the initial commit of a half-finished workspace. The interview creates policy; it does not copy anyone else's private files. |
| personal policy | Render valid local configs for personal policy, message guard, chief of staff, and knowledge capture from shipped generic templates. The scaffold audit fails CI if a documented fail-closed config lacks a template and validator route. |
| gates + runtimes | Install the commit guard, stable message-guard engine, day-end launcher, and optional inbox runtime under `~/.synthesis`; wire only the two owned hook entries while preserving every unrelated entry. Codex hook trust remains a human-controlled client setting and is reported, never auto-approved. |
| kernel | Create user-owned `AGENTS.source.md`, then render `AGENTS.md` and `CLAUDE.md`. A 55,000-byte hard limit refuses propagation before either output changes; the warning band starts at 85 percent. A stable PostToolUse hook propagates later valid source edits and refuses to overwrite a user-edited output. |
| doctor + welcome | Probe the catalog and print every layer as `installed`, `declined`, or `missing`, including `verification: unverifiable` when live truth cannot be established. Only a complete or explicitly declined system exits green. |

## What install does, in order

| Phase | Behavior |
|-------|----------|
| preflight | Verify git (guides through `xcode-select --install` if missing); detect clients via `SYNTHESIS_CLAUDE_BIN`/`SYNTHESIS_CODEX_BIN` → PATH → well-known locations (incl. the ChatGPT app's bundled codex). Absent clients are skipped, not fatal. |
| ecosystem | `install` adds a missing native plugin from the selected lifecycle target and checks an existing one without replacing its live cache. Stable is the default, edge is opt-in, and an org manifest's exact `version_pin` takes precedence over its channel. `update` explicitly refreshes or reconfigures existing native plugins, verifies the resulting version, and states the client-restart and receipt-verification boundary. A first installation may use the repo's direct-copy fallback when a client lacks the plugin CLI; an installed native plugin is never replaced by duplicate copies. |
| org-skills | For each manifest `skills_repos` entry: SSH-first clone/refresh into the engine cache, then delegate to that repo's own installer with its source pinned to the fresh cache. A cache that cannot refresh stops the step (`SYNTHESIS_ONBOARD_ALLOW_STALE=1` overrides, loudly). |
| knowledge-bases | Clone to `~/workspaces/<org-workspace>/<name>`, or **adopt** an existing clone found by matching remotes (never moved). Superseded remotes are repointed to the manifest primary (`git remote set-url`). Fast-forward pull when clean. When the repo ships `.githooks` and no global hooks engine is active, wire repo-local `core.hooksPath` so protective hooks run on fresh clones. Auth failures print the manifest's `auth_help` and mark the step "needs you" — the run continues and the re-run completes it. |
| workspace | Generate `~/workspaces/<org-workspace>/AGENTS.md` (+ `CLAUDE.md` = `@AGENTS.md`): the welcome, what-you-can-ask list, KB contract pointers. |
| migrations | Apply the manifest's skill tombstones (remove / rename / superseded-by-public) to user-level skill copies — archive first, always. |
| doctor + welcome | Verify everything, then greet: what to try asking, where the guides are, and that re-running is always safe. |

## Receipts and the no-clobber rule

State lives at `~/.synthesis/onboarding/receipts.json`: every generated
file's checksum, adopted repo locations, run history. A generated file whose
current content matches its receipt is engine-owned and may be updated
(previous copy archived under `~/.synthesis/onboarding/backups/`). A file a
person edited is **never overwritten** — the engine warns and moves on.
`uninstall` removes only receipt-owned files (archived first) and never
touches knowledge-base clones or plugins.

The receipt also stores the effective plugin policy. SessionStart reads that
policy and the executing plugin-cache manifest, then compares it with a
six-hour cached release-manifest check. It emits a notice when the installed
cache is behind or mismatched and preserves an explicit unverifiable state
when neither live nor cached release evidence is available. On python.org's
macOS runtime, where OpenSSL can have no configured CA path, the live check
retries with an existing operating-system CA bundle through a fully verifying
TLS context; it never disables certificate or hostname verification. `doctor` applies
the same comparison and exit-code contract.

## Release channels

- `stable` (default) follows the release-gated `stable` branch.
- `edge` follows `main` and is opt-in through `--channel edge` or
  `SYNTHESIS_ONBOARD_CHANNEL=edge`.
- Organization manifests may set an exact `version_pin`; the engine resolves
  it to the immutable `vX.Y.Z` release tag and the pin overrides the channel.

The gated release publisher advances `main`, `stable`, and the version tag in
one atomic push per remote. A pull request reaching `main` is available to
edge; stable moves only when the release gate succeeds.

## Safe plugin upgrades

Run `onboard.py update` only after closing other Claude Code sessions and
Codex tasks that use this marketplace, and make it the invoking session's last
action before restarting the client. Resume the same root conversation only
when its exact transcript-bound SessionStart receipt and loaded skill metadata
match the installed release. Start a new conversation/task only if restart
verification fails or the client cannot rehydrate it. Native clients resolve
plugin hooks to versioned cache paths; replacing that cache can invalidate hook
commands already loaded by another live session. Ordinary `install` and
`doctor` runs never refresh an existing native plugin. When the gated publisher
has installed the durable Codex cache guardian on this machine, `update`
synchronously restores and verifies the invoking task's exact historical hook
root before it returns; that narrows the unavoidable last-action boundary to
the client lifecycle reload instead of leaving a post-command restoration race.

## Scaffolding a personal knowledge workspace

```bash
onboard.py init-workspace --workspace alice [--remote git@github.com:alice/ai-knowledge-alice.git]
```

Creates `~/workspaces/<name>/ai-knowledge-<name>/` with `projects/index.yaml`,
`lessons/`, `AGENTS.md` + `CLAUDE.md` adapter, README, git init and first
commit — the synthesis-project-management container shape. Project *content*
stays agent-authored (that skill's "examine an example and adapt" principle);
this scaffolds the container so day one needs no hand-wiring.

## Personal-policy ownership and kernel regeneration

Generic examples live beside their consumers:

- `references/personal-policy.example.json`
- `references/kernel.example.md`
- `../synthesis-message-guard/patterns.example.json`
- `../synthesis-chief-of-staff/preferences.example.json`
- `../synthesis-knowledge-capture/config.example.json`

The interview turns those examples into local files. Generated files carry
receipt hashes; changes are applied only when the current bytes still match the
last engine-owned receipt. `AGENTS.source.md` is different: it becomes
user-owned at creation and is never removed by uninstall. Run `onboard.py
kernel` for an explicit regeneration; the installed edit hook runs the same
budget and no-clobber rules after source edits.

## Configuration

| Env var | Default | Purpose |
|---------|---------|---------|
| `SYNTHESIS_ONBOARD_HOME` | `$HOME` | Root for all install targets (tests use a sandbox home) |
| `SYNTHESIS_ONBOARD_STATE_DIR` | `~/.synthesis/onboarding` | Receipts + backups |
| `SYNTHESIS_WORKSPACES_ROOT` | `~/workspaces` | Where workspaces and KBs live |
| `SYNTHESIS_ONBOARD_CACHE_DIR` | XDG cache | Org repo caches |
| `SYNTHESIS_ONBOARD_SOURCE_DIR` | this repo | synthesis-skills checkout to install from |
| `SYNTHESIS_ONBOARD_CHANNEL` | `stable` | Engine/plugin channel (`stable` or opt-in `edge`) |
| `SYNTHESIS_CLAUDE_BIN` / `SYNTHESIS_CODEX_BIN` | auto | Client binary override; set-but-empty means "treat as absent" |
| `SYNTHESIS_ONBOARD_ALLOW_STALE` | unset | Accept an unrefreshable cache (loud) |
| `SYNTHESIS_ONBOARD_NO_PLUGIN_CLI` | unset | Force file-copy fallback |

## Relationship to neighbors

- **install.sh (repo root)** — the per-skill copy fallback this engine
  delegates to when a client lacks native plugin support.
- **onboard.sh (repo root)** — the curl-able bootstrap: ensures git, clones
  or refreshes this repo, hands off to this engine.
- **synthesis-skills-manager** — the agent-run protocol for skill authors
  (multi-repo source management, synthesis merges). This engine is the
  end-user installer; it never edits sources.
- **synthesis-agent-conformance** — the deep parity audit for maintainers.
  `onboard.py doctor` is the end-user health check; conformance remains the
  authoritative source/runtime/handoff verification.
- **synthesis-project-management / context-lifecycle** — define the
  workspace shape that `init-workspace` scaffolds.

## Supported client surfaces

- Claude Code, ChatGPT Codex desktop, and Codex CLI are first-class native
  plugin surfaces.
- Codex IDE is reported as `UNSUPPORTED`: it does not load plugins, and its
  shared user-skill roots cannot hold a second public copy without creating
  duplicate definitions in desktop/CLI.
- A plugin change becomes usable only after a genuine client lifecycle reload.
  Preserve the synthesis checkpoint, restart the client, and verify the exact
  current-plugin SessionStart receipt plus loaded skill metadata. A same-root
  conversation may continue when that proof passes; installed files alone do
  not prove a reload.

## Safety rules

- Never delete without archiving first; never force-push anything.
- Never overwrite a file the user edited (receipts decide ownership).
- Never enumerate or clone repos the manifest does not name.
- Org manifests are validated fail-closed: unknown keys are errors.
- The engine runs on python3 stdlib alone (PyYAML optional) so a fresh Mac
  with Command Line Tools needs nothing else.
- macOS and Linux are supported execution environments. Windows uses the same
  Linux path through WSL; native Windows exits before mutation with WSL
  guidance. Hosted CI executes the onboarding suite on both macOS and Linux.

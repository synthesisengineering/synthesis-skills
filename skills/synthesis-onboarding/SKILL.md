---
name: synthesis-onboarding
description: "One-command installer and doctor for the synthesis ecosystem: installs the synthesis-skills plugin into Claude Code and/or Codex, scaffolds ai-knowledge-<workspace> repos, and layers organization knowledge bases and shared skills from a declarative org manifest. Idempotent, upgrade-aware, fail-closed. Use when asked to: onboard, install synthesis, set up the ecosystem, set up a knowledge base, new machine setup, install the knowledge base for me, onboarding installer, org onboarding, verify my install."
license: "CC0-1.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.3.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Synthesis Onboarding

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

**Terminal (works with nothing pre-installed except macOS):**

```bash
curl -fsSL https://raw.githubusercontent.com/synthesisengineering/synthesis-skills/stable/onboard.sh | sh
```

**Agent (when Claude Code or Codex already has this plugin):** ask the
assistant to "set up the synthesis ecosystem" — it runs the same engine:

```bash
python3 <this-skill>/scripts/onboard.py install
```

Organization members use their org's wrapper instead (one command from the
org's knowledge-base repo), which calls the same engine with the org's
manifest. See `references/org-manifest.md`.

## Commands

```bash
onboard.py install [--manifest PATH] [--channel stable|edge] [--dry-run] [--json]
                   [--clients claude,codex] [--no-plugin-cli]
                   [--with-personal-workspace NAME]
onboard.py update          # explicit native-plugin refresh + install convergence
onboard.py doctor  [--manifest PATH] [--json]
onboard.py init-workspace --workspace NAME [--remote URL]
onboard.py uninstall [--dry-run]
```

Exit codes (guard contract): `0` fully converged / healthy; `1` errors or a
step that needs the user (auth, git identity) — re-run after acting; `2` the
engine could not establish ground truth (no git, invalid manifest).

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
when neither live nor cached release evidence is available. `doctor` applies
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
`doctor` runs never refresh an existing native plugin.

## Scaffolding a personal knowledge workspace

```bash
onboard.py init-workspace --workspace alice [--remote git@github.com:alice/ai-knowledge-alice.git]
```

Creates `~/workspaces/<name>/ai-knowledge-<name>/` with `projects/index.yaml`,
`lessons/`, `AGENTS.md` + `CLAUDE.md` adapter, README, git init and first
commit — the synthesis-project-management container shape. Project *content*
stays agent-authored (that skill's "examine an example and adapt" principle);
this scaffolds the container so day one needs no hand-wiring.

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
- v1 targets macOS; the engine avoids macOS-only code paths so Linux and
  Windows (WSL first) can follow without redesign.

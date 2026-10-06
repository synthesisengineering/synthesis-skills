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
bounded `--version` probe. Checks:

- the stable runtime, its hook script, and a self-test that the real hook denies
  `rm -rf ~` within the latency budget;
- per harness: the plugin installed and enabled, its code equal to the runtime (never a
  version label), all four events wired to the stable hook;
- Codex: `[features] hooks = true`, `project_doc_max_bytes` at least 98,304, the
  instruction chain for the current folder under the limit minus 4 KiB, every hook
  trusted, and the skill catalog (asked of `codex app-server`) within budget with every
  shipped skill discoverable;
- Muse: hooks approved, and its shell tool name treated as a shell by the guard;
- harness versions equal (or a release visibly in progress, never repaired);
- every workspace folder and repository under `~/workspaces/*` (or the configured
  `workspace_roots`) has `AGENTS.md` with `CLAUDE.md` importing it, so Claude Code and
  Codex read the same instructions;
- no worktree, live session or virtual environment under a temporary folder;
- no literal home path in the synced config;
- every decision packet is the generator's output;
- the global `core.hooksPath` (report only).

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

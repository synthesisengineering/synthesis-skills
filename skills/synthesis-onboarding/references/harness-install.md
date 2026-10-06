# Installing in each harness (setup.py)

## Contents

- [What setup does, in order](#what-setup-does-in-order)
- [Each harness's own commands](#each-harnesss-own-commands)
- [Codex settings setup owns](#codex-settings-setup-owns)
- [The runtime, the commit check and the CLI](#the-runtime-the-commit-check-and-the-cli)
- [The day-end launcher and nudge](#the-day-end-launcher-and-nudge)
- [First config](#first-config)
- [Hook trust stays with the person](#hook-trust-stays-with-the-person)
- [Restart, verify, uninstall](#restart-verify-uninstall)

## What setup does, in order

`python3 <checkout>/skills/synthesis-onboarding/scripts/setup.py` with no command does
everything, asking only what it cannot detect: the plugin in every harness it finds,
Codex's settings, the stable runtime, the commit check (asked), a first config (fresh
installs only), then optionally a workspace or an organization. Each part is also its
own command (`plugin`, `workspace`, `org`, `uninstall`). Every run prints one line per
step and ends with the restart sentence. `--dry-run` prints what each harness command
would be and changes nothing; `--no-input` never asks and names the flag it needed.

A harness that is not on the Mac is skipped with a line saying so; it never fails the
run. The Codex CLI ships inside the ChatGPT desktop app and is on PATH only in Codex's
own shells, so setup looks in the app's install folders too (the same finder doctor
uses; `SYNTHESIS_CODEX_BIN` overrides it, and an empty value means "absent").

## Each harness's own commands

Setup reads each harness's plugin list as JSON (Claude Code may print a list or a
`plugins` map; Codex prints `installed`). A list it cannot parse stops that harness with
a message; it is never taken to mean "not installed".

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

## Codex settings setup owns

Setup changes only these keys in `~/.codex/config.toml`, after copying the file to
`~/.synthesis/v5/backups/`:

- `[features] hooks = true`, inside a marked block. If the person set `hooks = false`,
  it stays, and setup says no synthesis guard will run in Codex.
- `project_doc_max_bytes` at least 98,304 (raised if lower, added if absent). Codex's
  default, 32 KiB, truncates the global rules plus a workspace's instructions.
- `project_doc_fallback_filenames = ["CLAUDE.md"]` when the key is absent; an existing
  list without `CLAUDE.md` is reported and left as set.

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
at 16:55 on weekdays. An older schedule under that label is archived first and unloaded;
the new one is loaded with `launchctl bootstrap`, or only written with `--no-launchctl`.
The banner text is generic and fixed (others see banners on screen-shares). Uninstall
unloads and removes only a schedule and a link that point at this install's copies.

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
approves either. `synthesis doctor` names every hook still waiting.

## Restart, verify, uninstall

- Restart each harness after setup: a client restart reloads hooks and skills without
  a new conversation (lesson 2026-08-17), so the person can resume where they were.
- `synthesis doctor` then reports every part; `synthesis doctor --latest` also compares
  with the published release.
- `setup.py uninstall [--dry-run]` removes the plugin with each harness's own command
  (`claude plugin uninstall … --yes`, `codex plugin remove …`, `muse plugins remove …`),
  restores `core.hooksPath`, removes only files the install wrote that are unedited, and
  keeps `config.json` and `state/` (settings, board, approvals), saying what it kept.

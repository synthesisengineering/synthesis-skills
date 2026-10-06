# Synthesis Skills

Synthesis Skills is one plugin for Claude Code, Codex and Muse. It carries 69 skills
for software engineering, writing, project management, correspondence and daily
operations, plus a small runtime: a `synthesis` command and four lifecycle hooks. The
skills follow the [Agent Skills](https://agentskills.io) standard. The runtime keeps
project state in git, keeps parallel sessions from overwriting each other, holds sends
and deploys until a person approves them, and refuses destructive commands.

Version 5 rebuilt the runtime from its requirements and rewrote every skill into one
format. [CHANGELOG.md](CHANGELOG.md) has the full history; this page describes what is
here now.

## Who it is for

- People who work with coding agents for weeks at a time, on software, writing,
  research or operations, and need a project to survive compaction, a restart, a
  switch between harnesses, or a move to another Mac.
- People who run several agent sessions at once and need them to see each other's
  work and stay out of each other's files.
- Anyone who wants outgoing messages and production deploys to wait for their
  approval, enforced by a hook rather than by the agent's memory.
- Teams and organizations that want the same methods and rules in every member's
  agents, from a shared configuration repository.

The methodology skills (writing, review, planning, reasoning) are plain instructions
and work in any client that reads Agent Skills. The skills that coordinate sessions or
guard actions need the runtime, which installs in Claude Code, Codex and Muse.

## What you get

### The skills

Every skill states its purpose in one paragraph, then its binding rules, then a contents
list that says what each linked file holds and when to read it, then its procedure. Each
`SKILL.md` stays under 8,000 bytes so that every harness reads all of it; longer
material lives in reference files. The [skill list](#skill-list) is below.

### Four hooks

All four run `~/.synthesis/v5/bin/synthesis-hook <event>`. That path and its text never
change between releases, so a harness's approval of the hook survives upgrades.

| Event | What it does |
|---|---|
| SessionStart | States the local time; injects the active project's `PRIME-DIRECTIVE.md` and the current-state block of its `CONTEXT.md`, this session's autopilot run if it has one, one line of ritual state, and a count of unread board messages. Claude Code and Codex run it again after compacting the conversation, so the brief comes back on its own. It also brings the installed runtime up to the plugin version the harness loaded. |
| UserPromptSubmit | Reads your prompt for `approve <code>` and grants that pending request. Delivers up to five unread board messages. |
| PreToolUse | Checks shell commands and message, calendar, mail and sharing tool calls before they run (see below). If its config can't be read or a guard fails, the call is blocked, never waved through. |
| Stop | Sends the agent's final reply back once if it uses deferring language, quotes someone with words that appear nowhere in the session, or (when `reply_file_links` is set) names a file without a clickable absolute-path link. For an autopilot run, it asks the session to continue to the plan's next open item. It fails open, since a turn-end check that fails closed would loop forever. |

What PreToolUse holds:

- **Sends and drafts** (Slack, Gmail, Mail and similar tools, plus any you add with
  `send_tools`). The text must first pass your `forbidden_phrases` and the format rules,
  such as HTML email with whole paragraphs. Then the agent shows you the exact text and
  recipient, and you type `approve <code>` in your own message. The approval covers that
  exact call once and expires after 15 minutes. Only the UserPromptSubmit hook can grant
  it, because it reads the prompt you typed, which the agent cannot write.
- **Deploys** (`wrangler deploy`, `vercel --prod`, `netlify deploy --prod`,
  `firebase deploy`, `npm publish`, `twine upload`, `gh release create`, a push to a
  repository listed in `push_deploys`, and your own `deploy_patterns`) need approval of
  the exact command. A deploy that would put a page live before its stated date, or
  change the date of a published page, is refused even with approval. A second deploy of
  the same site within 45 minutes needs its own approval.
- **Destructive commands.** A recursive `rm` of `/`, your home folder, `~/workspaces`,
  any folder directly inside it, a root you list in `protected_roots`, or any git
  repository is refused, and so is a force push to `main` or `master`.
- **Account routing.** Calendar, mail and sharing calls are checked against the account
  you configure for the workspace a session runs in, since an invitation sent from the
  wrong account cannot be unsent. Nothing is routed until you set `account_routing`.

The configuration lives in `~/.synthesis/v5/config.json`. A missing file means the
defaults above. The keys are documented in the
[guardrails configuration](skills/synthesis-agent-guardrails/references/config.md) and
the [message guard configuration](skills/synthesis-message-guard/references/config.md).

An optional global git hook adds a commit check in every repository. It blocks
credentials, private keys and credential files everywhere; unapproved disclosures in
repositories outsiders read, under a commit policy you configure; and commits that touch
another live session's claim. It then runs the repository's own hooks. Setup asks before turning it on
(`--git-hooks`); see [synthesis-git-hooks](skills/synthesis-git-hooks/SKILL.md).

### The `synthesis` command

| Command | What it does |
|---|---|
| `synthesis use <project>` | Set this session's active project. |
| `synthesis brief [project]` | Print the project's directive and current state, and any problems with its records. |
| `synthesis resume <project>` | Pick up a project: directive, state, next actions, plan and warnings (a newer copy elsewhere, upstream changes, other sessions working there). If the project differs from the session's own, it asks first; `--switch` switches after you agree. |
| `synthesis who` | List live sessions and their claims (`--all` includes stale ones). |
| `synthesis claim <paths>` | Claim absolute paths before writing; a trailing `/**` claims a subtree. A refused claim names the holder. `--take` takes over a claim that has been quiet for 8 hours and tells its holder. |
| `synthesis release [paths]` | Release some or all of this session's claims. |
| `synthesis msg <address> "<text>"` | Message a session by id, short name or `project:<id>`. An ambiguous address is refused, never guessed. `--durable` reaches every session that works on the project. |
| `synthesis inbox` | Show and mark unread messages. |
| `synthesis worktree create\|retire\|land` | Create a worktree under a claim, remove a merged clean one, or fast-forward the main checkout to the remote's default branch. |
| `synthesis handoff -m "<message>"` | Commit and push only the changes inside this session's claims, running every hook. Ends `READY`, or `NOT READY` with what blocks it. |
| `synthesis approvals` | List sends and deploys waiting for your approval. |
| `synthesis doctor` | Check the runtime, each harness's installed plugin, hook wiring and trust, and Codex's settings. `--latest` also asks whether a newer release exists. |
| `synthesis install`, `synthesis uninstall` | Install the runtime from a plugin folder, or remove what install wrote while keeping config and the board. |
| `synthesis version` | Print the runtime version. |

## Install

The installer targets macOS. It needs `git`, `python3` (the `/usr/bin/python3` that
ships with macOS is enough) and at least one of the harnesses.

### A whole Mac

```bash
curl -fsSL https://raw.githubusercontent.com/synthesisengineering/synthesis-skills/stable/onboard.sh | sh
```

`onboard.sh` keeps a source checkout at `~/.synthesis/v5/source` on the `stable` branch
and runs the onboarding skill's
[setup.py](skills/synthesis-onboarding/scripts/setup.py). Setup installs the plugin in
every harness it finds, using each harness's own commands; sets the Codex settings it
needs; installs the runtime and links `~/.local/bin/synthesis` if that name is free;
asks whether to turn on the commit check; and on a fresh install asks two questions for
a first config. Every step is safe to rerun.

Variants:

```bash
# Bring an existing workspace's repositories onto a new Mac
curl -fsSL https://raw.githubusercontent.com/synthesisengineering/synthesis-skills/stable/onboard.sh | sh -s -- workspace

# Join an organization that publishes a synthesis configuration repository
curl -fsSL https://raw.githubusercontent.com/synthesisengineering/synthesis-skills/stable/onboard.sh | sh -s -- --org-repo URL
```

To follow the development branch or pin a release, set `SYNTHESIS_REF` for `sh`, as in
`curl -fsSL .../onboard.sh | SYNTHESIS_REF=v5.0.0 sh`. The
[onboarding skill](skills/synthesis-onboarding/SKILL.md) and its
[harness reference](skills/synthesis-onboarding/references/harness-install.md) cover
every option, including `--dry-run`, `--no-input` and the day-end launcher.

### One harness at a time

Setup's `plugin` step installs into only the harnesses you name, with no questions and
no workspace step:

```bash
git clone --branch stable https://github.com/synthesisengineering/synthesis-skills.git ~/.synthesis/v5/source
python3 ~/.synthesis/v5/source/skills/synthesis-onboarding/scripts/setup.py plugin --clients codex
```

`--clients` takes `claude`, `codex`, `muse` or a comma-separated list. The step installs
the plugin with that harness's own commands, installs the runtime, links the `synthesis`
command, and for Codex sets `[features] hooks = true` and raises
`project_doc_max_bytes` to at least 98,304 in `~/.codex/config.toml`, after a backup.

These are the native commands it runs, if you would rather type them yourself:

```bash
# Claude Code
claude plugin marketplace add synthesisengineering/synthesis-skills@stable
claude plugin install synthesis-skills@synthesis-engineering

# Codex
codex plugin marketplace add synthesisengineering/synthesis-skills --ref stable
codex plugin add synthesis-skills@synthesis-engineering
```

Muse installs from a local bundle that setup builds, so it has no standalone command.
The native commands give you the skills and the hooks, but not the Codex settings or the
`~/.local/bin/synthesis` link. In Claude Code the SessionStart hook installs the runtime
from the plugin folder the first time it runs; the command is then at
`~/.synthesis/v5/bin/synthesis`.

### After installing

1. Restart each harness. A restart reloads hooks and skills; you can resume the
   conversation you were in.
2. Approve the hooks where the harness asks: in Codex open `/hooks` and trust the
   synthesis hooks; in Muse run `muse plugins approve synthesis-skills`. Setup never
   approves them for you.
3. Run `synthesis doctor`. It prints one line per check and names any hook still
   waiting for approval.

Without any config, sends, drafts and deploys wait for your approval, the deploy date
rules and destructive-command rules apply, and account routing is off.

### Update and uninstall

To update, run the installer again with the `plugin` step:

```bash
curl -fsSL https://raw.githubusercontent.com/synthesisengineering/synthesis-skills/stable/onboard.sh | sh -s -- plugin
```

An install that follows `main` or a pinned release keeps it. To uninstall, run
`python3 ~/.synthesis/v5/source/skills/synthesis-onboarding/scripts/setup.py uninstall --dry-run`
to see what would go, then again without `--dry-run`. It removes the plugin from each
harness, restores your previous `core.hooksPath`, removes the unedited files the install
wrote, and keeps your config and the board.

`install.sh` remains only so older links keep working; it runs `onboard.sh`.

## Skill list

Each line comes from the skill's own description. Every skill name starts with
`synthesis-` to avoid collisions with other plugins.

In Claude Code a skill loads when a request matches its description. In Codex, the
eleven foundational skills (agent-conformance, anti-shortcuts, autopilot, checkpoint,
code-planning, context-lifecycle, grounding-discipline, implementation-integrity,
project-management, skill-router and thinking-framework) load the same way; the rest
are reached through `synthesis-skill-router` or by name as `$synthesis-<name>`, which
keeps Codex's skill catalog within its budget.

### Projects and sessions

| Skill | What it does |
|---|---|
| [synthesis-project-management](skills/synthesis-project-management/SKILL.md) | Run projects as markdown records in git and keep parallel sessions from colliding: setup, index, lessons, claims, one context owner, messages, worktrees, handoff. |
| [synthesis-project-resume](skills/synthesis-project-resume/SKILL.md) | Start or resume a project in any harness on any Mac with verified context, respecting live claims and surfacing other Macs' changes. |
| [synthesis-context-lifecycle](skills/synthesis-context-lifecycle/SKILL.md) | Keep a project's working memory small, current and durable: CONTEXT, REFERENCE and session logs, archiving, deletion units and the records doctor. |
| [synthesis-checkpoint](skills/synthesis-checkpoint/SKILL.md) | Re-sync a session with ground truth: verified clock, project records, git, dated session entries and board claims. |
| [synthesis-autopilot](skills/synthesis-autopilot/SKILL.md) | Run an explicitly delegated whole task to the end from a plan file in the project, unattended when needed. |

### Engineering and review

| Skill | What it does |
|---|---|
| [synthesis-code-planning](skills/synthesis-code-planning/SKILL.md) | Plan and implement code: apply constraints, compare the viable approaches that remain, resolve delegated technical choices, implement with evidence. |
| [synthesis-preplan](skills/synthesis-preplan/SKILL.md) | Lock the architecture decisions for a ticket and hand a reviewable decision set to planning. |
| [synthesis-implementation-integrity](skills/synthesis-implementation-integrity/SKILL.md) | Verify an implementation is complete before calling it done: data chains, placeholders, test honesty, environment parity. |
| [synthesis-preflight](skills/synthesis-preflight/SKILL.md) | Pre-merge gate that grades branch, clean tree, tests and types, code audit, temporary workarounds and commit history into a go/no-go verdict. |
| [synthesis-code-audit](skills/synthesis-code-audit/SKILL.md) | Score a code diff on ten dimensions with PASS, WARNING, FAIL or UNKNOWN and an overall verdict. |
| [synthesis-pr-review](skills/synthesis-pr-review/SKILL.md) | Delta review of a pull request: regression risk, root cause, scope, and handoff to integration. |
| [synthesis-review-triage](skills/synthesis-review-triage/SKILL.md) | Prioritize a PR review queue by review gap, CI, age, size and labels, and gate re-reviews. |
| [synthesis-codebase-review](skills/synthesis-codebase-review/SKILL.md) | Codebase audit methodology with tiers from Essential to Mission-Critical. |
| [synthesis-code-integration](skills/synthesis-code-integration/SKILL.md) | The adopt-and-adapt pattern for integrating contributions: lead synthesist, quality gates, cherry-pick safety. |
| [synthesis-adversarial-review](skills/synthesis-adversarial-review/SKILL.md) | Bounded adversarial review by differently shaped agents, with a findings table and sufficiency rulings. |
| [synthesis-bitbucket](skills/synthesis-bitbucket/SKILL.md) | Work with Bitbucket Cloud through the open-source `bkt` CLI, with explicit repository binding and write-safety rules. |

### Writing and publishing

| Skill | What it does |
|---|---|
| [synthesis-reader-briefing](skills/synthesis-reader-briefing/SKILL.md) | Brief the reader before drafting a public article from internal material; catches insider context collapse. |
| [synthesis-article-writing](skills/synthesis-article-writing/SKILL.md) | Write and review articles: research, drafting, critical review, and review of the title, description and slug as a package. |
| [synthesis-article-refresh](skills/synthesis-article-refresh/SKILL.md) | Refresh an older published article while keeping the author's voice and its temporal integrity. |
| [synthesis-content-framing](skills/synthesis-content-framing/SKILL.md) | Frame synthesis engineering and synthesis coding articles: topic, sophistication, engagement and confidentiality gates. |
| [synthesis-content-quality](skills/synthesis-content-quality/SKILL.md) | Detect AI slop and empty substance in prose: model-family fingerprints, substance and depth tests, calibration, ESL safe-harbor. |
| [synthesis-writing-pitfalls](skills/synthesis-writing-pitfalls/SKILL.md) | Catch human-source bad-writing patterns: humble-bragging, throat-clearing, caveat overload, cliché, register mismatch. |
| [synthesis-writing-craft](skills/synthesis-writing-craft/SKILL.md) | Positive principles from the writing-craft tradition for agents drafting or editing on a writer's behalf. |
| [synthesis-fact-checking](skills/synthesis-fact-checking/SKILL.md) | Fact-check claims, quotes, studies, URLs and laundered citations before publication. |
| [synthesis-link-research](skills/synthesis-link-research/SKILL.md) | Find authoritative links for people and organizations, and recover dead URLs in archives. |
| [synthesis-content-distribution](skills/synthesis-content-distribution/SKILL.md) | Share content on social platforms: a brief, posts per platform, social-register checks, follow-up. |
| [synthesis-voice-profiler](skills/synthesis-voice-profiler/SKILL.md) | Build a voice profile from writing samples, as a section for `CLAUDE.md` or `AGENTS.md`. |
| [synthesis-clean-text](skills/synthesis-clean-text/SKILL.md) | Enforce clean-text and no-hidden-marker requirements and state what can and cannot be verified about statistical text marks. |
| [synthesis-text-provenance](skills/synthesis-text-provenance/SKILL.md) | Plan, record and audit text provenance for hosted and open-weight models; not for defeating provider marks or evading detectors. |

### Correspondence

| Skill | What it does |
|---|---|
| [synthesis-agent-correspondence](skills/synthesis-agent-correspondence/SKILL.md) | Compose and send honest agent correspondence: whose words and whose hands, personas, disclosure signatures, send gates. |
| [synthesis-concise-messaging](skills/synthesis-concise-messaging/SKILL.md) | Condense a message to five sentences or fewer. |
| [synthesis-executive-communication](skills/synthesis-executive-communication/SKILL.md) | Translate technical work for non-technical executives and boards. |
| [synthesis-slack-sync](skills/synthesis-slack-sync/SKILL.md) | Sync Slack channels, DMs and threads to local transcripts and update the daily plan. |
| [synthesis-inbox-cleanup](skills/synthesis-inbox-cleanup/SKILL.md) | Manifest-driven cleanup for iCloud and IMAP, Microsoft 365 and outlook.com, and Gmail, with prompt-injection defenses. |
| [synthesis-local-messaging](skills/synthesis-local-messaging/SKILL.md) | Read an authorized window of local iMessage or WhatsApp data into pointer-only notes, and send one approved iMessage. |

### Daily operations

| Skill | What it does |
|---|---|
| [synthesis-daily-rituals](skills/synthesis-daily-rituals/SKILL.md) | Day-start, day-end, mid-day sync and the weekly review across every declared channel, mailbox and repository. |
| [synthesis-catchup-ledger](skills/synthesis-catchup-ledger/SKILL.md) | Reconcile missed and pending commitments after a break into a dated catch-up ledger. |
| [synthesis-chief-of-staff](skills/synthesis-chief-of-staff/SKILL.md) | Chief of staff and executive assistant duties: meeting triage, scheduling, look-ahead reviews, holds, travel, follow-ups. |
| [synthesis-meeting-prep](skills/synthesis-meeting-prep/SKILL.md) | Prepare for a meeting with a scannable pack and a capture half, then debrief the transcript. |
| [synthesis-meeting-transcripts](skills/synthesis-meeting-transcripts/SKILL.md) | Fetch meeting notes and full transcripts into markdown, and verify a record is primary before it supports attribution. |
| [synthesis-absence-coordination](skills/synthesis-absence-coordination/SKILL.md) | Coordinate an absence: notification order, coverage, out-of-office, return sweep. |
| [synthesis-decision-packet](skills/synthesis-decision-packet/SKILL.md) | Collect five or more parallel decisions in one sitting through a self-contained HTML packet. |
| [synthesis-quick-answers](skills/synthesis-quick-answers/SKILL.md) | A read-mostly companion session for quick lookups, each answer naming its source and confidence tier. |

### Reasoning and agent discipline

| Skill | What it does |
|---|---|
| [synthesis-thinking-framework](skills/synthesis-thinking-framework/SKILL.md) | Five-mode thinking (first principles, systems, complexity, analogical, design) with a pre-response protocol. |
| [synthesis-anti-shortcuts](skills/synthesis-anti-shortcuts/SKILL.md) | Catch language that hides deferral, dismissal or false consultation; sub-agent dispatch and acceptance hygiene. |
| [synthesis-grounding-discipline](skills/synthesis-grounding-discipline/SKILL.md) | Keep output tied to evidence: record only what a source surfaced, prove absence, validate paths before writes or deletes. |
| [synthesis-tree-of-thought](skills/synthesis-tree-of-thought/SKILL.md) | Multi-expert collaborative reasoning. |

### Guards

| Skill | What it does |
|---|---|
| [synthesis-agent-guardrails](skills/synthesis-agent-guardrails/SKILL.md) | Configure the guards beyond sends: account routing, deploys and their date rules, destructive commands, the reply check, the provenance scan. |
| [synthesis-message-guard](skills/synthesis-message-guard/SKILL.md) | The send guard: no send or draft goes out until you approve that exact call and its text passes the scan and format rules. |
| [synthesis-git-hooks](skills/synthesis-git-hooks/SKILL.md) | The commit check: credentials everywhere, unapproved disclosures where outsiders read. |
| [synthesis-disclosure-policy](skills/synthesis-disclosure-policy/SKILL.md) | Decide whether a real organization or person may be named outward-facing, with a precedent ledger and five tests. |
| [synthesis-promotion-gate](skills/synthesis-promotion-gate/SKILL.md) | Scan a built site for configured internal markers before an approved deploy, and refuse on any hit. |
| [synthesis-repo-guard](skills/synthesis-repo-guard/SKILL.md) | Find work stranded on this Mac (uncommitted, unpushed, unpulled, detached) in a read-only scan. |

### Knowledge bases

| Skill | What it does |
|---|---|
| [synthesis-knowledge-capture](skills/synthesis-knowledge-capture/SKILL.md) | Capture durable session facts in an OKF knowledge base with deduplication, confidentiality routing and provenance. |
| [synthesis-kb-edit](skills/synthesis-kb-edit/SKILL.md) | Edit, validate and ship knowledge-base changes through the repository's `.agents/knowledge-base.yaml` workflow. |
| [synthesis-okf](skills/synthesis-okf/SKILL.md) | Validate, convert and author content for Google's Open Knowledge Format (OKF v0.1). |

### Install, release and machines

| Skill | What it does |
|---|---|
| [synthesis-onboarding](skills/synthesis-onboarding/SKILL.md) | Install synthesis on a Mac, bring a workspace onto a new Mac, enroll in an organization, update or uninstall. |
| [synthesis-agent-conformance](skills/synthesis-agent-conformance/SKILL.md) | Audit that synthesis behaves the same in Claude Code, Codex and Muse: installed parity, hooks, instruction adapters, handoff. |
| [synthesis-skills-manager](skills/synthesis-skills-manager/SKILL.md) | Release this plugin and keep installs true to source. |
| [synthesis-skill-router](skills/synthesis-skill-router/SKILL.md) | Route a request to the right synthesis skill while keeping specialist metadata out of Codex's prompt. |
| [synthesis-machine-sync](skills/synthesis-machine-sync/SKILL.md) | Move work between Macs, and set up or retire a Mac. |
| [synthesis-mac-sync](skills/synthesis-mac-sync/SKILL.md) | Keep several Macs in step: config through iCloud, repositories through git. |
| [synthesis-fleet-secrets](skills/synthesis-fleet-secrets/SKILL.md) | Provision machine secrets from a vault onto a Mac by hand, with nothing in git. |

### Models and assistant setup

| Skill | What it does |
|---|---|
| [synthesis-model-tiers](skills/synthesis-model-tiers/SKILL.md) | Three role labels (judgment, routine, bulk) resolved to current model IDs per provider, so nothing hardcodes a model name. |
| [synthesis-local-model-runtime](skills/synthesis-local-model-runtime/SKILL.md) | Profile a computer, recommend open-weight models that fit it, install them and verify inference. |
| [synthesis-llm-setup](skills/synthesis-llm-setup/SKILL.md) | Set up Claude Projects, ChatGPT GPTs and Gemini Gems with custom instructions and knowledge. |
| [synthesis-technical-advisor](skills/synthesis-technical-advisor/SKILL.md) | Configure an LLM as a senior technical advisor. |
| [synthesis-creative-writer](skills/synthesis-creative-writer/SKILL.md) | Configure an LLM as a creative writing coach and editor. |
| [synthesis-response-merger](skills/synthesis-response-merger/SKILL.md) | Combine several LLM responses into one document. |

## How a skill is built

```text
skills/<name>/
├── SKILL.md              # frontmatter, purpose, binding rules, contents, procedure
├── agents/openai.yaml    # Codex display text and implicit-invocation policy
├── references/           # material needed for one step or one situation
│   ├── coverage-map.md   # where every rule of the previous version lives now
│   └── preserved.md      # retired text, verbatim, with the reason, when any was retired
├── scripts/              # executable parts, when the skill has any
└── tests/                # tests for those scripts
```

- **Binding rules** come first: numbered, one or two lines each, with the reason. They
  are the rules that must hold every time, and they sit where a harness that truncates
  or re-attaches a skill after compaction still delivers them.
- **Contents** lists every section and every linked file with a line saying when to read
  it. No reference file is linked from nowhere.
- **References** each fit in one read (at most 1,500 lines), and a long one opens with
  its own contents list.
- **Coverage maps** record, rule by rule, where the previous version's text went. Nothing
  was dropped silently when the skills were rewritten: whatever was not kept is in a
  `preserved` file with the reason.

The rules and the reasons for them are in [docs/skill-format.md](docs/skill-format.md);
`tests/test_skill_format.py` enforces the checkable parts.

## Durable project memory

Projects live as plain markdown in a git repository, so any session in any harness, on
this Mac or another, continues from files rather than from a chat transcript:

```text
ai-knowledge-<workspace>/
├── projects/
│   ├── index.yaml              # every project and its status
│   └── <project-id>/
│       ├── PRIME-DIRECTIVE.md  # optional; injected at session start and after compaction
│       ├── CONTEXT.md          # working state, with a current-state block
│       ├── REFERENCE.md        # stable facts
│       ├── sessions/YYYY-MM.md # session history
│       └── resources/artifacts/
└── lessons/
```

`synthesis` finds these repositories through `knowledge_roots` in the config, or else
every `~/workspaces/*/ai-knowledge-*`. One session owns a project's `CONTEXT.md` at a
time; other sessions working on the same project write contribution files for the owner
to reconcile. Switching harnesses on the same Mac needs no commit. Moving to another Mac
is `synthesis handoff` here, then `synthesis resume <project>` there. When several agents
contribute, the session log records one attribution line per agent, because different
tools often commit under the same human identity.

The conventions are in [synthesis-project-management](skills/synthesis-project-management/SKILL.md)
and [synthesis-context-lifecycle](skills/synthesis-context-lifecycle/SKILL.md).
[docs/spec/versioning.md](docs/spec/versioning.md) states what readers of these records
can rely on across versions.

## Verification

CI runs one command, and you can run the same one locally:

```bash
python3 -m pytest -q tests/ skills/
```

It covers the core, every skill's tests, the skill format, budgets and hook latency, and
a source lint (manifests agree, licenses present, no personal paths). Code must run on
Python 3.9. On a machine with the plugin installed, `synthesis doctor` checks the
installed side. [AGENTS.md](AGENTS.md) describes both, and the release process.

## Licensing

Each skill declares its license as an SPDX identifier in the `license` field of its
`SKILL.md`, and that identifier selects the terms that apply to the skill's folder:

- **[CC0 1.0](LICENSE-CC0)** (public domain dedication, no attribution required): 45
  skills, mostly methodology and writing.
- **[Apache 2.0](LICENSE-APACHE)**: 24 skills, mostly those built around executable
  code.

The plugin manifests declare the package as `Apache-2.0 AND CC0-1.0`.

## Related

- Many of these skills are practical artifacts of
  [synthesis engineering](https://synthesisengineering.org), including
  [synthesis coding](https://synthesiscoding.org),
  [synthesis writing](https://synthesiswriting.org) and
  [synthesis project management](https://synthesisengineering.org/blog/2025/12/14/ai-native-project-management/).
- [The article that introduced these skills](https://synthesiscoding.org/blog/2026/03/18/synthesis-skills-install-methodology-into-your-ai-workflow/)
  (March 2026; its install steps predate version 5).
- [Slopcheck](https://tools.synthesiswriting.org/slopcheck/): the content-quality and
  fact-checking methods as a web page.
  [tools/slop-detection/manifest.md](tools/slop-detection/manifest.md) lets a chatbot
  load the same methods from URLs without installing anything.
- [Why synthesis engineering exists](docs/why-synthesis-engineering.md) and the
  [runtime contract](docs/runtime-integration.md) for adding another harness.

## Contributing and support

See [CONTRIBUTING.md](CONTRIBUTING.md), [GOVERNANCE.md](GOVERNANCE.md) and
[SUPPORT.md](SUPPORT.md).

## Author

Created and maintained by [Rajiv Pant](https://rajiv.com).

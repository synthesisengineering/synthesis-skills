# Synthesis Skills

Proven AI agent skills for code review, content creation, project management, and more. Built on the [Agent Skills](https://agentskills.io) open standard and portable across Claude Code, OpenAI Codex, Cursor, GitHub Copilot, and other capable agents.

## What's new

**The EA layer: absence coordination and the calendar guardian (August 2026).**
New `synthesis-absence-coordination` skill **v1.0.0**: an absence treated as a
handoff with a scheduled reversal, not an announcement — principals hear it
first in one email with their assistants cc'd, group channels are hard-gated
behind that message, every work-facing notice must answer *who decides, what
waits, how to reach me*, and a `personal_continuity` tier keeps the trainer or
therapist whose standing sessions travel disrupts informed with time zones and
researched facilities. A quiet type notifies the minimum while suppressing
broadcasts. Config-validated (guard-contract exit codes, subprocess-tested);
ships with per-tier message templates and a fifteen-minute quickstart. And
`synthesis-chief-of-staff` **v1.1.0** adds the **calendar guardian** doctrine —
next-day/week/month look-ahead horizons, per-entry review checklists,
overcommitment checks with named move-candidates, and id-tracked auto-expiring
holds that shield open time from same-day ambush — wired into the
daily-rituals cadence by `synthesis-daily-rituals` **v2.20.0**. See the
[4.19.0 and 4.20.0 release notes](CHANGELOG.md).

**Agent correspondence, generalized (August 2026).** New `synthesis-agent-correspondence` skill (Communication family): how AI agents compose and send correspondence on a human principal's behalf, honestly. v2 models it as three lanes on one axis — how much of the principal is in the words: principal-direct (their words, their hands — no disclosure), the assistant lane (their words, the agent's hands — one authorship signature), and the bot lane (their direction, the agent's words — a handled-for-me signature) — with review depth demoted to internal governance and the bot-vs-assistant archetype binding a persona to its lane. Recipients learn the legend from the emoji alone. Includes the persona-registry config schema, verified channel-disclosure facts, and the three compose/send gates that pair with `synthesis-message-guard`. See the [4.16.0 release notes](CHANGELOG.md).

**Executive communication for technical leaders (August 2026).** New `synthesis-executive-communication` skill (Communication family): translating technical work for the non-technical executives who fund it — the every-noun persona test, the six-category kill-list, mechanism-to-consequence translation patterns, upward-report structure, and an in-persona adversarial review protocol. See the [4.14.0 release notes](CHANGELOG.md).

**One-command onboarding for people and whole organizations (August 2026).**
New skill `synthesis-onboarding` **v1.0.0**: a convergence engine that takes
a bare Mac to a working synthesis setup — plugin into Claude Code and/or
Codex, an `ai-knowledge-<workspace>` scaffold, receipts-backed idempotent
re-runs that repair half-finished installs and never overwrite files you
edited, skill rename/removal reconciliation, and a built-in doctor. An
organization onboards its members by shipping one declarative
`.agents/onboarding.yaml` manifest in its knowledge-base repo — no
installer code — and the curl-able `onboard.sh` covers individuals. See the
[4.13.2 release notes](CHANGELOG.md).

**Portable drift detection, mechanically enforced (August 2026).**
The `synthesis-git-hooks` **v2.3.0** doctor no longer assumes where the
skill source lives: its drift baseline resolves through an explicit
override, the running copy itself, or documented install locations, so the
same health check works from a fresh machine, a worktree, or a plugin
cache — and a misconfigured override fails closed instead of silently
skipping. `synthesis-agent-conformance` now scans the repository for
personal workspace paths so this class of defect cannot return. See the
[4.10.0 release notes](CHANGELOG.md).

**Disclosure governance by precedent, not blacklist (July 2026).**
`synthesis-disclosure-policy` distinguishes the names you deliberately
publish in your own biography from disclosures nobody approved, backed by
an evidence-cited precedent ledger. `synthesis-git-hooks` **v2.2.0**
enforces it by publication surface: your site repos get full protection
minus your ledgered names, public OSS repos stay pinned strict, and a
missing or unverifiable ledger fails closed. See the
[4.9.0 release notes](CHANGELOG.md).


**Trustworthy resumption and safe retirement (July 2026).**
Activation, handoff, and SessionStart context now detect stale project
checkouts by comparing the record with its fetched upstream, and handoff
verifies that both client envelope formats carry identical context.
`synthesis-project-management` **v1.8.0** makes lease-managed boards
self-declaring — a machine without the lease config refuses to write rather
than losing changes silently, with a sanctioned `lease-disable` path — and
adds `retire_worktree.py` for fail-closed, remote-verified retirement of
merged worktrees. See the [4.7.0 release notes](CHANGELOG.md).

**Symmetric verification and cross-machine coordination (July 2026).**
Conformance checks, doctors, and installers now resolve the Claude and Codex
CLIs through overrides, `PATH`, and documented install locations, so the same
verification runs from either client's shell. `synthesis-project-management`
**v1.7.0** adds an opt-in git-backed coordination lease — an atomic ref
compare-and-swap on a shared remote — for safe same-resource sessions across
machines, and claim-overlap detection now matches mixed absolute, `~`, and
relative claim spellings. See the [4.6.0 release notes](CHANGELOG.md).

**A stable inbox engine across native clients (July 2026).**
`synthesis-inbox-cleanup` **v1.4.0** installs verified, immutable engine
releases under `~/.synthesis/inbox-cleanup/engine/`. Claude Code and Codex
private workflows now share `engine/current` instead of depending on either
client's version-numbered plugin cache. See the
[4.5.0 release notes](CHANGELOG.md).

**Clean handoff after project completion (July 2026).** A completed synthesis
project now emits no pending actions during activation or SessionStart; checked
items are never relabeled as future work. See the
[4.4.4 release notes](CHANGELOG.md).

**One repository contract for every agent (July 2026).** The public source now
tracks its own `AGENTS.md`, with Claude Code importing that same contract
through a one-line adapter. CI verifies both files so contributors using Codex
and Claude Code receive the same repository rules. See the
[4.4.3 release notes](CHANGELOG.md).

**Trustworthy native-plugin status (July 2026).** Installer status now reads
the checked-out or plugin-packaged skill tree directly, verifies that the
Claude Code and Codex plugins are enabled, and fails clearly when no
authoritative source is available. A stale legacy cache can no longer produce
filesystem errors followed by a false pass. See the
[4.4.2 release notes](CHANGELOG.md).

**Accurate cross-client project recovery (July 2026).** Active-project
activation and SessionStart now share one parser that selects pending,
multiline project actions. See the [4.4.1 release notes](CHANGELOG.md).

**Parallel Claude Code and Codex sessions without shared-state collisions
(July 2026).** `synthesis-project-management` **v1.6.0** registers the machine,
project, heartbeat, isolated worktree/branch, source claims, and context role
for every root session. Different projects can proceed independently.
Same-project sessions use one canonical context owner plus non-overlapping
contributors with session-specific reconciliation artifacts. The helper
refuses shared worktrees, branches, claims, and context ownership. See the
[4.4.0 release notes](CHANGELOG.md).

**First-class Codex interfaces and agent-neutral automation (July 2026).**
Every public skill now carries a Codex interface with an explicit invocation
prompt. Day-end automation installs under stable `~/.synthesis/` ownership and
can launch Codex or Claude Code from one configuration, while the
correspondence safety doctor validates both clients independently. Source
conformance rejects client-bound runtime paths before they ship. See the
[4.3.0 release notes](CHANGELOG.md).

**One knowledge-base contract across agents (July 2026).** New
`synthesis-kb-edit` reads `.agents/knowledge-base.yaml` for editable and
generated paths, topic routing, the one frontmatter schema, confidentiality
controls, Git host, and review policy. `synthesis-okf` v1.1.0 adds a
config-driven seven-point consistency checker, and
`synthesis-knowledge-capture` v1.1.0 hands validation and shipping to those
shared layers. A knowledge-base edit can now move between Claude Code and Codex
without tool-owned workflow copies or date-field drift. See the
[4.2.0 release notes](CHANGELOG.md).

**A skip is not a pass (July 2026).** `synthesis-implementation-integrity` **v1.1.0** adds a Test Honesty check for a specific reading error: "X passed, Y skipped, 0 failed" gets read as "tests pass," but a skip is an absence of information, not a green light. The new step asks whether the skipped set could plausibly contain the one test that validates the exact property a decision depends on — most load-bearing for security, data-integrity, and irreversibility claims, where a skip in that territory is never neutral. See the [3.17.0 release notes](CHANGELOG.md).

**Multi-agent dispatch hygiene for project management (July 2026).** `synthesis-project-management` **v1.2.0** adds a "Parallel Sub-Agent Dispatch" section covering two risks specific to concurrent writers on one project: git-index collisions (a bare `git commit` after `git add <your files>` commits everything currently staged, not just what you added, so checking `git status --short` / `git diff --cached --name-only` first has to be a mechanical prefix, not a judgment call) and tracking-doc aggregation (sub-agents that each correctly leave siblings' work alone also mean no single agent sees the combined result, so the orchestrator reconciles all reports before updating the shared CONTEXT.md/index.yaml). Project Discovery also gains a scope re-verification step: before dispatching work against a paused project's stated "N items remaining," re-derive that count from live disk/repo state — the claim goes stale the moment anything else touches the same corpus, even a workstream unaware the paused project exists. See the [3.16.0 release notes](CHANGELOG.md).

**Google's Open Knowledge Format, validated and converted (July 2026).** New skill `synthesis-okf` **v1.0.0** fills the one gap Google's own OKF repo leaves open: a conformance validator and an idempotent frontmatter converter for OKF v0.1 (announced 2026-06-12 by Google Cloud's Sam McVeety and Amir Hormati). `okf_validate.py` checks the spec's three hard rules plus soft-guidance warnings and link-checking; `okf_convert.py` backfills frontmatter onto an existing markdown corpus without ever overwriting what's already there. Proven across several real conversions, from a small public reference repo up to a 72-doc personal knowledge base. See the [3.15.0 release notes](CHANGELOG.md).

**Day-end that survives tired evenings (July 2026).** `synthesis-daily-rituals` **v2.16.0** provides full and Quick Close modes, owed-weekly loose-ends review, explicit `Decays:` dates, and a state-aware notification. Its launcher and nudge live under `~/.synthesis/day-end/`, independent of client skill caches, and the launcher can open Codex or Claude Code. See the [4.3.0 release notes](CHANGELOG.md).

**Autonomous execution as a mode (July 2026).** New skill `synthesis-autopilot` **v1.0.0** encodes the delegation contract users otherwise retype per task: one explicit phrase ("take care of this for me," "autopilot this," "handle this end to end") engages a mode that sequences the existing stack — thinking framework for decisions, plan file + context lifecycle + checkpoint for compaction survival, anti-shortcuts for quality, implementation integrity before "done." Strict trigger discipline (explicit delegation only — ambiguity resolves to not engaging), batched user-only questions at checkpoints instead of blocking, and an explicit rule that standing gates survive autonomy: delegating a task never delegates authority the user has reserved. See the [3.10.0 release notes](CHANGELOG.md).

**Agent attribution for multi-agent projects (July 2026).** When Claude Code, Codex, Cursor, or subagents contribute to the same project, git history alone cannot tell you which agent did what: different tools commonly commit under the same human author identity. `synthesis-context-lifecycle` **v1.3.0** defines the convention — one compact line per contributing agent at the end of a session-log entry, recording agent, model, effort, scope, verification performed, and a durable ref. Unknown values stay the literal word `unknown` (never inferred from git trailers, which are authored claims rather than verified facts), and secrets never go in attribution fields. `synthesis-project-management` **v1.1.0** adds the convention to its Session End and Cross-Agent Handoff protocols, so a receiving agent knows who did what, with what verification. See the [3.8.0 release notes](CHANGELOG.md).

**Slop detection is now a free hosted tool.** [Slopcheck](https://tools.synthesiswriting.org/slopcheck/) at `tools.synthesiswriting.org/slopcheck/` runs the upgraded `synthesis-content-quality` and `synthesis-fact-checking` skills as a web app, with zero data collection and no signup. Same engine that ships with these skills, available without installing anything.

**Two major skill upgrades shipped in May 2026.** `synthesis-content-quality` reached **v4.0** with model-family fingerprinting across eight LLM families (Claude, GPT, Gemini, Llama, Grok, DeepSeek, Mistral, Qwen), a substance-and-depth section grounded in the Frankfurt-Pennycook-Hicks-Humphries-Slater framework, the compounding-archive principle that retains patterns across the LLM era, and per-family two-axis calibration with an ESL safe-harbor. `synthesis-fact-checking` reached **v2.0** with nine new protocol sections covering nested attribution, paraphrase drift, composite quotes, position-shifting, source-translation drift, URL rot vs hallucination, AI-generated synthetic sources, citation laundering chains, and tool-specific hallucination patterns by LLM family. See [CHANGELOG.md](CHANGELOG.md) for the full release history.

## Install

### One-command onboarding (new machines, non-engineers, whole ecosystem)

```bash
curl -fsSL https://raw.githubusercontent.com/synthesisengineering/synthesis-skills/main/onboard.sh | sh
```

The `synthesis-onboarding` engine converges your machine: plugin installed
into whichever of Claude Code / Codex is present, optional
`ai-knowledge-<workspace>` scaffold, verified by its built-in doctor.
Re-running is always safe — it updates and repairs, and never overwrites
files you edited. Organizations layer their own knowledge bases and shared
skills on the same engine with one declarative manifest (no installer code);
see `skills/synthesis-onboarding/references/org-manifest.md`.

### Native plugin for ChatGPT, Codex, and Claude Code

The repository is a dual-runtime plugin. The same `skills/` source tree is
packaged for the ChatGPT/Codex plugin system and Claude Code.

```bash
# Codex / ChatGPT desktop
codex plugin marketplace add synthesisengineering/synthesis-skills
codex plugin add synthesis-skills@synthesis-engineering

# Claude Code
claude plugin marketplace add synthesisengineering/synthesis-skills
claude plugin install synthesis-skills@synthesis-engineering
```

The Codex package also restores the active synthesis project after context
compaction. Run `synthesis-agent-conformance` to verify both runtime
installations, instruction discovery, and project handoff.

### Agent Skills installer

**One command — installs all skills to every AI agent on your machine:**

```bash
npx skills add synthesisengineering/synthesis-skills --global --all --copy
```

This works with Claude Code, OpenAI Codex, Cursor, GitHub Copilot, and [40+ other agents](https://agentskills.io).

### No Node.js? Use the shell installer

```bash
curl -fsSL https://raw.githubusercontent.com/synthesisengineering/synthesis-skills/main/install.sh | sh
```

Or clone and run directly:

```bash
git clone https://github.com/synthesisengineering/synthesis-skills.git
cd synthesis-skills
./install.sh install
```

### Install specific skills only

```bash
npx skills add synthesisengineering/synthesis-skills --global --copy --skill synthesis-pr-review,synthesis-codebase-review
```

### Update / Uninstall

```bash
npx skills update          # Or: ./install.sh update
npx skills remove synthesis-skills  # Or: ./install.sh uninstall
```

## Durable Project Memory

The project-management skills use a three-tier memory structure:

- `CONTEXT.md` for current working state
- `REFERENCE.md` for stable project facts
- `sessions/` for historical session archives

That structure keeps project memory in the repo, not inside one assistant's chat transcript or tool-native memory. A project can move between Claude Code and Codex, and between synced workstations, because every agent reloads the same durable project files.

When multiple agents work on one project, the session log also records provenance: one attribution line per contributing agent, capturing agent, model, effort, scope, verification performed, and a durable reference. Git authorship cannot make that distinction on its own, because different tools commonly commit under the same human identity.

## Available Skills

All skills are prefixed with `synthesis-` to prevent namespace collisions with skills from other repositories.

### Engineering
| Skill | Description |
|-------|-------------|
| `synthesis-codebase-review` | Enterprise-scale codebase audit with tiered review system |
| `synthesis-code-audit` | 10-dimension quality scan of code diffs with scored PASS/WARNING/FAIL verdicts |
| `synthesis-pr-review` | Delta review methodology with security scanning and AI-analysis verification |
| `synthesis-review-triage` | PR queue prioritization: scoring, author-response detection, and review routing |
| `synthesis-code-integration` | Adopt-and-adapt pattern for integrating multi-contributor code with cherry-pick safety |
| `synthesis-code-planning` | Structured multi-approach evaluation before coding |
| `synthesis-preflight` | Pre-merge quality gate: tests, types, audit, commit hygiene, go/no-go verdict |
| `synthesis-implementation-integrity` | Adversarial self-review: verify implementations are genuinely complete before shipping |

### Content Creation
| Skill | Description |
|-------|-------------|
| `synthesis-article-writing` | Two-phase workflow: research/validation then strategic writing |
| `synthesis-content-distribution` | Strategic content sharing and distribution across platforms with quick-start templates |
| `synthesis-link-research` | Find authoritative links for people, organizations, and entities |

### Content Enhancement
| Skill | Description |
|-------|-------------|
| `synthesis-content-quality` | v4.0 slop-detection methodology: model-family fingerprinting (8 families), substance-and-depth tests, two-axis calibration, compounding archive |
| `synthesis-fact-checking` | v2.0 fact-checking with 9 new protocols: nested attribution, composite quotes, paraphrase drift, citation laundering, AI-synthetic sources, tool-specific hallucination signatures |
| `synthesis-article-refresh` | Refresh old blog posts while maintaining temporal integrity |

### Communication
| Skill | Description |
|-------|-------------|
| `synthesis-agent-correspondence` | How AI agents compose and send correspondence on a human's behalf — the three-lane authorship model (my words / my words via my agent / my agent under my direction), a persona-registry schema with binding archetypes, channel disclosure facts, and the compose/send gates |
| `synthesis-concise-messaging` | High-Five Habit — condense messages to 5 sentences or less |
| `synthesis-executive-communication` | Translate technical work for non-technical executives — the every-noun test, the six-category kill-list, and upward-report structure for CTOs and product/engineering leaders |

### Project Management
| Skill | Description |
|-------|-------------|
| `synthesis-autopilot` | Autonomous-execution mode for explicitly delegated work: plan-file protocol, batched decisions, standing gates preserved |
| `synthesis-agent-conformance` | Cross-agent control plane: native plugin/runtime checks, instruction migration, lifecycle-hook health, and durable handoff verification |
| `synthesis-context-lifecycle` | Three-tier context architecture for managing AI working memory, with agent attribution for multi-agent provenance |
| `synthesis-project-management` | Lightweight PM system for human-agent collaboration, with cross-agent handoff, agent attribution, and parallel sub-agent dispatch protocols |
| `synthesis-daily-rituals` | Day-start and day-end checklists with dependency-ordered rituals |

### Knowledge Bases

| Skill | Description |
|-------|-------------|
| `synthesis-kb-edit` | Config-driven plain-language editing, validation, branching, review, and synchronization |
| `synthesis-knowledge-capture` | Reconcile durable session facts into the correct knowledge base with provenance |
| `synthesis-okf` | Validate OKF conformance, metadata consistency, taxonomy use, and convert existing bundles |

### Synthesis Engineering
| Skill | Description |
|-------|-------------|
| `synthesis-anti-shortcuts` | Deterministic enforcement of anti-shortcut discipline: costume-vocabulary catalog, constraint-first protocol, sub-agent hygiene, case studies |
| `synthesis-content-framing` | Content framing with topic, sophistication, and engagement gates |

### Reasoning & Templates
| Skill | Description |
|-------|-------------|
| `synthesis-thinking-framework` | Five-mode thinking methodology: first principles, systems, complexity, analogical, and design thinking |
| `synthesis-voice-profiler` | Generate a structured writing voice profile from samples for agent instruction files |
| `synthesis-tree-of-thought` | Multi-expert collaborative reasoning technique |
| `synthesis-llm-setup` | Configure Claude Projects, ChatGPT GPTs, and Gemini Gems |
| `synthesis-creative-writer` | Creative writer persona template |
| `synthesis-technical-advisor` | Technical advisor persona template |

### DevOps & Sync
| Skill | Description |
|-------|-------------|
| `synthesis-git-hooks` | YAML-driven pre-commit policy: auto-classifies each repo by push remotes (personal vs strict), enforces tiered patterns for credentials and exposure-sensitive content |
| `synthesis-inbox-cleanup` | Manifest-driven email cleanup across iCloud / generic IMAP (Python), Microsoft 365 / outlook.com (Mail.app AppleScript), and Gmail (workspace-mcp API + native server-side filters). Public engine + private rules. Ships with prompt-injection defenses and adversarial test fixtures for any LLM-augmented path. macOS. |
| `synthesis-mac-sync` | Multi-Mac config sync via iCloud with git repo sync and machine inventory |
| `synthesis-meeting-transcripts` | Fetch AI-generated meeting notes and transcripts into local working files |
| `synthesis-repo-guard` | Workspace sync guard: detect unsynced repos, confidentiality-safe alerts, event-driven checkpoint auto-commits for private context repos |
| `synthesis-slack-sync` | Slack channel sync protocol: read channels, threads, DMs to local transcripts |
| `synthesis-skills-manager` | Agent-native skill installer: drift detection, synthesis merge, provenance tracking |

### Background Instructions
| Skill | Description |
|-------|-------------|
| `synthesis-clean-text` | Produce text without AI watermarking patterns |
| `synthesis-response-merger` | Combine multiple LLM responses into one unified document |

## How Skills Work

Skills use progressive disclosure:

1. **Tier 1** (always loaded): name + description (~50 tokens) — matches your requests
2. **Tier 2** (on activation): SKILL.md body — the actual instructions
3. **Tier 3** (on demand): reference files for detailed material

The plugin layout is:

```text
.codex-plugin/plugin.json
.claude-plugin/plugin.json
hooks/hooks.json
skills/<skill-name>/SKILL.md
```

When you ask your AI assistant to do something that matches a skill's description, it loads automatically. Skills that involve writing include defaults that work standalone. If you have personal preferences in agent instruction files such as `CLAUDE.md` or `AGENTS.md`, those override the defaults.

## Related

Many of these skills are practical artifacts of [synthesis engineering](https://synthesisengineering.org), including [synthesis coding](https://synthesiscoding.org), [synthesis writing](https://synthesiswriting.org), and [synthesis project management](https://synthesisengineering.org/articles/ai-native-project-management/).

## Licensing

- **[CC0 1.0](LICENSE-CC0)** — methodology and content skills (no attribution required)
- **[Apache 2.0](LICENSE-APACHE)** — skills with executable scripts

## Learn More

Read the launch article: [Synthesis Skills: Install Methodology Into Your AI Workflow](https://synthesiscoding.org/articles/synthesis-skills-install-methodology-into-your-ai-workflow/)

## Part of the Synthesis Engineering Ecosystem

- **[Synthesis coding](https://synthesiscoding.org)** — AI-assisted software development
- **[Synthesis engineering](https://synthesisengineering.org)** — broader human-AI collaboration methodology
- **[Agent Skills standard](https://agentskills.io)** — the open format these skills use

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Author

[Rajiv Pant](https://rajiv.com) — technology executive, AI practitioner, and creator of synthesis coding.

# Synthesis Skills

Proven AI agent skills for code review, content creation, project management, and more. Built on the [Agent Skills](https://agentskills.io) open standard and portable across Claude Code, OpenAI Codex, Cursor, GitHub Copilot, and other capable agents.

## Install

**One command — installs all skills to every AI agent on your machine:**

```bash
npx skills add synthesisengineering/synthesis-skills --global --all --copy
```

This works with Claude Code, OpenAI Codex, Cursor, GitHub Copilot, and [40+ other agents](https://agentskills.io).

### No Node.js? Use the shell installer:

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
| `synthesis-content-quality` | 36-point quality framework for AI-assisted content |
| `synthesis-fact-checking` | Systematic fact-check process with multi-source confidence framework |
| `synthesis-article-refresh` | Refresh old blog posts while maintaining temporal integrity |

### Communication
| Skill | Description |
|-------|-------------|
| `synthesis-concise-messaging` | High-Five Habit — condense messages to 5 sentences or less |

### Project Management
| Skill | Description |
|-------|-------------|
| `synthesis-context-lifecycle` | Three-tier context architecture for managing AI working memory |
| `synthesis-project-management` | Lightweight PM system for human-agent collaboration |
| `synthesis-daily-rituals` | Day-start and day-end checklists with dependency-ordered rituals |

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
| `synthesis-mac-sync` | Multi-Mac config sync via iCloud with git repo sync and machine inventory |
| `synthesis-meeting-transcripts` | Fetch AI-generated meeting notes and transcripts into local working files |
| `synthesis-repo-guard` | Session-end enforcement: detect uncommitted changes and unpushed commits across a workspace |
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

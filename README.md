# Synthesis Skills

Proven AI agent skills for code review, content creation, project management, and more. Built on the [Agent Skills](https://agentskills.io) open standard.

## Install

**One command — installs all 22 skills to every AI agent on your machine:**

```bash
npx skills add rajivpant/synthesis-skills --global --all --copy
```

This works with Claude Code, Cursor, Codex CLI, GitHub Copilot, and [40+ other agents](https://agentskills.io).

### No Node.js? Use the shell installer:

```bash
curl -fsSL https://raw.githubusercontent.com/rajivpant/synthesis-skills/main/install.sh | sh
```

Or clone and run directly:

```bash
git clone https://github.com/rajivpant/synthesis-skills.git
cd synthesis-skills
./install.sh install
```

### Install specific skills only

```bash
npx skills add rajivpant/synthesis-skills --global --copy --skill synthesis-pr-review,synthesis-codebase-review,synthesis-fact-checking
```

### Update / Uninstall

```bash
# Update to latest
npx skills update
# Or: ./install.sh update

# Uninstall
npx skills remove synthesis-skills
# Or: ./install.sh uninstall
```

## Available Skills

All skills are prefixed with `synthesis-` to prevent namespace collisions with skills from other repositories.

### Engineering
| Skill | Description |
|-------|-------------|
| `synthesis-codebase-review` | Enterprise-scale codebase audit with tiered review system |
| `synthesis-pr-review` | Delta review methodology for pull requests, including security scanning and AI-analysis verification |
| `synthesis-multi-contributor-coding` | Adopt-and-adapt integration pattern with cherry-pick safety and regression verification |
| `synthesis-code-generation` | Structured multi-approach code generation (background instruction) |

### Content Creation
| Skill | Description |
|-------|-------------|
| `synthesis-thought-leadership-writing` | Two-phase workflow: research/validation then strategic writing |
| `synthesis-content-promotion` | Strategic content promotion across social media platforms |
| `synthesis-social-media-post` | Social media post template for multiple platforms |
| `synthesis-blog-promotion` | Blog post promotion template |
| `synthesis-hyperlink-research` | Find authoritative links for people, organizations, and entities |

### Content Enhancement
| Skill | Description |
|-------|-------------|
| `synthesis-ai-content-quality` | 27-point quality framework for AI-assisted content |
| `synthesis-fact-checking` | Systematic fact-check process with multi-source confidence framework |
| `synthesis-blog-revitalization` | Revitalize old blog posts while maintaining temporal integrity |

### Communication
| Skill | Description |
|-------|-------------|
| `synthesis-message-condensation` | High-Five Habit framework — condense messages to 5 sentences or less |

### Project Management
| Skill | Description |
|-------|-------------|
| `synthesis-context-lifecycle` | Three-tier context architecture for managing AI working memory |
| `synthesis-project-management` | Lightweight PM system for human-agent collaboration |

### Synthesis Engineering
| Skill | Description |
|-------|-------------|
| `synthesis-content-framing` | Content framing methodology with topic, sophistication, and engagement gates |

### Reasoning & Templates
| Skill | Description |
|-------|-------------|
| `synthesis-tree-of-thought` | Multi-expert collaborative reasoning technique |
| `synthesis-llm-project-setup` | Configure Claude Projects, ChatGPT GPTs, and Gemini Gems |
| `synthesis-creative-writer-setup` | Configure an LLM as a creative writer assistant |
| `synthesis-technical-advisor-setup` | Configure an LLM as a technical advisor |

### Background Instructions
| Skill | Description |
|-------|-------------|
| `synthesis-anti-watermarking` | Produce clean text without AI watermarking patterns |
| `synthesis-response-merging` | Combine multiple LLM responses into one unified document |

## How Skills Work

Skills use progressive disclosure:

1. **Tier 1** (always loaded): name + description (~50 tokens) — matches your requests
2. **Tier 2** (on activation): SKILL.md body — the actual instructions
3. **Tier 3** (on demand): reference files for detailed material

When you ask your AI assistant to do something that matches a skill's description, it loads automatically. Skills that involve writing or style include defaults that work standalone — if you have personal preferences in your CLAUDE.md, those override the defaults.

## Licensing

- **[CC0 1.0](LICENSE-CC0)** — methodology and content skills (no attribution required)
- **[Apache 2.0](LICENSE-APACHE)** — skills with executable scripts

## Part of the Synthesis Engineering Ecosystem

- **[Synthesis coding](https://synthesiscoding.org)** — AI-assisted software development
- **[Synthesis engineering](https://rajiv.com)** — broader human-AI collaboration methodology
- **[Agent Skills standard](https://agentskills.io)** — the open format these skills use

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Author

[Rajiv Pant](https://rajiv.com) — technology executive, AI practitioner, and creator of synthesis coding.

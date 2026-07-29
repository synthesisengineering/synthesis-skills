# Contributing to Synthesis Skills

Thank you for your interest in contributing to Synthesis Skills.

## How to contribute

### Reporting issues

If you find a problem with a skill — unclear instructions, missing context, incorrect guidance — open an issue describing what went wrong and what you expected.

### Suggesting improvements

Open an issue or pull request with your suggested changes. For substantial changes, open an issue first to discuss the approach.

### Contributing new skills

New skill contributions are welcome. Before starting:

1. **Check existing skills** — make sure your idea isn't already covered
2. **Open an issue** — describe the skill you want to create, its intended audience, and what problem it solves
3. **Follow the skill structure** below

### Skill structure

Every skill must include:

```
skills/skill-name/
├── SKILL.md          # Main instructions with YAML frontmatter (required)
├── references/       # Supporting reference material (optional)
├── scripts/          # Executable scripts (optional)
├── assets/           # Templates, examples (optional)
└── LICENSE           # CC0 or Apache 2.0 (required)
```

### SKILL.md requirements

- Valid YAML frontmatter with `name`, `description`, `license`, and `metadata` fields
- Description should be specific and include trigger phrases (what would someone say that should activate this skill?)
- Body should be under 500 lines — move detailed reference material to `references/`
- Use imperative form ("Do X" not "You should do X")
- Include examples where they clarify intent
- If the skill involves writing or style, include `references/voice-defaults.md` with standalone defaults

### Quality standards

Before submitting:

- [ ] Skill works standalone (no dependency on personal agent instructions or other configuration)
- [ ] SKILL.md has valid frontmatter
- [ ] Body is under 500 lines
- [ ] No personal or organization-specific content
- [ ] Examples are generic and widely applicable
- [ ] LICENSE file is present (CC0 for methodology, Apache 2.0 for scripts)
- [ ] `python3 skills/synthesis-agent-conformance/scripts/conformance.py source` passes

## License

By contributing, you agree that your contributions will be licensed under the same dual-license structure as the rest of the repository (CC0 for methodology content, Apache 2.0 for executable scripts).

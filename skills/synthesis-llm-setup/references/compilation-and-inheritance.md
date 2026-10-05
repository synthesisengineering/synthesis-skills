# LLM setup: compilation and inheritance

What each compilation includes, who can see it, and how to run instruction compilation.

## Compilation and inheritance

### How it works

Each user compiles projects in their own repo. What content gets included depends on inheritance.

**Example: Compiling in ai-knowledge-personal:**
```
compiled/
├── personal/                     # Baseline (ragbot + personal)
├── company/                      # personal + company merged
├── client-a/                     # personal + company + client-a merged
└── client-b/                     # personal + client-b merged
```

**Example: Compiling in ai-knowledge-company (team member without access to personal):**
```
compiled/
├── company/                      # Baseline (ragbot + company, NO personal)
├── client-a/                     # company + client-a (NO personal)
└── client-c/                     # company + client-c
```

### Privacy model

Content is only included if the user has access to the source repo:
- Private content (ai-knowledge-{personal}) only appears in that user's compilations
- Team members get team content but not personal content
- Clients only get client-specific content

### Running instruction compilation

```bash
# Compile instructions for a project
ragbot compile --project {name}

# Without LLM API calls (just assemble)
ragbot compile --project {name} --no-llm

# Force recompile (ignore cache)
ragbot compile --project {name} --force

# Verbose output
ragbot compile --project {name} --verbose
```

Knowledge concatenation (`all-knowledge.md`) is handled automatically by CI/CD -- no manual step needed.

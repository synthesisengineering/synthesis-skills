# Preserved: lines replaced in 2.0.1

2.0.1 (2026-10-05, final v5 sweep) replaced the lines below because they named commands v5
does not have: `synthesis workspace ensure` (the v5 `synthesis` CLI has no `workspace`
command) and `onboard.sh ... setup --profile skills-only` (v5 setup has no `setup` command and
no profiles). The v5 equivalent is synthesis-onboarding's `setup.py workspace --new NAME`,
which scaffolds the same knowledge repository and runs without the `synthesis` launcher. The
rule these lines served is unchanged: the companion lives in the personal knowledge
workspace, created by synthesis-onboarding, never a substitute folder. Nothing here is current
procedure.

## SKILL.md, binding rule 8

```text
8. **Live in the personal knowledge workspace**, `~/workspaces/{workspace}/ai-knowledge-{workspace}/`, created with `synthesis workspace ensure --name {name}` from `synthesis-onboarding` (install the CLI through `onboard.sh` if it is missing); never a substitute folder.
```

## references/setup.md, Setup step 1

```text
1. **Ensure the personal knowledge workspace exists.** Run `synthesis workspace ensure --name {name}`. It safely scaffolds `~/workspaces/{name}/ai-knowledge-{name}/`, including a seeded `projects/index.yaml`, a Git-tracked `.agents/workspace-AGENTS.md`, a tracked `.agents/knowledge-base.yaml` declaring the `source/` bundle, and collision-safe workspace entry points for both clients. It is idempotent when the workspace already exists, and it leaves every seeded file alone once you have edited it. If the `synthesis` command is not installed yet (a plugin-only installation has no launcher), install it first with the stable bootstrap: `curl -fsSL https://raw.githubusercontent.com/synthesisengineering/synthesis-skills/stable/onboard.sh | sh -s -- setup --profile skills-only`. A shared organization workspace is a sibling, not a substitute; this pattern's project files belong in the personal repository.
```

## references/background.md, Relationship to Other Skills

```text
- **`synthesis-onboarding`** provides the stable `synthesis workspace ensure` command used in Setup step 1 — this skill never scaffolds a substitute of its own.
```

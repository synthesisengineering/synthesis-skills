# Preserved text: bitbucket, retired in milestone M3

Read this only to review what was cut. The passages below are no longer
instructions; they are kept verbatim so the reasoning stays readable (ruling D8).

## Why the binding validator was cut

`scripts/repository_binding.py` (1,752 lines: about 1,650 lines of `bkt --help`
grammar captured as data, plus `validate_argv`) had no caller outside its own two
test files (v5 code evaluation, tool scripts, bitbucket: CUT). Its rule is real
and stays as binding rule 4: every repository-acting `bkt` command names exactly
one literal `--repo`, and a shared default context never selects the repository
(scenario E80). The likely incident behind it, an inference in the evaluation:
a shared `bkt` default context could aim an operation at the wrong repository.
`tests/test_bitbucket_skill_contract.py` now checks that every command the skill
documents names exactly one `--repo`, and keeps the vendor-help checks the old
`scripts/test_help_contract.py` made.

## SKILL.md 2.0.0 lines replaced (verbatim)

```markdown
4. **Bind every repository call with one literal `--repo <slug>`** (`api` takes its canonical literal path instead). Never use a mutable active context as repository evidence, even for reads or loops.
5. **A parsed binding identifies a target only.** It grants no send, review, merge or publication authority.
- [references/coverage-map.md](references/coverage-map.md): where each part of the 1.2.2 text now lives.
`scripts/repository_binding.py` validates the declared CLI grammar without calling
the provider or reading global context. The private shared pre-tool owner calls
this verified public module through its Codex and Claude pre-tool adapters; unknown syntax refuses with
a diagnostic. A client without an enrolled native pre-tool adapter has skill guidance, not demonstrated mechanical enforcement. Verify adapter capability and native acceptance before claiming parity. The parser result identifies a target only: it grants no send,
review, merge or publication authority. Refresh its grammar from the reviewed
CLI's own help when adopting another CLI version, and retain refusal controls.
```

The 1.2.2 SKILL.md held the same paragraph; its first line read:

```markdown
`scripts/repository_binding.py` validates the declared CLI grammar without calling
```

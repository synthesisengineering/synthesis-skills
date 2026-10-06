# Preserved: lines replaced in 2.0.1

2.0.1 (2026-10-05) replaced the lines below because they told an agent to run machinery
v5 removed: the git-hooks doctor (`~/.synthesis/git-hooks/_load_config.py --doctor`) and
a policy file the commit check found by a fixed path. In v5 the commit check reads the
policy that `commit_policy` in `~/.synthesis/v5/config.json` names, and it reads the
ledger at every commit in a public-surface repository, refusing on a stale allowance or an
unreadable ledger. The rule these lines served is unchanged: check the policy and ledger
after every edit, and a stale allowance or unparsable ledger is a failure, not a warning.
[coverage-map.md](coverage-map.md#changed-in-201) says where each now lives. Nothing here
is current procedure.

## SKILL.md, binding rule 10

```text
10. **Run the hook doctor after every ledger or policy edit;** a stale allowance or unparsable ledger is a failure, not a warning.
```

## references/policy.md

The precedent ledger, rules, the `hook_patterns` bullet's last line:

```text
  allowance auditable; the hook doctor flags stale allowances.
```

Maintenance protocol, step 3:

```text
3. Run the hook doctor after every ledger or policy edit; a stale
   allowance or unparsable ledger is a failure, not a warning.
```

## references/adopting.md, steps 3 and 4

```text
3. **Classify your surfaces** in `~/.synthesis/git-hook-config.yaml`:
   your published-site repos into `public_surface_patterns`, your public
   OSS repos into `strict_repo_patterns`, your private-notes namespaces
   into `personal_remote_patterns`, and `disclosure_ledger:` pointing at
   your deployed ledger.
4. **Run the doctor**
   (`python3 ~/.synthesis/git-hooks/_load_config.py --doctor`) and keep it
   in your rituals — a stale allowance or unreadable ledger is a failure.
```

## references/ledger.example.yaml, header comment

```text
# and point `disclosure_ledger:` in ~/.synthesis/git-hook-config.yaml at the
# deployed copy. This file is the machine-readable record of facts YOU have
# Rules (enforced by the synthesis-git-hooks engine and doctor):
#   public-surface repos. The doctor flags stale allowances.
```

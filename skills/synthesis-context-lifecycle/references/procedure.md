# Context lifecycle: the procedure

The steps of a session on a project: start, work, the doctor's check and close. Read it at session start and before closing a session. The binding rules in SKILL.md govern: where a wording here differs from a rule, the rule applies ("rule 12" below is binding rule 12). The protocols in full are in [session-protocols.md](session-protocols.md).

## Procedure

**Session start.** Establish this conversation's project with `synthesis resume <id>` (it asks before switching and warns about newer copies), then the Session Start Protocol: `date "+%Y-%m-%d %H:%M:%S %Z (%A)"`; `git log -10 --pretty=format:"%h %ai %ci %s" -- <project>` and `git status --short -- <project>`; read CONTEXT.md, the newest dated session entries and REFERENCE.md; title the session after the project where the client allows it. Show the result in one line: today, last commit, whether CONTEXT.md matches.

**During work.** After each task, update CONTEXT.md under your claim. Keep the current-state block (Phase, Status, Last session, Plan, Next actions) current: it is what returns after compaction. Archive when CONTEXT.md passes 120 lines.

**Check.** Run the doctor for this project:

```bash
python3 -s "$HOME/.synthesis/v5/current/skills/synthesis-context-lifecycle/scripts/context_doctor.py" --project <root>/projects/<id>
```

It prints this project's findings, each `FAIL` or `warn` with a remedy line, then `HEALTHY` or `DEFECTS` with totals; it exits 0, 1 or 2. Without `--project` it audits every knowledge root, leads with this session's project and counts the rest.

**Close.** Append the session entry (with Attribution lines when several agents contributed), refresh the header and current-state block, archive cold content, run the doctor, and hand off per rule 12.

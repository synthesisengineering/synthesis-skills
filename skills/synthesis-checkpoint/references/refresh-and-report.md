# Refresh and report after an ecosystem change

Use this mode when asked to refresh an existing session after an upgrade, check
readiness, or report upgrade findings. It works for a first or repeated
refresh. The short user invocation is: "Run the current installed
synthesis-checkpoint skill in refresh-and-report mode."

## When it starts

After a release installs, the hooks run the new version at once, and a session that last saw an
older one gets a note at its next prompt or start: the two versions, the changelog sections in
between, and this mode as the way to refresh skill text loaded earlier. The note comes once per
session per release. Run this mode then, or whenever asked.

## Scope

Stay with this conversation's established project and workspace. This mode
inspects and reports; it does not repair projects, migrate anything, take or
release claims, publish, install, or schedule automations. Leave foreign work
and native memories unchanged. App closure and a quiet session do not prove a
claim is finished.

If a previous refresh ran in this conversation, read its actual output, keep
its failures and warnings, and reuse valid results rather than repeating
project work.

## Steps

1. **Runtime.** `synthesis version` names the installed runtime;
   `synthesis doctor` (or `--json`) checks the installed runtime, the stable
   hook path, each harness's plugin and hooks, and the guards' config, and
   names each problem. A missing or stale runtime is a reported installation
   problem, not permission to copy files.
2. **This session.** `synthesis who` shows this session's row (harness,
   project, claims); `synthesis inbox` shows unread messages.
3. **The project.** `synthesis brief` (or `synthesis resume <id>` in a fresh
   session) prints the directive, current state and plan; read the files it
   points to. A reported conflict stops project inspection beyond reporting it.
4. **The records.** Run the context doctor on the project:
   `python3 <synthesis-context-lifecycle>/scripts/context_doctor.py --project <path>`.
5. **The skill text.** Compare the skill bodies in context with the installed
   ones when the upgrade changed them; a stale loaded skill body is a reason to
   reload, not proof that the current startup failed.

## Reload evidence

Current skill text and a native runtime reload are distinct evidence. Never
equate an old in-context skill body with a failed current startup, or copying
new files with proof a running harness reloaded them. Installing or copying a
cache in place is not itself a reload. The evidence comes from the subsequent
client lifecycle event, not from the installer.

When the running session predates the installed version:

1. Save the durable checkpoint (records on disk).
2. Ask the user to restart the current client and resume this same
   conversation when the client can rehydrate an existing task.
3. After the restart, confirm that the SessionStart hook ran again: its
   re-injected project brief is back in context and `synthesis doctor` reports
   the runtime current.
4. Ask for a new conversation only when restart is unsupported or the
   re-injection did not happen.

Never fabricate an event or relabel an installed tree as a live reload.

## Report

Finish with the project, the separate runtime, session and claim results, the
checks reused and run fresh, unresolved issues, and the claim disposition
(release claims taken only for this pass). Peer reports go through
`synthesis msg <session or project:id>`; this mode sends nothing to email,
chat or anyone as the user. Stop after reporting and wait for the user's next
project instruction.

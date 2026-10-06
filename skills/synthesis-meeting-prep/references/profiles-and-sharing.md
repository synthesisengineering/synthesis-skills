# Meeting prep: profile configuration and shared contributions

Where the principal and reader profiles live, how `prep_init.py` binds them to one workspace, and how another seat contributes to a prep pack. Moved verbatim from the 1.3.0 SKILL.md; only link paths changed. Read it before any profile operation or shared write.

## 1. Configuration contract

Select the meeting's owning workspace before loading a profile. Resolve its
approved private context repository through the workspace's existing registry
and routing policy. Relationship-bound profiles belong in that workspace's
deletion unit. Personal records that must survive the relationship follow the
principal's retention policy separately; never migrate a mixed profile until
its ownership is resolved.

Every profile operation requires the explicit absolute repository root and a
stable workspace id. The tool verifies the exact Git checkout root and binds
the profile directory to that id. These arguments assert an already approved
private destination; a Git remote or repository name cannot establish privacy.
The tool does not discover a repository from the current directory, search
other workspaces, or fall back to the user's home directory.

```text
<context-repo>/profiles/meeting-prep/.owner.json
<context-repo>/profiles/meeting-prep/principal.json
<context-repo>/profiles/meeting-prep/readers/<id>.md
```

Use `scripts/prep_init.py resolve --context-repo /absolute/private-context
--workspace example` to resolve this directory without creating it. Pass the
same two owner arguments to `init` or `add-reader`. Creation refuses an
existing file; edit existing content through the context repository's normal
record workflow. New files are mode 0600 and new directories are mode 0700.

`principal.json` holds the principal's role, goals, authority, positions, and
pressure responses within this workspace. Reader profiles hold relationship,
technical depth, current concerns, prior context, and what landed last time.
Scaffold with `init` and `add-reader`, then complete the interview using this
workspace's evidence. Missing profiles permit the three essential questions
(reader relationship, technical depth, meeting purpose) and a draft using only
current context. Missing or ambiguous ownership prevents profile reads and
writes; it never triggers a search of global or other-workspace profiles.

Legacy global profiles need an explicit per-file ownership and hash map. The
existing prep owner provides read-only preflight and bounded apply/resume;
see [workspace-profiles.md](workspace-profiles.md). Migrating one
workspace leaves unresolved and other-owner entries untouched.

## Shared prep contributions

A broad `meeting-preps/` claim remains exclusive for ordinary edits. To accept a
contribution, its authenticated active recipient uses `prep_init.py share-pack`
with the exact contributor seat, private context repository, workspace, literal
Markdown artifact, create/append operation and (for append) reviewed SHA256.
`--private` asserts the already approved private destination; names and Git
remotes are not privacy evidence. Both seats register the same physical checkout
and branch; the profile owner marker and any team registry must agree. A team
shared/public repository cannot receive these private prep contributions.

The grant is recorded in the recipient's own coordination row, expires within
one hour (15 minutes by default), and binds its current ordinary claim scope.
Do not paste grant markers into `coordination claim`, narrow or release another
seat's claim, or claim the overlapping artifact as exclusive. Missing or ambiguous
authority refuses before an artifact effect. The recipient can invalidate grants
by changing its held scope or releasing its own seat through existing owners.

The contributor uses `prep_init.py write-pack` with that grant ID, native event
payload and bounded text file. Creation requires absence; append preserves the
complete reviewed prefix. The existing record transaction serializes competing
writers, rejects changed preimages and retains interruption custody. Restore
valid current authority and use the existing transaction recovery owner with the
same `meeting_prep_share` selection to recover; never remove its journal by hand.
A grant covers one artifact and transaction custody only. It grants no generic
edit, profile migration, publication, deployment or recipient impersonation right.
The recipient retains publication custody under its existing claim.

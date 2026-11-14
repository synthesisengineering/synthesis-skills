# Meeting prep: profile configuration and shared contributions

Where the principal and reader profiles live, how `prep_init.py` binds them to one workspace, and how another session contributes to a prep pack. Section 1 moved verbatim from the 1.3.0 SKILL.md apart from its last paragraph; the shared-contribution procedure was rewritten for the v5 board. The retired text is verbatim in [preserved.md](preserved.md). Read it before any profile operation or shared write.

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

Profiles that lived in the old global folder (`~/.synthesis/meeting-prep/`)
were migrated into their owning repositories in 1.3.0, and that folder is
empty. If one ever reappears, classify each file's owner first, then move it
with ordinary file and git operations into that workspace's repository; never
migrate a mixed profile until its ownership is resolved, and never copy one
into another workspace. See [workspace-profiles.md](workspace-profiles.md).

## Shared prep contributions

A prep pack lives inside some session's claim (often a broad `meeting-preps/`
claim held by the operations seat). Another session never writes inside a
claim it does not hold: the v5 commit check refuses a commit there, and an
uncommitted edit collides with the holder's work. To contribute:

1. Find the holder: `synthesis who`.
2. Send the contribution as a message, with the exact artifact path and the
   text: `synthesis msg <holder> "<artifact path>: <text to add>"`. The holder
   sees it on its next prompt.
3. The holder either writes the text in itself, or releases that one file
   (`synthesis release <path>`) so the contributor can `synthesis claim <path>`
   it, write, and release it again.

A contribution covers one artifact and nothing else: it is no permission to
edit other files, migrate profiles, publish, deploy, or speak for the holder.
Private prep content goes only to the workspace's private repository; a shared
or public team repository never receives it. The holder keeps publication
custody.

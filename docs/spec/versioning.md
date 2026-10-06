# Versioning and what readers can rely on

Three things carry versions here: the plugin, each skill, and the session files
on the coordination board. Project records carry none.

## The plugin

One semantic version covers the whole plugin. It appears in
`.claude-plugin/plugin.json`, `.codex-plugin/plugin.json` and
`.muse-plugin/plugin.json`, which must agree, and the newest entry in
[CHANGELOG.md](../../CHANGELOG.md) must be that version. The source lint in
`tests/test_source_lint.py` fails otherwise.

A release is a `vX.Y.Z` tag. The `stable` branch points at the latest release,
and `main` is where development lands. New installs follow `stable`; setup's
`--ref main` or `--ref vX.Y.Z` follows the development branch or pins a release,
and an update without `--ref` keeps whichever the install already follows.

## Skills

Each skill carries its own version in `metadata.version` in its `SKILL.md`,
independent of the plugin's. Release 5.0.0 moved every skill to its next major
version when it was rewritten into the format in
[skill-format.md](../skill-format.md). A rewritten skill keeps a coverage map
from its previous version's rules to where they live now.

## Project records

A project is plain markdown in one format, with no version field and nothing to
migrate. To read a project, `synthesis` needs only its folder under
`projects/` and a `CONTEXT.md`. Everything else is optional: a
`PRIME-DIRECTIVE.md`, the current-state block in `CONTEXT.md`, a `Plan:` field,
`REFERENCE.md`, `sessions/` and `resources/`. A project written by an earlier
version of these skills is read as it is. Files the reader does not use, such as
the `archive/` folders and migration markers the retired version-2 format added,
are ignored, never rewritten or removed.

## Board session files

Each session's file on the coordination board records a schema number. A reader
that meets a file from a newer schema says so (`synthesis who` prints a note
naming it) and never rewrites it. A reader that meets newer state names the
version and the update it needs, rather than repairing the file.

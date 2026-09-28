# Explicit project-format migration

Use `synthesis project-migrate plan --index <registry> --select <project-id>
--target-format 2 --json`. Repeat `--select` for an exact set, or choose
`--all-declared` to freeze all IDs in that explicitly selected registry. No home,
workspace or repository crawl selects projects implicitly. Each project is
resolved causally with fetch, fast-forward and coordination refresh disabled.
For several workspaces, produce a separate exact plan for each declared registry;
those plans retain independent consent and owner boundaries.

The only implemented transition is the existing v1→v2 format. This package does
not choose SQLite, invent a future format, replace CONTEXT/REFERENCE/session
records, or infer that upgrading the ecosystem release upgrades a project.
Partial, ambiguous or unknown formats refuse. A verified existing v2 project can
appear in a plan as `verify-current`, with no rewriting. Its marker, state and
session index must validate rather than merely exist.

The preview includes exact selected IDs, registry and directory identities,
source inode/hash/mode/size evidence, complete proposed UTF-8 output bytes and
hashes, a one-hour validity interval, and a digest. The canonical builders create
`.synthesis-project.yaml`, `RESUME_STATE.json`, and `sessions/INDEX.md`.
A generated resume skeleton and extracted open loops are marked unverified;
they never become a decision, approval, proof of completion or native acceptance.
The preview is a private proposed diff, not consent to apply it.

`project-migrate apply --plan <preview> --approve <digest> --board <board>
--native-payload <payload>` accepts that exact reviewed plan. `--dry-run` checks
inputs and real authority without creating a store, archive or target. `--project
<id>` selects one project already in the approved plan for execution by its real
native owner. Other projects remain explicitly pending. Without this selector,
every requested project's authority is checked before the first mutation.

PM admission still binds a native seat to its exact project/checkout and claim.
An approved multi-project plan is not permission to impersonate other sessions,
create their claims, release them, or bypass their record barriers. Execute each
project through its genuine owner; archive and transfer are not approvals.
Claims must cover the new paths and the existing `.record-transactions` store.

The existing record transaction owner stages new files, captures the exact
original CONTEXT/REFERENCE/session bytes into its private source custody,
fsyncs custody and commit intent, then uses no-clobber creation. A new competing
file is preserved. Modes are private 0600; no executable records are created.
Source files remain byte-for-byte and inode-for-inode unchanged. The manifest
retains their original identities and authenticated copies before effects.

One project is a cooperative recoverable transaction, not simultaneous atomic
renames visible to arbitrary readers. A selected set is not one global filesystem
transaction. Consent freshness is rechecked under the project lock immediately
before each new project transaction, after whole-set preflight and re-derivation.
A wait or earlier project cannot extend that lifetime. If a later outside change
or expiry interrupts execution, completed project
receipts remain committed and other projects remain incomplete. Existing managed
readers refuse an active partial transaction. External readers do not acquire
this protection merely by reading ordinary paths.

`project-migrate recover --plan <preview> --approve <digest> --board <board>
--native-payload <payload>` can finish only the exact original journal intent;
expiry does not authorize new migrations. The same `--project <id>` selector
limits recovery to one approved project under its genuine owner. It retains missing/corrupt/foreign
states rather than overwriting them. Completed intent is verified by its
independent history binding, manifest/commit hash, preserved source custody and
exact final target inodes. Identical repeat application verifies completed intents even after preview
expiry; it cannot start an uncommitted project with expired consent. Verification
and exact-journal recovery do not authorize new effects;
later edits are not silently migrated again. `project-migrate verify --plan
<preview>` verifies derived format custody. It does not establish client reload,
hook trust, native execution or cross-client semantic acceptance.

Plans allow at most 128 selected projects and 512 source files per project,
8 MiB per input, 32 MiB combined source custody/output per transaction and a
1 MiB plan. Capacity exhaustion is a refusal, never silent truncation. The
existing record owner retains its five-second locks and 4,096-entry history
bound. Preserve interrupted preparations, original failures and completed
custody through the project evidence owner; never prune them to pass a gate.

Deployment requires the matching onboarding CLI, project-format builders and
record-transaction module in one verified release. Installation alone is not
migration. An actual selected-project migration and each client's native reload
remain separately observable acceptance operations.

# Verification custody in a shared workspace

Run verification in an isolated copy by default. Pin its source commit and each
uncommitted input hash; direct temporary outputs, caches, profiles and generated
stores into a named scratch root. Existing claims and publication gates remain in
force. A clean source checkout says nothing about an unexamined cache elsewhere.

When a check genuinely requires a shared checkout, record its exact allowed write
set, claims, original bytes, modes, existence and file identities before execution.
Also record pre-existing dirty and untracked paths. Refuse the check if it cannot
bound its writes. Use the owning store's transaction/lock rather than a second
advisory mechanism, and retain every failure and interruption record.

After the check, compare all paths in its declared write set and its observed
deltas, including ignored files. Every uncommitted change made by the check must
be restored to its authenticated original state or retained with an explicit
unresolved disposition. Restore only the check's own proven bytes under the
owner's lock after verifying the current identity and digest still match what the
check wrote. If another process changed a path, preserve both versions and report
the conflict; never overwrite that later edit. An attributed manifest is evidence,
not authority to alter someone else's work.

Never use a blanket reset, stash, checkout or untracked-file deletion to obtain a
clean result. For a newly created path, remove it only through its authorized owner
after verifying exact provenance and retained evidence. If safe restoration cannot
be proved, stop mutating the shared checkout and complete independent checks in the
isolated copy. Report the unresolved path custody without declaring verification
clean. No source publication or foreign-manifest cleanup follows from this check.

The final handoff lists source pins, test command/environment, all output roots,
process dispositions, each restored or retained path and any publication still
required. Interruption does not turn incomplete restoration into success.

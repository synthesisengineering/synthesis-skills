# Team contract and participation boundaries

Read this contract before enabling multi-person coordination. Its owner is
`scripts/team_contract.py`; the existing coordination, project-state, enrollment,
Git guard and repository ACL owners remain authoritative for their own effects.
This is an opt-in source contract. A passing validator is not account enrollment,
proof of a person's identity, a host ACL, permission to send, or a native trial.

## Organization, people and standing roles

A version-1 team declaration binds an organization, deletion unit and monotonic
revision to people, immutable host account IDs, repositories, entitlements,
standing-role occupancy and release governance. Usernames are display labels.
Keep real roster/account mappings in the organization's approved private store.
A service identity names active human custodians and cannot occupy a human role.
Retired opaque IDs remain in attributable history; private biographical records
follow their deletion unit. Never rewrite an old author as the new occupant.

A standing role is separate from a temporary coordination session. Its dated,
non-overlapping occupancy records the prior and next human, a digest of the
succession brief, and explicit cover. `transfer_occupancy` is a pure proposed
transformation with a revision compare; the organization owner publishes it
under the existing claimed-record transaction and approval boundary. It does
not transfer sessions, leases, credentials, repository access or old approvals.
Offboarding checks account revocation, open occupancy and outstanding owned
claims separately; unknown evidence cannot become an offboarding pass.

## Enabling a team board

1. Verify all selected readers understand schema 6, using the release-bound
   coordination/conformance owners. Readers that cannot parse the schema must
   refuse it. Preserve the original board and history through the existing
   migration/record owner; do not hand-rewrite a live shared board.
2. Under the board owner's authority, release all existing sessions through
   their actual owners. Use `coordination.py migrate --team-contract team.json
   --team-digest <sha256> --expected-board-sha256 <reviewed-board-sha256>` to bind
   the regular sibling declaration through the existing lock/Git CAS owner.
   The command refuses stale boards, active/parked sessions and source drift;
   ordinary session mutations cannot add, remove or replace this binding.
   This explicit enrollment records a declaration, never a reader-readiness
   attestation. Actual reader qualification is the separate prerequisite above.
3. Claim through the current coordination CLI with `--person <opaque-id>` and,
   when applicable, `--standing-role <opaque-id>`. The native session, agent,
   client and machine must match their existing exact identity checks. The
   person must be the current occupant or explicit cover for the standing role.
4. Every claim still uses existing repository identity, scope and lease rules.
   Changing the person label on an existing session is forbidden. Succession
   names the incoming principal explicitly; it cannot adopt a foreign claim.
5. Include one `Session identity: {"session":"…","person":"…","native":"…"}`
   line in each newly written dated session entry. Keep legacy unattributed
   entries unattributed. The context doctor counts distinct sessions on the same
   day and refuses contradictory identity metadata; nested headings are not
   extra sessions. Checkpoint receipts bind the writer tuple to the board digest.

These declarations do not authenticate the human who supplied an opaque ID.
The repository/board hosting ACL and organization enrollment ceremony are the
identity backstop. Test those with a genuinely independent person before
claiming team acceptance. Editor bypass, remote-host enforcement and stale
lease behavior must be exercised at the actual deployment boundary.

## Shared and private sources

Shared organizational records and each person's private companion are distinct
repositories in the same deletion unit. A private companion has one declared
reader; that does not imply administrators cannot access the hosting service.
A shared reference may not depend on content inaccessible to its reader set.
An unavailable private tier is `UNKNOWN/UNAVAILABLE`, not an empty or clean tier.
Registry union must retain repository-qualified project identities and conflicting
sources; do not merge restricted prose into the shared index. Review each
lesson's audience before promotion. Archive ownership follows the source owner.

## Policy and approvals

Mandatory restrictions compose by union; allowed approval roles compose by
intersection. Empty eligible roles mean no authority. Reader floors only rise.
An individual allowlist never subtracts a team requirement. Actor identity and
the subjects mentioned in content are separate disclosure checks. Reuse each
existing action owner for exact approval and single-use receipt enforcement.

For Git, the owner may enroll digest-bound `team_policy_files` in the existing
private guard configuration. Each source has schema 1, organization, explicit
credential-free `repository_prefixes`, and `mandatory_patterns`. No exemptions
are accepted. The mandatory rules run before personal allowlists and path
exclusions, for both staged content and commit messages. Changed source bytes,
unsafe file identities and malformed declarations refuse the operation. This
package does not activate a policy or configure a host branch rule.

## Enrollment and releases

The organization manifest may bind `team_contract: {path, sha256}`. Persist
`principal_selection: {person, requested, team_digest}` in that organization's
existing desired-state entry. Enrollment derives required, optional and role-
gated resources from the complete inventory; excluded resources are excluded,
not permanent errors. A changed declaration requires renewed explicit selection.
Fresh selection uses the actual enrollment owner: `synthesis enroll --org-repo
<approved-repository> --team-person <opaque-id> --team-digest <reviewed-sha256>`.
Repeat `--team-entitlement <id>` for optional resources. Omitting optional resources
selects only eligible required resources. Repeating enrollment without these flags
preserves the existing explicit selection; changing any selection requires both
person and current declaration digest. Stale declarations or unauthorized resources
refuse before enrollment effects. This is selection, not human authentication.

Each knowledge entitlement binds a declared repository ID; its actual source
remote and reader set are checked before acquisition. A required resource
outside that person's audience remains excluded, and an explicit request refuses.
Host membership is person-once; native authentication, client readiness,
configuration and receipts are machine-each. No secret is copied by this contract.

Receipts and caches are organization/deletion-unit-qualified. Installing another
organization cannot retire the first organization's copies. A target collision
refuses; it does not silently replace an installed skill. Unscoped historical
copies require owner-led reconciliation rather than automatic reassignment.
Shared skill sources pin stable/edge plus an exact version, mirror owner and
review/direct-main-audit policy. Personal configuration belongs outside installed
copies; private namespaces use opaque principal IDs. Existing release and
verified-runtime owners enforce integrity and installed dependency closure.

## Fleet and actual acceptance

Reuse causal project recovery, machine-sync and fleet-handoff owners. Wall-clock
order alone cannot resolve conflicting updates. Offline or unknown remote state
never proves freshness, grants a lease or authorizes overwriting a peer. Fleet
health contains only declared opaque identities, capability state and evidence
pointers, not transcripts, secrets or private content. Environment-specific
resource/secret declarations stay separate; no migration is activated here.
A local per-person Console may observe shared sources under the person's ACL.
A hosted team Console requires a separate identity/authentication design.

Completion requires an independent second person to perform a complete native
session cycle, plus real second-machine enrollment and interruption recovery.
Synthetic adapter fixtures, installed bytes and declared identities establish
only their named layers. Preserve failed trials and unknown historical evidence.

## Managed action and contribution owners

Read [managed team workflows](team-managed-workflows.md) before using team-bound
registry readers, publication approvals, contribution reports, appointments or
retirement. These commands reuse record, coordination, enrollment and release
owners; their acceptance boundaries distinguish managed custody from host access.

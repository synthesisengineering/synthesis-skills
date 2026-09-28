# Provider changes and incident replay

The existing conformance owner accepts source-led triage through
`scripts/provider_intake.py change` and sanitized draft incidents through
`incident`. `replay` executes a bounded, fixed synthetic validator corpus; it
accepts no arbitrary command, provider call or caller-supplied pass receipt.
Use the release-verified public entrypoint. All commands emit JSON only.

A change binds provider, exact version, dated official-source URL and SHA-256,
affected surfaces, classification and evidence references. An official URL is a
source-location constraint, not proof this process fetched or authenticated it.
Inspect and bind the actual official release before authoring the input. Preserve
source, installed, available, live, outcome and continuity evidence separately.
Material changes need positive and negative controls for selected clients. Refresh
the support matrix for every relevant release and during declared maintenance;
this source package creates no recurring automation or account work.

An incident records a synthetic-only reproducer and retains attribution as
OpenAI/Synthesis/environment/unknown according to actual evidence. Automatic
redaction is a candidate sanitizer, not proof of complete disclosure review.
Contact and publication remain unauthorized until the owner approves exact text.
Keep private originals in their existing deletion unit. Never send logs, tokens,
full native transcripts or unrelated workspace paths by inference from an error.

A replay request has schema 1, scope `synthetic-only`, and 2–256 uniquely named
cases: id, operation (`change` or `incident`), input, expected accepted/refused.
Include both expected outcomes. Results bind input/output hashes and observed
validator outcomes. CONTROL_MISMATCH, errors and missing cases remain failures.
A passing local replay does not establish the cause of a real provider incident.

For Cursor and Copilot, separately qualify startup, catalog visibility, matching,
body loading, references, user-invocable:false, disable-model-invocation and
cross-skill references in actual clients. Fixture adapters cannot certify native
support. Keep each upstream issue/PR watch distinct and verify its current state
before acting. A historical open status is not a present status. Submitted versus
prepared-only outreach and expanded submission scope remain owner decisions.

Contributor, research, directory, adoption and community packages each name the
owning project, source/evidence, intended audience, exact proposed artifact,
approval boundary and next action. Articles stay publication-owned. No provider
contact, directory submission, community message or standards adoption is implied.
A2A remains conditional on the accepted named-edge trigger; do not create an
adapter merely because a protocol exists. File/JSON handoffs retain their current
transport-neutral record owners.

## Compatibility corpus preparation and review

`corpus-prepare` accepts schema 1, `corpus_id`, `source_kind` (`synthetic` or
`local-original`), and one to 64 `members`, each with a unique `id` and `text`.
Each text is at most 64 KiB. The request, candidate and decision specification
are each bounded to 1 MiB of canonical JSON; the packet command returns both
candidate and specification plus framing. It reduces common credential, email,
URL, path, network and stable-ID patterns, replaces source labels with generated case IDs, and hashes the exact
input. This is a local review candidate: ordinary prose can retain identifying,
private or protected details. Zero matches never imply safe disclosure.

`corpus-packet` uses the existing decision-packet owner to bind the exact source,
candidate bytes, every case and five whole-corpus dimensions: provenance, direct
identification, indirect identification, negative/protected content, and
cross-case aggregation. The recommendation remains unresolved until review.
Use `--corpus-source` with the original saved JSON file to bind its exact raw
bytes; without that flag the binding is to the canonical request JSON. The file
must be bounded and regular without aliases or hardlinks and is rechecked after
the consumer runs. Even whitespace changes invalidate a raw-file review.

`corpus-review` takes `{request, summary, provenance}`. Provenance records claimed
`principal`, `source_ref`, `received_at` with timezone, `scope`, and
`authority_ref`. The current source is re-prepared and the actual decision owner
parses the exact-spec summary. Changed source, stale packet hashes, unknown rows,
and unbound summaries refuse. A complete summary records `EXACT_SPEC_REVIEWED`;
partial or held findings remain `REVIEW_REQUIRED`. Claimed provenance stays
unverified and `authorization.granted` and `publication_authorized` stay false.

`corpus-publish` is an executable refusal even for an exact-spec-reviewed corpus.
This intake owner has no authenticated publication capability. The actual
publication/action owner must separately admit current explicit authority for
the exact candidate, destination and audience. Neither a pasted reviewer name,
a signed observation nor an exact-spec summary substitutes for that authority.
Prepared packets, candidate prose, review metadata and hashes remain local to
the source's disclosure/deletion boundary until that separate admission.

The email reduction scans maximal ASCII tokens once and conservatively removes
a whole token containing an address. This prevents quantified-prefix restart
amplification while retaining coverage for joined addresses. The byte/member
limits remain unchanged; no performance result grants disclosure authority.

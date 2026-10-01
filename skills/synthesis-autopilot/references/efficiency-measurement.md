# Measuring local owner overhead

Use `scripts/efficiency_profile.py` for an explicitly requested, read-only local
profile. Supply a bounded case object with `schema_version: 1`, `owner`
(`startup`, `resume`, `checkpoint`, or `review`), absolute current `project`,
`project_id`, `run_id`, and the existing native `actor`. The agent prepares the
case and a new retained scratch directory, invokes the owner, and summarizes
its report. It never launches a provider, native agent, local model or service.

The four measured boundaries are exact: PM current native/claim admission;
current run journal plus fresh owner/evidence inspection; the checkpoint's
read-only capsule calculation under active admission; and the deterministic
criterion report. This is not a timing claim for the entire UI session startup,
a full checkpoint publication, a paid independent review, or a native app.

Each run retains inputs, stdout, stderr, process-owner disposition, source
hashes and a report. Source hashes describe on-disk files for loaded modules at
probe completion, not an attestation of executable memory. It compares new Python interpreters with repeated calls
inside a single interpreter. Every repetition still admits current authority
and checks current bytes. OS filesystem caches are not flushed. The first
sample in the warm process includes its initial imports; later samples reveal
in-process reuse. Do not discard that first sample to inflate a speedup.

Reports include wall time, process CPU, peak traced Python allocation and
process-lifetime RSS high-water. RSS is not a per-operation delta. Provider
input/output/cached tokens, harness-wide tool totals and energy remain `null`
when not observed. Never substitute zero, a guessed tokenizer count or machine
power specifications for absent measurements.

A matching refusal is outcome equivalence, not operational readiness. Both
fields are shown. Source digests must also match across modes. Changed input,
revoked claims, corrupted evidence and unsupported capabilities require explicit
refusal/invalidation controls alongside current positive controls. Preserve all
results and unknowns. Record the experiment before choosing an optimization;
measure the changed implementation against the same outcome and guard checks.

The existing one-operation PM admission token is a useful deterministic
optimization: local observers can share that freshly issued token during the
operation, and it expires immediately afterward. It cannot be serialized or
replayed from native memory. A persistent cache of old authority would have a
different safety contract and is not an efficiency improvement.

Limits are 1–5 cold probes and 1–5 warm repetitions, up to 30 seconds per owned
process with the existing 1 MiB output bound. An interrupted/failed probe is
incomplete; retained diagnostic completeness may be unknown. Automatic retry,
model selection, new compute allowances and native-memory activation are absent.

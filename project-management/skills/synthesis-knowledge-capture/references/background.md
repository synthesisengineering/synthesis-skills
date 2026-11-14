# Knowledge capture: background

Release notes and the failure this skill exists to prevent. Read once, or when deciding whether a fact needs this workflow.

## Release notes

**Version 2.0.0** (2026-10-05) restructures the skill into the v5 format: binding
rules and contents first in SKILL.md, the rest moved verbatim into references/.
No rule changed; references/coverage-map.md maps every section.

**Version 1.2.0** (2026-09-01) ships `config.example.json` and connects the
private routing table to the guided onboarding interview. The example uses a
synthetic private workspace and a hold-for-approval push posture; the onboarding
validator refuses a domain without its repo, tier, or bundle path.

**Version 1.1.0** (2026-07-29)

(The paragraph that followed this line in 1.x, "A fact learned in a session and not
written to the durable knowledge base is a fact lost", now opens SKILL.md.)

## Why it exists

Most knowledge bases have a rule like *"update `source/` when you learn
something."* A rule is not a workflow, and a manual rule drifts. The failure has
three shapes, all real:

- **Evaporation.** The corrected fact lives only in the session transcript. The
  next session starts blind and repeats the old mistake.
- **Duplication.** A naive append adds a second, contradictory concept. Now the
  corpus asserts two things and a reader cannot tell which is current.
- **Destruction.** A blind overwrite deletes a framing that was still accurate
  on a different axis, replacing signal with a plausible error.

The canonical trigger: an agent learns a corrected fact about a person's role.
The corpus already holds several references to that person under a prior
framing. Evaporation loses the correction; duplication contradicts; a blind flip
destroys references that were right all along. The only safe path is: find every
existing mention first, decide in place, reconcile rather than flip, cite the
source. That path is this skill.

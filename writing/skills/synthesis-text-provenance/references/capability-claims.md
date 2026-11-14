# Capability Claims

Use this taxonomy for every provider, standards, detector, or runtime claim.

## Evidence classes

| Class | Meaning | Permitted claim |
|---|---|---|
| Deployed | Current primary documentation names the exact model/surface and says the feature is active | “Documented as deployed for X on DATE” |
| Documented roadmap | Provider says it intends or is rolling out the capability | “Planned or rolling out”; never “deployed” without exact support |
| Research | Paper, system card, or research post describes a method or experiment | “Researched”; never “present in production” |
| Authorized observation | A controlled account or API test returned a result with recorded settings | “Observed in this run”; never universal provider behavior |
| Third-party observation | A practitioner, editor, or researcher reports a behavior | “Reported by SOURCE”; not a provider fact |
| Unknown | No bounded source or test establishes the fact | “Unknown” or “not established by the sources reviewed” |

## Required claim dimensions

- exact provider and model label or ID;
- product surface or API endpoint class;
- region and account tier when exposed;
- observation or documentation date;
- source URL or immutable local evidence pointer;
- detector identity and version, if any;
- positive-result semantics;
- negative-result semantics;
- known editing, translation, truncation, or sampling limitations.

## Negative-result discipline

“Not detected” is not equivalent to “not present.” A negative result can mean
the signal is absent, the detector lacks access, the text is below a length
threshold, edits changed the signal, the wrong model/surface was tested, the
tool is outdated, or the feature is not documented for that surface.

Before reporting absence:

1. establish that the detector can return a known positive on the same surface;
2. record the detector's stated scope and minimum input requirements;
3. preserve the exact input hash and unedited text;
4. state the tested bounds rather than generalizing to authorship.

## Volatile capability matrix

Do not hard-code provider deployment status into this skill. Keep the current,
dated matrix in the owning synthesis project's evidence record, re-verify it
from primary sources, and update the skill only when a durable workflow rule
changes.

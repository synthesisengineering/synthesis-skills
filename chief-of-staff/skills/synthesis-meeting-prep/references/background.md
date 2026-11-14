# Meeting prep: release note and integration seams

Moved verbatim from the 1.3.0 SKILL.md. Read it when deciding which neighboring skill owns a step.

The 1.3.0 SKILL.md carried this first-release note under its title:

**Version 1.0.0** (2026-09-20): first release — the content contract
for meeting preparation (requirements R1–R12), the 64-factor
inventory, six structure variants, reader profiles, the debrief half,
and a mechanical prep linter (`scripts/prep_lint.py`).

## 4. Integration seams

- **Daily rituals** (`synthesis-daily-rituals` lead-time prep packs)
  own the scheduling machinery — which meetings need packs by when.
  This skill is the content contract that machinery drafts against.
- **Meeting transcripts** (`synthesis-meeting-transcripts`) own
  transcript fetch, naming, and the transcript-primary rule the
  debrief depends on.
- **OKF** (`synthesis-okf`) is the workspace knowledge interface
  for factor 37.
- **Console** renders packs filed under `meeting-preps/`; the basis
  statement is what makes them trustworthy there.

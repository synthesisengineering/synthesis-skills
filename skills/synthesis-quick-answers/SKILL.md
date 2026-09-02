---
name: synthesis-quick-answers
description: "Stand up and operate a low-cost, read-mostly companion session that answers ad hoc lookup questions about a workspace (people, teams, project status, releases, decisions) without pulling a focused project session off task or spending premium-model budget on quick lookups. Every answer carries a one-line grounding trailer — its source and a Verified/Cached/Uncertain confidence tier — so speed never gets mistaken for certainty, and a one-line routing entry in the workspace's own AGENTS.md/CLAUDE.md makes every future session apply it automatically, with no need to ask for it by name again. Bootstraps a missing personal knowledge workspace itself via synthesis-onboarding rather than inventing an ad hoc location. Use when asked to: set up an FAQ assistant, quick-answers session, lookup companion, ask-me-anything session, fast Q&A project, an ongoing session that already knows to use a skill; or when a question arrives that is a one-off lookup rather than the focused project's actual task. Not for: deep multi-session work, decisions, drafting, sending messages, or anything that should live in its own project — those graduate out."
license: "CC0-1.0"
depends_on:
  - synthesis-project-management
  - synthesis-context-lifecycle
  - synthesis-grounding-discipline
  - synthesis-concise-messaging
  - synthesis-model-tiers
  - synthesis-onboarding
metadata:
  author: "Rajiv Pant"
  version: "1.2.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Synthesis Quick Answers — Lookup Companion Pattern

## The Problem

Focused project sessions accumulate context on purpose — that's what makes them good at the work they're for. But not every question belongs there. "When is a colleague back from vacation" and "has a release shipped yet" are real, frequent, and usually urgent-feeling questions that have nothing to do with whatever a focused session is mid-task on. Answering them inline does two kinds of damage:

- **Context pollution.** The focused session's window fills with unrelated lookups, and its summarized history gets noisier every time it compacts.
- **Cost mismatch.** A one-line factual lookup doesn't need the reasoning depth or the model tier a hard architecture or strategy session runs at. Paying Max-effort-tier prices for "when is X back" is waste, repeated daily.

The fix is not "be disciplined about not asking." The questions are legitimate and often time-sensitive. The fix is a separate, cheap, low-ceremony surface built for exactly this shape of question — one that exists specifically so the *other* sessions can stay clean.

## The Pattern

A **quick-answers companion**: one `ongoing`-status project inside the user's own personal knowledge workspace (per `synthesis-project-management`, at `~/workspaces/{workspace}/ai-knowledge-{workspace}/` — the same location `synthesis-onboarding` scaffolds), used from a session on a routine-tier model, whose entire mandate is answering lookups by reading everything else in the workspace and writing almost nothing back.

It is deliberately **not** a "seat" in the operations sense (compare an `<org>-operations`-style project, which *owns* rituals, syncs, and triage). It owns no workflow. It is a read path across every other project, plus the workspace's knowledge base — and its value depends on staying that narrow. The moment it starts drafting, deciding, or sending, it has become a second copy of the work it exists to protect other sessions from absorbing.

**"Automatic" is a file, not a habit.** The entire reason this pattern is worth having — never needing to say "use the skill" — comes from one line in the workspace's own `AGENTS.md`/`CLAUDE.md`, read at the start of every session by convention. That line is Setup step 4 below, not an implementation detail; a companion without it is just this skill, invoked by hand, which is the exact daily friction the pattern exists to remove.

### Configuration

| Setting | Value | Description |
|---|---|---|
| `ai_knowledge_workspace` | `~/workspaces/{workspace}/ai-knowledge-{workspace}/` | Same location `synthesis-project-management` and `synthesis-onboarding` already use — never a substitute folder |
| `project_id` | `{workspace}-quick-answers` | e.g. `acme-quick-answers` — noun name, `ongoing` status, mirrors the workspace's own ops-seat naming |
| `faq_log` | `projects/{project_id}/resources/FAQ.md` | Append-only log of answered questions — see "The FAQ log" below |
| `model_tier` | `routine` (per `synthesis-model-tiers`) | Set by the user per client (`/model` in Claude Code, the equivalent in Codex) — an agent cannot switch its own model, so state the recommendation and wait rather than attempting it |

### Setup

This pattern needs a personal knowledge workspace — the same `ai-knowledge-{workspace}` repo `synthesis-project-management` and `synthesis-onboarding` already use, at `~/workspaces/{workspace}/ai-knowledge-{workspace}/`. Don't invent a substitute location (a loose folder somewhere else, a name that doesn't match): a companion that lives outside the convention every other project already follows is a second, incompatible system, not a lighter version of the same one.

1. **No personal knowledge workspace yet?** Create one first: `onboard.py init-workspace --workspace {name}` (part of `synthesis-onboarding`, already installed alongside this skill). It scaffolds `~/workspaces/{name}/ai-knowledge-{name}/` — `AGENTS.md`, `CLAUDE.md`, a seeded `projects/index.yaml`, and a local git repo (a remote is optional; purely local is fine to start). Skip this step if one already exists — check for `~/workspaces/{name}/ai-knowledge-{name}/` first. Don't confuse this with a shared organization workspace the user may already have (e.g. `~/workspaces/{org}/` holding cloned team repos) — that is a sibling directory, not the same thing, and this pattern's project files belong in the personal one.
2. Create the project the normal way (`synthesis-project-management`): `status: ongoing`, `bounded: false`, noun-first id (e.g. `{workspace}-quick-answers`). Give it a thin `CONTEXT.md` and, if the workspace has enough standing routing knowledge to be worth writing down (which sources answer which question shapes), a short `REFERENCE.md`.
3. Register it in `projects/index.yaml` under its own initiative if the workspace doesn't already have a natural home for "standing non-ops infrastructure" — don't force it under an operations initiative that implies it owns rituals.
4. **Point the workspace's own `AGENTS.md`/`CLAUDE.md` at it** — one routing line, exactly the way any other standing project already gets referenced there. This one line is the entire mechanism that makes the pattern actually automatic: a client reads that file at the start of every session, so from here on the user never has to say "use the skill" again. Skipping this step is the single most common way this pattern fails to live up to its own pitch — a companion that still needs to be invoked by name every time isn't a quick-answers companion, it's an ordinary skill with extra ceremony.
5. Tell the user which model tier to select for the session (see Configuration), and that this is a one-time-per-session setting they make, not something this skill can do for them.
6. Seed `resources/FAQ.md` with a header; leave it empty otherwise. It fills from use.

## Operating Protocol

Run this per question, every time — it's the whole point of the pattern:

1. **Classify before searching.** What kind of fact is this?
   - A person's status/availability/role → team directory, calendar, recent Slack/chat, the KB's people/org docs.
   - A team's charter/roster/current work → the KB's org docs, that team's tracked projects.
   - A project's status/history/decision → *that project's own* `index.yaml` entry and `CONTEXT.md`/`REFERENCE.md` — not a full re-read of its session history.
   - A release/ship fact → git tags, changelog, release notes, deploy records — not the KB's prose summary of it.
   Then query only the source(s) that answer that shape of question. Loading another project's entire context to answer one fact defeats the purpose of a *cheap* companion.

2. **Verify anything volatile before asserting it.** This is not optional politeness — it is the pattern's entire value proposition. A quick-answers session that confidently repeats a stale cached fact is worse than no session at all, because it's trusted precisely because it's fast. Follow `synthesis-grounding-discipline`'s cache-vs-truth rule: CONTEXT/REFERENCE files and prior session summaries are caches, not truth; run the verifying command for anything that could have changed (a person's schedule, a project's status, whether something shipped, a date). This workspace-management pattern exists because a stale "is being refreshed and moved to" sentence sat in a cache for two months before an agent repeated it as current — the exact failure mode this skill's speed advantage would otherwise make more likely, not less. This step's outcome — verified live, or only found in a cache — is what step 3's trailer reports; there is no separate step where confidence gets guessed after the fact.

3. **Answer tersely, and carry a grounding trailer on every answer, without exception.** Per `synthesis-concise-messaging`: the fact first, one sentence of context only if genuinely load-bearing, then one closing line naming the source and a confidence tier from `synthesis-grounding-discipline`'s vocabulary:

   | Tier | Means | Trailer example |
   |---|---|---|
   | **Verified** | Confirmed via a live verifying command / tool call this turn — file re-read, live query, `git log`, an API or calendar read | `Source: git tag -l 'v0.11*' (verified live) — Confidence: Verified` |
   | **Cached** | Read from a context file, KB doc, or prior session log without re-verifying live — name the cache's own as-of/last-updated date when it carries one | `Source: csa-2026-q3/CONTEXT.md, as of 2026-08-31, not re-verified this session — Confidence: Cached` |
   | **Uncertain** | No direct source found; this is inference or a best guess, not an observed fact | `Confidence: Uncertain — no source found; try <person/team/doc>` |

   A trailer is one line, not a paragraph — it names what was checked, nothing more. Never omit it: a fast answer with no stated confidence is indistinguishable from a guess, which defeats the entire pattern. **Cached is not a downgrade to apologize for** — plenty of quick answers are legitimately answered from a stable reference and that's fine to say plainly. What's not fine is a volatile fact (step 2's list: schedules, status, ship state, dates) answered as Cached when it should have been verified — that is a defect, not a shortcut: go verify, or say "Uncertain" and stop.

4. **Log it.** Append one line to `resources/FAQ.md`: date, question, the answer as given, the source(s) checked, and the confidence tier. This is a side effect, not extra work — it turns repeat-question friction into a growing, skimmable artifact, and it's what actually earns the name "FAQ" over time. Don't log ephemeral asks that will be false by tomorrow (exact meeting times, in-flight numbers) unless the pattern of asking is itself worth recording.

5. **Route durable facts onward, don't hoard them here.** If an answer surfaces something that belongs in the workspace's knowledge base (a role change, a team's charter, a standing fact about a product), that goes through the workspace's normal `synthesis-knowledge-capture` path — not into this project's own files as a second copy. This project's writes stay limited to its own `CONTEXT.md`/`FAQ.md` and, when the user says so, a KB capture.

## Scope Boundary — What This Is Not For

Keep the mandate narrow on purpose:

- No decisions, no drafting, no sending messages, no calendar changes, no autopilot delegation. Every one of those belongs in a session with the corresponding skill loaded and the corresponding scrutiny applied.
- If a question turns out to need real investigation — multiple sessions, a plan, a deliverable — say so and hand it to its own project rather than absorbing the work here. The companion's job is triage-speed answers, not the work the answer points toward.
- Don't let this become a second inbox. It answers what's asked; it doesn't proactively surface items (that's `synthesis-chief-of-staff` territory) or own any cadence (that's an operations seat's job).

## Relationship to Other Skills

- **`synthesis-project-management`** supplies the project itself (index entry, tiered `CONTEXT.md`/`REFERENCE.md`, cross-agent handoff so the same project works from Claude Code and Codex identically).
- **`synthesis-context-lifecycle`** governs the tiered-memory mechanics once the project exists.
- **`synthesis-grounding-discipline`** is why step 2 of the protocol is not skippable, and its cache-vs-truth vocabulary (verified vs. cached, name the layer) is exactly what step 3's confidence trailer reuses rather than inventing a parallel scheme.
- **`synthesis-concise-messaging`** shapes the answer format.
- **`synthesis-model-tiers`** supplies the `routine` tier recommendation and the vocabulary for stating it without attempting to switch it.
- **`synthesis-knowledge-capture`** is where durable facts actually get saved, not this skill.
- **`synthesis-onboarding`** is what Setup step 1 calls when the user has no personal knowledge workspace yet (`onboard.py init-workspace`) — this skill never scaffolds a substitute of its own.

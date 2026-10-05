# Quick answers: the operating protocol

The five steps run on every question, in order.

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

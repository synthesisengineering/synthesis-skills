# The Instruction-Kernel Pattern

How to keep an always-loaded instruction file small, enforceable, and within
budget by re-homing everything that does not need to be always-on — without
weakening a single rule.

## Contents

1. The problem
2. What the kernel is
3. The four enforcement classes
4. The not-weakening proof obligation
5. The budget gate
6. Migration mechanics

## 1. The problem

User-level instruction files (`CLAUDE.md`, `AGENTS.md`, generated from one
canonical source) grow monotonically: every incident adds a rule and no rule
ever leaves. Every byte is paid in every session's context window, which is why
such files carry a byte budget — and why a file at 99% of budget with no
headroom is a systemic hazard, not a formatting problem.

Two responses fail:

- **Raising the budget** defeats its purpose. The budget exists to protect
  per-session context.
- **Trimming rules' binding force** weakens the system the rules exist to
  protect.

The escape is architectural. Most instruction bytes are teaching material —
rationale, worked examples, incident narratives — that has (or deserves) a
canonical home in a skill, hook, or configuration file. The kernel keeps only
what must be always-on; everything else is loaded when its situation arises,
enforced mechanically, or read on demand.

## 2. What the kernel is

Exactly three things:

1. **Identity plus always-on invariants** — compressed operative rules, one to
   four lines each, with pointers to the canonical home that carries the
   narrative and rationale. The kernel keeps the rule text that binds, not the
   story of why it binds.
2. **The routing table** — task-shape → skill-stack triggers. This is the one
   part that must be always-loaded, because it is what makes situational
   loading reliable: a skill that would have prevented a failure is worthless
   if nothing triggers loading it.
3. **Enforcement declarations** — one-liners naming which fail-closed hooks
   mechanically enforce which rules ("X is enforced by hook Y; never bypass").
   Where such a hook exists and is verified, prose only needs to declare it.

Everything else — worked examples, incident vignettes, procedure detail,
reference tables, build commands — lives outside the kernel in the home that
canonically owns it.

## 3. The four enforcement classes

Every rule that leaves or stays in the kernel lands in exactly one class:

- **A — kernel-resident invariant.** Stays in the kernel as a compressed
  operative rule. For rules with no situational trigger: per-response conduct,
  destructive-operation guards, and gates that must hold precisely in the
  sessions least likely to load a skill (a deferral gate fires in sessions
  drifting toward deferral — the sessions least inclined to load the
  anti-deferral skill).
- **B — skill-resident plus routing-table trigger.** The substance lives in a
  skill; the kernel keeps the trigger row, plus a one-line invariant where the
  rule is also always-on.
- **C — hook-enforced (fail-closed) plus kernel one-liner.** A wired hook
  enforces or backstops the rule; the kernel declares it. The hook must fail
  closed: a guard that cannot run must block loudly, never pass with a
  warning.
- **D — configuration or reference file.** Loaded on demand; the kernel keeps
  at most a pointer.

## 4. The not-weakening proof obligation

Migration is only safe if it is provably non-weakening. For every byte leaving
the kernel:

- **Name the landing place and the enforcement class.** An unclassified rule is
  an orphaned rule.
- **Class-B rules require a routing-table trigger** present in the kernel and
  verified to fire on the task shapes the rule governs. Substance in a skill
  nothing loads is substance removed.
- **Class-C rules require a passing hook doctor** on every client before any
  rule relies on the hook. An unverified hook is not enforcement; the
  fail-closed philosophy applies to the migration itself.
- **Class-A invariants remain in the kernel**, compressed but operative.

Some rules keep a class-A remnant even when a skill or hook home exists,
because their failure mode is precisely "the enforcement did not engage":
session-scoped gates with no mechanical trigger, per-response formatting rules
no hook covers, and never-send rules whose hook matcher enumerates today's
tools but not tomorrow's. Migrating those without a kernel remnant would
weaken them; the matrix must say so explicitly.

The migration matrix (section 6) is the audit artifact for all of this: every
rule accounted for, no orphan, each weakening risk named and resolved.

## 5. The budget gate

The byte budget is the mechanism that keeps the kernel a kernel, and it must
itself fail closed:

- **Hard limit.** The generator or installer refuses to install a kernel over
  budget. Refusal, not warning.
- **Warn band.** A soft threshold (for example 85% of the hard limit),
  surfaced in doctor and install output, so the approach to the limit is
  visible long before it binds. A gate with only a hard limit reports 99% full
  with zero signal — the warn band is what turns the budget into an early
  indicator instead of a cliff.
- **Every write path validates.** Any mechanism that can make the kernel live
  — the installer and any edit-propagation hook alike — must run the same
  validation. Two enforcement layers that disagree let an over-budget kernel
  go live through the unvalidated path while the validated one correctly
  refuses the identical content.
- **Structural headroom.** Post-migration, target a kernel size well under the
  hard limit so growth headroom is a property of the architecture, not an
  accident of the last trim.

## 6. Migration mechanics

Order is the safety property:

1. **Build the homes first.** Create or extend the skill sections, hooks, and
   reference files; move content in verbatim-or-better. Delete nothing from
   the kernel yet. The system runs briefly with duplicates, which is safe;
   running with orphans is not.
2. **Write the migration matrix.** A per-rule audit artifact: rule → target
   home → enforcement class → verification that the home actually carries the
   substance. Verify by opening the named file, not from memory — home-exists
   claims carried from a plan or from recollection are reliably wrong
   somewhere, and each wrong one is a rule silently dropped.
3. **Verify enforcement.** New and changed hooks land with doctors passing on
   every client. Never infer one client's health from another's.
4. **Rewrite the kernel last.** The three-part kernel lands only after homes
   exist and enforcement is verified. Install, confirm the budget with
   headroom, run doctors and conformance on every client, and spot-test a
   sample of routing triggers and hooks live.
5. **Archive the old kernel.** Git history plus an archived copy, so the
   matrix can always be audited against the original text.

The instruction-budget and catalog checks in this skill's `conformance.py` are
the mechanical layer for steps 3–4: `instruction-budget` enforces the gate,
`catalog` verifies the skill homes are visible to each client, and `hook-live`
proves the enforcement declarations true.

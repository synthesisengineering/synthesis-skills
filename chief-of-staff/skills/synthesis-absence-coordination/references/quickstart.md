# Quickstart — adopt in fifteen minutes

You do not need the whole system on day one. This sequence gets a working, safe
configuration in one sitting, and each later step is optional.

## Minute 0–5: copy and personalize

```bash
mkdir -p ~/.synthesis/absence-coordination
cp <skill-dir>/example-config.yaml ~/.synthesis/absence-coordination/config.yaml
```

Open the config and replace, in this order of importance:

1. **`principal`** — your name, home time zone, and (if you use TripIt or similar) the
   address *verified on that account*. If you are not sure which address is verified,
   check the service's settings now — a wrong value here fails silently later.
2. **`recipient_tiers` → `principals` and `exec_assistants`** — your manager and their
   assistant are the minimum viable configuration. Everything else can wait.
3. Delete or empty any tier you do not have. An empty tier is fine; a guessed address
   is not.

## Minute 5–7: validate

```bash
python3 <skill-dir>/validate_config.py
```

Fix defects (exit 1) now — each failure message says what and why. Warnings can wait,
with one exception: if it warns that an address looks like a distribution alias, fix
that today. Alias breakage is silent and you will not get a second warning.

## Minute 7–12: dry-run an absence

Ask your agent:

> Using synthesis-absence-coordination, plan a vacation <dates> — draft everything,
> send nothing.

You should get: a conflict report across your calendars, the recurring-meeting
decision list, and per-tier drafts. Read the principals draft carefully — it is the one
you will send personally, and its tone is yours to correct now, once, rather than per
absence.

## Minute 12–15: pilot on the forgiving tiers

**Do not point this at your workplace first.** Run your first real absence with the
low-stakes tiers only — `personal_continuity` and `family` — and let the work tiers stay
draft-only for one cycle. A misworded note to your trainer costs nothing; the same
mistake to your CEO is why you are configuring carefully. Promote tiers to
agent-send only after you have read a few cycles of what the agent drafts.

## Later, when each becomes worth it

- **Coverage source** — wire `coverage.source: external` to whatever holds your org
  context, so delegation statements are real rather than improvised.
- **Shared team calendars** — fill in `calendars.shared` URLs as you learn them.
- **`notify_on_commit`** — once trusted, this is the feature that prevents conflicts:
  the people who protect calendars hear the moment a plan is real.
- **The quiet type** — read its section in SKILL.md before you need it, not during the
  week you need it.

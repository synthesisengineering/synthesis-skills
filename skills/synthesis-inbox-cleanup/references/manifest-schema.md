# Manifest schema

The YAML schema for `~/.synthesis/inbox-cleanup/rules.yaml`. This file is per-user and never enters version control.

## Top-level shape

```yaml
class_defaults:
  promo: trash
  newsletter: newsletter
  notification: archive

never_touch:
  domains:
    - bank.example.com
  addresses:
    - payroll@example.com

friends_protect:
  - match: {address: friend@example.com}

subject_rules:
  - if: {domain: shop.example, subject_contains: "shipped"}
    disposition: archive

senders:
  - match: {address: deals@example.com}
    class: promo
  - match: {domain: bigretailer.com}
    class: promo
  - match: {name: "marketing"}
    class: promo
```

## Sections

### `class_defaults`

Maps a class name (free-form, user-defined) to a default disposition (`keep | archive | newsletter | trash`). A sender rule with `class: promo` and no explicit `disposition:` inherits its disposition from this map.

Conventional classes:

| Class | Conventional disposition |
|---|---|
| `promo` | `trash` |
| `newsletter` | `newsletter` |
| `notification` | `archive` |
| `transactional` | `keep` |
| `social` | `archive` or `newsletter` |

You can add your own classes (e.g., `personal_finance` → `archive`).

### `never_touch`

The strongest rule. Any message matching here resolves to `keep` and skips all subsequent rules — including subject_rules and sender rules.

```yaml
never_touch:
  domains:
    - chase.com           # banking
    - kaiserpermanente.org # healthcare
    - justworks.com       # payroll
  addresses:
    - mom@example.com
    - boss@example.com
```

**This list is the load-bearing safety net.** Banks, payroll, healthcare, current employer, government, family — all belong here. The rules engine treats `never_touch` as inviolable; no LLM-callable path can modify it (see `prompt-injection-defenses.md`).

Domain matching is exact OR subdomain (`chase.com` matches `chase.com` and `alerts.chase.com`).

### `friends_protect`

Friends and personal contacts. Treated as `keep` by the resolver. Distinct from `never_touch` semantically (these are humans, not institutions) but the effect is the same.

```yaml
friends_protect:
  - match: {address: friend@example.com}
  - match: {domain: family-domain.example}
```

### `subject_rules`

Conditional rules that depend on both sender and subject. Useful when one sender is mixed (legitimate transactional + promo) and only the promo subjects should be moved.

```yaml
subject_rules:
  - if: {domain: bigretailer.com, subject_contains: "% off"}
    disposition: trash
  - if: {domain: airline.example, subject_contains: "shipped"}
    disposition: archive
```

`subject_contains` matches case-insensitively against any substring.

### `senders`

The main rules table. Each entry has a `match` block and either a `class` (which looks up the disposition via `class_defaults`) or an explicit `disposition`.

Match criteria, in resolution order (most specific wins):

1. `address` — exact lowercased email address match
2. `domain` — exact-or-subdomain match
3. `name` — case-insensitive substring match against the From display name (used when senders rotate domains but keep the display name)

```yaml
senders:
  # Address-specific (highest precedence)
  - match: {address: deals@store.example}
    class: promo

  # Domain (catches everything from the domain)
  - match: {domain: marketing.example.com}
    class: promo

  # Display-name fallback (use sparingly — name spoofing is easy)
  - match: {name: "Acme Marketing"}
    class: promo
```

A sender entry can use `disposition` directly instead of `class`:

```yaml
senders:
  - match: {domain: noisy.example}
    disposition: trash    # overrides any class_defaults mapping
```

## Resolution precedence

For each message, the resolver walks rules in this order and returns the first match:

1. `never_touch.addresses` (exact match)
2. `never_touch.domains` (exact-or-subdomain match)
3. `subject_rules` (domain match + subject substring)
4. `senders` with `address` match
5. `senders` with `domain` match
6. `senders` with `name` match
7. Default: `keep` with reason `unmatched`

Unmatched senders stay in the inbox. They appear in `icloud_tail.py` output as the work-queue.

## Validation

The resolver is in `scripts/_lib.py`. It does NOT validate the YAML against a strict schema at startup — invalid structure produces runtime KeyErrors. For v1 this is acceptable (you're the only user of your own manifest). A future enhancement would add a `validate` script.

## Migration from monolithic rule lists

If you've been managing email rules as a flat list of "block these senders" without categorization, the migration is:

1. Group your existing entries by class (promo / newsletter / notification / etc.)
2. Set `class_defaults` for each class
3. Move "never trash this" entries to `never_touch`
4. Use `senders` for the rest
5. Use `subject_rules` only when a single sender is genuinely mixed

The starting `templates/rules.example.yaml` is empty enough to begin from scratch, populated enough to show the shape.

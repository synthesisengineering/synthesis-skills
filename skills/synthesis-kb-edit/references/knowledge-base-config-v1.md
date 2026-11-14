# Knowledge-base configuration contract v1

`.agents/knowledge-base.yaml` is the repository-local policy consumed by
`synthesis-kb-edit`, `synthesis-okf`, and `synthesis-knowledge-capture`. Skills
contain the reusable workflow; this file contains repository-specific facts.

## Schema

```yaml
bundle_path: "source"
git_host: "github"             # github | bitbucket
default_branch: "main"
branch_prefix: "kb/"
ship: "pr"                     # pr | direct

review:
  who_merges: "A repository maintainer other than the editor"
  default_reviewers: []
  setup_guide: "docs/review-setup.md"  # relative path or null

editable:
  - "source/**"
refuse:
  - "compiled/**"
  - ".agents/**"
generated_artifacts:
  - "compiled/**"
  - "all-knowledge.md"

topic_routing:
  "shared instructions": "source/instructions/"
  "operational context": "source/contexts/"
  "current facts": "source/datasets/active/"
  "stable reference": "source/datasets/reference/"
  "procedure": "source/runbooks/"

taxonomy_path: "source/taxonomy.md"     # relative path or null

frontmatter:
  required:
    - "type"
  house:
    - "title"
    - "description"
    - "tags"
    - "owner"
    - "timestamp"
    - "status"
    - "resource"
  date_field: "timestamp"
  reserved_files:
    - "index.md"
    - "log.md"

confidentiality:
  forbidden_words_source: ".githooks/pre-commit"  # relative path or null
  hook_path: ".githooks"                          # relative path or null
  visible_to: "People with repository access"
  sharing_policy: ".agents/sharing-policy.md"     # relative path or null
  backstop_phrases:                               # the organization's own; one at least when a policy is named
    - "zephyr ledger"

notes: >
  Repository-specific rules that do not fit a structured field.
```

## Field rules

| Field | Rule |
|---|---|
| `bundle_path` | Non-empty path relative to the repository root. |
| `git_host` | `github` or `bitbucket`; selects host mechanics. |
| `default_branch` | Canonical published branch. |
| `branch_prefix` | Prefix for edit branches when `ship: pr`. |
| `ship` | `pr` opens review and never merges; `direct` follows repository push policy. |
| `review` | Declares who publishes, default reviewers, and an optional setup guide. |
| `editable` | Complete allowlist of paths the editor may change. |
| `refuse` | Paths the editor must not change. Refusal wins over editability. |
| `generated_artifacts` | Machine-produced paths. Generated wins over every other classification. |
| `topic_routing` | Human topic to repository-relative directory mapping. |
| `taxonomy_path` | Optional vocabulary/schema document read before formatting. |
| `frontmatter.required` | Required fields; must contain `type` for OKF. |
| `frontmatter.house` | Allowed house fields in addition to required fields. |
| `frontmatter.date_field` | The single last-meaningful-update field; it must appear in required or house. |
| `frontmatter.reserved_files` | Must contain OKF's `index.md` and `log.md`. |
| `confidentiality.forbidden_words_source` | Optional scanner/pattern source read at runtime. |
| `confidentiality.hook_path` | Optional configured Git hook directory. |
| `confidentiality.visible_to` | Plain-language audience used in editor explanations. |
| `confidentiality.sharing_policy` | Optional path of the repository's sharing policy (`references/sharing-standard.md`), made from `assets/sharing-policy.template.md` and named by `adopt-sharing-policy`; when set, the file must exist and every edit runs the phrase scan. |
| `confidentiality.backstop_phrases` | The organization's own phrases for the phrase scan; the plugin ships none. Required, with at least one phrase, when `sharing_policy` is set: a contract that names a policy with none holds every edit, and the error says to list one or remove the policy. |
| `notes` | Free text for remaining repository-specific policy. |

All configured paths are repository-relative, may not contain `..`, and may
not escape through symlinks when path checks are enabled.

The schema names every key. A key it does not name, at the top level or inside
`review`, `frontmatter` or `confidentiality`, makes the contract invalid: a
misspelled optional key would otherwise switch off what it configures, in
silence. Put repository-specific policy that has no key in `notes`.

## Classification precedence

For a repository-relative path:

1. `generated_artifacts` → `generated`
2. `refuse` → `refused`
3. `editable` → `editable`
4. no match → `outside`

This precedence prevents a broad editable glob from authorizing a generated or
explicitly refused descendant.

## Validation

```bash
# Schema only
python3 <skill-root>/scripts/kb_config.py <repo-root>

# Schema plus configured path and containment checks
python3 <skill-root>/scripts/kb_config.py <repo-root> --check-paths

# Mechanical path classification
python3 <skill-root>/scripts/kb_config.py <repo-root> \
  --resolve source/datasets/reference/example.md
```

Exit status is `0` when valid, `1` for an invalid contract, and `2` for usage
or loading failures.

Adopting the sharing standard names the policy in the contract together with
the organization's own phrases, and writes the policy's template where the
contract says unless a file is there (`sharing-standard.md`, "Adopting the
standard"). It exits `0` when the contract names the policy, `1` when it wrote
nothing (no phrases given or listed, or a contract it cannot change safely),
and `2` for usage or loading failures:

```bash
python3 <skill-root>/scripts/kb_config.py adopt-sharing-policy <repo-root> --phrase "zephyr ledger"
```

When the contract names a sharing policy, the phrase scan reads it and the
phrases; its commands, output and exit status are in
[`sharing-standard.md`](sharing-standard.md), "The phrase scan":

```bash
python3 <skill-root>/scripts/sharing_scan.py <repo-root> --range origin/main...HEAD
```

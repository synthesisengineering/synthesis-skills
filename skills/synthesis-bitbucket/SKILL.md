---
name: synthesis-bitbucket
description: "Work with Bitbucket Cloud via the open-source bkt CLI: PR lifecycle, repo and branch reads, and the bkt api escape hatch, with explicit repository binding and write-safety rules. Use when asked to: bitbucket, bkt, bitbucket pr, open bitbucket pr, review bitbucket pr, bitbucket cli, bitbucket api."
license: "Apache-2.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "2.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
  format: v5
---

# Synthesis Bitbucket (via `bkt`)

How an agent interacts with Bitbucket Cloud using [`bkt`](https://github.com/avivsinai/bitbucket-cli), an open-source community CLI that fills the role `gh` plays for GitHub. This skill exists because agents working across many repos otherwise drift to raw REST calls or the wrong CLI, reassembling auth, URL-encoding, and pagination by hand — differently every session.

**The rule in one line: if `bkt` can do it, use `bkt`.** The REST API is the escape hatch (`bkt api`), not the default.

Teams layer a private companion skill on top of this one carrying their workspace names, default context, and release conventions. This skill stays generic.

## Binding rules

Rules 1 to 3 are the 1.2.2 safety rules, numbered as before.

1. **Reads are free; writes are deliberate.** Never `approve`, `merge`, `decline`, or `create` without the operator's explicit intent for that specific PR.
2. **One command surface.** Do not mix `bkt`, raw `curl`, and git-host web UIs in one workflow — state drifts and auth surfaces multiply.
3. **Repo-level skills do not travel.** A skill checked into one repo is not loaded when the session works elsewhere. Install this skill (and your team's companion) at the personal/agent level so the command surface is present in every session.
4. **Bind every repository call with one literal `--repo <slug>`** (`api` takes its canonical literal path instead). Never use a mutable active context as repository evidence, even for reads or loops.
5. **A parsed binding identifies a target only.** It grants no send, review, merge or publication authority.
6. **`bkt pipeline run` can deploy.** Verify its effects and the applicable deployment authorization first.
7. **Pin a reviewed `bkt` version** and re-review the diff before upgrading: it is a community tool with write access to your repos.
8. **Git uses SSH keys; `bkt` uses the token.** A REST token does not necessarily authenticate git HTTPS, and the context host must match `bkt auth status` exactly.

## Contents

- [references/setup.md](references/setup.md): install and pin, authenticate (OAuth or a scoped API token), configure a connection context, and the context-host gotcha. Read it when `bkt` is not yet installed or authenticated, or when a call fails with "host not found".
- [references/pr-queue.md](references/pr-queue.md): how `scripts/pr_queue.py` builds the daily-rituals PR queue and when it reports `unscanned`. Read it when working on or interpreting the PR-queue scan.
- [references/coverage-map.md](references/coverage-map.md): where each part of the 1.2.2 text now lives.
- Explicit repository binding, Command catalog, the `gh` → `bkt` map, When NOT to apply: below.

## Explicit repository binding

Every supported repository read or write must carry one literal `--repo <slug>`.
Supply `--workspace <workspace>` for Cloud or `--project <key>` for Data Center
when selecting that namespace. Never use a mutable active context as repository
evidence, including for read-only calls, aliases such as `pr ls`, or repeated calls
in a loop. `bkt pr list --mine` also needs the intended repository when running
under this repository-scoped policy. Enumerate the authorized repository inventory
for a portfolio read instead of silently broadening its coverage.

Authentication, connection-context management, help/version and `api /user` GET
are non-repository operations. The actual `api` command does not support `--repo`:
use its canonical literal `/repositories/<workspace>/<repo>/...` or Data Center
`/rest/api/1.0/projects/<key>/repos/<repo>/...` path. An unresolved, redirected or
traversing path is not a binding. Never add an unsupported flag to manufacture one.

`scripts/repository_binding.py` validates the declared CLI grammar without calling
the provider or reading global context. The private shared pre-tool owner calls
this verified public module through its Codex and Claude pre-tool adapters; unknown syntax refuses with
a diagnostic. A client without an enrolled native pre-tool adapter has skill guidance, not demonstrated mechanical enforcement. Verify adapter capability and native acceptance before claiming parity. The parser result identifies a target only: it grants no send,
review, merge or publication authority. Refresh its grammar from the reviewed
CLI's own help when adopting another CLI version, and retain refusal controls.

## Command catalog

Global flags on any command: `--json` · `--yaml` · `--template '<Go template>'` · `--jq '<expr>'` (with `--json`) · `--format json|yaml` · `-c <context>`. Context overrides: `--workspace`, `--repo`.

### Read (safe, use freely)

- `bkt pr list --repo <repo>` — `--state OPEN|MERGED|DECLINED` · `--limit <n>` (0 = all) · `--mine`
- `bkt pr view <id> --repo <repo>` · `bkt pr diff <id> [--stat] --repo <repo>` · `bkt pr comments <id> [--state unresolved] --repo <repo>` · `bkt pr checks <id> [--wait] --repo <repo>`
- `bkt repo view --repo <repo>` · `bkt branch list --repo <repo>` · `bkt pipeline list|view --repo <repo>`

### Write (consequential — confirm intent before running)

- `bkt pr create --title <t> --description <d> --source <branch> --target <branch> [--reviewer <user|{UUID}>]… [--with-default-reviewers] [--draft] --repo <repo>`
- `bkt pr comment <id> --text <msg> [--parent <comment-id>] [--file <path> --to-line <n>] --repo <repo>`
- `bkt pr edit <id> --repo <repo>` · `bkt pr approve <id> --repo <repo>` · `bkt pr merge <id> [--strategy <server-supported-id>] --repo <repo>` · `bkt pr decline <id> --repo <repo>` · `bkt pr reopen <id> --repo <repo>`

- `bkt pipeline run --repo <repo> --ref <branch|tag|commit>` — starts a pipeline and can deploy; verify its effects and applicable deployment authorization first.

Merge strategy IDs depend on the server and repository. The CLI accepts a string; its help uses `rebase_fast_forward` as an example, not a universal supported-value list.

### Escape hatch

- `bkt api /repositories/<ws>/<repo>/...` — raw REST with auth handled. Use only for surfaces the catalog lacks; prefer adding a note to your team's companion skill when a gap becomes routine.

## `gh` → `bkt` map

| gh | bkt |
|---|---|
| `gh pr list` | `bkt pr list --repo <repo>` |
| `gh pr view N` | `bkt pr view N --repo <repo>` |
| `gh pr diff N` | `bkt pr diff N --repo <repo>` |
| `gh pr create` | `bkt pr create --repo <repo>` |
| `gh pr review --approve` | `bkt pr approve N --repo <repo>` |
| `gh pr merge N` | `bkt pr merge N --repo <repo>` |
| `gh pr comment N -b …` | `bkt pr comment N --text … --repo <repo>` |
| `gh api …` | `bkt api …` |

Bitbucket Cloud has **no PR labels** and its PR states are `OPEN`, `MERGED`, `DECLINED`, `SUPERSEDED` — port `gh` habits accordingly.

## When NOT to apply

- GitHub or GitLab repos (`gh` / `glab` are the right tools there)
- Bitbucket Data Center quirks beyond `bkt`'s support — check the project's README first

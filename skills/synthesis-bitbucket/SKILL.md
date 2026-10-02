---
name: synthesis-bitbucket
description: "Work with Bitbucket Cloud repos through the open-source bkt CLI — PR lifecycle (list, view, diff, comment, approve, merge), repo/branch reads, and the bkt api escape hatch. Encodes auth setup, the context-host gotcha, a gh-to-bkt command map, and write-safety rules so agents use one consistent command surface instead of reinventing REST calls. Use when asked to: bitbucket, bkt, bitbucket pr, open bitbucket pr, review bitbucket pr, bitbucket cli, bitbucket api."
license: "Apache-2.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.2.2"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Synthesis Bitbucket (via `bkt`)

How an agent interacts with Bitbucket Cloud using [`bkt`](https://github.com/avivsinai/bitbucket-cli), an open-source community CLI that fills the role `gh` plays for GitHub. This skill exists because agents working across many repos otherwise drift to raw REST calls or the wrong CLI, reassembling auth, URL-encoding, and pagination by hand — differently every session.

**The rule in one line: if `bkt` can do it, use `bkt`.** The REST API is the escape hatch (`bkt api`), not the default.

Teams layer a private companion skill on top of this one carrying their workspace names, default context, and release conventions. This skill stays generic.

## Install and pin

```bash
brew install avivsinai/tap/bitbucket-cli
brew pin bitbucket-cli   # freeze at the installed version
bkt --version
```

**Pin a reviewed version.** `bkt` is a community tool with write access to your repos. Review a release (or adopt your team's reviewed version), pin it, and re-review the diff before upgrading. `brew pin` freezes whatever is installed; a checksummed release binary from the project's GitHub Releases page is the alternative when you need an exact older version.

## Authenticate

**Preferred — OAuth in the browser** (no token handling):

```bash
bkt auth login https://bitbucket.org --kind cloud --web
```

**Alternative — scoped API token** created under the *Bitbucket* application at `id.atlassian.com → Security → API tokens`:

```bash
bkt auth login https://bitbucket.org --kind cloud \
  --username <atlassian-account-email> --token <api-token>
```

The username is the **email of the Atlassian account that owns the token** — not a Bitbucket username. Prefer the interactive prompt over `--token` (flags leak into shell history and process listings). Credentials land in the OS keychain.

⚠️ **Scoped API tokens that authenticate the REST API do not necessarily authenticate the git HTTPS endpoint** — they are separate credential surfaces. For `git push`/`fetch`, use SSH keys; keep `bkt` on the token. Mixing the two surfaces produces "the token works here but not there" mysteries that look like access problems and are not.

## Configure connection context and bind each repository

```bash
bkt context create <name> --host https://api.bitbucket.org/2.0 \
  --workspace <workspace> --repo <repo>
bkt context use <name>
```

**Gotcha:** `bkt context create` requires `--host`, and the host string must exactly match the one shown by `bkt auth status` (for Cloud: `https://api.bitbucket.org/2.0`, not `https://bitbucket.org`). A mismatched host fails with "host not found; run bkt auth login first" even when you are logged in.

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

## PR queue

`scripts/pr_queue.py` is the Bitbucket half of the daily-rituals PR-queue scan (`synthesis-daily-rituals/scripts/pr_queue_scan.py`), which dispatches each declared repo by origin host and loads this helper by path.

- `list_open_prs(workspace, repo_slug)` uses the explicitly bound `bkt api /repositories/<workspace>/<slug>/pullrequests` GET with reviewer fields requested. It classifies a complete inventory as awaiting your review, your own open PRs, or open PRs nobody was asked to review. The ordinary PR-list response omits reviewer fields and cannot establish an empty reviewer list.
- Identity comes from `bkt api /user --json` (`uuid`, `account_id`, `username`), matched on `uuid` and `account_id` only. Resolve it once with `bkt_identity()` and pass it through when scanning many repos.
- Pagination is bounded to 100 pages of 50 rows within 20 seconds for the repository. Every continuation must retain the repository and query scope. Missing reviewer identities, repeated PR IDs, incomplete pagination, a 404, non-zero exit, timeout, or unparseable body returns `{"status": "unscanned", "reason": ...}` with no partial `items`. Only an explicit complete empty inventory is an empty queue.
- Read-only. Tests inject a `runner` and never reach `bkt`.

## Safety rules

1. **Reads are free; writes are deliberate.** Never `approve`, `merge`, `decline`, or `create` without the operator's explicit intent for that specific PR.
2. **One command surface.** Do not mix `bkt`, raw `curl`, and git-host web UIs in one workflow — state drifts and auth surfaces multiply.
3. **Repo-level skills do not travel.** A skill checked into one repo is not loaded when the session works elsewhere. Install this skill (and your team's companion) at the personal/agent level so the command surface is present in every session.

## When NOT to apply

- GitHub or GitLab repos (`gh` / `glab` are the right tools there)
- Bitbucket Data Center quirks beyond `bkt`'s support — check the project's README first

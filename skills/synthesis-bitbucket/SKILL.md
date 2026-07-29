---
name: synthesis-bitbucket
description: "Work with Bitbucket Cloud repos through the open-source bkt CLI — PR lifecycle (list, view, diff, comment, approve, merge), repo/branch reads, and the bkt api escape hatch. Encodes auth setup, the context-host gotcha, a gh-to-bkt command map, and write-safety rules so agents use one consistent command surface instead of reinventing REST calls. Use when asked to: bitbucket, bkt, bitbucket pr, open bitbucket pr, review bitbucket pr, bitbucket cli, bitbucket api."
license: "Apache-2.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.0.0"
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

## Set the default context

```bash
bkt context create <name> --host https://api.bitbucket.org/2.0 \
  --workspace <workspace> --repo <repo>
bkt context use <name>
```

**Gotcha:** `bkt context create` requires `--host`, and the host string must exactly match the one shown by `bkt auth status` (for Cloud: `https://api.bitbucket.org/2.0`, not `https://bitbucket.org`). A mismatched host fails with "host not found; run bkt auth login first" even when you are logged in.

## Command catalog

Global flags on any command: `--json` · `--jq '<expr>'` (with `--json`) · `--format json|yaml` · `-c <context>`. Context overrides: `--workspace`, `--repo`.

### Read (safe, use freely)

- `bkt pr list` — `--state OPEN|MERGED|DECLINED` · `--limit <n>` (0 = all) · `--mine`
- `bkt pr view <id>` · `bkt pr diff <id> [--stat]` · `bkt pr comments <id> [--state unresolved]` · `bkt pr checks <id> [--wait]`
- `bkt repo view` · `bkt branch list` · `bkt pipeline list|view`

### Write (consequential — confirm intent before running)

- `bkt pr create --title <t> --description <d> --source <branch> --target <branch> [--reviewer <user|{UUID}>]… [--with-default-reviewers] [--draft]`
- `bkt pr comment <id> --text <msg> [--parent <comment-id>] [--file <path> --to-line <n>]`
- `bkt pr edit <id>` · `bkt pr approve <id>` · `bkt pr merge <id> --strategy merge_commit|squash|fast_forward` · `bkt pr decline <id>` · `bkt pr reopen <id>`

### Escape hatch

- `bkt api /repositories/<ws>/<repo>/...` — raw REST with auth handled. Use only for surfaces the catalog lacks; prefer adding a note to your team's companion skill when a gap becomes routine.

## `gh` → `bkt` map

| gh | bkt |
|---|---|
| `gh pr list` | `bkt pr list` |
| `gh pr view N` | `bkt pr view N` |
| `gh pr diff N` | `bkt pr diff N` |
| `gh pr create` | `bkt pr create` |
| `gh pr review --approve` | `bkt pr approve N` |
| `gh pr merge N` | `bkt pr merge N` |
| `gh pr comment N -b …` | `bkt pr comment N --text …` |
| `gh api …` | `bkt api …` |

Bitbucket Cloud has **no PR labels** and its PR states are `OPEN`, `MERGED`, `DECLINED`, `SUPERSEDED` — port `gh` habits accordingly.

## Safety rules

1. **Reads are free; writes are deliberate.** Never `approve`, `merge`, `decline`, or `create` without the operator's explicit intent for that specific PR.
2. **One command surface.** Do not mix `bkt`, raw `curl`, and git-host web UIs in one workflow — state drifts and auth surfaces multiply.
3. **Repo-level skills do not travel.** A skill checked into one repo is not loaded when the session works elsewhere. Install this skill (and your team's companion) at the personal/agent level so the command surface is present in every session.

## When NOT to apply

- GitHub or GitLab repos (`gh` / `glab` are the right tools there)
- Bitbucket Data Center quirks beyond `bkt`'s support — check the project's README first

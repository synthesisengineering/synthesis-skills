# Setup: install, authenticate, connect

One-time setup for `bkt`, kept as written in 1.2.2.

Contents:
- Install and pin
- Authenticate (OAuth or a scoped API token, and the git-versus-REST credential split)
- Configure connection context and bind each repository (the context-host gotcha)

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

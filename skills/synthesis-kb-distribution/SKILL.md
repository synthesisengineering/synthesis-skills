---
name: synthesis-kb-distribution
description: "Publish an OKF knowledge base to Claude and ChatGPT as an organization plugin, and serve it to people outside those workspaces through a read-only connector with Google sign-in and an access list. Use to set up, deploy, check or change knowledge-base distribution."
license: Apache-2.0
depends_on:
  - synthesis-okf
metadata:
  author: Rajiv Pant
  version: "1.0.0"
  format: v5
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Synthesis Knowledge-Base Distribution

An organization's knowledge base (OKF markdown in its own repository) reaches its people two ways
from one published tree: an organization plugin inside the Claude and ChatGPT workspaces, and a
read-only MCP connector for people those workspaces cannot reach, such as executives on personal
accounts. This skill holds the published tree's contract, the connector (`scripts/connector/`),
its tests and its deployment.

## Binding rules

1. **One published tree feeds both channels.** CI builds it from the knowledge base's default
   branch and pushes it to a private repository; nothing is published by hand. Both channels then
   show the same commit, so any answer traces to one source commit.
2. **Every published file keeps its provenance stamp,** and the connector reports the commit it
   serves (`/health`, and `served_commit` in `fetch`). Without them nobody can say what a reader saw.
3. **The connector never serves without sign-in.** No setting turns it off, and an empty access
   list stops the start, because a knowledge base for named people must not become public by a typo.
4. **The access list is checked at sign-in, on every token and on every tool call;** Google must
   report the address verified, and `KB_ALLOWED_HOSTED_DOMAINS` narrows it further. A removal takes
   effect on the person's next request.
5. **The connector's deploy key is read-only and separate from CI's write key,** both kept in
   secret managers, so a leaked connector key can read but never change the published tree.
6. **Secrets come from a secret manager,** never from the image, a repository or a deploy script:
   the OAuth client secret, the JWT signing key, the storage encryption key and the deploy key.
7. **Production uses `KB_OAUTH_STORE=firestore` with `KB_STORAGE_ENCRYPTION_KEY`.** The memory
   store loses every sign-in when an instance stops, and Cloud Run stops instances freely.
8. **Use an Internal OAuth consent screen** in the organization's Google Workspace, so accounts
   outside the organization cannot even begin a sign-in.
9. **Pin known-hosts lines you checked against the git host's published fingerprints;** host keys
   are checked strictly, so a man-in-the-middle cannot feed the connector content.
10. **Run the connector's tests with its pinned requirements before any deploy or upgrade:** the
    sign-in check reads two private FastMCP attributes and fails closed when they move.
11. **Nothing organization-specific goes into this skill.** Names, addresses and repositories live in
    the deployment's settings.

## Contents

- [references/published-layout.md](references/published-layout.md): the published tree (paths,
  manifests, index, provenance stamp), the checks a build makes before publishing, the CI step and
  how administrators give the plugin to the organization. Read it when building or checking the
  organization plugin or the publishing pipeline.
- [references/connector.md](references/connector.md): what the connector does, how access works,
  every environment variable, a local run, deployment on Google Cloud Run, adding it in ChatGPT
  and Claude, changing the access list and operating it. Read it before deploying, configuring or
  troubleshooting the connector.
- Commands, Setting it up, Checking it: below.

## Commands

The connector's tests, from the repository root:

```bash
python3 -m pytest -q skills/synthesis-kb-distribution/tests
```

It prints `N passed` (with `M skipped` when FastMCP is not installed: the server tests need the
pinned requirements and Python 3.12 or newer; `SYNTHESIS_REQUIRE_FASTMCP=1` makes them fail
instead of skipping). To run every test, install the lock into a virtual environment first:

```bash
python3.12 -m venv ~/.venvs/kb-connector
~/.venvs/kb-connector/bin/pip install pytest
~/.venvs/kb-connector/bin/pip install --require-hashes --no-deps -r skills/synthesis-kb-distribution/scripts/connector/requirements.txt
~/.venvs/kb-connector/bin/python -m pytest -q skills/synthesis-kb-distribution/tests
```

The image, from the repository root:

```bash
docker build --platform linux/amd64 -f skills/synthesis-kb-distribution/scripts/connector/Dockerfile -t kb-connector .
```

The running connector (`python -B -m kb_connector` from `scripts/connector/`) prints
`serving <n> documents from commit <sha>` when a copy loads, `refresh failed (...)` when a refresh
fails, and `sign-in allowed for <email>` or `sign-in refused for <email>: <reason>` per sign-in. If
its settings are wrong it prints `kb-connector: the connector cannot start:` and every problem,
then exits 2; if the first load fails it prints `kb-connector: the first load failed: <reason>` and
exits 1.

## Setting it up

1. **Publish.** Make CI build the published tree on every merge to the knowledge base's default
   branch and push it to a private repository (references/published-layout.md, sections 2 to 5).
2. **Organization plugin.** The workspace administrators add the published repository in Claude and
   ChatGPT and assign the plugin (section 6 there).
3. **Connector.** Deploy it on Cloud Run with a Google OAuth client, Firestore, Secret Manager and a
   read-only deploy key (references/connector.md, section 5), then give the listed people its
   address ending in `/mcp` to add in ChatGPT or Claude (section 6).

## Checking it

1. `curl -s <public-url>/health` shows `"status": "ok"` and the commit CI last pushed.
2. A listed person adds the connector, signs in and gets results from a search.
3. An address that is not listed reaches Google's sign-in and then sees
   `Access denied: <email> is not on this knowledge base's access list.`
4. After an address is removed (references/connector.md, section 7), that person's next request
   is refused.

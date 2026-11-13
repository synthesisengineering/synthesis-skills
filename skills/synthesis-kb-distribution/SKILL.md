---
name: synthesis-kb-distribution
description: "Publish an OKF knowledge base to Claude and ChatGPT as an organization plugin, and serve it to people outside those workspaces through a read-only connector with Google sign-in and an access list. Use to set up, deploy, check or change knowledge-base distribution."
license: Apache-2.0
depends_on:
  - synthesis-okf
metadata:
  author: Rajiv Pant
  version: "1.2.2"
  format: v5
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Synthesis Knowledge-Base Distribution

An organization's knowledge base (OKF markdown in its own repository) reaches its people two ways
from one published tree: an organization plugin inside the Claude and ChatGPT workspaces, and a
read-only MCP connector for people those workspaces cannot reach, such as executives on personal
accounts. This skill holds the published tree's contract, the scripts that build and publish it
(`scripts/build_plugin.py`, `scripts/publish_plugin.sh`) with generic templates, the connector
(`scripts/connector/`), their tests and the connector's deployment, and a Drive copy for Gemini
Notebook (`scripts/publish_drive.py`).

## Binding rules

1. **One published tree feeds both channels.** CI builds it from the knowledge base's default
   branch and pushes it to a private repository; nothing is published by hand. Both channels then
   show the same commit, so any answer traces to one source commit.
2. **Every published file keeps its provenance stamp,** and the connector reports the commit it
   serves (`/health`, and `served_commit` in `fetch`). Without them nobody can say what a reader saw.
3. **The connector never serves without sign-in.** No setting turns it off, and a start with no
   addresses and no groups stops, because a knowledge base for named people must not become public by a typo.
4. **The access list is checked at sign-in, on every token and on every tool call;** it holds
   addresses, the members of Google groups the organization's IT manages, or both. Google must
   report the address verified, and `KB_ALLOWED_HOSTED_DOMAINS` narrows it further. A removal takes
   effect on the person's next request, or at the next group read for a group member.
5. **The connector's deploy key is read-only and separate from CI's write key,** both kept in
   secret managers, so a leaked connector key can read but never change the published tree.
6. **Secrets come from a secret manager,** never from the image, a repository or a deploy script:
   the OAuth client secret, the JWT signing key, the storage encryption key and the deploy key.
7. **Production uses `KB_OAUTH_STORE=firestore` with `KB_STORAGE_ENCRYPTION_KEY`.** The memory
   store loses every sign-in when an instance stops, and Cloud Run stops instances freely. The
   connector starts on it only in the operator-only test mode.
8. **Use an Internal OAuth consent screen** in the organization's Google Workspace, so accounts
   outside the organization cannot even begin a sign-in.
9. **Pin known-hosts lines you checked against the git host's published fingerprints;** host keys
   are checked strictly, so a man-in-the-middle cannot feed the connector content.
10. **Run the connector's tests with its pinned requirements before any deploy or upgrade:** the
    sign-in check reads two private FastMCP attributes and fails closed when they move.
11. **Nothing organization-specific goes into this skill.** Names, addresses and repositories live in
    the deployment's settings and in the knowledge base's own build config and templates.
12. **CI runs the scripts at a pinned release whose commit it checks:** that step holds the write
    key, so a moved tag must not change what runs.
13. **A refused file is fixed or excluded, never let through by loosening the lint:** every
    assistant that loads the plugin would read it.

## Contents

- [references/published-layout.md](references/published-layout.md): the published tree (paths,
  manifests, index, provenance stamp), the build script with every config setting and template
  placeholder, its checks, the publish script and its CI step at a pinned release, how
  administrators give the plugin to the organization, and the Drive copy for Gemini Notebook
  (section 8). Read it when setting up, changing or troubleshooting the build, the publishing
  pipeline or the Drive copy.
- `templates/`: the generic SKILL.md and README.md templates, and the example config and exclusion
  list to copy.
- [references/connector.md](references/connector.md): what the connector does, how access works,
  every environment variable, a local run, deployment on Google Cloud Run, adding it in ChatGPT
  and Claude, changing the access list and operating it. Read it before deploying, configuring or
  troubleshooting the connector.
- Commands, Setting it up, Checking it: below.

## Commands

The skill's tests (the build, the publish script and the connector), from the repository root:

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

The build and the publication, from the knowledge base's repository (references/published-layout.md,
sections 4 and 6):

```bash
python3 <skill>/scripts/build_plugin.py --config distribution/kb-plugin.json --source source --out build/kb-plugin
KB_PUBLISH_REPO=<url> KB_PUBLISH_KNOWN_HOSTS=<line> sh <skill>/scripts/publish_plugin.sh --config distribution/kb-plugin.json --source source
```

The build prints `Built <plugin> <version> from <sha7> (<date>) into <out>` and each file left out;
a refusal lists every problem, writes nothing and exits 1. The publication then prints
`Published <plugin> <version> to <repository> (<branch>).` or `... nothing to push.`

## Setting it up

1. **Publish.** Copy and fill in the example config and exclusion list from `templates/`, then make
   CI run `publish_plugin.sh` at a pinned release on every merge (references/published-layout.md,
   sections 4 to 6).
2. **Organization plugin.** The workspace administrators add the published repository in Claude and
   ChatGPT and assign the plugin (section 7 there).
3. **Connector.** Deploy it on Cloud Run with a Google OAuth client, Firestore, Secret Manager and a
   read-only deploy key (references/connector.md, section 5), then give the listed people its
   address ending in `/mcp` to add in ChatGPT or Claude (section 6).
4. **Gemini Notebook (optional).** Make CI also run `publish_drive.py`, keeping a shared drive
   folder current for a notebook (references/published-layout.md, section 8).

## Checking it

1. The pipeline's log ends with `Published ...` or `nothing to push`, with only the expected
   `left out` lines.
2. `curl -s <public-url>/health` shows `"status": "ok"` and the commit CI last pushed.
3. A listed person adds the connector, signs in and gets results from a search.
4. An address that is not listed reaches Google's sign-in and then sees
   `Access denied: <email> is not on this knowledge base's access list.`
5. After an address is removed (references/connector.md, section 7), that person's next request
   is refused.
6. A Drive copy's log ends `Drive copy of ...`; each `added` or `moved to trash` file is a
   notebook source to add or remove.

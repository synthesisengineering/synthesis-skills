# The read-only knowledge-base connector

Contents:

1. What it does
2. How access works
3. Settings (environment variables)
4. Run it locally
5. Deploy on Google Cloud Run
6. Add it in ChatGPT and in Claude
7. Change the access list
8. Operate it
9. What it does not do

The code is in `scripts/connector/`: the `kb_connector` package, `Dockerfile`,
`Dockerfile.dockerignore`, `requirements.in` and the hashed lock `requirements.txt`. Its tests are
in `tests/test_kb_connector_*.py`.

## 1. What it does

The organization plugin reaches people inside the organization's Claude and ChatGPT workspaces.
People outside those workspaces, such as executives on personal ChatGPT or Claude accounts, cannot
receive an organization plugin. The connector serves them the same published content as a remote
MCP server (Model Context Protocol, the protocol both products use for custom connectors).

- **Two tools, both read-only.** `search(query)` returns `{"results": [...]}`, each result with
  `id`, `title`, `url` and a short `snippet`. `fetch(id)` returns `id`, `title`, `text` (the whole
  published markdown after its front matter, provenance stamp included), `url` and `metadata`. The
  metadata holds `front_matter` (every front-matter field), `provenance` (the stamp line),
  `source_path`, `source_repository`, `source_commit`, `published` and `served_commit`. These are
  the shapes ChatGPT's connectors and deep research expect: structured content, with the same
  object as JSON in the text content. Both tools carry `readOnlyHint: true`,
  `destructiveHint: false`, `idempotentHint: true` and `openWorldHint: false`.
- **Ranking.** BM25F over title, description, path and body, with the standard library only.
  A title match counts three times a body match, plurals and common suffixes fold (price, prices,
  priced and pricing match each other), and a phrase match ranks higher.
- **Content.** The connector clones the published repository shallowly at start, using a
  read-only deploy key, and asks the remote for its head every `KB_REFRESH_SECONDS` (600 by
  default). Only when the head moved does it clone again, into a new folder. The new copy is served
  only after it loads; a failed check, clone or load keeps the last good copy serving. A commit
  whose content will not load is not cloned again until the remote moves. Every markdown file under
  the published `references/` folder is a document; its id is its path there. Files in hidden
  folders are never served.
- **Health.** `GET /health` answers without sign-in:
  `{"status": "ok", "commit": "<sha>", "files": 412, "refreshed_at": "...Z", "last_attempt_at":
  "...Z", "last_refresh_failed": false}`, with status 200 while a copy is served and 503 before
  the first load. The path is `/health`, not `/healthz`: Cloud Run reserves some paths that end in
  `z`.
- **Sign-in.** Google, through FastMCP's OAuth proxy (`GoogleProvider`). ChatGPT and Claude
  register themselves (dynamic client registration, or client ID metadata documents), the person
  approves the connection on a consent page, then signs in with Google. The connector issues its
  own tokens and keeps Google's tokens encrypted in its OAuth store.

## 2. How access works

The access list is `KB_ALLOWED_EMAILS`. It is checked three times:

1. **At sign-in.** After Google returns, the connector reads the signed-in account and checks the
   list before any grant goes back to ChatGPT or Claude. A person not on the list sees a page
   saying why, and their client gets nothing.
2. **On every request.** Every bearer token is checked against Google and then against the list,
   so removing an address takes effect on that person's next request.
3. **On every tool call and tool listing.** A token for someone not on the list lists no tools and
   every call returns the reason.

To pass, the account's email must be on the list (letter case does not matter), Google must
report the address as verified, and when `KB_ALLOWED_HOSTED_DOMAINS` is set the account must belong
to one of those Google Workspace domains (Google's `hd` value; a personal Gmail account has none).
The messages a refused person sees:

- `Access denied: <email> is not on this knowledge base's access list. Ask its administrator to add the address.`
- `Access denied: Google has not verified the address <email>.`
- `Access denied: <email> is not an account in an allowed Google Workspace domain.`
- `Access denied: this sign-in could not be checked against the access list. ...` (the check
  itself failed, so the sign-in is refused rather than let through)

There is no setting that serves without sign-in, and an empty access list stops the start.

Logs name the email address and the reason, never a token. The HTTP access log is off, because the
Google callback's address carries Google's authorization code in its query string. Cloud Run's own
request log still records that address; the code is single-use, already spent by the time it is
logged, and useless without the client secret and the PKCE verifier.

## 3. Settings (environment variables)

Every setting is an environment variable. A start with a missing or malformed value stops and
lists every problem at once.

**Content**

| Variable | Default | Meaning |
|---|---|---|
| `KB_GIT_URL` | (one of these two is required) | The published repository, for example `git@github.com:<org>/<plugin-repo>.git`. |
| `KB_SOURCE_DIR` | | A local published tree instead of a repository, for local runs and tests. |
| `KB_GIT_BRANCH` | the remote's default branch | The branch to serve. |
| `KB_GIT_SSH_KEY_FILE` | required for an SSH URL | Path to the read-only deploy key's private half, mounted from the secret manager. The connector copies it to a private 0600 file, since a mounted secret may be readable by others, and adds a final newline if the secret lacks one. |
| `KB_GIT_KNOWN_HOSTS` | required for an SSH URL | The git host's known-hosts line or lines, for example `github.com ssh-ed25519 AAAA...`. Host keys are checked strictly. |
| `KB_REFRESH_SECONDS` | `600` | How often to ask the remote for its head; `0` never refreshes after the first load. |
| `KB_WORK_DIR` | `/tmp/kb-connector` in the image | Where clones are kept: one, or two during a swap. |
| `KB_REFERENCES_PATH` | the one `plugins/*/skills/*/references` folder | The folder to serve, relative to the tree, when the tree holds more than one plugin. |

**Sign-in and access**

| Variable | Default | Meaning |
|---|---|---|
| `KB_PUBLIC_URL` | required | The service's public `https://` address, with no path. `http://` is accepted only for localhost. |
| `KB_GOOGLE_CLIENT_ID` | required | The Google OAuth client's ID. |
| `KB_GOOGLE_CLIENT_SECRET` | required, secret | The Google OAuth client's secret. |
| `KB_ALLOWED_EMAILS` | required | Comma-separated addresses that may read the knowledge base. |
| `KB_ALLOWED_HOSTED_DOMAINS` | none | Comma-separated Google Workspace domains; when set, accounts outside them are refused even if listed. |
| `KB_JWT_SIGNING_KEY` | derived from the client secret | Secret that signs the connector's own tokens. Set it so rotating the Google client secret does not sign everyone out. |
| `KB_OAUTH_STORE` | `memory` | `firestore` for any deployment: registrations, grants and Google tokens survive restarts and are shared by every instance. `memory` loses them when the process stops. |
| `KB_STORAGE_ENCRYPTION_KEY` | required with `firestore`, secret | A Fernet key (44 characters) that encrypts everything the OAuth store writes. |
| `KB_FIRESTORE_PROJECT` | the runtime's project | Google Cloud project of the Firestore database. |
| `KB_FIRESTORE_DATABASE` | `(default)` | Firestore database name. |
| `KB_FIRESTORE_COLLECTION_PREFIX` | `kb-connector` | Prefix for the store's collections, so several connectors can share a database. |
| `KB_ALLOWED_REDIRECT_URIS` | any redirect a client registered | Comma-separated patterns (`*` matches anything) for the clients' OAuth redirect addresses. See section 6 for the vendors' published values. |
| `KB_TOKEN_CACHE_SECONDS` | `300` | How long a Google token check is reused; `0` checks with Google on every request. |

**Serving**

| Variable | Default | Meaning |
|---|---|---|
| `KB_SERVER_NAME` | `Knowledge base` | The name clients show for the server. |
| `KB_DOCUMENT_URL_TEMPLATE` | `kb:{id}` | Each document's `url`, for citations. Use `{id}`, `{source_path}` and `{commit}`; set it to an address people can open, such as the source repository's file view: `https://<git-host>/<org>/<kb-repo>/blob/{commit}/{source_path}`. ChatGPT cites a result only when its url is non-empty and recommends addresses a person can open. |
| `KB_SEARCH_LIMIT` | `10` | Results per search, 1 to 50. |
| `PORT` | `8080` | Port to listen on; Cloud Run sets it. |
| `KB_HOST` | `0.0.0.0` | Address to listen on. |
| `KB_LOG_LEVEL` | `INFO` | Log level. |

## 4. Run it locally

Use a virtual environment outside the plugin, with Python 3.12 or newer:

```bash
python3.12 -m venv ~/.venvs/kb-connector
~/.venvs/kb-connector/bin/pip install --require-hashes --no-deps -r <skill-root>/scripts/connector/requirements.txt
cd <skill-root>/scripts/connector
KB_SOURCE_DIR=<published-tree> KB_PUBLIC_URL=http://localhost:8080 \
KB_GOOGLE_CLIENT_ID=<id> KB_GOOGLE_CLIENT_SECRET=<secret> KB_ALLOWED_EMAILS=<you@example.com> \
  ~/.venvs/kb-connector/bin/python -B -m kb_connector
```

It prints `serving <n> documents from commit <sha>` and then uvicorn's startup lines. `-B` keeps
Python from writing bytecode into the plugin folder. For Google sign-in to work locally, add
`http://localhost:8080/auth/callback` as an authorized redirect URI on the OAuth client.

## 5. Deploy on Google Cloud Run

These steps use placeholders: `<project>` and `<region>` for the Google Cloud project and region,
`<service>` for the Cloud Run service name, `<number>` for the project number. Run them as someone
who administers that project.

**5.1 Address.** Cloud Run gives a service the address
`https://<service>-<number>.<region>.run.app`. That is `KB_PUBLIC_URL`, unless you map a custom
domain. Confirm it after the first deploy with
`gcloud run services describe <service> --region <region> --format 'value(status.url)'`.

**5.2 Google OAuth consent screen.** In the Google Cloud console for `<project>`, under Google Auth
Platform, set the audience (user type) to **Internal**, so only accounts in the organization's
Google Workspace can sign in at all. Request the `openid` and `email` scopes.

**5.3 OAuth client.** Create an OAuth client of type **Web application**. Add the authorized
redirect URI `https://<service>-<number>.<region>.run.app/auth/callback` (or the custom domain's).
Keep the client ID for `KB_GOOGLE_CLIENT_ID`; the secret goes into Secret Manager next.

**5.4 Secrets.** Create each secret in Secret Manager, reading the value from standard input so it
never lands in a file or the shell history:

```bash
gcloud secrets create kb-connector-client-secret --data-file=-        # paste the OAuth client secret
python3 -c "import secrets; print(secrets.token_urlsafe(48))" | gcloud secrets create kb-connector-jwt-key --data-file=-
python3 -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())" \
  | gcloud secrets create kb-connector-storage-key --data-file=-
```

The third command makes a Fernet key: 32 random bytes in URL-safe base64, 44 characters.

**5.5 Read-only deploy key.** Generate a key pair for this connector alone, give the published
repository its public half as a deploy key **without write access** (on GitHub: the repository's
Settings, Deploy keys, Add deploy key, with "Allow write access" left unchecked), store the private
half in Secret Manager, then delete both local files:

```bash
ssh-keygen -t ed25519 -N "" -C "kb-connector read-only" -f kb-connector-deploy-key
gcloud secrets create kb-connector-deploy-key --data-file=kb-connector-deploy-key
rm kb-connector-deploy-key kb-connector-deploy-key.pub
```

Use a different key from the one CI uses to push the published tree; that one needs write access
and should never reach the connector.

**5.6 Known hosts.** Fetch the git host's key and compare its fingerprint with the one the host
publishes (GitHub lists its SSH key fingerprints in its documentation):

```bash
ssh-keyscan -t ed25519 github.com > known-host
ssh-keygen -lf known-host        # compare this fingerprint with the published one before using it
```

The line in `known-host` is `KB_GIT_KNOWN_HOSTS`.

**5.7 Firestore.** Create a Firestore database in Native mode in `<project>` (the `(default)`
database, or a named one given in `KB_FIRESTORE_DATABASE`). The OAuth store writes small encrypted
records under collections starting with `KB_FIRESTORE_COLLECTION_PREFIX`. Expired records are
ignored when read and stay until overwritten; their expiry is stored as text, so a Firestore TTL
policy cannot remove them.

**5.8 Service account.** Create a service account for the service and grant it the Secret Manager
Secret Accessor role on the four secrets and the Cloud Datastore User role on the project (the
role Firestore uses). Grant nothing else.

**5.9 Image.** Create an Artifact Registry Docker repository, then build from the root of the
synthesis-skills repository (the image takes the plugin's YAML reader from `synthesis/`) and push:

```bash
docker build --platform linux/amd64 -f skills/synthesis-kb-distribution/scripts/connector/Dockerfile \
  -t <region>-docker.pkg.dev/<project>/<registry>/kb-connector:<version> .
docker push <region>-docker.pkg.dev/<project>/<registry>/kb-connector:<version>
```

The image runs as an unprivileged user, installs only the hashed lock with `--no-deps`, and starts
`python -m kb_connector` on `$PORT`.

**5.10 Settings file.** Keep the plain settings in a YAML file, since the access list has commas
and the known-hosts line has spaces:

```yaml
KB_GIT_URL: git@github.com:<org>/<plugin-repo>.git
KB_GIT_KNOWN_HOSTS: github.com ssh-ed25519 AAAA...
KB_GIT_SSH_KEY_FILE: /secrets/deploy-key
KB_PUBLIC_URL: https://<service>-<number>.<region>.run.app
KB_GOOGLE_CLIENT_ID: <id>.apps.googleusercontent.com
KB_ALLOWED_EMAILS: first.person@<domain>,second.person@<domain>
KB_ALLOWED_HOSTED_DOMAINS: <domain>
KB_OAUTH_STORE: firestore
KB_SERVER_NAME: <Organization> knowledge
KB_DOCUMENT_URL_TEMPLATE: https://github.com/<org>/<kb-repo>/blob/{commit}/{source_path}
```

**5.11 Deploy.**

```bash
gcloud run deploy <service> --region <region> \
  --image <region>-docker.pkg.dev/<project>/<registry>/kb-connector:<version> \
  --service-account <service-account-email> \
  --env-vars-file kb-connector.env.yaml \
  --set-secrets KB_GOOGLE_CLIENT_SECRET=kb-connector-client-secret:latest,KB_JWT_SIGNING_KEY=kb-connector-jwt-key:latest,KB_STORAGE_ENCRYPTION_KEY=kb-connector-storage-key:latest,/secrets/deploy-key=kb-connector-deploy-key:latest \
  --allow-unauthenticated \
  --memory 512Mi --cpu 1 --max-instances 3
```

- `--allow-unauthenticated` is required: ChatGPT and Claude cannot present Google Cloud identity
  tokens, so Cloud Run must pass requests through and the connector's own sign-in decides. No
  request reaches a tool without a token for someone on the list.
- A secret named with a path (`/secrets/deploy-key=...`) is mounted as a file; the others become
  environment variables.
- The service listens only after its first load succeeds, so a deploy whose content cannot be
  fetched fails Cloud Run's startup check instead of serving nothing.
- With request-based billing Cloud Run gives an instance CPU only while it handles requests, so the
  background refresh runs late on an idle instance. A new instance always loads the current head.
  If the refresh interval must hold, deploy with `--no-cpu-throttling`.

**5.12 Check it.**

```bash
curl -s https://<service>-<number>.<region>.run.app/health
curl -s -i -X POST https://<service>-<number>.<region>.run.app/mcp | grep -i www-authenticate
```

The first prints the health JSON with the commit CI last published. The second prints
`www-authenticate: Bearer ... resource_metadata="https://.../.well-known/oauth-protected-resource/mcp"`,
which is how clients discover the sign-in.

## 6. Add it in ChatGPT and in Claude

The connector's address for both is `KB_PUBLIC_URL` followed by `/mcp`.

**ChatGPT** (OpenAI's developer documentation, read 2026-11-09): open ChatGPT Plugins at
`https://chatgpt.com/plugins`, select the plus button, then **Add custom MCP server**. Give it a
name and description, enter the address under Connection, configure authentication as OAuth,
review the risk warning, confirm, and select **Create as a plugin**. Whether a given ChatGPT plan
or workspace allows custom MCP servers, and whether it sits behind developer mode, follows the
account's and workspace's policies; check OpenAI's current help pages. ChatGPT's documented
redirect is `https://chatgpt.com/connector_platform_oauth_redirect` for servers that send the
issuer with each authorization response (this one does), otherwise
`https://chatgpt.com/connector/oauth/<callback-id>`; the server's management page in ChatGPT shows
the exact value.

**Claude** (Claude's help center and connector documentation, read 2026-11-09): on Pro and Max
plans, the person goes to **Customize > Connectors**, selects **+ Add**, then **Add custom
connector**, enters a name and the address, and continues through the authentication settings
(the connector registers automatically). On Team and Enterprise plans an Owner adds it under
**Organization settings > Connectors**, and members then connect to it individually. Claude's
hosted apps use the redirect `https://claude.ai/api/mcp/auth_callback`; Claude Code uses a loopback
address on any port.

The first use opens the connector's consent page, then Google's sign-in. To limit which clients
can complete sign-in, set `KB_ALLOWED_REDIRECT_URIS`, for example to
`https://claude.ai/api/mcp/auth_callback,https://chatgpt.com/connector_platform_oauth_redirect,https://chatgpt.com/connector/oauth/*`.
Confirm the values against each vendor's current documentation first; an address missing from the
list refuses that client.

## 7. Change the access list

Edit `KB_ALLOWED_EMAILS` in the settings file and redeploy with the same command, or update the
one variable (gcloud's `^;^` prefix makes `;` the separator, so the commas stay inside the value):

```bash
gcloud run services update <service> --region <region> \
  --update-env-vars '^;^KB_ALLOWED_EMAILS=first.person@<domain>,second.person@<domain>'
```

The new revision serves the next request. A removed person's existing token stops working on
their next request; an added person can sign in at once.

## 8. Operate it

- **Is it current?** `/health` shows the served commit. Compare it with the published repository's
  head. `last_refresh_failed: true` means the last check, clone or load failed and the last good
  copy is still served; the log line `refresh failed (last good copy kept): ...` says why.
- **Log lines worth alerting on:** `refresh failed`, `sign-in refused for <email>: <reason>`,
  `token refused for <email>: <reason>` and `sign-in check failed`. The first means stale content;
  the others show who was refused.
- **Rotate a secret:** add a new version in Secret Manager and redeploy (or update the service) so
  a new revision reads it. Rotating `KB_JWT_SIGNING_KEY` or `KB_STORAGE_ENCRYPTION_KEY` signs
  everyone out; they sign in again on their next use.
- **Rotate the deploy key:** add the new public key to the repository, store the new private key as
  a new secret version, redeploy, then remove the old deploy key from the repository.
- **Upgrade FastMCP:** change `requirements.in`, regenerate `requirements.txt` with the command in
  its header, and run the connector's tests with the new lock installed. The sign-in check reads
  two private attributes of FastMCP's OAuth proxy (`_code_store`, `_token_validator`); if an
  upgrade moves them, the sign-in check fails closed and `test_kb_connector_server.py` fails.
- **Tests:** `python3 -m pytest -q skills/synthesis-kb-distribution/tests` from the repository
  root. Without the requirements installed, the FastMCP tests skip; with
  `SYNTHESIS_REQUIRE_FASTMCP=1` they fail instead of skipping.

## 9. What it does not do

- It never writes: there is no tool that changes the knowledge base or anything else.
- It has no per-document permissions. Everyone on the list can read everything published; leave a
  file out of the published tree to keep it from connector readers.
- It does not reach the knowledge base's source repository, only the published tree.
- It does not replace the organization plugin for people inside the workspaces; both serve the same
  published commit.

# The read-only knowledge-base connector

Contents:

1. What it does
2. How access works
3. Settings (environment variables)
4. Run it locally: the operator's own test
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
- **The plugin's guide through fetch.** `fetch("SKILL.md")` returns the plugin's own `SKILL.md`
  (what the knowledge base covers and the index of its documents) with an empty `url`; search
  never returns it. A platform that takes an MCP server but not a plugin, such as an agent builder,
  can tell its agent to fetch `SKILL.md` first, so the agent's instructions never hold a copy of the
  index that goes stale. The guide is read only from inside the published tree, never through a link.
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
  "...Z", "last_refresh_failed": false, "test_only": false}`, with status 200 while a copy is
  served and 503 before the first load. `test_only` is `true` while the connector runs as the
  operator's own test (section 4) and `false` otherwise. The path is `/health`, not `/healthz`:
  Cloud Run reserves some paths that end in `z`.
- **Sign-in.** Google, through FastMCP's OAuth proxy (`GoogleProvider`). ChatGPT and Claude
  register themselves (dynamic client registration, or client ID metadata documents), the person
  approves the connection on a consent page, then signs in with Google. The connector issues its
  own tokens and keeps Google's tokens encrypted in its OAuth store.

## 2. How access works

The access list is `KB_ALLOWED_EMAILS`, the members of the Google groups in `KB_ALLOWED_GROUPS`, or
both: a person on either passes. It is checked three times:

1. **At sign-in.** After Google returns, the connector reads the signed-in account and checks the
   list before any grant goes back to ChatGPT or Claude. A person not on the list sees a page
   saying why, and their client gets nothing.
2. **On every request.** Every bearer token is checked against Google and then against the list,
   so removing an address takes effect on that person's next request.
3. **On every tool call and tool listing.** A token for someone not on the list lists no tools and
   every call returns the reason.

**Groups.** With `KB_ALLOWED_GROUPS` set, the connector reads each group's members from Google's
Cloud Identity Groups API at start and every `KB_GROUP_REFRESH_SECONDS` (five minutes by default),
following groups nested inside them, as its own service account with the read-only groups scope.
People added to or removed from a group gain or lose access at the next read. If a read fails, the
last good membership is kept for at most three intervals; after that nobody gets in through a group
until a read succeeds, while the addresses in `KB_ALLOWED_EMAILS` keep working. A start whose first
read fails stops, so a deploy without the grant in section 7.2 fails loudly instead of letting
nobody in quietly. A group member counts as a person only through an individual account: a group
whose member is the whole organization or a customer is not expanded.

To pass, the account's email must be on the list or in a group (letter case does not matter), Google must
report the address as verified, and when `KB_ALLOWED_HOSTED_DOMAINS` is set the account must belong
to one of those Google Workspace domains (Google's `hd` value; a personal Gmail account has none).
The messages a refused person sees:

- `Access denied: <email> is not on this knowledge base's access list. Ask its administrator to add the address.`
- `Access denied: Google has not verified the address <email>.`
- `Access denied: the access groups could not be read just now. ...` (the group membership is
  older than three refresh intervals, so a group member is refused rather than let through)
- `Access denied: <email> is not an account in an allowed Google Workspace domain.`
- `Access denied: this sign-in could not be checked against the access list. ...` (the check
  itself failed, so the sign-in is refused rather than let through)

There is no setting that serves without sign-in, and a start with no addresses and no groups stops.

**The operator-only test mode.** With `KB_OPERATOR_TEST=1`, only the addresses in
`KB_OPERATOR_ADDRESSES` pass, at all three checks. They are one person's own accounts, three at
most (section 3). Anyone else is refused first, whatever the list,
a group or an allowed domain would say: they see the message a person not on the list sees, and
the log line gives the reason `operator_only_test_mode`. The operator is then checked as anyone
is: Google must report the address verified, the account must be in an allowed domain when domains
are set, and the address must be on the list or in a group. The mode narrows who gets in and never
adds anyone. Section 4 says what the mode is for.

**A refresh in the test mode.** A client that holds a refresh token, from a sign-in before the
mode came on, asks the token endpoint (`/token`) for a new token when its old one runs out. In the
test mode the list is checked there too, on the token the refresh produced: anyone the list
refuses gets no token. The client gets the error OAuth defines for a grant that is no longer
valid, with HTTP status 401:

```json
{"error":"invalid_grant","error_description":"Access denied: <email> is not on this knowledge base's access list. Ask its administrator to add the address."}
```

The log says `refresh refused for <email>: operator_only_test_mode`. The refresh token is spent
by the attempt, so the grant is gone on the connector too: the person signs in again, and while
the mode is on that sign-in shows the same message on a page. The operator's own refresh is
checked as every request is. While the operator passes it gets a new token; while the operator
does not, it is refused with the reason the list gives (`email_not_listed`, `email_unverified`,
`domain_not_allowed`, `group_unchecked`, or `no_identity` when Google does not say whose the new
token is), and the operator signs in again.

Outside the test mode the token endpoint does not consult the list. A refresh is given to whoever
holds the refresh token, and the list is checked on every request with the new token (the second
check above), so a person removed from the list gets a token that every request refuses.

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
| `KB_PUBLIC_URL` | required | The service's origin and nothing more: `https://`, the host, and a port if it needs one, such as `https://kb.example.com`. A trailing `/` is accepted; a path, a query, a fragment or a user-info part stops the start, and so does a host written as a number in an old spelling, in either mode (below the tables). `http://` is accepted only for `localhost` (also written `localhost.`), `127.0.0.1` and `[::1]`. A temporary or local address starts only as the operator's own test (below the tables). |
| `KB_OPERATOR_TEST` | off | `1` turns on the operator-only test mode (section 4): only `KB_OPERATOR_ADDRESSES` can sign in, the start logs a line that begins `TEST ONLY`, and `/health` carries `"test_only": true`. Any value but `1`, `0` or none stops the start. |
| `KB_OPERATOR_ADDRESSES` | required with `KB_OPERATOR_TEST=1` | The operator's own email address, or up to three of that one person's own accounts, separated by commas. A fourth address stops the start (below the tables). Set while the mode is off, it stops the start, so a misspelled switch cannot leave the whole list admitted. |
| `KB_GOOGLE_CLIENT_ID` | required | The Google OAuth client's ID. |
| `KB_GOOGLE_CLIENT_SECRET` | required, secret | The Google OAuth client's secret. |
| `KB_ALLOWED_EMAILS` | required unless `KB_ALLOWED_GROUPS` is set | Comma-separated addresses that may read the knowledge base. |
| `KB_ALLOWED_GROUPS` | none | Comma-separated Google group addresses whose members may read it (section 7.2). |
| `KB_GROUP_REFRESH_SECONDS` | `300` | How often the groups are read again, 60 to 86400. |
| `KB_ALLOWED_HOSTED_DOMAINS` | none | Comma-separated Google Workspace domains; when set, accounts outside them are refused even if listed. |
| `KB_JWT_SIGNING_KEY` | derived from the client secret | Secret that signs the connector's own tokens. Set it so rotating the Google client secret does not sign everyone out. |
| `KB_OAUTH_STORE` | `firestore` is required outside the operator-only test mode; `memory` in it | `firestore` for any deployment: registrations, grants and Google tokens survive restarts and are shared by every instance. `memory` keeps them in the process, so every restart signs everyone out; it is allowed only in the test mode, where the start logs a warning that says so. Outside the test mode a start with `memory`, named or not, stops (below the tables). |
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
| `KB_LOG_LEVEL` | `INFO` | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR` or `CRITICAL`. The line that begins `TEST ONLY` is logged whatever the level. |

**An origin and nothing more.** `KB_PUBLIC_URL` is the origin the connector builds its own
addresses on: `/mcp` for the clients and `/auth/callback` for Google. It is the scheme, the host and
a port if it needs one. `https://kb.example.com`, `https://kb.example.com/`, `https://kb.example.com:8443`
and `HTTPS://KB.Example.COM` all start. A path other than `/`, a query, a fragment or a user-info
part (`user:password@`) stops the start, in either mode, and so does an empty query or fragment
(`https://kb.example.com/?`), since the address is read as written. The start prints which parts it
found and the address written correctly, then exits 2; `https://kb.example.com/mcp` prints:

```text
kb-connector: the connector cannot start:
  - KB_PUBLIC_URL must be an origin and nothing more: the scheme, the host and a port if it needs one, since the connector builds its own addresses (/mcp, /auth/callback) on it. It has a path, which is not allowed. Write it as https://kb.example.com
```

With more than one part it names each, in order: `It has a user-info part (user:password@), a path,
a query and a fragment, which are not allowed.` It names a part and never shows it, since a password
or a query can be a secret and the message is printed. The address it shows keeps `http://` only
for localhost and is `https://` otherwise. A port that is not a number from 1 to 65535, a colon
with no port after it, brackets that close no IPv6 address, and a host with a character no host has,
make a malformed address, with no address shown:
`KB_PUBLIC_URL must be the service's https:// address (http:// only for localhost)`. A host is an
IP address or a name of letters, digits, hyphens, underscores and dots, so a backslash
(`https://kb.example.com\mcp`, which a browser reads as a slash and so as a path), a semicolon, a
space or a `%` in it stops the start.

**An IP address in an old spelling.** A host written as a number in an old spelling, such as
`127.1`, `2130706433`, `0x08080808` or `010.8.8.8`, stops the start in either mode, whatever
address it denotes, public or not. Programs read such a spelling differently: one takes `010.8.8.8`
for `8.8.8.8`, another for `10.8.8.8`, and a third looks it up as a name. The start prints this,
with the host it read, and exits 2:

```text
kb-connector: the connector cannot start:
  - KB_PUBLIC_URL writes its host as a number in an old spelling (0x08080808): programs read such a spelling differently, as one IP address, as another or as a name to look up, so the connector refuses it whatever address it denotes. Write the host as a name: the service's domain, or localhost for the operator's own test
```

An IP address in its standard form (`8.8.8.8`, `[2606:4700:4700::1111]`) is not an old spelling,
and is judged by the next rule.

**Temporary addresses.** Outside the operator-only test mode the connector does not start when
`KB_PUBLIC_URL` names an address that lasts only as long as one machine or its tunnel:

- a tunnel service's own domain, or any host under it: `trycloudflare.com`, `ngrok.io`,
  `ngrok.app`, `ngrok.dev`, `ngrok.pizza`, `ngrok-free.app`, `ngrok-free.dev`, `ngrok-free.pizza`,
  `loca.lt`, `localtunnel.me`, `serveo.net`, `serveousercontent.com`, `localhost.run`, `lhr.life`,
  `lhr.rocks`, `pinggy.io`, `pinggy.link`, `pinggy-free.link`, `devtunnels.ms`,
  `app.github.dev`, `ts.net`, `tunnelmole.net`, `bore.pub` and `loophole.site`;
- any name under a wildcard-DNS service, `nip.io` or `sslip.io`, whatever address it carries: such a
  name is answered with the address written in it and belongs to no organization;
- `localhost`, and any name that ends in `.localhost` or `.local`;
- an IP address the internet cannot reach: loopback (`127.0.0.1`, `[::1]`), `0.0.0.0`, the private
  ranges (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `fc00::/7`), link-local addresses, the
  shared range `100.64.0.0/10` and the reserved ranges.

An IPv6 address that carries an IPv4 address is judged as the IPv4 address it carries: mapped
(`[::ffff:100.64.0.1]`), compatible (`[::100.64.0.1]`), NAT64's well-known prefix
(`[64:ff9b::100.64.0.1]`) and 6to4 (`[2002:6440:1::1]`) are all `100.64.0.1`, in the shared range,
and `[::ffff:8.8.8.8]` is `8.8.8.8`, a public address. The prefix for translation inside one
network, `64:ff9b:1::/48`, is temporary. The verdict is the same on every Python from 3.9 on;
Python's own verdicts on these forms differ from one version to the next.

The address is read as a host. `demo.trycloudflare.com` counts, and so does the same host in upper
case, with a port or with a trailing dot (`localhost.` is `localhost`); `nottrycloudflare.com` does
not, and a listed name in a path or a query (`https://kb.example.com/trycloudflare.com`) is refused
as a path or a query, not as a temporary address. The list is `TEMPORARY_HOSTS` in
`kb_connector/config.py`; the send guard keeps the same list (`TUNNELS` in `synthesis/guards.py`), and
a test holds the two equal. A tunnel service that is not on it is not caught, so add its domain to
both when one comes into use.

The start prints this, with the host it read, and exits 2:

```text
kb-connector: the connector cannot start:
  - KB_PUBLIC_URL names a temporary or local address (<host>): it lasts only while this machine and its tunnel stay up, so nobody else may depend on it. To serve other people, deploy the connector to the organization's own infrastructure at a permanent address; for the operator's own test, set KB_OPERATOR_TEST=1 and KB_OPERATOR_ADDRESSES to the operator's own email address
```

Those are the two ways forward: deploy it (section 5), or run the operator's own test (section 4).

**The sign-in store.** The memory store is allowed only in the operator-only test mode. Anything
other people use must keep its state across restarts: a restart on the memory store signs
everyone out, each person's client is refused and has to connect again, and a platform that stops
idle instances, as Cloud Run does, restarts often. With more than one instance a memory store
breaks sign-in outright, since each instance holds its own registrations, grants and tokens and
knows nothing of a sign-in another instance began. Outside the test mode `KB_OAUTH_STORE` has no
default, and a start with no store named, or with `KB_OAUTH_STORE=memory` named on purpose, prints
this and exits 2:

```text
kb-connector: the connector cannot start:
  - KB_OAUTH_STORE must be firestore, with KB_STORAGE_ENCRYPTION_KEY: anything other people use must keep its state across restarts, and with more than one instance a memory store breaks sign-in outright. A single person's use is what the operator-only test mode is for, and memory is allowed only there, with KB_OPERATOR_TEST=1
```

In the test mode `memory` is the default and may also be named, and every such start logs
`KB_OAUTH_STORE=memory: sign-ins live in this process only, so every restart signs everyone out`.
`firestore` serves in both modes and logs nothing about the store.

**The operator's addresses.** `KB_OPERATOR_ADDRESSES` names one person's own accounts, so it
takes three addresses at most. An address written twice, or again in other letter case, counts
once. A fourth prints this, with the number of addresses it read, and exits 2:

```text
kb-connector: the connector cannot start:
  - KB_OPERATOR_ADDRESSES names 4 addresses and may name three at most: they are one person's own accounts, since the operator-only test mode is that person's test and nobody else's. Other people come in through KB_ALLOWED_EMAILS or KB_ALLOWED_GROUPS, on a deployed connector with the mode off
```

The line that begins `TEST ONLY` names each address that can sign in.

## 4. Run it locally: the operator's own test

**A local run is the operator's own test, and nobody else's.** Its address is never given to
anyone. The moment anyone else is to use the connector, deploy it to the organization's own
infrastructure first (section 5), at a permanent address, and give people that address.

A local run stops when the laptop's lid closes, when the process or the app that started it
restarts, and when the tunnel in front of it drops. Each of those cuts off everyone who was using
it. A restart signs them all out, since a local run keeps sign-ins in memory, and a free tunnel's
address does not come back: the next tunnel gets a new one, so a person who was given the old one
holds a connector that no longer exists.

The connector holds to this itself. On a temporary or local address, and on the memory sign-in
store (section 3), it starts only in the operator-only test mode:

- `KB_OPERATOR_TEST=1` turns the mode on and `KB_OPERATOR_ADDRESSES` names the operator's own
  address, or up to three of that one person's own accounts. Either without the other stops the
  start, and so does a fourth address.
- Only the operator can sign in, only the operator's token works on any later request, and only
  the operator's client gets a new token when it refreshes, whatever `KB_ALLOWED_EMAILS`,
  `KB_ALLOWED_GROUPS` and `KB_ALLOWED_HOSTED_DOMAINS` would admit (section 2). The operator still
  has to be on the list or in a group, so the test also checks the access list as it stands.
- The start logs a line that begins `TEST ONLY`, and `/health` carries `"test_only": true`.

Use a virtual environment outside the plugin, with Python 3.12 or newer:

```bash
python3.12 -m venv ~/.venvs/kb-connector
~/.venvs/kb-connector/bin/pip install --require-hashes --no-deps -r <skill-root>/scripts/connector/requirements.txt
cd <skill-root>/scripts/connector
KB_SOURCE_DIR=<published-tree> KB_PUBLIC_URL=http://localhost:8080 \
KB_GOOGLE_CLIENT_ID=<id> KB_GOOGLE_CLIENT_SECRET=<secret> KB_ALLOWED_EMAILS=<you@example.com> \
KB_OPERATOR_TEST=1 KB_OPERATOR_ADDRESSES=<you@example.com> \
  ~/.venvs/kb-connector/bin/python -B -m kb_connector
```

It logs these two warnings, then `serving <n> documents from commit <sha>` and uvicorn's startup
lines:

```text
<time> WARNING kb_connector: TEST ONLY: operator-only test mode at http://localhost:8080. The address is temporary and must not be given to anyone: a restart of this process, this machine or its tunnel ends it. Only <you@example.com> can sign in. List each thing this test needs before setting it up, and remove every one as soon as the test ends.
<time> WARNING kb_connector: KB_OAUTH_STORE=memory: sign-ins live in this process only, so every restart signs everyone out
```

`-B` keeps Python from writing bytecode into the plugin folder. For Google sign-in to work
locally, add `http://localhost:8080/auth/callback` as an authorized redirect URI on the OAuth
client.

ChatGPT's and Claude's hosted apps cannot reach `localhost`. To try the connector from them, put a
tunnel in front of the local run, set `KB_PUBLIC_URL` to the tunnel's `https://` address and add
that address's `/auth/callback` to the OAuth client. It is the same test under the same mode: the
operator's alone, on an address that ends with the tunnel.

A test leaves nothing behind. Before each thing the test needs is set up, write it on a teardown
list with how it is removed: the address the connector serves on, the tunnel, the redirect URI
added to the OAuth client, a deploy key, and each client's config entry that points at the test
address. When the test ends, take each one down in the same sitting and take it off the list. The
`TEST ONLY` line ends with that instruction. With the synthesis-skills plugin installed, the list
is the guardrails skill's
([a test's teardown list](../../synthesis-agent-guardrails/references/teardown.md)), and
`synthesis doctor` warns while an item remains:

```bash
python3 <synthesis-agent-guardrails>/scripts/teardown.py add "<what was set up>" --remove "<how it is removed>" --test "<the test>"
```

The mode also runs on a deployed connector, to try a deployment before anyone on the list is told
about it. It admits only the operator there too, and the `TEST ONLY` line then says not to give
the address to anyone while the mode is on. Remove `KB_OPERATOR_TEST` and `KB_OPERATOR_ADDRESSES`
to open the deployment to the list. It then has to be on `firestore`: a deployment tried on the
memory store stops at its first start without the mode (section 3).

Turning the mode on over a deployment people already use ends their sign-ins. Each request is
refused, and a client that asks for a new token is told its grant is no longer valid (section 2),
so each of those people signs in again once the mode is off.

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
records under collections starting with `KB_FIRESTORE_COLLECTION_PREFIX`. Each record's document ID
is the SHA-256 hash of its key: ChatGPT and Codex identify themselves by a URL, and Firestore refuses
a "/" in a document ID, and the hash also keeps authorization codes and token IDs out of document
names. Expired records are ignored when read and stay until overwritten; their expiry is stored as
text, so a Firestore TTL policy cannot remove them.

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

The first prints the health JSON with the commit CI last published and `"test_only": false`. The
second prints
`www-authenticate: Bearer ... resource_metadata="https://.../.well-known/oauth-protected-resource/mcp"`,
which is how clients discover the sign-in.

## 6. Add it in ChatGPT and in Claude

The connector's address for both is `KB_PUBLIC_URL` followed by `/mcp`. Give people the address of
a deployed connector only (section 5), whose `/health` shows `"test_only": false`. A local run's
address is the operator's own and is never given to anyone (section 4).

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

**7.1 Addresses.** Edit `KB_ALLOWED_EMAILS` in the settings file and redeploy with the same command, or update the
one variable (gcloud's `^;^` prefix makes `;` the separator, so the commas stay inside the value):

```bash
gcloud run services update <service> --region <region> \
  --update-env-vars '^;^KB_ALLOWED_EMAILS=first.person@<domain>,second.person@<domain>'
```

The new revision serves the next request. A removed person's existing token stops working on
their next request; an added person can sign in at once.

**7.2 A Google group the organization's IT manages.** People are then added and removed in Google
Admin or Google Groups, with no change to the connector.

1. Create the group, for example `knowledge-readers@<domain>`, and add the people.
2. Turn on the Cloud Identity API in `<project>`:
   `gcloud services enable cloudidentity.googleapis.com --project <project>`.
3. Let the service's service account (5.8) read groups. A super administrator, in the Google Admin
   console under Account > Admin roles, creates a custom role holding only the Admin API privilege
   Groups > Read, opens it, chooses Assign admin > Assign service accounts, and enters the service
   account's email. Google's Groups API setup guide documents the prebuilt Groups Admin role for
   this, which can also change groups; use it only if the start in step 5 reports a 403 with the
   custom role.
4. Set `KB_ALLOWED_GROUPS` to the group's address in the settings file (several are separated by
   commas). `KB_ALLOWED_EMAILS` may stay, for example for the administrator, or be left empty.
5. Redeploy with the command in 5.11. The start reads the group first and stops with
   `the access groups could not be read: ...` if it cannot, so a running revision proves the grant;
   `/health` then shows `access_groups` with `"status": "ok"`.

## 8. Operate it

The running connector (`python -B -m kb_connector` from `scripts/connector/`) prints
`serving <n> documents from commit <sha>` when a copy loads, `refresh failed (...)` when a refresh
fails, and `sign-in allowed for <email>` or `sign-in refused for <email>: <reason>` per sign-in. If
its settings are wrong it prints `kb-connector: the connector cannot start:` and every problem,
then exits 2; outside the test mode a temporary address and the memory sign-in store are two of
those problems, and in either mode an address that is more than an origin and a host in an old
numeric spelling are two more (section 3). If the first load fails it prints
`kb-connector: the first load failed: <reason>` and exits 1.

- **Is it current?** `/health` shows the served commit. Compare it with the published repository's
  head. `last_refresh_failed: true` means the last check, clone or load failed and the last good
  copy is still served; the log line `refresh failed (last good copy kept): ...` says why.
- **Is it a test?** `/health` shows `"test_only": true` while the operator-only test mode is on,
  and every start in the mode logs a line that begins `TEST ONLY`, naming the address and who can
  sign in. A connector other people use shows `false`. With the mode on, everyone but the operator
  is refused, with `sign-in refused for <email>: operator_only_test_mode`,
  `token refused for <email>: operator_only_test_mode` or
  `refresh refused for <email>: operator_only_test_mode` in the log.
- **Memory store:** only the operator's own test runs on it. A start in the test mode with
  `KB_OAUTH_STORE=memory`, or with no store named, logs
  `KB_OAUTH_STORE=memory: sign-ins live in this process only, so every restart signs everyone out`.
  Outside the mode the same start stops (section 3).
- **A deployment set up under version 1.1.0 of this skill or earlier** does not start under this
  version in these cases, each with the refusal section 3 shows. Change the setting first, then
  deploy the new version:
  - `KB_OAUTH_STORE` is `memory`, or is not set, which then meant `memory`: set
    `KB_OAUTH_STORE=firestore` and `KB_STORAGE_ENCRYPTION_KEY`, with the database and the role
    they need (5.4, 5.7, 5.8 and 5.10). Everyone signs in once more, because the sign-ins the
    memory store held ended with its process.
  - `KB_PUBLIC_URL` is a temporary or local address: deploy the connector at a permanent address
    (section 5), and give people that address in place of the old one.
  - `KB_PUBLIC_URL` has a path, a query, a fragment or a user-info part: set it to the origin the
    refusal shows. The connector is served at the root of its own origin, so a deployment reached
    through a path on a shared host moves to a host of its own; when the address changes, add the
    new `/auth/callback` to the OAuth client (5.3) and give each person the new origin followed by
    `/mcp` (section 6).
  - `KB_PUBLIC_URL` writes its host as a number in an old spelling: write it as the host's name.
- **Groups:** with `KB_ALLOWED_GROUPS` set, `/health` also reports `access_groups`: its `status`
  (`ok`, or `stale` once the membership is older than three intervals, which also makes `/health`
  answer 503), when it was last read, and whether the last read failed.
- **Log lines worth alerting on:** `access group refresh failed`, `refresh failed`, `sign-in refused for <email>: <reason>`,
  `token refused for <email>: <reason>`, `refresh refused for <email>: <reason>` and
  `sign-in check failed`. The first two mean the access groups or the content are going stale;
  the others show who was refused. On a deployed connector, alert on `TEST ONLY` as well: it means
  only the operator can get in. `KB_OAUTH_STORE=memory` is logged only beside it, in the test
  mode, and means the next restart signs the operator out.
- **Rotate a secret:** add a new version in Secret Manager and redeploy (or update the service) so
  a new revision reads it. Rotating `KB_JWT_SIGNING_KEY` or `KB_STORAGE_ENCRYPTION_KEY` signs
  everyone out; they sign in again on their next use.
- **Rotate the deploy key:** add the new public key to the repository, store the new private key as
  a new secret version, redeploy, then remove the old deploy key from the repository.
- **Upgrade FastMCP:** change `requirements.in`, regenerate `requirements.txt` with the command in
  its header, and run the connector's tests with the new lock installed. The sign-in check reads
  two private attributes of FastMCP's OAuth proxy (`_code_store`, `_token_validator`); if an
  upgrade moves them, the sign-in check fails closed and `test_kb_connector_server.py` fails.
  The test mode's refresh check stands on the provider's own methods: it wraps
  `exchange_refresh_token`, which the token endpoint calls for a refresh grant, reads the new
  token through `load_access_token`, and refuses by raising the SDK's `TokenError`. The same tests
  fail if an upgrade changes how the token endpoint calls them or what it answers.
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
- It does not serve other people from a temporary address. There it starts only as the operator's
  own test, which admits the operator alone (sections 3 and 4).

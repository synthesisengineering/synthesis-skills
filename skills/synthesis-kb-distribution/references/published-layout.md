# The published tree and the publishing step

Contents:

1. Why one published tree
2. The tree
3. A published knowledge file
4. Building it: the script, its config and templates
5. What the build checks
6. Publishing it: the script and the CI step at a pinned release
7. Giving the plugin to the organization
8. A Drive copy for Gemini Notebook

## 1. Why one published tree

The knowledge base lives as OKF markdown (each file with YAML front matter holding at least
`type`, usually `title`, `description` and a date field) in its own repository, under `source/`.
A build step (`scripts/build_plugin.py`, section 4) turns it into one published tree in a separate,
private repository. Two channels read that tree and nothing else:

- the **organization plugin**, which Claude and ChatGPT workspace administrators make available to
  people inside the organization;
- the **connector** (references/connector.md), which serves the same files to people outside those
  workspaces.

Because both read the same commit of the same tree, an answer given through either one can be
traced to the same source commit, and a file left out of the build is left out of both.

## 2. The tree

```text
.claude-plugin/marketplace.json           the marketplace both products read
.agents/plugins/marketplace.json          the same plugin in OpenAI's native marketplace format
README.md                                 what the repository is and that it is generated
plugins/<plugin>/
  .claude-plugin/plugin.json              name, version, description, author
  .codex-plugin/plugin.json               the same, plus "skills": "./skills/" and display text
  plugin.json                             the same manifest at the plugin root
  skills/<plugin>/SKILL.md                the index: front matter, then every file by section
  skills/<plugin>/references/<path>.md    one file per knowledge-base file, at its path under source/
```

- `<plugin>` is the plugin's name, used for both folders; the skill's `name` in `SKILL.md` must
  equal its folder's name.
- `.claude-plugin/marketplace.json` names the marketplace and its owner, then lists the plugin
  with `"source": "./plugins/<plugin>"`, its description and version.
- `.agents/plugins/marketplace.json` lists the same plugin with
  `"source": {"source": "local", "path": "./plugins/<plugin>"}` and an installation and
  authentication policy.
- The version comes from the config's format, by default `1.{date}.{time}`: the source commit's
  date and time in UTC, as `1.<YYYYMMDD>.<HHMM>`, so every publication sorts after the one before
  it and a time zone never steps it back (section 4).
- `SKILL.md` is the index a model reads first. Its description says what the knowledge base covers
  and when to use it. Its body lists each file as a link (`references/<path>.md`) with its title,
  last-updated date and description, grouped into sections by folder.

The connector needs only `plugins/<plugin>/skills/<plugin>/references/`. When the tree holds more
than one plugin, `KB_REFERENCES_PATH` names the folder to serve.

## 3. A published knowledge file

Each `references/<path>.md` is the source file's front matter, unchanged, then a provenance stamp
as the first line after it, then the source body:

```markdown
---
type: Decision
title: Pricing decision for 2027
description: The decision to move plans to per-seat pricing in 2027.
timestamp: 2026-10-12
---

> Published from `source/datasets/active/pricing-decision.md` in <org>/<kb-repo> at commit `abc1234` (2026-11-01).

# Pricing decision for 2027
...
```

The stamp's exact form is
``> Published from `source/<rel>` in <repo> at commit `<sha7>` (<date>).``, where `source/<rel>` is
the file's path in the source repository (the source folder's own name, whatever it is), `<repo>`
the config's `source_repository`, `<sha7>` the short source commit and `<date>` that commit's date
in UTC. The connector parses it into `source_path`, `source_repository`, `source_commit` and
`published` in `fetch`'s metadata, and `KB_DOCUMENT_URL_TEMPLATE` can build a citation address from
`{source_path}` and `{commit}`. A file without the stamp is still served, with those fields empty.

## 4. Building it: the script, its config and templates

`scripts/build_plugin.py` builds the tree with the Python standard library (3.9 or newer), so a CI
image needs nothing installed:

```bash
python3 <synthesis-skills>/skills/synthesis-kb-distribution/scripts/build_plugin.py \
  --config distribution/kb-plugin.json --source source --out build/kb-plugin [--commit <sha>]
```

It prints `Built <plugin> <version> from <sha7> (<date>) into <out>`, the knowledge-file count and
the plugin's size, then `left out <path>  (<glob>)` for each excluded file and
`note: the exclusion '<glob>' matched no file` for a glob that matched nothing, which is often a
misspelled folder. It exits 1 on any refusal in section 5, having written nothing, and 2 on a usage
error. `--commit` defaults to `HEAD`.

Everything organization-specific lives in the knowledge base's own repository: the config (JSON),
the exclusion list it names and, optionally, the organization's own templates. Start from
`templates/kb-plugin.example.json` and `templates/exclude.example.txt` in this skill. Paths in the
config are relative to the config file. A setting the build does not know is refused, so a
misspelled one cannot fall back to a default unnoticed.

| Setting | Required | What it sets |
|---|---|---|
| `source_repository` | yes | The repository label in every stamp and in the README, such as `<org>/<kb-repo>`. |
| `exclude_file` | yes | The exclusion list: one glob per line, relative to the source folder. `*` and `?` stay inside one folder name, `**` crosses folders, `**/` also matches no folder, and `#` starts a comment. |
| `marketplace.name` | yes | The marketplace's name: lowercase letters, digits and hyphens. |
| `marketplace.display_name`, `.owner`, `.description` | no | Default to the plugin's author, its author and its description. |
| `plugin.name` | yes | The plugin's and the skill's name: lowercase letters, digits and hyphens, at most 64 characters. |
| `plugin.display_name`, `.description`, `.author` | yes | The display name, the one-line description in every manifest, and the author. |
| `plugin.skill_description` | yes | The skill's description, which tells an assistant when to use the knowledge. |
| `plugin.developer` | no | The developer name Codex shows; defaults to the author. |
| `plugin.category`, `.policy` | no | The OpenAI marketplace entry's category (default `Productivity`) and policy (default `{"installation": "AVAILABLE", "authentication": "ON_INSTALL"}`). |
| `version` | no | `MAJOR.MINOR.PATCH` built from `{date}` (YYYYMMDD), `{time}` (HHMM without a leading zero) and `{count}` (commits in the history, so it needs a full clone), all from the source commit; default `1.{date}.{time}`. A fixed version such as `2.0.0` never changes, so the products may not notice a new publication. |
| `templates.skill`, `templates.readme` | no | The organization's own SKILL.md and README.md templates; the generic ones in `templates/` otherwise. |
| `template_values` | no | Extra `UPPER_CASE` placeholders for the organization's templates. |
| `corrections_contact` | no | Whom readers send corrections to, in the generic SKILL.md template. |
| `index.sections` | no | `[{"prefix": "decisions/", "heading": "Decisions"}, ...]`: each file goes under the first prefix it starts with; without sections, under its top-level folder. |
| `index.other_heading`, `index.date_field` | no | The heading for files no section takes (default `Other`) and the front-matter field shown as the updated date (default `timestamp`). |
| `lint.patterns`, `lint.extra_patterns` | no | Case-insensitive regular expressions for text addressed to an assistant: `patterns` replaces the defaults, `extra_patterns` adds to them. An empty set is refused. |
| `limits.max_files`, `.max_bytes`, `.max_skill_description` | no | Default 5,000 files and 200 MiB for the plugin and 1,024 characters for the skill description; check each product's current documentation. |

A template fills `{{NAME}}` with a value; `{{NAME|quoted}}` writes it as a double-quoted YAML string,
for front matter. The built-in values are `PLUGIN_NAME`, `DISPLAY_NAME`, `PLUGIN_DESCRIPTION`,
`SKILL_DESCRIPTION`, `AUTHOR`, `SOURCE_REPO`, `SOURCE_PATH` (the source folder in its repository),
`COMMIT`, `COMMIT_SHORT`, `COMMIT_DATE`, `VERSION`, `FILE_COUNT`, `EXCLUDE_FILE` (the exclusion list
in its repository), `CORRECTIONS_CONTACT` and `INDEX` (the file list). Values are filled in one pass,
so a title that contains braces is never read as a placeholder.

## 5. What the build checks

A build that publishes to every assistant in the organization should stop, rather than publish,
when any of these fail. `build_plugin.py` checks all of them before it writes anything and lists
every problem at once:

- **Front matter.** Every included file has front matter with a non-empty `type` (OKF's hard rule;
  `synthesis-okf`'s validator checks the whole bundle). The build reads front matter with the
  plugin's one YAML reader, the one the connector uses, so a block it cannot read stops the build
  instead of reaching readers with no fields.
- **Exclusions.** An exclusion list of globs relative to `source/` keeps drafts, private notes and
  anything not meant for every reader out of the tree; the build prints each file it left out and
  the glob that matched. `README.md` and hidden paths are never published.
- **Links and encoding.** A symbolic link is never followed: a linked file that would be published
  stops the build, since it could point at a key on the build machine, and a linked folder is left
  out and reported. A file that is not UTF-8 text stops the build.
- **Text addressed to an assistant.** Knowledge files describe the organization. A line that
  addresses an AI assistant instead (for example "ignore previous instructions", "you are an AI
  assistant", "system prompt", "do not tell the user") would be read by every assistant that loads
  the plugin or calls the connector, so the build stops and a person decides. The config's `lint`
  replaces or extends those patterns, for instance where the organization's own products make
  "system prompt" an ordinary phrase; it cannot remove them all.
- **The commit.** The stamps name one commit, so the source folder must hold exactly that commit's
  content: a file changed or deleted since that commit, or one that would be published but is not
  in it, stops the build.
- **Size.** The plugin stays inside the products' current limits on file count, total size and the
  skill description's length; check each product's documentation for the current numbers.
- **Output folder.** The build writes only to a dedicated output folder and refuses to clear any
  folder that is not a previous build's output: one holding only the build's own top-level entries
  and its `.claude-plugin/marketplace.json`. It never uses the source folder or anything inside it,
  the repository or a folder above it, `.git` or the home folder.
- **Placeholders.** Templates for `SKILL.md` and `README.md` leave no placeholder unfilled, and the
  rendered `SKILL.md` has the plugin's name and a non-empty description within the limit.

## 6. Publishing it: the script and the CI step at a pinned release

`scripts/publish_plugin.sh` (POSIX sh) runs the build into a private temporary folder, clones the
published repository, replaces everything in it but `.git` with the build, and pushes one commit,
`Publish <plugin> <version> from <sha7>`, made by a bot identity. When the build matches what is
already published it pushes nothing.

```bash
KB_PUBLISH_REPO=<published repository URL> KB_PUBLISH_KNOWN_HOSTS="<pinned host key line>" \
  sh <synthesis-skills>/skills/synthesis-kb-distribution/scripts/publish_plugin.sh \
  --config distribution/kb-plugin.json --source source --commit "<source commit>"
```

| Variable | What it sets |
|---|---|
| `KB_PUBLISH_REPO` | The published repository's git URL. Required; nothing defaults to any host. |
| `KB_PUBLISH_BRANCH` | The branch to publish; default `main`. A new repository or branch is created by the first push. |
| `KB_PUBLISH_KNOWN_HOSTS` | The git host's known_hosts line or lines, checked against the host's published fingerprints. Required for an SSH URL, and the only keys the push trusts: ssh reads no user or system known_hosts file and refuses any other key. |
| `KB_PUBLISH_SSH_KEY_FILE` | A private key for the push; otherwise ssh's agent or configuration supplies one. |
| `KB_PUBLISH_BOT_NAME`, `KB_PUBLISH_BOT_EMAIL` | The commit's author; default `kb-publish[bot]` and `kb-publish@users.noreply.invalid`. |
| `PYTHON` | The interpreter for the build; default `python3`. |

It prints the build's report, then `Published <plugin> <version> to <repository> (<branch>).` or
`The published copy already matches this build; nothing to push.` It exits 1 on any failure,
checking its settings before it builds, and 2 on a usage error. A credential embedded in an https
URL is never printed.

1. On every merge to the knowledge base's default branch that changes the source folder, the
   config, the exclusion list or the templates, CI runs the build from a clean checkout of that
   commit, with the commit passed in so every stamp names it. CI fetches this skill at a pinned
   release and checks the commit the tag resolves to, because the step runs where the write key
   is and a moved tag must not change what runs there:

   ```bash
   git clone --quiet --depth 1 --branch "$SYNTHESIS_SKILLS_TAG" \
     https://github.com/synthesisengineering/synthesis-skills.git "$TMP/synthesis-skills"
   test "$(git -C "$TMP/synthesis-skills" rev-parse HEAD)" = "$SYNTHESIS_SKILLS_COMMIT"
   sh "$TMP/synthesis-skills/skills/synthesis-kb-distribution/scripts/publish_plugin.sh" \
     --config distribution/kb-plugin.json --source source --commit "$CI_COMMIT"
   ```

   Both pins live in the pipeline file, so moving to a newer release is a reviewed change. CI
   clones are often shallow; a version format with `{count}` needs the full history.
2. CI pushes the built tree to the private published repository as one commit whose message names
   the source commit. It authenticates with a deploy key that has write access to the published
   repository only, stored in the CI system's secrets.
3. The connector, holding a different, read-only deploy key, sees the new head within
   `KB_REFRESH_SECONDS` and serves it once it loads. Its `/health` shows the served commit.
4. The organization plugin updates when each product syncs the published repository.

Keep the published repository private: it holds every published file in plain text.

## 7. Giving the plugin to the organization

The organization's Claude and ChatGPT administrators add the published repository as an
organization plugin marketplace and make the plugin available to the groups that should have it.
The products' admin consoles change; follow each product's current administrator documentation for
the exact steps and for how the repository is authorized. People outside those workspaces use the
connector instead.

## 8. A Drive copy for Gemini Notebook

An organization on Gemini for Google Workspace, which cannot add a custom connector, can still ask
Gemini about its knowledge base: a Gemini Notebook made from a Drive folder holding the published
Markdown answers from those files and cites them. A notebook re-reads a Drive file by itself when
the file's content changes, so CI keeps the folder current by replacing each changed file in place.
A notebook does not pick up a new file or drop a removed one by itself; someone who owns the
notebook adds or removes that source, and the step's log names each one.

`scripts/publish_drive.py` (Python 3.9 or newer, standard library only) reads the tree the build
wrote and brings one Drive folder in line with it:

- `SKILL.md` goes in as `<plugin>-index.md`, each `references/**/*.md` under its own file name,
  all in one flat folder. Two published files with the same name stop the run, as do two Drive
  files with one name; nothing is written first.
- A file whose content is unchanged (Drive's MD5 checksum) is left alone; a changed one has its
  content replaced, keeping its Drive ID; a new one is added as `text/markdown`; a `.md` file the
  build no longer has is moved to Drive's trash. Files with other names and subfolders are left
  alone.
- `--dry-run` lists the changes and writes nothing. The log ends with
  `Drive copy of <plugin> <version>: N added, N updated, N moved to trash, N unchanged.`; it exits 1
  on any failure and 2 on a usage error.

```bash
python3 <skill>/scripts/build_plugin.py --config distribution/kb-plugin.json --source source --out "$TMP/tree" --commit "$CI_COMMIT"
KB_DRIVE_FOLDER_ID=<folder ID> KB_DRIVE_OIDC_TOKEN="$BITBUCKET_STEP_OIDC_TOKEN" \
KB_DRIVE_WIF_PROVIDER=//iam.googleapis.com/projects/<number>/locations/global/workloadIdentityPools/<pool>/providers/<provider> \
KB_DRIVE_SERVICE_ACCOUNT=<account>@<project>.iam.gserviceaccount.com \
  python3 <skill>/scripts/publish_drive.py --tree "$TMP/tree"
```

| Variable | What it sets |
|---|---|
| `KB_DRIVE_FOLDER_ID` | The Drive folder the files go in, usually in a shared drive. Required. |
| `KB_DRIVE_ACCESS_TOKEN` | An access token with the Drive scope, for a run by a person. When it is set, the next three are not used. |
| `KB_DRIVE_OIDC_TOKEN` | The CI step's OIDC token. Bitbucket Pipelines issues one to a step with `oidc: true`, in `$BITBUCKET_STEP_OIDC_TOKEN`. |
| `KB_DRIVE_WIF_PROVIDER` | The workload identity provider's full name, starting `//iam.googleapis.com/projects/<number>/`. |
| `KB_DRIVE_SERVICE_ACCOUNT` | The service account whose hour-long token writes to Drive. |

**Keyless sign-in from CI.** The step stores no Google key. It exchanges the CI step's OIDC token at
Google's Security Token Service through a workload identity provider that accepts only the knowledge
base repository's default branch, then asks for an hour-long token of a service account that can
write to the shared drive. None of the three values is a secret. An administrator of the Google Cloud
project sets it up once (Bitbucket shown; the provider's issuer, audience and claims differ for
other CI systems):

1. In Bitbucket, Repository settings > Pipelines > OpenID Connect shows the **Identity provider URL**
   and **Audience** to copy. The token carries `repositoryUuid` and `branchName` among its claims
   (the issuer's `.well-known/openid-configuration` lists them); the repository's UUID is under
   that page's unique identifiers.
2. In the project (the APIs, a service account, a pool, a provider that accepts only that repository's
   default branch, and the right to use the account, given to identities from that pool only):

   ```bash
   gcloud services enable iam.googleapis.com iamcredentials.googleapis.com sts.googleapis.com drive.googleapis.com --project=<project>
   gcloud iam service-accounts create kb-drive-copy --project=<project> --display-name="Knowledge base Drive copy"
   gcloud iam workload-identity-pools create kb-ci --project=<project> --location=global --display-name="Knowledge base CI"
   gcloud iam workload-identity-pools providers create-oidc bitbucket --project=<project> --location=global \
     --workload-identity-pool=kb-ci --issuer-uri="<Identity provider URL>" --allowed-audiences="<Audience>" \
     --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repositoryUuid,attribute.branch=assertion.branchName" \
     --attribute-condition="assertion.repositoryUuid == '<repository UUID, exactly as that page shows it>' && assertion.branchName == 'main'"
   gcloud iam service-accounts add-iam-policy-binding kb-drive-copy@<project>.iam.gserviceaccount.com --project=<project> \
     --role=roles/iam.workloadIdentityUser \
     --member="principalSet://iam.googleapis.com/projects/<project number>/locations/global/workloadIdentityPools/kb-ci/*"
   ```

   The pool serves this step alone, so the provider's condition is what limits who can use the
   account: a pipeline on any other repository or branch is refused at the exchange.
3. In Drive, add `kb-drive-copy@<project>.iam.gserviceaccount.com` to the shared drive as a
   **Content manager**, the role that can replace and trash files. If the shared drive refuses an
   address outside the organization, a Workspace administrator allows it for that drive.
4. In CI, run the step after the publication with OIDC turned on (`oidc: true` on a Bitbucket step)
   and the four variables set.

**The notebook.** Make it from the folder's files (Gemini Notebook > New notebook > Add sources >
Drive, open the folder, select every file). Readers need two things: the notebook shared with them,
and read access to the source files, so the people or group who should read it go on the shared
drive as Viewers as well. Shared notebooks do not show in the Gemini app's list of notebooks, so give
readers the notebook's link.

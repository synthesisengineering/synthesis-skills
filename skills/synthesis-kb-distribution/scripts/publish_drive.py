#!/usr/bin/env python3
"""Keep a Google Drive folder's copy of a built knowledge-base plugin current, for Gemini Notebook.

    python3 publish_drive.py --tree <folder> [--dry-run]

Reads the tree build_plugin.py writes (references/published-layout.md): the plugin's SKILL.md, copied
as `<plugin>-index.md`, and every references/**/*.md under its own name. A notebook made from the
folder's files re-reads a changed file by itself, so each changed file is replaced in place, keeping
its Drive ID; a new file is added, and a .md file the build no longer has goes to Drive's trash. Both
are listed, since a notebook's sources are added and removed by hand. Other files and subfolders are
left alone. Two published files with one name, or two Drive files with one name, stop the run before
anything is written.

Environment:
  KB_DRIVE_FOLDER_ID        the folder the files go in, usually in a shared drive (required)
  KB_DRIVE_ACCESS_TOKEN     an access token with the Drive scope, for a run by a person; otherwise
  KB_DRIVE_OIDC_TOKEN       the CI step's OIDC token (Bitbucket Pipelines: $BITBUCKET_STEP_OIDC_TOKEN),
  KB_DRIVE_WIF_PROVIDER     exchanged at Google's Security Token Service through this workload identity
                            provider (//iam.googleapis.com/projects/<number>/locations/global/
                            workloadIdentityPools/<pool>/providers/<provider>)
  KB_DRIVE_SERVICE_ACCOUNT  for an hour's token of this service account, a Content manager of the
                            shared drive. No key is stored anywhere.

Prints each change, then `Drive copy of <plugin> <version>: N added, N updated, N moved to trash,
N unchanged.` Exit 1 on any failure, 2 on a usage error. Standard library only, Python 3.9 or newer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

FILES = "https://www.googleapis.com/drive/v3/files"
UPLOAD = "https://www.googleapis.com/upload/drive/v3/files"
SHARED = "supportsAllDrives=true"


class Refused(Exception):
    """A problem that stops the run."""


def call(method: str, url: str, token: str = "", body=None, content_type: str = "application/json") -> dict:
    """One HTTPS request: its JSON reply, or Refused naming the status and the start of the reply."""
    data = body if body is None or isinstance(body, bytes) else json.dumps(body).encode()
    request = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        request.add_header("Content-Type", content_type)
    if token:
        request.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            text = response.read().decode()
    except urllib.error.HTTPError as error:
        reply = error.read().decode(errors="replace")[:300]
        raise Refused(f"{method} {url.split('?')[0]} answered {error.code}: {reply}") from None
    except OSError as error:
        raise Refused(f"{method} {url.split('?')[0]} failed: {error}") from None
    return json.loads(text) if text else {}


def access_token(env, call=call) -> str:
    """A Drive token: the one given, or the CI step's OIDC token exchanged for the service account's."""
    if env.get("KB_DRIVE_ACCESS_TOKEN"):
        return env["KB_DRIVE_ACCESS_TOKEN"]
    names = ("KB_DRIVE_OIDC_TOKEN", "KB_DRIVE_WIF_PROVIDER", "KB_DRIVE_SERVICE_ACCOUNT")
    missing = [name for name in names if not env.get(name)]
    if missing:
        raise Refused("set KB_DRIVE_ACCESS_TOKEN, or " + ", ".join(missing) + " for the exchange in CI")
    provider = env["KB_DRIVE_WIF_PROVIDER"]
    if not provider.startswith("//iam.googleapis.com/projects/"):
        raise Refused("KB_DRIVE_WIF_PROVIDER must be the provider's full name, starting //iam.googleapis.com/projects/")
    form = urllib.parse.urlencode({
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange", "audience": provider,
        "scope": "https://www.googleapis.com/auth/cloud-platform",
        "requested_token_type": "urn:ietf:params:oauth:token-type:access_token",
        "subject_token": env["KB_DRIVE_OIDC_TOKEN"], "subject_token_type": "urn:ietf:params:oauth:token-type:jwt"})
    federated = call("POST", "https://sts.googleapis.com/v1/token", "", form.encode(),
                     "application/x-www-form-urlencoded").get("access_token")
    if not federated:
        raise Refused("the Security Token Service answered without an access token")
    account = urllib.parse.quote(env["KB_DRIVE_SERVICE_ACCOUNT"], safe="@")
    token = call("POST", f"https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/{account}"
                 ":generateAccessToken", federated, {"scope": ["https://www.googleapis.com/auth/drive"]}).get("accessToken")
    if not token:
        raise Refused(f"{env['KB_DRIVE_SERVICE_ACCOUNT']} gave no access token")
    return token


def published_files(tree: Path):
    """The plugin's name and version, and name -> path for its index and each knowledge file."""
    skills = sorted(tree.glob("plugins/*/skills/*/SKILL.md"))
    if len(skills) != 1:
        raise Refused(f"{tree} holds {len(skills)} plugin skills, not one: give the folder build_plugin.py wrote")
    skill = skills[0].parent
    plugin = skill.parent.parent
    version = json.loads((plugin / "plugin.json").read_text(encoding="utf-8")).get("version", "")
    files = {f"{skill.name}-index.md": skills[0]}
    for path in sorted((skill / "references").rglob("*.md")):
        if any(part.startswith(".") for part in path.relative_to(skill).parts):
            continue  # what the connector leaves out, this leaves out
        if path.name in files:
            raise Refused(f"two published files are named {path.name}, and a Drive folder holds one of each name")
        files[path.name] = path
    return plugin.name, version, files


def drive_files(folder: str, token: str, call=call) -> dict:
    """name -> (ID, MD5) for each file directly in the folder and not in the trash."""
    query = urllib.parse.urlencode({"q": f"'{folder}' in parents and trashed = false", "pageSize": 1000,
                                    "fields": "nextPageToken,files(id,name,md5Checksum,mimeType)",
                                    "supportsAllDrives": "true", "includeItemsFromAllDrives": "true"})
    found, page = {}, ""
    while True:
        reply = call("GET", f"{FILES}?{query}" + (f"&pageToken={urllib.parse.quote(page)}" if page else ""), token)
        for item in reply.get("files", []):
            if item.get("mimeType") == "application/vnd.google-apps.folder":
                continue
            if item["name"] in found:
                raise Refused(f"the Drive folder holds two files named {item['name']}: remove one, then run again")
            found[item["name"]] = (item["id"], item.get("md5Checksum", ""))
        page = reply.get("nextPageToken", "")
        if not page:
            return found


def upload(token: str, name: str, content: bytes, file_id: str = "", folder: str = "", call=call) -> dict:
    """Replace a file's content in place, keeping its ID, or add it to the folder."""
    if file_id:
        return call("PATCH", f"{UPLOAD}/{file_id}?uploadType=media&{SHARED}", token, content, "text/markdown")
    boundary = uuid.uuid4().hex
    meta = json.dumps({"name": name, "parents": [folder], "mimeType": "text/markdown"})
    body = (f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{meta}\r\n--{boundary}\r\n"
            "Content-Type: text/markdown\r\n\r\n").encode() + content + f"\r\n--{boundary}--\r\n".encode()
    return call("POST", f"{UPLOAD}?uploadType=multipart&{SHARED}", token, body, f"multipart/related; boundary={boundary}")


def sync(tree: Path, folder: str, token: str, dry_run: bool = False, out=print, call=call) -> dict:
    """Bring the folder in line with the tree; the counts of what changed."""
    plugin, version, files = published_files(tree)
    present = drive_files(folder, token, call)
    counts = dict.fromkeys(("added", "updated", "moved to trash", "unchanged"), 0)
    for name, path in files.items():
        content = path.read_bytes()
        file_id, md5 = present.get(name, ("", ""))
        if file_id and md5 == hashlib.md5(content, usedforsecurity=False).hexdigest():
            counts["unchanged"] += 1
            continue
        kind = "updated" if file_id else "added"
        out(f"{kind}: {name}")
        if not dry_run:
            upload(token, name, content, file_id, folder, call)
        counts[kind] += 1
    for name, (file_id, _) in sorted(present.items()):
        if name.endswith(".md") and name not in files:
            out(f"moved to trash: {name}")
            if not dry_run:
                call("PATCH", f"{FILES}/{file_id}?{SHARED}", token, {"trashed": True})
            counts["moved to trash"] += 1
    if counts["added"] or counts["moved to trash"]:
        out("A notebook made from this folder needs the added files added as sources and the trashed ones removed.")
    note = " (dry run: nothing written)" if dry_run else ""
    out(f"Drive copy of {plugin} {version}{note}: " + ", ".join(f"{n} {kind}" for kind, n in counts.items()) + ".")
    return counts


def main(argv=None, env=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--tree", required=True, type=Path, help="the folder build_plugin.py wrote")
    parser.add_argument("--dry-run", action="store_true", help="list the changes without writing them")
    args = parser.parse_args(argv)
    env = os.environ if env is None else env
    folder = env.get("KB_DRIVE_FOLDER_ID", "")
    try:
        if not re.fullmatch(r"[\w-]+", folder):
            raise Refused("KB_DRIVE_FOLDER_ID must be the Drive folder's ID (letters, digits, - and _)")
        published_files(args.tree)  # a bad tree is refused before any credential is used
        sync(args.tree, folder, access_token(env), args.dry_run)
    except (Refused, OSError, ValueError) as error:
        print(f"publish_drive: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

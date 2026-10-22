#!/usr/bin/env python3
"""Publish a filed action sheet to a private Cloudflare Pages host behind Cloudflare Access.

An optional adapter: the sheet works without it, as the filed local page (and, in Claude Code,
a private Artifact). This script never reads the page on disk as content. It rebuilds the page
from the filed spec beside it, so only the generator's output can be uploaded, and it uploads
only when a request with no sign-in to the host, and to a subdomain no deployment has, is
redirected to a Cloudflare Access sign-in. After the upload it checks the new deployment's own
address the same way. wrangler does the upload with its own sign-in; this script reads no
credential.

  publish_sheet.py PROJECT/resources/artifacts/<date>-<slug>.html --project NAME [--branch main]

Prints `published <deployment address>` and `latest <host address>`. A refusal prints
`will not publish:` and the reason, exit 2, before anything is uploaded. A deployment whose
address does not ask for a sign-in exits 3 and says to delete it. A failed or unfinished upload
prints `upload failed:` and exits 4.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import secrets
import shutil
import ssl
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request

sys.dont_write_bytecode = True  # an installed plugin must stay byte-identical; Muse verifies its bundle
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_sheet as bs  # noqa: E402

PROJECT = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,56}[a-z0-9])?")
REDIRECTS = {301, 302, 303, 307, 308}
SYSTEM_CA_FILES = ("/etc/ssl/cert.pem", "/etc/ssl/certs/ca-certificates.crt", "/etc/pki/tls/certs/ca-bundle.crt")
# Sheets name people and carry message text: no index, no cache, and no address passed on to the
# sites the sheet links to.
HEADERS = "/*\n  X-Robots-Tag: noindex\n  Cache-Control: no-store\n  Referrer-Policy: no-referrer\n"


class Refused(Exception):
    """Nothing was uploaded."""


class UploadFailed(Exception):
    """wrangler failed or did not finish; the host and its subdomains asked for a sign-in before it ran."""


class Exposed(Exception):
    """A deployment exists whose address does not ask for a sign-in."""


class _Stay(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None  # report the redirect; never follow it


def probe(url: str) -> tuple:
    """(status, Location) for a request with no sign-in. python.org's macOS Python can lack a CA
    path, so only a certificate failure retries with the operating system's own bundle."""
    failure = None
    for cafile in [None] + [f for f in SYSTEM_CA_FILES if pathlib.Path(f).is_file()]:
        context = ssl.create_default_context(cafile=cafile)
        opener = urllib.request.build_opener(_Stay, urllib.request.HTTPSHandler(context=context))
        try:
            with opener.open(url, timeout=20) as answer:
                return answer.status, answer.headers.get("Location", "")
        except urllib.error.HTTPError as answer:
            return answer.code, answer.headers.get("Location", "")
        except OSError as exc:
            failure = failure or exc
            if "CERTIFICATE_VERIFY_FAILED" not in str(failure):
                break
    raise Refused(f"could not reach {url}: {failure}")


def gated(url: str, probe=probe) -> str:
    """'' when a request with no sign-in to url is sent to a Cloudflare Access sign-in, else why not."""
    status, location = probe(url)
    target = urllib.parse.urlsplit(urllib.parse.urljoin(url, location)) if location else None
    if (status in REDIRECTS and target and target.scheme == "https" and target.hostname
            and target.hostname.endswith(".cloudflareaccess.com") and target.path.startswith("/cdn-cgi/access/login/")):
        return ""
    return f"{url} answered {status}" + (f" to {target.hostname}" if target and target.hostname else "") + \
        " to a request with no sign-in, not a redirect to a Cloudflare Access sign-in"


def sheet_page(path: pathlib.Path) -> str:
    """The generator's page for the filed spec beside path (a filed .html or its -spec.json)."""
    spec_path = path if path.name.endswith("-spec.json") else path.with_name(path.stem + "-spec.json")
    if path.suffix not in (".html", ".json") or not spec_path.is_file():
        raise Refused(f"{path} is not a filed sheet: file it with build_sheet.py --file-into, then publish "
                      "the filed page (its -spec.json must be beside it)")
    try:
        return bs.build(bs.read_spec(str(spec_path)))
    except ValueError as exc:
        raise Refused(f"{spec_path.name}: {exc}") from exc


def upload(page: str, project: str, branch: str, run=subprocess.run) -> str:
    """Upload the page as the site's index; return the new deployment's address."""
    wrangler = shutil.which("wrangler")
    if not wrangler:
        raise Refused("wrangler is not installed; the sheet stays the filed local page")
    with tempfile.TemporaryDirectory() as work:
        site = pathlib.Path(work) / "site"
        site.mkdir()
        (site / "index.html").write_text(page, encoding="utf-8")
        (site / "_headers").write_text(HEADERS, encoding="utf-8")
        try:
            done = run([wrangler, "pages", "deploy", str(site), "--project-name", project, "--branch", branch,
                        "--commit-dirty=true"], cwd=work, capture_output=True, text=True, timeout=300)
        except subprocess.TimeoutExpired as exc:
            raise UploadFailed(f"wrangler did not finish in {exc.timeout:.0f} s; look for a new deployment "
                               f"of {project} before publishing again") from exc
    found = re.findall(r"https://[0-9a-z-]+\." + re.escape(project) + r"\.pages\.dev", done.stdout + done.stderr)
    if done.returncode != 0 or not found:
        tail = " ".join((done.stderr or done.stdout).split())[-400:]
        raise UploadFailed(f"wrangler reported no deployment (exit {done.returncode}): {tail}")
    return found[0]  # the deployment's own address comes before any branch alias


def publish(path: pathlib.Path, project: str, branch: str = "main", probe=probe, run=subprocess.run) -> tuple:
    """(deployment address, host address), or Refused with nothing uploaded."""
    if not PROJECT.fullmatch(project):
        raise Refused(f"{project!r} is not a Pages project name")
    page = sheet_page(path)
    host = f"https://{project}.pages.dev/"
    for url in (host, f"https://{secrets.token_hex(4)}.{project}.pages.dev/"):
        why = gated(url, probe)
        if why:
            raise Refused(why + f"; nothing uploaded. Put one Access application with an allow policy for "
                          f"the principal in front of {project}.pages.dev and *.{project}.pages.dev first")
    deployment = upload(page, project, branch, run)
    why = gated(deployment + "/", probe)
    if why:
        raise Exposed(f"UPLOADED, BUT NOT BEHIND THE SIGN-IN: {why}. Delete this deployment now "
                      f"(Workers & Pages, {project}, Deployments) and check the Access application.")
    return deployment + "/", host


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
                                 allow_abbrev=False)
    ap.add_argument("sheet", type=pathlib.Path, help="the filed page, <date>-<slug>.html, or its -spec.json")
    ap.add_argument("--project", required=True, help="the Cloudflare Pages project that serves the sheets")
    ap.add_argument("--branch", default="main", help="the project's production branch (default: main)")
    args = ap.parse_args()
    try:
        deployment, host = publish(args.sheet, args.project, args.branch)
    except Refused as exc:
        print(f"will not publish: {exc}", file=sys.stderr)
        return 2
    except Exposed as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except UploadFailed as exc:
        print(f"upload failed: {exc}", file=sys.stderr)
        return 4
    print(f"published {deployment}\nlatest {host}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

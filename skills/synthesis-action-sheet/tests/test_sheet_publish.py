"""The sheet without a host, and the optional private host.

The core needs no hosting account: building, filing and recording run with the network refused,
an empty home folder and nothing on the path. publish_sheet.py uploads only the generator's page,
rebuilt from the filed spec, and only while the host and a fresh subdomain send a request with no
sign-in to a Cloudflare Access sign-in; these tests stand in for the network and for wrangler.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import build_sheet as bs  # noqa: E402
import publish_sheet as ps  # noqa: E402
import record_actions as ra  # noqa: E402

SIGN_IN = "https://team.cloudflareaccess.com/cdn-cgi/access/login/{host}?kid=k&redirect_url=%2F"
DEPLOYED = "https://0a1b2c3d.sheets-example.pages.dev"


def spec():
    return {"title": "Synthetic actions",
            "do": [{"id": "D-1", "channel": "task", "label": "Sign the fixture form", "why": "Fixture task.",
                    "agent": "never"}]}


@pytest.fixture
def filed(tmp_path):
    artifacts = tmp_path / "resources" / "artifacts"
    artifacts.mkdir(parents=True)
    _, page = bs.file_sheet(spec(), bs.build(spec()), artifacts, "2026-10-22")
    return page


def rebuilt(page):
    return bs.build(bs.read_spec(str(page.with_name(page.stem + "-spec.json"))))


def gate(open_hosts=()):
    """A stand-in for the network: every host asks for a sign-in except those in open_hosts."""
    def probe(url):
        host = url.split("/")[2]
        return (200, "") if host in open_hosts else (302, SIGN_IN.format(host=host))
    return probe


class Wrangler:
    """Records what would be uploaded, read while the upload's folder still exists."""
    def __init__(self, returncode=0, output=f"Deployment complete! Take a peek over at {DEPLOYED}\n"):
        self.returncode, self.output, self.calls, self.files = returncode, output, [], {}

    def __call__(self, args, **kwargs):
        self.calls.append(args)
        site = Path(args[3])
        self.files = {p.name: p.read_text(encoding="utf-8") for p in site.iterdir()}
        return subprocess.CompletedProcess(args, self.returncode, self.output, "")


@pytest.fixture(autouse=True)
def installed(monkeypatch):
    monkeypatch.setattr(ps.shutil, "which", lambda name: "/opt/bin/wrangler" if name == "wrangler" else None)


# --- no host ------------------------------------------------------------------------------------

def test_the_sheet_needs_no_host_account_or_network(tmp_path):
    """Build, file and record with the network refused, an empty home and an empty path."""
    site, home, bare = tmp_path / "site", tmp_path / "home", tmp_path / "bin"
    for folder in (site, home, bare):
        folder.mkdir()
    (site / "sitecustomize.py").write_text(
        "import socket\n"
        "def _refused(*args, **kwargs):\n"
        "    raise OSError('network refused by the test')\n"
        "socket.socket.connect = socket.socket.connect_ex = _refused\n"
        "socket.create_connection = socket.getaddrinfo = _refused\n", encoding="utf-8")
    env = {"HOME": str(home), "PATH": str(bare), "PYTHONPATH": str(site), "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1"}

    def run(*args):
        return subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True, env=env)

    control = run("-c", "import socket; socket.create_connection(('example.com', 443))")
    assert "network refused by the test" in control.stderr  # the refusal is in force for the runs below
    artifacts = tmp_path / "resources" / "artifacts"
    artifacts.mkdir(parents=True)
    (tmp_path / "spec.json").write_text(bs.canonical_spec_bytes(spec()).decode("utf-8"), encoding="utf-8")
    built = run(SCRIPTS / "build_sheet.py", tmp_path / "spec.json", "--file-into", artifacts, "--date", "2026-10-22")
    assert built.returncode == 0, built.stderr
    (tmp_path / "paste.txt").write_text(ra.compose_summary(spec(), {"D-1": {"mark": "done"}}), encoding="utf-8")
    recorded = run(SCRIPTS / "record_actions.py", tmp_path / "paste.txt", "--spec",
                   artifacts / "2026-10-22-synthetic-actions-spec.json", "--file-into", artifacts, "--date", "2026-10-22")
    assert recorded.returncode == 0, recorded.stderr
    assert sorted(p.name for p in artifacts.iterdir()) == [
        "2026-10-22-synthetic-actions-actions.json", "2026-10-22-synthetic-actions-spec.json",
        "2026-10-22-synthetic-actions.html"]


# --- the private host ---------------------------------------------------------------------------

def test_it_uploads_the_generators_page_never_the_file_on_disk(filed):
    filed.write_text(filed.read_text(encoding="utf-8") + "<p>added by hand</p>", encoding="utf-8")
    wrangler = Wrangler()
    assert ps.publish(filed, "sheets-example", probe=gate(), run=wrangler) == (
        DEPLOYED + "/", "https://sheets-example.pages.dev/")
    assert wrangler.files["index.html"] == rebuilt(filed)
    # The rebuild embeds the filed (sorted) spec, so its marker differs from the filed page's, but the paste
    # binds to the same spec digest, and record_actions.py files it against the filed spec as before.
    assert f'SPEC_DIGEST = "{bs.spec_digest(spec())}"' in wrangler.files["index.html"]
    assert "X-Robots-Tag: noindex" in wrangler.files["_headers"] and "no-referrer" in wrangler.files["_headers"]
    assert wrangler.calls[0][1:] == ["pages", "deploy", wrangler.calls[0][3], "--project-name", "sheets-example",
                                     "--branch", "main", "--commit-dirty=true"]


def test_the_filed_spec_works_as_the_argument_too(filed):
    wrangler = Wrangler()
    ps.publish(filed.with_name(filed.stem + "-spec.json"), "sheets-example", probe=gate(), run=wrangler)
    assert wrangler.files["index.html"] == rebuilt(filed)


@pytest.mark.parametrize("open_host", ["sheets-example.pages.dev", "subdomain"])
def test_an_open_host_or_subdomain_uploads_nothing(filed, open_host):
    wrangler = Wrangler()
    probe = gate([open_host]) if open_host != "subdomain" else (
        lambda url: (404, "") if url.count(".") == 3 else (302, SIGN_IN.format(host=url.split("/")[2])))
    with pytest.raises(ps.Refused, match="nothing uploaded"):
        ps.publish(filed, "sheets-example", probe=probe, run=wrangler)
    assert wrangler.calls == []


@pytest.mark.parametrize("answer", [(302, "https://login.example.test/cdn-cgi/access/login/x"),
                                    (302, "http://team.cloudflareaccess.com/cdn-cgi/access/login/x"),
                                    (302, "https://team.cloudflareaccess.com/elsewhere"),
                                    (200, SIGN_IN.format(host="x")), (401, "")])
def test_only_a_redirect_to_an_access_sign_in_counts_as_the_gate(answer):
    assert ps.gated("https://sheets-example.pages.dev/", lambda url: answer)


def test_the_probe_names_itself_and_never_follows_the_redirect(monkeypatch):
    """Cloudflare answered 403 to urllib's default user agent on the first real upload, before Access saw it."""
    import urllib.error
    seen = []

    class Opener:
        def open(self, request, timeout):
            seen.append((request.full_url, request.get_header("User-agent"), timeout))
            raise urllib.error.HTTPError(request.full_url, 302, "Found", {"Location": SIGN_IN.format(host="h")}, None)

    monkeypatch.setattr(ps.urllib.request, "build_opener", lambda *handlers: Opener())
    assert ps.probe("https://sheets-example.pages.dev/") == (302, SIGN_IN.format(host="h"))
    assert seen == [("https://sheets-example.pages.dev/", ps.AGENT, 20)] and "Python-urllib" not in ps.AGENT


def test_a_deployment_that_does_not_ask_for_a_sign_in_is_reported_loudly(filed):
    with pytest.raises(ps.Exposed, match="UPLOADED, BUT NOT BEHIND THE SIGN-IN"):
        ps.publish(filed, "sheets-example", probe=gate([DEPLOYED.split("/")[2]]), run=Wrangler())


@pytest.mark.parametrize("wrangler, expected", [(Wrangler(returncode=1, output="Authentication error"), "exit 1"),
                                                (Wrangler(output="done, with no address"), "reported no deployment")])
def test_a_failed_upload_is_not_reported_as_published(filed, wrangler, expected):
    with pytest.raises(ps.UploadFailed, match=expected):
        ps.publish(filed, "sheets-example", probe=gate(), run=wrangler)


def test_nothing_is_uploaded_without_wrangler_a_filed_spec_or_a_valid_project(filed, tmp_path, monkeypatch):
    with pytest.raises(ps.Refused, match="not a Pages project name"):
        ps.publish(filed, "Sheets_Example", probe=gate(), run=Wrangler())
    loose = tmp_path / "sheet.html"
    loose.write_text(bs.build(spec()), encoding="utf-8")
    with pytest.raises(ps.Refused, match="not a filed sheet"):
        ps.publish(loose, "sheets-example", probe=gate(), run=Wrangler())
    monkeypatch.setattr(ps.shutil, "which", lambda name: None)
    with pytest.raises(ps.Refused, match="wrangler is not installed"):
        ps.publish(filed, "sheets-example", probe=gate(), run=Wrangler())


def test_the_command_line_refuses_before_any_network_call(tmp_path):
    loose = tmp_path / "sheet.html"
    loose.write_text("<p>not a sheet</p>", encoding="utf-8")
    out = subprocess.run([sys.executable, str(SCRIPTS / "publish_sheet.py"), str(loose), "--project", "sheets-example"],
                         capture_output=True, text=True)
    assert out.returncode == 2 and out.stderr.startswith("will not publish:") and "not a filed sheet" in out.stderr
    assert subprocess.run([sys.executable, str(SCRIPTS / "publish_sheet.py"), str(loose)],
                          capture_output=True, text=True).returncode == 2  # --project is required

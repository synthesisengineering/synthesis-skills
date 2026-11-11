"""The Drive copy for Gemini Notebook: a built tree synced into a Drive folder (replaced here by a fake),
in place by name, and the CI exchange of an OIDC token for the service account's token."""

import hashlib
import io
import json
import sys
import urllib.error
import urllib.parse

import pytest

from kb_plugin_fixture import PUBLISHED, SCRIPTS, VERSION, build, make_repo

sys.path.insert(0, str(SCRIPTS))
import publish_drive  # noqa: E402
from publish_drive import Refused, access_token, main, published_files, sync  # noqa: E402

FOLDER = "folder-1"


class FakeDrive:
    """The Drive calls publish_drive makes, against files kept in memory, with every write recorded."""

    def __init__(self, page_size=1000):
        self.files, self.writes, self.page_size, self.next_id = {}, [], page_size, 0

    def add(self, name, content=b"", mime="text/markdown", parent=FOLDER):
        self.next_id += 1
        file_id = f"id{self.next_id}"
        self.files[file_id] = {"name": name, "content": content, "mimeType": mime, "parents": [parent], "trashed": False}
        return file_id

    def by_name(self, name):
        return {f["name"]: (i, f) for i, f in self.files.items() if not f["trashed"]}[name]

    def __call__(self, method, url, token="", body=None, content_type="application/json"):
        assert token == "token"
        path, _, query = url.partition("?")
        params = urllib.parse.parse_qs(query)
        assert params["supportsAllDrives"] == ["true"]
        if method == "GET":
            folder = params["q"][0].split("'")[1]
            items = [{"id": i, "name": f["name"], "mimeType": f["mimeType"],
                      **({"md5Checksum": hashlib.md5(f["content"]).hexdigest()} if f["mimeType"] == "text/markdown" else {})}
                     for i, f in sorted(self.files.items()) if folder in f["parents"] and not f["trashed"]]
            start = int(params.get("pageToken", ["0"])[0])
            more = start + self.page_size < len(items)
            return {"files": items[start:start + self.page_size], **({"nextPageToken": str(start + self.page_size)} if more else {})}
        self.writes.append((method, path.rsplit("/", 1)[-1]))
        if path.endswith("/upload/drive/v3/files"):  # multipart: metadata, then content
            boundary = content_type.split("boundary=")[1].encode()
            meta, content = [part.split(b"\r\n\r\n", 1)[1].rsplit(b"\r\n", 1)[0]
                             for part in body.split(b"--" + boundary)[1:3]]
            meta = json.loads(meta)
            return {"id": self.add(meta["name"], content, meta["mimeType"], meta["parents"][0])}
        file_id = path.rsplit("/", 1)[-1]
        if "/upload/" in path:
            assert params["uploadType"] == ["media"] and content_type == "text/markdown"
            self.files[file_id]["content"] = body
        else:
            self.files[file_id].update(json.loads(body) if isinstance(body, bytes) else body)
        return {"id": file_id}


@pytest.fixture
def tree(tmp_path):
    out = tmp_path / "out"
    assert build(make_repo(tmp_path), out).returncode == 0
    return out


def run(tree, drive, dry_run=False):
    lines = []
    counts = sync(tree, FOLDER, "token", dry_run, lines.append, drive)
    return counts, lines


def test_the_first_run_adds_every_file_and_the_second_changes_nothing(tree):
    plugin, version, files = published_files(tree)
    assert version == VERSION and len(files) == len(PUBLISHED) + 1 and f"{plugin}-index.md" in files
    drive = FakeDrive()
    counts, lines = run(tree, drive)
    assert counts == {"added": 6, "updated": 0, "moved to trash": 0, "unchanged": 0}
    for name, path in files.items():
        assert drive.by_name(name)[1]["content"] == path.read_bytes()
    assert lines[-1] == f"Drive copy of {plugin} {VERSION}: 6 added, 0 updated, 0 moved to trash, 0 unchanged."
    drive.writes.clear()
    counts, _ = run(tree, drive)
    assert counts["unchanged"] == 6 and not drive.writes


def test_a_changed_file_is_replaced_in_place_and_a_dropped_one_goes_to_the_trash(tree):
    drive = FakeDrive()
    run(tree, drive)
    other = drive.add("team notes", b"x", "application/vnd.google-apps.document")
    drive.add("kept.md", parent="another-folder")
    _, files = published_files(tree)[1:]
    files["roadmap.md"].write_text("# Roadmap\n\nChanged.\n", encoding="utf-8")
    files["glossary.md"].unlink()
    file_id = drive.by_name("roadmap.md")[0]
    counts, lines = run(tree, drive)
    assert counts == {"added": 0, "updated": 1, "moved to trash": 1, "unchanged": 4}
    assert drive.by_name("roadmap.md") == (file_id, drive.files[file_id])
    assert drive.files[file_id]["content"] == b"# Roadmap\n\nChanged.\n"
    assert "glossary.md" not in {f["name"] for f in drive.files.values() if not f["trashed"]}
    assert not drive.files[other]["trashed"] and "moved to trash: glossary.md" in lines
    assert any("added as sources and the trashed ones removed" in line for line in lines)


def test_a_dry_run_lists_the_changes_and_writes_nothing(tree):
    drive = FakeDrive()
    counts, lines = run(tree, drive, dry_run=True)
    assert counts["added"] == 6 and not drive.writes and not drive.files
    assert "(dry run: nothing written)" in lines[-1]


def test_every_page_of_the_folder_is_read(tree):
    drive = FakeDrive(page_size=2)
    run(tree, drive)
    drive.writes.clear()
    assert run(tree, drive)[0]["unchanged"] == 6 and not drive.writes


def test_two_files_with_one_name_stop_the_run_before_anything_is_written(tree):
    drive = FakeDrive()
    drive.add("roadmap.md")
    drive.add("roadmap.md")
    with pytest.raises(Refused, match="two files named roadmap.md"):
        run(tree, drive)
    assert not drive.writes
    skill = next(tree.glob("plugins/*/skills/*"))
    (skill / "references" / "notes" / "roadmap.md").write_text("# Another\n", encoding="utf-8")
    with pytest.raises(Refused, match="two published files are named roadmap.md"):
        published_files(tree)


def test_ci_exchanges_its_oidc_token_for_the_service_accounts_token():
    calls = []

    def fake(method, url, token="", body=None, content_type="application/json"):
        calls.append((url, token, body, content_type))
        return {"access_token": "federated"} if "sts." in url else {"accessToken": "drive-token"}

    provider = "//iam.googleapis.com/projects/1/locations/global/workloadIdentityPools/ci/providers/bitbucket"
    env = {"KB_DRIVE_OIDC_TOKEN": "jwt", "KB_DRIVE_WIF_PROVIDER": provider, "KB_DRIVE_SERVICE_ACCOUNT": "sync@p.iam.gserviceaccount.com"}
    assert access_token(env, fake) == "drive-token"
    (sts, none, form, kind), (iam, federated, request, _) = calls
    assert sts == "https://sts.googleapis.com/v1/token" and not none and kind == "application/x-www-form-urlencoded"
    assert urllib.parse.parse_qs(form.decode()) == {
        "grant_type": ["urn:ietf:params:oauth:grant-type:token-exchange"], "audience": [provider],
        "scope": ["https://www.googleapis.com/auth/cloud-platform"],
        "requested_token_type": ["urn:ietf:params:oauth:token-type:access_token"],
        "subject_token": ["jwt"], "subject_token_type": ["urn:ietf:params:oauth:token-type:jwt"]}
    assert iam == ("https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/"
                   "sync@p.iam.gserviceaccount.com:generateAccessToken")
    assert federated == "federated" and request == {"scope": ["https://www.googleapis.com/auth/drive"]}
    assert access_token({"KB_DRIVE_ACCESS_TOKEN": "given"}, None) == "given"
    with pytest.raises(Refused, match="KB_DRIVE_WIF_PROVIDER, KB_DRIVE_SERVICE_ACCOUNT"):
        access_token({"KB_DRIVE_OIDC_TOKEN": "jwt"}, fake)
    with pytest.raises(Refused, match="full name"):
        access_token({**env, "KB_DRIVE_WIF_PROVIDER": "projects/1/providers/x"}, fake)
    with pytest.raises(Refused, match="without an access token"):
        access_token(env, lambda *a, **k: {})


def test_the_folder_and_the_tree_are_checked_before_any_credential(tree, tmp_path, capsys):
    assert main(["--tree", str(tree)], {"KB_DRIVE_FOLDER_ID": "a'b"}) == 1
    assert "KB_DRIVE_FOLDER_ID must be" in capsys.readouterr().err
    assert main(["--tree", str(tmp_path / "empty")], {"KB_DRIVE_FOLDER_ID": FOLDER}) == 1
    assert "holds 0 plugin skills" in capsys.readouterr().err
    assert main(["--tree", str(tree)], {"KB_DRIVE_FOLDER_ID": FOLDER}) == 1
    assert "set KB_DRIVE_ACCESS_TOKEN" in capsys.readouterr().err
    with pytest.raises(SystemExit) as usage:
        main([], {})
    assert usage.value.code == 2


def test_a_refusal_names_the_status_and_never_the_token(monkeypatch):
    def refuse(request, timeout):
        assert request.get_header("Authorization") == "Bearer secret-token"
        raise urllib.error.HTTPError(request.full_url, 403, "Forbidden", {}, io.BytesIO(b'{"error": "denied"}'))

    monkeypatch.setattr(publish_drive.urllib.request, "urlopen", refuse)
    with pytest.raises(Refused) as refused:
        publish_drive.call("GET", publish_drive.FILES + "?q=x", "secret-token")
    assert "answered 403" in str(refused.value) and "secret-token" not in str(refused.value)

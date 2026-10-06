"""Line-bound approvals in the commit check (Rajiv's ruling, 2026-10-06).

No word list can tell a leak from a legitimate mention, so agents reworded text, split strings
or built terms at run time to get past the check, which weakened the code and defeated the
guard. Now a disclosure hit blocks with a code; the principal types approve and the code; the
approval is kept for that repository, file (or the commit message) and the line's exact text,
as a hash and a date. That line passes from then on; an edit or a new place asks again.
Credentials are never approvable; vendors' published example keys pass by exact value.
"Bluebird" stands for a private client name.
"""

import base64
import json
import os
import re
import secrets
import string
import subprocess
import sys
from pathlib import Path

import pytest

from synthesis import approvals, guards

CHECK = Path(__file__).resolve().parents[1] / "synthesis" / "commit_check.py"
STRICT, OTHER = "git@github.com:other-org/project.git", "git@github.com:other-org/second.git"
LINE = "Kickoff with Bluebird next week"
POLICY = """\
config_version: 2
tier_0_always:
  api_keys:
    - 'AKIA[0-9A-Z]{16}'
  private_key_markers:
    - '-----BEGIN DSA PRIVATE KEY-----'
    - 'BEGIN [A-Z]+ PRIVATE KEY'
    - 'PRIVATE KEY BLOCK'
tier_1_strict_only:
  confidential_names:
    - 'Bluebird'
"""


def synthetic_key(header="-----BEGIN PRIVATE KEY-----"):
    """Random base64 under a key header: shaped like a key, never one. A credential is never approvable, so
    fixtures for the credential rules are generated when the test runs; written out here, they would block
    this file's own commit. This is the one place a flagged value is assembled at run time."""
    body = [base64.b64encode(os.urandom(48)).decode() for _ in range(3)]
    return "\n".join([header, *body, "-----END PRIVATE KEY-----"]) + "\n"


@pytest.fixture
def store(tmp_path, write_config):
    (tmp_path / "policy.yaml").write_text(POLICY, encoding="utf-8")
    write_config({"commit_policy": str(tmp_path / "policy.yaml")})
    return tmp_path / "line-allowances.json"  # the default: beside the policy


def make_repo(tmp_path, remote=STRICT, name="repo"):
    root = tmp_path / name
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    for hook in ("pre-commit", "commit-msg"):
        path = root / ".git" / "hooks" / hook
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f'#!/bin/sh\nSYNTHESIS_GIT_HOOK={hook} exec "{sys.executable}" -S "{CHECK}" "$@"\n', encoding="utf-8")
        path.chmod(0o755)
    if remote:
        subprocess.run(["git", "-C", str(root), "remote", "add", "origin", remote], check=True)
    return root


def commit(repo, files, message="Update notes"):
    for name, text in files.items():
        path = repo / name
        if text is None:
            path.unlink()
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    return subprocess.run(["git", "-C", str(repo), "commit", "-qm", message], capture_output=True, text=True, timeout=60)


def entries(store):
    return json.loads(store.read_text(encoding="utf-8"))["lines"] if store.exists() else {}


def approved_commit(repo, files, principal, message="Update notes"):
    """Commit, see the block and its code, have the principal type it, commit again."""
    blocked = commit(repo, files, message)
    assert blocked.returncode != 0 and "approve followed by the code" in blocked.stderr, blocked.stderr
    assert principal(blocked.stderr)
    return commit(repo, {}, message)


# --- the approval, and what it covers ------------------------------------------------------------

def test_a_hit_blocks_with_a_code_and_the_rule_against_rewording(tmp_path, store):
    result = commit(make_repo(tmp_path), {"notes/a.md": LINE + "\n"})
    assert result.returncode != 0
    assert "notes/a.md:1: " + LINE in result.stderr and "unapproved disclosure" in result.stderr
    assert re.search(r"type approve followed by the code \d[0-9a-f]{5}\b", result.stderr)
    assert "never reword, split, encode or build the text at run time" in result.stderr
    assert not approvals.CODE.search(result.stderr)  # it never prints the phrase the principal types
    assert approvals.pending() and not store.exists()


def test_the_principals_approval_lets_the_line_through_and_records_one_entry(tmp_path, store, principal):
    repo = make_repo(tmp_path)
    result = approved_commit(repo, {"notes/a.md": LINE + "\n"}, principal)
    assert result.returncode == 0, result.stderr
    assert len(entries(store)) == 1 and not approvals.pending()


def test_an_approved_line_passes_later_and_an_edit_or_a_new_place_asks_again(tmp_path, store, principal):
    repo = make_repo(tmp_path)
    assert approved_commit(repo, {"notes/a.md": LINE + "\n"}, principal).returncode == 0
    assert commit(repo, {"notes/a.md": "Moved on\n"}).returncode == 0  # gone from HEAD, so the moved-text rule can't pass it
    again = commit(repo, {"notes/a.md": LINE + "\n"})
    assert again.returncode == 0, again.stderr  # the store passes it, with no new approval
    assert commit(repo, {"notes/a.md": "Moved on\n"}).returncode == 0
    for files in ({"notes/a.md": LINE + " on Monday\n"}, {"notes/b.md": LINE + "\n"}):
        result = commit(repo, files)
        assert result.returncode != 0 and "approve followed by the code" in result.stderr, files
        subprocess.run(["git", "-C", str(repo), "reset", "-q", "--hard"], check=True)
    assert len(entries(store)) == 1


def test_the_same_line_in_another_repository_asks_again_but_another_clone_of_the_same_one_does_not(tmp_path, store, principal):
    assert approved_commit(make_repo(tmp_path, STRICT, "first"), {"a.md": LINE + "\n"}, principal).returncode == 0
    assert commit(make_repo(tmp_path, OTHER, "other"), {"a.md": LINE + "\n"}).returncode != 0
    # The repository is its push remotes, normalized: another clone, on this Mac or another, over https, is the same.
    clone = make_repo(tmp_path, "https://GitHub.com/other-org/project", "clone")
    assert commit(clone, {"a.md": LINE + "\n"}).returncode == 0
    assert len(entries(store)) == 1


def test_a_grant_without_the_principals_prompt_in_the_transcript_does_not_count(tmp_path, store):
    repo = make_repo(tmp_path)
    blocked = commit(repo, {"a.md": LINE + "\n"})
    code = re.search(r"the code (\w{6})", blocked.stderr).group(1)
    assert approvals.grant_from_prompt(f"approve {code}")  # the prompt hook ran, by whoever's hand; no session record
    result = commit(repo, {})
    assert result.returncode != 0 and "only from the principal's own prompt" in result.stderr
    assert "gave no transcript" in result.stderr and not store.exists()


def test_the_store_holds_only_hashes_and_dates(tmp_path, store, principal):
    assert approved_commit(make_repo(tmp_path), {"a.md": LINE + "\n"}, principal).returncode == 0
    raw = store.read_text(encoding="utf-8")
    assert "Bluebird" not in raw and "Kickoff" not in raw and "a.md" not in raw
    (key, when), = entries(store).items()
    assert re.fullmatch(r"[0-9a-f]{64}", key) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", when)


def test_a_commit_message_hit_is_approved_the_same_way(tmp_path, store, principal):
    repo = make_repo(tmp_path)
    message = "Prepare the Bluebird kickoff"
    result = approved_commit(repo, {"a.md": "Agenda\n"}, principal, message)
    assert result.returncode == 0, result.stderr
    assert len(entries(store)) == 1
    assert commit(repo, {"b.md": "More\n"}, message).returncode == 0  # the same message line, approved for this repository
    assert commit(repo, {"c.md": "More\n"}, message + " today").returncode != 0


def test_the_store_may_be_named_in_the_config(tmp_path, write_config, principal):
    (tmp_path / "policy.yaml").write_text(POLICY, encoding="utf-8")
    named = tmp_path / "private" / "approved-lines.json"
    write_config({"commit_policy": str(tmp_path / "policy.yaml"), "line_allowances": str(named)})
    assert approved_commit(make_repo(tmp_path), {"a.md": LINE + "\n"}, principal).returncode == 0
    assert len(entries(named)) == 1 and not (tmp_path / "line-allowances.json").exists()


@pytest.mark.parametrize("damage", ["not json", "[]", '{"lines": []}', "{}"])
def test_a_store_that_cannot_be_read_blocks(tmp_path, store, damage):
    store.write_text(damage, encoding="utf-8")
    for files in ({"a.md": LINE + "\n"}, {"b.md": "Nothing flagged\n"}):  # read whenever it could decide a line
        result = commit(make_repo(tmp_path, name=f"repo-{len(files)}-{list(files)[0]}"), files)
        assert result.returncode != 0 and "cannot read the approved lines" in result.stderr
    assert store.read_text(encoding="utf-8") == damage


def test_the_store_in_the_repository_is_a_catalog(tmp_path, write_config, principal):
    repo = make_repo(tmp_path)
    (tmp_path / "policy.yaml").write_text(POLICY, encoding="utf-8")
    write_config({"commit_policy": str(tmp_path / "policy.yaml"), "line_allowances": str(repo / "approved.json")})
    (repo / "approved.json").write_text('{"lines": {"Bluebird": "2026-10-06"}}', encoding="utf-8")
    assert commit(repo, {"approved.json": '{"lines": {"Bluebird": "2026-10-06"}}'}).returncode == 0


# --- credentials are never approvable; the key rule is structural ----------------------------------

def test_the_published_aws_example_keys_pass_and_a_real_looking_key_blocks(tmp_path, store):
    repo = make_repo(tmp_path)
    example = "aws_access_key_id = AKIAIOSFODNN7EXAMPLE\naws_secret_access_key = wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY\n"
    assert commit(repo, {"docs/aws.md": example}).returncode == 0
    generated = "AKIA" + "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(16))  # see synthetic_key
    near = "AKIAIOSFODNN7EXAMPL" + secrets.choice("ABCDFGH")  # the example with its last character changed
    for value in (generated, near):
        result = commit(repo, {"config.ini": f"aws_access_key_id = {value}\n"})
        assert result.returncode != 0 and "looks like a" in result.stderr and "approve followed by" not in result.stderr
        subprocess.run(["git", "-C", str(repo), "reset", "-q", "--hard"], check=True)


def test_a_bare_key_header_passes_whatever_marker_the_policy_lists_and_a_key_blocks(tmp_path, store):
    repo = make_repo(tmp_path)
    headers = "".join(f"-----BEGIN {k}PRIVATE KEY-----\n" for k in ("", "DSA ", "RSA ", "EC ", "OPENSSH ", "ENCRYPTED "))
    headers += "-----BEGIN PGP PRIVATE KEY BLOCK-----\n---- BEGIN SSH2 ENCRYPTED PRIVATE KEY ----\n"
    assert commit(repo, {"docs/formats.md": headers}).returncode == 0, "a header alone is how docs and rules name a key"
    result = commit(repo, {"key.txt": synthetic_key()})
    assert result.returncode != 0 and "private key material" in result.stderr
    subprocess.run(["git", "-C", str(repo), "reset", "-q", "--hard"], check=True)
    ssh2 = synthetic_key('---- BEGIN SSH2 ENCRYPTED PRIVATE KEY ----\nComment: "example"')
    assert "private key material" in commit(repo, {"ssh2.txt": ssh2}).stderr


# --- the shell guard refuses writes to the store -----------------------------------------------------

@pytest.mark.parametrize("command", [
    "echo '{{}}' > {store}",
    "printf x | tee {store}",
    "cd {folder} && echo '{{}}' >> line-allowances.json",
    "cp /tmp/line-allowances.json {folder}/",
    "sed -i '' 's/a/b/' {store}",
    "python3 -c \"import json; json.dump({{}}, open('{store}', 'w'))\"",
])
def test_a_shell_command_writing_the_store_is_refused(tmp_path, store, command):
    config = {"commit_policy": str(tmp_path / "policy.yaml")}
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    reason = guards.check("Bash", {"command": command.format(store=store, folder=tmp_path)}, config, cwd=str(elsewhere))
    assert reason and ("approved commit lines" in reason or "writes where" in reason), reason


@pytest.mark.parametrize("command", ["cat {store}", "python3 -m json.tool {store}", "git -C {folder} status"])
def test_reading_the_store_is_allowed(tmp_path, store, command):
    config = {"commit_policy": str(tmp_path / "policy.yaml")}
    assert guards.check("Bash", {"command": command.format(store=store, folder=tmp_path)}, config, cwd=str(tmp_path)) is None

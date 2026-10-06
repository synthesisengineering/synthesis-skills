"""R3.3 / R3.5: the commit policy (classes, ledger, messages, keys, file names, moved lines).

Fixtures are anonymized: "Bluebird" stands for a private client name, "Example Daily" for a
former employer the principal has published, example-person for the principal's own namespace.
"""

import subprocess
import sys
import time
from pathlib import Path

import pytest

from synthesis import commit_check as cc

CHECK = Path(__file__).resolve().parents[1] / "synthesis" / "commit_check.py"
FAKE_AWS = "AKIA" + "ABCDEFGHIJKLMNOP"  # split so this file never trips the scanner itself
KEY = "-----BEGIN " + "RSA PRIVATE KEY-----"
PAY_WORD, MARK_WORD = "sal" + "ary", "Propri" + "etary"  # split for the same reason as FAKE_AWS
OPENSSH_MARKER = KEY[5:-5].replace('RSA', 'OPENSSH')  # an f-string may not nest its own quotes before 3.12
BODY = ["MIIEowIBAAKCAQEAu1SU1LfVLPHCozMxH2Mo4lgOEePzNm0tRgeLezV6ffAt0gun", "VTLw7onLRnrq0/IzW7yWR7QkrmBL7jTKEn5u+qKhbwKfBstIs+bMY2Zkp18gnTxK"]
POLICY = """\
config_version: 2
personal_remote_patterns:
  - '[:/]example-person/'
public_surface_patterns:
  - '[:/]example-person/site(\\.git)?$'
strict_repo_patterns:
  - '[:/]example-person/public-tool(\\.git)?$'
disclosure_ledger: '{ledger}'
tier_0_always:
  api_keys:
    - 'sk-ant-api[a-zA-Z0-9-]+'
  private_key_markers:
    - '{key_marker}'
tier_1_strict_only:
  financial:
    - '\\bsalary\\b'
  confidentiality_markers:
    - '\\bproprietary\\b'
  confidential_names:
    - 'Bluebird'
    - 'Example Daily'
allowlist_lines:
  - '^\\+[[:space:]]*"?license"?:[[:space:]]*"?{mark_word}"?,?[[:space:]]*$'
diff_exclude_paths:
  - '(^|/)docs/catalog/'
check_commit_message: true
"""
LEDGER = """\
ledger_version: 1
entities:
  example-daily:
    kind: organization
    registers:
      - biography
    hook_patterns:
      - 'Example Daily'
    evidence:
      - 'https://example.com/about'
"""


def _script(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    path.chmod(0o755)


@pytest.fixture
def policy(tmp_path, write_config):
    ledger = tmp_path / "ledger.yaml"
    ledger.write_text(LEDGER, encoding="utf-8")
    path = tmp_path / "policy.yaml"
    path.write_text(POLICY.format(ledger=ledger, key_marker=KEY.strip('-'), mark_word=MARK_WORD), encoding="utf-8")
    write_config({"commit_policy": str(path)})
    return path


def make_repo(tmp_path, remote=None, name="repo"):
    root = tmp_path / name
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    _script(root / ".git" / "hooks" / "pre-commit", f'exec "{sys.executable}" -S "{CHECK}" "$@"')
    _script(root / ".git" / "hooks" / "commit-msg", f'SYNTHESIS_GIT_HOOK=commit-msg exec "{sys.executable}" -S "{CHECK}" "$@"')
    if remote:
        subprocess.run(["git", "-C", str(root), "remote", "add", "origin", remote], check=True)
    return root


def commit(repo, files, message="update"):
    for name, data in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    return subprocess.run(["git", "-C", str(repo), "commit", "-qm", message], capture_output=True, text=True, timeout=60)


STRICT, PERSONAL = "git@github.com:other-org/project.git", "git@github.com:example-person/notes.git"
SITE = "git@github.com:example-person/site.git"


# --- classes ----------------------------------------------------------------------------------

@pytest.mark.parametrize("remote,blocked", [(None, True), (STRICT, True), (PERSONAL, False),
                                            ("git@github.com:example-person/public-tool.git", True)])
def test_exposure_patterns_follow_the_repository_class(tmp_path, policy, remote, blocked):
    result = commit(make_repo(tmp_path, remote), {"a.md": "Kickoff with Bluebird next week\n"})
    assert (result.returncode != 0) is blocked, result.stderr
    if blocked:
        assert "unapproved disclosure" in result.stderr


def test_mixed_remotes_take_the_stricter_class(tmp_path, policy):
    repo = make_repo(tmp_path, PERSONAL)
    subprocess.run(["git", "-C", str(repo), "remote", "set-url", "--add", "--push", "origin", STRICT], check=True)
    subprocess.run(["git", "-C", str(repo), "remote", "set-url", "--add", "--push", "origin", PERSONAL], check=True)
    assert commit(repo, {"a.md": "Bluebird\n"}).returncode != 0


def test_a_public_surface_allows_ledgered_names_and_blocks_the_rest(tmp_path, policy):
    repo = make_repo(tmp_path, SITE)
    assert commit(repo, {"bio.md": "I worked at Example Daily.\n"}).returncode == 0
    assert commit(repo, {"bio2.md": "Advising Bluebird.\n"}).returncode != 0


def test_a_missing_or_malformed_ledger_blocks_public_surface_commits(tmp_path, policy):
    repo = make_repo(tmp_path, SITE)
    (tmp_path / "ledger.yaml").write_text("entities:\n\tbad: tab\n", encoding="utf-8")
    result = commit(repo, {"bio.md": "plain words\n"})
    assert result.returncode != 0 and "disclosure ledger" in result.stderr
    (tmp_path / "ledger.yaml").unlink()
    assert commit(repo, {"bio.md": "plain words\n"}).returncode != 0
    assert commit(make_repo(tmp_path, PERSONAL, "notes"), {"a.md": "plain\n"}).returncode == 0  # only that class needs it


def test_a_ledger_entry_without_evidence_or_outside_the_identity_groups_is_refused(tmp_path, policy):
    ledger = tmp_path / "ledger.yaml"
    ledger.write_text(LEDGER.replace("    evidence:\n      - 'https://example.com/about'\n", ""), encoding="utf-8")
    assert "no evidence" in commit(make_repo(tmp_path, SITE), {"a.md": "x\n"}).stderr
    ledger.write_text(LEDGER.replace("'Example Daily'\n    evidence", "'\\bsalary\\b'\n    evidence"), encoding="utf-8")
    assert "identity groups" in commit(make_repo(tmp_path, SITE, "site2"), {"a.md": "x\n"}).stderr


# --- fail closed --------------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [("config_version: 2\ntier_0_always:\n\tk: x\n", "tab"),
                                           ("config_version: 2\ntier_1_strict_only:\n  a:\n    - 'x'\n", "tier_0_always"),
                                           ("config_version: 1\ntier_0_always:\n  a:\n    - 'x'\n", "config_version"),
                                           ("config_version: 2\ntier_0_always:\n  a:\n    - '(unclosed'\n", "invalid pattern"),
                                           ("config_version: 2\ntier_0_always: [x]\n", "outside the supported")])
def test_a_policy_that_cannot_be_read_with_certainty_blocks_every_commit(tmp_path, write_config, text, expected):
    path = tmp_path / "policy.yaml"
    path.write_text(text, encoding="utf-8")
    write_config({"commit_policy": str(path)})
    result = commit(make_repo(tmp_path, PERSONAL), {"a.md": "x\n"})
    assert result.returncode != 0 and expected in result.stderr and "commit blocked" in result.stderr


def test_a_named_policy_file_that_is_missing_blocks(tmp_path, write_config):
    write_config({"commit_policy": str(tmp_path / "absent.yaml")})
    assert "cannot read the commit policy" in commit(make_repo(tmp_path, PERSONAL), {"a.md": "x\n"}).stderr


def test_without_a_policy_credentials_still_block_and_nothing_else_does(tmp_path):
    repo = make_repo(tmp_path)
    assert commit(repo, {"a.md": f"Bluebird and {PAY_WORD} talk\n"}).returncode == 0
    assert commit(repo, {"b.md": f"{FAKE_AWS}\n"}).returncode != 0


# --- commit messages ----------------------------------------------------------------------------

def test_messages_are_scanned_in_strict_and_public_surface_repos_without_ledger_allowances(tmp_path, policy):
    assert "refused this message" in commit(make_repo(tmp_path, STRICT, "a"), {"a.md": "x\n"}, "Reframe the Bluebird post").stderr
    assert commit(make_repo(tmp_path, SITE, "b"), {"a.md": "x\n"}, "Update the Example Daily bio").returncode != 0
    assert commit(make_repo(tmp_path, PERSONAL, "c"), {"a.md": "x\n"}, "Notes on Bluebird").returncode == 0


def test_a_credential_in_a_message_blocks_in_every_class(tmp_path, policy):
    assert commit(make_repo(tmp_path, PERSONAL), {"a.md": "x\n"}, f"use {FAKE_AWS}").returncode != 0


def test_git_comment_lines_in_a_message_are_not_scanned(tmp_path, policy):
    assert commit(make_repo(tmp_path, STRICT), {"a.md": "x\n"}, "Tidy notes\n\n# Bluebird").returncode == 0


def test_the_message_check_honors_check_commit_message_false(tmp_path, policy):
    policy.write_text(policy.read_text().replace("check_commit_message: true", "check_commit_message: false"))
    assert commit(make_repo(tmp_path, STRICT), {"a.md": "x\n"}, "Bluebird notes").returncode == 0


# --- reading the diff byte for byte -------------------------------------------------------------

@pytest.mark.parametrize("name", ['odd "quoted" name.txt', "tab\tname.txt", "new\nline.txt", "ünïcode.txt", "-dash.txt"])
def test_unusual_file_names_cannot_hide_a_credential(tmp_path, name):
    result = commit(make_repo(tmp_path), {name: f"key {FAKE_AWS}\n"})
    assert result.returncode != 0 and "AWS access key" in result.stderr


def test_invalid_utf8_cannot_hide_a_match_or_earn_an_allowlist_exemption(tmp_path, policy):
    assert commit(make_repo(tmp_path, STRICT, "a"), {"a.txt": b"\xff\xfe Bluebird \xc3\n"}).returncode != 0
    assert commit(make_repo(tmp_path, STRICT, "b"), {"b.json": f'  "license": "{MARK_WORD}"\n'.encode()}).returncode == 0  # allowlisted
    assert commit(make_repo(tmp_path, STRICT, "c"), {"c.json": f'  "license": "{MARK_WORD}'.encode() + b'\xff"\n'}).returncode != 0


def test_catalog_paths_skip_exposure_patterns_but_never_credentials(tmp_path, policy):
    repo = make_repo(tmp_path, STRICT)
    assert commit(repo, {"docs/catalog/names.md": "Bluebird\n"}).returncode == 0
    assert commit(repo, {"docs/catalog/keys.md": f"{FAKE_AWS}\n"}).returncode != 0
    assert commit(repo, {"docs/catalog/new\nline.md": "Bluebird\n"}).returncode != 0  # a newline path earns no exclusion


def test_an_exact_copy_is_not_rescanned_but_an_edited_rename_is(tmp_path, policy):
    repo = make_repo(tmp_path, PERSONAL)
    assert commit(repo, {"CLAUDE.md": "Working notes on Bluebird\n" + "line\n" * 20}).returncode == 0
    subprocess.run(["git", "-C", str(repo), "remote", "set-url", "origin", STRICT], check=True)
    (repo / "AGENTS.md").write_text((repo / "CLAUDE.md").read_text())
    assert commit(repo, {}).returncode == 0  # the copy adds no lines
    subprocess.run(["git", "-C", str(repo), "mv", "AGENTS.md", "RULES.md"], check=True)
    assert commit(repo, {"RULES.md": (repo / "CLAUDE.md").read_text() + f"{PAY_WORD} bands\n"}).returncode != 0


def test_the_diff_parser_follows_hunk_counts_and_quoted_paths():
    diff = (b'diff --git a/x b/x\n--- a/x\n+++ "b/sp ace\\t\\303\\274.md"\n@@ -0,0 +1,2 @@\n'
            b"++++ b/looks-like-a-header\n+second\n")
    assert cc.added(diff) == [("sp ace\tü.md".encode(), 1, b"+++ b/looks-like-a-header"), ("sp ace\tü.md".encode(), 2, b"second")]
    with pytest.raises(cc.Refused):
        cc.added(b"diff --git a/x b/x\n+++ b/x\n@@ -0,0 +1,3 @@\n+one\n")  # truncated hunk


def test_git_output_is_bounded_in_size_and_time(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    (repo / "big.txt").write_text("x" * 5000)
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    monkeypatch.chdir(repo)
    with pytest.raises(cc.Refused, match="more than"):
        cc.git_bytes(["diff", "--cached"], time.monotonic() + 30, limit=1000)
    with pytest.raises(cc.Refused, match="longer than"):
        cc.git_bytes(["diff", "--cached"], time.monotonic() - 1)


# --- private keys and credential files ----------------------------------------------------------

def test_a_key_header_alone_is_a_rule_not_a_key(tmp_path, policy):
    repo = make_repo(tmp_path, STRICT)
    assert commit(repo, {"rules.yaml": f"markers:\n  - '{KEY[5:-5]}'\n  - '{OPENSSH_MARKER}'\n"}).returncode == 0
    assert commit(repo, {"doc.md": f"A PEM file starts with `{KEY}`.\n"}).returncode == 0


def test_a_key_header_followed_by_key_body_lines_blocks(tmp_path):
    result = commit(make_repo(tmp_path), {"id.pem.txt": "\n".join([KEY, *BODY, "abc=", KEY.replace("BEGIN", "END")]) + "\n"})
    assert result.returncode != 0 and "private key" in result.stderr


def test_an_unchanged_header_with_a_new_body_blocks(tmp_path):
    repo = make_repo(tmp_path)
    assert commit(repo, {"k.txt": KEY + "\n\nnotes\n"}).returncode == 0
    assert commit(repo, {"k.txt": KEY + "\n" + BODY[0] + "\nnotes\n"}).returncode != 0


def test_an_inline_escaped_key_and_a_key_in_a_message_block(tmp_path):
    repo = make_repo(tmp_path)
    assert commit(repo, {"cfg.json": '{"key": "' + KEY + "\\n" + BODY[0] + '\\n"}\n'}).returncode != 0
    assert commit(make_repo(tmp_path, name="m"), {"a.md": "x\n"}, "\n".join([KEY, *BODY])).returncode != 0


@pytest.mark.parametrize("name,blocked", [(".env", True), ("app/.env.local", True), ("deploy/id_rsa", True),
                                          ("certs/server.pem", True), ("keys/store.p12", True),
                                          (".env.example", False), ("id_rsa.pub", False), ("certs/server.crt", False)])
def test_credential_file_names_are_refused_whatever_they_hold(tmp_path, name, blocked):
    result = commit(make_repo(tmp_path), {name: "placeholder\n"})
    assert (result.returncode != 0) is blocked, result.stderr


# --- moved text is not a new disclosure ---------------------------------------------------------

def test_a_line_already_in_head_moves_without_counting_as_a_new_disclosure(tmp_path, policy):
    repo = make_repo(tmp_path, PERSONAL)
    assert commit(repo, {"catalog.md": "intro\nThe Bluebird case study\n"}).returncode == 0
    subprocess.run(["git", "-C", str(repo), "remote", "set-url", "origin", STRICT], check=True)
    moved = commit(repo, {"catalog.md": "intro\n", "references/part-2.md": "The Bluebird case study\n"})
    assert moved.returncode == 0, moved.stderr
    assert commit(repo, {"references/part-3.md": "A new Bluebird case study\n"}).returncode != 0


def test_a_moved_credential_still_blocks(tmp_path):
    repo = make_repo(tmp_path)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "--allow-empty", "-m", "start"], check=True)
    leaked = f"token = {FAKE_AWS}\n"
    (repo / "old.txt").write_text(leaked)
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "--no-verify", "-m", "an old leak"], check=True)
    assert commit(repo, {"old.txt": "gone\n", "new.txt": leaked}).returncode != 0


# --- the YAML subset ----------------------------------------------------------------------------

def test_the_yaml_reader_keeps_regex_escapes_literal_and_refuses_what_it_does_not_support():
    data = cc.parse_yaml("a:\n  b:\n    - '\\bx\\b'  # comment\n    - \"y\\\\b\"\n  c: []\n  d: 'it''s'\nflag: yes\nn: 3\n")
    assert data == {"a": {"b": ["\\bx\\b", "y\\b"], "c": [], "d": "it's"}, "flag": True, "n": 3}
    for bad in ("a: &anchor x\n", "a:\n  - b: c\n", "a: |\n  x\n", "a: 1\na: 2\n", "a: 'open\n"):
        with pytest.raises(cc.Refused):
            cc.parse_yaml(bad)


def test_posix_classes_in_policy_patterns_mean_what_grep_means():
    assert cc.regex(r"^\+[[:space:]]*x").search("+   X")
    assert cc.regex(r"[^[:alnum:]_]Bluebird").search("(Bluebird)") and not cc.regex(r"[^[:alnum:]_]Bluebird").search("xBluebird")


def test_classify_prints_the_class_and_the_shipped_example_policy_loads(tmp_path, policy, monkeypatch, capsys):
    monkeypatch.chdir(make_repo(tmp_path, SITE))
    assert cc.main(["--classify"]) == 0 and capsys.readouterr().out.strip() == "public-surface"
    example = Path(__file__).resolve().parents[1] / "skills" / "synthesis-git-hooks" / "git-hook-config.example.yaml"
    assert cc.load_policy({"commit_policy": str(example)})["config_version"] == 2

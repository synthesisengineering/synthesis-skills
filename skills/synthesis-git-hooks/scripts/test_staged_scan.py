from pathlib import Path
import os
import subprocess
import zipfile
import io
import pytest

HOOK = Path(__file__).resolve().with_name("pre-commit")
# A synthetic scanner input, assembled from its format and sequential alphabet.
SYNTHETIC_ACCESS_KEY = b"AKIA" + bytes(range(ord("A"), ord("Q")))


def git(root, *args):
    p = subprocess.run(["git", "-C", str(root), *args], capture_output=True, timeout=10)
    assert p.returncode == 0, p.stderr
    return p.stdout


def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init")
    git(root, "config", "user.name", "Synthetic Test")
    git(root, "config", "user.email", "fixture@example.invalid")
    git(root, "config", "core.hooksPath", "/dev/null")
    git(root, "config", "gc.auto", "0")
    git(root, "config", "maintenance.auto", "false")
    (root / "seed").write_text("seed\n")
    git(root, "add", "seed")
    git(root, "commit", "-m", "Fixture")
    policy = tmp_path / "policy.yaml"
    policy.write_text(
        "config_version: 2\npersonal_remote_patterns:\n  - 'never-matches'\ntier_0_always:\n  credentials:\n    - 'AKIA[0-9A-Z]{16}'\ntier_1_strict_only:\n  confidentiality:\n    - 'confidential'\n    - 'café'\ncheck_commit_message: false\n"
    )
    env = dict(
        os.environ,
        HOME=str(tmp_path / "home"),
        SYNTHESIS_GIT_HOOK_CONFIG=str(policy),
        LANG="en_US.UTF-8",
        LC_ALL="en_US.UTF-8",
    )
    return root, policy, env


def hook(root, env):
    p = subprocess.run([str(HOOK)], cwd=root, env=env, capture_output=True, timeout=20)
    (root.parent / "hook.stdout").write_bytes(p.stdout)
    (root.parent / "hook.stderr").write_bytes(p.stderr)
    return p


def stage(root, name, body):
    p = root / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(body)
    git(root, "add", "--", name)


def test_invalid_utf8_middle_zip_stored_part_is_scanned_without_crash(tmp_path):
    root, _, env = repo(tmp_path)
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w", compression=zipfile.ZIP_STORED) as z:
        z.writestr("fixture", b"A" * 32768 + b"\n\xff\xfe\n" + b"B" * 32768)
    part = data.getvalue()[16384:49152]
    assert b"\0" not in part[:8192] and b"\xff" in part
    stage(root, "archive.part0002", part)
    p = hook(root, env)
    assert p.returncode == 0, (p.stdout, p.stderr)


@pytest.mark.parametrize(
    "suffix",
    [
        b"\xff\xfe\nconfidential\n",
        b"\xff\x00\n" + SYNTHETIC_ACCESS_KEY + b"\n",
        b"\xff\ncaf\xc3\xa9\n",
    ],
    ids=['invalid-utf8-sensitive-word', 'nul-before-credential', 'invalid-utf8-unicode'],
)
def test_invalid_bytes_never_hide_sensitive_added_line(tmp_path, suffix):
    root, _, env = repo(tmp_path)
    stage(root, "archive.part", b"harmless\n" * 1500 + suffix)
    p = hook(root, env)
    assert p.returncode == 1 and b"SENSITIVE PATTERN DETECTED" in p.stdout, (
        p.stdout,
        p.stderr,
    )


def test_git_filename_cannot_execute_shell_in_exclusion_filter(tmp_path):
    root, _, env = repo(tmp_path)
    stage(root, "x'; touch INJECTION_MARKER; printf 'x", b"harmless\n")
    p = hook(root, env)
    assert not (root / "INJECTION_MARKER").exists(), (p.stdout, p.stderr)
    assert p.returncode == 0, (p.stdout, p.stderr)


def test_added_header_shaped_content_cannot_change_excluded_path(tmp_path):
    root, _, env = repo(tmp_path)
    stage(
        root,
        "ordinary.md",
        b"++ b/skills/synthesis-git-hooks/scripts/config.py\nconfidential\n",
    )
    p = hook(root, env)
    assert p.returncode == 1 and b"SENSITIVE PATTERN DETECTED" in p.stdout, (
        p.stdout,
        p.stderr,
    )


def test_literal_quoted_path_is_excluded_only_by_real_name(tmp_path):
    root, policy, env = repo(tmp_path)
    policy.write_text(
        policy.read_text() + 'diff_exclude_paths:\n  - "^review\'s notes[.]md$"\n'
    )
    stage(root, "review's notes.md", b"confidential\n")
    p = hook(root, env)
    assert p.returncode == 0, (p.stdout, p.stderr)


@pytest.mark.parametrize(
    "name",
    [
        "café.md",
        "space name.md",
        "tab\tname.md",
        "line\nname.md",
        "back\\slash.md",
        'quote"name.md',
    ],
)
def test_encoded_git_path_retains_real_sensitive_hunk(tmp_path, name):
    root, _, env = repo(tmp_path)
    stage(root, name, b"confidential\n")
    p = hook(root, env)
    assert p.returncode == 1 and b"SENSITIVE PATTERN DETECTED" in p.stdout, (
        p.stdout,
        p.stderr,
    )


def test_unicode_case_matching_keeps_current_locale_semantics(tmp_path):
    root, _, env = repo(tmp_path)
    stage(root, "unicode.md", "CAFÉ\n".encode())
    p = hook(root, env)
    assert p.returncode == 1 and b"SENSITIVE PATTERN DETECTED" in p.stdout, (
        p.stdout,
        p.stderr,
    )


def test_credential_header_shaped_line_is_never_discarded(tmp_path):
    root, _, env = repo(tmp_path)
    stage(root, "catalog.md", b"++ " + SYNTHETIC_ACCESS_KEY + b"\n")
    p = hook(root, env)
    assert p.returncode == 1 and b"SENSITIVE PATTERN DETECTED" in p.stdout, (
        p.stdout,
        p.stderr,
    )


def test_nul_before_sensitive_bytes_does_not_produce_binary_grep_summary(tmp_path):
    root, _, env = repo(tmp_path)
    stage(root, "part", b"x" * 9000 + b"\x00" + SYNTHETIC_ACCESS_KEY + b"\n")
    p = hook(root, env)
    assert p.returncode == 1 and SYNTHETIC_ACCESS_KEY in p.stdout, (
        p.stdout,
        p.stderr,
    )


def test_policy_apostrophes_cannot_execute_shell(tmp_path):
    root, policy, env = repo(tmp_path)
    policy.write_text(
        policy.read_text()
        + """diff_exclude_paths:
  - "x'; touch POLICY_INJECTION; printf 'x"
"""
    )
    stage(root, "plain.md", b"harmless\n")
    p = hook(root, env)
    assert not (root / "POLICY_INJECTION").exists()
    assert p.returncode == 0, (p.stdout, p.stderr)


def test_newline_path_never_uses_one_segment_as_exclusion(tmp_path):
    root, _, env = repo(tmp_path)
    stage(
        root,
        "ordinary\nskills/synthesis-git-hooks/scripts/excluded.py",
        b"confidential\n",
    )
    p = hook(root, env)
    assert p.returncode == 1 and b"SENSITIVE PATTERN DETECTED" in p.stdout, (
        p.stdout,
        p.stderr,
    )


def test_added_lines_refuse_truncation_and_unbound_headers():
    import importlib.util
    import time

    spec = importlib.util.spec_from_file_location(
        "staged_owner", HOOK.with_name("_scan_staged.py")
    )
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    for raw in [
        b"@@ -0,0 +1 @@\n+hidden\n",
        b"diff --git a/a b/a\n+++ b/a\n@@ -0,0 +1,2 @@\n+hidden\n",
        b"diff --git a/a b/a\n+++ b/a\n+outside\n",
    ]:
        with pytest.raises(m.ScanError):
            m.added_lines(raw, "", time.monotonic() + 1)


def test_missing_scanner_refuses_before_delegate(tmp_path):
    import shutil

    root, _, env = repo(tmp_path)
    copy = tmp_path / "engine"
    copy.mkdir()
    for name in ("pre-commit", "_load_config.py"):
        shutil.copy2(HOOK.with_name(name), copy / name)
    stage(root, "safe.md", b"harmless\n")
    p = subprocess.run(
        [str(copy / "pre-commit")], cwd=root, env=env, capture_output=True, timeout=10
    )
    assert p.returncode == 1 and b"Staged scanner not found" in p.stderr


@pytest.mark.parametrize(
    "body",
    [
        b"harmless\x00 confidential\n",
        b"harmless\xff confidential\n",
        b"harmless\x00 " + SYNTHETIC_ACCESS_KEY + b"\n",
    ],
    ids=['nul-sensitive-word', 'invalid-utf8-sensitive-word', 'nul-credential'],
)
def test_commit_message_bytes_cannot_hide_policy_matches(tmp_path, body):
    root, policy, env = repo(tmp_path)
    policy.write_text(
        policy.read_text().replace(
            "check_commit_message: false", "check_commit_message: true"
        )
    )
    msg = tmp_path / "message"
    msg.write_bytes(body)
    result = subprocess.run(
        [str(HOOK.with_name("commit-msg")), str(msg)],
        cwd=root,
        env=env,
        capture_output=True,
        timeout=10,
    )
    assert (
        result.returncode == 1
        and b"SENSITIVE PATTERN IN COMMIT MESSAGE" in result.stdout
    )


def test_message_allowlist_cannot_hide_tier_zero(tmp_path):
    root, policy, env = repo(tmp_path)
    policy.write_text(
        policy.read_text().replace(
            "check_commit_message: false", "check_commit_message: true"
        )
        + 'allowlist_lines:\n  - "^SPDX"\n'
    )
    msg = tmp_path / "message"
    msg.write_bytes(b"SPDX " + SYNTHETIC_ACCESS_KEY + b"\n")
    result = subprocess.run(
        [str(HOOK.with_name("commit-msg")), str(msg)],
        cwd=root,
        env=env,
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 1 and SYNTHETIC_ACCESS_KEY in result.stdout


def test_message_fifo_is_refused_without_waiting(tmp_path):
    root, policy, env = repo(tmp_path)
    policy.write_text(
        policy.read_text().replace(
            "check_commit_message: false", "check_commit_message: true"
        )
    )
    fifo = tmp_path / "message.fifo"
    os.mkfifo(fifo)
    result = subprocess.run(
        [str(HOOK.with_name("commit-msg")), str(fifo)],
        cwd=root,
        env=env,
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 1 and b"no clean scan" in result.stderr


def scanner_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "bounded_staged_owner", HOOK.with_name("_scan_staged.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_real_git_output_bound_is_fail_closed_and_reaped(tmp_path, monkeypatch):
    import time

    root, _, _ = repo(tmp_path)
    stage(root, "size.md", b"x" * 500 + b"\n")
    monkeypatch.chdir(root)
    module = scanner_module()
    monkeypatch.setattr(module, "MAX_DIFF_BYTES", 100)
    children = []
    actual = module.subprocess.Popen

    def capture(*args, **kwargs):
        process = actual(*args, **kwargs)
        children.append(process)
        return process

    monkeypatch.setattr(module.subprocess, "Popen", capture)
    with pytest.raises(module.ScanError, match="byte bound"):
        module.bounded_git(time.monotonic() + 5)
    assert children and all(child.poll() is not None for child in children)


def test_real_grep_timeout_reaps_owned_process(tmp_path, monkeypatch):
    import time

    module = scanner_module()
    executable = tmp_path / "grep"
    executable.write_text("#!/bin/sh\nexec /bin/sleep 5\n")
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path))
    children = []
    actual = module.subprocess.Popen

    def capture(*args, **kwargs):
        process = actual(*args, **kwargs)
        children.append(process)
        return process

    monkeypatch.setattr(module.subprocess, "Popen", capture)
    with pytest.raises(module.ScanError, match="pattern scanning failed"):
        module.grep(b"bytes\n", "bytes", time.monotonic() + 0.05)
    assert children and all(child.poll() is not None for child in children)


def test_diagnostic_is_bounded_without_losing_detection(tmp_path):
    root, _, env = repo(tmp_path)
    stage(root, "long-line.md", b"x" * 20000 + b" confidential\n")
    result = hook(root, env)
    assert result.returncode == 1 and b"SENSITIVE PATTERN DETECTED" in result.stdout
    assert b"display truncated" in result.stdout and len(result.stdout) < 18000


def test_invalid_direct_scanner_regex_never_returns_clean(tmp_path):
    root, _, env = repo(tmp_path)
    result = subprocess.run(
        [
            "python3",
            "-I",
            "-B",
            str(HOOK.with_name("_scan_staged.py")),
            "--tier0=AKIA",
            "--active=[",
            "--allowlist=",
            "--exclusion=",
        ],
        cwd=root,
        env=env,
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 2 and b"failed closed" in result.stderr


@pytest.mark.parametrize(
    "body", [b"harmless\xff confidential\n", b"harmless\xff CAF\xc3\x89\n"]
)
def test_invalid_byte_cannot_hide_match_on_same_line(tmp_path, body):
    root, _, env = repo(tmp_path)
    stage(root, "same-line.md", body)
    result = hook(root, env)
    assert result.returncode == 1 and b"SENSITIVE PATTERN DETECTED" in result.stdout


def test_invalid_byte_line_cannot_gain_allowlist_exemption(tmp_path):
    root, policy, env = repo(tmp_path)
    policy.write_text(policy.read_text() + 'allowlist_lines:\n  - "permitted"\n')
    stage(root, "same-line.md", b"permitted\xff confidential\n")
    result = hook(root, env)
    assert result.returncode == 1 and b"SENSITIVE PATTERN DETECTED" in result.stdout


def test_leading_dash_policy_is_literal_regex_not_grep_option(tmp_path):
    root, policy, env = repo(tmp_path)
    policy.write_text(
        policy.read_text().replace("- 'confidential'", "- '-confidential'")
    )
    stage(root, "same-line.md", b"-confidential\n")
    result = hook(root, env)
    assert result.returncode == 1 and b"SENSITIVE PATTERN DETECTED" in result.stdout

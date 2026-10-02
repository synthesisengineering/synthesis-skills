"""Synthetic actual-consumer controls for typed marker rules and key context."""

from pathlib import Path
import importlib.util
import json
import os
import subprocess
import time

import pytest

from test_staged_scan import repo, stage, git

SCRIPTS = Path(os.environ.get("SYNTHESIS_SCANNER_TEST_SOURCE", Path(__file__).parent))
FAMILIES = ("RSA ", "OPENSSH ", "EC ", "PGP ", "", "ENCRYPTED ")
MARKERS = ["BEGIN " + family + "PRIVATE KEY" for family in FAMILIES]
BODY = "U1lOVEhFVElDLU5PVC1BLVJFQUwtS0VZ"


def loader(name):
    spec = importlib.util.spec_from_file_location("marker_test_" + name, SCRIPTS / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def setup(tmp_path, *, personal=False, enabled=True):
    root, config, env = repo(tmp_path)
    config.write_text(
        "config_version: 2\npersonal_remote_patterns:\n  - '"
        + (".*" if personal else "never-matches")
        + "'\n"
        "tier_0_always:\n  api_keys:\n    - 'AKIA[0-9A-Z]{16}'\n  private_key_markers:\n"
        + "".join("    - '" + marker + "'\n" for marker in MARKERS)
        + "check_commit_message: "
        + str(enabled).lower()
        + "\n"
    )
    if personal:
        git(root, "remote", "add", "origin", "https://fixture.invalid/owned/repo.git")
    return root, config, env


def invoke(root, env, body=None):
    command = [str(SCRIPTS / "pre-commit")]
    if body is not None:
        msg = root / ".git/COMMIT_EDITMSG"
        msg.write_bytes(body)
        command = [str(SCRIPTS / "commit-msg"), str(msg)]
    result = subprocess.run(command, cwd=root, env=env, capture_output=True, timeout=30)
    counter = len(list(root.parent.glob("marker-command-*.json")))
    evidence = root.parent / ("marker-command-" + str(counter))
    evidence.with_suffix(".json").write_text(
        json.dumps({"argv": command, "cwd": str(root), "returncode": result.returncode})
    )
    evidence.with_suffix(".stdout").write_bytes(result.stdout)
    evidence.with_suffix(".stderr").write_bytes(result.stderr)
    return result


def assert_status(result, code):
    assert result.returncode == code, (result.stdout, result.stderr)
    if code == 1:
        assert b"SENSITIVE PATTERN" in result.stdout, (result.stdout, result.stderr)


def rule(marker=MARKERS[0]):
    return ("private_key_markers:\n  - '" + marker + "'\n").encode()


@pytest.mark.parametrize(
    "name,body",
    [
        ("policy.yaml", rule()),
        ("arbitrary.data", rule(MARKERS[1]).replace(b"'", b'"')),
        ("patterns.py", ('private_key_marker = r"' + MARKERS[2] + '"\n').encode()),
        ("skills/synthesis-git-hooks/rules.yaml", rule(MARKERS[3])),
    ],
)
def test_marker_rules_require_supported_syntax_not_filenames(tmp_path, name, body):
    root, _, env = setup(tmp_path)
    stage(root, name, body)
    assert_status(invoke(root, env), 0)


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize(
    "form", ["full", "header-only", "incomplete", "indented", "json", "escaped-ascii"]
)
def test_key_material_shapes_always_refuse(tmp_path, family, form):
    root, _, env = setup(tmp_path)
    marker = "BEGIN " + family + "PRIVATE KEY"
    if family == "PGP ":
        marker += " BLOCK"
    header = "-----" + marker + "-----\n"
    body = header + BODY + "\n-----" + marker.replace("BEGIN", "END", 1) + "-----\n"
    if form == "header-only":
        body = header
    elif form == "incomplete":
        body = header + BODY + "\n"
    elif form == "indented":
        body = "secret: |\n" + "".join("  " + line + "\n" for line in body.splitlines())
    elif form == "json":
        body = json.dumps({"secret": body}) + "\n"
    elif form == "escaped-ascii":
        body = json.dumps({"secret": body}).replace("BEGIN", "\\u0042EGIN") + "\n"
    stage(root, "data", body.encode())
    assert_status(invoke(root, env), 1)


@pytest.mark.parametrize(
    "body",
    [
        ('{"private_key_markers": "' + MARKERS[0] + '"}\n').encode(),
        ('other:\n  private_key_markers:\n    - "' + MARKERS[0] + '"\n').encode(),
        (
            'private_key_markers:\n  - "' + MARKERS[0] + '"\n  - "' + BODY + '"\n'
        ).encode(),
        ('private_key_marker = "' + MARKERS[0] + '"\n').encode(),
        ('private_key_marker = r"' + MARKERS[0] + '" + "' + BODY + '"\n').encode(),
        ('private_key_markers:\n  - "' + MARKERS[0] + "\n").encode(),
        (
            "private_key_markers:\n  - '" + MARKERS[0] + "' # " + MARKERS[1] + "\n"
        ).encode(),
    ],
)
def test_quotes_or_rule_key_alone_cannot_exempt_material(tmp_path, body):
    root, config, env = setup(tmp_path)
    config.write_text(
        config.read_text()
        + "allowlist_lines:\n  - '.*'\ndiff_exclude_paths:\n  - '.*'\n"
    )
    stage(root, "skills/synthesis-git-hooks/rules.yaml", body)
    assert_status(invoke(root, env), 1)


@pytest.mark.parametrize("custom_group", ["api_keys", "private_key_markers"])
def test_custom_patterns_are_not_subtracted_with_literal_markers(
    tmp_path, custom_group
):
    root, config, env = setup(tmp_path)
    # A custom regex overlaps the literal but remains independently mandatory.
    config.write_text(
        config.read_text().replace(
            "  " + custom_group + ":\n",
            "  " + custom_group + ":\n    - 'BEGIN.*PRIVATE KEY'\n",
        )
    )
    stage(root, "policy.yaml", rule())
    assert_status(invoke(root, env), 1)


@pytest.mark.parametrize(
    "body",
    [
        rule() + b"secret: AKIAABCDEFGHIJKLMNOP\n",
        rule()
        + ("secret: |\n  -----" + MARKERS[0] + "-----\n  " + BODY + "\n").encode(),
    ],
)
def test_rule_and_disclosure_in_same_file_still_refuse(tmp_path, body):
    root, _, env = setup(tmp_path)
    stage(root, "policy.yaml", body)
    assert_status(invoke(root, env), 1)


@pytest.mark.parametrize("catalog", [False, True])
def test_unchanged_header_with_added_body_still_refuses(tmp_path, catalog):
    root, _, env = setup(tmp_path)
    before = rule() if catalog else ("-----" + MARKERS[0] + "-----\n").encode()
    stage(root, "data", before)
    git(root, "commit", "-m", "Synthetic header baseline")
    after = before + (("  - '" + BODY + "'\n") if catalog else BODY + "\n").encode()
    stage(root, "data", after)
    assert (
        MARKERS[0].encode() not in git(root, "diff", "--cached", "-U0").split(b"@@")[-1]
    )
    assert_status(invoke(root, env), 1)


@pytest.mark.parametrize("family", FAMILIES)
def test_old_closed_key_does_not_block_unrelated_new_line(tmp_path, family):
    root, _, env = setup(tmp_path)
    marker = "BEGIN " + family + "PRIVATE KEY" + (" BLOCK" if family == "PGP " else "")
    before = (
        "-----"
        + marker
        + "-----\n"
        + BODY
        + "\n-----"
        + marker.replace("BEGIN", "END", 1)
        + "-----\n"
    ).encode()
    stage(root, "data", before)
    git(root, "commit", "-m", "Synthetic closed baseline")
    stage(root, "data", before + b"ordinary new line\n")
    assert_status(invoke(root, env), 0)


@pytest.mark.parametrize("staged_sensitive", [True, False])
def test_context_comes_from_index_not_worktree(tmp_path, staged_sensitive):
    root, _, env = setup(tmp_path)
    secret = ("-----" + MARKERS[0] + "-----\n").encode()
    stage(root, "data", secret if staged_sensitive else rule())
    (root / "data").write_bytes(rule() if staged_sensitive else secret)
    assert_status(invoke(root, env), 1 if staged_sensitive else 0)


@pytest.mark.parametrize("personal", [False, True])
@pytest.mark.parametrize("enabled", [False, True])
def test_message_material_remains_mandatory_when_optional_checks_disabled(
    tmp_path, personal, enabled
):
    root, _, env = setup(tmp_path, personal=personal, enabled=enabled)
    assert_status(invoke(root, env, ("-----" + MARKERS[4] + "-----\n").encode()), 1)
    assert_status(invoke(root, env, rule()), 0)
    assert_status(invoke(root, env, b"AKIAABCDEFGHIJKLMNOP\n"), 1)


def scan_arguments(config):
    cfg = loader("_load_config.py")
    parsed = cfg.parse_simple_yaml(config.read_text())
    return cfg.build_active_regex(parsed, "strict"), cfg.marker_scan_policy(
        parsed, "strict"
    )


def test_typed_policy_requires_exact_expression_binding(tmp_path, monkeypatch):
    root, config, _ = setup(tmp_path)
    stage(root, "data", rule())
    monkeypatch.chdir(root)
    module = loader("_scan_staged.py")
    active, typed = scan_arguments(config)
    bad = json.loads(typed)
    bad["active"] = "changed"
    with pytest.raises(module.ScanError, match="bind"):
        module.scan(active, active, "", "", marker_policy=json.dumps(bad))


def test_staged_index_replacement_refuses_after_real_capture(tmp_path, monkeypatch):
    root, config, _ = setup(tmp_path)
    stage(root, "data", rule())
    monkeypatch.chdir(root)
    module = loader("_scan_staged.py")
    active, typed = scan_arguments(config)
    original = module.bounded_git
    calls = []

    def acquire(deadline, arguments=None):
        if arguments and arguments[0] == "ls-files":
            calls.append(arguments)
            if len(calls) == 2:
                stage(root, "late", b"changed after capture\n")
        return original(deadline, arguments)

    monkeypatch.setattr(module, "bounded_git", acquire)
    with pytest.raises(module.ScanError, match="index changed"):
        module.scan(active, active, "", "", marker_policy=typed)
    assert len(calls) == 2


def test_changed_blob_bytes_cannot_claim_object_identity(tmp_path, monkeypatch):
    root, config, _ = setup(tmp_path)
    stage(root, "data", rule())
    monkeypatch.chdir(root)
    module = loader("_scan_staged.py")
    active, typed = scan_arguments(config)
    original = module.bounded_git

    def acquire(deadline, arguments=None):
        raw = original(deadline, arguments)
        return raw + b"changed\n" if arguments and arguments[0] == "cat-file" else raw

    monkeypatch.setattr(module, "bounded_git", acquire)
    with pytest.raises(module.ScanError, match="object identity"):
        module.scan(active, active, "", "", marker_policy=typed)


@pytest.mark.parametrize(
    "bound,value", [("MAX_CONTEXT_BYTES", 8), ("MAX_CONTEXT_FILES", 0)]
)
def test_marker_context_bounds_refuse_real_staged_consumer(
    tmp_path, monkeypatch, bound, value
):
    root, config, _ = setup(tmp_path)
    stage(root, "data", rule())
    monkeypatch.chdir(root)
    module = loader("_scan_staged.py")
    active, typed = scan_arguments(config)
    monkeypatch.setattr(module, bound, value)
    with pytest.raises(module.ScanError, match="bound"):
        module.scan(active, active, "", "", marker_policy=typed)


def test_marker_context_bounded_many_file_performance(tmp_path):
    root, _, env = setup(tmp_path)
    for index in range(64):
        stage(root, f"item-{index}.txt", b"ordinary data\n" * 300)
    started = time.monotonic()
    result = invoke(root, env)
    elapsed = time.monotonic() - started
    (tmp_path / "performance.json").write_text(
        json.dumps(
            {
                "files": 64,
                "bytes": 64 * len(b"ordinary data\n" * 300),
                "elapsed_seconds": elapsed,
                "ceiling_seconds": 20,
            }
        )
    )
    assert_status(result, 0)
    assert elapsed < 20


def test_template_supported_vocabulary_and_custom_policy_preservation():
    cfg = loader("_load_config.py")
    config = cfg.parse_simple_yaml(
        (SCRIPTS / "git-hook-config.example.yaml").read_text()
    )
    typed = json.loads(cfg.marker_scan_policy(config, "strict"))
    assert set(typed["markers"]) == set(MARKERS)
    custom = {"tier_0_always": {"credentials": ["CUSTOM_TOKEN", "BEGIN.*PRIVATE KEY"]}}
    typed = json.loads(cfg.marker_scan_policy(custom, "strict"))
    assert (
        typed["markers"] == []
        and typed["credentials"] == "CUSTOM_TOKEN|BEGIN.*PRIVATE KEY"
    )


def test_bare_end_words_do_not_close_an_unchanged_armored_header(tmp_path):
    root, _, env = setup(tmp_path)
    before = (
        "-----" + MARKERS[0] + "----- # " + MARKERS[0].replace("BEGIN", "END", 1) + "\n"
    ).encode()
    stage(root, "data", before)
    git(root, "commit", "-m", "Synthetic header comment baseline")
    stage(root, "data", before + (BODY + "\n").encode())
    assert_status(invoke(root, env), 1)


def test_old_complete_quoted_key_does_not_block_new_unrelated_line(tmp_path):
    root, _, env = setup(tmp_path)
    body = (
        "-----"
        + MARKERS[0]
        + "-----\n"
        + BODY
        + "\n-----"
        + MARKERS[0].replace("BEGIN", "END", 1)
        + "-----\n"
    )
    before = (json.dumps({"secret": body}) + "\n").encode()
    stage(root, "data", before)
    git(root, "commit", "-m", "Synthetic quoted baseline")
    stage(root, "data", before + b"ordinary\n")
    assert_status(invoke(root, env), 0)


def test_captured_parser_ignores_poisoned_pyc_with_positive_control(
    tmp_path, monkeypatch
):
    import py_compile
    import shutil
    import struct
    import sys

    root, _, env = setup(tmp_path)
    engine = tmp_path / "engine"
    engine.mkdir()
    for name in ("pre-commit", "commit-msg", "_load_config.py", "_scan_staged.py"):
        shutil.copy2(SCRIPTS / name, engine / name)
    event = tmp_path / "poison-events"
    poison = tmp_path / "poison.py"
    poison.write_text(
        f"from pathlib import Path\nPath({str(event)!r}).write_text('executed')\n"
    )
    real = engine / "_load_config.py"
    cache = Path(importlib.util.cache_from_source(str(real)))
    cache.parent.mkdir(parents=True)
    py_compile.compile(str(poison), cfile=str(cache), doraise=True)
    compiled = cache.read_bytes()
    meta = real.stat()
    cache.write_bytes(
        compiled[:4]
        + struct.pack("<III", 0, int(meta.st_mtime), meta.st_size)
        + compiled[16:]
    )
    # Other suites may already activate source-only imports in this process.
    # Prove that the poison is executable using a fresh ordinary interpreter;
    # do not disable the production loader policy to make a test pass.
    positive = subprocess.run(
        [
            sys.executable,
            "-B",
            "-I",
            "-S",
            # Isolated mode ignores PYTHONPYCACHEPREFIX. Bind the positive
            # control to the same cache namespace where the fixture was built.
            *(["-X", f"pycache_prefix={sys.pycache_prefix}"] if sys.pycache_prefix else []),
            "-c",
            "import importlib.util,sys; "
            "s=importlib.util.spec_from_file_location('poison_positive_control',sys.argv[1]); "
            "m=importlib.util.module_from_spec(s);s.loader.exec_module(m)",
            str(real),
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert positive.returncode == 0, positive.stderr
    assert event.read_text() == "executed"
    event.rename(tmp_path / "poison-positive-control-retained")
    monkeypatch.setitem(invoke.__globals__, "SCRIPTS", engine)
    stage(root, "rules.yaml", rule())
    assert_status(invoke(root, env), 0)
    assert not event.exists()


def test_changed_parser_source_refuses_before_compilation(tmp_path, monkeypatch):
    import shutil

    engine = tmp_path / "engine"
    engine.mkdir()
    for name in ("_load_config.py", "_scan_staged.py"):
        shutil.copy2(SCRIPTS / name, engine / name)
    module = loader("_scan_staged.py")
    module.__file__ = str(engine / "_scan_staged.py")
    source = engine / "_load_config.py"
    original = source.read_bytes()
    (tmp_path / "parser-before.py").write_bytes(original)
    inode = source.stat().st_ino
    real_read = module.os.read
    raced = []

    def read(fd, count):
        data = real_read(fd, count)
        if data and os.fstat(fd).st_ino == inode and not raced:
            source.write_bytes(original + b"\n# synthetic changed source\n")
            raced.append(True)
        return data

    monkeypatch.setattr(module.os, "read", read)
    with pytest.raises(module.ScanError, match="source changed"):
        module.load_rule_parser(time.monotonic() + 5)
    assert raced


def test_missing_parser_source_has_no_cache_fallback(tmp_path):
    import shutil

    root, config, env = setup(tmp_path)
    engine = tmp_path / "engine"
    engine.mkdir()
    shutil.copy2(SCRIPTS / "_scan_staged.py", engine / "_scan_staged.py")
    stage(root, "rules.yaml", rule())
    active, typed = scan_arguments(config)
    result = subprocess.run(
        [
            os.environ.get("PYTHON", "python3"),
            "-I",
            "-B",
            str(engine / "_scan_staged.py"),
            "--tier0=" + active,
            "--active=" + active,
            "--allowlist=",
            "--exclusion=",
            "--marker-policy=" + typed,
        ],
        cwd=root,
        env=env,
        capture_output=True,
        timeout=10,
    )
    (tmp_path / "missing-parser.stdout").write_bytes(result.stdout)
    (tmp_path / "missing-parser.stderr").write_bytes(result.stderr)
    assert result.returncode == 2 and b"failed closed" in result.stderr


@pytest.mark.parametrize("empty", ["[]", "[ ]", "[    ] # empty configuration list"])
def test_empty_sequence_mapping_values_preserve_complete_rules(tmp_path, empty):
    root, config, env = setup(tmp_path)
    config.write_text(config.read_text() + "diff_exclude_paths: " + empty + "\n")
    body = (
        rule() + ("tier_1_strict_only:\n  confidential_names: " + empty + "\n").encode()
    )
    parsed = loader("_load_config.py").parse_simple_yaml(body.decode())
    assert parsed["tier_1_strict_only"]["confidential_names"] == []
    stage(root, "historical-policy.data", body)
    assert_status(invoke(root, env), 0)
    assert_status(invoke(root, env, body), 0)


@pytest.mark.parametrize("text", ["'[]'", '"[]"'])
def test_quoted_empty_sequence_remains_string(text):
    assert (
        loader("_load_config.py").parse_simple_yaml("value: " + text)["value"] == "[]"
    )


@pytest.mark.parametrize(
    "neighbor",
    [
        "other: [value]\n",
        "other: {}\n",
        "other: [[],]\n",
        "other: &anchor []\n",
        "other: *anchor\n",
        "other: [] trailing\n",
        "other: [\n]\n",
        "other: [\t]\n",
        "other:\n  - []\n",
        "other: []\n  - value\n",
        "other: []\nother: []\n",
    ],
)
def test_empty_sequence_does_not_expand_other_yaml_grammar(tmp_path, neighbor):
    root, _, env = setup(tmp_path)
    body = rule() + neighbor.encode()
    parser = loader("_load_config.py")
    with pytest.raises(parser.ConfigError):
        parser.parse_simple_yaml(body.decode())
    stage(root, "policy.yaml", body)
    assert_status(invoke(root, env), 1)


@pytest.mark.parametrize(
    "secret",
    [
        b"secret: " + b"AKIA" + b"ABCDEFGHIJKLMNOP\n",
        b"secret: CUSTOM_CREDENTIAL_VALUE\n",
        ("secret: |\n  -----" + MARKERS[0] + "-----\n  " + BODY + "\n").encode(),
        ("  - '" + BODY + "'\n").encode(),
    ],
)
def test_empty_sequence_rules_do_not_hide_credentials_or_mixed_material(
    tmp_path, secret
):
    root, config, env = setup(tmp_path, personal=True, enabled=False)
    config.write_text(
        config.read_text().replace(
            "  api_keys:\n", "  api_keys:\n    - 'CUSTOM_CREDENTIAL_VALUE'\n"
        )
        + "allowlist_lines:\n  - '.*'\ndiff_exclude_paths:\n  - '.*'\n"
    )
    body = b"empty: []\n" + rule() + secret
    stage(root, "policy.yaml", body)
    assert_status(invoke(root, env), 1)
    assert_status(invoke(root, env, body), 1)


@pytest.mark.parametrize("catalog", [False, True])
def test_empty_sequence_old_header_new_body_is_still_material(tmp_path, catalog):
    root, _, env = setup(tmp_path)
    before = b"empty: []\n" + (
        rule() if catalog else ("-----" + MARKERS[0] + "-----\n").encode()
    )
    stage(root, "policy.yaml", before)
    git(root, "commit", "-m", "Synthetic empty-list header baseline")
    body = (("  - '" + BODY + "'\n") if catalog else BODY + "\n").encode()
    stage(root, "policy.yaml", before + body)
    patch = git(root, "diff", "--cached", "-U0")
    assert MARKERS[0].encode() not in patch.split(b"@@")[-1]
    assert_status(invoke(root, env), 1)


@pytest.mark.parametrize("group", ["api_keys", "private_key_markers"])
def test_empty_sequence_does_not_remove_overlapping_custom_patterns(tmp_path, group):
    root, config, env = setup(tmp_path)
    config.write_text(
        config.read_text().replace(
            "  " + group + ":\n", "  " + group + ":\n    - 'BEGIN.*PRIVATE KEY'\n"
        )
    )
    stage(root, "policy.yaml", b"empty: []\n" + rule())
    assert_status(invoke(root, env), 1)


@pytest.mark.parametrize("suffix", [b"", b"secret: " + b"AKIA" + b"ABCDEFGHIJKLMNOP\n"])
def test_empty_sequence_does_not_erase_other_configured_credential_groups(
    tmp_path, suffix
):
    root, config, env = setup(tmp_path)
    config.write_text(
        config.read_text().replace(
            "tier_0_always:\n", "tier_0_always:\n  inactive_group: []\n"
        )
        + "tier_1_strict_only:\n  confidential_names: []\n"
    )
    parsed = loader("_load_config.py").parse_simple_yaml(config.read_text())
    active = loader("_load_config.py").build_active_regex(parsed, "strict")
    assert "AKIA[0-9A-Z]{16}" in active
    stage(root, "policy.yaml", b"empty: []\n" + rule() + suffix)
    assert_status(invoke(root, env), 1 if suffix else 0)

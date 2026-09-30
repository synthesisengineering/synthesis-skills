"""Independent actual-consumer controls. All material is synthetic and unusable."""

import io
import zipfile
import pytest

import test_marker_rules as helper
from test_staged_scan import git, stage

MARKER = b"BEGIN RSA PRIVATE KEY"
HEADER = b"-----" + MARKER + b"-----\n"
BODY = b"U1lOVEhFVElDLU5PVC1BLVJFQUwtS0VZ\n"
FOOTER = b"-----END RSA PRIVATE KEY-----\n"


@pytest.mark.parametrize(
    "intervening",
    [
        b"# Documentation example: -----END RSA PRIVATE KEY-----\n",
        b'footer_example = "-----END RSA PRIVATE KEY-----"\n',
        b"-----END RSA PRIVATE KEY BLOCK-----\n",
    ],
)
def test_unproven_footer_cannot_close_existing_private_region(tmp_path, intervening):
    root, _, env = helper.setup(tmp_path)
    before = HEADER + intervening
    stage(root, "material.txt", before)
    git(root, "commit", "-m", "Synthetic interval baseline")
    stage(root, "material.txt", before + BODY)
    patch = git(root, "diff", "--cached", "-U0")
    (tmp_path / "captured.patch").write_bytes(patch)
    assert b"+" + BODY.strip() in patch
    assert b"+-----BEGIN" not in patch
    helper.assert_status(helper.invoke(root, env), 1)


@pytest.mark.parametrize(
    "before,after,expected",
    [
        (HEADER, BODY, 1),
        (HEADER + BODY + FOOTER, b"ordinary text\n", 0),
        (HEADER + b"# END RSA PRIVATE KEY\n", BODY, 1),
        (HEADER + b"-----END EC PRIVATE KEY-----\n", BODY, 1),
    ],
)
def test_region_controls(tmp_path, before, after, expected):
    root, _, env = helper.setup(tmp_path)
    stage(root, "data", before)
    git(root, "commit", "-m", "Synthetic region control")
    stage(root, "data", before + after)
    helper.assert_status(helper.invoke(root, env), expected)


@pytest.mark.parametrize("kind", ["nul-prefix", "stored-zip", "git-binary-attribute"])
def test_binary_diff_cannot_suppress_added_plaintext_marker(tmp_path, kind):
    root, _, env = helper.setup(tmp_path)
    data = HEADER + BODY + FOOTER
    if kind == "nul-prefix":
        data = b"\0fixture\n" + data
    elif kind == "stored-zip":
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_STORED) as z:
            z.writestr("synthetic.pem", data)
        data = stream.getvalue()
    elif kind == "git-binary-attribute":
        stage(root, ".gitattributes", b"data -diff\n")
        git(root, "commit", "-m", "Synthetic binary attribute")
    stage(root, "data", data)
    patch = git(root, "diff", "--cached", "-U0")
    (tmp_path / "captured.patch").write_bytes(patch)
    assert b"Binary files" in patch, patch
    assert HEADER in git(root, "show", ":data")
    helper.assert_status(helper.invoke(root, env), 1)


@pytest.mark.parametrize(
    "body",
    [
        b'private_key_markers:\n  - "BEGIN RSA PRIVATE KEY"\n',
        b'private_key_marker = r"BEGIN ENCRYPTED PRIVATE KEY"\n',
    ],
)
def test_complete_detection_rule_remains_clean(tmp_path, body):
    root, _, env = helper.setup(tmp_path)
    stage(root, "unrelated-name", body)
    helper.assert_status(helper.invoke(root, env), 0)


@pytest.mark.parametrize(
    "body",
    [
        b'private_key_markers:\n  - "BEGIN RSA PRIVATE KEY"\n  - "'
        + BODY.strip()
        + b'"\n',
        b'private_key_markers:\n  - "BEGIN RSA PRIVATE KEY"\nsecret: AKIAABCDEFGHIJKLMNOP\n',
        b'private_key_markers:\n  - "BEGIN RSA PRIVATE KEY"\nother:\n  private_key_markers:\n    - "BEGIN ENCRYPTED PRIVATE KEY"\n',
    ],
)
def test_mixed_or_unproven_rule_stays_protected(tmp_path, body):
    root, config, env = helper.setup(tmp_path, personal=True, enabled=False)
    config.write_text(
        config.read_text()
        + "allowlist_lines:\n  - '.*'\ndiff_exclude_paths:\n  - '.*'\n"
    )
    stage(root, "policy.yaml", body)
    helper.assert_status(helper.invoke(root, env), 1)


@pytest.mark.parametrize(
    "personal,enabled", [(True, False), (False, False), (True, True), (False, True)]
)
def test_actual_message_tier0_always_retained(tmp_path, personal, enabled):
    root, _, env = helper.setup(tmp_path, personal=personal, enabled=enabled)
    helper.assert_status(
        helper.invoke(root, env, b"-----BEGIN ENCRYPTED PRIVATE KEY-----\n"), 1
    )
    helper.assert_status(helper.invoke(root, env, b"AKIAABCDEFGHIJKLMNOP\n"), 1)


@pytest.mark.parametrize("group", ["private_key_markers", "custom_user_patterns"])
def test_overlapping_user_patterns_remain_independent(tmp_path, group):
    root, config, env = helper.setup(tmp_path)
    if group == "private_key_markers":
        config.write_text(
            config.read_text().replace(
                "  private_key_markers:\n",
                "  private_key_markers:\n    - 'BEGIN.*PRIVATE KEY'\n",
            )
        )
    else:
        config.write_text(
            config.read_text().replace(
                "tier_0_always:\n",
                "tier_0_always:\n  custom_user_patterns:\n    - 'BEGIN.*PRIVATE KEY'\n",
            )
        )
    stage(root, "data", b'private_key_markers:\n  - "BEGIN RSA PRIVATE KEY"\n')
    helper.assert_status(helper.invoke(root, env), 1)


@pytest.mark.parametrize(
    "nested",
    [
        b"-----BEGIN EC PRIVATE KEY-----\n-----END EC PRIVATE KEY-----\n",
        b'{"secret": "-----BEGIN RSA PRIVATE KEY-----\\nfixture\\n-----END RSA PRIVATE KEY-----\\n"}\n',
    ],
)
def test_nested_material_cannot_close_the_outer_region(tmp_path, nested):
    root, _, env = helper.setup(tmp_path)
    before = HEADER + nested
    stage(root, "data", before)
    git(root, "commit", "-m", "Synthetic nested region")
    stage(root, "data", before + BODY)
    helper.assert_status(helper.invoke(root, env), 1)

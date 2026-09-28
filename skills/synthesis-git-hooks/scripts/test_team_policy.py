from pathlib import Path
import sys
import json
import hashlib
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "skills/synthesis-git-hooks/scripts"))
import _load_config as policy  # noqa: E402 - source-bound import follows path/bootstrap initialization
import _scan_staged as scanner  # noqa: E402 - source-bound import follows path/bootstrap initialization


def fragment(tmp_path):
    p = tmp_path / "team.json"
    p.write_text(
        json.dumps(
            {
                "schema": 1,
                "organization": "synthetic-team",
                "repository_prefixes": ["https://git.example/team/"],
                "mandatory_patterns": ["SYNTHETIC_CONFIDENTIAL"],
            }
        )
    )
    return p, {
        "team_policy_files": {str(p): hashlib.sha256(p.read_bytes()).hexdigest()},
        "tier_0_always": ["SYNTHETIC_SECRET"],
        "tier_1_strict_only": ["BASE_PRIVATE"],
        "personal_remote_patterns": ["git.example/"],
        "allowlist_lines": [".*"],
        "diff_exclude_paths": [".*"],
    }


def test_additive_layer_cannot_lose_private_guards_or_demote_team(tmp_path):
    p, c = fragment(tmp_path)
    out = policy.apply_team_policy(c, ["https://git.example/team/repo.git"])
    assert (
        out["tier_0_always"] == c["tier_0_always"]
        and out["allowlist_lines"] == c["allowlist_lines"]
    )
    assert policy.classify_repo(out, ["https://git.example/team/repo.git"]) == "strict"
    assert out["_team_mandatory_regex"] == "SYNTHETIC_CONFIDENTIAL"
    assert "_team_mandatory_regex" not in c
    assert (
        policy.apply_team_policy(c, ["https://git.example/personal/repo.git"])[
            "_team_mandatory_regex"
        ]
        == ""
    )


def test_team_mandatory_scan_ignores_personal_exemptions(tmp_path):
    p = tmp_path / "message"
    p.write_text("SYNTHETIC_CONFIDENTIAL\n")
    assert b"SYNTHETIC_CONFIDENTIAL" in scanner.scan(
        "SECRET", "BASE_PRIVATE", ".*", ".*", str(p), mandatory="SYNTHETIC_CONFIDENTIAL"
    )
    p.write_text("ordinary clean message\n")
    assert (
        scanner.scan(
            "SECRET",
            "BASE_PRIVATE",
            ".*",
            ".*",
            str(p),
            mandatory="SYNTHETIC_CONFIDENTIAL",
        )
        == b""
    )


@pytest.mark.parametrize(
    "change", ["digest", "link", "allowance", "duplicate", "regex", "foreign-mode"]
)
def test_malformed_or_tampered_layer_refuses(tmp_path, change):
    p, c = fragment(tmp_path)
    if change == "digest":
        p.write_text(p.read_text() + " ")
    elif change == "link":
        q = tmp_path / "target"
        p.rename(q)
        p.symlink_to(q)
    elif change == "foreign-mode":
        p.chmod(0o666)
    elif change == "duplicate":
        p.write_text('{"schema":1,"schema":1}')
        c["team_policy_files"][str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
    else:
        d = json.loads(p.read_text())
        d["allowlist_lines"] = [".*"] if change == "allowance" else []
        if change == "regex":
            d.pop("allowlist_lines")
            d["mandatory_patterns"] = ["["]
        p.write_text(json.dumps(d))
        c["team_policy_files"][str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
    with pytest.raises(policy.ConfigError):
        policy.apply_team_policy(c, ["https://git.example/team/repo.git"])


def test_unknown_remote_cannot_choose_aweaker_layer(tmp_path):
    p, c = fragment(tmp_path)
    assert (
        policy.apply_team_policy(c, [])["_team_mandatory_regex"]
        == "SYNTHETIC_CONFIDENTIAL"
    )


def test_real_precommit_applies_team_restrictions_before_personal_exemptions(tmp_path):
    import subprocess
    from test_pre_commit import repository, HOOK

    root, env = repository(tmp_path)
    subprocess.run(
        ["git", "remote", "set-url", "origin", "https://git.example/team/repo.git"],
        cwd=root,
        check=True,
        capture_output=True,
        timeout=10,
    )
    fragment_path, c = fragment(tmp_path)
    config = Path(env["SYNTHESIS_GIT_HOOK_CONFIG"])
    config.write_text(
        "config_version: 2\npersonal_remote_patterns:\n  - git.example/\ntier_0_always:\n  - SECRET_VALUE\ntier_1_strict_only:\n  - BASE_PRIVATE\nallowlist_lines:\n  - .*\ndiff_exclude_paths:\n  - .*\ncheck_commit_message: false\nteam_policy_files:\n  "
        + str(fragment_path)
        + ": "
        + c["team_policy_files"][str(fragment_path)]
        + "\n"
    )
    target = root / "new.txt"
    target.write_text("SYNTHETIC_CONFIDENTIAL\n")
    subprocess.run(
        ["git", "add", "new.txt"], cwd=root, check=True, capture_output=True, timeout=10
    )
    result = subprocess.run(
        [str(HOOK)], cwd=root, env=env, text=True, capture_output=True, timeout=20
    )
    assert result.returncode == 1 and "SENSITIVE PATTERN DETECTED" in result.stdout, (
        result.stderr
    )
    target.write_text("ordinary synthetic content\n")
    subprocess.run(
        ["git", "add", "new.txt"], cwd=root, check=True, capture_output=True, timeout=10
    )
    clean = subprocess.run(
        [str(HOOK)], cwd=root, env=env, text=True, capture_output=True, timeout=20
    )
    assert clean.returncode == 0, clean.stderr + clean.stdout
    fragment_path.write_text(fragment_path.read_text() + " ")
    corrupt = subprocess.run(
        [str(HOOK)], cwd=root, env=env, text=True, capture_output=True, timeout=20
    )
    assert corrupt.returncode != 0 and "team policy refused" in corrupt.stderr, (
        corrupt.stderr + corrupt.stdout
    )


@pytest.mark.parametrize("optional_checks", [True, False])
def test_real_commit_message_keeps_mandatory_team_policy(tmp_path, optional_checks):
    import subprocess
    from test_pre_commit import repository, SCRIPT_DIR

    root, env = repository(tmp_path)
    subprocess.run(
        ["git", "remote", "set-url", "origin", "https://git.example/team/repo.git"],
        cwd=root, check=True, capture_output=True, timeout=10,
    )
    fragment_path, config = fragment(tmp_path)
    Path(env["SYNTHESIS_GIT_HOOK_CONFIG"]).write_text(
        "config_version: 2\npersonal_remote_patterns:\n  - git.example/\n"
        "tier_0_always:\n  - SYNTHETIC_SECRET\ntier_1_strict_only:\n  - BASE_PRIVATE\n"
        "allowlist_lines:\n  - .*\ndiff_exclude_paths:\n  - .*\n"
        + "check_commit_message: " + str(optional_checks).lower()
        + "\nteam_policy_files:\n  " + str(fragment_path) + ": "
        + config["team_policy_files"][str(fragment_path)] + "\n"
    )
    message = root / ".git/COMMIT_EDITMSG"

    def invoke(text):
        message.write_text(text)
        return subprocess.run(
            [str(SCRIPT_DIR / "commit-msg"), str(message)], cwd=root, env=env,
            text=True, capture_output=True, timeout=20,
        )

    forbidden = invoke("SYNTHETIC_CONFIDENTIAL\n")
    assert forbidden.returncode == 1, forbidden.stderr + forbidden.stdout
    assert "SENSITIVE PATTERN IN COMMIT MESSAGE" in forbidden.stdout
    clean = invoke("Ordinary synthetic maintenance\n")
    assert clean.returncode == 0, clean.stderr + clean.stdout
    fragment_path.write_text(fragment_path.read_text() + " ")
    corrupt = invoke("Ordinary synthetic maintenance\n")
    assert corrupt.returncode != 0 and "team policy refused" in corrupt.stderr

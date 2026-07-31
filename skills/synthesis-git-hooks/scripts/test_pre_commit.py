from __future__ import annotations

import os
import subprocess
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
HOOK = SCRIPT_DIR / "pre-commit"


def run(repository: Path, *command: str, env: dict[str, str] | None = None):
    return subprocess.run(
        command,
        cwd=repository,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def policy(path: Path) -> None:
    path.write_text(
        """\
config_version: 1
personal_remote_patterns:
  - '[:/]never-matches/'
tier_0_always:
  credentials:
    - 'AKIA[0-9A-Z]{16}'
tier_1_strict_only:
  confidentiality:
    - 'confidential'
check_commit_message: false
""",
        encoding="utf-8",
    )


def repository(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    root = tmp_path / "repo"
    root.mkdir()
    assert run(root, "git", "init").returncode == 0
    assert run(root, "git", "config", "user.name", "Test").returncode == 0
    assert run(root, "git", "config", "user.email", "test@example.com").returncode == 0
    assert (
        run(
            root,
            "git",
            "remote",
            "add",
            "origin",
            "https://github.com/example/public-repo.git",
        ).returncode
        == 0
    )
    (root / "CLAUDE.md").write_text(
        "# Rules\n\nDo not add confidential material.\n",
        encoding="utf-8",
    )
    assert run(root, "git", "add", "CLAUDE.md").returncode == 0
    assert (
        run(
            root,
            "git",
            "-c",
            "core.hooksPath=/dev/null",
            "commit",
            "-m",
            "Initial",
        ).returncode
        == 0
    )
    config = tmp_path / "policy.yaml"
    policy(config)
    environment = dict(os.environ)
    environment["SYNTHESIS_GIT_HOOK_CONFIG"] = str(config)
    return root, environment


def test_exact_instruction_copy_is_not_rescanned(tmp_path: Path) -> None:
    root, environment = repository(tmp_path)
    (root / "AGENTS.md").write_bytes((root / "CLAUDE.md").read_bytes())
    (root / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
    assert run(root, "git", "add", "AGENTS.md", "CLAUDE.md").returncode == 0

    completed = run(root, str(HOOK), env=environment)

    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_genuinely_new_sensitive_line_still_blocks(tmp_path: Path) -> None:
    root, environment = repository(tmp_path)
    (root / "NEW.md").write_text("New confidential material.\n", encoding="utf-8")
    assert run(root, "git", "add", "NEW.md").returncode == 0

    completed = run(root, str(HOOK), env=environment)

    assert completed.returncode == 1
    assert "SENSITIVE PATTERN DETECTED" in completed.stdout


import importlib.util
import sys

SIDECAR_PATH = SCRIPT_DIR / "_load_config.py"
SPEC = importlib.util.spec_from_file_location("load_config", SIDECAR_PATH)
assert SPEC and SPEC.loader
SIDECAR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = SIDECAR
SPEC.loader.exec_module(SIDECAR)


def surface_policy(path: Path, ledger: Path | None) -> None:
    ledger_line = f"disclosure_ledger: '{ledger}'\n" if ledger else ""
    path.write_text(
        f"""\
config_version: 1
personal_remote_patterns:
  - '[:/]example-person/'
strict_repo_patterns:
  - '[:/]example-person/public-oss(\\.git)?$'
public_surface_patterns:
  - '[:/]example-person/personal-site(\\.git)?$'
  - '[:/]example-sites/'
{ledger_line}tier_0_always:
  credentials:
    - 'AKIA[0-9A-Z]{{16}}'
tier_1_strict_only:
  confidentiality:
    - 'confidential'
  confidential_names:
    - 'example-client'
    - 'example-vendor'
check_commit_message: false
""",
        encoding="utf-8",
    )


def write_ledger(path: Path) -> None:
    path.write_text(
        """\
ledger_version: 1
entities:
  example-client:
    kind: organization
    relationship: former employer
    registers:
      - biography
    hook_patterns:
      - 'example-client'
    evidence:
      - 'personal-site/src/config/site.ts: bio names example-client'
""",
        encoding="utf-8",
    )


def load(config_path: Path) -> dict:
    return SIDECAR.parse_simple_yaml(config_path.read_text())


def test_classification_precedence(tmp_path: Path) -> None:
    config_path = tmp_path / "policy.yaml"
    ledger = tmp_path / "ledger.yaml"
    write_ledger(ledger)
    surface_policy(config_path, ledger)
    config = load(config_path)

    classify = SIDECAR.classify_repo
    oss = ["https://github.com/example-person/public-oss.git"]
    site = ["https://github.com/example-person/personal-site.git"]
    org_site = ["https://github.com/example-sites/blog.git"]
    private = ["https://github.com/example-person/notes.git"]
    mixed = site + ["https://github.com/elsewhere/mirror.git"]

    assert classify(config, oss) == "strict"
    assert classify(config, site) == "public-surface"
    assert classify(config, org_site) == "public-surface"
    assert classify(config, private) == "personal"
    assert classify(config, mixed) == "strict"
    assert classify(config, []) == "strict"


def test_public_surface_regex_subtracts_only_ledgered_names(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "policy.yaml"
    ledger = tmp_path / "ledger.yaml"
    write_ledger(ledger)
    surface_policy(config_path, ledger)
    config = load(config_path)

    surface = SIDECAR.build_active_regex(config, "public-surface")
    assert "example-client" not in surface
    assert "example-vendor" in surface
    assert "confidential" in surface
    assert "AKIA" in surface

    strict = SIDECAR.build_active_regex(config, "strict")
    assert "example-client" in strict

    personal = SIDECAR.build_active_regex(config, "personal")
    assert "example-client" not in personal
    assert "confidential" not in personal
    assert "AKIA" in personal


def test_ledger_failures_are_config_errors(tmp_path: Path) -> None:
    config_path = tmp_path / "policy.yaml"
    missing = tmp_path / "missing-ledger.yaml"
    surface_policy(config_path, missing)
    config = load(config_path)

    try:
        SIDECAR.build_active_regex(config, "public-surface")
        raise AssertionError("missing ledger must fail closed")
    except SIDECAR.ConfigError:
        pass

    no_evidence = tmp_path / "no-evidence.yaml"
    no_evidence.write_text(
        """\
ledger_version: 1
entities:
  example-client:
    hook_patterns:
      - 'example-client'
""",
        encoding="utf-8",
    )
    surface_policy(config_path, no_evidence)
    config = load(config_path)
    try:
        SIDECAR.build_active_regex(config, "public-surface")
        raise AssertionError("evidence-free entity must fail closed")
    except SIDECAR.ConfigError:
        pass

    # Strict and personal classes never read the ledger, so a broken ledger
    # must not break them.
    assert "example-client" in SIDECAR.build_active_regex(config, "strict")
    assert "AKIA" in SIDECAR.build_active_regex(config, "personal")


def surface_repository(
    tmp_path: Path, remote: str
) -> tuple[Path, dict[str, str]]:
    root = tmp_path / "surface-repo"
    root.mkdir()
    assert run(root, "git", "init").returncode == 0
    assert run(root, "git", "config", "user.name", "Test").returncode == 0
    assert (
        run(root, "git", "config", "user.email", "test@example.com").returncode
        == 0
    )
    assert run(root, "git", "remote", "add", "origin", remote).returncode == 0
    (root / "README.md").write_text("# Site\n", encoding="utf-8")
    assert run(root, "git", "add", "README.md").returncode == 0
    assert (
        run(
            root,
            "git",
            "-c",
            "core.hooksPath=/dev/null",
            "commit",
            "-m",
            "Initial",
        ).returncode
        == 0
    )
    config_path = tmp_path / "surface-policy.yaml"
    ledger = tmp_path / "surface-ledger.yaml"
    write_ledger(ledger)
    surface_policy(config_path, ledger)
    environment = dict(os.environ)
    environment["SYNTHESIS_GIT_HOOK_CONFIG"] = str(config_path)
    return root, environment


def test_hook_allows_ledgered_name_on_public_surface(tmp_path: Path) -> None:
    root, environment = surface_repository(
        tmp_path, "https://github.com/example-person/personal-site.git"
    )
    (root / "bio.md").write_text(
        "I led technology at example-client for five years.\n",
        encoding="utf-8",
    )
    assert run(root, "git", "add", "bio.md").returncode == 0

    completed = run(root, str(HOOK), env=environment)

    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_hook_blocks_unledgered_name_on_public_surface(tmp_path: Path) -> None:
    root, environment = surface_repository(
        tmp_path, "https://github.com/example-person/personal-site.git"
    )
    (root / "bio.md").write_text(
        "We also worked with example-vendor on the rollout.\n",
        encoding="utf-8",
    )
    assert run(root, "git", "add", "bio.md").returncode == 0

    completed = run(root, str(HOOK), env=environment)

    assert completed.returncode == 1
    assert "SENSITIVE PATTERN DETECTED" in completed.stdout


def test_hook_blocks_ledgered_name_in_forced_strict_repo(tmp_path: Path) -> None:
    root, environment = surface_repository(
        tmp_path, "https://github.com/example-person/public-oss.git"
    )
    (root / "docs.md").write_text(
        "Built while at example-client.\n", encoding="utf-8"
    )
    assert run(root, "git", "add", "docs.md").returncode == 0

    completed = run(root, str(HOOK), env=environment)

    assert completed.returncode == 1
    assert "SENSITIVE PATTERN DETECTED" in completed.stdout


def test_hook_fails_closed_when_surface_ledger_missing(tmp_path: Path) -> None:
    root, environment = surface_repository(
        tmp_path, "https://github.com/example-person/personal-site.git"
    )
    config_path = Path(environment["SYNTHESIS_GIT_HOOK_CONFIG"])
    surface_policy(config_path, tmp_path / "vanished-ledger.yaml")
    (root / "bio.md").write_text("Harmless line.\n", encoding="utf-8")
    assert run(root, "git", "add", "bio.md").returncode == 0

    completed = run(root, str(HOOK), env=environment)

    assert completed.returncode == 1
    assert "policy engine unavailable" in completed.stderr


def test_doctor_flags_stale_ledger_allowance(tmp_path: Path) -> None:
    config_path = tmp_path / "policy.yaml"
    ledger = tmp_path / "ledger.yaml"
    ledger.write_text(
        """\
ledger_version: 1
entities:
  example-client:
    hook_patterns:
      - 'name-not-in-tier-one'
    evidence:
      - 'site.ts: bio'
""",
        encoding="utf-8",
    )
    surface_policy(config_path, ledger)

    completed = subprocess.run(
        [sys.executable, str(SIDECAR_PATH), "--config", str(config_path), "--doctor"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert "stale or typo" in completed.stdout
    assert completed.returncode == 1

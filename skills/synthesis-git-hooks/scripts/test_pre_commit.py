from __future__ import annotations

import os
import shutil
import shlex
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
config_version: 2
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
config_version: 2
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


def test_ledger_allowance_must_be_an_eligible_identity_pattern(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "policy.yaml"
    ledger = tmp_path / "ledger.yaml"
    ledger.write_text(
        """\
ledger_version: 1
entities:
  example-client:
    registers:
      - biography
    hook_patterns:
      - 'name-not-in-tier-one'
    evidence:
      - 'site.ts: bio'
""",
        encoding="utf-8",
    )
    surface_policy(config_path, ledger)
    config = load(config_path)

    try:
        SIDECAR.build_active_regex(config, "public-surface")
        raise AssertionError("ineligible allowance must fail closed")
    except SIDECAR.ConfigError as exc:
        assert "allowance-eligible" in str(exc)


def test_ledger_cannot_subtract_a_topic_pattern(tmp_path: Path) -> None:
    """An allowance may never disable NDA/compensation-class detection."""
    config_path = tmp_path / "policy.yaml"
    ledger = tmp_path / "ledger.yaml"
    ledger.write_text(
        """\
ledger_version: 1
entities:
  example-client:
    registers:
      - biography
    hook_patterns:
      - 'confidential'
    evidence:
      - 'site.ts: bio'
""",
        encoding="utf-8",
    )
    surface_policy(config_path, ledger)
    config = load(config_path)

    try:
        SIDECAR.build_active_regex(config, "public-surface")
        raise AssertionError("topic-pattern allowance must fail closed")
    except SIDECAR.ConfigError as exc:
        assert "allowance-eligible" in str(exc)


def test_ledger_registers_are_validated(tmp_path: Path) -> None:
    config_path = tmp_path / "policy.yaml"
    ledger = tmp_path / "ledger.yaml"
    ledger.write_text(
        """\
ledger_version: 1
entities:
  example-client:
    registers:
      - operational
    hook_patterns:
      - 'example-client'
    evidence:
      - 'site.ts: bio'
""",
        encoding="utf-8",
    )
    surface_policy(config_path, ledger)
    config = load(config_path)

    try:
        SIDECAR.build_active_regex(config, "public-surface")
        raise AssertionError("forbidden register must fail closed")
    except SIDECAR.ConfigError as exc:
        assert "approved vocabulary" in str(exc)


def test_v1_config_is_refused_by_v2_engine(tmp_path: Path) -> None:
    config_path = tmp_path / "policy.yaml"
    surface_policy(config_path, None)
    config_path.write_text(
        config_path.read_text(encoding="utf-8").replace(
            "config_version: 2", "config_version: 1"
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(SIDECAR_PATH),
            "--config",
            str(config_path),
            "--emit-shell-vars",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 2
    assert "config_version" in completed.stderr


def test_invalid_exclusion_regex_fails_closed(tmp_path: Path) -> None:
    config_path = tmp_path / "policy.yaml"
    surface_policy(config_path, None)
    config_path.write_text(
        config_path.read_text(encoding="utf-8")
        + "diff_exclude_paths:\n  - '(^|/)docs/*.md['\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(SIDECAR_PATH),
            "--config",
            str(config_path),
            "--emit-shell-vars",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 2
    assert "diff_exclude_paths" in completed.stderr


def test_renamed_file_with_new_sensitive_line_blocks(tmp_path: Path) -> None:
    """Laundering path: git mv out of an excluded path plus new content."""
    root, environment = repository(tmp_path)
    (root / "NOTES.md").write_text("Harmless baseline.\n", encoding="utf-8")
    assert run(root, "git", "add", "NOTES.md").returncode == 0
    assert (
        run(
            root, "git", "-c", "core.hooksPath=/dev/null", "commit", "-m", "Add"
        ).returncode
        == 0
    )

    assert run(root, "git", "mv", "NOTES.md", "PUBLIC.md").returncode == 0
    (root / "PUBLIC.md").write_text(
        "Harmless baseline.\nNewly added confidential material.\n",
        encoding="utf-8",
    )
    assert run(root, "git", "add", "PUBLIC.md").returncode == 0

    completed = run(root, str(HOOK), env=environment)

    assert completed.returncode == 1, completed.stdout + completed.stderr
    assert "SENSITIVE PATTERN DETECTED" in completed.stdout


def test_copied_file_with_new_sensitive_line_blocks(tmp_path: Path) -> None:
    root, environment = repository(tmp_path)
    (root / "SOURCE.md").write_text("Baseline content here.\n", encoding="utf-8")
    assert run(root, "git", "add", "SOURCE.md").returncode == 0
    assert (
        run(
            root, "git", "-c", "core.hooksPath=/dev/null", "commit", "-m", "Add"
        ).returncode
        == 0
    )

    (root / "COPY.md").write_text(
        "Baseline content here.\nAdded confidential detail.\n", encoding="utf-8"
    )
    assert run(root, "git", "add", "COPY.md").returncode == 0

    completed = run(root, str(HOOK), env=environment)

    assert completed.returncode == 1
    assert "SENSITIVE PATTERN DETECTED" in completed.stdout


def test_quoted_filename_does_not_disable_the_scan(tmp_path: Path) -> None:
    """A filename with an apostrophe must not empty the whole diff."""
    root, environment = repository(tmp_path)
    (root / "rajiv's notes.md").write_text("Harmless.\n", encoding="utf-8")
    (root / "plain.md").write_text(
        "AKIAABCDEFGHIJKLMNOP\n", encoding="utf-8"
    )
    assert run(root, "git", "add", "-A").returncode == 0

    completed = run(root, str(HOOK), env=environment)

    assert completed.returncode == 1, completed.stdout + completed.stderr
    assert "SENSITIVE PATTERN DETECTED" in completed.stdout


def test_spaced_filename_content_is_scanned(tmp_path: Path) -> None:
    root, environment = repository(tmp_path)
    (root / "my notes.md").write_text(
        "AKIAABCDEFGHIJKLMNOP\n", encoding="utf-8"
    )
    assert run(root, "git", "add", "-A").returncode == 0

    completed = run(root, str(HOOK), env=environment)

    assert completed.returncode == 1
    assert "SENSITIVE PATTERN DETECTED" in completed.stdout


def test_tier0_is_never_excluded_by_path(tmp_path: Path) -> None:
    """Credentials block even in a pattern-catalog path."""
    root, environment = repository(tmp_path)
    catalog = root / "skills" / "synthesis-git-hooks" / "scripts"
    catalog.mkdir(parents=True)
    (catalog / "notes.md").write_text(
        "AKIAABCDEFGHIJKLMNOP\n", encoding="utf-8"
    )
    assert run(root, "git", "add", "-A").returncode == 0

    completed = run(root, str(HOOK), env=environment)

    assert completed.returncode == 1, completed.stdout + completed.stderr
    assert "SENSITIVE PATTERN DETECTED" in completed.stdout


def test_unanchored_config_basename_is_not_a_free_pass(tmp_path: Path) -> None:
    """A file merely NAMED git-hook-config.yaml must still be scanned."""
    root, environment = repository(tmp_path)
    decoy = root / "src"
    decoy.mkdir()
    (decoy / "git-hook-config.yaml").write_text(
        "note: confidential material\n", encoding="utf-8"
    )
    assert run(root, "git", "add", "-A").returncode == 0

    completed = run(root, str(HOOK), env=environment)

    assert completed.returncode == 1
    assert "SENSITIVE PATTERN DETECTED" in completed.stdout


def test_double_quoted_pattern_keeps_its_escapes(tmp_path: Path) -> None:
    """`\\b` in a double-quoted scalar must stay a word boundary."""
    parsed = SIDECAR.parse_simple_yaml('key: "\\\\bsalary\\\\b"\n')
    assert parsed["key"] == "\\bsalary\\b"
    assert not any(ord(ch) < 32 for ch in parsed["key"])


# ─── drift-source resolution (doctor) ────────────────────────────────────


def engine_copy(target: Path) -> None:
    """Copy the complete installed engine shape into `target`."""
    target.mkdir(parents=True, exist_ok=True)
    for name in SIDECAR.ENGINE_FILES:
        destination = target / name
        destination.write_bytes(
            SIDECAR.source_engine_path(SCRIPT_DIR, name).read_bytes()
        )
        destination.chmod(0o755)
    references = target.parent / "references"
    references.mkdir(exist_ok=True)
    (references / SIDECAR.COORDINATION_ASSET).write_bytes(
        SIDECAR.source_coordination_asset(SCRIPT_DIR).read_bytes()
    )


def r4_policy(path: Path, board: Path | None = None) -> None:
    policy(path)
    if board is not None:
        path.write_text(
            path.read_text(encoding="utf-8")
            + f"coordination_board: '{board}'\n",
            encoding="utf-8",
        )


def r4_engine_bundle(target: Path, *, coordination: bool = True) -> None:
    if not coordination:
        target.mkdir(parents=True, exist_ok=True)
        for name in SIDECAR.CORE_ENGINE_FILES:
            destination = target / name
            shutil.copy2(SCRIPT_DIR / name, destination)
            destination.chmod(0o755)
        return
    engine_copy(target)


def r4_board_claim(board: Path, root: Path, engine: Path) -> str:
    branch = run(root, "git", "branch", "--show-current").stdout.strip()
    completed = run(
        root,
        sys.executable,
        str(engine / "coordination.py"),
        "--board",
        str(board),
        "claim",
        "--session",
        "A",
        "--agent",
        "test",
        "--project",
        "project-a",
        "--mode",
        "autonomous",
        "--goal",
        "test hook",
        "--workspace",
        f"{root} @ {branch}",
        "--area",
        f"{root}/claimed/**",
        "--context-role",
        "owner",
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return "A"


def test_source_env_override_is_authoritative(tmp_path, monkeypatch) -> None:
    source = tmp_path / "anywhere" / "scripts"
    engine_copy(source)
    monkeypatch.setenv("SYNTHESIS_GIT_HOOKS_SOURCE", str(source))

    resolved, problem = SIDECAR.resolve_source_dir(None)

    assert problem is None
    assert resolved == source


def test_misconfigured_source_override_fails_closed(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SYNTHESIS_GIT_HOOKS_SOURCE", str(tmp_path / "missing"))

    resolved, problem = SIDECAR.resolve_source_dir(None)

    assert resolved is None
    assert problem is not None and "fail closed" in problem


def test_incomplete_source_override_fails_closed(tmp_path, monkeypatch) -> None:
    """A lone sidecar copy is not a source; byte-comparing against a partial
    directory would report "no drift" for the files it lacks."""
    partial = tmp_path / "partial"
    partial.mkdir()
    (partial / "_load_config.py").write_text("# lone file\n", encoding="utf-8")
    monkeypatch.setenv("SYNTHESIS_GIT_HOOKS_SOURCE", str(partial))

    resolved, problem = SIDECAR.resolve_source_dir(None)

    assert resolved is None
    assert problem is not None


def test_empty_source_override_skips_deliberately(monkeypatch) -> None:
    monkeypatch.setenv("SYNTHESIS_GIT_HOOKS_SOURCE", "")

    assert SIDECAR.resolve_source_dir(None) == (None, None)


def test_own_directory_is_the_default_source(tmp_path, monkeypatch) -> None:
    """Run from a checkout, worktree, or plugin cache, the running copy is
    the drift baseline — no hardcoded checkout path involved."""
    monkeypatch.delenv("SYNTHESIS_GIT_HOOKS_SOURCE", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    installed = tmp_path / ".synthesis" / "git-hooks"
    engine_copy(installed)

    resolved, problem = SIDECAR.resolve_source_dir(installed)

    assert problem is None
    assert resolved == SCRIPT_DIR


def test_installed_copy_never_compares_against_itself(tmp_path, monkeypatch) -> None:
    """When the doctor runs from the installed engine, the drift source must
    come from documented locations — comparing the installation against
    itself would report "no drift" unconditionally."""
    monkeypatch.delenv("SYNTHESIS_GIT_HOOKS_SOURCE", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)

    resolved, problem = SIDECAR.resolve_source_dir(SCRIPT_DIR)
    assert (resolved, problem) == (None, None)

    direct_copy = (
        tmp_path / ".claude" / "skills" / "synthesis-git-hooks" / "scripts"
    )
    engine_copy(direct_copy)

    resolved, problem = SIDECAR.resolve_source_dir(SCRIPT_DIR)
    assert problem is None
    assert resolved == direct_copy


def test_doctor_detects_drift_end_to_end(tmp_path: Path) -> None:
    """Installed engine + discovered source, healthy then drifted."""
    home = tmp_path / "home"
    installed = home / ".synthesis" / "git-hooks"
    engine_copy(installed)
    source = home / ".claude" / "skills" / "synthesis-git-hooks" / "scripts"
    engine_copy(source)
    config = tmp_path / "policy.yaml"
    policy(config)
    (home / ".gitconfig").write_text(
        f"[core]\n\thooksPath = {installed}\n", encoding="utf-8"
    )
    environment = dict(os.environ)
    environment["HOME"] = str(home)
    environment["SYNTHESIS_GIT_HOOK_CONFIG"] = str(config)
    for variable in (
        "SYNTHESIS_GIT_HOOKS_SOURCE",
        "XDG_CACHE_HOME",
        "XDG_CONFIG_HOME",
        "GIT_CONFIG_GLOBAL",
    ):
        environment.pop(variable, None)

    def doctor():
        return subprocess.run(
            [sys.executable, str(installed / "_load_config.py"), "--doctor"],
            cwd=tmp_path,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

    healthy = doctor()
    assert healthy.returncode == 0, healthy.stdout + healthy.stderr
    assert "no drift" in healthy.stdout

    (source / "pre-commit").write_bytes(b"#!/bin/bash\n# hotfixed\n")
    drifted = doctor()
    assert drifted.returncode == 1, drifted.stdout + drifted.stderr
    assert "DRIFT: installed pre-commit" in drifted.stdout


def test_r4_configured_hook_blocks_outside_claim(tmp_path: Path) -> None:
    root, environment = repository(tmp_path)
    engine = tmp_path / "engine"
    r4_engine_bundle(engine)
    board = tmp_path / "coordination" / "active-sessions.md"
    r4_board_claim(board, root, engine)
    r4_policy(Path(environment["SYNTHESIS_GIT_HOOK_CONFIG"]), board)
    environment["SYNTHESIS_COORDINATION_SESSION"] = "A"
    (root / "outside.md").write_text("ordinary content\n", encoding="utf-8")
    assert run(root, "git", "add", "outside.md").returncode == 0

    completed = run(root, str(engine / "pre-commit"), env=environment)

    assert completed.returncode == 1
    assert "refused-outside-claim" in completed.stdout + completed.stderr
    assert "COMMIT BLOCKED" in completed.stderr
    assert "coordination authority refused" in completed.stderr
    assert "policy engine unavailable" not in completed.stderr


def test_r4_configured_hook_consumes_bound_receipt(tmp_path: Path) -> None:
    root, environment = repository(tmp_path)
    engine = tmp_path / "engine"
    r4_engine_bundle(engine)
    board = tmp_path / "coordination" / "active-sessions.md"
    r4_board_claim(board, root, engine)
    r4_policy(Path(environment["SYNTHESIS_GIT_HOOK_CONFIG"]), board)
    environment["SYNTHESIS_COORDINATION_SESSION"] = "A"
    claimed = root / "claimed"
    claimed.mkdir()
    (claimed / "inside.md").write_text("ordinary content\n", encoding="utf-8")
    assert run(root, "git", "add", "claimed/inside.md").returncode == 0

    completed = run(root, str(engine / "pre-commit"), env=environment)

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "passed-inside-claim" in completed.stdout
    assert "authority receipt consumed" in completed.stdout
    assert "unverified remainder" in completed.stdout


def test_r4_hook_rejects_index_changed_after_receipt(tmp_path: Path) -> None:
    root, environment = repository(tmp_path)
    engine = tmp_path / "engine"
    r4_engine_bundle(engine)
    board = tmp_path / "coordination" / "active-sessions.md"
    r4_board_claim(board, root, engine)
    r4_policy(Path(environment["SYNTHESIS_GIT_HOOK_CONFIG"]), board)
    environment["SYNTHESIS_COORDINATION_SESSION"] = "A"
    claimed = root / "claimed"
    claimed.mkdir()
    (claimed / "inside.md").write_text("ordinary content\n", encoding="utf-8")
    assert run(root, "git", "add", "claimed/inside.md").returncode == 0

    real_checker = engine / "coordination-real.py"
    (engine / "coordination.py").replace(real_checker)
    (engine / "coordination.py").write_text(
        """\
import subprocess
import sys
from pathlib import Path

completed = subprocess.run(
    [sys.executable, str(Path(__file__).with_name("coordination-real.py")), *sys.argv[1:]],
    capture_output=True,
    text=True,
    check=False,
)
if completed.returncode == 0:
    repository = Path(sys.argv[sys.argv.index("--repository") + 1])
    late = repository / "claimed" / "late.md"
    late.write_text("late index mutation\\n", encoding="utf-8")
    subprocess.run(["git", "add", str(late)], cwd=repository, check=True)
sys.stdout.write(completed.stdout)
sys.stderr.write(completed.stderr)
raise SystemExit(completed.returncode)
""",
        encoding="utf-8",
    )

    completed = run(root, str(engine / "pre-commit"), env=environment)

    assert completed.returncode == 1
    assert "receipt validation failed" in completed.stderr


def test_r4_hook_rejects_refusing_outcome_with_valid_receipt(
    tmp_path: Path,
) -> None:
    root, environment = repository(tmp_path)
    engine = tmp_path / "engine"
    r4_engine_bundle(engine)
    board = tmp_path / "coordination" / "active-sessions.md"
    r4_board_claim(board, root, engine)
    r4_policy(Path(environment["SYNTHESIS_GIT_HOOK_CONFIG"]), board)
    environment["SYNTHESIS_COORDINATION_SESSION"] = "A"
    claimed = root / "claimed"
    claimed.mkdir()
    (claimed / "inside.md").write_text("ordinary content\n", encoding="utf-8")
    assert run(root, "git", "add", "claimed/inside.md").returncode == 0

    real_checker = engine / "coordination-real.py"
    (engine / "coordination.py").replace(real_checker)
    (engine / "coordination.py").write_text(
        """\
import json
import subprocess
import sys
from pathlib import Path

completed = subprocess.run(
    [sys.executable, str(Path(__file__).with_name("coordination-real.py")), *sys.argv[1:]],
    capture_output=True,
    text=True,
    check=False,
)
if completed.returncode == 0:
    payload = json.loads(completed.stdout)
    payload["enforcement_outcome"] = "refused-outside-claim"
    payload["outside_paths"] = ["claimed/inside.md"]
    sys.stdout.write(json.dumps(payload))
else:
    sys.stdout.write(completed.stdout)
sys.stderr.write(completed.stderr)
raise SystemExit(completed.returncode)
""",
        encoding="utf-8",
    )

    completed = run(root, str(engine / "pre-commit"), env=environment)

    assert completed.returncode == 1
    assert "receipt validation failed" in completed.stderr


def test_r4_unconfigured_hook_reports_control_absence(tmp_path: Path) -> None:
    root, environment = repository(tmp_path)
    engine = tmp_path / "engine"
    r4_engine_bundle(engine)
    r4_policy(Path(environment["SYNTHESIS_GIT_HOOK_CONFIG"]))
    (root / "ordinary.md").write_text("ordinary content\n", encoding="utf-8")
    assert run(root, "git", "add", "ordinary.md").returncode == 0

    completed = run(root, str(engine / "pre-commit"), env=environment)

    assert completed.returncode == 0, completed.stdout + completed.stderr
    output = completed.stdout + completed.stderr
    assert "coordination check-staged" in output
    assert "control absent" in output
    assert "commit not blocked by this control" in output


def test_r4_configured_hook_missing_runtime_fails_closed(tmp_path: Path) -> None:
    root, environment = repository(tmp_path)
    engine = tmp_path / "engine"
    r4_engine_bundle(engine, coordination=False)
    board = tmp_path / "coordination" / "active-sessions.md"
    r4_policy(Path(environment["SYNTHESIS_GIT_HOOK_CONFIG"]), board)
    environment["SYNTHESIS_COORDINATION_SESSION"] = "A"
    (root / "ordinary.md").write_text("ordinary content\n", encoding="utf-8")
    assert run(root, "git", "add", "ordinary.md").returncode == 0

    completed = run(root, str(engine / "pre-commit"), env=environment)

    assert completed.returncode == 1
    assert "coordination runtime" in completed.stderr
    assert "COMMIT BLOCKED" in completed.stderr


def test_r4_installer_copies_coordination_runtime(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    environment = dict(os.environ)
    environment["HOME"] = str(home)
    environment["GIT_CONFIG_GLOBAL"] = str(tmp_path / "gitconfig")
    environment.pop("SYNTHESIS_GIT_HOOKS_SOURCE", None)

    completed = subprocess.run(
        ["bash", str(SCRIPT_DIR / "install.sh")],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    installed = home / ".synthesis" / "git-hooks"
    assert {path.name for path in installed.iterdir()} == {
        "pre-commit",
        "commit-msg",
        "_load_config.py",
        "coordination.py",
        "coordination_schema.py",
        "pointer_lock.py",
        "peer_addressing.py",
        "source-path",
    }
    assert (
        home / ".synthesis" / "references" / "session-words-v1.txt.zlib.b85"
    ).is_file()
    seeded = home / ".synthesis" / "git-hook-config.yaml"
    assert SIDECAR.parse_simple_yaml(seeded.read_text(encoding="utf-8"))[
        "config_version"
    ] == 2
    output = completed.stdout + completed.stderr
    assert "installed engine matches skill source (no drift)" in output
    assert "skill source not found" not in output

    direct_doctor = subprocess.run(
        [sys.executable, str(installed / "_load_config.py"), "--doctor"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert direct_doctor.returncode == 0, direct_doctor.stdout + direct_doctor.stderr
    assert "installed engine matches skill source (no drift)" in direct_doctor.stdout
    assert "skill source not found" not in direct_doctor.stdout


def test_r4_invalid_persisted_source_pointer_fails_doctor_closed(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    installed = home / ".synthesis" / "git-hooks"
    engine_copy(installed)
    (installed / "source-path").write_text(
        str(tmp_path / "missing-source") + "\n", encoding="utf-8"
    )
    config = tmp_path / "policy.yaml"
    policy(config)
    (home / ".gitconfig").write_text(
        f"[core]\n\thooksPath = {installed}\n", encoding="utf-8"
    )
    environment = dict(os.environ)
    environment["HOME"] = str(home)
    environment["SYNTHESIS_GIT_HOOK_CONFIG"] = str(config)
    for variable in (
        "SYNTHESIS_GIT_HOOKS_SOURCE",
        "XDG_CACHE_HOME",
        "XDG_CONFIG_HOME",
        "GIT_CONFIG_GLOBAL",
    ):
        environment.pop(variable, None)

    completed = subprocess.run(
        [sys.executable, str(installed / "_load_config.py"), "--doctor"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 1
    assert "persisted source pointer" in completed.stdout
    assert "UNHEALTHY" in completed.stdout


def test_r4_config_sidecar_emits_board_gate(tmp_path: Path) -> None:
    board = tmp_path / "coordination" / "active-sessions.md"
    config = tmp_path / "policy.yaml"
    r4_policy(config, board)

    completed = subprocess.run(
        [
            sys.executable,
            str(SIDECAR_PATH),
            "--config",
            str(config),
            "--emit-shell-vars",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "COORDINATION_CHECK_STAGED=1" in completed.stdout
    assert f"COORDINATION_BOARD={shlex.quote(str(board))}" in completed.stdout

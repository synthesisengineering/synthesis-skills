"""Shared fixtures for the coordination tests."""

import pytest


@pytest.fixture
def codex_cli(tmp_path, monkeypatch):
    """A runnable Codex CLI stand-in, selected through the authoritative override.

    The codex lane exists only when this machine can run a Codex CLI, so a test
    that expects the lane provides one explicitly rather than depending on
    whether the machine running the suite happens to have Codex installed.
    """
    cli = tmp_path / "codex-cli" / "codex"
    cli.parent.mkdir()
    cli.write_text("#!/bin/sh\nexit 0\n")
    cli.chmod(0o755)
    monkeypatch.setenv("SYNTHESIS_CODEX_BIN", str(cli))
    return str(cli)


@pytest.fixture
def synthetic_storage_policy(tmp_path, monkeypatch):
    """Model durable storage only inside this test's own synthetic tree.

    Filesystem/index tests need durable and temporary placement cases on every
    host. Overriding temporary_roots alone leaves Darwin's additional T/C rule
    active. This explicit fixture models the complete policy for its allocated
    tree; unmodeled paths and symlink escapes keep the real protective policy.
    """
    from pathlib import Path
    import fleet_paths

    fixture_root = tmp_path.resolve()
    real = fleet_paths._temporary_storage_root

    def configure(temporary_roots):
        roots = tuple(Path(root).resolve() for root in temporary_roots)
        if any(root != fixture_root and fixture_root not in root.parents for root in roots):
            raise ValueError("synthetic roots must belong to this test's allocation")

        def classify(canonical):
            if canonical != fixture_root and fixture_root not in canonical.parents:
                return real(canonical)
            return next((str(root) for root in roots
                         if canonical == root or root in canonical.parents), None)

        monkeypatch.setattr(fleet_paths, "_temporary_storage_root", classify)

    return configure

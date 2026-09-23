"""Per-site descriptors and principal-name interpolation (PRO-4 seams).

Bare-string repos keep the historical behavior (both article layouts
scanned, messages address "the principal"). A sites entry narrows the
timeline scan to its own roots and names its own principal; malformed
descriptors fail closed at config load.
"""
from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parent.parent / "guards" / "publish_guard.py"
SPEC = importlib.util.spec_from_file_location("publish_guard_sites", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

import pytest  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _parser_runtime():
    """Bind the same-repo shell parser eagerly (fails fast on layout drift)."""
    MODULE._ensure_shell_parser()
    assert MODULE.inspect_command is not None
    yield


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True,
                   capture_output=True, timeout=20)


def _site(tmp_path, name="site"):
    repo = tmp_path / name
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    for key, value in (("user.name", "T"), ("user.email", "t@example.com"),
                       ("core.hooksPath", "/dev/null")):
        _git(repo, "config", key, value)
    _git(repo, "commit", "-q", "--allow-empty", "-m", "seed")
    _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    return repo


def _post(repo, rel, stamp):
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"---\ntitle: \"T\"\ndate: '{stamp}'\n---\n\nBody.\n",
                 encoding="utf-8")
    return p


FUTURE = "2026-08-30T16:47:00"
NOW = datetime(2026, 8, 29, 19, 30)


def test_default_scans_cover_both_layouts():
    assert MODULE.content_scans(None, "/x/site") == [
        ("content/posts", "index.md"),
        ("astro-site/src/content/articles", "*.md"),
    ]
    assert MODULE.content_scans({}, "/x/site") == list(MODULE.DEFAULT_CONTENT_SCANS)
    assert MODULE.content_scans({"auto_deploy_repos": ["/x/site"]}, "/x/site") == [
        ("content/posts", "index.md"),
        ("astro-site/src/content/articles", "*.md"),
    ]


def test_site_descriptor_narrows_roots_and_layout():
    cfg = {"sites": {"/x/site": {"content_layout": "flat",
                                 "content_roots": ["writing/drafts"]}}}
    assert MODULE.content_scans(cfg, "/x/site") == [("writing/drafts", "*.md")]
    cfg["sites"]["/x/site"]["content_layout"] = "nested-date"
    assert MODULE.content_scans(cfg, "/x/site") == [("writing/drafts", "index.md")]
    # Other repos keep the default.
    assert MODULE.content_scans(cfg, "/x/other") == list(MODULE.DEFAULT_CONTENT_SCANS)


def test_site_descriptor_matches_normalized_paths():
    cfg = {"sites": {"/x/site/": {"content_layout": "flat",
                                  "content_roots": ["w"]}}}
    assert MODULE.content_scans(cfg, "/x/site") == [("w", "*.md")]
    assert MODULE.content_scans(cfg, "/x/site/") == [("w", "*.md")]


def test_malformed_descriptor_fails_closed_at_load(tmp_path, monkeypatch):
    cfg_path = tmp_path / "config.json"
    monkeypatch.setenv("PUBLISH_GUARD_CONFIG", str(cfg_path))
    bad = [
        {"auto_deploy_repos": ["/x"], "sites": {"/x": {"content_layout": "weekly"}}},
        {"auto_deploy_repos": ["/x"], "sites": {"/x": {"content_roots": "posts"}}},
        {"auto_deploy_repos": ["/x"], "sites": {"/x": {"content_roots": ["ok", 7]}}},
        {"auto_deploy_repos": ["/x"], "sites": {"/x": "posts"}},
        {"auto_deploy_repos": ["/x"], "sites": ["/x"]},
        {"auto_deploy_repos": ["/x"], "principal_name": ["Not", "A", "Name"]},
        {"auto_deploy_repos": ["/x"],
         "sites": {"/x": {"principal_name": {"name": "x"}}}},
    ]
    for cfg in bad:
        cfg_path.write_text(json.dumps(cfg))
        with pytest.raises(ValueError):
            MODULE.load_config()
    good = {"auto_deploy_repos": ["/x"], "principal_name": "  ",
            "sites": {"/x": {"label": "X", "content_layout": "flat",
                             "content_roots": ["w"], "principal_name": ""}}}
    cfg_path.write_text(json.dumps(good))
    assert MODULE.load_config()["auto_deploy_repos"] == ["/x"]


def test_principal_resolution_order():
    assert MODULE.principal_display(None) == "the principal"
    assert MODULE.principal_display({}) == "the principal"
    cfg = {"principal_name": "Top Name"}
    assert MODULE.principal_display(cfg) == "Top Name"
    assert MODULE.principal_display(cfg, "/x/site") == "Top Name"
    cfg["sites"] = {"/x/site": {"principal_name": "Site Owner"}}
    assert MODULE.principal_display(cfg, "/x/site") == "Site Owner"
    assert MODULE.principal_display(cfg, "/x/other") == "Top Name"


def test_custom_roots_drive_the_future_scan(tmp_path):
    repo = tmp_path / "site"
    _post(repo, "writing/drafts/future.md", FUTURE)
    _post(repo, "content/posts/2026/08/30-x/index.md", FUTURE)
    cfg = {"sites": {str(repo): {"content_layout": "flat",
                                 "content_roots": ["writing/drafts"]}}}
    offenders = MODULE.future_dated_files(str(repo), now=NOW, cfg=cfg)
    assert [p for p, _ in offenders] == ["writing/drafts/future.md"]
    # Default config flags the nested file instead.
    offenders = MODULE.future_dated_files(str(repo), now=NOW, cfg=None)
    assert [p for p, _ in offenders] == ["content/posts/2026/08/30-x/index.md"]


def test_custom_roots_drive_the_mutation_scan(tmp_path):
    repo = _site(tmp_path)
    _post(repo, "writing/drafts/shipped.md", "2026-05-15T20:00:00")
    _post(repo, "content/posts/2026/05/15-y/index.md", "2026-05-15T20:00:00")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "publish")
    _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    _post(repo, "writing/drafts/shipped.md", "2026-05-16T09:00:00")
    _post(repo, "content/posts/2026/05/15-y/index.md", "2026-05-16T09:00:00")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "re-date")
    cfg = {"sites": {str(repo): {"content_layout": "flat",
                                 "content_roots": ["writing/drafts"]}}}
    mutations = MODULE.published_date_mutations(str(repo), cfg=cfg)
    assert [rel for rel, _, _ in mutations] == ["writing/drafts/shipped.md"]


def test_gate_block_names_the_configured_principal(tmp_path, monkeypatch):
    repo = _site(tmp_path)
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({
        "auto_deploy_repos": [str(repo)],
        "principal_name": "Dana Example",
    }))
    monkeypatch.setenv("PUBLISH_GUARD_CONFIG", str(cfg_path))
    monkeypatch.setenv("PUBLISH_GUARD_STATE_DIR", str(tmp_path / "state"))
    payload = {"tool_name": "Bash", "cwd": str(repo),
               "tool_input": {"command": f"cd {repo} && git push origin main"}}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    err = io.StringIO()
    monkeypatch.setattr(sys, "stderr", err)
    assert MODULE.gate() == 2
    assert "show Dana Example the change" in err.getvalue()


def test_gate_block_defaults_to_the_principal(tmp_path, monkeypatch):
    repo = _site(tmp_path)
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"auto_deploy_repos": [str(repo)]}))
    monkeypatch.setenv("PUBLISH_GUARD_CONFIG", str(cfg_path))
    monkeypatch.setenv("PUBLISH_GUARD_STATE_DIR", str(tmp_path / "state"))
    payload = {"tool_name": "Bash", "cwd": str(repo),
               "tool_input": {"command": f"cd {repo} && git push origin main"}}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    err = io.StringIO()
    monkeypatch.setattr(sys, "stderr", err)
    assert MODULE.gate() == 2
    assert "show the principal the change" in err.getvalue()


def test_per_site_principal_wins_in_gate(tmp_path, monkeypatch):
    repo = _site(tmp_path)
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({
        "auto_deploy_repos": [str(repo)],
        "principal_name": "Top Name",
        "sites": {str(repo): {"principal_name": "Site Owner"}},
    }))
    monkeypatch.setenv("PUBLISH_GUARD_CONFIG", str(cfg_path))
    monkeypatch.setenv("PUBLISH_GUARD_STATE_DIR", str(tmp_path / "state"))
    payload = {"tool_name": "Bash", "cwd": str(repo),
               "tool_input": {"command": f"cd {repo} && git push origin main"}}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    err = io.StringIO()
    monkeypatch.setattr(sys, "stderr", err)
    assert MODULE.gate() == 2
    assert "show Site Owner the change" in err.getvalue()
    assert "Top Name" not in err.getvalue()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

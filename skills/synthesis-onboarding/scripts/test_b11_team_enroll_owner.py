"""Existing enrollment owner must carry an already explicit team selection."""

from pathlib import Path
import pytest
import json
import sys

PUBLIC = Path(__file__).resolve().parents[3]
for s in ["synthesis-project-management", "synthesis-onboarding"]:
    sys.path.insert(0, str(PUBLIC / "skills" / s / "scripts"))
import synthesis_cli as cli  # noqa: E402 - exact source owner bound above
import team_enrollment as te  # noqa: E402 - exact source owner bound above
from test_team_enrollment import package  # noqa: E402 - exact source owner bound above
from test_additive_enrollment import base_state, REPOSITORY  # noqa: E402 - exact source owner bound above


def test_existing_explicit_selection_survives_actual_enroll_owner(
    tmp_path, monkeypatch
):
    org = tmp_path / "org"
    org.mkdir()
    manifest, selection, _ = package(org)
    manifest["ecosystem"] = {
        "clients": ["codex"],
        "channel": "stable",
        "version_pin": None,
    }
    state, base = base_state(tmp_path / "home")
    entry = {
        "repository": REPOSITORY,
        "manifest_path": ".agents/onboarding.yaml",
        "commit_policy": "floating",
        "commit": "1" * 40,
        "mode": "additive",
        "workspace": "unit-one",
        "principal_selection": selection,
    }
    enrolled = {
        **base,
        "organizations": [entry],
        "layers": {**base["layers"], "organization": "selected"},
    }
    state.run_transaction("enroll", enrolled, lambda tx: {})
    assert (
        te.select_manifest(manifest, selection)["_team_selection"]["person"] == "p-one"
    )
    monkeypatch.setattr(
        cli.organization, "acquire_repository", lambda *a, **k: (org, "1" * 40)
    )
    monkeypatch.setattr(cli.onboard, "load_manifest", lambda p: manifest)
    monkeypatch.setattr(cli, "_active_release", lambda: None)
    calls = []

    def engine(argv):
        proposed = json.loads(Path(argv[argv.index("--desired-state") + 1]).read_text())
        current = proposed["organizations"][0].get("principal_selection")
        calls.append(current)
        te.select_manifest(manifest, current)
        return 0

    code = cli.main(
        ["enroll", "--org-repo", REPOSITORY], state=state, engine_runner=engine
    )
    (tmp_path / "observed-selection.json").write_text(
        json.dumps(
            {
                "code": code,
                "calls": calls,
                "final_selection": state.read_desired()["organizations"][0].get(
                    "principal_selection"
                ),
            },
            indent=2,
        )
    )
    assert code == 0 and calls and all(s == selection for s in calls)
    assert state.read_desired()["organizations"][0]["principal_selection"] == selection


def setup_fresh(tmp_path, monkeypatch):
    org = tmp_path / "org"
    org.mkdir()
    manifest, selection, _ = package(org)
    manifest["ecosystem"] = {
        "clients": ["codex"],
        "channel": "stable",
        "version_pin": None,
    }
    state, base = base_state(tmp_path / "home")
    monkeypatch.setattr(
        cli.organization, "acquire_repository", lambda *a, **k: (org, "1" * 40)
    )
    monkeypatch.setattr(cli.onboard, "load_manifest", lambda p: manifest)
    monkeypatch.setattr(cli, "_active_release", lambda: None)
    return manifest, selection, state, base


def test_fresh_cli_selection_drives_the_actual_engine_owner(tmp_path, monkeypatch):
    manifest, selection, state, _ = setup_fresh(tmp_path, monkeypatch)
    selection["requested"] = ["design"]
    calls = []

    def engine(argv):
        data = json.loads(Path(argv[argv.index("--desired-state") + 1]).read_text())
        s = data["organizations"][0]["principal_selection"]
        calls.append(s)
        assert len(te.select_manifest(manifest, s)["skills_repos"]) == 1
        return 0

    args = [
        "enroll",
        "--org-repo",
        REPOSITORY,
        "--team-person",
        selection["person"],
        "--team-digest",
        selection["team_digest"],
        "--team-entitlement",
        "design",
    ]
    assert cli.main(args, state=state, engine_runner=engine) == 0
    assert calls == [selection, selection]
    assert state.read_desired()["organizations"][0]["principal_selection"] == selection




@pytest.mark.parametrize(
    "case", ["stale", "unauthorized", "incomplete", "duplicate", "no-selection"]
)
def test_fresh_selection_refuses_before_transaction_or_engine(
    tmp_path, monkeypatch, case
):
    manifest, selection, state, base = setup_fresh(tmp_path, monkeypatch)
    args = ["enroll", "--org-repo", REPOSITORY]
    if case != "no-selection":
        args += ["--team-person", "p-two" if case == "unauthorized" else "p-one"]
    if case not in ["no-selection", "incomplete"]:
        args += [
            "--team-digest",
            "f" * 64 if case == "stale" else selection["team_digest"],
        ]
    if case in ["unauthorized", "duplicate"]:
        args += ["--team-entitlement", "design"]
    if case == "duplicate":
        args += ["--team-entitlement", "design"]
    before = state.desired_path.read_bytes()
    calls = []
    assert cli.main(args, state=state, engine_runner=lambda a: calls.append(a)) == 2
    assert not calls and state.desired_path.read_bytes() == before
    assert not (state.state_dir / "enrollments").exists()

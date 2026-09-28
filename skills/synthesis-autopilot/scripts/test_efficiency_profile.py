# ruff: noqa: F811
# Pytest fixture imports are deliberately reused as injected argument names.
"""Measured local owner behavior; model tokens and energy are not invented."""

import pytest
from test_controller import facade, world, invoke, start_request, state_of  # noqa: F401
from test_run_state import engine, command, output  # noqa: F401


def case(facade, world):
    state = state_of(world, invoke(facade, world, start_request(world)))
    import autopilot

    state, path = output(autopilot.engine(), world, state)
    state = command(
        autopilot.engine(), world, state, "transition", {"status": "verifying"}
    )
    state = command(
        autopilot.engine(), world, state, "verify", {"criteria": ["accept"]}
    )
    world["profile_output"] = path
    return {
        "schema_version": 1,
        "project": str(world["project"]),
        "project_id": "alpha",
        "run_id": state["run_id"],
        "actor": world["actor"],
    }


@pytest.mark.parametrize("owner", ["startup", "resume", "checkpoint", "review"])
def test_real_owners_cold_and_warm_observations_have_equal_outcomes(
    facade, world, owner
):
    import efficiency_profile as profile

    spec = case(facade, world)
    spec["owner"] = owner
    report = profile.measure(
        spec, world["scratch"] / ("measured-" + owner), repetitions=2, seconds=30
    )
    assert report["outcome_equivalence"] == "PASS", report
    assert report["operational_status"] == "PASS", report
    assert report["scope"] == "local deterministic owner; not harness-wide performance"
    assert report["provider_tokens"] is None and report["energy_joules"] is None
    assert report["native_acceptance"] == "UNKNOWN"
    assert (
        len(report["cold_interpreters"]) == 2
        and len(report["warm_interpreter"]["samples"]) == 2
    )
    assert all(r["terminal"] == "reaped" for r in report["processes"])
    assert report["source_digests"]
    for sample in report["warm_interpreter"]["samples"]:
        assert sample["wall_seconds"] >= 0 and sample["cpu_seconds"] >= 0
        assert sample["python_peak_bytes"] > 0
        assert (
            sample["rss_scope"]
            == "process lifetime high-water; not per-operation delta"
        )


def test_changed_claim_is_a_measured_refusal_not_fast_success(facade, world):
    import efficiency_profile as profile

    spec = case(facade, world)
    spec["owner"] = "startup"
    world["board"].write_text(
        world["board"].read_text().replace("| active |", "| released |")
    )
    report = profile.measure(
        spec, world["scratch"] / "refused", repetitions=1, seconds=30
    )
    assert report["outcome_equivalence"] == "PASS"
    assert (
        report["cold_interpreters"][0]["samples"][0]["outcome"]["status"] == "REFUSED"
    )
    assert report["operational_status"] == "REFUSED"


@pytest.mark.parametrize("bad", [0, True, 6, 10000])
def test_profile_resource_bounds_are_not_optional(tmp_path, bad):
    import efficiency_profile as profile

    with pytest.raises(ValueError):
        profile.measure({}, tmp_path / "never", repetitions=bad, seconds=30)
    assert not (tmp_path / "never").exists()


@pytest.mark.parametrize("owner", ["startup", "resume", "checkpoint", "review"])
@pytest.mark.parametrize(
    "scenario",
    [
        "unchanged-current",
        "changed-registered-input",
        "revoked-claim",
        "corrupt-journal",
    ],
)
def test_preregistered_local_owner_matrix(facade, world, owner, scenario):
    import autopilot
    import efficiency_profile as profile

    spec = case(facade, world)
    spec["owner"] = owner
    if scenario == "changed-registered-input":
        # The required registered output changes after its journal digest was admitted.
        world["profile_output"].write_text(
            "Changed current bytes, not the registered output"
        )
    elif scenario == "revoked-claim":
        world["board"].write_text(
            world["board"].read_text().replace("| active |", "| released |")
        )
    elif scenario == "corrupt-journal":
        home = autopilot.engine()._home(world["project"], spec["run_id"])
        events = home / "events/000000000001.json"
        assert events.is_file()
        with events.open("ab") as stream:
            stream.write(b"{corrupt evidence}\n")
    report = profile.measure(
        spec,
        world["scratch"] / ("preregistered-" + owner + "-" + scenario),
        repetitions=3,
        seconds=30,
    )
    assert report["outcome_equivalence"] == "PASS", report
    expected = "PASS"
    if scenario in {"revoked-claim", "corrupt-journal"}:
        expected = "REFUSED"
    elif scenario == "changed-registered-input" and owner == "review":
        expected = "FAIL"
    # Startup authorizes current owner; it never certifies output completeness.
    # Resume/checkpoint represent current evidence; review carries the failure verdict.
    assert report["operational_status"] == expected, report
    assert report["authority_granted"] is False and report["provider_tokens"] is None


@pytest.mark.parametrize("fault", ["claim", "artifact"])
def test_warm_interpreter_rechecks_authority_and_output_between_samples(
    facade, world, monkeypatch, fault
):
    import efficiency_profile as profile

    spec = case(facade, world)
    spec["owner"] = "review" if fault == "artifact" else "startup"
    real = profile._operation
    count = 0

    def change_after_first(value):
        nonlocal count
        result = real(value)
        count += 1
        if count == 1:
            if fault == "claim":
                world["board"].write_text(
                    world["board"].read_text().replace("| active |", "| released |")
                )
            else:
                world["profile_output"].write_text(
                    "Changed after first successful warm observation"
                )
        return result

    monkeypatch.setattr(profile, "_operation", change_after_first)
    report = profile._probe(spec, 2)
    assert report["samples"][0]["outcome"]["status"] == "PASS"
    assert report["samples"][1]["outcome"]["status"] == (
        "REFUSED" if fault == "claim" else "FAIL"
    )
    assert (
        report["samples"][0]["outcome_sha256"] != report["samples"][1]["outcome_sha256"]
    )

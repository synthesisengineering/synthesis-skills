from pathlib import Path
import sys
import copy
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "skills/synthesis-agent-conformance/scripts"))
import provider_intake as pi  # noqa: E402 - source-bound import follows path/bootstrap initialization


def change():
    return {
        "schema": 1,
        "provider": "openai",
        "version": "synthetic-1",
        "source_url": "https://developers.openai.com/codex/changelog/",
        "source_sha256": "a" * 64,
        "observed_at": "2026-09-26T20:00:00-04:00",
        "surfaces": ["hooks", "session-lifecycle"],
        "classification": "provider-adapter",
        "evidence": [],
    }


def test_change_intake_distinguishes_required_unknown():
    report = pi.triage(change())
    assert (
        report["required_evidence_status"] == "UNKNOWN"
        and report["auto_activate"] is False
    )
    assert report["targets"] == ["claude", "codex"]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(source_url="https://evil.test/news"),
        lambda d: d.update(observed_at="yesterday"),
        lambda d: d.update(classification="no-impact"),
        lambda d: d.update(surfaces=["hooks", "hooks"]),
        lambda d: d.update(
            source_url="https://user:password@developers.openai.com/news"
        ),
    ],
)
def test_source_and_coverage_refusal(mutate):
    d = change()
    mutate(d)
    with pytest.raises(ValueError):
        pi.triage(d)


def test_sanitized_incident_is_a_draft_not_cause_or_contact():
    result = pi.incident(
        {
            "schema": 1,
            "provider": "openai",
            "client": "codex",
            "error_class": "authentication",
            "reproduction": "synthetic-only",
            "raw_excerpt": "Authorization: Bearer SYNTHETIC_VALUE\n/home/example/private/name.txt\nname@example.test",
            "source_sha256": "b" * 64,
            "cases": [
                {"id": "positive", "expected": "success", "observed": "success"},
                {"id": "negative", "expected": "refusal", "observed": "refusal"},
            ],
        }
    )
    assert (
        "SYNTHETIC_VALUE" not in result["excerpt"]
        and "name@example.test" not in result["excerpt"]
    )
    assert (
        result["attribution"] == "unknown"
        and result["contact_authorized"] is False
        and result["disclosure_status"] == "REVIEW_REQUIRED"
    )
    assert result["replay_scope"] == "synthetic-only"


def test_replay_computes_outcomes_instead_of_accepting_declared_receipts():
    good = change()
    bad = copy.deepcopy(good)
    bad["source_url"] = "https://untrusted.example.test/change"
    request = {
        "schema": 1,
        "scope": "synthetic-only",
        "cases": [
            {
                "id": "good",
                "operation": "change",
                "input": good,
                "expected": "accepted",
            },
            {"id": "bad", "operation": "change", "input": bad, "expected": "refused"},
        ],
    }
    result = pi.replay(request)
    assert (
        result["status"] == "REPLAYED_SYNTHETIC_CONTROLS"
        and len(result["results"]) == 2
    )
    assert (
        result["provider_cause"] == "UNRESOLVED"
        and result["contact_authorized"] is False
    )
    request["cases"][1]["input"] = copy.deepcopy(good)
    assert pi.replay(request)["status"] == "CONTROL_MISMATCH"
    with pytest.raises(ValueError):
        pi.replay({**request, "scope": "native-observed"})
    with pytest.raises(ValueError):
        pi.replay({**request, "cases": request["cases"][:1]})

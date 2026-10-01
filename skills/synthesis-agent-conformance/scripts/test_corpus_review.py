"""Local synthetic corpus preparation/decision consumption, not publication."""

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import provider_intake as pi


def request():
    return {
        "schema": 1,
        "corpus_id": "synthetic-corpus",
        "source_kind": "synthetic",
        "members": [{"id": "original-label", "text": "Ordinary observation"}],
    }


def provenance():
    return {
        "principal": "synthetic-reviewer",
        "source_ref": "synthetic-message",
        "received_at": "2026-09-27T00:00:00Z",
        "scope": "local exact candidate",
        "authority_ref": "unverified-synthetic-reference",
    }


def review_input(value=None):
    value = value or request()
    package = pi.corpus_review_packet(value)
    _, owner = pi._decision_owner()
    summary = owner.compose_summary(
        package["spec"],
        {r["id"]: {"choice": "reviewed"} for r in package["spec"]["rows"]},
    )
    return value, package, summary


@pytest.mark.parametrize(
    "text,absent",
    [
        ("person@example.test", "person@example.test"),
        ("/Users/person/client/secret.json", "/Users/person"),
        (r"C:\Users\person\secret", "person"),
        ("https://private.example.test/repository?token=secret", "private.example"),
        ("Authorization: Bearer synthetic-value", "synthetic-value"),
        ("@private-person", "@private-person"),
        ("192.168.0.20", "192.168.0.20"),
        ("../private/project/file", "../private"),
        ("~/private/file", "~/private"),
        ("123e4567-e89b-12d3-a456-426614174000", "123e4567"),
    ],
)
def test_common_identifiers_reduced_but_still_need_review(text, absent):
    value = request()
    value["members"][0]["text"] = text
    result = pi.prepare_corpus(value)
    assert absent not in result["members"][0]["content"]
    assert result["disclosure_status"] == "REVIEW_REQUIRED"
    assert result["publication_authorized"] is False


def test_indirect_and_combined_identification_remain_required_without_pattern_matches():
    value = request()
    value["members"] = [
        {"id": "a", "text": "The only director in the small village."},
        {"id": "b", "text": "She arrived at exactly 08:17 last Tuesday."},
    ]
    result = pi.prepare_corpus(value)
    assert all(not m["pattern_findings"] for m in result["members"])
    assert {"indirect-identification", "cross-case-aggregation"} <= set(
        result["required_dimensions"]
    )
    assert result["semantic_review_required"] and not result["publication_authorized"]


def test_source_labels_are_not_republished_and_all_bytes_bind_candidate():
    value = request()
    value["corpus_id"] = "private-project"
    value["members"][0]["id"] = "private-person"
    result = pi.prepare_corpus(value)
    assert "private-project" not in json.dumps(
        result
    ) and "private-person" not in json.dumps(result)
    changed = deepcopy(value)
    changed["members"][0]["id"] = "other-private-person"
    assert pi.prepare_corpus(changed)["source_sha256"] != result["source_sha256"]


def test_actual_packet_consumer_keeps_review_and_authority_separate():
    value, package, summary = review_input()
    owner, _ = pi._decision_owner()
    rendered = owner.build(package["spec"])
    assert "Ordinary observation" in rendered
    result = pi.review_corpus(value, summary, provenance())
    assert result["disclosure_status"] == "EXACT_SPEC_REVIEWED"
    assert (
        result["authorization"]["granted"] is False
        and result["provenance"]["status"] == "claimed-unverified"
    )
    assert not result["publication_authorized"]
    with pytest.raises(ValueError, match="actual action owner"):
        pi.require_corpus_publication(value, summary, provenance())


@pytest.mark.parametrize("mutation", ["text", "id", "order", "kind", "corpus"])
def test_changed_source_cannot_inherit_review(mutation):
    value, _, summary = review_input()
    if mutation == "text":
        value["members"][0]["text"] += " New meaning"
    elif mutation == "id":
        value["members"][0]["id"] = "different"
    elif mutation == "order":
        value["members"].insert(0, {"id": "other", "text": "Other case"})
    elif mutation == "kind":
        value["source_kind"] = "local-original"
    else:
        value["corpus_id"] = "different"
    with pytest.raises(ValueError):
        pi.review_corpus(value, summary, provenance())


def test_incomplete_review_and_legacy_paste_do_not_become_reviewed():
    value, package, _ = review_input()
    _, owner = pi._decision_owner()
    summary = owner.compose_summary(
        package["spec"], {package["spec"]["rows"][0]["id"]: {"choice": "reviewed"}}
    )
    assert (
        pi.review_corpus(value, summary, provenance())["disclosure_status"]
        == "REVIEW_REQUIRED"
    )
    with pytest.raises(ValueError):
        pi.review_corpus(
            value, owner.compose_legacy_summary(package["spec"], {}), provenance()
        )


@pytest.mark.parametrize(
    "change",
    [
        lambda r: r.update(schema=True),
        lambda r: r.update(approved=True),
        lambda r: r.update(members=[]),
        lambda r: r["members"].append(deepcopy(r["members"][0])),
        lambda r: r["members"][0].update(text="x" * 65537),
        lambda r: r["members"][0].update(publication_approved=True),
        lambda r: r.update(source_kind="anonymized-safe"),
    ],
)
def test_invalid_corpus_contract_refuses(change):
    value = request()
    change(value)
    with pytest.raises(ValueError):
        pi.prepare_corpus(value)


def test_actual_cli_review_and_publication_refusal():
    value, _, summary = review_input()
    data = {"request": value, "summary": summary, "provenance": provenance()}
    command = [sys.executable, str(Path(pi.__file__)), "corpus-review"]
    result = subprocess.run(
        command, input=json.dumps(data), capture_output=True, text=True, timeout=10
    )
    assert (
        result.returncode == 0
        and json.loads(result.stdout)["disclosure_status"] == "EXACT_SPEC_REVIEWED"
    )
    command[-1] = "corpus-publish"
    refused = subprocess.run(
        command, input=json.dumps(data), capture_output=True, text=True, timeout=10
    )
    assert refused.returncode == 2 and json.loads(refused.stdout)["status"] == "REFUSED"


def test_actual_saved_corpus_bytes_not_whitespace_normalized_into_old_review(tmp_path):
    value = request()
    raw = json.dumps(value, indent=2).encode()
    package = pi.corpus_review_packet(value, source_bytes=raw)
    _, owner = pi._decision_owner()
    summary = owner.compose_summary(
        package["spec"],
        {row["id"]: {"choice": "reviewed"} for row in package["spec"]["rows"]},
    )
    assert (
        pi.review_corpus(value, summary, provenance(), source_bytes=raw)[
            "disclosure_status"
        ]
        == "EXACT_SPEC_REVIEWED"
    )
    with pytest.raises(ValueError):
        pi.review_corpus(value, summary, provenance(), source_bytes=raw + b"\n")
    source = tmp_path / "source.json"
    source.write_bytes(raw)
    data = {"request": value, "summary": summary, "provenance": provenance()}
    result = subprocess.run(
        [
            sys.executable,
            str(Path(pi.__file__)),
            "corpus-review",
            "--corpus-source",
            str(source),
        ],
        input=json.dumps(data),
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    source.write_bytes(raw + b"\n")
    refused = subprocess.run(
        [
            sys.executable,
            str(Path(pi.__file__)),
            "corpus-review",
            "--corpus-source",
            str(source),
        ],
        input=json.dumps(data),
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert refused.returncode == 2


def test_saved_source_cannot_claim_different_input_or_use_link(tmp_path):
    value = request()
    with pytest.raises(ValueError):
        pi.prepare_corpus(value, source_bytes=b"{}")
    source = tmp_path / "source.json"
    source.write_text(json.dumps(value))
    alias = tmp_path / "alias.json"
    alias.symlink_to(source)
    result = subprocess.run(
        [
            sys.executable,
            str(Path(pi.__file__)),
            "corpus-prepare",
            "--corpus-source",
            str(alias),
        ],
        input=json.dumps(value),
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 2 and "REFUSED" in result.stdout


@pytest.mark.parametrize(
    "text",
    [
        "first@example.test-second@example.test",
        "first@example.test.second@example.test",
        "prefix+first@example.test",
        "(first@example.test)",
        "x@a.test/y@b.test",
        "single\nnext@example.test",
        "person@example.test trailing text",
        "aa@bbb.ccc.zzz",
        "ascii.user+tag@example.test",
        "@abc@example.test",
    ],
)
def test_email_scan_conservatively_covers_original_identifier_matches(text):
    import re

    old = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
    assert old
    request = {
        "schema": 1,
        "corpus_id": "coverage",
        "source_kind": "synthetic",
        "members": [{"id": "sample", "text": text}],
    }
    result = pi.prepare_corpus(request)
    assert all(match not in result["members"][0]["content"] for match in old)
    assert result["disclosure_status"] == "REVIEW_REQUIRED"
    assert result["publication_authorized"] is False


def test_large_corpus_avoids_email_prefix_restart_amplification(tmp_path):
    import subprocess
    import sys
    import time
    from pathlib import Path

    request = {
        "schema": 1,
        "corpus_id": "large-ordinary",
        "source_kind": "synthetic",
        "members": [{"id": "part-" + str(i), "text": "a" * 60000} for i in range(16)],
    }
    raw = json.dumps(request)
    assert len(raw.encode()) < 1024 * 1024
    start = time.monotonic()
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            str(Path(__file__).with_name("provider_intake.py")),
            "corpus-prepare",
        ],
        input=raw,
        text=True,
        capture_output=True,
        timeout=8,
    )
    (tmp_path / "stdout.json").write_text(result.stdout)
    (tmp_path / "stderr.txt").write_text(result.stderr)
    assert result.returncode == 0, result.stderr
    assert len(json.loads(result.stdout)["members"]) == 16
    assert time.monotonic() - start < 8

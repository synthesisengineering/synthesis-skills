"""Synthetic exact-material contracts through the actual packet and recorder owners."""

import base64
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest
import build_packet as bp
import record_rulings as rr
from test_packet_causal import spec

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jkAAAAABJRU5ErkJggg=="
)


def text_asset(
    text="Hello, fixture.\n\nA complete paragraph.\n\nRegards,\nSynthetic author",
    kind="correspondence",
    aid="draft",
):
    return {
        "id": aid,
        "title": "Complete synthetic draft",
        "kind": kind,
        "content": {"text": text, "sha256": hashlib.sha256(text.encode()).hexdigest()},
    }


def binary_asset(
    data=PNG, kind="image", media="image/png", filename="fixture.png", aid="image"
):
    return {
        "id": aid,
        "title": "Synthetic visual",
        "kind": kind,
        "filename": filename,
        "description": "A synthetic one-pixel fixture.",
        "content": {
            "base64": base64.b64encode(data).decode(),
            "sha256": hashlib.sha256(data).hexdigest(),
            "size": len(data),
            "media_type": media,
        },
    }


def review_spec():
    current = spec()
    current["rows"][0].update(
        revision="draft-3",
        delivery={
            "format": "Plain text",
            "destinations": ["reader@example.test"],
            "attachments": [],
        },
        review_assets=[text_asset()],
    )
    return current


def hard(current):
    return [p for p in bp.validate(current) if not p.startswith(("NOTE:", "READER:"))]


def test_actual_generator_and_cli_recorder_preserve_complete_material(tmp_path):
    current = review_spec()
    current["rows"][0]["review_assets"].append(binary_asset())
    current["rows"][0]["delivery"]["attachments"] = ["image"]
    filed, page = bp.file_packet(current, bp.build(current), tmp_path, "2026-09-27")
    summary = rr.compose_summary(
        current, {"R-0": {"choice": "test", "note": "Synthetic only"}}
    )
    proc = subprocess.run(
        [
            sys.executable,
            "-B",
            str(Path(rr.__file__)),
            "-",
            "--spec",
            str(filed),
            "--stdout",
        ],
        input=summary,
        text=True,
        capture_output=True,
        timeout=10,
    )
    assert proc.returncode == 0, proc.stderr
    record = json.loads(proc.stdout)
    for key in ("revision", "delivery", "review_assets"):
        assert record["rulings"][0][key] == current["rows"][0][key]
    assert record["authorization"]["granted"] is False
    assert record["authorization"]["authentication"] == "unverified"
    assert "renderReview" in page.read_text()


@pytest.mark.parametrize(
    "field,value",
    [
        ("revision", "draft-4"),
        ("format", "HTML"),
        ("destinations", ["other@example.test"]),
        ("attachments", ["draft"]),
        ("title", "Different draft title"),
        ("kind", "plain_text"),
        ("id", "draft-new"),
        ("text", "A changed draft."),
        ("description", "Changed description"),
    ],
)
def test_every_material_field_invalidates_persistence_and_returned_summary(
    field, value
):
    original = review_spec()
    response = rr.compose_summary(original, {"R-0": {"choice": "test"}})
    changed = copy.deepcopy(original)
    row = changed["rows"][0]
    if field == "revision":
        row[field] = value
    elif field in ("format", "destinations", "attachments"):
        row["delivery"][field] = value
    elif field == "text":
        row["review_assets"][0]["content"] = text_asset(value)["content"]
    else:
        row["review_assets"][0][field] = value
    assert not hard(changed)
    assert bp.spec_digest(changed) != bp.spec_digest(original)
    assert bp.spec_digest(changed) in bp.build(changed)
    with pytest.raises(rr.SummaryError, match="stale"):
        rr.parse_summary(response, changed)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda a: a.update(kind="html"),
        lambda a: a.update(path="/etc/passwd"),
        lambda a: a.update(id="../escape"),
        lambda a: a.update(id=[]),
        lambda a: a["content"].update(text="unbound change"),
        lambda a: a["content"].update(sha256="A" * 64),
        lambda a: a["content"].update(text="\x00"),
        lambda a: a["content"].update(text="\ud800"),
        lambda a: a.update(content={"text": "missing digest"}),
        lambda a: a.update(content={"unavailable": ""}),
        lambda a: a.update(content={"unavailable": "missing", "sha256": "0" * 64}),
        lambda a: a.update(
            content={"unavailable": "missing", "source": "javascript:alert(1)"}
        ),
        lambda a: a.update(
            content={
                "unavailable": "missing",
                "source": "https://user:pass@example.test/a",
            }
        ),
        lambda a: a.update(
            content={"unavailable": "missing", "source": "file:///etc/passwd"}
        ),
        lambda a: a.update(
            content={"unavailable": "missing", "source": "//example.test/a"}
        ),
        lambda a: a.update(
            content={"unavailable": "missing", "source": "https://example.test:9/a"}
        ),
    ],
)
def test_unsafe_or_ambiguous_assets_refused(mutation):
    current = review_spec()
    mutation(current["rows"][0]["review_assets"][0])
    assert hard(current)
    with pytest.raises(ValueError):
        bp.build(current)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda r: r.pop("delivery"),
        lambda r: r.pop("revision"),
        lambda r: r["delivery"].update(attachments=["missing"]),
        lambda r: r["delivery"].update(attachments=["draft", "draft"]),
        lambda r: r["delivery"].update(destinations=[{}]),
        lambda r: r["delivery"].update(secret="invisible"),
        lambda r: r.update(review_assets=[]),
        lambda r: r["review_assets"].append(copy.deepcopy(r["review_assets"][0])),
    ],
)
def test_delivery_and_asset_set_are_closed(mutation):
    current = review_spec()
    mutation(current["rows"][0])
    assert hard(current)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda a: a["content"].update(base64="!!!!"),
        lambda a: a["content"].update(size=True),
        lambda a: a["content"].update(size=1),
        lambda a: a["content"].update(media_type="image/svg+xml"),
        lambda a: a["content"].update(media_type="text/html"),
        lambda a: a["content"].update(sha256="0" * 64),
        lambda a: a.update(filename="../fixture.png"),
        lambda a: a.update(filename="fixture.html"),
        lambda a: a.update(filename="/tmp/fixture.png"),
        lambda a: a.pop("description"),
    ],
)
def test_binary_custody_refusals(mutation):
    current = review_spec()
    a = binary_asset()
    mutation(a)
    current["rows"][0]["review_assets"] = [a]
    assert hard(current)


def test_unresolved_material_stays_visible_but_cannot_acquire_a_choice():
    current = review_spec()
    current["rows"][0]["review_assets"][0]["content"] = {
        "unavailable": "Source not accessible in this capture.",
        "source": "https://example.test/source",
    }
    assert not hard(current)
    bp.build(current)
    assert rr.parse_summary(rr.compose_summary(current, {}), current)["decided"] == 0
    with pytest.raises(rr.SummaryError, match="unresolved"):
        rr.compose_summary(current, {"R-0": {"choice": "test"}})
    forged = {
        "schema_version": 2,
        "spec_sha256": bp.spec_digest(current),
        "selections": [
            {
                "id": r["id"],
                "choice": "test" if i == 0 else None,
                "note": "",
                "bulk": False,
            }
            for i, r in enumerate(current["rows"])
        ],
        "storage_blocked": False,
    }
    text = (
        rr.compose_summary(current, {}).split(rr.BINDING_PREFIX)[0]
        + rr.BINDING_PREFIX
        + json.dumps(forged)
    )
    with pytest.raises(rr.SummaryError, match="unresolved"):
        rr.parse_summary(text, current)


def test_text_unicode_full_size_and_byte_limits(monkeypatch):
    current = review_spec()
    t = (
        "مرحبا 🧪 e\u0301\n"
        + ("Long URL https://example.test/" + "a" * 1000 + "\n") * 90
    )
    current["rows"][0]["review_assets"] = [text_asset(t, "code")]
    assert not hard(current)
    assert (
        rr.parse_summary(rr.compose_summary(current, {}), current)["rulings"][0][
            "review_assets"
        ][0]["content"]["text"]
        == t
    )
    monkeypatch.setattr(bp, "MAX_REVIEW_TEXT_BYTES", 10)
    assert hard(current)


def test_aggregate_limit_applies_to_actual_decoded_bytes(monkeypatch):
    current = review_spec()
    monkeypatch.setattr(bp, "MAX_REVIEW_TOTAL_BYTES", 10)
    assert any("aggregate" in p for p in hard(current))


def test_external_source_is_never_read(monkeypatch):
    current = review_spec()
    current["rows"][0]["review_assets"][0]["content"] = {
        "unavailable": "No access",
        "source": "https://example.test/path",
    }
    monkeypatch.setattr(
        Path, "read_bytes", lambda *_: pytest.fail("implicit file read")
    )
    assert "https://example.test/path" in bp.build(current)


@pytest.mark.parametrize("node", ["symlink", "fifo", "directory", "oversize"])
def test_packet_file_input_is_finite_and_regular(tmp_path, monkeypatch, node):
    import os

    target = tmp_path / "spec.json"
    if node == "symlink":
        other = tmp_path / "other.json"
        other.write_text("{}")
        target.symlink_to(other)
    elif node == "fifo":
        os.mkfifo(target)
    elif node == "directory":
        target.mkdir()
    else:
        target.write_bytes(b"0123456789")
        monkeypatch.setattr(bp, "MAX_PACKET_INPUT_BYTES", 5)
    with pytest.raises((OSError, ValueError)):
        bp.read_packet_input(target)


def test_exact_packet_file_bytes_and_late_replacement(tmp_path, monkeypatch):
    target = tmp_path / "spec.json"
    raw = bp.canonical_spec_bytes(review_spec())
    target.write_bytes(raw)
    assert bp.read_packet_input(target) == raw
    original = Path.lstat

    def replace(path):
        if path == target:
            other = tmp_path / "replacement"
            other.write_bytes(raw)
            other.replace(target)
        return original(path)

    monkeypatch.setattr(Path, "lstat", replace)
    with pytest.raises(ValueError, match="changed"):
        bp.read_packet_input(target)


def test_every_binary_material_field_binds_current_generation():
    original = review_spec()
    original["rows"][0]["review_assets"] = [binary_asset()]
    response = rr.compose_summary(original, {"R-0": {"choice": "test"}})
    for key, value in [
        ("filename", "changed.png"),
        ("description", "A revised image description."),
    ]:
        current = copy.deepcopy(original)
        current["rows"][0]["review_assets"][0][key] = value
        assert not hard(current)
        with pytest.raises(rr.SummaryError, match="stale"):
            rr.parse_summary(response, current)
    current = copy.deepcopy(original)
    current["rows"][0]["review_assets"][0] = binary_asset(PNG + b"changed")
    assert not hard(current)
    with pytest.raises(rr.SummaryError, match="stale"):
        rr.parse_summary(response, current)


def test_legacy_grant_is_not_replaced_by_packet_record(tmp_path):
    current = review_spec()
    proc = subprocess.run(
        [
            sys.executable,
            "-B",
            str(Path(rr.__file__)),
            "-",
            "--legacy-unbound",
            "--stdout",
        ],
        input=rr.compose_legacy_summary(current, {"R-0": {"choice": "test"}}),
        text=True,
        capture_output=True,
        timeout=10,
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["authorization"]["granted"] is False


@pytest.mark.parametrize(
    "width,height", [(0, 1), (8193, 1), (4097, 4097), (2**31, 2**31)]
)
def test_compressed_image_cannot_claim_unbounded_decoded_size(width, height):
    data = PNG[:16] + width.to_bytes(4, "big") + height.to_bytes(4, "big") + PNG[24:]
    current = review_spec()
    current["rows"][0]["review_assets"] = [binary_asset(data)]
    assert any("dimensions" in p for p in hard(current))


@pytest.mark.parametrize(
    "media,data,expected",
    [
        ("image/png", PNG, (1, 1)),
        ("image/gif", b"GIF89a\x02\x00\x03\x00", (2, 3)),
        (
            "image/jpeg",
            b"\xff\xd8\xff\xc0\x00\x08\x08\x00\x03\x00\x02\x00\xff\xd9",
            (2, 3),
        ),
        (
            "image/webp",
            b"RIFF" + bytes(4) + b"WEBPVP8X" + bytes(8) + b"\x01\x00\x00\x02\x00\x00",
            (2, 3),
        ),
    ],
)
def test_dimension_readers_positive(media, data, expected):
    assert bp._review_image_dimensions(media, data) == expected


def test_large_bound_packet_is_accepted_by_actual_context_doctor_reader(tmp_path):
    conformance = (
        Path(bp.__file__).resolve().parents[2] / "synthesis-agent-conformance/scripts"
    )
    sys.path.insert(0, str(conformance))
    import skill_outputs

    current = review_spec()
    current["title"] = "Synthetic large review packet"
    current["rows"][0]["review_assets"] = [binary_asset(PNG + b"0" * (3 * 1024 * 1024))]
    spec_path, page_path = bp.file_packet(
        current, bp.build(current), tmp_path, "2026-09-27"
    )
    assert page_path.stat().st_size < 8 * 1024 * 1024
    assert spec_path.is_file()
    assert skill_outputs.verify_packet(page_path) == []


def test_escaped_text_cannot_exceed_actual_output_consumer_ceiling():
    current = review_spec()
    current["rows"][0]["review_assets"] = [
        text_asset("\\" * 1048576, aid="asset" + str(i)) for i in range(4)
    ]
    assert not hard(current)
    with pytest.raises(ValueError, match="context-doctor"):
        bp.build(current)


def test_succession_owner_keeps_material_binding_and_non_authorizing_status():
    scripts = (
        Path(bp.__file__).resolve().parents[2] / "synthesis-context-lifecycle/scripts"
    )
    sys.path.insert(0, str(scripts))
    import record_succession

    current = review_spec()
    recorded = rr.parse_summary(
        rr.compose_summary(current, {"R-0": {"choice": "test"}}), current
    )
    assert (
        record_succession.decision_status(json.dumps(recorded).encode(), current, "R-0")
        == "bound-answer-unverified"
    )
    recorded["rulings"][0]["review_assets"][0]["content"]["text"] += " forged"
    with pytest.raises(record_succession.SuccessionError, match="invalid bound ruling"):
        record_succession.decision_status(json.dumps(recorded).encode(), current, "R-0")

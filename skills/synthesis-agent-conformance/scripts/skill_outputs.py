"""Skill-output provenance verification.

Skills that ship deterministic generators (today: synthesis-decision-packet
via build_packet.py) mark their outputs with machine-verifiable provenance.
This module checks those marks. It exists because prose in a skill cannot
stop an agent substituting a hand-made lookalike — a failing doctor check
can. Shipped 2026-09-20 after a Muse session hand-authored two packets.

Registry: skill -> output globs + verifier. Extend by adding an entry and
a verifier; every skill with generated outputs belongs here.

Exit codes (CLI): 0 clean, 1 defects, 2 cannot verify.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

MARKER_RE = re.compile(
    r"<!-- synthesis-decision-packet spec-sha256:([0-9a-f]{64}) -->"
)
EMBEDDED_SPEC_RE = re.compile(
    r'<script type="application/json" id="spec">(.*?)</script>', re.S
)
SKILL = "synthesis-decision-packet"
PACKET_GLOB = "resources/artifacts/*packet*.html"
CHECK_NAME = "skill-outputs"


@dataclass
class OutputFinding:
    path: Path
    severity: str  # "defect" | "warning"
    message: str
    remedy: str


def _slug_of_page(page: Path) -> str:
    stem = page.stem
    m = re.match(r"\d{4}-\d{2}-\d{2}-(.+)", stem)
    return m.group(1) if m else stem


def _siblings(page: Path, suffix: str) -> list[Path]:
    return sorted(page.parent.glob(f"*-{_slug_of_page(page)}-{suffix}.json"))


def verify_packet(page: Path) -> list[OutputFinding]:
    """Verify one packet page. Any filed date matches for siblings."""
    try:
        text = _succession_owner().rt._snapshot(page)[0].decode("utf-8")
    except (OSError, ValueError, RuntimeError):
        return [OutputFinding(page, "defect",
                              f"{page.name} is unreadable; provenance unverifiable",
                              "restore the file or remove it if it is debris")]
    if "synthesis-packet-retired" in text:
        try:
            module = _succession_owner()
            project = page.parent.parent.parent
            candidates = [p for p in module.records(project)
                          if module.rt._read_json(p)[0].get("request", {}).get("inventory", {}).get("path")
                          == str(page.relative_to(project))]
            if len(candidates) != 1:
                raise ValueError("retired interface needs one exact succession record")
            module.validate_record(project, candidates[0])
            return []
        except (OSError, ValueError, RuntimeError) as exc:
            return [OutputFinding(page, "defect", str(exc), "preserve all custody and recover through context_edit")]
    marker = MARKER_RE.search(text)
    if marker is None:
        return [OutputFinding(page, "defect",
                              f"{page.name} is not generator output (no provenance marker) — "
                              "hand-authored packets skip note boxes, impact blocks, persistence, "
                              "and reader checks",
                              "rebuild it with build_packet.py --strict-reader --file-into, "
                              "or retire it through context_edit with exact custody and surviving obligations")]
    embedded = EMBEDDED_SPEC_RE.search(text)
    if embedded is None:
        return [OutputFinding(page, "defect",
                              f"{page.name} carries a marker but no embedded spec — forged or truncated",
                              "rebuild it with build_packet.py; do not hand-edit generator output")]
    actual = hashlib.sha256(embedded.group(1).encode("utf-8")).hexdigest()
    if actual != marker.group(1):
        return [OutputFinding(page, "defect",
                              f"{page.name} fails marker verification (embedded spec does not match "
                              "the marker hash) — edited after generation",
                              "rebuild it with build_packet.py; do not hand-edit generator output")]
    if not _siblings(page, "spec"):
        return [OutputFinding(page, "warning",
                              f"{page.name} verifies but its -spec.json is not filed beside it",
                              "file the spec with --file-into so other agents can rebuild and audit")]
    return []


def _succession_owner():
    scripts = Path(__file__).resolve().parents[2] / "synthesis-context-lifecycle/scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    import record_succession
    return record_succession


def scan_project(project_path: Path) -> list[OutputFinding]:
    findings: list[OutputFinding] = []
    try:
        owner = _succession_owner()
        with owner.rt.managed(project_path):
            deadline = time.monotonic() + owner.SCAN_SECONDS
            for page in owner.packet_pages(project_path):
                if time.monotonic() > deadline:
                    raise ValueError("packet scan time bound exceeded")
                findings.extend(verify_packet(page))
            for record in owner.records(project_path):
                if time.monotonic() > deadline:
                    raise ValueError("succession scan time bound exceeded")
                try:
                    result = owner.validate_record(project_path, record)
                    if result['current_destinations'] == 'changed-requires-review':
                        findings.append(OutputFinding(record, "warning", "succession destinations changed; historical custody verifies but current readiness needs review", "inspect surviving obligations; do not infer completion"))
                except (OSError, ValueError, RuntimeError) as exc:
                    findings.append(OutputFinding(record, "defect", str(exc),
                        "preserve custody; recover the transaction or reconcile exact source changes"))
    except (OSError, ValueError, RuntimeError) as exc:
        findings.append(OutputFinding(project_path, "defect", str(exc), "restore the managed record boundary"))
    return findings


def registry() -> dict:
    """The skill-output registry. Every generator-backed skill registers here."""
    return {
        SKILL: {
            "generators": ["skills/synthesis-decision-packet/scripts/build_packet.py"],
            "glob": PACKET_GLOB,
            "marker": "synthesis-decision-packet spec-sha256",
        },
    }


def doctor() -> tuple[bool, str]:
    """Heartbeat: the registry loads and the patterns compile."""
    try:
        reg = registry()
        assert reg[SKILL]["glob"] == PACKET_GLOB
        MARKER_RE.search("")
        EMBEDDED_SPEC_RE.search("")
        return True, f"skill-outputs registry ok ({len(reg)} skill)"
    except Exception as exc:
        return False, f"skill-outputs registry broken: {exc}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", help="project directory to scan")
    ap.add_argument("--doctor", action="store_true", help="heartbeat only")
    args = ap.parse_args(argv)
    if args.doctor:
        ok, msg = doctor()
        print(("PASS " if ok else "FAIL ") + msg)
        return 0 if ok else 2
    if not args.project:
        ap.error("--project DIR is required (or --doctor)")
    project = Path(args.project)
    if not project.is_dir():
        print(f"skill_outputs: {project} is not a directory", file=sys.stderr)
        return 2
    findings = scan_project(project)
    for f in findings:
        print(f"{f.severity.upper()} {f.path.name}: {f.message} :: {f.remedy}")
    if any(f.severity == "defect" for f in findings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

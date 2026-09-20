#!/usr/bin/env python3
"""Cross-machine handoff: the REMOTE_READY source gate and pull/verify resume.

Design: 2026-09-19-fleet-architecture.md section 4. Handoff moves *work*,
never process state: the unit is a repo plus its flushed manifests, and the
two halves meet at the git remote plus the leased board. Harness-neutral by
construction — the resume contract is a plan file + git + board checklist,
with no harness session formats anywhere in this module.

Source half (``create_handoff_offer``):

1. Worksets are enumerated with git truth (remote URL, branch, SHA, dirty
   files, ahead/behind).
2. Readiness is ``BLOCKED`` when any alert fires (dirty, unpushed,
   unpulled, missing remote/upstream), else ``REMOTE_READY`` when manifests
   were flushed, else ``CLEAN``. ``BLOCKED`` refuses before any board offer
   is posted (FLEET-AC-09).
3. The offer is recorded on the board as a ``handoff-offer`` message
   addressed to the destination machine-id, the source row parks (claims
   frozen, recoverable), and the offer seals into an artifact carrying the
   ticket id.

Destination half (``verify_destination`` + ``accept_handoff``):

1. The destination finds the offer addressed to its machine-id.
2. Verification keys on (remote URL, branch, SHA) — never the source's
   local paths — and refuses dirty destination state with the file list
   (FLEET-AC-10), leaving the source row parked.
3. The destination claims scope through the normal claim verb, posts
   ``handoff-accept``, and completes the resume checklist
   (``resume_checklist`` + ``write_resume_receipt``), identically for every
   harness lane (FLEET-AC-11).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import coordination as _coord

GIT_TIMEOUT_SECONDS = 30

READINESS_CLEAN = "CLEAN"
READINESS_REMOTE_READY = "REMOTE_READY"
READINESS_BLOCKED = "BLOCKED"

OFFER_RECORD_RE = re.compile(
    r"^handoff-offer\s+ticket=(\S+)\s+from_machine=(\S+)\s+"
    r"to_machine=(\S+)\s+readiness=(\S+)\s+session=(\S+)\s+seal=(\S+)\s*$"
)
REPO_RECORD_RE = re.compile(
    r"^handoff-repo\s+remote=(\S+)\s+branch=(\S+)\s+sha=(\S+)"
    r"(?:\s+repo=(.*))?\s*$"
)
ACCEPT_RECORD_RE = re.compile(
    r"^handoff-accept\s+ticket=(\S+)\s+from_machine=(\S+)\s+"
    r"to_machine=(\S+)\s+session=(\S+)(?:\s+shas=(\S*))?\s*$"
)


class HandoffError(ValueError):
    """A handoff that cannot proceed (missing session, ticket, or state)."""


class HandoffBlocked(HandoffError):
    """The source gate refused: ``alerts`` names every blocking condition."""

    def __init__(self, alerts: list[str]):
        super().__init__(
            "handoff source gate BLOCKED: " + "; ".join(alerts)
        )
        self.alerts = list(alerts)


class HandoffSealError(HandoffError):
    """A sealed artifact failed verification (tamper or corruption)."""


class ResumeIncomplete(HandoffError):
    """The resume checklist failed; no receipt is written."""

    def __init__(self, failures: dict[str, str]):
        super().__init__(
            "resume checklist incomplete: "
            + "; ".join(f"{name}: {detail}" for name, detail in failures.items())
        )
        self.failures = dict(failures)


@dataclass
class WorksetStatus:
    """Git truth for one repo in the handing-off scope."""

    repo: str
    """Human label (directory name); informational only, never an identity."""
    path: str
    """Source-local path; never interpreted on the destination."""
    remote_url: str
    branch: str
    sha: str
    dirty_files: list[str] = field(default_factory=list)
    ahead: int = 0
    behind: int = 0
    upstream: str = ""

    def alerts(self) -> list[str]:
        found = []
        if not self.remote_url:
            found.append(f"{self.repo}: no origin remote configured")
        if self.dirty_files:
            found.append(
                f"{self.repo}: dirty files: {', '.join(self.dirty_files)}"
            )
        if self.ahead:
            found.append(
                f"{self.repo}: {self.ahead} unpushed commit(s) on {self.branch}"
            )
        if self.behind:
            found.append(
                f"{self.repo}: {self.behind} unpulled commit(s) on {self.branch}"
            )
        if self.remote_url and not self.upstream:
            found.append(f"{self.repo}: no upstream tracks {self.branch}")
        return found


def _run_git(args: list[str], cwd: Path):
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=GIT_TIMEOUT_SECONDS,
        check=False,
    )


def collect_workset_status(repo_path: str | Path, *, git_runner=None) -> WorksetStatus:
    """Enumerate git truth for one workset repo on the source Mac."""
    runner = git_runner or _run_git
    root = Path(repo_path).expanduser()
    label = root.name or str(root)

    def show(args: list[str]) -> str:
        try:
            completed = runner(args, root)
        except (OSError, subprocess.SubprocessError) as exc:
            raise HandoffError(f"{label}: git failed: {exc}")
        if completed.returncode != 0:
            return ""
        return completed.stdout.strip()

    remote_url = show(["config", "--get", "remote.origin.url"])
    branch = show(["branch", "--show-current"]) or show(
        ["rev-parse", "--abbrev-ref", "HEAD"]
    )
    sha = show(["rev-parse", "HEAD"])
    dirty = [
        line[3:]
        for line in show(["status", "--porcelain"]).splitlines()
        if line.strip()
    ]
    upstream = show(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"])
    ahead = behind = 0
    if upstream:
        counts = show(["rev-list", "--left-right", "--count", "HEAD...@{upstream}"])
        parts = counts.split()
        if len(parts) == 2 and all(part.isdigit() for part in parts):
            ahead, behind = int(parts[0]), int(parts[1])
    return WorksetStatus(
        repo=label,
        path=str(root),
        remote_url=remote_url,
        branch=branch,
        sha=sha,
        dirty_files=dirty,
        ahead=ahead,
        behind=behind,
        upstream=upstream,
    )


def source_readiness(
    statuses: list[WorksetStatus], manifests: list[str]
) -> tuple[str, list[str]]:
    """The source gate truth table (§4.2): BLOCKED/REMOTE_READY/CLEAN."""
    alerts = [alert for status in statuses for alert in status.alerts()]
    if alerts:
        return READINESS_BLOCKED, alerts
    if manifests:
        return READINESS_REMOTE_READY, []
    return READINESS_CLEAN, []


def new_ticket() -> str:
    return "handoff-" + secrets.token_hex(6)


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def canonical_offer_bytes(offer: dict) -> bytes:
    return json.dumps(offer, sort_keys=True, separators=(",", ":")).encode("utf-8")


def seal_offer(offer: dict, *, sealed_at: str | None = None) -> dict:
    """Seal an offer dict into a tamper-evident artifact payload."""
    return {
        "ticket": offer["ticket"],
        "sealed_at": sealed_at or utcnow_iso(),
        "seal": hashlib.sha256(canonical_offer_bytes(offer)).hexdigest(),
        "offer": offer,
    }


def verify_sealed_artifact(sealed: dict) -> dict:
    """Return the offer inside a sealed artifact, or raise HandoffSealError."""
    if not isinstance(sealed, dict):
        raise HandoffSealError("sealed handoff artifact must be a JSON object")
    offer = sealed.get("offer")
    if not isinstance(offer, dict) or not offer.get("ticket"):
        raise HandoffSealError("sealed handoff artifact carries no offer")
    if sealed.get("ticket") != offer["ticket"]:
        raise HandoffSealError(
            f"sealed handoff ticket {sealed.get('ticket')!r} does not match "
            f"its offer {offer['ticket']!r}"
        )
    expected = hashlib.sha256(canonical_offer_bytes(offer)).hexdigest()
    if sealed.get("seal") != expected:
        raise HandoffSealError(
            f"sealed handoff {offer['ticket']} failed verification: content "
            "does not match its seal"
        )
    return offer


def write_sealed_artifact(artifacts_dir: Path, sealed: dict) -> Path:
    """Persist a sealed artifact; refuses to overwrite a different seal."""
    directory = Path(artifacts_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{sealed['ticket']}.sealed.json"
    if path.exists():
        try:
            previous = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            previous = None
        if not isinstance(previous, dict) or previous.get("seal") != sealed.get("seal"):
            raise HandoffSealError(
                f"handoff artifact {path} already seals a different offer; "
                "refusing to overwrite"
            )
        return path
    staging = path.with_suffix(".json.tmp")
    staging.write_text(json.dumps(sealed, indent=2) + "\n", encoding="utf-8")
    os.replace(staging, path)
    return path


def read_sealed_artifact(path: Path) -> dict:
    """Read and verify a sealed artifact file."""
    try:
        sealed = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise HandoffSealError(f"handoff artifact not found: {path}")
    except (OSError, ValueError) as exc:
        raise HandoffSealError(f"handoff artifact unreadable: {path}: {exc}")
    verify_sealed_artifact(sealed)
    return sealed


def offer_block(offer: dict, seal: str, *, stamp: str) -> str:
    lines = [
        f"### → {offer['to_machine']}, from handoff-offer — {stamp}",
        "",
        f"handoff-offer ticket={offer['ticket']} "
        f"from_machine={offer['from_machine']} "
        f"to_machine={offer['to_machine']} "
        f"readiness={offer['readiness']} "
        f"session={offer['session_compact']} seal={seal}",
    ]
    for workset in offer["worksets"]:
        lines.append(
            f"handoff-repo remote={workset['remote_url']} "
            f"branch={workset['branch']} sha={workset['sha']} "
            f"repo={workset['repo']}"
        )
    lines.extend(
        [
            f"Handoff offer: {offer['from_label']} → {offer['to_label']}: "
            f"{len(offer['worksets'])} repo(s), readiness {offer['readiness']}. "
            f"Verify (remote, branch, sha) per repo, claim scope, then accept.",
            "",
        ]
    )
    return "\n".join(lines)


def accept_block(
    *,
    ticket: str,
    from_machine: str,
    to_machine: str,
    dest_compact: str,
    shas: list[str],
    stamp: str,
) -> str:
    return "\n".join(
        [
            f"### → {to_machine}, from handoff-accept — {stamp}",
            "",
            f"handoff-accept ticket={ticket} from_machine={from_machine} "
            f"to_machine={to_machine} session={dest_compact} "
            f"shas={','.join(shas)}",
            f"Handoff accepted: {dest_compact} holds the scope for {ticket}.",
            "",
        ]
    )


def _record_lines(content: str, pattern: re.Pattern) -> list[re.Match]:
    from peer_addressing import parse_messages

    matches = []
    for message in parse_messages(content):
        for line in message.body.splitlines():
            match = pattern.match(line.strip())
            if match:
                matches.append(match)
    return matches


def find_offers(content: str, *, to_machine: str | None = None) -> list[dict]:
    """Every handoff offer on the board, optionally addressed to one Mac."""
    from peer_addressing import parse_messages

    offers = []
    for message in parse_messages(content):
        header = None
        repos: list[dict] = []
        for line in message.body.splitlines():
            offer_match = OFFER_RECORD_RE.match(line.strip())
            if offer_match:
                header = {
                    "ticket": offer_match.group(1),
                    "from_machine": offer_match.group(2),
                    "to_machine": offer_match.group(3),
                    "readiness": offer_match.group(4),
                    "session_compact": offer_match.group(5),
                    "seal": offer_match.group(6),
                }
                continue
            repo_match = REPO_RECORD_RE.match(line.strip())
            if repo_match and header is not None:
                repos.append(
                    {
                        "remote_url": repo_match.group(1),
                        "branch": repo_match.group(2),
                        "sha": repo_match.group(3),
                        "repo": (repo_match.group(4) or "").strip(),
                    }
                )
        if header is not None:
            if to_machine is None or header["to_machine"] == to_machine:
                header["worksets"] = repos
                offers.append(header)
    return offers


def find_accepts(content: str, *, ticket: str | None = None) -> list[dict]:
    """Every handoff accept on the board, optionally for one ticket."""
    accepts = []
    for match in _record_lines(content, ACCEPT_RECORD_RE):
        record = {
            "ticket": match.group(1),
            "from_machine": match.group(2),
            "to_machine": match.group(3),
            "session_compact": match.group(4),
            "shas": [sha for sha in (match.group(5) or "").split(",") if sha],
        }
        if ticket is None or record["ticket"] == ticket:
            accepts.append(record)
    return accepts


def create_handoff_offer(
    content: str,
    *,
    session_selector: str,
    dest_machine_id: str,
    dest_label: str,
    source_machine_id: str,
    source_label: str,
    statuses: list[WorksetStatus],
    manifests: list[str],
    ticket: str | None = None,
    now: datetime | None = None,
) -> tuple[str, dict]:
    """Run the source gate; on success post the offer and park the source.

    Raises HandoffBlocked before touching the board when the gate is
    BLOCKED (FLEET-AC-09: no offer is posted, the alert list returns).
    Returns the updated board content and the sealed artifact payload.
    """
    readiness, alerts = source_readiness(statuses, manifests)
    if readiness == READINESS_BLOCKED:
        raise HandoffBlocked(alerts)
    if not dest_machine_id.strip():
        raise HandoffError("handoff offer requires a destination machine-id")
    current = _coord.rows(content)
    session = _coord.find_session(current, session_selector)
    if session is None:
        raise HandoffError(f"handoff source session not found: {session_selector}")
    if session.status == "released":
        raise HandoffError(
            f"cannot hand off released session {session.label}"
        )
    moment = now or datetime.now(timezone.utc)
    stamp = moment.isoformat(timespec="seconds")
    updated = content
    if not _coord.is_parked(session):
        updated = _coord.park_session(
            updated,
            session_selector,
            basis="operator",
            actor=f"{source_label} handoff",
            now=moment,
        )
        session = _coord.find_session(_coord.rows(updated), session_selector)
    offer = {
        "ticket": ticket or new_ticket(),
        "from_machine": source_machine_id,
        "from_label": source_label,
        "to_machine": dest_machine_id,
        "to_label": dest_label,
        "session_compact": session.compact_id,
        "readiness": readiness,
        "worksets": [
            {
                "repo": status.repo,
                "remote_url": status.remote_url,
                "branch": status.branch,
                "sha": status.sha,
            }
            for status in statuses
        ],
        "manifests": list(manifests),
        "offered_at": stamp,
    }
    sealed = seal_offer(offer, sealed_at=stamp)
    updated = _coord.append_bus_block(updated, offer_block(offer, sealed["seal"], stamp=stamp))
    return updated, sealed


def default_remote_probe(remote_url: str, branch: str, sha: str, clone: Path) -> bool:
    """Whether the offered SHA is reachable from the remote via the clone."""
    fetched = _run_git(["fetch", "--quiet", "origin", branch], clone)
    if fetched.returncode != 0:
        return False
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", sha or ""):
        return False
    probed = _run_git(["cat-file", "-e", sha], clone)
    return probed.returncode == 0


def verify_destination(
    offer: dict,
    clones: dict[str, str | Path],
    *,
    git_runner=None,
    remote_probe=None,
) -> list[str]:
    """Verify the destination can take the offer; alerts (empty = verified).

    ``clones`` maps each offered remote URL to the destination's local clone
    path. Every check keys on (remote URL, branch, SHA); the source's local
    paths never enter. Dirty destination state refuses with the file list
    (FLEET-AC-10); the caller leaves the source row parked.
    """
    runner = git_runner or _run_git
    probe = remote_probe or (
        lambda remote, branch, sha, clone: default_remote_probe(
            remote, branch, sha, clone
        )
    )
    alerts: list[str] = []
    for workset in offer.get("worksets", []):
        remote_url = workset.get("remote_url", "")
        branch = workset.get("branch", "")
        sha = workset.get("sha", "")
        label = workset.get("repo") or remote_url
        raw_clone = clones.get(remote_url)
        if raw_clone is None:
            alerts.append(
                f"{label}: no destination clone of {remote_url}; clone it "
                "to a fleet-standard path, then resume"
            )
            continue
        clone = Path(raw_clone).expanduser()
        try:
            origin = runner(["config", "--get", "remote.origin.url"], clone)
        except (OSError, subprocess.SubprocessError):
            alerts.append(f"{label}: destination path is not a git checkout: {clone}")
            continue
        if origin.returncode != 0:
            alerts.append(f"{label}: destination path is not a git checkout: {clone}")
            continue
        if origin.stdout.strip().rstrip("/") != remote_url.rstrip("/"):
            alerts.append(
                f"{label}: destination remote {origin.stdout.strip()} does "
                f"not match offered {remote_url}"
            )
            continue
        try:
            if not probe(remote_url, branch, sha, clone):
                alerts.append(
                    f"{label}: offered {branch}@{sha[:12] if sha else '?'} "
                    f"is not reachable from {remote_url}"
                )
                continue
        except (OSError, subprocess.SubprocessError) as exc:
            alerts.append(f"{label}: remote verification failed: {exc}")
            continue
        try:
            status = runner(["status", "--porcelain"], clone)
        except (OSError, subprocess.SubprocessError) as exc:
            alerts.append(f"{label}: destination status failed: {exc}")
            continue
        dirty = [
            line[3:] for line in status.stdout.splitlines() if line.strip()
        ]
        if dirty:
            alerts.append(f"{label}: dirty files: {', '.join(dirty)}")
    return alerts


def accept_handoff(
    content: str,
    *,
    ticket: str,
    dest_machine_id: str,
    dest_compact: str,
    now: datetime | None = None,
) -> str:
    """Post the handoff-accept for a verified offer, addressed to the source.

    Scope claiming stays the destination's separate normal claim; this posts
    the accept record once verification and claiming hold.
    """
    offers = [offer for offer in find_offers(content) if offer["ticket"] == ticket]
    if not offers:
        raise HandoffError(f"handoff offer not found on the board: {ticket}")
    offer = offers[0]
    if offer["to_machine"] != dest_machine_id:
        raise HandoffError(
            f"handoff {ticket} is addressed to {offer['to_machine']}, "
            f"not {dest_machine_id}"
        )
    if find_accepts(content, ticket=ticket):
        raise HandoffError(f"handoff {ticket} was already accepted")
    moment = now or datetime.now(timezone.utc)
    return _coord.append_bus_block(
        content,
        accept_block(
            ticket=ticket,
            from_machine=dest_machine_id,
            to_machine=offer["from_machine"],
            dest_compact=dest_compact,
            shas=[workset["sha"] for workset in offer["worksets"]],
            stamp=moment.isoformat(timespec="seconds"),
        ),
    )


def resume_checklist(
    content: str,
    *,
    ticket: str,
    dest_compact: str,
    repo_states: list[dict],
    now: datetime | None = None,
) -> dict:
    """The harness-neutral resume contract (§4.4) as five named checks.

    ``repo_states`` carries destination git truth per offered repo label:
    ``{"repo": label, "clean": bool, "head_ok": bool}`` where ``head_ok``
    means HEAD equals the offered SHA or a documented descendant (the caller
    proves ancestry with git; this checklist asserts the flag).
    """
    _ = now
    offers = [offer for offer in find_offers(content) if offer["ticket"] == ticket]
    if not offers:
        raise HandoffError(f"handoff offer not found on the board: {ticket}")
    offer = offers[0]
    sessions = _coord.rows(content)
    dest = _coord.find_session(sessions, dest_compact)
    accepts = find_accepts(content, ticket=ticket)
    checks: dict[str, dict] = {}

    if dest is not None and _coord.active(dest) and accepts:
        checks["board-truth"] = {
            "ok": True,
            "detail": f"fresh board shows {dest.compact_id} active with accept posted",
        }
    else:
        missing = []
        if dest is None or not _coord.active(dest):
            missing.append(f"destination row {dest_compact} is not active")
        if not accepts:
            missing.append(f"no handoff-accept for {ticket}")
        checks["board-truth"] = {"ok": False, "detail": "; ".join(missing)}

    by_repo = {entry.get("repo"): entry for entry in repo_states}
    code_problems = []
    for workset in offer["worksets"]:
        state = by_repo.get(workset["repo"])
        if state is None:
            code_problems.append(f"{workset['repo']}: no destination state reported")
        elif not state.get("clean"):
            code_problems.append(f"{workset['repo']}: working state is not clean")
        elif not state.get("head_ok"):
            code_problems.append(
                f"{workset['repo']}: HEAD is not the offered SHA or a descendant"
            )
    checks["code-truth"] = (
        {"ok": True, "detail": f"{len(offer['worksets'])} repo(s) match accepted SHAs"}
        if not code_problems
        else {"ok": False, "detail": "; ".join(code_problems)}
    )

    context_problems = [
        f"{workset.get('repo')}: missing {field}"
        for workset in offer["worksets"]
        for field in ("remote_url", "branch", "sha")
        if not workset.get(field)
    ]
    checks["context-truth"] = (
        {
            "ok": True,
            "detail": "offer is sourceless-complete: every repo carries "
            "(remote, branch, sha); nothing source-local is required",
        }
        if not context_problems
        else {"ok": False, "detail": "; ".join(context_problems)}
    )

    claim_problems = []
    if dest is not None:
        for other in sessions:
            if other.session_uuid == dest.session_uuid or not _coord.active(other):
                continue
            if _coord.is_parked(other):
                # Parked claims are frozen, not freed: overlap with them is
                # the overlaps-parked successor list below, never a refusal.
                continue
            for mine in dest.claims:
                for theirs in other.claims:
                    try:
                        conflict = _coord.overlaps(
                            mine,
                            theirs,
                            left_workspaces=dest.workspaces,
                            right_workspaces=other.workspaces,
                        )
                    except Exception:
                        conflict = True
                    if conflict:
                        claim_problems.append(
                            f"{mine} overlaps active {other.compact_id}:{theirs}"
                        )
    successors = [
        record
        for record in _coord.overlaps_parked_successors(
            content, offer["session_compact"]
        )
        if dest is None or record["new"] != dest.compact_id
    ]
    successor_note = (
        f"; overlaps-parked successors to re-validate, never force-push: "
        f"{', '.join(record['new'] for record in successors)}"
        if successors
        else "; no overlaps-parked successors recorded"
    )
    checks["claim-truth"] = (
        {"ok": True, "detail": f"no overlapping active claim{successor_note}"}
        if not claim_problems
        else {"ok": False, "detail": "; ".join(claim_problems)}
    )

    checks["receipt"] = {"ok": True, "detail": "pending: written on completion"}
    report = {
        "ticket": ticket,
        "destination": dest.compact_id if dest is not None else dest_compact,
        "checks": checks,
        "ok": all(check["ok"] for name, check in checks.items() if name != "receipt"),
    }
    return report


def write_resume_receipt(
    receipts_dir: Path, report: dict, *, accepted_shas: list[str]
) -> Path:
    """Write the resume receipt; a failing checklist writes nothing."""
    failures = {
        name: check["detail"]
        for name, check in report.get("checks", {}).items()
        if name != "receipt" and not check.get("ok")
    }
    if failures or not report.get("ok"):
        raise ResumeIncomplete(failures or {"report": "checklist did not pass"})
    directory = Path(receipts_dir)
    directory.mkdir(parents=True, exist_ok=True)
    receipt = {
        "ticket": report["ticket"],
        "destination": report.get("destination"),
        "accepted_shas": list(accepted_shas),
        "checks": {
            name: check["detail"] for name, check in report["checks"].items()
        },
        "written_at": utcnow_iso(),
    }
    path = directory / f"{report['ticket']}.resume.json"
    staging = path.with_suffix(".json.tmp")
    staging.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    os.replace(staging, path)
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    verify = commands.add_parser(
        "verify", help="Verify a sealed handoff artifact."
    )
    verify.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "verify":
        try:
            sealed = read_sealed_artifact(args.artifact)
        except HandoffSealError as exc:
            print(f"FAIL: {exc}", file=sys.stderr)
            return 1
        print(f"sealed handoff {sealed['ticket']} verifies (seal ok)")
        return 0
    raise AssertionError("unreachable")


if __name__ == "__main__":
    sys.exit(main())

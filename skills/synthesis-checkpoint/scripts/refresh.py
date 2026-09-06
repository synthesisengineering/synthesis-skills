#!/usr/bin/env python3
"""Inspect an established local project; explicitly report optional campaign feedback.

Inspection never writes, calls a client CLI, fetches, activates or repairs. The
feedback subcommand alone appends to the existing coordination bus. Its report is
diagnostic evidence, never claim authority or proof that an agent read prose.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import uuid

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
for directory in ("synthesis-project-management", "synthesis-agent-conformance"):
    sys.path.insert(0, str(ROOT / "skills" / directory / "scripts"))
import project_state
from plan_reference import locate_plan
from live_receipt import session_receipt_path
from conformance import _receipt_check
import coordination
from peer_addressing import all_seats, detect_self

MARKER = "REFRESH_FEEDBACK_JSON:"
CHECKS = frozenset({"recovery", "project_tiers", "native_runtime", "installed_parity", "skill_files"})
SKILLS = ("synthesis-checkpoint", "synthesis-project-management", "synthesis-context-lifecycle")
VERSION = re.compile(r"\d+\.\d+\.\d+\Z")
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,159}\Z")
HASH = re.compile(r"[0-9a-f]{64}\Z")
MAX_JSON = 512 * 1024


class RefreshError(ValueError):
    pass


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise RefreshError("duplicate JSON object key")
        result[key] = value
    return result


def read_json(path: Path) -> dict:
    if path.is_symlink() or path.stat().st_size > MAX_JSON:
        raise RefreshError("unsafe or oversized JSON input")
    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=strict_object)
    if not isinstance(value, dict):
        raise RefreshError("JSON input must be an object")
    return value


def campaign(path: Path, *, required: bool = False) -> dict | None:
    try:
        value = read_json(path)
    except FileNotFoundError:
        if required:
            raise RefreshError("explicit campaign file is missing")
        return None
    keys = {"schema_version", "id", "recipient", "checks", "minimum_plugin_version"}
    if set(value) != keys or type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise RefreshError("campaign schema or fields are invalid")
    if not isinstance(value["id"], str) or not ID.fullmatch(value["id"]):
        raise RefreshError("campaign id is invalid")
    recipient = value["recipient"]
    if not isinstance(recipient, str) or not recipient.strip() or len(recipient) > 200 or any(ord(c) < 32 for c in recipient):
        raise RefreshError("campaign recipient is invalid")
    checks = value["checks"]
    if not isinstance(checks, list) or not checks or any(not isinstance(c, str) or c not in CHECKS for c in checks) or len(set(checks)) != len(checks):
        raise RefreshError("campaign checks are invalid")
    minimum = value["minimum_plugin_version"]
    if not isinstance(minimum, str) or not VERSION.fullmatch(minimum):
        raise RefreshError("campaign minimum plugin version is invalid")
    return value


@contextmanager
def local_git():
    previous = os.environ.get("GIT_OPTIONAL_LOCKS")
    os.environ["GIT_OPTIONAL_LOCKS"] = "0"
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("GIT_OPTIONAL_LOCKS", None)
        else:
            os.environ["GIT_OPTIONAL_LOCKS"] = previous


def manifest_version(root: Path) -> str:
    versions = []
    for client in ("claude", "codex"):
        value = read_json(root / f".{client}-plugin" / "plugin.json")
        version = value.get("version")
        if value.get("name") != "synthesis-skills" or not isinstance(version, str) or not VERSION.fullmatch(version):
            raise RefreshError("plugin manifest identity is invalid")
        versions.append(version)
    if versions[0] != versions[1]:
        raise RefreshError("plugin manifests disagree")
    return versions[0]


def status(value: str, code: str, **extra) -> dict:
    return {"status": value, "code": code, **extra}


def identity(client_ref: str, native: str, board: Path) -> tuple[str | None, dict]:
    try:
        uuid.UUID(native)
    except (ValueError, TypeError):
        return None, status("UNKNOWN", "NATIVE_ID_UNVERIFIED")
    if client_ref == "codex:" + native:
        client = "codex"
    elif client_ref == "cc:" + native:
        client = "claude"
    elif client_ref.startswith("ccd:"):
        own = detect_self()
        joined = own.primary_ref == client_ref and own.harness_session_id == native
        if not joined:
            joined = any(s.harness_session_id == native and "ccd:" + s.host_session_id == client_ref for s in all_seats(board, strict=True))
        if not joined:
            return None, status("UNKNOWN", "DESKTOP_NATIVE_JOIN_UNVERIFIED")
        client = "claude"
    else:
        return None, status("UNKNOWN", "CLIENT_REF_UNVERIFIED")
    own = detect_self()
    if own.harness_session_id and (own.harness_session_id != native or (own.client == "codex") != (client == "codex")):
        return None, status("FAIL", "CALLER_IDENTITY_MISMATCH")
    return client, status("PASS", "NATIVE_REFERENCE_CONSISTENT", scope="declared reference consistency; native receipt checked separately")


def file_evidence(path: Path, role: str, *, required: bool = True) -> dict:
    result = {"role": role, "path": str(path), "required": required}
    try:
        if path.is_symlink():
            raise RefreshError("symlink evidence refused")
        data = path.read_bytes()
    except FileNotFoundError:
        return {**result, **status("FAIL" if required else "NOT_PRESENT", "REQUIRED_INPUT_MISSING" if required else "OPTIONAL_INPUT_ABSENT")}
    except (OSError, RefreshError):
        return {**result, **status("FAIL", "INPUT_UNREADABLE")}
    return {**result, **status("PASS", "FILE_INSPECTED"), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "lines": len(data.splitlines())}


def native_evidence(client: str, native: str, installed_version: str, live_root: Path) -> dict:
    latest = live_root / f"public-sessionstart-{client}.json"
    try:
        receipt = session_receipt_path(latest, client, native)
        if receipt is None:
            return status("UNKNOWN", "EXACT_NATIVE_RECEIPT_MISSING")
        value = read_json(receipt)
        root_text = value.get("plugin_root")
        if not isinstance(root_text, str) or not Path(root_text).is_absolute():
            raise RefreshError("native plugin root is invalid")
        root = Path(root_text)
        actual = manifest_version(root)
        checks = []
        _receipt_check(checks, "native", receipt, expected_client=client, expected_plugin_version=installed_version,
                       expected_plugin_root=root, max_age_hours=None, receipt_scope="session:" + native)
        passed = bool(checks and checks[0].ok and actual == installed_version)
        observed_version = value.get("plugin_version")
        if not isinstance(observed_version, str) or not VERSION.fullmatch(observed_version):
            observed_version = None
        return status("PASS" if passed else "FAIL", "EXACT_NATIVE_RECEIPT_VERIFIED" if passed else "NATIVE_RECEIPT_INVALID_OR_STALE",
                      receipt=str(receipt), receipt_sha256=hashlib.sha256(receipt.read_bytes()).hexdigest(),
                      transcript=str(value.get("transcript_path", "")), plugin_root=str(root), plugin_version=observed_version,
                      expected_plugin_version=installed_version,
                      scope="exact native transcript binding and on-disk plugin manifests; enabled live registry not queried")
    except (OSError, ValueError):
        return status("FAIL", "NATIVE_RECEIPT_UNREADABLE_OR_INVALID")


def selected_lifecycle(project: Path, index_name: str, project_id: str) -> tuple[dict, dict | None, bool]:
    """Read current lifecycle from the selected checkout, never its stale peer."""
    selected_index = project.parent / index_name
    state = None
    invalid_state = False
    states = []
    successors = set()
    known = {"active", "ongoing", "paused", "completed", "archived", "superseded"}
    uncertain = False
    try:
        repo = project_state._repository_root(project)
        tracked = project_state._run(repo, "ls-files", "--error-unmatch", "--", str(selected_index.relative_to(repo)), check=False)
        if tracked.returncode or selected_index.is_symlink():
            raise RefreshError("selected registry is not a tracked regular file")
        entry = project_state._index_entry(selected_index.read_text(encoding="utf-8"), project_id)
        lifecycle = re.search(r"(?m)^\s*status:\s*['\"]?([A-Za-z_-]+)", entry)
        registry_status = lifecycle.group(1).lower() if lifecycle else None
        if registry_status not in known:
            uncertain = True
        else:
            states.append(registry_status)
        successor = re.search(r"(?m)^\s*superseded_by:\s*['\"]?([A-Za-z0-9_-]+)", entry)
        if successor:
            successors.add(successor.group(1))
        state_path = project / project_state.STATE_FILE
        if state_path.exists():
            try:
                state = read_json(state_path)
                value = state.get("status")
                if not isinstance(value, str) or value.lower() not in known:
                    uncertain = True
                else:
                    states.append(value.lower())
                successor = state.get("superseded_by")
                if successor is not None:
                    if isinstance(successor, str) and ID.fullmatch(successor):
                        successors.add(successor)
                    else:
                        uncertain = True
            except (OSError, ValueError):
                invalid_state = uncertain = True
        else:
            # Only an explicit current Status field in legacy context counts;
            # narrative archive history is never promoted to current lifecycle.
            context = (project / "CONTEXT.md").read_text(encoding="utf-8")
            preamble = re.split(r"(?m)^#{2,6}\s", context, maxsplit=1)[0]
            preamble = re.sub(r"(?ms)^```[^\n]*\n.*?^```[^\n]*$|^~~~[^\n]*\n.*?^~~~[^\n]*$", "", preamble)
            fields = re.findall(r"(?im)^[ \t]*(?:\*\*)?Status:(?:\*\*)?[ \t]*([A-Za-z_-]+)", preamble)
            for field in fields:
                if field.lower() in known:
                    states.append(field.lower())
                else:
                    uncertain = True
    except (OSError, ValueError, project_state.ProjectStateError):
        uncertain = True
    archived = "archived" in states
    superseded = "superseded" in states or bool(successors)
    uncertain = uncertain or len(set(states)) > 1
    outcome = "BLOCKED" if archived or superseded else "UNKNOWN" if uncertain else "PASS"
    code = "PROJECT_ARCHIVED" if archived else "PROJECT_SUPERSEDED" if superseded else "PROJECT_STATUS_UNVERIFIED" if uncertain else "PROJECT_NOT_ARCHIVED"
    result = status(outcome, code, registry=str(selected_index), lifecycle_statuses=sorted(set(states)),
                    status_disagreement=len(set(states)) > 1)
    if successors:
        result["successor_ids"] = sorted(successors)
        if len(successors) == 1:
            result["successor_id"] = next(iter(successors))
    return result, state, invalid_state


def inspect(args, *, ignore_campaign: bool = False) -> tuple[dict, dict | None]:
    selected_campaign = None if ignore_campaign else campaign(args.campaign, required=args.campaign_explicit)
    # Recovery and transcript-bound identity are prerequisites even for a
    # campaign requesting only a subset of the optional inspection planes.
    requested = set(selected_campaign["checks"] if selected_campaign else CHECKS) | {"recovery", "native_runtime"}
    checks = {}
    report = {"schema_version": 1, "client_ref": args.client_ref, "delivery_client_ref": args.client_ref, "native_session_id": args.native_session_id,
              "project_locator": str(args.index.parent / args.project_id), "campaign": selected_campaign["id"] if selected_campaign else None,
              "campaign_descriptor_digest": digest(selected_campaign) if selected_campaign else None,
              "observed_at": datetime.now(timezone.utc).isoformat(), "checks": checks, "read_targets": [],
              "scope": "local machine inspection; no execution authority, agent reading, runtime reload, or complete ecosystem acceptance",
              "agent_reading": "NOT_VERIFIED", "claim_disposition": "UNCHANGED", "feedback": "NOT_REQUESTED"}
    with local_git():
        client, checks["identity"] = identity(args.client_ref, args.native_session_id, args.board)
        if client:
            report["client_ref"] = ("codex:" if client == "codex" else "cc:") + args.native_session_id
        registry_repo = project_state._repository_root(args.index.parent)
        tracked = project_state._run(registry_repo, "ls-files", "--error-unmatch", "--", str(args.index.relative_to(registry_repo)), check=False)
        if tracked.returncode:
            raise RefreshError("project registry is not Git tracked")
        recovery = project_state.resolve_project(args.project_id, args.index, repo_guard_root=args.state_root / "repo-guard",
            checkpoint_receipt_root=args.state_root / "project-state" / "receipts", coordination_board=args.board if args.board.is_file() else None,
            pointer=None, fetch=False, fast_forward_canonical=False, refresh_coordination=False)
        checks["recovery"] = status(recovery.status, "LOCAL_CAUSAL_RESOLUTION", selected_path=recovery.selected_path,
            selected_head=recovery.selected_head, selected_tree=recovery.selected_tree, issue_count=len(recovery.issues),
            candidate_count=len(recovery.candidates), candidates=[{"path": c.project_path, "head": c.head, "source": c.source} for c in recovery.candidates[:12]])
        # No project prose is opened before a causal selection exists.
        if recovery.status in {"PASS", "LOCAL_RECOVERABLE"} and recovery.selected_path:
            project = Path(recovery.selected_path)
            # The registry locator identifies the logical input across a
            # conflict-to-recovered transition; selected checkout stays in
            # recovery evidence instead of silently changing the report key.
            checks["project_status"], state, invalid_state = selected_lifecycle(project, args.index.name, args.project_id)
            if invalid_state:
                checks["structured_hashes"] = status("FAIL", "STRUCTURED_STATE_INVALID")
            if "project_tiers" in requested:
                targets = report["read_targets"]
                targets.append(file_evidence(project / project_state.STATE_FILE, "structured_state", required=False))
                targets.append(file_evidence(project / "CONTEXT.md", "context"))
                if targets[-1]["status"] == "PASS":
                    context = (project / "CONTEXT.md").read_text(encoding="utf-8")
                    plan = locate_plan(project, context, **({"controlling_plan": state.get("controlling_plan")} if state else {}))
                    if plan.resolved:
                        targets.append(file_evidence(plan.resolved, "controlling_plan"))
                    else:
                        targets.append({"role": "controlling_plan", "required": plan.declared is not None,
                            **status("FAIL" if plan.declared is not None else "NOT_PRESENT", "DECLARED_PLAN_INVALID" if plan.declared is not None else "OPTIONAL_PLAN_ABSENT")})
                targets.append(file_evidence(project / "REFERENCE.md", "reference", required=False))
                logs = sorted((project / "sessions").glob("????-??.md"))
                targets.append(file_evidence(logs[-1] if logs else project / "sessions" / "YYYY-MM.md", "latest_session"))
                issues = project_state.semantic_issues(project)
                required_fail = any(t["status"] == "FAIL" for t in targets)
                checks["project_tiers"] = status("FAIL" if required_fail or issues else "PASS", "PROJECT_INPUTS_INSPECTED", semantic_issue_count=len(issues),
                    warning_count=sum(t["status"] == "NOT_PRESENT" for t in targets), agent_reading="NOT_VERIFIED")
                if state is not None:
                    try:
                        hashes_match = state.get("content_hashes") == project_state._content_hashes(project, state.get("controlling_plan"))
                    except (OSError, ValueError, project_state.ProjectStateError):
                        hashes_match = False
                    checks["structured_hashes"] = status("PASS" if hashes_match else "FAIL", "STRUCTURED_CONTENT_HASHES")
        else:
            checks["project_tiers"] = status("NOT_CHECKED", "UNRESOLVED_PROJECT_NO_PROSE_READ")

        installed_version = None
        try:
            installed_version = manifest_version(args.installed_root)
            source_version = manifest_version(args.source_root)
            if "installed_parity" in requested:
                checks["installed_parity"] = status("PASS" if installed_version == source_version else "FAIL", "PLUGIN_MANIFEST_COMPARISON",
                    installed_version=installed_version, source_version=source_version, installed_root=str(args.installed_root), source_root=str(args.source_root),
                    scope="two on-disk plugin manifests per root; client enabled registry and complete tree parity not queried")
            if selected_campaign:
                enough = tuple(map(int, installed_version.split("."))) >= tuple(map(int, selected_campaign["minimum_plugin_version"].split(".")))
                checks["campaign_version"] = status("PASS" if enough else "FAIL", "CAMPAIGN_MINIMUM_PLUGIN_VERSION")
        except (OSError, ValueError):
            checks["installed_parity"] = status("UNKNOWN", "PLUGIN_MANIFEST_UNAVAILABLE")
        if "native_runtime" in requested:
            checks["native_runtime"] = native_evidence(client, args.native_session_id, installed_version, args.state_root / "agent-conformance" / "live") if client and installed_version else status("UNKNOWN", "NATIVE_PREREQUISITE_UNVERIFIED")
        if "skill_files" in requested:
            files = [file_evidence(args.installed_root / "skills" / name / "SKILL.md", "skill:" + name) for name in SKILLS]
            report["read_targets"].extend(files)
            checks["skill_files"] = status("PASS" if all(f["status"] == "PASS" for f in files) else "FAIL", "INSTALLED_SKILL_FILES_INSPECTED", agent_reading="NOT_VERIFIED")
    values = {c["status"] for c in checks.values()}
    report["overall"] = "BLOCKED" if values & {"FAIL", "CONFLICT", "BLOCKED"} else "UNKNOWN" if values & {"UNKNOWN", "NOT_CHECKED"} else "READY"
    report["remaining_action"] = "Agent must read indicated project tiers and current skills, verify enabled runtime and execution claim before project work."
    return report, selected_campaign


def stable_report(report: dict) -> dict:
    # Constructed machine fields only: no caller-supplied report, arbitrary
    # strings from project prose, human titles, raw errors or private replies.
    keys = ("schema_version", "campaign", "campaign_descriptor_digest", "client_ref", "native_session_id", "project_locator", "checks", "read_targets",
            "overall", "scope", "agent_reading", "claim_disposition", "remaining_action")
    result = {key: report[key] for key in keys}
    check_fields = {"status", "code", "scope", "selected_path", "selected_head", "selected_tree", "issue_count", "candidate_count", "candidates",
                    "successor_id", "successor_ids", "registry", "lifecycle_statuses", "status_disagreement", "semantic_issue_count", "warning_count", "agent_reading", "installed_version", "source_version", "installed_root", "source_root",
                    "receipt", "receipt_sha256", "transcript", "plugin_root", "plugin_version", "expected_plugin_version"}
    check_names = CHECKS | {"identity", "project_status", "structured_hashes", "campaign_version"}
    result["checks"] = {name: {key: value for key, value in check.items() if key in check_fields}
                        for name, check in report["checks"].items() if name in check_names}
    target_fields = {"role", "path", "required", "status", "code", "sha256", "bytes", "lines"}
    result["read_targets"] = [{key: value for key, value in target.items() if key in target_fields} for target in report["read_targets"]]
    return result


def feedback(report: dict, selected_campaign: dict | None, board: Path) -> dict:
    if selected_campaign is None:
        return {"outcome": "LOCAL_ONLY", "code": "NO_CAMPAIGN"}
    if report["checks"]["identity"]["status"] != "PASS":
        raise RefreshError("feedback identity is unverified")
    # Reverify the native identity independently of version currency. An old
    # transcript-bound receipt may report a blocked refresh, but another
    # session's valid receipt is never a substitute for this sender's evidence.
    client = "codex" if report["client_ref"].startswith("codex:") else "claude"
    native = report["checks"].get("native_runtime", {})
    receipt_path = native.get("receipt")
    if not receipt_path:
        raise RefreshError("feedback requires transcript-bound native identity evidence")
    receipt_path = Path(receipt_path)
    value = read_json(receipt_path)
    if value.get("session_id") != report["native_session_id"] or value.get("client") != client or hashlib.sha256(receipt_path.read_bytes()).hexdigest() != native.get("receipt_sha256"):
        raise RefreshError("feedback native receipt changed or belongs to another session")
    checked = []
    _receipt_check(checked, "identity", receipt_path, expected_client=client, max_age_hours=None, receipt_scope="session:" + report["native_session_id"])
    if not checked or not checked[0].ok:
        raise RefreshError("feedback native identity could not be verified")
    payload = stable_report(report)
    canonical_ref = ("codex:" if client == "codex" else "cc:") + report["native_session_id"]
    payload["client_ref"] = canonical_ref
    # Recipient, requested checks and minimum version are part of what this
    # campaign asks. Changing them must deliver a new revision even when the
    # inspected project bytes and campaign id remain unchanged.
    payload["campaign_descriptor_digest"] = digest(selected_campaign)
    key = hashlib.sha256((selected_campaign["id"] + "\n" + canonical_ref + "\n" + report["project_locator"]).encode()).hexdigest()
    result_digest = digest(payload)
    result = {}

    def operation(content: str) -> str:
        previous = []
        malformed_unrelated = 0
        for line in content.splitlines():
            if not line.startswith(MARKER):
                continue
            try:
                item = json.loads(line[len(MARKER):].strip(), object_pairs_hook=strict_object)
            except ValueError:
                if key in re.findall(r'"report_key"\s*:\s*"([0-9a-f]{64})"', line):
                    raise RefreshError("matching feedback marker is malformed")
                malformed_unrelated += 1
                continue
            if not isinstance(item, dict):
                malformed_unrelated += 1
                continue
            revision = item.get("revision")
            old_digest = item.get("result_digest")
            old_key = item.get("report_key")
            if type(revision) is not int or revision < 1 or not isinstance(old_digest, str) or not HASH.fullmatch(old_digest) or not isinstance(old_key, str) or not HASH.fullmatch(old_key):
                if old_key == key:
                    raise RefreshError("matching feedback report has invalid revision or digest")
                malformed_unrelated += 1
                continue
            if old_key != key:
                continue
            previous.append(item)
        result.update(warning_count=malformed_unrelated, malformed_unrelated_records=malformed_unrelated)
        revisions = {}
        for item in previous:
            revision = item["revision"]
            if revision in revisions and revisions[revision] != item["result_digest"]:
                raise RefreshError("matching feedback report has conflicting revisions")
            revisions[revision] = item["result_digest"]
        latest = max(previous, key=lambda p: p["revision"]) if previous else None
        if latest and latest["result_digest"] == result_digest:
            result.update(outcome="ALREADY_RECORDED", report_key=key, revision=latest["revision"], result_digest=result_digest)
            return content
        revision = max(revisions, default=0) + 1
        message = {**payload, "report_key": key, "revision": revision, "result_digest": result_digest, "observed_at": report["observed_at"],
                   "delivery_client_ref": report.get("delivery_client_ref", report["client_ref"])}
        current = coordination.rows(content)
        kind, matches = coordination.resolve_targets(current, selected_campaign["recipient"])
        if kind in {"identity", "client-ref"}:
            if len(matches) != 1:
                raise RefreshError("feedback recipient is ambiguous")
            recipient = matches[0].label
        elif kind == "project":
            recipient = f"{matches[0].project} sessions"
        else:
            recipient = coordination.sanitize(selected_campaign["recipient"])
        boundary = re.search(r"(?m)^---[ \t]*\n\n## Protocol(?:[^\n]*)?$", content)
        if not boundary:
            raise RefreshError("board lacks Protocol boundary")
        block = f"### → {recipient}, from {coordination.sanitize(canonical_ref)} — {coordination.timestamp()}\n\n{MARKER}{json.dumps(message, sort_keys=True, separators=(',', ':'))}\n\n"
        result.update(outcome="APPENDED", report_key=key, revision=revision, result_digest=result_digest)
        return content[:boundary.start()] + block + content[boundary.start():]

    coordination.locked_update(board, operation)
    # A successful locked_update returns only after publishing/mirroring the
    # exact operation; no second unlocked read can overwrite that evidence.
    return result


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=("inspect", "feedback"))
    p.add_argument("--project-id", required=True)
    p.add_argument("--index", required=True, type=Path)
    p.add_argument("--client-ref", required=True)
    p.add_argument("--native-session-id", required=True)
    p.add_argument("--source-root", type=Path, default=ROOT)
    p.add_argument("--installed-root", type=Path, default=ROOT)
    p.add_argument("--state-root", type=Path, default=Path.home() / ".synthesis")
    p.add_argument("--board", type=Path)
    p.add_argument("--campaign", type=Path)
    p.add_argument("--no-campaign", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    report = None
    try:
        if not ID.fullmatch(args.project_id) or not args.index.is_absolute():
            raise RefreshError("project id and absolute registry path are required")
        if args.no_campaign and args.campaign:
            raise RefreshError("--campaign and --no-campaign are mutually exclusive")
        args.campaign_explicit = args.campaign is not None
        args.state_root = args.state_root.expanduser().resolve()
        args.campaign = args.campaign or args.state_root / "checkpoint" / "active-campaign.json"
        args.board = (args.board or args.state_root / "coordination" / "active-sessions.md").expanduser().resolve()
        args.index = args.index.expanduser().resolve()
        args.source_root = args.source_root.expanduser().resolve()
        args.installed_root = args.installed_root.expanduser().resolve()
        if args.no_campaign:
            # Explicit absence, not a caller-controlled dummy pathname.
            selected_campaign = None
            report, _ = inspect_without_campaign(args)
        else:
            report, selected_campaign = inspect(args)
        if args.command == "feedback":
            report["feedback"] = feedback(report, selected_campaign, args.board)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["overall"] == "READY" else 1
    except (OSError, ValueError, project_state.ProjectStateError, RuntimeError):
        if report is not None:
            # A transport refusal must not erase the completed inspection.
            # The final transcript remains a complete local feedback fallback.
            report["feedback"] = {"outcome": "NOT_DELIVERED", "code": "REFRESH_FEEDBACK_FAILED"}
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            print(json.dumps({"schema_version": 1, "overall": "UNKNOWN", "code": "REFRESH_INPUT_OR_OPERATION_FAILED", "feedback": "NOT_DELIVERED" if args.command == "feedback" else "NOT_REQUESTED"}))
        return 2


def inspect_without_campaign(args):
    # Kept separate from campaign loading so --no-campaign cannot accidentally
    # process a malformed or unwanted active campaign.
    return inspect(args, ignore_campaign=True)


if __name__ == "__main__":
    raise SystemExit(main())

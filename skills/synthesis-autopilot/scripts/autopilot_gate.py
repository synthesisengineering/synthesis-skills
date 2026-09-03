#!/usr/bin/env python3
"""autopilot_gate.py — the continuation stop-gate for autonomous engagements.

The failure this exists to prevent (observed live, 2026-08-29): a principal
delegated an overnight run and went to sleep; the agent engaged autopilot
correctly, ran two phases, and then its turn ended. Nothing in the harness
runs between turns, so the session sat idle all night — the machine even
rebooted unnoticed, because nothing was executing — and the phase that was
the entire point never started. The engagement LOOKED active the whole time.

The gate makes that silent stop impossible. Engaging autopilot registers the
engagement here; a Stop while any registered engagement is active and
unfinished is refused unless the agent has done one of three legal things:

  1. recorded a CONTINUATION — the verified mechanism that causes the next
     turn (in-flight background work whose completion re-invokes the
     session, a self-scheduled wakeup/loop, or a cron/scheduled re-entry);
  2. recorded a BLOCKER — with the principal alerted, per the skill's
     blocked-state alert rules;
  3. CLOSED the engagement — goals met, or explicitly incomplete with a
     reason.

All three outs are satisfiable by the agent alone, so the gate can fail
closed without deadlocking a session. An engagement is bound to its
coordination seat, project, and client-session identity. A live or abandoned
engagement owned by another session never blocks an unrelated session.

Runaway control lives in `cycle`: recording a wake that advanced nothing
requires a named external wait (`--waiting-on`). There is no way to record
a bare spin, so a loop that is burning cycles without progress has to
either name what it is waiting for or stop and alert.

Modes:
  register      --plan PATH --mission TEXT      begin an engagement
  continuation  --plan PATH --mechanism TEXT --next-wake TEXT --survives TEXT
  cycle         --plan PATH (--advanced TEXT | --no-advance --waiting-on TEXT)
  blocker       --plan PATH --reason TEXT --alerted
  close         --plan PATH (--goals-met | --incomplete TEXT)
  --gate        Stop-hook mode: read payload on stdin, allow (0) or block (2)
  --doctor      self-check with positive and negative controls
  --test        hermetic behavioral suite

Environment:
  AUTOPILOT_GATE_STATE_DIR  registry dir
                            (default ~/.synthesis/autopilot/engagements)
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ENGINE_VERSION = "1.1.0"


def state_dir() -> Path:
    return Path(os.environ.get(
        "AUTOPILOT_GATE_STATE_DIR",
        os.path.expanduser("~/.synthesis/autopilot/engagements"),
    ))


def entry_path(plan: str) -> Path:
    plan = os.path.abspath(os.path.expanduser(plan))
    key = hashlib.sha1(plan.encode()).hexdigest()[:12]
    return state_dir() / f"{Path(plan).stem[:40]}-{key}.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load(path: Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent))
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    os.replace(tmp, path)


def load_for_plan(plan: str) -> tuple[Path, dict]:
    path = entry_path(plan)
    if not path.exists():
        print(f"no engagement registered for plan {plan} "
              f"(expected {path}); run register first", file=sys.stderr)
        raise SystemExit(2)
    return path, load(path)


def _board_rows(path: Path) -> list[dict[str, str]]:
    text = path.read_text(encoding="utf-8")
    header = None
    rows: list[dict[str, str]] = []
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if header is None and "session uuid" in {cell.lower() for cell in cells}:
            header = [cell.lower() for cell in cells]
            continue
        if header is None or all(set(cell) <= {"-", ":"} for cell in cells):
            continue
        if len(cells) == len(header):
            rows.append(dict(zip(header, cells)))
    if header is None:
        raise ValueError("coordination board has no active-session table")
    return rows


def _project_from_plan(plan: str) -> str:
    parts = Path(plan).resolve().parts
    if "projects" in parts:
        index = len(parts) - 1 - list(reversed(parts)).index("projects")
        if index + 1 < len(parts):
            return parts[index + 1]
    return ""


def _registration_identity(plan: str) -> tuple[str, str, str, Path, dict[str, str]]:
    session_id = (
        os.environ.get("AUTOPILOT_GATE_SESSION_ID")
        or os.environ.get("SYNTHESIS_COORDINATION_SESSION")
        or ""
    ).strip()
    project_id = (
        os.environ.get("AUTOPILOT_GATE_PROJECT_ID") or _project_from_plan(plan)
    ).strip()
    client_ref = os.environ.get("SYNTHESIS_CLIENT_SESSION_REF", "").strip()
    board = Path(os.environ.get(
        "AUTOPILOT_GATE_COORDINATION_BOARD",
        os.path.expanduser("~/.synthesis/coordination/active-sessions.md"),
    )).resolve()
    if not session_id or not project_id or not client_ref:
        raise ValueError(
            "registration requires session, project, and client-session identity"
        )
    matches = [
        row for row in _board_rows(board)
        if row.get("session uuid") == session_id
        and row.get("project") == project_id
        and row.get("client session ref") == client_ref
        and row.get("status", "").lower() == "active"
    ]
    if len(matches) != 1:
        raise ValueError("registration requires exactly one matching active coordination claim")
    plan_path = str(Path(plan).resolve())
    row = matches[0]
    coverage = row.get("claimed areas (advisory lock)", "") + " " + row.get("workspace(s) / branch", "")
    project_root = str(Path(plan_path).parent.parent.parent)
    roots = [
        str(Path(token.strip().removesuffix("/**").removesuffix("/*")).resolve())
        for token in re.split(r"(?:<br>|[,;\s]+)", coverage)
        if token.strip().startswith("/")
    ]
    if plan_path not in coverage and project_root not in coverage and not any(
        plan_path == root or plan_path.startswith(root.rstrip("/") + "/")
        for root in roots
    ):
        raise ValueError("active coordination claim does not cover the autopilot plan")
    return session_id, project_id, client_ref, board, row


def cmd_register(plan: str, mission: str, horizon: str) -> int:
    if not mission.strip():
        print("register: --mission must describe what done means",
              file=sys.stderr)
        return 2
    try:
        session_id, project_id, client_ref, board, claim = _registration_identity(plan)
    except (OSError, ValueError) as exc:
        print(f"register: coordination claim binding failed: {exc}", file=sys.stderr)
        return 2
    path = entry_path(plan)
    if path.exists() and load(path).get("status") == "active":
        data = load(path)
        data.update({
            "session_id": session_id,
            "project_id": project_id,
            "client_session_ref": client_ref,
            "coordination_board": str(board),
            "claim_hash": hashlib.sha256(
                json.dumps(claim, sort_keys=True).encode()
            ).hexdigest(),
        })
        save(path, data)
        print(f"engagement binding refreshed for this plan: {path}")
        return 0
    save(path, {
        "plan": os.path.abspath(os.path.expanduser(plan)),
        "mission": mission.strip(),
        "horizon": horizon,
        "session_id": session_id,
        "project_id": project_id,
        "client_session_ref": client_ref,
        "coordination_board": str(board),
        "claim_hash": hashlib.sha256(
            json.dumps(claim, sort_keys=True).encode()
        ).hexdigest(),
        "engaged_at": now_iso(),
        "status": "active",
        "goals_met": False,
        "continuation": None,
        "blocker": None,
        "cycles": [],
    })
    print(f"engagement registered: {path}")
    return 0


def cmd_continuation(plan: str, mechanism: str, next_wake: str,
                     survives: str) -> int:
    for label, val in (("--mechanism", mechanism), ("--next-wake", next_wake),
                       ("--survives", survives)):
        if not val.strip():
            print(f"continuation: {label} must be non-empty — an unnamed "
                  "mechanism is the silent-idle failure restated",
                  file=sys.stderr)
            return 2
    path, data = load_for_plan(plan)
    data["continuation"] = {
        "mechanism": mechanism.strip(),
        "next_wake": next_wake.strip(),
        "survives": survives.strip(),
        "recorded_at": now_iso(),
    }
    save(path, data)
    print(f"continuation recorded ({mechanism.strip()[:60]})")
    return 0


def cmd_cycle(plan: str, advanced: str | None, no_advance: bool,
              waiting_on: str | None) -> int:
    path, data = load_for_plan(plan)
    if advanced and advanced.strip():
        data["cycles"].append({"at": now_iso(), "advanced": advanced.strip()})
    elif no_advance:
        if not (waiting_on and waiting_on.strip()):
            print("cycle: a wake that advanced nothing must name the external "
                  "wait (--waiting-on). There is no way to record a bare "
                  "spin — if nothing advanced and nothing external is "
                  "awaited, the run is spinning: stop and alert instead.",
                  file=sys.stderr)
            return 2
        data["cycles"].append({"at": now_iso(),
                               "waiting_on": waiting_on.strip()})
    else:
        print("cycle: pass --advanced TEXT or --no-advance --waiting-on TEXT",
              file=sys.stderr)
        return 2
    save(path, data)
    print(f"cycle recorded ({len(data['cycles'])} total)")
    return 0


def cmd_blocker(plan: str, reason: str, alerted: bool) -> int:
    if not reason.strip():
        print("blocker: --reason must say what prevents the goals",
              file=sys.stderr)
        return 2
    if not alerted:
        print("blocker: pass --alerted only after the principal alert has "
              "actually fired (the skill's blocked-state alert rules). A "
              "blocker nobody was told about is the silent stop again.",
              file=sys.stderr)
        return 2
    path, data = load_for_plan(plan)
    data["blocker"] = {"reason": reason.strip(), "alerted_at": now_iso()}
    save(path, data)
    print("blocker recorded (principal alerted)")
    return 0


def cmd_close(plan: str, goals_met: bool, incomplete: str | None) -> int:
    path, data = load_for_plan(plan)
    if goals_met:
        data["goals_met"] = True
        data["status"] = "closed"
        data["closed_at"] = now_iso()
    elif incomplete and incomplete.strip():
        data["status"] = "closed"
        data["closed_incomplete"] = incomplete.strip()
        data["closed_at"] = now_iso()
    else:
        print("close: pass --goals-met, or --incomplete REASON for an "
              "honest incomplete close", file=sys.stderr)
        return 2
    save(path, data)
    print(f"engagement closed: {path.name}")
    return 0


def _caller_identity(payload: dict) -> tuple[set[str], str]:
    identities = {
        str(payload.get(key) or "").strip()
        for key in ("session_id", "root_task_uuid", "task_id")
    }
    configured = os.environ.get("SYNTHESIS_CLIENT_SESSION_REF", "").strip()
    if configured:
        identities.add(configured)
        identities.add(configured.rsplit(":", 1)[-1])
    return {value for value in identities if value}, str(payload.get("cwd") or "")


def _owned_by_caller(data: dict, identities: set[str], cwd: str) -> bool:
    session_id = str(data.get("session_id") or "")
    client_ref = str(data.get("client_session_ref") or "")
    if session_id in identities or client_ref in identities:
        return True
    if client_ref and client_ref.rsplit(":", 1)[-1] in identities:
        return True
    plan = str(data.get("plan") or "")
    return (
        not session_id
        and not client_ref
        and bool(cwd)
        and plan.startswith(str(Path(cwd).resolve()) + os.sep)
    )


def _foreign_claim_state(data: dict) -> str:
    try:
        board = Path(str(data.get("coordination_board") or ""))
        session_id = str(data.get("session_id") or "")
        project_id = str(data.get("project_id") or "")
        if not board.is_file() or not session_id:
            return "UNKNOWN"
        rows = _board_rows(board)
        return "ACTIVE" if any(
            row.get("session uuid") == session_id
            and row.get("project") == project_id
            and row.get("status", "").lower() == "active"
            for row in rows
        ) else "INACTIVE"
    except Exception:
        return "UNKNOWN"


def gate() -> int:
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            payload = {}
    except Exception:
        payload = {}
    identities, cwd = _caller_identity(payload)
    root = state_dir()
    if not root.is_dir():
        return 0
    offenders: list[str] = []
    for path in sorted(root.glob("*.json")):
        try:
            data = load(path)
        except Exception as exc:
            print(f"autopilot-gate BLOCKED (fail closed): engagement record "
                  f"{path} is unreadable ({exc}). Repair or remove it — an "
                  "unreadable engagement cannot prove it was continued.",
                  file=sys.stderr)
            return 2
        if data.get("status") != "active" or data.get("goals_met"):
            continue
        if not _owned_by_caller(data, identities, cwd):
            state = _foreign_claim_state(data)
            print(
                "autopilot-gate: foreign engagement does not block this "
                f"session (project={data.get('project_id') or 'unknown'}, "
                f"session={data.get('session_id') or 'legacy'}, claim={state})",
                file=sys.stderr,
            )
            continue
        if data.get("continuation") or data.get("blocker"):
            continue
        offenders.append(
            f"{data.get('mission', path.name)!r} (plan {data.get('plan')})")
    if not offenders:
        return 0
    me = os.path.basename(__file__)
    print(
        "autopilot-gate BLOCKED: this session owns an autopilot "
        "engagement is active, unfinished, and has NO continuation — the "
        "exact shape of the overnight silent-idle failure. Engagements: "
        + "; ".join(offenders) + ". Before stopping, do exactly one: "
        f"(1) establish the next turn and record it ({me} continuation "
        "--plan P --mechanism ... --next-wake ... --survives ...), "
        f"(2) alert the principal and record the blocker ({me} blocker "
        "--plan P --reason ... --alerted), or "
        f"(3) close the engagement honestly ({me} close --plan P "
        "--goals-met | --incomplete REASON). Foreign engagements are reported "
        "separately and never block this session.",
        file=sys.stderr,
    )
    return 2


def run_doctor() -> int:
    ok = True

    def report(good: bool, label: str, detail: str = "") -> None:
        nonlocal ok
        print("  %s %s%s" % ("ok " if good else "FAIL", label,
                             ": " + detail if detail else ""))
        ok = ok and good

    print(f"autopilot-gate doctor (engine v{ENGINE_VERSION})")
    root = state_dir()
    try:
        root.mkdir(parents=True, exist_ok=True)
        probe = root / ".doctor-probe"
        probe.write_text("x", encoding="utf-8")
        probe.unlink()
        report(True, "state dir writable", str(root))
    except Exception as exc:
        report(False, "state dir writable", str(exc))
    bad = 0
    for path in root.glob("*.json"):
        try:
            load(path)
        except Exception:
            bad += 1
    report(bad == 0, "registry parseable",
           f"{bad} unreadable record(s)" if bad else "all records parse")
    print("HEALTHY" if ok else "UNHEALTHY")
    return 0 if ok else 2


def main() -> int:
    argv = sys.argv[1:]
    if not argv or argv[0] == "--gate":
        return gate()
    if argv[0] == "--doctor":
        return run_doctor()

    def val(flag: str) -> str | None:
        return argv[argv.index(flag) + 1] if flag in argv else None

    mode = argv[0]
    plan = val("--plan") or ""
    if not plan:
        print(__doc__)
        return 0 if mode in ("-h", "--help") else 2
    if mode == "register":
        return cmd_register(plan, val("--mission") or "",
                            val("--horizon") or "unspecified")
    if mode == "continuation":
        return cmd_continuation(plan, val("--mechanism") or "",
                                val("--next-wake") or "",
                                val("--survives") or "")
    if mode == "cycle":
        return cmd_cycle(plan, val("--advanced"),
                         "--no-advance" in argv, val("--waiting-on"))
    if mode == "blocker":
        return cmd_blocker(plan, val("--reason") or "", "--alerted" in argv)
    if mode == "close":
        return cmd_close(plan, "--goals-met" in argv, val("--incomplete"))
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())

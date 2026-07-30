#!/usr/bin/env python3
"""synthesis-message-guard — fail-closed pre-send gate for agent-drafted correspondence.

v1.1.0 (2026-07-29)

A PreToolUse hook engine that blocks message-sending and draft-creating tool
calls unless (a) the outgoing text passes a deterministic register scan against
a configured pattern set, and (b) a fresh, single-use grounding ledger exists
that is cryptographically bound (sha256) to the exact outgoing text and attests
that the composing agent did the research: read the full thread, searched prior
correspondence, and mapped every factual claim to a source.

Design principles (inherited from the synthesis-git-hooks v2 incident):
  1. FAIL CLOSED. Any internal error, unparseable config, unknown tool shape,
     or missing ledger blocks the send. "Engine broken" and "nothing to detect"
     are structurally distinguishable; absence of a positive pass is a block.
  2. ZERO DEPENDENCIES. Stdlib only. Behavior is identical under any python3.
  3. SELF-DIAGNOSING. --doctor verifies config, wiring, patterns, and runs
     positive controls (a known-bad text MUST trip the scanner; a known-clean
     text MUST pass). A guard nobody monitors is already broken.

Modes:
  --gate            (default) run as a Claude Code PreToolUse hook: read the
                    tool-call JSON on stdin, allow (exit 0) or block (exit 2).
  --sha             read message text on stdin, print its sha256. Convenience
                    for the composing agent when writing the ledger.
  --scan            read message text on stdin, print scan findings, exit 2 if
                    any block-tier hit. Lets an agent pre-check wording.
  --ledger-template print a skeleton ledger JSON.
  --doctor          self-check, including every active client hook config;
                    exit 0 HEALTHY / 2 UNHEALTHY.
  --test            behavioral test suite; exit 0 all pass / 2 failures.

Environment overrides (used by --test; safe to leave unset):
  MESSAGE_GUARD_CONFIG     path to patterns/config JSON
                           (default ~/.synthesis/message-guard/patterns.json)
  MESSAGE_GUARD_STATE_DIR  ledger/log dir (default ~/.synthesis/message-guard)
  MESSAGE_GUARD_CLAUDE_SETTINGS  Claude Code hooks to inspect in --doctor
                                 (default ~/.claude/settings.json)
  MESSAGE_GUARD_CODEX_HOOKS      Codex hooks to inspect in --doctor
                                 (default ~/.codex/hooks.json)
"""

import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone

ENGINE_VERSION = "1.1.0"


def config_path():
    return os.environ.get(
        "MESSAGE_GUARD_CONFIG",
        os.path.expanduser("~/.synthesis/message-guard/patterns.json"),
    )


def state_dir():
    return os.environ.get(
        "MESSAGE_GUARD_STATE_DIR", os.path.expanduser("~/.synthesis/message-guard")
    )


def ledger_path():
    return os.path.join(state_dir(), "ledger.json")


def log_path():
    return os.path.join(state_dir(), "log.jsonl")


# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

REQUIRED_CONFIG_KEYS = ("gated_tool_patterns", "exempt_tool_patterns",
                        "block_patterns", "warn_patterns",
                        "ledger_max_age_minutes", "text_field_candidates")


def load_config():
    """Load and validate config. Raises on ANY problem (caller fails closed)."""
    path = config_path()
    with open(path, "r", encoding="utf-8") as fh:
        cfg = json.load(fh)
    for key in REQUIRED_CONFIG_KEYS:
        if key not in cfg:
            raise ValueError("config missing required key: %s" % key)
    # Compile every regex now: an uncompilable pattern must fail loudly here,
    # never silently skip (a skipped pattern is an invisible hole in the guard).
    compiled_block = [(p["name"], re.compile(p["regex"], re.IGNORECASE))
                      for p in cfg["block_patterns"]]
    compiled_warn = [(p["name"], re.compile(p["regex"], re.IGNORECASE))
                     for p in cfg["warn_patterns"]]
    gated = [re.compile(p) for p in cfg["gated_tool_patterns"]]
    exempt = [re.compile(p) for p in cfg["exempt_tool_patterns"]]
    return cfg, compiled_block, compiled_warn, gated, exempt


# --------------------------------------------------------------------------
# Scan
# --------------------------------------------------------------------------

def scan_text(text, compiled_block, compiled_warn):
    blocks, warns = [], []
    for name, rx in compiled_block:
        m = rx.search(text)
        if m:
            blocks.append((name, m.group(0)))
    for name, rx in compiled_warn:
        m = rx.search(text)
        if m:
            warns.append((name, m.group(0)))
    return blocks, warns


def extract_text(tool_input, candidates):
    """Return (field_name, text) for the outgoing message, or (None, None)."""
    for key in candidates:
        val = tool_input.get(key)
        if isinstance(val, str) and val.strip():
            return key, val
    return None, None


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# Ledger
# --------------------------------------------------------------------------

def validate_ledger(ledger, text, cfg, tool_name):
    """Return list of failure strings; empty list = valid."""
    fails = []

    created = ledger.get("created_at", "")
    try:
        ts = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age_min = (datetime.now(timezone.utc) - ts).total_seconds() / 60.0
        if age_min < -2:
            fails.append("ledger created_at is in the future")
        elif age_min > float(cfg["ledger_max_age_minutes"]):
            fails.append(
                "ledger is stale (%.0f min old; max %s). Re-ground and rewrite it."
                % (age_min, cfg["ledger_max_age_minutes"]))
    except Exception:
        fails.append("ledger created_at missing or unparseable (use ISO-8601)")

    if ledger.get("message_sha256") != sha256_text(text):
        fails.append(
            "message_sha256 does not match the outgoing text. The message was "
            "edited after grounding, or the ledger was written for a different "
            "message. Re-verify the final text and rewrite the ledger "
            "(pipe the exact text to --sha).")

    if ledger.get("is_reply") is None:
        fails.append("ledger must state is_reply: true or false")

    if ledger.get("is_reply"):
        tfr = ledger.get("thread_fully_read") or {}
        if not (isinstance(tfr, dict) and tfr.get("source_ids")):
            fails.append(
                "is_reply=true but thread_fully_read.source_ids is empty — read "
                "the ENTIRE thread (including quoted history) and cite message "
                "IDs / ts values actually fetched this session.")
        hs = ledger.get("history_searched") or []
        ok = [h for h in hs if isinstance(h, dict) and h.get("query") and h.get("where")]
        if not ok:
            fails.append(
                "is_reply=true but history_searched is empty — search prior "
                "correspondence for this recipient/topic (all mailboxes AND "
                "local transcripts) and record each query and where it ran.")

    claims = ledger.get("claims")
    if ledger.get("no_factual_claims") is True:
        pass
    elif isinstance(claims, list) and claims:
        for i, c in enumerate(claims):
            if not (isinstance(c, dict) and c.get("claim") and c.get("source")):
                fails.append("claims[%d] must have non-empty claim and source" % i)
    else:
        fails.append(
            "ledger needs a claims[] array mapping every factual claim to its "
            "source, or no_factual_claims: true if the message asserts nothing.")

    for flag in ("voice_rules_pass", "invented_precision_scan",
                 "recipient_address_check"):
        if ledger.get(flag) is not True:
            fails.append("ledger flag %s must be explicitly true" % flag)

    if re.search(r"slack_send_message$", tool_name):
        if ledger.get("ragbot_branding_check") is not True:
            fails.append(
                "direct Slack sends require ragbot_branding_check: true — load "
                "the communications skill and verify tier + signature before "
                "sending as the agent.")

    return fails


# --------------------------------------------------------------------------
# Gate
# --------------------------------------------------------------------------

def block(msg):
    sys.stderr.write("message-guard BLOCKED: %s\n" % msg)
    sys.exit(2)


def run_gate():
    try:
        payload = json.load(sys.stdin)
        tool_name = payload.get("tool_name", "")
        tool_input = payload.get("tool_input") or {}

        cfg, cblock, cwarn, gated, exempt = load_config()

        if any(rx.search(tool_name) for rx in exempt):
            sys.exit(0)
        if not any(rx.search(tool_name) for rx in gated):
            # Reached us via settings matcher but not recognized: unknown = closed.
            block("tool %r matched the hook wiring but is not in "
                  "gated_tool_patterns. Update patterns.json deliberately "
                  "rather than sending through an unclassified tool." % tool_name)

        field, text = extract_text(tool_input, cfg["text_field_candidates"])
        if text is None:
            block("could not locate the outgoing message text in tool input "
                  "(looked for: %s). Unknown shape fails closed; add the field "
                  "name to text_field_candidates deliberately."
                  % ", ".join(cfg["text_field_candidates"]))

        hits, warns = scan_text(text, cblock, cwarn)
        if hits:
            detail = "; ".join("[%s] matched %r" % (n, s) for n, s in hits)
            block("register scan failed — %s. These patterns are banned in "
                  "messages on the principal's behalf (see the writing-voice "
                  "skill). Rewrite the message; do not paraphrase the banned "
                  "phrase into a synonym of itself." % detail)

        lp = ledger_path()
        if not os.path.exists(lp):
            block("no grounding ledger at %s. Before composing you must: "
                  "(1) read the FULL thread including quoted history, "
                  "(2) search prior correspondence for this recipient/topic "
                  "across all mailboxes and local transcripts, "
                  "(3) map every factual claim to a source, "
                  "(4) run the voice pass. Then write the ledger "
                  "(--ledger-template for the skeleton, --sha for the hash) "
                  "and retry. One ledger per message; it is consumed on use."
                  % lp)
        try:
            with open(lp, "r", encoding="utf-8") as fh:
                ledger = json.load(fh)
        except Exception as exc:
            block("ledger exists but is unreadable (%s). Rewrite it." % exc)

        fails = validate_ledger(ledger, text, cfg, tool_name)
        if fails:
            block("ledger invalid — " + " | ".join(fails))

        # Passed: consume the ledger (single use) and log the pass.
        record = {
            "at": datetime.now(timezone.utc).isoformat(),
            "tool": tool_name,
            "field": field,
            "sha256": sha256_text(text),
            "warns": [{"name": n, "match": s} for n, s in warns],
            "ledger": ledger,
            "engine": ENGINE_VERSION,
        }
        os.makedirs(state_dir(), exist_ok=True)
        with open(log_path(), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
        os.remove(lp)
        if warns:
            # Advisory only — surfaced to the model, does not block.
            sys.stderr.write(
                "message-guard advisory (allowed): %s\n"
                % "; ".join("[%s] %r" % (n, s) for n, s in warns))
        sys.exit(0)

    except SystemExit:
        raise
    except Exception as exc:  # ANY unexpected failure blocks. Fail closed.
        block("internal error (%s: %s) — the guard cannot verify this send, "
              "so it does not pass. Run --doctor." % (type(exc).__name__, exc))


# --------------------------------------------------------------------------
# Doctor
# --------------------------------------------------------------------------

POSITIVE_CONTROL_BAD = ("I'm sorry for the delay — I went quiet on you, and "
                        "I'm the least able to judge this myself.")
POSITIVE_CONTROL_CLEAN = ("Thank you for writing this up properly. The step "
                          "list is the valuable part. Send times that suit "
                          "you and I will make one of them work.")


def hook_config_covers(path, sample_tools):
    """Return whether a Claude Code or Codex hook config gates every sample."""
    with open(path, "r", encoding="utf-8") as fh:
        settings = json.load(fh)
    for entry in settings.get("hooks", {}).get("PreToolUse", []):
        matcher = entry.get("matcher", "")
        guard_present = any(
            "message_guard.py" in hook.get("command", "")
            for hook in entry.get("hooks", [])
        )
        if not guard_present:
            continue
        try:
            if matcher and all(re.search(matcher, tool) for tool in sample_tools):
                return True
        except re.error:
            return False
    return False


def run_doctor():
    ok = True

    def report(good, label, detail=""):
        nonlocal ok
        mark = "ok " if good else "FAIL"
        print("  %s %s%s" % (mark, label, (": " + detail) if detail else ""))
        if not good:
            ok = False

    print("synthesis-message-guard doctor (engine v%s)" % ENGINE_VERSION)
    print("  python: %s at %s" % (
        ".".join(map(str, sys.version_info[:3])), sys.executable))

    try:
        cfg, cblock, cwarn, gated, exempt = load_config()
        report(True, "config parses",
               "%d block + %d warn patterns, %d gated tool patterns"
               % (len(cblock), len(cwarn), len(gated)))
    except Exception as exc:
        report(False, "config", str(exc))
        print("UNHEALTHY: cannot continue without config.")
        return 2

    hits, _ = scan_text(POSITIVE_CONTROL_BAD, cblock, cwarn)
    report(len(hits) >= 2, "positive control (known-bad text trips scanner)",
           "%d hits" % len(hits))
    hits2, _ = scan_text(POSITIVE_CONTROL_CLEAN, cblock, cwarn)
    report(len(hits2) == 0, "negative control (clean text passes)",
           "%d hits" % len(hits2))

    sample_tools = [
        "mcp__abc123__slack_send_message",
        "mcp__abc123__slack_send_message_draft",
        "mcp__abc123__slack_schedule_message",
        "mcp__workspace-mcp__draft_gmail_message",
        "mcp__workspace-mcp__send_gmail_message",
        "mcp__d01c__create_draft",
        "mcp__d01c__update_draft",
        "mcp__apple-mail__send_email",
        "mcp__mail__send_message",
    ]
    missed = [t for t in sample_tools if not any(rx.search(t) for rx in gated)]
    report(not missed, "gated patterns cover the send/draft tool family",
           "missed: %s" % ", ".join(missed) if missed else "all covered")
    report(any(rx.search("mcp__ccd_session_mgmt__send_message") for rx in exempt),
           "inter-session messaging is exempted")

    client_configs = [
        (
            "Claude Code",
            "claude",
            "MESSAGE_GUARD_CLAUDE_SETTINGS",
            os.path.expanduser("~/.claude/settings.json"),
        ),
        (
            "Codex",
            "codex",
            "MESSAGE_GUARD_CODEX_HOOKS",
            os.path.expanduser("~/.codex/hooks.json"),
        ),
    ]
    active_clients = 0
    for label, executable, environment_key, default_path in client_configs:
        config_file = os.environ.get(environment_key, default_path)
        explicitly_configured = environment_key in os.environ
        active = (
            explicitly_configured
            or os.path.exists(config_file)
            or shutil.which(executable) is not None
        )
        if not active:
            print("  ok  %s hook wiring: client is not installed" % label)
            continue
        active_clients += 1
        try:
            wired = hook_config_covers(config_file, sample_tools)
            report(
                wired,
                "%s PreToolUse wiring covers the tool family" % label,
                config_file,
            )
        except Exception as exc:
            report(False, "%s hook config readable" % label, str(exc))
    report(active_clients > 0, "at least one supported agent client is active")

    try:
        os.makedirs(state_dir(), exist_ok=True)
        probe = os.path.join(state_dir(), ".doctor-probe")
        with open(probe, "w") as fh:
            fh.write("probe")
        os.remove(probe)
        report(True, "state dir writable", state_dir())
    except Exception as exc:
        report(False, "state dir writable", str(exc))

    print("HEALTHY: message guard fully operational." if ok
          else "UNHEALTHY: fix the failures above. The gate FAILS CLOSED, so "
               "sends will be blocked (not unprotected) until this is fixed.")
    return 0 if ok else 2


# --------------------------------------------------------------------------
# Test suite
# --------------------------------------------------------------------------

def run_tests():
    import subprocess

    me = os.path.abspath(__file__)
    tmp = tempfile.mkdtemp(prefix="msg-guard-test-")
    cfg_src = config_path()
    env = dict(os.environ)
    env["MESSAGE_GUARD_CONFIG"] = cfg_src
    env["MESSAGE_GUARD_STATE_DIR"] = tmp

    def invoke(payload, ledger=None):
        lp = os.path.join(tmp, "ledger.json")
        if os.path.exists(lp):
            os.remove(lp)
        if ledger is not None:
            with open(lp, "w") as fh:
                json.dump(ledger, fh)
        proc = subprocess.run(
            [sys.executable, me, "--gate"], input=json.dumps(payload),
            capture_output=True, text=True, env=env)
        return proc.returncode, proc.stderr

    def ledger_for(text, **over):
        base = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "message_sha256": sha256_text(text),
            "is_reply": True,
            "thread_fully_read": {"how": "gmail fetch", "source_ids": ["19fa..x"]},
            "history_searched": [{"query": "from:x subject:y", "where": "gmail",
                                  "results": "3 read"}],
            "claims": [{"claim": "payrun is Thursday",
                        "source": "gmail 19fa5b0fdcbf4839"}],
            "voice_rules_pass": True,
            "invented_precision_scan": True,
            "recipient_address_check": True,
        }
        base.update(over)
        return base

    slack_tool = "mcp__abc__slack_send_message_draft"
    clean = POSITIVE_CONTROL_CLEAN
    results = []

    def check(name, got, want):
        okay = got == want
        results.append((okay, name, got, want))
        print("  %s %s (exit %s, want %s)"
              % ("ok " if okay else "FAIL", name, got, want))

    print("synthesis-message-guard behavioral tests")

    rc, err = invoke({"tool_name": slack_tool, "tool_input": {"message": clean}})
    check("no ledger -> block", rc, 2)

    rc, _ = invoke({"tool_name": slack_tool, "tool_input": {"message": clean}},
                   ledger_for(clean))
    check("valid ledger + clean text -> allow", rc, 0)

    rc, err = invoke(
        {"tool_name": slack_tool,
         "tool_input": {"message": "Sorry I went quiet on you — " + clean}},
        ledger_for("Sorry I went quiet on you — " + clean))
    check("banned register -> block even with valid ledger", rc, 2)

    rc, _ = invoke({"tool_name": slack_tool, "tool_input": {"message": clean}},
                   ledger_for(clean + " EDITED AFTER GROUNDING"))
    check("sha mismatch -> block", rc, 2)

    stale = ledger_for(clean)
    stale["created_at"] = "2026-01-01T00:00:00+00:00"
    rc, _ = invoke({"tool_name": slack_tool, "tool_input": {"message": clean}}, stale)
    check("stale ledger -> block", rc, 2)

    noresearch = ledger_for(clean, history_searched=[])
    rc, _ = invoke({"tool_name": slack_tool, "tool_input": {"message": clean}},
                   noresearch)
    check("reply without history search -> block", rc, 2)

    rc, _ = invoke({"tool_name": "mcp__abc__slack_send_message",
                    "tool_input": {"message": clean}}, ledger_for(clean))
    check("direct slack send without branding check -> block", rc, 2)

    direct = ledger_for(clean, ragbot_branding_check=True)
    rc, _ = invoke({"tool_name": "mcp__abc__slack_send_message",
                    "tool_input": {"message": clean}}, direct)
    check("direct slack send with branding check -> allow", rc, 0)

    rc, _ = invoke({"tool_name": "mcp__ccd_session_mgmt__send_message",
                    "tool_input": {"message": "inter-session handoff"}})
    check("inter-session messaging exempt -> allow", rc, 0)

    rc, _ = invoke({"tool_name": slack_tool, "tool_input": {"weird_field": "x"}},
                   None)
    check("unknown input shape -> block", rc, 2)

    bad_env = dict(env)
    bad_env["MESSAGE_GUARD_CONFIG"] = os.path.join(tmp, "nonexistent.json")
    proc = subprocess.run(
        [sys.executable, me, "--gate"],
        input=json.dumps({"tool_name": slack_tool,
                          "tool_input": {"message": clean}}),
        capture_output=True, text=True, env=bad_env)
    check("missing config -> block (fail closed)", proc.returncode, 2)

    rc, _ = invoke({"tool_name": slack_tool, "tool_input": {"message": clean}},
                   ledger_for(clean, claims=[], no_factual_claims=False))
    check("no claims and no attestation -> block", rc, 2)

    failures = [r for r in results if not r[0]]
    print("%d/%d passed" % (len(results) - len(failures), len(results)))
    return 2 if failures else 0


# --------------------------------------------------------------------------
# Entry
# --------------------------------------------------------------------------

def main():
    args = sys.argv[1:]
    mode = args[0] if args else "--gate"
    if mode == "--gate":
        run_gate()
    elif mode == "--sha":
        print(sha256_text(sys.stdin.read()))
    elif mode == "--scan":
        try:
            _, cblock, cwarn, _, _ = load_config()
        except Exception as exc:
            print("config error: %s" % exc, file=sys.stderr)
            sys.exit(2)
        hits, warns = scan_text(sys.stdin.read(), cblock, cwarn)
        for n, s in hits:
            print("BLOCK [%s] %r" % (n, s))
        for n, s in warns:
            print("warn  [%s] %r" % (n, s))
        sys.exit(2 if hits else 0)
    elif mode == "--ledger-template":
        print(json.dumps({
            "created_at": datetime.now(timezone.utc).isoformat(),
            "message_sha256": "<pipe the EXACT final text to --sha>",
            "channel": "<slack|gmail|...>",
            "recipient": "<who>",
            "is_reply": True,
            "thread_fully_read": {"how": "<tool used>", "source_ids": []},
            "history_searched": [{"query": "", "where": "", "results": ""}],
            "claims": [{"claim": "", "source": ""}],
            "no_factual_claims": False,
            "voice_rules_pass": False,
            "invented_precision_scan": False,
            "recipient_address_check": False,
            "ragbot_branding_check": False,
        }, indent=2))
    elif mode == "--doctor":
        sys.exit(run_doctor())
    elif mode == "--test":
        sys.exit(run_tests())
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main()

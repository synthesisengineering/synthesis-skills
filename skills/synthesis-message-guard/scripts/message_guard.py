#!/usr/bin/env python3
"""synthesis-message-guard — fail-closed pre-send gate for agent-drafted correspondence.

v1.1.0 (2026-07-29)

A PreToolUse hook engine that blocks message-sending and draft-creating tool
calls unless (a) the outgoing text passes a deterministic register scan against
a configured pattern set, and (b) a fresh, single-use grounding ledger — stored
at ledger/<message-sha>.json so concurrent seats cannot clobber one another —
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
  --write-ledger    read a ledger JSON on stdin and file it at the path its own
                    message_sha256 dictates, atomically. THE way to stage a
                    ledger: the agent never types a path, so it cannot misfile.
  --ledger-path     read message text on stdin, print where its ledger belongs.
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

ENGINE_VERSION = "1.6.0"


def config_path():
    return os.environ.get(
        "MESSAGE_GUARD_CONFIG",
        os.path.expanduser("~/.synthesis/message-guard/patterns.json"),
    )


def state_dir():
    return os.environ.get(
        "MESSAGE_GUARD_STATE_DIR", os.path.expanduser("~/.synthesis/message-guard")
    )


LEDGER_ORPHAN_SWEEP_MULTIPLE = 4     # sweep ledgers this many times past max age


def ledger_dir():
    return os.path.join(state_dir(), "ledger")


def legacy_ledger_detail(path):
    """Who a leftover single-slot ledger belongs to, so the seat that wrote it
    can recognise it. 2026-09-02: one seat's helper script, written against
    the previous layout, kept the machine-wide doctor red for every seat, and
    nobody could tell whose file it was without recognising the sha."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return "unreadable"
    if not isinstance(data, dict):
        return "not a ledger object"
    parts = []
    for key in ("created_at", "channel", "recipient"):
        if data.get(key):
            parts.append("%s %s" % (key, str(data[key])[:80]))
    return ", ".join(parts) or "no created_at/channel/recipient fields"


def ledger_path_for(sha):
    """One ledger per message, named by the sha it is already bound to.

    The predecessor used a single `ledger.json`. Two seats composing at once
    clobbered each other: the first seat's send then failed the sha check and
    was told it had "edited the text after grounding" — false, and pointing at
    the wrong repair — while the second seat sailed through on a ledger the
    first had never seen. Keying by sha removes the collision with no new
    concept: the ledger was always bound to this exact text.
    """
    return os.path.join(ledger_dir(), "%s.json" % sha)


def tighten_ledger_store():
    """Keep the ledger directory private, on every write rather than at
    creation only — the directory outlives the umask that made it."""
    changed = []
    try:
        d = ledger_dir()
        if os.stat(d).st_mode & 0o777 != 0o700:
            os.chmod(d, 0o700)
            changed.append(d)
        for name in os.listdir(d):
            fp = os.path.join(d, name)
            if os.path.isfile(fp) and os.stat(fp).st_mode & 0o777 != 0o600:
                os.chmod(fp, 0o600)
                changed.append(fp)
    except OSError:
        pass
    return changed


def sweep_orphan_ledgers(cfg):
    """Delete ledgers far past max age. Returns the count removed.

    A ledger is single-use and short-lived; one left behind means a compose that
    never sent. Stale ones are harmless — the sha gate makes a ledger unusable
    for any other message — but they accumulate, and an unbounded directory of
    grounding records is its own small liability.
    """
    try:
        max_age = float(cfg.get("ledger_max_age_minutes", 120))
    except (TypeError, ValueError):
        return 0
    cutoff = time.time() - (max_age * 60 * LEDGER_ORPHAN_SWEEP_MULTIPLE)
    removed = 0
    try:
        names = os.listdir(ledger_dir())
    except OSError:
        return 0
    for name in names:
        if not name.endswith(".json"):
            continue
        fp = os.path.join(ledger_dir(), name)
        try:
            if os.path.getmtime(fp) < cutoff:
                os.remove(fp)
                removed += 1
        except OSError:
            continue
    return removed


def log_path():
    return os.path.join(state_dir(), "log.jsonl")


# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

REQUIRED_CONFIG_KEYS = ("gated_tool_patterns", "exempt_tool_patterns",
                        "block_patterns", "warn_patterns",
                        "ledger_max_age_minutes", "text_field_candidates")


DEFAULT_CURRENCY_PATTERN = (
    r"\b(unanswered|unsent|not (yet )?(replied|responded|answered|sent)|"
    r"no (reply|response|answer)( yet)?|still (open|waiting|pending|unanswered)|"
    r"has(n't| not) (replied|responded|answered|sent))\b"
)


def currency_config(cfg):
    """The read-freshness lane, or None when the config has not adopted it.

    A claim like "still unanswered" is a statement about NOW that rests on a
    read taken at some moment; the ledger recorded the source but not when
    it was read, so a claim resting on an eight-hour-old read passed as
    verified on 2026-09-01 while the answer had gone out that morning.
    Adopt with `currency_claim_patterns` (regexes that mark a claim as a
    currency claim) and `currency_claim_max_age_minutes`."""
    patterns = cfg.get("currency_claim_patterns")
    if not isinstance(patterns, list) or not patterns:
        return None
    return {
        "patterns": [re.compile(p, re.IGNORECASE) for p in patterns],
        "max_age": float(cfg.get("currency_claim_max_age_minutes", 30)),
    }


def minutes_since(value):
    """Minutes elapsed since an ISO-8601 moment, or None when unparseable."""
    try:
        ts = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - ts).total_seconds() / 60.0


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


LINKED_CONSTRUCT_RX = None  # compiled lazily; strips forms that RENDER as links


def _strip_linked_constructs(text):
    """Remove every construct in which a URL legitimately rides: HTML href
    attributes, Slack <url|label> / <url> mrkdwn, and markdown (url)
    notation. What remains is VISIBLE text; a persona domain surviving the
    strip is the visible-URL fallback form."""
    import re as _re
    global LINKED_CONSTRUCT_RX
    if LINKED_CONSTRUCT_RX is None:
        LINKED_CONSTRUCT_RX = _re.compile(
            r'href\s*=\s*"[^"]*"'
            r"|href\s*=\s*'[^']*'"
            r"|<https?://[^>|\s]*(?:\|[^>]*)?>"
            r"|\]\(https?://[^)]*\)"
        )
    return LINKED_CONSTRUCT_RX.sub(" ", text)


def signature_wire_failures(tool_name, tool_input, text, cfg):
    """Enforce the signature link-form rules (2026-08-30 incident: a
    persona-signed email to executives went out body_format plain, so the
    signature rendered as a bare visible URL and dropped its method link —
    one day after the doctrine naming the exact tool and parameter shipped.
    Correct doctrine did not bind because nothing read it; this does).

    Configured via the OPTIONAL patterns.json key signature_link_enforcement:
      { "markers": ["\\U0001F9DE", "\\U0001F916"],
        "domains": ["ragenie.ai", "ragbot.ai"],
        "html_body_format_tools": "send_gmail_message|draft_gmail_message",
        "linkless_fallback_tools": "regex-of-tools-with-no-link-support" }
    Checks run only when an outgoing message carries a persona marker, so
    unsigned traffic is never taxed. Absent key = checks off (adopt
    deliberately)."""
    enforcement = cfg.get("signature_link_enforcement")
    if not enforcement:
        return []
    markers = enforcement.get("markers", [])
    if not any(m in text for m in markers):
        return []
    failures = []
    import re as _re
    html_tools = enforcement.get("html_body_format_tools")
    if html_tools and _re.search(html_tools, tool_name):
        if tool_input.get("body_format", "plain") != "html":
            failures.append(
                "persona-signed email MUST use body_format html — the "
                "raw-MIME HTML path is the only permitted email form "
                "(comms doctrine v4.3.1); the plain default renders the "
                "signature as a bare URL")
        if _re.search(r"\]\(https?://", text):
            failures.append(
                "markdown link notation never renders in email bodies; "
                "convert to HTML anchors before staging")
    fallback_tools = enforcement.get("linkless_fallback_tools")
    if fallback_tools and _re.search(fallback_tools, tool_name):
        return failures  # visible-URL form is the legitimate form here
    stripped = _strip_linked_constructs(text)
    exposed = [d for d in enforcement.get("domains", []) if d in stripped]
    if exposed:
        failures.append(
            "persona signature uses the visible-URL fallback (%s appears "
            "as text, not inside a link) on a link-capable channel — the "
            "persona name must BE the hyperlink" % ", ".join(exposed))
    return failures


def check_header_hygiene(tool_input):
    """Return a list of failures in RFC threading headers; empty list = clean.

    An RFC Message-ID is passed with literal angle brackets: <abc@host>. A
    caller that HTML-escapes it writes `&lt;abc@host&gt;` straight into the
    In-Reply-To and References headers, where it matches no message. Gmail
    hides the damage whenever thread_id is also supplied — its own threading
    wins — so the error survives review and recurs. Twice on this machine
    (2026-08-20, 2026-08-28) before this check existed.
    """
    fails = []
    for key in ("in_reply_to", "references", "inReplyTo", "in_reply_to_id"):
        val = tool_input.get(key)
        if not isinstance(val, str) or not val.strip():
            continue
        if "&lt;" in val or "&gt;" in val or "&amp;" in val:
            fails.append(
                "%s contains HTML entities (%r). RFC Message-IDs take LITERAL "
                "angle brackets: <id@host>, never &lt;id@host&gt;. Pass the raw "
                "value." % (key, val[:80])
            )
        elif val.strip().startswith("<") and not val.strip().endswith(">"):
            fails.append(
                "%s is missing its closing angle bracket (%r)." % (key, val[:80])
            )
    return fails


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
    currency = currency_config(cfg)
    if ledger.get("no_factual_claims") is True:
        pass
    elif isinstance(claims, list) and claims:
        for i, c in enumerate(claims):
            if not (isinstance(c, dict) and c.get("claim") and c.get("source")):
                fails.append("claims[%d] must have non-empty claim and source" % i)
                continue
            if currency and any(rx.search(str(c["claim"])) for rx in currency["patterns"]):
                age = minutes_since(c.get("read_at"))
                snippet = str(c["claim"])[:60]
                if age is None:
                    fails.append(
                        "claims[%d] asserts a currency state (%r) but has no read_at — "
                        "re-read the source THIS RUN and record when (ISO-8601). A read "
                        "from earlier today is a statement about the past." % (i, snippet))
                elif age > currency["max_age"]:
                    fails.append(
                        "claims[%d] rests on a read %.0f min old (max %.0f for currency "
                        "claims: %r) — re-read the source and refresh read_at."
                        % (i, age, currency["max_age"], snippet))
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
# Peer-session sends (config-adopted, 2026-09-01)
# --------------------------------------------------------------------------
#
# Correspondence tools carry Rajiv-register text to humans and take the full
# ledger lane below. Peer-session tools carry agent-to-agent traffic; their
# failure mode is not register drift but MISDELIVERY — a target chosen by
# guessing a chat title or display label. The mechanical fix: the target
# session id must be registered as an ACTIVE client ref on the coordination
# board (schema v4), which only happens when that session claimed its seat.
# The lesson this makes mechanical: the board id is the identity; the client
# label is a display string.

def _board_has_active_ref(content, ref):
    """Self-contained active-row scan; no cross-skill import at hook time."""
    terminal = {"released", "complete", "completed", "closed"}
    in_table = False
    for line in content.splitlines():
        if line.strip() == "## Active sessions":
            in_table = True
            continue
        if in_table and line.startswith("## "):
            break
        if not in_table or not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.split("|")[1:-1]]
        if not cells or cells[0] in {"id", "session uuid"}:
            continue
        if set(cells[0]) <= {"-"}:
            continue
        if ref in cells and cells[-1].lower() not in terminal:
            return True
    return False


def peer_send_resolution_failures(tool_name, tool_input, cfg):
    """Return (handled, failures) for the peer-session send lane.

    handled is True when the tool matches the configured peer pattern; the
    peer lane then replaces the correspondence lane for this call. Absent
    config means not handled — adoption is deliberate, per instance.
    """
    peer = cfg.get("peer_send_resolution")
    if not isinstance(peer, dict):
        return False, []
    pattern = peer.get("tool_pattern")
    if not pattern or not re.search(pattern, tool_name):
        return False, []
    field = peer.get("target_field", "session_id")
    target = tool_input.get(field)
    if not isinstance(target, str) or not target.strip():
        return True, [
            "peer send carries no %r target; unknown shape fails closed" % field
        ]
    target = target.strip()
    board = os.path.expanduser(
        peer.get("board", "~/.synthesis/coordination/active-sessions.md")
    )
    try:
        with open(board, "r", encoding="utf-8") as fh:
            content = fh.read()
    except OSError as exc:
        return True, [
            "coordination board unreadable (%s) so the target cannot be "
            "verified: %s" % (board, exc)
        ]
    if _board_has_active_ref(content, "ccd:" + target) or _board_has_active_ref(
        content, target
    ):
        return True, []
    return True, [
        "target session id %r is not a registered active client ref on the "
        "coordination board (%s). Run coordination.py resolve "
        "--to <project-or-session> and address the exact ref it returns; if "
        "the peer has not claimed a seat, deliver via the board message bus "
        "and let it self-select — never guess a chat session by title or "
        "broadcast" % (target, board)
    ]


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

        # Peer-session lane runs BEFORE the exempt list: while unadopted,
        # instances may exempt inter-session tools; once adopted, the peer
        # pattern owns those tools and the exemption no longer bypasses it.
        peer_handled, peer_fails = peer_send_resolution_failures(
            tool_name, tool_input, cfg
        )
        if peer_handled:
            if peer_fails:
                block("peer-session resolution — " + " | ".join(peer_fails))
            os.makedirs(state_dir(), exist_ok=True)
            with open(log_path(), "a", encoding="utf-8") as fh:
                fh.write(json.dumps({
                    "at": datetime.now(timezone.utc).isoformat(),
                    "kind": "peer-send",
                    "tool": tool_name,
                    "engine": ENGINE_VERSION,
                }) + "\n")
            sys.exit(0)

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

        wire_fails = signature_wire_failures(tool_name, tool_input, text, cfg)
        if wire_fails:
            block("signature wire-form violation — " + " | ".join(wire_fails)
                  + ". Load the comms skill and use its exact per-platform "
                  "wire forms; the visible-URL form is only for channels "
                  "that cannot render links.")

        header_fails = check_header_hygiene(tool_input)
        if header_fails:
            block("threading headers malformed — " + " | ".join(header_fails))

        sweep_orphan_ledgers(cfg)
        text_sha = sha256_text(text)
        lp = ledger_path_for(text_sha)
        if not os.path.exists(lp):
            block("no grounding ledger for this exact message at %s. Before "
                  "composing you must: "
                  "(1) read the FULL thread including quoted history, "
                  "(2) search prior correspondence for this recipient/topic "
                  "across all mailboxes and local transcripts, "
                  "(3) map every factual claim to a source, "
                  "(4) run the voice pass. Then file the ledger with "
                  "--write-ledger (it computes this path from the ledger's own "
                  "message_sha256, so it cannot be misfiled); --ledger-template "
                  "gives the skeleton and --sha the hash. One ledger per "
                  "message, named by that message's sha, consumed on use. "
                  "A ledger written for DIFFERENT text lives at a different "
                  "path and is never silently substituted for this one."
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
            "sha256": text_sha,
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
# The clean control is a CANONICAL SIGNED agent message, not generic prose
# (board ask, 2026-08-03): a generic control passed while a retired-branding
# pattern compiled under IGNORECASE blocked every real signed send. The
# doctor's negative control must look like the traffic the guard exists to
# let through — a Slack-wire-form signature line included.
POSITIVE_CONTROL_CLEAN = ("Thank you for writing this up properly. The step "
                          "list is the valuable part. Send times that suit "
                          "you and I will make one of them work.\n\n"
                          "🤖 _I'm the principal's <https://ragbot.ai/|Ragbot>, "
                          "sent under standing direction — every reply is read_")


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

    # Dead-pattern control (2026-08-07 defect): a pattern authored with
    # surrogate-escape sequences (a "\\ud83e\\uddde"-style pair in place of
    # the real emoji character) compiles to lone surrogates that can never
    # match decoded text, so the rule it encodes is silently OFF while the
    # doctor stays green.
    dead = [name for name, rx in (cblock + cwarn)
            if any("\ud800" <= ch <= "\udfff" for ch in rx.pattern)]
    report(not dead, "no dead surrogate-escape patterns",
           ("%d pattern(s) can never match decoded text" % len(dead))
           if dead else "all patterns use real characters")

    # Config-supplied clean controls (2026-08-03 defect): the built-in
    # clean control passed while every REAL legitimate message was being
    # blocked, because it did not resemble the user's canonical traffic.
    # patterns.json may carry doctor_clean_controls: known-legitimate
    # messages that must pass the scanner exactly as sent.
    clean_controls = cfg.get("doctor_clean_controls", [])
    if clean_controls:
        failing = []
        for sample in clean_controls:
            sample_hits, _ = scan_text(str(sample), cblock, cwarn)
            if sample_hits:
                failing.append(str(sample)[:60])
        report(not failing, "config clean controls (canonical real "
               "messages pass)",
               "; ".join(failing) if failing
               else "%d control(s) pass" % len(clean_controls))
    else:
        report(True, "config clean controls",
               "none configured — add doctor_clean_controls with your "
               "canonical legitimate messages so a pattern change that "
               "blocks real traffic fails the doctor")

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
    peer_sample = "mcp__ccd_session_mgmt__send_message"
    peer_cfg = cfg.get("peer_send_resolution")
    if isinstance(peer_cfg, dict):
        try:
            peer_rx = re.compile(peer_cfg.get("tool_pattern") or "")
            report(bool(peer_cfg.get("tool_pattern"))
                   and bool(peer_rx.search(peer_sample)),
                   "peer-session pattern covers inter-session sends",
                   peer_cfg.get("tool_pattern", ""))
        except re.error as exc:
            report(False, "peer-session tool pattern compiles", str(exc))
        peer_board = os.path.expanduser(peer_cfg.get(
            "board", "~/.synthesis/coordination/active-sessions.md"))
        report(os.path.isfile(peer_board),
               "coordination board readable for peer resolution", peer_board)
    else:
        report(any(rx.search(peer_sample) for rx in exempt),
               "inter-session messaging is exempted (peer_send_resolution "
               "not adopted; adopt it to gate peer sends on board "
               "registration)")

    # --- ledger store ---
    # The ledger directory is the concurrency fix's load-bearing surface, so
    # the doctor must be able to see it, not assume it.
    legacy = os.path.join(state_dir(), "ledger.json")
    report(not os.path.exists(legacy),
           "no legacy single-slot ledger.json",
           ("found %s (%s) — a leftover from the pre-sha layout, usually a "
            "helper script that outlived the convention. It is inert (the gate "
            "reads ledger/<sha>.json); whoever it belongs to should delete it."
            % (legacy, legacy_ledger_detail(legacy)))
           if os.path.exists(legacy) else "sha-keyed store only")

    d = ledger_dir()
    if os.path.isdir(d):
        names = [n for n in os.listdir(d) if n.endswith(".json")]
        misnamed = [n for n in names if len(n) != 69 or not all(
            c in "0123456789abcdef" for c in n[:-5].lower())]
        report(not misnamed,
               "every ledger filename is a sha256 digest",
               "misnamed: %s — these can never match a send and are dead "
               "weight; --write-ledger cannot produce them, so they were "
               "hand-placed" % ", ".join(sorted(misnamed)[:5])
               if misnamed else "%d ledger(s) present" % len(names))
        try:
            max_age = float(cfg.get("ledger_max_age_minutes", 120))
        except (TypeError, ValueError):
            max_age = 120.0
        cutoff = time.time() - (max_age * 60)
        stale = []
        for n in names:
            try:
                if os.path.getmtime(os.path.join(d, n)) < cutoff:
                    stale.append(n)
            except OSError:
                continue
        # Stale ledgers are unusable, not unsafe — the sha binds each to one
        # exact text. Report rather than alarm; the gate sweeps them.
        report(True, "ledger store age",
               "%d of %d past max age (%s min); swept automatically at %dx"
               % (len(stale), len(names), max_age, LEDGER_ORPHAN_SWEEP_MULTIPLE)
               if names else "empty (the normal resting state)")
    else:
        report(True, "ledger store", "not yet created (normal before first use)")
    if os.path.isdir(ledger_dir()):
        dmode = os.stat(ledger_dir()).st_mode & 0o777
        loose = [n for n in os.listdir(ledger_dir())
                 if os.path.isfile(os.path.join(ledger_dir(), n))
                 and os.stat(os.path.join(ledger_dir(), n)).st_mode & 0o777 != 0o600]
        report(dmode == 0o700 and not loose, "ledger store is private",
               "dir %o, %d file(s) not 600 — a ledger carries the full "
               "outgoing text and its sources (the next --write-ledger "
               "repairs this)" % (dmode, len(loose))
               if (dmode != 0o700 or loose) else "700/600")

    currency_cfg = currency_config(cfg)
    if currency_cfg:
        stale_probe = any(rx.search("still unanswered by the recipient")
                          for rx in currency_cfg["patterns"])
        report(stale_probe, "currency-claim freshness lane adopted (unanswered/unsent "
               "claims must carry a fresh read_at)",
               "max age %.0f min" % currency_cfg["max_age"])
    else:
        report(True, "currency-claim freshness lane not adopted (adopt "
               "currency_claim_patterns + currency_claim_max_age_minutes to gate "
               "unanswered/unsent claims on read freshness)", "informational")

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
            if isinstance(peer_cfg, dict) and label == "Claude Code":
                report(
                    hook_config_covers(config_file, [peer_sample]),
                    "%s PreToolUse wiring routes peer-session sends" % label,
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
    if not os.path.exists(cfg_src):
        # The suite proves the ENGINE, not one machine's private patterns.
        # 2026-09-02: main sat red for hours while every developer machine
        # was green, because CI has no ~/.synthesis and the harness reached
        # for it. Fall back to the skill's example config and say so.
        example = os.path.join(os.path.dirname(me), "..", "patterns.example.json")
        if os.path.exists(example):
            print("config: %s is absent; running against patterns.example.json" % cfg_src)
            cfg_src = os.path.abspath(example)
    env = dict(os.environ)
    env["MESSAGE_GUARD_CONFIG"] = cfg_src
    env["MESSAGE_GUARD_STATE_DIR"] = tmp

    def invoke(payload, ledger=None, keep=False):
        # File the ledger where its own sha says it belongs, exactly as
        # --write-ledger does in production. Staging it anywhere else would
        # test a path the gate no longer reads.
        sha = (ledger or {}).get("message_sha256") or "0" * 64
        os.makedirs(os.path.join(tmp, "ledger"), exist_ok=True)
        lp = os.path.join(tmp, "ledger", "%s.json" % sha)
        d = os.path.join(tmp, "ledger")
        if os.path.isdir(d) and not keep:
            for stale_name in os.listdir(d):
                try:
                    os.remove(os.path.join(d, stale_name))
                except OSError:
                    pass
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

    # --- peer-session send lane ---
    # This asserted a bare exemption until peer_send_resolution was adopted;
    # that lane now OWNS the tool and demands a target that resolves on the
    # coordination board. The old assertion outlived the design it described,
    # and it read the LIVE board, so its result moved with unrelated work.
    # Both faults are fixed here: a board fixture, and the adopted contract.
    board = os.path.join(tmp, "active-sessions.md")
    live_ref = "ccd:local_1111aaaa-0000-4000-8000-000000000001"
    with open(board, "w", encoding="utf-8") as fh:
        fh.write("## Active sessions\n\n"
                 "| id | ref | project | status |\n"
                 "| --- | --- | --- | --- |\n"
                 "| 01 | %s | peer-a | owner |\n"
                 "| 02 | ccd:local_1111aaaa-0000-4000-8000-000000000002 | "
                 "peer-b | released |\n" % live_ref)
    peer_cfg_path = os.path.join(tmp, "patterns-peer.json")
    with open(cfg_src, "r", encoding="utf-8") as fh:
        peer_cfg = json.load(fh)
    peer_cfg.setdefault("peer_send_resolution", {
        "tool_pattern": "mcp__ccd_session_mgmt__send_message$",
        "target_field": "session_id",
    })["board"] = board
    with open(peer_cfg_path, "w", encoding="utf-8") as fh:
        json.dump(peer_cfg, fh)

    def peer_invoke(tool_input, cfg_file=peer_cfg_path):
        penv = dict(env)
        penv["MESSAGE_GUARD_CONFIG"] = cfg_file
        proc = subprocess.run(
            [sys.executable, me, "--gate"],
            input=json.dumps({"tool_name": "mcp__ccd_session_mgmt__send_message",
                              "tool_input": tool_input}),
            capture_output=True, text=True, env=penv)
        return proc.returncode, proc.stderr

    rc, _ = peer_invoke({"message": "handoff", "session_id": live_ref})
    check("peer send to a board-active ref -> allow", rc, 0)

    rc, err = peer_invoke({"message": "handoff"})
    check("peer send with no target -> block", rc, 2)
    check("...and names the missing field, not a generic failure",
          int("session_id" in err), 1)

    rc, _ = peer_invoke({"message": "handoff",
                         "session_id": "local_dead-beef-not-on-the-board"})
    check("peer send to an unregistered ref -> block", rc, 2)

    rc, _ = peer_invoke({"message": "handoff",
                         "session_id": "ccd:local_1111aaaa-0000-4000-8000-"
                                       "000000000002"})
    check("peer send to a RELEASED seat -> block", rc, 2)

    missing_board = dict(peer_cfg)
    missing_board["peer_send_resolution"] = dict(
        peer_cfg["peer_send_resolution"], board=os.path.join(tmp, "gone.md"))
    nb_path = os.path.join(tmp, "patterns-noboard.json")
    with open(nb_path, "w", encoding="utf-8") as fh:
        json.dump(missing_board, fh)
    rc, _ = peer_invoke({"message": "handoff", "session_id": live_ref}, nb_path)
    check("unreadable board -> block (fail closed)", rc, 2)

    # Without the peer block configured, the plain exemption still applies.
    unadopted = {k: v for k, v in peer_cfg.items() if k != "peer_send_resolution"}
    ua_path = os.path.join(tmp, "patterns-unadopted.json")
    with open(ua_path, "w", encoding="utf-8") as fh:
        json.dump(unadopted, fh)
    rc, _ = peer_invoke({"message": "handoff"}, ua_path)
    check("peer lane unadopted -> exemption still allows", rc, 0)

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

    # --- concurrent seats (the reason the ledger is keyed by sha) ---
    # Two seats compose different messages at the same moment. Under the old
    # single ledger.json the second write clobbered the first, and the first
    # seat's send then failed the sha check with "edited after grounding" — a
    # false diagnosis pointing at the wrong repair.
    other = clean + " Second seat's entirely separate message."
    os.makedirs(os.path.join(tmp, "ledger"), exist_ok=True)
    for led in (ledger_for(clean), ledger_for(other)):
        with open(os.path.join(tmp, "ledger",
                               led["message_sha256"] + ".json"), "w") as fh:
            json.dump(led, fh)
    rc, _ = invoke({"tool_name": slack_tool,
                    "tool_input": {"message": clean}}, keep=True)
    check("two seats' ledgers coexist -> first seat's message allowed", rc, 0)
    rc, _ = invoke({"tool_name": slack_tool,
                    "tool_input": {"message": other}}, keep=True)
    check("two seats' ledgers coexist -> second seat's message allowed", rc, 0)

    # A ledger written for OTHER text must never authorise this send. Under one
    # fixed path this surfaced as a sha mismatch; now the path simply has no
    # ledger, which is the honest diagnosis.
    rc, err = invoke({"tool_name": slack_tool,
                      "tool_input": {"message": clean}}, ledger_for(other))
    check("another message's ledger does not authorise this one -> block", rc, 2)
    check("...and the block says no ledger, not sha mismatch",
          int("no grounding ledger for this exact message" in err), 1)

    # Consuming one seat's ledger must not consume the other's.
    for led in (ledger_for(clean), ledger_for(other)):
        with open(os.path.join(tmp, "ledger",
                               led["message_sha256"] + ".json"), "w") as fh:
            json.dump(led, fh)
    invoke({"tool_name": slack_tool, "tool_input": {"message": clean}}, keep=True)
    rc, _ = invoke({"tool_name": slack_tool,
                    "tool_input": {"message": other}}, keep=True)
    check("consuming one seat's ledger leaves the other's intact", rc, 0)
    rc, _ = invoke({"tool_name": slack_tool,
                    "tool_input": {"message": clean}}, keep=True)
    check("a consumed ledger is still single-use -> block on reuse", rc, 2)

    # Real threads, not just distinct paths. The first half is a positive
    # control: it reproduces the original defect against a single fixed slot,
    # so a pass below is evidence of a fix rather than of an easy test.
    from concurrent.futures import ThreadPoolExecutor
    seats = 8
    texts = ["%s Seat %d's own distinct message." % (clean, i) for i in range(seats)]
    fixed = os.path.join(tmp, "old-layout.json")

    def old_write(text):
        with open(fixed, "w") as fh:
            json.dump(ledger_for(text), fh)

    with ThreadPoolExecutor(max_workers=seats) as ex:
        list(ex.map(old_write, texts))
    with open(fixed) as fh:
        survivor = json.load(fh)["message_sha256"]
    check("positive control: one fixed slot loses all but one seat",
          sum(1 for x in texts if sha256_text(x) == survivor), 1)

    def stage(text):
        proc = subprocess.run([sys.executable, me, "--write-ledger"],
                              input=json.dumps(ledger_for(text)),
                              capture_output=True, text=True, env=env)
        return proc.returncode

    with ThreadPoolExecutor(max_workers=seats) as ex:
        codes = list(ex.map(stage, texts))
    check("N seats stage ledgers concurrently -> all succeed",
          sum(1 for c in codes if c == 0), seats)
    check("N seats stage ledgers concurrently -> N distinct files",
          len([n for n in os.listdir(os.path.join(tmp, "ledger"))
               if n.endswith(".json")]), seats)

    def fire(text):
        proc = subprocess.run(
            [sys.executable, me, "--gate"], env=env, text=True,
            capture_output=True,
            input=json.dumps({"tool_name": slack_tool,
                              "tool_input": {"message": text}}))
        return proc.returncode

    with ThreadPoolExecutor(max_workers=seats) as ex:
        fired = list(ex.map(fire, texts))
    check("N seats send concurrently -> all allowed",
          sum(1 for c in fired if c == 0), seats)
    with ThreadPoolExecutor(max_workers=seats) as ex:
        again = list(ex.map(fire, texts))
    check("N seats replay concurrently -> none allowed (single-use holds)",
          sum(1 for c in again if c == 0), 0)

    # --write-ledger files by the ledger's own sha, so it cannot be misfiled.
    proc = subprocess.run([sys.executable, me, "--write-ledger"],
                          input=json.dumps(ledger_for(clean)),
                          capture_output=True, text=True, env=env)
    wrote = proc.stdout.strip()
    check("--write-ledger files at the sha path",
          int(wrote.endswith(sha256_text(clean) + ".json")
              and os.path.exists(wrote)), 1)

    # A ledger whose sha is not a real digest is refused, never filed.
    proc = subprocess.run(
        [sys.executable, me, "--write-ledger"],
        input=json.dumps(ledger_for(clean, message_sha256="nope")),
        capture_output=True, text=True, env=env)
    check("--write-ledger refuses a non-digest sha", proc.returncode, 2)

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
            "claims": [{"claim": "", "source": "", "read_at": "<ISO-8601 moment the source was read this run; required for unanswered/unsent/still-open claims>"}],
            "no_factual_claims": False,
            "voice_rules_pass": False,
            "invented_precision_scan": False,
            "recipient_address_check": False,
            "ragbot_branding_check": False,
        }, indent=2))
    elif mode == "--write-ledger":
        # Read a ledger JSON on stdin and file it where its own message_sha256
        # says it belongs. The composing agent never types the path, so it
        # cannot misfile one — and a ledger whose sha it did not compute from
        # the final text simply will not match at the gate.
        try:
            ledger = json.loads(sys.stdin.read())
        except Exception as exc:
            print("write-ledger: stdin is not valid JSON (%s)" % exc, file=sys.stderr)
            sys.exit(2)
        sha = ledger.get("message_sha256")
        if not isinstance(sha, str) or len(sha) != 64 or not all(
                c in "0123456789abcdef" for c in sha.lower()):
            print("write-ledger: message_sha256 must be a 64-char hex digest of "
                  "the EXACT final text (pipe it to --sha). Got: %r" % (sha,),
                  file=sys.stderr)
            sys.exit(2)
        os.makedirs(ledger_dir(), mode=0o700, exist_ok=True)
        tighten_ledger_store()
        dest = ledger_path_for(sha.lower())
        tmp = dest + ".tmp"
        # 0600 from creation: a ledger carries the full outgoing text and its
        # sources, and a mode set after the write leaves a readable window.
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(ledger, fh, indent=2)
        os.replace(tmp, dest)          # atomic; never a half-written ledger
        print(dest)
    elif mode == "--ledger-path":
        # Print where THIS text's ledger must live. Read-only.
        print(ledger_path_for(sha256_text(sys.stdin.read())))
    elif mode == "--doctor":
        sys.exit(run_doctor())
    elif mode == "--test":
        sys.exit(run_tests())
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main()

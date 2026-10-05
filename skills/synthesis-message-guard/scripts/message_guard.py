#!/usr/bin/env python3
"""synthesis-message-guard — fail-closed pre-send gate for agent-drafted correspondence.

v1.1.0 (2026-07-29)

A PreToolUse hook engine that blocks message-sending and draft-creating tool
calls unless (a) the outgoing text passes a deterministic register scan against
a configured pattern set, and (b) a fresh, single-use grounding ledger — stored
at ledger/<message-sha>.json so concurrent seats cannot clobber one another —
that is cryptographically bound (sha256) to the complete tool input and attests
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
  --message-sha     hash complete tool_name/tool_input JSON for a ledger.
  --sha             raw-text utility only; never use for a send ledger.
  --dispatch        route every enrolled tool by its owner-reviewed capability.
  --capability-plan / --capability-enroll / --capability-readiness
                    inspect a supplied native catalog, bind reviewed decisions,
                    and diagnose drift. These modes do not activate hooks.
  --build-email / --build-mime / --verify-readback / --monitor-email
                    local construction and supplied evidence checks; no sends.
  --scan            read message text on stdin, print scan findings, exit 2 if
                    any block-tier hit. Lets an agent pre-check wording.
  --ledger-template print a skeleton ledger JSON.
  --write-ledger    read a ledger JSON on stdin and file it at the path its own
                    message_sha256 dictates, atomically. THE way to stage a
                    ledger: the agent never types a path, so it cannot misfile.
  --message-ledger-path  complete tool-call JSON to exact ledger path.
  --ledger-path     raw-text utility only; not the send ledger path.
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
import shlex
import shutil
import stat
from pathlib import Path
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


LEDGER_ORPHAN_SWEEP_MULTIPLE = 4  # sweep ledgers this many times past max age


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

REQUIRED_CONFIG_KEYS = (
    "gated_tool_patterns",
    "exempt_tool_patterns",
    "block_patterns",
    "warn_patterns",
    "ledger_max_age_minutes",
    "text_field_candidates",
)


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
    capability_file = os.environ.get("MESSAGE_GUARD_CAPABILITIES")
    if capability_file:
        with open(capability_file, encoding="utf-8") as stream:
            registry = json.load(stream)
        validate_capability_registry(registry)
        cfg["message_capabilities"] = registry["capabilities"]
        cfg["_capability_registry"] = registry
    return validate_config(cfg)


def validate_config(cfg):
    """Validate owner data without consulting environment or installed state."""
    if not isinstance(cfg, dict):
        raise ValueError("message policy must be an object")
    for key in REQUIRED_CONFIG_KEYS:
        if key not in cfg:
            raise ValueError("config missing required key: %s" % key)
    # Compile every regex now: an uncompilable pattern must fail loudly here,
    # never silently skip (a skipped pattern is an invisible hole in the guard).
    compiled_block = [
        (p["name"], re.compile(p["regex"], re.IGNORECASE))
        for p in cfg["block_patterns"]
    ]
    compiled_warn = [
        (p["name"], re.compile(p["regex"], re.IGNORECASE)) for p in cfg["warn_patterns"]
    ]
    gated = [re.compile(p) for p in cfg["gated_tool_patterns"]]
    exempt = [re.compile(p) for p in cfg["exempt_tool_patterns"]]
    email_policy(cfg)
    paragraph_policy(cfg)
    # Validate every declaration even if no current call selects it.
    try:
        capability_for("__validation_probe__", cfg)
    except ValueError as exc:
        if "exactly one" not in str(exc):
            raise
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


# The same standalone guard owns construction, transport checks and readback.
# Keeping this stdlib-only code here also covers the setup-owned single-file copy.
MAX_MESSAGE_BYTES = 8 * 1024 * 1024
MAX_MESSAGE_NODES = 4096
MAX_MESSAGE_DEPTH = 32
TEXT_FIELDS = frozenset(
    {
        "message",
        "text",
        "body",
        "content",
        "prompt",
        "subject",
        "html",
        "htmlBody",
        "bodyHtml",
        "body_html",
        "textBody",
        "bodyText",
        "plain_text",
        "plainText",
        "bodyPlainText",
        "html_body",
        "text_body",
    }
)
DEFAULT_MESSAGE_CAPABILITIES = [
    {
        "tool_pattern": r"mcp__.*__(?:send_gmail_message|draft_gmail_message)$",
        "channel": "email",
        "body_field": "body",
        "format_field": "body_format",
        "html_value": "html",
        "plain_value": "plain",
    },
    {
        "tool_pattern": r"mcp__.*__slack_(?:send_message|send_message_draft|schedule_message)$",
        "channel": "human-text",
    },
]


def canonical_message(tool_name, tool_input):
    """Bind the whole submitted input, including recipients, subject and all parts."""
    if (
        not isinstance(tool_name, str)
        or not tool_name
        or not isinstance(tool_input, dict)
    ):
        raise ValueError("message requires a tool name and object input")
    count = 0

    def visit(value, depth=0):
        nonlocal count
        count += 1
        if count > MAX_MESSAGE_NODES or depth > MAX_MESSAGE_DEPTH:
            raise ValueError("message structure budget exceeded")
        if isinstance(value, dict):
            if not all(isinstance(k, str) for k in value):
                raise ValueError("message object keys must be strings")
            for child in value.values():
                visit(child, depth + 1)
        elif isinstance(value, list):
            for child in value:
                visit(child, depth + 1)
        elif value is not None and type(value) not in (str, int, bool, float):
            raise ValueError("message contains an unsupported value")

    visit(tool_input)
    raw = json.dumps(
        {
            "schema": "synthesis-message-v2",
            "tool_name": tool_name,
            "tool_input": tool_input,
        },
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    )
    if len(raw.encode("utf-8")) > MAX_MESSAGE_BYTES:
        raise ValueError("message byte budget exceeded")
    return raw


def message_digest(tool_name, tool_input):
    return sha256_text(canonical_message(tool_name, tool_input))


def message_fields(tool_input, candidates):
    """Every populated configured/standard text part, including nested multipart."""
    canonical_message("field-inspection", tool_input)
    fields = set(candidates) | TEXT_FIELDS
    found = []
    recognized = []

    def visit(value, path="", textual=False):
        if isinstance(value, str):
            if value.strip():
                found.append((path, value))
                if textual:
                    recognized.append(path)
        elif isinstance(value, dict):
            for key in sorted(value):
                child_path = path + "/" + key.replace("~", "~0").replace("/", "~1")
                visit(value[key], child_path, key in fields or child_path in fields)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, path + "/" + str(index), textual)

    visit(tool_input)
    return found if recognized else []


def capability_for(tool_name, cfg):
    """Only owner configuration declares capabilities; payload labels have no authority."""
    declarations = cfg.get("message_capabilities", DEFAULT_MESSAGE_CAPABILITIES)
    if not isinstance(declarations, list):
        raise ValueError("message capabilities must be a list")
    matches = []
    for entry in declarations:
        if not isinstance(entry, dict) or bool(entry.get("tool_pattern")) == bool(
            entry.get("tool_names")
        ):
            raise ValueError(
                "capability requires either one pattern or an exact tool-name list"
            )
        names = entry.get("tool_names")
        if names is not None and (
            not isinstance(names, list)
            or not names
            or any(not isinstance(n, str) or not n for n in names)
        ):
            raise ValueError("invalid capability tool-name list")
        if entry.get("channel") == "non-correspondence" and names is None:
            raise ValueError("non-correspondence capability requires exact tool names")
        if entry.get("channel") not in ("email", "human-text", "non-correspondence"):
            raise ValueError("unknown declared message capability")
        for option in ("body_field", "format_field", "html_value", "plain_value"):
            if option in entry and (
                not isinstance(entry[option], str) or not entry[option]
            ):
                raise ValueError("capability transport values must be nonempty strings")
        if "fixed_format" in entry and (
            entry["channel"] != "email"
            or entry["fixed_format"] not in ("plain", "html")
            or any(
                key in entry for key in ("format_field", "html_value", "plain_value")
            )
        ):
            raise ValueError(
                "fixed email format must be plain or html with no dynamic mapping"
            )
        if (
            tool_name in names
            if names is not None
            else re.search(entry["tool_pattern"], tool_name)
        ):
            matches.append(entry)
    if len(matches) != 1:
        raise ValueError(
            "tool capability must resolve to exactly one owner-configured declaration"
        )
    return matches[0]


# These are observed native spellings of three transports, not a normalization
# rule. Applying a proposal remains the configuration owner's reviewed action.
CLIENT_TOOL_SPELLINGS = tuple(
    (("mcp__workspace_mcp__" + action, "mcp__workspace-mcp__" + action), channel)
    for action, channel in (
        ("draft_gmail_message", "email"),
        ("send_gmail_message", "email"),
        ("send_message", "human-text"),
    )
)


def client_capability_check(inventories, cfg):
    """Resolve complete supplied client catalogs without granting authority."""
    if not isinstance(inventories, list) or len(inventories) > 3:
        raise ValueError("at most one complete inventory per supported client required")
    clients, seen = [], set()
    for inventory in inventories:
        snapshot = inventory_snapshot(inventory)
        client = snapshot["client"]
        if client in seen:
            raise ValueError("duplicate client inventory")
        seen.add(client)
        if cfg.get("_capability_registry"):
            # A finite dispatch enrollment owns its exact client, descriptors,
            # and complete tool set; legacy spelling pairs cannot enlarge it.
            capability_readiness(inventory, cfg)
        resolved, unresolved = [], []
        for tool in snapshot["tools"]:
            name = tool["name"]
            # Gate installations inspect their correspondence scope. Dispatch
            # registries must classify the entire native catalog.
            if not cfg.get("_capability_registry") and (
                not any(re.search(p, name) for p in cfg["gated_tool_patterns"])
                or any(re.search(p, name) for p in cfg["exempt_tool_patterns"])
            ):
                continue
            try:
                capability = capability_for(name, cfg)
                resolved.append({"name": name, "channel": capability["channel"]})
            except ValueError:
                unresolved.append(name)
        clients.append({"client": client, "inventory_digest": snapshot["inventory_digest"],
                        "resolved": resolved, "unresolved": unresolved})
    return {"status": "OWNER_REVIEW_REQUIRED" if any(c["unresolved"] for c in clients)
            else "DECLARED_CLIENT_INVENTORIES_CLASSIFIED", "clients": clients,
            "native_inventory_provenance_verified": False, "message_authority_granted": False,
            "read_only": True}


def client_capability_plan(inventories, cfg):
    """Propose only known exact spelling additions to explicit declarations."""
    initial = client_capability_check(inventories, cfg)
    if cfg.get("_capability_registry"):
        raise ValueError("dispatch registries require their complete enrollment owner")
    proposed = json.loads(json.dumps(cfg))
    additions = []
    for client in initial["clients"]:
        for name in client["unresolved"]:
            pairs = [(names, channel) for names, channel in CLIENT_TOOL_SPELLINGS if name in names]
            if not pairs:
                raise ValueError("unrecognized exact client spelling requires enrollment: " + name)
            names, channel = pairs[0]
            other = next(tool for tool in names if tool != name)
            entry = capability_for(other, proposed)
            if other not in entry.get("tool_names", []) or entry["channel"] != channel:
                raise ValueError("spelling proposal requires an exact matching transport declaration")
            # A conflicting target is never repaired by changing its channel or
            # precedence. Zero matches is the only permitted additive case.
            try:
                existing = capability_for(name, proposed)
            except ValueError:
                matches = [row for row in proposed["message_capabilities"]
                           if name in row.get("tool_names", []) or
                           (row.get("tool_pattern") and re.search(row["tool_pattern"], name))]
                if matches:
                    raise ValueError("ambiguous target spelling requires owner review")
                entry["tool_names"].append(name)
                additions.append({"client": client["client"], "source": other, "tool": name})
            else:
                if existing != entry:
                    raise ValueError("client spelling has a distinct declaration")
    validate_config(proposed)
    result = client_capability_check(inventories, proposed)
    result.update(status="READY_FOR_CONFIGURATION_REVIEW", additions=additions,
                  effective_configuration=proposed,
                  configuration_sha256=hashlib.sha256(json.dumps(proposed, sort_keys=True, separators=(",", ":")).encode()).hexdigest())
    return result


def declared_spelling_gaps(cfg):
    """Catch known cross-client drift even without claiming a live catalog."""
    if cfg.get("_capability_registry"):
        # Dispatch doctors validate the stored enrollment separately. Requiring
        # an absent alias here would invent a tool outside that finite catalog.
        return []
    gaps = []
    for names, expected_channel in CLIENT_TOOL_SPELLINGS:
        if not any(name in row.get("tool_names", []) for row in cfg.get("message_capabilities", []) for name in names):
            continue
        for name in names:
            try:
                if capability_for(name, cfg)["channel"] != expected_channel:
                    raise ValueError("wrong channel")
            except ValueError:
                gaps.append(name)
    return gaps


def client_capability_apply(request, cfg):
    """Apply a digest-bound owner review; retain config and migration preimages."""
    import fcntl
    import tempfile

    required = {"inventories", "expected_config_sha256", "reviewed_configuration_sha256", "owner_review"}
    if not isinstance(request, dict) or set(request) != required:
        raise ValueError("exact client repair request fields required")
    review = request["owner_review"]
    if (not isinstance(review, dict) or set(review) != {"source", "reviewed_at"}
            or not isinstance(review["source"], str) or not review["source"].strip()
            or len(review["source"]) > 4096 or not isinstance(review["reviewed_at"], str)):
        raise ValueError("attributed configuration owner review required")
    moment = datetime.fromisoformat(review["reviewed_at"].replace("Z", "+00:00"))
    if moment.tzinfo is None or moment > datetime.now(timezone.utc):
        raise ValueError("owner review must be aware and not future")
    path, root = Path(config_path()).absolute(), Path(state_dir()).absolute()
    if root.resolve() != root or path.parent != root:
        raise ValueError("client repair requires the ordinary unaliased configuration owner root")
    lock = root / ".configuration-repair.lock"
    fd = os.open(lock, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        identity = os.fstat(fd)
        if (not stat.S_ISREG(identity.st_mode) or identity.st_nlink != 1
                or identity.st_uid != os.getuid() or identity.st_mode & 0o077):
            raise ValueError("unsafe configuration repair lock")
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        raw = _migration_bytes(path)
        if hashlib.sha256(raw).hexdigest() != request["expected_config_sha256"]:
            raise ValueError("configuration changed since owner review")
        current = _migration_json(raw)
        if current != cfg:
            raise ValueError("effective configuration does not equal the retained owner bytes")
        proposal = client_capability_plan(request["inventories"], current)
        if proposal["configuration_sha256"] != request["reviewed_configuration_sha256"]:
            raise ValueError("owner review does not bind the spelling proposal")
        replacement = (json.dumps(proposal["effective_configuration"], indent=2) + "\n").encode()
        # An already repaired config is kept byte-for-byte, including formatting.
        if not proposal["additions"]:
            replacement = raw
        pending = _migration_pending(root)
        history = Path(tempfile.mkdtemp(prefix="client-repair-", dir=root))
        (history / "patterns.json").write_bytes(raw)
        (history / "patterns.json").chmod(0o600)
        record_path = root / "engine-migration.json"
        previous_record = _migration_bytes(record_path) if os.path.lexists(record_path) else None
        if previous_record is not None:
            (history / "engine-migration.json").write_bytes(previous_record)
            (history / "engine-migration.json").chmod(0o600)

        def replace_owned(target, body, expected):
            actual = _migration_bytes(target) if os.path.lexists(target) else None
            if actual != expected or _migration_pending(root) != pending:
                raise ValueError("configuration or pending custody changed during repair")
            mode = stat.S_IMODE(target.stat().st_mode) if expected is not None else 0o600
            temporary_fd, temporary_name = tempfile.mkstemp(prefix=".client-repair-", dir=root)
            with os.fdopen(temporary_fd, "wb") as stream:
                os.fchmod(stream.fileno(), mode)
                stream.write(body)
                stream.flush()
                os.fsync(stream.fileno())
            actual = _migration_bytes(target) if os.path.lexists(target) else None
            if actual != expected or _migration_pending(root) != pending:
                raise ValueError("owner compare-and-swap refused changed custody")
            os.replace(temporary_name, target)
            parent_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.fsync(parent_fd)
            finally:
                os.close(parent_fd)

        if replacement != raw:
            replace_owned(path, replacement, raw)
        plan = migration_preflight(plan=True)
        if plan["status"] != "OWNER_REVIEW_REQUIRED":
            raise ValueError("repaired configuration still refuses migration: " + str(plan))
        record = dict(plan["required_record"], owner_review=review)
        replace_owned(record_path, (json.dumps(record, indent=2) + "\n").encode(), previous_record)
        result = migration_preflight()
        if result["status"] != "READY_FOR_OWNER_ACTIVATION" or _migration_pending(root) != pending:
            raise ValueError("configuration repair did not close exact migration custody")
        return {"status": "READY_FOR_OWNER_ACTIVATION", "configuration_sha256": hashlib.sha256(_migration_bytes(path)).hexdigest(),
                "additions": proposal["additions"], "history": str(history), "pending_count": len(pending),
                "message_authority_granted": False, "native_inventory_provenance_verified": False}
    finally:
        os.close(fd)


def inventory_snapshot(inventory):
    """A supplied native catalog is evidence input, not an invented live observation."""
    if not isinstance(inventory, dict) or inventory.get("client") not in (
        "claude",
        "codex",
        "muse",
    ):
        raise ValueError("inventory requires a supported client")
    tools = inventory.get("tools")
    if not isinstance(tools, list) or not tools or len(tools) > 10000:
        raise ValueError("bounded nonempty native tool descriptor inventory required")
    source = inventory.get("source")
    if not isinstance(source, str) or not source.strip():
        raise ValueError("inventory source reference required")
    # A descriptor list is not evidence that pagination or discovery finished.
    # This envelope records the collector's explicit coverage assertion; it
    # still does not establish native provenance or owner authority.
    if set(inventory) != {
        "client",
        "source",
        "tools",
        "complete",
        "total_tools",
        "next_cursor",
    }:
        raise ValueError("inventory requires an explicit complete coverage envelope")
    if (
        inventory["complete"] is not True
        or inventory["next_cursor"] is not None
        or type(inventory["total_tools"]) is not int
        or inventory["total_tools"] != len(tools)
    ):
        raise ValueError("incomplete, paginated, or inconsistent native inventory")
    entries = []
    seen = set()
    for tool in tools:
        if (
            not isinstance(tool, dict)
            or not isinstance(tool.get("name"), str)
            or not tool["name"]
            or tool["name"] in seen
        ):
            raise ValueError("unique native tool descriptors required")
        if not isinstance(tool.get("input_schema"), dict):
            raise ValueError("native input schema required; a name is insufficient")
        seen.add(tool["name"])
        entries.append(
            {
                "name": tool["name"],
                "descriptor_sha256": message_digest("native-tool-descriptor", tool),
            }
        )
    entries.sort(key=lambda x: x["name"])
    snapshot = {
        "client": inventory["client"],
        "tools": entries,
        "coverage": {
            "complete": True,
            "total_tools": len(entries),
            "next_cursor": None,
        },
    }
    snapshot["inventory_digest"] = message_digest("native-tool-inventory", snapshot)
    return snapshot


def capability_plan(inventory, cfg):
    snapshot = inventory_snapshot(inventory)
    proposals = []
    by_name = {row["name"]: row for row in inventory["tools"]}
    for row in snapshot["tools"]:
        try:
            cap = dict(capability_for(row["name"], cfg))
            cap.pop("tool_pattern", None)
            cap["tool_names"] = [row["name"]]
            disposition = "EXISTING_OWNER_DECLARATION"
        except ValueError as exc:
            if "exactly one" not in str(exc):
                raise
            cap = None
            disposition = "OWNER_REVIEW_REQUIRED"
        proposals.append(
            {
                **row,
                "status": disposition,
                "capability": cap,
                "read_only_hint": (
                    by_name[row["name"]].get("annotations", {}).get("readOnlyHint")
                    if isinstance(by_name[row["name"]].get("annotations"), dict)
                    else None
                ),
            }
        )
    return {
        **snapshot,
        "proposals": proposals,
        "unclassified": sum(row["capability"] is None for row in proposals),
        "hint_is_authority": False,
        "native_inventory_provenance_verified": False,
    }


def capability_enroll(request, cfg):
    if not isinstance(request, dict):
        raise ValueError("enrollment request must be an object")
    inventory = request.get("inventory")
    snapshot = inventory_snapshot(inventory)
    review = request.get("owner_review")
    if (
        not isinstance(review, dict)
        or review.get("inventory_digest") != snapshot["inventory_digest"]
        or not isinstance(review.get("source"), str)
        or not review["source"].strip()
    ):
        raise ValueError(
            "owner review must bind the exact inventory and its authorization source"
        )
    decisions = request.get("decisions")
    if not isinstance(decisions, list):
        raise ValueError("explicit complete capability decisions required")
    observed = {row["name"]: row["descriptor_sha256"] for row in snapshot["tools"]}
    caps = []
    seen = set()
    for decision in decisions:
        if not isinstance(decision, dict):
            raise ValueError("invalid capability decision")
        name = decision.get("name")
        if (
            name not in observed
            or name in seen
            or decision.get("descriptor_sha256") != observed[name]
        ):
            raise ValueError(
                "decision missing, duplicated or stale against native descriptor"
            )
        seen.add(name)
        cap = decision.get("capability")
        if (
            not isinstance(cap, dict)
            or "tool_pattern" in cap
            or set(cap)
            - {
                "channel",
                "body_field",
                "format_field",
                "fixed_format",
                "html_value",
                "plain_value",
            }
        ):
            raise ValueError(
                "enrolled capability must be exact and contain only contract fields"
            )
        cap = {**cap, "tool_names": [name]}
        capability_for(name, {"message_capabilities": [cap]})
        if cap["channel"] == "email" and (
            not isinstance(cap.get("body_field"), str)
            or not (isinstance(cap.get("format_field"), str) or "fixed_format" in cap)
        ):
            raise ValueError(
                "email decision requires actual body and format schema mapping"
            )
        caps.append(cap)
    if seen != set(observed):
        raise ValueError("enrollment has unclassified native tools")
    return {
        "schema_version": 1,
        "capabilities": caps,
        "inventory": snapshot,
        "owner_review": review,
        "status": "READY_FOR_OWNER_ACTIVATION",
        "owner_authorization_verified": False,
        "native_inventory_provenance_verified": False,
    }


def validate_capability_registry(registry):
    """Refuse partial/corrupt enrollment; owner evidence is a pointer, not proof."""
    if not isinstance(registry, dict) or registry.get("schema_version") != 1:
        raise ValueError("invalid owner capability registry")
    snapshot = registry.get("inventory")
    if not isinstance(snapshot, dict) or snapshot.get("client") not in (
        "claude",
        "codex",
        "muse",
    ):
        raise ValueError("capability registry has no bound client inventory")
    rows = snapshot.get("tools")
    if not isinstance(rows, list) or not rows:
        raise ValueError("capability registry inventory is empty")
    names = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"name", "descriptor_sha256"}:
            raise ValueError("malformed enrolled descriptor")
        if (
            not isinstance(row["name"], str)
            or not row["name"]
            or not isinstance(row["descriptor_sha256"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", row["descriptor_sha256"])
        ):
            raise ValueError("invalid enrolled descriptor")
        names.append(row["name"])
    if names != sorted(set(names)):
        raise ValueError("enrolled inventory must be unique and ordered")
    coverage = snapshot.get("coverage")
    if (
        not isinstance(coverage, dict)
        or set(coverage) != {"complete", "total_tools", "next_cursor"}
        or coverage["complete"] is not True
        or coverage["next_cursor"] is not None
        or type(coverage["total_tools"]) is not int
        or coverage["total_tools"] != len(rows)
    ):
        raise ValueError("capability registry has no complete coverage binding")
    digest = message_digest(
        "native-tool-inventory",
        {"client": snapshot["client"], "tools": rows, "coverage": coverage},
    )
    review = registry.get("owner_review")
    if (
        digest != snapshot.get("inventory_digest")
        or not isinstance(review, dict)
        or review.get("inventory_digest") != digest
        or not isinstance(review.get("source"), str)
        or not review["source"].strip()
    ):
        raise ValueError("capability registry review binding differs")
    caps = registry.get("capabilities")
    if not isinstance(caps, list) or len(caps) != len(names):
        raise ValueError("capability registry is incomplete")
    bound = []
    for cap in caps:
        if (
            not isinstance(cap, dict)
            or "tool_pattern" in cap
            or set(cap)
            - {
                "channel",
                "tool_names",
                "body_field",
                "format_field",
                "fixed_format",
                "html_value",
                "plain_value",
            }
        ):
            raise ValueError("registry declarations must be exact")
        cap_names = cap.get("tool_names")
        if (
            not isinstance(cap_names, list)
            or len(cap_names) != 1
            or cap_names[0] not in names
        ):
            raise ValueError("invalid registry tool binding")
        bound.extend(cap_names)
        capability_for(cap_names[0], {"message_capabilities": caps})
        if cap["channel"] == "email" and (
            not isinstance(cap.get("body_field"), str)
            or not cap["body_field"]
            or not (isinstance(cap.get("format_field"), str) or "fixed_format" in cap)
        ):
            raise ValueError("email registry requires transport mapping")
    if sorted(bound) != names:
        raise ValueError("capability registry is duplicated or incomplete")
    return registry


def capability_readiness(inventory, cfg):
    registry = validate_capability_registry(cfg.get("_capability_registry"))
    current = inventory_snapshot(inventory)
    enrolled = registry["inventory"]
    if not isinstance(enrolled, dict):
        raise ValueError("no enrolled native inventory; broader hooks cannot activate")
    if enrolled.get("client") != current["client"]:
        raise ValueError("capability registry belongs to another client")
    old = {row["name"]: row["descriptor_sha256"] for row in enrolled.get("tools", [])}
    new = {row["name"]: row["descriptor_sha256"] for row in current["tools"]}
    added = sorted(new.keys() - old.keys())
    removed = sorted(old.keys() - new.keys())
    changed = sorted(name for name in new.keys() & old.keys() if new[name] != old[name])
    if (
        added
        or removed
        or changed
        or current["inventory_digest"] != enrolled.get("inventory_digest")
    ):
        raise ValueError(
            "native inventory drift: added=%s removed=%s changed=%s; retain old registry and review a new proposal"
            % (added, removed, changed)
        )
    for name in new:
        capability_for(name, cfg)
    return {
        "status": "READY_FOR_OWNER_ACTIVATION",
        "client": current["client"],
        "tools": len(new),
        "inventory_digest": current["inventory_digest"],
        "native_inventory_provenance_verified": False,
        "effect": "read-only; no hook, policy, or registry changed",
    }


def field_value(value, path):
    if not isinstance(path, str) or not path:
        raise ValueError("capability field mapping required")
    keys = path[1:].split("/") if path.startswith("/") else [path]
    for key in keys:
        key = key.replace("~1", "/").replace("~0", "~")
        if isinstance(value, dict):
            value = value.get(key)
        elif isinstance(value, list) and re.fullmatch(r"0|[1-9][0-9]*", key):
            # A JSON Pointer index has no sign, leading zero or append marker.
            if len(key) > 10 or int(key) >= len(value):
                return None
            value = value[int(key)]
        else:
            return None
    return value


def email_policy(cfg):
    policy = cfg.get("email_policy", {})
    if not isinstance(policy, dict):
        raise ValueError("email policy must be an object")
    if set(policy) - {"default_format", "allow_intra_paragraph_breaks"}:
        raise ValueError("unknown email policy key")
    result = {
        "default_format": policy.get("default_format", "html"),
        "allow_intra_paragraph_breaks": policy.get(
            "allow_intra_paragraph_breaks", False
        ),
    }
    if (
        result["default_format"] not in ("html", "plain")
        or type(result["allow_intra_paragraph_breaks"]) is not bool
    ):
        raise ValueError("invalid email policy override")
    return result


def html_inspection(value, *, allow_breaks=False):
    from html.parser import HTMLParser
    from urllib.parse import urlsplit

    class Inspector(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.text = []
            self.failures = []
            self.stack = []

        def handle_starttag(self, tag, attrs):
            permitted = {
                "p",
                "div",
                "span",
                "a",
                "em",
                "strong",
                "b",
                "i",
                "u",
                "ul",
                "ol",
                "li",
                "blockquote",
                "html",
                "body",
                "br",
            }
            if tag not in permitted:
                self.failures.append("unsupported HTML element: " + tag)
            if tag == "br" and not allow_breaks:
                self.failures.append("intra-paragraph HTML break is not permitted")
            if tag in {"p", "div", "li", "blockquote"}:
                self.text.append("\n\n")
            if tag == "br":
                self.text.append("\n")
            for name, val in attrs:
                if name not in {"href", "title", "lang", "dir"}:
                    self.failures.append("unsupported HTML attribute: " + name)
                if name == "href":
                    if (
                        not val
                        or any(ord(c) < 32 for c in val)
                        or urlsplit(val.strip()).scheme.lower()
                        not in {"https", "http", "mailto"}
                    ):
                        self.failures.append("unsafe or unsupported HTML link")
            if tag != "br":
                self.stack.append(tag)

        def handle_startendtag(self, tag, attrs):
            self.handle_starttag(tag, attrs)
            if tag != "br":
                self.handle_endtag(tag)

        def handle_endtag(self, tag):
            if tag == "br":
                self.failures.append("invalid closing break tag")
                return
            if not self.stack or self.stack[-1] != tag:
                self.failures.append("unbalanced HTML")
            else:
                self.stack.pop()
            if tag in {"p", "div", "li", "blockquote"}:
                self.text.append("\n\n")

        def handle_data(self, data):
            self.text.append(re.sub(r"\s+", " ", data))

        def handle_comment(self, data):
            self.failures.append("HTML comments are not supported in outgoing prose")

    parser = Inspector()
    parser.feed(value)
    parser.close()
    if parser.stack:
        parser.failures.append("unclosed HTML element")
    return "".join(parser.text).strip(), parser.failures



def scan_message_text(value, compiled_block, compiled_warn):
    """Scan wire and visible prose without discarding Slack link destinations."""
    import html

    def link_text(match):
        destination, label = match.group(1), match.group(2)
        # Slack angle links are not HTML tags. Keep both their visible label
        # and destination as text before the HTML/entity inspection pass.
        visible = html.unescape(label or destination)
        return html.escape(visible + (" " + destination if label else ""))

    inspectable = re.sub(
        r"<(https?://[^\s<>|]+|mailto:[^\s<>|]+)(?:\|([^<>]*))?>",
        link_text, value,
    )
    rendered = html_inspection(inspectable, allow_breaks=True)[0]
    blocks, warns = scan_text(value, compiled_block, compiled_warn)
    visible_blocks, visible_warns = scan_text(rendered, compiled_block, compiled_warn)
    return list(dict.fromkeys(blocks + visible_blocks)), list(dict.fromkeys(warns + visible_warns))


def paragraph_failures(value):
    # Blank lines separate paragraphs. A single physical newline within any
    # paragraph is the original defect; no wrapping width makes it acceptable.
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    return (
        ["intra-paragraph plain-text line break"]
        if any("\n" in p for p in re.split(r"\n[ \t]*\n+", normalized.strip()))
        else []
    )


def paragraph_policy(cfg):
    policy = cfg.get("paragraph_policy", {})
    if not isinstance(policy, dict) or set(policy) - {"allow_intra_paragraph_breaks"}:
        raise ValueError("invalid outbound paragraph policy")
    allow = policy.get("allow_intra_paragraph_breaks", False)
    if type(allow) is not bool:
        raise ValueError("paragraph override must be an owner-configured boolean")
    return allow


def build_text(spec, cfg):
    """Construct literal human-text paragraphs, without choosing or calling a tool."""
    if not isinstance(spec, dict) or set(spec) != {"paragraphs"}:
        raise ValueError("text constructor accepts only a paragraph list")
    paragraphs = spec["paragraphs"]
    if (
        not isinstance(paragraphs, list)
        or not paragraphs
        or any(not isinstance(p, str) or not p.strip() for p in paragraphs)
    ):
        raise ValueError("text constructor requires nonempty paragraphs")
    allow = paragraph_policy(cfg)
    value = "\n\n".join(p if allow else " ".join(p.split()) for p in paragraphs)
    canonical_message("text-constructor", {"message": value})
    return {"message": value}


def verify_text_readback(expected, observed, cfg):
    if not isinstance(expected, str) or not isinstance(observed, str):
        raise ValueError("text readback requires expected and observed strings")
    canonical_message("text-readback", {"expected": expected, "observed": observed})
    if not paragraph_policy(cfg) and paragraph_failures(observed):
        raise ValueError("observed text contains intra-paragraph line breaks")
    if expected != observed:
        raise ValueError("observed text differs from the approved content")
    return {
        "status": "VERIFIED_SUPPLIED_READBACK",
        "provenance_verified": False,
        "text_sha256": sha256_text(observed),
    }


def email_format_failures(tool_name, tool_input, cfg):
    cap = capability_for(tool_name, cfg)
    if cap["channel"] != "email":
        return []
    policy = email_policy(cfg)
    body_field = cap.get("body_field")
    format_field = cap.get("format_field")
    if not body_field or not (format_field or "fixed_format" in cap):
        return ["email capability lacks body/format mapping"]
    body = field_value(tool_input, body_field)
    if not isinstance(body, str) or not body.strip():
        return ["email body missing or not text"]
    if "fixed_format" in cap:
        # The native transport owns this format. A payload cannot override it.
        actual = cap["fixed_format"]
        wanted = policy["default_format"]
    else:
        actual = field_value(tool_input, format_field)
        wanted = cap.get(policy["default_format"] + "_value", policy["default_format"])
    if actual != wanted:
        return [
            "email requires %s via declared transport capability; configure an explicit policy override or use a capable transport"
            % policy["default_format"]
        ]
    failures = []
    html_keys = {"html", "htmlBody", "bodyHtml", "body_html", "html_body"}
    plain_keys = {
        "textBody",
        "bodyText",
        "plain_text",
        "plainText",
        "bodyPlainText",
        "text_body",
    }
    if policy["default_format"] == "html":
        if "<" not in body:
            failures.append("HTML email must contain paragraph markup")
        failures.extend(
            html_inspection(body, allow_breaks=policy["allow_intra_paragraph_breaks"])[
                1
            ]
        )
    elif not policy["allow_intra_paragraph_breaks"]:
        failures.extend(paragraph_failures(body))
    # Inspect every nested textual body, including MIME-style parts whose
    # literal content is not named htmlBody/textBody. Encoded text requires a
    # transport adapter; hashing opaque bytes is not a rendered-content check.
    canonical_message(tool_name, tool_input)
    text_keys = set(TEXT_FIELDS) | {"content", "body", "data", "raw"}
    html_marker = re.compile(
        r"</?(?:p|div|span|br|script|style|iframe|a|img|pre|table|b|i|strong|em)(?:\s|/?>)",
        re.I,
    )

    def inspect(value, inherited=None, key="", parent_text=False):
        if isinstance(value, dict):
            kinds = []
            for name in ("mimeType", "mime_type", "contentType", "content_type"):
                if name in value:
                    declared = value[name]
                    if not isinstance(declared, str):
                        failures.append("invalid nested content type")
                        continue
                    declared = declared.split(";", 1)[0].strip().lower()
                    if declared in ("html", "text/html"):
                        kinds.append("html")
                    elif declared in ("plain", "text", "text/plain"):
                        kinds.append("plain")
                    elif declared.startswith("text/"):
                        failures.append("unsupported nested textual MIME type")
            if len(set(kinds)) > 1:
                failures.append("conflicting nested content types")
            kind = kinds[0] if kinds else inherited
            if kinds and any(
                name in value
                for name in (
                    "encoding",
                    "contentTransferEncoding",
                    "content_transfer_encoding",
                )
            ):
                failures.append(
                    "encoded nested text requires a verified transport adapter"
                )
            for child_key, child in value.items():
                inspect(child, kind, child_key, parent_text or key in text_keys)
        elif isinstance(value, list):
            for child in value:
                inspect(child, inherited, key, parent_text)
        elif isinstance(value, str) and value:
            is_text = (
                key in text_keys or key in html_keys or key in plain_keys or parent_text
            )
            if key in ("data", "raw") and inherited in ("html", "plain"):
                failures.append(
                    "opaque nested MIME text requires a verified transport adapter"
                )
                return
            if key in (
                "mimeType",
                "mime_type",
                "contentType",
                "content_type",
                "encoding",
                "body_format",
            ):
                return
            kind = (
                "html"
                if key in html_keys
                else "plain"
                if key in plain_keys
                else inherited
            )
            if kind is None and is_text:
                kind = "html" if html_marker.search(value) else "plain"
            # Catch unnamed alternate HTML without interpreting recipient or
            # threading angle brackets as markup.
            if kind is None and html_marker.search(value):
                kind = "html"
            if not is_text and kind == inherited:
                return
            if kind == "html":
                failures.extend(
                    html_inspection(
                        value, allow_breaks=policy["allow_intra_paragraph_breaks"]
                    )[1]
                )
            elif kind == "plain" and not policy["allow_intra_paragraph_breaks"]:
                failures.extend(paragraph_failures(value))

    inspect(tool_input)
    return failures


def build_email(spec, cfg=None):
    """Construct literal paragraphs; never silently interpret prose as markup."""
    import html

    if not isinstance(spec, dict) or set(spec) - {
        "paragraphs",
        "subject",
        "to",
        "cc",
        "bcc",
    }:
        raise ValueError(
            "email constructor accepts paragraphs and explicit address/subject fields only"
        )
    paragraphs = spec.get("paragraphs")
    if (
        not isinstance(paragraphs, list)
        or not paragraphs
        or any(not isinstance(p, str) or not p.strip() for p in paragraphs)
    ):
        raise ValueError("email construction requires nonempty paragraph strings")
    policy = email_policy(cfg or {})
    clean = []
    for paragraph in paragraphs:
        if not policy["allow_intra_paragraph_breaks"]:
            paragraph = " ".join(paragraph.split())
        clean.append(paragraph)
    if policy["default_format"] == "html":
        body = "".join(
            "<p>" + html.escape(p).replace("\n", "<br>") + "</p>" for p in clean
        )
    else:
        body = "\n\n".join(clean)
    result = {key: value for key, value in spec.items() if key != "paragraphs"}
    result.update(body=body, body_format=policy["default_format"])
    canonical_message("email-constructor", result)
    return result


def email_mime(body):
    """Synthetic/local MIME construction only; this helper never sends."""
    from email.message import EmailMessage
    from email.policy import SMTP

    if not isinstance(body, dict):
        raise ValueError("expected MIME construction must be an object")
    headers = {
        "to": "To",
        "cc": "Cc",
        "bcc": "Bcc",
        "subject": "Subject",
        "from": "From",
        "reply_to": "Reply-To",
        "in_reply_to": "In-Reply-To",
        "references": "References",
        "message_id": "Message-ID",
    }
    unknown = set(body) - {"body", "body_format", *headers}
    if unknown:
        raise ValueError(
            "MIME readback cannot verify these transport fields: "
            + ", ".join(sorted(unknown))
        )
    canonical_message("email-mime", body)
    if not isinstance(body.get("body"), str) or not body["body"].strip():
        raise ValueError("nonempty expected MIME body required")
    msg = EmailMessage(policy=SMTP)
    for key, header in headers.items():
        if key in body:
            value = body[key]
            if isinstance(value, list):
                if key not in ("to", "cc", "bcc") or any(
                    not isinstance(v, str) for v in value
                ):
                    raise ValueError("only address headers accept string lists")
                value = ", ".join(value)
            if not isinstance(value, str):
                raise ValueError("invalid email header value")
            msg[header] = value
    text = body["body"]
    if body["body_format"] == "html":
        plain, failures = html_inspection(text, allow_breaks=True)
        if failures:
            raise ValueError("unsafe HTML construction: " + "; ".join(failures))
        msg.set_content(plain)
        msg.add_alternative(text, subtype="html")
    elif body["body_format"] == "plain":
        msg.set_content(text)
    else:
        raise ValueError("unknown email format")
    raw = msg.as_string()
    if len(raw.encode()) > MAX_MESSAGE_BYTES:
        raise ValueError("MIME message byte budget exceeded")
    return raw


def inspect_email_mime(raw, cfg):
    from email import policy
    from email.parser import Parser

    if not isinstance(raw, str) or len(raw.encode()) > MAX_MESSAGE_BYTES:
        raise ValueError("invalid or oversized MIME readback")
    msg = Parser(policy=policy.default).parsestr(raw)
    parts = []
    pending = [(msg, 0)]
    while pending:
        part, depth = pending.pop()
        parts.append(part)
        if len(parts) > 128 or depth > 16 or part.defects:
            raise ValueError("malformed or oversized MIME structure")
        for header in (
            "Content-Type",
            "Content-Transfer-Encoding",
            "Content-Disposition",
            "MIME-Version",
        ):
            if len(part.get_all(header, [])) > 1:
                raise ValueError("duplicate MIME control header")
        if (
            part.get_content_disposition() is not None
            or part.get_filename() is not None
        ):
            raise ValueError(
                "MIME attachment/disposition needs a transport-specific readback adapter"
            )
        if part.is_multipart():
            pending.extend((child, depth + 1) for child in reversed(part.get_payload()))
    for part in parts:
        if any(getattr(value, "defects", ()) for _, value in part.items()):
            raise ValueError("malformed MIME header")
    text_parts = []
    failures = []
    policy_cfg = email_policy(cfg)
    for part in parts:
        if part.is_multipart():
            continue
        mime = part.get_content_type()
        if mime not in ("text/plain", "text/html"):
            failures.append("unsupported MIME part " + mime)
            continue
        value = part.get_content()
        # Transfer decoders may record defects only when content is decoded.
        # A repaired/malformed encoding must not receive a verified receipt.
        if part.defects:
            raise ValueError("malformed MIME transfer encoding")
        if not isinstance(value, str):
            raise ValueError("MIME text decoding failed")
        value = value.replace("\r\n", "\n").replace("\r", "\n").removesuffix("\n")
        if mime == "text/html":
            failures.extend(
                html_inspection(
                    value, allow_breaks=policy_cfg["allow_intra_paragraph_breaks"]
                )[1]
            )
        elif not policy_cfg["allow_intra_paragraph_breaks"]:
            failures.extend(paragraph_failures(value))
        text_parts.append((mime, value))
    if not text_parts:
        failures.append("no readable MIME text parts")
    if policy_cfg["default_format"] == "html" and not any(
        kind == "text/html" for kind, _ in text_parts
    ):
        failures.append("HTML email part missing")
    if failures:
        raise ValueError("; ".join(failures))
    return msg, text_parts


def verify_email_readback(expected, raw, cfg):
    observed, parts = inspect_email_mime(raw, cfg)
    want_msg, want_parts = inspect_email_mime(email_mime(expected), cfg)
    if parts != want_parts:
        raise ValueError("readback parts differ from expected content")

    def topology(message):
        return [
            (
                part.get_content_type(),
                len(part.get_payload()) if part.is_multipart() else 0,
            )
            for part in message.walk()
        ]

    if topology(observed) != topology(want_msg):
        raise ValueError("readback MIME structure differs from expected content")
    headers = ["to", "cc", "bcc", "subject", "reply-to", "in-reply-to", "references"]
    headers.extend(
        name.replace("_", "-") for name in ("from", "message_id") if name in expected
    )
    for key in headers:
        if observed.get_all(key, []) != want_msg.get_all(key, []):
            raise ValueError("readback header differs: " + key)
    return {
        "status": "VERIFIED_SUPPLIED_READBACK",
        "provenance_verified": False,
        "mime_parts": len(parts),
        "verified_headers": headers,
        "expected_sha256": message_digest("email-readback", expected),
        "raw_sha256": sha256_text(raw),
    }


def monitor_email_records(records, cfg):
    if not isinstance(records, list) or len(records) > 1000:
        raise ValueError("bounded record list required")
    canonical_message("email-monitor-input", {"records": records})
    results = []
    seen = set()
    for record in records:
        if (
            not isinstance(record, dict)
            or not isinstance(record.get("message_id"), str)
            or not record["message_id"]
            or record["message_id"] in seen
        ):
            raise ValueError("unique message IDs required for monitoring inventory")
        seen.add(record["message_id"])
        try:
            if "expected" in record:
                verify_email_readback(record["expected"], record.get("raw_mime"), cfg)
            else:
                inspect_email_mime(record.get("raw_mime"), cfg)
            failures = []
        except Exception as exc:
            failures = [str(exc)]
        results.append({"message_id": record["message_id"], "violations": failures})
    return {
        "checked": len(results),
        "violations": sum(bool(r["violations"]) for r in results),
        "real_transport_observed": False,
        "results": results,
    }


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
                "signature as a bare URL"
            )
        if _re.search(r"\]\(https?://", text):
            failures.append(
                "markdown link notation never renders in email bodies; "
                "convert to HTML anchors before staging"
            )
    fallback_tools = enforcement.get("linkless_fallback_tools")
    if fallback_tools and _re.search(fallback_tools, tool_name):
        return failures  # visible-URL form is the legitimate form here
    stripped = _strip_linked_constructs(text)
    exposed = [d for d in enforcement.get("domains", []) if d in stripped]
    if exposed:
        failures.append(
            "persona signature uses the visible-URL fallback (%s appears "
            "as text, not inside a link) on a link-capable channel — the "
            "persona name must BE the hyperlink" % ", ".join(exposed)
        )
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


def build_grounding_envelope(request):
    """Assemble mechanical fields around explicit model-supplied judgments.

    The request must contain the final complete tool payload. No send, source
    reading, voice approval, factual verdict or policy exception is inferred.
    """
    if not isinstance(request, dict) or set(request) != {"tool_name", "tool_input", "grounding"}:
        raise ValueError("envelope requires final tool_name, tool_input and grounding")
    name, payload, grounding = request["tool_name"], request["tool_input"], request["grounding"]
    if not isinstance(name, str) or not name or len(name) > 256 or not isinstance(payload, dict) or not payload:
        raise ValueError("envelope requires a named tool and complete object payload")
    required = {"channel", "recipient", "is_reply", "claims", "no_factual_claims",
                "voice_rules_pass", "invented_precision_scan", "recipient_address_check", "ragbot_branding_check"}
    optional = {"thread_fully_read", "history_searched"}
    if not isinstance(grounding, dict) or not required <= set(grounding) or set(grounding) - required - optional:
        raise ValueError("grounding fields are missing or include caller-generated hash/time")
    for flag in required - {"channel", "recipient", "claims"}:
        if type(grounding[flag]) is not bool:
            raise ValueError("judgment flags must be explicit booleans")
    if not all(isinstance(grounding[key], str) and grounding[key].strip() for key in ("channel", "recipient")):
        raise ValueError("channel and recipient must be explicit")
    claims = grounding["claims"]
    if not isinstance(claims, list) or len(claims) > 4096 or (not claims and not grounding["no_factual_claims"]):
        raise ValueError("provide bounded claims or explicitly state no factual claims")
    if claims and grounding["no_factual_claims"]:
        raise ValueError("claims contradict no_factual_claims")
    for claim in claims:
        if not isinstance(claim, dict) or not {"claim", "source"} <= set(claim) or set(claim) - {"claim", "source", "read_at"} or not all(isinstance(claim[key], str) and claim[key].strip() for key in ("claim", "source")):
            raise ValueError("every claim requires explicit text and source provenance")
    # The existing gate validates thread freshness, claims, approvals and register.
    raw = json.dumps(request, allow_nan=False, ensure_ascii=False)
    if len(raw.encode("utf-8")) > 4 * 1024 * 1024:
        raise ValueError("grounding envelope input exceeds bound")
    result = json.loads(json.dumps(grounding, allow_nan=False))
    result["message_sha256"] = message_digest(name, payload)
    result["created_at"] = datetime.now(timezone.utc).isoformat()
    return result


def validate_ledger(ledger, text, cfg, tool_name, expected_sha=None):
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
                % (age_min, cfg["ledger_max_age_minutes"])
            )
    except Exception:
        fails.append("ledger created_at missing or unparseable (use ISO-8601)")

    if ledger.get("message_sha256") != (expected_sha or sha256_text(text)):
        fails.append(
            "message_sha256 does not match the outgoing text. The message was "
            "edited after grounding, or the ledger was written for a different "
            "message. Re-verify the final text and rewrite the ledger "
            "(pipe the complete tool_name/tool_input JSON to --message-sha)."
        )

    if ledger.get("is_reply") is None:
        fails.append("ledger must state is_reply: true or false")

    if ledger.get("is_reply"):
        tfr = ledger.get("thread_fully_read") or {}
        if not (isinstance(tfr, dict) and tfr.get("source_ids")):
            fails.append(
                "is_reply=true but thread_fully_read.source_ids is empty — read "
                "the ENTIRE thread (including quoted history) and cite message "
                "IDs / ts values actually fetched this session."
            )
        hs = ledger.get("history_searched") or []
        ok = [
            h for h in hs if isinstance(h, dict) and h.get("query") and h.get("where")
        ]
        if not ok:
            fails.append(
                "is_reply=true but history_searched is empty — search prior "
                "correspondence for this recipient/topic (all mailboxes AND "
                "local transcripts) and record each query and where it ran."
            )

    claims = ledger.get("claims")
    currency = currency_config(cfg)
    if ledger.get("no_factual_claims") is True:
        pass
    elif isinstance(claims, list) and claims:
        for i, c in enumerate(claims):
            if not (isinstance(c, dict) and c.get("claim") and c.get("source")):
                fails.append("claims[%d] must have non-empty claim and source" % i)
                continue
            if currency and any(
                rx.search(str(c["claim"])) for rx in currency["patterns"]
            ):
                age = minutes_since(c.get("read_at"))
                snippet = str(c["claim"])[:60]
                if age is None:
                    fails.append(
                        "claims[%d] asserts a currency state (%r) but has no read_at — "
                        "re-read the source THIS RUN and record when (ISO-8601). A read "
                        "from earlier today is a statement about the past."
                        % (i, snippet)
                    )
                elif age > currency["max_age"]:
                    fails.append(
                        "claims[%d] rests on a read %.0f min old (max %.0f for currency "
                        "claims: %r) — re-read the source and refresh read_at."
                        % (i, age, currency["max_age"], snippet)
                    )
    else:
        fails.append(
            "ledger needs a claims[] array mapping every factual claim to its "
            "source, or no_factual_claims: true if the message asserts nothing."
        )

    for flag in (
        "voice_rules_pass",
        "invented_precision_scan",
        "recipient_address_check",
    ):
        if ledger.get(flag) is not True:
            fails.append("ledger flag %s must be explicitly true" % flag)

    if re.search(r"slack_send_message$", tool_name):
        if ledger.get("ragbot_branding_check") is not True:
            fails.append(
                "direct Slack sends require ragbot_branding_check: true — load "
                "the communications skill and verify tier + signature before "
                "sending as the agent."
            )

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


def _peer_board_owner():
    """Bind the canonical parser to this source release or its installed payload."""
    import importlib

    here = Path(__file__).resolve().parent
    root = here
    if here.parts[-3:] == ("skills", "synthesis-message-guard", "scripts"):
        root = here.parents[1] / "synthesis-project-management/scripts"
    names = ("native_git", "claim_scope", "board_grammar", "coordination_schema")
    # No home-cache, PATH, or unrelated sys.path fallback can supply authority.
    for name in names:
        path = root / (name + ".py")
        _doctor_regular_bytes(path, limit=4 * 1024 * 1024)
        cached = sys.modules.get(name)
        if cached is not None and Path(cached.__file__).resolve() != path:
            raise ValueError("peer board runtime has a foreign module binding")
    sys.path.insert(0, str(root))
    try:
        modules = [importlib.import_module(name) for name in names]
        if any(Path(module.__file__).resolve() != root / (name + ".py")
               for name, module in zip(names, modules)):
            raise ValueError("peer board runtime module escaped its source")
        return modules[2]
    finally:
        sys.path.remove(str(root))


# The coordination board grows with history (about 2 MiB on 2026-10-05);
# keep the peer check well above that so growth cannot silently block sends.
PEER_BOARD_MAX_BYTES = 16 * 1024 * 1024


def _board_has_active_ref(content, ref):
    """Named schema columns and canonical nonterminal status, never prose matches."""
    if not isinstance(content, str) or len(content.encode("utf-8")) > PEER_BOARD_MAX_BYTES:
        raise ValueError("peer board exceeds the bounded parser input")
    owner = _peer_board_owner()
    rows = owner.parse_table_rows(content, strict=True)
    # Released rows are history: a long-lived desktop session keeps one client
    # ref across many released seats. Only two or more nonterminal rows that
    # assert the same native identity are ambiguous.
    active = [row for row in rows
              if row.get("client session ref") == ref and owner.active_status(row["status"])]
    return len(active) == 1


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
        content = _doctor_regular_bytes(board, limit=PEER_BOARD_MAX_BYTES).decode("utf-8")
        if _board_has_active_ref(content, "ccd:" + target) or _board_has_active_ref(content, target):
            return True, []
    except (OSError, ValueError, ImportError, AttributeError, RuntimeError) as exc:
        return True, [
            "coordination board unreadable or canonical parser unverifiable (%s): %s" % (board, exc)
        ]
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


def run_gate(payload=None, dispatch=False):
    try:
        payload = read_json_input() if payload is None else payload
        tool_name = payload.get("tool_name", "")
        tool_input = payload.get("tool_input") or {}

        cfg, cblock, cwarn, gated, exempt = load_config()
        if dispatch:
            registry = validate_capability_registry(cfg.get("_capability_registry"))
            if cfg.get("message_capabilities") != registry["capabilities"]:
                block(
                    "dispatch declarations differ from the complete enrolled registry"
                )

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
                fh.write(
                    json.dumps(
                        {
                            "at": datetime.now(timezone.utc).isoformat(),
                            "kind": "peer-send",
                            "tool": tool_name,
                            "engine": ENGINE_VERSION,
                        }
                    )
                    + "\n"
                )
            sys.exit(0)

        if dispatch:
            capability = capability_for(tool_name, cfg)
            if capability["channel"] == "non-correspondence":
                sys.exit(0)
        if not dispatch and any(rx.search(tool_name) for rx in exempt):
            sys.exit(0)
        if not dispatch and not any(rx.search(tool_name) for rx in gated):
            # Reached us via settings matcher but not recognized: unknown = closed.
            block(
                "tool %r matched the hook wiring but is not in "
                "gated_tool_patterns. Update patterns.json deliberately "
                "rather than sending through an unclassified tool." % tool_name
            )

        canonical_message(tool_name, tool_input)
        cap = capability_for(tool_name, cfg)
        if cap["channel"] == "non-correspondence":
            block(
                "non-correspondence capabilities belong to dispatch, not the send gate"
            )
        candidates = list(cfg["text_field_candidates"]) + [cap.get("body_field", "")]
        fields = message_fields(tool_input, candidates)
        if not fields:
            block("could not locate outgoing message text; unknown shape fails closed")
        warns = []
        for field, text in fields:
            hits, field_warns = scan_message_text(text, cblock, cwarn)
            warns += field_warns
            if hits:
                block(
                    "register scan failed in %s — %s"
                    % (field, "; ".join("[%s] matched %r" % item for item in hits))
                )
            wire_fails = signature_wire_failures(tool_name, tool_input, text, cfg)
            if wire_fails:
                block("signature wire-form violation — " + " | ".join(wire_fails))
        format_fails = email_format_failures(tool_name, tool_input, cfg)
        if cap["channel"] == "human-text" and not paragraph_policy(cfg):
            for field, value in fields:
                format_fails.extend(
                    field + ": " + reason for reason in paragraph_failures(value)
                )
        if format_fails:
            block("outbound format violation — " + " | ".join(format_fails))
        text = "\n\n".join(value for _, value in fields)
        header_fails = check_header_hygiene(tool_input)
        if header_fails:
            block("threading headers malformed — " + " | ".join(header_fails))

        sweep_orphan_ledgers(cfg)
        text_sha = message_digest(tool_name, tool_input)
        lp = ledger_path_for(text_sha)
        if not os.path.exists(lp):
            block(
                "no grounding ledger for this exact message at %s. Before "
                "composing you must: "
                "(1) read the FULL thread including quoted history, "
                "(2) search prior correspondence for this recipient/topic "
                "across all mailboxes and local transcripts, "
                "(3) map every factual claim to a source, "
                "(4) run the voice pass. Then file the ledger with "
                "--write-ledger (it computes this path from the ledger's own "
                "message_sha256, so it cannot be misfiled); --ledger-template "
                "gives the skeleton and --message-sha the cross-field hash. One ledger per "
                "message, named by that message's sha, consumed on use. "
                "A ledger written for DIFFERENT text lives at a different "
                "path and is never silently substituted for this one." % lp
            )
        try:
            with open(lp, "r", encoding="utf-8") as fh:
                ledger = json.load(fh)
        except Exception as exc:
            block("ledger exists but is unreadable (%s). Rewrite it." % exc)

        fails = validate_ledger(ledger, text, cfg, tool_name, expected_sha=text_sha)
        if fails:
            block("ledger invalid — " + " | ".join(fails))

        # Passed: consume the ledger (single use) and log the pass.
        record = {
            "at": datetime.now(timezone.utc).isoformat(),
            "tool": tool_name,
            "fields": [name for name, _ in fields],
            "digest_schema": "synthesis-message-v2",
            "channel": cap["channel"],
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
                % "; ".join("[%s] %r" % (n, s) for n, s in warns)
            )
        sys.exit(0)

    except SystemExit:
        raise
    except Exception as exc:  # ANY unexpected failure blocks. Fail closed.
        block(
            "internal error (%s: %s) — the guard cannot verify this send, "
            "so it does not pass. Run --doctor." % (type(exc).__name__, exc)
        )


# --------------------------------------------------------------------------
# Doctor
# --------------------------------------------------------------------------

POSITIVE_CONTROL_BAD = (
    "I'm sorry for the delay — I went quiet on you, and "
    "I'm the least able to judge this myself."
)
# The clean control is a CANONICAL SIGNED agent message, not generic prose
# (board ask, 2026-08-03): a generic control passed while a retired-branding
# pattern compiled under IGNORECASE blocked every real signed send. The
# doctor's negative control must look like the traffic the guard exists to
# let through — a Slack-wire-form signature line included.
POSITIVE_CONTROL_CLEAN = (
    "Thank you for writing this up properly. The step "
    "list is the valuable part. Send times that suit "
    "you and I will make one of them work.\n\n"
    "🤖 _I'm the principal's <https://ragbot.ai/|Ragbot>, "
    "sent under standing direction — every reply is read_"
)


def _doctor_regular_bytes(path, limit=1024 * 1024):
    """Bound local inspection without following a special node or waiting on it."""
    path = Path(path).absolute()
    if path.resolve() != path:
        raise ValueError("doctor input has an aliased path")
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
            raise ValueError("doctor input is not a bounded regular file")
        raw = bytearray()
        while len(raw) <= limit:
            part = os.read(fd, min(65536, limit + 1 - len(raw)))
            if not part:
                break
            raw.extend(part)
        after = os.fstat(fd)
        named = path.stat(follow_symlinks=False)
        def fields(s):
            return (s.st_dev, s.st_ino, s.st_mode, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        if (len(raw) != before.st_size or len(raw) > limit
                or fields(before) != fields(after) or fields(after) != fields(named)
                or path.resolve() != path):
            raise ValueError("doctor input changed during inspection")
        return bytes(raw)
    finally:
        os.close(fd)


def _doctor_guard_mode(hook):
    """Recognize a direct current-engine invocation, never a name in shell prose."""
    if not isinstance(hook, dict) or hook.get("type", "command") != "command":
        return None
    command = hook.get("command")
    managed = _doctor_managed_mode(command)
    if managed is not None:
        return managed
    if not isinstance(command, str) or any(c in command for c in ";&|`$<>\n\r"):
        return None
    try:
        args = shlex.split(command)
        if not args or not re.fullmatch(r"python(?:3(?:\.[0-9]+)?)?", Path(args[0]).name):
            return None
        interpreter = shutil.which(args.pop(0))
        if not interpreter:
            return None
        while args and args[0] in {"-B", "-I", "-S", "-u"}:
            args.pop(0)
        if len(args) != 2 or args[1] not in {"--gate", "--dispatch"}:
            return None
        engine = Path(args[0])
        if not engine.is_absolute() or engine.name != "message_guard.py":
            return None
        if _doctor_regular_bytes(engine) != _doctor_regular_bytes(Path(__file__).resolve()):
            return None
        return args[1]
    except (OSError, ValueError, TypeError):
        return None


def _doctor_managed_mode(command):
    """Inspect setup-owned route bindings; the runtime owner still verifies execution."""
    import ast

    if not isinstance(command, str):
        return None
    # This exact expression is emitted by the installer. Never evaluate a shell
    # expression or expand arbitrary command text while diagnosing wiring.
    prefix = '"${SYNTHESIS_INSTALL_BIN_DIR:-$HOME/.local/bin}/synthesis"'
    if command.startswith(prefix + " "):
        directory = os.environ.get("SYNTHESIS_INSTALL_BIN_DIR") or str(
            Path.home() / ".local/bin"
        )
        if not Path(directory).is_absolute():
            return None
        command = (
            shlex.quote(str(Path(directory) / "synthesis")) + command[len(prefix) :]
        )
    if any(c in command for c in ";&|`$<>\n\r"):
        return None
    try:
        args = shlex.split(command)
        script = "synthesis-message-guard/scripts/message_guard.py"
        if (
            len(args) != 5
            or args[1:4] != ["exec-public", script, "--"]
            or args[4] not in {"--gate", "--dispatch"}
        ):
            return None
        launcher = Path(args[0])
        if not launcher.is_absolute():
            return None
        pointer = Path(
            os.environ.get("SYNTHESIS_ACTIVE_DESCRIPTOR")
            or str(
                Path(
                    os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))
                )
                / "synthesis/active-release.json"
            )
        )
        raw = _doctor_regular_bytes(pointer)
        active = json.loads(raw)
        if not isinstance(active, dict):
            return None
        receipt = active.get("launcher", {})
        if not isinstance(receipt, dict):
            return None
        if (
            type(active.get("schema_version")) is not int
            or active["schema_version"] != 1
            or type(receipt.get("runtime_schema")) is not int
            or receipt["runtime_schema"] != 1
            or receipt.get("path") != str(launcher)
        ):
            return None
        blob = _doctor_regular_bytes(launcher)
        if (
            hashlib.sha256(blob).hexdigest() != receipt.get("sha256")
            or b"# generated by synthesis-onboarding; managed file"
            not in blob.splitlines()[:2]
            or not os.access(launcher, os.X_OK)
        ):
            return None
        root = Path(active["release_root"])
        if not root.is_absolute() or root.resolve() != root:
            return None
        runtime = _doctor_regular_bytes(
            root / "skills/synthesis-onboarding/scripts/release_runtime.py"
        )
        executable = active["interpreter"]["executable"]
        if not isinstance(executable, str) or not Path(executable).is_absolute():
            return None
        # Read the pinned runtime's literal bootstrap without importing or
        # executing descriptor-selected source. Wiring diagnosis remains a
        # byte comparison; actual execution belongs to the runtime verifier.
        assignments = [
            node
            for node in ast.parse(runtime).body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "SOURCE_IMPORT_CONTRACT"
                for target in node.targets
            )
        ]
        if (
            len(assignments) != 1
            or len(assignments[0].targets) != 1
            or not isinstance(assignments[0].value, ast.Constant)
            or not isinstance(assignments[0].value.value, str)
        ):
            return None
        contract = assignments[0].value.value
        expected = (
            (
                "#!%s -BIS\n# generated by synthesis-onboarding; managed file\n"
                % executable
            ).encode()
            + contract.encode()
            + (
                "\nenable_source_imports(%r)\nimport site\nsite.main()\n"
                % str(pointer.parent)
            ).encode()
            + runtime
            + (
                "\nif __name__ == '__main__':\n    sys.exit(launcher_main(Path(%r), sys.argv[1:]))\n"
                % str(pointer)
            ).encode()
        )
        if blob != expected:
            return None
        target = root / "skills" / script
        if _doctor_regular_bytes(target) != _doctor_regular_bytes(
            Path(__file__).resolve()
        ):
            return None
        if raw != _doctor_regular_bytes(pointer):
            return None
        return args[4]
    except (OSError, ValueError, TypeError, KeyError, RecursionError, SyntaxError):
        return None


def hook_config_covers(path, sample_tools):
    """Verify stored wiring and current engine bytes, not native hook loading."""
    try:
        settings = json.loads(_doctor_regular_bytes(path))
    except (OSError, ValueError, TypeError, RecursionError):
        return False
    if not isinstance(settings, dict) or not isinstance(settings.get("hooks"), dict):
        return False
    entries = settings["hooks"].get("PreToolUse", [])
    if not isinstance(entries, list):
        return False
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("hooks"), list):
            return False
        matcher = entry.get("matcher", "")
        if not isinstance(matcher, str):
            return False
        guard_present = any(_doctor_guard_mode(hook) for hook in entry.get("hooks", []))
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
    print(
        "  python: %s at %s"
        % (".".join(map(str, sys.version_info[:3])), sys.executable)
    )

    try:
        cfg, cblock, cwarn, gated, exempt = load_config()
        report(
            True,
            "config parses",
            "%d block + %d warn patterns, %d gated tool patterns"
            % (len(cblock), len(cwarn), len(gated)),
        )
    except Exception as exc:
        report(False, "config", str(exc))
        print("UNHEALTHY: cannot continue without config.")
        return 2

    if cfg.get("peer_send_resolution"):
        try:
            _peer_board_owner()
            report(True, "canonical peer board parser payload")
        except (OSError, ValueError, ImportError, AttributeError, RuntimeError) as exc:
            report(False, "canonical peer board parser payload", str(exc))

    policy_status = configuration_preflight(cfg, fresh=False)
    report(policy_status["status"] == "READY_FOR_CONFIGURATION_REVIEW",
           "explicit correspondence capability policy",
           policy_status.get("error", "declared scope only; native catalog coverage NOT_ESTABLISHED"))
    if policy_status.get("unsupported_transports"):
        report(True, "unsupported transports remain blocked under selected policy",
               ", ".join(policy_status["unsupported_transports"]))

    hits, _ = scan_text(POSITIVE_CONTROL_BAD, cblock, cwarn)
    report(
        len(hits) >= 2,
        "positive control (known-bad text trips scanner)",
        "%d hits" % len(hits),
    )
    hits2, _ = scan_text(POSITIVE_CONTROL_CLEAN, cblock, cwarn)
    report(
        len(hits2) == 0, "negative control (clean text passes)", "%d hits" % len(hits2)
    )

    # Dead-pattern control (2026-08-07 defect): a pattern authored with
    # surrogate-escape sequences (a "\\ud83e\\uddde"-style pair in place of
    # the real emoji character) compiles to lone surrogates that can never
    # match decoded text, so the rule it encodes is silently OFF while the
    # doctor stays green.
    dead = [
        name
        for name, rx in (cblock + cwarn)
        if any("\ud800" <= ch <= "\udfff" for ch in rx.pattern)
    ]
    report(
        not dead,
        "no dead surrogate-escape patterns",
        ("%d pattern(s) can never match decoded text" % len(dead))
        if dead
        else "all patterns use real characters",
    )

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
        report(
            not failing,
            "config clean controls (canonical real messages pass)",
            "; ".join(failing)
            if failing
            else "%d control(s) pass" % len(clean_controls),
        )
    else:
        report(
            True,
            "config clean controls",
            "none configured — add doctor_clean_controls with your "
            "canonical legitimate messages so a pattern change that "
            "blocks real traffic fails the doctor",
        )

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
    sample_tools += [name for row in cfg.get("message_capabilities", [])
                     if row.get("channel") != "non-correspondence"
                     for name in row.get("tool_names", [])]
    missed = [t for t in sample_tools if not any(rx.search(t) for rx in gated)]
    report(
        not missed,
        "gated patterns cover the send/draft tool family",
        "missed: %s" % ", ".join(missed) if missed else "all covered",
    )
    peer_sample = "mcp__ccd_session_mgmt__send_message"
    peer_cfg = cfg.get("peer_send_resolution")
    if isinstance(peer_cfg, dict):
        try:
            peer_rx = re.compile(peer_cfg.get("tool_pattern") or "")
            report(
                bool(peer_cfg.get("tool_pattern"))
                and bool(peer_rx.search(peer_sample)),
                "peer-session pattern covers inter-session sends",
                peer_cfg.get("tool_pattern", ""),
            )
        except re.error as exc:
            report(False, "peer-session tool pattern compiles", str(exc))
        peer_board = os.path.expanduser(
            peer_cfg.get("board", "~/.synthesis/coordination/active-sessions.md")
        )
        report(
            os.path.isfile(peer_board),
            "coordination board readable for peer resolution",
            peer_board,
        )
    else:
        report(
            any(rx.search(peer_sample) for rx in exempt),
            "inter-session messaging is exempted (peer_send_resolution "
            "not adopted; adopt it to gate peer sends on board "
            "registration)",
        )

    # --- ledger store ---
    # The ledger directory is the concurrency fix's load-bearing surface, so
    # the doctor must be able to see it, not assume it.
    legacy = os.path.join(state_dir(), "ledger.json")
    report(
        not os.path.exists(legacy),
        "no legacy single-slot ledger.json",
        (
            "found %s (%s) — a leftover from the pre-sha layout, usually a "
            "helper script that outlived the convention. It is inert (the gate "
            "reads ledger/<sha>.json); whoever it belongs to should delete it."
            % (legacy, legacy_ledger_detail(legacy))
        )
        if os.path.exists(legacy)
        else "sha-keyed store only",
    )

    d = ledger_dir()
    if os.path.isdir(d):
        names = [n for n in os.listdir(d) if n.endswith(".json")]
        misnamed = [
            n
            for n in names
            if len(n) != 69 or not all(c in "0123456789abcdef" for c in n[:-5].lower())
        ]
        report(
            not misnamed,
            "every ledger filename is a sha256 digest",
            "misnamed: %s — these can never match a send and are dead "
            "weight; --write-ledger cannot produce them, so they were "
            "hand-placed" % ", ".join(sorted(misnamed)[:5])
            if misnamed
            else "%d ledger(s) present" % len(names),
        )
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
        report(
            True,
            "ledger store age",
            "%d of %d past max age (%s min); swept automatically at %dx"
            % (len(stale), len(names), max_age, LEDGER_ORPHAN_SWEEP_MULTIPLE)
            if names
            else "empty (the normal resting state)",
        )
    else:
        report(True, "ledger store", "not yet created (normal before first use)")
    if os.path.isdir(ledger_dir()):
        dmode = os.stat(ledger_dir()).st_mode & 0o777
        loose = [
            n
            for n in os.listdir(ledger_dir())
            if os.path.isfile(os.path.join(ledger_dir(), n))
            and os.stat(os.path.join(ledger_dir(), n)).st_mode & 0o777 != 0o600
        ]
        report(
            dmode == 0o700 and not loose,
            "ledger store is private",
            "dir %o, %d file(s) not 600 — a ledger carries the full "
            "outgoing text and its sources (the next --write-ledger "
            "repairs this)" % (dmode, len(loose))
            if (dmode != 0o700 or loose)
            else "700/600",
        )

    currency_cfg = currency_config(cfg)
    if currency_cfg:
        stale_probe = any(
            rx.search("still unanswered by the recipient")
            for rx in currency_cfg["patterns"]
        )
        report(
            stale_probe,
            "currency-claim freshness lane adopted (unanswered/unsent "
            "claims must carry a fresh read_at)",
            "max age %.0f min" % currency_cfg["max_age"],
        )
    else:
        report(
            True,
            "currency-claim freshness lane not adopted (adopt "
            "currency_claim_patterns + currency_claim_max_age_minutes to gate "
            "unanswered/unsent claims on read freshness)",
            "informational",
        )

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
    client_configs.append(
        (
            "Muse Code",
            "muse",
            "MESSAGE_GUARD_MUSE_SETTINGS",
            os.path.expanduser("~/.config/muse/settings.json"),
        )
    )
    client_coverage = None
    inventory_path = os.environ.get("MESSAGE_GUARD_CLIENT_INVENTORIES")
    if inventory_path:
        try:
            client_coverage = client_capability_check(
                _migration_json(_migration_bytes(Path(inventory_path).absolute())), cfg
            )
        except (OSError, ValueError, TypeError, KeyError) as exc:
            report(False, "complete client capability inventories", str(exc))
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
        gaps = declared_spelling_gaps(cfg)
        report(not gaps, "%s exact client tool spellings resolve" % label,
               ", ".join(gaps) if gaps else "known declared transports; native catalog freshness remains unverified")
        if inventory_path and client_coverage is not None:
            coverage = next((row for row in client_coverage["clients"] if row["client"] == executable), None)
            report(coverage is not None and not coverage["unresolved"],
                   "%s supplied complete catalog capability resolution" % label,
                   json.dumps(coverage) if coverage else "no complete inventory for this active client")
        try:
            wired = hook_config_covers(config_file, sample_tools)
            settings = json.loads(_doctor_regular_bytes(config_file))
            dispatch_wired = any(
                _doctor_guard_mode(hook) == "--dispatch"
                for entry in settings.get("hooks", {}).get("PreToolUse", [])
                for hook in entry.get("hooks", [])
            )
            if dispatch_wired:
                try:
                    registry = validate_capability_registry(cfg.get("_capability_registry"))
                    if registry["capabilities"] != cfg.get("message_capabilities"):
                        raise ValueError("dispatch capabilities differ from enrolled registry")
                    report(True, "%s dispatch registry validates" % label,
                           "stored enrollment only; native inventory freshness NOT_ESTABLISHED")
                except (ValueError, KeyError, TypeError) as exc:
                    report(False, "%s dispatch registry" % label, str(exc))
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
        root = Path(state_dir()).absolute()
        if root.resolve() != root:
            raise ValueError("doctor state has an aliased ancestor")
        root.mkdir(parents=True, mode=0o700, exist_ok=True)
        parent = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        probe_name = ".doctor-probe-" + os.urandom(16).hex()
        probe_fd = None
        try:
            try:
                probe_fd = os.open(probe_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                   0o600, dir_fd=parent)
                if os.write(probe_fd, b"probe") != 5:
                    raise OSError("doctor probe write incomplete")
                os.fsync(probe_fd)
                held = os.fstat(parent)
                named = root.stat()
                if (held.st_dev, held.st_ino) != (named.st_dev, named.st_ino) or root.resolve() != root:
                    raise ValueError("doctor state changed during probe")
            finally:
                if probe_fd is not None:
                    owned = os.fstat(probe_fd)
                    os.close(probe_fd)
                    current = os.stat(probe_name, dir_fd=parent, follow_symlinks=False)
                    if (owned.st_dev, owned.st_ino) != (current.st_dev, current.st_ino):
                        raise ValueError("doctor probe custody changed; foreign path retained")
                    os.unlink(probe_name, dir_fd=parent)
        finally:
            os.close(parent)
        report(True, "state dir writable", state_dir())
    except Exception as exc:
        report(False, "state dir writable", str(exc))

    print(
        "HEALTHY: static guard configuration checks passed; native hook loading and catalog freshness require separate evidence."
        if ok
        else "UNHEALTHY: fix the failures above. The gate FAILS CLOSED, so "
        "sends will be blocked (not unprotected) until this is fixed."
    )
    return 0 if ok else 2


# --------------------------------------------------------------------------
# Test suite
# --------------------------------------------------------------------------


def run_tests():
    import subprocess

    me = os.path.abspath(__file__)
    tmp = str(Path(tempfile.mkdtemp(prefix="msg-guard-test-")).resolve())
    cfg_src = config_path()
    if not os.path.exists(cfg_src):
        # The suite proves the ENGINE, not one machine's private patterns.
        # 2026-09-02: main sat red for hours while every developer machine
        # was green, because CI has no ~/.synthesis and the harness reached
        # for it. Fall back to the skill's example config and say so.
        example = os.path.join(os.path.dirname(me), "..", "patterns.example.json")
        if os.path.exists(example):
            print(
                "config: %s is absent; running against patterns.example.json" % cfg_src
            )
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
            [sys.executable, me, "--gate"],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            env=env,
        )
        return proc.returncode, proc.stderr

    def ledger_for(text, **over):
        base = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "message_sha256": message_digest(slack_tool, {"message": text}),
            "is_reply": True,
            "thread_fully_read": {"how": "gmail fetch", "source_ids": ["19fa..x"]},
            "history_searched": [
                {"query": "from:x subject:y", "where": "gmail", "results": "3 read"}
            ],
            "claims": [
                {"claim": "payrun is Thursday", "source": "gmail 19fa5b0fdcbf4839"}
            ],
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
        print(
            "  %s %s (exit %s, want %s)" % ("ok " if okay else "FAIL", name, got, want)
        )

    print("synthesis-message-guard behavioral tests")

    rc, err = invoke({"tool_name": slack_tool, "tool_input": {"message": clean}})
    check("no ledger -> block", rc, 2)

    rc, _ = invoke(
        {"tool_name": slack_tool, "tool_input": {"message": clean}}, ledger_for(clean)
    )
    check("valid ledger + clean text -> allow", rc, 0)

    rc, err = invoke(
        {
            "tool_name": slack_tool,
            "tool_input": {"message": "Sorry I went quiet on you — " + clean},
        },
        ledger_for("Sorry I went quiet on you — " + clean),
    )
    check("banned register -> block even with valid ledger", rc, 2)

    rc, _ = invoke(
        {"tool_name": slack_tool, "tool_input": {"message": clean}},
        ledger_for(clean + " EDITED AFTER GROUNDING"),
    )
    check("sha mismatch -> block", rc, 2)

    stale = ledger_for(clean)
    stale["created_at"] = "2026-01-01T00:00:00+00:00"
    rc, _ = invoke({"tool_name": slack_tool, "tool_input": {"message": clean}}, stale)
    check("stale ledger -> block", rc, 2)

    noresearch = ledger_for(clean, history_searched=[])
    rc, _ = invoke(
        {"tool_name": slack_tool, "tool_input": {"message": clean}}, noresearch
    )
    check("reply without history search -> block", rc, 2)

    rc, _ = invoke(
        {"tool_name": "mcp__abc__slack_send_message", "tool_input": {"message": clean}},
        ledger_for(clean),
    )
    check("direct slack send without branding check -> block", rc, 2)

    direct = ledger_for(
        clean,
        ragbot_branding_check=True,
        message_sha256=message_digest(
            "mcp__abc__slack_send_message", {"message": clean}
        ),
    )
    rc, _ = invoke(
        {"tool_name": "mcp__abc__slack_send_message", "tool_input": {"message": clean}},
        direct,
    )
    check("direct slack send with branding check -> allow", rc, 0)

    # --- peer-session send lane ---
    # This asserted a bare exemption until peer_send_resolution was adopted;
    # that lane now OWNS the tool and demands a target that resolves on the
    # coordination board. The old assertion outlived the design it described,
    # and it read the LIVE board, so its result moved with unrelated work.
    # Both faults are fixed here: a board fixture, and the adopted contract.
    board = os.path.join(tmp, "active-sessions.md")
    live_ref = "ccd:local_1111aaaa-0000-4000-8000-000000000001"
    parser = _peer_board_owner()
    columns = parser.V6_COLUMNS
    rows = []
    for native, status in ((live_ref, "active"),
            ("ccd:local_1111aaaa-0000-4000-8000-000000000002", "released")):
        row = {key: "synthetic" for key in columns}
        row.update({"client session ref": native, "status": status})
        rows.append("| " + " | ".join(row[key] for key in columns) + " |")
    with open(board, "w", encoding="utf-8") as fh:
        fh.write("Schema: v6\n\n## Active sessions\n\n| " + " | ".join(columns)
                 + " |\n| " + " | ".join("---" for _ in columns) + " |\n"
                 + "\n".join(rows) + "\n\n## Messages\n")
    peer_cfg_path = os.path.join(tmp, "patterns-peer.json")
    with open(cfg_src, "r", encoding="utf-8") as fh:
        peer_cfg = json.load(fh)
    peer_cfg.setdefault(
        "peer_send_resolution",
        {
            "tool_pattern": "mcp__ccd_session_mgmt__send_message$",
            "target_field": "session_id",
        },
    )["board"] = board
    with open(peer_cfg_path, "w", encoding="utf-8") as fh:
        json.dump(peer_cfg, fh)

    def peer_invoke(tool_input, cfg_file=peer_cfg_path):
        penv = dict(env)
        penv["MESSAGE_GUARD_CONFIG"] = cfg_file
        proc = subprocess.run(
            [sys.executable, me, "--gate"],
            input=json.dumps(
                {
                    "tool_name": "mcp__ccd_session_mgmt__send_message",
                    "tool_input": tool_input,
                }
            ),
            capture_output=True,
            text=True,
            env=penv,
        )
        return proc.returncode, proc.stderr

    rc, _ = peer_invoke({"message": "handoff", "session_id": live_ref})
    check("peer send to a board-active ref -> allow", rc, 0)

    rc, err = peer_invoke({"message": "handoff"})
    check("peer send with no target -> block", rc, 2)
    check(
        "...and names the missing field, not a generic failure",
        int("session_id" in err),
        1,
    )

    rc, _ = peer_invoke(
        {"message": "handoff", "session_id": "local_dead-beef-not-on-the-board"}
    )
    check("peer send to an unregistered ref -> block", rc, 2)

    rc, _ = peer_invoke(
        {
            "message": "handoff",
            "session_id": "ccd:local_1111aaaa-0000-4000-8000-000000000002",
        }
    )
    check("peer send to a RELEASED seat -> block", rc, 2)

    missing_board = dict(peer_cfg)
    missing_board["peer_send_resolution"] = dict(
        peer_cfg["peer_send_resolution"], board=os.path.join(tmp, "gone.md")
    )
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

    rc, _ = invoke({"tool_name": slack_tool, "tool_input": {"weird_field": "x"}}, None)
    check("unknown input shape -> block", rc, 2)

    bad_env = dict(env)
    bad_env["MESSAGE_GUARD_CONFIG"] = os.path.join(tmp, "nonexistent.json")
    proc = subprocess.run(
        [sys.executable, me, "--gate"],
        input=json.dumps({"tool_name": slack_tool, "tool_input": {"message": clean}}),
        capture_output=True,
        text=True,
        env=bad_env,
    )
    check("missing config -> block (fail closed)", proc.returncode, 2)

    rc, _ = invoke(
        {"tool_name": slack_tool, "tool_input": {"message": clean}},
        ledger_for(clean, claims=[], no_factual_claims=False),
    )
    check("no claims and no attestation -> block", rc, 2)

    # --- concurrent seats (the reason the ledger is keyed by sha) ---
    # Two seats compose different messages at the same moment. Under the old
    # single ledger.json the second write clobbered the first, and the first
    # seat's send then failed the sha check with "edited after grounding" — a
    # false diagnosis pointing at the wrong repair.
    other = clean + " Second seat's entirely separate message."
    os.makedirs(os.path.join(tmp, "ledger"), exist_ok=True)
    for led in (ledger_for(clean), ledger_for(other)):
        with open(
            os.path.join(tmp, "ledger", led["message_sha256"] + ".json"), "w"
        ) as fh:
            json.dump(led, fh)
    rc, _ = invoke(
        {"tool_name": slack_tool, "tool_input": {"message": clean}}, keep=True
    )
    check("two seats' ledgers coexist -> first seat's message allowed", rc, 0)
    rc, _ = invoke(
        {"tool_name": slack_tool, "tool_input": {"message": other}}, keep=True
    )
    check("two seats' ledgers coexist -> second seat's message allowed", rc, 0)

    # A ledger written for OTHER text must never authorise this send. Under one
    # fixed path this surfaced as a sha mismatch; now the path simply has no
    # ledger, which is the honest diagnosis.
    rc, err = invoke(
        {"tool_name": slack_tool, "tool_input": {"message": clean}}, ledger_for(other)
    )
    check("another message's ledger does not authorise this one -> block", rc, 2)
    check(
        "...and the block says no ledger, not sha mismatch",
        int("no grounding ledger for this exact message" in err),
        1,
    )

    # Consuming one seat's ledger must not consume the other's.
    for led in (ledger_for(clean), ledger_for(other)):
        with open(
            os.path.join(tmp, "ledger", led["message_sha256"] + ".json"), "w"
        ) as fh:
            json.dump(led, fh)
    invoke({"tool_name": slack_tool, "tool_input": {"message": clean}}, keep=True)
    rc, _ = invoke(
        {"tool_name": slack_tool, "tool_input": {"message": other}}, keep=True
    )
    check("consuming one seat's ledger leaves the other's intact", rc, 0)
    rc, _ = invoke(
        {"tool_name": slack_tool, "tool_input": {"message": clean}}, keep=True
    )
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
    check(
        "positive control: one fixed slot loses all but one seat",
        sum(1 for x in texts if message_digest(slack_tool, {"message": x}) == survivor),
        1,
    )

    def stage(text):
        proc = subprocess.run(
            [sys.executable, me, "--write-ledger"],
            input=json.dumps(ledger_for(text)),
            capture_output=True,
            text=True,
            env=env,
        )
        return proc.returncode

    with ThreadPoolExecutor(max_workers=seats) as ex:
        codes = list(ex.map(stage, texts))
    check(
        "N seats stage ledgers concurrently -> all succeed",
        sum(1 for c in codes if c == 0),
        seats,
    )
    check(
        "N seats stage ledgers concurrently -> N distinct files",
        len(
            [n for n in os.listdir(os.path.join(tmp, "ledger")) if n.endswith(".json")]
        ),
        seats,
    )

    def fire(text):
        proc = subprocess.run(
            [sys.executable, me, "--gate"],
            env=env,
            text=True,
            capture_output=True,
            input=json.dumps(
                {"tool_name": slack_tool, "tool_input": {"message": text}}
            ),
        )
        return proc.returncode

    with ThreadPoolExecutor(max_workers=seats) as ex:
        fired = list(ex.map(fire, texts))
    check(
        "N seats send concurrently -> all allowed",
        sum(1 for c in fired if c == 0),
        seats,
    )
    with ThreadPoolExecutor(max_workers=seats) as ex:
        again = list(ex.map(fire, texts))
    check(
        "N seats replay concurrently -> none allowed (single-use holds)",
        sum(1 for c in again if c == 0),
        0,
    )

    # --write-ledger files by the ledger's own sha, so it cannot be misfiled.
    proc = subprocess.run(
        [sys.executable, me, "--write-ledger"],
        input=json.dumps(ledger_for(clean)),
        capture_output=True,
        text=True,
        env=env,
    )
    wrote = proc.stdout.strip()
    check(
        "--write-ledger files at the sha path",
        int(
            wrote.endswith(message_digest(slack_tool, {"message": clean}) + ".json")
            and os.path.exists(wrote)
        ),
        1,
    )

    # A ledger whose sha is not a real digest is refused, never filed.
    proc = subprocess.run(
        [sys.executable, me, "--write-ledger"],
        input=json.dumps(ledger_for(clean, message_sha256="nope")),
        capture_output=True,
        text=True,
        env=env,
    )
    check("--write-ledger refuses a non-digest sha", proc.returncode, 2)

    failures = [r for r in results if not r[0]]
    print("%d/%d passed" % (len(results) - len(failures), len(results)))
    return 2 if failures else 0


# --------------------------------------------------------------------------
# Entry
# --------------------------------------------------------------------------


def read_json_input():
    raw = sys.stdin.read(MAX_MESSAGE_BYTES + 1)
    if len(raw.encode("utf-8")) > MAX_MESSAGE_BYTES:
        raise ValueError("input byte budget exceeded")
    return json.loads(raw)


def program_mode(mode):
    try:
        data = read_json_input()
        if mode in ("--client-capability-plan", "--client-capability-apply", "--client-capability-check"):
            cfg = _migration_json(_migration_bytes(Path(config_path()).absolute()))
            registry_path = os.environ.get("MESSAGE_GUARD_CAPABILITIES")
            if registry_path:
                registry = _migration_json(_migration_bytes(Path(registry_path).absolute()))
                validate_capability_registry(registry)
                cfg["message_capabilities"] = registry["capabilities"]
                cfg["_capability_registry"] = registry
            cfg, *_ = validate_config(cfg)
        else:
            cfg, *_ = load_config()
        if mode == "--message-sha":
            print(message_digest(data["tool_name"], data["tool_input"]))
        elif mode == "--message-ledger-path":
            print(
                ledger_path_for(message_digest(data["tool_name"], data["tool_input"]))
            )
        elif mode == "--build-text":
            print(json.dumps(build_text(data, cfg), ensure_ascii=False))
        elif mode == "--verify-text-readback":
            print(
                json.dumps(
                    verify_text_readback(data["expected"], data["observed"], cfg)
                )
            )
        elif mode == "--build-email":
            print(json.dumps(build_email(data, cfg), ensure_ascii=False))
        elif mode == "--build-mime":
            print(email_mime(data), end="")
        elif mode == "--verify-readback":
            print(
                json.dumps(
                    verify_email_readback(data["expected"], data["raw_mime"], cfg)
                )
            )
        elif mode == "--monitor-email":
            report = monitor_email_records(data, cfg)
            print(json.dumps(report))
            return 2 if report["violations"] else 0
        elif mode == "--client-capability-plan":
            print(json.dumps(client_capability_plan(data, cfg)))
        elif mode == "--client-capability-apply":
            print(json.dumps(client_capability_apply(data, cfg)))
        elif mode == "--client-capability-check":
            result = client_capability_check(data, cfg)
            print(json.dumps(result))
            return 2 if result["status"] == "OWNER_REVIEW_REQUIRED" else 0
        elif mode == "--capability-plan":
            print(json.dumps(capability_plan(data, cfg)))
        elif mode == "--capability-enroll":
            print(json.dumps(capability_enroll(data, cfg)))
        elif mode == "--capability-readiness":
            print(json.dumps(capability_readiness(data, cfg)))
        elif mode == "--capability-check":
            if (
                not isinstance(data, list)
                or not data
                or len(data) > 10000
                or any(not isinstance(x, str) for x in data)
            ):
                raise ValueError("bounded nonempty native tool-name inventory required")
            if len(set(data)) != len(data):
                raise ValueError("duplicate native tool names")
            mapped = [
                {"tool": name, "channel": capability_for(name, cfg)["channel"]}
                for name in data
            ]
            print(
                json.dumps(
                    {
                        "status": "DECLARED_INVENTORY_CLASSIFIED",
                        "native_inventory_provenance_verified": False,
                        "tools": mapped,
                    }
                )
            )
        return 0
    except Exception as exc:
        print("message-guard verification refused: " + str(exc), file=sys.stderr)
        return 2


# Migration is a read-only owner preflight. It grants no message authority and
# never consumes, translates, expires, or deletes a pending grounding ledger.
MIGRATION_MAX_BYTES = 1024 * 1024
MIGRATION_MAX_PENDING = 4096
MIGRATION_MAX_TOTAL = 8 * 1024 * 1024


def _migration_bytes(path, limit=MIGRATION_MAX_BYTES):
    path = Path(path).absolute()
    if path.parent.resolve() != path.parent:
        raise ValueError("migration path has an aliased ancestor")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_uid != os.getuid()
            or before.st_mode & 0o022
            or before.st_size > limit
        ):
            raise ValueError("migration evidence must be bounded owned regular files")
        body = bytearray()
        while len(body) <= limit:
            part = os.read(fd, min(65536, limit + 1 - len(body)))
            if not part:
                break
            body.extend(part)
        if len(body) > limit:
            raise ValueError("migration evidence exceeds byte limit")
        after = os.fstat(fd)
        current = path.lstat()

        def key(st):
            return (
                st.st_dev,
                st.st_ino,
                st.st_mode,
                st.st_uid,
                st.st_nlink,
                st.st_size,
                st.st_mtime_ns,
                st.st_ctime_ns,
            )

        if (
            key(before) != key(after)
            or key(after) != key(current)
            or path.parent.resolve() != path.parent
            or len(body) != after.st_size
        ):
            raise ValueError("migration evidence changed while being read")
        return bytes(body)
    finally:
        os.close(fd)


def _migration_json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate migration JSON key")
            result[key] = value
        return result

    return json.loads(
        raw,
        object_pairs_hook=unique,
        parse_constant=lambda value: (_ for _ in ()).throw(
            ValueError("non-finite migration JSON")
        ),
    )


def _migration_pending(root):
    root = Path(root).absolute()
    if root.resolve() != root:
        raise ValueError("migration state directory has an alias")
    paths = []
    ledger = root / "ledger"
    if os.path.lexists(ledger):
        if ledger.is_symlink() or not ledger.is_dir():
            raise ValueError("pending ledger directory must be a real directory")
        # Bounded enumeration, including non-json residue: no silent omission.
        with os.scandir(ledger) as entries:
            for entry in entries:
                paths.append(Path(entry.path))
                if len(paths) > MIGRATION_MAX_PENDING:
                    raise ValueError("pending ledger count exceeds migration bound")
    if os.path.lexists(root / "ledger.json"):
        paths.append(root / "ledger.json")
    rows = []
    total = 0
    for path in sorted(paths):
        raw = _migration_bytes(path)
        total += len(raw)
        if total > MIGRATION_MAX_TOTAL:
            raise ValueError("pending ledgers exceed migration byte bound")
        rows.append(
            {
                "path": str(path.relative_to(root)),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw),
            }
        )
    return rows


def configuration_preflight(cfg, *, fresh=True):
    """Read-only fresh configuration check; never grants message authority."""
    result = {"schema": 1, "status": "REFUSED", "read_only": True,
              "message_authority_granted": False,
              "native_catalog_coverage": "NOT_ESTABLISHED",
              "provider_drafts": "NOT_INSPECTED"}
    try:
        validate_config(cfg)
        if not cfg.get("message_capabilities"):
            raise ValueError("explicit owner transport capabilities required")
        if set(cfg.get("email_policy", {})) != {
            "default_format", "allow_intra_paragraph_breaks"
        }:
            raise ValueError("explicit owner email policy required")
        unsupported = []
        for row in cfg["message_capabilities"]:
            # Fresh setup has finite exact declarations. Pattern-based migration
            # remains under its existing owner, not this bootstrap interface.
            if fresh and (not row.get("tool_names") or "tool_pattern" in row):
                raise ValueError("fresh setup requires exact declared tool_names")
            for tool in row.get("tool_names", []):
                capability_for(tool, cfg)  # also rejects ambiguous declarations
                if fresh and not any(re.search(p, tool) for p in cfg["gated_tool_patterns"]):
                    raise ValueError("declared tool is not gated: " + tool)
                if fresh and any(re.search(p, tool) for p in cfg["exempt_tool_patterns"]):
                    raise ValueError("declared tool has an exemption: " + tool)
            if fresh and row["channel"] == "non-correspondence":
                raise ValueError("non-correspondence requires complete registry enrollment")
            if row["channel"] == "email":
                if not row.get("body_field") or not (row.get("format_field") or row.get("fixed_format")):
                    raise ValueError("email transport requires explicit body and format mappings")
                if row.get("fixed_format") and row["fixed_format"] != email_policy(cfg)["default_format"]:
                    unsupported.extend(row.get("tool_names", [row.get("tool_pattern")]))
        result["configuration_sha256"] = hashlib.sha256(
            json.dumps(cfg, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        result["unsupported_transports"] = unsupported
        result["status"] = "READY_FOR_CONFIGURATION_REVIEW"
    except (ValueError, TypeError, KeyError, RecursionError, re.error) as exc:
        result["error"] = str(exc)
    return result


def migration_preflight(plan=False):
    """Return exact migration prerequisites, without mutating any live state."""
    result = {
        "schema": 1,
        "status": "REFUSED",
        "policy_gaps": [],
        "read_only": True,
        "native_catalog_coverage": "NOT_ESTABLISHED",
        "provider_drafts": "NOT_INSPECTED",
        "message_authority_granted": False,
    }
    try:
        path = Path(config_path()).absolute()
        root = Path(state_dir()).absolute()
        if not os.path.lexists(path):
            if path.parent.resolve() != path.parent:
                raise ValueError("unconfigured migration path has an aliased ancestor")
            result["status"] = "NOT_CONFIGURED"
            return result
        raw = _migration_bytes(path)
        cfg = _migration_json(raw)
        if not isinstance(cfg, dict):
            raise ValueError("message policy must be an object")
        if (
            not isinstance(cfg.get("message_capabilities"), list)
            or not cfg["message_capabilities"]
        ):
            result["policy_gaps"].append(
                "explicit owner transport capabilities required"
            )
        if not isinstance(cfg.get("email_policy"), dict) or set(
            cfg["email_policy"]
        ) != {"default_format", "allow_intra_paragraph_breaks"}:
            result["policy_gaps"].append("explicit owner email policy required")
        if os.environ.get("MESSAGE_GUARD_CAPABILITIES"):
            # A broad enrolled registry has its own complete catalog/readiness
            # contract. This legacy migration must bind the deployed owner config.
            result["policy_gaps"].append(
                "bind legacy transport declarations in owner config before migration"
            )
        if result["policy_gaps"]:
            return result
        load_config()  # Preserve validation of every existing protective rule.
        policy = email_policy(cfg)
        unsupported = []
        for declaration in cfg["message_capabilities"]:
            if declaration["channel"] != "email":
                continue
            if not declaration.get("body_field") or not (
                declaration.get("format_field") or declaration.get("fixed_format")
            ):
                result["policy_gaps"].append(
                    "email transport requires explicit body and format mappings"
                )
            elif (
                "fixed_format" in declaration
                and declaration["fixed_format"] != policy["default_format"]
            ):
                unsupported.append(
                    {
                        "declaration_sha256": hashlib.sha256(
                            json.dumps(declaration, sort_keys=True).encode()
                        ).hexdigest(),
                        "tools": declaration.get("tool_names", []),
                        "tool_pattern": declaration.get("tool_pattern"),
                        "disposition": "unavailable-under-selected-policy",
                        "reason": "fixed transport cannot satisfy the selected email format",
                    }
                )
        if result["policy_gaps"]:
            return result
        if _migration_bytes(path) != raw:
            raise ValueError("message configuration changed during preflight")
        pending = _migration_pending(root)
        engine_raw = _migration_bytes(Path(__file__))
        expected = {
            "schema": 1,
            "engine_sha256": hashlib.sha256(engine_raw).hexdigest(),
            "config_sha256": hashlib.sha256(raw).hexdigest(),
            "configuration_path": str(path),
            "state_directory": str(root),
            "pending_dispositions": [
                dict(row, disposition="retain-for-regrounding") for row in pending
            ],
            "provider_drafts": "NOT_INSPECTED",
            "unsupported_transports": unsupported,
        }
        result["unsupported_transports"] = unsupported
        result["required_record"] = expected
        result["record_path"] = str(root / "engine-migration.json")
        result["pending_count"] = len(pending)
        if plan:
            result["status"] = "OWNER_REVIEW_REQUIRED"
            return result
        record = _migration_json(_migration_bytes(root / "engine-migration.json"))
        if not isinstance(record, dict) or set(record) != set(expected) | {
            "owner_review"
        }:
            raise ValueError(
                "migration record schema is incomplete or has unknown fields"
            )
        if any(
            json.dumps(record.get(key), sort_keys=True)
            != json.dumps(value, sort_keys=True)
            for key, value in expected.items()
        ):
            raise ValueError(
                "migration record does not bind this engine, policy and retained pending ledgers"
            )
        review = record["owner_review"]
        if (
            not isinstance(review, dict)
            or set(review) != {"source", "reviewed_at"}
            or not isinstance(review["source"], str)
            or not review["source"].strip()
            or len(review["source"]) > 4096
            or not isinstance(review["reviewed_at"], str)
        ):
            raise ValueError("migration record requires an attributed owner review")
        timestamp = datetime.fromisoformat(review["reviewed_at"].replace("Z", "+00:00"))
        if timestamp.tzinfo is None or timestamp > datetime.now(timezone.utc):
            raise ValueError("migration owner review time must be aware and not future")
        if _migration_pending(root) != pending or _migration_bytes(path) != raw:
            raise ValueError("migration custody changed before completion")
        result["status"] = "READY_FOR_OWNER_ACTIVATION"
        result["owner_review_source"] = review["source"]
    except (OSError, ValueError, TypeError, KeyError, RecursionError) as exc:
        result["error"] = str(exc)
    return result


def main():
    args = sys.argv[1:]
    if "--capabilities-file" in args:
        position = args.index("--capabilities-file")
        if position + 1 >= len(args):
            block("capability registry path missing")
        os.environ["MESSAGE_GUARD_CAPABILITIES"] = os.path.expanduser(
            args[position + 1]
        )
        args = args[:position] + args[position + 2 :]
    mode = args[0] if args else "--gate"
    if len(args) > 1:
        block("unexpected command arguments")
    if mode in ("--configuration-preflight", "--policy-preflight"):
        try:
            raw = sys.stdin.buffer.read(1024 * 1024 + 1)
            if len(raw) > 1024 * 1024:
                raise ValueError("configuration exceeds 1 MiB")
            report = configuration_preflight(_migration_json(raw), fresh=mode == "--configuration-preflight")
        except (ValueError, TypeError, RecursionError) as exc:
            report = {"status": "REFUSED", "error": str(exc)}
        print(json.dumps(report, sort_keys=True))
        sys.exit(0 if report["status"] == "READY_FOR_CONFIGURATION_REVIEW" else 2)
    if mode in ("--migration-plan", "--migration-preflight"):
        report = migration_preflight(plan=mode == "--migration-plan")
        print(json.dumps(report, sort_keys=True))
        sys.exit(
            0
            if report["status"]
            in ("NOT_CONFIGURED", "READY_FOR_OWNER_ACTIVATION", "OWNER_REVIEW_REQUIRED")
            else 2
        )
    if mode in (
        "--message-sha",
        "--message-ledger-path",
        "--build-text",
        "--verify-text-readback",
        "--build-email",
        "--build-mime",
        "--verify-readback",
        "--monitor-email",
        "--capability-check",
        "--capability-plan",
        "--client-capability-plan",
        "--client-capability-apply",
        "--client-capability-check",
        "--capability-enroll",
        "--capability-readiness",
    ):
        sys.exit(program_mode(mode))
    elif mode == "--dispatch":
        run_gate(dispatch=True)
    elif mode == "--gate":
        run_gate()
    elif mode == "--sha":
        print(sha256_text(sys.stdin.read()))
    elif mode == "--scan":
        try:
            _, cblock, cwarn, _, _ = load_config()
        except Exception as exc:
            print("config error: %s" % exc, file=sys.stderr)
            sys.exit(2)
        hits, warns = scan_message_text(sys.stdin.read(), cblock, cwarn)
        for n, s in hits:
            print("BLOCK [%s] %r" % (n, s))
        for n, s in warns:
            print("warn  [%s] %r" % (n, s))
        sys.exit(2 if hits else 0)
    elif mode == "--build-ledger":
        try:
            raw = sys.stdin.read(4 * 1024 * 1024 + 1)
            if len(raw.encode("utf-8")) > 4 * 1024 * 1024:
                raise ValueError("grounding envelope input exceeds bound")
            print(json.dumps(build_grounding_envelope(json.loads(raw)), indent=2))
        except (ValueError, TypeError, RecursionError) as exc:
            print("build-ledger: " + str(exc), file=sys.stderr)
            sys.exit(2)
    elif mode == "--ledger-template":
        print(
            json.dumps(
                {
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "message_sha256": "<pipe the complete tool_name/tool_input JSON to --message-sha>",
                    "channel": "<slack|gmail|...>",
                    "recipient": "<who>",
                    "is_reply": True,
                    "thread_fully_read": {"how": "<tool used>", "source_ids": []},
                    "history_searched": [{"query": "", "where": "", "results": ""}],
                    "claims": [
                        {
                            "claim": "",
                            "source": "",
                            "read_at": "<ISO-8601 moment the source was read this run; required for unanswered/unsent/still-open claims>",
                        }
                    ],
                    "no_factual_claims": False,
                    "voice_rules_pass": False,
                    "invented_precision_scan": False,
                    "recipient_address_check": False,
                    "ragbot_branding_check": False,
                },
                indent=2,
            )
        )
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
        if (
            not isinstance(sha, str)
            or len(sha) != 64
            or not all(c in "0123456789abcdef" for c in sha.lower())
        ):
            print(
                "write-ledger: message_sha256 must be a 64-char hex digest of "
                "the complete tool payload (pipe JSON to --message-sha). Got: %r"
                % (sha,),
                file=sys.stderr,
            )
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
        os.replace(tmp, dest)  # atomic; never a half-written ledger
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

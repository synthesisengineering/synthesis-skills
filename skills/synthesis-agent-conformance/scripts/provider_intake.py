#!/usr/bin/env python3
"""Offline provider-change and sanitized incident inputs for conformance review.

No monitoring registration, network request, attribution verdict, account change
or outward publication happens here. The existing project/decision owner retains
all obligations and approval records.
"""

from __future__ import annotations
import argparse
from datetime import datetime
import json
import re
import sys
from urllib.parse import urlsplit

OFFICIAL = {
    "openai": {
        "openai.com",
        "developers.openai.com",
        "platform.openai.com",
        "help.openai.com",
        "status.openai.com",
    },
    "anthropic": {
        "anthropic.com",
        "www.anthropic.com",
        "docs.anthropic.com",
        "code.claude.com",
        "platform.claude.com",
    },
    "meta": {"dev.meta.ai", "www.meta.ai"},
    "github": {"docs.github.com", "github.blog"},
    "cursor": {"cursor.com", "docs.cursor.com"},
}
SURFACES = {
    "plugins",
    "skills",
    "hooks",
    "context",
    "authentication",
    "connectors",
    "subagents",
    "sandbox",
    "computer-use",
    "session-lifecycle",
}
CLASSIFICATIONS = {
    "shared-contract",
    "provider-adapter",
    "capability-boundary",
    "documentation",
    "no-impact",
}
MAX_BYTES = 1024 * 1024


def _shape(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError("intake fields must match the declared contract")


def _sha(value):
    if not isinstance(value, str) or not re.fullmatch("[0-9a-f]{64}", value):
        raise ValueError("exact source SHA-256 is required")


def _bounded(value):
    raw = json.dumps(value, allow_nan=False)
    if len(raw.encode()) > MAX_BYTES:
        raise ValueError("intake exceeds byte bound")


def triage(change):
    _bounded(change)
    _shape(
        change,
        {
            "schema",
            "provider",
            "version",
            "source_url",
            "source_sha256",
            "observed_at",
            "surfaces",
            "classification",
            "evidence",
        },
    )
    if (
        type(change["schema"]) is not int
        or change["schema"] != 1
        or change["provider"] not in OFFICIAL
    ):
        raise ValueError("unsupported provider intake")
    url = urlsplit(change["source_url"])
    if (
        url.scheme != "https"
        or url.hostname not in OFFICIAL[change["provider"]]
        or url.username
        or url.password
        or url.query
        or url.fragment
        or url.port not in (None, 443)
    ):
        raise ValueError("official, credential-free HTTPS source is required")
    _sha(change["source_sha256"])
    try:
        observed = datetime.fromisoformat(change["observed_at"].replace("Z", "+00:00"))
        if observed.tzinfo is None:
            raise ValueError("missing timezone")
    except (ValueError, AttributeError) as exc:
        raise ValueError(
            "observed_at must name a dated timezone-bearing source observation"
        ) from exc
    if not isinstance(change["version"], str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._+-]{0,127}", change["version"]
    ):
        raise ValueError("version must be an exact bounded source label")
    surfaces = change["surfaces"]
    if (
        not isinstance(surfaces, list)
        or any(not isinstance(v, str) for v in surfaces)
        or len(set(surfaces)) != len(surfaces)
        or not set(surfaces) <= SURFACES
    ):
        raise ValueError("surface coverage is unknown or duplicated")
    classification = change["classification"]
    if classification not in CLASSIFICATIONS or (
        classification == "no-impact" and surfaces
    ):
        raise ValueError("classification contradicts declared affected surfaces")
    evidence = change["evidence"]
    if not isinstance(evidence, list) or len(evidence) > 256:
        raise ValueError("evidence references must be bounded")
    seen = set()
    for row in evidence:
        _shape(row, {"client", "plane", "source_sha256", "outcome"})
        if (
            row["client"] not in {"claude", "codex", "muse", "cursor", "copilot"}
            or row["plane"]
            not in {"source", "installed", "native", "continuity", "capability"}
            or row["outcome"] not in {"passed", "failed", "unknown"}
        ):
            raise ValueError("unknown conformance evidence plane")
        _sha(row["source_sha256"])
        key = (row["client"], row["plane"])
        if key in seen:
            raise ValueError("duplicate client/plane observation")
        seen.add(key)
    return {
        "schema": 1,
        "provider": change["provider"],
        "version": change["version"],
        "source_url": change["source_url"],
        "source_sha256": change["source_sha256"],
        "observed_at": change["observed_at"],
        "classification": classification,
        "affected_surfaces": surfaces,
        "targets": ["claude", "codex"],
        "required_evidence_status": "UNKNOWN",
        "evidence_references": evidence,
        "next_owner": "synthesis-agent-conformance",
        "auto_activate": False,
        "scope": "intake structure; observations require independent owner verification",
    }


def incident(request):
    _bounded(request)
    _shape(
        request,
        {
            "schema",
            "provider",
            "client",
            "error_class",
            "reproduction",
            "raw_excerpt",
            "source_sha256",
            "cases",
        },
    )
    if (
        type(request["schema"]) is not int
        or request["schema"] != 1
        or request["provider"]
        not in set(OFFICIAL) | {"synthesis", "environment", "unknown"}
        or request["client"] not in {"claude", "codex", "muse", "cursor", "copilot"}
    ):
        raise ValueError("unknown incident identity")
    if request["error_class"] not in {
        "authentication",
        "unavailable",
        "timeout",
        "integrity",
        "permission",
        "crash",
        "unknown",
    } or request["reproduction"] not in {
        "synthetic-only",
        "source-only",
        "native-observed",
        "unreproduced",
    }:
        raise ValueError("unknown reproduction boundary")
    _sha(request["source_sha256"])
    text = request["raw_excerpt"]
    if not isinstance(text, str) or len(text.encode()) > 65536:
        raise ValueError("excerpt must be bounded text")
    patterns = [
        r"(?im)^(?:authorization|cookie|set-cookie|x-api-key)\s*:.*$",
        r"(?i)\b(?:password|api[_-]?key|token|secret)\s*[=:]\s*\S+",
        r"(?i)\bBearer\s+\S+",
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        r"(?:/Users/|/home/|/private/|[A-Za-z]:\\)[^\s\"\x27]+",
    ]
    counts = []
    for pattern in patterns:
        text, count = re.subn(pattern, "[REDACTED]", text)
        counts.append(count)
    cases = request["cases"]
    if not isinstance(cases, list) or len(cases) > 256:
        raise ValueError("replay cases must be bounded")
    ids = set()
    for case in cases:
        _shape(case, {"id", "expected", "observed"})
        if (
            not isinstance(case["id"], str)
            or not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", case["id"])
            or case["id"] in ids
            or case["expected"] not in {"success", "refusal", "unknown"}
            or case["observed"] not in {"success", "refusal", "unknown"}
        ):
            raise ValueError("invalid or duplicate replay case")
        ids.add(case["id"])
    return {
        "schema": 1,
        "provider_observed": request["provider"],
        "client": request["client"],
        "source_sha256": request["source_sha256"],
        "error_class": request["error_class"],
        "attribution": "unknown",
        "attribution_options": ["openai", "synthesis", "environment", "unknown"],
        "excerpt": text,
        "redactions": sum(counts),
        "replay_scope": request["reproduction"],
        "cases": cases,
        "disclosure_status": "REVIEW_REQUIRED",
        "contact_authorized": False,
        "limitations": [
            "pattern redaction cannot establish complete privacy",
            "an error alone does not identify its cause",
            "case declarations are not execution receipts",
        ],
    }



def _corpus_bytes(value):
    import hashlib
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    if len(raw) > MAX_BYTES:
        raise ValueError("corpus exceeds its finite byte bound")
    return raw, hashlib.sha256(raw).hexdigest()


def prepare_corpus(request, *, source_bytes=None):
    """Prepare a local review candidate, never an anonymization certificate.

    Deterministic reduction catches common identifiers. The required semantic
    dimensions cover contextual identification and cross-case aggregation even
    when no rule matches. Neither synthetic labels nor a zero-match result
    permit outward disclosure. Source IDs are hashed, not silently republished.
    """
    _bounded(request)
    _shape(request, {"schema", "corpus_id", "source_kind", "members"})
    if (type(request["schema"]) is not int or request["schema"] != 1
            or request["source_kind"] not in {"synthetic", "local-original"}
            or not isinstance(request["corpus_id"], str)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", request["corpus_id"])):
        raise ValueError("invalid corpus identity or source kind")
    members = request["members"]
    if not isinstance(members, list) or not 1 <= len(members) <= 64:
        raise ValueError("corpus requires one to 64 bounded members")
    canonical_source, source_digest = _corpus_bytes(request)
    if source_bytes is not None:
        import hashlib
        if not isinstance(source_bytes, bytes) or len(source_bytes) > MAX_BYTES:
            raise ValueError("saved corpus source exceeds byte bound")
        decoded = json.loads(source_bytes, object_pairs_hook=_unique_json,
                             parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite corpus source")))
        if _corpus_bytes(decoded)[0] != canonical_source:
            raise ValueError("saved corpus source does not equal the requested input")
        source_digest = hashlib.sha256(source_bytes).hexdigest()
    candidates, seen = [], set()
    rules = (
        ("credential", r"(?im)(?:authorization|cookie|(?:api[_-]?key|password|token|secret))\s*[:=]\s*[^\n]+"),
        ("credential", r"(?i)\bbearer\s+[A-Za-z0-9._~+/-]+"),
        # Tokenize once. A one-character local suffix before @ prevents the
        # quadratic retry of a long quantified local part. If any old email
        # match exists, its complete maximal ASCII token is conservatively
        # removed, including joined addresses and surrounding token context.
        ("email", r"[A-Za-z0-9._%+@-]+"),
        ("url", r"(?i)\b(?:https?|ssh|git)://[^\s<>]+"),
        ("path", r"(?<![A-Za-z0-9])(?:[A-Za-z]:[\\/]|/)[^\s<>\"]+"),
        ("path", r"(?:~[\\/]|\.\.?/)[^\s<>\"]+"),
        ("network", r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b"),
        ("stable-id", r"(?i)\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"),
        ("handle", r"(?<![A-Za-z0-9])@[A-Za-z0-9_.-]+"),
    )
    for index, member in enumerate(members):
        _shape(member, {"id", "text"})
        if (not isinstance(member["id"], str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", member["id"])
                or member["id"] in seen or not isinstance(member["text"], str)
                or len(member["text"].encode("utf-8")) > 65536):
            raise ValueError("invalid, duplicate or oversized corpus member")
        seen.add(member["id"])
        candidate = member["text"]
        findings = []
        for label, expression in rules:
            if label == "email":
                count = 0
                def redact_email_token(match):
                    nonlocal count
                    token = match.group(0)
                    if re.search(r"[A-Za-z0-9._%+-]@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", token):
                        count += 1
                        return "[redacted-email]"
                    return token
                candidate = re.sub(expression, redact_email_token, candidate)
            else:
                candidate, count = re.subn(expression, "[redacted-" + label + "]", candidate)
            if count:
                findings.append({"dimension": label, "count": count})
        _, member_digest = _corpus_bytes(member)
        _, text_digest = _corpus_bytes(candidate)
        candidates.append({"id": f"case-{index + 1:04d}", "source_sha256": member_digest,
                           "content_sha256": text_digest, "content": candidate,
                           "pattern_findings": findings})
    result = {"schema": 1, "corpus_id": "corpus-" + source_digest[:24],
              "source_kind": request["source_kind"], "source_sha256": source_digest,
              "members": candidates, "disclosure_status": "REVIEW_REQUIRED",
              "publication_authorized": False, "semantic_review_required": True,
              "required_dimensions": ["provenance", "direct-identification", "indirect-identification",
                                      "negative-or-protected-content", "cross-case-aggregation"],
              "limits": "Pattern matches reduce common identifiers; absence of matches proves no privacy property."}
    _corpus_bytes(result)
    return result


def _decision_owner():
    from pathlib import Path
    path = Path(__file__).resolve().parents[2] / "synthesis-decision-packet/scripts"
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
    import build_packet
    import record_rulings
    return build_packet, record_rulings


def corpus_review_packet(request, *, source_bytes=None):
    """Use the existing exact-spec packet owner; this is local review only."""
    candidate = prepare_corpus(request, source_bytes=source_bytes)
    _, digest = _corpus_bytes(candidate)
    packet = {"title": "Compatibility corpus disclosure review", "audience": "The accountable disclosure owner reviewing the complete local candidate.",
              "scope": "Local review only; no publication authorization. Exact source " + candidate["source_sha256"] + "; candidate " + digest + ".",
              "intro": "Review every candidate, all five disclosure dimensions, and their combined identification risk. A clean pattern scan is not evidence of safety. The actual publication owner must separately verify current explicit authority before any outward use.",
              "options": [{"value": "reviewed", "label": "Record this dimension as reviewed", "consequence": "Retain a byte-bound review finding without permitting publication."},
                          {"value": "hold", "label": "Keep this dimension unresolved", "consequence": "Keep the corpus in local review custody."}],
              "rows": []}
    for member in candidate["members"]:
        packet["rows"].append({"id": member["id"], "label": "Inspect " + member["id"],
            "context": member["content"], "reasoning": "Read the entire candidate, including indirect identifiers and context. Patterns do not recognize every private detail.",
            "recommendation": "hold", "impact": {"accept": "Keep this member unresolved until review establishes a defensible disposition.", "decline": "Record that the member was examined; publication still requires the action owner."}})
    for dimension in candidate["required_dimensions"]:
        packet["rows"].append({"id": "dimension-" + dimension, "label": "Assess " + dimension.replace("-", " "),
            "context": "Assess this dimension across every member and the combined corpus, including identifiers retained in otherwise ordinary prose.",
            "reasoning": "This judgment is independent of the number of pattern matches.", "recommendation": "hold",
            "impact": {"accept": "Keep the disclosure boundary unresolved.", "decline": "Record the dimension finding without creating publication permission."}})
    owner, _ = _decision_owner()
    problems = [item for item in owner.validate(packet) if not item.startswith(("NOTE:", "READER:"))]
    if problems:
        raise ValueError("invalid corpus decision packet: " + "; ".join(problems))
    _corpus_bytes(packet)
    return {"candidate": candidate, "candidate_sha256": digest, "spec": packet,
            "spec_sha256": owner.spec_digest(packet), "publication_authorized": False}


def review_corpus(request, summary, provenance, *, source_bytes=None):
    """Re-derive exact current candidate/spec before recording claimed review.

    The packet owner authenticates neither a principal nor their authority.
    Its explicit no-authority result is retained and publication remains closed.
    """
    _shape(provenance, {"principal", "source_ref", "received_at", "scope", "authority_ref"})
    if not all(isinstance(value, str) and 0 < len(value) <= 512 for value in provenance.values()):
        raise ValueError("review requires bounded claimed provenance")
    try:
        when = datetime.fromisoformat(provenance["received_at"].replace("Z", "+00:00"))
        if when.tzinfo is None:
            raise ValueError("missing timezone")
    except ValueError as exc:
        raise ValueError("review provenance needs an explicit timestamp") from exc
    if not isinstance(summary, str) or len(summary.encode("utf-8")) > MAX_BYTES:
        raise ValueError("review summary exceeds bound")
    package = corpus_review_packet(request, source_bytes=source_bytes)
    _, owner = _decision_owner()
    parsed = owner.parse_summary(summary, package["spec"])
    if parsed.get("binding", {}).get("status") != "spec-bound":
        raise ValueError("corpus review needs exact current spec binding")
    complete = all(row.get("choice_value") == "reviewed" for row in parsed["rulings"])
    _, summary_digest = _corpus_bytes(summary)
    return {"schema": 1, "source_sha256": package["candidate"]["source_sha256"],
            "candidate_sha256": package["candidate_sha256"], "spec_sha256": package["spec_sha256"],
            "summary_sha256": summary_digest, "rulings": parsed["rulings"],
            "provenance": {"status": "claimed-unverified", **provenance},
            "disclosure_status": "EXACT_SPEC_REVIEWED" if complete else "REVIEW_REQUIRED",
            "authorization": {"granted": False, "authentication": "unverified", "owner": "existing publication/action owner"},
            "publication_authorized": False,
            "remaining_gate": "The actual action owner must verify current trusted authority for the exact candidate, destination and audience. This record alone cannot authorize publication."}


def require_corpus_publication(request, summary, provenance, *, source_bytes=None):
    """Executable refusal: no generic publication owner is registered here."""
    review_corpus(request, summary, provenance, source_bytes=source_bytes)
    raise ValueError("externally authorized publication requires the actual action owner; exact-spec review is not authority")


def _unique_json(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate intake member before aggregation")
        value[key] = item
    return value


def replay(request):
    """Replay only these two deterministic validators over disclosed fixtures.

    Arbitrary executables, model calls, credentials and provider operations are
    not part of this interface. Its output cannot diagnose a real provider cause.
    """
    import hashlib

    _bounded(request)
    _shape(request, {"schema", "scope", "cases"})
    if (
        type(request["schema"]) is not int
        or request["schema"] != 1
        or request["scope"] != "synthetic-only"
    ):
        raise ValueError("replay accepts only the explicit synthetic contract")
    cases = request["cases"]
    if not isinstance(cases, list) or not 2 <= len(cases) <= 256:
        raise ValueError("replay requires bounded positive and negative controls")
    seen = set()
    expected = set()
    out = []
    for row in cases:
        _shape(row, {"id", "operation", "input", "expected"})
        if (
            not isinstance(row["id"], str)
            or not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", row["id"])
            or row["id"] in seen
            or row["operation"] not in {"change", "incident"}
            or row["expected"] not in {"accepted", "refused"}
        ):
            raise ValueError("replay case identity, operation or expectation invalid")
        seen.add(row["id"])
        expected.add(row["expected"])
        raw = json.dumps(
            row["input"], sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
        try:
            result = (triage if row["operation"] == "change" else incident)(
                row["input"]
            )
            status = "accepted"
            output_sha256 = hashlib.sha256(
                json.dumps(result, sort_keys=True, allow_nan=False).encode()
            ).hexdigest()
        except (ValueError, TypeError, KeyError, AttributeError, RecursionError):
            status = "refused"
            output_sha256 = None
        out.append(
            {
                "id": row["id"],
                "input_sha256": hashlib.sha256(raw).hexdigest(),
                "observed": status,
                "expected": row["expected"],
                "output_sha256": output_sha256,
            }
        )
    if expected != {"accepted", "refused"}:
        raise ValueError("replay must retain both positive and negative cases")
    return {
        "status": "REPLAYED_SYNTHETIC_CONTROLS"
        if all(row["expected"] == row["observed"] for row in out)
        else "CONTROL_MISMATCH",
        "results": out,
        "provider_cause": "UNRESOLVED",
        "native_execution": False,
        "contact_authorized": False,
        "disclosure_review": "REQUIRED",
    }


def main(argv=None):
    p = argparse.ArgumentParser(allow_abbrev=False)
    p.add_argument("mode", choices=("change", "incident", "replay", "corpus-prepare", "corpus-packet", "corpus-review", "corpus-publish"))
    p.add_argument("--doctor", action="store_true")
    p.add_argument("--corpus-source", help="Current saved corpus source; exact bytes bind review rather than canonical JSON alone")
    args = p.parse_args(argv)
    try:
        raw = sys.stdin.read(MAX_BYTES + 1)
        if len(raw.encode()) > MAX_BYTES:
            raise ValueError("intake exceeds byte bound")
        request = json.loads(raw, object_pairs_hook=_unique_json,
                             parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))
        source_bytes = None
        if args.corpus_source:
            if not args.mode.startswith("corpus-"):
                raise ValueError("saved corpus input requires a corpus command")
            from signed_receipt import read_regular
            source_bytes = read_regular(args.corpus_source, limit=MAX_BYTES)
        if args.mode in {"corpus-review", "corpus-publish"}:
            _shape(request, {"request", "summary", "provenance"})
            consumer = review_corpus if args.mode == "corpus-review" else require_corpus_publication
            result = consumer(request["request"], request["summary"], request["provenance"], source_bytes=source_bytes)
        elif args.mode in {"corpus-prepare", "corpus-packet"}:
            result = (prepare_corpus if args.mode == "corpus-prepare" else corpus_review_packet)(request, source_bytes=source_bytes)
        else:
            result = {"change": triage, "incident": incident, "replay": replay}[args.mode](request)
        if source_bytes is not None and read_regular(args.corpus_source, limit=MAX_BYTES) != source_bytes:
            raise ValueError("saved corpus changed during review")
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError) as exc:
        print(json.dumps({"status": "REFUSED", "reason": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

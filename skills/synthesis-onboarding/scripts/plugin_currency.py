#!/usr/bin/env python3
"""Release-channel and installed-plugin currency helpers.

The public repository exposes three lifecycle targets:

* ``stable`` branch — default, release-gated channel;
* ``main`` branch — opt-in edge channel;
* ``vX.Y.Z`` tags — immutable organization pins.

SessionStart and the onboarding doctor share this module so they cannot drift
on policy parsing, target discovery, or version comparison. Network discovery
is cached. An unavailable target remains explicitly unverifiable; it is never
silently treated as current.
"""

from __future__ import annotations

import json
import os
import re
import ssl
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


CHANNEL_REFS = {"stable": "stable", "edge": "main"}
DEFAULT_CHANNEL = "stable"
DEFAULT_TTL_SECONDS = 6 * 60 * 60
RAW_MANIFEST_TEMPLATE = (
    "https://raw.githubusercontent.com/synthesisengineering/"
    "synthesis-skills/{ref}/.codex-plugin/plugin.json"
)
VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
SYSTEM_CA_FILES = (
    "/etc/ssl/cert.pem",  # macOS and several BSDs
    "/etc/ssl/certs/ca-certificates.crt",  # Debian, Ubuntu, and WSL
    "/etc/pki/tls/certs/ca-bundle.crt",  # Fedora and RHEL
    "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem",
    "/etc/ssl/ca-bundle.pem",  # openSUSE
)


def normalize_policy(channel=None, version_pin=None):
    """Return a validated policy dictionary."""
    channel = channel or DEFAULT_CHANNEL
    if channel not in CHANNEL_REFS:
        raise ValueError("release channel must be stable or edge")
    if version_pin is not None:
        version_pin = str(version_pin).strip()
        if not VERSION_RE.fullmatch(version_pin):
            raise ValueError("version_pin must be an exact X.Y.Z version")
    return {"channel": channel, "version_pin": version_pin}


def policy_from_manifest(manifest, channel_override=None):
    ecosystem = (manifest or {}).get("ecosystem") or {}
    return normalize_policy(
        channel_override or ecosystem.get("channel"),
        ecosystem.get("version_pin"),
    )


def policy_ref(policy):
    normalized = normalize_policy(
        policy.get("channel"), policy.get("version_pin")
    )
    if normalized["version_pin"]:
        return "v%s" % normalized["version_pin"]
    return CHANNEL_REFS[normalized["channel"]]


def policy_label(policy):
    normalized = normalize_policy(
        policy.get("channel"), policy.get("version_pin")
    )
    if normalized["version_pin"]:
        return "pinned release %s" % normalized["version_pin"]
    return "%s channel" % normalized["channel"]


def version_tuple(version):
    if not isinstance(version, str) or not VERSION_RE.fullmatch(version):
        return None
    return tuple(int(part) for part in version.split("."))


def compare_versions(installed, target):
    """Return behind/current/ahead, or unverifiable for invalid versions."""
    installed_parts = version_tuple(installed)
    target_parts = version_tuple(target)
    if installed_parts is None or target_parts is None:
        return "unverifiable"
    if installed_parts < target_parts:
        return "behind"
    if installed_parts > target_parts:
        return "ahead"
    return "current"


def default_cache_path():
    state_dir = Path(
        os.environ.get(
            "SYNTHESIS_ONBOARD_STATE_DIR",
            str(Path.home() / ".synthesis" / "onboarding"),
        )
    )
    return state_dir / "plugin-currency.json"


def _read_cache(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"version": 1, "targets": {}}
    if not isinstance(data, dict) or not isinstance(data.get("targets"), dict):
        return {"version": 1, "targets": {}}
    return data


def _write_cache(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=path.name + ".",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_name = temporary.name
            temporary.write(json.dumps(data, indent=2, sort_keys=True) + "\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, path)
    finally:
        if temporary_name and os.path.exists(temporary_name):
            os.unlink(temporary_name)


def _certificate_verification_failed(exc):
    """Recognize verification failures even when urllib wraps the SSL error."""
    seen = set()
    current = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, ssl.SSLCertVerificationError):
            return True
        reason = getattr(current, "reason", None)
        if reason is not None and reason is not current:
            current = reason
            continue
        current = getattr(current, "__cause__", None)
    return "CERTIFICATE_VERIFY_FAILED" in str(exc)


def _candidate_ca_files():
    """Return existing platform CA bundles not already resolved by OpenSSL.

    Python.org's macOS runtime can have no resolved OpenSSL CA path even while
    the operating system ships ``/etc/ssl/cert.pem``. Linux distributions use
    a small set of other conventional bundle locations. Passing any candidate
    to ``ssl.create_default_context`` keeps chain and hostname verification
    enabled; this function never manufactures or downloads a trust root.
    """
    defaults = ssl.get_default_verify_paths()
    candidates = [defaults.cafile, *SYSTEM_CA_FILES]
    resolved = []
    seen = set()
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        try:
            identity = str(path.resolve())
        except OSError:
            identity = str(path)
        if identity in seen or not path.is_file():
            continue
        seen.add(identity)
        resolved.append(path)
    return resolved


def _verified_urlopen(url, timeout):
    """Open HTTPS with verified TLS across stock Python distributions.

    The default urllib path remains first. Only a certificate-verification
    failure triggers retries with an existing operating-system CA bundle.
    Network, HTTP, decoding, and other TLS failures remain failures instead of
    being masked by a second transport.
    """
    try:
        return urllib.request.urlopen(url, timeout=timeout)
    except (OSError, urllib.error.URLError) as first_error:
        if not _certificate_verification_failed(first_error):
            raise

    attempts = []
    for ca_file in _candidate_ca_files():
        try:
            context = ssl.create_default_context(cafile=str(ca_file))
            return urllib.request.urlopen(url, timeout=timeout, context=context)
        except (OSError, urllib.error.URLError) as retry_error:
            attempts.append("%s: %s" % (ca_file, retry_error))
    detail = "; ".join(attempts) or "no operating-system CA bundle found"
    raise urllib.error.URLError(
        "certificate verification failed with default trust; %s" % detail
    )


def resolve_target_version(
    policy,
    cache_path=None,
    ttl_seconds=DEFAULT_TTL_SECONDS,
    timeout=2,
    opener=None,
    now=None,
):
    """Resolve the desired plugin version, using fresh or stale cache evidence.

    Returns ``(version, detail)``. A stale cached version is usable evidence and
    is labeled as such. With neither live nor cached evidence, version is None.
    """
    ref = policy_ref(policy)
    cache_path = Path(cache_path or default_cache_path())
    cache = _read_cache(cache_path)
    cached = cache["targets"].get(ref) or {}
    now = time.time() if now is None else now
    cached_version = cached.get("version")
    checked_at = cached.get("checked_at")
    if (
        version_tuple(cached_version) is not None
        and isinstance(checked_at, (int, float))
        and 0 <= now - checked_at <= ttl_seconds
    ):
        return cached_version, "cached %s ref (fresh)" % ref

    url = RAW_MANIFEST_TEMPLATE.format(ref=ref)
    try:
        response = (opener or _verified_urlopen)(url, timeout=timeout)
        try:
            payload = json.loads(response.read().decode("utf-8"))
        finally:
            close = getattr(response, "close", None)
            if close:
                close()
        version = str(payload.get("version") or "")
        if version_tuple(version) is None:
            raise ValueError("release manifest has no exact X.Y.Z version")
        cache["targets"][ref] = {"version": version, "checked_at": now}
        try:
            _write_cache(cache_path, cache)
        except OSError:
            pass
        return version, "live %s ref" % ref
    except (OSError, UnicodeError, ValueError, urllib.error.URLError) as exc:
        if version_tuple(cached_version) is not None:
            return cached_version, "cached %s ref (stale; live check failed)" % ref
        return None, "%s ref unavailable: %s" % (ref, str(exc))


def read_persisted_policy(receipts_path=None):
    path = Path(
        receipts_path
        or os.environ.get(
            "SYNTHESIS_ONBOARD_RECEIPTS",
            str(
                Path(
                    os.environ.get(
                        "SYNTHESIS_ONBOARD_STATE_DIR",
                        str(Path.home() / ".synthesis" / "onboarding"),
                    )
                )
                / "receipts.json"
            ),
        )
    )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        policy = data.get("plugin_policy") or {}
        return normalize_policy(policy.get("channel"), policy.get("version_pin"))
    except (OSError, ValueError, AttributeError):
        return normalize_policy()


def installed_version_from_root(plugin_root):
    versions = []
    root = Path(plugin_root)
    for relative in (".claude-plugin/plugin.json", ".codex-plugin/plugin.json"):
        try:
            payload = json.loads((root / relative).read_text(encoding="utf-8"))
            version = str(payload.get("version") or "")
            if version_tuple(version) is not None:
                versions.append(version)
        except (OSError, ValueError, AttributeError):
            continue
    return versions[0] if versions and len(set(versions)) == 1 else None


def sessionstart_notice(plugin_root, receipts_path=None, resolver=resolve_target_version):
    """Return a truthful one-line lifecycle notice for an executing cache."""
    installed = installed_version_from_root(plugin_root)
    if installed is None:
        return ""
    policy = read_persisted_policy(receipts_path)
    target, detail = resolver(policy)
    label = policy_label(policy)
    if target is None:
        return (
            "Synthesis plugin currency: installed %s; %s could not be verified (%s)."
            % (installed, label, detail)
        )
    status = compare_versions(installed, target)
    if status == "current":
        return ""
    if status == "behind":
        return (
            "Synthesis update available: installed plugin %s; %s is %s. "
            "Run the synthesis-onboarding update flow as this session's last action."
            % (installed, label, target)
        )
    return (
        "Synthesis plugin policy mismatch: installed %s; %s resolves to %s. "
        "Run the synthesis-onboarding update flow as this session's last action."
        % (installed, label, target)
    )

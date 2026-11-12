"""Every setting from the environment, checked together so one start reports every problem.

references/connector.md documents each variable. A required value that is missing or malformed
stops the start (ConfigError lists them all); nothing falls back to serving without sign-in.
KB_OPERATOR_TEST=1 with KB_OPERATOR_ADDRESSES is the operator-only test mode: nobody else signs in.
"""

from __future__ import annotations

import re
import string
from dataclasses import dataclass
from urllib.parse import urlparse

from .access import listed

STORES = ("memory", "firestore")
URL_FIELDS = ("id", "source_path", "commit")
FERNET_KEY = re.compile(r"[A-Za-z0-9_-]{43}=")


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Settings:
    git_url: str
    git_branch: str
    ssh_key_file: str
    known_hosts: str
    source_dir: str
    references_path: str
    work_dir: str
    refresh_seconds: int
    public_url: str
    google_client_id: str
    google_client_secret: str
    jwt_signing_key: str
    allowed_emails: str
    allowed_hosted_domains: str
    allowed_groups: str
    operator_addresses: str
    group_refresh_seconds: int
    allowed_redirect_uris: tuple
    oauth_store: str
    firestore_project: str
    firestore_database: str
    firestore_prefix: str
    storage_key: str
    token_cache_seconds: int
    server_name: str
    document_url: str
    search_limit: int
    host: str
    port: int
    log_level: str


def _int(env, name, default, low, high, problems):
    raw = (env.get(name) or "").strip()
    if not raw:
        return default
    if not re.fullmatch(r"\d+", raw) or not low <= int(raw) <= high:
        problems.append(f"{name} must be a whole number from {low} to {high}, not {raw!r}")
        return default
    return int(raw)


def load(env) -> Settings:
    get = lambda name, default="": (env.get(name) or default).strip()  # noqa: E731
    problems = []
    git_url, source_dir = get("KB_GIT_URL"), get("KB_SOURCE_DIR")
    if bool(git_url) == bool(source_dir):
        problems.append("set exactly one of KB_GIT_URL (the published repository) and KB_SOURCE_DIR (a local folder)")
    public_url = get("KB_PUBLIC_URL").rstrip("/")
    parsed = urlparse(public_url)
    local = parsed.hostname in ("localhost", "127.0.0.1", "::1")
    if parsed.scheme not in ("https", "http") or not parsed.hostname or (parsed.scheme == "http" and not local):
        problems.append("KB_PUBLIC_URL must be the service's https:// address (http:// only for localhost)")
    test, operators = get("KB_OPERATOR_TEST"), get("KB_OPERATOR_ADDRESSES")
    if test not in ("", "0", "1") or (test == "1") != bool(listed(operators)):
        problems.append("the operator-only test mode needs both KB_OPERATOR_TEST=1 and KB_OPERATOR_ADDRESSES, the "
                        "operator's own email address or addresses: set both, or neither")
    for name in ("KB_GOOGLE_CLIENT_ID", "KB_GOOGLE_CLIENT_SECRET"):
        if not get(name):
            problems.append(f"{name} is required")
    if not get("KB_ALLOWED_EMAILS") and not get("KB_ALLOWED_GROUPS"):
        problems.append("KB_ALLOWED_EMAILS or KB_ALLOWED_GROUPS is required (either or both)")
    store = get("KB_OAUTH_STORE", "memory").lower()
    if store not in STORES:
        problems.append(f"KB_OAUTH_STORE must be one of {', '.join(STORES)}, not {store!r}")
    storage_key = get("KB_STORAGE_ENCRYPTION_KEY")
    if store == "firestore" and not FERNET_KEY.fullmatch(storage_key):
        problems.append("KB_OAUTH_STORE=firestore needs KB_STORAGE_ENCRYPTION_KEY, a Fernet key (44 characters)")
    settings = Settings(
        git_url=git_url, git_branch=get("KB_GIT_BRANCH"), ssh_key_file=get("KB_GIT_SSH_KEY_FILE"),
        known_hosts=(env.get("KB_GIT_KNOWN_HOSTS") or "").strip(), source_dir=source_dir,
        references_path=get("KB_REFERENCES_PATH"), work_dir=get("KB_WORK_DIR"),
        refresh_seconds=_int(env, "KB_REFRESH_SECONDS", 600, 0, 86400, problems), public_url=public_url,
        google_client_id=get("KB_GOOGLE_CLIENT_ID"), google_client_secret=get("KB_GOOGLE_CLIENT_SECRET"),
        jwt_signing_key=get("KB_JWT_SIGNING_KEY"), allowed_emails=get("KB_ALLOWED_EMAILS"),
        allowed_hosted_domains=get("KB_ALLOWED_HOSTED_DOMAINS"), allowed_groups=get("KB_ALLOWED_GROUPS"),
        operator_addresses=operators,
        group_refresh_seconds=_int(env, "KB_GROUP_REFRESH_SECONDS", 300, 60, 86400, problems),
        allowed_redirect_uris=tuple(u.strip() for u in get("KB_ALLOWED_REDIRECT_URIS").split(",") if u.strip()),
        oauth_store=store, firestore_project=get("KB_FIRESTORE_PROJECT"), firestore_database=get("KB_FIRESTORE_DATABASE"),
        firestore_prefix=get("KB_FIRESTORE_COLLECTION_PREFIX", "kb-connector"), storage_key=storage_key,
        token_cache_seconds=_int(env, "KB_TOKEN_CACHE_SECONDS", 300, 0, 3600, problems),
        server_name=get("KB_SERVER_NAME", "Knowledge base"), document_url=get("KB_DOCUMENT_URL_TEMPLATE", "kb:{id}"),
        search_limit=_int(env, "KB_SEARCH_LIMIT", 10, 1, 50, problems), host=get("KB_HOST", "0.0.0.0"),
        port=_int(env, "PORT", 8080, 1, 65535, problems), log_level=get("KB_LOG_LEVEL", "INFO").upper())
    try:
        fields = {name for _, name, _, _ in string.Formatter().parse(settings.document_url) if name is not None}
    except ValueError:
        fields = {"?"}
    if not fields & {"id", "source_path"} or fields - set(URL_FIELDS):
        problems.append("KB_DOCUMENT_URL_TEMPLATE may use only {" + "}, {".join(URL_FIELDS) + "} and needs {id} or "
                        "{source_path}")
    for name, value in (("KB_ALLOWED_EMAILS", settings.allowed_emails), ("KB_ALLOWED_GROUPS", settings.allowed_groups),
                        ("KB_OPERATOR_ADDRESSES", settings.operator_addresses)):
        if value and any(e.count("@") != 1 for e in listed(value)):
            problems.append(f"{name} must be comma-separated email addresses")
    if problems:
        raise ConfigError("the connector cannot start:\n  - " + "\n  - ".join(problems))
    return settings

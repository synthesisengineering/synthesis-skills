"""Every setting from the environment, checked together so one start reports every problem.

references/connector.md documents each variable. A required value that is missing or malformed
stops the start (ConfigError lists them all); nothing falls back to serving without sign-in.
KB_PUBLIC_URL is an origin and nothing more. KB_OPERATOR_TEST=1 with KB_OPERATOR_ADDRESSES is the
operator-only test mode: nobody else signs in, and a temporary address (temporary() below) or the
memory sign-in store starts in that mode alone.
"""

from __future__ import annotations

import ipaddress
import re
import string
from dataclasses import dataclass
from urllib.parse import urlsplit

from .access import listed

STORES = ("memory", "firestore")
# Hosts that last only as long as one machine or its tunnel: the tunnel services' own domains, and names only a
# machine or its own network knows. A tunnel service that is not listed is not caught: add its domain here.
TEMPORARY_HOSTS = ("trycloudflare.com", "ngrok.io", "ngrok.app", "ngrok.dev", "ngrok.pizza", "ngrok-free.app",
                   "ngrok-free.dev", "ngrok-free.pizza", "loca.lt", "localtunnel.me", "serveo.net",
                   "serveousercontent.com", "localhost.run", "lhr.life", "lhr.rocks", "pinggy.io", "pinggy.link",
                   "pinggy-free.link", "devtunnels.ms", "app.github.dev", "localhost", "local")
ORIGIN_PARTS = ("a user-info part (user:password@)", "a path", "a query", "a fragment")  # what KB_PUBLIC_URL may not have
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


def temporary(host) -> bool:
    """True for an address that lasts only as long as one machine or its tunnel: a host in TEMPORARY_HOSTS or under
    one, or an IP address the internet cannot reach. Read as a host: a look-alike or a name in a path does not count."""
    host = (host or "").lower().rstrip(".")
    if any(host == name or host.endswith("." + name) for name in TEMPORARY_HOSTS):
        return True
    try:
        return not ipaddress.ip_address(host).is_global
    except ValueError:  # a name, unless its last label is a number: an IP address in an old spelling, such as 127.1
        return bool(re.fullmatch(r"\d+|0x[0-9a-f]*", host.rsplit(".", 1)[-1]))


def _beyond_origin(raw, parsed, port, local) -> str:
    """Why KB_PUBLIC_URL is more than an origin (the scheme, the host and a port), or "" when it is one or no address at
    all. It names each part it found and shows the origin alone; it never shows a part, since a user-info part or a
    query can carry a secret and the message is printed."""
    more = [part for part, found in zip(ORIGIN_PARTS, ("@" in parsed.netloc, parsed.path not in ("", "/"),
                                                       "?" in raw.split("#")[0], "#" in raw)) if found]
    if not more or parsed.scheme not in ("https", "http") or not parsed.hostname or port == 0:
        return ""
    host = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
    origin = f"{'http' if parsed.scheme == 'http' and local else 'https'}://{host}" + (f":{port}" if port else "")
    return ("KB_PUBLIC_URL must be an origin and nothing more: the scheme, the host and a port if it needs one, since "
            f"the connector builds its own addresses (/mcp, /auth/callback) on it. It has {', '.join(more[:-1])}"
            f"{' and ' if more[1:] else ''}{more[-1]}, which {'are' if more[1:] else 'is'} not allowed. Write it as {origin}")


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
    raw = get("KB_PUBLIC_URL")
    public_url, parsed = raw.rstrip("/"), urlsplit(raw)
    try:
        port = parsed.port
    except ValueError:
        port = 0  # not a port, so not an address
    local = parsed.hostname in ("localhost", "127.0.0.1", "::1")
    if (parsed.scheme not in ("https", "http") or not parsed.hostname or port == 0
            or (parsed.scheme == "http" and not local)):
        problems.append("KB_PUBLIC_URL must be the service's https:// address (http:// only for localhost)")
    if beyond := _beyond_origin(raw, parsed, port, local):
        problems.append(beyond)
    test, operators = get("KB_OPERATOR_TEST"), get("KB_OPERATOR_ADDRESSES")
    if test not in ("", "0", "1") or (test == "1") != bool(listed(operators)):
        problems.append("the operator-only test mode needs both KB_OPERATOR_TEST=1 and KB_OPERATOR_ADDRESSES, the "
                        "operator's own email address or addresses: set both, or neither")
    if len(listed(operators)) > 3:
        problems.append(f"KB_OPERATOR_ADDRESSES names {len(listed(operators))} addresses and may name three at most: "
                        "they are one person's own accounts, since the operator-only test mode is that person's test "
                        "and nobody else's. Other people come in through KB_ALLOWED_EMAILS or KB_ALLOWED_GROUPS, on a "
                        "deployed connector with the mode off")
    if temporary(parsed.hostname) and test != "1":
        problems.append(f"KB_PUBLIC_URL names a temporary or local address ({parsed.hostname}): it lasts only while "
                        "this machine and its tunnel stay up, so nobody else may depend on it. To serve other people, "
                        "deploy the connector to the organization's own infrastructure at a permanent address; for "
                        "the operator's own test, set KB_OPERATOR_TEST=1 and KB_OPERATOR_ADDRESSES to the operator's "
                        "own email address")
    for name in ("KB_GOOGLE_CLIENT_ID", "KB_GOOGLE_CLIENT_SECRET"):
        if not get(name):
            problems.append(f"{name} is required")
    if not get("KB_ALLOWED_EMAILS") and not get("KB_ALLOWED_GROUPS"):
        problems.append("KB_ALLOWED_EMAILS or KB_ALLOWED_GROUPS is required (either or both)")
    store = get("KB_OAUTH_STORE", "memory" if test == "1" else "").lower()
    if store in ("", "memory") and test != "1":
        problems.append("KB_OAUTH_STORE must be firestore, with KB_STORAGE_ENCRYPTION_KEY: anything other people use must "
                        "keep its state across restarts, and with more than one instance a memory store breaks sign-in "
                        "outright. A single person's use is what the operator-only test mode is for, and memory is "
                        "allowed only there, with KB_OPERATOR_TEST=1")
    elif store not in STORES:
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
    if settings.log_level not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        problems.append(f"KB_LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR or CRITICAL, not {settings.log_level!r}")
    if problems:
        raise ConfigError("the connector cannot start:\n  - " + "\n  - ".join(problems))
    return settings

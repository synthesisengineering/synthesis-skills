"""The MCP server: read-only search and fetch, Google sign-in, and the access list everywhere.

Written against fastmcp 4.1.6, pinned in requirements.txt. The access list is applied three times:
at sign-in (the Google callback is wrapped, so a person not on the list sees a page saying why and
no grant reaches their client), to every token on every request (load_access_token, which FastMCP's
bearer middleware calls, so a person removed from the list loses access at once), and to every tool
call and tool listing (AuthMiddleware). The sign-in check reads the OAuth proxy's stored grant
through two private attributes, `_code_store` and `_token_validator`; if a FastMCP upgrade moves
them, the check fails closed and the tests in tests/test_kb_connector_server.py fail. In the
operator-only test mode all three admit the operator alone, the token endpoint refuses a refresh to
anyone else (exchange_refresh_token, which the SDK's token handler calls for a refresh grant), main()
logs a line that begins TEST ONLY and /health reports `test_only`.

Tokens are never logged: log lines name the email address and the reason only, and the access log
is off, since the callback's query string carries Google's authorization code.
"""

from __future__ import annotations

import logging
import os
import sys
import tempfile
from typing import Any, TypedDict
from urllib.parse import parse_qs, quote, urlparse

from fastmcp import FastMCP
from fastmcp.exceptions import AuthorizationError, ToolError
from fastmcp.server.auth.oauth_proxy.ui import create_error_html
from fastmcp.server.auth.providers.google import GoogleProvider
from fastmcp.server.middleware import AuthMiddleware
from mcp.server.auth.provider import TokenError
from mcp_types import ToolAnnotations
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.routing import Route

from . import config
from .access import AccessPolicy, Decision, listed
from .groups import GroupRoster
from .source import DirectorySource, GitSource, Library, SourceError

LOG = logging.getLogger("kb_connector")
CALLBACK = "/auth/callback"
GOOGLE_SCOPES = ["openid", "https://www.googleapis.com/auth/userinfo.email"]
READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)
UNCHECKED = Decision(False, "check_failed", "", "Access denied: this sign-in could not be checked against the "
                     "access list. Try again; if it keeps happening, tell the knowledge base's administrator.")


class SearchResult(TypedDict):
    id: str
    title: str
    url: str
    snippet: str


class SearchResults(TypedDict):
    results: list[SearchResult]


class FetchedDocument(TypedDict):
    id: str
    title: str
    text: str
    url: str
    metadata: dict[str, Any]


class AccessListGoogleProvider(GoogleProvider):
    """FastMCP's Google OAuth proxy with the access list at sign-in, on every token and, in the test mode, on a refresh."""

    def __init__(self, *, policy: AccessPolicy, **kwargs):
        super().__init__(redirect_path=CALLBACK, **kwargs)
        self.policy = policy

    async def load_access_token(self, token: str):
        access = await super().load_access_token(token)
        if access is None:
            return None
        decision = self.policy.decide(access.claims)
        if not decision.allowed:
            LOG.warning("token refused for %s: %s", decision.email or "(no address)", decision.reason)
            return None
        return access

    async def exchange_refresh_token(self, client, refresh_token, scopes):
        """FastMCP's refresh. In the operator-only test mode the access list then reads the new token, and a client
        whose person it refuses is told the grant is gone, in place of a token that every request would refuse."""
        tokens = await super().exchange_refresh_token(client, refresh_token, scopes)
        if self.policy.operators:
            access = await super().load_access_token(tokens.access_token)
            decision = self.policy.decide(access.claims if access else None)
            if not decision.allowed:  # the tokens just made reach nobody, and the old refresh token is spent
                LOG.warning("refresh refused for %s: %s", decision.email or "(no address)", decision.reason)
                raise TokenError("invalid_grant", decision.message)
        return tokens

    def get_routes(self, mcp_path: str | None = None):
        return [Route(CALLBACK, endpoint=self.checked_callback, methods=["GET"])
                if isinstance(route, Route) and route.path == CALLBACK else route
                for route in super().get_routes(mcp_path)]

    async def checked_callback(self, request: Request) -> Response:
        """FastMCP's Google callback, then the access list before the grant goes back to the client."""
        response = await self._handle_idp_callback(request)
        location = response.headers.get("location", "") if isinstance(response, RedirectResponse) else ""
        code = parse_qs(urlparse(location).query).get("code", [""])[0]
        if not code:
            return response  # an error page, or an error sent back to the client: no grant was made
        try:
            stored = await self._code_store.get(key=code)
            upstream = (stored.idp_tokens or {}).get("access_token") if stored else None
            verified = await self._token_validator.verify_token(upstream) if upstream else None
            decision = self.policy.decide(verified.claims if verified else None)
        except Exception as error:  # noqa: BLE001 - a check that cannot run refuses the sign-in
            LOG.error("sign-in check failed: %s", type(error).__name__)
            decision = UNCHECKED
        if decision.allowed:
            LOG.info("sign-in allowed for %s", decision.email)
            return response
        LOG.warning("sign-in refused for %s: %s", decision.email or "(no address)", decision.reason)
        try:
            await self._code_store.delete(key=code)
        except Exception as error:  # noqa: BLE001 - the code never reaches the client either way
            LOG.error("could not delete a refused grant: %s", type(error).__name__)
        return HTMLResponse(create_error_html(error_title="Access denied", error_message=decision.message),
                            status_code=403)


def access_check(policy: AccessPolicy):
    """An AuthMiddleware check: the access list again, for every tool call and listing."""
    def check(ctx) -> bool:
        decision = policy.decide(ctx.token.claims if ctx.token is not None else None)
        if not decision.allowed:
            raise AuthorizationError(decision.message)
        return True
    return check


def hashed_firestore_keys():
    """Every key stored in Firestore becomes its SHA-256 hash.

    A client that identifies itself by a metadata document (ChatGPT, Codex) has a URL for its ID. Used unhashed as a
    document ID, its slashes leave an odd number of path elements, so Firestore's client library raised when the OAuth
    proxy looked that client up, before the proxy could fetch the document. The proxy only gets, puts and deletes by
    key, so a hash loses nothing, and records written this way keep authorization codes and token IDs out of
    document names. py-key-value's always-hash strategy is private to that package; the public Firestore strategy is
    the base only for its type, and both methods are this class's own.
    """
    import hashlib

    from key_value.aio.stores.firestore import FirestoreV1KeySanitizationStrategy

    class HashedKeys(FirestoreV1KeySanitizationStrategy):
        def sanitize(self, value: str) -> str:  # surrogatepass: a key with an unpaired surrogate hashes too
            return hashlib.sha256(value.encode("utf-8", "surrogatepass")).hexdigest()

        def validate(self, value: str) -> None:  # any key is safe once hashed
            return None

    return HashedKeys()


def oauth_storage(settings: config.Settings):
    """Where the OAuth proxy keeps registrations, grants and Google tokens."""
    if settings.oauth_store == "memory":
        from key_value.aio.stores.memory import MemoryStore
        return MemoryStore()
    from cryptography.fernet import Fernet
    from key_value.aio.stores.firestore import FirestoreStore, FirestoreV1CollectionSanitizationStrategy
    from key_value.aio.wrappers.encryption import FernetEncryptionWrapper
    from key_value.aio.wrappers.prefix_collections import PrefixCollectionsWrapper
    store = FirestoreStore(project=settings.firestore_project or None, database=settings.firestore_database or None,
                           key_sanitization_strategy=hashed_firestore_keys(),
                           collection_sanitization_strategy=FirestoreV1CollectionSanitizationStrategy())
    return FernetEncryptionWrapper(PrefixCollectionsWrapper(store, prefix=settings.firestore_prefix),
                                   fernet=Fernet(settings.storage_key.encode()))


def build_auth(settings: config.Settings, policy: AccessPolicy, **overrides) -> AccessListGoogleProvider:
    options = dict(client_id=settings.google_client_id, client_secret=settings.google_client_secret,
                   base_url=settings.public_url, required_scopes=GOOGLE_SCOPES,
                   jwt_signing_key=settings.jwt_signing_key or None, client_storage=oauth_storage(settings),
                   cache_ttl_seconds=settings.token_cache_seconds or None,
                   allowed_client_redirect_uris=list(settings.allowed_redirect_uris) or None)
    options.update(overrides)
    return AccessListGoogleProvider(policy=policy, **options)


def document_url(template: str, doc, commit: str) -> str:
    source = doc.provenance.get("source_path") or doc.id
    return template.format(id=quote(doc.id), source_path=quote(source), commit=doc.provenance.get("commit") or commit)


def build_server(settings: config.Settings, library: Library, policy: AccessPolicy, auth) -> FastMCP:
    mcp = FastMCP(settings.server_name, auth=auth, middleware=[AuthMiddleware(auth=access_check(policy))],
                  instructions=f"{settings.server_name}: the organization's knowledge base, read-only. Use search "
                               "to find documents and fetch to read one in full; cite each document's url.")

    def snapshot():
        if library.current is None:
            raise ToolError("The knowledge base is not loaded yet. Try again in a minute.")
        return library.current

    @mcp.tool(annotations=READ_ONLY)
    def search(query: str) -> SearchResults:
        """Search the knowledge base. Returns the best-matching documents first, each with the id to pass
        to fetch, its title, its url for citation and a short snippet of the matching text."""
        snap = snapshot()
        hits = snap.index.search(query, settings.search_limit)
        return {"results": [{"id": h.id, "title": snap.corpus.get(h.id).title, "snippet": h.snippet,
                             "url": document_url(settings.document_url, snap.corpus.get(h.id), snap.commit)}
                            for h in hits]}

    @mcp.tool(annotations=READ_ONLY)
    def fetch(id: str) -> FetchedDocument:
        """Read one knowledge-base document by the id search returned: its full markdown text, its url, and
        metadata holding its front-matter fields and where and when it was published. The id SKILL.md returns
        the knowledge base's own guide: what it covers and an index of its documents."""
        snap = snapshot()
        doc = snap.corpus.get(id)
        if doc is None:
            raise ToolError(f"No document has the id {id!r}. Use an id that search returned.")
        prov = doc.provenance
        return {"id": doc.id, "title": doc.title, "text": doc.body,
                "url": "" if doc is snap.corpus.guide else document_url(settings.document_url, doc, snap.commit),
                "metadata": {"front_matter": doc.fields, "provenance": prov.get("stamp", ""),
                             "source_path": prov.get("source_path", ""), "source_repository": prov.get("source_repo", ""),
                             "source_commit": prov.get("commit", ""), "published": prov.get("published", ""),
                             "served_commit": snap.commit}}

    @mcp.custom_route("/health", methods=["GET"])
    async def health(request: Request) -> JSONResponse:
        report, ok = {**library.health(), "test_only": bool(policy.operators)}, True
        if policy.roster is not None:
            report["access_groups"] = policy.roster.health()
            ok = report["access_groups"]["status"] == "ok"
        return JSONResponse(report, status_code=200 if ok and report["status"] == "ok" else 503)

    return mcp


def main(env=None) -> int:
    env = os.environ if env is None else env
    try:
        settings = config.load(env)
        roster = GroupRoster(listed(settings.allowed_groups), settings.group_refresh_seconds) if settings.allowed_groups else None
        policy = AccessPolicy.from_settings(settings.allowed_emails, settings.allowed_hosted_domains, roster,
                                            settings.operator_addresses)
    except (config.ConfigError, ValueError) as error:
        print(f"kb-connector: {error}", file=sys.stderr)
        return 2
    logging.basicConfig(level=settings.log_level, stream=sys.stderr,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if policy.operators:
        temporary = config.temporary(urlparse(settings.public_url).hostname)
        loud = max(logging.WARNING, LOG.getEffectiveLevel())  # a warning, raised when KB_LOG_LEVEL would hide one
        LOG.log(loud, "TEST ONLY: operator-only test mode at %s. %s Only %s can sign in. List each thing this test "
                "needs before setting it up, and remove every one as soon as the test ends.", settings.public_url,
                "The address is temporary and must not be given to anyone: a restart of this process, this machine "
                "or its tunnel ends it." if temporary else
                "Do not give this address to anyone while the mode is on.", ", ".join(sorted(policy.operators)))
    if settings.oauth_store == "memory":
        LOG.warning("KB_OAUTH_STORE=memory: sign-ins live in this process only, so every restart signs everyone out")
    try:
        source = DirectorySource(settings.source_dir) if settings.source_dir else GitSource(
            settings.git_url, settings.work_dir or tempfile.mkdtemp(prefix="kb-connector-"), settings.git_branch,
            settings.ssh_key_file, settings.known_hosts)
    except SourceError as error:
        print(f"kb-connector: {error}", file=sys.stderr)
        return 2
    library = Library(source, settings.references_path)
    if not library.refresh():
        print(f"kb-connector: the first load failed: {library.last_error}", file=sys.stderr)
        return 1
    if roster is not None and not roster.refresh():
        print(f"kb-connector: the access groups could not be read: {roster.last_error}", file=sys.stderr)
        return 1
    library.start(settings.refresh_seconds)
    if roster is not None:
        roster.start()
    server = build_server(settings, library, policy, build_auth(settings, policy))
    server.run(transport="http", host=settings.host, port=settings.port, show_banner=False, stateless_http=True,
               uvicorn_config={"access_log": False})
    return 0

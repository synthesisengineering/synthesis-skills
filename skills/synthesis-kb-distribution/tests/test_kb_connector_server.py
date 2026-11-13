"""The server over HTTP, in process: the tools, /health, and the access list at sign-in, on every token and
on every tool call, and in the operator-only test mode on a refresh at the token endpoint. Sign-in runs
FastMCP's real OAuth proxy end to end (registration, consent, the Google callback, the token exchange, a
refresh); only Google is replaced: its token endpoint by a stand-in client, its tokeninfo and userinfo
endpoints by an httpx2 mock transport.

These need the connector's pinned requirements (requirements.txt), which need Python 3.12 or newer.
Without FastMCP they skip, unless SYNTHESIS_REQUIRE_FASTMCP=1, which makes a missing FastMCP fail.
"""

import asyncio
import base64
import dataclasses
import hashlib
import json
import logging
import os
import re
import secrets
import subprocess
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

if os.environ.get("SYNTHESIS_REQUIRE_FASTMCP") != "1":  # when it is "1", a missing FastMCP fails the imports below
    pytest.importorskip("fastmcp", reason="needs the connector's requirements.txt (Python 3.12+)")

import httpx2  # noqa: E402
from fastmcp.server.auth import AccessToken, TokenVerifier  # noqa: E402
from fastmcp.utilities.tests import asgi_server  # noqa: E402

from kb_connector import config, server  # noqa: E402
from kb_connector.access import AccessPolicy  # noqa: E402
from kb_connector.groups import GroupRoster  # noqa: E402
from kb_connector.source import DirectorySource, Library  # noqa: E402

CLIENT_ID = "test-client.apps.googleusercontent.com"
SCOPES = "openid https://www.googleapis.com/auth/userinfo.email"
REDIRECT = "http://localhost:8765/callback"
RESOURCE = "http://127.0.0.1/mcp"
PEOPLE = {"code-lead": ("lead@example.com", True, "example.com"),
          "code-analyst": ("analyst@example.com", True, "example.com"),
          "code-outsider": ("outsider@example.com", True, "example.com"),
          "code-unverified": ("lead@example.com", False, "example.com"),
          "code-personal": ("lead@example.com", True, None)}
PRICING = "datasets/active/pricing-decision.md"
OPERATOR = {"KB_OPERATOR_TEST": "1", "KB_OPERATOR_ADDRESSES": "lead@example.com"}  # the operator-only test mode
FIRESTORE = {"KB_OAUTH_STORE": "firestore", "KB_STORAGE_ENCRYPTION_KEY": "A" * 43 + "="}  # where a deployment keeps sign-ins


def settings_for(published, **env):
    """A deployment's settings, then moved to what an in-process test can stand on: http://127.0.0.1, the one origin
    FastMCP's in-process server answers on, and the memory store, unless the test names a store of its own. A local
    address and the memory store are what these settings would load only as the operator's own test."""
    settings = config.load({"KB_SOURCE_DIR": str(published), "KB_PUBLIC_URL": "https://kb.example.com",
                            "KB_GOOGLE_CLIENT_ID": CLIENT_ID, "KB_GOOGLE_CLIENT_SECRET": "test-secret",
                            "KB_ALLOWED_EMAILS": "lead@example.com,analyst@example.com", **FIRESTORE,
                            "KB_DOCUMENT_URL_TEMPLATE": "https://git.example.com/kb/src/{commit}/{source_path}", **env})
    return dataclasses.replace(settings, public_url="http://127.0.0.1", oauth_store=env.get("KB_OAUTH_STORE", "memory"))


@pytest.fixture
def firestore(monkeypatch):
    """The store a deployment names, for a start through main(): a memory store stands in for Firestore, so no test
    reaches Google Cloud."""
    from key_value.aio.stores.memory import MemoryStore
    monkeypatch.setattr(server, "oauth_storage", lambda settings: MemoryStore())
    return FIRESTORE


def policy_for(settings, roster=None):
    """The policy main() builds from these settings."""
    return AccessPolicy.from_settings(settings.allowed_emails, settings.allowed_hosted_domains, roster,
                                      settings.operator_addresses)


def loaded(published):
    library = Library(DirectorySource(published))
    assert library.refresh()
    return library


class ClaimsVerifier(TokenVerifier):
    """Bearer tokens that map straight to claims, to exercise the tool-level check on its own."""

    def __init__(self, tokens):
        super().__init__()
        self.tokens = tokens

    async def verify_token(self, token):
        claims = self.tokens.get(token)
        return AccessToken(token=token, client_id="test", scopes=[], claims=claims) if claims else None


class FakeGoogle:
    """Google's token endpoint, tokeninfo and userinfo, for the people in PEOPLE. It refreshes a token only for a
    test that says it expects refreshes."""

    def __init__(self, refreshes=False):
        self.tokens, self.refreshes = {}, refreshes

    def issue(self, code_name):
        """A new access token for the person who signed in with this code, as Google's token endpoint answers."""
        token = f"ya29.test-{secrets.token_hex(12)}"
        self.tokens[token] = PEOPLE[code_name]
        return {"access_token": token, "expires_in": 3600, "expires_at": int(time.time()) + 3600,
                "token_type": "Bearer", "scope": SCOPES}

    def upstream_client(self):
        google = self

        class TokenEndpoint:  # the surface OAuthProxy uses: fetch_token, refresh_token, aclose
            async def fetch_token(self, url, **params):
                assert url == "https://oauth2.googleapis.com/token" and params["code_verifier"]
                return {**google.issue(params["code"]), "refresh_token": f"1//test-refresh-{params['code']}"}

            async def refresh_token(self, url, **params):
                assert google.refreshes, "no refresh expected"
                assert url == "https://oauth2.googleapis.com/token"
                return google.issue(params["refresh_token"][len("1//test-refresh-"):])  # Google keeps the refresh token

            async def aclose(self):
                pass
        return TokenEndpoint()

    def handle(self, request):
        person = self.tokens.get(request.headers.get("authorization", "")[len("Bearer "):])
        if person is None:
            return httpx2.Response(400, json={"error": "invalid_token"})
        email, verified, domain = person
        if request.url.path == "/tokeninfo":
            return httpx2.Response(200, json={"aud": CLIENT_ID, "sub": f"sub-{email}", "scope": SCOPES,
                                              "expires_in": "3599", "email": email,
                                              "email_verified": "true" if verified else "false"})
        profile = {"id": f"sub-{email}", "email": email, "verified_email": verified, **({"hd": domain} if domain else {})}
        return httpx2.Response(200, json=profile)


def google_auth(settings, policy, google):
    auth = server.build_auth(settings, policy, http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(google.handle)))
    auth._create_upstream_oauth_client = google.upstream_client  # FastMCP's documented override point
    return auth


async def sign_in(http, code_name, client=None):
    """Register a client, consent, come back from Google, and exchange the code: (callback response, token). A
    dict passed as `client` is given what a client keeps: its id and the whole token response."""
    registered = await http.post("/register", json={"redirect_uris": [REDIRECT], "client_name": "test client",
                                                    "token_endpoint_auth_method": "none",
                                                    "grant_types": ["authorization_code", "refresh_token"],
                                                    "response_types": ["code"]})
    assert registered.status_code == 201, registered.text
    client_id = registered.json()["client_id"]
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    authorize = await http.get("/authorize", params={
        "response_type": "code", "client_id": client_id, "redirect_uri": REDIRECT, "code_challenge": challenge,
        "code_challenge_method": "S256", "state": "client-state", "scope": SCOPES, "resource": RESOURCE})
    assert authorize.status_code in (302, 303, 307), authorize.text
    consent_url = authorize.headers["location"]
    txn = parse_qs(urlparse(consent_url).query)["txn_id"][0]
    page = await http.get(consent_url)
    csrf = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)
    approved = await http.post("/consent", data={"txn_id": txn, "csrf_token": csrf, "action": "approve"})
    assert approved.status_code == 302 and approved.headers["location"].startswith("https://accounts.google.com/")
    callback = await http.get("/auth/callback", params={"code": code_name, "state": txn})
    if callback.status_code != 302:
        return callback, None
    location = urlparse(callback.headers["location"])
    assert f"{location.scheme}://{location.netloc}{location.path}" == REDIRECT
    granted = await http.post("/token", data={"grant_type": "authorization_code", "client_id": client_id,
                                              "code": parse_qs(location.query)["code"][0], "redirect_uri": REDIRECT,
                                              "code_verifier": verifier, "resource": RESOURCE})
    assert granted.status_code == 200, granted.text
    if client is not None:
        client.update(granted.json(), client_id=client_id)
    return callback, granted.json()["access_token"]


async def refresh(http, client):
    """What a client does when its access token runs out: the refresh grant at the token endpoint."""
    return await http.post("/token", data={"grant_type": "refresh_token", "client_id": client["client_id"],
                                           "refresh_token": client["refresh_token"]})


def run(coro):
    return asyncio.run(coro)


def test_the_tools_are_read_only_search_and_fetch(published):
    policy = AccessPolicy.from_settings("lead@example.com")
    mcp = server.build_server(settings_for(published), loaded(published), policy,
                              ClaimsVerifier({"t": {"email": "lead@example.com", "email_verified": "true"}}))

    async def go():
        async with asgi_server(mcp, stateless_http=True) as srv, srv.client(auth="t") as client:
            return await client.list_tools()
    tools = {tool.name: tool for tool in run(go())}
    assert set(tools) == {"search", "fetch"}
    for tool in tools.values():
        hints = tool.annotations.model_dump(by_alias=True, exclude_none=True)
        assert hints == {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True,
                         "openWorldHint": False}
    assert list(tools["search"].input_schema["properties"]) == ["query"]
    assert list(tools["fetch"].input_schema["properties"]) == ["id"]


def test_search_and_fetch_return_what_chatgpt_expects(published):
    subprocess.run(["git", "init", "--quiet"], cwd=published, check=True)
    subprocess.run(["git", "add", "."], cwd=published, check=True)
    subprocess.run(["git", "commit", "--quiet", "-m", "fixture"], cwd=published, check=True)
    library = loaded(published)
    mcp = server.build_server(settings_for(published), library, AccessPolicy.from_settings("lead@example.com"),
                              ClaimsVerifier({"t": {"email": "lead@example.com", "email_verified": True}}))

    async def go():
        async with asgi_server(mcp, stateless_http=True) as srv, srv.client(auth="t") as client:
            found = await client.call_tool("search", {"query": "per-seat pricing"})
            fetched = await client.call_tool("fetch", {"id": PRICING})
            missing = await client.call_tool("fetch", {"id": "../../etc/passwd"}, raise_on_error=False)
            guide = await client.call_tool("fetch", {"id": "SKILL.md"})
            return found, fetched, missing, guide
    next(published.glob("plugins/*/skills/*/references")).parent.joinpath("SKILL.md").write_text("# Guide\n\nEvery document.\n", encoding="utf-8")
    library.refresh()
    found, fetched, missing, guide = run(go())
    assert guide.structured_content["text"] == "# Guide\n\nEvery document." and guide.structured_content["url"] == ""
    results = found.structured_content["results"]
    assert json.loads(found.content[0].text) == found.structured_content
    assert results[0] == {"id": PRICING, "title": "Pricing decision for 2027",
                          "url": "https://git.example.com/kb/src/abc1234/source/datasets/active/pricing-decision.md",
                          "snippet": results[0]["snippet"]}
    assert "per-seat pricing" in results[0]["snippet"]
    doc = fetched.structured_content
    assert json.loads(fetched.content[0].text) == doc
    assert doc["id"] == PRICING and doc["title"] == "Pricing decision for 2027" and doc["url"] == results[0]["url"]
    assert doc["text"].startswith("> Published from `source/datasets/active/pricing-decision.md`")
    assert "five-person clinic" in doc["text"] and "status: decided" not in doc["text"]
    meta = doc["metadata"]
    assert meta["front_matter"]["status"] == "decided" and meta["front_matter"]["tags"] == ["pricing", "decision"]
    assert meta["provenance"].startswith("> Published from") and meta["source_commit"] == "abc1234"
    assert meta["source_repository"] == "example/knowledge-base" and meta["published"] == "2026-11-01"
    assert meta["served_commit"] == library.current.commit and len(library.current.commit) == 40
    assert missing.is_error and "No document has the id '../../etc/passwd'" in missing.content[0].text


def test_health_reports_the_served_commit_and_503_before_a_load(published):
    library = loaded(published)
    policy = AccessPolicy.from_settings("lead@example.com")

    async def health(lib):
        mcp = server.build_server(settings_for(published), lib, policy, ClaimsVerifier({}))
        async with asgi_server(mcp, stateless_http=True) as srv, srv.http_client() as http:
            return await http.get("/health")
    ok = run(health(library))
    assert ok.status_code == 200 and ok.json()["status"] == "ok" and ok.json()["files"] == 4
    assert set(ok.json()) == {"status", "commit", "files", "refreshed_at", "last_attempt_at", "last_refresh_failed",
                              "test_only"}
    assert ok.json()["test_only"] is False
    empty = run(health(Library(DirectorySource(published))))
    assert empty.status_code == 503 and empty.json()["status"] == "unavailable" and empty.json()["test_only"] is False


def test_health_says_when_the_connector_is_the_operators_own_test(published):
    settings = settings_for(published, **OPERATOR)

    async def health():
        mcp = server.build_server(settings, loaded(published), policy_for(settings), ClaimsVerifier({}))
        async with asgi_server(mcp, stateless_http=True) as srv, srv.http_client() as http:
            return await http.get("/health")
    answer = run(health())
    assert answer.status_code == 200 and answer.json()["status"] == "ok" and answer.json()["test_only"] is True


def directory(*people):
    """The two Cloud Identity reads for one group, leads@example.com, holding these people."""
    def read(path):
        if path.startswith("groups:lookup"):
            return {"name": "groups/leads"}
        return {"memberships": [{"preferredMemberKey": {"id": person}, "type": "USER"} for person in people]}
    return read


def test_health_reports_the_access_groups_and_503_when_they_are_stale(published):
    roster = GroupRoster(["leads@example.com"], 300, directory("lead@example.com"))
    policy = AccessPolicy.from_settings("", "", roster)

    async def health():
        mcp = server.build_server(settings_for(published), loaded(published), policy, ClaimsVerifier({}))
        async with asgi_server(mcp, stateless_http=True) as srv, srv.http_client() as http:
            return await http.get("/health")
    stale = run(health())
    assert stale.status_code == 503 and stale.json()["access_groups"]["status"] == "stale"
    assert roster.refresh()
    ok = run(health())
    assert ok.status_code == 200 and ok.json()["access_groups"] == {
        "status": "ok", "refreshed_at": ok.json()["access_groups"]["refreshed_at"], "last_refresh_failed": False}


def test_a_group_member_signs_in_and_loses_access_when_the_groups_cannot_be_read(published):
    settings, google = settings_for(published, KB_ALLOWED_EMAILS="", KB_ALLOWED_GROUPS="leads@example.com"), FakeGoogle()
    roster = GroupRoster(["leads@example.com"], 300, directory("lead@example.com"))
    assert roster.refresh()
    policy = AccessPolicy.from_settings(settings.allowed_emails, "", roster)

    async def go():
        mcp = server.build_server(settings, loaded(published), policy, google_auth(settings, policy, google))
        async with asgi_server(mcp, stateless_http=True) as srv, srv.http_client() as http:
            outsider = await sign_in(http, "code-outsider")
            _, token = await sign_in(http, "code-lead")
            before = await http.post("/mcp", headers={"authorization": f"Bearer {token}"}, json={})
            roster.refreshed_at -= 901  # three intervals without a good read
            after = await http.post("/mcp", headers={"authorization": f"Bearer {token}"}, json={})
            return outsider, token, before, after
    (outsider, none), token, before, after = run(go())
    assert outsider.status_code == 403 and none is None and "not on this knowledge base" in outsider.text
    assert token and before.status_code != 401 and after.status_code == 401


def test_main_refuses_to_start_when_the_access_groups_cannot_be_read(published, monkeypatch, capsys, firestore):
    env = {"KB_SOURCE_DIR": str(published), "KB_PUBLIC_URL": "https://kb.example.com", "KB_GOOGLE_CLIENT_ID": CLIENT_ID,
           "KB_GOOGLE_CLIENT_SECRET": "test-secret", "KB_ALLOWED_GROUPS": "leads@example.com",
           "KB_REFRESH_SECONDS": "0", **firestore}

    def refused(path):
        raise RuntimeError("Cloud Identity API answered 403 for groups:lookup: permission denied")
    monkeypatch.setattr(server, "GroupRoster", lambda groups, seconds: GroupRoster(groups, seconds, refused))
    assert server.main(env) == 1
    assert "the access groups could not be read: Cloud Identity API answered 403" in capsys.readouterr().err
    started = []

    def readable(groups, seconds):
        roster = GroupRoster(groups, seconds, directory("lead@example.com"))
        roster.start = lambda: started.append(roster)
        return roster
    monkeypatch.setattr(server, "GroupRoster", readable)
    monkeypatch.setattr(server.FastMCP, "run", lambda self, **kwargs: None)
    assert server.main(env) == 0 and started[0].members == {"lead@example.com"}


def test_a_listed_person_signs_in_with_google_and_searches_and_no_token_is_logged(published, caplog, monkeypatch):
    for name in ("", "fastmcp", "mcp", "httpx2", "kb_connector"):  # FastMCP sets its own loggers' levels
        caplog.set_level(logging.DEBUG, logger=name)
        logger = logging.getLogger(name)
        # FastMCP's logger writes through its own handler and does not propagate, and only pytest 9
        # captures such a logger by itself, so give it the capture handler under any pytest
        if not logger.propagate and caplog.handler not in logger.handlers:
            monkeypatch.setattr(logger, "handlers", [*logger.handlers, caplog.handler])
    settings, google = settings_for(published), FakeGoogle()
    policy = AccessPolicy.from_settings(settings.allowed_emails)

    async def go():
        mcp = server.build_server(settings, loaded(published), policy, google_auth(settings, policy, google))
        async with asgi_server(mcp, stateless_http=True) as srv, srv.http_client() as http:
            unauthenticated = await http.post("/mcp", json={})
            callback, token = await sign_in(http, "code-lead")
            async with srv.client(auth=token) as client:
                found = await client.call_tool("search", {"query": "glossary"})
            return unauthenticated, callback, token, found
    unauthenticated, callback, token, found = run(go())
    assert unauthenticated.status_code == 401 and "resource_metadata" in unauthenticated.headers["www-authenticate"]
    assert callback.status_code == 302 and token
    assert found.structured_content["results"][0]["id"] == "datasets/reference/glossary.md"
    assert "sign-in allowed for lead@example.com" in caplog.text
    assert "Token swap successful" in caplog.text  # FastMCP's own debug lines on the token path were captured
    secrets_seen = [token, *google.tokens, "1//test-refresh", "test-secret"]
    assert not [s for s in secrets_seen if s in caplog.text]


@pytest.mark.parametrize("code_name, message", [
    ("code-outsider", "outsider@example.com is not on this knowledge base"),
    ("code-unverified", "Google has not verified the address lead@example.com"),
])
def test_a_person_the_list_refuses_sees_why_and_gets_no_grant(published, code_name, message):
    settings, google = settings_for(published), FakeGoogle()
    policy = AccessPolicy.from_settings(settings.allowed_emails)

    async def go():
        mcp = server.build_server(settings, loaded(published), policy, google_auth(settings, policy, google))
        async with asgi_server(mcp, stateless_http=True) as srv, srv.http_client() as http:
            return await sign_in(http, code_name)
    callback, token = run(go())
    assert callback.status_code == 403 and token is None and "location" not in callback.headers
    assert "Access denied" in callback.text and message in callback.text


def test_hosted_domains_refuse_a_personal_account_at_sign_in(published):
    settings, google = settings_for(published, KB_ALLOWED_HOSTED_DOMAINS="example.com"), FakeGoogle()
    policy = AccessPolicy.from_settings(settings.allowed_emails, settings.allowed_hosted_domains)

    async def go():
        mcp = server.build_server(settings, loaded(published), policy, google_auth(settings, policy, google))
        async with asgi_server(mcp, stateless_http=True) as srv, srv.http_client() as http:
            return await sign_in(http, "code-personal"), await sign_in(http, "code-lead")
    (personal, none), (workspace, token) = run(go())
    assert personal.status_code == 403 and none is None and "allowed Google Workspace domain" in personal.text
    assert workspace.status_code == 302 and token


def test_a_person_removed_from_the_list_loses_access_at_once(published):
    settings, google = settings_for(published), FakeGoogle()
    policy = AccessPolicy.from_settings(settings.allowed_emails)

    async def go():
        auth = google_auth(settings, policy, google)
        mcp = server.build_server(settings, loaded(published), policy, auth)
        async with asgi_server(mcp, stateless_http=True) as srv, srv.http_client() as http:
            _, token = await sign_in(http, "code-lead")
            before = await http.post("/mcp", headers={"authorization": f"Bearer {token}"}, json={})
            auth.policy = AccessPolicy.from_settings("analyst@example.com")  # the list no longer has lead@
            after = await http.post("/mcp", headers={"authorization": f"Bearer {token}"}, json={})
            return before, after
    before, after = run(go())
    assert before.status_code != 401
    assert after.status_code == 401 and 'error="invalid_token"' in after.headers["www-authenticate"]


def test_a_sign_in_that_cannot_be_checked_is_refused(published):
    settings, google = settings_for(published), FakeGoogle()
    policy = AccessPolicy.from_settings(settings.allowed_emails)

    class BrokenStore:
        async def get(self, key):
            raise RuntimeError("storage down")

        async def delete(self, key):
            raise RuntimeError("storage down")

    async def go():
        auth = google_auth(settings, policy, google)
        mcp = server.build_server(settings, loaded(published), policy, auth)
        async with asgi_server(mcp, stateless_http=True) as srv, srv.http_client() as http:
            real = auth._code_store
            proxy_put = real.put

            class HalfBroken(BrokenStore):  # FastMCP still stores the grant; the access check cannot read it
                put = staticmethod(proxy_put)
            auth._code_store = HalfBroken()
            return await sign_in(http, "code-lead")
    callback, token = run(go())
    assert callback.status_code == 403 and token is None and "could not be checked" in callback.text


def test_the_tool_check_refuses_anyone_not_listed_whatever_the_token(published):
    policy = AccessPolicy.from_settings("lead@example.com")
    verifier = ClaimsVerifier({"outsider": {"email": "outsider@example.com", "email_verified": "true"},
                               "unverified": {"email": "lead@example.com", "email_verified": "false"}})
    mcp = server.build_server(settings_for(published), loaded(published), policy, verifier)

    async def go(token):
        async with asgi_server(mcp, stateless_http=True) as srv, srv.client(auth=token) as client:
            return await client.list_tools(), await client.call_tool("search", {"query": "x"}, raise_on_error=False)
    for token, message in (("outsider", "outsider@example.com is not on this knowledge base's access list"),
                           ("unverified", "Google has not verified")):
        tools, result = run(go(token))
        assert tools == [] and result.is_error and message in result.content[0].text


@pytest.mark.parametrize("env, group", [
    ({}, None),                                                                       # on the email list
    ({"KB_ALLOWED_EMAILS": "", "KB_ALLOWED_GROUPS": "leads@example.com"},             # in an allowed group
     ("lead@example.com", "analyst@example.com")),
    ({"KB_ALLOWED_HOSTED_DOMAINS": "example.com"}, None),                             # listed, in an allowed domain
])
def test_the_test_mode_signs_in_the_operator_and_nobody_else_the_rules_would_admit(published, caplog, env, group):
    settings, google = settings_for(published, **OPERATOR, **env), FakeGoogle()
    roster = GroupRoster(["leads@example.com"], 300, directory(*group)) if group else None
    assert roster is None or roster.refresh()
    policy = policy_for(settings, roster)

    async def go():
        mcp = server.build_server(settings, loaded(published), policy, google_auth(settings, policy, google))
        async with asgi_server(mcp, stateless_http=True) as srv, srv.http_client() as http:
            refused = await sign_in(http, "code-analyst")
            callback, token = await sign_in(http, "code-lead")
            async with srv.client(auth=token) as client:
                return refused, callback, await client.call_tool("search", {"query": "glossary"})
    (refused, none), callback, found = run(go())
    assert refused.status_code == 403 and none is None and "location" not in refused.headers
    assert "Access denied" in refused.text and "analyst@example.com is not on this knowledge base" in refused.text
    assert "sign-in refused for analyst@example.com: operator_only_test_mode" in caplog.text
    assert callback.status_code == 302
    assert found.structured_content["results"][0]["id"] == "datasets/reference/glossary.md"


def test_a_token_from_before_the_test_mode_works_for_the_operator_alone(published, caplog):
    settings, google = settings_for(published, **OPERATOR), FakeGoogle()
    policy = AccessPolicy.from_settings(settings.allowed_emails)  # before the test: the list lets both in

    async def go():
        auth = google_auth(settings, policy, google)
        mcp = server.build_server(settings, loaded(published), policy, auth)
        async with asgi_server(mcp, stateless_http=True) as srv, srv.http_client() as http:
            (_, analyst), (_, operator) = await sign_in(http, "code-analyst"), await sign_in(http, "code-lead")
            before = await http.post("/mcp", headers={"authorization": f"Bearer {analyst}"}, json={})
            auth.policy = policy_for(settings)  # the test mode comes on over a store that kept both tokens
            after = await http.post("/mcp", headers={"authorization": f"Bearer {analyst}"}, json={})
            kept = await http.post("/mcp", headers={"authorization": f"Bearer {operator}"}, json={})
            return before, after, kept
    before, after, kept = run(go())
    assert before.status_code != 401 and kept.status_code != 401
    assert after.status_code == 401 and 'error="invalid_token"' in after.headers["www-authenticate"]
    assert "token refused for analyst@example.com: operator_only_test_mode" in caplog.text


def unlisted(email):
    return f"Access denied: {email} is not on this knowledge base's access list. Ask its administrator to add the address."


def test_in_the_test_mode_the_token_endpoint_refuses_a_refresh_by_anyone_but_the_operator(published, caplog):
    settings, google = settings_for(published, **OPERATOR), FakeGoogle(refreshes=True)
    policy = AccessPolicy.from_settings(settings.allowed_emails)  # before the test: the list lets both in
    analyst, operator = {}, {}

    async def go():
        auth = google_auth(settings, policy, google)
        mcp = server.build_server(settings, loaded(published), policy, auth)
        async with asgi_server(mcp, stateless_http=True) as srv, srv.http_client() as http:
            await sign_in(http, "code-analyst", analyst)
            await sign_in(http, "code-lead", operator)
            auth.policy = policy_for(settings)  # the test mode comes on over a store that kept both grants
            refused, renewed = await refresh(http, analyst), await refresh(http, operator)
            used = await http.post("/mcp", headers={"authorization": f"Bearer {renewed.json()['access_token']}"}, json={})
            return refused, renewed, used, await refresh(http, analyst)
    refused, renewed, used, again = run(go())
    assert refused.status_code == 401 and refused.headers["cache-control"] == "no-store"
    assert refused.json()["error"] == "invalid_grant"  # RFC 6749, section 5.2: the grant is no longer valid
    assert refused.json()["error_description"] == unlisted("analyst@example.com")
    assert "access_token" not in refused.json() and "refresh_token" not in refused.json()
    assert "refresh refused for analyst@example.com: operator_only_test_mode" in caplog.text
    assert renewed.status_code == 200 and renewed.json()["access_token"] != operator["access_token"]
    assert renewed.json()["refresh_token"] != operator["refresh_token"] and used.status_code != 401
    assert "refresh refused for lead@example.com" not in caplog.text
    assert again.status_code == 401 and again.json()["error"] == "invalid_grant"  # asked again, the answer is the same


def test_outside_the_test_mode_a_refresh_is_given_whoever_asks_and_each_request_is_then_checked(published, caplog):
    settings, google = settings_for(published), FakeGoogle(refreshes=True)
    policy = AccessPolicy.from_settings(settings.allowed_emails)
    analyst, lead = {}, {}

    async def go():
        auth = google_auth(settings, policy, google)
        mcp = server.build_server(settings, loaded(published), policy, auth)
        async with asgi_server(mcp, stateless_http=True) as srv, srv.http_client() as http:
            await sign_in(http, "code-analyst", analyst)
            await sign_in(http, "code-lead", lead)
            auth.policy = AccessPolicy.from_settings("lead@example.com")  # the list no longer has analyst@
            removed, kept = await refresh(http, analyst), await refresh(http, lead)
            requests = [await http.post("/mcp", headers={"authorization": f"Bearer {answer.json()['access_token']}"}, json={})
                        for answer in (removed, kept)]
            return removed, kept, requests
    removed, kept, (refused, served) = run(go())
    for answer, client in ((removed, analyst), (kept, lead)):  # the token endpoint asks nothing of the list
        assert answer.status_code == 200 and answer.json()["access_token"] != client["access_token"]
        assert answer.json()["refresh_token"] != client["refresh_token"]
    assert refused.status_code == 401 and 'error="invalid_token"' in refused.headers["www-authenticate"]  # each request does
    assert served.status_code != 401
    assert "token refused for analyst@example.com: email_not_listed" in caplog.text and "refresh refused" not in caplog.text


def test_in_the_test_mode_the_operators_own_refresh_is_checked_as_every_request_is(published, caplog):
    settings, google = settings_for(published, **OPERATOR), FakeGoogle(refreshes=True)
    policy = policy_for(settings)
    unread, off_the_list = {}, {}

    async def go():
        auth = google_auth(settings, policy, google)
        mcp = server.build_server(settings, loaded(published), policy, auth)
        async with asgi_server(mcp, stateless_http=True) as srv, srv.http_client() as http:
            await sign_in(http, "code-lead", unread)
            await sign_in(http, "code-lead", off_the_list)
            issue = google.issue  # a new token Google's tokeninfo does not vouch for: nobody can say whose it is
            google.issue = lambda code_name: {**issue(code_name), "access_token": "ya29.test-unknown-to-tokeninfo"}
            unchecked = await refresh(http, unread)
            google.issue = issue
            auth.policy = AccessPolicy.from_settings("analyst@example.com", "", None, "lead@example.com")
            return unchecked, await refresh(http, off_the_list)  # the operator, no longer on the list
    unchecked, refused = run(go())
    for answer in (unchecked, refused):
        assert answer.status_code == 401 and answer.json()["error"] == "invalid_grant" and "access_token" not in answer.json()
    assert unchecked.json()["error_description"] == ("Access denied: the sign-in did not identify a Google account. "
                                                     "Sign in again.")
    assert "refresh refused for (no address): no_identity" in caplog.text
    assert refused.json()["error_description"] == unlisted("lead@example.com")
    assert "refresh refused for lead@example.com: email_not_listed" in caplog.text


def test_the_tool_check_refuses_everyone_but_the_operator_in_the_test_mode(published):
    settings = settings_for(published, **OPERATOR)
    verifier = ClaimsVerifier({"analyst": {"email": "analyst@example.com", "email_verified": "true"},
                               "operator": {"email": "lead@example.com", "email_verified": "true"}})
    mcp = server.build_server(settings, loaded(published), policy_for(settings), verifier)

    async def go(token):
        async with asgi_server(mcp, stateless_http=True) as srv, srv.client(auth=token) as client:
            return await client.list_tools(), await client.call_tool("search", {"query": "x"}, raise_on_error=False)
    tools, result = run(go("analyst"))  # on the list, and not the operator
    assert tools == [] and result.is_error
    assert "analyst@example.com is not on this knowledge base's access list" in result.content[0].text
    tools, result = run(go("operator"))
    assert {tool.name for tool in tools} == {"search", "fetch"} and not result.is_error


class FirestoreLikeClient:
    """An in-memory Firestore whose document references are first built by the real client library, so the
    library's own path check applies: an ID whose slashes leave an odd number of path elements raises "A document must
    have an even number of path elements", the error the first deployment logged. The ID rules the Firestore service
    enforces are then applied here (no "/", not "." or "..", not __.*__, at most 1,500 bytes), since the library leaves
    those to the service. Building a reference makes no network call; get, set and delete keep the fields here."""

    def __init__(self):
        from google.auth.credentials import AnonymousCredentials
        from google.cloud import firestore
        self.library = firestore.AsyncClient(project="example-project", credentials=AnonymousCredentials())
        self.documents = {}  # (collection, document ID) -> the stored fields

    def collection(self, name):
        client = self

        class Collection:
            def document(self, document_id):
                client.library.collection(name).document(document_id)  # the library's own path check
                if "/" in document_id or document_id in ("", ".", "..") or re.fullmatch(r"__.*__", document_id) \
                        or len(document_id.encode("utf-8", "surrogatepass")) > 1500:
                    raise ValueError(f"the Firestore service refuses the document ID {document_id[:60]!r}")
                return FirestoreLikeClient.Document(client, name, document_id)
        return Collection()

    class Document:
        def __init__(self, client, collection, document_id):
            self.client, self.path = client, (collection, document_id)

        async def get(self):
            fields = self.client.documents.get(self.path)
            return type("Snapshot", (), {"exists": fields is not None, "id": self.path[1],
                                         "to_dict": lambda _: None if fields is None else dict(fields)})()

        async def set(self, fields):
            self.client.documents[self.path] = dict(fields)

        async def delete(self):
            self.client.documents.pop(self.path, None)


def firestore_over(monkeypatch, client):
    """server.oauth_storage builds the real FirestoreStore, here over the in-memory client; returns what
    oauth_storage passed to it."""
    import key_value.aio.stores.firestore as firestore_package
    from key_value.aio.stores.firestore import store as firestore_store
    real = firestore_store.FirestoreStore
    made = {}

    class OverInMemoryClient(real):
        def __init__(self, **kwargs):
            made.update(kwargs)
            options = {k: v for k, v in kwargs.items() if k not in ("project", "database")}
            super().__init__(client=client, **options)
    monkeypatch.setattr(firestore_store, "FirestoreStore", OverInMemoryClient)
    monkeypatch.setattr(firestore_package, "FirestoreStore", OverInMemoryClient)
    return made


def firestore_settings(published):
    from cryptography.fernet import Fernet
    return settings_for(published, KB_OAUTH_STORE="firestore", KB_STORAGE_ENCRYPTION_KEY=Fernet.generate_key().decode(),
                        KB_FIRESTORE_PROJECT="example-project", KB_FIRESTORE_COLLECTION_PREFIX="kb-test")


CODEX = "https://chatgpt.com/oauth/codex/client.json"  # a client ID that is a metadata document's URL


def test_oauth_state_goes_to_firestore_encrypted_prefixed_and_under_hashed_ids(published, monkeypatch):
    from key_value.aio.stores.firestore import FirestoreV1CollectionSanitizationStrategy
    from key_value.aio.stores.memory import MemoryStore
    from key_value.aio.wrappers.encryption import FernetEncryptionWrapper
    from key_value.aio.wrappers.prefix_collections import PrefixCollectionsWrapper

    client = FirestoreLikeClient()
    made = firestore_over(monkeypatch, client)
    settings = firestore_settings(published)
    storage = server.oauth_storage(settings)
    assert (made["project"], made["database"]) == ("example-project", None)
    keys = made["key_sanitization_strategy"]
    assert keys.sanitize("a/b") == hashlib.sha256(b"a/b").hexdigest()
    assert re.fullmatch(r"[0-9a-f]{64}", keys.sanitize("\ud800"))  # an unpaired surrogate hashes too
    assert isinstance(made["collection_sanitization_strategy"], FirestoreV1CollectionSanitizationStrategy)
    assert isinstance(storage, FernetEncryptionWrapper) and isinstance(storage.key_value, PrefixCollectionsWrapper)
    assert storage.key_value.prefix == "kb-test"
    assert isinstance(server.oauth_storage(settings_for(published)), MemoryStore)
    google = FakeGoogle()
    policy = AccessPolicy.from_settings(settings.allowed_emails)

    async def go():  # a whole sign-in through the real Firestore store, encrypted and prefixed
        mcp = server.build_server(settings, loaded(published), policy, google_auth(settings, policy, google))
        async with asgi_server(mcp, stateless_http=True) as srv, srv.http_client() as http:
            return await sign_in(http, "code-lead")
    assert run(go())[1]
    assert client.documents and all(re.fullmatch(r"[0-9a-f]{64}", key) for _, key in client.documents)
    assert {collection.split("__")[0] for collection, _ in client.documents} == {"kb-test"}
    for fields in client.documents.values():  # what a document keeps: no key, no address, the value encrypted
        assert set(fields) <= {"created_at", "expires_at", "value", "version"}
        assert "lead@example.com" not in repr(fields)


def test_a_client_that_identifies_by_a_url_gets_past_its_lookup_on_firestore(published, monkeypatch):
    """ChatGPT and Codex identify themselves by a metadata document, so their client ID is a URL. On Firestore the
    OAuth proxy's lookup of that ID raised in the client library, and /authorize answered 500 to both (2026-11-13, the
    first deployment). With hashed keys the lookup finds nothing and goes on to the metadata document, which this
    test never fetches: the client is then unknown, a 400."""
    firestore_over(monkeypatch, FirestoreLikeClient())
    settings = firestore_settings(published)
    policy = AccessPolicy.from_settings(settings.allowed_emails)
    auth = google_auth(settings, policy, FakeGoogle())
    fetched = []

    async def no_fetch(client_id):
        fetched.append(client_id)
        return None
    auth._cimd_manager.get_client = no_fetch

    async def go():
        mcp = server.build_server(settings, loaded(published), policy, auth)
        async with asgi_server(mcp, stateless_http=True) as srv, srv.http_client() as http:
            return await http.get("/authorize", params={
                "response_type": "code", "client_id": CODEX, "redirect_uri": "http://127.0.0.1:5555/callback",
                "code_challenge": "c" * 43, "code_challenge_method": "S256", "state": "s", "scope": SCOPES,
                "resource": RESOURCE})
    answer = run(go())
    assert answer.status_code == 400 and fetched == [CODEX], (answer.status_code, answer.text[:300])


def test_the_client_library_refuses_a_url_as_a_document_id_and_a_hashed_store_keeps_one(published, monkeypatch):
    with pytest.raises(ValueError, match="even number of path elements"):  # the library's own check, why keys are hashed
        FirestoreLikeClient().collection("kb-test__mcp-oauth-proxy-clients").document(CODEX)
    client = FirestoreLikeClient()
    firestore_over(monkeypatch, client)
    storage = server.oauth_storage(firestore_settings(published))

    async def go():
        await storage.put(key=CODEX, value={"client_name": "Codex"}, collection="mcp-oauth-proxy-clients")
        stored = await storage.get(key=CODEX, collection="mcp-oauth-proxy-clients")
        kept = dict(client.documents)
        deleted = await storage.delete(key=CODEX, collection="mcp-oauth-proxy-clients")
        return stored, kept, deleted, await storage.get(key=CODEX, collection="mcp-oauth-proxy-clients")
    stored, kept, deleted, after = run(go())
    assert stored == {"client_name": "Codex"} and deleted and after is None
    assert [key for _, key in kept] == [hashlib.sha256(CODEX.encode()).hexdigest()]
    assert CODEX not in repr(kept)


def test_records_from_before_the_hashed_ids_are_not_read_so_each_person_signs_in_again(published, monkeypatch):
    """What an upgrade from 5.4.0 to 5.12.0 does on Firestore, as the changelog and connector.md 5.7 say: a record
    stored under its raw key is never found again, and stays until it is removed."""
    from cryptography.fernet import Fernet
    from key_value.aio.stores.firestore import store as firestore_store
    from key_value.aio.wrappers.encryption import FernetEncryptionWrapper
    from key_value.aio.wrappers.prefix_collections import PrefixCollectionsWrapper

    client = FirestoreLikeClient()
    settings = firestore_settings(published)
    before = FernetEncryptionWrapper(PrefixCollectionsWrapper(firestore_store.FirestoreStore(client=client),
                                                              prefix="kb-test"),
                                     fernet=Fernet(settings.storage_key.encode()))  # how 5.4.0 to 5.12.0 stored
    firestore_over(monkeypatch, client)
    after = server.oauth_storage(settings)
    uuid = "0b6f0e3c-5a3e-4f7e-9d7a-2b9b7f1c1e11"  # a client registered by dynamic registration

    async def go():
        await before.put(key=uuid, value={"client_name": "Claude"}, collection="mcp-oauth-proxy-clients")
        return await before.get(key=uuid, collection="mcp-oauth-proxy-clients"), \
            await after.get(key=uuid, collection="mcp-oauth-proxy-clients")
    old_read, new_read = run(go())
    assert old_read == {"client_name": "Claude"} and new_read is None
    assert [key for _, key in client.documents] == [uuid]  # the old document stays until it is removed


def test_main_refuses_bad_settings_and_serves_good_ones_statelessly(published, monkeypatch, capsys, firestore):
    assert server.main({}) == 2
    assert "KB_GOOGLE_CLIENT_ID is required" in capsys.readouterr().err
    env = {"KB_SOURCE_DIR": str(published), "KB_PUBLIC_URL": "https://kb.example.com", "KB_GOOGLE_CLIENT_ID": CLIENT_ID,
           "KB_GOOGLE_CLIENT_SECRET": "test-secret", "KB_ALLOWED_EMAILS": "lead@example.com", "KB_REFRESH_SECONDS": "0",
           **firestore}
    assert server.main({**env, "KB_SOURCE_DIR": str(published / "absent")}) == 1
    assert "the first load failed" in capsys.readouterr().err
    assert server.main({**env, "KB_SOURCE_DIR": "", "KB_GIT_URL": "git@git.example.com:x/y.git"}) == 2
    assert "KB_GIT_SSH_KEY_FILE and KB_GIT_KNOWN_HOSTS" in capsys.readouterr().err
    calls = []
    monkeypatch.setattr(server.FastMCP, "run", lambda self, **kwargs: calls.append((self, kwargs)))
    assert server.main(env) == 0
    mcp, kwargs = calls[0]
    assert isinstance(mcp.auth, server.AccessListGoogleProvider)
    assert kwargs == {"transport": "http", "host": "0.0.0.0", "port": 8080, "show_banner": False,
                      "stateless_http": True, "uvicorn_config": {"access_log": False}}


def test_main_says_test_only_at_the_start_of_the_operators_own_test(published, monkeypatch, caplog, capsys, firestore):
    env = {"KB_SOURCE_DIR": str(published), "KB_PUBLIC_URL": "https://kb.example.com", "KB_GOOGLE_CLIENT_ID": CLIENT_ID,
           "KB_GOOGLE_CLIENT_SECRET": "test-secret", "KB_ALLOWED_EMAILS": "lead@example.com,analyst@example.com",
           "KB_REFRESH_SECONDS": "0", **firestore}
    served = []
    monkeypatch.setattr(server.FastMCP, "run", lambda self, **kwargs: served.append(self))
    assert server.main(env) == 0 and served[-1].auth.policy.operators == frozenset()
    assert not [message for message in caplog.messages if "TEST ONLY" in message]
    assert server.main({**env, **OPERATOR, "KB_OPERATOR_ADDRESSES": "Second@Example.com, lead@example.com"}) == 0
    assert served[-1].auth.policy.operators == {"lead@example.com", "second@example.com"}
    (line,) = [record for record in caplog.records if record.getMessage().startswith("TEST ONLY")]
    assert line.levelno == logging.WARNING and line.name == "kb_connector"
    assert "operator-only test mode at https://kb.example.com." in line.getMessage()
    assert "Do not give this address to anyone" in line.getMessage() and "temporary" not in line.getMessage()
    assert "Only lead@example.com, second@example.com can sign in." in line.getMessage()
    assert server.main({**env, "KB_OPERATOR_TEST": "1"}) == 2 and len(served) == 2  # the mode with no operator named
    assert "needs both KB_OPERATOR_TEST=1 and KB_OPERATOR_ADDRESSES" in capsys.readouterr().err


def test_main_names_each_of_three_operator_addresses_and_refuses_to_start_with_a_fourth(published, monkeypatch, caplog,
                                                                                       capsys):
    env = {"KB_SOURCE_DIR": str(published), "KB_PUBLIC_URL": "http://localhost:8080", "KB_GOOGLE_CLIENT_ID": CLIENT_ID,
           "KB_GOOGLE_CLIENT_SECRET": "test-secret", "KB_ALLOWED_EMAILS": "lead@example.com", "KB_REFRESH_SECONDS": "0",
           "KB_OPERATOR_TEST": "1"}
    three = "third@example.com, Second@Example.com, lead@example.com"
    served = []
    monkeypatch.setattr(server.FastMCP, "run", lambda self, **kwargs: served.append(self))
    assert server.main({**env, "KB_OPERATOR_ADDRESSES": three}) == 0
    assert served[-1].auth.policy.operators == {"lead@example.com", "second@example.com", "third@example.com"}
    (line,) = [message for message in caplog.messages if message.startswith("TEST ONLY")]
    assert "Only lead@example.com, second@example.com, third@example.com can sign in." in line
    assert server.main({**env, "KB_OPERATOR_ADDRESSES": three + ", fourth@example.com"}) == 2 and len(served) == 1
    assert ("kb-connector: the connector cannot start:\n  - KB_OPERATOR_ADDRESSES names 4 addresses and may name three "
            "at most: they are one person's own accounts") in capsys.readouterr().err


def test_main_refuses_a_temporary_address_and_the_operators_own_test_says_what_ends_it(published, monkeypatch, caplog,
                                                                                      capsys):
    env = {"KB_SOURCE_DIR": str(published), "KB_PUBLIC_URL": "https://quiet-river-demo.trycloudflare.com",
           "KB_GOOGLE_CLIENT_ID": CLIENT_ID, "KB_GOOGLE_CLIENT_SECRET": "test-secret",
           "KB_ALLOWED_EMAILS": "lead@example.com,analyst@example.com", "KB_REFRESH_SECONDS": "0"}
    served = []
    monkeypatch.setattr(server.FastMCP, "run", lambda self, **kwargs: served.append(self))
    for url in ("https://quiet-river-demo.trycloudflare.com", "http://localhost:8080"):
        assert server.main({**env, "KB_PUBLIC_URL": url}) == 2 and not served
        refusal = capsys.readouterr().err
        assert refusal.startswith("kb-connector: the connector cannot start:\n  - KB_PUBLIC_URL names a temporary or ")
        assert "deploy the connector to the organization's own infrastructure at a permanent address" in refusal
        assert "KB_OPERATOR_TEST=1 and KB_OPERATOR_ADDRESSES" in refusal
    assert server.main({**env, **OPERATOR}) == 0 and served[-1].auth.policy.operators == {"lead@example.com"}
    (line,) = [message for message in caplog.messages if message.startswith("TEST ONLY")]
    assert "operator-only test mode at https://quiet-river-demo.trycloudflare.com." in line
    assert "The address is temporary and must not be given to anyone" in line
    assert "a restart of this process, this machine or its tunnel ends it." in line
    assert "Only lead@example.com can sign in." in line
    assert line.endswith(" can sign in. " + TEARDOWN)


TEARDOWN = "List each thing this test needs before setting it up, and remove every one as soon as the test ends."
REFERENCE = Path(__file__).resolve().parents[1] / "references" / "connector.md"


def test_the_start_line_of_a_test_on_a_deployment_asks_for_the_same_list(published, monkeypatch, caplog, firestore):
    env = {"KB_SOURCE_DIR": str(published), "KB_PUBLIC_URL": "https://kb.example.com", "KB_GOOGLE_CLIENT_ID": CLIENT_ID,
           "KB_GOOGLE_CLIENT_SECRET": "test-secret", "KB_ALLOWED_EMAILS": "lead@example.com", "KB_REFRESH_SECONDS": "0",
           **firestore, **OPERATOR}
    monkeypatch.setattr(server.FastMCP, "run", lambda self, **kwargs: None)
    assert server.main(env) == 0
    (line,) = [message for message in caplog.messages if message.startswith("TEST ONLY")]
    assert line.endswith("Do not give this address to anyone while the mode is on. Only lead@example.com can sign in. " + TEARDOWN)


def test_the_reference_shows_the_start_line_word_for_word_and_names_the_list(published, monkeypatch, caplog):
    env = {"KB_SOURCE_DIR": str(published), "KB_PUBLIC_URL": "http://localhost:8080", "KB_GOOGLE_CLIENT_ID": CLIENT_ID,
           "KB_GOOGLE_CLIENT_SECRET": "test-secret", "KB_ALLOWED_EMAILS": "lead@example.com", "KB_REFRESH_SECONDS": "0",
           **OPERATOR}
    monkeypatch.setattr(server.FastMCP, "run", lambda self, **kwargs: None)
    assert server.main(env) == 0
    (line,) = [message for message in caplog.messages if message.startswith("TEST ONLY")]
    reference = REFERENCE.read_text(encoding="utf-8")
    assert f"<time> WARNING kb_connector: {line}\n".replace("lead@example.com", "<you@example.com>") in reference
    assert "teardown.py add" in reference and "../../synthesis-agent-guardrails/references/teardown.md" in reference


def test_main_starts_localhost_written_with_a_trailing_dot_as_the_operators_own_test(published, monkeypatch, caplog):
    env = {"KB_SOURCE_DIR": str(published), "KB_PUBLIC_URL": "http://localhost.:8080", "KB_GOOGLE_CLIENT_ID": CLIENT_ID,
           "KB_GOOGLE_CLIENT_SECRET": "test-secret", "KB_ALLOWED_EMAILS": "lead@example.com", "KB_REFRESH_SECONDS": "0",
           **OPERATOR}
    served = []
    monkeypatch.setattr(server.FastMCP, "run", lambda self, **kwargs: served.append(self))
    assert server.main(env) == 0 and len(served) == 1  # as http://localhost:8080 starts
    (line,) = [message for message in caplog.messages if message.startswith("TEST ONLY")]
    assert "operator-only test mode at http://localhost.:8080. The address is temporary" in line


def test_main_refuses_the_memory_store_outside_the_operators_own_test_and_warns_of_it_at_every_start_inside(
        published, monkeypatch, caplog, capsys):
    from key_value.aio.stores.memory import MemoryStore
    env = {"KB_SOURCE_DIR": str(published), "KB_PUBLIC_URL": "https://kb.example.com", "KB_GOOGLE_CLIENT_ID": CLIENT_ID,
           "KB_GOOGLE_CLIENT_SECRET": "test-secret", "KB_ALLOWED_EMAILS": "lead@example.com", "KB_REFRESH_SECONDS": "0"}
    warning = "KB_OAUTH_STORE=memory: sign-ins live in this process only, so every restart signs everyone out"
    served = []
    monkeypatch.setattr(server.FastMCP, "run", lambda self, **kwargs: served.append(self))
    for store in ({}, {"KB_OAUTH_STORE": "memory"}):                            # no store named, and memory named on purpose
        assert server.main({**env, **store}) == 2 and not served
        refusal = capsys.readouterr().err
        assert refusal.startswith("kb-connector: the connector cannot start:\n  - KB_OAUTH_STORE must be firestore, with "
                                  "KB_STORAGE_ENCRYPTION_KEY: anything other people use must keep its state across restarts")
        assert "with more than one instance a memory store breaks sign-in outright" in refusal
        assert "memory is allowed only there, with KB_OPERATOR_TEST=1" in refusal
    for change in (OPERATOR,                                                    # the operator's own test, none named
                   {**OPERATOR, "KB_OAUTH_STORE": "memory"},                    # and named
                   {**OPERATOR, "KB_PUBLIC_URL": "http://localhost:8080"}):
        caplog.clear()
        assert server.main({**env, **change}) == 0
        assert caplog.messages.count(warning) == 1
        assert [record.levelno for record in caplog.records if record.getMessage() == warning] == [logging.WARNING]
    monkeypatch.setattr(server, "oauth_storage", lambda settings: MemoryStore())  # stands in for Firestore
    for mode in ({}, OPERATOR):
        caplog.clear()
        assert server.main({**env, **FIRESTORE, **mode}) == 0
        assert not [message for message in caplog.messages if "KB_OAUTH_STORE" in message]
    assert len(served) == 5


def test_no_log_level_hides_the_test_only_line(published, monkeypatch, caplog):
    env = {"KB_SOURCE_DIR": str(published), "KB_PUBLIC_URL": "http://localhost:8080", "KB_GOOGLE_CLIENT_ID": CLIENT_ID,
           "KB_GOOGLE_CLIENT_SECRET": "test-secret", "KB_ALLOWED_EMAILS": "lead@example.com", "KB_REFRESH_SECONDS": "0",
           **OPERATOR}
    monkeypatch.setattr(server.FastMCP, "run", lambda self, **kwargs: None)
    caplog.set_level(logging.ERROR, logger="kb_connector")  # what KB_LOG_LEVEL=ERROR does to the connector's own lines
    assert server.main(env) == 0
    (line,) = [record for record in caplog.records if record.getMessage().startswith("TEST ONLY")]
    assert line.levelno == logging.ERROR and "must not be given to anyone" in line.getMessage()
    assert not [message for message in caplog.messages if "KB_OAUTH_STORE=memory" in message]  # an ordinary warning

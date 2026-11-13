"""Settings from the environment: defaults, every problem reported at once, nothing served without sign-in, and
no temporary address and no memory sign-in store outside the operator's own test."""

import pytest

from kb_connector import config
from kb_connector.config import ConfigError, load

KEY = "A" * 43 + "="
BASE = {"KB_GIT_URL": "git@git.example.com:example/knowledge-plugin.git", "KB_PUBLIC_URL": "https://kb.example.com/",
        "KB_GOOGLE_CLIENT_ID": "id.apps.googleusercontent.com", "KB_GOOGLE_CLIENT_SECRET": "secret",
        "KB_ALLOWED_EMAILS": "lead@example.com", "KB_OAUTH_STORE": "firestore",
        "KB_STORAGE_ENCRYPTION_KEY": KEY}  # a deployment keeps its sign-ins in Firestore
OPERATOR = {"KB_OPERATOR_TEST": "1", "KB_OPERATOR_ADDRESSES": "lead@example.com"}  # the operator-only test mode


def problems(env):
    with pytest.raises(ConfigError) as caught:
        load(env)
    return str(caught.value)


def test_defaults():
    settings = load(BASE)
    assert settings.public_url == "https://kb.example.com" and settings.refresh_seconds == 600
    assert settings.search_limit == 10 and settings.port == 8080
    assert settings.document_url == "kb:{id}" and settings.token_cache_seconds == 300
    assert settings.firestore_prefix == "kb-connector" and settings.allowed_redirect_uris == ()
    assert settings.work_dir == "" and settings.host == "0.0.0.0" and settings.server_name == "Knowledge base"


def test_overrides():
    settings = load({**BASE, "KB_REFRESH_SECONDS": "0", "PORT": "9000", "KB_OAUTH_STORE": "Firestore",
                     "KB_STORAGE_ENCRYPTION_KEY": KEY, "KB_ALLOWED_REDIRECT_URIS": "https://a.example/cb, https://b.example/*",
                     "KB_DOCUMENT_URL_TEMPLATE": "https://git.example.com/kb/src/{commit}/{source_path}",
                     "KB_GIT_KNOWN_HOSTS": "git.example.com ssh-ed25519 AAAA\n", "KB_LOG_LEVEL": "debug"})
    assert settings.refresh_seconds == 0 and settings.port == 9000 and settings.oauth_store == "firestore"
    assert settings.log_level == "DEBUG" and load(BASE).log_level == "INFO"
    assert settings.allowed_redirect_uris == ("https://a.example/cb", "https://b.example/*")
    assert settings.known_hosts == "git.example.com ssh-ed25519 AAAA"


def test_every_problem_is_reported_together():
    text = problems({"KB_PUBLIC_URL": "http://kb.example.com", "KB_SEARCH_LIMIT": "500", "PORT": "x"})
    for expected in ("set exactly one of KB_GIT_URL", "KB_PUBLIC_URL must be the service's https://",
                     "KB_GOOGLE_CLIENT_ID is required", "KB_GOOGLE_CLIENT_SECRET is required",
                     "KB_ALLOWED_EMAILS or KB_ALLOWED_GROUPS is required", "KB_SEARCH_LIMIT must be a whole number from 1 to 50",
                     "PORT must be a whole number", "KB_OAUTH_STORE must be firestore, with KB_STORAGE_ENCRYPTION_KEY"):
        assert expected in text


@pytest.mark.parametrize("change, expected", [
    ({"KB_SOURCE_DIR": "/srv/kb"}, "set exactly one of"),
    ({"KB_OAUTH_STORE": "redis"}, "KB_OAUTH_STORE must be one of memory, firestore"),
    ({"KB_STORAGE_ENCRYPTION_KEY": ""}, "KB_OAUTH_STORE=firestore needs KB_STORAGE_ENCRYPTION_KEY"),
    ({"KB_STORAGE_ENCRYPTION_KEY": "short"}, "KB_OAUTH_STORE=firestore needs KB_STORAGE_ENCRYPTION_KEY"),
    ({"KB_DOCUMENT_URL_TEMPLATE": "https://x.example/{commit}"}, "needs {id} or {source_path}"),
    ({"KB_DOCUMENT_URL_TEMPLATE": "https://x.example/{id}/{secret}"}, "may use only {id}, {source_path}, {commit}"),
    ({"KB_DOCUMENT_URL_TEMPLATE": "https://x.example/{id"}, "may use only"),
    ({"KB_ALLOWED_EMAILS": "lead@example.com, example.com"}, "comma-separated email addresses"),
    ({"KB_REFRESH_SECONDS": "-5"}, "KB_REFRESH_SECONDS must be a whole number from 0 to 86400"),
    ({"KB_PUBLIC_URL": "kb.example.com"}, "KB_PUBLIC_URL must be"),
    ({**OPERATOR, "KB_OPERATOR_ADDRESSES": "lead"}, "KB_OPERATOR_ADDRESSES must be comma-separated email addresses"),
    ({"KB_LOG_LEVEL": "loud"}, "KB_LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR or CRITICAL, not 'LOUD'"),
])
def test_a_bad_value_stops_the_start(change, expected):
    assert expected in problems({**BASE, **change})


def test_the_operator_only_test_mode_is_one_switch_and_the_operators_own_addresses():
    assert load(BASE).operator_addresses == "" and load({**BASE, "KB_OPERATOR_TEST": "0"}).operator_addresses == ""
    assert load({**BASE, **OPERATOR}).operator_addresses == "lead@example.com"  # a permanent address may run the test too
    two = load({**BASE, "KB_OPERATOR_TEST": " 1 ", "KB_OPERATOR_ADDRESSES": " Lead@Example.com, second@example.com "})
    assert two.operator_addresses == "Lead@Example.com, second@example.com"


@pytest.mark.parametrize("change", [
    {"KB_OPERATOR_TEST": "1"},                                               # the mode with no operator named
    {"KB_OPERATOR_TEST": "1", "KB_OPERATOR_ADDRESSES": " , "},               # only separators: still nobody
    {"KB_OPERATOR_ADDRESSES": "lead@example.com"},                           # an operator named, the mode not on
    {"KB_OPERATOR_TEST": "0", "KB_OPERATOR_ADDRESSES": "lead@example.com"},
    {"KB_OPERATOR_TEST": "yes", "KB_OPERATOR_ADDRESSES": "lead@example.com"},  # only 1 turns it on
    {"KB_OPERATOR_TEST": "true"},
])
def test_a_test_mode_set_by_halves_stops_the_start(change):
    assert ("the operator-only test mode needs both KB_OPERATOR_TEST=1 and KB_OPERATOR_ADDRESSES"
            in problems({**BASE, **change}))


THREE = "lead@example.com, second@example.com, third@example.com"


def test_the_operator_addresses_are_one_persons_own_accounts_three_at_most():
    assert load({**BASE, **OPERATOR, "KB_OPERATOR_ADDRESSES": THREE}).operator_addresses == THREE
    twice = THREE + ", LEAD@Example.com ,third@example.com"                     # an address named twice is one address
    assert load({**BASE, **OPERATOR, "KB_OPERATOR_ADDRESSES": twice}).operator_addresses == twice
    for more, count in ((", fourth@example.com", 4), (", fourth@example.com, LEAD@example.com, fifth@example.com", 5)):
        text = problems({**BASE, **OPERATOR, "KB_OPERATOR_ADDRESSES": THREE + more})
        assert (f"KB_OPERATOR_ADDRESSES names {count} addresses and may name three at most: they are one person's own "
                "accounts, since the operator-only test mode is that person's test and nobody else's. Other people come "
                "in through KB_ALLOWED_EMAILS or KB_ALLOWED_GROUPS, on a deployed connector with the mode off") in text
    off = problems({**BASE, "KB_OPERATOR_ADDRESSES": THREE + ", fourth@example.com"})  # four named, the mode not on
    assert "names 4 addresses and may name three at most" in off and "needs both KB_OPERATOR_TEST=1" in off


NO_STORE = {name: value for name, value in BASE.items() if name not in ("KB_OAUTH_STORE", "KB_STORAGE_ENCRYPTION_KEY")}
MEMORY_REFUSED = ("KB_OAUTH_STORE must be firestore, with KB_STORAGE_ENCRYPTION_KEY: anything other people use must keep "
                  "its state across restarts, and with more than one instance a memory store breaks sign-in outright. A "
                  "single person's use is what the operator-only test mode is for, and memory is allowed only there, "
                  "with KB_OPERATOR_TEST=1")


@pytest.mark.parametrize("store", [
    {},                                                                # no store named
    {"KB_OAUTH_STORE": "memory"}, {"KB_OAUTH_STORE": " Memory "},      # memory named on purpose
    {"KB_OAUTH_STORE": "memory", "KB_STORAGE_ENCRYPTION_KEY": KEY},    # a key beside it changes nothing
])
def test_the_memory_sign_in_store_stops_the_start_outside_the_operators_own_test_named_or_not(store):
    for off in ({}, {"KB_OPERATOR_TEST": "0"}):
        text = problems({**NO_STORE, **store, **off})
        assert MEMORY_REFUSED in text and "KB_OAUTH_STORE must be one of" not in text  # one refusal, with its reason
    assert load({**NO_STORE, **store, **OPERATOR}).oauth_store == "memory"  # the operator's own test: the default, or named


def test_firestore_serves_in_both_modes_and_a_test_mode_set_by_halves_lets_no_memory_store_in():
    assert load(BASE).oauth_store == "firestore" and load({**BASE, **OPERATOR}).oauth_store == "firestore"
    for half in ({"KB_OPERATOR_ADDRESSES": "lead@example.com"},                          # an operator named, the mode not on
                 {"KB_OPERATOR_TEST": "yes", "KB_OPERATOR_ADDRESSES": "lead@example.com"}):  # only 1 turns it on
        text = problems({**NO_STORE, "KB_OAUTH_STORE": "memory", **half})
        assert MEMORY_REFUSED in text and "needs both KB_OPERATOR_TEST=1 and KB_OPERATOR_ADDRESSES" in text


def test_http_is_allowed_only_for_a_local_address():
    for url in ("http://127.0.0.1:8080", "http://localhost:8080"):  # local, so only as the operator's own test
        assert load({**BASE, **OPERATOR, "KB_PUBLIC_URL": url}).public_url == url
    assert "KB_PUBLIC_URL must be the service's https://" in problems({**BASE, **OPERATOR,
                                                                      "KB_PUBLIC_URL": "http://192.168.1.20:8080"})


@pytest.mark.parametrize("host", [
    "trycloudflare.com", "quiet-river-demo.trycloudflare.com", "demo.ngrok.io", "demo.ngrok.app", "demo.ngrok-free.app",
    "demo.ngrok.dev", "demo.ngrok-free.dev", "demo.ngrok.pizza", "demo.ngrok-free.pizza", "demo.loca.lt",
    "demo.localtunnel.me", "demo.serveo.net", "demo.serveousercontent.com", "demo.localhost.run", "demo.lhr.life",
    "demo.lhr.rocks", "demo.a.pinggy.io", "demo.a.pinggy.link", "demo.run.pinggy-free.link",
    "demo-8080.use.devtunnels.ms", "demo-8080.app.github.dev",                     # a tunnel service, at any depth
    "localhost", "kb.localhost", "laptop.local", "LOCALHOST", "Demo.TryCloudflare.COM", "demo.trycloudflare.com.",
    "127.0.0.1", "0.0.0.0", "::1", "10.1.2.3", "172.16.5.4", "192.168.1.20", "169.254.10.10", "100.100.100.100",
    "fd12:3456:789a::1", "fe80::1",                                                # no address the internet can reach
    "127.1", "2130706433", "0x7f000001",                                           # an IP address in an old spelling
])
def test_a_tunnel_host_a_local_name_and_an_unreachable_ip_are_temporary(host):
    assert config.temporary(host) is True


@pytest.mark.parametrize("host", [
    "kb.example.com", "nottrycloudflare.com", "trycloudflare.com.example.com", "ngrok.io.example.org",
    "my-ngrok.app.example", "localhost.example.com", "local.example.com", "mylocalhost", "notlocal", "kb.locale",
    "8.8.8.8", "172.32.0.1", "2606:4700:4700::1111", "", None,
])
def test_a_look_alike_host_and_a_public_address_are_not_temporary(host):
    assert config.temporary(host) is False


@pytest.mark.parametrize("url, host", [
    ("https://quiet-river-demo.trycloudflare.com", "quiet-river-demo.trycloudflare.com"),  # under a listed host
    ("HTTPS://Demo.TryCloudflare.COM/", "demo.trycloudflare.com"),                         # upper case
    ("https://demo.ngrok-free.app:8443", "demo.ngrok-free.app"),                           # a port in the address
    ("http://localhost:8080", "localhost"),
    ("http://127.0.0.1:8080", "127.0.0.1"),
    ("http://[::1]:8080", "::1"),                                                          # an IPv6 literal
    ("https://[fd12:3456:789a::1]", "fd12:3456:789a::1"),
    ("https://0.0.0.0:8443", "0.0.0.0"),
    ("https://192.168.1.20", "192.168.1.20"),
    ("https://laptop.local", "laptop.local"),
])
def test_a_temporary_address_stops_the_start_and_names_both_ways_forward(url, host):
    text = problems({**BASE, "KB_PUBLIC_URL": url})
    assert f"KB_PUBLIC_URL names a temporary or local address ({host}): it lasts only while this machine" in text
    assert "deploy the connector to the organization's own infrastructure at a permanent address" in text
    assert "for the operator's own test, set KB_OPERATOR_TEST=1 and KB_OPERATOR_ADDRESSES" in text
    assert load({**BASE, **OPERATOR, "KB_PUBLIC_URL": url}).public_url == url.rstrip("/")  # the operator's own test
    assert "needs both KB_OPERATOR_TEST=1" in problems({**BASE, "KB_OPERATOR_TEST": "1", "KB_PUBLIC_URL": url})


@pytest.mark.parametrize("url", [
    "https://nottrycloudflare.com", "https://trycloudflare.com.example.com", "https://localhost.example.com:8443",
    "https://8.8.8.8", "https://[2606:4700:4700::1111]:8443",
])
def test_a_look_alike_host_starts_as_any_permanent_address_does(url):
    assert load({**BASE, "KB_PUBLIC_URL": url}).public_url == url.rstrip("/")


@pytest.mark.parametrize("url", ["https://kb.example.com/trycloudflare.com", "https://kb.example.com/?via=demo.ngrok.io"])
def test_a_listed_name_in_the_path_or_the_query_is_refused_as_a_path_or_a_query_and_not_as_temporary(url):
    text = problems({**BASE, "KB_PUBLIC_URL": url})
    assert "which is not allowed. Write it as https://kb.example.com" in text and "temporary" not in text


ORIGIN = ("KB_PUBLIC_URL must be an origin and nothing more: the scheme, the host and a port if it needs one, since the "
          "connector builds its own addresses (/mcp, /auth/callback) on it. It has ")


@pytest.mark.parametrize("url", [
    "https://kb.example.com", "https://kb.example.com/",                       # with a trailing slash or without
    "https://kb.example.com:8443", "HTTPS://KB.Example.COM:8443/",             # a port, and a host in upper case
    "https://[2606:4700:4700::1111]:8443/",
])
def test_an_origin_starts_with_a_trailing_slash_a_port_or_a_host_in_upper_case(url):
    assert load({**BASE, "KB_PUBLIC_URL": url}).public_url == url.rstrip("/")


@pytest.mark.parametrize("url, parts, origin", [
    ("https://kb.example.com/mcp", "a path, which is", "https://kb.example.com"),
    ("https://kb.example.com//", "a path, which is", "https://kb.example.com"),
    ("https://kb.example.com/;v=1", "a path, which is", "https://kb.example.com"),
    ("https://kb.example.com/?x=1", "a query, which is", "https://kb.example.com"),
    ("https://kb.example.com?", "a query, which is", "https://kb.example.com"),                 # an empty query is one
    ("https://kb.example.com#top", "a fragment, which is", "https://kb.example.com"),
    ("https://kb.example.com/#", "a fragment, which is", "https://kb.example.com"),
    ("https://reader:s3cret@kb.example.com", "a user-info part (user:password@), which is", "https://kb.example.com"),
    ("https://@kb.example.com:8443/", "a user-info part (user:password@), which is", "https://kb.example.com:8443"),
    ("HTTPS://Reader:S3cret@KB.Example.COM:8443/base/?token=t0ken-value#top",
     "a user-info part (user:password@), a path, a query and a fragment, which are", "https://kb.example.com:8443"),
    ("https://[2606:4700:4700::1111]:8443/mcp", "a path, which is", "https://[2606:4700:4700::1111]:8443"),
])
def test_a_path_a_query_a_fragment_or_a_user_info_part_stops_the_start_and_the_origin_is_shown(url, parts, origin):
    text = problems({**BASE, "KB_PUBLIC_URL": url})
    assert f"{ORIGIN}{parts} not allowed. Write it as {origin}\n" in text + "\n"
    assert "s3cret" not in text.lower() and "t0ken-value" not in text  # each part is named, never shown: it may be a secret
    assert "temporary" not in text and "must be the service's https://" not in text


def test_the_origin_shown_is_one_the_connector_takes():
    local = problems({**BASE, **OPERATOR, "KB_PUBLIC_URL": "http://localhost:8080/mcp"})
    assert "It has a path, which is not allowed. Write it as http://localhost:8080" in local
    plain = problems({**BASE, "KB_PUBLIC_URL": "http://kb.example.com/mcp"})  # http only for localhost: shown as https
    assert "It has a path, which is not allowed. Write it as https://kb.example.com" in plain
    assert "KB_PUBLIC_URL must be the service's https:// address (http:// only for localhost)" in plain


@pytest.mark.parametrize("url", ["https://kb.example.com:abc", "https://kb.example.com:99999", "https://kb.example.com:0",
                                 "https://kb.example.com:abc/mcp"])
def test_a_port_that_is_no_port_stops_the_start(url):
    text = problems({**BASE, "KB_PUBLIC_URL": url})
    assert "KB_PUBLIC_URL must be the service's https:// address" in text and "Write it as" not in text

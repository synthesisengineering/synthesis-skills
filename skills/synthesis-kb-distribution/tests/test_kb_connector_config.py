"""Settings from the environment: defaults, every problem reported at once, nothing served without sign-in."""

import pytest

from kb_connector.config import ConfigError, load

KEY = "A" * 43 + "="
BASE = {"KB_GIT_URL": "git@git.example.com:example/knowledge-plugin.git", "KB_PUBLIC_URL": "https://kb.example.com/",
        "KB_GOOGLE_CLIENT_ID": "id.apps.googleusercontent.com", "KB_GOOGLE_CLIENT_SECRET": "secret",
        "KB_ALLOWED_EMAILS": "lead@example.com"}


def problems(env):
    with pytest.raises(ConfigError) as caught:
        load(env)
    return str(caught.value)


def test_defaults():
    settings = load(BASE)
    assert settings.public_url == "https://kb.example.com" and settings.refresh_seconds == 600
    assert settings.oauth_store == "memory" and settings.search_limit == 10 and settings.port == 8080
    assert settings.document_url == "kb:{id}" and settings.token_cache_seconds == 300
    assert settings.firestore_prefix == "kb-connector" and settings.allowed_redirect_uris == ()
    assert settings.work_dir == "" and settings.host == "0.0.0.0" and settings.server_name == "Knowledge base"


def test_overrides():
    settings = load({**BASE, "KB_REFRESH_SECONDS": "0", "PORT": "9000", "KB_OAUTH_STORE": "Firestore",
                     "KB_STORAGE_ENCRYPTION_KEY": KEY, "KB_ALLOWED_REDIRECT_URIS": "https://a.example/cb, https://b.example/*",
                     "KB_DOCUMENT_URL_TEMPLATE": "https://git.example.com/kb/src/{commit}/{source_path}",
                     "KB_GIT_KNOWN_HOSTS": "git.example.com ssh-ed25519 AAAA\n"})
    assert settings.refresh_seconds == 0 and settings.port == 9000 and settings.oauth_store == "firestore"
    assert settings.allowed_redirect_uris == ("https://a.example/cb", "https://b.example/*")
    assert settings.known_hosts == "git.example.com ssh-ed25519 AAAA"


def test_every_problem_is_reported_together():
    text = problems({"KB_PUBLIC_URL": "http://kb.example.com", "KB_SEARCH_LIMIT": "500", "PORT": "x"})
    for expected in ("set exactly one of KB_GIT_URL", "KB_PUBLIC_URL must be the service's https://",
                     "KB_GOOGLE_CLIENT_ID is required", "KB_GOOGLE_CLIENT_SECRET is required",
                     "KB_ALLOWED_EMAILS is required", "KB_SEARCH_LIMIT must be a whole number from 1 to 50",
                     "PORT must be a whole number"):
        assert expected in text


@pytest.mark.parametrize("change, expected", [
    ({"KB_SOURCE_DIR": "/srv/kb"}, "set exactly one of"),
    ({"KB_OAUTH_STORE": "redis"}, "KB_OAUTH_STORE must be one of memory, firestore"),
    ({"KB_OAUTH_STORE": "firestore"}, "needs KB_STORAGE_ENCRYPTION_KEY"),
    ({"KB_OAUTH_STORE": "firestore", "KB_STORAGE_ENCRYPTION_KEY": "short"}, "needs KB_STORAGE_ENCRYPTION_KEY"),
    ({"KB_DOCUMENT_URL_TEMPLATE": "https://x.example/{commit}"}, "needs {id} or {source_path}"),
    ({"KB_DOCUMENT_URL_TEMPLATE": "https://x.example/{id}/{secret}"}, "may use only {id}, {source_path}, {commit}"),
    ({"KB_DOCUMENT_URL_TEMPLATE": "https://x.example/{id"}, "may use only"),
    ({"KB_ALLOWED_EMAILS": "lead@example.com, example.com"}, "comma-separated email addresses"),
    ({"KB_REFRESH_SECONDS": "-5"}, "KB_REFRESH_SECONDS must be a whole number from 0 to 86400"),
    ({"KB_PUBLIC_URL": "kb.example.com"}, "KB_PUBLIC_URL must be"),
])
def test_a_bad_value_stops_the_start(change, expected):
    assert expected in problems({**BASE, **change})


def test_http_is_allowed_only_for_a_local_address():
    assert load({**BASE, "KB_PUBLIC_URL": "http://127.0.0.1:8080"}).public_url == "http://127.0.0.1:8080"
    assert load({**BASE, "KB_PUBLIC_URL": "http://localhost:8080"}).public_url == "http://localhost:8080"

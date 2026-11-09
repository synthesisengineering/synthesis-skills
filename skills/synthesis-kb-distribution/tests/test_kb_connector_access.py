"""The access list on the claims Google's verifier produces, without Google."""

import pytest

from kb_connector.access import AccessPolicy, listed


def claims(email="lead@example.com", verified="true", hd=None, profile=True):
    data = {"sub": "1", "email": email, "email_verified": verified}
    if profile:
        data["google_user_data"] = {"email": email, "verified_email": verified in (True, "true")}
        if hd:
            data["google_user_data"]["hd"] = hd
    return data


POLICY = AccessPolicy.from_settings(" Lead@Example.com, analyst@example.com ,lead@example.com")


def test_a_listed_verified_address_is_allowed_whatever_its_case():
    assert POLICY.emails == {"lead@example.com", "analyst@example.com"}
    for email in ("lead@example.com", "LEAD@EXAMPLE.COM", " analyst@example.com "):
        decision = POLICY.decide(claims(email=email))
        assert decision.allowed and decision.reason == "allowed"
    assert POLICY.decide(claims(verified=True)).allowed  # userinfo reports a boolean


def test_an_address_not_on_the_list_is_refused_with_a_clear_message():
    decision = POLICY.decide(claims(email="someone@example.com"))
    assert not decision.allowed and decision.reason == "email_not_listed"
    assert decision.message == ("Access denied: someone@example.com is not on this knowledge base's access list. "
                                "Ask its administrator to add the address.")


@pytest.mark.parametrize("verified", ["false", False, None, "", "yes", 1])
def test_an_unverified_address_is_refused_even_when_listed(verified):
    decision = POLICY.decide(claims(verified=verified))
    assert not decision.allowed and decision.reason == "email_unverified"
    assert "has not verified" in decision.message


@pytest.mark.parametrize("value", [None, {}, {"sub": "1"}, {"email": "  "}, "not claims"])
def test_no_identity_is_refused(value):
    decision = POLICY.decide(value)
    assert not decision.allowed and decision.reason == "no_identity"


def test_hosted_domains_when_required_come_from_googles_userinfo():
    policy = AccessPolicy.from_settings("lead@example.com,friend@gmail.com", "Example.com")
    assert policy.decide(claims(hd="example.com")).allowed
    assert policy.decide({**claims(profile=False), "hd": "example.com"}).allowed  # an hd claim of its own
    for refused in (claims(hd="other.example"), claims(), claims(profile=False),
                    claims(email="friend@gmail.com")):  # a personal account has no hosted domain
        decision = policy.decide(refused)
        assert not decision.allowed and decision.reason == "domain_not_allowed"
        assert "allowed Google Workspace domain" in decision.message
    assert not policy.decide(claims(email="outsider@example.com", hd="example.com")).allowed


def test_an_empty_or_malformed_list_is_refused_at_start():
    for raw in ("", " , ", None):
        with pytest.raises(ValueError, match="nobody can sign in"):
            AccessPolicy.from_settings(raw)
    with pytest.raises(ValueError, match="not email addresses: example.com"):
        AccessPolicy.from_settings("lead@example.com,example.com")
    assert listed("B, a ,b,,") == ("b", "a")

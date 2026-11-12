"""Access by Google group: the roster from the Cloud Identity Groups API (replaced here by a fake), how
long a roster may be trusted, and the policy that lets a listed person or a group member in."""

import pytest

from kb_connector.access import AccessPolicy
from kb_connector.config import ConfigError, load
from kb_connector.groups import GroupRoster

GROUPS = {  # group address -> (resource name, pages of memberships)
    "leads@example.com": ("groups/leads", [
        [{"preferredMemberKey": {"id": "Lead@Example.com"}, "type": "USER"},
         {"preferredMemberKey": {"id": "assistants@example.com"}, "type": "GROUP"}],
        [{"preferredMemberKey": {"id": "analyst@example.com"}, "type": "USER"},
         {"preferredMemberKey": {"id": "leads@example.com"}, "type": "GROUP"}]]),  # a cycle, followed once
    "assistants@example.com": ("groups/assistants", [[{"preferredMemberKey": {"id": "ea@example.com"}, "type": "USER"},
                                                      {"preferredMemberKey": {}, "type": "OTHER"}]]),
}


class FakeDirectory:
    """groups:lookup and memberships, the two Cloud Identity reads the roster makes, with every path kept."""

    def __init__(self, groups=GROUPS):
        self.groups, self.paths, self.fail = groups, [], False

    def __call__(self, path):
        self.paths.append(path)
        if self.fail:
            raise RuntimeError("Cloud Identity API answered 403 for groups:lookup: permission denied")
        if path.startswith("groups:lookup?groupKey.id="):
            return {"name": self.groups[path.split("=", 1)[1]][0]}
        name, query = path.split("/memberships?")
        pages = next(p for n, p in self.groups.values() if n == name)
        index = int(query.split("pageToken=")[1]) if "pageToken=" in query else 0
        return {"memberships": pages[index], **({"nextPageToken": str(index + 1)} if index + 1 < len(pages) else {})}


class Clock:
    def __init__(self):
        self.now = 1_000_000.0

    def __call__(self):
        return self.now


def roster(directory=None, clock=None):
    return GroupRoster(["leads@example.com"], 300, directory or FakeDirectory(), clock or Clock())


def claims(email):
    return {"email": email, "email_verified": "true"}


def test_the_roster_reads_every_page_and_follows_nested_groups_once():
    directory = FakeDirectory()
    people = roster(directory)
    assert people.refresh() and people.last_error == ""
    assert people.members == {"lead@example.com", "analyst@example.com", "ea@example.com"}
    assert directory.paths == ["groups:lookup?groupKey.id=leads@example.com",
                               "groups/leads/memberships?view=FULL&pageSize=500",
                               "groups:lookup?groupKey.id=assistants@example.com",
                               "groups/assistants/memberships?view=FULL&pageSize=500",
                               "groups/leads/memberships?view=FULL&pageSize=500&pageToken=1"]


def test_a_failed_read_keeps_the_last_roster_for_three_intervals_then_refuses():
    directory, clock = FakeDirectory(), Clock()
    people = roster(directory, clock)
    assert people.contains("lead@example.com") is None  # never read: nobody gets in through a group
    assert people.refresh() and people.contains("lead@example.com") and people.contains("x@example.com") is False
    directory.fail = True
    clock.now += 600
    assert not people.refresh() and "403" in people.last_error
    assert people.contains("lead@example.com") and people.health()["status"] == "ok"
    assert people.health()["last_refresh_failed"]
    clock.now += 301  # more than three intervals since the last good read
    assert people.contains("lead@example.com") is None and people.health()["status"] == "stale"
    directory.fail = False
    assert people.refresh() and people.contains("lead@example.com") and not people.health()["last_refresh_failed"]


def test_a_member_is_let_in_and_a_stale_roster_refuses_with_a_reason():
    clock = Clock()
    people = roster(clock=clock)
    policy = AccessPolicy.from_settings("", "", people)  # groups alone are enough
    assert policy.decide(claims("ea@example.com")).reason == "group_unchecked"
    assert people.refresh()
    assert policy.decide(claims("EA@example.com")).reason == "allowed_by_group"
    refused = policy.decide(claims("outsider@example.com"))
    assert not refused.allowed and refused.reason == "email_not_listed"
    assert not policy.decide({"email": "ea@example.com", "email_verified": "false"}).allowed
    clock.now += 901
    stale = policy.decide(claims("ea@example.com"))
    assert not stale.allowed and stale.reason == "group_unchecked"
    assert "access groups could not be read just now" in stale.message


def test_a_listed_address_needs_no_group_and_hosted_domains_still_apply():
    people = roster()  # never read, so only the list can let anyone in
    policy = AccessPolicy.from_settings("owner@example.com", "example.com", people)
    assert policy.decide({**claims("owner@example.com"), "hd": "example.com"}).reason == "allowed"
    assert people.refresh()
    assert policy.decide(claims("lead@example.com")).reason == "domain_not_allowed"
    assert policy.decide({**claims("lead@example.com"), "hd": "example.com"}).reason == "allowed_by_group"


def test_the_operator_only_test_mode_refuses_a_group_member_who_is_not_the_operator():
    people = roster()
    assert people.refresh()
    policy = AccessPolicy.from_settings("", "", people, "lead@example.com")
    assert policy.decide(claims("Lead@Example.com")).reason == "allowed_by_group"
    refused = policy.decide(claims("ea@example.com"))  # in the group, which would let them in
    assert not refused.allowed and refused.reason == "operator_only_test_mode"
    assert "ea@example.com is not on this knowledge base's access list" in refused.message
    outside = AccessPolicy.from_settings("", "", people, "owner@example.com")  # an operator the group does not hold
    assert outside.decide(claims("owner@example.com")).reason == "email_not_listed"


def test_settings_take_groups_alone_and_refuse_neither():
    base = {"KB_SOURCE_DIR": "/kb", "KB_PUBLIC_URL": "https://kb.example.com", "KB_GOOGLE_CLIENT_ID": "id",
            "KB_GOOGLE_CLIENT_SECRET": "secret", "KB_OAUTH_STORE": "memory"}
    settings = load({**base, "KB_ALLOWED_GROUPS": "leads@example.com"})
    assert settings.allowed_emails == "" and settings.group_refresh_seconds == 300
    assert load({**base, "KB_ALLOWED_GROUPS": "a@example.com", "KB_GROUP_REFRESH_SECONDS": "60"}).group_refresh_seconds == 60
    for env, expected in (({}, "KB_ALLOWED_EMAILS or KB_ALLOWED_GROUPS is required"),
                          ({"KB_ALLOWED_GROUPS": "leads"}, "KB_ALLOWED_GROUPS must be comma-separated email addresses"),
                          ({"KB_ALLOWED_GROUPS": "a@example.com", "KB_GROUP_REFRESH_SECONDS": "30"},
                           "KB_GROUP_REFRESH_SECONDS must be a whole number from 60 to 86400")):
        with pytest.raises(ConfigError, match=expected):
            load({**base, **env})
    with pytest.raises(ValueError, match="both empty"):
        AccessPolicy.from_settings("", "", None)

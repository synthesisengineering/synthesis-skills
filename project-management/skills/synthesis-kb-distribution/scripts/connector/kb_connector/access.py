"""Who may read the knowledge base: an email access list or Google groups, a verified address, optional domains.

A person passes as listed in KB_ALLOWED_EMAILS or as a member of a group in KB_ALLOWED_GROUPS (groups.py keeps
that roster). The policy reads the claims Google's token verifier produced for a signed-in person: `email`,
`email_verified` (tokeninfo reports the string "true"; userinfo a boolean) and, when hosted domains are required,
`hd` from Google's userinfo (`google_user_data`). Every denial says why in words a person can act on. No
addresses and no groups are refused at start, since that would let nobody in. In the operator-only test mode
(KB_OPERATOR_ADDRESSES) nobody but the operator passes, and the operator only as the rules above allow.
"""

from __future__ import annotations

from dataclasses import dataclass

NOT_LISTED = "Access denied: {} is not on this knowledge base's access list. Ask its administrator to add the address."


def listed(raw: str) -> tuple:
    """A comma-separated setting as distinct, lowercased, trimmed entries."""
    return tuple(dict.fromkeys(item.strip().lower() for item in (raw or "").split(",") if item.strip()))


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str
    email: str
    message: str


class AccessPolicy:
    def __init__(self, emails, hosted_domains=(), roster=None, operators=()):
        self.emails = frozenset(e.strip().lower() for e in emails if e and e.strip())
        self.hosted_domains = frozenset(d.strip().lower() for d in hosted_domains if d and d.strip())
        self.roster = roster
        self.operators = frozenset(o.strip().lower() for o in operators if o and o.strip())  # test mode only
        if not self.emails and roster is None:
            raise ValueError("KB_ALLOWED_EMAILS and KB_ALLOWED_GROUPS are both empty: list at least one address "
                             "or group, or nobody can sign in")
        malformed = sorted(e for e in self.emails if e.count("@") != 1 or e.startswith("@") or e.endswith("@"))
        if malformed:
            raise ValueError(f"KB_ALLOWED_EMAILS has entries that are not email addresses: {', '.join(malformed)}")

    @classmethod
    def from_settings(cls, emails: str, hosted_domains: str = "", roster=None, operators: str = "") -> "AccessPolicy":
        return cls(listed(emails), listed(hosted_domains), roster, listed(operators))

    def decide(self, claims) -> Decision:
        claims = claims if isinstance(claims, dict) else {}
        email = str(claims.get("email") or "").strip().lower()
        if not email:
            return Decision(False, "no_identity", "",
                            "Access denied: the sign-in did not identify a Google account. Sign in again.")
        if self.operators and email not in self.operators:  # the operator's own test: nobody else, whatever follows
            return Decision(False, "operator_only_test_mode", email, NOT_LISTED.format(email))
        verified = claims.get("email_verified")
        if not (verified is True or (isinstance(verified, str) and verified.strip().lower() == "true")):
            return Decision(False, "email_unverified", email,
                            f"Access denied: Google has not verified the address {email}.")
        if self.hosted_domains:
            profile = claims.get("google_user_data") if isinstance(claims.get("google_user_data"), dict) else {}
            domain = str(claims.get("hd") or profile.get("hd") or "").strip().lower()
            if domain not in self.hosted_domains:
                return Decision(False, "domain_not_allowed", email,
                                f"Access denied: {email} is not an account in an allowed Google Workspace domain.")
        if email in self.emails:
            return Decision(True, "allowed", email, "")
        member = self.roster.contains(email) if self.roster is not None else False
        if member:
            return Decision(True, "allowed_by_group", email, "")
        if member is None:
            return Decision(False, "group_unchecked", email,
                            "Access denied: the access groups could not be read just now. Try again in a few "
                            "minutes; if it keeps happening, tell the knowledge base's administrator.")
        return Decision(False, "email_not_listed", email, NOT_LISTED.format(email))

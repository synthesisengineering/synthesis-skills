"""Who may read the knowledge base: an email access list, a verified address, optional Workspace domains.

The policy reads the claims the Google token verifier produced for a signed-in person: `email`,
`email_verified` (tokeninfo reports the string "true"; userinfo a boolean) and, when hosted domains
are required, `hd` from Google's userinfo (`google_user_data`). Every denial says why in words a
person can act on. An empty access list is refused at start, since it would let nobody in.
"""

from __future__ import annotations

from dataclasses import dataclass


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
    def __init__(self, emails, hosted_domains=()):
        self.emails = frozenset(e.strip().lower() for e in emails if e and e.strip())
        self.hosted_domains = frozenset(d.strip().lower() for d in hosted_domains if d and d.strip())
        if not self.emails:
            raise ValueError("KB_ALLOWED_EMAILS is empty: list at least one address, or nobody can sign in")
        malformed = sorted(e for e in self.emails if e.count("@") != 1 or e.startswith("@") or e.endswith("@"))
        if malformed:
            raise ValueError(f"KB_ALLOWED_EMAILS has entries that are not email addresses: {', '.join(malformed)}")

    @classmethod
    def from_settings(cls, emails: str, hosted_domains: str = "") -> "AccessPolicy":
        return cls(listed(emails), listed(hosted_domains))

    def decide(self, claims) -> Decision:
        claims = claims if isinstance(claims, dict) else {}
        email = str(claims.get("email") or "").strip().lower()
        if not email:
            return Decision(False, "no_identity", "",
                            "Access denied: the sign-in did not identify a Google account. Sign in again.")
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
        if email not in self.emails:
            return Decision(False, "email_not_listed", email,
                            f"Access denied: {email} is not on this knowledge base's access list. "
                            "Ask its administrator to add the address.")
        return Decision(True, "allowed", email, "")

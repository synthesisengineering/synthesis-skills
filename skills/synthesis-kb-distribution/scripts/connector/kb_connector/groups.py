"""Access by Google group: who is in each allowed group now, read from the Cloud Identity Groups API.

The roster lists every member of each group in KB_ALLOWED_GROUPS at start and every
KB_GROUP_REFRESH_SECONDS, following nested groups, as the service's own account (Application Default
Credentials; on Cloud Run, the service account) with the read-only groups scope. An administrator lets
that account read groups (references/connector.md, section 7). A failed refresh keeps the last good
roster for at most three intervals; after that nobody gets in through a group until a refresh
succeeds (the email list still works), so a roster that cannot be read never lets anyone in for long.
"""

from __future__ import annotations

import logging
import threading
import time
from urllib.parse import quote

LOG = logging.getLogger("kb_connector")
API = "https://cloudidentity.googleapis.com/v1/"
SCOPE = "https://www.googleapis.com/auth/cloud-identity.groups.readonly"


def google_reader():
    """A GET of one Cloud Identity API path as the service's own account: the JSON body, or an error."""
    import google.auth
    from google.auth.transport.requests import AuthorizedSession
    session = AuthorizedSession(google.auth.default(scopes=[SCOPE])[0])

    def get(path: str) -> dict:
        response = session.get(API + path, timeout=30)
        if response.status_code != 200:
            raise RuntimeError(f"Cloud Identity API answered {response.status_code} for {path.split('?')[0]}: "
                               f"{response.text[:300]}")
        return response.json()
    return get


class GroupRoster:
    """The people in the allowed groups, swapped whole by refresh() so a check never sees half a list."""

    def __init__(self, groups, refresh_seconds: int = 300, read=None, clock=time.time):
        self.groups = tuple(groups)
        self.refresh_seconds, self.read, self.clock = refresh_seconds, read, clock
        self.members = frozenset()
        self.refreshed_at = self.attempted_at = None
        self.last_error = ""
        self._stop = threading.Event()
        self._thread = None

    def people_in(self, group: str, seen: set) -> set:
        """Everyone in one group, each nested group followed once."""
        if group in seen:
            return set()
        seen.add(group)
        name = self.read("groups:lookup?groupKey.id=" + quote(group, safe="@"))["name"]
        people, token = set(), ""
        while True:
            page = self.read(f"{name}/memberships?view=FULL&pageSize=500" + (f"&pageToken={quote(token)}" if token else ""))
            for membership in page.get("memberships", []):
                key = str((membership.get("preferredMemberKey") or {}).get("id") or "").strip().lower()
                if key and membership.get("type") == "GROUP":
                    people |= self.people_in(key, seen)
                elif key:
                    people.add(key)
            token = page.get("nextPageToken") or ""
            if not token:
                return people

    def refresh(self) -> bool:
        """Read every group again; on any failure keep the last good roster. True when the read succeeded."""
        self.attempted_at = self.clock()
        try:
            self.read = self.read or google_reader()
            seen, people = set(), set()
            for group in self.groups:
                people |= self.people_in(group, seen)
            self.members, self.refreshed_at, self.last_error = frozenset(people), self.attempted_at, ""
            LOG.info("access groups read: %d people in %d groups", len(people), len(seen))
            return True
        except Exception as error:  # noqa: BLE001 - any failure keeps the last good roster, for a while
            self.last_error = str(error)[:500] or type(error).__name__
            LOG.error("access group refresh failed: %s", self.last_error)
            return False

    def current(self) -> bool:
        """Recent enough to let anyone in: read within the last three refresh intervals."""
        return self.refreshed_at is not None and self.clock() - self.refreshed_at <= 3 * self.refresh_seconds

    def contains(self, email: str):
        """True or False from a current roster; None when it is not current, which refuses."""
        return (email in self.members) if self.current() else None

    def start(self) -> None:
        """Refresh on a daemon thread every refresh_seconds."""
        if self._thread:
            return

        def loop():
            while not self._stop.wait(self.refresh_seconds):
                self.refresh()
        self._thread = threading.Thread(target=loop, name="kb-groups", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def health(self) -> dict:
        stamp = None if self.refreshed_at is None else time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.refreshed_at))
        return {"status": "ok" if self.current() else "stale", "refreshed_at": stamp,
                "last_refresh_failed": bool(self.last_error)}

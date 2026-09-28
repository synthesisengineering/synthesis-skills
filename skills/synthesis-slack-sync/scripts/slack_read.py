"""Slack's documented read-only Web API, with account-bound request custody."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import re


class SlackRead:
    def __init__(self, entry, declared, transport):
        if not re.fullmatch(r"[a-z0-9-]+\.slack\.com", entry.domain):
            raise ValueError("declare an exact Slack domain")
        if not re.fullmatch(
            r"T[A-Z0-9]+", declared.get("team_id", "")
        ) or not re.fullmatch(r"[UW][A-Z0-9]+", declared.get("user_id", "")):
            raise ValueError(
                "declare exact Slack team_id and user_id for read-only user-token acquisition"
            )
        if set(declared) != {"kind", "team_id", "user_id"}:
            raise ValueError("unknown or missing Slack adapter fields")
        self.entry, self.declared, self.transport = entry, declared, transport
        self.channels = {}
        self.search_pages = {}

    def readiness(self):
        value, call = self.transport.call("auth.test")
        if (
            value.get("team_id") != self.declared["team_id"]
            or value.get("user_id") != self.declared["user_id"]
            or value.get("url") != "https://" + self.entry.domain + "/"
            or value.get("bot_id")
        ):
            raise ValueError(
                "Slack identity does not match exact declared user/workspace"
            )
        return {
            "status": "authenticated",
            "team_id": value["team_id"],
            "user_id": value["user_id"],
            "tool_call_id": call,
            "observed_at": datetime.now().astimezone().isoformat(),
            "capabilities": "read endpoints verified only when actually consumed",
        }

    def describe(self, channel_id):
        value, call = self.transport.call("conversations.info", {"channel": channel_id})
        channel = value.get("channel", {})
        if channel.get("id") != channel_id:
            raise ValueError("Slack conversation identity differs")
        if channel.get("is_im") is True:
            user = channel.get("user")
            if not isinstance(user, str) or not re.fullmatch(r"[UW][A-Z0-9]+", user):
                raise ValueError("Slack DM lacks a stable search peer")
            query = f"in:<@{user}>"
        else:
            name = channel.get("name")
            if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9_-]+", name):
                raise ValueError(
                    "Slack conversation lacks a supported exact search name"
                )
            query = "in:" + name
        self.channels[channel_id] = query
        return call

    def read_channel(self, *, channel_id, oldest, latest, cursor, limit, detail):
        if detail != "detailed" or channel_id not in self.channels:
            raise ValueError("undeclared Slack history request")
        args = {
            "channel": channel_id,
            "oldest": oldest,
            "latest": latest,
            "inclusive": "true",
            "limit": min(limit, 100),
        }
        if cursor:
            args["cursor"] = cursor
        value, call = self.transport.call("conversations.history", args)
        return {**value, "tool_call_id": call}

    def read_thread(self, *, channel_id, message_ts, cursor, limit, detail):
        if detail != "detailed" or channel_id not in self.channels:
            raise ValueError("undeclared Slack thread request")
        args = {"channel": channel_id, "ts": message_ts, "limit": min(limit, 100)}
        if cursor:
            args["cursor"] = cursor
        value, call = self.transport.call("conversations.replies", args)
        return {**value, "tool_call_id": call}

    def search_replies(self, *, channel_id, oldest, latest, cursor, limit, detail):
        if detail != "detailed" or channel_id not in self.channels:
            raise ValueError("undeclared Slack search request")
        # Search's documented day windows are deliberately wider; local exact
        # timestamp selection is applied after complete provider pagination.
        lower = datetime.fromtimestamp(float(oldest), timezone.utc).date() - timedelta(
            days=1
        )
        upper = datetime.fromtimestamp(float(latest), timezone.utc).date() + timedelta(
            days=1
        )
        if type(limit) is not int or limit < 1:
            raise ValueError("invalid Slack search page size")
        count = min(limit, 100)
        if cursor is not None and (
            not isinstance(cursor, str)
            or not re.fullmatch(r"page:[1-9]\d{0,2}", cursor)
        ):
            raise ValueError("invalid Slack search cursor")
        page = 1 if cursor is None else int(cursor[5:])
        if not 1 <= page <= 100:
            raise ValueError("invalid Slack search page")
        key = (channel_id, oldest, latest, count)
        previous = self.search_pages.get(key)
        if page != 1 and (previous is None or previous["next_page"] != page):
            raise ValueError("Slack search page has no exact preceding proof")
        value, call = self.transport.call(
            "search.messages",
            {
                "query": f"{self.channels[channel_id]} after:{lower} before:{upper}",
                "count": count,
                "page": page,
                "highlight": "false",
                "sort": "timestamp",
                "sort_dir": "asc",
            },
        )
        messages = value.get("messages", {})
        if not isinstance(messages, dict):
            raise ValueError("Slack search messages envelope absent")
        declarations = []
        for name, fields in (
            ("paging", ("pages", "count", "total")),
            ("pagination", ("page_count", "per_page", "total_count")),
        ):
            if name not in messages:
                continue
            paging = messages[name]
            if not isinstance(paging, dict):
                raise ValueError("Slack search pagination proof malformed")
            pages, per_page, total = (paging.get(field) for field in fields)
            if (
                any(
                    type(value) is not int
                    for value in (paging.get("page"), pages, per_page, total)
                )
                or paging["page"] != page
                or not 1 <= per_page <= count
                or not 0 <= total <= 10000
                or not 0 <= pages <= 100
                or pages != ((total + per_page - 1) // per_page)
                and not (total == 0 and pages == 1)
                or page > max(1, pages)
            ):
                raise ValueError(
                    "Slack search counts do not prove complete bounded pages"
                )
            first = (page - 1) * per_page + 1 if total else 0
            last = min(page * per_page, total)
            if "first" in paging or "last" in paging:
                if (
                    type(paging.get("first")) is not int
                    or type(paging.get("last")) is not int
                    or (paging["first"], paging["last"]) != (first, last)
                ):
                    raise ValueError("Slack search result range contradicts page proof")
            declarations.append((max(1, pages), per_page, total))
        if not declarations or len(set(declarations)) != 1:
            raise ValueError("Slack search pagination absent or contradictory")
        pages, per_page, total = declarations[0]
        if "total" in messages and (
            type(messages["total"]) is not int or messages["total"] != total
        ):
            raise ValueError("Slack search total contradicts pagination")
        if page != 1 and previous["declaration"] != declarations[0]:
            raise ValueError("Slack search pagination changed between pages")
        hits = messages.get("matches")
        expected = min(per_page, max(0, total - (page - 1) * per_page))
        if not isinstance(hits, list) or len(hits) != expected:
            raise ValueError("Slack search matches do not cover the declared page")
        seen = set() if page == 1 else set(previous["seen"])
        rows = []
        for hit in hits:
            if (
                not isinstance(hit, dict)
                or not isinstance(hit.get("channel"), dict)
                or hit.get("channel", {}).get("id") != channel_id
            ):
                raise ValueError("foreign Slack search match")
            ts = hit.get("ts")
            if not isinstance(ts, str) or not re.fullmatch(r"[1-9]\d{9}\.\d{6}", ts):
                raise ValueError("invalid Slack search timestamp")
            if ts in seen:
                raise ValueError(
                    "Slack search repeats a message across declared results"
                )
            seen.add(ts)
            if Decimal(oldest) <= Decimal(ts) <= Decimal(latest):
                rows.append(hit)
        if len(seen) != min(page * per_page, total):
            raise ValueError("Slack search cumulative result count differs")
        self.search_pages[key] = {
            "declaration": declarations[0],
            "seen": seen,
            "next_page": page + 1 if page < pages else None,
        }
        return {
            "ok": True,
            "messages": rows,
            "response_metadata": {
                "next_cursor": f"page:{page + 1}" if page < pages else ""
            },
            "has_more": page < pages,
            "tool_call_id": call,
        }

"""Declared Google Drive/Docs reads through the local workspace-mcp server.

The server already holds the account's Google grant, so acquisition adds no
credential. This process makes every call itself over the loopback MCP
endpoint and retains each raw response in custody; nothing is replayed from
agent-written text. Identity is the account's own primary calendar, the
inventory is a complete paged Drive search in the user corpus, and the
transcript tab is the one tab whose title matches the declared title within
the document's complete tab list, bound thereafter by that tab's ID.
"""

import datetime as dt
import hashlib
import json
import re

from mcp_client import _init_session, _parse_sse, bounded_post, call_tool_text, session_headers

KIND = "workspace-mcp-v1"
DOC = "application/vnd.google-apps.document"
LOOPBACK = re.compile(r"http://(?:127\.0\.0\.1|localhost|\[::1\]):\d{2,5}/mcp")
FIELDS = {"kind", "url", "name_contains", "positive_control_id", "window_field"}
FILE_ROW = re.compile(
    r'^- Name: "(?P<name>[^"\n]*)" \(ID: (?P<id>[A-Za-z0-9_-]+), Type: (?P<type>[^,\n]+), '
    r"Size: [^,\n]*, Created: (?P<created>[^,\n]+), Modified: (?P<modified>[^,)\n]+)[,)]"
)


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError("invalid declared Google source identifier")
    return value


def utc(value):
    moment = dt.datetime.fromisoformat(value)
    if moment.tzinfo is None:
        raise ValueError("inventory bound lacks an offset")
    return moment.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class McpTransport:
    """One bounded MCP session; every response is retained before it is read."""

    def __init__(self, url, capture):
        import httpx

        if not isinstance(url, str) or not LOOPBACK.fullmatch(url):
            raise ValueError("workspace-mcp acquisition requires a loopback http URL")
        self.url, self.capture, self.next_id = url, capture, 2
        self.client = httpx.Client(timeout=60, follow_redirects=False, trust_env=False)
        self.session = _init_session(
            self.client, url=url, capture=capture, client_name="fetch-meeting.py"
        )

    def call(self, tool, arguments):
        request_id, self.next_id = self.next_id, self.next_id + 1
        response = bounded_post(
            self.client,
            self.url,
            capture=self.capture,
            headers=session_headers(self.session),
            json={
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "tools/call",
                "params": {"name": tool, "arguments": arguments},
            },
        )
        digest = hashlib.sha256(response.content).hexdigest()
        receipt = self.capture.calls[-1]["path"]
        text = call_tool_text(_parse_sse(response.text, expected_id=request_id))
        return text, f"{receipt}#{digest}"

    def close(self):
        self.client.close()


class WorkspaceMcpRead:
    def __init__(self, cfg, transport):
        self.cfg, self.transport = cfg, transport
        self.account = cfg["google_account"]
        adapter = cfg.get("acquisition_adapter", {})
        if adapter.get("kind") != KIND or set(adapter) != FIELDS:
            raise ValueError("unknown or missing workspace-mcp adapter fields")
        if not isinstance(self.account, str) or not re.fullmatch(r"[^\s@'\"]+@[^\s@'\"]+", self.account):
            raise ValueError("declare one exact Google account email")
        self.control = identifier(adapter["positive_control_id"])
        self.field = adapter["window_field"]
        if self.field not in {"createdTime", "modifiedTime"}:
            raise ValueError("declare the provider inventory window_field: createdTime or modifiedTime")
        name = adapter["name_contains"]
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9 _.:-]{3,100}", name):
            raise ValueError("declare a plain name_contains filter")
        self.name = name
        title = cfg.get("transcript_tab_title")
        if not isinstance(title, str) or not title.strip() or "transcript_tab_id" in cfg:
            raise ValueError("workspace-mcp selects the transcript by transcript_tab_title alone")
        self.title = title
        self.url = adapter["url"]

    def readiness(self):
        text, call = self.transport.call("list_calendars", {"user_google_email": self.account})
        primary = re.findall(r'^- "[^"\n]*" \(Primary\) \(ID: ([^)\s]+)\)$', text, re.M)
        if primary != [self.account]:
            raise ValueError("Google authenticated account differs from the declared account")
        return {
            "status": "authenticated",
            "account": self.account,
            "observed_at": dt.datetime.now().astimezone().isoformat(),
            "tool_call_id": call,
            "native_acceptance": False,
        }

    def positive_control(self):
        text, call = self.transport.call(
            "get_drive_file_permissions",
            {"user_google_email": self.account, "file_id": self.control},
        )
        fields = dict(re.findall(r"^(File|ID|Type|Trashed): (.*)$", text, re.M))
        if (
            fields.get("ID") != self.control
            or fields.get("Type") != DOC
            or fields.get("Trashed") != "False"
            or self.name not in fields.get("File", "")
        ):
            raise ValueError(
                "positive control is not a live document the declared inventory query matches"
            )
        return {
            "observed": True,
            "source": "google-drive",
            "source_id": self.control,
            "account": self.account,
            "observed_at": dt.datetime.now().astimezone().isoformat(),
            "tool_call_id": call,
        }

    def list_documents(self, *, source, account, oldest, latest, cursor, limit):
        if source != "google-drive" or account != self.account:
            raise ValueError("foreign Google inventory request")
        # One user corpus without shared-drive items: Drive reports an
        # incomplete search only across several corpora, which this excludes.
        query = (
            f"name contains '{self.name}' and mimeType = '{DOC}' and trashed = false "
            f"and {self.field} >= '{utc(oldest)}' and {self.field} <= '{utc(latest)}'"
        )
        arguments = {
            "user_google_email": self.account,
            "query": query,
            "page_size": limit,
            "corpora": "user",
            "include_items_from_all_drives": False,
            "detailed": True,
        }
        if cursor is not None:
            arguments["page_token"] = cursor
        text, call = self.transport.call("search_drive_files", arguments)
        lines = text.split("\n")
        found = re.fullmatch(rf"Found (\d+) files for {re.escape(self.account)} matching .*:", lines[0])
        empty = len(lines) == 1 and re.fullmatch(r"No files found for '.*'\.", lines[0])
        if not found and not empty:
            raise ValueError("Google inventory response is not a declared-account file listing")
        rows, token = [], None
        for line in lines[1:]:
            if line.startswith("nextPageToken: ") and token is None:
                token = line[len("nextPageToken: ") :].strip()
                continue
            match = FILE_ROW.match(line)
            if match is None:
                if line.strip():
                    raise ValueError("unparsed line in a Google inventory page")
                continue
            if match["type"] != DOC or self.name not in match["name"]:
                raise ValueError("foreign document in Google inventory")
            rows.append(
                {
                    "source_id": identifier(match["id"]),
                    "occurred_at": dt.datetime.fromisoformat(
                        match["created" if self.field == "createdTime" else "modified"]
                    ).isoformat(),
                    "provider_time_field": self.field,
                }
            )
        if (int(found[1]) if found else 0) != len(rows):
            raise ValueError("Google inventory page does not hold the files it reports")
        return {
            "ok": True,
            "documents": rows,
            "next_cursor": token,
            "complete": not token,
            "tool_call_id": call,
        }

    def transcript(self, source_id):
        identifier(source_id)
        text, call = self.transport.call(
            "inspect_doc_structure",
            {"user_google_email": self.account, "document_id": source_id},
        )
        head = f"Document structure analysis for {source_id}:\n\n"
        body = text[len(head) :].rsplit("\n\nLink: ", 1)[0] if text.startswith(head) else ""
        try:
            tabs = json.loads(body).get("tabs")
        except (ValueError, AttributeError) as exc:
            raise ValueError("Google document tab inventory unavailable") from exc
        if (
            not isinstance(tabs, list)
            or not tabs
            or any(
                not isinstance(tab, dict)
                or not isinstance(tab.get("title"), str)
                or not re.fullmatch(r"[A-Za-z0-9._-]+", str(tab.get("tab_id")))
                for tab in tabs
            )
            or len({tab["tab_id"] for tab in tabs}) != len(tabs)
        ):
            raise ValueError("Google document tab inventory is malformed")
        chosen = [tab for tab in tabs if tab["title"] == self.title]
        if len(chosen) != 1:
            raise ValueError(
                f"declared transcript unavailable: {len(chosen)} tabs titled "
                f"{self.title!r}; owner review required"
            )
        calls, parts, transcript = [call], [], None
        for tab in tabs:
            content, read = self.transport.call(
                "get_doc_as_markdown",
                {
                    "user_google_email": self.account,
                    "document_id": source_id,
                    "tab_id": tab["tab_id"],
                    "include_comments": False,
                },
            )
            calls.append(read)
            if tab is chosen[0]:
                transcript = content
            else:
                parts.append(f"### {tab['title']}\n\n{content}")
        if not transcript.strip():
            raise ValueError("declared transcript tab is empty; owner review required")
        return {
            "transcript": transcript,
            "notes": "\n\n".join(parts),
            "transcript_tab_id": chosen[0]["tab_id"],
            "tab_ids": [tab["tab_id"] for tab in tabs],
            "raw_sha256": [read.rsplit("#", 1)[1] for read in calls],
        }

"""Declared Google Drive/Docs read adapter, with exact account/folder/tab identity.

API contracts: Drive v3 about.get/files.list/files.get; Docs v1 documents.get.
The timestamp field is explicitly declared; it is not inferred meeting time.
"""

from datetime import datetime
import re


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError("invalid declared Google source identifier")
    return value


class GoogleRead:
    def __init__(self, cfg, transport):
        self.cfg = cfg
        self.transport = transport
        self.account = cfg["google_account"]
        adapter = cfg.get("acquisition_adapter", {})
        if adapter.get("kind") != "google-rest-v1":
            raise ValueError(
                "complete structured acquisition requires explicitly selected google-rest-v1; MCP/plain-text has no inferred tab inventory or fallback"
            )
        if set(adapter) != {
            "kind",
            "token",
            "folder_id",
            "positive_control_id",
            "window_field",
        }:
            raise ValueError("unknown or missing Google adapter fields")
        if not isinstance(self.account, str) or not re.fullmatch(
            r"[^\s@]+@[^\s@]+", self.account
        ):
            raise ValueError("declare one exact Google account email")
        self.folder = identifier(adapter.get("folder_id"))
        self.control = identifier(adapter.get("positive_control_id"))
        self.field = adapter.get("window_field")
        if self.field not in {"createdTime", "modifiedTime"}:
            raise ValueError(
                "declare the provider inventory window_field: createdTime or modifiedTime"
            )
        identifier(cfg.get("transcript_tab_id"))

    def readiness(self):
        result, call = self.transport.call(
            "drive/about", {"fields": "user(emailAddress,permissionId)"}
        )
        if result.get("user", {}).get("emailAddress") != self.account:
            raise ValueError(
                "Google authenticated account differs from the declared account"
            )
        return {
            "status": "authenticated",
            "account": self.account,
            "observed_at": datetime.now().astimezone().isoformat(),
            "tool_call_id": call,
            "native_acceptance": False,
        }

    def positive_control(self):
        result, call = self.transport.call(
            "drive/file/" + self.control, {"fields": "id,mimeType,parents,trashed"}
        )
        if (
            result.get("id") != self.control
            or result.get("mimeType") != "application/vnd.google-apps.document"
            or self.folder not in result.get("parents", [])
            or result.get("trashed") is not False
        ):
            raise ValueError(
                "Google positive control is not the declared live document in the selected folder"
            )
        return {
            "observed": True,
            "source": "google-drive",
            "source_id": self.control,
            "account": self.account,
            "observed_at": datetime.now().astimezone().isoformat(),
            "tool_call_id": call,
        }

    def list_documents(self, *, source, account, oldest, latest, cursor, limit):
        if source != "google-drive" or account != self.account:
            raise ValueError("foreign Google inventory request")
        query = (
            f"'{self.folder}' in parents and trashed = false and mimeType = 'application/vnd.google-apps.document' "
            f"and {self.field} >= '{oldest}' and {self.field} <= '{latest}'"
        )
        params = {
            "q": query,
            "pageSize": limit,
            "corpora": "user",
            "fields": "kind,incompleteSearch,nextPageToken,files(id,name,mimeType,parents,createdTime,modifiedTime)",
        }
        if cursor is not None:
            params["pageToken"] = cursor
        result, call = self.transport.call("drive/files", params)
        if (
            result.get("kind") != "drive#fileList"
            or result.get("incompleteSearch") is not False
            or not isinstance(result.get("files"), list)
        ):
            raise ValueError("Google inventory completeness unavailable")
        rows = []
        for doc in result["files"]:
            if (
                not isinstance(doc, dict)
                or doc.get("mimeType") != "application/vnd.google-apps.document"
                or self.folder not in doc.get("parents", [])
            ):
                raise ValueError("foreign document in Google inventory")
            rows.append(
                {
                    "source_id": identifier(doc.get("id")),
                    "occurred_at": doc.get(self.field),
                    "provider_time_field": self.field,
                }
            )
        return {
            "ok": True,
            "documents": rows,
            "next_cursor": result.get("nextPageToken"),
            "complete": not result.get("nextPageToken"),
            "tool_call_id": call,
        }

    def document(self, source_id):
        result, call = self.transport.call(
            "docs/" + identifier(source_id), {"includeTabsContent": "true"}
        )
        if result.get("documentId") != source_id or not isinstance(
            result.get("tabs"), list
        ):
            raise ValueError(
                "Google document identity or complete structured tabs unavailable"
            )
        # documents.get(includeTabsContent=true) returns all tabs without paging.
        return {**result, "tabsComplete": True}, call

"""Select provider document tabs by stable ID; never infer absence from flattening."""

import json

MAX_BYTES = 8 * 1024 * 1024


def select_tabs(raw, *, transcript_tab_id):
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > MAX_BYTES:
        raise ValueError("document exceeds the bounded UTF-8 input")
    try:
        def pairs(items):
            result = {}
            for key, value in items:
                if key in result:
                    raise ValueError("duplicate document field")
                result[key] = value
            return result
        document = json.loads(raw, object_pairs_hook=pairs)
    except json.JSONDecodeError:
        return {
            "status": "unknown",
            "reason": "tab-inventory-unavailable",
            "transcript": None,
            "notes": None,
        }
    if not isinstance(document, dict) or not isinstance(document.get("tabs"), list):
        return {
            "status": "unknown",
            "reason": "tab-inventory-unavailable",
            "transcript": None,
            "notes": None,
        }
    if document.get("truncated") is True:
        return {
            "status": "unknown",
            "reason": "tab-inventory-incomplete",
            "transcript": None,
            "notes": None,
        }
    if not isinstance(transcript_tab_id, str) or not transcript_tab_id:
        return {
            "status": "unknown",
            "reason": "transcript-tab-id-not-declared",
            "transcript": None,
            "notes": None,
        }
    tabs = {}
    count = [0]

    def walk(values, depth=0):
        if depth > 12 or not isinstance(values, list):
            raise ValueError("invalid tab nesting")
        for tab in values:
            count[0] += 1
            if count[0] > 1000:
                raise ValueError("too many document tabs")
            if not isinstance(tab, dict):
                raise ValueError("invalid document tab")
            properties = tab.get("tabProperties", {})
            key = properties.get("tabId")
            if not isinstance(key, str) or not key or key in tabs:
                raise ValueError("missing or duplicate tab ID")
            tabs[key] = tab
            walk(tab.get("childTabs", []), depth + 1)

    walk(document["tabs"])

    def content(tab):
        node = tab.get("documentTab")
        if tab.get("truncated") is True or (
            isinstance(node, dict) and node.get("truncated") is True
        ):
            raise ValueError("tab content is truncated")
        if not isinstance(node, dict) or "body" not in node:
            raise ValueError("tab content was not returned")
        if not isinstance(node["body"], dict) or not isinstance(node["body"].get("content"), list):
            raise ValueError("tab body content structure unavailable")
        output = []
        nodes = [0]

        def flatten(value, depth=0):
            nodes[0] += 1
            if depth > 40 or nodes[0] > 100000:
                raise ValueError("document structure exceeded")
            if isinstance(value, dict):
                if "textRun" in value:
                    text = value["textRun"].get("content")
                    if not isinstance(text, str):
                        raise ValueError("invalid text run")
                    output.append(text)
                else:
                    recognized = False
                    for key in (
                        "content",
                        "paragraph",
                        "elements",
                        "table",
                        "tableRows",
                        "tableCells",
                        "body",
                    ):
                        if key in value:
                            recognized = True
                            flatten(value[key], depth + 1)
                    if not recognized and value and not set(value) <= {"startIndex", "endIndex", "sectionBreak"}:
                        raise ValueError("unsupported tab content structure")
            elif isinstance(value, list):
                for child in value:
                    flatten(child, depth + 1)
            else:
                raise ValueError("invalid tab content node")

        flatten(node["body"])
        return "".join(output)

    if transcript_tab_id not in tabs:
        # Missing from a response is only evidence of absence if the adapter
        # explicitly attests complete tab enumeration for this exact document.
        if document.get("tabsComplete") is not True:
            return {
                "status": "unknown",
                "reason": "tab-inventory-incomplete",
                "transcript": None,
                "notes": None,
            }
        try:
            notes = "\n".join(content(tab) for tab in tabs.values())
        except ValueError as exc:
            return {
                "status": "unknown",
                "reason": "tab-content-unavailable",
                "detail": str(exc),
                "transcript": None,
                "notes": None,
            }
        return {
            "status": "no-source",
            "reason": "transcript-tab-absent",
            "transcript_tab_id": transcript_tab_id,
            "transcript": None,
            "notes": notes,
        }
    try:
        transcript = content(tabs[transcript_tab_id])
        notes = "\n".join(
            content(tab) for key, tab in tabs.items() if key != transcript_tab_id
        )
    except ValueError as exc:
        return {
            "status": "unknown",
            "reason": "tab-content-unavailable",
            "detail": str(exc),
            "transcript": None,
            "notes": None,
        }
    if document.get("tabsComplete") is not True:
        return {
            "status": "unknown",
            "reason": "tab-inventory-incomplete",
            "transcript": None,
            "notes": None,
        }
    if not transcript.strip():
        return {
            "status": "no-source",
            "reason": "transcript-tab-empty",
            "transcript_tab_id": transcript_tab_id,
            "transcript": "",
            "notes": notes,
        }
    return {
        "status": "transcript",
        "reason": None,
        "transcript_tab_id": transcript_tab_id,
        "transcript": transcript,
        "notes": notes,
        "tab_ids": list(tabs),
    }

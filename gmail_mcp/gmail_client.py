import base64
from email.mime.text import MIMEText
from typing import Any

from googleapiclient.discovery import build

from .auth import load_credentials

_service = None


def get_service():
    global _service
    if _service is None:
        _service = build("gmail", "v1", credentials=load_credentials())
    return _service


def _header(headers: list[dict], name: str) -> str | None:
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return None


def _extract_bodies(payload: dict) -> tuple[str, str]:
    plain = ""
    html = ""

    def walk(part: dict) -> None:
        nonlocal plain, html
        mime = part.get("mimeType", "")
        data = part.get("body", {}).get("data")
        if mime == "text/plain" and data and not plain:
            plain = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        elif mime == "text/html" and data and not html:
            html = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        for sub in part.get("parts", []):
            walk(sub)

    walk(payload)
    return plain, html


def _extract_attachments(payload: dict) -> list[dict[str, Any]]:
    attachments = []

    def walk(part: dict) -> None:
        filename = part.get("filename")
        body = part.get("body", {})
        if filename and body.get("attachmentId"):
            attachments.append(
                {
                    "filename": filename,
                    "mimeType": part.get("mimeType"),
                    "attachmentId": body["attachmentId"],
                    "size": body.get("size", 0),
                }
            )
        for sub in part.get("parts", []):
            walk(sub)

    walk(payload)
    return attachments


def search_messages(query: str, max_results: int = 10) -> list[dict[str, Any]]:
    service = get_service()
    resp = (
        service.users()
        .messages()
        .list(userId="me", q=query, maxResults=max_results)
        .execute()
    )
    results = []
    for m in resp.get("messages", []):
        msg = (
            service.users()
            .messages()
            .get(
                userId="me",
                id=m["id"],
                format="metadata",
                metadataHeaders=["Subject", "From", "To", "Cc", "Bcc", "Date"],
            )
            .execute()
        )
        headers = msg["payload"]["headers"]
        results.append(
            {
                "id": msg["id"],
                "threadId": msg["threadId"],
                "labelIds": msg.get("labelIds", []),
                "snippet": msg.get("snippet", ""),
                "subject": _header(headers, "Subject"),
                "from": _header(headers, "From"),
                "to": _header(headers, "To"),
                "cc": _header(headers, "Cc"),
                "bcc": _header(headers, "Bcc"),
                "date": _header(headers, "Date"),
            }
        )
    return results


def get_message(message_id: str) -> dict[str, Any]:
    service = get_service()
    msg = (
        service.users()
        .messages()
        .get(userId="me", id=message_id, format="full")
        .execute()
    )
    headers = msg["payload"]["headers"]
    body, body_html = _extract_bodies(msg["payload"])
    return {
        "id": msg["id"],
        "threadId": msg["threadId"],
        "labelIds": msg.get("labelIds", []),
        "snippet": msg.get("snippet", ""),
        "subject": _header(headers, "Subject"),
        "from": _header(headers, "From"),
        "to": _header(headers, "To"),
        "cc": _header(headers, "Cc"),
        "bcc": _header(headers, "Bcc"),
        "date": _header(headers, "Date"),
        "body": body,
        "body_html": body_html,
        "attachments": _extract_attachments(msg["payload"]),
    }


def get_thread(thread_id: str) -> dict[str, Any]:
    service = get_service()
    thread = service.users().threads().get(userId="me", id=thread_id, format="full").execute()
    messages = []
    for msg in thread.get("messages", []):
        headers = msg["payload"]["headers"]
        body, body_html = _extract_bodies(msg["payload"])
        messages.append(
            {
                "id": msg["id"],
                "labelIds": msg.get("labelIds", []),
                "snippet": msg.get("snippet", ""),
                "subject": _header(headers, "Subject"),
                "from": _header(headers, "From"),
                "to": _header(headers, "To"),
                "cc": _header(headers, "Cc"),
                "bcc": _header(headers, "Bcc"),
                "date": _header(headers, "Date"),
                "body": body,
                "body_html": body_html,
                "attachments": _extract_attachments(msg["payload"]),
            }
        )
    return {"id": thread_id, "messages": messages}


def create_draft(
    to: str,
    subject: str,
    body: str,
    cc: str | None = None,
    bcc: str | None = None,
    reply_to_message_id: str | None = None,
) -> dict[str, Any]:
    service = get_service()

    message = MIMEText(body)
    message["To"] = to
    message["Subject"] = subject
    if cc:
        message["Cc"] = cc
    if bcc:
        message["Bcc"] = bcc

    thread_id = None
    if reply_to_message_id:
        original = (
            service.users()
            .messages()
            .get(
                userId="me",
                id=reply_to_message_id,
                format="metadata",
                metadataHeaders=["Message-ID", "References"],
            )
            .execute()
        )
        thread_id = original.get("threadId")
        headers = original["payload"]["headers"]
        original_message_id = _header(headers, "Message-ID")
        original_references = _header(headers, "References")
        if original_message_id:
            message["In-Reply-To"] = original_message_id
            message["References"] = (
                f"{original_references} {original_message_id}".strip()
                if original_references
                else original_message_id
            )

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    draft_body: dict[str, Any] = {"message": {"raw": raw}}
    if thread_id:
        draft_body["message"]["threadId"] = thread_id

    draft = service.users().drafts().create(userId="me", body=draft_body).execute()
    return {
        "draftId": draft["id"],
        "messageId": draft["message"]["id"],
        "threadId": draft["message"].get("threadId"),
    }


def list_labels() -> list[dict[str, Any]]:
    service = get_service()
    resp = service.users().labels().list(userId="me").execute()
    labels = []
    for l in resp.get("labels", []):
        detail = service.users().labels().get(userId="me", id=l["id"]).execute()
        labels.append(
            {
                "id": detail["id"],
                "name": detail["name"],
                "type": detail["type"],
                "messagesTotal": detail.get("messagesTotal", 0),
                "messagesUnread": detail.get("messagesUnread", 0),
                "threadsTotal": detail.get("threadsTotal", 0),
                "threadsUnread": detail.get("threadsUnread", 0),
            }
        )
    return labels

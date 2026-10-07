"""Meta (Messenger + Instagram) adapters via the Graph API (spec §5.1, Phase 2).

Both platforms share the Messenger Platform webhook shape (entry[].messaging[])
and send through the Page access token, so the logic lives in MetaAdapter and
the two subclasses differ only in their webhook `object` label and id field.

Per-channel credentials (channel.get_credentials()):
    page_access_token : the Page (or IG-linked Page) access token
    page_id           : the Facebook Page id        (Messenger)
    ig_id             : the Instagram account id     (Instagram)

App-level values (config, one Meta app): META_APP_SECRET, META_VERIFY_TOKEN.
The webhook callback URL + verify token are registered once in the Meta app
dashboard; connect() then subscribes each Page to the app.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import mimetypes
import os
import uuid
from datetime import timedelta

import requests
from flask import current_app

from app.channels.base import (
    ChannelAdapter,
    DownloadedMedia,
    NormalizedMedia,
    NormalizedMessage,
    SendResult,
)
from app.models.enums import AttachmentType

log = logging.getLogger(__name__)


def verify_signature(app_secret: str, raw_body: bytes, header: str | None) -> bool:
    """Validate the X-Hub-Signature-256 header (spec §5.1 CH-5)."""
    if not app_secret or not header or not header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(
        app_secret.encode(), raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, header)


def _attachment_type(att_type: str) -> AttachmentType:
    return {
        "image": AttachmentType.IMAGE,
        "audio": AttachmentType.AUDIO,
        "video": AttachmentType.FILE,
        "file": AttachmentType.FILE,
    }.get(att_type, AttachmentType.FILE)


class MetaAdapter(ChannelAdapter):
    reply_window = timedelta(hours=24)  # Meta's standard messaging window

    webhook_object = ""   # "page" | "instagram" — set by subclasses
    id_field = "page_id"  # which credential holds this channel's account id

    @property
    def _token(self) -> str:
        token = self.channel.get_credentials().get("page_access_token")
        if not token:
            raise RuntimeError("Meta channel has no page_access_token configured")
        return token

    def _graph(self, path: str) -> str:
        version = current_app.config.get("META_GRAPH_VERSION", "v21.0")
        return f"https://graph.facebook.com/{version}/{path}"

    def _timeout(self) -> int:
        return current_app.config.get("HTTP_TIMEOUT", 30)

    # ---------------- inbound ----------------
    def parse_webhook(self, payload: dict) -> list[NormalizedMessage]:
        """Parse a single webhook *entry* into normalized messages."""
        out: list[NormalizedMessage] = []
        for event in payload.get("messaging", []):
            message = event.get("message")
            if not message or message.get("is_echo"):
                continue  # delivery/read receipts and our own echoes are skipped
            sender_id = str(event.get("sender", {}).get("id"))
            media: list[NormalizedMedia] = []
            for att in message.get("attachments", []) or []:
                url = (att.get("payload") or {}).get("url")
                if url:
                    media.append(NormalizedMedia(_attachment_type(att.get("type", "")), url))
            out.append(NormalizedMessage(
                external_user_id=sender_id,
                external_message_id=str(message.get("mid")),
                text=message.get("text"),
                media=media,
            ))
        return out

    def download_media(self, external_file_id: str) -> DownloadedMedia:
        # For Meta, the "file id" is a CDN URL on the attachment payload.
        resp = requests.get(external_file_id, timeout=self._timeout())
        resp.raise_for_status()
        media_root = current_app.config["MEDIA_ROOT"]
        sub = os.path.join(media_root, "meta", str(self.channel.id))
        os.makedirs(sub, exist_ok=True)
        mime = resp.headers.get("Content-Type") or mimetypes.guess_type(external_file_id)[0]
        ext = mimetypes.guess_extension(mime or "") or ""
        dest = os.path.join(sub, f"{uuid.uuid4().hex}{ext}")
        with open(dest, "wb") as fh:
            fh.write(resp.content)
        return DownloadedMedia(storage_path=dest, mime_type=mime, size_bytes=len(resp.content))

    # ---------------- outbound ----------------
    def send_text(self, external_user_id: str, text: str) -> SendResult:
        try:
            resp = requests.post(
                self._graph("me/messages"),
                params={"access_token": self._token},
                json={
                    "recipient": {"id": external_user_id},
                    "messaging_type": "RESPONSE",
                    "message": {"text": text},
                },
                timeout=self._timeout(),
            )
            data = resp.json()
            if resp.status_code >= 400 or "error" in data:
                err = (data.get("error") or {}).get("message", f"HTTP {resp.status_code}")
                return SendResult(ok=False, error=err)
            return SendResult(ok=True, external_message_id=data.get("message_id"))
        except Exception as exc:  # noqa: BLE001 — surfaced as a send failure
            log.warning("Meta send failed: %s", exc)
            return SendResult(ok=False, error=str(exc))

    # ---------------- lifecycle / admin ----------------
    def _account_id(self) -> str:
        creds = self.channel.get_credentials()
        return str(creds.get(self.id_field) or creds.get("page_id") or "")

    def _subscribe_node(self) -> str:
        # Subscriptions always target the Facebook Page, even for Instagram.
        creds = self.channel.get_credentials()
        return str(creds.get("page_id") or self._account_id())

    def test_connection(self) -> dict:
        node = self._account_id() or "me"
        resp = requests.get(
            self._graph(node),
            params={"access_token": self._token, "fields": "id,name,username"},
            timeout=self._timeout(),
        )
        data = resp.json()
        if "error" in data:
            raise RuntimeError(data["error"].get("message", "Meta error"))
        return {
            "id": data.get("id"),
            "name": data.get("name") or data.get("username"),
        }

    def set_webhook(self, url: str, secret: str) -> None:
        # Meta's callback URL is set once in the app dashboard; here we subscribe
        # the Page to the app so its message events start flowing.
        page_id = self._subscribe_node()
        if not page_id:
            raise RuntimeError("Meta channel has no page_id to subscribe")
        resp = requests.post(
            self._graph(f"{page_id}/subscribed_apps"),
            params={"access_token": self._token,
                    "subscribed_fields": "messages,messaging_postbacks"},
            timeout=self._timeout(),
        )
        data = resp.json()
        if "error" in data:
            raise RuntimeError(data["error"].get("message", "subscribe failed"))

    def delete_webhook(self) -> None:
        page_id = self._subscribe_node()
        if not page_id:
            return
        try:
            requests.delete(
                self._graph(f"{page_id}/subscribed_apps"),
                params={"access_token": self._token},
                timeout=self._timeout(),
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("Meta unsubscribe failed: %s", exc)


class MessengerAdapter(MetaAdapter):
    webhook_object = "page"
    id_field = "page_id"


class InstagramAdapter(MetaAdapter):
    webhook_object = "instagram"
    id_field = "ig_id"

"""Telegram Bot API adapter (spec §5.1, Phase 1).

Credentials (in channel.get_credentials()):
    bot_token       : the token from @BotFather
    webhook_secret  : random secret echoed back in X-Telegram-Bot-Api-Secret-Token
"""
from __future__ import annotations

import logging
import mimetypes
import os
import uuid

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


class TelegramAdapter(ChannelAdapter):
    @property
    def _token(self) -> str:
        token = self.channel.get_credentials().get("bot_token")
        if not token:
            raise RuntimeError("Telegram channel has no bot_token configured")
        return token

    def _api(self, method: str) -> str:
        return f"https://api.telegram.org/bot{self._token}/{method}"

    def _call(self, method: str, **params) -> dict:
        timeout = current_app.config.get("HTTP_TIMEOUT", 30)
        resp = requests.post(self._api(method), json=params, timeout=timeout)
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram {method} failed: {data.get('description')}")
        return data["result"]

    # ---------------- inbound ----------------
    def parse_webhook(self, payload: dict) -> list[NormalizedMessage]:
        msg = payload.get("message") or payload.get("edited_message")
        if not msg:
            return []
        chat = msg.get("chat", {})
        sender = msg.get("from", {})
        external_user_id = str(chat.get("id"))
        name = (sender.get("first_name", "") + " " + sender.get("last_name", "")).strip()

        media: list[NormalizedMedia] = []
        text = msg.get("text") or msg.get("caption")

        if "photo" in msg and msg["photo"]:
            largest = msg["photo"][-1]  # highest resolution
            media.append(NormalizedMedia(AttachmentType.IMAGE, largest["file_id"], "image/jpeg"))
        if "voice" in msg:
            media.append(NormalizedMedia(AttachmentType.AUDIO, msg["voice"]["file_id"], "audio/ogg"))
        if "audio" in msg:
            media.append(NormalizedMedia(AttachmentType.AUDIO, msg["audio"]["file_id"]))
        if "document" in msg:
            doc = msg["document"]
            media.append(NormalizedMedia(
                AttachmentType.FILE, doc["file_id"], doc.get("mime_type"), doc.get("file_name")
            ))

        return [NormalizedMessage(
            external_user_id=external_user_id,
            external_message_id=str(msg.get("message_id")),
            text=text,
            display_name=name or sender.get("username"),
            media=media,
        )]

    def download_media(self, external_file_id: str) -> DownloadedMedia:
        info = self._call("getFile", file_id=external_file_id)
        file_path = info["file_path"]
        url = f"https://api.telegram.org/file/bot{self._token}/{file_path}"
        timeout = current_app.config.get("HTTP_TIMEOUT", 30)
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()

        media_root = current_app.config["MEDIA_ROOT"]
        sub = os.path.join(media_root, "telegram", str(self.channel.id))
        os.makedirs(sub, exist_ok=True)
        ext = os.path.splitext(file_path)[1] or ""
        name = f"{uuid.uuid4().hex}{ext}"
        dest = os.path.join(sub, name)
        with open(dest, "wb") as fh:
            fh.write(resp.content)

        mime = mimetypes.guess_type(dest)[0]
        return DownloadedMedia(storage_path=dest, mime_type=mime, size_bytes=len(resp.content))

    # ---------------- outbound ----------------
    def send_text(self, external_user_id: str, text: str) -> SendResult:
        try:
            result = self._call("sendMessage", chat_id=external_user_id, text=text)
            return SendResult(ok=True, external_message_id=str(result.get("message_id")))
        except Exception as exc:  # noqa: BLE001 — surfaced to the agent as send failure
            log.warning("Telegram sendMessage failed: %s", exc)
            return SendResult(ok=False, error=str(exc))

    # ---------------- lifecycle / admin ----------------
    def test_connection(self) -> dict:
        me = self._call("getMe")
        return {
            "id": me.get("id"),
            "username": me.get("username"),
            "name": me.get("first_name"),
            "link": f"https://t.me/{me.get('username')}" if me.get("username") else None,
        }

    def set_webhook(self, url: str, secret: str) -> None:
        self._call(
            "setWebhook",
            url=url,
            secret_token=secret,
            allowed_updates=["message", "edited_message"],
            drop_pending_updates=False,
        )

    def delete_webhook(self) -> None:
        self._call("deleteWebhook", drop_pending_updates=False)

    def set_commands(self, commands: list[dict]) -> None:
        # commands: [{"command": "start", "description": "ابدأ"}, ...]
        cleaned = [
            {"command": c["command"].lstrip("/").strip(), "description": c.get("description", "")}
            for c in commands if c.get("command")
        ]
        self._call("setMyCommands", commands=cleaned)

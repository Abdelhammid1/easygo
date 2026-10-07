"""Unified channel adapter interface (spec §4.1).

Every channel (Telegram now; Messenger/Instagram later) implements the same
contract so the inbox and AI layers never depend on a specific platform.
Adding Meta in Phase 2 is a new adapter, not a change to the core.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import timedelta
from typing import ClassVar

from app.models.enums import AttachmentType


@dataclass
class NormalizedMedia:
    type: AttachmentType
    external_file_id: str
    mime_type: str | None = None
    file_name: str | None = None


@dataclass
class NormalizedMessage:
    """A platform message mapped to our internal shape."""
    external_user_id: str           # identity key on the channel (== chat for DMs)
    external_message_id: str
    text: str | None = None
    display_name: str | None = None
    avatar_url: str | None = None
    media: list[NormalizedMedia] = field(default_factory=list)


@dataclass
class SendResult:
    ok: bool
    external_message_id: str | None = None
    error: str | None = None


@dataclass
class DownloadedMedia:
    storage_path: str
    mime_type: str | None = None
    size_bytes: int | None = None


class ChannelAdapter(ABC):
    """Contract shared by all channels."""

    # Platforms that restrict sending to a window after the customer's last
    # message set this (e.g. Meta = 24h). None means no window (e.g. Telegram).
    reply_window: ClassVar[timedelta | None] = None

    def __init__(self, channel):
        self.channel = channel

    # --- inbound ---
    @abstractmethod
    def parse_webhook(self, payload: dict) -> list[NormalizedMessage]:
        """Turn a raw webhook body into zero or more normalized messages."""

    @abstractmethod
    def download_media(self, external_file_id: str) -> DownloadedMedia:
        """Fetch a media file and store it locally; return its path."""

    # --- outbound ---
    @abstractmethod
    def send_text(self, external_user_id: str, text: str) -> SendResult:
        """Send a text reply to the customer on this channel."""

    # --- lifecycle / admin ---
    @abstractmethod
    def test_connection(self) -> dict:
        """Verify credentials; return a small info dict (raises on failure)."""

    @abstractmethod
    def set_webhook(self, url: str, secret: str) -> None:
        """Register the receiving webhook with the platform."""

    @abstractmethod
    def delete_webhook(self) -> None:
        """Remove the registered webhook."""

    def set_commands(self, commands: list[dict]) -> None:
        """Optional: push bot commands (command/description). No-op by default."""
        return None

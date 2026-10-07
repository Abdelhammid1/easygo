"""Resolve a Channel row to its adapter implementation."""
from __future__ import annotations

from app.channels.base import ChannelAdapter
from app.channels.meta import InstagramAdapter, MessengerAdapter
from app.channels.telegram import TelegramAdapter
from app.models.enums import ChannelType

_ADAPTERS = {
    ChannelType.TELEGRAM: TelegramAdapter,
    ChannelType.MESSENGER: MessengerAdapter,
    ChannelType.INSTAGRAM: InstagramAdapter,
}


def get_adapter(channel) -> ChannelAdapter:
    ctype = channel.type
    adapter_cls = _ADAPTERS.get(ctype)
    if adapter_cls is None:
        raise NotImplementedError(f"No adapter for channel type {ctype}")
    return adapter_cls(channel)

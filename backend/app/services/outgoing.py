"""Outbound sending: deliver a reply, track send status, retry on failure (§4.1)."""
from __future__ import annotations

import logging

from app.channels.registry import get_adapter
from app.extensions import db
from app.models.base import utcnow
from app.models.core import Conversation, Message
from app.models.enums import (
    MessageDirection,
    MessageType,
    SendStatus,
    SenderType,
)
from app.services import realtime

log = logging.getLogger(__name__)

MAX_SEND_ATTEMPTS = 2


def reply_window_open(conversation: Conversation) -> bool:
    """False only when a platform window exists and has expired (spec §5.1)."""
    expires = conversation.reply_window_expires_at
    return expires is None or utcnow() <= expires


def send_reply(
    conversation: Conversation,
    text: str,
    *,
    sender_type: SenderType,
    sender_user_id: int | None = None,
    ai_confidence: float | None = None,
    ai_sources: list | None = None,
) -> Message:
    """Create an outbound message, send it via the channel adapter, track status."""
    channel = conversation.channel
    identity = next(
        (i for i in conversation.contact.identities if i.channel_id == channel.id),
        None,
    )

    message = Message(
        conversation_id=conversation.id,
        channel_id=channel.id,
        direction=MessageDirection.OUTBOUND,
        sender_type=sender_type,
        sender_user_id=sender_user_id,
        type=MessageType.TEXT,
        body=text,
        send_status=SendStatus.PENDING,
        ai_confidence=ai_confidence,
        ai_sources=ai_sources,
    )
    db.session.add(message)
    db.session.flush()

    if identity is None:
        message.send_status = SendStatus.FAILED
        message.error_reason = "no channel identity for contact"
        db.session.commit()
        return message

    # Platform reply window (Meta 24h): refuse to send outside it (spec §5.1).
    if not reply_window_open(conversation):
        message.send_status = SendStatus.FAILED
        message.error_reason = "reply_window_expired"
        db.session.commit()
        realtime.message_created(message)
        return message

    adapter = get_adapter(channel)
    last_error = None
    for attempt in range(1, MAX_SEND_ATTEMPTS + 1):
        result = adapter.send_text(identity.external_id, text)
        if result.ok:
            message.send_status = SendStatus.SENT
            message.external_id = result.external_message_id
            break
        last_error = result.error
        log.warning("send attempt %s/%s failed: %s", attempt, MAX_SEND_ATTEMPTS, last_error)
    else:
        message.send_status = SendStatus.FAILED
        message.error_reason = last_error

    conversation.last_message_at = utcnow()
    conversation.last_message_preview = text[:280]
    db.session.commit()

    realtime.message_created(message)
    realtime.conversation_updated(conversation)
    return message

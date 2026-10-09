"""Inbound pipeline: store incoming messages before any processing (spec §8).

Guarantees:
- every message is persisted first (no loss even if AI fails),
- idempotency via UNIQUE(channel_id, external_id): the same webhook delivered
  twice never creates two messages (spec §4.1),
- a resolved conversation reopens on a new customer message (IN-13).
"""
from __future__ import annotations

import logging

from sqlalchemy.exc import IntegrityError

from app.channels.base import NormalizedMessage
from app.channels.registry import get_adapter
from app.extensions import db
from app.models.base import utcnow
from app.models.core import (
    Attachment,
    Channel,
    Contact,
    ContactIdentity,
    Conversation,
    Message,
)
from app.models.enums import (
    ConversationState,
    MessageDirection,
    MessageType,
    SenderType,
)

log = logging.getLogger(__name__)


def _get_or_create_contact(channel: Channel, nm: NormalizedMessage):
    identity = db.session.scalar(
        db.select(ContactIdentity).filter_by(
            channel_id=channel.id, external_id=nm.external_user_id
        )
    )
    if identity:
        if nm.display_name and not identity.display_name:
            identity.display_name = nm.display_name
        return identity.contact, identity

    contact = Contact(name=nm.display_name)
    db.session.add(contact)
    db.session.flush()
    identity = ContactIdentity(
        contact_id=contact.id,
        channel_id=channel.id,
        external_id=nm.external_user_id,
        display_name=nm.display_name,
        avatar_url=nm.avatar_url,
    )
    db.session.add(identity)
    try:
        db.session.flush()
    except IntegrityError:
        # Concurrent first message from the same customer created the identity
        # first. Postgres blocked our insert until that commit, so it now exists.
        db.session.rollback()
        identity = db.session.scalar(
            db.select(ContactIdentity).filter_by(
                channel_id=channel.id, external_id=nm.external_user_id
            )
        )
        if identity is None:
            raise
        return identity.contact, identity
    return contact, identity


def _get_or_create_conversation(channel: Channel, contact: Contact) -> Conversation:
    conv = db.session.scalar(
        db.select(Conversation)
        .filter_by(channel_id=channel.id, contact_id=contact.id)
        .order_by(Conversation.created_at.desc())
    )
    if conv is None or conv.state == ConversationState.RESOLVED:
        # Start a fresh conversation for a brand-new contact, and also when the
        # last one was resolved — a new message is a new order/topic, so context
        # and the escalation counter start clean (ticket). The old resolved
        # conversation stays in history; the contact ties them together.
        conv = Conversation(channel_id=channel.id, contact_id=contact.id)
        db.session.add(conv)
        db.session.flush()
    return conv


def _message_type(nm: NormalizedMessage) -> MessageType:
    if nm.media:
        return {
            "image": MessageType.IMAGE,
            "audio": MessageType.AUDIO,
            "file": MessageType.FILE,
        }.get(getattr(nm.media[0].type, "value", ""), MessageType.FILE)
    return MessageType.TEXT


def store_incoming(channel: Channel, nm: NormalizedMessage) -> Message | None:
    """Persist one normalized inbound message. Returns None if it was a duplicate."""
    contact, _identity = _get_or_create_contact(channel, nm)
    conv = _get_or_create_conversation(channel, contact)

    message = Message(
        conversation_id=conv.id,
        channel_id=channel.id,
        direction=MessageDirection.INBOUND,
        sender_type=SenderType.CUSTOMER,
        type=_message_type(nm),
        body=nm.text,
        external_id=nm.external_message_id,
    )
    db.session.add(message)
    try:
        db.session.flush()
    except IntegrityError:
        # Duplicate (channel_id, external_id) — idempotent no-op.
        db.session.rollback()
        log.info("Duplicate inbound message ignored: ext=%s", nm.external_message_id)
        return None

    # Download and attach media.
    if nm.media:
        adapter = get_adapter(channel)
        for media in nm.media:
            try:
                dl = adapter.download_media(media.external_file_id)
                db.session.add(Attachment(
                    message_id=message.id,
                    type=media.type,
                    storage_path=dl.storage_path,
                    mime_type=dl.mime_type or media.mime_type,
                    size_bytes=dl.size_bytes,
                ))
            except Exception as exc:  # noqa: BLE001 — keep the message even if media fails
                log.warning("media download failed (%s): %s", media.external_file_id, exc)

    # Update conversation rollup + unread.
    now = utcnow()
    conv.last_message_at = now
    conv.last_message_preview = (nm.text or _media_preview(message))[:280]
    conv.unread_count = (conv.unread_count or 0) + 1

    # Reset the platform reply window (e.g. Meta's 24h) from the customer's
    # latest message. Channels without a window leave this untouched (spec §5.1).
    window = get_adapter(channel).reply_window
    if window is not None:
        conv.reply_window_expires_at = now + window

    db.session.commit()
    return message


def _media_preview(message: Message) -> str:
    kind = getattr(message.type, "value", "")
    return {"image": "📷 صورة", "audio": "🎙 رسالة صوتية", "file": "📎 ملف"}.get(kind, "رسالة")

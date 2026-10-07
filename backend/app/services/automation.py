"""Automation rules (spec §5.4): welcome, business hours, auto-assign, SLA, auto-close."""
from __future__ import annotations

import logging
import os
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.extensions import db
from app.models.base import utcnow
from app.models.core import Attachment, Conversation, Message, User
from app.models.enums import (
    ConversationState,
    MessageDirection,
    NotificationType,
    SenderType,
    UserRole,
    UserStatus,
)
from app.models.org import OrgSettings
from app.models.support import Notification

log = logging.getLogger(__name__)

_WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def get_settings() -> OrgSettings | None:
    return db.session.get(OrgSettings, 1)


def _parse_hhmm(value: str) -> time | None:
    try:
        hh, mm = value.split(":")
        return time(int(hh), int(mm))
    except (ValueError, AttributeError):
        return None


def within_business_hours(settings: OrgSettings, now: datetime | None = None) -> bool:
    """True if `now` falls in the configured weekly schedule (open if none set)."""
    schedule = settings.business_hours or {}
    if not schedule:
        return True  # no schedule configured -> always open
    try:
        tz = ZoneInfo(settings.timezone or "UTC")
    except Exception:  # noqa: BLE001
        tz = ZoneInfo("UTC")
    local = (now or utcnow()).astimezone(tz)
    window = schedule.get(_WEEKDAYS[local.weekday()])
    if not window or len(window) != 2:
        return False
    start, end = _parse_hhmm(window[0]), _parse_hhmm(window[1])
    if start is None or end is None:
        return True
    return start <= local.time() <= end


def is_first_inbound(conversation: Conversation) -> bool:
    count = db.session.scalar(
        db.select(db.func.count(Message.id)).where(
            Message.conversation_id == conversation.id,
            Message.direction == MessageDirection.INBOUND,
        )
    )
    return (count or 0) <= 1


def handle_first_contact(conversation: Conversation) -> bool:
    """Send welcome / out-of-hours notice on the first message.

    Returns False when out-of-hours handling means the AI should NOT run.
    """
    from app.services import outgoing

    settings = get_settings()
    if settings is None or not is_first_inbound(conversation):
        return True

    if settings.out_of_hours_enabled and not within_business_hours(settings):
        outgoing.send_reply(conversation, settings.out_of_hours_text,
                            sender_type=SenderType.SYSTEM)
        return False

    if settings.welcome_enabled:
        outgoing.send_reply(conversation, settings.welcome_text,
                            sender_type=SenderType.SYSTEM)
    return True


def auto_assign(conversation: Conversation) -> None:
    """Assign to the least-busy active agent (AU-1). Caller commits."""
    settings = get_settings()
    if settings is None or not settings.auto_assign_enabled or conversation.assignee_id:
        return
    agents = db.session.scalars(
        db.select(User).where(User.role == UserRole.AGENT, User.status == UserStatus.ACTIVE)
    ).all()
    if not agents:
        return
    # Least-busy: fewest open/needs-human conversations currently assigned.
    def load(uid: int) -> int:
        return db.session.scalar(
            db.select(db.func.count(Conversation.id)).where(
                Conversation.assignee_id == uid,
                Conversation.state.in_([ConversationState.OPEN, ConversationState.NEEDS_HUMAN]),
            )
        ) or 0

    conversation.assignee_id = min(agents, key=lambda a: load(a.id)).id


# --------------------- scheduled maintenance ---------------------

def run_sla_check() -> int:
    """Notify supervisors of needs-human conversations idle past the SLA (AU-4)."""
    settings = get_settings()
    if settings is None or not settings.sla_minutes:
        return 0
    cutoff = utcnow() - timedelta(minutes=settings.sla_minutes)
    stale = db.session.scalars(
        db.select(Conversation).where(
            Conversation.state == ConversationState.NEEDS_HUMAN,
            Conversation.last_message_at < cutoff,
        )
    ).all()
    from app.services import notify

    recipients = db.session.scalars(
        db.select(User).where(
            User.status == UserStatus.ACTIVE,
            User.role.in_([UserRole.SUPERVISOR, UserRole.ADMIN]),
        )
    ).all()
    created = 0
    for conv in stale:
        # Dedupe: skip if an unread SLA alert already exists for this conversation.
        exists = db.session.scalar(
            db.select(Notification.id).where(
                Notification.conversation_id == conv.id,
                Notification.type == NotificationType.SLA_BREACH,
                Notification.is_read.is_(False),
            ).limit(1)
        )
        if exists:
            continue
        for user in recipients:
            notify.create(user.id, NotificationType.SLA_BREACH,
                          "محادثة تحتاج موظفًا تجاوزت زمن الاستجابة", conv.id)
            created += 1
    db.session.commit()
    return created


def run_auto_close() -> int:
    """Resolve idle open/pending conversations after the configured delay (AU-5)."""
    settings = get_settings()
    if settings is None or not settings.auto_close_minutes:
        return 0
    cutoff = utcnow() - timedelta(minutes=settings.auto_close_minutes)
    result = db.session.execute(
        db.update(Conversation)
        .where(
            Conversation.state.in_([ConversationState.OPEN, ConversationState.PENDING]),
            Conversation.last_message_at < cutoff,
        )
        .values(state=ConversationState.RESOLVED)
    )
    db.session.commit()
    return getattr(result, "rowcount", 0) or 0


def _safe_unlink(path: str | None) -> None:
    if not path:
        return
    try:
        if os.path.isfile(path):
            os.remove(path)
    except OSError as exc:
        log.warning("retention: could not delete media %s: %s", path, exc)


def run_retention() -> int:
    """Purge conversations + media older than retention_days (spec §5.7 AD-6).

    Contacts are kept; only their conversations, messages, and media are removed.
    """
    settings = get_settings()
    if settings is None or not settings.retention_days:
        return 0
    cutoff = utcnow() - timedelta(days=settings.retention_days)
    convs = db.session.scalars(
        db.select(Conversation.id).where(Conversation.last_message_at < cutoff)
    ).all()
    ids = list(convs)
    if not ids:
        return 0

    # Delete the media files on disk before removing the rows.
    paths = db.session.scalars(
        db.select(Attachment.storage_path)
        .join(Message, Attachment.message_id == Message.id)
        .where(Message.conversation_id.in_(ids))
    ).all()
    for path in paths:
        _safe_unlink(path)

    # Notifications reference conversations without an ON DELETE rule — null them
    # first so the conversation delete doesn't violate the FK. Messages, attachments,
    # AI runs, notes and tag links cascade at the DB level.
    db.session.execute(
        db.update(Notification).where(Notification.conversation_id.in_(ids))
        .values(conversation_id=None)
    )
    db.session.execute(db.delete(Conversation).where(Conversation.id.in_(ids)))
    db.session.commit()
    return len(ids)

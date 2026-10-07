"""Worker task: process one stored inbound message (spec §6.1 flow).

Enqueued by the webhook after the message is persisted. Runs in the worker
process; pushes its own app context so it works regardless of fork behaviour.
"""
from __future__ import annotations

import logging

from app.extensions import db
from app.models.ai import AISettings
from app.models.core import Conversation, Message
from app.models.enums import (
    ConversationState,
    EscalationReason,
    MessageType,
    NotificationType,
    SenderType,
)
from app.services import automation, escalation, notify, outgoing, realtime
from app.services.ai import service as ai_service

_AI_FAILURE_SUBJECT = "easyGo: فشل في خدمة الذكاء الاصطناعي"


def _alert_ai_failure(detail: str) -> None:
    notify.alert_admins(
        NotificationType.AI_FAILURE, _AI_FAILURE_SUBJECT,
        f"تعذّر على الذكاء الاصطناعي الرد: {detail}",
        throttle_minutes=30,
    )

log = logging.getLogger(__name__)

_app = None


def _get_app():
    global _app
    if _app is None:
        from app import create_app
        _app = create_app()
    return _app


def process_incoming_message(message_id: int) -> None:
    """Entrypoint executed by RQ."""
    app = _get_app()
    with app.app_context():
        try:
            _process(message_id)
        except Exception:  # noqa: BLE001 — never lose the job silently
            log.exception("process_incoming_message failed for id=%s", message_id)


def _ai_replies_since_human(conversation_id: int) -> int:
    """How many AI auto-replies have been sent since a human last stepped in.

    Counts AI messages back to the most recent agent message (customer messages
    do NOT reset the count), so a long AI-only back-and-forth eventually hands
    off to a person even though each turn is prompted by the customer (§6.3).
    """
    rows = db.session.scalars(
        db.select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(40)
    ).all()
    count = 0
    for m in rows:
        if m.sender_type == SenderType.AGENT:
            break
        if m.sender_type == SenderType.AI:
            count += 1
    return count


def _process(message_id: int) -> None:
    message = db.session.get(Message, message_id)
    if message is None:
        return
    conversation = db.session.get(Conversation, message.conversation_id)
    if conversation is None:
        return

    # Always surface the inbound message to connected agents.
    realtime.message_created(message)
    realtime.conversation_updated(conversation)

    # Blocked customers get nothing automatic (spec §5.3 CT-5).
    if conversation.contact and conversation.contact.is_blocked:
        return

    # First-contact automation: welcome / out-of-hours notice (spec §5.4).
    if not automation.handle_first_contact(conversation):
        return  # out-of-hours notice sent — don't run the AI now

    settings = db.session.get(AISettings, 1)

    # --- guards: when NOT to auto-reply ---
    if settings is None or not settings.ai_enabled:
        return  # global kill switch (spec §6.4)
    if conversation.state == ConversationState.NEEDS_HUMAN:
        return  # already with a human
    ai_mode = getattr(conversation.ai_mode, "value", conversation.ai_mode)
    if ai_mode != "active":
        return  # off / suggest: no automatic send in Phase 1
    if not settings.has_api_key:
        log.warning("AI enabled but no API key configured — escalating.")
        escalation.escalate(conversation, EscalationReason.AI_ERROR, notify_customer=False)
        _alert_ai_failure("لم يتم ضبط مفتاح مزوّد الذكاء الاصطناعي")
        return

    # Media without a vision/STT provider is escalated (spec §6.2 fallback).
    if message.type in (MessageType.IMAGE, MessageType.AUDIO, MessageType.FILE):
        escalation.escalate(conversation, EscalationReason.UNREADABLE_MEDIA)
        return

    # Too many AI replies without a human resolving it -> hand to a human.
    if _ai_replies_since_human(conversation.id) >= settings.max_consecutive_replies:
        escalation.escalate(conversation, EscalationReason.REPEATED_FAILURE)
        return

    # --- run the AI flow ---
    decision = ai_service.generate(conversation, trigger_message=message)

    if decision.escalate or not decision.reply_text:
        escalation.escalate(
            conversation, decision.reason or EscalationReason.LOW_CONFIDENCE
        )
        if decision.reason == EscalationReason.AI_ERROR:
            _alert_ai_failure("خطأ تقني في خدمة الذكاء الاصطناعي")
        return

    outgoing.send_reply(
        conversation, decision.reply_text, sender_type=SenderType.AI
    )

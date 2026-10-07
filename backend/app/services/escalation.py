"""Escalate a conversation to a human (spec §6.3).

On escalation: state -> needs_human, auto-reply stops, a system note is added,
agents are notified, and the customer is told a human will take over. The AI
does not reply again until a human re-enables it.
"""
from __future__ import annotations

import logging

from app.channels.registry import get_adapter
from app.extensions import db
from app.models.base import utcnow
from app.models.core import Conversation, Message, User
from app.models.enums import (
    AIMode,
    ConversationState,
    EscalationReason,
    MessageDirection,
    MessageType,
    NotificationType,
    SenderType,
    SendStatus,
    UserStatus,
    UserRole,
)
from app.services import notify, realtime
from app.services.outgoing import reply_window_open

log = logging.getLogger(__name__)

_REASON_AR = {
    EscalationReason.REQUESTED_HUMAN: "طلب العميل التحدث مع موظف",
    EscalationReason.NEGATIVE_SENTIMENT: "نبرة استياء أو شكوى",
    EscalationReason.LOW_CONFIDENCE: "ثقة منخفضة في الرد",
    EscalationReason.NO_KB_ANSWER: "لا توجد إجابة في قاعدة المعرفة",
    EscalationReason.SENSITIVE_TOPIC: "موضوع حساس (دفع/استرجاع/شكوى)",
    EscalationReason.REPEATED_FAILURE: "تكرار دون حل",
    EscalationReason.UNREADABLE_MEDIA: "وسائط يصعب على الذكاء الاصطناعي التعامل معها",
    EscalationReason.AI_ERROR: "تعذّر الوصول لخدمة الذكاء الاصطناعي",
}

# Customer-facing handoff message (spec §6.3 — text is editable later via settings).
HANDOFF_TEXT = "تمام، هحوّلك لموظف من فريقنا هيساعدك حالًا 🙏"


def escalate(
    conversation: Conversation,
    reason: EscalationReason,
    *,
    notify_customer: bool = True,
) -> None:
    conversation.state = ConversationState.NEEDS_HUMAN
    conversation.escalation_reason = reason
    # Pause auto-reply; it resumes only when a human re-enables it (spec §6.3).
    conversation.ai_mode = AIMode.OFF

    # System message in the thread (visible to agents).
    db.session.add(Message(
        conversation_id=conversation.id,
        channel_id=conversation.channel_id,
        direction=MessageDirection.OUTBOUND,
        sender_type=SenderType.SYSTEM,
        type=MessageType.SYSTEM,
        body=f"⤴ تم التصعيد إلى موظف — السبب: {_REASON_AR.get(reason, reason.value)}",
    ))

    # Notify all active staff (in-app + realtime + web push).
    recipients = db.session.scalars(
        db.select(User).where(
            User.status == UserStatus.ACTIVE,
            User.role.in_([UserRole.AGENT, UserRole.SUPERVISOR, UserRole.ADMIN]),
        )
    ).all()
    body = f"محادثة تحتاج موظفًا: {_REASON_AR.get(reason, reason.value)}"
    for user in recipients:
        notify.create(user.id, NotificationType.ESCALATION, body, conversation.id)

    # Auto-assign to an agent if enabled (spec §5.4 AU-1).
    from app.services import automation
    automation.auto_assign(conversation)

    conversation.last_message_at = utcnow()
    db.session.commit()

    # Tell the customer a human is coming (best-effort; only if we still can).
    if notify_customer and reply_window_open(conversation):
        _notify_customer(conversation)

    realtime.conversation_updated(conversation)


def _notify_customer(conversation: Conversation) -> None:
    identity = next(
        (i for i in conversation.contact.identities
         if i.channel_id == conversation.channel_id),
        None,
    )
    if identity is None:
        return
    from app.models.org import OrgSettings
    org = db.session.get(OrgSettings, 1)
    text = org.handoff_text if org and org.handoff_text else HANDOFF_TEXT
    try:
        adapter = get_adapter(conversation.channel)
        result = adapter.send_text(identity.external_id, text)
        db.session.add(Message(
            conversation_id=conversation.id,
            channel_id=conversation.channel_id,
            direction=MessageDirection.OUTBOUND,
            sender_type=SenderType.SYSTEM,
            type=MessageType.TEXT,
            body=text,
            external_id=result.external_message_id,
            send_status=SendStatus.SENT if result.ok else SendStatus.FAILED,
            error_reason=None if result.ok else result.error,
        ))
        db.session.commit()
    except Exception as exc:  # noqa: BLE001 — handoff notice is best-effort
        log.warning("handoff notice failed: %s", exc)
        db.session.rollback()

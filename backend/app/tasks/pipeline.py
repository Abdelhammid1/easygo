"""Worker task: process one stored inbound message (spec §6.1 flow).

Enqueued by the webhook after the message is persisted. Runs in the worker
process; pushes its own app context so it works regardless of fork behaviour.
"""
from __future__ import annotations

import logging
import re

from app.extensions import db
from app.models.ai import AISettings, KBChunk, KBItem, Order
from app.models.base import utcnow
from app.models.core import Conversation, Message
from app.models.enums import (
    ConversationState,
    EscalationReason,
    MessageType,
    NotificationType,
    SenderType,
)
from app.models.org import DEFAULT_ATTENTION_KEYWORDS, OrgSettings
from app.services import automation, escalation, notify, outgoing, realtime
from app.services.ai import service as ai_service
from app.utils.arabic import contains_any


def _source_titles(chunk_ids: list[int] | None) -> list[str]:
    if not chunk_ids:
        return []
    rows = db.session.execute(
        db.select(KBItem.title).join(KBChunk, KBChunk.item_id == KBItem.id)
        .where(KBChunk.id.in_(chunk_ids))
    ).all()
    return sorted({t for (t,) in rows})


def _save_new_address(conversation: Conversation, new_address: str | None) -> None:
    if new_address and conversation.contact:
        conversation.contact.address = new_address


def _save_customer_phone(conversation: Conversation, message: Message) -> None:
    """If the customer typed a phone number and we have none saved, keep it so a
    later "نفس الرقم" can reuse it (ticket §6)."""
    contact = conversation.contact
    if contact is None or contact.phone or not message.body:
        return
    m = re.search(r"(01[0125]\d{8})", message.body.replace(" ", "").replace("-", ""))
    if m:
        contact.phone = m.group(1)


def _flag_attention(conversation: Conversation, message: Message) -> None:
    """Flag + notify on a risk keyword (complaint/cancel/late/refund...).

    The bot still replies normally — this only surfaces the conversation to staff
    (bell + "تحتاج انتباه" filter). No-op if already flagged (ticket §2).
    """
    if conversation.needs_attention or not message.body:
        return
    org = db.session.get(OrgSettings, 1)
    keywords = (org.attention_keywords if org and org.attention_keywords
                else DEFAULT_ATTENTION_KEYWORDS)
    hits = contains_any(message.body, keywords)
    if not hits:
        return
    conversation.needs_attention = True
    db.session.commit()
    name = conversation.contact.name if conversation.contact else "عميل"
    notify.notify_staff(
        NotificationType.NEEDS_ATTENTION,
        f"محادثة تحتاج انتباه ({'، '.join(hits)}) — {name}",
        conversation_id=conversation.id,
    )
    realtime.conversation_updated(conversation)


def _order_summary(conversation: Conversation, order: dict) -> str:
    name = conversation.contact.name if conversation.contact else "عميل"
    lines = [f"🧾 أوردر مؤكد — {name}"]
    for stop in (order.get("stops") or []):
        items = "، ".join(stop.get("items") or [])
        lines.append(f"• {stop.get('shop', '')}: {items}".strip())
    if order.get("delivery_landmark"):
        lines.append(f"التسليم: {order['delivery_landmark']}")
    if order.get("phones"):
        lines.append("هواتف: " + "، ".join(str(p) for p in order["phones"]))
    if order.get("payment_method"):
        lines.append(f"الدفع: {order['payment_method']}")
    if order.get("invoice_required"):
        lines.append("مطلوب فاتورة")
    return "\n".join(lines)


def _notify_order_confirmed(conversation: Conversation, order: dict) -> None:
    name = conversation.contact.name if conversation.contact else "عميل"
    notify.notify_staff(
        NotificationType.ORDER_CONFIRMED, f"أوردر مؤكد جديد من {name}",
        conversation_id=conversation.id,
    )
    # Optional: post a summary to a staff Telegram group if configured.
    from app.channels.registry import get_adapter
    from app.models.core import Channel
    from app.models.enums import ChannelStatus, ChannelType
    from app.models.org import OrgSettings

    org = db.session.get(OrgSettings, 1)
    chat_id = org.order_notify_telegram_chat_id if org else None
    if not chat_id:
        return
    channel = db.session.scalar(
        db.select(Channel).where(
            Channel.type == ChannelType.TELEGRAM,
            Channel.status == ChannelStatus.CONNECTED,
        )
    )
    if channel is None:
        return
    try:
        get_adapter(channel).send_text(chat_id, _order_summary(conversation, order))
    except Exception as exc:  # noqa: BLE001 — best-effort
        log.warning("order group notify failed: %s", exc)

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

    # Surface risky conversations to staff + remember a typed phone (bot still replies).
    _flag_attention(conversation, message)
    _save_customer_phone(conversation, message)

    # --- run the AI flow ---
    decision = ai_service.generate(conversation, trigger_message=message)

    # Provider outage (blank/error after retries): send the customer NOTHING
    # misleading; record ai_error (already logged) + alert staff (ticket §1).
    if decision.ai_error:
        _alert_ai_failure("ردّ فارغ من مزوّد الذكاء الاصطناعي بعد عدة محاولات")
        return

    sources = _source_titles(decision.used_chunk_ids)

    # Order confirmed -> send the model's reply, record the order, stay AI-active,
    # reset the counter, and alert staff. NOT an escalation (ticket).
    if decision.order_confirmed and decision.reply_text:
        outgoing.send_reply(
            conversation, decision.reply_text, sender_type=SenderType.AI,
            ai_confidence=decision.confidence, ai_sources=sources,
        )
        order = decision.order or {}
        db.session.add(Order(
            conversation_id=conversation.id,
            contact_id=conversation.contact_id,
            stops=order.get("stops"),
            delivery_landmark=order.get("delivery_landmark"),
            phones=order.get("phones"),
            payment_method=order.get("payment_method"),
            invoice_required=bool(order.get("invoice_required")),
            raw=order,
        ))
        conversation.order_confirmed = True
        conversation.ai_turn_reset_at = utcnow()  # marker: last AI state change
        _save_new_address(conversation, decision.new_address)
        db.session.commit()
        realtime.conversation_updated(conversation)
        _notify_order_confirmed(conversation, order)
        return

    # Escalate ONLY when the customer asked for a human (ticket §2).
    if decision.escalate:
        escalation.escalate(
            conversation, decision.reason or EscalationReason.REQUESTED_HUMAN
        )
        return

    if not decision.reply_text:
        return  # nothing to send (generate() normally supplies a clarify fallback)

    _save_new_address(conversation, decision.new_address)  # committed by send_reply
    outgoing.send_reply(
        conversation, decision.reply_text, sender_type=SenderType.AI,
        ai_confidence=decision.confidence, ai_sources=sources,
    )

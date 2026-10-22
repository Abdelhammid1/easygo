"""Worker task: process one stored inbound message (spec §6.1 flow).

Enqueued by the webhook after the message is persisted. Runs in the worker
process; pushes its own app context so it works regardless of fork behaviour.
"""
from __future__ import annotations

import logging
import re
import time
from datetime import timedelta
from typing import cast

from app.extensions import db
from app.models.ai import AISettings, KBChunk, KBItem, Order
from app.models.base import utcnow
from app.models.core import Conversation, Message
from app.models.enums import (
    ConversationState,
    EscalationReason,
    MessageDirection,
    MessageType,
    NotificationType,
    SenderType,
)
from app.models.org import DEFAULT_ATTENTION_KEYWORDS, OrgSettings
from app.services import automation, escalation, notify, outgoing, realtime
from app.services.ai import service as ai_service
from app.tasks.queue import AI_QUEUE, get_connection, get_queue
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


def _save_customer_phone(conversation: Conversation, text: str) -> None:
    """If the customer typed a phone number and we have none saved, keep it so a
    later "نفس الرقم" can reuse it (ticket §6)."""
    contact = conversation.contact
    if contact is None or contact.phone or not text:
        return
    m = re.search(r"(01[0125]\d{8})", text.replace(" ", "").replace("-", ""))
    if m:
        contact.phone = m.group(1)


def _flag_attention(conversation: Conversation, text: str) -> None:
    """Flag + notify on a risk keyword (complaint/cancel/late/refund...).

    The bot still replies normally — this only surfaces the conversation to staff
    (bell + "تحتاج انتباه" filter). No-op if already flagged (ticket §2).
    """
    if conversation.needs_attention or not text:
        return
    org = db.session.get(OrgSettings, 1)
    keywords = (org.attention_keywords if org and org.attention_keywords
                else DEFAULT_ATTENTION_KEYWORDS)
    hits = contains_any(text, keywords)
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


def _places_count(order: dict) -> int | None:
    """How many shops to visit — display only (derived, not price-authoritative)."""
    pc = order.get("places_count")
    if isinstance(pc, bool):
        pc = None
    return (int(pc) if isinstance(pc, (int, float))
            else (len(order.get("stops") or []) or None))


def _active_order(conversation_id: int) -> Order | None:
    """Latest not-yet-delivered order on the conversation (editable in place)."""
    return db.session.scalar(
        db.select(Order).where(
            Order.conversation_id == conversation_id,
            Order.status.notin_(("delivered", "cancelled")),
        ).order_by(Order.id.desc())
    )


def _order_snapshot(order: Order) -> dict:
    fee = order.delivery_fee
    return {
        "revision": order.revision,
        "stops": order.stops,
        "delivery_landmark": order.delivery_landmark,
        "phones": order.phones,
        "payment_method": order.payment_method,
        "invoice_required": order.invoice_required,
        "delivery_fee": float(fee) if fee is not None else None,
        "price_pending": order.price_pending,
        "places_count": order.places_count,
        "at": order.updated_at.isoformat() if order.updated_at else None,
    }


def _order_summary(conversation: Conversation, order: Order, *, updated: bool) -> str:
    name = conversation.contact.name if conversation.contact else "عميل"
    head = f"✏️ تعديل الأوردر #{order.id}" if updated else f"🧾 أوردر مؤكد #{order.id}"
    lines = [f"{head} — {name}"]
    for stop in (order.stops or []):
        if not isinstance(stop, dict):
            continue
        items = "، ".join(str(i) for i in (stop.get("items") or []))
        label = stop.get("shop", "")
        if stop.get("category"):
            label = f"{label} ({stop['category']})"
        lines.append(f"• {label}: {items}".strip())
    if order.places_count:
        lines.append(f"عدد الأماكن: {order.places_count}")
    if order.delivery_landmark:
        lines.append(f"التسليم: {order.delivery_landmark}")
    if order.phones:
        lines.append("هواتف: " + "، ".join(str(p) for p in order.phones))
    if order.payment_method:
        lines.append(f"الدفع: {order.payment_method}")
    if order.price_pending:
        lines.append("التوصيل: بانتظار التسعير")
    elif order.delivery_fee is not None:
        lines.append(f"التوصيل: {order.delivery_fee} ج")
    if order.invoice_required:
        lines.append("مطلوب فاتورة")
    return "\n".join(lines)


def _notify_order(conversation: Conversation, order: Order, *, updated: bool) -> None:
    name = conversation.contact.name if conversation.contact else "عميل"
    if updated:
        extra = " (محتاج إعادة تسعير)" if order.price_pending else ""
        notify.notify_staff(
            NotificationType.ORDER_UPDATED, f"تم تعديل الأوردر #{order.id} — {name}{extra}",
            conversation_id=conversation.id,
        )
    else:
        notify.notify_staff(
            NotificationType.ORDER_CONFIRMED, f"أوردر مؤكد جديد #{order.id} — {name}",
            conversation_id=conversation.id,
        )
    # Optional: post a summary to a staff Telegram group if configured.
    from app.channels.registry import get_adapter
    from app.models.core import Channel
    from app.models.enums import ChannelStatus, ChannelType

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
        get_adapter(channel).send_text(
            chat_id, _order_summary(conversation, order, updated=updated))
    except Exception as exc:  # noqa: BLE001 — best-effort
        log.warning("order group notify failed: %s", exc)


def _handle_order(conversation: Conversation, decision, sources: list[str]) -> None:
    """Send the AI confirmation, then create OR update-in-place the order (§3)."""
    outgoing.send_reply(
        conversation, decision.reply_text, sender_type=SenderType.AI,
        ai_confidence=decision.confidence, ai_sources=sources,
    )
    order_dict = decision.order or {}
    places = _places_count(order_dict)
    existing = _active_order(conversation.id)
    if existing is not None:
        # Edit an existing confirmed order: snapshot the old state, bump revision.
        history = list(existing.revisions or [])
        history.append(_order_snapshot(existing))
        existing.revisions = history
        existing.revision = (existing.revision or 0) + 1
        existing.stops = order_dict.get("stops")
        existing.delivery_landmark = order_dict.get("delivery_landmark")
        existing.phones = order_dict.get("phones")
        existing.payment_method = order_dict.get("payment_method")
        existing.invoice_required = bool(order_dict.get("invoice_required"))
        existing.places_count = places
        # Delivery pricing is REP-authoritative, never model-set (anti-injection).
        # Any edit can change the fee (stops/items changed), so force a re-price:
        # keep the prior fee as a hint but flag it pending until a rep re-confirms.
        existing.price_pending = True
        existing.raw = order_dict  # model's suggested fee (if any) lives here only
        order_row = existing
        updated = True
    else:
        order_row = Order(
            conversation_id=conversation.id,
            contact_id=conversation.contact_id,
            stops=order_dict.get("stops"),
            delivery_landmark=order_dict.get("delivery_landmark"),
            phones=order_dict.get("phones"),
            payment_method=order_dict.get("payment_method"),
            invoice_required=bool(order_dict.get("invoice_required")),
            places_count=places,
            delivery_fee=None,      # rep prices delivery, not the AI/customer
            price_pending=True,
            raw=order_dict,
        )
        db.session.add(order_row)
        updated = False

    conversation.order_confirmed = True
    conversation.ai_turn_reset_at = utcnow()  # marker: last AI state change
    _save_new_address(conversation, decision.new_address)
    db.session.commit()
    realtime.conversation_updated(conversation)
    _notify_order(conversation, order_row, updated=updated)

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


_DEBOUNCE_KEY = "easygo:debounce:%s"


def process_incoming_message(message_id: int) -> None:
    """RQ entrypoint: surface the message, then debounce or run the AI."""
    app = _get_app()
    with app.app_context():
        try:
            _receive(message_id)
        except Exception:  # noqa: BLE001 — never lose the job silently
            log.exception("process_incoming_message failed for id=%s", message_id)


def run_conversation_ai(conversation_id: int) -> None:
    """RQ entrypoint for the debounced AI run (fired after the quiet window)."""
    app = _get_app()
    with app.app_context():
        try:
            get_connection().delete(_DEBOUNCE_KEY % conversation_id)
        except Exception as exc:  # noqa: BLE001 — Redis cleanup is best-effort
            log.warning("debounce key cleanup failed for cid=%s: %s", conversation_id, exc)
        try:
            _run_ai(conversation_id)
        except Exception:  # noqa: BLE001 — never lose the job silently
            log.exception("run_conversation_ai failed for cid=%s", conversation_id)


def _receive(message_id: int) -> None:
    """Surface the inbound message to agents, then schedule/run the AI (§4)."""
    message = db.session.get(Message, message_id)
    if message is None:
        return
    conversation = db.session.get(Conversation, message.conversation_id)
    if conversation is None:
        return

    # Always surface every inbound message to connected agents immediately.
    realtime.message_created(message)
    realtime.conversation_updated(conversation)

    settings = db.session.get(AISettings, 1)
    if settings is None or (settings.debounce_seconds or 0) <= 0:
        _run_ai(conversation.id)  # debounce disabled: behave exactly as before
    else:
        _schedule_debounced_ai(conversation.id, settings)


def _schedule_debounced_ai(conversation_id: int, settings: AISettings) -> None:
    """Debounce: (re)schedule one AI run per burst, renewing up to the max window."""
    from rq.job import Job  # type: ignore[import]  # lazy; keep module import light

    conn = get_connection()
    base = max(1, int(settings.debounce_seconds or 5))
    max_window = max(base, int(settings.debounce_max_seconds or 15))
    key = _DEBOUNCE_KEY % conversation_id
    now = time.time()
    data: dict = cast(dict, conn.hgetall(key)) or {}
    first_ts = float(data[b"first_ts"]) if data.get(b"first_ts") else now
    prev_job = data.get(b"job_id")
    if prev_job:
        try:
            Job.fetch(prev_job.decode(), connection=conn).cancel()
        except Exception:  # noqa: BLE001 — already ran/cancelled: ignore
            pass
    # Renew the window per message, but never wait past first_ts + max_window.
    delay = min(base, max(0.0, first_ts + max_window - now))
    job = get_queue(AI_QUEUE).enqueue_in(
        timedelta(seconds=delay), run_conversation_ai, conversation_id)
    conn.hset(key, mapping={"first_ts": first_ts, "job_id": job.id})
    conn.expire(key, max_window + 60)


def _latest_inbound(conversation_id: int) -> Message | None:
    return db.session.scalar(
        db.select(Message).where(
            Message.conversation_id == conversation_id,
            Message.direction == MessageDirection.INBOUND,
            Message.sender_type == SenderType.CUSTOMER,
            Message.is_deleted.is_(False),
        ).order_by(Message.created_at.desc()).limit(1)
    )


def _burst_text(conversation_id: int) -> str:
    """Concatenate the trailing customer messages (since the last AI/agent turn)
    so keyword/phone scanning covers the whole coalesced burst."""
    rows = db.session.scalars(
        db.select(Message)
        .where(Message.conversation_id == conversation_id, Message.is_deleted.is_(False))
        .order_by(Message.created_at.desc())
        .limit(20)
    ).all()
    parts: list[str] = []
    for m in rows:
        if m.sender_type in (SenderType.AI, SenderType.AGENT, SenderType.SYSTEM):
            break
        if m.sender_type == SenderType.CUSTOMER and m.body:
            parts.append(m.body)
    return "\n".join(reversed(parts))


def _ai_replies_since_human(conversation_id: int) -> int:
    """How many AI auto-replies since a human last stepped in (or the last reset).

    Counts back to the most recent agent message or `ai_turn_reset_at` (order
    confirmation). Used as a runaway guard, NOT an escalation trigger (ticket §2).
    """
    conversation = db.session.get(Conversation, conversation_id)
    reset_at = conversation.ai_turn_reset_at if conversation else None
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
        if reset_at is not None and m.created_at is not None and m.created_at <= reset_at:
            break
        if m.sender_type == SenderType.AI:
            count += 1
    return count


def _process(message_id: int) -> None:
    """Synchronous surface + AI run for one message (debounce bypass; used by tests)."""
    message = db.session.get(Message, message_id)
    if message is None:
        return
    conversation = db.session.get(Conversation, message.conversation_id)
    if conversation is None:
        return
    realtime.message_created(message)
    realtime.conversation_updated(conversation)
    _run_ai(conversation.id)


def _run_ai(conversation_id: int) -> None:
    """Run the AI flow once for the conversation, covering any coalesced burst (§4).

    Uses the latest inbound customer message as the trigger; keyword/phone scanning
    spans the whole burst so nothing in a multi-message burst is missed.
    """
    conversation = db.session.get(Conversation, conversation_id)
    if conversation is None:
        return
    message = _latest_inbound(conversation_id)
    if message is None:
        return

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

    # Runaway guard: after too many AI replies with no human and no resolution, go
    # quiet and flag for staff — but do NOT escalate/hand off (ticket §2: only an
    # explicit "اكلم موظف" escalates). A human reply or an order resets the count.
    if _ai_replies_since_human(conversation.id) >= settings.max_consecutive_replies:
        if not conversation.needs_attention:
            conversation.needs_attention = True
            db.session.commit()
            name = conversation.contact.name if conversation.contact else "عميل"
            notify.notify_staff(
                NotificationType.NEEDS_ATTENTION,
                f"محادثة تجاوزت حد الردود التلقائية وتحتاج متابعة — {name}",
                conversation_id=conversation.id,
            )
            realtime.conversation_updated(conversation)
        return  # stop auto-replying this turn

    # Scan the whole coalesced burst for risk keywords + a typed phone (bot still replies).
    burst = _burst_text(conversation.id)
    _flag_attention(conversation, burst)
    _save_customer_phone(conversation, burst)

    # --- run the AI flow ---
    decision = ai_service.generate(conversation, trigger_message=message)

    # Provider outage (blank/error after retries): send the customer NOTHING
    # misleading; record ai_error (already logged) + alert staff (ticket §1).
    if decision.ai_error:
        _alert_ai_failure("ردّ فارغ من مزوّد الذكاء الاصطناعي بعد عدة محاولات")
        return

    sources = _source_titles(decision.used_chunk_ids)

    # Order confirmed (or edited) -> send the model's reply, create/update the order
    # row, stay AI-active, and alert staff. NOT an escalation (ticket §3).
    if decision.order_confirmed and decision.reply_text:
        _handle_order(conversation, decision, sources)
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

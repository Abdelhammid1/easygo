"""AI orchestration: build context, call the provider, decide reply vs escalate.

Implements the automatic-reply flow (spec §6.1) and escalation rules (§6.3),
and keeps the model provider-agnostic via get_provider().
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass

from app.extensions import db
from app.models.ai import AIRun, AISettings, PromptVersion
from app.models.core import Conversation, Message
from app.models.enums import EscalationReason, SenderType
from app.services import knowledge
from app.services.ai.base import AIProvider, ChatMessage
from app.services.ai.deepseek import DeepSeekProvider

log = logging.getLogger(__name__)

CONTEXT_WINDOW = 10  # recent messages fed to the model

# Maps the model's reason string to our enum.
_REASON_MAP = {
    "requested_human": EscalationReason.REQUESTED_HUMAN,
    "negative_sentiment": EscalationReason.NEGATIVE_SENTIMENT,
    "low_confidence": EscalationReason.LOW_CONFIDENCE,
    "no_kb_answer": EscalationReason.NO_KB_ANSWER,
    "sensitive_topic": EscalationReason.SENSITIVE_TOPIC,
    "repeated_failure": EscalationReason.REPEATED_FAILURE,
    "unreadable_media": EscalationReason.UNREADABLE_MEDIA,
    "ai_error": EscalationReason.AI_ERROR,
}

_JSON_CONTRACT = (
    "أعد ردك بصيغة JSON فقط دون أي نص خارج الـ JSON، بالشكل التالي:\n"
    '{"reply": "نص الرد للعميل", "confidence": 0.0, '
    '"escalate": false, "escalation_reason": null}\n'
    "اجعل escalate=true وحدّد escalation_reason بإحدى القيم "
    "[requested_human, negative_sentiment, sensitive_topic, no_kb_answer, low_confidence] "
    "إذا: طلب العميل التحدث مع موظف، أو ظهرت نبرة غضب/شكوى/استياء، أو كان الموضوع "
    "حساسًا (دفع، استرجاع، شكوى رسمية، مسائل قانونية)، أو لم تجد إجابة في قاعدة "
    "المعرفة، أو كانت ثقتك منخفضة. لا تخترع أسعارًا أو سياسات غير موجودة في قاعدة المعرفة."
)


@dataclass
class AIDecision:
    reply_text: str | None
    confidence: float
    escalate: bool
    reason: EscalationReason | None
    used_chunk_ids: list[int]
    latency_ms: int
    cost_usd: float | None
    raw_output: str


def get_provider(settings: AISettings) -> AIProvider:
    """Instantiate the configured provider (default: DeepSeek)."""
    api_key = settings.get_api_key() or ""
    if settings.provider == "deepseek":
        return DeepSeekProvider(api_key, settings.model, settings.base_url)
    raise NotImplementedError(f"Unknown AI provider: {settings.provider}")


def _system_prompt(settings: AISettings) -> str:
    base = ""
    if settings.active_prompt_version_id:
        pv = db.session.get(PromptVersion, settings.active_prompt_version_id)
        if pv:
            base = pv.system_prompt
    return f"{base}\n\n{_JSON_CONTRACT}" if base else _JSON_CONTRACT


def _history(conversation: Conversation) -> list[ChatMessage]:
    rows = db.session.scalars(
        db.select(Message)
        .where(Message.conversation_id == conversation.id, Message.is_deleted.is_(False))
        .order_by(Message.created_at.desc())
        .limit(CONTEXT_WINDOW)
    ).all()
    rows = list(reversed(rows))
    out: list[ChatMessage] = []
    for m in rows:
        if not m.body:
            continue
        role = "user" if m.sender_type == SenderType.CUSTOMER else "assistant"
        out.append(ChatMessage(role=role, content=m.body))
    return out


def _parse(raw: str) -> dict:
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        # Fallback: treat the whole output as a reply, low confidence.
        return {"reply": (raw or "").strip(), "confidence": 0.3, "escalate": False}


def playground(query: str) -> dict:
    """Dry-run the AI on an ad-hoc question (spec §6 KB-5). Persists nothing."""
    settings = db.session.get(AISettings, 1)
    if settings is None:
        raise RuntimeError("AI settings are not initialised (run `flask seed`)")

    chunks = knowledge.retrieve(query, limit=5)
    kb_block = "\n\n".join(f"- {c.content}" for c in chunks)
    messages = [ChatMessage("system", _system_prompt(settings))]
    if kb_block:
        messages.append(ChatMessage("system", f"مقاطع ذات صلة من قاعدة المعرفة:\n{kb_block}"))
    messages.append(ChatMessage("user", query))

    provider = get_provider(settings)
    completion = provider.complete(messages, json_mode=True)
    parsed = _parse(completion.content)
    return {
        "reply": parsed.get("reply"),
        "confidence": parsed.get("confidence"),
        "escalate": bool(parsed.get("escalate")),
        "escalation_reason": parsed.get("escalation_reason"),
        "used_chunks": [{"id": c.id, "item_id": c.item_id, "content": c.content}
                        for c in chunks],
        "cost_usd": completion.cost_usd,
    }


def generate(conversation: Conversation, trigger_message: Message | None = None) -> AIDecision:
    """Run the AI flow for a conversation and persist an AIRun log (§6.5)."""
    settings = db.session.get(AISettings, 1)
    if settings is None:
        raise RuntimeError("AI settings are not initialised (run `flask seed`)")

    query = (trigger_message.body if trigger_message else "") or ""
    chunks = knowledge.retrieve(query, limit=5)
    kb_block = "\n\n".join(f"- {c.content}" for c in chunks)

    messages: list[ChatMessage] = [ChatMessage("system", _system_prompt(settings))]
    if kb_block:
        messages.append(ChatMessage(
            "system", f"مقاطع ذات صلة من قاعدة المعرفة:\n{kb_block}"
        ))
    messages.extend(_history(conversation))

    provider = get_provider(settings)
    started = time.monotonic()
    try:
        completion = provider.complete(messages, json_mode=True)
        parsed = _parse(completion.content)
        raw_output = completion.content
        cost = completion.cost_usd
    except Exception as exc:  # noqa: BLE001 — AI failure must escalate, never drop
        log.error("AI provider error: %s", exc)
        parsed = {"reply": None, "confidence": 0.0, "escalate": True,
                  "escalation_reason": "ai_error"}
        raw_output = f"ERROR: {exc}"
        cost = None
    latency_ms = int((time.monotonic() - started) * 1000)

    confidence = float(parsed.get("confidence") or 0.0)
    escalate = bool(parsed.get("escalate"))
    reason = _REASON_MAP.get(parsed.get("escalation_reason") or "")

    # Enforce the confidence threshold regardless of what the model said.
    if confidence < settings.confidence_threshold:
        escalate = True
        reason = reason or EscalationReason.LOW_CONFIDENCE

    reply_text = (parsed.get("reply") or "").strip() or None
    if escalate and reason is None:
        reason = EscalationReason.LOW_CONFIDENCE

    decision = AIDecision(
        reply_text=None if escalate else reply_text,
        confidence=confidence,
        escalate=escalate,
        reason=reason if escalate else None,
        used_chunk_ids=[c.id for c in chunks],
        latency_ms=latency_ms,
        cost_usd=cost,
        raw_output=raw_output,
    )

    db.session.add(AIRun(
        conversation_id=conversation.id,
        message_id=trigger_message.id if trigger_message else None,
        input_context=[{"role": m.role, "content": m.content} for m in messages],
        used_chunk_ids=decision.used_chunk_ids,
        output_text=decision.reply_text,
        confidence=decision.confidence,
        escalated=decision.escalate,
        escalation_reason=decision.reason,
        latency_ms=decision.latency_ms,
        cost_usd=decision.cost_usd,
    ))
    db.session.commit()
    return decision

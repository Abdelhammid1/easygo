"""Inbox API: list conversations, read messages, reply, assign, change state/AI."""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.extensions import db
from app.models.ai import AIRun, KBChunk, KBItem
from app.models.core import Attachment, Conversation, Message, User
from app.models.enums import AIMode, ConversationState, SenderType, UserRole, UserStatus
from app.models.support import InternalNote, Tag
from app.security.permissions import Permission, require_permission
from app.services import outgoing, realtime

bp = Blueprint("conversations", __name__, url_prefix="/api/conversations")


def _conv_json(c: Conversation) -> dict:
    contact = c.contact
    expires = c.reply_window_expires_at
    return {
        "id": c.id,
        "channel": getattr(c.channel.type, "value", c.channel.type) if c.channel else None,
        "contact": {"id": contact.id, "name": contact.name} if contact else None,
        "state": getattr(c.state, "value", c.state),
        "ai_mode": getattr(c.ai_mode, "value", c.ai_mode),
        "escalation_reason": getattr(c.escalation_reason, "value", c.escalation_reason),
        "assignee_id": c.assignee_id,
        "unread_count": c.unread_count,
        "last_message_preview": c.last_message_preview,
        "last_message_at": c.last_message_at.isoformat() if c.last_message_at else None,
        "reply_window_expires_at": expires.isoformat() if expires else None,
        "reply_window_open": outgoing.reply_window_open(c),
    }


def _conv_detail(c: Conversation) -> dict:
    """Richer serialization for the open conversation (context panel)."""
    data = _conv_json(c)
    contact = c.contact
    assignee = c.assignee
    data["contact"] = (
        {
            "id": contact.id,
            "name": contact.name,
            "phone": contact.phone,
            "address": contact.address,
            "is_blocked": contact.is_blocked,
            "created_at": contact.created_at.isoformat() if contact.created_at else None,
        }
        if contact
        else None
    )
    data["assignee"] = {"id": assignee.id, "name": assignee.name} if assignee else None
    data["tags"] = [{"id": t.id, "name": t.name, "color": t.color} for t in c.tags]
    return data


def _msg_json(m: Message) -> dict:
    return {
        "id": m.id,
        "direction": getattr(m.direction, "value", m.direction),
        "sender_type": getattr(m.sender_type, "value", m.sender_type),
        "sender_user_id": m.sender_user_id,
        "type": getattr(m.type, "value", m.type),
        "body": m.body,
        "send_status": getattr(m.send_status, "value", m.send_status),
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "attachments": [
            {
                "id": a.id,
                "type": getattr(a.type, "value", a.type),
                "url": f"/api/media/attachments/{a.id}",
                "mime_type": a.mime_type,
                "transcript": a.extracted_text,
                "image_description": a.image_description,
            }
            for a in m.attachments
        ],
    }


@bp.get("")
@login_required
@require_permission(Permission.VIEW_CONVERSATIONS)
def list_conversations():
    query = db.select(Conversation)
    state = request.args.get("state")
    if state:
        try:
            query = query.where(Conversation.state == ConversationState(state))
        except ValueError:
            return jsonify(error="invalid_state"), 400
    assignee = request.args.get("assignee")
    if assignee == "me":
        query = query.where(Conversation.assignee_id == current_user.id)
    query = query.order_by(Conversation.last_message_at.desc().nullslast()).limit(100)
    rows = db.session.scalars(query).all()
    return jsonify(conversations=[_conv_json(c) for c in rows])


@bp.get("/<int:conversation_id>/messages")
@login_required
@require_permission(Permission.VIEW_CONVERSATIONS)
def get_messages(conversation_id: int):
    conv = db.session.get(Conversation, conversation_id)
    if conv is None:
        return jsonify(error="not_found"), 404
    msgs = db.session.scalars(
        db.select(Message)
        .where(Message.conversation_id == conversation_id, Message.is_deleted.is_(False))
        .order_by(Message.created_at)
    ).all()
    # Opening a conversation clears its unread counter.
    conv.unread_count = 0
    db.session.commit()
    return jsonify(conversation=_conv_detail(conv), messages=[_msg_json(m) for m in msgs])


@bp.post("/<int:conversation_id>/reply")
@login_required
@require_permission(Permission.REPLY_CONVERSATIONS)
def reply(conversation_id: int):
    conv = db.session.get(Conversation, conversation_id)
    if conv is None:
        return jsonify(error="not_found"), 404
    text = (request.get_json(silent=True) or {}).get("text", "").strip()
    if not text:
        return jsonify(error="empty_message"), 400
    if conv.contact and conv.contact.is_blocked:
        return jsonify(error="contact_blocked"), 400
    # Meta 24h window: block before sending and tell the agent (spec §5.1).
    if not outgoing.reply_window_open(conv):
        return jsonify(error="reply_window_expired"), 409

    message = outgoing.send_reply(
        conv, text, sender_type=SenderType.AGENT, sender_user_id=current_user.id
    )

    # A human reply stops the AI on this conversation (spec §8).
    conv.ai_mode = AIMode.OFF
    if conv.assignee_id is None:
        conv.assignee_id = current_user.id
    if conv.state == ConversationState.NEEDS_HUMAN:
        conv.state = ConversationState.OPEN
    conv.unread_count = 0
    db.session.commit()
    realtime.conversation_updated(conv)

    if message.send_status and getattr(message.send_status, "value", "") == "failed":
        return jsonify(message=_msg_json(message), warning="send_failed"), 502
    return jsonify(message=_msg_json(message))


@bp.post("/<int:conversation_id>/ai-mode")
@login_required
@require_permission(Permission.TOGGLE_AI_CONVERSATION)
def set_ai_mode(conversation_id: int):
    conv = db.session.get(Conversation, conversation_id)
    if conv is None:
        return jsonify(error="not_found"), 404
    try:
        mode = AIMode((request.get_json(silent=True) or {}).get("mode", ""))
    except ValueError:
        return jsonify(error="invalid_mode"), 400
    conv.ai_mode = mode
    # Re-enabling AI after escalation returns the conversation to open.
    if mode == AIMode.ACTIVE and conv.state == ConversationState.NEEDS_HUMAN:
        conv.state = ConversationState.OPEN
        conv.escalation_reason = None
    db.session.commit()
    realtime.conversation_updated(conv)
    return jsonify(conversation=_conv_detail(conv))


@bp.post("/<int:conversation_id>/state")
@login_required
@require_permission(Permission.CHANGE_CONVERSATION_STATE)
def set_state(conversation_id: int):
    conv = db.session.get(Conversation, conversation_id)
    if conv is None:
        return jsonify(error="not_found"), 404
    try:
        state = ConversationState((request.get_json(silent=True) or {}).get("state", ""))
    except ValueError:
        return jsonify(error="invalid_state"), 400
    conv.state = state
    db.session.commit()
    realtime.conversation_updated(conv)
    return jsonify(conversation=_conv_detail(conv))


@bp.post("/<int:conversation_id>/assign")
@login_required
@require_permission(Permission.ASSIGN_CONVERSATIONS)
def assign(conversation_id: int):
    conv = db.session.get(Conversation, conversation_id)
    if conv is None:
        return jsonify(error="not_found"), 404
    assignee_id = (request.get_json(silent=True) or {}).get("assignee_id")

    # Agents may only assign conversations to themselves (spec §3).
    role_value = getattr(current_user.role, "value", current_user.role)
    if role_value == UserRole.AGENT.value and assignee_id not in (None, current_user.id):
        return jsonify(error="agents_can_only_self_assign"), 403

    conv.assignee_id = assignee_id
    db.session.commit()
    realtime.conversation_updated(conv)
    return jsonify(conversation=_conv_detail(conv))


# ---------------- context panel: co-pilot, notes, tags, team ----------------

@bp.get("/<int:conversation_id>/copilot")
@login_required
@require_permission(Permission.VIEW_CONVERSATIONS)
def copilot(conversation_id: int):
    """Latest AI run for the conversation — powers the co-pilot panel (§6.5)."""
    run = db.session.scalar(
        db.select(AIRun).where(AIRun.conversation_id == conversation_id)
        .order_by(AIRun.created_at.desc()).limit(1)
    )
    if run is None:
        return jsonify(run=None)
    titles = []
    if run.used_chunk_ids:
        titles = [
            t for (t,) in db.session.execute(
                db.select(KBItem.title).join(KBChunk, KBChunk.item_id == KBItem.id)
                .where(KBChunk.id.in_(run.used_chunk_ids))
            ).all()
        ]
    return jsonify(run={
        "confidence": run.confidence,
        "escalated": run.escalated,
        "escalation_reason": getattr(run.escalation_reason, "value", run.escalation_reason),
        "suggested_reply": run.output_text,
        "sources": sorted(set(titles)),
        "cost_usd": float(run.cost_usd) if run.cost_usd is not None else None,
        "at": run.created_at.isoformat() if run.created_at else None,
    })


@bp.get("/<int:conversation_id>/notes")
@login_required
@require_permission(Permission.VIEW_CONVERSATIONS)
def list_notes(conversation_id: int):
    rows = db.session.scalars(
        db.select(InternalNote).where(InternalNote.conversation_id == conversation_id)
        .order_by(InternalNote.created_at.desc())
    ).all()
    return jsonify(notes=[
        {
            "id": n.id,
            "body": n.body,
            "author": n.author.name if n.author else None,
            "at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in rows
    ])


@bp.post("/<int:conversation_id>/notes")
@login_required
@require_permission(Permission.VIEW_CONVERSATIONS)
def add_note(conversation_id: int):
    body = (request.get_json(silent=True) or {}).get("body", "").strip()
    if not body:
        return jsonify(error="empty_note"), 400
    note = InternalNote(conversation_id=conversation_id, author_id=current_user.id, body=body)
    db.session.add(note)
    db.session.commit()
    return jsonify(note={
        "id": note.id, "body": note.body, "author": current_user.name,
        "at": note.created_at.isoformat() if note.created_at else None,
    }), 201


@bp.post("/<int:conversation_id>/tags")
@login_required
@require_permission(Permission.VIEW_CONVERSATIONS)
def add_tag(conversation_id: int):
    conv = db.session.get(Conversation, conversation_id)
    if conv is None:
        return jsonify(error="not_found"), 404
    tag_id = (request.get_json(silent=True) or {}).get("tag_id")
    tag = db.session.get(Tag, tag_id) if tag_id else None
    if tag is None:
        return jsonify(error="tag_not_found"), 404
    if tag not in conv.tags:
        conv.tags.append(tag)
        db.session.commit()
    return jsonify(conversation=_conv_detail(conv))


@bp.delete("/<int:conversation_id>/tags/<int:tag_id>")
@login_required
@require_permission(Permission.VIEW_CONVERSATIONS)
def remove_tag(conversation_id: int, tag_id: int):
    conv = db.session.get(Conversation, conversation_id)
    if conv is None:
        return jsonify(error="not_found"), 404
    tag = db.session.get(Tag, tag_id)
    if tag and tag in conv.tags:
        conv.tags.remove(tag)
        db.session.commit()
    return jsonify(conversation=_conv_detail(conv))


@bp.get("/assignable")
@login_required
@require_permission(Permission.VIEW_CONVERSATIONS)
def assignable():
    """Active staff a conversation can be assigned to (for the assign dropdown)."""
    rows = db.session.scalars(
        db.select(User).where(User.status == UserStatus.ACTIVE).order_by(User.name)
    ).all()
    return jsonify(users=[
        {"id": u.id, "name": u.name, "role": getattr(u.role, "value", u.role)} for u in rows
    ])

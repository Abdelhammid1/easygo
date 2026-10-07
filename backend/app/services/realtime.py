"""Emit live updates to connected clients (spec §4, IN-12).

Safe to call from the web process or the worker: Socket.IO is configured with a
Redis message queue, so emits from the worker reach web-connected clients.
"""
from __future__ import annotations

import logging

from app.extensions import socketio

log = logging.getLogger(__name__)


def _message_payload(message) -> dict:
    return {
        "id": message.id,
        "conversation_id": message.conversation_id,
        "direction": getattr(message.direction, "value", message.direction),
        "sender_type": getattr(message.sender_type, "value", message.sender_type),
        "type": getattr(message.type, "value", message.type),
        "body": message.body,
        "created_at": message.created_at.isoformat() if message.created_at else None,
    }


def _conversation_payload(conversation) -> dict:
    return {
        "id": conversation.id,
        "state": getattr(conversation.state, "value", conversation.state),
        "ai_mode": getattr(conversation.ai_mode, "value", conversation.ai_mode),
        "assignee_id": conversation.assignee_id,
        "unread_count": conversation.unread_count,
        "last_message_preview": conversation.last_message_preview,
        "escalation_reason": getattr(
            conversation.escalation_reason, "value", conversation.escalation_reason
        ),
    }


def _emit(event: str, payload: dict, room: str | None = None) -> None:
    try:
        socketio.emit(event, payload, to=room)
    except Exception as exc:  # noqa: BLE001 — realtime is best-effort, never fatal
        log.warning("socketio emit %s failed: %s", event, exc)


def message_created(message) -> None:
    _emit("message:new", _message_payload(message), room=f"conversation:{message.conversation_id}")


def conversation_updated(conversation) -> None:
    payload = _conversation_payload(conversation)
    _emit("conversation:update", payload, room=f"conversation:{conversation.id}")
    _emit("inbox:update", payload)  # inbox list refresh for everyone


def notify_user(user_id: int, payload: dict) -> None:
    """Live in-app notification to one user's personal room (spec §5.5 NT-1)."""
    _emit("notification:new", payload, room=f"user:{user_id}")

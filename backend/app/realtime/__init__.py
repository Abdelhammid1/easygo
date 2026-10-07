"""Realtime (Socket.IO) events for live inbox updates (spec §4, IN-12).

Phase 0 wires authentication and room joining only. Phase 1 emits
message/conversation events from the worker via the Redis message queue.
"""
from __future__ import annotations

from flask_login import current_user
from flask_socketio import join_room

from app.extensions import socketio


@socketio.on("connect")
def on_connect():
    if not getattr(current_user, "is_authenticated", False):
        return False  # reject unauthenticated sockets
    # Each user gets a personal room for direct notifications.
    join_room(f"user:{current_user.id}")
    return None


@socketio.on("conversation:open")
def on_open_conversation(data):
    """Agent opened a conversation — join its room to receive live updates."""
    conv_id = (data or {}).get("conversation_id")
    if conv_id:
        join_room(f"conversation:{conv_id}")


@socketio.on("disconnect")
def on_disconnect():
    # Room cleanup is handled by Socket.IO automatically.
    return None

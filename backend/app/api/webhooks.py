"""Inbound channel webhooks.

Design rule (spec §4.1): store fast, process later. The webhook verifies the
signature, persists each message, enqueues a job, and returns 200 immediately.
"""
from __future__ import annotations

import logging

from flask import Blueprint, abort, current_app, jsonify, request

from app.channels.meta import verify_signature
from app.channels.registry import get_adapter
from app.extensions import db
from app.models.core import Channel
from app.models.enums import ChannelType
from app.services import ingestion
from app.tasks.queue import enqueue_incoming

log = logging.getLogger(__name__)

bp = Blueprint("webhooks", __name__, url_prefix="/api/webhooks")


@bp.post("/telegram/<int:channel_id>")
def telegram_webhook(channel_id: int):
    channel = db.session.get(Channel, channel_id)
    if channel is None or channel.type != ChannelType.TELEGRAM:
        abort(404)

    # Verify the secret token Telegram echoes back (spec §5.1 CH-5).
    secret = channel.get_credentials().get("webhook_secret")
    got = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if secret and got != secret:
        log.warning("Telegram webhook secret mismatch for channel %s", channel_id)
        abort(403)

    payload = request.get_json(silent=True) or {}
    adapter = get_adapter(channel)

    try:
        normalized = adapter.parse_webhook(payload)
    except Exception:  # noqa: BLE001 — never 500 back to Telegram
        log.exception("Failed to parse Telegram update for channel %s", channel_id)
        return jsonify(ok=True)  # ack anyway to avoid redelivery storms

    for nm in normalized:
        message = ingestion.store_incoming(channel, nm)
        if message is not None:
            enqueue_incoming(message.id)

    return jsonify(ok=True)


# ---------------- Meta (Messenger + Instagram) ----------------

_META_TYPES = (ChannelType.MESSENGER, ChannelType.INSTAGRAM)


@bp.get("/meta")
def meta_verify():
    """Meta webhook verification handshake (configured once in the app dashboard)."""
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token and token == current_app.config.get("META_VERIFY_TOKEN"):
        return challenge or "", 200
    return "forbidden", 403


@bp.post("/meta")
def meta_webhook():
    raw = request.get_data()
    app_secret = current_app.config.get("META_APP_SECRET", "")
    if not verify_signature(app_secret, raw, request.headers.get("X-Hub-Signature-256")):
        log.warning("Meta webhook signature verification failed")
        abort(403)

    payload = request.get_json(silent=True) or {}
    # entry[].id is the Page id (Messenger) or IG account id (Instagram); we map
    # it to a channel via external_ref (set when the channel was connected).
    for entry in payload.get("entry", []):
        account_id = str(entry.get("id"))
        channel = db.session.scalar(
            db.select(Channel).where(
                Channel.external_ref == account_id, Channel.type.in_(_META_TYPES)
            )
        )
        if channel is None:
            log.info("Meta event for unknown account %s — ignored", account_id)
            continue
        adapter = get_adapter(channel)
        try:
            normalized = adapter.parse_webhook(entry)
        except Exception:  # noqa: BLE001 — ack anyway to avoid redelivery storms
            log.exception("Failed to parse Meta entry for channel %s", channel.id)
            continue
        for nm in normalized:
            message = ingestion.store_incoming(channel, nm)
            if message is not None:
                enqueue_incoming(message.id)

    return jsonify(ok=True)

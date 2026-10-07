"""In-app notifications (spec §5.5)."""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.extensions import db
from app.models.support import Notification, PushSubscription
from app.services import push

bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")


def _json(n: Notification) -> dict:
    return {
        "id": n.id,
        "type": getattr(n.type, "value", n.type),
        "body": n.body,
        "conversation_id": n.conversation_id,
        "is_read": n.is_read,
        "created_at": n.created_at.isoformat() if n.created_at else None,
    }


@bp.get("")
@login_required
def list_notifications():
    only_unread = request.args.get("unread") == "1"
    query = db.select(Notification).where(Notification.user_id == current_user.id)
    if only_unread:
        query = query.where(Notification.is_read.is_(False))
    query = query.order_by(Notification.created_at.desc()).limit(100)
    rows = db.session.scalars(query).all()
    unread = db.session.scalar(
        db.select(db.func.count(Notification.id)).where(
            Notification.user_id == current_user.id, Notification.is_read.is_(False)
        )
    )
    return jsonify(notifications=[_json(n) for n in rows], unread_count=unread or 0)


@bp.post("/<int:notification_id>/read")
@login_required
def mark_read(notification_id: int):
    n = db.session.get(Notification, notification_id)
    if n is None or n.user_id != current_user.id:
        return jsonify(error="not_found"), 404
    n.is_read = True
    db.session.commit()
    return jsonify(ok=True)


@bp.post("/read-all")
@login_required
def mark_all_read():
    db.session.execute(
        db.update(Notification)
        .where(Notification.user_id == current_user.id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    db.session.commit()
    return jsonify(ok=True)


# ------------------------- web push (NT-2) -------------------------

@bp.get("/push/key")
@login_required
def push_key():
    """Public VAPID key the browser needs to subscribe (null if push disabled)."""
    return jsonify(public_key=push.public_key())


@bp.post("/push/subscribe")
@login_required
def push_subscribe():
    data = request.get_json(silent=True) or {}
    endpoint = data.get("endpoint")
    keys = data.get("keys") or {}
    p256dh, auth = keys.get("p256dh"), keys.get("auth")
    if not endpoint or not p256dh or not auth:
        return jsonify(error="invalid_subscription"), 400

    existing = db.session.scalar(
        db.select(PushSubscription).filter_by(endpoint=endpoint)
    )
    if existing:
        existing.user_id = current_user.id  # re-bind to current user
        existing.p256dh, existing.auth = p256dh, auth
    else:
        db.session.add(PushSubscription(
            user_id=current_user.id, endpoint=endpoint, p256dh=p256dh, auth=auth
        ))
    db.session.commit()
    return jsonify(ok=True)


@bp.post("/push/unsubscribe")
@login_required
def push_unsubscribe():
    endpoint = (request.get_json(silent=True) or {}).get("endpoint")
    if endpoint:
        db.session.execute(
            db.delete(PushSubscription).where(
                PushSubscription.endpoint == endpoint,
                PushSubscription.user_id == current_user.id,
            )
        )
        db.session.commit()
    return jsonify(ok=True)

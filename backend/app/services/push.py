"""Web Push delivery (spec §5.5 NT-2). Disabled when VAPID keys are unconfigured."""
from __future__ import annotations

import json
import logging

from flask import current_app

from app.extensions import db
from app.models.support import PushSubscription

log = logging.getLogger(__name__)


def is_configured() -> bool:
    cfg = current_app.config
    return bool(cfg.get("VAPID_PUBLIC_KEY") and cfg.get("VAPID_PRIVATE_KEY"))


def public_key() -> str | None:
    return current_app.config.get("VAPID_PUBLIC_KEY") or None


def send_to_user(user_id: int, payload: dict) -> int:
    """Push `payload` to all of a user's subscriptions. Returns # delivered.

    Subscriptions the browser has dropped (404/410) are pruned. Best-effort:
    never raises. Caller need not commit — pruning commits itself.
    """
    if not is_configured():
        return 0
    try:
        from pywebpush import WebPushException, webpush
    except Exception as exc:  # noqa: BLE001
        log.warning("pywebpush unavailable: %s", exc)
        return 0

    cfg = current_app.config
    subs = db.session.scalars(
        db.select(PushSubscription).where(PushSubscription.user_id == user_id)
    ).all()
    delivered = 0
    stale: list[int] = []
    for sub in subs:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=json.dumps(payload, ensure_ascii=False),
                vapid_private_key=cfg["VAPID_PRIVATE_KEY"],
                vapid_claims={"sub": cfg.get("VAPID_SUBJECT", "mailto:admin@localhost")},
            )
            delivered += 1
        except WebPushException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status in (404, 410):
                stale.append(sub.id)  # subscription expired — drop it
            else:
                log.warning("web push failed: %s", exc)
        except Exception as exc:  # noqa: BLE001
            log.warning("web push error: %s", exc)

    if stale:
        db.session.execute(
            db.delete(PushSubscription).where(PushSubscription.id.in_(stale))
        )
        db.session.commit()
    return delivered

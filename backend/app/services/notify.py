"""Central notification dispatch (spec §5.5): in-app row + realtime + web push,
plus email for failure alerts (NT-3)."""
from __future__ import annotations

from datetime import timedelta

from app.extensions import db
from app.models.base import utcnow
from app.models.core import User
from app.models.enums import NotificationType, UserRole, UserStatus
from app.models.support import Notification
from app.services import email, push, realtime


def create(
    user_id: int,
    ntype: NotificationType,
    body: str | None = None,
    conversation_id: int | None = None,
) -> Notification:
    """Add an in-app notification and fan out live + push. Caller commits."""
    note = Notification(
        user_id=user_id, type=ntype, body=body, conversation_id=conversation_id
    )
    db.session.add(note)
    db.session.flush()

    payload = {
        "id": note.id,
        "type": getattr(ntype, "value", ntype),
        "body": body,
        "conversation_id": conversation_id,
    }
    realtime.notify_user(user_id, payload)
    push.send_to_user(user_id, {"title": "easyGo", "body": body or "",
                                "conversation_id": conversation_id})
    return note


def _active_staff(roles: list[UserRole]) -> list[User]:
    return list(db.session.scalars(
        db.select(User).where(User.status == UserStatus.ACTIVE, User.role.in_(roles))
    ).all())


def notify_staff(
    ntype: NotificationType,
    body: str,
    *,
    conversation_id: int | None = None,
    roles: list[UserRole] | None = None,
) -> None:
    """Notify every active staff member in the given roles (default: all). Commits."""
    roles = roles or [UserRole.AGENT, UserRole.SUPERVISOR, UserRole.ADMIN]
    for user in _active_staff(roles):
        create(user.id, ntype, body, conversation_id)
    db.session.commit()


def alert_admins(
    ntype: NotificationType,
    subject: str,
    body: str,
    *,
    throttle_minutes: int | None = None,
) -> bool:
    """Operational alert to admins/supervisors: in-app + push + email (NT-3).

    With `throttle_minutes`, skips entirely if an alert of this type was already
    created within that window (avoids repeated-failure spam). Commits. Returns
    True if it alerted, False if throttled.
    """
    if throttle_minutes:
        cutoff = utcnow() - timedelta(minutes=throttle_minutes)
        recent = db.session.scalar(
            db.select(Notification.id).where(
                Notification.type == ntype, Notification.created_at >= cutoff
            ).limit(1)
        )
        if recent:
            return False

    admins = _active_staff([UserRole.ADMIN, UserRole.SUPERVISOR])
    for user in admins:
        create(user.id, ntype, body)
    db.session.commit()
    emails = [u.email for u in admins if getattr(u.role, "value", u.role) == UserRole.ADMIN.value]
    if emails:
        email.send_email(emails, subject, body)
    return True

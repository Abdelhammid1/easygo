"""Audit trail helper (spec §5.7 AD-5).

Call record(...) inside a request before the surrounding commit; it adds an
AuditLog row to the current session, leaving the commit to the caller.
"""
from __future__ import annotations

from typing import Any

from flask_login import current_user

from app.extensions import db
from app.models.support import AuditLog


def record(
    action: str,
    *,
    entity_type: str | None = None,
    entity_id: Any = None,
    before: dict | None = None,
    after: dict | None = None,
    user_id: int | None = None,
) -> None:
    if user_id is None and getattr(current_user, "is_authenticated", False):
        user_id = current_user.id
    db.session.add(AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        before=before,
        after=after,
    ))

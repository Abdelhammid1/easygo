"""Common model mixins."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from app.extensions import db


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    if TYPE_CHECKING:
        # SQLAlchemy's declarative constructor accepts column values as kwargs,
        # but its type stubs don't express that; this keeps pyright correct
        # without affecting the real runtime constructor.
        def __init__(self, **kwargs: Any) -> None: ...

    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

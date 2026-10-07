"""Supporting entities: tags, internal notes, canned responses, notifications, audit."""
from __future__ import annotations

from app.extensions import db
from app.models.base import TimestampMixin
from app.models.enums import NotificationType


def _enum(e, length=24):
    return db.Enum(e, native_enum=False, length=length, validate_strings=True)


# Many-to-many between conversations and tags.
conversation_tags = db.Table(
    "conversation_tags",
    db.Column("conversation_id", db.Integer,
              db.ForeignKey("conversations.id", ondelete="CASCADE"), primary_key=True),
    db.Column("tag_id", db.Integer,
              db.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Tag(TimestampMixin, db.Model):
    __tablename__ = "tags"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), unique=True, nullable=False)
    color = db.Column(db.String(16), nullable=True)

    conversations = db.relationship(
        "Conversation", secondary=conversation_tags, back_populates="tags"
    )


class InternalNote(TimestampMixin, db.Model):
    """A note on a conversation, never visible to the customer (spec §5.2)."""
    __tablename__ = "internal_notes"

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(
        db.Integer, db.ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    body = db.Column(db.Text, nullable=False)

    author = db.relationship("User")


class CannedResponse(TimestampMixin, db.Model):
    __tablename__ = "canned_responses"

    id = db.Column(db.Integer, primary_key=True)
    shortcut = db.Column(db.String(40), unique=True, nullable=False)
    body = db.Column(db.Text, nullable=False)


class Notification(TimestampMixin, db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    type = db.Column(_enum(NotificationType), nullable=False)
    body = db.Column(db.Text, nullable=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey("conversations.id"), nullable=True)
    is_read = db.Column(db.Boolean, nullable=False, default=False)


class PushSubscription(TimestampMixin, db.Model):
    """A browser Web Push subscription for a user (spec §5.5 NT-2)."""
    __tablename__ = "push_subscriptions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    endpoint = db.Column(db.Text, unique=True, nullable=False)
    p256dh = db.Column(db.String(255), nullable=False)
    auth = db.Column(db.String(255), nullable=False)


class AuditLog(TimestampMixin, db.Model):
    """Append-only record of important actions (spec §5.7 AD-5)."""
    __tablename__ = "audit_logs"

    id = db.Column(db.BigInteger, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    action = db.Column(db.String(80), nullable=False, index=True)
    entity_type = db.Column(db.String(60), nullable=True)
    entity_id = db.Column(db.String(60), nullable=True)
    before = db.Column(db.JSON, nullable=True)
    after = db.Column(db.JSON, nullable=True)

    user = db.relationship("User")

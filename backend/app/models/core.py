"""Core entities: users, channels, contacts, conversations, messages, media."""
from __future__ import annotations

from typing import TYPE_CHECKING

from flask_login import UserMixin
from sqlalchemy.orm import Mapped, relationship

from app.extensions import bcrypt, db
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.support import Tag
from app.models.enums import (
    AttachmentType,
    ChannelStatus,
    ChannelType,
    ConversationState,
    AIMode,
    EscalationReason,
    MessageDirection,
    MessageType,
    SendStatus,
    SenderType,
    UserRole,
    UserStatus,
)


def _enum(e, length=24):
    return db.Enum(e, native_enum=False, length=length, validate_strings=True)


class User(TimestampMixin, UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(_enum(UserRole), nullable=False, default=UserRole.AGENT)
    status = db.Column(_enum(UserStatus), nullable=False, default=UserStatus.ACTIVE)
    last_login_at = db.Column(db.DateTime(timezone=True), nullable=True)

    def set_password(self, raw: str) -> None:
        self.password_hash = bcrypt.generate_password_hash(raw).decode()

    def check_password(self, raw: str) -> bool:
        return bcrypt.check_password_hash(self.password_hash, raw)

    @property
    def is_active(self):  # type: ignore[override]  # Flask-Login: only active users may log in
        return self.status == UserStatus.ACTIVE

    def __repr__(self) -> str:
        return f"<User {self.email} ({self.role})>"


class Channel(TimestampMixin, db.Model):
    """A connected messaging channel. Credentials are encrypted at rest."""
    __tablename__ = "channels"

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(_enum(ChannelType), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    status = db.Column(
        _enum(ChannelStatus), nullable=False, default=ChannelStatus.DISCONNECTED
    )
    # Fernet-encrypted JSON (bot token, webhook secret, page id, ...).
    credentials_enc = db.Column(db.Text, nullable=True)
    # Non-secret channel config (webhook url, bot commands, username, ...).
    config = db.Column(db.JSON, nullable=True)
    # Per-channel AI behaviour overrides (JSON).
    ai_settings = db.Column(db.JSON, nullable=True)
    external_ref = db.Column(db.String(255), nullable=True)  # bot id / page id
    last_error = db.Column(db.Text, nullable=True)

    conversations = db.relationship("Conversation", back_populates="channel")

    def set_credentials(self, data: dict) -> None:
        from app.security.crypto import encrypt_json
        self.credentials_enc = encrypt_json(data) if data else None

    def get_credentials(self) -> dict:
        from app.security.crypto import decrypt_json
        return decrypt_json(self.credentials_enc) if self.credentials_enc else {}

    def __repr__(self) -> str:
        return f"<Channel {self.type}:{self.name}>"


class Contact(TimestampMixin, db.Model):
    """A customer. One contact may have identities across several channels."""
    __tablename__ = "contacts"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=True)
    phone = db.Column(db.String(40), nullable=True, index=True)
    address = db.Column(db.String(400), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    is_blocked = db.Column(db.Boolean, nullable=False, default=False)
    custom_fields = db.Column(db.JSON, nullable=True)

    identities: Mapped[list["ContactIdentity"]] = relationship(
        "ContactIdentity", back_populates="contact", cascade="all, delete-orphan"
    )
    conversations = db.relationship("Conversation", back_populates="contact")

    def __repr__(self) -> str:
        return f"<Contact {self.id}:{self.name}>"


class ContactIdentity(TimestampMixin, db.Model):
    """How a contact appears on a specific channel (external id + avatar)."""
    __tablename__ = "contact_identities"
    __table_args__ = (
        db.UniqueConstraint("channel_id", "external_id", name="uq_identity_channel_ext"),
    )

    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(
        db.Integer, db.ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False
    )
    channel_id = db.Column(db.Integer, db.ForeignKey("channels.id"), nullable=False)
    external_id = db.Column(db.String(255), nullable=False, index=True)
    display_name = db.Column(db.String(160), nullable=True)
    avatar_url = db.Column(db.String(500), nullable=True)

    contact = db.relationship("Contact", back_populates="identities")
    channel = db.relationship("Channel")


class Conversation(TimestampMixin, db.Model):
    __tablename__ = "conversations"

    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(db.Integer, db.ForeignKey("channels.id"), nullable=False)
    contact_id = db.Column(db.Integer, db.ForeignKey("contacts.id"), nullable=False)
    assignee_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    state = db.Column(
        _enum(ConversationState), nullable=False, default=ConversationState.OPEN,
        index=True,
    )
    ai_mode = db.Column(_enum(AIMode), nullable=False, default=AIMode.ACTIVE)
    escalation_reason = db.Column(_enum(EscalationReason, length=32), nullable=True)

    unread_count = db.Column(db.Integer, nullable=False, default=0)
    last_message_at = db.Column(db.DateTime(timezone=True), nullable=True, index=True)
    last_message_preview = db.Column(db.String(280), nullable=True)
    # Meta 24h reply window: when sending becomes restricted (spec §5.1).
    reply_window_expires_at = db.Column(db.DateTime(timezone=True), nullable=True)

    channel = db.relationship("Channel", back_populates="conversations")
    contact = db.relationship("Contact", back_populates="conversations")
    assignee = db.relationship("User")
    messages = db.relationship(
        "Message", back_populates="conversation",
        cascade="all, delete-orphan", order_by="Message.created_at",
    )
    tags: Mapped[list["Tag"]] = relationship(
        "Tag", secondary="conversation_tags", back_populates="conversations"
    )

    def __repr__(self) -> str:
        return f"<Conversation {self.id} state={self.state}>"


class Message(TimestampMixin, db.Model):
    """Every inbound message is stored before any processing (spec §8)."""
    __tablename__ = "messages"
    __table_args__ = (
        # Idempotency: the same external message is never stored twice (spec §4.1).
        # Keyed per-conversation because providers (e.g. Telegram) scope their
        # message ids per chat, not per channel — the same id recurs across chats.
        db.UniqueConstraint(
            "conversation_id", "external_id", name="uq_message_conversation_ext"
        ),
    )

    id = db.Column(db.BigInteger, primary_key=True)
    conversation_id = db.Column(
        db.Integer, db.ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    channel_id = db.Column(db.Integer, db.ForeignKey("channels.id"), nullable=False)

    direction = db.Column(_enum(MessageDirection), nullable=False)
    sender_type = db.Column(_enum(SenderType), nullable=False)
    sender_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    type = db.Column(_enum(MessageType), nullable=False, default=MessageType.TEXT)
    body = db.Column(db.Text, nullable=True)

    external_id = db.Column(db.String(255), nullable=True)  # provider message id
    send_status = db.Column(_enum(SendStatus), nullable=True)  # outbound only
    error_reason = db.Column(db.Text, nullable=True)
    is_deleted = db.Column(db.Boolean, nullable=False, default=False)

    conversation = db.relationship("Conversation", back_populates="messages")
    attachments: Mapped[list["Attachment"]] = relationship(
        "Attachment", back_populates="message", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Message {self.id} {self.direction}/{self.sender_type}>"


class Attachment(TimestampMixin, db.Model):
    __tablename__ = "attachments"

    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(
        db.BigInteger, db.ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    type = db.Column(_enum(AttachmentType), nullable=False)
    storage_path = db.Column(db.String(600), nullable=False)
    mime_type = db.Column(db.String(120), nullable=True)
    size_bytes = db.Column(db.Integer, nullable=True)
    # STT transcript (audio) / vision description (image) produced by AI layer.
    extracted_text = db.Column(db.Text, nullable=True)
    image_description = db.Column(db.Text, nullable=True)

    message = db.relationship("Message", back_populates="attachments")

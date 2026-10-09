"""AI + knowledge-base entities: KB items/chunks, AI runs, settings, prompt versions."""
from __future__ import annotations

from sqlalchemy.orm import Mapped, relationship

from app.extensions import db
from app.models.base import TimestampMixin
from app.models.enums import EscalationReason


def _enum(e, length=32):
    return db.Enum(e, native_enum=False, length=length, validate_strings=True)


class KBItem(TimestampMixin, db.Model):
    """A knowledge-base entry (product, FAQ, policy, ...)."""
    __tablename__ = "kb_items"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    content = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(80), nullable=True, index=True)
    source_type = db.Column(db.String(40), nullable=True)  # text | pdf | docx | xlsx | csv
    source_path = db.Column(db.String(600), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    chunks: Mapped[list["KBChunk"]] = relationship(
        "KBChunk", back_populates="item", cascade="all, delete-orphan"
    )


class KBChunk(TimestampMixin, db.Model):
    """A chunk of a KB item with its embedding, for semantic retrieval.

    The embedding is stored as JSON for Phase 0. When pgvector is added, this
    becomes a vector column; the retrieval interface stays the same.
    """
    __tablename__ = "kb_chunks"

    id = db.Column(db.BigInteger, primary_key=True)
    item_id = db.Column(
        db.Integer, db.ForeignKey("kb_items.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    seq = db.Column(db.Integer, nullable=False, default=0)
    content = db.Column(db.Text, nullable=False)
    embedding = db.Column(db.JSON, nullable=True)

    item = db.relationship("KBItem", back_populates="chunks")


class AISettings(TimestampMixin, db.Model):
    """Global AI configuration + the live kill switch (spec §6.4)."""
    __tablename__ = "ai_settings"

    id = db.Column(db.Integer, primary_key=True)
    # Global kill switch — when False, no automatic replies anywhere.
    ai_enabled = db.Column(db.Boolean, nullable=False, default=True)
    confidence_threshold = db.Column(db.Float, nullable=False, default=0.6)
    max_consecutive_replies = db.Column(db.Integer, nullable=False, default=3)
    daily_request_cap = db.Column(db.Integer, nullable=True)
    send_delay_seconds = db.Column(db.Integer, nullable=False, default=0)
    active_prompt_version_id = db.Column(
        db.Integer, db.ForeignKey("prompt_versions.id"), nullable=True
    )

    # Provider config (provider-agnostic interface, spec §6; default: DeepSeek).
    provider = db.Column(db.String(40), nullable=False, default="deepseek")
    model = db.Column(db.String(80), nullable=False, default="deepseek-chat")
    base_url = db.Column(db.String(200), nullable=False, default="https://api.deepseek.com")
    api_key_enc = db.Column(db.Text, nullable=True)  # Fernet-encrypted

    active_prompt = db.relationship("PromptVersion", foreign_keys=[active_prompt_version_id])

    def set_api_key(self, raw: str | None) -> None:
        from app.security.crypto import encrypt_str
        self.api_key_enc = encrypt_str(raw) if raw else None

    def get_api_key(self) -> str | None:
        from app.security.crypto import decrypt_str
        return decrypt_str(self.api_key_enc) if self.api_key_enc else None

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key_enc)


class PromptVersion(TimestampMixin, db.Model):
    """A versioned system prompt / persona (spec §6.4 AI-5)."""
    __tablename__ = "prompt_versions"

    id = db.Column(db.Integer, primary_key=True)
    version = db.Column(db.Integer, nullable=False, default=1)
    system_prompt = db.Column(db.Text, nullable=False)
    tone = db.Column(db.String(120), nullable=True)
    notes = db.Column(db.String(300), nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)


class AIRun(TimestampMixin, db.Model):
    """One automatic-reply attempt, fully logged for review (spec §6.5)."""
    __tablename__ = "ai_runs"

    id = db.Column(db.BigInteger, primary_key=True)
    conversation_id = db.Column(
        db.Integer, db.ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    message_id = db.Column(db.BigInteger, db.ForeignKey("messages.id"), nullable=True)

    input_context = db.Column(db.JSON, nullable=True)   # messages fed to the model
    used_chunk_ids = db.Column(db.JSON, nullable=True)  # KB chunks retrieved
    output_text = db.Column(db.Text, nullable=True)
    confidence = db.Column(db.Float, nullable=True)

    escalated = db.Column(db.Boolean, nullable=False, default=False)
    escalation_reason = db.Column(_enum(EscalationReason), nullable=True)

    latency_ms = db.Column(db.Integer, nullable=True)
    cost_usd = db.Column(db.Numeric(10, 5), nullable=True)
    rating = db.Column(db.Boolean, nullable=True)  # reviewer feedback: good/bad


class Order(TimestampMixin, db.Model):
    """A delivery order the AI confirmed in a conversation (ticket: order flow)."""
    __tablename__ = "orders"

    id = db.Column(db.BigInteger, primary_key=True)
    conversation_id = db.Column(
        db.Integer, db.ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    contact_id = db.Column(db.Integer, db.ForeignKey("contacts.id"), nullable=True, index=True)

    status = db.Column(db.String(24), nullable=False, default="confirmed")
    stops = db.Column(db.JSON, nullable=True)            # [{shop, items:[...]}]
    delivery_landmark = db.Column(db.Text, nullable=True)
    phones = db.Column(db.JSON, nullable=True)           # ["01..."]
    payment_method = db.Column(db.String(60), nullable=True)
    invoice_required = db.Column(db.Boolean, nullable=False, default=False)
    raw = db.Column(db.JSON, nullable=True)              # the model's full order object

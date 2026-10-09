"""Organisation-wide operational settings (singleton): automation, hours, texts."""
from __future__ import annotations

from app.extensions import db
from app.models.base import TimestampMixin

DEFAULT_WELCOME = "أهلاً بحضرتك في خدمة التوصيل 👋 اكتب طلبك أو استفسارك وهنساعدك فورًا."
DEFAULT_OUT_OF_HOURS = (
    "شكرًا لتواصلك 🙏 إحنا دلوقتي خارج ساعات العمل، وهنرد على حضرتك أول ما نفتح."
)
DEFAULT_HANDOFF = "تمام، هحوّلك لموظف من فريقنا هيساعدك حالًا 🙏"


class OrgSettings(TimestampMixin, db.Model):
    """Single row (id=1) holding org-level behaviour (spec §5.4, §5.7, §6.3)."""
    __tablename__ = "org_settings"

    id = db.Column(db.Integer, primary_key=True)

    # Welcome / greeting on first message (AU-3).
    welcome_enabled = db.Column(db.Boolean, nullable=False, default=True)
    welcome_text = db.Column(db.Text, nullable=False, default=DEFAULT_WELCOME)

    # Business hours (AU-2). schedule: {"mon":["09:00","17:00"], ...}; off days omitted.
    timezone = db.Column(db.String(64), nullable=False, default="Africa/Cairo")
    business_hours = db.Column(db.JSON, nullable=True)
    out_of_hours_enabled = db.Column(db.Boolean, nullable=False, default=False)
    out_of_hours_text = db.Column(db.Text, nullable=False, default=DEFAULT_OUT_OF_HOURS)

    # Auto-assignment (AU-1).
    auto_assign_enabled = db.Column(db.Boolean, nullable=False, default=False)
    auto_assign_strategy = db.Column(db.String(20), nullable=False, default="round_robin")

    # SLA alert + idle auto-close (AU-4, AU-5), in minutes; null disables.
    sla_minutes = db.Column(db.Integer, nullable=True)
    auto_close_minutes = db.Column(db.Integer, nullable=True)

    # Retention policy (AD-6), in days; null keeps forever.
    retention_days = db.Column(db.Integer, nullable=True)

    # Customer-facing handoff text on escalation (§6.3).
    handoff_text = db.Column(db.Text, nullable=False, default=DEFAULT_HANDOFF)

    # Optional: Telegram chat id of a staff group to post confirmed-order summaries to.
    order_notify_telegram_chat_id = db.Column(db.String(64), nullable=True)

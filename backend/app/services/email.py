"""Best-effort email alerts (spec §5.5 NT-3). Disabled when SMTP is unconfigured."""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from flask import current_app

log = logging.getLogger(__name__)


def is_configured() -> bool:
    return bool(current_app.config.get("SMTP_HOST"))


def send_email(to: str | list[str], subject: str, body: str) -> bool:
    """Send a plain-text email. Returns True on success, False otherwise."""
    cfg = current_app.config
    if not cfg.get("SMTP_HOST"):
        return False
    recipients = [to] if isinstance(to, str) else list(to)
    recipients = [r for r in recipients if r]
    if not recipients:
        return False

    msg = EmailMessage()
    msg["From"] = cfg["MAIL_FROM"]
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        with smtplib.SMTP(cfg["SMTP_HOST"], cfg["SMTP_PORT"], timeout=15) as smtp:
            if cfg.get("SMTP_USE_TLS"):
                smtp.starttls()
            if cfg.get("SMTP_USERNAME"):
                smtp.login(cfg["SMTP_USERNAME"], cfg["SMTP_PASSWORD"])
            smtp.send_message(msg)
        return True
    except Exception as exc:  # noqa: BLE001 — email is best-effort, never fatal
        log.warning("email send failed: %s", exc)
        return False

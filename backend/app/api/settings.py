"""Admin settings: AI provider config + channel setup (token, link, commands, webhook)."""
from __future__ import annotations

import secrets

from flask import Blueprint, current_app, jsonify, request
from flask_login import login_required

from app.channels.registry import get_adapter
from app.extensions import db
from app.models.ai import AISettings, PromptVersion
from app.models.core import Channel
from app.models.enums import ChannelStatus, ChannelType, NotificationType
from app.security.permissions import Permission, require_permission
from app.services import audit, notify

bp = Blueprint("settings", __name__, url_prefix="/api/settings")


# ============================= AI settings =============================

def _ai_json(s: AISettings) -> dict:
    return {
        "provider": s.provider,
        "model": s.model,
        "base_url": s.base_url,
        "has_api_key": s.has_api_key,          # key itself is never returned
        "ai_enabled": s.ai_enabled,            # global kill switch
        "confidence_threshold": s.confidence_threshold,
        "max_consecutive_replies": s.max_consecutive_replies,
        "daily_request_cap": s.daily_request_cap,
        "send_delay_seconds": s.send_delay_seconds,
    }


@bp.get("/ai")
@login_required
@require_permission(Permission.AI_SETTINGS)
def get_ai_settings():
    s = db.session.get(AISettings, 1)
    if s is None:
        return jsonify(error="ai_settings_not_initialised"), 404
    return jsonify(settings=_ai_json(s))


@bp.get("/ai/kill-switch")
@login_required
@require_permission(Permission.AI_KILL_SWITCH)
def get_kill_switch():
    """Read the global AI on/off state (admins + supervisors, spec §3)."""
    s = db.session.get(AISettings, 1)
    if s is None:
        return jsonify(error="ai_settings_not_initialised"), 404
    return jsonify(ai_enabled=s.ai_enabled)


@bp.post("/ai/kill-switch")
@login_required
@require_permission(Permission.AI_KILL_SWITCH)
def set_kill_switch():
    """Flip the global AI kill switch (admins + supervisors, spec §6.4 AI-1)."""
    s = db.session.get(AISettings, 1)
    if s is None:
        return jsonify(error="ai_settings_not_initialised"), 404
    enabled = bool((request.get_json(silent=True) or {}).get("enabled"))
    s.ai_enabled = enabled
    audit.record("ai.kill_switch", entity_type="ai_settings", entity_id=1,
                 after={"ai_enabled": enabled})
    db.session.commit()
    return jsonify(ai_enabled=s.ai_enabled)


@bp.put("/ai")
@login_required
@require_permission(Permission.AI_SETTINGS)
def update_ai_settings():
    s = db.session.get(AISettings, 1)
    if s is None:
        return jsonify(error="ai_settings_not_initialised"), 404
    data = request.get_json(silent=True) or {}

    for field in ("provider", "model", "base_url"):
        if field in data and data[field] is not None:
            setattr(s, field, str(data[field]).strip())
    if "ai_enabled" in data:
        s.ai_enabled = bool(data["ai_enabled"])
    if "confidence_threshold" in data:
        s.confidence_threshold = float(data["confidence_threshold"])
    if "max_consecutive_replies" in data:
        s.max_consecutive_replies = int(data["max_consecutive_replies"])
    if "send_delay_seconds" in data:
        s.send_delay_seconds = int(data["send_delay_seconds"])
    if "daily_request_cap" in data:
        s.daily_request_cap = data["daily_request_cap"]

    # API key is write-only; empty string leaves it unchanged, null clears it.
    if "api_key" in data:
        key = data["api_key"]
        if key is None:
            s.set_api_key(None)
        elif str(key).strip():
            s.set_api_key(str(key).strip())

    audit.record("ai_settings.update", entity_type="ai_settings", entity_id=1,
                 after={"provider": s.provider, "model": s.model,
                        "ai_enabled": s.ai_enabled})
    db.session.commit()
    return jsonify(settings=_ai_json(s))


# ============================= Prompts =============================

def _prompt_json(p: PromptVersion, active_id: int | None) -> dict:
    return {
        "id": p.id,
        "version": p.version,
        "tone": p.tone,
        "notes": p.notes,
        "system_prompt": p.system_prompt,
        "is_active": p.id == active_id,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


@bp.get("/prompts")
@login_required
@require_permission(Permission.AI_SETTINGS)
def list_prompts():
    s = db.session.get(AISettings, 1)
    active_id = s.active_prompt_version_id if s else None
    rows = db.session.scalars(
        db.select(PromptVersion).order_by(PromptVersion.version.desc())
    ).all()
    return jsonify(active_id=active_id, prompts=[_prompt_json(p, active_id) for p in rows])


@bp.post("/prompts")
@login_required
@require_permission(Permission.AI_SETTINGS)
def create_prompt():
    data = request.get_json(silent=True) or {}
    body = (data.get("system_prompt") or "").strip()
    if not body:
        return jsonify(error="system_prompt_required"), 400
    top = db.session.scalar(db.select(db.func.max(PromptVersion.version))) or 0
    pv = PromptVersion(
        version=top + 1, system_prompt=body,
        tone=(data.get("tone") or None), notes=(data.get("notes") or None),
    )
    db.session.add(pv)
    db.session.flush()
    if data.get("activate"):
        s = db.session.get(AISettings, 1)
        if s:
            s.active_prompt_version_id = pv.id
    audit.record("ai_prompt.create", entity_type="prompt_version", entity_id=pv.id)
    db.session.commit()
    s = db.session.get(AISettings, 1)
    return jsonify(prompt=_prompt_json(pv, s.active_prompt_version_id if s else None)), 201


@bp.post("/prompts/<int:prompt_id>/activate")
@login_required
@require_permission(Permission.AI_SETTINGS)
def activate_prompt(prompt_id: int):
    pv = db.session.get(PromptVersion, prompt_id)
    if pv is None:
        return jsonify(error="not_found"), 404
    s = db.session.get(AISettings, 1)
    if s is None:
        return jsonify(error="ai_settings_not_initialised"), 404
    s.active_prompt_version_id = pv.id
    audit.record("ai_prompt.activate", entity_type="prompt_version", entity_id=pv.id)
    db.session.commit()
    return jsonify(ok=True, active_id=pv.id)


# ============================== Channels ==============================

def _channel_json(c: Channel) -> dict:
    cfg = c.config or {}
    return {
        "id": c.id,
        "type": getattr(c.type, "value", c.type),
        "name": c.name,
        "status": getattr(c.status, "value", c.status),
        "has_credentials": bool(c.credentials_enc),
        "account_id": c.external_ref,          # bot id / page id / ig id
        "bot_link": cfg.get("link"),           # telegram
        "bot_username": cfg.get("username"),   # telegram
        "page_name": cfg.get("page_name"),     # meta
        "webhook_url": cfg.get("webhook_url"),
        "commands": cfg.get("commands", []),
        "last_error": c.last_error,
    }


def _webhook_url(channel: Channel) -> str:
    base = (current_app.config.get("PUBLIC_BASE_URL") or "").rstrip("/")
    if not base:
        raise RuntimeError("PUBLIC_BASE_URL is not set — cannot register a webhook")
    return f"{base}/api/webhooks/telegram/{channel.id}"


# Required credential fields per channel type (checked before connecting).
_REQUIRED_CREDENTIALS = {
    ChannelType.TELEGRAM: ["bot_token"],
    ChannelType.MESSENGER: ["page_access_token", "page_id"],
    ChannelType.INSTAGRAM: ["page_access_token", "page_id", "ig_id"],
}


def _missing_credentials(channel: Channel) -> list[str]:
    creds = channel.get_credentials()
    required = _REQUIRED_CREDENTIALS.get(channel.type, [])
    return [f for f in required if not creds.get(f)]


@bp.get("/channels")
@login_required
@require_permission(Permission.MANAGE_CHANNELS)
def list_channels():
    channels = db.session.scalars(db.select(Channel).order_by(Channel.id)).all()
    return jsonify(channels=[_channel_json(c) for c in channels])


@bp.post("/channels")
@login_required
@require_permission(Permission.MANAGE_CHANNELS)
def create_channel():
    data = request.get_json(silent=True) or {}
    try:
        ctype = ChannelType(data.get("type", ""))
    except ValueError:
        return jsonify(error="invalid_channel_type"), 400
    channel = Channel(
        type=ctype,
        name=(data.get("name") or ctype.value).strip(),
        status=ChannelStatus.DISCONNECTED,
    )
    db.session.add(channel)
    db.session.commit()
    return jsonify(channel=_channel_json(channel)), 201


@bp.get("/channels/<int:channel_id>")
@login_required
@require_permission(Permission.MANAGE_CHANNELS)
def get_channel(channel_id: int):
    channel = db.session.get(Channel, channel_id)
    if channel is None:
        return jsonify(error="not_found"), 404
    return jsonify(channel=_channel_json(channel))


@bp.put("/channels/<int:channel_id>")
@login_required
@require_permission(Permission.MANAGE_CHANNELS)
def update_channel(channel_id: int):
    channel = db.session.get(Channel, channel_id)
    if channel is None:
        return jsonify(error="not_found"), 404
    data = request.get_json(silent=True) or {}

    if "name" in data and data["name"]:
        channel.name = str(data["name"]).strip()

    # Secrets/ids (merged into encrypted credentials):
    #   telegram  -> bot_token
    #   messenger -> page_access_token, page_id
    #   instagram -> page_access_token, ig_id
    cred_updates = {}
    for field in ("bot_token", "page_access_token", "page_id", "ig_id"):
        if data.get(field):
            cred_updates[field] = str(data[field]).strip()
    if cred_updates:
        creds = channel.get_credentials()
        creds.update(cred_updates)
        channel.set_credentials(creds)

    # Bot commands (non-secret) — stored in config; pushed to Telegram on connect.
    if "commands" in data and isinstance(data["commands"], list):
        cfg = dict(channel.config or {})
        cfg["commands"] = [
            {"command": str(c.get("command", "")).lstrip("/").strip(),
             "description": str(c.get("description", "")).strip()}
            for c in data["commands"] if c.get("command")
        ]
        channel.config = cfg

    db.session.commit()
    return jsonify(channel=_channel_json(channel))


@bp.post("/channels/<int:channel_id>/test")
@login_required
@require_permission(Permission.MANAGE_CHANNELS)
def test_channel(channel_id: int):
    channel = db.session.get(Channel, channel_id)
    if channel is None:
        return jsonify(error="not_found"), 404
    try:
        info = get_adapter(channel).test_connection()
    except Exception as exc:  # noqa: BLE001
        return jsonify(ok=False, error=str(exc)), 400
    return jsonify(ok=True, info=info)


@bp.post("/channels/<int:channel_id>/connect")
@login_required
@require_permission(Permission.MANAGE_CHANNELS)
def connect_channel(channel_id: int):
    channel = db.session.get(Channel, channel_id)
    if channel is None:
        return jsonify(error="not_found"), 404

    # Validate required credentials up front so we fail with a clear message.
    missing = _missing_credentials(channel)
    if missing:
        return jsonify(error="missing_credentials", fields=missing), 400

    adapter = get_adapter(channel)
    cfg = dict(channel.config or {})
    try:
        # 1) verify credentials + fetch account identity
        info = adapter.test_connection()
        channel.external_ref = str(info.get("id") or "")

        if channel.type == ChannelType.TELEGRAM:
            # Telegram: self-hosted webhook with a secret token + bot commands.
            creds = channel.get_credentials()
            if not creds.get("webhook_secret"):
                creds["webhook_secret"] = secrets.token_urlsafe(32)
                channel.set_credentials(creds)
            url = _webhook_url(channel)
            adapter.set_webhook(url, creds["webhook_secret"])
            if cfg.get("commands"):
                adapter.set_commands(cfg["commands"])
            cfg.update({"webhook_url": url, "username": info.get("username"),
                        "link": info.get("link")})
        else:
            # Meta: the app's callback URL is set once in the dashboard; here we
            # subscribe the Page to the app so its events flow. external_ref holds
            # the routing id (page id for Messenger, IG account id for Instagram).
            adapter.set_webhook("", "")  # subscribe page (url/secret unused)
            cfg.update({"page_name": info.get("name")})
    except Exception as exc:  # noqa: BLE001
        channel.status = ChannelStatus.ERROR
        channel.last_error = str(exc)
        db.session.commit()
        notify.alert_admins(
            NotificationType.CHANNEL_DOWN, "easyGo: تعذّر ربط قناة",
            f"فشل ربط القناة «{channel.name}»: {exc}",
        )
        return jsonify(ok=False, error=str(exc)), 400

    channel.config = cfg
    channel.status = ChannelStatus.CONNECTED
    channel.last_error = None
    audit.record("channel.connect", entity_type="channel", entity_id=channel.id,
                 after={"type": getattr(channel.type, "value", channel.type)})
    db.session.commit()
    return jsonify(ok=True, channel=_channel_json(channel))


@bp.post("/channels/<int:channel_id>/disconnect")
@login_required
@require_permission(Permission.MANAGE_CHANNELS)
def disconnect_channel(channel_id: int):
    channel = db.session.get(Channel, channel_id)
    if channel is None:
        return jsonify(error="not_found"), 404
    try:
        get_adapter(channel).delete_webhook()
    except Exception as exc:  # noqa: BLE001 — still mark disconnected locally
        channel.last_error = str(exc)
    channel.status = ChannelStatus.DISCONNECTED
    db.session.commit()
    return jsonify(ok=True, channel=_channel_json(channel))

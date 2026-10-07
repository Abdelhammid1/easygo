"""Org-level settings: automation, business hours, retention, texts (spec §5.4, §5.7)."""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import login_required

from app.extensions import db
from app.models.org import OrgSettings
from app.security.permissions import Permission, require_permission
from app.services import audit

bp = Blueprint("org_settings", __name__, url_prefix="/api/settings/org")

_STR_FIELDS = ("welcome_text", "out_of_hours_text", "handoff_text",
               "timezone", "auto_assign_strategy")
_BOOL_FIELDS = ("welcome_enabled", "out_of_hours_enabled", "auto_assign_enabled")
_INT_FIELDS = ("sla_minutes", "auto_close_minutes", "retention_days")


def _json(s: OrgSettings) -> dict:
    return {
        "welcome_enabled": s.welcome_enabled,
        "welcome_text": s.welcome_text,
        "timezone": s.timezone,
        "business_hours": s.business_hours or {},
        "out_of_hours_enabled": s.out_of_hours_enabled,
        "out_of_hours_text": s.out_of_hours_text,
        "auto_assign_enabled": s.auto_assign_enabled,
        "auto_assign_strategy": s.auto_assign_strategy,
        "sla_minutes": s.sla_minutes,
        "auto_close_minutes": s.auto_close_minutes,
        "retention_days": s.retention_days,
        "handoff_text": s.handoff_text,
    }


@bp.get("")
@login_required
@require_permission(Permission.MANAGE_ORG_SETTINGS)
def get_org_settings():
    s = db.session.get(OrgSettings, 1)
    if s is None:
        return jsonify(error="org_settings_not_initialised"), 404
    return jsonify(settings=_json(s))


@bp.put("")
@login_required
@require_permission(Permission.MANAGE_ORG_SETTINGS)
def update_org_settings():
    s = db.session.get(OrgSettings, 1)
    if s is None:
        return jsonify(error="org_settings_not_initialised"), 404
    data = request.get_json(silent=True) or {}

    for field in _STR_FIELDS:
        if field in data and data[field] is not None:
            setattr(s, field, str(data[field]).strip())
    for field in _BOOL_FIELDS:
        if field in data:
            setattr(s, field, bool(data[field]))
    for field in _INT_FIELDS:
        if field in data:
            value = data[field]
            setattr(s, field, int(value) if value not in (None, "") else None)
    if "business_hours" in data and isinstance(data["business_hours"], dict):
        s.business_hours = data["business_hours"]

    audit.record("org_settings.update", entity_type="org_settings", entity_id=1)
    db.session.commit()
    return jsonify(settings=_json(s))

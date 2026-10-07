"""Audit log viewer (spec §5.7 AD-5)."""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import login_required

from app.extensions import db
from app.models.support import AuditLog
from app.security.permissions import Permission, require_permission

bp = Blueprint("audit", __name__, url_prefix="/api/audit")


@bp.get("")
@login_required
@require_permission(Permission.VIEW_AUDIT_LOG)
def list_audit():
    limit = min(int(request.args.get("limit", 100)), 500)
    action = request.args.get("action")
    query = db.select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
    if action:
        query = db.select(AuditLog).where(AuditLog.action == action)\
            .order_by(AuditLog.id.desc()).limit(limit)
    rows = db.session.scalars(query).all()
    return jsonify(entries=[
        {
            "id": a.id,
            "user_id": a.user_id,
            "action": a.action,
            "entity_type": a.entity_type,
            "entity_id": a.entity_id,
            "before": a.before,
            "after": a.after,
            "at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in rows
    ])

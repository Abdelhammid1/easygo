"""Tags and canned responses (spec §5.7 AD-3, IN-8, IN-10)."""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import login_required
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.support import CannedResponse, Tag
from app.security.permissions import Permission, require_permission

bp = Blueprint("catalog", __name__, url_prefix="/api/catalog")


# ----------------------------- tags -----------------------------

@bp.get("/tags")
@login_required
@require_permission(Permission.VIEW_CONVERSATIONS)
def list_tags():
    rows = db.session.scalars(db.select(Tag).order_by(Tag.name)).all()
    return jsonify(tags=[{"id": t.id, "name": t.name, "color": t.color} for t in rows])


@bp.post("/tags")
@login_required
@require_permission(Permission.MANAGE_KB)  # supervisors/admins manage catalog
def create_tag():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify(error="name_required"), 400
    tag = Tag(name=name, color=data.get("color"))
    db.session.add(tag)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(error="tag_exists"), 409
    return jsonify(tag={"id": tag.id, "name": tag.name, "color": tag.color}), 201


@bp.delete("/tags/<int:tag_id>")
@login_required
@require_permission(Permission.MANAGE_KB)
def delete_tag(tag_id: int):
    tag = db.session.get(Tag, tag_id)
    if tag is None:
        return jsonify(error="not_found"), 404
    db.session.delete(tag)
    db.session.commit()
    return jsonify(ok=True)


# ------------------------ canned responses ------------------------

@bp.get("/canned")
@login_required
@require_permission(Permission.VIEW_CONVERSATIONS)
def list_canned():
    rows = db.session.scalars(db.select(CannedResponse).order_by(CannedResponse.shortcut)).all()
    return jsonify(canned=[{"id": c.id, "shortcut": c.shortcut, "body": c.body} for c in rows])


@bp.post("/canned")
@login_required
@require_permission(Permission.MANAGE_KB)
def create_canned():
    data = request.get_json(silent=True) or {}
    shortcut = (data.get("shortcut") or "").strip()
    body = (data.get("body") or "").strip()
    if not shortcut or not body:
        return jsonify(error="shortcut_and_body_required"), 400
    canned = CannedResponse(shortcut=shortcut, body=body)
    db.session.add(canned)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(error="shortcut_exists"), 409
    return jsonify(canned={"id": canned.id, "shortcut": canned.shortcut, "body": canned.body}), 201


@bp.put("/canned/<int:canned_id>")
@login_required
@require_permission(Permission.MANAGE_KB)
def update_canned(canned_id: int):
    canned = db.session.get(CannedResponse, canned_id)
    if canned is None:
        return jsonify(error="not_found"), 404
    data = request.get_json(silent=True) or {}
    if data.get("shortcut"):
        canned.shortcut = data["shortcut"].strip()
    if data.get("body"):
        canned.body = data["body"].strip()
    db.session.commit()
    return jsonify(canned={"id": canned.id, "shortcut": canned.shortcut, "body": canned.body})


@bp.delete("/canned/<int:canned_id>")
@login_required
@require_permission(Permission.MANAGE_KB)
def delete_canned(canned_id: int):
    canned = db.session.get(CannedResponse, canned_id)
    if canned is None:
        return jsonify(error="not_found"), 404
    db.session.delete(canned)
    db.session.commit()
    return jsonify(ok=True)

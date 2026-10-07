"""User & role management (spec §3, §5.7 AD-1). Admin only."""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.extensions import db
from app.models.core import User
from app.models.enums import UserRole, UserStatus
from app.security.permissions import Permission, require_permission
from app.services import audit

bp = Blueprint("users", __name__, url_prefix="/api/users")


def _user_json(u: User) -> dict:
    return {
        "id": u.id,
        "name": u.name,
        "email": u.email,
        "role": getattr(u.role, "value", u.role),
        "status": getattr(u.status, "value", u.status),
        "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
    }


@bp.get("")
@login_required
@require_permission(Permission.MANAGE_USERS)
def list_users():
    rows = db.session.scalars(db.select(User).order_by(User.id)).all()
    return jsonify(users=[_user_json(u) for u in rows])


@bp.post("")
@login_required
@require_permission(Permission.MANAGE_USERS)
def create_user():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    name = (data.get("name") or "").strip()
    password = data.get("password") or ""
    if not email or not name or len(password) < 8:
        return jsonify(error="name_email_and_password(>=8)_required"), 400
    try:
        role = UserRole(data.get("role", "agent"))
    except ValueError:
        return jsonify(error="invalid_role"), 400
    if db.session.scalar(db.select(User).filter_by(email=email)):
        return jsonify(error="email_exists"), 409

    user = User(name=name, email=email, role=role, status=UserStatus.ACTIVE)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    audit.record("user.create", entity_type="user", entity_id=user.id,
                 after={"email": email, "role": role.value})
    db.session.commit()
    return jsonify(user=_user_json(user)), 201


@bp.put("/<int:user_id>")
@login_required
@require_permission(Permission.MANAGE_USERS)
def update_user(user_id: int):
    user = db.session.get(User, user_id)
    if user is None:
        return jsonify(error="not_found"), 404
    data = request.get_json(silent=True) or {}

    if data.get("name"):
        user.name = str(data["name"]).strip()
    if data.get("password"):
        if len(data["password"]) < 8:
            return jsonify(error="password_too_short"), 400
        user.set_password(data["password"])
    if "role" in data:
        try:
            new_role = UserRole(data["role"])
        except ValueError:
            return jsonify(error="invalid_role"), 400
        if _would_remove_last_admin(user, new_role=new_role):
            return jsonify(error="cannot_demote_last_admin"), 409
        user.role = new_role
    if "status" in data:
        try:
            new_status = UserStatus(data["status"])
        except ValueError:
            return jsonify(error="invalid_status"), 400
        if user.id == current_user.id and new_status == UserStatus.DISABLED:
            return jsonify(error="cannot_disable_self"), 409
        if new_status == UserStatus.DISABLED and _would_remove_last_admin(user):
            return jsonify(error="cannot_disable_last_admin"), 409
        user.status = new_status

    audit.record("user.update", entity_type="user", entity_id=user.id)
    db.session.commit()
    return jsonify(user=_user_json(user))


def _would_remove_last_admin(user: User, new_role: UserRole | None = None) -> bool:
    """True if changing this user would leave zero active admins."""
    is_admin = user.role == UserRole.ADMIN
    if not is_admin:
        return False
    if new_role is not None and new_role == UserRole.ADMIN:
        return False
    active_admins = db.session.scalar(
        db.select(db.func.count(User.id)).where(
            User.role == UserRole.ADMIN, User.status == UserStatus.ACTIVE
        )
    )
    return (active_admins or 0) <= 1

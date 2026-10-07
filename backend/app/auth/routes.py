"""Session-based authentication endpoints."""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required, login_user, logout_user

from app.extensions import db
from app.models.base import utcnow
from app.models.core import User
from app.security import csrf
from app.security.permissions import ROLE_PERMISSIONS

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _user_json(user: User) -> dict:
    role_value = user.role.value if hasattr(user.role, "value") else user.role
    perms = sorted(p.value for p in ROLE_PERMISSIONS.get(str(role_value), set()))
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": role_value,
        "permissions": perms,
    }


@bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    if not email or not password:
        return jsonify(error="email_and_password_required"), 400

    user = db.session.scalar(db.select(User).filter_by(email=email))
    if user is None or not user.check_password(password):
        return jsonify(error="invalid_credentials"), 401
    if not user.is_active:
        return jsonify(error="account_disabled"), 403

    login_user(user)
    user.last_login_at = utcnow()
    db.session.commit()
    # Fresh CSRF token for this session; client echoes it in X-CSRF-Token.
    return jsonify(user=_user_json(user), csrf_token=csrf.rotate_token())


@bp.post("/logout")
@login_required
def logout():
    logout_user()
    return jsonify(ok=True)


@bp.get("/me")
@login_required
def me():
    return jsonify(
        user=_user_json(current_user),  # type: ignore[arg-type]
        csrf_token=csrf.get_or_create_token(),
    )

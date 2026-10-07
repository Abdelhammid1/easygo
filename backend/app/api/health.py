"""Health / readiness endpoint."""
from __future__ import annotations

from flask import Blueprint, jsonify

from app import extensions
from app.extensions import db

bp = Blueprint("health", __name__, url_prefix="/api")


@bp.get("/health")
def health():
    checks = {"db": False, "redis": False}
    try:
        db.session.execute(db.text("SELECT 1"))
        checks["db"] = True
    except Exception:
        pass
    try:
        if extensions.redis_client is not None:
            extensions.redis_client.ping()
            checks["redis"] = True
    except Exception:
        pass

    ok = all(checks.values())
    return jsonify(status="ok" if ok else "degraded", checks=checks), (200 if ok else 503)

"""Application factory."""
from __future__ import annotations

import redis as redis_lib
from flask import Flask, jsonify, request

from app import extensions
from app.config import get_config
from app.extensions import bcrypt, db, login_manager, migrate, socketio


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(get_config(config_name))

    _init_extensions(app)
    _register_login(app)
    _register_csrf(app)
    _register_blueprints(app)
    _register_cli(app)
    _register_error_handlers(app)

    return app


def _init_extensions(app: Flask) -> None:
    db.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    socketio.init_app(app, message_queue=app.config["REDIS_URL"])
    extensions.redis_client = redis_lib.from_url(app.config["REDIS_URL"])

    # Import models so they register with SQLAlchemy / Flask-Migrate.
    from app import models  # noqa: F401
    # Register realtime event handlers.
    from app import realtime  # noqa: F401


def _register_login(app: Flask) -> None:
    from app.models.core import User

    @login_manager.user_loader
    def load_user(user_id: str):
        return db.session.get(User, int(user_id))

    @login_manager.unauthorized_handler
    def unauthorized():
        return jsonify(error="unauthorized"), 401


def _register_csrf(app: Flask) -> None:
    from app.security import csrf

    @app.before_request
    def _csrf_guard():
        if csrf.is_exempt(request.path, request.method):
            return None
        if not csrf.validate():
            return jsonify(error="csrf_failed"), 403
        return None


def _register_blueprints(app: Flask) -> None:
    from app.api.audit import bp as audit_bp
    from app.api.automation import bp as org_settings_bp
    from app.api.catalog import bp as catalog_bp
    from app.api.contacts import bp as contacts_bp
    from app.api.conversations import bp as conversations_bp
    from app.api.health import bp as health_bp
    from app.api.knowledge import bp as knowledge_bp
    from app.api.media import bp as media_bp
    from app.api.notifications import bp as notifications_bp
    from app.api.reports import bp as reports_bp
    from app.api.settings import bp as settings_bp
    from app.api.users import bp as users_bp
    from app.api.webhooks import bp as webhooks_bp
    from app.auth.routes import bp as auth_bp

    for blueprint in (
        health_bp, auth_bp, settings_bp, webhooks_bp, conversations_bp,
        users_bp, contacts_bp, knowledge_bp, catalog_bp, notifications_bp,
        reports_bp, media_bp, org_settings_bp, audit_bp,
    ):
        app.register_blueprint(blueprint)


def _register_cli(app: Flask) -> None:
    from app.cli import register_cli

    register_cli(app)


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(404)
    def not_found(_e):
        return jsonify(error="not_found"), 404

    @app.errorhandler(500)
    def server_error(_e):
        return jsonify(error="server_error"), 500

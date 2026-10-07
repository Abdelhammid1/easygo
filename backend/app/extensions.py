"""Shared extension instances, initialised in the app factory."""
from __future__ import annotations

from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
bcrypt = Bcrypt()

# async_mode="threading" keeps the dev/scaffold stack simple (works under
# gunicorn gthread). Revisit (eventlet/gevent) when load-testing realtime.
socketio = SocketIO(cors_allowed_origins="*", async_mode="threading")

# Assigned in create_app() from REDIS_URL.
redis_client = None

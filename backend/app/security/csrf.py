"""CSRF protection (synchronizer-token pattern) for cookie-authenticated routes.

The token lives in the server-side session. Clients read it from the login /
`/me` response and echo it back in the `X-CSRF-Token` header on unsafe requests.
SameSite=Lax already blocks most cross-site POSTs; this closes the gap.
"""
from __future__ import annotations

import secrets

from flask import request, session

SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}

# Prefixes that authenticate by other means (not the session cookie).
EXEMPT_PREFIXES = ("/api/webhooks/", "/socket.io/")
# Endpoints that must work before a token exists.
EXEMPT_PATHS = {"/api/auth/login"}

_SESSION_KEY = "csrf_token"


def get_or_create_token() -> str:
    token = session.get(_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[_SESSION_KEY] = token
    return token


def rotate_token() -> str:
    session[_SESSION_KEY] = secrets.token_urlsafe(32)
    return session[_SESSION_KEY]


def is_exempt(path: str, method: str) -> bool:
    if method in SAFE_METHODS:
        return True
    if path in EXEMPT_PATHS:
        return True
    return any(path.startswith(p) for p in EXEMPT_PREFIXES)


def validate() -> bool:
    expected = session.get(_SESSION_KEY)
    provided = request.headers.get("X-CSRF-Token", "")
    return bool(expected) and secrets.compare_digest(expected, provided)

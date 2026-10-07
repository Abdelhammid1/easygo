"""Symmetric encryption for secrets at rest (channel tokens/credentials).

Secrets are never stored in plaintext in the DB (spec §4.1). A Fernet key is
read from FERNET_KEY. In dev, if it is missing we derive one deterministically
from SECRET_KEY so the app still boots and secrets remain readable across
restarts — but this ties secret confidentiality to SECRET_KEY and prevents key
rotation, so a dedicated FERNET_KEY must be set in production.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app

log = logging.getLogger(__name__)


def _get_fernet() -> Fernet:
    key = current_app.config.get("FERNET_KEY") or ""
    if not key:
        log.warning(
            "FERNET_KEY not set — deriving a dev key from SECRET_KEY. Secrets stay "
            "readable while SECRET_KEY is unchanged, but set FERNET_KEY in production."
        )
        secret = current_app.config["SECRET_KEY"].encode()
        key = base64.urlsafe_b64encode(hashlib.sha256(secret).digest()).decode()
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_str(value: str) -> str:
    return _get_fernet().encrypt(value.encode()).decode()


def decrypt_str(token: str) -> str:
    try:
        return _get_fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        log.error("Failed to decrypt a secret (wrong or rotated FERNET_KEY).")
        raise


def encrypt_json(data: dict[str, Any]) -> str:
    return encrypt_str(json.dumps(data, ensure_ascii=False))


def decrypt_json(token: str) -> dict[str, Any]:
    return json.loads(decrypt_str(token))

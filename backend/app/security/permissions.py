"""Role-based access control — the permission matrix from spec §3.

Roles: admin, supervisor, agent. Some agent abilities are scoped to "self"
(e.g. assigning only to themselves); that nuance is enforced in route logic,
while this module answers the coarse "is this action allowed for the role".
"""
from __future__ import annotations

import enum
from functools import wraps

from flask import jsonify
from flask_login import current_user


class Permission(str, enum.Enum):
    VIEW_CONVERSATIONS = "view_conversations"
    REPLY_CONVERSATIONS = "reply_conversations"
    ASSIGN_CONVERSATIONS = "assign_conversations"          # others; agent=self only
    CHANGE_CONVERSATION_STATE = "change_conversation_state"
    TOGGLE_AI_CONVERSATION = "toggle_ai_conversation"
    AI_KILL_SWITCH = "ai_kill_switch"                      # global stop
    MANAGE_KB = "manage_kb"                                # agent = view only
    MANAGE_CHANNELS = "manage_channels"
    MANAGE_USERS = "manage_users"
    AI_SETTINGS = "ai_settings"
    MANAGE_ORG_SETTINGS = "manage_org_settings"            # automation, hours, retention
    VIEW_REPORTS = "view_reports"                          # agent = own only
    VIEW_AUDIT_LOG = "view_audit_log"


# role name -> set of granted permissions
ROLE_PERMISSIONS: dict[str, set[Permission]] = {
    "admin": set(Permission),  # everything
    "supervisor": {
        Permission.VIEW_CONVERSATIONS,
        Permission.REPLY_CONVERSATIONS,
        Permission.ASSIGN_CONVERSATIONS,
        Permission.CHANGE_CONVERSATION_STATE,
        Permission.TOGGLE_AI_CONVERSATION,
        Permission.AI_KILL_SWITCH,
        Permission.MANAGE_KB,
        Permission.VIEW_REPORTS,
        Permission.VIEW_AUDIT_LOG,
    },
    "agent": {
        Permission.VIEW_CONVERSATIONS,
        Permission.REPLY_CONVERSATIONS,
        Permission.ASSIGN_CONVERSATIONS,   # self only (checked in route logic)
        Permission.CHANGE_CONVERSATION_STATE,
        Permission.TOGGLE_AI_CONVERSATION,
        Permission.VIEW_REPORTS,           # own only (checked in route logic)
    },
}


def role_has(role: str, perm: Permission) -> bool:
    return perm in ROLE_PERMISSIONS.get(role, set())


def current_user_has(perm: Permission) -> bool:
    if not getattr(current_user, "is_authenticated", False):
        return False
    role = getattr(current_user, "role", None)
    if role is None:
        return False
    role_value = getattr(role, "value", role)
    return role_has(str(role_value), perm)


def require_permission(perm: Permission):
    """Decorator guarding an API route by permission (assumes login required)."""

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not getattr(current_user, "is_authenticated", False):
                return jsonify(error="unauthorized"), 401
            if not current_user_has(perm):
                return jsonify(error="forbidden", permission=perm.value), 403
            return fn(*args, **kwargs)

        return wrapper

    return decorator

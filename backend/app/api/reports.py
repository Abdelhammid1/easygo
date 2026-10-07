"""Reports & analytics (spec §5.6, RP-1..RP-8)."""
from __future__ import annotations

import csv
import io
from datetime import timedelta

from flask import Blueprint, Response, jsonify, request
from flask_login import current_user, login_required

from app.extensions import db
from app.models.ai import AIRun
from app.models.base import utcnow
from app.models.core import Conversation, Message
from app.models.enums import MessageDirection, SenderType, UserRole
from app.security.permissions import Permission, require_permission

bp = Blueprint("reports", __name__, url_prefix="/api/reports")


def _agent_scope_only() -> bool:
    role = getattr(current_user.role, "value", current_user.role)
    return role == UserRole.AGENT.value


@bp.get("/summary")
@login_required
@require_permission(Permission.VIEW_REPORTS)
def summary():
    # Org-wide KPIs are for supervisors+; agents see only their own performance
    # via /reports/agents and the scoped CSV export (spec §3).
    if _agent_scope_only():
        return jsonify(error="forbidden_agent_scope"), 403
    days = min(int(request.args.get("days", 30)), 180)
    since = utcnow() - timedelta(days=days)

    # RP-1: conversations by channel.
    by_channel = {
        cid: n for cid, n in db.session.execute(
            db.select(Conversation.channel_id, db.func.count(Conversation.id))
            .group_by(Conversation.channel_id)
        ).all()
    }

    # by state.
    by_state = {
        getattr(s, "value", s): n for s, n in db.session.execute(
            db.select(Conversation.state, db.func.count(Conversation.id))
            .group_by(Conversation.state)
        ).all()
    }

    # RP-1: conversations created per day.
    by_day = [
        {"day": d.isoformat() if hasattr(d, "isoformat") else str(d), "count": n}
        for d, n in db.session.execute(
            db.select(db.func.date(Conversation.created_at), db.func.count(Conversation.id))
            .where(Conversation.created_at >= since)
            .group_by(db.func.date(Conversation.created_at))
            .order_by(db.func.date(Conversation.created_at))
        ).all()
    ]

    # RP-3 + RP-7: AI usage.
    ai_total = db.session.scalar(
        db.select(db.func.count(AIRun.id)).where(AIRun.created_at >= since)) or 0
    ai_escalated = db.session.scalar(
        db.select(db.func.count(AIRun.id))
        .where(AIRun.created_at >= since, AIRun.escalated.is_(True))) or 0
    ai_cost = db.session.scalar(
        db.select(db.func.coalesce(db.func.sum(AIRun.cost_usd), 0))
        .where(AIRun.created_at >= since))

    # RP-4: escalation reasons.
    escalation_reasons = {
        getattr(r, "value", r): n for r, n in db.session.execute(
            db.select(AIRun.escalation_reason, db.func.count(AIRun.id))
            .where(AIRun.created_at >= since, AIRun.escalated.is_(True))
            .group_by(AIRun.escalation_reason)
        ).all() if r is not None
    }

    # RP-2: average first-response time (seconds), via first outbound per conversation.
    first_out = (
        db.select(Message.conversation_id,
                  db.func.min(Message.created_at).label("t"))
        .where(Message.direction == MessageDirection.OUTBOUND)
        .group_by(Message.conversation_id)
        .subquery()
    )
    avg_first_response = db.session.scalar(
        db.select(db.func.avg(
            db.func.extract("epoch", first_out.c.t - Conversation.created_at)))
        .select_from(Conversation)
        .join(first_out, first_out.c.conversation_id == Conversation.id)
        .where(Conversation.created_at >= since)
    )

    return jsonify(
        window_days=days,
        conversations_by_channel={str(k): v for k, v in by_channel.items()},
        conversations_by_state=by_state,
        conversations_by_day=by_day,
        ai={
            "runs": ai_total,
            "escalated": ai_escalated,
            "resolved_by_ai": ai_total - ai_escalated,
            "escalation_rate": round(ai_escalated / ai_total, 3) if ai_total else 0,
            "estimated_cost_usd": float(ai_cost or 0),
        },
        escalation_reasons=escalation_reasons,
        avg_first_response_seconds=round(float(avg_first_response), 1) if avg_first_response else None,
    )


@bp.get("/agents")
@login_required
@require_permission(Permission.VIEW_REPORTS)
def agents():
    """RP-5: per-agent handled conversations + messages sent."""
    msgs = db.session.execute(
        db.select(Message.sender_user_id, db.func.count(Message.id))
        .where(Message.sender_type == SenderType.AGENT,
               Message.sender_user_id.is_not(None))
        .group_by(Message.sender_user_id)
    ).all()
    rows = [{"user_id": uid, "messages_sent": n} for uid, n in msgs]
    if _agent_scope_only():
        rows = [r for r in rows if r["user_id"] == current_user.id]
    return jsonify(agents=rows)


@bp.get("/export/conversations.csv")
@login_required
@require_permission(Permission.VIEW_REPORTS)
def export_conversations():
    """RP-8: CSV export of conversations."""
    query = db.select(Conversation).order_by(Conversation.created_at.desc()).limit(5000)
    if _agent_scope_only():
        query = query.where(Conversation.assignee_id == current_user.id)
    rows = db.session.scalars(query).all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "channel_id", "contact_id", "state", "ai_mode",
                     "assignee_id", "escalation_reason", "created_at", "last_message_at"])
    for c in rows:
        writer.writerow([
            c.id, c.channel_id, c.contact_id,
            getattr(c.state, "value", c.state),
            getattr(c.ai_mode, "value", c.ai_mode),
            c.assignee_id or "",
            getattr(c.escalation_reason, "value", c.escalation_reason) or "",
            c.created_at.isoformat() if c.created_at else "",
            c.last_message_at.isoformat() if c.last_message_at else "",
        ])
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=conversations.csv"},
    )

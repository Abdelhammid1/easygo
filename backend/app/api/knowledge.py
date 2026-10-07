"""Knowledge base API (spec §7): CRUD, file ingestion, playground, suggestions."""
from __future__ import annotations

import os
import uuid
from datetime import timedelta

from flask import Blueprint, current_app, jsonify, request
from flask_login import login_required
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models.ai import AIRun, KBItem
from app.models.base import utcnow
from app.models.core import Message
from app.models.enums import EscalationReason
from app.security.permissions import Permission, require_permission
from app.services import audit, knowledge
from app.services.ai import service as ai_service

bp = Blueprint("knowledge", __name__, url_prefix="/api/knowledge")

_EXT_TO_TYPE = {
    ".txt": "txt", ".md": "txt", ".csv": "csv",
    ".pdf": "pdf", ".docx": "docx", ".xlsx": "xlsx",
}
STALE_AFTER_DAYS = 120


def _item_json(i: KBItem) -> dict:
    return {
        "id": i.id,
        "title": i.title,
        "category": i.category,
        "is_active": i.is_active,
        "source_type": i.source_type,
        "chunk_count": len(i.chunks),
        "updated_at": i.updated_at.isoformat() if i.updated_at else None,
        "content": i.content,
    }


@bp.get("")
@login_required
@require_permission(Permission.VIEW_CONVERSATIONS)  # agents may view (spec §3)
def list_items():
    rows = db.session.scalars(db.select(KBItem).order_by(KBItem.id.desc())).all()
    return jsonify(items=[_item_json(i) for i in rows])


@bp.post("")
@login_required
@require_permission(Permission.MANAGE_KB)
def create_item():
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify(error="title_required"), 400
    item = KBItem(
        title=title,
        content=data.get("content") or "",
        category=(data.get("category") or None),
        source_type="text",
        is_active=bool(data.get("is_active", True)),
    )
    db.session.add(item)
    db.session.flush()
    knowledge.reindex_item(item)
    audit.record("kb.create", entity_type="kb_item", entity_id=item.id)
    db.session.commit()
    return jsonify(item=_item_json(item)), 201


@bp.put("/<int:item_id>")
@login_required
@require_permission(Permission.MANAGE_KB)
def update_item(item_id: int):
    item = db.session.get(KBItem, item_id)
    if item is None:
        return jsonify(error="not_found"), 404
    data = request.get_json(silent=True) or {}
    content_changed = False
    if "title" in data and data["title"]:
        item.title = str(data["title"]).strip()
    if "category" in data:
        item.category = data["category"] or None
    if "is_active" in data:
        item.is_active = bool(data["is_active"])
    if "content" in data:
        item.content = data["content"] or ""
        content_changed = True
    if content_changed:
        knowledge.reindex_item(item)
    audit.record("kb.update", entity_type="kb_item", entity_id=item.id)
    db.session.commit()
    return jsonify(item=_item_json(item))


@bp.delete("/<int:item_id>")
@login_required
@require_permission(Permission.MANAGE_KB)
def delete_item(item_id: int):
    item = db.session.get(KBItem, item_id)
    if item is None:
        return jsonify(error="not_found"), 404
    audit.record("kb.delete", entity_type="kb_item", entity_id=item.id,
                 before={"title": item.title})
    db.session.delete(item)
    db.session.commit()
    return jsonify(ok=True)


@bp.post("/upload")
@login_required
@require_permission(Permission.MANAGE_KB)
def upload_item():
    """Create a KB item from an uploaded file (PDF/Word/Excel/CSV/text), KB-2."""
    file = request.files.get("file")
    if file is None or not file.filename:
        return jsonify(error="file_required"), 400
    filename = secure_filename(file.filename)
    ext = os.path.splitext(filename)[1].lower()
    source_type = _EXT_TO_TYPE.get(ext)
    if source_type is None:
        return jsonify(error="unsupported_type", allowed=sorted(_EXT_TO_TYPE)), 400

    kb_dir = os.path.join(current_app.config["MEDIA_ROOT"], "kb")
    os.makedirs(kb_dir, exist_ok=True)
    dest = os.path.join(kb_dir, f"{uuid.uuid4().hex}{ext}")
    file.save(dest)

    text = knowledge.extract_text(dest, source_type)
    item = KBItem(
        title=(request.form.get("title") or filename).strip(),
        content=text,
        category=(request.form.get("category") or None),
        source_type=source_type,
        source_path=dest,
        is_active=True,
    )
    db.session.add(item)
    db.session.flush()
    n = knowledge.reindex_item(item)
    audit.record("kb.upload", entity_type="kb_item", entity_id=item.id,
                 after={"source_type": source_type, "chunks": n})
    db.session.commit()
    return jsonify(item=_item_json(item), extracted_chars=len(text), chunks=n), 201


@bp.post("/playground")
@login_required
@require_permission(Permission.MANAGE_KB)
def playground():
    query = (request.get_json(silent=True) or {}).get("query", "").strip()
    if not query:
        return jsonify(error="query_required"), 400
    try:
        return jsonify(result=ai_service.playground(query))
    except Exception as exc:  # noqa: BLE001
        return jsonify(error="ai_error", detail=str(exc)), 502


@bp.get("/stale")
@login_required
@require_permission(Permission.MANAGE_KB)
def stale_items():
    """Items not updated in a while (KB-6)."""
    cutoff = utcnow() - timedelta(days=STALE_AFTER_DAYS)
    rows = db.session.scalars(
        db.select(KBItem).where(KBItem.updated_at < cutoff).order_by(KBItem.updated_at)
    ).all()
    return jsonify(items=[_item_json(i) for i in rows], stale_after_days=STALE_AFTER_DAYS)


@bp.get("/suggestions")
@login_required
@require_permission(Permission.MANAGE_KB)
def suggestions():
    """Questions the AI couldn't answer, to add to the KB (KB-7 / RP-6)."""
    rows = db.session.execute(
        db.select(AIRun, Message.body)
        .join(Message, AIRun.message_id == Message.id)
        .where(AIRun.escalated.is_(True),
               AIRun.escalation_reason == EscalationReason.NO_KB_ANSWER)
        .order_by(AIRun.created_at.desc())
        .limit(50)
    ).all()
    return jsonify(suggestions=[
        {"question": body, "confidence": run.confidence,
         "at": run.created_at.isoformat() if run.created_at else None}
        for run, body in rows if body
    ])

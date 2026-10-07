"""Contacts (spec §5.3): view, edit, block, and merge across channels."""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import login_required

from app.extensions import db
from app.models.core import Contact, ContactIdentity, Conversation
from app.security.permissions import Permission, require_permission
from app.services import audit

bp = Blueprint("contacts", __name__, url_prefix="/api/contacts")


def _contact_json(c: Contact, *, with_identities: bool = False) -> dict:
    data = {
        "id": c.id,
        "name": c.name,
        "phone": c.phone,
        "address": c.address,
        "notes": c.notes,
        "is_blocked": c.is_blocked,
        "custom_fields": c.custom_fields or {},
    }
    if with_identities:
        data["identities"] = [
            {
                "id": i.id,
                "channel_id": i.channel_id,
                "external_id": i.external_id,
                "display_name": i.display_name,
            }
            for i in c.identities
        ]
    return data


@bp.get("")
@login_required
@require_permission(Permission.VIEW_CONVERSATIONS)
def list_contacts():
    q = (request.args.get("q") or "").strip()
    query = db.select(Contact).order_by(Contact.id.desc()).limit(100)
    if q:
        like = f"%{q}%"
        query = db.select(Contact).where(
            db.or_(Contact.name.ilike(like), Contact.phone.ilike(like))
        ).order_by(Contact.id.desc()).limit(100)
    rows = db.session.scalars(query).all()
    return jsonify(contacts=[_contact_json(c) for c in rows])


@bp.get("/<int:contact_id>")
@login_required
@require_permission(Permission.VIEW_CONVERSATIONS)
def get_contact(contact_id: int):
    contact = db.session.get(Contact, contact_id)
    if contact is None:
        return jsonify(error="not_found"), 404
    convs = db.session.scalars(
        db.select(Conversation).where(Conversation.contact_id == contact_id)
        .order_by(Conversation.last_message_at.desc().nullslast())
    ).all()
    return jsonify(
        contact=_contact_json(contact, with_identities=True),
        conversations=[{"id": c.id, "state": getattr(c.state, "value", c.state),
                        "channel_id": c.channel_id} for c in convs],
    )


@bp.put("/<int:contact_id>")
@login_required
@require_permission(Permission.VIEW_CONVERSATIONS)
def update_contact(contact_id: int):
    contact = db.session.get(Contact, contact_id)
    if contact is None:
        return jsonify(error="not_found"), 404
    data = request.get_json(silent=True) or {}
    for field in ("name", "phone", "address", "notes"):
        if field in data:
            setattr(contact, field, (data[field] or None))
    if "custom_fields" in data and isinstance(data["custom_fields"], dict):
        contact.custom_fields = data["custom_fields"]
    db.session.commit()
    return jsonify(contact=_contact_json(contact, with_identities=True))


@bp.post("/<int:contact_id>/block")
@login_required
@require_permission(Permission.VIEW_CONVERSATIONS)
def set_block(contact_id: int):
    contact = db.session.get(Contact, contact_id)
    if contact is None:
        return jsonify(error="not_found"), 404
    blocked = bool((request.get_json(silent=True) or {}).get("blocked", True))
    contact.is_blocked = blocked
    audit.record("contact.block" if blocked else "contact.unblock",
                 entity_type="contact", entity_id=contact.id)
    db.session.commit()
    return jsonify(contact=_contact_json(contact))


@bp.post("/<int:contact_id>/merge")
@login_required
@require_permission(Permission.VIEW_CONVERSATIONS)
def merge_contact(contact_id: int):
    """Merge `source_id` into this contact: identities + conversations move over."""
    target = db.session.get(Contact, contact_id)
    if target is None:
        return jsonify(error="not_found"), 404
    source_id = (request.get_json(silent=True) or {}).get("source_id")
    if not source_id or source_id == contact_id:
        return jsonify(error="invalid_source"), 400
    source = db.session.get(Contact, source_id)
    if source is None:
        return jsonify(error="source_not_found"), 404

    # Reassign via bulk UPDATE (not the ORM relationship): touching
    # source.identities would let delete-orphan cascade delete the rows we move.
    db.session.execute(
        db.update(ContactIdentity).where(ContactIdentity.contact_id == source.id)
        .values(contact_id=target.id)
    )
    db.session.execute(
        db.update(Conversation).where(Conversation.contact_id == source.id)
        .values(contact_id=target.id)
    )
    # Keep any notes from the source.
    if source.notes and source.notes not in (target.notes or ""):
        target.notes = "\n".join(filter(None, [target.notes, source.notes]))
    target.is_blocked = target.is_blocked or source.is_blocked

    audit.record("contact.merge", entity_type="contact", entity_id=target.id,
                 after={"merged_from": source.id})
    # Drop any cached (now-stale) collection so the cascade sees no children.
    db.session.expire(source)
    db.session.delete(source)
    db.session.commit()
    return jsonify(contact=_contact_json(target, with_identities=True))

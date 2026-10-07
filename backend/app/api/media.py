"""Protected media serving — attachments are behind auth (spec §4, §10)."""
from __future__ import annotations

import os

from flask import Blueprint, abort, jsonify, send_file
from flask_login import login_required

from app.extensions import db
from app.models.core import Attachment

bp = Blueprint("media", __name__, url_prefix="/api/media")


@bp.get("/attachments/<int:attachment_id>")
@login_required
def get_attachment(attachment_id: int):
    att = db.session.get(Attachment, attachment_id)
    if att is None:
        return jsonify(error="not_found"), 404
    path = att.storage_path
    # Guard against path traversal / files outside the media root.
    from flask import current_app
    media_root = os.path.realpath(current_app.config["MEDIA_ROOT"])
    real = os.path.realpath(path)
    if not real.startswith(media_root + os.sep) or not os.path.isfile(real):
        abort(404)
    return send_file(real, mimetype=att.mime_type or "application/octet-stream")

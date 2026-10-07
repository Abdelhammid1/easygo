"""Background job queue (RQ over Redis).

Reception is separated from processing (spec §4.1): webhooks store the raw
message and enqueue a job; the worker picks it up and does the heavy work
(media handling, AI, outbound send). Phase 0 provides the plumbing and a
placeholder task; Phase 1 fills in the real pipeline.
"""
from __future__ import annotations

import logging
import os

from redis import Redis
from rq import Queue

log = logging.getLogger(__name__)

INCOMING_QUEUE = "incoming"
AI_QUEUE = "ai"
OUTGOING_QUEUE = "outgoing"


def get_connection() -> Redis:
    return Redis.from_url(os.environ.get("REDIS_URL", "redis://redis:6379/0"))


def get_queue(name: str = INCOMING_QUEUE) -> Queue:
    return Queue(name, connection=get_connection())


def enqueue_incoming(message_id: int) -> None:
    """Hand a stored inbound message to the worker for processing (§4.1)."""
    from app.tasks.pipeline import process_incoming_message

    get_queue(INCOMING_QUEUE).enqueue(process_incoming_message, message_id)

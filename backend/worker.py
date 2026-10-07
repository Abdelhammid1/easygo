"""RQ worker entrypoint — processes incoming messages, AI jobs, outgoing sends.

Uses SimpleWorker (no fork): jobs run in this process, so the Flask app and its
DB engine are created once (in the pipeline task) and reused, avoiding both
duplicate apps and fork/connection-sharing issues. Fine for this scale.
"""
from rq import SimpleWorker

from app.tasks.queue import AI_QUEUE, INCOMING_QUEUE, OUTGOING_QUEUE, get_connection

if __name__ == "__main__":
    worker = SimpleWorker(
        [INCOMING_QUEUE, AI_QUEUE, OUTGOING_QUEUE],
        connection=get_connection(),
    )
    worker.work(with_scheduler=True)

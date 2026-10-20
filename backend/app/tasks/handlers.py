"""Mapeamento tipo de job -> função. Cada handler recebe o payload (dict)."""
from app.services import broadcast_service, instagram_service, webhook_service
from app.workflow import engine


def _process_webhook_event(payload: dict) -> None:
    webhook_service.process_event(payload["event_id"])


def _resume_execution(payload: dict) -> None:
    engine.resume(payload["execution_id"])


def _wait_timeout(payload: dict) -> None:
    engine.wait_timeout(payload["execution_id"], payload["node_id"], int(payload["steps"]))


def _broadcast_start(payload: dict) -> None:
    broadcast_service.start(payload["broadcast_id"])


def _broadcast_batch(payload: dict) -> None:
    broadcast_service.send_batch(payload["broadcast_id"])


def _refresh_tokens(payload: dict) -> None:
    instagram_service.refresh_expiring_tokens()


HANDLERS = {
    "process_webhook_event": _process_webhook_event,
    "resume_execution": _resume_execution,
    "wait_timeout": _wait_timeout,
    "broadcast_start": _broadcast_start,
    "broadcast_batch": _broadcast_batch,
    "refresh_tokens": _refresh_tokens,
}

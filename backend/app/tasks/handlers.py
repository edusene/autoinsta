"""Mapeamento tipo de job -> função. Cada handler recebe o payload (dict)."""
from app.services import instagram_service, webhook_service
from app.workflow import engine


def _process_webhook_event(payload: dict) -> None:
    webhook_service.process_event(payload["event_id"])


def _resume_execution(payload: dict) -> None:
    engine.resume(payload["execution_id"])


def _refresh_tokens(payload: dict) -> None:
    instagram_service.refresh_expiring_tokens()


HANDLERS = {
    "process_webhook_event": _process_webhook_event,
    "resume_execution": _resume_execution,
    "refresh_tokens": _refresh_tokens,
}

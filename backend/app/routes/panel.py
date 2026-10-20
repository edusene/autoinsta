"""Rotas do painel: dashboard, contatos, caixa de entrada, logs/execuções e configurações."""
import uuid
from typing import Literal

from flask import Blueprint, request
from pydantic import BaseModel, Field

from app.errors import AppError, ok
from app.extensions import limiter
from app.services import contact_service, dashboard_service, execution_service, inbox_service, settings_service
from app.utils.auth import current_user_id, require_auth
from app.utils.http import pagination, parse_body

bp = Blueprint("panel", __name__, url_prefix="/api")

EXECUTION_STATUSES = {"running", "waiting", "success", "error", "cancelled"}


class SettingsBody(BaseModel):
    ai_default_model: str | None = Field(default=None, max_length=80)


class ContactBody(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=4000)
    status: Literal["active", "blocked", "archived"] | None = None
    tags: list[str] | None = Field(default=None, max_length=30)
    automation_paused: bool | None = None


class InboxMessageBody(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


@bp.get("/dashboard")
@require_auth
def dashboard():
    return ok(dashboard_service.summary(current_user_id()))


@bp.get("/contacts")
@require_auth
def contacts():
    limit, offset = pagination()
    search = (request.args.get("search") or "").strip()[:100] or None
    tag = (request.args.get("tag") or "").strip().lower()[:40] or None
    return ok(contact_service.list_contacts(current_user_id(), search, limit, offset, tag))


@bp.get("/contacts/tags")
@require_auth
def contact_tags():
    return ok(contact_service.list_tags(current_user_id()))


@bp.get("/contacts/<uuid:contact_id>")
@require_auth
def contact(contact_id):
    return ok(contact_service.get_contact(current_user_id(), str(contact_id)))


@bp.put("/contacts/<uuid:contact_id>")
@require_auth
def update_contact(contact_id):
    body = parse_body(ContactBody)
    return ok(contact_service.update_contact(current_user_id(), str(contact_id), body.model_dump(exclude_unset=True)))


# --- caixa de entrada ---------------------------------------------------------

@bp.get("/inbox/conversations")
@require_auth
def conversations():
    limit, offset = pagination(default_limit=30)
    search = (request.args.get("search") or "").strip()[:100] or None
    unread = request.args.get("filter") == "unread"
    return ok(inbox_service.list_conversations(current_user_id(), search, unread, limit, offset))


@bp.get("/inbox/unread-count")
@require_auth
def unread_count():
    return ok({"unread_conversations": inbox_service.unread_count(current_user_id())})


@bp.get("/inbox/conversations/<uuid:contact_id>")
@require_auth
def conversation(contact_id):
    return ok(inbox_service.get_conversation(current_user_id(), str(contact_id)))


@bp.post("/inbox/conversations/<uuid:contact_id>/read")
@require_auth
def read_conversation(contact_id):
    inbox_service.mark_read(current_user_id(), str(contact_id))
    return ok({"read": True})


@bp.post("/inbox/conversations/<uuid:contact_id>/messages")
@require_auth
@limiter.limit("30 per minute")
def send_inbox_message(contact_id):
    body = parse_body(InboxMessageBody)
    return ok(inbox_service.send_message(current_user_id(), str(contact_id), body.text), 201)


@bp.get("/logs")
@require_auth
def logs():
    limit, offset = pagination()
    status = request.args.get("status") or None
    if status and status not in EXECUTION_STATUSES:
        raise AppError("VALIDATION_ERROR", "Status inválido.")
    workflow_id = request.args.get("workflow_id") or None
    if workflow_id:
        try:
            workflow_id = str(uuid.UUID(workflow_id))
        except ValueError:
            raise AppError("VALIDATION_ERROR", "workflow_id inválido.")
    return ok(execution_service.list_executions(current_user_id(), workflow_id, status, limit, offset))


@bp.get("/executions/<uuid:execution_id>")
@require_auth
def execution(execution_id):
    return ok(execution_service.get_execution(current_user_id(), str(execution_id)))


@bp.get("/settings")
@require_auth
def get_settings():
    return ok(settings_service.get_settings(current_user_id()))


@bp.put("/settings")
@require_auth
def update_settings():
    body = parse_body(SettingsBody)
    return ok(settings_service.update_settings(current_user_id(), body.ai_default_model))

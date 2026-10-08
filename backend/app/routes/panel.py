"""Rotas do painel: dashboard, contatos, logs/execuções e configurações."""
import uuid

from flask import Blueprint, request
from pydantic import BaseModel, Field

from app.errors import AppError, ok
from app.services import contact_service, dashboard_service, execution_service, settings_service
from app.utils.auth import current_user_id, require_auth
from app.utils.http import pagination, parse_body

bp = Blueprint("panel", __name__, url_prefix="/api")

EXECUTION_STATUSES = {"running", "waiting", "success", "error", "cancelled"}


class SettingsBody(BaseModel):
    ai_default_model: str | None = Field(default=None, max_length=80)


@bp.get("/dashboard")
@require_auth
def dashboard():
    return ok(dashboard_service.summary(current_user_id()))


@bp.get("/contacts")
@require_auth
def contacts():
    limit, offset = pagination()
    search = (request.args.get("search") or "").strip()[:100] or None
    return ok(contact_service.list_contacts(current_user_id(), search, limit, offset))


@bp.get("/contacts/<uuid:contact_id>")
@require_auth
def contact(contact_id):
    return ok(contact_service.get_contact(current_user_id(), str(contact_id)))


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

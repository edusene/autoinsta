"""Disparos em massa."""
from datetime import datetime

from flask import Blueprint, request
from pydantic import BaseModel, Field

from app.errors import AppError, ok
from app.services import broadcast_service
from app.utils.auth import current_user_id, require_auth
from app.utils.http import pagination, parse_body

bp = Blueprint("broadcasts", __name__, url_prefix="/api/broadcasts")

RECIPIENT_STATUSES = {"pending", "processing", "sent", "skipped", "failed"}


class ButtonBody(BaseModel):
    id: str | None = Field(default=None, max_length=32)
    title: str = Field(max_length=40)
    url: str = Field(max_length=2000)


class AudienceBody(BaseModel):
    tags: list[str] = Field(default_factory=list, max_length=20)


class CreateBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    text: str = Field(default="", max_length=1000)
    buttons: list[ButtonBody] = Field(default_factory=list, max_length=3)
    audience: AudienceBody = Field(default_factory=AudienceBody)
    track_links: bool = True


class UpdateBody(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    text: str | None = Field(default=None, max_length=1000)
    buttons: list[ButtonBody] | None = Field(default=None, max_length=3)
    audience: AudienceBody | None = None
    track_links: bool | None = None


class SendBody(BaseModel):
    scheduled_at: datetime | None = None


@bp.get("")
@require_auth
def list_broadcasts():
    return ok(broadcast_service.list_broadcasts(current_user_id()))


@bp.post("")
@require_auth
def create_broadcast():
    body = parse_body(CreateBody)
    return ok(broadcast_service.create_broadcast(current_user_id(), body.model_dump()), 201)


@bp.post("/audience-preview")
@require_auth
def audience_preview():
    body = parse_body(AudienceBody)
    return ok(broadcast_service.audience_preview(current_user_id(), body.model_dump()))


@bp.get("/<uuid:broadcast_id>")
@require_auth
def get_broadcast(broadcast_id):
    return ok(broadcast_service.get_broadcast(current_user_id(), str(broadcast_id)))


@bp.put("/<uuid:broadcast_id>")
@require_auth
def update_broadcast(broadcast_id):
    body = parse_body(UpdateBody)
    fields = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    return ok(broadcast_service.update_broadcast(current_user_id(), str(broadcast_id), fields))


@bp.delete("/<uuid:broadcast_id>")
@require_auth
def delete_broadcast(broadcast_id):
    broadcast_service.delete_broadcast(current_user_id(), str(broadcast_id))
    return ok({"deleted": True})


@bp.post("/<uuid:broadcast_id>/send")
@require_auth
def send_broadcast(broadcast_id):
    body = parse_body(SendBody)
    return ok(broadcast_service.send(current_user_id(), str(broadcast_id), body.scheduled_at))


@bp.post("/<uuid:broadcast_id>/cancel")
@require_auth
def cancel_broadcast(broadcast_id):
    return ok(broadcast_service.cancel(current_user_id(), str(broadcast_id)))


@bp.get("/<uuid:broadcast_id>/recipients")
@require_auth
def recipients(broadcast_id):
    limit, offset = pagination(default_limit=50)
    status = request.args.get("status") or None
    if status and status not in RECIPIENT_STATUSES:
        raise AppError("VALIDATION_ERROR", "Status inválido.")
    return ok(broadcast_service.list_recipients(current_user_id(), str(broadcast_id), status, limit, offset))

from flask import Blueprint
from typing import Literal

from pydantic import BaseModel, Field

from app.errors import ok
from app.extensions import limiter
from app.services import instagram_service, webhook_service
from app.utils.auth import current_user_id, require_auth
from app.utils.http import pagination, parse_body

bp = Blueprint("instagram", __name__, url_prefix="/api/instagram")


class SimulateBody(BaseModel):
    kind: Literal["message", "comment", "new_contact", "story_mention", "story_reply", "ig_me_link",
                  "reaction", "live_comment"] = "message"
    text: str = Field(default="", max_length=1000)


class CallbackBody(BaseModel):
    code: str = Field(min_length=1, max_length=2048)
    state: str = Field(min_length=1, max_length=1024)


def _status(data: dict | None = None) -> dict:
    """Status da conexão + quais formas de conectar este usuário pode usar."""
    data = data or instagram_service.get_status(current_user_id())
    return {**data, "connect_options": instagram_service.connect_options()}


@bp.get("/status")
@require_auth
def status():
    return ok(_status())


@bp.get("/connect")
@require_auth
@limiter.limit("20 per minute")
def connect():
    return ok({"authorize_url": instagram_service.build_connect_url(current_user_id())})


@bp.post("/callback")
@require_auth
@limiter.limit("20 per minute")
def callback():
    body = parse_body(CallbackBody)
    return ok(_status(instagram_service.complete_connection(current_user_id(), body.code, body.state)))


@bp.post("/disconnect")
@require_auth
def disconnect():
    return ok(_status(instagram_service.disconnect(current_user_id())))


@bp.post("/resubscribe")
@require_auth
@limiter.limit("10 per minute")
def resubscribe():
    return ok(_status(instagram_service.resubscribe(current_user_id())))


@bp.get("/events")
@require_auth
def events():
    """Eventos recebidos da Meta para a conta conectada + tentativas recusadas."""
    limit, _ = pagination(default_limit=30, max_limit=100)
    return ok(webhook_service.list_events(current_user_id(), limit))


@bp.post("/simulate")
@require_auth
@limiter.limit("20 per minute")
def simulate():
    """Simula uma DM/comentário: roda os workflows ativos sem enviar nada ao Instagram."""
    body = parse_body(SimulateBody)
    return ok(webhook_service.simulate(current_user_id(), body.kind, body.text.strip()), 201)


@bp.get("/diagnostics")
@require_auth
@limiter.limit("20 per minute")
def diagnostics():
    return ok(instagram_service.diagnostics(current_user_id()))

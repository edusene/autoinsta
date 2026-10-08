from flask import Blueprint, g
from pydantic import BaseModel, Field

from app.errors import ok
from app.extensions import limiter
from app.services import instagram_service
from app.utils.auth import current_user_id, require_auth
from app.utils.http import parse_body

bp = Blueprint("instagram", __name__, url_prefix="/api/instagram")


class CallbackBody(BaseModel):
    code: str = Field(min_length=1, max_length=2048)
    state: str = Field(min_length=1, max_length=1024)


def _status(data: dict | None = None) -> dict:
    """Status da conexão + quais formas de conectar este usuário pode usar."""
    data = data or instagram_service.get_status(current_user_id())
    return {**data, "connect_options": instagram_service.connect_options(g.user.email)}


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


@bp.post("/connect-token")
@require_auth
@limiter.limit("10 per minute")
def connect_token():
    """Conecta com o token gerado no painel da Meta (configurado no servidor)."""
    return ok(_status(instagram_service.connect_with_server_token(current_user_id(), g.user.email)))


@bp.post("/disconnect")
@require_auth
def disconnect():
    return ok(_status(instagram_service.disconnect(current_user_id())))


@bp.post("/resubscribe")
@require_auth
@limiter.limit("10 per minute")
def resubscribe():
    return ok(_status(instagram_service.resubscribe(current_user_id())))


@bp.get("/diagnostics")
@require_auth
@limiter.limit("20 per minute")
def diagnostics():
    return ok(instagram_service.diagnostics(current_user_id()))

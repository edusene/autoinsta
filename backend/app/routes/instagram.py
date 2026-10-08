from flask import Blueprint
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


@bp.get("/status")
@require_auth
def status():
    return ok(instagram_service.get_status(current_user_id()))


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
    return ok(instagram_service.complete_connection(current_user_id(), body.code, body.state))


@bp.post("/disconnect")
@require_auth
def disconnect():
    return ok(instagram_service.disconnect(current_user_id()))


@bp.post("/resubscribe")
@require_auth
@limiter.limit("10 per minute")
def resubscribe():
    return ok(instagram_service.resubscribe(current_user_id()))


@bp.get("/diagnostics")
@require_auth
@limiter.limit("20 per minute")
def diagnostics():
    return ok(instagram_service.diagnostics(current_user_id()))

"""Links rastreados (CTR): /r/<código> registra o clique e redireciona para o destino."""
import logging
import re

from flask import Blueprint, abort, redirect, request

from app import db
from app.extensions import limiter
from app.repositories import message_repository

logger = logging.getLogger(__name__)

bp = Blueprint("links", __name__)

CODE_RE = re.compile(r"^[A-Za-z0-9_-]{4,16}$")
# Robôs que abrem o link para gerar a prévia (ex.: o próprio Instagram) não contam como clique
BOT_RE = re.compile(r"facebookexternalhit|facebot|meta-externalagent|bot|crawler|spider|preview|slurp", re.I)


@bp.get("/r/<code>")
@limiter.limit("120 per minute")
def follow(code: str):
    if not CODE_RE.match(code):
        abort(404)
    with db.connection() as conn:
        link = message_repository.get_link(conn, code)
        if not link:
            abort(404, description="Link não encontrado.")
        if not BOT_RE.search(request.headers.get("User-Agent", "")):
            message_repository.register_click(conn, link["id"], str(link["message_id"]))
    response = redirect(link["url"], code=302)
    response.headers["Cache-Control"] = "no-store"
    return response

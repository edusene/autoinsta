"""Entrega do painel (React compilado) e da configuração pública que ele usa.

Com isso API e painel rodam no mesmo serviço e no mesmo domínio:
  /api/*, /webhooks/*, /health  -> Flask
  /assets/*                     -> arquivos compilados do Vite
  qualquer outra rota           -> index.html (rotas do React Router)
"""
from pathlib import Path

from flask import Blueprint, abort, current_app, send_from_directory

from app.errors import ok
from app.extensions import limiter

bp = Blueprint("frontend", __name__)

BACKEND_PREFIXES = ("api/", "webhooks/", "health")


@bp.get("/api/public-config")
@limiter.exempt
def public_config():
    """Somente valores PÚBLICOS (seguros no navegador)."""
    cfg = current_app.config
    return ok({
        "supabase_url": cfg["SUPABASE_URL"],
        "supabase_anon_key": cfg["SUPABASE_ANON_KEY"],
        "privacy_contact_email": cfg["PRIVACY_CONTACT_EMAIL"],
        # Público (vai na URL de autorização); exibido para diagnosticar "Invalid redirect_uri"
        "meta_redirect_uri": cfg["META_REDIRECT_URI"],
    })


@bp.get("/", defaults={"path": ""})
@bp.get("/<path:path>")
@limiter.exempt
def spa(path: str):
    if path.startswith(BACKEND_PREFIXES):
        abort(404)
    dist = Path(current_app.config["FRONTEND_DIST"])
    index = dist / "index.html"
    if not index.is_file():
        abort(404, description="Painel não compilado (rode `npm run build` em frontend/).")
    # send_from_directory bloqueia path traversal (../)
    if path and (dist / path).is_file():
        response = send_from_directory(dist, path)
        if path.startswith("assets/"):  # nomes com hash: podem ficar em cache por 1 ano
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response
    response = send_from_directory(dist, "index.html")
    response.headers["Cache-Control"] = "no-cache"
    return response

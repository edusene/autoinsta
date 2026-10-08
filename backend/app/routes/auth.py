"""Cadastro, login, logout e refresh de sessão são feitos pelo SDK oficial do
Supabase Auth no frontend. A API só expõe o perfil do usuário autenticado."""
from flask import Blueprint, g

from app.errors import ok
from app.services import auth_service
from app.utils.auth import require_auth

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@bp.get("/me")
@require_auth
def me():
    profile = auth_service.get_profile(g.user.id)
    return ok({"id": g.user.id, "email": g.user.email, "display_name": profile and profile["display_name"]})

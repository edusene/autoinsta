"""Decorator de autenticação para as rotas da API."""
from functools import wraps

from flask import g, request

from app.errors import UnauthorizedError
from app.services import auth_service


def require_auth(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        scheme, _, token = header.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise UnauthorizedError()
        user = auth_service.verify_token(token.strip())
        # Garante a linha em profiles (FK de todas as tabelas do usuário).
        auth_service.ensure_profile(user)
        g.user = user
        return view(*args, **kwargs)

    return wrapper


def current_user_id() -> str:
    return g.user.id

from flask import g, request
from flask_limiter import Limiter


def _rate_limit_key() -> str:
    # Usuário autenticado quando disponível; caso contrário, IP.
    user = getattr(g, "user", None)
    return f"user:{user.id}" if user else f"ip:{request.remote_addr}"


limiter = Limiter(key_func=_rate_limit_key)
